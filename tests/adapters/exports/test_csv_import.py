from __future__ import annotations

import csv
import io
from dataclasses import replace

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.exports.csv_import import ExportConnector
from bookystats.domain.errors import ConnectorError
from bookystats.domain.matching import MatchKind, compare_books
from bookystats.domain.models import (
    CollectionProgress,
    CollectionSnapshot,
    FieldState,
    Source,
    SyncState,
)
from tests.support.exports import account, collect, csv_body, document, observation


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


def test_storygraph_only_ratings_and_matching_identity_are_processed() -> None:
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
    assert {item.field for item in book.observations} <= C.RATING_IDENTITY_FIELDS
    assert not book.reading_events
    assert book.status == C.ReadingStatus.UNKNOWN
    assert book.added_at is C.NONE
    assert book.edition_format is C.NONE
    assert book.raw_status is C.NONE
    assert book.raw_fields[S.IMPORT_REVIEW] == S.TEST_IMPORT_REVIEW
    assert snapshot.capabilities[S.REVIEW] == FieldState.UNSUPPORTED
    assert snapshot.capabilities[S.READING_EVENTS] == FieldState.UNSUPPORTED
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


def test_storygraph_history_is_raw_only_even_when_unmapped() -> None:
    row = C.TEST_IMPORT_STORYGRAPH_ROW.copy()
    row[S.IMPORT_DATES_READ] = S.TEST_IMPORT_RANGE_HISTORY
    snapshot = collect(Source.STORYGRAPH, [row])
    book = snapshot.records[C.ZERO]
    assert book.raw_fields[S.IMPORT_DATES_READ] == S.TEST_IMPORT_RANGE_HISTORY
    assert not book.reading_events
    assert snapshot.capabilities[S.READING_EVENTS] == FieldState.UNSUPPORTED
    assert observation(book, S.RATING).value == C.TEST_IMPORT_QUARTER_NUMBER


@pytest.mark.parametrize(S.VALUE, C.TEST_IMPORT_INVALID_HISTORY_CASES)
def test_ignored_storygraph_dates_do_not_block_valid_ratings(value: str) -> None:
    row = C.TEST_IMPORT_STORYGRAPH_ROW.copy()
    row[S.IMPORT_DATES_READ] = value
    book = collect(Source.STORYGRAPH, [row]).records[C.ZERO]
    assert not book.reading_events
    assert book.raw_fields[S.IMPORT_DATES_READ] == value
    assert observation(book, S.RATING).value == C.TEST_IMPORT_QUARTER_NUMBER


def test_invalid_goodreads_read_count_is_rejected() -> None:
    row = C.TEST_IMPORT_GOODREADS_ROW.copy()
    row[S.IMPORT_READ_COUNT] = S.TEST_IMPORT_ZERO
    row[S.IMPORT_DATE_READ] = S.TEST_IMPORT_DATE
    with pytest.raises(ConnectorError) as error:
        collect(Source.GOODREADS, [row])
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


def test_storygraph_invalid_isbn_keeps_rating_without_promoting_identifier() -> None:
    row = C.TEST_IMPORT_BASE_ROWS[Source.STORYGRAPH].copy()
    row[S.IMPORT_UID] = S.TEST_IMPORT_INVALID_ISBN_X
    row[S.IMPORT_STAR_RATING] = S.TEST_IMPORT_QUARTER_RATING
    snapshot = collect(Source.STORYGRAPH, [row])
    book = snapshot.records[C.ZERO]
    assert not book.isbns
    assert book.source_id != S.TEST_IMPORT_INVALID_ISBN_X
    assert observation(book, S.RATING).value == C.TEST_IMPORT_QUARTER_NUMBER
    assert book.raw_fields[S.IMPORT_UID] == S.TEST_IMPORT_INVALID_ISBN_X
    assert any(issue.code == S.INVALID_ISBN for issue in snapshot.issues)


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
    row = C.TEST_IMPORT_BASE_ROWS[Source.GOODREADS].copy()
    row[S.IMPORT_EXCLUSIVE_SHELF] = S.TEST_IMPORT_UNKNOWN_STATUS
    snapshot = collect(Source.GOODREADS, [row])
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


