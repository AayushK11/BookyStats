from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from statistics import median

from pydantic import Field

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisBook


class RecommendationEvaluationFold(C.Model):
    training_work_ids: tuple[int, ...]
    heldout_work_ids: tuple[int, ...]
    training_feature_count: int


class RecommendationEvaluation(C.Model):
    version: str = S.REC2_EVALUATION_VERSION
    status: str = S.REC2_UNAVAILABLE
    scope: str = S.REC2_EVALUATION_SCOPE
    activation_policy: str = S.REC2_SHADOW_POLICY
    new_scoring_active: bool = C.FALSE
    reason: str | None = S.REC2_INSUFFICIENT
    eligible_rated_works: int = Field(default=C.ZERO, ge=C.ZERO)
    cohort_size: int = Field(default=C.ZERO, ge=C.ZERO)
    missing_author_works: int = Field(default=C.ZERO, ge=C.ZERO)
    independent_components: int = Field(default=C.ZERO, ge=C.ZERO)
    known_length_works: int = Field(default=C.ZERO, ge=C.ZERO)
    known_original_year_works: int = Field(default=C.ZERO, ge=C.ZERO)
    mean_mae: float | None = C.NONE
    simple_length_mae: float | None = C.NONE
    current_heuristic_mae: float | None = C.NONE
    shadow_candidate_mae: float | None = C.NONE
    current_mean_fallbacks: int = C.ZERO
    shadow_mean_fallbacks: int = C.ZERO
    simple_mean_fallbacks: int = C.ZERO
    current_fallback_rate: float | None = C.NONE
    shadow_fallback_rate: float | None = C.NONE
    simple_fallback_rate: float | None = C.NONE
    shadow_beats_comparators: bool | None = C.NONE
    folds: tuple[RecommendationEvaluationFold, ...] = ()


def _authors(book: AnalysisBook) -> set[str]:
    return {S.SPACE.join(author.split()).casefold() for author in book.authors if author.strip()}


def author_components(books: tuple[AnalysisBook, ...]) -> tuple[tuple[AnalysisBook, ...], ...]:
    parents = {book.work_id: book.work_id for book in books}

    def root(work_id: int) -> int:
        while parents[work_id] != work_id:
            parents[work_id] = parents[parents[work_id]]
            work_id = parents[work_id]
        return work_id

    owners: dict[str, int] = {}
    for book in sorted(books, key=lambda item: item.work_id):
        for author in sorted(_authors(book)):
            previous = owners.setdefault(author, book.work_id)
            parents[root(book.work_id)] = root(previous)
    groups: dict[int, list[AnalysisBook]] = defaultdict(list)
    for book in sorted(books, key=lambda item: item.work_id):
        groups[root(book.work_id)].append(book)
    return tuple(tuple(group) for _, group in sorted(groups.items()))


def _folds(
    components: tuple[tuple[AnalysisBook, ...], ...],
) -> tuple[tuple[AnalysisBook, ...], ...]:
    folds: list[list[AnalysisBook]] = [[] for _ in range(min(C.REC2_MAX_FOLDS, len(components)))]
    for group in sorted(
        components, key=lambda group: (-len(group), tuple(book.work_id for book in group))
    ):
        index = min(range(len(folds)), key=lambda index: (len(folds[index]), index))
        folds[index].extend(group)
    return tuple(tuple(sorted(fold, key=lambda book: book.work_id)) for fold in folds)


def _numeric(book: AnalysisBook) -> tuple[tuple[str, int], ...]:
    values = []
    if book.page_count is not C.NONE:
        values.append((S.REC2_LENGTH, book.page_count))
    if book.first_publication_year is not C.NONE:
        values.append((S.REC2_YEAR, book.first_publication_year))
    return tuple(values)


@C.frozen_dataclass
class FeatureProfile:
    baseline: float
    cutoffs: dict[str, float]
    signals: dict[tuple[str, str], float]


FeatureReader = Callable[[AnalysisBook], tuple[tuple[str, str], ...]]


def _tokens(
    book: AnalysisBook, features: FeatureReader, cutoffs: dict[str, float]
) -> tuple[tuple[str, str], ...]:
    return (
        *features(book),
        *(
            (field, S.REC2_LOWER if value <= cutoffs[field] else S.REC2_UPPER)
            for field, value in _numeric(book)
            if field in cutoffs
        ),
    )


