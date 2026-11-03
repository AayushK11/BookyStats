from __future__ import annotations

from collections import Counter

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import report_format as F
from bookystats.application.reader_context import (
    Context,
    integer,
    items,
    mapping,
    number,
    text,
    title_of,
)
from bookystats.application.reader_insights import additions, year_rows
from bookystats.domain.analytics import AnalysisBook
from bookystats.domain.reader_report import (
    BarRow,
    BarsBlock,
    Block,
    BookGroup,
    BookItem,
    BooksBlock,
    CalloutBlock,
    Chapter,
    CoverageBlock,
    CoverageRow,
    ProseBlock,
    Stat,
    TilesBlock,
)


def records(value: JsonValue) -> list[dict[str, JsonValue]]:
    return [mapping(entry) for entry in items(value)]


def fold(value: str) -> str:
    return S.SPACE.join(value.split()).casefold()


def wait_stats(ctx: Context) -> tuple[Stat, ...]:
    summary = mapping(
        ctx.value(S.ANX_LIBRARY_ADDITIONS.format(collection=S.TO_READ)).get(S.ANX_AGE_SUMMARY)
    )
    dated = integer(summary.get(S.AN_CALC_N)) or C.ZERO
    middle, longest = number(summary.get(S.AN_CALC_MEDIAN)), number(summary.get(S.AN_CALC_MAX))
    if dated < ctx.minimum or middle is C.NONE:
        return ()
    detail = S.RPT_WAIT_DETAIL.format(books=F.books(dated))
    stats = [
        Stat(label=S.RPT_WAIT_MEDIAN, value=F.span(middle), detail=detail, tone=C.RptTone.AMBER)
    ]
    if longest is not C.NONE:
        stats.append(
            Stat(
                label=S.RPT_WAIT_LONGEST, value=F.span(longest), detail=detail, tone=C.RptTone.AMBER
            )
        )
    return tuple(stats)


def waiting(ctx: Context) -> list[tuple[int, AnalysisBook, str]]:
    labels = mapping(ctx.value(S.AN_CALC_WATCH_AGE).get(S.AN_CALC_LABELS))
    found: list[tuple[int, AnalysisBook, str]] = []
    for book_id, entry in labels.items():
        detail = mapping(entry)
        age = integer(detail.get(S.AN_CALC_AGE_DAYS))
        added = text(detail.get(S.AN_CALC_ADDED))
        book = ctx.by_book_id.get(book_id)
        if age is not C.NONE and added and book is not C.NONE:
            found.append((age, book, added))
    return sorted(found, key=lambda entry: (-entry[C.ZERO], entry[C.ONE].work_id))


def composition_rows(ctx: Context) -> tuple[tuple[BarRow, ...], int, int, bool]:
    finding = ctx.findings.get(S.AN_PROFILE_WATCH_COMPOSITION.format(feature=S.GENRES))
    if finding is C.NONE:
        return (), C.ZERO, C.ZERO, C.FALSE
    value = mapping(finding.value)
    read_known = integer(value.get(S.AN_CALC_READ_KNOWN)) or C.ZERO
    watch_known = integer(value.get(S.AN_CALC_WATCH_KNOWN)) or C.ZERO
    rows: list[BarRow] = []
    for entry in items(value.get(S.AN_CALC_COMPOSITION_GAPS)):
        detail = mapping(entry)
        label = text(detail.get(S.AN_CALC_LEFT_LABEL))
        read_share = number(detail.get(S.AN_CALC_READ_SHARE))
        watch_share = number(detail.get(S.AN_CALC_WATCH_SHARE))
        delta = number(detail.get(S.AN_CALC_COMPOSITION_DELTA))
        if not label or read_share is C.NONE or watch_share is C.NONE or delta is C.NONE:
            continue
        points = F.signed(delta * C.RPT_PERCENT_SCALE, C.ZERO)
        rows.append(
            BarRow(
                label=F.sentence(label),
                value=delta,
                shown=S.RPT_POINTS.format(value=points),
                caption=S.RPT_COMPOSITION_CAPTION.format(
                    watch=F.fraction(watch_share), read=F.fraction(read_share)
                ),
                tone=C.RptTone.AMBER if delta >= C.ZERO else C.RptTone.TEAL,
            )
        )
    return tuple(rows), read_known, watch_known, C.TRUE


