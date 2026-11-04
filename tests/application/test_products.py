from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.analytics import AnalyticsService
from bookystats.application.products import ProductGenerationError, ProductsService
from bookystats.application.recommendations import RecommendationService
from bookystats.application.reporting import render_library_report
from bookystats.application.sync import SyncService
from bookystats.domain.analytics import (
    AnalysisInput,
    AnalyticsReceipt,
    AnalyticsReport,
    AnalyticsSettings,
)
from bookystats.domain.metadata_quality import MetadataQualityReport
from bookystats.domain.models import Account, ReadingStatus, SyncState
from bookystats.domain.products import ProductReceipt
from bookystats.domain.reader_report import ReaderReport, manifest_digest
from bookystats.domain.recommendations import RecommendationReport
from bookystats.persistence.analytics import AnalyticsStore
from bookystats.persistence.products import ReportBundleStore
from bookystats.persistence.recommendations import RecommendationStore
from bookystats.runtime.config import MetadataSettings, Settings
from tests.application.test_analytics import _InputReader
from tests.application.test_statistics import _book, _data
from tests.support.reader_library import library
from tests.support.sources import FixtureConnector, MemoryStorage, accounts, complete_snapshot


def test_products_share_pinned_input_and_reuse_verified_published_bundle(tmp_path: Path) -> None:
    data = _data(
        _book(C.ONE, C.FOUR).model_copy(update={S.COLLECTIONS: (S.READ,)}),
        _book(C.TWO, status=ReadingStatus.TO_READ).model_copy(update={S.COLLECTIONS: (S.TO_READ,)}),
    )
    reader = _InputReader(data)
    rendered: list[AnalysisInput] = []

    def render(
        current: AnalysisInput,
        analysis: AnalyticsReport,
        recommendations: RecommendationReport,
        quality: MetadataQualityReport,
        destination: Path,
    ) -> None:
        assert current.manifest == analysis.manifest == recommendations.manifest == quality.manifest
        assert current.as_of == analysis.as_of == recommendations.as_of == quality.as_of
        assert (
            analysis.report_id == recommendations.analysis_report_id == quality.analysis_report_id
        )
        rendered.append(current)
        destination.write_bytes(S.PROD_TEST_PDF)

    path = tmp_path / S.AN_DATABASE
    with AnalyticsStore(path) as analyses, RecommendationStore(path) as recommendations:
        analytics = AnalyticsService(reader, analyses).run((), AnalyticsSettings())
        saved = analyses.latest()
        assert saved is not C.NONE
        reader.data = data.model_copy(update={S.AN_CALC_AS_OF_FIELD: S.AN_CALC_TEST_FINISH})
        products = ProductsService(
            reader,
            analyses,
            ReportBundleStore(tmp_path),
            recommend=RecommendationService(recommendations).run,
            provider_status=dict,
            render_pdf=render,
        )
        result = products.run((), AnalyticsSettings(), analytics)
        assert result.state == SyncState.COMPLETE
        assert result.ranked + result.unrankable + result.excluded == C.ONE
        assert len(rendered) == C.ONE
        assert rendered[C.ZERO].as_of == saved.as_of
        first_recommendations = recommendations.latest()
        assert first_recommendations is not C.NONE
        assert products.run((), AnalyticsSettings(), analytics) == result
        assert len(rendered) == C.ONE
        assert recommendations.latest() == first_recommendations
        reader.data = reader.data.model_copy(
            update={
                S.AN_CALC_TEST_MANIFEST_FIELD: data.manifest.model_copy(
                    update={S.AN_ACCOUNT_FINGERPRINT: S.DIFFERENT_BOOK}
                )
            }
        )
        with pytest.raises(ProductGenerationError, match=S.PROD_INPUT_MISMATCH):
            products.run((), AnalyticsSettings(), analytics)
        assert ReportBundleStore(tmp_path).latest(current=saved) == result
        assert len(rendered) == C.ONE


