from __future__ import annotations

import copy
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.cache import MetadataCache
from bookystats.errors import ConnectorError
from bookystats.interfaces import HttpResponse
from bookystats.models import BookRecord, FieldState, Observation, Source, SyncState
from bookystats.net import HttpClient
from bookystats.providers.google_books import GoogleBooksProvider


class FakeHttp:
    def __init__(self, *responses: HttpResponse | ConnectorError) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], dict[str, str]]] = []

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        self.calls.append((url, dict(params or {}), dict(headers or {})))
        assert self.responses, S.TEST_GOOGLE_BOOKS_FAKEHTTP_FETCH_UNEXPECTED_METADATA_REQUEST
        response = self.responses.pop(C.ZERO)
        if isinstance(response, ConnectorError):
            raise response
        return response


def response(payload: object, status: int = C.TEST_GOOGLE_BOOKS_RESPONSE_STATUS) -> HttpResponse:
    return HttpResponse(
        url=S.TEST_GOOGLE_BOOKS_RESPONSE_URL_HTTPS_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES,
        status_code=status,
        headers={
            S.CONTENT_TYPE_2: S.TEST_GOOGLE_BOOKS_RESPONSE_HEADERS_APPLICATION_JSON_CHARSET_UTF
        },
        body=json.dumps(payload).encode(),
    )


@pytest.fixture
def payload() -> dict[str, Any]:
    path = Path(__file__).parent.joinpath(S.FIXTURES, S.METADATA, S.GOOGLE_BOOKS_JSON)
    return json.loads(path.read_text(encoding=S.UTF_8))


