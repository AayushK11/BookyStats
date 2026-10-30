from __future__ import annotations

import shutil
import threading
import uuid
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

import bookystats.browser as browser_module
from bookystats import cli
from bookystats import constants as C
from bookystats import strings as S
from bookystats.browser import BrowserClient, BrowserRuntime
from bookystats.config import MetadataSettings, Settings
from bookystats.errors import ConnectorError
from bookystats.models import SyncState
from tests.test_sync import accounts


class FakeError(Exception):
    pass


class FakeTimeout(FakeError):
    pass


class Response:
    def __init__(
        self,
        html=S.TEST_BROWSER_AUTHENTICATED_HTML_NAV_A_HREF_PROFILE_ALICE_YOUR,
        status=C.RESPONSE_INIT_STATUS,
        headers=C.NONE,
    ):
        self.html = html
        self.status = status
        self.headers = headers or {}


class Route:
    def __init__(self, url, response, method=S.GET, main=C.TRUE):
        self.request = SimpleNamespace(
            url=url,
            method=method,
            frame=SimpleNamespace(parent_frame=C.NONE if main else object()),
            is_navigation_request=lambda: main,
        )
        self.response = response
        self.aborted = C.FALSE
        self.continued = C.FALSE
        self.fulfilled = C.FALSE
        self.fetches = []

    def fetch(self, **kwargs):
        self.fetches.append(kwargs)
        return self.response

    def abort(self, _reason):
        self.aborted = C.TRUE

    def continue_(self):
        self.continued = C.TRUE

    def fulfill(self, *, response=C.NONE, status=C.NONE, body=C.NONE):
        if response is C.NONE:
            assert status == C.INTERFACES_PAGEDOCUMENT_STATUS_CODE
            assert body == S.EMPTY
        else:
            assert response is self.response
        self.fulfilled = C.TRUE


class Page:
    def __init__(self, context):
        self.context = context
        self.url = S.PAGE_INIT_ABOUT_BLANK
        self.html = S.EMPTY
        self.gotos = []
        self.waits = []
        self.selectors = []
        self.wait_callback = C.NONE
        self.failure = C.NONE
        self.handlers = {}

    def on(self, name, handler):
        self.handlers[name] = handler

    def goto(self, url, *, wait_until):
        self.gotos.append(url)
        assert wait_until == S.DOMCONTENTLOADED
        if self.failure:
            raise self.failure
        response = self.context.responses[url]
        route = Route(url, response)
        self.context.routes.append(route)
        self.context.guard(route)
        if route.aborted:
            raise FakeError(S.TEST_BROWSER_PAGE_GOTO_HTTPS_EXAMPLE_INVALID_TOKEN_DO_NOT_LOG)
        self.url = url
        self.html = response.html
        return response

    def content(self):
        return self.html

    def wait_for_timeout(self, ms):
        self.waits.append(ms)
        if self.wait_callback:
            self.wait_callback()

    def wait_for_selector(self, selector, *, state):
        self.selectors.append((selector, state))


class Context:
    def __init__(self):
        self.responses = {C.TEST_BROWSER_URL: Response()}
        self.routes = []
        self.guard = C.NONE
        self.page = Page(self)
        self.pages = [self.page]
        self.closed = C.FALSE

    def set_default_timeout(self, _timeout):
        pass

    def set_default_navigation_timeout(self, _timeout):
        pass

    def route(self, _pattern, callback):
        self.guard = callback

    def on(self, _event, _callback):
        pass

    def close(self):
        self.closed = C.TRUE


class Runtime:
    def __init__(self, context):
        self.context = context
        self.launches = []
        self.stopped = C.FALSE
        self.chromium = self
        self.failure = C.NONE

    def launch_persistent_context(self, **kwargs):
        self.launches.append(kwargs)
        if self.failure:
            raise self.failure
        return self.context

    def stop(self):
        self.stopped = C.TRUE


