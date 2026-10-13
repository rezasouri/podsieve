"""UI-only speaker aliases and external final publication; CLI layout stays intact."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import shutil
import uuid

from src.core.storage_layout import StorageLayout, SPEAKER_ID_PATTERN, validate_source_id


def speaker_name(value: str) -> str:
    value = value.strip()
    if not value or value in {".", ".."} or any(c in '/\\' or ord(c) < 32 for c in value):
        raise ValueError("Speaker ID must be a non-empty folder name without / or \\\\.")
    if len(value.encode("utf-8")) > 240:
        raise ValueError("Speaker ID is too long for a folder name.")
    return value


def read_preferences(layout: StorageLayout) -> dict:
    path = layout.data_root / ".podsieve-ui.json"
    if not path.is_file():
        return {"aliases": {}, "outputs": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("aliases"), dict) or not isinstance(data.get("outputs"), dict):
        raise ValueError("Invalid UI storage preferences")
    return data


def write_preferences(layout: StorageLayout, data: dict) -> None:
    layout.data_root.mkdir(parents=True, exist_ok=True)
    target = layout.data_root / ".podsieve-ui.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def internal_speaker(layout: StorageLayout, name: str, *, create: bool = False) -> str | None:
    name = speaker_name(name)
    if SPEAKER_ID_PATTERN.fullmatch(name):
        return name
    prefs = read_preferences(layout)
    if name in prefs["aliases"]:
        return prefs["aliases"][name]
    if not create:
        return None
    used = set(prefs["aliases"].values())
    while True:
        key = f"speaker_{secrets.randbelow(1_000_000):06d}"
        if key not in used and not layout.speaker_root(key).exists():
            break
    prefs["aliases"][name] = key
    write_preferences(layout, prefs)
    return key


def output_key(name: str, source: str) -> str:
    return json.dumps([speaker_name(name), validate_source_id(source)], ensure_ascii=False)


def output_directory(parent: str, name: str) -> Path:
    root = Path(parent).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Select an existing absolute output directory.")
    target = root.resolve() / speaker_name(name)
    if target.is_symlink():
        raise ValueError("Output speaker folder must not be a symbolic link.")
    if target.exists() and not target.is_dir():
        raise ValueError("Output speaker path is not a directory.")
    return target


def check_destination(target: Path, name: str, source: str, overwrite: bool) -> dict:
    owner = target / ".podsieve-export.json"
    if not target.exists() or not any(target.iterdir()):
        return {"speaker": name, "sources": {}}
    if not owner.is_file() or owner.is_symlink():
        raise FileExistsError("Output folder contains unrelated files; select another directory or speaker name.")
    data = json.loads(owner.read_text(encoding="utf-8"))
    if data.get("speaker") != name or not isinstance(data.get("sources"), dict):
        raise ValueError("Output folder belongs to another speaker.")
    if source in data["sources"] and not overwrite:
        raise FileExistsError("Source output already exists; enable overwrite to replace it.")
    if any(p.is_symlink() for p in target.rglob("*")):
        raise ValueError("Output folder must not contain symbolic links.")
    return data


@dataclass(frozen=True)
class ExportLayout(StorageLayout):
    """Redirect only final segments to a temporary directory on the target disk."""
    export_stage: Path = Path()

    def diarization_segments_dir(self, speaker_id: str, source_id: str) -> Path:
        return self.export_stage / "segments"


def publish_output(stage: Path, target: Path, name: str, source: str, *, overwrite: bool) -> None:
    """Atomically publish source-prefixed clips, retaining other sources for this speaker."""
    owner = check_destination(target, name, source, overwrite)
    build = target.with_name(f".{target.name}-building-{uuid.uuid4().hex}")
    backup = target.with_name(f".{target.name}-previous-{uuid.uuid4().hex}")
    try:
        if target.exists():
            shutil.copytree(target, build)
        else:
            build.mkdir()
        for relative in owner["sources"].get(source, []):
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Invalid file path in UI export manifest")
            (build / path).unlink(missing_ok=True)
        exported = []
        for clip in sorted((stage / "segments").rglob("*.wav")):
            relative = clip.relative_to(stage / "segments")
            relative = relative.with_name(f"{source}_{relative.name}")
            destination = build / relative
            if destination.exists():
                raise FileExistsError(f"Output file already exists: {relative}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(clip, destination)
            exported.append(relative.as_posix())
        manifests = build / ".podsieve" / source
        manifests.mkdir(parents=True, exist_ok=True)
        if (stage / "manifest.csv").is_file():
            with (stage / "manifest.csv").open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                fields = reader.fieldnames
                rows = list(reader)
            for row in rows:
                path = Path(row["file"])
                if path.parts[0] != "segments" or ".." in path.parts:
                    raise ValueError("Invalid final manifest path")
                path = Path(*path.parts[1:])
                row["file"] = path.with_name(f"{source}_{path.name}").as_posix()
            with (manifests / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        if (stage / "manifest.json").is_file():
            manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
            manifest.update(output=str(target), speaker_id=name)
            (manifests / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        owner["sources"][source] = exported
        (build / ".podsieve-export.json").write_text(json.dumps(owner, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        had_target = target.exists()
        if had_target:
            target.rename(backup)
        try:
            build.rename(target)
        except OSError:
            if had_target:
                backup.rename(target)
            raise
        if had_target:
            shutil.rmtree(backup)
    finally:
        if build.exists():
            shutil.rmtree(build)
