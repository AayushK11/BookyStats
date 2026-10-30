from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from bookystats import __version__
from bookystats import constants as C
from bookystats import strings as S
from bookystats.models import Source, utc_now
from bookystats.raw import RawDocument
from bookystats.redaction import redact
from bookystats.report import run_lines
from bookystats.sync import SyncReceipt


def log_directory(directory: Path) -> Path:
    return directory / S.LOGS_FOLDER


def latest_log(directory: Path) -> Path | None:
    folder = log_directory(directory)
    if not folder.is_dir():
        return C.NONE
    # File names start with a fixed-width UTC stamp, so the greatest name is the newest log.
    return max(folder.glob(S.RUNLOG_PATTERN), default=C.NONE)


def _stamp(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp).astimezone(UTC).strftime(S.RUNLOG_STAMP_FORMAT)


def _write(directory: Path, name: str, lines: Iterable[str], secrets: Iterable[str]) -> Path:
    folder = log_directory(directory)
    folder.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
    path = folder / name
    text = redact(S.NEWLINE.join(lines) + S.NEWLINE, secrets)
    # Exclusive creation: a log is history and is never overwritten.
    with path.open(S.EXCLUSIVE_CREATE_MODE, encoding=S.UTF_8, newline=S.NEWLINE) as handle:
        handle.write(text)
    return path


def write_run_log(
    directory: Path,
    receipt: SyncReceipt,
    *,
    trigger: str,
    inputs: Mapping[Source, RawDocument],
    secrets: Iterable[str],
) -> Path:
    lines = [
        S.RUNLOG_TITLE,
        S.RUNLOG_VERSION_LINE.format(version=__version__),
        S.RUNLOG_RUN_LINE.format(run_id=receipt.run_id, trigger=trigger),
        S.RUNLOG_STATE_LINE.format(state=receipt.state.value),
        S.RUNLOG_STARTED_LINE.format(started=receipt.started_at),
        S.RUNLOG_FINISHED_LINE.format(finished=receipt.finished_at),
    ]
    if inputs:
        lines.extend([S.EMPTY, S.RUNLOG_FILES_HEADING])
        lines.extend(
            S.RUNLOG_FILE_LINE.format(
                source=source.value,
                origin=document.origin,
                size=len(document.body),
                sha256=document.sha256,
                captured=document.captured_at,
                document=document.id,
            )
            for source, document in inputs.items()
        )
    lines.extend([S.EMPTY, *run_lines(receipt, issue_limit=C.NONE)])
    name = S.RUNLOG_FILE_NAME.format(stamp=_stamp(receipt.started_at), run_id=receipt.run_id)
    return _write(directory, name, lines, secrets)


def write_failure_log(directory: Path, message: str, *, secrets: Iterable[str]) -> Path:
    now = utc_now()
    lines = [
        S.RUNLOG_FAILED_TITLE,
        S.RUNLOG_VERSION_LINE.format(version=__version__),
        S.RUNLOG_TIME_LINE.format(time=now),
        S.RUNLOG_FAILURE_LINE.format(message=message),
    ]
    return _write(directory, S.RUNLOG_FAILED_FILE_NAME.format(stamp=_stamp(now)), lines, secrets)