def fit_profile(
    training: tuple[AnalysisBook, ...], features: FeatureReader, *, richer: bool
) -> FeatureProfile:
    baseline = sum(book.rating for book in training if book.rating is not C.NONE) / len(training)
    numeric: dict[str, list[int]] = defaultdict(list)
    if richer:
        for book in training:
            for field, value in _numeric(book):
                numeric[field].append(value)
    cutoffs = {field: float(median(values)) for field, values in numeric.items()}
    ratings: dict[tuple[str, str], list[float]] = defaultdict(list)
    for book in training:
        if book.rating is not C.NONE:
            for token in _tokens(book, features, cutoffs):
                ratings[token].append(book.rating)
    signals = {
        token: round(
            (sum(values) - baseline * len(values)) / (len(values) + C.REC_PRIOR_STRENGTH),
            C.REC_SCORE_PRECISION,
        )
        for token, values in ratings.items()
    }
    return FeatureProfile(baseline=baseline, cutoffs=cutoffs, signals=signals)


def predict_profile(
    profile: FeatureProfile,
    book: AnalysisBook,
    features: FeatureReader,
    *,
    length_only: bool = C.FALSE,
) -> tuple[float, bool]:
    values = [
        profile.signals[token]
        for token in _tokens(book, features, profile.cutoffs)
        if token in profile.signals and (not length_only or token[C.ZERO] == S.REC2_LENGTH)
    ]
    return (
        profile.baseline + (sum(values) / len(values) if values else C.ZERO),
        not values,
    )


def evaluate_recommendations(
    rated: tuple[AnalysisBook, ...], features: FeatureReader
) -> RecommendationEvaluation:
    known = tuple(sorted((book for book in rated if _authors(book)), key=lambda book: book.work_id))
    components = author_components(known)
    report = RecommendationEvaluation(
        eligible_rated_works=len(rated),
        missing_author_works=len(rated) - len(known),
        independent_components=len(components),
        known_length_works=sum(book.page_count is not C.NONE for book in known),
        known_original_year_works=sum(book.first_publication_year is not C.NONE for book in known),
    )
    if len(known) < C.REC2_MIN_RATED or len(components) < C.REC2_MIN_COMPONENTS:
        return report
    folds = _folds(components)
    if any(len(known) - len(fold) < C.REC2_MIN_TRAIN for fold in folds):
        return report
    baseline_errors, current_errors, shadow_errors, simple_errors = [], [], [], []
    current_fallbacks = shadow_fallbacks = simple_fallbacks = C.ZERO
    audits = []
    for heldout in folds:
        heldout_ids = {book.work_id for book in heldout}
        training = tuple(book for book in known if book.work_id not in heldout_ids)
        current = fit_profile(training, features, richer=C.FALSE)
        shadow = fit_profile(training, features, richer=C.TRUE)
        audits.append(
            RecommendationEvaluationFold(
                training_work_ids=tuple(sorted(book.work_id for book in training)),
                heldout_work_ids=tuple(sorted(heldout_ids)),
                training_feature_count=len(shadow.signals),
            )
        )
        for book in heldout:
            if book.rating is C.NONE:
                continue
            prediction, fallback = predict_profile(current, book, features)
            richer_prediction, richer_fallback = predict_profile(shadow, book, features)
            simple_prediction, simple_fallback = predict_profile(
                shadow, book, features, length_only=C.TRUE
            )
            baseline_errors.append(abs(current.baseline - book.rating))
            current_errors.append(abs(prediction - book.rating))
            shadow_errors.append(abs(richer_prediction - book.rating))
            simple_errors.append(abs(simple_prediction - book.rating))
            current_fallbacks += fallback
            shadow_fallbacks += richer_fallback
            simple_fallbacks += simple_fallback
    mean_mae, current_mae, shadow_mae, simple_mae = (
        sum(values) / len(values)
        for values in (baseline_errors, current_errors, shadow_errors, simple_errors)
    )
    return RecommendationEvaluation(
        eligible_rated_works=report.eligible_rated_works,
        missing_author_works=report.missing_author_works,
        independent_components=report.independent_components,
        known_length_works=report.known_length_works,
        known_original_year_works=report.known_original_year_works,
        status=S.REC2_AVAILABLE,
        reason=C.NONE,
        cohort_size=len(baseline_errors),
        mean_mae=mean_mae,
        current_heuristic_mae=current_mae,
        shadow_candidate_mae=shadow_mae,
        simple_length_mae=simple_mae,
        current_mean_fallbacks=current_fallbacks,
        shadow_mean_fallbacks=shadow_fallbacks,
        simple_mean_fallbacks=simple_fallbacks,
        current_fallback_rate=current_fallbacks / len(baseline_errors),
        shadow_fallback_rate=shadow_fallbacks / len(baseline_errors),
        simple_fallback_rate=simple_fallbacks / len(baseline_errors),
        shadow_beats_comparators=shadow_mae < min(mean_mae, current_mae, simple_mae),
        folds=tuple(audits),
    )
