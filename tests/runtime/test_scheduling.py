from __future__ import annotations

import base64
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import ConfigurationError
from bookystats.runtime import scheduling
from bookystats.runtime.config import Settings, WeeklySettings, atomic_write
from bookystats.runtime.scheduling import (
    RunEvidence,
    ScheduleActivation,
    StabilityHistory,
    record_live_run,
    require_activation,
    require_stable,
    schedule_status,
    task_xml,
)
from tests.support.scheduling import activation, receipt
from tests.support.sources import accounts


def test_implementation_fingerprint_includes_modules_outside_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / S.BOOKYSTATS_2
    module = package / S.RUNTIME_FOLDER / S.TEST_REPORTING_MODULE_FILE
    module.parent.mkdir(parents=C.TRUE)
    module.write_text(S.EMPTY, encoding=S.UTF_8)
    shared = package / S.CONSTANTS_MODULE_FILE
    shared.write_text(S.CURRENT, encoding=S.UTF_8)
    monkeypatch.setattr(scheduling, S.TEST_REPORTING_FILE_ATTRIBUTE, str(module))
    initial = scheduling.implementation_fingerprint()
    shared.write_text(S.NEW, encoding=S.UTF_8)
    assert scheduling.implementation_fingerprint() != initial


def test_activation_binds_code_accounts_interpreter_and_schedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scheduling, S.TEST_SCHEDULING_FINGERPRINT, lambda: S.CURRENT)
    settings = Settings(
        accounts=accounts(),
        weekly=WeeklySettings(
            enabled=C.TRUE, weekday=S.MON, time=S.SETTINGS_WEEKLY_TIME_TEXT, timezone=S.UTC
        ),
    )
    saved = activation(tmp_path, settings)
    atomic_write(tmp_path / S.SCHEDULE_JSON, saved.model_dump_json())
    python = Path(sys.executable)
    require_activation(tmp_path, python, settings)
    changed_accounts = settings.model_copy(update={S.ACCOUNTS: settings.accounts[C.ONE :]})
    changed_schedule = settings.model_copy(
        update={S.WEEKLY: settings.weekly.model_copy(update={S.TIME: S.ALTERNATE_SCHEDULE_TIME})}
    )
    for changed in (changed_accounts, changed_schedule):
        with pytest.raises(ConfigurationError):
            require_activation(tmp_path, python, changed)
    with pytest.raises(ConfigurationError):
        require_activation(tmp_path, tmp_path / S.PYTHON_EXE, settings)
    monkeypatch.setattr(scheduling, S.TEST_SCHEDULING_FINGERPRINT, lambda: S.NEW)
    with pytest.raises(ConfigurationError):
        require_activation(tmp_path, python, settings)
    monkeypatch.setattr(scheduling, S.TEST_SCHEDULING_FINGERPRINT, lambda: S.CURRENT)
    legacy = ScheduleActivation(
        task_name=saved.task_name,
        enabled_at=saved.enabled_at,
        weekday=saved.weekday,
        time=saved.time,
        timezone=saved.timezone,
    )
    atomic_write(tmp_path / S.SCHEDULE_JSON, legacy.model_dump_json(exclude_none=C.TRUE))
    with pytest.raises(ConfigurationError):
        require_activation(tmp_path, python, settings)


@pytest.mark.skipif(os.name != S.NT, reason=S.WINDOWS_ONLY_TEST_REASON)
def test_task_xml_reader_preserves_unicode_paths_in_windows_powershell(tmp_path: Path) -> None:
    directory = tmp_path / S.UNICODE_TEST_FOLDER
    settings = Settings(
        accounts=accounts(),
        weekly=WeeklySettings(
            enabled=C.TRUE, weekday=S.MON, time=S.SETTINGS_WEEKLY_TIME_TEXT, timezone=S.UTC
        ),
    )
    path = directory / S.WEEKLY_TASK_XML
    xml = task_xml(directory, directory / S.PYTHON_EXE, settings)
    atomic_write(path, xml)
    encoded = scheduling._powershell(
        S.POWERSHELL_XML_ROUNDTRIP.format(expression=scheduling._task_xml_reader(path))
    )
    assert base64.b64decode(encoded).decode(S.UTF_8) == xml


def test_default_schedule_neither_installs_nor_claims_enabled(tmp_path: Path) -> None:
    assert schedule_status(tmp_path, Settings()) == {
        S.ENABLED_2: C.FALSE,
        S.CONFIGURED: C.FALSE,
        S.STATE: S.NOT_REGISTERED,
    }
    assert list(tmp_path.iterdir()) == []


def test_weekly_gate_requires_live_complete_unattended_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.BOOKYSTATS_SCHEDULING_IMPLEMENTATION_FINGERPRINT, lambda: S.CURRENT)
    settings = Settings(accounts=accounts())
    with pytest.raises(
        ConfigurationError,
        match=S.TEST_SCHEDULING_WEEKLY_GATE_REQUIRES_EVIDENCE_MATCH_TWO_CONSECUTIVE,
    ):
        require_stable(tmp_path, settings, {S.LAST_RUN: {S.RUN_ID: C.ONE}})
    record_live_run(tmp_path, settings, receipt(C.ONE, complete=C.TRUE), unattended=C.FALSE)
    record_live_run(tmp_path, settings, receipt(C.TWO, complete=C.TRUE), unattended=C.TRUE)
    require_stable(tmp_path, settings, {S.LAST_RUN: {S.RUN_ID: C.TWO}})
    record_live_run(tmp_path, settings, receipt(C.THREE, complete=C.FALSE), unattended=C.TRUE)
    with pytest.raises(
        ConfigurationError,
        match=S.TEST_SCHEDULING_WEEKLY_GATE_REQUIRES_EVIDENCE_MATCH_TWO_CONSECUTIVE,
    ):
        require_stable(tmp_path, settings, {S.LAST_RUN: {S.RUN_ID: C.THREE}})


