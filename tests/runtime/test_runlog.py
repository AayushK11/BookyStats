from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from bookystats import __version__
from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.outcome import RunProbe, format_duration
from bookystats.application.sync import MetadataReceipt
from bookystats.domain.errors import BookyError
from bookystats.domain.models import Issue, Source, SyncState
from bookystats.runtime.runlog import (
    OperationalLog,
    RunLogError,
    latest_log,
    log_directory,
    write_failure_log,
)
from bookystats.runtime.runsummary import read_summary, summary_path
from tests.support.outcomes import (
    RetryStore,
    StepTimer,
    explainer,
    inject_append_fault,
    local_clock,
    sync_receipt,
)


def _text(directory: Path) -> str:
    return (log_directory(directory) / S.LOG_FILE_NAME).read_text(encoding=S.UTF_8)


def _open(
    directory: Path, timer: StepTimer | None = C.NONE, warnings: list[str] | None = C.NONE
) -> OperationalLog:
    return OperationalLog(
        directory,
        trigger=S.INPUT_FILE,
        secrets=C.TEST_REPORTING_SECRETS,
        clock=local_clock,
        timer=timer if timer is not C.NONE else StepTimer(),
        warn=warnings.append if warnings is not C.NONE else C.NONE,
    )


def _end_line(text: str) -> str:
    return next(line for line in reversed(text.splitlines()) if line.startswith(S.OPLOG_END_TOKEN))


def test_a_run_appends_one_readable_block_after_the_existing_history(tmp_path: Path) -> None:
    folder = log_directory(tmp_path)
    folder.mkdir()
    (folder / S.LOG_FILE_NAME).write_text(S.TEST_OPLOG_LEGACY_TEXT, encoding=S.UTF_8)
    receipt = sync_receipt()
    timer = StepTimer()
    started = S.PROD_RUN_STARTED.format(run_id=C.TEST_OPLOG_RUN_ID)
    with _open(tmp_path, timer) as log:
        log.event(started)
        timer.value = C.TEST_OPLOG_TOTAL
        outcome = log.finish(receipt, explainer(receipt))
    text = _text(tmp_path)
    lines = text.splitlines()
    begin = lines.index(
        S.OPLOG_START.format(instant=S.TEST_OPLOG_CLOCK_INSTANT, trigger=S.INPUT_FILE)
    )
    assert text.startswith(S.TEST_OPLOG_LEGACY_TEXT)
    assert lines[begin - C.ONE] == S.EMPTY
    assert lines[begin + C.ONE] == S.OPLOG_VERSION_LINE.format(
        version=__version__, format=C.OPLOG_FORMAT
    )
    assert lines[begin + C.TWO] == S.OPLOG_EVENT.format(
        stamp=S.TEST_OPLOG_LOCAL_STAMP, message=started
    )
    for expected in (
        S.OPLOG_RUN_LINE.format(run_id=C.TEST_OPLOG_RUN_ID, state=S.COMPLETE),
        S.OPLOG_VERIFICATION_NONE,
        S.OPLOG_ISSUES_NONE,
    ):
        assert S.OPLOG_INDENT + expected in lines
    assert lines[-C.ONE - len(outcome.lines) : -C.ONE] == list(outcome.lines)
    assert lines[-C.ONE] == S.OPLOG_END.format(
        instant=S.TEST_OPLOG_CLOCK_INSTANT,
        run_id=C.TEST_OPLOG_RUN_ID,
        state=S.COMPLETE,
        exit_code=C.ZERO,
        duration=format_duration(C.TEST_OPLOG_TOTAL),
    )
    saved = read_summary(tmp_path)
    assert saved is not C.NONE
    assert (saved.outcome, saved.exit_code, saved.run_id, saved.trigger) == (
        S.COMPLETE,
        C.ZERO,
        C.TEST_OPLOG_RUN_ID,
        S.INPUT_FILE,
    )
    assert saved.finished_utc == S.TEST_OPLOG_CLOCK_UTC
    assert saved.lines == outcome.lines


