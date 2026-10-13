"""Read real desktop artifacts and remove one source without changing CLI commands."""
from __future__ import annotations

from datetime import datetime
import json
import shutil
from pathlib import Path
import uuid

from src.core.storage_layout import StorageLayout, require_contained, validate_source_id
from src.core.storage_metadata import load_speaker_metadata, write_speaker_metadata, write_global_registries
from ui.storage_adapter import read_preferences, output_key, output_directory, check_destination

STAGES = ("raw", "conversion", "separation", "diarization")


def format_date(value):
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(value)


def source_roots(layout, key, source):
    """Only this source's directories; never the whole registered speaker directory."""
    paths = list(layout.raw_dir(key).glob(f"{source}.*"))
    paths += [layout.wav_source_path(key, source), layout.separated_source_dir(key, source),
              layout.diarization_source_dir(key, source), layout.work_dir(key, source)]
    result = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_symlink():
            raise ValueError("Source artifact must not be a symbolic link")
        require_contained(path, layout.speaker_root(key))
        result.append(path)
    return result


def artifact(path, title=None):
    available = path.exists()
    directory = available and path.is_dir()
    files = [p for p in path.rglob("*") if p.is_file()] if directory else [path] if available else []
    size = sum(p.stat().st_size for p in files)
    return dict(name=title or path.name, path=str(path), available=available, directory=directory,
                bytes=size, size=f"{len(files)} items" if directory else f"{size / 1024 / 1024:.1f} MB" if size > 1024 * 1024 else f"{size / 1024:.1f} KB",
                uri=path.as_uri() if available and not directory else "")


def scan_sources(layout: StorageLayout) -> list[dict]:
    prefs = read_preferences(layout)
    aliases = {key: name for name, key in prefs["aliases"].items()}
    rows = []
    for metadata_path in sorted(layout.speakers_root.glob("speaker_*/metadata.json")):
        key = metadata_path.parent.name
        meta = load_speaker_metadata(layout, key)
        name = aliases.get(key, key)
        for src in meta.get("sources", []):
            source = validate_source_id(src["source_id"])
            parent = prefs["outputs"].get(output_key(name, source), "")
            final = Path(parent).expanduser().resolve() / name if parent else layout.diarization_segments_dir(key, source)
            raw_path = src.get("raw", {}).get("path")
            raw = require_contained(layout.speaker_root(key) / raw_path, layout.speaker_root(key)) if raw_path else layout.raw_source_path(key, source, Path(src.get("original_filename", ".wav")).suffix or ".wav")
            final_artifact = artifact(final, "Final segments")
            if parent and (final / ".podsieve-export.json").is_file():
                export_owner = json.loads((final / ".podsieve-export.json").read_text(encoding="utf-8"))
                own_files = [require_contained(final / relative, final) for relative in export_owner.get("sources", {}).get(source, [])]
                own_files = [p for p in own_files if p.is_file()]
                final_artifact.update(available=source in export_owner.get("sources", {}), size=f"{len(own_files)} items", bytes=sum(p.stat().st_size for p in own_files))
            elif parent:
                final_artifact["available"] = False
            annotation = layout.diarization_annotation_dir(key, source)
            manifests = final / ".podsieve" / source if parent else final.parent
            groups = [
                dict(name="Raw Audio", files=[artifact(raw)]),
                dict(name="Converted WAV", files=[artifact(layout.wav_source_path(key, source))]),
                dict(name="Separated Audio", files=[artifact(layout.vocals_path(key, source)), artifact(layout.instrumental_path(key, source))]),
                dict(name="Diarization", files=[artifact(annotation / "diarization.json"), artifact(annotation / "diarization.rttm"), final_artifact]),
                dict(name="Manifest Files", files=[artifact(metadata_path), artifact(manifests / "manifest.csv"), artifact(manifests / "manifest.json")]),
                dict(name="Quality Diagnostics", files=[artifact(layout.diarization_quality_dir(key, source) / "quality_summary.json"), artifact(layout.diarization_evidence_dir(key, source), "Model evidence")]),
            ]
            files = {p.resolve(): p for root in source_roots(layout, key, source)
                     for p in (root.rglob("*") if root.is_dir() else [root]) if p.is_file()}
            if parent and (final / ".podsieve-export.json").is_file():
                owner = json.loads((final / ".podsieve-export.json").read_text(encoding="utf-8"))
                for relative in owner.get("sources", {}).get(source, []):
                    p = require_contained(final / relative, final)
                    if p.is_file():
                        files[p.resolve()] = p
                if manifests.is_dir():
                    for p in manifests.rglob("*"):
                        if p.is_file():
                            files[p.resolve()] = p
            size = sum(p.stat().st_size for p in files.values())
            states = ["completed" if src.get(stage, {}).get("status") == "completed" else "not-started" for stage in STAGES]
            kind = {"local": "Local File", "youtube": "YouTube", "castbox": "Castbox"}.get(src.get("source_type"), src.get("source_type", "Local File"))
            preview = next((p for p in [layout.vocals_path(key, source), layout.wav_source_path(key, source), raw] if p.is_file()), None)
            rows.append(dict(key=f"{key}/{source}", internalSpeaker=key, id=source, speaker=name,
                             speakerName=meta.get("speaker_name") or name, name=src.get("original_filename") or source,
                             input=kind, sourceRef=src.get("source_url") or str(raw), language=meta.get("language", "fa"),
                             created=format_date(src.get("created_at")), updated=format_date(src.get("updated_at")),
                             bytes=size, size=f"{size / 1024 / 1024:.1f} MB", artifacts=len(files),
                             status="completed" if all(s == "completed" for s in states) else "pending", stages=states,
                             stageTimes=[format_date(src.get(stage, {}).get("completed_at")) for stage in STAGES],
                             stage=(["Ingest", "Convert", "Separate", "Diarize"][max(i for i, s in enumerate(states) if s == "completed")] if "completed" in states else "Pending"),
                             outputPath=str(final), outputAvailable=final_artifact["available"], fileGroups=groups,
                             previewUri=preview.as_uri() if preview else "", previewName=preview.name if preview else "",
                             reviewStatus=src.get("manual_review", {}).get("status", "pending"), failure=""))
    return rows


