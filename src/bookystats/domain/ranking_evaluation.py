from __future__ import annotations

from collections.abc import Callable, Mapping
from itertools import combinations, groupby
from math import ceil, isfinite, log2

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisBook
from bookystats.domain.recommendation_evaluation import author_components

type RankingPredictor = Callable[
    [tuple[AnalysisBook, ...], tuple[AnalysisBook, ...]], Mapping[int, float | None]
]


class RankingMetrics(C.Model):
    ndcg_at_10: float | None = C.NONE
    precision_at_10: float | None = C.NONE
    concordance: float | None = C.NONE
    compared_works: int = C.ZERO
    positive_works: int = C.ZERO
    unequal_pairs: int = C.ZERO
    k: int = C.ZERO


class RankingModelEvaluation(C.Model):
    metrics: RankingMetrics
    score_count: int = C.ZERO
    mean_fallbacks: int = C.ZERO


class RankingFold(C.Model):
    training_work_ids: tuple[int, ...]
    heldout_work_ids: tuple[int, ...]
    training_components: int
    heldout_components: int
    training_description_count: int
    heldout_description_count: int
    mean: RankingModelEvaluation
    current: RankingModelEvaluation
    genre: RankingModelEvaluation
    candidate: RankingModelEvaluation
    length: RankingModelEvaluation | None = C.NONE


class RankingDeltas(C.Model):
    ndcg_at_10: float | None = C.NONE
    precision_at_10: float | None = C.NONE
    concordance: float | None = C.NONE
    ndcg_winning_folds: int = C.ZERO
    compared_folds: int = C.ZERO


class RankingEvaluation(C.Model):
    version: str = S.RE3_EVALUATION_VERSION
    scope: str = S.RE3_EVALUATION_SCOPE
    metric_policy: str = S.RE3_METRIC_POLICY
    activation_policy: str = S.RE3_ACTIVATION_POLICY
    status: str = S.RE3_INSUFFICIENT
    activation_eligible: bool = C.FALSE
    reasons: tuple[str, ...] = C.RE3_EMPTY
    input_works: int = C.ZERO
    valid_rated_works: int = C.ZERO
    cohort_size: int = C.ZERO
    missing_rating_works: int = C.ZERO
    conflicted_rating_works: int = C.ZERO
    missing_author_works: int = C.ZERO
    independent_components: int = C.ZERO
    description_covered_works: int = C.ZERO
    usable_folds: int = C.ZERO
    mean: RankingModelEvaluation
    current: RankingModelEvaluation
    genre: RankingModelEvaluation
    candidate: RankingModelEvaluation
    length: RankingModelEvaluation | None = C.NONE
    candidate_vs_mean: RankingDeltas
    candidate_vs_current: RankingDeltas
    candidate_vs_genre: RankingDeltas
    candidate_vs_length: RankingDeltas | None = C.NONE
    folds: tuple[RankingFold, ...] = C.RE3_EMPTY


def _validate_books(books: tuple[AnalysisBook, ...]) -> None:
    ids: set[int] = set()
    for book in books:
        if type(book.work_id) is not int or book.work_id <= C.ZERO or book.work_id in ids:
            raise ValueError(S.RE3_DUPLICATE_ID)
        ids.add(book.work_id)
        if book.rating is not C.NONE and (
            type(book.rating) not in C.RE3_SCORE_TYPES
            or not C.ZERO <= book.rating <= C.FIVE
            or not isfinite(book.rating)
        ):
            raise ValueError(S.RE3_INVALID_RATING)


def _has_author(book: AnalysisBook) -> bool:
    return any(author.strip() for author in book.authors)


def _has_description(book: AnalysisBook) -> bool:
    return bool(book.description and book.description.strip())


def grouped_folds(books: tuple[AnalysisBook, ...]) -> tuple[tuple[AnalysisBook, ...], ...]:
    _validate_books(books)
    components = author_components(tuple(book for book in books if _has_author(book)))
    folds: list[list[AnalysisBook]] = [[] for _ in range(min(C.RE3_MAX_FOLDS, len(components)))]
    for component in sorted(
        components, key=lambda group: (-len(group), tuple(book.work_id for book in group))
    ):
        index = min(range(len(folds)), key=lambda index: (len(folds[index]), index))
        folds[index].extend(component)
    return tuple(tuple(sorted(fold, key=lambda book: book.work_id)) for fold in folds)


