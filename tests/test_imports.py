from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import replace

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import ConnectorError
from bookystats.imports import ExportConnector
from bookystats.matching import MatchKind, compare_books
from bookystats.models import (
    Account,
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    FieldState,
    Observation,
    Source,
    SyncState,
)
from bookystats.raw import RawDocument


def account(source: Source = Source.GOODREADS) -> Account:
    account_id, profile = C.TEST_IMPORT_ACCOUNT_VALUES[source]
    return Account(source=source, account_id=account_id, profile_url=profile)


def document(body: bytes, source: Source = Source.GOODREADS) -> RawDocument:
    return RawDocument(
        id=S.TEST_IMPORT_DOCUMENT_ID,
        source=source,
        account_id=account(source).account_id,
        body=body,
        media_type=S.TEST_IMPORT_CSV_MEDIA,
        origin=S.TEST_IMPORT_ORIGIN,
        captured_at=S.TEST_IMPORT_CAPTURED_AT,
        sha256=hashlib.sha256(body).hexdigest(),
    )


def csv_body(source: Source, rows: list[dict[str, str]], *, bom: bool = C.FALSE) -> bytes:
    output = io.StringIO(newline=S.EMPTY)
    headers = tuple(
        dict.fromkeys(
            [
                *C.TEST_IMPORT_DEFAULT_HEADERS[source],
                *(header for row in rows for header in row),
            ]
        )
    )
    writer = csv.writer(output, lineterminator=S.NEWLINE)
    writer.writerow(headers)
    writer.writerows([row.get(header, S.EMPTY) for header in headers] for row in rows)
    return output.getvalue().encode(S.UTF_8_SIG if bom else S.UTF_8)


def collect(source: Source, rows: list[dict[str, str]]) -> CollectionSnapshot:
    return ExportConnector(document(csv_body(source, rows), source)).collect(account(source))


def observation(book: BookRecord, field: str) -> Observation:
    return next(value for value in book.observations if value.field == field)


def test_goodreads_complete_file_retains_every_column_and_separates_reader_metadata() -> None:
    row = C.TEST_IMPORT_GOODREADS_ROW.copy()
    progress: list[CollectionProgress] = []
    snapshot = ExportConnector(document(csv_body(Source.GOODREADS, [row], bom=C.TRUE))).collect(
        account(), on_progress=progress.append
    )
    assert snapshot.state == SyncState.COMPLETE
    assert snapshot.input_kind == S.INPUT_FILE
    assert snapshot.raw_document_id == S.TEST_IMPORT_DOCUMENT_ID
    assert snapshot.processing_version == S.IMPORT_PROCESSING_VERSION
    assert not snapshot.identity_verified
    assert snapshot.termination_verified
    assert snapshot.expected_count == C.ONE
    assert snapshot.collection == S.LIBRARY
    book = snapshot.records[C.ZERO]
    assert book.source_id == S.TEST_IMPORT_NATIVE_ID
    assert book.collections == C.IMPORT_COLLECTIONS
    assert book.raw_fields == row
    assert book.authors == C.TEST_IMPORT_EXPECTED_AUTHORS
    assert book.isbns == C.TEST_IMPORT_EXPECTED_ISBNS
    assert book.edition_format == S.TEST_IMPORT_PAPERBACK
    assert book.shelves == C.TEST_IMPORT_EXPECTED_SHELVES
    assert book.shelf_position == C.SEVEN
    assert book.added_at is not C.NONE
    assert book.added_at.precision == S.MONTH
    assert observation(book, S.GOODREADS_PERSONAL_RATING).value == C.FOUR
    assert observation(book, S.GOODREADS_PERSONAL_RATING).scope == S.READER
    assert observation(book, S.COMMUNITY_RATING).value == C.TEST_IMPORT_COMMUNITY_NUMBER
    assert observation(book, S.COMMUNITY_RATING).scope == S.WORK
    assert observation(book, S.REVIEW).value == S.TEST_IMPORT_REVIEW
    assert observation(book, S.IMPORT_PRIVATE_NOTES_FIELD).value == S.TEST_IMPORT_NOTES
    assert observation(book, S.IMPORT_SPOILER_FIELD).value is C.TRUE
    assert observation(book, S.PAGE_COUNT).value == C.INTEGRATION_PAGE_COUNT
    assert observation(book, S.PAGE_COUNT).scope == S.EDITION
    assert observation(book, S.PUBLICATION_DATE).value == S.TEST_IMPORT_YEAR
    assert observation(book, S.IMPORT_ORIGINAL_PUBLICATION_FIELD).scope == S.WORK
    assert observation(book, S.IMPORT_OWNED_COPIES_FIELD).value == C.ONE
    assert all(item.source_url == S.TEST_IMPORT_ORIGIN for item in book.observations)
    assert all(item.observed_at == S.TEST_IMPORT_CAPTURED_AT for item in book.observations)
    assert any(issue.code == S.IMPORT_UNKNOWN_COLUMN for issue in snapshot.issues)
    assert progress[-C.ONE].records == snapshot.records
    assert not any(item.field == S.RATING for item in book.observations)


