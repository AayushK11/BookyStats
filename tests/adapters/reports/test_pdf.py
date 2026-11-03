from __future__ import annotations

from io import BytesIO

from pydantic import JsonValue
from pypdf import PdfReader

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.reports.pdf import render_pdf
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisComponent,
    AnalysisInput,
    AnalysisManifest,
    AnalyticsReport,
    Finding,
)
from bookystats.domain.models import ReadingStatus


def _report(books: tuple[AnalysisBook, ...]) -> tuple[AnalysisInput, AnalyticsReport]:
    data = AnalysisInput(
        books=books,
        as_of=S.PDF_TEST_DATE,
        manifest=AnalysisManifest(
            account_fingerprint=S.PDF_TEST_ACCOUNT,
            settings_hash=S.PDF_TEST_HASH,
            snapshots=(),
        ),
    )
    analysis = AnalyticsReport(
        manifest=data.manifest,
        as_of=data.as_of,
        taste=AnalysisComponent(
            key=S.PDF_TEST_HASH, kind=C.AnalyticsComponentKind.TASTE, findings=()
        ),
        watchlist=AnalysisComponent(
            key=S.PDF_TEST_HASH, kind=C.AnalyticsComponentKind.WATCHLIST, findings=()
        ),
    )
    return data, analysis


def _render(
    data: AnalysisInput,
    analysis: AnalyticsReport,
    recommendations: dict[str, JsonValue] | None = C.NONE,
    quality: dict[str, JsonValue] | None = C.NONE,
) -> tuple[bytes, str, PdfReader]:
    stream = BytesIO()
    pages = render_pdf(data, analysis, recommendations or {}, quality or {}, stream)
    payload = stream.getvalue()
    reader = PdfReader(BytesIO(payload))
    assert pages == len(reader.pages)
    return payload, S.NEWLINE.join(page.extract_text() for page in reader.pages), reader


def test_empty_pdf_explains_unavailable_data() -> None:
    data, analysis = _report(())
    payload, text, reader = _render(data, analysis)
    assert payload.startswith(S.PDF_MAGIC)
    assert S.PDF_PAGES_UNAVAILABLE in text.replace(S.NEWLINE, S.SPACE)
    assert S.PDF_NO_SHORTLIST in text.replace(S.NEWLINE, S.SPACE)
    assert reader.outline
    assert S.RD_SECTION_COVERAGE in text
    assert len(reader.pages) <= C.RD_PAGE_BUDGET


def test_reader_cover_distinguishes_frequent_authors_from_supported_rating_favorites() -> None:
    books = tuple(
        AnalysisBook(
            work_id=index + C.ONE,
            source_ids=(str(index),),
            title=S.AN_CALC_TEST_AUTHOR_FORMAT.format(index=index),
            authors=(S.REC_TEST_AUTHOR if index < C.SIX else S.REC_TEST_OTHER_AUTHOR,),
            status=ReadingStatus.READ,
            rating=C.THREE if index < C.SIX else C.FIVE,
            page_count=C.AN_CALC_SHORT_LIMIT if index < C.SIX else C.AN_CALC_LONG_LIMIT,
        )
        for index in range(C.SIX + C.FIVE)
    )
    data, analysis = _report(books)
    _, text, reader = _render(data, analysis)
    first_page = S.SPACE.join(reader.pages[C.ZERO].extract_text().split())
    assert S.RD_HIGHLIGHTS in first_page
    assert (
        S.RD_REPEAT_CONTRAST.format(
            most_count=C.SIX,
            most_author=S.REC_TEST_AUTHOR,
            best_author=S.REC_TEST_OTHER_AUTHOR,
            best_average=S.RD_NUMBER.format(value=C.FIVE),
            best_count=C.FIVE,
        )
        in first_page
    )
    assert S.RD_SECTION_COVERAGE in text
    assert len(reader.pages) <= C.RD_PAGE_BUDGET


def test_long_unicode_titles_paginate_with_embedded_fonts_and_stable_order() -> None:
    books = tuple(
        AnalysisBook(
            work_id=index + C.ONE,
            source_ids=(str(index),),
            title=S.PDF_TEST_LONG_TITLE.format(index=index),
            authors=(S.PDF_TEST_AUTHOR,),
            status=ReadingStatus.READ,
            rating=C.FOUR if index % C.TWO else C.NONE,
            page_count=C.PDF_TEST_PAGES,
        )
        for index in range(C.PDF_INVENTORY_LIMIT)
    )
    data, analysis = _report(books)
    payload, text, reader = _render(data, analysis)
    reversed_data = data.model_copy(update={S.BOOKS: tuple(reversed(books))})
    repeated, repeated_text, _ = _render(reversed_data, analysis)
    assert payload == repeated
    assert text == repeated_text
    assert len(reader.pages) > C.PDF_TEST_MIN_PAGES
    assert S.PDF_TEST_UNICODE in text.replace(S.NEWLINE, S.SPACE)
    assert S.PDF_TEST_CJK in text
    assert S.PDF_TEST_TITLE_FIRST in text
    assert S.PDF_TEST_TITLE_LAST not in text
    assert len(reader.pages) <= C.RD_PAGE_BUDGET
    for page in reader.pages:
        for font in page[S.PDF_TEST_RESOURCES][S.PDF_TEST_FONT_RESOURCE].values():
            resolved = font.get_object()
            if S.PDF_TEST_DESCRIPTOR in resolved:
                assert S.PDF_TEST_FONT_FILE in resolved[S.PDF_TEST_DESCRIPTOR]


