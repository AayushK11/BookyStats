from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from bookystats import constants as C
from bookystats import strings as S
from bookystats.errors import BookyError, ConnectorError
from bookystats.imports import count_export_rows
from bookystats.interfaces import Storage
from bookystats.models import (
    Check,
    CheckName,
    Issue,
    Source,
    SyncState,
    Verification,
    VerificationResult,
)
from bookystats.raw import RawDocument, RawStore
from bookystats.sync import MetadataReceipt, SourceReceipt, SyncReceipt


def _check(name: CheckName, result: VerificationResult, source: Source, detail: str) -> Check:
    return Check(name=name, result=result, source=source, detail=detail)


def _describe(issue: Issue) -> str:
    return S.VERIFY_ISSUE.format(code=issue.code, message=issue.message)


def _raw_copy_check(
    source: Source, document: RawDocument, archive: RawStore, supplied: Path | None
) -> Check:
    def failed(detail: str) -> Check:
        return _check(CheckName.RAW_COPY, VerificationResult.FAILED, source, detail)

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
        source,
        detail.format(
            origin=stored.origin,
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


def _library_count(library: Storage, source: Source, account_id: str) -> int:
    entries = library.status().get(S.SOURCES)
    for entry in entries if isinstance(entries, list) else ():
        if (
            isinstance(entry, dict)
            and entry.get(S.SOURCE) == source
            and entry.get(S.ACCOUNT_ID) == account_id
            and entry.get(S.COLLECTION) == S.LIBRARY
        ):
            count = entry.get(S.ACTIVE_COUNT)
            return count if isinstance(count, int) else C.ZERO
    return C.ZERO


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
    stored = _library_count(library, receipt.source, document.account_id)
    agree = rows == receipt.records == stored
    return _check(
        CheckName.ROW_COUNTS,
        VerificationResult.SUCCESS if agree else VerificationResult.FAILED,
        receipt.source,
        (S.VERIFY_ROWS_MATCH if agree else S.VERIFY_ROWS_DIFFER).format(
            rows=rows, records=receipt.records, library=stored
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
    if document is C.NONE:
        return [
            _check(
                CheckName.EXPORT,
                VerificationResult.PARTIAL,
                receipt.source,
                S.VERIFY_MISSING_EXPORT.format(flag=C.VERIFY_SOURCE_FLAGS[receipt.source]),
            )
        ]
    checks = [_raw_copy_check(receipt.source, document, archive, supplied)]
    if receipt.state != SyncState.COMPLETE or receipt.publication is C.NONE:
        checks.append(_processing_failure(receipt))
    else:
        checks.append(_row_count_check(receipt, document, library))
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
    inputs: Mapping[Source, RawDocument],
    supplied: Mapping[Source, Path | None],
) -> Verification:
    checks: list[Check] = []
    for source in receipt.sources:
        checks.extend(
            _source_checks(
                source,
                archive,
                library,
                inputs.get(source.source),
                supplied.get(source.source),
            )
        )
    checks.extend(_metadata_check(metadata) for metadata in receipt.metadata)
    worst = max(
        (check.result for check in checks),
        key=C.VERIFICATION_SEVERITY.__getitem__,
        default=VerificationResult.SUCCESS,
    )
    return Verification(result=worst, checks=tuple(checks))
