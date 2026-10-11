from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .storage_layout import StorageLayout, ensure_relative_path


PREPARED_MANIFEST_FIELDS = (
    "chunk_id",
    "speaker_id",
    "source_id",
    "chunk_path",
    "source_segment_path",
    "crop_start_sec",
    "crop_end_sec",
    "duration_sec",
    "sample_rate",
    "channels",
    "vad_backend",
    "quality_status",
    "mode",
    "silence_mode",
    "source_duration_sec",
    "source_speech_duration_sec",
    "source_chunk_capacity",
    "calculated_source_capacity",
    "effective_source_capacity",
    "capacity_limited_by_max_chunks_per_segment",
    "active_speech_sec",
    "active_speech_ratio",
    "internal_silence_sec",
    "max_internal_silence_sec",
    "rms_dbfs",
    "peak",
    "duplicate_check_status",
    "speaker_duplicate_check_status",
    "start_boundary_status",
    "end_boundary_status",
    "leading_silence_sec",
    "trailing_silence_sec",
    "candidate_attempt",
)

PREPARED_COMPLETED_STATUSES = {"completed", "completed_with_shortfall"}
PREPARED_QUALITY_STATUSES = {"accepted", "rejected"}
PREPARED_DURATION_TOLERANCE_SEC = 0.01


@dataclass(frozen=True)
class PreparedManifestAdmission:
    speaker_id: str
    manifest_path: Path
    summary_path: Path
    rows: tuple[dict[str, str], ...]
    accepted_rows: tuple[dict[str, str], ...]
    rejected_rows: tuple[dict[str, str], ...]
    accepted_duration_sec: float
    rejected_duration_sec: float

    @property
    def accepted_row_count(self) -> int:
        return len(self.accepted_rows)

    @property
    def rejected_row_count(self) -> int:
        return len(self.rejected_rows)


def missing_prepared_manifest_fields(fieldnames: object) -> set[str]:
    return set(PREPARED_MANIFEST_FIELDS) - set(fieldnames or ())