def watchlist(ctx: Context) -> Chapter | None:
    summary = ctx.summary
    if summary.watchlist == C.ZERO:
        return C.NONE
    familiar, fresh = summary.watchlist_familiar_authors, summary.watchlist_new_authors
    unknown = summary.watchlist_unknown_authors
    known = familiar + fresh
    tiles = [
        Stat(
            label=S.RPT_WATCH_SIZE,
            value=F.count(summary.watchlist),
            detail=S.RPT_WATCH_SIZE_DETAIL,
            tone=C.RptTone.AMBER,
        )
    ]
    if known:
        tiles.append(
            Stat(
                label=S.RPT_WATCH_FAMILIAR,
                value=F.count(familiar),
                detail=S.RPT_WATCH_SHARE_DETAIL.format(share=F.percent(familiar, known)),
                tone=C.RptTone.TEAL,
            )
        )
        tiles.append(
            Stat(
                label=S.RPT_WATCH_NEW,
                value=F.count(fresh),
                detail=S.RPT_WATCH_SHARE_DETAIL.format(share=F.percent(fresh, known)),
            )
        )
    if unknown:
        tiles.append(
            Stat(
                label=S.RPT_WATCH_UNKNOWN,
                value=F.count(unknown),
                detail=S.RPT_WATCH_UNKNOWN_DETAIL,
                tone=C.RptTone.GREY,
            )
        )
    tiles.extend(wait_stats(ctx))
    blocks: list[Block] = [TilesBlock(tiles=tuple(tiles), note=S.RPT_WATCH_TILES_NOTE)]
    rows, read_known, watch_known, present = composition_rows(ctx)
    if rows:
        note = S.RPT_WATCH_COMPOSITION_NOTE.format(
            read=F.count(read_known), watch=F.count(watch_known), minimum=ctx.minimum
        )
        blocks.append(
            BarsBlock(
                heading=S.RPT_WATCH_COMPOSITION_HEADING,
                style=C.RptBarStyle.DIVERGING,
                rows=rows,
                note=note,
                axis=S.RPT_AXIS_POINTS,
            )
        )
    elif present:
        thin = S.RPT_WATCH_COMPOSITION_THIN.format(
            read=F.count(read_known), watch=F.count(watch_known), minimum=ctx.minimum
        )
        blocks.append(ProseBlock(heading=S.RPT_WATCH_COMPOSITION_HEADING, paragraphs=(thin,)))
    longest = waiting(ctx)[: C.RPT_WAIT_LIMIT]
    if len(longest) >= C.THREE:
        books = tuple(
            BookItem(
                title=title_of(book),
                byline=F.byline(book.authors),
                detail=S.RPT_WAIT_ITEM.format(added=F.month_year(added), span=F.span(age)),
            )
            for age, book, added in longest
        )
        blocks.append(
            BooksBlock(
                heading=S.RPT_WAIT_HEADING,
                groups=(BookGroup(heading=S.EMPTY, books=books),),
                note=S.RPT_WAIT_NOTE,
            )
        )
    added = additions(ctx, S.TO_READ)
    if len(added) >= C.TWO:
        total = sum(added.values())
        note = S.RPT_WATCH_ADDED_NOTE.format(books=F.count(total))
        undated = summary.watchlist - total
        if undated > C.ZERO:
            note += S.SPACE + S.RPT_ADDED_UNKNOWN.format(books=F.books(undated))
        blocks.append(
            BarsBlock(
                heading=S.RPT_WATCH_ADDED_HEADING,
                style=C.RptBarStyle.VERTICAL,
                rows=year_rows(added, ctx.year),
                note=note,
                axis=S.RPT_AXIS_BOOKS,
            )
        )
    return Chapter(
        key=S.RPT_CHAPTER_WATCHLIST,
        title=S.RPT_WATCHLIST_TITLE,
        kicker=S.RPT_WATCHLIST_KICKER,
        intro=S.RPT_WATCHLIST_INTRO,
        blocks=tuple(blocks),
    )


