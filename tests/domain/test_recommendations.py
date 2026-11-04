from __future__ import annotations

import pytest
from pydantic import JsonValue

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
from bookystats.domain.recommendation_evaluation import (
    author_components,
    evaluate_recommendations,
    fit_profile,
)
from bookystats.domain.recommendations import (
    RecommendationItem,
    RecommendationReport,
    _features,
    _shortlist,
    build_recommendations,
    recommendation_key,
)
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


def test_shortlist_can_trade_small_score_differences_for_variety_without_mutating_ranking() -> None:
    books = {
        work_id: _book(
            work_id,
            genre=S.REC_TEST_GENRE if work_id <= C.TWO else S.REC_TEST_OTHER_GENRE,
            status=ReadingStatus.TO_READ,
        )
        for work_id in range(C.ONE, C.FIVE)
    }
    ranked = tuple(
        RecommendationItem(
            work_id=book.work_id,
            title=book.title,
            authors=book.authors,
            source_ids=book.source_ids,
            status=S.REC_RANKED,
            ranking_score=score,
        )
        for book, score in zip(books.values(), C.REC3_TEST_SHORTLIST_SCORES, strict=C.TRUE)
    )
    shortlist = _shortlist(ranked, books)
    assert tuple(item.work_id for item in shortlist[: C.THREE]) == (C.ONE, C.THREE, C.TWO)
    assert shortlist[-C.ONE].work_id == C.FOUR
    assert tuple(item.work_id for item in ranked) == (C.ONE, C.TWO, C.THREE, C.FOUR)


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


def series_book(
    book: AnalysisBook, position: str | None, *, multiple: bool = C.FALSE
) -> AnalysisBook:
    memberships: list[JsonValue] = [
        {
            S.WD_SERIES_ID: S.REC2_TEST_QID,
            S.WD_NAME: S.REC_TEST_SERIES,
            S.WD_POSITION: position,
        }
    ]
    if multiple:
        memberships.append(
            {
                S.WD_SERIES_ID: S.REC2_TEST_OTHER_QID,
                S.WD_NAME: S.REC_TEST_SERIES,
                S.WD_POSITION: S.REC2_TEST_POSITION_ONE,
            }
        )
    return book.model_copy(
        update={
            S.AN_EVIDENCE: (
                AnalysisEvidence(
                    source=Source.WIKIDATA.value,
                    source_id=S.REC2_TEST_QID,
                    observation=Observation(
                        field=S.WD_SERIES_MEMBERSHIPS,
                        value=memberships,
                        state=FieldState.PRESENT,
                        scope=S.WORK,
                        source_url=S.REC2_TEST_URL,
                    ),
                ),
            )
        }
    )


def test_verified_order_changes_shortlist_not_global_scores_or_completed_eligibility() -> None:
    first, other = history()
    pinned = data(
        series_book(first, S.REC2_TEST_POSITION_ONE),
        other,
        series_book(candidate(C.THREE), S.REC2_TEST_POSITION_THREE),
        series_book(candidate(C.FOUR), S.REC2_TEST_POSITION_TWO),
        series_book(candidate(C.ONE), S.REC2_TEST_POSITION_ONE),
    )
    report = build_recommendations(pinned, analysis(pinned))
    assert tuple(item.work_id for item in report.ranked) == (C.THREE, C.FOUR)
    assert tuple(item.work_id for item in report.shortlist) == (C.FOUR, C.THREE)
    context = report.ranked[C.ZERO].series_context[C.ZERO]
    assert context.earlier_eligible_work_ids == (C.FOUR,)
    assert context.known_completed_positions == (C.ONE,)
    assert context.explanation
    assert report.shortlist[C.ZERO].series_context[C.ZERO].next_after_known_completed
    assert report.excluded[C.ZERO].work_id == C.ONE