def test_layout_bundle_is_published_beside_legacy_bundle_and_reused(tmp_path: Path) -> None:
    lib = library(*C.RPT_TEST_SMALL)
    reader = _InputReader(lib.data)
    renders: list[Path] = []

    def render(
        current: AnalysisInput,
        analysis: AnalyticsReport,
        recommendations: RecommendationReport,
        quality: MetadataQualityReport,
        destination: Path,
    ) -> object:
        renders.append(destination)
        return render_library_report(current, analysis, recommendations, quality, destination)

    store = ReportBundleStore(tmp_path)
    path = tmp_path / S.AN_DATABASE
    with AnalyticsStore(path) as analyses, RecommendationStore(path) as recommendations:
        analytics = AnalyticsService(reader, analyses).run((), AnalyticsSettings())
        saved = analyses.latest()
        assert saved is not C.NONE
        legacy = store.publish(
            saved,
            recommendations=S.PROD_TEST_JSON,
            metadata_quality=S.PROD_TEST_JSON,
            summary=ProductReceipt(state=SyncState.COMPLETE, analytics_report_id=saved.report_id),
            render_pdf=lambda target: target.write_bytes(S.PROD_TEST_PDF),
        )
        products = ProductsService(
            reader,
            analyses,
            store,
            recommend=RecommendationService(recommendations).run,
            provider_status=dict,
            render_pdf=render,
        )
        result = products.run((), AnalyticsSettings(), analytics)
        assert result.output_directory is not C.NONE
        assert result.pdf_file is not C.NONE
        assert result.output_directory != legacy.output_directory
        assert len(renders) == C.ONE
        assert store.latest() == result
        typed = ReaderReport.model_validate_json(
            (Path(result.output_directory) / S.RPT_BUNDLE_FILE).read_bytes()
        )
        assert typed.analysis_report_id == saved.report_id
        assert typed.manifest_digest == manifest_digest(saved.manifest)
        details = S.RPT_DETAILS.format(
            model=typed.model_version,
            layout=C.RPT_LAYOUT_VERSION,
            report=saved.report_id,
            digest=typed.manifest_digest[: C.RPT_DIGEST_SHOWN],
        )
        printed = S.EMPTY.join(
            S.EMPTY.join(page.extract_text().split()) for page in PdfReader(result.pdf_file).pages
        )
        assert S.EMPTY.join(typed.cover.title.split()) in printed
        assert S.EMPTY.join(details.split()) not in printed
        assert products.run((), AnalyticsSettings(), analytics) == result
        assert len(renders) == C.ONE
        assert store.for_report(saved) == legacy


def test_stale_analytics_receipt_cannot_publish_newer_report(tmp_path: Path) -> None:
    reader = _InputReader(_data(_book(C.ONE, C.FOUR)))
    path = tmp_path / S.AN_DATABASE
    with AnalyticsStore(path) as analyses, RecommendationStore(path) as recommendations:
        service = AnalyticsService(reader, analyses)
        stale = service.run((), AnalyticsSettings())
        service.run((), AnalyticsSettings())

        def unexpected_render(
            data: AnalysisInput,
            analysis: AnalyticsReport,
            recommendation: RecommendationReport,
            quality: MetadataQualityReport,
            destination: Path,
        ) -> None:
            pytest.fail(S.PROD_TEST_FAILURE)

        products = ProductsService(
            reader,
            analyses,
            ReportBundleStore(tmp_path),
            recommend=RecommendationService(recommendations).run,
            provider_status=dict,
            render_pdf=unexpected_render,
        )
        with pytest.raises(ProductGenerationError, match=S.PROD_INPUT_MISMATCH):
            products.run((), AnalyticsSettings(), stale)
        assert recommendations.latest() is C.NONE
        assert not (tmp_path / S.PROD_REPORTS_FOLDER).exists()


@pytest.mark.parametrize(S.PROD_TEST_SOURCE_FAILURE, C.PROD_TEST_SOURCE_FAILURES)
def test_sync_skips_delivery_on_source_failure_and_reports_output_failure(
    source_failure: bool,
) -> None:
    calls: list[str] = []
    events: list[str] = []

    class Analyses:
        def run(
            self, configured: tuple[Account, ...], settings: AnalyticsSettings
        ) -> AnalyticsReceipt:
            calls.append(S.PROD_ANALYTICS_STAGE)
            return AnalyticsReceipt(state=SyncState.COMPLETE, report_id=C.ONE)

    class Products:
        def run(
            self,
            configured: tuple[Account, ...],
            settings: AnalyticsSettings,
            analytics: AnalyticsReceipt,
        ) -> ProductReceipt:
            calls.append(S.PROD_PRODUCTS)
            raise ProductGenerationError(S.PROD_TEST_FAILURE)

    configured = accounts()
    receipt = SyncService(
        MemoryStorage(),
        Settings(
            accounts=configured,
            metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
        ),
        {}
        if source_failure
        else {
            account.source: FixtureConnector(complete_snapshot(account)) for account in configured
        },
        {},
        analytics=Analyses(),
        products=Products(),
        on_event=events.append,
    ).run()
    assert receipt.state != SyncState.COMPLETE
    assert receipt.products is not C.NONE
    if source_failure:
        assert not calls
        assert receipt.products.state == SyncState.PARTIAL
        assert receipt.products.issues[C.ZERO].code == S.PROD_SKIPPED_CODE
    else:
        assert calls == [S.PROD_ANALYTICS_STAGE, S.PROD_PRODUCTS]
        assert receipt.products.state == SyncState.FAILED
        assert receipt.products.issues[C.ZERO].code == S.PROD_FAILED_CODE
        assert S.PROD_STAGE_PRODUCTS in events
