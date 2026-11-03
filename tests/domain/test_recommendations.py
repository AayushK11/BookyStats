from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisComponent,
    AnalysisEvidence,
    AnalysisInput,
    AnalyticsReport,
    PossibleReadMatch,
)
from bookystats.domain.models import FieldState, Observation, ReadingStatus, Source
from bookystats.domain.recommendations import build_recommendations, recommendation_key
from tests.application.test_statistics import _book, _data


def analysis(data: AnalysisInput) -> AnalyticsReport:
    return AnalyticsReport(
        manifest=data.manifest,
        as_of=data.as_of,
        taste=AnalysisComponent(
            key=C.AN_STORE_TEST_KEYS[C.ZERO],
            kind=C.AnalyticsComponentKind.TASTE,
            findings=(),
        ),
        watchlist=AnalysisComponent(
            key=C.AN_STORE_TEST_KEYS[C.ONE],
            kind=C.AnalyticsComponentKind.WATCHLIST,
            findings=(),
        ),
    )


def data(*books: AnalysisBook) -> AnalysisInput:
    return _data(*books).model_copy(update={S.REC_AS_OF: S.REC_TEST_AS_OF})


def candidate(work_id: int = C.THREE) -> AnalysisBook:
    return _book(
        work_id,
        author=S.REC_TEST_AUTHOR,
        genre=S.REC_TEST_GENRE,
        status=ReadingStatus.TO_READ,
    )


def history() -> tuple[AnalysisBook, ...]:
    return (
        _book(C.ONE, C.FIVE, author=S.REC_TEST_AUTHOR, genre=S.REC_TEST_GENRE),
        _book(C.TWO, C.ONE, author=S.REC_TEST_OTHER_AUTHOR, genre=S.REC_TEST_OTHER_GENRE),
    )


def test_excludes_completed_active_paused_dnf_and_collapses_confirmed_editions() -> None:
    variants = [
        candidate(C.THREE).model_copy(update={S.COLLECTIONS: (S.TO_READ,), S.STATUS: status})
        for status in C.REC_BLOCKED_STATUSES
    ]
    for book in variants:
        pinned = data(*history(), book)
        report = build_recommendations(pinned, analysis(pinned))
        assert not report.ranked
        assert len(report.excluded) == C.ONE
        assert report.excluded[C.ZERO].ranking_score is C.NONE
    duplicate = candidate(C.ONE)
    pinned = data(*history(), duplicate)
    report = build_recommendations(pinned, analysis(pinned))
    assert len(report.excluded) == C.ONE
    assert report.excluded[C.ZERO].reasons == (S.REC_READ,)


def test_future_publication_respects_original_and_edition_scope() -> None:
    original = candidate().model_copy(update={S.REC_ORIGINAL_YEAR: C.REC_FUTURE_YEAR})
    edition = candidate(C.FOUR).model_copy(update={S.REC_YEAR: C.REC_FUTURE_YEAR})
    unknown = candidate(C.FIVE)
    pinned = data(*history(), original, edition, unknown)
    report = build_recommendations(pinned, analysis(pinned))
    assert len(report.ranked) == C.ONE
    assert report.ranked[C.ZERO].work_id == C.FIVE
    assert S.REC_UNKNOWN_PUBLICATION in report.ranked[C.ZERO].missingness
    assert {item.reasons[C.ZERO] for item in report.excluded} == {
        S.REC_UNRELEASED_WORK,
        S.REC_UNRELEASED_EDITION,
    }


