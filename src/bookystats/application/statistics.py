from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
from itertools import combinations, product
from math import comb, isfinite, log2, sqrt
from random import Random
from statistics import mean, median, pstdev, quantiles

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisComponent,
    AnalysisInput,
    AnalyticsSettings,
    Capability,
    Finding,
)
from bookystats.domain.categories import analytical_categories
from bookystats.domain.models import ReadingStatus


def _unique(books: tuple[AnalysisBook, ...]) -> tuple[AnalysisBook, ...]:
    result: dict[int, AnalysisBook] = {}
    for book in books:
        previous = result.get(book.work_id)
        if previous is C.NONE:
            result[book.work_id] = book
        elif previous.rating != book.rating or book.rating_conflict:
            result[book.work_id] = previous.model_copy(
                update={S.RATING: C.NONE, S.AN_CALC_RATING_CONFLICT: C.TRUE}
            )
    return tuple(result[work_id] for work_id in sorted(result))


def _completed(book: AnalysisBook) -> bool:
    return S.READ in book.collections or book.status == ReadingStatus.READ


def _watchlisted(book: AnalysisBook) -> bool:
    return S.TO_READ in book.collections or book.status == ReadingStatus.TO_READ


def _abandoned(book: AnalysisBook) -> bool:
    return book.status == ReadingStatus.DNF or bool(
        C.AN_CALC_DNF_COLLECTIONS.intersection(book.collections)
    )


def _rated(books: tuple[AnalysisBook, ...]) -> tuple[AnalysisBook, ...]:
    return tuple(book for book in books if book.rating is not C.NONE and not book.rating_conflict)


def _ratings(books: tuple[AnalysisBook, ...]) -> list[float]:
    return [book.rating for book in _rated(books) if book.rating is not C.NONE]


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else C.NONE


def _labels(book: AnalysisBook, feature: str) -> tuple[str, ...]:
    if feature == S.LANGUAGE:
        languages = {
            label.strip().casefold()
            for label in book.features.get(S.LANGUAGE, ())
            if book.field_states.get(S.LANGUAGE, C.FieldState.PRESENT) == C.FieldState.PRESENT
            if label.strip()
        }
        return tuple(sorted({C.AN_CALC_LANGUAGE_ALIASES.get(label, label) for label in languages}))
    state_field = S.PAGE_COUNT if feature == S.AN_CALC_LENGTH else feature
    state = book.field_states.get(state_field)
    if state is not C.NONE and state != C.FieldState.PRESENT:
        return ()
    if feature == S.AUTHORS:
        return tuple(sorted(set(author for author in book.authors if author.strip())))
    if feature == S.AN_CALC_LENGTH:
        if book.page_count is C.NONE:
            return ()
        if book.page_count < C.AN_CALC_SHORT_LIMIT:
            return (S.AN_CALC_SHORT,)
        if book.page_count < C.AN_CALC_LONG_LIMIT:
            return (S.AN_CALC_MEDIUM,)
        return (S.AN_CALC_LONG,)
    labels = tuple(label for label in book.features.get(feature, ()) if label.strip())
    if feature == S.GENRES:
        return analytical_categories(labels)
    return tuple(sorted(set(labels)))


def _grouped(books: tuple[AnalysisBook, ...], feature: str) -> dict[str, tuple[AnalysisBook, ...]]:
    groups: dict[str, list[AnalysisBook]] = defaultdict(list)
    for book in books:
        for label in _labels(book, feature):
            groups[label].append(book)
    return {label: tuple(groups[label]) for label in sorted(groups)}


def _fractional_distribution(books: tuple[AnalysisBook, ...], feature: str) -> dict[str, float]:
    known = tuple(book for book in books if _labels(book, feature))
    result: dict[str, float] = defaultdict(float)
    for book in known:
        labels = _labels(book, feature)
        weight = C.ONE / (len(known) * len(labels))
        for label in labels:
            result[label] += weight
    return dict(result)


def _jensen_shannon(left: dict[str, float], right: dict[str, float]) -> float | None:
    if not left or not right:
        return C.NONE
    divergence: float = C.ZERO
    for label in left.keys() | right.keys():
        p = left.get(label, C.ZERO)
        q = right.get(label, C.ZERO)
        midpoint = (p + q) / C.TWO
        if p:
            divergence += p * log2(p / midpoint) / C.TWO
        if q:
            divergence += q * log2(q / midpoint) / C.TWO
    return min(C.ONE, sqrt(max(C.ZERO, divergence)))


def _numeric_profile(values: list[int]) -> dict[str, JsonValue]:
    quartiles = (
        quantiles(values, n=C.FOUR, method=S.AN_CALC_QUANTILE_METHOD)
        if len(values) >= C.TWO
        else values
    )
    return {
        S.AN_CALC_N: len(values),
        S.AN_CALC_MEAN: mean(values) if values else C.NONE,
        S.AN_CALC_MEDIAN: median(values) if values else C.NONE,
        S.AN_CALC_MIN: min(values) if values else C.NONE,
        S.AN_CALC_MAX: max(values) if values else C.NONE,
        S.AN_CALC_QUARTILE_LOW: quartiles[C.ZERO] if quartiles else C.NONE,
        S.AN_CALC_QUARTILE_HIGH: quartiles[-C.ONE] if quartiles else C.NONE,
    }


def _rating_summary(
    books: tuple[AnalysisBook, ...], settings: AnalyticsSettings, baseline: float | None
) -> dict[str, JsonValue]:
    values = _ratings(books)
    histogram = Counter(values)
    high = sum(value >= settings.high_rating_threshold for value in values)
    return {
        S.AN_CALC_RATED: len(values),
        S.AN_CALC_RATING_MISSING: len(books) - len(values),
        S.AN_CALC_COVERAGE: _ratio(len(values), len(books)),
        S.AN_CALC_MEAN: mean(values) if values else C.NONE,
        S.AN_CALC_MEDIAN: median(values) if values else C.NONE,
        S.AN_CALC_STDEV: pstdev(values) if values else C.NONE,
        S.AN_CALC_MIN: min(values) if values else C.NONE,
        S.AN_CALC_MAX: max(values) if values else C.NONE,
        S.AN_CALC_HISTOGRAM: {str(rating): histogram[rating] for rating in sorted(histogram)},
        S.AN_CALC_HIGH_COUNT: high,
        S.AN_CALC_HIGH_SHARE: _ratio(high, len(values)),
        S.AN_CALC_THRESHOLD: settings.high_rating_threshold,
        S.AN_CALC_PRIOR: settings.prior_strength,
        S.AN_CALC_ADJUSTED: (
            (sum(values) + settings.prior_strength * baseline)
            / (len(values) + settings.prior_strength)
            if values and baseline is not C.NONE
            else C.NONE
        ),
    }


def _concentration(
    books: tuple[AnalysisBook, ...], feature: str, settings: AnalyticsSettings
) -> tuple[dict[str, JsonValue], bool]:
    rated = _rated(books)
    authors = _grouped(rated, S.AUTHORS)
    series = _grouped(rated, S.SERIES)
    author_known = sum(bool(_labels(book, S.AUTHORS)) for book in rated)
    series_known = sum(bool(_labels(book, S.SERIES)) for book in rated)
    author_share = _ratio(
        max((len(group) for group in authors.values()), default=C.ZERO), author_known
    )
    series_share = _ratio(
        max((len(group) for group in series.values()), default=C.ZERO), series_known
    )
    leave_out: dict[str, JsonValue] = {}
    if feature != S.AUTHORS and len(authors) >= C.TWO:
        for author in authors:
            remaining = tuple(book for book in rated if author not in book.authors)
            if len(remaining) >= settings.min_group_size:
                leave_out[author] = mean(_ratings(remaining))
    weak = len(rated) < settings.min_group_size or (
        feature != S.AUTHORS
        and (
            author_known != len(rated)
            or author_share is C.NONE
            or author_share > C.AN_CALC_CONCENTRATION_LIMIT
            or (
                feature != S.SERIES
                and series_share is not C.NONE
                and max((len(group) for group in series.values()), default=C.ZERO)
                > C.AN_CALC_CONCENTRATION_LIMIT * len(rated)
            )
        )
    )
    return {
        S.AN_CALC_AUTHOR_KNOWN: author_known,
        S.AN_CALC_SERIES_KNOWN: series_known,
        S.AN_CALC_AUTHOR_SHARE: author_share,
        S.AN_CALC_SERIES_SHARE: series_share,
        S.AN_CALC_LEAVE_AUTHOR: leave_out,
        S.AN_CALC_INDEPENDENT_AUTHORS: len(authors),
    }, weak


def _adjusted_mean(
    books: tuple[AnalysisBook, ...], settings: AnalyticsSettings, baseline: float | None
) -> float | None:
    values = _ratings(books)
    if not values or baseline is C.NONE:
        return C.NONE
    return (sum(values) + settings.prior_strength * baseline) / (
        len(values) + settings.prior_strength
    )


def _predict_held_out(
    held_out: AnalysisBook,
    training: tuple[AnalysisBook, ...],
    settings: AnalyticsSettings,
) -> tuple[float | None, float | None, dict[str, float]]:
    training = _rated(
        tuple(
            book
            for book in _unique(training)
            if book.work_id != held_out.work_id and _completed(book)
        )
    )
    values = _ratings(training)
    if not values:
        return C.NONE, C.NONE, {}
    baseline = mean(values)
    dimensions: dict[str, float] = {}
    for feature in C.AN_CALC_VALIDATION_FEATURES:
        groups = _grouped(training, feature)
        predictions: list[float] = []
        for label in _labels(held_out, feature):
            group = groups.get(label, ())
            if len(group) < settings.min_group_size:
                continue
            prediction = _adjusted_mean(group, settings, baseline)
            if prediction is not C.NONE:
                predictions.append(prediction)
        if predictions:
            dimensions[feature] = mean(predictions)
    prediction = mean(dimensions.values()) if dimensions else baseline
    return min(C.FIVE, max(C.ZERO, prediction)), baseline, dimensions


