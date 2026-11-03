from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import MetadataReceipt, SourceReceipt
from bookystats.cli.report import run_lines
from bookystats.domain.analytics import AnalyticsReceipt
from bookystats.domain.models import (
    Check,
    CheckName,
    Issue,
    Source,
    SyncState,
    Verification,
    VerificationResult,
)
from bookystats.domain.products import ProductReceipt
from bookystats.persistence.raw import RawDocument
from bookystats.runtime.runlog import (
    OperationalLog,
    latest_log,
    log_directory,
    prune_logs,
    write_failure_log,
    write_run_log,
)
from tests.support.reporting import reporting_issues, run_receipt


def _document() -> RawDocument:
    return RawDocument(
        id=S.TEST_IMPORT_DOCUMENT_ID,
        source=Source.GOODREADS,
        account_id=S.TEST_REPORTING_ACCOUNT,
        body=S.TEST_REPORTING_FIXTURE_CSV,
        media_type=S.RAW_CSV_MEDIA_TYPE,
        origin=S.TEST_REPORTING_FILE,
        captured_at=S.TEST_REPORTING_FIRST_TIME,
        sha256=hashlib.sha256(S.TEST_REPORTING_FIXTURE_CSV).hexdigest(),
    )


def test_run_log_keeps_full_issues_verification_and_raw_lineage_without_source_paths(
    tmp_path: Path,
) -> None:
    document = _document()
    verification = Verification(
        result=VerificationResult.PARTIAL,
        checks=(
            Check(
                name=CheckName.METADATA,
                result=VerificationResult.PARTIAL,
                source=Source.GOOGLE_BOOKS,
                detail=S.TEST_REPORTING_MESSAGE_ONE,
            ),
        ),
    )
    receipt = run_receipt(
        sources=(
            SourceReceipt(
                source=Source.GOODREADS,
                state=SyncState.COMPLETE,
                issues=reporting_issues(),
                collection=S.READ,
                input_kind=S.INPUT_FILE,
            ),
        ),
        verification=verification,
    )
    path = write_run_log(
        tmp_path,
        receipt,
        trigger=S.INPUT_FILE,
        inputs={
            (Source.GOODREADS, S.READ): replace(
                document, origin=S.TEST_REPORTING_PRIVATE_PATH, collection=S.READ
            )
        },
        secrets=(),
        report_lines=run_lines(receipt, issue_limit=C.NONE),
    )
    text = path.read_text(encoding=S.UTF_8)
    assert str(tmp_path) not in text
    assert S.TEST_REPORTING_PRIVATE_PATH not in text
    assert (
        S.RUNLOG_FILE_LINE.format(
            source=S.GOODREADS + S.SLASH + S.READ,
            origin=S.TEST_REPORTING_FILE,
            size=len(document.body),
            sha256=document.sha256,
            captured=document.captured_at,
            document=document.id,
        )
        in text
    )
    for issue in reporting_issues():
        assert S.REPORT_ISSUE_LINE.format(code=issue.code, message=issue.message) in text
    assert S.REPORT_RESULT_LINE.format(result=S.PARTIAL.upper()) in text
    assert text.endswith(S.NEWLINE)
    assert path.parent == log_directory(tmp_path)


def test_run_logs_redact_explicit_keys_query_keys_and_bearer_tokens(tmp_path: Path) -> None:
    receipt = run_receipt(
        sources=(
            SourceReceipt(
                source=Source.GOODREADS,
                state=SyncState.FAILED,
                issues=(
                    Issue(
                        code=S.TEST_REPORTING_ISSUE_ONE,
                        message=S.TEST_REPORTING_SECRET_MESSAGE,
                    ),
                ),
            ),
        )
    )
    path = write_run_log(
        tmp_path,
        receipt,
        trigger=S.INPUT_FILE,
        inputs={},
        secrets=iter(C.TEST_REPORTING_SECRETS),
        report_lines=run_lines(receipt, issue_limit=C.NONE),
    )
    text = path.read_text(encoding=S.UTF_8)
    assert all(value not in text for value in C.TEST_REPORTING_REDACTED_VALUES)
    assert S.REDACTION_REDACT_RESULT_REDACTED in text
    assert S.TEST_REPORTING_ISSUE_ONE in text


