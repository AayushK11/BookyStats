from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.exports.csv_import import count_export_rows
from bookystats.application.sync import MetadataReceipt, SourceReceipt, SyncReceipt
from bookystats.domain.errors import BookyError, ConnectorError
from bookystats.domain.interfaces import Storage
from bookystats.domain.models import (
    Check,
    CheckName,
    Issue,
    Source,
    SyncState,
    Verification,
    VerificationResult,
)
from bookystats.persistence.raw import RawDocument, RawStore


def _check(name: CheckName, result: VerificationResult, source: Source, detail: str) -> Check:
    return Check(name=name, result=result, source=source, detail=detail)


def _describe(issue: Issue) -> str:
    return S.VERIFY_ISSUE.format(code=issue.code, message=issue.message)


def _raw_copy_check(
    receipt: SourceReceipt, document: RawDocument, archive: RawStore, supplied: Path | None
) -> Check:
    def failed(detail: str) -> Check:
        return _check(CheckName.RAW_COPY, VerificationResult.FAILED, receipt.source, detail)

    if (
        document.source != receipt.source
        or document.account_id != receipt.account_id
        or document.collection != receipt.collection
        or (
            (receipt.input_kind == S.INPUT_FILE or receipt.raw_document_id is not C.NONE)
            and document.id != receipt.raw_document_id
        )
    ):
        return failed(S.VERIFY_RAW_COPY_LINEAGE_DIFFERS)
    try:
        stored = archive.get(document.id)
    except BookyError:
        return failed(S.VERIFY_RAW_COPY_UNREADABLE)
    if stored != document:
        return failed(S.VERIFY_RAW_COPY_DIFFERS)
    if supplied is not C.NONE:
        try:
            on_disk = hashlib.sha256(supplied.read_bytes()).hexdigest()
        except OSError:
            return failed(S.VERIFY_RAW_COPY_FILE_UNREADABLE)
        if on_disk != stored.sha256:
            return failed(S.VERIFY_RAW_COPY_FILE_CHANGED)
        detail = S.VERIFY_RAW_COPY_NEW
    else:
        detail = S.VERIFY_RAW_COPY_REPLAY
    return _check(
        CheckName.RAW_COPY,
        VerificationResult.SUCCESS,
        receipt.source,
        detail.format(
            origin=PureWindowsPath(stored.origin).name,
            captured=stored.captured_at,
            digest=stored.sha256[: C.VERIFY_DIGEST_LENGTH],
            size=len(stored.body),
        ),
    )


def _processing_failure(receipt: SourceReceipt) -> Check:
    reason = (
        _describe(receipt.issues[-C.ONE])
        if receipt.issues
        else S.VERIFY_PROCESSING_NO_ISSUE.format(state=receipt.state.value)
    )
    return _check(
        CheckName.PROCESSING,
        VerificationResult.FAILED,
        receipt.source,
        S.VERIFY_PROCESSING_FAILED.format(reason=reason),
    )


def _library_count(
    library: Storage, source: Source, account_id: str, collection: str
) -> int | None:
    entries = library.status().get(S.SOURCES)
    for entry in entries if isinstance(entries, list) else ():
        if (
            isinstance(entry, dict)
            and entry.get(S.SOURCE) == source
            and entry.get(S.ACCOUNT_ID) == account_id
            and entry.get(S.COLLECTION) == collection
        ):
            count = entry.get(S.ACTIVE_COUNT)
            return (
                count
                if isinstance(count, int) and not isinstance(count, bool) and count >= C.ZERO
                else C.NONE
            )
    return C.NONE


def _row_count_check(receipt: SourceReceipt, document: RawDocument, library: Storage) -> Check:
    try:
        rows = count_export_rows(document.body)
    except ConnectorError as exc:
        return _check(
            CheckName.ROW_COUNTS,
            VerificationResult.FAILED,
            receipt.source,
            S.VERIFY_ROWS_UNCOUNTABLE.format(message=exc),
        )
    stored = _library_count(library, receipt.source, document.account_id, receipt.collection)
    agree = rows == receipt.records == stored
    return _check(
        CheckName.ROW_COUNTS,
        VerificationResult.SUCCESS if agree else VerificationResult.FAILED,
        receipt.source,
        (S.VERIFY_ROWS_MATCH if agree else S.VERIFY_ROWS_DIFFER).format(
            rows=rows,
            records=receipt.records,
            library=stored if stored is not C.NONE else S.STATUS_UNKNOWN,
        ),
    )


