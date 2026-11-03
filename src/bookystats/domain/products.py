from __future__ import annotations

from pydantic import Field

from bookystats import constants as C
from bookystats.domain.analytics import AnalysisManifest
from bookystats.domain.models import Issue, Model, SyncState


class ProductReceipt(Model):
    state: SyncState
    analytics_report_id: int | None = C.NONE
    output_directory: str | None = C.NONE
    pdf_file: str | None = C.NONE
    metadata_quality_file: str | None = C.NONE
    recommendations_file: str | None = C.NONE
    manifest_file: str | None = C.NONE
    ranked: int = Field(default=C.ZERO, ge=C.ZERO)
    shortlisted: int = Field(default=C.ZERO, ge=C.ZERO)
    unrankable: int = Field(default=C.ZERO, ge=C.ZERO)
    excluded: int = Field(default=C.ZERO, ge=C.ZERO)
    recommendations_reused: bool = C.FALSE
    issues: tuple[Issue, ...] = ()


class BundleManifest(Model):
    schema_version: int = Field(default=C.ONE, ge=C.ONE, le=C.TWO)
    layout_version: int = Field(default=C.ONE, ge=C.ONE)
    analytics_report_id: int = Field(ge=C.ONE)
    analysis_manifest: AnalysisManifest
    files: dict[str, str]
    summary: ProductReceipt


class BundlePointer(Model):
    schema_version: int = Field(default=C.ONE, ge=C.ONE, le=C.TWO)
    layout_version: int = Field(default=C.ONE, ge=C.ONE)
    analytics_report_id: int = Field(ge=C.ONE)
    manifest_sha256: str
