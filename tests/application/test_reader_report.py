from __future__ import annotations

from collections.abc import Iterator
from functools import cache

import pytest
from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import report_format as F
from bookystats.application.reader_report import build_reader_report
from bookystats.domain.reader_report import (
    BarsBlock,
    Block,
    BooksBlock,
    CalloutBlock,
    Chapter,
    CompareBlock,
    FactsBlock,
    ProseBlock,
    QuotesBlock,
    ReaderReport,
    TilesBlock,
    manifest_digest,
)
from tests.support.reader_library import library


@cache
def _built(read: int, watch: int) -> ReaderReport:
    lib = library(read, watch)
    return build_reader_report(lib.data, lib.analysis, lib.recommendations, lib.quality)


def _texts(value: JsonValue) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _texts(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in C.RPT_TEST_MACHINE_FIELDS:
                yield from _texts(item)


def _all_texts(report: ReaderReport) -> list[str]:
    return list(_texts(report.model_dump(mode=S.JSON)))


def _blocks(report: ReaderReport) -> Iterator[tuple[Chapter, Block]]:
    for chapter in report.chapters:
        for block in chapter.blocks:
            yield chapter, block


def _items(block: Block) -> tuple[object, ...]:
    match block:
        case ProseBlock() | CalloutBlock():
            return block.paragraphs
        case TilesBlock():
            return block.tiles
        case FactsBlock():
            return block.facts
        case QuotesBlock():
            return block.quotes
        case BooksBlock():
            return block.groups
        case _:
            return block.rows


def test_story_follows_the_reader_first_order() -> None:
    rich = [chapter.key for chapter in _built(*C.RPT_TEST_RICH).chapters]
    assert rich == list(C.RPT_TEST_CHAPTER_ORDER)
    small = [chapter.key for chapter in _built(*C.RPT_TEST_SMALL).chapters]
    assert small == [key for key in C.RPT_TEST_CHAPTER_ORDER if key in small]


def test_report_carries_verified_provenance_and_round_trips() -> None:
    lib = library(*C.RPT_TEST_RICH)
    report = _built(*C.RPT_TEST_RICH)
    assert report.model_version == C.RPT_MODEL_VERSION
    assert report.analysis_report_id == lib.analysis.report_id
    assert report.as_of == lib.analysis.as_of
    assert report.calculation_version == lib.data.manifest.calculation_version
    assert report.manifest_digest == manifest_digest(lib.analysis.manifest)
    changed = lib.analysis.manifest.model_copy(update={S.AN_ACCOUNT_FINGERPRINT: S.DIFFERENT_BOOK})
    assert manifest_digest(changed) != report.manifest_digest
    assert ReaderReport.model_validate_json(report.model_dump_json()) == report


def test_report_is_deterministic_and_independent_of_input_order() -> None:
    lib = library(*C.RPT_TEST_RICH)
    shuffled = lib.data.model_copy(update={S.RPT_TEST_BOOKS_FIELD: tuple(reversed(lib.data.books))})
    again = build_reader_report(shuffled, lib.analysis, lib.recommendations, lib.quality)
    assert again == _built(*C.RPT_TEST_RICH)


def test_model_and_json_inputs_build_the_same_report() -> None:
    lib = library(*C.RPT_TEST_SMALL)
    plain = build_reader_report(
        lib.data,
        lib.analysis,
        lib.recommendations.model_dump(mode=S.JSON),
        lib.quality.model_dump(mode=S.JSON),
    )
    assert plain == _built(*C.RPT_TEST_SMALL)


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_SIZES)
def test_no_formatting_artifacts_reach_the_reader(read: int, watch: int) -> None:
    texts = _all_texts(_built(read, watch))
    assert texts
    assert not [text for text in texts if C.RPT_TEST_ARTIFACTS.search(text)]


@pytest.mark.parametrize(S.RPT_TEST_VALUE, C.RPT_TEST_NUMBERS)
def test_numbers_never_gain_padding_or_negative_zero(value: float) -> None:
    text = F.trimmed(value)
    assert not C.RPT_TEST_PADDED.search(text)
    assert text != S.RPT_TEST_NEGATIVE_ZERO
    assert abs(float(text) - value) <= C.RPT_TEST_TOLERANCE


def test_percent_never_overstates_the_edges() -> None:
    whole = S.RPT_PERCENT.format(value=C.RPT_PERCENT_SCALE)
    assert F.percent(C.RPT_TEST_ALL, C.RPT_TEST_ALL) == whole
    assert F.percent(C.RPT_TEST_ALMOST, C.RPT_TEST_ALL) != whole
    assert F.percent(C.ONE, C.RPT_TEST_ALL) == S.RPT_PERCENT_UNDER_ONE
    assert F.percent(C.ONE, C.ZERO) == S.RPT_UNKNOWN


def test_shortening_never_cuts_inside_a_word() -> None:
    shortened = C.ZERO
    for limit in (C.RPT_TEST_LIMIT, C.RPT_TITLE_LIMIT):
        for text in (*C.RPT_TEST_TITLES, C.RPT_TEST_RUNON):
            short = F.shorten(text, limit)
            if short == text:
                continue
            shortened += C.ONE
            kept = short.removesuffix(S.RPT_ELLIPSIS)
            assert short.endswith(S.RPT_ELLIPSIS)
            assert text.startswith(kept)
            assert not text[len(kept)].isalnum()
    assert shortened >= C.TWO


