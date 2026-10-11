from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path
from typing import Any

from src.core.config import config_value, load_config, resolve_from_root
from src.core.errors import PipelineError, StageError
from src.core.logging_config import configure_logging
from src.core.storage_layout import StorageLayout, validate_source_id, validate_speaker_id
from src.core.storage_metadata import (
    source_by_id,
    stage_path,
    update_conversion_completed,
    update_diarization_completed,
    update_separation_completed,
    upsert_source_metadata,
    write_global_registries,
    write_speaker_metadata,
)
from src.diarization import diarize_audio
from src.ingestion.converter import convert_to_wav
from src.ingestion.downloader import download_url_audio
from src.separation.runner import separate_audio


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the speaker/source dataset pipeline.")
    parser.add_argument(
        "--config",
        dest="base_config",
        metavar="CONFIG",
        type=Path,
        default=Path("configs/default.yaml"),
        help="YAML configuration path.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Override storage.data_root.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_identity(command: argparse.ArgumentParser, *, source: bool = True) -> None:
        command.add_argument("--speaker-id", required=True)
        if source:
            command.add_argument("--source-id", required=True)

    ingest = subparsers.add_parser(
        "ingest", help="Ingest a local file, YouTube URL, or Castbox URL."
    )
    add_identity(ingest)
    ingest_input = ingest.add_mutually_exclusive_group(required=True)
    ingest_input.add_argument("--input-file", type=Path)
    ingest_input.add_argument("--url")
    ingest.add_argument("--name", default="", help="Human-readable speaker name.")
    ingest.add_argument("--gender", default="")
    ingest.add_argument("--language", default="fa")
    ingest.add_argument("--overwrite", action="store_true")

    convert = subparsers.add_parser("convert", help="Convert one source to WAV.")
    add_identity(convert)
    convert.add_argument("--overwrite", action="store_true")

    separate = subparsers.add_parser("separate", help="Separate one source.")
    add_identity(separate)
    separate.add_argument("--overwrite", action="store_true")
    separate.add_argument("--keep-work-dir", action="store_true")

    diarize = subparsers.add_parser("diarize", help="Diarize one source.")
    add_identity(diarize)
    diarize.add_argument("--overwrite", action="store_true")

    return parser


def storage_layout_from_config(
    root: Path,
    config: dict[str, Any],
    *,
    data_root_override: Path | None = None,
) -> StorageLayout:
    storage = config.get("storage", {})
    if not isinstance(storage, dict):
        raise PipelineError("Configuration section 'storage' must be a mapping")
    data_root = data_root_override or storage.get("data_root", "data")
    return StorageLayout(
        data_root=resolve_from_root(root, data_root),
        schema_version=str(storage.get("schema_version", "1.0")),
    )


def run_ingest(
    *,
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    input_file: Path | None = None,
    url: str | None = None,
    config: dict[str, Any] | None = None,
    name: str,
    gender: str,
    language: str,
    overwrite: bool,
) -> Path:
    validate_speaker_id(speaker_id)
    validate_source_id(source_id)
    if (input_file is None) == (url is None):
        raise StageError("ingest", "pass exactly one of --input-file or --url")

    if input_file is not None:
        if not input_file.is_file():
            raise StageError("ingest", f"input file does not exist: {input_file}")
        _prepare_raw_slot(layout, speaker_id, source_id, overwrite=overwrite)
        raw_output = layout.raw_source_path(speaker_id, source_id, input_file.suffix)
        raw_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_file, raw_output)
        source_type = "local"
        source_url = ""
        original_filename = input_file.name
    else:
        output_template = layout.raw_dir(speaker_id) / f"{source_id}.%(ext)s"
        raw_output, source_type = download_url_audio(
            url=str(url),
            output_template=output_template,
            config=config or {},
            overwrite=overwrite,
        )
        source_url = str(url)
        original_filename = raw_output.name

    metadata = upsert_source_metadata(
        layout,
        speaker_id,
        source_id,
        original_filename=original_filename,
        source_type=source_type,
        source_url=source_url,
        raw_path=raw_output,
        overwrite=overwrite,
    )
    if name:
        metadata["speaker_name"] = name
    if gender:
        metadata["gender"] = gender
    if language:
        metadata["language"] = language
    write_speaker_metadata(layout, speaker_id, metadata)
    write_global_registries(layout)
    return raw_output


def run_convert(
    *,
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    config: dict[str, Any],
    overwrite: bool,
) -> Path:
    source = source_by_id(layout, speaker_id, source_id)
    raw_relative = stage_path(source, "raw")
    if not raw_relative:
        raise StageError("convert", f"raw stage is not completed for {speaker_id}/{source_id}")
    raw_path = layout.speaker_root(speaker_id) / raw_relative
    output = layout.wav_source_path(speaker_id, source_id)
    sample_rate = int(config_value(config, "audio", "sample_rate", 44100))
    result = convert_to_wav(raw_path, output, sample_rate=sample_rate, overwrite=overwrite)
    update_conversion_completed(layout, speaker_id, source_id, result)
    write_global_registries(layout)
    return result


