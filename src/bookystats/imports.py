from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Iterator
from decimal import Decimal
from urllib.parse import quote

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.dates import parse_date
from bookystats.errors import ConnectorError
from bookystats.identifiers import normalize_isbn
from bookystats.interfaces import ProgressCallback
from bookystats.models import (
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
)
from bookystats.raw import RawDocument


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
                source_url=self.document.origin,
                observed_at=self.document.captured_at,
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

    def list_field(self, header: str, field: str) -> tuple[str, ...]:
        if self.absent(header, field, S.READER):
            return tuple()
        values = tuple(
            dict.fromkeys(
                value
                for value in C.IMPORT_LIST_SEPARATOR.split((self.get(header) or S.EMPTY).strip())
                if value
            )
        )
        if not values:
            raise self.invalid(header)
        self.observe(field, list(values), S.READER)
        return values

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

    def history_dates(self) -> tuple[list[PartialDate], bool]:
        raw = self.get(S.IMPORT_DATES_READ)
        if not raw or not raw.strip():
            return [], C.FALSE
        try:
            date = parse_date(raw)
            assert date is not C.NONE
            return [date], C.FALSE
        except (ValueError, OverflowError) as exc:
            if C.IMPORT_NUMERIC_DATE.fullmatch(raw.strip()):
                raise self.invalid(S.IMPORT_DATES_READ, S.INVALID_DATE) from exc
        if not C.IMPORT_DATE_LIST.fullmatch(raw):
            self.issue(S.IMPORT_HISTORY_UNMAPPED, S.IMPORT_HISTORY_UNMAPPED_MESSAGE)
            return [], C.TRUE
        dates: list[PartialDate] = []
        for value in C.IMPORT_LIST_SEPARATOR.split(raw.strip()):
            try:
                date = parse_date(value)
                assert date is not C.NONE
                dates.append(date)
            except (ValueError, OverflowError) as exc:
                raise self.invalid(S.IMPORT_DATES_READ, S.INVALID_DATE) from exc
        return dates, C.FALSE

    def reading_events(
        self, source_id: str, read_count: int | float | None
    ) -> tuple[ReadingEvent, ...]:
        header = C.IMPORT_FINISH_HEADERS[self.account.source]
        dates: list[PartialDate] = []
        incomplete = C.FALSE
        if self.account.source == Source.STORYGRAPH:
            dates, incomplete = self.history_dates()
        self.validate_distinct_dates(dates)
        last = self.date_value(header)
        if last is not C.NONE and not any(date.value == last.value for date in dates):
            dates.append(last)
        self.validate_distinct_dates(dates)
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
        supported = self.get(header) is not C.NONE or (
            self.account.source == Source.STORYGRAPH and self.get(S.IMPORT_DATES_READ) is not C.NONE
        )
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

    def validate_distinct_dates(self, dates: list[PartialDate]) -> None:
        values = sorted(date.value for date in dates)
        for previous, current in zip(values, values[C.ONE :], strict=C.FALSE):
            if current.startswith(previous):
                raise self.invalid(S.IMPORT_DATES_READ, S.IMPORT_HISTORY_CONFLICT)

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
        edition_format = self.text(C.IMPORT_FORMAT_HEADERS[source], S.EDITION_FORMAT, S.EDITION)
        isbns, uid = self.identifiers()
        source_id, url = self.identity(title, authors, edition_format, isbns, uid)
        status = self.status()
        added_at = self.added_date()
        self.number_field(
            C.IMPORT_RATING_HEADERS[source],
            C.IMPORT_RATING_FIELDS[source],
            S.READER,
            fractional=source == Source.STORYGRAPH,
            maximum=C.FIVE,
            zero_empty=source == Source.GOODREADS,
            quarters=source == Source.STORYGRAPH,
        )
        self.text(C.IMPORT_REVIEW_HEADERS[source], S.REVIEW, S.READER, verbatim=C.TRUE)
        read_count = self.number_field(S.IMPORT_READ_COUNT, S.READ_COUNT, S.READER)
        events = self.reading_events(source_id, read_count)
        shelves: tuple[str, ...] = tuple()
        shelf_position: int | None = C.NONE
        if source == Source.GOODREADS:
            shelves, shelf_position = self.shelves()
            self.goodreads_metadata()
        else:
            for header, field in C.IMPORT_STORYGRAPH_LIST_FIELDS:
                self.list_field(header, field)
            self.text(S.IMPORT_PACE, S.PACE, S.READER)
            self.observe(S.COMMUNITY_RATING, C.NONE, S.WORK, FieldState.UNSUPPORTED)
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
        if (
            not headers
            or not all(normalized)
            or len(set(normalized)) != len(normalized)
            or S.IMPORT_TITLE.casefold() not in normalized
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
            if normalized_header not in C.IMPORT_KNOWN_HEADERS[account.source]
        ]
        records: list[BookRecord] = []
        identities: dict[str, int] = {}
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
            record = row.parse()
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
        snapshot = CollectionSnapshot(
            source=account.source,
            account_id=account.account_id,
            collection=S.LIBRARY,
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
                    collection=S.LIBRARY,
                    pages_seen=C.ONE,
                    records=snapshot.records,
                    message=S.IMPORT_FILE_COMPLETE_MESSAGE,
                )
            )
        return snapshot
