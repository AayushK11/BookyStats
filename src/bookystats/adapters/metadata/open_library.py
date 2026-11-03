from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import NoReturn, cast

from pydantic import JsonValue, ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.dates import parse_date
from bookystats.domain.errors import ConnectorError, ProviderDeferredError
from bookystats.domain.identifiers import normalize_isbn, normalized_isbns, normalized_text
from bookystats.domain.interfaces import HttpFetcher, HttpResponse
from bookystats.domain.matching import (
    select_metadata_candidate,
    work_bibliography_compatible,
    work_candidate_keys,
)
from bookystats.domain.metadata import missing_fallback_fields
from bookystats.domain.models import (
    BookRecord,
    EnrichmentResult,
    FieldState,
    Issue,
    MetadataCandidate,
    Observation,
    Source,
    SyncState,
    utc_now,
)
from bookystats.persistence.cache import MetadataCache, MetadataCacheError
from bookystats.persistence.raw import RecordingFetcher


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError(S.GOOGLE_BOOKS_REJECT_CONSTANT_NON_FINITE_JSON_NUMBERS_ARE_NOT_CATALOG)


def _integer(value: JsonValue, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _text(value: JsonValue) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= C.OPEN_LIBRARY_TEXT
        and (S.GOOGLE_BOOKS_TEXT_TEXT not in value)
    )


def _strings(value: JsonValue, maximum: int = C.OPEN_LIBRARY_STRINGS) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= maximum
        and all(_text(item) and bool(cast(str, item).strip()) for item in value)
    )


def _rating(value: JsonValue) -> bool:
    return (
        isinstance(value, (int, float))
        and (not isinstance(value, bool))
        and (C.ONE <= value <= C.FIVE)
        and math.isfinite(value)
    )


class _Fields:
    def __init__(self, data: dict[str, JsonValue], url: str, observed_at: str) -> None:
        self.data = data
        self.url = url
        self.observed_at = observed_at
        self.observations: list[Observation] = []
        self.issues: list[Issue] = []

    def add(
        self, field: str, value: JsonValue = C.NONE, state: FieldState = FieldState.PRESENT
    ) -> None:
        self.observations.append(
            Observation(
                field=field,
                value=value,
                state=state,
                scope=S.WORK,
                source_url=self.url,
                observed_at=self.observed_at,
            )
        )

    def issue(self, field: str) -> None:
        self.issues.append(
            Issue(
                code=S.INVALID_METADATA_FIELD,
                message=S.FIELDS_ISSUE_MESSAGE_TEMPLATE_2.format(v0=field),
            )
        )

    def read(self, key: str, field: str, valid: Callable[[JsonValue], bool]) -> JsonValue:
        if key not in self.data:
            self.add(field, state=FieldState.UNAVAILABLE)
            return C.NONE
        value = self.data[key]
        if not valid(value):
            self.issue(field)
            self.add(field, state=FieldState.FAILED)
            return C.NONE
        if value == S.EMPTY or value == []:
            self.add(field, state=FieldState.EMPTY)
            return C.NONE
        self.add(field, value)
        return value


def _isbns(fields: _Fields) -> tuple[str, ...]:
    if S.ISBN not in fields.data:
        fields.add(S.ISBNS, state=FieldState.UNAVAILABLE)
        return ()
    raw = fields.data[S.ISBN]
    valid: set[str] = set()
    invalid = not isinstance(raw, list) or len(raw) > C.META_RUN_OPEN_LIBRARY_MAX_ISBNS
    if not invalid:
        for value in cast(list[JsonValue], raw):
            if not _text(value):
                invalid = C.TRUE
                continue
            assert isinstance(value, str)
            isbn = normalize_isbn(value)
            if isbn is C.NONE:
                invalid = C.TRUE
            else:
                valid.add(isbn)
    if invalid:
        fields.issue(S.ISBNS)
    result = tuple(sorted(valid))
    if result:
        fields.add(S.ISBNS, list(result))
    else:
        fields.add(S.ISBNS, state=FieldState.FAILED if invalid else FieldState.EMPTY)
    return result


def _series(fields: _Fields) -> None:
    fields.read(S.META_COVERAGE_SERIES_NAME, S.SERIES, _strings)
    fields.read(
        S.META_COVERAGE_SERIES_POSITION,
        S.META_COVERAGE_SERIES_POSITIONS,
        lambda value: (
            _strings(value)
            and all(
                C.META_COVERAGE_POSITION_PATTERN.fullmatch(item) is not C.NONE
                for item in cast(list[str], value)
            )
        ),
    )


def _ratings(fields: _Fields) -> None:
    if (
        type(fields.data.get(S.RATINGS_AVERAGE)) in (int, float)
        and fields.data[S.RATINGS_AVERAGE] == C.ZERO
        and type(fields.data.get(S.RATINGS_COUNT)) is int
        and fields.data[S.RATINGS_COUNT] == C.ZERO
    ):
        fields.add(S.COMMUNITY_RATING, state=FieldState.UNAVAILABLE)
        mean = C.NONE
    else:
        mean = fields.read(S.RATINGS_AVERAGE, S.COMMUNITY_RATING, _rating)
    count = fields.read(
        S.RATINGS_COUNT,
        S.COMMUNITY_RATINGS_COUNT,
        lambda value: _integer(value, C.ZERO, C.OPEN_LIBRARY_MAX_RATINGS),
    )
    if mean is not C.NONE and (count is C.NONE or count == C.ZERO):
        fields.issues.append(
            Issue(
                code=S.INCONSISTENT_RATING,
                message=S.OPEN_LIBRARY_RATINGS_MESSAGE_OPEN_SUPPLIED_A_COMMUNITY_MEAN_WITHOUT,
            )
        )
        fields.observations = [
            item.model_copy(update={S.VALUE: C.NONE, S.STATE: FieldState.FAILED})
            if item.field == S.COMMUNITY_RATING
            else item
            for item in fields.observations
        ]
    elif mean is C.NONE and type(count) is int and (count > C.ZERO):
        fields.issues.append(
            Issue(
                code=S.INCOMPLETE_RATING,
                message=S.OPEN_LIBRARY_RATINGS_MESSAGE_OPEN_SUPPLIED_A_COMMUNITY_COUNT_BUT,
            )
        )


