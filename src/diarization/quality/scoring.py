from __future__ import annotations

from collections.abc import Sequence

from .schemas import Candidate, QualityConfig


def rank_candidates(candidates: Sequence[Candidate], config: QualityConfig) -> list[Candidate]:
    scale = max(config.weights.values(), default=1.0) or 1.0
    for candidate in candidates:
        present = [(config.weights.get(name, 0.0), min(1.0, max(0.0, value)))
                   for name, value in candidate.feature_scores.items()]
        candidate.review_score = round(min(1.0, sum(weight * value for weight, value in present) / scale), 6)
        if any(feature in candidate.evidence_available for feature in ("speaker_embeddings", "frame_activity", "independent_vad", "native_clustering_scores")):
            candidate.ranking_group = "model_or_activity_evidence"
        else:
            candidate.ranking_group = "annotation_timing_only"
        candidate.issue_types = sorted(set(candidate.issue_types))
        candidate.evidence_available = sorted(set(candidate.evidence_available))
    ordered = sorted(candidates, key=lambda item: (
        0 if item.ranking_group == "model_or_activity_evidence" else 1,
        -item.review_score, item.start, item.end,
        item.assigned_speaker or "", ",".join(item.issue_types),
    ))
    for index, item in enumerate(ordered, 1):
        item.rank = index
    return ordered
