from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import suppress
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from time import monotonic
from types import TracebackType

from bookystats import __version__
from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.outcome import (
    Outcome,
    explain_failure,
    format_duration,
    format_instant,
    readable_deadlines,
    utc_text,
)
from bookystats.application.sync import SyncReceipt
from bookystats.domain.errors import BookyError
from bookystats.domain.models import Issue, SyncState, VerificationResult
from bookystats.runtime.redaction import redact
from bookystats.runtime.runsummary import RunSummary, RunSummaryGate, save_summary


class RunLogError(BookyError):
    pass


def log_directory(directory: Path) -> Path:
    return directory / S.LOGS_FOLDER


def _logs(directory: Path) -> Iterable[Path]:
    return (
        path
        for path in log_directory(directory).glob(S.RUNLOG_PATTERN)
        if C.RUNLOG_NAME_PATTERN.fullmatch(path.name) and not path.is_symlink() and path.is_file()
    )


def latest_log(directory: Path) -> Path | None:
    persistent = log_directory(directory) / S.LOG_FILE_NAME
    if not persistent.is_symlink() and persistent.is_file():
        return persistent
    return max(
        _logs(directory),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        default=C.NONE,
    )


def _safe_text(message: str, secrets: Iterable[str]) -> str:
    result = redact(message, secrets)
    for pattern in C.LOG_SECRET_PATTERNS:
        result = pattern.sub(S.REDACTION_REDACT_RESULT_REDACTED_2, result)
    result = C.OPLOG_URL_QUERY.sub(S.OPLOG_URL_QUERY_REPLACEMENT, result)
    return C.LOG2_PATH_PATTERN.sub(S.REDACTION_REDACT_RESULT_REDACTED, result)


def _clip(text: str) -> str:
    text = S.SPACE.join(text.split())
    if len(text) > C.LOG_ISSUE_MESSAGE_LENGTH:
        return text[: C.LOG_ISSUE_MESSAGE_LENGTH] + S.OPLOG_TRUNCATED
    return text


def _append(directory: Path, lines: Iterable[str], secrets: Iterable[str]) -> Path:
    body = tuple(lines)
    folder = log_directory(directory)
    path = folder / S.LOG_FILE_NAME
    if not body:
        return path
    text = _safe_text(S.NEWLINE.join(body) + S.NEWLINE, secrets)
    try:
        # The caller holds SyncLock across a run; this lock also keeps same-process
        # diagnostic writers from interleaving a multi-line event.
        with C.LOG_WRITE_LOCK:
            if folder.is_symlink():
                raise RunLogError(S.LOG_SYMLINK_ERROR)
            folder.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
            if path.is_symlink():
                raise RunLogError(S.LOG_SYMLINK_ERROR)
            with path.open(
                S.LOG_APPEND_MODE,
                encoding=S.UTF_8,
                errors=S.OPLOG_BACKSLASHREPLACE,
                newline=S.NEWLINE,
            ) as handle:
                handle.write(text)
                handle.flush()
    except OSError as exc:
        # Only the OS reason is kept: exception text can carry the file path.
        raise RunLogError(exc.strerror or type(exc).__name__) from C.NONE
    return path


def _unterminated_start(path: Path) -> str | None:
    # Best effort over the newest bytes only; an unreadable tail simply shows no notice.
    try:
        if path.is_symlink() or not path.is_file():
            return C.NONE
        with path.open(S.OPLOG_READ_BINARY) as handle:
            handle.seek(max(C.ZERO, path.stat().st_size - C.OPLOG_TAIL_BYTES))
            tail = handle.read().decode(S.UTF_8, errors=S.OPLOG_BACKSLASHREPLACE)
    except OSError:
        return C.NONE
    started = tail.rfind(S.OPLOG_START_TOKEN)
    if started < C.ZERO or tail.rfind(S.OPLOG_END_TOKEN) > started:
        return C.NONE
    # The notice keeps only the instant and trigger, so it never reads as a run boundary itself.
    first = tail[started:].splitlines()[C.ZERO]
    return first.removeprefix(S.OPLOG_START_TOKEN).strip(S.OPLOG_START_STRIP)


