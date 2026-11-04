from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.metadata_quality import build_metadata_quality
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisComponent,
    AnalysisEvidence,
    AnalysisInput,
    AnalysisManifest,
    AnalyticsReport,
)
from bookystats.domain.metadata_quality import MetadataFieldCoverage, MetadataQualityReport
from bookystats.domain.models import FieldState, Observation, ReadingStatus, Source


def _data(*books: AnalysisBook) -> AnalysisInput:
    return AnalysisInput(
        books=books,
        as_of=S.AN_CALC_TEST_FINISH,
        manifest=AnalysisManifest(
            account_fingerprint=S.AN_CALC_TEST_ACCOUNT,
            settings_hash=S.AN_CALC_TEST_HASH,
            snapshots=(),
        ),
    )


def _analysis(data: AnalysisInput) -> AnalyticsReport:
    return AnalyticsReport(
        manifest=data.manifest,
        as_of=data.as_of,
        taste=AnalysisComponent(key=S.AN_TASTE, kind=C.AnalyticsComponentKind.TASTE, findings=()),
        watchlist=AnalysisComponent(
            key=S.AN_WATCHLIST, kind=C.AnalyticsComponentKind.WATCHLIST, findings=()
        ),
    )


def _evidence(
    field: str,
    value: str | int | list[str],
    *,
    source: Source = Source.OPEN_LIBRARY,
    scope: S.ObservationScope = S.WORK,
) -> AnalysisEvidence:
    provider_id = S.OL45883W if source == Source.OPEN_LIBRARY else S.TESTVOLUME_1
    url = (
        S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=provider_id)
        if source == Source.OPEN_LIBRARY
        else S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE.format(v0=provider_id)
    )
    return AnalysisEvidence(
        source=source.value,
        source_id=provider_id,
        observation=Observation(
            field=field,
            value=value,
            state=FieldState.PRESENT,
            scope=scope,
            source_url=url,
            observed_at=S.AN_CALC_TEST_FINISH,
        ),
    )


def _book(work_id: int = C.ONE, **changes: object) -> AnalysisBook:
    book = AnalysisBook(
        work_id=work_id,
        source_ids=(str(work_id),),
        title=S.MATILDA,
        collections=(S.READ,),
        status=ReadingStatus.READ,
    )
    return book.model_copy(update=changes)


def _row(
    report: MetadataQualityReport, field: str, population: str = S.MQ_REPORT_ALL
) -> MetadataFieldCoverage:
    return next(
        row for row in report.coverage if row.field == field and row.population_name == population
    )


def test_coverage_includes_unrated_read_and_distinguishes_language_scopes() -> None:
    evidence = _evidence(S.DESCRIPTION, S.META_COVERAGE_TEST_DETAILS_TEXT)
    described = _book(
        description=S.META_COVERAGE_TEST_DETAILS_TEXT,
        features={S.LANGUAGES: (S.EN,)},
        evidence=(evidence, evidence, _evidence(S.LANGUAGES, [S.EN])),
    )
    watch = _book(
        C.TWO,
        status=ReadingStatus.TO_READ,
        collections=(S.TO_READ,),
        field_states={S.DESCRIPTION: FieldState.EMPTY, S.LANGUAGE: FieldState.UNSUPPORTED},
    )
    data = _data(described, watch)
    report = build_metadata_quality(data, _analysis(data), {})
    assert report.population == C.TWO
    assert report.read_works == report.watchlist_works == C.ONE
    assert _row(report, S.DESCRIPTION).available == C.ONE
    assert _row(report, S.DESCRIPTION).missing == C.ONE
    assert _row(report, S.DESCRIPTION).states[FieldState.EMPTY.value] == C.ONE
    assert _row(report, S.DESCRIPTION).sources == {Source.OPEN_LIBRARY.value: C.ONE}
    assert _row(report, S.RATING, S.READ).population == C.ONE
    assert _row(report, S.RATING, S.READ).available == C.ZERO
    assert _row(report, S.LANGUAGE).available == C.ZERO
    assert _row(report, S.LANGUAGES).available == C.ONE
    assert report.identity.independently_verified_works is C.NONE
    assert not report.diagnostics
    assert MetadataQualityReport.model_validate_json(report.model_dump_json()) == report