@pytest.fixture
def driver(monkeypatch):
    context = Context()
    runtime = Runtime(context)
    api = SimpleNamespace(
        Error=FakeError,
        TimeoutError=FakeTimeout,
        sync_playwright=lambda: SimpleNamespace(start=lambda: runtime),
    )
    original_import = browser_module.importlib.import_module
    monkeypatch.setattr(
        browser_module.importlib,
        S.IMPORT_MODULE,
        lambda name: api if name == S.PLAYWRIGHT_SYNC_API else original_import(name),
    )
    monkeypatch.setattr(BrowserClient, S.TEST_BROWSER_DRIVER_PREPARE_PROFILE, lambda _self: C.NONE)
    return (context, runtime)


def client(**kwargs):
    return BrowserClient(
        Path(S.TESTS) / S.FIXTURES / S.STORYGRAPH / S.UNUSED_PROFILE,
        allowed_hosts=(S.APP_THESTORYGRAPH_COM,),
        **kwargs,
    )


def test_unused_context_is_lazy_and_creates_no_browser_or_profile(driver) -> None:
    context, runtime = driver
    with client():
        assert not runtime.launches
    assert not runtime.launches
    assert not context.closed
    assert not runtime.stopped


def test_unused_shared_runtime_is_lazy(driver) -> None:
    context, driver_runtime = driver
    with BrowserRuntime() as runtime, client(runtime=runtime):
        assert not driver_runtime.launches
    assert not driver_runtime.stopped
    assert not context.closed


def test_standard_persistent_context_reuses_page_and_has_no_stealth_settings(driver) -> None:
    context, runtime = driver
    with client() as browser:
        first = browser.fetch(C.TEST_BROWSER_URL)
        browser.fetch(C.TEST_BROWSER_URL, wait_for=S.MAIN)
    assert first.html == S.TEST_BROWSER_AUTHENTICATED_HTML_NAV_A_HREF_PROFILE_ALICE_YOUR
    assert len(runtime.launches) == C.ONE
    assert runtime.launches[C.ZERO] == {
        S.USER_DATA_DIR: str(Path(S.TESTS) / S.FIXTURES / S.STORYGRAPH / S.UNUSED_PROFILE),
        S.HEADLESS: C.TRUE,
        S.ACCEPT_DOWNLOADS: C.FALSE,
        S.SERVICE_WORKERS: S.BLOCK,
        S.CHROMIUM_SANDBOX: C.TRUE,
        S.TIMEOUT: C.TEST_BROWSER_STANDARD_PERSISTENT_CONTEXT_AND_HAS_NO_STEALTH_SETTINGS,
    }
    assert context.page.selectors == [(S.MAIN, S.ATTACHED)]
    assert all(
        route.fetches
        == [
            {
                S.MAX_REDIRECTS: C.ZERO,
                S.TIMEOUT: C.TEST_BROWSER_STANDARD_PERSISTENT_CONTEXT_AND_HAS_NO_STEALTH_SETTINGS,
            }
        ]
        for route in context.routes
    )
    assert context.closed and runtime.stopped


@pytest.mark.parametrize(
    S.HTML,
    [
        S.TEST_BROWSER_LOGIN_HTML_FORM_ACTION_USERS_SIGN_IN_INPUT,
        S.TEST_BROWSER_UNATTENDED_AUTH_AND_TITLE_JUST_A_MOMENT_TITLE,
    ],
)
def test_unattended_auth_and_challenges_never_wait_or_prompt(
    driver, monkeypatch, capsys, html
) -> None:
    context, _runtime = driver
    context.responses[C.TEST_BROWSER_URL] = Response(html)
    monkeypatch.setattr(
        S.BUILTINS_INPUT,
        lambda *_args: pytest.fail(
            S.TEST_BROWSER_UNATTENDED_AUTH_AND_PROMPT_NO_CONSOLE_INPUT_PERMITTED
        ),
    )
    with client() as browser, pytest.raises(ConnectorError) as failure:
        browser.fetch(C.TEST_BROWSER_URL, wait_for=S.PRIVATE_CONTENT)
    assert failure.value.state == (
        SyncState.NEEDS_AUTH
        if html == S.TEST_BROWSER_LOGIN_HTML_FORM_ACTION_USERS_SIGN_IN_INPUT
        else SyncState.BLOCKED
    )
    assert not context.page.waits
    assert not context.page.selectors
    assert capsys.readouterr().out == S.EMPTY


