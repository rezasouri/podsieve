from __future__ import annotations

import logging
from pathlib import Path

from ..core.errors import StageError


LOGGER = logging.getLogger(__name__)



def create_separator(
    *,
    model_dir: Path,
    output_dir: Path,
    sample_rate: int,
    preset: str | None,
    use_autocast: bool,
):
    try:
        from audio_separator.separator import Separator
    except ImportError as exc:
        raise StageError(
            "separation",
            "audio-separator is not installed; install audio-separator==0.44.2",
        ) from exc
    
    params = {
        "model_file_dir": str(model_dir),
        "output_dir": str(output_dir),
        "output_format": "WAV",
        "sample_rate": sample_rate,
        "normalization_threshold": 0.9,
        "amplification_threshold": 0.0,
        "use_autocast": use_autocast,
    }
   
    if preset:
        params["ensemble_preset"] = preset

    return Separator(**params)


def load_separator_model(
    separator,
    *,
    model: str,
    preset: str | None
):
    if preset:
        LOGGER.info(f"stage=separation loading_preset={preset}")
        separator.load_model()
    else:
        LOGGER.info(f"stage=separation loading_model={model}")
        separator.load_model(model_filename=model)


def find_separated_output(output_dir: Path, stem: str) -> Path:
    desire_path = output_dir / f"{stem}.wav"
    if desire_path.is_file():
        return desire_path
    
    matches = sorted(output_dir.glob(f"*{stem}.wav"))
    if matches:
        return matches[0]
    
    raise StageError(
        "separation",
        f"audio-separator did not create expected output for stem={stem}",
    )


def separate_one_chunk(
    separator,
    chunk: Path,
    output_dir: Path
) -> tuple[Path, Path]:
    out_names = {
        "Vocals": f"{chunk.stem}_vocals",
        "Instrumental": f"{chunk.stem}_instrumental",
    }

    separator.separate(str(chunk), out_names)
    vocals = find_separated_output(output_dir, out_names["Vocals"])
    instrumental = find_separated_output(output_dir, out_names["Instrumental"])

    return vocals, instrumental


def separate_chunks(
    chunks: list[Path],
    *,
    model_dir: Path,
    output_dir: Path,
    model: str,
    preset: str | None,
    sample_rate: int,
    use_autocast: bool,
) -> tuple[list[Path], list[Path]]:
    """Separate all chunks into vocals and instrumental files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    separator = create_separator(
        model_dir=model_dir,
        output_dir=output_dir,
        sample_rate=sample_rate,
        preset=preset,
        use_autocast=use_autocast,
    )

    load_separator_model(separator, model=model, preset=preset)

    vocals_files: list[Path] = []
    instrumental_files: list[Path] = []

    for index, chunk in enumerate(chunks, start=1):
        LOGGER.info(f"stage=separation chunk={index}/{len(chunks)} input={chunk}")

        vocals, instrumental = separate_one_chunk(separator, chunk, output_dir)

        vocals_files.append(vocals)
        instrumental_files.append(instrumental)

    return vocals_files, instrumental_files