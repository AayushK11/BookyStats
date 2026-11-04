from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import HttpClient
from bookystats.domain.errors import ConnectorError, ProviderDeferredError
from bookystats.domain.models import Source
from bookystats.persistence.cache import MetadataCache


@pytest.mark.parametrize(S.CODE, tuple(C.WD_TRANSIENT_API_CODES))
@pytest.mark.parametrize(S.WIKIDATA_TEST_RETRY_FIELDS, C.WIKIDATA_TEST_RETRY_DELAYS)
def test_wikidata_http_success_api_pause_survives_fresh_clients(
    tmp_path: Path, code: str, retry_header: str | None, expected_delay: int
) -> None:
    calls: list[httpx.Request] = []
    now = [C.DR_TEST_NOW]

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            C.INTERFACES_PAGEDOCUMENT_STATUS_CODE,
            json={S.ERROR: {S.CODE: code}} if len(calls) == C.ONE else {},
            headers={} if retry_header is C.NONE else {S.RETRY_AFTER: retry_header},
        )

    for attempt in range(C.THREE):
        cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
        try:
            with httpx.Client(transport=httpx.MockTransport(handle)) as client:
                fetcher = HttpClient(
                    allowed_hosts=(S.WIKIDATA_HOST,),
                    client=client,
                    min_interval=C.ZERO,
                    max_attempts=C.ONE,
                    retry_store=cache,
                    provider=Source.WIKIDATA,
                    wall_clock=lambda: now[C.ZERO],
                )
                if attempt == C.ONE:
                    with pytest.raises(ProviderDeferredError):
                        fetcher.fetch(S.WD_ENDPOINT)
                    assert fetcher.requests == C.ZERO
                    now[C.ZERO] += expected_delay
                else:
                    response = fetcher.fetch(S.WD_ENDPOINT)
                    assert response.wire_attempts == len(calls)
                    assert response.retry_at == (
                        C.DR_TEST_NOW + expected_delay if attempt == C.ZERO else C.NONE
                    )
                    assert response.error_code == (
                        S.DR_HTTP_RETRYABLE if attempt == C.ZERO else C.NONE
                    )
        finally:
            cache.close()
    assert len(calls) == C.TWO


@pytest.mark.parametrize(S.CODE, (S.TEST, [], C.NONE))
def test_wikidata_unknown_or_malformed_api_code_does_not_create_a_pause(code: object) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                C.INTERFACES_PAGEDOCUMENT_STATUS_CODE, json={S.ERROR: {S.CODE: code}}
            )
        )
    ) as client:
        fetcher = HttpClient(
            allowed_hosts=(S.WIKIDATA_HOST,),
            client=client,
            min_interval=C.ZERO,
            provider=Source.WIKIDATA,
        )
        response = fetcher.fetch(S.WD_ENDPOINT)
        assert response.retry_at is C.NONE
        assert response.error_code is C.NONE


def test_redirect_outside_source_is_never_followed() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            C.TEST_NET_REDIRECT_OUTSIDE_SOURCE_IS_NEVER_FOLLOWED_HANDLE,
            headers={
                S.LOCATION: S.TEST_REDIRECT_OUTSIDE_SOURCE_IS_HEADERS_HTTPS_OTHER_INVALID_PRIVATE
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handle))
    with (
        HttpClient(
            allowed_hosts=(S.SOURCE_INVALID,), client=client, min_interval=C.ZERO
        ) as fetcher,
        pytest.raises(ConnectorError, match=S.OUTSIDE),
    ):
        fetcher.fetch(S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS)
    assert len(requests) == C.ONE


