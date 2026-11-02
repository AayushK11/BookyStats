from __future__ import annotations

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import MetadataReceipt, SourceReceipt
from bookystats.cli.report import receipt_lines, run_lines, status_lines, verification_lines
from bookystats.domain.models import (
    Check,
    CheckName,
    Issue,
    PublicationResult,
    Source,
    SyncState,
    Verification,
    VerificationResult,
)
from tests.support.reporting import reporting_issues, run_receipt


@pytest.mark.parametrize(S.TEST_REPORTING_LIMIT_FIELDS, C.TEST_REPORTING_ISSUE_LIMITS)
def test_terminal_limits_issues_per_source_and_provider_but_full_report_keeps_all(
    limit: int | None, shown: int
) -> None:
    issues = reporting_issues()
    receipt = run_receipt(
        sources=(
            SourceReceipt(
                source=Source.GOODREADS,
                state=SyncState.COMPLETE,
                collection=S.READ,
                records=C.ONE,
                pages=C.TWO,
                publication=PublicationResult(
                    snapshot_id=C.ONE,
                    added=C.ONE,
                    updated=C.TWO,
                    unchanged=C.THREE,
                    removed=C.FOUR,
                ),
                issues=issues,
                input_kind=S.INPUT_FILE,
            ),
        ),
        metadata=(
            MetadataReceipt(
                provider=Source.GOOGLE_BOOKS,
                state=SyncState.PARTIAL,
                processed=C.ONE,
                deferred=C.TWO,
                issues=issues,
            ),
        ),
    )
    lines = receipt_lines(receipt, issue_limit=limit)
    for index, issue in enumerate(issues):
        assert lines.count(S.REPORT_ISSUE_LINE.format(code=issue.code, message=issue.message)) == (
            C.TWO if index < shown else C.ZERO
        )
    if shown < len(issues):
        assert lines.count(S.REPORT_MORE_ISSUES_LINE.format(count=len(issues) - shown)) == C.TWO
    else:
        assert len(lines) == C.FIVE + C.TWO * len(issues)
    assert (
        S.REPORT_PUBLICATION_LINE.format(
            added=C.ONE, updated=C.TWO, unchanged=C.THREE, removed=C.FOUR
        )
        in lines
    )
    assert (
        S.REPORT_SOURCE_LINE.format(
            source=S.GOODREADS, collection=S.READ, state=S.COMPLETE, records=C.ONE, pages=C.TWO
        )
        in lines
    )
    assert (
        S.REPORT_METADATA_LINE.format(
            provider=S.GOOGLE_BOOKS, state=S.PARTIAL, processed=C.ONE, deferred=C.TWO
        )
        in lines
    )
    assert lines[-C.ONE] == S.CLI_FILE_SCOPE


@pytest.mark.parametrize(S.TEST_REPORTING_RESULT_FIELDS, C.TEST_REPORTING_RESULTS)
def test_verification_formats_marker_name_and_overall_result(result: VerificationResult) -> None:
    check = Check(
        name=CheckName.RAW_COPY,
        result=result,
        source=Source.GOODREADS,
        detail=S.TEST_REPORTING_MESSAGE_ONE,
    )
    verification = Verification(result=result, checks=(check,))
    lines = verification_lines(verification)
    assert lines == [
        S.REPORT_CHECKS_HEADING,
        S.REPORT_CHECK_LINE.format(
            marker=C.VERIFICATION_MARKERS[result],
            source=S.GOODREADS,
            name=CheckName.RAW_COPY.value.replace(S.UNDERSCORE, S.SPACE),
            detail=check.detail,
        ),
        S.REPORT_RESULT_LINE.format(result=result.value.upper()),
        C.VERIFICATION_EXPLANATIONS[result],
    ]
    receipt = run_receipt(verification=verification)
    assert run_lines(receipt, issue_limit=C.NONE) == [
        *receipt_lines(receipt, issue_limit=C.NONE),
        S.EMPTY,
        *lines,
    ]


def test_without_verification_retains_last_good_snapshot_explanation() -> None:
    receipt = run_receipt()
    lines = run_lines(receipt, issue_limit=C.NONE)
    assert lines == receipt_lines(receipt, issue_limit=C.NONE)
    assert S.CLI_PRINT_RECEIPT_LAST_GOOD_SOURCE_SNAPSHOTS_REMAIN_AVAILABLE_THIS in lines
    assert S.REPORT_CHECKS_HEADING not in lines


def test_repeated_issues_are_counted_per_scope_without_changing_receipt() -> None:
    first, second, third = reporting_issues()
    issues = (first, second, first, second, third)
    receipt = run_receipt(
        sources=(SourceReceipt(source=Source.GOODREADS, state=SyncState.PARTIAL, issues=issues),),
        metadata=(
            MetadataReceipt(provider=Source.GOOGLE_BOOKS, state=SyncState.PARTIAL, issues=issues),
        ),
    )
    limited = receipt_lines(receipt, issue_limit=C.ONE)
    full = receipt_lines(receipt, issue_limit=C.NONE)
    for issue in (first, second):
        grouped = S.REPORT_REPEATED_ISSUE_LINE.format(
            code=issue.code, message=issue.message, count=C.TWO
        )
        assert full.count(grouped) == C.TWO
    assert limited.count(S.REPORT_MORE_ISSUES_LINE.format(count=C.THREE)) == C.TWO
    assert S.REPORT_MORE_ISSUES_LINE.format(count=C.THREE) not in full
    assert receipt.sources[C.ZERO].issues == issues
    assert receipt.metadata[C.ZERO].issues == issues


