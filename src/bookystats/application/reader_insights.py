from __future__ import annotations

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import report_format as F
from bookystats.application.reader_context import (
    Context,
    integer,
    mapping,
    number,
    text,
    title_of,
    year_entries,
)
from bookystats.domain.reader import ReaderComparison, ReaderGroup
from bookystats.domain.reader_report import (
    BarRow,
    BarsBlock,
    Block,
    CalloutBlock,
    Chapter,
    CompareBlock,
    CompareRow,
    Quote,
    QuotesBlock,
    Stat,
    TilesBlock,
)


def community(ctx: Context) -> Chapter | None:
    comparisons = ctx.summary.community_comparisons
    if not comparisons:
        return C.NONE
    total = len(comparisons)
    higher = [item for item in comparisons if item.difference > C.RPT_SAME_GAP]
    lower = [item for item in comparisons if item.difference < -C.RPT_SAME_GAP]
    same = total - len(higher) - len(lower)
    gap = sum(item.difference for item in comparisons) / total
    tiles = (
        Stat(label=S.RPT_COMMUNITY_COMPARED, value=F.count(total), tone=C.RptTone.SLATE),
        Stat(
            label=S.RPT_COMMUNITY_HIGHER,
            value=F.count(len(higher)),
            detail=F.percent(len(higher), total),
            tone=C.RptTone.SLATE,
        ),
        Stat(
            label=S.RPT_COMMUNITY_LOWER,
            value=F.count(len(lower)),
            detail=F.percent(len(lower), total),
            tone=C.RptTone.SLATE,
        ),
        Stat(
            label=S.RPT_COMMUNITY_SAME,
            value=F.count(same),
            detail=F.percent(same, total),
            tone=C.RptTone.SLATE,
        ),
        Stat(
            label=S.RPT_COMMUNITY_GAP,
            value=F.signed(gap),
            detail=S.RPT_COMMUNITY_GAP_DETAIL,
            tone=C.RptTone.SLATE,
        ),
    )
    blocks: list[Block] = [TilesBlock(tiles=tiles)]
    eligible = [
        item
        for item in comparisons
        if item.community_sample_size is not C.NONE
        and item.community_sample_size >= C.RPT_COMMUNITY_SAMPLE
    ]
    leaving = total - len(eligible)

    def rows(picks: list[ReaderComparison]) -> tuple[CompareRow, ...]:
        built: list[CompareRow] = []
        for pick in picks:
            book = ctx.by_work.get(pick.work_id)
            if book is C.NONE or pick.community_sample_size is C.NONE:
                continue
            built.append(
                CompareRow(
                    title=title_of(book),
                    byline=F.byline(book.authors),
                    personal=pick.personal,
                    community=pick.community,
                    personal_text=F.trimmed(pick.personal),
                    community_text=F.trimmed(pick.community),
                    delta=F.signed_stars(pick.difference),
                    sample=F.noun(pick.community_sample_size, S.RPT_RATING, S.RPT_RATINGS),
                )
            )
        return tuple(built)

    def strongest(sign: int) -> list[ReaderComparison]:
        ordered = sorted(
            (item for item in eligible if item.difference * sign > C.RPT_SAME_GAP),
            key=lambda item: (-abs(item.difference), item.work_id),
        )
        return ordered[: C.RPT_COMPARE_LIMIT]

    above, below = rows(strongest(C.ONE)), rows(strongest(-C.ONE))
    note = S.RPT_COMMUNITY_SAMPLE_NOTE.format(
        minimum=C.RPT_COMMUNITY_SAMPLE,
        left=F.noun(leaving, S.RPT_COMPARISON, S.RPT_COMPARISONS),
    )
    if above:
        blocks.append(
            CompareBlock(
                heading=S.RPT_COMMUNITY_ABOVE_HEADING,
                rows=above,
                note=note if not below else S.EMPTY,
            )
        )
    if below:
        blocks.append(CompareBlock(heading=S.RPT_COMMUNITY_BELOW_HEADING, rows=below, note=note))
    if not above and not below:
        blocks.append(CalloutBlock(paragraphs=(note,), tone=C.RptTone.SLATE))
    blocks.append(
        CalloutBlock(
            heading=S.RPT_COMMUNITY_CALLOUT_HEADING,
            paragraphs=(S.RPT_COMMUNITY_CALLOUT,),
            tone=C.RptTone.SLATE,
        )
    )
    return Chapter(
        key=S.RPT_CHAPTER_COMMUNITY,
        title=S.RPT_COMMUNITY_TITLE,
        kicker=S.RPT_COMMUNITY_KICKER,
        intro=S.RPT_COMMUNITY_INTRO,
        blocks=tuple(blocks),
    )


