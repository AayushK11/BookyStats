from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.content_analysis import description_provenance
from bookystats.domain.analytics import (
    AnalysisBook,
    AnalysisInput,
    AnalyticsSettings,
    DeclaredLabel,
)
from bookystats.domain.models import (
    BookRecord,
    EnrichmentResult,
    FieldState,
    Issue,
    Observation,
    PartialDate,
    ReadingEvent,
    ReadingStatus,
    Source,
    SupplementalCompletionDate,
    SyncState,
)
from bookystats.persistence.analysis_input import AnalyticsInputError
from bookystats.persistence.library import Database, _identity_hash, _semantic_hash
from tests.persistence.test_library import book, metadata_candidate, publish, rating, snapshot
from tests.support.sources import accounts


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Database]:
    db = Database(tmp_path / S.LIBRARY_SQLITE3)
    db.initialize()
    try:
        yield db
    finally:
        db.close()


def publish_scope(
    db: Database,
    source: Source,
    *records: BookRecord,
    collection: str = S.LIBRARY,
    state: SyncState = SyncState.COMPLETE,
) -> None:
    account = next(account for account in accounts() if account.source == source)
    data = snapshot(
        *records,
        source=source,
        account_id=account.account_id,
        collection=collection,
        state=state,
    ).model_copy(update={S.INPUT_RAW_DOCUMENT_ID: S.ONE_2})
    if state == SyncState.COMPLETE:
        publish(db, data)
    else:
        run = db.start_run(S.TEST)
        db.save_snapshot(run, data)
        db.finish_run(run, state)


def seed(db: Database) -> BookRecord:
    personal = book(**{S.OBSERVATIONS: (rating(C.FOUR),)})
    catalog = book(
        **{
            S.SOURCE: Source.GOODREADS,
            S.OBSERVATIONS: (
                rating(C.ONE),
                rating(C.THREE, field=S.COMMUNITY_RATING),
            ),
        }
    )
    publish_scope(db, Source.STORYGRAPH, personal)
    publish_scope(db, Source.GOODREADS, catalog, collection=S.READ)
    return catalog


def test_uses_confirmed_links_and_keeps_rating_authority_separate(library: Database) -> None:
    seed(library)
    data = library.analytics_input(accounts(), AnalyticsSettings())
    assert len(data.books) == C.ONE
    result = data.books[C.ZERO]
    assert result.rating == C.FOUR
    assert result.community_ratings == {Source.GOODREADS.value: C.THREE}
    assert data.personal_rating_records == C.ONE
    assert len(data.manifest.snapshots) == C.TWO
    assert all(
        item.source != Source.GOODREADS.value
        for item in result.evidence
        if item.observation.field == S.RATING
    )


def test_possible_read_candidates_are_active_scoped_evidence_not_confirmed_links(
    library: Database,
) -> None:
    seed(library)
    watch = book(
        **{
            S.SOURCE: Source.GOODREADS,
            S.SOURCE_ID: S.TEST_IMPORT_SECOND_ID,
            S.TITLE: S.TEST_IMPORT_OTHER_TITLE,
            S.ISBNS: (),
            S.STATUS: ReadingStatus.TO_READ,
        }
    )
    publish_scope(library, Source.GOODREADS, watch, collection=S.TO_READ)
    connection = library._connection()
    rows = connection.execute(S.REC_TEST_RECORDS, (Source.GOODREADS.value,)).fetchall()
    left, right = rows[C.ONE][S.ID], rows[C.ZERO][S.ID]
    snapshot_id = connection.execute(S.REC_TEST_SNAPSHOT).fetchone()[C.ZERO]
    with connection:
        connection.execute(S.REC_TEST_PENDING, (left, right, snapshot_id, snapshot_id))
    pinned = library.analytics_input(accounts(), AnalyticsSettings())
    candidate = next(item for item in pinned.books if watch.source_id in item.source_ids)
    completed = next(item for item in pinned.books if S.READ in item.collections)
    assert candidate.work_id != completed.work_id
    assert len(candidate.possible_read_matches) == C.ONE
    possible = candidate.possible_read_matches[C.ZERO]
    assert possible.work_id == completed.work_id
    assert possible.source == Source.GOODREADS
    assert possible.source_snapshot_ids
    publish_scope(library, Source.GOODREADS, collection=S.READ)
    changed = library.analytics_input(accounts(), AnalyticsSettings())
    candidate = next(item for item in changed.books if watch.source_id in item.source_ids)
    assert not candidate.possible_read_matches