@pytest.mark.parametrize(S.REC_TEST_PUBLICATION, C.REC_TEST_PUBLICATIONS)
def test_known_future_month_or_day_is_not_reduced_to_a_released_year(
    date: str, scope: S.ObservationScope, field: str, reason: str
) -> None:
    observation = AnalysisEvidence(
        source=Source.GOODREADS.value,
        source_id=S.ONE_2,
        observation=Observation(
            field=field,
            value=date,
            scope=scope,
            state=FieldState.PRESENT,
            source_url=S.CONTENT_ANALYSIS_TEST_FILE_URL,
        ),
    )
    future = candidate().model_copy(
        update={
            S.REC_YEAR: int(S.REC_TEST_CURRENT_YEAR),
            S.REC_ORIGINAL_YEAR: int(S.REC_TEST_CURRENT_YEAR),
            S.AN_EVIDENCE: (observation,),
        }
    )
    pinned = data(*history(), future)
    report = build_recommendations(pinned, analysis(pinned))
    assert not report.ranked
    assert report.excluded[C.ZERO].reasons == (reason,)


def test_possible_read_links_abstain_without_forcing_an_identity() -> None:
    target = PossibleReadMatch(
        candidate_id=C.ONE,
        work_id=C.ONE,
        source=Source.GOODREADS,
        source_id=S.ONE_2,
        source_snapshot_ids=(C.ONE,),
    )
    possible = candidate().model_copy(update={S.REC_POSSIBLE_READ_MATCHES: (target,)})
    pinned = data(*history(), possible)
    report = build_recommendations(pinned, analysis(pinned))
    assert not report.ranked
    assert report.unrankable[C.ZERO].work_id == C.THREE
    assert report.unrankable[C.ZERO].identity_tier == S.REC_POSSIBLE
    assert report.unrankable[C.ZERO].ranking_score is C.NONE


def test_same_title_author_overlap_is_not_a_confirmed_match() -> None:
    completed = history()[C.ZERO]
    possible = candidate().model_copy(update={S.TITLE: completed.title})
    pinned = data(*history(), possible)
    report = build_recommendations(pinned, analysis(pinned))
    assert not report.excluded
    assert report.unrankable[C.ZERO].reasons == (S.REC_POSSIBLE_READ,)


def test_scores_use_shared_read_personal_ratings_not_candidate_or_community_or_reviews() -> None:
    pinned = data(*history(), candidate())
    report = build_recommendations(pinned, analysis(pinned))
    changed = data(
        *(
            book.model_copy(
                update={
                    S.REVIEW: S.REC_NO_SIGNAL,
                    S.REC_COMMUNITY_RATINGS: {Source.GOODREADS.value: C.FIVE},
                }
            )
            for book in history()
        ),
        candidate().model_copy(
            update={
                S.RATING: C.ONE,
                S.REVIEW: S.REC_NO_SIGNAL,
                S.REC_COMMUNITY_RATINGS: {Source.GOODREADS.value: C.ONE},
            }
        ),
    )
    repeated = build_recommendations(changed, analysis(changed))
    assert repeated.key == report.key
    assert repeated.ranked == report.ranked
    item = report.ranked[C.ZERO]
    assert item.ranking_score is not C.NONE and item.ranking_score > C.ZERO
    assert item.score_label == S.REC_SCORE_LABEL
    assert tuple(example.work_id for example in item.supporting_books) == (C.ONE,)
    assert item.preference_tier == S.REC_LIMITED


def test_explicit_disliked_shared_examples_are_visible_not_hidden() -> None:
    dislike = candidate().model_copy(
        update={
            S.AUTHORS: (S.REC_TEST_OTHER_AUTHOR,),
            S.REC_FEATURES: {S.GENRES: (S.REC_TEST_OTHER_GENRE,)},
        }
    )
    pinned = data(*history(), dislike)
    report = build_recommendations(pinned, analysis(pinned))
    item = report.ranked[C.ZERO]
    assert item.ranking_score is not C.NONE and item.ranking_score < C.ZERO
    assert item.mismatches
    assert item.supporting_books[C.ZERO].rating == C.ONE


