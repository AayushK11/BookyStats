from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.runtime.config import atomic_write


class RunSummaryGate(C.Model):
    provider: str
    retry_at_utc: str
    http_status: int | None = C.NONE
    error_code: str | None = C.NONE


class RunSummary(C.Model):
    # Redacted, path-free record of the latest sync attempt for offline status.
    schema_version: int
    run_id: int | None = C.NONE
    trigger: str
    outcome: str
    exit_code: int
    finished_utc: str
    duration_seconds: float
    lines: tuple[str, ...]
    gates: tuple[RunSummaryGate, ...] = ()
    network_requests: dict[str, int]


def summary_path(directory: Path) -> Path:
    return directory / S.LAYOUT_RUNTIME / S.RUNSUM_FILE_NAME


def save_summary(directory: Path, summary: RunSummary) -> Path:
    path = summary_path(directory)
    atomic_write(path, summary.model_dump_json(indent=C.TWO) + S.NEWLINE)
    return path


def read_summary(directory: Path) -> RunSummary | None:
    # Offline and read-only: never creates folders, and unreadable content is simply absent.
    path = summary_path(directory)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > C.RUNSUM_MAX_BYTES:
            return C.NONE
        summary = RunSummary.model_validate_json(path.read_bytes())
    except (OSError, ValidationError):
        return C.NONE
    return summary if summary.schema_version == C.RUNSUM_SCHEMA_VERSION else C.NONE
