from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.adapters.metadata.open_library import OpenLibraryProvider
from bookystats.application.sync import SyncService
from bookystats.domain.analytics import AnalyticsSettings
from bookystats.domain.matching import MatchKind, MatchResult, title_author_key
from bookystats.domain.models import (
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    EnrichmentResult,
    FieldState,
    Issue,
    MetadataCandidate,
    Observation,
    PartialDate,
    PublicationResult,
    ReadingEvent,
    ReadingStatus,
    Source,
    SyncState,
)
from bookystats.persistence import library as storage_module
from bookystats.persistence.library import AccountMismatchError, Database, SnapshotRejectedError
from bookystats.persistence.payloads import PayloadIntegrityError, PayloadStore
from bookystats.runtime.config import Settings
from tests.adapters.metadata.test_open_library import FakeHttp, response, work_response
from tests.support.paths import fixture_path
from tests.support.sources import accounts


@pytest.fixture
def database_path() -> Iterator[Path]:
    directory = Path(S.TESTS) / S.FIXTURES / S.STORAGE / (S.CASE + uuid4().hex)
    directory.mkdir(parents=C.TRUE)
    try:
        yield (directory / S.LIBRARY_SQLITE)
    finally:
        shutil.rmtree(directory)


@pytest.fixture
def db(database_path: Path) -> Iterator[Database]:
    database = Database(database_path)
    database.initialize()
    try:
        yield database
    finally:
        database.close()


def test_existing_only_open_never_creates_a_missing_database(tmp_path: Path) -> None:
    path = tmp_path / S.LAYOUT_DATABASES / S.LIBRARY_SQLITE3
    with closing(Database(path)) as database, pytest.raises(sqlite3.OperationalError):
        database.initialize(require_existing=C.TRUE)
    assert not path.exists()
    assert not path.parent.exists()