@pytest.mark.parametrize(S.MAX_ATTEMPTS, (C.ONE, C.THREE))
def test_retry_after_large_delay_does_not_hammer_provider(max_attempts: int) -> None:
    requests: list[httpx.Request] = []
    sleeps: list[float] = []
    now = [C.ZERO]

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            C.TEST_NET_RETRY_AFTER_LARGE_DELAY_DOES_NOT_HAMMER_PROVIDER_HANDLE,
            headers={
                S.RETRY_AFTER: S.TEST_RETRY_AFTER_LARGE_DELAY_HAMMER_PROVIDER_HANDLE_HEADERS_TEXT
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        fetcher = HttpClient(
            allowed_hosts=(S.SOURCE_INVALID,),
            client=client,
            min_interval=C.ZERO,
            sleep=sleeps.append,
            clock=lambda: now[C.ZERO],
            max_attempts=max_attempts,
        )
        response = fetcher.fetch(
            S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
        )
        with pytest.raises(ProviderDeferredError):
            fetcher.fetch(S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS)
        assert len(requests) == C.ONE
        now[C.ZERO] += int(S.TEST_RETRY_AFTER_LARGE_DELAY_HAMMER_PROVIDER_HANDLE_HEADERS_TEXT)
        fetcher.fetch(S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS)
    assert response.status_code == C.TEST_NET_RETRY_AFTER_LARGE_DELAY_DOES_NOT_HAMMER_PROVIDER
    assert len(requests) == C.TWO
    assert sleeps == []


def test_transient_error_retries_but_receipt_does_not_contain_key() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.params[S.KEY] == S.PRIVATE_3
        return httpx.Response(
            C.TEST_NET_TRANSIENT_ERROR_RETRIES_BUT_DOES_NOT_CONTAIN_KEY_HANDLE
            if len(seen) == C.ONE
            else C.TEST_NET_TRANSIENT_ERROR_RETRIES_BUT_DOES_NOT_CONTAIN_KEY_HANDLE_2,
            headers={S.SET_COOKIE_2: S.PRIVATE_SESSION},
            content=S.TEST_TRANSIENT_ERROR_RETRIES_BUT_CONTAIN_KEY_HANDLE_CONTENT_BYTES,
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        fetcher = HttpClient(
            allowed_hosts=(S.SOURCE_INVALID,),
            client=client,
            min_interval=C.ZERO,
            sleep=lambda _: C.NONE,
        )
        response = fetcher.fetch(
            S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS,
            params={S.KEY: S.PRIVATE_3},
        )
    assert len(seen) == C.TWO
    assert (
        response.status_code == C.TEST_NET_TRANSIENT_ERROR_RETRIES_BUT_RECEIPT_DOES_NOT_CONTAIN_KEY
    )
    assert response.url == S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
    assert S.PRIVATE_4 not in repr(response)


def test_response_budget_and_network_error_are_explicit() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                C.TEST_NET_RESPONSE_BUDGET_AND_NETWORK_ERROR_ARE_EXPLICIT_TRANSPORT,
                content=S.TEST_RESPONSE_BUDGET_AND_NETWORK_EXPLICIT_TRANSPORT_CONTENT_BYTES,
            )
        )
    ) as client:
        fetcher = HttpClient(
            allowed_hosts=(S.SOURCE_INVALID,),
            client=client,
            max_body_bytes=C.THREE,
            min_interval=C.ZERO,
        )
        with pytest.raises(
            ConnectorError,
            match=S.TEST_NET_RESPONSE_BUDGET_AND_NETWORK_ARE_EXPLICIT_MATCH_SIZE_LIMIT,
        ):
            fetcher.fetch(S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(
                httpx.ConnectError(S.SECRET_IN_EXCEPTION, request=request)
            )
        )
    ) as client:
        fetcher = HttpClient(
            allowed_hosts=(S.SOURCE_INVALID,),
            client=client,
            max_attempts=C.ONE,
            min_interval=C.ZERO,
        )
        with pytest.raises(ConnectorError) as failure:
            fetcher.fetch(
                S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS,
                params={S.KEY: S.PRIVATE_3},
            )
        assert S.SECRET_2 not in str(failure.value)
        assert S.PRIVATE_3 not in str(failure.value)