def test_failure_logs_are_redacted_and_keep_the_explicit_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.TEST_REPORTING_CLOCK, lambda: S.TEST_REPORTING_FIRST_TIME)
    path = write_failure_log(
        tmp_path, S.TEST_REPORTING_SECRET_MESSAGE, secrets=C.TEST_REPORTING_SECRETS
    )
    text = path.read_text(encoding=S.UTF_8)
    assert S.RUNLOG_FAILED_TITLE + S.NEWLINE in text
    assert S.RUNLOG_TIME_LINE.format(time=S.TEST_REPORTING_FIRST_TIME) in text
    assert all(value not in text for value in C.TEST_REPORTING_REDACTED_VALUES)
    plain = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    assert S.RUNLOG_FAILURE_LINE.format(message=S.TEST_REPORTING_FAILURE) in plain.read_text(
        encoding=S.UTF_8
    )


def test_same_second_failures_append_to_one_persistent_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.TEST_REPORTING_CLOCK, lambda: S.TEST_REPORTING_FIRST_TIME)
    first = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_ONE, secrets=())
    second = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_TWO, secrets=())
    assert first == second
    assert S.TEST_REPORTING_MESSAGE_ONE in second.read_text(encoding=S.UTF_8)
    assert S.TEST_REPORTING_MESSAGE_TWO in second.read_text(encoding=S.UTF_8)
    third = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_THREE, secrets=())
    assert second.exists()
    assert S.TEST_REPORTING_MESSAGE_THREE in third.read_text(encoding=S.UTF_8)
    assert list(log_directory(tmp_path).glob(S.RUNLOG_PATTERN)) == [third]


def test_repeated_receipt_logs_preserve_previous_entries(tmp_path: Path) -> None:
    receipt = run_receipt()
    first = write_run_log(
        tmp_path,
        receipt,
        trigger=S.INPUT_FILE,
        inputs={},
        secrets=(),
        report_lines=run_lines(receipt, issue_limit=C.NONE),
    )
    original = first.read_bytes()
    second = write_run_log(
        tmp_path,
        receipt,
        trigger=S.INPUT_FILE,
        inputs={},
        secrets=(),
        report_lines=run_lines(receipt, issue_limit=C.NONE),
    )
    assert second == first
    assert second.read_bytes().startswith(original)
    assert second.read_text(encoding=S.UTF_8).count(S.LOG_TEST_START_TOKEN) == C.TWO
    assert second.read_text(encoding=S.UTF_8).count(S.LOG_TEST_END_TOKEN) == C.TWO


def test_run_log_preserves_supplied_report_lines_from_an_iterator(tmp_path: Path) -> None:
    path = write_run_log(
        tmp_path,
        run_receipt(),
        trigger=S.INPUT_FILE,
        inputs={},
        secrets=(),
        report_lines=iter((S.TEST_REPORTING_MESSAGE_ONE, S.TEST_REPORTING_MESSAGE_TWO)),
    )
    assert S.NEWLINE.join(
        (S.TEST_REPORTING_MESSAGE_ONE, S.TEST_REPORTING_MESSAGE_TWO)
    ) in path.read_text(encoding=S.UTF_8)


def test_equal_utc_instants_from_different_offsets_append_normalized_utc_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.TEST_REPORTING_CLOCK, lambda: S.TEST_REPORTING_FIRST_TIME)
    first = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_ONE, secrets=())
    monkeypatch.setattr(S.TEST_REPORTING_CLOCK, lambda: S.TEST_REPORTING_OFFSET_TIME)
    second = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_TWO, secrets=())
    assert first == second
    text = second.read_text(encoding=S.UTF_8)
    assert S.TEST_REPORTING_MESSAGE_ONE in text
    assert S.TEST_REPORTING_MESSAGE_TWO in text
    assert S.TEST_REPORTING_OFFSET_TIME not in text
    assert S.TEST_REPORTING_FIRST_TIME in text


def test_appending_preserves_legacy_logs_unmanaged_files_and_directories(tmp_path: Path) -> None:
    folder = log_directory(tmp_path)
    folder.mkdir()
    unrelated = folder / S.TEST_REPORTING_UNMANAGED_LOG
    unrelated.write_text(S.TEST_REPORTING_MESSAGE_ONE, encoding=S.UTF_8)
    nested = folder / S.TEST_REPORTING_DIRECTORY_LOG
    nested.mkdir()
    legacy = folder / S.TEST_REPORTING_OLDER_LOG
    legacy.write_text(S.TEST_REPORTING_MESSAGE_TWO, encoding=S.UTF_8)
    first = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    second = write_run_log(
        tmp_path,
        run_receipt(),
        trigger=S.INPUT_FILE,
        inputs={},
        secrets=(),
        report_lines=(),
    )
    prune_logs(tmp_path, keep=second)
    assert first.exists()
    assert latest_log(tmp_path) == second
    assert unrelated.read_text(encoding=S.UTF_8) == S.TEST_REPORTING_MESSAGE_ONE
    assert legacy.read_text(encoding=S.UTF_8) == S.TEST_REPORTING_MESSAGE_TWO
    assert nested.is_dir()


