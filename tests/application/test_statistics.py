from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from math import comb

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.statistics import (
    _author_components,
    _author_folds,
    _completion_date,
    _labels,
    _paired_stability,
    _predict_held_out,
    build_reading_profile,
    build_taste,
    build_watchlist,
)
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisComponent,
    AnalysisEvidence,
    AnalysisInput,
    AnalysisManifest,
    AnalysisSnapshot,
    AnalyticsSettings,
    Finding,
)
from bookystats.domain.categories import analytical_categories
from bookystats.domain.models import (
    FieldState,
    Observation,
    PartialDate,
    ReadingEvent,
    ReadingStatus,
    Source,
    SupplementalCompletionDate,
    SyncState,
)


def _book(
    work_id: int,
    rating: float | None = C.NONE,
    *,
    genre: str | None = C.NONE,
    author: str | None = C.NONE,
    status: ReadingStatus = ReadingStatus.READ,
    pages: int | None = C.NONE,
    events: tuple[ReadingEvent, ...] = (),
    providers: dict[str, float] | None = C.NONE,
    review: str | None = C.NONE,
) -> AnalysisBook:
    return AnalysisBook(
        work_id=work_id,
        source_ids=(str(work_id),),
        title=S.AN_CALC_TEST_AUTHOR_FORMAT.format(index=work_id),
        authors=(author or S.AN_CALC_TEST_AUTHOR_FORMAT.format(index=work_id),),
        status=status,
        rating=rating,
        features={S.GENRES: (genre,)} if genre is not C.NONE else {},
        page_count=pages,
        reading_events=events,
        community_ratings=providers or {},
        review=review,
    )


def _data(*books: AnalysisBook) -> AnalysisInput:
    return AnalysisInput(
        books=books,
        personal_rating_records=C.TEN,
        manifest=AnalysisManifest(
            account_fingerprint=S.AN_CALC_TEST_ACCOUNT,
            settings_hash=S.AN_CALC_TEST_HASH,
            snapshots=(
                AnalysisSnapshot(
                    source=Source.GOODREADS,
                    account_id=S.AN_CALC_TEST_ACCOUNT,
                    collection=S.READ,
                    snapshot_id=C.ONE,
                    input_kind=S.INPUT_FILE,
                    finished_at=S.AN_CALC_TEST_FINISH,
                    records=len(books),
                    attempt_state=SyncState.COMPLETE,
                ),
            ),
        ),
    )


def _taste(data: AnalysisInput, settings: AnalyticsSettings | None = C.NONE) -> AnalysisComponent:
    return build_taste(data, settings or AnalyticsSettings(), key=S.AN_CALC_TEST_KEY)


def _finding(component: AnalysisComponent, metric: str) -> Finding:
    return next(finding for finding in component.findings if finding.metric_id == metric)


def _summary(component: AnalysisComponent, metric: str) -> dict[str, object]:
    value = _finding(component, metric).value
    assert isinstance(value, dict)
    return dict(value)


def _group(component: AnalysisComponent, feature: str, label: str) -> Finding:
    return _finding(component, S.AN_CALC_GROUP.format(feature=feature, label=label))


def _supplemental(
    value: str | None,
    *,
    source_id: str = S.TEST_IMPORT_SECOND_ID,
    state: FieldState = FieldState.PRESENT,
) -> SupplementalCompletionDate:
    return SupplementalCompletionDate(
        source_id=source_id,
        finished=PartialDate(value=value) if value is not C.NONE else C.NONE,
        observation=Observation(
            field=S.DTX_SUPPLEMENTAL_COMPLETION_DATE,
            value=value,
            state=state,
            scope=S.READER,
            source_url=S.CONTENT_ANALYSIS_TEST_FILE_URL,
            observed_at=S.AN_CALC_TEST_FINISH,
        ),
    )


def test_supplemental_completion_cohorts_preserve_goodreads_precedence_and_unknowns() -> None:
    actual = _book(
        C.ONE,
        C.FOUR,
        events=(
            ReadingEvent(
                finished=PartialDate(value=S.AN_CALC_TEST_YEAR),
                status=ReadingStatus.READ,
            ),
        ),
    ).model_copy(
        update={S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (_supplemental(S.ANX_TEST_EARLIER_DATE),)}
    )
    fallback = _book(C.TWO).model_copy(
        update={S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (_supplemental(S.ANX_TEST_EARLIER_DATE),)}
    )
    conflicting = _book(C.THREE).model_copy(
        update={
            S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (
                _supplemental(S.ANX_TEST_EARLIER_DATE),
                _supplemental(S.ANX_TEST_LATER_DATE),
            )
        }
    )
    unavailable = _book(C.FOUR).model_copy(
        update={
            S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (
                _supplemental(C.NONE, state=FieldState.UNAVAILABLE),
            )
        }
    )
    future = _book(C.FIVE).model_copy(
        update={S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (_supplemental(S.ANX_TEST_FUTURE_DATE),)}
    )
    library_only = _book(C.SIX).model_copy(
        update={S.ADDED_AT: PartialDate(value=S.ANX_TEST_EARLIER_DATE)}
    )
    data = _data(actual, fallback, conflicting, unavailable, future, library_only).model_copy(
        update={S.CONTENT_ANALYSIS_AS_OF: S.ANX_TEST_AS_OF}
    )
    finding = _finding(_taste(data), S.ANX_COMPLETION_COHORTS)
    summary = _summary(_taste(data), S.ANX_COMPLETION_COHORTS)
    assert finding.sample_size == C.TWO
    assert finding.missing_count == C.FOUR
    assert summary[S.ANX_CONFLICTING_DATES] == [conflicting.book_id]
    assert summary[S.ANX_FUTURE_DATES] == C.ONE
    selected = summary[S.ANX_SELECTED_DATES]
    assert selected[actual.book_id][S.VALUE] == S.AN_CALC_TEST_YEAR
    assert selected[actual.book_id][S.ANX_DATE_ORIGIN] == S.ANX_AUTHORITATIVE_DATE
    assert selected[fallback.book_id][S.ANX_DATE_ORIGIN] == S.ANX_SUPPLEMENTAL_DATE
    assert selected[fallback.book_id][S.AN_CALC_EVIDENCE][C.ZERO][S.SOURCE_ID] == (
        S.TEST_IMPORT_SECOND_ID
    )
    assert summary[S.ANX_SUPPLEMENTAL_STATES][FieldState.UNAVAILABLE.value] == C.ONE
    assert summary[S.ANX_COHORTS][S.AN_CALC_TEST_YEAR][S.ANX_CURRENT_RATINGS] is C.NONE
    assert actual.reading_events[C.ZERO].finished is not C.NONE
    assert fallback.reading_events == ()


def test_duplicate_supplemental_values_are_consistent_not_multiple_reading_events() -> None:
    book = _book(C.ONE).model_copy(
        update={
            S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (
                _supplemental(S.ANX_TEST_EARLIER_DATE),
                _supplemental(
                    S.ANX_TEST_EARLIER_DATE,
                    source_id=S.TEST_IMPORT_THIRD_ID,
                ),
            )
        }
    )
    finished, origin, conflict = _completion_date(book)
    assert finished is not C.NONE and finished.value == S.ANX_TEST_EARLIER_DATE
    assert origin == S.ANX_SUPPLEMENTAL_DATE
    assert not conflict
    assert book.reading_events == ()