def test_stage_durations_come_from_the_orchestration_events(tmp_path: Path) -> None:
    receipt = sync_receipt()
    timer = StepTimer()
    metadata_stage = S.PROD_STAGE_METADATA.format(provider=Source.GOOGLE_BOOKS.value)
    with _open(tmp_path, timer) as log:
        timer.value = C.TEST_OPLOG_SOURCES_START
        log.event(S.PROD_STAGE_SOURCES)
        timer.value = C.TEST_OPLOG_METADATA_START
        log.event(metadata_stage)
        timer.value = C.TEST_OPLOG_STAGES_END
        log.event(S.PROD_STAGE_FINISHED.format(run_id=C.TEST_OPLOG_RUN_ID, state=S.COMPLETE))
        timer.value = C.TEST_OPLOG_TOTAL
        log.finish(receipt, explainer(receipt))

    def name(stage: str) -> str:
        return stage.removeprefix(S.OPLOG_STAGE_PREFIX).removesuffix(S.OPLOG_PERIOD)

    spent = C.TEST_OPLOG_STAGES_END - C.TEST_OPLOG_SOURCES_START
    expected = [
        S.OPLOG_INDENT + S.OPLOG_TIME_HEADING,
        S.OPLOG_DEEP_INDENT
        + S.OPLOG_TIME_LINE.format(
            duration=format_duration(C.TEST_OPLOG_METADATA_START - C.TEST_OPLOG_SOURCES_START),
            stage=name(S.PROD_STAGE_SOURCES),
        ),
        S.OPLOG_DEEP_INDENT
        + S.OPLOG_TIME_LINE.format(
            duration=format_duration(C.TEST_OPLOG_STAGES_END - C.TEST_OPLOG_METADATA_START),
            stage=name(metadata_stage),
        ),
        S.OPLOG_DEEP_INDENT
        + S.OPLOG_TIME_LINE.format(
            duration=format_duration(C.TEST_OPLOG_TOTAL - spent), stage=S.OPLOG_TIME_OTHER
        ),
    ]
    lines = _text(tmp_path).splitlines()
    first = lines.index(expected[C.ZERO])
    assert lines[first : first + len(expected)] == expected


def test_log_and_summary_never_contain_secrets_credentials_paths_or_personal_text(
    tmp_path: Path,
) -> None:
    messages = (
        S.LOG_TEST_PROVIDER_MESSAGE,
        S.LOG2_TEST_PRIVATE_PATH_MESSAGE,
        S.TEST_OPLOG_URL_MESSAGE,
        S.TEST_REPORTING_SECRET_MESSAGE,
    )
    receipt = sync_receipt(
        metadata=(
            MetadataReceipt(
                provider=Source.GOOGLE_BOOKS,
                state=SyncState.PARTIAL,
                issues=tuple(
                    Issue(code=S.TEST_REPORTING_ISSUE_ONE, message=message) for message in messages
                ),
            ),
        )
    )
    with _open(tmp_path) as log:
        for message in messages:
            log.event(message)
        log.finish(receipt, explainer(receipt, exit_code=C.THREE))
    saved = summary_path(tmp_path).read_text(encoding=S.UTF_8)
    text = _text(tmp_path)
    for private in C.TEST_OPLOG_PRIVATE_VALUES:
        assert private not in text
        assert private not in saved
    assert S.TEST_OPLOG_URL_HOST in text
    assert S.TEST_OPLOG_QUERY_REMOVED in text


def test_failures_keep_the_cause_but_never_private_exception_text(tmp_path: Path) -> None:
    plain = tmp_path / S.TEST_REPORTING_ENV_DIRECTORY
    inside = tmp_path / S.TEST_REPORTING_OVERRIDE_DIRECTORY
    redacted = tmp_path / S.TEST_REPORTING_PLATFORM_DIRECTORY
    with pytest.raises(ValueError), _open(plain):
        raise ValueError(S.TEST_OPLOG_PERSONAL)
    store = RetryStore()
    store.states[(Source.GOOGLE_BOOKS, C.OUTCOME_PROVIDER_HOSTS[Source.GOOGLE_BOOKS])] = ValueError(
        S.TEST_OPLOG_PERSONAL
    )
    probe = RunProbe()
    probe.attach(store)
    with pytest.raises(ValueError), _open(inside):
        probe.begin()
    with pytest.raises(BookyError), _open(redacted):
        raise BookyError(S.TEST_REPORTING_SECRET_MESSAGE)
    assert S.OPLOG_UNEXPECTED_BARE.format(type=S.TEST_OPLOG_VALUE_ERROR) in _text(plain)
    first_party = _text(inside)
    assert S.TEST_OPLOG_VALUE_ERROR in first_party
    assert S.TEST_OPLOG_PROBE_FRAME in first_party
    for directory in (plain, inside, redacted):
        assert S.TEST_OPLOG_FAILED_END in _end_line(_text(directory))
        assert S.TEST_OPLOG_PERSONAL not in _text(directory)
        assert S.TEST_REPORTING_SECRET not in _text(directory)
        saved = read_summary(directory)
        assert saved is not C.NONE
        assert (saved.outcome, saved.exit_code) == (S.FAILED, C.ONE)
    assert S.TEST_REPORTING_KEY_SECRET not in _text(redacted)


