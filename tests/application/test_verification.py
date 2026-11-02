from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, create_autospec

import pytest
from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import MetadataReceipt, SourceReceipt
from bookystats.application.verification import verify_run
from bookystats.domain.interfaces import Storage
from bookystats.domain.models import (
    CheckName,
    Issue,
    PublicationResult,
    Source,
    SyncState,
    Verification,
    VerificationResult,
)
from bookystats.persistence.raw import RawDocument, RawStore
from tests.support.reporting import run_receipt


@pytest.fixture
def archive(tmp_path: Path) -> Iterator[RawStore]:
    store = RawStore(tmp_path / S.TEST_REPORTING_RAW_DATABASE)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def document(archive: RawStore) -> RawDocument:
    return archive.capture(
        Source.GOODREADS,
        S.TEST_REPORTING_ACCOUNT,
        S.TEST_REPORTING_FIXTURE_CSV,
        media_type=S.RAW_CSV_MEDIA_TYPE,
        origin=S.TEST_REPORTING_FILE,
    )


def _entry(
    count: JsonValue = C.ONE,
    *,
    source: Source = Source.GOODREADS,
    account: str = S.TEST_REPORTING_ACCOUNT,
    collection: str = S.LIBRARY,
) -> dict[str, JsonValue]:
    return {
        S.SOURCE: source.value,
        S.ACCOUNT_ID: account,
        S.COLLECTION: collection,
        S.ACTIVE_COUNT: count,
    }


@pytest.fixture
def library() -> Mock:
    store = create_autospec(Storage, instance=C.TRUE)
    store.status.return_value = {S.SOURCES: [_entry()]}
    return store


def source_receipt(document: RawDocument) -> SourceReceipt:
    return SourceReceipt(
        source=document.source,
        account_id=document.account_id,
        state=SyncState.COMPLETE,
        records=C.ONE,
        publication=PublicationResult(snapshot_id=C.ONE, added=C.ONE),
        input_kind=S.INPUT_FILE,
        raw_document_id=document.id,
        collection=document.collection,
    )


def _verify(
    archive: RawStore,
    library: Storage,
    document: RawDocument,
    *,
    source: SourceReceipt | None = C.NONE,
    supplied: Path | None = C.NONE,
    metadata: tuple[MetadataReceipt, ...] = (),
) -> Verification:
    source = source if source is not C.NONE else source_receipt(document)
    key = (source.source, source.collection)
    return verify_run(
        run_receipt(sources=(source,), metadata=metadata),
        archive=archive,
        library=library,
        inputs={key: document},
        supplied={key: supplied},
    )


def test_new_file_and_replay_verify_original_bytes(
    archive: RawStore, library: Mock, document: RawDocument, tmp_path: Path
) -> None:
    path = tmp_path / S.TEST_REPORTING_PRIVATE_DIRECTORY / S.TEST_REPORTING_FILE
    path.parent.mkdir()
    path.write_bytes(document.body)
    fresh = _verify(archive, library, document, supplied=path)
    assert fresh.result == VerificationResult.SUCCESS
    assert (
        S.VERIFY_RAW_COPY_NEW.format(
            origin=document.origin,
            digest=document.sha256[: C.VERIFY_DIGEST_LENGTH],
            size=len(document.body),
        )
        == fresh.checks[C.ZERO].detail
    )
    assert str(path.parent) not in fresh.checks[C.ZERO].detail
    path.unlink()
    replay = _verify(archive, library, document)
    assert replay.result == VerificationResult.SUCCESS
    assert (
        S.VERIFY_RAW_COPY_REPLAY.format(
            origin=document.origin,
            captured=document.captured_at,
            digest=document.sha256[: C.VERIFY_DIGEST_LENGTH],
            size=len(document.body),
        )
        == replay.checks[C.ZERO].detail
    )