def test_supported_content_quote_links_and_shortlist_reasons() -> None:
    data, analysis = _report(())
    finding = Finding(
        metric_id=S.CONTENT_ANALYSIS_HUNGERS.format(collection=S.READ),
        population=S.READ,
        value={
            S.CONTENT_ANALYSIS_GROUPS: {
                S.AN_CONNECTION: {
                    S.CONTENT_ANALYSIS_COUNT: C.FIVE,
                    S.CONTENT_ANALYSIS_PROOF: [
                        {
                            S.CONTENT_ANALYSIS_WORK: S.PDF_TEST_SOURCE,
                            S.CONTENT_ANALYSIS_QUOTE: S.PDF_TEST_QUOTE,
                            S.CONTENT_ANALYSIS_URL: S.PDF_TEST_URL,
                        }
                    ],
                }
            }
        },
        sample_size=C.FIVE,
        reliability=S.AN_SUPPORTED,
        unit=S.WORK,
    )
    analysis = analysis.model_copy(
        update={S.AN_TASTE: analysis.taste.model_copy(update={S.AN_FINDINGS: (finding,)})}
    )
    recommendation: dict[str, JsonValue] = {
        S.PDF_KEY_SHORTLIST: [
            {
                S.TITLE: S.PDF_TEST_UNICODE,
                S.PDF_KEY_SCORE: C.ONE,
                S.PDF_KEY_REASONS: [S.PDF_TEST_REASON],
                S.PDF_KEY_MISSINGNESS: [S.PDF_TEST_GAP],
            }
        ]
    }
    _, text, reader = _render(data, analysis, recommendation)
    assert S.PDF_TEST_QUOTE in text
    assert S.PDF_TEST_REASON in text
    assert S.RD_REC_MISSING in S.SPACE.join(text.split())
    links = [
        annotation.get_object().get(S.PDF_TEST_ACTION, {}).get(S.PDF_TEST_URI)
        for page in reader.pages
        for annotation in page.get(S.PDF_TEST_ANNOTATIONS, [])
    ]
    assert S.PDF_TEST_URL in links


def test_nested_quality_and_diagnostics_are_readable_without_raw_json() -> None:
    data, analysis = _report(())
    quality: dict[str, JsonValue] = {
        S.PDF_KEY_COVERAGE: [
            {
                S.FIELD: S.DESCRIPTION,
                S.PDF_KEY_SCOPE: S.WORK,
                S.PDF_KEY_POPULATION: C.FIVE,
                S.PDF_KEY_AVAILABLE: C.ONE,
                S.PDF_KEY_MISSING: C.FOUR,
                S.PDF_KEY_STATES: {S.UNAVAILABLE: C.FOUR},
            }
        ],
        S.PDF_KEY_DIAGNOSTICS: [
            {S.CODE: S.PDF_TEST_QUALITY_CODE, S.PDF_KEY_COUNT: C.FOUR, S.MESSAGE: S.PDF_TEST_GAP}
        ],
    }
    _, text, _ = _render(data, analysis, quality=quality)
    assert S.PDF_TEST_QUALITY_CODE not in text
    assert S.RD_QUALITY_NOTICE in S.SPACE.join(text.split())


def test_oversized_single_word_cells_split_across_pages_without_layout_failure() -> None:
    data, analysis = _report(
        (
            AnalysisBook(
                work_id=C.ONE,
                source_ids=(S.PDF_TEST_SOURCE,),
                title=S.PDF_TEST_LONG_WORD * C.PDF_TEST_LONG_WORD_REPEATS,
                authors=(S.PDF_TEST_UNICODE * C.PDF_TEST_LONG_WORD_REPEATS,),
                status=ReadingStatus.READ,
            ),
        )
    )
    _, text, reader = _render(data, analysis)
    assert S.SPACE.join(S.PDF_TRUNCATED.split()) in S.SPACE.join(text.split())
    assert len(reader.pages) > C.PDF_TEST_MIN_PAGES


def test_validation_summary_is_not_crowded_out_by_many_feature_groups() -> None:
    data, analysis = _report(())
    groups = tuple(
        Finding(
            metric_id=S.PDF_TEST_GROUP_METRIC.format(index=index),
            population=S.READ,
            value=C.ONE,
            sample_size=C.FIVE,
            reliability=S.AN_SUPPORTED,
            unit=S.WORK,
        )
        for index in range(C.PDF_FINDING_LIMIT + C.ONE)
    )
    validation = Finding(
        metric_id=S.AN_CALC_VALIDATION,
        population=S.READ,
        value=S.PDF_TEST_VALIDATION_PROOF,
        sample_size=C.FIVE,
        reliability=S.AN_SUPPORTED,
        unit=S.WORK,
    )
    analysis = analysis.model_copy(
        update={
            S.AN_TASTE: analysis.taste.model_copy(update={S.AN_FINDINGS: (*groups, validation)})
        }
    )
    _, text, _ = _render(data, analysis)
    assert S.RD_VALIDATION_NOTE in S.SPACE.join(text.split())
    assert S.PDF_TEST_VALIDATION_PROOF not in text
