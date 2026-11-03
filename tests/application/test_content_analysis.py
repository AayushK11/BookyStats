from __future__ import annotations

import json
import pickle

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.content_analysis import build_content_analysis
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisEvidence,
    AnalysisInput,
    AnalysisManifest,
    AnalysisSnapshot,
    AnalyticsSettings,
    Finding,
)
from bookystats.domain.models import FieldState, Observation, ReadingStatus, Source, SyncState


def _book(
    work_id: int,
    text: str | None = S.CONTENT_ANALYSIS_TEST_TEXT,
    *,
    state: FieldState = FieldState.PRESENT,
    source: Source = Source.GOODREADS,
    collection: str = S.READ,
    evidence: bool = C.TRUE,
    url: str = S.CONTENT_ANALYSIS_TEST_PRIVATE_URL,
    public_url: str | None = C.NONE,
    authors: tuple[str, ...] = (),
    rating: float | None = C.NONE,
) -> AnalysisBook:
    return AnalysisBook(
        work_id=work_id,
        source_ids=(str(work_id),),
        title=S.CONTENT_ANALYSIS_TEST_UNMATCHED,
        authors=authors,
        rating=rating,
        collections=(collection,),
        status=ReadingStatus.UNKNOWN,
        description=text,
        field_states={S.DESCRIPTION: state},
        evidence=(
            AnalysisEvidence(
                source=source.value,
                source_id=str(work_id),
                public_url=public_url,
                observation=Observation(
                    field=S.DESCRIPTION,
                    value=text if state == FieldState.PRESENT else C.NONE,
                    state=state,
                    source_url=url,
                    observed_at=S.AN_CALC_TEST_FINISH,
                ),
            ),
        )
        if evidence
        else (),
    )


