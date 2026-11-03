from __future__ import annotations

import re
from html import escape
from math import ceil
from typing import Any, NamedTuple
from urllib.parse import urlsplit

from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    HRFlowable,
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.reports.charts import (
    Badge,
    BarCell,
    ColumnChart,
    Dumbbell,
    Legend,
    LegendEntry,
    Meter,
    RatingScale,
)
from bookystats.adapters.reports.document import Heading, ReportDocument
from bookystats.adapters.reports.theme import Theme, paint
from bookystats.domain.reader_report import (
    BarRow,
    BarsBlock,
    Block,
    BookGroup,
    BookItem,
    BooksBlock,
    CalloutBlock,
    Chapter,
    CompareBlock,
    CoverageBlock,
    FactsBlock,
    ProseBlock,
    Quote,
    QuotesBlock,
    Stat,
    TilesBlock,
)

type Command = tuple[Any, ...]


class Card(NamedTuple):
    content: list[Flowable]
    tone: C.RptTone


def safe_link(url: str) -> bool:
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return C.FALSE
    if parts.scheme not in C.RPT_LINK_SCHEMES or host is C.NONE or port is not C.NONE:
        return C.FALSE
    if parts.username is not C.NONE or parts.password is not C.NONE:
        return C.FALSE
    return any(
        host == allowed or host.endswith(S.RPT_HOST_DOT + allowed) for allowed in C.RPT_LINK_HOSTS
    )


def balanced(count: int, limit: int) -> int:
    return ceil(count / ceil(count / limit))


def scale_of(block: BarsBlock) -> float:
    if block.maximum:
        return block.maximum
    peak = max(
        (abs(row.value) for row in block.rows if row.value is not C.NONE), default=float(C.ZERO)
    )
    return peak or float(C.ONE)


def rows_style(commands: list[Command]) -> TableStyle:
    return TableStyle(commands)


