from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import BookyError
from bookystats.persistence.inspection import pragma_integer, sidecar_paths
from bookystats.persistence.integrity import verify_connection


class BackupError(BookyError):
    pass


class StoreMigrationBlocked(BookyError):
    pass


@C.frozen_dataclass
class BackupFileRecord:
    name: str
    sha256: str
    size: int
    application_id: int
    user_version: int
    tables: Mapping[str, int]


@C.frozen_dataclass
class BackupResult:
    directory: Path
    path: Path
    kind: C.StoreKind
    reason: str
    created_at: str
    record: BackupFileRecord


def backup_root(path: Path) -> Path:
    parent = Path(path).parent
    base = parent.parent if parent.name == S.LAYOUT_DATABASES else parent
    return base / S.DBSAFE_BACKUPS_DIRECTORY


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open(S.DBSAFE_MODE_READ_BINARY) as handle:
        while chunk := handle.read(C.DBSAFE_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _flush_to_disk(path: Path) -> None:
    with path.open(S.DBSAFE_MODE_UPDATE_BINARY) as handle:
        os.fsync(handle.fileno())


def _catalog(connection: sqlite3.Connection) -> tuple[int, int, dict[str, int]]:
    tables: dict[str, int] = {}
    for row in connection.execute(S.DBSAFE_SELECT_TABLES).fetchall():
        name = str(row[C.ZERO])
        quoted = name.replace(S.DBSAFE_QUOTE, S.DBSAFE_ESCAPED_QUOTE)
        tables[name] = int(
            connection.execute(S.DBSAFE_COUNT_ROWS.format(table=quoted)).fetchone()[C.ZERO]
        )
    return (
        pragma_integer(connection, S.DBSAFE_PRAGMA_APPLICATION_ID),
        pragma_integer(connection, S.DBSAFE_PRAGMA_USER_VERSION),
        tables,
    )


def _require_space(source: sqlite3.Connection, root: Path) -> None:
    pages = pragma_integer(source, S.DBSAFE_PRAGMA_PAGE_COUNT)
    page_size = pragma_integer(source, S.DBSAFE_PRAGMA_PAGE_SIZE)
    if shutil.disk_usage(root).free < pages * page_size + C.DBSAFE_FREE_SPACE_MARGIN:
        raise BackupError(S.DBSAFE_BACKUP_NO_SPACE)


def _reserve(root: Path, created: datetime, kind: C.StoreKind, reason: str) -> tuple[Path, Path]:
    stem = S.HYPHEN.join((created.strftime(S.DBSAFE_STAMP_FORMAT), kind.value, reason))
    for attempt in range(C.ONE, C.DBSAFE_NAME_ATTEMPTS):
        name = stem if attempt == C.ONE else S.HYPHEN.join((stem, str(attempt)))
        directory = root / name
        failed = root / (name + S.DBSAFE_FAILED_SUFFIX)
        staging = root / (name + S.DBSAFE_INCOMPLETE_SUFFIX)
        if directory.exists() or failed.exists():
            continue
        try:
            staging.mkdir()
        except FileExistsError:
            continue
        return directory, staging
    raise BackupError(S.DBSAFE_BACKUP_NAME_EXHAUSTED)


def _discard(created: list[Path], staging: Path) -> None:
    # Only files this call created inside its own staging folder are removed.
    for path in created:
        path.unlink(missing_ok=C.TRUE)
    with contextlib.suppress(OSError):
        staging.rmdir()


def _copy(
    source: sqlite3.Connection, target: Path, kind: C.StoreKind, created: list[Path]
) -> BackupFileRecord:
    created.append(target)
    created.extend(sidecar_paths(target))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
        destination.execute(S.DBSAFE_PRAGMA_JOURNAL_MODE_DELETE).fetchone()
        if not verify_connection(destination, kind, comprehensive=C.FALSE).structurally_sound:
            raise BackupError(S.DBSAFE_BACKUP_COPY_DAMAGED)
        application_id, version, tables = _catalog(destination)
    finally:
        destination.close()
    _flush_to_disk(target)
    return BackupFileRecord(
        name=target.name,
        sha256=file_sha256(target),
        size=target.stat().st_size,
        application_id=application_id,
        user_version=version,
        tables=tables,
    )


def _write_manifest(
    path: Path, kind: C.StoreKind, reason: str, created_at: str, record: BackupFileRecord
) -> None:
    manifest = {
        S.DBSAFE_FORMAT: C.DBSAFE_MANIFEST_FORMAT,
        S.DBSAFE_CREATED_AT: created_at,
        S.KIND: kind.value,
        S.REASON: reason,
        S.DBSAFE_SQLITE_VERSION: sqlite3.sqlite_version,
        S.DBSAFE_FILE: {
            S.DBSAFE_NAME: record.name,
            S.DBSAFE_SHA256: record.sha256,
            S.DBSAFE_SIZE: record.size,
            S.DBSAFE_APPLICATION_ID: record.application_id,
            S.VERSION: record.user_version,
            S.DBSAFE_TABLES: dict(record.tables),
        },
    }
    with path.open(S.DBSAFE_MODE_CREATE, encoding=S.UTF_8) as handle:
        handle.write(json.dumps(manifest, indent=C.TWO, sort_keys=C.TRUE))
        handle.flush()
        os.fsync(handle.fileno())


def create_backup(
    source: sqlite3.Connection,
    path: Path,
    kind: C.StoreKind,
    *,
    reason: str,
    root: Path | None = C.NONE,
    now: datetime | None = C.NONE,
) -> BackupResult:
    path = Path(path)
    if not C.DBSAFE_REASON_PATTERN.fullmatch(reason):
        raise BackupError(S.DBSAFE_BACKUP_REASON_INVALID)
    created = (now or datetime.now(UTC)).astimezone(UTC)
    created_at = created.isoformat()
    base = Path(root) if root is not C.NONE else backup_root(path)
    base.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
    _require_space(source, base)
    directory, staging = _reserve(base, created, kind, reason)
    written: list[Path] = []
    try:
        record = _copy(source, staging / path.name, kind, written)
        manifest = staging / S.DBSAFE_MANIFEST_NAME
        written.append(manifest)
        _write_manifest(manifest, kind, reason, created_at, record)
        staging.replace(directory)
    except BaseException:
        _discard(written, staging)
        raise
    try:
        return BackupResult(
            directory=directory,
            path=directory / record.name,
            kind=kind,
            reason=reason,
            created_at=created_at,
            record=verify_backup(directory).record,
        )
    except BaseException:
        with contextlib.suppress(OSError):
            directory.replace(directory.with_name(directory.name + S.DBSAFE_FAILED_SUFFIX))
        raise


def _manifest(directory: Path) -> tuple[C.StoreKind, str, str, BackupFileRecord]:
    try:
        manifest = json.loads((directory / S.DBSAFE_MANIFEST_NAME).read_text(encoding=S.UTF_8))
        if manifest[S.DBSAFE_FORMAT] != C.DBSAFE_MANIFEST_FORMAT:
            raise ValueError(S.DBSAFE_BACKUP_MANIFEST_INVALID)
        file = manifest[S.DBSAFE_FILE]
        record = BackupFileRecord(
            name=str(file[S.DBSAFE_NAME]),
            sha256=str(file[S.DBSAFE_SHA256]),
            size=int(file[S.DBSAFE_SIZE]),
            application_id=int(file[S.DBSAFE_APPLICATION_ID]),
            user_version=int(file[S.VERSION]),
            tables={str(table): int(count) for table, count in file[S.DBSAFE_TABLES].items()},
        )
        return (
            C.StoreKind(manifest[S.KIND]),
            str(manifest[S.REASON]),
            str(manifest[S.DBSAFE_CREATED_AT]),
            record,
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise BackupError(S.DBSAFE_BACKUP_MANIFEST_INVALID) from C.NONE


def verify_backup(directory: Path) -> BackupResult:
    directory = Path(directory)
    kind, reason, created_at, record = _manifest(directory)
    if Path(record.name).name != record.name:
        raise BackupError(S.DBSAFE_BACKUP_MANIFEST_INVALID)
    path = directory / record.name
    try:
        size = path.stat().st_size
    except OSError:
        raise BackupError(S.DBSAFE_BACKUP_FILE_MISSING) from C.NONE
    if size != record.size or file_sha256(path) != record.sha256:
        raise BackupError(S.DBSAFE_BACKUP_HASH_MISMATCH)
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + S.DBSAFE_URI_IMMUTABLE, uri=C.TRUE)
        try:
            sound = verify_connection(connection, kind, comprehensive=C.FALSE).structurally_sound
            catalog = _catalog(connection)
        finally:
            connection.close()
    except sqlite3.Error:
        raise BackupError(S.DBSAFE_BACKUP_COPY_DAMAGED) from C.NONE
    if not sound or catalog != (record.application_id, record.user_version, dict(record.tables)):
        raise BackupError(S.DBSAFE_BACKUP_COPY_DAMAGED)
    return BackupResult(
        directory=directory,
        path=path,
        kind=kind,
        reason=reason,
        created_at=created_at,
        record=record,
    )


def restore_backup(directory: Path, target: Path) -> Path:
    # Restoring never overwrites: the owner moves a damaged file aside first.
    target = Path(target)
    backup = verify_backup(directory)
    if target.exists() or any(sidecar.exists() for sidecar in sidecar_paths(target)):
        raise BackupError(S.DBSAFE_RESTORE_TARGET_EXISTS)
    target.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
    staging = target.with_name(target.name + S.DBSAFE_RESTORING_SUFFIX)
    try:
        shutil.copyfile(backup.path, staging)
        if file_sha256(staging) != backup.record.sha256:
            raise BackupError(S.DBSAFE_BACKUP_HASH_MISMATCH)
        _flush_to_disk(staging)
        staging.replace(target)
    except BaseException:
        staging.unlink(missing_ok=C.TRUE)
        raise
    return target


def protect_migration(
    connection: sqlite3.Connection, path: Path, kind: C.StoreKind, *, reason: str
) -> BackupResult:
    try:
        if not verify_connection(connection, kind, comprehensive=C.FALSE).structurally_sound:
            raise StoreMigrationBlocked(S.DBSAFE_BLOCKED_INTEGRITY)
        return create_backup(connection, path, kind, reason=reason)
    except (BackupError, OSError, sqlite3.Error):
        raise StoreMigrationBlocked(S.DBSAFE_BLOCKED_BACKUP) from C.NONE
