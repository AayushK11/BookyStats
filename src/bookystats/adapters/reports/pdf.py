from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from statistics import mean
from typing import BinaryIO, cast
from urllib.parse import urlsplit

from pydantic import JsonValue
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    LongTable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisBook, AnalysisInput, AnalyticsReport
from bookystats.domain.identifiers import normalized_text
from bookystats.domain.models import ReadingStatus
from bookystats.domain.reader import ReaderGroup, build_reader_summary


class _Document(BaseDocTemplate):
    def afterFlowable(self, flowable: Flowable) -> None:
        if isinstance(flowable, Paragraph) and flowable.style.name == S.PDF_STYLE_H1:
            text = flowable.getPlainText()
            key = S.PDF_BOOKMARK.format(index=hashlib.sha256(text.encode(S.UTF_8)).hexdigest())
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=C.ZERO, closed=C.FALSE)
            self.notify(S.PDF_TOC_ENTRY, (C.ZERO, text, self.page, key))


def _fonts() -> None:
    root = Path(__file__).parent / S.PDF_FONTS_FOLDER
    for name, filename in C.PDF_FONTS:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(root / filename)))
    pdfmetrics.registerFontFamily(
        S.PDF_FONT,
        normal=S.PDF_FONT,
        bold=S.PDF_FONT_BOLD,
        italic=S.PDF_FONT,
        boldItalic=S.PDF_FONT_BOLD,
    )


def _text(value: object, limit: int = C.PDF_TEXT_LIMIT) -> str:
    text = S.PDF_UNKNOWN if value is C.NONE else str(value)
    text = C.PDF_CONTROL_PATTERN.sub(S.SPACE, text)
    if len(text) > limit:
        text = text[:limit] + S.PDF_TRUNCATED
    fragments: list[str] = []
    for character in text:
        for font_name, _ in C.PDF_FONTS:
            font = cast(TTFont, pdfmetrics.getFont(font_name))
            if ord(character) in font.face.charToGlyph:
                fragments.append(
                    escape(character)
                    if font_name in C.PDF_PRIMARY_FONTS
                    else S.PDF_FONT_SPAN.format(font=font_name, text=escape(character))
                )
                break
        else:
            fragments.append(S.PDF_UNSUPPORTED_GLYPH.format(code=ord(character)))
    return S.EMPTY.join(fragments)


