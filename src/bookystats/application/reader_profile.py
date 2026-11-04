from __future__ import annotations

from collections import Counter, defaultdict

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import report_format as F
from bookystats.application.reader_context import (
    Context,
    integer,
    is_sparse,
    item_of,
    mapping,
    number,
    numeric,
    tier_tone,
    title_of,
    whole,
    year_entries,
)
from bookystats.domain.analytics import AnalysisBook
from bookystats.domain.reader import ReaderGroup
from bookystats.domain.reader_report import (
    BarRow,
    BarsBlock,
    Block,
    BookGroup,
    BookItem,
    BooksBlock,
    Chapter,
    Fact,
    FactsBlock,
    ProseBlock,
    Stat,
    TilesBlock,
)


def stat(label: str, value: str, detail: str = S.EMPTY, tone: C.RptTone = C.RptTone.INK) -> Stat:
    return Stat(label=label, value=value, detail=detail, tone=tone)


def fact(headline: str, body: str, tone: C.RptTone = C.RptTone.TEAL) -> Fact:
    return Fact(headline=headline, body=body, tone=tone)


def quoted(title: str) -> str:
    return S.RPT_QUOTED.format(text=title)


def sorted_by_pages(ctx: Context) -> list[AnalysisBook]:
    known = [book for book in ctx.read if ctx.plausible_pages(book) is not C.NONE]
    return sorted(
        known,
        key=lambda book: (ctx.plausible_pages(book) or C.ZERO, book.title.casefold(), book.work_id),
    )


def sorted_by_year(ctx: Context) -> list[AnalysisBook]:
    known = [book for book in ctx.read if ctx.plausible_year(book) is not C.NONE]
    return sorted(
        known,
        key=lambda book: (
            ctx.plausible_year(book) or C.ZERO,
            book.title.casefold(),
            book.work_id,
        ),
    )


def total_pages(ctx: Context) -> int:
    return sum(ctx.plausible_pages(book) or C.ZERO for book in ctx.read)


def pages_known(ctx: Context) -> int:
    return sum(ctx.plausible_pages(book) is not C.NONE for book in ctx.read)


def average_caption(group: ReaderGroup, minimum: int) -> str:
    if group.average is C.NONE or is_sparse(group.rated, minimum):
        return S.RPT_TOO_FEW_RATED.format(rated=group.rated)
    return S.RPT_AVERAGE_CAPTION.format(average=F.trimmed(group.average), rated=group.rated)


def leaders(groups: tuple[ReaderGroup, ...]) -> tuple[ReaderGroup, ...]:
    if not groups or groups[C.ZERO].works < C.TWO:
        return ()
    top = groups[C.ZERO].works
    return tuple(group for group in groups if group.works == top)


def leader_fact(
    groups: tuple[ReaderGroup, ...], headline: str, noun: str, nouns: str
) -> Fact | None:
    tied = leaders(groups)
    if not tied:
        return C.NONE
    count = F.books(tied[C.ZERO].works)
    if len(tied) == C.ONE:
        body = S.RPT_LEAD_ONE.format(name=tied[C.ZERO].label, noun=noun, count=count)
    elif len(tied) <= C.THREE:
        names = F.join_names(group.label for group in tied)
        body = S.RPT_LEAD_FEW.format(names=names, nouns=nouns, count=count)
    else:
        body = S.RPT_LEAD_MANY.format(total=len(tied), nouns=nouns, count=count)
    return fact(headline, body)


def book_fact(headline: str, template: str, book: AnalysisBook, **values: str) -> Fact:
    body = template.format(title=quoted(title_of(book)), byline=F.byline(book.authors), **values)
    return fact(headline, body)


def tie_text(ctx: Context, books: list[AnalysisBook], pick: AnalysisBook, *, year: bool) -> str:
    probe = ctx.plausible_year if year else ctx.plausible_pages
    others = sum(probe(book) == probe(pick) for book in books) - C.ONE
    if others <= C.ZERO:
        return S.EMPTY
    return S.RPT_TIED.format(others=F.noun(others, S.RPT_OTHER_BOOK, S.RPT_OTHER_BOOKS))