def _error_comparison(
    residuals: list[float], baseline_residuals: list[float]
) -> dict[str, JsonValue]:
    if not residuals:
        return {
            S.AN_CALC_N: C.ZERO,
            S.AN_CALC_PREDICTOR_ERRORS: C.NONE,
            S.AN_CALC_BASELINE_ERRORS: C.NONE,
            S.AN_CALC_MAE_GAIN: C.NONE,
            S.AN_CALC_RMSE_GAIN: C.NONE,
            S.AN_CALC_ADVANTAGE: C.NONE,
        }
    mae = mean(abs(value) for value in residuals)
    rmse = sqrt(mean(value * value for value in residuals))
    baseline_mae = mean(abs(value) for value in baseline_residuals)
    baseline_rmse = sqrt(mean(value * value for value in baseline_residuals))
    return {
        S.AN_CALC_N: len(residuals),
        S.AN_CALC_PREDICTOR_ERRORS: {S.AN_CALC_MAE: mae, S.AN_CALC_RMSE: rmse},
        S.AN_CALC_BASELINE_ERRORS: {
            S.AN_CALC_MAE: baseline_mae,
            S.AN_CALC_RMSE: baseline_rmse,
        },
        S.AN_CALC_MAE_GAIN: baseline_mae - mae,
        S.AN_CALC_RMSE_GAIN: baseline_rmse - rmse,
        S.AN_CALC_ADVANTAGE: mae < baseline_mae,
    }


def _author_components(
    books: tuple[AnalysisBook, ...],
) -> tuple[tuple[AnalysisBook, ...], ...]:
    known = tuple(book for book in _unique(books) if _labels(book, S.AUTHORS))
    parents = {book.work_id: book.work_id for book in known}
    owners: dict[str, int] = {}

    def root(work_id: int) -> int:
        while parents[work_id] != work_id:
            parents[work_id] = parents[parents[work_id]]
            work_id = parents[work_id]
        return work_id

    for book in known:
        for author in _labels(book, S.AUTHORS):
            name = S.SPACE.join(author.split()).casefold()
            previous = owners.setdefault(name, book.work_id)
            left, right = root(book.work_id), root(previous)
            parents[max(left, right)] = min(left, right)
    groups: dict[int, list[AnalysisBook]] = defaultdict(list)
    for book in known:
        groups[root(book.work_id)].append(book)
    return tuple(tuple(groups[work_id]) for work_id in sorted(groups))


def _author_folds(
    components: tuple[tuple[AnalysisBook, ...], ...],
) -> tuple[tuple[AnalysisBook, ...], ...]:
    folds: list[list[AnalysisBook]] = [[] for _ in range(min(C.AV_MAX_FOLDS, len(components)))]
    for component in sorted(
        components, key=lambda group: (-len(group), tuple(book.work_id for book in group))
    ):
        index = min(range(len(folds)), key=lambda candidate: (len(folds[candidate]), candidate))
        folds[index].extend(component)
    return tuple(tuple(sorted(fold, key=lambda book: book.work_id)) for fold in folds)


def _paired_stability(
    component_losses: tuple[tuple[tuple[float, float], ...], ...], *, has_signal: bool
) -> dict[str, JsonValue]:
    losses = tuple(group for group in component_losses if group)
    supported = (
        len(losses) >= C.AV_MIN_COMPONENTS
        and sum(len(group) for group in losses) >= C.AN_CALC_VALIDATION_MIN
        and has_signal
    )
    result: dict[str, JsonValue] = {
        S.AV_STATE: (
            S.AV_AVAILABLE if supported else S.AV_STABILITY_SMALL if has_signal else S.AV_NO_SIGNAL
        ),
        S.AV_COMPONENTS: len(losses),
        S.AV_MIN_COMPONENTS: C.AV_MIN_COMPONENTS,
        S.AV_MINIMUM_WORKS: C.AN_CALC_VALIDATION_MIN,
        S.AV_DRAWS: C.AV_BOOTSTRAP_DRAWS if supported else C.ZERO,
        S.AV_SEED: C.AV_BOOTSTRAP_SEED,
        S.AV_STABILITY_RANGE: C.NONE,
    }
    if not supported:
        return result
    totals = tuple(
        (sum(baseline - prediction for prediction, baseline in group), len(group))
        for group in losses
    )
    random = Random(C.AV_BOOTSTRAP_SEED)
    gains: list[float] = []
    for _ in range(C.AV_BOOTSTRAP_DRAWS):
        sample = tuple(totals[random.randrange(len(totals))] for _ in totals)
        gains.append(sum(gain for gain, _ in sample) / sum(count for _, count in sample))
    cutoffs = quantiles(gains, n=C.AV_PERCENTILE_PARTS, method=S.AN_CALC_QUANTILE_METHOD)
    result[S.AV_STABILITY_RANGE] = {
        S.AV_LOWER: cutoffs[C.ZERO],
        S.AV_UPPER: cutoffs[-C.ONE],
    }
    return result


def _dated_cohorts(
    books: tuple[AnalysisBook, ...], as_of: str
) -> dict[str, tuple[AnalysisBook, ...]]:
    try:
        current_year = datetime.fromisoformat(as_of).year
    except ValueError:
        return {}
    cohorts: dict[str, list[AnalysisBook]] = defaultdict(list)
    for book in books:
        finishes = {
            event.finished.value
            for event in book.reading_events
            if event.status == ReadingStatus.READ
            and event.finished is not C.NONE
            and event.finished.precision == S.DAY
        }
        if not finishes:
            continue
        year = min(finishes)[: C.FOUR]
        if int(year) < current_year:
            cohorts[year].append(book)
    return {year: tuple(cohorts[year]) for year in sorted(cohorts)}


def _rarefied_genres(books: tuple[AnalysisBook, ...], volume: int) -> float:
    groups = _grouped(books, S.GENRES)
    population = len(books)
    denominator = comb(population, volume)
    return sum(
        C.ONE
        - (
            comb(population - len(group), volume) / denominator
            if population - len(group) >= volume
            else C.ZERO
        )
        for group in groups.values()
    )