def _receipt_lines(receipt: SyncReceipt, secrets: Iterable[str], zone: tzinfo) -> list[str]:
    complete = [source for source in receipt.sources if source.state == SyncState.COMPLETE]
    lines = [
        S.OPLOG_INDENT + S.OPLOG_RUN_LINE.format(run_id=receipt.run_id, state=receipt.state.value),
        S.OPLOG_INDENT
        + S.OPLOG_SOURCES.format(
            complete=len(complete),
            total=len(receipt.sources),
            records=sum(source.records for source in complete),
        ),
    ]
    if any(source.input_kind == S.INPUT_FILE for source in receipt.sources):
        lines.append(S.OPLOG_INDENT + S.OPLOG_FILE_SCOPE)
    for source in receipt.sources:
        publication = source.publication
        if publication is C.NONE:
            text = S.OPLOG_SOURCE_UNPUBLISHED.format(
                source=source.source.value, collection=source.collection, state=source.state.value
            )
        else:
            text = S.OPLOG_SOURCE_LINE.format(
                source=source.source.value,
                collection=source.collection,
                state=source.state.value,
                records=source.records,
                added=publication.added,
                updated=publication.updated,
                unchanged=publication.unchanged,
                removed=publication.removed,
            )
        lines.append(S.OPLOG_DEEP_INDENT + text)
    lines.extend(
        S.OPLOG_INDENT
        + S.OPLOG_CORE.format(
            provider=metadata.provider.value,
            unresolved=metadata.fallback_unresolved,
            skipped=metadata.skipped_by_strategy,
        )
        for metadata in receipt.metadata
        if metadata.coverage_scope == S.ENR_CORE_COVERAGE_SCOPE
    )
    if receipt.analytics is not C.NONE:
        analytics = receipt.analytics
        lines.append(
            S.OPLOG_INDENT
            + S.OPLOG_ANALYTICS.format(
                state=analytics.state.value,
                report_id=analytics.report_id,
                read=analytics.read_works,
                rated=analytics.rated_read,
                taste=S.OPLOG_YES if analytics.taste_reused else S.OPLOG_NO,
                watchlist=S.OPLOG_YES if analytics.watchlist_reused else S.OPLOG_NO,
            )
        )
    if receipt.products is not C.NONE:
        products = receipt.products
        lines.append(
            S.OPLOG_INDENT
            + (
                S.LOG2_PRODUCTS
                if products.state == SyncState.COMPLETE
                else S.LOG2_PRODUCTS_RETAINED
            ).format(state=products.state.value, report_id=products.analytics_report_id)
        )
    lines.extend(_verification_lines(receipt))
    lines.extend(_issue_summary_lines(receipt, secrets, zone))
    return lines


def _verification_lines(receipt: SyncReceipt) -> list[str]:
    verification = receipt.verification
    if verification is C.NONE:
        return [S.OPLOG_INDENT + S.OPLOG_VERIFICATION_NONE]
    failed = [check for check in verification.checks if check.result != VerificationResult.SUCCESS]
    lines = [
        S.OPLOG_INDENT
        + S.OPLOG_VERIFICATION.format(
            result=verification.result.value,
            passed=len(verification.checks) - len(failed),
            total=len(verification.checks),
        )
    ]
    lines.extend(
        S.OPLOG_DEEP_INDENT
        + _clip(
            S.OPLOG_CHECK_LINE.format(
                name=check.name, result=check.result.value, detail=check.detail
            )
        )
        for check in failed[: C.OPLOG_MAX_CHECKS]
    )
    if len(failed) > C.OPLOG_MAX_CHECKS:
        lines.append(
            S.OPLOG_DEEP_INDENT + S.OPLOG_CHECKS_MORE.format(count=len(failed) - C.OPLOG_MAX_CHECKS)
        )
    return lines


