from __future__ import annotations

import hashlib
import hmac
import json
import math
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import BookyError
from bookystats.domain.interfaces import HttpRetryState
from bookystats.domain.models import Source


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


def _valid_quota(value: object) -> bool:
    if not isinstance(value, Mapping):
        return C.FALSE
    return all(
        isinstance(name, str)
        and name in C.L1_QUOTA_PATTERNS
        and isinstance(item, str)
        and C.L1_QUOTA_PATTERNS[name].fullmatch(item) is not C.NONE
        for name, item in value.items()
    ) and (not value or S.L1_QUOTA_SCOPE in value)


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
                connection.execute(S.DR_RETRY_SCHEMA)
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

    def get(
        self, provider: Source, key: str, *, allow_expired: bool = C.FALSE
    ) -> dict[str, JsonValue] | None:
        return self._get(self._key(provider, key), allow_expired=allow_expired)

    def catalog_entries(self, provider: Source) -> tuple[dict[str, JsonValue], ...]:
        self._key(provider, S.ENR_CATALOG_KEY)
        try:
            keys: list[tuple[str]] = (
                self._db().execute(S.ENR_CATALOG_KEYS, (provider.value,)).fetchall()
            )
        except sqlite3.Error:
            raise MetadataCacheError(
                S.CACHE_METADATACACHE_GET_METADATA_CACHE_COULD_NOT_BE_READ_SAFELY
            ) from C.NONE
        return tuple(
            payload
            for (key,) in keys
            if (payload := self._get((provider.value, key), allow_expired=C.TRUE)) is not C.NONE
        )

    def _get(
        self, identity: tuple[str, str], *, allow_expired: bool
    ) -> dict[str, JsonValue] | None:
        try:
            row: tuple[object, object, object] | None = (
                self._db()
                .execute(
                    S.METADATACACHE_GET_ROW_SELECT_PAYLOAD_AT_CHECKSUM_FROM_METADATA,
                    identity,
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
        if not allow_expired and expires_at <= _utc_timestamp():
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

    def get_retry_state(self, provider: Source, host: str) -> HttpRetryState | None:
        try:
            row: tuple[object, object] | None = (
                self._db().execute(S.DR_RETRY_SELECT, self._key(provider, host)).fetchone()
            )
            if row is C.NONE:
                return C.NONE
            payload, checksum = row
            if (
                not isinstance(payload, str)
                or not isinstance(checksum, str)
                or not checksum.isascii()
                or not hmac.compare_digest(_checksum(payload, C.ZERO), checksum)
            ):
                raise ValueError
            value = json.loads(payload)
            if not isinstance(value, dict) or set(value) not in (
                C.DR_RETRY_KEYS,
                C.L1_RETRY_KEYS_WITH_QUOTA,
            ):
                raise ValueError
            deadline = value[S.DR_RETRY_AT]
            status = value[S.DR_STATUS_CODE]
            headers = value[S.DR_HEADERS]
            attempts = value[S.DR_WIRE_ATTEMPTS]
            failures = value[S.DR_FAILURES]
            error = value[S.DR_ERROR_CODE]
            quota = value.get(S.L1_QUOTA, {})
            if (
                (
                    deadline is not C.NONE
                    and (
                        type(deadline) not in (int, float)
                        or not math.isfinite(deadline)
                        or deadline < C.ZERO
                    )
                )
                or (
                    status is not C.NONE
                    and (
                        type(status) is not int or not C.DR_STATUS_MIN <= status <= C.DR_STATUS_MAX
                    )
                )
                or not isinstance(headers, dict)
                or any(
                    name not in C.NET_SAFE_HEADERS or not isinstance(item, str)
                    for name, item in headers.items()
                )
                or type(attempts) is not int
                or attempts < C.ZERO
                or type(failures) is not int
                or failures < C.ZERO
                or (error is not C.NONE and error not in C.DR_ERROR_CODES)
                or not _valid_quota(quota)
            ):
                raise ValueError
            return HttpRetryState(deadline, status, headers, attempts, failures, error, quota)
        except (sqlite3.Error, ValueError, TypeError, RecursionError, OverflowError):
            raise MetadataCacheError(S.DR_RETRY_READ_ERROR) from C.NONE

    def save_retry_state(self, provider: Source, host: str, state: HttpRetryState) -> None:
        try:
            if (
                (
                    state.retry_at is not C.NONE
                    and (
                        type(state.retry_at) not in (int, float)
                        or not math.isfinite(state.retry_at)
                        or state.retry_at < C.ZERO
                    )
                )
                or (
                    state.status_code is not C.NONE
                    and (
                        type(state.status_code) is not int
                        or not C.DR_STATUS_MIN <= state.status_code <= C.DR_STATUS_MAX
                    )
                )
                or type(state.wire_attempts) is not int
                or state.wire_attempts < C.ZERO
                or type(state.failures) is not int
                or state.failures < C.ZERO
                or (state.error_code is not C.NONE and state.error_code not in C.DR_ERROR_CODES)
                or any(not isinstance(value, str) for value in state.headers.values())
                or not _valid_quota(state.quota)
            ):
                raise ValueError
            document: dict[str, object] = {
                S.DR_RETRY_AT: state.retry_at,
                S.DR_STATUS_CODE: state.status_code,
                S.DR_HEADERS: {
                    name: value
                    for name, value in state.headers.items()
                    if name in C.NET_SAFE_HEADERS
                },
                S.DR_WIRE_ATTEMPTS: state.wire_attempts,
                S.DR_FAILURES: state.failures,
                S.DR_ERROR_CODE: state.error_code,
            }
            if state.quota:
                document[S.L1_QUOTA] = dict(state.quota)
            payload = json.dumps(document, sort_keys=C.TRUE, allow_nan=C.FALSE)
        except (ValueError, TypeError, OverflowError, RecursionError):
            raise MetadataCacheError(S.DR_RETRY_WRITE_ERROR) from C.NONE
        try:
            with self._db() as connection:
                connection.execute(
                    S.DR_RETRY_INSERT,
                    (*self._key(provider, host), payload, _checksum(payload, C.ZERO)),
                )
        except sqlite3.Error:
            raise MetadataCacheError(S.DR_RETRY_WRITE_ERROR) from C.NONE
