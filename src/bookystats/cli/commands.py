from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections.abc import Callable, Mapping, MutableMapping
from contextlib import ExitStack
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, TextIO

from pydantic import JsonValue, ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import HttpClient
from bookystats.application.sync import SourceReceipt, SyncReceipt, SyncService
from bookystats.application.verification import verify_run
from bookystats.cli.report import run_lines, status_lines
from bookystats.cli.storage_status import (
    attention_lines,
    latest_analytics,
    library_status,
    storage_report,
)
from bookystats.domain.errors import AlreadyRunning, BookyError, ConfigurationError
from bookystats.domain.interfaces import MetadataProvider, SourceConnector
from bookystats.domain.models import (
    CollectionProgress,
    Issue,
    Source,
    SyncState,
    VerificationResult,
)
from bookystats.runtime.config import (
    Settings,
    account_from_url,
    atomic_write,
    configuration_path,
    data_directory,
    load_settings,
    save_settings,
)
from bookystats.runtime.layout import database_path, google_credentials_path
from bookystats.runtime.locking import SyncLock
from bookystats.runtime.redaction import redact
from bookystats.runtime.runlog import OperationalLog, latest_log, write_failure_log
from bookystats.runtime.scheduling import require_activation, schedule_status

if TYPE_CHECKING:
    from bookystats.domain.analytics import AnalyticsReport
    from bookystats.persistence.raw import RawDocument, RawStore


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog=S.BOOKY,
        usage=S.CLI_COMPACT_USAGE,
        description=S.PARSER_RESULT_DESCRIPTION_READ_ONLY_READING_DATA_SYNC_REPORTS_READ,
    )
    result.add_argument(S.COMMAND, choices=C.CLI_PUBLIC_COMMANDS, nargs=S.CLI_OPTIONAL_COMMAND)
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
    result.add_argument(S.CLI_STORYGRAPH_FILE, type=Path, help=S.CLI_FILE_HELP)
    result.add_argument(S.CLI_GOODREADS_FILE, type=Path, help=S.CLI_FILE_HELP)
    result.add_argument(S.CLI_GOODREADS_WATCHLIST_FILE, type=Path, help=S.CLI_SHELF_FILE_HELP)
    result.add_argument(S.CLI_GOODREADS_READ_FILE, type=Path, help=S.CLI_SHELF_FILE_HELP)
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


def _write_fetch_helper(directory: Path, settings: Settings, *, as_json: bool) -> None:
    from bookystats.adapters.exports.goodreads_helper import render_goodreads_helper

    account = next(
        (account for account in settings.accounts if account.source == Source.GOODREADS), C.NONE
    )
    if account is C.NONE:
        raise ConfigurationError(S.FETCH_ACCOUNT_REQUIRED)
    path = directory / S.LAYOUT_RUNTIME / S.FETCH_HELPER_FILE
    atomic_write(path, render_goodreads_helper(account))
    report = {
        S.COMMAND: S.FETCH,
        S.FETCH_HELPER_PATH: str(path),
        S.FETCH_READ_URL: S.FETCH_SHELF_URL.format(account_id=account.account_id, shelf=S.READ),
        S.FETCH_WATCHLIST_URL: S.FETCH_SHELF_URL.format(
            account_id=account.account_id, shelf=S.TO_READ
        ),
        S.FETCH_SCOPE_NOTICE: S.FETCH_SCOPE_MESSAGE,
    }
    if as_json:
        print(json.dumps(report, indent=C.TWO, ensure_ascii=C.TRUE))
    else:
        print(
            S.FETCH_INSTRUCTIONS.format(
                path=path,
                read_url=report[S.FETCH_READ_URL],
                watchlist_url=report[S.FETCH_WATCHLIST_URL],
                scope_notice=S.FETCH_SCOPE_MESSAGE,
            )
        )


