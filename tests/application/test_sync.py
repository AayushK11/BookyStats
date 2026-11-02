from __future__ import annotations

from contextlib import ExitStack, closing
from pathlib import Path

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import HttpClient
from bookystats.adapters.metadata.google_books import GoogleBooksProvider
from bookystats.application.sync import SyncService
from bookystats.domain.errors import ProviderDeferredError
from bookystats.domain.models import (
    BookRecord,
    EnrichmentResult,
    FieldState,
    Issue,
    ReadingStatus,
    Source,
    SyncState,
)
from bookystats.persistence.library import Database
from bookystats.runtime.config import MetadataSettings, Settings
from tests.support.sources import (
    AuthRequiredConnector,
    FixtureConnector,
    MemoryStorage,
    accounts,
    complete_snapshot,
)


def _metadata_books() -> tuple[BookRecord, ...]:
    return tuple(
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


def test_source_scope_closes_before_enrichment_and_progress_follows_checkpoints() -> None:
    storage = MemoryStorage()
    storage.targets = _metadata_books()
    closed: list[str] = []
    finished_sources = []
    progress: list[tuple[Source, int, int]] = []
    scope = ExitStack()
    scope.callback(closed.append, S.SOURCES)

    class Provider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            assert closed == [S.SOURCES]
            assert len(finished_sources) == C.TWO
            return EnrichmentResult(source_id=book.source_id, state=SyncState.COMPLETE)

    def metadata_progress(source: Source, completed: int, total: int) -> None:
        assert len(storage.enriched) == completed
        progress.append((source, completed, total))

    receipt = SyncService(
        storage,
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
        ),
        {account.source: FixtureConnector(complete_snapshot(account)) for account in accounts()},
        {Source.GOOGLE_BOOKS: Provider()},
        source_context=scope,
        on_source_complete=finished_sources.append,
        on_metadata_progress=metadata_progress,
    ).run()
    assert receipt.state == SyncState.COMPLETE
    assert progress == [
        (Source.GOOGLE_BOOKS, C.ZERO, C.TWO),
        (Source.GOOGLE_BOOKS, C.ONE, C.TWO),
        (Source.GOOGLE_BOOKS, C.TWO, C.TWO),
    ]


def test_interrupted_enrichment_keeps_completed_book_in_sqlite(tmp_path: Path) -> None:
    configured = accounts()
    books = _metadata_books()

    class Provider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            if book.source_id == books[C.ONE].source_id:
                raise KeyboardInterrupt
            return EnrichmentResult(source_id=book.source_id, state=SyncState.COMPLETE)

    path = tmp_path / S.LIBRARY_SQLITE3
    with closing(Database(path)) as storage:
        storage.initialize()
        snapshots = {account.source: complete_snapshot(account) for account in configured}
        snapshots[Source.GOODREADS] = snapshots[Source.GOODREADS].model_copy(
            update={S.RECORDS: books, S.EXPECTED_COUNT: len(books)}
        )
        with pytest.raises(KeyboardInterrupt):
            SyncService(
                storage,
                Settings(
                    accounts=configured,
                    metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
                ),
                {source: FixtureConnector(snapshot) for source, snapshot in snapshots.items()},
                {Source.GOOGLE_BOOKS: Provider()},
            ).run()
    with closing(Database(path)) as reopened:
        reopened.initialize()
        status = reopened.status()
        assert status[S.LAST_RUN][S.STATE] == S.INTERRUPTED
        assert status[S.METADATA][S.GOOGLE_BOOKS][S.ATTEMPTS] == C.ONE
        assert status[S.LIBRARY][S.SOURCE_RECORDS] == C.TWO