def test_google_edition_descriptors_have_work_coverage_without_false_provenance_warnings() -> None:
    description = _evidence(
        S.DESCRIPTION,
        S.METADATA_TEST_RICH_DESCRIPTION,
        source=Source.GOOGLE_BOOKS,
        scope=S.EDITION,
    )
    genres = _evidence(
        S.GENRES,
        [S.ANALYTIC_CATEGORY_FANTASY],
        source=Source.GOOGLE_BOOKS,
        scope=S.EDITION,
    )
    book = _book(
        description=S.METADATA_TEST_RICH_DESCRIPTION,
        features={S.GENRES: (S.ANALYTIC_CATEGORY_FANTASY,)},
        evidence=(description, genres),
    )
    data = _data(book)
    report = build_metadata_quality(data, _analysis(data), {})
    assert _row(report, S.DESCRIPTION).available == C.ONE
    assert _row(report, S.DESCRIPTION).sources == {Source.GOOGLE_BOOKS.value: C.ONE}
    assert _row(report, S.GENRES).sources == {Source.GOOGLE_BOOKS.value: C.ONE}
    assert not report.diagnostics
    assert book.evidence[C.ZERO].observation.scope == S.EDITION


def test_optional_source_publication_disagreement_is_an_explicit_quality_diagnostic() -> None:
    flag = AnalysisEvidence(
        source=Source.GOODREADS.value,
        source_id=S.MQ_REPORT_TEST_GOODREADS_ID,
        public_url=S.MQ_REPORT_TEST_GOODREADS_URL,
        observation=Observation(
            field=S.METADATA_PUBLICATION_CONFLICT,
            value=S.IMPORT_BROWSER_FIRST_PUBLICATION,
            state=FieldState.PRESENT,
            scope=S.WORK,
            source_url=S.MQ_REPORT_TEST_CSV_ORIGIN,
        ),
    )
    data = _data(
        _book(field_states={S.FIRST_PUBLICATION_YEAR: FieldState.FAILED}, evidence=(flag,))
    )
    report = build_metadata_quality(data, _analysis(data), {})
    assert len(report.diagnostics) == C.ONE
    diagnostic = report.diagnostics[C.ZERO]
    assert diagnostic.code == S.METADATA_PUBLICATION_CONFLICT
    assert diagnostic.field == S.FIRST_PUBLICATION_YEAR
    assert diagnostic.work_ids == (C.ONE,)
    assert _row(report, S.FIRST_PUBLICATION_YEAR).available == C.ZERO


def test_work_consistency_is_not_accuracy_or_alternative_description_conflict() -> None:
    shared = (
        _evidence(S.TITLE, S.MATILDA),
        _evidence(S.TITLE, S.MATILDA, source=Source.GOOGLE_BOOKS, scope=S.EDITION),
        _evidence(S.ISBNS, [S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT]),
        _evidence(S.DESCRIPTION, S.META_COVERAGE_TEST_DETAILS_TEXT),
        _evidence(
            S.DESCRIPTION,
            S.MQ_REPORT_TEST_OTHER_DESCRIPTION,
            source=Source.GOOGLE_BOOKS,
        ),
    )
    first = _book(description=S.META_COVERAGE_TEST_DETAILS_TEXT, evidence=shared)
    second = _book(
        C.TWO,
        evidence=(
            _evidence(S.FIRST_PUBLICATION_YEAR, C.MQ_REPORT_TEST_YEAR),
            _evidence(
                S.FIRST_PUBLICATION_YEAR,
                C.MQ_REPORT_TEST_YEAR + C.ONE,
                source=Source.GOOGLE_BOOKS,
            ),
        ),
    )
    data = _data(first, second)
    report = build_metadata_quality(data, _analysis(data), {})
    assert report.identity.cross_provider_works == C.TWO
    assert report.identity.cross_provider_comparable_works == C.TWO
    assert report.identity.cross_provider_consistent_works == C.ONE
    assert report.identity.identity_anchor_works == C.ONE
    assert len(report.diagnostics) == C.ONE
    diagnostic = report.diagnostics[C.ZERO]
    assert diagnostic.code == S.MQ_REPORT_PROVIDER_DISCREPANCY
    assert diagnostic.field == S.FIRST_PUBLICATION_YEAR
    assert diagnostic.work_ids == (C.TWO,)


