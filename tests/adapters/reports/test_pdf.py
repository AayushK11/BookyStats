from __future__ import annotations

from collections.abc import Iterator, Mapping
from functools import cache
from io import BytesIO
from typing import NamedTuple

import pytest
from pydantic import JsonValue
from pypdf import PageObject, PdfReader
from reportlab.lib.colors import Color

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.reports.blocks import safe_link
from bookystats.adapters.reports.pdf import render_pdf
from bookystats.adapters.reports.theme import paint
from bookystats.application.reader_report import build_reader_report
from bookystats.domain.reader_report import (
    Chapter,
    Link,
    ProseBlock,
    Quote,
    QuotesBlock,
    ReaderReport,
)
from tests.support.reader_library import library


class Run(NamedTuple):
    x: float
    y: float
    text: str
    font: str


@C.frozen_dataclass
class Rendered:
    report: ReaderReport
    payload: bytes
    reader: PdfReader
    texts: tuple[str, ...]
    declared: int


def _flat(text: str) -> str:
    return S.EMPTY.join(text.split())


def _read(payload: bytes) -> tuple[PdfReader, tuple[str, ...]]:
    reader = PdfReader(BytesIO(payload))
    return reader, tuple(_flat(page.extract_text()) for page in reader.pages)


@cache
def _rendered(read: int, watch: int) -> Rendered:
    lib = library(read, watch)
    report = build_reader_report(lib.data, lib.analysis, lib.recommendations, lib.quality)
    stream = BytesIO()
    declared = render_pdf(report, stream)
    reader, texts = _read(stream.getvalue())
    return Rendered(
        report=report, payload=stream.getvalue(), reader=reader, texts=texts, declared=declared
    )


def _runs(page: PageObject) -> list[Run]:
    found: list[Run] = []

    def visit(
        text: str,
        cm: list[float],
        tm: list[float],
        font: Mapping[str, object] | None,
        size: float,
    ) -> None:
        if text.strip():
            base = str((font or {}).get(S.RPT_TEST_BASE_FONT, S.EMPTY))
            x = tm[C.FOUR] * cm[C.ZERO] + cm[C.FOUR]
            y = tm[C.FIVE] * cm[C.THREE] + cm[C.FIVE]
            found.append(Run(x, y, text, base))

    page.extract_text(visitor_text=visit)
    return found


def _outline(reader: PdfReader) -> dict[str, int]:
    pages: dict[str, int] = {}

    def walk(items: list[object]) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                pages.setdefault(_flat(item.title), reader.get_destination_page_number(item))

    walk(reader.outline)
    return pages


def _contents(rendered: Rendered) -> dict[str, int]:
    lines: dict[int, list[Run]] = {}
    for run in _runs(rendered.reader.pages[C.ONE]):
        lines.setdefault(round(run.y), []).append(run)
    entries: dict[str, int] = {}
    for runs in lines.values():
        line = _flat(S.EMPTY.join(run.text for run in sorted(runs)))
        found = C.RPT_TEST_TOC_LINE.match(line)
        if found:
            entries[found.group(S.RPT_TEST_TITLE_KEY)] = int(found.group(S.RPT_TEST_PAGE_KEY))
    return entries


def _uris(reader: PdfReader) -> set[str]:
    found: set[str] = set()
    for page in reader.pages:
        for annotation in page.get(S.PDF_TEST_ANNOTATIONS, []):
            action = annotation.get_object().get(S.PDF_TEST_ACTION, {})
            if S.PDF_TEST_URI in action:
                found.add(str(action[S.PDF_TEST_URI]))
    return found


