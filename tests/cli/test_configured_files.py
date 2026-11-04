from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import HttpClient
from bookystats.application.sync import SyncReceipt, SyncService
from bookystats.cli.commands import main
from bookystats.domain.analytics import AnalyticsSettings
from bookystats.domain.interfaces import HttpResponse
from bookystats.domain.models import ReadingStatus, Source, SyncState, VerificationResult
from bookystats.persistence.analytics import AnalyticsStore
from bookystats.persistence.library import Database
from bookystats.persistence.raw import RawStore
from bookystats.runtime.config import FileSettings, MetadataSettings, Settings, save_settings
from bookystats.runtime.layout import database_path
from bookystats.runtime.locking import SyncLock
from bookystats.runtime.runlog import log_directory
from bookystats.runtime.runsummary import read_summary, summary_path
from tests.support.exports import csv_body
from tests.support.outcomes import inject_append_fault
from tests.support.paths import fixture_path
from tests.support.sources import accounts


@pytest.fixture
def configured_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)

    def unexpected_network(*args: object, **kwargs: object) -> None:
        pytest.fail(S.CLI_TEST_UNEXPECTED_NETWORK)

    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, unexpected_network)
    (tmp_path / S.CLI_TEST_STORYGRAPH_NAME).write_text(S.CLI_TEST_STORYGRAPH_CSV, encoding=S.UTF_8)
    (tmp_path / S.TEST_BROWSER_EXPORT_WATCH_NAME).write_bytes(
        csv_body(Source.GOODREADS, [C.TEST_BROWSER_EXPORT_ROW])
    )
    (tmp_path / S.TEST_BROWSER_EXPORT_READ_NAME).write_bytes(
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
    settings = Settings(
        accounts=accounts(),
        files=FileSettings(
            storygraph_file=Path(S.CLI_TEST_STORYGRAPH_NAME),
            goodreads_watchlist_file=Path(S.TEST_BROWSER_EXPORT_WATCH_NAME),
            goodreads_read_file=Path(S.TEST_BROWSER_EXPORT_READ_NAME),
        ),
        metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
    )
    save_settings(tmp_path, settings)
    return settings


def _arguments(directory: Path) -> list[str]:
    return [S.SYNC, S.CLI_PARSER_DATA_DIR, str(directory), S.CLI_PARSER_JSON]


def test_csvs_rebuild_enrichment_and_analysis_in_independent_empty_data_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    monkeypatch.setenv(S.GOOGLE_BOOKS_API_KEY, S.CLI_TEST_GOOGLE_KEY)
    storygraph = tmp_path / S.CLI_TEST_STORYGRAPH_NAME
    goodreads = tmp_path / S.CLI_TEST_GOODREADS_NAME
    storygraph.write_text(S.CLI_TEST_STORYGRAPH_CSV, encoding=S.UTF_8)
    goodreads.write_text(S.CLI_TEST_GOODREADS_CSV.replace(S.TO_READ, S.READ), encoding=S.UTF_8)
    calls: list[Source] = []

    def fetch(
        self: HttpClient,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        if urlsplit(url).hostname == S.WWW_GOOGLEAPIS_COM:
            provider = Source.GOOGLE_BOOKS
            name = S.GOOGLE_BOOKS_JSON
        else:
            assert urlsplit(url).hostname == S.OPENLIBRARY_ORG
            provider = Source.OPEN_LIBRARY
            name = (
                S.OPEN_LIBRARY_JSON
                if url == S.OPEN_LIBRARY_ENDPOINT_HTTPS_OPENLIBRARY_ORG_SEARCH_JSON
                else S.META_COVERAGE_WORK_FIXTURE
            )
        calls.append(provider)
        return HttpResponse(
            url=url,
            status_code=C.HTTP_OK,
            headers={S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
            body=fixture_path(S.METADATA, name).read_bytes(),
        )

    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, fetch)
    settings = Settings(
        accounts=accounts(),
        files=FileSettings(storygraph_file=storygraph, goodreads_file=goodreads),
        metadata=MetadataSettings(
            google_books=C.TRUE,
            open_library=C.TRUE,
            strategy=S.ENR_STRATEGY_INDEPENDENT,
        ),
    )
    for iteration in range(C.TWO):
        directory = tmp_path / str(iteration)
        assert not directory.exists()
        save_settings(directory, settings)
        assert all(not database_path(directory, name).exists() for name in C.CLI_LOCAL_DATABASES)
        calls.clear()
        assert main(_arguments(directory)) == C.ZERO
        receipt = SyncReceipt.model_validate_json(capsys.readouterr().out)
        assert receipt.state == SyncState.COMPLETE
        assert receipt.verification is not C.NONE
        assert receipt.verification.result == VerificationResult.SUCCESS
        assert receipt.analytics is not C.NONE
        assert receipt.analytics.state == SyncState.COMPLETE
        assert not receipt.analytics.taste_reused
        assert not receipt.analytics.watchlist_reused
        assert Source.GOOGLE_BOOKS in calls and Source.OPEN_LIBRARY in calls
        assert all(item.state == SyncState.COMPLETE for item in receipt.metadata)
        assert all(database_path(directory, name).is_file() for name in C.CLI_LOCAL_DATABASES)
        with closing(Database(database_path(directory, S.LIBRARY_SQLITE3))) as library:
            data = library.analytics_input(accounts(), AnalyticsSettings())
        assert len(data.books) == C.ONE
        book = data.books[C.ZERO]
        assert book.status == ReadingStatus.READ
        assert book.rating == C.INTEGRATION_RATING
        assert book.description is not C.NONE
        assert len(book.features[S.LANGUAGE]) == C.ONE
        assert S.EN in book.features[S.LANGUAGE]
        assert len(book.features[S.LANGUAGES]) == C.TWO
        with closing(RawStore(database_path(directory, S.CLI_RAW_DATABASE))) as archive:
            for source in receipt.sources:
                assert source.raw_document_id is not C.NONE
                original = storygraph if source.source == Source.STORYGRAPH else goodreads
                assert archive.get(source.raw_document_id).body == original.read_bytes()
        with AnalyticsStore(database_path(directory, S.AN_DATABASE)) as reports:
            report = reports.latest()
        assert report is not C.NONE
        assert report.taste.findings
        assert report.manifest.calculation_version == S.AN_CALCULATION_VERSION
        count = len(calls)
        assert main(_arguments(directory)) == C.ZERO
        replay = SyncReceipt.model_validate_json(capsys.readouterr().out)
        assert replay.analytics is not C.NONE
        assert replay.analytics.taste_reused and replay.analytics.watchlist_reused
        assert len(calls) == count
        assert main([S.STATUS, S.CLI_PARSER_DATA_DIR, str(directory)]) == C.ZERO
        capsys.readouterr()
        assert len(calls) == count


def test_fallback_csv_sync_keeps_core_missingness_partial_on_unchanged_repeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    monkeypatch.setenv(S.GOOGLE_BOOKS_API_KEY, S.CLI_TEST_GOOGLE_KEY)
    storygraph = tmp_path / S.CLI_TEST_STORYGRAPH_NAME
    goodreads = tmp_path / S.CLI_TEST_GOODREADS_NAME
    storygraph.write_text(S.CLI_TEST_STORYGRAPH_CSV, encoding=S.UTF_8)
    goodreads.write_text(S.CLI_TEST_GOODREADS_CSV.replace(S.TO_READ, S.READ), encoding=S.UTF_8)
    calls: list[Source] = []

    def fetch(
        self: HttpClient,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        google = urlsplit(url).hostname == S.WWW_GOOGLEAPIS_COM
        calls.append(Source.GOOGLE_BOOKS if google else Source.OPEN_LIBRARY)
        name = (
            S.GOOGLE_BOOKS_JSON
            if google
            else S.OPEN_LIBRARY_JSON
            if url == S.OPEN_LIBRARY_ENDPOINT_HTTPS_OPENLIBRARY_ORG_SEARCH_JSON
            else S.META_COVERAGE_WORK_FIXTURE
        )
        body = fixture_path(S.METADATA, name).read_bytes()
        if name == S.META_COVERAGE_WORK_FIXTURE:
            work = json.loads(body)
            work.pop(S.DESCRIPTION, C.NONE)
            body = json.dumps(work).encode(S.UTF_8)
        if google:
            catalog = json.loads(body)
            for volume in catalog[S.ITEMS]:
                volume[S.VOLUMEINFO].pop(S.DESCRIPTION, C.NONE)
            body = json.dumps(catalog).encode(S.UTF_8)
        return HttpResponse(
            url=url,
            status_code=C.HTTP_OK,
            headers={S.CONTENT_TYPE: S.GOOGLE_BOOKS_HTTP_PAYLOAD_APPLICATION_JSON},
            body=body,
        )

    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, fetch)
    save_settings(
        tmp_path,
        Settings(
            accounts=accounts(),
            files=FileSettings(storygraph_file=storygraph, goodreads_file=goodreads),
        ),
    )
    assert main(_arguments(tmp_path)) == C.THREE
    receipt = SyncReceipt.model_validate_json(capsys.readouterr().out)
    google = next(item for item in receipt.metadata if item.provider == Source.GOOGLE_BOOKS)
    assert calls[C.ZERO] == Source.OPEN_LIBRARY
    assert Source.GOOGLE_BOOKS in calls
    assert google.state == SyncState.PARTIAL
    assert google.coverage_scope == S.ENR_CORE_COVERAGE_SCOPE
    assert google.fallback_fields == C.ENR_FALLBACK_FIELDS
    assert google.fallback_unresolved > C.ZERO
    assert receipt.verification is not C.NONE
    assert receipt.verification.result == VerificationResult.PARTIAL
    assert all(
        check.result == VerificationResult.SUCCESS
        for check in receipt.verification.checks
        if check.name != S.METADATA
    )
    assert all(source.state == SyncState.COMPLETE for source in receipt.sources)
    assert receipt.analytics is not C.NONE and receipt.analytics.state == SyncState.COMPLETE
    count = len(calls)
    assert main(_arguments(tmp_path)) == C.THREE
    replay = SyncReceipt.model_validate_json(capsys.readouterr().out)
    repeated_google = next(item for item in replay.metadata if item.provider == Source.GOOGLE_BOOKS)
    assert repeated_google.requested == C.ZERO
    assert repeated_google.fallback_unresolved == google.fallback_unresolved
    assert replay.analytics is not C.NONE
    assert replay.analytics.taste_reused and replay.analytics.watchlist_reused
    assert len(calls) == count


def test_plain_sync_imports_configured_files_without_source_access_and_is_idempotent(
    tmp_path: Path, configured_files: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_arguments(tmp_path)) == C.ZERO
    initial = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert initial.state == SyncState.COMPLETE
    assert initial.verification is not C.NONE
    assert initial.verification.result == VerificationResult.SUCCESS
    assert not initial.account_sync_complete
    assert initial.analytics is not C.NONE
    assert initial.analytics.state == SyncState.COMPLETE
    assert {(item.source, item.collection) for item in initial.sources} == C.AUTO_SYNC_TEST_SCOPES
    paths = configured_files.files.paths(tmp_path)
    with closing(RawStore(database_path(tmp_path, S.CLI_RAW_DATABASE))) as archive:
        for item in initial.sources:
            assert item.input_kind == S.INPUT_FILE
            assert item.raw_document_id is not C.NONE
            original = archive.get(item.raw_document_id)
            path = paths[(item.source, item.collection)]
            assert path is not C.NONE
            assert original.body == path.read_bytes()
            assert original.origin == path.name
    assert main(_arguments(tmp_path)) == C.ZERO
    replay = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert replay.state == SyncState.COMPLETE
    assert replay.analytics is not C.NONE
    assert replay.analytics.taste_reused and replay.analytics.watchlist_reused
    assert all(
        item.publication is not C.NONE
        and item.publication.added == C.ZERO
        and item.publication.updated == C.ZERO
        and item.publication.unchanged == C.ONE
        and item.publication.removed == C.ZERO
        for item in replay.sources
    )
    assert not (tmp_path / S.PROFILES).exists()
    assert not (tmp_path / S.STABILITY_JSON).exists()
    assert main([S.STATUS, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ZERO
    status = capsys.readouterr().out
    assert S.STATUS_CSV_HEADING in status
    assert all(path is C.NONE or path.name in status for path in paths.values())


def test_storygraph_leaving_read_scope_removes_active_rating_but_preserves_archive(
    tmp_path: Path, configured_files: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_arguments(tmp_path)) == C.ZERO
    capsys.readouterr()
    path = tmp_path / S.CLI_TEST_STORYGRAPH_NAME
    body = S.CLI_TEST_STORYGRAPH_CSV.replace(
        S.COMMA + S.READ + S.COMMA, S.COMMA + S.TO_READ + S.COMMA
    ).encode(S.UTF_8)
    path.write_bytes(body)
    assert main(_arguments(tmp_path)) == C.ZERO
    receipt = SyncReceipt.model_validate_json(capsys.readouterr().out)
    storygraph = next(item for item in receipt.sources if item.source == Source.STORYGRAPH)
    assert storygraph.records == C.ZERO
    assert storygraph.publication is not C.NONE
    assert storygraph.publication.removed == C.ONE
    assert receipt.verification is not C.NONE
    assert receipt.verification.result == VerificationResult.SUCCESS
    assert storygraph.raw_document_id is not C.NONE
    with closing(RawStore(database_path(tmp_path, S.CLI_RAW_DATABASE))) as archive:
        assert archive.get(storygraph.raw_document_id).body == body
    with closing(Database(database_path(tmp_path, S.LIBRARY_SQLITE3))) as library:
        data = library.analytics_input(configured_files.accounts, AnalyticsSettings())
        assert data.personal_rating_records == C.ZERO
        assert all(book.rating is C.NONE for book in data.books)
        assert library.enrichment_targets(Source.GOOGLE_BOOKS)
        assert all(
            book.source == Source.GOODREADS
            for book in library.enrichment_targets(Source.GOOGLE_BOOKS)
        )


@pytest.mark.parametrize(S.CSV_TEST_FAILURE_PARAMETER, C.CSV_TEST_FAILURES)
def test_bad_input_retains_its_snapshot_without_blocking_healthy_configured_files(
    tmp_path: Path,
    configured_files: Settings,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    assert main(_arguments(tmp_path)) == C.ZERO
    initial = SyncReceipt.model_validate_json(capsys.readouterr().out)
    read_scope = (Source.GOODREADS, S.READ)
    initial_read = next(
        item for item in initial.sources if (item.source, item.collection) == read_scope
    )
    with closing(Database(database_path(tmp_path, S.LIBRARY_SQLITE3))) as library:
        first_status = library.status()[S.SOURCES]
    assert isinstance(first_status, list)
    read_snapshot = next(
        entry[S.ACTIVE_SNAPSHOT_ID]
        for entry in first_status
        if isinstance(entry, dict) and (entry[S.SOURCE], entry[S.COLLECTION]) == read_scope
    )
    read = tmp_path / S.TEST_BROWSER_EXPORT_READ_NAME
    if failure == S.CSV_INPUT_UNAVAILABLE_CODE:
        read.unlink()
    else:
        read.write_text(S.CLI_TEST_BROKEN_CSV, encoding=S.UTF_8)
    assert main(_arguments(tmp_path)) == C.THREE
    latest = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert latest.state == SyncState.PARTIAL
    assert latest.analytics is not C.NONE
    assert latest.analytics.state == SyncState.PARTIAL
    assert initial.analytics is not C.NONE
    with AnalyticsStore(database_path(tmp_path, S.AN_DATABASE)) as reports:
        retained = reports.latest()
    assert retained is not C.NONE
    assert retained.report_id == initial.analytics.report_id
    failed = next(item for item in latest.sources if (item.source, item.collection) == read_scope)
    assert failed.input_kind == S.INPUT_FILE
    assert failed.state == SyncState.FAILED
    assert failed.publication is C.NONE
    assert failed.raw_document_id != initial_read.raw_document_id
    if failure == S.CSV_INPUT_UNAVAILABLE_CODE:
        assert failed.raw_document_id is C.NONE
        assert failed.issues[C.ZERO].code == failure
    else:
        assert failed.raw_document_id is not C.NONE
        with closing(RawStore(database_path(tmp_path, S.CLI_RAW_DATABASE))) as archive:
            assert archive.get(failed.raw_document_id).body == read.read_bytes()
    assert all(
        item.state == SyncState.COMPLETE and item.publication is not C.NONE
        for item in latest.sources
        if (item.source, item.collection) != read_scope
    )
    with closing(Database(database_path(tmp_path, S.LIBRARY_SQLITE3))) as library:
        assert len(library.active_records()) == C.THREE
        final_status = library.status()[S.SOURCES]
    assert isinstance(final_status, list)
    assert any(
        isinstance(entry, dict)
        and (entry[S.SOURCE], entry[S.COLLECTION]) == read_scope
        and entry[S.ACTIVE_SNAPSHOT_ID] == read_snapshot
        and entry[S.ACTIVE_COUNT] == C.ONE
        for entry in final_status
    )


def test_unconfigured_files_do_not_replay_archived_csvs(
    tmp_path: Path, configured_files: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_arguments(tmp_path)) == C.ZERO
    capsys.readouterr()
    save_settings(tmp_path, configured_files.model_copy(update={S.CSV_FILES_KEY: FileSettings()}))
    assert main(_arguments(tmp_path)) == C.THREE
    receipt = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert all(
        item.state == SyncState.NOT_CONFIGURED
        and item.input_kind == S.INPUT_FILE
        and item.raw_document_id is C.NONE
        and item.publication is C.NONE
        for item in receipt.sources
    )
    assert not receipt.account_sync_complete


def _log_text(directory: Path) -> str:
    return (log_directory(directory) / S.LOG_FILE_NAME).read_text(encoding=S.UTF_8)


def _last_end_line(directory: Path) -> str:
    return next(
        line
        for line in reversed(_log_text(directory).splitlines())
        if line.startswith(S.OPLOG_END_TOKEN)
    )


def test_json_sync_keeps_stdout_machine_readable_and_appends_one_private_log(
    tmp_path: Path, configured_files: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_arguments(tmp_path)) == C.ZERO
    captured = capsys.readouterr()
    receipt = SyncReceipt.model_validate_json(captured.out)
    saved = read_summary(tmp_path)
    assert saved is not C.NONE
    log = log_directory(tmp_path) / S.LOG_FILE_NAME
    first = log.read_bytes()
    expected = [*saved.lines, S.REPORT_RUN_LOG_LINE.format(path=log)]
    assert captured.err.splitlines()[-len(expected) :] == expected
    assert all(line in first.decode(S.UTF_8) for line in saved.lines)
    assert str(tmp_path) not in first.decode(S.UTF_8)
    assert (saved.outcome, saved.exit_code, saved.run_id) == (S.COMPLETE, C.ZERO, receipt.run_id)
    fields = json.loads(summary_path(tmp_path).read_text(encoding=S.UTF_8))
    assert set(fields) == C.TEST_OPLOG_SUMMARY_FIELDS
    assert main(_arguments(tmp_path)) == C.ZERO
    capsys.readouterr()
    appended = log.read_bytes()
    assert appended.startswith(first)
    assert appended.count(S.OPLOG_START_TOKEN.encode()) == C.TWO
    assert appended.count(S.OPLOG_END_TOKEN.encode()) == C.TWO


def test_status_shows_the_last_attempt_offline_and_never_changes_the_log_or_summary(
    tmp_path: Path, configured_files: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_arguments(tmp_path)) == C.ZERO
    saved = read_summary(tmp_path)
    capsys.readouterr()
    assert saved is not C.NONE
    watched = (log_directory(tmp_path) / S.LOG_FILE_NAME, summary_path(tmp_path))

    def snapshot() -> list[tuple[bytes, int]]:
        return [(path.read_bytes(), path.stat().st_mtime_ns) for path in watched]

    before = snapshot()
    logs_before = sorted(path.name for path in log_directory(tmp_path).iterdir())
    status_arguments = [S.STATUS, S.CLI_PARSER_DATA_DIR, str(tmp_path)]
    assert main(status_arguments) == C.ZERO
    shown = capsys.readouterr().out
    assert S.TEST_OPLOG_ATTEMPT_PREFIX in shown
    assert all(S.RUNSUM_TEXT_LINE.format(text=line) in shown for line in saved.lines)
    assert main([*status_arguments, S.CLI_PARSER_JSON]) == C.ZERO
    report = json.loads(capsys.readouterr().out)
    assert report[S.RUNSUM_KEY][S.RUNSUM_LINES_KEY] == list(saved.lines)
    assert snapshot() == before
    assert sorted(path.name for path in log_directory(tmp_path).iterdir()) == logs_before


def test_partial_sync_names_the_failed_source_and_next_action_in_log_and_summary(
    tmp_path: Path, configured_files: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_arguments(tmp_path)) == C.ZERO
    capsys.readouterr()
    (tmp_path / S.TEST_BROWSER_EXPORT_READ_NAME).unlink()
    assert main(_arguments(tmp_path)) == C.THREE
    captured = capsys.readouterr()
    SyncReceipt.model_validate_json(captured.out)
    names = S.OUTCOME_SOURCE_NAME.format(
        source=S.LOG3_SOURCE_GOODREADS,
        collection=S.LOG3_COLLECTION_READ,
        state=SyncState.FAILED.value,
    )
    why = S.OUTCOME_CAUSE_LINE.format(
        text=S.OUTCOME_SOURCES.format(count=C.ONE, total=C.THREE, names=names)
    )
    action = S.OUTCOME_NEXT_LINE.format(action=S.OUTCOME_ACTION_SOURCES)
    saved = read_summary(tmp_path)
    assert saved is not C.NONE
    assert (saved.outcome, saved.exit_code) == (S.PARTIAL, C.THREE)
    assert why in saved.lines
    assert action in saved.lines
    assert why in captured.err
    assert S.TEST_OPLOG_PARTIAL_END in _last_end_line(tmp_path)
    assert why in _log_text(tmp_path)


def test_unopenable_run_log_stops_the_sync_before_any_input_is_archived(
    tmp_path: Path, configured_files: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    log_directory(tmp_path).write_text(S.EMPTY, encoding=S.UTF_8)
    assert main(_arguments(tmp_path)) == C.ONE
    captured = capsys.readouterr()
    assert captured.out == S.EMPTY
    assert S.OPLOG_SYNC_NOT_STARTED in captured.err
    assert str(tmp_path) not in captured.err
    assert not database_path(tmp_path, S.CLI_RAW_DATABASE).exists()


def test_failing_log_writes_are_warned_once_and_turn_success_into_exit_three(
    tmp_path: Path,
    configured_files: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inject_append_fault(monkeypatch, lambda call: call >= C.TWO)
    assert main(_arguments(tmp_path)) == C.THREE
    captured = capsys.readouterr()
    reason = S.TEST_OPLOG_DISK_FULL
    SyncReceipt.model_validate_json(captured.out)
    assert captured.err.count(S.OPLOG_WARNING.format(reason=reason)) == C.ONE
    assert (
        S.OUTCOME_CAUSE_LINE.format(text=S.OUTCOME_LOG_INCOMPLETE.format(reason=reason))
        in captured.err
    )
    saved = read_summary(tmp_path)
    assert saved is not C.NONE
    assert saved.exit_code == C.THREE


def test_interrupted_sync_exits_130_and_records_the_interruption(
    tmp_path: Path,
    configured_files: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def interrupted(*arguments: object, **options: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(SyncService, S.TEST_OPLOG_RUN_ATTRIBUTE, interrupted)
    assert main(_arguments(tmp_path)) == C.CLI_MAIN
    captured = capsys.readouterr()
    log = log_directory(tmp_path) / S.LOG_FILE_NAME
    saved = read_summary(tmp_path)
    assert saved is not C.NONE
    assert (saved.outcome, saved.exit_code) == (S.INTERRUPTED, C.CLI_MAIN)
    assert S.TEST_OPLOG_INTERRUPTED_END in _last_end_line(tmp_path)
    assert S.REPORT_RUN_LOG_LINE.format(path=log) in captured.err
    assert captured.out == S.EMPTY


def test_a_concurrent_sync_exits_four_without_creating_a_run_log(
    tmp_path: Path, configured_files: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    with SyncLock(tmp_path):
        assert main(_arguments(tmp_path)) == C.FOUR
    captured = capsys.readouterr()
    assert captured.out == S.EMPTY
    assert captured.err
    assert not log_directory(tmp_path).exists()
