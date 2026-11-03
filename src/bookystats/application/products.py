from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.metadata_quality import build_metadata_quality
from bookystats.application.reader_report import build_reader_report
from bookystats.domain.analytics import (
    AnalysisInput,
    AnalyticsReceipt,
    AnalyticsReport,
    AnalyticsSettings,
)
from bookystats.domain.errors import BookyError
from bookystats.domain.interfaces import (
    AnalyticsInputReader,
    AnalyticsReportReader,
    ReportBundleRepository,
)
from bookystats.domain.metadata_quality import MetadataQualityReport
from bookystats.domain.models import Account, SyncState
from bookystats.domain.products import ProductReceipt
from bookystats.domain.recommendations import RecommendationReport


class ProductGenerationError(BookyError):
    pass


class ProductsService:
    def __init__(
        self,
        reader: AnalyticsInputReader,
        analyses: AnalyticsReportReader,
        bundles: ReportBundleRepository,
        *,
        recommend: Callable[[AnalysisInput, AnalyticsReport], RecommendationReport],
        provider_status: Callable[[], Mapping[str, JsonValue]],
        render_pdf: Callable[
            [AnalysisInput, AnalyticsReport, RecommendationReport, MetadataQualityReport, Path],
            object,
        ],
    ) -> None:
        self.reader = reader
        self.analyses = analyses
        self.bundles = bundles
        self.recommend = recommend
        self.provider_status = provider_status
        self.render_pdf = render_pdf

    def run(
        self,
        accounts: tuple[Account, ...],
        settings: AnalyticsSettings,
        analytics: AnalyticsReceipt,
    ) -> ProductReceipt:
        analysis = self.analyses.latest()
        if (
            analytics.state != SyncState.COMPLETE
            or analysis is C.NONE
            or analysis.report_id is C.NONE
            or analytics.report_id != analysis.report_id
            or analysis.as_of is C.NONE
        ):
            raise ProductGenerationError(S.PROD_INPUT_MISMATCH)
        data = self.reader.analytics_input(accounts, settings)
        if data.manifest != analysis.manifest:
            raise ProductGenerationError(S.PROD_INPUT_MISMATCH)
        data = data.model_copy(update={S.AN_CALC_AS_OF_FIELD: analysis.as_of})
        existing = self.bundles.for_report(analysis, layout_version=C.RPT_LAYOUT_VERSION)
        if existing is not C.NONE:
            return existing
        recommendations = self.recommend(data, analysis)
        if (
            recommendations.manifest != analysis.manifest
            or recommendations.as_of != analysis.as_of
            or recommendations.analysis_report_id != analysis.report_id
        ):
            raise ProductGenerationError(S.PROD_INPUT_MISMATCH)
        quality = build_metadata_quality(data, analysis, self.provider_status())
        reader_report = build_reader_report(data, analysis, recommendations, quality)
        summary = ProductReceipt(
            state=SyncState.COMPLETE,
            analytics_report_id=analysis.report_id,
            ranked=len(recommendations.ranked),
            shortlisted=len(recommendations.shortlist),
            unrankable=len(recommendations.unrankable),
            excluded=len(recommendations.excluded),
            recommendations_reused=recommendations.reused,
        )
        return self.bundles.publish(
            analysis,
            recommendations=recommendations.model_dump_json(indent=C.TWO),
            metadata_quality=quality.model_dump_json(indent=C.TWO),
            summary=summary,
            render_pdf=lambda path: self.render_pdf(data, analysis, recommendations, quality, path),
            reader_report=reader_report.model_dump_json(indent=C.TWO),
            layout_version=C.RPT_LAYOUT_VERSION,
        )