def test_library_addition_profile_keeps_partial_dates_and_day_only_ages_separate() -> None:
    values = (
        S.AN_CALC_TEST_FINISH,
        S.AN_CALC_TEST_MONTH,
        S.AN_CALC_TEST_YEAR,
        S.ANX_TEST_FUTURE_DATE,
    )
    books = tuple(
        _book(index).model_copy(update={S.ADDED_AT: PartialDate(value=value)})
        for index, value in enumerate(values, start=C.ONE)
    )
    data = _data(*books).model_copy(update={S.CONTENT_ANALYSIS_AS_OF: S.ANX_TEST_AS_OF})
    component = build_reading_profile(data, AnalyticsSettings(), key=S.AN_CALC_TEST_KEY)
    finding = _finding(component, S.ANX_LIBRARY_ADDITIONS.format(collection=S.READ))
    summary = _summary(component, S.ANX_LIBRARY_ADDITIONS.format(collection=S.READ))
    assert finding.sample_size == C.THREE
    assert finding.missing_count == C.ONE
    assert summary[S.ANX_DATE_PRECISIONS] == {S.DAY: C.ONE, S.MONTH: C.ONE, S.YEAR: C.ONE}
    assert summary[S.ANX_AGE_SUMMARY][S.AN_CALC_N] == C.ONE
    assert summary[S.ANX_COHORTS] == {S.AN_CALC_TEST_YEAR: C.THREE}
    assert summary[S.ANX_FUTURE_DATES] == C.ONE
    assert S.ANX_ADDITION_NOTE in finding.limitations


def test_catalog_holdout_uses_only_positive_feature_training_after_work_exclusion() -> None:
    settings = AnalyticsSettings(min_group_size=C.THREE)
    training = tuple(
        _book(index, C.FOUR).model_copy(
            update={S.ANX_FEATURES: {S.ANX_FEATURE: (S.AN_CONNECTION,)}}
        )
        for index in range(C.ONE, C.FOUR)
    )
    held_out = _book(C.FOUR, C.ONE).model_copy(
        update={S.ANX_FEATURES: {S.ANX_FEATURE: (S.AN_CONNECTION,)}}
    )
    prediction = _predict_held_out(
        held_out, (*training, held_out), settings, features=C.ANX_VALIDATION_FEATURES
    )
    altered = held_out.model_copy(update={S.RATING: C.FIVE})
    assert prediction == _predict_held_out(
        altered, (*training, altered), settings, features=C.ANX_VALIDATION_FEATURES
    )
    assert prediction[C.TWO] == {S.ANX_FEATURE: C.FOUR}
    unsupported = _predict_held_out(
        held_out, (*training[: C.TWO], held_out), settings, features=C.ANX_VALIDATION_FEATURES
    )
    assert unsupported[C.ZERO] == unsupported[C.ONE]
    assert unsupported[C.TWO] == {}


@pytest.mark.parametrize(S.ANALYTIC_CATEGORY_TEST_PARAMETERS, C.ANALYTIC_CATEGORY_TEST_CASES)
def test_genre_families_require_exact_curated_aliases(
    labels: tuple[str, ...], expected: tuple[str, ...]
) -> None:
    book = _book(C.ONE).model_copy(update={S.AN_CALC_TEST_FEATURES_FIELD: {S.GENRES: labels}})
    assert _labels(book, S.GENRES) == expected


def test_unmapped_catalog_subjects_are_not_genre_complement_examples() -> None:
    known = _book(C.ONE, C.FIVE, genre=S.ANALYTIC_CATEGORY_FANTASY)
    other = _book(C.TWO, C.ONE, genre=S.ANALYTIC_CATEGORY_HISTORY)
    unmapped = _book(C.THREE, C.FIVE, genre=S.ANALYTIC_CATEGORY_TEST_BESTSELLER)
    component = _taste(_data(known, other, unmapped))
    finding = _group(component, S.GENRES, S.ANALYTIC_CATEGORY_FANTASY)
    assert isinstance(finding.value, dict)
    complement = finding.value[S.AN_CALC_COMPLEMENT]
    assert isinstance(complement, dict)
    assert complement[S.AN_CALC_COMPLEMENT_BOOKS] == [other.book_id]
    breadth = _finding(component, S.AN_CALC_BREADTH.format(feature=S.GENRES))
    assert breadth.missing_count == C.ONE


def test_missing_ratings_and_genres_remain_unknown_with_true_denominators() -> None:
    known = _book(C.ONE, C.FOUR)
    missing = _book(C.TWO)
    component = _taste(_data(known, missing))
    summary = _summary(component, S.AN_CALC_RATINGS)
    assert summary[S.AN_CALC_MEAN] == C.FOUR
    assert summary[S.AN_CALC_RATED] == C.ONE
    assert summary[S.AN_CALC_RATING_MISSING] == C.ONE
    assert summary[S.AN_CALC_COVERAGE] == C.ONE / C.TWO
    assert _finding(component, S.AN_CALC_RATING_RECORDS).value == C.TEN
    assert _finding(component, S.AN_CALC_READ_COUNT).value == C.TWO
    rating_finding = _finding(component, S.AN_CALC_RATINGS)
    assert rating_finding.supporting_books == (known.book_id,)
    assert rating_finding.source_snapshot_ids == (C.ONE,)
    breadth = _finding(component, S.AN_CALC_BREADTH.format(feature=S.GENRES))
    assert breadth.missing_count == C.TWO
    assert _summary(component, breadth.metric_id)[S.AN_CALC_HHI] is C.NONE
    empty = _summary(_taste(_data(missing)), S.AN_CALC_RATINGS)
    assert empty[S.AN_CALC_MEAN] is C.NONE
    assert empty[S.AN_CALC_HIGH_SHARE] is C.NONE


def test_thin_sample_is_shrunk_and_not_a_supported_preference() -> None:
    component = _taste(
        _data(
            _book(C.ONE, C.FIVE, genre=S.AN_CALC_TEST_GENRE),
            _book(C.TWO, C.ONE, genre=S.AN_CALC_TEST_OTHER),
        )
    )
    group = _group(component, S.GENRES, S.AN_CALC_TEST_GENRE)
    assert isinstance(group.value, dict)
    assert group.value[S.AN_CALC_MEAN] == C.FIVE
    expected = (C.FIVE + C.FIVE * C.THREE) / C.SIX
    assert group.value[S.AN_CALC_ADJUSTED] == pytest.approx(expected)
    assert group.reliability == S.AN_CALC_WEAK
    assert S.AN_CALC_SINGLE in group.limitations
    assert (
        S.AN_CALC_PREFERENCE_KEY.format(feature=S.GENRES, label=S.AN_CALC_TEST_GENRE)
        not in component.preferences
    )


def test_author_concentration_weakens_genre_but_supports_author_consistency() -> None:
    component = _taste(
        _data(
            *(
                _book(
                    index,
                    C.FOUR,
                    genre=S.AN_CALC_TEST_GENRE,
                    author=S.AN_CALC_TEST_AUTHOR,
                )
                for index in range(C.ONE, C.SIX)
            )
        )
    )
    genre = _group(component, S.GENRES, S.AN_CALC_TEST_GENRE)
    assert genre.reliability == S.AN_CALC_WEAK
    assert genre.uncertainty[S.AN_CALC_AUTHOR_SHARE] == C.ONE
    author = _group(component, S.AUTHORS, S.AN_CALC_TEST_AUTHOR)
    assert author.reliability == S.AN_CALC_EXPLORATORY
    assert isinstance(author.value, dict)
    assert author.value[S.AN_CALC_STDEV] == C.ZERO


def test_supported_diverse_group_reports_leave_one_author_out_and_conditionals() -> None:
    component = _taste(
        _data(
            *(
                _book(
                    index,
                    C.FOUR,
                    genre=S.AN_CALC_TEST_GENRE,
                    pages=C.AN_CALC_LONG_LIMIT,
                )
                for index in range(C.ONE, C.SEVEN)
            )
        )
    )
    group = _group(component, S.GENRES, S.AN_CALC_TEST_GENRE)
    assert group.reliability == S.AN_CALC_EXPLORATORY
    stability = group.uncertainty[S.AN_CALC_LEAVE_AUTHOR]
    assert isinstance(stability, dict)
    assert len(stability) == C.SIX
    assert all(value == C.FOUR for value in stability.values())
    conditional = _finding(
        component,
        S.AN_CALC_CONDITIONAL.format(genre=S.AN_CALC_TEST_GENRE, length=S.AN_CALC_LONG),
    )
    assert conditional.sample_size == C.SIX
    assert conditional.uncertainty[S.AN_CALC_GENRE_BASELINE] == C.FOUR
    assert conditional.uncertainty[S.AN_CALC_LENGTH_BASELINE] == C.FOUR