def _blind(book: AnalysisBook) -> AnalysisBook:
    # Reconstruct rather than blacklist future personal fields on AnalysisBook.
    return AnalysisBook(
        work_id=book.work_id,
        source_ids=book.source_ids,
        title=book.title,
        authors=book.authors,
        features={
            name: values for name, values in book.features.items() if name in C.RE3_PUBLIC_FIELDS
        },
        page_count=book.page_count,
        publication_year=book.publication_year,
        first_publication_year=book.first_publication_year,
        description=book.description,
        field_states={
            name: value for name, value in book.field_states.items() if name in C.RE3_PUBLIC_FIELDS
        },
        evidence=tuple(
            evidence.model_copy(update={S.DETAIL: C.NONE}, deep=C.TRUE)
            for evidence in book.evidence
            if evidence.observation.field in C.RE3_PUBLIC_FIELDS
        ),
        series=book.series.model_copy(deep=C.TRUE) if book.series is not C.NONE else C.NONE,
        first_publication_date=book.first_publication_date,
        edition_publication_date=book.edition_publication_date,
        edition_language=book.edition_language,
        field_evidence={
            name: value
            for name, value in book.field_evidence.items()
            if name in C.RE3_PUBLIC_FIELDS
        },
        field_sources={
            name: value for name, value in book.field_sources.items() if name in C.RE3_PUBLIC_FIELDS
        },
    ).model_copy(deep=C.TRUE)


def _metrics(ratings: tuple[float, ...], scores: tuple[float, ...]) -> RankingMetrics:
    count = len(ratings)
    k = min(C.RE3_RANK_K, count)
    positives = sum(rating >= C.RE3_POSITIVE_THRESHOLD for rating in ratings)
    gains = tuple(C.TWO**rating - C.ONE for rating in ratings)
    ideal = sum(
        gain / log2(index + C.TWO) for index, gain in enumerate(sorted(gains, reverse=C.TRUE)[:k])
    )
    dcg = expected_positives = float(C.ZERO)
    position = C.ZERO
    ranked = sorted(range(count), key=lambda index: -scores[index])
    for _, tied in groupby(ranked, key=lambda index: scores[index]):
        block = tuple(tied)
        included = max(C.ZERO, min(len(block), k - position))
        # A uniformly random permutation within a score tie has these exact expectations.
        dcg += (
            sum(gains[index] for index in block)
            / len(block)
            * sum(C.ONE / log2(rank + C.TWO) for rank in range(position, position + included))
        )
        expected_positives += (
            sum(ratings[index] >= C.RE3_POSITIVE_THRESHOLD for index in block)
            * included
            / len(block)
        )
        position += len(block)
    concordant = float(C.ZERO)
    pairs = C.ZERO
    for left, right in combinations(range(count), C.TWO):
        if ratings[left] == ratings[right]:
            continue
        pairs += C.ONE
        if scores[left] == scores[right]:
            concordant += C.RE3_SCORE_TIE_CREDIT
        elif (scores[left] > scores[right]) == (ratings[left] > ratings[right]):
            concordant += C.ONE
    return RankingMetrics(
        ndcg_at_10=dcg / ideal if ideal > C.ZERO else C.NONE,
        precision_at_10=expected_positives / k if k and positives else C.NONE,
        concordance=concordant / pairs if pairs else C.NONE,
        compared_works=count,
        positive_works=positives,
        unequal_pairs=pairs,
        k=k,
    )