def _build_service(
    directory: Path,
    settings: Settings,
    stack: ExitStack,
    *,
    interactive: bool,
    inputs: MutableMapping[tuple[Source, str], RawDocument] | None = C.NONE,
    archive: RawStore | None = C.NONE,
    files: Mapping[tuple[Source, str], Path | None] | None = C.NONE,
    on_event: Callable[[str], None] | None = C.NONE,
) -> SyncService:
    from bookystats.adapters.exports.csv_import import ExportConnector, FileExportConnector
    from bookystats.adapters.metadata.google_books import GoogleBooksProvider
    from bookystats.adapters.metadata.open_library import OpenLibraryProvider
    from bookystats.persistence.cache import MetadataCache, MetadataCacheError
    from bookystats.persistence.library import Database
    from bookystats.persistence.raw import RecordingFetcher

    store = Database(database_path(directory, S.LIBRARY_SQLITE3))
    store.initialize()
    stack.callback(store.close)
    connectors: dict[Source, SourceConnector] = {}
    collection_connectors: dict[tuple[Source, str], SourceConnector] = {}
    if files is C.NONE and inputs is not C.NONE:
        collection_connectors = {
            scope: ExportConnector(document) for scope, document in inputs.items()
        }
    else:
        if archive is C.NONE:
            from bookystats.persistence.raw import RawStore

            archive = RawStore(database_path(directory, S.CLI_RAW_DATABASE))
            stack.callback(archive.close)
        selected = files if files is not C.NONE else settings.files.paths(directory)
        configured = {account.source for account in settings.accounts}
        if any(
            path is not C.NONE and source not in configured
            for (source, _), path in selected.items()
        ):
            raise ConfigurationError(S.CLI_UNCONFIGURED_FILE)

        def captured(document: RawDocument) -> None:
            if inputs is not C.NONE:
                inputs[(document.source, document.collection)] = document

        collection_connectors = {
            scope: FileExportConnector(archive, path, collection=scope[C.ONE], on_capture=captured)
            for scope, path in selected.items()
            if scope[C.ZERO] in configured
        }
    providers: dict[Source, MetadataProvider] = {}
    provider_issues: dict[Source, Issue] = {}
    provider_factories: dict[Source, Callable[[], MetadataProvider | Issue]] = {}
    key = os.environ.get(S.GOOGLE_BOOKS_API_KEY, S.EMPTY).strip()
    token: str | None = C.NONE
    deferred_google = (
        settings.metadata.google_books
        and settings.metadata.open_library
        and settings.metadata.strategy == S.ENR_STRATEGY_OPEN_LIBRARY_FIRST
        and not key
    )
    if settings.metadata.google_books and not key and not deferred_google:
        from bookystats.adapters.google_oauth import AuthorizationRequired, ensure_access_token

        try:
            token = ensure_access_token(directory, interactive=interactive)
        except AuthorizationRequired as exc:
            provider_issues[Source.GOOGLE_BOOKS] = Issue(
                code=S.OAUTH_AUTHORIZATION_REQUIRED_CODE, message=str(exc)
            )
        except ConfigurationError as exc:
            provider_issues[Source.GOOGLE_BOOKS] = Issue(code=S.OAUTH_ISSUE_CODE, message=str(exc))
        else:
            if token is C.NONE:
                provider_issues[Source.GOOGLE_BOOKS] = Issue(
                    code=S.OAUTH_AUTHORIZATION_REQUIRED_CODE,
                    message=S.OAUTH_AUTHORIZATION_REQUIRED,
                )
    needed = [
        source
        for source, configured in (
            (
                Source.GOOGLE_BOOKS,
                settings.metadata.google_books and (bool(key or token) or deferred_google),
            ),
            (Source.OPEN_LIBRARY, settings.metadata.open_library),
        )
        if configured
    ]
    cache: MetadataCache | None = C.NONE
    if needed:
        try:
            cache = MetadataCache(database_path(directory, S.METADATA_SQLITE3))
        except MetadataCacheError as exc:
            provider_issues.update(
                {source: Issue(code=S.METADATA_CACHE_ERROR, message=str(exc)) for source in needed}
            )
        else:
            stack.callback(cache.close)

    def google_provider() -> MetadataProvider | Issue:
        access_token = token
        if deferred_google:
            from bookystats.adapters.google_oauth import AuthorizationRequired, ensure_access_token

            try:
                access_token = ensure_access_token(directory, interactive=interactive)
            except AuthorizationRequired as exc:
                return Issue(code=S.OAUTH_AUTHORIZATION_REQUIRED_CODE, message=str(exc))
            except ConfigurationError as exc:
                return Issue(code=S.OAUTH_ISSUE_CODE, message=str(exc))
            if access_token is C.NONE:
                return Issue(
                    code=S.OAUTH_AUTHORIZATION_REQUIRED_CODE,
                    message=S.OAUTH_AUTHORIZATION_REQUIRED,
                )
        google_http = stack.enter_context(
            HttpClient(
                allowed_hosts=(S.WWW_GOOGLEAPIS_COM,),
                timeout=settings.http_timeout_seconds,
                max_requests=settings.metadata.max_books_per_run * C.FOUR,
                max_attempts=C.ONE,
                retry_store=cache,
                provider=Source.GOOGLE_BOOKS,
            )
        )
        return GoogleBooksProvider(
            RecordingFetcher(google_http, archive, source=Source.GOOGLE_BOOKS)
            if archive is not C.NONE
            else google_http,
            api_key=key,
            access_token=access_token,
            cache=cache,
        )

    if settings.metadata.google_books and cache is not C.NONE:
        if deferred_google:
            provider_factories[Source.GOOGLE_BOOKS] = google_provider
        elif key or token:
            initialized = google_provider()
            if isinstance(initialized, Issue):
                provider_issues[Source.GOOGLE_BOOKS] = initialized
            else:
                providers[Source.GOOGLE_BOOKS] = initialized
    if settings.metadata.open_library and cache is not C.NONE:
        user_agent = S.CLI_BUILD_SERVICE_USER_AGENT_BOOKYSTATS
        if settings.metadata.contact:
            user_agent += S.CLI_BUILD_SERVICE_TEMPLATE.format(v0=settings.metadata.contact)
        library_http = stack.enter_context(
            HttpClient(
                allowed_hosts=(S.OPENLIBRARY_ORG,),
                timeout=settings.http_timeout_seconds,
                min_interval=C.ONE,
                max_requests=settings.metadata.max_books_per_run * C.THREE,
                user_agent=user_agent,
                retry_store=cache,
                provider=Source.OPEN_LIBRARY,
            )
        )
        providers[Source.OPEN_LIBRARY] = OpenLibraryProvider(
            RecordingFetcher(library_http, archive, source=Source.OPEN_LIBRARY)
            if archive is not C.NONE
            else library_http,
            cache=cache,
            work_details=C.TRUE,
        )

    def notify(message: str) -> None:
        print(redact(message, _secrets()), file=sys.stderr, flush=C.TRUE)
        if on_event is not C.NONE:
            on_event(message)

    collection_progress: dict[tuple[Source, str], float] = {}
    metadata_buckets: dict[tuple[Source, int], int] = {}

    def progress(event: CollectionProgress) -> None:
        key = (event.source, event.collection)
        now = monotonic()
        previous = collection_progress.get(key)
        if previous is C.NONE or now - previous >= C.LOG2_PROGRESS_SECONDS:
            collection_progress[key] = now
            notify(
                S.CLI_BUILD_SERVICE_PROGRESS_TEMPLATE.format(
                    v0=event.source.value, v1=event.collection, v2=event.pages_seen
                )
            )

    def source_complete(receipt: SourceReceipt) -> None:
        notify(
            (
                S.LOG2_SOURCE if receipt.state == SyncState.COMPLETE else S.LOG2_SOURCE_RETAINED
            ).format(
                source=receipt.source.value,
                collection=receipt.collection,
                state=receipt.state.value,
                records=receipt.records,
            )
        )

    def metadata_progress(source: Source, completed: int, total: int) -> None:
        bucket = (
            min(C.LOG2_PROGRESS_BUCKETS, completed * C.LOG2_PROGRESS_BUCKETS // total)
            if total > C.ZERO
            else C.ZERO
        )
        key = (source, total)
        previous = metadata_buckets.get(key)
        if previous is C.NONE or bucket > previous:
            metadata_buckets[key] = bucket
            notify(
                S.LOG2_METADATA_PROGRESS.format(
                    source=source.value,
                    completed=completed,
                    total=total,
                    percent=completed * C.LOG2_PROGRESS_PERCENT // total if total else C.ZERO,
                )
            )

    from bookystats.application.analytics import AnalyticsService
    from bookystats.application.products import ProductsService
    from bookystats.application.recommendations import RecommendationService
    from bookystats.application.reporting import render_library_report
    from bookystats.persistence.analytics import AnalyticsStore
    from bookystats.persistence.products import ReportBundleStore
    from bookystats.persistence.recommendations import RecommendationStore

    analytics: AnalyticsService | None = C.NONE
    products: ProductsService | None = C.NONE
    if settings.analytics.enabled:
        analysis_store = AnalyticsStore(database_path(directory, S.AN_DATABASE))
        stack.callback(analysis_store.close)
        analytics = AnalyticsService(store, analysis_store)
        recommendations = RecommendationStore(database_path(directory, S.AN_DATABASE))
        stack.callback(recommendations.close)

        def provider_status() -> Mapping[str, JsonValue]:
            value = store.status().get(S.METADATA)
            if not isinstance(value, dict):
                raise ConfigurationError(S.PROD_INVALID_PROVIDER_STATUS)
            return value

        products = ProductsService(
            store,
            analysis_store,
            ReportBundleStore(directory),
            recommend=RecommendationService(recommendations).run,
            provider_status=provider_status,
            render_pdf=render_library_report,
        )

    return SyncService(
        store,
        settings,
        connectors,
        providers,
        on_progress=progress,
        provider_issues=provider_issues,
        provider_factories=provider_factories,
        collection_connectors=collection_connectors,
        on_source_complete=source_complete,
        on_metadata_progress=metadata_progress,
        analytics=analytics,
        products=products,
        on_event=on_event,
    )


def _print_receipt(receipt: SyncReceipt, output: TextIO, *, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(receipt.model_dump(mode=S.JSON), indent=C.TWO, ensure_ascii=C.TRUE),
            file=output,
        )
        return
    for line in run_lines(receipt, issue_limit=C.FIVE):
        print(line, file=output)
    if receipt.log_file is not C.NONE:
        print(S.REPORT_RUN_LOG_LINE.format(path=receipt.log_file), file=output)


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return C.NONE


def _status(directory: Path, settings: Settings) -> dict[str, JsonValue]:
    path = database_path(directory, S.LIBRARY_SQLITE3)
    saved = library_status(path) if path.exists() else C.NONE
    report: dict[str, JsonValue] = (
        saved
        if saved is not C.NONE
        else {
            S.LIBRARY: {},
            S.SOURCES: [],
            S.LAST_RUN: C.NONE,
            S.STATE: S.DBSAFE_STATE_UNAVAILABLE if path.exists() else S.NOT_SYNCED,
        }
    )
    report[S.DATA_DIRECTORY] = str(directory)
    analysis_path = database_path(directory, S.AN_DATABASE)
    latest: AnalyticsReport | None = C.NONE
    if analysis_path.is_file():
        latest = latest_analytics(analysis_path)
        report[S.AN_ANALYTICS] = latest.model_dump(mode=S.JSON) if latest is not C.NONE else C.NONE
    from bookystats.persistence.products import ReportBundleStore

    products = ReportBundleStore(directory).latest(current=latest)
    if products is not C.NONE:
        report[S.PROD_PRODUCTS] = products.model_dump(mode=S.JSON)
    report[S.CONFIGURED_SOURCES] = [account.source.value for account in settings.accounts]
    report[S.SCHEDULE] = schedule_status(directory, settings)
    report[S.GOOGLE_BOOKS_KEY_CONFIGURED] = bool(os.environ.get(S.GOOGLE_BOOKS_API_KEY))
    report[S.GOOGLE_BOOKS_OAUTH_SAVED] = google_credentials_path(directory).is_file()
    raw_path = database_path(directory, S.CLI_RAW_DATABASE)
    library_path = database_path(directory, S.LIBRARY_SQLITE3)
    newest_log = latest_log(directory)
    report[S.CLI_RAW_ARCHIVE] = str(raw_path) if raw_path.exists() else C.NONE
    report[S.RAW_ARCHIVE_BYTES] = _file_size(raw_path)
    report[S.LIBRARY_DATABASE] = str(library_path) if library_path.exists() else C.NONE
    report[S.LIBRARY_BYTES] = _file_size(library_path)
    report[S.LATEST_LOG] = str(newest_log) if newest_log is not C.NONE else C.NONE
    report[S.CSV_CONFIGURATION_PATH] = str(configuration_path(directory))
    report[S.DBSAFE_STORAGE] = storage_report(directory)
    configured = {account.source for account in settings.accounts}
    report[S.CSV_INPUTS] = [
        {
            S.SOURCE: source.value,
            S.COLLECTION: collection,
            S.CSV_INPUT_PATH: str(path) if path is not C.NONE else C.NONE,
            S.CSV_INPUT_EXISTS: path.is_file() if path is not C.NONE else C.FALSE,
        }
        for (source, collection), path in settings.files.paths(directory).items()
        if source in configured
    ]
    return report


def _print_status(report: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=C.TWO, ensure_ascii=C.TRUE))
        return
    for line in status_lines(report):
        print(line)
    for line in attention_lines(report):
        print(line)


