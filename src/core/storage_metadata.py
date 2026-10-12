from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .storage_layout import (
    StorageLayout,
    ensure_relative_path,
    validate_source_id,
    validate_speaker_id,
)


STAGE_PENDING = "pending"
STAGE_COMPLETED = "completed"

SPEAKER_REGISTRY_FIELDS = (
    "schema_version",
    "speaker_id",
    "speaker_name",
    "gender",
    "language",
    "speaker_directory",
    "status",
    "created_at",
    "updated_at",
)

SOURCE_REGISTRY_FIELDS = (
    "schema_version",
    "source_id",
    "speaker_id",
    "original_filename",
    "source_type",
    "source_url",
    "raw_status",
    "raw_path",
    "conversion_status",
    "wav_path",
    "separation_status",
    "vocals_path",
    "instrumental_path",
    "diarization_status",
    "diarization_path",
    "diarization_segment_count",
    "manual_review_status",
    "manual_review_remaining_segment_count",
    "created_at",
    "updated_at",
)

GLOBAL_CHUNK_REGISTRY_FIELDS = (
    "chunk_id",
    "speaker_id",
    "source_id",
    "chunk_path",
    "source_segment_path",
    "duration_sec",
    "sample_rate",
    "quality_status",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.building")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    return path


def _atomic_write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: Iterable[Mapping[str, Any]],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.building")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    temporary.replace(path)
    return path


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"metadata root must be an object: {path}")
    return data


def _stage(status: str = STAGE_PENDING, **values: Any) -> dict[str, Any]:
    stage = {"status": status, "completed_at": None}
    stage.update(values)
    return stage


def _pending_source_stages() -> dict[str, dict[str, Any]]:
    return {
        "raw": _stage(path=None),
        "conversion": _stage(path=None),
        "separation": _stage(vocals_path=None, instrumental_path=None),
        "diarization": _stage(path=None, segment_count=None),
        "manual_review": _stage(remaining_segment_count=None, fingerprint=None),
    }


def stage_status(source: Mapping[str, Any], stage_name: str) -> str:
    stage = source.get(stage_name, {})
    if not isinstance(stage, Mapping):
        return STAGE_PENDING
    return str(stage.get("status") or STAGE_PENDING)


def stage_path(source: Mapping[str, Any], stage_name: str, key: str = "path") -> str:
    stage = source.get(stage_name, {})
    if not isinstance(stage, Mapping):
        return ""
    return str(stage.get(key) or "")


def load_speaker_metadata(layout: StorageLayout, speaker_id: str) -> dict[str, Any]:
    validate_speaker_id(speaker_id)
    path = layout.speaker_metadata_path(speaker_id)
    if path.is_file():
        metadata = read_json(path)
        if metadata.get("speaker_id") != speaker_id:
            raise ValueError(
                f"metadata speaker_id does not match directory: {path}"
            )
        _validate_metadata_paths(metadata)
        return metadata

    now = utc_now()
    return {
        "schema_version": layout.schema_version,
        "speaker_id": speaker_id,
        "speaker_name": "",
        "gender": "",
        "language": "fa",
        "status": "active",
        "sources": [],
        "created_at": now,
        "updated_at": now,
    }