def _predict(
    predictor: RankingPredictor,
    training: tuple[AnalysisBook, ...],
    heldout: tuple[AnalysisBook, ...],
    baseline: float,
) -> RankingModelEvaluation:
    predictions = predictor(
        tuple(book.model_copy(deep=C.TRUE) for book in training),
        tuple(_blind(book) for book in heldout),
    )
    if not isinstance(predictions, Mapping):
        raise ValueError(S.RE3_INVALID_OUTPUT)
    target_ids = {book.work_id for book in heldout}
    seen: set[int] = set()
    clean: dict[int, float] = {}
    for work_id, score in predictions.items():
        if type(work_id) is not int or work_id not in target_ids or work_id in seen:
            raise ValueError(S.RE3_FOREIGN_ID)
        seen.add(work_id)
        if score is C.NONE:
            continue
        if type(score) not in C.RE3_SCORE_TYPES:
            raise ValueError(S.RE3_INVALID_SCORE)
        try:
            numeric = float(score)
        except OverflowError as error:
            raise ValueError(S.RE3_INVALID_SCORE) from error
        if not isfinite(numeric):
            raise ValueError(S.RE3_INVALID_SCORE)
        clean[work_id] = numeric
    return RankingModelEvaluation(
        metrics=_metrics(
            tuple(book.rating for book in heldout if book.rating is not C.NONE),
            tuple(clean.get(book.work_id, baseline) for book in heldout),
        ),
        score_count=len(clean),
        mean_fallbacks=len(heldout) - len(clean),
    )


def _weighted(metrics: tuple[RankingMetrics, ...], field: str) -> float | None:
    values = tuple(
        (
            getattr(metric, field),
            metric.unequal_pairs if field == S.RE3_CONCORDANCE else metric.compared_works,
        )
        for metric in metrics
        if getattr(metric, field) is not C.NONE
    )
    weight = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / weight if weight else C.NONE


def _aggregate(folds: tuple[RankingFold, ...], model: str) -> RankingModelEvaluation:
    results: tuple[RankingModelEvaluation, ...] = tuple(getattr(fold, model) for fold in folds)
    metrics = tuple(result.metrics for result in results)
    return RankingModelEvaluation(
        metrics=RankingMetrics(
            ndcg_at_10=_weighted(metrics, S.RE3_NDCG),
            precision_at_10=_weighted(metrics, S.RE3_PRECISION),
            concordance=_weighted(metrics, S.RE3_CONCORDANCE),
            compared_works=sum(metric.compared_works for metric in metrics),
            positive_works=sum(metric.positive_works for metric in metrics),
            unequal_pairs=sum(metric.unequal_pairs for metric in metrics),
            k=min(C.RE3_RANK_K, sum(metric.compared_works for metric in metrics)),
        ),
        score_count=sum(result.score_count for result in results),
        mean_fallbacks=sum(result.mean_fallbacks for result in results),
    )


def _delta(left: float | None, right: float | None) -> float | None:
    return left - right if left is not C.NONE and right is not C.NONE else C.NONE


def _deltas(
    candidate: RankingModelEvaluation,
    comparator: RankingModelEvaluation,
    folds: tuple[RankingFold, ...],
    model: str,
) -> RankingDeltas:
    paired = tuple(
        (fold.candidate.metrics.ndcg_at_10, getattr(fold, model).metrics.ndcg_at_10)
        for fold in folds
        if fold.candidate.metrics.ndcg_at_10 is not C.NONE
        and getattr(fold, model).metrics.ndcg_at_10 is not C.NONE
    )
    return RankingDeltas(
        ndcg_at_10=_delta(candidate.metrics.ndcg_at_10, comparator.metrics.ndcg_at_10),
        precision_at_10=_delta(
            candidate.metrics.precision_at_10, comparator.metrics.precision_at_10
        ),
        concordance=_delta(candidate.metrics.concordance, comparator.metrics.concordance),
        ndcg_winning_folds=sum(left > right for left, right in paired),
        compared_folds=len(paired),
    )


