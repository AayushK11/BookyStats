from __future__ import annotations

import json
import math
import re
import threading
from collections.abc import Callable
from typing import NoReturn, cast

from pydantic import JsonValue, ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.cache import MetadataCache, MetadataCacheError
from bookystats.errors import ConnectorError, ProviderDeferredError
from bookystats.identifiers import normalize_isbn, normalized_isbns, normalized_text
from bookystats.interfaces import HttpFetcher, HttpResponse
from bookystats.models import (
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


def _strings(value: JsonValue) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= C.OPEN_LIBRARY_STRINGS
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
    invalid = not _strings(raw)
    if not invalid:
        for value in cast(list[str], raw):
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


def _ratings(fields: _Fields) -> None:
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
    observed_at = utc_now()
    for raw in docs[: C.OPEN_LIBRARY_MAX_RESULTS]:
        candidate, errors = _work(raw, observed_at)
        issues.extend(errors)
        if candidate is not C.NONE:
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
    )


def _cached(payload: dict[str, JsonValue]) -> _Search:
    try:
        raw, complete = (payload[S.CANDIDATES], payload[S.COMPLETE])
        if (
            not isinstance(raw, list)
            or len(raw) > C.OPEN_LIBRARY_MAX_RESULTS
            or type(complete) is not bool
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
    return _Search(candidates, complete=complete, cache_hit=C.TRUE)


def _matches(book: BookRecord, candidate: MetadataCandidate) -> bool:
    if set(normalized_isbns(book.isbns)) & set(candidate.isbns):
        return C.TRUE
    return normalized_text(book.title) == normalized_text(candidate.title) and bool(
        {normalized_text(author) for author in book.authors if normalized_text(author)}
        & {normalized_text(author) for author in candidate.authors if normalized_text(author)}
    )


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


class OpenLibraryProvider:
    def __init__(self, http: HttpFetcher, *, cache: MetadataCache | None = C.NONE) -> None:
        self._http = http
        self._cache = cache
        self._budget_used = C.FALSE
        self._budget_lock = threading.Lock()

    def lookup(self, book: BookRecord) -> EnrichmentResult:
        return self.lookup_many((book,))[C.ZERO]

    def lookup_many(self, books: tuple[BookRecord, ...]) -> tuple[EnrichmentResult, ...]:
        results: list[EnrichmentResult | None] = [C.NONE] * len(books)
        pending: dict[str, list[int]] = {}
        queries: dict[str, str] = {}
        for index, book in enumerate(books):
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
                    C.METADATA_CAPTURE_VERSION,
                    query,
                    S.PROVIDER_ALL_FIELDS,
                    C.OPEN_LIBRARY_MAX_RESULTS,
                ],
                separators=(S.COMMA, S.COLON),
            )
            try:
                cached = self._cache.get(Source.OPEN_LIBRARY, key) if self._cache else C.NONE
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
        with self._budget_lock:
            if self._budget_used:
                selected = []
            elif selected:
                self._budget_used = C.TRUE
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
                response = self._http.fetch(
                    S.OPEN_LIBRARY_ENDPOINT_HTTPS_OPENLIBRARY_ORG_SEARCH_JSON,
                    params={
                        S.Q: S.OPEN_LIBRARY_QUERY_OR.join(queries[key] for key in selected),
                        S.FIELDS: S.PROVIDER_ALL_FIELDS,
                        S.LIMIT: str(C.OPEN_LIBRARY_MAX_RESULTS),
                    },
                    headers={S.ACCEPT: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
                )
                search = _search_payload(_http_payload(response))
                if any(
                    not any(_matches(books[pending[key][C.ZERO]], candidate) for key in selected)
                    for candidate in search.candidates
                ):
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
                    )
                for key in selected:
                    subset = _Search(
                        tuple(
                            candidate
                            for candidate in search.candidates
                            if _matches(books[pending[key][C.ZERO]], candidate)
                        ),
                        search.issues,
                        search.complete,
                    )
                    if (
                        self._cache
                        and (not subset.issues)
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
                            },
                            ttl_seconds=C.OPEN_LIBRARY_POSITIVE_TTL
                            if subset.candidates
                            else C.OPEN_LIBRARY_NEGATIVE_TTL,
                        )
                    for index in pending[key]:
                        results[index] = _result(books[index], subset)
            except ProviderDeferredError:
                raise
            except (ConnectorError, MetadataCacheError) as error:
                for key in selected:
                    for index in pending[key]:
                        results[index] = _failure(books[index], error)
        return tuple(cast(EnrichmentResult, result) for result in results)
