from __future__ import annotations

from collections.abc import Mapping
from math import log2
from typing import cast

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisBook, AnalysisEvidence
from bookystats.domain.models import FieldState, Observation
from bookystats.domain.ranking_evaluation import (
    RankingEvaluation,
    _metrics,
    evaluate_ranking,
    grouped_folds,
)


def _books(count: int = C.RE3_TEST_COHORT) -> tuple[AnalysisBook, ...]:
    return tuple(
        AnalysisBook(
            work_id=index + C.ONE,
            source_ids=(str(index),),
            title=S.RE3_TEST_TITLE.format(index=index),
            authors=(S.RE3_TEST_AUTHOR.format(index=index),),
            rating=C.RE3_TEST_POSITIVE_RATING if index % C.TWO else C.RE3_TEST_NEGATIVE_RATING,
            page_count=C.RE3_TEST_HIGH_PAGES if index % C.TWO else C.RE3_TEST_LOW_PAGES,
            description=S.RE3_TEST_DESCRIPTION,
            features={S.GENRES: (S.REC_TEST_GENRE,)},
        )
        for index in range(count)
    )


def _missing(
    training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
) -> Mapping[int, float | None]:
    return {}


def _learn_pages(
    training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
) -> Mapping[int, float | None]:
    learned: dict[int | None, list[float]] = {}
    for book in training:
        assert book.rating is not C.NONE
        learned.setdefault(book.page_count, []).append(book.rating)
    return {
        book.work_id: sum(learned[book.page_count]) / len(learned[book.page_count])
        for book in targets
        if book.page_count in learned
    }


def _evaluate(books: tuple[AnalysisBook, ...]) -> RankingEvaluation:
    return evaluate_ranking(books, current=_missing, candidate=_learn_pages, genre=_missing)


def test_tied_metrics_match_manual_graded_gain_and_pairwise_expectation() -> None:
    metrics = _metrics(C.RE3_TEST_METRIC_RATINGS, C.RE3_TEST_METRIC_SCORES)
    tied_gain = (C.RE3_TEST_HIGH_GAIN + C.RE3_TEST_MID_GAIN) / C.TWO
    expected_dcg = tied_gain * (C.ONE + C.ONE / log2(C.THREE)) + C.ONE / C.TWO
    ideal_dcg = C.RE3_TEST_HIGH_GAIN + C.RE3_TEST_MID_GAIN / log2(C.THREE) + C.ONE / C.TWO
    assert metrics.ndcg_at_10 == pytest.approx(expected_dcg / ideal_dcg)
    assert metrics.precision_at_10 == pytest.approx(C.ONE / C.THREE)
    assert metrics.concordance == pytest.approx(C.RE3_TEST_FIVE_SIXTHS)
    assert metrics.compared_works == C.THREE
    assert metrics.positive_works == C.ONE
    assert metrics.unequal_pairs == C.THREE
    assert metrics.k == C.THREE


def test_flat_mean_ties_are_unbiased_even_when_tied_block_crosses_top_ten() -> None:
    ratings = tuple(
        C.RE3_TEST_POSITIVE_RATING if index < C.FIVE else C.RE3_TEST_NEGATIVE_RATING
        for index in range(C.RE3_TEST_SMALL_COHORT)
    )
    scores = tuple(float(C.THREE) for _ in ratings)
    result = _metrics(ratings, scores)
    average_gain = (
        C.FIVE * C.RE3_TEST_HIGH_GAIN + (C.RE3_TEST_SMALL_COHORT - C.FIVE) * C.RE3_TEST_LOW_GAIN
    ) / len(ratings)
    expected_dcg = average_gain * sum(C.ONE / log2(index + C.TWO) for index in range(C.RE3_RANK_K))
    ideal_dcg = sum(
        (C.RE3_TEST_HIGH_GAIN if index < C.FIVE else C.RE3_TEST_LOW_GAIN) / log2(index + C.TWO)
        for index in range(C.RE3_RANK_K)
    )
    assert result.ndcg_at_10 == pytest.approx(expected_dcg / ideal_dcg)
    assert result.precision_at_10 == pytest.approx(C.ONE / C.THREE)
    assert result.concordance == C.RE3_SCORE_TIE_CREDIT
    assert result.k == C.RE3_RANK_K
    assert result == _metrics(tuple(reversed(ratings)), scores)