def author_names(ctx: Context) -> dict[str, str]:
    names: dict[str, str] = {}
    for book in sorted(ctx.data.books, key=lambda book: book.work_id):
        for author in book.authors:
            names.setdefault(fold(author), F.clean(author))
    return names


def lean(contribution: float) -> str:
    if contribution >= C.RPT_LEAN_MINIMUM:
        return S.RPT_LEAN_ABOVE
    if contribution <= -C.RPT_LEAN_MINIMUM:
        return S.RPT_LEAN_BELOW
    return S.RPT_LEAN_NEAR


def reason(component: dict[str, JsonValue], names: dict[str, str]) -> str | None:
    feature = text(component.get(S.PDF_KEY_FEATURE))
    label = text(component.get(S.PDF_KEY_LABEL))
    books = integer(component.get(S.PDF_KEY_SAMPLE_SIZE))
    contribution = number(component.get(S.PDF_KEY_CONTRIBUTION))
    if not label or books is C.NONE or contribution is C.NONE:
        return C.NONE
    if feature == S.REC_AUTHOR:
        label = names.get(label, label)
    template = C.RPT_REASON_TEMPLATES.get(feature, S.RPT_REASON_OTHER)
    return template.format(label=F.sentence(label), books=F.books(books), lean=lean(contribution))


def shortlist_item(
    position: int, item: dict[str, JsonValue], names: dict[str, str]
) -> BookItem | None:
    title = F.display_title(text(item.get(S.TITLE)))
    if not title:
        return C.NONE
    lines: list[str] = []
    components = sorted(
        records(item.get(S.PDF_KEY_COMPONENTS)),
        key=lambda part: (
            -(number(part.get(S.PDF_KEY_CONTRIBUTION)) or C.ZERO),
            text(part.get(S.PDF_KEY_LABEL)),
        ),
    )
    for component in components[: C.RPT_REASON_LIMIT]:
        line = reason(component, names)
        if line is not C.NONE:
            lines.append(line)
    hidden = len(components) - C.RPT_REASON_LIMIT
    if hidden > C.ZERO:
        lines.append(S.RPT_REASON_MORE.format(count=hidden))
    mismatches = len(items(item.get(S.PDF_KEY_MISMATCHES)))
    if mismatches:
        lines.append(
            S.RPT_WORTH_CHECKING.format(
                features=F.noun(mismatches, S.RPT_SHARED_FEATURE, S.RPT_SHARED_FEATURES),
                bar=C.REC_MISMATCH_THRESHOLD,
            )
        )
    supporting = records(item.get(S.PDF_KEY_SUPPORTING))
    if supporting:
        rating = number(supporting[C.ZERO].get(S.RATING))
        example = F.display_title(text(supporting[C.ZERO].get(S.TITLE)))
        if rating is not C.NONE and example:
            lines.append(
                S.RPT_EXAMPLE.format(
                    title=S.RPT_QUOTED.format(text=example), rating=F.trimmed(rating)
                )
            )
    if text(item.get(S.PDF_KEY_PREFERENCE_TIER)) == S.REC_LIMITED:
        lines.append(S.RPT_THIN_EVIDENCE.format(books=C.RPT_THIN_SAMPLE))
    added = text(item.get(S.ADDED_AT))
    detail = S.RPT_ON_LIST_SINCE.format(added=F.month_year(added)) if added else S.EMPTY
    authors = tuple(text(author) for author in items(item.get(S.AUTHORS)))
    return BookItem(
        title=title,
        byline=F.byline(authors),
        detail=detail,
        marker=str(position),
        lines=tuple(lines),
    )


