from __future__ import annotations

import httpx
from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.config import MetadataSettings, Settings
from bookystats.errors import ConnectorError
from bookystats.interfaces import ProgressCallback
from bookystats.models import (
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
from bookystats.net import HttpClient
from bookystats.providers.google_books import GoogleBooksProvider
from bookystats.sync import SyncService


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


def test_sources_publish_independently_on_auth_failure() -> None:
    _storygraph, goodreads = accounts()
    storage = MemoryStorage()
    settings = Settings(accounts=accounts(), metadata=MetadataSettings(google_books=C.FALSE))
    service = SyncService(
        storage,
        settings,
        {
            Source.STORYGRAPH: AuthRequiredConnector(),
            Source.GOODREADS: FixtureConnector(complete_snapshot(goodreads)),
        },
        {},
    )
    receipt = service.run()
    assert receipt.state == SyncState.PARTIAL
    assert not receipt.account_sync_complete
    assert storage.published == [
        complete_snapshot(goodreads).model_copy(
            update={
                S.STARTED_AT: storage.published[C.ZERO].started_at,
                S.FINISHED_AT: storage.published[C.ZERO].finished_at,
            }
        )
    ]
    assert storage.saved[C.ZERO].state == SyncState.NEEDS_AUTH
    assert storage.completed == [SyncState.PARTIAL]


def test_missing_required_detail_capability_cannot_claim_complete() -> None:
    storygraph, goodreads = accounts()
    unsupported = complete_snapshot(storygraph).model_copy(
        update={S.CAPABILITIES: {S.STATUS: FieldState.PRESENT}}
    )
    storage = MemoryStorage()
    receipt = SyncService(
        storage,
        Settings(accounts=accounts(), metadata=MetadataSettings(google_books=C.FALSE)),
        {
            Source.STORYGRAPH: FixtureConnector(unsupported),
            Source.GOODREADS: FixtureConnector(complete_snapshot(goodreads)),
        },
        {},
    ).run()
    assert receipt.sources[C.ZERO].state == SyncState.PARTIAL
    assert receipt.sources[C.ZERO].issues[C.ZERO].code == S.REQUIRED_FIELDS_UNVERIFIED
    assert len(storage.published) == C.ONE


def test_account_mismatch_does_not_publish_another_readers_data() -> None:
    storygraph, goodreads = accounts()
    mismatched = complete_snapshot(storygraph).model_copy(update={S.ACCOUNT_ID: S.SOMEONE_ELSE})
    storage = MemoryStorage()
    receipt = SyncService(
        storage,
        Settings(accounts=accounts(), metadata=MetadataSettings(google_books=C.FALSE)),
        {
            Source.STORYGRAPH: FixtureConnector(mismatched),
            Source.GOODREADS: FixtureConnector(complete_snapshot(goodreads)),
        },
        {},
    ).run()
    assert receipt.sources[C.ZERO].state == SyncState.FAILED
    assert receipt.sources[C.ZERO].issues[C.ZERO].code == S.SOURCE_IDENTITY_MISMATCH
    assert all(item.source != Source.STORYGRAPH for item in storage.published)


def test_missing_metadata_key_does_not_undo_complete_account_publication() -> None:
    storage = MemoryStorage()
    receipt = SyncService(
        storage,
        Settings(accounts=accounts()),
        {account.source: FixtureConnector(complete_snapshot(account)) for account in accounts()},
        {},
    ).run()
    assert receipt.account_sync_complete
    assert len(storage.published) == C.TWO
    assert receipt.metadata[C.ZERO].state == SyncState.NOT_CONFIGURED
    assert receipt.state == SyncState.PARTIAL


def test_noop_without_optional_metadata_can_complete() -> None:
    storage = MemoryStorage()
    receipt = SyncService(
        storage,
        Settings(accounts=accounts(), metadata=MetadataSettings(google_books=C.FALSE)),
        {account.source: FixtureConnector(complete_snapshot(account)) for account in accounts()},
        {},
    ).run()
    assert receipt.account_sync_complete
    assert receipt.state == SyncState.COMPLETE
    assert receipt.metadata == ()


class WrongMetadataProvider:
    def lookup(self, book: BookRecord) -> EnrichmentResult:
        return EnrichmentResult(source_id=S.DIFFERENT_BOOK, state=SyncState.COMPLETE)


def test_metadata_cannot_attach_to_a_different_record() -> None:
    storage = MemoryStorage()
    storage.targets = (
        BookRecord(
            source=Source.GOODREADS,
            source_id=S.TEST_METADATA_CANNOT_ATTACH_TO_A_DIFFERENT_RECORD_SOURCE_ID_TEXT,
            title=S.TEST_METADATA_CANNOT_ATTACH_TO_A_DIFFERENT_RECORD_TITLE_A_BOOK,
            url=S.TEST_METADATA_CANNOT_ATTACH_TO_A_HTTPS_WWW_GOODREADS_COM_BOOK_SHOW,
        ),
    )
    receipt = SyncService(
        storage,
        Settings(accounts=accounts()),
        {account.source: FixtureConnector(complete_snapshot(account)) for account in accounts()},
        {Source.GOOGLE_BOOKS: WrongMetadataProvider()},
    ).run()
    assert receipt.metadata[C.ZERO].state == SyncState.FAILED
    assert storage.enriched == []


def test_provider_cooldown_defers_unrequested_books_without_storing_failures() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            C.HTTP_TOO_MANY_REQUESTS,
            headers={S.RETRY_AFTER: str(C.TEST_PROVIDER_COOLDOWN_SECONDS)},
        )

    storage = MemoryStorage()
    storage.targets = tuple(
        BookRecord(
            source=Source.GOODREADS,
            source_id=str(number),
            title=S.INTEGRATION_TITLE,
            authors=(S.INTEGRATION_AUTHOR,),
            isbns=(S.INTEGRATION_ISBN,),
            url=S.INTEGRATION_GOODREADS_BOOK,
        )
        for number in range(C.TWO)
    )
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        http = HttpClient(allowed_hosts=(S.WWW_GOOGLEAPIS_COM,), client=client, min_interval=C.ZERO)
        receipt = SyncService(
            storage,
            Settings(
                accounts=accounts(),
                metadata=MetadataSettings(max_books_per_run=C.TWO),
            ),
            {
                account.source: FixtureConnector(complete_snapshot(account))
                for account in accounts()
            },
            {Source.GOOGLE_BOOKS: GoogleBooksProvider(http, api_key=S.DO_NOT_PRINT_THIS)},
        ).run()
    assert receipt.account_sync_complete
    assert receipt.state == SyncState.PARTIAL
    assert len(requests) == C.ONE
    assert len(storage.enriched) == C.ONE
    metadata = receipt.metadata[C.ZERO]
    assert metadata.requested == C.TWO
    assert metadata.deferred == C.ONE
    assert any(issue.code == S.PROVIDER_COOLDOWN for issue in metadata.issues)
    assert S.DO_NOT_PRINT_THIS not in receipt.model_dump_json()
