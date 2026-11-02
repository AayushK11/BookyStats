from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.dates import parse_date
from bookystats.domain.errors import ConnectorError
from bookystats.domain.identifiers import normalize_isbn
from bookystats.domain.interfaces import ProgressCallback
from bookystats.domain.models import (
    Account,
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    FieldState,
    Issue,
    Observation,
    PartialDate,
    ReadingEvent,
    ReadingStatus,
    Source,
    SyncState,
    utc_now,
)
from bookystats.persistence.raw import RawDocument, RawStore, RawStoreError


class FileExportConnector:
    def __init__(
        self,
        archive: RawStore,
        path: Path | None,
        *,
        collection: str,
        on_capture: Callable[[RawDocument], None],
    ) -> None:
        self.archive = archive
        self.path = path
        self.collection = collection
        self.on_capture = on_capture

    def collect(
        self,
        account: Account,
        *,
        interactive: bool = C.FALSE,
        on_progress: ProgressCallback | None = C.NONE,
    ) -> CollectionSnapshot:
        started = utc_now()
        document: RawDocument | None = C.NONE
        try:
            if self.path is C.NONE:
                raise ConnectorError(
                    S.CSV_INPUT_NOT_CONFIGURED.format(
                        source=account.source.value, collection=self.collection
                    ),
                    state=SyncState.NOT_CONFIGURED,
                    code=S.CSV_INPUT_NOT_CONFIGURED_CODE,
                )
            document = self.archive.capture_file(account, self.path, collection=self.collection)
            self.on_capture(document)
            return ExportConnector(document).collect(
                account, interactive=interactive, on_progress=on_progress
            )
        except RawStoreError:
            error = ConnectorError(
                S.CSV_INPUT_UNAVAILABLE.format(filename=self.path.name if self.path else S.EMPTY),
                code=S.CSV_INPUT_UNAVAILABLE_CODE,
            )
        except ConnectorError as exc:
            error = exc
        return CollectionSnapshot(
            source=account.source,
            account_id=account.account_id,
            collection=self.collection,
            state=error.state,
            started_at=started,
            finished_at=utc_now(),
            input_kind=S.INPUT_FILE,
            raw_document_id=document.id if document is not C.NONE else C.NONE,
            processing_version=S.IMPORT_PROCESSING_VERSION,
            issues=(Issue(code=error.code, message=str(error), retryable=error.retryable),),
        )


def _validate_quoting(text: str) -> None:
    # csv.reader(strict=True) still accepts quotes inside unquoted fields.
    state = C.IMPORT_CSV_START
    for char in text:
        if state == C.IMPORT_CSV_QUOTED:
            if char == S.IMPORT_QUOTE:
                state = C.IMPORT_CSV_AFTER_QUOTE
        elif char == S.IMPORT_QUOTE:
            if state not in C.IMPORT_QUOTE_START_STATES:
                raise ConnectorError(S.IMPORT_CSV_MESSAGE, code=S.IMPORT_CSV_ERROR)
            state = C.IMPORT_CSV_QUOTED
        elif char == S.COMMA or char in C.IMPORT_NEWLINES:
            state = C.IMPORT_CSV_START
        elif state == C.IMPORT_CSV_AFTER_QUOTE:
            raise ConnectorError(S.IMPORT_CSV_MESSAGE, code=S.IMPORT_CSV_ERROR)
        else:
            state = C.IMPORT_CSV_UNQUOTED
    if state == C.IMPORT_CSV_QUOTED:
        raise ConnectorError(S.IMPORT_CSV_MESSAGE, code=S.IMPORT_CSV_ERROR)


def _csv_rows(body: bytes) -> Iterator[list[str]]:
    try:
        text = body.decode(S.UTF_8_SIG)
    except UnicodeDecodeError as exc:
        raise ConnectorError(S.IMPORT_ENCODING_MESSAGE, code=S.IMPORT_ENCODING_ERROR) from exc
    if S.IMPORT_NUL in text:
        raise ConnectorError(S.IMPORT_ENCODING_MESSAGE, code=S.IMPORT_ENCODING_ERROR)
    _validate_quoting(text)
    try:
        yield from csv.reader(io.StringIO(text, newline=S.EMPTY), strict=C.TRUE)
    except csv.Error as exc:
        raise ConnectorError(S.IMPORT_CSV_MESSAGE, code=S.IMPORT_CSV_ERROR) from exc


def _storygraph_read_scope(status: str | None, number: int) -> bool:
    key = S.SPACE.join((status or S.EMPTY).casefold().replace(S.HYPHEN, S.SPACE).split())
    parsed = C.IMPORT_STATUS_NAMES.get(key)
    if parsed is C.NONE:
        raise ConnectorError(
            S.STORYGRAPH_READ_SCOPE_INVALID_MESSAGE.format(row=number),
            code=S.STORYGRAPH_READ_SCOPE_INVALID_CODE,
        )
    return parsed == ReadingStatus.READ


