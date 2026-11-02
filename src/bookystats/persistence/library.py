from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalysisInput, AnalyticsSettings
from bookystats.domain.errors import AccountMismatchError as AccountMismatchError
from bookystats.domain.errors import SnapshotRejectedError as SnapshotRejectedError
from bookystats.domain.identifiers import normalized_isbns, normalized_text
from bookystats.domain.matching import (
    MatchKind,
    MatchResult,
    candidate_title_author_key,
    compare_books,
    edition_identity_facts,
    select_metadata_candidate,
    title_author_key,
    work_bibliography_compatible,
)
from bookystats.domain.models import (
    Account,
    BookRecord,
    CollectionProgress,
    CollectionSnapshot,
    EnrichmentResult,
    FieldState,
    MetadataCandidate,
    PublicationResult,
    ReadingEvent,
    ReadingStatus,
    Source,
    SyncState,
    utc_now,
)
from bookystats.persistence.payloads import PayloadStore
from bookystats.persistence.payloads import canonical_json as _json


@C.frozen_dataclass
class _ProviderWorkProof:
    work_id: str
    attempt_id: int
    candidate_id: int
    identity_hash: str
    book: BookRecord


def _parsed_json(value: str) -> JsonValue:
    return cast(JsonValue, json.loads(value))


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode(S.UTF_8)).hexdigest()


def _date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace(S.Z, S.DATES_PARSE_DATE_PARSED_TEXT))
    if parsed.tzinfo is C.NONE:
        raise ValueError(S.STORAGE_DATE_SNAPSHOT_TIMESTAMPS_MUST_INCLUDE_A_TIMEZONE)
    return parsed.astimezone(UTC)


def _event_payload(event: ReadingEvent) -> dict[str, JsonValue]:
    return {
        S.SOURCE_EVENT_ID: event.source_event_id,
        S.STARTED: event.started.value if event.started else C.NONE,
        S.FINISHED: event.finished.value if event.finished else C.NONE,
        S.STATUS: event.status.value,
    }


def _event_key(event: ReadingEvent, occurrence: int = C.ONE) -> str:
    if event.source_event_id is not C.NONE:
        return S.STORAGE_EVENT_KEY_ID + event.source_event_id
    key = S.STORAGE_EVENT_KEY_ANONYMOUS + _digest(_event_payload(event))
    # Keep occurrence one compatible with already-persisted anonymous keys.
    if occurrence == C.ONE:
        return key
    return S.STORAGE_EVENT_OCCURRENCE_KEY.format(key=key, occurrence=occurrence)


def _reading_occurrences(events: tuple[ReadingEvent, ...]) -> dict[str, ReadingEvent]:
    occurrences: dict[str, int] = {}
    result: dict[str, ReadingEvent] = {}
    for event in events:
        key = _event_key(event)
        if event.source_event_id is C.NONE:
            occurrences[key] = occurrences.get(key, C.ZERO) + C.ONE
            key = _event_key(event, occurrences[key])
        elif key in result and _event_payload(result[key]) != _event_payload(event):
            raise ValueError(S.STORAGE_DATABASE_SAVE_READINGS_A_READING_EVENT_ID_HAS_CONFLICTING)
        result[key] = event
    return result


def _semantic_hash(book: BookRecord) -> str:
    payload = book.model_dump(mode=S.JSON)
    payload.pop(S.DETAIL_CHECKED_AT, C.NONE)
    if book.added_at:
        payload[S.ADDED_AT] = book.added_at.value
    observations = []
    for item in book.observations:
        observation = item.model_dump(mode=S.JSON)
        observation.pop(S.OBSERVED_AT, C.NONE)
        observations.append(observation)
    payload[S.OBSERVATIONS] = sorted(observations, key=_json)
    payload[S.READING_EVENTS] = sorted(
        _json(_event_payload(event)) for event in _reading_occurrences(book.reading_events).values()
    )
    payload[S.SHELVES] = sorted(set(book.shelves))
    payload[S.COLLECTIONS] = sorted(set(book.collections))
    return _digest(payload)


def _identity_hash(book: BookRecord) -> str:
    payload: dict[str, object] = {
        S.TITLE_AUTHOR: title_author_key(book),
        S.TITLE: book.title,
        S.AUTHORS: book.authors,
        S.ISBNS: normalized_isbns(book.isbns),
        S.LANGUAGE: book.language,
        S.EDITION_FORMAT: book.edition_format,
    }
    observed: dict[str, list[str]] = {}
    for field, facts in edition_identity_facts(book).items():
        if value := getattr(book, field):
            facts = facts - {normalized_text(value)}
        if facts:
            observed[field] = sorted(facts)
    # Preserve existing hashes when observations only repeat the scalar edition facts.
    if observed:
        payload[S.OBSERVATIONS] = observed
    return _digest(payload)