def test_goodreads_export_keeps_read_and_current_records_not_only_to_read() -> None:
    rows = [
        {
            **C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS],
            S.IMPORT_BOOK_ID: source_id,
            S.IMPORT_EXCLUSIVE_SHELF: shelf,
        }
        for source_id, shelf in C.TEST_IMPORT_SHELF_CASES
    ]
    snapshot = collect(Source.GOODREADS, rows)
    assert tuple(record.status for record in snapshot.records) == C.TEST_IMPORT_EXPECTED_STATUSES
    assert snapshot.expected_count == C.THREE
    assert all(record.collections == C.IMPORT_COLLECTIONS for record in snapshot.records)


def test_storygraph_partial_date_rereads_and_raw_unknown_fields_are_preserved() -> None:
    row = C.TEST_IMPORT_STORYGRAPH_ROW.copy()
    row[S.IMPORT_AUTHORS] = S.COMMA.join(C.TEST_IMPORT_EXPECTED_AUTHORS)
    snapshot = collect(Source.STORYGRAPH, [row])
    book = snapshot.records[C.ZERO]
    assert snapshot.state == SyncState.COMPLETE
    assert book.raw_fields == row
    assert book.source_id == S.TEST_IMPORT_UID
    assert book.authors == C.TEST_IMPORT_EXPECTED_AUTHORS
    assert observation(book, S.RATING).value == C.TEST_IMPORT_QUARTER_NUMBER
    assert observation(book, S.RATING).scope == S.READER
    assert observation(book, S.ISBNS).state == FieldState.UNAVAILABLE
    assert observation(book, S.MOODS).value == C.TEST_IMPORT_EXPECTED_MOODS
    assert observation(book, S.COMMUNITY_RATING).state == FieldState.UNSUPPORTED
    assert observation(book, S.REVIEW).value == S.TEST_IMPORT_REVIEW
    assert observation(book, S.READING_EVENTS).state == FieldState.PRESENT
    assert [
        event.finished.value for event in book.reading_events if event.finished is not C.NONE
    ] == C.TEST_IMPORT_EXPECTED_DATES
    assert all(event.started is C.NONE for event in book.reading_events)
    assert len({event.source_event_id for event in book.reading_events}) == C.TWO
    assert not snapshot.identity_verified


@pytest.mark.parametrize(S.TEST_IMPORT_PARAM_SOURCE, C.TEST_IMPORT_SOURCE_CASES)
def test_reprocessing_same_document_is_idempotent(source: Source) -> None:
    raw = document(csv_body(source, [C.TEST_IMPORT_BASE_ROWS[source]]), source)
    connector = ExportConnector(raw)
    first = connector.collect(account(source))
    second = connector.collect(account(source), interactive=C.TRUE)
    assert first.records == second.records
    assert first.raw_document_id == second.raw_document_id


@pytest.mark.parametrize(S.TEST_IMPORT_PARAM_SOURCE, C.TEST_IMPORT_SOURCE_CASES)
def test_header_only_is_complete_file_not_account_evidence(source: Source) -> None:
    snapshot = collect(source, [])
    assert snapshot.state == SyncState.COMPLETE
    assert snapshot.expected_count == C.ZERO
    assert not snapshot.records
    assert not snapshot.identity_verified
    assert snapshot.input_kind == S.INPUT_FILE
    assert snapshot.capabilities[S.READING_EVENTS] == FieldState.UNSUPPORTED
    assert snapshot.capabilities[C.IMPORT_RATING_FIELDS[source]] == FieldState.UNSUPPORTED