def _data(*books: AnalysisBook) -> AnalysisInput:
    return AnalysisInput(
        books=books,
        as_of=S.AN_CALC_TEST_FINISH,
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


def _analyze(data: AnalysisInput) -> tuple[Finding, ...]:
    return build_content_analysis(data, AnalyticsSettings(min_group_size=C.THREE))[C.ZERO]


def _metric(findings: tuple[Finding, ...], metric: str) -> Finding:
    return next(finding for finding in findings if finding.metric_id == metric)


def _hunger(findings: tuple[Finding, ...]) -> Finding:
    return _metric(findings, S.CONTENT_ANALYSIS_HUNGERS.format(collection=S.READ))


def _value(finding: Finding) -> dict[str, object]:
    assert isinstance(finding.value, dict)
    return dict(finding.value)


def _groups(finding: Finding) -> dict[str, object]:
    groups = _value(finding)[S.CONTENT_ANALYSIS_GROUPS]
    assert isinstance(groups, dict)
    return groups


def test_unrated_public_descriptions_have_bounded_reproducible_evidence() -> None:
    data = _data(*(_book(work_id) for work_id in range(C.ONE, C.SIX)))
    findings = _analyze(data)
    hunger = _hunger(findings)
    assert set(_groups(hunger)) == {name for name, _ in C.CONTENT_ANALYSIS_HUNGER_RULES}
    for group in _groups(hunger).values():
        assert isinstance(group, dict)
        assert group[S.CONTENT_ANALYSIS_COUNT] == C.FIVE
        assert group[S.CONTENT_ANALYSIS_SHARE] == C.ONE
        assert group[S.CONTENT_ANALYSIS_RULE_PATTERN]
        proofs = group[S.CONTENT_ANALYSIS_PROOF]
        assert len(proofs) == C.CONTENT_ANALYSIS_MAX_PROOFS
        assert proofs[C.ZERO][S.CONTENT_ANALYSIS_FIELD] == S.DESCRIPTION
        assert proofs[C.ZERO][S.CONTENT_ANALYSIS_URL] == S.CONTENT_ANALYSIS_TEST_URL
        assert proofs[C.ZERO][S.CONTENT_ANALYSIS_MATCH]
        assert proofs[C.ZERO][S.CONTENT_ANALYSIS_QUOTE]
    assert hunger.sample_size == C.FIVE
    assert hunger.source_snapshot_ids == (C.ONE,)
    assert hunger.calculation_version == data.manifest.calculation_version
    assert hunger.period == data.as_of
    assert hunger.uncertainty[S.CONTENT_ANALYSIS_RULE_VERSION] == S.CONTENT_ANALYSIS_VERSION
    assert S.CONTENT_ANALYSIS_HUNGER_LIMIT in hunger.limitations
    json.dumps([finding.model_dump(mode=S.JSON) for finding in findings], allow_nan=C.FALSE)


def test_changing_ratings_and_reviews_cannot_change_content_mentions_or_exposure() -> None:
    data = _data(*(_book(work_id) for work_id in range(C.ONE, C.FOUR)))
    changed = data.model_copy(
        update={
            S.BOOKS: tuple(
                book.model_copy(
                    update={S.RATING: C.FIVE, S.REVIEW: S.CONTENT_ANALYSIS_TEST_NEGATED}
                )
                for book in data.books
            )
        }
    )
    original_findings = _analyze(data)
    changed_findings = _analyze(changed)
    for metric in (
        S.CONTENT_ANALYSIS_THEMES.format(collection=S.READ),
        S.CONTENT_ANALYSIS_HUNGERS.format(collection=S.READ),
        S.ANX_EXPOSURE,
    ):
        assert _metric(original_findings, metric) == _metric(changed_findings, metric)


def test_file_lineage_and_public_book_reference_remain_separate() -> None:
    data = _data(
        *(
            _book(
                work_id,
                url=S.CONTENT_ANALYSIS_TEST_FILE_URL,
                public_url=S.CONTENT_ANALYSIS_TEST_PRIVATE_URL,
            )
            for work_id in range(C.ONE, C.FOUR)
        )
    )
    hunger = _hunger(_analyze(data))
    assert hunger.sample_size == C.THREE
    for group in _groups(hunger).values():
        assert isinstance(group, dict)
        assert group[S.CONTENT_ANALYSIS_PROOF][C.ZERO][S.CONTENT_ANALYSIS_URL] == (
            S.CONTENT_ANALYSIS_TEST_URL
        )
    assert all(
        book.evidence[C.ZERO].observation.source_url == S.CONTENT_ANALYSIS_TEST_FILE_URL
        for book in data.books
    )
    missing_reference = _data(_book(C.ONE, url=S.CONTENT_ANALYSIS_TEST_FILE_URL))
    assert _hunger(_analyze(missing_reference)).sample_size == C.ZERO


@pytest.mark.parametrize(
    S.CONTENT_ANALYSIS_TEST_PROVIDER_PARAMETERS,
    (
        (Source.GOOGLE_BOOKS, S.CONTENT_ANALYSIS_TEST_GOOGLE_URL),
        (Source.OPEN_LIBRARY, S.CONTENT_ANALYSIS_TEST_OPEN_LIBRARY_URL),
    ),
)
def test_selected_provider_description_evidence_is_usable(source: Source, url: str) -> None:
    data = _data(*(_book(work_id, source=source, url=url) for work_id in range(C.ONE, C.FOUR)))
    wonder = _groups(_hunger(_analyze(data)))[S.AN_WONDER]
    assert isinstance(wonder, dict)
    assert wonder[S.CONTENT_ANALYSIS_COUNT] == C.THREE
    assert wonder[S.CONTENT_ANALYSIS_PROOF][C.ZERO][S.CONTENT_ANALYSIS_SOURCE] == source.value
    assert wonder[S.CONTENT_ANALYSIS_PROOF][C.ZERO][S.CONTENT_ANALYSIS_URL] == url


@pytest.mark.parametrize(
    S.STATE,
    (FieldState.UNAVAILABLE, FieldState.FAILED, FieldState.UNSUPPORTED, FieldState.EMPTY),
)
def test_unknown_failed_empty_descriptions_are_not_known_zeroes(state: FieldState) -> None:
    data = _data(*(_book(work_id, state=state) for work_id in range(C.ONE, C.FOUR)))
    findings, capabilities = build_content_analysis(data, AnalyticsSettings(min_group_size=C.THREE))
    finding = _hunger(findings)
    assert finding.sample_size == C.ZERO
    assert finding.missing_count == C.THREE
    assert _groups(finding) == {}
    assert _value(finding)[S.CONTENT_ANALYSIS_MISSING] == {state.value: C.THREE}
    assert capabilities[C.ONE].state == C.AnalyticsCapability.NEEDS_ENRICHMENT


def test_nearby_negation_and_substrings_do_not_create_mentions() -> None:
    data = _data(
        *(_book(work_id, S.CONTENT_ANALYSIS_TEST_NEGATED) for work_id in range(C.ONE, C.FOUR))
    )
    assert _groups(_hunger(_analyze(data))) == {}
    theme = _metric(_analyze(data), S.CONTENT_ANALYSIS_THEMES.format(collection=S.READ))
    assert _groups(theme) == {}
    assert _value(theme)[S.CONTENT_ANALYSIS_UNMATCHED] == C.THREE


def test_empty_description_is_distinct_from_failed_and_unverified_provenance() -> None:
    data = _data(
        _book(C.ONE, S.EMPTY),
        _book(C.TWO, state=FieldState.FAILED),
        _book(C.THREE, evidence=C.FALSE),
    )
    finding = _hunger(_analyze(data))
    assert finding.sample_size == C.ZERO
    assert _value(finding)[S.CONTENT_ANALYSIS_MISSING] == {
        FieldState.EMPTY.value: C.ONE,
        FieldState.FAILED.value: C.ONE,
        S.CONTENT_ANALYSIS_UNVERIFIED: C.ONE,
    }


def test_many_terms_and_duplicate_work_count_once_per_family() -> None:
    books = tuple(
        _book(work_id, S.CONTENT_ANALYSIS_TEST_REPEATED) for work_id in range(C.ONE, C.FOUR)
    )
    hunger = _hunger(_analyze(_data(*books, *books)))
    intensity = _groups(hunger)[S.AN_INTENSITY]
    assert isinstance(intensity, dict)
    assert intensity[S.CONTENT_ANALYSIS_COUNT] == C.THREE
    assert hunger.sample_size == C.THREE


def test_support_limit_suppresses_unestablished_families() -> None:
    data = _data(_book(C.ONE), _book(C.TWO), _book(C.THREE, S.CONTENT_ANALYSIS_TEST_UNMATCHED))
    findings, capabilities = build_content_analysis(data, AnalyticsSettings(min_group_size=C.THREE))
    assert _groups(_hunger(findings)) == {}
    assert capabilities[C.ONE].state == C.AnalyticsCapability.NEEDS_OBSERVATIONS
    assert _hunger(findings).sample_size == C.THREE


def test_reviews_unverified_taxonomy_and_storygraph_text_are_not_description_evidence() -> None:
    books = tuple(
        _book(work_id, S.CONTENT_ANALYSIS_TEST_UNMATCHED).model_copy(
            update={
                S.REVIEW: S.CONTENT_ANALYSIS_TEST_TEXT,
                S.AN_CALC_TEST_FEATURES_FIELD: {
                    S.GENRES: (S.CONTENT_ANALYSIS_TEST_TEXT,),
                    S.CONTENT_ANALYSIS_TEST_UNVERIFIED: (S.CONTENT_ANALYSIS_TEST_TEXT,),
                },
            }
        )
        for work_id in range(C.ONE, C.FOUR)
    )
    assert _groups(_hunger(_analyze(_data(*books)))) == {}
    storygraph = _data(
        *(_book(work_id, source=Source.STORYGRAPH) for work_id in range(C.ONE, C.FOUR))
    )
    assert _hunger(_analyze(storygraph)).sample_size == C.ZERO
    no_evidence = _data(*(_book(work_id, evidence=C.FALSE) for work_id in range(C.ONE, C.FOUR)))
    assert _hunger(_analyze(no_evidence)).sample_size == C.ZERO


def test_rules_reject_genre_markers_idioms_and_marketing_cues() -> None:
    books = tuple(_book(work_id, S.AN3_TEST_MARKETING) for work_id in range(C.ONE, C.SIX))
    findings = _analyze(_data(*books))
    themes = _metric(findings, S.CONTENT_ANALYSIS_THEMES.format(collection=S.READ))
    assert _groups(_hunger(findings)) == {}
    assert _groups(themes) == {}
    assert _hunger(findings).sample_size == C.FIVE


def test_quotes_are_whole_description_sentences_with_rule_ids() -> None:
    books = tuple(_book(work_id, S.AN3_TEST_MIXED) for work_id in range(C.ONE, C.SIX))
    hunger = _hunger(_analyze(_data(*books)))
    assert S.AN3_CONTENT_RULES_NOTE in hunger.limitations
    assert set(_groups(hunger)) == {S.AN_WONDER}
    wonder = _groups(hunger)[S.AN_WONDER]
    assert isinstance(wonder, dict)
    proofs = wonder[S.CONTENT_ANALYSIS_PROOF]
    assert isinstance(proofs, list)
    assert proofs
    for proof in proofs:
        assert isinstance(proof, dict)
        assert proof[S.CONTENT_ANALYSIS_QUOTE] == S.AN3_TEST_CUE_SENTENCE
        assert proof[S.AN3_RULE_ID] == S.AN3_TEST_WONDER_RULE
        assert proof[S.AN3_QUOTE_TRUNCATED] is C.FALSE


def test_very_long_sentences_are_shortened_only_on_word_boundaries() -> None:
    books = tuple(_book(work_id, S.AN3_TEST_LONG_SENTENCE) for work_id in range(C.ONE, C.SIX))
    wonder = _groups(_hunger(_analyze(_data(*books))))[S.AN_WONDER]
    assert isinstance(wonder, dict)
    proofs = wonder[S.CONTENT_ANALYSIS_PROOF]
    assert isinstance(proofs, list)
    for proof in proofs:
        assert isinstance(proof, dict)
        quote = proof[S.CONTENT_ANALYSIS_QUOTE]
        assert isinstance(quote, str)
        assert proof[S.AN3_QUOTE_TRUNCATED] is C.TRUE
        assert str(proof[S.CONTENT_ANALYSIS_MATCH]) in quote
        start = S.AN3_TEST_LONG_SENTENCE.index(quote)
        end = start + len(quote)
        assert len(quote) < len(S.AN3_TEST_LONG_SENTENCE)
        assert S.AN3_TEST_LONG_SENTENCE[start - C.ONE] == S.SPACE
        assert S.AN3_TEST_LONG_SENTENCE[end] == S.SPACE


def test_watchlist_only_changes_are_excluded_and_top_level_job_is_picklable() -> None:
    read = tuple(_book(work_id) for work_id in range(C.ONE, C.FOUR))
    watch = tuple(_book(work_id, collection=S.TO_READ) for work_id in range(C.FOUR, C.SEVEN))
    watch += (_book(C.SEVEN, S.CONTENT_ANALYSIS_TEST_UNMATCHED, collection=S.TO_READ),)
    findings = _analyze(_data(*read, *watch))
    assert findings == _analyze(_data(*read))
    job = pickle.loads(pickle.dumps(build_content_analysis))
    assert job(_data(*read), AnalyticsSettings(min_group_size=C.THREE))[C.ZERO] == findings


def test_catalog_associations_never_emit_explicit_appetite_or_assessment_scores() -> None:
    findings = _analyze(_data(*(_book(work_id) for work_id in range(C.ONE, C.FOUR))))
    assert {
        S.AN_CALC_APPETITE.format(dimension=dimension) for dimension in C.ANALYTICS_DIMENSIONS
    }.isdisjoint(finding.metric_id for finding in findings)
    assert {
        S.CONTENT_ANALYSIS_THEMES.format(collection=collection)
        for collection in C.CONTENT_ANALYSIS_COLLECTIONS
    } | {
        S.CONTENT_ANALYSIS_HUNGERS.format(collection=collection)
        for collection in C.CONTENT_ANALYSIS_COLLECTIONS
    } <= {finding.metric_id for finding in findings}
    for collection in C.CONTENT_ANALYSIS_COLLECTIONS:
        hunger = _metric(findings, S.CONTENT_ANALYSIS_HUNGERS.format(collection=collection))
        assert set(_groups(hunger)).issubset({name for name, _ in C.CONTENT_ANALYSIS_HUNGER_RULES})


def test_catalog_enjoyment_excludes_unmatched_and_unverified_negative_examples() -> None:
    positive = tuple(
        _book(
            index,
            S.ANX_TEST_CONNECTION if index <= C.THREE else S.ANX_TEST_INTENSITY,
            authors=(S.AN_CALC_TEST_AUTHOR_FORMAT.format(index=index),),
            rating=C.FOUR if index <= C.THREE else C.ONE,
        )
        for index in range(C.ONE, C.SEVEN)
    )
    unknown = (
        _book(C.SEVEN, S.ANX_TEST_UNMATCHED, rating=C.FIVE),
        _book(C.EIGHT, evidence=C.FALSE, rating=C.FIVE),
    )
    data = _data(*positive, *unknown)
    findings = _analyze(data)
    exposure = _value(_metric(findings, S.ANX_EXPOSURE))
    assert exposure[S.ANX_POSITIVE] == C.SIX
    assert exposure[S.ANX_UNMATCHED] == C.ONE
    assert exposure[S.ANX_UNKNOWN] == C.ONE
    connection = _metric(findings, S.ANX_ENJOYMENT.format(dimension=S.AN_CONNECTION))
    summary = _value(connection)
    assert summary[S.ANX_BASELINE] == C.FIVE / C.TWO
    assert summary[S.ANX_ASSOCIATION][S.AN_CALC_MEAN] == C.FOUR
    assert summary[S.ANX_DIFFERENCE] > C.ZERO
    assert connection.sample_size == C.THREE
    assert (
        connection.uncertainty[S.CONTENT_ANALYSIS_PROOF][C.ZERO][S.CONTENT_ANALYSIS_QUOTE]
        == S.ANX_TEST_CONNECTION
    )
    changed = _analyze(
        _data(*positive, *(book.model_copy(update={S.RATING: C.ZERO}) for book in unknown))
    )
    assert _metric(changed, S.ANX_ENJOYMENT.format(dimension=S.AN_CONNECTION)) == connection
    assert all(S.ANX_FEATURE not in book.features for book in data.books)


def test_catalog_rating_availability_detects_positive_cohort_composition_shift() -> None:
    data = _data(
        *(
            _book(
                index,
                S.ANX_TEST_CONNECTION if index <= C.THREE else S.ANX_TEST_INTENSITY,
                rating=C.FOUR if index <= C.THREE else C.NONE,
            )
            for index in range(C.ONE, C.SEVEN)
        ),
        _book(C.SEVEN, S.ANX_TEST_UNMATCHED),
    )
    finding = _metric(_analyze(data), S.ANX_AVAILABILITY)
    summary = _value(finding)
    assert finding.sample_size == C.SIX
    assert summary[S.AN_BIAS_AVAILABLE][S.AN_CALC_TOTAL] == C.THREE
    assert summary[S.AN_BIAS_UNAVAILABLE][S.AN_CALC_TOTAL] == C.THREE
    assert summary[S.AN_CALC_COMPOSITION_DISTANCE] == C.ONE
    assert S.ANX_NOTE in finding.limitations
    assert _value(_metric(_analyze(data), S.ANX_EXPOSURE))[S.ANX_UNMATCHED] == C.ONE


def test_catalog_enjoyment_stays_unavailable_with_unrated_or_concentrated_evidence() -> None:
    for rating in (C.NONE, C.FOUR):
        data = _data(
            *(
                _book(
                    index,
                    S.ANX_TEST_CONNECTION,
                    authors=(S.AN_CALC_TEST_AUTHOR,),
                    rating=rating,
                )
                for index in range(C.ONE, C.FOUR)
            )
        )
        findings, capabilities = build_content_analysis(
            data, AnalyticsSettings(min_group_size=C.THREE)
        )
        metric = S.ANX_ENJOYMENT.format(dimension=S.AN_CONNECTION)
        assert _value(_metric(findings, metric))[S.ANX_ASSOCIATION] is C.NONE
        assert next(item for item in capabilities if item.metric_id == metric).state == (
            C.AnalyticsCapability.NEEDS_OBSERVATIONS
        )


def test_catalog_author_validation_is_positive_only_same_cohort_and_order_invariant() -> None:
    books = tuple(
        _book(
            index,
            S.ANX_TEST_CONNECTION
            if index <= C.AN_CALC_VALIDATION_MIN // C.TWO
            else S.ANX_TEST_INTENSITY,
            authors=(S.AN_CALC_TEST_AUTHOR_FORMAT.format(index=index),),
            rating=C.ONE if index <= C.AN_CALC_VALIDATION_MIN // C.TWO else C.FIVE,
        )
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN + C.ONE)
    )
    unmatched = _book(C.AN_CALC_VALIDATION_MIN + C.ONE, S.ANX_TEST_UNMATCHED, rating=C.ZERO)
    findings = _analyze(_data(*books, unmatched))
    validation = _metric(findings, S.ANX_VALIDATION)
    summary = _value(validation)
    assert summary[S.AN_CALC_N] == len(books)
    assert summary[S.AN_CALC_SIGNAL] == len(books)
    assert summary[S.AN_CALC_MAE_GAIN] > C.ZERO
    assert summary[S.AN_CALC_ADVANTAGE] is C.TRUE
    assert validation == _metric(_analyze(_data(*reversed(books), unmatched)), S.ANX_VALIDATION)
    assert unmatched.book_id not in validation.supporting_books