def missing_line(shortlist: list[dict[str, JsonValue]]) -> str | None:
    counts: Counter[str] = Counter()
    for item in shortlist:
        for message in {text(entry) for entry in items(item.get(S.PDF_KEY_MISSINGNESS))}:
            if message in C.RPT_MISSING_LABELS:
                counts[message] += C.ONE
    if not counts:
        return C.NONE
    ordered = sorted(counts.items(), key=lambda entry: (-entry[C.ONE], entry[C.ZERO]))
    parts = [
        S.RPT_MISSING_PART.format(what=C.RPT_MISSING_LABELS[message], books=F.count(books))
        for message, books in ordered
    ]
    return S.RPT_SHORTLIST_MISSING.format(parts=S.COMMA_SPACE.join(parts))


def shortlist(ctx: Context) -> Chapter | None:
    report = ctx.recommendations
    ranked = items(report.get(S.PDF_KEY_RANKED))
    unrankable = items(report.get(S.PDF_KEY_UNRANKABLE))
    excluded = items(report.get(S.PDF_KEY_EXCLUDED))
    picks = records(report.get(S.PDF_KEY_SHORTLIST))[: C.REC_SHORTLIST_SIZE]
    if not (ranked or unrankable or excluded or picks) or not ctx.watch:
        return C.NONE
    names = author_names(ctx)
    books = tuple(
        book
        for position, pick in enumerate(picks, start=C.ONE)
        if (book := shortlist_item(position, pick, names)) is not C.NONE
    )
    counts = S.RPT_SHORTLIST_COUNTS.format(
        ranked=F.count(len(ranked)),
        unrankable=F.count(len(unrankable)),
        excluded=F.count(len(excluded)),
    )
    notes = [S.RPT_SHORTLIST_CAVEAT, counts]
    missing = missing_line(picks)
    if missing is not C.NONE:
        notes.append(missing)
    blocks: list[Block] = []
    if books:
        group = BookGroup(heading=S.EMPTY, books=books)
        blocks.append(
            BooksBlock(
                heading=S.RPT_SHORTLIST_HEADING,
                groups=(group,),
                note=S.RPT_SHORTLIST_NOTE.format(shown=len(books)),
            )
        )
    else:
        blocks.append(ProseBlock(paragraphs=(S.RPT_SHORTLIST_NONE,)))
    blocks.append(
        CalloutBlock(
            heading=S.RPT_SHORTLIST_CAVEAT_HEADING, paragraphs=tuple(notes), tone=C.RptTone.AMBER
        )
    )
    return Chapter(
        key=S.RPT_CHAPTER_SHORTLIST,
        title=S.RPT_SHORTLIST_TITLE,
        kicker=S.RPT_SHORTLIST_KICKER,
        intro=S.RPT_SHORTLIST_INTRO,
        blocks=tuple(blocks),
    )


def pair(record: dict[str, JsonValue] | None) -> tuple[int, int]:
    if record is C.NONE:
        return C.ZERO, C.ZERO
    return (
        integer(record.get(S.PDF_KEY_AVAILABLE)) or C.ZERO,
        integer(record.get(S.PDF_KEY_POPULATION)) or C.ZERO,
    )


def coverage_rows(ctx: Context) -> tuple[CoverageRow, ...]:
    table = {
        (text(record.get(S.FIELD)), text(record.get(S.PDF_KEY_POPULATION_NAME))): record
        for record in records(ctx.quality.get(S.PDF_KEY_COVERAGE))
    }
    rows: list[CoverageRow] = []
    for field, label in C.RPT_COVERAGE_FIELDS:
        read_known, read_total = pair(table.get((field, S.READ)))
        watch_known, watch_total = pair(table.get((field, S.TO_READ)))
        if field == S.RATING:
            watch_known = watch_total = C.ZERO
        if read_total == C.ZERO and watch_total == C.ZERO:
            continue
        rows.append(
            CoverageRow(
                label=label,
                read_known=read_known,
                read_total=read_total,
                watch_known=watch_known,
                watch_total=watch_total,
            )
        )
    return tuple(rows)


