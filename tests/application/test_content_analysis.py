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
) -> AnalysisBook:
    return AnalysisBook(
        work_id=work_id,
        source_ids=(str(work_id),),
        title=S.CONTENT_ANALYSIS_TEST_UNMATCHED,
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


def test_changing_every_rating_and_review_cannot_change_content_findings() -> None:
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
    assert _analyze(data) == _analyze(changed)


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
    wonder = _groups(hunger)[S.AN_WONDER]
    assert isinstance(wonder, dict)
    assert wonder[S.CONTENT_ANALYSIS_COUNT] == C.THREE
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


def test_watchlist_only_changes_are_excluded_and_top_level_job_is_picklable() -> None:
    read = tuple(_book(work_id) for work_id in range(C.ONE, C.FOUR))
    watch = tuple(_book(work_id, collection=S.TO_READ) for work_id in range(C.FOUR, C.SEVEN))
    watch += (_book(C.SEVEN, S.CONTENT_ANALYSIS_TEST_UNMATCHED, collection=S.TO_READ),)
    findings = _analyze(_data(*read, *watch))
    assert findings == _analyze(_data(*read))
    job = pickle.loads(pickle.dumps(build_content_analysis))
    assert job(_data(*read), AnalyticsSettings(min_group_size=C.THREE))[C.ZERO] == findings


def test_no_assessment_colors_axes_or_appetite_features_are_emitted() -> None:
    findings = _analyze(_data(*(_book(work_id) for work_id in range(C.ONE, C.FOUR))))
    assert {finding.metric_id for finding in findings} == {
        S.CONTENT_ANALYSIS_THEMES.format(collection=collection)
        for collection in C.CONTENT_ANALYSIS_COLLECTIONS
    } | {
        S.CONTENT_ANALYSIS_HUNGERS.format(collection=collection)
        for collection in C.CONTENT_ANALYSIS_COLLECTIONS
    }
    for collection in C.CONTENT_ANALYSIS_COLLECTIONS:
        hunger = _metric(findings, S.CONTENT_ANALYSIS_HUNGERS.format(collection=collection))
        assert set(_groups(hunger)).issubset({name for name, _ in C.CONTENT_ANALYSIS_HUNGER_RULES})