def test_interactive_owner_login_is_visible_bounded_and_only_retries_navigation(
    driver, capsys
) -> None:
    context, runtime = driver
    context.responses[C.TEST_BROWSER_URL] = Response(
        S.TEST_BROWSER_LOGIN_HTML_FORM_ACTION_USERS_SIGN_IN_INPUT
    )

    def logged_in():
        context.responses[C.TEST_BROWSER_URL] = Response()
        context.page.url = S.TEST_INTERACTIVE_OWNER_LOGIN_IS_NAVIGATION_LOGGED_IN_TEMPLATE.format(
            v0=C.TEST_BROWSER_ORIGIN
        )
        context.page.html = S.TEST_BROWSER_AUTHENTICATED_HTML_NAV_A_HREF_PROFILE_ALICE_YOUR

    context.page.wait_callback = logged_in
    with client(interactive=C.TRUE) as browser:
        document = browser.fetch(C.TEST_BROWSER_URL)
    assert document.html == S.TEST_BROWSER_AUTHENTICATED_HTML_NAV_A_HREF_PROFILE_ALICE_YOUR
    assert runtime.launches[C.ZERO][S.HEADLESS] is C.FALSE
    assert context.page.gotos == [C.TEST_BROWSER_URL, C.TEST_BROWSER_URL]
    assert len(context.page.waits) == C.ONE
    assert (
        S.TEST_BROWSER_INTERACTIVE_OWNER_NAVIGATION_VISIBLE_SOURCE_BROWSE in capsys.readouterr().out
    )
    assert not browser._login_active


def test_interactive_login_deadline_does_not_turn_into_unbounded_input(driver, monkeypatch) -> None:
    context, _runtime = driver
    context.responses[C.TEST_BROWSER_URL] = Response(
        S.TEST_BROWSER_LOGIN_HTML_FORM_ACTION_USERS_SIGN_IN_INPUT
    )
    clock = iter(
        (
            C.TEST_BROWSER_INTERACTIVE_LOGIN_DEADLINE_INTO_UNBOUNDED_INPUT_CLOCK,
            C.TEST_BROWSER_INTERACTIVE_LOGIN_DEADLINE_INTO_UNBOUNDED_INPUT_CLOCK,
            C.TEST_BROWSER_INTERACTIVE_LOGIN_DEADLINE_INTO_UNBOUNDED_INPUT_CLOCK_2,
        )
    )
    monkeypatch.setattr(browser_module.time, S.MONOTONIC, lambda: next(clock))
    with (
        client(interactive=C.TRUE, timeout_seconds=C.ONE) as browser,
        pytest.raises(ConnectorError) as failure,
    ):
        browser.fetch(C.TEST_BROWSER_URL)
    assert failure.value.state == SyncState.NEEDS_AUTH
    assert failure.value.code == S.LOGIN_WAIT_EXPIRED
    assert len(context.page.waits) == C.ONE


def test_interactive_challenge_is_not_solved_or_retried(driver) -> None:
    context, _runtime = driver
    context.responses[C.TEST_BROWSER_URL] = Response(
        S.TEST_BROWSER_INTERACTIVE_CHALLENGE_IS_CHALLENGE_FORM_CHALLENGE_FORM
    )
    with client(interactive=C.TRUE) as browser, pytest.raises(ConnectorError) as failure:
        browser.fetch(C.TEST_BROWSER_URL)
    assert failure.value.state == SyncState.BLOCKED
    assert context.page.gotos == [C.TEST_BROWSER_URL]
    assert not context.page.waits


@pytest.mark.parametrize(
    S.URL,
    [
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_THESTORYGRAPH_COM_PROFILE_ALICE,
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_APP_THESTORYGRAPH_COM_EVIL_EXAMPLE,
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_HTTPS_EVIL_EXAMPLE,
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_HTTPS_APP_THESTORYGRAPH_COM,
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_PASSWORD_APP_THESTORYGRAPH_COM,
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_APP_THESTORYGRAPH_COM_EVIL_EXAMPLE_2,
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_HTTPS_APP_THESTORYGRAPH_COM_2,
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_HTTPS_MALFORMED,
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_TEMPLATE.format(
            v0=C.TEST_BROWSER_ORIGIN
        ),
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_TEMPLATE_2.format(
            v0=C.TEST_BROWSER_ORIGIN
        ),
        S.TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_TEMPLATE_3.format(
            v0=C.TEST_BROWSER_ORIGIN
        ),
    ],
)
def test_unsafe_urls_rejected_before_startup(driver, url) -> None:
    _context, runtime = driver
    with client() as browser, pytest.raises(ConnectorError) as failure:
        browser.fetch(url)
    assert failure.value.state == SyncState.BLOCKED
    assert not runtime.launches
    assert url not in str(failure.value)


