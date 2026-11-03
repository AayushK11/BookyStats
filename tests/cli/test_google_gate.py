from __future__ import annotations

import sqlite3
import time
from contextlib import ExitStack
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters import google_oauth
from bookystats.adapters.http import HttpClient, cooldown_message
from bookystats.cli import commands as cli
from bookystats.domain.errors import ConnectorError, ProviderDeferredError
from bookystats.domain.interfaces import HttpRetryState
from bookystats.domain.models import BookRecord, Issue, Source
from bookystats.persistence.cache import MetadataCache
from bookystats.runtime.config import MetadataSettings, Settings
from bookystats.runtime.layout import database_path
from tests.support.sources import accounts


def _book() -> BookRecord:
    return BookRecord(
        source=Source.STORYGRAPH,
        source_id=S.ORIGINAL_READER_BOOK_ID,
        title=S.MATILDA,
        authors=(S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
        isbns=(S.TEST_GOOGLE_BOOKS_BOOK_ISBNS_TEXT,),
        url=S.TEST_GOOGLE_BOOKS_BOOK_URL_THESTORYGRAPH_COM_BOOKS_ORIGINAL_READER,
    )


def _seed_gate(directory: Path, offset: int) -> HttpRetryState:
    state = HttpRetryState(
        retry_at=time.time() + offset,
        status_code=C.L1_TEST_GATE_STATUS,
        error_code=S.DR_HTTP_RETRYABLE,
        failures=C.ONE,
        wire_attempts=C.ONE,
        quota=dict(C.L1_DETAILED_EVIDENCE),
    )
    cache = MetadataCache(database_path(directory, S.METADATA_SQLITE3))
    try:
        cache.save_retry_state(Source.GOOGLE_BOOKS, S.WWW_GOOGLEAPIS_COM, state)
    finally:
        cache.close()
    return state


def _unexpected(*args: object, **kwargs: object) -> None:
    pytest.fail(S.CLI_TEST_UNEXPECTED_NETWORK)


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(S.GOOGLE_BOOKS_API_KEY, raising=C.FALSE)
    monkeypatch.setattr(google_oauth, S.CLI_TEST_ENSURE_TOKEN, _unexpected)
    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, _unexpected)


@pytest.mark.usefixtures(S.L1_FIXTURE_OFFLINE)
@pytest.mark.parametrize(S.CLI_TEST_INTERACTIVE_PARAMETER, C.CLI_TEST_INTERACTIVITY)
def test_persisted_gate_skips_eager_google_authorization_and_still_defers_lookups(
    tmp_path: Path, interactive: bool
) -> None:
    gate = _seed_gate(tmp_path, C.L1_TEST_GATE_SECONDS)
    settings = Settings(
        accounts=accounts(),
        metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
    )
    with ExitStack() as stack:
        service = cli._build_service(tmp_path, settings, stack, interactive=interactive, inputs={})
        assert not service.provider_issues
        with pytest.raises(ProviderDeferredError) as deferred:
            service.providers[Source.GOOGLE_BOOKS].lookup(_book())
    assert str(deferred.value) == cooldown_message(gate)
    assert S.L1_TEST_DETAILED_LIMIT in str(deferred.value)


@pytest.mark.usefixtures(S.L1_FIXTURE_OFFLINE)
@pytest.mark.parametrize(S.CLI_TEST_INTERACTIVE_PARAMETER, C.CLI_TEST_INTERACTIVITY)
def test_persisted_gate_skips_deferred_google_authorization_when_targets_need_it(
    tmp_path: Path, interactive: bool
) -> None:
    gate = _seed_gate(tmp_path, C.L1_TEST_GATE_SECONDS)
    with ExitStack() as stack:
        service = cli._build_service(
            tmp_path, Settings(accounts=accounts()), stack, interactive=interactive, inputs={}
        )
        assert Source.GOOGLE_BOOKS not in service.providers
        provider = service.provider_factories[Source.GOOGLE_BOOKS]()
        assert not isinstance(provider, Issue)
        with pytest.raises(ProviderDeferredError) as deferred:
            provider.lookup(_book())
    assert str(deferred.value) == cooldown_message(gate)


@pytest.mark.parametrize(S.CLI_TEST_INTERACTIVE_PARAMETER, C.CLI_TEST_INTERACTIVITY)
def test_expired_gate_keeps_the_normal_authorization_and_request_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interactive: bool
) -> None:
    _seed_gate(tmp_path, -C.L1_TEST_GATE_SECONDS)
    authorizations: list[bool] = []
    requests: list[str] = []

    def authorize(directory: Path, *, interactive: bool) -> str:
        authorizations.append(interactive)
        return S.OAUTH_TEST_ACCESS_TOKEN

    def refuse(self: HttpClient, url: str, **kwargs: object) -> None:
        requests.append(url)
        raise ConnectorError(S.CLI_TEST_UNEXPECTED_NETWORK)

    monkeypatch.delenv(S.GOOGLE_BOOKS_API_KEY, raising=C.FALSE)
    monkeypatch.setattr(google_oauth, S.CLI_TEST_ENSURE_TOKEN, authorize)
    monkeypatch.setattr(HttpClient, S.CLI_TEST_FETCH, refuse)
    settings = Settings(
        accounts=accounts(),
        metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE),
    )
    with ExitStack() as stack:
        service = cli._build_service(tmp_path, settings, stack, interactive=interactive, inputs={})
        service.providers[Source.GOOGLE_BOOKS].lookup(_book())
    assert authorizations == [interactive]
    assert len(requests) == C.ONE


def test_gate_probe_creates_nothing_and_fails_open_on_unreadable_state(tmp_path: Path) -> None:
    assert cli._google_cooldown(tmp_path, C.NONE) is C.NONE
    assert not tuple(tmp_path.iterdir())
    gate = _seed_gate(tmp_path, C.L1_TEST_GATE_SECONDS)
    assert cli._google_cooldown(tmp_path, C.NONE) == gate
    connection = sqlite3.connect(database_path(tmp_path, S.METADATA_SQLITE3))
    try:
        with connection:
            connection.execute(S.L1_TEST_TAMPER_QUOTA)
    finally:
        connection.close()
    assert cli._google_cooldown(tmp_path, C.NONE) is C.NONE


def test_gate_probe_fails_open_on_a_file_that_is_not_a_database(tmp_path: Path) -> None:
    (tmp_path / S.METADATA_SQLITE3).write_bytes(C.L1_TEST_OVERLONG.encode())
    assert cli._google_cooldown(tmp_path, C.NONE) is C.NONE