def supplemental(
    value: str = S.DTX_TEST_DAY, source_id: str = S.ONE_2
) -> SupplementalCompletionDate:
    return SupplementalCompletionDate(
        source_id=source_id,
        finished=PartialDate(value=value, raw=value),
        observation=Observation(
            field=S.DTX_SUPPLEMENTAL_COMPLETION_DATE,
            value=value,
            scope=S.READER,
            state=FieldState.PRESENT,
            source_url=S.TEST_IMPORT_ORIGIN,
            observed_at=S.TEST_IMPORT_CAPTURED_AT,
        ),
    )


def _assert_no_storygraph_date(data: AnalysisInput) -> AnalysisBook:
    result = data.books[C.ZERO]
    text = data.model_dump_json()
    assert not result.goodreads_completion_dates
    assert S.DTX_SUPPLEMENTAL_COMPLETION_DATE not in result.field_states
    assert S.DTX_SUPPLEMENTAL_COMPLETION_DATE not in text
    assert S.DTX_TEST_DAY not in text
    return result


def test_legacy_storygraph_supplemental_dates_never_enter_analysis_input(
    library: Database,
) -> None:
    date = supplemental()
    personal = book(
        **{
            S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (date,),
            S.OBSERVATIONS: (rating(C.FOUR), date.observation),
        }
    )
    catalog = book(**{S.SOURCE: Source.GOODREADS, S.ADDED_AT: PartialDate(value=S.DTX_TEST_YEAR)})
    publish_scope(library, Source.STORYGRAPH, personal)
    publish_scope(library, Source.GOODREADS, catalog, collection=S.READ)
    data = library.analytics_input(accounts(), AnalyticsSettings())
    result = _assert_no_storygraph_date(data)
    assert result.rating == C.FOUR
    assert not result.reading_events
    assert result.added_at == catalog.added_at
    assert data.personal_rating_records == C.ONE
    assert any(
        item.source == Source.STORYGRAPH.value and item.observation.field == S.RATING
        for item in result.evidence
    )


def test_unlinked_legacy_storygraph_dates_leave_no_analysis_trace(library: Database) -> None:
    date = supplemental()
    publish_scope(
        library,
        Source.STORYGRAPH,
        book(
            **{
                S.ISBNS: (),
                S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (date,),
                S.OBSERVATIONS: (date.observation,),
            }
        ),
    )
    publish_scope(
        library,
        Source.GOODREADS,
        book(**{S.SOURCE: Source.GOODREADS, S.ISBNS: ()}),
        collection=S.READ,
    )
    data = library.analytics_input(accounts(), AnalyticsSettings())
    result = _assert_no_storygraph_date(data)
    assert result.rating is C.NONE
    assert not result.reading_events


def test_goodreads_history_is_unchanged_by_conflicting_storygraph_dates(
    library: Database,
) -> None:
    dates = (supplemental(), supplemental(S.DTX_TEST_OTHER_DATE, S.TEST_IMPORT_SECOND_ID))
    publish_scope(
        library,
        Source.STORYGRAPH,
        *(
            book(
                **{
                    S.SOURCE_ID: date.source_id,
                    S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (date,),
                    S.OBSERVATIONS: (date.observation,),
                }
            )
            for date in dates
        ),
    )
    event = ReadingEvent(finished=PartialDate(value=S.DTX_TEST_YEAR), status=ReadingStatus.READ)
    publish_scope(
        library,
        Source.GOODREADS,
        book(**{S.SOURCE: Source.GOODREADS, S.READING_EVENTS: (event,)}),
        collection=S.READ,
    )
    data = library.analytics_input(accounts(), AnalyticsSettings())
    result = _assert_no_storygraph_date(data)
    assert S.DTX_TEST_OTHER_DATE not in data.model_dump_json()
    assert result.reading_events == (event,)


def test_supplemental_capture_time_does_not_change_record_semantics() -> None:
    date = supplemental()
    changed = date.model_copy(
        update={
            S.DTX_OBSERVATION: date.observation.model_copy(
                update={S.OBSERVED_AT: S.TEST_STORAGE_START_T10}
            ),
        }
    )
    original = book(**{S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (date,)})
    recaptured = original.model_copy(update={S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (changed,)})
    assert _semantic_hash(original) == _semantic_hash(recaptured)
    changed_date = original.model_copy(
        update={
            S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (supplemental(S.DTX_TEST_OTHER_DATE),),
        }
    )
    assert _semantic_hash(original) != _semantic_hash(changed_date)


