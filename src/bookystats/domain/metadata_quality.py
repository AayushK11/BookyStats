from __future__ import annotations

from pydantic import Field, JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisManifest, Capability


class MetadataFieldCoverage(C.Model):
    field: str
    scope: str
    population_name: str
    population: int = Field(ge=C.ZERO)
    available: int = Field(ge=C.ZERO)
    missing: int = Field(ge=C.ZERO)
    states: dict[str, int]
    sources: dict[str, int]
    missing_causes: dict[str, int] = Field(default_factory=dict)
    specific_available: int | None = Field(default=C.NONE, ge=C.ZERO)


class MetadataIdentitySummary(C.Model):
    selected_metadata_records: int = Field(ge=C.ZERO)
    provider_linked_works: int = Field(ge=C.ZERO)
    cross_provider_works: int = Field(ge=C.ZERO)
    identity_anchor_works: int = Field(ge=C.ZERO)
    cross_provider_comparable_works: int = Field(ge=C.ZERO)
    cross_provider_consistent_works: int = Field(ge=C.ZERO)
    independently_verified_works: int | None = C.NONE


class MetadataQualityDiagnostic(C.Model):
    code: str
    field: str | None = C.NONE
    work_ids: tuple[int, ...]
    count: int = Field(ge=C.ZERO)
    message: str


class MetadataQualityReport(C.Model):
    schema_version: str = S.MQ_REPORT_VERSION
    as_of: str
    manifest: AnalysisManifest
    analysis_report_id: int | None = C.NONE
    population: int = Field(ge=C.ZERO)
    read_works: int = Field(ge=C.ZERO)
    watchlist_works: int = Field(ge=C.ZERO)
    coverage: tuple[MetadataFieldCoverage, ...]
    identity: MetadataIdentitySummary
    diagnostics: tuple[MetadataQualityDiagnostic, ...]
    capabilities: tuple[Capability, ...] = ()
    provider_status: dict[str, JsonValue] = Field(default_factory=dict)
    limitations: tuple[str, ...] = ()


def implausible_page_count(pages: int | None) -> bool:
    return pages is not C.NONE and pages < C.L1_COV_MIN_PLAUSIBLE_PAGES


def early_first_publication_year(year: int | None) -> bool:
    return year is not C.NONE and year < C.L1_COV_EARLY_YEAR_LIMIT