def test_issue_counts_are_complete_while_examples_stay_bounded_and_clipped(
    tmp_path: Path,
) -> None:
    notice = min(C.LOG2_EXPECTED_NOTICE_CODES)
    issues = (
        *(
            Issue(
                code=S.TEST_REPORTING_ISSUE_ONE,
                message=S.TEST_OPLOG_DISTINCT.format(number=number),
            )
            for number in range(C.LOG2_TEST_LARGE_NOTICE_COUNT)
        ),
        Issue(
            code=S.TEST_REPORTING_ISSUE_TWO,
            message=S.TEST_OPLOG_FILLER * C.TEST_OPLOG_LONG_COUNT,
        ),
        *(
            Issue(code=notice, message=S.TEST_OPLOG_DISTINCT.format(number=number))
            for number in range(C.LOG2_TEST_LARGE_NOTICE_COUNT)
        ),
    )
    receipt = sync_receipt(
        metadata=(
            MetadataReceipt(provider=Source.GOOGLE_BOOKS, state=SyncState.PARTIAL, issues=issues),
        )
    )
    with _open(tmp_path) as log:
        log.finish(receipt, explainer(receipt, exit_code=C.THREE))
    lines = _text(tmp_path).splitlines()
    scope = Source.GOOGLE_BOOKS.value
    for code in (S.TEST_REPORTING_ISSUE_ONE, notice):
        counted = S.OPLOG_ISSUE_COUNT.format(
            scope=scope, code=code, count=C.LOG2_TEST_LARGE_NOTICE_COUNT
        )
        assert S.OPLOG_DEEP_INDENT + counted in lines
    single = S.OPLOG_ISSUE_COUNT_ONE.format(scope=scope, code=S.TEST_REPORTING_ISSUE_TWO)
    assert S.OPLOG_DEEP_INDENT + single in lines
    prefix = S.OPLOG_EXAMPLE_INDENT + S.TEST_OPLOG_EXAMPLE_PREFIX
    examples = [line for line in lines if line.startswith(prefix)]
    assert len(examples) == C.LOG_ISSUE_EXAMPLES + C.ONE
    assert [len(line) for line in examples if line.endswith(S.OPLOG_TRUNCATED)] == [
        len(prefix) + C.LOG_ISSUE_MESSAGE_LENGTH + len(S.OPLOG_TRUNCATED)
    ]
    assert S.OPLOG_INDENT + S.LOG2_NOTICE_EXPLANATION in lines


def test_a_log_that_cannot_be_opened_stops_the_run_without_naming_the_path(
    tmp_path: Path,
) -> None:
    log_directory(tmp_path).write_text(S.EMPTY, encoding=S.UTF_8)
    with pytest.raises(RunLogError) as opening, _open(tmp_path):
        pass
    with pytest.raises(RunLogError) as failure:
        write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    for caught in (opening, failure):
        assert str(caught.value)
        assert str(tmp_path) not in str(caught.value)


def test_a_failure_log_that_cannot_be_completed_raises_instead_of_looking_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inject_append_fault(monkeypatch, lambda call: call >= C.TWO)
    with pytest.raises(RunLogError, match=S.TEST_OPLOG_DISK_FULL):
        write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())


def test_symlinked_log_folder_or_file_is_refused_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = log_directory(tmp_path)
    monkeypatch.setattr(Path, S.LOG2_TEST_SYMLINK, lambda path: path.name == S.LOGS_FOLDER)
    with pytest.raises(RunLogError, match=S.LOG_SYMLINK_ERROR), _open(tmp_path):
        pass
    assert not folder.exists()
    folder.mkdir()
    monkeypatch.setattr(Path, S.LOG2_TEST_SYMLINK, lambda path: path.name == S.LOG_FILE_NAME)
    with pytest.raises(RunLogError, match=S.LOG_SYMLINK_ERROR), _open(tmp_path):
        pass
    assert not (folder / S.LOG_FILE_NAME).exists()