def book(**changes: object) -> BookRecord:
    return BookRecord.model_validate(
        {
            S.SOURCE: Source.STORYGRAPH,
            S.SOURCE_ID: S.ONE_2,
            S.TITLE: S.MATILDA,
            S.AUTHORS: (S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
            S.URL: S.TEST_STORAGE_BOOK_HTTPS_APP_THESTORYGRAPH_COM_BOOKS_ONE,
            S.ISBNS: (S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,),
            S.STATUS: ReadingStatus.READ,
        }
        | changes
    )


def rating(
    value: float, *, field: str = S.RATING, observed_at: str = S.TEST_STORAGE_FINISH_T10
) -> Observation:
    return Observation(
        field=field,
        value=value,
        state=FieldState.PRESENT,
        scope=S.READER,
        source_url=S.TEST_STORAGE_BOOK_HTTPS_APP_THESTORYGRAPH_COM_BOOKS_ONE,
        observed_at=observed_at,
    )


def snapshot(
    *records: BookRecord,
    source: Source = Source.STORYGRAPH,
    account_id: str | None = C.NONE,
    collection: str = S.LIBRARY,
    state: SyncState = SyncState.COMPLETE,
    started_at: str = S.TEST_STORAGE_START_T10,
    finished_at: str = S.TEST_STORAGE_FINISH_T10,
) -> CollectionSnapshot:
    return CollectionSnapshot(
        source=source,
        account_id=account_id
        or (S.READER if source == Source.STORYGRAPH else S.TEST_STORAGE_SNAPSHOT_ACCOUNT_ID_TEXT),
        collection=collection,
        state=state,
        records=records,
        started_at=started_at,
        finished_at=finished_at,
        pages_seen=C.ONE,
        expected_count=len(records) if state == SyncState.COMPLETE else C.NONE,
        identity_verified=state == SyncState.COMPLETE,
        termination_verified=state == SyncState.COMPLETE,
        capabilities={
            S.RATING: FieldState.PRESENT,
            S.REVIEW: FieldState.PRESENT,
            S.READING_EVENTS: FieldState.PRESENT,
            S.STATUS: FieldState.PRESENT,
        }
        if source == Source.STORYGRAPH
        else {S.WATCHLIST: FieldState.PRESENT},
    )


def publish(db: Database, data: CollectionSnapshot) -> PublicationResult:
    run = db.start_run(S.TEST)
    result = db.save_snapshot(run, data)
    db.finish_run(run, data.state)
    assert result is not C.NONE
    return result


def library(db: Database) -> dict[str, int]:
    result = db.status()[S.LIBRARY]
    assert isinstance(result, dict)
    return {key: int(value) for key, value in result.items() if isinstance(value, int)}


def rows(db: Database, sql: str, values: tuple[object, ...] = ()) -> list[sqlite3.Row]:
    return db._connection().execute(sql, values).fetchall()


def _restore_legacy_layout(db: Database) -> None:
    connection = db._connection()
    payloads = PayloadStore(connection)
    connection.execute(S.STORAGE_DATABASE_INITIALIZE_BEGIN_IMMEDIATE)
    for select, update, collection in C.STORAGE_PAYLOAD_MIGRATIONS:
        for row in connection.execute(select).fetchall():
            text = (
                payloads.load_collection_json(row[C.ONE])
                if collection
                else payloads.load_text(row[C.ONE])
            )
            connection.execute(update, (text, row[C.ZERO]))
    connection.execute(S.TEST_STORAGE_DROP_PAYLOADS)
    connection.execute(S.TEST_STORAGE_FORCE_LEGACY)
    connection.execute(S.COMMIT)


def metadata_candidate(**changes: object) -> MetadataCandidate:
    return MetadataCandidate.model_validate(
        {
            S.PROVIDER: Source.GOOGLE_BOOKS,
            S.PROVIDER_ID: S.VOLUME,
            S.EDITION_ID: S.VOLUME,
            S.TITLE: S.MATILDA,
            S.AUTHORS: (S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,),
            S.ISBNS: (S.TEST_GOODREADS_RSS_WALKS_SHORT_PAGES_TO_A_VERIFIED_EMPTY_TAIL_TEXT_4,),
            S.URL: S.TEST_STORAGE_METADATA_CANDIDATE_HTTPS_GOOGLE_COM_BOOKS_ID_VOLUME,
            S.OBSERVATIONS: (
                Observation(
                    field=S.PAGE_COUNT,
                    value=C.TEST_STORAGE_METADATA_CANDIDATE,
                    scope=S.EDITION,
                    state=FieldState.PRESENT,
                    source_url=S.TEST_STORAGE_METADATA_CANDIDATE_HTTPS_GOOGLE_COM_BOOKS_ID_VOLUME,
                    observed_at=S.TEST_STORAGE_FINISH_T10,
                ),
            ),
        }
        | changes
    )


@pytest.mark.parametrize(
    S.STATE,
    [
        SyncState.PARTIAL,
        SyncState.NEEDS_AUTH,
        SyncState.BLOCKED,
        SyncState.FAILED,
        SyncState.NOT_CONFIGURED,
        SyncState.INTERRUPTED,
    ],
)
def test_noncomplete_empty_attempt_never_removes_active_membership(
    db: Database, state: SyncState
) -> None:
    original = book(source=Source.GOODREADS, status=ReadingStatus.TO_READ)
    publish(db, snapshot(original, source=Source.GOODREADS, collection=S.WATCHLIST))
    run = db.start_run(S.RETRY)
    result = db.save_snapshot(
        run,
        snapshot(
            source=Source.GOODREADS,
            collection=S.WATCHLIST,
            state=state,
            started_at=S.TEST_STORAGE_LATER_T10,
            finished_at=S.TEST_STORAGE_LATER_FINISH_T10,
        ),
    )
    db.finish_run(run, state)
    assert result is C.NONE
    assert db.active_records() == (original,)
    status = db.status()
    sources = status[S.SOURCES]
    assert isinstance(sources, list) and isinstance(sources[C.ZERO], dict)
    assert sources[C.ZERO][S.STATE] == state.value
    assert sources[C.ZERO][S.LAST_SUCCESS_AT] == S.TEST_STORAGE_FINISH_T10
    assert sources[C.ZERO][S.LAST_ATTEMPT_AT] == S.TEST_STORAGE_LATER_FINISH_T10
    assert sources[C.ZERO][S.ACTIVE_COUNT] == C.ONE
    assert (
        len(rows(db, S.TEST_STORAGE_NONCOMPLETE_EMPTY_ATTEMPT_ID_FROM_SNAPSHOTS_WHERE_PUB)) == C.ONE
    )


def test_complete_empty_removes_only_that_sources_collection(db: Database) -> None:
    first = book()
    second = book(
        source_id=S.TWO_2,
        title=S.TEST_COMPLETE_EMPTY_REMOVES_ONLY_SECOND_TITLE_DIFFERENT_WORK,
        isbns=(),
    )
    third = book(source=Source.GOODREADS, source_id=S.THIRD)
    publish(db, snapshot(first))
    publish(db, snapshot(second, collection=S.TO_READ))
    publish(db, snapshot(third, source=Source.GOODREADS, collection=S.WATCHLIST))
    result = publish(
        db,
        snapshot(started_at=S.TEST_STORAGE_LATER_T10, finished_at=S.TEST_STORAGE_LATER_FINISH_T10),
    )
    assert result.removed == C.ONE
    assert {(item.source, item.source_id) for item in db.active_records()} == {
        (Source.STORYGRAPH, S.TWO_2),
        (Source.GOODREADS, S.THIRD),
    }
    assert len(db.record_history(Source.STORYGRAPH, S.READER, S.ONE_2)) == C.ONE
    assert (
        len(rows(db, S.TEST_STORAGE_COMPLETE_EMPTY_REMOVES_SELECT_ID_FROM_SOURCE_RECORDS))
        == C.THREE
    )


def test_partial_evidence_is_durable_without_touching_current_personal_data(db: Database) -> None:
    original = book(observations=(rating(C.THREE),))
    publish(db, snapshot(original))
    partial = book(observations=(rating(C.FOUR),))
    run = db.start_run(S.PARTIAL)
    assert db.save_snapshot(run, snapshot(partial, state=SyncState.PARTIAL)) is C.NONE
    assert db.active_records() == (original,)
    history = db.record_history(Source.STORYGRAPH, S.READER, S.ONE_2)
    assert [item[S.PUBLISHED] for item in history] == [C.TRUE, C.FALSE]
    assert len(rows(db, S.TEST_STORAGE_PARTIAL_EVIDENCE_IS_DATA_SELECT_ID_FROM_OBSERVATIO)) == C.TWO
    assert library(db)[S.WORKS] == C.ONE


def test_reimport_ignores_check_timestamps_without_duplicate_works_or_readings(
    db: Database,
) -> None:
    event = ReadingEvent(
        source_event_id=S.READING_1,
        started=PartialDate(value=S.EVENT_STARTED_TEXT),
        finished=PartialDate(value=S.EVENT_FINISHED_TEXT),
        status=ReadingStatus.READ,
    )
    original = book(
        observations=(rating(C.FOUR),),
        reading_events=(event,),
        detail_checked_at=S.TEST_STORAGE_FINISH_T10,
    )
    first = publish(db, snapshot(original))
    newer = original.model_copy(
        update={
            S.OBSERVATIONS: (rating(C.FOUR, observed_at=S.TEST_STORAGE_LATER_FINISH_T10),),
            S.DETAIL_CHECKED_AT: S.TEST_STORAGE_LATER_FINISH_T10,
        }
    )
    second = publish(
        db,
        snapshot(
            newer, started_at=S.TEST_STORAGE_LATER_T10, finished_at=S.TEST_STORAGE_LATER_FINISH_T10
        ),
    )
    assert (first.added, second.added, second.updated, second.unchanged) == (
        C.ONE,
        C.ZERO,
        C.ZERO,
        C.ONE,
    )
    assert library(db) == {
        S.SOURCE_RECORDS: C.ONE,
        S.WORKS: C.ONE,
        S.EDITIONS: C.ONE,
        S.READING_EVENTS: C.ONE,
        S.UNRESOLVED: C.ZERO,
    }
    assert db.active_records()[C.ZERO].detail_checked_at == S.TEST_STORAGE_LATER_FINISH_T10
    assert (
        len(rows(db, S.TEST_STORAGE_REIMPORT_IGNORES_CHECK_READINGS_SELECT_ID_FROM_READING))
        == C.TWO
    )


def test_current_rating_and_review_changes_do_not_become_historical_reading_ratings(
    db: Database,
) -> None:
    old_event = ReadingEvent(
        source_event_id=S.OLD_READ,
        finished=PartialDate(value=S.OLD_EVENT_FINISHED_TEXT),
        status=ReadingStatus.READ,
    )
    review = Observation(
        field=S.REVIEW,
        value=S.TEST_CURRENT_RATING_AND_REVIEW_RATINGS_REVIEW_ORIGINAL_REVIEW,
        scope=S.READER,
        state=FieldState.PRESENT,
        source_url=S.TEST_STORAGE_BOOK_HTTPS_APP_THESTORYGRAPH_COM_BOOKS_ONE,
        observed_at=S.TEST_STORAGE_FINISH_T10,
    )
    original = book(observations=(rating(C.THREE), review), reading_events=(old_event,))
    publish(db, snapshot(original))
    updated = original.model_copy(
        update={
            S.OBSERVATIONS: (
                rating(
                    C.TEST_CURRENT_RATING_AND_REVIEW_READING_RATINGS_UPDATED_UPDATE,
                    observed_at=S.TEST_STORAGE_LATER_FINISH_T10,
                ),
                review.model_copy(
                    update={
                        S.VALUE: S.UPDATED_UPDATE_UPDATE_RECONSIDERED_REVIEW,
                        S.OBSERVED_AT: S.TEST_STORAGE_LATER_FINISH_T10,
                    }
                ),
            )
        }
    )
    result = publish(
        db,
        snapshot(
            updated,
            started_at=S.TEST_STORAGE_LATER_T10,
            finished_at=S.TEST_STORAGE_LATER_FINISH_T10,
        ),
    )
    assert (result.updated, result.added, result.unchanged) == (C.ONE, C.ZERO, C.ZERO)
    assert (
        db.active_records()[C.ZERO].observations[C.ZERO].value
        == C.TEST_STORAGE_CURRENT_RATING_AND_BECOME_HISTORICAL_READING_RATINGS
    )
    assert (
        len(rows(db, S.TEST_STORAGE_CURRENT_RATING_AND_REVIEW_RATINGS_SELECT_ID_FROM_RE)) == C.ONE
    )
    persisted_event = json.loads(
        rows(db, S.TEST_STORAGE_CURRENT_RATING_AND_READING_RATINGS_PERSISTED_EVENT_S)[C.ZERO][
            C.ZERO
        ]
    )
    assert persisted_event == old_event.model_dump(mode=S.JSON)
    assert S.RATING not in persisted_event
    assert [
        json.loads(row[S.JSON_2])
        for row in rows(
            db, S.TEST_STORAGE_CURRENT_RATING_AND_READING_RATINGS_SELECT_JSON, (S.RATING,)
        )
    ] == [C.THREE, C.TEST_STORAGE_CURRENT_RATING_AND_BECOME_HISTORICAL_READING_RATINGS]


def test_rereads_are_explicit_events_not_a_read_count(db: Database) -> None:
    events = (
        ReadingEvent(source_event_id=S.FIRST, finished=PartialDate(value=S.EVENTS_FINISHED_TEXT)),
        ReadingEvent(
            source_event_id=S.SECOND, finished=PartialDate(value=S.EVENTS_FINISHED_TEXT_2)
        ),
    )
    data = book(
        reading_events=events,
        observations=(
            Observation(
                field=S.READ_COUNT,
                value=C.SEVEN,
                state=FieldState.PRESENT,
                scope=S.READER,
                source_url=S.TEST_STORAGE_BOOK_HTTPS_APP_THESTORYGRAPH_COM_BOOKS_ONE,
            ),
        ),
    )
    publish(db, snapshot(data))
    publish(
        db,
        snapshot(
            data, started_at=S.TEST_STORAGE_LATER_T10, finished_at=S.TEST_STORAGE_LATER_FINISH_T10
        ),
    )
    assert library(db)[S.READING_EVENTS] == C.TWO
    only_count = book(
        source_id=S.COUNT_ONLY,
        title=S.TEST_REREADS_ARE_EXPLICIT_EVENTS_NOT_ONLY_COUNT_TITLE_OTHER_BOOK,
        isbns=(),
        observations=data.observations,
    )
    publish(
        db,
        snapshot(
            data,
            only_count,
            started_at=S.TEST_STORAGE_LATER_T10,
            finished_at=S.TEST_STORAGE_LATER_FINISH_T10,
        ),
    )
    assert library(db)[S.READING_EVENTS] == C.TWO


def test_anonymous_reading_completion_refines_one_event_and_preserves_history(db: Database) -> None:
    started = ReadingEvent(
        started=PartialDate(value=S.STARTED_STARTED_TEXT), status=ReadingStatus.CURRENTLY_READING
    )
    publish(db, snapshot(book(reading_events=(started,))))
    finished = started.model_copy(
        update={S.FINISHED: PartialDate(value=S.FINISHED_UPDATE_TEXT), S.STATUS: ReadingStatus.READ}
    )
    publish(
        db,
        snapshot(
            book(reading_events=(finished,)),
            started_at=S.TEST_STORAGE_LATER_T10,
            finished_at=S.TEST_STORAGE_LATER_FINISH_T10,
        ),
    )
    assert library(db)[S.READING_EVENTS] == C.ONE
    assert (
        len(rows(db, S.TEST_STORAGE_REIMPORT_IGNORES_CHECK_READINGS_SELECT_ID_FROM_READING))
        == C.TWO
    )
    assert len(db.record_history(Source.STORYGRAPH, S.READER, S.ONE_2)) == C.TWO


def test_distinct_source_event_ids_can_represent_same_date_rereads(db: Database) -> None:
    events = (
        ReadingEvent(
            source_event_id=S.ONE_2,
            finished=PartialDate(value=S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT),
        ),
        ReadingEvent(
            source_event_id=S.TWO_2,
            finished=PartialDate(value=S.TEST_GOODREADS_SOURCE_DATE_PRECISION_IS_RETAINED_TEXT),
        ),
    )
    data = book(reading_events=events)
    publish(db, snapshot(data))
    publish(db, snapshot(data))
    assert library(db)[S.READING_EVENTS] == C.TWO


@pytest.mark.parametrize(
    S.FINISHED,
    [
        C.NONE,
        PartialDate(value=S.EVENT_STARTED_TEXT),
        PartialDate(value=S.EVENT_FINISHED_TEXT),
        PartialDate(value=S.STARTED_STARTED_TEXT),
    ],
)
def test_anonymous_reread_multiplicity_is_stable_and_explicit_ids_still_deduplicate(
    db: Database, finished: PartialDate | None
) -> None:
    anonymous = ReadingEvent(finished=finished, status=ReadingStatus.READ)
    identified = anonymous.model_copy(update={S.SOURCE_EVENT_ID: S.READING_1})
    publish(db, snapshot(book(reading_events=(anonymous, identified, identified))))
    assert library(db)[S.READING_EVENTS] == C.TWO
    rereads = book(reading_events=(anonymous, identified, anonymous, identified))
    changed = publish(db, snapshot(rereads))
    assert changed.updated == C.ONE
    assert library(db)[S.READING_EVENTS] == C.THREE
    identities = [tuple(row) for row in rows(db, S.TEST_STORAGE_READING_IDENTITIES)]
    reordered = rereads.model_copy(
        update={S.READING_EVENTS: tuple(reversed(rereads.reading_events))}
    )
    repeated = publish(db, snapshot(reordered))
    assert repeated.updated == C.ZERO
    assert repeated.unchanged == C.ONE
    assert library(db)[S.READING_EVENTS] == C.THREE
    assert [tuple(row) for row in rows(db, S.TEST_STORAGE_READING_IDENTITIES)] == identities
    assert sum(row[C.TWO] == S.READING_1 for row in identities) == C.ONE


def test_valid_cross_source_identity_keeps_both_personal_assessments(db: Database) -> None:
    storygraph = book(
        observations=(
            rating(C.TEST_VALID_CROSS_SOURCE_PERSONAL_ASSESSMENTS_STORYGRAPH_OBSERVATIONS),
        )
    )
    goodreads = book(
        source=Source.GOODREADS, observations=(rating(C.ONE, field=S.GOODREADS_PERSONAL_RATING),)
    )
    publish(db, snapshot(storygraph))
    publish(db, snapshot(goodreads, source=Source.GOODREADS, collection=S.WATCHLIST))
    assert library(db)[S.SOURCE_RECORDS] == C.TWO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE
    assert {item.source: item.observations[C.ZERO].value for item in db.active_records()} == {
        Source.STORYGRAPH: C.TEST_STORAGE_VALID_CROSS_SOURCE_KEEPS_BOTH_PERSONAL_ASSESSMENTS,
        Source.GOODREADS: C.TEST_STORAGE_VALID_CROSS_SOURCE_KEEPS_BOTH_PERSONAL_ASSESSMENTS_2,
    }
    assert (
        len(rows(db, S.TEST_STORAGE_VALID_CROSS_SOURCE_IDENTITY_ID_FROM_MATCH_DECISIONS_W)) == C.ONE
    )


def test_shared_isbn_with_conflicting_authors_remains_unresolved(db: Database) -> None:
    publish(db, snapshot(book()))
    conflicting = book(
        source=Source.GOODREADS,
        authors=(S.TEST_SHARED_ISBN_WITH_CONFLICTING_CONFLICTING_AUTHORS_NOT_ROALD_DAHL,),
    )
    result = publish(db, snapshot(conflicting, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    assert library(db)[S.UNRESOLVED] == C.TWO
    assert result.unresolved == C.ONE
    assert db.match_candidates()[C.ZERO][S.KIND] == S.CONFLICTING


@pytest.mark.parametrize(S.CONFLICT_POSITION, [C.ZERO, C.ONE, C.TWO])
def test_snapshot_isbn_conflicts_cannot_merge_by_record_order(
    db: Database, conflict_position: int
) -> None:
    records = [book(source_id=S.FIRST), book(source_id=S.SECOND)]
    records.insert(
        conflict_position,
        book(
            source_id=S.CONFLICT,
            authors=(S.TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_A_DIFFERENT_AUTHOR,),
        ),
    )
    publish(db, snapshot(*records))
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.THREE
    assert library(db)[S.UNRESOLVED] == C.THREE


def test_exact_title_author_requires_resolution_and_keeps_editions_distinct(db: Database) -> None:
    publish(db, snapshot(book(isbns=())))
    publish(db, snapshot(book(source=Source.GOODREADS, isbns=()), source=Source.GOODREADS))
    assert library(db)[S.WORKS] == C.TWO
    candidate = db.match_candidates()[C.ZERO]
    assert candidate[S.KIND] == S.LIKELY
    decision_id = db.resolve_match(
        int(str(candidate[S.ID])),
        accept=C.TRUE,
        note=S.TEST_EXACT_TITLE_AUTHOR_REQUIRES_DECISION_ID_NOTE_READER_CONFIRMED,
    )
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO
    db.undo_match(decision_id)
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    assert db.match_candidates()[C.ZERO][S.RESOLUTION] == S.PENDING
    with pytest.raises(ValueError, match=S.UNREVERSED):
        db.undo_match(decision_id)


def test_normalized_existing_matches_reconsider_without_rewriting_identity_hashes(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    left = book(title=S.MATCH_UPGRADE_TEST_TITLE, authors=(S.MATCH_UPGRADE_TEST_AUTHOR,))
    right = book(
        source=Source.GOODREADS,
        title=S.MATCH_UPGRADE_TEST_SERIES_TITLE,
        authors=(S.MATCH_UPGRADE_TEST_SPACED_AUTHOR,),
    )
    with monkeypatch.context() as legacy:
        legacy.setattr(
            storage_module,
            S.MATCH_UPGRADE_TEST_COMPARE_ATTRIBUTE,
            lambda left, right: MatchResult(
                MatchKind.CONFLICTING, S.MATCHING_COMPARE_BOOKS_ISBN_AGREES_BUT_FULL_TITLES_DIFFER
            ),
        )
        publish(db, snapshot(left))
        publish(db, snapshot(right, source=Source.GOODREADS))
    before = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)
    assert library(db)[S.WORKS] == C.TWO
    db._connection().execute(
        S.MATCH_UPGRADE_TEST_LEGACY_KEY, (title_author_key(left), before[C.ZERO][S.ID])
    )
    repeated = publish(db, snapshot(right, source=Source.GOODREADS))
    assert repeated.unchanged == C.ONE
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE
    after = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)
    assert [row[S.IDENTITY_HASH] for row in before] == [row[S.IDENTITY_HASH] for row in after]
    assert len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)) == C.ONE
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert [tuple(row) for row in rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)] == [
        tuple(row) for row in after
    ]
    assert len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)) == C.ONE


