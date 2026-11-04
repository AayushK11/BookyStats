from __future__ import annotations

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.models import ReadingStatus
from bookystats.domain.recommendation_learning import SimilarityIndex, fit_hybrid
from bookystats.domain.recommendations import recommendation_features
from tests.application.test_statistics import _book


def test_learns_contrasting_semantic_ratings_without_shared_genres_or_authors() -> None:
    training = tuple(
        _book(
            work_id,
            C.FIVE if work_id <= C.TEN else C.ONE,
        )
        for work_id in range(C.ONE, C.REC3_TEST_TRAIN_SIZE + C.ONE)
    )
    vectors = {
        book.work_id: C.REC3_TEST_POSITIVE_VECTOR
        if book.work_id <= C.TEN
        else C.REC3_TEST_NEGATIVE_VECTOR
        for book in training
    }
    vectors[C.REC3_TEST_TARGET] = C.REC3_TEST_POSITIVE_VECTOR
    model = fit_hybrid(training, SimilarityIndex(vectors), recommendation_features)
    target = _book(C.REC3_TEST_TARGET, status=ReadingStatus.TO_READ)
    positive = model.predict(target)
    negative = model.predict(_book(C.REC3_TEST_TRAIN_SIZE, status=ReadingStatus.TO_READ))
    assert positive is not C.NONE and negative is not C.NONE
    assert positive > negative
    assert model.predict(target.model_copy(update={S.RATING: C.ZERO})) == positive
    assert any(
        weight.channel == S.REC3_SEMANTIC and weight.weight > C.ZERO for weight in model.weights
    )


def test_missing_features_are_not_negative_examples_or_forced_predictions() -> None:
    training = tuple(
        _book(
            work_id,
            C.FIVE if work_id <= C.TEN else C.ONE,
            genre=S.REC3_TEST_POSITIVE if work_id <= C.TEN else S.REC3_TEST_NEGATIVE,
        )
        for work_id in range(C.ONE, C.REC3_TEST_TRAIN_SIZE + C.ONE)
    )
    model = fit_hybrid(training, SimilarityIndex({}), recommendation_features)
    high = _book(C.REC3_TEST_TARGET, genre=S.REC3_TEST_POSITIVE)
    low = high.model_copy(update={S.REC_FEATURES: {S.GENRES: (S.REC3_TEST_NEGATIVE,)}})
    positive, negative = model.predict(high), model.predict(low)
    assert positive is not C.NONE and negative is not C.NONE and positive > negative
    assert model.predict(_book(C.REC3_TEST_TARGET)) is C.NONE