def _work(raw: JsonValue, observed_at: str) -> tuple[MetadataCandidate | None, tuple[Issue, ...]]:
    if not isinstance(raw, dict):
        return (
            C.NONE,
            (
                Issue(
                    code=S.INVALID_WORK,
                    message=S.OPEN_LIBRARY_WORK_MESSAGE_OPEN_LIBRARY_RETURNED_A_MALFORMED_WORK,
                ),
            ),
        )
    key, title = (raw.get(S.KEY), raw.get(S.TITLE))
    match = (
        re.fullmatch(S.OPEN_LIBRARY_WORK_MATCH_WORKS_OL_D_W, key)
        if isinstance(key, str)
        else C.NONE
    )
    if match is C.NONE or not _text(title) or (not cast(str, title).strip()):
        return (
            C.NONE,
            (
                Issue(
                    code=S.INVALID_WORK,
                    message=S.OPEN_LIBRARY_WORK_MESSAGE_OPEN_LIBRARY_RETURNED_A_MALFORMED_WORK,
                ),
            ),
        )
    identifier = match[C.ONE]
    url = S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=identifier)
    fields = _Fields(raw, url, observed_at)
    fields.add(S.PROVIDER_ID, identifier)
    fields.add(S.TITLE, cast(str, title).strip())
    authors_value = fields.read(S.AUTHOR_NAME, S.AUTHORS, _strings)
    authors = tuple(author.strip() for author in cast(list[str], authors_value or []))
    isbns = _isbns(fields)
    fields.read(S.SUBJECT, S.GENRES, _strings)
    fields.read(
        S.LANGUAGE,
        S.LANGUAGES,
        lambda value: (
            _strings(value)
            and all(
                re.fullmatch(S.GOOGLE_BOOKS_VOLUME_A_Z, item) is not C.NONE
                for item in cast(list[str], value)
            )
        ),
    )
    fields.read(
        S.NUMBER_OF_PAGES_MEDIAN,
        S.MEDIAN_PAGE_COUNT,
        lambda value: _integer(value, C.ONE, C.OPEN_LIBRARY_MAX_PAGES),
    )
    if S.FIRST_PUBLISH_YEAR not in raw:
        fields.add(S.FIRST_PUBLICATION_YEAR, state=FieldState.UNAVAILABLE)
    elif not _integer(raw[S.FIRST_PUBLISH_YEAR], C.ONE, C.OPEN_LIBRARY_WORK):
        fields.issue(S.FIRST_PUBLICATION_YEAR)
        fields.add(S.FIRST_PUBLICATION_YEAR, state=FieldState.FAILED)
    else:
        fields.add(S.FIRST_PUBLICATION_YEAR, raw[S.FIRST_PUBLISH_YEAR])
    fields.add(S.DESCRIPTION, state=FieldState.UNAVAILABLE)
    _series(fields)
    _ratings(fields)
    return (
        MetadataCandidate(
            provider=Source.OPEN_LIBRARY,
            provider_id=identifier,
            work_id=identifier,
            title=cast(str, title).strip(),
            authors=authors,
            isbns=isbns,
            url=url,
            observations=tuple(fields.observations),
        ),
        tuple(fields.issues),
    )


