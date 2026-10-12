from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from .overlap import confirmed_overlap, interval_overlap
from .schemas import Candidate, Interval, QualityConfig, Segment


def _unit(values: Sequence[float]) -> np.ndarray | None:
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1 or not vector.size or not np.all(np.isfinite(vector)):
        return None
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 else None


def _reliable_subset(indexed: list[tuple[int, np.ndarray]]) -> list[tuple[int, np.ndarray]]:
    if not indexed:
        return []
    centre = _unit(np.mean([vector for _, vector in indexed], axis=0))
    if centre is None:
        return []
    if len(indexed) < 4:
        return indexed
    similarities = np.array([float(vector @ centre) for _, vector in indexed])
    keep = np.argsort(similarities)[len(indexed) // 4:]
    return [indexed[int(i)] for i in keep]


def speaker_confusion(
    segments: Sequence[Segment], embeddings: Mapping[int, Sequence[float]], config: QualityConfig
) -> tuple[list[Candidate], list[str]]:
    """Cosine margins against clean, leave-one-out speaker prototypes."""
    overlap = [interval for interval, _ in confirmed_overlap(segments)]
    clean: dict[str, list[tuple[int, np.ndarray]]] = {}
    warnings: list[str] = []
    dimensions: set[int] = set()
    for segment in segments:
        if segment.duration < config.minimum_segment_duration:
            continue
        if any(interval_overlap(Interval(segment.start, segment.end), item) > 0 for item in overlap):
            continue
        raw = embeddings.get(segment.index)
        vector = _unit(raw) if raw is not None else None
        if vector is not None:
            dimensions.add(vector.size)
            clean.setdefault(segment.speaker, []).append((segment.index, vector))
    if len(dimensions) > 1:
        return [], ["Embedding dimensions disagree; speaker comparison unavailable."]
    reliable = {speaker: _reliable_subset(indexed) for speaker, indexed in clean.items()}
    reference_sums = {
        speaker: np.sum([vector for _, vector in indexed], axis=0)
        for speaker, indexed in reliable.items() if indexed
    }
    references = {speaker: _unit(values) for speaker, values in reference_sums.items()}
    candidates: list[Candidate] = []
    for segment in segments:
        if segment.duration < config.minimum_segment_duration:
            continue
        if any(interval_overlap(Interval(segment.start, segment.end), item) > 0 for item in overlap):
            continue
        vector = _unit(embeddings[segment.index]) if segment.index in embeddings else None
        if vector is None or vector.size not in dimensions:
            continue
        own_indexed = reliable.get(segment.speaker, [])
        own = [(index, value) for index, value in own_indexed if index != segment.index]
        if len(own) < config.minimum_reference_segments:
            own = [(index, value) for index, value in clean.get(segment.speaker, []) if index != segment.index]
        if len(own) < config.minimum_reference_segments:
            continue
        if len(own_indexed) == len(own) + 1:
            own_reference = _unit(reference_sums[segment.speaker] - vector)
        else:
            own_reference = _unit(np.sum([value for _, value in own], axis=0))
        if own_reference is None:
            continue
        others: list[tuple[str, float]] = []
        for speaker, indexed in reliable.items():
            if speaker == segment.speaker or len(indexed) < config.minimum_reference_segments:
                continue
            reference = references[speaker]
            if reference is not None:
                others.append((speaker, float(vector @ reference)))
        if not others:
            continue
        other, alternative_similarity = max(others, key=lambda item: (item[1], item[0]))
        assigned_similarity = float(vector @ own_reference)
        margin = assigned_similarity - alternative_similarity
        if margin < config.embedding_margin_threshold:
            candidates.append(Candidate(
                start=segment.start, end=segment.end, assigned_speaker=segment.speaker,
                candidate_speaker=other, issue_types=["speaker_confusion_candidate"],
                features={"assigned_similarity": round(assigned_similarity, 6),
                          "alternative_similarity": round(alternative_similarity, 6),
                          "speaker_margin": round(margin, 6)},
                feature_scores={"speaker_margin": min(1.0, max(0.0, (config.embedding_margin_threshold - margin) / max(.2, config.embedding_margin_threshold)))},
                evidence_available=["speaker_embeddings"],
            ))
    reference_speakers = sum(len(items) >= config.minimum_reference_segments for items in reliable.values())
    if reference_speakers < 2 or not any(
        len(items) >= config.minimum_reference_segments + 1 for items in clean.values()
    ):
        warnings.append("Insufficient clean reference speech from two speakers for embedding comparison.")
    return candidates, warnings
