from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.config import Settings
from bookystats.errors import ConnectorError, ProviderDeferredError, SnapshotRejectedError
from bookystats.interfaces import (
    BatchMetadataProvider,
    MetadataProvider,
    ProgressCallback,
    SourceConnector,
    Storage,
)
from bookystats.models import (
    Account,
    CollectionProgress,
    CollectionSnapshot,
    EnrichmentResult,
    FieldState,
    Issue,
    Model,
    PublicationResult,
    Source,
    SyncState,
    utc_now,
)


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
    ) -> None:
        self.store = store
        self.settings = settings
        self.connectors = connectors
        self.providers = providers
        self.on_progress = on_progress
        self.provider_issues = provider_issues or {}

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
    def _check_snapshot(account: Account, snapshot: CollectionSnapshot) -> CollectionSnapshot:
        expected_collection = (
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
        missing = [
            field
            for field in C.SYNC_REQUIRED_CAPABILITIES[account.source]
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

    def _source(self, run_id: int, account: Account, interactive: bool) -> SourceReceipt:
        started = utc_now()
        connector = self.connectors.get(account.source)
        if connector is C.NONE:
            return SourceReceipt(
                source=account.source,
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
            snapshot = self._check_snapshot(account, snapshot)
        except ConnectorError as exc:
            snapshot = CollectionSnapshot(
                source=account.source,
                account_id=account.account_id,
                collection=S.LIBRARY if account.source == Source.STORYGRAPH else S.TO_READ,
                state=exc.state,
                started_at=started,
                issues=(Issue(code=exc.code, message=str(exc), retryable=exc.retryable),),
            )
        except ValidationError:
            snapshot = CollectionSnapshot(
                source=account.source,
                account_id=account.account_id,
                collection=S.LIBRARY if account.source == Source.STORYGRAPH else S.TO_READ,
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
                    provider=source, state=SyncState.FAILED, issues=(setup_issue,)
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
        targets = self.store.enrichment_targets(
            source, max_age_days=self.settings.metadata.max_age_days
        )
        selected = targets[: self.settings.metadata.max_books_per_run]
        if not selected:
            return MetadataReceipt(provider=source, state=SyncState.COMPLETE)
        results: tuple[EnrichmentResult, ...]
        requested = len(selected)
        deferred_issue: Issue | None = C.NONE
        if source == Source.OPEN_LIBRARY and isinstance(provider, BatchMetadataProvider):
            try:
                results = provider.lookup_many(selected)
            except ProviderDeferredError as exc:
                selected = ()
                results = ()
                deferred_issue = Issue(code=exc.code, message=str(exc), retryable=C.TRUE)
            except ConnectorError as exc:
                results = tuple(self._provider_failure(book.source_id, exc) for book in selected)
        else:
            if source == Source.OPEN_LIBRARY:
                selected = selected[: C.ONE]
            requested = len(selected)
            collected: list[EnrichmentResult] = []
            for book in selected:
                try:
                    collected.append(provider.lookup(book))
                except ProviderDeferredError as exc:
                    selected = selected[: len(collected)]
                    deferred_issue = Issue(code=exc.code, message=str(exc), retryable=C.TRUE)
                    break
                except ConnectorError as exc:
                    collected.append(self._provider_failure(book.source_id, exc))
            results = tuple(collected)
        if len(results) != len(selected) or any(
            (
                result.source_id != book.source_id
                for book, result in zip(selected, results, strict=C.FALSE)
            )
        ):
            return MetadataReceipt(
                provider=source,
                state=SyncState.FAILED,
                requested=requested,
                deferred=len(targets),
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
        for book, result in zip(selected, results, strict=C.TRUE):
            self.store.save_enrichment(book.source, source, result)
            issues.extend(result.issues)
        deferred = len(targets) - len(selected)
        complete = all(result.state == SyncState.COMPLETE for result in results) and (not deferred)
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
            for source in (Source.STORYGRAPH, Source.GOODREADS):
                account = accounts.get(source)
                if account is C.NONE:
                    sources.append(
                        SourceReceipt(
                            source=source,
                            state=SyncState.NOT_CONFIGURED,
                            issues=(
                                Issue(
                                    code=S.ACCOUNT_MISSING,
                                    message=S.RUN_ISSUES_MESSAGE_THIS_READER_ACCOUNT_IS_NOT_CONFIGURED,
                                ),
                            ),
                        )
                    )
                else:
                    sources.append(self._source(run_id, account, interactive))
            metadata: list[MetadataReceipt] = []
            if self.settings.metadata.google_books:
                metadata.append(self._metadata(Source.GOOGLE_BOOKS))
            if self.settings.metadata.open_library:
                metadata.append(self._metadata(Source.OPEN_LIBRARY))
            sources_complete = all(item.state == SyncState.COMPLETE for item in sources)
            accounts_complete = sources_complete and all(
                item.input_kind == S.INPUT_LIVE for item in sources
            )
            state = (
                SyncState.COMPLETE
                if sources_complete and all(item.state == SyncState.COMPLETE for item in metadata)
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
            )
        except KeyboardInterrupt:
            self.store.finish_run(run_id, SyncState.INTERRUPTED)
            finalized = C.TRUE
            raise
        finally:
            if not finalized:
                self.store.finish_run(run_id, SyncState.FAILED)
