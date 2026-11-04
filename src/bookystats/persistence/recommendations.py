from __future__ import annotations

import hashlib
import hmac
import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalyticsSettings
from bookystats.domain.errors import BookyError
from bookystats.domain.recommendations import RecommendationItem, RecommendationReport
from bookystats.persistence.analytics import AnalyticsStore, AnalyticsStoreError
from bookystats.persistence.inspection import open_read_only


class RecommendationStoreError(BookyError):
    pass


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode(S.UTF_8)).hexdigest()


def _key(value: object) -> str:
    if not isinstance(value, str) or C.AN_STORE_KEY_PATTERN.fullmatch(value) is C.NONE:
        raise RecommendationStoreError(S.REC_STORE_ERROR)
    return value


def _unbound(report: RecommendationReport) -> RecommendationReport:
    manifest = report.manifest.model_copy(
        update={
            S.REC_SNAPSHOTS: (),
            S.METADATA: (),
            S.REC_SETTINGS_HASH: S.EMPTY,
            S.REC_ANALYTICS_SETTINGS: AnalyticsSettings(),
        }
    )
    updates: dict[str, object] = {
        S.REC_REPORT_ID: C.NONE,
        S.REC_MANIFEST: manifest,
        S.REC_ANALYSIS_REPORT_ID: C.NONE,
        S.REC_REUSED: C.FALSE,
        S.REC_SNAPSHOT_IDS: (),
        S.REC_AS_OF: report.as_of[: C.TEN],
    }
    for field in C.REC_ITEM_FIELDS:
        items: tuple[RecommendationItem, ...] = getattr(report, field)
        updates[field] = tuple(item.model_copy(update={S.REC_SOURCE_IDS: ()}) for item in items)
    return report.model_copy(update=updates)


def _payload(report: RecommendationReport) -> str:
    if report.policy_version not in C.REC2_SUPPORTED_POLICIES:
        raise RecommendationStoreError(S.REC_STORE_ERROR)
    if report.policy_version != S.REC_POLICY_VERSION and (
        report.learning is not C.NONE
        or report.ranking_evaluation is not C.NONE
        or any(
            item.semantic_neighbors
            or item.description_excerpt is not C.NONE
            or item.description_url is not C.NONE
            or item.shortlist_note is not C.NONE
            or item.ranking_method != S.REC3_CURRENT
            for field in C.REC_ITEM_FIELDS
            for item in getattr(report, field)
        )
    ):
        raise RecommendationStoreError(S.REC_STORE_ERROR)
    if report.policy_version == S.REC2_LEGACY_POLICY:
        if report.evaluation is not C.NONE or any(
            item.series_context for field in C.REC_ITEM_FIELDS for item in getattr(report, field)
        ):
            raise RecommendationStoreError(S.REC_STORE_ERROR)
        return report.model_dump_json(exclude=C.REC3_V1_REPORT_EXCLUDES, warnings=S.ERROR)
    if report.policy_version == S.REC3_PREVIOUS_POLICY:
        return report.model_dump_json(exclude=C.REC3_OLD_REPORT_EXCLUDES, warnings=S.ERROR)
    if (
        report.ranking_evaluation is not C.NONE
        and report.ranking_evaluation.version == S.REC3_PREVIOUS_RANKING_VERSION
    ):
        if (
            report.ranking_evaluation.length is not C.NONE
            or report.ranking_evaluation.candidate_vs_length is not C.NONE
            or any(fold.length is not C.NONE for fold in report.ranking_evaluation.folds)
        ):
            raise RecommendationStoreError(S.REC_STORE_ERROR)
        return report.model_dump_json(exclude=C.REC3_RANKING_V1_REPORT_EXCLUDES, warnings=S.ERROR)
    return report.model_dump_json(exclude=C.REC_REPORT_EXCLUDES, warnings=S.ERROR)


def _decode(key: object, payload: object, digest: object) -> RecommendationReport:
    try:
        if not isinstance(payload, str) or not hmac.compare_digest(_hash(payload), _key(digest)):
            raise RecommendationStoreError(S.REC_STORE_ERROR)
        report = RecommendationReport.model_validate_json(payload)
        if report.key != _key(key) or report.policy_version not in C.REC2_SUPPORTED_POLICIES:
            raise RecommendationStoreError(S.REC_STORE_ERROR)
        if _payload(report) != payload:
            raise RecommendationStoreError(S.REC_STORE_ERROR)
        return report
    except (ValueError, TypeError, RecursionError):
        raise RecommendationStoreError(S.REC_STORE_ERROR) from C.NONE