@pytest.mark.parametrize(S.COLLECTION, (S.TO_READ, S.READ))
def test_browser_export_recovers_labeled_metadata_without_inventing_personal_data(
    collection: str,
) -> None:
    row = C.TEST_BROWSER_EXPORT_ROW.copy()
    row[S.IMPORT_BROWSER_SERIES_NUMBER] = S.TEST_BROWSER_EXPORT_FALSE_SERIES
    raw = replace(document(csv_body(Source.GOODREADS, [row])), collection=collection)
    snapshot = ExportConnector(raw).collect(account())
    book = snapshot.records[C.ZERO]
    assert snapshot.collection == collection
    assert snapshot.raw_document_id == raw.id
    assert not snapshot.identity_verified
    assert book.status.value == collection
    assert book.shelves == (collection,)
    assert book.collections == (collection,)
    assert book.source_id == S.TEST_IMPORT_NATIVE_ID
    assert book.authors == (S.TEST_IMPORT_AUTHOR,)
    assert book.isbns == C.TEST_IMPORT_EXPECTED_ISBNS
    assert book.raw_fields == row
    assert book.added_at is not C.NONE
    assert book.added_at.value == S.TEST_BROWSER_EXPORT_DATE_ADDED
    assert book.shelf_position == C.SEVEN
    assert book.edition_format == S.TEST_IMPORT_PAPERBACK
    assert observation(book, S.PAGE_COUNT).value == C.INTEGRATION_PAGE_COUNT
    assert observation(book, S.COMMUNITY_RATING).value == C.TEST_IMPORT_COMMUNITY_NUMBER
    assert observation(book, S.RATINGS_COUNT).value == C.TEST_BROWSER_EXPORT_RATINGS
    assert observation(book, S.DESCRIPTION).value == S.TEST_BROWSER_EXPORT_DESCRIPTION
    assert observation(book, S.GENRES).state == FieldState.UNAVAILABLE
    assert observation(book, S.GENRES).value is C.NONE
    assert observation(book, S.DQ_CAPTURE_UNVERIFIED_GENRES).value == row[S.GENRES]
    assert (
        observation(book, S.DQ_CAPTURE_UNVERIFIED_SERIES_NUMBER).value
        == row[S.IMPORT_BROWSER_SERIES_NUMBER]
    )
    assert observation(book, S.IMPORT_BROWSER_FIRST_PUBLICATION).value == S.TEST_IMPORT_DATE
    assert observation(book, S.REVIEW).state == FieldState.UNSUPPORTED
    assert observation(book, S.GOODREADS_PERSONAL_RATING).state == FieldState.UNSUPPORTED
    assert observation(book, S.READING_EVENTS).state == FieldState.UNSUPPORTED
    assert not book.reading_events
    assert snapshot.capabilities[S.COMMUNITY_RATING] == FieldState.PRESENT
    assert any(issue.code == S.IMPORT_BROWSER_SCOPE_NOTICE for issue in snapshot.issues)


@pytest.mark.parametrize(S.VALUE, C.DQ_CAPTURE_TEST_ROWS)
def test_browser_navigation_labels_are_unverified_even_with_personal_field_version(
    value: dict[str, str],
) -> None:
    row = {
        **value,
        S.GENRES: S.DQ_CAPTURE_TEST_GENRES,
        S.SERIES: S.DQ_CAPTURE_TEST_SERIES,
        S.IMPORT_BROWSER_SERIES_NUMBER: S.TEST_BROWSER_EXPORT_FALSE_SERIES,
    }
    body = csv_body(Source.GOODREADS, [row])
    raw = replace(document(body), collection=S.READ)
    snapshot = ExportConnector(raw).collect(account())
    book = snapshot.records[C.ZERO]
    assert raw.body == body
    assert book.raw_fields == row
    assert book.status == C.ReadingStatus.READ
    for header, field, unverified in C.DQ_CAPTURE_LABEL_FIELDS:
        captured = observation(book, unverified)
        assert captured.state == FieldState.PRESENT
        assert captured.value == row[header]
        assert captured.scope == S.WORK
        assert captured.source_url == observation(book, S.DESCRIPTION).source_url
        assert captured.observed_at == observation(book, S.DESCRIPTION).observed_at
        if field is not C.NONE:
            assert observation(book, field).state == FieldState.UNAVAILABLE
            assert observation(book, field).value is C.NONE
            assert snapshot.capabilities[field] == FieldState.UNAVAILABLE
        assert any(
            issue.code == S.DQ_CAPTURE_UNVERIFIED_CODE
            and header in issue.message
            and issue.source_id == book.source_id
            for issue in snapshot.issues
        )
    assert observation(book, S.GOODREADS_PERSONAL_RATING).state == FieldState.UNSUPPORTED
    if S.GOODREADS_EXPORT_VERSION_HEADER in row:
        assert observation(book, S.REVIEW).value == S.TEST_IMPORT_REVIEW
        assert observation(book, S.GOODREADS_EXPORT_DATE_READ_FIELD).value == S.TEST_IMPORT_DATE
        assert len(book.reading_events) == C.ONE
    else:
        assert observation(book, S.REVIEW).state == FieldState.UNSUPPORTED
        assert not book.reading_events


