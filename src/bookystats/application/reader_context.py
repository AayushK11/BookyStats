from __future__ import annotations

import math
from datetime import datetime
from typing import NamedTuple

from pydantic import BaseModel, JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import report_format as F
from bookystats.domain.analytics import AnalysisBook, AnalysisInput, AnalyticsReport, Finding
from bookystats.domain.reader import ReaderSummary, build_reader_summary
from bookystats.domain.reader_report import BookItem


def mapping(value: JsonValue) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def items(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def number(value: JsonValue) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return C.NONE
    return float(value)


def integer(value: JsonValue) -> int | None:
    parsed = number(value)
    return C.NONE if parsed is C.NONE else int(parsed)


def text(value: JsonValue) -> str:
    return F.clean(value) if isinstance(value, str) else S.EMPTY


def numeric(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return C.NONE
    return parsed if math.isfinite(parsed) else C.NONE


def whole(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return C.NONE


class Context(NamedTuple):
    data: AnalysisInput
    analysis: AnalyticsReport
    summary: ReaderSummary
    read: tuple[AnalysisBook, ...]
    watch: tuple[AnalysisBook, ...]
    by_work: dict[int, AnalysisBook]
    by_book_id: dict[str, AnalysisBook]
    findings: dict[str, Finding]
    recommendations: dict[str, JsonValue]
    quality: dict[str, JsonValue]
    as_of: datetime | None

    @property
    def minimum(self) -> int:
        return self.data.manifest.settings.min_group_size

    @property
    def threshold(self) -> float:
        return self.summary.favorite_threshold

    @property
    def year(self) -> int | None:
        return C.NONE if self.as_of is C.NONE else self.as_of.year

    def value(self, metric_id: str) -> dict[str, JsonValue]:
        finding = self.findings.get(metric_id)
        return mapping(finding.value) if finding is not C.NONE else {}

    def rated(self) -> tuple[AnalysisBook, ...]:
        return tuple(
            book for book in self.read if book.rating is not C.NONE and not book.rating_conflict
        )

    def plausible_pages(self, book: AnalysisBook) -> int | None:
        pages = book.page_count
        usable = book.field_states.get(S.PAGE_COUNT, C.FieldState.PRESENT) == C.FieldState.PRESENT
        if pages is C.NONE or not usable or not C.RPT_MIN_PAGES <= pages <= C.RPT_MAX_PAGES:
            return C.NONE
        return pages

    def plausible_year(self, book: AnalysisBook) -> int | None:
        year = book.first_publication_year
        usable = (
            book.field_states.get(S.FIRST_PUBLICATION_YEAR, C.FieldState.PRESENT)
            == C.FieldState.PRESENT
        )
        if year is C.NONE or not usable or year < C.RPT_MIN_YEAR:
            return C.NONE
        return C.NONE if self.year is not C.NONE and year > self.year else year


def year_entries(ctx: Context, metric_id: str) -> dict[int, JsonValue]:
    entries: dict[int, JsonValue] = {}
    for key, entry in mapping(ctx.value(metric_id).get(S.ANX_COHORTS)).items():
        year = whole(key)
        if year is not C.NONE:
            entries[year] = entry
    return dict(sorted(entries.items()))


def title_of(book: AnalysisBook) -> str:
    return F.display_title(book.title) or S.RPT_UNTITLED


def item_of(book: AnalysisBook, detail: str = S.EMPTY) -> BookItem:
    return BookItem(title=title_of(book), byline=F.byline(book.authors), detail=detail)


def is_read(book: AnalysisBook) -> bool:
    return S.READ in book.collections or book.status == C.ReadingStatus.READ


def is_watch(book: AnalysisBook) -> bool:
    return S.TO_READ in book.collections or book.status == C.ReadingStatus.TO_READ


def payload(value: BaseModel | JsonValue) -> dict[str, JsonValue]:
    dumped = value.model_dump(mode=S.JSON) if isinstance(value, BaseModel) else value
    return mapping(dumped)


def make_context(
    data: AnalysisInput,
    analysis: AnalyticsReport,
    recommendations: BaseModel | JsonValue,
    quality: BaseModel | JsonValue,
) -> Context:
    summary = build_reader_summary(data)
    findings: dict[str, Finding] = {}
    for finding in (*analysis.taste.findings, *analysis.watchlist.findings):
        findings.setdefault(finding.metric_id, finding)
    return Context(
        data=data,
        analysis=analysis,
        summary=summary,
        read=tuple(book for book in data.books if is_read(book)),
        watch=tuple(book for book in data.books if is_watch(book)),
        by_work={book.work_id: book for book in data.books},
        by_book_id={book.book_id: book for book in data.books},
        findings=findings,
        recommendations=payload(recommendations),
        quality=payload(quality),
        as_of=F.as_of_parts(data.as_of),
    )


def tone_of(book: AnalysisBook, threshold: float) -> C.RptTone:
    if book.rating is C.NONE or book.rating_conflict:
        return C.RptTone.GREY
    return C.RptTone.TEAL if book.rating >= threshold else C.RptTone.AMBER


def is_sparse(count: int, minimum: int) -> bool:
    return count < minimum
