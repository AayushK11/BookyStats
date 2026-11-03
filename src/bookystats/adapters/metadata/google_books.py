from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from typing import NoReturn, cast

from bs4 import BeautifulSoup
from pydantic import JsonValue, ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.dates import parse_date
from bookystats.domain.errors import ConfigurationError, ConnectorError, ProviderDeferredError
from bookystats.domain.identifiers import normalize_isbn, normalized_isbns, normalized_text
from bookystats.domain.interfaces import HttpFetcher, HttpResponse
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


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError(S.GOOGLE_BOOKS_REJECT_CONSTANT_NON_FINITE_JSON_NUMBERS_ARE_NOT_CATALOG)


def _integer(value: JsonValue, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _text(value: JsonValue, maximum: int = C.GOOGLE_BOOKS_TEXT_MAXIMUM) -> bool:
    return (
        isinstance(value, str) and len(value) <= maximum and (S.GOOGLE_BOOKS_TEXT_TEXT not in value)
    )


def _strings(value: JsonValue) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= C.GOOGLE_BOOKS_STRINGS
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
                scope=S.EDITION,
                source_url=self.url,
                observed_at=self.observed_at,
            )
        )

    def issue(self, field: str) -> None:
        self.issues.append(
            Issue(
                code=S.INVALID_METADATA_FIELD,
                message=S.FIELDS_ISSUE_MESSAGE_TEMPLATE.format(v0=field),
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
    if S.INDUSTRYIDENTIFIERS not in fields.data:
        fields.add(S.ISBNS, state=FieldState.UNAVAILABLE)
        return ()
    raw = fields.data[S.INDUSTRYIDENTIFIERS]
    values: set[str] = set()
    invalid = not isinstance(raw, list) or len(raw) > C.GOOGLE_BOOKS_ISBNS_INVALID
    if not invalid:
        for item in cast(list[JsonValue], raw):
            if not isinstance(item, dict):
                invalid = C.TRUE
                continue
            kind, identifier = (item.get(S.TYPE), item.get(S.IDENTIFIER))
            if kind in (S.OTHER, S.ISSN):
                continue
            length = (
                {S.ISBN_10: C.TEN, S.ISBN_13: C.GOOGLE_BOOKS_ISBNS_LENGTH}.get(kind)
                if isinstance(kind, str)
                else C.NONE
            )
            if length is C.NONE or not isinstance(identifier, str):
                invalid = C.TRUE
                continue
            compact = re.sub(S.IDENTIFIERS_NORMALIZE_ISBN_CANDIDATE_S, S.EMPTY, identifier)
            isbn = normalize_isbn(identifier)
            if isbn is C.NONE or len(compact) != length:
                invalid = C.TRUE
            else:
                values.add(isbn)
    if invalid:
        fields.issue(S.ISBNS)
    result = tuple(sorted(values))
    if result:
        fields.add(S.ISBNS, list(result))
    else:
        fields.add(S.ISBNS, state=FieldState.FAILED if invalid else FieldState.EMPTY)
    return result


def _published_date(fields: _Fields) -> None:
    field = S.PUBLICATION_DATE
    if S.PUBLISHEDDATE not in fields.data:
        fields.add(field, state=FieldState.UNAVAILABLE)
        return
    value = fields.data[S.PUBLISHEDDATE]
    try:
        if not isinstance(value, str) or not (
            re.fullmatch(S.DATES_PARSE_DATE_D_D_D, value)
            or re.match(S.DATES_PARSE_DATE_D_D_D_T, value)
        ):
            raise ValueError
        parsed = parse_date(value)
        if parsed is C.NONE:
            raise ValueError
    except ValueError:
        fields.issue(field)
        fields.add(field, state=FieldState.FAILED)
    else:
        fields.add(field, parsed.value)


def _ratings(fields: _Fields) -> None:
    mean = fields.read(S.AVERAGERATING, S.COMMUNITY_RATING, _rating)
    count = fields.read(
        S.RATINGSCOUNT,
        S.COMMUNITY_RATINGS_COUNT,
        lambda value: _integer(value, C.ZERO, C.GOOGLE_BOOKS_MAX_RATINGS),
    )
    if mean is not C.NONE and (count is C.NONE or count == C.ZERO):
        fields.issues.append(
            Issue(
                code=S.INCONSISTENT_RATING,
                message=S.GOOGLE_BOOKS_RATINGS_MESSAGE_GOOGLE_A_COMMUNITY_MEAN_WITHOUT,
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
                message=S.GOOGLE_BOOKS_RATINGS_MESSAGE_GOOGLE_SUPPLIED_A_COMMUNITY_COUNT_BUT,
            )
        )


def _volume(raw: JsonValue, observed_at: str) -> tuple[MetadataCandidate | None, tuple[Issue, ...]]:
    if not isinstance(raw, dict):
        return (
            C.NONE,
            (
                Issue(
                    code=S.INVALID_VOLUME,
                    message=S.GOOGLE_BOOKS_VOLUME_MESSAGE_GOOGLE_BOOKS_RETURNED_A_MALFORMED_VOLUME,
                ),
            ),
        )
    identifier, info = (raw.get(S.ID), raw.get(S.VOLUMEINFO))
    if (
        not isinstance(identifier, str)
        or re.fullmatch(S.GOOGLE_BOOKS_VOLUME_A_ZA_Z0, identifier) is C.NONE
        or (not isinstance(info, dict))
        or (not _text(info.get(S.TITLE)))
        or (not cast(str, info[S.TITLE]).strip())
    ):
        return (
            C.NONE,
            (
                Issue(
                    code=S.INVALID_VOLUME,
                    message=S.GOOGLE_BOOKS_VOLUME_MESSAGE_GOOGLE_BOOKS_RETURNED_A_MALFORMED_VOLUME,
                ),
            ),
        )
    url = S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE.format(v0=identifier)
    fields = _Fields(info, url, observed_at)
    title = cast(str, info[S.TITLE]).strip()
    fields.add(S.PROVIDER_ID, identifier)
    fields.add(S.TITLE, title)
    authors_value = fields.read(S.AUTHORS, S.AUTHORS, _strings)
    authors = tuple(item.strip() for item in cast(list[str], authors_value or []))
    isbns = _isbns(fields)
    fields.read(S.CATEGORIES, S.GENRES, _strings)
    fields.read(
        S.LANGUAGE,
        S.LANGUAGE,
        lambda value: (
            isinstance(value, str)
            and re.fullmatch(S.META_RUN_LANGUAGE_PATTERN, value) is not C.NONE
        ),
    )
    if type(info.get(S.PAGECOUNT)) is int and info[S.PAGECOUNT] == C.ZERO:
        fields.add(S.PAGE_COUNT, state=FieldState.UNAVAILABLE)
    else:
        fields.read(
            S.PAGECOUNT,
            S.PAGE_COUNT,
            lambda value: _integer(value, C.ONE, C.GOOGLE_BOOKS_MAX_PAGES),
        )
    description = fields.read(
        S.DESCRIPTION, S.DESCRIPTION, lambda value: _text(value, C.GOOGLE_BOOKS_VOLUME_DESCRIPTION)
    )
    if isinstance(description, str):
        document = BeautifulSoup(description, S.HTML_PARSER)
        for tag in document([S.SCRIPT, S.STYLE]):
            tag.decompose()
        plain = document.get_text(S.SPACE, strip=C.TRUE)
        fields.observations = [
            item.model_copy(
                update={
                    S.VALUE: plain or C.NONE,
                    S.STATE: FieldState.PRESENT if plain else FieldState.EMPTY,
                }
            )
            if item.field == S.DESCRIPTION
            else item
            for item in fields.observations
        ]
    _published_date(fields)
    _ratings(fields)
    return (
        MetadataCandidate(
            provider=Source.GOOGLE_BOOKS,
            provider_id=identifier,
            edition_id=identifier,
            title=title,
            authors=authors,
            isbns=isbns,
            url=url,
            observations=tuple(fields.observations),
        ),
        tuple(fields.issues),
    )


def _http_payload(response: HttpResponse) -> dict[str, JsonValue]:
    status = response.status_code
    if status != C.GOOGLE_BOOKS_HTTP_PAYLOAD:
        raise ConnectorError(
            S.GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_REJECTED_THE_PUBLIC_CATALOG_REQUEST,
            state=SyncState.NEEDS_AUTH
            if status == C.GOOGLE_BOOKS_HTTP_PAYLOAD_STATE
            else SyncState.BLOCKED
            if status in (C.GOOGLE_BOOKS_HTTP_PAYLOAD_STATE_2, C.GOOGLE_BOOKS_HTTP_PAYLOAD_STATE_3)
            else SyncState.FAILED,
            code=S.RATE_LIMITED if status == C.GOOGLE_BOOKS_HTTP_PAYLOAD_CODE else S.HTTP_ERROR,
            retryable=status == C.GOOGLE_BOOKS_HTTP_PAYLOAD_RETRYABLE
            or status >= C.GOOGLE_BOOKS_HTTP_PAYLOAD_RETRYABLE_2
            or status == C.GOOGLE_BOOKS_HTTP_PAYLOAD_RETRYABLE_3,
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
            S.GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_BOOKS_RETURNED_NON_JSON_CONTENT_NOT,
            code=S.UNEXPECTED_CONTENT,
        )
    try:
        if len(response.body) > C.GOOGLE_BOOKS_HTTP_PAYLOAD_2:
            raise ValueError
        payload: object = json.loads(response.text, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ConnectorError(
            S.GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_BOOKS_RETURNED_INVALID_JSON, code=S.INVALID_RESPONSE
        ) from C.NONE
    if not isinstance(payload, dict):
        raise ConnectorError(
            S.GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_RETURNED_AN_INVALID_RESULT_SHAPE,
            code=S.INVALID_RESPONSE,
        )
    if S.ERROR in payload:
        error = payload[S.ERROR]
        limited = isinstance(error, dict) and (
            error.get(S.CODE) == C.GOOGLE_BOOKS_HTTP_PAYLOAD_LIMITED
            or error.get(S.STATUS) == S.RESOURCE_EXHAUSTED
            or (
                isinstance(error.get(S.ERRORS), list)
                and any(
                    isinstance(item, dict)
                    and item.get(S.REASON)
                    in (
                        S.QUOTAEXCEEDED,
                        S.DAILYLIMITEXCEEDED,
                        S.RATELIMITEXCEEDED,
                        S.USERRATELIMITEXCEEDED,
                    )
                    for item in error[S.ERRORS]
                )
            )
        )
        raise ConnectorError(
            S.GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_BOOKS_RETURNED_AN_API_ERROR_RATHER,
            code=S.RATE_LIMITED if limited else S.API_ERROR,
            state=SyncState.BLOCKED if limited else SyncState.FAILED,
            retryable=limited,
        )
    return cast(dict[str, JsonValue], payload)


@C.frozen_dataclass
class _Search:
    candidates: tuple[MetadataCandidate, ...]
    issues: tuple[Issue, ...] = ()
    complete: bool = C.TRUE
    cache_hit: bool = C.FALSE


def _search_payload(payload: dict[str, JsonValue]) -> _Search:
    total, items = (payload.get(S.TOTALITEMS), payload.get(S.ITEMS, []))
    if (
        not _integer(total, C.ZERO, C.GOOGLE_BOOKS_SEARCH_PAYLOAD)
        or not isinstance(items, list)
        or cast(int, total) < len(items)
        or (cast(int, total) > C.ZERO and (not items))
    ):
        raise ConnectorError(
            S.GOOGLE_BOOKS_HTTP_PAYLOAD_GOOGLE_RETURNED_AN_INVALID_RESULT_SHAPE,
            code=S.INVALID_RESPONSE,
        )
    candidates: list[MetadataCandidate] = []
    issues: list[Issue] = []
    seen: set[str] = set()
    observed_at = utc_now()
    for raw in items[: C.FIVE]:
        candidate, errors = _volume(raw, observed_at)
        issues.extend(errors)
        if candidate is not C.NONE:
            if candidate.provider_id in seen:
                candidates = [
                    item for item in candidates if item.provider_id != candidate.provider_id
                ]
                issues.append(
                    Issue(
                        code=S.DUPLICATE_CANDIDATE,
                        message=S.GOOGLE_BOOKS_SEARCH_PAYLOAD_MESSAGE_REPEATED_A_VOLUME_IDENTITY_IT,
                    )
                )
            else:
                seen.add(candidate.provider_id)
                candidates.append(candidate)
    return _Search(tuple(candidates), tuple(issues), cast(int, total) <= len(items[: C.FIVE]))


def _cached(payload: dict[str, JsonValue]) -> _Search:
    try:
        raw, complete = (payload[S.CANDIDATES], payload[S.COMPLETE])
        if not isinstance(raw, list) or len(raw) > C.FIVE or type(complete) is not bool:
            raise ValueError
        candidates = tuple(MetadataCandidate.model_validate(item) for item in raw)
        for item in candidates:
            if (
                item.provider != Source.GOOGLE_BOOKS
                or re.fullmatch(S.GOOGLE_BOOKS_VOLUME_A_ZA_Z0, item.provider_id) is C.NONE
                or item.edition_id != item.provider_id
                or (item.work_id is not C.NONE)
                or (item.url != S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE.format(v0=item.provider_id))
                or any(
                    field.source_url != item.url or field.scope != S.EDITION
                    for field in item.observations
                )
            ):
                raise ValueError
    except (KeyError, ValueError, TypeError, ValidationError):
        raise MetadataCacheError(
            S.GOOGLE_BOOKS_CACHED_METADATA_CACHE_CONTAINS_AN_INVALID_GOOGLE_BOOKS
        ) from C.NONE
    return _Search(candidates, complete=complete, cache_hit=C.TRUE)


def _title_author_match(book: BookRecord, candidate: MetadataCandidate) -> bool:
    return normalized_text(book.title) == normalized_text(candidate.title) and bool(
        {normalized_text(author) for author in book.authors if normalized_text(author)}
        & {normalized_text(author) for author in candidate.authors if normalized_text(author)}
    )


class GoogleBooksProvider:
    def __init__(
        self,
        http: HttpFetcher,
        *,
        api_key: str | None = C.NONE,
        access_token: str | None = C.NONE,
        cache: MetadataCache | None = C.NONE,
    ) -> None:
        self._http = http
        self._api_key = api_key.strip() if api_key else C.NONE
        self._access_token = access_token.strip() if access_token else C.NONE
        if self._access_token and not C.OAUTH_BEARER_PATTERN.fullmatch(self._access_token):
            raise ConfigurationError(S.OAUTH_FAILURE)
        self._cache = cache
        self._halted = C.FALSE
        self._halt_code = S.METADATA_DEFERRED

    def _search(self, query: str) -> _Search:
        key = json.dumps(
            [
                C.METADATA_CAPTURE_VERSION,
                query,
                S.PROVIDER_FULL_RESPONSE,
                C.FIVE,
            ],
            separators=(S.COMMA, S.COLON),
        )
        if self._cache is not C.NONE:
            cached = self._cache.get(Source.GOOGLE_BOOKS, key, allow_expired=C.TRUE)
            if cached is not C.NONE:
                return _cached(cached)
        params = {
            S.Q: query,
            S.MAXRESULTS: str(C.FIVE),
            S.PRINTTYPE: S.BOOKS,
            S.PRETTYPRINT: S.FALSE_2,
        }
        headers = {S.ACCEPT: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON}
        if self._access_token:
            headers[S.OAUTH_AUTHORIZATION_HEADER] = S.OAUTH_BEARER_HEADER.format(
                token=self._access_token
            )
        elif self._api_key:
            params[S.KEY] = self._api_key
        response = self._http.fetch(
            S.GOOGLE_BOOKS_ENDPOINT_HTTPS_WWW_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES,
            params=params,
            headers=headers,
        )
        result = _search_payload(_http_payload(response))
        if (
            self._cache is not C.NONE
            and (not result.issues)
            and (result.candidates or result.complete)
        ):
            self._cache.put(
                Source.GOOGLE_BOOKS,
                key,
                {
                    S.CANDIDATES: [
                        cast(JsonValue, item.model_dump(mode=S.JSON)) for item in result.candidates
                    ],
                    S.COMPLETE: result.complete,
                },
                ttl_seconds=C.GOOGLE_BOOKS_POSITIVE_TTL
                if result.candidates
                else C.GOOGLE_BOOKS_NEGATIVE_TTL,
            )
        return result

    def lookup(self, book: BookRecord) -> EnrichmentResult:
        if self._halted:
            raise ProviderDeferredError(
                S.META_RUN_HALTED_MESSAGE,
                state=SyncState.BLOCKED,
                code=self._halt_code,
                retryable=C.TRUE,
            )
        if not (self._api_key or self._access_token):
            return EnrichmentResult(
                source_id=book.source_id,
                state=SyncState.NOT_CONFIGURED,
                issues=(
                    Issue(
                        code=S.GOOGLE_BOOKS_NOT_CONFIGURED,
                        message=S.OAUTH_PROVIDER_REQUIRED,
                        source_id=book.source_id,
                    ),
                ),
            )
        isbns = normalized_isbns(book.isbns)
        title = normalized_text(book.title)
        authors = [normalized_text(author) for author in book.authors if normalized_text(author)]
        queries = [
            (S.GOOGLEBOOKSPROVIDER_LOOKUP_QUERIES_TEMPLATE.format(v0=isbn), C.TRUE)
            for isbn in isbns[: C.TWO]
        ]
        if (
            title
            and authors
            and (len(title) <= C.GOOGLE_BOOKS_GOOGLEBOOKSPROVIDER_LOOKUP)
            and (len(authors[C.ZERO]) <= C.GOOGLE_BOOKS_GOOGLEBOOKSPROVIDER_LOOKUP_2)
        ):
            queries.append(
                (
                    S.GOOGLE_BOOKS_GOOGLEBOOKSPROVIDER_LOOKUP_TEMPLATE.format(
                        v0=title, v1=authors[C.ZERO]
                    ),
                    C.FALSE,
                )
            )
        if not queries:
            return EnrichmentResult(
                source_id=book.source_id,
                state=SyncState.PARTIAL,
                issues=(
                    Issue(
                        code=S.INSUFFICIENT_IDENTITY,
                        message=S.LOOKUP_ISSUES_MESSAGE_CATALOG_LOOKUP_NEEDS_A_VALID_ISBN_OR,
                        source_id=book.source_id,
                    ),
                ),
            )
        issues: list[Issue] = []
        if any(normalize_isbn(value) is C.NONE for value in book.isbns):
            issues.append(
                Issue(
                    code=S.INVALID_INPUT_ISBN,
                    message=S.GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_AN_INVALID_ISBN_WAS_EXCLUDED_FROM,
                )
            )
        all_cached = C.TRUE
        candidates: tuple[MetadataCandidate, ...] = ()
        unverified = C.FALSE
        try:
            for query, by_isbn in queries:
                result = self._search(query)
                all_cached = all_cached and result.cache_hit
                issues.extend(result.issues)
                if not result.complete:
                    issues.append(
                        Issue(
                            code=S.SEARCH_TRUNCATED,
                            message=S.GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_GOOGLE_RESULTS_WERE_BOUNDED_MORE,
                        )
                    )
                candidates = tuple(
                    candidate
                    for candidate in result.candidates
                    if (
                        bool(set(isbns) & set(candidate.isbns))
                        if by_isbn
                        else _title_author_match(book, candidate)
                    )
                )
                unverified = unverified or bool(result.candidates and (not candidates))
                if candidates or (result.issues and (not result.candidates)):
                    break
        except MetadataCacheError:
            return EnrichmentResult(
                source_id=book.source_id,
                state=SyncState.FAILED,
                issues=(
                    Issue(
                        code=S.METADATA_CACHE_ERROR,
                        message=S.LOOKUP_ISSUES_MESSAGE_THE_METADATA_CACHE_COULD_NOT_BE_USED,
                        source_id=book.source_id,
                    ),
                ),
            )
        except ProviderDeferredError:
            raise
        except ConnectorError as error:
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
                if error.code == S.RATE_LIMITED:
                    self._halt_code = S.PROVIDER_COOLDOWN
            return EnrichmentResult(
                source_id=book.source_id,
                state=error.state if error.state != SyncState.COMPLETE else SyncState.FAILED,
                issues=(
                    Issue(
                        code=error.code
                        if error.code in C.GOOGLE_BOOKS_SAFE_FAILURE_CODES
                        else S.METADATA_REQUEST_FAILED,
                        message=S.LOOKUP_ISSUES_MESSAGE_GOOGLE_BOOKS_LOOKUP_FAILED_CHECK_THE_NETWORK,
                        source_id=book.source_id,
                        retryable=error.retryable,
                    ),
                ),
            )
        if not candidates and unverified:
            issues.append(
                Issue(
                    code=S.UNVERIFIED_CANDIDATES,
                    message=S.GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_CATALOG_NOT_VERIFY_AGAINST_THE,
                )
            )
        if not candidates and len(isbns) > C.TWO:
            issues.append(
                Issue(
                    code=S.METADATA_DEFERRED,
                    message=S.GOOGLEBOOKSPROVIDER_LOOKUP_MESSAGE_ADDITIONAL_WERE_DEFERRED_TO_KEEP,
                )
            )
        state = SyncState.COMPLETE
        if issues:
            state = SyncState.PARTIAL
            if not candidates and any(issue.code == S.INVALID_VOLUME for issue in issues):
                state = SyncState.FAILED
        return EnrichmentResult(
            source_id=book.source_id,
            state=state,
            candidates=candidates,
            issues=tuple(
                issue.model_copy(update={S.SOURCE_ID: book.source_id}) for issue in issues
            ),
            cache_hit=all_cached,
        )