def _source_checks(
    receipt: SourceReceipt,
    archive: RawStore,
    library: Storage,
    document: RawDocument | None,
    supplied: Path | None,
) -> list[Check]:
    if receipt.account_id is C.NONE:
        return [
            _check(
                CheckName.EXPORT,
                VerificationResult.PARTIAL,
                receipt.source,
                S.VERIFY_NOT_CONFIGURED,
            )
        ]
    if receipt.input_kind == S.INPUT_LIVE:
        return _capture_checks(receipt, archive, library)
    if document is C.NONE:
        return [
            _check(
                CheckName.EXPORT,
                VerificationResult.PARTIAL,
                receipt.source,
                S.VERIFY_MISSING_EXPORT.format(flag=C.VERIFY_SOURCE_FLAGS[receipt.source]),
            )
        ]
    checks = [_raw_copy_check(receipt, document, archive, supplied)]
    if receipt.state != SyncState.COMPLETE or receipt.publication is C.NONE:
        checks.append(_processing_failure(receipt))
    else:
        checks.append(_row_count_check(receipt, document, library))
    return checks


def _capture_checks(receipt: SourceReceipt, archive: RawStore, library: Storage) -> list[Check]:
    if receipt.raw_document_id is C.NONE:
        checks = [
            _check(
                CheckName.RAW_COPY,
                VerificationResult.FAILED,
                receipt.source,
                S.VERIFY_CAPTURE_MISSING,
            )
        ]
    else:
        try:
            document = archive.get(receipt.raw_document_id)
            capture = archive.load_capture(receipt.raw_document_id)
        except BookyError:
            checks = [
                _check(
                    CheckName.RAW_COPY,
                    VerificationResult.FAILED,
                    receipt.source,
                    S.VERIFY_RAW_COPY_UNREADABLE,
                )
            ]
        else:
            raw_check = _raw_copy_check(receipt, document, archive, C.NONE)
            if raw_check.result == VerificationResult.SUCCESS:
                raw_check = raw_check.model_copy(
                    update={
                        S.DETAIL: S.VERIFY_CAPTURE_RAW.format(
                            pages=len(capture.documents),
                            digest=document.sha256[: C.VERIFY_DIGEST_LENGTH],
                        )
                    }
                )
            checks = [raw_check]
            if receipt.state == SyncState.COMPLETE and receipt.publication is not C.NONE:
                stored = _library_count(
                    library, receipt.source, capture.account_id, receipt.collection
                )
                agree = (
                    raw_check.result == VerificationResult.SUCCESS
                    and capture.state == SyncState.COMPLETE
                    and capture.record_count == receipt.records == stored
                    and (
                        capture.expected_count is C.NONE
                        or capture.expected_count == receipt.records
                    )
                )
                checks.append(
                    _check(
                        CheckName.ROW_COUNTS,
                        VerificationResult.SUCCESS if agree else VerificationResult.FAILED,
                        receipt.source,
                        S.VERIFY_CAPTURE_COUNTS.format(
                            records=receipt.records,
                            library=stored if stored is not C.NONE else S.STATUS_UNKNOWN,
                            expected=(
                                capture.expected_count
                                if capture.expected_count is not C.NONE
                                else S.STATUS_UNKNOWN
                            ),
                        ),
                    )
                )
    if receipt.state != SyncState.COMPLETE or receipt.publication is C.NONE:
        checks.append(_processing_failure(receipt))
    return checks


def _metadata_check(receipt: MetadataReceipt) -> Check:
    if receipt.state == SyncState.COMPLETE:
        return _check(
            CheckName.METADATA,
            VerificationResult.SUCCESS,
            receipt.provider,
            S.VERIFY_METADATA_OK.format(processed=receipt.processed),
        )
    reason = (
        _describe(receipt.issues[C.ZERO])
        if receipt.issues
        else S.VERIFY_METADATA_NO_ISSUE.format(
            processed=receipt.processed, deferred=receipt.deferred
        )
    )
    return _check(
        CheckName.METADATA,
        VerificationResult.PARTIAL,
        receipt.provider,
        S.VERIFY_METADATA_PARTIAL.format(state=receipt.state.value, reason=reason),
    )


def verify_run(
    receipt: SyncReceipt,
    *,
    archive: RawStore,
    library: Storage,
    inputs: Mapping[tuple[Source, str], RawDocument],
    supplied: Mapping[tuple[Source, str], Path | None],
) -> Verification:
    checks: list[Check] = []
    for source in receipt.sources:
        checks.extend(
            _source_checks(
                source,
                archive,
                library,
                inputs.get((source.source, source.collection)),
                supplied.get((source.source, source.collection)),
            )
        )
    checks.extend(_metadata_check(metadata) for metadata in receipt.metadata)
    worst = max(
        (check.result for check in checks),
        key=C.VERIFICATION_SEVERITY.__getitem__,
        default=VerificationResult.SUCCESS,
    )
    return Verification(result=worst, checks=tuple(checks))