def _http_payload(response: HttpResponse) -> dict[str, JsonValue]:
    status = response.status_code
    if status != C.OPEN_LIBRARY_HTTP_PAYLOAD:
        raise ConnectorError(
            S.OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_REJECTED_THE_PUBLIC_CATALOG_REQUEST,
            state=SyncState.NEEDS_AUTH
            if status == C.OPEN_LIBRARY_HTTP_PAYLOAD_STATE
            else SyncState.BLOCKED
            if status in (C.OPEN_LIBRARY_HTTP_PAYLOAD_STATE_2, C.OPEN_LIBRARY_HTTP_PAYLOAD_STATE_3)
            else SyncState.FAILED,
            code=S.RATE_LIMITED if status == C.OPEN_LIBRARY_HTTP_PAYLOAD_CODE else S.HTTP_ERROR,
            retryable=status == C.OPEN_LIBRARY_HTTP_PAYLOAD_RETRYABLE
            or status >= C.OPEN_LIBRARY_HTTP_PAYLOAD_RETRYABLE_2
            or status == C.OPEN_LIBRARY_HTTP_PAYLOAD_RETRYABLE_3,
        )
    content_type = (
        next(
            (
                value.lower()
                for key, value in response.headers.items()
                if key.lower() == S.CONTENT_TYPE
            ),
            S.EMPTY,
        )
        .split(S.GOOGLE_BOOKS_HTTP_PAYLOAD_CONTENT_TYPE_TEXT, C.ONE)[C.ZERO]
        .strip()
    )
    if (
        content_type
        and content_type != S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON
        and (not content_type.endswith(S.GOOGLE_BOOKS_HTTP_PAYLOAD_JSON))
    ):
        raise ConnectorError(
            S.OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_LIBRARY_RETURNED_NON_JSON_CONTENT_NOT,
            code=S.UNEXPECTED_CONTENT,
        )
    try:
        if len(response.body) > C.OPEN_LIBRARY_HTTP_PAYLOAD_2:
            raise ValueError
        payload: object = json.loads(response.text, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ConnectorError(
            S.OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_LIBRARY_RETURNED_INVALID_JSON, code=S.INVALID_RESPONSE
        ) from C.NONE
    if not isinstance(payload, dict):
        raise ConnectorError(
            S.OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_RETURNED_AN_INVALID_RESULT_SHAPE,
            code=S.INVALID_RESPONSE,
        )
    if S.ERROR in payload or S.ERRORS in payload:
        raise ConnectorError(
            S.OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_LIBRARY_RETURNED_AN_API_ERROR_RATHER, code=S.API_ERROR
        )
    return cast(dict[str, JsonValue], payload)


@C.frozen_dataclass
class _Search:
    candidates: tuple[MetadataCandidate, ...]
    issues: tuple[Issue, ...] = ()
    complete: bool = C.TRUE
    cache_hit: bool = C.FALSE
    candidate_issues: tuple[tuple[str, tuple[Issue, ...]], ...] = ()


def _search_payload(payload: dict[str, JsonValue]) -> _Search:
    total = payload.get(S.NUMFOUND, payload.get(S.NUM_FOUND))
    docs, start, exact = (
        payload.get(S.DOCS),
        payload.get(S.START, C.ZERO),
        payload.get(S.NUMFOUNDEXACT, C.TRUE),
    )
    if (
        not _integer(total, C.ZERO, C.OPEN_LIBRARY_SEARCH_PAYLOAD)
        or not isinstance(docs, list)
        or (not _integer(start, C.ZERO, C.ZERO))
        or (type(exact) is not bool)
        or (cast(int, total) < len(docs))
        or (cast(int, total) > C.ZERO and (not docs))
        or (S.NUMFOUND in payload and S.NUM_FOUND in payload and (total != payload[S.NUM_FOUND]))
    ):
        raise ConnectorError(
            S.OPEN_LIBRARY_HTTP_PAYLOAD_OPEN_RETURNED_AN_INVALID_RESULT_SHAPE,
            code=S.INVALID_RESPONSE,
        )
    candidates: list[MetadataCandidate] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    candidate_issues: list[tuple[str, tuple[Issue, ...]]] = []
    observed_at = utc_now()
    for raw in docs[: C.OPEN_LIBRARY_MAX_RESULTS]:
        candidate, errors = _work(raw, observed_at)
        if candidate is C.NONE:
            issues.extend(errors)
        if candidate is not C.NONE:
            candidate_issues.append((candidate.provider_id, errors))
            if candidate.provider_id in seen:
                candidates = [
                    item for item in candidates if item.provider_id != candidate.provider_id
                ]
                issues.append(
                    Issue(
                        code=S.DUPLICATE_CANDIDATE,
                        message=S.OPEN_LIBRARY_SEARCH_PAYLOAD_MESSAGE_OPEN_REPEATED_A_WORK_IDENTITY_IT,
                    )
                )
            else:
                seen.add(candidate.provider_id)
                candidates.append(candidate)
    return _Search(
        tuple(candidates),
        tuple(issues),
        exact and cast(int, total) <= len(docs[: C.OPEN_LIBRARY_MAX_RESULTS]),
        candidate_issues=tuple(candidate_issues),
    )


def _cached(payload: dict[str, JsonValue]) -> _Search:
    try:
        raw, complete, errors = (
            payload[S.CANDIDATES],
            payload[S.COMPLETE],
            payload.get(S.ISSUES, []),
        )
        if (
            not isinstance(raw, list)
            or len(raw) > C.OPEN_LIBRARY_MAX_RESULTS
            or type(complete) is not bool
            or not isinstance(errors, list)
        ):
            raise ValueError
        issues = tuple(Issue.model_validate(item) for item in errors)
        if any(
            issue.code not in C.META_COVERAGE_OPTIONAL_ISSUES or issue.source_id is not C.NONE
            for issue in issues
        ):
            raise ValueError
        candidates = tuple(MetadataCandidate.model_validate(item) for item in raw)
        for item in candidates:
            if (
                item.provider != Source.OPEN_LIBRARY
                or re.fullmatch(S.OPEN_LIBRARY_CACHED_OL_D_W, item.provider_id) is C.NONE
                or item.work_id != item.provider_id
                or (item.edition_id is not C.NONE)
                or (item.url != S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=item.provider_id))
                or any(
                    field.source_url != item.url
                    or field.scope != S.WORK
                    or field.field in (S.PAGE_COUNT, S.LANGUAGE, S.PUBLICATION_DATE)
                    for field in item.observations
                )
            ):
                raise ValueError
    except (KeyError, ValueError, TypeError, ValidationError):
        raise MetadataCacheError(
            S.OPEN_LIBRARY_CACHED_METADATA_CACHE_CONTAINS_AN_INVALID_OPEN_LIBRARY
        ) from C.NONE
    return _Search(candidates, issues, complete=complete, cache_hit=C.TRUE)


def _matches(book: BookRecord, candidate: MetadataCandidate) -> bool:
    if set(normalized_isbns(book.isbns)) & set(candidate.isbns):
        return C.TRUE
    return work_bibliography_compatible(book, candidate)