def test_supplemental_date_changes_preserve_provider_identity_and_queue(
    library: Database,
) -> None:
    date = supplemental()
    original = book(
        **{
            S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (date,),
            S.OBSERVATIONS: (date.observation,),
        }
    )
    publish_scope(library, Source.STORYGRAPH, original)
    library.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=original.source_id,
            state=SyncState.COMPLETE,
            candidates=(metadata_candidate(),),
        ),
    )
    assert library.enrichment_targets(Source.GOOGLE_BOOKS) == ()
    changed = supplemental(S.DTX_TEST_OTHER_DATE)
    updated = original.model_copy(
        update={
            S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (changed,),
            S.OBSERVATIONS: (changed.observation,),
        }
    )
    assert _identity_hash(updated) == _identity_hash(original)
    assert _semantic_hash(updated) != _semantic_hash(original)
    publish_scope(library, Source.STORYGRAPH, updated)
    personal_account = next(
        account for account in accounts() if account.source == Source.STORYGRAPH
    )
    assert not library.metadata_for(
        Source.STORYGRAPH, personal_account.account_id, updated.source_id
    )[C.ZERO][S.STALE_IDENTITY]
    assert library.enrichment_targets(Source.GOOGLE_BOOKS) == ()


@pytest.mark.parametrize(S.ANALYTIC_CATEGORY_TEST_PARAMETERS, C.ANALYTIC_CATEGORY_TEST_CASES)
def test_provider_genre_families_retain_raw_subjects_and_mapping_provenance(
    library: Database, labels: tuple[str, ...], expected: tuple[str, ...]
) -> None:
    catalog = seed(library)
    candidate = metadata_candidate()
    observation = Observation(
        field=S.GENRES,
        value=list(labels),
        scope=S.EDITION,
        state=FieldState.PRESENT,
        source_url=candidate.url,
    )
    candidate = candidate.model_copy(update={S.OBSERVATIONS: (observation,)})
    library.save_enrichment(
        Source.GOODREADS,
        candidate.provider,
        EnrichmentResult(
            source_id=catalog.source_id,
            state=SyncState.COMPLETE,
            candidates=(candidate,),
        ),
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.features.get(S.GENRES, ()) == expected
    assert result.field_states[S.GENRES] == (
        FieldState.PRESENT if expected else FieldState.UNAVAILABLE
    )
    assert any(item.observation == observation for item in result.evidence)
    derived = [
        item for item in result.evidence if item.observation.field == S.ANALYTIC_CATEGORY_FIELD
    ]
    assert bool(derived) == bool(expected)
    if expected:
        assert derived[C.ZERO].observation.value == list(expected)
        assert derived[C.ZERO].observation.source_url == observation.source_url
        assert derived[C.ZERO].source == candidate.provider.value
        assert derived[C.ZERO].detail == S.ANALYTIC_CATEGORY_VERSION


def test_browser_and_personal_genre_labels_are_not_provider_genre_evidence(
    library: Database,
) -> None:
    catalog = seed(library)
    observation = Observation(
        field=S.GENRES,
        value=[S.ANALYTIC_CATEGORY_FANTASY],
        scope=S.WORK,
        state=FieldState.PRESENT,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    unverified = observation.model_copy(update={S.FIELD: S.DQ_CAPTURE_UNVERIFIED_GENRES})
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(update={S.OBSERVATIONS: (observation, unverified)}),
        collection=S.READ,
    )
    publish_scope(
        library,
        Source.STORYGRAPH,
        book(**{S.OBSERVATIONS: (rating(C.FOUR), observation)}),
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert S.GENRES not in result.features
    assert result.field_states[S.GENRES] == FieldState.UNAVAILABLE
    assert result.rating == C.FOUR
    assert any(item.observation == unverified for item in result.evidence)
    assert not any(
        item.source == Source.STORYGRAPH.value and item.observation.field == S.GENRES
        for item in result.evidence
    )


def test_reader_scoped_provider_genres_do_not_become_work_categories(
    library: Database,
) -> None:
    catalog = seed(library)
    candidate = metadata_candidate()
    observation = Observation(
        field=S.GENRES,
        value=[S.ANALYTIC_CATEGORY_FANTASY],
        scope=S.READER,
        state=FieldState.PRESENT,
        source_url=candidate.url,
    )
    library.save_enrichment(
        Source.GOODREADS,
        candidate.provider,
        EnrichmentResult(
            source_id=catalog.source_id,
            state=SyncState.COMPLETE,
            candidates=(candidate.model_copy(update={S.OBSERVATIONS: (observation,)}),),
        ),
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert S.GENRES not in result.features
    assert not any(
        item.source == candidate.provider.value and item.observation.scope == S.READER
        for item in result.evidence
    )


def test_ambiguous_title_author_match_does_not_transfer_a_rating(library: Database) -> None:
    publish_scope(
        library, Source.STORYGRAPH, book(**{S.ISBNS: (), S.OBSERVATIONS: (rating(C.FIVE),)})
    )
    publish_scope(
        library,
        Source.GOODREADS,
        book(**{S.SOURCE: Source.GOODREADS, S.ISBNS: ()}),
        collection=S.READ,
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.rating is C.NONE
    assert result.field_states[S.RATING] == FieldState.UNAVAILABLE


def test_conflicting_confirmed_ratings_are_not_averaged(library: Database) -> None:
    seed(library)
    publish_scope(
        library,
        Source.STORYGRAPH,
        book(**{S.OBSERVATIONS: (rating(C.FOUR),)}),
        book(**{S.SOURCE_ID: S.TEST_IMPORT_SECOND_ID, S.OBSERVATIONS: (rating(C.FIVE),)}),
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.rating is C.NONE
    assert result.rating_conflict
    assert result.field_states[S.RATING] == FieldState.FAILED


def test_selected_metadata_is_pinned_and_invalidated_by_identity_changes(library: Database) -> None:
    catalog = seed(library)
    library.save_enrichment(
        Source.GOODREADS,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=catalog.source_id,
            state=SyncState.COMPLETE,
            candidates=(metadata_candidate(),),
        ),
    )
    data = library.analytics_input(accounts(), AnalyticsSettings())
    assert len(data.manifest.metadata) == C.ONE
    assert data.books[C.ZERO].page_count is not C.NONE
    changed = catalog.model_copy(update={S.TITLE: S.TEST_IMPORT_OTHER_TITLE})
    publish_scope(library, Source.GOODREADS, changed, collection=S.READ)
    updated = library.analytics_input(accounts(), AnalyticsSettings())
    assert not updated.manifest.metadata
    assert updated.books[C.ZERO].page_count is C.NONE


def test_wikidata_work_facts_are_pinned_without_borrowing_edition_values(
    library: Database,
) -> None:
    catalog = seed(library)
    reference = S.WIKIDATA_WORK_URL.format(v0=S.WIKIDATA_TEST_ID)
    candidate = metadata_candidate(
        provider=Source.WIKIDATA,
        provider_id=S.WIKIDATA_TEST_ID,
        work_id=S.WIKIDATA_TEST_ID,
        edition_id=C.NONE,
        isbns=(),
        url=reference,
        observations=tuple(
            Observation(
                field=field,
                value=value,
                state=FieldState.FAILED if value is C.NONE else FieldState.PRESENT,
                scope=S.WORK,
                source_url=reference,
            )
            for field, value in (
                (S.GENRES, [S.ANALYTIC_CATEGORY_FANTASY]),
                (S.FIRST_PUBLICATION_YEAR, S.WIKIDATA_TEST_YEAR),
                (S.LANGUAGE, S.FR),
                (S.PAGE_COUNT, C.TEST_STORAGE_METADATA_CANDIDATE),
                (S.WD_ORIGINAL_LANGUAGE, C.NONE),
            )
        ),
    )
    library.save_enrichment(
        Source.GOODREADS,
        Source.WIKIDATA,
        EnrichmentResult(
            source_id=catalog.source_id,
            state=SyncState.PARTIAL,
            candidates=(candidate,),
            issues=(
                Issue(
                    code=S.INVALID_METADATA_FIELD,
                    message=S.TEST,
                ),
            ),
        ),
    )
    data = library.analytics_input(accounts(), AnalyticsSettings())
    result = data.books[C.ZERO]
    assert result.features[S.GENRES] == (S.ANALYTIC_CATEGORY_FANTASY,)
    assert result.first_publication_year == C.WIKIDATA_TEST_YEAR_NUMBER
    assert result.page_count is C.NONE
    assert S.LANGUAGE not in result.features
    assert data.manifest.metadata[C.ZERO].provider == Source.WIKIDATA
    assert all(
        book.source != Source.GOODREADS for book in library.enrichment_targets(Source.WIKIDATA)
    )
    assert any(
        book.source == Source.GOODREADS for book in library.enrichment_targets(Source.OPEN_LIBRARY)
    )


def test_only_explicit_appetite_labels_are_used(library: Database) -> None:
    catalog = seed(library)
    assert (
        S.AN_APPETITE
        not in library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO].features
    )
    settings = AnalyticsSettings(
        book_labels=(
            DeclaredLabel(goodreads_id=catalog.source_id, dimension=S.AN_WONDER, evidence=S.TEST),
        )
    )
    data = library.analytics_input(accounts(), settings)
    assert data.books[C.ZERO].features[S.AN_APPETITE] == (S.AN_WONDER,)
    assert any(item.detail == S.TEST for item in data.books[C.ZERO].evidence)
    assert data.manifest.settings == settings


def test_failed_latest_source_attempt_blocks_new_analysis(library: Database) -> None:
    seed(library)
    publish_scope(library, Source.STORYGRAPH, state=SyncState.FAILED)
    with pytest.raises(AnalyticsInputError, match=S.AN_INPUT_INCOMPLETE):
        library.analytics_input(accounts(), AnalyticsSettings())


def test_watchlist_update_cannot_replace_pinned_read_facts(library: Database) -> None:
    catalog = seed(library)
    watch = catalog.model_copy(update={S.OBSERVATIONS: (rating(C.ONE, field=S.COMMUNITY_RATING),)})
    publish_scope(library, Source.GOODREADS, watch, collection=S.TO_READ)
    data = library.analytics_input(accounts(), AnalyticsSettings())
    assert data.books[C.ZERO].community_ratings[Source.GOODREADS.value] == C.THREE
    assert any(
        item.observation.field == S.COMMUNITY_RATING and item.observation.value == C.THREE
        for item in data.books[C.ZERO].evidence
    )
    assert data.books[C.ZERO].rating == C.FOUR


def test_incompatible_same_id_across_snapshots_blocks_analysis(library: Database) -> None:
    catalog = seed(library)
    watch = catalog.model_copy(update={S.TITLE: S.TEST_IMPORT_OTHER_TITLE})
    publish_scope(library, Source.GOODREADS, watch, collection=S.TO_READ)
    with pytest.raises(AnalyticsInputError, match=S.AN_INPUT_LINEAGE_ERROR):
        library.analytics_input(accounts(), AnalyticsSettings())


@pytest.mark.parametrize(S.AN_TEST_FIELD_STATE, C.AN_TEST_MISSING_STATES)
def test_missing_rating_states_are_preserved(library: Database, field_state: FieldState) -> None:
    seed(library)
    missing = Observation(
        field=S.RATING,
        state=field_state,
        source_url=S.TEST_STORAGE_BOOK_HTTPS_APP_THESTORYGRAPH_COM_BOOKS_ONE,
    )
    publish_scope(library, Source.STORYGRAPH, book(**{S.OBSERVATIONS: (missing,)}))
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.rating is C.NONE
    assert result.field_states[S.RATING] == field_state


def test_conflicting_catalog_values_are_not_zero_or_silently_unknown(library: Database) -> None:
    catalog = seed(library)
    first = catalog.model_copy(update={S.OBSERVATIONS: (rating(C.ONE, field=S.PAGE_COUNT),)})
    second = first.model_copy(
        update={
            S.SOURCE_ID: S.TEST_IMPORT_SECOND_ID,
            S.OBSERVATIONS: (rating(C.TWO, field=S.PAGE_COUNT),),
        }
    )
    publish_scope(library, Source.GOODREADS, first, second, collection=S.READ)
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.page_count is C.NONE
    assert result.field_states[S.PAGE_COUNT] == FieldState.FAILED


def test_work_publication_and_description_are_distinct_from_edition_facts(
    library: Database,
) -> None:
    catalog = seed(library)
    observations = (
        Observation(
            field=S.IMPORT_BROWSER_FIRST_PUBLICATION,
            value=S.TEST_GOOGLE_BOOKS_PUBLICATION_DATE_PRESERVES_SOURCE_PRECISION_TEXT,
            scope=S.WORK,
            state=FieldState.PRESENT,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
        Observation(
            field=S.PUBLICATION_DATE,
            value=S.TEST_IMPORT_DATE,
            scope=S.EDITION,
            state=FieldState.PRESENT,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
        Observation(
            field=S.DESCRIPTION,
            value=S.TEST_BROWSER_EXPORT_DESCRIPTION,
            scope=S.WORK,
            state=FieldState.PRESENT,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
        Observation(
            field=S.PAGE_COUNT,
            value=C.INTEGRATION_PAGE_COUNT,
            scope=S.WORK,
            state=FieldState.PRESENT,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
    )
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(update={S.OBSERVATIONS: observations}),
        collection=S.READ,
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.first_publication_year == int(
        S.TEST_GOOGLE_BOOKS_PUBLICATION_DATE_PRESERVES_SOURCE_PRECISION_TEXT[: C.FOUR]
    )
    assert result.publication_year == int(S.TEST_IMPORT_DATE[: C.FOUR])
    assert result.first_publication_year != result.publication_year
    assert result.description == S.TEST_BROWSER_EXPORT_DESCRIPTION
    assert result.page_count is C.NONE
    assert result.field_states[S.PAGE_COUNT] == FieldState.FAILED
    assert not result.reading_events
    assert any(
        item.public_url == catalog.url and item.observation.source_url == S.TEST_BROWSER_EXPORT_URL
        for item in result.evidence
        if item.source == Source.GOODREADS.value and item.observation.field == S.DESCRIPTION
    )


def test_invalid_publication_precision_is_failed_instead_of_truncated_to_a_year(
    library: Database,
) -> None:
    catalog = seed(library)
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(
            update={
                S.OBSERVATIONS: (
                    Observation(
                        field=S.PUBLICATION_DATE,
                        value=S.TEST_IMPORT_DATE + S.TEST,
                        scope=S.EDITION,
                        state=FieldState.PRESENT,
                        source_url=S.TEST_BROWSER_EXPORT_URL,
                    ),
                )
            }
        ),
        collection=S.READ,
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.publication_year is C.NONE
    assert result.field_states[S.PUBLICATION_DATE] == FieldState.FAILED


def test_linked_provider_work_fields_are_shared_but_personal_source_editions_are_not(
    library: Database,
) -> None:
    seed(library)
    personal = book()
    url = S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE.format(v0=S.VOLUME)
    candidate = metadata_candidate().model_copy(
        update={
            S.URL: url,
            S.OBSERVATIONS: (
                Observation(
                    field=S.DESCRIPTION,
                    value=S.TEST_BROWSER_EXPORT_DESCRIPTION,
                    state=FieldState.PRESENT,
                    source_url=url,
                    scope=S.EDITION,
                ),
                Observation(
                    field=S.PAGE_COUNT,
                    value=C.INTEGRATION_PAGE_COUNT,
                    state=FieldState.PRESENT,
                    source_url=url,
                    scope=S.EDITION,
                ),
            ),
        }
    )
    library.save_enrichment(
        Source.STORYGRAPH,
        Source.GOOGLE_BOOKS,
        EnrichmentResult(
            source_id=personal.source_id,
            state=SyncState.COMPLETE,
            candidates=(candidate,),
        ),
    )
    data = library.analytics_input(accounts(), AnalyticsSettings())
    result = data.books[C.ZERO]
    assert result.description == S.TEST_BROWSER_EXPORT_DESCRIPTION
    assert result.page_count is C.NONE
    assert data.manifest.metadata[C.ZERO].source_id == S.AN_METADATA_ORIGIN.format(
        source=Source.STORYGRAPH.value, source_id=personal.source_id
    )
    assert any(
        item.observation.field == S.DESCRIPTION
        and item.source == Source.GOOGLE_BOOKS.value
        and item.detail == data.manifest.metadata[C.ZERO].source_id
        for item in result.evidence
    )
    changed = book(
        **{
            S.SOURCE: Source.GOODREADS,
            S.TITLE: S.TEST_IMPORT_OTHER_TITLE,
            S.ISBNS: (),
        }
    )
    publish_scope(library, Source.GOODREADS, changed, collection=S.READ)
    unlinked = library.analytics_input(accounts(), AnalyticsSettings())
    assert unlinked.books[C.ZERO].description is C.NONE
    assert not unlinked.manifest.metadata


def test_provider_work_fields_cross_collections_without_sharing_edition_fields(
    library: Database,
) -> None:
    seed(library)
    watch = book(
        **{
            S.SOURCE: Source.GOODREADS,
            S.SOURCE_ID: S.TWO_2,
            S.STATUS: S.TO_READ,
        }
    )
    publish_scope(library, Source.GOODREADS, watch, collection=S.TO_READ)
    candidate = metadata_candidate()
    description = Observation(
        field=S.DESCRIPTION,
        value=S.TEST_BROWSER_EXPORT_DESCRIPTION,
        state=FieldState.PRESENT,
        source_url=candidate.url,
        scope=S.WORK,
    )
    library.save_enrichment(
        Source.GOODREADS,
        candidate.provider,
        EnrichmentResult(
            source_id=watch.source_id,
            state=SyncState.COMPLETE,
            candidates=(
                candidate.model_copy(
                    update={S.OBSERVATIONS: (*candidate.observations, description)}
                ),
            ),
        ),
    )
    data = library.analytics_input(accounts(), AnalyticsSettings())
    assert len(data.books) == C.ONE
    result = data.books[C.ZERO]
    assert result.description == description.value
    assert result.page_count is C.NONE
    assert set(result.collections) == {S.READ, S.TO_READ}
    assert data.manifest.metadata[C.ZERO].source_id == watch.source_id


def test_alternative_provider_descriptions_are_not_scalar_fact_conflicts(
    library: Database,
) -> None:
    catalog = seed(library)
    description = S.TEST_BROWSER_EXPORT_DESCRIPTION
    longer = description + S.SPACE + description
    for provider, text in (
        (Source.GOOGLE_BOOKS, description),
        (Source.OPEN_LIBRARY, longer),
    ):
        provider_id = S.OL45883W if provider == Source.OPEN_LIBRARY else S.VOLUME
        url = (
            S.OPEN_LIBRARY_WORK_URL_TEMPLATE
            if provider == Source.OPEN_LIBRARY
            else S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE
        ).format(v0=provider_id)
        candidate = metadata_candidate(
            **{
                S.PROVIDER: provider,
                S.PROVIDER_ID: provider_id,
                S.URL: url,
                S.OBSERVATIONS: (
                    Observation(
                        field=S.DESCRIPTION,
                        value=text,
                        state=FieldState.PRESENT,
                        source_url=url,
                        scope=S.WORK if provider == Source.OPEN_LIBRARY else S.EDITION,
                    ),
                ),
            }
        )
        library.save_enrichment(
            Source.GOODREADS,
            provider,
            EnrichmentResult(
                source_id=catalog.source_id,
                state=SyncState.COMPLETE,
                candidates=(candidate,),
            ),
        )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.description == longer
    assert result.field_states[S.DESCRIPTION] == FieldState.PRESENT
    assert {
        item.observation.value
        for item in result.evidence
        if item.observation.field == S.DESCRIPTION
    } == {description, longer}


@pytest.mark.parametrize(S.PROVIDER, (Source.GOOGLE_BOOKS, Source.OPEN_LIBRARY))
def test_substantive_public_description_beats_clipped_primary_without_relabeling_scope(
    library: Database, provider: Source
) -> None:
    catalog = seed(library)
    preview = Observation(
        field=S.DESCRIPTION,
        value=S.METADATA_TEST_PREVIEW,
        state=FieldState.PRESENT,
        scope=S.WORK,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(update={S.OBSERVATIONS: (preview,)}),
        collection=S.READ,
    )
    provider_id = S.OL45883W if provider == Source.OPEN_LIBRARY else S.VOLUME
    url = (
        S.OPEN_LIBRARY_WORK_URL_TEMPLATE
        if provider == Source.OPEN_LIBRARY
        else S.GOOGLE_BOOKS_VOLUME_URL_TEMPLATE
    ).format(v0=provider_id)
    observation = Observation(
        field=S.DESCRIPTION,
        value=S.METADATA_TEST_RICH_DESCRIPTION,
        state=FieldState.PRESENT,
        scope=S.WORK if provider == Source.OPEN_LIBRARY else S.EDITION,
        source_url=url,
    )
    candidate = metadata_candidate(
        **{
            S.PROVIDER: provider,
            S.PROVIDER_ID: provider_id,
            S.URL: url,
            S.OBSERVATIONS: (observation,),
        }
    )
    library.save_enrichment(
        Source.GOODREADS,
        provider,
        EnrichmentResult(
            source_id=catalog.source_id,
            state=SyncState.COMPLETE,
            candidates=(candidate,),
        ),
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.description == S.METADATA_TEST_RICH_DESCRIPTION
    assert result.field_states[S.DESCRIPTION] == FieldState.PRESENT
    assert any(item.observation == preview for item in result.evidence)
    assert any(item.observation == observation for item in result.evidence)
    provenance = description_provenance(result)
    assert provenance is not C.NONE
    assert provenance[S.CONTENT_ANALYSIS_SOURCE] == provider.value
    assert provenance[S.CONTENT_ANALYSIS_URL] == url


def test_clipped_only_description_remains_raw_evidence_not_complete_content(
    library: Database,
) -> None:
    catalog = seed(library)
    preview = Observation(
        field=S.DESCRIPTION,
        value=S.METADATA_TEST_PREVIEW,
        state=FieldState.PRESENT,
        scope=S.WORK,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(update={S.OBSERVATIONS: (preview,)}),
        collection=S.READ,
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.description is C.NONE
    assert result.field_states[S.DESCRIPTION] == FieldState.UNAVAILABLE
    assert any(item.observation == preview for item in result.evidence)
    assert description_provenance(result) is C.NONE


def test_validated_edition_retains_legitimate_thousand_page_length(library: Database) -> None:
    catalog = seed(library)
    candidate = metadata_candidate()
    pages = candidate.observations[C.ZERO].model_copy(update={S.VALUE: C.METADATA_TEST_LONG_PAGES})
    library.save_enrichment(
        Source.GOODREADS,
        candidate.provider,
        EnrichmentResult(
            source_id=catalog.source_id,
            state=SyncState.COMPLETE,
            candidates=(candidate.model_copy(update={S.OBSERVATIONS: (pages,)}),),
        ),
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.page_count == C.METADATA_TEST_LONG_PAGES
    assert result.field_states[S.PAGE_COUNT] == FieldState.PRESENT
    assert any(item.observation == pages for item in result.evidence)


@pytest.mark.parametrize(S.FIELD, (S.IMPORT_BROWSER_FIRST_PUBLICATION, S.PUBLICATION_DATE))
def test_optional_goodreads_publication_conflict_cannot_be_hidden_by_provider_fallback(
    library: Database, field: str
) -> None:
    catalog = seed(library)
    scope = S.WORK if field == S.IMPORT_BROWSER_FIRST_PUBLICATION else S.EDITION
    flags = (
        Observation(
            field=field,
            scope=scope,
            state=FieldState.UNAVAILABLE,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
        Observation(
            field=S.METADATA_PUBLICATION_CONFLICT,
            value=field,
            scope=scope,
            state=FieldState.PRESENT,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
    )
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(update={S.OBSERVATIONS: flags}),
        collection=S.READ,
    )
    candidate = metadata_candidate(
        **{
            S.OBSERVATIONS: (
                Observation(
                    field=S.FIRST_PUBLICATION_YEAR
                    if field == S.IMPORT_BROWSER_FIRST_PUBLICATION
                    else S.PUBLICATION_DATE,
                    value=S.METADATA_TEST_DATE_YEAR,
                    scope=scope,
                    state=FieldState.PRESENT,
                    source_url=S.TEST_BROWSER_EXPORT_URL,
                ),
            )
        }
    )
    library.save_enrichment(
        Source.GOODREADS,
        candidate.provider,
        EnrichmentResult(
            source_id=catalog.source_id,
            state=SyncState.COMPLETE,
            candidates=(candidate,),
        ),
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    target = (
        S.FIRST_PUBLICATION_YEAR
        if field == S.IMPORT_BROWSER_FIRST_PUBLICATION
        else S.PUBLICATION_DATE
    )
    assert result.first_publication_year is C.NONE
    assert result.publication_year is C.NONE
    assert result.field_states[target] == FieldState.FAILED
    assert any(item.observation == flags[C.ONE] for item in result.evidence)


@pytest.mark.parametrize(S.AV_TEST_SCOPE_PARAMETERS, C.AV_TEST_LANGUAGE_SCOPE_CASES)
def test_language_features_require_their_own_scope_without_discarding_evidence(
    library: Database, field: str, scope: S.ObservationScope, eligible: bool
) -> None:
    catalog = seed(library)
    observation = Observation(
        field=field,
        value=(S.AN_CALC_LANGUAGE_ENG if field == S.LANGUAGE else [S.AN_CALC_LANGUAGE_ENG]),
        scope=scope,
        state=FieldState.PRESENT,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(update={S.OBSERVATIONS: (observation,)}),
        collection=S.READ,
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert (field in result.features) == eligible
    if eligible:
        assert result.features[field] == (S.AN_CALC_LANGUAGE_ENG,)
    assert result.field_states[field] == (FieldState.PRESENT if eligible else FieldState.FAILED)
    assert any(item.observation == observation for item in result.evidence)


def test_work_availability_and_unsupported_edition_language_remain_separate(
    library: Database,
) -> None:
    catalog = seed(library)
    edition = Observation(
        field=S.LANGUAGE,
        scope=S.EDITION,
        state=FieldState.UNSUPPORTED,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    work = Observation(
        field=S.LANGUAGES,
        value=[S.AN_CALC_LANGUAGE_ENG],
        scope=S.WORK,
        state=FieldState.PRESENT,
        source_url=S.TEST_BROWSER_EXPORT_URL,
    )
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(update={S.OBSERVATIONS: (edition, work)}),
        collection=S.READ,
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert S.LANGUAGE not in result.features
    assert result.field_states[S.LANGUAGE] == FieldState.UNSUPPORTED
    assert result.features[S.LANGUAGES] == (S.AN_CALC_LANGUAGE_ENG,)
    assert result.field_states[S.LANGUAGES] == FieldState.PRESENT
    assert any(item.observation == edition for item in result.evidence)
    assert any(item.observation == work for item in result.evidence)


def test_mixed_language_scope_conflicts_do_not_pollute_eligible_features(
    library: Database,
) -> None:
    catalog = seed(library)
    observations = (
        Observation(
            field=S.LANGUAGE,
            value=S.FR,
            state=FieldState.PRESENT,
            scope=S.EDITION,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
        Observation(
            field=S.LANGUAGE,
            value=S.AN_CALC_LANGUAGE_ENG,
            state=FieldState.PRESENT,
            scope=S.WORK,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
        Observation(
            field=S.LANGUAGES,
            value=[S.AN_CALC_LANGUAGE_ENG],
            state=FieldState.PRESENT,
            scope=S.WORK,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
        Observation(
            field=S.LANGUAGES,
            value=[S.FR],
            state=FieldState.PRESENT,
            scope=S.EDITION,
            source_url=S.TEST_BROWSER_EXPORT_URL,
        ),
    )
    publish_scope(
        library,
        Source.GOODREADS,
        catalog.model_copy(update={S.OBSERVATIONS: observations}),
        collection=S.READ,
    )
    result = library.analytics_input(accounts(), AnalyticsSettings()).books[C.ZERO]
    assert result.features[S.LANGUAGE] == (S.FR,)
    assert result.features[S.LANGUAGES] == (S.AN_CALC_LANGUAGE_ENG,)
    assert result.field_states[S.LANGUAGE] == result.field_states[S.LANGUAGES] == FieldState.PRESENT
    assert all(
        any(item.observation == observation for item in result.evidence)
        for observation in observations
    )
