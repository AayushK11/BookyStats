from __future__ import annotations

from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.recommendations import RecommendationService
from bookystats.domain.analytics import AnalysisInput
from bookystats.persistence.recommendations import RecommendationStore
from tests.domain.test_recommendations import analysis, candidate, data, history


def test_repeated_semantics_reuse_cache_and_rebind_current_source_provenance(
    tmp_path: Path,
) -> None:
    pinned = data(*history(), candidate())
    with RecommendationStore(tmp_path / S.AN_DATABASE) as store:
        service = RecommendationService(store)
        first = service.run(pinned, analysis(pinned))
        changed: AnalysisInput = pinned.model_copy(
            update={
                S.REC_MANIFEST: pinned.manifest.model_copy(
                    update={
                        S.REC_SNAPSHOTS: tuple(
                            snapshot.model_copy(update={S.AN_STORE_TEST_SNAPSHOT_ID: C.TWO})
                            for snapshot in pinned.manifest.snapshots
                        )
                    }
                ),
                S.BOOKS: tuple(
                    book.model_copy(update={S.REC_SOURCE_IDS: (S.REC_TEST_AUTHOR,)})
                    for book in pinned.books
                ),
            }
        )
        repeated = service.run(changed, analysis(changed))
        assert repeated.key == first.key
        assert repeated.reused
        assert repeated.report_id != first.report_id
        assert repeated.source_snapshot_ids == (C.TWO,)
        assert repeated.ranked[C.ZERO].source_ids == (S.REC_TEST_AUTHOR,)
        assert store.latest() == repeated
        cached = store.get_cached(first.key)
        assert cached is not C.NONE
        assert not cached.source_snapshot_ids
        assert not cached.ranked[C.ZERO].source_ids
        assert not cached.manifest.snapshots


def test_incompatible_pinned_inputs_fail_without_replacing_last_good(tmp_path: Path) -> None:
    pinned = data(*history(), candidate())
    with RecommendationStore(tmp_path / S.AN_DATABASE) as store:
        service = RecommendationService(store)
        first = service.run(pinned, analysis(pinned))
        changed = pinned.model_copy(update={S.REC_AS_OF: S.REC_TEST_FUTURE_AS_OF})
        with pytest.raises(ValueError, match=S.REC_COMPATIBILITY_ERROR):
            service.run(changed, analysis(pinned))
        assert store.latest() == first