def test_subtitle_index_discovers_candidates_without_promoting_ratings_or_editions(
    db: Database,
) -> None:
    left = book(title=S.MATCH_UPGRADE_TEST_TITLE, isbns=(), observations=(rating(C.FOUR),))
    right = book(source=Source.GOODREADS, title=S.MATCH_UPGRADE_TEST_SUBTITLE, isbns=())
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    candidate = db.match_candidates()[C.ZERO]
    assert candidate[S.KIND] == S.LIKELY
    assert candidate[S.REASON] == S.MATCH_UPGRADE_SUBTITLE_CANDIDATE
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert len(db.match_candidates()) == C.ONE
    assert not rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)


def test_alternate_isbns_remain_distinct_editions_despite_normalized_title(db: Database) -> None:
    publish(db, snapshot(book(title=S.MATCH_UPGRADE_TEST_TITLE)))
    alternate = book(
        source=Source.GOODREADS,
        title=S.MATCH_UPGRADE_TEST_SERIES_TITLE,
        isbns=(S.MATCH_UPGRADE_TEST_ALTERNATE_ISBN,),
    )
    publish(db, snapshot(alternate, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    assert db.match_candidates()[C.ZERO][S.KIND] == S.LIKELY
    assert not rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)


def test_multiple_confirmed_work_groups_are_not_resolved_by_record_order(db: Database) -> None:
    first = book(source_id=S.FIRST, isbns=())
    second = book(source_id=S.SECOND, source=Source.GOODREADS, isbns=())
    publish(db, snapshot(first))
    publish(db, snapshot(second, source=Source.GOODREADS))
    candidate_id = int(str(db.match_candidates()[C.ZERO][S.ID]))
    db.resolve_match(candidate_id, accept=C.FALSE)
    first = first.model_copy(update={S.ISBNS: book().isbns})
    second = second.model_copy(update={S.ISBNS: book().isbns})
    publish(db, snapshot(first))
    publish(db, snapshot(second, source=Source.GOODREADS))
    newcomer = book(source=Source.GOODREADS, source_id=S.THIRD)
    publish(db, snapshot(second, newcomer, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.THREE
    assert len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)) == C.ONE


def test_one_confirmed_work_with_multiple_editions_does_not_collapse_editions(db: Database) -> None:
    first = book(isbns=())
    second = book(source=Source.GOODREADS, isbns=())
    publish(db, snapshot(first))
    publish(db, snapshot(second, source=Source.GOODREADS))
    db.resolve_match(int(str(db.match_candidates()[C.ZERO][S.ID])), accept=C.TRUE)
    first = first.model_copy(update={S.ISBNS: book().isbns})
    second = second.model_copy(update={S.ISBNS: book().isbns})
    publish(db, snapshot(first))
    publish(db, snapshot(second, source=Source.GOODREADS))
    newcomer = book(source=Source.GOODREADS, source_id=S.THIRD)
    publish(db, snapshot(second, newcomer, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == C.TWO
    assert library(db)[S.EDITIONS] == C.THREE
    assert len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)) == C.ONE


def _different_editions(db: Database) -> tuple[BookRecord, BookRecord]:
    left = book()
    right = book(
        source=Source.GOODREADS,
        isbns=(S.MATCH_UPGRADE_TEST_ALTERNATE_ISBN,),
    )
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    return left, right


def _work_metadata(
    db: Database,
    item: BookRecord,
    *,
    work_id: str = S.MATCH_UPGRADE_TEST_PROVIDER_WORK,
) -> MetadataCandidate:
    candidate = MetadataCandidate(
        provider=Source.OPEN_LIBRARY,
        provider_id=work_id,
        work_id=work_id,
        title=item.title,
        authors=item.authors,
        isbns=item.isbns,
        url=S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=work_id),
    )
    db.save_enrichment(
        item.source,
        Source.OPEN_LIBRARY,
        EnrichmentResult(
            source_id=item.source_id, state=SyncState.COMPLETE, candidates=(candidate,)
        ),
    )
    return candidate


def test_withdrawn_source_records_cannot_supply_identity_or_conflict(db: Database) -> None:
    withdrawn = book()
    publish(db, snapshot(withdrawn))
    publish(db, snapshot())
    current = book(source=Source.GOODREADS)
    publish(db, snapshot(current, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert not db.match_candidates()
    assert not rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)
    identities = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)
    assert identities[C.ZERO][S.WORK_ID] != identities[C.ONE][S.WORK_ID]


def test_replacement_snapshot_excludes_withdrawn_conflicts_before_matching(db: Database) -> None:
    withdrawn = book(authors=(S.TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_A_DIFFERENT_AUTHOR,))
    publish(db, snapshot(withdrawn))
    goodreads = book(source=Source.GOODREADS)
    publish(db, snapshot(goodreads, source=Source.GOODREADS))
    replacement = book(source_id=S.SECOND)
    result = publish(db, snapshot(replacement))
    assert result.removed == C.ONE
    active = [row for row in rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES) if row[S.ID] != C.ONE]
    assert active[C.ZERO][S.WORK_ID] == active[C.ONE][S.WORK_ID]
    assert active[C.ZERO][S.EDITION_ID] == active[C.ONE][S.EDITION_ID]
    assert library(db)[S.UNRESOLVED] == C.ZERO


def test_current_verified_open_library_work_links_never_collapse_editions(db: Database) -> None:
    left, right = _different_editions(db)
    _work_metadata(db, left)
    _work_metadata(db, right)
    assert db.reconcile_provider_work_matches() == C.ONE
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO
    candidate = db.match_candidates(include_resolved=C.TRUE)[C.ZERO]
    assert candidate[S.RESOLUTION] == S.MATCH_UPGRADE_WORK_CONFIRMED
    assert candidate[S.REASON] == S.MATCH_UPGRADE_PROVIDER_REASON
    assert candidate[S.IDENTIFIERS] == [S.MATCH_UPGRADE_TEST_PROVIDER_WORK]
    identities = [tuple(row) for row in rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)]
    assert db.reconcile_provider_work_matches() == C.ZERO
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert [tuple(row) for row in rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)] == identities
    assert len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)) == C.ONE


