from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from statistics import mean, median

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisBook, AnalysisInput
from bookystats.domain.categories import analytical_categories
from bookystats.domain.identifiers import normalized_text
from bookystats.domain.models import FieldState, ReadingStatus, Source


class ReaderGroup(C.Model):
    label: str
    works: int
    rated: int
    favorites: int
    average: float | None = C.NONE
    adjusted_average: float | None = C.NONE
    difference_from_baseline: float | None = C.NONE
    examples: tuple[int, ...] = ()
    standouts: int = C.ZERO
    below_usual: int = C.ZERO


class ReaderComparison(C.Model):
    work_id: int
    personal: float
    community: float
    difference: float
    community_sample_size: int | None = C.NONE


class ReaderSummary(C.Model):
    read: int
    watchlist: int
    rated: int
    conflicting_ratings: int
    average: float | None = C.NONE
    median_rating: float | None = C.NONE
    most_used_rating: float | None = C.NONE
    most_used_rating_count: int
    favorites: int
    favorite_threshold: float
    pages_known: int
    typical_pages: float | None = C.NONE
    genres_known: int
    authors_known: int
    distinct_authors: int
    authors: tuple[ReaderGroup, ...]
    genres: tuple[ReaderGroup, ...]
    watchlist_genres: tuple[ReaderGroup, ...]
    lengths: tuple[ReaderGroup, ...]
    watchlist_familiar_authors: int
    watchlist_new_authors: int
    watchlist_unknown_authors: int
    favorite_examples: tuple[int, ...]
    community_comparisons: tuple[ReaderComparison, ...]
    usual_rating: float | None = C.NONE
    tied_usual_ratings: tuple[float, ...] = ()
    standout: int = C.ZERO
    solid: int = C.ZERO
    below_usual: int = C.ZERO
    standout_examples: tuple[int, ...] = ()


def _ratings(books: tuple[AnalysisBook, ...]) -> tuple[float, ...]:
    return tuple(
        book.rating for book in books if book.rating is not C.NONE and not book.rating_conflict
    )


def usual_rating(values: Iterable[float]) -> tuple[float, ...]:
    # Every most-used rating, lowest first; the first entry is the usual rating.
    histogram = Counter(values)
    if not histogram:
        return ()
    top = max(histogram.values())
    return tuple(sorted(rating for rating, count in histogram.items() if count == top))


def tier_counts(values: Iterable[float], usual: float | None) -> tuple[int, int, int]:
    # Standout (above), solid (equal) and below-usual counts relative to the usual rating.
    if usual is C.NONE:
        return (C.ZERO, C.ZERO, C.ZERO)
    items = tuple(values)
    return (
        sum(value > usual for value in items),
        sum(value == usual for value in items),
        sum(value < usual for value in items),
    )


def community_sample_size(book: AnalysisBook) -> int | None:
    # The single positive Goodreads ratings count behind the public average, else unknown.
    sizes = {
        item.observation.value
        for item in book.evidence
        if item.source == Source.GOODREADS.value
        and item.observation.field in C.AN3_SAMPLE_SIZE_FIELDS
        and item.observation.scope == S.WORK
        and item.observation.state == FieldState.PRESENT
        and type(item.observation.value) is int
        and item.observation.value > C.ZERO
    }
    return next(iter(sizes)) if len(sizes) == C.ONE else C.NONE


def _labels(book: AnalysisBook, field: str) -> tuple[str, ...]:
    if field == S.AUTHORS:
        return tuple(sorted({name.strip() for name in book.authors if name.strip()}))
    state = book.field_states.get(field)
    if state is not C.NONE and state != FieldState.PRESENT:
        return ()
    if field == S.GENRES:
        return analytical_categories(book.features.get(field, ()))
    if book.page_count is C.NONE:
        return ()
    if book.page_count < C.AN_CALC_SHORT_LIMIT:
        return (S.RD_SHORT,)
    if book.page_count < C.AN_CALC_LONG_LIMIT:
        return (S.RD_MEDIUM,)
    return (S.RD_LONG,)


def _examples(books: tuple[AnalysisBook, ...], limit: int) -> tuple[int, ...]:
    return tuple(
        book.work_id
        for book in sorted(
            (book for book in books if book.rating is not C.NONE and not book.rating_conflict),
            key=lambda book: (-(book.rating or C.ZERO), book.title.casefold(), book.work_id),
        )[:limit]
    )