def _titles(value: JsonValue) -> Iterator[str]:
    if isinstance(value, list):
        for item in value:
            yield from _titles(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == S.RPT_TEST_TITLE_KEY and isinstance(item, str):
                yield item
            else:
                yield from _titles(item)


def _quotes(report: ReaderReport) -> list[Quote]:
    return [
        quote
        for chapter in report.chapters
        for block in chapter.blocks
        if isinstance(block, QuotesBlock)
        for quote in block.quotes
    ]


def _with_chapter(chapter: Chapter) -> tuple[PdfReader, tuple[str, ...]]:
    base = _rendered(*C.RPT_TEST_SMALL).report
    report = base.model_copy(update={S.RPT_TEST_CHAPTERS_FIELD: (chapter,)})
    stream = BytesIO()
    render_pdf(report, stream)
    return _read(stream.getvalue())


def test_page_counts_follow_the_evidence_without_padding() -> None:
    rich = _rendered(*C.RPT_TEST_RICH).declared
    small = _rendered(*C.RPT_TEST_SMALL).declared
    void = _rendered(*C.RPT_TEST_VOID).declared
    low, high = C.RPT_TEST_RICH_PAGES
    assert low <= rich <= high
    assert small <= C.RPT_TEST_SMALL_PAGES_MAX
    assert void <= C.RPT_TEST_EMPTY_PAGES_MAX
    assert void < small < rich


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_SIZES)
def test_declared_pages_match_the_document_and_none_is_blank(read: int, watch: int) -> None:
    rendered = _rendered(read, watch)
    assert rendered.declared == len(rendered.reader.pages) == len(rendered.texts)
    assert all(len(text) >= C.RPT_TEST_MIN_PAGE_CHARS for text in rendered.texts[C.ONE :])


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_SIZES)
def test_text_stays_inside_the_page_frame(read: int, watch: int) -> None:
    slack = C.RPT_TEST_FRAME_SLACK
    left = C.PDF_MARGIN - slack
    right = C.PDF_PAGE_WIDTH - C.PDF_MARGIN + slack
    bottom = C.RPT_MARGIN_BOTTOM - slack
    top = C.PDF_PAGE_HEIGHT - C.RPT_MARGIN_TOP + slack
    header = C.PDF_PAGE_HEIGHT - C.RPT_HEADER_DROP
    for index, page in enumerate(_rendered(read, watch).reader.pages):
        for run in _runs(page):
            assert left <= run.x <= right
            if index:
                running = abs(run.y - header) <= slack or abs(run.y - C.RPT_FOOTER_RISE) <= slack
                assert running or bottom <= run.y <= top


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_SIZES)
def test_cover_is_unnumbered_and_every_other_page_has_its_number(read: int, watch: int) -> None:
    rendered = _rendered(read, watch)
    assert _flat(rendered.report.cover.title) in rendered.texts[C.ZERO]
    for number, text in enumerate(rendered.texts[C.ONE :], start=C.TWO):
        assert _flat(S.RPT_PAGE_NUMBER.format(page=number)) in text


def test_contents_and_chart_key_appear_only_when_the_evidence_needs_them() -> None:
    front = _rendered(*C.RPT_TEST_RICH).texts[C.ONE]
    assert _flat(S.RPT_TOC_TITLE) in front
    assert _flat(S.RPT_KEY_HEADING) in front
    whole = S.EMPTY.join(_rendered(*C.RPT_TEST_VOID).texts)
    assert _flat(S.RPT_TOC_TITLE) not in whole
    assert _flat(S.RPT_KEY_HEADING) not in whole


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_CONTENT_SIZES)
def test_outline_and_printed_contents_lead_to_the_chapters(read: int, watch: int) -> None:
    rendered = _rendered(read, watch)
    outline = _outline(rendered.reader)
    contents = _contents(rendered)
    for chapter in rendered.report.chapters:
        title = _flat(chapter.title)
        assert title in rendered.texts[outline[title]]
        assert contents[title] == outline[title] + C.ONE
        assert contents[title] <= rendered.declared


def test_document_metadata_and_language_describe_the_report() -> None:
    rendered = _rendered(*C.RPT_TEST_SMALL)
    metadata = rendered.reader.metadata
    assert metadata is not C.NONE
    assert metadata.title == rendered.report.cover.title
    assert metadata.author == S.PDF_AUTHOR
    assert metadata.subject == rendered.report.cover.subtitle
    assert metadata[S.RPT_TEST_KEYWORDS_KEY] == S.RPT_PDF_KEYWORDS
    assert rendered.reader.trailer[S.RPT_TEST_ROOT][S.RPT_TEST_LANG] == S.RPT_PDF_LANGUAGE


