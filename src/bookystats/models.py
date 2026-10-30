from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, JsonValue, field_validator

from bookystats import constants as C
from bookystats import strings as S
from bookystats.constants import FieldState as FieldState
from bookystats.constants import Model as Model
from bookystats.constants import ReadingStatus as ReadingStatus
from bookystats.constants import Source as Source
from bookystats.constants import SyncState as SyncState


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class PartialDate(Model):
    value: str
    raw: str | None = C.NONE

    @field_validator(S.VALUE)
    @classmethod
    def valid_date(cls, value: str) -> str:
        if not re.fullmatch(S.DATES_PARSE_DATE_D_D_D, value):
            raise ValueError(S.MODELS_PARTIALDATE_VALID_DATE_DATE_MUST_HAVE_YYYY_YYYY_MM_OR)
        parts = [int(part) for part in value.split(S.HYPHEN)]
        if not C.ONE <= parts[C.ZERO] <= C.MODELS_PARTIALDATE_VALID_DATE:
            raise ValueError(S.MODELS_PARTIALDATE_VALID_DATE_YEAR_IS_OUTSIDE_THE_SUPPORTED_RANGE)
        if len(parts) >= C.TWO and (not C.ONE <= parts[C.ONE] <= C.MODELS_PARTIALDATE_VALID_DATE_2):
            raise ValueError(S.MODELS_PARTIALDATE_VALID_DATE_MONTH_IS_OUTSIDE_THE_SUPPORTED_RANGE)
        if len(parts) == C.THREE and (
            not C.ONE <= parts[C.TWO] <= calendar.monthrange(parts[C.ZERO], parts[C.ONE])[C.ONE]
        ):
            raise ValueError(S.MODELS_PARTIALDATE_VALID_DATE_DAY_IS_OUTSIDE_THE_SUPPORTED_RANGE)
        return value

    @property
    def precision(self) -> S.DatePrecision:
        if len(self.value) == C.FOUR:
            return S.YEAR
        if len(self.value) == C.SEVEN:
            return S.MONTH
        return S.DAY


class Issue(Model):
    code: str
    message: str
    source_id: str | None = C.NONE
    retryable: bool = C.FALSE


class Observation(Model):
    field: str
    value: JsonValue = C.NONE
    state: FieldState
    scope: S.ObservationScope = S.WORK
    source_url: str
    observed_at: str = Field(default_factory=utc_now)

    @C.AFTER_MODEL_VALIDATOR
    def consistent_state(self) -> Observation:
        if self.state == FieldState.PRESENT and self.value is C.NONE:
            raise ValueError(S.MODELS_OBSERVATION_CONSISTENT_STATE_A_OBSERVATION_MUST_HAVE_A)
        if self.state != FieldState.PRESENT and self.value is not C.NONE:
            raise ValueError(S.MODELS_OBSERVATION_CONSISTENT_STATE_CANNOT_CONTAIN_INVENTED_VALUES)
        return self


class ReadingEvent(Model):
    source_event_id: str | None = C.NONE
    started: PartialDate | None = C.NONE
    finished: PartialDate | None = C.NONE
    status: ReadingStatus = ReadingStatus.UNKNOWN

    @C.AFTER_MODEL_VALIDATOR
    def ordered_dates(self) -> ReadingEvent:
        if (
            self.started is not C.NONE
            and self.finished is not C.NONE
            and (self.started.precision == self.finished.precision)
            and (self.started.value > self.finished.value)
        ):
            raise ValueError(S.MODELS_READINGEVENT_ORDERED_DATES_READING_START_IS_AFTER_ITS_FINISH)
        return self


class BookRecord(Model):
    source: Source
    source_id: str = Field(min_length=C.ONE)
    title: str = Field(min_length=C.ONE)
    authors: tuple[str, ...] = ()
    url: str
    status: ReadingStatus = ReadingStatus.UNKNOWN
    raw_status: str | None = C.NONE
    isbns: tuple[str, ...] = ()
    edition_format: str | None = C.NONE
    language: str | None = C.NONE
    collections: tuple[str, ...] = ()
    shelves: tuple[str, ...] = ()
    added_at: PartialDate | None = C.NONE
    shelf_position: int | None = Field(default=C.NONE, ge=C.ZERO)
    observations: tuple[Observation, ...] = ()
    reading_events: tuple[ReadingEvent, ...] = ()
    detail_checked_at: str | None = C.NONE

    @field_validator(S.URL)
    @classmethod
    def absolute_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != S.HTTPS or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(S.MODELS_BOOKRECORD_ABSOLUTE_URL_BOOK_MUST_BE_ABSOLUTE_HTTPS_URLS)
        return value