def test_failed_replacement_preserves_previous_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    original = first.read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(
            Path,
            S.TEST_REPORTING_OPEN,
            Mock(side_effect=PermissionError(S.TEST_REPORTING_IO_FAILURE)),
        )
        with pytest.raises(PermissionError, match=S.TEST_REPORTING_IO_FAILURE):
            write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_TWO, secrets=())
    assert first.read_bytes() == original


def test_latest_log_uses_write_order_not_start_time_or_lexical_run_id(
    tmp_path: Path,
) -> None:
    folder = log_directory(tmp_path)
    folder.mkdir()
    older = folder / S.TEST_REPORTING_OLDER_LOG
    newer = folder / S.TEST_REPORTING_NEWER_LOG
    older.write_text(S.TEST_REPORTING_MESSAGE_ONE, encoding=S.UTF_8)
    newer.write_text(S.TEST_REPORTING_MESSAGE_TWO, encoding=S.UTF_8)
    os.utime(older, (C.TEST_REPORTING_MTIME_OLDER, C.TEST_REPORTING_MTIME_OLDER))
    os.utime(newer, (C.TEST_REPORTING_MTIME_NEWER, C.TEST_REPORTING_MTIME_NEWER))
    (folder / S.TEST_REPORTING_DIRECTORY_LOG).mkdir()
    (folder / S.TEST_REPORTING_NOT_LOG).write_text(S.EMPTY, encoding=S.UTF_8)
    assert latest_log(tmp_path) == newer


def test_missing_and_empty_log_directories_are_not_created_by_status(tmp_path: Path) -> None:
    assert latest_log(tmp_path) is C.NONE
    assert not log_directory(tmp_path).exists()
    log_directory(tmp_path).mkdir()
    assert latest_log(tmp_path) is C.NONE


def test_log_io_errors_propagate_instead_of_silently_discarding_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        Path,
        S.TEST_REPORTING_OPEN,
        Mock(side_effect=PermissionError(S.TEST_REPORTING_IO_FAILURE)),
    )
    with pytest.raises(PermissionError, match=S.TEST_REPORTING_IO_FAILURE):
        write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    with pytest.raises(PermissionError, match=S.TEST_REPORTING_IO_FAILURE):
        write_run_log(
            tmp_path,
            run_receipt(),
            trigger=S.INPUT_FILE,
            inputs={},
            secrets=(),
            report_lines=run_lines(run_receipt(), issue_limit=C.NONE),
        )
    assert list(log_directory(tmp_path).iterdir()) == []


def test_context_flushes_progress_before_final_receipt_and_finishes_only_once(
    tmp_path: Path,
) -> None:
    receipt = run_receipt()
    with OperationalLog(tmp_path, trigger=S.INPUT_FILE) as log:
        assert log.path.name == S.LOG_FILE_NAME
        assert S.LOG_TEST_START_TOKEN in log.path.read_text(encoding=S.UTF_8)
        log.event(S.LOG_TEST_PROGRESS)
        incremental = log.path.read_text(encoding=S.UTF_8)
        assert S.LOG_TEST_PROGRESS in incremental
        assert S.LOG_TEST_END_TOKEN not in incremental
        log.finish(receipt, inputs={}, report_lines=(S.TEST_REPORTING_MESSAGE_ONE,))
        complete = log.path.read_bytes()
        log.finish(receipt, inputs={}, report_lines=(S.TEST_REPORTING_MESSAGE_TWO,))
        log.fail(S.TEST_REPORTING_FAILURE)
    assert log.path.read_bytes() == complete
    assert log.path.read_text(encoding=S.UTF_8).count(S.LOG_TEST_END_TOKEN) == C.ONE
    with pytest.raises(RuntimeError, match=S.LOG_ALREADY_FINISHED):
        log.event(S.LOG_TEST_PROGRESS)