def test_selected_partial_optional_metadata_still_supplies_confirmed_work_identity(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    _work_metadata(db, left)
    candidate = _work_metadata(db, right)
    db.save_enrichment(
        right.source,
        Source.OPEN_LIBRARY,
        EnrichmentResult(
            source_id=right.source_id,
            state=SyncState.PARTIAL,
            candidates=(candidate,),
            issues=(Issue(code=S.INVALID_METADATA_FIELD, message=S.MATCH_UPGRADE_PROVIDER_REASON),),
        ),
    )
    assert db.reconcile_provider_work_matches() == C.ONE
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO


def test_provider_work_text_without_source_authors_or_isbn_is_insufficient(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    left = left.model_copy(update={S.ISBNS: (), S.AUTHORS: ()})
    publish(db, snapshot(left))
    _work_metadata(db, left)
    _work_metadata(db, right)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_google_volume_ids_do_not_replace_reciprocal_full_bibliography_evidence(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    assert db.reconcile_provider_work_matches() == C.ONE
    assert (
        db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.REASON] == S.MATCH_REPAIR_WORK_REASON
    )
    for item in (left, right):
        candidate = metadata_candidate(
            provider_id=S.MATCH_UPGRADE_TEST_PROVIDER_WORK,
            work_id=S.MATCH_UPGRADE_TEST_PROVIDER_WORK,
            isbns=item.isbns,
        )
        db.save_enrichment(
            item.source,
            Source.GOOGLE_BOOKS,
            EnrichmentResult(
                source_id=item.source_id, state=SyncState.COMPLETE, candidates=(candidate,)
            ),
        )
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO


def test_reciprocal_bibliography_work_match_retains_edition_facts_and_is_reversible(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    left = left.model_copy(update={S.LANGUAGE: S.EN, S.EDITION_FORMAT: S.PAPERBACK})
    right = right.model_copy(update={S.LANGUAGE: S.FR, S.EDITION_FORMAT: S.AUDIOBOOK})
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ONE
    identities = [tuple(row) for row in rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)]
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert [tuple(row) for row in rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)] == identities
    candidate = db.match_candidates(include_resolved=C.TRUE)[C.ZERO]
    decision_id = int(str(candidate[S.DECISION_ID]))
    db.undo_match(decision_id)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO


@pytest.mark.parametrize(
    S.CHANGES,
    (
        {S.AUTHORS: (S.TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_A_DIFFERENT_AUTHOR,)},
        {S.TITLE: S.MATCH_UPGRADE_TEST_SUBTITLE},
        {S.TITLE: S.MATCH_UPGRADE_TEST_OMNIBUS},
    ),
)
def test_bibliography_work_matching_requires_full_title_and_authors(
    db: Database, changes: dict[str, object]
) -> None:
    _left, right = _different_editions(db)
    right = right.model_copy(update=changes)
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_unique_full_bibliography_can_link_works_without_inventing_edition_identifiers(
    db: Database,
) -> None:
    left = book(isbns=(), source_id=S.STORYGRAPH_UUID)
    right = book(source=Source.GOODREADS, isbns=(), source_id=S.STORYGRAPH_UUID)
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ONE
    candidate = db.match_candidates(include_resolved=C.TRUE)[C.ZERO]
    assert candidate[S.IDENTIFIERS] == []
    assert candidate[S.REASON] == S.MATCH_REPAIR_WORK_REASON
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO


def test_unselected_same_title_peer_blocks_reciprocal_bibliography_work_match(
    db: Database,
) -> None:
    _left, right = _different_editions(db)
    unselected = right.model_copy(update={S.SOURCE_ID: S.THIRD, S.ISBNS: ()})
    publish(db, snapshot(right, unselected, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.THREE


def test_unique_full_bibliography_within_one_source_is_not_cross_source_corroboration(
    db: Database,
) -> None:
    left = book(isbns=())
    right = left.model_copy(update={S.SOURCE_ID: S.SECOND})
    publish(db, snapshot(left, right))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_new_reciprocal_ambiguity_reverses_bibliography_work_link(db: Database) -> None:
    left, right = _different_editions(db)
    assert db.reconcile_provider_work_matches() == C.ONE
    third = right.model_copy(update={S.SOURCE_ID: S.THIRD, S.ISBNS: left.isbns})
    publish(db, snapshot(right, third, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    identities = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)
    assert identities[C.ZERO][S.WORK_ID] != identities[C.ONE][S.WORK_ID]
    assert db.reconcile_provider_work_matches() == C.ZERO


def test_changed_identity_hash_reverses_even_a_normalization_equivalent_work_link(
    db: Database,
) -> None:
    _left, right = _different_editions(db)
    assert db.reconcile_provider_work_matches() == C.ONE
    changed = right.model_copy(update={S.TITLE: S.MATILDA_2})
    publish(db, snapshot(changed, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO
    assert db.reconcile_provider_work_matches() == C.ZERO


def test_rejected_bibliography_candidate_is_not_automatically_reconsidered(db: Database) -> None:
    _different_editions(db)
    candidate = db.match_candidates()[C.ZERO]
    db.resolve_match(int(str(candidate[S.ID])), accept=C.FALSE)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.RESOLUTION] == S.REJECTED


def test_ambiguous_current_provider_identity_blocks_bibliography_fallback(db: Database) -> None:
    left, _right = _different_editions(db)
    first = _work_metadata(db, left)
    second = first.model_copy(
        update={
            S.PROVIDER_ID: S.MATCH_UPGRADE_TEST_OTHER_WORK,
            S.WORK_ID: S.MATCH_UPGRADE_TEST_OTHER_WORK,
            S.URL: S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=S.MATCH_UPGRADE_TEST_OTHER_WORK),
        }
    )
    db.save_enrichment(
        left.source,
        Source.OPEN_LIBRARY,
        EnrichmentResult(
            source_id=left.source_id,
            state=SyncState.COMPLETE,
            candidates=(first, second),
        ),
    )
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_isbn_corroborated_coauthor_omission_links_only_work_and_repeats_idempotently(
    db: Database,
) -> None:
    left = book(
        authors=(
            S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,
            S.TEST_NORMALIZED_FULL_TITLES_AND_LEFT_AUTHORS_QUENTIN_BLAKE,
        )
    )
    right = book(source=Source.GOODREADS)
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ONE
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO
    candidate = db.match_candidates(include_resolved=C.TRUE)[C.ZERO]
    assert candidate[S.REASON] == S.MATCH_REPAIR_CORROBORATED_REASON
    assert candidate[S.IDENTIFIERS] == list(left.isbns)
    assert db.reconcile_provider_work_matches() == C.ZERO


def test_conflicting_unselected_isbn_peer_blocks_coauthor_subset_work_matching(
    db: Database,
) -> None:
    left = book(
        authors=(
            S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,
            S.TEST_NORMALIZED_FULL_TITLES_AND_LEFT_AUTHORS_QUENTIN_BLAKE,
        )
    )
    right = book(source=Source.GOODREADS)
    conflicting = right.model_copy(
        update={
            S.SOURCE_ID: S.THIRD,
            S.AUTHORS: (S.TEST_MATCHING_SHARED_ISBN_WITH_NOT_CONFIRM_A_DIFFERENT_AUTHOR,),
        }
    )
    publish(db, snapshot(left))
    publish(db, snapshot(right, conflicting, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.THREE


def test_corroborated_coauthor_subset_cannot_override_verified_catalog_conflict(
    db: Database,
) -> None:
    left = book(
        authors=(
            S.TEST_GOOGLE_BOOKS_BOOK_AUTHORS_ROALD_DAHL,
            S.TEST_NORMALIZED_FULL_TITLES_AND_LEFT_AUTHORS_QUENTIN_BLAKE,
        )
    )
    right = book(source=Source.GOODREADS)
    publish(db, snapshot(left))
    publish(db, snapshot(right, source=Source.GOODREADS))
    _work_metadata(db, left)
    _work_metadata(db, right, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_different_verified_provider_work_ids_do_not_merge_same_title(db: Database) -> None:
    left, right = _different_editions(db)
    _work_metadata(db, left)
    _work_metadata(db, right, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_unselected_title_only_catalog_works_cannot_veto_unique_bibliography_links(
    db: Database,
) -> None:
    personal = book(isbns=())
    catalog = book(source=Source.GOODREADS, isbns=())
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ONE
    selected = _work_metadata(db, personal)
    alternative = selected.model_copy(
        update={
            S.PROVIDER_ID: S.MATCH_UPGRADE_TEST_OTHER_WORK,
            S.WORK_ID: S.MATCH_UPGRADE_TEST_OTHER_WORK,
            S.URL: S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=S.MATCH_UPGRADE_TEST_OTHER_WORK),
        }
    )
    db.save_enrichment(
        personal.source,
        Source.OPEN_LIBRARY,
        EnrichmentResult(
            source_id=personal.source_id,
            state=SyncState.COMPLETE,
            candidates=(selected, alternative),
        ),
    )
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO


def test_automatic_work_recovery_requires_same_pair_unchanged_identities_and_no_human_override(
    db: Database,
) -> None:
    personal = book(isbns=())
    catalog = book(source=Source.GOODREADS, isbns=())
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ONE
    duplicate = catalog.model_copy(update={S.SOURCE_ID: S.SECOND})
    publish(db, snapshot(catalog, duplicate, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    separated = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)
    assert separated[C.ZERO][S.WORK_ID] != separated[C.ONE][S.WORK_ID]
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ONE
    restored = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)
    assert restored[C.ZERO][S.WORK_ID] == restored[C.ONE][S.WORK_ID]
    assert restored[C.ZERO][S.EDITION_ID] != restored[C.ONE][S.EDITION_ID]
    assert db.reconcile_provider_work_matches() == C.ZERO


def test_current_catalog_conflict_splits_automatic_isbn_identity_and_rating(db: Database) -> None:
    personal = book(observations=(rating(C.FOUR),))
    catalog = book(source=Source.GOODREADS)
    for account, record in zip(accounts(), (personal, catalog), strict=C.TRUE):
        data = snapshot(
            record,
            source=account.source,
            account_id=account.account_id,
            collection=S.LIBRARY if account.source == Source.STORYGRAPH else S.READ,
        ).model_copy(update={S.INPUT_RAW_DOCUMENT_ID: S.ONE_2})
        publish(db, data)
    assert db.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO].rating == C.FOUR
    _work_metadata(db, personal)
    _work_metadata(db, catalog, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)

    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    assert db.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO].rating is C.NONE
    candidate = db.match_candidates()[C.ZERO]
    assert candidate[S.KIND] == S.CONFLICTING
    assert candidate[S.REASON] == S.MTX_CATALOG_CONFLICT
    decisions = len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)) == decisions


def test_catalog_conflict_blocks_new_isbn_link_into_existing_group(db: Database) -> None:
    personal = book()
    catalog = book(source=Source.GOODREADS)
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    _work_metadata(db, personal)
    _work_metadata(db, catalog, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)
    descendant = catalog.model_copy(update={S.SOURCE_ID: S.THIRD})

    publish(db, snapshot(catalog, descendant, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.THREE
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.THREE


def test_catalog_conflict_splits_dependent_automatic_isbn_links(db: Database) -> None:
    personal = book()
    catalog = book(source=Source.GOODREADS)
    descendant = catalog.model_copy(update={S.SOURCE_ID: S.THIRD})
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, descendant, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE
    _work_metadata(db, personal)
    _work_metadata(db, descendant, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)

    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.THREE
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.THREE


def test_same_current_catalog_and_unrelated_search_hit_do_not_split_isbn_link(
    db: Database,
) -> None:
    personal = book()
    catalog = book(source=Source.GOODREADS)
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    _work_metadata(db, personal)
    selected = _work_metadata(db, catalog)
    unrelated = selected.model_copy(
        update={
            S.PROVIDER_ID: S.MATCH_UPGRADE_TEST_OTHER_WORK,
            S.WORK_ID: S.MATCH_UPGRADE_TEST_OTHER_WORK,
            S.URL: S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=S.MATCH_UPGRADE_TEST_OTHER_WORK),
            S.TITLE: S.TEST_UNRELATED_SEARCH_HITS_DO_NOT_UNRELATED_TITLE_AN_UNRELATED_WORK,
            S.ISBNS: (),
        }
    )
    db.save_enrichment(
        catalog.source,
        Source.OPEN_LIBRARY,
        EnrichmentResult(
            source_id=catalog.source_id,
            state=SyncState.COMPLETE,
            candidates=(selected, unrelated),
        ),
    )
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE


def test_stale_catalog_identity_cannot_split_automatic_isbn_link(db: Database) -> None:
    personal = book()
    catalog = book(source=Source.GOODREADS)
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    _work_metadata(db, personal)
    _work_metadata(db, catalog, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)

    changed = catalog.model_copy(update={S.TITLE: S.MATILDA_2})
    publish(db, snapshot(changed, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE


def test_superseded_catalog_conflict_does_not_split_automatic_isbn_link(db: Database) -> None:
    personal = book()
    catalog = book(source=Source.GOODREADS)
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    _work_metadata(db, personal)
    _work_metadata(db, catalog, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)
    _work_metadata(db, catalog)

    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE


def test_withdrawn_catalog_conflict_does_not_split_active_isbn_pair(db: Database) -> None:
    personal = book()
    catalog = book(source=Source.GOODREADS)
    withdrawn = catalog.model_copy(update={S.SOURCE_ID: S.THIRD})
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, withdrawn, source=Source.GOODREADS))
    _work_metadata(db, personal)
    _work_metadata(db, withdrawn, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)

    publish(db, snapshot(catalog, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE


def test_catalog_conflict_preserves_explicit_acceptance_and_undo(db: Database) -> None:
    personal = book()
    catalog = book(source=Source.GOODREADS)
    publish(db, snapshot(personal))
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    _work_metadata(db, personal)
    _work_metadata(db, catalog, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)
    db.reconcile_provider_work_matches()
    candidate_id = int(str(db.match_candidates()[C.ZERO][S.ID]))
    decision_id = db.resolve_match(candidate_id, accept=C.TRUE)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE
    assert db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.RESOLUTION] == S.ACCEPTED

    db.undo_match(decision_id)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    db.resolve_match(candidate_id, accept=C.FALSE)
    publish(db, snapshot(catalog, source=Source.GOODREADS))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.RESOLUTION] == S.REJECTED


def test_provider_work_identity_cannot_override_contradictory_bibliography(db: Database) -> None:
    left, right = _different_editions(db)
    changed = right.model_copy(
        update={S.TITLE: S.TEST_MATCHING_FULL_TITLE_IS_NOT_MERGE_PARTS_TITLE_MATILDA_PART_TWO}
    )
    publish(db, snapshot(changed, source=Source.GOODREADS))
    _work_metadata(db, left)
    _work_metadata(db, changed)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_provider_work_matching_abstains_from_multiple_current_cross_source_candidates(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    third = right.model_copy(update={S.SOURCE_ID: S.THIRD})
    publish(db, snapshot(right, third, source=Source.GOODREADS))
    for item in (left, right, third):
        _work_metadata(db, item)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_conflicting_provider_work_ids_in_an_existing_group_block_transitive_merges(
    db: Database,
) -> None:
    left = book()
    same_edition = book(source=Source.GOODREADS)
    other_edition = book(
        source=Source.GOODREADS,
        source_id=S.THIRD,
        isbns=(S.MATCH_UPGRADE_TEST_ALTERNATE_ISBN,),
    )
    publish(db, snapshot(left))
    publish(db, snapshot(same_edition, other_edition, source=Source.GOODREADS))
    _work_metadata(db, left)
    _work_metadata(db, same_edition, work_id=S.MATCH_UPGRADE_TEST_OTHER_WORK)
    _work_metadata(db, other_edition)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.THREE


def test_stale_identity_invalidates_a_provider_work_link_without_transferring_ratings(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    _work_metadata(db, left)
    _work_metadata(db, right)
    assert db.reconcile_provider_work_matches() == C.ONE
    changed = left.model_copy(
        update={S.TITLE: S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_TITLE_DIFFERENT_BOOK}
    )
    publish(db, snapshot(changed))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    assert db.match_candidates()[C.ZERO][S.REASON] == S.MATCH_UPGRADE_PROVIDER_LOST
    assert db.match_candidates()[C.ZERO][S.KIND] == S.LIKELY
    assert len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)) == C.TWO
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert len(rows(db, S.MATCH_UPGRADE_TEST_DECISIONS)) == C.TWO


def test_latest_ambiguous_provider_attempt_does_not_reuse_last_good_work_identity(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    _work_metadata(db, left)
    candidate = _work_metadata(db, right)
    assert db.reconcile_provider_work_matches() == C.ONE
    other = candidate.model_copy(
        update={
            S.PROVIDER_ID: S.MATCH_UPGRADE_TEST_OTHER_WORK,
            S.WORK_ID: S.MATCH_UPGRADE_TEST_OTHER_WORK,
            S.URL: S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=S.MATCH_UPGRADE_TEST_OTHER_WORK),
        }
    )
    db.save_enrichment(
        right.source,
        Source.OPEN_LIBRARY,
        EnrichmentResult(
            source_id=right.source_id, state=SyncState.COMPLETE, candidates=(candidate, other)
        ),
    )
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_rejected_work_suggestion_and_explicit_undo_are_never_silently_overruled(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    candidate_id = int(str(db.match_candidates()[C.ZERO][S.ID]))
    rejection = db.resolve_match(candidate_id, accept=C.FALSE)
    _work_metadata(db, left)
    _work_metadata(db, right)
    assert db.reconcile_provider_work_matches() == C.ZERO
    db.undo_match(rejection)
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == C.TWO


def test_provider_work_decision_is_reversible_and_cannot_reappear_on_reconciliation(
    db: Database,
) -> None:
    left, right = _different_editions(db)
    _work_metadata(db, left)
    _work_metadata(db, right)
    assert db.reconcile_provider_work_matches() == C.ONE
    decision_id = int(str(db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.DECISION_ID]))
    db.undo_match(decision_id)
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    assert db.reconcile_provider_work_matches() == C.ZERO


def test_lost_provider_work_identity_also_splits_dependent_isbn_links(db: Database) -> None:
    left, right = _different_editions(db)
    _work_metadata(db, left)
    _work_metadata(db, right)
    assert db.reconcile_provider_work_matches() == C.ONE
    descendant = right.model_copy(update={S.SOURCE_ID: S.THIRD})
    publish(db, snapshot(right, descendant, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO
    changed = left.model_copy(
        update={S.TITLE: S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_TITLE_DIFFERENT_BOOK}
    )
    publish(db, snapshot(changed))
    assert db.reconcile_provider_work_matches() == C.ZERO
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.THREE


@pytest.mark.parametrize(S.MQ_IDENTITY_PARAMETERS, C.MQ_IDENTITY_TEST_CASES)
def test_observed_edition_identity_changes_make_selected_metadata_stale(
    db: Database, field: str, original_value: str, changed_value: str
) -> None:
    source = book(**{field: original_value})
    publish(db, snapshot(source))
    _work_metadata(db, source)
    before = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH]
    observation = Observation(
        field=field,
        value=changed_value,
        state=FieldState.PRESENT,
        scope=S.EDITION,
        source_url=source.url,
    )
    changed = source.model_copy(update={S.OBSERVATIONS: (observation,)})
    publish(db, snapshot(changed))
    assert rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH] != before
    assert db.metadata_for(source.source, S.READER, source.source_id)[C.ZERO][S.STALE_IDENTITY]
    publish(db, snapshot(source))
    assert rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH] == before
    assert not db.metadata_for(source.source, S.READER, source.source_id)[C.ZERO][S.STALE_IDENTITY]


@pytest.mark.parametrize(S.MQ_IDENTITY_PARAMETERS, C.MQ_IDENTITY_TEST_CASES)
def test_redundant_observed_edition_facts_preserve_identity_and_provider_freshness(
    db: Database, field: str, original_value: str, changed_value: str
) -> None:
    source = book(**{field: original_value})
    publish(db, snapshot(source))
    _work_metadata(db, source)
    before = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH]
    observation = Observation(
        field=field,
        value=original_value,
        state=FieldState.PRESENT,
        scope=S.EDITION,
        source_url=source.url,
    )
    publish(db, snapshot(source.model_copy(update={S.OBSERVATIONS: (observation, observation)})))
    assert rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH] == before
    assert not db.metadata_for(source.source, S.READER, source.source_id)[C.ZERO][S.STALE_IDENTITY]


@pytest.mark.parametrize(S.MQ_IDENTITY_PARAMETERS, C.MQ_IDENTITY_TEST_CASES)
def test_observation_only_edition_identity_is_hashed_and_order_independent(
    db: Database, field: str, original_value: str, changed_value: str
) -> None:
    source = book()
    publish(db, snapshot(source))
    _work_metadata(db, source)
    before = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH]
    observation = Observation(
        field=field,
        value=original_value,
        state=FieldState.PRESENT,
        scope=S.EDITION,
        source_url=source.url,
    )
    changed = source.model_copy(update={S.OBSERVATIONS: (observation,)})
    publish(db, snapshot(changed))
    observed = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH]
    assert observed != before
    assert db.metadata_for(source.source, S.READER, source.source_id)[C.ZERO][S.STALE_IDENTITY]
    contradictory = observation.model_copy(update={S.VALUE: changed_value})
    publish(
        db,
        snapshot(source.model_copy(update={S.OBSERVATIONS: (observation, contradictory)})),
    )
    conflicting = rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH]
    assert conflicting != observed
    publish(
        db,
        snapshot(
            source.model_copy(update={S.OBSERVATIONS: (contradictory, observation, observation)})
        ),
    )
    assert rows(db, S.MATCH_UPGRADE_TEST_IDENTITIES)[C.ZERO][S.IDENTITY_HASH] == conflicting


