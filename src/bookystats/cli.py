from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import TextIO

from pydantic import JsonValue, ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.config import (
    Settings,
    account_from_url,
    browser_profile,
    data_directory,
    load_settings,
    save_settings,
)
from bookystats.errors import AlreadyRunning, BookyError, ConfigurationError
from bookystats.interfaces import MetadataProvider, SourceConnector
from bookystats.locking import SyncLock
from bookystats.models import CollectionProgress, Issue, Source, SyncState
from bookystats.net import HttpClient
from bookystats.redaction import redact
from bookystats.scheduling import (
    enable_weekly,
    record_live_run,
    require_activation,
    schedule_status,
)
from bookystats.sync import SyncReceipt, SyncService


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog=S.BOOKY,
        description=S.PARSER_RESULT_DESCRIPTION_READ_ONLY_READING_DATA_SYNC_REPORTS_READ,
    )
    result.add_argument(S.COMMAND, choices=(S.SYNC, S.STATUS))
    result.add_argument(
        S.CLI_PARSER_DATA_DIR,
        type=Path,
        help=S.CLI_PARSER_HELP_OVERRIDE_THE_PRIVATE_LOCAL_DATA_DIRECTORY,
    )
    result.add_argument(
        S.CLI_PARSER_JSON, action=S.STORE_TRUE, help=S.CLI_PARSER_HELP_PRINT_A_STRUCTURED_RECEIPT
    )
    mode = result.add_mutually_exclusive_group()
    mode.add_argument(
        S.CLI_PARSER_INTERACTIVE,
        action=S.STORE_TRUE,
        help=S.CLI_PARSER_HELP_ALLOW_VISIBLE_ACCOUNT_SIGN_IN,
    )
    mode.add_argument(
        S.CLI_PARSER_UNATTENDED,
        action=S.STORE_TRUE,
        help=S.CLI_PARSER_HELP_NEVER_PROMPT_OR_WAIT_FOR_SIGN_IN,
    )
    result.add_argument(S.CLI_PARSER_SCHEDULED, action=S.STORE_TRUE, help=argparse.SUPPRESS)
    return result


def _setup(directory: Path, settings: Settings) -> Settings:
    if settings.accounts:
        return settings
    accounts = []
    for source, prompt in (
        (Source.STORYGRAPH, S.CLI_SETUP_STORYGRAPH_READER_PROFILE_URL_BLANK_TO_SKIP),
        (Source.GOODREADS, S.CLI_SETUP_GOODREADS_READER_PROFILE_URL_BLANK_TO_SKIP),
    ):
        value = input(prompt).strip()
        if value:
            accounts.append(account_from_url(source, value))
    if not accounts:
        raise ConfigurationError(S.CLI_SETUP_NO_ACCOUNT_PROFILES_WERE_PROVIDED_NO_REQUESTS)
    updated = settings.model_copy(update={S.ACCOUNTS: tuple(accounts)})
    save_settings(directory, updated)
    return updated


