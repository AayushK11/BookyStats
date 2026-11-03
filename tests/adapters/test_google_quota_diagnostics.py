from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.http import (
    HttpClient,
    active_cooldown,
    cooldown_message,
    google_quota_evidence,
)
from bookystats.domain.errors import ProviderDeferredError
from bookystats.domain.interfaces import HttpRetryState
from bookystats.domain.models import Source
from bookystats.persistence.cache import MetadataCache, MetadataCacheError
from tests.support.paths import fixture_path


def _fixture(name: str) -> bytes:
    return fixture_path(S.METADATA, name).read_bytes()


def _execute(path: Path, statement: str) -> list[tuple[str]]:
    connection = sqlite3.connect(path)
    try:
        with connection:
            return connection.execute(statement).fetchall()
    finally:
        connection.close()


def _fetcher(cache: MetadataCache, client: httpx.Client, now: list[float]) -> HttpClient:
    return HttpClient(
        allowed_hosts=(S.WWW_GOOGLEAPIS_COM,),
        client=client,
        min_interval=C.ZERO,
        max_attempts=C.ONE,
        retry_store=cache,
        provider=Source.GOOGLE_BOOKS,
        wall_clock=lambda: now[C.ZERO],
    )


@pytest.mark.parametrize(S.L1_QUOTA_PARAMETERS, C.L1_QUOTA_CASES)
def test_structured_google_quota_is_validated_persisted_and_explains_the_gate(
    tmp_path: Path,
    fixture_name: str,
    status: int,
    expected: Mapping[str, str],
    delay: int,
    note: str,
) -> None:
    body = _fixture(fixture_name)
    now = [C.DR_TEST_NOW]
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(status, content=body))
        ) as client:
            fetcher = _fetcher(cache, client, now)
            url = S.GOOGLE_BOOKS_ENDPOINT_HTTPS_WWW_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES
            assert fetcher.fetch(url).retry_at == C.DR_TEST_NOW + delay
            state = cache.get_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM)
            assert state is not C.NONE
            assert dict(state.quota) == expected
            with pytest.raises(ProviderDeferredError) as deferred:
                fetcher.fetch(url)
            assert fetcher.requests == C.ONE
        assert str(deferred.value) == cooldown_message(state)
        assert S.DR_COOLDOWN_MESSAGE.format(deadline=state.retry_at) in str(deferred.value)
        assert note in str(deferred.value)
    finally:
        cache.close()
    stored = S.L1_EMPTY_BYTES.join(item.read_bytes() for item in tmp_path.glob(S.L1_GLOB_ALL))
    assert S.L1_TEST_PROJECT_NUMBER not in stored


@pytest.mark.parametrize(S.L1_QUOTA_SCOPE_PARAMETERS, C.L1_QUOTA_SCOPE_CASES)
def test_quota_evidence_needs_google_books_its_own_host_and_a_quota_status(
    tmp_path: Path, fixture_name: str, status: int, provider: Source, host: str, url: str
) -> None:
    body = _fixture(fixture_name)
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(status, content=body))
        ) as client:
            HttpClient(
                allowed_hosts=(host,),
                client=client,
                min_interval=C.ZERO,
                max_attempts=C.ONE,
                retry_store=cache,
                provider=provider,
                wall_clock=lambda: C.DR_TEST_NOW,
            ).fetch(url)
        state = cache.get_retry_state(provider, host)
        assert state is not C.NONE
        assert not state.quota
    finally:
        cache.close()


def test_later_success_from_a_fresh_client_clears_quota_evidence_and_the_gate(
    tmp_path: Path,
) -> None:
    now = [C.DR_TEST_NOW]
    url = S.GOOGLE_BOOKS_ENDPOINT_HTTPS_WWW_GOOGLEAPIS_COM_BOOKS_V1_VOLUMES
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        quota = _fixture(S.L1_GOOGLE_DETAILED_FIXTURE)
        with httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(C.L1_TEST_GATE_STATUS, content=quota)
            )
        ) as client:
            _fetcher(cache, client, now).fetch(url)
        gated = cache.get_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM)
        assert gated is not C.NONE
        assert gated.quota
        now[C.ZERO] += C.QUEUE_GOOGLE_DAILY_COOLDOWN_SECONDS + C.ONE
        with httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(C.HTTP_OK, content=S.L1_BODY_SUCCESS)
            )
        ) as client:
            assert _fetcher(cache, client, now).fetch(url).status_code == C.HTTP_OK
        recovered = cache.get_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM)
        assert recovered is not C.NONE
        assert not recovered.quota
        assert recovered.retry_at is C.NONE
        assert recovered.error_code is C.NONE
    finally:
        cache.close()


