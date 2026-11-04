from __future__ import annotations

from collections.abc import Mapping
from math import exp, isfinite, log, sqrt

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisBook
from bookystats.domain.ranking_evaluation import RankingEvaluation, grouped_folds
from bookystats.domain.recommendation_evaluation import (
    FeatureProfile,
    FeatureReader,
    fit_profile,
    predict_profile,
)


class DescriptionDocument(C.Model):
    text: str
    provenance: dict[str, JsonValue]
    public_url: str


class SemanticNeighbor(C.Model):
    work_id: int
    title: str
    rating: float
    similarity: float
    description_excerpt: str
    description_url: str


class LearnedWeight(C.Model):
    channel: str
    weight: float
    cross_fitted_examples: int


class LearningSummary(C.Model):
    active: bool = C.FALSE
    encoder_fingerprint: str = S.REC3_DISABLED
    usable_description_works: int = C.ZERO
    encoded_description_works: int = C.ZERO
    rated_description_works: int = C.ZERO
    weights: tuple[LearnedWeight, ...] = ()
    scope: str = S.REC3_SCOPE


def excerpt(text: str) -> str:
    if len(text) <= C.REC3_EXCERPT_LENGTH:
        return text
    return text[: C.REC3_EXCERPT_LENGTH].rsplit(S.SPACE, C.ONE)[C.ZERO]


class SimilarityIndex:
    def __init__(self, vectors: Mapping[int, tuple[float, ...]]) -> None:
        dimensions = {len(vector) for vector in vectors.values()}
        if len(dimensions) > C.ONE or C.ZERO in dimensions:
            raise ValueError(S.REC3_INVALID_VECTORS)
        normalized: dict[int, tuple[float, ...]] = {}
        for work_id, vector in vectors.items():
            if not all(isfinite(value) for value in vector):
                raise ValueError(S.REC3_INVALID_VECTORS)
            norm = sqrt(sum(value * value for value in vector))
            if not norm or not isfinite(norm):
                raise ValueError(S.REC3_INVALID_VECTORS)
            normalized[work_id] = tuple(value / norm for value in vector)
        self.vectors = normalized
        self._pairs: dict[tuple[int, int], float] = {}

    def similarity(self, left: int, right: int) -> float | None:
        if left not in self.vectors or right not in self.vectors:
            return C.NONE
        pair = (min(left, right), max(left, right))
        if pair not in self._pairs:
            self._pairs[pair] = max(
                -C.ONE,
                min(
                    C.ONE,
                    sum(
                        a * b
                        for a, b in zip(self.vectors[left], self.vectors[right], strict=C.TRUE)
                    ),
                ),
            )
        return self._pairs[pair]

    def neighbors(
        self, book: AnalysisBook, training: tuple[AnalysisBook, ...]
    ) -> tuple[tuple[AnalysisBook, float], ...]:
        matches = []
        for candidate in training:
            if candidate.work_id == book.work_id:
                continue
            similarity = self.similarity(book.work_id, candidate.work_id)
            if similarity is not C.NONE and similarity >= C.REC3_SIMILARITY_FLOOR:
                matches.append((candidate, similarity))
        return tuple(
            sorted(matches, key=lambda match: (-match[C.ONE], match[C.ZERO].work_id))[
                : C.REC3_NEIGHBOR_LIMIT
            ]
        )


@C.frozen_dataclass
class ChannelValue:
    residual: float
    supporting_work_ids: tuple[int, ...]


@C.frozen_dataclass
class ChannelProfile:
    training: tuple[AnalysisBook, ...]
    categorical: FeatureProfile
    index: SimilarityIndex
    features: FeatureReader

    def _weighted(self, matches: tuple[tuple[AnalysisBook, float], ...]) -> ChannelValue | None:
        matches = tuple(
            (book, weight) for book, weight in matches if weight >= C.REC3_MIN_NEIGHBOR_WEIGHT
        )
        if len(matches) < C.REC3_MIN_NEIGHBORS:
            return C.NONE
        total = sum(weight for _, weight in matches)
        residual = sum(
            weight * (book.rating - self.categorical.baseline)
            for book, weight in matches
            if book.rating is not C.NONE
        )
        return ChannelValue(
            residual=residual / (total + C.REC3_SHRINKAGE),
            supporting_work_ids=tuple(book.work_id for book, _ in matches),
        )

    def channels(self, book: AnalysisBook) -> tuple[ChannelValue | None, ...]:
        score, fallback = predict_profile(self.categorical, book, self.features)
        feature = (
            ChannelValue(
                score - self.categorical.baseline,
                tuple(
                    candidate.work_id
                    for candidate in self.training
                    if set(self.features(candidate)).intersection(self.features(book))
                ),
            )
            if not fallback
            else C.NONE
        )
        semantic = self._weighted(
            tuple(
                (
                    candidate,
                    (similarity - C.REC3_SIMILARITY_FLOOR) / (C.ONE - C.REC3_SIMILARITY_FLOOR),
                )
                for candidate, similarity in self.index.neighbors(book, self.training)
                if similarity > C.REC3_SIMILARITY_FLOOR
            )
        )
        lengths, years = [], []
        for candidate in self.training:
            if (
                book.page_count is not C.NONE
                and book.page_count > C.ZERO
                and candidate.page_count is not C.NONE
                and candidate.page_count > C.ZERO
            ):
                distance = log(book.page_count / candidate.page_count) / C.REC3_LENGTH_WIDTH
                lengths.append((candidate, exp(-distance * distance)))
            if (
                book.first_publication_year is not C.NONE
                and candidate.first_publication_year is not C.NONE
            ):
                distance = (
                    book.first_publication_year - candidate.first_publication_year
                ) / C.REC3_YEAR_WIDTH
                years.append((candidate, exp(-distance * distance)))
        return feature, semantic, self._weighted(tuple(lengths)), self._weighted(tuple(years))