def _build_service(
    directory: Path, settings: Settings, stack: ExitStack, *, interactive: bool
) -> SyncService:
    from bookystats.browser import BrowserClient, BrowserRuntime
    from bookystats.cache import MetadataCache, MetadataCacheError
    from bookystats.connectors.goodreads import GoodreadsConnector
    from bookystats.connectors.storygraph import StoryGraphConnector
    from bookystats.providers.google_books import GoogleBooksProvider
    from bookystats.providers.open_library import OpenLibraryProvider
    from bookystats.storage import Database

    store = Database(directory / S.LIBRARY_SQLITE3)
    store.initialize()
    stack.callback(store.close)
    browser_runtime = stack.enter_context(BrowserRuntime())
    connectors: dict[Source, SourceConnector] = {}
    for account in settings.accounts:
        hosts = (
            (S.APP_THESTORYGRAPH_COM,)
            if account.source == Source.STORYGRAPH
            else (S.WWW_GOODREADS_COM, S.GOODREADS_COM)
        )
        browser = stack.enter_context(
            BrowserClient(
                browser_profile(directory, account),
                allowed_hosts=hosts,
                interactive=interactive,
                timeout_seconds=settings.browser_timeout_seconds,
                runtime=browser_runtime,
            )
        )
        if account.source == Source.STORYGRAPH:
            connectors[account.source] = StoryGraphConnector(browser, max_pages=settings.max_pages)
        else:
            http = stack.enter_context(
                HttpClient(
                    allowed_hosts=hosts,
                    timeout=settings.http_timeout_seconds,
                    max_requests=settings.max_pages + C.TEN,
                )
            )
            connectors[account.source] = GoodreadsConnector(
                http, browser, max_pages=settings.max_pages
            )
    providers: dict[Source, MetadataProvider] = {}
    provider_issues: dict[Source, Issue] = {}
    key = os.environ.get(S.GOOGLE_BOOKS_API_KEY, S.EMPTY).strip()
    needed = [
        source
        for source, configured in (
            (Source.GOOGLE_BOOKS, settings.metadata.google_books and bool(key)),
            (Source.OPEN_LIBRARY, settings.metadata.open_library),
        )
        if configured
    ]
    cache: MetadataCache | None = C.NONE
    if needed:
        try:
            cache = MetadataCache(directory / S.METADATA_SQLITE3)
        except MetadataCacheError as exc:
            provider_issues = {
                source: Issue(code=S.METADATA_CACHE_ERROR, message=str(exc)) for source in needed
            }
        else:
            stack.callback(cache.close)
    if settings.metadata.google_books and key and cache is not C.NONE:
        google_http = stack.enter_context(
            HttpClient(
                allowed_hosts=(S.WWW_GOOGLEAPIS_COM,),
                timeout=settings.http_timeout_seconds,
                max_requests=settings.metadata.max_books_per_run * C.FOUR,
            )
        )
        providers[Source.GOOGLE_BOOKS] = GoogleBooksProvider(google_http, api_key=key, cache=cache)
    if settings.metadata.open_library and cache is not C.NONE:
        user_agent = S.CLI_BUILD_SERVICE_USER_AGENT_BOOKYSTATS
        if settings.metadata.contact:
            user_agent += S.CLI_BUILD_SERVICE_TEMPLATE.format(v0=settings.metadata.contact)
        library_http = stack.enter_context(
            HttpClient(
                allowed_hosts=(S.OPENLIBRARY_ORG,),
                timeout=settings.http_timeout_seconds,
                min_interval=C.ONE,
                max_requests=C.TEN,
                user_agent=user_agent,
            )
        )
        providers[Source.OPEN_LIBRARY] = OpenLibraryProvider(library_http, cache=cache)

    def progress(event: CollectionProgress) -> None:
        if event.pages_seen == C.ONE or event.pages_seen % C.TEN == C.ZERO:
            print(
                S.CLI_BUILD_SERVICE_PROGRESS_TEMPLATE.format(
                    v0=event.source.value, v1=event.collection, v2=event.pages_seen
                ),
                file=sys.stderr,
            )

    return SyncService(
        store,
        settings,
        connectors,
        providers,
        on_progress=progress,
        provider_issues=provider_issues,
    )


def _print_receipt(receipt: SyncReceipt, output: TextIO, *, as_json: bool) -> None:
    if as_json:
        print(receipt.model_dump_json(indent=C.TWO), file=output)
        return
    print(
        S.CLI_PRINT_RECEIPT_TEMPLATE.format(v0=receipt.run_id, v1=receipt.state.value), file=output
    )
    for source in receipt.sources:
        print(
            S.CLI_PRINT_RECEIPT_TEMPLATE_2.format(
                v0=source.source.value, v1=source.state.value, v2=source.records, v3=source.pages
            ),
            file=output,
        )
        if source.publication is not C.NONE:
            counts = source.publication
            print(
                S.CLI_PRINT_RECEIPT_TEMPLATE_3.format(
                    v0=counts.added, v1=counts.updated, v2=counts.unchanged, v3=counts.removed
                ),
                file=output,
            )
        for issue in source.issues[: C.FIVE]:
            print(
                S.CLI_PRINT_RECEIPT_TEMPLATE_4.format(v0=issue.code, v1=issue.message), file=output
            )
        if len(source.issues) > C.FIVE:
            print(
                S.CLI_PRINT_RECEIPT_TEMPLATE_5.format(v0=len(source.issues) - C.FIVE), file=output
            )
    for metadata in receipt.metadata:
        print(
            S.CLI_PRINT_RECEIPT_TEMPLATE_6.format(
                v0=metadata.provider.value,
                v1=metadata.state.value,
                v2=metadata.processed,
                v3=metadata.deferred,
            ),
            file=output,
        )
        for issue in metadata.issues[: C.FIVE]:
            print(
                S.CLI_PRINT_RECEIPT_TEMPLATE_4.format(v0=issue.code, v1=issue.message), file=output
            )
    if not receipt.account_sync_complete:
        print(S.CLI_PRINT_RECEIPT_LAST_GOOD_SOURCE_SNAPSHOTS_REMAIN_AVAILABLE_THIS, file=output)


