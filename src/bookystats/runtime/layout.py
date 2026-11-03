from __future__ import annotations

import sqlite3
from pathlib import Path

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import ConfigurationError


class DataLayoutError(ConfigurationError):
    pass


def _resolve(legacy: Path, organized: Path) -> Path:
    for path in (legacy, organized):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise DataLayoutError(S.LAYOUT_INVALID_FILE.format(filename=path.name))
    if legacy.exists() and organized.exists():
        raise DataLayoutError(S.LAYOUT_CONFLICT.format(filename=legacy.name))
    return legacy if legacy.exists() else organized


def database_path(directory: Path, filename: str) -> Path:
    if filename not in C.CLI_LOCAL_DATABASES:
        raise DataLayoutError(S.LAYOUT_INVALID_NAME)
    return _resolve(directory / filename, directory / S.LAYOUT_DATABASES / filename)


def google_credentials_path(directory: Path) -> Path:
    return _resolve(
        directory / S.OAUTH_FILE,
        directory / S.LAYOUT_CREDENTIALS / S.OAUTH_FILE,
    )


def _checkpoint(path: Path) -> None:
    connection = sqlite3.connect(path, timeout=C.ZERO)
    try:
        rows = connection.execute(S.LAYOUT_INTEGRITY).fetchall()
        if tuple(rows) != C.LAYOUT_VALID_INTEGRITY:
            raise DataLayoutError(S.LAYOUT_DATABASE_INVALID.format(filename=path.name))
        checkpoint = connection.execute(S.LAYOUT_CHECKPOINT).fetchone()
        if checkpoint is C.NONE or checkpoint[C.ZERO] != C.ZERO:
            raise DataLayoutError(S.LAYOUT_DATABASE_BUSY.format(filename=path.name))
    finally:
        connection.close()
    # Moving only the main file is unsafe while journal/coordination files remain.
    if any(path.with_name(path.name + suffix).exists() for suffix in C.LAYOUT_SQLITE_SIDECARS):
        raise DataLayoutError(S.LAYOUT_DATABASE_BUSY.format(filename=path.name))


def _migrate_locked(directory: Path) -> tuple[str, ...]:
    candidates = [
        (directory / filename, directory / S.LAYOUT_DATABASES / filename, C.TRUE)
        for filename in C.CLI_LOCAL_DATABASES
    ]
    candidates.append(
        (
            directory / S.OAUTH_FILE,
            directory / S.LAYOUT_CREDENTIALS / S.OAUTH_FILE,
            C.FALSE,
        )
    )
    for legacy, organized, _ in candidates:
        _resolve(legacy, organized)
    for legacy, _, database in candidates:
        if legacy.exists() and database:
            _checkpoint(legacy)
    moved: list[str] = []
    for legacy, organized, _ in candidates:
        if legacy.exists():
            organized.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
            legacy.rename(organized)
            moved.append(legacy.name)
    return tuple(moved)
