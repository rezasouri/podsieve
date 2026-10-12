"""Diagnostics using the clustering scores produced by the diarization model."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .schemas import Candidate, Segment


def cluster_candidates(segments: Sequence[Segment], arrays: dict[str, np.ndarray], metadata: dict,
                       *, margin_threshold: float = 0.12) -> list[Candidate]:
    scores = arrays["cluster_scores"]
    assignments = arrays["effective_cluster_assignments"]
    embeddings = arrays["chunk_embeddings"]
    if scores.shape[-1] < 2:
        return []
    window = metadata["windows"]["segmentation"]
    mapping = metadata["cluster_to_speaker"]
    result: list[Candidate] = []
    for chunk in range(scores.shape[0]):
        start = window["start"] + chunk * window["step"]
        end = start + window["duration"]
        for channel in range(scores.shape[1]):
            assigned = int(assignments[chunk, channel])
            if assigned < 0 or not np.all(np.isfinite(embeddings[chunk, channel])):
                continue
            values = scores[chunk, channel]
            if not np.all(np.isfinite(values)):
                continue
            alternatives = [(j, float(value)) for j, value in enumerate(values) if j != assigned]
            if not alternatives:
                continue
            other, other_score = max(alternatives, key=lambda item: item[1])
            margin = float(values[assigned] - other_score)
            if margin >= margin_threshold:
                continue
            assigned_label = mapping.get(str(assigned))
            other_label = mapping.get(str(other))
            if assigned_label is None or other_label is None:
                continue
            matches = [s for s in segments if s.speaker == assigned_label and s.start < end and s.end > start]
            if not matches:
                continue
            match = max(matches, key=lambda s: min(s.end, end) - max(s.start, start))
            result.append(Candidate(max(start, match.start), min(end, match.end), assigned_label, other_label,
                ["cluster_assignment_ambiguity"],
                features={"native_score_assigned": round(float(values[assigned]), 6),
                          "native_score_alternative": round(other_score, 6),
                          "native_score_margin": round(margin, 6),
                          "cluster_metric": metadata["cluster_metric"],
                          "chunk_index": chunk, "local_channel": channel},
                feature_scores={"cluster_margin": min(1.0, max(0.0, (margin_threshold - margin) / (2 * margin_threshold)))},
                evidence_available=["native_clustering_scores"]))
    return result
