from __future__ import annotations

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import ConnectorError, ProviderDeferredError
from bookystats.net import HttpClient


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
