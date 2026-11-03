from __future__ import annotations

from contextlib import closing
from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application import analytics as analytics_module
from bookystats.application.analytics import (
    AnalyticsService,
    _calculate_components,
    _component_key,
    _taste_input,
)
from bookystats.domain.analytics import (
    AnalysisEvidence,
    AnalysisInput,
    AnalyticsSettings,
    Capability,
    Finding,
)
from bookystats.domain.models import (
    Account,
    FieldState,
    Observation,
    PartialDate,
    ReadingStatus,
    Source,
    SyncState,
)
from bookystats.persistence.analysis_input import AnalyticsInputError
from bookystats.persistence.analytics import AnalyticsStore
from bookystats.persistence.library import Database
from tests.application.test_statistics import _book, _data, _supplemental
from tests.persistence.test_analysis_input import publish_scope, seed
from tests.persistence.test_library import book, rating
from tests.support.sources import accounts


class _InputReader:
    def __init__(self, data: AnalysisInput) -> None:
        self.data = data

    def analytics_input(
        self, accounts: tuple[Account, ...], settings: AnalyticsSettings
    ) -> AnalysisInput:
        return self.data


def _failed_content_job(
    data: AnalysisInput, settings: AnalyticsSettings
) -> tuple[tuple[Finding, ...], tuple[Capability, ...]]:
    raise RuntimeError(S.TEST)


def test_unchanged_reimports_reuse_calculations_with_current_provenance(tmp_path: Path) -> None:
    with (
        closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as library,
        AnalyticsStore(tmp_path / S.AN_DATABASE) as reports,
    ):
        library.initialize()
        catalog = seed(library)
        service = AnalyticsService(library, reports)
        initial = service.run(accounts(), AnalyticsSettings())
        first = reports.latest()
        assert first is not C.NONE
        assert initial.state == SyncState.COMPLETE
        assert initial.rated_read == C.ONE
        assert not initial.taste_reused
        publish_scope(library, Source.GOODREADS, catalog, collection=S.READ)
        repeated = service.run(accounts(), AnalyticsSettings())
        current = reports.latest()
        assert current is not C.NONE
        assert repeated.taste_reused and repeated.watchlist_reused
        assert repeated.report_id != initial.report_id
        assert current.taste.key == first.taste.key
        assert (
            current.taste.findings[C.ZERO].source_snapshot_ids
            != first.taste.findings[C.ZERO].source_snapshot_ids
        )
        assert current.taste.findings[C.ZERO].source_snapshot_ids == tuple(
            item.snapshot_id for item in current.manifest.snapshots
        )


@pytest.mark.parametrize(S.AN_TEST_OVERLAP, C.AN_TEST_OVERLAPS)
def test_watchlist_only_changes_do_not_recompute_taste(tmp_path: Path, overlap: bool) -> None:
    with (
        closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as library,
        AnalyticsStore(tmp_path / S.AN_DATABASE) as reports,
    ):
        library.initialize()
        catalog = seed(library)
        service = AnalyticsService(library, reports)
        service.run(accounts(), AnalyticsSettings())
        watch = (
            catalog.model_copy(
                update={S.SOURCE_ID: S.TEST_IMPORT_SECOND_ID, S.STATUS: ReadingStatus.TO_READ}
            )
            if overlap
            else book(
                **{
                    S.SOURCE: Source.GOODREADS,
                    S.SOURCE_ID: S.TEST_IMPORT_SECOND_ID,
                    S.TITLE: S.TEST_IMPORT_OTHER_TITLE,
                    S.ISBNS: (),
                    S.STATUS: ReadingStatus.TO_READ,
                }
            )
        )
        publish_scope(library, Source.GOODREADS, watch, collection=S.TO_READ)
        changed = service.run(accounts(), AnalyticsSettings())
        assert changed.taste_reused
        assert not changed.watchlist_reused


def test_changed_personal_rating_invalidates_dependent_calculations(tmp_path: Path) -> None:
    with (
        closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as library,
        AnalyticsStore(tmp_path / S.AN_DATABASE) as reports,
    ):
        library.initialize()
        seed(library)
        service = AnalyticsService(library, reports)
        service.run(accounts(), AnalyticsSettings())
        publish_scope(library, Source.STORYGRAPH, book(**{S.OBSERVATIONS: (rating(C.FIVE),)}))
        changed = service.run(accounts(), AnalyticsSettings())
        assert not changed.taste_reused
        assert not changed.watchlist_reused