def count_export_rows(body: bytes, *, source: Source | None = C.NONE) -> int:
    rows = _csv_rows(body)
    headers = next(rows, C.NONE)
    if source != Source.STORYGRAPH:
        return sum(C.ONE for _ in rows)
    normalized = [header.strip().casefold() for header in headers] if headers else []
    if S.IMPORT_READ_STATUS.casefold() not in normalized:
        raise ConnectorError(S.IMPORT_SCHEMA_MESSAGE, code=S.IMPORT_SCHEMA_ERROR)
    status_index = normalized.index(S.IMPORT_READ_STATUS.casefold())
    count = C.ZERO
    for number, values in enumerate(rows, start=C.TWO):
        if len(values) != len(normalized):
            raise ConnectorError(
                S.IMPORT_WIDTH_MESSAGE.format(
                    row=number, actual=len(values), expected=len(normalized)
                ),
                code=S.IMPORT_CSV_ERROR,
            )
        if _storygraph_read_scope(values[status_index], number):
            count += C.ONE
    return count


class _ExportRow:
    def __init__(
        self, raw: dict[str, str], number: int, account: Account, document: RawDocument
    ) -> None:
        self.raw = raw
        self.values = {header.strip().casefold(): value for header, value in raw.items()}
        self.number = number
        self.account = account
        self.document = document
        self.observations: list[Observation] = []
        self.issues: list[Issue] = []
        self.observation_url = document.origin
        self.observed_at = document.captured_at

    def get(self, header: str) -> str | None:
        return self.values.get(header.casefold())

    def invalid(self, header: str, code: str = S.INVALID_RECORD) -> ConnectorError:
        return ConnectorError(
            S.IMPORT_INVALID_MESSAGE.format(row=self.number, field=header), code=code
        )

    def issue(self, code: str, message: str, *, field: str = S.EMPTY) -> None:
        self.issues.append(Issue(code=code, message=message.format(row=self.number, field=field)))

    def observe(
        self,
        field: str,
        value: JsonValue,
        scope: S.ObservationScope,
        state: FieldState = FieldState.PRESENT,
    ) -> None:
        self.observations.append(
            Observation(
                field=field,
                value=value,
                scope=scope,
                state=state,
                source_url=self.observation_url,
                observed_at=self.observed_at,
            )
        )

    def absent(self, header: str, field: str, scope: S.ObservationScope) -> bool:
        raw = self.get(header)
        if raw is C.NONE or not raw.strip():
            self.observe(
                field,
                C.NONE,
                scope,
                FieldState.UNSUPPORTED if raw is C.NONE else FieldState.EMPTY,
            )
            return C.TRUE
        return C.FALSE

    def text(
        self, header: str, field: str, scope: S.ObservationScope, *, verbatim: bool = C.FALSE
    ) -> str | None:
        if self.absent(header, field, scope):
            return C.NONE
        raw = self.get(header)
        assert raw is not C.NONE
        value = raw if verbatim else raw.strip()
        self.observe(field, value, scope)
        return value

    def number_value(
        self, header: str, *, fractional: bool = C.FALSE, maximum: int | None = C.NONE
    ) -> Decimal:
        raw = (self.get(header) or S.EMPTY).strip()
        pattern = C.IMPORT_DECIMAL if fractional else C.IMPORT_INTEGER
        if len(raw) > C.IMPORT_MAX_NUMBER_LENGTH or not pattern.fullmatch(raw):
            raise self.invalid(header, S.INVALID_NUMBER)
        value = Decimal(raw)
        if maximum is not C.NONE and value > maximum:
            raise self.invalid(header, S.INVALID_NUMBER)
        return value

    def number_field(
        self,
        header: str,
        field: str,
        scope: S.ObservationScope,
        *,
        fractional: bool = C.FALSE,
        maximum: int | None = C.NONE,
        zero_empty: bool = C.FALSE,
        zero_unknown: bool = C.FALSE,
        quarters: bool = C.FALSE,
    ) -> int | float | None:
        if self.absent(header, field, scope):
            return C.NONE
        value = self.number_value(header, fractional=fractional, maximum=maximum)
        numerator, denominator = value.as_integer_ratio()
        if quarters and numerator * C.IMPORT_RATING_QUARTERS % denominator:
            raise self.invalid(header, S.INVALID_NUMBER)
        if value == C.ZERO and (zero_empty or zero_unknown):
            self.observe(
                field, C.NONE, scope, FieldState.UNAVAILABLE if zero_unknown else FieldState.EMPTY
            )
            if zero_unknown:
                self.issue(S.IMPORT_UNKNOWN_NUMBER, S.IMPORT_UNKNOWN_NUMBER_MESSAGE, field=header)
            return C.NONE
        result = float(value) if fractional else int(value)
        self.observe(field, result, scope)
        return result

    def date_value(self, header: str) -> PartialDate | None:
        try:
            return parse_date(self.get(header))
        except (ValueError, OverflowError) as exc:
            raise self.invalid(header, S.INVALID_DATE) from exc

    def added_date(self) -> PartialDate | None:
        if self.absent(S.IMPORT_DATE_ADDED, S.ADDED_AT, S.READER):
            return C.NONE
        date = self.date_value(S.IMPORT_DATE_ADDED)
        assert date is not C.NONE
        self.observe(S.ADDED_AT, date.value, S.READER)
        return date

    def year(self, header: str, field: str, scope: S.ObservationScope) -> None:
        if self.absent(header, field, scope):
            return
        year = int(self.number_value(header, maximum=C.IMPORT_MAX_YEAR))
        if year == C.ZERO:
            self.observe(field, C.NONE, scope, FieldState.UNAVAILABLE)
            self.issue(S.IMPORT_UNKNOWN_NUMBER, S.IMPORT_UNKNOWN_NUMBER_MESSAGE, field=header)
        else:
            date = parse_date(S.IMPORT_YEAR_TEMPLATE.format(year=year))
            assert date is not C.NONE
            self.observe(field, date.value, scope)

    def authors(self) -> tuple[str, ...]:
        header = C.IMPORT_AUTHOR_HEADERS[self.account.source]
        raw = self.get(header)
        values: list[str] = []
        if raw and raw.strip():
            if self.account.source == Source.GOODREADS:
                values.append(raw.strip())
            else:
                values.extend(C.IMPORT_LIST_SEPARATOR.split(raw.strip()))
        additional = self.get(S.IMPORT_ADDITIONAL_AUTHORS)
        if self.account.source == Source.GOODREADS and additional and additional.strip():
            values.extend(C.IMPORT_LIST_SEPARATOR.split(additional.strip()))
        authors = tuple(dict.fromkeys(value for value in values if value))
        self.observe(
            S.AUTHORS,
            list(authors) if authors else C.NONE,
            S.WORK,
            FieldState.PRESENT
            if authors
            else FieldState.UNSUPPORTED
            if raw is C.NONE and additional is C.NONE
            else FieldState.EMPTY,
        )
        return authors

    def identifiers(self) -> tuple[tuple[str, ...], str | None]:
        isbns: set[str] = set()
        uid: str | None = C.NONE
        headers = C.IMPORT_ISBN_HEADERS[self.account.source]
        any_value = C.FALSE
        for header in headers:
            raw = self.get(header)
            if raw is C.NONE or not raw.strip():
                continue
            value = raw.strip()
            wrapper = C.IMPORT_ISBN_WRAPPER.fullmatch(value)
            if wrapper:
                value = wrapper[C.ONE]
                if not value:
                    continue
            any_value = C.TRUE
            isbn = normalize_isbn(value)
            if isbn is not C.NONE:
                isbns.add(isbn)
                continue
            compact = value.replace(S.HYPHEN, S.EMPTY).replace(S.SPACE, S.EMPTY)
            if (
                self.account.source == Source.STORYGRAPH
                and wrapper is C.NONE
                and C.IMPORT_UID.fullmatch(value)
                and not C.IMPORT_ISBN_SHAPE.fullmatch(compact)
            ):
                uid = value
            elif self.account.source == Source.STORYGRAPH:
                self.issue(S.INVALID_ISBN, S.IMPORT_STORYGRAPH_INVALID_IDENTIFIER, field=header)
            else:
                raise self.invalid(header, S.INVALID_ISBN)
        if self.account.source == Source.GOODREADS and len(isbns) > C.ONE:
            raise self.invalid(S.IMPORT_ISBN13, S.INVALID_ISBN)
        identifiers: list[JsonValue] = [isbn for isbn in sorted(isbns)]
        self.observe(
            S.ISBNS,
            identifiers if isbns else C.NONE,
            S.EDITION,
            FieldState.PRESENT
            if isbns
            else FieldState.UNAVAILABLE
            if any_value
            else FieldState.EMPTY
            if any(self.get(header) is not C.NONE for header in headers)
            else FieldState.UNSUPPORTED,
        )
        return tuple(sorted(isbns)), uid

    def identity(
        self,
        title: str,
        authors: tuple[str, ...],
        edition_format: str | None,
        isbns: tuple[str, ...],
        uid: str | None,
    ) -> tuple[str, str]:
        native = uid
        url_template = S.IMPORT_STORYGRAPH_URL
        if self.account.source == Source.GOODREADS:
            native = (self.get(S.IMPORT_BOOK_ID) or S.EMPTY).strip() or C.NONE
            if native is not C.NONE:
                if (
                    len(native) > C.IMPORT_MAX_NUMBER_LENGTH
                    or not C.IMPORT_INTEGER.fullmatch(native)
                    or not int(native)
                ):
                    raise self.invalid(S.IMPORT_BOOK_ID)
                native = str(int(native))
            url_template = S.IMPORT_GOODREADS_URL
        if native is not C.NONE:
            source_id = native
            kind = S.IMPORT_NATIVE_IDENTITY
            url = url_template.format(source_id=quote(source_id, safe=S.EMPTY))
        elif isbns:
            source_id = S.IMPORT_ISBN_ID.format(isbn=isbns[C.ZERO])
            kind = S.IMPORT_ISBN_IDENTITY
            url = self.account.profile_url
        else:
            identity = json.dumps(
                [
                    self.account.source,
                    self.account.account_id,
                    title,
                    sorted(authors),
                    edition_format,
                ],
                ensure_ascii=C.FALSE,
            )
            source_id = S.IMPORT_SYNTHETIC_ID.format(
                digest=hashlib.sha256(identity.encode(S.UTF_8)).hexdigest()
            )
            kind = S.IMPORT_SYNTHETIC_IDENTITY
            url = self.account.profile_url
            self.issue(S.IMPORT_SYNTHETIC_NOTICE, S.IMPORT_SYNTHETIC_MESSAGE)
        self.observe(S.IMPORT_IDENTITY_FIELD, kind, S.EDITION)
        return source_id, url

    def status(self) -> ReadingStatus:
        header = C.IMPORT_STATUS_HEADERS[self.account.source]
        if self.absent(header, S.STATUS, S.READER):
            return ReadingStatus.UNKNOWN
        raw = self.get(header)
        assert raw is not C.NONE
        key = S.SPACE.join(raw.casefold().replace(S.HYPHEN, S.SPACE).split())
        status = C.IMPORT_STATUS_NAMES.get(key)
        if status is C.NONE:
            self.observe(S.STATUS, C.NONE, S.READER, FieldState.UNAVAILABLE)
            self.issue(S.IMPORT_UNKNOWN_STATUS, S.IMPORT_UNKNOWN_STATUS_MESSAGE)
            return ReadingStatus.UNKNOWN
        self.observe(S.STATUS, status.value, S.READER)
        return status

    def shelves(self) -> tuple[tuple[str, ...], int | None]:
        shelves: list[str] = []
        raw = self.get(S.IMPORT_BOOKSHELVES)
        if raw and raw.strip():
            shelves.extend(value.strip() for value in raw.split(S.COMMA) if value.strip())
        exclusive = (self.get(S.IMPORT_EXCLUSIVE_SHELF) or S.EMPTY).strip()
        if exclusive:
            shelves.append(exclusive)
        unique = tuple(dict.fromkeys(shelves))
        self.observe(
            S.SHELVES,
            list(unique) if unique else C.NONE,
            S.READER,
            FieldState.PRESENT
            if unique
            else FieldState.UNSUPPORTED
            if raw is C.NONE and self.get(S.IMPORT_EXCLUSIVE_SHELF) is C.NONE
            else FieldState.EMPTY,
        )
        positions: dict[str, JsonValue] = {}
        shelf_position: int | None = C.NONE
        if not self.absent(S.IMPORT_POSITIONS, S.IMPORT_POSITIONS_FIELD, S.READER):
            for value in (self.get(S.IMPORT_POSITIONS) or S.EMPTY).split(S.COMMA):
                match = C.IMPORT_POSITION.fullmatch(value.strip())
                if (
                    match is C.NONE
                    or match[C.ONE] in positions
                    or len(match[C.TWO]) > C.IMPORT_MAX_NUMBER_LENGTH
                ):
                    raise self.invalid(S.IMPORT_POSITIONS)
                positions[match[C.ONE]] = int(match[C.TWO])
                if match[C.ONE] == exclusive:
                    shelf_position = int(match[C.TWO])
            self.observe(S.IMPORT_POSITIONS_FIELD, positions, S.READER)
        return unique, shelf_position

    def reading_events(
        self, source_id: str, read_count: int | float | None
    ) -> tuple[ReadingEvent, ...]:
        header = S.IMPORT_DATE_READ
        last = self.date_value(header)
        dates = [last] if last is not C.NONE else []
        incomplete = C.FALSE
        if read_count is not C.NONE:
            if read_count < len(dates):
                raise self.invalid(S.IMPORT_READ_COUNT, S.IMPORT_HISTORY_CONFLICT)
            if read_count > len(dates):
                incomplete = C.TRUE
                self.issue(S.IMPORT_HISTORY_INCOMPLETE, S.IMPORT_HISTORY_INCOMPLETE_MESSAGE)
        events = tuple(
            ReadingEvent(
                source_event_id=S.IMPORT_EVENT_ID.format(source_id=source_id, date=date.value),
                finished=date,
                status=ReadingStatus.READ,
            )
            for date in dates
        )
        supported = self.get(header) is not C.NONE
        state = (
            FieldState.UNAVAILABLE
            if incomplete
            else FieldState.PRESENT
            if events
            else FieldState.EMPTY
            if supported
            else FieldState.UNSUPPORTED
        )
        self.observe(
            S.READING_EVENTS,
            [event.model_dump(mode=S.JSON) for event in events]
            if state == FieldState.PRESENT
            else C.NONE,
            S.READER,
            state,
        )
        return events

    def goodreads_metadata(self) -> None:
        for header, field, scope in C.IMPORT_GOODREADS_TEXT_FIELDS:
            self.text(header, field, scope, verbatim=C.TRUE)
        self.number_field(
            S.IMPORT_AVERAGE_RATING,
            S.COMMUNITY_RATING,
            S.WORK,
            fractional=C.TRUE,
            maximum=C.FIVE,
        )
        self.number_field(S.IMPORT_PAGES, S.PAGE_COUNT, S.EDITION, zero_unknown=C.TRUE)
        self.number_field(S.IMPORT_OWNED_COPIES, S.IMPORT_OWNED_COPIES_FIELD, S.READER)
        self.year(S.IMPORT_YEAR, S.PUBLICATION_DATE, S.EDITION)
        self.year(S.IMPORT_ORIGINAL_YEAR, S.IMPORT_ORIGINAL_PUBLICATION_FIELD, S.WORK)
        if not self.absent(S.IMPORT_SPOILER, S.IMPORT_SPOILER_FIELD, S.READER):
            value = (self.get(S.IMPORT_SPOILER) or S.EMPTY).strip().casefold()
            if value not in C.IMPORT_BOOLEAN_VALUES:
                raise self.invalid(S.IMPORT_SPOILER)
            self.observe(S.IMPORT_SPOILER_FIELD, C.IMPORT_BOOLEAN_VALUES[value], S.READER)

    def parse(self) -> BookRecord:
        source = self.account.source
        title = self.text(S.IMPORT_TITLE, S.TITLE, S.WORK)
        if title is C.NONE:
            raise self.invalid(S.IMPORT_TITLE)
        authors = self.authors()
        edition_format = (
            self.text(C.IMPORT_FORMAT_HEADERS[source], S.EDITION_FORMAT, S.EDITION)
            if source == Source.GOODREADS
            else C.NONE
        )
        isbns, uid = self.identifiers()
        source_id, url = self.identity(title, authors, edition_format, isbns, uid)
        if source == Source.STORYGRAPH:
            self.number_field(
                S.IMPORT_STAR_RATING,
                S.RATING,
                S.READER,
                fractional=C.TRUE,
                maximum=C.FIVE,
                quarters=C.TRUE,
            )
            return BookRecord(
                source=source,
                source_id=source_id,
                title=title,
                authors=authors,
                url=url,
                isbns=isbns,
                collections=C.IMPORT_COLLECTIONS,
                observations=tuple(self.observations),
                raw_fields=dict(self.raw),
            )
        status = self.status()
        added_at = self.added_date()
        self.number_field(
            C.IMPORT_RATING_HEADERS[source],
            C.IMPORT_RATING_FIELDS[source],
            S.READER,
            fractional=C.FALSE,
            maximum=C.FIVE,
            zero_empty=C.TRUE,
        )
        self.text(C.IMPORT_REVIEW_HEADERS[source], S.REVIEW, S.READER, verbatim=C.TRUE)
        read_count = self.number_field(S.IMPORT_READ_COUNT, S.READ_COUNT, S.READER)
        events = self.reading_events(source_id, read_count)
        shelves, shelf_position = self.shelves()
        self.goodreads_metadata()
        return BookRecord(
            source=source,
            source_id=source_id,
            title=title,
            authors=authors,
            url=url,
            status=status,
            raw_status=self.get(C.IMPORT_STATUS_HEADERS[source]),
            isbns=isbns,
            edition_format=edition_format,
            collections=C.IMPORT_COLLECTIONS,
            shelves=shelves,
            shelf_position=shelf_position,
            added_at=added_at,
            observations=tuple(self.observations),
            reading_events=events,
            raw_fields={header: value for header, value in self.raw.items()},
        )

    def browser_export(self) -> BookRecord:
        if self.document.collection not in (S.TO_READ, S.READ):
            raise ConnectorError(S.IMPORT_BROWSER_SCOPE_ERROR, code=S.IMPORT_SCHEMA_ERROR)
        url = (self.get(S.IMPORT_BROWSER_URL) or S.EMPTY).strip()
        parsed = urlsplit(url)
        identity = C.BROWSER_BOOK_URL.fullmatch(parsed.path)
        if (
            parsed.scheme != S.HTTPS
            or parsed.hostname not in (S.WWW_GOODREADS_COM, S.GOODREADS_COM)
            or parsed.username
            or parsed.password
            or parsed.port not in (C.NONE, C.MODELS_ACCOUNT_VALID_PROFILE)
            or parsed.query
            or parsed.fragment
            or identity is C.NONE
            or not int(identity[C.ONE])
        ):
            raise self.invalid(S.IMPORT_BROWSER_URL)
        self.values[S.IMPORT_BOOK_ID.casefold()] = str(int(identity[C.ONE]))
        self.values[S.IMPORT_EXCLUSIVE_SHELF.casefold()] = self.document.collection
        structured = any(
            self.get(header) is not C.NONE for header in C.GOODREADS_EXPORT_STRUCTURED_HEADERS
        )
        if structured:
            self.browser_provenance()
        # These official-export columns are not browser evidence. In particular,
        # flattened star widgets and row text never become personal facts.
        for header in (
            C.IMPORT_REVIEW_HEADERS[Source.GOODREADS],
            S.IMPORT_DATE_READ,
            S.IMPORT_READ_COUNT,
            C.IMPORT_RATING_HEADERS[Source.GOODREADS],
        ):
            self.values.pop(header.casefold(), C.NONE)
        author = (self.get(S.IMPORT_AUTHOR) or S.EMPTY).strip()
        if author.count(S.COMMA) == C.ONE:
            family, given = author.split(S.COMMA, C.ONE)
            if family.strip() and given.strip():
                self.values[S.IMPORT_AUTHOR.casefold()] = given.strip() + S.SPACE + family.strip()
        details = self.get(S.IMPORT_BROWSER_DETAILS) or S.EMPTY
        extracted = {
            field: match[S.VALUE]
            for field, pattern in C.BROWSER_ROW_PATTERNS.items()
            if (match := pattern.search(details)) is not C.NONE
        }
        for field in (S.IMPORT_ISBN, S.IMPORT_ISBN13):
            direct = self.get(field)
            if direct and direct.strip():
                # Both independent observations must identify the same edition.
                if field in extracted and normalize_isbn(direct) != normalize_isbn(
                    extracted[field]
                ):
                    raise self.invalid(field, S.INVALID_ISBN)
            elif field in extracted:
                self.values[field.casefold()] = extracted[field]
        for field in (S.IMPORT_DATE_ADDED, S.IMPORT_BINDING):
            self.values[field.casefold()] = extracted.get(field, S.EMPTY)
        direct_format = self.get(S.IMPORT_FORMAT)
        if direct_format and direct_format.strip():
            if (
                extracted.get(S.IMPORT_BINDING)
                and direct_format.strip() != extracted[S.IMPORT_BINDING]
            ):
                raise self.invalid(S.IMPORT_FORMAT)
            self.values[S.IMPORT_BINDING.casefold()] = direct_format
        for field, header in (
            (S.IMPORT_AVERAGE_RATING, S.IMPORT_BROWSER_AVERAGE),
            (S.RATINGS_COUNT, S.IMPORT_BROWSER_RATINGS),
        ):
            direct = (self.get(header) or S.EMPTY).strip()
            recovered = extracted.get(field, S.EMPTY)
            if (
                direct
                and recovered
                and direct.replace(S.COMMA, S.EMPTY) != recovered.replace(S.COMMA, S.EMPTY)
            ):
                raise self.invalid(header)
            self.values[field.casefold()] = (direct or recovered).replace(S.COMMA, S.EMPTY)
        page_text = (self.get(S.IMPORT_BROWSER_PAGES) or S.EMPTY).strip()
        page_match = C.BROWSER_PAGE_DETAILS.match(page_text)
        pages = (
            page_text
            if C.IMPORT_INTEGER.fullmatch(page_text)
            else (page_match[S.VALUE] if page_match else S.EMPTY)
        )
        if pages and extracted.get(S.IMPORT_PAGES) and pages != extracted[S.IMPORT_PAGES]:
            raise self.invalid(S.IMPORT_PAGES)
        self.values[S.IMPORT_PAGES.casefold()] = pages or extracted.get(S.IMPORT_PAGES, S.EMPTY)
        if page_text and not pages:
            self.issue(
                S.IMPORT_BROWSER_UNMAPPED,
                S.IMPORT_BROWSER_UNMAPPED_MESSAGE,
                field=S.IMPORT_BROWSER_PAGES,
            )
        book = self.parse()
        self.number_field(S.RATINGS_COUNT, S.RATINGS_COUNT, S.WORK)
        self.text(S.DESCRIPTION, S.DESCRIPTION, S.WORK, verbatim=C.TRUE)
        self.browser_capture_labels()
        self.text(S.LANGUAGE, S.LANGUAGE, S.EDITION)
        publication = (self.get(S.IMPORT_BROWSER_PUBLICATION) or S.EMPTY).strip()
        publication_match = C.BROWSER_FIRST_PUBLISHED.search(publication)
        publication_field = S.IMPORT_BROWSER_FIRST_PUBLICATION
        if publication_match is C.NONE:
            publication_match = C.BROWSER_EDITION_PUBLISHED.search(publication)
            publication_field = S.PUBLICATION_DATE
        if publication_match:
            date = parse_date(publication_match[S.VALUE])
            assert date is not C.NONE
            self.observe(
                publication_field,
                date.value,
                S.WORK if publication_field == S.IMPORT_BROWSER_FIRST_PUBLICATION else S.EDITION,
            )
        else:
            self.observe(
                S.IMPORT_BROWSER_FIRST_PUBLICATION,
                C.NONE,
                S.WORK,
                FieldState.UNAVAILABLE if publication else FieldState.EMPTY,
            )
            if publication:
                self.issue(
                    S.IMPORT_BROWSER_UNMAPPED,
                    S.IMPORT_BROWSER_UNMAPPED_MESSAGE,
                    field=S.IMPORT_BROWSER_PUBLICATION,
                )
        events = self.browser_personal_fields(book.source_id) if structured else ()
        return book.model_copy(
            update={
                S.COLLECTIONS: (self.document.collection,),
                S.SHELF_POSITION: int(extracted[S.SHELF_POSITION])
                if S.SHELF_POSITION in extracted
                else C.NONE,
                S.OBSERVATIONS: tuple(self.observations),
                S.READING_EVENTS: events,
            }
        )

    def browser_capture_labels(self) -> None:
        # The legacy collector queried the whole document. Shelf-v1 versions
        # personal fields only; it does not establish scope for these labels.
        for header, field, unverified in C.DQ_CAPTURE_LABEL_FIELDS:
            value = self.text(header, unverified, S.WORK, verbatim=C.TRUE)
            if field is not C.NONE:
                self.observe(
                    field,
                    C.NONE,
                    S.WORK,
                    FieldState.UNAVAILABLE
                    if value is not C.NONE
                    else FieldState.UNSUPPORTED
                    if self.get(header) is C.NONE
                    else FieldState.EMPTY,
                )
            if value is not C.NONE:
                self.issue(
                    S.DQ_CAPTURE_UNVERIFIED_CODE,
                    S.DQ_CAPTURE_UNVERIFIED_MESSAGE,
                    field=header,
                )

    def browser_provenance(self) -> None:
        for header in C.GOODREADS_EXPORT_STRUCTURED_HEADERS:
            if self.get(header) is C.NONE:
                raise self.invalid(header, S.IMPORT_SCHEMA_ERROR)
        if self.get(S.GOODREADS_EXPORT_VERSION_HEADER) != S.GOODREADS_EXPORT_VERSION:
            raise self.invalid(S.GOODREADS_EXPORT_VERSION_HEADER)
        if self.get(S.GOODREADS_EXPORT_COLLECTION) != self.document.collection:
            raise self.invalid(S.GOODREADS_EXPORT_COLLECTION)
        if self.get(S.GOODREADS_EXPORT_COLLECTION_STATE) != S.COMPLETE:
            raise self.invalid(S.GOODREADS_EXPORT_COLLECTION_STATE)
        origin = self.get(S.GOODREADS_EXPORT_SOURCE_URL) or S.EMPTY
        try:
            parsed = urlsplit(origin)
            identity = C.GOODREADS_EXPORT_SOURCE_URL.fullmatch(parsed.path)
            if (
                parsed.scheme != S.HTTPS
                or parsed.hostname not in (S.WWW_GOODREADS_COM, S.GOODREADS_COM)
                or parsed.username
                or parsed.password
                or parsed.port is not C.NONE
                or parsed.fragment
                or identity is C.NONE
                or identity[C.ONE] != self.account.account_id
            ):
                raise self.invalid(S.GOODREADS_EXPORT_SOURCE_URL)
            query = parse_qs(parsed.query, keep_blank_values=C.TRUE)
            if (
                query.get(S.SHELF) != [self.document.collection]
                or not query.keys() <= C.GOODREADS_EXPORT_QUERY_KEYS
            ):
                raise self.invalid(S.GOODREADS_EXPORT_SOURCE_URL)
        except ValueError as exc:
            raise self.invalid(S.GOODREADS_EXPORT_SOURCE_URL) from exc
        captured = self.get(S.GOODREADS_EXPORT_CAPTURED_AT) or S.EMPTY
        try:
            instant = datetime.fromisoformat(captured.replace(S.Z, S.DATES_PARSE_DATE_PARSED_TEXT))
            if instant.tzinfo is C.NONE:
                raise self.invalid(S.GOODREADS_EXPORT_CAPTURED_AT)
        except ValueError as exc:
            raise self.invalid(S.GOODREADS_EXPORT_CAPTURED_AT) from exc
        self.observation_url = origin
        self.observed_at = captured

    def browser_personal_fields(self, source_id: str) -> tuple[ReadingEvent, ...]:
        # Replace generic unsupported observations with explicit structured evidence.
        fields = {S.REVIEW, S.READING_EVENTS}
        self.observations = [item for item in self.observations if item.field not in fields]
        dates: dict[str, PartialDate | None] = {}
        states: dict[str, FieldState] = {}
        for header, state_header, field in C.GOODREADS_EXPORT_FIELDS:
            value = self.get(header) or S.EMPTY
            state_text = self.get(state_header)
            try:
                state = FieldState(state_text or S.EMPTY)
            except ValueError as exc:
                raise self.invalid(state_header) from exc
            if state not in C.GOODREADS_EXPORT_STATES or (
                (state == FieldState.PRESENT) != bool(value.strip())
            ):
                raise self.invalid(header)
            states[field] = state
            if field == S.REVIEW:
                self.observe(
                    field, value if state == FieldState.PRESENT else C.NONE, S.READER, state
                )
                continue
            date = self.date_value(header) if state == FieldState.PRESENT else C.NONE
            dates[field] = date
            self.observe(field, date.value if date is not C.NONE else C.NONE, S.READER, state)
        started = dates[S.GOODREADS_EXPORT_DATE_STARTED_FIELD]
        finished = dates[S.GOODREADS_EXPORT_DATE_READ_FIELD]
        if (
            started is not C.NONE
            and finished is not C.NONE
            and started.precision == finished.precision
            and started.value > finished.value
        ):
            raise self.invalid(S.GOODREADS_EXPORT_STARTED, S.INVALID_DATE)
        event_date = finished or started
        events = (
            (
                ReadingEvent(
                    source_event_id=S.IMPORT_EVENT_ID.format(
                        source_id=source_id,
                        date=event_date.value if event_date is not C.NONE else S.EMPTY,
                    ),
                    started=started,
                    finished=finished,
                    status=ReadingStatus.READ
                    if self.document.collection == S.READ
                    else ReadingStatus.TO_READ,
                ),
            )
            if started is not C.NONE or finished is not C.NONE
            else ()
        )
        event_state = (
            FieldState.UNAVAILABLE
            if FieldState.UNAVAILABLE
            in (
                states[S.GOODREADS_EXPORT_DATE_READ_FIELD],
                states[S.GOODREADS_EXPORT_DATE_STARTED_FIELD],
            )
            else FieldState.PRESENT
            if events
            else FieldState.EMPTY
            if FieldState.EMPTY
            in (
                states[S.GOODREADS_EXPORT_DATE_READ_FIELD],
                states[S.GOODREADS_EXPORT_DATE_STARTED_FIELD],
            )
            else FieldState.UNSUPPORTED
        )
        self.observe(
            S.READING_EVENTS,
            [event.model_dump(mode=S.JSON) for event in events]
            if event_state == FieldState.PRESENT
            else C.NONE,
            S.READER,
            event_state,
        )
        return events


