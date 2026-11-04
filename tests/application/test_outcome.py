from __future__ import annotations

from datetime import UTC, datetime

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.outcome import (
    RunProbe,
    explain_failure,
    explain_outcome,
    format_duration,
    format_instant,
    parse_utc,
    readable_deadlines,
    utc_text,
)
from bookystats.application.sync import MetadataReceipt, SourceReceipt
from bookystats.domain.errors import BookyError
from bookystats.domain.interfaces import HttpRetryState
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
from tests.support.outcomes import (
    RetryStore,
    complete_sources,
    google_gate,
    local_clock,
    paused_metadata,
    sync_receipt,
)


def _causes(lines: tuple[str, ...]) -> list[str]:
    return [line for line in lines if line.startswith(S.TEST_OPLOG_WHY)]


def test_complete_run_reports_counts_and_has_no_cause_lines() -> None:
    receipt = sync_receipt(
        metadata=(
            MetadataReceipt(
                provider=Source.OPEN_LIBRARY,
                state=SyncState.COMPLETE,
                requested=C.THREE,
                processed=C.THREE,
                cache_hits=C.ONE,
            ),
        )
    )
    outcome = explain_outcome(
        receipt,
        exit_code=C.ZERO,
        now=local_clock(),
        network_requests=((S.OPEN_LIBRARY, C.TEST_OPLOG_NETWORK),),
        duration_seconds=C.TEST_OPLOG_DURATION,
    )
    assert (outcome.state, outcome.exit_code) == (S.COMPLETE, C.ZERO)
    assert outcome.lines[C.ZERO] == S.OUTCOME_HEADLINE.format(
        state=S.COMPLETE.upper(), exit_code=C.ZERO, duration=S.TEST_OPLOG_SECONDS_TEXT
    )
    assert S.OUTCOME_COMPLETE.format(finished=C.THREE, total=C.THREE) in outcome.lines
    assert not _causes(outcome.lines)
    assert (
        S.OUTCOME_LOOKUPS.format(
            provider=S.OUTCOME_OPEN_LIBRARY,
            state=S.COMPLETE,
            processed=C.THREE,
            requested=C.THREE,
            deferred=C.ZERO,
            hits=C.ONE,
            network=S.OUTCOME_NETWORK.format(count=C.TEST_OPLOG_NETWORK),
        )
        in outcome.lines
    )


def test_source_only_success_does_not_claim_metadata_or_provider_recovery() -> None:
    outcome = explain_outcome(sync_receipt(), exit_code=C.ZERO, now=local_clock())
    assert outcome.state == S.COMPLETE
    assert S.LOG3_LOOKUPS_OFF in outcome.lines


def test_paused_provider_is_explained_with_local_and_utc_time_without_quota_claims() -> None:
    outcome = explain_outcome(
        sync_receipt(metadata=paused_metadata()),
        exit_code=C.THREE,
        now=local_clock(),
        gates=(google_gate(),),
        network_requests=((S.GOOGLE_BOOKS, C.TEST_OPLOG_NETWORK),),
        duration_seconds=C.TEST_OPLOG_MINUTES,
    )
    text = S.NEWLINE.join(outcome.lines)
    assert (outcome.state, outcome.exit_code) == (S.OUTCOME_NEEDS_ATTENTION, C.THREE)
    assert (
        S.OUTCOME_CAUSE_LINE.format(
            text=S.OUTCOME_PAUSED.format(
                provider=S.OUTCOME_GOOGLE_BOOKS,
                until=S.TEST_OPLOG_GATE_INSTANT,
                reason=S.OUTCOME_AFTER_HTTP.format(status=C.TEST_OPLOG_HTTP_STATUS),
                waiting=S.OUTCOME_WAITING.format(
                    waiting=S.OUTCOME_BOOKS.format(count=C.TEST_OPLOG_DEFERRED)
                ),
            )
        )
        in outcome.lines
    )
    assert (
        S.OUTCOME_NEXT_LINE.format(
            action=S.OUTCOME_ACTION_PAUSED.format(until=S.TEST_OPLOG_GATE_INSTANT)
        )
        in outcome.lines
    )
    assert S.OUTCOME_PARKED.format(provider=S.OUTCOME_OPEN_LIBRARY) in text
    assert not any(word in text.lower() for word in (S.TEST_OPLOG_QUOTA, S.TEST_OPLOG_RESET))
    assert str(int(C.TEST_OPLOG_GATE_EPOCH)) not in text
    assert outcome.gates == (google_gate(),)


