from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from urllib.parse import urlsplit

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisEvidence,
    AnalysisInput,
    AnalyticsReport,
)
from bookystats.domain.categories import analytical_categories
from bookystats.domain.identifiers import normalized_isbns, normalized_text
from bookystats.domain.metadata import public_work_descriptor
from bookystats.domain.metadata_quality import (
    MetadataFieldCoverage,
    MetadataIdentitySummary,
    MetadataQualityDiagnostic,
    MetadataQualityReport,
    early_first_publication_year,
    implausible_page_count,
)
from bookystats.domain.models import FieldState, ReadingStatus, Source, canonical_json


def _read(book: AnalysisBook) -> bool:
    return book.status == ReadingStatus.READ or S.READ in book.collections


def _watchlist(book: AnalysisBook) -> bool:
    return S.TO_READ in book.collections


def _public_provider_origin(item: AnalysisEvidence) -> bool:
    url = item.observation.source_url
    if item.source == Source.OPEN_LIBRARY.value:
        return url in (
            S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=item.source_id),
            S.META_COVERAGE_WORK_DETAIL_URL.format(identifier=item.source_id),
        )
    if item.source == Source.GOOGLE_BOOKS.value:
        return url == S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE.format(v0=item.source_id)
    if item.source == Source.WIKIDATA.value:
        return (
            C.WIKIDATA_ENTITY_ID.fullmatch(item.source_id) is not C.NONE
            and url == S.WIKIDATA_WORK_URL.format(v0=item.source_id)
            and item.observation.scope == S.WORK
        )
    return C.FALSE


def _provider_sources(book: AnalysisBook) -> set[str]:
    return {
        item.source
        for item in book.evidence
        if item.source in C.ANALYTIC_CATEGORY_SOURCES and _public_provider_origin(item)
    }


def _provider_labels(book: AnalysisBook) -> bool:
    return any(
        item.source in C.ANALYTIC_CATEGORY_SOURCES
        and item.observation.field == S.GENRES
        and public_work_descriptor(item.source, item.source_id, item.observation)
        and item.observation.state == FieldState.PRESENT
        and _public_provider_origin(item)
        and any(
            isinstance(label, str) and label.strip()
            for label in (
                item.observation.value
                if isinstance(item.observation.value, list)
                else [item.observation.value]
            )
        )
        for item in book.evidence
    )


def _missing_cause(book: AnalysisBook, field: str, state: FieldState) -> str:
    if field == S.RATING:
        if book.rating_conflict:
            return S.MQ_REPORT_RATING_CONFLICT
        return S.L1_COV_CAUSE_NO_RATING if _read(book) else S.L1_COV_CAUSE_NOT_APPLICABLE
    if not _provider_sources(book):
        return S.L1_COV_CAUSE_NO_RECORD
    if field == S.GENRES and _provider_labels(book):
        return S.L1_COV_CAUSE_UNMAPPED
    if state == FieldState.FAILED:
        return S.L1_COV_CAUSE_FAILED
    if state == FieldState.UNSUPPORTED:
        return S.L1_COV_CAUSE_UNSUPPORTED
    return S.L1_COV_CAUSE_NO_VALUE


def _trusted(item: AnalysisEvidence, field: str) -> bool:
    if item.source in C.ANALYTIC_CATEGORY_SOURCES:
        return _public_provider_origin(item)
    if item.source == Source.STORYGRAPH.value:
        return field == S.RATING and item.observation.scope == S.READER
    if item.source == Source.GOODREADS.value:
        if field in (S.GENRES, S.SERIES, S.LANGUAGES):
            return C.FALSE
        try:
            url = urlsplit(item.public_url or item.observation.source_url)
            port = url.port
        except ValueError:
            return C.FALSE
        identity = C.BROWSER_BOOK_URL.fullmatch(url.path)
        return (
            url.scheme == S.HTTPS
            and url.hostname in (S.WWW_GOODREADS_COM, S.GOODREADS_COM)
            and not url.username
            and not url.password
            and port in (C.NONE, C.MODELS_ACCOUNT_VALID_PROFILE)
            and identity is not C.NONE
            and identity[C.ONE] == item.source_id
            and not url.query
            and not url.fragment
        )
    return C.FALSE


def _field_evidence(book: AnalysisBook, field: str, scope: str) -> tuple[AnalysisEvidence, ...]:
    aliases = (
        (S.FIRST_PUBLICATION_YEAR, S.IMPORT_BROWSER_FIRST_PUBLICATION)
        if field == S.FIRST_PUBLICATION_YEAR
        else (S.GENRES, S.ANALYTIC_CATEGORY_FIELD)
        if field == S.GENRES
        else (field,)
    )
    return tuple(
        item
        for item in book.evidence
        if item.observation.field in aliases
        and (
            item.observation.scope == scope
            or (
                scope == S.WORK
                and field in C.ENR_FALLBACK_FIELDS
                and public_work_descriptor(item.source, item.source_id, item.observation)
            )
        )
        and item.observation.state == FieldState.PRESENT
    )