def _mapping(value: JsonValue) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def _items(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def _number(value: float | int | None) -> str:
    return S.PDF_UNKNOWN if value is C.NONE else S.RD_NUMBER.format(value=value)


def _percentage(known: int, total: int) -> str:
    return S.RD_PERCENT.format(value=known / total) if total else S.PDF_UNKNOWN


def _label(value: str) -> str:
    return value.replace(S.UNDERSCORE, S.SPACE).capitalize()


class _Report:
    def __init__(
        self,
        data: AnalysisInput,
        analysis: AnalyticsReport,
        recommendations: dict[str, JsonValue],
        quality: dict[str, JsonValue],
    ) -> None:
        self.data = data
        self.analysis = analysis
        self.recommendations = recommendations
        self.quality = quality
        self.summary = build_reader_summary(data)
        self.books = {book.work_id: book for book in data.books}
        self.book_by_id = {book.book_id: book for book in data.books}
        self.author_names = {
            normalized_text(author): author for book in data.books for author in book.authors
        }
        self.findings = {
            finding.metric_id: finding
            for finding in (*analysis.taste.findings, *analysis.watchlist.findings)
        }
        self.read = tuple(
            book
            for book in data.books
            if S.READ in book.collections or book.status == ReadingStatus.READ
        )
        self.story: list[Flowable] = []
        self.styles = {
            name: ParagraphStyle(
                name,
                fontName=S.PDF_FONT_BOLD if name in C.PDF_BOLD_STYLES else S.PDF_FONT,
                fontSize=size,
                leading=leading,
                textColor=colors.white
                if name == S.PDF_STYLE_TABLE_HEAD
                else colors.HexColor(S.PDF_INK),
                spaceAfter=space,
                alignment=TA_LEFT,
                splitLongWords=C.TRUE,
                allowWidows=C.FALSE,
                allowOrphans=C.FALSE,
                keepWithNext=name in C.PDF_HEADING_STYLES,
            )
            for name, size, leading, space in C.PDF_STYLE_SPECS
        }

    def paragraph(self, text: object, style: str = S.PDF_STYLE_BODY) -> Paragraph:
        return Paragraph(_text(text), self.styles[style])

    def add(self, text: object, style: str = S.PDF_STYLE_BODY) -> None:
        self.story.append(self.paragraph(text, style))

    def section(self, title: str) -> None:
        self.story.append(PageBreak())
        self.add(title, S.PDF_STYLE_H1)

    def value(self, metric: str) -> dict[str, JsonValue]:
        finding = self.findings.get(metric)
        return _mapping(finding.value) if finding is not C.NONE else {}

    def table(self, headers: tuple[str, ...], rows: list[list[object]]) -> None:
        if not rows:
            self.add(S.PDF_NO_OBSERVATIONS, S.PDF_STYLE_NOTE)
            return
        cells = [
            [self.paragraph(value, S.PDF_STYLE_TABLE_HEAD) for value in headers],
            *[[self.paragraph(value, S.PDF_STYLE_CELL) for value in row] for row in rows],
        ]
        table = LongTable(
            cells,
            colWidths=[C.PDF_CONTENT_WIDTH / len(headers)] * len(headers),
            repeatRows=C.ONE,
            hAlign=S.PDF_ALIGN_LEFT,
            splitByRow=C.ONE,
            splitInRow=C.ONE,
        )
        table.setStyle(
            TableStyle(
                [
                    (
                        S.PDF_BACKGROUND,
                        (C.ZERO, C.ZERO),
                        (-C.ONE, C.ZERO),
                        colors.HexColor(S.PDF_NAVY),
                    ),
                    (S.PDF_VALIGN, (C.ZERO, C.ZERO), (-C.ONE, -C.ONE), S.PDF_TOP),
                    (
                        S.PDF_ROW_BACKGROUNDS,
                        (C.ZERO, C.ONE),
                        (-C.ONE, -C.ONE),
                        [colors.white, colors.HexColor(S.PDF_PALE)],
                    ),
                    (S.PDF_LEFT_PADDING, (C.ZERO, C.ZERO), (-C.ONE, -C.ONE), C.PDF_CELL_PADDING),
                    (S.PDF_RIGHT_PADDING, (C.ZERO, C.ZERO), (-C.ONE, -C.ONE), C.PDF_CELL_PADDING),
                    (S.PDF_TOP_PADDING, (C.ZERO, C.ZERO), (-C.ONE, -C.ONE), C.PDF_CELL_PADDING),
                    (S.PDF_BOTTOM_PADDING, (C.ZERO, C.ZERO), (-C.ONE, -C.ONE), C.PDF_CELL_PADDING),
                ]
            )
        )
        self.story.extend((table, Spacer(C.ONE, C.PDF_SPACER)))

    def chart(self, counts: Counter[str], title: str, *, full: bool = C.FALSE) -> None:
        self.add(title, S.PDF_STYLE_H2)
        selected = (
            sorted(counts.items())
            if full
            else sorted(counts.items(), key=lambda item: (-item[C.ONE], item[C.ZERO]))[
                : C.PDF_CHART_ROWS
            ]
        )
        if not selected:
            self.add(S.PDF_NO_OBSERVATIONS)
            return
        maximum = max(value for _, value in selected)
        rows: list[list[object]] = []
        for label, value in selected:
            drawing = Drawing(C.RD_CHART_WIDTH, C.RD_ROW_HEIGHT)
            bar = Rect(
                C.ZERO,
                C.ZERO,
                C.RD_CHART_WIDTH * value / max(maximum, C.ONE),
                C.PDF_BAR_HEIGHT,
            )
            bar.fillColor = colors.HexColor(S.PDF_TEAL)
            bar.strokeColor = C.NONE
            drawing.add(bar)
            rows.append([self.paragraph(label), drawing, self.paragraph(value)])
        self.story.append(
            LongTable(
                rows,
                colWidths=[
                    C.PDF_CONTENT_WIDTH - C.RD_CHART_WIDTH - C.PDF_MARGIN,
                    C.RD_CHART_WIDTH,
                    C.PDF_MARGIN,
                ],
                hAlign=S.PDF_ALIGN_LEFT,
            )
        )
        self.story.append(Spacer(C.ONE, C.PDF_SPACER))

    def cover(self) -> None:
        summary = self.summary
        self.story.append(Spacer(C.ONE, C.PDF_COVER_SPACE))
        self.add(S.PDF_EYEBROW, S.PDF_STYLE_KICKER)
        self.add(S.RD_TITLE, S.PDF_STYLE_TITLE)
        self.add(S.RD_DECK, S.PDF_STYLE_DECK)
        self.add(
            S.RD_AS_OF.format(
                date=datetime.fromisoformat(self.data.as_of).strftime(S.RD_DATE_FORMAT)
            ),
            S.PDF_STYLE_NOTE,
        )
        self.add(
            S.RD_COVER_COUNTS.format(read=summary.read, watch=summary.watchlist), S.PDF_STYLE_H2
        )
        self.add(S.RD_COVER_RATING.format(rated=summary.rated))
        self.add(
            S.RD_COVER_HIGHLIGHT.format(
                pages=_number(summary.typical_pages), authors=summary.distinct_authors
            )
        )
        self.add(S.RD_COVER_NOTE)
        regulars = sorted(
            (
                group
                for group in summary.authors
                if group.adjusted_average is not C.NONE and group.rated >= C.TWO
            ),
            key=lambda group: (-(group.adjusted_average or C.ZERO), group.label.casefold()),
        )
        lengths = sorted(
            (
                group
                for group in summary.lengths
                if group.difference_from_baseline is not C.NONE
                and group.difference_from_baseline >= C.RD_HIGHLIGHT_DIFFERENCE
            ),
            key=lambda group: (-(group.difference_from_baseline or C.ZERO), group.label),
        )
        contrast = (
            regulars and summary.authors and regulars[C.ZERO].label != summary.authors[C.ZERO].label
        )
        if contrast or lengths:
            self.add(S.RD_HIGHLIGHTS, S.PDF_STYLE_H2)
        if contrast:
            most, best = summary.authors[C.ZERO], regulars[C.ZERO]
            self.add(
                S.RD_REPEAT_CONTRAST.format(
                    most_author=most.label[: C.RD_NAME_LIMIT],
                    most_count=most.works,
                    best_author=best.label[: C.RD_NAME_LIMIT],
                    best_count=best.rated,
                    best_average=_number(best.average),
                )
            )
        if lengths:
            best = lengths[C.ZERO]
            self.add(
                S.RD_LENGTH_HIGHLIGHT.format(
                    label=best.label.lower(),
                    count=best.rated,
                    average=_number(best.average),
                    baseline=_number(summary.average),
                )
            )
        self.story.append(PageBreak())
        self.add(S.RD_CONTENTS, S.PDF_STYLE_TITLE)
        toc = TableOfContents()
        toc.levelStyles = [self.styles[S.PDF_STYLE_TOC]]
        toc.dotsMinLevel = C.ZERO
        self.story.append(toc)

    def shape(self) -> None:
        self.section(S.RD_SECTION_SHAPE)
        self.add(S.RD_SHAPE_INTRO)
        summary = self.summary
        if summary.pages_known:
            self.add(
                S.RD_LENGTH_SUMMARY.format(
                    known=summary.pages_known,
                    total=summary.read,
                    pages=_number(summary.typical_pages),
                )
            )
            self.chart(
                Counter({group.label: group.works for group in summary.lengths}), S.PDF_PAGES_LABEL
            )
        else:
            self.add(S.PDF_PAGES_UNAVAILABLE)
        self.group_table(summary.lengths)
        if self.read:
            self.add(S.RD_READ_EXAMPLES, S.PDF_STYLE_H2)
            for book in sorted(self.read, key=lambda book: (book.title.casefold(), book.work_id))[
                : C.THREE
            ]:
                self.add(
                    S.RD_BOOK_REFERENCE.format(
                        title=book.title[: C.RD_NAME_LIMIT],
                        authors=S.COMMA_SPACE.join(book.authors) or S.PDF_UNKNOWN,
                    )
                )
        self.add(
            S.RD_GROUP_NOTE.format(minimum=self.data.manifest.settings.min_group_size),
            S.PDF_STYLE_NOTE,
        )

    def genres(self) -> None:
        self.section(S.RD_SECTION_GENRES)
        summary = self.summary
        self.add(S.RD_GENRE_INTRO)
        self.add(
            S.RD_GENRE_COVERAGE.format(
                known=summary.genres_known,
                total=summary.read,
                percent=_percentage(summary.genres_known, summary.read),
                missing=summary.read - summary.genres_known,
            )
        )
        self.chart(
            Counter({group.label: group.works for group in summary.genres}), S.PDF_GENRES_LABEL
        )
        self.add(S.RD_GENRE_CAUTION, S.PDF_STYLE_NOTE)
        self.group_table(summary.genres)

    def example(self, book: AnalysisBook) -> None:
        self.add(
            S.RD_BOOK_RATING.format(
                title=book.title[: C.RD_NAME_LIMIT],
                authors=S.COMMA_SPACE.join(book.authors),
                rating=_number(book.rating),
            )
        )

    def ratings(self) -> None:
        self.section(S.RD_SECTION_RATINGS)
        summary = self.summary
        self.add(S.RD_RATINGS_INTRO)
        self.add(
            S.RD_RATING_SUMMARY.format(
                rated=summary.rated,
                total=summary.read,
                percent=_percentage(summary.rated, summary.read),
                average=_number(summary.average),
                median=_number(summary.median_rating),
            )
        )
        self.chart(
            Counter(
                _number(book.rating)
                for book in self.read
                if book.rating is not C.NONE and not book.rating_conflict
            ),
            S.PDF_RATING_DISTRIBUTION,
            full=C.TRUE,
        )
        if summary.most_used_rating is not C.NONE:
            self.add(
                S.RD_RATING_VOCABULARY.format(
                    rating=_number(summary.most_used_rating),
                    count=summary.most_used_rating_count,
                    percent=_percentage(summary.most_used_rating_count, summary.rated),
                )
            )
        self.add(
            S.RD_FAVORITES.format(
                count=summary.favorites, threshold=_number(summary.favorite_threshold)
            )
        )
        self.add(S.RD_FAVORITE_EXAMPLES, S.PDF_STYLE_H2)
        for work_id in summary.favorite_examples:
            self.example(self.books[work_id])
        self.add(S.RD_FAVORITES_NOTE, S.PDF_STYLE_NOTE)

    def group_table(self, groups: tuple[ReaderGroup, ...]) -> None:
        self.table(
            C.RD_GROUP_HEADERS,
            [
                [group.label, group.works, group.rated, _number(group.average)]
                for group in groups[: C.RD_GROUP_LIMIT]
            ],
        )

    def crowd(self) -> None:
        self.section(S.RD_SECTION_CROWD)
        self.add(S.RD_CROWD_INTRO)
        comparisons = self.summary.community_comparisons
        if comparisons:
            self.add(
                S.RD_CROWD_SUMMARY.format(
                    count=len(comparisons),
                    difference=S.RD_DIFFERENCE.format(
                        value=mean(item.difference for item in comparisons)
                    ),
                )
            )
        else:
            self.add(S.PDF_NO_OBSERVATIONS)
        self.add(S.RD_CROWD_NOTE, S.PDF_STYLE_NOTE)
        for positive, title in C.RD_CROWD_DIRECTIONS:
            self.add(title, S.PDF_STYLE_H2)
            selected = sorted(
                (
                    item
                    for item in comparisons
                    if (item.difference > C.ZERO if positive else item.difference < C.ZERO)
                ),
                key=lambda item: (
                    -abs(item.difference),
                    self.books[item.work_id].title.casefold(),
                    item.work_id,
                ),
            )[: C.REC_EXAMPLE_LIMIT]
            for item in selected:
                self.add(
                    S.RD_CROWD_ITEM.format(
                        title=self.books[item.work_id].title[: C.RD_NAME_LIMIT],
                        personal=_number(item.personal),
                        community=_number(item.community),
                        difference=S.RD_DIFFERENCE.format(value=item.difference),
                    )
                )
                self.add(
                    S.RD_CROWD_COUNT.format(count=item.community_sample_size)
                    if item.community_sample_size is not C.NONE
                    else S.RD_CROWD_UNKNOWN_COUNT,
                    S.PDF_STYLE_NOTE,
                )

    def authors(self) -> None:
        self.section(S.RD_SECTION_AUTHORS)
        self.add(S.RD_AUTHORS_INTRO)
        if self.summary.authors:
            self.add(
                S.RD_AUTHOR_CONCENTRATION.format(
                    count=self.summary.authors[C.ZERO].works, total=self.summary.read
                )
            )
        self.group_table(self.summary.authors)
        for group in self.summary.authors[: C.REC_EXAMPLE_LIMIT]:
            if group.examples:
                self.add(group.label, S.PDF_STYLE_H3)
                self.example(self.books[group.examples[C.ZERO]])

    def preferences(self) -> None:
        self.section(S.RD_SECTION_PREFERENCES)
        summary = self.summary
        self.add(S.RD_PREFERENCES_INTRO)
        self.add(S.RD_BASELINE.format(average=_number(summary.average), rated=summary.rated))
        self.add(
            S.RD_GROUP_NOTE.format(minimum=self.data.manifest.settings.min_group_size),
            S.PDF_STYLE_NOTE,
        )
        groups = sorted(
            (
                group
                for group in (*summary.genres, *summary.lengths)
                if group.difference_from_baseline is not C.NONE
            ),
            key=lambda group: (
                -abs(group.difference_from_baseline or C.ZERO),
                group.label.casefold(),
            ),
        )[: C.RD_GROUP_LIMIT]
        if not groups:
            self.add(S.RD_NO_SIGNAL)
        for group in groups:
            difference = group.difference_from_baseline
            if difference is C.NONE:
                continue
            self.add(
                S.RD_SIGNAL.format(
                    label=group.label,
                    count=group.rated,
                    average=_number(group.average),
                    adjusted=_number(group.adjusted_average),
                    difference=S.RD_DIFFERENCE.format(value=difference),
                )
            )

    def appetites(self) -> None:
        self.section(S.RD_SECTION_APPETITES)
        self.add(S.RD_APPETITE_INTRO)
        groups = _mapping(
            self.value(S.CONTENT_ANALYSIS_HUNGERS.format(collection=S.READ)).get(
                S.CONTENT_ANALYSIS_GROUPS
            )
        )
        for dimension in C.ANALYTICS_DIMENSIONS:
            group = _mapping(groups.get(dimension))
            count = group.get(S.CONTENT_ANALYSIS_COUNT)
            self.add(
                S.RD_APPETITE_SUPPORT.format(label=_label(dimension), count=count)
                if isinstance(count, int) and not isinstance(count, bool)
                else S.RD_APPETITE_ABSENT.format(label=_label(dimension)),
                S.PDF_STYLE_H3,
            )
            association = _mapping(
                self.value(S.ANX_ENJOYMENT.format(dimension=dimension)).get(S.ANX_ASSOCIATION)
            )
            rated = association.get(S.AN_CALC_RATED)
            average = association.get(S.AN_CALC_MEAN)
            if (
                isinstance(rated, int)
                and rated >= self.data.manifest.settings.min_group_size
                and isinstance(average, int | float)
                and not isinstance(average, bool)
            ):
                self.add(S.RD_APPETITE_RATING.format(count=rated, average=_number(average)))
            proofs = _items(group.get(S.CONTENT_ANALYSIS_PROOF))
            if proofs:
                self.proof(_mapping(proofs[C.ZERO]))

    def proof(self, proof: dict[str, JsonValue]) -> None:
        identity = proof.get(S.CONTENT_ANALYSIS_WORK)
        book = self.book_by_id.get(identity) if isinstance(identity, str) else C.NONE
        rendered = _text(
            S.RD_QUOTE.format(
                title=book.title[: C.RD_NAME_LIMIT] if book is not C.NONE else S.PDF_UNKNOWN,
                quote=proof.get(S.CONTENT_ANALYSIS_QUOTE),
            )
        )
        reference = proof.get(S.CONTENT_ANALYSIS_URL)
        if isinstance(reference, str) and C.CONTENT_ANALYSIS_PUBLIC_URL.match(reference):
            parsed = urlsplit(reference)
            if not (parsed.username or parsed.password or parsed.query or parsed.fragment):
                rendered += S.SPACE + S.PDF_LINK.format(
                    url=escape(reference, quote=C.TRUE), label=S.RD_PROOF_LINK
                )
        self.story.append(Paragraph(rendered, self.styles[S.PDF_STYLE_NOTE]))

    def timeline(self) -> None:
        self.section(S.RD_SECTION_TIME)
        self.add(S.RD_TIME_INTRO)
        cohorts = _mapping(self.value(S.ANX_COMPLETION_COHORTS).get(S.ANX_COHORTS))
        counts = Counter(
            {
                year: count
                for year, value in cohorts.items()
                if isinstance((count := _mapping(value).get(S.AN_CALC_N)), int)
                and not isinstance(count, bool)
            }
        )
        self.add(S.RD_TIME_COVERAGE.format(known=sum(counts.values()), total=self.summary.read))
        self.chart(counts, S.RD_SECTION_TIME, full=C.TRUE)
        self.table(
            C.RD_TIME_HEADERS,
            [
                [
                    year,
                    _mapping(value).get(S.AN_CALC_N),
                    _mapping(_mapping(value).get(S.ANX_DATE_ORIGIN)).get(
                        S.ANX_AUTHORITATIVE_DATE, C.ZERO
                    ),
                    _mapping(_mapping(value).get(S.ANX_DATE_ORIGIN)).get(
                        S.ANX_SUPPLEMENTAL_DATE, C.ZERO
                    ),
                ]
                for year, value in sorted(cohorts.items())
            ],
        )
        self.add(S.RD_TIME_NOTE, S.PDF_STYLE_NOTE)

    def watchlist(self) -> None:
        self.section(S.RD_SECTION_WATCH)
        summary = self.summary
        self.add(S.RD_WATCH_INTRO)
        self.add(
            S.RD_WATCH_SUMMARY.format(
                familiar=summary.watchlist_familiar_authors,
                new=summary.watchlist_new_authors,
                unknown=summary.watchlist_unknown_authors,
            )
        )
        self.add(
            S.RD_RECOMMENDATION_COUNTS.format(
                ranked=len(_items(self.recommendations.get(S.PDF_KEY_RANKED))),
                unknown=len(_items(self.recommendations.get(S.PDF_KEY_UNRANKABLE))),
                excluded=len(_items(self.recommendations.get(S.PDF_KEY_EXCLUDED))),
            )
        )
        read = {group.label: group.works for group in summary.genres}
        watch = {group.label: group.works for group in summary.watchlist_genres}
        self.add(S.RD_READ_VS_WATCH, S.PDF_STYLE_H2)
        self.table(
            C.RD_WATCH_HEADERS,
            [
                [label, read.get(label, C.ZERO), watch.get(label, C.ZERO)]
                for label in sorted(
                    read.keys() | watch.keys(), key=lambda label: (-watch.get(label, C.ZERO), label)
                )[: C.RD_GROUP_LIMIT]
            ],
        )
        self.add(S.RD_WATCH_GENRE_NOTE, S.PDF_STYLE_NOTE)

    def shortlist(self) -> None:
        self.section(S.RD_SECTION_SHORTLIST)
        self.add(S.RD_SHORTLIST_INTRO)
        items = _items(self.recommendations.get(S.PDF_KEY_SHORTLIST))[: C.REC_SHORTLIST_SIZE]
        if not items:
            self.add(S.PDF_NO_SHORTLIST)
        for index, value in enumerate(items, start=C.ONE):
            if index == C.RD_SHORTLIST_PAGE_SIZE + C.ONE:
                self.section(S.RD_SECTION_SHORTLIST_MORE)
            item = _mapping(value)
            self.add(S.RD_REC_TITLE.format(rank=index, title=item.get(S.TITLE)), S.PDF_STYLE_H2)
            self.add(
                S.COMMA_SPACE.join(str(author) for author in _items(item.get(S.AUTHORS))),
                S.PDF_STYLE_NOTE,
            )
            components = _items(item.get(S.PDF_KEY_COMPONENTS))
            for component in components[: C.TWO]:
                part = _mapping(component)
                feature = part.get(S.PDF_KEY_FEATURE)
                label = part.get(S.PDF_KEY_LABEL)
                if feature == S.REC_AUTHOR and isinstance(label, str):
                    label = self.author_names.get(normalized_text(label), label)
                self.add(
                    S.RD_REC_SIGNAL.format(
                        feature=C.RD_FEATURE_LABELS.get(feature, S.RD_HEADER_CATEGORY)
                        if isinstance(feature, str)
                        else S.RD_HEADER_CATEGORY,
                        label=label,
                        count=part.get(S.PDF_KEY_SAMPLE_SIZE),
                    )
                )
            if not components:
                for reason in _items(item.get(S.PDF_KEY_REASONS))[: C.ONE]:
                    self.add(reason)
            examples = _items(item.get(S.PDF_KEY_SUPPORTING))
            if examples:
                example = _mapping(examples[C.ZERO])
                self.add(
                    S.RD_REC_EXAMPLE.format(
                        title=example.get(S.TITLE), rating=example.get(S.RATING)
                    )
                )
            if _items(item.get(S.PDF_KEY_MISMATCHES)):
                self.add(S.RD_REC_CAUTION, S.PDF_STYLE_NOTE)
            if _items(item.get(S.PDF_KEY_MISSINGNESS)):
                self.add(S.RD_REC_MISSING, S.PDF_STYLE_NOTE)

    def coverage(self) -> None:
        self.section(S.RD_SECTION_COVERAGE)
        self.add(S.RD_COVERAGE_INTRO)
        records = {
            (record.get(S.FIELD), record.get(S.PDF_KEY_POPULATION_NAME)): record
            for value in _items(self.quality.get(S.PDF_KEY_COVERAGE))
            if (record := _mapping(value))
        }
        rows: list[list[object]] = []
        gaps: list[tuple[float, str]] = []
        for field, label in C.RD_COVERAGE_FIELDS:
            row: list[object] = [label]
            for population in C.RD_POPULATIONS:
                record = records.get((field, population), {})
                known, total = record.get(S.PDF_KEY_AVAILABLE), record.get(S.PDF_KEY_POPULATION)
                if isinstance(known, int) and isinstance(total, int) and total > C.ZERO:
                    row.append(
                        S.RD_COVERAGE_VALUE.format(
                            known=known, total=total, percent=_percentage(known, total)
                        )
                    )
                    if population == S.READ:
                        gaps.append((known / total, label))
                else:
                    row.append(S.PDF_UNKNOWN)
            rows.append(row)
        self.table(C.RD_COVERAGE_HEADERS, rows)
        if gaps:
            self.add(
                S.RD_COVERAGE_GAP.format(
                    fields=S.COMMA_SPACE.join(label for _, label in sorted(gaps)[: C.THREE])
                )
            )
        if _items(self.quality.get(S.PDF_KEY_DIAGNOSTICS)):
            self.add(S.RD_QUALITY_NOTICE)
        self.add(S.RD_MISSING_NOTE, S.PDF_STYLE_NOTE)

    def notes(self) -> None:
        self.section(S.RD_SECTION_NOTES)
        self.add(S.RD_NOTES)
        self.add(S.RD_SOURCES_NOTE)
        self.add(S.RD_VALIDATION_NOTE)
        self.add(S.PDF_LIMIT_FONT, S.PDF_STYLE_NOTE)

    def build(self, destination: BinaryIO) -> int:
        for section in (
            self.cover,
            self.shape,
            self.genres,
            self.ratings,
            self.crowd,
            self.authors,
            self.preferences,
            self.appetites,
            self.timeline,
            self.watchlist,
            self.shortlist,
            self.coverage,
            self.notes,
        ):
            section()
        document = _Document(
            destination,
            pagesize=C.PDF_PAGE_SIZE,
            leftMargin=C.PDF_MARGIN,
            rightMargin=C.PDF_MARGIN,
            topMargin=C.PDF_MARGIN,
            bottomMargin=C.PDF_MARGIN,
            title=S.RD_TITLE,
            author=S.PDF_AUTHOR,
            pageCompression=C.ONE,
            invariant=C.ONE,
            allowSplitting=C.ONE,
        )
        frame = Frame(
            C.PDF_MARGIN,
            C.PDF_MARGIN,
            C.PDF_CONTENT_WIDTH,
            C.PDF_CONTENT_HEIGHT,
            leftPadding=C.ZERO,
            rightPadding=C.ZERO,
            topPadding=C.ZERO,
            bottomPadding=C.ZERO,
        )

        def furniture(canvas: Canvas, doc: BaseDocTemplate) -> None:
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor(S.PDF_TEAL))
            canvas.setLineWidth(C.PDF_RULE_WIDTH)
            canvas.line(
                C.PDF_MARGIN, C.PDF_HEADER_Y, C.PDF_PAGE_WIDTH - C.PDF_MARGIN, C.PDF_HEADER_Y
            )
            canvas.setFont(S.PDF_FONT, C.PDF_NOTE_SIZE)
            canvas.setFillColor(colors.HexColor(S.PDF_MUTED))
            canvas.drawString(C.PDF_MARGIN, C.PDF_FOOTER_Y, S.PDF_FOOTER)
            canvas.drawRightString(
                C.PDF_PAGE_WIDTH - C.PDF_MARGIN, C.PDF_FOOTER_Y, S.PDF_PAGE.format(page=doc.page)
            )
            canvas.restoreState()

        document.addPageTemplates(
            [PageTemplate(id=S.PDF_TEMPLATE, frames=[frame], onPage=furniture)]
        )
        document.multiBuild(self.story)
        return document.page


def render_pdf(
    data: AnalysisInput,
    analysis: AnalyticsReport,
    recommendations: dict[str, JsonValue],
    quality: dict[str, JsonValue],
    destination: BinaryIO,
) -> int:
    _fonts()
    return _Report(data, analysis, recommendations, quality).build(destination)
