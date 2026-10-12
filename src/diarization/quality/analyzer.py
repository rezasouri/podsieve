from __future__ import annotations

import json
import math
import shutil
import tempfile
import uuid
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping, Sequence

import soundfile as sf

from .embeddings import speaker_confusion
from .overlap import confirmed_overlap, interval_overlap, union_intervals
from .overlap_review import export_overlap_review
from .schemas import ANALYZER_VERSION, ActivityFrame, Candidate, EvidenceAdapter, Interval, QualityConfig, Segment
from .scoring import rank_candidates
from .segmentation import activity_candidates, vad_disagreement_candidates
from .temporal import temporal_candidates
from .writers import export_group_clips, export_review_clips, merge_review_candidates, write_results


def _finite_time(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"invalid timestamp: {value!r}")
    return number


def read_diarization(path: Path) -> list[Segment]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        document = json.loads(path.read_text(encoding="utf-8"))
        rows = document["segments"]
        if not isinstance(rows, list):
            raise ValueError("diarization JSON segments must be a list")
        segments = [Segment(_finite_time(row["start"]), _finite_time(row["end"]),
                            str(row["speaker"]), int(row.get("index", index)))
                    for index, row in enumerate(rows)]
    elif path.suffix.lower() == ".rttm":
        segments = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 8 or parts[0] != "SPEAKER":
                raise ValueError(f"invalid RTTM line {line_number}")
            start, duration = _finite_time(parts[3]), _finite_time(parts[4])
            segments.append(Segment(start, start + duration, parts[7], len(segments)))
    else:
        raise ValueError("diarization input must be .json or .rttm")
    for item in segments:
        if item.end <= item.start or not item.speaker:
            raise ValueError(f"invalid diarization segment: {item}")
    if len({item.index for item in segments}) != len(segments):
        raise ValueError("diarization segment indices must be unique")
    return segments