def test_each_provider_cause_has_its_own_next_action() -> None:
    waiting = S.OUTCOME_BOOKS.format(count=C.THREE)
    name = S.OUTCOME_GOOGLE_BOOKS
    cases = (
        (
            S.REQUEST_BUDGET_EXHAUSTED,
            S.OUTCOME_BUDGET.format(provider=name, waiting=waiting),
            S.OUTCOME_ACTION_BUDGET,
        ),
        (
            S.OAUTH_AUTHORIZATION_REQUIRED_CODE,
            S.OUTCOME_SIGN_IN.format(provider=name, waiting=waiting),
            S.OUTCOME_ACTION_SIGN_IN.format(key=S.GOOGLE_BOOKS_API_KEY),
        ),
        (
            S.PROVIDER_COOLDOWN,
            S.OUTCOME_EARLIER_PAUSE.format(provider=name, waiting=waiting),
            S.OUTCOME_ACTION_GENERIC,
        ),
    )
    for code, cause, action in cases:
        metadata = MetadataReceipt(
            provider=Source.GOOGLE_BOOKS,
            state=SyncState.PARTIAL,
            deferred=C.THREE,
            issues=(Issue(code=code, message=S.TEST_REPORTING_MESSAGE_ONE),),
        )
        outcome = explain_outcome(
            sync_receipt(metadata=(metadata,)), exit_code=C.THREE, now=local_clock()
        )
        assert S.OUTCOME_CAUSE_LINE.format(text=cause) in outcome.lines
        assert S.OUTCOME_NEXT_LINE.format(action=action) in outcome.lines


def test_causes_are_bounded_and_the_remainder_is_counted() -> None:
    failed = SourceReceipt(source=Source.GOODREADS, collection=S.READ, state=SyncState.FAILED)
    verification = Verification(
        result=VerificationResult.FAILED,
        checks=(
            Check(
                name=CheckName.ROW_COUNTS,
                result=VerificationResult.FAILED,
                source=Source.GOODREADS,
                detail=S.TEST_REPORTING_MESSAGE_ONE,
            ),
        ),
    )
    receipt = sync_receipt(
        state=SyncState.PARTIAL,
        sources=(*complete_sources(), failed),
        metadata=paused_metadata(),
        verification=verification,
    )
    outcome = explain_outcome(
        receipt,
        exit_code=C.THREE,
        now=local_clock(),
        gates=(google_gate(),),
        log_error=S.TEST_OPLOG_DISK_FULL,
    )
    causes = _causes(outcome.lines)
    assert outcome.state == S.PARTIAL
    assert len(causes) == C.OUTCOME_MAX_CAUSES + C.ONE
    assert causes[C.ZERO] == S.OUTCOME_CAUSE_LINE.format(
        text=S.OUTCOME_SOURCES.format(
            count=C.ONE,
            total=C.FOUR,
            names=S.OUTCOME_SOURCE_NAME.format(
                source=S.LOG3_SOURCE_GOODREADS,
                collection=S.LOG3_COLLECTION_READ,
                state=S.FAILED,
            ),
        )
    )
    assert (
        S.OUTCOME_CAUSE_LINE.format(
            text=S.OUTCOME_LOG_INCOMPLETE.format(reason=S.TEST_OPLOG_DISK_FULL)
        )
        in causes
    )
    assert causes[-C.ONE] == S.OUTCOME_MORE.format(count=C.ONE)


