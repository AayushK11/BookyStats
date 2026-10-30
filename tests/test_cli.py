from __future__ import annotations

import json
from pathlib import Path

import pytest

from bookystats import cli, scheduling
from bookystats import constants as C
from bookystats import strings as S
from bookystats.cli import main
from bookystats.config import Settings, WeeklySettings, atomic_write, save_settings
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
    assert (
        S.TEST_CLI_UNATTENDED_WITHOUT_ACCOUNTS_NEVER_PROMPTS_NO_EXPORTS in capsys.readouterr().err
    )
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
