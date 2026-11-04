from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

from platformdirs import user_data_path
from pydantic import Field, ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalyticsSettings
from bookystats.domain.errors import ConfigurationError
from bookystats.domain.models import Account, Model, Source


class MetadataSettings(Model):
    google_books: bool = C.TRUE
    open_library: bool = C.TRUE
    wikidata: bool = C.FALSE
    wikidata_max_requests_per_run: int = Field(
        default=C.WIKIDATA_MAX_REQUESTS_DEFAULT,
        ge=C.ONE,
        le=C.WIKIDATA_MAX_REQUESTS_LIMIT,
    )
    strategy: S.MetadataStrategy = S.ENR_STRATEGY_OPEN_LIBRARY_FIRST
    max_books_per_run: int = Field(
        default=C.METADATASETTINGS_MAX_BOOKS_PER_RUN_DEFAULT,
        ge=C.ONE,
        le=C.METADATASETTINGS_MAX_BOOKS_PER_RUN_LE,
    )
    max_age_days: int = Field(
        default=C.METADATASETTINGS_MAX_AGE_DAYS_DEFAULT,
        ge=C.ONE,
        le=C.METADATASETTINGS_MAX_AGE_DAYS_LE,
        description=S.QUEUE_LEGACY_MAX_AGE_DESCRIPTION,
        exclude=C.TRUE,
    )
    contact: str | None = C.NONE


class FileSettings(Model):
    storygraph_file: Path | None = C.NONE
    goodreads_file: Path | None = C.NONE
    goodreads_watchlist_file: Path | None = C.NONE
    goodreads_read_file: Path | None = C.NONE

    @C.AFTER_MODEL_VALIDATOR
    def separate_goodreads_input_modes(self) -> FileSettings:
        if self.goodreads_file is not C.NONE and (
            self.goodreads_watchlist_file is not C.NONE or self.goodreads_read_file is not C.NONE
        ):
            raise ValueError(S.CLI_GOODREADS_SCOPE_CONFLICT)
        return self

    def paths(self, directory: Path) -> dict[tuple[Source, str], Path | None]:
        paths = {(Source.STORYGRAPH, S.LIBRARY): self.storygraph_file}
        if self.goodreads_file is not C.NONE:
            paths[(Source.GOODREADS, S.LIBRARY)] = self.goodreads_file
        else:
            paths[(Source.GOODREADS, S.TO_READ)] = self.goodreads_watchlist_file
            paths[(Source.GOODREADS, S.READ)] = self.goodreads_read_file
        resolved: dict[tuple[Source, str], Path | None] = {}
        for scope, path in paths.items():
            if path is C.NONE:
                resolved[scope] = C.NONE
                continue
            expanded = path.expanduser()
            if not expanded.is_absolute():
                portable = PureWindowsPath(expanded)
                if portable.drive or portable.root:
                    raise ConfigurationError(S.CSV_INPUT_FOREIGN_PATH)
                expanded = Path(*portable.parts)
            resolved[scope] = (directory / expanded).resolve()
        return resolved


class WeeklySettings(Model):
    enabled: bool = C.FALSE
    weekday: str | None = C.NONE
    time: str | None = C.NONE
    timezone: str | None = C.NONE

    @C.AFTER_MODEL_VALIDATOR
    def schedule_requires_explicit_time(self) -> WeeklySettings:
        if self.weekday is not C.NONE and self.weekday not in {
            S.MON,
            S.TUE,
            S.WED,
            S.THU,
            S.FRI,
            S.SAT,
            S.SUN,
        }:
            raise ValueError(S.CONFIG_WEEKLYSETTINGS_SCHEDULE_REQUIRES_EXPLICIT_BE_MON_THROUGH_SUN)
        if self.time is not C.NONE and (
            not re.fullmatch(S.CONFIG_WEEKLYSETTINGS_SCHEDULE_REQUIRES_EXPLICIT_TIME_D_D, self.time)
        ):
            raise ValueError(S.CONFIG_WEEKLYSETTINGS_SCHEDULE_REQUIRES_EXPLICIT_TIME_MUST_BE_HH_MM)
        if self.enabled and (not (self.weekday and self.time and self.timezone)):
            raise ValueError(S.CONFIG_WEEKLYSETTINGS_SCHEDULE_REQUIRES_AN_EXPLICIT_DAY_TIME)
        return self


class RecommendationSettings(Model):
    semantic_enabled: bool = C.TRUE
    allow_model_download: bool = C.TRUE
    acceleration: S.EmbeddingAcceleration = S.EM3_AUTO
    threads: int = Field(default=C.REC3_DEFAULT_THREADS, ge=C.ONE, le=C.REC3_MAX_THREADS)
    batch_size: int = Field(default=C.REC3_DEFAULT_BATCH, ge=C.ONE, le=C.REC3_MAX_BATCH)


