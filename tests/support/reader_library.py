from __future__ import annotations

from functools import cache
from typing import NamedTuple

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.content_analysis import build_content_analysis
from bookystats.application.metadata_quality import build_metadata_quality
from bookystats.application.statistics import build_taste, build_watchlist
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisEvidence,
    AnalysisInput,
    AnalysisManifest,
    AnalysisSnapshot,
    AnalyticsReport,
    AnalyticsSettings,
)
from bookystats.domain.metadata_quality import MetadataQualityReport
from bookystats.domain.models import (
    FieldState,
    Observation,
    PartialDate,
    ReadingEvent,
    ReadingStatus,
    Source,
    SyncState,
)
from bookystats.domain.recommendations import RecommendationReport, build_recommendations


class Library(NamedTuple):
    data: AnalysisInput
    analysis: AnalyticsReport
    recommendations: RecommendationReport
    quality: MetadataQualityReport


def _date(year: int, month: int, day: int) -> PartialDate:
    return PartialDate(value=S.RPT_TEST_DATE.format(year=year, month=month, day=day))


def _evidence(
    work_id: int, field: str, value: JsonValue, public_url: str | None = C.NONE
) -> AnalysisEvidence:
    return AnalysisEvidence(
        source=Source.GOODREADS.value,
        source_id=str(work_id),
        public_url=public_url,
        observation=Observation(
            field=field,
            value=value,
            state=FieldState.PRESENT,
            source_url=S.RPT_TEST_PRIVATE_URL.format(work_id=work_id),
            observed_at=S.RPT_TEST_AS_OF,
        ),
    )