def test_duplicate_works_do_not_weight_ratings_and_conflicts_are_unknown() -> None:
    book = _book(C.ONE, C.FIVE)
    component = _taste(_data(book, book, _book(C.TWO, C.ONE)))
    assert _finding(component, S.AN_CALC_READ_COUNT).value == C.TWO
    assert _summary(component, S.AN_CALC_RATINGS)[S.AN_CALC_MEAN] == C.THREE
    conflict = _taste(_data(book, _book(C.ONE, C.ONE)))
    assert _summary(conflict, S.AN_CALC_RATINGS)[S.AN_CALC_MEAN] is C.NONE


def test_year_precision_is_not_month_or_duration_and_duplicate_events_count_once() -> None:
    year_event = ReadingEvent(
        started=PartialDate(value=S.AN_CALC_TEST_YEAR),
        finished=PartialDate(value=S.AN_CALC_TEST_YEAR),
        status=ReadingStatus.READ,
    )
    day_event = ReadingEvent(
        started=PartialDate(value=S.AN_CALC_TEST_START),
        finished=PartialDate(value=S.AN_CALC_TEST_FINISH),
        status=ReadingStatus.READ,
    )
    year = _book(C.ONE, C.FOUR, events=(year_event,))
    exact = _book(C.TWO, C.TWO, events=(day_event, day_event))
    component = _taste(_data(year, exact))
    year_metric = S.AN_CALC_PERIOD.format(precision=S.YEAR, period=S.AN_CALC_TEST_YEAR)
    month_metric = S.AN_CALC_PERIOD.format(precision=S.MONTH, period=S.AN_CALC_TEST_MONTH)
    assert _finding(component, year_metric).sample_size == C.TWO
    assert _finding(component, month_metric).supporting_books == (exact.book_id,)
    assert _finding(component, month_metric).missing_count == C.ONE
    durations = _finding(component, S.AN_CALC_DURATION)
    assert durations.sample_size == C.ONE
    assert durations.missing_count == C.ONE
    assert isinstance(durations.value, dict)
    assert durations.value[S.AN_CALC_MEAN] == C.AN_CALC_TEST_DAYS
    assert durations.value[S.AN_CALC_EVENT_COUNT] == C.ONE
    assert (
        next(
            capability
            for capability in component.capabilities
            if capability.metric_id == S.AN_CALC_REVISIONS
        ).state
        == C.AnalyticsCapability.UNSUPPORTED
    )


def test_dnf_is_separate_from_low_rating_and_absence_is_not_zero() -> None:
    read = _book(C.ONE, C.ONE)
    dnf = _book(C.TWO, status=ReadingStatus.DNF)
    component = _taste(_data(read, dnf))
    assert _finding(component, S.AN_CALC_READ_COUNT).value == C.ONE
    explicit = _finding(component, S.AN_CALC_DNF)
    assert explicit.supporting_books == (dnf.book_id,)
    assert isinstance(explicit.value, dict)
    assert explicit.value[S.AN_CALC_N] == C.ONE
    unknown = _summary(_taste(_data(read)), S.AN_CALC_DNF)
    assert unknown[S.AN_CALC_N] is C.NONE


def test_community_comparison_keeps_providers_and_unknowns_separate() -> None:
    paired = _book(
        C.ONE,
        C.FOUR,
        providers={S.GOOGLE_BOOKS: C.THREE, S.OPEN_LIBRARY: C.FIVE},
    )
    unpaired = _book(C.TWO, providers={S.GOOGLE_BOOKS: C.ONE})
    component = _taste(_data(paired, unpaired))
    google = _summary(component, S.AN_CALC_PROVIDER.format(provider=S.GOOGLE_BOOKS))
    library = _summary(component, S.AN_CALC_PROVIDER.format(provider=S.OPEN_LIBRARY))
    assert google[S.AN_CALC_DELTA] == C.ONE
    assert library[S.AN_CALC_DELTA] == -C.ONE
    assert (
        _finding(component, S.AN_CALC_PROVIDER.format(provider=S.GOOGLE_BOOKS)).missing_count
        == C.ONE
    )


def test_goodreads_comparison_keeps_storygraph_personal_rating_unchanged() -> None:
    component = _taste(_data(_book(C.ONE, C.FOUR, providers={S.GOODREADS: C.ONE})))
    comparison = _summary(component, S.AN_CALC_PROVIDER.format(provider=S.GOODREADS))
    assert comparison[S.AN_CALC_MEAN] == C.FOUR
    assert comparison[S.AN_CALC_PROVIDER_MEAN] == C.ONE


def test_catalog_category_paths_are_exact_not_genre_guesses() -> None:
    assert analytical_categories((S.ENR_CATEGORY_TEST_PATH,)) == (S.ANALYTIC_CATEGORY_FANTASY,)
    assert not analytical_categories((S.ENR_CATEGORY_TEST_FALSE_PATH,))


def test_appetite_uses_only_explicit_labels_and_independent_declarations() -> None:
    settings = AnalyticsSettings(
        declared_preferences={dimension: C.ONE for dimension in C.ANALYTICS_DIMENSIONS}
    )
    component = _taste(_data(_book(C.ONE, C.FIVE, genre=S.AN_CALC_TEST_GENRE)), settings)
    for dimension in C.ANALYTICS_DIMENSIONS:
        summary = _summary(component, S.AN_CALC_APPETITE.format(dimension=dimension))
        assert summary[S.AN_CALC_DECLARED] == C.ONE
        assert summary[S.AN_CALC_EXPOSURE] is C.NONE
        assert summary[S.AN_CALC_ENJOYMENT] is C.NONE
        exposure = next(
            capability
            for capability in component.capabilities
            if capability.metric_id == S.AN_CALC_APP_EXPOSURE.format(dimension=dimension)
        )
        assert exposure.state == C.AnalyticsCapability.NEEDS_ENRICHMENT
    assert not any(key.startswith(S.AN_CALC_APPETITE_LABELS) for key in component.preferences)


def test_review_mentions_preserve_exact_negative_context_and_evidence() -> None:
    book = _book(C.ONE, C.ONE, review=S.AN_CALC_TEST_REVIEW)
    evidence = AnalysisEvidence(
        source=S.GOODREADS,
        source_id=book.source_ids[C.ZERO],
        observation=Observation(
            field=S.REVIEW,
            value=S.AN_CALC_TEST_REVIEW,
            state=FieldState.PRESENT,
            source_url=S.GOODREADS,
            observed_at=S.AN_CALC_TEST_FINISH,
        ),
    )
    book = book.model_copy(update={S.AN_CALC_EVIDENCE_FIELD: (evidence,)})
    component = _taste(_data(book))
    pacing = _summary(component, S.AN_CALC_REVIEW.format(theme=S.AN_CALC_THEME_PACING))
    excerpts = pacing[S.AN_CALC_EXCERPT]
    assert isinstance(excerpts, list)
    assert excerpts[C.ZERO][S.AN_CALC_EXCERPT] == S.AN_CALC_TEST_REVIEW
    assert excerpts[C.ZERO][S.AN_CALC_EVIDENCE]
    assert not component.preferences


def test_watchlist_change_does_not_change_taste_and_never_ranks_books() -> None:
    read = tuple(
        _book(index, C.FOUR, genre=S.AN_CALC_TEST_GENRE) for index in range(C.ONE, C.SEVEN)
    )
    watch = _book(C.SEVEN, genre=S.AN_CALC_TEST_OTHER, status=ReadingStatus.TO_READ)
    original = _data(*read)
    changed = original.model_copy(update={S.BOOKS: (*read, watch)})
    before = _taste(original)
    after = _taste(changed)
    assert before == after
    result = build_watchlist(changed, AnalyticsSettings(), after, key=S.AN_CALC_TEST_KEY)
    assert _finding(result, S.AN_CALC_WATCH_COUNT).value == C.ONE
    assert not result.preferences
    summary = _summary(result, S.AN_CALC_WATCH_FEATURE.format(feature=S.GENRES))
    assert S.AN_CALC_TEST_OTHER in summary[S.AN_CALC_UNSUPPORTED_LABELS]
    labels = summary[S.AN_CALC_LABELS]
    assert isinstance(labels, dict)
    assert labels[S.AN_CALC_TEST_OTHER][S.AN_CALC_PREFERENCE_DELTA] is C.NONE
    assert (
        next(
            capability
            for capability in result.capabilities
            if capability.metric_id == S.AN_CALC_WATCH_AGE
        ).state
        == C.AnalyticsCapability.UNSUPPORTED
    )


