from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import math
import os
import secrets
import sys
import time
import warnings
import webbrowser
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import validate_source_url
from bookystats.domain.errors import ConfigurationError
from bookystats.runtime.config import atomic_write
from bookystats.runtime.layout import google_credentials_path


@C.oauth_credentials_dataclass
class Credentials:
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    expires_at: float


class AuthorizationRequired(ConfigurationError):
    pass


def _failure() -> ConfigurationError:
    return ConfigurationError(S.OAUTH_FAILURE)


def _text(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or not value.isascii()
        or any(character.isspace() for character in value)
    ):
        raise _failure()
    return value


def _bearer(value: object) -> str:
    token = _text(value)
    if not C.OAUTH_BEARER_PATTERN.fullmatch(token):
        raise _failure()
    return token


def _save(directory: Path, credentials: Credentials) -> None:
    atomic_write(
        google_credentials_path(directory),
        json.dumps(
            {
                S.OAUTH_CLIENT_ID: credentials.client_id,
                S.OAUTH_CLIENT_SECRET: credentials.client_secret,
                S.OAUTH_ACCESS_TOKEN: credentials.access_token,
                S.OAUTH_REFRESH_TOKEN: credentials.refresh_token,
                S.OAUTH_EXPIRES_AT: credentials.expires_at,
            }
        )
        + S.NEWLINE,
    )


def _load(directory: Path) -> Credentials | None:
    path = google_credentials_path(directory)
    try:
        content = path.read_text(encoding=S.UTF_8)
    except FileNotFoundError:
        return C.NONE
    except (OSError, UnicodeError):
        raise _failure() from C.NONE
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            raise _failure()
        expiry = data[S.OAUTH_EXPIRES_AT]
        if type(expiry) not in (int, float) or not math.isfinite(expiry):
            raise _failure()
        return Credentials(
            client_id=_text(data[S.OAUTH_CLIENT_ID]),
            client_secret=_text(data[S.OAUTH_CLIENT_SECRET]),
            access_token=_bearer(data[S.OAUTH_ACCESS_TOKEN]),
            refresh_token=_text(data[S.OAUTH_REFRESH_TOKEN]),
            expires_at=float(expiry),
        )
    except (KeyError, ValueError, TypeError, OverflowError):
        raise _failure() from C.NONE


def _token_request(
    fields: Mapping[str, str], client: httpx.Client | None = C.NONE
) -> dict[str, object]:
    validate_source_url(S.OAUTH_TOKEN_ENDPOINT, C.OAUTH_TOKEN_HOSTS)
    owned = client is C.NONE
    transport = client or httpx.Client(follow_redirects=C.FALSE, trust_env=C.FALSE)
    try:
        with transport.stream(
            S.OAUTH_POST,
            S.OAUTH_TOKEN_ENDPOINT,
            data=fields,
            timeout=C.OAUTH_HTTP_TIMEOUT,
            follow_redirects=C.FALSE,
        ) as response:
            body = bytearray()
            for part in response.iter_bytes():
                body.extend(part)
                if len(body) > C.OAUTH_MAX_TOKEN_RESPONSE:
                    raise _failure()
            data = json.loads(body)
            if not isinstance(data, dict):
                raise _failure()
            if response.status_code != C.OAUTH_HTTP_OK:
                if (
                    response.status_code == C.OAUTH_HTTP_BAD_REQUEST
                    and fields.get(S.OAUTH_GRANT_TYPE) == S.OAUTH_REFRESH_TOKEN
                    and data.get(S.OAUTH_ERROR) == S.OAUTH_INVALID_GRANT
                ):
                    raise AuthorizationRequired(S.OAUTH_AUTHORIZATION_REQUIRED)
                raise _failure()
            if data.get(S.OAUTH_TOKEN_TYPE) != S.OAUTH_BEARER:
                raise _failure()
            scope = data.get(S.OAUTH_SCOPE)
            if scope is not C.NONE and (
                not isinstance(scope, str) or S.OAUTH_BOOKS_SCOPE not in scope.split()
            ):
                raise _failure()
            return data
    except (httpx.HTTPError, ValueError, UnicodeError):
        raise _failure() from C.NONE
    finally:
        if owned:
            transport.close()