def test_changed_and_disappeared_supplied_file_fail_without_losing_saved_copy(
    archive: RawStore, library: Mock, document: RawDocument, tmp_path: Path
) -> None:
    path = tmp_path / S.TEST_REPORTING_FILE
    path.write_bytes(S.TEST_REPORTING_CHANGED_CSV)
    changed = _verify(archive, library, document, supplied=path)
    assert changed.result == VerificationResult.FAILED
    assert changed.checks[C.ZERO].detail == S.VERIFY_RAW_COPY_FILE_CHANGED
    path.unlink()
    missing = _verify(archive, library, document, supplied=path)
    assert missing.result == VerificationResult.FAILED
    assert missing.checks[C.ZERO].detail == S.VERIFY_RAW_COPY_FILE_UNREADABLE
    assert archive.get(document.id) == document


@pytest.mark.parametrize(S.TEST_REPORTING_RAW_FIELDS, C.TEST_REPORTING_RAW_TAMPERING)
def test_raw_payload_and_capture_tampering_fail_verification(
    archive: RawStore,
    library: Mock,
    document: RawDocument,
    tmp_path: Path,
    statement: str,
) -> None:
    with sqlite3.connect(tmp_path / S.TEST_REPORTING_RAW_DATABASE) as connection:
        connection.execute(statement)
    result = _verify(archive, library, document)
    assert result.result == VerificationResult.FAILED
    assert result.checks[C.ZERO].detail == S.VERIFY_RAW_COPY_UNREADABLE


def test_processed_document_must_equal_saved_copy(
    archive: RawStore, library: Mock, document: RawDocument
) -> None:
    result = _verify(archive, library, replace(document, body=S.TEST_REPORTING_CHANGED_CSV))
    assert result.result == VerificationResult.FAILED
    assert result.checks[C.ZERO].detail == S.VERIFY_RAW_COPY_DIFFERS


@pytest.mark.parametrize(S.TEST_REPORTING_LINEAGE_FIELDS, C.TEST_REPORTING_LINEAGE_CASES)
def test_receipt_must_be_bound_to_saved_source_account_scope_and_document(
    archive: RawStore, library: Mock, document: RawDocument, field: str, value: str | None
) -> None:
    source = source_receipt(document).model_copy(update={field: value})
    result = _verify(archive, library, document, source=source)
    assert result.result == VerificationResult.FAILED
    assert result.checks[C.ZERO].detail == S.VERIFY_RAW_COPY_LINEAGE_DIFFERS


def test_reconciliation_counts_only_the_exact_source_account_and_collection(
    archive: RawStore, library: Mock, document: RawDocument
) -> None:
    library.status.return_value = {
        S.SOURCES: [
            _entry(C.FOUR, source=Source.STORYGRAPH),
            _entry(C.THREE, account=S.TEST_REPORTING_OTHER_ACCOUNT),
            _entry(C.TWO, collection=S.READ),
            _entry(),
        ]
    }
    assert _verify(archive, library, document).result == VerificationResult.SUCCESS
    library.status.return_value[S.SOURCES].pop()
    failed = _verify(archive, library, document)
    assert failed.result == VerificationResult.FAILED
    assert failed.checks[-C.ONE].name == CheckName.ROW_COUNTS


def test_multiple_collections_of_one_source_verify_their_own_raw_documents(
    archive: RawStore, library: Mock
) -> None:
    watchlist = archive.capture(
        Source.GOODREADS,
        S.TEST_REPORTING_ACCOUNT,
        S.TEST_REPORTING_FIXTURE_CSV,
        media_type=S.RAW_CSV_MEDIA_TYPE,
        origin=S.TEST_BROWSER_EXPORT_WATCH_NAME,
        collection=S.TO_READ,
    )
    history = archive.capture(
        Source.GOODREADS,
        S.TEST_REPORTING_ACCOUNT,
        S.TEST_REPORTING_TWO_ROW_CSV,
        media_type=S.RAW_CSV_MEDIA_TYPE,
        origin=S.TEST_BROWSER_EXPORT_READ_NAME,
        collection=S.READ,
    )
    receipt = run_receipt(
        sources=(
            source_receipt(watchlist),
            source_receipt(history).model_copy(update={S.RECORDS: C.TWO}),
        )
    )
    library.status.return_value = {
        S.SOURCES: [
            _entry(C.ONE, collection=S.TO_READ),
            _entry(C.TWO, collection=S.READ),
        ]
    }
    inputs = {
        (Source.GOODREADS, S.TO_READ): watchlist,
        (Source.GOODREADS, S.READ): history,
    }
    result = verify_run(receipt, archive=archive, library=library, inputs=inputs, supplied={})
    assert result.result == VerificationResult.SUCCESS
    assert len(result.checks) == C.FOUR
    inputs[(Source.GOODREADS, S.READ)] = watchlist
    swapped = verify_run(receipt, archive=archive, library=library, inputs=inputs, supplied={})
    assert swapped.result == VerificationResult.FAILED
    assert swapped.checks[C.ZERO].result == VerificationResult.SUCCESS
    assert swapped.checks[C.TWO].detail == S.VERIFY_RAW_COPY_LINEAGE_DIFFERS


