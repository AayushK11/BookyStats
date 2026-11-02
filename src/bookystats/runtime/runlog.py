from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import TextIO

from bookystats import __version__
from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import SyncReceipt
from bookystats.domain.models import Source, utc_now
from bookystats.persistence.raw import RawDocument
from bookystats.runtime.redaction import redact


def log_directory(directory: Path) -> Path:
    return directory / S.LOGS_FOLDER


def _logs(directory: Path) -> Iterable[Path]:
    folder = log_directory(directory)
    return (
        path
        for path in folder.glob(S.RUNLOG_PATTERN)
        if C.RUNLOG_NAME_PATTERN.fullmatch(path.name) and not path.is_symlink() and path.is_file()
    )


def latest_log(directory: Path) -> Path | None:
    # Run stamps describe start time, not when a completed or failed run was logged.
    return max(
        _logs(directory),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        default=C.NONE,
    )


def prune_logs(directory: Path, *, keep: Path) -> None:
    for path in _logs(directory):
        if path != keep:
            path.unlink()


def _stamp(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp).astimezone(UTC).strftime(S.RUNLOG_STAMP_FORMAT)


def _write(directory: Path, name: str, lines: Iterable[str], secrets: Iterable[str]) -> Path:
    folder = log_directory(directory)
    folder.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
    path = folder / name
    text = redact(S.NEWLINE.join(lines) + S.NEWLINE, secrets)
    sequence = C.ZERO
    handle: TextIO | None = C.NONE
    while handle is C.NONE:
        # Never overwrite the previous log before its replacement is complete.
        try:
            handle = path.open(S.EXCLUSIVE_CREATE_MODE, encoding=S.UTF_8, newline=S.NEWLINE)
        except FileExistsError:
            sequence += C.ONE
            original = Path(name)
            path = folder / S.RUNLOG_COLLISION_NAME.format(
                stem=original.stem, sequence=sequence, suffix=original.suffix
            )
    with handle:
        handle.write(text)
    prune_logs(directory, keep=path)
    return path


def write_run_log(
    directory: Path,
    receipt: SyncReceipt,
    *,
    trigger: str,
    inputs: Mapping[tuple[Source, str], RawDocument],
    secrets: Iterable[str],
    report_lines: Iterable[str],
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
                source=source.value + S.SLASH + collection,
                origin=PureWindowsPath(document.origin).name,
                size=len(document.body),
                sha256=document.sha256,
                captured=document.captured_at,
                document=document.id,
            )
            for (source, collection), document in inputs.items()
        )
    lines.extend([S.EMPTY, *report_lines])
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