def preference_rows(groups: tuple[ReaderGroup, ...]) -> tuple[BarRow, ...]:
    supported = [group for group in groups if group.difference_from_baseline is not C.NONE]
    ordered = sorted(
        supported,
        key=lambda group: (-(group.difference_from_baseline or C.ZERO), group.label.casefold()),
    )
    chosen = (
        ordered
        if len(ordered) <= C.RPT_POINTER_LIMIT * C.TWO
        else [*ordered[: C.RPT_POINTER_LIMIT], *ordered[-C.RPT_POINTER_LIMIT :]]
    )
    rows = [
        BarRow(
            label=F.sentence(group.label),
            value=group.difference_from_baseline,
            shown=F.signed(group.difference_from_baseline or C.ZERO),
            caption=S.RPT_POINTER_CAPTION.format(rated=group.rated),
            tone=C.RptTone.GREEN
            if (group.difference_from_baseline or C.ZERO) >= C.ZERO
            else C.RptTone.CORAL,
        )
        for group in chosen
    ]
    return tuple(rows) if len(rows) >= C.TWO else ()


def validation_callout(ctx: Context) -> CalloutBlock | None:
    finding = ctx.findings.get(S.AV_VALIDATION)
    if finding is C.NONE:
        return C.NONE
    value = mapping(finding.value)
    state = value.get(S.AV_STATE)
    if state != S.AV_AVAILABLE:
        reasons = {
            S.AV_SMALL: S.RPT_VALIDATION_SMALL,
            S.AV_NO_TRAINING: S.RPT_VALIDATION_NO_TRAINING,
            S.AV_NO_SIGNAL: S.RPT_VALIDATION_NO_SIGNAL,
        }
        reason = reasons.get(state if isinstance(state, str) else S.EMPTY)
        if reason is C.NONE:
            return C.NONE
        return CalloutBlock(
            heading=S.RPT_VALIDATION_HEADING, paragraphs=(reason,), tone=C.RptTone.AMBER
        )
    predictor = number(mapping(value.get(S.AN_CALC_PREDICTOR_ERRORS)).get(S.AN_CALC_MAE))
    baseline = number(mapping(value.get(S.AN_CALC_BASELINE_ERRORS)).get(S.AN_CALC_MAE))
    books = integer(value.get(S.AN_CALC_N))
    if predictor is C.NONE or baseline is C.NONE or books is C.NONE:
        return C.NONE
    better = predictor < baseline
    lines = [
        S.RPT_VALIDATION_RESULT.format(
            books=F.books(books),
            predictor=F.star_count(predictor),
            baseline=F.trimmed(baseline),
            verdict=S.RPT_VALIDATION_BETTER if better else S.RPT_VALIDATION_NOT_BETTER,
        )
    ]
    stability = mapping(finding.uncertainty.get(S.AV_STABILITY))
    spread = mapping(stability.get(S.AV_STABILITY_RANGE))
    low, high = number(spread.get(S.AV_LOWER)), number(spread.get(S.AV_UPPER))
    if low is not C.NONE and high is not C.NONE:
        lines.append(S.RPT_VALIDATION_RANGE.format(low=F.signed(low), high=F.signed(high)))
    lines.append(S.RPT_VALIDATION_SCOPE)
    return CalloutBlock(
        heading=S.RPT_VALIDATION_HEADING, paragraphs=tuple(lines), tone=C.RptTone.AMBER
    )