def run_separation(
    *,
    root: Path,
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    config: dict[str, Any],
    overwrite: bool,
    keep_work_dir: bool,
) -> tuple[Path, Path]:
    checkpoints_dir = resolve_from_root(
        root,
        config_value(config, "separation", "checkpoints_dir", "checkpoints"),
    )
    work_dir = layout.work_dir(speaker_id, source_id) / "separation"
    vocals, instrumental = separate_audio(
        input_file=layout.wav_source_path(speaker_id, source_id),
        vocals_output=layout.vocals_path(speaker_id, source_id),
        instrumental_output=layout.instrumental_path(speaker_id, source_id),
        model_dir=checkpoints_dir,
        work_dir=work_dir,
        model=str(
            config_value(
                config,
                "separation",
                "model",
                "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
            )
        ),
        preset=config_value(config, "separation", "preset"),
        chunk_seconds=int(config_value(config, "audio", "chunk_seconds", 180)),
        sample_rate=int(config_value(config, "audio", "sample_rate", 44100)),
        use_autocast=bool(config_value(config, "separation", "use_autocast", False)),
        keep_work_dir=keep_work_dir,
        overwrite=overwrite,
    )
    update_separation_completed(
        layout,
        speaker_id,
        source_id,
        vocals_path=vocals,
        instrumental_path=instrumental,
    )
    write_global_registries(layout)
    return vocals, instrumental


def run_diarization(
    *,
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    config: dict[str, Any],
    overwrite: bool,
) -> dict[str, Any]:
    input_file = layout.vocals_path(speaker_id, source_id)
    result = diarize_audio(
        input_file=input_file,
        rttm_output=layout.diarization_rttm_path(speaker_id, source_id),
        json_output=layout.diarization_json_path(speaker_id, source_id),
        segments_dir=layout.diarization_segments_dir(speaker_id, source_id),
        source_id=source_id,
        model=str(
            config_value(
                config,
                "diarization",
                "model",
                "pyannote/speaker-diarization-3.1",
            )
        ),
        token_env=str(config_value(config, "diarization", "token_env", "HF_TOKEN")),
        target_sample_rate=int(
            config_value(config, "audio", "diarization_sample_rate", 16000)
        ),
        device=config_value(config, "diarization", "device"),
        save_json=bool(config_value(config, "diarization", "save_json", True)),
        save_segments=bool(config_value(config, "diarization", "save_segments", True)),
        segment_padding_sec=float(
            config_value(config, "diarization", "segment_padding_sec", 0.25)
        ),
        segment_fade_sec=float(
            config_value(config, "diarization", "segment_fade_sec", 0.005)
        ),
        segment_min_duration_sec=float(
            config_value(config, "diarization", "segment_min_duration_sec", 0.05)
        ),
        cache_dir=resolve_from_root(
            root,
            config_value(config, "diarization", "cache_dir", "checkpoints/huggingface"),
        ),
        overwrite=overwrite,
    )
    update_diarization_completed(
        layout,
        speaker_id,
        source_id,
        diarization_dir=layout.diarization_source_dir(speaker_id, source_id),
        rttm_path=layout.diarization_rttm_path(speaker_id, source_id),
        json_path=result["json"],
        segments_dir=result["segments_dir"],
    )
    write_global_registries(layout)
    return result


def _prepare_raw_slot(
    layout: StorageLayout,
    speaker_id: str,
    source_id: str,
    *,
    overwrite: bool,
) -> None:
    raw_dir = layout.raw_dir(speaker_id)
    existing = sorted(raw_dir.glob(f"{source_id}.*")) if raw_dir.exists() else []
    if existing and not overwrite:
        joined = ", ".join(str(path) for path in existing)
        raise StageError(
            "ingest",
            f"raw source already exists: {joined}. Pass --overwrite to replace it.",
        )
    if overwrite:
        for path in existing:
            if path.is_file():
                path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    config = load_config(resolve_from_root(root, args.base_config))
    layout = storage_layout_from_config(root, config, data_root_override=args.data_root)

    try:
        speaker_id = getattr(args, "speaker_id", None)
        source_id = getattr(args, "source_id", None)
        if speaker_id:
            validate_speaker_id(speaker_id)
        if source_id:
            validate_source_id(source_id)

        if args.command == "ingest":
            output = run_ingest(
                layout=layout,
                speaker_id=args.speaker_id,
                source_id=args.source_id,
                input_file=args.input_file,
                url=args.url,
                config=config,
                name=args.name,
                gender=args.gender,
                language=args.language,
                overwrite=args.overwrite,
            )
        elif args.command == "convert":
            output = run_convert(
                layout=layout,
                speaker_id=args.speaker_id,
                source_id=args.source_id,
                config=config,
                overwrite=args.overwrite,
            )
        elif args.command == "separate":
            output, _ = run_separation(
                root=root,
                layout=layout,
                speaker_id=args.speaker_id,
                source_id=args.source_id,
                config=config,
                overwrite=args.overwrite,
                keep_work_dir=args.keep_work_dir,
            )
        elif args.command == "diarize":
            result = run_diarization(
                layout=layout,
                speaker_id=args.speaker_id,
                source_id=args.source_id,
                config=config,
                overwrite=args.overwrite,
            )
            output = result["rttm"]
        else:
            raise PipelineError(f"unsupported command: {args.command}")
    except (OSError, PipelineError, StageError, ValueError) as exc:
        LOGGER.error("pipeline status=failed error=%s", exc)
        return 1

    LOGGER.info("pipeline status=completed output=%s", output)
    LOGGER.info(f"Output: {output}")
    return 0


if __name__ == "__main__":
    configure_logging(log_filename="application.log")
    raise SystemExit(main())