@pytest.mark.parametrize(S.DQ_CAPTURE_TEST_LABEL_PARAMETERS, C.DQ_CAPTURE_TEST_LABEL_FIELDS)
@pytest.mark.parametrize(S.DQ_CAPTURE_TEST_STATE_PARAMETERS, C.DQ_CAPTURE_TEST_STATE_CASES)
def test_browser_capture_labels_preserve_absent_empty_and_unknown_states(
    header: str,
    field: str,
    unverified: str,
    value: str | None,
    state: FieldState,
) -> None:
    row = C.TEST_BROWSER_EXPORT_ROW.copy()
    row.pop(header, C.NONE)
    if value is not C.NONE:
        row[header] = value
    snapshot = structured_collect(row)
    book = snapshot.records[C.ZERO]
    assert book.raw_fields == row
    assert observation(book, field).state == state
    assert observation(book, field).value is C.NONE
    captured = observation(book, unverified)
    assert captured.state == (FieldState.PRESENT if state == FieldState.UNAVAILABLE else state)
    assert captured.value == (value if state == FieldState.UNAVAILABLE else C.NONE)


def test_browser_export_requires_explicit_shelf_and_valid_source_url() -> None:
    row = C.TEST_BROWSER_EXPORT_ROW.copy()
    body = csv_body(Source.GOODREADS, [row])
    with pytest.raises(ConnectorError, match=S.IMPORT_BROWSER_SCOPE_ERROR):
        ExportConnector(document(body)).collect(account())
    row[S.IMPORT_BROWSER_URL] = S.TEST_BROWSER_EXPORT_BAD_URL
    raw = replace(document(csv_body(Source.GOODREADS, [row])), collection=S.TO_READ)
    with pytest.raises(ConnectorError):
        ExportConnector(raw).collect(account())


def test_browser_export_retains_unknown_metadata_and_rejects_conflicting_identifiers() -> None:
    row = C.TEST_BROWSER_EXPORT_ROW.copy()
    row[S.IMPORT_BROWSER_DETAILS] = S.TEST_BROWSER_EXPORT_BAD_DETAILS
    row[S.IMPORT_BROWSER_PAGES] = S.TEST_BROWSER_EXPORT_BAD_PAGES
    raw = replace(document(csv_body(Source.GOODREADS, [row])), collection=S.TO_READ)
    snapshot = ExportConnector(raw).collect(account())
    book = snapshot.records[C.ZERO]
    assert not book.isbns
    assert observation(book, S.PAGE_COUNT).value is C.NONE
    assert book.raw_fields == row
    assert any(issue.code == S.IMPORT_BROWSER_UNMAPPED for issue in snapshot.issues)
    row = {**C.TEST_BROWSER_EXPORT_ROW, S.IMPORT_ISBN: S.TEST_IMPORT_OTHER_ISBN}
    raw = replace(document(csv_body(Source.GOODREADS, [row])), collection=S.TO_READ)
    with pytest.raises(ConnectorError) as error:
        ExportConnector(raw).collect(account())
    assert error.value.code == S.INVALID_ISBN


def structured_collect(row: dict[str, str]) -> CollectionSnapshot:
    raw = replace(document(csv_body(Source.GOODREADS, [row])), collection=S.READ)
    return ExportConnector(raw).collect(account())


