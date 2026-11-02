from __future__ import annotations

from pathlib import Path

import pytest

from bookystats import strings as S
from bookystats.domain.errors import AlreadyRunning
from bookystats.runtime.locking import SyncLock


def test_overlapping_sync_is_rejected_and_lock_is_released(tmp_path: Path) -> None:
    with SyncLock(tmp_path), pytest.raises(AlreadyRunning), SyncLock(tmp_path):
        pytest.fail(S.TEST_LOCKING_OVERLAPPING_SYNC_IS_CONCURRENT_SYNC_ACQUIRED_THE_LOCK)
    with SyncLock(tmp_path):
        pass
