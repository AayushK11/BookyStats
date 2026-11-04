from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

import pytest
from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.errors import ConfigurationError
from bookystats.domain.models import Source
from bookystats.runtime import config
from bookystats.runtime.config import (
    FileSettings,
    MetadataSettings,
    RecommendationSettings,
    Settings,
    WeeklySettings,
    account_from_url,
    configuration_path,
    data_directory,
    load_settings,
    save_settings,
)
from tests.support.sources import accounts


def test_csv_paths_round_trip_and_resolve_relative_to_data_directory(tmp_path: Path) -> None:
    relative = Path(S.CLI_TEST_STORYGRAPH_NAME)
    absolute = tmp_path / S.TEST_BROWSER_EXPORT_READ_NAME
    files = FileSettings(storygraph_file=relative, goodreads_read_file=absolute)
    save_settings(tmp_path, Settings(files=files))
    loaded = load_settings(tmp_path)
    assert loaded.files == files
    paths = loaded.files.paths(tmp_path)
    assert paths[(Source.STORYGRAPH, S.LIBRARY)] == tmp_path / relative
    assert paths[(Source.GOODREADS, S.READ)] == absolute
    assert paths[(Source.GOODREADS, S.TO_READ)] is C.NONE


def test_windows_style_relative_csv_paths_work_on_every_platform(tmp_path: Path) -> None:
    files = FileSettings(
        storygraph_file=Path(str(PureWindowsPath(S.PROFILES) / S.CLI_TEST_STORYGRAPH_NAME))
    )
    assert files.paths(tmp_path)[(Source.STORYGRAPH, S.LIBRARY)] == (
        tmp_path / S.PROFILES / S.CLI_TEST_STORYGRAPH_NAME
    )


def test_configured_goodreads_whole_library_cannot_mix_with_split_csvs() -> None:
    with pytest.raises(ValidationError):
        FileSettings(
            goodreads_file=Path(S.CLI_TEST_GOODREADS_NAME),
            goodreads_read_file=Path(S.TEST_BROWSER_EXPORT_READ_NAME),
        )
    files = FileSettings(goodreads_file=Path(S.CLI_TEST_GOODREADS_NAME))
    assert (Source.GOODREADS, S.LIBRARY) in files.paths(Path.cwd())
    assert (Source.GOODREADS, S.READ) not in files.paths(Path.cwd())


def test_checkout_configuration_is_portable_without_leaking_into_other_data_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    checkout = tmp_path / S.TEST_REPORTING_CHECKOUT
    checkout.mkdir()
    shared = Settings(
        accounts=accounts(),
        files=FileSettings(storygraph_file=Path(S.CLI_TEST_STORYGRAPH_NAME)),
    )
    save_settings(checkout, shared)
    monkeypatch.setattr(config, S.TEST_REPORTING_CHECKOUT_ROOT, lambda: checkout)
    directory = checkout / S.CHECKOUT_DATA_FOLDER
    assert configuration_path(directory) == checkout / S.CONFIG_JSON
    assert load_settings(directory) == shared
    assert load_settings(directory).files.paths(directory)[(Source.STORYGRAPH, S.LIBRARY)] == (
        directory / S.CLI_TEST_STORYGRAPH_NAME
    )
    isolated = tmp_path / S.TEST_REPORTING_ENV_DIRECTORY
    assert not load_settings(isolated).accounts
    assert configuration_path(isolated) == isolated / S.CONFIG_JSON
    override = Settings(
        files=FileSettings(goodreads_file=Path(S.CLI_TEST_GOODREADS_NAME)),
        metadata=MetadataSettings(google_books=C.FALSE, open_library=C.FALSE),
    )
    save_settings(directory, override)
    assert configuration_path(directory) == directory / S.CONFIG_JSON
    assert load_settings(directory) == override


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


def test_metadata_defaults_to_both_providers_and_preserves_explicit_provider_choices(
    tmp_path: Path,
) -> None:
    defaults = load_settings(tmp_path)
    assert defaults.metadata.open_library
    assert defaults.metadata.google_books
    chosen = Settings(metadata=MetadataSettings(google_books=C.TRUE, open_library=C.FALSE))
    save_settings(tmp_path, chosen)
    assert load_settings(tmp_path).metadata == chosen.metadata


def test_wikidata_is_explicit_and_has_a_separate_persisted_wire_budget(tmp_path: Path) -> None:
    assert not MetadataSettings().wikidata
    chosen = Settings(
        metadata=MetadataSettings(
            wikidata=C.TRUE,
            wikidata_max_requests_per_run=C.TWO,
        )
    )
    save_settings(tmp_path, chosen)
    assert load_settings(tmp_path).metadata == chosen.metadata
    with pytest.raises(ValidationError):
        MetadataSettings(wikidata_max_requests_per_run=C.ZERO)


