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
from bookystats.domain.errors import BookyError
from bookystats.domain.interfaces import HttpFetcher, HttpResponse, PageDocument
from bookystats.domain.models import Account, CollectionSnapshot, Source, SyncState, utc_now
from bookystats.persistence.backup import StoreMigrationBlocked, protect_migration


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
    collection: str = S.LIBRARY
    http_metadata: str | None = C.NONE


@C.frozen_dataclass
class SourceCapture:
    source: Source
    account_id: str
    collection: str
    state: SyncState
    record_count: int
    expected_count: int | None
    termination_verified: bool
    identity_verified: bool
    pages_seen: int
    documents: tuple[RawDocument, ...]


def _capture_values(document: RawDocument) -> tuple[str, ...]:
    return (
        document.id,
        document.source.value,
        document.account_id,
        document.media_type,
        document.origin,
        document.captured_at,
        document.sha256,
        document.collection,
    )


def _checksum(document: RawDocument, sequence: int, *, legacy: bool = C.FALSE) -> str:
    values = _capture_values(document)
    if legacy:
        values = values[: -C.ONE]
    if document.http_metadata is not C.NONE:
        values = (*values, document.http_metadata)
    encoded = json.dumps((sequence, *values), ensure_ascii=C.TRUE).encode(S.UTF_8)
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
            self._protect_migration(path, connection)
            with connection:
                connection.execute(S.RAW_BEGIN)
                self._initialize(connection)
        except RawStoreError:
            self.close()
            raise
        except StoreMigrationBlocked:
            self.close()
            raise RawStoreError(S.DBSAFE_RAW_BLOCKED) from C.NONE
        except (OSError, sqlite3.Error):
            self.close()
            raise RawStoreError(S.RAW_OPEN_ERROR) from C.NONE

    @staticmethod
    def _protect_migration(path: Path, connection: sqlite3.Connection) -> None:
        # Older raw layouts are upgraded in place, so they get a verified backup first.
        application = connection.execute(S.RAW_PRAGMA_APPLICATION).fetchone()[C.ZERO]
        version = connection.execute(S.RAW_PRAGMA_VERSION).fetchone()[C.ZERO]
        if application == C.RAW_APPLICATION_ID and version in (
            C.RAW_LEGACY_SCHEMA_VERSION,
            C.RAW_SCHEMA_VERSION,
        ):
            protect_migration(connection, path, C.StoreKind.RAW, reason=S.DBSAFE_REASON_MIGRATION)

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
            connection.execute(S.DR_RAW_MIGRATE)
            connection.execute(S.RAW_INDEX_SCHEMA)
            connection.execute(S.RAW_PRAGMA_APPLICATION_SET.format(value=C.RAW_APPLICATION_ID))
            connection.execute(S.RAW_PRAGMA_VERSION_SET.format(value=C.DR_RAW_SCHEMA_VERSION))
        elif (
            application != C.RAW_APPLICATION_ID
            or version
            not in (C.RAW_LEGACY_SCHEMA_VERSION, C.RAW_SCHEMA_VERSION, C.DR_RAW_SCHEMA_VERSION)
            or objects != C.RAW_SCHEMA_OBJECTS
        ):
            raise RawStoreError(S.RAW_UNSUPPORTED_ERROR)
        elif version == C.RAW_LEGACY_SCHEMA_VERSION:
            rows = connection.execute(S.RAW_LEGACY_SELECT).fetchall()
            documents = [
                (row[C.ZERO], RawStore._document((*row, S.LIBRARY), legacy=C.TRUE)) for row in rows
            ]
            connection.execute(S.RAW_MIGRATE_COLLECTION)
            for sequence, document in documents:
                connection.execute(
                    S.RAW_MIGRATE_CHECKSUM, (_checksum(document, sequence), document.id)
                )
        if objects and version in (C.RAW_LEGACY_SCHEMA_VERSION, C.RAW_SCHEMA_VERSION):
            connection.execute(S.DR_RAW_MIGRATE)
            connection.execute(S.RAW_PRAGMA_VERSION_SET.format(value=C.DR_RAW_SCHEMA_VERSION))
        connection.execute(S.DR_RAW_CHECK)
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
        collection: str = S.LIBRARY,
        http_response: HttpResponse | None = C.NONE,
    ) -> RawDocument:
        self._binding(source, account_id)
        if (
            not isinstance(body, bytes)
            or not isinstance(media_type, str)
            or not media_type
            or not isinstance(origin, str)
            or not origin
            or collection not in (S.LIBRARY, S.TO_READ, S.READ)
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
            collection=collection,
            http_metadata=(
                json.dumps(
                    {
                        S.DR_STATUS_CODE: http_response.status_code,
                        S.DR_HEADERS: {
                            name.lower(): value
                            for name, value in http_response.headers.items()
                            if name.lower() in C.NET_SAFE_HEADERS
                        },
                        S.DR_RETRY_AT: http_response.retry_at,
                        S.DR_WIRE_ATTEMPTS: http_response.wire_attempts,
                        S.DR_ERROR_CODE: http_response.error_code,
                    },
                    sort_keys=C.TRUE,
                    allow_nan=C.FALSE,
                )
                if http_response is not C.NONE
                else C.NONE
            ),
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
                    S.DR_RAW_INSERT,
                    (
                        sequence,
                        *_capture_values(document),
                        _checksum(document, sequence),
                        document.http_metadata,
                    ),
                )
        except (sqlite3.Error, UnicodeError):
            raise RawStoreError(S.RAW_WRITE_ERROR) from C.NONE
        return document

    def capture_file(
        self, account: Account, path: Path, *, collection: str = S.LIBRARY
    ) -> RawDocument:
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
            collection=collection,
        )

    def capture_page(self, account: Account, page: PageDocument, *, collection: str) -> RawDocument:
        parsed = urlsplit(page.url)
        if (
            parsed.scheme != S.HTTPS
            or parsed.hostname not in C.AUTO_CAPTURE_HOSTS[account.source]
            or parsed.username is not C.NONE
            or parsed.password is not C.NONE
            or any(_sensitive_name(key) for key, _ in parse_qsl(parsed.query))
        ):
            raise RawStoreError(S.RAW_PROVENANCE_ERROR)
        return self.capture(
            account.source,
            account.account_id,
            page.html.encode(S.UTF_8),
            media_type=S.AUTO_CAPTURE_HTML_MEDIA_TYPE,
            origin=page.url,
            collection=collection,
        )

    def capture_collection(
        self,
        account: Account,
        snapshot: CollectionSnapshot,
        pages: tuple[RawDocument, ...],
    ) -> RawDocument:
        if (
            snapshot.source != account.source
            or snapshot.account_id != account.account_id
            or (snapshot.state == SyncState.COMPLETE and not pages)
            or any(
                page.source != account.source
                or page.account_id != account.account_id
                or page.collection != snapshot.collection
                or self.get(page.id) != page
                for page in pages
            )
        ):
            raise RawStoreError(S.RAW_PROVENANCE_ERROR)
        manifest = {
            S.SOURCE: account.source.value,
            S.ACCOUNT_ID: account.account_id,
            S.COLLECTION: snapshot.collection,
            S.STARTED_AT: snapshot.started_at,
            S.FINISHED_AT: snapshot.finished_at,
            S.STATE: snapshot.state.value,
            S.AUTO_CAPTURE_RECORD_COUNT: len(snapshot.records),
            S.EXPECTED_COUNT: snapshot.expected_count,
            S.TERMINATION_VERIFIED: snapshot.termination_verified,
            S.IDENTITY_VERIFIED: snapshot.identity_verified,
            S.AUTO_CAPTURE_PAGES_SEEN: snapshot.pages_seen,
            S.AUTO_CAPTURE_DOCUMENTS: [
                {
                    S.INPUT_RAW_DOCUMENT_ID: page.id,
                    S.URL: page.origin,
                    S.AUTO_CAPTURE_AT: page.captured_at,
                    S.AUTO_CAPTURE_SHA256: page.sha256,
                }
                for page in pages
            ],
        }
        return self.capture(
            account.source,
            account.account_id,
            json.dumps(manifest, ensure_ascii=C.FALSE).encode(S.UTF_8),
            media_type=S.AUTO_CAPTURE_MANIFEST_MEDIA_TYPE,
            origin=account.profile_url,
            collection=snapshot.collection,
        )

    def load_capture(self, document_id: str) -> SourceCapture:
        manifest = self.get(document_id)
        if manifest.media_type != S.AUTO_CAPTURE_MANIFEST_MEDIA_TYPE:
            raise RawStoreError(S.RAW_PROVENANCE_ERROR)
        try:
            payload = json.loads(manifest.body)
            if not isinstance(payload, dict):
                raise ValueError
            count = payload[S.AUTO_CAPTURE_RECORD_COUNT]
            expected = payload[S.EXPECTED_COUNT]
            termination = payload[S.TERMINATION_VERIFIED]
            identity = payload[S.IDENTITY_VERIFIED]
            pages_seen = payload[S.AUTO_CAPTURE_PAGES_SEEN]
            references = payload[S.AUTO_CAPTURE_DOCUMENTS]
            state = SyncState(payload[S.STATE])
            if (
                payload[S.SOURCE] != manifest.source.value
                or payload[S.ACCOUNT_ID] != manifest.account_id
                or payload[S.COLLECTION] != manifest.collection
                or type(count) is not int
                or count < C.ZERO
                or (expected is not C.NONE and (type(expected) is not int or expected < C.ZERO))
                or type(termination) is not bool
                or type(identity) is not bool
                or type(pages_seen) is not int
                or pages_seen < C.ZERO
                or not isinstance(references, list)
            ):
                raise ValueError
            documents: list[RawDocument] = []
            for reference in references:
                if not isinstance(reference, dict) or not isinstance(
                    reference.get(S.INPUT_RAW_DOCUMENT_ID), str
                ):
                    raise ValueError
                page = self.get(reference[S.INPUT_RAW_DOCUMENT_ID])
                if (
                    page.source != manifest.source
                    or page.account_id != manifest.account_id
                    or page.collection != manifest.collection
                    or page.media_type != S.AUTO_CAPTURE_HTML_MEDIA_TYPE
                    or reference[S.URL] != page.origin
                    or reference[S.AUTO_CAPTURE_SHA256] != page.sha256
                    or reference[S.AUTO_CAPTURE_AT] != page.captured_at
                ):
                    raise ValueError
                documents.append(page)
            if len({page.id for page in documents}) != len(documents):
                raise ValueError
            if state == SyncState.COMPLETE and (
                not documents
                or not termination
                or not identity
                or (expected is not C.NONE and expected != count)
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise RawStoreError(S.RAW_PROVENANCE_ERROR) from C.NONE
        return SourceCapture(
            source=manifest.source,
            account_id=manifest.account_id,
            collection=manifest.collection,
            state=state,
            record_count=count,
            expected_count=expected,
            termination_verified=termination,
            identity_verified=identity,
            pages_seen=pages_seen,
            documents=tuple(documents),
        )

    @staticmethod
    def _document(row: tuple[object, ...], *, legacy: bool = C.FALSE) -> RawDocument:
        http_metadata = row[-C.ONE] if len(row) == C.DR_RAW_ROW_LENGTH else C.NONE
        if len(row) == C.DR_RAW_ROW_LENGTH:
            row = row[: -C.ONE]
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
            collection,
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
            or collection not in (S.LIBRARY, S.TO_READ, S.READ)
            or (http_metadata is not C.NONE and not isinstance(http_metadata, str))
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
            identifier,
            bound_source,
            account,
            body,
            media_type,
            origin,
            captured_at,
            digest,
            str(collection),
            http_metadata,
        )
        if not hmac.compare_digest(hashlib.sha256(body).hexdigest(), digest) or not (
            hmac.compare_digest(_checksum(document, sequence, legacy=legacy), checksum)
        ):
            raise RawStoreError(S.RAW_CORRUPT_ERROR)
        return document

    def latest(
        self,
        source: Source,
        account_id: str,
        *,
        collection: str = S.LIBRARY,
        media_type: str | None = C.NONE,
    ) -> RawDocument | None:
        self._binding(source, account_id)
        try:
            row: tuple[object, ...] | None = (
                self._db()
                .execute(
                    S.DR_RAW_LATEST_MEDIA if media_type is not C.NONE else S.DR_RAW_LATEST,
                    (source.value, account_id, collection, media_type)
                    if media_type is not C.NONE
                    else (source.value, account_id, collection),
                )
                .fetchone()
            )
        except (sqlite3.Error, UnicodeError):
            raise RawStoreError(S.RAW_READ_ERROR) from C.NONE
        return C.NONE if row is C.NONE else self._document(row)

    def get(self, document_id: str) -> RawDocument:
        try:
            row: tuple[object, ...] | None = (
                self._db().execute(S.DR_RAW_GET, (document_id,)).fetchone()
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


def verify_documents(connection: sqlite3.Connection) -> tuple[int, int]:
    # Explicit comprehensive check of every saved capture; normal reads verify only the document
    # they load. Older layouts are verified by the backup and upgrade path instead.
    if connection.execute(S.RAW_PRAGMA_VERSION).fetchone()[C.ZERO] != C.DR_RAW_SCHEMA_VERSION:
        return C.ZERO, C.ZERO
    total = damaged = C.ZERO
    for row in connection.execute(S.DBSAFE_SELECT_RAW_DOCUMENTS):
        total += C.ONE
        try:
            RawStore._document(row)
        except RawStoreError:
            damaged += C.ONE
    return total, damaged


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
        metadata = (
            origin
            + media_type
            + json.dumps(
                {
                    name: value
                    for name, value in response.headers.items()
                    if name.lower() in C.NET_SAFE_HEADERS
                },
                ensure_ascii=C.TRUE,
            )
        ).encode(S.UTF_8)
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
        self.last_capture: RawDocument | None = C.NONE

    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        self.last_capture = C.NONE
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
        safe_response = HttpResponse(
            url=response.url,
            status_code=response.status_code,
            headers={
                name.lower(): value
                for name, value in response.headers.items()
                if name.lower() in C.NET_SAFE_HEADERS
            },
            body=response.body,
            retry_at=response.retry_at,
            wire_attempts=response.wire_attempts,
            error_code=response.error_code,
        )
        self.last_capture = self._archive.capture(
            self._source,
            S.RAW_CATALOG_ACCOUNT,
            response.body,
            media_type=media_type,
            origin=origin,
            http_response=safe_response,
        )
        return response