def test_safe_redirect_hops_are_separately_validated(driver) -> None:
    context, _runtime = driver
    redirected = S.TEST_BROWSER_SAFE_REDIRECT_SEPARATELY_VALIDATED_REDIRECTED_TEMPLATE.format(
        v0=C.TEST_BROWSER_ORIGIN
    )
    context.responses[C.TEST_BROWSER_URL] = Response(
        status=C.TEST_SAFE_REDIRECT_HOPS_ARE_SEPARATELY_VALIDATED_STATUS,
        headers={S.LOCATION: redirected},
    )
    context.responses[redirected] = Response()
    with client() as browser:
        document = browser.fetch(C.TEST_BROWSER_URL)
    assert document.url == redirected
    assert context.page.gotos == [C.TEST_BROWSER_URL, redirected]
    assert context.routes[C.ZERO].fulfilled and not context.routes[C.ZERO].aborted
    assert not any(route.continued for route in context.routes)


def test_external_redirect_is_blocked_before_followup_or_cookie_transfer(driver) -> None:
    context, _runtime = driver
    context.responses[C.TEST_BROWSER_URL] = Response(
        status=C.TEST_EXTERNAL_REDIRECT_IS_BLOCKED_FOLLOWUP_OR_COOKIE_TRANSFER_STATUS,
        headers={
            S.LOCATION: S.TEST_EXTERNAL_REDIRECT_IS_BLOCKED_BEFORE_HTTPS_EVIL_EXAMPLE_TOKEN_DO
        },
    )
    with client() as browser, pytest.raises(ConnectorError) as failure:
        browser.fetch(C.TEST_BROWSER_URL)
    assert failure.value.code == S.UNSAFE_NAVIGATION
    assert context.page.gotos == [C.TEST_BROWSER_URL]
    assert not context.routes[C.ZERO].continued and (not context.routes[C.ZERO].fulfilled)
    assert S.DO_NOT_LOG not in str(failure.value)


def test_later_redirect_hop_cannot_escape_host_validation(driver) -> None:
    context, _runtime = driver
    second = S.TEST_BROWSER_LATER_REDIRECT_HOP_HOST_VALIDATION_SECOND_TEMPLATE.format(
        v0=C.TEST_BROWSER_ORIGIN
    )
    context.responses[C.TEST_BROWSER_URL] = Response(
        status=C.TEST_LATER_REDIRECT_HOP_CANNOT_ESCAPE_HOST_VALIDATION_STATUS,
        headers={S.LOCATION: second},
    )
    context.responses[second] = Response(
        status=C.TEST_LATER_REDIRECT_HOP_CANNOT_ESCAPE_HOST_VALIDATION_STATUS,
        headers={S.LOCATION: S.TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_HTTPS_EVIL_EXAMPLE},
    )
    with client() as browser, pytest.raises(ConnectorError):
        browser.fetch(C.TEST_BROWSER_URL)
    assert context.page.gotos == [C.TEST_BROWSER_URL, second]


def test_redirect_loops_are_bounded(driver) -> None:
    context, _runtime = driver
    context.responses[C.TEST_BROWSER_URL] = Response(
        status=C.TEST_REDIRECT_LOOPS_ARE_BOUNDED_STATUS, headers={S.LOCATION: C.TEST_BROWSER_URL}
    )
    with client() as browser, pytest.raises(ConnectorError) as failure:
        browser.fetch(C.TEST_BROWSER_URL)
    assert failure.value.code == S.REDIRECT_LOOP
    assert context.page.gotos == [C.TEST_BROWSER_URL]


