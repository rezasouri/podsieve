from __future__ import annotations

import logging
from pathlib import Path

from ..core.commands import require_executable, run_command
from ..core.errors import StageError


LOGGER = logging.getLogger(__name__)


def split_audio_to_chunks(
    input_file: Path,
    chunks_dir: Path,
    *,
    chunk_seconds: int,
    sample_rate: int
) -> list[Path]:
    ffmpeg = require_executable("ffmpeg", "separation")

    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_pattern = chunks_dir / "chunk_%05d.wav"

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_file),
        "-map",
        "0:a:0",
        "-ac",
        "2",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        str(chunk_pattern),
    ]

    run_command(command, stage="separation")

    chunks = sorted(chunks_dir.glob("chunk_*.wav"))
    if not chunks:
        raise StageError("separation", f"ffmpeg created no chunks from {input_file}")
    
    LOGGER.info(f"stage=separation chunks={len(chunks)}")
    return chunks



def write_ffmpeg_concat_list(files: list[Path], list_file: Path) -> None:
    """Write a concat list file for ffmpeg."""
    lines = []

    for file in files:
        escaped_path = str(file.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped_path}'")

    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")



def concat_wavs(files: list[Path], output_file: Path, list_file: Path) -> None:
    """Concatenate WAV files into one output WAV."""
    if not files:
        raise StageError("separation", f"no chunks available for {output_file.name}")

    ffmpeg = require_executable("ffmpeg", "separation")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    write_ffmpeg_concat_list(files, list_file)

    temporary_output = output_file.with_name(f".{output_file.stem}.building.wav")

    if temporary_output.exists():
        temporary_output.unlink()

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c:a",
        "pcm_s16le",
        str(temporary_output),
    ]

    run_command(command, stage="separation")

    if not temporary_output.is_file():
        raise StageError("separation", f"ffmpeg did not create {temporary_output}")

    temporary_output.replace(output_file)