def cohort_years(ctx: Context) -> dict[int, int]:
    years: dict[int, int] = {}
    for year, entry in year_entries(ctx, S.ANX_COMPLETION_COHORTS).items():
        books = integer(mapping(entry).get(S.AN_CALC_N))
        if books is C.NONE or books <= C.ZERO:
            continue
        if ctx.year is not C.NONE and year > ctx.year:
            continue
        years[year] = books
    return years


def glance(ctx: Context) -> Chapter | None:
    summary = ctx.summary
    if summary.read == C.ZERO and summary.watchlist == C.ZERO:
        return Chapter(
            key=S.RPT_CHAPTER_EMPTY,
            title=S.RPT_EMPTY_TITLE,
            kicker=S.RPT_EMPTY_KICKER,
            blocks=(ProseBlock(paragraphs=(S.RPT_EMPTY_BODY,)),),
        )
    tiles = [stat(S.RPT_TILE_READ, F.count(summary.read), S.RPT_TILE_READ_DETAIL)]
    if summary.rated:
        share = F.percent(summary.rated, summary.read)
        detail = S.RPT_TILE_RATED_DETAIL.format(share=share)
        tiles.append(stat(S.RPT_TILE_RATED, F.count(summary.rated), detail, C.RptTone.TEAL))
    elif summary.read:
        tiles.append(stat(S.RPT_TILE_RATED, S.RPT_UNKNOWN, S.RPT_TILE_NO_RATINGS, C.RptTone.GREY))
    if summary.average is not C.NONE:
        detail = S.RPT_TILE_AVERAGE_DETAIL.format(median=F.trimmed(summary.median_rating or C.ZERO))
        value = S.RPT_OUT_OF_FIVE.format(value=F.trimmed(summary.average))
        tiles.append(stat(S.RPT_TILE_AVERAGE, value, detail, C.RptTone.TEAL))
    if summary.usual_rating is not C.NONE:
        detail = S.RPT_TILE_STANDOUT_DETAIL.format(
            part=F.count(summary.standout),
            total=F.count(summary.rated),
            rating=F.star_count(summary.usual_rating),
        )
        value = F.percent(summary.standout, summary.rated)
        tiles.append(stat(S.RPT_TILE_STANDOUT, value, detail, C.RptTone.TEAL))
    if summary.typical_pages is not C.NONE:
        detail = S.RPT_TILE_LENGTH_DETAIL.format(books=F.books(summary.pages_known))
        tiles.append(stat(S.RPT_TILE_LENGTH, F.pages(summary.typical_pages), detail))
    if pages_known(ctx):
        detail = S.RPT_TILE_PAGES_DETAIL.format(books=F.books(pages_known(ctx)))
        tiles.append(stat(S.RPT_TILE_PAGES, F.count(total_pages(ctx)), detail))
    if summary.distinct_authors:
        detail = S.RPT_TILE_AUTHORS_DETAIL.format(books=F.books(summary.authors_known))
        tiles.append(stat(S.RPT_TILE_AUTHORS, F.count(summary.distinct_authors), detail))
    if summary.genres:
        detail = S.RPT_TILE_GENRES_DETAIL.format(books=F.books(summary.genres_known))
        tiles.append(stat(S.RPT_TILE_GENRES, F.count(len(summary.genres)), detail))
    years = sorted_by_year(ctx)
    if len(years) >= C.TWO:
        low, high = ctx.plausible_year(years[C.ZERO]), ctx.plausible_year(years[-C.ONE])
        span = S.RPT_YEAR_SPAN.format(low=low, high=high)
        detail = S.RPT_TILE_ERAS_DETAIL.format(books=F.books(len(years)))
        tiles.append(stat(S.RPT_TILE_ERAS, span, detail))
    if summary.watchlist:
        detail = S.RPT_TILE_WATCH_DETAIL.format(
            familiar=F.count(summary.watchlist_familiar_authors)
        )
        tiles.append(stat(S.RPT_TILE_WATCH, F.count(summary.watchlist), detail, C.RptTone.AMBER))
    if summary.community_comparisons:
        count = F.count(len(summary.community_comparisons))
        tiles.append(stat(S.RPT_TILE_COMPARED, count, S.RPT_TILE_COMPARED_DETAIL, C.RptTone.SLATE))
    dated = sum(cohort_years(ctx).values())
    if dated:
        detail = S.RPT_TILE_DATED_DETAIL.format(read=F.count(summary.read))
        tiles.append(stat(S.RPT_TILE_DATED, F.count(dated), detail))
    return Chapter(
        key=S.RPT_CHAPTER_GLANCE,
        title=S.RPT_GLANCE_TITLE,
        kicker=S.RPT_GLANCE_KICKER,
        intro=S.RPT_GLANCE_INTRO,
        blocks=(TilesBlock(tiles=tuple(tiles)),),
    )