class RecommendationStore:
    def __init__(self, path: Path, *, read_only: bool = C.FALSE) -> None:
        self._connection: sqlite3.Connection | None = C.NONE
        self.upgrade_pending = C.FALSE
        try:
            # AnalyticsStore creates or upgrades the shared schema and validates its identity,
            # exact tables, integrity and foreign keys; saved reports are verified when read.
            with AnalyticsStore(path, require_existing=read_only, read_only=read_only) as store:
                self.upgrade_pending = store.upgrade_pending
            if read_only:
                self._connection = open_read_only(path).connection
            else:
                self._connection = sqlite3.connect(path, timeout=C.FIVE)
                self._db().execute(S.AN_STORE_FOREIGN_KEYS)
        except (OSError, sqlite3.Error, ValueError, RecommendationStoreError, AnalyticsStoreError):
            self.close()
            raise RecommendationStoreError(S.REC_STORE_ERROR) from C.NONE

    def verify_history(self) -> dict[str, int]:
        checked = {S.DBSAFE_CHECKED_CACHE_ROWS: C.ZERO, S.DBSAFE_CHECKED_RECOMMENDATIONS: C.ZERO}
        if self.upgrade_pending:
            return checked
        try:
            connection = self._db()
            for row in connection.execute(S.REC_ALL_CACHE):
                report = _decode(*row)
                if _payload(_unbound(report)) != row[C.ONE]:
                    raise RecommendationStoreError(S.REC_STORE_ERROR)
                checked[S.DBSAFE_CHECKED_CACHE_ROWS] += C.ONE
            for row in connection.execute(S.REC_ALL_REPORTS):
                self._report(row)
                checked[S.DBSAFE_CHECKED_RECOMMENDATIONS] += C.ONE
        except (sqlite3.Error, UnicodeError):
            raise RecommendationStoreError(S.REC_STORE_ERROR) from C.NONE
        return checked

    def _db(self) -> sqlite3.Connection:
        if self._connection is C.NONE:
            raise RecommendationStoreError(S.REC_STORE_CLOSED)
        return self._connection

    def get_cached(self, key: str) -> RecommendationReport | None:
        try:
            row = self._db().execute(S.REC_GET_CACHE, (_key(key),)).fetchone()
            report = C.NONE if row is C.NONE else _decode(*row)
            if report is not C.NONE and _payload(_unbound(report)) != row[C.ONE]:
                raise RecommendationStoreError(S.REC_STORE_ERROR)
            return report
        except (sqlite3.Error, UnicodeError):
            raise RecommendationStoreError(S.REC_STORE_ERROR) from C.NONE

    def publish(self, report: RecommendationReport) -> RecommendationReport:
        try:
            report = RecommendationReport.model_validate_json(
                report.model_dump_json(warnings=S.ERROR)
            )
            key = _key(report.key)
            cached = _unbound(report)
            cache_payload = _payload(cached)
            payload = _payload(report)
            _decode(key, cache_payload, _hash(cache_payload))
            connection = self._db()
            with connection:
                connection.execute(S.AN_STORE_BEGIN)
                existing = self.get_cached(key)
                if existing is C.NONE:
                    connection.execute(
                        S.REC_INSERT_CACHE, (key, cache_payload, _hash(cache_payload))
                    )
                elif _payload(existing) != cache_payload:
                    raise RecommendationStoreError(S.REC_STORE_ERROR)
                cursor = connection.execute(
                    S.REC_INSERT_REPORT, (key, report.analysis_report_id, payload, _hash(payload))
                )
                report_id = cursor.lastrowid
                if report_id is C.NONE:
                    raise RecommendationStoreError(S.REC_STORE_ERROR)
            return report.model_copy(update={S.REC_REPORT_ID: report_id})
        except (ValueError, TypeError, AttributeError, RecursionError, sqlite3.Error):
            raise RecommendationStoreError(S.REC_STORE_ERROR) from C.NONE

    def _report(self, row: tuple[object, ...]) -> RecommendationReport:
        report_id, key, analysis_id, payload, digest = row
        report = _decode(key, payload, digest)
        cached = self.get_cached(_key(key))
        if (
            type(report_id) is not int
            or report_id < C.ONE
            or report.analysis_report_id != analysis_id
            or cached is C.NONE
            or _payload(cached) != _payload(_unbound(report))
        ):
            raise RecommendationStoreError(S.REC_STORE_ERROR)
        return report.model_copy(update={S.REC_REPORT_ID: report_id})

    def latest(self) -> RecommendationReport | None:
        try:
            row = self._db().execute(S.REC_LATEST).fetchone()
            return C.NONE if row is C.NONE else self._report(row)
        except (sqlite3.Error, UnicodeError):
            raise RecommendationStoreError(S.REC_STORE_ERROR) from C.NONE

    def close(self) -> None:
        if self._connection is not C.NONE:
            connection, self._connection = self._connection, C.NONE
            connection.close()

    def __enter__(self) -> Self:
        self._db()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
