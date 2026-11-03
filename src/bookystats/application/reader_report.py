from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import reader_insights as insights
from bookystats.application import reader_outlook as outlook
from bookystats.application import reader_profile as profile
from bookystats.application import report_format as F
from bookystats.application.reader_context import Context, make_context, tone_of
from bookystats.domain.analytics import AnalysisBook, AnalysisInput, AnalyticsReport
from bookystats.domain.reader_report import (
    Chapter,
    Cover,
    ReaderReport,
    SkylineBar,
    Stat,
    Swatch,
    manifest_digest,
)


def added_key(book: AnalysisBook) -> tuple[bool, str, int]:
    added = book.added_at
    return (added is C.NONE, S.EMPTY if added is C.NONE else added.value, book.work_id)


def heroes(ctx: Context) -> tuple[Stat, ...]:
    summary = ctx.summary
    found: list[Stat] = []
    if summary.read:
        found.append(
            Stat(
                label=S.RPT_HERO_READ,
                value=F.count(summary.read),
                detail=S.RPT_HERO_READ_DETAIL,
                tone=C.RptTone.TEAL,
            )
        )
    if summary.rated:
        share = F.percent(summary.rated, summary.read)
        found.append(
            Stat(
                label=S.RPT_HERO_RATED,
                value=F.count(summary.rated),
                detail=S.RPT_HERO_RATED_DETAIL.format(share=share),
                tone=C.RptTone.TEAL,
            )
        )
    known = profile.pages_known(ctx)
    if known:
        found.append(
            Stat(
                label=S.RPT_HERO_PAGES,
                value=F.count(profile.total_pages(ctx)),
                detail=S.RPT_HERO_PAGES_DETAIL.format(books=F.books(known)),
            )
        )
    if summary.distinct_authors:
        found.append(
            Stat(
                label=S.RPT_HERO_AUTHORS,
                value=F.count(summary.distinct_authors),
                detail=S.RPT_HERO_AUTHORS_DETAIL.format(books=F.books(summary.authors_known)),
            )
        )
    if summary.watchlist:
        found.append(
            Stat(
                label=S.RPT_HERO_WATCH,
                value=F.count(summary.watchlist),
                detail=S.RPT_HERO_WATCH_DETAIL,
                tone=C.RptTone.AMBER,
            )
        )
    return tuple(found[: C.FOUR])


def skyline(ctx: Context) -> tuple[SkylineBar, ...]:
    books = sorted(ctx.read, key=added_key)
    if not C.RPT_SKYLINE_MINIMUM <= len(books) <= C.RPT_SKYLINE_LIMIT:
        return ()
    pages = [ctx.plausible_pages(book) for book in books]
    tallest = max((value for value in pages if value is not C.NONE), default=C.ZERO)
    if tallest == C.ZERO:
        return ()
    return tuple(
        SkylineBar(
            height=C.NONE if page is C.NONE else page / tallest,
            tone=tone_of(book, ctx.usual),
        )
        for book, page in zip(books, pages, strict=C.TRUE)
    )


def legend(ctx: Context) -> tuple[Swatch, ...]:
    tiers = (
        ()
        if ctx.usual is C.NONE
        else (
            Swatch(label=S.RPT_LEGEND_STANDOUT, tone=C.RptTone.TEAL),
            Swatch(label=S.RPT_LEGEND_SOLID, tone=C.RptTone.SLATE),
            Swatch(label=S.RPT_LEGEND_BELOW, tone=C.RptTone.AMBER),
        )
    )
    return (*tiers, Swatch(label=S.RPT_LEGEND_UNRATED, tone=C.RptTone.GREY))


def skyline_caption(ctx: Context) -> str:
    usual = ctx.usual
    if usual is C.NONE:
        return S.RPT_SKYLINE_CAPTION
    template = S.RPT_SKYLINE_USUAL_TIED if ctx.summary.tied_usual_ratings else S.RPT_SKYLINE_USUAL
    return S.RPT_SKYLINE_CAPTION + S.SPACE + template.format(rating=F.star_count(usual))


def cover(ctx: Context) -> Cover:
    summary = ctx.summary
    empty = summary.read == C.ZERO and summary.watchlist == C.ZERO
    bars = skyline(ctx)
    return Cover(
        eyebrow=S.RPT_COVER_EYEBROW,
        title=S.RPT_COVER_TITLE,
        subtitle=S.RPT_COVER_EMPTY if empty else S.RPT_COVER_SUBTITLE,
        as_of=S.RPT_COVER_AS_OF.format(date=F.as_of_text(ctx.data.as_of)),
        heroes=heroes(ctx),
        skyline=bars,
        skyline_caption=skyline_caption(ctx) if bars else S.EMPTY,
        legend=legend(ctx) if bars else (),
    )


def build_reader_report(
    data: AnalysisInput,
    analysis: AnalyticsReport,
    recommendations: BaseModel | JsonValue,
    quality: BaseModel | JsonValue,
) -> ReaderReport:
    ctx = make_context(data, analysis, recommendations, quality)
    builders: tuple[Callable[[Context], Chapter | None], ...] = (
        profile.glance,
        profile.facts,
        profile.shape,
        profile.genres,
        profile.ratings,
        profile.favorites,
        profile.authors,
        insights.pointers,
        insights.appetites,
        insights.timeline,
        insights.community,
        outlook.watchlist,
        outlook.shortlist,
        outlook.coverage,
    )
    chapters = tuple(chapter for build in builders if (chapter := build(ctx)) is not C.NONE)
    present = frozenset(chapter.key for chapter in chapters)
    return ReaderReport(
        model_version=C.RPT_MODEL_VERSION,
        analysis_report_id=analysis.report_id,
        as_of=data.as_of,
        manifest_digest=manifest_digest(data.manifest),
        calculation_version=data.manifest.calculation_version,
        cover=cover(ctx),
        chapters=chapters,
        fine_print=outlook.fine_print(present),
        technical_notes=outlook.technical_notes(ctx, present),
    )
