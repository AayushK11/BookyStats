from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import IO

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import AlreadyRunning


def _lock_file(descriptor: int, *, release: bool = C.FALSE) -> None:
    if os.name == S.NT:
        module = importlib.import_module(S.MSVCRT)
        locking: Callable[[int, int, int], None] = getattr(module, S.LOCKING)
        operation: int = getattr(module, S.LK_UNLCK if release else S.LK_NBLCK)
        locking(descriptor, operation, C.ONE)
    else:
        module = importlib.import_module(S.FCNTL)
        flock: Callable[[int, int], None] = getattr(module, S.FLOCK)
        operation = getattr(module, S.LOCK_UN if release else S.LOCK_EX)
        if not release:
            operation |= getattr(module, S.LOCK_NB)
        flock(descriptor, operation)


class SyncLock:
    def __init__(self, directory: Path) -> None:
        self._path = directory / S.SYNC_LOCK
        self._file: IO[bytes] | None = C.NONE

    def __enter__(self) -> SyncLock:
        self._path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
        handle = self._path.open(S.SYNCLOCK_ENTER_HANDLE_A_B)
        try:
            handle.seek(C.ZERO, os.SEEK_END)
            if handle.tell() == C.ZERO:
                handle.write(S.LOCKING_SYNCLOCK_ENTER_BYTES)
                handle.flush()
            handle.seek(C.ZERO)
            _lock_file(handle.fileno())
        except OSError:
            handle.close()
            raise AlreadyRunning(
                S.LOCKING_SYNCLOCK_ENTER_ANOTHER_BOOKYSTATS_SYNC_IS_RUNNING_FOR_THIS
            ) from C.NONE
        self._file = handle
        return self

    def __exit__(self, *_: object) -> None:
        handle = self._file
        if handle is C.NONE:
            return
        try:
            handle.seek(C.ZERO)
            _lock_file(handle.fileno(), release=C.TRUE)
        finally:
            handle.close()
            self._file = C.NONE
