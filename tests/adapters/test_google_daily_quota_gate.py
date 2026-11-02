from pathlib import Path

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import HttpClient
from bookystats.domain.errors import ProviderDeferredError
from bookystats.domain.models import Source
from bookystats.persistence.cache import MetadataCache
from tests.support.paths import fixture_path


@pytest.mark.parametrize(S.QUEUE_DAILY_TEST_PARAMETERS, C.QUEUE_DAILY_TEST_CASES)
def test_daily_quota_floor_is_durable_across_two_fresh_clients(
    tmp_path: Path,
    fixture_name: str,
    status: int,
    retry_header: str | None,
    expected_delay: int,
) -> None:
    calls: list[httpx.Request] = []
    now = C.DR_TEST_NOW
    body = fixture_path(S.METADATA, fixture_name).read_bytes()

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            status,
            content=body,
            headers={} if retry_header is C.NONE else {S.RETRY_AFTER: retry_header},
        )

    for attempt in range(C.TWO):
        cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
        try:
            with httpx.Client(transport=httpx.MockTransport(handle)) as client:
                fetcher = HttpClient(
                    allowed_hosts=(S.WWW_GOOGLEAPIS_COM,),
                    client=client,
                    min_interval=C.ZERO,
                    retry_store=cache,
                    provider=Source.GOOGLE_BOOKS,
                    wall_clock=lambda now=now: now,
                )
                if attempt == C.ZERO:
                    response = fetcher.fetch(
                        S.GOOGLE_BOOKS_ENDPOINT_HTTPS_WWW_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES,
                        params={S.KEY: S.PRIVATE_3},
                    )
                    assert response.retry_at == C.DR_TEST_NOW + expected_delay
                    assert response.wire_attempts == C.ONE
                else:
                    with pytest.raises(ProviderDeferredError):
                        fetcher.fetch(
                            S.GOOGLE_BOOKS_ENDPOINT_HTTPS_WWW_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES
                        )
                    assert fetcher.requests == C.ZERO
                state = cache.get_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM)
                assert state is not C.NONE
                assert state.retry_at == C.DR_TEST_NOW + expected_delay
                assert state.wire_attempts == C.ONE
                assert S.PRIVATE_3 not in repr(state)
                assert len(calls) == C.ONE
        finally:
            cache.close()
        now += C.ONE


@pytest.mark.parametrize(S.QUEUE_DAILY_SCOPE_TEST_PARAMETERS, C.QUEUE_DAILY_SCOPE_TEST_CASES)
def test_unknown_quota_and_other_status_provider_or_host_keep_normal_backoff(
    tmp_path: Path, fixture_name: str, status: int, provider: Source, host: str, url: str
) -> None:
    body = fixture_path(S.METADATA, fixture_name).read_bytes()
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(status, content=body))
        ) as client:
            response = HttpClient(
                allowed_hosts=(host,),
                client=client,
                min_interval=C.ZERO,
                max_attempts=C.ONE,
                retry_store=cache,
                provider=provider,
                wall_clock=lambda: C.DR_TEST_NOW,
            ).fetch(url)
            assert response.retry_at == C.DR_TEST_NOW + C.ONE
    finally:
        cache.close()
