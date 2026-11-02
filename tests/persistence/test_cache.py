from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

import pytest
from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.interfaces import HttpRetryState
from bookystats.domain.models import Source
from bookystats.persistence.cache import MetadataCache, MetadataCacheError


def test_persistent_cache_is_provider_isolated_and_returns_detached_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        S.BOOKYSTATS_CACHE_UTC_TIMESTAMP,
        lambda: C.TEST_CACHE_PERSISTENT_CACHE_IS_ISOLATED_AND_RETURNS_DETACHED_DATA,
    )
    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    cache.put(
        Source.GOOGLE_BOOKS,
        S.TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN,
        {S.TITLE: S.MATILDA},
        ttl_seconds=C.TEST_CACHE_PERSISTENT_CACHE_IS_RETURNS_DETACHED_DATA_TTL_SECONDS,
    )
    cache.put(
        Source.OPEN_LIBRARY,
        S.TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN,
        {S.TITLE: S.OTHER_2},
        ttl_seconds=C.TEST_CACHE_PERSISTENT_CACHE_IS_RETURNS_DETACHED_DATA_TTL_SECONDS,
    )
    value = cache.get(
        Source.GOOGLE_BOOKS, S.TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN
    )
    assert value == {S.TITLE: S.MATILDA}
    value[S.TITLE] = S.TEST_CACHE_PERSISTENT_CACHE_IS_RETURNS_DETACHED_DATA_CHANGED_LOCALLY
    cache.close()
    reopened = MetadataCache(path)
    assert reopened.get(
        Source.GOOGLE_BOOKS, S.TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN
    ) == {S.TITLE: S.MATILDA}
    assert reopened.get(
        Source.OPEN_LIBRARY, S.TEST_CACHE_PERSISTENT_CACHE_IS_AND_RETURNS_DETACHED_DATA_ISBN
    ) == {S.TITLE: S.OTHER_2}
    assert reopened.get(Source.OPEN_LIBRARY, S.ABSENT) is C.NONE
    reopened.close()


def test_expiration_is_utc_timestamp_based_and_excludes_expiry_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [C.TEST_CACHE_EXPIRATION_IS_UTC_AND_EXCLUDES_EXPIRY_BOUNDARY_NOW]
    monkeypatch.setattr(S.BOOKYSTATS_CACHE_UTC_TIMESTAMP, lambda: now[C.ZERO])
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    cache.put(
        Source.GOOGLE_BOOKS,
        S.IDENTITY,
        {S.CANDIDATES: []},
        ttl_seconds=C.TEST_CACHE_EXPIRATION_IS_UTC_EXCLUDES_EXPIRY_BOUNDARY_TTL_SECONDS,
    )
    now[C.ZERO] += C.TEST_CACHE_EXPIRATION_IS_UTC_BASED_AND_EXCLUDES_EXPIRY_BOUNDARY
    assert cache.get(Source.GOOGLE_BOOKS, S.IDENTITY) == {S.CANDIDATES: []}
    now[C.ZERO] += C.ONE
    assert cache.get(Source.GOOGLE_BOOKS, S.IDENTITY) is C.NONE
    cache.put(Source.GOOGLE_BOOKS, S.IDENTITY, {S.FRESH: C.TRUE}, ttl_seconds=C.ZERO)
    assert cache.get(Source.GOOGLE_BOOKS, S.IDENTITY) is C.NONE
    cache.close()


def test_corrupt_database_and_corrupt_entry_are_explicit_errors(tmp_path: Path) -> None:
    path = tmp_path / S.CATALOG_SQLITE
    path.write_bytes(S.TEST_CACHE_CORRUPT_DATABASE_AND_ENTRY_ARE_EXPLICIT_ERRORS_BYTES)
    with pytest.raises(MetadataCacheError) as error:
        MetadataCache(path)
    assert S.DO_NOT_LEAK not in str(error.value)
    path.unlink()
    cache = MetadataCache(path)
    cache.put(Source.OPEN_LIBRARY, S.IDENTITY, {S.CANDIDATES: []}, ttl_seconds=C.ZERO)
    with sqlite3.connect(path) as database:
        database.execute(
            S.TEST_CACHE_CORRUPT_DATABASE_AND_UPDATE_METADATA_CACHE_SET_PAYLOAD,
            (S.TEST_CACHE_CORRUPT_DATABASE_AND_CORRUPT_ERRORS_BROKEN_DO_NOT_LEAK,),
        )
    with pytest.raises(MetadataCacheError) as error:
        cache.get(Source.OPEN_LIBRARY, S.IDENTITY)
    assert S.DO_NOT_LEAK not in str(error.value)
    cache.close()


