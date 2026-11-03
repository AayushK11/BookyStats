from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.metadata.open_library import OpenLibraryProvider
from bookystats.domain.errors import ConnectorError, ProviderDeferredError
from bookystats.domain.interfaces import HttpResponse
from bookystats.domain.matching import select_metadata_candidate
from bookystats.domain.models import BookRecord, Source, SyncState
from bookystats.persistence.cache import MetadataCache


class FakeHttp:
    def __init__(self, *responses: HttpResponse | ConnectorError) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        self.calls.append(dict(params or {}))
        assert self.responses, S.TEST_GOOGLE_BOOKS_FAKEHTTP_FETCH_UNEXPECTED_METADATA_REQUEST
        response = self.responses.pop(C.ZERO)
        if isinstance(response, ConnectorError):
            raise response
        return response


def search(*docs: dict[str, object], found: int | None = C.NONE) -> HttpResponse:
    payload = {
        S.NUMFOUND: len(docs) if found is C.NONE else found,
        S.START: C.ZERO,
        S.NUMFOUNDEXACT: C.TRUE,
        S.DOCS: list(docs),
    }
    return HttpResponse(
        url=S.OPEN_LIBRARY_ENDPOINT_HTTPS_OPENLIBRARY_ORG_SEARCH_JSON,
        status_code=C.TEST_OPEN_LIBRARY_RESPONSE_STATUS,
        headers={S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
        body=json.dumps(payload).encode(),
    )


def doc(
    work_id: str, title: str, authors: tuple[str, ...], isbns: tuple[str, ...]
) -> dict[str, object]:
    return {S.KEY: work_id, S.TITLE: title, S.AUTHOR_NAME: list(authors), S.ISBN: list(isbns)}


def book(**changes: object) -> BookRecord:
    return BookRecord.model_validate(
        {
            S.SOURCE: Source.GOODREADS,
            S.SOURCE_ID: S.L1_ID_TEST_SOURCE_ID,
            S.TITLE: S.L1_ID_TEST_BARE_TITLE,
            S.AUTHORS: (S.L1_ID_TEST_AUTHOR,),
            S.URL: S.L1_ID_TEST_BOOK_URL,
        }
        | changes
    )


def exact_doc(*isbns: str) -> dict[str, object]:
    return doc(S.L1_ID_TEST_WORK_ID, S.L1_ID_TEST_BARE_TITLE, (S.L1_ID_TEST_AUTHOR,), isbns)


def noise_doc() -> dict[str, object]:
    return doc(
        S.L1_ID_TEST_OTHER_WORK_ID,
        S.L1_ID_TEST_UNRELATED_TITLE,
        (S.L1_ID_TEST_OTHER_AUTHOR,),
        (),
    )


def issue_codes(result: object) -> set[str]:
    return {issue.code for issue in getattr(result, S.ISSUES)}


def test_article_variant_work_is_returned_and_selected_for_a_title_search() -> None:
    variant = doc(S.L1_ID_TEST_WORK_ID, S.L1_ID_TEST_ARTICLE_TITLE, (S.L1_ID_TEST_AUTHOR,), ())
    source = book()
    result = OpenLibraryProvider(FakeHttp(search(variant))).lookup(source)
    assert result.state == SyncState.COMPLETE and not result.issues
    assert select_metadata_candidate(source, result.candidates) is not C.NONE


def test_contributor_superset_with_the_shared_isbn_is_selected() -> None:
    credited = doc(
        S.L1_ID_TEST_WORK_ID,
        S.L1_ID_TEST_BARE_TITLE,
        (S.L1_ID_TEST_AUTHOR, S.L1_ID_TEST_CONTRIBUTOR),
        (S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
    )
    source = book(isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,))
    result = OpenLibraryProvider(FakeHttp(search(credited))).lookup(source)
    assert result.candidates
    assert select_metadata_candidate(source, result.candidates) is not C.NONE


def test_unrelated_documents_do_not_block_a_unique_match_and_are_never_cached(
    tmp_path: Path,
) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        first = OpenLibraryProvider(FakeHttp(search(exact_doc(), noise_doc())), cache=cache).lookup(
            book()
        )
        assert first.state == SyncState.COMPLETE and not first.issues
        assert [item.provider_id for item in first.candidates] == [S.L1_ID_TEST_WORK_ID]
        http = FakeHttp(search(exact_doc(), noise_doc()))
        OpenLibraryProvider(http, cache=cache).lookup(book())
        assert len(http.calls) == C.ONE
    finally:
        cache.close()


def test_subtitle_plausible_document_still_blocks_the_match() -> None:
    subtitled = doc(
        S.L1_ID_TEST_OTHER_WORK_ID,
        S.L1_ID_TEST_SUBTITLE_TITLE,
        (S.L1_ID_TEST_AUTHOR,),
        (),
    )
    result = OpenLibraryProvider(FakeHttp(search(exact_doc(), subtitled))).lookup(book())
    assert S.UNVERIFIED_CANDIDATES in issue_codes(result)


def test_truncated_search_still_blocks_unrelated_document_rescue() -> None:
    http = FakeHttp(search(exact_doc(), noise_doc(), found=C.THREE))
    result = OpenLibraryProvider(http).lookup(book())
    assert S.UNVERIFIED_CANDIDATES in issue_codes(result)


def test_ambiguous_exact_documents_are_never_selected() -> None:
    twin = doc(S.L1_ID_TEST_OTHER_WORK_ID, S.L1_ID_TEST_BARE_TITLE, (S.L1_ID_TEST_AUTHOR,), ())
    source = book()
    result = OpenLibraryProvider(FakeHttp(search(exact_doc(), twin))).lookup(source)
    assert len(result.candidates) == C.TWO
    assert select_metadata_candidate(source, result.candidates) is C.NONE


def test_isbn_negative_falls_back_to_a_title_author_search() -> None:
    source = book(isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,))
    http = FakeHttp(search(), search(exact_doc(S.L1_ID_TEST_OTHER_ISBN)))
    result = OpenLibraryProvider(http).lookup(source)
    assert len(http.calls) == C.TWO
    assert http.calls[C.ONE][S.Q] == S.OPEN_LIBRARY_QUERY_TEMPLATE.format(
        v0=S.L1_ID_TEST_QUERY_TITLE, v1=S.L1_ID_TEST_AUTHOR_QUERY
    )
    assert select_metadata_candidate(source, result.candidates) is not C.NONE


