from __future__ import annotations

import importlib
import re
import time
from contextlib import suppress
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import ConnectorError
from bookystats.interfaces import PageDocument
from bookystats.models import SyncState

if TYPE_CHECKING:
    from playwright.sync_api import Playwright


class BrowserRuntime:
    def __init__(self) -> None:
        self._playwright: Playwright | None = C.NONE
        self._errors: tuple[type[Exception], ...] = ()

    def __enter__(self) -> BrowserRuntime:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is C.NONE:
            self.close()
        else:
            with suppress(ConnectorError):
                self.close()

    def get(self) -> Playwright:
        if self._playwright is not C.NONE:
            return self._playwright
        api = importlib.import_module(S.PLAYWRIGHT_SYNC_API)
        self._errors = (api.Error,)
        playwright: Playwright = api.sync_playwright().start()
        self._playwright = playwright
        return playwright

    def close(self) -> None:
        try:
            if self._playwright is not C.NONE:
                self._playwright.stop()
        except self._errors:
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_CLOSE_THE_BROWSER_SESSION_COULD_NOT_BE_CLOSED,
                code=S.BROWSER_CLOSE_FAILED,
            ) from C.NONE
        finally:
            self._playwright = C.NONE


def page_access_problem(document: PageDocument) -> ConnectorError | None:
    soup = BeautifulSoup(document.html, S.HTML_PARSER)
    title = soup.title.get_text(S.SPACE, strip=C.TRUE).casefold() if soup.title else S.EMPTY
    challenge = soup.select_one(
        S.BROWSER_PAGE_ACCESS_PROBLEM_CHALLENGE_CHALLENGE_RUNNING_CF_TURNSTILE
    )
    if (
        document.status_code in {C.BROWSER_PAGE_ACCESS_PROBLEM, C.BROWSER_PAGE_ACCESS_PROBLEM_2}
        or challenge is not C.NONE
        or any(
            marker in title
            for marker in (
                S.BROWSER_PAGE_ACCESS_PROBLEM_JUST_A_MOMENT,
                S.BROWSER_PAGE_ACCESS_PROBLEM_ATTENTION_REQUIRED,
                S.BROWSER_PAGE_ACCESS_PROBLEM_VERIFY_YOU_ARE_HUMAN,
            )
        )
    ):
        return ConnectorError(
            S.BROWSER_PAGE_ACCESS_PROBLEM_THE_SOURCE_BLOCKED_ACCESS_OR_PRESENTED_A,
            state=SyncState.BLOCKED,
            code=S.SOURCE_BLOCKED,
        )
    if (
        document.status_code == C.BROWSER_PAGE_ACCESS_PROBLEM_3
        or C.BROWSER_LOGIN_PATH.search(urlsplit(document.url).path)
        or soup.select_one(S.BROWSER_PAGE_ACCESS_PROBLEM_FORM_INPUT_TYPE_PASSWORD) is not C.NONE
    ):
        return ConnectorError(
            S.BROWSER_PAGE_ACCESS_PROBLEM_THE_NEEDS_AN_AUTHENTICATED_OWNER_SESSION,
            state=SyncState.NEEDS_AUTH,
            code=S.NEEDS_AUTH,
        )
    if (
        document.status_code is not C.NONE
        and document.status_code >= C.BROWSER_PAGE_ACCESS_PROBLEM_4
    ):
        return ConnectorError(
            S.BROWSER_PAGE_ACCESS_PROBLEM_THE_AN_UNSUCCESSFUL_PAGE_RESPONSE,
            code=S.SOURCE_HTTP_ERROR,
            retryable=document.status_code >= C.BROWSER_PAGE_ACCESS_PROBLEM_RETRYABLE,
        )
    return C.NONE


