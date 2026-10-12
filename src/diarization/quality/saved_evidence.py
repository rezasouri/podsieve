"""Read validated, native diarization evidence without loading any model."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from ..evidence import validate_evidence
from .clustering import cluster_candidates
from .schemas import ActivityFrame, Interval


class SavedEvidenceAdapter:
    def __init__(self, path: Path, *, audio_path: Path, annotation_path: Path):
        self.path = path
        self.manifest = validate_evidence(path, audio_path=audio_path, annotation_path=annotation_path)
        self.meta = self.manifest["metadata"]

    def _array(self, name: str) -> np.ndarray:
        spec = self.manifest["files"][name]
        return np.load(self.path / spec["file"], mmap_mode="r", allow_pickle=False)

    def segment_embeddings(self) -> dict[int, Sequence[float]]:
        vectors = self._array("segment_embeddings")
        return {i: vectors[i] for i in range(len(vectors)) if np.all(np.isfinite(vectors[i]))}

    def activity_frames(self) -> list[ActivityFrame]:
        values = self._array("mapped_activity")
        labels = self.meta["speaker_labels"]
        resolution = self.meta["mapped_activity_resolution"]
        duration = self.meta["audio_duration_seconds"]
        return [ActivityFrame(i * resolution, min(duration, (i + 1) * resolution),
                              {label: float(values[i, j]) for j, label in enumerate(labels)})
                for i in range(len(values)) if i * resolution < duration]

    def independent_vad(self) -> list[Interval]:
        return [Interval(float(start), float(end)) for start, end in self._array("independent_vad")]

    def provenance(self) -> dict[str, str]:
        return {"adapter": type(self).__name__, "model": self.meta["model"],
                "pyannote_audio_version": self.meta["pyannote_audio_version"],
                "evidence_manifest": str(self.path / "manifest.json")}

    def statistics(self) -> dict[str, object]:
        status = self._array("segment_embedding_status")
        assignments = self._array("effective_cluster_assignments")
        return {"segment_embeddings_extracted": int(np.sum(status == 0)),
                "chunk_embeddings_finite": int(np.sum(np.all(np.isfinite(self._array("chunk_embeddings")), axis=2))),
                "active_cluster_assignments": int(np.sum(assignments >= 0)),
                "prototype_reference_counts": self._array("speaker_prototype_reference_counts").tolist(),
                "independent_vad_intervals": len(self._array("independent_vad"))}

    def clustering_candidates(self, segments, margin_threshold: float):
        names = ("cluster_scores", "effective_cluster_assignments", "chunk_embeddings")
        return cluster_candidates(segments, {name: self._array(name) for name in names}, self.meta,
                                  margin_threshold=margin_threshold)