def _query(book: BookRecord) -> str | None:
    isbns = normalized_isbns(book.isbns)
    if isbns:
        return (
            S.OPEN_LIBRARY_QUERY_TEXT
            + S.OPEN_LIBRARY_QUERY_OR.join(
                S.GOOGLEBOOKSPROVIDER_LOOKUP_QUERIES_TEMPLATE.format(v0=isbn)
                for isbn in isbns[: C.THREE]
            )
            + S.OPEN_LIBRARY_QUERY_TEXT_2
        )
    title = normalized_text(book.title)
    authors = [normalized_text(author) for author in book.authors if normalized_text(author)]
    if (
        title
        and authors
        and (len(title) <= C.OPEN_LIBRARY_QUERY)
        and (len(authors[C.ZERO]) <= C.OPEN_LIBRARY_QUERY_2)
    ):
        return S.OPEN_LIBRARY_QUERY_TEMPLATE.format(v0=title, v1=authors[C.ZERO])
    return C.NONE


def _failure(book: BookRecord, error: ConnectorError | MetadataCacheError) -> EnrichmentResult:
    if isinstance(error, MetadataCacheError):
        issue = Issue(
            code=S.METADATA_CACHE_ERROR,
            message=S.FAILURE_ISSUE_MESSAGE_THE_METADATA_CACHE_COULD_NOT_BE_USED,
            source_id=book.source_id,
        )
        state = SyncState.FAILED
    else:
        issue = Issue(
            code=error.code
            if error.code in C.OPEN_LIBRARY_SAFE_FAILURE_CODES
            else S.METADATA_REQUEST_FAILED,
            message=S.FAILURE_ISSUE_MESSAGE_OPEN_LIBRARY_FAILED_CHECK_CONNECTIVITY_OR,
            source_id=book.source_id,
            retryable=error.retryable,
        )
        state = error.state if error.state != SyncState.COMPLETE else SyncState.FAILED
    return EnrichmentResult(source_id=book.source_id, state=state, issues=(issue,))


def _result(book: BookRecord, search: _Search) -> EnrichmentResult:
    issues = list(search.issues)
    if any(normalize_isbn(value) is C.NONE for value in book.isbns):
        issues.append(
            Issue(
                code=S.INVALID_INPUT_ISBN,
                message=S.GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_AN_INVALID_ISBN_WAS_EXCLUDED_FROM,
            )
        )
    if len(normalized_isbns(book.isbns)) > C.THREE:
        issues.append(
            Issue(
                code=S.METADATA_DEFERRED,
                message=S.OPEN_LIBRARY_RESULT_MESSAGE_ADDITIONAL_TERMS_WERE_DEFERRED_TO_BOUND,
            )
        )
    if not search.complete:
        issues.append(
            Issue(
                code=S.SEARCH_TRUNCATED,
                message=S.OPEN_LIBRARY_RESULT_MESSAGE_OPEN_RETURNED_A_LIMITED_OR_APPROXIMATE,
            )
        )
    candidates = tuple(candidate for candidate in search.candidates if _matches(book, candidate))
    state = SyncState.PARTIAL if issues else SyncState.COMPLETE
    if not candidates and any(issue.code == S.INVALID_WORK for issue in issues):
        state = SyncState.FAILED
    return EnrichmentResult(
        source_id=book.source_id,
        state=state,
        candidates=candidates,
        issues=tuple(issue.model_copy(update={S.SOURCE_ID: book.source_id}) for issue in issues),
        cache_hit=search.cache_hit,
    )


def _detail_series(fields: _Fields) -> None:
    if S.SERIES not in fields.data:
        fields.add(S.SERIES, state=FieldState.UNAVAILABLE)
        fields.add(S.META_COVERAGE_SERIES_MEMBERSHIPS, state=FieldState.UNAVAILABLE)
        return
    raw = fields.data[S.SERIES]
    if not isinstance(raw, list) or len(raw) > C.OPEN_LIBRARY_STRINGS:
        fields.issue(S.SERIES)
        fields.add(S.SERIES, state=FieldState.FAILED)
        fields.add(S.META_COVERAGE_SERIES_MEMBERSHIPS, state=FieldState.FAILED)
        return
    names: list[JsonValue] = []
    memberships: list[JsonValue] = []
    invalid = C.FALSE
    for item in raw:
        if _text(item) and cast(str, item).strip():
            names.append(item)
            continue
        reference = item.get(S.SERIES) if isinstance(item, dict) else C.NONE
        key = reference.get(S.KEY) if isinstance(reference, dict) else C.NONE
        match = (
            C.META_COVERAGE_SERIES_REFERENCE_PATTERN.fullmatch(key)
            if isinstance(key, str)
            else C.NONE
        )
        if match is C.NONE:
            invalid = C.TRUE
            continue
        membership: dict[str, JsonValue] = {S.META_COVERAGE_SERIES_ID: match[C.ONE]}
        assert isinstance(item, dict)
        if S.META_COVERAGE_MEMBERSHIP_POSITION in item:
            position = item[S.META_COVERAGE_MEMBERSHIP_POSITION]
            if isinstance(position, str) and (
                position == S.EMPTY
                or C.META_COVERAGE_POSITION_PATTERN.fullmatch(position) is not C.NONE
            ):
                membership[S.META_COVERAGE_MEMBERSHIP_POSITION] = position
            else:
                fields.issue(S.META_COVERAGE_SERIES_POSITIONS)
        memberships.append(membership)
    if invalid:
        fields.issue(S.META_COVERAGE_SERIES_MEMBERSHIPS)
    fields.add(
        S.SERIES,
        names or C.NONE,
        FieldState.PRESENT
        if names
        else FieldState.FAILED
        if invalid and not memberships
        else FieldState.EMPTY
        if not raw
        else FieldState.UNAVAILABLE,
    )
    fields.add(
        S.META_COVERAGE_SERIES_MEMBERSHIPS,
        memberships or C.NONE,
        FieldState.PRESENT
        if memberships
        else FieldState.FAILED
        if invalid
        else FieldState.EMPTY
        if not raw
        else FieldState.UNAVAILABLE,
    )


