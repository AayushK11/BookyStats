from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from typing import Protocol

from pydantic import Field, JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisInput,
    AnalysisManifest,
    AnalyticsReport,
)
from bookystats.domain.models import FieldState, PartialDate, ReadingStatus, Source, canonical_json


class RecommendationExample(C.Model):
    work_id: int = Field(ge=C.ONE)
    title: str
    rating: float = Field(ge=C.ZERO, le=C.FIVE)


class RecommendationComponent(C.Model):
    feature: str
    label: str
    contribution: float
    sample_size: int = Field(ge=C.ONE)
    supporting_work_ids: tuple[int, ...]


class RecommendationItem(C.Model):
    work_id: int = Field(ge=C.ONE)
    title: str
    authors: tuple[str, ...]
    source_ids: tuple[str, ...]
    status: str
    ranking_score: float | None = C.NONE
    score_label: str = S.REC_SCORE_LABEL
    reasons: tuple[str, ...] = ()
    mismatches: tuple[str, ...] = ()
    missingness: tuple[str, ...] = ()
    supporting_books: tuple[RecommendationExample, ...] = ()
    components: tuple[RecommendationComponent, ...] = ()
    identity_tier: str = S.REC_CONFIRMED
    feature_tier: str = S.REC_ABSENT
    preference_tier: str = S.REC_ABSENT
    added_at: str | None = C.NONE


class RecommendationReport(C.Model):
    report_id: int | None = C.NONE
    key: str
    policy_version: str = S.REC_POLICY_VERSION
    as_of: str
    manifest: AnalysisManifest
    analysis_report_id: int | None = C.NONE
    ranked: tuple[RecommendationItem, ...] = ()
    unrankable: tuple[RecommendationItem, ...] = ()
    excluded: tuple[RecommendationItem, ...] = ()
    shortlist: tuple[RecommendationItem, ...] = ()
    limitations: tuple[str, ...] = C.REC_LIMITATIONS
    source_snapshot_ids: tuple[int, ...] = ()
    reused: bool = C.FALSE


class RecommendationRepository(Protocol):
    def get_cached(self, key: str) -> RecommendationReport | None:
        pass

    def publish(self, report: RecommendationReport) -> RecommendationReport:
        pass

    def latest(self) -> RecommendationReport | None:
        pass


def _normalize(value: str) -> str:
    return S.SPACE.join(value.split()).casefold()


def _read(book: AnalysisBook) -> bool:
    return (
        S.READ in book.collections
        or book.status == ReadingStatus.READ
        or any(
            event.status == ReadingStatus.READ or event.finished is not C.NONE
            for event in book.reading_events
        )
    )


def _features(book: AnalysisBook) -> tuple[tuple[str, str], ...]:
    shared = {
        (feature, _normalize(label))
        for feature in C.REC_SHARED_FEATURES
        for label in book.features.get(feature, ())
        if label.strip()
    }
    shared.update((S.REC_AUTHOR, _normalize(author)) for author in book.authors if author.strip())
    return tuple(sorted(shared))


def _series(book: AnalysisBook) -> tuple[str, ...]:
    verified = {
        _normalize(label)
        for item in book.evidence
        if item.source in C.REC_SERIES_SOURCES
        and item.observation.field == S.SERIES
        and item.observation.scope == S.WORK
        and item.observation.state == FieldState.PRESENT
        for label in (
            item.observation.value
            if isinstance(item.observation.value, list)
            else [item.observation.value]
        )
        if isinstance(label, str)
    }
    return tuple(sorted(verified.intersection(map(_normalize, book.features.get(S.SERIES, ())))))


def _publication_dates(book: AnalysisBook) -> tuple[tuple[str, str], ...]:
    result = []
    for scope, fields in C.REC_PUBLICATION_FIELDS:
        items = [
            item
            for item in book.evidence
            if item.observation.scope == scope
            and item.observation.field in fields
            and item.source in C.REC_PUBLICATION_SOURCES
            and item.observation.state == FieldState.PRESENT
        ]
        preferred = [item for item in items if item.source == Source.GOODREADS.value]
        dates = set()
        for item in preferred or items:
            value = item.observation.value
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                continue
            try:
                date = PartialDate(value=str(value))
            except ValueError:
                continue
            year = book.first_publication_year if scope == S.WORK else book.publication_year
            if year == int(date.value[: C.REC_YEAR_SLICE]):
                dates.add(date.value)
        if len(dates) == C.ONE:
            result.append((scope, next(iter(dates))))
    return tuple(result)