def test_empty_input_has_explicit_capability_gates_not_fabricated_findings() -> None:
    component = _taste(_data())
    assert _summary(component, S.AN_CALC_RATINGS)[S.AN_CALC_MEAN] is C.NONE
    assert not component.preferences
    capabilities = {capability.metric_id: capability for capability in component.capabilities}
    assert capabilities[S.AN_CALC_REVIEWS].state == C.AnalyticsCapability.UNSUPPORTED
    assert capabilities[S.AN_CALC_TIME].state == C.AnalyticsCapability.NEEDS_OBSERVATIONS
    assert capabilities[S.AN_CALC_COMMUNITY].state == C.AnalyticsCapability.NEEDS_ENRICHMENT
    assert all(metric in capabilities for metric, _reason in C.AN_CALC_UNSUPPORTED_TOPICS)


def test_watchlist_age_preserves_partial_precision_and_uses_explicit_as_of() -> None:
    exact = _book(C.ONE, status=ReadingStatus.TO_READ).model_copy(
        update={S.AN_CALC_TEST_ADDED_FIELD: PartialDate(value=S.AN_CALC_TEST_START)}
    )
    year = _book(C.TWO, status=ReadingStatus.TO_READ).model_copy(
        update={S.AN_CALC_TEST_ADDED_FIELD: PartialDate(value=S.AN_CALC_TEST_YEAR)}
    )
    snapshot = AnalysisSnapshot(
        source=Source.GOODREADS,
        account_id=S.AN_CALC_TEST_ACCOUNT,
        collection=S.TO_READ,
        snapshot_id=C.TWO,
        input_kind=S.INPUT_FILE,
        finished_at=S.AN_CALC_TEST_FINISH_LATER,
        records=C.TWO,
        attempt_state=SyncState.COMPLETE,
    )
    data = _data(exact, year)
    manifest = data.manifest.model_copy(update={S.AN_CALC_TEST_SNAPSHOTS_FIELD: (snapshot,)})
    data = data.model_copy(
        update={
            S.AN_CALC_TEST_MANIFEST_FIELD: manifest,
            S.AN_CALC_AS_OF_FIELD: S.AN_CALC_TEST_FINISH_LATER,
        }
    )
    component = build_watchlist(data, AnalyticsSettings(), _taste(data), key=S.AN_CALC_TEST_KEY)
    age = _summary(component, S.AN_CALC_WATCH_AGE)
    entries = age[S.AN_CALC_LABELS]
    assert isinstance(entries, dict)
    assert entries[exact.book_id][S.AN_CALC_AGE_DAYS] == C.AN_CALC_TEST_AGE_DAYS
    assert entries[year.book_id][S.AN_CALC_AGE_DAYS] is C.NONE
    assert entries[year.book_id][S.AN_CALC_PRECISION] == S.YEAR
    assert entries[year.book_id][S.AN_CALC_ADDED] == S.AN_CALC_TEST_YEAR


def test_explicit_appetite_labels_support_exposure_without_heuristics() -> None:
    book = _book(C.ONE, C.FOUR).model_copy(
        update={S.AN_CALC_TEST_FEATURES_FIELD: {S.AN_APPETITE: (S.AN_WONDER, S.AN_CONNECTION)}}
    )
    component = _taste(_data(book))
    for dimension in C.ANALYTICS_DIMENSIONS:
        summary = _summary(component, S.AN_CALC_APPETITE.format(dimension=dimension))
        if dimension in book.features[S.AN_APPETITE]:
            assert summary[S.AN_CALC_EXPOSURE] == C.ONE
            enjoyment = summary[S.AN_CALC_ENJOYMENT]
            assert isinstance(enjoyment, dict)
            assert enjoyment[S.AN_CALC_MEAN] == C.FOUR
        else:
            assert summary[S.AN_CALC_EXPOSURE] is C.NONE


def test_multilabel_breadth_uses_fractional_work_membership() -> None:
    book = _book(C.ONE, C.FOUR).model_copy(
        update={
            S.AN_CALC_TEST_FEATURES_FIELD: {S.GENRES: (S.AN_CALC_TEST_GENRE, S.AN_CALC_TEST_OTHER)}
        }
    )
    component = _taste(_data(book, _book(C.TWO)))
    breadth = _summary(component, S.AN_CALC_BREADTH.format(feature=S.GENRES))
    assert breadth[S.AN_CALC_HHI] == C.ONE / C.TWO
    assert breadth[S.AN_CALC_EFFECTIVE] == C.TWO
    assert _group(component, S.GENRES, S.AN_CALC_TEST_GENRE).missing_count == C.ONE


def test_unknown_provider_scale_does_not_create_paired_comparison() -> None:
    book = _book(C.ONE, C.FOUR, providers={S.AN_CALC_TEST_OTHER: C.FIVE})
    component = _taste(_data(book))
    metric = S.AN_CALC_PROVIDER.format(provider=S.AN_CALC_TEST_OTHER)
    assert not any(finding.metric_id == metric for finding in component.findings)
    assert (
        next(
            capability for capability in component.capabilities if capability.metric_id == metric
        ).state
        == C.AnalyticsCapability.NEEDS_ENRICHMENT
    )


def _historical_book(index: int, rating: float, genre: str, finished: str) -> AnalysisBook:
    event = ReadingEvent(
        finished=PartialDate(value=finished),
        status=ReadingStatus.READ,
    )
    return _book(index, rating, genre=genre, events=(event, event))


def _historical_data(*books: AnalysisBook) -> AnalysisInput:
    return _data(*books).model_copy(update={S.AN_CALC_AS_OF_FIELD: S.AN_CALC_TEST_AS_OF})


def test_feature_complement_excludes_unknown_labels_and_reports_shrunk_effect() -> None:
    group = _book(C.ONE, C.FIVE, genre=S.AN_CALC_TEST_GENRE)
    complement = _book(C.TWO, C.ONE, genre=S.AN_CALC_TEST_OTHER)
    unknown = _book(C.THREE, C.FIVE)
    component = _taste(_data(group, complement, unknown))
    finding = _group(component, S.GENRES, S.AN_CALC_TEST_GENRE)
    assert isinstance(finding.value, dict)
    comparison = finding.value[S.AN_CALC_COMPLEMENT]
    assert isinstance(comparison, dict)
    assert comparison[S.AN_CALC_N] == C.ONE
    assert comparison[S.AN_CALC_RATED] == C.ONE
    assert comparison[S.AN_CALC_MEAN] == C.ONE
    assert comparison[S.AN_CALC_HIGH_SHARE] == C.ZERO
    assert comparison[S.AN_CALC_COMPLEMENT_BOOKS] == [complement.book_id]
    assert finding.value[S.AN_CALC_SHRUNK_EFFECT] == pytest.approx(C.FOUR / C.SIX)
    assert finding.value[S.AN_CALC_HIGH_LIFT] is C.NONE
    assert finding.value[S.AN_CALC_HIGH_DIFFERENCE] == C.ONE
    assert S.AN_CALC_COMPARISON_NOTE in finding.limitations


def test_held_out_prediction_never_uses_held_out_rating_even_when_passed_in_training() -> None:
    held = _book(C.ONE, C.FIVE, genre=S.AN_CALC_TEST_GENRE)
    training = tuple(
        _book(
            index,
            C.ONE if index <= C.SIX else C.FIVE,
            genre=S.AN_CALC_TEST_GENRE if index <= C.SIX else S.AN_CALC_TEST_OTHER,
        )
        for index in range(C.TWO, C.TEN + C.TWO)
    )
    prediction, baseline, dimensions = _predict_held_out(
        held, (held, *training), AnalyticsSettings()
    )
    assert baseline == C.THREE
    assert prediction == C.TWO
    assert dimensions[S.GENRES] == C.TWO
    changed = held.model_copy(update={S.RATING: C.ONE})
    assert _predict_held_out(changed, (held, *training), AnalyticsSettings()) == (
        prediction,
        baseline,
        dimensions,
    )


