from __future__ import annotations

import hashlib
import hmac
import json
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import BookyError
from bookystats.models import Source


class MetadataCacheError(BookyError):
    pass


def _utc_timestamp() -> float:
    return datetime.now(UTC).timestamp()


def _is_json(value: object) -> bool:
    if value is C.NONE or type(value) in (str, bool, int):
        return C.TRUE
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json(item) for item in value)
    if isinstance(value, dict):
        return all((isinstance(key, str) and _is_json(item) for key, item in value.items()))
    return C.FALSE


def _checksum(payload: str, expires_at: float) -> str:
    return hashlib.sha256(
        S.CACHE_CHECKSUM_TEMPLATE.format(v0=expires_at, v1=payload).encode()
    ).hexdigest()


class MetadataCache:
    def __init__(self, path: Path) -> None:
        self._connection: sqlite3.Connection | None = C.NONE
        try:
            path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
            connection = sqlite3.connect(path, timeout=C.FIVE)
            self._connection = connection
            if connection.execute(S.CACHE_METADATACACHE_INIT_PRAGMA_QUICK_CHECK).fetchall() != [
                (S.OK,)
            ]:
                raise MetadataCacheError(
                    S.CACHE_METADATACACHE_INIT_METADATA_CACHE_IS_CORRUPT_REPAIR_OR_REMOVE
                )
            with connection:
                connection.execute(
                    S.CACHE_METADATACACHE_INIT_CREATE_TABLE_IF_NOT_EXISTS_METADATA_CACHE
                )
        except (OSError, sqlite3.Error, MetadataCacheError):
            self.close()
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_INIT_METADATA_CACHE_COULD_NOT_BE_OPENED_SAFELY
            ) from C.NONE

    def _db(self) -> sqlite3.Connection:
        if self._connection is C.NONE:
            raise MetadataCacheError(S.CACHE_METADATACACHE_DB_METADATA_CACHE_IS_CLOSED)
        return self._connection

    @staticmethod
    def _key(provider: Source, key: str) -> tuple[str, str]:
        if provider not in (Source.GOOGLE_BOOKS, Source.OPEN_LIBRARY):
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_KEY_ONLY_PUBLIC_METADATA_PROVIDERS_MAY_USE_THIS
            )
        if not isinstance(key, str) or not key:
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_KEY_A_PUBLIC_CATALOG_CACHE_KEY_IS_REQUIRED
            )
        try:
            digest = hashlib.sha256(key.encode()).hexdigest()
        except UnicodeError:
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_KEY_METADATA_CACHE_KEY_IS_NOT_VALID_UNICODE
            ) from C.NONE
        return (provider.value, digest)

    def get(self, provider: Source, key: str) -> dict[str, JsonValue] | None:
        try:
            row: tuple[object, object, object] | None = (
                self._db()
                .execute(
                    S.METADATACACHE_GET_ROW_SELECT_PAYLOAD_AT_CHECKSUM_FROM_METADATA,
                    self._key(provider, key),
                )
                .fetchone()
            )
        except sqlite3.Error:
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_GET_METADATA_CACHE_COULD_NOT_BE_READ_SAFELY
            ) from C.NONE
        if row is C.NONE:
            return C.NONE
        payload, expires_at, checksum = row
        if (
            not isinstance(payload, str)
            or not isinstance(expires_at, (int, float))
            or isinstance(expires_at, bool)
            or (not math.isfinite(expires_at))
            or (not isinstance(checksum, str))
            or (not checksum.isascii())
            or (not hmac.compare_digest(_checksum(payload, expires_at), checksum))
        ):
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_GET_METADATA_CACHE_CONTAINS_A_DAMAGED_ENTRY
            )
        try:
            decoded = json.loads(payload)
        except (ValueError, RecursionError):
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_GET_METADATA_CACHE_CONTAINS_INVALID_JSON
            ) from C.NONE
        if not isinstance(decoded, dict) or not _is_json(decoded):
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_GET_METADATA_CACHE_CONTAINS_INVALID_CATALOG_DATA
            )
        if expires_at <= _utc_timestamp():
            return C.NONE
        return cast(dict[str, JsonValue], decoded)

    def put(
        self, provider: Source, key: str, payload: dict[str, JsonValue], *, ttl_seconds: int
    ) -> None:
        identity = self._key(provider, key)
        if type(ttl_seconds) is not int or ttl_seconds < C.ZERO:
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_PUT_METADATA_CACHE_TTL_MUST_BE_A_NONNEGATIVE
            )
        try:
            expires_at = _utc_timestamp() + ttl_seconds
            valid = isinstance(payload, dict) and _is_json(payload) and math.isfinite(expires_at)
            if not valid:
                raise ValueError
            encoded = json.dumps(
                payload,
                ensure_ascii=C.TRUE,
                sort_keys=C.TRUE,
                separators=(S.COMMA, S.COLON),
                allow_nan=C.FALSE,
            )
        except (ValueError, TypeError, OverflowError, RecursionError):
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_PUT_METADATA_CACHE_ONLY_FINITE_JSON_CATALOG
            ) from C.NONE
        try:
            with self._db() as connection:
                connection.execute(
                    S.CACHE_METADATACACHE_PUT_INSERT_INTO_CACHE_PROVIDER_CACHE_KEY,
                    (*identity, encoded, expires_at, _checksum(encoded, expires_at)),
                )
        except sqlite3.Error:
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_PUT_METADATA_CACHE_COULD_NOT_BE_WRITTEN_SAFELY
            ) from C.NONE

    def close(self) -> None:
        if self._connection is not C.NONE:
            connection, self._connection = (self._connection, C.NONE)
            try:
                connection.close()
            except sqlite3.Error:
                raise MetadataCacheError(
                    S.CACHE_METADATACACHE_CLOSE_METADATA_CACHE_COULD_NOT_BE_CLOSED_SAFELY
                ) from C.NONE