class _Calculation:
    def __init__(
        self, data: AnalysisInput, settings: AnalyticsSettings, books: tuple[AnalysisBook, ...]
    ) -> None:
        self.data = data
        self.settings = settings
        self.books = books
        self.read = tuple(book for book in books if _completed(book))
        values = _ratings(self.read)
        self.baseline = mean(values) if values else C.NONE
        self.findings: list[Finding] = []
        self.capabilities: list[Capability] = []
        self.preferences: dict[str, float] = {}

    def add(
        self,
        metric: str,
        books: tuple[AnalysisBook, ...],
        value: JsonValue,
        *,
        population: str = S.AN_CALC_POP_READ,
        unit: str = S.AN_CALC_UNIT_SUMMARY,
        missing: int = C.ZERO,
        reliability: str = S.AN_CALC_RELIABLE,
        uncertainty: dict[str, JsonValue] | None = C.NONE,
        limitations: tuple[str, ...] = (),
        baseline: float | None = C.NONE,
        period: str | None = C.NONE,
    ) -> None:
        self.findings.append(
            Finding(
                metric_id=metric,
                population=population,
                value=value,
                unit=unit,
                sample_size=len(books),
                missing_count=missing,
                baseline=baseline,
                period=period,
                reliability=reliability,
                uncertainty=uncertainty or {},
                supporting_books=tuple(book.book_id for book in books),
                limitations=limitations,
                calculation_version=self.data.manifest.calculation_version,
                source_snapshot_ids=tuple(
                    snapshot.snapshot_id for snapshot in self.data.manifest.snapshots
                ),
            )
        )

    def capability(
        self,
        metric: str,
        available: int,
        population: int,
        reason: str,
        *,
        absent: C.AnalyticsCapability = C.AnalyticsCapability.NEEDS_OBSERVATIONS,
        minimum: int = C.ONE,
    ) -> None:
        state = (
            absent
            if available < minimum
            else C.AnalyticsCapability.SUPPORTED
            if available == population
            else C.AnalyticsCapability.SUBSET
        )
        self.capabilities.append(
            Capability(
                metric_id=metric,
                state=state,
                available=available,
                population=population,
                reason=reason,
            )
        )

    def records(self, metric: str, value: JsonValue, count: int) -> None:
        self.findings.append(
            Finding(
                metric_id=metric,
                population=S.AN_CALC_POP_RECORDS,
                value=value,
                unit=S.AN_CALC_UNIT_SUMMARY,
                sample_size=count,
                missing_count=C.ZERO,
                reliability=S.AN_CALC_RELIABLE,
                limitations=(S.AN_CALC_SCOPE_NOTE,),
                calculation_version=self.data.manifest.calculation_version,
                source_snapshot_ids=tuple(
                    snapshot.snapshot_id for snapshot in self.data.manifest.snapshots
                ),
            )
        )

    def group(
        self,
        metric: str,
        group: tuple[AnalysisBook, ...],
        feature: str,
        known: int,
        comparison_population: tuple[AnalysisBook, ...] | None = C.NONE,
    ) -> bool:
        summary = _rating_summary(group, self.settings, self.baseline)
        population = (
            comparison_population
            if comparison_population is not C.NONE
            else tuple(book for book in self.read if _labels(book, feature))
        )
        group_ids = {book.work_id for book in group}
        complement = tuple(book for book in population if book.work_id not in group_ids)
        complement_summary = _rating_summary(complement, self.settings, self.baseline)
        group_high = _ratio(
            sum(value >= self.settings.high_rating_threshold for value in _ratings(group)),
            len(_rated(group)),
        )
        complement_high = _ratio(
            sum(value >= self.settings.high_rating_threshold for value in _ratings(complement)),
            len(_rated(complement)),
        )
        adjusted_group = _adjusted_mean(group, self.settings, self.baseline)
        adjusted_complement = _adjusted_mean(complement, self.settings, self.baseline)
        comparison_supported = (
            len(_rated(group)) >= self.settings.min_group_size
            and len(_rated(complement)) >= self.settings.min_group_size
        )
        complement_summary[S.AN_CALC_N] = len(complement)
        complement_summary[S.AN_CALC_COMPLEMENT_BOOKS] = [book.book_id for book in complement]
        summary.update(
            {
                S.AN_CALC_COMPLEMENT: complement_summary,
                S.AN_CALC_SHRUNK_EFFECT: (
                    adjusted_group - adjusted_complement
                    if adjusted_group is not C.NONE and adjusted_complement is not C.NONE
                    else C.NONE
                ),
                S.AN_CALC_HIGH_LIFT: (
                    group_high / complement_high
                    if group_high is not C.NONE and complement_high
                    else C.NONE
                ),
                S.AN_CALC_HIGH_DIFFERENCE: (
                    group_high - complement_high
                    if group_high is not C.NONE and complement_high is not C.NONE
                    else C.NONE
                ),
                S.AN_CALC_COMPARISON_SUPPORTED: comparison_supported,
            }
        )
        all_favorites = sum(
            value >= self.settings.high_rating_threshold for value in _ratings(self.read)
        )
        summary.update(
            {
                S.AN_CALC_N: len(group),
                S.AN_CALC_TOTAL: len(self.read),
                S.AN_CALC_KNOWN: known,
                S.AN_CALC_MISSING: len(self.read) - known,
                S.AN_CALC_PREVALENCE: _ratio(len(group), len(self.read)),
                S.AN_CALC_KNOWN_PREVALENCE: _ratio(len(group), known),
                S.AN_CALC_FAVORITE_SHARE: _ratio(
                    sum(value >= self.settings.high_rating_threshold for value in _ratings(group)),
                    all_favorites,
                ),
            }
        )
        uncertainty, weak = _concentration(group, feature, self.settings)
        complement_uncertainty, complement_weak = _concentration(complement, feature, self.settings)
        uncertainty[S.AN_CALC_COMPLEMENT] = complement_uncertainty
        weak = weak or (comparison_supported and complement_weak)
        notes = [
            S.AN_CALC_NO_INFERENCE,
            S.AN_CALC_PRIOR_NOTE,
            S.AN_CALC_MULTILABEL,
            S.AN_CALC_COMPARISON_NOTE,
        ]
        if feature == S.LANGUAGE:
            notes.append(S.AN_CALC_LANGUAGE_NOTE)
        comparisons: dict[str, JsonValue] = {}
        if comparison_supported and feature != S.AUTHORS:
            for author in _grouped(_rated(population), S.AUTHORS):
                group_without = tuple(book for book in group if author not in book.authors)
                complement_without = tuple(
                    book for book in complement if author not in book.authors
                )
                if (
                    len(_rated(group_without)) < self.settings.min_group_size
                    or len(_rated(complement_without)) < self.settings.min_group_size
                ):
                    continue
                left = _adjusted_mean(group_without, self.settings, self.baseline)
                right = _adjusted_mean(complement_without, self.settings, self.baseline)
                if left is not C.NONE and right is not C.NONE:
                    comparisons[author] = left - right
        uncertainty[S.AN_CALC_COMPARISON_LOO] = comparisons
        differences = [value for value in comparisons.values() if isinstance(value, float)]
        if differences:
            weak = weak or min(differences) < C.ZERO < max(differences)
        leave_out = uncertainty[S.AN_CALC_LEAVE_AUTHOR]
        if isinstance(leave_out, dict) and leave_out and self.baseline is not C.NONE:
            deltas = [
                value - self.baseline for value in leave_out.values() if isinstance(value, float)
            ]
            if deltas:
                uncertainty[S.AN_CALC_LOO_RANGE] = [min(deltas), max(deltas)]
                weak = weak or min(deltas) < C.ZERO < max(deltas)
                notes.append(S.AN_CALC_LOO_NOTE)
        if weak:
            notes.append(S.AN_CALC_THIN)
        if len(_rated(group)) == C.ONE:
            notes.append(S.AN_CALC_SINGLE)
        self.add(
            metric,
            group,
            summary,
            missing=len(self.read) - known,
            baseline=self.baseline,
            reliability=S.AN_CALC_WEAK if weak else S.AN_CALC_EXPLORATORY,
            uncertainty=uncertainty,
            limitations=tuple(notes),
        )
        return not weak and comparison_supported

    def core(self) -> None:
        rated = _rated(self.read)
        self.records(
            S.AN_CALC_RATING_RECORDS,
            self.data.personal_rating_records,
            self.data.personal_rating_records,
        )
        self.add(S.AN_CALC_READ_COUNT, self.read, len(self.read), unit=S.AN_CALC_UNIT_WORKS)
        self.add(
            S.AN_CALC_RATED_COUNT,
            rated,
            len(rated),
            missing=len(self.read) - len(rated),
            unit=S.AN_CALC_UNIT_WORKS,
            limitations=(S.AN_CALC_NO_RATINGS,),
        )
        self.add(
            S.AN_CALC_RATINGS,
            rated,
            _rating_summary(self.read, self.settings, self.baseline),
            missing=len(self.read) - len(rated),
            limitations=(S.AN_CALC_NO_INFERENCE,),
        )
        favorites = tuple(
            book
            for book in rated
            if book.rating is not C.NONE and book.rating >= self.settings.high_rating_threshold
        )
        self.add(
            S.AN_CALC_FAVORITES,
            favorites,
            {
                S.AN_CALC_N: len(favorites),
                S.AN_CALC_TOTAL: len(self.read),
                S.AN_CALC_RATED: len(rated),
                S.AN_CALC_HIGH_SHARE: _ratio(len(favorites), len(rated)),
                S.AN_CALC_THRESHOLD: self.settings.high_rating_threshold,
            },
            missing=len(self.read) - len(rated),
            limitations=(S.AN_CALC_NO_INFERENCE,),
        )
        self.capability(S.AN_CALC_RATINGS, len(rated), len(self.read), S.AN_CALC_NO_RATINGS)
        uncertainty, weak = _concentration(favorites, S.GENRES, self.settings)
        self.add(
            S.AN_CALC_FAVORITE_CONCENTRATION,
            favorites,
            {
                S.AN_CALC_N: len(favorites),
                S.AN_CALC_RATED: len(rated),
                S.AN_CALC_HIGH_SHARE: _ratio(len(favorites), len(rated)),
            },
            missing=len(self.read) - len(rated),
            uncertainty=uncertainty,
            reliability=S.AN_CALC_WEAK if weak else S.AN_CALC_RELIABLE,
            limitations=(S.AN_CALC_NO_INFERENCE, S.AN_CALC_THIN)
            if weak
            else (S.AN_CALC_NO_INFERENCE,),
        )

    def features(self) -> None:
        for feature in C.AN_CALC_FEATURES:
            groups = _grouped(self.read, feature)
            known = sum(bool(_labels(book, feature)) for book in self.read)
            supported = C.ZERO
            thin: dict[str, JsonValue] = {}
            thin_books: dict[int, AnalysisBook] = {}
            for label, group in groups.items():
                if feature in C.AN_CALC_CONSISTENCY_FEATURES and len(_rated(group)) <= C.ONE:
                    thin[label] = {
                        S.AN_CALC_N: len(group),
                        S.AN_CALC_RATED: len(_rated(group)),
                        S.AN_CALC_RATING_MISSING: len(group) - len(_rated(group)),
                    }
                    thin_books.update((book.work_id, book) for book in group)
                    continue
                if self.group(
                    S.AN_CALC_GROUP.format(feature=feature, label=label), group, feature, known
                ):
                    supported += C.ONE
                    adjusted = _rating_summary(group, self.settings, self.baseline)[
                        S.AN_CALC_ADJUSTED
                    ]
                    if isinstance(adjusted, float) and self.baseline is not C.NONE:
                        self.preferences[
                            S.AN_CALC_PREFERENCE_KEY.format(feature=feature, label=label)
                        ] = adjusted - self.baseline
            if thin:
                self.add(
                    S.AN_CALC_THIN_GROUPS.format(feature=feature),
                    tuple(thin_books[work_id] for work_id in sorted(thin_books)),
                    {
                        S.AN_CALC_LABELS: thin,
                        S.AN_CALC_TOTAL: len(self.read),
                        S.AN_CALC_KNOWN: known,
                    },
                    missing=len(self.read) - known,
                    reliability=S.AN_CALC_WEAK,
                    limitations=(S.AN_CALC_SINGLE, S.AN_CALC_THIN),
                )
            self.capability(
                S.AN_CALC_FEATURE_ENJOYMENT.format(feature=feature),
                supported,
                len(groups),
                S.AN_CALC_NEED_SUPPORT,
            )

    def breadth(self) -> None:
        for feature in C.AN_CALC_FEATURES:
            groups = _grouped(self.read, feature)
            known = sum(bool(_labels(book, feature)) for book in self.read)
            self.capability(
                feature,
                known,
                len(self.read),
                S.AN_CALC_NEED_FEATURES,
                absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
            )
            shares = _fractional_distribution(self.read, feature)
            hhi = sum(value * value for value in shares.values())
            repeated = {label for label, group in groups.items() if len(group) >= C.TWO}
            self.add(
                S.AN_CALC_BREADTH.format(feature=feature),
                tuple(book for book in self.read if _labels(book, feature)),
                {
                    S.AN_CALC_LABELS: len(groups) if known else C.NONE,
                    S.AN_CALC_TOTAL: len(self.read),
                    S.AN_CALC_KNOWN: known,
                    S.AN_CALC_MISSING: len(self.read) - known,
                    S.AN_CALC_MEMBERSHIP: {label: len(group) for label, group in groups.items()},
                    S.AN_CALC_REPEATED_LABELS: len(repeated) if known else C.NONE,
                    S.AN_CALC_SINGLETON_LABELS: len(groups) - len(repeated) if known else C.NONE,
                    S.AN_CALC_REPEATED_WORKS: (
                        sum(bool(set(_labels(book, feature)) & repeated) for book in self.read)
                        if known
                        else C.NONE
                    ),
                    S.AN_CALC_HHI: hhi if known else C.NONE,
                    S.AN_CALC_EFFECTIVE: C.ONE / hhi if hhi else C.NONE,
                    S.AN_CALC_SHARES: {label: value for label, value in shares.items()},
                },
                missing=len(self.read) - known,
                limitations=(S.AN_CALC_PROFILE_NOTE,),
            )

    def rating_availability(self) -> None:
        rated = _rated(self.read)
        rated_ids = {book.work_id for book in rated}
        unavailable = tuple(book for book in self.read if book.work_id not in rated_ids)
        for feature in C.AN_CALC_FEATURES:
            left = _fractional_distribution(rated, feature)
            right = _fractional_distribution(unavailable, feature)
            left_known = sum(bool(_labels(book, feature)) for book in rated)
            right_known = sum(bool(_labels(book, feature)) for book in unavailable)
            metric = S.AN_BIAS_METRIC.format(feature=feature)
            self.add(
                metric,
                tuple(book for book in self.read if _labels(book, feature)),
                {
                    S.AN_BIAS_AVAILABLE: {
                        S.AN_CALC_TOTAL: len(rated),
                        S.AN_CALC_KNOWN: left_known,
                        S.AN_CALC_MISSING: len(rated) - left_known,
                        S.AN_CALC_SHARES: dict(sorted(left.items())),
                    },
                    S.AN_BIAS_UNAVAILABLE: {
                        S.AN_CALC_TOTAL: len(unavailable),
                        S.AN_CALC_KNOWN: right_known,
                        S.AN_CALC_MISSING: len(unavailable) - right_known,
                        S.AN_CALC_SHARES: dict(sorted(right.items())),
                    },
                    S.AN_CALC_COMPOSITION_DISTANCE: _jensen_shannon(left, right),
                },
                missing=len(self.read) - left_known - right_known,
                reliability=S.AN_CALC_EXPLORATORY,
                limitations=(S.AN_BIAS_NOTE,),
            )
            self.capability(
                metric,
                left_known + right_known,
                len(self.read),
                S.AN_BIAS_NOTE,
                absent=C.AnalyticsCapability.NEEDS_OBSERVATIONS
                if not rated or not unavailable
                else C.AnalyticsCapability.NEEDS_ENRICHMENT
                if not left_known or not right_known
                else C.AnalyticsCapability.NEEDS_OBSERVATIONS,
                minimum=C.ONE
                if min(left_known, right_known) >= self.settings.min_group_size
                else left_known + right_known + C.ONE,
            )

    def structure_profile(self) -> None:
        pages = tuple(book for book in self.read if _labels(book, S.AN_CALC_LENGTH))
        years = tuple(
            book
            for book in self.read
            if book.publication_year is not C.NONE
            and book.field_states.get(S.PUBLICATION_DATE, C.FieldState.PRESENT)
            == C.FieldState.PRESENT
        )
        page_values = [book.page_count for book in pages if book.page_count is not C.NONE]
        year_values = [
            book.publication_year for book in years if book.publication_year is not C.NONE
        ]
        page_summary = _numeric_profile(page_values)
        page_summary[S.AN_CALC_TOTAL] = len(self.read)
        self.add(
            S.AN_CALC_STRUCTURE_PAGES,
            pages,
            page_summary,
            missing=len(self.read) - len(pages),
            limitations=(S.AN_CALC_PAGES_NOTE, S.AN_CALC_PROFILE_NOTE),
        )
        year_summary = _numeric_profile(year_values)
        year_summary[S.AN_CALC_TOTAL] = len(self.read)
        year_summary[S.AN_CALC_EDITION_YEARS] = {
            str(year): count for year, count in sorted(Counter(year_values).items())
        }
        self.add(
            S.AN_CALC_STRUCTURE_PUBLICATION,
            years,
            year_summary,
            missing=len(self.read) - len(years),
            limitations=(S.AN_CALC_PUBLICATION_NOTE, S.AN_CALC_PROFILE_NOTE),
        )
        self.capability(
            S.AN_CALC_STRUCTURE_PAGES,
            len(pages),
            len(self.read),
            S.AN_CALC_PAGES_NOTE,
            absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
        )
        self.capability(
            S.AN_CALC_STRUCTURE_PUBLICATION,
            len(years),
            len(self.read),
            S.AN_CALC_PUBLICATION_NOTE,
            absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
        )
        first = tuple(
            book
            for book in self.read
            if book.first_publication_year is not C.NONE
            and book.field_states.get(S.FIRST_PUBLICATION_YEAR, C.FieldState.PRESENT)
            == C.FieldState.PRESENT
        )
        first_values = [
            book.first_publication_year
            for book in first
            if book.first_publication_year is not C.NONE
        ]
        first_summary = _numeric_profile(first_values)
        first_summary[S.AN_CALC_TOTAL] = len(self.read)
        first_summary[S.FIRST_PUBLICATION_YEAR] = {
            str(year): count for year, count in sorted(Counter(first_values).items())
        }
        self.add(
            S.AN_PROFILE_FIRST_PUBLICATION,
            first,
            first_summary,
            missing=len(self.read) - len(first),
            limitations=(S.AN_PROFILE_FIRST_PUBLICATION_NOTE,),
        )
        self.capability(
            S.AN_PROFILE_FIRST_PUBLICATION,
            len(first),
            len(self.read),
            S.AN_PROFILE_FIRST_PUBLICATION_NOTE,
            absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
        )

    def metadata_quality(self) -> None:
        coverage: dict[str, JsonValue] = {}
        for field in C.AN_PROFILE_METADATA_FIELDS:
            feature = S.AN_CALC_LENGTH if field == S.PAGE_COUNT else field
            known = tuple(
                book
                for book in self.read
                if (
                    bool(_labels(book, feature))
                    if field in C.AN_CALC_FEATURES or field in (S.PAGE_COUNT, S.LANGUAGES)
                    else book.field_states.get(field) == C.FieldState.PRESENT
                )
            )
            sources: Counter[str] = Counter()
            for book in known:
                sources.update(
                    {
                        item.source
                        for item in book.evidence
                        if item.observation.state == C.FieldState.PRESENT
                        and (
                            item.observation.field == field
                            or (
                                field == S.FIRST_PUBLICATION_YEAR
                                and item.observation.field == S.IMPORT_BROWSER_FIRST_PUBLICATION
                            )
                        )
                        and (
                            field not in C.AV_FEATURE_SCOPES
                            or item.observation.scope == C.AV_FEATURE_SCOPES[field]
                        )
                    }
                )
            known_ids = {book.work_id for book in known}
            states = Counter(
                (
                    C.FieldState.PRESENT
                    if book.work_id in known_ids
                    else book.field_states.get(field, C.FieldState.UNAVAILABLE)
                ).value
                for book in self.read
            )
            summary: dict[str, JsonValue] = {
                S.AN_CALC_KNOWN: len(known),
                S.AN_CALC_MISSING: len(self.read) - len(known),
                S.AN_PROFILE_SOURCE_COUNTS: dict(sorted(sources.items())),
                S.AN_PROFILE_STATE_COUNTS: dict(sorted(states.items())),
            }
            if field in C.AV_FEATURE_SCOPES:
                summary[S.AV_LANGUAGE_SCOPE] = C.AV_FEATURE_SCOPES[field]
                summary[S.AV_LANGUAGE_INTERPRETATION] = (
                    S.AV_MATCHED_EDITION_LANGUAGE
                    if field == S.LANGUAGE
                    else S.AV_WORK_LANGUAGE_AVAILABILITY
                )
            coverage[field] = summary
        self.add(
            S.AN_PROFILE_METADATA,
            self.read,
            {
                S.AN_CALC_LABELS: coverage,
                S.AN_PROFILE_UNVERIFIED_WORKS: sum(
                    any(
                        item.observation.field.startswith(S.AN_PROFILE_UNVERIFIED_PREFIX)
                        and bool(item.observation.value)
                        for item in book.evidence
                    )
                    for book in self.read
                ),
            },
            limitations=(S.AN_PROFILE_METADATA_NOTE,),
        )

    def recurring_attributes(self) -> None:
        genres = _grouped(self.read, S.GENRES)
        selected_genres = set(
            sorted(genres, key=lambda label: (-len(genres[label]), label))[
                : C.AN_CALC_CONDITIONAL_GENRES
            ]
        )
        formats = _grouped(self.read, S.EDITION_FORMAT)
        selected_formats = set(
            sorted(formats, key=lambda label: (-len(formats[label]), label))[
                : C.AN_CALC_PROFILE_FORMATS
            ]
        )
        results: dict[str, JsonValue] = {}
        available: dict[int, AnalysisBook] = {}
        for kind in C.AN_CALC_COOCCURRENCE_KINDS:
            known: list[AnalysisBook] = []
            observed: dict[tuple[str, str], list[AnalysisBook]] = defaultdict(list)
            for book in self.read:
                labels = tuple(
                    label for label in _labels(book, S.GENRES) if label in selected_genres
                )
                if not _labels(book, S.GENRES):
                    continue
                if kind == S.AN_CALC_PAIR_GENRES:
                    pairs = list(combinations(labels, C.TWO))
                else:
                    feature = (
                        S.AN_CALC_LENGTH if kind == S.AN_CALC_PAIR_LENGTH else S.EDITION_FORMAT
                    )
                    other_labels = _labels(book, feature)
                    if not other_labels:
                        continue
                    if feature == S.EDITION_FORMAT:
                        other_labels = tuple(
                            label for label in other_labels if label in selected_formats
                        )
                    pairs = list(product(labels, other_labels))
                known.append(book)
                available[book.work_id] = book
                for pair in pairs:
                    observed[pair].append(book)
            supported = sorted(
                (
                    pair
                    for pair, group in observed.items()
                    if len(group) >= self.settings.min_group_size
                ),
                key=lambda pair: (-len(observed[pair]), pair),
            )[: C.AN_CALC_PROFILE_COMBINATIONS]
            entries: list[JsonValue] = []
            for left, right in supported:
                group = observed[(left, right)]
                entries.append(
                    {
                        S.AN_CALC_LEFT_LABEL: left,
                        S.AN_CALC_RIGHT_LABEL: right,
                        S.AN_CALC_N: len(group),
                        S.AN_CALC_KNOWN_PREVALENCE: _ratio(len(group), len(known)),
                        S.AN_CALC_SUPPORTING_BOOKS: [book.book_id for book in group],
                    }
                )
            candidates = (
                comb(len(selected_genres), C.TWO)
                if kind == S.AN_CALC_PAIR_GENRES
                else len(selected_genres)
                * (
                    len(C.AN_CALC_LENGTHS)
                    if kind == S.AN_CALC_PAIR_LENGTH
                    else len(selected_formats)
                )
            )
            results[kind] = {
                S.AN_CALC_TOTAL: len(self.read),
                S.AN_CALC_KNOWN: len(known),
                S.AN_CALC_MISSING: len(self.read) - len(known),
                S.AN_CALC_CANDIDATES: candidates,
                S.AN_CALC_MIN_SUPPORT: self.settings.min_group_size,
                S.AN_CALC_COMBINATIONS: entries,
            }
            self.capability(
                S.AN_CALC_RECURRING_CAPABILITY.format(kind=kind),
                len(known),
                len(self.read),
                S.AN_CALC_RECURRING_NOTE,
                absent=C.AnalyticsCapability.NEEDS_ENRICHMENT
                if not known
                else C.AnalyticsCapability.NEEDS_OBSERVATIONS,
                minimum=C.ONE if supported else len(known) + C.ONE,
            )
        self.add(
            S.AN_CALC_RECURRING,
            tuple(available[work_id] for work_id in sorted(available)),
            results,
            missing=len(self.read) - len(available),
            reliability=S.AN_CALC_EXPLORATORY,
            limitations=(S.AN_CALC_RECURRING_NOTE, S.AN_CALC_PROFILE_NOTE),
        )

    def conditional(self) -> None:
        genres = _grouped(self.read, S.GENRES)
        selected = sorted(genres, key=lambda label: (-len(genres[label]), label))[
            : C.AN_CALC_CONDITIONAL_GENRES
        ]
        known = sum(
            bool(_labels(book, S.GENRES)) and bool(_labels(book, S.AN_CALC_LENGTH))
            for book in self.read
        )
        supported_books: set[int] = set()
        for genre in selected:
            for length in C.AN_CALC_LENGTHS:
                group = tuple(
                    book for book in genres[genre] if length in _labels(book, S.AN_CALC_LENGTH)
                )
                if len(_rated(group)) < self.settings.min_group_size:
                    continue
                metric = S.AN_CALC_CONDITIONAL.format(genre=genre, length=length)
                stable = self.group(
                    metric,
                    group,
                    S.GENRES,
                    known,
                    tuple(
                        book
                        for book in self.read
                        if _labels(book, S.GENRES) and _labels(book, S.AN_CALC_LENGTH)
                    ),
                )
                finding = self.findings.pop()
                length_group = tuple(
                    book for book in self.read if length in _labels(book, S.AN_CALC_LENGTH)
                )
                uncertainty = dict(finding.uncertainty)
                uncertainty[S.AN_CALC_GENRE_BASELINE] = (
                    mean(_ratings(genres[genre])) if _ratings(genres[genre]) else C.NONE
                )
                uncertainty[S.AN_CALC_LENGTH_BASELINE] = (
                    mean(_ratings(length_group)) if _ratings(length_group) else C.NONE
                )
                self.findings.append(
                    finding.model_copy(
                        update={
                            S.AN_CALC_UNCERTAINTY: uncertainty,
                            S.AN_CALC_LIMITATIONS: (
                                *finding.limitations,
                                S.AN_CALC_CONDITIONAL_NOTE,
                            ),
                        }
                    )
                )
                if stable:
                    supported_books.update(book.work_id for book in group)
        self.capability(
            S.AN_CALC_CONDITIONS,
            len(supported_books),
            len(self.read),
            S.AN_CALC_CONDITIONAL_NOTE,
            minimum=self.settings.min_group_size,
        )

    def validation(self) -> None:
        self.author_validation()
        rated = _rated(self.read)
        self.capability(
            S.AN_CALC_VALIDATION,
            len(rated),
            len(self.read),
            S.AN_CALC_VALIDATION_NEED,
            minimum=C.AN_CALC_VALIDATION_MIN,
        )
        if len(rated) < C.AN_CALC_VALIDATION_MIN:
            self.capability(
                S.AN_CALC_VALIDATION_SIGNAL,
                C.ZERO,
                len(rated),
                S.AN_CALC_VALIDATION_NEED,
            )
            return
        residuals: list[float] = []
        baseline_residuals: list[float] = []
        signal_residuals: list[float] = []
        signal_baselines: list[float] = []
        dimension_residuals: dict[str, list[float]] = defaultdict(list)
        dimension_baselines: dict[str, list[float]] = defaultdict(list)
        for held_out in rated:
            prediction, baseline, dimensions = _predict_held_out(held_out, rated, self.settings)
            if prediction is C.NONE or baseline is C.NONE or held_out.rating is C.NONE:
                continue
            residuals.append(prediction - held_out.rating)
            baseline_residuals.append(baseline - held_out.rating)
            if dimensions:
                signal_residuals.append(prediction - held_out.rating)
                signal_baselines.append(baseline - held_out.rating)
            for feature, value in dimensions.items():
                dimension_residuals[feature].append(value - held_out.rating)
                dimension_baselines[feature].append(baseline - held_out.rating)
        summary = _error_comparison(residuals, baseline_residuals)
        summary.update(
            {
                S.AN_CALC_SIGNAL: len(signal_residuals),
                S.AN_CALC_SIGNAL_COVERAGE: _ratio(len(signal_residuals), len(rated)),
                S.AN_CALC_FALLBACK: len(rated) - len(signal_residuals),
                S.AN_CALC_TRAINING_MIN: self.settings.min_group_size,
                S.AN_CALC_SIGNAL_SUBSET: _error_comparison(signal_residuals, signal_baselines),
                S.AN_CALC_DIMENSIONS: {
                    feature: _error_comparison(values, dimension_baselines[feature])
                    for feature, values in sorted(dimension_residuals.items())
                },
            }
        )
        self.add(
            S.AN_CALC_VALIDATION,
            rated,
            summary,
            unit=S.AN_CALC_UNIT_RATING,
            missing=len(self.read) - len(rated),
            reliability=S.AN_CALC_EXPLORATORY,
            limitations=(S.AN_CALC_VALIDATION_NOTE,),
        )
        self.capability(
            S.AN_CALC_VALIDATION_SIGNAL,
            len(signal_residuals),
            len(rated),
            S.AN_CALC_VALIDATION_NEED,
            absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
        )

    def author_validation(self) -> None:
        rated = _rated(self.read)
        components = _author_components(rated)
        known = tuple(book for component in components for book in component)
        component_ids = {
            book.work_id: index for index, component in enumerate(components) for book in component
        }
        residuals: list[float] = []
        baselines: list[float] = []
        signal_residuals: list[float] = []
        signal_baselines: list[float] = []
        losses: dict[int, list[tuple[float, float]]] = defaultdict(list)
        evaluated: list[AnalysisBook] = []
        folds: list[JsonValue] = []
        adequate = len(known) >= C.AN_CALC_VALIDATION_MIN and len(components) >= C.TWO
        if adequate:
            for index, held_out in enumerate(_author_folds(components)):
                held_ids = {book.work_id for book in held_out}
                training = tuple(book for book in known if book.work_id not in held_ids)
                fold_residuals: list[float] = []
                fold_baselines: list[float] = []
                for book in held_out:
                    prediction, baseline, dimensions = _predict_held_out(
                        book, training, self.settings
                    )
                    if prediction is C.NONE or baseline is C.NONE or book.rating is C.NONE:
                        continue
                    residual = prediction - book.rating
                    baseline_residual = baseline - book.rating
                    evaluated.append(book)
                    residuals.append(residual)
                    baselines.append(baseline_residual)
                    fold_residuals.append(residual)
                    fold_baselines.append(baseline_residual)
                    losses[component_ids[book.work_id]].append(
                        (abs(residual), abs(baseline_residual))
                    )
                    if dimensions:
                        signal_residuals.append(residual)
                        signal_baselines.append(baseline_residual)
                fold = _error_comparison(fold_residuals, fold_baselines)
                fold.update(
                    {
                        S.AV_FOLD: index + C.ONE,
                        S.AV_TRAINING_WORKS: len(training),
                        S.AV_TRAINING_MEAN: mean(_ratings(training)),
                    }
                )
                folds.append(fold)
        summary = _error_comparison(residuals, baselines)
        summary.update(
            {
                S.AV_STATE: (
                    S.AV_SMALL
                    if len(known) < C.AN_CALC_VALIDATION_MIN
                    else S.AV_NO_TRAINING
                    if not adequate
                    else S.AV_AVAILABLE
                    if signal_residuals
                    else S.AV_NO_SIGNAL
                ),
                S.AV_KNOWN: len(known),
                S.AV_UNKNOWN: len(rated) - len(known),
                S.AV_COMPONENTS: len(components),
                S.AV_LARGEST_COMPONENT: max(map(len, components), default=C.ZERO),
                S.AV_NO_TRAINING_WORKS: len(known) if len(components) == C.ONE else C.ZERO,
                S.AV_MINIMUM_WORKS: C.AN_CALC_VALIDATION_MIN,
                S.AV_MAXIMUM_FOLDS: C.AV_MAX_FOLDS,
                S.AV_FOLDS: folds,
                S.AN_CALC_SIGNAL: len(signal_residuals),
                S.AN_CALC_SIGNAL_COVERAGE: _ratio(len(signal_residuals), len(evaluated)),
                S.AN_CALC_FALLBACK: len(evaluated) - len(signal_residuals),
                S.AN_CALC_TRAINING_MIN: self.settings.min_group_size,
                S.AN_CALC_SIGNAL_SUBSET: _error_comparison(signal_residuals, signal_baselines),
            }
        )
        self.add(
            S.AV_VALIDATION,
            tuple(sorted(evaluated, key=lambda book: book.work_id)),
            summary,
            unit=S.AN_CALC_UNIT_RATING,
            missing=len(self.read) - len(evaluated),
            reliability=S.AN_CALC_EXPLORATORY if evaluated else S.AN_CALC_WEAK,
            uncertainty={
                S.AV_STABILITY: _paired_stability(
                    tuple(tuple(losses[index]) for index in sorted(losses)),
                    has_signal=bool(signal_residuals),
                )
            },
            limitations=(S.AV_NOTE, S.AV_STABILITY_NOTE),
        )
        self.capability(
            S.AV_VALIDATION,
            len(evaluated),
            len(self.read),
            S.AV_NEED,
            minimum=C.AN_CALC_VALIDATION_MIN,
        )
        self.capability(
            S.AV_SIGNAL_CAPABILITY,
            len(signal_residuals),
            len(rated),
            S.AV_NEED,
            absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
        )

    def yearly_breadth(self, cohorts: dict[str, tuple[AnalysisBook, ...]]) -> None:
        minimum = max(C.AN_CALC_COHORT_MIN, self.settings.min_group_size)
        known = {
            year: tuple(book for book in group if _labels(book, S.GENRES))
            for year, group in cohorts.items()
        }
        years = sorted(year for year, group in known.items() if len(group) >= minimum)[
            -C.AN_CALC_MAX_COHORT_YEARS :
        ]
        support = tuple(book for year in years for book in known[year])
        adequate = len(years) >= C.TWO
        self.capability(
            S.AN_CALC_YEAR_BREADTH,
            len(support),
            len(self.read),
            S.AN_CALC_RAREFACTION_NEED,
            minimum=C.ONE if adequate else len(support) + C.ONE,
        )
        if not adequate:
            return
        volume = min(len(known[year]) for year in years)
        results: dict[str, JsonValue] = {}
        for year in years:
            books = known[year]
            results[year] = {
                S.AN_CALC_N: len(cohorts[year]),
                S.AN_CALC_KNOWN: len(books),
                S.AN_CALC_MISSING: len(cohorts[year]) - len(books),
                S.AN_CALC_SAMPLE_VOLUME: volume,
                S.AN_CALC_EXPECTED_LABELS: _rarefied_genres(books, volume),
                S.AN_CALC_OBSERVED_LABELS: len(_grouped(books, S.GENRES)),
                S.AN_CALC_TAG_DENSITY: mean(len(_labels(book, S.GENRES)) for book in books),
                S.AN_CALC_SUPPORTING_BOOKS: [book.book_id for book in books],
            }
        self.add(
            S.AN_CALC_YEAR_BREADTH,
            support,
            {
                S.AN_CALC_SAMPLE_VOLUME: volume,
                S.AN_CALC_COHORT_YEARS: [year for year in years],
                S.AN_CALC_COHORTS: results,
            },
            missing=len(self.read) - len(support),
            uncertainty={
                S.AN_CALC_EXCLUSIONS: {
                    S.AN_CALC_UNDATED_EXCLUDED: (
                        len(self.read) - sum(len(group) for group in cohorts.values())
                    ),
                    S.AN_CALC_COHORT_EXCLUDED: sum(
                        len(group) for year, group in cohorts.items() if year not in years
                    ),
                    S.AN_CALC_MISSING_LABEL_EXCLUDED: sum(
                        len(cohorts[year]) - len(known[year]) for year in years
                    ),
                }
            },
            limitations=(S.AN_CALC_RAREFACTION_NOTE,),
        )

    def comparable_change(self, cohorts: dict[str, tuple[AnalysisBook, ...]]) -> None:
        minimum = max(C.AN_CALC_COHORT_MIN, self.settings.min_group_size)
        known = {
            year: _rated(tuple(book for book in group if _labels(book, S.GENRES)))
            for year, group in cohorts.items()
        }
        years = sorted(year for year, group in known.items() if len(group) >= minimum)[-C.TWO :]
        if len(years) < C.TWO:
            self.capability(
                S.AN_CALC_TASTE_CHANGE,
                sum(len(group) for group in known.values()),
                len(self.read),
                S.AN_CALC_CHANGE_NEED,
                minimum=len(self.read) + C.ONE,
            )
            return
        before, after = years
        strata: dict[str, dict[tuple[str, ...], tuple[AnalysisBook, ...]]] = {}
        for year in years:
            groups: dict[tuple[str, ...], list[AnalysisBook]] = defaultdict(list)
            for book in known[year]:
                groups[_labels(book, S.GENRES)].append(book)
            strata[year] = {labels: tuple(group) for labels, group in groups.items()}
        shared = sorted(
            labels
            for labels in strata[before].keys() & strata[after].keys()
            if len(strata[before][labels]) >= self.settings.min_group_size
            and len(strata[after][labels]) >= self.settings.min_group_size
        )
        support = tuple(
            book for year in years for labels in shared for book in strata[year][labels]
        )
        adequate = len(shared) >= C.TWO
        self.capability(
            S.AN_CALC_TASTE_CHANGE,
            len(support),
            len(self.read),
            S.AN_CALC_CHANGE_NEED,
            minimum=C.ONE if adequate else len(support) + C.ONE,
        )
        if not adequate:
            return
        standardized: dict[str, float] = dict.fromkeys(years, C.ZERO)
        standardized_high: dict[str, float] = dict.fromkeys(years, C.ZERO)
        records: list[JsonValue] = []
        weak = C.FALSE
        for labels in shared:
            pooled = sum(len(strata[year][labels]) for year in years)
            weight = pooled / len(support)
            record: dict[str, JsonValue] = {
                S.AN_CALC_LABELS: list(labels),
                S.AN_CALC_WEIGHT: weight,
            }
            for year in years:
                group = strata[year][labels]
                values = _ratings(group)
                group_mean = mean(values)
                high_share = sum(
                    value >= self.settings.high_rating_threshold for value in values
                ) / len(values)
                concentration, concentrated = _concentration(group, S.GENRES, self.settings)
                weak = weak or concentrated
                standardized[year] += weight * group_mean
                standardized_high[year] += weight * high_share
                record[year] = {
                    S.AN_CALC_N: len(group),
                    S.AN_CALC_MEAN: group_mean,
                    S.AN_CALC_HIGH_SHARE: high_share,
                    S.AN_CALC_UNCERTAINTY: concentration,
                    S.AN_CALC_SUPPORTING_BOOKS: [book.book_id for book in group],
                }
            records.append(record)
        comparable_before = tuple(book for labels in shared for book in strata[before][labels])
        comparable_after = tuple(book for labels in shared for book in strata[after][labels])
        self.add(
            S.AN_CALC_TASTE_CHANGE,
            support,
            {
                S.AN_CALC_BEFORE: before,
                S.AN_CALC_AFTER: after,
                S.AN_CALC_STRATA: records,
                S.AN_CALC_STANDARDIZED: {year: standardized[year] for year in years},
                S.AN_CALC_STANDARDIZED_HIGH: {year: standardized_high[year] for year in years},
                S.AN_CALC_STANDARDIZED_DELTA: standardized[after] - standardized[before],
                S.AN_CALC_STANDARDIZED_HIGH_DELTA: (
                    standardized_high[after] - standardized_high[before]
                ),
                S.AN_CALC_RAW_DELTA: (
                    mean(_ratings(comparable_after)) - mean(_ratings(comparable_before))
                ),
                S.AN_CALC_SHARED_COVERAGE: {
                    before: _ratio(len(comparable_before), len(known[before])),
                    after: _ratio(len(comparable_after), len(known[after])),
                },
                S.AN_CALC_COHORTS: {
                    year: {
                        S.AN_CALC_TOTAL: len(cohorts[year]),
                        S.AN_CALC_RATED: len(_rated(cohorts[year])),
                        S.AN_CALC_RATED_KNOWN: len(known[year]),
                        S.AN_CALC_RATING_MISSING: len(cohorts[year]) - len(_rated(cohorts[year])),
                        S.AN_CALC_MISSING: sum(
                            not _labels(book, S.GENRES) for book in cohorts[year]
                        ),
                        S.AN_CALC_MEAN: mean(_ratings(known[year])),
                    }
                    for year in years
                },
            },
            missing=len(self.read) - len(support),
            reliability=S.AN_CALC_WEAK if weak else S.AN_CALC_EXPLORATORY,
            limitations=(S.AN_CALC_CHANGE_NOTE, S.AN_CALC_NO_INFERENCE),
        )

    def reviews(self) -> None:
        reviews = tuple(book for book in self.books if book.review and book.review.strip())
        self.capability(
            S.AN_CALC_REVIEWS,
            len(reviews),
            len(self.books),
            S.AN_CALC_NEED_REVIEWS,
            absent=C.AnalyticsCapability.UNSUPPORTED,
        )
        for theme, pattern in C.AN_CALC_REVIEW_THEMES:
            matches = tuple(
                book
                for book in reviews
                if book.review is not C.NONE and pattern.search(book.review)
            )
            self.capability(
                S.AN_CALC_REVIEW.format(theme=theme),
                len(reviews),
                len(self.books),
                S.AN_CALC_REVIEW_NOTE,
                absent=C.AnalyticsCapability.UNSUPPORTED,
            )
            if not reviews:
                continue
            excerpts: list[JsonValue] = []
            for book in matches:
                excerpts.append(
                    {
                        S.AN_CALC_BOOK: book.book_id,
                        S.AN_CALC_EXCERPT: book.review,
                        S.AN_CALC_EVIDENCE: [
                            evidence.model_dump(mode=S.JSON)
                            for evidence in book.evidence
                            if evidence.source == S.GOODREADS
                            and evidence.observation.field == S.REVIEW
                        ],
                    }
                )
            self.add(
                S.AN_CALC_REVIEW.format(theme=theme),
                matches,
                {
                    S.AN_CALC_THEME: theme,
                    S.AN_CALC_N: len(matches),
                    S.AN_CALC_KNOWN: len(reviews),
                    S.AN_CALC_EXCERPT: excerpts,
                },
                population=S.AN_CALC_POP_HISTORY,
                missing=len(self.books) - len(reviews),
                limitations=(S.AN_CALC_REVIEW_NOTE,),
            )

    def time(self) -> None:
        periods: dict[tuple[str, str], dict[int, AnalysisBook]] = defaultdict(dict)
        durations: dict[int, list[int]] = {}
        dated: set[int] = set()
        month_dated: set[int] = set()
        reread_books: list[AnalysisBook] = []
        reread_events = C.ZERO
        for book in self.read:
            exact_pairs: set[tuple[str, str]] = set()
            identified: set[str] = set()
            identified_finish_dates: set[str] = set()
            for event in book.reading_events:
                if event.status != ReadingStatus.READ or event.finished is C.NONE:
                    continue
                finished = event.finished
                dated.add(book.work_id)
                periods[(S.YEAR, finished.value[: C.FOUR])][book.work_id] = book
                if finished.precision != S.YEAR:
                    periods[(S.MONTH, finished.value[: C.SEVEN])][book.work_id] = book
                    month_dated.add(book.work_id)
                if event.source_event_id is not C.NONE and finished.precision == S.DAY:
                    identified.add(event.source_event_id)
                    identified_finish_dates.add(finished.value)
                if (
                    event.started is not C.NONE
                    and event.started.precision == S.DAY
                    and finished.precision == S.DAY
                ):
                    exact_pairs.add((event.started.value, finished.value))
            values = [
                (date.fromisoformat(finished) - date.fromisoformat(started)).days
                for started, finished in sorted(exact_pairs)
            ]
            if values:
                durations[book.work_id] = values
            identified_reads = min(len(identified), len(identified_finish_dates))
            if identified_reads >= C.TWO:
                reread_books.append(book)
                reread_events += identified_reads - C.ONE
        for (precision, period), works in sorted(periods.items()):
            group = tuple(works[work_id] for work_id in sorted(works))
            self.add(
                S.AN_CALC_PERIOD.format(precision=precision, period=period),
                group,
                {
                    S.AN_CALC_N: len(group),
                    S.AN_CALC_TOTAL: len(self.read),
                    S.AN_CALC_RATINGS: _rating_summary(group, self.settings, self.baseline),
                },
                missing=len(self.read) - len(month_dated if precision == S.MONTH else dated),
                period=period,
                limitations=(S.AN_CALC_TIME_NOTE,),
            )
        duration_books = tuple(book for book in self.read if book.work_id in durations)
        book_means = [mean(values) for values in durations.values()]
        self.add(
            S.AN_CALC_DURATION,
            duration_books,
            {
                S.AN_CALC_MEAN: mean(book_means) if book_means else C.NONE,
                S.AN_CALC_MEDIAN: median(book_means) if book_means else C.NONE,
                S.AN_CALC_DURATIONS: {
                    book.book_id: [value for value in durations[book.work_id]]
                    for book in duration_books
                },
                S.AN_CALC_EVENT_COUNT: sum(len(values) for values in durations.values()),
            },
            missing=len(self.read) - len(duration_books),
            unit=S.AN_CALC_UNIT_DAYS,
            limitations=(S.AN_CALC_DURATION_NOTE, S.AN_CALC_DURATION_MEAN_NOTE),
        )
        self.capability(S.AN_CALC_TIME, len(dated), len(self.read), S.AN_CALC_NEED_DATES)
        self.capability(
            S.AN_CALC_DURATION, len(duration_books), len(self.read), S.AN_CALC_NEED_DATES
        )
        self.capability(
            S.AN_CALC_REREADS, len(reread_books), len(self.read), S.AN_CALC_NEED_REREADS
        )
        if reread_books:
            self.add(
                S.AN_CALC_REREADS,
                tuple(reread_books),
                {S.AN_CALC_REREAD_COUNT: reread_events},
                missing=len(self.read) - len(reread_books),
                limitations=(S.AN_CALC_NEED_REREADS,),
            )

    def community(self) -> None:
        providers = sorted({provider for book in self.read for provider in book.community_ratings})
        matched: set[int] = set()
        for provider in providers:
            paired = tuple(
                book
                for book in _rated(self.read)
                if provider in C.AN_CALC_PROVIDER_SCALES
                and provider in book.community_ratings
                and isfinite(book.community_ratings[provider])
                and C.ZERO <= book.community_ratings[provider] <= C.FIVE
            )
            metric = S.AN_CALC_PROVIDER.format(provider=provider)
            self.capability(
                metric,
                len(paired),
                len(self.read),
                S.AN_CALC_NEED_COMMUNITY,
                absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
            )
            if not paired:
                continue
            matched.update(book.work_id for book in paired)
            personal = _ratings(paired)
            community = [book.community_ratings[provider] for book in paired]
            self.add(
                metric,
                paired,
                {
                    S.AN_CALC_PROVIDER_NAME: provider,
                    S.AN_CALC_PROVIDER_SCALE: S.AN_CALC_PROVIDER_SCALE_VALUE,
                    S.AN_CALC_MEAN: mean(personal),
                    S.AN_CALC_PROVIDER_MEAN: mean(community),
                    S.AN_CALC_DELTA: mean(
                        personal_rating - provider_rating
                        for personal_rating, provider_rating in zip(
                            personal, community, strict=C.TRUE
                        )
                    ),
                },
                missing=len(self.read) - len(paired),
                limitations=(S.AN_CALC_NO_INFERENCE, S.AN_CALC_PROVIDER_NOTE),
            )
        self.capability(
            S.AN_CALC_COMMUNITY,
            len(matched),
            len(self.read),
            S.AN_CALC_NEED_COMMUNITY,
            absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
        )

    def appetite(self) -> None:
        labeled = tuple(book for book in self.read if _labels(book, S.AN_APPETITE))
        groups = _grouped(labeled, S.AN_APPETITE)
        for dimension in C.ANALYTICS_DIMENSIONS:
            group = groups.get(dimension, ())
            declared = self.settings.declared_preferences.get(dimension)
            uncertainty, weak = _concentration(group, S.AN_APPETITE, self.settings)
            uncertainty[S.AN_CALC_EVIDENCE] = {
                book.book_id: [
                    evidence.model_dump(mode=S.JSON)
                    for evidence in book.evidence
                    if evidence.observation.field == S.AN_APPETITE
                ]
                for book in group
            }
            self.add(
                S.AN_CALC_APPETITE.format(dimension=dimension),
                group,
                {
                    S.AN_CALC_DECLARED: declared,
                    S.AN_CALC_EXPOSURE: _ratio(len(group), len(labeled)) if group else C.NONE,
                    S.AN_CALC_KNOWN: len(labeled),
                    S.AN_CALC_TOTAL: len(self.read),
                    S.AN_CALC_ENJOYMENT: (
                        _rating_summary(group, self.settings, self.baseline) if group else C.NONE
                    ),
                },
                missing=len(self.read) - len(labeled),
                reliability=S.AN_CALC_WEAK if weak else S.AN_CALC_EXPLORATORY,
                baseline=self.baseline,
                uncertainty=uncertainty,
                limitations=(S.AN_CALC_APP_NOTE, S.AN_CALC_NO_INFERENCE),
            )
            self.capability(
                S.AN_CALC_APP_DECLARED.format(dimension=dimension),
                C.ZERO if declared is C.NONE else C.ONE,
                C.ONE,
                S.AN_CALC_NEED_DECLARATION,
                absent=C.AnalyticsCapability.UNSUPPORTED,
            )
            self.capability(
                S.AN_CALC_APP_EXPOSURE.format(dimension=dimension),
                len(group),
                len(self.read),
                S.AN_CALC_NEED_APP_LABELS,
                absent=C.AnalyticsCapability.NEEDS_ENRICHMENT,
            )
            self.capability(
                S.AN_CALC_APP_ENJOYMENT.format(dimension=dimension),
                len(_rated(group)),
                len(group),
                S.AN_CALC_NEED_SUPPORT,
                minimum=max(self.settings.min_group_size, len(_rated(group)) + C.ONE)
                if weak
                else self.settings.min_group_size,
            )
            if not weak and group and self.baseline is not C.NONE:
                adjusted = _rating_summary(group, self.settings, self.baseline)[S.AN_CALC_ADJUSTED]
                if isinstance(adjusted, float):
                    self.preferences[
                        S.AN_CALC_PREFERENCE_KEY.format(feature=S.AN_APPETITE, label=dimension)
                    ] = adjusted - self.baseline

    def dnf(self) -> None:
        dnf = tuple(book for book in self.books if _abandoned(book))
        scoped = any(
            snapshot.collection in C.AN_CALC_DNF_COLLECTIONS
            and snapshot.source == C.Source.GOODREADS
            and snapshot.attempt_state == C.SyncState.COMPLETE
            for snapshot in self.data.manifest.snapshots
        )
        self.add(
            S.AN_CALC_DNF,
            dnf,
            {
                S.AN_CALC_N: len(dnf) if scoped or dnf else C.NONE,
                S.AN_CALC_TOTAL: len(self.books),
                S.AN_CALC_LABELS: {
                    label: len(group) for label, group in _grouped(dnf, S.GENRES).items()
                },
                S.AN_CALC_KNOWN: sum(bool(_labels(book, S.GENRES)) for book in dnf),
                S.AN_CALC_MISSING: sum(not _labels(book, S.GENRES) for book in dnf),
            },
            population=S.AN_CALC_POP_HISTORY,
            missing=C.ZERO if scoped else len(self.books) - len(dnf),
            limitations=(S.AN_CALC_DNF_NOTE,),
        )
        self.capability(
            S.AN_CALC_DNF,
            len(self.books) if scoped else len(dnf),
            len(self.books),
            S.AN_CALC_DNF_NOTE,
            minimum=C.ZERO if scoped else C.ONE,
        )

    def watchlist_age(self, watch: tuple[AnalysisBook, ...]) -> None:
        dated = tuple(book for book in watch if book.added_at is not C.NONE)
        as_of: date | None
        try:
            as_of = datetime.fromisoformat(self.data.as_of).date()
        except ValueError:
            as_of = C.NONE
        entries: dict[str, JsonValue] = {}
        for book in dated:
            added = book.added_at
            if added is C.NONE:
                continue
            age = C.NONE
            if added.precision == S.DAY and as_of is not C.NONE:
                difference = (as_of - date.fromisoformat(added.value)).days
                if difference >= C.ZERO:
                    age = difference
            entries[book.book_id] = {
                S.AN_CALC_ADDED: added.value,
                S.AN_CALC_PRECISION: added.precision,
                S.AN_CALC_AGE_DAYS: age,
            }
        self.add(
            S.AN_CALC_WATCH_AGE,
            dated,
            {
                S.AN_CALC_AS_OF: as_of.isoformat() if as_of is not C.NONE else C.NONE,
                S.AN_CALC_LABELS: entries,
            },
            population=S.AN_CALC_POP_WATCH,
            missing=len(watch) - len(dated),
            limitations=(S.AN_CALC_AGE_NOTE,),
        )
        self.capability(
            S.AN_CALC_WATCH_AGE,
            len(dated),
            len(watch),
            S.AN_CALC_AGE_NOTE,
            absent=C.AnalyticsCapability.UNSUPPORTED,
        )


