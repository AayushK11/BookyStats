from __future__ import annotations

from typing import BinaryIO, NamedTuple

from reportlab.platypus import (
    Flowable,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.reports.blocks import Composer, ReadingGroup
from bookystats.adapters.reports.charts import BarCell, Dumbbell, Legend, LegendEntry, Skyline
from bookystats.adapters.reports.document import ReportDocument
from bookystats.adapters.reports.theme import Theme
from bookystats.domain.reader_report import (
    BarRow,
    BarsBlock,
    Chapter,
    CompareBlock,
    CompareRow,
    ReaderReport,
    TilesBlock,
)


class Marks(NamedTuple):
    solid: bool
    sparse: bool
    unknown: bool
    compare: bool


def marks_of(report: ReaderReport) -> Marks:
    blocks = [block for chapter in report.chapters for block in chapter.blocks]
    bars = [row for block in blocks if isinstance(block, BarsBlock) for row in block.rows]
    pairs = [row for block in blocks if isinstance(block, CompareBlock) for row in block.rows]
    skyline = report.cover.skyline
    return Marks(
        solid=any(row.value is not C.NONE and not row.sparse for row in bars)
        or any(bar.height is not C.NONE for bar in skyline),
        sparse=any(row.sparse for row in bars) or any(row.sparse for row in pairs),
        unknown=any(row.value is C.NONE for row in bars)
        or any(bar.height is C.NONE for bar in skyline),
        compare=bool(pairs),
    )


def cover_story(report: ReaderReport, composer: Composer) -> list[Flowable]:
    cover = report.cover
    flows: list[Flowable] = list(composer.tile_grid(cover.heroes, hero=C.TRUE))
    flows.append(Spacer(C.ONE, C.RPT_COVER_GAP))
    flows.append(composer.para(S.RPT_COVER_INVITATION, C.RptText.LEAD))
    if cover.skyline:
        flows.append(Spacer(C.ONE, C.RPT_COVER_GAP))
        flows.append(Skyline(cover.skyline))
        if cover.skyline_caption:
            flows.append(Spacer(C.ONE, C.RPT_GAP))
            flows.append(composer.para(cover.skyline_caption, C.RptText.CAPTION))
        if cover.legend:
            flows.append(Spacer(C.ONE, C.RPT_GAP))
            entries = tuple(
                LegendEntry(C.RptShape.SQUARE, swatch.tone, swatch.label) for swatch in cover.legend
            )
            flows.append(Legend(composer.theme, entries))
    flows.append(NextPageTemplate(S.RPT_TEMPLATE_BODY))
    flows.append(PageBreak())
    return flows


def key_story(marks: Marks, composer: Composer, level: int) -> list[Flowable]:
    rows: list[tuple[Flowable, str]] = []
    sample = BarRow(label=S.EMPTY, value=C.RPT_SAMPLE_BAR)
    if marks.solid:
        rows.append((BarCell(sample, C.RptBarStyle.HORIZONTAL, float(C.ONE)), S.RPT_KEY_SOLID))
    if marks.sparse:
        faint = BarRow(label=S.EMPTY, value=C.RPT_SAMPLE_SPARSE, sparse=C.TRUE)
        rows.append((BarCell(faint, C.RptBarStyle.HORIZONTAL, float(C.ONE)), S.RPT_KEY_SPARSE))
    if marks.unknown:
        blank = BarRow(label=S.EMPTY)
        rows.append((BarCell(blank, C.RptBarStyle.HORIZONTAL, float(C.ONE)), S.RPT_KEY_UNKNOWN))
    if marks.compare:
        pair = CompareRow(
            title=S.EMPTY,
            byline=S.EMPTY,
            personal=C.RPT_SAMPLE_PERSONAL,
            community=C.RPT_SAMPLE_COMMUNITY,
            personal_text=S.EMPTY,
            community_text=S.EMPTY,
            delta=S.EMPTY,
            sample=S.EMPTY,
        )
        rows.append((Dumbbell(pair), S.RPT_KEY_COMPARE))
    if not rows:
        return []
    data = [[chart, composer.para(text, C.RptText.BODY)] for chart, text in rows]
    commands = [
        (S.RPT_TS_VALIGN, C.RPT_CELL_START, C.RPT_CELL_END, S.RPT_TS_MIDDLE),
        (S.RPT_TS_LEFT_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.ZERO),
        (S.RPT_TS_RIGHT_PADDING, C.RPT_CELL_START, (C.ZERO, -C.ONE), C.RPT_PAD * C.TWO),
        (S.RPT_TS_TOP_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
        (S.RPT_TS_BOTTOM_PADDING, C.RPT_CELL_START, C.RPT_CELL_END, C.RPT_BAR_PAD),
    ]
    table = Table(
        data,
        colWidths=[C.RPT_KEY_COLUMN, composer.width - C.RPT_KEY_COLUMN],
        style=TableStyle(commands),
    )
    table.hAlign = S.RPT_TS_LEFT
    heading = composer.heading(S.RPT_KEY_HEADING, C.RptText.H2, level)
    intro = composer.para(S.RPT_KEY_INTRO, C.RptText.NOTE)
    return [KeepTogether([heading, intro, table])]


def front_story(report: ReaderReport, composer: Composer) -> list[Flowable]:
    flows: list[Flowable] = []
    listed = len(report.chapters) >= C.RPT_TOC_MINIMUM
    if listed:
        flows.extend(
            composer.header(S.RPT_TOC_KICKER, S.RPT_TOC_TITLE, S.RPT_TOC_INTRO, listed=C.FALSE)
        )
        toc = TableOfContents()
        toc.levelStyles = [composer.theme.styles[C.RptText.TOC]]
        toc.dotsMinLevel = C.ZERO
        flows.append(toc)
    flows.extend(key_story(marks_of(report), composer, C.ONE if listed else C.ZERO))
    if flows:
        flows.append(PageBreak())
    return flows


def about_story(report: ReaderReport, composer: Composer) -> list[Flowable]:
    flows = composer.header(S.RPT_ABOUT_KICKER, S.RPT_ABOUT_TITLE, S.RPT_ABOUT_INTRO)
    sources = [composer.para(text, C.RptText.BULLET, S.RPT_BULLET) for text in report.fine_print]
    if sources:
        flows = [ReadingGroup([*flows, sources[C.ZERO]]), *sources[C.ONE :]]
    notes = [S.RPT_COMPANION_NOTE, S.RPT_UNTAGGED]
    if composer.theme.fallbacks:
        notes.append(S.RPT_FALLBACK_NOTE.format(count=composer.theme.fallbacks))
    flows.append(
        KeepTogether(
            [
                composer.heading(S.RPT_READING_NOTES_HEAD, C.RptText.H2, C.ONE),
                *(composer.para(text, C.RptText.NOTE) for text in notes),
            ]
        )
    )
    return flows


def display_chapter(chapter: Chapter, report: ReaderReport) -> Chapter:
    if chapter.key != S.RPT_CHAPTER_GLANCE:
        return chapter
    covered = {
        (C.RPT_COVER_TILE_LABELS.get(hero.label, hero.label), hero.value)
        for hero in report.cover.heroes
    }
    blocks = tuple(
        block.model_copy(
            update={
                S.RPT_TILES_FIELD: tuple(
                    tile for tile in block.tiles if (tile.label, tile.value) not in covered
                )
            }
        )
        if isinstance(block, TilesBlock)
        else block
        for block in chapter.blocks
    )
    return chapter.model_copy(update={S.RPT_BLOCKS_FIELD: blocks, S.RPT_INTRO_FIELD: S.EMPTY})


def render_pdf(report: ReaderReport, stream: BinaryIO) -> int:
    theme = Theme()
    document = ReportDocument(stream, report, theme)
    composer = Composer(theme, document)
    story: list[Flowable] = [
        *cover_story(report, composer),
        *front_story(report, composer),
    ]
    for number, chapter in enumerate(report.chapters, start=C.ONE):
        story.extend(composer.chapter(display_chapter(chapter, report), number))
    story.extend(about_story(report, composer))
    document.multiBuild(story)
    return int(document.page)
