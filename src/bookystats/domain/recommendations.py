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
from bookystats.domain.ranking_evaluation import RankingEvaluation
from bookystats.domain.recommendation_evaluation import (
    RecommendationEvaluation,
    evaluate_recommendations,
)
from bookystats.domain.recommendation_learning import (
    LearningContext,
    LearningSummary,
    SemanticNeighbor,
    SimilarityIndex,
    excerpt,
)


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


class RecommendationSeriesContext(C.Model):
    source: str
    series_id: str
    name: str
    position: int | None = C.NONE
    earlier_eligible_work_ids: tuple[int, ...] = ()
    known_completed_positions: tuple[int, ...] = ()
    next_after_known_completed: bool = C.FALSE
    explanation: str = S.EMPTY


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
    series_context: tuple[RecommendationSeriesContext, ...] = ()
    semantic_neighbors: tuple[SemanticNeighbor, ...] = ()
    description_excerpt: str | None = C.NONE
    description_url: str | None = C.NONE
    ranking_method: str = S.REC3_CURRENT
    shortlist_note: str | None = C.NONE


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
    evaluation: RecommendationEvaluation | None = C.NONE
    ranking_evaluation: RankingEvaluation | None = C.NONE
    learning: LearningSummary | None = C.NONE


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


def recommendation_features(book: AnalysisBook) -> tuple[tuple[str, str], ...]:
    shared = {
        (feature, _normalize(label))
        for feature in C.REC_SHARED_FEATURES
        for label in book.features.get(feature, ())
        if label.strip()
    }
    shared.update((S.REC_AUTHOR, _normalize(author)) for author in book.authors if author.strip())
    return tuple(sorted(shared))


_features = recommendation_features


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
    labels = verified.intersection(map(_normalize, book.features.get(S.SERIES, ())))
    labels.update(_series_key(item) for item in _memberships(book))
    return tuple(sorted(labels))


def _series_key(item: RecommendationSeriesContext) -> str:
    return S.REC2_SERIES_KEY.format(source=item.source, identifier=item.series_id)


def _position(value: JsonValue) -> int | None:
    if isinstance(value, str) and C.REC2_INTEGER_PATTERN.fullmatch(value) is not C.NONE:
        return int(value)
    return C.NONE


def _memberships(book: AnalysisBook) -> tuple[RecommendationSeriesContext, ...]:
    memberships: dict[tuple[str, str], list[RecommendationSeriesContext]] = defaultdict(list)
    vetoed = {
        evidence.source
        for evidence in book.evidence
        if evidence.observation.scope == S.WORK
        and evidence.observation.field in C.REC2_MEMBERSHIP_FIELDS
        and evidence.observation.state != FieldState.PRESENT
    }
    for evidence in book.evidence:
        observation = evidence.observation
        if observation.scope != S.WORK or observation.state != FieldState.PRESENT:
            continue
        wikidata = (
            evidence.source == Source.WIKIDATA.value
            and observation.field == S.WD_SERIES_MEMBERSHIPS
            and C.REC2_URL_PATTERN.fullmatch(observation.source_url) is not C.NONE
        )
        open_library = (
            evidence.source == Source.OPEN_LIBRARY.value
            and observation.field == S.META_COVERAGE_SERIES_MEMBERSHIPS
            and C.REC2_OL_URL_PATTERN.fullmatch(observation.source_url) is not C.NONE
        )
        if not (wikidata or open_library):
            continue
        if not isinstance(observation.value, list):
            vetoed.add(evidence.source)
            continue
        for value in observation.value:
            if not isinstance(value, dict):
                vetoed.add(evidence.source)
                continue
            identifier = value.get(S.REC2_SERIES_ID)
            pattern = C.REC2_QID_PATTERN if wikidata else C.REC2_OL_SERIES_PATTERN
            if not isinstance(identifier, str) or pattern.fullmatch(identifier) is C.NONE:
                vetoed.add(evidence.source)
                continue
            label = value.get(S.WD_NAME)
            item = RecommendationSeriesContext(
                source=evidence.source,
                series_id=identifier,
                name=label if isinstance(label, str) and label.strip() else identifier,
                position=_position(value.get(S.REC2_POSITION)),
            )
            memberships[(evidence.source, identifier)].append(item)
    if not any(source == Source.OPEN_LIBRARY.value for source, _ in memberships):
        legacy: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        invalid_legacy: set[tuple[str, str]] = set()
        for evidence in book.evidence:
            observation = evidence.observation
            if (
                evidence.source != Source.OPEN_LIBRARY.value
                or observation.scope != S.WORK
                or observation.field not in C.REC2_LEGACY_SERIES_FIELDS
                or C.REC2_OL_URL_PATTERN.fullmatch(observation.source_url) is C.NONE
            ):
                continue
            provenance = (evidence.source_id, observation.source_url)
            if observation.state != FieldState.PRESENT:
                invalid_legacy.add(provenance)
                continue
            values = (
                observation.value if isinstance(observation.value, list) else [observation.value]
            )
            for value in values:
                if isinstance(value, str) and value.strip():
                    legacy[provenance][observation.field].add(value)
                else:
                    invalid_legacy.add(provenance)
        for provenance, fields in legacy.items():
            if provenance in invalid_legacy:
                continue
            labels, positions = fields[S.SERIES], fields[S.META_COVERAGE_SERIES_POSITIONS]
            if len(labels) != C.ONE or len(positions) != C.ONE:
                continue
            label = next(iter(labels))
            position = _position(next(iter(positions)))
            if position is C.NONE:
                continue
            identifier = S.REC2_LABEL_KEY.format(label=_normalize(label))
            memberships[(Source.OPEN_LIBRARY.value, identifier)].append(
                RecommendationSeriesContext(
                    source=Source.OPEN_LIBRARY.value,
                    series_id=identifier,
                    name=label,
                    position=position,
                )
            )
    result = []
    for _, variants in sorted(memberships.items()):
        known_positions = {item.position for item in variants}
        representative = min(variants, key=lambda item: item.name)
        result.append(
            representative.model_copy(
                update={
                    S.REC2_POSITION: representative.position
                    if len(known_positions) == C.ONE and representative.source not in vetoed
                    else C.NONE
                }
            )
        )
    return tuple(result)


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