def _insert_id(cursor: sqlite3.Cursor) -> int:
    if cursor.lastrowid is C.NONE:
        raise RuntimeError(S.STORAGE_INSERT_ID_SQLITE_DID_NOT_RETURN_AN_INSERTED_ROW)
    return cursor.lastrowid


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = C.NONE
        self._payload_store: PayloadStore | None = C.NONE

    def initialize(self) -> None:
        if self._conn is not C.NONE:
            return
        self.path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
        connection = sqlite3.connect(str(self.path), timeout=C.FIVE, isolation_level=C.NONE)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute(S.STORAGE_DATABASE_INITIALIZE_PRAGMA_FOREIGN_KEYS_ON)
            connection.execute(S.STORAGE_DATABASE_INITIALIZE_PRAGMA_BUSY_TIMEOUT)
            version = int(
                connection.execute(S.DATABASE_INITIALIZE_VERSION_PRAGMA_USER_VERSION).fetchone()[
                    C.ZERO
                ]
            )
            application_id = int(
                connection.execute(
                    S.DATABASE_INITIALIZE_APPLICATION_ID_PRAGMA_APPLICATION_ID
                ).fetchone()[C.ZERO]
            )
            if version not in (
                C.ZERO,
                C.STORAGE_LEGACY_VERSION,
                C.META_COVERAGE_PRIOR_SCHEMA_VERSION,
                C.STORAGE_SCHEMA_VERSION,
            ) or application_id not in (
                C.ZERO,
                C.STORAGE_APPLICATION_ID,
            ):
                raise RuntimeError(
                    S.STORAGE_DATABASE_INITIALIZE_UNSUPPORTED_BOOKYSTATS_DATABASE_SCHEMA
                )
            connection.execute(S.STORAGE_DATABASE_INITIALIZE_PRAGMA_JOURNAL_MODE_WAL)
            migrated = C.FALSE
            if version in (
                C.ZERO,
                C.STORAGE_LEGACY_VERSION,
                C.META_COVERAGE_PRIOR_SCHEMA_VERSION,
            ):
                connection.execute(S.STORAGE_DATABASE_INITIALIZE_BEGIN_IMMEDIATE)
                locked_version = int(
                    connection.execute(
                        S.DATABASE_INITIALIZE_VERSION_PRAGMA_USER_VERSION
                    ).fetchone()[C.ZERO]
                )
                if locked_version == C.ZERO:
                    tables = connection.execute(
                        S.DATABASE_INITIALIZE_TABLES_SELECT_NAME_FROM_SQLITE_MASTER_WHERE_TYPE
                    ).fetchall()
                    if tables:
                        raise RuntimeError(
                            S.STORAGE_DATABASE_INITIALIZE_REFUSING_UNRECOGNIZED_NONEMPTY_DATABASE
                        )
                    for (
                        statement
                    ) in S.STORAGE_SCHEMA_CREATE_TABLE_RUNS_ID_INTEGER_PRIMARY_KEY.split(
                        S.GOOGLE_BOOKS_HTTP_PAYLOAD_CONTENT_TYPE_TEXT
                    ):
                        if statement.strip():
                            connection.execute(statement)
                    connection.execute(
                        S.STORAGE_DATABASE_INITIALIZE_TEMPLATE.format(v0=C.STORAGE_APPLICATION_ID)
                    )
                    connection.execute(S.STORAGE_PAYLOAD_SCHEMA)
                elif locked_version == C.STORAGE_LEGACY_VERSION:
                    connection.execute(S.STORAGE_PAYLOAD_SCHEMA)
                    payloads = PayloadStore(connection)
                    for select, update, collection in C.STORAGE_PAYLOAD_MIGRATIONS:
                        cursor = connection.execute(select)
                        while batch := cursor.fetchmany(C.STORAGE_MIGRATION_BATCH_SIZE):
                            for row in batch:
                                reference = (
                                    payloads.save_collection_json(row[C.ONE])
                                    if collection
                                    else payloads.save_json(row[C.ONE])
                                )
                                connection.execute(update, (reference, row[C.ZERO]))
                    migrated = C.TRUE
                elif locked_version not in (
                    C.META_COVERAGE_PRIOR_SCHEMA_VERSION,
                    C.STORAGE_SCHEMA_VERSION,
                ):
                    raise RuntimeError(
                        S.STORAGE_DATABASE_INITIALIZE_UNSUPPORTED_BOOKYSTATS_DATABASE_SCHEMA
                    )
                if S.META_COVERAGE_IMPLEMENTATION_COLUMN not in {
                    row[C.ONE] for row in connection.execute(S.META_COVERAGE_ATTEMPT_COLUMNS)
                }:
                    connection.execute(S.META_COVERAGE_MIGRATE_IMPLEMENTATION)
                connection.execute(
                    S.STORAGE_DATABASE_INITIALIZE_TEMPLATE_2.format(v0=C.STORAGE_SCHEMA_VERSION)
                )
                connection.execute(S.COMMIT)
            if migrated:
                # Reclaim the replaced JSON pages, without deleting any captured history.
                connection.execute(S.STORAGE_CHECKPOINT)
                connection.execute(S.STORAGE_COMPACT)
        except BaseException:
            connection.close()
            raise
        self._conn = connection
        self._payload_store = PayloadStore(connection)

    def close(self) -> None:
        if self._conn is not C.NONE:
            self._conn.close()
            self._conn = C.NONE
            self._payload_store = C.NONE

    def _connection(self) -> sqlite3.Connection:
        self.initialize()
        assert self._conn is not C.NONE
        return self._conn

    def _payloads(self) -> PayloadStore:
        self.initialize()
        assert self._payload_store is not C.NONE
        return self._payload_store

    @contextmanager
    def _transaction(self, *, write: bool = C.TRUE) -> Iterator[sqlite3.Connection]:
        connection = self._connection()
        connection.execute(S.STORAGE_DATABASE_INITIALIZE_BEGIN_IMMEDIATE if write else S.BEGIN)
        try:
            yield connection
            connection.execute(S.COMMIT)
        except BaseException:
            if connection.in_transaction:
                connection.execute(S.ROLLBACK)
            raise

    @staticmethod
    def _open_run(connection: sqlite3.Connection, run_id: int) -> None:
        row = connection.execute(
            S.DATABASE_OPEN_RUN_ROW_SELECT_FINISHED_AT_FROM_RUNS_WHERE_ID, (run_id,)
        ).fetchone()
        if row is C.NONE:
            raise ValueError(S.STORAGE_DATABASE_OPEN_RUN_UNKNOWN_INGESTION_RUN)
        if row[S.FINISHED_AT] is not C.NONE:
            raise ValueError(S.STORAGE_DATABASE_OPEN_RUN_THE_INGESTION_RUN_IS_ALREADY_FINISHED)

    def start_run(self, trigger: str) -> int:
        if not trigger.strip():
            raise ValueError(S.STORAGE_DATABASE_START_RUN_A_RUN_TRIGGER_IS_REQUIRED)
        with self._transaction() as connection:
            return _insert_id(
                connection.execute(
                    S.STORAGE_DATABASE_START_RUN_INSERT_INTO_RUNS_TRIGGER_STATE_STARTED_AT,
                    (trigger, SyncState.PARTIAL.value, utc_now()),
                )
            )

    def stage_progress(self, run_id: int, progress: CollectionProgress) -> None:
        progress = CollectionProgress.model_validate(progress.model_dump())
        if progress.source not in C.STORAGE_READER_SOURCES or not progress.collection.strip():
            raise ValueError(S.STORAGE_DATABASE_STAGE_PROGRESS_PROGRESS_A_READER_SOURCE_AND_A)
        if any(book.source != progress.source for book in progress.records):
            raise ValueError(S.STORAGE_DATABASE_STAGE_PROGRESS_PROGRESS_RECORDS_FROM_ANOTHER_SOURCE)
        now = utc_now()
        with self._transaction() as connection:
            self._open_run(connection, run_id)
            connection.execute(
                S.STORAGE_DATABASE_STAGE_PROGRESS_INSERT_RUN_ID_SOURCE_COLLECTION,
                (
                    run_id,
                    progress.source.value,
                    progress.collection,
                    now,
                    self._payloads().save_collection_json(progress.model_dump_json()),
                ),
            )
            connection.execute(
                S.STORAGE_DATABASE_STAGE_PROGRESS_UPDATE_SET_STATE_LAST_ATTEMPT,
                (
                    SyncState.PARTIAL.value,
                    now,
                    progress.source.value,
                    progress.collection,
                    progress.source.value,
                ),
            )

    def _raw_snapshot(
        self, connection: sqlite3.Connection, run_id: int, snapshot: CollectionSnapshot
    ) -> int:
        snapshot_id = _insert_id(
            connection.execute(
                S.DATABASE_RAW_SNAPSHOT_SNAPSHOT_ID_SNAPSHOTS_RUN_ID_SOURCE_ACCOUNT,
                (
                    run_id,
                    snapshot.source.value,
                    snapshot.account_id,
                    snapshot.collection,
                    snapshot.state.value,
                    _date(snapshot.started_at).isoformat(),
                    _date(snapshot.finished_at).isoformat(),
                    self._payloads().save_collection_json(snapshot.model_dump_json()),
                ),
            )
        )
        for book in snapshot.records:
            snapshot_record_id = _insert_id(
                connection.execute(
                    S.DATABASE_RAW_SNAPSHOT_SNAPSHOT_RECORD_RECORDS_SNAPSHOT_ID_SOURCE,
                    (
                        snapshot_id,
                        book.source_id,
                        self._payloads().save_json(book.model_dump_json()),
                    ),
                )
            )
            connection.executemany(
                S.STORAGE_DATABASE_RAW_SNAPSHOT_INSERT_SNAPSHOT_RECORD_ID_FIELD,
                [
                    (
                        snapshot_record_id,
                        item.field,
                        item.state.value,
                        item.scope,
                        _json(item.value),
                        item.source_url,
                        item.observed_at,
                    )
                    for item in book.observations
                ],
            )
        return snapshot_id

    def save_snapshot(self, run_id: int, snapshot: CollectionSnapshot) -> PublicationResult | None:
        snapshot = CollectionSnapshot.model_validate(snapshot.model_dump())
        if (
            snapshot.source not in C.STORAGE_READER_SOURCES
            or not snapshot.account_id.strip()
            or (not snapshot.collection.strip())
        ):
            raise ValueError(S.STORAGE_DATABASE_SAVE_SNAPSHOT_A_REQUIRES_A_READER_SOURCE_ACCOUNT)
        if _date(snapshot.started_at) > _date(snapshot.finished_at):
            raise ValueError(S.STORAGE_DATABASE_SAVE_SNAPSHOT_SNAPSHOT_START_IS_AFTER_ITS_FINISH)
        rejection: SnapshotRejectedError | None = C.NONE
        result: PublicationResult | None = C.NONE
        with self._transaction() as connection:
            self._open_run(connection, run_id)
            snapshot_id = self._raw_snapshot(connection, run_id, snapshot)
            binding = connection.execute(
                S.DATABASE_SAVE_SNAPSHOT_BINDING_SELECT_ID_FROM_SOURCE_ACCOUNTS_WHERE,
                (snapshot.source.value,),
            ).fetchone()
            if binding is not C.NONE and binding[S.ACCOUNT_ID] != snapshot.account_id:
                rejection = AccountMismatchError(
                    S.DATABASE_SAVE_SNAPSHOT_REJECTION_SOURCE_USE_AN_EXPLICIT_RECONNECT
                )
            previous = connection.execute(
                S.DATABASE_SAVE_SNAPSHOT_PREVIOUS_SELECT_AT_FROM_SOURCE_COLLECTIONS,
                (snapshot.source.value, snapshot.account_id, snapshot.collection),
            ).fetchone()
            if (
                rejection is C.NONE
                and snapshot.state == SyncState.COMPLETE
                and (previous is not C.NONE)
                and (_date(snapshot.started_at) < _date(previous[S.STARTED_AT]))
            ):
                rejection = SnapshotRejectedError(
                    S.DATABASE_SAVE_SNAPSHOT_REJECTION_A_SNAPSHOT_IS_ALREADY_ACTIVE
                )
            state = SyncState.FAILED if rejection is not C.NONE else snapshot.state
            connection.execute(
                S.STORAGE_DATABASE_SAVE_SNAPSHOT_INSERT_COLLECTIONS_SOURCE_ACCOUNT_ID,
                (
                    snapshot.source.value,
                    snapshot.account_id,
                    snapshot.collection,
                    state.value,
                    _date(snapshot.finished_at).isoformat(),
                    snapshot_id,
                    _json(snapshot.capabilities),
                ),
            )
            if rejection is not C.NONE:
                connection.execute(
                    S.STORAGE_DATABASE_SAVE_SNAPSHOT_UPDATE_SET_REJECTION_REASON_WHERE_ID,
                    (str(rejection), snapshot_id),
                )
            elif snapshot.state == SyncState.COMPLETE:
                connection.execute(
                    S.STORAGE_DATABASE_SAVE_SNAPSHOT_INSERT_ACCOUNTS_SOURCE_ACCOUNT_ID,
                    (snapshot.source.value, snapshot.account_id),
                )
                result = self._publish(connection, snapshot_id, snapshot)
        if rejection is not C.NONE:
            raise rejection
        return result

    def _publish(
        self, connection: sqlite3.Connection, snapshot_id: int, snapshot: CollectionSnapshot
    ) -> PublicationResult:
        self._refresh_matching_index(connection)
        collection_id = int(
            connection.execute(
                S.DATABASE_PUBLISH_COLLECTION_ID_SOURCE_COLLECTIONS_WHERE_SOURCE,
                (snapshot.source.value, snapshot.account_id, snapshot.collection),
            ).fetchone()[S.ID]
        )
        prior_members = {
            int(row[S.RECORD_ID])
            for row in connection.execute(
                S.DATABASE_PUBLISH_PRIOR_MEMBERS_FROM_MEMBERSHIPS_WHERE_COLLECTION, (collection_id,)
            )
        }
        added = updated = unchanged = C.ZERO
        now = _date(snapshot.finished_at).isoformat()
        isbn_records: dict[str, list[BookRecord]] = {}
        contested_isbns: set[str] = set()
        for book in snapshot.records:
            for isbn in normalized_isbns(book.isbns):
                peers = isbn_records.setdefault(isbn, [])
                if any(compare_books(book, peer).kind != MatchKind.CONFIRMED for peer in peers):
                    contested_isbns.add(isbn)
                peers.append(book)
        for book in snapshot.records:
            record_id, changed = self._save_record(
                connection, snapshot_id, snapshot, book, contested_isbns
            )
            if record_id not in prior_members:
                added += C.ONE
            elif changed:
                updated += C.ONE
            else:
                unchanged += C.ONE
            connection.execute(
                S.STORAGE_DATABASE_PUBLISH_UPDATE_SNAPSHOT_RECORDS_SET_RECORD_ID_WHERE,
                (record_id, snapshot_id, book.source_id),
            )
            connection.execute(
                S.STORAGE_DATABASE_PUBLISH_INSERT_INTO_COLLECTION_ID_RECORD_ID,
                (collection_id, record_id, snapshot.source.value, snapshot.account_id, now, now),
            )
            self._save_readings(connection, record_id, snapshot_id, book, now)
        removed = connection.execute(
            S.DATABASE_PUBLISH_REMOVED_DELETE_FROM_WHERE_COLLECTION_ID_AND,
            (collection_id, snapshot_id),
        ).rowcount
        connection.execute(
            S.STORAGE_DATABASE_PUBLISH_UPDATE_SNAPSHOTS_SET_PUBLISHED_WHERE_ID, (snapshot_id,)
        )
        connection.execute(
            S.STORAGE_DATABASE_PUBLISH_UPDATE_SOURCE_SET_ACTIVE_SNAPSHOT_ID,
            (snapshot_id, now, _json(snapshot.capabilities), collection_id),
        )
        unresolved = int(
            connection.execute(
                S.DATABASE_PUBLISH_UNRESOLVED_SELECT_COUNT_FROM_SOURCE_RECORDS_R_JOIN,
                (snapshot_id,),
            ).fetchone()[C.ZERO]
        )
        return PublicationResult(
            snapshot_id=snapshot_id,
            added=added,
            updated=updated,
            unchanged=unchanged,
            removed=removed,
            unresolved=unresolved,
            issues=snapshot.issues,
        )

    @staticmethod
    def _new_identity(connection: sqlite3.Connection, now: str) -> tuple[int, int]:
        work_id = _insert_id(
            connection.execute(
                S.DATABASE_NEW_IDENTITY_WORK_ID_INSERT_INTO_WORKS_CREATED_AT_VALUES, (now,)
            )
        )
        edition_id = _insert_id(
            connection.execute(
                S.DATABASE_NEW_IDENTITY_EDITION_ID_INSERT_EDITIONS_WORK_ID_CREATED_AT,
                (work_id, now),
            )
        )
        return (work_id, edition_id)

    @staticmethod
    def _refresh_matching_index(connection: sqlite3.Connection) -> None:
        payloads = PayloadStore(connection)
        updates = []
        for row in connection.execute(S.MATCH_UPGRADE_INDEX_ROWS):
            book = BookRecord.model_validate_json(payloads.load_text(row[S.LATEST_JSON]))
            key = candidate_title_author_key(book)
            if key != row[S.MATCH_UPGRADE_INDEX_KEY]:
                updates.append((key, row[S.ID]))
        connection.executemany(S.MATCH_UPGRADE_INDEX_UPDATE, updates)

    @staticmethod
    def _comparison_rows(
        connection: sqlite3.Connection, record_id: int, book: BookRecord
    ) -> list[sqlite3.Row]:
        ids: set[int] = set()
        key = candidate_title_author_key(book)
        if key:
            ids.update(
                int(row[S.ID])
                for row in connection.execute(
                    S.STORAGE_DATABASE_COMPARISON_ROWS_SELECT_SOURCE_RECORDS_WHERE_TITLE, (key,)
                )
            )
        for isbn in normalized_isbns(book.isbns):
            ids.update(
                int(row[S.RECORD_ID])
                for row in connection.execute(
                    S.STORAGE_DATABASE_COMPARISON_ROWS_FROM_RECORD_IDENTIFIERS_WHERE, (isbn,)
                )
            )
        for row in connection.execute(
            S.STORAGE_DATABASE_COMPARISON_ROWS_SELECT_ID_TARGET_RECORD_ID_FROM,
            (record_id, record_id),
        ):
            ids.add(int(row[S.RECORD_ID]))
            ids.add(int(row[S.TARGET_RECORD_ID]))
        ids.discard(record_id)
        return [
            connection.execute(
                S.STORAGE_DATABASE_COMPARISON_ROWS_SELECT_FROM_SOURCE_RECORDS_WHERE_ID, (other_id,)
            ).fetchone()
            for other_id in sorted(ids)
        ]

    def _save_record(
        self,
        connection: sqlite3.Connection,
        snapshot_id: int,
        snapshot: CollectionSnapshot,
        book: BookRecord,
        contested_isbns: set[str],
    ) -> tuple[int, bool]:
        old = connection.execute(
            S.DATABASE_SAVE_RECORD_OLD_SELECT_FROM_SOURCE_RECORDS_WHERE_SOURCE_AND,
            (book.source.value, snapshot.account_id, book.source_id),
        ).fetchone()
        now = _date(snapshot.finished_at).isoformat()
        semantic_hash = _semantic_hash(book)
        if old is C.NONE:
            prior_work_id, prior_edition_id = self._new_identity(connection, now)
            record_id = _insert_id(
                connection.execute(
                    S.DATABASE_SAVE_RECORD_RECORD_ID_SOURCE_RECORDS_SOURCE_ACCOUNT_ID,
                    (
                        book.source.value,
                        snapshot.account_id,
                        book.source_id,
                        prior_work_id,
                        prior_edition_id,
                        S.UNRESOLVED,
                        candidate_title_author_key(book),
                        semantic_hash,
                        _identity_hash(book),
                        self._payloads().save_json(book.model_dump_json()),
                        now,
                        now,
                        snapshot_id,
                    ),
                )
            )
        else:
            record_id = int(old[S.ID])
            prior_work_id, prior_edition_id = (int(old[S.WORK_ID]), int(old[S.EDITION_ID]))
            connection.execute(
                S.STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_TITLE_AUTHOR_KEY,
                (
                    candidate_title_author_key(book),
                    semantic_hash,
                    _identity_hash(book),
                    self._payloads().save_json(book.model_dump_json()),
                    now,
                    snapshot_id,
                    record_id,
                ),
            )
        connection.execute(
            S.STORAGE_DATABASE_SAVE_RECORD_DELETE_IDENTIFIERS_WHERE_RECORD_ID, (record_id,)
        )
        connection.executemany(
            S.STORAGE_DATABASE_SAVE_RECORD_INSERT_IDENTIFIERS_RECORD_ID_ISBN,
            [(record_id, isbn) for isbn in normalized_isbns(book.isbns)],
        )
        comparisons = [
            (
                row,
                compare_books(
                    book,
                    BookRecord.model_validate_json(self._payloads().load_text(row[S.LATEST_JSON])),
                ),
            )
            for row in self._comparison_rows(connection, record_id, book)
        ]
        confirmed = [
            (row, match) for row, match in comparisons if match.kind == MatchKind.CONFIRMED
        ]
        identities = {(int(row[S.WORK_ID]), int(row[S.EDITION_ID])) for row, _ in confirmed}
        contested = bool(contested_isbns.intersection(normalized_isbns(book.isbns))) or any(
            (
                match.kind == MatchKind.CONFLICTING
                or (match.kind == MatchKind.LIKELY and bool(match.identifiers))
                for _, match in comparisons
            )
        )
        chosen: tuple[sqlite3.Row, MatchResult] | None = C.NONE
        if (
            len(identities) == C.ONE
            and not contested
            and (
                old is C.NONE or self._can_reconsider_identity(connection, record_id, prior_work_id)
            )
        ):
            chosen = confirmed[C.ZERO]
            connection.execute(
                S.STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_WORK_ID_EDITION,
                (chosen[C.ZERO][S.WORK_ID], chosen[C.ZERO][S.EDITION_ID], record_id),
            )
        for other, comparison in comparisons:
            candidate_id = self._save_candidate(
                connection, record_id, other, comparison, snapshot_id
            )
            if chosen is not C.NONE and int(other[S.ID]) == int(chosen[C.ZERO][S.ID]):
                self._decision(
                    connection,
                    record_id=record_id,
                    candidate_id=candidate_id,
                    kind=S.AUTOMATIC,
                    prior=(prior_work_id, prior_edition_id),
                    current=(int(other[S.WORK_ID]), int(other[S.EDITION_ID])),
                    prior_resolution=S.PENDING,
                    evidence={
                        S.SNAPSHOT_ID: snapshot_id,
                        S.REASON: comparison.reason,
                        S.IDENTIFIERS: list(comparison.identifiers),
                    },
                )
            self._refresh_match_state(connection, int(other[S.ID]))
        self._refresh_match_state(connection, record_id)
        return (record_id, old is C.NONE or old[S.SEMANTIC_HASH] != semantic_hash)

    @staticmethod
    def _can_reconsider_identity(
        connection: sqlite3.Connection, record_id: int, work_id: int
    ) -> bool:
        # Never move an existing group, or overrule a human/reversed automatic decision.
        return (
            connection.execute(S.MATCH_UPGRADE_OTHER_WORK_MEMBER, (work_id, record_id)).fetchone()
            is C.NONE
            and connection.execute(
                S.MATCH_UPGRADE_PRIOR_DECISION, (record_id, record_id, record_id)
            ).fetchone()
            is C.NONE
        )

    def _save_candidate(
        self,
        connection: sqlite3.Connection,
        record_id: int,
        other: sqlite3.Row,
        match: MatchResult,
        snapshot_id: int,
    ) -> int | None:
        subject, target = (max(record_id, int(other[S.ID])), min(record_id, int(other[S.ID])))
        existing: sqlite3.Row | None = connection.execute(
            S.DATABASE_SAVE_CANDIDATE_EXISTING_MATCH_CANDIDATES_WHERE_RECORD, (subject, target)
        ).fetchone()
        if match.kind == MatchKind.UNRELATED and existing is C.NONE:
            return C.NONE
        automatic_history = (
            connection.execute(S.STORAGE_AUTOMATIC_MATCH_HISTORY, (existing[S.ID],)).fetchall()
            if existing is not C.NONE
            else []
        )
        if (
            match.kind != MatchKind.CONFIRMED
            and existing is not C.NONE
            and existing[S.RESOLUTION] not in (S.ACCEPTED, S.REJECTED)
        ):
            for decision in automatic_history:
                self._invalidate_automatic_match(connection, decision, existing, match, snapshot_id)
        current = connection.execute(
            S.DATABASE_SAVE_CANDIDATE_CURRENT_SELECT_ID_EDITION_ID_FROM_SOURCE, (record_id,)
        ).fetchone()
        other_identity = connection.execute(
            S.DATABASE_SAVE_CANDIDATE_CURRENT_SELECT_ID_EDITION_ID_FROM_SOURCE, (other[S.ID],)
        ).fetchone()
        resolution = S.PENDING
        if match.kind == MatchKind.UNRELATED and not automatic_history:
            resolution = S.DISMISSED
        elif (
            match.kind == MatchKind.CONFIRMED
            and current[S.WORK_ID] == other_identity[S.WORK_ID]
            and (current[S.EDITION_ID] == other_identity[S.EDITION_ID])
        ):
            resolution = S.AUTO_CONFIRMED
        connection.execute(
            S.STORAGE_DATABASE_SAVE_CANDIDATE_INSERT_CANDIDATES_RECORD_ID_TARGET,
            (
                subject,
                target,
                match.kind.value,
                (
                    S.STORAGE_INVALIDATED_MATCH_REASON.format(reason=match.reason)
                    if automatic_history and match.kind != MatchKind.CONFIRMED
                    else match.reason
                ),
                _json(match.identifiers),
                resolution,
                snapshot_id,
                snapshot_id,
            ),
        )
        return int(
            connection.execute(
                S.DATABASE_SAVE_CANDIDATE_EXISTING_MATCH_CANDIDATES_WHERE_RECORD, (subject, target)
            ).fetchone()[S.ID]
        )

    def _invalidate_automatic_match(
        self,
        connection: sqlite3.Connection,
        decision: sqlite3.Row,
        candidate: sqlite3.Row,
        match: MatchResult,
        snapshot_id: int,
    ) -> None:
        if decision[S.REVERSED_BY] is not C.NONE:
            return
        record = connection.execute(
            S.DATABASE_SAVE_CANDIDATE_CURRENT_SELECT_ID_EDITION_ID_FROM_SOURCE,
            (decision[S.RECORD_ID],),
        ).fetchone()
        prior = (int(decision[S.WORK_ID]), int(decision[S.EDITION_ID]))
        if (record[S.WORK_ID], record[S.EDITION_ID]) != prior:
            return
        # A subsequent human acceptance, unlike an automatic link, owns its mapping.
        if connection.execute(
            S.STORAGE_LATER_ACCEPTED_MATCH, (decision[S.RECORD_ID], decision[S.ID])
        ).fetchone():
            return
        current = (int(decision[S.PRIOR_WORK_ID]), int(decision[S.PRIOR_EDITION_ID]))
        connection.execute(
            S.STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_WORK_ID_EDITION,
            (*current, decision[S.RECORD_ID]),
        )
        invalidation_id = self._decision(
            connection,
            record_id=int(decision[S.RECORD_ID]),
            candidate_id=int(candidate[S.ID]),
            kind=S.STORAGE_INVALIDATED_AUTOMATIC_MATCH,
            prior=prior,
            current=current,
            prior_resolution=str(candidate[S.RESOLUTION]),
            evidence={
                S.REVERTS: int(decision[S.ID]),
                S.SNAPSHOT_ID: snapshot_id,
                S.KIND: match.kind.value,
                S.REASON: match.reason,
                S.IDENTIFIERS: list(match.identifiers),
            },
        )
        connection.execute(
            S.STORAGE_DATABASE_UNDO_MATCH_UPDATE_DECISIONS_SET_REVERSED_BY_WHERE,
            (invalidation_id, decision[S.ID]),
        )
        connection.execute(
            S.STORAGE_DATABASE_RESOLVE_MATCH_UPDATE_SET_RESOLUTION_WHERE_ID,
            (S.PENDING, candidate[S.ID]),
        )
        self._refresh_after_mapping_change(connection, int(decision[S.RECORD_ID]))

    @staticmethod
    def _refresh_match_state(connection: sqlite3.Connection, record_id: int) -> None:
        pending = [
            row[S.KIND]
            for row in connection.execute(
                S.DATABASE_REFRESH_MATCH_STATE_MATCH_CANDIDATES_WHERE_RESOLUTION,
                (record_id, record_id),
            )
        ]
        if MatchKind.CONFLICTING.value in pending:
            state = S.CONFLICTING
        elif pending:
            state = S.UNRESOLVED
        elif connection.execute(
            S.STORAGE_DATABASE_REFRESH_MATCH_STATE_SOURCE_RECORDS_WHERE_ID_AND,
            (record_id, record_id),
        ).fetchone():
            state = S.CONFIRMED
        elif connection.execute(
            S.STORAGE_DATABASE_REFRESH_MATCH_STATE_IDENTIFIERS_I_JOIN_SOURCE, (record_id,)
        ).fetchone():
            state = S.INDEPENDENT
        else:
            state = S.UNRESOLVED
        connection.execute(
            S.STORAGE_DATABASE_REFRESH_MATCH_STATE_RECORDS_SET_MATCH_STATE_WHERE, (state, record_id)
        )

    @staticmethod
    def _decision(
        connection: sqlite3.Connection,
        *,
        record_id: int,
        candidate_id: int | None,
        kind: str,
        prior: tuple[int, int],
        current: tuple[int, int],
        prior_resolution: str | None,
        evidence: dict[str, JsonValue],
    ) -> int:
        return _insert_id(
            connection.execute(
                S.STORAGE_DATABASE_DECISION_INSERT_INTO_DECISIONS_RECORD_ID_CANDIDATE,
                (
                    record_id,
                    candidate_id,
                    kind,
                    prior[C.ZERO],
                    prior[C.ONE],
                    current[C.ZERO],
                    current[C.ONE],
                    prior_resolution,
                    _json(evidence),
                    utc_now(),
                ),
            )
        )

    @staticmethod
    def _can_refine_reading(old: ReadingEvent, new: ReadingEvent) -> bool:
        if old.source_event_id is not C.NONE or new.source_event_id is not C.NONE:
            return C.FALSE
        shared = C.FALSE
        added = C.FALSE
        for old_date, new_date in ((old.started, new.started), (old.finished, new.finished)):
            if old_date is not C.NONE and new_date is not C.NONE:
                if old_date.value != new_date.value:
                    return C.FALSE
                shared = C.TRUE
            elif old_date is not C.NONE:
                return C.FALSE
            elif new_date is not C.NONE:
                added = C.TRUE
        status_progressed = (
            old.status
            in (ReadingStatus.UNKNOWN, ReadingStatus.CURRENTLY_READING, ReadingStatus.PAUSED)
            and new.status != old.status
        )
        return shared and (added or status_progressed)

    def _save_readings(
        self,
        connection: sqlite3.Connection,
        record_id: int,
        snapshot_id: int,
        book: BookRecord,
        now: str,
    ) -> None:
        snapshot_record_id = int(
            connection.execute(
                S.DATABASE_SAVE_READINGS_SNAPSHOT_SNAPSHOT_RECORDS_WHERE_SNAPSHOT,
                (snapshot_id, book.source_id),
            ).fetchone()[S.ID]
        )
        events = _reading_occurrences(book.reading_events)
        existing = connection.execute(
            S.DATABASE_SAVE_READINGS_EXISTING_SELECT_EVENTS_WHERE_RECORD_ID, (record_id,)
        ).fetchall()
        existing_events = {
            int(row[S.ID]): ReadingEvent.model_validate_json(row[S.EVENT_JSON]) for row in existing
        }
        by_key = {row[S.EVENT_KEY]: row for row in existing}
        used: set[int] = set()
        for key, event in events.items():
            previous = by_key.get(key)
            if previous is C.NONE and event.source_event_id is C.NONE:
                refinements = [
                    row
                    for row in existing
                    if int(row[S.ID]) not in used
                    and self._can_refine_reading(existing_events[int(row[S.ID])], event)
                    and (
                        sum(
                            self._can_refine_reading(existing_events[int(row[S.ID])], incoming)
                            for incoming in events.values()
                        )
                        == C.ONE
                    )
                ]
                if len(refinements) == C.ONE:
                    previous = refinements[C.ZERO]
            if previous is C.NONE:
                event_id = _insert_id(
                    connection.execute(
                        S.DATABASE_SAVE_READINGS_EVENT_ID_READING_EVENTS_RECORD_ID_EVENT,
                        (
                            record_id,
                            key,
                            event.source_event_id,
                            event.model_dump_json(),
                            now,
                            now,
                            snapshot_id,
                        ),
                    )
                )
            else:
                event_id = int(previous[S.ID])
                connection.execute(
                    S.STORAGE_DATABASE_SAVE_READINGS_UPDATE_EVENTS_SET_EVENT_KEY_EVENT,
                    (key, event.model_dump_json(), now, snapshot_id, event_id),
                )
            used.add(event_id)
            connection.execute(
                S.STORAGE_DATABASE_SAVE_READINGS_OBSERVATIONS_SNAPSHOT_RECORD_ID,
                (snapshot_record_id, event_id, event.model_dump_json()),
            )

    def finish_run(self, run_id: int, state: SyncState) -> None:
        state = SyncState(state)
        with self._transaction() as connection:
            row = connection.execute(
                S.DATABASE_FINISH_RUN_ROW_SELECT_STATE_FINISHED_AT_FROM_RUNS_WHERE, (run_id,)
            ).fetchone()
            if row is C.NONE:
                raise ValueError(S.STORAGE_DATABASE_OPEN_RUN_UNKNOWN_INGESTION_RUN)
            if row[S.FINISHED_AT] is not C.NONE:
                if row[S.STATE] != state.value:
                    raise ValueError(
                        S.STORAGE_DATABASE_FINISH_RUN_A_FINISHED_RUN_CANNOT_CHANGE_STATE
                    )
                return
            connection.execute(
                S.STORAGE_DATABASE_FINISH_RUN_UPDATE_RUNS_SET_STATE_FINISHED_AT_WHERE,
                (state.value, utc_now(), run_id),
            )

    def active_records(self) -> tuple[BookRecord, ...]:
        return tuple(
            BookRecord.model_validate_json(self._payloads().load_text(row[S.LATEST_JSON]))
            for row in self._connection().execute(
                S.STORAGE_DATABASE_ACTIVE_RECORDS_SELECT_JSON_FROM_SOURCE_RECORDS
            )
        )

    def analytics_input(
        self, accounts: tuple[Account, ...], settings: AnalyticsSettings
    ) -> AnalysisInput:
        from bookystats.persistence.analysis_input import read_analytics_input

        with self._transaction(write=C.FALSE) as connection:
            return read_analytics_input(
                connection, self._payloads(), accounts, settings, _identity_hash
            )

    def status(self) -> dict[str, JsonValue]:
        with self._transaction(write=C.FALSE) as connection:
            sources: list[JsonValue] = []
            for row in connection.execute(
                S.STORAGE_DATABASE_STATUS_SELECT_C_SELECT_COUNT_FROM_MEMBERSHIPS_M
            ):
                sources.append(
                    {
                        S.SOURCE: row[S.SOURCE],
                        S.ACCOUNT_ID: row[S.ACCOUNT_ID],
                        S.COLLECTION: row[S.COLLECTION],
                        S.STATE: row[S.STATE],
                        S.LAST_ATTEMPT_AT: row[S.LAST_ATTEMPT_AT],
                        S.LAST_SUCCESS_AT: row[S.LAST_SUCCESS_AT],
                        S.ACTIVE_COUNT: int(row[S.ACTIVE_COUNT]),
                        S.COVERAGE: _parsed_json(row[S.COVERAGE_JSON]),
                        S.LAST_ATTEMPT_COVERAGE: _parsed_json(row[S.ATTEMPT_COVERAGE_JSON]),
                        S.ACTIVE_SNAPSHOT_ID: row[S.ACTIVE_SNAPSHOT_ID],
                    }
                )
            for row in connection.execute(S.STORAGE_DATABASE_STATUS_SELECT_P_A_ACCOUNT_ID_R_STATE):
                sources.append(
                    {
                        S.SOURCE: row[S.SOURCE],
                        S.ACCOUNT_ID: row[S.ACCOUNT_ID],
                        S.COLLECTION: row[S.COLLECTION],
                        S.STATE: row[S.STATE],
                        S.LAST_ATTEMPT_AT: row[S.STAGED_AT],
                        S.LAST_SUCCESS_AT: C.NONE,
                        S.ACTIVE_COUNT: C.ZERO,
                        S.COVERAGE: {},
                        S.LAST_ATTEMPT_COVERAGE: {},
                        S.ACTIVE_SNAPSHOT_ID: C.NONE,
                    }
                )
            counts = connection.execute(
                S.DATABASE_STATUS_COUNTS_SELECT_COUNT_AS_SOURCE_RECORDS_COUNT_DISTINCT
            ).fetchone()
            reading_events = int(
                connection.execute(
                    S.DATABASE_STATUS_READING_EVENTS_SELECT_FROM_READING_EVENTS_E_WHERE
                ).fetchone()[C.ZERO]
            )
            metadata: dict[str, JsonValue] = {}
            for provider in C.STORAGE_METADATA_PROVIDERS:
                attempts = connection.execute(
                    S.DATABASE_STATUS_ATTEMPTS_SELECT_COUNT_AS_TOTAL_MAX_CHECKED_AT,
                    (provider.value,),
                ).fetchone()
                selected = connection.execute(
                    S.DATABASE_STATUS_SELECTED_SELECT_COUNT_AS_TOTAL_MAX_E_LAST, (provider.value,)
                ).fetchone()
                candidates = int(
                    connection.execute(
                        S.DATABASE_STATUS_CANDIDATES_SELECT_COUNT_ENRICHMENT_CANDIDATES_C_JOIN,
                        (provider.value,),
                    ).fetchone()[C.ZERO]
                )
                unresolved = int(
                    connection.execute(
                        S.DATABASE_STATUS_UNRESOLVED_SELECT_COUNT_ENRICHMENT_ATTEMPTS_A_WHERE,
                        (provider.value, SyncState.COMPLETE.value),
                    ).fetchone()[C.ZERO]
                )
                metadata[provider.value] = {
                    S.ATTEMPTS: int(attempts[S.TOTAL]),
                    S.CANDIDATES: candidates,
                    S.SELECTED: int(selected[S.TOTAL]),
                    S.UNRESOLVED: unresolved,
                    S.LAST_ATTEMPT_AT: attempts[S.LAST_ATTEMPT_AT],
                    S.LAST_SUCCESS_AT: selected[S.LAST_SUCCESS_AT],
                }
            last = connection.execute(
                S.DATABASE_STATUS_LAST_SELECT_FROM_RUNS_ORDER_BY_ID_DESC
            ).fetchone()
            return {
                S.SOURCES: sources,
                S.LIBRARY: {
                    S.SOURCE_RECORDS: int(counts[S.SOURCE_RECORDS]),
                    S.WORKS: int(counts[S.WORKS]),
                    S.EDITIONS: int(counts[S.EDITIONS]),
                    S.READING_EVENTS: reading_events,
                    S.UNRESOLVED: int(counts[S.UNRESOLVED]),
                },
                S.METADATA: metadata,
                S.LAST_RUN: {
                    S.RUN_ID: int(last[S.ID]),
                    S.STATE: last[S.STATE],
                    S.STARTED_AT: last[S.STARTED_AT],
                    S.FINISHED_AT: last[S.FINISHED_AT],
                }
                if last is not C.NONE
                else C.NONE,
            }

    @staticmethod
    def _provider(provider: Source) -> Source:
        provider = Source(provider)
        if provider not in C.STORAGE_METADATA_PROVIDERS:
            raise ValueError(S.STORAGE_DATABASE_PROVIDER_EXPECTED_A_METADATA_PROVIDER)
        return provider

    def save_enrichment(self, source: Source, provider: Source, result: EnrichmentResult) -> None:
        source = Source(source)
        provider = self._provider(provider)
        result = EnrichmentResult.model_validate(result.model_dump())
        if source not in C.STORAGE_READER_SOURCES:
            raise ValueError(S.STORAGE_DATABASE_SAVE_ENRICHMENT_ENRICHMENT_TARGET_A_READER_SOURCE)
        if any(candidate.provider != provider for candidate in result.candidates):
            raise ValueError(S.STORAGE_DATABASE_SAVE_ENRICHMENT_CANDIDATE_FROM_ANOTHER_PROVIDER)
        now = utc_now()
        with self._transaction() as connection:
            record = connection.execute(
                S.DATABASE_SAVE_ENRICHMENT_RECORD_SELECT_R_FROM_SOURCE_RECORDS_R_JOIN,
                (source.value, result.source_id),
            ).fetchone()
            if record is C.NONE:
                raise ValueError(
                    S.STORAGE_DATABASE_SAVE_ENRICHMENT_ENRICHMENT_NOT_BEEN_PUBLISHED_FOR
                )
            book = BookRecord.model_validate_json(self._payloads().load_text(record[S.LATEST_JSON]))
            recover_optional_fields = bool(result.issues) and all(
                issue.code in C.META_COVERAGE_OPTIONAL_ISSUES for issue in result.issues
            )
            selected = (
                select_metadata_candidate(book, result.candidates)
                if result.state == SyncState.COMPLETE
                or (result.state == SyncState.PARTIAL and recover_optional_fields)
                else C.NONE
            )
            state = result.state
            if selected is not C.NONE and any(
                item.scope == S.READER
                or (
                    item.state == FieldState.FAILED
                    and (
                        not recover_optional_fields
                        or item.field not in C.META_COVERAGE_OPTIONAL_FIELDS
                    )
                )
                for item in selected.observations
            ):
                selected = C.NONE
                state = SyncState.PARTIAL
            attempt_id = _insert_id(
                connection.execute(
                    S.DATABASE_SAVE_ENRICHMENT_ATTEMPT_ID_ATTEMPTS_RECORD_ID_PROVIDER,
                    (
                        record[S.ID],
                        provider.value,
                        state.value,
                        now,
                        record[S.IDENTITY_HASH],
                        self._payloads().save_json(result.model_dump_json()),
                        C.META_COVERAGE_IMPLEMENTATION_VERSION
                        if provider == Source.OPEN_LIBRARY
                        else C.ONE,
                    ),
                )
            )
            selected_id: int | None = C.NONE
            for candidate in result.candidates:
                comparison = compare_books(book, candidate)
                is_selected = (
                    selected is not C.NONE and candidate == selected and (selected_id is C.NONE)
                )
                candidate_id = _insert_id(
                    connection.execute(
                        S.DATABASE_SAVE_ENRICHMENT_CANDIDATE_ID_CANDIDATES_ATTEMPT_ID_PROVIDER,
                        (
                            attempt_id,
                            candidate.provider_id,
                            comparison.kind.value,
                            comparison.reason,
                            int(is_selected),
                            self._payloads().save_json(candidate.model_dump_json()),
                        ),
                    )
                )
                connection.executemany(
                    S.STORAGE_DATABASE_SAVE_ENRICHMENT_OBSERVATIONS_CANDIDATE_ID_FIELD,
                    [
                        (
                            candidate_id,
                            item.field,
                            item.state.value,
                            item.scope,
                            _json(item.value),
                            item.source_url,
                            item.observed_at,
                        )
                        for item in candidate.observations
                    ],
                )
                if is_selected:
                    selected_id = candidate_id
            if selected_id is not C.NONE:
                connection.execute(
                    S.STORAGE_DATABASE_SAVE_ENRICHMENT_INSERT_ACTIVE_RECORD_ID_PROVIDER,
                    (record[S.ID], provider.value, attempt_id, selected_id, now),
                )

    def enrichment_targets(
        self,
        provider: Source,
        *,
        max_age_days: int = C.DATABASE_ENRICHMENT_TARGETS_MAX_AGE_DAYS,
        limit: int | None = C.NONE,
    ) -> tuple[BookRecord, ...]:
        provider = self._provider(provider)
        if max_age_days < C.ZERO or (limit is not C.NONE and limit < C.ZERO):
            raise ValueError(S.STORAGE_DATABASE_ENRICHMENT_TARGETS_LIMIT_CANNOT_BE_NEGATIVE)
        cutoff = (datetime.now(UTC) - timedelta(days=max_age_days)).isoformat()
        rows = self._connection().execute(
            S.DATABASE_ENRICHMENT_TARGETS_ROWS_SELECT_JSON_FROM_SOURCE_RECORDS,
            (
                provider.value,
                SyncState.COMPLETE.value,
                cutoff,
                C.META_COVERAGE_IMPLEMENTATION_VERSION
                if provider == Source.OPEN_LIBRARY
                else C.ONE,
                -C.ONE if limit is C.NONE else limit,
            ),
        )
        return tuple(
            BookRecord.model_validate_json(self._payloads().load_text(row[S.LATEST_JSON]))
            for row in rows
        )

    def record_history(
        self, source: Source, account_id: str, source_id: str
    ) -> tuple[dict[str, JsonValue], ...]:
        return tuple(
            {
                S.SNAPSHOT_ID: int(row[S.SNAPSHOT_ID]),
                S.RUN_ID: int(row[S.RUN_ID]),
                S.COLLECTION: row[S.COLLECTION],
                S.STATE: row[S.STATE],
                S.PUBLISHED: bool(row[S.PUBLISHED]),
                S.REJECTION_REASON: row[S.REJECTION_REASON],
                S.STARTED_AT: row[S.STARTED_AT],
                S.FINISHED_AT: row[S.FINISHED_AT],
                S.RECORD: self._payloads().load(row[S.RECORD_JSON]),
            }
            for row in self._connection().execute(
                S.STORAGE_DATABASE_RECORD_HISTORY_SELECT_S_R_RECORD_JSON_S_ID,
                (Source(source).value, account_id, source_id),
            )
        )

    def staged_progress(self, run_id: int) -> tuple[CollectionProgress, ...]:
        return tuple(
            CollectionProgress.model_validate_json(
                self._payloads().load_collection_json(row[S.RAW_JSON])
            )
            for row in self._connection().execute(
                S.STORAGE_DATABASE_STAGED_PROGRESS_SELECT_JSON_FROM_PROGRESS_WHERE_RUN,
                (run_id,),
            )
        )

    def metadata_for(
        self, source: Source, account_id: str, source_id: str
    ) -> tuple[dict[str, JsonValue], ...]:
        return tuple(
            {
                S.PROVIDER: row[S.PROVIDER],
                S.LAST_SUCCESS_AT: row[S.LAST_SUCCESS_AT],
                S.STALE_IDENTITY: row[S.OBSERVED_IDENTITY] != row[S.IDENTITY_HASH],
                S.CANDIDATE: self._payloads().load(row[S.CANDIDATE_JSON]),
            }
            for row in self._connection().execute(
                S.STORAGE_DATABASE_METADATA_FOR_SELECT_E_PROVIDER_E_LAST_SUCCESS_AT,
                (Source(source).value, account_id, source_id),
            )
        )

    def match_candidates(
        self, *, include_resolved: bool = C.FALSE
    ) -> tuple[dict[str, JsonValue], ...]:
        rows = self._connection().execute(
            S.DATABASE_MATCH_CANDIDATES_ROWS_SELECT_C_ID_R_SOURCE_R_ACCOUNT,
            (int(include_resolved),),
        )
        results: list[dict[str, JsonValue]] = []
        for row in rows:
            result = cast(dict[str, JsonValue], dict(row))
            result[S.IDENTIFIERS] = _parsed_json(str(result.pop(S.IDENTIFIERS_JSON)))
            results.append(result)
        return tuple(results)

    def _provider_work_proofs(
        self, connection: sqlite3.Connection, active_ids: set[int]
    ) -> dict[int, _ProviderWorkProof]:
        proofs: dict[int, _ProviderWorkProof] = {}
        for row in connection.execute(S.MATCH_UPGRADE_WORK_SELECTED, (Source.OPEN_LIBRARY.value,)):
            record_id = int(row[S.RECORD_ID])
            if record_id not in active_ids:
                continue
            record = connection.execute(
                S.STORAGE_DATABASE_COMPARISON_ROWS_SELECT_FROM_SOURCE_RECORDS_WHERE_ID,
                (record_id,),
            ).fetchone()
            book = BookRecord.model_validate_json(self._payloads().load_text(record[S.LATEST_JSON]))
            candidate = MetadataCandidate.model_validate_json(
                self._payloads().load_text(row[S.CANDIDATE_JSON])
            )
            candidates = connection.execute(
                S.MATCH_UPGRADE_ATTEMPT_CANDIDATES, (row[S.MATCH_UPGRADE_ATTEMPT_ID],)
            ).fetchall()
            if sum(item[S.MATCH_UPGRADE_SELECTED] for item in candidates) != C.ONE:
                continue
            plausible = tuple(
                MetadataCandidate.model_validate_json(
                    self._payloads().load_text(item[S.CANDIDATE_JSON])
                )
                for item in candidates
            )
            if (
                candidate.provider != Source.OPEN_LIBRARY
                or not candidate.work_id
                or candidate.provider_id != candidate.work_id
                or candidate.edition_id is not C.NONE
                or not C.MATCH_UPGRADE_PROVIDER_WORK_PATTERN.fullmatch(candidate.work_id)
                or candidate.url != S.OPEN_LIBRARY_WORK_URL_TEMPLATE.format(v0=candidate.work_id)
                or select_metadata_candidate(book, plausible) != candidate
            ):
                continue
            proofs[record_id] = _ProviderWorkProof(
                work_id=candidate.work_id,
                attempt_id=int(row[S.MATCH_UPGRADE_ATTEMPT_ID]),
                candidate_id=int(row[S.CANDIDATE_ID]),
                identity_hash=str(row[S.IDENTITY_HASH]),
                book=book,
            )
        return proofs

    def _audit_automatic_isbn_matches(self, connection: sqlite3.Connection) -> None:
        for decision in reversed(
            connection.execute(S.MATCH_UPGRADE_DECISIONS, (S.AUTOMATIC,)).fetchall()
        ):
            candidate = connection.execute(
                S.DATABASE_RESOLVE_MATCH_CANDIDATE_SELECT_MATCH_CANDIDATES_WHERE_ID,
                (decision[S.CANDIDATE_ID],),
            ).fetchone()
            if candidate is C.NONE:
                continue
            record_id = int(decision[S.RECORD_ID])
            target_id = (
                int(candidate[S.TARGET_RECORD_ID])
                if int(candidate[S.RECORD_ID]) == record_id
                else int(candidate[S.RECORD_ID])
            )
            record, target = (
                connection.execute(
                    S.STORAGE_DATABASE_COMPARISON_ROWS_SELECT_FROM_SOURCE_RECORDS_WHERE_ID,
                    (item,),
                ).fetchone()
                for item in (record_id, target_id)
            )
            comparison = compare_books(
                BookRecord.model_validate_json(self._payloads().load_text(record[S.LATEST_JSON])),
                BookRecord.model_validate_json(self._payloads().load_text(target[S.LATEST_JSON])),
            )
            if comparison.kind == MatchKind.CONFIRMED and (
                record[S.WORK_ID],
                record[S.EDITION_ID],
            ) != (target[S.WORK_ID], target[S.EDITION_ID]):
                comparison = MatchResult(
                    MatchKind.LIKELY, S.MATCH_UPGRADE_DEPENDENCY_LOST, comparison.identifiers
                )
            if comparison.kind != MatchKind.CONFIRMED:
                self._invalidate_automatic_match(
                    connection,
                    decision,
                    candidate,
                    comparison,
                    int(record[S.MATCH_UPGRADE_LAST_SNAPSHOT_ID]),
                )

    def _save_provider_work_candidate(
        self,
        connection: sqlite3.Connection,
        record: sqlite3.Row,
        target: sqlite3.Row,
        work_id: str,
    ) -> int:
        candidate_id = self._save_candidate(
            connection,
            int(record[S.ID]),
            target,
            MatchResult(MatchKind.CONFIRMED, S.MATCH_UPGRADE_PROVIDER_REASON, (work_id,)),
            int(record[S.MATCH_UPGRADE_LAST_SNAPSHOT_ID]),
        )
        assert candidate_id is not C.NONE
        connection.execute(
            S.STORAGE_DATABASE_RESOLVE_MATCH_UPDATE_SET_RESOLUTION_WHERE_ID,
            (S.MATCH_UPGRADE_WORK_CONFIRMED, candidate_id),
        )
        return candidate_id

    def reconcile_provider_work_matches(self) -> int:
        with self._transaction() as connection:
            active_ids = {
                int(row[S.RECORD_ID])
                for row in connection.execute(S.MATCH_UPGRADE_ACTIVE_RECORD_IDS)
            }
            records = {
                int(row[S.ID]): row for row in connection.execute(S.MATCH_UPGRADE_ALL_RECORDS)
            }
            proofs = self._provider_work_proofs(connection, active_ids)
            invalidated = C.FALSE
            for decision in connection.execute(
                S.MATCH_UPGRADE_DECISIONS, (S.MATCH_UPGRADE_PROVIDER_AUTOMATIC,)
            ).fetchall():
                record_id = int(decision[S.RECORD_ID])
                record = records[record_id]
                if (record[S.WORK_ID], record[S.EDITION_ID]) != (
                    decision[S.WORK_ID],
                    decision[S.EDITION_ID],
                ) or connection.execute(
                    S.STORAGE_LATER_ACCEPTED_MATCH, (record_id, decision[S.ID])
                ).fetchone():
                    continue
                candidate = connection.execute(
                    S.DATABASE_RESOLVE_MATCH_CANDIDATE_SELECT_MATCH_CANDIDATES_WHERE_ID,
                    (decision[S.CANDIDATE_ID],),
                ).fetchone()
                target_id = (
                    int(candidate[S.TARGET_RECORD_ID])
                    if int(candidate[S.RECORD_ID]) == record_id
                    else int(candidate[S.RECORD_ID])
                )
                target = records[target_id]
                evidence = _parsed_json(decision[S.MATCH_UPGRADE_EVIDENCE_JSON])
                assert isinstance(evidence, dict)
                work_id = evidence[S.PROVIDER_ID]
                members = [
                    item for item in records.values() if item[S.WORK_ID] == record[S.WORK_ID]
                ]
                valid = (
                    candidate[S.RESOLUTION] != S.REJECTED
                    and target[S.WORK_ID] == record[S.WORK_ID]
                    and all(
                        int(item[S.ID]) in proofs
                        and proofs[int(item[S.ID])].work_id == work_id
                        and target_id in proofs
                        and work_bibliography_compatible(
                            proofs[int(item[S.ID])].book, proofs[target_id].book
                        )
                        for item in members
                    )
                )
                if valid:
                    assert isinstance(work_id, str)
                    self._save_provider_work_candidate(connection, record, target, work_id)
                    continue
                prior = (int(record[S.WORK_ID]), int(record[S.EDITION_ID]))
                current = (int(decision[S.PRIOR_WORK_ID]), int(decision[S.PRIOR_EDITION_ID]))
                connection.execute(
                    S.STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_WORK_ID_EDITION,
                    (*current, record_id),
                )
                invalidation_id = self._decision(
                    connection,
                    record_id=record_id,
                    candidate_id=int(candidate[S.ID]),
                    kind=S.MATCH_UPGRADE_PROVIDER_INVALIDATED,
                    prior=prior,
                    current=current,
                    prior_resolution=str(candidate[S.RESOLUTION]),
                    evidence={
                        S.REVERTS: int(decision[S.ID]),
                        S.REASON: S.MATCH_UPGRADE_PROVIDER_LOST,
                    },
                )
                connection.execute(
                    S.STORAGE_DATABASE_UNDO_MATCH_UPDATE_DECISIONS_SET_REVERSED_BY_WHERE,
                    (invalidation_id, decision[S.ID]),
                )
                connection.execute(
                    S.MATCH_UPGRADE_RESET_WORK_CANDIDATE,
                    (S.MATCH_UPGRADE_PROVIDER_LOST, candidate[S.ID]),
                )
                invalidated = C.TRUE
            if invalidated:
                self._audit_automatic_isbn_matches(connection)
            records = {
                int(row[S.ID]): row for row in connection.execute(S.MATCH_UPGRADE_ALL_RECORDS)
            }
            groups: dict[int, list[int]] = {}
            buckets: dict[str, list[int]] = {}
            for record_id, record in records.items():
                groups.setdefault(int(record[S.WORK_ID]), []).append(record_id)
            for record_id, proof in proofs.items():
                buckets.setdefault(proof.work_id, []).append(record_id)
            linked = C.ZERO
            for work_id, record_ids in buckets.items():
                # Only a unique cross-source singleton pair can introduce a new work link.
                if len(record_ids) != C.TWO:
                    continue
                target_id, record_id = sorted(record_ids)
                target, record = records[target_id], records[record_id]
                if (
                    target[S.SOURCE] == record[S.SOURCE]
                    or target[S.WORK_ID] == record[S.WORK_ID]
                    or any(
                        len(groups[int(item[S.WORK_ID])]) != C.ONE
                        or not self._can_reconsider_identity(
                            connection, int(item[S.ID]), int(item[S.WORK_ID])
                        )
                        for item in (target, record)
                    )
                    or not work_bibliography_compatible(
                        proofs[target_id].book, proofs[record_id].book
                    )
                ):
                    continue
                prior = (int(record[S.WORK_ID]), int(record[S.EDITION_ID]))
                edition_id = _insert_id(
                    connection.execute(
                        S.DATABASE_NEW_IDENTITY_EDITION_ID_INSERT_EDITIONS_WORK_ID_CREATED_AT,
                        (target[S.WORK_ID], utc_now()),
                    )
                )
                current = (int(target[S.WORK_ID]), edition_id)
                connection.execute(
                    S.STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_WORK_ID_EDITION,
                    (*current, record_id),
                )
                candidate_id = self._save_provider_work_candidate(
                    connection, record, target, work_id
                )
                self._decision(
                    connection,
                    record_id=record_id,
                    candidate_id=candidate_id,
                    kind=S.MATCH_UPGRADE_PROVIDER_AUTOMATIC,
                    prior=prior,
                    current=current,
                    prior_resolution=S.PENDING,
                    evidence={
                        S.PROVIDER: Source.OPEN_LIBRARY.value,
                        S.PROVIDER_ID: work_id,
                        S.MATCH_UPGRADE_WORK_PROOFS: [
                            {
                                S.RECORD_ID: item,
                                S.IDENTITY_HASH: proofs[item].identity_hash,
                                S.MATCH_UPGRADE_ATTEMPT_ID: proofs[item].attempt_id,
                                S.CANDIDATE_ID: proofs[item].candidate_id,
                            }
                            for item in (target_id, record_id)
                        ],
                    },
                )
                linked += C.ONE
            for record_id in active_ids:
                self._refresh_match_state(connection, record_id)
            return linked

    @staticmethod
    def _refresh_after_mapping_change(connection: sqlite3.Connection, record_id: int) -> None:
        connection.execute(
            S.STORAGE_DATABASE_REFRESH_AFTER_MAPPING_SET_RESOLUTION_PENDING_WHERE,
            (record_id, record_id),
        )
        ids = {record_id}
        for row in connection.execute(
            S.STORAGE_DATABASE_COMPARISON_ROWS_SELECT_ID_TARGET_RECORD_ID_FROM,
            (record_id, record_id),
        ):
            ids.update((int(row[S.RECORD_ID]), int(row[S.TARGET_RECORD_ID])))
        for affected_id in ids:
            Database._refresh_match_state(connection, affected_id)

    def resolve_match(self, candidate_id: int, *, accept: bool, note: str = S.EMPTY) -> int:
        with self._transaction() as connection:
            candidate = connection.execute(
                S.DATABASE_RESOLVE_MATCH_CANDIDATE_SELECT_MATCH_CANDIDATES_WHERE_ID, (candidate_id,)
            ).fetchone()
            if candidate is C.NONE or candidate[S.RESOLUTION] != S.PENDING:
                raise ValueError(
                    S.STORAGE_DATABASE_RESOLVE_MATCH_EXPECTED_A_PENDING_MATCH_CANDIDATE
                )
            record = connection.execute(
                S.STORAGE_DATABASE_COMPARISON_ROWS_SELECT_FROM_SOURCE_RECORDS_WHERE_ID,
                (candidate[S.RECORD_ID],),
            ).fetchone()
            target = connection.execute(
                S.STORAGE_DATABASE_COMPARISON_ROWS_SELECT_FROM_SOURCE_RECORDS_WHERE_ID,
                (candidate[S.TARGET_RECORD_ID],),
            ).fetchone()
            prior = (int(record[S.WORK_ID]), int(record[S.EDITION_ID]))
            current = prior
            if accept:
                comparison = compare_books(
                    BookRecord.model_validate_json(
                        self._payloads().load_text(record[S.LATEST_JSON])
                    ),
                    BookRecord.model_validate_json(
                        self._payloads().load_text(target[S.LATEST_JSON])
                    ),
                )
                if comparison.kind == MatchKind.CONFIRMED:
                    current = (int(target[S.WORK_ID]), int(target[S.EDITION_ID]))
                elif record[S.WORK_ID] != target[S.WORK_ID]:
                    edition_id = _insert_id(
                        connection.execute(
                            S.DATABASE_NEW_IDENTITY_EDITION_ID_INSERT_EDITIONS_WORK_ID_CREATED_AT,
                            (target[S.WORK_ID], utc_now()),
                        )
                    )
                    current = (int(target[S.WORK_ID]), edition_id)
                connection.execute(
                    S.STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_WORK_ID_EDITION,
                    (*current, record[S.ID]),
                )
            decision_id = self._decision(
                connection,
                record_id=int(record[S.ID]),
                candidate_id=candidate_id,
                kind=S.ACCEPTED if accept else S.REJECTED,
                prior=prior,
                current=current,
                prior_resolution=str(candidate[S.RESOLUTION]),
                evidence={
                    S.NOTE: note,
                    S.KIND: candidate[S.KIND],
                    S.REASON: candidate[S.REASON],
                    S.IDENTIFIERS: _parsed_json(candidate[S.IDENTIFIERS_JSON]),
                },
            )
            connection.execute(
                S.STORAGE_DATABASE_RESOLVE_MATCH_UPDATE_SET_RESOLUTION_WHERE_ID,
                (S.ACCEPTED if accept else S.REJECTED, candidate_id),
            )
            self._refresh_after_mapping_change(connection, int(record[S.ID]))
            return decision_id

    def undo_match(self, decision_id: int) -> int:
        with self._transaction() as connection:
            decision = connection.execute(
                S.DATABASE_UNDO_MATCH_DECISION_SELECT_FROM_MATCH_DECISIONS_WHERE_ID, (decision_id,)
            ).fetchone()
            if (
                decision is C.NONE
                or decision[S.REVERSED_BY] is not C.NONE
                or decision[S.KIND] == S.UNDO
            ):
                raise ValueError(
                    S.STORAGE_DATABASE_UNDO_MATCH_EXPECTED_AN_UNREVERSED_MATCHING_DECISION
                )
            later = connection.execute(
                S.DATABASE_UNDO_MATCH_LATER_SELECT_MATCH_DECISIONS_WHERE_RECORD_ID,
                (decision[S.RECORD_ID], decision_id),
            ).fetchone()
            record = connection.execute(
                S.DATABASE_SAVE_CANDIDATE_CURRENT_SELECT_ID_EDITION_ID_FROM_SOURCE,
                (decision[S.RECORD_ID],),
            ).fetchone()
            if later or (record[S.WORK_ID], record[S.EDITION_ID]) != (
                decision[S.WORK_ID],
                decision[S.EDITION_ID],
            ):
                raise ValueError(S.STORAGE_DATABASE_UNDO_MATCH_UNDO_LATER_MATCHING_DECISIONS_FIRST)
            prior = (int(decision[S.WORK_ID]), int(decision[S.EDITION_ID]))
            current = (int(decision[S.PRIOR_WORK_ID]), int(decision[S.PRIOR_EDITION_ID]))
            connection.execute(
                S.STORAGE_DATABASE_SAVE_RECORD_UPDATE_RECORDS_SET_WORK_ID_EDITION,
                (*current, decision[S.RECORD_ID]),
            )
            reverse_id = self._decision(
                connection,
                record_id=int(decision[S.RECORD_ID]),
                candidate_id=decision[S.CANDIDATE_ID],
                kind=S.UNDO,
                prior=prior,
                current=current,
                prior_resolution=C.NONE,
                evidence={S.REVERTS: decision_id},
            )
            connection.execute(
                S.STORAGE_DATABASE_UNDO_MATCH_UPDATE_DECISIONS_SET_REVERSED_BY_WHERE,
                (reverse_id, decision_id),
            )
            if decision[S.CANDIDATE_ID] is not C.NONE:
                # Undoing an invalidation is an explicit human override, not new ISBN evidence.
                connection.execute(
                    S.STORAGE_DATABASE_RESOLVE_MATCH_UPDATE_SET_RESOLUTION_WHERE_ID,
                    (
                        (
                            S.ACCEPTED
                            if decision[S.KIND]
                            in (
                                S.STORAGE_INVALIDATED_AUTOMATIC_MATCH,
                                S.MATCH_UPGRADE_PROVIDER_INVALIDATED,
                            )
                            else decision[S.PRIOR_RESOLUTION] or S.PENDING
                        ),
                        decision[S.CANDIDATE_ID],
                    ),
                )
            self._refresh_after_mapping_change(connection, int(decision[S.RECORD_ID]))
            if decision[S.KIND] == S.MATCH_UPGRADE_PROVIDER_AUTOMATIC:
                self._audit_automatic_isbn_matches(connection)
            return reverse_id

    def backup(self, path: Path) -> None:
        path = Path(path)
        if path.resolve() == self.path.resolve() or path.exists():
            raise ValueError(S.STORAGE_DATABASE_BACKUP_BACKUP_DESTINATION_MUST_BE_A_NEW_DISTINCT)
        path.parent.mkdir(parents=C.TRUE, exist_ok=C.TRUE)
        with path.open(S.XB):
            pass
        try:
            with closing(sqlite3.connect(str(path))) as destination:
                self._connection().backup(destination)
        except BaseException:
            path.unlink()
            raise