def remove_source(layout: StorageLayout, key: str, name: str, source: str) -> Path:
    """Move only owned artifacts to local trash, with rollback if registry updates fail."""
    validate_source_id(source)
    meta = load_speaker_metadata(layout, key)
    if not any(row["source_id"] == source for row in meta.get("sources", [])):
        raise ValueError("Source is no longer registered")
    prefs = read_preferences(layout)
    paths = source_roots(layout, key, source)
    parent = prefs["outputs"].get(output_key(name, source), "")
    owner = None
    target = None
    if parent:
        target = output_directory(parent, name)
        if target.exists() and (target / ".podsieve-export.json").is_file():
            owner = check_destination(target, name, source, True)
            for relative in owner["sources"].get(source, []):
                p = require_contained(target / relative, target)
                if p.is_file():
                    paths.append(p)
            manifests = target / ".podsieve" / source
            if manifests.exists():
                paths.append(manifests)
    trash = layout.data_root / ".podsieve-trash" / uuid.uuid4().hex
    trash.mkdir(parents=True)
    moved = []
    old_owner = (target / ".podsieve-export.json").read_bytes() if owner is not None else None
    try:
        for i, path in enumerate(paths):
            destination = trash / str(i)
            # shutil.move handles output folders on a different filesystem.
            shutil.move(str(path), str(destination))
            moved.append((path, destination))
        new_meta = dict(meta, sources=[row for row in meta["sources"] if row["source_id"] != source])
        write_speaker_metadata(layout, key, new_meta)
        if owner is not None:
            owner["sources"].pop(source, None)
            (target / ".podsieve-export.json").write_text(json.dumps(owner, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_global_registries(layout)
        (trash / "restore.json").write_text(json.dumps({"speaker": key, "source": source,
            "metadata": meta, "output_owner": old_owner.decode("utf-8") if old_owner else None,
            "paths": [{"original": str(p), "trash": str(t)} for p, t in moved]}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        for original, archived in reversed(moved):
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(archived), str(original))
        write_speaker_metadata(layout, key, meta)
        if old_owner is not None:
            (target / ".podsieve-export.json").write_bytes(old_owner)
        write_global_registries(layout)
        raise
    return trash
