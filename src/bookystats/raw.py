from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import (
    parse_qsl,
    quote,
    quote_plus,
    unquote,
    unquote_plus,
    urlencode,
    urlsplit,
    urlunsplit,
)
from uuid import uuid4

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import BookyError
from bookystats.interfaces import HttpFetcher, HttpResponse
from bookystats.models import Account, Source, utc_now


class RawStoreError(BookyError):
    pass


@C.frozen_dataclass
class RawDocument:
    id: str
    source: Source
    account_id: str
    body: bytes
    media_type: str
    origin: str
    captured_at: str
    sha256: str


def _capture_values(document: RawDocument) -> tuple[str, ...]:
    return (
        document.id,
        document.source.value,
        document.account_id,
        document.media_type,
        document.origin,
        document.captured_at,
        document.sha256,
    )


def _checksum(document: RawDocument, sequence: int) -> str:
    encoded = json.dumps((sequence, *_capture_values(document)), ensure_ascii=C.TRUE).encode(
        S.UTF_8
    )
    return hashlib.sha256(encoded).hexdigest()


class RawStore:
    def __init__(self, path: Path) -> None:
        self._connection: sqlite3.Connection | None = C.NONE
        try:
            path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
            connection = sqlite3.connect(path, timeout=C.FIVE)
            self._connection = connection
            connection.execute(S.RAW_PRAGMA_FOREIGN_KEYS)
            connection.execute(S.RAW_PRAGMA_SYNCHRONOUS)
            with connection:
                connection.execute(S.RAW_BEGIN)
                self._initialize(connection)
        except RawStoreError:
            self.close()
            raise
        except (OSError, sqlite3.Error):
            self.close()
            raise RawStoreError(S.RAW_OPEN_ERROR) from C.NONE

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        if tuple(connection.execute(S.RAW_PRAGMA_INTEGRITY).fetchall()) != C.RAW_INTEGRITY_OK:
            raise RawStoreError(S.RAW_CORRUPT_ERROR)
        application = connection.execute(S.RAW_PRAGMA_APPLICATION).fetchone()[C.ZERO]
        version = connection.execute(S.RAW_PRAGMA_VERSION).fetchone()[C.ZERO]
        objects = tuple(connection.execute(S.RAW_SCHEMA_OBJECTS).fetchall())
        if application == C.ZERO and version == C.ZERO and not objects:
            connection.execute(S.RAW_PAYLOAD_SCHEMA)
            connection.execute(S.RAW_CAPTURE_SCHEMA)
            connection.execute(S.RAW_INDEX_SCHEMA)
            connection.execute(S.RAW_PRAGMA_APPLICATION_SET.format(value=C.RAW_APPLICATION_ID))
            connection.execute(S.RAW_PRAGMA_VERSION_SET.format(value=C.RAW_SCHEMA_VERSION))
        elif (
            application != C.RAW_APPLICATION_ID
            or version != C.RAW_SCHEMA_VERSION
            or objects != C.RAW_SCHEMA_OBJECTS
        ):
            raise RawStoreError(S.RAW_UNSUPPORTED_ERROR)
        connection.execute(S.RAW_CHECK_SCHEMA)
        if connection.execute(S.RAW_PRAGMA_FOREIGN_CHECK).fetchall():
            raise RawStoreError(S.RAW_CORRUPT_ERROR)

    def _db(self) -> sqlite3.Connection:
        if self._connection is C.NONE:
            raise RawStoreError(S.RAW_CLOSED_ERROR)
        return self._connection

    @staticmethod
    def _binding(source: Source, account_id: str) -> None:
        if not isinstance(source, Source) or not isinstance(account_id, str) or not account_id:
            raise RawStoreError(S.RAW_INVALID_ERROR)

    def capture(
        self,
        source: Source,
        account_id: str,
        body: bytes,
        *,
        media_type: str,
        origin: str,
    ) -> RawDocument:
        self._binding(source, account_id)
        if (
            not isinstance(body, bytes)
            or not isinstance(media_type, str)
            or not media_type
            or not isinstance(origin, str)
            or not origin
        ):
            raise RawStoreError(S.RAW_INVALID_ERROR)
        document = RawDocument(
            id=uuid4().hex,
            source=source,
            account_id=account_id,
            body=body,
            media_type=media_type,
            origin=origin,
            captured_at=utc_now(),
            sha256=hashlib.sha256(body).hexdigest(),
        )
        try:
            with self._db() as connection:
                connection.execute(S.RAW_BEGIN)
                connection.execute(S.RAW_INSERT_PAYLOAD, (document.sha256, body))
                stored = connection.execute(S.RAW_SELECT_PAYLOAD, (document.sha256,)).fetchone()
                if stored is C.NONE or stored[C.ZERO] != body:
                    raise RawStoreError(S.RAW_CORRUPT_ERROR)
                sequence = connection.execute(S.RAW_NEXT_SEQUENCE).fetchone()[C.ZERO]
                if not isinstance(sequence, int) or sequence <= C.ZERO:
                    raise RawStoreError(S.RAW_CORRUPT_ERROR)
                connection.execute(
                    S.RAW_INSERT_CAPTURE,
                    (sequence, *_capture_values(document), _checksum(document, sequence)),
                )
        except (sqlite3.Error, UnicodeError):
            raise RawStoreError(S.RAW_WRITE_ERROR) from C.NONE
        return document

    def capture_file(self, account: Account, path: Path) -> RawDocument:
        try:
            body = path.read_bytes()
        except OSError:
            raise RawStoreError(S.RAW_FILE_ERROR) from C.NONE
        return self.capture(
            account.source,
            account.account_id,
            body,
            media_type=(
                S.RAW_CSV_MEDIA_TYPE
                if path.suffix.casefold() == S.RAW_CSV_SUFFIX
                else S.RAW_BINARY_MEDIA_TYPE
            ),
            origin=path.name,
        )

    @staticmethod
    def _document(row: tuple[object, ...]) -> RawDocument:
        (
            sequence,
            identifier,
            source,
            account,
            body,
            media_type,
            origin,
            captured_at,
            digest,
            checksum,
        ) = row
        if (
            not isinstance(sequence, int)
            or sequence <= C.ZERO
            or not isinstance(identifier, str)
            or not identifier
            or not isinstance(source, str)
            or not isinstance(account, str)
            or not account
            or not isinstance(body, bytes)
            or not isinstance(media_type, str)
            or not media_type
            or not isinstance(origin, str)
            or not origin
            or not isinstance(captured_at, str)
            or not isinstance(digest, str)
            or not C.RAW_HASH_PATTERN.fullmatch(digest)
            or not isinstance(checksum, str)
            or not C.RAW_HASH_PATTERN.fullmatch(checksum)
        ):
            raise RawStoreError(S.RAW_CORRUPT_ERROR)
        try:
            bound_source = Source(source)
            captured = datetime.fromisoformat(captured_at)
        except ValueError:
            raise RawStoreError(S.RAW_CORRUPT_ERROR) from C.NONE
        if captured.tzinfo is C.NONE or captured.utcoffset() != UTC.utcoffset(captured):
            raise RawStoreError(S.RAW_CORRUPT_ERROR)
        document = RawDocument(
            identifier, bound_source, account, body, media_type, origin, captured_at, digest
        )
        if not hmac.compare_digest(hashlib.sha256(body).hexdigest(), digest) or not (
            hmac.compare_digest(_checksum(document, sequence), checksum)
        ):
            raise RawStoreError(S.RAW_CORRUPT_ERROR)
        return document

    def latest(self, source: Source, account_id: str) -> RawDocument | None:
        self._binding(source, account_id)
        try:
            row: tuple[object, ...] | None = (
                self._db().execute(S.RAW_LATEST_CAPTURE, (source.value, account_id)).fetchone()
            )
        except (sqlite3.Error, UnicodeError):
            raise RawStoreError(S.RAW_READ_ERROR) from C.NONE
        return C.NONE if row is C.NONE else self._document(row)

    def get(self, document_id: str) -> RawDocument:
        try:
            row: tuple[object, ...] | None = (
                self._db().execute(S.RAW_GET_CAPTURE, (document_id,)).fetchone()
            )
        except (sqlite3.Error, UnicodeError):
            raise RawStoreError(S.RAW_READ_ERROR) from C.NONE
        if row is C.NONE:
            raise RawStoreError(S.RAW_MISSING_ERROR)
        return self._document(row)

    def close(self) -> None:
        if self._connection is not C.NONE:
            connection, self._connection = self._connection, C.NONE
            try:
                connection.close()
            except sqlite3.Error:
                raise RawStoreError(S.RAW_CLOSE_ERROR) from C.NONE


