from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.config import (
    Settings,
    WeeklySettings,
    account_from_url,
    browser_profile,
    default_accounts,
    load_settings,
    save_settings,
)
from bookystats.errors import ConfigurationError
from bookystats.models import Source


def test_settings_round_trip_without_credentials(tmp_path: Path) -> None:
    account = account_from_url(
        Source.GOODREADS, S.TEST_CONFIG_SETTINGS_ROUND_TRIP_GOODREADS_COM_USER_SHOW_READER
    )
    settings = Settings(accounts=(account,))
    save_settings(tmp_path, settings)
    loaded = load_settings(tmp_path)
    assert loaded == settings
    assert not loaded.weekly.enabled
    payload = json.loads((tmp_path / S.CONFIG_JSON).read_text())
    assert S.API_KEY not in payload
    assert browser_profile(tmp_path, account).parent.name == S.GOODREADS


@pytest.mark.parametrize(
    S.URL,
    [
        S.TEST_CONFIG_INVALID_PROFILE_REJECTS_WWW_GOODREADS_COM_AUTHOR_SHOW,
        S.TEST_CONFIG_INVALID_PROFILE_REJECTS_GOODREADS_COM_EVIL_EXAMPLE_USER,
        S.TEST_CONFIG_INVALID_PROFILE_REJECTS_WWW_GOODREADS_COM_USER_SHOW,
        S.TEST_CONFIG_INVALID_PROFILE_REJECTS_GOODREADS_COM_USER_SHOW_KEY,
    ],
)
def test_invalid_profile_rejects_without_echoing_secret(url: str) -> None:
    with pytest.raises(ConfigurationError) as error:
        account_from_url(Source.GOODREADS, url)
    assert S.PRIVATE not in str(error.value)


def test_invalid_config_does_not_echo_input(tmp_path: Path) -> None:
    (tmp_path / S.CONFIG_JSON).write_text(
        S.TEST_CONFIG_INVALID_CONFIG_DOES_NOT_ECHO_INPUT_UNKNOWN_PRIVATE
    )
    with pytest.raises(ConfigurationError) as error:
        load_settings(tmp_path)
    assert S.PRIVATE not in str(error.value)


def test_built_in_profiles_apply_until_overridden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    assert load_settings(tmp_path).accounts == default_accounts()
    assert {account.account_id for account in default_accounts()} == {
        S.DEFAULT_STORYGRAPH_ACCOUNT,
        S.DEFAULT_GOODREADS_ACCOUNT,
    }
    monkeypatch.setenv(
        S.BOOKYSTATS_GOODREADS_PROFILE,
        S.TEST_CONFIG_SETTINGS_ROUND_TRIP_GOODREADS_COM_USER_SHOW_READER,
    )
    overridden = {account.source: account for account in load_settings(tmp_path).accounts}
    assert overridden[Source.GOODREADS].account_id != S.DEFAULT_GOODREADS_ACCOUNT
    assert overridden[Source.STORYGRAPH].account_id == S.DEFAULT_STORYGRAPH_ACCOUNT
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE)
    save_settings(tmp_path, Settings(accounts=()))
    assert load_settings(tmp_path).accounts == ()


def test_weekly_schedule_requires_explicit_time() -> None:
    with pytest.raises(ValidationError):
        WeeklySettings(enabled=C.TRUE)
    with pytest.raises(ValidationError):
        WeeklySettings(
            enabled=C.TRUE,
            weekday=S.MON,
            time=S.TEST_CONFIG_WEEKLY_SCHEDULE_REQUIRES_EXPLICIT_TIME_TIME_TEXT,
            timezone=S.UTC,
        )