def test_holdout_support_gate_applies_after_exclusion_and_falls_back_to_training_mean() -> None:
    held = _book(C.ONE, C.FIVE, genre=S.AN_CALC_TEST_GENRE)
    books = tuple(
        _book(
            index,
            C.ONE if index <= C.FIVE else C.FIVE,
            genre=S.AN_CALC_TEST_GENRE if index <= C.FIVE else S.AN_CALC_TEST_OTHER,
        )
        for index in range(C.TWO, C.TEN + C.ONE)
    )
    prediction, baseline, dimensions = _predict_held_out(held, (held, *books), AnalyticsSettings())
    assert prediction == baseline
    assert baseline == pytest.approx((C.FOUR + C.FIVE * C.FIVE) / C.NINE)
    assert not dimensions


def test_prediction_averages_tags_within_dimensions_before_combining_dimensions() -> None:
    training: list[AnalysisBook] = []
    for index in range(C.ONE, C.TEN + C.ONE):
        book = _book(
            index,
            C.ONE if index <= C.FIVE else C.FIVE,
            genre=S.AN_CALC_TEST_GENRE if index <= C.FIVE else S.AN_CALC_TEST_OTHER,
        )
        if index <= C.FIVE:
            book = book.model_copy(
                update={
                    S.AN_CALC_TEST_FEATURES_FIELD: {
                        **book.features,
                        S.LANGUAGE: (S.AN_CALC_TEST_LANGUAGE,),
                    }
                }
            )
        training.append(book)
    held = _book(C.TEN + C.ONE, C.FIVE).model_copy(
        update={
            S.AN_CALC_TEST_FEATURES_FIELD: {
                S.GENRES: (S.AN_CALC_TEST_GENRE, S.AN_CALC_TEST_OTHER),
                S.LANGUAGE: (S.AN_CALC_TEST_LANGUAGE,),
            }
        }
    )
    prediction, baseline, dimensions = _predict_held_out(held, tuple(training), AnalyticsSettings())
    assert baseline == C.THREE
    assert dimensions[S.GENRES] == C.THREE
    assert dimensions[S.LANGUAGE] == C.TWO
    assert prediction == C.FIVE / C.TWO


def test_retrospective_validation_reports_real_improvement_and_same_work_baseline() -> None:
    books = tuple(
        _book(
            index,
            C.ONE if index <= C.AN_CALC_VALIDATION_MIN // C.TWO else C.FIVE,
            genre=(
                S.AN_CALC_TEST_GENRE
                if index <= C.AN_CALC_VALIDATION_MIN // C.TWO
                else S.AN_CALC_TEST_OTHER
            ),
        )
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN + C.ONE)
    )
    component = _taste(_data(*books))
    summary = _summary(component, S.AN_CALC_VALIDATION)
    assert summary[S.AN_CALC_N] == C.AN_CALC_VALIDATION_MIN
    assert summary[S.AN_CALC_SIGNAL] == C.AN_CALC_VALIDATION_MIN
    assert summary[S.AN_CALC_FALLBACK] == C.ZERO
    assert summary[S.AN_CALC_ADVANTAGE] is C.TRUE
    assert summary[S.AN_CALC_MAE_GAIN] > C.ZERO
    assert summary[S.AN_CALC_RMSE_GAIN] > C.ZERO
    assert _finding(component, S.AN_CALC_VALIDATION).supporting_books == tuple(
        book.book_id for book in books
    )


def test_validation_without_supported_features_matches_baseline_and_small_data_is_gated() -> None:
    books = tuple(
        _book(index, C.ONE if index % C.TWO else C.FIVE)
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN + C.ONE)
    )
    summary = _summary(_taste(_data(*books)), S.AN_CALC_VALIDATION)
    assert summary[S.AN_CALC_SIGNAL] == C.ZERO
    assert summary[S.AN_CALC_FALLBACK] == C.AN_CALC_VALIDATION_MIN
    assert summary[S.AN_CALC_MAE_GAIN] == C.ZERO
    assert summary[S.AN_CALC_ADVANTAGE] is C.FALSE
    small = _taste(_data(*books[: C.FIVE]))
    assert not any(finding.metric_id == S.AN_CALC_VALIDATION for finding in small.findings)
    assert (
        next(
            capability
            for capability in small.capabilities
            if capability.metric_id == S.AN_CALC_VALIDATION
        ).state
        == C.AnalyticsCapability.NEEDS_OBSERVATIONS
    )


def test_author_folds_keep_normalized_transitive_coauthors_together() -> None:
    books = (
        _book(C.ONE, C.ONE, author=S.AV_TEST_AUTHOR_A),
        _book(C.TWO, C.FIVE).model_copy(
            update={
                S.AV_TEST_AUTHORS_FIELD: (
                    S.AV_TEST_AUTHOR_A_NORMALIZED,
                    S.AV_TEST_AUTHOR_B,
                )
            }
        ),
        _book(C.THREE, C.TWO).model_copy(
            update={S.AV_TEST_AUTHORS_FIELD: (S.AV_TEST_BRIDGE, S.AV_TEST_AUTHOR_C)}
        ),
        _book(C.FOUR, C.THREE, author=S.AV_TEST_AUTHOR_C),
        _book(C.FIVE, C.FOUR),
        _book(C.SIX, C.FIVE).model_copy(update={S.AV_TEST_AUTHORS_FIELD: ()}),
    )
    components = _author_components(books)
    assert tuple(tuple(book.work_id for book in group) for group in components) == (
        (C.ONE, C.TWO, C.THREE, C.FOUR),
        (C.FIVE,),
    )
    folds = _author_folds(components)
    assert folds == _author_folds(_author_components(tuple(reversed(books))))
    assert len(folds) == C.TWO
    assert tuple(book.work_id for book in folds[C.ZERO]) == (C.ONE, C.TWO, C.THREE, C.FOUR)


def test_author_blocked_baselines_fit_only_other_folds() -> None:
    books = tuple(
        _book(
            index,
            C.ONE if index <= C.TEN else C.FIVE,
            genre=S.AN_CALC_TEST_GENRE if index <= C.TEN else S.AN_CALC_TEST_OTHER,
            author=S.AN_CALC_TEST_AUTHOR if index <= C.TEN else C.NONE,
        )
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN + C.ONE)
    )
    unknown = _book(C.AN_CALC_VALIDATION_MIN + C.ONE, C.ZERO).model_copy(
        update={S.AV_TEST_AUTHORS_FIELD: ()}
    )
    component = _taste(_data(*books, unknown))
    summary = _summary(component, S.AV_VALIDATION)
    assert summary[S.AN_CALC_N] == len(books)
    assert summary[S.AV_UNKNOWN] == C.ONE
    assert summary[S.AV_COMPONENTS] == C.TEN * C.TWO + C.ONE
    assert summary[S.AV_LARGEST_COMPONENT] == C.TEN
    folds = summary[S.AV_FOLDS]
    assert isinstance(folds, list)
    groups = _author_folds(_author_components(books))
    for fold, held_out in zip(folds, groups, strict=C.TRUE):
        assert isinstance(fold, dict)
        held_ids = {book.work_id for book in held_out}
        training = tuple(book for book in books if book.work_id not in held_ids)
        expected = sum(book.rating or C.ZERO for book in training) / len(training)
        assert fold[S.AV_TRAINING_MEAN] == pytest.approx(expected)
        assert fold[S.AV_TRAINING_WORKS] == len(training)
    assert S.AV_NOTE in _finding(component, S.AV_VALIDATION).limitations