class Composer:
    def __init__(self, theme: Theme, document: ReportDocument) -> None:
        self.theme = theme
        self.document = document
        self.width = document.frame_width
        self.room = document.frame_height * C.RPT_CHAPTER_ROOM

    def heading(self, text: str, name: C.RptText, level: int, listed: bool = C.FALSE) -> Heading:
        return Heading(self.document, self.theme, text, name, level, listed)

    def para(self, text: str, name: C.RptText, bullet: str | None = C.NONE) -> Paragraph:
        return self.theme.para(text, name, bullet)

    def bold(self, text: str, name: C.RptText) -> Paragraph:
        return self.theme.paragraph(S.RPT_BOLD.format(text=self.theme.markup(text)), name)

    def small(self, text: str) -> str:
        return S.RPT_SMALL.format(
            color=S.RPT_HEX_MUTED, size=C.RPT_INLINE_SIZE, text=self.theme.markup(text)
        )

    def header(self, kicker: str, title: str, intro: str, listed: bool = C.TRUE) -> list[Flowable]:
        parts: list[Flowable] = []
        if kicker:
            parts.append(self.para(kicker, C.RptText.KICKER))
        parts.append(self.heading(title, C.RptText.H1, C.ZERO, listed))
        parts.append(
            HRFlowable(
                width=C.RPT_RULE_LENGTH,
                thickness=C.RPT_RULE_THICK,
                color=paint(S.RPT_HEX_TEAL),
                spaceBefore=C.RPT_ACCENT,
                spaceAfter=C.RPT_GAP,
                hAlign=S.RPT_TS_LEFT,
            )
        )
        if intro:
            parts.append(self.para(intro, C.RptText.LEAD))
        return [CondPageBreak(self.room), KeepTogether(parts)]

    def chapter(self, chapter: Chapter) -> list[Flowable]:
        flows = self.header(chapter.kicker, chapter.title, chapter.intro)
        for block in chapter.blocks:
            flows.extend(self.render(block))
        return flows

    def render(self, block: Block) -> list[Flowable]:
        if isinstance(block, ProseBlock):
            return self.prose(block)
        if isinstance(block, TilesBlock):
            return self.assemble(block.heading, [self.tile_grid(block.tiles)], block.note)
        if isinstance(block, FactsBlock):
            return self.facts(block)
        if isinstance(block, BarsBlock):
            return self.bars(block)
        if isinstance(block, QuotesBlock):
            return self.quotes(block)
        if isinstance(block, BooksBlock):
            return self.books(block)
        if isinstance(block, CompareBlock):
            return self.compare(block)
        if isinstance(block, CoverageBlock):
            return self.coverage(block)
        return self.callout(block)

    def assemble(
        self, title: str, units: list[list[Flowable]], note: str, loose: bool = C.FALSE
    ) -> list[Flowable]:
        units = [unit for unit in units if unit]
        if not units:
            return []
        if title:
            lead: list[Flowable] = [self.heading(title, C.RptText.H2, C.ONE)]
        else:
            lead = [Spacer(C.ONE, C.RPT_BLOCK_GAP)]
        tail: list[Flowable] = [self.para(note, C.RptText.NOTE)] if note else []
        if not loose:
            return [KeepTogether([*lead, *(part for unit in units for part in unit), *tail])]
        flows: list[Flowable] = []
        for index, unit in enumerate(units):
            parts = list(unit)
            if index == C.ZERO:
                parts = [*lead, *parts]
            if index == len(units) - C.ONE:
                parts = [*parts, *tail]
            flows.append(KeepTogether(parts) if len(parts) > C.ONE else parts[C.ZERO])
        return flows

    def prose(self, block: ProseBlock) -> list[Flowable]:
        units: list[list[Flowable]] = [
            [self.para(text, C.RptText.BODY)] for text in block.paragraphs
        ]
        return self.assemble(block.heading, units, S.EMPTY, loose=C.TRUE)

    def callout(self, block: CalloutBlock) -> list[Flowable]:
        content: list[Flowable] = []
        if block.heading:
            content.append(self.para(block.heading, C.RptText.CALLOUT_HEAD))
        content.extend(self.para(text, C.RptText.CALLOUT_BODY) for text in block.paragraphs)
        grid = self.card_grid([[Card(content, block.tone)]], C.ONE)
        return [KeepTogether([Spacer(C.ONE, C.RPT_BLOCK_GAP), grid])]

    def card_grid(self, rows: list[list[Card]], per_row: int, after: float = C.ZERO) -> Table:
        columns = per_row * C.TWO - C.ONE
        width = (self.width - (per_row - C.ONE) * C.RPT_GAP) / per_row
        widths = [width if index % C.TWO == C.ZERO else C.RPT_GAP for index in range(columns)]
        data: list[list[object]] = []
        heights: list[float | None] = []
        commands: list[Command] = [
            (S.RPT_TS_VALIGN, C.RPT_CELL_START, C.RPT_CELL_END, S.RPT_TS_TOP)
        ]
        for cards in rows:
            if data:
                data.append([S.EMPTY] * columns)
                heights.append(C.RPT_GAP)
            line = len(data)
            cells: list[object] = [S.EMPTY] * columns
            for index, card in enumerate(cards):
                column = index * C.TWO
                cells[column] = card.content
                corner = (column, line)
                commands.extend(
                    (
                        (S.RPT_TS_BACKGROUND, corner, corner, paint(C.RPT_TONE_TINTS[card.tone])),
                        (
                            S.RPT_TS_LINE_BEFORE,
                            corner,
                            corner,
                            C.RPT_ACCENT,
                            paint(C.RPT_TONE_COLORS[card.tone]),
                        ),
                        (S.RPT_TS_LEFT_PADDING, corner, corner, C.RPT_PAD + C.RPT_ACCENT),
                        (S.RPT_TS_RIGHT_PADDING, corner, corner, C.RPT_PAD),
                        (S.RPT_TS_TOP_PADDING, corner, corner, C.RPT_PAD),
                        (S.RPT_TS_BOTTOM_PADDING, corner, corner, C.RPT_PAD),
                    )
                )
            data.append(cells)
            heights.append(C.NONE)
        table = Table(
            data,
            colWidths=widths,
            rowHeights=heights,
            style=rows_style(commands),
            spaceAfter=after,
        )
        table.hAlign = S.RPT_TS_LEFT
        return table

    def inner_width(self, per_row: int) -> float:
        width = (self.width - (per_row - C.ONE) * C.RPT_GAP) / per_row
        return width - C.RPT_ACCENT - C.TWO * C.RPT_PAD

    def tile_grid(self, tiles: tuple[Stat, ...], hero: bool = C.FALSE) -> list[Flowable]:
        if not tiles:
            return []
        per_row = balanced(len(tiles), C.RPT_TILES_PER_ROW)
        inner = self.inner_width(per_row)
        names = C.RPT_HERO_VALUES if hero else C.RPT_TILE_VALUES
        cards = [self.tile_card(tile, names, inner) for tile in tiles]
        rows = [cards[start : start + per_row] for start in range(C.ZERO, len(cards), per_row)]
        return [self.card_grid(rows, per_row)]

    def tile_card(self, tile: Stat, names: tuple[C.RptText, ...], inner: float) -> Card:
        content: list[Flowable] = [self.para(tile.label, C.RptText.TILE_LABEL)]
        value_style = self.theme.fit(tile.value, names, inner)
        content.append(self.para(tile.value, value_style))
        if tile.detail:
            content.append(self.para(tile.detail, C.RptText.TILE_DETAIL))
        return Card(content, tile.tone)

    def facts(self, block: FactsBlock) -> list[Flowable]:
        per_row = min(C.RPT_FACT_COLUMNS, len(block.facts))
        cards = [
            Card(
                [
                    self.para(fact.headline, C.RptText.FACT_HEAD),
                    self.para(fact.body, C.RptText.FACT_BODY),
                ],
                fact.tone,
            )
            for fact in block.facts
        ]
        if not cards:
            return []
        rows = [cards[start : start + per_row] for start in range(C.ZERO, len(cards), per_row)]
        body: list[list[Flowable]] = [
            [self.card_grid([row], per_row, after=C.RPT_GAP)] for row in rows
        ]
        return self.assemble(block.heading, body, block.note, loose=C.TRUE)

    def bars(self, block: BarsBlock) -> list[Flowable]:
        if not block.rows:
            return []
        maximum = scale_of(block)
        if block.style is C.RptBarStyle.VERTICAL:
            chart: list[Flowable] = [ColumnChart(self.theme, block.rows, maximum)]
            notes = self.column_notes(block)
            if notes:
                chart.append(self.para(notes, C.RptText.CAPTION))
            return self.assemble(block.heading, [chart], block.note)
        table: list[Flowable] = [self.bar_table(block, maximum)]
        if block.axis:
            table.append(self.para(S.RPT_SCALE_CAPTION.format(axis=block.axis), C.RptText.CAPTION))
        return self.assemble(block.heading, [table], block.note)

    def column_notes(self, block: BarsBlock) -> str:
        notes = [S.RPT_SCALE_CAPTION.format(axis=block.axis)] if block.axis else []
        if any(row.sparse for row in block.rows):
            notes.append(S.RPT_COLUMN_SPARSE_NOTE)
        if any(row.value is C.NONE for row in block.rows):
            notes.append(S.RPT_COLUMN_UNKNOWN_NOTE)
        return S.SPACE.join(notes)

    def bar_table(self, block: BarsBlock, maximum: float) -> Table:
        label_width = self.width * C.RPT_BAR_LABEL_SHARE
        track_width = self.width * C.RPT_BAR_TRACK_SHARE
        widths = [label_width, track_width, self.width - label_width - track_width]
        data = [self.bar_cells(row, block.style, maximum) for row in block.rows]
        commands: list[Command] = [
            (S.RPT_TS_VALIGN, C.RPT_CELL_START, C.RPT_CELL_END, S.RPT_TS_MIDDLE),
            (S.RPT_TS_LEFT_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.ZERO),
            (S.RPT_TS_RIGHT_PADDING, C.RPT_CELL_START, (C.ONE, -C.ONE), C.RPT_GAP + C.RPT_PAD),
            (S.RPT_TS_RIGHT_PADDING, (C.TWO, C.ZERO), C.RPT_CELL_END, C.ZERO),
            (S.RPT_TS_TOP_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
            (S.RPT_TS_BOTTOM_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
            (
                S.RPT_TS_LINE_BELOW,
                C.RPT_CELL_START,
                (-C.ONE, -C.TWO),
                C.RPT_HAIRLINE,
                paint(S.RPT_HEX_RULE),
            ),
        ]
        table = Table(data, colWidths=widths, style=rows_style(commands))
        table.hAlign = S.RPT_TS_LEFT
        return table

    def bar_cells(self, row: BarRow, style: C.RptBarStyle, maximum: float) -> list[object]:
        value: list[Flowable] = []
        if row.shown:
            bold = S.RPT_BOLD.format(text=self.theme.markup(row.shown))
            value.append(self.theme.paragraph(bold, C.RptText.BAR_VALUE))
        caption = [row.caption] if row.caption else []
        if row.sparse:
            caption.append(S.RPT_SPARSE_TAG)
        if caption:
            value.append(self.para(S.RPT_DOT_SEPARATOR.join(caption), C.RptText.CAPTION))
        return [self.para(row.label, C.RptText.BAR_LABEL), BarCell(row, style, maximum), value]

    def quotes(self, block: QuotesBlock) -> list[Flowable]:
        units: list[list[Flowable]] = [[self.quote_card(quote)] for quote in block.quotes]
        return self.assemble(block.heading, units, block.note, loose=C.TRUE)

    def quote_card(self, quote: Quote) -> Flowable:
        meta = S.RPT_BOLD.format(text=self.theme.markup(quote.title))
        if quote.byline:
            meta += S.RPT_DOT_SEPARATOR + self.theme.markup(quote.byline)
        if quote.link is not C.NONE and safe_link(quote.link.url):
            meta += S.RPT_DOT_SEPARATOR + S.RPT_LINK_ANCHOR.format(
                url=escape(quote.link.url, quote=C.TRUE),
                color=S.RPT_HEX_TEAL,
                label=self.theme.markup(quote.link.label),
            )
        text = S.RPT_QUOTED.format(text=self.cued(quote.text, quote.cue))
        content: list[Flowable] = [
            self.theme.paragraph(text, C.RptText.QUOTE),
            self.theme.paragraph(meta, C.RptText.QUOTE_META),
        ]
        return self.card_grid([[Card(content, C.RptTone.TEAL)]], C.ONE, after=C.RPT_GAP)

    def cued(self, text: str, cue: str) -> str:
        found = C.NONE
        if cue.strip():
            pattern = S.RPT_CUE_PATTERN.format(cue=re.escape(cue.strip()))
            found = re.search(pattern, text, re.IGNORECASE)
        if found is C.NONE:
            return self.theme.markup(text)
        start, end = found.span()
        return (
            self.theme.markup(text[:start])
            + S.RPT_BOLD.format(text=self.theme.markup(text[start:end]))
            + self.theme.markup(text[end:])
        )

    def books(self, block: BooksBlock) -> list[Flowable]:
        ranked = any(book.marker or book.lines for group in block.groups for book in group.books)
        units: list[list[Flowable]] = []
        for group in block.groups:
            lead: list[Flowable] = []
            if group.heading:
                lead.append(self.para(group.heading, C.RptText.GROUP))
            if not ranked:
                units.append([*lead, self.book_list(group)])
                continue
            for book in group.books:
                units.append([*lead, self.ranked_book(book)])
                lead = []
        return self.assemble(block.heading, units, block.note, loose=C.TRUE)

    def ranked_book(self, book: BookItem) -> Flowable:
        content: list[Flowable] = [self.bold(book.title, C.RptText.BOOK_TITLE)]
        meta = S.RPT_DOT_SEPARATOR.join(text for text in (book.byline, book.detail) if text)
        if meta:
            content.append(self.para(meta, C.RptText.BOOK_META))
        content.extend(self.para(line, C.RptText.BOOK_LINE, S.RPT_BULLET) for line in book.lines)
        badge_width = C.RPT_BADGE_RADIUS * C.TWO + C.RPT_PAD
        marker: Flowable | str = Badge(self.theme, book.marker) if book.marker else S.EMPTY
        commands: list[Command] = [
            (S.RPT_TS_VALIGN, C.RPT_CELL_START, C.RPT_CELL_END, S.RPT_TS_TOP),
            (S.RPT_TS_BACKGROUND, C.RPT_CELL_START, C.RPT_CELL_END, paint(S.RPT_HEX_TINT_INK)),
            (S.RPT_TS_LEFT_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_PAD),
            (S.RPT_TS_RIGHT_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_PAD),
            (S.RPT_TS_TOP_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_PAD),
            (S.RPT_TS_BOTTOM_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_PAD),
            (S.RPT_TS_RIGHT_PADDING, C.RPT_CELL_START, C.RPT_CELL_START, C.ZERO),
        ]
        table = Table(
            [[marker, content]],
            colWidths=[badge_width + C.RPT_PAD, self.width - badge_width - C.RPT_PAD],
            style=rows_style(commands),
            spaceAfter=C.RPT_GAP,
        )
        table.hAlign = S.RPT_TS_LEFT
        return table

    def book_list(self, group: BookGroup) -> Table:
        left = self.width * C.RPT_BOOK_TITLE_SHARE
        data: list[list[object]] = []
        for book in group.books:
            title = self.theme.markup(book.title)
            if book.byline:
                title += S.SPACE + self.small(S.RPT_DOT_SEPARATOR.lstrip() + book.byline)
            data.append(
                [
                    self.theme.paragraph(title, C.RptText.BOOK_TITLE),
                    self.para(book.detail, C.RptText.BOOK_DETAIL),
                ]
            )
        commands: list[Command] = [
            (S.RPT_TS_VALIGN, C.RPT_CELL_START, C.RPT_CELL_END, S.RPT_TS_TOP),
            (S.RPT_TS_LEFT_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.ZERO),
            (S.RPT_TS_RIGHT_PADDING, C.RPT_CELL_START, (C.ZERO, -C.ONE), C.RPT_PAD),
            (S.RPT_TS_RIGHT_PADDING, (C.ONE, C.ZERO), C.RPT_CELL_END, C.ZERO),
            (S.RPT_TS_TOP_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
            (S.RPT_TS_BOTTOM_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
            (
                S.RPT_TS_LINE_BELOW,
                C.RPT_CELL_START,
                (-C.ONE, -C.TWO),
                C.RPT_HAIRLINE,
                paint(S.RPT_HEX_RULE),
            ),
        ]
        table = Table(data, colWidths=[left, self.width - left], style=rows_style(commands))
        table.hAlign = S.RPT_TS_LEFT
        return table

    def compare(self, block: CompareBlock) -> list[Flowable]:
        if not block.rows:
            return []
        title_width = self.width * C.RPT_COMPARE_TITLE_SHARE
        chart_width = self.width * C.RPT_COMPARE_CHART_SHARE
        widths = [title_width, chart_width, self.width - title_width - chart_width]
        data: list[list[object]] = [[S.EMPTY, RatingScale(), S.EMPTY]]
        for row in block.rows:
            title: list[Flowable] = [self.bold(row.title, C.RptText.BOOK_TITLE)]
            if row.byline:
                title.append(self.para(row.byline, C.RptText.BOOK_META))
            values = S.RPT_COMPARE_VALUES.format(
                personal=self.theme.markup(row.personal_text),
                community=self.theme.markup(row.community_text),
                dot=S.RPT_DOT_SEPARATOR,
            )
            gap = S.RPT_COMPARE_GAP.format(
                delta=self.theme.markup(row.delta),
                dot=S.RPT_DOT_SEPARATOR,
                sample=self.theme.markup(row.sample),
            )
            if row.sparse:
                gap += S.RPT_DOT_SEPARATOR + S.RPT_SPARSE_TAG
            numbers: list[Flowable] = [
                self.theme.paragraph(values, C.RptText.BAR_VALUE),
                self.theme.paragraph(gap, C.RptText.CAPTION),
            ]
            data.append([title, Dumbbell(row), numbers])
        commands: list[Command] = [
            (S.RPT_TS_VALIGN, C.RPT_CELL_START, C.RPT_CELL_END, S.RPT_TS_MIDDLE),
            (S.RPT_TS_LEFT_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.ZERO),
            (S.RPT_TS_RIGHT_PADDING, C.RPT_CELL_START, (C.ONE, -C.ONE), C.RPT_PAD),
            (S.RPT_TS_RIGHT_PADDING, (C.TWO, C.ZERO), C.RPT_CELL_END, C.ZERO),
            (S.RPT_TS_TOP_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
            (S.RPT_TS_BOTTOM_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
            (
                S.RPT_TS_LINE_BELOW,
                (C.ZERO, C.ONE),
                (-C.ONE, -C.TWO),
                C.RPT_HAIRLINE,
                paint(S.RPT_HEX_RULE),
            ),
        ]
        table = Table(data, colWidths=widths, style=rows_style(commands))
        table.hAlign = S.RPT_TS_LEFT
        legend = Legend(
            self.theme,
            (
                LegendEntry(C.RptShape.CIRCLE, C.RptTone.TEAL, S.RPT_LEGEND_YOU),
                LegendEntry(C.RptShape.SQUARE, C.RptTone.SLATE, S.RPT_LEGEND_CROWD),
            ),
        )
        return self.assemble(block.heading, [[legend, table]], block.note)

    def coverage(self, block: CoverageBlock) -> list[Flowable]:
        if not block.rows:
            return []
        label = self.width * C.RPT_COVERAGE_LABEL_SHARE
        meter = self.width * C.RPT_COVERAGE_METER_SHARE
        text = (self.width - label - meter * C.TWO) / C.TWO
        widths = [label, meter, text, meter, text]
        data: list[list[object]] = [
            [
                S.EMPTY,
                self.bold(S.RPT_COVERAGE_READ, C.RptText.CAPTION),
                S.EMPTY,
                self.bold(S.RPT_COVERAGE_WATCH, C.RptText.CAPTION),
                S.EMPTY,
            ]
        ]
        for row in block.rows:
            data.append(
                [
                    self.para(row.label, C.RptText.BAR_LABEL),
                    *self.coverage_side(row.read_known, row.read_total),
                    *self.coverage_side(row.watch_known, row.watch_total),
                ]
            )
        commands: list[Command] = [
            (S.RPT_TS_VALIGN, C.RPT_CELL_START, C.RPT_CELL_END, S.RPT_TS_MIDDLE),
            (S.RPT_TS_SPAN, (C.ONE, C.ZERO), (C.TWO, C.ZERO)),
            (S.RPT_TS_SPAN, (C.THREE, C.ZERO), (C.FOUR, C.ZERO)),
            (S.RPT_TS_LEFT_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.ZERO),
            (S.RPT_TS_RIGHT_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_PAD),
            (S.RPT_TS_TOP_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
            (S.RPT_TS_BOTTOM_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
            (
                S.RPT_TS_LINE_BELOW,
                C.RPT_CELL_START,
                (-C.ONE, -C.TWO),
                C.RPT_HAIRLINE,
                paint(S.RPT_HEX_RULE),
            ),
        ]
        table = Table(data, colWidths=widths, style=rows_style(commands))
        table.hAlign = S.RPT_TS_LEFT
        return self.assemble(block.heading, [[table]], block.note)

    def coverage_side(self, known: int, total: int) -> list[object]:
        if not total:
            return [S.EMPTY, self.para(S.RPT_COVERAGE_EMPTY, C.RptText.CAPTION)]
        words = S.RPT_COVERAGE_CELL.format(known=known, total=total)
        return [Meter(known, total), self.para(words, C.RptText.CAPTION)]