def test_evaluation_is_deterministic_and_mean_does_not_rank_by_work_id() -> None:
    books = _books()
    result = _evaluate(books)
    assert result == _evaluate(tuple(reversed(books)))
    assert result.mean.metrics.precision_at_10 == C.RE3_SCORE_TIE_CREDIT
    assert result.mean.metrics.concordance == C.RE3_SCORE_TIE_CREDIT
    assert result.candidate.metrics.ndcg_at_10 == pytest.approx(C.ONE)
    assert result.candidate.metrics.precision_at_10 == pytest.approx(C.ONE)
    assert result.candidate.metrics.concordance == pytest.approx(C.ONE)
    assert result.candidate.score_count == len(books)
    assert result.candidate.mean_fallbacks == C.ZERO
    assert result.candidate_vs_mean.ndcg_at_10 is not C.NONE
    assert result.candidate_vs_mean.ndcg_at_10 > C.RE3_MIN_NDCG_IMPROVEMENT
    assert result.candidate_vs_mean.ndcg_winning_folds == C.RE3_MAX_FOLDS
    assert result.activation_eligible
    assert not result.reasons
    assert result.status == S.RE3_EVALUATED
    assert result.length is C.NONE
    assert result.candidate_vs_length is C.NONE
    assert all(fold.length is C.NONE for fold in result.folds)


