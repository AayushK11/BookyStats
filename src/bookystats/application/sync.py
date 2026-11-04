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
    ConfirmedWorkMetadataReader,
    MetadataProvider,
    ProductsRunner,
    ProgressCallback,
    SelectedMetadataReader,
    SourceConnector,
    Storage,
    StreamingMetadataProvider,
)
from bookystats.domain.metadata import missing_fallback_fields
from bookystats.domain.models import (
    Account,
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    EnrichmentResult,
    FieldState,
    Issue,
    MetadataCandidate,
    Model,
    PublicationResult,
    ReadingStatus,
    Source,
    SyncState,
    Verification,
    utc_now,
)
from bookystats.domain.products import ProductReceipt
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
    # Saved per-book results, including cached and incomplete outcomes; not wire requests.
    attempted: int | None = C.NONE
    candidates: int = C.ZERO
    cache_hits: int = C.ZERO
    skipped_by_strategy: int = C.ZERO
    coverage_scope: str = S.ENR_LOOKUP_COVERAGE_SCOPE
    fallback_fields: tuple[str, ...] = ()
    fallback_unresolved: int = C.ZERO
    deferred: int = C.ZERO
    issues: tuple[Issue, ...] = ()

    @property
    def fallback_skipped(self) -> int:
        return self.skipped_by_strategy


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
    products: ProductReceipt | None = C.NONE


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
        provider_factories: Mapping[Source, Callable[[], MetadataProvider | Issue]] | None = C.NONE,
        collection_connectors: Mapping[tuple[Source, str], SourceConnector] | None = C.NONE,
        source_context: AbstractContextManager[object] | None = C.NONE,
        on_source_complete: Callable[[SourceReceipt], None] | None = C.NONE,
        on_metadata_progress: Callable[[Source, int, int], None] | None = C.NONE,
        analytics: AnalyticsRunner | None = C.NONE,
        products: ProductsRunner | None = C.NONE,
        on_event: Callable[[str], None] | None = C.NONE,
    ) -> None:
        self.store = store
        self.settings = settings
        self.connectors = connectors
        self.providers = dict(providers)
        self.on_progress = on_progress
        self.provider_issues = dict(provider_issues or {})
        self.provider_factories = provider_factories or {}
        self.collection_connectors = collection_connectors or {}
        self.source_context = source_context
        self.on_source_complete = on_source_complete
        self.on_metadata_progress = on_metadata_progress
        self.analytics = analytics
        self.products = products
        self.on_event = on_event

    def _event(self, message: str) -> None:
        if self.on_event is not C.NONE:
            self.on_event(message)

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
                        if field in C.DTX_PERSONAL_FIELDS
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

    def _fallback_gaps(self, book: BookRecord) -> tuple[str, ...]:
        candidates: list[MetadataCandidate] = []
        work_candidates: tuple[MetadataCandidate, ...] = ()
        if isinstance(self.store, SelectedMetadataReader):
            account = next(
                (account for account in self.settings.accounts if account.source == book.source),
                C.NONE,
            )
            if account is not C.NONE:
                for item in self.store.metadata_for(
                    book.source, account.account_id, book.source_id
                ):
                    if item.get(S.STALE_IDENTITY) is not C.FALSE:
                        continue
                    candidate = MetadataCandidate.model_validate(item.get(S.CANDIDATE))
                    if item.get(S.PROVIDER) == candidate.provider.value:
                        candidates.append(candidate)
                if isinstance(self.store, ConfirmedWorkMetadataReader):
                    work_candidates = self.store.metadata_for_work(
                        book.source, account.account_id, book.source_id
                    )
        return missing_fallback_fields(book, candidates, work_candidates=work_candidates)

    def _metadata(self, source: Source) -> MetadataReceipt:
        targets = self.store.enrichment_targets(source)
        fallback_skipped = C.ZERO
        fallback_fields: tuple[str, ...] = ()
        if (
            source == Source.GOOGLE_BOOKS
            and self.settings.metadata.open_library
            and self.settings.metadata.strategy == S.ENR_STRATEGY_OPEN_LIBRARY_FIRST
        ):
            fallback_fields = C.ENR_FALLBACK_FIELDS
            filtered = [book for book in targets if self._fallback_gaps(book)]
            fallback_skipped = len(targets) - len(filtered)
            targets = tuple(filtered)
        if (
            not targets
            and fallback_fields
            and (
                fallback_skipped
                or not any(self._fallback_gaps(book) for book in self.store.active_records())
            )
        ):
            receipt = MetadataReceipt(
                provider=source,
                state=SyncState.COMPLETE,
                attempted=C.ZERO,
            )
        else:
            receipt = self._metadata_targets(source, targets)
        unresolved = (
            sum(bool(self._fallback_gaps(book)) for book in self.store.active_records())
            if fallback_fields
            else C.ZERO
        )
        if unresolved and receipt.state == SyncState.COMPLETE:
            receipt = receipt.model_copy(
                update={
                    S.STATE: SyncState.PARTIAL,
                    S.ISSUES: (
                        *receipt.issues,
                        Issue(
                            code=S.ENR_GAPS_REMAIN_CODE,
                            message=S.ENR_GAPS_REMAIN_MESSAGE.format(count=unresolved),
                        ),
                    ),
                }
            )
        return receipt.model_copy(
            update={
                S.ENR_SKIPPED_BY_STRATEGY: fallback_skipped,
                S.ENR_COVERAGE_SCOPE: (
                    S.WIKIDATA_SCOPE
                    if source == Source.WIKIDATA
                    else S.ENR_CORE_COVERAGE_SCOPE
                    if fallback_fields
                    else S.ENR_LOOKUP_COVERAGE_SCOPE
                ),
                S.ENR_FALLBACK_FIELDS: fallback_fields,
                S.ENR_FALLBACK_UNRESOLVED: unresolved,
            }
        )

    def _metadata_targets(self, source: Source, targets: tuple[BookRecord, ...]) -> MetadataReceipt:
        provider = self.providers.get(source)
        if provider is C.NONE and targets and source in self.provider_factories:
            initialized = self.provider_factories[source]()
            if isinstance(initialized, Issue):
                self.provider_issues[source] = initialized
            else:
                provider = initialized
                self.providers[source] = provider
        if provider is C.NONE:
            setup_issue = self.provider_issues.get(source)
            if setup_issue is not C.NONE:
                return MetadataReceipt(
                    provider=source,
                    attempted=C.ZERO,
                    deferred=len(targets),
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
                attempted=C.ZERO,
                deferred=len(targets),
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

        targets = tuple(
            sorted(
                targets,
                key=lambda book: (
                    book.source != Source.GOODREADS or book.status != ReadingStatus.READ
                ),
            )
        )
        selected = targets[: self.settings.metadata.max_books_per_run]
        if source == Source.OPEN_LIBRARY and not isinstance(
            provider, (BatchMetadataProvider, StreamingMetadataProvider)
        ):
            selected = selected[: C.ONE]
        if not selected:
            issue = coverage_issue()
            return MetadataReceipt(
                provider=source,
                state=SyncState.COMPLETE if issue is C.NONE else SyncState.PARTIAL,
                attempted=C.ZERO,
                issues=() if issue is C.NONE else (issue,),
            )
        results: tuple[EnrichmentResult, ...]
        requested = len(selected)
        if self.on_metadata_progress is not C.NONE:
            self.on_metadata_progress(source, C.ZERO, requested)
        incremental = C.FALSE
        invalid_batch = C.FALSE
        deferred_issue: Issue | None = C.NONE
        if source == Source.OPEN_LIBRARY and isinstance(provider, StreamingMetadataProvider):
            incremental = C.TRUE
            streamed: list[EnrichmentResult] = []
            for offset in range(C.ZERO, requested, C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES):
                batch = selected[offset : offset + C.OPEN_LIBRARY_MAX_BATCH_IDENTITIES]
                emitted = C.ZERO
                try:
                    for result in provider.iter_lookup_many(batch):
                        if emitted >= len(batch) or result.source_id != batch[emitted].source_id:
                            invalid_batch = C.TRUE
                            break
                        book = batch[emitted]
                        if any(
                            issue.code == S.MC_TARGET_DEFERRED
                            or (
                                issue.code == S.METADATA_DEFERRED
                                and issue.message
                                == S.ISSUES_MESSAGE_OPEN_LIBRARY_S_TARGETED_BATCH_BUDGET_IS
                            )
                            for issue in result.issues
                        ):
                            deferred_issue = next(
                                (
                                    issue
                                    for issue in result.issues
                                    if issue.code != S.MC_TARGET_DEFERRED
                                ),
                                result.issues[C.ZERO],
                            )
                            break
                        self.store.save_enrichment(book.source, source, result)
                        streamed.append(result)
                        emitted += C.ONE
                        if self.on_metadata_progress is not C.NONE:
                            self.on_metadata_progress(source, len(streamed), requested)
                except ProviderDeferredError as exc:
                    deferred_issue = Issue(code=exc.code, message=str(exc), retryable=C.TRUE)
                except ConnectorError as exc:
                    if emitted < len(batch):
                        book = batch[emitted]
                        result = self._provider_failure(book.source_id, exc)
                        self.store.save_enrichment(book.source, source, result)
                        streamed.append(result)
                        if self.on_metadata_progress is not C.NONE:
                            self.on_metadata_progress(source, len(streamed), requested)
                    deferred_issue = Issue(code=exc.code, message=str(exc), retryable=exc.retryable)
                if deferred_issue is not C.NONE:
                    selected = selected[: len(streamed)]
                    break
                if invalid_batch or emitted != len(batch):
                    invalid_batch = C.TRUE
                    break
            results = tuple(streamed)
        elif source == Source.OPEN_LIBRARY and isinstance(provider, BatchMetadataProvider):
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
        if (
            invalid_batch
            or len(results) != len(selected)
            or any(
                (
                    result.source_id != book.source_id
                    for book, result in zip(selected, results, strict=C.FALSE)
                )
            )
        ):
            saved = results if incremental else ()
            return MetadataReceipt(
                provider=source,
                state=SyncState.FAILED,
                requested=requested,
                processed=sum(result.state == SyncState.COMPLETE for result in saved),
                attempted=len(saved),
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
            attempted=len(results),
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
            self._event(S.PROD_RUN_STARTED.format(run_id=run_id))
            self._event(S.PROD_STAGE_SOURCES)
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
            provider_order = (
                C.METADATA_OPEN_LIBRARY_FIRST_ORDER
                if self.settings.metadata.strategy == S.ENR_STRATEGY_OPEN_LIBRARY_FIRST
                else C.METADATA_INDEPENDENT_ORDER
            )
            enabled = {
                Source.GOOGLE_BOOKS: self.settings.metadata.google_books,
                Source.OPEN_LIBRARY: self.settings.metadata.open_library,
                Source.WIKIDATA: self.settings.metadata.wikidata,
            }
            if not any(enabled.values()):
                self._event(S.LOG3_LOOKUPS_OFF)
            for provider in provider_order:
                if enabled[provider]:
                    self._event(S.PROD_STAGE_METADATA.format(provider=provider.value))
                    metadata.append(self._metadata(provider))
                    result = metadata[-C.ONE]
                    self._event(
                        S.LOG3_METADATA_RESULT.format(
                            provider=C.LOG3_SOURCE_NAMES.get(provider.value, provider.value),
                            attempted=result.attempted
                            if result.attempted is not C.NONE
                            else result.processed,
                            complete=result.processed,
                            waiting=result.deferred,
                            state=result.state.value,
                        )
                    )
            sources_complete = all(item.state == SyncState.COMPLETE for item in sources)
            if sources_complete:
                self._event(S.PROD_STAGE_RECONCILE)
                self.store.reconcile_provider_work_matches()
            accounts_complete = sources_complete and all(
                item.input_kind == S.INPUT_LIVE for item in sources
            )
            analytics: AnalyticsReceipt | None = C.NONE
            if self.settings.analytics.enabled and self.analytics is not C.NONE:
                if sources_complete:
                    self._event(S.PROD_STAGE_ANALYTICS)
                    try:
                        analytics = self.analytics.run(
                            self.settings.accounts, self.settings.analytics
                        )
                    except (BookyError, ValidationError) as exc:
                        analytics = AnalyticsReceipt(
                            state=SyncState.FAILED,
                            issues=(
                                Issue(
                                    code=S.AN_FAILED_CODE,
                                    message=S.OPLOG_ANALYTICS_FAILED.format(
                                        error_type=type(exc).__name__
                                    )
                                    if isinstance(exc, ValidationError)
                                    else str(exc),
                                ),
                            ),
                        )
                else:
                    analytics = AnalyticsReceipt(
                        state=SyncState.PARTIAL,
                        issues=(Issue(code=S.AN_SKIPPED_CODE, message=S.AN_SKIPPED_MESSAGE),),
                    )
                self._event(
                    S.PROD_STAGE_RESULT.format(
                        stage=S.PROD_ANALYTICS_STAGE, state=analytics.state.value
                    )
                )
            products: ProductReceipt | None = C.NONE
            if self.products is not C.NONE:
                if analytics is not C.NONE and analytics.state == SyncState.COMPLETE:
                    self._event(S.PROD_STAGE_PRODUCTS)
                    try:
                        products = self.products.run(
                            self.settings.accounts, self.settings.analytics, analytics
                        )
                    except (BookyError, ValidationError, OSError) as exc:
                        products = ProductReceipt(
                            state=SyncState.FAILED,
                            analytics_report_id=analytics.report_id,
                            issues=(
                                Issue(
                                    code=S.PROD_FAILED_CODE,
                                    message=S.PROD_FAILED_MESSAGE.format(
                                        error_type=type(exc).__name__
                                    ),
                                ),
                            ),
                        )
                else:
                    products = ProductReceipt(
                        state=SyncState.PARTIAL,
                        issues=(Issue(code=S.PROD_SKIPPED_CODE, message=S.PROD_SKIPPED_MESSAGE),),
                    )
                self._event(
                    S.PROD_STAGE_RESULT.format(stage=S.PROD_PRODUCTS, state=products.state.value)
                )
            state = (
                SyncState.COMPLETE
                if sources_complete
                and all(item.state == SyncState.COMPLETE for item in metadata)
                and (analytics is C.NONE or analytics.state == SyncState.COMPLETE)
                and (products is C.NONE or products.state == SyncState.COMPLETE)
                else SyncState.PARTIAL
            )
            self.store.finish_run(run_id, state)
            self._event(S.PROD_STAGE_FINISHED.format(run_id=run_id, state=state.value))
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
                products=products,
            )
        except KeyboardInterrupt:
            self.store.finish_run(run_id, SyncState.INTERRUPTED)
            finalized = C.TRUE
            raise
        finally:
            if not finalized:
                self.store.finish_run(run_id, SyncState.FAILED)