def recommendation_key(
    data: AnalysisInput,
    analysis: AnalyticsReport,
    *,
    encoder_fingerprint: str = S.REC3_DISABLED,
    description_fingerprint: str = S.EMPTY,
    learning_enabled: bool = C.FALSE,
) -> str:
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
                S.PAGE_COUNT: book.page_count,
                S.REC2_MEMBERSHIPS: [item.model_dump(mode=S.JSON) for item in _memberships(book)],
                S.REC2_EVIDENCE: sorted(
                    (
                        {
                            S.SOURCE: evidence.source,
                            S.SOURCE_ID: evidence.source_id,
                            S.FIELD: evidence.observation.field,
                            S.REC2_SCOPE: evidence.observation.scope,
                            S.STATE: evidence.observation.state.value,
                            S.VALUE: evidence.observation.value,
                            S.REC2_SOURCE_URL: evidence.observation.source_url,
                            S.REC2_PUBLIC_URL: evidence.public_url,
                        }
                        for evidence in book.evidence
                        if evidence.observation.field in C.REC2_EVIDENCE_FIELDS
                    ),
                    key=canonical_json,
                ),
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
        S.REC2_EVALUATION: S.REC2_EVALUATION_VERSION,
        S.REC3_MODEL: encoder_fingerprint,
        S.REC3_DOCUMENTS: description_fingerprint,
        S.REC3_LEARNING: learning_enabled,
        S.REC3_KEY_LEARNER_VERSION: S.REC3_LEARNER_VERSION,
        S.REC3_RANKING_EVALUATION: S.RE3_EVALUATION_VERSION,
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
    ranked: Iterable[RecommendationItem],
    books: dict[int, AnalysisBook],
    index: SimilarityIndex | None = C.NONE,
) -> tuple[RecommendationItem, ...]:
    authors: dict[str, int] = defaultdict(int)
    series: dict[str, int] = defaultdict(int)
    genres: set[str] = set()
    selected: list[RecommendationItem] = []
    remaining = list(ranked)
    while remaining and len(selected) < C.REC_SHORTLIST_SIZE:
        selected_ids = {item.work_id for item in selected}
        available = [
            item
            for item in remaining
            if not any(
                authors[_normalize(author)] >= C.REC_AUTHOR_CAP
                for author in item.authors
                if author.strip()
            )
            and not any(series[label] >= C.REC_SERIES_CAP for label in _series(books[item.work_id]))
            and not any(
                earlier not in selected_ids
                for context in item.series_context
                for earlier in context.earlier_eligible_work_ids
            )
        ]
        if not available:
            break
        best = max(
            item.ranking_score if item.ranking_score is not C.NONE else C.ZERO for item in available
        )
        comparable = [
            item
            for item in available
            if (item.ranking_score if item.ranking_score is not C.NONE else C.ZERO)
            >= best - C.REC3_DIVERSITY_WINDOW
        ]

        def redundancy(item: RecommendationItem) -> float:
            labels = set(map(_normalize, books[item.work_id].features.get(S.GENRES, ())))
            overlap = len(labels.intersection(genres)) / len(labels) if labels else C.ZERO
            content = max(
                (
                    value
                    for previous in selected
                    if index is not C.NONE
                    and (value := index.similarity(item.work_id, previous.work_id)) is not C.NONE
                ),
                default=C.ZERO,
            )
            return max(overlap, content)

        item = min(
            comparable,
            key=lambda item: (
                -(
                    (item.ranking_score if item.ranking_score is not C.NONE else C.ZERO)
                    - C.REC3_DIVERSITY_PENALTY * redundancy(item)
                ),
                -sum(
                    authors[_normalize(author)] == C.ZERO
                    for author in set(item.authors)
                    if author.strip()
                ),
                -len(
                    {_normalize(genre) for genre in books[item.work_id].features.get(S.GENRES, ())}
                    - genres
                ),
                item.title.casefold(),
                item.work_id,
            ),
        )
        remaining.remove(item)
        names = {_normalize(author) for author in item.authors if author.strip()}
        labels = _series(books[item.work_id])
        selected.append(item.model_copy(update={S.REC3_SHORTLIST_NOTE: S.REC3_DIVERSITY_NOTE}))
        for name in names:
            authors[name] += C.ONE
        for label in labels:
            series[label] += C.ONE
        genres.update(_normalize(genre) for genre in books[item.work_id].features.get(S.GENRES, ()))
    return tuple(selected)


