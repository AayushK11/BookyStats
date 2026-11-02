from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import zlib
from typing import cast

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import BookyError
from bookystats.domain.models import canonical_json as canonical_json


class PayloadIntegrityError(BookyError):
    pass


class PayloadStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    @staticmethod
    def _parse(text: str) -> JsonValue:
        try:
            return cast(JsonValue, json.loads(text))
        except (ValueError, TypeError):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED) from C.NONE

    def save_json(self, text: str) -> str:
        return self.save(self._parse(text))

    def save(self, value: JsonValue) -> str:
        try:
            text = canonical_json(value)
            body = text.encode(S.UTF_8)
        except (ValueError, UnicodeError):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED) from C.NONE
        if len(body) > C.STORAGE_PAYLOAD_MAX_BYTES:
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        digest = hashlib.sha256(body).hexdigest()
        reference = S.STORAGE_PAYLOAD_PREFIX + digest
        cursor = self.connection.execute(
            S.STORAGE_PAYLOAD_INSERT,
            (digest, zlib.compress(body, level=C.STORAGE_PAYLOAD_COMPRESSION_LEVEL), len(body)),
        )
        if cursor.rowcount == C.ZERO and self.load_text(reference) != text:
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        return reference

    def load_text(self, reference: str) -> str:
        if not isinstance(reference, str) or not reference.startswith(S.STORAGE_PAYLOAD_PREFIX):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        digest = reference[len(S.STORAGE_PAYLOAD_PREFIX) :]
        if not C.RAW_HASH_PATTERN.fullmatch(digest):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        row = self.connection.execute(S.STORAGE_PAYLOAD_SELECT, (digest,)).fetchone()
        if row is C.NONE:
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        body, size = row
        if (
            not isinstance(body, bytes)
            or not isinstance(size, int)
            or not C.ZERO <= size <= C.STORAGE_PAYLOAD_MAX_BYTES
        ):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        try:
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(body, size + C.ONE)
            if (
                len(decoded) != size
                or not decoder.eof
                or decoder.unused_data
                or decoder.unconsumed_tail
                or not hmac.compare_digest(hashlib.sha256(decoded).hexdigest(), digest)
            ):
                raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
            return decoded.decode(S.UTF_8)
        except (zlib.error, UnicodeError):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED) from C.NONE

    def load(self, reference: str) -> JsonValue:
        return self._parse(self.load_text(reference))

    def save_collection_json(self, text: str) -> str:
        collection = self._parse(text)
        if not isinstance(collection, dict) or not isinstance(collection.get(S.RECORDS), list):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        records = collection[S.RECORDS]
        assert isinstance(records, list)
        if not all(isinstance(record, dict) for record in records):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        collection[S.RECORDS] = [self.save(record) for record in records]
        return self.save(collection)

    def load_collection_json(self, reference: str) -> str:
        collection = self.load(reference)
        if not isinstance(collection, dict) or not isinstance(collection.get(S.RECORDS), list):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        records = collection[S.RECORDS]
        assert isinstance(records, list)
        if not all(isinstance(record, str) for record in records):
            raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
        restored: list[JsonValue] = []
        for record in records:
            assert isinstance(record, str)
            value = self.load(record)
            if not isinstance(value, dict):
                raise PayloadIntegrityError(S.STORAGE_PAYLOAD_DAMAGED)
            restored.append(value)
        collection[S.RECORDS] = restored
        return canonical_json(collection)