def test_processing_count_must_agree_with_both_raw_and_library(
    archive: RawStore, library: Mock, document: RawDocument
) -> None:
    source = source_receipt(document).model_copy(update={S.RECORDS: C.TWO})
    result = _verify(archive, library, document, source=source)
    assert result.result == VerificationResult.FAILED
    assert result.checks[-C.ONE].detail == S.VERIFY_ROWS_DIFFER.format(
        rows=C.ONE, records=C.TWO, library=C.ONE
    )


def test_verification_does_not_disclose_a_full_path_in_capture_origin(
    archive: RawStore, library: Mock
) -> None:
    document = archive.capture(
        Source.GOODREADS,
        S.TEST_REPORTING_ACCOUNT,
        S.TEST_REPORTING_FIXTURE_CSV,
        media_type=S.RAW_CSV_MEDIA_TYPE,
        origin=S.TEST_REPORTING_PRIVATE_PATH,
    )
    result = _verify(archive, library, document)
    assert result.result == VerificationResult.SUCCESS
    assert S.TEST_REPORTING_PRIVATE_PATH not in result.checks[C.ZERO].detail
    assert S.TEST_REPORTING_FILE in result.checks[C.ZERO].detail


@pytest.mark.parametrize(S.TEST_REPORTING_COUNT_FIELDS, C.TEST_REPORTING_BAD_COUNTS)
def test_invalid_or_different_library_counts_do_not_pass(
    archive: RawStore, library: Mock, document: RawDocument, count: JsonValue
) -> None:
    library.status.return_value = {S.SOURCES: [_entry(count)]}
    result = _verify(archive, library, document)
    assert result.result == VerificationResult.FAILED
    assert result.checks[-C.ONE].name == CheckName.ROW_COUNTS


def test_an_empty_export_requires_an_actual_empty_library_scope(
    archive: RawStore, library: Mock
) -> None:
    document = archive.capture(
        Source.GOODREADS,
        S.TEST_REPORTING_ACCOUNT,
        S.TEST_REPORTING_EMPTY_CSV,
        media_type=S.RAW_CSV_MEDIA_TYPE,
        origin=S.TEST_REPORTING_FILE,
    )
    source = source_receipt(document).model_copy(update={S.RECORDS: C.ZERO})
    library.status.return_value = {S.SOURCES: []}
    missing = _verify(archive, library, document, source=source)
    assert missing.result == VerificationResult.FAILED
    assert S.STATUS_UNKNOWN in missing.checks[-C.ONE].detail
    library.status.return_value = {S.SOURCES: [_entry(C.ZERO)]}
    assert _verify(archive, library, document, source=source).result == VerificationResult.SUCCESS


def test_malformed_export_cannot_be_reconciled(archive: RawStore, library: Mock) -> None:
    document = archive.capture(
        Source.GOODREADS,
        S.TEST_REPORTING_ACCOUNT,
        S.TEST_REPORTING_INVALID_CSV,
        media_type=S.RAW_CSV_MEDIA_TYPE,
        origin=S.TEST_REPORTING_FILE,
    )
    result = _verify(archive, library, document)
    assert result.result == VerificationResult.FAILED
    assert result.checks[-C.ONE].name == CheckName.ROW_COUNTS


