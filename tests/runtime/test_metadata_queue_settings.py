from bookystats import constants as C
from bookystats import strings as S
from bookystats.runtime.config import MetadataSettings


def test_legacy_age_setting_loads_but_is_not_saved_as_an_active_policy() -> None:
    settings = MetadataSettings.model_validate(
        {S.QUEUE_LEGACY_MAX_AGE_KEY: C.METADATASETTINGS_MAX_AGE_DAYS_DEFAULT}
    )
    assert settings.google_books and settings.open_library
    assert S.QUEUE_LEGACY_MAX_AGE_KEY not in settings.model_dump()
