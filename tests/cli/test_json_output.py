from __future__ import annotations

import io
import json

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import SourceReceipt, SyncReceipt
from bookystats.cli.commands import _print_receipt, _print_status
from bookystats.domain.models import Issue, Source, SyncState


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
