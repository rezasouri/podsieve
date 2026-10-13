from __future__ import annotations

import csv
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any


_SAFE_LABEL = re.compile(r"[^A-Za-z0-9._-]+")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"expected a JSON list in {path}")
    return [row for row in value if isinstance(row, dict)]


def _safe_label(value: str) -> str:
    return _SAFE_LABEL.sub("_", value).strip("._-") or "SPEAKER"


def _overlaps(start: float, end: float, windows: list[tuple[float, float]]) -> bool:
    return any(left < end and right > start for left, right in windows)


def publish_clean_segments(
    *,
    source_id: str,
    temporary_segments_dir: Path,
    segments: list[dict[str, Any]],
    quality_dir: Path,
    final_dir: Path,
    padding_seconds: float,
    overwrite: bool,
    quality_analysis: bool,
) -> dict[str, Any]:
    """Publish unflagged diarization clips and stable manifests as one final artifact."""
    if final_dir.exists() and any(final_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"final diarization segments already exist in {final_dir}; pass --overwrite")

    suspicious = _load_rows(quality_dir / "suspicious_segments.json") if quality_analysis else []
    overlap_candidates = (
        _load_rows(quality_dir / "overlap_candidates.json")
        if quality_analysis else []
    )
    excluded_windows = [
        (float(row["start"]), float(row["end"]))
        for row in suspicious
        if row.get("start") is not None and row.get("end") is not None
    ]
    for row in overlap_candidates:
        # Missed overlap rows are model-generated review candidates, not
        # confirmed errors. Keep them in diagnostics without discarding a
        # complete diarization turn from the final output.
        if row.get("category") != "detected_overlap":
            continue
        start = row.get("clip_start_seconds")
        end = row.get("clip_end_seconds")
        if start is None or end is None:
            start, end = row.get("start"), row.get("end")
        if start is not None and end is not None:
            excluded_windows.append((float(start), float(end)))

    selected: list[dict[str, Any]] = []
    unavailable_indices: list[int] = []
    excluded_indices: list[int] = []
    stage_dir = final_dir.with_name(f".{final_dir.name}-building-{uuid.uuid4().hex}")
    stage_segments = stage_dir / "segments"
    stage_segments.mkdir(parents=True)
    try:
        for row in segments:
            index = int(row["index"])
            speaker = str(row["speaker"])
            filename = f"{_safe_label(speaker)}_{index:04d}.wav"
            clip = temporary_segments_dir / filename
            if not clip.is_file():
                unavailable_indices.append(index)
                continue
            start = max(0.0, float(row["start"]) - padding_seconds)
            end = float(row["end"]) + padding_seconds
            if _overlaps(start, end, excluded_windows):
                excluded_indices.append(index)
                continue

            relative_path = Path("segments") / _safe_label(speaker) / filename
            destination = stage_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(clip, destination)
            selected.append({
                "index": index,
                "speaker": speaker,
                "start": float(row["start"]),
                "end": float(row["end"]),
                "duration_seconds": round(float(row["end"]) - float(row["start"]), 6),
                "file": relative_path.as_posix(),
                "classification": "not_flagged_by_quality_review" if quality_analysis else "quality_analysis_disabled",
            })

        selected.sort(key=lambda item: (item["speaker"], item["start"], item["index"]))
        fields = ["index", "speaker", "start", "end", "duration_seconds", "file", "classification"]
        with (stage_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(selected)

        manifest = {
            "schema_version": "1.0",
            "source_id": source_id,
            "output": "final/segments",
            "classification": "segments not intersecting ranked quality findings or detected output overlaps; missed-overlap candidates remain for listening review",
            "quality_analysis_enabled": quality_analysis,
            "quality_review_windows": len(suspicious),
            "overlap_review_windows": len(overlap_candidates),
            "overlap_windows_used_for_exclusion": sum(
                row.get("category") == "detected_overlap" for row in overlap_candidates
            ),
            "segment_export_padding_seconds": padding_seconds,
            "diarization_segment_count": len(segments),
            "published_segment_count": len(selected),
            "excluded_by_quality_review_count": len(excluded_indices),
            "wav_not_exported_count": len(unavailable_indices),
            "excluded_segment_indices": excluded_indices,
            "wav_not_exported_segment_indices": unavailable_indices,
            "speaker_counts": {
                speaker: sum(item["speaker"] == speaker for item in selected)
                for speaker in sorted({item["speaker"] for item in selected})
            },
            "files": "manifest.csv",
        }
        (stage_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        backup_dir: Path | None = None
        if final_dir.exists():
            backup_dir = final_dir.with_name(f".{final_dir.name}-previous-{uuid.uuid4().hex}")
            final_dir.rename(backup_dir)
        try:
            stage_dir.rename(final_dir)
        except OSError:
            if backup_dir is not None:
                backup_dir.rename(final_dir)
                backup_dir = None
            raise
        if backup_dir is not None:
            shutil.rmtree(backup_dir)
    finally:
        if stage_dir.exists():
            shutil.rmtree(stage_dir)

    return manifest
