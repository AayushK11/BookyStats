from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.domain.analytics import AnalyticsSettings, DeclaredLabel
from bookystats.domain.models import (
    BookRecord,
    EnrichmentResult,
    FieldState,
    Observation,
    Source,
    SyncState,
)
from bookystats.persistence.analysis_input import AnalyticsInputError
from bookystats.persistence.library import Database
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
    candidate = metadata_candidate().model_copy(
        update={
            S.OBSERVATIONS: (
                Observation(
                    field=S.DESCRIPTION,
                    value=S.TEST_BROWSER_EXPORT_DESCRIPTION,
                    state=FieldState.PRESENT,
                    source_url=S.TEST_BROWSER_EXPORT_URL,
                    scope=S.WORK,
                ),
                Observation(
                    field=S.PAGE_COUNT,
                    value=C.INTEGRATION_PAGE_COUNT,
                    state=FieldState.PRESENT,
                    source_url=S.TEST_BROWSER_EXPORT_URL,
                    scope=S.EDITION,
                ),
            )
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
        candidate = metadata_candidate(
            **{
                S.PROVIDER: provider,
                S.OBSERVATIONS: (
                    Observation(
                        field=S.DESCRIPTION,
                        value=text,
                        state=FieldState.PRESENT,
                        source_url=S.TEST_BROWSER_EXPORT_URL,
                        scope=S.WORK,
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