def test_confirmed_negative_is_cached_for_both_queries(tmp_path: Path) -> None:
    source = book(isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,))
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        first = OpenLibraryProvider(FakeHttp(search(), search()), cache=cache).lookup(source)
        http = FakeHttp()
        again = OpenLibraryProvider(http, cache=cache).lookup(source)
        assert first.state == again.state == SyncState.COMPLETE and not again.candidates
        assert not first.cache_hit and again.cache_hit and not http.calls
    finally:
        cache.close()


def test_isbn_hit_or_missing_authors_do_not_trigger_the_fallback() -> None:
    isbns = (S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,)
    hit = FakeHttp(search(exact_doc(*isbns)))
    assert OpenLibraryProvider(hit).lookup(book(isbns=isbns)).candidates
    assert len(hit.calls) == C.ONE
    anonymous = FakeHttp(search())
    result = OpenLibraryProvider(anonymous).lookup(book(isbns=isbns, authors=()))
    assert result.state == SyncState.COMPLETE and not result.candidates
    assert len(anonymous.calls) == C.ONE


def test_deferred_fallback_is_retryable_and_keeps_other_results() -> None:
    first = book(isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,))
    second = book(
        source_id=S.L1_ID_TEST_SECOND_SOURCE_ID,
        title=S.L1_ID_TEST_UNRELATED_TITLE,
        authors=(S.L1_ID_TEST_OTHER_AUTHOR,),
        isbns=(S.L1_ID_TEST_OTHER_ISBN,),
    )
    found = doc(
        S.L1_ID_TEST_OTHER_WORK_ID,
        S.L1_ID_TEST_UNRELATED_TITLE,
        (S.L1_ID_TEST_OTHER_AUTHOR,),
        (S.L1_ID_TEST_OTHER_ISBN,),
    )
    http = FakeHttp(
        search(found),
        ProviderDeferredError(
            S.PROVIDER_COOLDOWN_MESSAGE, code=S.PROVIDER_COOLDOWN, retryable=C.TRUE
        ),
    )
    deferred, kept = OpenLibraryProvider(http).lookup_many((first, second))
    assert deferred.state == SyncState.PARTIAL and not deferred.candidates
    assert issue_codes(deferred) == {S.MC_TARGET_DEFERRED, S.PROVIDER_COOLDOWN}
    assert all(issue.retryable for issue in deferred.issues)
    assert kept.state == SyncState.COMPLETE and kept.candidates
    assert len(http.calls) == C.TWO


def test_failed_fallback_is_a_failure_not_a_negative() -> None:
    http = FakeHttp(
        search(),
        ConnectorError(
            S.L1_ID_TEST_FAILURE_MESSAGE, code=S.L1_ID_TEST_FAILURE_CODE, retryable=C.TRUE
        ),
    )
    result = OpenLibraryProvider(http).lookup(book(isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,)))
    assert result.state == SyncState.FAILED and not result.candidates
    assert S.METADATA_REQUEST_FAILED in issue_codes(result)


def test_halted_run_defers_a_due_fallback_instead_of_recording_a_negative(
    tmp_path: Path,
) -> None:
    cached = book(isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,))
    fresh = book(
        source_id=S.L1_ID_TEST_SECOND_SOURCE_ID,
        title=S.L1_ID_TEST_UNRELATED_TITLE,
        authors=(S.L1_ID_TEST_OTHER_AUTHOR,),
        isbns=(S.L1_ID_TEST_OTHER_ISBN,),
    )
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        OpenLibraryProvider(FakeHttp(search(), search()), cache=cache).lookup(cached)
        http = FakeHttp(
            ProviderDeferredError(
                S.PROVIDER_COOLDOWN_MESSAGE, code=S.PROVIDER_COOLDOWN, retryable=C.TRUE
            )
        )
        pending, other = OpenLibraryProvider(http, cache=cache).lookup_many((cached, fresh))
        assert pending.state == other.state == SyncState.PARTIAL
        assert S.METADATA_DEFERRED in issue_codes(pending)
        assert len(http.calls) == C.ONE
    finally:
        cache.close()
