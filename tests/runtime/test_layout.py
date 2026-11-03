from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import AlreadyRunning
from bookystats.runtime.layout import DataLayoutError, database_path, google_credentials_path
from bookystats.runtime.locking import SyncLock, _lock_file


def _seed(path: Path) -> None:
    path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(S.LAYOUT_TEST_CREATE)
        connection.execute(S.LAYOUT_TEST_INSERT, (C.ONE,))
        connection.commit()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_legacy_migration_preserves_all_files_and_is_idempotent(tmp_path: Path) -> None:
    for filename in C.CLI_LOCAL_DATABASES:
        _seed(tmp_path / filename)
    (tmp_path / S.OAUTH_FILE).write_bytes(S.LAYOUT_TEST_CREDENTIALS)
    (tmp_path / S.CONFIG_JSON).write_bytes(S.LAYOUT_TEST_CREDENTIALS)
    (tmp_path / S.SYNC_LOCK).write_bytes(S.LOCKING_SYNCLOCK_ENTER_BYTES)
    hashes = {name: _hash(tmp_path / name) for name in C.LAYOUT_MOVED_FILES}
    for filename in C.CLI_LOCAL_DATABASES:
        assert database_path(tmp_path, filename) == tmp_path / filename
    lock = SyncLock(tmp_path)
    with lock:
        assert set(lock.migrated_files) == set(C.LAYOUT_MOVED_FILES)
    assert not (tmp_path / S.SYNC_LOCK).exists()
    assert (tmp_path / S.LAYOUT_RUNTIME / S.SYNC_LOCK).is_file()
    for filename in C.CLI_LOCAL_DATABASES:
        path = database_path(tmp_path, filename)
        assert path.parent.name == S.LAYOUT_DATABASES
        assert _hash(path) == hashes[filename]
        assert not (tmp_path / filename).exists()
        with closing(sqlite3.connect(path)) as connection:
            assert connection.execute(S.LAYOUT_TEST_SELECT).fetchall() == [(C.ONE,)]
    assert _hash(google_credentials_path(tmp_path)) == hashes[S.OAUTH_FILE]
    assert google_credentials_path(tmp_path).parent.name == S.LAYOUT_CREDENTIALS
    assert (tmp_path / S.CONFIG_JSON).read_bytes() == S.LAYOUT_TEST_CREDENTIALS
    with lock:
        assert not lock.migrated_files


def test_conflicting_locations_fail_before_any_move(tmp_path: Path) -> None:
    _seed(tmp_path / S.CLI_RAW_DATABASE)
    _seed(tmp_path / S.LIBRARY_SQLITE3)
    destination = tmp_path / S.LAYOUT_DATABASES / S.LIBRARY_SQLITE3
    _seed(destination)
    original = _hash(tmp_path / S.CLI_RAW_DATABASE)
    with pytest.raises(DataLayoutError), SyncLock(tmp_path):
        pytest.fail(S.TEST)
    assert _hash(tmp_path / S.CLI_RAW_DATABASE) == original
    assert not (tmp_path / S.LAYOUT_DATABASES / S.CLI_RAW_DATABASE).exists()
    assert destination.is_file()
    assert (tmp_path / S.LIBRARY_SQLITE3).is_file()


def test_active_legacy_sync_prevents_migration(tmp_path: Path) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    _seed(path)
    legacy = tmp_path / S.SYNC_LOCK
    legacy.write_bytes(S.LOCKING_SYNCLOCK_ENTER_BYTES)
    with legacy.open(S.SYNCLOCK_ENTER_HANDLE_A_B) as handle:
        handle.seek(C.ZERO)
        _lock_file(handle.fileno())
        try:
            with pytest.raises(AlreadyRunning), SyncLock(tmp_path):
                pytest.fail(S.TEST)
            assert path.is_file()
            assert not (tmp_path / S.LAYOUT_DATABASES / path.name).exists()
        finally:
            handle.seek(C.ZERO)
            _lock_file(handle.fileno(), release=C.TRUE)
    with SyncLock(tmp_path):
        assert database_path(tmp_path, path.name).parent.name == S.LAYOUT_DATABASES


def test_active_wal_reader_prevents_loss_and_recovery_retains_commits(tmp_path: Path) -> None:
    path = tmp_path / S.LIBRARY_SQLITE3
    writer = sqlite3.connect(path)
    reader: sqlite3.Connection | None = C.NONE
    try:
        writer.execute(S.LAYOUT_TEST_WAL)
        writer.execute(S.LAYOUT_TEST_NO_CHECKPOINT)
        writer.execute(S.LAYOUT_TEST_CREATE)
        writer.execute(S.LAYOUT_TEST_INSERT, (C.ONE,))
        writer.commit()
        reader = sqlite3.connect(path)
        reader.execute(S.LAYOUT_TEST_BEGIN_READ)
        reader.execute(S.LAYOUT_TEST_SELECT).fetchall()
        writer.execute(S.LAYOUT_TEST_INSERT, (C.TWO,))
        writer.commit()
        with pytest.raises(DataLayoutError), SyncLock(tmp_path):
            pytest.fail(S.TEST)
        assert path.is_file()
        assert not (tmp_path / S.LAYOUT_DATABASES / path.name).exists()
    finally:
        if reader is not C.NONE:
            reader.close()
        writer.close()
    with (
        SyncLock(tmp_path),
        closing(sqlite3.connect(database_path(tmp_path, path.name))) as connection,
    ):
        assert connection.execute(S.LAYOUT_TEST_SELECT).fetchall() == [(C.ONE,), (C.TWO,)]


def test_partial_file_move_resumes_without_overwriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (S.CLI_RAW_DATABASE, S.LIBRARY_SQLITE3):
        _seed(tmp_path / name)
    rename = Path.rename

    def interrupt(source: Path, target: Path) -> Path:
        if source.name == S.LIBRARY_SQLITE3:
            raise OSError(S.LAYOUT_TEST_FAILURE)
        return rename(source, target)

    monkeypatch.setattr(Path, S.LAYOUT_TEST_RENAME, interrupt)
    with pytest.raises(OSError, match=S.LAYOUT_TEST_FAILURE), SyncLock(tmp_path):
        pytest.fail(S.TEST)
    assert database_path(tmp_path, S.CLI_RAW_DATABASE).parent.name == S.LAYOUT_DATABASES
    assert database_path(tmp_path, S.LIBRARY_SQLITE3).parent == tmp_path
    monkeypatch.setattr(Path, S.LAYOUT_TEST_RENAME, rename)
    with SyncLock(tmp_path) as lock:
        assert lock.migrated_files == (S.LIBRARY_SQLITE3,)
    assert database_path(tmp_path, S.LIBRARY_SQLITE3).parent.name == S.LAYOUT_DATABASES


def test_resolving_new_locations_does_not_create_runtime_files(tmp_path: Path) -> None:
    assert database_path(tmp_path, S.AN_DATABASE) == (tmp_path / S.LAYOUT_DATABASES / S.AN_DATABASE)
    assert google_credentials_path(tmp_path) == (tmp_path / S.LAYOUT_CREDENTIALS / S.OAUTH_FILE)
    assert not tuple(tmp_path.iterdir())
    with pytest.raises(DataLayoutError):
        database_path(tmp_path, S.CONFIG_JSON)