def test_structured_browser_fields_preserve_review_dates_and_row_provenance() -> None:
    row = C.TEST_GOODREADS_EXPORT_ROW.copy()
    book = structured_collect(row).records[C.ZERO]
    assert book.raw_fields == row
    review = observation(book, S.REVIEW)
    assert review.value == S.TEST_IMPORT_REVIEW
    assert review.source_url == S.TEST_GOODREADS_EXPORT_SOURCE_URL
    assert review.observed_at == S.TEST_IMPORT_CAPTURED_AT
    assert review.state == FieldState.PRESENT
    assert observation(book, S.GOODREADS_EXPORT_DATE_READ_FIELD).value == S.TEST_IMPORT_DATE
    assert observation(book, S.GOODREADS_EXPORT_DATE_STARTED_FIELD).state == FieldState.UNSUPPORTED
    assert observation(book, S.GOODREADS_PERSONAL_RATING).state == FieldState.UNSUPPORTED
    assert book.status == C.ReadingStatus.READ
    assert len(book.reading_events) == C.ONE
    assert book.reading_events[C.ZERO].started is C.NONE
    assert book.reading_events[C.ZERO].finished is not C.NONE
    assert book.reading_events[C.ZERO].finished.raw == S.TEST_IMPORT_DATE_TEXT


@pytest.mark.parametrize(S.TEST_GOODREADS_EXPORT_PARAMETER_STATE, tuple(C.GOODREADS_EXPORT_STATES))
def test_structured_browser_field_states_are_explicit(state: FieldState) -> None:
    row = C.TEST_GOODREADS_EXPORT_ROW.copy()
    for header, state_header, _field in C.GOODREADS_EXPORT_FIELDS:
        row[state_header] = state.value
        if state != FieldState.PRESENT:
            row[header] = S.EMPTY
        elif header == S.GOODREADS_EXPORT_STARTED:
            row[header] = S.TEST_IMPORT_YEAR
    snapshot = structured_collect(row)
    book = snapshot.records[C.ZERO]
    for _header, _state_header, field in C.GOODREADS_EXPORT_FIELDS:
        assert observation(book, field).state == state
    assert bool(book.reading_events) == (state == FieldState.PRESENT)
    assert snapshot.capabilities[S.REVIEW] == state
    assert not snapshot.identity_verified
    assert snapshot.input_kind == S.INPUT_FILE


@pytest.mark.parametrize(
    S.TEST_GOODREADS_EXPORT_PARAMETER_FIELD_VALUE, C.TEST_GOODREADS_EXPORT_INVALID_CASES
)
def test_structured_browser_invalid_fields_fail_without_partial_publication(
    header: str, value: str
) -> None:
    row = {**C.TEST_GOODREADS_EXPORT_ROW, header: value}
    with pytest.raises(ConnectorError):
        structured_collect(row)


def test_structured_browser_requires_complete_header_schema_even_for_empty_files() -> None:
    output = io.StringIO(newline=S.EMPTY)
    csv.writer(output).writerow((S.IMPORT_TITLE, S.IMPORT_BROWSER_URL, S.GOODREADS_EXPORT_REVIEW))
    raw = replace(document(output.getvalue().encode(S.UTF_8)), collection=S.READ)
    with pytest.raises(ConnectorError) as error:
        ExportConnector(raw).collect(account())
    assert error.value.code == S.IMPORT_SCHEMA_ERROR


def test_legacy_browser_columns_cannot_smuggle_personal_facts() -> None:
    row = {
        **C.TEST_BROWSER_EXPORT_ROW,
        S.IMPORT_MY_REVIEW: S.TEST_IMPORT_REVIEW,
        S.IMPORT_DATE_READ: S.TEST_IMPORT_DATE,
        S.IMPORT_READ_COUNT: S.TEST_IMPORT_ZERO,
        S.IMPORT_MY_RATING: S.TEST_IMPORT_RATING,
    }
    book = structured_collect(row).records[C.ZERO]
    assert observation(book, S.REVIEW).state == FieldState.UNSUPPORTED
    assert observation(book, S.GOODREADS_PERSONAL_RATING).state == FieldState.UNSUPPORTED
    assert not book.reading_events
    assert book.raw_fields == row