def test_automatic_match_can_be_reversed_without_reimport_silently_restoring_it(
    db: Database,
) -> None:
    first = book()
    second = book(source=Source.GOODREADS)
    publish(db, snapshot(first))
    publish(db, snapshot(second, source=Source.GOODREADS))
    decision_id = int(str(db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.DECISION_ID]))
    db.undo_match(decision_id)
    publish(db, snapshot(second, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == C.TWO
    assert db.match_candidates()[C.ZERO][S.RESOLUTION] == S.PENDING


@pytest.mark.parametrize(S.TEST_STORAGE_CHANGED_SOURCE, [Source.STORYGRAPH, Source.GOODREADS])
def test_unsupported_automatic_match_splits_and_remains_actionable_across_imports(
    db: Database, changed_source: Source
) -> None:
    event = ReadingEvent(
        source_event_id=S.READING_1, finished=PartialDate(value=S.EVENT_STARTED_TEXT)
    )
    source_books = {
        Source.STORYGRAPH: book(reading_events=(event,), observations=(rating(C.FOUR),)),
        Source.GOODREADS: book(
            source=Source.GOODREADS,
            reading_events=(event,),
            observations=(rating(C.ONE, field=S.GOODREADS_PERSONAL_RATING),),
        ),
    }
    for source, original in source_books.items():
        publish(db, snapshot(original, source=source))
        db.save_enrichment(
            source,
            Source.GOOGLE_BOOKS,
            EnrichmentResult(
                source_id=original.source_id,
                state=SyncState.COMPLETE,
                candidates=(metadata_candidate(),),
            ),
        )
    automatic_id = int(str(db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.DECISION_ID]))
    changed = source_books[changed_source].model_copy(
        update={
            S.TITLE: S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_TITLE_DIFFERENT_BOOK,
            S.AUTHORS: (S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_AUTHORS_OTHER_AUTHOR,),
            S.ISBNS: (S.TEST_UNRELATED_SEARCH_HITS_DO_EVIDENCE_UNRELATED_ISBNS_TEXT,),
        }
    )
    changed_snapshot = snapshot(changed, source=changed_source)
    publish(db, changed_snapshot)
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.TWO
    assert library(db)[S.UNRESOLVED] == C.TWO
    assert library(db)[S.READING_EVENTS] == C.TWO
    pending = db.match_candidates()[C.ZERO]
    assert pending[S.KIND] == C.MatchKind.UNRELATED.value
    assert pending[S.RESOLUTION] == S.PENDING
    invalidation_id = int(str(pending[S.DECISION_ID]))
    automatic = rows(
        db, S.DATABASE_UNDO_MATCH_DECISION_SELECT_FROM_MATCH_DECISIONS_WHERE_ID, (automatic_id,)
    )[C.ZERO]
    assert automatic[S.REVERSED_BY] == invalidation_id
    for source, original in source_books.items():
        account_id = (
            S.READER if source == Source.STORYGRAPH else S.TEST_STORAGE_SNAPSHOT_ACCOUNT_ID_TEXT
        )
        history = db.record_history(source, account_id, original.source_id)
        assert len(history) == (C.TWO if source == changed_source else C.ONE)
        assert history[C.ZERO][S.RECORD] == original.model_dump(mode=S.JSON)
        metadata = db.metadata_for(source, account_id, original.source_id)[C.ZERO]
        assert metadata[S.STALE_IDENTITY] is (source == changed_source)
        assert metadata[S.CANDIDATE] == metadata_candidate().model_dump(mode=S.JSON)
    db.close()
    db.initialize()
    repeated = publish(db, changed_snapshot)
    assert repeated.unchanged == C.ONE
    assert library(db)[S.WORKS] == C.TWO
    assert library(db)[S.UNRESOLVED] == C.TWO
    assert db.match_candidates()[C.ZERO][S.DECISION_ID] == invalidation_id
    db.undo_match(invalidation_id)
    publish(db, changed_snapshot)
    assert library(db)[S.WORKS] == library(db)[S.EDITIONS] == C.ONE
    assert db.match_candidates() == ()
    assert db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.RESOLUTION] == S.ACCEPTED


def test_changed_evidence_does_not_invalidate_explicit_human_acceptance(db: Database) -> None:
    publish(db, snapshot(book(isbns=())))
    other = book(source=Source.GOODREADS, isbns=())
    publish(db, snapshot(other, source=Source.GOODREADS))
    candidate_id = int(str(db.match_candidates()[C.ZERO][S.ID]))
    decision_id = db.resolve_match(candidate_id, accept=C.TRUE)
    changed = other.model_copy(
        update={
            S.TITLE: S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_TITLE_DIFFERENT_BOOK,
            S.AUTHORS: (S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_AUTHORS_OTHER_AUTHOR,),
        }
    )
    publish(db, snapshot(changed, source=Source.GOODREADS))
    assert library(db)[S.WORKS] == C.ONE
    assert library(db)[S.EDITIONS] == C.TWO
    assert db.match_candidates() == ()
    assert db.match_candidates(include_resolved=C.TRUE)[C.ZERO][S.DECISION_ID] == decision_id
    db.undo_match(decision_id)
    assert library(db)[S.WORKS] == C.TWO


def test_rejected_likely_match_and_undo_preserve_source_records(db: Database) -> None:
    publish(db, snapshot(book(isbns=())))
    other = book(source=Source.GOODREADS, isbns=())
    publish(db, snapshot(other, source=Source.GOODREADS))
    candidate_id = int(str(db.match_candidates()[C.ZERO][S.ID]))
    decision_id = db.resolve_match(candidate_id, accept=C.FALSE)
    publish(db, snapshot(other, source=Source.GOODREADS))
    assert db.match_candidates() == ()
    db.undo_match(decision_id)
    assert len(db.match_candidates()) == C.ONE
    assert library(db)[S.WORKS] == C.TWO