def facts(ctx: Context) -> Chapter | None:
    summary = ctx.summary
    found: list[Fact | None] = []
    by_pages = sorted_by_pages(ctx)
    if len(by_pages) >= C.TWO:
        longest, shortest = by_pages[-C.ONE], by_pages[C.ZERO]
        for headline, book in ((S.RPT_FACT_LONGEST, longest), (S.RPT_FACT_SHORTEST, shortest)):
            pages = F.pages(ctx.plausible_pages(book) or C.ZERO)
            tie = tie_text(ctx, by_pages, book, year=C.FALSE)
            found.append(book_fact(headline, S.RPT_FACT_PAGES, book, pages=pages, tie=tie))
    by_year = sorted_by_year(ctx)
    if len(by_year) >= C.TWO:
        oldest, newest = by_year[C.ZERO], by_year[-C.ONE]
        for headline, book in ((S.RPT_FACT_OLDEST, oldest), (S.RPT_FACT_NEWEST, newest)):
            year = str(ctx.plausible_year(book))
            tie = tie_text(ctx, by_year, book, year=C.TRUE)
            found.append(book_fact(headline, S.RPT_FACT_YEAR, book, year=year, tie=tie))
    if summary.usual_rating is not C.NONE:
        share = F.share_text(summary.standout, summary.rated)
        rating = F.star_count(summary.usual_rating)
        body = S.RPT_FACT_STANDOUT_BODY.format(rating=rating, share=share)
        found.append(fact(S.RPT_FACT_STANDOUT, body))
    found.append(leader_fact(summary.authors, S.RPT_FACT_AUTHOR, S.RPT_AUTHOR, S.RPT_AUTHORS))
    genre = leader_fact(summary.genres, S.RPT_FACT_GENRE, S.RPT_GENRE, S.RPT_GENRES)
    if genre is not C.NONE:
        note = S.RPT_GENRE_COVERAGE.format(
            known=F.count(summary.genres_known), read=F.count(summary.read)
        )
        genre = fact(genre.headline, genre.body + S.SPACE + note)
    found.append(genre)
    years = cohort_years(ctx)
    if years:
        top = max(years.values())
        busiest = sorted(year for year, books in years.items() if books == top)
        names = F.join_names(str(year) for year in busiest)
        body = S.RPT_FACT_BUSIEST_BODY.format(
            years=names, books=F.books(top), dated=F.books(sum(years.values()))
        )
        if ctx.year in busiest:
            body += S.SPACE + S.RPT_SO_FAR
        found.append(fact(S.RPT_FACT_BUSIEST, body, C.RptTone.AMBER))
    series = series_groups(ctx)
    if series:
        count = sum(len(entry) for entry in series.values())
        body = S.RPT_FACT_SERIES_BODY.format(books=F.books(count), series=len(series))
        found.append(fact(S.RPT_FACT_SERIES, body))
    known = summary.watchlist_familiar_authors + summary.watchlist_new_authors
    if known:
        share = F.share_text(summary.watchlist_familiar_authors, known)
        body = S.RPT_FACT_WATCH_BODY.format(share=share)
        if summary.watchlist_unknown_authors:
            body += S.SPACE + S.RPT_FACT_WATCH_UNKNOWN.format(
                unknown=F.books(summary.watchlist_unknown_authors)
            )
        found.append(fact(S.RPT_FACT_WATCH, body))
    kept = tuple(item for item in found if item is not C.NONE)
    if not kept:
        return C.NONE
    return Chapter(
        key=S.RPT_CHAPTER_FACTS,
        title=S.RPT_FACTS_TITLE,
        kicker=S.RPT_FACTS_KICKER,
        intro=S.RPT_FACTS_INTRO,
        blocks=(
            FactsBlock(
                facts=kept,
                note=S.RPT_FACTS_LENGTH_NOTE
                if C.ZERO < pages_known(ctx) < ctx.summary.read
                else S.EMPTY,
            ),
        ),
    )