def _secrets() -> tuple[str, ...]:
    return (
        os.environ.get(S.GOOGLE_BOOKS_API_KEY, S.EMPTY),
        os.environ.get(S.OAUTH_CLIENT_ID_ENV, S.EMPTY),
        os.environ.get(S.OAUTH_CLIENT_SECRET_ENV, S.EMPTY),
    )


def _trigger(args: argparse.Namespace) -> str:
    return S.SCHEDULED if args.scheduled else S.INPUT_FILE


def _succeeded(receipt: SyncReceipt) -> bool:
    return receipt.state == SyncState.COMPLETE and (
        receipt.verification is C.NONE or receipt.verification.result == VerificationResult.SUCCESS
    )


def _archive_inputs(
    directory: Path,
    settings: Settings,
    files: Mapping[tuple[Source, str], Path | None],
    stack: ExitStack,
) -> tuple[RawStore, dict[tuple[Source, str], RawDocument]]:
    from bookystats.persistence.raw import RawStore

    archive = RawStore(database_path(directory, S.CLI_RAW_DATABASE))
    stack.callback(archive.close)
    configured = {account.source for account in settings.accounts}
    if any(path is not C.NONE and source not in configured for (source, _), path in files.items()):
        raise ConfigurationError(S.CLI_UNCONFIGURED_FILE)
    inputs: dict[tuple[Source, str], RawDocument] = {}
    for account in settings.accounts:
        for source, collection in C.MANUAL_INPUT_SCOPES:
            if source != account.source:
                continue
            path = files.get((source, collection))
            document = (
                archive.capture_file(account, path, collection=collection)
                if path is not C.NONE
                else archive.latest(
                    source,
                    account.account_id,
                    collection=collection,
                    media_type=S.RAW_CSV_MEDIA_TYPE,
                )
            )
            if document is not C.NONE:
                inputs[(source, collection)] = document
    if (Source.GOODREADS, S.LIBRARY) in inputs and any(
        (Source.GOODREADS, collection) in inputs for collection in (S.TO_READ, S.READ)
    ):
        raise ConfigurationError(S.CLI_GOODREADS_SCOPE_CONFLICT)
    if not inputs:
        raise ConfigurationError(S.CLI_NO_RAW_INPUT)
    return archive, inputs