@pytest.mark.parametrize(
    S.URL,
    [
        S.TEST_NET_UNSAFE_URLS_FAIL_BEFORE_REQUEST_HTTP_SOURCE_INVALID_BOOKS,
        S.TEST_NET_UNSAFE_URLS_FAIL_BEFORE_SOURCE_INVALID_EVIL_EXAMPLE_BOOKS,
        S.TEST_NET_UNSAFE_URLS_FAIL_BEFORE_USER_PASSWORD_SOURCE_INVALID_BOOKS,
        S.TEST_NET_UNSAFE_URLS_FAIL_BEFORE_REQUEST_HTTPS_SOURCE_INVALID_BOOKS,
        S.TEST_NET_UNSAFE_URLS_FAIL_BEFORE_REQUEST_FILE_C_PRIVATE,
    ],
)
def test_unsafe_urls_fail_before_request(url: str) -> None:

    def handle(request: httpx.Request) -> httpx.Response:
        pytest.fail(S.TEST_NET_UNSAFE_URLS_FAIL_UNSAFE_NAVIGATION_REACHED_THE_TRANSPORT)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        fetcher = HttpClient(allowed_hosts=(S.SOURCE_INVALID,), client=client)
        with pytest.raises(ConnectorError):
            fetcher.fetch(url)


@pytest.mark.parametrize(S.DR_TEST_RETRY_PARAMETERS, C.DR_TEST_RESTART_CASES)
def test_retry_gate_survives_restart_and_expires_without_reset(
    tmp_path: Path, status: int, headers: dict[str, str], delay: int
) -> None:
    now = [C.DR_TEST_NOW]
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, headers=headers)

    path = tmp_path / S.CATALOG_SQLITE
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        cache = MetadataCache(path)
        first = HttpClient(
            allowed_hosts=(S.SOURCE_INVALID,),
            client=client,
            max_attempts=C.ONE,
            min_interval=C.ZERO,
            retry_store=cache,
            provider=Source.OPEN_LIBRARY,
            wall_clock=lambda: now[C.ZERO],
        )
        response = first.fetch(
            S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
        )
        assert response.retry_at == now[C.ZERO] + delay
        assert response.wire_attempts == C.ONE
        cache.close()
        cache = MetadataCache(path)
        try:
            restarted = HttpClient(
                allowed_hosts=(S.SOURCE_INVALID,),
                client=client,
                max_attempts=C.ONE,
                min_interval=C.ZERO,
                retry_store=cache,
                provider=Source.OPEN_LIBRARY,
                wall_clock=lambda: now[C.ZERO],
            )
            with pytest.raises(ProviderDeferredError):
                restarted.fetch(
                    S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
                )
            assert len(calls) == C.ONE
            now[C.ZERO] += delay
            resumed = restarted.fetch(
                S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
            )
            assert resumed.wire_attempts == C.TWO
            assert resumed.retry_at == now[C.ZERO] + (delay if headers else C.TWO)
        finally:
            cache.close()


def test_http_date_retry_after_and_provider_host_scopes(tmp_path: Path) -> None:
    now = [C.DR_TEST_NOW]
    deadline = now[C.ZERO] + C.TEST_PROVIDER_COOLDOWN_SECONDS
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            C.HTTP_TOO_MANY_REQUESTS,
            headers={
                S.RETRY_AFTER: format_datetime(datetime.fromtimestamp(deadline, UTC), usegmt=C.TRUE)
            },
        )

    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        try:
            first = HttpClient(
                allowed_hosts=(S.SOURCE_INVALID, S.DR_TEST_OTHER_HOST),
                client=client,
                max_attempts=C.ONE,
                min_interval=C.ZERO,
                retry_store=cache,
                provider=Source.OPEN_LIBRARY,
                wall_clock=lambda: now[C.ZERO],
            )
            response = first.fetch(
                S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
            )
            assert response.retry_at == deadline
            other_host = first.fetch(S.DR_TEST_OTHER_URL)
            assert other_host.wire_attempts == C.ONE
            other_provider = HttpClient(
                allowed_hosts=(S.SOURCE_INVALID,),
                client=client,
                max_attempts=C.ONE,
                min_interval=C.ZERO,
                retry_store=cache,
                provider=Source.GOOGLE_BOOKS,
                wall_clock=lambda: now[C.ZERO],
            )
            assert (
                other_provider.fetch(
                    S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
                ).wire_attempts
                == C.ONE
            )
            assert len(calls) == C.THREE
        finally:
            cache.close()


