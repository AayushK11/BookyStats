from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path

import pytest
from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.cli.storage_status import latest_analytics, library_status
from bookystats.domain.interfaces import HttpRetryState
from bookystats.domain.models import BookRecord, Source
from bookystats.persistence import backup as backup_module
from bookystats.persistence.analytics import AnalyticsStore, AnalyticsStoreError
from bookystats.persistence.backup import (
    BackupError,
    BackupResult,
    StoreMigrationBlocked,
    create_backup,
    file_sha256,
    restore_backup,
    verify_backup,
)
from bookystats.persistence.cache import MetadataCache, MetadataCacheError
from bookystats.persistence.inspection import (
    ReadOnlyConnection,
    StoreChangedDuringRead,
    has_sidecars,
    inspect_store,
    read_consistent,
)
from bookystats.persistence.integrity import IntegrityReport, verify_store
from bookystats.persistence.library import Database
from bookystats.persistence.raw import RawStore
from tests.persistence.test_analytics import _report, _tamper
from tests.persistence.test_library import (
    _restore_legacy_layout,
    book,
    library,
    publish,
    snapshot,
)
from tests.persistence.test_raw import _capture


def fingerprint(path: Path) -> tuple[str, tuple[str, ...]]:
    return file_sha256(path), tuple(sorted(item.name for item in path.parent.iterdir()))


def _backups(root: Path) -> list[Path]:
    folder = root / S.DBSAFE_BACKUPS_DIRECTORY
    return sorted(folder.iterdir()) if folder.is_dir() else []


def _counts(status: Mapping[str, JsonValue] | None) -> dict[str, int]:
    assert status is not C.NONE
    section = status[S.LIBRARY]
    assert isinstance(section, dict)
    return {key: value for key, value in section.items() if isinstance(value, int)}