def build_reading_profile(
    data: AnalysisInput, settings: AnalyticsSettings, *, key: str
) -> AnalysisComponent:
    calculation = _Calculation(data, settings, _unique(data.books))
    calculation.breadth()
    calculation.structure_profile()
    calculation.recurring_attributes()
    calculation.metadata_quality()
    return AnalysisComponent(
        key=key,
        kind=C.AnalyticsComponentKind.TASTE,
        findings=tuple(calculation.findings),
        capabilities=tuple(calculation.capabilities),
    )


def build_taste(
    data: AnalysisInput,
    settings: AnalyticsSettings,
    *,
    key: str,
    include_profile: bool = C.TRUE,
) -> AnalysisComponent:
    calculation = _Calculation(
        data,
        settings,
        tuple(book for book in _unique(data.books) if _completed(book) or _abandoned(book)),
    )
    calculation.core()
    calculation.features()
    calculation.rating_availability()
    calculation.conditional()
    calculation.validation()
    cohorts = _dated_cohorts(calculation.read, data.as_of)
    calculation.yearly_breadth(cohorts)
    calculation.comparable_change(cohorts)
    calculation.reviews()
    calculation.time()
    calculation.community()
    calculation.appetite()
    calculation.dnf()
    for metric, reason in C.AN_CALC_UNSUPPORTED_TOPICS:
        calculation.capability(
            metric,
            C.ZERO,
            len(calculation.read),
            reason,
            absent=C.AnalyticsCapability.UNSUPPORTED,
        )
    if include_profile:
        profile = build_reading_profile(data, settings, key=key)
        calculation.findings.extend(profile.findings)
        calculation.capabilities.extend(profile.capabilities)
    return AnalysisComponent(
        key=key,
        kind=C.AnalyticsComponentKind.TASTE,
        findings=tuple(calculation.findings),
        capabilities=tuple(calculation.capabilities),
        preferences=calculation.preferences,
    )