@pytest.mark.parametrize(
    S.REC2_POSITION,
    C.REC2_TEST_UNKNOWN_POSITIONS,
)
def test_unknown_or_fractional_series_positions_do_not_force_order(position: str | None) -> None:
    pinned = data(
        *history(),
        series_book(candidate(C.THREE), S.REC2_TEST_POSITION_THREE),
        series_book(candidate(C.FOUR), position),
    )
    report = build_recommendations(pinned, analysis(pinned))
    assert tuple(item.work_id for item in report.shortlist) == (C.THREE, C.FOUR)
    assert not report.ranked[C.ZERO].series_context[C.ZERO].earlier_eligible_work_ids


def test_multiple_memberships_and_conflicting_ordinals_abstain_from_order() -> None:
    later = series_book(candidate(C.THREE), S.REC2_TEST_POSITION_THREE)
    earlier = series_book(candidate(C.FOUR), S.REC2_TEST_POSITION_ONE, multiple=C.TRUE)
    pinned = data(*history(), later, earlier)
    report = build_recommendations(pinned, analysis(pinned))
    assert report.shortlist[C.ZERO].work_id == C.THREE
    contradictory = series_book(candidate(C.FOUR), S.REC2_TEST_POSITION_TWO)
    conflict = earlier.model_copy(
        update={
            S.AN_EVIDENCE: (
                *series_book(candidate(C.FOUR), S.REC2_TEST_POSITION_ONE).evidence,
                *contradictory.evidence,
            )
        }
    )
    pinned = data(*history(), later, conflict)
    report = build_recommendations(pinned, analysis(pinned))
    assert report.shortlist[C.ZERO].work_id == C.THREE
    assert report.ranked[C.ONE].series_context[C.ZERO].position is C.NONE


def test_legacy_open_library_series_pairing_requires_single_name_and_position() -> None:
    def legacy(book: AnalysisBook, positions: list[JsonValue]) -> AnalysisBook:
        return book.model_copy(
            update={
                S.AN_EVIDENCE: tuple(
                    AnalysisEvidence(
                        source=Source.OPEN_LIBRARY.value,
                        source_id=str(book.work_id),
                        observation=Observation(
                            field=field,
                            value=value,
                            scope=S.WORK,
                            state=FieldState.PRESENT,
                            source_url=S.REC2_TEST_OL_URL,
                        ),
                    )
                    for field, value in (
                        (S.SERIES, [S.REC_TEST_SERIES]),
                        (S.META_COVERAGE_SERIES_POSITIONS, positions),
                    )
                )
            }
        )

    later = legacy(candidate(C.THREE), [S.REC2_TEST_POSITION_THREE])
    earlier = legacy(candidate(C.FOUR), [S.REC2_TEST_POSITION_ONE])
    pinned = data(*history(), later, earlier)
    report = build_recommendations(pinned, analysis(pinned))
    assert tuple(item.work_id for item in report.shortlist) == (C.FOUR, C.THREE)
    ambiguous = legacy(candidate(C.FOUR), [S.REC2_TEST_POSITION_ONE, S.REC2_TEST_POSITION_TWO])
    pinned = data(*history(), later, ambiguous)
    assert build_recommendations(pinned, analysis(pinned)).shortlist[C.ZERO].work_id == C.THREE
    cross_provider = data(
        *history(), series_book(candidate(C.THREE), S.REC2_TEST_POSITION_THREE), earlier
    )
    report = build_recommendations(cross_provider, analysis(cross_provider))
    assert report.shortlist[C.ZERO].work_id == C.THREE


def test_unsupported_counterevidence_vetoes_order_without_dropping_candidate() -> None:
    earlier = series_book(candidate(C.FOUR), S.REC2_TEST_POSITION_ONE)
    evidence = earlier.evidence[C.ZERO]
    unsupported = evidence.model_copy(
        update={
            S.REC2_TEST_OBSERVATION_KEY: evidence.observation.model_copy(
                update={S.STATE: FieldState.UNAVAILABLE, S.VALUE: C.NONE}
            )
        }
    )
    earlier = earlier.model_copy(update={S.AN_EVIDENCE: (*earlier.evidence, unsupported)})
    pinned = data(*history(), series_book(candidate(C.THREE), S.REC2_TEST_POSITION_THREE), earlier)
    report = build_recommendations(pinned, analysis(pinned))
    assert report.shortlist[C.ZERO].work_id == C.THREE
    assert report.ranked[C.ONE].series_context[C.ZERO].position is C.NONE


