from __future__ import annotations

import inspect
from collections import Counter
from collections.abc import Iterator
from functools import cache

import pytest
from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import reader_context, reader_insights, reader_outlook
from bookystats.application import reader_profile as profile
from bookystats.application import reader_report as assembly
from bookystats.application import report_format as F
from bookystats.application.reader_context import Context, make_context
from bookystats.application.reader_report import build_reader_report, cover
from bookystats.domain import reader_report as model
from bookystats.domain.reader import build_reader_summary
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
    Stat,
    TilesBlock,
    manifest_digest,
)
from bookystats.domain.recommendation_evaluation import RecommendationEvaluation
from tests.support.reader_library import library

_REPORT_MODULES = (
    reader_context,
    reader_insights,
    reader_outlook,
    profile,
    assembly,
    F,
    model,
)


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


def _tiles(chapter: Chapter | None) -> dict[str, Stat]:
    blocks = () if chapter is C.NONE else chapter.blocks
    return {
        tile.label: tile
        for block in blocks
        if isinstance(block, TilesBlock)
        for tile in block.tiles
    }


def _facts(chapter: Chapter | None) -> dict[str, str]:
    blocks = () if chapter is C.NONE else chapter.blocks
    return {
        fact.headline: fact.body
        for block in blocks
        if isinstance(block, FactsBlock)
        for fact in block.facts
    }


def _with_summary(read: int, watch: int, **changes: object) -> Context:
    lib = library(read, watch)
    ctx = make_context(lib.data, lib.analysis, lib.recommendations, lib.quality)
    return ctx._replace(summary=ctx.summary.model_copy(update=changes))


def test_rating_tiers_compare_with_the_usual_rating_everywhere() -> None:
    lib = library(*C.RPT_TEST_RICH)
    summary = build_reader_summary(lib.data)
    usual = summary.usual_rating
    assert usual is not C.NONE
    report = _built(*C.RPT_TEST_RICH)
    rating = F.star_count(usual)
    chapters = {chapter.key: chapter for chapter in report.chapters}
    tile = _tiles(chapters[S.RPT_CHAPTER_GLANCE])[S.RPT_TILE_STANDOUT]
    assert tile.value == F.percent(summary.standout, summary.rated)
    assert tile.detail == S.RPT_TILE_STANDOUT_DETAIL.format(
        part=F.count(summary.standout), total=F.count(summary.rated), rating=rating
    )
    tones = Counter(bar.tone for bar in report.cover.skyline)
    assert report.cover.skyline
    assert (tones[C.RptTone.TEAL], tones[C.RptTone.SLATE], tones[C.RptTone.AMBER]) == (
        summary.standout,
        summary.solid,
        summary.below_usual,
    )
    labels = [swatch.label for swatch in report.cover.legend]
    assert labels == [
        S.RPT_LEGEND_STANDOUT,
        S.RPT_LEGEND_SOLID,
        S.RPT_LEGEND_BELOW,
        S.RPT_LEGEND_UNRATED,
    ]
    assert S.RPT_SKYLINE_USUAL.format(rating=rating) in report.cover.skyline_caption
    histogram = next(
        block
        for _, block in _blocks(report)
        if isinstance(block, BarsBlock) and block.heading == S.RPT_HISTOGRAM_HEADING
    )
    for row in histogram.rows:
        value = float(row.label)
        expected = (
            C.RptTone.TEAL
            if value > usual
            else C.RptTone.SLATE
            if value == usual
            else C.RptTone.AMBER
        )
        assert row.tone == expected
    assert S.RPT_HISTOGRAM_TONES in histogram.note
    body = S.RPT_TIERS_BODY.format(
        rating=rating,
        rated=F.books(summary.rated),
        standout=F.count(summary.standout),
        solid=F.count(summary.solid),
        below=F.count(summary.below_usual),
    )
    assert _facts(chapters[S.RPT_CHAPTER_RATINGS])[S.RPT_FACT_TIERS] == body


def test_tied_and_unknown_usual_ratings_are_disclosed_not_guessed() -> None:
    tied = _with_summary(*C.RPT_TEST_RICH, **{S.RPT_TEST_TIED_FIELD: C.RPT_TEST_TIED_USUAL})
    assert S.RPT_TIERS_TIED in _facts(profile.ratings(tied))[S.RPT_FACT_TIERS]
    lowest = F.star_count(tied.summary.usual_rating or C.ZERO)
    assert S.RPT_SKYLINE_USUAL_TIED.format(rating=lowest) in cover(tied).skyline_caption
    unknown = _with_summary(*C.RPT_TEST_RICH, **{S.RPT_TEST_USUAL_FIELD: C.NONE})
    assert S.RPT_TILE_STANDOUT not in _tiles(profile.glance(unknown))
    assert S.RPT_FACT_TIERS not in _facts(profile.ratings(unknown))
    shown = cover(unknown)
    assert [swatch.label for swatch in shown.legend] == [S.RPT_LEGEND_UNRATED]
    assert {bar.tone for bar in shown.skyline} == {C.RptTone.GREY}
    assert shown.skyline_caption == S.RPT_SKYLINE_CAPTION