def _grouped(
    data: AnalysisInput,
) -> tuple[tuple[AnalysisBook, ...], dict[int, tuple[AnalysisBook, ...]]]:
    groups: dict[int, list[AnalysisBook]] = defaultdict(list)
    for book in data.books:
        groups[book.work_id].append(book)
    grouped = {work_id: tuple(books) for work_id, books in sorted(groups.items())}
    # Conflicting edition facts are never silently combined into one candidate.
    selected = tuple(
        min(
            books,
            key=lambda book: (
                S.TO_READ not in book.collections and book.status != ReadingStatus.TO_READ,
                book.title.casefold(),
                canonical_json(book.model_dump(mode=S.JSON, exclude=C.REC_REPRESENTATIVE_EXCLUDES)),
            ),
        )
        for _, books in sorted(grouped.items())
    )
    return selected, grouped


@C.frozen_dataclass
class _Signal:
    component: RecommendationComponent
    examples: tuple[RecommendationExample, ...]
    reason: str
    mismatch: str | None


def _signals(
    index: dict[tuple[str, str], list[AnalysisBook]], baseline: float
) -> dict[tuple[str, str], _Signal]:
    result = {}
    for (feature, label), matches in index.items():
        total = sum(match.rating for match in matches if match.rating is not C.NONE)
        contribution = (total - baseline * len(matches)) / (len(matches) + C.REC_PRIOR_STRENGTH)
        disliked = sum(
            match.rating is not C.NONE and match.rating < C.REC_MISMATCH_THRESHOLD
            for match in matches
        )
        result[(feature, label)] = _Signal(
            component=RecommendationComponent(
                feature=feature,
                label=label,
                contribution=round(contribution, C.REC_SCORE_PRECISION),
                sample_size=len(matches),
                supporting_work_ids=tuple(sorted(match.work_id for match in matches)),
            ),
            examples=tuple(
                RecommendationExample(work_id=match.work_id, title=match.title, rating=match.rating)
                for match in sorted(
                    matches,
                    key=lambda match: (
                        -(match.rating if match.rating is not C.NONE else C.ZERO),
                        match.work_id,
                    ),
                )[: C.REC_EXAMPLE_LIMIT]
                if match.rating is not C.NONE
            ),
            reason=S.REC_SUPPORT.format(feature=feature, label=label, count=len(matches)),
            mismatch=S.REC_MISMATCH.format(feature=feature, label=label, count=disliked)
            if disliked
            else C.NONE,
        )
    return result


def recommendation_key(data: AnalysisInput, analysis: AnalyticsReport) -> str:
    facts: list[JsonValue] = []
    for book in sorted(
        data.books,
        key=lambda item: (item.work_id, canonical_json(item.model_dump(mode=S.JSON))),
    ):
        facts.append(
            {
                S.REC_WORK_ID: book.work_id,
                S.REC_TITLE: book.title,
                S.REC_AUTHOR_NAMES: list(book.authors),
                S.REC_COLLECTIONS: list(book.collections),
                S.REC_STATUS: book.status.value,
                S.REC_RATING: book.rating if _read(book) and not book.rating_conflict else C.NONE,
                S.REC_FEATURES: [list(feature) for feature in _features(book)],
                S.SERIES: list(_series(book)),
                S.REC_YEAR: book.publication_year,
                S.REC_ORIGINAL_YEAR: book.first_publication_year,
                S.REC_EVENTS: [
                    {
                        S.STATUS: event.status.value,
                        S.FINISHED: event.finished.value
                        if event.finished is not C.NONE
                        else C.NONE,
                    }
                    for event in book.reading_events
                ],
                S.REC_ADDED_AT: book.added_at.value if book.added_at is not C.NONE else C.NONE,
                S.REC_POSSIBLE_TARGETS: [
                    {
                        S.REC_WORK_ID: match.work_id,
                        S.SOURCE: match.source.value,
                        S.SOURCE_ID: match.source_id,
                    }
                    for match in book.possible_read_matches
                ],
                S.REC_PUBLICATION_DATES: [list(value) for value in _publication_dates(book)],
            }
        )
    facts.sort(key=canonical_json)
    payload: JsonValue = {
        S.REC_POLICY: S.REC_POLICY_VERSION,
        S.REC_CALCULATION_VERSION: data.manifest.calculation_version,
        S.REC_AS_OF: data.as_of[: C.TEN],
        S.REC_ACCOUNT: data.manifest.account_fingerprint,
        S.REC_BOOKS: facts,
        S.REC_ISSUES: [{S.CODE: issue.code, S.SOURCE_ID: issue.source_id} for issue in data.issues],
    }
    return hashlib.sha256(canonical_json(payload).encode(S.UTF_8)).hexdigest()