def test_diversity_breaks_equal_scores_without_overriding_clear_quality() -> None:
    books = {
        C.THREE: candidate(C.THREE),
        C.FOUR: candidate(C.FOUR),
        C.FIVE: candidate(C.FIVE).model_copy(update={S.AUTHORS: (S.REC_TEST_OTHER_AUTHOR,)}),
    }

    def item(work_id: int, score: float) -> RecommendationItem:
        book = books[work_id]
        return RecommendationItem(
            work_id=work_id,
            title=book.title,
            authors=book.authors,
            source_ids=book.source_ids,
            status=S.REC_RANKED,
            ranking_score=score,
        )

    tied = _shortlist((item(C.THREE, C.ONE), item(C.FOUR, C.ONE), item(C.FIVE, C.ONE)), books)
    assert tuple(book.work_id for book in tied) == (C.THREE, C.FIVE, C.FOUR)
    quality = _shortlist((item(C.THREE, C.TWO), item(C.FOUR, C.TWO), item(C.FIVE, C.ONE)), books)
    assert tuple(book.work_id for book in quality) == (C.THREE, C.FOUR, C.FIVE)


def evaluation_history() -> tuple[AnalysisBook, ...]:
    return tuple(
        _book(
            index + C.ONE,
            C.ONE if index % C.TWO else C.FIVE,
            author=S.REC2_TEST_AUTHOR.format(index=index),
            genre=S.REC_TEST_GENRE if index % C.TWO else S.REC_TEST_OTHER_GENRE,
        ).model_copy(
            update={
                S.PAGE_COUNT: C.INTEGRATION_PAGE_COUNT + index,
                S.REC_ORIGINAL_YEAR: C.REC_FUTURE_YEAR - index,
            }
        )
        for index in range(C.REC2_MIN_RATED)
    )


def test_evaluation_uses_same_cohort_training_only_means_and_keeps_shadow_inactive() -> None:
    books = evaluation_history()
    result = evaluate_recommendations(books, _features)
    assert result.status == S.REC2_AVAILABLE
    assert result.cohort_size == len(books)
    assert not result.new_scoring_active
    by_id = {book.work_id: book for book in books}
    expected_errors = []
    seen: list[int] = []
    for fold in result.folds:
        assert not set(fold.training_work_ids).intersection(fold.heldout_work_ids)
        training = tuple(by_id[work_id] for work_id in fold.training_work_ids)
        baseline = sum(book.rating for book in training if book.rating is not C.NONE) / len(
            training
        )
        for work_id in fold.heldout_work_ids:
            rating = by_id[work_id].rating
            assert rating is not C.NONE
            expected_errors.append(abs(baseline - rating))
        seen.extend(fold.heldout_work_ids)
    assert sorted(seen) == sorted(by_id)
    assert result.mean_mae == pytest.approx(sum(expected_errors) / len(expected_errors))
    assert result.current_heuristic_mae is not C.NONE
    assert result.simple_length_mae is not C.NONE
    assert result.shadow_candidate_mae is not C.NONE
    assert result == evaluate_recommendations(tuple(reversed(books)), _features)


def test_connected_coauthors_stay_together_and_training_vocabulary_has_no_heldout_tokens() -> None:
    first = _book(C.ONE, C.FIVE, author=S.REC_TEST_AUTHOR, genre=S.REC_TEST_GENRE)
    bridge = _book(C.TWO, C.FOUR).model_copy(
        update={S.AUTHORS: (S.REC_TEST_AUTHOR, S.REC_TEST_OTHER_AUTHOR)}
    )
    last = _book(C.THREE, C.THREE, author=S.REC_TEST_OTHER_AUTHOR)
    assert len(author_components((first, bridge, last))) == C.ONE
    training = (first.model_copy(update={S.PAGE_COUNT: C.INTEGRATION_PAGE_COUNT}),)
    profile = fit_profile(training, _features, richer=C.TRUE)
    assert (S.REC_AUTHOR, S.REC_TEST_OTHER_AUTHOR.casefold()) not in profile.signals
    assert (S.GENRES, S.REC_TEST_OTHER_GENRE) not in profile.signals
    assert profile.cutoffs[S.REC2_LENGTH] == C.INTEGRATION_PAGE_COUNT