def test_author_blocked_retains_predictor_worse_than_baseline() -> None:
    books = tuple(
        _book(
            index,
            C.ONE
            if (index <= C.AN_CALC_VALIDATION_MIN // C.TWO)
            or (index > C.AN_CALC_VALIDATION_MIN + C.AN_CALC_VALIDATION_MIN // C.TWO)
            else C.FIVE,
            genre=(
                S.AN_CALC_TEST_GENRE
                if (index - C.ONE) % C.AN_CALC_VALIDATION_MIN < C.AN_CALC_VALIDATION_MIN // C.TWO
                else S.AN_CALC_TEST_OTHER
            ),
            author=(
                S.AV_TEST_AUTHOR_A if index <= C.AN_CALC_VALIDATION_MIN else S.AV_TEST_AUTHOR_B
            ),
        )
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN * C.TWO + C.ONE)
    )
    component = _taste(_data(*books))
    summary = _summary(component, S.AV_VALIDATION)
    assert summary[S.AN_CALC_N] == len(books)
    assert summary[S.AN_CALC_SIGNAL] == len(books)
    assert summary[S.AN_CALC_ADVANTAGE] is C.FALSE
    assert summary[S.AN_CALC_MAE_GAIN] == -C.THREE / C.TWO
    assert summary[S.AN_CALC_RMSE_GAIN] == -C.THREE / C.TWO
    stability = _finding(component, S.AV_VALIDATION).uncertainty[S.AV_STABILITY]
    assert isinstance(stability, dict)
    assert stability[S.AV_STATE] == S.AV_STABILITY_SMALL


def test_author_blocked_unknown_authors_and_single_component_are_unavailable() -> None:
    books = tuple(
        _book(index, C.FOUR, author=S.AN_CALC_TEST_AUTHOR)
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN + C.ONE)
    )
    blocked = _summary(_taste(_data(*books)), S.AV_VALIDATION)
    assert blocked[S.AV_STATE] == S.AV_NO_TRAINING
    assert blocked[S.AV_NO_TRAINING_WORKS] == len(books)
    assert blocked[S.AN_CALC_N] == C.ZERO
    assert blocked[S.AN_CALC_BASELINE_ERRORS] is C.NONE
    unknown = _book(C.AN_CALC_VALIDATION_MIN + C.ONE, C.ONE).model_copy(
        update={S.AV_TEST_AUTHORS_FIELD: ()}
    )
    excluded = _summary(_taste(_data(*books, unknown)), S.AV_VALIDATION)
    assert excluded[S.AV_UNKNOWN] == C.ONE
    assert excluded[S.AV_KNOWN] == len(books)
    small = _summary(_taste(_data(*books[: C.FIVE])), S.AV_VALIDATION)
    assert small[S.AV_STATE] == S.AV_SMALL


def test_author_blocked_no_signal_is_baseline_only_not_supported_prediction() -> None:
    books = tuple(
        _book(index, C.ONE if index % C.TWO else C.FIVE)
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN + C.ONE)
    )
    component = _taste(_data(*books))
    summary = _summary(component, S.AV_VALIDATION)
    assert summary[S.AV_STATE] == S.AV_NO_SIGNAL
    assert summary[S.AN_CALC_FALLBACK] == len(books)
    assert summary[S.AN_CALC_SIGNAL] == C.ZERO
    assert summary[S.AN_CALC_MAE_GAIN] == C.ZERO
    assert summary[S.AN_CALC_PREDICTOR_ERRORS] == summary[S.AN_CALC_BASELINE_ERRORS]
    stability = _finding(component, S.AV_VALIDATION).uncertainty[S.AV_STABILITY]
    assert isinstance(stability, dict)
    assert stability[S.AV_STATE] == S.AV_NO_SIGNAL
    assert stability[S.AV_STABILITY_RANGE] is C.NONE


def test_paired_component_resampling_is_deterministic_and_preserves_negative_results() -> None:
    losses = tuple(
        ((C.ONE, C.TWO),) if index % C.TWO else ((C.TWO, C.ONE),) * C.TWO
        for index in range(C.AN_CALC_VALIDATION_MIN)
    )
    result = _paired_stability(losses, has_signal=C.TRUE)
    assert result == _paired_stability(losses, has_signal=C.TRUE)
    assert result[S.AV_DRAWS] == C.AV_BOOTSTRAP_DRAWS
    interval = result[S.AV_STABILITY_RANGE]
    assert isinstance(interval, dict)
    lower = interval[S.AV_LOWER]
    upper = interval[S.AV_UPPER]
    assert isinstance(lower, float)
    assert isinstance(upper, float)
    assert lower < C.ZERO
    assert upper < C.ONE
    unavailable = _paired_stability(losses[: C.TWO], has_signal=C.TRUE)
    assert unavailable[S.AV_STABILITY_RANGE] is C.NONE
    negative = _paired_stability((((C.TWO, C.ONE),),) * C.AN_CALC_VALIDATION_MIN, has_signal=C.TRUE)
    assert negative[S.AV_STABILITY_RANGE] == {
        S.AV_LOWER: -C.ONE,
        S.AV_UPPER: -C.ONE,
    }


def test_author_blocked_whole_report_is_order_and_process_invariant() -> None:
    books = tuple(
        _book(
            index,
            C.ONE if index % C.TWO else C.FIVE,
            genre=S.AN_CALC_TEST_GENRE if index % C.TWO else S.AN_CALC_TEST_OTHER,
        )
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN + C.ONE)
    )
    forward = _finding(_taste(_data(*books)), S.AV_VALIDATION)
    backward = _finding(_taste(_data(*reversed(books))), S.AV_VALIDATION)
    assert forward == backward
    with ProcessPoolExecutor(max_workers=C.ONE) as workers:
        parallel = workers.submit(
            build_taste, _data(*books), AnalyticsSettings(), key=S.AN_CALC_TEST_KEY
        ).result()
    assert _finding(parallel, S.AV_VALIDATION) == forward
    stability = forward.uncertainty[S.AV_STABILITY]
    assert isinstance(stability, dict)
    assert stability[S.AV_STATE] == S.AV_AVAILABLE


def test_yearly_breadth_rarefies_equal_unique_work_volume_and_excludes_partial_dates() -> None:
    books: list[AnalysisBook] = []
    for index in range(C.ONE, C.TEN * C.THREE + C.ONE):
        books.append(
            _historical_book(
                index,
                C.FOUR,
                S.AN_CALC_TEST_OTHER if index > C.TEN * C.TWO else S.AN_CALC_TEST_GENRE,
                S.AN_CALC_TEST_OLD_FINISH if index <= C.TEN else S.AN_CALC_TEST_FINISH,
            )
        )
    books.append(
        _historical_book(C.TEN * C.FOUR, C.FOUR, S.AN_CALC_TEST_OTHER, S.AN_CALC_TEST_EARLY_PARTIAL)
    )
    component = _taste(_historical_data(*books))
    summary = _summary(component, S.AN_CALC_YEAR_BREADTH)
    assert summary[S.AN_CALC_SAMPLE_VOLUME] == C.TEN
    cohorts = summary[S.AN_CALC_COHORTS]
    assert isinstance(cohorts, dict)
    before = cohorts[S.AN_CALC_TEST_OLD_FINISH[: C.FOUR]]
    after = cohorts[S.AN_CALC_TEST_FINISH[: C.FOUR]]
    assert before[S.AN_CALC_EXPECTED_LABELS] == C.ONE
    assert after[S.AN_CALC_EXPECTED_LABELS] == pytest.approx(
        C.TWO - C.TWO / comb(C.TEN * C.TWO, C.TEN)
    )
    assert after[S.AN_CALC_KNOWN] == C.TEN * C.TWO
    assert S.AN_CALC_TEST_EARLY_PARTIAL not in cohorts
    assert _finding(component, S.AN_CALC_YEAR_BREADTH).sample_size == C.TEN * C.THREE