def test_network_failure_and_budget_have_truthful_durable_diagnostics(tmp_path: Path) -> None:
    now = [C.DR_TEST_NOW]
    failing = [C.TRUE]

    def handle(request: httpx.Request) -> httpx.Response:
        if failing[C.ZERO]:
            raise httpx.ConnectError(S.SECRET_IN_EXCEPTION, request=request)
        return httpx.Response(C.HTTP_OK)

    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        try:
            fetcher = HttpClient(
                allowed_hosts=(S.SOURCE_INVALID,),
                client=client,
                max_attempts=C.ONE,
                max_requests=C.ONE,
                min_interval=C.ZERO,
                retry_store=cache,
                provider=Source.OPEN_LIBRARY,
                wall_clock=lambda: now[C.ZERO],
            )
            with pytest.raises(ConnectorError) as error:
                fetcher.fetch(
                    S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS,
                    params={S.KEY: S.PRIVATE_3},
                )
            assert error.value.code == S.NETWORK_ERROR
            state = cache.get_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID)
            assert state is not C.NONE
            assert state.status_code is C.NONE
            assert state.error_code == S.NETWORK_ERROR
            assert state.wire_attempts == C.ONE
            cache.close()
            cache = MetadataCache(path)
            restarted = HttpClient(
                allowed_hosts=(S.SOURCE_INVALID,),
                client=client,
                max_attempts=C.ONE,
                max_requests=C.ONE,
                min_interval=C.ZERO,
                retry_store=cache,
                provider=Source.OPEN_LIBRARY,
                wall_clock=lambda: now[C.ZERO],
            )
            with pytest.raises(ProviderDeferredError):
                restarted.fetch(
                    S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
                )
            now[C.ZERO] += C.ONE
            failing[C.ZERO] = C.FALSE
            assert (
                restarted.fetch(
                    S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
                ).status_code
                == C.HTTP_OK
            )
            with pytest.raises(ConnectorError) as error:
                restarted.fetch(
                    S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
                )
            assert error.value.code == S.REQUEST_BUDGET_EXHAUSTED
            state = cache.get_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID)
            assert state is not C.NONE
            assert state.status_code is C.NONE
            assert state.error_code == S.REQUEST_BUDGET_EXHAUSTED
            assert state.wire_attempts == C.TWO
        finally:
            cache.close()
    assert S.PRIVATE_3.encode() not in path.read_bytes()
    assert S.SECRET_IN_EXCEPTION.encode() not in path.read_bytes()


class InterruptedStream(httpx.SyncByteStream):
    def __iter__(self) -> Iterator[bytes]:
        yield S.EMPTY_BYTES
        raise KeyboardInterrupt