def test_late_metadata_identity_mismatch_preserves_only_valid_prior_results() -> None:
    storage = MemoryStorage()
    storage.targets = _metadata_books()

    class Provider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            return EnrichmentResult(
                source_id=(book.source_id if book == storage.targets[C.ZERO] else S.DIFFERENT_BOOK),
                state=SyncState.COMPLETE,
            )

    receipt = SyncService(
        storage,
        Settings(metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE)),
        {},
        {Source.GOOGLE_BOOKS: Provider()},
    )._metadata(Source.GOOGLE_BOOKS)
    assert receipt.state == SyncState.FAILED
    assert receipt.processed == C.ONE
    assert receipt.deferred == C.ONE
    assert len(storage.enriched) == C.ONE
    assert storage.enriched[C.ZERO][C.TWO].source_id == storage.targets[C.ZERO].source_id


def test_open_library_batches_checkpoint_before_next_request() -> None:
    storage = MemoryStorage()
    storage.targets = _metadata_books() * C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES
    calls: list[int] = []

    class Provider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            return EnrichmentResult(source_id=book.source_id, state=SyncState.COMPLETE)

        def lookup_many(self, books: tuple[BookRecord, ...]) -> tuple[EnrichmentResult, ...]:
            assert len(storage.enriched) == sum(calls)
            assert len(books) <= C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES
            calls.append(len(books))
            return tuple(self.lookup(book) for book in books)

    receipt = SyncService(
        storage,
        Settings(metadata=MetadataSettings(max_books_per_run=len(storage.targets))),
        {},
        {Source.OPEN_LIBRARY: Provider()},
    )._metadata(Source.OPEN_LIBRARY)
    assert receipt.state == SyncState.COMPLETE
    assert receipt.processed == len(storage.targets)
    assert len(calls) == C.TWO


def test_open_library_later_cooldown_preserves_completed_batch() -> None:
    storage = MemoryStorage()
    storage.targets = _metadata_books() * C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES

    class Provider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            return EnrichmentResult(source_id=book.source_id, state=SyncState.COMPLETE)

        def lookup_many(self, books: tuple[BookRecord, ...]) -> tuple[EnrichmentResult, ...]:
            if storage.enriched:
                raise ProviderDeferredError(S.PROVIDER_COOLDOWN_MESSAGE, code=S.PROVIDER_COOLDOWN)
            return tuple(self.lookup(book) for book in books)

    receipt = SyncService(
        storage,
        Settings(metadata=MetadataSettings(max_books_per_run=len(storage.targets))),
        {},
        {Source.OPEN_LIBRARY: Provider()},
    )._metadata(Source.OPEN_LIBRARY)
    assert receipt.state == SyncState.PARTIAL
    assert receipt.processed == C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES
    assert receipt.deferred == C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES
    assert len(storage.enriched) == C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES


def test_open_library_refinement_stops_before_unattempted_target_and_preserves_cause() -> None:
    storage = MemoryStorage()
    storage.targets = _metadata_books()

    class Provider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            return EnrichmentResult(source_id=book.source_id, state=SyncState.COMPLETE)

        def lookup_many(self, books: tuple[BookRecord, ...]) -> tuple[EnrichmentResult, ...]:
            return (
                self.lookup(books[C.ZERO]),
                EnrichmentResult(
                    source_id=books[C.ONE].source_id,
                    state=SyncState.PARTIAL,
                    issues=(
                        Issue(code=S.MC_TARGET_DEFERRED, message=S.META_RUN_HALTED_MESSAGE),
                        Issue(
                            code=S.PROVIDER_COOLDOWN,
                            message=S.PROVIDER_COOLDOWN_MESSAGE,
                            retryable=C.TRUE,
                        ),
                    ),
                ),
            )

    receipt = SyncService(
        storage,
        Settings(),
        {},
        {Source.OPEN_LIBRARY: Provider()},
    )._metadata(Source.OPEN_LIBRARY)
    assert receipt.state == SyncState.PARTIAL
    assert receipt.processed == receipt.deferred == C.ONE
    assert len(storage.enriched) == C.ONE
    assert any(issue.code == S.PROVIDER_COOLDOWN for issue in receipt.issues)
    assert all(issue.code != S.MC_TARGET_DEFERRED for issue in receipt.issues)


