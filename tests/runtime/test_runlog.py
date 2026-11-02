from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import SourceReceipt
from bookystats.cli.report import run_lines
from bookystats.domain.models import (
    Check,
    CheckName,
    Issue,
    Source,
    SyncState,
    Verification,
    VerificationResult,
)
from bookystats.persistence.raw import RawDocument
from bookystats.runtime.runlog import latest_log, log_directory, write_failure_log, write_run_log
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
    assert text.startswith(S.RUNLOG_FAILED_TITLE + S.NEWLINE)
    assert S.RUNLOG_TIME_LINE.format(time=S.TEST_REPORTING_FIRST_TIME) in text
    assert all(value not in text for value in C.TEST_REPORTING_REDACTED_VALUES)
    plain = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    assert S.RUNLOG_FAILURE_LINE.format(message=S.TEST_REPORTING_FAILURE) in plain.read_text(
        encoding=S.UTF_8
    )


def test_same_second_failures_keep_only_latest_completed_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.TEST_REPORTING_CLOCK, lambda: S.TEST_REPORTING_FIRST_TIME)
    first = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_ONE, secrets=())
    second = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_TWO, secrets=())
    assert first != second
    assert not first.exists()
    assert S.TEST_REPORTING_MESSAGE_TWO in second.read_text(encoding=S.UTF_8)
    third = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_THREE, secrets=())
    assert not second.exists()
    assert S.TEST_REPORTING_MESSAGE_THREE in third.read_text(encoding=S.UTF_8)
    assert list(log_directory(tmp_path).glob(S.RUNLOG_PATTERN)) == [third]


def test_repeated_receipt_logs_retire_old_file_after_writing_replacement(tmp_path: Path) -> None:
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
    assert second != first
    assert not first.exists()
    assert original == second.read_bytes()


def test_run_log_preserves_supplied_report_lines_from_an_iterator(tmp_path: Path) -> None:
    path = write_run_log(
        tmp_path,
        run_receipt(),
        trigger=S.INPUT_FILE,
        inputs={},
        secrets=(),
        report_lines=iter((S.TEST_REPORTING_MESSAGE_ONE, S.TEST_REPORTING_MESSAGE_TWO)),
    )
    assert path.read_text(encoding=S.UTF_8).endswith(
        S.NEWLINE.join((S.TEST_REPORTING_MESSAGE_ONE, S.TEST_REPORTING_MESSAGE_TWO, S.EMPTY))
    )


def test_equal_utc_instants_from_different_offsets_are_collisions_not_overwrites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S.TEST_REPORTING_CLOCK, lambda: S.TEST_REPORTING_FIRST_TIME)
    first = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_ONE, secrets=())
    monkeypatch.setattr(S.TEST_REPORTING_CLOCK, lambda: S.TEST_REPORTING_OFFSET_TIME)
    second = write_failure_log(tmp_path, S.TEST_REPORTING_MESSAGE_TWO, secrets=())
    assert first != second
    assert first.stem in second.stem
    assert not first.exists()
    assert S.TEST_REPORTING_MESSAGE_TWO in second.read_text(encoding=S.UTF_8)


def test_retention_ignores_unmanaged_files_and_directories(tmp_path: Path) -> None:
    folder = log_directory(tmp_path)
    folder.mkdir()
    unrelated = folder / S.TEST_REPORTING_UNMANAGED_LOG
    unrelated.write_text(S.TEST_REPORTING_MESSAGE_ONE, encoding=S.UTF_8)
    nested = folder / S.TEST_REPORTING_DIRECTORY_LOG
    nested.mkdir()
    first = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    second = write_run_log(
        tmp_path,
        run_receipt(),
        trigger=S.INPUT_FILE,
        inputs={},
        secrets=(),
        report_lines=(),
    )
    assert not first.exists()
    assert latest_log(tmp_path) == second
    assert unrelated.read_text(encoding=S.UTF_8) == S.TEST_REPORTING_MESSAGE_ONE
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
