from __future__ import annotations

import sys
from pathlib import Path

from bookystats import strings as S
from bookystats.application.sync import SyncReceipt
from bookystats.domain.models import SyncState, utc_now
from bookystats.runtime.config import Settings
from bookystats.runtime.scheduling import (
    ScheduleActivation,
    task_name,
)


def receipt(run_id: int, *, complete: bool) -> SyncReceipt:
    return SyncReceipt(
        run_id=run_id,
        state=SyncState.COMPLETE if complete else SyncState.PARTIAL,
        started_at=utc_now(),
        finished_at=utc_now(),
        account_sync_complete=complete,
        sources=(),
        metadata=(),
    )


def activation(directory: Path, settings: Settings) -> ScheduleActivation:
    return ScheduleActivation(
        task_name=task_name(directory),
        enabled_at=utc_now(),
        weekday=S.MON,
        time=S.SETTINGS_WEEKLY_TIME_TEXT,
        timezone=S.UTC,
        accounts=settings.account_fingerprint,
        implementation=S.CURRENT,
        python_executable=str(Path(sys.executable).resolve()),
    )
