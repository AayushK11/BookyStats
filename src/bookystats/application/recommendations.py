from __future__ import annotations

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisInput, AnalyticsReport
from bookystats.domain.recommendations import (
    RecommendationItem,
    RecommendationReport,
    RecommendationRepository,
    build_recommendations,
    recommendation_key,
)


def _bind(
    report: RecommendationReport, data: AnalysisInput, analysis: AnalyticsReport
) -> RecommendationReport:
    source_ids: dict[int, set[str]] = {}
    for book in data.books:
        source_ids.setdefault(book.work_id, set()).update(book.source_ids)
    updates: dict[str, object] = {
        S.REC_MANIFEST: data.manifest,
        S.REC_AS_OF: data.as_of,
        S.REC_ANALYSIS_REPORT_ID: analysis.report_id,
        S.REC_REPORT_ID: C.NONE,
        S.REC_REUSED: C.TRUE,
        S.REC_SNAPSHOT_IDS: tuple(snapshot.snapshot_id for snapshot in data.manifest.snapshots),
    }
    for field in C.REC_ITEM_FIELDS:
        items: tuple[RecommendationItem, ...] = getattr(report, field)
        updates[field] = tuple(
            item.model_copy(
                update={S.REC_SOURCE_IDS: tuple(sorted(source_ids.get(item.work_id, set())))}
            )
            for item in items
        )
    return report.model_copy(update=updates)


class RecommendationService:
    def __init__(self, repository: RecommendationRepository) -> None:
        self.repository = repository

    def run(self, data: AnalysisInput, analysis: AnalyticsReport) -> RecommendationReport:
        if data.manifest != analysis.manifest or (
            analysis.as_of is not C.NONE and data.as_of[: C.TEN] != analysis.as_of[: C.TEN]
        ):
            raise ValueError(S.REC_COMPATIBILITY_ERROR)
        cached = self.repository.get_cached(recommendation_key(data, analysis))
        report = (
            build_recommendations(data, analysis)
            if cached is C.NONE
            else _bind(cached, data, analysis)
        )
        return self.repository.publish(report)