def _record_failure(directory: Path, command: str, message: str) -> None:
    if command != S.SYNC:
        return
    try:
        path = write_failure_log(directory, message, secrets=_secrets())
    except OSError:
        print(S.CLI_LOG_WRITE_WARNING, file=sys.stderr)
        return
    print(S.REPORT_RUN_LOG_LINE.format(path=path), file=sys.stderr)


def main(argv: list[str] | None = C.NONE) -> int:
    arguments = parser()
    args = arguments.parse_args(argv)
    if args.command is C.NONE:
        print(S.CLI_QUICK_HELP)
        return C.ZERO
    file_input = bool(
        args.storygraph_file
        or args.goodreads_file
        or args.goodreads_watchlist_file
        or args.goodreads_read_file
    )
    if args.goodreads_file and (args.goodreads_watchlist_file or args.goodreads_read_file):
        arguments.error(S.CLI_GOODREADS_SCOPE_CONFLICT)
    if file_input and (args.interactive or args.scheduled):
        arguments.error(S.CLI_FILE_MODE_CONFLICT)
    if args.command != S.SYNC and file_input:
        arguments.error(S.CLI_STATUS_FILE_CONFLICT)
    if args.command == S.FETCH and args.scheduled:
        arguments.error(S.FETCH_SCHEDULED_CONFLICT)
    directory = data_directory(args.data_dir)
    active_log: OperationalLog | None = C.NONE
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
        if args.command == S.FETCH:
            _write_fetch_helper(directory, settings, as_json=args.json)
            return C.ZERO
        with SyncLock(directory) as sync_lock, ExitStack() as stack:
            trigger = _trigger(args)
            active_log = stack.enter_context(
                OperationalLog(
                    directory,
                    trigger=trigger,
                    secrets=(*_secrets(), str(directory)),
                    compact_receipts=C.TRUE,
                )
            )
            if sync_lock.migrated_files:
                active_log.event(S.LAYOUT_MIGRATED.format(count=len(sync_lock.migrated_files)))
            if args.scheduled:
                require_activation(directory, Path(sys.executable), settings)
            inputs: dict[tuple[Source, str], RawDocument] = {}
            files: dict[tuple[Source, str], Path | None] = {}
            archive: RawStore | None = C.NONE
            if file_input:
                files = {
                    (Source.STORYGRAPH, S.LIBRARY): args.storygraph_file,
                    (Source.GOODREADS, S.LIBRARY): args.goodreads_file,
                    (Source.GOODREADS, S.TO_READ): args.goodreads_watchlist_file,
                    (Source.GOODREADS, S.READ): args.goodreads_read_file,
                }
                archive, inputs = _archive_inputs(directory, settings, files, stack)
            else:
                from bookystats.persistence.raw import RawStore

                archive = RawStore(database_path(directory, S.CLI_RAW_DATABASE))
                stack.callback(archive.close)
                files = settings.files.paths(directory)
            service = _build_service(
                directory,
                settings,
                stack,
                interactive=interactive,
                inputs=inputs,
                archive=archive,
                files=files if not file_input else C.NONE,
                on_event=active_log.event,
            )
            receipt = service.run(interactive=interactive, trigger=trigger)
            if archive is not C.NONE:
                verification = verify_run(
                    receipt, archive=archive, library=service.store, inputs=inputs, supplied=files
                )
                receipt = receipt.model_copy(update={S.VERIFICATION: verification})
            path = active_log.finish(
                receipt,
                inputs=inputs,
                report_lines=(),
                delivery_issues=receipt.products.issues if receipt.products is not C.NONE else (),
            )
            receipt = receipt.model_copy(update={S.LOG_FILE: str(path)})
            _print_receipt(receipt, sys.stdout, as_json=args.json)
            return C.ZERO if _succeeded(receipt) else C.THREE
    except AlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        return C.FOUR
    except BookyError as exc:
        message = redact(str(exc), _secrets())
        print(message, file=sys.stderr)
        if active_log is C.NONE:
            _record_failure(directory, args.command, message)
        return C.ONE
    except (sqlite3.Error, OSError, ValidationError) as exc:
        print(S.CLI_MAIN_A_LOCAL_DATA_CONFIGURATION_OR_RECORD_VALIDATION, file=sys.stderr)
        if active_log is C.NONE:
            _record_failure(
                directory, args.command, S.RUNLOG_FAILURE_TYPE.format(type=type(exc).__name__)
            )
        return C.ONE
    except (KeyboardInterrupt, EOFError):
        print(S.CLI_MAIN_SYNC_INTERRUPTED_NO_INCOMPLETE_SOURCE_SNAPSHOT_IS, file=sys.stderr)
        if active_log is C.NONE:
            _record_failure(
                directory,
                args.command,
                S.CLI_MAIN_SYNC_INTERRUPTED_NO_INCOMPLETE_SOURCE_SNAPSHOT_IS,
            )
        return C.CLI_MAIN