def test_catalog_author_validation_retains_worse_than_baseline_results() -> None:
    books = tuple(
        _book(
            index,
            S.ANX_TEST_CONNECTION
            if (index - C.ONE) % C.AN_CALC_VALIDATION_MIN < C.AN_CALC_VALIDATION_MIN // C.TWO
            else S.ANX_TEST_INTENSITY,
            authors=(
                S.AV_TEST_AUTHOR_A if index <= C.AN_CALC_VALIDATION_MIN else S.AV_TEST_AUTHOR_B,
            ),
            rating=C.ONE
            if index <= C.AN_CALC_VALIDATION_MIN // C.TWO
            or index > C.AN_CALC_VALIDATION_MIN + C.AN_CALC_VALIDATION_MIN // C.TWO
            else C.FIVE,
        )
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN * C.TWO + C.ONE)
    )
    summary = _value(_metric(_analyze(_data(*books)), S.ANX_VALIDATION))
    assert summary[S.AN_CALC_N] == len(books)
    assert summary[S.AN_CALC_ADVANTAGE] is C.FALSE
    assert summary[S.AN_CALC_MAE_GAIN] == -C.THREE / C.TWO


def test_catalog_validation_has_no_training_for_one_connected_author_component() -> None:
    books = tuple(
        _book(
            index,
            S.ANX_TEST_CONNECTION,
            authors=(S.AN_CALC_TEST_AUTHOR,),
            rating=C.FOUR,
        )
        for index in range(C.ONE, C.AN_CALC_VALIDATION_MIN + C.ONE)
    )
    summary = _value(_metric(_analyze(_data(*books)), S.ANX_VALIDATION))
    assert summary[S.AV_STATE] == S.AV_NO_TRAINING
    assert summary[S.AN_CALC_N] == C.ZERO
    assert summary[S.AV_NO_TRAINING_WORKS] == len(books)
