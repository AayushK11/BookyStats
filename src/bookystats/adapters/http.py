from __future__ import annotations

import base64
import html
import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, quote, quote_plus, unquote_plus, urljoin, urlsplit, urlunsplit

import httpx

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import ConnectorError, ProviderDeferredError
from bookystats.domain.interfaces import HttpResponse, HttpRetryState, RetryStateStore
from bookystats.domain.models import Source, SyncState


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
        wall_clock: Callable[[], float] = time.time,
        retry_store: RetryStateStore | None = C.NONE,
        provider: Source | None = C.NONE,
    ) -> None:
        if not allowed_hosts or timeout <= C.ZERO or min_interval < C.ZERO:
            raise ValueError(S.NET_HTTPCLIENT_INIT_INVALID_HTTP_TIMEOUT_OR_INTERVAL_CONFIGURATION)
        if max_attempts < C.ONE or max_requests < C.ONE or max_body_bytes < C.ONE:
            raise ValueError(S.NET_HTTPCLIENT_INIT_HTTP_LIMITS_MUST_BE_POSITIVE)
        if retry_store is not C.NONE and provider not in C.RAW_METADATA_SOURCES:
            raise ValueError(S.DR_RETRY_CONFIG_ERROR)
        self.allowed_hosts = allowed_hosts
        self._timeout = timeout
        self._interval = min_interval
        self._attempts = max_attempts
        self._limit = max_requests
        self._body_limit = max_body_bytes
        self._sleep = sleep
        self._clock = clock
        self._wall_clock = wall_clock
        self._retry_store = retry_store
        self._provider = provider
        self._states: dict[str, HttpRetryState] = {}
        self._last_request: float | None = C.NONE
        self._cooldowns: dict[str, float] = {}
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

    def _state(self, host: str) -> HttpRetryState:
        if self._retry_store is not C.NONE and self._provider is not C.NONE:
            return self._retry_store.get_retry_state(self._provider, host) or HttpRetryState()
        return self._states.get(host, HttpRetryState())

    def _save_state(self, host: str, state: HttpRetryState) -> None:
        if self._retry_store is not C.NONE and self._provider is not C.NONE:
            self._retry_store.save_retry_state(self._provider, host, state)
        self._states[host] = state

    def _throttle(self, host: str) -> None:
        state = self._state(host)
        if self._clock() < self._cooldowns.get(host, C.ZERO) or (
            self._retry_store is not C.NONE
            and state.retry_at is not C.NONE
            and self._wall_clock() < state.retry_at
        ):
            raise ProviderDeferredError(
                S.DR_COOLDOWN_MESSAGE.format(deadline=state.retry_at),
                state=SyncState.BLOCKED,
                code=S.PROVIDER_COOLDOWN,
                retryable=C.TRUE,
            )
        if self.requests >= self._limit:
            self._save_state(
                host,
                replace(
                    state,
                    status_code=C.NONE,
                    headers={},
                    error_code=S.REQUEST_BUDGET_EXHAUSTED,
                ),
            )
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
        host = urlsplit(url).hostname or S.EMPTY
        self._throttle(host)
        state = self._state(host)
        state = replace(
            state,
            wire_attempts=state.wire_attempts + C.ONE,
            status_code=C.NONE,
            headers={},
            error_code=S.DR_REQUEST_PENDING,
            retry_at=self._wall_clock() + max(self._timeout, self._backoff(state.failures)),
        )
        self._save_state(host, state)
        try:
            with self._client.stream(
                S.GET, url, headers=headers, timeout=self._timeout, follow_redirects=C.FALSE
            ) as response:
                safe_headers = self._safe_headers(response.headers, url, headers)
                state = replace(state, status_code=response.status_code, headers=safe_headers)
                if response.status_code in C.NET_RETRYABLE:
                    delay = self._retry_delay(safe_headers.get(S.RETRY_AFTER), state.failures)
                    deadline = self._wall_clock() + delay
                    if not math.isfinite(deadline):
                        deadline = self._wall_clock() + self._backoff(state.failures)
                    state = replace(
                        state,
                        retry_at=deadline,
                        failures=state.failures + C.ONE,
                        error_code=S.DR_HTTP_RETRYABLE,
                    )
                self._save_state(host, state)
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
                    headers=safe_headers,
                    body=S.EMPTY_BYTES.join(parts),
                )
                return (result, response.headers.get(S.LOCATION))
        except httpx.TimeoutException:
            error = ConnectorError(
                S.NET_HTTPCLIENT_REQUEST_THE_SOURCE_REQUEST_TIMED_OUT,
                code=S.REQUEST_TIMEOUT,
                retryable=C.TRUE,
            )
            self._record_error(host, error)
            raise error from C.NONE
        except (
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.ProxyError,
            httpx.DecodingError,
        ):
            error = ConnectorError(
                S.NET_HTTPCLIENT_REQUEST_THE_SOURCE_CONNECTION_FAILED,
                code=S.NETWORK_ERROR,
                retryable=C.TRUE,
            )
            self._record_error(host, error)
            raise error from C.NONE
        except ConnectorError as error:
            self._record_error(host, error)
            raise

    @staticmethod
    def _safe_headers(
        response: Mapping[str, str], url: str, headers: Mapping[str, str] | None
    ) -> dict[str, str]:
        values = [
            value
            for name, value in parse_qsl(urlsplit(url).query)
            if C.RAW_SECRET_NAME_PATTERN.sub(S.EMPTY, name.casefold()).endswith(
                C.RAW_SECRET_NAME_SUFFIXES
            )
        ]
        for name, value in (headers or {}).items():
            if not C.RAW_SECRET_NAME_PATTERN.sub(S.EMPTY, name.casefold()).endswith(
                C.RAW_SECRET_NAME_SUFFIXES
            ):
                continue
            values.extend(value.split())
            tokens = value.split(maxsplit=C.ONE)
            if (
                S.RAW_AUTHORIZATION in name.casefold()
                and len(tokens) == C.TWO
                and tokens[C.ZERO].casefold() == S.RAW_BASIC
            ):
                try:
                    decoded = base64.b64decode(tokens[C.ONE], validate=C.TRUE).decode(S.UTF_8)
                except (ValueError, UnicodeError):
                    pass
                else:
                    values.extend(decoded.partition(S.COLON))
            values.extend(
                item.partition(S.RAW_EQUALS)[C.TWO].strip().strip(S.RAW_QUOTES)
                for item in value.split(S.RAW_SEMICOLON)
            )
        secrets = {
            variant
            for value in values
            if value and value != S.COLON
            for variant in (
                value,
                unquote_plus(value),
                quote(value, safe=S.EMPTY),
                quote_plus(value, safe=S.EMPTY),
                html.escape(value),
                json.dumps(value, ensure_ascii=C.TRUE)[C.ONE : -C.ONE],
            )
        }
        return {
            name.lower(): value
            for name, value in response.items()
            if name.lower() in C.NET_SAFE_HEADERS
            and not any(secret in value or secret in unquote_plus(value) for secret in secrets)
        }

    @staticmethod
    def _backoff(failures: int) -> float:
        return float(C.TWO ** min(failures, C.DR_BACKOFF_EXPONENT_LIMIT))

    def _record_error(self, host: str, error: ConnectorError) -> None:
        state = self._state(host)
        delay = self._backoff(state.failures)
        deadline = self._wall_clock() + delay
        if state.error_code == S.DR_HTTP_RETRYABLE:
            deadline = max(state.retry_at or C.ZERO, deadline)
        self._save_state(
            host,
            replace(
                state,
                failures=state.failures + (state.error_code != S.DR_HTTP_RETRYABLE),
                retry_at=deadline,
                error_code=error.code,
            ),
        )

    def _retry_delay(self, value: str | None, attempt: int) -> float:
        if value is not C.NONE:
            if value.strip().isdigit():
                try:
                    delay = float(value)
                    if math.isfinite(delay):
                        return delay
                except (ValueError, OverflowError):
                    pass
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is C.NONE:
                    parsed = parsed.replace(tzinfo=UTC)
                return max(C.ZERO, parsed.timestamp() - self._wall_clock())
            except (TypeError, ValueError, OverflowError, OSError):
                pass
        return self._backoff(attempt)

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
                        if exc.retryable and exc.code != S.REQUEST_BUDGET_EXHAUSTED:
                            host = urlsplit(request_url).hostname or S.EMPTY
                            state = self._state(host)
                            self._cooldowns[host] = self._clock() + max(
                                C.ZERO, (state.retry_at or C.ZERO) - self._wall_clock()
                            )
                        raise
                    state = self._state(urlsplit(request_url).hostname or S.EMPTY)
                    self._sleep(max(C.ZERO, (state.retry_at or C.ZERO) - self._wall_clock()))
                    continue
                host = urlsplit(request_url).hostname or S.EMPTY
                state = self._state(host)
                if result.status_code not in C.NET_RETRYABLE:
                    self._save_state(
                        host,
                        replace(
                            state,
                            retry_at=C.NONE,
                            failures=C.ZERO,
                            error_code=C.NONE,
                        ),
                    )
                    break
                delay = max(C.ZERO, (state.retry_at or C.ZERO) - self._wall_clock())
                if attempt + C.ONE == self._attempts or delay > C.NET_HTTPCLIENT_FETCH:
                    self._cooldowns[host] = self._clock() + delay
                    break
                self._sleep(delay)
            if result is C.NONE:
                raise ConnectorError(
                    S.NET_HTTPCLIENT_FETCH_SOURCE_REQUEST_DID_NOT_RETURN_A_RESPONSE,
                    code=S.NO_RESPONSE,
                )
            if result.status_code not in C.NET_REDIRECTS:
                state = self._state(urlsplit(request_url).hostname or S.EMPTY)
                return replace(
                    result,
                    retry_at=state.retry_at,
                    wire_attempts=state.wire_attempts,
                    error_code=state.error_code,
                )
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
