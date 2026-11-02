from __future__ import annotations

import base64
import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters import google_oauth
from bookystats.adapters.google_oauth import Credentials
from bookystats.adapters.http import HttpClient
from bookystats.domain.errors import ConfigurationError


def credentials(expiry: float = C.ZERO) -> Credentials:
    return Credentials(
        S.OAUTH_TEST_CLIENT_ID,
        S.OAUTH_TEST_CLIENT_SECRET,
        S.OAUTH_TEST_ACCESS_TOKEN,
        S.OAUTH_TEST_REFRESH_TOKEN,
        expiry,
    )


def token_response(refresh: bool = C.TRUE) -> dict[str, object]:
    result: dict[str, object] = {
        S.OAUTH_ACCESS_TOKEN: S.OAUTH_TEST_NEW_ACCESS_TOKEN,
        S.OAUTH_TOKEN_TYPE: S.OAUTH_BEARER,
        S.OAUTH_EXPIRES_IN: C.OAUTH_TEST_TOKEN_LIFETIME,
        S.OAUTH_SCOPE: S.OAUTH_BOOKS_SCOPE,
    }
    if refresh:
        result[S.OAUTH_REFRESH_TOKEN] = S.OAUTH_TEST_REFRESH_TOKEN
    return result


@pytest.mark.parametrize(S.OAUTH_TEST_CALLBACK_PARAMETER, C.OAUTH_TEST_INVALID_CALLBACKS)
def test_callback_rejects_state_denial_duplicates_and_wrong_path(path: str) -> None:
    with pytest.raises(ConfigurationError, match=S.OAUTH_TEST_FAILURE_MATCH):
        google_oauth._callback_code(path, S.OAUTH_TEST_STATE)


def test_authorization_binds_state_and_pkce_and_persists_only_private_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(S.OAUTH_CLIENT_ID_ENV, S.OAUTH_TEST_CLIENT_ID)
    monkeypatch.setenv(S.OAUTH_CLIENT_SECRET_ENV, S.OAUTH_TEST_CLIENT_SECRET)
    authorization: dict[str, list[str]] = {}

    def receive(
        url: str, state: str, port: int, *, browser_open: Callable[[str], bool], timeout: float
    ) -> str:
        parsed = urlsplit(url)
        assert parsed.scheme == S.HTTPS
        assert parsed.hostname == urlsplit(S.OAUTH_AUTHORIZATION_ENDPOINT).hostname
        authorization.update(parse_qs(parsed.query))
        assert authorization[S.OAUTH_STATE] == [state]
        assert authorization[S.OAUTH_CODE_CHALLENGE_METHOD] == [S.OAUTH_S256]
        assert authorization[S.OAUTH_SCOPE] == [S.OAUTH_BOOKS_SCOPE]
        assert authorization[S.OAUTH_ACCESS_TYPE] == [S.OAUTH_OFFLINE]
        assert S.OAUTH_TEST_CLIENT_SECRET not in url
        path = (
            S.OAUTH_CALLBACK_PATH
            + S.OAUTH_QUERY_SEPARATOR
            + urlencode({S.OAUTH_STATE: state, S.OAUTH_CODE: S.OAUTH_TEST_CODE})
        )
        return google_oauth._callback_code(path, state)

    def exchange(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == S.OAUTH_TOKEN_ENDPOINT
        fields = parse_qs(request.content.decode())
        verifier = fields[S.OAUTH_CODE_VERIFIER][C.ZERO]
        assert len(verifier) >= C.OAUTH_TEST_VERIFIER_MINIMUM
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(S.OAUTH_BASE64_PADDING)
            .decode(S.OAUTH_ASCII)
        )
        assert authorization[S.OAUTH_CODE_CHALLENGE] == [challenge]
        assert fields[S.OAUTH_CODE] == [S.OAUTH_TEST_CODE]
        assert fields[S.OAUTH_CLIENT_SECRET] == [S.OAUTH_TEST_CLIENT_SECRET]
        assert fields[S.OAUTH_REDIRECT_URI_KEY] == authorization[S.OAUTH_REDIRECT_URI_KEY]
        return httpx.Response(C.OAUTH_HTTP_OK, json=token_response())

    monkeypatch.setattr(google_oauth, S.OAUTH_TEST_RECEIVE_ATTRIBUTE, receive)
    with httpx.Client(transport=httpx.MockTransport(exchange)) as client:
        google_oauth.authorize(tmp_path, client=client, clock=lambda: C.OAUTH_TEST_NOW)
    stored = google_oauth._load(tmp_path)
    assert stored is not C.NONE
    assert stored.access_token == S.OAUTH_TEST_NEW_ACCESS_TOKEN
    assert stored.expires_at == C.OAUTH_TEST_NOW + C.OAUTH_TEST_TOKEN_LIFETIME
    assert list(tmp_path.iterdir()) == [tmp_path / S.OAUTH_FILE]
    assert S.OAUTH_TEST_ACCESS_TOKEN not in repr(stored)
    assert S.OAUTH_TEST_CLIENT_SECRET not in repr(stored)