def test_source_ids_are_namespaced_and_stable_on_updates(db: Database) -> None:
    publish(db, snapshot(book(isbns=())))
    identity = rows(db, S.TEST_STORAGE_SOURCE_IDS_ARE_NAMESPACED_WORK_ID_EDITION_ID_FIRST_SEE)[
        C.ZERO
    ]
    other = book(
        source=Source.GOODREADS,
        title=S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_TITLE_DIFFERENT_BOOK,
        authors=(S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_OTHER_AUTHORS_OTHER_AUTHOR,),
        isbns=(),
    )
    publish(db, snapshot(other, source=Source.GOODREADS))
    changed = book(
        title=S.TEST_SOURCE_IDS_ARE_NAMESPACED_UPDATES_CHANGED_TITLE_CORRECTED_TITLE,
        isbns=(S.TEST_UNRELATED_SEARCH_HITS_DO_EVIDENCE_UNRELATED_ISBNS_TEXT,),
    )
    publish(
        db,
        snapshot(
            changed,
            started_at=S.TEST_STORAGE_LATER_T10,
            finished_at=S.TEST_STORAGE_LATER_FINISH_T10,
        ),
    )
    updated = rows(
        db,
        S.TEST_STORAGE_SOURCE_IDS_ARE_NAMESPACED_WORK_ID_EDITION_ID_FIRST_SEEN,
        (Source.STORYGRAPH.value,),
    )[C.ZERO]
    assert tuple(updated) == tuple(identity)
    assert library(db)[S.SOURCE_RECORDS] == library(db)[S.WORKS] == C.TWO


def test_account_change_is_rejected_but_its_evidence_is_retained(db: Database) -> None:
    original = book()
    publish(db, snapshot(original))
    run = db.start_run(S.FOREIGN_ACCOUNT)
    with pytest.raises(AccountMismatchError):
        db.save_snapshot(run, snapshot(book(source_id=S.FOREIGN), account_id=S.ANOTHER_READER))
    assert db.active_records() == (original,)
    rejected = db.record_history(Source.STORYGRAPH, S.ANOTHER_READER, S.FOREIGN)
    assert len(rejected) == C.ONE and rejected[C.ZERO][S.PUBLISHED] is C.FALSE
    assert rejected[C.ZERO][S.REJECTION_REASON]
    assert (
        rows(db, S.TEST_STORAGE_ACCOUNT_CHANGE_IS_ACCOUNT_ID_FROM_SOURCE_ACCOUN)[C.ZERO][C.ZERO]
        == S.READER
    )


def test_empty_first_complete_snapshot_also_binds_account(db: Database) -> None:
    publish(db, snapshot())
    run = db.start_run(S.DIFFERENT_ACCOUNT)
    with pytest.raises(AccountMismatchError):
        db.save_snapshot(run, snapshot(account_id=S.DIFFERENT))


def test_older_complete_snapshot_cannot_replace_newer_membership(db: Database) -> None:
    original = book()
    publish(
        db,
        snapshot(
            original,
            started_at=S.TEST_STORAGE_LATER_T10,
            finished_at=S.TEST_STORAGE_LATER_FINISH_T10,
        ),
    )
    run = db.start_run(S.STALE)
    with pytest.raises(SnapshotRejectedError, match=S.NEWER):
        db.save_snapshot(run, snapshot())
    assert db.active_records() == (original,)


def test_complete_model_copy_is_revalidated_before_any_removal(db: Database) -> None:
    publish(db, snapshot(book()))
    invalid = snapshot().model_copy(update={S.IDENTITY_VERIFIED: C.FALSE})
    run = db.start_run(S.BAD_CALLER)
    with pytest.raises(
        ValueError, match=S.TEST_STORAGE_COMPLETE_MODEL_COPY_ANY_REMOVAL_MATCH_VERIFIED_IDENTITY
    ):
        db.save_snapshot(run, invalid)
    assert len(db.active_records()) == C.ONE


def test_atomic_rollback_restores_memberships_records_observations_and_identity(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = book(observations=(rating(C.THREE),))
    publish(db, snapshot(original))
    baseline = library(db)
    save_record = db._save_record

    def fail_after_one(
        connection: sqlite3.Connection,
        snapshot_id: int,
        data: CollectionSnapshot,
        record: BookRecord,
        contested_isbns: set[str],
    ) -> tuple[int, bool]:
        if record.source_id == S.SECOND:
            raise RuntimeError(
                S.TEST_STORAGE_ATOMIC_ROLLBACK_RESTORES_IDENTITY_FAIL_AFTER_ONE_INJECT
            )
        return save_record(connection, snapshot_id, data, record, contested_isbns)

    monkeypatch.setattr(
        db, S.TEST_STORAGE_ATOMIC_ROLLBACK_RESTORES_AND_IDENTITY_SAVE_RECORD, fail_after_one
    )
    run = db.start_run(S.ROLLBACK_2)
    with pytest.raises(RuntimeError, match=S.INJECTED):
        db.save_snapshot(
            run,
            snapshot(
                book(observations=(rating(C.FIVE),)),
                book(source_id=S.SECOND),
                started_at=S.TEST_STORAGE_LATER_T10,
                finished_at=S.TEST_STORAGE_LATER_FINISH_T10,
            ),
        )
    assert library(db) == baseline
    assert db.active_records() == (original,)
    assert (
        len(rows(db, S.TEST_STORAGE_ATOMIC_ROLLBACK_RESTORES_IDENTITY_SELECT_ID_FROM_SNAPSH))
        == C.ONE
    )
    assert len(rows(db, S.TEST_STORAGE_PARTIAL_EVIDENCE_IS_DATA_SELECT_ID_FROM_OBSERVATIO)) == C.ONE
    assert not db._connection().in_transaction


def test_conflicting_explicit_reading_events_roll_back_entire_snapshot(db: Database) -> None:
    publish(db, snapshot(book()))
    events = (
        ReadingEvent(source_event_id=S.SAME, finished=PartialDate(value=S.EVENT_STARTED_TEXT)),
        ReadingEvent(source_event_id=S.SAME, finished=PartialDate(value=S.EVENTS_FINISHED_TEXT_3)),
    )
    run = db.start_run(S.CONFLICTING_EVENTS)
    with pytest.raises(
        ValueError, match=S.TEST_STORAGE_CONFLICTING_EXPLICIT_MATCH_CONFLICTING_OBSERVATIONS
    ):
        db.save_snapshot(run, snapshot(book(reading_events=events)))
    assert library(db)[S.READING_EVENTS] == C.ZERO
    assert (
        len(rows(db, S.TEST_STORAGE_ATOMIC_ROLLBACK_RESTORES_IDENTITY_SELECT_ID_FROM_SNAPSH))
        == C.ONE
    )


def test_precision_dates_and_source_added_date_round_trip_without_invention(db: Database) -> None:
    events = (
        ReadingEvent(
            started=PartialDate(value=S.EVENT_STARTED_TEXT, raw=S.EVENT_STARTED_TEXT),
            finished=PartialDate(value=S.EVENTS_FINISHED_TEXT_4, raw=S.EVENTS_FINISHED_RAW_JUNE),
        ),
        ReadingEvent(
            finished=PartialDate(value=S.EVENTS_FINISHED_TEXT_5, raw=S.EVENTS_FINISHED_RAW_MAY)
        ),
    )
    original = book(
        added_at=PartialDate(value=S.ORIGINAL_ADDED_AT_TEXT, raw=S.ORIGINAL_ADDED_AT_RAW_MARCH),
        reading_events=events,
    )
    publish(db, snapshot(original))
    assert db.active_records() == (original,)
    missing_added = book(
        source_id=S.MISSING_ADDED,
        title=S.TEST_PRECISION_DATES_AND_SOURCE_MISSING_ADDED_TITLE_ANOTHER_WORK,
        isbns=(),
    )
    publish(db, snapshot(original, missing_added))
    assert (
        next(item for item in db.active_records() if item.source_id == S.MISSING_ADDED).added_at
        is C.NONE
    )
    assert rows(
        db, S.TEST_STORAGE_PRECISION_DATES_AND_SOURCE_SELECT_FIRST_SEEN_FROM_SO, (S.MISSING_ADDED,)
    )[C.ZERO][C.ZERO]


def test_sql_metacharacters_remain_data(db: Database) -> None:
    dangerous = S.TEST_STORAGE_SQL_METACHARACTERS_REMAIN_DROP_TABLE_SOURCE_RECORDS
    original = book(
        source_id=dangerous,
        title=S.TEST_SQL_METACHARACTERS_REMAIN_DATA_ORIGINAL_TITLE_O_REILLY + dangerous,
        isbns=(),
    )
    data = snapshot(original, account_id=dangerous, collection=dangerous)
    run = db.start_run(dangerous)
    result = db.save_snapshot(run, data)
    assert result is not C.NONE and result.added == C.ONE
    assert db.active_records() == (original,)
    assert len(db.record_history(Source.STORYGRAPH, dangerous, dangerous)) == C.ONE
    assert (
        len(rows(db, S.TEST_STORAGE_COMPLETE_EMPTY_REMOVES_SELECT_ID_FROM_SOURCE_RECORDS)) == C.ONE
    )


def test_progress_is_restart_durable_and_never_activates_records(
    db: Database, database_path: Path
) -> None:
    run = db.start_run(S.RESUME)
    progress = CollectionProgress(
        source=Source.STORYGRAPH,
        collection=S.LIBRARY,
        pages_seen=C.TWO,
        records=(book(),),
        cursor=S.NEXT_PAGE,
    )
    db.stage_progress(run, progress)
    assert db.active_records() == ()
    assert not db._connection().in_transaction
    db.close()
    reopened = Database(database_path)
    try:
        assert reopened.staged_progress(run) == (progress,)
        assert reopened.active_records() == ()
        last = reopened.status()[S.LAST_RUN]
        assert isinstance(last, dict) and last[S.FINISHED_AT] is C.NONE
        reopened.finish_run(run, SyncState.INTERRUPTED)
    finally:
        reopened.close()


def test_restart_backup_pragmas_and_status_json(db: Database, database_path: Path) -> None:
    original = book(
        observations=(rating(C.TEST_RESTART_BACKUP_PRAGMAS_AND_STATUS_JSON_ORIGINAL_OBSERVATIONS),)
    )
    publish(db, snapshot(original))
    for pragma, expected in (
        (S.FOREIGN_KEYS, C.ONE),
        (S.JOURNAL_MODE, S.WAL),
        (S.BUSY_TIMEOUT, C.TEST_STORAGE_RESTART_BACKUP_PRAGMAS_AND_STATUS_JSON),
        (S.USER_VERSION, C.STORAGE_SCHEMA_VERSION),
    ):
        assert (
            db._connection()
            .execute(S.TEST_STORAGE_RESTART_BACKUP_PRAGMAS_AND_STATUS_JSON_PRAGMA + pragma)
            .fetchone()[C.ZERO]
            == expected
        )
    backup_path = database_path.with_name(S.BACKUP_SQLITE)
    db.backup(backup_path)
    db.close()
    reopened = Database(database_path)
    backup = Database(backup_path)
    try:
        assert reopened.active_records() == backup.active_records() == (original,)
        assert json.loads(json.dumps(reopened.status())) == reopened.status()
        assert not reopened._connection().in_transaction
        with pytest.raises(
            ValueError, match=S.TEST_STORAGE_RESTART_BACKUP_PRAGMAS_STATUS_JSON_MATCH_NEW_DISTINCT
        ):
            reopened.backup(backup_path)
    finally:
        reopened.close()
        backup.close()


def test_confident_metadata_is_separate_and_retains_provenance(db: Database) -> None:
    original = book(
        observations=(
            rating(C.TEST_CONFIDENT_METADATA_IS_RETAINS_PROVENANCE_ORIGINAL_OBSERVATIONS),
        )
    )
    publish(db, snapshot(original))
    candidate = metadata_candidate()
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(source_id=S.ONE_2, state=SyncState.COMPLETE, candidates=(candidate,)),
    )
    assert db.active_records() == (original,)
    selected = db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2)
    assert selected[C.ZERO][S.CANDIDATE] == candidate.model_dump(mode=S.JSON)
    assert selected[C.ZERO][S.STALE_IDENTITY] is C.FALSE
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    assert db.enrichment_targets(Source.OPEN_LIBRARY) == (original,)
    assert rows(db, S.TEST_STORAGE_CONFIDENT_METADATA_IS_SCOPE_SOURCE_URL_FROM_METADATA)[C.ZERO][
        :
    ] == (S.EDITION, S.TEST_STORAGE_METADATA_CANDIDATE_HTTPS_GOOGLE_COM_BOOKS_ID_VOLUME)
    assert not db._connection().in_transaction