class ExportConnector:
    def __init__(self, document: RawDocument) -> None:
        self.document = document

    def collect(
        self,
        account: Account,
        *,
        interactive: bool = C.FALSE,
        on_progress: ProgressCallback | None = C.NONE,
    ) -> CollectionSnapshot:
        if self.document.source != account.source:
            raise ConnectorError(S.IMPORT_SOURCE_MESSAGE, code=S.IMPORT_SOURCE_ERROR)
        if self.document.account_id != account.account_id:
            raise ConnectorError(S.IMPORT_ACCOUNT_MESSAGE, code=S.IMPORT_ACCOUNT_ERROR)
        rows = _csv_rows(self.document.body)
        headers = next(rows, C.NONE)
        normalized = [header.strip().casefold() for header in headers] if headers else []
        browser_export = (
            account.source == Source.GOODREADS and S.IMPORT_BROWSER_URL.casefold() in normalized
        )
        structured_headers = {header.casefold() for header in C.GOODREADS_EXPORT_STRUCTURED_HEADERS}
        if (
            browser_export
            and structured_headers.intersection(normalized)
            and not (structured_headers <= set(normalized))
        ):
            raise ConnectorError(S.IMPORT_SCHEMA_MESSAGE, code=S.IMPORT_SCHEMA_ERROR)
        if (browser_export and self.document.collection not in (S.TO_READ, S.READ)) or (
            not browser_export and self.document.collection != S.LIBRARY
        ):
            raise ConnectorError(S.IMPORT_BROWSER_SCOPE_ERROR, code=S.IMPORT_SCHEMA_ERROR)
        if (
            not headers
            or not all(normalized)
            or len(set(normalized)) != len(normalized)
            or S.IMPORT_TITLE.casefold() not in normalized
            or (
                account.source == Source.STORYGRAPH
                and S.IMPORT_READ_STATUS.casefold() not in normalized
            )
            or not any(
                identifier.casefold() in normalized
                for identifier in C.IMPORT_SCHEMA_IDENTIFIERS[account.source]
            )
        ):
            raise ConnectorError(S.IMPORT_SCHEMA_MESSAGE, code=S.IMPORT_SCHEMA_ERROR)
        issues = [
            Issue(
                code=S.IMPORT_UNKNOWN_COLUMN,
                message=S.IMPORT_UNKNOWN_COLUMN_MESSAGE.format(column=header),
            )
            for header, normalized_header in zip(headers, normalized, strict=C.TRUE)
            if normalized_header
            not in (
                C.BROWSER_EXPORT_HEADERS | structured_headers
                if browser_export
                else C.IMPORT_KNOWN_HEADERS[account.source]
            )
        ]
        if account.source == Source.STORYGRAPH:
            issues.append(
                Issue(
                    code=S.IMPORT_STORYGRAPH_SCOPE_NOTICE, message=S.IMPORT_STORYGRAPH_SCOPE_MESSAGE
                )
            )
        if browser_export:
            issues.append(
                Issue(code=S.IMPORT_BROWSER_SCOPE_NOTICE, message=S.IMPORT_BROWSER_SCOPE_MESSAGE)
            )
        records: list[BookRecord] = []
        identities: dict[str, int] = {}
        excluded = C.ZERO
        for number, values in enumerate(rows, start=C.TWO):
            if len(values) != len(headers):
                raise ConnectorError(
                    S.IMPORT_WIDTH_MESSAGE.format(
                        row=number, actual=len(values), expected=len(headers)
                    ),
                    code=S.IMPORT_CSV_ERROR,
                )
            row = _ExportRow(
                dict(zip(headers, values, strict=C.TRUE)), number, account, self.document
            )
            if account.source == Source.STORYGRAPH and not _storygraph_read_scope(
                row.get(S.IMPORT_READ_STATUS), number
            ):
                excluded += C.ONE
                continue
            record = row.browser_export() if browser_export else row.parse()
            if record.source_id in identities:
                raise ConnectorError(
                    S.IMPORT_DUPLICATE_MESSAGE.format(
                        first=identities[record.source_id], second=number
                    ),
                    code=S.IMPORT_DUPLICATE_ID,
                )
            identities[record.source_id] = number
            records.append(record)
            issues.extend(
                issue.model_copy(update={S.SOURCE_ID: record.source_id}) for issue in row.issues
            )
        if excluded:
            issues.append(
                Issue(
                    code=S.STORYGRAPH_READ_SCOPE_EXCLUDED_CODE,
                    message=S.STORYGRAPH_READ_SCOPE_EXCLUDED_MESSAGE.format(count=excluded),
                )
            )
        capabilities = {
            field: FieldState.PRESENT
            if any(header.casefold() in normalized for header in supported_headers)
            else FieldState.UNSUPPORTED
            for field, supported_headers in C.IMPORT_CAPABILITY_HEADERS[account.source].items()
        }
        for record in records:
            for observation in record.observations:
                if observation.state == FieldState.UNAVAILABLE:
                    capabilities[observation.field] = FieldState.UNAVAILABLE
        if account.source == Source.STORYGRAPH or browser_export:
            capabilities = {
                field: FieldState.PRESENT
                if any(
                    observation.field == field and observation.state == FieldState.PRESENT
                    for record in records
                    for observation in record.observations
                )
                else FieldState.UNAVAILABLE
                if any(
                    observation.field == field and observation.state == FieldState.UNAVAILABLE
                    for record in records
                    for observation in record.observations
                )
                else FieldState.EMPTY
                if any(
                    observation.field == field and observation.state == FieldState.EMPTY
                    for record in records
                    for observation in record.observations
                )
                else FieldState.UNSUPPORTED
                for field in {
                    *capabilities,
                    *(item.field for record in records for item in record.observations),
                }
            }
        snapshot = CollectionSnapshot(
            source=account.source,
            account_id=account.account_id,
            collection=self.document.collection,
            state=SyncState.COMPLETE,
            records=tuple(records),
            started_at=self.document.captured_at,
            pages_seen=C.ONE,
            expected_count=len(records),
            identity_verified=C.FALSE,
            termination_verified=C.TRUE,
            capabilities=capabilities,
            issues=tuple(issues),
            input_kind=S.INPUT_FILE,
            raw_document_id=self.document.id,
            processing_version=S.IMPORT_PROCESSING_VERSION,
        )
        if on_progress is not C.NONE:
            on_progress(
                CollectionProgress(
                    source=account.source,
                    collection=self.document.collection,
                    pages_seen=C.ONE,
                    records=snapshot.records,
                    message=S.IMPORT_FILE_COMPLETE_MESSAGE,
                )
            )
        return snapshot