def read_optional_features(path: Path | None) -> tuple[dict[int, Sequence[float]], list[ActivityFrame], list[Interval], dict[str, Any]]:
    if path is None:
        return {}, [], [], {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("features file must contain a JSON object")
    embeddings = {int(key): value for key, value in data.get("segment_embeddings", {}).items()}
    frames = [ActivityFrame(_finite_time(row["start"]), _finite_time(row["end"]),
                            {str(k): float(v) for k, v in row["activities"].items()})
              for row in data.get("activity_frames", [])]
    vad = [Interval(_finite_time(row["start"]), _finite_time(row["end"]))
           for row in data.get("independent_vad", [])]
    if any(item.end <= item.start for item in [*frames, *vad]):
        raise ValueError("feature intervals must have positive duration")
    if any(not 0 <= value <= 1 or not math.isfinite(value)
           for frame in frames for value in frame.activities.values()):
        raise ValueError("frame activities must be finite values in [0, 1]")
    if frames and not data.get("activity_source"):
        raise ValueError("activity_frames require an activity_source description")
    if frames and data.get("timebase") != "global_seconds":
        raise ValueError("activity_frames require timebase='global_seconds'")
    if frames and data.get("speaker_label_space") != "final_diarization":
        raise ValueError("activity_frames require speaker_label_space='final_diarization'")
    if embeddings and not data.get("embedding_source"):
        raise ValueError("segment_embeddings require an embedding_source description")
    if vad and data.get("vad_source") != "independent":
        raise ValueError("independent_vad requires vad_source='independent'")
    return embeddings, frames, vad, {"activity_source": data.get("activity_source"),
                                     "vad_source": data.get("vad_source"),
                                     "embedding_source": data.get("embedding_source")}


def analyze_source(
    *, source_id: str, audio_path: Path, diarization_path: Path, output_dir: Path,
    config: QualityConfig, features_path: Path | None = None, top_k: int | None = 30,
    min_score: float = 0.0, export_clips: bool | None = None, overwrite: bool = False,
    reference_rttm: Path | None = None, collar: float = 0.0, skip_overlap: bool = False,
    evidence_adapter: EvidenceAdapter | None = None,
    configured_backend: str = "pyannote/speaker-diarization-3.1",
) -> dict[str, Any]:
    """Analyze existing output only; this function never loads a diarization model."""
    if not config.enabled:
        raise ValueError("diarization_quality.enabled is false")
    if top_k is not None and top_k < 1:
        raise ValueError("top_k must be positive")
    if not 0 <= min_score <= 1:
        raise ValueError("min_score must be between 0 and 1")
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)
    if evidence_adapter is not None and features_path is not None:
        raise ValueError("use either an evidence adapter or --features-file")
    segments = read_diarization(diarization_path)
    info = sf.info(str(audio_path))
    duration = info.frames / info.samplerate
    if any(item.end > duration + 0.05 for item in segments):
        raise ValueError("diarization timestamps exceed vocals audio duration")
    if evidence_adapter is not None:
        embeddings = dict(evidence_adapter.segment_embeddings())
        frames = list(evidence_adapter.activity_frames())
        vad = list(evidence_adapter.independent_vad())
        evidence_sources = (evidence_adapter.provenance() if hasattr(evidence_adapter, "provenance")
                            else {"adapter": type(evidence_adapter).__name__})
    else:
        embeddings, frames, vad, evidence_sources = read_optional_features(features_path)
    if any(not math.isfinite(item.start) or not math.isfinite(item.end)
           or item.end <= item.start or item.start < 0 for item in [*frames, *vad]):
        raise ValueError("evidence intervals must have non-negative start and positive duration")
    if any(not math.isfinite(value) or not 0 <= value <= 1
           for frame in frames for value in frame.activities.values()):
        raise ValueError("frame activities must be finite values in [0, 1]")
    if any(item.end > duration + 0.05 for item in [*frames, *vad]):
        raise ValueError("feature timestamps exceed vocals audio duration")
    candidates: list[Candidate] = []
    warnings: list[str] = []
    embedding_warnings: list[str] = []
    overlap = confirmed_overlap(segments) if config.overlap_analysis else []
    for interval, speakers in overlap:
        candidates.append(Candidate(interval.start, interval.end, None, None,
            ["confirmed_output_overlap"], features={"speakers": list(speakers)},
            feature_scores={"confirmed_overlap": 0.5}, evidence_available=["diarization_annotation"]))
    if config.temporal_analysis:
        candidates.extend(temporal_candidates(segments, config))
    if config.embedding_analysis and embeddings:
        found, messages = speaker_confusion(segments, embeddings, config)
        candidates.extend(found)
        warnings.extend(messages)
        embedding_warnings.extend(messages)
    if evidence_adapter is not None and hasattr(evidence_adapter, "clustering_candidates"):
        candidates.extend(evidence_adapter.clustering_candidates(segments, config.cluster_margin_threshold))
    if frames and (config.segmentation_analysis or config.overlap_analysis):
        candidates.extend(activity_candidates(
            segments, frames, config,
            include_overlap=config.overlap_analysis,
            include_boundaries=config.segmentation_analysis,
        ))
    if config.speech_activity_analysis and vad:
        candidates.extend(vad_disagreement_candidates(segments, vad, config))
    speakers = sorted({s.speaker for s in segments})
    if config.expected_num_speakers is not None and len(speakers) != config.expected_num_speakers:
        warnings.append(f"Observed {len(speakers)} speakers; expected {config.expected_num_speakers}.")
    vad_extracted = bool(vad) or (evidence_adapter is not None and
                                  "independent_vad" in getattr(evidence_adapter, "meta", {}))
    availability = {
        "speaker_embeddings": bool(embeddings) and not embedding_warnings if config.embedding_analysis else False,
        "confirmed_output_overlap": config.overlap_analysis,
        "missed_overlap_evidence": bool(frames) if config.overlap_analysis else False,
        "temporal_patterns": config.temporal_analysis,
        "segmentation_uncertainty": bool(frames) if config.segmentation_analysis else False,
        "independent_speech_activity": vad_extracted if config.speech_activity_analysis else False,
        "native_clustering_scores": evidence_adapter is not None and hasattr(evidence_adapter, "clustering_candidates"),
    }
    feature_status = {
        "speaker_embeddings": "disabled" if not config.embedding_analysis else (
            "unavailable: no embeddings supplied" if not embeddings else (
                "unavailable: " + embedding_warnings[0] if embedding_warnings else "available")),
        "missed_overlap_evidence": "disabled" if not config.overlap_analysis else (
            "available" if frames else "unavailable: no compatible frame activity supplied"),
        "segmentation_uncertainty": "disabled" if not config.segmentation_analysis else (
            "available" if frames else "unavailable: no compatible frame activity supplied"),
        "independent_speech_activity": "disabled" if not config.speech_activity_analysis else (
            "available" if vad else ("available: detector returned no speech" if vad_extracted
                                     else "unavailable: no independent VAD supplied")),
        "native_clustering_scores": "available" if availability["native_clustering_scores"] else "unavailable: no saved clustering scores",
    }
    ranked = rank_candidates(candidates, config)
    for item in ranked:
        item.source_id = source_id
        item.evidence_provenance = dict(evidence_sources)
    selected = [item for item in ranked if item.review_score >= min_score]
    if top_k is not None:
        selected = selected[:top_k]
    review_groups = merge_review_candidates(selected)
    speech_duration = sum(item.end - item.start for item in union_intervals(
        [Interval(item.start, item.end) for item in segments]))
    review_duration = sum(item.end - item.start for item in union_intervals(
        [Interval(item.start, item.end) for item in selected]))
    issue_counts: dict[str, int] = {}
    for candidate in ranked:
        for issue in candidate.issue_types:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    try:
        pyannote_version = version("pyannote.audio")
    except PackageNotFoundError:
        pyannote_version = None
    summary: dict[str, Any] = {
        "analyzer_version": ANALYZER_VERSION, "source_id": source_id,
        "configured_backend": configured_backend, "audio_path": str(audio_path),
        "pyannote_audio_version": pyannote_version,
        "model_revision": (getattr(evidence_adapter, "meta", {}).get("model_revision", "unavailable: not recorded")
                           if evidence_adapter is not None else "unavailable: not recorded in existing diarization output"),
        "audio_duration_seconds": round(duration, 6), "sample_rate": info.samplerate,
        "speaker_count": len(speakers), "segment_count": len(segments),
        "confirmed_overlap_count": len(overlap), "candidate_count": len(ranked),
        "exported_candidate_count": len(selected), "feature_availability": availability,
        "review_group_count": len(review_groups),
        "issue_counts": issue_counts,
        "speech_duration_seconds": round(speech_duration, 6),
        "review_duration_seconds": round(review_duration, 6),
        "review_duration_as_speech_percent": round(100 * review_duration / speech_duration, 2) if speech_duration else None,
        "feature_status": feature_status,
        "evidence_sources": evidence_sources, "warnings": warnings,
        "evidence_statistics": (evidence_adapter.statistics() if evidence_adapter is not None
                                and hasattr(evidence_adapter, "statistics") else {}),
        "configuration": config.as_dict(), "ranking_method": "weighted sum of available feature scores divided by maximum configured weight; model evidence grouped first; review priority, not error probability",
        "ranking_filters": {"top_k": top_k, "min_score": min_score},
    }
    if reference_rttm is not None:
        from .evaluation import evaluate_reference
        summary["ground_truth_evaluation"] = evaluate_reference(
            reference_rttm, segments, selected, collar=collar, skip_overlap=skip_overlap)
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"quality output already exists in {output_dir}; pass --overwrite")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-building-", dir=output_dir.parent))
    backup: Path | None = None
    try:
        should_export_clips = export_clips if export_clips is not None else config.export_review_clips
        review_clip_root = staging / "review_clips"
        overlap_build = staging / ".overlap-review-building"
        if should_export_clips:
            export_review_clips(
                audio_path, review_clip_root / "suspicious", selected,
                config.review_padding_seconds,
                relative_dir="review_clips/suspicious",
            )
            export_group_clips(
                audio_path, review_clip_root / "groups", review_groups,
                config.review_padding_seconds,
                relative_dir="review_clips/groups",
            )
        overlap_summary = export_overlap_review(
            audio_path, overlap_build, ranked, config, audio_duration=duration,
            export_audio=should_export_clips,
            clip_path_prefix="review_clips/overlap",
        )
        if should_export_clips:
            overlap_clip_dir = review_clip_root / "overlap"
            overlap_clip_dir.parent.mkdir(parents=True, exist_ok=True)
            generated_clips = overlap_build / "clips"
            if generated_clips.exists():
                generated_clips.rename(overlap_clip_dir)
        for filename in ("overlap_candidates.csv", "overlap_candidates.json", "overlap_summary.json"):
            generated = overlap_build / filename
            if generated.exists():
                generated.replace(staging / filename)
        if overlap_build.exists():
            shutil.rmtree(overlap_build)
        summary["overlap_review"] = {
            "candidate_count": overlap_summary["candidate_count"],
            "counts_by_category": overlap_summary["counts_by_category"],
            "directory": "review_clips/overlap" if should_export_clips else None,
            "clips_exported": should_export_clips,
            "minimum_score_applied": False,
            "top_k_limit_applied": False,
        }
        (staging / "README.md").write_text(
            "# Diarization quality review\n\n"
            "`suspicious_segments.csv` lists ranked quality findings. "
            "`overlap_candidates.csv` lists all overlap findings. WAV excerpts are grouped under "
            "`review_clips/suspicious/`, `review_clips/groups/`, and `review_clips/overlap/`. "
            "Candidates require listening review; scores are priorities, not probabilities.\n",
            encoding="utf-8",
        )
        write_results(staging, selected, summary, overwrite=False, groups=review_groups)
        if output_dir.exists():
            backup = output_dir.with_name(f".{output_dir.name}-previous-{uuid.uuid4().hex}")
            output_dir.rename(backup)
        try:
            staging.rename(output_dir)
        except OSError:
            if backup is not None:
                backup.rename(output_dir)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return summary