def test_limited_metadata_budget_prioritizes_authoritative_read_collection() -> None:
    storage = MemoryStorage()
    original = _metadata_books()
    storage.targets = (
        original[C.ZERO].model_copy(update={S.STATUS: ReadingStatus.TO_READ}),
        original[C.ONE].model_copy(update={S.STATUS: ReadingStatus.READ}),
    )

    class Provider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            return EnrichmentResult(source_id=book.source_id, state=SyncState.COMPLETE)

    receipt = SyncService(
        storage,
        Settings(metadata=MetadataSettings(max_books_per_run=C.ONE)),
        {},
        {Source.GOOGLE_BOOKS: Provider()},
    )._metadata(Source.GOOGLE_BOOKS)
    assert receipt.processed == receipt.deferred == C.ONE
    assert storage.enriched[C.ZERO][C.TWO].source_id == storage.targets[C.ONE].source_id


def test_complete_file_processing_never_counts_as_complete_account_capture() -> None:
    storage = MemoryStorage()
    configured = accounts()
    connectors = {
        account.source: FixtureConnector(
            complete_snapshot(account).model_copy(
                update={
                    S.COLLECTION: S.LIBRARY,
                    S.INPUT_KIND: S.INPUT_FILE,
                    S.INPUT_RAW_DOCUMENT_ID: S.INPUT_TEST_RAW_ID,
                    S.INPUT_PROCESSING_VERSION: S.INPUT_TEST_VERSION,
                    S.IDENTITY_VERIFIED: C.FALSE,
                    S.CAPABILITIES: {},
                }
            )
        )
        for account in configured
    }
    receipt = SyncService(
        storage,
        Settings(
            accounts=configured,
            metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
        ),
        connectors,
        {},
    ).run()
    assert receipt.state == SyncState.COMPLETE
    assert not receipt.account_sync_complete
    assert len(storage.published) == C.TWO
    assert all(source.raw_document_id == S.INPUT_TEST_RAW_ID for source in receipt.sources)


def test_sources_publish_independently_on_auth_failure() -> None:
    _storygraph, goodreads = accounts()
    storage = MemoryStorage()
    settings = Settings(
        accounts=accounts(),
        metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
    )
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
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
        ),
        {
            Source.STORYGRAPH: FixtureConnector(unsupported),
            Source.GOODREADS: FixtureConnector(complete_snapshot(goodreads)),
        },
        {},
    ).run()
    assert receipt.sources[C.ZERO].state == SyncState.PARTIAL
    assert receipt.sources[C.ZERO].issues[C.ZERO].code == S.REQUIRED_FIELDS_UNVERIFIED
    assert len(storage.published) == C.ONE


def test_read_collection_requires_read_status_not_watchlist_coverage() -> None:
    _storygraph, goodreads = accounts()
    snapshot = complete_snapshot(goodreads).model_copy(
        update={
            S.COLLECTION: S.READ,
            S.CAPABILITIES: {S.STATUS: FieldState.PRESENT},
        }
    )
    checked = SyncService._check_snapshot(goodreads, snapshot, collection=S.READ)
    assert checked.state == SyncState.COMPLETE
    missing = snapshot.model_copy(update={S.CAPABILITIES: {S.WATCHLIST: FieldState.PRESENT}})
    checked = SyncService._check_snapshot(goodreads, missing, collection=S.READ)
    assert checked.state == SyncState.PARTIAL
    assert checked.issues[C.ZERO].code == S.REQUIRED_FIELDS_UNVERIFIED


def test_account_mismatch_does_not_publish_another_readers_data() -> None:
    storygraph, goodreads = accounts()
    mismatched = complete_snapshot(storygraph).model_copy(update={S.ACCOUNT_ID: S.SOMEONE_ELSE})
    storage = MemoryStorage()
    receipt = SyncService(
        storage,
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
        ),
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
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
        ),
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
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
        ),
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
        Settings(
            accounts=accounts(),
            metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
        ),
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
                metadata=MetadataSettings(
                    google_books=C.TRUE, open_library=C.FALSE, max_books_per_run=C.TWO
                ),
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