def test_context_redacts_provider_urls_headers_and_exception_text_on_every_write(
    tmp_path: Path,
) -> None:
    with (
        pytest.raises(ValueError),
        OperationalLog(
            tmp_path, trigger=S.INPUT_FILE, secrets=iter(C.TEST_REPORTING_SECRETS)
        ) as log,
    ):
        log.event(S.TEST_REPORTING_SECRET_MESSAGE)
        log.event(S.LOG_TEST_PROVIDER_MESSAGE)
        raise ValueError(S.LOG_TEST_PROVIDER_MESSAGE)
    text = log.path.read_text(encoding=S.UTF_8)
    assert all(value not in text for value in C.LOG_TEST_PRIVATE_VALUES)
    assert all(value not in text for value in C.TEST_REPORTING_REDACTED_VALUES)
    assert text.count(S.LOG_TEST_END_TOKEN) == C.ONE
    assert S.RUNLOG_FAILED_TITLE in text


def test_interrupted_and_unfinished_runs_preserve_previous_history(tmp_path: Path) -> None:
    path = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    original = path.read_bytes()
    with pytest.raises(KeyboardInterrupt), OperationalLog(tmp_path, trigger=S.INPUT_FILE) as log:
        log.event(S.LOG_TEST_PROGRESS)
        raise KeyboardInterrupt
    with OperationalLog(tmp_path, trigger=S.INPUT_FILE):
        pass
    text = path.read_text(encoding=S.UTF_8)
    assert path.read_bytes().startswith(original)
    assert S.LOG_TEST_PROGRESS in text
    assert S.LOG_TEST_INTERRUPT_TYPE in text
    assert S.LOG_INTERRUPTED in text
    assert text.count(S.LOG_TEST_START_TOKEN) == C.THREE
    assert text.count(S.LOG_TEST_END_TOKEN) == C.THREE


def test_repeated_issue_messages_are_grouped_in_final_report(tmp_path: Path) -> None:
    issue = Issue(code=S.TEST_REPORTING_ISSUE_ONE, message=S.TEST_REPORTING_MESSAGE_ONE)
    receipt = run_receipt(
        sources=(
            SourceReceipt(
                source=Source.GOODREADS,
                state=SyncState.PARTIAL,
                issues=(issue, issue, issue),
            ),
        )
    )
    path = write_run_log(
        tmp_path,
        receipt,
        trigger=S.INPUT_FILE,
        inputs={},
        secrets=(),
        report_lines=run_lines(receipt, issue_limit=C.NONE),
    )
    text = path.read_text(encoding=S.UTF_8)
    assert (
        S.REPORT_REPEATED_ISSUE_LINE.format(code=issue.code, message=issue.message, count=C.THREE)
        in text
    )
    assert (
        S.LOG_ISSUE_COUNT.format(
            scope=S.GOODREADS + S.SLASH + S.LIBRARY, code=issue.code, count=C.THREE
        )
        in text
    )
    assert text.count(S.LOG_ISSUE_EXAMPLE.format(message=issue.message)) == C.ONE


