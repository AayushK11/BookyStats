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
from bookystats.domain.metadata_quality import (
    MetadataFieldCoverage,
    MetadataQualityReport,
    early_first_publication_year,
    implausible_page_count,
)
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


def _report(*books: AnalysisBook) -> MetadataQualityReport:
    data = _data(*books)
    analysis = AnalyticsReport(
        manifest=data.manifest,
        as_of=data.as_of,
        taste=AnalysisComponent(key=S.AN_TASTE, kind=C.AnalyticsComponentKind.TASTE, findings=()),
        watchlist=AnalysisComponent(
            key=S.AN_WATCHLIST, kind=C.AnalyticsComponentKind.WATCHLIST, findings=()
        ),
    )
    return build_metadata_quality(data, analysis, {})


def _evidence(field: str, value: str | int | list[str]) -> AnalysisEvidence:
    return AnalysisEvidence(
        source=Source.OPEN_LIBRARY.value,
        source_id=S.OL45883W,
        observation=Observation(
            field=field,
            value=value,
            state=FieldState.PRESENT,
            scope=S.WORK,
            source_url=S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=S.OL45883W),
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


def _watch(work_id: int) -> AnalysisBook:
    return _book(work_id, status=ReadingStatus.TO_READ, collections=(S.TO_READ,))


def test_each_missing_value_gets_one_deterministic_primary_cause() -> None:
    record = _evidence(S.TITLE, S.MATILDA)
    report = _report(
        _book(C.ONE),
        _watch(C.TWO),
        _book(C.THREE, evidence=(_evidence(S.GENRES, [C.L1_GEN_UNMAPPED_LABELS[C.ZERO]]),)),
        _book(
            C.FOUR,
            evidence=(record,),
            field_states={S.SERIES: FieldState.FAILED, S.LANGUAGE: FieldState.UNSUPPORTED},
        ),
        _book(C.FIVE, rating_conflict=C.TRUE, evidence=(record,)),
    )
    assert _row(report, S.DESCRIPTION).missing_causes == {
        S.L1_COV_CAUSE_NO_RECORD: C.TWO,
        S.L1_COV_CAUSE_NO_VALUE: C.THREE,
    }
    assert _row(report, S.GENRES).missing_causes == {
        S.L1_COV_CAUSE_NO_RECORD: C.TWO,
        S.L1_COV_CAUSE_UNMAPPED: C.ONE,
        S.L1_COV_CAUSE_NO_VALUE: C.TWO,
    }
    assert _row(report, S.SERIES).missing_causes == {
        S.L1_COV_CAUSE_NO_RECORD: C.TWO,
        S.L1_COV_CAUSE_FAILED: C.ONE,
        S.L1_COV_CAUSE_NO_VALUE: C.TWO,
    }
    assert _row(report, S.LANGUAGE).missing_causes[S.L1_COV_CAUSE_UNSUPPORTED] == C.ONE
    assert _row(report, S.RATING).missing_causes == {
        S.L1_COV_CAUSE_NO_RATING: C.THREE,
        S.L1_COV_CAUSE_NOT_APPLICABLE: C.ONE,
        S.MQ_REPORT_RATING_CONFLICT: C.ONE,
    }
    assert _row(report, S.RATING, S.TO_READ).missing_causes == {
        S.L1_COV_CAUSE_NOT_APPLICABLE: C.ONE
    }
    for row in report.coverage:
        assert sum(row.missing_causes.values()) == row.missing
        assert set(row.missing_causes) <= set(C.L1_COV_CAUSES)
    assert MetadataQualityReport.model_validate_json(report.model_dump_json()) == report
    assert report.limitations[-C.ONE] == S.L1_COV_LIMIT_CAUSES


def test_specific_genre_count_excludes_only_broad_families() -> None:
    report = _report(
        _book(C.ONE, features={S.GENRES: (S.ANALYTIC_CATEGORY_FICTION,)}),
        _book(
            C.TWO,
            features={S.GENRES: (S.ANALYTIC_CATEGORY_FICTION, S.ANALYTIC_CATEGORY_FANTASY)},
        ),
        _book(C.THREE, features={S.GENRES: (S.ANALYTIC_CATEGORY_NONFICTION,)}),
        _book(C.FOUR),
    )
    genres = _row(report, S.GENRES)
    assert (genres.available, genres.specific_available) == (C.THREE, C.ONE)
    assert all(row.specific_available is C.NONE for row in report.coverage if row.field != S.GENRES)
    assert _row(report, S.GENRES, S.READ).specific_available == C.ONE


@pytest.mark.parametrize(S.L1_COV_TEST_PARAMETERS, C.L1_COV_PLAUSIBILITY_CASES)
def test_implausible_values_are_diagnosed_but_raw_values_stay_available(
    pages: int | None, year: int | None, codes: tuple[str, ...]
) -> None:
    report = _report(_book(C.ONE, page_count=pages, first_publication_year=year))
    flagged = {
        item.code: item
        for item in report.diagnostics
        if item.code in (S.L1_COV_IMPLAUSIBLE_PAGES, S.L1_COV_EARLY_FIRST_PUBLICATION)
    }
    assert tuple(sorted(flagged)) == tuple(sorted(codes))
    assert all(item.work_ids == (C.ONE,) and item.count == C.ONE for item in flagged.values())
    assert implausible_page_count(pages) == (S.L1_COV_IMPLAUSIBLE_PAGES in codes)
    assert early_first_publication_year(year) == (S.L1_COV_EARLY_FIRST_PUBLICATION in codes)
    assert _row(report, S.PAGE_COUNT).available == (pages is not C.NONE)
    assert _row(report, S.FIRST_PUBLICATION_YEAR).available == (year is not C.NONE)


def test_new_coverage_fields_are_additive_for_older_payloads() -> None:
    older = MetadataFieldCoverage(
        field=S.DESCRIPTION,
        scope=S.WORK,
        population_name=S.MQ_REPORT_ALL,
        population=C.ONE,
        available=C.ZERO,
        missing=C.ONE,
        states={},
        sources={},
    )
    assert older.missing_causes == {}
    assert older.specific_available is C.NONE
