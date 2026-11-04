from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping

from bookystats import constants as C
from bookystats import strings as S
from bookystats.application.content_analysis import description_provenance, public_description
from bookystats.domain.analytics import AnalysisBook, AnalysisInput, AnalyticsReport
from bookystats.domain.interfaces import DescriptionEncoder
from bookystats.domain.models import canonical_json
from bookystats.domain.ranking_evaluation import evaluate_ranking
from bookystats.domain.recommendation_evaluation import (
    FeatureReader,
    fit_profile,
    predict_profile,
)
from bookystats.domain.recommendation_learning import (
    DescriptionDocument,
    LearningContext,
    SimilarityIndex,
    fit_hybrid,
)
from bookystats.domain.recommendations import (
    RecommendationItem,
    RecommendationReport,
    RecommendationRepository,
    build_recommendations,
    rated_history,
    recommendation_features,
    recommendation_key,
)


def _documents(data: AnalysisInput) -> dict[int, DescriptionDocument]:
    candidates: dict[int, dict[str, DescriptionDocument]] = {}
    for book in data.books:
        text = public_description(book)
        provenance = description_provenance(book)
        if text is C.NONE or provenance is C.NONE:
            continue
        url = provenance.get(S.CONTENT_ANALYSIS_URL)
        if not isinstance(url, str):
            continue
        document = DescriptionDocument(text=text, provenance=provenance, public_url=url)
        candidates.setdefault(book.work_id, {})[
            canonical_json(document.model_dump(mode=S.JSON))
        ] = document
    return {
        work_id: next(iter(documents.values()))
        for work_id, documents in candidates.items()
        if len(documents) == C.ONE
    }


def _feature_predictor(
    training: tuple[AnalysisBook, ...],
    targets: tuple[AnalysisBook, ...],
    features: FeatureReader,
) -> Mapping[int, float | None]:
    profile = fit_profile(training, features, richer=C.FALSE)
    predictions: dict[int, float | None] = {}
    for book in targets:
        score, fallback = predict_profile(profile, book, features)
        predictions[book.work_id] = (
            C.NONE
            if fallback
            else profile.baseline + round(score - profile.baseline, C.REC_SCORE_PRECISION)
        )
    return predictions


def _genres(book: AnalysisBook) -> tuple[tuple[str, str], ...]:
    return tuple(token for token in recommendation_features(book) if token[C.ZERO] == S.GENRES)


def _bind(
    report: RecommendationReport, data: AnalysisInput, analysis: AnalyticsReport
) -> RecommendationReport:
    source_ids: dict[int, set[str]] = {}
    for book in data.books:
        source_ids.setdefault(book.work_id, set()).update(book.source_ids)
    updates: dict[str, object] = {
        S.REC_MANIFEST: data.manifest,
        S.REC_AS_OF: data.as_of,
        S.REC_ANALYSIS_REPORT_ID: analysis.report_id,
        S.REC_REPORT_ID: C.NONE,
        S.REC_REUSED: C.TRUE,
        S.REC_SNAPSHOT_IDS: tuple(snapshot.snapshot_id for snapshot in data.manifest.snapshots),
    }
    for field in C.REC_ITEM_FIELDS:
        items: tuple[RecommendationItem, ...] = getattr(report, field)
        updates[field] = tuple(
            item.model_copy(
                update={S.REC_SOURCE_IDS: tuple(sorted(source_ids.get(item.work_id, set())))}
            )
            for item in items
        )
    return report.model_copy(update=updates)


