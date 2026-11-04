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
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisComponent,
    AnalysisInput,
    AnalysisManifest,
    AnalyticsReport,
)
from bookystats.domain.models import ReadingStatus
from bookystats.domain.reader_report import ReaderReport, manifest_digest
from tests.support.reader_library import library


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


def _flat(text: str) -> str:
    return S.EMPTY.join(text.split())


def test_real_pdf_is_numbered_outlined_and_verified(tmp_path: Path) -> None:
    data, analysis, report = _inputs()
    destination = tmp_path / S.PDF_TEST_FILENAME
    artifact = reporting.render_library_report(data, analysis, report, report, destination)
    reader = PdfReader(destination)
    assert artifact.path == destination
    assert artifact.page_count == len(reader.pages) > C.ONE
    assert artifact.sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert reader.outline
    assert not list(tmp_path.glob(S.PDF_TEST_STAGING_PATTERN))
    for number, page in enumerate(reader.pages[C.ONE :], start=C.TWO):
        assert _flat(S.RPT_PAGE_NUMBER.format(page=number)) in _flat(page.extract_text())


def test_pdf_failure_keeps_previous_artifact_and_cleans_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, analysis, report = _inputs()
    destination = tmp_path / S.PDF_TEST_FILENAME
    destination.write_bytes(S.PDF_TEST_PREVIOUS)

    def fail(reader_report: ReaderReport, stream: BinaryIO) -> int:
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


def test_rendered_report_names_the_exact_saved_inputs_and_stays_within_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lib = library(*C.RPT_TEST_SMALL)
    captured: list[ReaderReport] = []
    render_pdf = reporting.render_pdf

    def capture(reader_report: ReaderReport, stream: BinaryIO) -> int:
        captured.append(reader_report)
        return render_pdf(reader_report, stream)

    monkeypatch.setattr(reporting, S.PDF_TEST_RENDER_ATTRIBUTE, capture)
    artifact = reporting.render_library_report(
        lib.data, lib.analysis, lib.recommendations, lib.quality, tmp_path / S.PDF_TEST_FILENAME
    )
    details = S.RPT_DETAILS.format(
        model=C.RPT_MODEL_VERSION,
        layout=C.RPT_LAYOUT_VERSION,
        report=lib.analysis.report_id,
        digest=manifest_digest(lib.analysis.manifest)[: C.RPT_DIGEST_SHOWN],
    )
    text = S.EMPTY.join(_flat(page.extract_text()) for page in PdfReader(artifact.path).pages)
    assert _flat(details) not in text
    assert not [
        term for term in C.RPT_READER_INTERNAL_TERMS if _flat(term).casefold() in text.casefold()
    ]
    report = ReaderReport.model_validate_json(captured[C.ZERO].model_dump_json())
    assert report.analysis_report_id == lib.analysis.report_id
    assert report.manifest_digest == manifest_digest(lib.analysis.manifest)
    assert report.model_version == C.RPT_MODEL_VERSION
    assert report.as_of == lib.data.as_of
    assert report.technical_notes
    assert report.technical_notes == captured[C.ZERO].technical_notes
    assert _flat(report.cover.as_of) in text
    assert _flat(S.RPT_COMPANION_NOTE) in text
    assert C.RPT_TEST_EMPTY_PAGES_MAX < artifact.page_count <= C.RPT_TEST_SMALL_PAGES_MAX


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
