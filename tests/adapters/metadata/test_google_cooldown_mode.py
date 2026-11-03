from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import cooldown_message
from bookystats.adapters.metadata.google_books import GoogleBooksProvider
from bookystats.domain.errors import ProviderDeferredError
from bookystats.domain.interfaces import HttpResponse, HttpRetryState
from bookystats.domain.models import BookRecord, Source, SyncState
from bookystats.persistence.cache import MetadataCache
from tests.support.paths import fixture_path


class RecordingFetcher:
    def __init__(self, *bodies: bytes) -> None:
        self.bodies = list(bodies)
        self.calls: list[str] = []

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        self.calls.append(url)
        return HttpResponse(
            url=url,
            status_code=C.HTTP_OK,
            headers={
                S.CONTENT_TYPE_2: S.TEST_GOOGLE_BOOKS_RESPONSE_HEADERS_APPLICATION_JSON_CHARSET_UTF
            },
            body=self.bodies.pop(C.ZERO),
        )


@pytest.fixture
def book() -> BookRecord:
    return BookRecord(
        source=Source.STORYGRAPH,
        source_id=S.ORIGINAL_READER_BOOK_ID,
        title=S.MATILDA,
        authors=(S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
        isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
        url=S.TEST_GOOGLE_BOOKS_BOOK_URL_THESTORYGRAPH_COM_BOOKS_ORIGINAL_READER,
    )


@pytest.fixture
def gate() -> HttpRetryState:
    return HttpRetryState(
        retry_at=C.DR_TEST_NOW + C.QUEUE_GOOGLE_DAILY_COOLDOWN_SECONDS,
        status_code=C.L1_TEST_GATE_STATUS,
        error_code=S.DR_HTTP_RETRYABLE,
        failures=C.ONE,
        wire_attempts=C.ONE,
        quota=dict(C.L1_DETAILED_EVIDENCE),
    )


def test_gated_provider_defers_uncached_lookups_without_credentials_or_requests(
    book: BookRecord, gate: HttpRetryState
) -> None:
    fetcher = RecordingFetcher()
    with pytest.raises(ProviderDeferredError) as deferred:
        GoogleBooksProvider(fetcher, cooldown=gate).lookup(book)
    assert str(deferred.value) == cooldown_message(gate)
    assert S.L1_TEST_DETAILED_LIMIT in str(deferred.value)
    assert deferred.value.state == SyncState.BLOCKED
    assert deferred.value.code == S.PROVIDER_COOLDOWN
    assert deferred.value.retryable
    assert not fetcher.calls


def test_gated_provider_still_serves_complete_cached_results_without_a_request(
    tmp_path: Path, book: BookRecord, gate: HttpRetryState
) -> None:
    body = json.dumps(
        json.loads(fixture_path(S.METADATA, S.GOOGLE_BOOKS_JSON).read_text(encoding=S.UTF_8))
    ).encode()
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        seeding = RecordingFetcher(body)
        first = GoogleBooksProvider(seeding, api_key=S.SECRET_API_KEY, cache=cache).lookup(book)
        assert first.state == SyncState.COMPLETE
        assert len(seeding.calls) == C.ONE
        gated = RecordingFetcher()
        cached = GoogleBooksProvider(gated, cache=cache, cooldown=gate).lookup(book)
        assert cached.state == SyncState.COMPLETE
        assert cached.cache_hit
        assert cached.candidates == first.candidates
        assert not gated.calls
    finally:
        cache.close()