def test_recommendation_acceleration_round_trips_and_rejects_unknown_policy(tmp_path: Path) -> None:
    chosen = Settings(recommendations=RecommendationSettings(acceleration=S.EM3_CUDA))
    save_settings(tmp_path, chosen)
    assert load_settings(tmp_path).recommendations == chosen.recommendations
    with pytest.raises(ValidationError):
        RecommendationSettings.model_validate(dict(acceleration=S.PRIVATE))


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


def test_missing_configuration_has_no_accounts_and_does_not_create_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    assert not load_settings(tmp_path).accounts
    assert not (tmp_path / S.CONFIG_JSON).exists()


def test_profiles_come_from_saved_config_with_explicit_environment_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(S.BOOKYSTATS_STORYGRAPH_PROFILE, raising=C.FALSE)
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE, raising=C.FALSE)
    settings = Settings(accounts=accounts())
    save_settings(tmp_path, settings)
    assert load_settings(tmp_path) == settings
    monkeypatch.setenv(
        S.BOOKYSTATS_GOODREADS_PROFILE,
        S.TEST_CONFIG_SETTINGS_ROUND_TRIP_GOODREADS_COM_USER_SHOW_READER,
    )
    overridden = {account.source: account for account in load_settings(tmp_path).accounts}
    assert overridden[Source.GOODREADS] == account_from_url(
        Source.GOODREADS, S.TEST_CONFIG_SETTINGS_ROUND_TRIP_GOODREADS_COM_USER_SHOW_READER
    )
    assert overridden[Source.STORYGRAPH] == settings.accounts[C.ZERO]
    monkeypatch.delenv(S.BOOKYSTATS_GOODREADS_PROFILE)
    assert load_settings(tmp_path) == settings
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


def test_explicit_data_directory_takes_precedence_over_environment_and_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = tmp_path / S.TEST_REPORTING_ENV_DIRECTORY
    checkout = tmp_path / S.TEST_REPORTING_CHECKOUT
    override = tmp_path / S.TEST_REPORTING_OVERRIDE_DIRECTORY
    monkeypatch.setenv(S.BOOKYSTATS_DATA_DIR, str(environment))
    monkeypatch.setattr(config, S.TEST_REPORTING_CHECKOUT_ROOT, lambda: checkout)
    assert data_directory(override) == override.resolve()
    assert not override.exists()
    assert not environment.exists()
    assert not checkout.exists()


def test_environment_data_directory_takes_precedence_without_creating_checkout_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / S.TEST_REPORTING_CHECKOUT
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(S.BOOKYSTATS_DATA_DIR, S.TEST_REPORTING_ENV_DIRECTORY)
    monkeypatch.setattr(config, S.TEST_REPORTING_CHECKOUT_ROOT, lambda: checkout)
    assert data_directory() == (tmp_path / S.TEST_REPORTING_ENV_DIRECTORY).resolve()
    assert not checkout.exists()
    assert not (tmp_path / S.TEST_REPORTING_ENV_DIRECTORY).exists()


def test_editable_checkout_defaults_to_repository_data_independent_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / S.TEST_REPORTING_CHECKOUT
    module = (
        checkout
        / S.SOURCE_FOLDER
        / S.BOOKYSTATS_2
        / S.RUNTIME_FOLDER
        / S.TEST_REPORTING_MODULE_FILE
    )
    module.parent.mkdir(parents=C.TRUE)
    module.write_text(S.EMPTY, encoding=S.UTF_8)
    (checkout / S.PYPROJECT_FILE).write_text(S.EMPTY, encoding=S.UTF_8)
    monkeypatch.setattr(config, S.TEST_REPORTING_FILE_ATTRIBUTE, str(module))
    monkeypatch.delenv(S.BOOKYSTATS_DATA_DIR)
    monkeypatch.chdir(tmp_path)
    assert data_directory() == checkout / S.CHECKOUT_DATA_FOLDER
    assert not (checkout / S.CHECKOUT_DATA_FOLDER).exists()


def test_noneditable_install_falls_back_to_platform_data_without_creating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = (
        tmp_path
        / S.TEST_REPORTING_INSTALLED_DIRECTORY
        / S.BOOKYSTATS_2
        / S.RUNTIME_FOLDER
        / S.TEST_REPORTING_MODULE_FILE
    )
    fallback = tmp_path / S.TEST_REPORTING_PLATFORM_DIRECTORY
    calls: list[tuple[str, bool]] = []

    def platform_data(appname: str, *, appauthor: bool) -> Path:
        calls.append((appname, appauthor))
        return fallback

    monkeypatch.setattr(config, S.TEST_REPORTING_FILE_ATTRIBUTE, str(module))
    monkeypatch.setattr(config, S.TEST_REPORTING_USER_DATA_PATH, platform_data)
    monkeypatch.delenv(S.BOOKYSTATS_DATA_DIR)
    assert data_directory() == fallback.resolve()
    assert calls == [(S.BOOKYSTATS, C.FALSE)]
    assert not fallback.exists()
    assert not module.exists()