def _issue_group_lines(
    scope: str, issues: Iterable[Issue], secrets: Iterable[str], zone: tzinfo
) -> list[str]:
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, C.ZERO) + C.ONE
        samples = examples.setdefault(issue.code, [])
        if issue.code in C.LOG2_EXPECTED_NOTICE_CODES or len(samples) >= C.LOG_ISSUE_EXAMPLES:
            continue
        sample = _clip(readable_deadlines(_safe_text(issue.message, secrets), zone))
        if sample not in samples:
            samples.append(sample)
    lines: list[str] = []
    for code, count in sorted(counts.items()):
        template = S.OPLOG_ISSUE_COUNT_ONE if count == C.ONE else S.OPLOG_ISSUE_COUNT
        lines.append(S.OPLOG_DEEP_INDENT + template.format(scope=scope, code=code, count=count))
        lines.extend(
            S.OPLOG_EXAMPLE_INDENT + S.OPLOG_ISSUE_EXAMPLE.format(message=sample)
            for sample in examples[code]
        )
    return lines


def _issue_summary_lines(receipt: SyncReceipt, secrets: Iterable[str], zone: tzinfo) -> list[str]:
    scopes: dict[str, list[Issue]] = {}
    for source in receipt.sources:
        scope = source.source.value + S.SLASH + source.collection
        scopes.setdefault(scope, []).extend(source.issues)
    for provider in receipt.metadata:
        scopes.setdefault(provider.provider.value, []).extend(provider.issues)
    if receipt.analytics is not C.NONE:
        scopes.setdefault(S.LOG_ANALYTICS_SCOPE, []).extend(receipt.analytics.issues)
    if receipt.products is not C.NONE:
        scopes.setdefault(S.LOG_DELIVERY_SCOPE, []).extend(receipt.products.issues)
    lines = [
        line
        for scope, issues in scopes.items()
        for line in _issue_group_lines(scope, issues, secrets, zone)
    ]
    if not lines:
        return [S.OPLOG_INDENT + S.OPLOG_ISSUES_NONE]
    heading = S.OPLOG_INDENT + S.OPLOG_ISSUES_HEADING.format(limit=C.LOG_ISSUE_EXAMPLES)
    lines.insert(C.ZERO, heading)
    if any(
        issue.code in C.LOG2_EXPECTED_NOTICE_CODES for issues in scopes.values() for issue in issues
    ):
        lines.append(S.OPLOG_INDENT + S.LOG2_NOTICE_EXPLANATION)
    return lines


def _system_now() -> datetime:
    return datetime.now(UTC).astimezone()


def _gate_time(epoch: float) -> str | None:
    try:
        return utc_text(datetime.fromtimestamp(epoch, UTC))
    except (OverflowError, OSError, ValueError):
        return C.NONE


def _unexpected(exc: BaseException, traceback: TracebackType | None) -> str:
    # Only the exception type and the innermost first-party frame: its text may hold private data.
    where: tuple[str, int, str] | None = C.NONE
    while traceback is not C.NONE:
        frame = traceback.tb_frame
        module = frame.f_globals.get(S.OPLOG_MODULE_KEY)
        if isinstance(module, str) and module.startswith(S.OPLOG_MODULE_PREFIX):
            where = (module, traceback.tb_lineno, frame.f_code.co_qualname)
        traceback = traceback.tb_next
    if where is C.NONE:
        return S.OPLOG_UNEXPECTED_BARE.format(type=type(exc).__name__)
    return S.OPLOG_UNEXPECTED.format(
        type=type(exc).__name__, module=where[C.ZERO], line=where[C.ONE], function=where[C.TWO]
    )


