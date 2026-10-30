from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from pydantic import Field, JsonValue, ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.config import Settings, atomic_write
from bookystats.errors import ConfigurationError
from bookystats.models import Model, Source, utc_now
from bookystats.sync import SyncReceipt


class RunEvidence(Model):
    run_id: int
    accounts: str
    implementation: str
    completed_at: str
    account_sync_complete: bool
    unattended: bool


class StabilityHistory(Model):
    schema_version: int = Field(default=C.ONE, ge=C.ONE, le=C.ONE)
    runs: tuple[RunEvidence, ...] = ()


class ScheduleActivation(Model):
    task_name: str
    enabled_at: str
    weekday: str
    time: str
    timezone: str
    accounts: str | None = C.NONE
    implementation: str | None = C.NONE
    python_executable: str | None = C.NONE


def implementation_fingerprint() -> str:
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob(S.SCHEDULING_IMPLEMENTATION_FINGERPRINT_PY)):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_history(directory: Path) -> StabilityHistory:
    path = directory / S.STABILITY_JSON
    if not path.exists():
        return StabilityHistory()
    try:
        return StabilityHistory.model_validate_json(path.read_bytes())
    except ValidationError:
        raise ConfigurationError(
            S.SCHEDULING_READ_HISTORY_THE_LOCAL_RECEIPT_IS_INVALID_WEEKLY
        ) from C.NONE


def record_live_run(
    directory: Path, settings: Settings, receipt: SyncReceipt, *, unattended: bool
) -> None:
    history = _read_history(directory)
    evidence = RunEvidence(
        run_id=receipt.run_id,
        accounts=settings.account_fingerprint,
        implementation=implementation_fingerprint(),
        completed_at=receipt.finished_at,
        account_sync_complete=receipt.account_sync_complete,
        unattended=unattended,
    )
    updated = history.model_copy(update={S.RUNS: (*history.runs[-C.SEVEN :], evidence)})
    atomic_write(directory / S.STABILITY_JSON, updated.model_dump_json(indent=C.TWO) + S.NEWLINE)


def require_stable(
    directory: Path, settings: Settings, database_status: dict[str, JsonValue]
) -> None:
    if {account.source for account in settings.accounts} != {Source.STORYGRAPH, Source.GOODREADS}:
        raise ConfigurationError(S.SCHEDULING_REQUIRE_STABLE_BOTH_READER_MUST_BE_CONFIGURED_BEFORE)
    runs = _read_history(directory).runs[-C.TWO :]
    current = implementation_fingerprint()
    if (
        len(runs) != C.TWO
        or runs[C.ZERO].run_id == runs[C.ONE].run_id
        or (
            not all(
                run.account_sync_complete
                and run.accounts == settings.account_fingerprint
                and (run.implementation == current)
                for run in runs
            )
        )
        or (not any(run.unattended for run in runs))
    ):
        raise ConfigurationError(S.SCHEDULING_REQUIRE_STABLE_WEEKLY_TWO_CONSECUTIVE_COMPLETE_LIVE)
    latest = database_status.get(S.LAST_RUN)
    if not isinstance(latest, dict) or latest.get(S.RUN_ID) != runs[-C.ONE].run_id:
        raise ConfigurationError(
            S.SCHEDULING_REQUIRE_STABLE_THE_STABILITY_RECEIPT_DOES_NOT_MATCH_THE
        )
    latest_time = datetime.fromisoformat(runs[-C.ONE].completed_at)
    if latest_time.tzinfo is C.NONE or datetime.now().astimezone() - latest_time > timedelta(
        days=C.SEVEN
    ):
        raise ConfigurationError(
            S.SCHEDULING_REQUIRE_STABLE_THE_COMPLETE_LIVE_SYNC_RECEIPT_IS_STALE
        )


def task_name(directory: Path) -> str:
    suffix = hashlib.sha256(str(directory.resolve()).casefold().encode()).hexdigest()[
        : C.SCHEDULING_TASK_NAME_SUFFIX
    ]
    return S.SCHEDULING_TASK_NAME_TEMPLATE.format(v0=suffix)


