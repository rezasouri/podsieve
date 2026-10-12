from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Sequence

from .schemas import Candidate


def _write_json(path: Path, document: Any) -> None:
    temporary = path.with_name(f".{path.name}.building")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def export_review_clips(
    audio_path: Path, output_dir: Path, candidates: Sequence[Candidate], padding: float,
    *, relative_dir: str = "review_clips",
) -> None:
    import soundfile as sf

    output_dir.mkdir(parents=True, exist_ok=True)
    with sf.SoundFile(str(audio_path)) as source:
        for candidate in candidates:
            start = max(0, math.floor((candidate.start - padding) * source.samplerate))
            end = min(len(source), math.ceil((candidate.end + padding) * source.samplerate))
            if end <= start:
                continue
            output = output_dir / f"review_{candidate.rank:04d}_{start:012d}_{end:012d}.wav"
            source.seek(start)
            samples = source.read(end - start, dtype="float32", always_2d=True)
            sf.write(str(output), samples, source.samplerate, subtype="PCM_16")
            candidate.review_clip = f"{relative_dir}/{output.name}"


def merge_review_candidates(candidates: Sequence[Candidate], max_gap: float = .3) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item in sorted(candidates, key=lambda row: (row.start, row.end, row.rank)):
        if groups and item.start - groups[-1]["end"] <= max_gap:
            groups[-1]["end"] = max(groups[-1]["end"], item.end)
            groups[-1]["candidate_ranks"].append(item.rank)
        else:
            groups.append({"start": item.start, "end": item.end, "candidate_ranks": [item.rank]})
    return groups


def export_group_clips(
    audio_path: Path, output_dir: Path, groups: list[dict[str, Any]], padding: float,
    *, relative_dir: str = "review_groups",
) -> None:
    import soundfile as sf

    output_dir.mkdir(parents=True, exist_ok=True)
    with sf.SoundFile(str(audio_path)) as source:
        for index, group in enumerate(groups, 1):
            start = max(0, math.floor((group["start"] - padding) * source.samplerate))
            end = min(len(source), math.ceil((group["end"] + padding) * source.samplerate))
            source.seek(start)
            samples = source.read(max(0, end - start), dtype="float32", always_2d=True)
            name = f"group_{index:04d}.wav"
            sf.write(str(output_dir / name), samples, source.samplerate, subtype="PCM_16")
            group["review_clip"] = f"{relative_dir}/{name}"


def write_results(output_dir: Path, candidates: Sequence[Candidate], summary: dict[str, Any], overwrite: bool,
                  groups: list[dict[str, Any]] | None = None) -> None:
    names = ("suspicious_segments.json", "suspicious_segments.csv", "quality_summary.json")
    existing = [output_dir / name for name in names if (output_dir / name).exists()]
    if existing and not overwrite:
        raise FileExistsError(f"quality output already exists: {existing[0]}; pass --overwrite")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / names[0], [item.as_dict() for item in candidates])
    _write_json(output_dir / "review_groups.json", groups or [])
    temporary = output_dir / f".{names[1]}.building"
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "rank", "source_id", "start", "end", "assigned_speaker", "candidate_speaker", "issue_types",
            "review_score", "ranking_group", "feature_scores", "features", "evidence_available", "evidence_provenance", "warnings", "review_clip",
        ))
        writer.writeheader()
        for item in candidates:
            row = item.as_dict()
            for key in ("issue_types", "feature_scores", "features", "evidence_available", "evidence_provenance", "warnings"):
                row[key] = json.dumps(row[key], ensure_ascii=False, sort_keys=True)
            writer.writerow(row)
    temporary.replace(output_dir / names[1])
    _write_json(output_dir / names[2], summary)