def _sensitive_name(name: str) -> bool:
    normalized = C.RAW_SECRET_NAME_PATTERN.sub(S.EMPTY, name.casefold())
    return normalized.endswith(C.RAW_SECRET_NAME_SUFFIXES)


def _credential_parts(name: str, value: str) -> set[str]:
    parts = {value}
    if S.RAW_AUTHORIZATION in name.casefold():
        tokens = value.split(maxsplit=C.ONE)
        credential = tokens[C.ONE] if len(tokens) == C.TWO else S.EMPTY
        parts.add(credential)
        if tokens and tokens[C.ZERO].casefold() == S.RAW_BASIC:
            try:
                decoded = base64.b64decode(credential, validate=C.TRUE).decode(S.UTF_8)
            except ValueError:
                pass
            else:
                parts.update(decoded.partition(S.COLON))
    if S.RAW_COOKIE in name.casefold():
        parts.update(
            item.partition(S.RAW_EQUALS)[C.TWO].strip().strip(S.RAW_QUOTES)
            for item in value.split(S.RAW_SEMICOLON)
        )
    return {part for part in parts if part and part != S.COLON}


def _request_secrets(
    url: str, params: Mapping[str, str] | None, headers: Mapping[str, str] | None
) -> set[str]:
    try:
        parsed = urlsplit(url)
        secrets = {unquote(value) for value in (parsed.username, parsed.password) if value}
        pairs = [*parse_qsl(parsed.query), *(params or {}).items(), *(headers or {}).items()]
        for name, value in pairs:
            if _sensitive_name(name):
                secrets.update(_credential_parts(name, value))
        return secrets
    except ValueError:
        raise RawStoreError(S.RAW_PROVENANCE_ERROR) from C.NONE