class OperationalLog:
    def __init__(
        self,
        directory: Path,
        *,
        trigger: str,
        secrets: Iterable[str] = (),
        clock: Callable[[], datetime] = _system_now,
        timer: Callable[[], float] = monotonic,
        warn: Callable[[str], None] | None = C.NONE,
    ) -> None:
        self.directory = directory
        self.trigger = trigger
        self.secrets = tuple(secrets)
        self.path = log_directory(directory) / S.LOG_FILE_NAME
        self.problem: str | None = C.NONE
        self.run_id: int | None = C.NONE
        self.outcome: Outcome | None = C.NONE
        self._clock = clock
        self._timer = timer
        self._warn = warn
        self._began: float = C.ZERO
        self._finished = C.FALSE
        self._dropped = C.ZERO
        self._stages: dict[str, float] = {}
        self._open: tuple[str, float] | None = C.NONE

    def now(self) -> datetime:
        return self._clock()

    def elapsed(self) -> float:
        return max(C.ZERO, self._timer() - self._began)

    def _zone(self) -> tzinfo:
        return self._clock().tzinfo or UTC

    def _instant(self) -> str:
        moment = self._clock()
        return format_instant(moment.timestamp(), moment.tzinfo)

    def _notify(self, text: str) -> None:
        if self._warn is not C.NONE:
            with suppress(OSError, ValueError):
                self._warn(text)

    def _degrade(self, reason: str, lost: int) -> None:
        self._dropped += lost
        if self.problem is C.NONE:
            self.problem = reason
            self._notify(S.OPLOG_WARNING.format(reason=reason))

    def __enter__(self) -> OperationalLog:
        self._began = self._timer()
        previous = _unterminated_start(self.path)
        lines = [
            S.EMPTY,
            S.OPLOG_START.format(instant=self._instant(), trigger=self.trigger),
            S.OPLOG_VERSION_LINE.format(version=__version__, format=C.OPLOG_FORMAT),
        ]
        if previous is not C.NONE:
            lines.append(S.OPLOG_UNTERMINATED.format(start=previous))
        _append(self.directory, lines, self.secrets)
        return self

    def _close_stage(self) -> None:
        if self._open is not C.NONE:
            name, began = self._open
            spent = max(C.ZERO, self._timer() - began)
            self._stages[name] = self._stages.get(name, C.ZERO) + spent
            self._open = C.NONE

    def _track(self, message: str) -> None:
        first = next(iter(message.splitlines()), S.EMPTY)
        if self.run_id is C.NONE:
            started = C.OPLOG_RUN_STARTED.fullmatch(first)
            if started is not C.NONE:
                self.run_id = int(started[C.ONE])
        finished = C.OPLOG_RUN_FINISHED.fullmatch(first)
        if first.startswith(S.OPLOG_STAGE_PREFIX) or finished is not C.NONE:
            self._close_stage()
            if finished is C.NONE:
                name = first.removeprefix(S.OPLOG_STAGE_PREFIX).removesuffix(S.OPLOG_PERIOD)
                self._open = (name, self._timer())

    def event(self, message: str) -> None:
        if self._finished:
            raise RuntimeError(S.LOG_ALREADY_FINISHED)
        self._track(message)
        stamp = self._clock().isoformat(sep=S.SPACE, timespec=S.OUTCOME_SECONDS)
        lines = tuple(
            S.OPLOG_EVENT.format(stamp=stamp, message=line) for line in message.splitlines()
        )
        try:
            _append(self.directory, lines, self.secrets)
        except RunLogError as exc:
            self._degrade(str(exc), len(lines))

    def _time_lines(self, total: float) -> list[str]:
        if not self._stages:
            return []
        lines = [S.OPLOG_INDENT + S.OPLOG_TIME_HEADING]
        lines.extend(
            S.OPLOG_DEEP_INDENT
            + S.OPLOG_TIME_LINE.format(duration=format_duration(seconds), stage=name)
            for name, seconds in self._stages.items()
        )
        other = max(C.ZERO, total - sum(self._stages.values()))
        lines.append(
            S.OPLOG_DEEP_INDENT
            + S.OPLOG_TIME_LINE.format(duration=format_duration(other), stage=S.OPLOG_TIME_OTHER)
        )
        return lines

    def _write_end(self, outcome: Outcome, receipt: SyncReceipt | None) -> None:
        body = [
            *(_receipt_lines(receipt, self.secrets, self._zone()) if receipt is not C.NONE else ()),
            *self._time_lines(outcome.duration_seconds),
        ]
        if self._dropped:
            body.append(
                S.OPLOG_INDENT + S.OPLOG_DEGRADED.format(count=self._dropped, reason=self.problem)
            )
        end = S.OPLOG_END.format(
            instant=self._instant(),
            run_id=self.run_id if self.run_id is not C.NONE else S.OPLOG_NO_RUN,
            state=outcome.state,
            exit_code=outcome.exit_code,
            duration=format_duration(outcome.duration_seconds),
        )
        summary = [S.OPLOG_SUMMARY_HEADING, *body] if body else []
        _append(self.directory, (*summary, *outcome.lines, end), self.secrets)

    def _save_summary(self, outcome: Outcome) -> None:
        gates: list[RunSummaryGate] = []
        for gate in outcome.gates:
            retry = _gate_time(gate.retry_at)
            if retry is not C.NONE:
                gates.append(
                    RunSummaryGate(
                        provider=gate.provider.value,
                        retry_at_utc=retry,
                        http_status=gate.status_code,
                        error_code=_safe_text(gate.error_code, self.secrets)
                        if gate.error_code is not C.NONE
                        else C.NONE,
                    )
                )
        summary = RunSummary(
            schema_version=C.RUNSUM_SCHEMA_VERSION,
            run_id=self.run_id,
            trigger=self.trigger,
            outcome=outcome.state,
            exit_code=outcome.exit_code,
            finished_utc=utc_text(self._clock()),
            duration_seconds=round(outcome.duration_seconds, C.ONE),
            lines=tuple(_safe_text(line, self.secrets) for line in outcome.lines),
            gates=tuple(gates),
            network_requests=dict(outcome.network_requests),
        )
        try:
            save_summary(self.directory, summary)
        except OSError as exc:
            self._notify(S.OPLOG_SUMMARY_WARNING.format(reason=exc.strerror or type(exc).__name__))

    def _conclude(
        self, explain: Callable[[str | None], Outcome], receipt: SyncReceipt | None
    ) -> Outcome:
        outcome = explain(self.problem)
        self._finished = C.TRUE
        self._close_stage()
        try:
            self._write_end(outcome, receipt)
        except RunLogError as exc:
            self._degrade(str(exc), C.ONE)
            outcome = explain(self.problem)
        self.outcome = outcome
        self._save_summary(outcome)
        return outcome

    def finish(self, receipt: SyncReceipt, explain: Callable[[str | None], Outcome]) -> Outcome:
        if self.outcome is not C.NONE:
            return self.outcome
        if self.run_id is C.NONE:
            self.run_id = receipt.run_id
        return self._conclude(explain, receipt)

    def fail(self, detail: str, *, state: str = S.FAILED, exit_code: int = C.ONE) -> Outcome:
        if self.outcome is not C.NONE:
            return self.outcome
        text = _clip(readable_deadlines(_safe_text(detail, self.secrets), self._zone()))
        return self._conclude(
            lambda error: explain_failure(
                state=state,
                exit_code=exit_code,
                detail=text,
                duration_seconds=self.elapsed(),
                log_error=error,
            ),
            C.NONE,
        )

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._finished:
            return
        if isinstance(exc, KeyboardInterrupt | EOFError):
            self.fail(S.OPLOG_INTERRUPTED, state=S.INTERRUPTED, exit_code=C.CLI_MAIN)
        elif isinstance(exc, BookyError):
            self.fail(str(exc))
        elif exc is not C.NONE:
            self.fail(_unexpected(exc, traceback))
        else:
            self.fail(S.OPLOG_NO_RECEIPT)


def write_failure_log(
    directory: Path,
    message: str,
    *,
    secrets: Iterable[str],
    trigger: str = S.LOG_FAILURE_TRIGGER,
    state: str = S.FAILED,
    exit_code: int = C.ONE,
) -> Path:
    with OperationalLog(directory, trigger=trigger, secrets=secrets) as log:
        log.fail(message, state=state, exit_code=exit_code)
        if log.problem is not C.NONE:
            raise RunLogError(log.problem)
        return log.path
