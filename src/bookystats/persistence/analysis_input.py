from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from collections.abc import Callable

from pydantic import ValidationError

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisEvidence,
    AnalysisInput,
    AnalysisManifest,
    AnalysisMetadata,
    AnalysisSnapshot,
    AnalyticsSettings,
    PossibleReadMatch,
)
from bookystats.domain.categories import analytical_categories
from bookystats.domain.errors import BookyError
from bookystats.domain.models import (
    Account,
    BookRecord,
    CollectionSnapshot,
    FieldState,
    Issue,
    MetadataCandidate,
    Observation,
    PartialDate,
    ReadingStatus,
    Source,
    SupplementalCompletionDate,
    SyncState,
)
from bookystats.persistence.payloads import PayloadStore, canonical_json


class AnalyticsInputError(BookyError):
    pass


@C.frozen_dataclass
class _Record:
    record_id: int
    work_id: int
    book: BookRecord
    collections: tuple[str, ...]


def _present(evidence: list[AnalysisEvidence], field: str) -> list[AnalysisEvidence]:
    return [
        item
        for item in evidence
        if item.observation.field == field and item.observation.state == FieldState.PRESENT
    ]


def _scalar(
    evidence: list[AnalysisEvidence], field: str, *, scope: S.ObservationScope | None = C.NONE
) -> str | int | float | None:
    items = [
        item
        for item in _present(evidence, field)
        if scope is C.NONE or item.observation.scope == scope
    ]
    preferred = [item for item in items if item.source == Source.GOODREADS.value]
    values = {
        canonical_json(item.observation.value): item.observation.value
        for item in preferred or items
    }
    if len(values) != C.ONE:
        return C.NONE
    value = next(iter(values.values()))
    return value if isinstance(value, (str, int, float)) and not isinstance(value, bool) else C.NONE


def _publication_year(value: str | int | float | None) -> int | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return C.NONE
    try:
        date = PartialDate(value=str(value))
    except ValidationError:
        return C.NONE
    return int(date.value.split(S.HYPHEN)[C.ZERO])


def _description(evidence: list[AnalysisEvidence]) -> str | None:
    items = [
        item
        for item in _present(evidence, S.DESCRIPTION)
        if item.observation.scope == S.WORK
        and isinstance(item.observation.value, str)
        and item.observation.value.strip()
    ]
    preferred = [item for item in items if item.source == Source.GOODREADS.value]
    descriptions = [
        item.observation.value
        for item in preferred or items
        if isinstance(item.observation.value, str)
    ]
    return max(descriptions, key=lambda value: (len(value), value)) if descriptions else C.NONE


def _missing_state(
    evidence: list[AnalysisEvidence], field: str, *, aliases: tuple[str, ...] = ()
) -> FieldState:
    states = {
        item.observation.state for item in evidence if item.observation.field in (field, *aliases)
    }
    if FieldState.FAILED in states or FieldState.PRESENT in states:
        return FieldState.FAILED
    if len(states) == C.ONE and FieldState.EMPTY in states:
        return FieldState.EMPTY
    if len(states) == C.ONE and FieldState.UNSUPPORTED in states:
        return FieldState.UNSUPPORTED
    return FieldState.UNAVAILABLE


