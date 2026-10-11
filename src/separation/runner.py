from __future__ import annotations

import shutil
from pathlib import Path

from .ffmpeg import concat_wavs, split_audio_to_chunks
from .model import separate_chunks
from .worksapce import prepare_separation_dirs, validate_separation_inputs


def separate_audio(
    input_file: Path,
    vocals_output: Path,
    instrumental_output: Path,
    *,
    model_dir: Path,
    work_dir: Path,
    model: str,
    preset: str | None = None,
    chunk_seconds: int = 180,
    sample_rate: int = 44100,
    use_autocast: bool = False,
    keep_work_dir: bool = False,
    overwrite: bool = False
) -> tuple[Path, Path]:
    validate_separation_inputs(
        input_file=input_file,
        vocals_output=vocals_output,
        instrumental_output=instrumental_output,
        chunk_seconds=chunk_seconds,
        overwrite=overwrite
    )

    chunks_dir, separated_chunks_dir = prepare_separation_dirs(
        model_dir=model_dir,
        vocals_output=vocals_output,
        instrumental_output=instrumental_output,
        work_dir=work_dir
    )

    completed = False
    try:
        chunks = split_audio_to_chunks(
            input_file, chunks_dir, chunk_seconds=chunk_seconds, sample_rate=sample_rate
        )
        vocals_chunks, instrumental_chunks = separate_chunks(
            chunks,
            model_dir=model_dir,
            output_dir=separated_chunks_dir,
            model=model,
            preset=preset,
            sample_rate=sample_rate,
            use_autocast=use_autocast
        )
        concat_wavs(vocals_chunks, vocals_output, work_dir / "vocals_concat.txt")
        concat_wavs(instrumental_chunks, instrumental_output, work_dir / "instrumental_concat.txt")
        completed = True
    finally:
        if completed and not keep_work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)

            for parent in (work_dir.parent, work_dir.parent.parent):
                try:
                    parent.rmdir()
                except OSError:
                    break

    return vocals_output.resolve(), instrumental_output.resolve()