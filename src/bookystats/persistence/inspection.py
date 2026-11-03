from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import BookyError


class StoreStateError(BookyError):
    def __init__(self, state: C.StoreState, message: str) -> None:
        super().__init__(message)
        self.state = state


class StoreUpgradeRequired(StoreStateError):
    pass


class StoreChangedDuringRead(StoreStateError):
    pass


@C.frozen_dataclass
class FileState:
    size: int
    modified_ns: int


@C.frozen_dataclass
class StoreInspection:
    kind: C.StoreKind
    state: C.StoreState
    version: int | None
    target_version: int
    application_id: int | None
    journal_mode: str | None
    readable: bool
    detail: str

    def report(self) -> dict[str, JsonValue]:
        return {
            S.STATE: self.state.value,
            S.VERSION: self.version,
            S.DBSAFE_TARGET_VERSION: self.target_version,
            S.DBSAFE_APPLICATION_ID: self.application_id,
            S.DBSAFE_JOURNAL_MODE: self.journal_mode,
            S.DBSAFE_READABLE: self.readable,
            S.DETAIL: self.detail,
        }


def sidecar_paths(path: Path) -> tuple[Path, ...]:
    return tuple(path.with_name(path.name + suffix) for suffix in C.LAYOUT_SQLITE_SIDECARS)


def has_sidecars(path: Path) -> bool:
    return any(sidecar.exists() for sidecar in sidecar_paths(path))


def file_state(path: Path) -> FileState | None:
    try:
        stat = path.stat()
    except OSError:
        return C.NONE
    return FileState(stat.st_size, stat.st_mtime_ns)


def pragma_integer(connection: sqlite3.Connection, statement: str) -> int:
    value = connection.execute(statement).fetchone()[C.ZERO]
    return value if isinstance(value, int) else C.ZERO


def state_error(error: sqlite3.Error) -> StoreStateError:
    text = str(error).lower()
    if any(word in text for word in C.DBSAFE_BUSY_WORDS):
        return StoreStateError(C.StoreState.BUSY, S.DBSAFE_MESSAGE_BUSY)
    if any(word in text for word in C.DBSAFE_RECOVERY_WORDS):
        return StoreStateError(C.StoreState.DAMAGED, S.DBSAFE_MESSAGE_RECOVERY)
    return StoreStateError(C.StoreState.DAMAGED, S.DBSAFE_MESSAGE_DAMAGED)


def _read_header(path: Path) -> bytes:
    try:
        with path.open(S.DBSAFE_MODE_READ_BINARY) as handle:
            header = handle.read(C.DBSAFE_HEADER_SIZE)
    except FileNotFoundError:
        raise StoreStateError(C.StoreState.ABSENT, S.DBSAFE_MESSAGE_ABSENT) from C.NONE
    except OSError:
        raise StoreStateError(C.StoreState.DAMAGED, S.DBSAFE_MESSAGE_UNREADABLE) from C.NONE
    if not header:
        raise StoreStateError(C.StoreState.ABSENT, S.DBSAFE_MESSAGE_ABSENT)
    if not header.startswith(S.DBSAFE_SQLITE_MAGIC):
        raise StoreStateError(C.StoreState.UNRECOGNIZED, S.DBSAFE_MESSAGE_FOREIGN)
    if len(header) < C.DBSAFE_HEADER_SIZE:
        raise StoreStateError(C.StoreState.DAMAGED, S.DBSAFE_MESSAGE_DAMAGED)
    return header


class ReadOnlyConnection:
    # A WAL database at rest is opened immutable only because a plain read-only open would create
    # -wal/-shm sidecars. Immutable skips locking, so a later size/time/sidecar change means a
    # writer appeared and the read must be repeated rather than trusted.
    def __init__(
        self,
        connection: sqlite3.Connection,
        path: Path,
        *,
        immutable: bool,
        wal: bool,
        state: FileState | None,
    ) -> None:
        self.connection = connection
        self.path = path
        self.immutable = immutable
        self.wal = wal
        self._state = state

    def stable(self) -> bool:
        if not self.immutable:
            return C.TRUE
        return file_state(self.path) == self._state and not has_sidecars(self.path)

    def close(self) -> None:
        self.connection.close()


def open_read_only(path: Path) -> ReadOnlyConnection:
    path = Path(path)
    header = _read_header(path)
    wal = header[C.DBSAFE_HEADER_FORMAT_OFFSET] == C.DBSAFE_WAL_FORMAT
    immutable = wal and not has_sidecars(path)
    before = file_state(path)
    suffix = S.DBSAFE_URI_IMMUTABLE if immutable else S.DBSAFE_URI_READ_ONLY
    try:
        connection = sqlite3.connect(
            path.resolve().as_uri() + suffix,
            uri=C.TRUE,
            timeout=C.DBSAFE_READ_TIMEOUT_SECONDS,
            isolation_level=C.NONE,
        )
    except sqlite3.Error as error:
        raise state_error(error) from error
    return ReadOnlyConnection(connection, path, immutable=immutable, wal=wal, state=before)


