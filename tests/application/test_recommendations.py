from __future__ import annotations

from pathlib import Path

import pytest

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.recommendations import RecommendationService
from bookystats.domain.analytics import AnalysisInput
from bookystats.domain.errors import BookyError
from bookystats.persistence.recommendations import RecommendationStore
from tests.application.test_content_analysis import _book as public_book
from tests.domain.test_recommendations import analysis, candidate, data, history


class Encoder:
    def __init__(self) -> None:
        self.calls = C.ZERO
        self.failed = C.FALSE
        self.identifier = S.REC3_TEST_ENCODER

    @property
    def fingerprint(self) -> str:
        return self.identifier

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls += C.ONE
        if self.failed:
            raise BookyError(S.REC3_TEST_ENCODER_FAILURE)
        return tuple(C.REC3_TEST_VECTOR for _ in texts)


def described() -> AnalysisInput:
    return data(
        *(
            public_book(
                work_id,
                url=S.CONTENT_ANALYSIS_TEST_URL,
                collection=S.READ if work_id < C.FOUR else S.TO_READ,
                rating=C.FIVE if work_id < C.FOUR else C.NONE,
                authors=(S.AN_CALC_TEST_AUTHOR_FORMAT.format(index=work_id),),
            )
            for work_id in range(C.ONE, C.FIVE)
        )
    )


def test_public_semantics_cache_avoids_encoder_and_rejects_failed_updates(tmp_path: Path) -> None:
    pinned, encoder = described(), Encoder()
    with RecommendationStore(tmp_path / S.AN_DATABASE) as store:
        service = RecommendationService(store, encoder)
        first = service.run(pinned, analysis(pinned))
        assert encoder.calls == C.ONE
        assert first.learning is not C.NONE
        assert first.learning.encoded_description_works == C.FOUR
        assert not first.learning.active
        assert len(first.unrankable[C.ZERO].semantic_neighbors) == C.THREE
        encoder.failed = C.TRUE
        repeated = service.run(pinned, analysis(pinned))
        assert repeated.reused and encoder.calls == C.ONE
        encoder.identifier = S.REC3_TEST_OTHER_ENCODER
        with pytest.raises(BookyError, match=S.REC3_TEST_ENCODER_FAILURE):
            service.run(pinned, analysis(pinned))
        assert store.latest() == repeated


def test_description_reference_changes_invalidate_but_capture_time_does_not(tmp_path: Path) -> None:
    pinned, encoder = described(), Encoder()
    with RecommendationStore(tmp_path / S.AN_DATABASE) as store:
        service = RecommendationService(store, encoder)
        first = service.run(pinned, analysis(pinned))
        recaptured = pinned.model_copy(
            update={
                S.BOOKS: tuple(
                    book.model_copy(
                        update={
                            S.AN_EVIDENCE: tuple(
                                evidence.model_copy(
                                    update={
                                        S.DTX_OBSERVATION: evidence.observation.model_copy(
                                            update={S.OBSERVED_AT: S.REC_TEST_FUTURE_AS_OF}
                                        )
                                    }
                                )
                                for evidence in book.evidence
                            )
                        }
                    )
                    for book in pinned.books
                )
            }
        )
        assert service.run(recaptured, analysis(recaptured)).key == first.key
        assert encoder.calls == C.ONE
        changed = pinned.model_copy(
            update={
                S.BOOKS: tuple(
                    public_book(
                        book.work_id,
                        url=S.CONTENT_ANALYSIS_TEST_FILE_URL,
                        public_url=S.CONTENT_ANALYSIS_TEST_URL,
                        collection=book.collections[C.ZERO],
                        rating=book.rating,
                        authors=book.authors,
                    )
                    for book in pinned.books
                )
            }
        )
        assert service.run(changed, analysis(changed)).key == first.key
        referenced = changed.model_copy(
            update={
                S.BOOKS: tuple(
                    book.model_copy(
                        update={
                            S.AN_EVIDENCE: tuple(
                                evidence.model_copy(
                                    update={
                                        S.REC2_PUBLIC_URL: S.RPT_TEST_PUBLIC_URL.format(
                                            work_id=book.work_id
                                        )
                                    }
                                )
                                for evidence in book.evidence
                            )
                        }
                    )
                    for book in changed.books
                )
            }
        )
        assert service.run(referenced, analysis(referenced)).key != first.key
        assert encoder.calls == C.TWO


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