def write_speaker_metadata(
    layout: StorageLayout,
    speaker_id: str,
    metadata: Mapping[str, Any],
) -> Path:
    validate_speaker_id(speaker_id)
    document = dict(metadata)
    document["schema_version"] = str(document.get("schema_version") or layout.schema_version)
    document["speaker_id"] = speaker_id
    document["updated_at"] = utc_now()
    document.setdefault("created_at", document["updated_at"])
    document.setdefault("language", "fa")
    document.setdefault("status", "active")
    document.setdefault("sources", [])
    _validate_metadata_paths(document)
    return _atomic_write_text(
        layout.speaker_metadata_path(speaker_id),
        json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def upsert_source_metadata(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    *,
    original_filename: str,
    source_type: str,
    raw_path: Path,
    source_url: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    validate_source_id(source_id)
    if not raw_path.is_file():
        raise ValueError(f"raw source does not exist: {raw_path}")

    metadata = load_speaker_metadata(layout, speaker_id)
    now = utc_now()
    sources = list(metadata.get("sources") or [])
    matches = [item for item in sources if item.get("source_id") == source_id]
    if len(matches) > 1:
        raise ValueError(f"duplicate source_id in metadata: {source_id}")
    if matches and not overwrite:
        raise ValueError(
            f"source_id already exists for {speaker_id}: {source_id}; pass --overwrite"
        )

    raw_relative = layout.relative_to_speaker(speaker_id, raw_path).as_posix()
    values = {
        "source_id": source_id,
        "original_filename": original_filename,
        "source_type": source_type,
        "source_url": source_url,
        "created_at": matches[0].get("created_at", now) if matches else now,
        "updated_at": now,
        **_pending_source_stages(),
    }
    values["raw"] = {
        "status": STAGE_COMPLETED,
        "path": raw_relative,
        "completed_at": now,
    }

    if matches:
        sources = [
            {**item, **values} if item.get("source_id") == source_id else item
            for item in sources
        ]
    else:
        sources.append(values)

    metadata["sources"] = sorted(sources, key=lambda item: str(item["source_id"]))
    write_speaker_metadata(layout, speaker_id, metadata)
    return metadata


def update_conversion_completed(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    wav_path: Path,
) -> dict[str, Any]:
    if not wav_path.is_file():
        raise ValueError(f"WAV output does not exist: {wav_path}")
    return _update_source_stage(
        layout,
        speaker_id,
        source_id,
        "conversion",
        {"path": layout.relative_to_speaker(speaker_id, wav_path).as_posix()},
    )


def update_separation_completed(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    *,
    vocals_path: Path,
    instrumental_path: Path,
) -> dict[str, Any]:
    for path in (vocals_path, instrumental_path):
        if not path.is_file():
            raise ValueError(f"separation output does not exist: {path}")
    return _update_source_stage(
        layout,
        speaker_id,
        source_id,
        "separation",
        {
            "vocals_path": layout.relative_to_speaker(speaker_id, vocals_path).as_posix(),
            "instrumental_path": layout.relative_to_speaker(
                speaker_id, instrumental_path
            ).as_posix(),
        },
    )


def update_diarization_completed(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    *,
    diarization_dir: Path,
    rttm_path: Path,
    json_path: Path | None,
    segments_dir: Path | None,
) -> dict[str, Any]:
    if not rttm_path.is_file():
        raise ValueError(f"diarization RTTM does not exist: {rttm_path}")
    if json_path is not None and not json_path.is_file():
        raise ValueError(f"diarization JSON does not exist: {json_path}")
    if segments_dir is not None and not segments_dir.is_dir():
        raise ValueError(f"diarization segments directory does not exist: {segments_dir}")
    segment_count = (
        len([path for path in segments_dir.rglob("*.wav") if path.is_file()])
        if segments_dir is not None
        else 0
    )

    metadata = _update_source_stage(
        layout,
        speaker_id,
        source_id,
        "diarization",
        {
            "path": layout.relative_to_speaker(speaker_id, diarization_dir).as_posix(),
            "segment_count": segment_count,
        },
        write=False,
    )
    source = _source_by_id_from_metadata(metadata, source_id)
    source["manual_review"] = _stage(
        STAGE_PENDING,
        remaining_segment_count=None,
        fingerprint=None,
    )
    source["updated_at"] = utc_now()
    write_speaker_metadata(layout, speaker_id, metadata)
    return metadata


def mark_source_reviewed(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    *,
    allow_empty: bool = False,
) -> dict[str, Any]:
    validate_source_id(source_id)
    metadata = load_speaker_metadata(layout, speaker_id)
    source = _source_by_id_from_metadata(metadata, source_id)
    if stage_status(source, "diarization") != STAGE_COMPLETED:
        raise ValueError(f"{speaker_id}/{source_id}: diarization is not completed")

    segments_dir = layout.diarization_segments_dir(speaker_id, source_id)
    count, fingerprint = review_segment_state(layout, speaker_id, source_id)
    if not segments_dir.is_dir():
        raise ValueError(f"segments directory does not exist: {segments_dir}")
    if count == 0 and not allow_empty:
        raise ValueError(f"no reviewed segment WAVs remain for {speaker_id}/{source_id}")

    now = utc_now()
    source["manual_review"] = {
        "status": STAGE_COMPLETED,
        "remaining_segment_count": count,
        "fingerprint": fingerprint,
        "completed_at": now,
    }
    source["updated_at"] = now
    metadata["sources"] = sorted(metadata.get("sources") or [], key=lambda item: str(item["source_id"]))
    write_speaker_metadata(layout, speaker_id, metadata)
    return metadata


def review_segment_state(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
) -> tuple[int, str]:
    segments_dir = layout.diarization_segments_dir(speaker_id, source_id)
    files = sorted(path for path in segments_dir.rglob("*.wav") if path.is_file())
    digest = hashlib.sha256()
    for path in files:
        if path.stat().st_size == 0:
            raise ValueError(f"zero-byte segment file: {path}")
        relative = layout.relative_to_speaker(speaker_id, path).as_posix()
        stat = path.stat()
        digest.update(f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8"))
    return len(files), digest.hexdigest()


def speaker_sources(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    sources = list(metadata.get("sources") or [])
    seen: set[str] = set()
    for source in sources:
        source_id = str(source.get("source_id", ""))
        validate_source_id(source_id)
        if source_id in seen:
            raise ValueError(f"duplicate source_id in metadata: {source_id}")
        seen.add(source_id)
        _validate_source_paths(source)
    return sorted(sources, key=lambda source: str(source["source_id"]))


def source_by_id(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
) -> dict[str, Any]:
    validate_source_id(source_id)
    metadata = load_speaker_metadata(layout, speaker_id)
    return _source_by_id_from_metadata(metadata, source_id)


def write_prepared_summary_json(
    path: Path,
    *,
    schema_version: str,
    speaker_id: str,
    source_count: int,
    reviewed_source_count: int,
    remaining_segment_count: int,
    chunk_count: int,
    total_chunk_duration_sec: float,
    sample_rate: int,
    status: str,
    extra: Mapping[str, Any] | None = None,
) -> Path:
    document = {
        "schema_version": schema_version,
        "speaker_id": speaker_id,
        "source_count": source_count,
        "reviewed_source_count": reviewed_source_count,
        "remaining_segment_count": remaining_segment_count,
        "chunk_count": chunk_count,
        "total_chunk_duration_sec": round(float(total_chunk_duration_sec), 3),
        "sample_rate": sample_rate,
        "status": status,
        "updated_at": utc_now(),
    }
    if extra:
        document.update(dict(extra))
        document["updated_at"] = utc_now()
    return _atomic_write_text(
        path,
        json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def write_global_registries(layout: StorageLayout) -> None:
    speaker_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    chunk_rows: list[dict[str, Any]] = []

    for metadata_path in sorted(layout.speakers_root.glob("speaker_*/metadata.json")):
        metadata = read_json(metadata_path)
        speaker_id = str(metadata.get("speaker_id", ""))
        validate_speaker_id(speaker_id)
        speaker_root = layout.speaker_root(speaker_id)
        speaker_rows.append(
            {
                "schema_version": metadata.get("schema_version", layout.schema_version),
                "speaker_id": speaker_id,
                "speaker_name": metadata.get("speaker_name", ""),
                "gender": metadata.get("gender", ""),
                "language": metadata.get("language", "fa"),
                "speaker_directory": layout.relative_to_data_root(speaker_root).as_posix(),
                "status": metadata.get("status", "active"),
                "created_at": metadata.get("created_at", ""),
                "updated_at": metadata.get("updated_at", ""),
            }
        )
        for source in speaker_sources(metadata):
            source_rows.append(_source_registry_row(layout, speaker_id, source))

        manifest_path = layout.prepared_manifest_path(speaker_id)
        if manifest_path.is_file():
            with manifest_path.open(newline="", encoding="utf-8") as stream:
                for row in csv.DictReader(stream):
                    chunk_rows.append(
                        {
                            "chunk_id": row.get("chunk_id", ""),
                            "speaker_id": row.get("speaker_id", ""),
                            "source_id": row.get("source_id", ""),
                            "chunk_path": Path(
                                layout.relative_to_data_root(
                                    speaker_root / ensure_relative_path(
                                        row.get("chunk_path", ""),
                                        field_name="chunk_path",
                                    )
                                )
                            ).as_posix(),
                            "source_segment_path": Path(
                                layout.relative_to_data_root(
                                    speaker_root / ensure_relative_path(
                                        row.get("source_segment_path", ""),
                                        field_name="source_segment_path",
                                    )
                                )
                            ).as_posix(),
                            "duration_sec": row.get("duration_sec", ""),
                            "sample_rate": row.get("sample_rate", ""),
                            "quality_status": row.get("quality_status", ""),
                        }
                    )

    _atomic_write_csv(layout.speakers_manifest_path, SPEAKER_REGISTRY_FIELDS, speaker_rows)
    _atomic_write_csv(layout.sources_manifest_path, SOURCE_REGISTRY_FIELDS, source_rows)
    _atomic_write_csv(layout.chunks_manifest_path, GLOBAL_CHUNK_REGISTRY_FIELDS, chunk_rows)


def _update_source_stage(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    stage_name: str,
    values: Mapping[str, Any],
    *,
    write: bool = True,
) -> dict[str, Any]:
    metadata = load_speaker_metadata(layout, speaker_id)
    source = _source_by_id_from_metadata(metadata, source_id)
    now = utc_now()
    stage = dict(source.get(stage_name) or {})
    stage.update(values)
    stage["status"] = STAGE_COMPLETED
    stage["completed_at"] = now
    source[stage_name] = stage
    source["updated_at"] = now
    if write:
        write_speaker_metadata(layout, speaker_id, metadata)
    return metadata


def _source_by_id_from_metadata(
    metadata: Mapping[str, Any],
    source_id: str,
) -> dict[str, Any]:
    matches = [
        source
        for source in speaker_sources(metadata)
        if source.get("source_id") == source_id
    ]
    if not matches:
        speaker_id = metadata.get("speaker_id", "speaker")
        raise ValueError(f"source_id is not registered for {speaker_id}: {source_id}")
    return matches[0]


def _source_registry_row(
    layout: StorageLayout,
    speaker_id: str,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    speaker_root = layout.speaker_root(speaker_id)
    return {
        "schema_version": layout.schema_version,
        "source_id": source.get("source_id", ""),
        "speaker_id": speaker_id,
        "original_filename": source.get("original_filename", ""),
        "source_type": source.get("source_type", ""),
        "source_url": source.get("source_url", ""),
        "raw_status": stage_status(source, "raw"),
        "raw_path": _data_relative_or_empty(layout, speaker_root, stage_path(source, "raw")),
        "conversion_status": stage_status(source, "conversion"),
        "wav_path": _data_relative_or_empty(
            layout, speaker_root, stage_path(source, "conversion")
        ),
        "separation_status": stage_status(source, "separation"),
        "vocals_path": _data_relative_or_empty(
            layout, speaker_root, stage_path(source, "separation", "vocals_path")
        ),
        "instrumental_path": _data_relative_or_empty(
            layout, speaker_root, stage_path(source, "separation", "instrumental_path")
        ),
        "diarization_status": stage_status(source, "diarization"),
        "diarization_path": _data_relative_or_empty(
            layout, speaker_root, stage_path(source, "diarization")
        ),
        "diarization_segment_count": (
            source.get("diarization", {}).get("segment_count", "")
            if isinstance(source.get("diarization"), Mapping)
            else ""
        ),
        "manual_review_status": stage_status(source, "manual_review"),
        "manual_review_remaining_segment_count": (
            source.get("manual_review", {}).get("remaining_segment_count", "")
            if isinstance(source.get("manual_review"), Mapping)
            else ""
        ),
        "created_at": source.get("created_at", ""),
        "updated_at": source.get("updated_at", ""),
    }


def _data_relative_or_empty(layout: StorageLayout, speaker_root: Path, value: object) -> str:
    if not value:
        return ""
    relative = ensure_relative_path(str(value), field_name="metadata path")
    return layout.relative_to_data_root(speaker_root / relative).as_posix()


def _validate_metadata_paths(metadata: Mapping[str, Any]) -> None:
    for source in metadata.get("sources") or []:
        _validate_source_paths(source)


def _validate_source_paths(source: Mapping[str, Any]) -> None:
    checks = (
        ("raw", "path"),
        ("conversion", "path"),
        ("separation", "vocals_path"),
        ("separation", "instrumental_path"),
        ("diarization", "path"),
    )
    for stage_name, field in checks:
        stage = source.get(stage_name, {})
        if not isinstance(stage, Mapping):
            continue
        value = stage.get(field)
        if value:
            ensure_relative_path(str(value), field_name=f"{stage_name}.{field}")