def _work(
    work_id: int,
    records: list[_Record],
    rating_evidence: list[AnalysisEvidence],
    supplemental_dates: list[SupplementalCompletionDate],
    metadata: dict[int, list[AnalysisEvidence]],
    work_metadata: dict[int, list[AnalysisEvidence]],
    settings: AnalyticsSettings,
) -> AnalysisBook:
    collections = tuple(sorted({scope for record in records for scope in record.collections}))
    source_ids = tuple(sorted(record.book.source_id for record in records))
    read_records = [
        record
        for record in records
        if S.READ in record.collections or record.book.status == ReadingStatus.READ
    ]
    records = read_records or records
    primary = records[C.ZERO].book
    evidence = [
        AnalysisEvidence(
            source=Source.GOODREADS.value,
            source_id=record.book.source_id,
            observation=item,
            public_url=record.book.url,
        )
        for record in records
        for item in record.book.observations
        if item.field != S.RATING
    ]
    evidence.extend(item for record in records for item in metadata.get(record.record_id, ()))
    evidence.extend(work_metadata.get(work_id, ()))
    evidence.extend(rating_evidence)
    supplemental_evidence = [
        AnalysisEvidence(
            source=item.source.value,
            source_id=item.source_id,
            observation=item.observation,
            detail=S.DTX_SUPPLEMENTAL_LINEAGE,
        )
        for item in supplemental_dates
    ]
    evidence.extend(supplemental_evidence)
    states: dict[str, FieldState] = {}
    features: dict[str, tuple[str, ...]] = {}
    for field in C.AN_FEATURE_FIELDS:
        items = [
            item
            for item in _present(evidence, field)
            if field not in C.AV_FEATURE_SCOPES
            or item.observation.scope == C.AV_FEATURE_SCOPES[field]
        ]
        if field == S.GENRES:
            items = [
                item
                for item in items
                if item.source in C.ANALYTIC_CATEGORY_SOURCES and item.observation.scope == S.WORK
            ]
        preferred = [item for item in items if item.source == Source.GOODREADS.value]
        labels: set[str] = set()
        for item in preferred or items:
            value = item.observation.value
            for label in value if isinstance(value, list) else [value]:
                if isinstance(label, str) and label.strip():
                    labels.add(S.SPACE.join(label.split()).casefold())
        if field == S.GENRES:
            labels = set(analytical_categories(labels))
            for item in items:
                value = item.observation.value
                categories = (
                    analytical_categories(label for label in value if isinstance(label, str))
                    if isinstance(value, list)
                    else (analytical_categories((value,)) if isinstance(value, str) else ())
                )
                if categories:
                    evidence.append(
                        AnalysisEvidence(
                            source=item.source,
                            source_id=item.source_id,
                            public_url=item.public_url,
                            detail=S.ANALYTIC_CATEGORY_VERSION,
                            observation=item.observation.model_copy(
                                update={
                                    S.FIELD: S.ANALYTIC_CATEGORY_FIELD,
                                    S.VALUE: list(categories),
                                }
                            ),
                        )
                    )
        if labels:
            features[field] = tuple(sorted(labels))
            states[field] = FieldState.PRESENT
        else:
            states[field] = (
                FieldState.UNAVAILABLE
                if field == S.GENRES and _present(evidence, field)
                else _missing_state(evidence, field)
            )
    declared = [label for label in settings.book_labels if label.goodreads_id in source_ids]
    if declared:
        features[S.AN_APPETITE] = tuple(sorted({label.dimension for label in declared}))
        evidence.extend(
            AnalysisEvidence(
                source=S.AN_DECLARED,
                source_id=label.goodreads_id,
                detail=label.evidence,
                observation=Observation(
                    field=S.AN_APPETITE,
                    value=label.dimension,
                    state=FieldState.PRESENT,
                    source_url=S.CONFIG_JSON,
                ),
            )
            for label in declared
        )
    ratings = {
        float(item.observation.value)
        for item in rating_evidence
        if item.source == Source.STORYGRAPH.value
        and item.observation.field == S.RATING
        and item.observation.scope == S.READER
        and item.observation.state == FieldState.PRESENT
        and isinstance(item.observation.value, (int, float))
        and not isinstance(item.observation.value, bool)
        and C.ZERO <= item.observation.value <= C.FIVE
    }
    rating = next(iter(ratings)) if len(ratings) == C.ONE else C.NONE
    states[S.RATING] = (
        FieldState.PRESENT
        if rating is not C.NONE
        else FieldState.FAILED
        if len(ratings) > C.ONE
        else _missing_state(rating_evidence, S.RATING)
    )
    community: dict[str, float] = {}
    for provider in C.AN_COMMUNITY_SOURCES:
        value = _scalar([item for item in evidence if item.source == provider], S.COMMUNITY_RATING)
        if isinstance(value, (int, float)) and C.ZERO <= value <= C.FIVE:
            community[provider] = float(value)
    pages = _scalar(evidence, S.PAGE_COUNT, scope=S.EDITION)
    publication = _scalar(evidence, S.PUBLICATION_DATE, scope=S.EDITION)
    first_publication = [
        item
        for item in evidence
        if item.observation.field in (S.IMPORT_BROWSER_FIRST_PUBLICATION, S.FIRST_PUBLICATION_YEAR)
        and item.observation.scope == S.WORK
        and item.observation.state == FieldState.PRESENT
    ]
    preferred_first = [item for item in first_publication if item.source == Source.GOODREADS.value]
    first_years = {
        _publication_year(item.observation.value)
        for item in preferred_first or first_publication
        if isinstance(item.observation.value, (str, int, float))
        and not isinstance(item.observation.value, bool)
    }
    first_year = next(iter(first_years)) if len(first_years) == C.ONE else C.NONE
    description = _description(evidence)
    review = _scalar([item for item in evidence if item.source == Source.GOODREADS.value], S.REVIEW)
    year = _publication_year(publication)
    pages = pages if isinstance(pages, int) and pages > C.ZERO else C.NONE
    review = review if isinstance(review, str) and review.strip() else C.NONE
    description = description if isinstance(description, str) and description.strip() else C.NONE
    for field, value in (
        (S.PAGE_COUNT, pages),
        (S.PUBLICATION_DATE, year),
        (S.REVIEW, review),
        (S.DESCRIPTION, description),
    ):
        states[field] = (
            FieldState.PRESENT if value is not C.NONE else _missing_state(evidence, field)
        )
    states[S.FIRST_PUBLICATION_YEAR] = (
        FieldState.PRESENT
        if first_year is not C.NONE
        else FieldState.FAILED
        if first_publication
        else _missing_state(
            evidence, S.FIRST_PUBLICATION_YEAR, aliases=(S.IMPORT_BROWSER_FIRST_PUBLICATION,)
        )
    )
    added = {record.book.added_at.value for record in records if record.book.added_at is not C.NONE}
    completion_values = {
        item.finished.value
        for item in supplemental_dates
        if item.finished is not C.NONE and item.observation.state == FieldState.PRESENT
    }
    states[S.DTX_SUPPLEMENTAL_COMPLETION_DATE] = (
        FieldState.FAILED
        if len(completion_values) > C.ONE
        else FieldState.PRESENT
        if completion_values
        else _missing_state(supplemental_evidence, S.DTX_SUPPLEMENTAL_COMPLETION_DATE)
    )
    return AnalysisBook(
        work_id=work_id,
        source_ids=source_ids,
        title=primary.title,
        authors=tuple(sorted({author for record in records for author in record.book.authors})),
        collections=collections,
        status=ReadingStatus.READ if read_records else primary.status,
        rating=rating,
        rating_conflict=len(ratings) > C.ONE,
        features=features,
        page_count=pages,
        publication_year=year,
        first_publication_year=first_year,
        description=description,
        review=review,
        community_ratings=community,
        reading_events=tuple(event for record in records for event in record.book.reading_events),
        supplemental_completion_dates=tuple(supplemental_dates),
        added_at=PartialDate(value=next(iter(added))) if len(added) == C.ONE else C.NONE,
        field_states=states,
        evidence=tuple(evidence),
    )


