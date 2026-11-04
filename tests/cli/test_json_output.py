from __future__ import annotations

import io
import json

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.outcome import explain_outcome
from bookystats.application.sync import SourceReceipt, SyncReceipt
from bookystats.cli.commands import _print_receipt, _print_status
from bookystats.cli.report import run_lines
from bookystats.domain.models import Issue, Source, SyncState
from tests.support.outcomes import local_clock, sync_receipt


@pytest.mark.parametrize(S.AN_TEST_OUTPUT_KIND, C.AN_TEST_OUTPUT_KINDS)
def test_json_can_be_redirected_to_a_non_unicode_terminal(
    monkeypatch: pytest.MonkeyPatch, output_kind: str
) -> None:
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding=S.AN_TEST_ASCII)
    if output_kind == S.STATUS:
        monkeypatch.setattr(S.AN_TEST_STDOUT, stream)
        _print_status({S.TITLE: S.AN_TEST_UNICODE}, as_json=C.TRUE)
    else:
        receipt = SyncReceipt(
            run_id=C.ONE,
            state=SyncState.COMPLETE,
            started_at=S.TEST_STORAGE_START_T10,
            finished_at=S.TEST_STORAGE_FINISH_T10,
            account_sync_complete=C.FALSE,
            sources=(
                SourceReceipt(
                    source=Source.GOODREADS,
                    state=SyncState.COMPLETE,
                    issues=(Issue(code=S.TEST, message=S.AN_TEST_UNICODE),),
                ),
            ),
            metadata=(),
        )
        _print_receipt(receipt, stream, as_json=C.TRUE)
    stream.flush()
    result = json.loads(buffer.getvalue())
    value = (
        result[S.TITLE]
        if output_kind == S.STATUS
        else result[S.SOURCES][C.ZERO][S.ISSUES][C.ZERO][S.MESSAGE]
    )
    assert value == S.AN_TEST_UNICODE


def test_json_mode_keeps_stdout_machine_readable_and_sends_the_summary_to_stderr() -> None:
    receipt = sync_receipt().model_copy(update={S.LOG_FILE: S.LOG_FILE_NAME})
    outcome = explain_outcome(receipt, exit_code=C.ZERO, now=local_clock())
    out, err = io.StringIO(), io.StringIO()
    _print_receipt(receipt, out, as_json=C.TRUE, outcome=outcome, summary=err)
    assert SyncReceipt.model_validate_json(out.getvalue()) == receipt
    assert err.getvalue().splitlines() == [
        *outcome.lines,
        S.REPORT_RUN_LOG_LINE.format(path=S.LOG_FILE_NAME),
    ]


def test_human_mode_prints_run_lines_outcome_and_log_pointer_on_stdout_only() -> None:
    receipt = sync_receipt().model_copy(update={S.LOG_FILE: S.LOG_FILE_NAME})
    outcome = explain_outcome(receipt, exit_code=C.ZERO, now=local_clock())
    out, err = io.StringIO(), io.StringIO()
    _print_receipt(receipt, out, as_json=C.FALSE, outcome=outcome, summary=err)
    assert err.getvalue() == S.EMPTY
    assert out.getvalue().splitlines() == [
        *outcome.lines,
        S.EMPTY,
        *run_lines(receipt, issue_limit=C.FIVE),
        S.REPORT_RUN_LOG_LINE.format(path=S.LOG_FILE_NAME),
    ]