def test_ambiguous_and_failed_metadata_do_not_replace_last_confident_selection(
    db: Database,
) -> None:
    original = book()
    publish(db, snapshot(original))
    first = metadata_candidate()
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(source_id=S.ONE_2, state=SyncState.COMPLETE, candidates=(first,)),
    )
    before = db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2)
    other = metadata_candidate(provider_id=S.SECOND, edition_id=S.SECOND)
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(source_id=S.ONE_2, state=SyncState.COMPLETE, candidates=(first, other)),
    )
    assert db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2) == before
    assert (
        len(rows(db, S.TEST_STORAGE_AMBIGUOUS_AND_FAILED_SELECTION_SELECT_ID_FROM_ENRICHM)) == C.ONE
    )
    metadata = db.status()[S.METADATA]
    assert isinstance(metadata, dict) and isinstance(metadata[S.GOOGLE_BOOKS], dict)
    assert metadata[S.GOOGLE_BOOKS][S.UNRESOLVED] == C.ONE
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(source_id=S.ONE_2, state=SyncState.FAILED),
    )
    assert db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2) == before
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    db._connection().execute(S.QUEUE_TEST_ATTEMPT_OLD_TIMESTAMP)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == (original,)


def test_title_only_provider_result_stays_unresolved(db: Database) -> None:
    publish(db, snapshot(book(isbns=())))
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=S.ONE_2, state=SyncState.COMPLETE, candidates=(metadata_candidate(),)
        ),
    )
    assert db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2) == ()
    assert (
        rows(db, S.TEST_STORAGE_TITLE_ONLY_PROVIDER_KIND_FROM_ENRICHMENT_CANDIDATES)[C.ZERO][C.ZERO]
        == S.LIKELY
    )


def test_optional_provider_failure_keeps_confirmed_fields_and_failure_evidence(
    db: Database,
) -> None:
    original = book()
    publish(db, snapshot(original))
    candidate = metadata_candidate()
    failed = candidate.observations[C.ZERO].model_copy(
        update={S.FIELD: S.COMMUNITY_RATING, S.VALUE: C.NONE, S.STATE: FieldState.FAILED}
    )
    candidate = candidate.model_copy(update={S.OBSERVATIONS: (*candidate.observations, failed)})
    result = EnrichmentResult(
        source_id=original.source_id,
        state=SyncState.PARTIAL,
        candidates=(candidate,),
        issues=(Issue(code=S.INVALID_METADATA_FIELD, message=S.COMMUNITY_RATING),),
    )
    db.save_enrichment(original.source, Source.GOOGLE_BOOKS, result)
    selected = db.metadata_for(original.source, S.READER, original.source_id)
    assert selected[C.ZERO][S.CANDIDATE] == candidate.model_dump(mode=S.JSON)
    assert db.active_records() == (original,)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    db.save_enrichment(original.source, Source.GOOGLE_BOOKS, result)
    repeated = db.metadata_for(original.source, S.READER, original.source_id)
    assert repeated[C.ZERO][S.CANDIDATE] == selected[C.ZERO][S.CANDIDATE]


def test_failed_optional_work_details_publish_confirmed_search_fields_not_search_blockers(
    db: Database,
) -> None:
    original = book()
    publish(db, snapshot(original))
    payload = json.loads(fixture_path(S.METADATA, S.OPEN_LIBRARY_JSON).read_text(encoding=S.UTF_8))
    http = FakeHttp(
        response(payload),
        work_response({}, status=C.OPEN_LIBRARY_HTTP_PAYLOAD_CODE),
    )
    result = OpenLibraryProvider(http, work_details=C.TRUE).lookup(original)
    assert result.state == SyncState.PARTIAL
    assert {issue.code for issue in result.issues} == {S.META_COVERAGE_DETAIL_FAILED}
    for code in C.META_COVERAGE_TEST_BLOCKING_ISSUES:
        db.save_enrichment(
            original.source,
            Source.OPEN_LIBRARY,
            result.model_copy(
                update={
                    S.ISSUES: (*result.issues, Issue(code=code, message=code)),
                }
            ),
        )
        assert not db.metadata_for(original.source, S.READER, original.source_id)
    db.save_enrichment(original.source, Source.OPEN_LIBRARY, result)
    selected = db.metadata_for(original.source, S.READER, original.source_id)
    assert selected[C.ZERO][S.CANDIDATE] == result.candidates[C.ZERO].model_dump(mode=S.JSON)
    fields = {item.field: item for item in result.candidates[C.ZERO].observations}
    assert fields[S.GENRES].state == FieldState.PRESENT
    assert fields[S.GENRES].value == payload[S.DOCS][C.ZERO][S.SUBJECT]
    assert fields[S.FIRST_PUBLICATION_YEAR].state == FieldState.PRESENT
    assert fields[S.ISBNS].state == FieldState.PRESENT
    assert fields[S.DESCRIPTION].state == FieldState.FAILED
    assert db.active_records() == (original,)


@pytest.mark.parametrize(S.META_COVERAGE_TEST_ISSUE_CODE, C.META_COVERAGE_TEST_BLOCKING_ISSUES)
def test_optional_recovery_does_not_allow_incomplete_or_unverified_search(
    db: Database, issue_code: str
) -> None:
    publish(db, snapshot(book()))
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=S.ONE_2,
            state=SyncState.PARTIAL,
            candidates=(metadata_candidate(),),
            issues=(
                Issue(code=S.INVALID_METADATA_FIELD, message=S.ISBNS),
                Issue(code=issue_code, message=issue_code),
            ),
        ),
    )
    assert not db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2)


def test_optional_recovery_still_rejects_ambiguous_missing_and_conflicting_identity(
    db: Database,
) -> None:
    publish(db, snapshot(book()))
    first = metadata_candidate()
    candidates = (
        (first, metadata_candidate(provider_id=S.SECOND, edition_id=S.SECOND)),
        (metadata_candidate(isbns=()),),
        (metadata_candidate(title=S.SECOND),),
    )
    for alternatives in candidates:
        db.save_enrichment(
            Source.STORYGRAPH,
            Source.GOOGLE_BOOKS,
            EnrichmentResult(
                source_id=S.ONE_2,
                state=SyncState.PARTIAL,
                candidates=alternatives,
                issues=(Issue(code=S.INVALID_METADATA_FIELD, message=S.ISBNS),),
            ),
        )
        assert not db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2)


@pytest.mark.parametrize(S.META_COVERAGE_TEST_FAILED_FIELD, (S.PROVIDER_ID, S.TITLE, S.AUTHORS))
def test_optional_recovery_cannot_hide_a_failed_identity_observation(
    db: Database, failed_field: str
) -> None:
    publish(db, snapshot(book()))
    candidate = metadata_candidate()
    failed = candidate.observations[C.ZERO].model_copy(
        update={S.FIELD: failed_field, S.VALUE: C.NONE, S.STATE: FieldState.FAILED}
    )
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=S.ONE_2,
            state=SyncState.PARTIAL,
            candidates=(candidate.model_copy(update={S.OBSERVATIONS: (failed,)}),),
            issues=(Issue(code=S.INVALID_METADATA_FIELD, message=failed_field),),
        ),
    )
    assert not db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2)


def test_provider_reader_fields_are_quarantined_not_used_as_personal_data(db: Database) -> None:
    original = book(
        observations=(
            rating(C.TEST_PROVIDER_READER_FIELDS_ARE_PERSONAL_DATA_ORIGINAL_OBSERVATIONS),
        )
    )
    publish(db, snapshot(original))
    candidate = metadata_candidate(observations=(rating(C.ONE),))
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(source_id=S.ONE_2, state=SyncState.COMPLETE, candidates=(candidate,)),
    )
    assert db.active_records() == (original,)
    assert db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2) == ()
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    assert (
        len(rows(db, S.TEST_STORAGE_PROVIDER_READER_FIELDS_ARE_SELECT_ID_FROM_METADATA_OBS))
        == C.ONE
    )


def test_metadata_refresh_tracks_identity_not_rating_or_status_and_is_bounded(db: Database) -> None:
    original = book(observations=(rating(C.FOUR),))
    publish(db, snapshot(original))
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ZERO) == ()
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (original,)
    db.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=S.ONE_2, state=SyncState.COMPLETE, candidates=(metadata_candidate(),)
        ),
    )
    publish(db, snapshot(book(observations=(rating(C.FIVE),))))
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, max_age_days=C.ZERO) == ()
    db._connection().execute(S.QUEUE_TEST_ATTEMPT_OLD_TIMESTAMP)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    updated = book(status=ReadingStatus.TO_READ, observations=(rating(C.FIVE),))
    newly_added = book(source_id=S.TWO_2)
    publish(db, snapshot(updated, newly_added))
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == (newly_added,)
    assert (
        db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2)[C.ZERO][S.STALE_IDENTITY] is C.FALSE
    )
    renamed = book(title=S.TEST_METADATA_REFRESH_TRACKS_IDENTITY_TITLE_MATILDA_A_DIFFERENT_EDIT)
    publish(db, snapshot(renamed))
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == (renamed,)
    assert db.metadata_for(Source.STORYGRAPH, S.READER, S.ONE_2)[C.ZERO][S.STALE_IDENTITY] is C.TRUE
    with pytest.raises(ValueError, match=S.NEGATIVE):
        db.enrichment_targets(Source.GOOGLE_BOOKS, limit=-C.ONE)
    with pytest.raises(ValueError, match=S.NEGATIVE):
        db.enrichment_targets(Source.GOOGLE_BOOKS, max_age_days=-C.ONE)


def test_provider_and_target_mismatch_are_rejected_without_writes(db: Database) -> None:
    publish(db, snapshot(book()))
    result = EnrichmentResult(source_id=S.MISSING, state=SyncState.COMPLETE)
    with pytest.raises(
        ValueError, match=S.TEST_STORAGE_PROVIDER_AND_TARGET_WRITES_MATCH_NOT_BEEN_PUBLISHED
    ):
        db.save_enrichment(Source.STORYGRAPH, Source.GOOGLE_BOOKS, result)
    result = EnrichmentResult(
        source_id=S.ONE_2, state=SyncState.COMPLETE, candidates=(metadata_candidate(),)
    )
    with pytest.raises(
        ValueError, match=S.TEST_STORAGE_PROVIDER_AND_TARGET_WRITES_MATCH_ANOTHER_PROVIDER
    ):
        db.save_enrichment(Source.STORYGRAPH, Source.OPEN_LIBRARY, result)
    assert rows(db, S.TEST_STORAGE_PROVIDER_AND_TARGET_SELECT_ID_FROM_ENRICHMENT_ATTEMPTS) == []


@pytest.mark.parametrize(S.TEST_STORAGE_RETRY_STATE, [SyncState.FAILED, SyncState.PARTIAL])
def test_bounded_metadata_runs_progress_past_a_persistent_failure(
    db: Database, retry_state: SyncState
) -> None:
    first, later = book(), book(source_id=S.TWO_2)
    publish(db, snapshot(first, later))
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (first,)
    db.save_enrichment(
        first.source,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(source_id=first.source_id, state=retry_state),
    )
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (later,)
    db.save_enrichment(
        later.source,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=later.source_id,
            state=SyncState.COMPLETE,
            candidates=(metadata_candidate(),),
        ),
    )
    assert db.metadata_for(later.source, S.READER, later.source_id)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == ()
    db._connection().execute(S.QUEUE_TEST_ATTEMPT_OLD_TIMESTAMP)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (
        (first,) if retry_state == SyncState.FAILED else ()
    )


