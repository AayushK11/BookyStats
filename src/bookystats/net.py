from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import ConnectorError, ProviderDeferredError
from bookystats.interfaces import HttpResponse
from bookystats.models import SyncState


def validate_source_url(url: str, allowed_hosts: tuple[str, ...]) -> None:
    try:
        parsed = urlsplit(url)
        permitted = (
            parsed.scheme == S.HTTPS
            and parsed.hostname in allowed_hosts
            and (parsed.port in (C.NONE, C.NET_VALIDATE_SOURCE_URL_PERMITTED))
            and (not parsed.username)
            and (not parsed.password)
            and (not parsed.fragment)
        )
    except ValueError:
        permitted = C.FALSE
    if not permitted:
        raise ConnectorError(
            S.NET_VALIDATE_SOURCE_URL_NAVIGATION_THE_CONFIGURED_SOURCE_IS_NOT, code=S.UNSAFE_URL
        )


def public_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, S.EMPTY, S.EMPTY))


class HttpClient:
    def __init__(
        self,
        *,
        allowed_hosts: tuple[str, ...],
        timeout: float = C.HTTPCLIENT_INIT_TIMEOUT,
        min_interval: float = C.ONE,
        max_attempts: int = C.THREE,
        max_requests: int = C.HTTPCLIENT_INIT_MAX_REQUESTS,
        max_body_bytes: int = C.EIGHT
        * C.HTTPCLIENT_INIT_MAX_BODY_BYTES
        * C.HTTPCLIENT_INIT_MAX_BODY_BYTES,
        user_agent: str = S.HTTPCLIENT_INIT_USER_AGENT_BOOKYSTATS_PERSONAL_READING_DATA_LOOKUP,
        client: httpx.Client | None = C.NONE,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not allowed_hosts or timeout <= C.ZERO or min_interval < C.ZERO:
            raise ValueError(S.NET_HTTPCLIENT_INIT_INVALID_HTTP_TIMEOUT_OR_INTERVAL_CONFIGURATION)
        if max_attempts < C.ONE or max_requests < C.ONE or max_body_bytes < C.ONE:
            raise ValueError(S.NET_HTTPCLIENT_INIT_HTTP_LIMITS_MUST_BE_POSITIVE)
        self.allowed_hosts = allowed_hosts
        self._timeout = timeout
        self._interval = min_interval
        self._attempts = max_attempts
        self._limit = max_requests
        self._body_limit = max_body_bytes
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = C.NONE
        self._cooldown_until: float = C.ZERO
        self.requests = C.ZERO
        self._owned = client is C.NONE
        self._client = client or httpx.Client(
            timeout=timeout, follow_redirects=C.FALSE, headers={S.USER_AGENT: user_agent}
        )

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def _throttle(self) -> None:
        if self._clock() < self._cooldown_until:
            raise ProviderDeferredError(
                S.PROVIDER_COOLDOWN_MESSAGE,
                state=SyncState.BLOCKED,
                code=S.PROVIDER_COOLDOWN,
                retryable=C.TRUE,
            )
        if self.requests >= self._limit:
            raise ConnectorError(
                S.NET_HTTPCLIENT_THROTTLE_THE_CONFIGURED_BUDGET_WAS_REACHED_COLLECTION,
                code=S.REQUEST_BUDGET_EXHAUSTED,
                retryable=C.TRUE,
            )
        if self._last_request is not C.NONE:
            remaining = self._interval - (self._clock() - self._last_request)
            if remaining > C.ZERO:
                self._sleep(remaining)
        self._last_request = self._clock()
        self.requests += C.ONE

    def _request(
        self, url: str, headers: Mapping[str, str] | None
    ) -> tuple[HttpResponse, str | None]:
        self._throttle()
        try:
            with self._client.stream(
                S.GET, url, headers=headers, timeout=self._timeout, follow_redirects=C.FALSE
            ) as response:
                parts: list[bytes] = []
                length = C.ZERO
                for part in response.iter_bytes():
                    length += len(part)
                    if length > self._body_limit:
                        raise ConnectorError(
                            S.NET_HTTPCLIENT_REQUEST_SOURCE_RESPONSE_THE_CONFIGURED_SIZE_LIMIT,
                            code=S.RESPONSE_TOO_LARGE,
                        )
                    parts.append(part)
                result = HttpResponse(
                    url=public_url(str(response.url)),
                    status_code=response.status_code,
                    headers={
                        name.lower(): value
                        for name, value in response.headers.items()
                        if name.lower() in C.NET_SAFE_HEADERS
                    },
                    body=S.EMPTY_BYTES.join(parts),
                )
                return (result, response.headers.get(S.LOCATION))
        except httpx.TimeoutException:
            raise ConnectorError(
                S.NET_HTTPCLIENT_REQUEST_THE_SOURCE_REQUEST_TIMED_OUT,
                code=S.REQUEST_TIMEOUT,
                retryable=C.TRUE,
            ) from C.NONE
        except (httpx.NetworkError, httpx.RemoteProtocolError, httpx.ProxyError):
            raise ConnectorError(
                S.NET_HTTPCLIENT_REQUEST_THE_SOURCE_CONNECTION_FAILED,
                code=S.NETWORK_ERROR,
                retryable=C.TRUE,
            ) from C.NONE

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        if value is not C.NONE:
            if value.strip().isdigit():
                delay = float(value)
                if math.isfinite(delay):
                    return delay
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is C.NONE:
                    parsed = parsed.replace(tzinfo=UTC)
                return max(C.ZERO, (parsed - datetime.now(UTC)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
        return float(C.TWO**attempt)

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        validate_source_url(url, self.allowed_hosts)
        request_url = str(httpx.URL(url).copy_merge_params(params or {}))
        visited: set[str] = set()
        for _redirect in range(C.SIX):
            validate_source_url(request_url, self.allowed_hosts)
            if request_url in visited:
                raise ConnectorError(
                    S.NET_HTTPCLIENT_FETCH_THE_SOURCE_REDIRECTED_IN_A_LOOP, code=S.REDIRECT_LOOP
                )
            visited.add(request_url)
            result: HttpResponse | None = C.NONE
            location: str | None = C.NONE
            for attempt in range(self._attempts):
                try:
                    result, location = self._request(request_url, headers)
                except ProviderDeferredError:
                    raise
                except ConnectorError as exc:
                    if (
                        not exc.retryable
                        or exc.code == S.REQUEST_BUDGET_EXHAUSTED
                        or attempt + C.ONE == self._attempts
                    ):
                        raise
                    self._sleep(float(C.TWO**attempt))
                    continue
                if result.status_code not in C.NET_RETRYABLE:
                    break
                delay = self._retry_delay(result.headers.get(S.RETRY_AFTER), attempt)
                if attempt + C.ONE == self._attempts or delay > C.NET_HTTPCLIENT_FETCH:
                    self._cooldown_until = max(self._cooldown_until, self._clock() + delay)
                    break
                self._sleep(delay)
            if result is C.NONE:
                raise ConnectorError(
                    S.NET_HTTPCLIENT_FETCH_SOURCE_REQUEST_DID_NOT_RETURN_A_RESPONSE,
                    code=S.NO_RESPONSE,
                )
            if result.status_code not in C.NET_REDIRECTS:
                return result
            if not location:
                raise ConnectorError(
                    S.NET_HTTPCLIENT_FETCH_SOURCE_REDIRECT_HAS_NO_DESTINATION,
                    code=S.INVALID_REDIRECT,
                )
            redirected = urljoin(request_url, location)
            validate_source_url(redirected, self.allowed_hosts)
            if urlsplit(request_url).hostname != urlsplit(redirected).hostname:
                headers = C.NONE
            request_url = redirected
        raise ConnectorError(
            S.NET_HTTPCLIENT_FETCH_THE_SOURCE_EXCEEDED_THE_REDIRECT_LIMIT, code=S.REDIRECT_LIMIT
        )
