from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.persistence.cache import _row_intact, _valid_quota
from bookystats.persistence.inspection import (
    ReadOnlyConnection,
    StoreStateError,
    read_consistent,
    require_readable,
)
from bookystats.runtime.config import atomic_write
from bookystats.runtime.layout import database_path


class RunSummaryGate(C.Model):
    provider: str
    retry_at_utc: str
    http_status: int | None = C.NONE
    error_code: str | None = C.NONE
    daily_limit: bool = C.FALSE


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


def read_provider_gates(directory: Path) -> tuple[RunSummaryGate, ...]:
    # Reuse cache integrity/diagnostic policy without constructing a cache, which can migrate.
    # The inspection reader is read-only and does not create WAL/SHM files.
    def read(handle: ReadOnlyConnection) -> tuple[RunSummaryGate, ...]:
        require_readable(handle, C.StoreKind.METADATA)
        gates: list[RunSummaryGate] = []
        for provider, host in C.OUTCOME_PROVIDER_HOSTS.items():
            row = handle.connection.execute(
                S.DR_RETRY_SELECT, (provider.value, hashlib.sha256(host.encode()).hexdigest())
            ).fetchone()
            if row is C.NONE or not _row_intact(row[C.ZERO], C.ZERO, row[C.ONE]):
                continue
            value = json.loads(row[C.ZERO])
            if not isinstance(value, dict) or set(value) not in (
                C.DR_RETRY_KEYS,
                C.L1_RETRY_KEYS_WITH_QUOTA,
            ):
                continue
            deadline = value.get(S.DR_RETRY_AT)
            status = value.get(S.DR_STATUS_CODE)
            quota = value.get(S.L1_QUOTA, {})
            if (
                isinstance(deadline, bool)
                or not isinstance(deadline, int | float)
                or not math.isfinite(deadline)
                or deadline < C.ZERO
                or not _valid_quota(quota)
            ):
                continue
            if status is not C.NONE and (
                isinstance(status, bool)
                or not isinstance(status, int)
                or not C.DR_STATUS_MIN <= status <= C.DR_STATUS_MAX
            ):
                continue
            try:
                retry = datetime.fromtimestamp(deadline, UTC).strftime(S.RUNSUM_TIME_FORMAT)
            except (OverflowError, OSError, ValueError):
                continue
            gates.append(
                RunSummaryGate(
                    provider=provider.value,
                    retry_at_utc=retry,
                    http_status=status,
                    daily_limit=provider == C.Source.GOOGLE_BOOKS
                    and isinstance(quota, dict)
                    and quota.get(S.L1_QUOTA_SCOPE) == S.L1_QUOTA_DAILY,
                )
            )
        return tuple(gates)

    try:
        return read_consistent(database_path(directory, S.METADATA_SQLITE3), read)
    except (StoreStateError, ValueError, TypeError, RecursionError, OverflowError, OSError):
        return ()