def _missing(book: AnalysisBook) -> tuple[str, ...]:
    missing = []
    if book.first_publication_year is C.NONE:
        missing.append(S.REC_UNKNOWN_PUBLICATION)
    if book.publication_year is C.NONE:
        missing.append(S.REC_UNKNOWN_EDITION)
    if not book.features.get(S.GENRES):
        missing.append(S.REC_UNKNOWN_GENRE)
    if not book.features.get(S.AN_APPETITE):
        missing.append(S.REC_UNKNOWN_APPETITE)
    if not _series(book):
        missing.append(S.REC_UNKNOWN_SERIES)
    return tuple(missing)


def _eligible(variants: tuple[AnalysisBook, ...], year: int) -> str | None:
    if any(_read(book) for book in variants):
        return S.REC_READ
    if any(book.status == ReadingStatus.CURRENTLY_READING for book in variants):
        return S.REC_ACTIVE
    if any(book.status in C.REC_RECONSIDER_STATUSES for book in variants):
        return S.REC_RECONSIDER
    if any(
        book.first_publication_year is not C.NONE and book.first_publication_year > year
        for book in variants
    ):
        return S.REC_UNRELEASED_WORK
    return C.NONE


def _shortlist(
    ranked: Iterable[RecommendationItem], books: dict[int, AnalysisBook]
) -> tuple[RecommendationItem, ...]:
    authors: dict[str, int] = defaultdict(int)
    series: dict[str, int] = defaultdict(int)
    selected = []
    for item in ranked:
        names = {_normalize(author) for author in item.authors if author.strip()}
        labels = _series(books[item.work_id])
        if any(authors[name] >= C.REC_AUTHOR_CAP for name in names) or any(
            series[label] >= C.REC_SERIES_CAP for label in labels
        ):
            continue
        selected.append(item)
        for name in names:
            authors[name] += C.ONE
        for label in labels:
            series[label] += C.ONE
        if len(selected) == C.REC_SHORTLIST_SIZE:
            break
    return tuple(selected)