@pytest.mark.parametrize(S.TEST_IMPORT_PARAM_SOURCE_BODY, C.TEST_IMPORT_ABSENT_AUTHOR_CASES)
def test_identified_export_without_authors_keeps_authors_unsupported(
    source: Source, body: str
) -> None:
    snapshot = ExportConnector(document(body.encode(S.UTF_8), source)).collect(account(source))
    book = snapshot.records[C.ZERO]
    assert not book.authors
    assert observation(book, S.AUTHORS).state == FieldState.UNSUPPORTED
    assert book.raw_fields


@pytest.mark.parametrize(S.TEST_IMPORT_PARAM_RATING_STATE_VALUE, C.TEST_IMPORT_RATING_CASES)
def test_zero_empty_and_absent_ratings_remain_distinct(
    source: Source, rating: str | None, state: FieldState, expected: int | None
) -> None:
    row = C.TEST_IMPORT_BASE_ROWS[source].copy()
    if rating is not C.NONE:
        row[C.IMPORT_RATING_HEADERS[source]] = rating
    book = collect(source, [row]).records[C.ZERO]
    value = observation(book, C.IMPORT_RATING_FIELDS[source])
    assert value.state == state
    assert value.value == expected
    assert not book.reading_events


def test_goodreads_date_read_is_an_event_without_invented_start() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[S.IMPORT_DATE_READ] = S.TEST_IMPORT_DATE_TEXT
    book = collect(Source.GOODREADS, [row]).records[C.ZERO]
    event = book.reading_events[C.ZERO]
    assert event.finished is not C.NONE
    assert event.finished.value == S.TEST_IMPORT_DATE
    assert event.finished.raw == S.TEST_IMPORT_DATE_TEXT
    assert event.started is C.NONE


def test_unmapped_history_and_undated_reads_are_explicit_not_invented() -> None:
    row = C.TEST_IMPORT_STORYGRAPH_ROW.copy()
    row[S.IMPORT_DATES_READ] = S.TEST_IMPORT_RANGE_HISTORY
    snapshot = collect(Source.STORYGRAPH, [row])
    book = snapshot.records[C.ZERO]
    assert book.raw_fields[S.IMPORT_DATES_READ] == S.TEST_IMPORT_RANGE_HISTORY
    assert len(book.reading_events) == C.ONE
    assert observation(book, S.READING_EVENTS).state == FieldState.UNAVAILABLE
    assert snapshot.capabilities[S.READING_EVENTS] == FieldState.UNAVAILABLE
    assert any(issue.code == S.IMPORT_HISTORY_UNMAPPED for issue in snapshot.issues)
    assert any(issue.code == S.IMPORT_HISTORY_INCOMPLETE for issue in snapshot.issues)


@pytest.mark.parametrize(S.VALUE, C.TEST_IMPORT_INVALID_HISTORY_CASES)
def test_invalid_or_ambiguous_dated_events_reject_whole_export(value: str) -> None:
    row = C.TEST_IMPORT_STORYGRAPH_ROW.copy()
    row[S.IMPORT_DATES_READ] = value
    with pytest.raises(ConnectorError):
        collect(Source.STORYGRAPH, [row])


def test_read_count_smaller_than_actual_dated_events_rejects_export() -> None:
    row = C.TEST_IMPORT_STORYGRAPH_ROW.copy()
    row[S.IMPORT_READ_COUNT] = S.TEST_IMPORT_ONE
    with pytest.raises(ConnectorError) as error:
        collect(Source.STORYGRAPH, [row])
    assert error.value.code == S.IMPORT_HISTORY_CONFLICT


@pytest.mark.parametrize(S.TEST_IMPORT_PARAM_BODY_CODE, C.TEST_IMPORT_STRUCTURE_CASES)
def test_invalid_encoding_schema_and_csv_fail_without_publishing_progress(
    body: bytes, code: str
) -> None:
    progress: list[CollectionProgress] = []
    with pytest.raises(ConnectorError) as error:
        ExportConnector(document(body)).collect(account(), on_progress=progress.append)
    assert error.value.code == code
    assert error.value.state == SyncState.FAILED
    assert not progress


def test_wrong_source_is_rejected_before_parsing_invalid_bytes() -> None:
    raw = document(S.TEST_IMPORT_INVALID_UTF8, Source.STORYGRAPH)
    with pytest.raises(ConnectorError) as error:
        ExportConnector(raw).collect(account())
    assert error.value.code == S.IMPORT_SOURCE_ERROR


