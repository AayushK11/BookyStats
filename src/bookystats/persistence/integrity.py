from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path

from bookystats import constants as C
from bookystats import strings as S
from bookystats.persistence.inspection import StoreStateError, read_consistent
from bookystats.persistence.payloads import PayloadIntegrityError, PayloadStore


@C.frozen_dataclass
class IntegrityReport:
    kind: C.StoreKind
    comprehensive: bool
    checked: Mapping[str, int]
    failures: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def structurally_sound(self) -> bool:
        return S.DBSAFE_FAILURE_INTEGRITY not in self.failures and (
            S.DBSAFE_FAILURE_UNREADABLE not in self.failures
        )

    def report(self) -> dict[str, object]:
        return {
            S.KIND: self.kind.value,
            S.DBSAFE_OK: self.ok,
            S.DBSAFE_COMPREHENSIVE: self.comprehensive,
            S.DBSAFE_CHECKED: dict(self.checked),
            S.DBSAFE_FAILURES: list(self.failures),
        }


def _has_table(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(S.DBSAFE_TABLE_EXISTS, (table,)).fetchone() is not C.NONE


def _damaged_collections(
    connection: sqlite3.Connection, payloads: PayloadStore, verified: set[str]
) -> int:
    # A collection payload lists record payload references; each must resolve to a verified payload.
    damaged = C.ZERO
    seen: set[str] = set()
    for table, column in C.DBSAFE_COLLECTION_COLUMNS:
        query = S.DBSAFE_SELECT_COLLECTION_REFERENCES.format(table=table, column=column)
        for (reference,) in connection.execute(query).fetchall():
            if reference in seen:
                continue
            seen.add(reference)
            try:
                collection = payloads.load(reference)
            except PayloadIntegrityError:
                damaged += C.ONE
                continue
            records = collection.get(S.RECORDS) if isinstance(collection, dict) else C.NONE
            if not isinstance(records, list) or any(
                not isinstance(record, str)
                or not record.startswith(S.STORAGE_PAYLOAD_PREFIX)
                or record[len(S.STORAGE_PAYLOAD_PREFIX) :] not in verified
                for record in records
            ):
                damaged += C.ONE
    return damaged


def _library_payloads(connection: sqlite3.Connection, checked: dict[str, int]) -> list[str]:
    if not _has_table(connection, S.DBSAFE_PAYLOAD_TABLE):
        return []
    failures: list[str] = []
    payloads = PayloadStore(connection)
    digests = [str(row[C.ZERO]) for row in connection.execute(S.DBSAFE_SELECT_PAYLOAD_DIGESTS)]
    verified: set[str] = set()
    damaged = C.ZERO
    for digest in digests:
        try:
            payloads.load_text(S.STORAGE_PAYLOAD_PREFIX + digest)
        except PayloadIntegrityError:
            damaged += C.ONE
        else:
            verified.add(digest)
    checked[S.DBSAFE_CHECKED_PAYLOADS] = len(digests)
    if damaged:
        failures.append(S.DBSAFE_FAILURE_PAYLOAD_DAMAGED)
    dangling = sum(
        int(
            connection.execute(
                S.DBSAFE_DANGLING_PAYLOADS.format(table=table, column=column)
            ).fetchone()[C.ZERO]
        )
        for table, column in C.DBSAFE_PAYLOAD_COLUMNS
    ) + _damaged_collections(connection, payloads, verified)
    checked[S.DBSAFE_CHECKED_DANGLING] = dangling
    if dangling:
        failures.append(S.DBSAFE_FAILURE_PAYLOAD_DANGLING)
    return failures


def _raw_documents(connection: sqlite3.Connection, checked: dict[str, int]) -> list[str]:
    from bookystats.persistence.raw import verify_documents

    total, damaged = verify_documents(connection)
    checked[S.DBSAFE_CHECKED_DOCUMENTS] = total
    return [S.DBSAFE_FAILURE_DOCUMENT_DAMAGED] if damaged else []


def _metadata_rows(connection: sqlite3.Connection, checked: dict[str, int]) -> list[str]:
    from bookystats.persistence.cache import verify_rows

    total, damaged = verify_rows(connection)
    checked[S.DBSAFE_CHECKED_ROWS] = total
    return [S.DBSAFE_FAILURE_ROW_DAMAGED] if damaged else []


def verify_connection(
    connection: sqlite3.Connection, kind: C.StoreKind, *, comprehensive: bool = C.FALSE
) -> IntegrityReport:
    failures: list[str] = []
    checked: dict[str, int] = {}
    try:
        rows = [tuple(row) for row in connection.execute(S.DBSAFE_PRAGMA_INTEGRITY_CHECK)]
        if rows != [(S.OK,)]:
            failures.append(S.DBSAFE_FAILURE_INTEGRITY)
        violations = connection.execute(S.DBSAFE_PRAGMA_FOREIGN_KEY_CHECK).fetchall()
        checked[S.DBSAFE_CHECKED_FOREIGN_KEYS] = len(violations)
        if violations:
            failures.append(S.DBSAFE_FAILURE_FOREIGN_KEY)
        if comprehensive and S.DBSAFE_FAILURE_INTEGRITY not in failures:
            if kind is C.StoreKind.LIBRARY:
                failures.extend(_library_payloads(connection, checked))
            elif kind is C.StoreKind.RAW:
                failures.extend(_raw_documents(connection, checked))
            elif kind is C.StoreKind.METADATA:
                failures.extend(_metadata_rows(connection, checked))
    except sqlite3.Error:
        failures.append(S.DBSAFE_FAILURE_UNREADABLE)
    return IntegrityReport(kind, comprehensive, checked, tuple(failures))


def _analytics_history(path: Path) -> IntegrityReport:
    from bookystats.persistence.analytics import AnalyticsStore, AnalyticsStoreError
    from bookystats.persistence.recommendations import RecommendationStore, RecommendationStoreError

    checked: dict[str, int] = {}
    failures: list[str] = []
    try:
        with AnalyticsStore(path, require_existing=C.TRUE, read_only=C.TRUE) as analytics:
            checked.update(analytics.verify_history())
        with RecommendationStore(path, read_only=C.TRUE) as recommendations:
            checked.update(recommendations.verify_history())
    except (AnalyticsStoreError, RecommendationStoreError):
        failures.append(S.DBSAFE_FAILURE_HISTORY_DAMAGED)
    return IntegrityReport(C.StoreKind.ANALYTICS, C.TRUE, checked, tuple(failures))


def verify_store(path: Path, kind: C.StoreKind, *, comprehensive: bool = C.TRUE) -> IntegrityReport:
    try:
        report = read_consistent(
            path,
            lambda handle: verify_connection(handle.connection, kind, comprehensive=comprehensive),
        )
    except StoreStateError as error:
        return IntegrityReport(kind, comprehensive, {}, (error.state.value,))
    if comprehensive and kind is C.StoreKind.ANALYTICS and report.ok:
        history = _analytics_history(path)
        return IntegrityReport(
            kind,
            C.TRUE,
            {**report.checked, **history.checked},
            (*report.failures, *history.failures),
        )
    return report