def test_report_never_reads_or_shows_supplemental_dates() -> None:
    sources = S.EMPTY.join(inspect.getsource(module) for module in _REPORT_MODULES).casefold()
    shown = S.EMPTY.join(_all_texts(_built(*C.RPT_TEST_RICH))).casefold()
    assert [term for term in C.RPT_TEST_DATE_TERMS if term in sources or term in shown] == []


def test_implausible_values_are_left_out_and_disclosed() -> None:
    texts = _all_texts(_built(*C.RPT_TEST_RICH))
    assert not [text for text in texts if any(bad in text for bad in C.RPT_TEST_IMPLAUSIBLE)]
    note = S.RPT_IMPLAUSIBLE_PAGES.format(
        low=C.RPT_MIN_PAGES, high=F.count(C.RPT_MAX_PAGES), books=F.books(C.TWO)
    )
    assert any(note in text for text in texts)
    plausible = F.books(C.RPT_TEST_RICH_READ - C.THREE)
    assert S.RPT_TILE_ERAS_DETAIL.format(books=plausible) in texts


def test_long_novels_remain_eligible_and_missing_lengths_do_not_claim_to_be_short() -> None:
    lib = library(*C.RPT_TEST_RICH)
    ctx = make_context(lib.data, lib.analysis, lib.recommendations, lib.quality)
    original = ctx.read[C.ZERO]
    book = original.model_copy(
        update={
            S.PAGE_COUNT: C.RPT_TEST_LONG_EDITION_PAGES,
            S.AN_CALC_FIELD_STATES_FIELD: {
                **original.field_states,
                S.PAGE_COUNT: C.FieldState.PRESENT,
            },
        }
    )
    changed = ctx._replace(read=(book, *ctx.read[C.ONE :]))
    assert changed.plausible_pages(book) == C.RPT_TEST_LONG_EDITION_PAGES
    chapter = profile.shape(changed)
    assert chapter is not C.NONE
    longest = next(
        block
        for block in chapter.blocks
        if isinstance(block, BooksBlock) and block.heading == S.RPT_LONGEST_HEADING
    )
    assert any(
        item.title == F.display_title(book.title)
        and item.detail == F.pages(C.RPT_TEST_LONG_EDITION_PAGES)
        for group in longest.groups
        for item in group.books
    )
    assert longest.note == S.RPT_LONGEST_NOTE.format(
        known=F.count(profile.pages_known(changed)), read=F.count(changed.summary.read)
    )
    assert any(
        block.note == S.RPT_FACTS_LENGTH_NOTE
        for _, block in _blocks(_built(*C.RPT_TEST_RICH))
        if isinstance(block, FactsBlock)
    )


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


def test_shortlist_explains_same_cohort_shadow_evaluation_without_claiming_activation() -> None:
    lib = library(*C.RPT_TEST_RICH)
    evaluation = RecommendationEvaluation(
        status=S.REC2_AVAILABLE,
        reason=C.NONE,
        cohort_size=C.REC2_MIN_RATED,
        mean_mae=C.ONE,
        simple_length_mae=C.TWO,
        current_heuristic_mae=C.THREE,
        shadow_candidate_mae=C.FOUR,
    )
    recommendations = lib.recommendations.model_copy(update={S.REC2_EVALUATION: evaluation})
    report = build_reader_report(lib.data, lib.analysis, recommendations, lib.quality)
    texts = _all_texts(report)
    assert S.REC3_DIVERSITY_NOTE in texts
    assert S.REC2_EVALUATION_SCOPE in texts
    assert S.REC2_SHADOW_POLICY in texts
    assert (
        S.REC2_PDF_SUMMARY.format(
            count=C.REC2_MIN_RATED,
            mean=F.trimmed(C.ONE),
            simple=F.trimmed(C.TWO),
            current=F.trimmed(C.THREE),
            shadow=F.trimmed(C.FOUR),
            fallback=C.ZERO,
            shadow_fallback=C.ZERO,
        )
        in texts
    )


def test_shortlist_prints_verified_series_context_and_unknown_rating_error_is_not_zero() -> None:
    lib = library(*C.RPT_TEST_RICH)
    item = lib.recommendations.shortlist[C.ZERO].model_dump(mode=S.JSON)
    item[S.REC2_SERIES_CONTEXT] = [{S.REC2_EXPLANATION: S.REC2_NEXT_NOTE}]
    shown = reader_outlook.shortlist_item(C.ONE, item, {})
    assert shown is not C.NONE
    assert S.REC2_NEXT_NOTE in shown.lines
    assert reader_outlook.rating_error({}, S.REC2_MEAN_MAE) == S.RPT_UNKNOWN