def test_only_embedded_fonts_draw_text_and_no_images_are_used() -> None:
    reader = _rendered(*C.RPT_TEST_RICH).reader
    drawn = {run.font for page in reader.pages for run in _runs(page)}
    assert drawn
    assert not [font for font in drawn if S.RPT_TEST_STANDARD_FONT in font]
    for page in reader.pages:
        assert not len(page.images)
        for font in page[S.PDF_TEST_RESOURCES][S.PDF_TEST_FONT_RESOURCE].values():
            resolved = font.get_object()
            if S.RPT_TEST_STANDARD_FONT not in str(resolved.get(S.RPT_TEST_BASE_FONT)):
                assert S.PDF_TEST_FONT_FILE in resolved[S.PDF_TEST_DESCRIPTOR]


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_SIZES)
def test_external_links_are_exactly_the_safe_quote_references(read: int, watch: int) -> None:
    rendered = _rendered(read, watch)
    expected = {quote.link.url for quote in _quotes(rendered.report) if quote.link}
    uris = _uris(rendered.reader)
    assert uris == expected
    assert all(safe_link(uri) for uri in uris)
    if (read, watch) == C.RPT_TEST_RICH:
        assert expected


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_SIZES)
def test_titles_and_quotes_reach_the_page_whole(read: int, watch: int) -> None:
    rendered = _rendered(read, watch)
    page_text = S.EMPTY.join(rendered.texts)
    titles = list(_titles(rendered.report.model_dump(mode=S.JSON)))
    assert titles
    assert [title for title in titles if _flat(title) not in page_text] == []
    assert [
        quote.text for quote in _quotes(rendered.report) if _flat(quote.text) not in page_text
    ] == []
    assert S.RPT_TEST_FALLBACK_MARK not in page_text


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_SIZES)
def test_no_supplemental_date_text_reaches_the_pdf(read: int, watch: int) -> None:
    text = S.EMPTY.join(_rendered(read, watch).texts).casefold()
    assert [term for term in C.RPT_TEST_DATE_TERMS if _flat(term).casefold() in text] == []


def test_unsupported_characters_are_flagged_instead_of_silently_dropped() -> None:
    chapter = Chapter(
        key=S.RPT_TEST_GLYPH_CHAPTER,
        title=S.RPT_TEST_GLYPH_TITLE,
        blocks=(ProseBlock(paragraphs=(S.RPT_TEST_GLYPH_TEXT,)),),
    )
    _, texts = _with_chapter(chapter)
    text = S.EMPTY.join(texts)
    assert _flat(S.RPT_TEST_GLYPH_CODE) in text
    assert S.RPT_TEST_EMOJI not in text
    assert _flat(S.RPT_FALLBACK_NOTE.format(count=C.ONE)) in text


def test_only_allow_listed_links_become_annotations() -> None:
    safe = S.RPT_TEST_PUBLIC_URL.format(work_id=C.ONE)
    unsafe = S.RPT_TEST_PRIVATE_URL.format(work_id=C.ONE)
    quotes = tuple(
        Quote(
            text=S.RPT_TEST_WHOLE,
            cue=S.RPT_TEST_CUE,
            title=S.RPT_TEST_GLYPH_TITLE,
            byline=S.RPT_TEST_NEW_AUTHOR.format(index=C.ONE),
            link=Link(label=S.RPT_TEST_WORD, url=url),
        )
        for url in (safe, unsafe)
    )
    chapter = Chapter(
        key=S.RPT_TEST_GLYPH_CHAPTER,
        title=S.RPT_TEST_GLYPH_TITLE,
        blocks=(QuotesBlock(quotes=quotes),),
    )
    reader, _ = _with_chapter(chapter)
    assert _uris(reader) == {safe}


@pytest.mark.parametrize(S.RPT_TEST_URL, C.RPT_TEST_UNSAFE_URLS)
def test_links_outside_the_public_allow_list_are_refused(url: str) -> None:
    assert not safe_link(url)


def test_rendering_is_byte_for_byte_repeatable() -> None:
    rendered = _rendered(*C.RPT_TEST_SMALL)
    again = BytesIO()
    assert render_pdf(rendered.report, again) == rendered.declared
    assert again.getvalue() == rendered.payload


def _channel(value: float) -> float:
    if value <= C.RPT_TEST_LINEAR_CUTOFF:
        return value / C.RPT_TEST_LINEAR_DIVISOR
    return float(((value + C.RPT_TEST_GAMMA_OFFSET) / C.RPT_TEST_GAMMA_SCALE) ** C.RPT_TEST_GAMMA)


def _luminance(color: Color) -> float:
    red, green, blue = C.RPT_TEST_LUMA_WEIGHTS
    return red * _channel(color.red) + green * _channel(color.green) + blue * _channel(color.blue)


def _contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_luminance(paint(foreground)), _luminance(paint(background))), reverse=C.TRUE
    )
    return (lighter + C.RPT_TEST_FLARE) / (darker + C.RPT_TEST_FLARE)


@pytest.mark.parametrize(S.RPT_TEST_PAIR_ARGS, C.RPT_TEST_TEXT_PAIRS)
def test_text_colors_are_readable_on_their_backgrounds(foreground: str, background: str) -> None:
    assert _contrast(foreground, background) >= C.RPT_TEST_TEXT_CONTRAST


@pytest.mark.parametrize(S.RPT_TEST_PAIR_ARGS, C.RPT_TEST_GRAPHIC_PAIRS)
def test_chart_colors_stand_out_from_the_page(foreground: str, background: str) -> None:
    assert _contrast(foreground, background) >= C.RPT_TEST_GRAPHIC_CONTRAST