def _credentials(
    data: dict[str, object],
    client_id: str,
    client_secret: str,
    now: float,
    refresh_token: str | None = C.NONE,
) -> Credentials:
    expiry = data.get(S.OAUTH_EXPIRES_IN)
    if (
        type(expiry) not in (int, float)
        or not isinstance(expiry, (int, float))
        or not math.isfinite(expiry)
        or expiry <= C.OAUTH_EXPIRY_MARGIN
    ):
        raise _failure()
    expires_at = now + expiry
    if not math.isfinite(expires_at):
        raise _failure()
    return Credentials(
        client_id=client_id,
        client_secret=client_secret,
        access_token=_bearer(data.get(S.OAUTH_ACCESS_TOKEN)),
        refresh_token=_text(data.get(S.OAUTH_REFRESH_TOKEN, refresh_token)),
        expires_at=expires_at,
    )


def access_token(
    directory: Path,
    *,
    client: httpx.Client | None = C.NONE,
    clock: Callable[[], float] = time.time,
) -> str | None:
    credentials = _load(directory)
    if credentials is C.NONE:
        return C.NONE
    if credentials.expires_at > clock() + C.OAUTH_EXPIRY_MARGIN:
        return credentials.access_token
    data = _token_request(
        {
            S.OAUTH_GRANT_TYPE: S.OAUTH_REFRESH_TOKEN,
            S.OAUTH_REFRESH_TOKEN: credentials.refresh_token,
            S.OAUTH_CLIENT_ID: credentials.client_id,
            S.OAUTH_CLIENT_SECRET: credentials.client_secret,
        },
        client,
    )
    updated = _credentials(
        data,
        credentials.client_id,
        credentials.client_secret,
        clock(),
        credentials.refresh_token,
    )
    _save(directory, updated)
    return updated.access_token


def ensure_access_token(
    directory: Path,
    *,
    interactive: bool,
    client: httpx.Client | None = C.NONE,
    clock: Callable[[], float] = time.time,
    prompt: Callable[[str], str] | None = C.NONE,
    browser_open: Callable[[str], bool] = webbrowser.open,
    port: int = C.OAUTH_LOOPBACK_PORT,
    timeout: float = C.OAUTH_CONSENT_TIMEOUT,
) -> str | None:
    try:
        token = access_token(directory, client=client, clock=clock)
    except AuthorizationRequired:
        if not interactive:
            raise
        token = C.NONE
    if token is not C.NONE or not interactive:
        return token
    saved = _load(directory)
    authorize(
        directory,
        client=client,
        browser_open=browser_open,
        port=port,
        timeout=timeout,
        clock=clock,
        prompt=prompt,
        client_id=saved.client_id if saved is not C.NONE else C.NONE,
        client_secret=saved.client_secret if saved is not C.NONE else C.NONE,
    )
    return access_token(directory, client=client, clock=clock)


def _callback_code(path: str, state: str) -> str:
    parsed = urlsplit(path)
    query = parse_qs(parsed.query, keep_blank_values=C.TRUE)
    supplied = query.get(S.OAUTH_STATE, [])
    code = query.get(S.OAUTH_CODE, [])
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or parsed.path != S.OAUTH_CALLBACK_PATH
        or len(path) > C.OAUTH_MAX_CALLBACK
        or len(supplied) != C.ONE
        or not hmac.compare_digest(supplied[C.ZERO].encode(), state.encode())
        or S.OAUTH_ERROR in query
        or len(code) != C.ONE
    ):
        raise _failure()
    return _text(code[C.ZERO])


def _receive_code(
    authorization_url: str,
    state: str,
    port: int,
    *,
    browser_open: Callable[[str], bool],
    timeout: float,
) -> str:
    code: str | None = C.NONE
    failed = C.FALSE
    expected_host = S.OAUTH_LOOPBACK_AUTHORITY.format(port=port)

    class Callback(BaseHTTPRequestHandler):
        def setup(self) -> None:
            self.request.settimeout(C.OAUTH_SOCKET_TIMEOUT)
            super().setup()

        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            nonlocal code, failed
            try:
                if self.headers.get(S.OAUTH_HOST_HEADER) != expected_host:
                    raise _failure()
                code = _callback_code(self.path, state)
            except (ConfigurationError, ValueError, UnicodeError):
                failed = C.TRUE
            try:
                self.send_response(C.OAUTH_HTTP_BAD_REQUEST if failed else C.OAUTH_HTTP_OK)
                self.send_header(S.CONTENT_TYPE, S.OAUTH_CALLBACK_CONTENT_TYPE)
                self.send_header(S.OAUTH_CACHE_CONTROL, S.OAUTH_NO_STORE)
                self.end_headers()
                self.wfile.write(S.OAUTH_CALLBACK_BODY)
            except OSError:
                pass

    try:
        with ThreadingHTTPServer((S.OAUTH_LOOPBACK_HOST, port), Callback) as server:
            deadline = time.monotonic() + timeout
            if not browser_open(authorization_url):
                raise _failure()
            while code is C.NONE and not failed:
                remaining = deadline - time.monotonic()
                if remaining <= C.ZERO:
                    raise _failure()
                server.timeout = min(remaining, C.OAUTH_POLL_INTERVAL)
                server.handle_request()
    except (OSError, webbrowser.Error):
        raise _failure() from C.NONE
    if failed or code is C.NONE:
        raise _failure()
    return code


