from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from types import TracebackType

from bookystats import __version__
from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import SyncReceipt
from bookystats.domain.models import Issue, Source, SyncState, utc_now
from bookystats.persistence.raw import RawDocument
from bookystats.runtime.redaction import redact


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


def prune_logs(directory: Path, *, keep: Path) -> None:
    # Compatibility for callers of the old retention helper: history is never removed.
    return


def _utc(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp).astimezone(UTC).isoformat()


def _safe_text(message: str, secrets: Iterable[str]) -> str:
    result = redact(message, secrets)
    for pattern in C.LOG_SECRET_PATTERNS:
        result = pattern.sub(S.REDACTION_REDACT_RESULT_REDACTED_2, result)
    return C.LOG2_PATH_PATTERN.sub(S.REDACTION_REDACT_RESULT_REDACTED, result)


def _append(directory: Path, lines: Iterable[str], secrets: Iterable[str]) -> Path:
    text = _safe_text(S.NEWLINE.join(lines) + S.NEWLINE, secrets)
    folder = log_directory(directory)
    path = folder / S.LOG_FILE_NAME
    # The caller holds SyncLock across a run; this lock also keeps same-process
    # diagnostic writers from interleaving a multi-line event.
    with C.LOG_WRITE_LOCK:
        if folder.is_symlink():
            raise OSError(S.LOG_SYMLINK_ERROR)
        folder.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
        if path.is_symlink():
            raise OSError(S.LOG_SYMLINK_ERROR)
        with path.open(S.LOG_APPEND_MODE, encoding=S.UTF_8, newline=S.NEWLINE) as handle:
            handle.write(text)
            handle.flush()
    return path


def _receipt_lines(
    receipt: SyncReceipt,
    trigger: str,
    inputs: Mapping[tuple[Source, str], RawDocument],
    report_lines: Iterable[str],
) -> list[str]:
    lines = [
        S.RUNLOG_TITLE,
        S.RUNLOG_RUN_LINE.format(run_id=receipt.run_id, trigger=trigger),
        S.RUNLOG_STATE_LINE.format(state=receipt.state.value),
        S.RUNLOG_STARTED_LINE.format(started=_utc(receipt.started_at)),
        S.RUNLOG_FINISHED_LINE.format(finished=_utc(receipt.finished_at)),
    ]
    if inputs:
        lines.extend([S.EMPTY, S.RUNLOG_FILES_HEADING])
        lines.extend(
            S.RUNLOG_FILE_LINE.format(
                source=source.value + S.SLASH + collection,
                origin=PureWindowsPath(document.origin).name,
                size=len(document.body),
                sha256=document.sha256,
                captured=document.captured_at,
                document=document.id,
            )
            for (source, collection), document in inputs.items()
        )
    lines.extend([S.EMPTY, *report_lines])
    return lines


def _compact_receipt_lines(receipt: SyncReceipt) -> list[str]:
    lines = [
        S.LOG2_RECEIPT.format(run_id=receipt.run_id, state=receipt.state.value),
        S.LOG2_SOURCES.format(
            complete=sum(source.state == SyncState.COMPLETE for source in receipt.sources),
            total=len(receipt.sources),
            records=sum(
                source.records for source in receipt.sources if source.state == SyncState.COMPLETE
            ),
        ),
    ]
    for metadata in receipt.metadata:
        lines.append(
            S.LOG2_METADATA.format(
                provider=metadata.provider.value,
                state=metadata.state.value,
                processed=metadata.processed,
                requested=metadata.requested,
                deferred=metadata.deferred,
            )
        )
        if metadata.coverage_scope == S.ENR_CORE_COVERAGE_SCOPE:
            lines.append(
                S.LOG2_CORE.format(
                    unresolved=metadata.fallback_unresolved,
                    skipped=metadata.skipped_by_strategy,
                )
            )
    if receipt.analytics is not C.NONE:
        lines.append(
            S.LOG2_ANALYTICS.format(
                state=receipt.analytics.state.value,
                report_id=receipt.analytics.report_id,
                read=receipt.analytics.read_works,
                rated=receipt.analytics.rated_read,
            )
        )
    if receipt.products is not C.NONE:
        products = receipt.products
        lines.append(
            (
                S.LOG2_PRODUCTS
                if products.state == SyncState.COMPLETE
                else S.LOG2_PRODUCTS_RETAINED
            ).format(state=products.state.value, report_id=products.analytics_report_id)
        )
    if receipt.verification is not C.NONE:
        lines.append(S.LOG2_VERIFICATION.format(result=receipt.verification.result.value))
    return lines


