from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import IO

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import AlreadyRunning
from bookystats.runtime.layout import DataLayoutError, _migrate_locked


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
        self._directory = directory
        self._path = directory / S.LAYOUT_RUNTIME / S.SYNC_LOCK
        self._legacy_path = directory / S.SYNC_LOCK
        self._stack: ExitStack | None = C.NONE
        self._organized = C.FALSE
        self.migrated_files: tuple[str, ...] = ()

    @staticmethod
    def _acquire(path: Path) -> IO[bytes]:
        path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
        handle = path.open(S.SYNCLOCK_ENTER_HANDLE_A_B)
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
        return handle

    @staticmethod
    def _release(handle: IO[bytes]) -> None:
        try:
            handle.seek(C.ZERO)
            _lock_file(handle.fileno(), release=C.TRUE)
        finally:
            handle.close()

    def _release_legacy(self, handle: IO[bytes]) -> None:
        self._release(handle)
        if self._organized:
            self._legacy_path.unlink(missing_ok=C.TRUE)

    def __enter__(self) -> SyncLock:
        if self._stack is not C.NONE:
            raise AlreadyRunning(
                S.LOCKING_SYNCLOCK_ENTER_ANOTHER_BOOKYSTATS_SYNC_IS_RUNNING_FOR_THIS
            )
        self._organized = C.FALSE
        with ExitStack() as stack:
            stack.callback(self._release, self._acquire(self._path))
            if self._legacy_path.is_symlink():
                raise DataLayoutError(S.LAYOUT_INVALID_FILE.format(filename=self._legacy_path.name))
            if self._legacy_path.exists():
                stack.callback(self._release_legacy, self._acquire(self._legacy_path))
            self.migrated_files = _migrate_locked(self._directory)
            self._organized = C.TRUE
            self._stack = stack.pop_all()
        return self

    def __exit__(self, *_: object) -> None:
        if self._stack is not C.NONE:
            stack = self._stack
            self._stack = C.NONE
            stack.close()