def test_mid_run_write_failure_warns_once_and_can_never_end_as_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inject_append_fault(monkeypatch, lambda call: C.TWO <= call <= C.THREE)
    warnings: list[str] = []
    receipt = sync_receipt()
    with _open(tmp_path, warnings=warnings) as log:
        log.event(S.TEST_REPORTING_MESSAGE_ONE)
        log.event(S.TEST_REPORTING_MESSAGE_TWO)
        outcome = log.finish(receipt, explainer(receipt))
    incomplete = S.OUTCOME_LOG_INCOMPLETE.format(reason=S.TEST_OPLOG_DISK_FULL)
    text = _text(tmp_path)
    assert log.problem == S.TEST_OPLOG_DISK_FULL
    assert warnings == [S.OPLOG_WARNING.format(reason=S.TEST_OPLOG_DISK_FULL)]
    assert (outcome.state, outcome.exit_code) == (S.OUTCOME_NEEDS_ATTENTION, C.THREE)
    assert S.OUTCOME_CAUSE_LINE.format(text=incomplete) in outcome.lines
    assert S.TEST_REPORTING_MESSAGE_ONE not in text
    assert (
        S.OPLOG_INDENT + S.OPLOG_DEGRADED.format(count=C.TWO, reason=S.TEST_OPLOG_DISK_FULL)
        in text.splitlines()
    )
    saved = read_summary(tmp_path)
    assert saved is not C.NONE
    assert saved.exit_code == C.THREE


def test_final_write_failure_is_reported_in_the_outcome_and_the_saved_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inject_append_fault(monkeypatch, lambda call: call >= C.TWO)
    warnings: list[str] = []
    receipt = sync_receipt()
    with _open(tmp_path, warnings=warnings) as log:
        outcome = log.finish(receipt, explainer(receipt))
    assert outcome.exit_code == C.THREE
    assert warnings == [S.OPLOG_WARNING.format(reason=S.TEST_OPLOG_DISK_FULL)]
    assert S.OPLOG_END_TOKEN not in _text(tmp_path)
    saved = read_summary(tmp_path)
    assert saved is not C.NONE
    assert (saved.exit_code, saved.lines) == (C.THREE, outcome.lines)
    assert (
        S.OUTCOME_CAUSE_LINE.format(
            text=S.OUTCOME_LOG_INCOMPLETE.format(reason=S.TEST_OPLOG_DISK_FULL)
        )
        in saved.lines
    )


def test_summary_save_failure_is_warned_and_does_not_hide_the_finished_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*arguments: object, **options: object) -> None:
        raise OSError(errno.ENOSPC, S.TEST_OPLOG_DISK_FULL)

    monkeypatch.setattr(os, S.TEST_OPLOG_REPLACE_ATTRIBUTE, refuse)
    warnings: list[str] = []
    receipt = sync_receipt()
    with _open(tmp_path, warnings=warnings) as log:
        outcome = log.finish(receipt, explainer(receipt))
    assert outcome.exit_code == C.ZERO
    assert warnings == [S.OPLOG_SUMMARY_WARNING.format(reason=S.TEST_OPLOG_DISK_FULL)]
    assert _text(tmp_path).count(S.OPLOG_END_TOKEN) == C.ONE
    assert read_summary(tmp_path) is C.NONE
    assert list(summary_path(tmp_path).parent.iterdir()) == []


def test_interrupt_is_recorded_with_exit_code_130_and_the_run_id_seen_so_far(
    tmp_path: Path,
) -> None:
    with pytest.raises(KeyboardInterrupt), _open(tmp_path) as log:
        log.event(S.PROD_RUN_STARTED.format(run_id=C.TEST_OPLOG_RUN_ID))
        raise KeyboardInterrupt
    assert _end_line(_text(tmp_path)) == S.OPLOG_END.format(
        instant=S.TEST_OPLOG_CLOCK_INSTANT,
        run_id=C.TEST_OPLOG_RUN_ID,
        state=S.INTERRUPTED,
        exit_code=C.CLI_MAIN,
        duration=format_duration(C.ZERO),
    )
    assert log.outcome is not C.NONE
    assert log.outcome.lines[-C.ONE] == S.OUTCOME_NEXT_LINE.format(
        action=S.OUTCOME_ACTION_INTERRUPTED
    )
    saved = read_summary(tmp_path)
    assert saved is not C.NONE
    assert (saved.outcome, saved.exit_code) == (S.INTERRUPTED, C.CLI_MAIN)


def test_leaving_the_block_without_a_receipt_is_a_failure_not_a_success(tmp_path: Path) -> None:
    with _open(tmp_path) as log:
        pass
    assert log.outcome is not C.NONE
    assert (log.outcome.state, log.outcome.exit_code) == (S.FAILED, C.ONE)
    assert S.OUTCOME_CAUSE_LINE.format(text=S.OPLOG_NO_RECEIPT) in log.outcome.lines
    assert S.OPLOG_NO_RUN in _end_line(_text(tmp_path))


