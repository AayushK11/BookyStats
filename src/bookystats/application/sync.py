from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from contextlib import AbstractContextManager, nullcontext

from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalyticsReceipt
from bookystats.domain.errors import (
    BookyError,
    ConnectorError,
    ProviderDeferredError,
    SnapshotRejectedError,
)
from bookystats.domain.interfaces import (
    AnalyticsRunner,
    BatchMetadataProvider,
    MetadataProvider,
    ProgressCallback,
    SourceConnector,
    Storage,
)
from bookystats.domain.models import (
    Account,
    CollectionProgress,
    CollectionSnapshot,
    EnrichmentResult,
    FieldState,
    Issue,
    Model,
    PublicationResult,
    ReadingStatus,
    Source,
    SyncState,
    Verification,
    utc_now,
)
from bookystats.runtime.config import Settings


class SourceReceipt(Model):
    source: Source
    account_id: str | None = C.NONE
    state: SyncState
    records: int = C.ZERO
    pages: int = C.ZERO
    publication: PublicationResult | None = C.NONE
    issues: tuple[Issue, ...] = ()
    input_kind: S.InputKind = S.INPUT_LIVE
    raw_document_id: str | None = C.NONE
    collection: str = S.LIBRARY


class MetadataReceipt(Model):
    provider: Source
    state: SyncState
    requested: int = C.ZERO
    processed: int = C.ZERO
    candidates: int = C.ZERO
    cache_hits: int = C.ZERO
    deferred: int = C.ZERO
    issues: tuple[Issue, ...] = ()


class SyncReceipt(Model):
    run_id: int
    state: SyncState
    started_at: str
    finished_at: str
    account_sync_complete: bool
    sources: tuple[SourceReceipt, ...]
    metadata: tuple[MetadataReceipt, ...]
    verification: Verification | None = C.NONE
    log_file: str | None = C.NONE
    analytics: AnalyticsReceipt | None = C.NONE


