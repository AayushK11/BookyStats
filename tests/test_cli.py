from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from bookystats import cli, scheduling
from bookystats import constants as C
from bookystats import strings as S
from bookystats.cli import main
from bookystats.config import Settings, WeeklySettings, atomic_write, save_settings
from bookystats.errors import ConfigurationError
from bookystats.interfaces import HttpResponse
from bookystats.models import Source, SyncState
from bookystats.net import HttpClient
from bookystats.storage import Database
from bookystats.sync import SyncReceipt
from tests.test_scheduling import activation
from tests.test_sync import accounts


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


def test_unattended_without_accounts_never_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)

    def unexpected_input(prompt: str) -> str:
        pytest.fail(S.TEST_CLI_UNATTENDED_WITHOUT_INPUT_UNATTENDED_EXECUTION_PROMPTED)

    monkeypatch.setattr(S.BUILTINS_INPUT, unexpected_input)
    save_settings(tmp_path, Settings(accounts=()))
    assert main([S.SYNC, S.CLI_PARSER_UNATTENDED, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ONE
    assert S.CLI_MAIN_CONFIGURE_READER_PROFILE_URLS_IN_CONFIG_JSON in capsys.readouterr().err
    assert not (tmp_path / S.LIBRARY_SQLITE3).exists()
    assert (tmp_path / S.CONFIG_JSON).exists()


def test_disabled_scheduled_run_never_collects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    assert main([S.SYNC, S.CLI_PARSER_SCHEDULED, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ZERO
    assert S.DISABLED in capsys.readouterr().out
    assert not (tmp_path / S.LIBRARY_SQLITE3).exists()


def test_only_sync_and_status_are_exposed() -> None:
    with pytest.raises(SystemExit) as failure:
        main([S.EXPORT])
    assert failure.value.code == C.TWO


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
    assert not (tmp_path / S.LIBRARY_SQLITE3).exists()


def test_manual_files_publish_with_raw_lineage_and_replay_without_originals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from bookystats.raw import RawStore

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

    monkeypatch.setattr(cli, S.CLI_TEST_RECORD_LIVE, unexpected_schedule)
    monkeypatch.setattr(cli, S.CLI_TEST_ENABLE_WEEKLY, unexpected_schedule)
    save_settings(
        tmp_path,
        Settings(
            weekly=WeeklySettings(
                enabled=C.TRUE, weekday=S.MON, time=S.SETTINGS_WEEKLY_TIME_TEXT, timezone=S.UTC
            )
        ),
    )
    base = [
        S.SYNC,
        S.CLI_PARSER_DATA_DIR,
        str(tmp_path),
        S.CLI_PARSER_JSON,
        S.CLI_METADATA,
        S.CLI_METADATA_NONE,
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
    archive = RawStore(tmp_path / S.CLI_RAW_DATABASE)
    try:
        document = archive.latest(Source.STORYGRAPH, S.DEFAULT_STORYGRAPH_ACCOUNT)
        assert document is not C.NONE
        assert document.body == storygraph.read_bytes()
    finally:
        archive.close()
    storygraph.unlink()
    goodreads.unlink()
    assert main(base) == C.ZERO
    replay = SyncReceipt.model_validate_json(capsys.readouterr().out)
    assert [item.raw_document_id for item in replay.sources] == [
        item.raw_document_id for item in receipt.sources
    ]
    assert all(
        item.publication is not C.NONE
        and item.publication.added == C.ZERO
        and item.publication.unchanged == C.ONE
        for item in replay.sources
    )
    database = Database(tmp_path / S.LIBRARY_SQLITE3)
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
    archive = RawStore(tmp_path / S.CLI_RAW_DATABASE)
    try:
        broken = archive.latest(Source.STORYGRAPH, S.DEFAULT_STORYGRAPH_ACCOUNT)
        assert broken is not C.NONE and broken.body == storygraph.read_bytes()
    finally:
        archive.close()
    database = Database(tmp_path / S.LIBRARY_SQLITE3)
    try:
        assert database.active_records() == records
    finally:
        database.close()


def test_fresh_manual_sync_never_falls_back_to_account_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def unexpected_service(*args: object, **kwargs: object) -> None:
        pytest.fail(S.TEST_UNEXPECTED_SERVICE_START)

    monkeypatch.setattr(cli, S.TEST_BUILD_SERVICE, unexpected_service)
    assert main([S.SYNC, S.CLI_PARSER_DATA_DIR, str(tmp_path)]) == C.ONE
    assert S.CLI_NO_RAW_INPUT in capsys.readouterr().err
    assert not (tmp_path / S.LIBRARY_SQLITE3).exists()


def test_scheduled_capture_cannot_enable_interactive_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    save_settings(
        tmp_path,
        Settings(
            weekly=WeeklySettings(
                enabled=C.TRUE, weekday=S.MON, time=S.SETTINGS_WEEKLY_TIME_TEXT, timezone=S.UTC
            )
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
    from bookystats.raw import RawDocument, RawStore

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
    ) -> RawDocument:
        document = original_capture(
            self, source, account_id, body, media_type=media_type, origin=origin
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
                S.CLI_METADATA,
                S.CLI_METADATA_GOOGLE,
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
