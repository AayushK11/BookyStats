from __future__ import annotations

import hashlib
from contextlib import closing
from pathlib import Path

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.exports.csv_import import ExportConnector, FileExportConnector
from bookystats.domain.models import CollectionSnapshot, PublicationResult, Source, SyncState
from bookystats.persistence.library import Database
from bookystats.persistence.raw import RawDocument, RawStore
from tests.support.exports import account, csv_body, document
from tests.support.paths import fixture_path


def legacy_snapshot() -> CollectionSnapshot:
    text = fixture_path(S.L1_IMPORTS_FIXTURES, S.L1_LEGACY_STORYGRAPH_SNAPSHOT).read_text(
        encoding=S.UTF_8
    )
    return CollectionSnapshot.model_validate_json(text)


def legacy_body(legacy: CollectionSnapshot) -> bytes:
    return csv_body(Source.STORYGRAPH, [dict(record.raw_fields) for record in legacy.records])


def replay(legacy: CollectionSnapshot) -> CollectionSnapshot:
    raw = document(legacy_body(legacy), Source.STORYGRAPH)
    return ExportConnector(raw).collect(account(Source.STORYGRAPH))


def publish(db: Database, data: CollectionSnapshot) -> PublicationResult:
    run = db.start_run(S.TEST)
    result = db.save_snapshot(run, data)
    db.finish_run(run, data.state)
    assert result is not C.NONE
    return result


def history_payloads(db: Database, source_id: str) -> list[dict[str, JsonValue]]:
    payloads: list[dict[str, JsonValue]] = []
    for entry in db.record_history(Source.STORYGRAPH, S.TEST_IMPORT_READER, source_id):
        payload = entry[S.RECORD]
        assert isinstance(payload, dict)
        payloads.append(payload)
    return payloads


def last_date_cell(payload: dict[str, JsonValue]) -> JsonValue:
    raw = payload[S.L1_RAW_FIELDS_KEY]
    assert isinstance(raw, dict)
    return raw[S.IMPORT_LAST_DATE_READ]


def test_legacy_payload_with_supplemental_dates_still_deserializes_and_round_trips() -> None:
    legacy = legacy_snapshot()
    assert legacy.processing_version == S.L1_LEGACY_PROCESSING_VERSION
    assert legacy.processing_version != S.IMPORT_PROCESSING_VERSION
    assert len(legacy.records) == C.THREE
    assert (
        tuple(
            record.supplemental_completion_dates[C.ZERO].observation.state
            for record in legacy.records
        )
        == C.L1_LEGACY_DATE_STATES
    )
    assert CollectionSnapshot.model_validate_json(legacy.model_dump_json()) == legacy


def test_replaying_legacy_rows_keeps_identity_and_raw_cells_but_publishes_no_dates() -> None:
    legacy = legacy_snapshot()
    replayed = replay(legacy)
    assert replayed.state == SyncState.COMPLETE
    assert replayed.processing_version == S.IMPORT_PROCESSING_VERSION
    assert replayed.processing_version != legacy.processing_version
    assert len(replayed.records) == len(legacy.records)
    for old, new in zip(legacy.records, replayed.records, strict=C.TRUE):
        assert old.supplemental_completion_dates
        assert not new.supplemental_completion_dates
        assert (new.source_id, new.title, new.authors, new.url) == (
            old.source_id,
            old.title,
            old.authors,
            old.url,
        )
        assert new.raw_fields == old.raw_fields
        assert new.raw_fields[S.IMPORT_LAST_DATE_READ] == old.raw_fields[S.IMPORT_LAST_DATE_READ]
        assert new.observations == tuple(
            item for item in old.observations if item.field != S.DTX_SUPPLEMENTAL_COMPLETION_DATE
        )
    assert S.DTX_SUPPLEMENTAL_COMPLETION_DATE in legacy.capabilities
    assert S.DTX_SUPPLEMENTAL_COMPLETION_DATE not in replayed.capabilities


def test_library_replaces_latest_payloads_and_keeps_legacy_history_intact(tmp_path: Path) -> None:
    legacy = legacy_snapshot()
    replayed = replay(legacy)
    with closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as db:
        db.initialize()
        assert publish(db, legacy).added == C.THREE
        assert publish(db, replayed).updated == C.THREE
        assert publish(db, replayed).unchanged == C.THREE
        active = {record.source_id: record for record in db.active_records()}
        assert set(active) == {record.source_id for record in legacy.records}
        for old in legacy.records:
            current = active[old.source_id]
            assert not current.supplemental_completion_dates
            assert current.raw_fields == old.raw_fields
            assert [item for item in current.observations if item.field == S.RATING] == [
                item for item in old.observations if item.field == S.RATING
            ]
            history = history_payloads(db, old.source_id)
            assert len(history) >= C.TWO
            assert history[C.ZERO][S.DTX_SUPPLEMENTAL_COMPLETION_DATES]
            assert not history[-C.ONE][S.DTX_SUPPLEMENTAL_COMPLETION_DATES]
            assert {last_date_cell(payload) for payload in history} == {
                old.raw_fields[S.IMPORT_LAST_DATE_READ]
            }


def test_file_connector_archives_original_bytes_before_dropping_storygraph_dates(
    tmp_path: Path,
) -> None:
    legacy = legacy_snapshot()
    body = legacy_body(legacy)
    path = tmp_path / S.TEST_RAW_FILE
    path.write_bytes(body)
    captured: list[RawDocument] = []
    with closing(RawStore(tmp_path / S.TEST_RAW_FILENAME)) as archive:
        snapshot = FileExportConnector(
            archive, path, collection=S.LIBRARY, on_capture=captured.append
        ).collect(account(Source.STORYGRAPH))
        stored = archive.get(captured[C.ZERO].id)
    assert stored is not C.NONE
    assert stored.body == body
    assert stored.sha256 == hashlib.sha256(body).hexdigest()
    assert snapshot.raw_document_id == stored.id
    assert snapshot.processing_version == S.IMPORT_PROCESSING_VERSION
    assert [record.raw_fields for record in snapshot.records] == [
        record.raw_fields for record in legacy.records
    ]
    assert not any(record.supplemental_completion_dates for record in snapshot.records)