def identity_line(ctx: Context) -> str | None:
    identity = mapping(ctx.quality.get(S.PDF_KEY_IDENTITY))
    works = integer(ctx.quality.get(S.PDF_KEY_POPULATION))
    linked = integer(identity.get(S.RPT_KEY_LINKED))
    anchored = integer(identity.get(S.RPT_KEY_ANCHORED))
    comparable = integer(identity.get(S.RPT_KEY_COMPARABLE))
    consistent = integer(identity.get(S.RPT_KEY_CONSISTENT))
    if works is C.NONE or linked is C.NONE or anchored is C.NONE:
        return C.NONE
    verified = integer(identity.get(S.RPT_KEY_VERIFIED))
    line = S.RPT_IDENTITY.format(
        linked=F.count(linked), works=F.books(works), anchored=F.count(anchored)
    )
    if comparable == C.ZERO:
        line += S.SPACE + S.RPT_IDENTITY_NO_COMPARISON
    elif comparable is not C.NONE and consistent is not C.NONE:
        line += S.SPACE + S.RPT_IDENTITY_COMPARED.format(
            comparable=F.noun(comparable, S.RPT_WORK, S.RPT_WORKS), consistent=F.count(consistent)
        )
    unknown = S.RPT_NOT_MEASURED if verified is C.NONE else F.count(verified)
    return line + S.SPACE + S.RPT_IDENTITY_VERIFIED.format(verified=unknown)


def flagged(ctx: Context) -> list[str]:
    books: dict[str, set[int]] = {}
    for entry in records(ctx.quality.get(S.PDF_KEY_DIAGNOSTICS)):
        code = text(entry.get(S.CODE))
        if code not in C.RPT_FLAG_LABELS:
            continue
        ids = {work for work in map(integer, items(entry.get(S.PDF_KEY_WORK_IDS))) if work}
        books.setdefault(code, set()).update(ids)
    ordered = sorted(books.items(), key=lambda entry: (-len(entry[C.ONE]), entry[C.ZERO]))
    return [
        S.RPT_FLAGGED_LINE.format(books=F.books(len(ids)), message=C.RPT_FLAG_LABELS[code])
        for code, ids in ordered
        if ids
    ]


def coverage(ctx: Context) -> Chapter | None:
    rows = coverage_rows(ctx)
    if not rows:
        return C.NONE
    blocks: list[Block] = [
        CoverageBlock(heading=S.RPT_COVERAGE_HEADING, rows=rows, note=S.RPT_COVERAGE_NOTE)
    ]
    line = identity_line(ctx)
    if line is not C.NONE:
        blocks.append(ProseBlock(heading=S.RPT_IDENTITY_HEADING, paragraphs=(line,)))
    lines = flagged(ctx)
    if lines:
        blocks.append(
            CalloutBlock(
                heading=S.RPT_FLAGGED_HEADING,
                paragraphs=(S.RPT_FLAGGED_INTRO, *lines),
                tone=C.RptTone.SLATE,
            )
        )
    return Chapter(
        key=S.RPT_CHAPTER_COVERAGE,
        title=S.RPT_COVERAGE_TITLE,
        kicker=S.RPT_COVERAGE_KICKER,
        intro=S.RPT_COVERAGE_INTRO,
        blocks=tuple(blocks),
    )


def fine_print(present: frozenset[str]) -> tuple[str, ...]:
    lines = [S.RPT_FINE_SOURCES, S.RPT_FINE_SNAPSHOT]
    lines.extend(note for key, note in C.RPT_FINE_NOTES if key in present)
    return tuple(dict.fromkeys(lines))


def technical_notes(ctx: Context, present: frozenset[str]) -> tuple[str, ...]:
    lines: list[str] = []
    if S.RPT_CHAPTER_SHORTLIST in present:
        lines.extend(text(entry) for entry in items(ctx.recommendations.get(S.PDF_KEY_LIMITATIONS)))
    if S.RPT_CHAPTER_COVERAGE in present:
        lines.extend(text(entry) for entry in items(ctx.quality.get(S.PDF_KEY_LIMITATIONS)))
    return tuple(dict.fromkeys(line for line in lines if line))