@C.frozen_dataclass
class HybridModel:
    profile: ChannelProfile | None
    weights: tuple[LearnedWeight, ...]

    def predict(self, book: AnalysisBook) -> float | None:
        if self.profile is C.NONE:
            return C.NONE
        channels = self.profile.channels(book)
        supported = [
            weight.weight * channel.residual
            for weight, channel in zip(self.weights, channels, strict=C.TRUE)
            if channel is not C.NONE and weight.weight > C.ZERO
        ]
        return (
            max(C.ZERO, min(C.FIVE, self.profile.categorical.baseline + sum(supported)))
            if supported
            else C.NONE
        )


def _profile(
    training: tuple[AnalysisBook, ...], index: SimilarityIndex, features: FeatureReader
) -> ChannelProfile:
    return ChannelProfile(
        training, fit_profile(training, features, richer=C.FALSE), index, features
    )


def fit_hybrid(
    training: tuple[AnalysisBook, ...], index: SimilarityIndex, features: FeatureReader
) -> HybridModel:
    known = tuple(
        book
        for book in training
        if book.rating is not C.NONE
        and not book.rating_conflict
        and any(author.strip() for author in book.authors)
    )
    if not known:
        return HybridModel(C.NONE, ())
    rows: list[tuple[tuple[float, ...], float]] = []
    counts = [C.ZERO for _ in C.REC3_CHANNELS]
    for heldout in grouped_folds(known):
        heldout_ids = {book.work_id for book in heldout}
        fitting = tuple(book for book in known if book.work_id not in heldout_ids)
        if not fitting:
            continue
        profile = _profile(fitting, index, features)
        for book in heldout:
            if book.rating is C.NONE:
                continue
            channels = profile.channels(book)
            for position, channel in enumerate(channels):
                counts[position] += channel is not C.NONE
            rows.append(
                (
                    tuple(
                        channel.residual if channel is not C.NONE else C.ZERO
                        for channel in channels
                    ),
                    book.rating - profile.categorical.baseline,
                )
            )
    weights = [float(C.ZERO) for _ in C.REC3_CHANNELS]
    gram = tuple(
        tuple(
            sum(values[left] * values[right] for values, _ in rows) for right in range(len(weights))
        )
        for left in range(len(weights))
    )
    targets = tuple(
        sum(values[position] * target for values, target in rows)
        for position in range(len(weights))
    )
    for _ in range(C.REC3_OPTIMIZATION_STEPS):
        change = float(C.ZERO)
        for position in range(len(weights)):
            numerator = targets[position] - sum(
                weight * gram[position][offset]
                for offset, weight in enumerate(weights)
                if offset != position
            )
            denominator = gram[position][position]
            weight = max(C.ZERO, min(C.REC3_MAX_WEIGHT, numerator / (denominator + C.REC3_RIDGE)))
            change = max(change, abs(weight - weights[position]))
            weights[position] = weight
        if change < C.REC3_CONVERGENCE:
            break
    else:
        raise ValueError(S.REC3_NOT_CONVERGED)
    return HybridModel(
        _profile(known, index, features),
        tuple(
            LearnedWeight(channel=channel, weight=weight, cross_fitted_examples=count)
            for channel, weight, count in zip(C.REC3_CHANNELS, weights, counts, strict=C.TRUE)
        ),
    )


@C.frozen_dataclass
class LearningContext:
    encoder_fingerprint: str
    description_fingerprint: str
    documents: Mapping[int, DescriptionDocument]
    index: SimilarityIndex
    model: HybridModel
    evaluation: RankingEvaluation
