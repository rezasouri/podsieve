from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Protocol, Sequence


ANALYZER_VERSION = "1.0"


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    speaker: str
    index: int

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Interval:
    start: float
    end: float


@dataclass(frozen=True)
class ActivityFrame:
    start: float
    end: float
    activities: Mapping[str, float]


class EvidenceAdapter(Protocol):
    """Optional, timestamped evidence supplied without running diarization."""

    def segment_embeddings(self) -> Mapping[int, Sequence[float]]: ...
    def activity_frames(self) -> Sequence[ActivityFrame]: ...
    def independent_vad(self) -> Sequence[Interval]: ...


@dataclass(frozen=True)
class QualityConfig:
    enabled: bool = True
    expected_num_speakers: int | None = None
    embedding_analysis: bool = True
    overlap_analysis: bool = True
    temporal_analysis: bool = True
    segmentation_analysis: bool = True
    speech_activity_analysis: bool = True
    minimum_segment_duration: float = 0.5
    minimum_reference_segments: int = 2
    short_turn_seconds: float = 0.7
    rapid_switch_seconds: float = 1.2
    short_gap_seconds: float = 0.15
    boundary_window_seconds: float = 0.25
    activity_threshold: float = 0.5
    activity_margin_threshold: float = 0.1
    minimum_activity_interval: float = 0.2
    embedding_margin_threshold: float = 0.1
    cluster_margin_threshold: float = 0.12
    review_padding_seconds: float = 0.5
    export_review_clips: bool = True
    weights: Mapping[str, float] = field(default_factory=lambda: {
        "speaker_margin": 1.0,
        "short_turn": 0.4,
        "rapid_switch": 0.6,
        "short_gap": 0.25,
        "confirmed_overlap": 0.3,
        "missed_overlap": 0.8,
        "spurious_overlap": 0.8,
        "uncertain_overlap": 0.7,
        "boundary_uncertainty": 0.5,
        "activity_disagreement": 0.7,
        "cluster_margin": 0.8,
    })

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> QualityConfig:
        known = set(cls.__dataclass_fields__)
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"unknown diarization_quality settings: {sorted(unknown)}")
        data = dict(values)
        if "weights" in data:
            data["weights"] = {str(k): float(v) for k, v in data["weights"].items()}
        result = cls(**data)
        for name in ("minimum_segment_duration", "short_turn_seconds", "rapid_switch_seconds",
                     "short_gap_seconds", "boundary_window_seconds", "minimum_activity_interval",
                     "review_padding_seconds", "embedding_margin_threshold", "cluster_margin_threshold"):
            if getattr(result, name) < 0:
                raise ValueError(f"diarization_quality.{name} must be non-negative")
        if result.minimum_reference_segments < 1:
            raise ValueError("minimum_reference_segments must be positive")
        if result.expected_num_speakers is not None and result.expected_num_speakers < 1:
            raise ValueError("expected_num_speakers must be positive")
        if not 0 <= result.activity_threshold <= 1 or not 0 <= result.activity_margin_threshold <= 1:
            raise ValueError("activity thresholds must be between 0 and 1")
        if any(value < 0 for value in result.weights.values()):
            raise ValueError("quality weights must be non-negative")
        return result

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Candidate:
    start: float
    end: float
    assigned_speaker: str | None
    candidate_speaker: str | None
    issue_types: list[str]
    source_id: str | None = None
    features: dict[str, float | int | str | list[str]] = field(default_factory=dict)
    feature_scores: dict[str, float] = field(default_factory=dict)
    evidence_available: list[str] = field(default_factory=list)
    evidence_provenance: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    review_score: float = 0.0
    ranking_group: str = "temporal_only"
    rank: int = 0
    review_clip: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
