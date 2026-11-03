from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime, tzinfo

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.sync import MetadataReceipt, SyncReceipt
from bookystats.domain.errors import BookyError
from bookystats.domain.interfaces import HttpRetryState, RetryStateStore
from bookystats.domain.models import Source, SyncState, VerificationResult


@C.frozen_dataclass
class Gate:
    provider: Source
    retry_at: float
    status_code: int | None = C.NONE
    error_code: str | None = C.NONE


@C.frozen_dataclass
class Outcome:
    state: str
    exit_code: int
    lines: tuple[str, ...]
    duration_seconds: float = C.ZERO
    gates: tuple[Gate, ...] = ()
    network_requests: tuple[tuple[str, int], ...] = ()


@C.frozen_dataclass
class _Cause:
    text: str
    action: str | None = C.NONE


def format_duration(seconds: float) -> str:
    seconds = seconds if math.isfinite(seconds) and seconds >= C.ZERO else C.ZERO
    if round(seconds, C.ONE) < C.OUTCOME_SIXTY:
        return S.OUTCOME_DURATION_SECONDS.format(seconds=seconds)
    minutes, rest = divmod(round(seconds), C.OUTCOME_SIXTY)
    if minutes < C.OUTCOME_SIXTY:
        return S.OUTCOME_DURATION_MINUTES.format(minutes=minutes, seconds=rest)
    hours, minutes = divmod(minutes, C.OUTCOME_SIXTY)
    return S.OUTCOME_DURATION_HOURS.format(hours=hours, minutes=minutes, seconds=rest)


def format_instant(epoch: float, zone: tzinfo | None = C.NONE) -> str:
    # Local time with its offset, followed by UTC; zone=None means the system zone.
    try:
        universal = datetime.fromtimestamp(epoch, UTC)
        local = universal.astimezone(zone)
    except (OverflowError, OSError, ValueError):
        return S.OUTCOME_TIME_UNKNOWN
    return S.OUTCOME_INSTANT.format(
        local=local.isoformat(sep=S.SPACE, timespec=S.OUTCOME_SECONDS),
        utc=universal.strftime(S.OUTCOME_UTC_FORMAT),
    )


def readable_deadlines(text: str, zone: tzinfo | None = C.NONE) -> str:
    # Provider cooldown messages carry a raw epoch; show it as a dated local time plus UTC.
    return C.OUTCOME_EPOCH_PATTERN.sub(
        lambda match: format_instant(float(match[C.ONE]), zone), text
    )


