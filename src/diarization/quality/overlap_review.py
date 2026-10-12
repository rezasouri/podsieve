"""Export every overlap-specific finding as an individually reviewable clip."""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Sequence

import soundfile as sf

from .schemas import Candidate, QualityConfig
from .overlap import union_intervals
from .schemas import Interval


ISSUE_CATEGORY = {
    "confirmed_output_overlap": "detected_overlap",
    "missed_overlap_candidate": "missed_overlap_candidate",
    "uncertain_overlap_candidate": "uncertain_overlap_candidate",
    "spurious_overlap_candidate": "uncertain_overlap_candidate",
}


def export_overlap_review(audio_path: Path, output_dir: Path, candidates: Sequence[Candidate],
                          config: QualityConfig, *, audio_duration: float,
                          context_seconds: float = 1.0, export_audio: bool = True,
                          clip_path_prefix: str = "clips") -> dict:
    selected: dict[tuple[str, int, int], Candidate] = {}
    for candidate in candidates:
        categories = sorted({ISSUE_CATEGORY[issue] for issue in candidate.issue_types if issue in ISSUE_CATEGORY})
        for category in categories:
            key = (category, round(candidate.start * 1000), round(candidate.end * 1000))
            if key not in selected:
                selected[key] = candidate

    base_rows = []
    for (category, start_ms, end_ms), candidate in selected.items():
        features = candidate.features
        speakers = (features.get("speakers") or features.get("active_speakers")
                    or features.get("overlap_speakers") or features.get("diarized_speakers") or [])
        evidence_value = (features.get("weaker_activity") or features.get("second_speaker_activity")
                          or features.get("overlap_evidence_score"))
        base_rows.append({
            "start": start_ms / 1000,
            "end": end_ms / 1000,
            "category": category,
            "speakers": sorted(set(str(item) for item in speakers)),
            "overlap_evidence_score": evidence_value,
            "review_priority_score": candidate.review_score,
            "evidence_sources": candidate.evidence_available,
            "evidence_provenance": candidate.evidence_provenance,
            "issue_types": candidate.issue_types,
            "features": candidate.features,
        })
    base_rows.sort(key=lambda row: (-row["review_priority_score"], row["start"], row["end"], row["category"]))
    for index, row in enumerate(base_rows, 1):
        prefix = {"detected_overlap": "detected", "missed_overlap_candidate": "missed_candidate",
                  "uncertain_overlap_candidate": "uncertain"}[row["category"]]
        row["candidate_id"] = f"OVERLAP_{index:04d}_{prefix}"
        row["duration_seconds"] = round(row["end"] - row["start"], 6)
        row["review_status"] = "unreviewed"
        row["notes"] = ""

    output_dir.mkdir(parents=True, exist_ok=True)
    clip_dir = output_dir / "clips"
    if export_audio:
        clip_dir.mkdir(parents=True, exist_ok=True)
    with sf.SoundFile(audio_path) as audio:
        sample_rate = audio.samplerate
        frame_count = len(audio)
        for row in base_rows:
            if export_audio:
                clip_start = max(0, math.floor((row["start"] - context_seconds) * sample_rate))
                clip_end = min(frame_count, math.ceil((row["end"] + context_seconds) * sample_rate))
                if clip_end <= clip_start:
                    raise ValueError(f"invalid overlap candidate interval: {row['candidate_id']}")
                audio.seek(clip_start)
                samples = audio.read(clip_end - clip_start, dtype="float32", always_2d=True)
                clip_name = f"{row['candidate_id']}.wav"
                clip_path = clip_dir / clip_name
                sf.write(clip_path, samples, sample_rate, subtype="PCM_16")
                clip_info = sf.info(clip_path)
                if clip_info.frames != clip_end - clip_start or clip_info.samplerate != sample_rate:
                    raise ValueError(f"exported overlap clip failed verification: {clip_path}")
                row["clip_start_seconds"] = clip_start / sample_rate
                row["clip_end_seconds"] = clip_end / sample_rate
                row["review_wav_path"] = str(Path(clip_path_prefix) / clip_name)
            else:
                row["clip_start_seconds"] = None
                row["clip_end_seconds"] = None
                row["review_wav_path"] = None

    payload = [{key: row[key] for key in (
        "candidate_id", "start", "end", "duration_seconds", "category", "speakers",
        "overlap_evidence_score", "review_priority_score", "evidence_sources",
        "evidence_provenance", "issue_types", "features", "review_wav_path",
        "clip_start_seconds", "clip_end_seconds", "review_status", "notes")}
        for row in base_rows]
    json_path = output_dir / "overlap_candidates.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = output_dir / "overlap_candidates.csv"
    fields = list(payload[0]) if payload else ["candidate_id", "start", "end", "duration_seconds", "category",
                                                "speakers", "overlap_evidence_score", "review_priority_score",
                                                "evidence_sources", "evidence_provenance", "issue_types", "features",
                                                "review_wav_path", "clip_start_seconds", "clip_end_seconds", "review_status", "notes"]
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in payload:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                             if isinstance(value, (dict, list)) else value for key, value in row.items()})

    unique_duration = sum(item.end - item.start for item in union_intervals(
        [Interval(row["start"], row["end"]) for row in base_rows]))
    counts = dict(Counter(row["category"] for row in base_rows))
    summary = {
        "audio_duration_seconds": round(audio_duration, 6),
        "candidate_count": len(payload), "counts_by_category": counts,
        "candidate_duration_seconds_sum": round(sum(row["duration_seconds"] for row in base_rows), 6),
        "unique_candidate_duration_seconds": round(unique_duration, 6),
        "audio_review_percent": round(unique_duration / audio_duration * 100, 3) if audio_duration else None,
        "context_seconds_each_side": context_seconds,
        "clips_exported": export_audio,
        "thresholds": {"activity_threshold": config.activity_threshold,
                       "activity_margin_threshold": config.activity_margin_threshold,
                       "minimum_activity_interval_seconds": config.minimum_activity_interval,
                       "cluster_margin_threshold": config.cluster_margin_threshold,
                       "score_minimum_applied": False,
                       "top_k_limit_applied": False},
        "clip_source": str(audio_path), "sample_rate": sample_rate,
        "all_clips_verified": export_audio,
    }
    summary_path = output_dir / "overlap_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    readme = """# Overlap review\n\nListen to each WAV in `clips/` and record the result in `overlap_candidates.csv` or `overlap_candidates.json`. `start` and `end` are source timestamps for the candidate itself. `clip_start_seconds` and `clip_end_seconds` include one second of listening context on each side when available. Padding is not overlap evidence.\n\nCategories:\n\n- `detected_overlap`: the final diarization contains two or more speakers at once.\n- `missed_overlap_candidate`: segmentation activity indicates concurrent speakers absent from the final annotation.\n- `uncertain_overlap_candidate`: weaker or inconsistent concurrent activity, including possible false output overlap.\n\nEvery row starts with `review_status=unreviewed` and empty `notes`. Scores are review priorities, not probabilities.\n"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")
    return summary