def pointers(ctx: Context) -> Chapter | None:
    summary = ctx.summary
    blocks: list[Block] = []
    baseline = F.trimmed(summary.average) if summary.average is not C.NONE else S.RPT_UNKNOWN
    for heading, groups in (
        (S.RPT_POINTER_GENRES, summary.genres),
        (S.RPT_POINTER_AUTHORS, summary.authors),
        (S.RPT_POINTER_LENGTHS, summary.lengths),
    ):
        rows = preference_rows(groups)
        if rows:
            blocks.append(
                BarsBlock(
                    heading=heading,
                    style=C.RptBarStyle.DIVERGING,
                    rows=rows,
                    note=S.RPT_POINTER_NOTE.format(baseline=baseline, minimum=ctx.minimum),
                    axis=S.RPT_AXIS_DIFFERENCE,
                )
            )
    callout = validation_callout(ctx)
    if not blocks:
        return C.NONE
    if callout is not C.NONE:
        blocks.append(callout)
    return Chapter(
        key=S.RPT_CHAPTER_POINTERS,
        title=S.RPT_POINTERS_TITLE,
        kicker=S.RPT_POINTERS_KICKER,
        intro=S.RPT_POINTERS_INTRO,
        blocks=tuple(blocks),
    )


def label_of(name: str) -> str:
    return F.sentence(name.replace(S.RPT_UNDERSCORE, S.SPACE))


def mention_rows(
    groups: dict[str, JsonValue], names: tuple[str, ...], known: int
) -> tuple[BarRow, ...]:
    rows: list[BarRow] = []
    for name in names:
        entry = mapping(groups.get(name))
        share = number(entry.get(S.CONTENT_ANALYSIS_SHARE))
        books = integer(entry.get(S.CONTENT_ANALYSIS_COUNT))
        if share is C.NONE or books is C.NONE:
            continue
        rows.append(
            BarRow(
                label=label_of(name),
                value=share,
                shown=F.percent(books, known),
                caption=S.RPT_MENTION_CAPTION.format(books=F.count(books), known=F.count(known)),
            )
        )
    return tuple(rows)


def appetite_quotes(ctx: Context, groups: dict[str, JsonValue]) -> tuple[Quote, ...]:
    quotes: list[Quote] = []
    for name in C.ANALYTICS_DIMENSIONS:
        proofs = mapping(groups.get(name)).get(S.CONTENT_ANALYSIS_PROOF)
        for proof in proofs if isinstance(proofs, list) else []:
            detail = mapping(proof)
            book = ctx.by_book_id.get(text(detail.get(S.CONTENT_ANALYSIS_WORK)))
            cue = text(detail.get(S.CONTENT_ANALYSIS_MATCH))
            if book is C.NONE or not cue:
                continue
            excerpt = F.word_safe_excerpt(
                text(detail.get(S.CONTENT_ANALYSIS_QUOTE)), cue, book.description
            )
            if excerpt is C.NONE:
                continue
            link = F.human_link(text(detail.get(S.CONTENT_ANALYSIS_URL)) or C.NONE)
            quotes.append(
                Quote(
                    text=excerpt,
                    cue=cue,
                    title=title_of(book),
                    byline=F.byline(book.authors),
                    link=link,
                )
            )
            break
    return tuple(quotes)


def share_of(groups: dict[str, JsonValue], name: str) -> float:
    return number(mapping(groups.get(name)).get(S.CONTENT_ANALYSIS_SHARE)) or C.ZERO