def authorize(
    directory: Path,
    *,
    client: httpx.Client | None = C.NONE,
    browser_open: Callable[[str], bool] = webbrowser.open,
    port: int = C.OAUTH_LOOPBACK_PORT,
    timeout: float = C.OAUTH_CONSENT_TIMEOUT,
    clock: Callable[[], float] = time.time,
    prompt: Callable[[str], str] | None = C.NONE,
    client_id: str | None = C.NONE,
    client_secret: str | None = C.NONE,
) -> None:
    if not (C.ZERO < port <= C.OAUTH_MAX_PORT) or not (C.ZERO < timeout <= C.OAUTH_CONSENT_TIMEOUT):
        raise _failure()
    client_id = client_id or os.environ.get(S.OAUTH_CLIENT_ID_ENV, S.EMPTY).strip()
    client_secret = client_secret or os.environ.get(S.OAUTH_CLIENT_SECRET_ENV, S.EMPTY).strip()
    if not client_id or not client_secret:
        if prompt is C.NONE and not sys.stdin.isatty():
            raise ConfigurationError(S.OAUTH_SETUP_REQUIRED)
        read_secret = prompt or getpass.getpass
        try:
            with warnings.catch_warnings():
                warnings.simplefilter(S.OAUTH_WARNING_ERROR, getpass.GetPassWarning)
                client_id = client_id or read_secret(S.OAUTH_CLIENT_ID_PROMPT).strip()
                client_secret = client_secret or read_secret(S.OAUTH_CLIENT_SECRET_PROMPT).strip()
        except (getpass.GetPassWarning, EOFError):
            raise ConfigurationError(S.OAUTH_SETUP_REQUIRED) from C.NONE
    client_id, client_secret = _text(client_id), _text(client_secret)
    state = secrets.token_urlsafe(C.OAUTH_RANDOM_BYTES)
    verifier = secrets.token_urlsafe(C.OAUTH_VERIFIER_BYTES)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(S.OAUTH_BASE64_PADDING)
        .decode(S.OAUTH_ASCII)
    )
    redirect_uri = S.OAUTH_REDIRECT_URI.format(port=port)
    authorization_url = (
        S.OAUTH_AUTHORIZATION_ENDPOINT
        + S.OAUTH_QUERY_SEPARATOR
        + urlencode(
            {
                S.OAUTH_CLIENT_ID: client_id,
                S.OAUTH_REDIRECT_URI_KEY: redirect_uri,
                S.OAUTH_RESPONSE_TYPE: S.OAUTH_CODE,
                S.OAUTH_SCOPE: S.OAUTH_BOOKS_SCOPE,
                S.OAUTH_STATE: state,
                S.OAUTH_CODE_CHALLENGE: challenge,
                S.OAUTH_CODE_CHALLENGE_METHOD: S.OAUTH_S256,
                S.OAUTH_ACCESS_TYPE: S.OAUTH_OFFLINE,
                S.OAUTH_PROMPT: S.OAUTH_CONSENT,
            }
        )
    )
    code = _receive_code(authorization_url, state, port, browser_open=browser_open, timeout=timeout)
    data = _token_request(
        {
            S.OAUTH_GRANT_TYPE: S.OAUTH_AUTHORIZATION_CODE,
            S.OAUTH_CODE: code,
            S.OAUTH_CLIENT_ID: client_id,
            S.OAUTH_CLIENT_SECRET: client_secret,
            S.OAUTH_REDIRECT_URI_KEY: redirect_uri,
            S.OAUTH_CODE_VERIFIER: verifier,
        },
        client,
    )
    _save(directory, _credentials(data, client_id, client_secret, clock()))