def test_insufficient_evaluation_is_unavailable_not_zero_and_old_reports_parse() -> None:
    pinned = data(*history(), candidate())
    report = build_recommendations(pinned, analysis(pinned))
    assert report.evaluation is not C.NONE
    assert report.evaluation.status == S.REC2_UNAVAILABLE
    assert report.evaluation.mean_mae is C.NONE
    assert report.evaluation.reason
    legacy = report.model_dump(mode=S.JSON)
    legacy.pop(S.REC2_EVALUATION)
    assert RecommendationReport.model_validate(legacy).evaluation is C.NONE


def test_evaluation_cache_tracks_numeric_inputs_and_provenance_but_not_capture_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = series_book(candidate(), S.REC2_TEST_POSITION_ONE)
    pinned = data(*history(), book)
    original = recommendation_key(pinned, analysis(pinned))
    evidence = book.evidence[C.ZERO]
    observed = evidence.model_copy(
        update={
            S.REC2_TEST_OBSERVATION_KEY: evidence.observation.model_copy(
                update={S.REC2_TEST_OBSERVED_KEY: S.REC2_TEST_OBSERVED_AT}
            )
        }
    )
    recaptured = data(*history(), book.model_copy(update={S.AN_EVIDENCE: (observed,)}))
    assert recommendation_key(recaptured, analysis(recaptured)) == original
    provenance = evidence.model_copy(update={S.REC2_PUBLIC_URL: S.REC2_TEST_PUBLIC_URL})
    rebound = data(*history(), book.model_copy(update={S.AN_EVIDENCE: (provenance,)}))
    assert recommendation_key(rebound, analysis(rebound)) != original
    pages = data(
        history()[C.ZERO].model_copy(update={S.PAGE_COUNT: C.INTEGRATION_PAGE_COUNT}),
        history()[C.ONE],
        book,
    )
    assert recommendation_key(pages, analysis(pages)) != original
    monkeypatch.setattr(S, S.REC2_TEST_VERSION_KEY, S.REC_TEST_PREVIOUS_ANALYSIS_VERSION)
    assert recommendation_key(pinned, analysis(pinned)) != original


def test_evaluation_missing_features_use_same_cohort_mean_fallback_not_negative_evidence() -> None:
    books = tuple(
        book.model_copy(
            update={S.PAGE_COUNT: C.NONE, S.REC_ORIGINAL_YEAR: C.NONE, S.REC_FEATURES: {}}
        )
        for book in evaluation_history()
    )
    result = evaluate_recommendations(books, _features)
    assert result.status == S.REC2_AVAILABLE
    assert result.cohort_size == len(books)
    assert result.current_mean_fallbacks == len(books)
    assert result.shadow_mean_fallbacks == len(books)
    assert result.simple_mean_fallbacks == len(books)
    assert result.current_fallback_rate == C.ONE
    assert result.mean_mae == result.current_heuristic_mae
    assert result.mean_mae == result.shadow_candidate_mae
    assert result.mean_mae == result.simple_length_mae
    assert not result.shadow_beats_comparators


def test_large_single_coauthor_component_still_has_no_heldout_evaluation() -> None:
    books = tuple(
        book.model_copy(update={S.AUTHORS: (S.REC_TEST_AUTHOR,)}) for book in evaluation_history()
    )
    result = evaluate_recommendations(books, _features)
    assert result.status == S.REC2_UNAVAILABLE
    assert result.independent_components == C.ONE
    assert not result.folds
    assert result.mean_mae is C.NONE
