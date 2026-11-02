from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import (
    AnalysisComponent,
    AnalysisManifest,
    AnalysisMetadata,
    AnalysisSnapshot,
    AnalyticsReport,
    Capability,
    Finding,
)
from bookystats.domain.models import Issue
from bookystats.persistence.analytics import AnalyticsStore, AnalyticsStoreError


def _component(
    kind: C.AnalyticsComponentKind = C.AnalyticsComponentKind.TASTE,
    key: str = C.AN_STORE_TEST_KEYS[C.ZERO],
) -> AnalysisComponent:
    return AnalysisComponent(
        key=key,
        kind=kind,
        findings=(
            Finding(
                metric_id=S.AN_STORE_TEST_METRIC,
                population=S.AN_STORE_TEST_LABEL,
                value=C.TWO,
                unit=S.AN_STORE_TEST_UNIT,
                sample_size=C.THREE,
                missing_count=C.ONE,
                reliability=S.AN_STORE_TEST_RELIABILITY,
                uncertainty={S.AN_STORE_TEST_LABEL: C.NONE},
                source_snapshot_ids=(),
            ),
        ),
        capabilities=(
            Capability(
                metric_id=S.AN_STORE_TEST_METRIC,
                state=C.AnalyticsCapability.SUBSET,
                available=C.TWO,
                population=C.THREE,
                reason=S.AN_STORE_TEST_LABEL,
            ),
        ),
        preferences={S.AN_WONDER: C.ONE},
    )


def _report() -> AnalyticsReport:
    return AnalyticsReport(
        created_at=S.AN_STORE_TEST_TIME,
        manifest=AnalysisManifest(
            account_fingerprint=S.AN_STORE_TEST_ACCOUNT,
            settings_hash=S.AN_STORE_TEST_SETTINGS,
            snapshots=(
                AnalysisSnapshot(
                    source=C.Source.GOODREADS,
                    account_id=S.AN_STORE_TEST_ACCOUNT_ID,
                    collection=S.TO_READ,
                    snapshot_id=C.ONE,
                    raw_document_id=S.AN_STORE_TEST_RAW,
                    processing_version=S.AN_CALCULATION_VERSION,
                    input_kind=S.INPUT_FILE,
                    finished_at=S.AN_STORE_TEST_TIME,
                    records=C.THREE,
                    attempt_state=C.SyncState.COMPLETE,
                ),
            ),
            metadata=(
                AnalysisMetadata(
                    source_id=S.AN_STORE_TEST_LABEL,
                    provider=C.Source.GOOGLE_BOOKS,
                    attempt_id=C.ONE,
                    candidate_id=C.TWO,
                    checked_at=S.AN_STORE_TEST_TIME,
                    payload_hash=C.AN_STORE_TEST_KEYS[C.TWO],
                ),
            ),
        ),
        taste=_component(),
        watchlist=_component(C.AnalyticsComponentKind.WATCHLIST, C.AN_STORE_TEST_KEYS[C.ONE]),
        issues=(Issue(code=S.AN_STORE_TEST_LABEL, message=S.AN_STORE_TEST_LABEL),),
    )


def _tamper(path: Path, statement: str, values: tuple[object, ...] = ()) -> None:
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.execute(statement, values)
    finally:
        connection.close()


def _counts(path: Path) -> tuple[int, int]:
    connection = sqlite3.connect(path)
    try:
        return (
            connection.execute(S.AN_STORE_TEST_COMPONENT_COUNT).fetchone()[C.ZERO],
            connection.execute(S.AN_STORE_TEST_REPORT_COUNT).fetchone()[C.ZERO],
        )
    finally:
        connection.close()


def _payload(component: AnalysisComponent) -> tuple[str, str]:
    text = json.dumps(
        component.model_dump(mode=S.JSON),
        sort_keys=C.TRUE,
        ensure_ascii=C.TRUE,
        separators=(S.COMMA, S.COLON),
        allow_nan=C.FALSE,
    )
    return text, hashlib.sha256(text.encode(S.UTF_8)).hexdigest()


def test_components_roundtrip_and_kinds_have_distinct_immutable_keys(tmp_path: Path) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    report = _report()
    with AnalyticsStore(path) as store:
        assert store.latest() is C.NONE
        assert store.get_component(report.taste.key) is C.NONE
        store.save_component(report.taste)
        store.save_component(report.watchlist)
        store.save_component(report.taste)
        assert store.get_component(report.taste.key) == report.taste
        assert store.get_component(report.watchlist.key) == report.watchlist
        with pytest.raises(AnalyticsStoreError):
            store.save_component(
                report.watchlist.model_copy(
                    update={S.AN_STORE_TEST_COMPONENT_KEY: report.taste.key}
                )
            )
        with pytest.raises(AnalyticsStoreError):
            store.get_component(S.AN_STORE_TEST_BAD_KEY)
    with AnalyticsStore(path) as reopened:
        assert reopened.get_component(report.taste.key) == report.taste
    assert _counts(path) == (C.TWO, C.ZERO)