def read_analytics_input(
    connection: sqlite3.Connection,
    payloads: PayloadStore,
    accounts: tuple[Account, ...],
    settings: AnalyticsSettings,
    identity_hash: Callable[[BookRecord], str],
) -> AnalysisInput:
    configured = {account.source.value: account.account_id for account in accounts}
    bound = {row[S.SOURCE]: row[S.ACCOUNT_ID] for row in connection.execute(S.AN_INPUT_ACCOUNTS)}
    if not configured or any(
        bound.get(source) != account for source, account in configured.items()
    ):
        raise AnalyticsInputError(S.AN_INPUT_ACCOUNT_ERROR)
    snapshots: list[AnalysisSnapshot] = []
    pinned: dict[tuple[str, str, str], BookRecord] = {}
    counts: dict[str, int] = {}
    completion_counts: dict[str, int] = {}
    for row in connection.execute(S.AN_INPUT_SNAPSHOTS):
        if row[S.SOURCE] not in configured:
            continue
        if (
            row[S.ACCOUNT_ID] != configured[row[S.SOURCE]]
            or row[S.STATE] != SyncState.COMPLETE.value
        ):
            raise AnalyticsInputError(S.AN_INPUT_INCOMPLETE)
        snapshot = CollectionSnapshot.model_validate_json(
            payloads.load_collection_json(row[S.RAW_JSON])
        )
        if (
            snapshot.state != SyncState.COMPLETE
            or snapshot.source.value != row[S.SOURCE]
            or snapshot.account_id != row[S.ACCOUNT_ID]
            or snapshot.collection != row[S.COLLECTION]
            or not snapshot.raw_document_id
            or not row[S.AN_PUBLISHED]
        ):
            raise AnalyticsInputError(S.AN_INPUT_LINEAGE_ERROR)
        counts[S.AN_SCOPE.format(source=snapshot.source.value, collection=snapshot.collection)] = (
            len(snapshot.records)
        )
        if snapshot.source == Source.STORYGRAPH:
            completion_counts.update(
                {
                    key: sum(
                        any(
                            item.observation.state == state
                            for item in book.supplemental_completion_dates
                        )
                        or (
                            state == FieldState.UNSUPPORTED
                            and not book.supplemental_completion_dates
                        )
                        for book in snapshot.records
                    )
                    for state, key in C.DTX_SOURCE_COMPLETION_STATE_KEYS.items()
                }
            )
        pinned.update(
            ((snapshot.source.value, snapshot.collection, book.source_id), book)
            for book in snapshot.records
        )
        snapshots.append(
            AnalysisSnapshot(
                source=snapshot.source,
                account_id=snapshot.account_id,
                collection=snapshot.collection,
                snapshot_id=row[S.ACTIVE_SNAPSHOT_ID],
                raw_document_id=snapshot.raw_document_id,
                processing_version=snapshot.processing_version,
                input_kind=snapshot.input_kind,
                finished_at=snapshot.finished_at,
                records=len(snapshot.records),
                attempt_state=SyncState(row[S.STATE]),
            )
        )
    if {item.source.value for item in snapshots} != configured.keys():
        raise AnalyticsInputError(S.AN_INPUT_INCOMPLETE)
    goodreads_scopes = {item.collection for item in snapshots if item.source == Source.GOODREADS}
    if S.LIBRARY in goodreads_scopes and goodreads_scopes.intersection((S.READ, S.TO_READ)):
        raise AnalyticsInputError(S.CLI_GOODREADS_SCOPE_CONFLICT)
    rows = list(connection.execute(S.AN_INPUT_RECORDS))
    membership: dict[int, set[str]] = defaultdict(set)
    records: dict[int, _Record] = {}
    for row in rows:
        if configured.get(row[S.SOURCE]) != row[S.ACCOUNT_ID]:
            continue
        record_id = int(row[S.ID])
        membership[record_id].add(row[S.COLLECTION])
        if record_id not in records:
            book = BookRecord.model_validate_json(payloads.load_text(row[S.LATEST_JSON]))
            if book.source.value != row[S.SOURCE] or book.source_id != row[S.SOURCE_ID]:
                raise AnalyticsInputError(S.AN_INPUT_LINEAGE_ERROR)
            records[record_id] = _Record(
                record_id,
                int(row[S.WORK_ID]),
                book,
                (),
            )
        key = (row[S.SOURCE], row[S.COLLECTION], row[S.SOURCE_ID])
        if key not in pinned:
            raise AnalyticsInputError(S.AN_INPUT_LINEAGE_ERROR)
        if identity_hash(pinned[key]) != row[S.IDENTITY_HASH]:
            raise AnalyticsInputError(S.AN_INPUT_LINEAGE_ERROR)
        if row[S.COLLECTION] == S.READ or S.READ not in membership[record_id]:
            record = records[record_id]
            records[record_id] = _Record(record_id, record.work_id, pinned[key], ())
    if any(record.book.source.value not in configured for record in records.values()):
        raise AnalyticsInputError(S.AN_INPUT_ACCOUNT_ERROR)
    metadata: dict[int, list[AnalysisEvidence]] = defaultdict(list)
    work_metadata: dict[int, list[AnalysisEvidence]] = defaultdict(list)
    catalog_work_ids = {
        record.work_id for record in records.values() if record.book.source == Source.GOODREADS
    }
    references: list[AnalysisMetadata] = []
    for row in connection.execute(S.AN_INPUT_METADATA):
        record_id = int(row[S.RECORD_ID])
        if record_id not in records or records[record_id].work_id not in catalog_work_ids:
            continue
        payload = payloads.load_text(row[S.CANDIDATE_JSON])
        candidate = MetadataCandidate.model_validate_json(payload)
        if candidate.provider.value != row[S.PROVIDER]:
            raise AnalyticsInputError(S.AN_INPUT_LINEAGE_ERROR)
        origin = records[record_id].book
        via_personal_source = origin.source == Source.STORYGRAPH
        origin_id = (
            S.AN_METADATA_ORIGIN.format(source=origin.source.value, source_id=origin.source_id)
            if via_personal_source
            else origin.source_id
        )
        provider_evidence = [
            AnalysisEvidence(
                source=candidate.provider.value,
                source_id=candidate.provider_id,
                observation=observation,
                detail=origin_id if via_personal_source else C.NONE,
            )
            for observation in candidate.observations
            if observation.scope != S.READER
            and (not via_personal_source or observation.scope == S.WORK)
        ]
        work_metadata[records[record_id].work_id].extend(
            item for item in provider_evidence if item.observation.scope == S.WORK
        )
        metadata[record_id].extend(
            item for item in provider_evidence if item.observation.scope != S.WORK
        )
        if not provider_evidence:
            continue
        references.append(
            AnalysisMetadata(
                source_id=origin_id,
                provider=candidate.provider,
                attempt_id=row[S.AN_ATTEMPT_ID],
                candidate_id=row[S.CANDIDATE_ID],
                checked_at=row[S.AN_CHECKED_AT],
                payload_hash=hashlib.sha256(payload.encode(S.UTF_8)).hexdigest(),
            )
        )
    groups: dict[int, list[_Record]] = defaultdict(list)
    ratings: dict[int, list[AnalysisEvidence]] = defaultdict(list)
    supplemental: dict[int, list[SupplementalCompletionDate]] = defaultdict(list)
    personal_count = C.ZERO
    for record_id, record in records.items():
        if record.book.source == Source.GOODREADS:
            groups[record.work_id].append(
                _Record(
                    record.record_id,
                    record.work_id,
                    record.book,
                    tuple(sorted(membership[record_id])),
                )
            )
        elif record.book.source == Source.STORYGRAPH:
            supplemental[record.work_id].extend(record.book.supplemental_completion_dates)
            observations = [item for item in record.book.observations if item.field == S.RATING]
            ratings[record.work_id].extend(
                AnalysisEvidence(
                    source=Source.STORYGRAPH.value,
                    source_id=record.book.source_id,
                    observation=item,
                )
                for item in observations
            )
            personal_count += any(item.state == FieldState.PRESENT for item in observations)
    settings_hash = hashlib.sha256(
        canonical_json(settings.model_dump(mode=S.JSON)).encode(S.UTF_8)
    ).hexdigest()
    fingerprint = hashlib.sha256(
        json.dumps(sorted(configured.items()), separators=(S.COMMA, S.COLON)).encode(S.UTF_8)
    ).hexdigest()
    issues = (
        (Issue(code=S.AN_NO_READ_DATA, message=S.AN_NO_READ_DATA_MESSAGE),)
        if S.AN_READ_SCOPE not in counts and S.LIBRARY not in goodreads_scopes
        else ()
    )
    possible: dict[int, list[PossibleReadMatch]] = defaultdict(list)
    for row in connection.execute(S.REC_PENDING_MATCHES):
        left, right = int(row[S.RECORD_ID]), int(row[S.REC_TARGET_RECORD_ID])
        if left not in records or right not in records:
            continue
        for candidate_origin_id, candidate_target_id in ((left, right), (right, left)):
            candidate_origin = records[candidate_origin_id]
            target = records[candidate_target_id]
            if (
                candidate_origin.book.source != Source.GOODREADS
                or candidate_origin.work_id == target.work_id
                or not (
                    S.READ in membership[candidate_target_id]
                    or (
                        target.book.source == Source.GOODREADS
                        and target.book.status == ReadingStatus.READ
                    )
                    or target.book.source == Source.STORYGRAPH
                )
            ):
                continue
            possible[candidate_origin.work_id].append(
                PossibleReadMatch(
                    candidate_id=int(row[S.ID]),
                    work_id=target.work_id,
                    source=target.book.source,
                    source_id=target.book.source_id,
                    source_snapshot_ids=tuple(
                        item.snapshot_id
                        for item in snapshots
                        if item.source == target.book.source
                        and item.collection in membership[candidate_target_id]
                    ),
                )
            )
    return AnalysisInput(
        books=tuple(
            _work(
                work_id,
                records,
                ratings[work_id],
                supplemental[work_id],
                metadata,
                work_metadata,
                settings,
            ).model_copy(update={S.REC_POSSIBLE_READ_MATCHES: tuple(possible[work_id])})
            for work_id, records in sorted(groups.items())
        ),
        manifest=AnalysisManifest(
            account_fingerprint=fingerprint,
            snapshots=tuple(snapshots),
            metadata=tuple(references),
            settings_hash=settings_hash,
            settings=settings,
        ),
        source_counts=counts,
        supplemental_completion_counts=completion_counts,
        personal_rating_records=personal_count,
        issues=issues,
    )
