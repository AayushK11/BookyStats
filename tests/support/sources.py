from __future__ import annotations

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import ConnectorError
from bookystats.domain.interfaces import ProgressCallback
from bookystats.domain.models import (
    Account,
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    EnrichmentResult,
    FieldState,
    PublicationResult,
    Source,
    SyncState,
    utc_now,
)


def accounts() -> tuple[Account, ...]:
    return (
        Account(
            source=Source.STORYGRAPH,
            account_id=S.READER,
            profile_url=S.TEST_REJECTS_AN_ACCOUNT_FOR_A_APP_THESTORYGRAPH_COM_PROFILE_READER,
        ),
        Account(
            source=Source.GOODREADS,
            account_id=S.TEST_MODELS_COMPLETE_SNAPSHOT_REQUIRES_AND_IDENTITY_ACCOUNT_ID_TEXT,
            profile_url=S.TEST_SYNC_ACCOUNTS_PROFILE_URL_HTTPS_WWW_GOODREADS_COM_USER_SHOW,
        ),
    )


def complete_snapshot(account: Account) -> CollectionSnapshot:
    return CollectionSnapshot(
        source=account.source,
        account_id=account.account_id,
        collection=S.LIBRARY if account.source == Source.STORYGRAPH else S.TO_READ,
        state=SyncState.COMPLETE,
        started_at=utc_now(),
        identity_verified=C.TRUE,
        termination_verified=C.TRUE,
        expected_count=C.ZERO,
        pages_seen=C.ONE,
        capabilities={
            name: FieldState.PRESENT
            for name in (S.RATING, S.REVIEW, S.READING_EVENTS, S.STATUS, S.WATCHLIST)
        },
    )


class MemoryStorage:
    def __init__(self) -> None:
        self.saved: list[CollectionSnapshot] = []
        self.published: list[CollectionSnapshot] = []
        self.completed: list[SyncState] = []
        self.targets: tuple[BookRecord, ...] = ()
        self.enriched: list[tuple[Source, Source, EnrichmentResult]] = []

    def start_run(self, trigger: str) -> int:
        return C.ONE

    def stage_progress(self, run_id: int, progress: CollectionProgress) -> None:
        pass

    def save_snapshot(self, run_id: int, snapshot: CollectionSnapshot) -> PublicationResult | None:
        self.saved.append(snapshot)
        if snapshot.state == SyncState.COMPLETE:
            self.published.append(snapshot)
            return PublicationResult(snapshot_id=len(self.saved))
        return C.NONE

    def finish_run(self, run_id: int, state: SyncState) -> None:
        self.completed.append(state)

    def status(self) -> dict[str, JsonValue]:
        return {}

    def active_records(self) -> tuple[BookRecord, ...]:
        return self.targets

    def save_enrichment(self, source: Source, provider: Source, result: EnrichmentResult) -> None:
        self.enriched.append((source, provider, result))

    def reconcile_provider_work_matches(self) -> int:
        return C.ZERO

    def enrichment_targets(
        self,
        provider: Source,
        *,
        max_age_days: int = C.MEMORYSTORAGE_ENRICHMENT_TARGETS_MAX_AGE_DAYS,
        limit: int | None = C.NONE,
    ) -> tuple[BookRecord, ...]:
        return self.targets if limit is C.NONE else self.targets[:limit]


class FixtureConnector:
    def __init__(self, snapshot: CollectionSnapshot) -> None:
        self.snapshot = snapshot

    def collect(
        self,
        account: Account,
        *,
        interactive: bool = C.FALSE,
        on_progress: ProgressCallback | None = C.NONE,
    ) -> CollectionSnapshot:
        return self.snapshot


class AuthRequiredConnector:
    def collect(
        self,
        account: Account,
        *,
        interactive: bool = C.FALSE,
        on_progress: ProgressCallback | None = C.NONE,
    ) -> CollectionSnapshot:
        raise ConnectorError(
            S.TEST_SYNC_AUTHREQUIREDCONNECTOR_COLLECT_SIGN_IN_TO_THE_SOURCE_AGAIN,
            state=SyncState.NEEDS_AUTH,
            code=S.AUTHENTICATION_REQUIRED,
        )