def _detail_fields(
    payload: dict[str, JsonValue], candidate: MetadataCandidate, observed_at: str
) -> _Fields:
    expected_key = S.OPEN_LIBRARY_WORK_MATCH_WORKS_OL_D_W
    key, title = payload.get(S.KEY), payload.get(S.TITLE)
    kind = payload.get(S.TYPE)
    if (
        not isinstance(key, str)
        or re.fullmatch(expected_key, key) is C.NONE
        or key.rsplit(S.SLASH, C.ONE)[-C.ONE] != candidate.provider_id
        or not _text(title)
        or normalized_text(cast(str, title)) != normalized_text(candidate.title)
        or (
            S.TYPE in payload
            and (not isinstance(kind, dict) or kind.get(S.KEY) != S.META_COVERAGE_WORK_TYPE)
        )
    ):
        raise ConnectorError(
            S.OPEN_LIBRARY_WORK_MESSAGE_OPEN_LIBRARY_RETURNED_A_MALFORMED_WORK,
            code=S.INVALID_WORK,
        )
    fields = _Fields(
        payload,
        S.META_COVERAGE_WORK_DETAIL_URL.format(identifier=candidate.provider_id),
        observed_at,
    )
    description = payload.get(S.DESCRIPTION)
    if isinstance(description, dict):
        if description.get(S.TYPE) == S.META_COVERAGE_TEXT_TYPE:
            description = description.get(S.VALUE)
        else:
            description = C.NONE
    if S.DESCRIPTION not in payload:
        fields.add(S.DESCRIPTION, state=FieldState.UNAVAILABLE)
    elif (
        not isinstance(description, str)
        or len(description) > C.META_COVERAGE_DESCRIPTION_LIMIT
        or S.GOOGLE_BOOKS_TEXT_TEXT in description
    ):
        fields.issue(S.DESCRIPTION)
        fields.add(S.DESCRIPTION, state=FieldState.FAILED)
    elif not description.strip():
        fields.add(S.DESCRIPTION, state=FieldState.EMPTY)
    else:
        fields.add(S.DESCRIPTION, description)
    fields.read(S.META_COVERAGE_SUBJECTS, S.GENRES, _strings)
    _detail_series(fields)
    value = payload.get(S.META_COVERAGE_FIRST_PUBLISH_DATE)
    if S.META_COVERAGE_FIRST_PUBLISH_DATE not in payload:
        fields.add(S.META_COVERAGE_FIRST_PUBLICATION_DATE, state=FieldState.UNAVAILABLE)
    else:
        try:
            if not isinstance(value, str):
                raise ValueError
            date = parse_date(value)
        except ValueError:
            fields.issue(S.META_COVERAGE_FIRST_PUBLICATION_DATE)
            fields.add(S.META_COVERAGE_FIRST_PUBLICATION_DATE, state=FieldState.FAILED)
        else:
            if date is C.NONE:
                fields.add(S.META_COVERAGE_FIRST_PUBLICATION_DATE, state=FieldState.EMPTY)
            else:
                fields.add(S.META_COVERAGE_FIRST_PUBLICATION_DATE, date.value)
                fields.add(S.FIRST_PUBLICATION_YEAR, int(date.value.split(S.HYPHEN, C.ONE)[C.ZERO]))
    return fields


def _detail_conflicts(previous: Observation, detail: Observation) -> bool:
    if (
        detail.field in C.META_COVERAGE_SET_FIELDS
        and isinstance(previous.value, list)
        and isinstance(detail.value, list)
        and all(isinstance(item, str) for item in (*previous.value, *detail.value))
    ):
        return C.FALSE
    if detail.field == S.META_COVERAGE_FIRST_PUBLICATION_DATE:
        left, right = previous.value, detail.value
        if isinstance(left, str) and isinstance(right, str):
            try:
                first, second = parse_date(left), parse_date(right)
            except ValueError:
                pass
            else:
                if first is not C.NONE and second is not C.NONE:
                    return not (
                        first.value == second.value
                        or first.value.startswith(second.value + S.HYPHEN)
                        or second.value.startswith(first.value + S.HYPHEN)
                    )
    return previous.value != detail.value


def _merge_details(
    candidate: MetadataCandidate, fields: _Fields
) -> tuple[MetadataCandidate, tuple[Issue, ...]]:
    observations = list(candidate.observations)
    issues = list(fields.issues)
    for detail in fields.observations:
        previous = [
            item
            for item in observations
            if item.field == detail.field and item.state == FieldState.PRESENT
        ]
        if detail.state == FieldState.PRESENT and any(
            _detail_conflicts(item, detail) for item in previous
        ):
            issues.append(
                Issue(
                    code=S.META_COVERAGE_DETAIL_CONFLICT,
                    message=S.META_COVERAGE_CONFLICT_MESSAGE.format(field=detail.field),
                )
            )
        observations = [
            item
            for item in observations
            if item.field != detail.field or item.state == FieldState.PRESENT
        ]
        observations.append(detail)
    return (
        candidate.model_copy(update={S.OBSERVATIONS: tuple(observations)}),
        tuple(issues),
    )