def test_wrong_account_is_rejected_before_parsing_invalid_bytes() -> None:
    raw = replace(document(S.TEST_IMPORT_INVALID_UTF8), account_id=S.TEST_IMPORT_OTHER_READER)
    with pytest.raises(ConnectorError) as error:
        ExportConnector(raw).collect(account())
    assert error.value.code == S.IMPORT_ACCOUNT_ERROR


@pytest.mark.parametrize(S.TEST_IMPORT_PARAM_HEADER_VALUE, C.TEST_IMPORT_INVALID_NUMBER_CASES)
def test_invalid_numeric_fields_reject_complete_file(header: str, value: str) -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[header] = value
    with pytest.raises(ConnectorError) as error:
        collect(Source.GOODREADS, [row])
    assert error.value.code == S.INVALID_NUMBER


def test_storygraph_rejects_non_quarter_personal_rating() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.STORYGRAPH].copy()
    row[S.IMPORT_STAR_RATING] = S.TEST_IMPORT_NON_QUARTER_RATING
    with pytest.raises(ConnectorError) as error:
        collect(Source.STORYGRAPH, [row])
    assert error.value.code == S.INVALID_NUMBER


@pytest.mark.parametrize(S.VALUE, C.TEST_IMPORT_INVALID_ISBN_CASES)
def test_isbn_formulas_and_invalid_checksums_are_not_evaluated_or_discarded(value: str) -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[S.IMPORT_ISBN] = value
    with pytest.raises(ConnectorError) as error:
        collect(Source.GOODREADS, [row])
    assert error.value.code == S.INVALID_ISBN


def test_exact_empty_isbn_wrapper_means_empty_and_keeps_original_text() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[S.IMPORT_ISBN] = S.TEST_IMPORT_EMPTY_WRAPPER
    book = collect(Source.GOODREADS, [row]).records[C.ZERO]
    assert not book.isbns
    assert observation(book, S.ISBNS).state == FieldState.EMPTY
    assert book.raw_fields[S.IMPORT_ISBN] == S.TEST_IMPORT_EMPTY_WRAPPER


def test_storygraph_invalid_isbn10_check_digit_is_not_promoted_to_native_uid() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.STORYGRAPH].copy()
    row[S.IMPORT_UID] = S.TEST_IMPORT_INVALID_ISBN_X
    with pytest.raises(ConnectorError) as error:
        collect(Source.STORYGRAPH, [row])
    assert error.value.code == S.INVALID_ISBN


def test_conflicting_goodreads_isbn_columns_reject_ambiguous_edition_identity() -> None:
    row = C.TEST_IMPORT_GOODREADS_ROW.copy()
    row[S.IMPORT_ISBN13] = S.TEST_IMPORT_OTHER_ISBN
    with pytest.raises(ConnectorError) as error:
        collect(Source.GOODREADS, [row])
    assert error.value.code == S.INVALID_ISBN


@pytest.mark.parametrize(S.VALUE, C.TEST_IMPORT_DATE_CASES)
def test_invalid_or_ambiguous_single_date_does_not_replace_snapshot(value: str) -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[S.IMPORT_DATE_ADDED] = value
    with pytest.raises(ConnectorError) as error:
        collect(Source.GOODREADS, [row])
    assert error.value.code == S.INVALID_DATE


@pytest.mark.parametrize(S.TEST_IMPORT_PARAM_SOURCE, C.TEST_IMPORT_SOURCE_CASES)
def test_conflicting_duplicate_source_ids_are_not_silently_dropped(source: Source) -> None:
    first = C.TEST_IMPORT_BASE_ROWS[source].copy()
    second = first.copy()
    second[S.IMPORT_TITLE] = S.TEST_IMPORT_OTHER_TITLE
    with pytest.raises(ConnectorError) as error:
        collect(source, [first, second])
    assert error.value.code == S.IMPORT_DUPLICATE_ID
    assert str(C.TWO) in str(error.value)
    assert str(C.THREE) in str(error.value)


def test_identical_duplicate_rows_are_also_explicitly_rejected() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS]
    with pytest.raises(ConnectorError) as error:
        collect(Source.GOODREADS, [row, row])
    assert error.value.code == S.IMPORT_DUPLICATE_ID


