from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisEvidence,
    AnalysisInput,
    AnalysisManifest,
)
from bookystats.domain.models import FieldState, Observation, ReadingStatus, Source
from bookystats.domain.reader import (
    build_reader_summary,
    community_sample_size,
    tier_counts,
    usual_rating,
)


def _book(work_id: int, rating: float | None = C.NONE) -> AnalysisBook:
    return AnalysisBook(
        work_id=work_id,
        source_ids=(str(work_id),),
        title=S.AN_CALC_TEST_AUTHOR_FORMAT.format(index=work_id),
        authors=(S.REC_TEST_AUTHOR,),
        status=ReadingStatus.READ,
        rating=rating,
        features={S.GENRES: (S.AN_CALC_TEST_GENRE,)},
        page_count=C.AN_CALC_SHORT_LIMIT,
    )


def _data(*books: AnalysisBook) -> AnalysisInput:
    return AnalysisInput(
        books=books,
        manifest=AnalysisManifest(
            account_fingerprint=S.AN_CALC_TEST_ACCOUNT,
            snapshots=(),
            settings_hash=S.AN_CALC_TEST_HASH,
        ),
    )


def _crowd_size(
    book: AnalysisBook,
    *sizes: int | None,
    field: str = S.RATINGS_COUNT,
    source: str = S.GOODREADS,
    scope: S.ObservationScope = S.WORK,
) -> AnalysisBook:
    evidence = tuple(
        AnalysisEvidence(
            source=source,
            source_id=str(book.work_id),
            observation=Observation(
                field=field,
                value=size,
                scope=scope,
                state=FieldState.PRESENT if size is not C.NONE else FieldState.UNAVAILABLE,
                source_url=S.CONTENT_ANALYSIS_TEST_URL,
            ),
        )
        for size in sizes
    )
    return book.model_copy(
        update={
            S.AN_EVIDENCE: evidence,
            S.REC_COMMUNITY_RATINGS: {Source.GOODREADS.value: C.THREE},
        }
    )


def test_unrated_and_conflicted_works_remain_in_read_denominators_not_rating_means() -> None:
    missing = _book(C.TWO).model_copy(
        update={
            S.AUTHORS: (),
            S.AN_CALC_FIELD_STATES_FIELD: {
                S.GENRES: FieldState.FAILED,
                S.PAGE_COUNT: FieldState.UNAVAILABLE,
            },
        }
    )
    conflict = _book(C.THREE, C.ONE).model_copy(update={S.AN_CALC_RATING_CONFLICT: C.TRUE})
    summary = build_reader_summary(_data(_book(C.ONE, C.FIVE), missing, conflict))
    assert summary.read == C.THREE
    assert summary.rated == C.ONE and summary.conflicting_ratings == C.ONE
    assert summary.average == C.FIVE and summary.favorites == C.ONE
    assert summary.pages_known == summary.genres_known == summary.authors_known == C.TWO
    assert summary.genres[C.ZERO].works == C.TWO
    assert summary.genres[C.ZERO].rated == C.ONE
    assert summary.genres[C.ZERO].adjusted_average is C.NONE
    assert summary.favorite_examples == (C.ONE,)


def test_watchlist_familiarity_uses_all_read_authors_including_unrated_works() -> None:
    familiar = _book(C.TWO).model_copy(update={S.STATUS: ReadingStatus.TO_READ})
    unfamiliar = _book(C.THREE).model_copy(
        update={S.STATUS: ReadingStatus.TO_READ, S.AUTHORS: (S.REC_TEST_OTHER_AUTHOR,)}
    )
    unknown = _book(C.FOUR).model_copy(update={S.STATUS: ReadingStatus.TO_READ, S.AUTHORS: ()})
    summary = build_reader_summary(_data(_book(C.ONE), familiar, unfamiliar, unknown))
    assert summary.read == C.ONE and summary.watchlist == C.THREE
    assert summary.watchlist_familiar_authors == C.ONE
    assert summary.watchlist_new_authors == C.ONE
    assert summary.watchlist_unknown_authors == C.ONE
    assert summary.rated == C.ZERO and summary.average is C.NONE