def _with_series_context(
    items: list[RecommendationItem],
    candidates: list[RecommendationItem],
    books: dict[int, AnalysisBook],
    read: list[AnalysisBook],
) -> list[RecommendationItem]:
    memberships = {work_id: _memberships(book) for work_id, book in books.items()}
    eligible_positions: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for candidate in candidates:
        contexts = memberships[candidate.work_id]
        if candidate.identity_tier != S.REC_CONFIRMED or len(contexts) != C.ONE:
            continue
        context = contexts[C.ZERO]
        if context.position is not C.NONE:
            eligible_positions[_series_key(context)].append((candidate.work_id, context.position))
    completed: dict[str, set[int]] = defaultdict(set)
    for book in read:
        for context in _memberships(book):
            if context.position is not C.NONE:
                completed[_series_key(context)].add(context.position)
    result = []
    for item in items:
        contexts = memberships[item.work_id]
        annotated = []
        for context in contexts:
            earlier = tuple(
                sorted(
                    work_id
                    for work_id, position in eligible_positions[_series_key(context)]
                    if len(contexts) == C.ONE
                    and context.position is not C.NONE
                    and position < context.position
                )
            )
            known_completed = tuple(sorted(completed[_series_key(context)]))
            next_known = (
                len(contexts) == C.ONE
                and context.position is not C.NONE
                and context.position - C.ONE in known_completed
                and not earlier
            )
            earlier_titles = S.COMMA_SPACE.join(
                S.REC2_EARLIER_TITLE.format(
                    title=books[work_id].title,
                    position=memberships[work_id][C.ZERO].position,
                )
                for work_id in earlier
            )
            annotated.append(
                RecommendationSeriesContext(
                    source=context.source,
                    series_id=context.series_id,
                    name=context.name,
                    position=context.position,
                    earlier_eligible_work_ids=earlier,
                    known_completed_positions=known_completed,
                    next_after_known_completed=next_known,
                    explanation=S.REC2_SERIES_NOTE.format(
                        name=context.name,
                        position=context.position
                        if context.position is not C.NONE
                        else S.REC2_NO_KNOWN,
                        earlier=earlier_titles or S.REC2_NO_KNOWN,
                        completed=S.COMMA_SPACE.join(map(str, known_completed)) or S.REC2_NO_KNOWN,
                    )
                    + (S.SPACE + S.REC2_NEXT_NOTE if next_known else S.EMPTY),
                )
            )
        result.append(item.model_copy(update={S.REC2_SERIES_CONTEXT: tuple(annotated)}))
    return result


def rated_history(data: AnalysisInput) -> tuple[AnalysisBook, ...]:
    _, groups = _grouped(data)
    return tuple(
        min(
            (book for book in variants if _read(book) and book.rating is not C.NONE),
            key=lambda book: (book.title.casefold(), canonical_json(book.model_dump(mode=S.JSON))),
        )
        for variants in groups.values()
        if any(_read(book) and book.rating is not C.NONE for book in variants)
        and not any(book.rating_conflict for book in variants)
        and len({book.rating for book in variants if book.rating is not C.NONE}) <= C.ONE
    )