def test_fallback_identity_is_stable_without_cross_source_confirmation() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.STORYGRAPH].copy()
    row[S.IMPORT_UID] = S.TEST_IMPORT_ISBN_WRAPPED
    isbn_book = collect(Source.STORYGRAPH, [row]).records[C.ZERO]
    assert isbn_book.source_id == S.IMPORT_ISBN_ID.format(isbn=S.TEST_IMPORT_ISBN)
    assert isbn_book.isbns == C.TEST_IMPORT_EXPECTED_ISBNS
    row[S.IMPORT_UID] = S.EMPTY
    first = collect(Source.STORYGRAPH, [row])
    row[S.IMPORT_REVIEW] = S.TEST_IMPORT_REVIEW
    row[S.IMPORT_STAR_RATING] = S.TEST_IMPORT_QUARTER_RATING
    second = collect(Source.STORYGRAPH, [row])
    assert first.records[C.ZERO].source_id == second.records[C.ZERO].source_id
    assert any(issue.code == S.IMPORT_SYNTHETIC_NOTICE for issue in first.issues)
    assert (
        observation(first.records[C.ZERO], S.IMPORT_IDENTITY_FIELD).value
        == S.IMPORT_SYNTHETIC_IDENTITY
    )
    goodreads = collect(Source.GOODREADS, [C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS]]).records[
        C.ZERO
    ]
    assert compare_books(goodreads, first.records[C.ZERO]).kind == MatchKind.LIKELY


def test_original_header_spelling_and_unknown_values_survive_normalized_lookup() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[S.TEST_IMPORT_UNKNOWN_SPELLING] = S.TEST_IMPORT_UNKNOWN_VALUE
    snapshot = collect(Source.GOODREADS, [row])
    assert snapshot.records[C.ZERO].raw_fields == row
    assert any(issue.code == S.IMPORT_UNKNOWN_COLUMN for issue in snapshot.issues)


def test_unknown_status_is_unavailable_not_empty_and_preserves_source_value() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.STORYGRAPH].copy()
    row[S.IMPORT_READ_STATUS] = S.TEST_IMPORT_UNKNOWN_STATUS
    snapshot = collect(Source.STORYGRAPH, [row])
    book = snapshot.records[C.ZERO]
    assert book.status == C.ReadingStatus.UNKNOWN
    assert book.raw_status == S.TEST_IMPORT_UNKNOWN_STATUS
    assert observation(book, S.STATUS).state == FieldState.UNAVAILABLE
    assert any(issue.code == S.IMPORT_UNKNOWN_STATUS for issue in snapshot.issues)


def test_zero_page_count_and_publication_year_are_unknown_not_fabricated_metadata() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[S.IMPORT_PAGES] = S.TEST_IMPORT_ZERO
    row[S.IMPORT_YEAR] = S.TEST_IMPORT_ZERO
    snapshot = collect(Source.GOODREADS, [row])
    book = snapshot.records[C.ZERO]
    assert observation(book, S.PAGE_COUNT).state == FieldState.UNAVAILABLE
    assert observation(book, S.PUBLICATION_DATE).state == FieldState.UNAVAILABLE
    assert any(issue.code == S.IMPORT_UNKNOWN_NUMBER for issue in snapshot.issues)


def test_malformed_shelf_positions_are_not_silently_dropped() -> None:
    row = C.TEST_IMPORT_GOODREADS_ROW.copy()
    row[S.IMPORT_POSITIONS] = S.TEST_IMPORT_BROKEN_POSITIONS
    with pytest.raises(ConnectorError):
        collect(Source.GOODREADS, [row])


def test_missing_title_and_invalid_native_id_are_explicit_record_failures() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[S.IMPORT_TITLE] = S.EMPTY
    with pytest.raises(ConnectorError):
        collect(Source.GOODREADS, [row])
    row[S.IMPORT_TITLE] = S.TEST_IMPORT_TITLE
    row[S.IMPORT_BOOK_ID] = S.TEST_IMPORT_INVALID_NUMBER
    with pytest.raises(ConnectorError):
        collect(Source.GOODREADS, [row])
    row[S.IMPORT_BOOK_ID] = S.TEST_IMPORT_NATIVE_ID * C.IMPORT_MAX_NUMBER_LENGTH
    with pytest.raises(ConnectorError):
        collect(Source.GOODREADS, [row])