def _safe_origin(url: str) -> str:
    try:
        parsed = urlsplit(url)
        if parsed.scheme != S.HTTPS or not parsed.hostname:
            raise ValueError
        netloc = parsed.netloc.rsplit(S.RAW_AT, C.ONE)[-C.ONE]
        return urlunsplit((parsed.scheme, netloc, parsed.path, S.EMPTY, S.EMPTY))
    except ValueError:
        raise RawStoreError(S.RAW_PROVENANCE_ERROR) from C.NONE


def _provider_origin(
    source: Source, request_url: str, response_url: str, params: Mapping[str, str] | None
) -> str:
    try:
        origin = _safe_origin(response_url)
        allowed = C.RAW_PROVIDER_QUERY_KEYS[source]
        query: dict[str, str] = {}
        if _safe_origin(request_url) == origin:
            query.update(
                (key, value)
                for key, value in parse_qsl(urlsplit(request_url).query)
                if key in allowed
            )
            query.update((key, value) for key, value in (params or {}).items() if key in allowed)
        query.update(
            (key, value) for key, value in parse_qsl(urlsplit(response_url).query) if key in allowed
        )
        return urlunsplit(urlsplit(origin)._replace(query=urlencode(query)))
    except ValueError:
        raise RawStoreError(S.RAW_PROVENANCE_ERROR) from C.NONE


def _reject_credential_echo(
    response: HttpResponse, origin: str, media_type: str, secrets: set[str]
) -> None:
    try:
        metadata = (origin + media_type).encode(S.UTF_8)
        # Decode escapes only for credential screening; archived bytes remain untouched.
        screening_body = (
            C.RAW_UNICODE_ESCAPE_PATTERN.sub(
                lambda match: chr(int(match[C.ONE], C.RAW_HEX_BASE)).encode(
                    S.UTF_8, errors=S.RAW_SURROGATEPASS
                ),
                response.body,
            )
            if secrets
            else response.body
        )
        for secret in secrets:
            decoded = unquote_plus(secret)
            variants = {
                secret,
                decoded,
                quote(secret, safe=S.EMPTY),
                quote_plus(secret, safe=S.EMPTY),
                html.escape(secret),
                json.dumps(secret, ensure_ascii=C.TRUE)[C.ONE : -C.ONE],
            }
            for variant in variants:
                for encoding in C.RAW_SECRET_ENCODINGS:
                    encoded = variant.encode(encoding)
                    if encoded and (
                        encoded in response.body or encoded in screening_body or encoded in metadata
                    ):
                        raise RawStoreError(S.RAW_CREDENTIAL_ERROR)
    except UnicodeError:
        raise RawStoreError(S.RAW_CREDENTIAL_ERROR) from C.NONE


class RecordingFetcher:
    def __init__(self, http: HttpFetcher, archive: RawStore, *, source: Source) -> None:
        if not isinstance(source, Source) or source not in C.RAW_METADATA_SOURCES:
            raise RawStoreError(S.RAW_PROVIDER_ERROR)
        self._http = http
        self._archive = archive
        self._source = source

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        secrets = _request_secrets(url, params, headers)
        response = self._http.fetch(url, params=params, headers=headers)
        origin = _provider_origin(self._source, url, response.url, params)
        media_type = next(
            (
                value.split(S.RAW_SEMICOLON, C.ONE)[C.ZERO].strip()
                for name, value in response.headers.items()
                if name.casefold() == S.CONTENT_TYPE and value.strip()
            ),
            S.RAW_BINARY_MEDIA_TYPE,
        )
        _reject_credential_echo(response, origin, media_type, secrets)
        self._archive.capture(
            self._source,
            S.RAW_CATALOG_ACCOUNT,
            response.body,
            media_type=media_type,
            origin=origin,
        )
        return response