def test_comparable_current_rating_change_removes_genre_mix_shift_without_revision_claims() -> None:
    books: list[AnalysisBook] = []
    for index in range(C.ONE, C.TEN * C.FOUR + C.ONE):
        earlier = index <= C.TEN * C.TWO
        favorite_genre = index <= C.TEN + C.FIVE or (
            C.TEN * C.TWO < index <= C.TEN * C.TWO + C.FIVE
        )
        books.append(
            _historical_book(
                index,
                C.FIVE if favorite_genre else C.ONE,
                S.AN_CALC_TEST_GENRE if favorite_genre else S.AN_CALC_TEST_OTHER,
                S.AN_CALC_TEST_OLD_FINISH if earlier else S.AN_CALC_TEST_FINISH,
            )
        )
    component = _taste(_historical_data(*books))
    summary = _summary(component, S.AN_CALC_TASTE_CHANGE)
    assert summary[S.AN_CALC_RAW_DELTA] == -C.TWO
    assert summary[S.AN_CALC_STANDARDIZED_DELTA] == C.ZERO
    assert summary[S.AN_CALC_STANDARDIZED_HIGH_DELTA] == C.ZERO
    standardized = summary[S.AN_CALC_STANDARDIZED]
    assert isinstance(standardized, dict)
    assert all(value == C.THREE for value in standardized.values())
    finding = _finding(component, S.AN_CALC_TASTE_CHANGE)
    assert finding.sample_size == C.TEN * C.FOUR
    assert finding.reliability == S.AN_CALC_EXPLORATORY
    assert S.AN_CALC_CHANGE_NOTE in finding.limitations
    assert (
        next(
            capability
            for capability in component.capabilities
            if capability.metric_id == S.AN_CALC_REVISIONS
        ).state
        == C.AnalyticsCapability.UNSUPPORTED
    )


def test_comparable_change_requires_shared_supported_strata_not_just_two_years() -> None:
    books = tuple(
        _historical_book(
            index,
            C.FOUR,
            S.AN_CALC_TEST_GENRE,
            S.AN_CALC_TEST_OLD_FINISH if index <= C.TEN else S.AN_CALC_TEST_FINISH,
        )
        for index in range(C.ONE, C.TEN * C.TWO + C.ONE)
    )
    component = _taste(_historical_data(*books))
    assert not any(finding.metric_id == S.AN_CALC_TASTE_CHANGE for finding in component.findings)
    assert (
        next(
            capability
            for capability in component.capabilities
            if capability.metric_id == S.AN_CALC_TASTE_CHANGE
        ).state
        == C.AnalyticsCapability.NEEDS_OBSERVATIONS
    )


def test_complements_exclude_unavailable_empty_unsupported_and_failed_feature_states() -> None:
    known = _book(C.ONE, C.FIVE, genre=S.AN_CALC_TEST_GENRE)
    complement = _book(C.TWO, C.ONE, genre=S.AN_CALC_TEST_OTHER)
    unavailable = tuple(
        _book(index + C.THREE, C.FIVE, genre=S.AN_CALC_TEST_OTHER).model_copy(
            update={S.AN_CALC_FIELD_STATES_FIELD: {S.GENRES: state}}
        )
        for index, state in enumerate(C.AN_CALC_TEST_UNKNOWN_FEATURE_STATES)
    )
    component = _taste(_data(known, complement, *unavailable))
    finding = _group(component, S.GENRES, S.AN_CALC_TEST_GENRE)
    assert isinstance(finding.value, dict)
    comparison = finding.value[S.AN_CALC_COMPLEMENT]
    assert isinstance(comparison, dict)
    assert comparison[S.AN_CALC_COMPLEMENT_BOOKS] == [complement.book_id]
    assert finding.value[S.AN_CALC_MISSING] == C.FOUR
    assert finding.value[S.AN_CALC_KNOWN] == C.TWO
    assert finding.missing_count == C.FOUR


def test_english_iso_aliases_are_one_group_without_mutating_source_labels() -> None:
    short = _book(C.ONE, C.FOUR).model_copy(
        update={S.AN_CALC_TEST_FEATURES_FIELD: {S.LANGUAGE: (S.AN_CALC_LANGUAGE_EN,)}}
    )
    long = _book(C.TWO, C.FIVE).model_copy(
        update={S.AN_CALC_TEST_FEATURES_FIELD: {S.LANGUAGE: (S.AN_CALC_LANGUAGE_ENG,)}}
    )
    component = _taste(_data(short, long))
    finding = _group(component, S.LANGUAGE, S.AN_CALC_LANGUAGE_EN)
    assert finding.sample_size == C.TWO
    assert finding.supporting_books == (short.book_id, long.book_id)
    assert long.features[S.LANGUAGE] == (S.AN_CALC_LANGUAGE_ENG,)
    assert not any(
        finding.metric_id
        == S.AN_CALC_GROUP.format(feature=S.LANGUAGE, label=S.AN_CALC_LANGUAGE_ENG)
        for finding in component.findings
    )


def test_reading_profiles_include_unrated_works_and_are_independent_of_ratings() -> None:
    books = tuple(
        _book(
            index + C.ONE,
            C.FOUR,
            genre=S.AN_CALC_TEST_GENRE,
            author=S.AN_CALC_TEST_AUTHOR,
            pages=C.AN_CALC_SHORT_LIMIT,
        )
        for index in range(C.FIVE)
    )
    rated = _taste(_data(*books))
    unrated = _taste(_data(*(book.model_copy(update={S.RATING: C.NONE}) for book in books)))
    metrics = {S.AN_CALC_BREADTH.format(feature=feature) for feature in C.AN_CALC_FEATURES} | {
        S.AN_CALC_STRUCTURE_PAGES,
        S.AN_CALC_STRUCTURE_PUBLICATION,
        S.AN_PROFILE_FIRST_PUBLICATION,
        S.AN_CALC_RECURRING,
        S.AN_PROFILE_METADATA,
    }
    assert tuple(item for item in rated.findings if item.metric_id in metrics) == tuple(
        item for item in unrated.findings if item.metric_id in metrics
    )
    assert _finding(unrated, S.AN_CALC_STRUCTURE_PAGES).sample_size == C.FIVE
    assert _summary(unrated, S.AN_CALC_STRUCTURE_PAGES)[S.AN_CALC_MEDIAN] == C.AN_CALC_SHORT_LIMIT
    assert _summary(unrated, S.AN_CALC_RECURRING)[S.AN_CALC_PAIR_LENGTH][S.AN_CALC_COMBINATIONS]


def test_watchlist_fractional_composition_is_rating_independent_and_not_enjoyment() -> None:
    read = tuple(
        _book(
            index + C.ONE,
            genre=S.AN_CALC_TEST_GENRE,
        ).model_copy(
            update={
                S.AN_CALC_TEST_FEATURES_FIELD: {
                    S.GENRES: (S.AN_CALC_TEST_GENRE, S.AN_CALC_TEST_OTHER)
                }
            }
        )
        for index in range(C.FIVE)
    )
    watch = tuple(
        _book(
            index + C.TEN,
            genre=S.AN_CALC_TEST_GENRE,
            status=ReadingStatus.TO_READ,
        )
        for index in range(C.FIVE)
    )
    data = _data(*read, *watch)
    taste = _taste(data)
    result = build_watchlist(data, AnalyticsSettings(), taste, key=S.AN_CALC_TEST_KEY)
    metric = S.AN_PROFILE_WATCH_COMPOSITION.format(feature=S.GENRES)
    summary = _summary(result, metric)
    assert not taste.preferences
    assert summary[S.AN_CALC_READ_SHARE] == {
        S.AN_CALC_TEST_GENRE: C.ONE / C.TWO,
        S.AN_CALC_TEST_OTHER: C.ONE / C.TWO,
    }
    assert summary[S.AN_CALC_WATCH_SHARE] == {S.AN_CALC_TEST_GENRE: C.ONE}
    distance = summary[S.AN_CALC_COMPOSITION_DISTANCE]
    assert isinstance(distance, float) and C.ZERO < distance < C.ONE
    assert next(item for item in result.capabilities if item.metric_id == metric).state == (
        C.AnalyticsCapability.SUPPORTED
    )
    changed = _data(*(book.model_copy(update={S.RATING: C.FIVE}) for book in (*read, *watch)))
    recalculated = build_watchlist(
        changed, AnalyticsSettings(), _taste(changed), key=S.AN_CALC_TEST_KEY
    )
    assert _finding(result, metric) == _finding(recalculated, metric)