def test_expired_gates_are_not_reported_as_active() -> None:
    outcome = explain_outcome(
        sync_receipt(metadata=paused_metadata()),
        exit_code=C.THREE,
        now=local_clock().replace(year=local_clock().year + C.ONE),
        gates=(google_gate(),),
    )
    assert outcome.gates == ()
    assert not any(S.TEST_OPLOG_PAUSED_WORDS in line for line in outcome.lines)
    assert (
        S.OUTCOME_CAUSE_LINE.format(
            text=S.OUTCOME_EARLIER_PAUSE.format(
                provider=S.OUTCOME_GOOGLE_BOOKS,
                waiting=S.OUTCOME_BOOKS.format(count=C.TEST_OPLOG_DEFERRED),
            )
        )
        in outcome.lines
    )


def test_failure_and_interrupt_outcomes_name_the_cause_and_a_distinct_next_action() -> None:
    failed = explain_failure(
        state=S.FAILED,
        exit_code=C.ONE,
        detail=S.TEST_REPORTING_FAILURE,
        duration_seconds=C.TEST_OPLOG_DURATION,
        log_error=S.TEST_OPLOG_DISK_FULL,
    )
    assert failed.lines == (
        S.OUTCOME_HEADLINE.format(
            state=S.FAILED.upper(), exit_code=C.ONE, duration=S.TEST_OPLOG_SECONDS_TEXT
        ),
        S.OUTCOME_CAUSE_LINE.format(text=S.TEST_REPORTING_FAILURE),
        S.OUTCOME_CAUSE_LINE.format(
            text=S.OUTCOME_LOG_INCOMPLETE.format(reason=S.TEST_OPLOG_DISK_FULL)
        ),
        S.OUTCOME_NEXT_LINE.format(action=S.OUTCOME_ACTION_FAILED),
    )
    interrupted = explain_failure(
        state=S.INTERRUPTED, exit_code=C.CLI_MAIN, detail=S.OPLOG_INTERRUPTED
    )
    assert interrupted.lines[-C.ONE] == S.OUTCOME_NEXT_LINE.format(
        action=S.OUTCOME_ACTION_INTERRUPTED
    )


def test_durations_instants_and_cooldown_epochs_are_human_readable() -> None:
    for seconds, text in C.TEST_OPLOG_DURATION_CASES:
        assert format_duration(seconds) == text
    zone = local_clock().tzinfo
    assert format_instant(C.TEST_OPLOG_GATE_EPOCH, zone) == S.TEST_OPLOG_GATE_INSTANT
    assert (
        readable_deadlines(S.DR_COOLDOWN_MESSAGE.format(deadline=C.TEST_OPLOG_GATE_EPOCH), zone)
        == S.TEST_OPLOG_DEFERRED_TEXT
    )
    assert readable_deadlines(S.TEST_REPORTING_MESSAGE_ONE) == S.TEST_REPORTING_MESSAGE_ONE
    moment = datetime.fromisoformat(S.TEST_REPORTING_OFFSET_TIME)
    assert parse_utc(utc_text(moment)) == moment.astimezone(UTC)
    assert parse_utc(S.TEST_OPLOG_NOT_JSON) is C.NONE


def test_probe_counts_this_run_only_and_keeps_unreadable_state_unknown() -> None:
    probe = RunProbe()
    assert probe.network_requests() == () and probe.gates() == ()
    store = RetryStore()
    google = (Source.GOOGLE_BOOKS, C.OUTCOME_PROVIDER_HOSTS[Source.GOOGLE_BOOKS])
    library = (Source.OPEN_LIBRARY, C.OUTCOME_PROVIDER_HOSTS[Source.OPEN_LIBRARY])
    store.states[google] = HttpRetryState(wire_attempts=C.TEST_OPLOG_WIRE_BEFORE)
    store.states[library] = BookyError(S.TEST_OPLOG_DISK_FULL)
    probe.attach(store)
    probe.begin()
    store.states[google] = HttpRetryState(
        retry_at=C.TEST_OPLOG_GATE_EPOCH,
        status_code=C.TEST_OPLOG_HTTP_STATUS,
        wire_attempts=C.TEST_OPLOG_WIRE_AFTER,
    )
    assert probe.network_requests() == (
        (S.GOOGLE_BOOKS, C.TEST_OPLOG_WIRE_AFTER - C.TEST_OPLOG_WIRE_BEFORE),
        (S.WIKIDATA, C.ZERO),
    )
    assert probe.gates() == (google_gate(),)
    store.states.clear()
    fresh = RunProbe()
    fresh.attach(store)
    fresh.begin()
    assert fresh.network_requests() == (
        (S.GOOGLE_BOOKS, C.ZERO),
        (S.OPEN_LIBRARY, C.ZERO),
        (S.WIKIDATA, C.ZERO),
    )
    assert fresh.gates() == ()