def test_crowd_comparisons_are_separate_and_never_change_personal_preference_groups() -> None:
    original = _book(C.ONE, C.FIVE)
    compared = original.model_copy(
        update={S.REC_COMMUNITY_RATINGS: {Source.GOODREADS.value: C.THREE}}
    )
    before = build_reader_summary(_data(original))
    after = build_reader_summary(_data(compared))
    assert after.average == before.average == C.FIVE
    assert after.genres == before.genres and after.authors == before.authors
    assert after.favorite_examples == before.favorite_examples
    assert not before.community_comparisons
    comparison = after.community_comparisons[C.ZERO]
    assert comparison.personal == C.FIVE and comparison.community == C.THREE
    assert comparison.difference == C.TWO
    assert comparison.community_sample_size is C.NONE
    invalid = compared.model_copy(update={S.REC_COMMUNITY_RATINGS: {Source.GOODREADS.value: C.TEN}})
    assert not build_reader_summary(_data(invalid)).community_comparisons


def test_reader_examples_are_deterministic_and_duplicate_work_ids_are_rejected() -> None:
    first, second = _book(C.ONE, C.FIVE), _book(C.TWO, C.FIVE)
    assert build_reader_summary(_data(first, second)) == build_reader_summary(_data(second, first))
    with pytest.raises(ValueError, match=S.RD_DUPLICATE):
        build_reader_summary(_data(first, first))


def test_goodreads_browser_ratings_count_is_the_comparison_sample_size() -> None:
    # The Goodreads browser import writes `ratings_count`; the provider spelling also counts.
    for field in (S.RATINGS_COUNT, S.COMMUNITY_RATINGS_COUNT):
        book = _crowd_size(_book(C.ONE, C.FIVE), C.AN3_TEST_CROWD_SIZE, field=field)
        comparison = build_reader_summary(_data(book)).community_comparisons[C.ZERO]
        assert comparison.community_sample_size == C.AN3_TEST_CROWD_SIZE
        assert comparison.community == C.THREE and comparison.personal == C.FIVE


def test_crowd_sample_size_requires_one_positive_goodreads_work_count() -> None:
    base = _book(C.ONE, C.FIVE)
    size = C.AN3_TEST_CROWD_SIZE
    assert community_sample_size(_crowd_size(base, size, size)) == size
    unusable = (
        _crowd_size(base, size, C.AN3_TEST_CROWD_OTHER_SIZE),
        _crowd_size(base, C.NONE),
        _crowd_size(base, C.ZERO),
        _crowd_size(base, -C.ONE),
        _crowd_size(base, C.TRUE),
        _crowd_size(base, size, source=S.OPEN_LIBRARY),
        _crowd_size(base, size, scope=S.EDITION),
        base,
    )
    for book in unusable:
        assert community_sample_size(book) is C.NONE
    for book in unusable[: -C.ONE]:
        comparison = build_reader_summary(_data(book)).community_comparisons[C.ZERO]
        assert comparison.community_sample_size is C.NONE


def test_rating_tiers_are_relative_to_the_usual_rating_not_the_configured_threshold() -> None:
    ratings = (C.THREE, C.THREE, C.THREE, C.FOUR, C.FIVE, C.TWO)
    summary = build_reader_summary(
        _data(*(_book(index, value) for index, value in enumerate(ratings, C.ONE)))
    )
    assert summary.usual_rating == C.THREE and not summary.tied_usual_ratings
    assert (summary.standout, summary.solid, summary.below_usual) == (C.TWO, C.THREE, C.ONE)
    assert summary.standout + summary.solid + summary.below_usual == summary.rated
    assert summary.standout_examples == (C.FIVE, C.FOUR)
    group = summary.genres[C.ZERO]
    assert (group.standouts, group.below_usual) == (C.TWO, C.ONE)
    # The legacy threshold fields keep their meaning for older saved-report consumers.
    assert summary.favorites == C.TWO and summary.favorite_threshold == C.FOUR


def test_tied_usual_ratings_use_the_lowest_and_are_disclosed() -> None:
    assert usual_rating((C.THREE, C.FIVE, C.THREE, C.FIVE, C.FOUR)) == (C.THREE, C.FIVE)
    assert usual_rating(()) == ()
    ratings = (C.FIVE, C.THREE, C.FIVE, C.THREE)
    summary = build_reader_summary(
        _data(*(_book(index, value) for index, value in enumerate(ratings, C.ONE)))
    )
    assert summary.usual_rating == C.THREE and summary.tied_usual_ratings == (C.THREE, C.FIVE)
    assert (summary.standout, summary.solid, summary.below_usual) == (C.TWO, C.TWO, C.ZERO)
    assert tier_counts((C.ONE, C.TWO), C.NONE) == (C.ZERO, C.ZERO, C.ZERO)
    unrated = build_reader_summary(_data(_book(C.ONE)))
    assert unrated.usual_rating is C.NONE
    assert (unrated.standout, unrated.solid, unrated.below_usual) == (C.ZERO, C.ZERO, C.ZERO)