def test_targets_remove_personal_data_but_keep_public_metadata_and_training_ratings() -> None:
    evidence = tuple(
        AnalysisEvidence(
            source=S.GOODREADS,
            source_id=S.RE3_TEST_TITLE,
            observation=Observation(
                field=field,
                value=S.RE3_TEST_REVIEW if field != S.DESCRIPTION else S.RE3_TEST_DESCRIPTION,
                state=FieldState.PRESENT,
                source_url=S.RE3_TEST_PUBLIC_URL,
                observed_at=S.RE3_TEST_DATE,
            ),
            detail=S.RE3_TEST_REVIEW,
            public_url=S.RE3_TEST_PUBLIC_URL,
        )
        for field in (
            S.RATING,
            S.REVIEW,
            S.GOODREADS_PERSONAL_RATING,
            S.COMMUNITY_RATING,
            S.DESCRIPTION,
        )
    )
    books = tuple(
        book.model_copy(
            update={
                S.REVIEW: S.RE3_TEST_REVIEW,
                S.RE3_TEST_COMMUNITY_RATINGS: {S.GOODREADS: C.FIVE},
                S.AN_EVIDENCE: evidence,
                S.AN_CALC_FIELD_STATES_FIELD: {
                    S.RATING: FieldState.PRESENT,
                    S.DESCRIPTION: FieldState.PRESENT,
                },
                S.REC_FEATURES: {
                    S.RATING: (S.RE3_TEST_REVIEW,),
                    S.GENRES: (S.REC_TEST_GENRE,),
                    S.AN_APPETITE: (S.AN_WONDER,),
                },
                S.RE3_FIELD_SOURCES: {S.RATING: S.RE3_TEST_REVIEW, S.DESCRIPTION: S.GOODREADS},
                S.RE3_FIELD_EVIDENCE: {
                    S.RATING: C.EvidenceTier.SINGLE_SOURCE,
                    S.DESCRIPTION: C.EvidenceTier.SINGLE_SOURCE,
                },
            }
        )
        for book in _books()
    )
    seen: list[int] = []

    def checked(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        assert training
        assert all(book.rating is not C.NONE for book in training)
        assert not {book.work_id for book in training}.intersection(
            book.work_id for book in targets
        )
        for target in targets:
            assert target.rating is C.NONE
            assert not target.rating_conflict
            assert target.review is C.NONE
            assert not target.community_ratings
            assert target.description == S.RE3_TEST_DESCRIPTION
            assert target.features[S.GENRES] == (S.REC_TEST_GENRE,)
            assert target.features[S.AN_APPETITE] == (S.AN_WONDER,)
            assert S.RATING not in target.features
            assert S.RATING not in target.field_states
            assert S.RATING not in target.field_sources
            assert S.RATING not in target.field_evidence
            assert len(target.evidence) == C.ONE
            public = target.evidence[C.ZERO]
            assert public.observation.field == S.DESCRIPTION
            assert public.observation.value == S.RE3_TEST_DESCRIPTION
            assert public.public_url == S.RE3_TEST_PUBLIC_URL
            assert public.detail is C.NONE
            seen.append(target.work_id)
        return _learn_pages(training, targets)

    result = evaluate_ranking(books, current=checked, candidate=checked, genre=checked)
    assert len(seen) == len(books) * C.THREE
    assert result.candidate.metrics.compared_works == len(books)
    assert all(book.rating is not C.NONE and book.review == S.RE3_TEST_REVIEW for book in books)


def test_transitive_coauthors_are_never_split_even_for_small_inner_training_folds() -> None:
    books = _books(C.FIVE)
    first, bridge, last, independent, other = books
    connected = (
        first,
        bridge.model_copy(update={S.AUTHORS: (*first.authors, *last.authors)}),
        last,
        independent,
        other,
    )
    folds = grouped_folds(connected)
    assert len(folds) == C.THREE
    assert folds == grouped_folds(tuple(reversed(connected)))
    together = {first.work_id, bridge.work_id, last.work_id}
    assert any(together.issubset({book.work_id for book in fold}) for fold in folds)
    for fold in _evaluate(connected).folds:
        assert not set(fold.training_work_ids).intersection(fold.heldout_work_ids)
        assert not together.intersection(fold.training_work_ids) or not together.intersection(
            fold.heldout_work_ids
        )
    assert len(grouped_folds((first, independent))) == C.TWO


def test_missing_features_and_scores_keep_same_cohort_with_mean_fallbacks() -> None:
    books = tuple(
        book.model_copy(update={S.PAGE_COUNT: C.NONE, S.DESCRIPTION: C.NONE, S.REC_FEATURES: {}})
        for book in _books()
    )

    def explicit_missing(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        return {target.work_id: C.NONE for target in targets}

    result = evaluate_ranking(
        books, current=_missing, candidate=explicit_missing, genre=explicit_missing
    )
    assert result.cohort_size == len(books)
    assert result.description_covered_works == C.ZERO
    for model in (result.current, result.genre, result.candidate):
        assert model.metrics == result.mean.metrics
        assert model.metrics.compared_works == len(books)
        assert model.mean_fallbacks == len(books)
        assert model.score_count == C.ZERO
    assert not result.activation_eligible
    assert S.RE3_REASON_DESCRIPTIONS in result.reasons
    for fold in result.folds:
        assert fold.training_description_count == C.ZERO
        assert fold.heldout_description_count == C.ZERO


def test_partial_predictions_use_each_folds_training_mean_not_global_mean() -> None:
    def partial(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        mean = sum(book.rating for book in training if book.rating is not C.NONE) / len(training)
        return {targets[C.ZERO].work_id: mean, targets[C.ONE].work_id: C.NONE}

    books = _books(C.RE3_TEST_SMALL_COHORT)
    result = evaluate_ranking(books, current=partial, candidate=partial, genre=partial)
    assert result.candidate.metrics == result.mean.metrics
    assert result.candidate.score_count == len(result.folds)
    assert result.candidate.mean_fallbacks == len(books) - len(result.folds)
    assert all(fold.candidate.metrics == fold.mean.metrics for fold in result.folds)


def test_missing_conflicted_ratings_and_missing_authors_are_explicit_exclusions() -> None:
    books = _books()
    extras = (
        books[C.ZERO].model_copy(update={S.WORK_ID: C.RE3_TEST_FOREIGN_ID, S.RATING: C.NONE}),
        books[C.ONE].model_copy(
            update={
                S.WORK_ID: C.RE3_TEST_FOREIGN_ID + C.ONE,
                S.RE3_TEST_RATING_CONFLICT: C.TRUE,
            }
        ),
        books[C.TWO].model_copy(
            update={S.WORK_ID: C.RE3_TEST_FOREIGN_ID + C.TWO, S.AUTHORS: (S.SPACE,)}
        ),
    )
    result = _evaluate((*books, *extras))
    assert result.input_works == len(books) + C.THREE
    assert result.missing_rating_works == C.ONE
    assert result.conflicted_rating_works == C.ONE
    assert result.missing_author_works == C.ONE
    assert result.valid_rated_works == len(books) + C.ONE
    assert result.cohort_size == len(books)
    assert result.candidate.metrics.compared_works == len(books)


def test_tiny_flat_and_no_positive_cohorts_preserve_unavailable_metrics() -> None:
    tiny = _evaluate(_books(C.ONE))
    assert tiny.status == S.RE3_INSUFFICIENT
    assert not tiny.folds
    assert tiny.mean.metrics.ndcg_at_10 is C.NONE
    assert tiny.mean.metrics.precision_at_10 is C.NONE
    assert tiny.mean.metrics.concordance is C.NONE
    assert not tiny.activation_eligible
    assert S.RE3_REASON_WORKS in tiny.reasons
    assert S.RE3_REASON_COMPONENTS in tiny.reasons
    flat = _evaluate(tuple(book.model_copy(update={S.RATING: C.FOUR}) for book in _books()))
    assert flat.mean.metrics.ndcg_at_10 == pytest.approx(C.ONE)
    assert flat.mean.metrics.concordance is C.NONE
    assert flat.mean.metrics.precision_at_10 is C.NONE
    assert not flat.activation_eligible
    assert S.RE3_REASON_FOLDS in flat.reasons
    assert S.RE3_REASON_PRECISION in flat.reasons
    zero = _evaluate(tuple(book.model_copy(update={S.RATING: C.ZERO}) for book in _books()))
    assert zero.mean.metrics.ndcg_at_10 is C.NONE
    assert zero.mean.metrics.precision_at_10 is C.NONE
    assert zero.mean.metrics.concordance is C.NONE


@pytest.mark.parametrize(S.RE3_TEST_BAD_CASE, C.RE3_TEST_INVALID_CASES)
def test_invalid_predictions_raise_instead_of_silently_counting_success(kind: str) -> None:
    def invalid(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        work_id = targets[C.ZERO].work_id
        if kind == S.RE3_TEST_BAD_FOREIGN:
            return {C.RE3_TEST_FOREIGN_ID: C.ONE}
        if kind == S.RE3_TEST_BAD_NAN:
            return {work_id: C.RE3_TEST_NAN}
        if kind == S.RE3_TEST_BAD_INFINITY:
            return {work_id: C.RE3_TEST_INFINITY}
        if kind == S.RE3_TEST_BAD_TEXT:
            return cast(Mapping[int, float], {work_id: S.RE3_TEST_REVIEW})
        if kind == S.RE3_TEST_BAD_BOOLEAN:
            return {work_id: C.TRUE}
        if kind == S.RE3_TEST_BAD_KEY:
            return {C.TRUE: C.ONE}
        return cast(Mapping[int, float], ())

    with pytest.raises(ValueError):
        evaluate_ranking(_books(), current=_missing, candidate=invalid, genre=_missing)
    with pytest.raises(ValueError):
        evaluate_ranking(
            _books(), current=_missing, candidate=_missing, genre=_missing, length=invalid
        )


def test_duplicate_work_ids_are_rejected_before_callbacks_run() -> None:
    books = _books(C.TWO)
    with pytest.raises(ValueError, match=S.RE3_DUPLICATE_ID):
        _evaluate((*books, books[C.ZERO]))
    with pytest.raises(ValueError, match=S.RE3_DUPLICATE_ID):
        grouped_folds((*books, books[C.ZERO]))


def test_perfect_candidate_does_not_activate_when_current_is_equally_strong() -> None:
    result = evaluate_ranking(
        _books(), current=_learn_pages, candidate=_learn_pages, genre=_missing
    )
    assert not result.activation_eligible
    assert result.candidate_vs_current.ndcg_at_10 == C.ZERO
    assert S.RE3_REASON_IMPROVEMENT in result.reasons
    assert S.RE3_REASON_WINS in result.reasons


def test_no_improvement_never_activates_even_with_all_support_thresholds_met() -> None:
    result = evaluate_ranking(_books(), current=_missing, candidate=_missing, genre=_missing)
    assert result.cohort_size >= C.RE3_MIN_RATED
    assert result.independent_components >= C.RE3_MIN_COMPONENTS
    assert result.usable_folds >= C.RE3_MIN_FOLDS
    assert not result.activation_eligible
    assert S.RE3_REASON_IMPROVEMENT in result.reasons
    assert S.RE3_REASON_WINS in result.reasons
    assert S.RE3_REASON_DESCRIPTIONS not in result.reasons


@pytest.mark.parametrize(S.RE3_TEST_INCLUDE_LENGTH, C.RE3_TEST_OPTIONAL_LENGTH)
def test_ndcg_gains_cannot_hide_precision_regression_against_strongest_comparator(
    include_length: bool,
) -> None:
    books = tuple(
        book.model_copy(
            update={
                S.RATING: C.RE3_TEST_PRECISION_RATINGS[index % C.FOUR],
                S.PAGE_COUNT: index % C.FOUR + C.ONE,
            }
        )
        for index, book in enumerate(_books())
    )

    def current(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        return {
            work_id: float(score >= C.RE3_POSITIVE_THRESHOLD)
            for work_id, score in _learn_pages(training, targets).items()
            if score is not C.NONE
        }

    def candidate(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        return {
            work_id: C.FOUR if score == C.RE3_POSITIVE_THRESHOLD else score
            for work_id, score in _learn_pages(training, targets).items()
        }

    result = evaluate_ranking(
        books,
        current=_missing if include_length else current,
        candidate=candidate,
        genre=_missing,
        length=current if include_length else C.NONE,
    )
    deltas = (
        result.candidate_vs_mean,
        result.candidate_vs_current,
        result.candidate_vs_genre,
        *((result.candidate_vs_length,) if result.candidate_vs_length is not C.NONE else ()),
    )
    for delta in deltas:
        assert delta.ndcg_at_10 is not C.NONE
        assert delta.ndcg_at_10 >= C.RE3_MIN_NDCG_IMPROVEMENT
        assert delta.ndcg_winning_folds == C.RE3_MAX_FOLDS
    strongest_delta = result.candidate_vs_length if include_length else result.candidate_vs_current
    assert strongest_delta is not C.NONE
    assert strongest_delta.precision_at_10 is not C.NONE
    assert strongest_delta.precision_at_10 < C.ZERO
    assert not result.activation_eligible
    assert result.reasons == (S.RE3_REASON_PRECISION,)


@pytest.mark.parametrize(S.RE3_TEST_BAD_FOLDS, C.RE3_TEST_BAD_FOLD_COUNTS)
def test_predefined_fold_win_gate_requires_four_of_five_not_just_average_gain(
    bad_folds: int,
) -> None:
    def candidate(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        direction = -C.ONE if min(book.work_id for book in targets) <= bad_folds else C.ONE
        return {
            work_id: score * direction
            for work_id, score in _learn_pages(training, targets).items()
            if score is not C.NONE
        }

    result = evaluate_ranking(_books(), current=_missing, candidate=candidate, genre=_missing)
    assert result.candidate_vs_mean.ndcg_at_10 is not C.NONE
    assert result.candidate_vs_mean.ndcg_at_10 > C.RE3_MIN_NDCG_IMPROVEMENT
    assert result.activation_eligible == (bad_folds == C.ONE)
    assert (S.RE3_REASON_WINS in result.reasons) == (bad_folds > C.ONE)


@pytest.mark.parametrize(S.RE3_TEST_BAD_FOLDS, C.RE3_TEST_LENGTH_BAD_FOLDS)
def test_length_comparator_tying_or_beating_candidate_blocks_activation(bad_folds: int) -> None:
    def candidate(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        direction = -C.ONE if min(book.work_id for book in targets) <= bad_folds else C.ONE
        return {
            work_id: score * direction
            for work_id, score in _learn_pages(training, targets).items()
            if score is not C.NONE
        }

    books = _books()
    without_length = evaluate_ranking(books, current=_missing, candidate=candidate, genre=_missing)
    assert without_length.activation_eligible
    result = evaluate_ranking(
        books, current=_missing, candidate=candidate, genre=_missing, length=_learn_pages
    )
    assert result.length is not C.NONE
    assert result.length.score_count == len(books)
    assert result.length.metrics.compared_works == len(books)
    assert result.candidate_vs_length is not C.NONE
    assert result.candidate_vs_length.ndcg_at_10 is not C.NONE
    assert result.candidate_vs_length.ndcg_at_10 <= C.ZERO
    assert result.candidate_vs_length.ndcg_winning_folds == C.ZERO
    assert not result.activation_eligible
    assert S.RE3_REASON_IMPROVEMENT in result.reasons
    assert S.RE3_REASON_WINS in result.reasons


def test_supplied_length_comparator_is_included_in_eighty_percent_fold_win_gate() -> None:
    def length(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        return _learn_pages(training, targets) if targets[C.ZERO].work_id <= C.TWO else {}

    result = evaluate_ranking(
        _books(), current=_missing, candidate=_learn_pages, genre=_missing, length=length
    )
    assert result.candidate_vs_length is not C.NONE
    assert result.candidate_vs_length.ndcg_at_10 is not C.NONE
    assert result.candidate_vs_length.ndcg_at_10 >= C.RE3_MIN_NDCG_IMPROVEMENT
    assert result.candidate_vs_length.ndcg_winning_folds == C.THREE
    assert not result.activation_eligible
    assert result.reasons == (S.RE3_REASON_WINS,)


def test_length_missing_features_use_same_blinded_cohort_and_tracked_mean_fallbacks() -> None:
    books = tuple(
        book.model_copy(update={S.PAGE_COUNT: C.NONE}) if index % C.THREE == C.ZERO else book
        for index, book in enumerate(_books())
    )
    seen: list[int] = []

    def length(
        training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
    ) -> Mapping[int, float | None]:
        assert all(book.rating is not C.NONE for book in training)
        assert not {book.work_id for book in training}.intersection(
            book.work_id for book in targets
        )
        assert all(
            book.rating is C.NONE
            and not book.rating_conflict
            and book.review is C.NONE
            and not book.community_ratings
            for book in targets
        )
        seen.extend(book.work_id for book in targets)
        return _learn_pages(
            training, tuple(book for book in targets if book.page_count is not C.NONE)
        )

    result = evaluate_ranking(
        books, current=_missing, candidate=_learn_pages, genre=_missing, length=length
    )
    assert sorted(seen) == sorted(book.work_id for book in books)
    assert result.length is not C.NONE
    assert result.length.metrics.compared_works == len(books)
    assert result.length.metrics.positive_works == result.mean.metrics.positive_works
    assert result.length.mean_fallbacks == sum(book.page_count is C.NONE for book in books)
    assert result.length.score_count + result.length.mean_fallbacks == len(books)
    for fold in result.folds:
        assert fold.length is not C.NONE
        assert fold.length.metrics.compared_works == len(fold.heldout_work_ids)
        assert fold.length.metrics.positive_works == fold.mean.metrics.positive_works