def evaluate_ranking(
    books: tuple[AnalysisBook, ...],
    *,
    current: RankingPredictor,
    candidate: RankingPredictor,
    genre: RankingPredictor,
    length: RankingPredictor | None = C.NONE,
) -> RankingEvaluation:
    _validate_books(books)
    rated = tuple(book for book in books if book.rating is not C.NONE and not book.rating_conflict)
    known = tuple(sorted((book for book in rated if _has_author(book)), key=lambda b: b.work_id))
    components = author_components(known)
    folds = grouped_folds(known) if len(components) >= C.TWO else C.RE3_EMPTY
    audits: list[RankingFold] = []
    for heldout in folds:
        heldout_ids = {book.work_id for book in heldout}
        training = tuple(book for book in known if book.work_id not in heldout_ids)
        baseline = sum(book.rating for book in training if book.rating is not C.NONE) / len(
            training
        )
        ratings = tuple(book.rating for book in heldout if book.rating is not C.NONE)
        audits.append(
            RankingFold(
                training_work_ids=tuple(book.work_id for book in training),
                heldout_work_ids=tuple(book.work_id for book in heldout),
                training_components=len(author_components(training)),
                heldout_components=len(author_components(heldout)),
                training_description_count=sum(_has_description(book) for book in training),
                heldout_description_count=sum(_has_description(book) for book in heldout),
                mean=RankingModelEvaluation(
                    metrics=_metrics(ratings, tuple(baseline for _ in heldout)),
                    score_count=len(heldout),
                ),
                current=_predict(current, training, heldout, baseline),
                genre=_predict(genre, training, heldout, baseline),
                candidate=_predict(candidate, training, heldout, baseline),
                length=(
                    _predict(length, training, heldout, baseline)
                    if length is not C.NONE
                    else C.NONE
                ),
            )
        )
    records = tuple(audits)
    mean, current_result, genre_result, candidate_result = (
        _aggregate(records, name) for name in C.RE3_MODELS
    )
    length_result = _aggregate(records, S.RE3_LENGTH) if length is not C.NONE else C.NONE
    comparators: tuple[tuple[str, RankingModelEvaluation], ...] = (
        (S.RE3_MEAN, mean),
        (S.RE3_CURRENT, current_result),
        (S.RE3_GENRE, genre_result),
    )
    if length_result is not C.NONE:
        comparators += ((S.RE3_LENGTH, length_result),)
    deltas = tuple(
        _deltas(candidate_result, comparator, records, name) for name, comparator in comparators
    )
    usable = sum(
        fold.candidate.metrics.ndcg_at_10 is not C.NONE
        and fold.candidate.metrics.unequal_pairs > C.ZERO
        for fold in records
    )
    reasons: list[str] = []
    if len(known) < C.RE3_MIN_RATED:
        reasons.append(S.RE3_REASON_WORKS)
    if len(components) < C.RE3_MIN_COMPONENTS:
        reasons.append(S.RE3_REASON_COMPONENTS)
    if usable < C.RE3_MIN_FOLDS:
        reasons.append(S.RE3_REASON_FOLDS)
    if not records or any(
        fold.training_description_count < C.RE3_MIN_DESCRIPTION_TRAINING for fold in records
    ):
        reasons.append(S.RE3_REASON_DESCRIPTIONS)
    if any(
        delta.ndcg_at_10 is C.NONE or delta.ndcg_at_10 < C.RE3_MIN_NDCG_IMPROVEMENT
        for delta in deltas
    ):
        reasons.append(S.RE3_REASON_IMPROVEMENT)
    if not records or any(
        delta.ndcg_winning_folds < ceil(C.RE3_REQUIRED_WIN_FRACTION * len(records))
        for delta in deltas
    ):
        reasons.append(S.RE3_REASON_WINS)
    comparator_precision = tuple(
        comparator.metrics.precision_at_10 for _, comparator in comparators
    )
    precision = candidate_result.metrics.precision_at_10
    if (
        precision is C.NONE
        or any(value is C.NONE for value in comparator_precision)
        or precision < max(value for value in comparator_precision if value is not C.NONE)
    ):
        reasons.append(S.RE3_REASON_PRECISION)
    return RankingEvaluation(
        status=S.RE3_EVALUATED if records else S.RE3_INSUFFICIENT,
        activation_eligible=not reasons,
        reasons=tuple(reasons),
        input_works=len(books),
        valid_rated_works=len(rated),
        cohort_size=len(known),
        missing_rating_works=sum(
            book.rating is C.NONE and not book.rating_conflict for book in books
        ),
        conflicted_rating_works=sum(book.rating_conflict for book in books),
        missing_author_works=len(rated) - len(known),
        independent_components=len(components),
        description_covered_works=sum(_has_description(book) for book in known),
        usable_folds=usable,
        mean=mean,
        current=current_result,
        genre=genre_result,
        candidate=candidate_result,
        length=length_result,
        candidate_vs_mean=deltas[C.ZERO],
        candidate_vs_current=deltas[C.ONE],
        candidate_vs_genre=deltas[C.TWO],
        candidate_vs_length=deltas[-C.ONE] if length_result is not C.NONE else C.NONE,
        folds=records,
    )