@pytest.fixture
def book() -> BookRecord:
    return BookRecord(
        source=Source.STORYGRAPH,
        source_id=S.ORIGINAL_READER_BOOK_ID,
        title=S.MATILDA,
        authors=(S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
        isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
        url=S.TEST_GOOGLE_BOOKS_BOOK_URL_THESTORYGRAPH_COM_BOOKS_ORIGINAL_READER,
        observations=(
            Observation(
                field=S.REVIEW,
                value=S.PRIVATE_READER_REVIEW,
                state=FieldState.PRESENT,
                scope=S.READER,
                source_url=S.TEST_GOOGLE_BOOKS_BOOK_URL_THESTORYGRAPH_COM_BOOKS_ORIGINAL_READER,
            ),
        ),
    )


def test_isbn_search_extracts_scoped_catalog_without_private_fields(
    payload: dict[str, Any], book: BookRecord
) -> None:
    http = FakeHttp(response(payload))
    result = GoogleBooksProvider(http, api_key=S.SECRET_API_KEY).lookup(book)
    assert result.state == SyncState.COMPLETE
    assert result.source_id == book.source_id
    (candidate,) = result.candidates
    assert candidate.provider_id == candidate.edition_id == S.TESTVOLUME_1
    assert candidate.work_id is C.NONE
    assert candidate.isbns == (
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,
    )
    assert candidate.url == S.TEST_GOOGLE_BOOKS_ISBN_SEARCH_EXTRACTS_HTTPS_BOOKS_GOOGLE_COM_BOOKS
    fields = {item.field: item for item in candidate.observations}
    assert (
        fields[S.PAGE_COUNT].value
        == C.TEST_GOOGLE_BOOKS_ISBN_SEARCH_SCOPED_CATALOG_WITHOUT_PRIVATE_FIELDS
    )
    assert (
        fields[S.PUBLICATION_DATE].value
        == S.TEST_GOOGLE_BOOKS_ISBN_SEARCH_CATALOG_WITHOUT_PRIVATE_FIELDS_TEXT
    )
    assert (
        fields[S.COMMUNITY_RATING].value
        == C.TEST_GOOGLE_BOOKS_ISBN_SEARCH_SCOPED_CATALOG_WITHOUT_PRIVATE_FIELDS_2
    )
    assert (
        fields[S.COMMUNITY_RATINGS_COUNT].value
        == C.TEST_GOOGLE_BOOKS_ISBN_SEARCH_SCOPED_CATALOG_WITHOUT_PRIVATE_FIELDS_3
    )
    assert fields[S.GENRES].value == [
        S.TEST_GOOGLE_BOOKS_ISBN_SEARCH_PRIVATE_FIELDS_JUVENILE_FICTION
    ]
    assert (
        fields[S.DESCRIPTION].value
        == S.TEST_GOOGLE_BOOKS_ISBN_SEARCH_FIELDS_SYNTHETIC_CATALOG_FIXTURE_NO
    )
    assert S.FIRST_PUBLICATION_YEAR not in fields
    assert all(
        item.scope == S.EDITION and item.source_url == candidate.url for item in fields.values()
    )
    url, params, headers = http.calls[C.ZERO]
    assert S.GOODREADS_SAFE_URL_TEXT not in url and S.SECRET_API_KEY not in url
    assert params[S.Q] == S.TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN
    assert params[S.KEY] == S.SECRET_API_KEY
    assert S.FIELDS not in params
    assert S.PRIVATE_READER_REVIEW not in json.dumps(http.calls)
    assert S.ORIGINAL_READER_BOOK_ID not in json.dumps(http.calls)
    assert S.AUTHORIZATION not in headers
    assert S.SECRET_API_KEY not in result.model_dump_json()


@pytest.mark.parametrize(
    S.KEY, [C.NONE, S.EMPTY, S.TEST_GOOGLE_BOOKS_APPLICATION_KEY_IS_EVEN_FOR_PUBLIC_DATA_TEXT]
)
def test_application_key_is_required_even_for_public_data(
    book: BookRecord, key: str | None
) -> None:
    http = FakeHttp()
    result = GoogleBooksProvider(http, api_key=key).lookup(book)
    assert result.state == SyncState.NOT_CONFIGURED
    assert result.issues[C.ZERO].code == S.GOOGLE_BOOKS_NOT_CONFIGURED
    assert not http.calls


def test_isbn_miss_uses_verified_title_author_and_preserves_ambiguity(
    payload: dict[str, Any], book: BookRecord
) -> None:
    other = copy.deepcopy(payload[S.ITEMS][C.ZERO])
    other[S.ID] = S.TESTVOLUME_2
    payload[S.ITEMS].append(other)
    payload[S.TOTALITEMS] = C.TWO
    http = FakeHttp(response({S.TOTALITEMS: C.ZERO}), response(payload))
    result = GoogleBooksProvider(http, api_key=S.KEY).lookup(book)
    assert result.state == SyncState.COMPLETE
    assert len(result.candidates) == C.TWO
    assert [call[C.ONE][S.Q] for call in http.calls] == [
        S.TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN,
        S.TEST_GOOGLE_BOOKS_ISBN_MISS_AMBIGUITY_INTITLE_MATILDA_INAUTHOR_R,
    ]


def test_title_only_or_wrong_author_is_not_a_verified_fallback(
    payload: dict[str, Any], book: BookRecord
) -> None:
    payload[S.ITEMS][C.ZERO][S.VOLUMEINFO][S.AUTHORS] = [
        S.TEST_GOOGLE_BOOKS_TITLE_ONLY_OR_NOT_A_VERIFIED_FALLBACK_SOMEONE_ELSE
    ]
    without_isbn = book.model_copy(update={S.ISBNS: ()})
    http = FakeHttp(response(payload))
    result = GoogleBooksProvider(http, api_key=S.KEY).lookup(without_isbn)
    assert not result.candidates
    assert result.state == SyncState.PARTIAL
    assert any(issue.code == S.UNVERIFIED_CANDIDATES for issue in result.issues)
    no_author = without_isbn.model_copy(update={S.AUTHORS: ()})
    assert (
        GoogleBooksProvider(FakeHttp(), api_key=S.KEY).lookup(no_author).state == SyncState.PARTIAL
    )


def test_escaped_parameters_cannot_change_endpoint_or_add_private_fields(
    payload: dict[str, Any], book: BookRecord
) -> None:
    title = S.TEST_GOOGLE_BOOKS_ESCAPED_PARAMETERS_CANNOT_TITLE_THE_BOOK_KEY_OTHE
    author = S.TEST_GOOGLE_BOOKS_ESCAPED_PARAMETERS_CANNOT_AUTHOR_ANNE_OR_O_NEIL_C
    payload[S.ITEMS][C.ZERO][S.VOLUMEINFO].update({S.TITLE: title, S.AUTHORS: [author]})
    book = book.model_copy(update={S.TITLE: title, S.AUTHORS: (author,), S.ISBNS: ()})
    http = FakeHttp(response(payload))
    result = GoogleBooksProvider(
        http, api_key=S.TEST_ESCAPED_PARAMETERS_CANNOT_CHANGE_RESULT_API_KEY_PRIVATE_KEY
    ).lookup(book)
    assert len(result.candidates) == C.ONE
    assert (
        http.calls[C.ZERO][C.ONE][S.Q]
        == S.TEST_GOOGLE_BOOKS_ESCAPED_PARAMETERS_CANNOT_INTITLE_THE_BOOK_KEY_OT
    )
    assert (
        http.calls[C.ZERO][C.ZERO]
        == S.GOOGLE_BOOKS_ENDPOINT_HTTPS_WWW_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES
    )
    assert (
        http.calls[C.ZERO][C.ONE][S.KEY]
        == S.TEST_ESCAPED_PARAMETERS_CANNOT_CHANGE_RESULT_API_KEY_PRIVATE_KEY
    )


@pytest.mark.parametrize(
    S.DATE,
    [
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_6,
        S.TEST_GOOGLE_BOOKS_ISBN_SEARCH_CATALOG_WITHOUT_PRIVATE_FIELDS_TEXT,
        S.TEST_GOOGLE_BOOKS_PUBLICATION_DATE_PRESERVES_SOURCE_PRECISION_TEXT,
    ],
)
def test_publication_date_preserves_source_precision(
    payload: dict[str, Any], book: BookRecord, date: str
) -> None:
    payload[S.ITEMS][C.ZERO][S.VOLUMEINFO][S.PUBLISHEDDATE] = date
    result = GoogleBooksProvider(FakeHttp(response(payload)), api_key=S.KEY).lookup(book)
    observed = next(
        item for item in result.candidates[C.ZERO].observations if item.field == S.PUBLICATION_DATE
    )
    assert observed.value == date
    assert observed.scope == S.EDITION


@pytest.mark.parametrize(
    (S.KEY, S.VALUE, S.FIELD),
    [
        (S.PAGECOUNT, C.ZERO, S.PAGE_COUNT),
        (
            S.PAGECOUNT,
            C.TEN**C.TEST_GOOGLE_BOOKS_INVALID_OPTIONAL_ARE_ISSUES_NOT_FABRICATED_METRICS,
            S.PAGE_COUNT,
        ),
        (S.PAGECOUNT, C.TRUE, S.PAGE_COUNT),
        (S.RATINGSCOUNT, -C.ONE, S.COMMUNITY_RATINGS_COUNT),
        (
            S.RATINGSCOUNT,
            C.TEN**C.TEST_GOOGLE_BOOKS_INVALID_OPTIONAL_ARE_ISSUES_NOT_FABRICATED_METRICS,
            S.COMMUNITY_RATINGS_COUNT,
        ),
        (S.AVERAGERATING, C.SEVEN, S.COMMUNITY_RATING),
        (S.AVERAGERATING, C.TRUE, S.COMMUNITY_RATING),
        (
            S.PUBLISHEDDATE,
            S.TEST_GOOGLE_BOOKS_INVALID_OPTIONAL_NOT_FABRICATED_METRICS_TEXT,
            S.PUBLICATION_DATE,
        ),
        (
            S.PUBLISHEDDATE,
            S.TEST_GOOGLE_BOOKS_INVALID_OPTIONAL_NOT_FABRICATED_METRICS_TEXT_2,
            S.PUBLICATION_DATE,
        ),
        (
            S.PUBLISHEDDATE,
            S.TEST_GOOGLE_BOOKS_INVALID_OPTIONAL_NOT_FABRICATED_METRICS_T12_Z,
            S.PUBLICATION_DATE,
        ),
        (S.LANGUAGE, [S.EN], S.LANGUAGE),
        (S.CATEGORIES, S.FICTION, S.GENRES),
    ],
)
def test_invalid_optional_values_are_issues_not_fabricated_metrics(
    payload: dict[str, Any], book: BookRecord, key: str, value: object, field: str
) -> None:
    payload[S.ITEMS][C.ZERO][S.VOLUMEINFO][key] = value
    result = GoogleBooksProvider(FakeHttp(response(payload)), api_key=S.KEY).lookup(book)
    assert result.state == SyncState.PARTIAL
    item = next(item for item in result.candidates[C.ZERO].observations if item.field == field)
    assert item.value is C.NONE and item.state == FieldState.FAILED
    assert any(issue.code == S.INVALID_METADATA_FIELD for issue in result.issues)


def test_missing_metrics_stay_unknown_and_explicit_zero_count_is_distinct(
    payload: dict[str, Any], book: BookRecord
) -> None:
    info = payload[S.ITEMS][C.ZERO][S.VOLUMEINFO]
    info.pop(S.AVERAGERATING)
    info.pop(S.RATINGSCOUNT)
    result = GoogleBooksProvider(FakeHttp(response(payload)), api_key=S.KEY).lookup(book)
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert result.state == SyncState.COMPLETE
    assert fields[S.COMMUNITY_RATING].state == FieldState.UNAVAILABLE
    assert fields[S.COMMUNITY_RATINGS_COUNT].value is C.NONE
    info[S.RATINGSCOUNT] = C.ZERO
    result = GoogleBooksProvider(FakeHttp(response(payload)), api_key=S.KEY).lookup(book)
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert result.state == SyncState.COMPLETE
    assert fields[S.COMMUNITY_RATING].value is C.NONE
    assert fields[S.COMMUNITY_RATINGS_COUNT].value == C.ZERO
    info[S.AVERAGERATING] = C.TEST_GOOGLE_BOOKS_MISSING_METRICS_EXPLICIT_ZERO_COUNT_IS_DISTINCT
    result = GoogleBooksProvider(FakeHttp(response(payload)), api_key=S.KEY).lookup(book)
    assert result.state == SyncState.PARTIAL
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert fields[S.COMMUNITY_RATING].state == FieldState.FAILED
    assert any(issue.code == S.INCONSISTENT_RATING for issue in result.issues)


@pytest.mark.parametrize(
    S.INVALID,
    [
        [],
        {},
        {S.TOTALITEMS: S.TEST_GOOGLE_BOOKS_WRONG_ENVELOPES_OF_BECOMING_EMPTY_RESULTS_TEXT},
        {S.TOTALITEMS: C.TRUE},
        {S.TOTALITEMS: C.ONE},
        {S.TOTALITEMS: C.ZERO, S.ITEMS: {}},
        {S.TOTALITEMS: C.ZERO, S.ITEMS: [{S.ID: S.X_2}]},
    ],
)
def test_wrong_envelopes_fail_instead_of_becoming_empty_results(
    book: BookRecord, invalid: object
) -> None:
    result = GoogleBooksProvider(FakeHttp(response(invalid)), api_key=S.KEY).lookup(book)
    assert result.state == SyncState.FAILED
    assert not result.candidates
    assert result.issues[C.ZERO].code == S.INVALID_RESPONSE


@pytest.mark.parametrize(
    S.INVALID,
    [
        float(S.NAN),
        float(S.INF),
        float(S.TEST_CACHE_INVALID_JSON_DOES_NOT_REPLACE_A_GOOD_ENTRY_INF),
    ],
)
def test_nonfinite_json_is_an_explicit_failure(
    payload: dict[str, Any], book: BookRecord, invalid: float
) -> None:
    payload[S.ITEMS][C.ZERO][S.VOLUMEINFO][S.AVERAGERATING] = invalid
    result = GoogleBooksProvider(FakeHttp(response(payload)), api_key=S.KEY).lookup(book)
    assert result.state == SyncState.FAILED
    assert result.issues[C.ZERO].code == S.INVALID_RESPONSE


@pytest.mark.parametrize(
    S.FAILURE,
    [
        response(
            {
                S.ERROR: {
                    S.CODE: C.TEST_GOOGLE_BOOKS_TRANSIENT_FAILURES_AND_NEVER_NEGATIVE_CACHED,
                    S.MESSAGE: S.SECRET_API_KEY,
                }
            },
            C.TEST_GOOGLE_BOOKS_TRANSIENT_FAILURES_AND_NEVER_NEGATIVE_CACHED,
        ),
        response(
            {
                S.ERROR: {
                    S.CODE: C.TEST_GOOGLE_BOOKS_TRANSIENT_FAILURES_AND_NEVER_NEGATIVE_CACHED_2,
                    S.ERRORS: [{S.REASON: S.QUOTAEXCEEDED}],
                }
            }
        ),
        response(
            {S.ERROR: {S.MESSAGE: S.SECRET_API_KEY}},
            C.TEST_GOOGLE_BOOKS_TRANSIENT_FAILURES_AND_NEVER_NEGATIVE_CACHED_3,
        ),
        ConnectorError(
            S.TEST_GOOGLE_BOOKS_TRANSIENT_FAILURES_FAILED_HTTPS_WWW_GOOGLEAPIS_C,
            code=S.SECRET_API_KEY,
            retryable=C.TRUE,
        ),
    ],
)
def test_transient_failures_are_redacted_and_never_negative_cached(
    payload: dict[str, Any],
    book: BookRecord,
    tmp_path: Path,
    failure: HttpResponse | ConnectorError,
) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    http = FakeHttp(failure, response(payload))
    provider = GoogleBooksProvider(http, api_key=S.SECRET_API_KEY, cache=cache)
    failed = provider.lookup(book)
    assert failed.state in (SyncState.FAILED, SyncState.BLOCKED)
    assert failed.issues[C.ZERO].retryable
    assert S.SECRET_API_KEY not in failed.model_dump_json()
    recovered = provider.lookup(book)
    assert recovered.state == SyncState.COMPLETE and (not recovered.cache_hit)
    assert len(http.calls) == C.TWO
    cache.close()


def test_html_login_and_unsafe_volume_identity_are_not_catalog_success(book: BookRecord) -> None:
    html = HttpResponse(
        url=S.TEST_HTML_LOGIN_AND_UNSAFE_VOLUME_HTTPS_ACCOUNTS_GOOGLE_COM_LOGIN_KE,
        status_code=C.TEST_HTML_LOGIN_AND_UNSAFE_VOLUME_CATALOG_SUCCESS_HTML_STATUS_CODE,
        headers={S.CONTENT_TYPE: S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_HANDLER_DO_GET_TEXT_HTML},
        body=S.TEST_HTML_LOGIN_AND_UNSAFE_VOLUME_CATALOG_SUCCESS_HTML_BODY_BYTES,
    )
    result = GoogleBooksProvider(FakeHttp(html), api_key=S.SECRET).lookup(book)
    assert result.state == SyncState.FAILED
    assert S.SECRET not in result.model_dump_json()
    unsafe = {
        S.TOTALITEMS: C.ONE,
        S.ITEMS: [
            {
                S.ID: S.TEST_GOOGLE_BOOKS_HTML_LOGIN_AND_SUCCESS_UNSAFE_HTTPS_EVIL_EXAMPLE,
                S.VOLUMEINFO: {S.TITLE: S.MATILDA},
            }
        ],
    }
    result = GoogleBooksProvider(FakeHttp(response(unsafe)), api_key=S.SECRET).lookup(book)
    assert result.state == SyncState.FAILED
    assert result.issues[C.ZERO].code == S.INVALID_VOLUME
    assert S.SECRET not in result.model_dump_json()


def test_fresh_cache_survives_key_rotation_without_caching_sensitive_payload(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path
) -> None:
    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    first = GoogleBooksProvider(
        FakeHttp(response(payload)), api_key=S.SECRET_KEY_ONE, cache=cache
    ).lookup(book)
    http = FakeHttp()
    second = GoogleBooksProvider(http, api_key=S.SECRET_KEY_TWO, cache=cache).lookup(book)
    assert second.cache_hit and (not http.calls)
    assert first.candidates == second.candidates
    cache.close()
    stored = path.read_bytes()
    assert (
        S.TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_BYTES not in stored
        and S.TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_BYTES_2 not in stored
    )
    assert S.TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_BYTES_3 not in stored
    with sqlite3.connect(path) as database:
        (key,) = database.execute(
            S.TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_SELECT_CACHE
        ).fetchone()
    assert len(key) == C.TEST_GOOGLE_BOOKS_FRESH_CACHE_WITHOUT_CACHING_SENSITIVE_PAYLOAD


def test_stale_cache_is_refetched_and_normal_empty_results_are_cached(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [C.TEST_GOOGLE_BOOKS_STALE_CACHE_IS_NORMAL_EMPTY_RESULTS_ARE_CACHED_NOW]
    monkeypatch.setattr(S.BOOKYSTATS_CACHE_UTC_TIMESTAMP, lambda: now[C.ZERO])
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    http = FakeHttp(response(payload), response(payload))
    provider = GoogleBooksProvider(http, api_key=S.KEY, cache=cache)
    assert not provider.lookup(book).cache_hit
    now[C.ZERO] += (
        C.EIGHT
        * C.TEST_GOOGLE_BOOKS_STALE_CACHE_IS_AND_NORMAL_EMPTY_RESULTS_ARE_CACHED
        * C.TEST_GOOGLE_BOOKS_STALE_CACHE_IS_AND_NORMAL_EMPTY_RESULTS_ARE_CACHED_2
        * C.TEST_GOOGLE_BOOKS_STALE_CACHE_IS_AND_NORMAL_EMPTY_RESULTS_ARE_CACHED_2
    )
    assert not provider.lookup(book).cache_hit
    assert len(http.calls) == C.TWO
    missing = book.model_copy(
        update={
            S.ISBNS: (),
            S.TITLE: S.TEST_STALE_CACHE_IS_REFETCHED_CACHED_MISSING_UPDATE_UNLISTED_TITLE,
        }
    )
    empty_http = FakeHttp(response({S.TOTALITEMS: C.ZERO}))
    empty_provider = GoogleBooksProvider(empty_http, api_key=S.KEY, cache=cache)
    assert empty_provider.lookup(missing).state == SyncState.COMPLETE
    second = empty_provider.lookup(missing)
    assert second.cache_hit and (not second.candidates)
    assert len(empty_http.calls) == C.ONE
    cache.close()


def test_cache_damage_is_an_issue_not_an_invisible_network_fallback(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path
) -> None:
    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    provider = GoogleBooksProvider(FakeHttp(response(payload)), api_key=S.KEY, cache=cache)
    provider.lookup(book)
    with sqlite3.connect(path) as database:
        database.execute(S.TEST_GOOGLE_BOOKS_CACHE_DAMAGE_IS_UPDATE_METADATA_CACHE_SET_PA)
    result = provider.lookup(book)
    assert result.state == SyncState.FAILED
    assert result.issues[C.ZERO].code == S.METADATA_CACHE_ERROR
    cache.close()


def test_repeated_volume_id_cannot_become_one_silently_confirmable_candidate(
    payload: dict[str, Any], book: BookRecord
) -> None:
    duplicate = copy.deepcopy(payload[S.ITEMS][C.ZERO])
    duplicate[S.VOLUMEINFO][S.TITLE] = (
        S.TEST_GOOGLE_BOOKS_REPEATED_CONFIRMABLE_CANDIDATE_CONTRADICTORY
    )
    payload[S.ITEMS].append(duplicate)
    payload[S.TOTALITEMS] = C.TWO
    result = GoogleBooksProvider(FakeHttp(response(payload)), api_key=S.KEY).lookup(book)
    assert result.state == SyncState.PARTIAL
    assert not result.candidates
    assert any(issue.code == S.DUPLICATE_CANDIDATE for issue in result.issues)


def test_real_transport_encodes_the_application_key_as_one_parameter(
    payload: dict[str, Any], book: BookRecord
) -> None:
    secret = S.TEST_GOOGLE_BOOKS_REAL_TRANSPORT_SECRET_PRIVATE_KEY_ANOTHER

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get_list(S.KEY) == [secret]
        assert (
            request.url.params[S.Q]
            == S.TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN
        )
        assert request.url.host == S.WWW_GOOGLEAPIS_COM
        return httpx.Response(
            C.TEST_GOOGLE_BOOKS_REAL_TRANSPORT_ENCODES_KEY_AS_ONE_PARAMETER_HANDLE, json=payload
        )

    with (
        httpx.Client(transport=httpx.MockTransport(handle)) as session,
        HttpClient(
            allowed_hosts=(S.WWW_GOOGLEAPIS_COM,), client=session, min_interval=C.ZERO
        ) as transport,
    ):
        result = GoogleBooksProvider(transport, api_key=secret).lookup(book)
    assert result.state == SyncState.COMPLETE
    assert S.PRIVATE_2 not in result.model_dump_json()