def length_rows(ctx: Context) -> tuple[BarRow, ...]:
    summary = ctx.summary
    labels = {
        S.RD_SHORT: S.RPT_LENGTH_SHORT.format(limit=C.AN_CALC_SHORT_LIMIT),
        S.RD_MEDIUM: S.RPT_LENGTH_MEDIUM.format(
            low=C.AN_CALC_SHORT_LIMIT, high=C.AN_CALC_LONG_LIMIT - C.ONE
        ),
        S.RD_LONG: S.RPT_LENGTH_LONG.format(limit=C.AN_CALC_LONG_LIMIT),
    }
    bands = {group.label: group for group in summary.lengths}
    rows = [
        BarRow(
            label=label,
            value=float(bands[key].works),
            shown=F.count(bands[key].works),
            caption=average_caption(bands[key], ctx.minimum),
            sparse=is_sparse(bands[key].rated, ctx.minimum),
        )
        for key, label in labels.items()
        if key in bands
    ]
    unknown = summary.read - sum(group.works for group in summary.lengths)
    if unknown > C.ZERO:
        rows.append(
            BarRow(
                label=S.RPT_LENGTH_UNKNOWN,
                shown=F.count(unknown),
                caption=S.RPT_UNKNOWN_CAPTION,
                tone=C.RptTone.GREY,
            )
        )
    return tuple(rows)


