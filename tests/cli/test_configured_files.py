from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import HttpClient
from bookystats.application.sync import SyncReceipt
from bookystats.cli.commands import main
from bookystats.domain.analytics import AnalyticsSettings
from bookystats.domain.interfaces import HttpResponse
from bookystats.domain.models import ReadingStatus, Source, SyncState, VerificationResult
from bookystats.persistence.analytics import AnalyticsStore
from bookystats.persistence.library import Database
from bookystats.persistence.raw import RawStore
from bookystats.runtime.config import FileSettings, MetadataSettings, Settings, save_settings
from tests.support.exports import csv_body
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
        metadata=MetadataSettings(google_books=C.TRUE, open_library=C.TRUE),
    )
    for iteration in range(C.TWO):
        directory = tmp_path / str(iteration)
        assert not directory.exists()
        save_settings(directory, settings)
        assert all(not (directory / name).exists() for name in C.CLI_LOCAL_DATABASES)
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
        assert all((directory / name).is_file() for name in C.CLI_LOCAL_DATABASES)
        with closing(Database(directory / S.LIBRARY_SQLITE3)) as library:
            data = library.analytics_input(accounts(), AnalyticsSettings())
        assert len(data.books) == C.ONE
        book = data.books[C.ZERO]
        assert book.status == ReadingStatus.READ
        assert book.rating == C.INTEGRATION_RATING
        assert book.description is not C.NONE
        assert len(book.features[S.LANGUAGE]) == C.ONE
        assert S.EN in book.features[S.LANGUAGE]
        assert len(book.features[S.LANGUAGES]) == C.TWO
        with closing(RawStore(directory / S.CLI_RAW_DATABASE)) as archive:
            for source in receipt.sources:
                assert source.raw_document_id is not C.NONE
                original = storygraph if source.source == Source.STORYGRAPH else goodreads
                assert archive.get(source.raw_document_id).body == original.read_bytes()
        with AnalyticsStore(directory / S.AN_DATABASE) as reports:
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
    with closing(RawStore(tmp_path / S.CLI_RAW_DATABASE)) as archive:
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
    with closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as library:
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
    with AnalyticsStore(tmp_path / S.AN_DATABASE) as reports:
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
        with closing(RawStore(tmp_path / S.CLI_RAW_DATABASE)) as archive:
            assert archive.get(failed.raw_document_id).body == read.read_bytes()
    assert all(
        item.state == SyncState.COMPLETE and item.publication is not C.NONE
        for item in latest.sources
        if (item.source, item.collection) != read_scope
    )
    with closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as library:
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