def _read(index: int) -> AnalysisBook:
    work_id = index + C.ONE
    genres = C.RPT_TEST_GENRES
    primary = genres[(index * C.THREE + index // C.SEVEN) % len(genres)]
    shelved = (primary,) if index % C.FIVE else (primary, genres[(index + C.FOUR) % len(genres)])
    rating = (
        C.NONE if index % C.NINE == C.FOUR else C.RPT_TEST_RATINGS[index % len(C.RPT_TEST_RATINGS)]
    )
    pages = C.RPT_TEST_PAGE_OVERRIDES.get(
        index, C.RPT_TEST_PAGE_BASE + (index * C.RPT_TEST_PAGE_STEP) % C.RPT_TEST_PAGE_SPAN
    )
    year = C.RPT_TEST_YEAR_OVERRIDES.get(
        index, C.RPT_TEST_YEAR_BASE + (index * C.RPT_TEST_YEAR_STEP) % C.RPT_TEST_YEAR_SPAN
    )
    months = len(C.RPT_MONTHS)
    finished = _date(
        C.RPT_TEST_FIRST_YEAR + index // months,
        (index * C.FIVE) % months + C.ONE,
        index % C.RPT_TEST_DAY_CYCLE + C.ONE,
    )
    events = (
        (ReadingEvent(finished=finished, status=ReadingStatus.READ),)
        if index % C.EIGHT != C.THREE
        else ()
    )
    community: dict[str, float] = {}
    evidence: list[AnalysisEvidence] = []
    if index % C.THREE != C.TWO:
        community[S.GOODREADS] = round(
            C.RPT_TEST_COMMUNITY_BASE + (index % C.TEN) * C.RPT_TEST_COMMUNITY_STEP, C.TWO
        )
        sample = C.RPT_TEST_SMALL_SAMPLE if index % C.SEVEN == C.ZERO else C.RPT_TEST_LARGE_SAMPLE
        evidence.append(_evidence(work_id, S.COMMUNITY_RATINGS_COUNT, sample))
    described = index % C.TWO == C.ZERO
    if described:
        public = S.RPT_TEST_PUBLIC_URL.format(work_id=C.RPT_TEST_PUBLIC_BASE + work_id)
        evidence.append(_evidence(work_id, S.DESCRIPTION, S.CONTENT_ANALYSIS_TEST_TEXT, public))
    titles = C.RPT_TEST_TITLES
    title = titles[index % len(titles)]
    if index >= len(titles):
        title = S.RPT_TEST_REPEAT_TITLE.format(title=title, round=index // len(titles) + C.ONE)
    return AnalysisBook(
        work_id=work_id,
        source_ids=(str(work_id),),
        title=title,
        authors=(C.RPT_TEST_AUTHOR_POOL[index % len(C.RPT_TEST_AUTHOR_POOL)],),
        collections=(S.READ,),
        status=ReadingStatus.READ,
        rating=rating,
        rating_conflict=index in C.RPT_TEST_CONFLICTS,
        features={S.GENRES: shelved},
        page_count=pages,
        first_publication_year=year,
        description=S.CONTENT_ANALYSIS_TEST_TEXT if described else C.NONE,
        community_ratings=community,
        reading_events=events,
        added_at=_date(
            C.RPT_TEST_ADDED_YEAR + index // C.RPT_TEST_ADDED_SPAN,
            index % C.NINE + C.ONE,
            C.RPT_TEST_ADDED_DAY,
        ),
        field_states={S.DESCRIPTION: FieldState.PRESENT} if described else {},
        evidence=tuple(evidence),
    )


def _waiting(read: int, index: int) -> AnalysisBook:
    work_id = read + index + C.ONE
    titles = C.RPT_TEST_TITLES
    pool = C.RPT_TEST_AUTHOR_POOL
    genres = C.RPT_TEST_GENRES
    author = (
        pool[(index * C.FIVE) % len(pool)]
        if index % C.THREE == C.ZERO
        else S.RPT_TEST_NEW_AUTHOR.format(index=index)
    )
    return AnalysisBook(
        work_id=work_id,
        source_ids=(str(work_id),),
        title=S.RPT_TEST_WAIT_TITLE.format(
            index=index + C.ONE, title=titles[(index + C.THREE) % len(titles)]
        ),
        authors=(author,),
        collections=(S.TO_READ,),
        status=ReadingStatus.TO_READ,
        features={S.GENRES: (genres[(index * C.TWO) % len(genres)],)} if index % C.FOUR else {},
        page_count=C.RPT_TEST_WAIT_PAGE_BASE + index * C.RPT_TEST_WAIT_PAGE_STEP
        if index % C.FIVE
        else C.NONE,
        first_publication_year=C.RPT_TEST_WAIT_YEAR_BASE + index if index % C.SIX else C.NONE,
        added_at=_date(
            C.RPT_TEST_WAIT_ADDED_YEAR + index // C.NINE,
            index % C.NINE + C.ONE,
            C.RPT_TEST_WAIT_ADDED_DAY,
        ),
    )


@cache
def library(read: int = C.RPT_TEST_RICH_READ, watch: int = C.RPT_TEST_RICH_WATCH) -> Library:
    manifest = AnalysisManifest(
        account_fingerprint=S.RPT_TEST_ACCOUNT,
        settings_hash=S.RPT_TEST_HASH,
        snapshots=(
            AnalysisSnapshot(
                source=Source.GOODREADS,
                account_id=S.RPT_TEST_ACCOUNT,
                collection=S.READ,
                snapshot_id=C.ONE,
                input_kind=S.INPUT_FILE,
                finished_at=S.RPT_TEST_AS_OF,
                records=read,
                attempt_state=SyncState.COMPLETE,
            ),
        ),
    )
    data = AnalysisInput(
        books=(
            *(_read(index) for index in range(read)),
            *(_waiting(read, index) for index in range(watch)),
        ),
        manifest=manifest,
        as_of=S.RPT_TEST_AS_OF,
        personal_rating_records=read,
    )
    taste = build_taste(data, manifest.settings, key=S.RPT_TEST_KEY)
    findings, capabilities = build_content_analysis(data, AnalyticsSettings(min_group_size=C.THREE))
    taste = taste.model_copy(
        update={
            S.AN_FINDINGS: (*taste.findings, *findings),
            S.AN_CAPABILITIES: (*taste.capabilities, *capabilities),
        }
    )
    analysis = AnalyticsReport(
        report_id=C.ONE,
        manifest=manifest,
        as_of=S.RPT_TEST_AS_OF,
        created_at=S.RPT_TEST_AS_OF,
        taste=taste,
        watchlist=build_watchlist(data, manifest.settings, taste, key=S.RPT_TEST_KEY),
    )
    return Library(
        data=data,
        analysis=analysis,
        recommendations=build_recommendations(data, analysis),
        quality=build_metadata_quality(data, analysis, {}),
    )