def test_publication_keeps_exact_manifest_and_allocates_ids_without_payload_duplication(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    report = _report()
    with AnalyticsStore(path) as store:
        first = store.publish(report)
        assert first.report_id == C.ONE
        assert first.manifest == report.manifest
        assert first.created_at == report.created_at
        assert report.report_id is C.NONE
        replay = report.model_copy(
            update={
                S.AN_STORE_REPORT_ID: C.ONE,
                S.AN_STORE_TEST_REUSED: C.TRUE,
            }
        )
        second = store.publish(replay)
        assert second.report_id == C.TWO
        assert second.taste_reused
        assert store.latest() == second
    assert _counts(path) == (C.TWO, C.TWO)
    with AnalyticsStore(path) as store:
        assert store.latest() == second
        assert store.publish(report).report_id == C.THREE


def test_unbound_cache_is_immutable_while_reports_rebind_current_snapshot_provenance(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    unbound = _report()

    def bind(snapshot_id: int) -> AnalyticsReport:
        def component(value: AnalysisComponent) -> AnalysisComponent:
            return value.model_copy(
                update={
                    S.AN_STORE_FINDINGS: tuple(
                        finding.model_copy(update={S.AN_STORE_SNAPSHOT_IDS: (snapshot_id,)})
                        for finding in value.findings
                    )
                }
            )

        return unbound.model_copy(
            update={
                S.AN_STORE_TASTE: component(unbound.taste),
                S.AN_STORE_WATCHLIST: component(unbound.watchlist),
                S.AN_STORE_TEST_MANIFEST: unbound.manifest.model_copy(
                    update={
                        S.AN_STORE_TEST_SNAPSHOTS: tuple(
                            snapshot.model_copy(update={S.AN_STORE_TEST_SNAPSHOT_ID: snapshot_id})
                            for snapshot in unbound.manifest.snapshots
                        )
                    }
                ),
            }
        )

    first_input = bind(C.ONE)
    second_input = bind(C.TWO)
    with AnalyticsStore(path) as store:
        store.save_component(unbound.taste)
        store.save_component(unbound.watchlist)
        first = store.publish(first_input)
        assert store.latest() == first
        assert first == first_input.model_copy(update={S.AN_STORE_REPORT_ID: C.ONE})
        second = store.publish(second_input)
        assert second == second_input.model_copy(update={S.AN_STORE_REPORT_ID: C.TWO})
        assert store.latest() == second
        assert store.get_component(unbound.taste.key) == unbound.taste
        assert store.get_component(unbound.watchlist.key) == unbound.watchlist
    with AnalyticsStore(path) as reopened:
        assert reopened.latest() == second
        assert reopened.get_component(unbound.taste.key) == unbound.taste
    connection = sqlite3.connect(path)
    try:
        documents = [
            json.loads(row[C.THREE])
            for row in connection.execute(S.AN_STORE_TEST_ORDERED_REPORTS).fetchall()
        ]
    finally:
        connection.close()
    for document, snapshot_id in zip(documents, (C.ONE, C.TWO), strict=C.TRUE):
        assert document[S.AN_STORE_TASTE][S.AN_STORE_SNAPSHOT_IDS] == [[snapshot_id]]
        assert document[S.AN_STORE_WATCHLIST][S.AN_STORE_SNAPSHOT_IDS] == [[snapshot_id]]
        assert (
            document[S.AN_STORE_TEST_MANIFEST][S.AN_STORE_TEST_SNAPSHOTS][C.ZERO][
                S.AN_STORE_TEST_SNAPSHOT_ID
            ]
            == snapshot_id
        )
    assert _counts(path) == (C.TWO, C.TWO)


def test_failed_publish_rolls_back_new_components_and_preserves_latest(tmp_path: Path) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    report = _report()
    with AnalyticsStore(path) as store:
        saved = store.publish(report)
        changed = report.model_copy(
            update={
                S.AN_STORE_TASTE: _component(key=C.AN_STORE_TEST_KEYS[C.TWO]),
                S.AN_STORE_WATCHLIST: report.watchlist.model_copy(
                    update={S.AN_STORE_TEST_PREFERENCES: {S.AN_WONDER: C.ZERO}}
                ),
            }
        )
        with pytest.raises(AnalyticsStoreError, match=S.AN_STORE_COLLISION):
            store.publish(changed)
        assert store.latest() == saved
        assert store.get_component(C.AN_STORE_TEST_KEYS[C.TWO]) is C.NONE
        assert _counts(path) == (C.TWO, C.ONE)
        _tamper(path, S.AN_STORE_TEST_FAIL_INSERT)
        with pytest.raises(AnalyticsStoreError):
            store.publish(
                report.model_copy(
                    update={S.AN_STORE_TASTE: _component(key=C.AN_STORE_TEST_KEYS[C.TWO])}
                )
            )
        assert store.latest() == saved
        assert _counts(path) == (C.TWO, C.ONE)


def test_invalid_component_bindings_and_calculation_version_fail_before_publication(
    tmp_path: Path,
) -> None:
    report = _report()
    with AnalyticsStore(tmp_path / S.AN_STORE_TEST_FILENAME) as store:
        saved = store.publish(report)
        wrong_kind = report.model_copy(update={S.AN_STORE_TASTE: report.watchlist})
        with pytest.raises(AnalyticsStoreError):
            store.publish(wrong_kind)
        bad_version = report.model_copy(
            update={
                S.AN_STORE_TEST_MANIFEST: report.manifest.model_copy(
                    update={S.AN_STORE_TEST_VERSION: S.AN_STORE_TEST_LABEL}
                )
            }
        )
        with pytest.raises(AnalyticsStoreError):
            store.publish(bad_version)
        bad_payload = report.taste.model_copy(
            update={S.AN_STORE_TEST_PREFERENCES: {S.AN_WONDER: S.AN_STORE_TEST_LABEL}}
        )
        with pytest.raises(AnalyticsStoreError):
            store.save_component(bad_payload)
        with pytest.raises(AnalyticsStoreError):
            store.publish(report.model_copy(update={S.AN_STORE_TASTE: bad_payload}))
        assert store.latest() == saved


@pytest.mark.parametrize(S.AN_STORE_TEST_CORRUPTION_PARAMETER, C.AN_STORE_TEST_CORRUPTIONS)
def test_schema_identity_and_future_versions_are_rejected(tmp_path: Path, statement: str) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    with AnalyticsStore(path) as store:
        store.publish(_report())
    _tamper(path, statement)
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)


def test_unrecognized_database_and_non_sqlite_file_are_not_replaced(tmp_path: Path) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    _tamper(path, S.AN_STORE_TEST_BAD_SCHEMA)
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)
    path.unlink()
    path.write_bytes(S.AN_STORE_TEST_CORRUPT_BYTES)
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)
    assert path.read_bytes() == S.AN_STORE_TEST_CORRUPT_BYTES