def utc_text(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(S.RUNSUM_TIME_FORMAT)


def parse_utc(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, S.RUNSUM_TIME_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return C.NONE


def _provider_name(provider: Source) -> str:
    return C.OUTCOME_PROVIDER_NAMES.get(provider, provider.value)


def _books(count: int) -> str:
    return (S.OUTCOME_BOOK_ONE if count == C.ONE else S.OUTCOME_BOOKS).format(count=count)


def _network_text(counts: dict[str, int], provider: Source) -> str:
    count = counts.get(provider.value)
    if count is C.NONE:
        return S.OUTCOME_NETWORK_UNKNOWN
    return (S.OUTCOME_NETWORK_ONE if count == C.ONE else S.OUTCOME_NETWORK).format(count=count)


def _paused(gate: Gate, waiting: int, zone: tzinfo) -> str:
    if gate.status_code is not C.NONE:
        reason = S.OUTCOME_AFTER_HTTP.format(status=gate.status_code)
    elif gate.error_code == S.DR_REQUEST_PENDING:
        reason = S.OUTCOME_AFTER_PENDING
    else:
        reason = S.EMPTY
    return S.OUTCOME_PAUSED.format(
        provider=_provider_name(gate.provider),
        until=format_instant(gate.retry_at, zone),
        reason=reason,
        waiting=S.OUTCOME_WAITING.format(waiting=_books(waiting)) if waiting else S.EMPTY,
    )


def _provider_cause(metadata: MetadataReceipt) -> _Cause | None:
    if metadata.state == SyncState.COMPLETE:
        return C.NONE
    codes = {issue.code for issue in metadata.issues}
    name = _provider_name(metadata.provider)
    waiting = _books(metadata.deferred)
    if S.REQUEST_BUDGET_EXHAUSTED in codes:
        return _Cause(
            S.OUTCOME_BUDGET.format(provider=name, waiting=waiting), S.OUTCOME_ACTION_BUDGET
        )
    if S.OAUTH_AUTHORIZATION_REQUIRED_CODE in codes:
        return _Cause(
            S.OUTCOME_SIGN_IN.format(provider=name, waiting=waiting),
            S.OUTCOME_ACTION_SIGN_IN.format(key=S.GOOGLE_BOOKS_API_KEY),
        )
    if S.OAUTH_ISSUE_CODE in codes:
        return _Cause(S.OUTCOME_ACCESS_FAILED.format(provider=name), S.OUTCOME_ACTION_GENERIC)
    if S.METADATA_CACHE_ERROR in codes:
        return _Cause(S.OUTCOME_CACHE_ERROR.format(provider=name), S.OUTCOME_ACTION_GENERIC)
    if S.PROVIDER_COOLDOWN in codes:
        return _Cause(
            S.OUTCOME_EARLIER_PAUSE.format(provider=name, waiting=waiting),
            S.OUTCOME_ACTION_GENERIC,
        )
    if metadata.deferred:
        return _Cause(
            S.OUTCOME_DEFERRED.format(provider=name, waiting=waiting), S.OUTCOME_ACTION_GENERIC
        )
    if S.QUEUE_NO_LOOKUPS_DUE_CODE in codes:
        return _Cause(S.OUTCOME_PARKED.format(provider=name))
    return _Cause(
        S.OUTCOME_PROVIDER_STATE.format(provider=name, state=metadata.state.value),
        S.OUTCOME_ACTION_GENERIC,
    )


def _source_causes(receipt: SyncReceipt) -> list[_Cause]:
    unfinished = [source for source in receipt.sources if source.state != SyncState.COMPLETE]
    if not unfinished:
        return []
    names = S.COMMA_SPACE.join(
        S.OUTCOME_SOURCE_NAME.format(
            source=source.source.value, collection=source.collection, state=source.state.value
        )
        for source in unfinished[: C.OUTCOME_MAX_NAMES]
    )
    return [
        _Cause(
            S.OUTCOME_SOURCES.format(
                count=len(unfinished), total=len(receipt.sources), names=names
            ),
            S.OUTCOME_ACTION_SOURCES,
        )
    ]


def _verification_causes(receipt: SyncReceipt) -> list[_Cause]:
    verification = receipt.verification
    if verification is C.NONE or verification.result == VerificationResult.SUCCESS:
        return []
    failed = [check for check in verification.checks if check.result != VerificationResult.SUCCESS]
    if not failed:
        text = S.OUTCOME_VERIFICATION_SHORT.format(result=verification.result.value)
    else:
        text = S.OUTCOME_VERIFICATION.format(
            result=verification.result.value,
            failed=len(failed),
            total=len(verification.checks),
            names=S.COMMA_SPACE.join(str(check.name) for check in failed[: C.OUTCOME_MAX_NAMES]),
        )
    return [_Cause(text, S.OUTCOME_ACTION_VERIFICATION)]


def _stage_causes(receipt: SyncReceipt) -> list[_Cause]:
    causes: list[_Cause] = []
    for label, stage in (
        (S.OUTCOME_ANALYTICS, receipt.analytics),
        (S.OUTCOME_REPORTS, receipt.products),
    ):
        if stage is not C.NONE and stage.state != SyncState.COMPLETE:
            causes.append(
                _Cause(
                    S.OUTCOME_STAGE.format(stage=label, state=stage.state.value),
                    S.OUTCOME_ACTION_STAGE,
                )
            )
    return causes


def explain_outcome(
    receipt: SyncReceipt,
    *,
    exit_code: int,
    now: datetime,
    gates: Iterable[Gate] = (),
    network_requests: Iterable[tuple[str, int]] = (),
    duration_seconds: float = C.ZERO,
    log_error: str | None = C.NONE,
) -> Outcome:
    zone = now.tzinfo or UTC
    moment = now.timestamp()
    active = tuple(
        sorted(
            (gate for gate in gates if gate.retry_at > moment),
            key=lambda gate: gate.provider.value,
        )
    )
    measured = tuple(network_requests)
    counts = dict(measured)
    unfinished_providers = {
        item.provider for item in receipt.metadata if item.state != SyncState.COMPLETE
    }
    pauses = [gate for gate in active if gate.provider in unfinished_providers]
    paused = {gate.provider for gate in pauses}
    waiting = {item.provider: item.deferred for item in receipt.metadata}
    pause_action = S.OUTCOME_ACTION_PAUSED.format(
        until=format_instant(max((gate.retry_at for gate in pauses), default=C.ZERO), zone)
    )
    causes = _source_causes(receipt)
    causes.extend(
        _Cause(_paused(gate, waiting.get(gate.provider, C.ZERO), zone), pause_action)
        for gate in pauses
    )
    parked: list[_Cause] = []
    for item in receipt.metadata:
        cause = _provider_cause(item) if item.provider not in paused else C.NONE
        if cause is not C.NONE:
            (causes if cause.action is not C.NONE else parked).append(cause)
    causes.extend(_verification_causes(receipt))
    causes.extend(_stage_causes(receipt))
    if log_error is not C.NONE:
        causes.append(
            _Cause(S.OUTCOME_LOG_INCOMPLETE.format(reason=log_error), S.OUTCOME_ACTION_LOG)
        )
    causes.extend(parked)
    if exit_code == C.ZERO:
        state = S.COMPLETE
    elif receipt.state != SyncState.COMPLETE:
        state = receipt.state.value
    else:
        state = S.OUTCOME_NEEDS_ATTENTION
    header = S.OUTCOME_HEADLINE.format(
        state=state.upper(), exit_code=exit_code, duration=format_duration(duration_seconds)
    )
    lookups = tuple(
        S.OUTCOME_LOOKUPS.format(
            provider=_provider_name(item.provider),
            state=item.state.value,
            processed=item.processed,
            requested=item.requested,
            deferred=item.deferred,
            hits=item.cache_hits,
            network=_network_text(counts, item.provider),
        )
        for item in receipt.metadata
    )
    if exit_code == C.ZERO and not causes:
        finished = sum(source.state == SyncState.COMPLETE for source in receipt.sources)
        lines = (
            header,
            S.OUTCOME_COMPLETE.format(finished=finished, total=len(receipt.sources)),
            *lookups,
        )
    else:
        if not causes:
            causes.append(_Cause(S.OUTCOME_UNSPECIFIED, S.OUTCOME_ACTION_GENERIC))
        shown = causes[: C.OUTCOME_MAX_CAUSES]
        hidden = len(causes) - len(shown)
        action = next(
            (cause.action for cause in causes if cause.action is not C.NONE),
            S.OUTCOME_ACTION_NOTHING,
        )
        lines = (
            header,
            *(S.OUTCOME_CAUSE_LINE.format(text=cause.text) for cause in shown),
            *((S.OUTCOME_MORE.format(count=hidden),) if hidden else ()),
            *lookups,
            S.OUTCOME_NEXT_LINE.format(action=action),
        )
    return Outcome(
        state=state,
        exit_code=exit_code,
        lines=lines,
        duration_seconds=duration_seconds,
        gates=active,
        network_requests=measured,
    )


def explain_failure(
    *,
    state: str,
    exit_code: int,
    detail: str,
    duration_seconds: float = C.ZERO,
    log_error: str | None = C.NONE,
) -> Outcome:
    action = S.OUTCOME_ACTION_INTERRUPTED if state == S.INTERRUPTED else S.OUTCOME_ACTION_FAILED
    causes = [detail]
    if log_error is not C.NONE:
        causes.append(S.OUTCOME_LOG_INCOMPLETE.format(reason=log_error))
    return Outcome(
        state=state,
        exit_code=exit_code,
        lines=(
            S.OUTCOME_HEADLINE.format(
                state=state.upper(), exit_code=exit_code, duration=format_duration(duration_seconds)
            ),
            *(S.OUTCOME_CAUSE_LINE.format(text=text) for text in causes),
            S.OUTCOME_NEXT_LINE.format(action=action),
        ),
        duration_seconds=duration_seconds,
    )


class RunProbe:
    # Reads saved provider retry gates and cumulative wire-attempt counters from the cache.
    def __init__(self) -> None:
        self._store: RetryStateStore | None = C.NONE
        self._baseline: dict[Source, int] = {}

    def attach(self, store: RetryStateStore) -> None:
        self._store = store

    def _read(self, provider: Source) -> tuple[bool, HttpRetryState | None]:
        # (False, None) means the saved state is unreadable: unknown, never zero.
        if self._store is C.NONE:
            return C.FALSE, C.NONE
        try:
            return C.TRUE, self._store.get_retry_state(provider, C.OUTCOME_PROVIDER_HOSTS[provider])
        except BookyError:
            return C.FALSE, C.NONE

    def begin(self) -> None:
        self._baseline = {}
        for provider in C.OUTCOME_PROVIDER_HOSTS:
            known, state = self._read(provider)
            if known:
                self._baseline[provider] = state.wire_attempts if state is not C.NONE else C.ZERO

    def network_requests(self) -> tuple[tuple[str, int], ...]:
        counts: list[tuple[str, int]] = []
        for provider in C.OUTCOME_PROVIDER_HOSTS:
            known, state = self._read(provider)
            if known and provider in self._baseline:
                current = state.wire_attempts if state is not C.NONE else C.ZERO
                counts.append((provider.value, max(C.ZERO, current - self._baseline[provider])))
        return tuple(counts)

    def gates(self) -> tuple[Gate, ...]:
        found: list[Gate] = []
        for provider in C.OUTCOME_PROVIDER_HOSTS:
            _, state = self._read(provider)
            if state is not C.NONE and state.retry_at is not C.NONE:
                found.append(Gate(provider, state.retry_at, state.status_code, state.error_code))
        return tuple(found)
