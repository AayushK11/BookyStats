from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol, runtime_checkable

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.models import (
    Account,
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    EnrichmentResult,
    PublicationResult,
    Source,
    SyncState,
)

ProgressCallback = Callable[[CollectionProgress], None]


@C.frozen_dataclass
class PageDocument:
    url: str
    html: str
    status_code: int | None = C.INTERFACES_PAGEDOCUMENT_STATUS_CODE


class BrowserFetcher(Protocol):
    def fetch(self, url: str, *, wait_for: str | None = C.NONE) -> PageDocument:
        pass


@C.frozen_dataclass
class HttpResponse:
    url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode(S.UTF_8_SIG)


class HttpFetcher(Protocol):
    def fetch(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = C.NONE,
        headers: Mapping[str, str] | None = C.NONE,
    ) -> HttpResponse:
        pass


class SourceConnector(Protocol):
    def collect(
        self,
        account: Account,
        *,
        interactive: bool = C.FALSE,
        on_progress: ProgressCallback | None = C.NONE,
    ) -> CollectionSnapshot:
        pass


class MetadataProvider(Protocol):
    def lookup(self, book: BookRecord) -> EnrichmentResult:
        pass


@runtime_checkable
class BatchMetadataProvider(Protocol):
    def lookup_many(self, books: tuple[BookRecord, ...]) -> tuple[EnrichmentResult, ...]:
        pass


class Storage(Protocol):
    def start_run(self, trigger: str) -> int:
        pass

    def stage_progress(self, run_id: int, progress: CollectionProgress) -> None:
        pass

    def save_snapshot(self, run_id: int, snapshot: CollectionSnapshot) -> PublicationResult | None:
        pass

    def finish_run(self, run_id: int, state: SyncState) -> None:
        pass

    def status(self) -> dict[str, JsonValue]:
        pass

    def active_records(self) -> tuple[BookRecord, ...]:
        pass

    def save_enrichment(self, source: Source, provider: Source, result: EnrichmentResult) -> None:
        pass

    def enrichment_targets(
        self,
        provider: Source,
        *,
        max_age_days: int = C.STORAGE_ENRICHMENT_TARGETS_MAX_AGE_DAYS,
        limit: int | None = C.NONE,
    ) -> tuple[BookRecord, ...]:
        pass