def test_no_shared_signal_abstains_and_unknowns_are_not_penalized() -> None:
    unknown = _book(C.FOUR, status=ReadingStatus.TO_READ)
    author_only = candidate().model_copy(update={S.REC_FEATURES: {}})
    pinned = data(*history(), unknown, author_only)
    report = build_recommendations(pinned, analysis(pinned))
    assert len(report.unrankable) == C.ONE
    assert report.unrankable[C.ZERO].work_id == C.FOUR
    assert report.unrankable[C.ZERO].ranking_score is C.NONE
    assert S.REC_NO_SIGNAL in report.unrankable[C.ZERO].reasons
    assert len(report.ranked) == C.ONE
    assert report.ranked[C.ZERO].components[C.ZERO].feature == S.REC_AUTHOR
    assert S.REC_UNKNOWN_GENRE in report.ranked[C.ZERO].missingness


def test_unrated_and_conflicted_read_ratings_are_not_training_examples() -> None:
    unrated = _book(C.ONE, author=S.REC_TEST_AUTHOR, genre=S.REC_TEST_GENRE)
    conflicted = history()[C.ZERO].model_copy(
        update={S.WORK_ID: C.TWO, S.REC_RATING_CONFLICT: C.TRUE}
    )
    pinned = data(unrated, conflicted, candidate())
    report = build_recommendations(pinned, analysis(pinned))
    assert not report.ranked
    assert len(report.unrankable) == C.ONE
    assert S.REC_NO_RATING in report.limitations


def test_deterministic_ties_and_varied_author_cap_keep_full_ranking() -> None:
    candidates = tuple(candidate(index) for index in range(C.THREE, C.TEN))
    pinned = data(*history(), *candidates, candidates[C.ZERO])
    reversed_input = pinned.model_copy(update={S.BOOKS: tuple(reversed(pinned.books))})
    first = build_recommendations(pinned, analysis(pinned))
    second = build_recommendations(reversed_input, analysis(reversed_input))
    assert first == second
    assert len(first.ranked) == C.TEN - C.THREE
    assert len(first.shortlist) == C.REC_AUTHOR_CAP
    assert len({item.work_id for item in first.ranked}) == len(first.ranked)


def test_shortlist_series_cap_uses_verified_evidence_not_browser_labels() -> None:
    selected = []
    for work_id in range(C.THREE, C.TEN):
        book = candidate(work_id).model_copy(
            update={
                S.AUTHORS: (str(work_id),),
                S.REC_FEATURES: {
                    S.GENRES: (S.REC_TEST_GENRE,),
                    S.SERIES: (S.REC_TEST_SERIES,),
                },
                S.AN_EVIDENCE: (
                    AnalysisEvidence(
                        source=Source.OPEN_LIBRARY.value,
                        source_id=str(work_id),
                        observation=Observation(
                            field=S.SERIES,
                            value=S.REC_TEST_SERIES,
                            state=FieldState.PRESENT,
                            scope=S.WORK,
                            source_url=S.CONTENT_ANALYSIS_TEST_FILE_URL,
                        ),
                    ),
                ),
            }
        )
        selected.append(book)
    pinned = data(*history(), *selected)
    report = build_recommendations(pinned, analysis(pinned))
    assert len(report.shortlist) == C.REC_SERIES_CAP
    unverified = data(
        *history(),
        *(book.model_copy(update={S.AN_EVIDENCE: ()}) for book in selected),
    )
    unverified_report = build_recommendations(unverified, analysis(unverified))
    assert len(unverified_report.shortlist) == len(selected)
    assert all(S.REC_UNKNOWN_SERIES in item.missingness for item in unverified_report.ranked)


def test_cache_key_changes_for_day_ratings_and_possible_read_state_not_recapture() -> None:
    pinned = data(*history(), candidate())
    changed_day = pinned.model_copy(update={S.REC_AS_OF: S.REC_TEST_FUTURE_AS_OF})
    changed_rating = data(
        history()[C.ZERO].model_copy(update={S.RATING: C.FOUR}), history()[C.ONE], candidate()
    )
    assert recommendation_key(pinned, analysis(pinned)) != recommendation_key(
        changed_day, analysis(changed_day)
    )
    assert recommendation_key(pinned, analysis(pinned)) != recommendation_key(
        changed_rating, analysis(changed_rating)
    )