class Settings(Model):
    schema_version: int = Field(default=C.ONE, ge=C.ONE, le=C.ONE)
    accounts: tuple[Account, ...] = Field(default_factory=tuple)
    http_timeout_seconds: float = Field(
        default=C.SETTINGS_HTTP_TIMEOUT_SECONDS_DEFAULT,
        gt=C.ZERO,
        le=C.SETTINGS_HTTP_TIMEOUT_SECONDS_LE,
    )
    files: FileSettings = Field(default_factory=FileSettings)
    analytics: AnalyticsSettings = Field(default_factory=AnalyticsSettings)
    recommendations: RecommendationSettings = Field(default_factory=RecommendationSettings)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)
    weekly: WeeklySettings = Field(default_factory=WeeklySettings)

    @C.AFTER_MODEL_VALIDATOR
    def one_account_per_source(self) -> Settings:
        if len({account.source for account in self.accounts}) != len(self.accounts):
            raise ValueError(S.CONFIG_SETTINGS_ONE_ACCOUNT_PER_SOURCE_CAN_HAVE_ONLY_ONE_READER)
        return self

    @property
    def account_fingerprint(self) -> str:
        encoded = json.dumps(
            sorted((account.source.value, account.account_id) for account in self.accounts),
            separators=(S.COMMA, S.COLON),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


def _checkout_root() -> Path | None:
    root = Path(__file__).resolve().parents[C.THREE]
    if (root / S.PYPROJECT_FILE).is_file() and (root / S.SOURCE_FOLDER / S.BOOKYSTATS_2).is_dir():
        return root
    return C.NONE


def data_directory(override: str | Path | None = C.NONE) -> Path:
    configured = override or os.environ.get(S.BOOKYSTATS_DATA_DIR)
    if configured:
        return Path(configured).expanduser().resolve()
    checkout = _checkout_root()
    if checkout is not C.NONE:
        return checkout / S.CHECKOUT_DATA_FOLDER
    return user_data_path(S.BOOKYSTATS, appauthor=C.FALSE).resolve()


def account_from_url(source: Source, url: str) -> Account:
    path = urlsplit(url.strip()).path
    if source == Source.STORYGRAPH:
        matched = re.fullmatch(S.CONFIG_ACCOUNT_FROM_URL_MATCHED_PROFILE_A_ZA_Z0_A_ZA_Z0, path)
    elif source == Source.GOODREADS:
        matched = re.fullmatch(S.CONFIG_ACCOUNT_FROM_URL_MATCHED_USER_SHOW_D, path)
    else:
        raise ConfigurationError(
            S.CONFIG_ACCOUNT_FROM_URL_ONLY_STORYGRAPH_AND_GOODREADS_CAN_BE_READER
        )
    if matched is C.NONE:
        raise ConfigurationError(S.CONFIG_ACCOUNT_FROM_URL_TEMPLATE.format(v0=source.value))
    try:
        return Account(source=source, account_id=matched[C.ONE], profile_url=url.strip())
    except (ValueError, ValidationError):
        raise ConfigurationError(
            S.CONFIG_ACCOUNT_FROM_URL_TEMPLATE_2.format(v0=source.value)
        ) from C.NONE


def configuration_path(directory: Path) -> Path:
    path = directory / S.CONFIG_JSON
    checkout = _checkout_root()
    if (
        not path.exists()
        and checkout is not C.NONE
        and directory.resolve() == (checkout / S.CHECKOUT_DATA_FOLDER).resolve()
    ):
        return checkout / S.CONFIG_JSON
    return path


def load_settings(directory: Path) -> Settings:
    path = configuration_path(directory)
    if path.exists():
        try:
            settings = Settings.model_validate_json(path.read_bytes())
        except (ValueError, ValidationError):
            raise ConfigurationError(
                S.CONFIG_LOAD_SETTINGS_CONFIG_JSON_IS_INVALID_CHECK_ITS_FIELDS
            ) from C.NONE
    else:
        settings = Settings()
    accounts: dict[Source, Account] = {account.source: account for account in settings.accounts}
    for source, variable in (
        (Source.STORYGRAPH, S.BOOKYSTATS_STORYGRAPH_PROFILE),
        (Source.GOODREADS, S.BOOKYSTATS_GOODREADS_PROFILE),
    ):
        value = os.environ.get(variable)
        if value:
            accounts[source] = account_from_url(source, value)
    return settings.model_copy(update={S.ACCOUNTS: tuple(accounts.values())})


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
    descriptor, temporary = tempfile.mkstemp(
        prefix=S.ATOMIC_WRITE_PREFIX_TEMPLATE.format(v0=path.name), dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, S.W, encoding=S.UTF_8, newline=S.NEWLINE) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, C.CONFIG_ATOMIC_WRITE)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=C.TRUE)


def save_settings(directory: Path, settings: Settings) -> None:
    atomic_write(directory / S.CONFIG_JSON, settings.model_dump_json(indent=C.TWO) + S.NEWLINE)