def _status(directory: Path, settings: Settings) -> dict[str, JsonValue]:
    path = directory / S.LIBRARY_SQLITE3
    if not path.exists():
        report: dict[str, JsonValue] = {
            S.LIBRARY: {},
            S.SOURCES: [],
            S.LAST_RUN: C.NONE,
            S.STATE: S.NOT_SYNCED,
        }
    else:
        from bookystats.storage import Database

        store = Database(path)
        try:
            store.initialize()
            report = store.status()
        finally:
            store.close()
    report[S.DATA_DIRECTORY] = str(directory)
    report[S.CONFIGURED_SOURCES] = [account.source.value for account in settings.accounts]
    report[S.SCHEDULE] = schedule_status(directory, settings)
    report[S.GOOGLE_BOOKS_KEY_CONFIGURED] = bool(os.environ.get(S.GOOGLE_BOOKS_API_KEY))
    return report


def _print_status(report: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=C.TWO, ensure_ascii=C.FALSE))
        return
    print(S.CLI_PRINT_STATUS_BOOKYSTATS_STATUS_LOCAL_DATA_NO_SOURCE_REQUESTS)
    for key, value in report.items():
        print(
            S.CLI_PRINT_STATUS_TEMPLATE.format(
                v0=key.replace(S.UNDERSCORE, S.SPACE), v1=json.dumps(value, ensure_ascii=C.FALSE)
            )
        )


def main(argv: list[str] | None = C.NONE) -> int:
    args = parser().parse_args(argv)
    directory = data_directory(args.data_dir)
    try:
        settings = load_settings(directory)
        if args.command == S.STATUS:
            _print_status(_status(directory, settings), as_json=args.json)
            return C.ZERO
        if args.scheduled and (not settings.weekly.enabled):
            print(S.CLI_MAIN_WEEKLY_SCHEDULING_IS_DISABLED_NO_SOURCE_REQUESTS)
            return C.ZERO
        interactive = not (args.unattended or args.scheduled) and (
            args.interactive or sys.stdin.isatty()
        )
        if not settings.accounts and interactive:
            settings = _setup(directory, settings)
        if not settings.accounts:
            raise ConfigurationError(S.CLI_MAIN_CONFIGURE_READER_PROFILE_URLS_IN_CONFIG_JSON)
        with SyncLock(directory), ExitStack() as stack:
            if args.scheduled:
                require_activation(directory, Path(sys.executable), settings)
            service = _build_service(directory, settings, stack, interactive=interactive)
            receipt = service.run(
                interactive=interactive,
                trigger=S.SCHEDULED
                if args.scheduled
                else S.MANUAL
                if interactive
                else S.UNATTENDED,
            )
            record_live_run(directory, settings, receipt, unattended=not interactive)
            _print_receipt(receipt, sys.stdout, as_json=args.json)
            if settings.weekly.enabled and (not args.scheduled):
                enable_weekly(directory, Path(sys.executable), settings, service.store.status())
            return C.ZERO if receipt.state == SyncState.COMPLETE else C.THREE
    except AlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        return C.FOUR
    except BookyError as exc:
        print(redact(str(exc), (os.environ.get(S.GOOGLE_BOOKS_API_KEY, S.EMPTY),)), file=sys.stderr)
        return C.ONE
    except (sqlite3.Error, OSError, ValidationError):
        print(S.CLI_MAIN_A_LOCAL_DATA_CONFIGURATION_OR_RECORD_VALIDATION, file=sys.stderr)
        return C.ONE
    except (KeyboardInterrupt, EOFError):
        print(S.CLI_MAIN_SYNC_INTERRUPTED_NO_INCOMPLETE_SOURCE_SNAPSHOT_IS, file=sys.stderr)
        return C.CLI_MAIN