def test_content_public_reference_invalidates_cache_but_capture_time_does_not(
    tmp_path: Path,
) -> None:
    with (
        closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as library,
        AnalyticsStore(tmp_path / S.AN_DATABASE) as reports,
    ):
        library.initialize()
        catalog = seed(library).model_copy(
            update={
                S.URL: S.CONTENT_ANALYSIS_TEST_URL,
                S.OBSERVATIONS: (
                    Observation(
                        field=S.DESCRIPTION,
                        value=S.CONTENT_ANALYSIS_TEST_TEXT,
                        state=FieldState.PRESENT,
                        scope=S.WORK,
                        source_url=S.CONTENT_ANALYSIS_TEST_FILE_URL,
                        observed_at=S.TEST_STORAGE_START_T10,
                    ),
                ),
            }
        )
        publish_scope(library, Source.GOODREADS, catalog, collection=S.READ)
        service = AnalyticsService(library, reports)
        original = service.run(accounts(), AnalyticsSettings())
        assert not original.taste_reused
        recaptured = catalog.model_copy(
            update={
                S.OBSERVATIONS: tuple(
                    item.model_copy(update={S.OBSERVED_AT: S.TEST_STORAGE_FINISH_T10})
                    for item in catalog.observations
                )
            }
        )
        publish_scope(library, Source.GOODREADS, recaptured, collection=S.READ)
        repeated = service.run(accounts(), AnalyticsSettings())
        assert repeated.taste_reused and repeated.watchlist_reused
        unreferenced = recaptured.model_copy(
            update={S.URL: S.TEST_STORAGE_BOOK_HTTPS_APP_THESTORYGRAPH_COM_BOOKS_ONE}
        )
        publish_scope(library, Source.GOODREADS, unreferenced, collection=S.READ)
        changed = service.run(accounts(), AnalyticsSettings())
        assert not changed.taste_reused and not changed.watchlist_reused


def test_failed_source_retains_previous_report(tmp_path: Path) -> None:
    with (
        closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as library,
        AnalyticsStore(tmp_path / S.AN_DATABASE) as reports,
    ):
        library.initialize()
        seed(library)
        service = AnalyticsService(library, reports)
        original = service.run(accounts(), AnalyticsSettings())
        publish_scope(library, Source.STORYGRAPH, state=SyncState.FAILED)
        with pytest.raises(AnalyticsInputError, match=S.AN_INPUT_INCOMPLETE):
            service.run(accounts(), AnalyticsSettings())
        current = reports.latest()
        assert current is not C.NONE
        assert current.report_id == original.report_id