class OpenLibraryProvider:
    def __init__(
        self,
        http: HttpFetcher,
        *,
        cache: MetadataCache | None = C.NONE,
        work_details: bool = C.FALSE,
        detail_request_limit: int = C.ENR_DETAIL_REQUEST_LIMIT,
    ) -> None:
        self._http = http
        self._cache = cache
        self._halted = C.FALSE
        self._work_details = work_details
        self._detail_request_limit = detail_request_limit
        self._detail_requests = C.ZERO
        self._catalog: dict[str, dict[str, MetadataCandidate]] | None = C.NONE

    def _catalog_lookup(self, book: BookRecord) -> _Search | None:
        if self._cache is C.NONE:
            return C.NONE
        if self._catalog is C.NONE:
            self._catalog = {}
            for entry in self._cache.catalog_entries(Source.OPEN_LIBRARY):
                if S.CANDIDATES not in entry:
                    continue
                search = _cached(entry)
                if not search.complete or search.issues:
                    continue
                self._remember_catalog(search)
        matches = {
            candidate.provider_id: candidate
            for key in work_candidate_keys(book)
            for candidate in self._catalog.get(key, {}).values()
            if _matches(book, candidate)
        }
        candidates = tuple(matches[key] for key in sorted(matches))
        if not candidates:
            return C.NONE
        return _Search(candidates, cache_hit=C.TRUE)

    def _remember_catalog(self, search: _Search) -> None:
        if self._catalog is C.NONE or not search.complete or search.issues:
            return
        for candidate in search.candidates:
            for key in work_candidate_keys(candidate):
                candidates = self._catalog.setdefault(key, {})
                previous = candidates.get(candidate.provider_id)
                if previous is C.NONE or max(
                    (item.observed_at or S.EMPTY for item in candidate.observations),
                    default=S.EMPTY,
                ) > max(
                    (item.observed_at or S.EMPTY for item in previous.observations),
                    default=S.EMPTY,
                ):
                    candidates[candidate.provider_id] = candidate

    def _detail_payload(
        self, candidate: MetadataCandidate
    ) -> tuple[dict[str, JsonValue], str, bool]:
        url = S.META_COVERAGE_WORK_DETAIL_URL.format(identifier=candidate.provider_id)
        key = S.META_COVERAGE_WORK_CACHE_KEY.format(identifier=candidate.provider_id)
        cached = (
            self._cache.get(Source.OPEN_LIBRARY, key, allow_expired=C.TRUE)
            if self._cache
            else C.NONE
        )
        if cached is not C.NONE:
            body, stamp, origin = (
                cached.get(S.META_COVERAGE_BODY),
                cached.get(S.META_COVERAGE_CAPTURED_AT),
                cached.get(S.META_COVERAGE_ORIGIN),
            )
            if (
                not isinstance(body, str)
                or not isinstance(stamp, str)
                or origin != url
                or not stamp
            ):
                raise MetadataCacheError(
                    S.OPEN_LIBRARY_CACHED_METADATA_CACHE_CONTAINS_AN_INVALID_OPEN_LIBRARY
                )
            try:
                if datetime.fromisoformat(stamp).tzinfo is C.NONE:
                    raise ValueError
            except ValueError:
                raise MetadataCacheError(
                    S.OPEN_LIBRARY_CACHED_METADATA_CACHE_CONTAINS_AN_INVALID_OPEN_LIBRARY
                ) from C.NONE
            response = HttpResponse(
                url=url,
                status_code=C.OPEN_LIBRARY_HTTP_PAYLOAD,
                headers={S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
                body=body.encode(S.UTF_8),
            )
            return _http_payload(response), stamp, C.TRUE
        if self._halted:
            raise ConnectorError(
                S.META_RUN_HALTED_MESSAGE, code=S.METADATA_DEFERRED, retryable=C.TRUE
            )
        if self._detail_requests >= self._detail_request_limit:
            raise ProviderDeferredError(
                S.ENR_DETAIL_DEFERRED_MESSAGE,
                code=S.ENR_DETAIL_DEFERRED,
                retryable=C.TRUE,
            )
        self._detail_requests += C.ONE
        response = self._http.fetch(
            url, headers={S.ACCEPT: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON}
        )
        if response.url != url:
            raise ConnectorError(
                S.OPEN_LIBRARY_WORK_MESSAGE_OPEN_LIBRARY_RETURNED_A_MALFORMED_WORK,
                code=S.INVALID_WORK,
            )
        payload = _http_payload(response)
        captured = self._http.last_capture if isinstance(self._http, RecordingFetcher) else C.NONE
        stamp = captured.captured_at if captured is not C.NONE else utc_now()
        _detail_fields(payload, candidate, stamp)
        if self._cache:
            self._cache.put(
                Source.OPEN_LIBRARY,
                key,
                {
                    S.META_COVERAGE_BODY: response.body.decode(S.UTF_8),
                    S.META_COVERAGE_CAPTURED_AT: stamp,
                    S.META_COVERAGE_ORIGIN: response.url,
                    S.META_COVERAGE_CAPTURE_ID: captured.id if captured is not C.NONE else C.NONE,
                },
                ttl_seconds=C.OPEN_LIBRARY_POSITIVE_TTL,
            )
        return payload, stamp, C.FALSE

    def _enrich_details(self, book: BookRecord, result: EnrichmentResult) -> EnrichmentResult:
        if result.state not in (SyncState.COMPLETE, SyncState.PARTIAL) or any(
            issue.code not in C.META_COVERAGE_OPTIONAL_ISSUES for issue in result.issues
        ):
            return result
        candidate = select_metadata_candidate(book, result.candidates)
        if candidate is C.NONE:
            return result
        if not missing_fallback_fields(book, (candidate,)):
            return result
        try:
            payload, stamp, cache_hit = self._detail_payload(candidate)
            enriched, issues = _merge_details(candidate, _detail_fields(payload, candidate, stamp))
        except ProviderDeferredError as error:
            if error.code != S.ENR_DETAIL_DEFERRED:
                raise
            return result.model_copy(
                update={
                    S.STATE: SyncState.PARTIAL,
                    S.ISSUES: (
                        *result.issues,
                        Issue(
                            code=error.code,
                            message=str(error),
                            source_id=book.source_id,
                            retryable=C.TRUE,
                        ),
                    ),
                }
            )
        except (ConnectorError, MetadataCacheError) as error:
            if isinstance(error, ConnectorError) and (
                error.state in (SyncState.BLOCKED, SyncState.NEEDS_AUTH)
                or error.code == S.REQUEST_BUDGET_EXHAUSTED
            ):
                self._halted = C.TRUE
            issue = Issue(
                code=S.META_COVERAGE_DETAIL_FAILED,
                message=S.META_COVERAGE_DETAIL_FAILED_MESSAGE.format(
                    code=error.code if isinstance(error, ConnectorError) else S.METADATA_CACHE_ERROR
                ),
                source_id=book.source_id,
                retryable=error.retryable if isinstance(error, ConnectorError) else C.FALSE,
            )
            failed = candidate.model_copy(
                update={
                    S.OBSERVATIONS: tuple(
                        item.model_copy(
                            update={
                                S.STATE: FieldState.FAILED,
                                S.META_COVERAGE_SOURCE_URL: S.META_COVERAGE_WORK_DETAIL_URL.format(
                                    identifier=candidate.provider_id
                                ),
                                S.OBSERVED_AT: utc_now(),
                            }
                        )
                        if item.field in C.META_COVERAGE_DETAIL_FIELDS
                        and item.state not in (FieldState.PRESENT, FieldState.EMPTY)
                        else item
                        for item in candidate.observations
                    )
                }
            )
            return result.model_copy(
                update={
                    S.STATE: SyncState.PARTIAL,
                    S.ISSUES: (*result.issues, issue),
                    S.CANDIDATES: tuple(
                        failed if item == candidate else item for item in result.candidates
                    ),
                }
            )
        return result.model_copy(
            update={
                S.CANDIDATES: tuple(
                    enriched if item == candidate else item for item in result.candidates
                ),
                S.STATE: SyncState.PARTIAL if result.issues or issues else SyncState.COMPLETE,
                S.ISSUES: (
                    *result.issues,
                    *(issue.model_copy(update={S.SOURCE_ID: book.source_id}) for issue in issues),
                ),
                S.META_COVERAGE_CACHE_HIT: result.cache_hit and cache_hit,
            }
        )

    def _lookup_search(
        self,
        books: tuple[BookRecord, ...],
        pending: dict[str, list[int]],
        queries: dict[str, str],
        selected: list[str],
        results: list[EnrichmentResult | None],
    ) -> None:
        try:
            response = self._http.fetch(
                S.OPEN_LIBRARY_ENDPOINT_HTTPS_OPENLIBRARY_ORG_SEARCH_JSON,
                params={
                    S.Q: S.OPEN_LIBRARY_QUERY_OR.join(queries[key] for key in selected),
                    S.FIELDS: S.ENR_OPEN_LIBRARY_SEARCH_FIELDS,
                    S.LIMIT: str(C.OPEN_LIBRARY_MAX_RESULTS),
                },
                headers={S.ACCEPT: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
            )
        except ConnectorError as error:
            if error.code != S.REQUEST_BUDGET_EXHAUSTED:
                raise
            raise ProviderDeferredError(
                S.META_RUN_HALTED_MESSAGE,
                state=SyncState.BLOCKED,
                code=error.code,
                retryable=C.TRUE,
            ) from C.NONE
        search = _search_payload(_http_payload(response))
        unverified = any(
            not any(_matches(books[pending[key][C.ZERO]], candidate) for key in selected)
            for candidate in search.candidates
        )
        if len(selected) > C.ONE and (not search.complete or search.issues or unverified):
            midpoint = len(selected) // C.TWO
            self._lookup_search(books, pending, queries, selected[:midpoint], results)
            self._lookup_search(books, pending, queries, selected[midpoint:], results)
            return
        if unverified:
            search = _Search(
                search.candidates,
                (
                    *search.issues,
                    Issue(
                        code=S.UNVERIFIED_CANDIDATES,
                        message=S.LOOKUP_MANY_SEARCH_MESSAGE_SOME_IDENTITIES_DID_NOT_VERIFY_AGAINST,
                    ),
                ),
                search.complete,
                candidate_issues=search.candidate_issues,
            )
        for key in selected:
            matched = tuple(
                candidate
                for candidate in search.candidates
                if _matches(books[pending[key][C.ZERO]], candidate)
            )
            matched_ids = {candidate.provider_id for candidate in matched}
            subset = _Search(
                matched,
                (
                    *search.issues,
                    *(
                        issue
                        for identifier, errors in search.candidate_issues
                        if identifier in matched_ids
                        for issue in errors
                    ),
                ),
                search.complete,
            )
            if (
                self._cache
                and all(issue.code in C.META_COVERAGE_OPTIONAL_ISSUES for issue in subset.issues)
                and (subset.candidates or subset.complete)
            ):
                self._cache.put(
                    Source.OPEN_LIBRARY,
                    key,
                    {
                        S.CANDIDATES: [
                            cast(JsonValue, item.model_dump(mode=S.JSON))
                            for item in subset.candidates
                        ],
                        S.COMPLETE: subset.complete,
                        S.ISSUES: [
                            cast(JsonValue, issue.model_dump(mode=S.JSON))
                            for issue in subset.issues
                        ],
                    },
                    ttl_seconds=C.OPEN_LIBRARY_POSITIVE_TTL
                    if subset.candidates
                    else C.OPEN_LIBRARY_NEGATIVE_TTL,
                )
                self._remember_catalog(subset)
            for index in pending[key]:
                results[index] = _result(books[index], subset)

    def lookup(self, book: BookRecord) -> EnrichmentResult:
        return self.lookup_many((book,))[C.ZERO]

    def lookup_many(self, books: tuple[BookRecord, ...]) -> tuple[EnrichmentResult, ...]:
        return tuple(self.iter_lookup_many(books))

    def iter_lookup_many(self, books: tuple[BookRecord, ...]) -> Iterator[EnrichmentResult]:
        for book, result in zip(books, self._lookup_many_search(books), strict=C.TRUE):
            yield self._enrich_details(book, result) if self._work_details else result

    def _lookup_many_search(self, books: tuple[BookRecord, ...]) -> tuple[EnrichmentResult, ...]:
        if self._halted:
            raise ProviderDeferredError(
                S.META_RUN_HALTED_MESSAGE,
                state=SyncState.BLOCKED,
                code=S.METADATA_DEFERRED,
                retryable=C.TRUE,
            )
        results: list[EnrichmentResult | None] = [C.NONE] * len(books)
        pending: dict[str, list[int]] = {}
        queries: dict[str, str] = {}
        for index, book in enumerate(books):
            try:
                local = self._catalog_lookup(book)
            except MetadataCacheError as error:
                results[index] = _failure(book, error)
                continue
            if local is not C.NONE:
                results[index] = _result(book, local)
                continue
            query = _query(book)
            if query is C.NONE:
                results[index] = EnrichmentResult(
                    source_id=book.source_id,
                    state=SyncState.PARTIAL,
                    issues=(
                        Issue(
                            code=S.INSUFFICIENT_IDENTITY,
                            message=S.ISSUES_MESSAGE_LOOKUP_NEEDS_A_VALID_ISBN_OR_A,
                            source_id=book.source_id,
                        ),
                    ),
                )
                continue
            key = json.dumps(
                [
                    C.META_COVERAGE_OPEN_LIBRARY_CACHE_VERSION,
                    query,
                    S.ENR_OPEN_LIBRARY_SEARCH_FIELDS,
                    C.OPEN_LIBRARY_MAX_RESULTS,
                ],
                separators=(S.COMMA, S.COLON),
            )
            try:
                cached = (
                    self._cache.get(Source.OPEN_LIBRARY, key, allow_expired=C.TRUE)
                    if self._cache
                    else C.NONE
                )
                if self._cache:
                    for version in (
                        C.META_COVERAGE_OPEN_LIBRARY_CACHE_VERSION,
                        C.METADATA_CAPTURE_VERSION,
                    ):
                        if cached is not C.NONE:
                            break
                        legacy_key = json.dumps(
                            [
                                version,
                                query,
                                S.PROVIDER_ALL_FIELDS,
                                C.OPEN_LIBRARY_MAX_RESULTS,
                            ],
                            separators=(S.COMMA, S.COLON),
                        )
                        cached = self._cache.get(
                            Source.OPEN_LIBRARY, legacy_key, allow_expired=C.TRUE
                        )
                if cached is not C.NONE:
                    results[index] = _result(book, _cached(cached))
                    continue
            except MetadataCacheError as error:
                results[index] = _failure(book, error)
                continue
            queries[key] = query
            pending.setdefault(key, []).append(index)
        selected: list[str] = []
        length = C.ZERO
        for key in pending:
            if (
                len(selected) < C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES
                and length + len(queries[key]) + C.FOUR <= C.OPEN_LIBRARY_MAX_QUERY_LENGTH
            ):
                selected.append(key)
                length += len(queries[key]) + C.FOUR
        for key, indices in pending.items():
            if key not in selected:
                for index in indices:
                    results[index] = EnrichmentResult(
                        source_id=books[index].source_id,
                        state=SyncState.PARTIAL,
                        issues=(
                            Issue(
                                code=S.METADATA_DEFERRED,
                                message=S.ISSUES_MESSAGE_OPEN_LIBRARY_S_TARGETED_BATCH_BUDGET_IS,
                                source_id=books[index].source_id,
                            ),
                        ),
                    )
        if selected:
            try:
                self._lookup_search(books, pending, queries, selected, results)
            except ProviderDeferredError as error:
                self._halted = C.TRUE
                if not any(result is not C.NONE for result in results):
                    raise
                for key in selected:
                    for index in pending[key]:
                        if results[index] is C.NONE:
                            results[index] = EnrichmentResult(
                                source_id=books[index].source_id,
                                state=SyncState.PARTIAL,
                                issues=(
                                    Issue(
                                        code=S.MC_TARGET_DEFERRED,
                                        message=S.META_RUN_HALTED_MESSAGE,
                                        source_id=books[index].source_id,
                                        retryable=C.TRUE,
                                    ),
                                    Issue(
                                        code=error.code,
                                        message=S.META_RUN_HALTED_MESSAGE,
                                        source_id=books[index].source_id,
                                        retryable=C.TRUE,
                                    ),
                                ),
                            )
            except (ConnectorError, MetadataCacheError) as error:
                if isinstance(error, ConnectorError):
                    if error.code == S.REQUEST_BUDGET_EXHAUSTED:
                        self._halted = C.TRUE
                        raise ProviderDeferredError(
                            S.META_RUN_HALTED_MESSAGE,
                            state=SyncState.BLOCKED,
                            code=error.code,
                            retryable=C.TRUE,
                        ) from C.NONE
                    if error.state in (SyncState.NEEDS_AUTH, SyncState.BLOCKED):
                        self._halted = C.TRUE
                for key in selected:
                    for index in pending[key]:
                        if results[index] is C.NONE:
                            results[index] = _failure(books[index], error)
        return tuple(cast(EnrichmentResult, result) for result in results)