def test_work_language_availability_does_not_supply_edition_language_composition() -> None:
    read = _book(C.ONE).model_copy(
        update={
            S.AN_CALC_TEST_FEATURES_FIELD: {S.LANGUAGES: (S.AN_CALC_LANGUAGE_ENG,)},
            S.AN_CALC_FIELD_STATES_FIELD: {
                S.LANGUAGE: FieldState.UNAVAILABLE,
                S.LANGUAGES: FieldState.PRESENT,
            },
        }
    )
    watch = _book(C.TWO, status=ReadingStatus.TO_READ)
    data = _data(read, watch)
    taste = _taste(data)
    assert _finding(taste, S.AN_CALC_BREADTH.format(feature=S.LANGUAGE)).sample_size == C.ZERO
    coverage = _summary(taste, S.AN_PROFILE_METADATA)[S.AN_CALC_LABELS]
    assert isinstance(coverage, dict)
    assert coverage[S.LANGUAGE][S.AN_CALC_KNOWN] == C.ZERO
    assert coverage[S.LANGUAGES][S.AN_CALC_KNOWN] == C.ONE
    result = build_watchlist(data, AnalyticsSettings(), taste, key=S.AN_CALC_TEST_KEY)
    metric = S.AN_PROFILE_WATCH_COMPOSITION.format(feature=S.LANGUAGE)
    assert _summary(result, metric)[S.AN_CALC_COMPOSITION_DISTANCE] is C.NONE
    assert _summary(result, metric)[S.AN_CALC_COMPOSITION_GAPS] == []
    assert next(item for item in result.capabilities if item.metric_id == metric).state == (
        C.AnalyticsCapability.NEEDS_ENRICHMENT
    )


@pytest.mark.parametrize(S.AN_TEST_FIELD_STATE, C.AN_CALC_TEST_UNKNOWN_FEATURE_STATES)
def test_work_availability_never_rescues_unknown_matched_edition_language(
    field_state: FieldState,
) -> None:
    book = _book(C.ONE).model_copy(
        update={
            S.AN_CALC_TEST_FEATURES_FIELD: {
                S.LANGUAGE: (S.FR,),
                S.LANGUAGES: (S.AN_CALC_LANGUAGE_ENG,),
            },
            S.AN_CALC_FIELD_STATES_FIELD: {
                S.LANGUAGE: field_state,
                S.LANGUAGES: FieldState.PRESENT,
            },
        }
    )
    assert _labels(book, S.LANGUAGE) == ()
    assert _labels(book, S.LANGUAGES) == (S.AN_CALC_LANGUAGE_ENG,)
    assert book.field_states[S.LANGUAGE] == field_state
    assert book.features[S.LANGUAGE] == (S.FR,)


def test_mixed_language_scopes_have_separate_coverage_sources_and_no_false_group() -> None:
    edition = Observation(
        field=S.LANGUAGE,
        value=S.FR,
        state=FieldState.PRESENT,
        scope=S.EDITION,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    work = Observation(
        field=S.LANGUAGES,
        value=[S.AN_CALC_LANGUAGE_ENG],
        state=FieldState.PRESENT,
        scope=S.WORK,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    rejected = Observation(
        field=S.LANGUAGE,
        value=S.FR,
        state=FieldState.PRESENT,
        scope=S.WORK,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    book = _book(C.ONE, C.FOUR).model_copy(
        update={
            S.AN_CALC_TEST_FEATURES_FIELD: {
                S.LANGUAGE: (S.FR,),
                S.LANGUAGES: (S.AN_CALC_LANGUAGE_ENG,),
            },
            S.AN_EVIDENCE: (
                AnalysisEvidence(source=S.GOOGLE_BOOKS, source_id=S.TEST, observation=edition),
                AnalysisEvidence(source=S.OPEN_LIBRARY, source_id=S.TEST, observation=work),
                AnalysisEvidence(source=S.OPEN_LIBRARY, source_id=S.TEST, observation=rejected),
            ),
        }
    )
    data = _data(book)
    component = _taste(data)
    assert _labels(book, S.LANGUAGE) == (S.FR,)
    assert _group(component, S.LANGUAGE, S.FR).supporting_books == (book.book_id,)
    assert not any(
        finding.metric_id == S.AN_CALC_GROUP.format(feature=S.LANGUAGE, label=S.AN_CALC_LANGUAGE_EN)
        for finding in component.findings
    )
    coverage = _summary(component, S.AN_PROFILE_METADATA)[S.AN_CALC_LABELS]
    assert isinstance(coverage, dict)
    edition_coverage = coverage[S.LANGUAGE]
    work_coverage = coverage[S.LANGUAGES]
    assert isinstance(edition_coverage, dict)
    assert isinstance(work_coverage, dict)
    assert edition_coverage[S.AN_CALC_KNOWN] == work_coverage[S.AN_CALC_KNOWN] == C.ONE
    assert edition_coverage[S.AN_PROFILE_SOURCE_COUNTS] == {S.GOOGLE_BOOKS: C.ONE}
    assert work_coverage[S.AN_PROFILE_SOURCE_COUNTS] == {S.OPEN_LIBRARY: C.ONE}
    assert edition_coverage[S.AV_LANGUAGE_SCOPE] == S.EDITION
    assert work_coverage[S.AV_LANGUAGE_SCOPE] == S.WORK
    assert edition_coverage[S.AV_LANGUAGE_INTERPRETATION] == S.AV_MATCHED_EDITION_LANGUAGE
    assert work_coverage[S.AV_LANGUAGE_INTERPRETATION] == S.AV_WORK_LANGUAGE_AVAILABILITY
    assert tuple(item.observation for item in book.evidence) == (edition, work, rejected)
    with ProcessPoolExecutor(max_workers=C.ONE) as workers:
        parallel = workers.submit(
            build_taste, data, AnalyticsSettings(), key=S.AN_CALC_TEST_KEY
        ).result()
    assert parallel == component


def test_work_translation_languages_cannot_support_a_language_predictor() -> None:
    held = _book(C.ONE, C.FIVE).model_copy(
        update={
            S.AN_CALC_TEST_FEATURES_FIELD: {S.LANGUAGES: (S.AN_CALC_LANGUAGE_ENG,)},
            S.AN_CALC_FIELD_STATES_FIELD: {
                S.LANGUAGE: FieldState.UNAVAILABLE,
                S.LANGUAGES: FieldState.PRESENT,
            },
        }
    )
    training = tuple(
        _book(index, C.ONE if index <= C.SIX else C.FIVE).model_copy(
            update={
                S.AN_CALC_TEST_FEATURES_FIELD: (
                    {S.LANGUAGES: (S.AN_CALC_LANGUAGE_ENG,)} if index <= C.SIX else {}
                )
            }
        )
        for index in range(C.TWO, C.TEN + C.TWO)
    )
    prediction, baseline, dimensions = _predict_held_out(held, training, AnalyticsSettings())
    assert baseline == C.THREE
    assert prediction == baseline
    assert dimensions == {}


def test_rating_availability_audit_detects_unrepresentative_known_book_types() -> None:
    books = tuple(
        _book(index + C.ONE, C.FOUR, genre=S.AN_CALC_TEST_GENRE) for index in range(C.FIVE)
    ) + tuple(_book(index + C.TEN, genre=S.AN_CALC_TEST_OTHER) for index in range(C.FIVE))
    component = _taste(_data(*books))
    metric = S.AN_BIAS_METRIC.format(feature=S.GENRES)
    summary = _summary(component, metric)
    assert summary[S.AN_CALC_COMPOSITION_DISTANCE] == C.ONE
    available = summary[S.AN_BIAS_AVAILABLE]
    unavailable = summary[S.AN_BIAS_UNAVAILABLE]
    assert isinstance(available, dict) and isinstance(unavailable, dict)
    assert available[S.AN_CALC_TOTAL] == C.FIVE
    assert unavailable[S.AN_CALC_TOTAL] == C.FIVE
    assert _finding(component, metric).sample_size == C.TEN
    assert _finding(component, metric).reliability == S.AN_CALC_EXPLORATORY
