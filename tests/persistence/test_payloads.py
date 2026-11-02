from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.persistence.payloads import PayloadIntegrityError, PayloadStore, canonical_json


@pytest.fixture
def payloads() -> Iterator[PayloadStore]:
    connection = sqlite3.connect(S.TEST_PAYLOAD_MEMORY)
    connection.execute(S.STORAGE_PAYLOAD_SCHEMA)
    try:
        yield PayloadStore(connection)
    finally:
        connection.close()


def test_payloads_compress_deduplicate_and_restore_exact_values(payloads: PayloadStore) -> None:
    value = {S.TEST_PAYLOAD_KEY: S.TEST_PAYLOAD_TEXT * C.TEST_PAYLOAD_REPETITIONS}
    first = payloads.save(value)
    assert payloads.save(value) == first
    assert payloads.load(first) == value
    assert payloads.connection.execute(S.STORAGE_PAYLOAD_COUNTS).fetchone()[C.ZERO] == C.ONE
    body, size = payloads.connection.execute(
        S.STORAGE_PAYLOAD_SELECT, (first[len(S.STORAGE_PAYLOAD_PREFIX) :],)
    ).fetchone()
    assert len(body) < size


@pytest.mark.parametrize(S.TEST_PAYLOAD_SQL_PARAM, C.TEST_PAYLOAD_TAMPERING)
def test_damaged_missing_or_inconsistent_payloads_fail_explicitly(
    payloads: PayloadStore,
    sql: str,
) -> None:
    reference = payloads.save({S.TEST_PAYLOAD_KEY: S.TEST_PAYLOAD_TEXT})
    payloads.connection.execute(sql, (reference[len(S.STORAGE_PAYLOAD_PREFIX) :],))
    with pytest.raises(PayloadIntegrityError, match=S.STORAGE_PAYLOAD_DAMAGED):
        payloads.load(reference)
    if sql != S.TEST_PAYLOAD_REMOVE:
        with pytest.raises(PayloadIntegrityError, match=S.STORAGE_PAYLOAD_DAMAGED):
            payloads.save({S.TEST_PAYLOAD_KEY: S.TEST_PAYLOAD_TEXT})


def test_collection_manifests_share_records_and_restore_order(payloads: PayloadStore) -> None:
    record = {S.TEST_PAYLOAD_KEY: S.TEST_PAYLOAD_TEXT}
    first = payloads.save_collection_json(canonical_json({S.RECORDS: [record, record]}))
    restored = json.loads(payloads.load_collection_json(first))
    assert isinstance(restored, dict)
    assert restored[S.RECORDS] == [record, record]
    assert payloads.connection.execute(S.STORAGE_PAYLOAD_COUNTS).fetchone()[C.ZERO] == C.TWO