def build_watchlist(
    data: AnalysisInput,
    settings: AnalyticsSettings,
    taste: AnalysisComponent,
    *,
    key: str,
) -> AnalysisComponent:
    calculation = _Calculation(data, settings, _unique(data.books))
    watch = tuple(book for book in calculation.books if _watchlisted(book))
    calculation.records(
        S.AN_CALC_SOURCE_COUNTS,
        {source: count for source, count in sorted(data.source_counts.items())},
        sum(data.source_counts.values()),
    )
    calculation.add(
        S.AN_CALC_WATCH_COUNT,
        watch,
        len(watch),
        population=S.AN_CALC_POP_WATCH,
        unit=S.AN_CALC_UNIT_WORKS,
    )
    supported_watch: set[int] = set()
    for feature in C.AN_CALC_WATCH_FEATURES:
        read_groups = _grouped(calculation.read, feature)
        watch_groups = _grouped(watch, feature)
        read_known = sum(bool(_labels(book, feature)) for book in calculation.read)
        watch_known = sum(bool(_labels(book, feature)) for book in watch)
        composition: dict[str, JsonValue] = {}
        unsupported: list[JsonValue] = []
        supported_books: set[int] = set()
        for label in sorted(set(read_groups) | set(watch_groups)):
            read_share = _ratio(len(read_groups.get(label, ())), read_known)
            watch_share = _ratio(len(watch_groups.get(label, ())), watch_known)
            preference = taste.preferences.get(
                S.AN_CALC_PREFERENCE_KEY.format(feature=feature, label=label)
            )
            if preference is C.NONE:
                unsupported.append(label)
            elif read_known and watch_known:
                supported_books.update(book.work_id for book in watch_groups.get(label, ()))
            composition[label] = {
                S.AN_CALC_READ_SHARE: read_share,
                S.AN_CALC_WATCH_SHARE: watch_share,
                S.AN_CALC_COMPOSITION_DELTA: (
                    watch_share - read_share
                    if watch_share is not C.NONE and read_share is not C.NONE
                    else C.NONE
                ),
                S.AN_CALC_PREFERENCE_DELTA: preference,
            }
        calculation.add(
            S.AN_CALC_WATCH_FEATURE.format(feature=feature),
            tuple(book for book in watch if _labels(book, feature)),
            {
                S.AN_CALC_READ_KNOWN: read_known,
                S.AN_CALC_WATCH_KNOWN: watch_known,
                S.AN_CALC_LABELS: composition,
                S.AN_CALC_UNSUPPORTED_LABELS: unsupported,
            },
            population=S.AN_CALC_POP_WATCH,
            missing=len(watch) - watch_known,
            limitations=(S.AN_CALC_WATCH_NOTE, S.AN_CALC_MULTILABEL),
        )
        calculation.capability(
            S.AN_CALC_WATCH_FEATURE.format(feature=feature),
            len(supported_books),
            len(watch),
            S.AN_CALC_NEED_SUPPORT,
            absent=C.AnalyticsCapability.NEEDS_ENRICHMENT
            if not read_known or not watch_known
            else C.AnalyticsCapability.NEEDS_OBSERVATIONS,
        )
        read_distribution = _fractional_distribution(calculation.read, feature)
        watch_distribution = _fractional_distribution(watch, feature)
        gaps: list[tuple[float, str, dict[str, JsonValue]]] = []
        if min(read_known, watch_known) >= settings.min_group_size:
            for label in read_distribution.keys() | watch_distribution.keys():
                read_support = len(read_groups.get(label, ()))
                watch_support = len(watch_groups.get(label, ()))
                if read_support + watch_support < settings.min_group_size:
                    continue
                delta = watch_distribution.get(label, C.ZERO) - read_distribution.get(label, C.ZERO)
                gaps.append(
                    (
                        delta,
                        label,
                        {
                            S.AN_CALC_LEFT_LABEL: label,
                            S.AN_CALC_READ_SHARE: read_distribution.get(label, C.ZERO),
                            S.AN_CALC_WATCH_SHARE: watch_distribution.get(label, C.ZERO),
                            S.AN_CALC_COMPOSITION_DELTA: delta,
                            S.AN_CALC_READ_LABEL_SUPPORT: read_support,
                            S.AN_CALC_WATCH_LABEL_SUPPORT: watch_support,
                        },
                    )
                )
        gaps.sort(key=lambda item: (-abs(item[C.ZERO]), item[C.ONE]))
        metric = S.AN_PROFILE_WATCH_COMPOSITION.format(feature=feature)
        calculation.add(
            metric,
            tuple(book for book in watch if _labels(book, feature)),
            {
                S.AN_CALC_READ_KNOWN: read_known,
                S.AN_CALC_WATCH_KNOWN: watch_known,
                S.AN_CALC_READ_MISSING: len(calculation.read) - read_known,
                S.AN_CALC_WATCH_MISSING: len(watch) - watch_known,
                S.AN_CALC_READ_SHARE: dict(sorted(read_distribution.items())),
                S.AN_CALC_WATCH_SHARE: dict(sorted(watch_distribution.items())),
                S.AN_CALC_COMPOSITION_DISTANCE: _jensen_shannon(
                    read_distribution, watch_distribution
                ),
                S.AN_CALC_COMPOSITION_GAPS: [
                    entry for _, _, entry in gaps[: C.AN_CALC_PROFILE_GAPS]
                ],
            },
            population=S.AN_CALC_POP_WATCH,
            missing=len(watch) - watch_known,
            reliability=S.AN_CALC_RELIABLE
            if min(read_known, watch_known) >= settings.min_group_size
            else S.AN_CALC_WEAK,
            limitations=(S.AN_CALC_COMPOSITION_NOTE,),
        )
        calculation.capability(
            metric,
            read_known + watch_known,
            len(calculation.read) + len(watch),
            S.AN_CALC_COMPOSITION_REASON,
            absent=C.AnalyticsCapability.NEEDS_ENRICHMENT
            if not read_known or not watch_known
            else C.AnalyticsCapability.NEEDS_OBSERVATIONS,
            minimum=C.ONE
            if min(read_known, watch_known) >= settings.min_group_size
            else read_known + watch_known + C.ONE,
        )
        supported_watch.update(supported_books)
    calculation.capability(
        S.AN_CALC_WATCH_MISMATCH,
        len(supported_watch),
        len(watch),
        S.AN_CALC_WATCH_NOTE,
    )
    calculation.watchlist_age(watch)
    calculation.capability(
        S.AN_CALC_WATCH_MOVEMENT,
        C.ZERO,
        len(watch),
        S.AN_CALC_NEED_MOVEMENT,
    )
    return AnalysisComponent(
        key=key,
        kind=C.AnalyticsComponentKind.WATCHLIST,
        findings=tuple(calculation.findings),
        capabilities=tuple(calculation.capabilities),
    )
