from __future__ import annotations

from pydantic import Field, JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.models import (
    FieldState,
    Issue,
    Observation,
    PartialDate,
    ReadingEvent,
    ReadingStatus,
    Source,
    SyncState,
    utc_now,
)


class DeclaredLabel(C.Model):
    goodreads_id: str = Field(min_length=C.ONE)
    dimension: str
    evidence: str = Field(min_length=C.ONE)

    @C.AFTER_MODEL_VALIDATOR
    def known_dimension(self) -> DeclaredLabel:
        if self.dimension not in C.ANALYTICS_DIMENSIONS:
            raise ValueError(S.AN_UNKNOWN_DIMENSION)
        return self


class AnalyticsSettings(C.Model):
    enabled: bool = C.TRUE
    min_group_size: int = Field(
        default=C.FIVE, ge=C.THREE, le=C.METADATASETTINGS_MAX_BOOKS_PER_RUN_LE
    )
    prior_strength: float = Field(default=C.FIVE, gt=C.ZERO)
    high_rating_threshold: float = Field(default=C.FOUR, ge=C.ZERO, le=C.FIVE)
    declared_preferences: dict[str, float] = Field(default_factory=dict)
    book_labels: tuple[DeclaredLabel, ...] = ()

    @C.AFTER_MODEL_VALIDATOR
    def valid_preferences(self) -> AnalyticsSettings:
        if any(
            name not in C.ANALYTICS_DIMENSIONS or not C.ZERO <= value <= C.ONE
            for name, value in self.declared_preferences.items()
        ):
            raise ValueError(S.AN_INVALID_PREFERENCES)
        return self


class AnalysisEvidence(C.Model):
    source: str
    source_id: str
    observation: Observation
    public_url: str | None = C.NONE
    detail: str | None = C.NONE


class AnalysisBook(C.Model):
    work_id: int = Field(ge=C.ONE)
    source_ids: tuple[str, ...]
    title: str
    authors: tuple[str, ...] = ()
    collections: tuple[str, ...] = ()
    status: ReadingStatus = ReadingStatus.UNKNOWN
    rating: float | None = Field(default=C.NONE, ge=C.ZERO, le=C.FIVE)
    rating_conflict: bool = C.FALSE
    features: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    page_count: int | None = Field(default=C.NONE, ge=C.ONE)
    publication_year: int | None = Field(default=C.NONE, ge=C.ONE)
    first_publication_year: int | None = Field(default=C.NONE, ge=C.ONE)
    description: str | None = C.NONE
    review: str | None = C.NONE
    community_ratings: dict[str, float] = Field(default_factory=dict)
    reading_events: tuple[ReadingEvent, ...] = ()
    added_at: PartialDate | None = C.NONE
    field_states: dict[str, FieldState] = Field(default_factory=dict)
    evidence: tuple[AnalysisEvidence, ...] = ()

    @property
    def book_id(self) -> str:
        return S.AN_WORK_ID.format(work_id=self.work_id)


class AnalysisSnapshot(C.Model):
    source: Source
    account_id: str
    collection: str
    snapshot_id: int = Field(ge=C.ONE)
    raw_document_id: str | None = C.NONE
    processing_version: str | None = C.NONE
    input_kind: S.InputKind
    finished_at: str
    records: int = Field(ge=C.ZERO)
    attempt_state: SyncState


class AnalysisMetadata(C.Model):
    source_id: str
    provider: Source
    attempt_id: int = Field(ge=C.ONE)
    candidate_id: int = Field(ge=C.ONE)
    checked_at: str
    payload_hash: str


class AnalysisManifest(C.Model):
    account_fingerprint: str
    snapshots: tuple[AnalysisSnapshot, ...]
    metadata: tuple[AnalysisMetadata, ...] = ()
    calculation_version: str = S.AN_CALCULATION_VERSION
    settings_hash: str
    settings: AnalyticsSettings = Field(default_factory=AnalyticsSettings)


class AnalysisInput(C.Model):
    books: tuple[AnalysisBook, ...]
    manifest: AnalysisManifest
    source_counts: dict[str, int] = Field(default_factory=dict)
    personal_rating_records: int = Field(default=C.ZERO, ge=C.ZERO)
    issues: tuple[Issue, ...] = ()
    as_of: str = Field(default_factory=utc_now)


class Finding(C.Model):
    metric_id: str
    population: str
    value: JsonValue = C.NONE
    unit: str
    sample_size: int = Field(ge=C.ZERO)
    missing_count: int = Field(default=C.ZERO, ge=C.ZERO)
    baseline: float | None = C.NONE
    period: str | None = C.NONE
    reliability: str
    uncertainty: dict[str, JsonValue] = Field(default_factory=dict)
    supporting_books: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    calculation_version: str = S.AN_CALCULATION_VERSION
    source_snapshot_ids: tuple[int, ...] = ()


class Capability(C.Model):
    metric_id: str
    state: C.AnalyticsCapability
    available: int = Field(ge=C.ZERO)
    population: int = Field(ge=C.ZERO)
    reason: str


class AnalysisComponent(C.Model):
    key: str
    kind: C.AnalyticsComponentKind
    findings: tuple[Finding, ...]
    capabilities: tuple[Capability, ...] = ()
    preferences: dict[str, float] = Field(default_factory=dict)


class AnalyticsReport(C.Model):
    report_id: int | None = C.NONE
    created_at: str = Field(default_factory=utc_now)
    as_of: str | None = C.NONE
    manifest: AnalysisManifest
    taste: AnalysisComponent
    watchlist: AnalysisComponent
    taste_reused: bool = C.FALSE
    watchlist_reused: bool = C.FALSE
    issues: tuple[Issue, ...] = ()


class AnalyticsReceipt(C.Model):
    state: SyncState
    execution_mode: str = S.AN_EXECUTION_SERIAL
    report_id: int | None = C.NONE
    findings: int = Field(default=C.ZERO, ge=C.ZERO)
    rated_read: int = Field(default=C.ZERO, ge=C.ZERO)
    read_works: int = Field(default=C.ZERO, ge=C.ZERO)
    taste_reused: bool = C.FALSE
    watchlist_reused: bool = C.FALSE
    issues: tuple[Issue, ...] = ()
