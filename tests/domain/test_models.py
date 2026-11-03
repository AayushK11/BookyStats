from __future__ import annotations

import pytest
from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.dates import parse_date
from bookystats.domain.identifiers import normalize_isbn
from bookystats.domain.models import (
    CollectionSnapshot,
    FieldState,
    Observation,
    PartialDate,
    ReadingEvent,
    Source,
    SupplementalCompletionDate,
    SyncState,
    utc_now,
)


def test_partial_date_precision_is_preserved() -> None:
    year = parse_date(S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT)
    month = parse_date(S.TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_MONTH_TEXT)
    leap_day = parse_date(S.TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_LEAP_DAY_FEBRUARY)
    assert year == PartialDate(
        value=S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT,
        raw=S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT,
    )
    assert year.precision == S.YEAR
    assert month is not C.NONE and month.precision == S.MONTH
    assert (
        leap_day is not C.NONE
        and leap_day.value == S.TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_TEXT
    )
    with pytest.raises(ValueError):
        parse_date(S.TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_TEXT_2)
    with pytest.raises(ValueError):
        parse_date(S.TEST_MODELS_PARTIAL_DATE_PRECISION_IS_PRESERVED_TEXT_3)


def test_invalid_reading_order_is_not_silently_normalized() -> None:
    with pytest.raises(ValidationError):
        ReadingEvent(
            started=PartialDate(
                value=S.TEST_INVALID_READING_ORDER_IS_NOT_SILENTLY_NORMALIZED_STARTED_TEXT
            ),
            finished=PartialDate(
                value=S.TEST_INVALID_READING_ORDER_IS_NOT_SILENTLY_NORMALIZED_FINISHED_TEXT
            ),
        )


def test_isbn_uid_and_spreadsheet_wrapping() -> None:
    assert (
        normalize_isbn(S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT)
        == S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_2
    )
    assert (
        normalize_isbn(S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_3)
        == S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_2
    )
    assert normalize_isbn(S.TEST_MODELS_ISBN_UID_AND_SPREADSHEET_WRAPPING_TEXT_4) is C.NONE
    assert normalize_isbn(S.FBDD6B7C_F512_47F2_AA94_D8BF0D5F5175) is C.NONE


def test_missing_observation_is_not_zero() -> None:
    with pytest.raises(ValidationError):
        Observation(
            field=S.RATING,
            value=C.ZERO,
            state=FieldState.EMPTY,
            source_url=S.TEST_MODELS_MISSING_OBSERVATION_IS_THESTORYGRAPH_COM_BOOKS_EXAMPLE,
        )
    observed = Observation(
        field=S.RATING,
        value=C.TEST_MISSING_OBSERVATION_IS_NOT_ZERO_OBSERVED,
        state=FieldState.PRESENT,
        source_url=S.TEST_MODELS_MISSING_OBSERVATION_IS_THESTORYGRAPH_COM_BOOKS_EXAMPLE,
    )
    assert observed.value == C.TEST_MODELS_MISSING_OBSERVATION_IS_NOT_ZERO


def test_supplemental_completion_requires_consistent_reader_evidence() -> None:
    observed = Observation(
        field=S.DTX_SUPPLEMENTAL_COMPLETION_DATE,
        value=S.DTX_TEST_DAY,
        state=FieldState.PRESENT,
        scope=S.READER,
        source_url=S.TEST_IMPORT_ORIGIN,
    )
    supplemental = SupplementalCompletionDate(
        source_id=S.TEST_IMPORT_UID,
        finished=PartialDate(value=S.DTX_TEST_DAY),
        observation=observed,
    )
    assert supplemental.source == Source.STORYGRAPH
    with pytest.raises(ValidationError):
        SupplementalCompletionDate(
            source_id=supplemental.source_id,
            finished=PartialDate(value=S.DTX_TEST_YEAR),
            observation=observed,
        )
    with pytest.raises(ValidationError):
        SupplementalCompletionDate(
            source_id=supplemental.source_id,
            finished=supplemental.finished,
            observation=observed.model_copy(update={S.DTX_SCOPE: S.WORK}),
        )


def test_complete_snapshot_requires_real_termination_and_identity() -> None:
    with pytest.raises(ValidationError):
        CollectionSnapshot(
            source=Source.GOODREADS,
            account_id=S.TEST_MODELS_COMPLETE_SNAPSHOT_REQUIRES_AND_IDENTITY_ACCOUNT_ID_TEXT,
            collection=S.TO_READ,
            state=SyncState.COMPLETE,
            started_at=utc_now(),
        )


def test_file_completion_requires_raw_lineage_and_eof_not_claimed_account_identity() -> None:
    snapshot = CollectionSnapshot(
        source=Source.GOODREADS,
        account_id=S.TEST_MODELS_COMPLETE_SNAPSHOT_REQUIRES_AND_IDENTITY_ACCOUNT_ID_TEXT,
        collection=S.LIBRARY,
        state=SyncState.COMPLETE,
        started_at=utc_now(),
        input_kind=S.INPUT_FILE,
        raw_document_id=S.INPUT_TEST_RAW_ID,
        processing_version=S.INPUT_TEST_VERSION,
        termination_verified=C.TRUE,
        expected_count=C.ZERO,
    )
    assert not snapshot.identity_verified
    for update in C.INPUT_INVALID_LINEAGE_UPDATES:
        with pytest.raises(ValidationError):
            CollectionSnapshot.model_validate(snapshot.model_copy(update=update).model_dump())


def test_missing_file_failure_does_not_invent_raw_lineage() -> None:
    failed = CollectionSnapshot(
        source=Source.GOODREADS,
        account_id=S.TEST_MODELS_COMPLETE_SNAPSHOT_REQUIRES_AND_IDENTITY_ACCOUNT_ID_TEXT,
        collection=S.READ,
        state=SyncState.FAILED,
        started_at=utc_now(),
        input_kind=S.INPUT_FILE,
        processing_version=S.INPUT_TEST_VERSION,
    )
    assert failed.raw_document_id is C.NONE
    with pytest.raises(ValidationError):
        CollectionSnapshot.model_validate(
            failed.model_copy(
                update={
                    S.STATE: SyncState.COMPLETE,
                    S.TERMINATION_VERIFIED: C.TRUE,
                }
            ).model_dump()
        )