def test_process_parallel_results_equal_serial_results(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _data(
        *(
            _book(index, C.FOUR, genre=S.AN_CALC_TEST_GENRE).model_copy(
                update={
                    S.DESCRIPTION: S.CONTENT_ANALYSIS_TEST_TEXT,
                    S.AN_EVIDENCE: (
                        AnalysisEvidence(
                            source=S.GOODREADS,
                            source_id=str(index),
                            observation=Observation(
                                field=S.DESCRIPTION,
                                value=S.CONTENT_ANALYSIS_TEST_TEXT,
                                state=FieldState.PRESENT,
                                source_url=S.CONTENT_ANALYSIS_TEST_URL,
                                observed_at=S.AN_CALC_TEST_FINISH,
                            ),
                        ),
                    ),
                    S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (_supplemental(S.ANX_TEST_EARLIER_DATE),),
                }
            )
            for index in range(C.ONE, C.FOUR)
        )
    )
    settings = AnalyticsSettings(min_group_size=C.THREE)
    serial = _calculate_components(
        data,
        data,
        settings,
        S.AN_CALC_TEST_KEY,
        S.AN_CALC_TEST_KEY,
        C.NONE,
        C.NONE,
    )
    monkeypatch.setattr(C, S.AN_TEST_PARALLEL_THRESHOLD_ATTRIBUTE, C.ONE)
    parallel = _calculate_components(
        data,
        data,
        settings,
        S.AN_CALC_TEST_KEY,
        S.AN_CALC_TEST_KEY,
        C.NONE,
        C.NONE,
    )
    assert serial[C.TWO] == S.AN_EXECUTION_SERIAL
    assert parallel[C.TWO] == S.AN_EXECUTION_PARALLEL
    assert serial[: C.TWO] == parallel[: C.TWO]


def test_read_membership_invalidates_taste_without_watchlist_overlap_invalidation() -> None:
    settings = AnalyticsSettings()
    original = _data(_book(C.ONE, status=ReadingStatus.UNKNOWN))
    included = original.model_copy(
        update={
            S.BOOKS: tuple(
                book.model_copy(update={S.COLLECTIONS: (S.READ,)}) for book in original.books
            )
        }
    )
    overlapping = included.model_copy(
        update={
            S.BOOKS: tuple(
                book.model_copy(update={S.COLLECTIONS: (S.READ, S.TO_READ)})
                for book in included.books
            )
        }
    )
    assert _component_key(_taste_input(original), settings) != _component_key(
        _taste_input(included), settings
    )
    assert _component_key(_taste_input(included), settings) == _component_key(
        _taste_input(overlapping), settings
    )


def test_supplemental_recapture_reuses_calculation_and_rebinds_current_provenance(
    tmp_path: Path,
) -> None:
    settings = AnalyticsSettings()
    supplemental = _supplemental(S.ANX_TEST_EARLIER_DATE)
    original = _data(
        _book(C.ONE).model_copy(update={S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (supplemental,)})
    )
    recaptured = supplemental.model_copy(
        update={
            S.DTX_OBSERVATION: supplemental.observation.model_copy(
                update={S.OBSERVED_AT: S.TEST_STORAGE_FINISH_T10}
            )
        }
    )
    current = original.model_copy(
        update={
            S.BOOKS: tuple(
                book.model_copy(update={S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (recaptured,)})
                for book in original.books
            ),
            S.AN_STORE_TEST_MANIFEST: original.manifest.model_copy(
                update={
                    S.AN_STORE_TEST_SNAPSHOTS: tuple(
                        snapshot.model_copy(update={S.SNAPSHOT_ID: C.TWO})
                        for snapshot in original.manifest.snapshots
                    )
                }
            ),
        }
    )
    key = _component_key(original, settings)
    assert key == _component_key(current, settings)
    reader = _InputReader(original)
    with AnalyticsStore(tmp_path / S.AN_DATABASE) as reports:
        service = AnalyticsService(reader, reports)
        first = service.run(accounts(), settings)
        reader.data = current
        repeated = service.run(accounts(), settings)
        report = reports.latest()
    assert repeated.taste_reused and repeated.watchlist_reused
    assert repeated.report_id != first.report_id
    assert report is not C.NONE
    finding = next(
        item for item in report.taste.findings if item.metric_id == S.ANX_COMPLETION_COHORTS
    )
    assert finding.source_snapshot_ids == (C.TWO,)
    assert isinstance(finding.value, dict)
    selected = finding.value[S.ANX_SELECTED_DATES]
    assert isinstance(selected, dict)
    entry = selected[current.books[C.ZERO].book_id]
    assert isinstance(entry, dict)
    proof = entry[S.AN_CALC_EVIDENCE]
    assert isinstance(proof, list)
    assert proof[C.ZERO][S.ANX_SOURCE_URL] == S.CONTENT_ANALYSIS_TEST_FILE_URL
    assert S.OBSERVED_AT not in proof[C.ZERO]


def test_library_addition_and_supplemental_completion_changes_invalidate_taste() -> None:
    settings = AnalyticsSettings()
    original = _data(_book(C.ONE))
    for update in (
        {S.ADDED_AT: PartialDate(value=S.ANX_TEST_EARLIER_DATE)},
        {S.DTX_SUPPLEMENTAL_COMPLETION_DATES: (_supplemental(S.ANX_TEST_EARLIER_DATE),)},
    ):
        changed = original.model_copy(
            update={S.BOOKS: tuple(book.model_copy(update=update) for book in original.books)}
        )
        assert _component_key(original, settings) != _component_key(changed, settings)


def test_worker_failure_keeps_last_published_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        closing(Database(tmp_path / S.LIBRARY_SQLITE3)) as library,
        AnalyticsStore(tmp_path / S.AN_DATABASE) as reports,
    ):
        library.initialize()
        seed(library)
        service = AnalyticsService(library, reports)
        original = service.run(accounts(), AnalyticsSettings())
        publish_scope(library, Source.STORYGRAPH, book(**{S.OBSERVATIONS: (rating(C.FIVE),)}))
        monkeypatch.setattr(C, S.AN_TEST_PARALLEL_THRESHOLD_ATTRIBUTE, C.ONE)
        monkeypatch.setattr(analytics_module, S.AN_TEST_CONTENT_JOB_ATTRIBUTE, _failed_content_job)
        with pytest.raises(RuntimeError, match=S.TEST):
            service.run(accounts(), AnalyticsSettings())
        current = reports.latest()
        assert current is not C.NONE
        assert current.report_id == original.report_id
