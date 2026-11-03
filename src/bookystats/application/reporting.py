from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.reports.pdf import render_pdf
from bookystats.application.reader_report import build_reader_report
from bookystats.domain.analytics import AnalysisInput, AnalyticsReport


@C.frozen_dataclass
class LibraryReportArtifact:
    path: Path
    sha256: str
    page_count: int


def _report_json(report: BaseModel | JsonValue) -> dict[str, JsonValue]:
    value = report.model_dump(mode=S.JSON) if isinstance(report, BaseModel) else report
    if not isinstance(value, dict):
        raise ValueError(S.PDF_INVALID_REPORT)
    return value


def _validate_report(
    report: dict[str, JsonValue], data: AnalysisInput, analysis: AnalyticsReport
) -> None:
    if (
        report.get(S.PDF_KEY_AS_OF) != data.as_of
        or report.get(S.PDF_KEY_MANIFEST) != data.manifest.model_dump(mode=S.JSON)
        or report.get(S.PDF_KEY_ANALYSIS_ID) != analysis.report_id
    ):
        raise ValueError(S.PDF_PIN_MISMATCH)


def render_library_report(
    data: AnalysisInput,
    analysis: AnalyticsReport,
    recommendations: BaseModel | JsonValue,
    quality: BaseModel | JsonValue,
    destination: Path,
) -> LibraryReportArtifact:
    if analysis.manifest != data.manifest or analysis.as_of != data.as_of:
        raise ValueError(S.PDF_PIN_MISMATCH)
    recommendation_json = _report_json(recommendations)
    quality_json = _report_json(quality)
    _validate_report(recommendation_json, data, analysis)
    _validate_report(quality_json, data, analysis)
    reader_report = build_reader_report(data, analysis, recommendation_json, quality_json)
    destination.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
    staging = destination.with_name(
        S.PDF_STAGING_NAME.format(name=destination.name, token=uuid4().hex)
    )
    created = C.FALSE
    try:
        with staging.open(S.PDF_EXCLUSIVE_BINARY) as stream:
            created = C.TRUE
            pages = render_pdf(reader_report, stream)
            stream.flush()
            os.fsync(stream.fileno())
        payload = staging.read_bytes()
        if (
            pages < C.ONE
            or not payload.startswith(S.PDF_MAGIC)
            or not payload.rstrip().endswith(S.PDF_EOF)
        ):
            raise ValueError(S.PDF_INVALID_ARTIFACT)
        digest = hashlib.sha256(payload).hexdigest()
        os.replace(staging, destination)
    finally:
        if created:
            staging.unlink(missing_ok=C.TRUE)
    return LibraryReportArtifact(path=destination, sha256=digest, page_count=pages)
