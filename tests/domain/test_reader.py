from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisBook, AnalysisInput, AnalysisManifest
from bookystats.domain.models import FieldState, ReadingStatus, Source
from bookystats.domain.reader import build_reader_summary


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