class SyncService:
    def __init__(
        self,
        store: Storage,
        settings: Settings,
        connectors: Mapping[Source, SourceConnector],
        providers: Mapping[Source, MetadataProvider],
        *,
        on_progress: ProgressCallback | None = C.NONE,
        provider_issues: Mapping[Source, Issue] | None = C.NONE,
        collection_connectors: Mapping[tuple[Source, str], SourceConnector] | None = C.NONE,
        source_context: AbstractContextManager[object] | None = C.NONE,
        on_source_complete: Callable[[SourceReceipt], None] | None = C.NONE,
        on_metadata_progress: Callable[[Source, int, int], None] | None = C.NONE,
        analytics: AnalyticsRunner | None = C.NONE,
    ) -> None:
        self.store = store
        self.settings = settings
        self.connectors = connectors
        self.providers = providers
        self.on_progress = on_progress
        self.provider_issues = provider_issues or {}
        self.collection_connectors = collection_connectors or {}
        self.source_context = source_context
        self.on_source_complete = on_source_complete
        self.on_metadata_progress = on_metadata_progress
        self.analytics = analytics

    def _progress(self, run_id: int, expected: Source, progress: CollectionProgress) -> None:
        if progress.source != expected:
            raise ConnectorError(
                S.SYNC_SYNCSERVICE_PROGRESS_THE_CONNECTOR_PROGRESS_FOR_A_DIFFERENT,
                code=S.SOURCE_IDENTITY_MISMATCH,
            )
        self.store.stage_progress(run_id, progress)
        if self.on_progress is not C.NONE:
            self.on_progress(progress)

    @staticmethod
    def _check_snapshot(
        account: Account, snapshot: CollectionSnapshot, collection: str | None = C.NONE
    ) -> CollectionSnapshot:
        expected_collection = collection or (
            S.LIBRARY
            if account.source == Source.STORYGRAPH or snapshot.input_kind == S.INPUT_FILE
            else S.TO_READ
        )
        if (
            snapshot.source != account.source
            or snapshot.account_id != account.account_id
            or snapshot.collection != expected_collection
        ):
            raise ConnectorError(
                S.SYNC_SYNCSERVICE_CHECK_SNAPSHOT_THE_COLLECTION_DOES_NOT_BELONG_TO,
                code=S.SOURCE_IDENTITY_MISMATCH,
            )
        if account.source == Source.STORYGRAPH:
            snapshot = snapshot.model_copy(
                update={
                    S.RECORDS: tuple(book.ratings_only() for book in snapshot.records),
                    S.CAPABILITIES: {
                        field: state
                        for field, state in snapshot.capabilities.items()
                        if field in C.RATING_IDENTITY_FIELDS
                    },
                }
            )
        required = (
            C.SYNC_GOODREADS_READ_CAPABILITIES
            if account.source == Source.GOODREADS and snapshot.collection == S.READ
            else C.SYNC_REQUIRED_CAPABILITIES[account.source]
        )
        missing = [
            field
            for field in required
            if snapshot.capabilities.get(field, FieldState.UNSUPPORTED)
            in (FieldState.UNSUPPORTED, FieldState.FAILED)
        ]
        if snapshot.input_kind == S.INPUT_LIVE and snapshot.state == SyncState.COMPLETE and missing:
            return snapshot.model_copy(
                update={
                    S.STATE: SyncState.PARTIAL,
                    S.ISSUES: (
                        *snapshot.issues,
                        Issue(
                            code=S.REQUIRED_FIELDS_UNVERIFIED,
                            message=S.CHECK_SNAPSHOT_UPDATE_MESSAGE_SOURCE_CAPABILITIES_REMAIN_UNVERIFIED
                            + S.CHECK_SNAPSHOT_UPDATE_MESSAGE_TEXT.join(missing),
                        ),
                    ),
                }
            )
        return snapshot

    def _source(
        self, run_id: int, account: Account, interactive: bool, collection: str | None = C.NONE
    ) -> SourceReceipt:
        started = utc_now()
        connector = (
            self.collection_connectors.get((account.source, collection))
            if collection is not C.NONE
            else self.connectors.get(account.source)
        )
        if connector is C.NONE:
            return SourceReceipt(
                source=account.source,
                collection=collection or S.LIBRARY,
                account_id=account.account_id,
                state=SyncState.NOT_CONFIGURED,
                issues=(
                    Issue(
                        code=S.CONNECTOR_MISSING,
                        message=S.SOURCE_ISSUES_MESSAGE_NO_CONNECTOR_IS_CONFIGURED,
                    ),
                ),
            )
        try:
            snapshot = connector.collect(
                account,
                interactive=interactive,
                on_progress=lambda progress: self._progress(run_id, account.source, progress),
            )
            snapshot = self._check_snapshot(account, snapshot, collection)
        except ConnectorError as exc:
            snapshot = CollectionSnapshot(
                source=account.source,
                account_id=account.account_id,
                collection=collection
                or (S.LIBRARY if account.source == Source.STORYGRAPH else S.TO_READ),
                state=exc.state,
                started_at=started,
                issues=(Issue(code=exc.code, message=str(exc), retryable=exc.retryable),),
            )
        except ValidationError:
            snapshot = CollectionSnapshot(
                source=account.source,
                account_id=account.account_id,
                collection=collection
                or (S.LIBRARY if account.source == Source.STORYGRAPH else S.TO_READ),
                state=SyncState.FAILED,
                started_at=started,
                issues=(
                    Issue(
                        code=S.INVALID_SOURCE_CONTRACT,
                        message=S.SNAPSHOT_ISSUES_MESSAGE_SOURCE_RECORDS_VALIDATION_THE_PRIOR_SNAPSHOT,
                    ),
                ),
            )
        try:
            publication = self.store.save_snapshot(run_id, snapshot)
        except SnapshotRejectedError as exc:
            return SourceReceipt(
                source=account.source,
                account_id=account.account_id,
                state=SyncState.FAILED,
                records=len(snapshot.records),
                pages=snapshot.pages_seen,
                issues=(
                    *snapshot.issues,
                    Issue(code=S.SNAPSHOT_REJECTED, message=str(exc)),
                ),
                input_kind=snapshot.input_kind,
                raw_document_id=snapshot.raw_document_id,
                collection=snapshot.collection,
            )
        return SourceReceipt(
            source=account.source,
            account_id=account.account_id,
            state=snapshot.state,
            records=len(snapshot.records),
            pages=snapshot.pages_seen,
            publication=publication,
            issues=snapshot.issues,
            input_kind=snapshot.input_kind,
            raw_document_id=snapshot.raw_document_id,
            collection=snapshot.collection,
        )

    @staticmethod
    def _provider_failure(source_id: str, exc: ConnectorError) -> EnrichmentResult:
        return EnrichmentResult(
            source_id=source_id,
            state=exc.state,
            issues=(Issue(code=exc.code, message=str(exc), retryable=exc.retryable),),
        )

    def _metadata(self, source: Source) -> MetadataReceipt:
        provider = self.providers.get(source)
        if provider is C.NONE:
            setup_issue = self.provider_issues.get(source)
            if setup_issue is not C.NONE:
                return MetadataReceipt(
                    provider=source,
                    state=(
                        SyncState.NEEDS_AUTH
                        if setup_issue.code == S.OAUTH_AUTHORIZATION_REQUIRED_CODE
                        else SyncState.FAILED
                    ),
                    issues=(setup_issue,),
                )
            return MetadataReceipt(
                provider=source,
                state=SyncState.NOT_CONFIGURED,
                issues=(
                    Issue(
                        code=S.METADATA_NOT_CONFIGURED,
                        message=S.METADATA_ISSUES_MESSAGE_THIS_METADATA_PROVIDER_IS_ENABLED_BUT_HAS,
                    ),
                ),
            )

        def coverage_issue() -> Issue | None:
            metadata = self.store.status().get(S.METADATA)
            coverage = metadata.get(source.value) if isinstance(metadata, dict) else C.NONE
            incomplete = coverage.get(S.QUEUE_INCOMPLETE) if isinstance(coverage, dict) else C.NONE
            if isinstance(incomplete, int) and incomplete > C.ZERO:
                return Issue(
                    code=S.QUEUE_NO_LOOKUPS_DUE_CODE,
                    message=S.QUEUE_NO_LOOKUPS_DUE_MESSAGE.format(count=incomplete),
                )
            return C.NONE

        targets = self.store.enrichment_targets(source)
        targets = tuple(
            sorted(
                targets,
                key=lambda book: (
                    book.source != Source.GOODREADS or book.status != ReadingStatus.READ
                ),
            )
        )
        selected = targets[: self.settings.metadata.max_books_per_run]
        if source == Source.OPEN_LIBRARY and not isinstance(provider, BatchMetadataProvider):
            selected = selected[: C.ONE]
        if not selected:
            issue = coverage_issue()
            return MetadataReceipt(
                provider=source,
                state=SyncState.COMPLETE if issue is C.NONE else SyncState.PARTIAL,
                issues=() if issue is C.NONE else (issue,),
            )
        results: tuple[EnrichmentResult, ...]
        requested = len(selected)
        if self.on_metadata_progress is not C.NONE:
            self.on_metadata_progress(source, C.ZERO, requested)
        incremental = C.FALSE
        deferred_issue: Issue | None = C.NONE
        if source == Source.OPEN_LIBRARY and isinstance(provider, BatchMetadataProvider):
            incremental = C.TRUE
            batch_collected: list[EnrichmentResult] = []
            for offset in range(C.ZERO, requested, C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES):
                batch = selected[offset : offset + C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES]
                try:
                    batch_results = provider.lookup_many(batch)
                except ProviderDeferredError as exc:
                    selected = selected[: len(batch_collected)]
                    deferred_issue = Issue(code=exc.code, message=str(exc), retryable=C.TRUE)
                    break
                except ConnectorError as exc:
                    batch_results = tuple(
                        self._provider_failure(book.source_id, exc) for book in batch
                    )
                if len(batch_results) != len(batch) or any(
                    result.source_id != book.source_id
                    for book, result in zip(batch, batch_results, strict=C.FALSE)
                ):
                    break
                for book, result in zip(batch, batch_results, strict=C.TRUE):
                    if any(issue.code == S.MC_TARGET_DEFERRED for issue in result.issues):
                        selected = selected[: len(batch_collected)]
                        deferred_issue = next(
                            (
                                issue
                                for issue in result.issues
                                if issue.code != S.MC_TARGET_DEFERRED
                            ),
                            result.issues[C.ZERO],
                        )
                        break
                    if any(
                        issue.code == S.METADATA_DEFERRED
                        and issue.message
                        == S.ISSUES_MESSAGE_OPEN_LIBRARY_S_TARGETED_BATCH_BUDGET_IS
                        for issue in result.issues
                    ):
                        selected = selected[: len(batch_collected)]
                        deferred_issue = Issue(
                            code=S.METADATA_DEFERRED,
                            message=S.META_RUN_HALTED_MESSAGE,
                            retryable=C.TRUE,
                        )
                        break
                    self.store.save_enrichment(book.source, source, result)
                    batch_collected.append(result)
                    if self.on_metadata_progress is not C.NONE:
                        self.on_metadata_progress(source, len(batch_collected), requested)
                if deferred_issue is not C.NONE:
                    break
            results = tuple(batch_collected)
        else:
            incremental = C.TRUE
            collected: list[EnrichmentResult] = []
            for book in selected:
                try:
                    result = provider.lookup(book)
                except ProviderDeferredError as exc:
                    selected = selected[: len(collected)]
                    deferred_issue = Issue(code=exc.code, message=str(exc), retryable=C.TRUE)
                    break
                except ConnectorError as exc:
                    result = self._provider_failure(book.source_id, exc)
                if result.source_id != book.source_id:
                    break
                self.store.save_enrichment(book.source, source, result)
                collected.append(result)
                if self.on_metadata_progress is not C.NONE:
                    self.on_metadata_progress(source, len(collected), requested)
            results = tuple(collected)
        if len(results) != len(selected) or any(
            (
                result.source_id != book.source_id
                for book, result in zip(selected, results, strict=C.FALSE)
            )
        ):
            saved = results if incremental else ()
            return MetadataReceipt(
                provider=source,
                state=SyncState.FAILED,
                requested=requested,
                processed=sum(result.state == SyncState.COMPLETE for result in saved),
                candidates=sum(len(result.candidates) for result in saved),
                cache_hits=sum(result.cache_hit for result in saved),
                deferred=len(targets) - len(saved),
                issues=(
                    Issue(
                        code=S.METADATA_IDENTITY_MISMATCH,
                        message=S.METADATA_ISSUES_MESSAGE_METADATA_RESULTS_NOT_MATCH_THEIR_REQUESTED,
                    ),
                ),
            )
        issues: list[Issue] = []
        if deferred_issue is not C.NONE:
            issues.append(deferred_issue)
        for index, (book, result) in enumerate(zip(selected, results, strict=C.TRUE), C.ONE):
            if not incremental:
                self.store.save_enrichment(book.source, source, result)
                if self.on_metadata_progress is not C.NONE:
                    self.on_metadata_progress(source, index, requested)
            issues.extend(result.issues)
        deferred = len(targets) - len(selected)
        complete = all(result.state == SyncState.COMPLETE for result in results) and (not deferred)
        if complete and (issue := coverage_issue()) is not C.NONE:
            complete = C.FALSE
            issues.append(issue)
        if deferred:
            issues.append(
                Issue(
                    code=S.METADATA_DEFERRED,
                    message=S.SYNCSERVICE_METADATA_MESSAGE_TEMPLATE.format(v0=deferred),
                )
            )
        return MetadataReceipt(
            provider=source,
            state=SyncState.COMPLETE if complete else SyncState.PARTIAL,
            requested=requested,
            processed=sum(result.state == SyncState.COMPLETE for result in results),
            candidates=sum(len(result.candidates) for result in results),
            cache_hits=sum(result.cache_hit for result in results),
            deferred=deferred,
            issues=tuple(issues),
        )

    def run(self, *, interactive: bool = C.FALSE, trigger: str = S.MANUAL) -> SyncReceipt:
        started = utc_now()
        run_id = self.store.start_run(trigger)
        finalized = C.FALSE
        try:
            accounts = {account.source: account for account in self.settings.accounts}
            sources: list[SourceReceipt] = []
            with self.source_context or nullcontext():
                for source in (Source.STORYGRAPH, Source.GOODREADS):
                    account = accounts.get(source)
                    receipts: Iterable[SourceReceipt]
                    if account is C.NONE:
                        receipts = (
                            SourceReceipt(
                                source=source,
                                state=SyncState.NOT_CONFIGURED,
                                issues=(
                                    Issue(
                                        code=S.ACCOUNT_MISSING,
                                        message=S.RUN_ISSUES_MESSAGE_THIS_READER_ACCOUNT_IS_NOT_CONFIGURED,
                                    ),
                                ),
                            ),
                        )
                    else:
                        collections: list[str | None] = [
                            collection
                            for candidate, collection in self.collection_connectors
                            if candidate == source
                        ]
                        receipts = (
                            self._source(run_id, account, interactive, collection)
                            for collection in collections or [C.NONE]
                        )
                    for receipt in receipts:
                        sources.append(receipt)
                        if self.on_source_complete is not C.NONE:
                            self.on_source_complete(receipt)
            metadata: list[MetadataReceipt] = []
            if self.settings.metadata.google_books:
                metadata.append(self._metadata(Source.GOOGLE_BOOKS))
            if self.settings.metadata.open_library:
                metadata.append(self._metadata(Source.OPEN_LIBRARY))
            sources_complete = all(item.state == SyncState.COMPLETE for item in sources)
            if sources_complete:
                self.store.reconcile_provider_work_matches()
            accounts_complete = sources_complete and all(
                item.input_kind == S.INPUT_LIVE for item in sources
            )
            analytics: AnalyticsReceipt | None = C.NONE
            if self.settings.analytics.enabled and self.analytics is not C.NONE:
                if sources_complete:
                    try:
                        analytics = self.analytics.run(
                            self.settings.accounts, self.settings.analytics
                        )
                    except (BookyError, ValidationError) as exc:
                        analytics = AnalyticsReceipt(
                            state=SyncState.FAILED,
                            issues=(Issue(code=S.AN_FAILED_CODE, message=str(exc)),),
                        )
                else:
                    analytics = AnalyticsReceipt(
                        state=SyncState.PARTIAL,
                        issues=(Issue(code=S.AN_SKIPPED_CODE, message=S.AN_SKIPPED_MESSAGE),),
                    )
            state = (
                SyncState.COMPLETE
                if sources_complete
                and all(item.state == SyncState.COMPLETE for item in metadata)
                and (analytics is C.NONE or analytics.state == SyncState.COMPLETE)
                else SyncState.PARTIAL
            )
            self.store.finish_run(run_id, state)
            finalized = C.TRUE
            return SyncReceipt(
                run_id=run_id,
                state=state,
                started_at=started,
                finished_at=utc_now(),
                account_sync_complete=accounts_complete,
                sources=tuple(sources),
                metadata=tuple(metadata),
                analytics=analytics,
            )
        except KeyboardInterrupt:
            self.store.finish_run(run_id, SyncState.INTERRUPTED)
            finalized = C.TRUE
            raise
        finally:
            if not finalized:
                self.store.finish_run(run_id, SyncState.FAILED)