def test_contamination_provenance_and_unbacked_selection_are_reported_without_repair() -> None:
    provider_reader = _evidence(S.RATING, C.FOUR, source=Source.GOOGLE_BOOKS, scope=S.READER)
    browser_label = AnalysisEvidence(
        source=Source.GOODREADS.value,
        source_id=S.MQ_REPORT_TEST_GOODREADS_ID,
        public_url=S.MQ_REPORT_TEST_GOODREADS_URL,
        observation=Observation(
            field=S.GENRES,
            value=[S.ANALYTIC_CATEGORY_FANTASY],
            scope=S.WORK,
            state=FieldState.PRESENT,
            source_url=S.MQ_REPORT_TEST_CSV_ORIGIN,
        ),
    )
    unsafe = _evidence(S.LANGUAGE, S.EN, scope=S.EDITION).model_copy(
        update={
            S.DTX_OBSERVATION: _evidence(S.LANGUAGE, S.EN, scope=S.EDITION).observation.model_copy(
                update={S.META_COVERAGE_SOURCE_URL: S.MQ_REPORT_TEST_LANGUAGE_URL}
            )
        }
    )
    book = _book(
        description=S.META_COVERAGE_TEST_DETAILS_TEXT,
        features={S.GENRES: (S.ANALYTIC_CATEGORY_FANTASY,), S.LANGUAGE: (S.EN,)},
        evidence=(browser_label, provider_reader, unsafe),
        rating=C.FOUR,
    )
    data = _data(book)
    report = build_metadata_quality(data, _analysis(data), {})
    codes = {diagnostic.code for diagnostic in report.diagnostics}
    assert S.MQ_REPORT_UNBACKED in codes
    assert S.MQ_REPORT_UNTRUSTED in codes
    assert S.MQ_REPORT_PROVIDER_ORIGIN in codes
    assert S.MQ_REPORT_READER_CONTAMINATION in codes
    assert S.MQ_REPORT_UNVERIFIED_LABELS in codes
    assert _row(report, S.GENRES).sources == {}
    assert data.books[C.ZERO] == book


def _storygraph(field: str, value: str | float) -> AnalysisEvidence:
    return AnalysisEvidence(
        source=Source.STORYGRAPH.value,
        source_id=S.TESTVOLUME_1,
        observation=Observation(
            field=field,
            value=value,
            state=FieldState.PRESENT,
            scope=S.READER,
            source_url=S.MQ_REPORT_TEST_CSV_ORIGIN,
            observed_at=S.AN_CALC_TEST_FINISH,
        ),
    )


def test_storygraph_evidence_beyond_ratings_is_reader_contamination() -> None:
    rated = _book(evidence=(_storygraph(S.RATING, C.FOUR),), rating=C.FOUR)
    dated = _book(
        C.TWO,
        evidence=(
            _storygraph(S.RATING, C.FOUR),
            _storygraph(S.DTX_SUPPLEMENTAL_COMPLETION_DATE, S.DTX_TEST_DAY),
        ),
        rating=C.FOUR,
    )
    data = _data(rated, dated)
    report = build_metadata_quality(data, _analysis(data), {})
    contamination = [
        (diagnostic.field, diagnostic.work_ids)
        for diagnostic in report.diagnostics
        if diagnostic.code == S.MQ_REPORT_READER_CONTAMINATION
    ]
    assert contamination == [(S.DTX_SUPPLEMENTAL_COMPLETION_DATE, (C.TWO,))]


def test_quality_rejects_mismatched_analysis_snapshot_or_as_of() -> None:
    data = _data(_book())
    report = _analysis(data)
    stale = report.model_copy(update={S.CONTENT_ANALYSIS_AS_OF: S.AN_CALC_TEST_AS_OF})
    with pytest.raises(ValueError, match=S.MQ_REPORT_INPUT_MISMATCH):
        build_metadata_quality(data, stale, {})
    other_manifest = data.manifest.model_copy(
        update={S.MQ_REPORT_KEY_SETTINGS_HASH: S.DIFFERENT_BOOK}
    )
    with pytest.raises(ValueError, match=S.MQ_REPORT_INPUT_MISMATCH):
        build_metadata_quality(
            data, report.model_copy(update={S.AN_CALC_TEST_MANIFEST_FIELD: other_manifest}), {}
        )