def test_damaged_hash_and_internally_mismatched_component_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    report = _report()
    with AnalyticsStore(path) as store:
        store.publish(report)
        _tamper(path, S.AN_STORE_TEST_BAD_HASH, (C.AN_STORE_TEST_KEYS[C.TWO],))
        with pytest.raises(AnalyticsStoreError):
            store.get_component(report.taste.key)
        with pytest.raises(AnalyticsStoreError):
            store.latest()
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)
    text, digest = _payload(_component(key=C.AN_STORE_TEST_KEYS[C.TWO]))
    _tamper(path, S.AN_STORE_TEST_BAD_PAYLOAD, (text, digest, report.taste.key))
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)


def test_report_hash_bindings_and_foreign_keys_are_verified(tmp_path: Path) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    report = _report()
    with AnalyticsStore(path) as store:
        store.publish(report)
        _tamper(path, S.AN_STORE_TEST_BAD_BINDING)
        with pytest.raises(AnalyticsStoreError):
            store.latest()
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)
    _tamper(path, S.AN_STORE_TEST_BAD_FK, (C.AN_STORE_TEST_KEYS[C.TWO],))
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)


def test_report_hash_and_typed_payload_are_verified_even_when_hash_is_recomputed(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_STORE_TEST_FILENAME
    with AnalyticsStore(path) as store:
        store.publish(_report())
        _tamper(path, S.AN_STORE_TEST_BAD_REPORT_HASH, (C.AN_STORE_TEST_KEYS[C.TWO],))
        with pytest.raises(AnalyticsStoreError):
            store.latest()
        connection = sqlite3.connect(path)
        try:
            data = json.loads(connection.execute(S.AN_STORE_TEST_GET_REPORT).fetchone()[C.ZERO])
        finally:
            connection.close()
        data[S.AN_STORE_TEST_REUSED] = S.AN_STORE_TEST_LABEL
        text = json.dumps(
            data,
            sort_keys=C.TRUE,
            ensure_ascii=C.TRUE,
            separators=(S.COMMA, S.COLON),
        )
        digest = hashlib.sha256(text.encode(S.UTF_8)).hexdigest()
        _tamper(path, S.AN_STORE_TEST_TAMPER_REPORT, (text, digest))
        with pytest.raises(AnalyticsStoreError):
            store.latest()
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)


def test_closed_store_never_reopens_and_first_use_creates_parent_directories(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_STORE_TEST_LABEL / S.AN_STORE_TEST_FILENAME
    assert not path.parent.exists()
    store = AnalyticsStore(path)
    assert path.exists()
    store.close()
    store.close()
    with pytest.raises(AnalyticsStoreError, match=S.AN_STORE_CLOSED):
        store.latest()
    with pytest.raises(AnalyticsStoreError, match=S.AN_STORE_CLOSED):
        store.get_component(C.AN_STORE_TEST_KEYS[C.ZERO])
    with pytest.raises(AnalyticsStoreError, match=S.AN_STORE_CLOSED):
        store.save_component(_component())
    with pytest.raises(AnalyticsStoreError, match=S.AN_STORE_CLOSED):
        store.publish(_report())