def test_implementation_or_database_change_invalidates_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.BOOKYSTATS_SCHEDULING_IMPLEMENTATION_FINGERPRINT, lambda: S.OLD)
    settings = Settings(accounts=accounts())
    record_live_run(tmp_path, settings, receipt(C.ONE, complete=C.TRUE), unattended=C.FALSE)
    record_live_run(tmp_path, settings, receipt(C.TWO, complete=C.TRUE), unattended=C.TRUE)
    with pytest.raises(
        ConfigurationError, match=S.TEST_SCHEDULING_IMPLEMENTATION_OR_GATE_MATCH_CURRENT_DATABASE
    ):
        require_stable(tmp_path, settings, {S.LAST_RUN: {S.RUN_ID: C.FOUR}})
    monkeypatch.setattr(S.BOOKYSTATS_SCHEDULING_IMPLEMENTATION_FINGERPRINT, lambda: S.NEW)
    with pytest.raises(
        ConfigurationError, match=S.TEST_SCHEDULING_IMPLEMENTATION_OR_GATE_MATCH_THIS_IMPLEMENTATION
    ):
        require_stable(tmp_path, settings, {S.LAST_RUN: {S.RUN_ID: C.TWO}})


def test_stale_evidence_cannot_enable_schedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.BOOKYSTATS_SCHEDULING_IMPLEMENTATION_FINGERPRINT, lambda: S.CURRENT)
    settings = Settings(accounts=accounts())
    history = StabilityHistory(
        runs=tuple(
            RunEvidence(
                run_id=number,
                accounts=settings.account_fingerprint,
                implementation=S.CURRENT,
                completed_at=(datetime.now(UTC) - timedelta(days=C.EIGHT)).isoformat(),
                account_sync_complete=C.TRUE,
                unattended=C.TRUE,
            )
            for number in (C.ONE, C.TWO)
        )
    )
    atomic_write(tmp_path / S.STABILITY_JSON, history.model_dump_json())
    with pytest.raises(ConfigurationError, match=S.STALE):
        require_stable(tmp_path, settings, {S.LAST_RUN: {S.RUN_ID: C.TWO}})


def test_xml_uses_same_cli_no_password_and_catches_missed_runs(tmp_path: Path) -> None:
    settings = Settings(
        accounts=accounts(),
        weekly=WeeklySettings(
            enabled=C.TRUE, weekday=S.MON, time=S.SETTINGS_WEEKLY_TIME_TEXT, timezone=S.UTC
        ),
    )
    root = ET.fromstring(
        task_xml(
            tmp_path,
            tmp_path / S.PYTHON_EXE,
            settings,
            now=datetime(
                C.TEST_XML_USES_SAME_CLI_NO_PASSWORD_AND_CATCHES_MISSED_RUNS_ROOT_NOW,
                C.TEN,
                C.TEST_XML_USES_SAME_CLI_NO_PASSWORD_AND_CATCHES_MISSED_RUNS_ROOT_NOW_2,
                C.TEST_XML_USES_SAME_CLI_NO_PASSWORD_AND_CATCHES_MISSED_RUNS_ROOT_NOW_3,
                C.ZERO,
                tzinfo=UTC,
            ),
        )
    )
    namespace = {S.T: S.SCHEDULING_TASK_XML_TASK_HTTP_SCHEMAS_MICROSOFT_COM_WINDOWS_MIT_TASK}
    assert (
        root.findtext(
            S.TEST_SCHEDULING_XML_USES_SAME_CLI_CATCHES_MISSED_RUNS_T_LOGONTYPE,
            namespaces=namespace,
        )
        == S.INTERACTIVETOKEN
    )
    assert (
        root.findtext(
            S.TEST_SCHEDULING_XML_USES_SAME_MISSED_RUNS_T_STARTWHENAVAILABLE, namespaces=namespace
        )
        == S.TRUE_2
    )
    assert (
        root.findtext(
            S.TEST_SCHEDULING_XML_USES_SAME_MISSED_RUNS_T_MULTIPLEINSTANCESPOLICY,
            namespaces=namespace,
        )
        == S.IGNORENEW
    )
    assert (
        root.findtext(
            S.TEST_SCHEDULING_XML_USES_SAME_CATCHES_MISSED_RUNS_T_STARTBOUNDARY,
            namespaces=namespace,
        )
        == S.TEST_SCHEDULING_XML_USES_SAME_CLI_AND_CATCHES_MISSED_RUNS_T09
    )
    arguments = root.findtext(
        S.TEST_SCHEDULING_XML_USES_SAME_CLI_MISSED_RUNS_ARGUMENTS_T_ARGUMENTS, namespaces=namespace
    )
    assert arguments is not C.NONE
    assert S.CLI_PARSER_UNATTENDED in arguments
    assert S.CLI_PARSER_SCHEDULED in arguments
    assert S.EXPORT not in arguments
