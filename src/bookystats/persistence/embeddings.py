from __future__ import annotations

import hashlib
import hmac
import math
import os
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import BookyError


class EmbeddingCacheError(BookyError):
    pass


class _VectorRecord(C.Model):
    version: int
    fingerprint: str
    text_key: str
    dimension: int
    vector: tuple[float, ...]


class _VectorEnvelope(C.Model):
    record: _VectorRecord
    sha256: str


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open(S.EM3_READ_BINARY) as stream:
        while chunk := stream.read(C.EM3_DOWNLOAD_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def publish_immutable(staged: Path, destination: Path) -> None:
    # Hard-link publication is atomic and never replaces an existing entry on any OS.
    try:
        os.link(staged, destination)
    except FileExistsError:
        if not hmac.compare_digest(file_hash(staged), file_hash(destination)):
            raise EmbeddingCacheError(S.EM3_CACHE_ERROR) from C.NONE


def _validate(vector: tuple[float, ...]) -> None:
    if len(vector) != C.EM3_DIMENSION or not all(math.isfinite(value) for value in vector):
        raise EmbeddingCacheError(S.EM3_CACHE_ERROR)
    norm = math.hypot(*vector)
    if not math.isclose(norm, C.ONE, abs_tol=C.EM3_UNIT_TOLERANCE):
        raise EmbeddingCacheError(S.EM3_CACHE_ERROR)


class EmbeddingVectorCache:
    def __init__(self, directory: Path, fingerprint: str) -> None:
        namespace = _digest(fingerprint.encode(S.UTF_8))
        self.directory = directory / S.EM3_VECTORS_FOLDER / namespace
        self.fingerprint = fingerprint

    def key(self, text: str) -> str:
        return _digest(text.encode(S.UTF_8))

    def _path(self, text_key: str) -> Path:
        if C.EM3_HASH_PATTERN.fullmatch(text_key) is C.NONE:
            raise EmbeddingCacheError(S.EM3_CACHE_ERROR)
        return self.directory / (text_key + S.EM3_CACHE_SUFFIX)

    def get(self, text_key: str) -> tuple[float, ...] | None:
        path = self._path(text_key)
        try:
            if not path.exists():
                return C.NONE
            if path.stat().st_size > C.EM3_CACHE_MAX_BYTES:
                raise EmbeddingCacheError(S.EM3_CACHE_ERROR)
            envelope = _VectorEnvelope.model_validate_json(path.read_bytes(), strict=C.TRUE)
            record = envelope.record
            expected = _digest(record.model_dump_json().encode(S.UTF_8))
            if (
                C.EM3_HASH_PATTERN.fullmatch(envelope.sha256) is C.NONE
                or not hmac.compare_digest(expected, envelope.sha256)
                or record.version != C.EM3_CACHE_VERSION
                or record.fingerprint != self.fingerprint
                or record.text_key != text_key
                or record.dimension != C.EM3_DIMENSION
            ):
                raise EmbeddingCacheError(S.EM3_CACHE_ERROR)
            _validate(record.vector)
            return record.vector
        except (OSError, ValueError, ValidationError, RecursionError):
            raise EmbeddingCacheError(S.EM3_CACHE_ERROR) from C.NONE

    def put(self, text_key: str, vector: tuple[float, ...]) -> None:
        _validate(vector)
        record = _VectorRecord(
            version=C.EM3_CACHE_VERSION,
            fingerprint=self.fingerprint,
            text_key=text_key,
            dimension=C.EM3_DIMENSION,
            vector=vector,
        )
        envelope = _VectorEnvelope(
            record=record, sha256=_digest(record.model_dump_json().encode(S.UTF_8))
        )
        path = self._path(text_key)
        staged = self.directory / (uuid4().hex + S.EM3_PART_SUFFIX)
        try:
            existing = self.get(text_key)
            if existing is not C.NONE:
                if existing != vector:
                    raise EmbeddingCacheError(S.EM3_CACHE_ERROR)
                return
            self.directory.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
            with staged.open(S.EM3_WRITE_BINARY) as stream:
                stream.write(envelope.model_dump_json().encode(S.UTF_8))
                stream.flush()
                os.fsync(stream.fileno())
            publish_immutable(staged, path)
        except OSError:
            raise EmbeddingCacheError(S.EM3_CACHE_ERROR) from C.NONE
        finally:
            staged.unlink(missing_ok=C.TRUE)
