from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import HttpClient
from bookystats.application.sync import SourceReceipt, SyncReceipt
from bookystats.cli import commands as cli
from bookystats.cli.commands import main
from bookystats.domain.errors import ConfigurationError
from bookystats.domain.interfaces import HttpResponse
from bookystats.domain.models import (
    CollectionProgress,
    Issue,
    Source,
    SyncState,
    VerificationResult,
)
from bookystats.persistence.library import Database
from bookystats.runtime import scheduling
from bookystats.runtime.config import (
    MetadataSettings,
    Settings,
    WeeklySettings,
    atomic_write,
    save_settings,
)
from bookystats.runtime.layout import database_path
from tests.support.exports import csv_body
from tests.support.scheduling import activation
from tests.support.sources import accounts


@pytest.mark.parametrize(S.LOG2_TEST_LARGE_TOTAL, (C.ZERO, C.ONE, C.LOG2_TEST_LARGE_TOTAL))
def test_metadata_progress_is_percentage_bounded_without_timeout_boilerplate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], total: int
) -> None:
    events: list[str] = []
    with ExitStack() as stack:
        service = cli._build_service(
            tmp_path,
            Settings(
                accounts=accounts(),
                metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
            ),
            stack,
            interactive=C.FALSE,
            inputs={},
            on_event=events.append,
        )
        assert service.on_metadata_progress is not C.NONE
        for completed in range(total + C.ONE):
            service.on_metadata_progress(Source.OPEN_LIBRARY, completed, total)
        service.on_metadata_progress(Source.OPEN_LIBRARY, total, total)
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == len(events) <= C.LOG2_PROGRESS_BUCKETS + C.ONE
    assert lines[C.ZERO] == S.LOG2_METADATA_PROGRESS.format(
        source=S.OPEN_LIBRARY, completed=C.ZERO, total=total, percent=C.ZERO
    )
    assert lines[-C.ONE] == S.LOG2_METADATA_PROGRESS.format(
        source=S.OPEN_LIBRARY,
        completed=total,
        total=total,
        percent=C.LOG2_PROGRESS_PERCENT if total else C.ZERO,
    )
    assert all(S.LOG2_TEST_ZERO_TIMEOUT not in line for line in lines)


def test_source_progress_is_time_bounded_and_completion_has_no_row_examples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    events: list[str] = []
    monkeypatch.setattr(cli, S.LOG2_TEST_MONOTONIC, lambda: C.ZERO)
    with ExitStack() as stack:
        service = cli._build_service(
            tmp_path,
            Settings(
                accounts=accounts(),
                metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
            ),
            stack,
            interactive=C.FALSE,
            inputs={},
            on_event=events.append,
        )
        assert service.on_progress is not C.NONE
        for page in range(C.ONE, C.LOG2_TEST_LARGE_TOTAL + C.ONE):
            service.on_progress(
                CollectionProgress(source=Source.GOODREADS, collection=S.READ, pages_seen=page)
            )
        monkeypatch.setattr(cli, S.LOG2_TEST_MONOTONIC, lambda: C.LOG2_PROGRESS_SECONDS)
        service.on_progress(
            CollectionProgress(
                source=Source.GOODREADS,
                collection=S.READ,
                pages_seen=C.LOG2_TEST_LARGE_TOTAL + C.ONE,
            )
        )
        assert service.on_source_complete is not C.NONE
        service.on_source_complete(
            SourceReceipt(
                source=Source.GOODREADS,
                collection=S.READ,
                state=SyncState.COMPLETE,
                records=C.LOG2_TEST_LARGE_TOTAL,
                issues=(
                    Issue(
                        code=S.DQ_CAPTURE_UNVERIFIED_CODE,
                        message=S.TEST_REPORTING_MESSAGE_ONE,
                    ),
                ),
            )
        )
        service.on_source_complete(
            SourceReceipt(
                source=Source.GOODREADS,
                collection=S.READ,
                state=SyncState.FAILED,
            )
        )
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == len(events) == C.FOUR
    assert S.TEST_REPORTING_MESSAGE_ONE not in S.NEWLINE.join(lines)
    assert lines[-C.TWO] == S.LOG2_SOURCE.format(
        source=S.GOODREADS,
        collection=S.READ,
        state=S.COMPLETE,
        records=C.LOG2_TEST_LARGE_TOTAL,
    )
    assert lines[-C.ONE] == S.LOG2_SOURCE_RETAINED.format(
        source=S.GOODREADS, collection=S.READ, state=S.FAILED
    )