def test_final_issue_totals_include_codes_omitted_from_display_and_delivery(
    tmp_path: Path,
) -> None:
    first = Issue(code=S.TEST_REPORTING_ISSUE_ONE, message=S.TEST_REPORTING_MESSAGE_ONE)
    second = Issue(code=S.TEST_REPORTING_ISSUE_ONE, message=S.TEST_REPORTING_MESSAGE_TWO)
    third = Issue(code=S.TEST_REPORTING_ISSUE_ONE, message=S.TEST_REPORTING_MESSAGE_THREE)
    secret = Issue(code=S.TEST_REPORTING_ISSUE_TWO, message=S.LOG_TEST_PROVIDER_MESSAGE)
    long = Issue(
        code=S.TEST_REPORTING_ISSUE_THREE,
        message=S.LOG_TEST_PROGRESS * C.LOG_ISSUE_MESSAGE_LENGTH,
    )
    receipt = run_receipt(
        sources=(
            SourceReceipt(
                source=Source.GOODREADS,
                state=SyncState.PARTIAL,
                collection=S.READ,
                issues=(first, first, second, third, secret),
            ),
        ),
        metadata=(
            MetadataReceipt(
                provider=Source.GOOGLE_BOOKS,
                state=SyncState.PARTIAL,
                issues=(secret, secret),
            ),
        ),
    )
    receipt = receipt.model_copy(
        update={
            S.AN_ANALYTICS: AnalyticsReceipt(
                state=SyncState.PARTIAL, issues=(secret, secret, secret, secret)
            )
        }
    )
    with OperationalLog(tmp_path, trigger=S.INPUT_FILE) as log:
        log.finish(
            receipt,
            inputs={},
            report_lines=run_lines(receipt, issue_limit=C.ZERO),
            delivery_issues=(secret, secret, secret, long),
        )
    text = log.path.read_text(encoding=S.UTF_8)
    assert (
        S.LOG_ISSUE_COUNT.format(
            scope=S.GOODREADS + S.SLASH + S.READ, code=first.code, count=C.FOUR
        )
        in text
    )
    assert (
        S.LOG_ISSUE_COUNT.format(
            scope=S.GOODREADS + S.SLASH + S.READ, code=secret.code, count=C.ONE
        )
        in text
    )
    assert S.LOG_ISSUE_COUNT.format(scope=S.GOOGLE_BOOKS, code=secret.code, count=C.TWO) in text
    assert (
        S.LOG_ISSUE_COUNT.format(scope=S.LOG_DELIVERY_SCOPE, code=secret.code, count=C.THREE)
        in text
    )
    assert (
        S.LOG_ISSUE_COUNT.format(scope=S.LOG_ANALYTICS_SCOPE, code=secret.code, count=C.FOUR)
        in text
    )
    assert S.TEST_REPORTING_MESSAGE_ONE in text
    assert S.TEST_REPORTING_MESSAGE_TWO in text
    assert S.TEST_REPORTING_MESSAGE_THREE not in text
    assert all(value not in text for value in C.LOG_TEST_PRIVATE_VALUES)
    assert S.LOG_ISSUE_TRUNCATED in text


@pytest.mark.parametrize(S.LOG_TEST_METHOD_PARAMETER, (S.LOG_TEST_WRITE, S.LOG_TEST_FLUSH))
def test_write_and_flush_failures_are_explicit_and_preserve_existing_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    path = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    original = path.read_bytes()
    handle = Mock()
    getattr(handle, method).side_effect = PermissionError(S.TEST_REPORTING_IO_FAILURE)
    context = Mock()
    context.__enter__ = Mock(return_value=handle)
    context.__exit__ = Mock(return_value=C.FALSE)
    with monkeypatch.context() as patch:
        patch.setattr(Path, S.TEST_REPORTING_OPEN, Mock(return_value=context))
        with (
            pytest.raises(PermissionError, match=S.TEST_REPORTING_IO_FAILURE),
            OperationalLog(tmp_path, trigger=S.INPUT_FILE),
        ):
            pass
    assert path.read_bytes() == original


@pytest.mark.parametrize(S.CODE, tuple(C.LOG2_EXPECTED_NOTICE_CODES))
def test_compact_receipt_counts_large_notice_groups_without_raw_examples_or_lineage(
    tmp_path: Path, code: str
) -> None:
    notice = Issue(code=code, message=S.TEST_REPORTING_MESSAGE_ONE)
    receipt = run_receipt(
        sources=(
            SourceReceipt(
                source=Source.GOODREADS,
                state=SyncState.COMPLETE,
                collection=S.READ,
                records=C.LOG2_TEST_LARGE_TOTAL,
                issues=(notice,) * C.LOG2_TEST_LARGE_NOTICE_COUNT,
            ),
        )
    )
    document = _document()
    with OperationalLog(tmp_path, trigger=S.INPUT_FILE, compact_receipts=C.TRUE) as log:
        log.finish(
            receipt,
            inputs={(Source.GOODREADS, S.READ): document},
            report_lines=(),
        )
    text = log.path.read_text(encoding=S.UTF_8)
    assert (
        S.LOG_ISSUE_COUNT.format(
            scope=S.GOODREADS + S.SLASH + S.READ,
            code=notice.code,
            count=C.LOG2_TEST_LARGE_NOTICE_COUNT,
        )
        in text
    )
    assert S.TEST_REPORTING_MESSAGE_ONE not in text
    assert S.LOG2_NOTICE_EXPLANATION in text
    assert document.sha256 not in text
    assert S.RUNLOG_FILES_HEADING not in text
    assert S.LOG2_RECEIPT.format(run_id=receipt.run_id, state=receipt.state.value) in text
    assert len(text.splitlines()) < C.LOG2_PROGRESS_BUCKETS