@pytest.mark.parametrize(S.DR_TEST_FAILURE, C.DR_TEST_BODY_FAILURES)
def test_retry_after_is_durable_before_body_failure(tmp_path: Path, failure: str) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            C.HTTP_TOO_MANY_REQUESTS,
            headers={S.RETRY_AFTER: S.DR_TEST_RETRY_SECONDS},
            stream=InterruptedStream() if failure == S.DR_TEST_BODY_ABORT else C.NONE,
            content=(
                S.EMPTY_BYTES
                if failure == S.DR_TEST_BODY_ABORT
                else S.TEST_RESPONSE_BUDGET_AND_NETWORK_EXPLICIT_TRANSPORT_CONTENT_BYTES
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        try:
            fetcher = HttpClient(
                allowed_hosts=(S.SOURCE_INVALID,),
                client=client,
                min_interval=C.ZERO,
                max_attempts=C.ONE,
                max_body_bytes=C.ONE,
                retry_store=cache,
                provider=Source.OPEN_LIBRARY,
                wall_clock=lambda: C.DR_TEST_NOW,
            )
            with pytest.raises(
                KeyboardInterrupt if failure == S.DR_TEST_BODY_ABORT else ConnectorError
            ):
                fetcher.fetch(
                    S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
                )
            state = cache.get_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID)
            assert state is not C.NONE
            assert state.status_code == C.HTTP_TOO_MANY_REQUESTS
            assert state.retry_at == C.DR_TEST_NOW + C.TEST_PROVIDER_COOLDOWN_SECONDS
            assert state.wire_attempts == C.ONE
        finally:
            cache.close()


def test_persistent_short_retry_waits_and_success_clears_failure_state(tmp_path: Path) -> None:
    now = [C.DR_TEST_NOW]
    calls: list[httpx.Request] = []
    sleeps: list[float] = []

    def wait(delay: float) -> None:
        sleeps.append(delay)
        now[C.ZERO] += delay

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            C.NET_RETRYABLE_5 if len(calls) == C.ONE else C.HTTP_OK,
            headers={
                S.ETAG: S.PRIVATE_3,
                S.SET_COOKIE_2: S.PRIVATE_SESSION,
                S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON,
            },
        )

    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        try:
            fetcher = HttpClient(
                allowed_hosts=(S.SOURCE_INVALID,),
                client=client,
                min_interval=C.ZERO,
                retry_store=cache,
                provider=Source.OPEN_LIBRARY,
                wall_clock=lambda: now[C.ZERO],
                sleep=wait,
            )
            response = fetcher.fetch(
                S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS,
                params={S.KEY: S.PRIVATE_3},
            )
            assert response.status_code == C.HTTP_OK
            assert response.retry_at is C.NONE
            assert response.wire_attempts == C.TWO
            assert response.error_code is C.NONE
            assert response.headers == {
                S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON
            }
            assert sleeps == [C.ONE]
            state = cache.get_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID)
            assert state is not C.NONE and state.failures == C.ZERO
        finally:
            cache.close()
    assert S.PRIVATE_3.encode() not in path.read_bytes()
    assert S.PRIVATE_SESSION.encode() not in path.read_bytes()


def test_abort_before_response_keeps_unknown_status_and_restart_guard(tmp_path: Path) -> None:
    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise KeyboardInterrupt

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        fetcher = HttpClient(
            allowed_hosts=(S.SOURCE_INVALID,),
            client=client,
            min_interval=C.ZERO,
            retry_store=cache,
            provider=Source.OPEN_LIBRARY,
            wall_clock=lambda: C.DR_TEST_NOW,
        )
        with pytest.raises(KeyboardInterrupt):
            fetcher.fetch(S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS)
        cache.close()
        cache = MetadataCache(path)
        try:
            state = cache.get_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID)
            assert state is not C.NONE
            assert state.status_code is C.NONE
            assert state.error_code == S.DR_REQUEST_PENDING
            assert state.retry_at == C.DR_TEST_NOW + C.HTTPCLIENT_INIT_TIMEOUT
            restarted = HttpClient(
                allowed_hosts=(S.SOURCE_INVALID,),
                client=client,
                min_interval=C.ZERO,
                retry_store=cache,
                provider=Source.OPEN_LIBRARY,
                wall_clock=lambda: C.DR_TEST_NOW,
            )
            with pytest.raises(ProviderDeferredError):
                restarted.fetch(
                    S.TEST_NET_REDIRECT_OUTSIDE_SOURCE_FOLLOWED_HTTPS_SOURCE_INVALID_BOOKS
                )
            assert len(calls) == C.ONE
        finally:
            cache.close()
