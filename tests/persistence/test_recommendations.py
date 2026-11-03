from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.recommendations import RecommendationService
from bookystats.domain.recommendations import build_recommendations
from bookystats.persistence.analytics import AnalyticsStore, AnalyticsStoreError
from bookystats.persistence.recommendations import RecommendationStore, RecommendationStoreError
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