def test_status_is_local_and_does_not_create_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    monkeypatch.setenv(S.GOOGLE_BOOKS_API_KEY, S.DO_NOT_PRINT_THIS)
    assert main([S.STATUS, S.CLI_PARSER_JSON, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ZERO
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report[S.STATE] == S.NOT_SYNCED
    assert report[S.GOOGLE_BOOKS_KEY_CONFIGURED] is C.TRUE
    assert report[S.SCHEDULE][S.ENABLED_2] is C.FALSE
    assert S.DO_NOT_PRINT_THIS not in captured.out
    assert list(tmp_path.iterdir()) == []


def test_status_reads_legacy_database_without_moving_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    legacy = tmp_path / S.LIBRARY_SQLITE3
    library = Database(legacy)
    try:
        library.initialize()
    finally:
        library.close()
    assert main([S.STATUS, S.CLI_PARSER_JSON, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ZERO
    report = json.loads(capsys.readouterr().out)
    assert report[S.LIBRARY_DATABASE] == str(legacy)
    assert legacy.is_file()
    assert not (tmp_path / S.LAYOUT_DATABASES).exists()
    assert not (tmp_path / S.LAYOUT_RUNTIME).exists()


def test_unattended_without_accounts_never_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)

    def unexpected_input(prompt: str) -> str:
        pytest.fail(S.TEST_CLI_UNATTENDED_WITHOUT_INPUT_UNATTENDED_EXECUTION_PROMPTED)

    monkeypatch.setattr(S.BUILTINS_INPUT, unexpected_input)
    assert main([S.SYNC, S.CLI_PARSER_UNATTENDED, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ONE
    assert S.CLI_MAIN_CONFIGURE_READER_PROFILE_URLS_IN_CONFIG_JSON in capsys.readouterr().err
    assert not database_path(tmp_path, S.LIBRARY_SQLITE3).exists()
    assert not (tmp_path / S.CONFIG_JSON).exists()


def test_first_terminal_sync_saves_selected_profiles_before_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from bookystats.runtime.config import load_settings

    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    chosen = accounts()
    answers = iter(account.profile_url for account in chosen)
    monkeypatch.setattr(cli.sys.stdin, S.CLI_TEST_ISATTY, lambda: C.TRUE)
    monkeypatch.setattr(S.BUILTINS_INPUT, lambda prompt: next(answers))

    def configured_service(
        directory: Path, settings: Settings, *args: object, **kwargs: object
    ) -> None:
        assert settings.accounts == chosen
        assert load_settings(directory).accounts == chosen
        raise ConfigurationError(S.CLI_TEST_SCHEDULE_GUARD)

    monkeypatch.setattr(cli, S.TEST_BUILD_SERVICE, configured_service)
    assert main([S.SYNC, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ONE
    assert S.CLI_TEST_SCHEDULE_GUARD in capsys.readouterr().err
    assert load_settings(tmp_path).accounts == chosen
    assert not database_path(tmp_path, S.LIBRARY_SQLITE3).exists()


def test_disabled_scheduled_run_never_collects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    assert main([S.SYNC, S.CLI_PARSER_SCHEDULED, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ZERO
    assert S.DISABLED in capsys.readouterr().out
    assert not database_path(tmp_path, S.LIBRARY_SQLITE3).exists()


def test_nonpublic_command_is_rejected() -> None:
    with pytest.raises(SystemExit) as failure:
        main([S.EXPORT])
    assert failure.value.code == C.TWO


def test_fetch_writes_a_helper_without_network_database_or_configuration_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    monkeypatch.setenv(S.GOOGLE_BOOKS_API_KEY, S.DO_NOT_PRINT_THIS)
    save_settings(tmp_path, Settings(accounts=accounts()))
    configuration = (tmp_path / S.CONFIG_JSON).read_bytes()

    def unexpected_service(*args: object, **kwargs: object) -> None:
        pytest.fail(S.CLI_TEST_UNEXPECTED_NETWORK)

    monkeypatch.setattr(cli, S.TEST_BUILD_SERVICE, unexpected_service)
    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, unexpected_service)
    assert main([S.FETCH, S.CLI_PARSER_DATA_DIR, str(tmp_path), S.CLI_PARSER_JSON]) == C.ZERO
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report[S.COMMAND] == S.FETCH
    helper = Path(report[S.FETCH_HELPER_PATH])
    assert helper == tmp_path / S.LAYOUT_RUNTIME / S.FETCH_HELPER_FILE
    script = helper.read_text(encoding=S.UTF_8)
    assert S.FETCH_ACCOUNT_PLACEHOLDER not in script
    assert json.dumps(accounts()[C.ONE].account_id) in script
    assert S.DO_NOT_PRINT_THIS not in script + captured.out + captured.err
    assert (tmp_path / S.CONFIG_JSON).read_bytes() == configuration
    assert all(not database_path(tmp_path, name).exists() for name in C.CLI_LOCAL_DATABASES)


def test_fetch_requires_a_configured_goodreads_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    save_settings(tmp_path, Settings(accounts=accounts()[: C.ONE]))
    assert main([S.FETCH, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ONE
    assert S.FETCH_ACCOUNT_REQUIRED in capsys.readouterr().err
    assert not (tmp_path / S.LAYOUT_RUNTIME / S.FETCH_HELPER_FILE).exists()


@pytest.mark.parametrize(S.CLI_TEST_RETIRED_OPTION, C.CLI_FETCH_REJECTED_OPTIONS)
def test_fetch_rejects_input_and_scheduled_collection_options(option: str) -> None:
    arguments = [S.FETCH, option]
    if option == S.CLI_STORYGRAPH_FILE:
        arguments.append(S.CLI_TEST_STORYGRAPH_NAME)
    with pytest.raises(SystemExit) as failure:
        main(arguments)
    assert failure.value.code == C.TWO


def test_bare_invocation_shows_short_guide_without_touching_data(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def unexpected_directory(*args: object) -> Path:
        pytest.fail(S.CLI_TEST_UNEXPECTED_NETWORK)

    monkeypatch.setattr(cli, S.DATA_DIRECTORY, unexpected_directory)
    assert main([]) == C.ZERO
    captured = capsys.readouterr()
    assert captured.out == S.CLI_QUICK_HELP + S.NEWLINE
    assert captured.err == S.EMPTY
    assert S.CLI_GOODREADS_FILE not in captured.out


@pytest.mark.parametrize(S.CLI_TEST_RETIRED_OPTION, C.CLI_RETIRED_OPTIONS)
def test_separate_setup_and_metadata_selection_options_are_removed(option: str) -> None:
    with pytest.raises(SystemExit) as failure:
        main([S.SYNC, option])
    assert failure.value.code == C.TWO


@pytest.mark.parametrize(S.CLI_TEST_INTERACTIVE_PARAMETER, C.CLI_TEST_INTERACTIVITY)
def test_google_credentials_are_automatically_resolved_during_sync_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interactive: bool
) -> None:
    from bookystats.adapters import google_oauth

    calls: list[bool] = []

    def ensure_token(directory: Path, *, interactive: bool) -> str:
        assert directory == tmp_path
        calls.append(interactive)
        return S.DO_NOT_PRINT_THIS

    monkeypatch.delenv(S.GOOGLE_BOOKS_API_KEY, raising=C.FALSE)
    monkeypatch.setattr(google_oauth, S.CLI_TEST_ENSURE_TOKEN, ensure_token)
    settings = Settings(
        accounts=accounts(),
        metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
    )
    with ExitStack() as stack:
        service = cli._build_service(tmp_path, settings, stack, interactive=interactive, inputs={})
        assert Source.GOOGLE_BOOKS in service.providers
        assert len(service.providers) == C.ONE
    assert calls == [interactive]


def test_missing_headless_google_authorization_is_explicit_and_never_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bookystats.adapters import google_oauth

    def ensure_token(directory: Path, *, interactive: bool) -> None:
        assert not interactive

    monkeypatch.delenv(S.GOOGLE_BOOKS_API_KEY, raising=C.FALSE)
    monkeypatch.setattr(google_oauth, S.CLI_TEST_ENSURE_TOKEN, ensure_token)
    settings = Settings(
        accounts=accounts(),
        metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
    )
    with ExitStack() as stack:
        service = cli._build_service(tmp_path, settings, stack, interactive=C.FALSE, inputs={})
        assert Source.GOOGLE_BOOKS not in service.providers
        metadata = service._metadata(Source.GOOGLE_BOOKS)
        assert metadata.state == SyncState.NEEDS_AUTH
        assert metadata.issues[C.ZERO].code == S.OAUTH_AUTHORIZATION_REQUIRED_CODE


@pytest.mark.parametrize(S.CLI_TEST_INTERACTIVE_PARAMETER, C.CLI_TEST_INTERACTIVITY)
def test_fallback_does_not_authorize_google_before_due_gaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interactive: bool
) -> None:
    from bookystats.adapters import google_oauth

    def unexpected_authorization(*args: object, **kwargs: object) -> None:
        pytest.fail(S.CLI_TEST_UNEXPECTED_NETWORK)

    monkeypatch.delenv(S.GOOGLE_BOOKS_API_KEY, raising=C.FALSE)
    monkeypatch.setattr(google_oauth, S.CLI_TEST_ENSURE_TOKEN, unexpected_authorization)
    with ExitStack() as stack:
        service = cli._build_service(
            tmp_path, Settings(accounts=accounts()), stack, interactive=interactive, inputs={}
        )
        assert Source.GOOGLE_BOOKS not in service.providers
        assert Source.GOOGLE_BOOKS in service.provider_factories
        receipt = service._metadata(Source.GOOGLE_BOOKS)
        assert receipt.state == SyncState.COMPLETE
        assert receipt.coverage_scope == S.ENR_CORE_COVERAGE_SCOPE
        assert receipt.requested == receipt.processed == C.ZERO


def test_scheduled_run_rejects_changed_code_before_constructing_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    settings = Settings(
        accounts=accounts(),
        weekly=WeeklySettings(
            enabled=C.TRUE, weekday=S.MON, time=S.SETTINGS_WEEKLY_TIME_TEXT, timezone=S.UTC
        ),
    )
    save_settings(tmp_path, settings)
    atomic_write(tmp_path / S.SCHEDULE_JSON, activation(tmp_path, settings).model_dump_json())
    monkeypatch.setattr(scheduling, S.TEST_SCHEDULING_FINGERPRINT, lambda: S.NEW)

    def unexpected_service(*args: object, **kwargs: object) -> None:
        pytest.fail(S.TEST_UNEXPECTED_SERVICE_START)

    monkeypatch.setattr(cli, S.TEST_BUILD_SERVICE, unexpected_service)
    assert main([S.SYNC, S.CLI_PARSER_SCHEDULED, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ONE
    assert S.SCHEDULE_REVALIDATION_REQUIRED in capsys.readouterr().err
    assert not database_path(tmp_path, S.LIBRARY_SQLITE3).exists()


def test_explicit_files_publish_with_raw_lineage_and_reuse_other_archived_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from bookystats.persistence.raw import RawStore

    def unexpected_fetch(*args: object, **kwargs: object) -> None:
        pytest.fail(S.CLI_TEST_UNEXPECTED_NETWORK)

    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, unexpected_fetch)
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    storygraph = tmp_path / S.CLI_TEST_STORYGRAPH_NAME
    goodreads = tmp_path / S.CLI_TEST_GOODREADS_NAME
    storygraph.write_text(S.CLI_TEST_STORYGRAPH_CSV, encoding=S.UTF_8)
    goodreads.write_text(S.CLI_TEST_GOODREADS_CSV, encoding=S.UTF_8)

    def unexpected_schedule(*args: object, **kwargs: object) -> None:
        pytest.fail(S.CLI_TEST_MANUAL_SCHEDULE)

    monkeypatch.setattr(scheduling, S.CLI_TEST_RECORD_LIVE, unexpected_schedule)
    monkeypatch.setattr(scheduling, S.CLI_TEST_ENABLE_WEEKLY, unexpected_schedule)
    save_settings(
        tmp_path,
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
            weekly=WeeklySettings(
                enabled=C.TRUE, weekday=S.MON, time=S.SETTINGS_WEEKLY_TIME_TEXT, timezone=S.UTC
            ),
        ),
    )
    base = [
        S.SYNC,
        S.CLI_PARSER_DATA_DIR,
        str(tmp_path),
        S.CLI_PARSER_JSON,
    ]
    assert (
        main([*base, S.CLI_STORYGRAPH_FILE, str(storygraph), S.CLI_GOODREADS_FILE, str(goodreads)])
        == C.ZERO
    )
    receipt = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert receipt.state == SyncState.COMPLETE
    assert not receipt.account_sync_complete
    assert all(item.input_kind == S.INPUT_FILE and item.raw_document_id for item in receipt.sources)
    assert not (tmp_path / S.PROFILES).exists()
    assert not (tmp_path / S.STABILITY_JSON).exists()
    archive = RawStore(database_path(tmp_path, S.CLI_RAW_DATABASE))
    try:
        document = archive.latest(Source.STORYGRAPH, accounts()[C.ZERO].account_id)
        assert document is not C.NONE
        assert document.body == storygraph.read_bytes()
    finally:
        archive.close()
    storygraph.unlink()
    assert main([*base, S.CLI_GOODREADS_FILE, str(goodreads)]) == C.ZERO
    replay = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert replay.sources[C.ZERO].raw_document_id == receipt.sources[C.ZERO].raw_document_id
    assert replay.sources[C.ONE].raw_document_id != receipt.sources[C.ONE].raw_document_id
    assert all(
        item.publication is not C.NONE
        and item.publication.added == C.ZERO
        and item.publication.unchanged == C.ONE
        for item in replay.sources
    )
    database = Database(database_path(tmp_path, S.LIBRARY_SQLITE3))
    try:
        records = database.active_records()
        assert len(records) == C.TWO
        assert all(
            record.raw_fields[S.CLI_TEST_EXTRA_COLUMN] == S.CLI_TEST_EXTRA_VALUE
            for record in records
        )
    finally:
        database.close()
    storygraph.write_text(S.CLI_TEST_BROKEN_CSV, encoding=S.UTF_8)
    assert main([*base, S.CLI_STORYGRAPH_FILE, str(storygraph)]) == C.THREE
    failure = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert failure.sources[C.ZERO].publication is C.NONE
    archive = RawStore(database_path(tmp_path, S.CLI_RAW_DATABASE))
    try:
        broken = archive.latest(Source.STORYGRAPH, accounts()[C.ZERO].account_id)
        assert broken is not C.NONE and broken.body == storygraph.read_bytes()
    finally:
        archive.close()
    database = Database(database_path(tmp_path, S.LIBRARY_SQLITE3))
    try:
        assert database.active_records() == records
    finally:
        database.close()


@pytest.mark.parametrize(S.CLI_TEST_INTERACTIVE_PARAMETER, C.CLI_TEST_INTERACTIVITY)
def test_plain_sync_selects_configured_csvs_instead_of_live_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    interactive: bool,
) -> None:
    save_settings(tmp_path, Settings(accounts=accounts()))

    def fresh_service(*args: object, inputs: object, archive: object, **kwargs: object) -> None:
        assert inputs == {}
        assert archive is not C.NONE
        assert kwargs[S.CSV_FILES_KEY] == Settings().files.paths(tmp_path)
        assert kwargs[S.CLI_TEST_INTERACTIVE_PARAMETER] is interactive
        raise ConfigurationError(S.CLI_TEST_SCHEDULE_GUARD)

    monkeypatch.setattr(cli.sys.stdin, S.CLI_TEST_ISATTY, lambda: interactive)
    monkeypatch.setattr(cli, S.TEST_BUILD_SERVICE, fresh_service)
    assert main([S.SYNC, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ONE
    assert S.CLI_TEST_SCHEDULE_GUARD in capsys.readouterr().err
    assert not database_path(tmp_path, S.LIBRARY_SQLITE3).exists()


def test_scheduled_capture_cannot_enable_interactive_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    save_settings(
        tmp_path,
        Settings(
            accounts=accounts(),
            weekly=WeeklySettings(
                enabled=C.TRUE, weekday=S.MON, time=S.SETTINGS_WEEKLY_TIME_TEXT, timezone=S.UTC
            ),
        ),
    )
    monkeypatch.setattr(cli, S.CLI_TEST_REQUIRE_ACTIVATION, lambda *args, **kwargs: C.NONE)

    def scheduled_service(*args: object, interactive: bool, **kwargs: object) -> None:
        assert not interactive
        raise ConfigurationError(S.CLI_TEST_SCHEDULE_GUARD)

    monkeypatch.setattr(cli, S.TEST_BUILD_SERVICE, scheduled_service)
    assert (
        main(
            [
                S.SYNC,
                S.CLI_PARSER_SCHEDULED,
                S.CLI_PARSER_INTERACTIVE,
                S.CLI_PARSER_DATA_DIR,
                str(tmp_path),
            ]
        )
        == C.ONE
    )
    assert S.CLI_TEST_SCHEDULE_GUARD in capsys.readouterr().err


def test_manual_pipeline_archives_provider_response_before_enrichment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from bookystats.persistence.raw import RawDocument, RawStore

    captured: list[RawDocument] = []
    original_capture = RawStore.capture

    def capture(
        self: RawStore,
        source: Source,
        account_id: str,
        body: bytes,
        *,
        media_type: str,
        origin: str,
        collection: str = S.LIBRARY,
        http_response: HttpResponse | None = C.NONE,
    ) -> RawDocument:
        document = original_capture(
            self,
            source,
            account_id,
            body,
            media_type=media_type,
            origin=origin,
            collection=collection,
            http_response=http_response,
        )
        captured.append(document)
        return document

    def fetch(
        self: HttpClient,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        return HttpResponse(
            url=url,
            status_code=C.HTTP_OK,
            headers={S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
            body=S.CLI_TEST_METADATA_BODY.encode(S.UTF_8),
        )

    monkeypatch.setattr(RawStore, S.CLI_TEST_CAPTURE, capture)
    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, fetch)
    monkeypatch.setenv(S.GOOGLE_BOOKS_API_KEY, S.CLI_TEST_GOOGLE_KEY)
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    storygraph = tmp_path / S.CLI_TEST_STORYGRAPH_NAME
    goodreads = tmp_path / S.CLI_TEST_GOODREADS_NAME
    storygraph.write_text(S.CLI_TEST_STORYGRAPH_CSV, encoding=S.UTF_8)
    goodreads.write_text(S.CLI_TEST_GOODREADS_CSV, encoding=S.UTF_8)
    save_settings(
        tmp_path,
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
        ),
    )
    assert (
        main(
            [
                S.SYNC,
                S.CLI_PARSER_DATA_DIR,
                str(tmp_path),
                S.CLI_PARSER_JSON,
                S.CLI_STORYGRAPH_FILE,
                str(storygraph),
                S.CLI_GOODREADS_FILE,
                str(goodreads),
            ]
        )
        == C.ZERO
    )
    receipt = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert receipt.metadata[C.ZERO].processed == C.TWO
    provider_documents = [item for item in captured if item.source == Source.GOOGLE_BOOKS]
    assert provider_documents
    assert all(
        item.body == S.CLI_TEST_METADATA_BODY.encode(S.UTF_8)
        and S.CLI_TEST_GOOGLE_KEY not in item.origin
        for item in provider_documents
    )


def test_separate_goodreads_shelves_survive_later_import_replay_and_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from bookystats.persistence.raw import RawStore

    def unexpected_fetch(*args: object, **kwargs: object) -> None:
        pytest.fail(S.CLI_TEST_UNEXPECTED_NETWORK)

    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, unexpected_fetch)
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    save_settings(
        tmp_path,
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
        ),
    )
    storygraph = tmp_path / S.CLI_TEST_STORYGRAPH_NAME
    watchlist = tmp_path / S.TEST_BROWSER_EXPORT_WATCH_NAME
    read = tmp_path / S.TEST_BROWSER_EXPORT_READ_NAME
    storygraph.write_text(S.CLI_TEST_STORYGRAPH_CSV, encoding=S.UTF_8)
    watchlist.write_bytes(csv_body(Source.GOODREADS, [C.TEST_BROWSER_EXPORT_ROW]))
    read.write_bytes(
        csv_body(
            Source.GOODREADS,
            [
                {
                    **C.TEST_BROWSER_EXPORT_ROW,
                    S.IMPORT_BROWSER_URL: S.IMPORT_GOODREADS_URL.format(
                        source_id=S.TEST_IMPORT_SECOND_ID
                    ),
                    S.IMPORT_TITLE: S.TEST_IMPORT_OTHER_TITLE,
                    S.IMPORT_BROWSER_DETAILS: S.EMPTY,
                }
            ],
        )
    )
    base = [
        S.SYNC,
        S.CLI_PARSER_DATA_DIR,
        str(tmp_path),
        S.CLI_PARSER_JSON,
    ]
    assert (
        main(
            [
                *base,
                S.CLI_STORYGRAPH_FILE,
                str(storygraph),
                S.CLI_GOODREADS_WATCHLIST_FILE,
                str(watchlist),
            ]
        )
        == C.ZERO
    )
    first = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert first.verification is not C.NONE
    assert first.verification.result == VerificationResult.SUCCESS
    assert main([*base, S.CLI_GOODREADS_READ_FILE, str(read)]) == C.ZERO
    imported = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert [item.collection for item in imported.sources] == [S.LIBRARY, S.TO_READ, S.READ]
    assert imported.verification is not C.NONE
    assert imported.verification.result == VerificationResult.SUCCESS
    assert not imported.account_sync_complete
    assert imported.log_file is not C.NONE
    log = Path(imported.log_file).read_text(encoding=S.UTF_8)
    assert S.LOG2_VERIFICATION.format(result=S.SUCCESS) in log
    assert S.TEST_BROWSER_EXPORT_READ_NAME not in log
    assert S.RUNLOG_FILES_HEADING not in log
    assert str(tmp_path) not in log
    archive = RawStore(database_path(tmp_path, S.CLI_RAW_DATABASE))
    try:
        for collection in (S.TO_READ, S.READ):
            raw = archive.latest(
                Source.GOODREADS, accounts()[C.ONE].account_id, collection=collection
            )
            assert raw is not C.NONE
            assert raw.collection == collection
    finally:
        archive.close()
    for path in (watchlist, read):
        path.unlink()
    assert main([*base, S.CLI_STORYGRAPH_FILE, str(storygraph)]) == C.ZERO
    replay = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert all(
        item.publication is not C.NONE
        and item.publication.added == C.ZERO
        and item.publication.unchanged == C.ONE
        for item in replay.sources
    )
    watchlist.write_text(S.CLI_TEST_BROKEN_CSV, encoding=S.UTF_8)
    assert main([*base, S.CLI_GOODREADS_WATCHLIST_FILE, str(watchlist)]) == C.THREE
    failed = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert failed.verification is not C.NONE
    assert failed.verification.result == VerificationResult.FAILED
    assert failed.sources[-C.ONE].state == SyncState.COMPLETE
    database = Database(database_path(tmp_path, S.LIBRARY_SQLITE3))
    try:
        records = database.active_records()
        assert len(records) == C.THREE
        assert {record.status.value for record in records if record.source == Source.GOODREADS} == {
            S.TO_READ,
            S.READ,
        }
    finally:
        database.close()