def test_export_subresources_mutations_and_download_responses_are_blocked(driver) -> None:
    attachment_header = S.TEST_EXPORT_SUBRESOURCES_MUTATIONS_AND_HEADERS_ATTACHMENT_FILENAME_L
    with client() as browser:
        browser.fetch(C.TEST_BROWSER_URL)
        export = Route(
            S.TEST_BROWSER_EXPORT_SUBRESOURCES_ARE_BLOCKED_EXPORT_TEMPLATE.format(
                v0=C.TEST_BROWSER_ORIGIN
            ),
            Response(),
            main=C.FALSE,
        )
        browser._guard_request(export)
        assert export.aborted and (not export.fetches) and (not export.continued)
        browser._route_error = C.NONE
        mutation = Route(
            S.TEST_BROWSER_EXPORT_SUBRESOURCES_ARE_BLOCKED_MUTATION_TEMPLATE.format(
                v0=C.TEST_BROWSER_ORIGIN
            ),
            Response(),
            method=S.POST,
        )
        browser._guard_request(mutation)
        assert mutation.aborted and (not mutation.fetches)
        attachment = Route(
            C.TEST_BROWSER_URL,
            Response(headers={S.CONTENT_DISPOSITION: attachment_header}),
        )
        browser._guard_request(attachment)
        assert attachment.aborted and (not attachment.fulfilled)


def test_only_discovered_owner_login_form_can_submit(driver) -> None:
    _context, _runtime = driver
    with client(interactive=C.TRUE) as browser:
        browser.fetch(C.TEST_BROWSER_URL)
        browser._login_active = C.TRUE
        browser._login_actions.add(
            S.TEST_BROWSER_ONLY_DISCOVERED_OWNER_LOGIN_FORM_CAN_SUBMIT_TEMPLATE.format(
                v0=C.TEST_BROWSER_ORIGIN
            )
        )
        login = Route(
            S.TEST_BROWSER_ONLY_DISCOVERED_OWNER_LOGIN_FORM_CAN_SUBMIT_TEMPLATE.format(
                v0=C.TEST_BROWSER_ORIGIN
            ),
            Response(),
            method=S.POST,
        )
        browser._guard_request(login)
        assert login.fulfilled
        other = Route(
            S.TEST_BROWSER_EXPORT_SUBRESOURCES_ARE_BLOCKED_MUTATION_TEMPLATE.format(
                v0=C.TEST_BROWSER_ORIGIN
            ),
            Response(),
            method=S.POST,
        )
        browser._guard_request(other)
        assert other.aborted and (not other.fetches)


@pytest.mark.parametrize(
    (S.ERROR, S.CODE),
    [
        (
            FakeTimeout(S.TEST_BROWSER_BROWSER_ERRORS_ARE_TYPED_RAW_MESSAGES_TOKEN_DO_NOT_LOG),
            S.BROWSER_TIMEOUT,
        ),
        (
            FakeError(S.TEST_BROWSER_BROWSER_ERRORS_ARE_TYPED_MESSAGES_COOKIES_DO_NOT_LOG),
            S.BROWSER_OPERATION_FAILED,
        ),
    ],
)
def test_browser_errors_are_typed_and_do_not_leak_raw_messages(driver, error, code) -> None:
    context, _runtime = driver
    context.page.failure = error
    with client() as browser, pytest.raises(ConnectorError) as failure:
        browser.fetch(C.TEST_BROWSER_URL)
    assert failure.value.code == code
    assert S.DO_NOT_LOG not in str(failure.value)
    assert failure.value.__cause__ is C.NONE


def test_missing_dependencies_are_actionable_and_not_automatically_installed(monkeypatch) -> None:

    def unavailable(_name):
        raise ImportError(S.TEST_BROWSER_MISSING_DEPENDENCIES_INSTALLED_UNAVAILABLE_SECRET_DEPEN)

    monkeypatch.setattr(browser_module.importlib, S.IMPORT_MODULE, unavailable)
    with client() as browser, pytest.raises(ConnectorError) as failure:
        browser.fetch(C.TEST_BROWSER_URL)
    assert failure.value.code == S.BROWSER_DEPENDENCIES_MISSING
    assert S.TEST_BROWSER_MISSING_DEPENDENCIES_INSTALLED_PLAYWRIGHT_INSTALL_CHROM in str(
        failure.value
    )
    assert S.TEST_BROWSER_MISSING_DEPENDENCIES_INSTALLED_UNAVAILABLE_SECRET_DEPEN not in str(
        failure.value
    )