def test_expired_token_refreshes_without_browser_and_retains_refresh_token(
    tmp_path: Path,
) -> None:
    google_oauth._save(tmp_path, credentials())
    requests: list[httpx.Request] = []

    def exchange(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert str(request.url) == S.OAUTH_TOKEN_ENDPOINT
        fields = parse_qs(request.content.decode())
        assert fields[S.OAUTH_GRANT_TYPE] == [S.OAUTH_REFRESH_TOKEN]
        assert fields[S.OAUTH_REFRESH_TOKEN] == [S.OAUTH_TEST_REFRESH_TOKEN]
        assert S.OAUTH_CODE not in fields
        return httpx.Response(C.OAUTH_HTTP_OK, json=token_response(refresh=C.FALSE))

    with httpx.Client(transport=httpx.MockTransport(exchange)) as client:
        assert (
            google_oauth.ensure_access_token(
                tmp_path,
                interactive=C.FALSE,
                client=client,
                clock=lambda: C.OAUTH_TEST_NOW,
                prompt=no_prompt,
                browser_open=no_browser,
            )
            == S.OAUTH_TEST_NEW_ACCESS_TOKEN
        )
        assert (
            google_oauth.ensure_access_token(
                tmp_path,
                interactive=C.FALSE,
                client=client,
                clock=lambda: C.OAUTH_TEST_NOW,
                prompt=no_prompt,
                browser_open=no_browser,
            )
            == S.OAUTH_TEST_NEW_ACCESS_TOKEN
        )
    assert len(requests) == C.ONE
    stored = google_oauth._load(tmp_path)
    assert stored is not C.NONE
    assert stored.refresh_token == S.OAUTH_TEST_REFRESH_TOKEN


def test_failed_refresh_does_not_replace_credentials_or_leak_provider_errors(
    tmp_path: Path,
) -> None:
    google_oauth._save(tmp_path, credentials())
    original = (tmp_path / S.OAUTH_FILE).read_bytes()

    def exchange(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            C.OAUTH_HTTP_BAD_REQUEST,
            json={S.OAUTH_ERROR: S.OAUTH_TEST_CLIENT_SECRET},
        )

    with (
        httpx.Client(transport=httpx.MockTransport(exchange)) as client,
        pytest.raises(ConfigurationError) as failure,
    ):
        google_oauth.access_token(tmp_path, client=client)
    assert str(failure.value) == S.OAUTH_FAILURE
    assert S.OAUTH_TEST_CLIENT_SECRET not in str(failure.value)
    assert (tmp_path / S.OAUTH_FILE).read_bytes() == original


def test_token_redirect_is_not_followed(tmp_path: Path) -> None:
    google_oauth._save(tmp_path, credentials())
    requests: list[httpx.Request] = []

    def exchange(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            C.OAUTH_TEST_HTTP_REDIRECT,
            headers={S.LOCATION: S.OAUTH_TEST_OTHER_URL},
        )

    with (
        httpx.Client(transport=httpx.MockTransport(exchange), follow_redirects=C.TRUE) as client,
        pytest.raises(ConfigurationError),
    ):
        google_oauth.access_token(tmp_path, client=client)
    assert len(requests) == C.ONE


def test_callback_listener_browser_failure_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    class Server:
        def __init__(self, address: tuple[str, int], handler: object) -> None:
            assert address == (S.OAUTH_LOOPBACK_HOST, C.OAUTH_LOOPBACK_PORT)

        def __enter__(self) -> Server:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(google_oauth, S.OAUTH_TEST_SERVER_ATTRIBUTE, Server)
    with pytest.raises(ConfigurationError) as failure:
        google_oauth._receive_code(
            S.OAUTH_AUTHORIZATION_ENDPOINT,
            S.OAUTH_TEST_STATE,
            C.OAUTH_LOOPBACK_PORT,
            browser_open=lambda url: C.FALSE,
            timeout=C.ONE,
        )
    assert str(failure.value) == S.OAUTH_FAILURE


def test_listener_wait_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter(C.OAUTH_TEST_DEADLINE_TIMES)

    class Server:
        timeout = C.ZERO

        def __init__(self, address: tuple[str, int], handler: object) -> None:
            pass

        def __enter__(self) -> Server:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def handle_request(self) -> None:
            assert self.timeout <= C.OAUTH_POLL_INTERVAL

    monkeypatch.setattr(google_oauth, S.OAUTH_TEST_SERVER_ATTRIBUTE, Server)
    monkeypatch.setattr(time, S.OAUTH_TEST_MONOTONIC_ATTRIBUTE, lambda: next(times))
    with pytest.raises(ConfigurationError):
        google_oauth._receive_code(
            S.OAUTH_AUTHORIZATION_ENDPOINT,
            S.OAUTH_TEST_STATE,
            C.OAUTH_LOOPBACK_PORT,
            browser_open=lambda url: C.TRUE,
            timeout=C.ONE,
        )


def test_bearer_header_is_removed_on_cross_host_redirect() -> None:
    requests: list[httpx.Request] = []

    def exchange(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == C.ONE:
            return httpx.Response(
                C.OAUTH_TEST_HTTP_REDIRECT,
                headers={S.LOCATION: S.OAUTH_TEST_OTHER_URL},
            )
        return httpx.Response(C.OAUTH_HTTP_OK)

    with (
        httpx.Client(transport=httpx.MockTransport(exchange)) as client,
        HttpClient(
            allowed_hosts=(S.WWW_GOOGLEAPIS_COM, S.OPENLIBRARY_ORG),
            client=client,
            min_interval=C.ZERO,
        ) as transport,
    ):
        transport.fetch(
            S.GOOGLE_BOOKS_ENDPOINT_HTTPS_WWW_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES,
            headers={
                S.OAUTH_AUTHORIZATION_HEADER: S.OAUTH_BEARER_HEADER.format(
                    token=S.OAUTH_TEST_ACCESS_TOKEN
                )
            },
        )
    assert S.OAUTH_AUTHORIZATION_HEADER in requests[C.ZERO].headers
    assert S.OAUTH_AUTHORIZATION_HEADER not in requests[C.ONE].headers


def no_prompt(message: str) -> str:
    pytest.fail(S.OAUTH_TEST_UNAVAILABLE_PROMPT)


def no_browser(url: str) -> bool:
    pytest.fail(S.OAUTH_TEST_UNAVAILABLE_BROWSER)


def install_consent_receiver(monkeypatch: pytest.MonkeyPatch) -> None:
    def receive(
        url: str, state: str, port: int, *, browser_open: Callable[[str], bool], timeout: float
    ) -> str:
        assert parse_qs(urlsplit(url).query)[S.OAUTH_STATE] == [state]
        assert browser_open(url)
        return S.OAUTH_TEST_CODE

    monkeypatch.setattr(google_oauth, S.OAUTH_TEST_RECEIVE_ATTRIBUTE, receive)


@pytest.mark.parametrize(S.OAUTH_TEST_ENVIRONMENT_PARAMETER, C.OAUTH_TEST_INTERACTIVITY)
def test_first_interactive_sync_authorizes_using_hidden_prompt_or_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, use_environment: bool
) -> None:
    for key, value in (
        (S.OAUTH_CLIENT_ID_ENV, S.OAUTH_TEST_CLIENT_ID),
        (S.OAUTH_CLIENT_SECRET_ENV, S.OAUTH_TEST_CLIENT_SECRET),
    ):
        if use_environment:
            monkeypatch.setenv(key, value)
        else:
            monkeypatch.delenv(key, raising=C.FALSE)
    prompts: list[str] = []
    browsers: list[str] = []

    def prompt(message: str) -> str:
        prompts.append(message)
        if message == S.OAUTH_CLIENT_ID_PROMPT:
            return S.OAUTH_TEST_CLIENT_ID
        assert message == S.OAUTH_CLIENT_SECRET_PROMPT
        return S.OAUTH_TEST_CLIENT_SECRET

    def browser(url: str) -> bool:
        browsers.append(url)
        return C.TRUE

    def exchange(request: httpx.Request) -> httpx.Response:
        assert parse_qs(request.content.decode())[S.OAUTH_GRANT_TYPE] == [
            S.OAUTH_AUTHORIZATION_CODE
        ]
        return httpx.Response(C.OAUTH_HTTP_OK, json=token_response())

    install_consent_receiver(monkeypatch)
    with httpx.Client(transport=httpx.MockTransport(exchange)) as client:
        assert (
            google_oauth.ensure_access_token(
                tmp_path,
                interactive=C.TRUE,
                client=client,
                prompt=no_prompt if use_environment else prompt,
                browser_open=browser,
                clock=lambda: C.OAUTH_TEST_NOW,
            )
            == S.OAUTH_TEST_NEW_ACCESS_TOKEN
        )
    assert len(browsers) == C.ONE
    assert prompts == (
        [] if use_environment else [S.OAUTH_CLIENT_ID_PROMPT, S.OAUTH_CLIENT_SECRET_PROMPT]
    )
    stored = google_oauth._load(tmp_path)
    assert stored is not C.NONE
    assert stored.access_token == S.OAUTH_TEST_NEW_ACCESS_TOKEN


@pytest.mark.parametrize(S.OAUTH_TEST_INTERACTIVE_PARAMETER, C.OAUTH_TEST_INTERACTIVITY)
def test_ensure_reuses_stored_token_without_network_prompt_or_browser(
    tmp_path: Path, interactive: bool
) -> None:
    google_oauth._save(tmp_path, credentials(C.OAUTH_TEST_TOKEN_LIFETIME))

    def exchange(request: httpx.Request) -> httpx.Response:
        pytest.fail(S.OAUTH_FAILURE)

    with httpx.Client(transport=httpx.MockTransport(exchange)) as client:
        assert (
            google_oauth.ensure_access_token(
                tmp_path,
                interactive=interactive,
                client=client,
                prompt=no_prompt,
                browser_open=no_browser,
                clock=lambda: C.OAUTH_TEST_NOW,
            )
            == S.OAUTH_TEST_ACCESS_TOKEN
        )


def test_headless_missing_credentials_never_opens_browser_or_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(S.OAUTH_CLIENT_ID_ENV, S.OAUTH_TEST_CLIENT_ID)
    monkeypatch.setenv(S.OAUTH_CLIENT_SECRET_ENV, S.OAUTH_TEST_CLIENT_SECRET)
    assert (
        google_oauth.ensure_access_token(
            tmp_path, interactive=C.FALSE, prompt=no_prompt, browser_open=no_browser
        )
        is C.NONE
    )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(S.OAUTH_TEST_INTERACTIVE_PARAMETER, C.OAUTH_TEST_INTERACTIVITY)
def test_invalid_refresh_grant_reauthorizes_only_interactively(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interactive: bool
) -> None:
    google_oauth._save(tmp_path, credentials())
    original = (tmp_path / S.OAUTH_FILE).read_bytes()
    monkeypatch.delenv(S.OAUTH_CLIENT_ID_ENV, raising=C.FALSE)
    monkeypatch.delenv(S.OAUTH_CLIENT_SECRET_ENV, raising=C.FALSE)
    requests: list[httpx.Request] = []
    browsers: list[str] = []

    def browser(url: str) -> bool:
        browsers.append(url)
        return C.TRUE

    def exchange(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        fields = parse_qs(request.content.decode())
        assert fields[S.OAUTH_CLIENT_ID] == [S.OAUTH_TEST_CLIENT_ID]
        assert fields[S.OAUTH_CLIENT_SECRET] == [S.OAUTH_TEST_CLIENT_SECRET]
        if fields[S.OAUTH_GRANT_TYPE] == [S.OAUTH_REFRESH_TOKEN]:
            return httpx.Response(
                C.OAUTH_HTTP_BAD_REQUEST, json={S.OAUTH_ERROR: S.OAUTH_INVALID_GRANT}
            )
        assert interactive
        assert fields[S.OAUTH_GRANT_TYPE] == [S.OAUTH_AUTHORIZATION_CODE]
        return httpx.Response(C.OAUTH_HTTP_OK, json=token_response())

    install_consent_receiver(monkeypatch)
    with httpx.Client(transport=httpx.MockTransport(exchange)) as client:
        if interactive:
            assert (
                google_oauth.ensure_access_token(
                    tmp_path,
                    interactive=interactive,
                    client=client,
                    prompt=no_prompt,
                    browser_open=browser,
                    clock=lambda: C.OAUTH_TEST_NOW,
                )
                == S.OAUTH_TEST_NEW_ACCESS_TOKEN
            )
            assert len(requests) == C.TWO
            assert len(browsers) == C.ONE
        else:
            with pytest.raises(google_oauth.AuthorizationRequired) as failure:
                google_oauth.ensure_access_token(
                    tmp_path,
                    interactive=interactive,
                    client=client,
                    prompt=no_prompt,
                    browser_open=no_browser,
                )
            assert str(failure.value) == S.OAUTH_AUTHORIZATION_REQUIRED
            assert len(requests) == C.ONE
            assert (tmp_path / S.OAUTH_FILE).read_bytes() == original


@pytest.mark.parametrize(S.OAUTH_TEST_REFRESH_FAILURE_PARAMETER, C.OAUTH_TEST_REFRESH_FAILURES)
def test_refresh_failure_does_not_trigger_consent_or_replace_credentials(
    tmp_path: Path, failure_mode: str
) -> None:
    google_oauth._save(tmp_path, credentials())
    original = (tmp_path / S.OAUTH_FILE).read_bytes()

    def exchange(request: httpx.Request) -> httpx.Response:
        if failure_mode == S.OAUTH_TEST_REFRESH_FAILURE_NETWORK:
            raise httpx.ConnectError(S.OAUTH_TEST_CLIENT_SECRET)
        if failure_mode == S.OAUTH_TEST_REFRESH_FAILURE_SERVER:
            return httpx.Response(
                C.OAUTH_TEST_HTTP_UNAVAILABLE, json={S.OAUTH_ERROR: S.OAUTH_INVALID_GRANT}
            )
        if failure_mode == S.OAUTH_TEST_REFRESH_FAILURE_BAD_BODY:
            return httpx.Response(
                C.OAUTH_HTTP_BAD_REQUEST, content=S.OAUTH_TEST_DAMAGED_CREDENTIALS
            )
        if failure_mode == S.OAUTH_TEST_REFRESH_FAILURE_BAD_STATUS:
            return httpx.Response(C.OAUTH_HTTP_OK, json={S.OAUTH_ERROR: S.OAUTH_INVALID_GRANT})
        return httpx.Response(
            C.OAUTH_HTTP_BAD_REQUEST, json={S.OAUTH_ERROR: S.OAUTH_TEST_CLIENT_SECRET}
        )

    with (
        httpx.Client(transport=httpx.MockTransport(exchange)) as client,
        pytest.raises(ConfigurationError) as failure,
    ):
        google_oauth.ensure_access_token(
            tmp_path,
            interactive=C.TRUE,
            client=client,
            prompt=no_prompt,
            browser_open=no_browser,
        )
    assert not isinstance(failure.value, google_oauth.AuthorizationRequired)
    assert str(failure.value) == S.OAUTH_FAILURE
    assert (tmp_path / S.OAUTH_FILE).read_bytes() == original


@pytest.mark.parametrize(S.OAUTH_TEST_INTERACTIVE_PARAMETER, C.OAUTH_TEST_INTERACTIVITY)
def test_damaged_saved_credentials_fail_visibly_without_reauthorization(
    tmp_path: Path, interactive: bool
) -> None:
    path = tmp_path / S.OAUTH_FILE
    path.write_text(S.OAUTH_TEST_DAMAGED_CREDENTIALS, encoding=S.UTF_8)
    original = path.read_bytes()
    with pytest.raises(ConfigurationError):
        google_oauth.ensure_access_token(
            tmp_path, interactive=interactive, prompt=no_prompt, browser_open=no_browser
        )
    assert path.read_bytes() == original