def test_daily_limit_explanation_requires_saved_structured_google_evidence() -> None:
    store = RetryStore()
    google = (Source.GOOGLE_BOOKS, C.OUTCOME_PROVIDER_HOSTS[Source.GOOGLE_BOOKS])
    probe = RunProbe()
    probe.attach(store)
    store.states[google] = HttpRetryState(
        retry_at=C.TEST_OPLOG_GATE_EPOCH,
        status_code=C.TEST_OPLOG_HTTP_STATUS,
        quota=C.L1_DAILY_FIXTURE_EVIDENCE,
    )
    gates = probe.gates()
    assert gates[C.ZERO].daily_limit is C.TRUE
    outcome = explain_outcome(
        sync_receipt(metadata=paused_metadata()),
        exit_code=C.THREE,
        now=local_clock(),
        gates=gates,
    )
    assert S.LOG3_DAILY_LIMIT in S.NEWLINE.join(outcome.lines)
    store.states[google] = HttpRetryState(
        retry_at=C.TEST_OPLOG_GATE_EPOCH,
        status_code=C.TEST_OPLOG_HTTP_STATUS,
    )
    assert probe.gates()[C.ZERO].daily_limit is C.FALSE
    generic = explain_outcome(
        sync_receipt(metadata=paused_metadata()),
        exit_code=C.THREE,
        now=local_clock(),
        gates=probe.gates(),
    )
    assert S.LOG3_DAILY_LIMIT not in S.NEWLINE.join(generic.lines)


def test_report_ready_is_distinct_from_partial_book_details_and_reviewed_count() -> None:
    metadata = MetadataReceipt(
        provider=Source.OPEN_LIBRARY,
        state=SyncState.PARTIAL,
        requested=C.THREE,
        attempted=C.THREE,
        processed=C.ONE,
        deferred=C.ZERO,
    )
    products = ProductReceipt(
        state=SyncState.COMPLETE,
        analytics_report_id=C.ONE,
        pdf_file=S.PROD_PDF_FILE,
    )
    receipt = sync_receipt(state=SyncState.PARTIAL, metadata=(metadata,)).model_copy(
        update={S.PROD_PRODUCTS: products}
    )
    outcome = explain_outcome(receipt, exit_code=C.THREE, now=local_clock())
    assert outcome.state == S.PARTIAL
    assert outcome.lines[C.ONE] == S.LOG3_REPORT_READY.format(
        filename=S.PROD_PDF_FILE, report_id=C.ONE, scope=S.LOG3_REPORT_PARTIAL
    )
    assert (
        S.LOG3_ATTEMPTED.format(
            provider=S.OUTCOME_OPEN_LIBRARY, attempted=C.THREE, incomplete=C.TWO
        )
        in outcome.lines
    )
    assert (
        S.OUTCOME_CAUSE_LINE.format(
            text=S.LOG3_PROVIDER_INCOMPLETE.format(provider=S.OUTCOME_OPEN_LIBRARY)
        )
        in outcome.lines
    )
    assert S.OUTCOME_COMPLETE.format(finished=C.THREE, total=C.THREE) not in outcome.lines
    legacy = MetadataReceipt.model_validate(
        {
            S.PROVIDER: Source.OPEN_LIBRARY,
            S.STATE: SyncState.PARTIAL,
            S.LOG3_PROCESSED_KEY: C.ONE,
        }
    )
    assert legacy.attempted is C.NONE