def task_xml(
    directory: Path, python_executable: Path, settings: Settings, *, now: datetime | None = C.NONE
) -> str:
    weekly = settings.weekly
    if not weekly.enabled or weekly.weekday is C.NONE or weekly.time is C.NONE:
        raise ConfigurationError(S.SCHEDULING_TASK_XML_WEEKLY_SCHEDULING_IS_DISABLED_OR_LACKS_ITS)
    current = now or datetime.now().astimezone()
    hour, minute = (int(value) for value in weekly.time.split(S.COLON))
    target_weekday = tuple(C.SCHEDULING_WEEKDAYS).index(weekly.weekday)
    boundary = current.replace(hour=hour, minute=minute, second=C.ZERO, microsecond=C.ZERO)
    boundary += timedelta(days=(target_weekday - current.weekday()) % C.SEVEN)
    if boundary <= current:
        boundary += timedelta(days=C.SEVEN)
    task = ET.Element(
        S.TASK,
        {
            S.VERSION: S.SCHEDULING_TASK_XML_TASK_TEXT,
            S.XMLNS: S.SCHEDULING_TASK_XML_TASK_HTTP_SCHEMAS_MICROSOFT_COM_WINDOWS_MIT_TASK,
        },
    )
    registration = ET.SubElement(task, S.REGISTRATIONINFO)
    ET.SubElement(
        registration, S.DESCRIPTION_2
    ).text = S.SCHEDULING_TASK_XML_BOOKYSTATS_WEEKLY_ACCOUNT_INGESTION_REQUIRES
    triggers = ET.SubElement(task, S.TRIGGERS)
    trigger = ET.SubElement(triggers, S.CALENDARTRIGGER)
    ET.SubElement(trigger, S.STARTBOUNDARY).text = boundary.strftime(
        S.SCHEDULING_TASK_XML_Y_M_DT_H_M_S
    )
    ET.SubElement(trigger, S.ENABLED).text = S.TRUE_2
    schedule = ET.SubElement(trigger, S.SCHEDULEBYWEEK)
    ET.SubElement(schedule, S.WEEKSINTERVAL).text = S.SCHEDULING_TASK_XML_TEXT
    ET.SubElement(ET.SubElement(schedule, S.DAYSOFWEEK), C.SCHEDULING_WEEKDAYS[weekly.weekday])
    principals = ET.SubElement(task, S.PRINCIPALS)
    principal = ET.SubElement(principals, S.PRINCIPAL, {S.ID: S.READER_2})
    ET.SubElement(principal, S.LOGONTYPE).text = S.INTERACTIVETOKEN
    ET.SubElement(principal, S.RUNLEVEL).text = S.LEASTPRIVILEGE
    configuration = ET.SubElement(task, S.SETTINGS)
    for key, value in (
        (S.MULTIPLEINSTANCESPOLICY, S.IGNORENEW),
        (S.DISALLOWSTARTIFONBATTERIES, S.FALSE_2),
        (S.STOPIFGOINGONBATTERIES, S.FALSE_2),
        (S.STARTWHENAVAILABLE, S.TRUE_2),
        (S.RUNONLYIFNETWORKAVAILABLE, S.TRUE_2),
        (S.ENABLED, S.TRUE_2),
        (S.EXECUTIONTIMELIMIT, S.PT4H),
    ):
        ET.SubElement(configuration, key).text = value
    action = ET.SubElement(ET.SubElement(task, S.ACTIONS, {S.CONTEXT: S.READER_2}), S.EXEC)
    ET.SubElement(action, S.COMMAND_2).text = str(python_executable.resolve())
    ET.SubElement(action, S.ARGUMENTS).text = subprocess.list2cmdline(
        [
            S.SCHEDULING_TASK_XML_M,
            S.BOOKYSTATS_2,
            S.SYNC,
            S.CLI_PARSER_UNATTENDED,
            S.CLI_PARSER_SCHEDULED,
            S.CLI_PARSER_DATA_DIR,
            str(directory.resolve()),
        ]
    )
    ET.SubElement(action, S.WORKINGDIRECTORY).text = str(directory.resolve())
    return ET.tostring(task, encoding=S.UNICODE, xml_declaration=C.TRUE)


def _powershell(script: str) -> str:
    completed = subprocess.run(
        [
            S.POWERSHELL_EXE,
            S.SCHEDULING_POWERSHELL_COMPLETED_NOPROFILE,
            S.SCHEDULING_POWERSHELL_COMPLETED_NONINTERACTIVE,
            S.SCHEDULING_POWERSHELL_COMPLETED_COMMAND,
            script,
        ],
        capture_output=C.TRUE,
        text=C.TRUE,
        timeout=C.POWERSHELL_COMPLETED_TIMEOUT,
        check=C.FALSE,
    )
    if completed.returncode:
        raise ConfigurationError(S.SCHEDULING_POWERSHELL_WINDOWS_TASK_OPERATION_FAILED_THE_PRIOR)
    return completed.stdout.strip()


def _ps_literal(value: str) -> str:
    return (
        S.SCHEDULING_PS_LITERAL_TEXT
        + value.replace(S.SCHEDULING_PS_LITERAL_TEXT, S.SCHEDULING_PS_LITERAL_TEXT_2)
        + S.SCHEDULING_PS_LITERAL_TEXT
    )


def _read_activation(directory: Path) -> ScheduleActivation | None:
    path = directory / S.SCHEDULE_JSON
    if not path.exists():
        return C.NONE
    try:
        return ScheduleActivation.model_validate_json(path.read_bytes())
    except ValidationError:
        raise ConfigurationError(S.INVALID_ACTIVATION) from C.NONE


