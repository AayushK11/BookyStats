from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.persistence.embeddings import EmbeddingCacheError, EmbeddingVectorCache


def _vector() -> tuple[float, ...]:
    return (float(C.ONE),) + (float(C.ZERO),) * (C.EM3_DIMENSION - C.ONE)


def test_typed_cache_round_trip_restart_and_immutable_collision(tmp_path: Path) -> None:
    store = EmbeddingVectorCache(tmp_path, S.EM3_TEST_FINGERPRINT)
    key = store.key(S.EM3_TEST_TEXT)
    assert store.get(key) is C.NONE
    store.put(key, _vector())
    store.put(key, _vector())
    assert EmbeddingVectorCache(tmp_path, S.EM3_TEST_FINGERPRINT).get(key) == _vector()
    incompatible = tuple(reversed(_vector()))
    with pytest.raises(EmbeddingCacheError):
        store.put(key, incompatible)
    assert store.get(key) == _vector()
    assert not tuple(tmp_path.rglob(S.EM3_PART_PATTERN))
    assert EmbeddingVectorCache(tmp_path, S.EM3_MODEL).get(key) is C.NONE
    assert store.get(store.key(S.EM3_TEST_OTHER_TEXT)) is C.NONE


def test_concurrent_publication_keeps_complete_identical_entry(tmp_path: Path) -> None:
    store = EmbeddingVectorCache(tmp_path, S.EM3_TEST_FINGERPRINT)
    key = store.key(S.EM3_TEST_TEXT)
    with ThreadPoolExecutor(max_workers=C.FOUR) as pool:
        tuple(pool.map(lambda item: store.put(item, _vector()), (key,) * C.FOUR))
    assert store.get(key) == _vector()
    assert len(tuple(store.directory.glob(S.EM3_JSON_PATTERN))) == C.ONE
    assert not tuple(tmp_path.rglob(S.EM3_PART_PATTERN))


@pytest.mark.parametrize(
    S.EM3_TEST_DIGEST_FIELDS,
    C.EM3_TEST_BAD_DIGESTS,
)
def test_hash_corruption_is_explicit_and_never_overwritten(tmp_path: Path, digest: str) -> None:
    store = EmbeddingVectorCache(tmp_path, S.EM3_TEST_FINGERPRINT)
    key = store.key(S.EM3_TEST_TEXT)
    store.put(key, _vector())
    path = store.directory / (key + S.EM3_CACHE_SUFFIX)
    payload = json.loads(path.read_bytes())
    payload[S.EM3_TEST_HASH] = digest
    corrupted = json.dumps(payload).encode(S.UTF_8)
    path.write_bytes(corrupted)
    with pytest.raises(EmbeddingCacheError):
        store.get(key)
    with pytest.raises(EmbeddingCacheError):
        store.put(key, _vector())
    assert path.read_bytes() == corrupted


def test_wrong_typed_dimensions_rejected_even_with_recomputed_hash(tmp_path: Path) -> None:
    store = EmbeddingVectorCache(tmp_path, S.EM3_TEST_FINGERPRINT)
    key = store.key(S.EM3_TEST_TEXT)
    store.put(key, _vector())
    path = store.directory / (key + S.EM3_CACHE_SUFFIX)
    payload = json.loads(path.read_bytes())
    payload[S.EM3_TEST_RECORD][S.EM3_TEST_DIMENSION] = C.ONE
    payload[S.EM3_TEST_HASH] = hashlib.sha256(
        json.dumps(
            payload[S.EM3_TEST_RECORD], separators=(S.COMMA, S.COLON), ensure_ascii=C.FALSE
        ).encode(S.UTF_8)
    ).hexdigest()
    path.write_text(json.dumps(payload), encoding=S.UTF_8)
    with pytest.raises(EmbeddingCacheError):
        store.get(key)


def test_invalid_cache_vectors_paths_and_payloads_are_explicit(tmp_path: Path) -> None:
    store = EmbeddingVectorCache(tmp_path, S.EM3_TEST_FINGERPRINT)
    key = store.key(S.EM3_TEST_TEXT)
    with pytest.raises(EmbeddingCacheError):
        store.put(key, (float(C.ONE),))
    with pytest.raises(EmbeddingCacheError):
        store.put(key, (float(C.ZERO),) * C.EM3_DIMENSION)
    with pytest.raises(EmbeddingCacheError):
        store.put(key, (C.EM3_TEST_NAN,) * C.EM3_DIMENSION)
    with pytest.raises(EmbeddingCacheError):
        store.get(S.EM3_TEST_TEXT)
    store.directory.mkdir(parents=C.TRUE)
    path = store.directory / (key + S.EM3_CACHE_SUFFIX)
    path.write_bytes(S.EM3_TEST_CORRUPT_BYTES)
    with pytest.raises(EmbeddingCacheError):
        store.get(key)
