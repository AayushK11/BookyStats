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
from bookystats.adapters.http import HttpClient
from bookystats.adapters.metadata.open_library import OpenLibraryProvider, _Fields, _merge_details
from bookystats.domain.errors import ConnectorError, ProviderDeferredError
from bookystats.domain.interfaces import HttpResponse
from bookystats.domain.models import BookRecord, FieldState, Source, SyncState
from bookystats.persistence.cache import MetadataCache
from bookystats.persistence.raw import RawStore, RecordingFetcher
from tests.support.paths import fixture_path


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


def response(payload: object, status: int = C.TEST_OPEN_LIBRARY_RESPONSE_STATUS) -> HttpResponse:
    return HttpResponse(
        url=S.OPEN_LIBRARY_ENDPOINT_HTTPS_OPENLIBRARY_ORG_SEARCH_JSON,
        status_code=status,
        headers={S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
        body=json.dumps(payload).encode(),
    )


@pytest.fixture
def payload() -> dict[str, Any]:
    path = fixture_path(S.METADATA, S.OPEN_LIBRARY_JSON)
    return json.loads(path.read_text(encoding=S.UTF_8))


@pytest.fixture
def book() -> BookRecord:
    return BookRecord(
        source=Source.GOODREADS,
        source_id=S.ORIGINAL_WATCHLIST_BOOK,
        title=S.MATILDA,
        authors=(S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
        isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
        url=S.TEST_OPEN_LIBRARY_BOOK_URL_HTTPS_WWW_GOODREADS_COM_BOOK_SHOW,
        shelves=(S.PRIVATE_SHELF,),
    )


def test_rejected_batch_stops_subsequent_requests(book: BookRecord) -> None:
    http = FakeHttp(response({}, status=C.OPEN_LIBRARY_HTTP_PAYLOAD_STATE_2))
    provider = OpenLibraryProvider(http)
    assert provider.lookup(book).state == SyncState.BLOCKED
    with pytest.raises(ProviderDeferredError):
        provider.lookup(book)
    assert len(http.calls) == C.ONE


def test_zero_mean_without_ratings_is_unavailable_not_failed(
    payload: dict[str, Any], book: BookRecord
) -> None:
    payload[S.DOCS][C.ZERO].update({S.RATINGS_AVERAGE: C.ZERO, S.RATINGS_COUNT: C.ZERO})
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.COMPLETE
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert fields[S.COMMUNITY_RATING].state == FieldState.UNAVAILABLE
    assert fields[S.COMMUNITY_RATING].value is C.NONE
    assert fields[S.COMMUNITY_RATINGS_COUNT].value == C.ZERO


def test_work_isbn_aggregates_can_exceed_ordinary_text_list_bound(
    payload: dict[str, Any], book: BookRecord
) -> None:
    work = payload[S.DOCS][C.ZERO]
    original = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    work[S.ISBN] *= C.OPEN_LIBRARY_STRINGS
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.COMPLETE
    assert result.candidates[C.ZERO].isbns == original.candidates[C.ZERO].isbns


def test_large_isbn_aggregate_keeps_valid_isbns_but_does_not_hide_corrupt_entries(
    payload: dict[str, Any], book: BookRecord
) -> None:
    work = payload[S.DOCS][C.ZERO]
    work[S.ISBN] *= C.OPEN_LIBRARY_STRINGS
    work[S.ISBN].append(S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_4)
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.PARTIAL
    assert result.candidates[C.ZERO].isbns
    assert any(issue.code == S.INVALID_METADATA_FIELD for issue in result.issues)


def test_invalid_optional_isbn_items_keep_valid_identity_and_scoped_catalog_fields(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path
) -> None:
    work = payload[S.DOCS][C.ZERO]
    original_isbns = list(work[S.ISBN])
    work[S.ISBN].extend(
        (C.NONE, C.TRUE, C.ONE, S.EMPTY, S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_4)
    )
    work[S.META_COVERAGE_SERIES_NAME] = [S.META_COVERAGE_TEST_SERIES]
    work[S.META_COVERAGE_SERIES_POSITION] = [S.META_COVERAGE_TEST_POSITION]
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        first = OpenLibraryProvider(FakeHttp(response(payload)), cache=cache).lookup(book)
        http = FakeHttp()
        repeated = OpenLibraryProvider(http, cache=cache).lookup(book)
        assert first.state == repeated.state == SyncState.PARTIAL
        assert repeated.cache_hit and not http.calls
        assert first.candidates == repeated.candidates
        assert first.issues == repeated.issues
        candidate = first.candidates[C.ZERO]
        assert candidate.isbns
        assert candidate.isbns == tuple(
            sorted(
                {
                    S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,
                    S.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_TEXT,
                }
            )
        )
        fields = {item.field: item for item in candidate.observations}
        assert fields[S.ISBNS].state == FieldState.PRESENT
        assert fields[S.GENRES].value == work[S.SUBJECT]
        assert fields[S.FIRST_PUBLICATION_YEAR].value == work[S.FIRST_PUBLISH_YEAR]
        assert fields[S.SERIES].value == [S.META_COVERAGE_TEST_SERIES]
        assert fields[S.META_COVERAGE_SERIES_POSITIONS].value == [S.META_COVERAGE_TEST_POSITION]
        assert all(
            field.scope == S.WORK and field.source_url == candidate.url
            for field in candidate.observations
        )
        assert fields[S.DESCRIPTION].state == FieldState.UNAVAILABLE
        assert len(work[S.ISBN]) > len(original_isbns)
    finally:
        cache.close()


def test_all_invalid_isbns_remain_failed_without_losing_catalog_subjects(
    payload: dict[str, Any], book: BookRecord
) -> None:
    work = payload[S.DOCS][C.ZERO]
    work[S.ISBN] = [
        C.NONE,
        S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_4,
    ]
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    candidate = result.candidates[C.ZERO]
    fields = {item.field: item for item in candidate.observations}
    assert result.state == SyncState.PARTIAL
    assert not candidate.isbns
    assert fields[S.ISBNS].state == FieldState.FAILED
    assert fields[S.GENRES].value == work[S.SUBJECT]
    assert fields[S.SERIES].state == FieldState.UNAVAILABLE


def test_invalid_series_position_does_not_invent_an_order(
    payload: dict[str, Any], book: BookRecord
) -> None:
    work = payload[S.DOCS][C.ZERO]
    work[S.META_COVERAGE_SERIES_NAME] = [S.META_COVERAGE_TEST_SERIES]
    work[S.META_COVERAGE_SERIES_POSITION] = [S.META_COVERAGE_TEST_BAD_POSITION]
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert result.state == SyncState.PARTIAL
    assert fields[S.SERIES].value == [S.META_COVERAGE_TEST_SERIES]
    assert fields[S.META_COVERAGE_SERIES_POSITIONS].state == FieldState.FAILED
    assert fields[S.META_COVERAGE_SERIES_POSITIONS].value is C.NONE


def test_work_isbn_aggregate_still_has_a_finite_safety_bound(
    payload: dict[str, Any], book: BookRecord
) -> None:
    payload[S.DOCS][C.ZERO][S.ISBN] *= C.META_RUN_OPEN_LIBRARY_MAX_ISBNS
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.PARTIAL
    assert not result.candidates[C.ZERO].isbns
    assert any(issue.code == S.INVALID_METADATA_FIELD for issue in result.issues)


def test_edition_identifier_in_work_namespace_is_not_promoted_to_work(
    payload: dict[str, Any], book: BookRecord
) -> None:
    payload[S.DOCS][C.ZERO][S.KEY] = S.META_RUN_TEST_MALFORMED_WORK_KEY
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.FAILED
    assert not result.candidates
    assert any(issue.code == S.INVALID_WORK for issue in result.issues)


def test_optional_failure_only_affects_matching_book_in_batch(
    payload: dict[str, Any], book: BookRecord
) -> None:
    other = copy.deepcopy(payload[S.DOCS][C.ZERO])
    other.update(
        {
            S.KEY: S.OL123W,
            S.TITLE: S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_SHARE_HITS_TO_KILL_A_MOCKINGBIRD,
            S.AUTHOR_NAME: [S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_INDIVIDUAL_CACHE_HITS_HARPER_LEE],
            S.ISBN: [S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_2],
            S.RATINGS_COUNT: -C.ONE,
        }
    )
    payload[S.DOCS].append(other)
    payload[S.NUMFOUND] = C.TWO
    second_book = book.model_copy(
        update={
            S.SOURCE_ID: S.SECOND_ORIGINAL_ID,
            S.TITLE: other[S.TITLE],
            S.AUTHORS: tuple(other[S.AUTHOR_NAME]),
            S.ISBNS: tuple(other[S.ISBN]),
        }
    )
    first, second = OpenLibraryProvider(FakeHttp(response(payload))).lookup_many(
        (book, second_book)
    )
    assert first.state == SyncState.COMPLETE
    assert second.state == SyncState.PARTIAL
    assert second.issues


def test_work_search_never_promotes_aggregate_or_partial_edition_data_to_exact_edition(
    payload: dict[str, Any], book: BookRecord
) -> None:
    http = FakeHttp(response(payload))
    result = OpenLibraryProvider(http).lookup(book)
    assert result.state == SyncState.COMPLETE
    assert result.source_id == S.ORIGINAL_WATCHLIST_BOOK
    (candidate,) = result.candidates
    assert candidate.provider_id == candidate.work_id == S.OL45883W
    assert candidate.edition_id is C.NONE
    assert candidate.url == S.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_HTTPS_OPE
    assert candidate.isbns == (
        S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,
        S.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_TEXT,
    )
    fields = {item.field: item for item in candidate.observations}
    assert (
        fields[S.FIRST_PUBLICATION_YEAR].value
        == C.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_EDITION_DATA_TO_EXACT_EDITION
    )
    assert (
        fields[S.MEDIAN_PAGE_COUNT].value
        == C.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_EDITION_DATA_TO_EXACT_EDITION_2
    )
    assert fields[S.LANGUAGES].value == [S.ENG, S.FRE]
    assert (
        fields[S.COMMUNITY_RATING].value
        == C.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_EDITION_DATA_TO_EXACT_EDITION_3
    )
    assert (
        fields[S.COMMUNITY_RATINGS_COUNT].value
        == C.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_EDITION_DATA_TO_EXACT_EDITION_4
    )
    assert S.PAGE_COUNT not in fields and S.LANGUAGE not in fields
    assert S.PUBLICATION_DATE not in fields
    assert all(
        item.scope == S.WORK and item.source_url == candidate.url for item in fields.values()
    )
    url, params, headers = http.calls[C.ZERO]
    assert url == S.OPEN_LIBRARY_ENDPOINT_HTTPS_OPENLIBRARY_ORG_SEARCH_JSON
    assert params[S.Q] == S.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_ISBN
    assert (
        int(params[S.LIMIT])
        <= C.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_EDITION_DATA_TO_EXACT_EDITION_5
    )
    assert params[S.FIELDS] == S.PROVIDER_ALL_FIELDS
    assert headers == {S.ACCEPT: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON}
    assert S.PRIVATE_SHELF not in json.dumps(http.calls)
    assert S.ORIGINAL_WATCHLIST_BOOK not in json.dumps(http.calls)


def test_distinct_books_share_one_batch_and_have_individual_cache_hits(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path
) -> None:
    other = copy.deepcopy(payload[S.DOCS][C.ZERO])
    other.update(
        {
            S.KEY: S.OL123W,
            S.TITLE: S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_SHARE_HITS_TO_KILL_A_MOCKINGBIRD,
            S.AUTHOR_NAME: [S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_INDIVIDUAL_CACHE_HITS_HARPER_LEE],
            S.ISBN: [S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_2],
        }
    )
    payload[S.DOCS].append(other)
    payload[S.NUMFOUND] = C.TWO
    second_book = book.model_copy(
        update={
            S.SOURCE_ID: S.SECOND_ORIGINAL_ID,
            S.TITLE: S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_SHARE_HITS_TO_KILL_A_MOCKINGBIRD,
            S.AUTHORS: (S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_INDIVIDUAL_CACHE_HITS_HARPER_LEE,),
            S.ISBNS: (S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_2,),
        }
    )
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    http = FakeHttp(response(payload))
    provider = OpenLibraryProvider(http, cache=cache)
    first, second = provider.lookup_many((book, second_book))
    assert first.state == second.state == SyncState.COMPLETE
    assert first.source_id == book.source_id and second.source_id == second_book.source_id
    assert first.candidates[C.ZERO].work_id == S.OL45883W
    assert second.candidates[C.ZERO].work_id == S.OL123W
    assert (
        http.calls[C.ZERO][C.ONE][S.Q]
        == S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_SHARE_CACHE_HITS_ISBN_OR_ISBN
    )
    assert provider.lookup(second_book).cache_hit
    assert len(http.calls) == C.ONE
    cache.close()


def test_huge_watchlist_is_one_bounded_batch_and_explicitly_defers_the_remainder(
    book: BookRecord,
) -> None:
    books = tuple(
        book.model_copy(
            update={
                S.SOURCE_ID: str(index),
                S.TITLE: S.TEST_HUGE_WATCHLIST_IS_ONE_THE_REMAINDER_BOOKS_UPDATE_TEMPLATE.format(
                    v0=index
                ),
                S.ISBNS: (),
            }
        )
        for index in range(C.TEST_OPEN_LIBRARY_HUGE_WATCHLIST_DEFERS_THE_REMAINDER_BOOKS)
    )
    http = FakeHttp(response({S.NUMFOUND: C.ZERO, S.DOCS: [], S.START: C.ZERO}))
    provider = OpenLibraryProvider(http)
    results = provider.lookup_many(books)
    assert (
        len(results) == C.TEST_OPEN_LIBRARY_HUGE_WATCHLIST_AND_EXPLICITLY_DEFERS_THE_REMAINDER
        and len(http.calls) == C.ONE
    )
    assert (
        sum(result.state == SyncState.COMPLETE for result in results)
        == C.TEST_OPEN_LIBRARY_HUGE_WATCHLIST_AND_EXPLICITLY_DEFERS_THE_REMAINDER_2
    )
    assert all(
        result.state == SyncState.PARTIAL and result.issues[C.ZERO].code == S.METADATA_DEFERRED
        for result in results[
            C.TEST_OPEN_LIBRARY_HUGE_WATCHLIST_AND_EXPLICITLY_DEFERS_THE_REMAINDER_2 :
        ]
    )
    assert (
        http.calls[C.ZERO][C.ONE][S.Q].count(
            S.TEST_OPEN_LIBRARY_HUGE_WATCHLIST_DEFERS_THE_REMAINDER_TITLE
        )
        == C.TEST_OPEN_LIBRARY_HUGE_WATCHLIST_AND_EXPLICITLY_DEFERS_THE_REMAINDER_2
    )
    http.responses.append(response({S.NUMFOUND: C.ZERO, S.DOCS: [], S.START: C.ZERO}))
    repeated = provider.lookup(
        books[C.TEST_OPEN_LIBRARY_HUGE_WATCHLIST_DEFERS_THE_REMAINDER_REPEATED]
    )
    assert repeated.state == SyncState.COMPLETE
    assert not repeated.candidates
    assert len(http.calls) == C.TWO


def test_repeated_identity_is_not_repeated_network_work(
    payload: dict[str, Any], book: BookRecord
) -> None:
    books = tuple(
        book.model_copy(update={S.SOURCE_ID: str(index)})
        for index in range(C.TEST_OPEN_LIBRARY_REPEATED_IDENTITY_NOT_REPEATED_NETWORK_WORK_BOOKS)
    )
    http = FakeHttp(response(payload))
    results = OpenLibraryProvider(http).lookup_many(books)
    assert len(http.calls) == C.ONE
    assert (
        http.calls[C.ZERO][C.ONE][S.Q].count(
            S.TEST_OPEN_LIBRARY_REPEATED_IDENTITY_NOT_REPEATED_NETWORK_WORK_ISBN
        )
        == C.ONE
    )
    assert all(result.state == SyncState.COMPLETE for result in results)
    assert [result.source_id for result in results] == [
        str(index)
        for index in range(C.TEST_OPEN_LIBRARY_REPEATED_IDENTITY_IS_NOT_REPEATED_NETWORK_WORK)
    ]


def test_partial_results_never_cache_unreturned_books_as_not_found(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path
) -> None:
    payload[S.NUMFOUND] = C.TEST_OPEN_LIBRARY_PARTIAL_RESULTS_UNRETURNED_BOOKS_AS_NOT_FOUND
    other = book.model_copy(update={S.SOURCE_ID: S.OTHER_3, S.TITLE: S.UNKNOWN, S.ISBNS: ()})
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    http = FakeHttp(response(payload), response(payload), response(payload))
    first, missing = OpenLibraryProvider(http, cache=cache).lookup_many((book, other))
    assert len(http.calls) == C.THREE
    assert first.state == missing.state == SyncState.PARTIAL
    assert first.candidates and (not missing.candidates)
    assert any(issue.code == S.SEARCH_TRUNCATED for issue in missing.issues)
    cached = OpenLibraryProvider(FakeHttp(), cache=cache).lookup(book)
    assert cached.cache_hit and cached.state == SyncState.PARTIAL
    http = FakeHttp(response({S.NUMFOUND: C.ZERO, S.DOCS: []}))
    retried = OpenLibraryProvider(http, cache=cache).lookup(other)
    assert retried.state == SyncState.COMPLETE and (not retried.cache_hit)
    assert len(http.calls) == C.ONE
    cache.close()


def _refinement_identity(
    payload: dict[str, Any], book: BookRecord
) -> tuple[BookRecord, dict[str, Any]]:
    other = book.model_copy(
        update={
            S.SOURCE_ID: S.SECOND_ORIGINAL_ID,
            S.TITLE: S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_SHARE_HITS_TO_KILL_A_MOCKINGBIRD,
            S.AUTHORS: (S.TEST_OPEN_LIBRARY_DISTINCT_BOOKS_INDIVIDUAL_CACHE_HITS_HARPER_LEE,),
            S.ISBNS: (S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_2,),
        }
    )
    data = copy.deepcopy(payload)
    data[S.DOCS][C.ZERO].update(
        {
            S.KEY: S.OL123W,
            S.TITLE: other.title,
            S.AUTHOR_NAME: list(other.authors),
            S.ISBN: list(other.isbns),
        }
    )
    return other, data


@pytest.mark.parametrize(S.COMPLETE, C.MC_REFINEMENT_COMPLETE_CASES)
def test_incomplete_or_unverified_batch_is_refined_without_weakening_identity(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path, complete: bool
) -> None:
    other, other_payload = _refinement_identity(payload, book)
    initial = copy.deepcopy(payload)
    if complete:
        initial[S.DOCS][C.ZERO].update({S.TITLE: S.UNKNOWN, S.AUTHOR_NAME: [S.UNKNOWN], S.ISBN: []})
    else:
        initial[S.NUMFOUND] = C.OPEN_LIBRARY_MAX_RESULTS + C.ONE
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        http = FakeHttp(response(initial), response(payload), response(other_payload))
        provider = OpenLibraryProvider(http, cache=cache)
        first, second = provider.lookup_many((book, other))
        assert first.state == second.state == SyncState.COMPLETE
        assert first.candidates[C.ZERO].provider_id == S.OL45883W
        assert second.candidates[C.ZERO].provider_id == S.OL123W
        assert len(http.calls) == C.THREE
        assert S.OPEN_LIBRARY_QUERY_OR in http.calls[C.ZERO][C.ONE][S.Q]
        assert S.OPEN_LIBRARY_QUERY_OR not in http.calls[C.ONE][C.ONE][S.Q]
        assert S.OPEN_LIBRARY_QUERY_OR not in http.calls[C.TWO][C.ONE][S.Q]
        assert provider.lookup(other).cache_hit
        assert len(http.calls) == C.THREE
    finally:
        cache.close()


@pytest.mark.parametrize(S.CODE, C.MC_DEFERRED_CAUSES)
def test_refinement_deferral_retains_successful_prefix_and_cached_progress(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path, code: str
) -> None:
    other, _ = _refinement_identity(payload, book)
    initial = copy.deepcopy(payload)
    initial[S.NUMFOUND] = C.OPEN_LIBRARY_MAX_RESULTS + C.ONE
    error = (
        ConnectorError(S.META_RUN_HALTED_MESSAGE, code=code, retryable=C.TRUE)
        if code == S.REQUEST_BUDGET_EXHAUSTED
        else ProviderDeferredError(S.PROVIDER_COOLDOWN_MESSAGE, code=code, retryable=C.TRUE)
    )
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        http = FakeHttp(response(initial), response(payload), error)
        provider = OpenLibraryProvider(http, cache=cache)
        first, deferred = provider.lookup_many((book, other))
        assert first.state == SyncState.COMPLETE and first.candidates
        assert not deferred.candidates
        assert {issue.code for issue in deferred.issues} == {S.MC_TARGET_DEFERRED, code}
        assert len(http.calls) == C.THREE
        with pytest.raises(ProviderDeferredError):
            provider.lookup(other)
        cached = OpenLibraryProvider(FakeHttp(), cache=cache).lookup(book)
        assert cached.cache_hit and cached.state == SyncState.COMPLETE
    finally:
        cache.close()


def test_approximate_empty_response_is_partial_and_not_negative_cached(
    book: BookRecord, tmp_path: Path
) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    approximate = response({S.NUMFOUND: C.ZERO, S.DOCS: [], S.NUMFOUNDEXACT: C.FALSE})
    first = OpenLibraryProvider(FakeHttp(approximate), cache=cache).lookup(book)
    assert first.state == SyncState.PARTIAL
    http = FakeHttp(response({S.NUMFOUND: C.ZERO, S.DOCS: []}))
    second = OpenLibraryProvider(http, cache=cache).lookup(book)
    assert not second.cache_hit and len(http.calls) == C.ONE
    cache.close()


def test_ambiguous_work_candidates_remain_candidates(
    payload: dict[str, Any], book: BookRecord
) -> None:
    other = copy.deepcopy(payload[S.DOCS][C.ZERO])
    other[S.KEY] = S.TEST_OPEN_LIBRARY_AMBIGUOUS_WORK_REMAIN_CANDIDATES_WORKS_OL123W
    payload[S.DOCS].append(other)
    payload[S.NUMFOUND] = C.TWO
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.COMPLETE and len(result.candidates) == C.TWO
    assert all(candidate.edition_id is C.NONE for candidate in result.candidates)


def test_title_author_search_is_verified_and_query_syntax_is_escaped(
    payload: dict[str, Any], book: BookRecord
) -> None:
    book = book.model_copy(
        update={
            S.TITLE: S.TEST_TITLE_AUTHOR_SEARCH_IS_VERIFIED_ESCAPED_BOOK_UPDATE_MATILDA_OR,
            S.AUTHORS: (S.TEST_TITLE_AUTHOR_SEARCH_IS_VERIFIED_BOOK_UPDATE_ROALD_DAHL_CO,),
            S.ISBNS: (),
        }
    )
    payload[S.DOCS][C.ZERO].update({S.TITLE: book.title, S.AUTHOR_NAME: list(book.authors)})
    http = FakeHttp(response(payload))
    result = OpenLibraryProvider(http).lookup(book)
    assert result.candidates
    assert (
        http.calls[C.ZERO][C.ONE][S.Q]
        == S.TEST_OPEN_LIBRARY_TITLE_AUTHOR_SEARCH_TITLE_MATILDA_OR_AND_AUTHOR
    )
    payload[S.DOCS][C.ZERO][S.AUTHOR_NAME] = [
        S.TEST_OPEN_LIBRARY_TITLE_AUTHOR_SEARCH_IS_ESCAPED_NOT_THE_AUTHOR
    ]
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert not result.candidates and result.state == SyncState.PARTIAL
    assert any(issue.code == S.UNVERIFIED_CANDIDATES for issue in result.issues)
    no_author = book.model_copy(update={S.AUTHORS: ()})
    assert (
        OpenLibraryProvider(FakeHttp()).lookup(no_author).issues[C.ZERO].code
        == S.INSUFFICIENT_IDENTITY
    )


@pytest.mark.parametrize(
    (S.KEY, S.VALUE, S.FIELD),
    [
        (S.NUMBER_OF_PAGES_MEDIAN, C.ZERO, S.MEDIAN_PAGE_COUNT),
        (
            S.NUMBER_OF_PAGES_MEDIAN,
            C.TEN**C.TEST_OPEN_LIBRARY_INVALID_WORK_VALUES_ARE_PARTIAL_AND_EXPLICIT,
            S.MEDIAN_PAGE_COUNT,
        ),
        (S.RATINGS_COUNT, -C.ONE, S.COMMUNITY_RATINGS_COUNT),
        (
            S.RATINGS_COUNT,
            C.TEN**C.TEST_OPEN_LIBRARY_INVALID_WORK_VALUES_ARE_PARTIAL_AND_EXPLICIT,
            S.COMMUNITY_RATINGS_COUNT,
        ),
        (
            S.RATINGS_AVERAGE,
            C.TEN**C.TEST_OPEN_LIBRARY_INVALID_WORK_VALUES_ARE_PARTIAL_AND_EXPLICIT_2,
            S.COMMUNITY_RATING,
        ),
        (S.RATINGS_AVERAGE, C.TRUE, S.COMMUNITY_RATING),
        (S.FIRST_PUBLISH_YEAR, C.ZERO, S.FIRST_PUBLICATION_YEAR),
        (
            S.FIRST_PUBLISH_YEAR,
            S.TEST_GOOGLE_BOOKS_ISBN_SEARCH_CATALOG_WITHOUT_PRIVATE_FIELDS_TEXT,
            S.FIRST_PUBLICATION_YEAR,
        ),
        (
            S.FIRST_PUBLISH_YEAR,
            C.TEST_OPEN_LIBRARY_INVALID_WORK_VALUES_ARE_PARTIAL_AND_EXPLICIT_3,
            S.FIRST_PUBLICATION_YEAR,
        ),
        (S.LANGUAGE, S.ENG, S.LANGUAGES),
    ],
)
def test_invalid_work_values_are_partial_and_explicit(
    payload: dict[str, Any], book: BookRecord, key: str, value: object, field: str
) -> None:
    payload[S.DOCS][C.ZERO][key] = value
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.PARTIAL
    observed = next(item for item in result.candidates[C.ZERO].observations if item.field == field)
    assert observed.value is C.NONE and observed.state == S.FAILED
    assert any(issue.code == S.INVALID_METADATA_FIELD for issue in result.issues)


@pytest.mark.parametrize(
    S.INVALID,
    [
        [],
        {},
        {
            S.NUMFOUND: S.TEST_GOOGLE_BOOKS_WRONG_ENVELOPES_OF_BECOMING_EMPTY_RESULTS_TEXT,
            S.DOCS: [],
        },
        {S.NUMFOUND: C.ZERO, S.DOCS: {}},
        {S.NUMFOUND: C.ONE, S.DOCS: []},
        {S.NUMFOUND: C.ZERO, S.DOCS: [], S.NUMFOUNDEXACT: S.TRUE_2},
        {S.NUMFOUND: C.ZERO, S.NUM_FOUND: C.ONE, S.DOCS: []},
        {
            S.NUMFOUND: C.ZERO,
            S.DOCS: [],
            S.START: C.TEST_OPEN_LIBRARY_MALFORMED_ENVELOPES_FAIL_NOT_MISSING,
        },
        {S.ERROR: S.TEST_OPEN_LIBRARY_MALFORMED_ENVELOPES_PROVIDER_ERROR_PRIVATE_TOKEN},
    ],
)
def test_malformed_envelopes_fail_not_missing(book: BookRecord, invalid: object) -> None:
    result = OpenLibraryProvider(FakeHttp(response(invalid))).lookup(book)
    assert result.state == SyncState.FAILED
    assert result.issues and (not result.candidates)
    assert S.PRIVATE_TOKEN not in result.model_dump_json()


@pytest.mark.parametrize(
    S.VALUE,
    [
        float(S.NAN),
        float(S.INF),
        float(S.TEST_CACHE_INVALID_JSON_DOES_NOT_REPLACE_A_GOOD_ENTRY_INF),
    ],
)
def test_nonfinite_json_is_not_accepted(
    payload: dict[str, Any], book: BookRecord, value: float
) -> None:
    payload[S.DOCS][C.ZERO][S.RATINGS_AVERAGE] = value
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.FAILED
    assert result.issues[C.ZERO].code == S.INVALID_RESPONSE


@pytest.mark.parametrize(
    S.FAILURE,
    [
        response(
            {S.ERROR: S.PRIVATE_TOKEN},
            C.TEST_OPEN_LIBRARY_TRANSIENT_FAILURE_CACHED_FOR_A_FUTURE_INVOCATION,
        ),
        response(
            {S.ERROR: S.PRIVATE_TOKEN},
            C.TEST_OPEN_LIBRARY_TRANSIENT_FAILURE_CACHED_FOR_A_FUTURE_INVOCATION_2,
        ),
        ConnectorError(
            S.TEST_OPEN_LIBRARY_TRANSIENT_FUTURE_INVOCATION_HTTPS_OPENLIBRARY,
            code=S.PRIVATE_TOKEN,
            retryable=C.TRUE,
        ),
    ],
)
def test_transient_failure_is_redacted_and_not_cached_for_a_future_invocation(
    payload: dict[str, Any],
    book: BookRecord,
    tmp_path: Path,
    failure: HttpResponse | ConnectorError,
) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    failed = OpenLibraryProvider(FakeHttp(failure), cache=cache).lookup(book)
    assert failed.state in (SyncState.FAILED, SyncState.BLOCKED)
    assert failed.issues[C.ZERO].retryable
    assert S.PRIVATE_TOKEN not in failed.model_dump_json()
    http = FakeHttp(response(payload))
    recovered = OpenLibraryProvider(http, cache=cache).lookup(book)
    assert recovered.state == SyncState.COMPLETE and (not recovered.cache_hit)
    assert len(http.calls) == C.ONE
    cache.close()


def test_html_and_unsafe_work_links_are_explicit_failures(
    payload: dict[str, Any], book: BookRecord
) -> None:
    html = HttpResponse(
        url=S.TEST_HTML_AND_UNSAFE_WORK_LINKS_HTTPS_OPENLIBRARY_ORG_ACCOUNT_LOGIN,
        status_code=C.TEST_HTML_AND_UNSAFE_WORK_LINKS_EXPLICIT_FAILURES_HTML_STATUS_CODE,
        headers={S.CONTENT_TYPE: S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_HANDLER_DO_GET_TEXT_HTML},
        body=S.TEST_HTML_AND_UNSAFE_WORK_LINKS_EXPLICIT_FAILURES_HTML_BODY_BYTES,
    )
    result = OpenLibraryProvider(FakeHttp(html)).lookup(book)
    assert result.state == SyncState.FAILED
    assert S.PRIVATE_TOKEN not in result.model_dump_json()
    payload[S.DOCS][C.ZERO][S.KEY] = (
        S.TEST_OPEN_LIBRARY_HTML_AND_UNSAFE_WORKS_OL123W_TOKEN_PRIVATE_TOKEN
    )
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.FAILED and (not result.candidates)
    assert result.issues[C.ZERO].code == S.INVALID_WORK
    assert S.PRIVATE_TOKEN not in result.model_dump_json()


def test_unknown_metrics_are_not_zero_and_inconsistent_rating_is_flagged(
    payload: dict[str, Any], book: BookRecord
) -> None:
    work = payload[S.DOCS][C.ZERO]
    work.pop(S.RATINGS_AVERAGE)
    work.pop(S.RATINGS_COUNT)
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert result.state == SyncState.COMPLETE
    assert fields[S.COMMUNITY_RATING].value is C.NONE
    assert fields[S.COMMUNITY_RATINGS_COUNT].state == S.UNAVAILABLE
    work.update(
        {
            S.RATINGS_AVERAGE: C.TEST_INCONSISTENT_RATING,
            S.RATINGS_COUNT: C.ZERO,
        }
    )
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert result.state == SyncState.PARTIAL
    assert fields[S.COMMUNITY_RATING].state == S.FAILED
    assert any(issue.code == S.INCONSISTENT_RATING for issue in result.issues)


def test_cache_is_catalog_only_stale_entries_refetch_and_corruption_is_explicit(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [C.TEST_OPEN_LIBRARY_CACHE_IS_CATALOG_AND_CORRUPTION_IS_EXPLICIT_NOW]
    monkeypatch.setattr(S.BOOKYSTATS_CACHE_UTC_TIMESTAMP, lambda: now[C.ZERO])
    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    first = OpenLibraryProvider(FakeHttp(response(payload)), cache=cache).lookup(book)
    cached = OpenLibraryProvider(FakeHttp(), cache=cache).lookup(book)
    assert cached.cache_hit and first.candidates == cached.candidates
    now[C.ZERO] += (
        C.EIGHT
        * C.TEST_OPEN_LIBRARY_CACHE_IS_REFETCH_AND_CORRUPTION_IS_EXPLICIT
        * C.TEST_OPEN_LIBRARY_CACHE_IS_REFETCH_AND_CORRUPTION_IS_EXPLICIT_2
        * C.TEST_OPEN_LIBRARY_CACHE_IS_REFETCH_AND_CORRUPTION_IS_EXPLICIT_2
    )
    http = FakeHttp(response(payload))
    fresh = OpenLibraryProvider(http, cache=cache).lookup(book)
    assert not fresh.cache_hit and len(http.calls) == C.ONE
    assert (
        S.TEST_GOOGLE_BOOKS_FRESH_CACHE_CACHING_SENSITIVE_PAYLOAD_BYTES_2 not in path.read_bytes()
    )
    assert (
        S.TEST_OPEN_LIBRARY_CACHE_IS_CATALOG_AND_CORRUPTION_IS_EXPLICIT_BYTES
        not in path.read_bytes()
    )
    with sqlite3.connect(path) as database:
        database.execute(S.TEST_GOOGLE_BOOKS_CACHE_DAMAGE_IS_UPDATE_METADATA_CACHE_SET_PA)
    broken = OpenLibraryProvider(FakeHttp(), cache=cache).lookup(book)
    assert broken.state == SyncState.FAILED
    assert broken.issues[C.ZERO].code == S.METADATA_CACHE_ERROR
    cache.close()


def test_legacy_count_shape_and_normal_no_results_can_be_cached(
    book: BookRecord, tmp_path: Path
) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    http = FakeHttp(response({S.NUM_FOUND: C.ZERO, S.START: C.ZERO, S.DOCS: []}))
    first = OpenLibraryProvider(http, cache=cache).lookup(book)
    second = OpenLibraryProvider(FakeHttp(), cache=cache).lookup(book)
    assert first.state == second.state == SyncState.COMPLETE
    assert not first.candidates and (not second.candidates) and second.cache_hit
    cache.close()


def test_legacy_parsed_cache_does_not_force_http_for_a_parser_upgrade(
    payload: dict[str, Any], book: BookRecord, tmp_path: Path
) -> None:
    first = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        cache.put(
            Source.OPEN_LIBRARY,
            json.dumps(
                [
                    C.METADATA_CAPTURE_VERSION,
                    S.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_ISBN,
                    S.PROVIDER_ALL_FIELDS,
                    C.OPEN_LIBRARY_MAX_RESULTS,
                ],
                separators=(S.COMMA, S.COLON),
            ),
            {
                S.CANDIDATES: [candidate.model_dump(mode=S.JSON) for candidate in first.candidates],
                S.COMPLETE: C.TRUE,
            },
            ttl_seconds=C.OPEN_LIBRARY_POSITIVE_TTL,
        )
        http = FakeHttp()
        cached = OpenLibraryProvider(http, cache=cache).lookup(book)
        assert cached.cache_hit and not http.calls
        assert cached.state == SyncState.COMPLETE
        assert cached.candidates == first.candidates
    finally:
        cache.close()


def test_repeated_work_id_does_not_hide_contradictory_candidates(
    payload: dict[str, Any], book: BookRecord
) -> None:
    duplicate = copy.deepcopy(payload[S.DOCS][C.ZERO])
    duplicate[S.TITLE] = S.TEST_GOOGLE_BOOKS_REPEATED_CONFIRMABLE_CANDIDATE_CONTRADICTORY
    payload[S.DOCS].append(duplicate)
    payload[S.NUMFOUND] = C.TWO
    result = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book)
    assert result.state == SyncState.PARTIAL
    assert not result.candidates
    assert any(issue.code == S.DUPLICATE_CANDIDATE for issue in result.issues)


def test_injected_transport_keeps_application_contact_identification(
    payload: dict[str, Any], book: BookRecord
) -> None:
    agent = S.TEST_OPEN_LIBRARY_INJECTED_TRANSPORT_AGENT_BOOKYSTATS_OPERATOR_E

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers[S.USER_AGENT] == agent
        assert (
            request.url.params[S.Q]
            == S.TEST_OPEN_LIBRARY_WORK_SEARCH_NEVER_DATA_TO_EXACT_EDITION_ISBN
        )
        assert request.url.host == S.OPENLIBRARY_ORG
        return httpx.Response(
            C.TEST_OPEN_LIBRARY_INJECTED_APPLICATION_CONTACT_IDENTIFICATION_HANDLE, json=payload
        )

    with (
        httpx.Client(
            transport=httpx.MockTransport(handle), headers={S.USER_AGENT: agent}
        ) as session,
        HttpClient(
            allowed_hosts=(S.OPENLIBRARY_ORG,), client=session, min_interval=C.ZERO
        ) as transport,
    ):
        result = OpenLibraryProvider(transport).lookup(book)
    assert result.state == SyncState.COMPLETE


@pytest.fixture
def work_payload() -> dict[str, Any]:
    return json.loads(
        fixture_path(S.METADATA, S.META_COVERAGE_WORK_FIXTURE).read_text(encoding=S.UTF_8)
    )


def work_response(payload: object, status: int = C.OPEN_LIBRARY_HTTP_PAYLOAD) -> HttpResponse:
    return HttpResponse(
        url=S.META_COVERAGE_WORK_DETAIL_URL.format(identifier=S.OL45883W),
        status_code=status,
        headers={S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
        body=json.dumps(payload).encode(S.UTF_8),
    )


def test_confirmed_work_details_add_description_and_precise_work_publication(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord, tmp_path: Path
) -> None:
    raw = RawStore(tmp_path / S.TEST_RAW_FILENAME)
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    http = FakeHttp(response(payload), work_response(work_payload))
    recording = RecordingFetcher(http, raw, source=Source.OPEN_LIBRARY)
    try:
        result = OpenLibraryProvider(recording, cache=cache, work_details=C.TRUE).lookup(book)
        assert result.state == SyncState.COMPLETE
        candidate = result.candidates[C.ZERO]
        fields = {
            item.field: item for item in candidate.observations if item.state == FieldState.PRESENT
        }
        assert fields[S.DESCRIPTION].value == S.META_COVERAGE_TEST_DETAILS_TEXT
        assert (
            fields[S.META_COVERAGE_FIRST_PUBLICATION_DATE].value == S.META_COVERAGE_TEST_FIRST_DATE
        )
        assert fields[S.SERIES].value == [S.META_COVERAGE_TEST_SERIES]
        assert S.PAGE_COUNT not in fields and S.PUBLICATION_DATE not in fields
        assert candidate.edition_id is C.NONE
        assert recording.last_capture is not C.NONE
        assert fields[S.DESCRIPTION].observed_at == recording.last_capture.captured_at
        assert fields[S.DESCRIPTION].source_url == http.calls[C.ONE][C.ZERO]
        assert fields[S.DESCRIPTION].scope == S.WORK
        stored = cache.get(
            Source.OPEN_LIBRARY,
            S.META_COVERAGE_WORK_CACHE_KEY.format(identifier=candidate.provider_id),
        )
        assert stored is not C.NONE
        assert stored[S.META_COVERAGE_BODY] == work_response(work_payload).text
        assert stored[S.META_COVERAGE_CAPTURE_ID] == recording.last_capture.id
        empty = FakeHttp()
        repeated = OpenLibraryProvider(empty, cache=cache, work_details=C.TRUE).lookup(book)
        assert repeated.cache_hit and not empty.calls
        assert repeated.candidates == result.candidates
    finally:
        raw.close()
        cache.close()


def test_ambiguous_and_title_only_candidates_never_trigger_work_details(
    payload: dict[str, Any], book: BookRecord
) -> None:
    without_isbn = book.model_copy(update={S.ISBNS: ()})
    http = FakeHttp(response(payload))
    result = OpenLibraryProvider(http, work_details=C.TRUE).lookup(without_isbn)
    assert result.candidates and len(http.calls) == C.ONE
    second = copy.deepcopy(payload[S.DOCS][C.ZERO])
    second[S.KEY] = S.OL123W
    payload[S.DOCS].append(second)
    payload[S.NUMFOUND] = C.TWO
    http = FakeHttp(response(payload))
    result = OpenLibraryProvider(http, work_details=C.TRUE).lookup(book)
    assert len(result.candidates) == C.TWO
    assert len(http.calls) == C.ONE


def test_mismatched_detail_identity_is_partial_and_search_evidence_survives(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord
) -> None:
    work_payload[S.KEY] = S.META_RUN_TEST_MALFORMED_WORK_KEY
    http = FakeHttp(response(payload), work_response(work_payload))
    result = OpenLibraryProvider(http, work_details=C.TRUE).lookup(book)
    assert result.state == SyncState.PARTIAL
    assert result.candidates[C.ZERO].provider_id == S.OL45883W
    assert any(issue.code == S.META_COVERAGE_DETAIL_FAILED for issue in result.issues)
    assert not any(
        item.field == S.DESCRIPTION and item.state == FieldState.PRESENT
        for item in result.candidates[C.ZERO].observations
    )


def test_detail_rate_limit_retains_search_and_stops_further_http(
    payload: dict[str, Any], book: BookRecord
) -> None:
    http = FakeHttp(
        response(payload),
        work_response({}, status=C.OPEN_LIBRARY_HTTP_PAYLOAD_CODE),
    )
    provider = OpenLibraryProvider(http, work_details=C.TRUE)
    result = provider.lookup(book)
    assert result.state == SyncState.PARTIAL
    assert result.candidates
    assert result.issues[C.ZERO].retryable
    assert any(
        item.field == S.DESCRIPTION and item.state == FieldState.FAILED
        for item in result.candidates[C.ZERO].observations
    )
    with pytest.raises(ProviderDeferredError):
        provider.lookup(book)
    assert len(http.calls) == C.TWO


def test_work_detail_conflicts_retain_both_scoped_observations(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord
) -> None:
    work_payload[S.META_COVERAGE_FIRST_PUBLISH_DATE] = S.TEST_IMPORT_DATE
    work_payload[S.DESCRIPTION] = S.EMPTY
    work_payload.pop(S.SERIES)
    result = OpenLibraryProvider(
        FakeHttp(response(payload), work_response(work_payload)), work_details=C.TRUE
    ).lookup(book)
    assert result.state == SyncState.PARTIAL
    assert any(issue.code == S.META_COVERAGE_DETAIL_CONFLICT for issue in result.issues)
    fields = result.candidates[C.ZERO].observations
    years = [item for item in fields if item.field == S.FIRST_PUBLICATION_YEAR]
    assert len(years) == C.TWO and years[C.ZERO].value != years[C.ONE].value
    assert all(item.scope == S.WORK for item in years)
    assert any(item.field == S.DESCRIPTION and item.state == FieldState.EMPTY for item in fields)
    assert any(item.field == S.SERIES and item.state == FieldState.UNAVAILABLE for item in fields)


@pytest.mark.parametrize(S.META_COVERAGE_TEST_DATE_PARAM, C.META_COVERAGE_TEST_DATE_VALUES)
def test_work_publication_precision_is_retained(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord, published: str
) -> None:
    work_payload[S.META_COVERAGE_FIRST_PUBLISH_DATE] = published
    result = OpenLibraryProvider(
        FakeHttp(response(payload), work_response(work_payload)), work_details=C.TRUE
    ).lookup(book)
    observed = next(
        item
        for item in result.candidates[C.ZERO].observations
        if item.field == S.META_COVERAGE_FIRST_PUBLICATION_DATE
    )
    assert observed.value == published and observed.scope == S.WORK


def test_bad_optional_work_description_and_date_do_not_erase_search_subjects(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord
) -> None:
    work_payload[S.DESCRIPTION] = {S.VALUE: S.META_COVERAGE_TEST_DETAILS_TEXT}
    work_payload[S.META_COVERAGE_FIRST_PUBLISH_DATE] = S.META_COVERAGE_TEST_BAD_DATE
    result = OpenLibraryProvider(
        FakeHttp(response(payload), work_response(work_payload)), work_details=C.TRUE
    ).lookup(book)
    assert result.state == SyncState.PARTIAL
    fields = result.candidates[C.ZERO].observations
    assert any(item.field == S.GENRES and item.state == FieldState.PRESENT for item in fields)
    assert any(item.field == S.DESCRIPTION and item.state == FieldState.FAILED for item in fields)
    assert any(
        item.field == S.META_COVERAGE_FIRST_PUBLICATION_DATE and item.state == FieldState.FAILED
        for item in fields
    )


def test_missing_detail_fields_remain_unavailable_without_edition_inventions(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord
) -> None:
    for field in (
        S.DESCRIPTION,
        S.META_COVERAGE_SUBJECTS,
        S.SERIES,
        S.META_COVERAGE_FIRST_PUBLISH_DATE,
    ):
        work_payload.pop(field)
    result = OpenLibraryProvider(
        FakeHttp(response(payload), work_response(work_payload)), work_details=C.TRUE
    ).lookup(book)
    assert result.state == SyncState.COMPLETE
    fields = result.candidates[C.ZERO].observations
    assert any(
        item.field == S.DESCRIPTION and item.state == FieldState.UNAVAILABLE for item in fields
    )
    assert not any(
        item.field == S.PUBLICATION_DATE or item.field == S.PAGE_COUNT for item in fields
    )


def test_search_and_detail_taxonomy_differences_are_additive_not_scalar_conflicts(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord
) -> None:
    payload[S.DOCS][C.ZERO][S.META_COVERAGE_SERIES_NAME] = [S.META_COVERAGE_TEST_SERIES]
    work_payload[S.META_COVERAGE_SUBJECTS] = [S.META_COVERAGE_TEST_ADDITIONAL_SUBJECT]
    work_payload[S.SERIES] = [S.SECOND]
    result = OpenLibraryProvider(
        FakeHttp(response(payload), work_response(work_payload)), work_details=C.TRUE
    ).lookup(book)
    assert result.state == SyncState.COMPLETE
    assert not any(issue.code == S.META_COVERAGE_DETAIL_CONFLICT for issue in result.issues)
    genres = [
        item.value
        for item in result.candidates[C.ZERO].observations
        if item.field == S.GENRES and item.state == FieldState.PRESENT
    ]
    assert payload[S.DOCS][C.ZERO][S.SUBJECT] in genres
    assert work_payload[S.META_COVERAGE_SUBJECTS] in genres
    series = [
        item.value
        for item in result.candidates[C.ZERO].observations
        if item.field == S.SERIES and item.state == FieldState.PRESENT
    ]
    assert [S.META_COVERAGE_TEST_SERIES] in series and [S.SECOND] in series


@pytest.mark.parametrize(
    S.META_COVERAGE_TEST_DATE_CONFLICT_PARAMS, C.META_COVERAGE_TEST_DATE_CONFLICT_CASES
)
def test_work_publication_date_overlap_is_not_a_contradiction_but_disjoint_dates_are(
    payload: dict[str, Any], book: BookRecord, published: str, expected_conflict: bool
) -> None:
    candidate = OpenLibraryProvider(FakeHttp(response(payload))).lookup(book).candidates[C.ZERO]
    coarse = candidate.observations[C.ZERO].model_copy(
        update={S.FIELD: S.META_COVERAGE_FIRST_PUBLICATION_DATE, S.VALUE: published}
    )
    candidate = candidate.model_copy(update={S.OBSERVATIONS: (*candidate.observations, coarse)})
    fields = _Fields(
        {},
        S.META_COVERAGE_WORK_DETAIL_URL.format(identifier=candidate.provider_id),
        coarse.observed_at,
    )
    fields.add(S.META_COVERAGE_FIRST_PUBLICATION_DATE, S.META_COVERAGE_TEST_PRECISE_DATE)
    enriched, issues = _merge_details(candidate, fields)
    assert (
        any(issue.code == S.META_COVERAGE_DETAIL_CONFLICT for issue in issues) == expected_conflict
    )
    dates = [
        item.value
        for item in enriched.observations
        if item.field == S.META_COVERAGE_FIRST_PUBLICATION_DATE
    ]
    assert published in dates and S.META_COVERAGE_TEST_PRECISE_DATE in dates


def test_native_work_series_references_preserve_membership_without_inventing_labels(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord
) -> None:
    work_payload[S.SERIES] = [
        {
            S.SERIES: {S.KEY: S.META_COVERAGE_TEST_SERIES_REFERENCE},
            S.META_COVERAGE_MEMBERSHIP_POSITION: S.META_COVERAGE_TEST_POSITION,
        }
    ]
    result = OpenLibraryProvider(
        FakeHttp(response(payload), work_response(work_payload)), work_details=C.TRUE
    ).lookup(book)
    assert result.state == SyncState.COMPLETE
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    memberships = fields[S.META_COVERAGE_SERIES_MEMBERSHIPS]
    assert memberships.state == FieldState.PRESENT
    assert memberships.scope == S.WORK
    assert memberships.value == [
        {
            S.META_COVERAGE_SERIES_ID: S.META_COVERAGE_TEST_SERIES_ID,
            S.META_COVERAGE_MEMBERSHIP_POSITION: S.META_COVERAGE_TEST_POSITION,
        }
    ]
    assert fields[S.SERIES].state == FieldState.UNAVAILABLE
    assert not any(item.state == FieldState.FAILED for item in fields.values())


def test_invalid_series_reference_cannot_hide_a_valid_membership_or_become_one(
    payload: dict[str, Any], work_payload: dict[str, Any], book: BookRecord
) -> None:
    work_payload[S.SERIES] = [
        {S.SERIES: {S.KEY: S.META_COVERAGE_TEST_SERIES_REFERENCE}},
        {S.SERIES: {S.KEY: S.META_COVERAGE_TEST_BAD_SERIES_REFERENCE}},
    ]
    result = OpenLibraryProvider(
        FakeHttp(response(payload), work_response(work_payload)), work_details=C.TRUE
    ).lookup(book)
    assert result.state == SyncState.PARTIAL
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert fields[S.META_COVERAGE_SERIES_MEMBERSHIPS].value == [
        {S.META_COVERAGE_SERIES_ID: S.META_COVERAGE_TEST_SERIES_ID}
    ]
    assert any(issue.code == S.INVALID_METADATA_FIELD for issue in result.issues)