@pytest.mark.parametrize(S.TEST_REPORTING_SOURCE_FIELDS, C.TEST_REPORTING_SOURCE_STATES)
def test_unpublished_processing_is_failed_even_with_an_intact_raw_copy(
    archive: RawStore,
    library: Mock,
    document: RawDocument,
    state: SyncState,
    publication: PublicationResult | None,
    expected: VerificationResult,
) -> None:
    source = source_receipt(document).model_copy(
        update={S.STATE: state, S.TEST_REPORTING_PUBLICATION: publication}
    )
    result = _verify(archive, library, document, source=source)
    assert result.result == expected
    assert result.checks[C.ZERO].result == VerificationResult.SUCCESS
    assert result.checks[-C.ONE].name == CheckName.PROCESSING
    assert S.VERIFY_PROCESSING_NO_ISSUE.format(state=state.value) in result.checks[-C.ONE].detail
    library.status.assert_not_called()


def test_processing_failure_reports_last_issue(
    archive: RawStore, library: Mock, document: RawDocument
) -> None:
    issue = Issue(code=S.TEST_REPORTING_ISSUE_ONE, message=S.TEST_REPORTING_MESSAGE_ONE)
    source = source_receipt(document).model_copy(
        update={S.STATE: SyncState.FAILED, S.ISSUES: (issue,)}
    )
    result = _verify(archive, library, document, source=source)
    assert (
        S.VERIFY_ISSUE.format(code=issue.code, message=issue.message)
        in result.checks[-C.ONE].detail
    )


def test_unconfigured_and_missing_exports_are_explicit_partial_checks(
    archive: RawStore, library: Mock
) -> None:
    receipt = run_receipt(
        sources=(
            SourceReceipt(source=Source.STORYGRAPH, state=SyncState.NOT_CONFIGURED),
            SourceReceipt(
                source=Source.GOODREADS,
                account_id=S.TEST_REPORTING_ACCOUNT,
                state=SyncState.NOT_CONFIGURED,
                input_kind=S.INPUT_FILE,
            ),
        )
    )
    result = verify_run(receipt, archive=archive, library=library, inputs={}, supplied={})
    assert result.result == VerificationResult.PARTIAL
    assert result.checks[C.ZERO].detail == S.VERIFY_NOT_CONFIGURED
    assert result.checks[C.ONE].detail == S.VERIFY_MISSING_EXPORT.format(flag=S.CLI_GOODREADS_FILE)
    assert all(check.name == CheckName.EXPORT for check in result.checks)
    library.status.assert_not_called()


@pytest.mark.parametrize(S.TEST_REPORTING_METADATA_FIELDS, C.TEST_REPORTING_METADATA_CASES)
def test_metadata_incompleteness_is_partial_and_does_not_mask_source_failure(
    archive: RawStore,
    library: Mock,
    document: RawDocument,
    state: SyncState,
    issues: bool,
    expected: VerificationResult,
) -> None:
    issue = Issue(code=S.TEST_REPORTING_ISSUE_ONE, message=S.TEST_REPORTING_MESSAGE_ONE)
    metadata = MetadataReceipt(
        provider=Source.GOOGLE_BOOKS,
        state=state,
        processed=C.ONE,
        deferred=C.TWO if state != SyncState.COMPLETE else C.ZERO,
        issues=(issue,) if issues else (),
    )
    result = _verify(archive, library, document, metadata=(metadata,))
    assert result.result == expected
    assert result.checks[-C.ONE].name == CheckName.METADATA
    assert result.checks[-C.ONE].result == expected
    if issues:
        assert (
            S.VERIFY_ISSUE.format(code=issue.code, message=issue.message)
            in result.checks[-C.ONE].detail
        )
    library.status.return_value = {S.SOURCES: [_entry(C.ZERO)]}
    assert (
        _verify(archive, library, document, metadata=(metadata,)).result
        == VerificationResult.FAILED
    )