def _groups(
    books: tuple[AnalysisBook, ...], field: str, data: AnalysisInput, usual: float | None
) -> tuple[ReaderGroup, ...]:
    groups: dict[str, list[AnalysisBook]] = defaultdict(list)
    names: dict[str, str] = {}
    settings = data.manifest.settings
    ratings = _ratings(books)
    baseline = mean(ratings) if ratings else C.NONE
    for book in books:
        for label in _labels(book, field):
            key = normalized_text(label)
            if not key:
                continue
            names[key] = min(names.get(key, label), label)
            if book not in groups[key]:
                groups[key].append(book)
    result: list[ReaderGroup] = []
    for key, group in groups.items():
        values = _ratings(tuple(group))
        standouts, _, below = tier_counts(values, usual)
        adjusted = (
            (sum(values) + settings.prior_strength * baseline)
            / (len(values) + settings.prior_strength)
            if baseline is not C.NONE and len(values) >= settings.min_group_size
            else C.NONE
        )
        result.append(
            ReaderGroup(
                label=names[key],
                works=len(group),
                rated=len(values),
                favorites=sum(value >= settings.high_rating_threshold for value in values),
                average=mean(values) if values else C.NONE,
                adjusted_average=adjusted,
                difference_from_baseline=adjusted - baseline
                if adjusted is not C.NONE and baseline is not C.NONE
                else C.NONE,
                examples=_examples(tuple(group), C.REC_EXAMPLE_LIMIT),
                standouts=standouts,
                below_usual=below,
            )
        )
    return tuple(sorted(result, key=lambda group: (-group.works, group.label.casefold())))


def build_reader_summary(data: AnalysisInput) -> ReaderSummary:
    books = {book.work_id: book for book in data.books}
    if len(books) != len(data.books):
        raise ValueError(S.RD_DUPLICATE)
    read = tuple(
        book
        for book in books.values()
        if S.READ in book.collections or book.status == ReadingStatus.READ
    )
    watch = tuple(
        book
        for book in books.values()
        if S.TO_READ in book.collections or book.status == ReadingStatus.TO_READ
    )
    ratings = _ratings(read)
    pages = tuple(
        book.page_count
        for book in read
        if book.page_count is not C.NONE
        and book.field_states.get(S.PAGE_COUNT, FieldState.PRESENT) == FieldState.PRESENT
    )
    authors = {normalized_text(author) for book in read for author in _labels(book, S.AUTHORS)}
    familiar = sum(
        bool({normalized_text(author) for author in _labels(book, S.AUTHORS)} & authors)
        for book in watch
    )
    unknown = sum(not _labels(book, S.AUTHORS) for book in watch)
    threshold = data.manifest.settings.high_rating_threshold
    histogram = Counter(ratings)
    ties = usual_rating(ratings)
    usual = ties[C.ZERO] if ties else C.NONE
    most_used = (
        min(histogram, key=lambda rating: (-histogram[rating], rating)) if histogram else C.NONE
    )
    standout, solid, below = tier_counts(ratings, usual)
    comparisons: list[ReaderComparison] = []
    for book in read:
        community = book.community_ratings.get(Source.GOODREADS.value)
        if (
            book.rating is C.NONE
            or book.rating_conflict
            or community is C.NONE
            or not C.ZERO <= community <= C.FIVE
        ):
            continue
        comparisons.append(
            ReaderComparison(
                work_id=book.work_id,
                personal=book.rating,
                community=community,
                difference=book.rating - community,
                community_sample_size=community_sample_size(book),
            )
        )
    return ReaderSummary(
        read=len(read),
        watchlist=len(watch),
        rated=len(ratings),
        conflicting_ratings=sum(book.rating_conflict for book in read),
        average=mean(ratings) if ratings else C.NONE,
        median_rating=median(ratings) if ratings else C.NONE,
        most_used_rating=most_used,
        most_used_rating_count=histogram.get(most_used, C.ZERO)
        if most_used is not C.NONE
        else C.ZERO,
        favorites=sum(value >= threshold for value in ratings),
        favorite_threshold=threshold,
        pages_known=len(pages),
        typical_pages=float(median(pages)) if pages else C.NONE,
        genres_known=sum(bool(_labels(book, S.GENRES)) for book in read),
        authors_known=sum(bool(_labels(book, S.AUTHORS)) for book in read),
        distinct_authors=len(authors),
        authors=_groups(read, S.AUTHORS, data, usual),
        genres=_groups(read, S.GENRES, data, usual),
        watchlist_genres=_groups(watch, S.GENRES, data, usual),
        lengths=_groups(read, S.PAGE_COUNT, data, usual),
        watchlist_familiar_authors=familiar,
        watchlist_new_authors=len(watch) - familiar - unknown,
        watchlist_unknown_authors=unknown,
        favorite_examples=_examples(
            tuple(
                book
                for book in read
                if book.rating is not C.NONE
                and not book.rating_conflict
                and book.rating >= threshold
            ),
            C.RD_EXAMPLE_LIMIT,
        ),
        community_comparisons=tuple(sorted(comparisons, key=lambda item: item.work_id)),
        usual_rating=usual,
        tied_usual_ratings=ties if len(ties) > C.ONE else (),
        standout=standout,
        solid=solid,
        below_usual=below,
        standout_examples=_examples(
            tuple(
                book
                for book in read
                if usual is not C.NONE
                and book.rating is not C.NONE
                and not book.rating_conflict
                and book.rating > usual
            ),
            C.RD_EXAMPLE_LIMIT,
        ),
    )