def _value(book: AnalysisBook, field: str) -> JsonValue:
    if field == S.DESCRIPTION:
        return book.description
    if field == S.RATING:
        return book.rating
    if field == S.PAGE_COUNT:
        return book.page_count
    if field == S.PUBLICATION_DATE:
        return book.publication_year
    if field == S.FIRST_PUBLICATION_YEAR:
        return book.first_publication_year
    return list(book.features.get(field, ())) or C.NONE


def _backs(item: AnalysisEvidence, field: str, value: JsonValue) -> bool:
    observed = item.observation.value
    if field in (S.PUBLICATION_DATE, S.FIRST_PUBLICATION_YEAR):
        if not isinstance(observed, (str, int)) or isinstance(observed, bool):
            return C.FALSE
        text = str(observed).split(S.HYPHEN)[C.ZERO]
        return text.isdecimal() and int(text) == value
    if field in (S.GENRES, S.LANGUAGE, S.LANGUAGES, S.SERIES):
        labels = (
            [label for label in observed if isinstance(label, str)]
            if isinstance(observed, list)
            else [observed]
            if isinstance(observed, str)
            else []
        )
        normalized = (
            set(analytical_categories(labels))
            if field == S.GENRES
            else {S.SPACE.join(label.split()).casefold() for label in labels}
        )
        return isinstance(value, list) and bool(normalized.intersection(value))
    if (
        isinstance(observed, (int, float))
        and not isinstance(observed, bool)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        return observed == value
    return canonical_json(observed) == canonical_json(value)


def _coverage(
    books: tuple[AnalysisBook, ...], population_name: str
) -> tuple[MetadataFieldCoverage, ...]:
    rows: list[MetadataFieldCoverage] = []
    for field, scope in C.MQ_REPORT_FIELDS:
        states: Counter[str] = Counter()
        sources: Counter[str] = Counter()
        causes: Counter[str] = Counter()
        available = specific = C.ZERO
        for book in books:
            value = _value(book, field)
            present = value is not C.NONE and value != S.EMPTY and value != []
            state = (
                FieldState.PRESENT
                if present
                else book.field_states.get(field, FieldState.UNAVAILABLE)
            )
            if not present and state == FieldState.PRESENT:
                state = FieldState.FAILED
            states[state.value] += C.ONE
            available += present
            if present:
                sources.update(
                    {
                        item.source
                        for item in _field_evidence(book, field, scope)
                        if _trusted(item, field) and _backs(item, field, value)
                    }
                )
                if field == S.GENRES and isinstance(value, list):
                    specific += any(label not in C.L1_COV_BROAD_GENRES for label in value)
            else:
                causes[_missing_cause(book, field, state)] += C.ONE
        rows.append(
            MetadataFieldCoverage(
                field=field,
                scope=scope,
                population_name=population_name,
                population=len(books),
                available=available,
                missing=len(books) - available,
                states=dict(sorted(states.items())),
                sources=dict(sorted(sources.items())),
                missing_causes=dict(sorted(causes.items())),
                specific_available=specific if field == S.GENRES else C.NONE,
            )
        )
    return tuple(rows)


def _provider_values(book: AnalysisBook, field: str) -> dict[str, set[str]]:
    values: dict[str, set[str]] = defaultdict(set)
    for item in book.evidence:
        observation = item.observation
        if (
            item.source not in C.ANALYTIC_CATEGORY_SOURCES
            or observation.field != field
            or (
                observation.scope != S.WORK
                and not (field in C.MQ_REPORT_IDENTITY_FIELDS and observation.scope == S.EDITION)
            )
            or observation.state != FieldState.PRESENT
            or not _public_provider_origin(item)
        ):
            continue
        if field == S.TITLE and isinstance(observation.value, str):
            value = normalized_text(observation.value)
        elif field == S.AUTHORS and isinstance(observation.value, list):
            authors = sorted(
                {
                    normalized_text(author)
                    for author in observation.value
                    if isinstance(author, str) and normalized_text(author)
                }
            )
            if not authors:
                continue
            value = canonical_json(authors)
        elif field == S.FIRST_PUBLICATION_YEAR and type(observation.value) is int:
            value = str(observation.value)
        else:
            continue
        if value:
            values[item.source].add(value)
    return values


def build_metadata_quality(
    data: AnalysisInput,
    analysis: AnalyticsReport,
    provider_status: Mapping[str, JsonValue],
) -> MetadataQualityReport:
    if data.manifest != analysis.manifest or data.as_of != analysis.as_of:
        raise ValueError(S.MQ_REPORT_INPUT_MISMATCH)
    groups: dict[tuple[str, str | None], set[int]] = defaultdict(set)
    linked = cross = anchored = comparable = consistent = C.ZERO
    for book in data.books:
        providers = _provider_sources(book)
        linked += bool(providers)
        cross += len(providers) > C.ONE
        if any(
            item.observation.field == S.ISBNS
            and item.observation.state == FieldState.PRESENT
            and isinstance(item.observation.value, list)
            and normalized_isbns(
                tuple(value for value in item.observation.value if isinstance(value, str))
            )
            for item in book.evidence
        ):
            anchored += C.ONE
        compared = C.FALSE
        agrees = C.TRUE
        for field in C.MQ_REPORT_COMPARISON_FIELDS:
            values = _provider_values(book, field)
            if len(values) > C.ONE:
                compared = C.TRUE
                if len({value for items in values.values() for value in items}) != C.ONE:
                    agrees = C.FALSE
                    groups[(S.MQ_REPORT_PROVIDER_DISCREPANCY, field)].add(book.work_id)
        comparable += compared
        consistent += compared and agrees
        for field, scope in C.MQ_REPORT_FIELDS:
            value = _value(book, field)
            if value is C.NONE or value == S.EMPTY or value == []:
                continue
            evidence = _field_evidence(book, field, scope)
            backed = [item for item in evidence if _backs(item, field, value)]
            fully_backed = bool(backed) and (
                not isinstance(value, list)
                or all(any(_backs(item, field, [label]) for item in evidence) for label in value)
            )
            if not fully_backed:
                groups[(S.MQ_REPORT_UNBACKED, field)].add(book.work_id)
            elif not any(_trusted(item, field) for item in backed) or (
                isinstance(value, list)
                and not all(
                    any(_trusted(item, field) and _backs(item, field, [label]) for item in evidence)
                    for label in value
                )
            ):
                groups[(S.MQ_REPORT_UNTRUSTED, field)].add(book.work_id)
        if book.rating_conflict:
            groups[(S.MQ_REPORT_RATING_CONFLICT, S.RATING)].add(book.work_id)
        if (
            book.first_publication_year is not C.NONE
            and book.publication_year is not C.NONE
            and book.first_publication_year > book.publication_year
        ):
            groups[(S.MQ_REPORT_YEAR_ORDER, S.FIRST_PUBLICATION_YEAR)].add(book.work_id)
        if implausible_page_count(book.page_count):
            groups[(S.L1_COV_IMPLAUSIBLE_PAGES, S.PAGE_COUNT)].add(book.work_id)
        if early_first_publication_year(book.first_publication_year):
            groups[(S.L1_COV_EARLY_FIRST_PUBLICATION, S.FIRST_PUBLICATION_YEAR)].add(book.work_id)
        for item in book.evidence:
            observation = item.observation
            if observation.state != FieldState.PRESENT:
                continue
            if (
                item.source == Source.GOODREADS.value
                and observation.field == S.METADATA_PUBLICATION_CONFLICT
                and observation.value in (S.IMPORT_BROWSER_FIRST_PUBLICATION, S.PUBLICATION_DATE)
            ):
                field = (
                    S.FIRST_PUBLICATION_YEAR
                    if observation.value == S.IMPORT_BROWSER_FIRST_PUBLICATION
                    else S.PUBLICATION_DATE
                )
                groups[(S.METADATA_PUBLICATION_CONFLICT, field)].add(book.work_id)
            if item.source in C.ANALYTIC_CATEGORY_SOURCES:
                if not _public_provider_origin(item):
                    groups[(S.MQ_REPORT_PROVIDER_ORIGIN, observation.field)].add(book.work_id)
                if observation.scope == S.READER:
                    groups[(S.MQ_REPORT_READER_CONTAMINATION, observation.field)].add(book.work_id)
            elif (
                item.source == Source.STORYGRAPH.value
                and observation.field not in C.MQ_REPORT_STORYGRAPH_FIELDS
            ):
                groups[(S.MQ_REPORT_READER_CONTAMINATION, observation.field)].add(book.work_id)
            if item.source == Source.GOODREADS.value and observation.field in (S.GENRES, S.SERIES):
                groups[(S.MQ_REPORT_UNVERIFIED_LABELS, observation.field)].add(book.work_id)
    read = tuple(book for book in data.books if _read(book))
    watchlist = tuple(book for book in data.books if _watchlist(book))
    return MetadataQualityReport(
        as_of=data.as_of,
        manifest=data.manifest,
        analysis_report_id=analysis.report_id,
        population=len(data.books),
        read_works=len(read),
        watchlist_works=len(watchlist),
        coverage=(
            *_coverage(data.books, S.MQ_REPORT_ALL),
            *_coverage(read, S.READ),
            *_coverage(watchlist, S.TO_READ),
        ),
        identity=MetadataIdentitySummary(
            selected_metadata_records=len(data.manifest.metadata),
            provider_linked_works=linked,
            cross_provider_works=cross,
            identity_anchor_works=anchored,
            cross_provider_comparable_works=comparable,
            cross_provider_consistent_works=consistent,
        ),
        diagnostics=tuple(
            MetadataQualityDiagnostic(
                code=code,
                field=field,
                work_ids=tuple(sorted(work_ids)),
                count=len(work_ids),
                message=C.MQ_REPORT_DIAGNOSTIC_MESSAGES[code],
            )
            for (code, field), work_ids in sorted(
                groups.items(),
                key=lambda item: (item[C.ZERO][C.ZERO], item[C.ZERO][C.ONE] or S.EMPTY),
            )
        ),
        capabilities=(*analysis.taste.capabilities, *analysis.watchlist.capabilities),
        provider_status=dict(provider_status),
        limitations=C.L1_COV_LIMITATIONS,
    )
