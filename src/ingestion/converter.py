from __future__ import annotations

from pathlib import Path

from ..core.commands import require_executable, run_command
from ..core.errors import StageError
from ..core.files import ensure_outputs_available


def convert_to_wav(
    input_file: Path,
    output_file: Path,
    *,
    sample_rate: int = 44100,
    overwrite: bool = False,
) -> Path:
    """Convert the first audio stream to stereo 16-bit PCM WAV."""
    stage = "convert"
    if not input_file.is_file():
        raise StageError(stage, f"input audio does not exist: {input_file}")

    if input_file.resolve() == output_file.resolve() and input_file.suffix.lower() == ".wav":
        return input_file.resolve()

    ensure_outputs_available([output_file], overwrite, stage)
    executable = require_executable("ffmpeg", stage)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        "-y" if overwrite else "-n",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_file),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "2",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(output_file),
    ]
    run_command(command, stage=stage)
    if not output_file.is_file():
        raise StageError(stage, f"ffmpeg did not create expected output: {output_file}")
    return output_file.resolve()

