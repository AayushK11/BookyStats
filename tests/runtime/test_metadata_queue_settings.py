from pathlib import Path

import pytest
from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.runtime.config import MetadataSettings, Settings, load_settings, save_settings


def test_legacy_age_setting_loads_but_is_not_saved_as_an_active_policy() -> None:
    settings = MetadataSettings.model_validate(
        {S.QUEUE_LEGACY_MAX_AGE_KEY: C.METADATASETTINGS_MAX_AGE_DAYS_DEFAULT}
    )
    assert settings.google_books and settings.open_library
    assert S.QUEUE_LEGACY_MAX_AGE_KEY not in settings.model_dump()


def test_metadata_strategy_defaults_and_independent_mode_round_trip(tmp_path: Path) -> None:
    assert MetadataSettings().strategy == S.ENR_STRATEGY_OPEN_LIBRARY_FIRST
    settings = Settings(
        metadata=MetadataSettings(strategy=S.ENR_STRATEGY_INDEPENDENT, max_books_per_run=C.TEN)
    )
    save_settings(tmp_path, settings)
    assert load_settings(tmp_path).metadata == settings.metadata
    with pytest.raises(ValidationError):
        MetadataSettings.model_validate({S.ENR_STRATEGY: S.INVALID})