def appetites(ctx: Context) -> Chapter | None:
    hunger = ctx.findings.get(S.CONTENT_ANALYSIS_HUNGERS.format(collection=S.READ))
    themes = ctx.findings.get(S.CONTENT_ANALYSIS_THEMES.format(collection=S.READ))
    blocks: list[Block] = []
    if hunger is not C.NONE:
        value = mapping(hunger.value)
        known = integer(value.get(S.CONTENT_ANALYSIS_KNOWN)) or C.ZERO
        groups = mapping(value.get(S.CONTENT_ANALYSIS_GROUPS))
        rows = mention_rows(groups, C.ANALYTICS_DIMENSIONS, known)
        if rows and known:
            hidden = integer(value.get(S.CONTENT_ANALYSIS_SUPPRESSED)) or C.ZERO
            note = S.RPT_APPETITE_NOTE.format(known=F.count(known), read=F.count(ctx.summary.read))
            if hidden:
                note += S.SPACE + S.RPT_APPETITE_HIDDEN.format(count=hidden, minimum=ctx.minimum)
            blocks.append(
                BarsBlock(
                    heading=S.RPT_APPETITE_HEADING,
                    rows=rows,
                    note=note,
                    axis=S.RPT_AXIS_SHARE,
                    maximum=C.RPT_SHARE_SCALE,
                )
            )
        enjoyment = enjoyment_rows(ctx)
        if enjoyment:
            blocks.append(
                BarsBlock(
                    heading=S.RPT_ENJOYMENT_HEADING,
                    style=C.RptBarStyle.DIVERGING,
                    rows=enjoyment,
                    note=S.RPT_ENJOYMENT_NOTE,
                    axis=S.RPT_AXIS_DIFFERENCE,
                )
            )
        quotes = appetite_quotes(ctx, groups)
        if quotes:
            blocks.append(
                QuotesBlock(heading=S.RPT_QUOTES_HEADING, quotes=quotes, note=S.RPT_QUOTES_NOTE)
            )
    if themes is not C.NONE:
        value = mapping(themes.value)
        theme_known = integer(value.get(S.CONTENT_ANALYSIS_KNOWN)) or C.ZERO
        groups = mapping(value.get(S.CONTENT_ANALYSIS_GROUPS))
        names = tuple(sorted(groups, key=lambda name: (-share_of(groups, name), name)))
        rows = mention_rows(groups, names, theme_known)
        if rows and theme_known:
            blocks.append(
                BarsBlock(
                    heading=S.RPT_THEMES_HEADING,
                    rows=rows,
                    note=S.RPT_THEMES_NOTE,
                    axis=S.RPT_AXIS_SHARE,
                    maximum=C.RPT_SHARE_SCALE,
                )
            )
    if not blocks:
        return C.NONE
    return Chapter(
        key=S.RPT_CHAPTER_APPETITES,
        title=S.RPT_APPETITES_TITLE,
        kicker=S.RPT_APPETITES_KICKER,
        intro=S.RPT_APPETITES_INTRO,
        blocks=tuple(blocks),
    )


def enjoyment_rows(ctx: Context) -> tuple[BarRow, ...]:
    rows: list[BarRow] = []
    for name in C.ANALYTICS_DIMENSIONS:
        value = ctx.value(S.ANX_ENJOYMENT.format(dimension=name))
        difference, rated = number(value.get(S.ANX_DIFFERENCE)), integer(value.get(S.AN_CALC_RATED))
        if difference is C.NONE or rated is C.NONE:
            continue
        rows.append(
            BarRow(
                label=label_of(name),
                value=difference,
                shown=F.signed(difference),
                caption=S.RPT_POINTER_CAPTION.format(rated=rated),
                tone=C.RptTone.GREEN if difference >= C.ZERO else C.RptTone.CORAL,
            )
        )
    return tuple(rows) if len(rows) >= C.TWO else ()


def precision_text(entries: dict[int, JsonValue]) -> str:
    totals: dict[str, int] = {}
    for entry in entries.values():
        for kind, books in mapping(mapping(entry).get(S.ANX_DATE_PRECISIONS)).items():
            parsed = integer(books)
            if parsed is not C.NONE:
                totals[kind] = totals.get(kind, C.ZERO) + parsed
    parts = [
        S.RPT_PRECISION_PART.format(books=F.count(totals[kind]), kind=label)
        for kind, label in (
            (S.DAY, S.RPT_PRECISION_DAY),
            (S.MONTH, S.RPT_PRECISION_MONTH),
            (S.YEAR, S.RPT_PRECISION_YEAR),
        )
        if totals.get(kind)
    ]
    return F.join_names(parts)