def test_compact_receipt_preserves_explicit_report_iterator_and_previous_history(
    tmp_path: Path,
) -> None:
    path = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    original = path.read_bytes()
    with OperationalLog(tmp_path, trigger=S.INPUT_FILE, compact_receipts=C.TRUE) as log:
        log.finish(
            run_receipt(),
            inputs={},
            report_lines=iter((S.TEST_REPORTING_MESSAGE_ONE, S.TEST_REPORTING_MESSAGE_TWO)),
        )
    text = path.read_text(encoding=S.UTF_8)
    assert path.read_bytes().startswith(original)
    assert S.NEWLINE.join((S.TEST_REPORTING_MESSAGE_ONE, S.TEST_REPORTING_MESSAGE_TWO)) in text
    assert S.LOG2_TEST_UTC_DUPLICATE not in text
    assert text.count(S.LOG_TEST_START_TOKEN) == text.count(S.LOG_TEST_END_TOKEN) == C.TWO


def test_compact_partial_run_explains_provider_gaps_and_retained_products(
    tmp_path: Path,
) -> None:
    issue = Issue(
        code=S.IMPORT_CSV_ERROR,
        message=S.LOG2_TEST_PRIVATE_PATH_MESSAGE,
    )
    provider_issue = Issue(
        code=S.OAUTH_AUTHORIZATION_REQUIRED_CODE,
        message=S.OAUTH_AUTHORIZATION_REQUIRED,
    )
    receipt = run_receipt(
        metadata=(
            MetadataReceipt(
                provider=Source.GOOGLE_BOOKS,
                state=SyncState.NEEDS_AUTH,
                coverage_scope=S.ENR_CORE_COVERAGE_SCOPE,
                fallback_unresolved=C.THREE,
                skipped_by_strategy=C.TWO,
                issues=(provider_issue,),
            ),
        ),
    ).model_copy(
        update={
            S.STATE: SyncState.PARTIAL,
            S.PROD_PRODUCTS: ProductReceipt(state=SyncState.FAILED, issues=(issue,)),
        }
    )
    with OperationalLog(tmp_path, trigger=S.INPUT_FILE, compact_receipts=C.TRUE) as log:
        log.finish(receipt, inputs={}, report_lines=())
    text = log.path.read_text(encoding=S.UTF_8)
    assert S.LOG2_CORE.format(unresolved=C.THREE, skipped=C.TWO) in text
    assert S.LOG2_PRODUCTS_RETAINED.format(state=S.FAILED) in text
    assert S.OAUTH_AUTHORIZATION_REQUIRED in text
    assert S.LOG2_TEST_ACTION in text
    assert S.LOG2_TEST_PRIVATE_PATH_MESSAGE not in text
    assert (
        S.LOG_ISSUE_COUNT.format(scope=S.LOG_DELIVERY_SCOPE, code=issue.code, count=C.ONE) in text
    )
    assert text.splitlines()[-C.ONE].endswith(S.LOG2_TEST_PARTIAL_END)


def test_issue_counts_merge_repeated_receipts_for_the_same_scope(tmp_path: Path) -> None:
    issue = Issue(code=S.TEST_REPORTING_ISSUE_ONE, message=S.TEST_REPORTING_MESSAGE_ONE)
    source = SourceReceipt(source=Source.GOODREADS, state=SyncState.PARTIAL, issues=(issue, issue))
    with OperationalLog(tmp_path, trigger=S.INPUT_FILE, compact_receipts=C.TRUE) as log:
        log.finish(run_receipt(sources=(source, source)), inputs={}, report_lines=())
    text = log.path.read_text(encoding=S.UTF_8)
    assert (
        text.count(
            S.LOG_ISSUE_COUNT.format(
                scope=S.GOODREADS + S.SLASH + S.LIBRARY, code=issue.code, count=C.FOUR
            )
        )
        == C.ONE
    )
    assert text.count(S.LOG_ISSUE_EXAMPLE.format(message=issue.message)) == C.ONE


@pytest.mark.parametrize(S.LOG2_TEST_LARGE_TOTAL, (C.ZERO, C.ONE))
def test_operational_log_rejects_file_and_directory_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, total: int
) -> None:
    folder = log_directory(tmp_path)
    blocked = folder if total == C.ZERO else folder / S.LOG_FILE_NAME
    monkeypatch.setattr(Path, S.LOG2_TEST_SYMLINK, lambda path: path == blocked)
    with pytest.raises(OSError, match=S.LOG_SYMLINK_ERROR):
        write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