def test_a_previous_run_without_an_end_line_is_called_out_once(tmp_path: Path) -> None:
    folder = log_directory(tmp_path)
    folder.mkdir()
    killed = S.OPLOG_START.format(instant=S.TEST_OPLOG_CLOCK_INSTANT, trigger=S.SCHEDULED)
    (folder / S.LOG_FILE_NAME).write_text(killed + S.NEWLINE, encoding=S.UTF_8)
    for _ in range(C.TWO):
        with _open(tmp_path) as log:
            log.fail(S.TEST_REPORTING_FAILURE)
    text = _text(tmp_path)
    described = killed.removeprefix(S.OPLOG_START_TOKEN).strip(S.OPLOG_START_STRIP)
    assert text.count(S.TEST_OPLOG_UNTERMINATED_FRAGMENT) == C.ONE
    assert S.OPLOG_UNTERMINATED.format(start=described) in text
    assert text.count(S.OPLOG_START_TOKEN) == C.THREE
    assert text.count(S.OPLOG_END_TOKEN) == C.TWO


def test_finishing_twice_returns_the_same_outcome_and_late_events_are_rejected(
    tmp_path: Path,
) -> None:
    receipt = sync_receipt()
    with _open(tmp_path) as log:
        first = log.finish(receipt, explainer(receipt))
        assert log.finish(receipt, explainer(receipt)) is first
        with pytest.raises(RuntimeError, match=S.LOG_ALREADY_FINISHED):
            log.event(S.TEST_REPORTING_MESSAGE_ONE)
    assert _text(tmp_path).count(S.OPLOG_END_TOKEN) == C.ONE


def test_failure_log_records_state_exit_code_and_redacted_message(tmp_path: Path) -> None:
    path = write_failure_log(
        tmp_path,
        S.TEST_REPORTING_SECRET_MESSAGE,
        secrets=C.TEST_REPORTING_SECRETS,
        state=S.INTERRUPTED,
        exit_code=C.CLI_MAIN,
    )
    text = path.read_text(encoding=S.UTF_8)
    saved = read_summary(tmp_path)
    assert path == log_directory(tmp_path) / S.LOG_FILE_NAME
    assert S.TEST_OPLOG_INTERRUPTED_END in _end_line(text)
    assert S.TEST_REPORTING_SECRET not in text
    assert saved is not C.NONE
    assert saved.trigger == S.LOG_FAILURE_TRIGGER


def test_runs_preserve_history_legacy_logs_unmanaged_files_and_directories(
    tmp_path: Path,
) -> None:
    folder = log_directory(tmp_path)
    folder.mkdir()
    history = S.TEST_OPLOG_LEGACY_TEXT * C.TEST_OPLOG_HISTORY_REPEATS
    persistent = folder / S.LOG_FILE_NAME
    persistent.write_text(history, encoding=S.UTF_8)
    unrelated = folder / S.TEST_REPORTING_UNMANAGED_LOG
    unrelated.write_text(S.TEST_REPORTING_MESSAGE_ONE, encoding=S.UTF_8)
    nested = folder / S.TEST_REPORTING_DIRECTORY_LOG
    nested.mkdir()
    legacy = folder / S.TEST_REPORTING_OLDER_LOG
    legacy.write_text(S.TEST_REPORTING_MESSAGE_TWO, encoding=S.UTF_8)
    first = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    second = write_failure_log(tmp_path, S.TEST_REPORTING_FAILURE, secrets=())
    text = persistent.read_text(encoding=S.UTF_8)
    assert first == second == persistent == latest_log(tmp_path)
    assert text.startswith(history)
    assert text.count(S.OPLOG_START_TOKEN) == text.count(S.OPLOG_END_TOKEN) == C.TWO
    assert unrelated.read_text(encoding=S.UTF_8) == S.TEST_REPORTING_MESSAGE_ONE
    assert legacy.read_text(encoding=S.UTF_8) == S.TEST_REPORTING_MESSAGE_TWO
    assert nested.is_dir()
    assert sorted(path.name for path in folder.iterdir()) == sorted(
        (
            S.LOG_FILE_NAME,
            S.TEST_REPORTING_UNMANAGED_LOG,
            S.TEST_REPORTING_DIRECTORY_LOG,
            S.TEST_REPORTING_OLDER_LOG,
        )
    )


def test_latest_log_uses_write_order_not_start_time_or_lexical_run_id(tmp_path: Path) -> None:
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
