from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from bookystats import constants as C
from bookystats import storage as storage_module
from bookystats import strings as S
from bookystats.models import (
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    EnrichmentResult,
    FieldState,
    MetadataCandidate,
    Observation,
    PartialDate,
    PublicationResult,
    ReadingEvent,
    ReadingStatus,
    Source,
    SyncState,
)
from bookystats.storage import AccountMismatchError, Database, SnapshotRejectedError


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
        (S.USER_VERSION, C.ONE),
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
    assert db.enrichment_targets(Source.GOOGLE_BOOKS) == (original,)
    assert (
        len(rows(db, S.TEST_STORAGE_PROVIDER_READER_FIELDS_ARE_SELECT_ID_FROM_METADATA_OBS))
        == C.ONE
    )


def test_metadata_refresh_tracks_identity_not_current_rating_and_is_bounded(db: Database) -> None:
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
    assert len(db.enrichment_targets(Source.GOOGLE_BOOKS, max_age_days=C.ZERO)) == C.ONE
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
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (first,)


def test_metadata_retries_rotate_by_attempt_order_even_when_timestamps_tie(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, later = book(), book(source_id=S.TWO_2)
    publish(db, snapshot(first, later))
    now = storage_module.utc_now()
    monkeypatch.setattr(storage_module, S.TEST_STORAGE_FIXED_CLOCK, lambda: now)
    for target in (first, later, first):
        assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (target,)
        db.save_enrichment(
            target.source,
            Source.GOOGLE_BOOKS,
            EnrichmentResult(source_id=target.source_id, state=SyncState.FAILED),
        )
    assert db.enrichment_targets(Source.GOOGLE_BOOKS, limit=C.ONE) == (later,)