def _activation_matches(
    activation: ScheduleActivation,
    directory: Path,
    python_executable: Path,
    settings: Settings,
) -> bool:
    return (
        activation.task_name == task_name(directory)
        and activation.accounts == settings.account_fingerprint
        and activation.implementation == implementation_fingerprint()
        and activation.python_executable is not C.NONE
        and Path(activation.python_executable) == python_executable.resolve()
        and activation.weekday == settings.weekly.weekday
        and activation.time == settings.weekly.time
        and activation.timezone == settings.weekly.timezone
    )


def require_activation(directory: Path, python_executable: Path, settings: Settings) -> None:
    activation = _read_activation(directory)
    if (
        not settings.weekly.enabled
        or activation is C.NONE
        or not _activation_matches(activation, directory, python_executable, settings)
    ):
        raise ConfigurationError(S.SCHEDULE_REVALIDATION_REQUIRED)


def _task_xml_reader(path: Path) -> str:
    return S.TASK_XML_READER.format(path=_ps_literal(str(path)))


def enable_weekly(
    directory: Path,
    python_executable: Path,
    settings: Settings,
    database_status: dict[str, JsonValue],
) -> str:
    if not settings.weekly.enabled:
        raise ConfigurationError(
            S.SCHEDULING_ENABLE_WEEKLY_SET_AN_WEEKLY_SCHEDULE_BEFORE_REQUESTING
        )
    if settings.weekly.weekday is C.NONE or settings.weekly.time is C.NONE:
        raise ConfigurationError(S.SCHEDULE_REVALIDATION_REQUIRED)
    if os.name != S.NT:
        raise ConfigurationError(S.SCHEDULING_ENABLE_WEEKLY_AUTOMATIC_CURRENTLY_SUPPORTS_WINDOWS)
    activation = _read_activation(directory)
    if (
        activation is not C.NONE
        and _activation_matches(activation, directory, python_executable, settings)
        and schedule_status(directory, settings).get(S.ENABLED_2) is C.TRUE
    ):
        return activation.task_name
    require_stable(directory, settings, database_status)
    zone = _powershell(S.SCHEDULING_ENABLE_WEEKLY_ZONE_STOP_GET_TIMEZONE_ID)
    if settings.weekly.timezone != zone:
        raise ConfigurationError(S.SCHEDULING_ENABLE_WEEKLY_THE_CONFIGURED_TIME_ZONE_MUST_MATCH)
    xml_path = directory / S.WEEKLY_TASK_XML
    atomic_write(xml_path, task_xml(directory, python_executable, settings))
    name = task_name(directory)
    try:
        _powershell(
            S.SCHEDULING_ENABLE_WEEKLY_TEMPLATE.format(
                v0=_task_xml_reader(xml_path), v1=_ps_literal(name), v2=_ps_literal(name)
            )
        )
    finally:
        xml_path.unlink(missing_ok=C.TRUE)
    activated = ScheduleActivation(
        task_name=name,
        enabled_at=utc_now(),
        weekday=settings.weekly.weekday,
        time=settings.weekly.time,
        timezone=zone,
        accounts=settings.account_fingerprint,
        implementation=implementation_fingerprint(),
        python_executable=str(python_executable.resolve()),
    )
    atomic_write(directory / S.SCHEDULE_JSON, activated.model_dump_json(indent=C.TWO) + S.NEWLINE)
    return name


def schedule_status(directory: Path, settings: Settings) -> dict[str, JsonValue]:
    path = directory / S.SCHEDULE_JSON
    if not path.exists():
        return {
            S.ENABLED_2: C.FALSE,
            S.CONFIGURED: settings.weekly.enabled,
            S.STATE: S.NOT_REGISTERED,
        }
    if os.name != S.NT:
        return {
            S.ENABLED_2: C.FALSE,
            S.CONFIGURED: settings.weekly.enabled,
            S.STATE: S.UNSUPPORTED_HOST,
        }
    name = task_name(directory)
    output = _powershell(
        S.SCHEDULING_SCHEDULE_STATUS_OUTPUT_TEMPLATE.format(
            v0=_ps_literal(name), v1=_ps_literal(name)
        )
    )
    if output == S.NULL:
        return {
            S.ENABLED_2: C.FALSE,
            S.CONFIGURED: settings.weekly.enabled,
            S.STATE: S.TASK_MISSING,
        }
    try:
        parsed: JsonValue = json.loads(output)
    except json.JSONDecodeError:
        raise ConfigurationError(
            S.SCHEDULING_SCHEDULE_STATUS_WINDOWS_AN_UNREADABLE_SCHEDULE_STATUS
        ) from C.NONE
    if not isinstance(parsed, dict):
        raise ConfigurationError(S.SCHEDULING_SCHEDULE_STATUS_WINDOWS_AN_UNEXPECTED_SCHEDULE_STATUS)
    parsed[S.CONFIGURED] = settings.weekly.enabled
    return parsed