@pytest.mark.parametrize(
    S.INVALID,
    [
        float(S.NAN),
        float(S.INF),
        float(S.TEST_CACHE_INVALID_JSON_DOES_NOT_REPLACE_A_GOOD_ENTRY_INF),
        object(),
        {C.ONE: S.X_2},
    ],
)
def test_invalid_json_does_not_replace_a_good_entry(tmp_path: Path, invalid: object) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    cache.put(
        Source.OPEN_LIBRARY,
        S.IDENTITY,
        {S.VALID: C.TRUE},
        ttl_seconds=C.TEST_CACHE_INVALID_JSON_DOES_NOT_REPLACE_A_GOOD_ENTRY_TTL_SECONDS,
    )
    with pytest.raises(MetadataCacheError):
        cache.put(
            Source.OPEN_LIBRARY,
            S.IDENTITY,
            {S.INVALID: cast(JsonValue, invalid)},
            ttl_seconds=C.TEST_CACHE_INVALID_JSON_DOES_NOT_REPLACE_A_GOOD_ENTRY_TTL_SECONDS,
        )
    assert cache.get(Source.OPEN_LIBRARY, S.IDENTITY) == {S.VALID: C.TRUE}
    cache.close()


def test_expiry_tampering_is_not_silently_trusted(tmp_path: Path) -> None:
    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    cache.put(
        Source.OPEN_LIBRARY,
        S.IDENTITY,
        {S.VALID: C.TRUE},
        ttl_seconds=C.TEST_CACHE_EXPIRY_TAMPERING_IS_NOT_SILENTLY_TRUSTED_TTL_SECONDS,
    )
    with sqlite3.connect(path) as database:
        database.execute(S.TEST_CACHE_EXPIRY_TAMPERING_IS_NOT_CACHE_SET_EXPIRES_AT_EXPIRES)
    with pytest.raises(MetadataCacheError):
        cache.get(Source.OPEN_LIBRARY, S.IDENTITY)
    cache.close()


def test_closed_cache_and_invalid_ttl_fail_explicitly(tmp_path: Path) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    with pytest.raises(MetadataCacheError):
        cache.put(Source.OPEN_LIBRARY, S.IDENTITY, {}, ttl_seconds=-C.ONE)
    cache.close()
    cache.close()
    with pytest.raises(MetadataCacheError):
        cache.get(Source.OPEN_LIBRARY, S.IDENTITY)


def test_non_ascii_checksum_damage_is_an_operational_error(tmp_path: Path) -> None:
    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    cache.put(
        Source.OPEN_LIBRARY,
        S.IDENTITY,
        {S.VALID: C.TRUE},
        ttl_seconds=C.TEST_CACHE_NON_ASCII_CHECKSUM_AN_OPERATIONAL_ERROR_TTL_SECONDS,
    )
    with sqlite3.connect(path) as database:
        database.execute(
            S.TEST_CACHE_NON_ASCII_CHECKSUM_UPDATE_METADATA_CACHE_SET_CHECKSUM,
            (S.TEST_CACHE_NON_ASCII_CHECKSUM_DAMAGE_IS_AN_OPERATIONAL_ERROR_TEXT,),
        )
    with pytest.raises(MetadataCacheError):
        cache.get(Source.OPEN_LIBRARY, S.IDENTITY)
    cache.close()


def test_retry_state_adds_to_existing_cache_and_checks_deadline_integrity(tmp_path: Path) -> None:
    path = tmp_path / S.CATALOG_SQLITE
    with sqlite3.connect(path) as connection:
        connection.execute(S.CACHE_METADATACACHE_INIT_CREATE_TABLE_IF_NOT_EXISTS_METADATA_CACHE)
    cache = MetadataCache(path)
    try:
        assert cache.get_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID) is C.NONE
        cache.put(Source.OPEN_LIBRARY, S.IDENTITY, {S.VALID: C.TRUE}, ttl_seconds=C.TEN)
        cache.save_retry_state(
            Source.OPEN_LIBRARY,
            S.SOURCE_INVALID,
            HttpRetryState(retry_at=float(S.DR_TEST_RETRY_SECONDS)),
        )
        with sqlite3.connect(path) as connection:
            connection.execute(S.DR_TEST_TAMPER_RETRY)
        with pytest.raises(MetadataCacheError, match=S.DR_RETRY_READ_ERROR):
            cache.get_retry_state(Source.OPEN_LIBRARY, S.SOURCE_INVALID)
        assert cache.get(Source.OPEN_LIBRARY, S.IDENTITY) == {S.VALID: C.TRUE}
    finally:
        cache.close()