def test_excerpts_keep_whole_words_and_mark_real_omissions() -> None:
    source = S.CONTENT_ANALYSIS_TEST_TEXT
    cut = F.word_safe_excerpt(S.RPT_TEST_MIDWORD, S.RPT_TEST_CUE, source)
    assert cut == S.RPT_ELLIPSIS + S.RPT_TEST_WHOLE + S.RPT_ELLIPSIS
    assert F.word_safe_excerpt(S.RPT_TEST_MIDWORD, S.RPT_TEST_PARTIAL_CUE, source) is C.NONE


def test_every_quote_is_whole_words_from_the_description() -> None:
    quotes = [
        quote
        for _, block in _blocks(_built(*C.RPT_TEST_RICH))
        if isinstance(block, QuotesBlock)
        for quote in block.quotes
    ]
    assert quotes
    source = S.CONTENT_ANALYSIS_TEST_TEXT
    for quote in quotes:
        segments = [part.strip() for part in quote.text.split(S.RPT_ELLIPSIS) if part.strip()]
        assert segments
        for segment in segments:
            start = source.find(segment)
            end = start + len(segment)
            assert start >= C.ZERO
            assert start == C.ZERO or not source[start - C.ONE].isalnum()
            assert end == len(source) or not source[end].isalnum()
        before = source[: source.find(segments[C.ZERO])].rstrip()
        starts_clean = not before or before.endswith(C.RPT_SENTENCE_END)
        assert quote.text.startswith(S.RPT_ELLIPSIS) or starts_clean
        assert quote.text.endswith(S.RPT_ELLIPSIS) or segments[-C.ONE].endswith(C.RPT_SENTENCE_END)
        assert quote.cue.casefold() in quote.text.casefold()


@pytest.mark.parametrize(S.RPT_TEST_URL, C.RPT_TEST_SAFE_URLS)
def test_public_urls_become_human_links(url: str) -> None:
    link = F.human_link(url)
    assert link is not C.NONE
    assert link.url.startswith(S.RPT_HTTPS)
    assert not link.url.endswith(S.RPT_JSON_SUFFIX)
    assert S.RPT_TEST_API_HOST not in link.url


@pytest.mark.parametrize(S.RPT_TEST_URL, C.RPT_TEST_REJECTED_URLS)
def test_untrusted_urls_never_become_links(url: str) -> None:
    assert F.human_link(url) is C.NONE


def test_links_are_rebuilt_without_ports() -> None:
    link = F.human_link(S.RPT_TEST_PORT_URL)
    assert link is not C.NONE
    assert S.RPT_TEST_PORT_MARK not in link.url


def test_community_comparisons_stay_in_their_own_chapter() -> None:
    report = _built(*C.RPT_TEST_RICH)
    holders = {chapter.key for chapter, block in _blocks(report) if isinstance(block, CompareBlock)}
    assert holders == {S.RPT_CHAPTER_COMMUNITY}
    community = next(chapter for chapter in report.chapters if chapter.key in holders)
    assert any(isinstance(block, CalloutBlock) for block in community.blocks)
    ratings = next(chapter for chapter in report.chapters if chapter.key == S.RPT_CHAPTER_RATINGS)
    assert S.RPT_RATINGS_INTRO in _texts(ratings.model_dump(mode=S.JSON))


def test_unknown_and_sparse_samples_stay_visible() -> None:
    rows = [
        row
        for _, block in _blocks(_built(*C.RPT_TEST_RICH))
        if isinstance(block, BarsBlock)
        for row in block.rows
    ]
    assert any(row.sparse for row in rows)
    unknown = [row for row in rows if row.value is C.NONE]
    assert unknown
    assert all(row.caption == S.RPT_UNKNOWN_CAPTION for row in unknown)


def test_implausible_values_are_left_out_and_disclosed() -> None:
    texts = _all_texts(_built(*C.RPT_TEST_RICH))
    assert not [text for text in texts if any(bad in text for bad in C.RPT_TEST_IMPLAUSIBLE)]
    note = S.RPT_IMPLAUSIBLE_PAGES.format(
        low=C.RPT_MIN_PAGES, high=F.count(C.RPT_MAX_PAGES), books=F.books(C.TWO)
    )
    assert any(note in text for text in texts)
    plausible = F.books(C.RPT_TEST_RICH_READ - C.THREE)
    assert S.RPT_TILE_ERAS_DETAIL.format(books=plausible) in texts


def test_empty_library_gets_one_honest_page_of_content_not_padding() -> None:
    report = _built(*C.RPT_TEST_VOID)
    assert [chapter.key for chapter in report.chapters] == [S.RPT_CHAPTER_EMPTY]
    assert not report.cover.heroes
    assert not report.cover.skyline


@pytest.mark.parametrize(S.RPT_TEST_SIZE_ARGS, C.RPT_TEST_SIZES)
def test_no_chapter_or_block_is_empty_padding(read: int, watch: int) -> None:
    report = _built(read, watch)
    assert report.chapters
    for chapter in report.chapters:
        assert chapter.blocks
        assert all(_items(block) for block in chapter.blocks)
