from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

import pytest
from pydantic import JsonValue
from pypdf import PdfReader

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import reporting
from bookystats.application.metadata_quality import build_metadata_quality
from bookystats.application.statistics import build_taste, build_watchlist
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisComponent,
    AnalysisInput,
    AnalysisManifest,
    AnalyticsReport,
)
from bookystats.domain.models import ReadingStatus
from bookystats.domain.recommendations import build_recommendations


def _inputs() -> tuple[AnalysisInput, AnalyticsReport, dict[str, JsonValue]]:
    data = AnalysisInput(
        books=(
            AnalysisBook(
                work_id=C.ONE,
                source_ids=(S.PDF_TEST_SOURCE,),
                title=S.PDF_TEST_UNICODE,
                status=ReadingStatus.READ,
                authors=(S.PDF_TEST_AUTHOR,),
            ),
        ),
        manifest=AnalysisManifest(
            account_fingerprint=S.PDF_TEST_ACCOUNT,
            snapshots=(),
            settings_hash=S.PDF_TEST_HASH,
        ),
        as_of=S.PDF_TEST_DATE,
    )
    analysis = AnalyticsReport(
        report_id=C.ONE,
        manifest=data.manifest,
        as_of=data.as_of,
        created_at=data.as_of,
        taste=AnalysisComponent(
            key=S.PDF_TEST_HASH, kind=C.AnalyticsComponentKind.TASTE, findings=()
        ),
        watchlist=AnalysisComponent(
            key=S.PDF_TEST_HASH, kind=C.AnalyticsComponentKind.WATCHLIST, findings=()
        ),
    )
    report: dict[str, JsonValue] = {
        S.PDF_KEY_AS_OF: data.as_of,
        S.PDF_KEY_MANIFEST: data.manifest.model_dump(mode=S.JSON),
        S.PDF_KEY_ANALYSIS_ID: analysis.report_id,
    }
    return data, analysis, report


def test_real_pdf_contains_unicode_and_all_sections(tmp_path: Path) -> None:
    data, analysis, report = _inputs()
    destination = tmp_path / S.PDF_TEST_FILENAME
    artifact = reporting.render_library_report(data, analysis, report, report, destination)
    reader = PdfReader(destination)
    text = S.NEWLINE.join(page.extract_text() for page in reader.pages)
    assert artifact.path == destination
    assert artifact.page_count == len(reader.pages)
    assert artifact.sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert artifact.page_count >= C.PDF_TEST_MIN_PAGES
    assert S.PDF_TEST_UNICODE in text.replace(S.NEWLINE, S.SPACE)
    assert S.PDF_NO_SHORTLIST in text
    assert S.RD_SECTION_APPETITES in S.SPACE.join(text.split())
    assert S.RD_TIME_NOTE in S.SPACE.join(text.split())
    assert reader.outline
    assert len(reader.pages) <= C.RD_PAGE_BUDGET
    assert not list(tmp_path.glob(S.PDF_TEST_STAGING_PATTERN))
    for page in reader.pages:
        assert S.PDF_PAGE.format(page=reader.pages.index(page) + C.ONE) in page.extract_text()


def test_pdf_failure_keeps_previous_artifact_and_cleans_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, analysis, report = _inputs()
    destination = tmp_path / S.PDF_TEST_FILENAME
    destination.write_bytes(S.PDF_TEST_PREVIOUS)

    def fail(
        data: AnalysisInput,
        analysis: AnalyticsReport,
        recommendations: dict[str, JsonValue],
        quality: dict[str, JsonValue],
        stream: BinaryIO,
    ) -> int:
        stream.write(S.PDF_MAGIC)
        raise RuntimeError(S.PDF_TEST_FAILURE)

    monkeypatch.setattr(reporting, S.PDF_TEST_RENDER_ATTRIBUTE, fail)
    with pytest.raises(RuntimeError, match=S.PDF_TEST_FAILURE):
        reporting.render_library_report(data, analysis, report, report, destination)
    assert destination.read_bytes() == S.PDF_TEST_PREVIOUS
    assert not list(tmp_path.glob(S.PDF_TEST_STAGING_PATTERN))


def test_pdf_rejects_mixed_pins_before_touching_artifact(tmp_path: Path) -> None:
    data, analysis, report = _inputs()
    destination = tmp_path / S.PDF_TEST_FILENAME
    destination.write_bytes(S.PDF_TEST_PREVIOUS)
    stale = dict(report)
    stale[S.PDF_KEY_AS_OF] = S.PDF_TEST_OTHER_DATE
    with pytest.raises(ValueError, match=S.PDF_PIN_MISMATCH):
        reporting.render_library_report(data, analysis, stale, report, destination)
    assert destination.read_bytes() == S.PDF_TEST_PREVIOUS


def test_successful_render_atomically_replaces_previous_pdf(tmp_path: Path) -> None:
    data, analysis, report = _inputs()
    destination = tmp_path / S.PDF_TEST_FILENAME
    destination.write_bytes(S.PDF_TEST_PREVIOUS)
    artifact = reporting.render_library_report(data, analysis, report, report, destination)
    assert destination.read_bytes().startswith(S.PDF_MAGIC)
    assert artifact.page_count == len(PdfReader(destination).pages)


def test_native_analytics_recommendations_and_quality_contracts_render(tmp_path: Path) -> None:
    data, analysis, _ = _inputs()
    settings = data.manifest.settings
    taste = build_taste(data, settings, key=S.PDF_TEST_HASH)
    watchlist = build_watchlist(data, settings, taste, key=S.PDF_TEST_HASH)
    analysis = analysis.model_copy(update={S.AN_TASTE: taste, S.AN_WATCHLIST: watchlist})
    recommendations = build_recommendations(data, analysis)
    quality = build_metadata_quality(data, analysis, {})
    artifact = reporting.render_library_report(
        data, analysis, recommendations, quality, tmp_path / S.PDF_TEST_FILENAME
    )
    text = S.NEWLINE.join(page.extract_text() for page in PdfReader(artifact.path).pages)
    assert S.PDF_TEST_UNICODE in text.replace(S.NEWLINE, S.SPACE)
    assert S.RD_SECTION_COVERAGE in text
    assert S.RD_SOURCES_NOTE in S.SPACE.join(text.split())
    assert S.PDF_PROVIDER_STATUS not in text


def test_atomic_replace_failure_preserves_previous_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, analysis, report = _inputs()
    destination = tmp_path / S.PDF_TEST_FILENAME
    destination.write_bytes(S.PDF_TEST_PREVIOUS)

    def fail(source: Path, target: Path) -> None:
        assert source.read_bytes().rstrip().endswith(S.PDF_EOF)
        raise PermissionError(S.PDF_TEST_FAILURE)

    monkeypatch.setattr(reporting.os, S.PDF_TEST_REPLACE_ATTRIBUTE, fail)
    with pytest.raises(PermissionError, match=S.PDF_TEST_FAILURE):
        reporting.render_library_report(data, analysis, report, report, destination)
    assert destination.read_bytes() == S.PDF_TEST_PREVIOUS
    assert not list(tmp_path.glob(S.PDF_TEST_STAGING_PATTERN))