def year_rows(counts: dict[int, int], current: int | None) -> tuple[BarRow, ...]:
    if not counts:
        return ()
    rows: list[BarRow] = []
    for year in range(min(counts), max(counts) + C.ONE):
        books = counts.get(year, C.ZERO)
        label = S.RPT_YEAR_SO_FAR.format(year=year) if year == current else str(year)
        rows.append(BarRow(label=label, value=float(books), shown=F.count(books)))
    return tuple(rows)


def timeline(ctx: Context) -> Chapter | None:
    blocks: list[Block] = []
    entries = year_entries(ctx, S.ANX_COMPLETION_COHORTS)
    finished = {
        year: integer(mapping(entry).get(S.AN_CALC_N)) or C.ZERO for year, entry in entries.items()
    }
    finished = {year: books for year, books in finished.items() if books > C.ZERO}
    if finished:
        dated = sum(finished.values())
        note = S.RPT_FINISHED_NOTE.format(dated=F.count(dated), read=F.count(ctx.summary.read))
        precision = precision_text({year: entries[year] for year in finished})
        if precision:
            note += S.SPACE + S.RPT_PRECISION_NOTE.format(precision=precision)
        if ctx.year in finished:
            note += S.SPACE + S.RPT_YEAR_SO_FAR_NOTE
        blocks.append(
            BarsBlock(
                heading=S.RPT_FINISHED_HEADING,
                style=C.RptBarStyle.VERTICAL,
                rows=year_rows(finished, ctx.year),
                note=note,
                axis=S.RPT_AXIS_BOOKS,
            )
        )
    rated_rows: list[BarRow] = []
    for year, entry in entries.items():
        summary = mapping(mapping(entry).get(S.ANX_CURRENT_RATINGS))
        mean_rating, rated = (
            number(summary.get(S.AN_CALC_MEAN)),
            integer(summary.get(S.AN_CALC_RATED)),
        )
        if mean_rating is C.NONE or rated is C.NONE or rated < ctx.minimum:
            continue
        rated_rows.append(
            BarRow(
                label=str(year),
                value=mean_rating,
                shown=F.trimmed(mean_rating),
                caption=S.RPT_POINTER_CAPTION.format(rated=rated),
            )
        )
    if len(rated_rows) >= C.TWO:
        blocks.append(
            BarsBlock(
                heading=S.RPT_TODAY_HEADING,
                rows=tuple(rated_rows),
                note=S.RPT_TODAY_NOTE.format(minimum=ctx.minimum),
                axis=S.RPT_AXIS_STARS,
                maximum=C.RPT_STAR_SCALE,
            )
        )
    added = additions(ctx, S.READ)
    if len(added) >= C.TWO:
        total = sum(added.values())
        undated = ctx.summary.read - total
        note = S.RPT_ADDED_NOTE.format(books=F.count(total))
        if undated > C.ZERO:
            note += S.SPACE + S.RPT_ADDED_UNKNOWN.format(books=F.books(undated))
        blocks.append(
            BarsBlock(
                heading=S.RPT_ADDED_HEADING,
                style=C.RptBarStyle.VERTICAL,
                rows=year_rows(added, ctx.year),
                note=note,
                axis=S.RPT_AXIS_BOOKS,
            )
        )
    if not blocks:
        return C.NONE
    return Chapter(
        key=S.RPT_CHAPTER_TIME,
        title=S.RPT_TIME_TITLE,
        kicker=S.RPT_TIME_KICKER,
        intro=S.RPT_TIME_INTRO,
        blocks=tuple(blocks),
    )


def additions(ctx: Context, collection: str) -> dict[int, int]:
    entries = year_entries(ctx, S.ANX_LIBRARY_ADDITIONS.format(collection=collection))
    counts = {year: integer(entry) or C.ZERO for year, entry in entries.items()}
    return {year: books for year, books in counts.items() if books > C.ZERO}