def _index_names(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return [str(row[C.ZERO]) for row in connection.execute(S.DBSAFE_TEST_SELECT_INDEXES)]


def _table_rows(path: Path) -> dict[str, list[tuple[object, ...]]]:
    with closing(sqlite3.connect(path)) as connection:
        names = [str(row[C.ZERO]) for row in connection.execute(S.DBSAFE_SELECT_TABLES)]
        return {
            name: sorted(
                (
                    tuple(row)
                    for row in connection.execute(S.DBSAFE_TEST_SELECT_ROWS.format(table=name))
                ),
                key=repr,
            )
            for name in names
        }


def _flip_last_byte(path: Path) -> None:
    content = bytearray(path.read_bytes())
    content[-C.ONE] ^= C.DBSAFE_TEST_FLIP_MASK
    path.write_bytes(bytes(content))


def _prior_library(path: Path, version: int) -> tuple[dict[str, int], tuple[BookRecord, ...]]:
    with closing(Database(path)) as db:
        publish(db, snapshot(book()))
        expected = (library(db), db.active_records())
        if version == C.STORAGE_LEGACY_VERSION:
            _restore_legacy_layout(db)
    if version == C.DBSAFE_LIBRARY_PRIOR_VERSION:
        for name in C.DBSAFE_TEST_INDEX_NAMES:
            _tamper(path, S.DBSAFE_TEST_DROP_INDEX.format(name=name))
        _tamper(path, S.DBSAFE_TEST_VERSION_THREE)
    return expected


def test_status_leaves_a_wal_library_at_rest_byte_identical_without_sidecars(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    with closing(Database(path)) as db:
        publish(db, snapshot(book()))
        counts = library(db)
    assert not has_sidecars(path)
    before = fingerprint(path)
    assert _counts(library_status(path)) == counts
    assert inspect_store(path, C.StoreKind.LIBRARY).state is C.StoreState.CURRENT
    assert verify_store(path, C.StoreKind.LIBRARY).ok
    assert fingerprint(path) == before
    assert not has_sidecars(path)


def test_status_reads_committed_wal_data_while_a_writer_holds_the_write_lock(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    with closing(Database(path)) as writer:
        publish(writer, snapshot(book()))
        assert has_sidecars(path)
        writer._connection().execute(S.STORAGE_DATABASE_INITIALIZE_BEGIN_IMMEDIATE)
        try:
            seen = _counts(library_status(path))
        finally:
            writer._connection().execute(S.ROLLBACK)
        assert seen == library(writer)
        assert any(seen.values())


def test_status_reads_a_rollback_journal_store_while_a_writer_transaction_is_open(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    with AnalyticsStore(path) as store:
        saved = store.publish(_report())
    writer = sqlite3.connect(path, isolation_level=C.NONE)
    try:
        writer.execute(S.STORAGE_DATABASE_INITIALIZE_BEGIN_IMMEDIATE)
        assert latest_analytics(path) == saved
        assert inspect_store(path, C.StoreKind.ANALYTICS).state is C.StoreState.CURRENT
    finally:
        writer.close()


def test_absent_and_foreign_files_are_classified_without_being_created_or_changed(
    tmp_path: Path,
) -> None:
    missing = tmp_path / S.DBSAFE_TEST_RESTORED / S.LIBRARY_SQLITE3
    assert inspect_store(missing, C.StoreKind.LIBRARY).state is C.StoreState.ABSENT
    assert library_status(missing) is C.NONE
    assert not missing.parent.exists()
    foreign = tmp_path / S.LIBRARY_SQLITE3
    foreign.write_bytes(S.DBSAFE_TEST_FOREIGN_BYTES)
    before = fingerprint(foreign)
    assert inspect_store(foreign, C.StoreKind.LIBRARY).state is C.StoreState.UNRECOGNIZED
    assert library_status(foreign) is C.NONE
    assert fingerprint(foreign) == before


def test_legacy_v1_library_is_unavailable_to_status_and_never_migrated_by_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    _prior_library(path, C.STORAGE_LEGACY_VERSION)
    before = fingerprint(path)
    inspection = inspect_store(path, C.StoreKind.LIBRARY)
    assert inspection.state is C.StoreState.UPGRADE_NEEDED
    assert inspection.version == C.STORAGE_LEGACY_VERSION
    assert inspection.readable is C.FALSE
    assert library_status(path) is C.NONE
    assert fingerprint(path) == before
    assert not has_sidecars(path)


def test_prior_v3_library_is_readable_in_place_and_upgrades_by_adding_indexes_only(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    counts, _records = _prior_library(path, C.DBSAFE_LIBRARY_PRIOR_VERSION)
    rows = _table_rows(path)
    before = fingerprint(path)
    inspection = inspect_store(path, C.StoreKind.LIBRARY)
    assert (inspection.state, inspection.readable) == (C.StoreState.UPGRADE_NEEDED, C.TRUE)
    assert _counts(library_status(path)) == counts
    assert fingerprint(path) == before
    with closing(Database(path)) as db:
        db.initialize()
    assert _table_rows(path) == rows
    assert set(C.DBSAFE_TEST_INDEX_NAMES) <= set(_index_names(path))


@pytest.mark.parametrize(S.DBSAFE_TEST_PARAM_VERSION, C.DBSAFE_TEST_PRIOR_LAYOUTS)
def test_library_upgrade_makes_a_verified_backup_and_preserves_every_record(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    counts, records = _prior_library(path, version)
    before = fingerprint(path)
    assert inspect_store(path, C.StoreKind.LIBRARY).state is C.StoreState.UPGRADE_NEEDED
    assert fingerprint(path) == before
    with closing(Database(path)) as db:
        assert library(db) == counts
        assert db.active_records() == records
    (backup,) = _backups(tmp_path)
    saved = verify_backup(backup)
    assert (saved.kind, saved.reason) == (C.StoreKind.LIBRARY, S.DBSAFE_REASON_MIGRATION)
    assert saved.record.user_version == version
    assert inspect_store(path, C.StoreKind.LIBRARY).state is C.StoreState.CURRENT
    fresh = tmp_path / S.DBSAFE_TEST_FRESH / S.LIBRARY_SQLITE3
    with closing(Database(fresh)) as db:
        db.initialize()
    assert _index_names(path) == _index_names(fresh)


def _assert_migration_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, replacement: object
) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    _prior_library(path, C.DBSAFE_LIBRARY_PRIOR_VERSION)
    before = fingerprint(path)
    monkeypatch.setattr(backup_module, name, replacement)
    with closing(Database(path)) as db, pytest.raises(StoreMigrationBlocked):
        db.initialize()
    assert fingerprint(path) == before
    assert not has_sidecars(path)


def test_migration_is_refused_and_nothing_changes_when_the_backup_cannot_be_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> BackupResult:
        raise BackupError(S.DBSAFE_TEST_BACKUP_FAILED)

    _assert_migration_refused(tmp_path, monkeypatch, S.DBSAFE_TEST_CREATE_BACKUP, fail)


def test_migration_is_refused_and_nothing_changes_when_the_integrity_gate_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(
        connection: sqlite3.Connection, kind: C.StoreKind, *, comprehensive: bool = C.FALSE
    ) -> IntegrityReport:
        return IntegrityReport(kind, comprehensive, {}, (S.DBSAFE_FAILURE_INTEGRITY,))

    _assert_migration_refused(tmp_path, monkeypatch, S.DBSAFE_TEST_VERIFY_CONNECTION, failing)
    assert _backups(tmp_path) == []


def test_backup_of_a_live_wal_library_is_verified_restorable_and_not_wal(tmp_path: Path) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    with closing(Database(path)) as db:
        publish(db, snapshot(book()))
        assert has_sidecars(path)
        result = db.verified_backup()
        counts = library(db)
    assert result.directory.parent == tmp_path / S.DBSAFE_BACKUPS_DIRECTORY
    assert (result.kind, result.reason) == (C.StoreKind.LIBRARY, S.DBSAFE_REASON_MAINTENANCE)
    assert verify_backup(result.directory).record == result.record
    assert result.path.read_bytes()[C.DBSAFE_HEADER_FORMAT_OFFSET] != C.DBSAFE_WAL_FORMAT
    restored = restore_backup(
        result.directory, tmp_path / S.DBSAFE_TEST_RESTORED / S.LIBRARY_SQLITE3
    )
    assert file_sha256(restored) == result.record.sha256
    assert _counts(library_status(restored)) == counts
    with pytest.raises(BackupError):
        restore_backup(result.directory, restored)


def test_backup_verification_rejects_tampering_and_unsafe_names(tmp_path: Path) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    with closing(Database(path)) as db:
        publish(db, snapshot(book()))
        result = db.verified_backup()
        with pytest.raises(BackupError):
            create_backup(
                db._connection(),
                path,
                C.StoreKind.LIBRARY,
                reason=S.DBSAFE_TEST_INVALID_REASON,
            )
    assert _backups(tmp_path) == [result.directory]
    _flip_last_byte(result.path)
    with pytest.raises(BackupError):
        verify_backup(result.directory)
    target = tmp_path / S.DBSAFE_TEST_RESTORED
    with pytest.raises(BackupError):
        restore_backup(result.directory, target)
    assert not target.exists()


@pytest.mark.parametrize(S.DBSAFE_TEST_PARAM_DAMAGE, C.DBSAFE_TEST_PAYLOAD_DAMAGE)
def test_comprehensive_verify_finds_damaged_or_missing_library_payloads(
    tmp_path: Path, statement: str, failure: str
) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    with closing(Database(path)) as db:
        publish(db, snapshot(book()))
    sound = verify_store(path, C.StoreKind.LIBRARY)
    assert sound.ok
    assert sound.checked[S.DBSAFE_CHECKED_PAYLOADS] > C.ZERO
    _tamper(path, statement)
    assert failure in verify_store(path, C.StoreKind.LIBRARY).failures
    assert verify_store(path, C.StoreKind.LIBRARY, comprehensive=C.FALSE).ok


def test_comprehensive_verify_finds_damaged_cache_rows_and_retry_gates(tmp_path: Path) -> None:
    path = tmp_path / S.METADATA_SQLITE3
    with closing(MetadataCache(path)) as cache:
        cache.put(
            Source.OPEN_LIBRARY,
            S.IDENTITY,
            {S.VALID: C.TRUE},
            ttl_seconds=C.DBSAFE_TEST_TTL_SECONDS,
        )
        cache.save_retry_state(
            Source.OPEN_LIBRARY,
            S.SOURCE_INVALID,
            HttpRetryState(retry_at=float(S.DR_TEST_RETRY_SECONDS)),
        )
    sound = verify_store(path, C.StoreKind.METADATA)
    assert sound.ok
    assert sound.checked[S.DBSAFE_CHECKED_ROWS] == C.TWO
    _tamper(path, S.DR_TEST_TAMPER_RETRY)
    assert verify_store(path, C.StoreKind.METADATA).failures == (S.DBSAFE_FAILURE_ROW_DAMAGED,)
    assert verify_store(path, C.StoreKind.METADATA, comprehensive=C.FALSE).ok


def test_comprehensive_verify_finds_a_damaged_raw_document(tmp_path: Path) -> None:
    path = tmp_path / S.TEST_RAW_FILENAME
    with closing(RawStore(path)) as archive:
        _capture(archive)
    sound = verify_store(path, C.StoreKind.RAW)
    assert sound.ok
    assert sound.checked[S.DBSAFE_CHECKED_DOCUMENTS] == C.ONE
    _tamper(path, S.TEST_RAW_TAMPER_CHECKSUM)
    assert verify_store(path, C.StoreKind.RAW).failures == (S.DBSAFE_FAILURE_DOCUMENT_DAMAGED,)


def test_analytics_open_and_selected_reads_skip_unrelated_history_but_deep_verify_finds_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    report = _report()
    with AnalyticsStore(path) as store:
        store.save_component(report.taste)
        store.save_component(report.watchlist)
    assert verify_store(path, C.StoreKind.ANALYTICS).ok
    _tamper(path, S.DBSAFE_TEST_DAMAGE_COMPONENT, (S.REC_TEST_BAD_HASH, report.watchlist.key))
    with AnalyticsStore(path) as store:
        assert store.get_component(report.taste.key) == report.taste
        with pytest.raises(AnalyticsStoreError):
            store.get_component(report.watchlist.key)
        with pytest.raises(AnalyticsStoreError):
            store.verify_history()
    failures = verify_store(path, C.StoreKind.ANALYTICS).failures
    assert failures == (S.DBSAFE_FAILURE_HISTORY_DAMAGED,)
    assert verify_store(path, C.StoreKind.ANALYTICS, comprehensive=C.FALSE).ok


def test_v2_analytics_is_readable_before_upgrade_and_the_upgrade_is_backed_up(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    with AnalyticsStore(path) as store:
        saved = store.publish(_report())
    for statement in (S.REC_DROP_REPORTS, S.REC_DROP_CACHE, S.REC_LEGACY_VERSION):
        _tamper(path, statement)
    before = fingerprint(path)
    inspection = inspect_store(path, C.StoreKind.ANALYTICS)
    assert (inspection.state, inspection.readable) == (C.StoreState.UPGRADE_NEEDED, C.TRUE)
    assert latest_analytics(path) == saved
    assert fingerprint(path) == before
    with AnalyticsStore(path) as store:
        assert store.latest() == saved
    (backup,) = _backups(tmp_path)
    assert verify_backup(backup).record.user_version == C.AN_STORE_SCHEMA_VERSION
    assert inspect_store(path, C.StoreKind.ANALYTICS).state is C.StoreState.CURRENT


def test_v2_raw_archive_upgrade_is_backed_up_and_documents_survive(tmp_path: Path) -> None:
    path = tmp_path / S.TEST_RAW_FILENAME
    with closing(RawStore(path)) as archive:
        original = _capture(archive)
    _tamper(path, S.DR_TEST_DROP_METADATA)
    _tamper(path, S.RAW_PRAGMA_VERSION_SET.format(value=C.RAW_SCHEMA_VERSION))
    before = fingerprint(path)
    assert inspect_store(path, C.StoreKind.RAW).state is C.StoreState.UPGRADE_NEEDED
    assert fingerprint(path) == before
    with closing(RawStore(path)) as archive:
        assert archive.get(original.id) == original
    (backup,) = _backups(tmp_path)
    assert verify_backup(backup).record.user_version == C.RAW_SCHEMA_VERSION
    assert inspect_store(path, C.StoreKind.RAW).state is C.StoreState.CURRENT


def test_legacy_metadata_file_is_adopted_with_a_backup_keeping_rows_and_retry_gates(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.METADATA_SQLITE3
    retry = HttpRetryState(retry_at=float(S.DR_TEST_RETRY_SECONDS))
    with closing(MetadataCache(path)) as cache:
        cache.put(
            Source.OPEN_LIBRARY,
            S.IDENTITY,
            {S.VALID: C.TRUE},
            ttl_seconds=C.DBSAFE_TEST_TTL_SECONDS,
        )
        cache.save_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID, retry)
    _tamper(path, S.DBSAFE_TEST_RESET_APPLICATION_ID)
    _tamper(path, S.DBSAFE_TEST_RESET_USER_VERSION)
    before = fingerprint(path)
    adoptable = inspect_store(path, C.StoreKind.METADATA)
    assert (adoptable.state, adoptable.readable) == (C.StoreState.UPGRADE_NEEDED, C.TRUE)
    assert fingerprint(path) == before
    with closing(MetadataCache(path)) as cache:
        assert cache.get(Source.OPEN_LIBRARY, S.IDENTITY) == {S.VALID: C.TRUE}
        assert cache.get_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID) == retry
    assert inspect_store(path, C.StoreKind.METADATA).state is C.StoreState.CURRENT
    (backup,) = _backups(tmp_path)
    saved = verify_backup(backup)
    assert saved.kind is C.StoreKind.METADATA
    assert (saved.record.application_id, saved.record.user_version) == (C.ZERO, C.ZERO)
    assert saved.record.tables == {
        S.DBSAFE_TABLE_METADATA_CACHE: C.ONE,
        S.DBSAFE_TABLE_METADATA_RETRY: C.ONE,
    }
    with closing(MetadataCache(path)):
        pass
    assert _backups(tmp_path) == [backup]


@pytest.mark.parametrize(S.DBSAFE_TEST_PARAM_SCENARIO, C.DBSAFE_TEST_REJECTED_METADATA)
def test_metadata_cache_rejects_foreign_newer_or_extended_files_without_changing_them(
    tmp_path: Path, scenario: str
) -> None:
    path = tmp_path / S.METADATA_SQLITE3
    if scenario == S.DBSAFE_TEST_SCENARIO_FOREIGN:
        with closing(Database(path)) as db:
            publish(db, snapshot(book()))
    else:
        with closing(MetadataCache(path)) as cache:
            cache.put(
                Source.OPEN_LIBRARY,
                S.IDENTITY,
                {S.VALID: C.TRUE},
                ttl_seconds=C.DBSAFE_TEST_TTL_SECONDS,
            )
        if scenario == S.DBSAFE_TEST_SCENARIO_NEWER:
            _tamper(path, S.DBSAFE_TEST_VERSION_NEWER)
        else:
            for statement in (
                S.DBSAFE_TEST_RESET_APPLICATION_ID,
                S.DBSAFE_TEST_RESET_USER_VERSION,
                S.DBSAFE_TEST_EXTRA_TABLE,
            ):
                _tamper(path, statement)
    before = fingerprint(path)
    with pytest.raises(MetadataCacheError):
        MetadataCache(path)
    assert fingerprint(path) == before


def test_immutable_read_is_repeated_when_a_writer_appears(tmp_path: Path) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    with closing(Database(path)) as db:
        publish(db, snapshot(book()))
    writers: list[Database] = []
    modes: list[bool] = []

    def work(handle: ReadOnlyConnection) -> int:
        modes.append(handle.immutable)
        if not writers:
            writer = Database(path)
            writer.initialize()
            writers.append(writer)
        return len(modes)

    try:
        assert read_consistent(path, work) == C.TWO
    finally:
        for writer in writers:
            writer.close()
    assert modes == [C.TRUE, C.FALSE]


def test_read_reports_a_busy_state_when_the_file_never_stabilises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    with closing(Database(path)) as db:
        publish(db, snapshot(book()))
    monkeypatch.setattr(ReadOnlyConnection, S.DBSAFE_TEST_STABLE, lambda self: C.FALSE)
    attempts: list[int] = []
    with pytest.raises(StoreChangedDuringRead) as error:
        read_consistent(path, lambda handle: attempts.append(C.ONE))
    assert error.value.state is C.StoreState.BUSY
    assert len(attempts) == C.DBSAFE_READ_ATTEMPTS


@pytest.mark.parametrize(S.DBSAFE_TEST_PARAM_PLAN, C.DBSAFE_TEST_INDEX_PLANS)
def test_new_library_indexes_serve_their_lookups(tmp_path: Path, query: str, index: str) -> None:
    with closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as db:
        plan = db._connection().execute(S.DBSAFE_TEST_EXPLAIN + query, (C.ONE,)).fetchall()
    assert any(index in row[S.DETAIL] for row in plan)
