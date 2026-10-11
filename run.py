from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path
from typing import Any

from src.core.config import load_config, resolve_from_root
from src.core.errors import PipelineError, StageError
from src.core.storage_layout import StorageLayout, validate_source_id, validate_speaker_id
from src.core.storage_metadata import upsert_source_metadata, write_global_registries, write_speaker_metadata
from src.ingestion.downloader import download_url_audio

LOGGER = logging.getLogger(__name__)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the PodSieve audio pipeline.")
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--data-root", type=Path, default=None)
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Ingest a local file or supported URL.")
    ingest.add_argument("--speaker-id", required=True)
    ingest.add_argument("--source-id", required=True)
    input_group = ingest.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input-file", type=Path)
    input_group.add_argument("--url")
    ingest.add_argument("--name", default="")
    ingest.add_argument("--gender", default="")
    ingest.add_argument("--language", default="fa")
    ingest.add_argument("--overwrite", action="store_true")
    return parser

def _prepare_raw_slot(layout: StorageLayout, speaker_id: str, source_id: str, overwrite: bool) -> None:
    raw_dir = layout.raw_dir(speaker_id)
    existing = sorted(raw_dir.glob(f"{source_id}.*")) if raw_dir.exists() else []
    if existing and not overwrite:
        raise StageError("ingest", f"raw source already exists: {existing[0]}; pass --overwrite")
    for path in existing:
        if path.is_file():
            path.unlink()

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parent
    config = load_config(resolve_from_root(root, args.config))
    layout = StorageLayout(resolve_from_root(root, args.data_root or config.get("storage", {}).get("data_root", "data")))
    try:
        validate_speaker_id(args.speaker_id)
        validate_source_id(args.source_id)
        if args.input_file:
            if not args.input_file.is_file():
                raise StageError("ingest", f"input file does not exist: {args.input_file}")
            _prepare_raw_slot(layout, args.speaker_id, args.source_id, args.overwrite)
            output = layout.raw_source_path(args.speaker_id, args.source_id, args.input_file.suffix)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args.input_file, output)
            source_type, source_url, filename = "local", "", args.input_file.name
        else:
            template = layout.raw_dir(args.speaker_id) / f"{args.source_id}.%(ext)s"
            output, source_type = download_url_audio(url=args.url, output_template=template, config=config, overwrite=args.overwrite)
            source_url, filename = args.url, output.name
        metadata = upsert_source_metadata(layout, args.speaker_id, args.source_id, original_filename=filename, source_type=source_type, source_url=source_url, raw_path=output, overwrite=args.overwrite)
        metadata.update({key: value for key, value in {"speaker_name": args.name, "gender": args.gender, "language": args.language}.items() if value})
        write_speaker_metadata(layout, args.speaker_id, metadata)
        write_global_registries(layout)
        print(output)
        return 0
    except (OSError, PipelineError, ValueError) as exc:
        LOGGER.error("ingest failed: %s", exc)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