def test_missing_browser_binary_is_actionable_without_raw_process_error(driver) -> None:
    _context, runtime = driver
    runtime.failure = FakeError(
        S.TEST_BROWSER_MISSING_BROWSER_BINARY_IS_ERROR_EXECUTABLE_DOESN_T_EXIS
    )
    with client() as browser, pytest.raises(ConnectorError) as failure:
        browser.fetch(C.TEST_BROWSER_URL)
    assert failure.value.code == S.BROWSER_NOT_INSTALLED
    assert S.TEST_BROWSER_MISSING_DEPENDENCIES_INSTALLED_PLAYWRIGHT_INSTALL_CHROM in str(
        failure.value
    )
    assert S.PRIVATE_USER_DIRECTORY not in str(failure.value)
    assert runtime.stopped


def test_closed_session_cannot_restart(driver) -> None:
    _context, runtime = driver
    browser = client()
    browser.close()
    browser.close()
    with pytest.raises(ConnectorError, match=S.CLOSED):
        browser.fetch(C.TEST_BROWSER_URL)
    assert not runtime.launches


def test_login_xhr_redirect_cannot_send_credentials_to_another_host(driver) -> None:
    redirect_url = S.TEST_BROWSER_UNSAFE_URLS_REJECTED_BEFORE_STARTUP_HTTPS_EVIL_EXAMPLE
    with client(interactive=C.TRUE) as browser:
        browser.fetch(C.TEST_BROWSER_URL)
        browser._login_active = C.TRUE
        browser._login_actions.add(
            S.TEST_BROWSER_ONLY_DISCOVERED_OWNER_LOGIN_FORM_CAN_SUBMIT_TEMPLATE.format(
                v0=C.TEST_BROWSER_ORIGIN
            )
        )
        route = Route(
            S.TEST_BROWSER_ONLY_DISCOVERED_OWNER_LOGIN_FORM_CAN_SUBMIT_TEMPLATE.format(
                v0=C.TEST_BROWSER_ORIGIN
            ),
            Response(
                status=C.TEST_LOGIN_XHR_REDIRECT_CANNOT_SEND_TO_ANOTHER_HOST_ROUTE_STATUS,
                headers={S.LOCATION: redirect_url},
            ),
            method=S.POST,
            main=C.FALSE,
        )
        browser._guard_request(route)
        assert route.aborted and (not route.continued)
        assert browser._route_error.code == S.UNSAFE_NAVIGATION
        assert route.fetches == [
            {
                S.MAX_REDIRECTS: C.ZERO,
                S.TIMEOUT: C.TEST_BROWSER_LOGIN_XHR_REDIRECT_SEND_CREDENTIALS_TO_ANOTHER_HOST,
            }
        ]


@pytest.mark.browser
def test_factory_shares_driver_but_isolates_profiles_and_closes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = pytest.importorskip(S.PLAYWRIGHT_SYNC_API)
    with api.sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).is_file():
            pytest.skip(S.TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_INSTALL_CHROMIUM_WITH)
    clients: list[BrowserClient] = []

    def tracked_browser(*args, **kwargs):
        browser = BrowserClient(*args, **kwargs)
        clients.append(browser)
        return browser

    monkeypatch.setattr(browser_module, S.TEST_BROWSER_CLASS_NAME, tracked_browser)
    settings = Settings(
        accounts=accounts(),
        metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
    )
    with ExitStack() as stack:
        cli._build_service(tmp_path, settings, stack, interactive=C.FALSE)
        first, second = clients
        first._start()
        first._context.add_cookies(
            [{S.NAME: S.BOOKY, S.VALUE: S.READER, S.URL: C.TEST_BROWSER_ORIGIN}]
        )
        second._start()
        assert not second._context.cookies()
        first.close()
        assert second._context.new_page().url == S.PAGE_INIT_ABOUT_BLANK
    with BrowserClient(
        tmp_path / S.CURRENT,
        allowed_hosts=(S.APP_THESTORYGRAPH_COM,),
    ) as standalone:
        standalone._start()