def build_recommendations(data: AnalysisInput, analysis: AnalyticsReport) -> RecommendationReport:
    if data.manifest != analysis.manifest or (
        analysis.as_of is not C.NONE and data.as_of[: C.TEN] != analysis.as_of[: C.TEN]
    ):
        raise ValueError(S.REC_COMPATIBILITY_ERROR)
    books, groups = _grouped(data)
    read = [
        min(
            (variant for variant in variants if _read(variant)),
            key=lambda variant: (
                variant.title.casefold(),
                canonical_json(variant.model_dump(mode=S.JSON)),
            ),
        )
        for variants in groups.values()
        if any(_read(variant) for variant in variants)
    ]
    rated = [
        book
        for book in read
        if book.rating is not C.NONE
        and not book.rating_conflict
        and len(
            {variant.rating for variant in groups[book.work_id] if variant.rating is not C.NONE}
        )
        <= C.ONE
    ]
    baseline = (
        sum(book.rating for book in rated if book.rating is not C.NONE) / len(rated)
        if rated
        else C.ZERO
    )
    index: dict[tuple[str, str], list[AnalysisBook]] = defaultdict(list)
    for book in rated:
        for token in _features(book):
            index[token].append(book)
    signals = _signals(index, baseline)
    read_names = {
        (_normalize(book.title), _normalize(author))
        for book in read
        for author in book.authors
        if author.strip()
    }
    familiar = {_normalize(author) for book in read for author in book.authors if author.strip()}
    questionable = {
        issue.source_id
        for issue in data.issues
        if any(token in issue.code.casefold() for token in C.REC_AMBIGUITY_TOKENS)
        and issue.source_id is not C.NONE
    }
    ranked, unrankable, excluded = [], [], []
    for book in books:
        variants = groups[book.work_id]
        if not any(
            S.TO_READ in item.collections or item.status == ReadingStatus.TO_READ
            for item in variants
        ):
            continue
        reason = _eligible(variants, int(data.as_of[: C.REC_YEAR_SLICE]))
        if reason is C.NONE and (
            book.publication_year is not C.NONE
            and book.publication_year > int(data.as_of[: C.REC_YEAR_SLICE])
        ):
            reason = S.REC_UNRELEASED_EDITION
        if reason is C.NONE:
            for scope, date in _publication_dates(book):
                if date > data.as_of[: len(date)]:
                    reason = S.REC_UNRELEASED_WORK if scope == S.WORK else S.REC_UNRELEASED_EDITION
                    break
        possible = (
            bool(book.possible_read_matches)
            or any(
                (_normalize(book.title), _normalize(author)) in read_names
                for author in book.authors
                if author.strip()
            )
            or bool(set(book.source_ids).intersection(questionable))
        )
        item = RecommendationItem(
            work_id=book.work_id,
            title=book.title,
            authors=book.authors,
            source_ids=tuple(
                sorted({value for variant in variants for value in variant.source_ids})
            ),
            status=S.REC_EXCLUDED if reason is not C.NONE else S.REC_UNRANKABLE,
            missingness=_missing(book),
            added_at=book.added_at.value if book.added_at is not C.NONE else C.NONE,
        )
        if reason is not C.NONE:
            excluded.append(item.model_copy(update={S.REC_REASONS: (reason,)}))
            continue
        if possible:
            unrankable.append(
                item.model_copy(
                    update={
                        S.REC_REASONS: (S.REC_POSSIBLE_READ,),
                        S.REC_IDENTITY_TIER: S.REC_POSSIBLE,
                    }
                )
            )
            continue
        components, reasons, mismatches = [], [], []
        examples: dict[int, RecommendationExample] = {}
        for feature, label in _features(book):
            signal = signals.get((feature, label))
            if signal is C.NONE:
                continue
            components.append(signal.component)
            reasons.append(signal.reason)
            if signal.mismatch is not C.NONE:
                mismatches.append(signal.mismatch)
            for example in signal.examples:
                examples[example.work_id] = example
        if any(_normalize(author) in familiar for author in book.authors):
            reasons.append(S.REC_FAMILIAR)
        if not components:
            unrankable.append(
                item.model_copy(
                    update={
                        S.REC_REASONS: (*reasons, S.REC_NO_SIGNAL),
                    }
                )
            )
            continue
        ranked.append(
            item.model_copy(
                update={
                    S.STATUS: S.REC_RANKED,
                    S.REC_RANKING_SCORE: round(
                        sum(component.contribution for component in components) / len(components),
                        C.REC_SCORE_PRECISION,
                    ),
                    S.REC_REASONS: tuple(reasons),
                    S.REC_MISMATCHES: tuple(mismatches),
                    S.REC_COMPONENTS: tuple(components),
                    S.REC_SUPPORTING_BOOKS: tuple(
                        sorted(
                            examples.values(),
                            key=lambda example: (-example.rating, example.work_id),
                        )
                    )[: C.REC_EXAMPLE_LIMIT],
                    S.REC_FEATURE_TIER: S.REC_SUPPORTED,
                    S.REC_PREFERENCE_TIER: S.REC_SUPPORTED
                    if any(component.sample_size >= C.THREE for component in components)
                    else S.REC_LIMITED,
                }
            )
        )
    ranked.sort(
        key=lambda item: (
            -(item.ranking_score if item.ranking_score is not C.NONE else C.ZERO),
            item.title.casefold(),
            item.work_id,
        )
    )
    return RecommendationReport(
        key=recommendation_key(data, analysis),
        as_of=data.as_of,
        manifest=data.manifest,
        analysis_report_id=analysis.report_id,
        ranked=tuple(ranked),
        unrankable=tuple(unrankable),
        excluded=tuple(excluded),
        shortlist=_shortlist(ranked, {book.work_id: book for book in books}),
        source_snapshot_ids=tuple(snapshot.snapshot_id for snapshot in data.manifest.snapshots),
        limitations=(S.REC_LIMITATIONS,) + ((S.REC_NO_RATING,) if not rated else ()),
    )