class BrowserClient:
    def __init__(
        self,
        profile_dir: Path,
        *,
        allowed_hosts: tuple[str, ...],
        interactive: bool = C.FALSE,
        timeout_seconds: float = C.BROWSERCLIENT_INIT_TIMEOUT_SECONDS,
        runtime: BrowserRuntime | None = C.NONE,
    ) -> None:
        if not allowed_hosts or any(
            not re.fullmatch(S.BROWSER_BROWSERCLIENT_INIT_A_Z0_A_Z0_A_Z0, host)
            or S.BROWSER_BROWSERCLIENT_INIT_TEXT in host
            for host in allowed_hosts
        ):
            raise ValueError(S.BROWSER_BROWSERCLIENT_INIT_ALLOWED_HOSTS_CONTAIN_EXACT_LOWERCASE_DNS)
        if not C.ZERO < timeout_seconds <= C.BROWSER_BROWSERCLIENT_INIT:
            raise ValueError(S.BROWSER_BROWSERCLIENT_INIT_TIMEOUT_SECONDS_MUST_BE_BETWEEN_ZERO_AND)
        self.profile_dir = Path(profile_dir)
        self.allowed_hosts = tuple(dict.fromkeys(allowed_hosts))
        self.interactive = interactive
        self.timeout_seconds = timeout_seconds
        self._runtime = runtime if runtime is not C.NONE else BrowserRuntime()
        self._owns_runtime = runtime is C.NONE
        self._context: Any = C.NONE
        self._page: Any = C.NONE
        self._errors: tuple[type[Exception], ...] = ()
        self._timeouts: tuple[type[Exception], ...] = ()
        self._closed = C.FALSE
        self._route_error: ConnectorError | None = C.NONE
        self._pending_redirect: str | None = C.NONE
        self._login_actions: set[str] = set()
        self._login_active = C.FALSE
        self._login_attempted = C.FALSE

    def __enter__(self) -> BrowserClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is C.NONE:
            self.close()
        else:
            with suppress(ConnectorError):
                self.close()

    def _checked_url(self, url: str) -> str:
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme == S.HTTPS
                and parsed.hostname in self.allowed_hosts
                and (parsed.port in (C.NONE, C.BROWSERCLIENT_CHECKED_URL_VALID))
                and (parsed.username is C.NONE)
                and (parsed.password is C.NONE)
                and (not re.search(S.BROWSERCLIENT_CHECKED_URL_VALID_X00_X20, url))
            )
        except ValueError:
            valid = C.FALSE
        if not valid:
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_CHECKED_URL_REFUSED_OUTSIDE_THE_CONFIGURED,
                state=SyncState.BLOCKED,
                code=S.UNSAFE_NAVIGATION,
            )
        decoded_path = unquote(unquote(parsed.path))
        decoded_query = unquote(unquote(parsed.query))
        if C.BROWSER_EXPORT_PATH.search(decoded_path) or re.search(
            S.BROWSER_BROWSERCLIENT_CHECKED_URL_EXPORT_DOWNLOAD, decoded_query, re.I
        ):
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_CHECKED_URL_DOWNLOAD_NAVIGATION_IS_DISABLED,
                state=SyncState.BLOCKED,
                code=S.EXPORT_DISABLED,
            )
        return url

    def _prepare_profile(self) -> None:
        try:
            if self.profile_dir.is_symlink():
                raise ConnectorError(
                    S.BROWSER_BROWSERCLIENT_PREPARE_PROFILE_THE_PROFILE_MUST_NOT_BE,
                    code=S.UNSAFE_PROFILE,
                )
            self.profile_dir.mkdir(
                mode=C.BROWSERCLIENT_PREPARE_PROFILE_MODE, parents=C.TRUE, exist_ok=C.TRUE
            )
            if self.profile_dir.stat().st_mode & C.BROWSER_BROWSERCLIENT_PREPARE_PROFILE:
                import os

                if os.name != S.NT:
                    self.profile_dir.chmod(C.BROWSER_BROWSERCLIENT_PREPARE_PROFILE_2)
        except OSError:
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_PREPARE_PROFILE_THE_PROFILE_COULD_NOT_BE,
                code=S.PROFILE_UNAVAILABLE,
            ) from C.NONE

    def _start(self) -> None:
        if self._closed:
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_START_THIS_BROWSER_SESSION_IS_CLOSED, code=S.BROWSER_CLOSED
            )
        if self._context is not C.NONE:
            return
        try:
            api = importlib.import_module(S.PLAYWRIGHT_SYNC_API)
        except ImportError:
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_START_BOOKYSTATS_BROWSER_DEPENDENCIES,
                code=S.BROWSER_DEPENDENCIES_MISSING,
            ) from C.NONE
        self._errors = (api.Error,)
        self._timeouts = (api.TimeoutError,)
        self._prepare_profile()
        try:
            playwright = self._runtime.get()
            self._context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=not self.interactive,
                accept_downloads=C.FALSE,
                service_workers=S.BLOCK,
                chromium_sandbox=C.TRUE,
                timeout=self.timeout_seconds * C.START_TIMEOUT,
            )
            self._context.set_default_timeout(self.timeout_seconds * C.BROWSER_BROWSERCLIENT_START)
            self._context.set_default_navigation_timeout(
                self.timeout_seconds * C.BROWSER_BROWSERCLIENT_START
            )
            self._context.route(S.BROWSER_BROWSERCLIENT_START_TEXT, self._guard_request)
            self._context.on(S.PAGE, self._configure_page)
            pages = self._context.pages
            self._page = pages[C.ZERO] if pages else self._context.new_page()
            for page in self._context.pages:
                self._configure_page(page)
        except self._errors as exc:
            code = (
                S.BROWSER_NOT_INSTALLED
                if S.BROWSERCLIENT_START_CODE_EXECUTABLE_DOESN_T_EXIST in str(exc)
                else S.BROWSER_START_FAILED
            )
            self._discard_started_browser()
            message = (
                S.BROWSERCLIENT_START_MESSAGE_CHROMIUM_IS_NOT_INSTALLED_RUN_PYTHON_M
                if code == S.BROWSER_NOT_INSTALLED
                else S.BROWSERCLIENT_START_MESSAGE_THE_BROWSER_COULD_NOT_START_CHECK_THE
            )
            raise ConnectorError(message, code=code) from C.NONE
        except OSError:
            self._discard_started_browser()
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_START_THE_BROWSER_PROCESS_COULD_NOT_BE_STARTED,
                code=S.BROWSER_START_FAILED,
            ) from C.NONE

    def _discard_started_browser(self) -> None:
        with suppress(ConnectorError):
            self.close()

    def _configure_page(self, page: Any) -> None:
        page.on(S.DOWNLOAD, lambda download: download.cancel())

    def _guard_request(self, route: Any) -> None:
        request = route.request
        main_navigation = request.is_navigation_request() and request.frame.parent_frame is C.NONE
        login_submission = (
            self._login_active and request.method == S.POST and (request.url in self._login_actions)
        )
        try:
            parsed = urlsplit(request.url)
            if C.BROWSER_EXPORT_PATH.search(unquote(unquote(parsed.path))) or re.search(
                S.BROWSER_BROWSERCLIENT_CHECKED_URL_EXPORT_DOWNLOAD,
                unquote(unquote(parsed.query)),
                re.I,
            ):
                raise ConnectorError(
                    S.BROWSER_BROWSERCLIENT_GUARD_REQUEST_AN_DOWNLOAD_REQUEST_WAS_BLOCKED,
                    state=SyncState.BLOCKED,
                    code=S.EXPORT_DISABLED,
                )
            if main_navigation:
                self._checked_url(request.url)
            if request.method not in {S.GET, S.HEAD, S.OPTIONS}:
                if not login_submission:
                    route.abort(S.BLOCKEDBYCLIENT)
                    return
                self._checked_url(request.url)
            if not main_navigation and (not login_submission):
                route.continue_()
                return
            response = route.fetch(
                max_redirects=C.ZERO,
                timeout=self.timeout_seconds * C.GUARD_REQUEST_RESPONSE_TIMEOUT,
            )
            location = response.headers.get(S.LOCATION)
            if (
                C.BROWSER_BROWSERCLIENT_GUARD_REQUEST
                <= response.status
                < C.BROWSER_BROWSERCLIENT_GUARD_REQUEST_2
                and location
            ):
                target = self._checked_url(urljoin(request.url, location))
                if response.status in {
                    C.BROWSER_BROWSERCLIENT_GUARD_REQUEST_3,
                    C.BROWSER_BROWSERCLIENT_GUARD_REQUEST_4,
                } and request.method not in {S.GET, S.HEAD}:
                    raise ConnectorError(
                        S.BROWSER_BROWSERCLIENT_GUARD_REQUEST_A_REQUIRING_FORM_RESUBMISSION_IS,
                        state=SyncState.NEEDS_AUTH,
                        code=S.LOGIN_REDIRECT_UNSUPPORTED,
                    )
                self._pending_redirect = target
                # Aborting starts Chromium's error document, racing the next goto.
                # Complete the validated hop inertly without forwarding Location.
                route.fulfill(status=C.INTERFACES_PAGEDOCUMENT_STATUS_CODE, body=S.EMPTY)
                return
            if S.ATTACHMENT in response.headers.get(S.CONTENT_DISPOSITION, S.EMPTY).casefold():
                raise ConnectorError(
                    S.BROWSER_BROWSERCLIENT_GUARD_REQUEST_A_FILE_DOWNLOAD_WAS_BLOCKED,
                    state=SyncState.BLOCKED,
                    code=S.EXPORT_DISABLED,
                )
            route.fulfill(response=response)
        except ConnectorError as exc:
            self._route_error = exc
            route.abort(S.BLOCKEDBYCLIENT)
        except self._timeouts:
            self._route_error = ConnectorError(
                S.BROWSERCLIENT_GUARD_REQUEST_THE_SOURCE_PAGE_TIMED_OUT,
                code=S.BROWSER_TIMEOUT,
                retryable=C.TRUE,
            )
            route.abort(S.TIMEDOUT)
        except self._errors:
            self._route_error = ConnectorError(
                S.BROWSERCLIENT_GUARD_REQUEST_THE_BROWSER_COULD_NOT_LOAD_THE_SOURCE,
                code=S.BROWSER_OPERATION_FAILED,
                retryable=C.TRUE,
            )
            route.abort(S.FAILED)

    def _navigate(self, url: str) -> PageDocument:
        target = self._checked_url(url)
        visited: set[str] = set()
        for _ in range(C.TEN):
            if target in visited:
                raise ConnectorError(
                    S.BROWSER_BROWSERCLIENT_NAVIGATE_A_BROWSER_REDIRECT_REPEATED,
                    code=S.REDIRECT_LOOP,
                )
            visited.add(target)
            self._pending_redirect = C.NONE
            self._route_error = C.NONE
            try:
                response = self._page.goto(target, wait_until=S.DOMCONTENTLOADED)
            except self._errors:
                if self._route_error is not C.NONE:
                    raise self._route_error from C.NONE
                if self._pending_redirect is C.NONE:
                    raise
                response = C.NONE
            if self._route_error is not C.NONE:
                raise self._route_error
            if self._pending_redirect is not C.NONE:
                target = self._pending_redirect
                continue
            final_url = self._checked_url(self._page.url)
            return PageDocument(
                url=final_url,
                html=self._page.content(),
                status_code=response.status if response is not C.NONE else C.NONE,
            )
        raise ConnectorError(
            S.BROWSER_BROWSERCLIENT_NAVIGATE_THE_REDIRECT_LIMIT_WAS_REACHED, code=S.REDIRECT_LIMIT
        )

    def _owner_login(self, original_url: str, document: PageDocument) -> PageDocument:
        self._login_attempted = C.TRUE
        soup = BeautifulSoup(document.html, S.HTML_PARSER)
        self._login_actions.clear()
        for password in soup.select(S.BROWSER_PAGE_ACCESS_PROBLEM_FORM_INPUT_TYPE_PASSWORD):
            form = password.find_parent(S.FORM)
            if form is not C.NONE:
                action = str(form.get(S.ACTION) or document.url)
                self._login_actions.add(self._checked_url(urljoin(document.url, action)))
        self._login_active = C.TRUE
        print(S.BROWSER_BROWSERCLIENT_OWNER_LOGIN_TEMPLATE.format(v0=self.timeout_seconds))
        deadline = time.monotonic() + self.timeout_seconds
        try:
            while time.monotonic() < deadline:
                if self._route_error is not C.NONE:
                    raise self._route_error
                if self._pending_redirect is not C.NONE:
                    document = self._navigate(self._pending_redirect)
                else:
                    document = PageDocument(
                        self._checked_url(self._page.url), self._page.content(), C.NONE
                    )
                problem = page_access_problem(document)
                if problem is C.NONE:
                    return self._navigate(original_url)
                if problem.state != SyncState.NEEDS_AUTH:
                    raise problem
                self._page.wait_for_timeout(
                    min(
                        C.BROWSER_BROWSERCLIENT_OWNER_LOGIN,
                        self.timeout_seconds * C.BROWSER_BROWSERCLIENT_OWNER_LOGIN_2,
                    )
                )
        finally:
            self._login_active = C.FALSE
            self._login_actions.clear()
        raise ConnectorError(
            S.BROWSER_BROWSERCLIENT_OWNER_LOGIN_OWNER_WAS_NOT_COMPLETED_WITHIN_THE,
            state=SyncState.NEEDS_AUTH,
            code=S.LOGIN_WAIT_EXPIRED,
        )

    def fetch(self, url: str, *, wait_for: str | None = C.NONE) -> PageDocument:
        self._checked_url(url)
        self._start()
        try:
            document = self._navigate(url)
            problem = page_access_problem(document)
            if (
                problem is not C.NONE
                and problem.state == SyncState.NEEDS_AUTH
                and self.interactive
                and (not self._login_attempted)
            ):
                document = self._owner_login(url, document)
                problem = page_access_problem(document)
            if problem is not C.NONE:
                raise problem
            if wait_for:
                self._page.wait_for_selector(wait_for, state=S.ATTACHED)
                document = PageDocument(
                    self._checked_url(self._page.url), self._page.content(), document.status_code
                )
                problem = page_access_problem(document)
                if problem is not C.NONE:
                    raise problem
            if self._route_error is not C.NONE:
                raise self._route_error
            return document
        except self._timeouts:
            raise ConnectorError(
                S.BROWSERCLIENT_GUARD_REQUEST_THE_SOURCE_PAGE_TIMED_OUT,
                code=S.BROWSER_TIMEOUT,
                retryable=C.TRUE,
            ) from C.NONE
        except self._errors:
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_FETCH_THE_BROWSER_STOPPED_OR_COULD_NOT_LOAD,
                code=S.BROWSER_OPERATION_FAILED,
                retryable=C.TRUE,
            ) from C.NONE

    def close(self) -> None:
        self._closed = C.TRUE
        failed = C.FALSE
        try:
            if self._context is not C.NONE:
                self._context.close()
        except self._errors:
            failed = C.TRUE
        finally:
            self._context = C.NONE
            self._page = C.NONE
            try:
                if self._owns_runtime:
                    self._runtime.close()
            except ConnectorError:
                failed = C.TRUE
        if failed:
            raise ConnectorError(
                S.BROWSER_BROWSERCLIENT_CLOSE_THE_BROWSER_SESSION_COULD_NOT_BE_CLOSED,
                code=S.BROWSER_CLOSE_FAILED,
            )