def read_consistent[T](path: Path, work: Callable[[ReadOnlyConnection], T]) -> T:
    for _attempt in range(C.DBSAFE_READ_ATTEMPTS):
        handle = open_read_only(path)
        try:
            handle.connection.execute(S.BEGIN)
            result = work(handle)
        except sqlite3.Error as error:
            if handle.stable():
                raise state_error(error) from error
        except StoreStateError:
            if handle.stable():
                raise
        else:
            if handle.stable():
                return result
        finally:
            handle.close()
    raise StoreChangedDuringRead(C.StoreState.BUSY, S.DBSAFE_MESSAGE_CHANGED)


def matches_shapes(
    connection: sqlite3.Connection, contract: C.StoreContract, tables: frozenset[str]
) -> bool:
    if not contract.required_tables <= tables or not tables <= set(contract.shapes):
        return C.FALSE
    for table in tables:
        rows = connection.execute(S.DBSAFE_TABLE_INFO.format(table=table)).fetchall()
        shape = tuple((row[C.ONE], row[C.TWO], row[C.THREE], row[C.FIVE]) for row in rows)
        if shape != contract.shapes[table]:
            return C.FALSE
    return C.TRUE


def classify(handle: ReadOnlyConnection, kind: C.StoreKind) -> StoreInspection:
    contract = C.DBSAFE_CONTRACTS[kind]
    connection = handle.connection
    try:
        application_id = pragma_integer(connection, S.DBSAFE_PRAGMA_APPLICATION_ID)
        version = pragma_integer(connection, S.DBSAFE_PRAGMA_USER_VERSION)
        tables = frozenset(
            str(row[C.ZERO]) for row in connection.execute(S.DBSAFE_SELECT_TABLES).fetchall()
        )
        adoptable = (
            contract.adopts_unstamped
            and application_id == C.ZERO
            and version == C.ZERO
            and matches_shapes(connection, contract, tables)
        )
    except sqlite3.Error as error:
        raise state_error(error) from error
    journal = S.DBSAFE_JOURNAL_WAL if handle.wal else S.DBSAFE_JOURNAL_ROLLBACK

    def inspection(state: C.StoreState, readable: bool, detail: str) -> StoreInspection:
        return StoreInspection(
            kind=kind,
            state=state,
            version=version,
            target_version=contract.current_version,
            application_id=application_id,
            journal_mode=journal,
            readable=readable,
            detail=detail,
        )

    if application_id == C.ZERO and version == C.ZERO:
        if not tables:
            return inspection(C.StoreState.ABSENT, C.FALSE, S.DBSAFE_MESSAGE_NO_TABLES)
        if adoptable:
            return inspection(C.StoreState.UPGRADE_NEEDED, C.TRUE, S.DBSAFE_MESSAGE_ADOPT)
        return inspection(C.StoreState.UNRECOGNIZED, C.FALSE, S.DBSAFE_MESSAGE_FOREIGN)
    if application_id not in contract.accepted_application_ids:
        return inspection(C.StoreState.UNRECOGNIZED, C.FALSE, S.DBSAFE_MESSAGE_FOREIGN)
    if version > contract.current_version:
        return inspection(C.StoreState.NEWER_THAN_SUPPORTED, C.FALSE, S.DBSAFE_MESSAGE_NEWER)
    if version == contract.current_version:
        missing = contract.required_tables - tables
        if missing:
            return inspection(
                C.StoreState.DAMAGED,
                C.FALSE,
                S.DBSAFE_MESSAGE_MISSING_TABLES.format(tables=S.COMMA.join(sorted(missing))),
            )
        return inspection(C.StoreState.CURRENT, C.TRUE, S.DBSAFE_MESSAGE_CURRENT)
    if version in contract.upgrade_versions:
        return inspection(
            C.StoreState.UPGRADE_NEEDED,
            version in contract.readable_versions,
            S.DBSAFE_MESSAGE_UPGRADE.format(version=version, target=contract.current_version),
        )
    return inspection(C.StoreState.UNRECOGNIZED, C.FALSE, S.DBSAFE_MESSAGE_FOREIGN)


def require_readable(handle: ReadOnlyConnection, kind: C.StoreKind) -> StoreInspection:
    inspection = classify(handle, kind)
    if inspection.readable:
        return inspection
    if inspection.state is C.StoreState.UPGRADE_NEEDED:
        raise StoreUpgradeRequired(inspection.state, inspection.detail)
    raise StoreStateError(inspection.state, inspection.detail)


def inspect_store(path: Path, kind: C.StoreKind) -> StoreInspection:
    contract = C.DBSAFE_CONTRACTS[kind]
    try:
        return read_consistent(path, lambda handle: classify(handle, kind))
    except StoreStateError as error:
        return StoreInspection(
            kind=kind,
            state=error.state,
            version=C.NONE,
            target_version=contract.current_version,
            application_id=C.NONE,
            journal_mode=C.NONE,
            readable=C.FALSE,
            detail=str(error),
        )