def _issue_group_lines(scope: str, issues: Iterable[Issue], secrets: Iterable[str]) -> list[str]:
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, C.ZERO) + C.ONE
        samples = examples.setdefault(issue.code, [])
        if issue.code in C.LOG2_EXPECTED_NOTICE_CODES:
            continue
        if len(samples) >= C.LOG_ISSUE_EXAMPLES:
            continue
        sample = S.SPACE.join(_safe_text(issue.message, secrets).split())
        if len(sample) > C.LOG_ISSUE_MESSAGE_LENGTH:
            sample = sample[: C.LOG_ISSUE_MESSAGE_LENGTH] + S.LOG_ISSUE_TRUNCATED
        if sample not in samples:
            samples.append(sample)
    lines: list[str] = []
    for code, count in sorted(counts.items()):
        lines.append(S.LOG_ISSUE_COUNT.format(scope=scope, code=code, count=count))
        lines.extend(S.LOG_ISSUE_EXAMPLE.format(message=sample) for sample in examples[code])
    return lines


def _issue_summary_lines(
    receipt: SyncReceipt, delivery_issues: Iterable[Issue], secrets: Iterable[str]
) -> list[str]:
    scopes: dict[str, list[Issue]] = {}
    for source in receipt.sources:
        scope = source.source.value + S.SLASH + source.collection
        scopes.setdefault(scope, []).extend(source.issues)
    for provider in receipt.metadata:
        scopes.setdefault(provider.provider.value, []).extend(provider.issues)
    if receipt.analytics is not C.NONE:
        scopes.setdefault(S.LOG_ANALYTICS_SCOPE, []).extend(receipt.analytics.issues)
    delivery = tuple(delivery_issues)
    if not delivery and receipt.products is not C.NONE:
        delivery = receipt.products.issues
    scopes.setdefault(S.LOG_DELIVERY_SCOPE, []).extend(delivery)
    lines = [
        line
        for scope, issues in scopes.items()
        for line in _issue_group_lines(scope, issues, secrets)
    ]
    if any(
        issue.code in C.LOG2_EXPECTED_NOTICE_CODES for issues in scopes.values() for issue in issues
    ):
        lines.append(S.LOG2_NOTICE_EXPLANATION)
    return [S.EMPTY, S.LOG_ISSUES_HEADING, *lines] if lines else []


class OperationalLog:
    def __init__(
        self,
        directory: Path,
        *,
        trigger: str,
        secrets: Iterable[str] = (),
        compact_receipts: bool = C.FALSE,
    ) -> None:
        self.directory = directory
        self.trigger = trigger
        self.secrets = tuple(secrets)
        self.path = log_directory(directory) / S.LOG_FILE_NAME
        self._finished = C.FALSE
        self.compact_receipts = compact_receipts

    def __enter__(self) -> OperationalLog:
        _append(
            self.directory,
            (
                S.EMPTY,
                S.LOG2_RUN_START.format(time=_utc(utc_now()), trigger=self.trigger),
                S.RUNLOG_VERSION_LINE.format(version=__version__),
            ),
            self.secrets,
        )
        return self

    def event(self, message: str) -> None:
        if self._finished:
            raise RuntimeError(S.LOG_ALREADY_FINISHED)
        timestamp = _utc(utc_now())
        _append(
            self.directory,
            (S.LOG2_EVENT.format(time=timestamp, message=line) for line in message.splitlines()),
            self.secrets,
        )

    def finish(
        self,
        receipt: SyncReceipt,
        *,
        inputs: Mapping[tuple[Source, str], RawDocument],
        report_lines: Iterable[str],
        delivery_issues: Iterable[Issue] = (),
    ) -> Path:
        if not self._finished:
            receipt_lines = (
                [*_compact_receipt_lines(receipt), *report_lines]
                if self.compact_receipts
                else _receipt_lines(receipt, self.trigger, inputs, report_lines)
            )
            _append(
                self.directory,
                (
                    *receipt_lines,
                    *_issue_summary_lines(receipt, delivery_issues, self.secrets),
                    S.LOG2_RUN_END.format(time=_utc(utc_now()), outcome=receipt.state.value),
                ),
                self.secrets,
            )
            self._finished = C.TRUE
        return self.path

    def fail(self, message: str) -> Path:
        if not self._finished:
            _append(
                self.directory,
                (
                    S.RUNLOG_FAILED_TITLE,
                    S.RUNLOG_TIME_LINE.format(time=_utc(utc_now())),
                    S.RUNLOG_FAILURE_LINE.format(message=message),
                    S.LOG2_RUN_END.format(time=_utc(utc_now()), outcome=S.FAILED),
                ),
                self.secrets,
            )
            self._finished = C.TRUE
        return self.path

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self._finished:
            self.fail(
                S.LOG_INTERRUPTED
                if exc is C.NONE
                else S.LOG_EXCEPTION.format(type=type(exc).__name__, message=str(exc))
            )


def write_run_log(
    directory: Path,
    receipt: SyncReceipt,
    *,
    trigger: str,
    inputs: Mapping[tuple[Source, str], RawDocument],
    secrets: Iterable[str],
    report_lines: Iterable[str],
) -> Path:
    with OperationalLog(directory, trigger=trigger, secrets=secrets) as log:
        return log.finish(receipt, inputs=inputs, report_lines=report_lines)


def write_failure_log(directory: Path, message: str, *, secrets: Iterable[str]) -> Path:
    with OperationalLog(directory, trigger=S.LOG_FAILURE_TRIGGER, secrets=secrets) as log:
        return log.fail(message)
