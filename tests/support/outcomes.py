from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.outcome import Gate, Outcome, explain_outcome
from bookystats.application.sync import MetadataReceipt, SourceReceipt, SyncReceipt
from bookystats.domain.interfaces import HttpRetryState
from bookystats.domain.models import (
    Issue,
    PublicationResult,
    Source,
    SyncState,
    Verification,
)
from bookystats.runtime import runlog
from bookystats.runtime.runlog import RunLogError


def local_clock() -> datetime:
    return datetime.fromisoformat(S.TEST_REPORTING_OFFSET_TIME)


class AppendFault:
    # Replaces the log writer: the chosen numbered calls fail like a full disk, others write.
    def __init__(self, fails: Callable[[int], bool]) -> None:
        self.fails = fails
        self.calls = C.ZERO
        self.write = runlog._append

    def __call__(self, directory: Path, lines: Iterable[str], secrets: Iterable[str]) -> Path:
        self.calls += C.ONE
        if self.fails(self.calls):
            raise RunLogError(S.TEST_OPLOG_DISK_FULL)
        return self.write(directory, lines, secrets)


def inject_append_fault(
    monkeypatch: pytest.MonkeyPatch, fails: Callable[[int], bool]
) -> AppendFault:
    fault = AppendFault(fails)
    monkeypatch.setattr(runlog, S.TEST_OPLOG_APPEND_ATTRIBUTE, fault)
    return fault


def explainer(
    receipt: SyncReceipt, *, exit_code: int = C.ZERO, duration: float = C.TEST_OPLOG_TOTAL
) -> Callable[[str | None], Outcome]:
    # Mirrors the CLI: a log that could not be written never leaves the run looking complete.
    def explain(error: str | None) -> Outcome:
        return explain_outcome(
            receipt,
            exit_code=exit_code if error is C.NONE else C.THREE,
            now=local_clock(),
            duration_seconds=duration,
            log_error=error,
        )

    return explain


class StepTimer:
    # A monotonic clock the test advances explicitly.
    def __init__(self) -> None:
        self.value: float = C.ZERO

    def __call__(self) -> float:
        return self.value


class RetryStore:
    # Scripted retry state; an exception value is raised, like an unreadable cache.
    def __init__(self) -> None:
        self.states: dict[tuple[Source, str], HttpRetryState | Exception] = {}

    def get_retry_state(self, provider: Source, host: str) -> HttpRetryState | None:
        state = self.states.get((provider, host))
        if isinstance(state, Exception):
            raise state
        return state

    def save_retry_state(self, provider: Source, host: str, state: HttpRetryState) -> None:
        self.states[(provider, host)] = state


def complete_sources() -> tuple[SourceReceipt, ...]:
    return tuple(
        SourceReceipt(
            source=source,
            collection=collection,
            state=SyncState.COMPLETE,
            records=C.ONE,
            input_kind=S.INPUT_FILE,
            publication=PublicationResult(snapshot_id=C.ONE, added=C.ONE),
        )
        for source, collection in (
            (Source.STORYGRAPH, S.LIBRARY),
            (Source.GOODREADS, S.TO_READ),
            (Source.GOODREADS, S.READ),
        )
    )


def sync_receipt(
    *,
    state: SyncState = SyncState.COMPLETE,
    sources: tuple[SourceReceipt, ...] | None = C.NONE,
    metadata: tuple[MetadataReceipt, ...] = (),
    verification: Verification | None = C.NONE,
) -> SyncReceipt:
    return SyncReceipt(
        run_id=C.TEST_OPLOG_RUN_ID,
        state=state,
        started_at=S.TEST_REPORTING_FIRST_TIME,
        finished_at=S.TEST_REPORTING_SECOND_TIME,
        account_sync_complete=C.FALSE,
        sources=complete_sources() if sources is C.NONE else sources,
        metadata=metadata,
        verification=verification,
    )


def paused_metadata() -> tuple[MetadataReceipt, ...]:
    # Google Books deferred behind a provider pause; Open Library has nothing more due.
    return (
        MetadataReceipt(
            provider=Source.GOOGLE_BOOKS,
            state=SyncState.PARTIAL,
            requested=C.LOG2_TEST_LARGE_TOTAL,
            processed=C.TEST_OPLOG_PROCESSED,
            cache_hits=C.TEST_OPLOG_CACHE_HITS,
            skipped_by_strategy=C.TEST_OPLOG_SKIPPED,
            deferred=C.TEST_OPLOG_DEFERRED,
            issues=(
                Issue(
                    code=S.PROVIDER_COOLDOWN,
                    message=S.DR_COOLDOWN_MESSAGE.format(deadline=C.TEST_OPLOG_GATE_EPOCH),
                ),
            ),
        ),
        MetadataReceipt(
            provider=Source.OPEN_LIBRARY,
            state=SyncState.PARTIAL,
            requested=C.LOG2_TEST_LARGE_TOTAL,
            processed=C.TEST_OPLOG_PROCESSED,
            issues=(Issue(code=S.QUEUE_NO_LOOKUPS_DUE_CODE, message=S.TEST_REPORTING_MESSAGE_ONE),),
        ),
    )


def google_gate() -> Gate:
    return Gate(Source.GOOGLE_BOOKS, C.TEST_OPLOG_GATE_EPOCH, C.TEST_OPLOG_HTTP_STATUS)
