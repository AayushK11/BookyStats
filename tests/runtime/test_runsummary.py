from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.runtime.runsummary import (
    RunSummary,
    RunSummaryGate,
    read_summary,
    save_summary,
    summary_path,
)


def _summary() -> RunSummary:
    return RunSummary(
        schema_version=C.RUNSUM_SCHEMA_VERSION,
        run_id=C.TEST_OPLOG_RUN_ID,
        trigger=S.INPUT_FILE,
        outcome=S.PARTIAL,
        exit_code=C.THREE,
        finished_utc=S.TEST_OPLOG_FINISHED_UTC,
        duration_seconds=C.TEST_OPLOG_DURATION,
        lines=(S.TEST_REPORTING_MESSAGE_ONE,),
        gates=(
            RunSummaryGate(
                provider=S.GOOGLE_BOOKS,
                retry_at_utc=S.TEST_OPLOG_ACTIVE_RETRY,
                http_status=C.TEST_OPLOG_HTTP_STATUS,
            ),
        ),
        network_requests={S.GOOGLE_BOOKS: C.TEST_OPLOG_NETWORK},
    )


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in summary_path(directory).parent.iterdir())


def test_summary_round_trips_with_only_documented_fields_and_no_paths_or_urls(
    tmp_path: Path,
) -> None:
    path = save_summary(tmp_path, _summary())
    text = path.read_text(encoding=S.UTF_8)
    assert path == summary_path(tmp_path)
    assert read_summary(tmp_path) == _summary()
    assert set(json.loads(text)) == C.TEST_OPLOG_SUMMARY_FIELDS
    assert str(tmp_path) not in text
    assert S.TEST_OPLOG_SCHEME not in text
    assert _names(tmp_path) == [S.RUNSUM_FILE_NAME]


def test_saving_again_replaces_the_previous_summary(tmp_path: Path) -> None:
    save_summary(tmp_path, _summary())
    newer = _summary().model_copy(update={S.TEST_OPLOG_OUTCOME_FIELD: S.COMPLETE})
    save_summary(tmp_path, newer)
    assert read_summary(tmp_path) == newer
    assert _names(tmp_path) == [S.RUNSUM_FILE_NAME]


def test_a_failed_replace_keeps_the_previous_summary_and_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_summary(tmp_path, _summary())

    def refuse(*arguments: object, **options: object) -> None:
        raise OSError(S.TEST_OPLOG_DISK_FULL)

    monkeypatch.setattr(os, S.TEST_OPLOG_REPLACE_ATTRIBUTE, refuse)
    newer = _summary().model_copy(update={S.TEST_OPLOG_OUTCOME_FIELD: S.COMPLETE})
    with pytest.raises(OSError, match=S.TEST_OPLOG_DISK_FULL):
        save_summary(tmp_path, newer)
    assert read_summary(tmp_path) == _summary()
    assert _names(tmp_path) == [S.RUNSUM_FILE_NAME]


def test_missing_summary_reads_as_absent_without_creating_the_runtime_folder(
    tmp_path: Path,
) -> None:
    assert read_summary(tmp_path) is C.NONE
    assert not (tmp_path / S.LAYOUT_RUNTIME).exists()


def test_unreadable_or_foreign_summaries_read_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = summary_path(tmp_path)
    path.parent.mkdir()
    path.write_text(S.TEST_OPLOG_NOT_JSON, encoding=S.UTF_8)
    assert read_summary(tmp_path) is C.NONE
    path.write_text(S.SPACE * (C.RUNSUM_MAX_BYTES + C.ONE), encoding=S.UTF_8)
    assert read_summary(tmp_path) is C.NONE
    future = _summary().model_copy(
        update={S.TEST_OPLOG_SCHEMA_FIELD: C.RUNSUM_SCHEMA_VERSION + C.ONE}
    )
    path.write_text(future.model_dump_json(), encoding=S.UTF_8)
    assert read_summary(tmp_path) is C.NONE
    path.write_text(_summary().model_dump_json(), encoding=S.UTF_8)
    assert read_summary(tmp_path) == _summary()
    monkeypatch.setattr(Path, S.LOG2_TEST_SYMLINK, lambda candidate: candidate == path)
    assert read_summary(tmp_path) is C.NONE
    monkeypatch.undo()
    path.unlink()
    path.mkdir()
    assert read_summary(tmp_path) is C.NONE