class Account(Model):
    source: Literal[Source.STORYGRAPH, Source.GOODREADS]
    account_id: str = Field(min_length=C.ONE)
    profile_url: str

    @C.AFTER_MODEL_VALIDATOR
    def valid_profile(self) -> Account:
        parsed = urlsplit(self.profile_url)
        allowed = {
            Source.STORYGRAPH: {S.APP_THESTORYGRAPH_COM},
            Source.GOODREADS: {S.WWW_GOODREADS_COM, S.GOODREADS_COM},
        }
        if (
            parsed.scheme != S.HTTPS
            or parsed.hostname not in allowed[self.source]
            or parsed.username
            or parsed.password
            or (parsed.port not in (C.NONE, C.MODELS_ACCOUNT_VALID_PROFILE))
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(S.MODELS_ACCOUNT_VALID_PROFILE_PROFILE_MUST_BE_AN_UNCREDENTIALED_HTTPS)
        if self.source == Source.GOODREADS:
            match = re.fullmatch(S.CONFIG_ACCOUNT_FROM_URL_MATCHED_USER_SHOW_D, parsed.path)
            if match is C.NONE or match[C.ONE] != self.account_id:
                raise ValueError(S.MODELS_ACCOUNT_VALID_PROFILE_IDENTIFY_THE_CONFIGURED_READER)
        else:
            match = re.fullmatch(S.ACCOUNT_VALID_PROFILE_MATCH_PROFILE, parsed.path)
            if match is C.NONE or match[C.ONE] != self.account_id:
                raise ValueError(S.MODELS_ACCOUNT_VALID_PROFILE_IDENTIFY_THE_CONFIGURED_READER_2)
        return self


class CollectionProgress(Model):
    source: Source
    collection: str
    pages_seen: int = Field(default=C.ZERO, ge=C.ZERO)
    records: tuple[BookRecord, ...] = ()
    cursor: str | None = C.NONE
    message: str = S.EMPTY


class CollectionSnapshot(Model):
    source: Source
    account_id: str
    collection: str
    state: SyncState
    records: tuple[BookRecord, ...] = ()
    started_at: str
    finished_at: str = Field(default_factory=utc_now)
    pages_seen: int = Field(default=C.ZERO, ge=C.ZERO)
    expected_count: int | None = Field(default=C.NONE, ge=C.ZERO)
    identity_verified: bool = C.FALSE
    termination_verified: bool = C.FALSE
    capabilities: dict[str, FieldState] = Field(default_factory=dict)
    issues: tuple[Issue, ...] = ()

    @C.AFTER_MODEL_VALIDATOR
    def complete_means_complete(self) -> CollectionSnapshot:
        ids = [record.source_id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError(S.MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_MUST_BE_RECONCILED_BEFORE)
        if any(record.source != self.source for record in self.records):
            raise ValueError(S.MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_RECORD_FROM_ANOTHER_SOURCE)
        if self.state == SyncState.COMPLETE:
            if not self.identity_verified or not self.termination_verified:
                raise ValueError(S.MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_IDENTITY_AND_PAGINATION)
            if self.expected_count is not C.NONE and len(ids) != self.expected_count:
                raise ValueError(
                    S.MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_DIFFERS_FROM_THE_EXPECTED
                )
            if any(
                item.state == FieldState.FAILED
                for book in self.records
                for item in book.observations
            ):
                raise ValueError(S.MODELS_COLLECTIONSNAPSHOT_COMPLETE_MEANS_CANNOT_BE_PUBLISHED_AS)
        return self


class MetadataCandidate(Model):
    provider: Literal[Source.GOOGLE_BOOKS, Source.OPEN_LIBRARY]
    provider_id: str
    title: str
    authors: tuple[str, ...] = ()
    isbns: tuple[str, ...] = ()
    url: str
    observations: tuple[Observation, ...] = ()
    work_id: str | None = C.NONE
    edition_id: str | None = C.NONE


class EnrichmentResult(Model):
    source_id: str
    state: SyncState
    candidates: tuple[MetadataCandidate, ...] = ()
    issues: tuple[Issue, ...] = ()
    cache_hit: bool = C.FALSE


class PublicationResult(Model):
    snapshot_id: int
    added: int = C.ZERO
    updated: int = C.ZERO
    unchanged: int = C.ZERO
    removed: int = C.ZERO
    unresolved: int = C.ZERO
    issues: tuple[Issue, ...] = ()
