from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SPEAKER_ID_PATTERN = re.compile(r"^speaker_\d{3,6}$")
SOURCE_ID_PATTERN = re.compile(r"^source_\d{3,6}$")


def validate_speaker_id(speaker_id: str) -> str:
    if not SPEAKER_ID_PATTERN.fullmatch(speaker_id):
        raise ValueError(
            "speaker_id must match speaker_NNN with 3-6 digits, for example speaker_001"
        )
    return speaker_id


def validate_source_id(source_id: str) -> str:
    if not SOURCE_ID_PATTERN.fullmatch(source_id):
        raise ValueError(
            "source_id must match source_NNN with 3-6 digits, for example source_001"
        )
    return source_id


def normalize_extension(extension: str) -> str:
    suffix = extension.strip().lower()
    if not suffix:
        raise ValueError("source extension cannot be empty")
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    if "/" in suffix or "\\" in suffix or suffix in {".", ".."}:
        raise ValueError(f"invalid source extension: {extension!r}")
    return suffix


def ensure_relative_path(path: str | Path, *, field_name: str = "path") -> Path:
    value = Path(path)
    if value.is_absolute():
        raise ValueError(f"{field_name} must be relative: {path}")
    if any(part == ".." for part in value.parts):
        raise ValueError(f"{field_name} must not contain '..': {path}")
    return value


def require_contained(path: Path, root: Path, *, field_name: str = "path") -> Path:
    resolved_path = path.expanduser().resolve()
    resolved_root = root.expanduser().resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"{field_name} escapes storage root: {path}")
    return resolved_path


@dataclass(frozen=True)
class StorageLayout:
    data_root: Path
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", Path(self.data_root))
    @property
    def speakers_root(self) -> Path:
        return self.data_root / "speakers"

    @property
    def manifests_root(self) -> Path:
        return self.data_root / "manifests"

    @property
    def speakers_manifest_path(self) -> Path:
        return self.manifests_root / "speakers.csv"

    @property
    def sources_manifest_path(self) -> Path:
        return self.manifests_root / "sources.csv"

    @property
    def chunks_manifest_path(self) -> Path:
        return self.manifests_root / "chunks.csv"

    def speaker_root(self, speaker_id: str) -> Path:
        return self.speakers_root / validate_speaker_id(speaker_id)

    def speaker_metadata_path(self, speaker_id: str) -> Path:
        return self.speaker_root(speaker_id) / "metadata.json"

    def raw_dir(self, speaker_id: str) -> Path:
        return self.speaker_root(speaker_id) / "raw"

    def raw_source_path(
        self,
        speaker_id: str,
        source_id: str,
        extension: str,
    ) -> Path:
        return self.raw_dir(speaker_id) / f"{validate_source_id(source_id)}{normalize_extension(extension)}"

    def wav_dir(self, speaker_id: str) -> Path:
        return self.speaker_root(speaker_id) / "wav"

    def wav_source_path(self, speaker_id: str, source_id: str) -> Path:
        return self.wav_dir(speaker_id) / f"{validate_source_id(source_id)}.wav"

    def separated_source_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.speaker_root(speaker_id) / "separated" / validate_source_id(source_id)

    def vocals_path(self, speaker_id: str, source_id: str) -> Path:
        return self.separated_source_dir(speaker_id, source_id) / "vocals.wav"

    def instrumental_path(self, speaker_id: str, source_id: str) -> Path:
        return self.separated_source_dir(speaker_id, source_id) / "instrumental.wav"

    def diarization_source_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.speaker_root(speaker_id) / "diarization" / validate_source_id(source_id)

    def diarization_root(self, speaker_id: str) -> Path:
        return self.speaker_root(speaker_id) / "diarization"

    def diarization_json_path(self, speaker_id: str, source_id: str) -> Path:
        return self.diarization_annotation_dir(speaker_id, source_id) / "diarization.json"

    def diarization_rttm_path(self, speaker_id: str, source_id: str) -> Path:
        return self.diarization_annotation_dir(speaker_id, source_id) / "diarization.rttm"

    def diarization_annotation_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.diarization_source_dir(speaker_id, source_id) / "annotation"

    def diarization_final_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.diarization_source_dir(speaker_id, source_id) / "final"

    def diarization_segments_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.diarization_final_dir(speaker_id, source_id) / "segments"

    def diarization_clean_segments_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.diarization_segments_dir(speaker_id, source_id)

    def diarization_evidence_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.diarization_source_dir(speaker_id, source_id) / "diagnostics" / "evidence"

    def diarization_quality_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.diarization_source_dir(speaker_id, source_id) / "diagnostics" / "quality"

    def prepared_dir(self, speaker_id: str) -> Path:
        return self.speaker_root(speaker_id) / "prepared"

    def chunks_dir(self, speaker_id: str) -> Path:
        return self.prepared_dir(speaker_id) / "chunks"

    def chunk_id(self, speaker_id: str, chunk_index: int) -> str:
        if chunk_index < 1:
            raise ValueError("chunk_index must start at 1")
        return f"{validate_speaker_id(speaker_id)}_chunk_{chunk_index:06d}"

    def chunk_path(self, speaker_id: str, chunk_index: int) -> Path:
        return self.chunks_dir(speaker_id) / f"{self.chunk_id(speaker_id, chunk_index)}.wav"

    def prepared_manifest_path(self, speaker_id: str) -> Path:
        return self.prepared_dir(speaker_id) / "manifest.csv"

    def prepared_summary_path(self, speaker_id: str) -> Path:
        return self.prepared_dir(speaker_id) / "summary.json"

    def work_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.speaker_root(speaker_id) / "work" / validate_source_id(source_id)

    def relative_to_speaker(self, speaker_id: str, path: Path) -> Path:
        root = self.speaker_root(speaker_id).resolve()
        resolved = path.resolve()
        require_contained(resolved, root, field_name="path")
        return resolved.relative_to(root)

    def relative_to_data_root(self, path: Path) -> Path:
        root = self.data_root.resolve()
        resolved = path.resolve()
        require_contained(resolved, root, field_name="path")
        return resolved.relative_to(root)