@pytest.mark.browser
def test_real_browser_local_redirects_and_session_reuse_without_source_network(monkeypatch) -> None:
    api = pytest.importorskip(S.PLAYWRIGHT_SYNC_API)
    with api.sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).is_file():
            pytest.skip(S.TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_INSTALL_CHROMIUM_WITH)
    seen: list[tuple[str, bool]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(
                (
                    self.path,
                    S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_BOOKY
                    in self.headers.get(S.COOKIE, S.EMPTY),
                )
            )
            if self.path == S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_START:
                self.send_response(
                    C.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_SOURCE_NETWORK_HANDLER_DO_GET
                )
                self.send_header(
                    S.LOCATION_2,
                    S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_PAGE,
                )
                self.send_header(
                    S.SET_COOKIE,
                    S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_HANDLER_DO_GET_BOOKY_PATH_MAX,
                )
                self.end_headers()
            elif self.path == S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_UNSAFE:
                self.send_response(
                    C.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_SOURCE_NETWORK_HANDLER_DO_GET
                )
                self.send_header(
                    S.LOCATION_2,
                    S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_DO_GET_HTTPS_EVIL_EXAMPLE_T,
                )
                self.end_headers()
            else:
                body = S.HANDLER_DO_GET_BODY_BYTES
                self.send_response(
                    C.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_SOURCE_NETWORK_HANDLER_DO_GET_2
                )
                self.send_header(
                    S.CONTENT_TYPE_2,
                    S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_HANDLER_DO_GET_TEXT_HTML,
                )
                self.send_header(S.CONTENT_LENGTH_2, str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(
        (S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_SERVER_TEXT, C.ZERO), Handler
    )
    server.daemon_threads = C.TRUE
    port = server.server_address[C.ONE]
    origin = S.TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_ORIGIN_TEMPLATE.format(v0=port)
    thread = threading.Thread(target=server.serve_forever, daemon=C.TRUE)
    profile = (
        Path(S.TESTS)
        / S.FIXTURES
        / S.STORYGRAPH
        / S.TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_PROFILE_TEMPLATE.format(
            v0=uuid.uuid4().hex
        )
    )
    thread.start()

    def local_only(url):
        parsed = urlsplit(url)
        if (
            parsed.scheme != S.HTTP
            or parsed.hostname
            != S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_SERVER_TEXT
            or parsed.port != port
        ):
            raise ConnectorError(
                S.TEST_BROWSER_REAL_BROWSER_LOCAL_NETWORK_LOCAL_ONLY_LOCAL_FIXTU,
                state=SyncState.BLOCKED,
                code=S.UNSAFE_NAVIGATION,
            )
        return url

    try:
        with BrowserClient(
            profile,
            allowed_hosts=(S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_SERVER_TEXT,),
            timeout_seconds=C.TEN,
        ) as browser:
            monkeypatch.setattr(
                browser,
                S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_CHECKED_URL,
                local_only,
            )
            document = browser.fetch(
                S.TEST_BROWSER_REAL_BROWSER_LOCAL_SOURCE_NETWORK_DOCUMENT_TEMPLATE.format(
                    v0=origin
                ),
                wait_for=S.MAIN,
            )
            assert (
                document.url
                == S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_TEMPLATE.format(
                    v0=origin
                )
            )
            assert (
                S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_PAGE,
                C.TRUE,
            ) in seen
            with pytest.raises(ConnectorError) as failure:
                browser.fetch(
                    S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_TEMPLATE_2.format(
                        v0=origin
                    )
                )
            assert failure.value.code == S.UNSAFE_NAVIGATION
        with BrowserClient(
            profile,
            allowed_hosts=(S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_SERVER_TEXT,),
            timeout_seconds=C.TEN,
        ) as browser:
            monkeypatch.setattr(
                browser,
                S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_CHECKED_URL,
                local_only,
            )
            browser.fetch(
                S.TEST_BROWSER_REAL_BROWSER_LOCAL_WITHOUT_SOURCE_NETWORK_TEMPLATE.format(v0=origin)
            )
            assert seen[-C.ONE] == (
                S.TEST_REAL_BROWSER_LOCAL_REDIRECTS_AND_NETWORK_HANDLER_DO_GET_PAGE,
                C.TRUE,
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=C.FIVE)
        if profile.exists():
            shutil.rmtree(profile)