def test_issue_grouping_requires_both_code_and_message_to_match() -> None:
    first, second, _ = reporting_issues()
    issues = (
        first,
        Issue(code=first.code, message=second.message),
        Issue(code=second.code, message=first.message),
    )
    receipt = run_receipt(
        sources=(SourceReceipt(source=Source.GOODREADS, state=SyncState.PARTIAL, issues=issues),)
    )
    lines = receipt_lines(receipt, issue_limit=C.NONE)
    for issue in issues:
        assert S.REPORT_ISSUE_LINE.format(code=issue.code, message=issue.message) in lines


def test_empty_status_preserves_missing_local_state() -> None:
    lines = status_lines({})
    assert S.STATUS_RAW_ARCHIVE_LINE.format(location=S.STATUS_NOT_CREATED) in lines
    assert S.STATUS_LIBRARY_DATABASE_LINE.format(location=S.STATUS_NOT_CREATED) in lines
    assert S.STATUS_LATEST_LOG_LINE.format(location=S.STATUS_NONE_YET) in lines
    assert S.STATUS_LAST_RUN_LINE.format(value=S.STATUS_NONE_YET) in lines
    assert S.STATUS_NONE_LINE in lines
    assert S.STATUS_GOOGLE_KEY_LINE.format(state=S.STATUS_KEY_NOT_SET) in lines


def test_status_distinguishes_retained_snapshots_and_saved_oauth_from_live_success() -> None:
    lines = status_lines(
        {
            S.SOURCES: [
                {
                    S.SOURCE: S.GOODREADS,
                    S.COLLECTION: S.READ,
                    S.STATE: S.NEEDS_AUTH,
                    S.ACTIVE_COUNT: C.THREE,
                }
            ],
            S.GOOGLE_BOOKS_OAUTH_SAVED: C.TRUE,
        }
    )
    assert S.STATUS_SOURCE_HEADER in lines
    assert S.STATUS_RETAINED_SNAPSHOTS in lines
    assert S.STATUS_GOOGLE_KEY_LINE.format(state=S.STATUS_OAUTH_SAVED) in lines
    assert S.STATUS_GOOGLE_KEY_LINE.format(state=S.STATUS_KEY_NOT_SET) not in lines


def test_status_renders_scoped_counts_and_local_file_sizes_without_boolean_counts() -> None:
    lines = status_lines(
        {
            S.DATA_DIRECTORY: S.TEST_REPORTING_ENV_DIRECTORY,
            S.CLI_RAW_ARCHIVE: S.TEST_REPORTING_RAW_DATABASE,
            S.RAW_ARCHIVE_BYTES: C.BYTES_PER_MEGABYTE,
            S.LIBRARY_DATABASE: S.LIBRARY_SQLITE3,
            S.LIBRARY_BYTES: C.TRUE,
            S.LAST_RUN: {
                S.RUN_ID: C.ONE,
                S.STATE: S.COMPLETE,
                S.FINISHED_AT: S.TEST_REPORTING_SECOND_TIME,
            },
            S.SOURCES: [
                {
                    S.SOURCE: S.GOODREADS,
                    S.COLLECTION: S.READ,
                    S.STATE: S.COMPLETE,
                    S.ACTIVE_COUNT: C.TRUE,
                }
            ],
            S.METADATA: {S.GOOGLE_BOOKS: {S.SELECTED: C.ONE, S.UNRESOLVED: C.TWO}},
            S.SCHEDULE: {S.STATE: S.NOT_CONFIGURED},
            S.GOOGLE_BOOKS_KEY_CONFIGURED: C.TRUE,
        }
    )
    assert (
        S.STATUS_RAW_ARCHIVE_LINE.format(
            location=S.STATUS_LOCATION_WITH_SIZE.format(
                path=S.TEST_REPORTING_RAW_DATABASE, size=S.TEST_REPORTING_MEGABYTE
            )
        )
        in lines
    )
    assert S.STATUS_LIBRARY_DATABASE_LINE.format(location=S.LIBRARY_SQLITE3) in lines
    assert (
        S.STATUS_SOURCE_LINE.format(
            source=S.GOODREADS,
            collection=S.READ,
            state=S.COMPLETE,
            count=C.ZERO,
            success=S.STATUS_NEVER,
        )
        in lines
    )
    assert (
        S.STATUS_METADATA_LINE.format(
            provider=S.GOOGLE_BOOKS, matched=C.ONE, unmatched=C.TWO, success=S.STATUS_NEVER
        )
        in lines
    )
    assert S.STATUS_GOOGLE_KEY_LINE.format(state=S.STATUS_KEY_SET) in lines