class RecommendationService:
    def __init__(
        self,
        repository: RecommendationRepository,
        encoder: DescriptionEncoder | None = C.NONE,
        *,
        on_event: Callable[[str], None] | None = C.NONE,
    ) -> None:
        self.repository = repository
        self.encoder = encoder
        self.on_event = on_event

    def _event(self, message: str) -> None:
        if self.on_event is not C.NONE:
            self.on_event(message)

    def run(self, data: AnalysisInput, analysis: AnalyticsReport) -> RecommendationReport:
        if data.manifest != analysis.manifest or (
            analysis.as_of is not C.NONE and data.as_of[: C.TEN] != analysis.as_of[: C.TEN]
        ):
            raise ValueError(S.REC_COMPATIBILITY_ERROR)
        documents = _documents(data) if self.encoder is not C.NONE else {}
        fingerprint = self.encoder.fingerprint if self.encoder is not C.NONE else S.REC3_DISABLED
        description_fingerprint = (
            hashlib.sha256(
                canonical_json(
                    [
                        {S.REC_WORK_ID: work_id, S.DESCRIPTION: document.model_dump(mode=S.JSON)}
                        for work_id, document in sorted(documents.items())
                    ]
                ).encode(S.UTF_8)
            ).hexdigest()
            if documents
            else S.EMPTY
        )
        cached = self.repository.get_cached(
            recommendation_key(
                data,
                analysis,
                encoder_fingerprint=fingerprint,
                description_fingerprint=description_fingerprint,
                learning_enabled=C.TRUE,
            )
        )
        if cached is not C.NONE:
            self._event(S.REC3_LOG_REUSED)
            return self.repository.publish(_bind(cached, data, analysis))
        history = rated_history(data)
        vectors: dict[int, tuple[float, ...]] = {}
        if self.encoder is not C.NONE and (
            sum(book.work_id in documents for book in history) >= C.REC3_MIN_NEIGHBORS
        ):
            work_ids = tuple(sorted(documents))
            self._event(S.REC3_LOG_ENCODING.format(count=len(work_ids)))
            encoded = self.encoder.encode(tuple(documents[work_id].text for work_id in work_ids))
            if len(encoded) != len(work_ids):
                raise ValueError(S.REC3_INVALID_VECTORS)
            vectors = dict(zip(work_ids, encoded, strict=C.TRUE))
        index = SimilarityIndex(vectors)

        def current(
            training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
        ) -> Mapping[int, float | None]:
            return _feature_predictor(training, targets, recommendation_features)

        def genre(
            training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
        ) -> Mapping[int, float | None]:
            return _feature_predictor(training, targets, _genres)

        def candidate(
            training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
        ) -> Mapping[int, float | None]:
            model = fit_hybrid(training, index, recommendation_features)
            predictions: dict[int, float | None] = {}
            for book in targets:
                score = model.predict(book)
                predictions[book.work_id] = (
                    model.profile.categorical.baseline
                    + round(score - model.profile.categorical.baseline, C.REC_SCORE_PRECISION)
                    if score is not C.NONE and model.profile is not C.NONE
                    else C.NONE
                )
            return predictions

        def length(
            training: tuple[AnalysisBook, ...], targets: tuple[AnalysisBook, ...]
        ) -> Mapping[int, float | None]:
            profile = fit_profile(training, recommendation_features, richer=C.TRUE)
            predictions: dict[int, float | None] = {}
            for book in targets:
                score, fallback = predict_profile(
                    profile, book, recommendation_features, length_only=C.TRUE
                )
                predictions[book.work_id] = (
                    C.NONE
                    if fallback
                    else profile.baseline + round(score - profile.baseline, C.REC_SCORE_PRECISION)
                )
            return predictions

        self._event(S.REC3_LOG_EVALUATING.format(count=len(history)))
        represented_history = tuple(
            book if book.work_id in vectors else book.model_copy(update={S.DESCRIPTION: C.NONE})
            for book in history
        )
        evaluation = evaluate_ranking(
            represented_history, current=current, candidate=candidate, genre=genre, length=length
        )
        learning = LearningContext(
            encoder_fingerprint=fingerprint,
            description_fingerprint=description_fingerprint,
            documents=documents,
            index=index,
            model=fit_hybrid(history, index, recommendation_features),
            evaluation=evaluation,
        )
        report = build_recommendations(data, analysis, learning=learning)
        self._event(
            S.REC3_LOG_FINISHED.format(
                ranked=len(report.ranked),
                abstained=len(report.unrankable),
                shortlist=len(report.shortlist),
                active=S.REC3_PDF_ACTIVE if evaluation.activation_eligible else S.REC3_PDF_INACTIVE,
            )
        )
        return self.repository.publish(report)
