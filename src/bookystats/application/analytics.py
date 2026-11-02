from __future__ import annotations

import hashlib
from concurrent.futures import ProcessPoolExecutor

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.content_analysis import build_content_analysis, description_provenance
from bookystats.application.statistics import build_reading_profile, build_taste, build_watchlist
from bookystats.domain.analytics import (
    AnalysisComponent,
    AnalysisInput,
    AnalyticsReceipt,
    AnalyticsReport,
    AnalyticsSettings,
    Capability,
    Finding,
)
from bookystats.domain.interfaces import AnalyticsInputReader, AnalyticsRepository
from bookystats.domain.models import Account, ReadingStatus, SyncState, canonical_json


def _key(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json(value).encode(S.UTF_8)).hexdigest()


def _taste_input(data: AnalysisInput) -> AnalysisInput:
    return data.model_copy(
        update={
            S.BOOKS: tuple(
                book
                for book in data.books
                if S.READ in book.collections
                or (book.status != ReadingStatus.TO_READ and S.TO_READ not in book.collections)
            ),
            S.AN_SOURCE_COUNTS: {
                scope: count
                for scope, count in data.source_counts.items()
                if scope != S.AN_WATCHLIST_SCOPE
            },
        }
    )


def _component_key(
    data: AnalysisInput, settings: AnalyticsSettings, *, taste_key: str | None = C.NONE
) -> str:
    facts: list[JsonValue] = [
        book.model_dump(
            mode=S.JSON,
            exclude=C.AN_TASTE_BOOK_EXCLUDES
            if taste_key is C.NONE
            else C.AN_SEMANTIC_BOOK_EXCLUDES,
        )
        for book in data.books
    ]
    return _key(
        {
            S.BOOKS: facts,
            S.AN_CONTENT_EVIDENCE: [description_provenance(book) for book in data.books],
            S.AN_SOURCE_COUNTS: {scope: count for scope, count in data.source_counts.items()},
            S.AN_PERSONAL_RATING_RECORDS: data.personal_rating_records,
            S.AN_ACCOUNT_FINGERPRINT: data.manifest.account_fingerprint,
            S.AN_CALCULATION_VERSION_KEY: data.manifest.calculation_version,
            S.SETTINGS: settings.model_dump(mode=S.JSON, exclude=C.AN_SEMANTIC_SETTINGS_EXCLUDES),
            S.AN_TASTE_KEY: taste_key,
            S.AN_AS_OF_DATE: data.as_of[: C.TEN],
        }
    )


def _unbound(component: AnalysisComponent) -> AnalysisComponent:
    return component.model_copy(
        update={
            S.AN_FINDINGS: tuple(
                finding.model_copy(update={S.AN_SOURCE_SNAPSHOT_IDS: ()})
                for finding in component.findings
            )
        }
    )


def _bind(component: AnalysisComponent, data: AnalysisInput) -> AnalysisComponent:
    ids = tuple(
        snapshot.snapshot_id
        for snapshot in data.manifest.snapshots
        if component.kind == C.AnalyticsComponentKind.WATCHLIST or snapshot.collection != S.TO_READ
    )
    return component.model_copy(
        update={
            S.AN_FINDINGS: tuple(
                finding.model_copy(update={S.AN_SOURCE_SNAPSHOT_IDS: ids})
                for finding in component.findings
            )
        }
    )


def _merge_analyses(
    enjoyment: AnalysisComponent,
    profile: AnalysisComponent,
    content: tuple[tuple[Finding, ...], tuple[Capability, ...]],
) -> AnalysisComponent:
    return enjoyment.model_copy(
        update={
            S.AN_FINDINGS: enjoyment.findings + profile.findings + content[C.ZERO],
            S.AN_CAPABILITIES: enjoyment.capabilities + profile.capabilities + content[C.ONE],
        }
    )


def _calculate_components(
    data: AnalysisInput,
    taste_data: AnalysisInput,
    settings: AnalyticsSettings,
    taste_key: str,
    watchlist_key: str,
    taste: AnalysisComponent | None,
    watchlist: AnalysisComponent | None,
) -> tuple[AnalysisComponent, AnalysisComponent, str]:
    mode = S.AN_EXECUTION_CACHED
    if taste is C.NONE and len(taste_data.books) >= C.AN_PARALLEL_MIN_WORKS:
        mode = S.AN_EXECUTION_PARALLEL
        with ProcessPoolExecutor(max_workers=C.AN_PARALLEL_WORKERS) as workers:
            enjoyment_job = workers.submit(
                build_taste, taste_data, settings, key=taste_key, include_profile=C.FALSE
            )
            profile_job = workers.submit(build_reading_profile, taste_data, settings, key=taste_key)
            content_job = workers.submit(build_content_analysis, taste_data, settings)
            enjoyment = enjoyment_job.result()
            watchlist_job = (
                workers.submit(build_watchlist, data, settings, enjoyment, key=watchlist_key)
                if watchlist is C.NONE
                else C.NONE
            )
            taste = _merge_analyses(enjoyment, profile_job.result(), content_job.result())
            if watchlist_job is not C.NONE:
                watchlist = watchlist_job.result()
    elif taste is C.NONE:
        mode = S.AN_EXECUTION_SERIAL
        taste = _merge_analyses(
            build_taste(taste_data, settings, key=taste_key, include_profile=C.FALSE),
            build_reading_profile(taste_data, settings, key=taste_key),
            build_content_analysis(taste_data, settings),
        )
    if watchlist is C.NONE:
        if mode == S.AN_EXECUTION_CACHED:
            mode = S.AN_EXECUTION_SERIAL
        watchlist = build_watchlist(data, settings, taste, key=watchlist_key)
    return taste, watchlist, mode


class AnalyticsService:
    def __init__(self, reader: AnalyticsInputReader, repository: AnalyticsRepository) -> None:
        self.reader = reader
        self.repository = repository

    def run(self, accounts: tuple[Account, ...], settings: AnalyticsSettings) -> AnalyticsReceipt:
        data = self.reader.analytics_input(accounts, settings)
        taste_data = _taste_input(data)
        taste_key = _component_key(taste_data, settings)
        taste = self.repository.get_component(taste_key)
        taste_reused = taste is not C.NONE
        watchlist_key = _component_key(data, settings, taste_key=taste_key)
        watchlist = self.repository.get_component(watchlist_key)
        watchlist_reused = watchlist is not C.NONE
        taste, watchlist, mode = _calculate_components(
            data, taste_data, settings, taste_key, watchlist_key, taste, watchlist
        )
        taste, watchlist = _unbound(taste), _unbound(watchlist)
        if not taste_reused:
            self.repository.save_component(taste)
        if not watchlist_reused:
            self.repository.save_component(watchlist)
        report = self.repository.publish(
            AnalyticsReport(
                manifest=data.manifest,
                as_of=data.as_of,
                taste=_bind(taste, data),
                watchlist=_bind(watchlist, data),
                taste_reused=taste_reused,
                watchlist_reused=watchlist_reused,
                issues=data.issues,
            )
        )
        read = [
            book
            for book in taste_data.books
            if S.READ in book.collections or book.status == ReadingStatus.READ
        ]
        return AnalyticsReceipt(
            state=SyncState.COMPLETE,
            execution_mode=mode,
            report_id=report.report_id,
            findings=len(taste.findings) + len(watchlist.findings),
            rated_read=sum(book.rating is not C.NONE for book in read),
            read_works=len(read),
            taste_reused=taste_reused,
            watchlist_reused=watchlist_reused,
            issues=report.issues,
        )