def test_quota_in_the_retry_state_round_trips_and_invalid_values_are_never_written(
    tmp_path: Path,
) -> None:
    path = tmp_path / S.CATALOG_SQLITE
    cache = MetadataCache(path)
    try:
        legacy = HttpRetryState(
            retry_at=float(C.L1_TEST_GATE_SECONDS), error_code=S.DR_HTTP_RETRYABLE
        )
        cache.save_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM, legacy)
        ((payload,),) = _execute(path, S.L1_SELECT_RETRY_PAYLOADS)
        assert set(json.loads(payload)) == C.DR_RETRY_KEYS
        assert cache.get_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM) == legacy
        saved = replace(legacy, quota=dict(C.L1_DETAILED_EVIDENCE))
        cache.save_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM, saved)
        assert cache.get_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM) == saved
        for invalid in C.L1_BAD_QUOTAS:
            with pytest.raises(MetadataCacheError, match=S.DR_RETRY_WRITE_ERROR):
                cache.save_retry_state(
                    Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM, replace(legacy, quota=dict(invalid))
                )
        assert cache.get_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM) == saved
        _execute(path, S.L1_TEST_TAMPER_QUOTA)
        with pytest.raises(MetadataCacheError, match=S.DR_RETRY_READ_ERROR):
            cache.get_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM)
    finally:
        cache.close()


@pytest.mark.parametrize(S.L1_BODY_PARAMETER, C.L1_NON_QUOTA_BODIES)
def test_malformed_or_unrelated_error_bodies_yield_no_quota_evidence(body: bytes) -> None:
    assert google_quota_evidence(body) == {}


def test_daily_evidence_wins_over_other_scopes_and_error_info_over_the_legacy_reason() -> None:
    payload = json.loads(_fixture(S.L1_GOOGLE_DETAILED_FIXTURE))
    minute = json.loads(_fixture(S.QUEUE_GOOGLE_UNKNOWN_QUOTA_FIXTURE))[S.ERROR][
        S.QUEUE_GOOGLE_ERROR_DETAILS
    ][C.ZERO]
    payload[S.ERROR][S.QUEUE_GOOGLE_ERROR_DETAILS].insert(C.ZERO, minute)
    payload[S.ERROR][S.ERRORS] = [{S.REASON: S.DAILYLIMITEXCEEDED}]
    assert google_quota_evidence(json.dumps(payload).encode()) == C.L1_DETAILED_EVIDENCE


def test_unrecognized_quota_units_are_not_classified() -> None:
    payload = json.loads(_fixture(S.QUEUE_GOOGLE_UNKNOWN_QUOTA_FIXTURE))
    payload[S.ERROR][S.QUEUE_GOOGLE_ERROR_DETAILS][C.ZERO][S.METADATA][
        S.QUEUE_GOOGLE_QUOTA_UNIT
    ] = S.L1_TEST_HOUR_UNIT
    assert google_quota_evidence(json.dumps(payload).encode()) == {}


def test_active_cooldown_reports_only_unexpired_gates(tmp_path: Path) -> None:
    cache = MetadataCache(tmp_path / S.CATALOG_SQLITE)
    try:
        assert active_cooldown(cache, Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM) is C.NONE
        cache.save_retry_state(
            Source.GOOGLE_BOOKS,
            S.WWW_GOOGLEAPIS_COM,
            HttpRetryState(retry_at=C.DR_TEST_NOW + C.ONE, error_code=S.DR_HTTP_RETRYABLE),
        )
        assert (
            active_cooldown(
                cache, Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM, wall_clock=lambda: C.DR_TEST_NOW
            )
            is not C.NONE
        )
        assert (
            active_cooldown(
                cache,
                Source.GOOGLE_BOOKS,
                S.WWW_GOOGLEAPIS_COM,
                wall_clock=lambda: C.DR_TEST_NOW + C.ONE,
            )
            is C.NONE
        )
    finally:
        cache.close()