def test_due_metadata_retries_rotate_by_attempt_order(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, later = book(), book(source_id=S.TWO_2)
    publish(db, snapshot(first, later))
    now = storage_module._date(S.QUEUE_TEST_FIXED_TIME)
    monkeypatch.setattr(storage_module, S.TEST_STORAGE_FIXED_CLOCK, lambda: now.isoformat())
    for target in (first, later, first):
        assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (target,)
        db.save_enrichment(
            target.source,
            Source.GOOGLE_BOOKS,
            EnrichmentResult(source_id=target.source_id, state=SyncState.FAILED),
        )
        now += timedelta(seconds=C.QUEUE_TRANSIENT_RETRY_SECONDS)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (later,)


@pytest.mark.parametrize(
    S.META_COVERAGE_TEST_ISSUE_CODE,
    (S.INVALID_METADATA_FIELD, S.INSUFFICIENT_IDENTITY, S.UNVERIFIED_CANDIDATES),
)
def test_deterministic_partial_does_not_retry_until_identity_changes(
    db: Database, issue_code: str
) -> None:
    original = book()
    publish(db, snapshot(original))
    db.save_enrichment(
        original.source,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=original.source_id,
            state=SyncState.PARTIAL,
            issues=(Issue(code=issue_code, message=issue_code),),
        ),
    )
    db._connection().execute(S.QUEUE_TEST_ATTEMPT_OLD_TIMESTAMP)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    renamed = book(title=S.TEST_METADATA_REFRESH_TRACKS_IDENTITY_TITLE_MATILDA_A_DIFFERENT_EDIT)
    publish(db, snapshot(renamed))
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == (renamed,)


@pytest.mark.parametrize(S.TEST_STORAGE_RETRY_STATE, (SyncState.FAILED, SyncState.PARTIAL))
def test_retryable_metadata_uses_persisted_due_time_across_restart(
    db: Database, database_path: Path, monkeypatch: pytest.MonkeyPatch, retry_state: SyncState
) -> None:
    original = book()
    publish(db, snapshot(original))
    monkeypatch.setattr(storage_module, S.TEST_STORAGE_FIXED_CLOCK, lambda: S.QUEUE_TEST_FIXED_TIME)
    db.save_enrichment(
        original.source,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=original.source_id,
            state=retry_state,
            issues=(Issue(code=S.METADATA_REQUEST_FAILED, message=S.FAILED, retryable=C.TRUE),),
        ),
    )
    db._connection().execute(S.META_COVERAGE_TEST_OLD_IMPLEMENTATION)
    db.close()
    reopened = Database(database_path)
    try:
        monkeypatch.setattr(
            storage_module, S.TEST_STORAGE_FIXED_CLOCK, lambda: S.QUEUE_TEST_BEFORE_RETRY
        )
        assert reopened.enrichment_targets(Source.GOOGLE_BOOKS) == ()
        monkeypatch.setattr(
            storage_module, S.TEST_STORAGE_FIXED_CLOCK, lambda: S.QUEUE_TEST_RETRY_DUE
        )
        assert reopened.enrichment_targets(Source.GOOGLE_BOOKS) == (original,)
    finally:
        reopened.close()


def test_healthy_no_candidate_result_settles_without_selected_metadata(db: Database) -> None:
    original = book()
    publish(db, snapshot(original))
    db.save_enrichment(
        original.source,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(source_id=original.source_id, state=SyncState.COMPLETE),
    )
    db._connection().execute(S.QUEUE_TEST_ATTEMPT_OLD_TIMESTAMP)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    assert db.metadata_for(original.source, S.READER, original.source_id) == ()


def test_metadata_queue_excludes_records_without_current_membership(db: Database) -> None:
    original = book()
    publish(db, snapshot(original))
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == (original,)
    publish(db, snapshot())
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    assert db.record_history(original.source, S.READER, original.source_id)


@pytest.mark.parametrize(S.TEST_STORAGE_RETRY_STATE, (SyncState.COMPLETE, SyncState.PARTIAL))
def test_parked_unresolved_metadata_is_visible_without_requeueing_and_excludes_inactive(
    db: Database, retry_state: SyncState
) -> None:
    original = book()
    publish(db, snapshot(original))
    first = metadata_candidate()
    candidates = (
        (first, metadata_candidate(provider_id=S.SECOND, edition_id=S.SECOND))
        if retry_state == SyncState.COMPLETE
        else (first,)
    )
    db.save_enrichment(
        original.source,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=original.source_id,
            state=retry_state,
            candidates=candidates,
            issues=(Issue(code=S.INVALID_METADATA_FIELD, message=S.COMMUNITY_RATING),),
        ),
    )

    class Provider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            raise AssertionError

    service = SyncService(db, Settings(), {}, {Source.GOOGLE_BOOKS: Provider()})
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    coverage = db.status()[S.METADATA]
    assert isinstance(coverage, dict)
    google = coverage[S.GOOGLE_BOOKS]
    assert isinstance(google, dict)
    assert google[S.QUEUE_INCOMPLETE] == C.ONE
    assert google[S.SELECTED] == (C.ONE if retry_state == SyncState.PARTIAL else C.ZERO)
    assert google[S.QUEUE_ATTEMPT_STATES] == {retry_state.value: C.ONE}
    receipt = service._metadata(Source.GOOGLE_BOOKS)
    assert receipt.state == SyncState.PARTIAL
    assert receipt.requested == receipt.processed == C.ZERO
    assert receipt.issues[C.ZERO].code == S.QUEUE_NO_LOOKUPS_DUE_CODE
    later = book(source_id=S.TWO_2)
    publish(db, snapshot(original, later))

    class HealthyProvider:
        def lookup(self, book: BookRecord) -> EnrichmentResult:
            assert book.source_id == later.source_id
            return EnrichmentResult(source_id=book.source_id, state=SyncState.COMPLETE)

    service = SyncService(db, Settings(), {}, {Source.GOOGLE_BOOKS: HealthyProvider()})
    receipt = service._metadata(Source.GOOGLE_BOOKS)
    assert receipt.state == SyncState.PARTIAL
    assert receipt.requested == receipt.processed == C.ONE
    assert receipt.issues[C.ZERO].code == S.QUEUE_NO_LOOKUPS_DUE_CODE
    publish(db, snapshot())
    coverage = db.status()[S.METADATA]
    assert isinstance(coverage, dict)
    google = coverage[S.GOOGLE_BOOKS]
    assert isinstance(google, dict)
    assert google[S.ATTEMPTS] == google[S.CANDIDATES] == google[S.SELECTED] == C.ZERO
    assert google[S.UNRESOLVED] == google[S.QUEUE_INCOMPLETE] == C.ZERO
    assert google[S.QUEUE_ATTEMPT_STATES] == {}
    assert service._metadata(Source.GOOGLE_BOOKS).state == SyncState.COMPLETE


def test_identical_replays_share_payloads_without_losing_snapshot_history(db: Database) -> None:
    original = book(observations=(rating(C.FOUR),))
    data = snapshot(original)
    first = publish(db, data)
    count = rows(db, S.STORAGE_PAYLOAD_COUNTS)[C.ZERO][C.ZERO]
    second = publish(db, data)
    assert second.snapshot_id != first.snapshot_id
    assert second.unchanged == C.ONE
    assert rows(db, S.STORAGE_PAYLOAD_COUNTS)[C.ZERO][C.ZERO] == count
    history = db.record_history(original.source, data.account_id, original.source_id)
    assert len(history) == C.TWO
    assert all(item[S.RECORD] == original.model_dump(mode=S.JSON) for item in history)


def test_library_migration_preserves_records_progress_history_and_enrichment(
    db: Database,
    database_path: Path,
) -> None:
    original = book(
        observations=(rating(C.FOUR),),
        reading_events=(
            ReadingEvent(
                finished=PartialDate(value=S.TEST_IMPORT_DATE),
                status=ReadingStatus.READ,
            ),
        ),
    )
    run = db.start_run(S.TEST)
    progress = CollectionProgress(source=original.source, collection=S.LIBRARY, records=(original,))
    db.stage_progress(run, progress)
    data = snapshot(original)
    db.save_snapshot(run, data)
    db.save_enrichment(
        original.source,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=original.source_id,
            state=SyncState.COMPLETE,
            candidates=(metadata_candidate(),),
        ),
    )
    db.finish_run(run, SyncState.COMPLETE)
    before_status = db.status()
    before_history = db.record_history(original.source, data.account_id, original.source_id)
    before_metadata = db.metadata_for(original.source, data.account_id, original.source_id)
    _restore_legacy_layout(db)
    db.close()
    migrated = Database(database_path)
    try:
        assert migrated.active_records() == (original,)
        assert migrated.status() == before_status
        assert (
            migrated.record_history(original.source, data.account_id, original.source_id)
            == before_history
        )
        assert (
            migrated.metadata_for(original.source, data.account_id, original.source_id)
            == before_metadata
        )
        assert migrated.staged_progress(run) == (progress,)
        assert (
            migrated._connection()
            .execute(S.DATABASE_INITIALIZE_VERSION_PRAGMA_USER_VERSION)
            .fetchone()[C.ZERO]
            == C.STORAGE_SCHEMA_VERSION
        )
    finally:
        migrated.close()


def test_damaged_legacy_migration_rolls_back_without_partial_schema_or_payloads(
    db: Database,
    database_path: Path,
) -> None:
    publish(db, snapshot(book()))
    _restore_legacy_layout(db)
    db._connection().execute(S.TEST_STORAGE_CORRUPT_LEGACY)
    db.close()
    migrated = Database(database_path)
    with pytest.raises(PayloadIntegrityError, match=S.STORAGE_PAYLOAD_DAMAGED):
        migrated.initialize()
    with closing(sqlite3.connect(database_path)) as connection:
        assert (
            connection.execute(S.DATABASE_INITIALIZE_VERSION_PRAGMA_USER_VERSION).fetchone()[C.ZERO]
            == C.STORAGE_LEGACY_VERSION
        )
        assert connection.execute(S.TEST_STORAGE_PAYLOAD_TABLE_COUNT).fetchone()[C.ZERO] == C.ZERO


@pytest.mark.parametrize(S.TEST_STORAGE_RETRY_STATE, (SyncState.COMPLETE, SyncState.PARTIAL))
def test_provider_implementation_change_refreshes_an_otherwise_fresh_attempt(
    db: Database, retry_state: SyncState
) -> None:
    original = book()
    publish(db, snapshot(original))
    result = EnrichmentResult(
        source_id=original.source_id,
        state=retry_state,
        candidates=(metadata_candidate(),),
    )
    db.save_enrichment(original.source, Source.GOOGLE_BOOKS, result)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    db._connection().execute(S.META_COVERAGE_TEST_OLD_IMPLEMENTATION)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == (original,)
    db.save_enrichment(original.source, Source.GOOGLE_BOOKS, result)
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == ()


def test_schema_two_migration_keeps_selected_metadata_and_marks_old_parser_for_refresh(
    db: Database, database_path: Path
) -> None:
    original = book()
    publish(db, snapshot(original))
    db.save_enrichment(
        original.source,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=original.source_id,
            state=SyncState.COMPLETE,
            candidates=(metadata_candidate(),),
        ),
    )
    before = db.metadata_for(original.source, S.READER, original.source_id)
    db._connection().execute(S.META_COVERAGE_TEST_DROP_IMPLEMENTATION)
    db._connection().execute(S.META_COVERAGE_TEST_SCHEMA_TWO)
    db.close()
    migrated = Database(database_path)
    try:
        assert migrated.metadata_for(original.source, S.READER, original.source_id) == before
        assert migrated.active_records() == (original,)
        assert migrated.enrichment_targets(Source.GOOGLE_BOOKS) == (original,)
    finally:
        migrated.close()
