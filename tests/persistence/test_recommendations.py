from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.recommendations import RecommendationService
from bookystats.domain.recommendations import RecommendationReport, build_recommendations
from bookystats.persistence.analytics import AnalyticsStore, AnalyticsStoreError
from bookystats.persistence.recommendations import (
    RecommendationStore,
    RecommendationStoreError,
    _unbound,
)
from tests.domain.test_recommendations import analysis, candidate, data, history
from tests.persistence.test_analytics import _report, _tamper


def test_typed_historical_reports_share_analytics_database_and_keep_cache_immutable(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    pinned = data(*history(), candidate())
    with RecommendationStore(path) as store:
        first = store.publish(build_recommendations(pinned, analysis(pinned)))
        assert store.latest() == first
        changed_item = first.ranked[C.ZERO].model_copy(update={S.REC_RANKING_SCORE: C.TEN})
        collision = first.model_copy(update={S.REC_RANKED_FIELD: (changed_item,)})
        with pytest.raises(RecommendationStoreError):
            store.publish(collision)
        assert store.latest() == first
    with AnalyticsStore(path) as analytics:
        assert analytics.latest() is C.NONE
        saved = analytics.publish(_report())
        assert saved.report_id == C.ONE
    with RecommendationStore(path) as reopened:
        assert reopened.latest() == first
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(S.REC_TEST_COUNT).fetchone()[C.ZERO] == C.ONE
    finally:
        connection.close()


def test_failed_foreign_key_publish_rolls_back_cache_and_preserves_last_good(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    pinned = data(*history(), candidate())
    with RecommendationStore(path) as store:
        saved = store.publish(build_recommendations(pinned, analysis(pinned)))
        changed = data(*history(), candidate(C.FOUR))
        invalid = build_recommendations(changed, analysis(changed)).model_copy(
            update={S.REC_ANALYSIS_REPORT_ID: C.TEN}
        )
        with pytest.raises(RecommendationStoreError):
            store.publish(invalid)
        assert store.latest() == saved
        assert store.get_cached(invalid.key) is C.NONE


def test_analytics_version_change_preserves_historical_cache_and_publishes_separately(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    current = data(*history(), candidate())
    old = current.model_copy(
        update={
            S.REC_MANIFEST: current.manifest.model_copy(
                update={S.REC_CALCULATION_VERSION: S.REC_TEST_PREVIOUS_ANALYSIS_VERSION}
            )
        }
    )
    with RecommendationStore(path) as store:
        historical = store.publish(build_recommendations(old, analysis(old)))
        cached = store.get_cached(historical.key)
        assert cached is not C.NONE
        assert cached.manifest.calculation_version == old.manifest.calculation_version
        saved = store.publish(build_recommendations(current, analysis(current)))
        assert saved.key != historical.key
    with RecommendationStore(path) as reopened:
        assert reopened.latest() == saved
        assert reopened.get_cached(historical.key) == cached


def test_hash_corruption_is_detected_before_reuse(tmp_path: Path) -> None:
    path = tmp_path / S.AN_DATABASE
    pinned = data(*history(), candidate())
    with RecommendationStore(path) as store:
        service = RecommendationService(store)
        saved = service.run(pinned, analysis(pinned))
        _tamper(path, S.REC_TEST_CORRUPT, (S.REC_TEST_BAD_HASH, saved.key))
        with pytest.raises(RecommendationStoreError):
            service.run(pinned, analysis(pinned))
    with RecommendationStore(path) as store, pytest.raises(RecommendationStoreError):
        store.verify_history()


def test_legacy_v2_migration_preserves_exact_payloads_hashes_and_reports(tmp_path: Path) -> None:
    path = tmp_path / S.AN_DATABASE
    with AnalyticsStore(path) as store:
        saved = store.publish(_report())
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.execute(S.REC_DROP_REPORTS)
            connection.execute(S.REC_DROP_CACHE)
            connection.execute(S.REC_LEGACY_VERSION)
        components = connection.execute(S.REC_LEGACY_CONTENT).fetchall()
        reports = connection.execute(S.REC_LEGACY_REPORTS).fetchall()
    finally:
        connection.close()
    with AnalyticsStore(path) as store:
        assert store.latest() == saved
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(S.REC_LEGACY_CONTENT).fetchall() == components
        assert connection.execute(S.REC_LEGACY_REPORTS).fetchall() == reports
        assert connection.execute(S.AN_STORE_VERSION).fetchone()[C.ZERO] == C.REC_SCHEMA_VERSION
    finally:
        connection.close()


def test_legacy_unexpected_schema_is_rejected_without_migrating(tmp_path: Path) -> None:
    path = tmp_path / S.AN_DATABASE
    with AnalyticsStore(path):
        pass
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.execute(S.REC_DROP_REPORTS)
            connection.execute(S.REC_DROP_CACHE)
            connection.execute(S.REC_LEGACY_VERSION)
            connection.execute(S.AN_STORE_TEST_BAD_SCHEMA)
    finally:
        connection.close()
    with pytest.raises(AnalyticsStoreError):
        AnalyticsStore(path)
    connection = sqlite3.connect(path)
    try:
        assert (
            connection.execute(S.AN_STORE_VERSION).fetchone()[C.ZERO] == C.AN_STORE_SCHEMA_VERSION
        )
        assert not connection.execute(S.REC_SCHEMA).fetchall()
    finally:
        connection.close()


def test_v2_history_is_verified_without_rewriting_bytes_when_v3_is_published(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    pinned = data(*history(), candidate())
    old = build_recommendations(pinned, analysis(pinned)).model_copy(
        update={
            S.REC_POLICY: S.REC3_PREVIOUS_POLICY,
            S.REC_KEY: _digest(S.REC3_PREVIOUS_POLICY),
        }
    )
    old = RecommendationReport.model_validate_json(
        old.model_dump_json(exclude=C.REC3_OLD_REPORT_EXCLUDES)
    )
    cache_payload = _unbound(old).model_dump_json(exclude=C.REC3_OLD_REPORT_EXCLUDES)
    report_payload = old.model_dump_json(exclude=C.REC3_OLD_REPORT_EXCLUDES)
    with RecommendationStore(path):
        pass
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(S.REC_INSERT_CACHE, (old.key, cache_payload, _digest(cache_payload)))
        connection.execute(
            S.REC_INSERT_REPORT,
            (old.key, old.analysis_report_id, report_payload, _digest(report_payload)),
        )
        original = connection.execute(S.REC_ALL_REPORTS).fetchone()
    with RecommendationStore(path) as store:
        assert store.latest() == old.model_copy(update={S.REC_REPORT_ID: C.ONE})
        current = RecommendationService(store).run(pinned, analysis(pinned))
        assert current.policy_version == S.REC_POLICY_VERSION
        store.verify_history()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute(S.REC_ALL_REPORTS).fetchone() == original
        assert connection.execute(S.REC_GET_CACHE, (old.key,)).fetchone()[C.ONE] == cache_payload


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode(S.UTF_8)).hexdigest()


def _legacy_payload(report: RecommendationReport) -> str:
    document = report.model_dump(mode=S.JSON, exclude=C.REC3_V1_REPORT_EXCLUDES)
    return json.dumps(document, ensure_ascii=C.FALSE, separators=C.REC2_JSON_SEPARATORS)


def _seed_legacy_history(path: Path) -> tuple[RecommendationReport, str, str]:
    pinned = data(*history(), candidate())
    report = build_recommendations(pinned, analysis(pinned)).model_copy(
        update={
            S.REC_POLICY: S.REC2_LEGACY_POLICY,
            S.REC_KEY: _digest(S.REC2_TEST_LEGACY_KEY),
            S.REC2_EVALUATION: C.NONE,
        }
    )
    report = RecommendationReport.model_validate_json(_legacy_payload(report))
    cache_payload, report_payload = _legacy_payload(_unbound(report)), _legacy_payload(report)
    with RecommendationStore(path):
        pass
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(S.REC_INSERT_CACHE, (report.key, cache_payload, _digest(cache_payload)))
        connection.execute(
            S.REC_INSERT_REPORT,
            (report.key, report.analysis_report_id, report_payload, _digest(report_payload)),
        )
    return report.model_copy(update={S.REC_REPORT_ID: C.ONE}), cache_payload, report_payload


def test_v1_history_roundtrips_with_v2_without_changing_original_bytes_keys_or_hashes(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    historical, cache_payload, report_payload = _seed_legacy_history(path)
    with closing(sqlite3.connect(path)) as connection:
        original_cache = connection.execute(S.REC_GET_CACHE, (historical.key,)).fetchone()
        original_report = connection.execute(S.REC_ALL_REPORTS).fetchone()
    with RecommendationStore(path, read_only=C.TRUE) as store:
        assert store.latest() == historical
        cached = store.get_cached(historical.key)
        assert cached is not C.NONE
        assert cached.evaluation is C.NONE
        assert all(not item.series_context for item in cached.ranked)
        assert store.verify_history() == {
            S.DBSAFE_CHECKED_CACHE_ROWS: C.ONE,
            S.DBSAFE_CHECKED_RECOMMENDATIONS: C.ONE,
        }
    pinned = data(*history(), candidate())
    with RecommendationStore(path) as store:
        repeated = store.publish(historical)
        assert repeated.key == historical.key
        assert repeated.policy_version == S.REC2_LEGACY_POLICY
        assert repeated.report_id == C.TWO
        current = store.publish(build_recommendations(pinned, analysis(pinned)))
        assert current.key != historical.key
        assert current.evaluation is not C.NONE
        assert store.latest() == current
        assert store.verify_history() == {
            S.DBSAFE_CHECKED_CACHE_ROWS: C.TWO,
            S.DBSAFE_CHECKED_RECOMMENDATIONS: C.THREE,
        }
    with RecommendationStore(path, read_only=C.TRUE) as store:
        assert store.latest() == current
        assert store.get_cached(historical.key) == cached
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute(S.REC_GET_CACHE, (historical.key,)).fetchone() == original_cache
        assert original_report in connection.execute(S.REC_ALL_REPORTS).fetchall()
    assert original_cache[C.ONE :] == (cache_payload, _digest(cache_payload))
    assert original_report[C.THREE :] == (report_payload, _digest(report_payload))


@pytest.mark.parametrize(S.REC2_TEST_MUTATION, C.REC2_TEST_CORRUPTION_CASES)
def test_v1_cache_and_reports_reject_checksum_policy_or_noncanonical_changes(
    tmp_path: Path, mutation: str, report_row: bool
) -> None:
    path = tmp_path / S.AN_DATABASE
    historical, cache_payload, report_payload = _seed_legacy_history(path)
    original = report_payload if report_row else cache_payload
    payload = original
    if mutation in C.REC2_TEST_SPACE_MUTATIONS:
        payload += S.SPACE
    else:
        document = json.loads(payload)
        if mutation == S.REC2_TEST_UNKNOWN_POLICY:
            document[S.REC_POLICY] = S.REC2_TEST_UNSUPPORTED_POLICY
        elif mutation == S.REC2_TEST_EXTRA_EVALUATION:
            document[S.REC2_EVALUATION] = C.NONE
        else:
            document[S.REC_RANKED_FIELD][C.ZERO][S.REC2_SERIES_CONTEXT] = []
        payload = json.dumps(document, ensure_ascii=C.FALSE, separators=C.REC2_JSON_SEPARATORS)
    digest = _digest(original if mutation == S.REC2_TEST_BAD_CHECKSUM else payload)
    statement = S.REC2_TEST_UPDATE_REPORT if report_row else S.REC2_TEST_UPDATE_CACHE
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(statement, (payload, digest, historical.key))
    with RecommendationStore(path, read_only=C.TRUE) as store:
        if not report_row:
            with pytest.raises(RecommendationStoreError):
                store.get_cached(historical.key)
        with pytest.raises(RecommendationStoreError):
            store.latest()
        with pytest.raises(RecommendationStoreError):
            store.verify_history()
    with closing(sqlite3.connect(path)) as connection:
        rows = connection.execute(S.REC_ALL_REPORTS if report_row else S.REC_ALL_CACHE).fetchall()
    assert any(payload in row and digest in row for row in rows)


def test_v1_publication_cannot_silently_discard_new_evaluation_evidence(tmp_path: Path) -> None:
    path = tmp_path / S.AN_DATABASE
    pinned = data(*history(), candidate())
    current = build_recommendations(pinned, analysis(pinned))
    incompatible = current.model_copy(update={S.REC_POLICY: S.REC2_LEGACY_POLICY})
    with RecommendationStore(path) as store:
        with pytest.raises(RecommendationStoreError):
            store.publish(incompatible)
        assert store.latest() is C.NONE
        assert store.get_cached(current.key) is C.NONE


def test_v1_canonical_report_must_still_match_immutable_cached_recommendations(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.AN_DATABASE
    historical, _, report_payload = _seed_legacy_history(path)
    document = json.loads(report_payload)
    document[S.REC_RANKED_FIELD][C.ZERO][S.REC_RANKING_SCORE] = C.TEN
    changed = json.dumps(document, ensure_ascii=C.FALSE, separators=C.REC2_JSON_SEPARATORS)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(S.REC2_TEST_UPDATE_REPORT, (changed, _digest(changed), historical.key))
    with RecommendationStore(path, read_only=C.TRUE) as store:
        assert store.get_cached(historical.key) is not C.NONE
        with pytest.raises(RecommendationStoreError):
            store.latest()
        with pytest.raises(RecommendationStoreError):
            store.verify_history()