def decade_rows(ctx: Context) -> tuple[tuple[BarRow, ...], int, int]:
    years = mapping(ctx.value(S.AN_PROFILE_FIRST_PUBLICATION).get(S.FIRST_PUBLICATION_YEAR))
    counts: Counter[int] = Counter()
    excluded = C.ZERO
    for key, value in years.items():
        year, books = whole(key), integer(value)
        if year is C.NONE or books is C.NONE:
            continue
        if year < C.RPT_MIN_YEAR or (ctx.year is not C.NONE and year > ctx.year):
            excluded += books
            continue
        counts[year // C.TEN * C.TEN] += books
    if not counts:
        return (), C.ZERO, excluded
    first, last = min(counts), max(counts)
    decades = list(range(first, last + C.TEN, C.TEN))
    cut = first
    if len(decades) > C.RPT_DECADE_LIMIT:
        cut = decades[-C.RPT_DECADE_LIMIT]
    rows: list[BarRow] = []
    older = sum(books for decade, books in counts.items() if decade < cut)
    if older:
        label = S.RPT_BEFORE.format(year=cut)
        rows.append(BarRow(label=label, value=float(older), shown=F.count(older)))
    for decade in decades:
        if decade >= cut:
            books = counts.get(decade, C.ZERO)
            label = S.RPT_DECADE.format(decade=decade)
            rows.append(BarRow(label=label, value=float(books), shown=F.count(books)))
    return tuple(rows), sum(counts.values()), excluded


def shape(ctx: Context) -> Chapter | None:
    if not ctx.read:
        return C.NONE
    blocks: list[Block] = []
    lengths = length_rows(ctx)
    if any(row.value is not C.NONE for row in lengths):
        note = S.RPT_LENGTH_NOTE.format(minimum=ctx.minimum)
        blocks.append(
            BarsBlock(heading=S.RPT_LENGTH_HEADING, rows=lengths, note=note, axis=S.RPT_AXIS_BOOKS)
        )
    pages = ctx.value(S.AN_CALC_STRUCTURE_PAGES)
    quartiles = (
        number(pages.get(S.AN_CALC_QUARTILE_LOW)),
        number(pages.get(S.AN_CALC_MEDIAN)),
        number(pages.get(S.AN_CALC_QUARTILE_HIGH)),
    )
    low, middle, high = quartiles
    if low is not C.NONE and middle is not C.NONE and high is not C.NONE:
        tiles = (
            stat(S.RPT_TILE_Q1, F.pages(low)),
            stat(S.RPT_TILE_MEDIAN, F.pages(middle), tone=C.RptTone.TEAL),
            stat(S.RPT_TILE_Q3, F.pages(high)),
        )
        note = S.RPT_QUARTILE_NOTE
        implausible = ctx.summary.pages_known - pages_known(ctx)
        if implausible > C.ZERO:
            note += S.SPACE + S.RPT_IMPLAUSIBLE_PAGES.format(
                books=F.books(implausible), low=C.RPT_MIN_PAGES, high=F.count(C.RPT_MAX_PAGES)
            )
        blocks.append(TilesBlock(heading=S.RPT_QUARTILE_HEADING, tiles=tiles, note=note))
    longest = list(reversed(sorted_by_pages(ctx)))[: C.RPT_LONGEST_LIMIT]
    if len(longest) >= C.THREE:
        books = tuple(
            item_of(book, F.pages(ctx.plausible_pages(book) or C.ZERO)) for book in longest
        )
        group = BookGroup(heading=S.EMPTY, books=books)
        blocks.append(
            BooksBlock(
                heading=S.RPT_LONGEST_HEADING,
                groups=(group,),
                note=S.RPT_LONGEST_NOTE.format(
                    known=F.count(pages_known(ctx)), read=F.count(ctx.summary.read)
                ),
            )
        )
    decades, known, excluded = decade_rows(ctx)
    if known >= C.TWO and len(decades) >= C.TWO:
        note = S.RPT_DECADE_NOTE.format(known=F.count(known), read=F.count(ctx.summary.read))
        if excluded:
            note += S.SPACE + S.RPT_DECADE_EXCLUDED.format(
                books=F.books(excluded), low=C.RPT_MIN_YEAR
            )
        blocks.append(
            BarsBlock(
                heading=S.RPT_DECADE_HEADING,
                style=C.RptBarStyle.VERTICAL,
                rows=decades,
                note=note,
                axis=S.RPT_AXIS_BOOKS,
            )
        )
    if not blocks:
        return C.NONE
    return Chapter(
        key=S.RPT_CHAPTER_SHAPE,
        title=S.RPT_SHAPE_TITLE,
        kicker=S.RPT_SHAPE_KICKER,
        intro=S.RPT_SHAPE_INTRO,
        blocks=tuple(blocks),
    )


def genres(ctx: Context) -> Chapter | None:
    summary = ctx.summary
    if not summary.genres:
        return C.NONE
    top = summary.genres[: C.RPT_GENRE_LIMIT]
    rows = [
        BarRow(
            label=F.sentence(group.label),
            value=float(group.works),
            shown=F.count(group.works),
            caption=average_caption(group, ctx.minimum),
            sparse=is_sparse(group.rated, ctx.minimum),
        )
        for group in top
    ]
    unknown = summary.read - summary.genres_known
    if unknown > C.ZERO:
        rows.append(
            BarRow(
                label=S.RPT_GENRE_UNKNOWN,
                shown=F.count(unknown),
                caption=S.RPT_UNKNOWN_CAPTION,
                tone=C.RptTone.GREY,
            )
        )
    note = S.RPT_GENRE_NOTE.format(
        known=F.count(summary.genres_known), read=F.count(summary.read), minimum=ctx.minimum
    )
    if len(summary.genres) > len(top):
        note += S.SPACE + S.RPT_GENRE_MORE.format(
            shown=len(top), total=F.count(len(summary.genres))
        )
    block = BarsBlock(
        heading=S.RPT_GENRE_HEADING, rows=tuple(rows), note=note, axis=S.RPT_AXIS_BOOKS
    )
    return Chapter(
        key=S.RPT_CHAPTER_GENRES,
        title=S.RPT_GENRES_TITLE,
        kicker=S.RPT_GENRES_KICKER,
        intro=S.RPT_GENRES_INTRO,
        blocks=(block,),
    )


def rating_axis(values: list[float]) -> list[float]:
    for step in C.RPT_RATING_STEPS:
        if all(abs(value / step - round(value / step)) < C.RPT_EPSILON for value in values):
            low, high = min(values), max(values)
            return [low + step * index for index in range(round((high - low) / step) + C.ONE)]
    return sorted(values)


def histogram(ctx: Context) -> dict[float, int]:
    raw = mapping(ctx.value(S.AN_CALC_RATINGS).get(S.AN_CALC_HISTOGRAM))
    parsed: dict[float, int] = {}
    for key, value in raw.items():
        rating, books = numeric(key), integer(value)
        if rating is not C.NONE and books is not C.NONE:
            parsed[rating] = books
    return parsed


def ratings(ctx: Context) -> Chapter | None:
    summary = ctx.summary
    if summary.read == C.ZERO:
        return C.NONE
    blocks: list[Block] = []
    counts = histogram(ctx)
    if counts:
        axis = rating_axis(list(counts))
        peak = max(counts.values())
        peak_ratings = [rating for rating, books in counts.items() if books == peak]
        rows = [
            BarRow(
                label=F.trimmed(rating),
                value=float(counts.get(rating, C.ZERO)),
                shown=F.count(counts.get(rating, C.ZERO)),
                tone=tier_tone(rating, summary.usual_rating),
            )
            for rating in axis
        ]
        note = S.RPT_HISTOGRAM_NOTE.format(rated=F.books(summary.rated))
        if summary.usual_rating is not C.NONE:
            note += S.SPACE + S.RPT_HISTOGRAM_TONES
        blocks.append(
            BarsBlock(
                heading=S.RPT_HISTOGRAM_HEADING,
                style=C.RptBarStyle.VERTICAL,
                rows=tuple(rows),
                note=note,
                axis=S.RPT_AXIS_BOOKS,
            )
        )
        if len(peak_ratings) == C.ONE:
            body = S.RPT_MOST_USED_ONE.format(
                rating=F.trimmed(peak_ratings[C.ZERO]), books=F.books(peak)
            )
        else:
            names = F.join_names(F.trimmed(rating) for rating in sorted(peak_ratings))
            body = S.RPT_MOST_USED_TIED.format(ratings=names, books=F.books(peak))
        found = [fact(S.RPT_FACT_MOST_USED, body)]
    else:
        found = []
    if summary.usual_rating is not C.NONE:
        body = S.RPT_TIERS_BODY.format(
            rating=F.star_count(summary.usual_rating),
            rated=F.books(summary.rated),
            standout=F.count(summary.standout),
            solid=F.count(summary.solid),
            below=F.count(summary.below_usual),
        )
        if summary.tied_usual_ratings:
            body += S.SPACE + S.RPT_TIERS_TIED
        found.append(fact(S.RPT_FACT_TIERS, body))
    unrated = summary.read - summary.rated
    if unrated > C.ZERO:
        body = S.RPT_UNRATED_BODY.format(books=F.books(unrated))
        if summary.conflicting_ratings:
            conflict = S.RPT_UNRATED_CONFLICT.format(books=F.books(summary.conflicting_ratings))
            body += S.SPACE + conflict
        found.append(fact(S.RPT_FACT_UNRATED, body, C.RptTone.AMBER))
    if found:
        blocks.append(FactsBlock(facts=tuple(found)))
    if not blocks:
        return C.NONE
    return Chapter(
        key=S.RPT_CHAPTER_RATINGS,
        title=S.RPT_RATINGS_TITLE,
        kicker=S.RPT_RATINGS_KICKER,
        intro=S.RPT_RATINGS_INTRO,
        blocks=tuple(blocks),
    )


def first_author(book: AnalysisBook) -> str:
    names = [name for name in (F.clean(author) for author in book.authors) if name]
    return names[C.ZERO] if names else S.RPT_UNKNOWN_AUTHOR_GROUP


def favorites(ctx: Context) -> Chapter | None:
    rated = ctx.rated()
    if not rated:
        return C.NONE
    top = max(book.rating or C.ZERO for book in rated)
    best = [book for book in rated if book.rating == top]
    shown = F.stable_pick(
        best, lambda book: book.book_id, C.RPT_FAVORITE_LIMIT, S.RPT_SALT_FAVORITES
    )
    by_author: dict[str, list[AnalysisBook]] = defaultdict(list)
    for book in shown:
        by_author[first_author(book)].append(book)
    groups: list[BookGroup] = []
    singles: list[AnalysisBook] = []
    for author, books in sorted(
        by_author.items(), key=lambda pair: (-len(pair[C.ONE]), pair[C.ZERO].casefold())
    ):
        if len(books) >= C.TWO and author != S.RPT_UNKNOWN_AUTHOR_GROUP:
            ordered = sorted(books, key=lambda book: (book.title.casefold(), book.work_id))
            heading = S.RPT_AUTHOR_HEADING.format(author=author, books=len(books))
            titles = tuple(BookItem(title=title_of(book)) for book in ordered)
            groups.append(BookGroup(heading=heading, books=titles))
        else:
            singles.extend(books)
    if singles:
        ordered = sorted(singles, key=lambda book: (book.title.casefold(), book.work_id))
        groups.append(
            BookGroup(heading=S.RPT_SINGLES_HEADING, books=tuple(item_of(book) for book in ordered))
        )
    stars = F.trimmed(top)
    rating = F.star_count(top)
    if len(shown) < len(best):
        note = S.RPT_FAVORITES_SAMPLE.format(
            shown=len(shown), total=F.books(len(best)), rating=rating
        )
    else:
        note = S.RPT_FAVORITES_ALL.format(total=F.books(len(best)), rating=rating)
    return Chapter(
        key=S.RPT_CHAPTER_FAVORITES,
        title=S.RPT_FAVORITES_TITLE.format(rating=stars),
        kicker=S.RPT_FAVORITES_KICKER,
        intro=S.RPT_FAVORITES_INTRO.format(rating=rating),
        blocks=(BooksBlock(groups=tuple(groups), note=note),),
    )


def series_groups(ctx: Context) -> dict[str, list[AnalysisBook]]:
    groups: dict[str, list[AnalysisBook]] = defaultdict(list)
    for book in ctx.read:
        membership = book.series
        if membership is C.NONE or membership.tier not in C.RPT_SERIES_TIERS:
            continue
        groups[F.clean(membership.name).casefold()].append(book)
    return groups


def series_rows(ctx: Context) -> tuple[tuple[BarRow, ...], int]:
    groups = series_groups(ctx)
    rows: list[tuple[int, str, BarRow]] = []
    for key, books in groups.items():
        names = sorted(F.clean(book.series.name) for book in books if book.series is not C.NONE)
        positions = sorted(
            {
                book.series.position_number
                for book in books
                if book.series is not C.NONE and book.series.position_number is not C.NONE
            }
        )
        caption = (
            S.RPT_SERIES_POSITIONS.format(
                positions=S.COMMA_SPACE.join(
                    S.RPT_POSITION.format(number=F.trimmed(position, C.ONE))
                    for position in positions
                )
            )
            if positions
            else S.RPT_SERIES_NO_POSITION
        )
        rows.append(
            (
                len(books),
                key,
                BarRow(
                    label=names[C.ZERO],
                    value=float(len(books)),
                    shown=F.count(len(books)),
                    caption=caption,
                ),
            )
        )
    ordered = sorted(rows, key=lambda row: (-row[C.ZERO], row[C.ONE]))
    unverified = sum(
        book.series is not C.NONE and book.series.tier not in C.RPT_SERIES_TIERS
        for book in ctx.read
    )
    return tuple(row[C.TWO] for row in ordered[: C.RPT_SERIES_LIMIT]), unverified


def authors(ctx: Context) -> Chapter | None:
    summary = ctx.summary
    blocks: list[Block] = []
    frequent = tuple(group for group in summary.authors if group.works >= C.RPT_AUTHOR_MINIMUM)
    if frequent:
        shown = frequent[: C.RPT_AUTHOR_LIMIT]
        rows = tuple(
            BarRow(
                label=group.label,
                value=float(group.works),
                shown=F.count(group.works),
                caption=average_caption(group, ctx.minimum),
                sparse=is_sparse(group.rated, ctx.minimum),
            )
            for group in shown
        )
        note = S.RPT_AUTHORS_NOTE.format(minimum=C.RPT_AUTHOR_MINIMUM)
        blocks.append(
            BarsBlock(heading=S.RPT_AUTHORS_HEADING, rows=rows, note=note, axis=S.RPT_AXIS_BOOKS)
        )
    series, unverified = series_rows(ctx)
    if series:
        note = S.RPT_SERIES_NOTE
        if unverified:
            note += S.SPACE + S.RPT_SERIES_UNVERIFIED.format(books=F.books(unverified))
        blocks.append(
            BarsBlock(heading=S.RPT_SERIES_HEADING, rows=series, note=note, axis=S.RPT_AXIS_BOOKS)
        )
    if not blocks:
        return C.NONE
    return Chapter(
        key=S.RPT_CHAPTER_AUTHORS,
        title=S.RPT_AUTHORS_TITLE,
        kicker=S.RPT_AUTHORS_KICKER,
        intro=S.RPT_AUTHORS_INTRO,
        blocks=tuple(blocks),
    )