def read_prepared_manifest(path: Path) -> tuple[list[dict[str, str]], tuple[str, ...]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            missing = missing_prepared_manifest_fields(reader.fieldnames)
            if missing:
                raise ValueError(
                    f"{path}: missing fields: " + ", ".join(sorted(missing))
                )
            return [dict(row) for row in reader], tuple(reader.fieldnames or ())
    except (OSError, csv.Error) as exc:
        raise ValueError(f"{path}: could not read prepared manifest: {exc}") from exc


def load_prepared_summary(path: Path, speaker_id: str) -> Mapping[str, object]:
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{speaker_id}: could not read prepared summary: {exc}") from exc
    if not isinstance(summary, Mapping):
        raise ValueError(f"{speaker_id}: prepared summary root must be an object")
    return summary


def validate_prepared_summary_consistency(
    *,
    summary_path: Path,
    summary: Mapping[str, object],
    speaker_id: str,
    accepted_rows: list[Mapping[str, str]],
    rejected_rows: list[Mapping[str, str]],
    expected_sample_rate: int,
) -> None:
    if str(summary.get("speaker_id", "")) != speaker_id:
        raise ValueError(
            f"Prepared summary mismatch for {speaker_id}: "
            f"summary speaker_id={summary.get('speaker_id')!r} summary path={summary_path}"
        )
    status = str(summary.get("status", ""))
    if status not in PREPARED_COMPLETED_STATUSES:
        raise ValueError(
            f"{speaker_id}: prepared summary status {status!r} is not completed "
            f"summary path={summary_path}"
        )
    accepted_count = len(accepted_rows)
    summary_chunk_count = _summary_int(summary, "chunk_count", summary_path)
    if summary_chunk_count != accepted_count:
        raise ValueError(
            f"Prepared summary mismatch for {speaker_id}: "
            f"summary chunk_count={summary_chunk_count} manifest accepted rows={accepted_count} "
            f"summary path={summary_path}"
        )
    summary_accepted = _summary_int(
        summary,
        "accepted_chunks",
        summary_path,
        default=summary_chunk_count,
    )
    if summary_accepted != accepted_count:
        raise ValueError(
            f"Prepared summary mismatch for {speaker_id}: "
            f"summary accepted_chunks={summary_accepted} manifest accepted rows={accepted_count} "
            f"summary path={summary_path}"
        )
    for field_name in ("manifest_rejected_rows", "rejected_manifest_rows"):
        if field_name in summary:
            summary_rejected = _summary_int(summary, field_name, summary_path)
            if summary_rejected != len(rejected_rows):
                raise ValueError(
                    f"Prepared summary mismatch for {speaker_id}: "
                    f"summary {field_name}={summary_rejected} "
                    f"manifest rejected rows={len(rejected_rows)} summary path={summary_path}"
                )
    duration = sum(_row_float(row, "duration_sec") for row in accepted_rows)
    summary_duration = _summary_float(summary, "total_chunk_duration_sec", summary_path)
    if abs(summary_duration - duration) > PREPARED_DURATION_TOLERANCE_SEC:
        raise ValueError(
            f"Prepared summary mismatch for {speaker_id}: "
            f"summary total_chunk_duration_sec={summary_duration:.3f} "
            f"manifest accepted duration={duration:.3f} summary path={summary_path}"
        )
    summary_sample_rate = _summary_int(summary, "sample_rate", summary_path)
    if summary_sample_rate != expected_sample_rate:
        raise ValueError(
            f"Prepared summary mismatch for {speaker_id}: "
            f"summary sample_rate={summary_sample_rate} expected={expected_sample_rate} "
            f"summary path={summary_path}"
        )


def validate_prepared_chunk_inventory(
    *,
    layout: StorageLayout,
    speaker_id: str,
    accepted_rows: list[Mapping[str, str]],
) -> None:
    speaker_root = layout.speaker_root(speaker_id).resolve()
    chunks_dir = layout.chunks_dir(speaker_id).resolve()
    manifest_paths: set[Path] = set()
    for row in accepted_rows:
        value = str(row.get("chunk_path", "")).strip()
        if not value:
            continue
        rel = ensure_relative_path(value, field_name="chunk_path")
        manifest_paths.add((speaker_root / rel).resolve())
    actual_paths = (
        {path.resolve() for path in chunks_dir.glob("*.wav")}
        if chunks_dir.is_dir()
        else set()
    )
    stale = sorted(actual_paths - manifest_paths)
    if stale:
        examples = [
            path.relative_to(speaker_root).as_posix()
            if speaker_root in path.parents
            else path.as_posix()
            for path in stale[:5]
        ]
        raise ValueError(
            f"Stale prepared chunk files found for {speaker_id}: "
            f"directory={chunks_dir} unlisted_count={len(stale)} "
            f"examples={examples}"
        )


def validate_prepared_source_segment_reference(
    *,
    layout: StorageLayout,
    speaker_id: str,
    row: Mapping[str, str],
    prefix: str,
    require_exists: bool = True,
    validate_manifest_crop_bounds: bool = True,
) -> Path:
    speaker_root = layout.speaker_root(speaker_id).resolve()
    source_id = str(row.get("source_id", "")).strip()
    chunk_id = str(row.get("chunk_id", "")).strip()
    value = str(row.get("source_segment_path", "")).strip()
    if not value:
        raise ValueError(f"{prefix}: source_segment_path is required")
    try:
        segment_rel = ensure_relative_path(value, field_name="source_segment_path")
    except ValueError as exc:
        raise ValueError(f"{prefix}: {exc}") from exc
    segment_path = (speaker_root / segment_rel).resolve()
    if speaker_root != segment_path and speaker_root not in segment_path.parents:
        raise ValueError(
            f"{prefix}: source_segment_path escapes speaker directory "
            f"speaker_id={speaker_id} source_id={source_id} chunk_id={chunk_id} "
            f"source_segment_path={segment_rel.as_posix()}"
        )
    if require_exists and not segment_path.is_file():
        raise ValueError(
            "Missing source segment for accepted chunk: "
            f"speaker_id={speaker_id} source_id={source_id} chunk_id={chunk_id} "
            f"source_segment_path={segment_rel.as_posix()} reason=file does not exist"
        )
    if validate_manifest_crop_bounds:
        crop_start = _row_float(row, "crop_start_sec")
        crop_end = _row_float(row, "crop_end_sec")
        source_duration = _row_float(row, "source_duration_sec")
        if crop_start < 0:
            raise ValueError(f"{prefix}: crop_start_sec is negative")
        if crop_end <= crop_start:
            raise ValueError(f"{prefix}: crop_end_sec must be greater than crop_start_sec")
        if crop_end > source_duration + PREPARED_DURATION_TOLERANCE_SEC:
            raise ValueError(
                f"{prefix}: crop_end_sec {crop_end:.3f} exceeds manifest "
                f"source_duration_sec {source_duration:.3f}"
            )
    return segment_path


def admitted_prepared_rows(
    *,
    speaker_id: str,
    manifest_path: Path,
    summary_path: Path,
    rows: list[dict[str, str]],
    summary: Mapping[str, object],
    expected_sample_rate: int,
) -> PreparedManifestAdmission:
    accepted = [
        row for row in rows if str(row.get("quality_status", "")).strip() == "accepted"
    ]
    rejected = [
        row for row in rows if str(row.get("quality_status", "")).strip() != "accepted"
    ]
    validate_prepared_summary_consistency(
        summary_path=summary_path,
        summary=summary,
        speaker_id=speaker_id,
        accepted_rows=accepted,
        rejected_rows=rejected,
        expected_sample_rate=expected_sample_rate,
    )
    return PreparedManifestAdmission(
        speaker_id=speaker_id,
        manifest_path=manifest_path,
        summary_path=summary_path,
        rows=tuple(rows),
        accepted_rows=tuple(accepted),
        rejected_rows=tuple(rejected),
        accepted_duration_sec=sum(_row_float(row, "duration_sec") for row in accepted),
        rejected_duration_sec=sum(_row_float(row, "duration_sec") for row in rejected),
    )


def _summary_int(
    summary: Mapping[str, object],
    field_name: str,
    path: Path,
    *,
    default: int | None = None,
) -> int:
    value = summary.get(field_name, default)
    if value is None:
        raise ValueError(f"{path}: summary field {field_name} is required")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: summary field {field_name} must be an integer") from exc


def _summary_float(summary: Mapping[str, object], field_name: str, path: Path) -> float:
    value = summary.get(field_name)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: summary field {field_name} must be numeric") from exc


def _row_float(row: Mapping[str, str], field_name: str) -> float:
    try:
        return float(str(row.get(field_name, "")).strip())
    except ValueError as exc:
        raise ValueError(f"invalid numeric manifest field {field_name}") from exc