def _semantic_context(
    item: RecommendationItem, book: AnalysisBook, context: LearningContext
) -> RecommendationItem:
    document = context.documents.get(book.work_id)
    profile = context.model.profile
    if document is C.NONE or profile is C.NONE:
        return item
    neighbors = tuple(
        SemanticNeighbor(
            work_id=neighbor.work_id,
            title=neighbor.title,
            rating=neighbor.rating,
            similarity=round(similarity, C.REC_SCORE_PRECISION),
            description_excerpt=excerpt(context.documents[neighbor.work_id].text),
            description_url=context.documents[neighbor.work_id].public_url,
        )
        for neighbor, similarity in context.index.neighbors(book, profile.training)[: C.THREE]
        if neighbor.rating is not C.NONE and neighbor.work_id in context.documents
    )
    return item.model_copy(
        update={
            S.REC3_NEIGHBORS: neighbors,
            S.REC3_EXCERPT: excerpt(document.text),
            S.REC3_PUBLIC_URL: document.public_url,
        }
    )


def build_recommendations(
    data: AnalysisInput,
    analysis: AnalyticsReport,
    *,
    learning: LearningContext | None = C.NONE,
) -> RecommendationReport:
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
    rated = list(rated_history(data))
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
        if learning is not C.NONE:
            item = _semantic_context(item, book, learning)
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
        learned_score = (
            learning.model.predict(book)
            if learning is not C.NONE and learning.evaluation.activation_eligible
            else C.NONE
        )
        if learning is not C.NONE and learning.evaluation.activation_eligible:
            components = []
            reasons = [S.REC3_LEARNED_REASON]
            profile = learning.model.profile
            if profile is not C.NONE and learned_score is not C.NONE:
                components = [
                    RecommendationComponent(
                        feature=weight.channel,
                        label=C.REC3_CHANNEL_LABELS[weight.channel],
                        contribution=round(weight.weight * channel.residual, C.REC_SCORE_PRECISION),
                        sample_size=len(channel.supporting_work_ids),
                        supporting_work_ids=channel.supporting_work_ids,
                    )
                    for weight, channel in zip(
                        learning.model.weights, profile.channels(book), strict=C.TRUE
                    )
                    if channel is not C.NONE and weight.weight > C.ZERO
                ]
                item = item.model_copy(update={S.REC3_METHOD: S.REC3_HYBRID})
        if not components:
            unrankable.append(
                item.model_copy(
                    update={
                        S.REC_REASONS: (
                            *reasons,
                            S.REC3_NO_LEARNED_SCORE
                            if learning is not C.NONE and learning.evaluation.activation_eligible
                            else S.REC_NO_SIGNAL,
                        ),
                    }
                )
            )
            continue
        ranked.append(
            item.model_copy(
                update={
                    S.STATUS: S.REC_RANKED,
                    S.REC_RANKING_SCORE: round(
                        learned_score - learning.model.profile.categorical.baseline
                        if learned_score is not C.NONE
                        and learning is not C.NONE
                        and learning.model.profile is not C.NONE
                        else sum(component.contribution for component in components)
                        / len(components),
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
    by_id = {
        book.work_id: book.model_copy(
            update={
                S.AN_EVIDENCE: tuple(
                    evidence for variant in groups[book.work_id] for evidence in variant.evidence
                )
            }
        )
        for book in books
    }
    eligible = ranked + unrankable
    completed = [by_id[book.work_id] for book in read]
    ranked = _with_series_context(ranked, eligible, by_id, completed)
    unrankable = _with_series_context(unrankable, eligible, by_id, completed)
    return RecommendationReport(
        key=recommendation_key(
            data,
            analysis,
            encoder_fingerprint=learning.encoder_fingerprint
            if learning is not C.NONE
            else S.REC3_DISABLED,
            description_fingerprint=learning.description_fingerprint
            if learning is not C.NONE
            else S.EMPTY,
            learning_enabled=learning is not C.NONE,
        ),
        as_of=data.as_of,
        manifest=data.manifest,
        analysis_report_id=analysis.report_id,
        ranked=tuple(ranked),
        unrankable=tuple(unrankable),
        excluded=tuple(excluded),
        shortlist=_shortlist(ranked, by_id, learning.index if learning is not C.NONE else C.NONE),
        evaluation=evaluate_recommendations(tuple(rated), _features),
        ranking_evaluation=learning.evaluation if learning is not C.NONE else C.NONE,
        learning=LearningSummary(
            active=learning.evaluation.activation_eligible,
            encoder_fingerprint=learning.encoder_fingerprint,
            usable_description_works=len(learning.documents),
            encoded_description_works=len(learning.index.vectors),
            rated_description_works=sum(book.work_id in learning.index.vectors for book in rated),
            weights=learning.model.weights,
        )
        if learning is not C.NONE
        else C.NONE,
        source_snapshot_ids=tuple(snapshot.snapshot_id for snapshot in data.manifest.snapshots),
        limitations=(S.REC_LIMITATIONS,) + ((S.REC_NO_RATING,) if not rated else ()),
    )
