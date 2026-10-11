from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .audio import load_audio_for_pyannote
from .pyannote_io import extract_annotation, segments_from_annotation
from .writers import (
    DEFAULT_MIN_SEGMENT_DURATION_SEC,
    DEFAULT_SEGMENT_FADE_SEC,
    DEFAULT_SEGMENT_PADDING_SEC,
    write_json,
    write_rttm,
    write_segment_wavs,
)
from ..core.errors import StageError
from ..core.files import ensure_outputs_available


LOGGER = logging.getLogger(__name__)


def diarize_audio(
    input_file: Path,
    rttm_output: Path,
    json_output: Path,
    segments_dir: Path,
    *,
    source_id: str,
    model: str = "pyannote/speaker-diarization-3.1",
    token_env: str = "HF_TOKEN",
    target_sample_rate: int = 16000,
    device: str | None = None,
    save_json: bool = True,
    save_segments: bool = True,
    segment_padding_sec: float = DEFAULT_SEGMENT_PADDING_SEC,
    segment_fade_sec: float = DEFAULT_SEGMENT_FADE_SEC,
    segment_min_duration_sec: float = DEFAULT_MIN_SEGMENT_DURATION_SEC,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run pyannote diarization and save RTTM, JSON, and speaker-turn WAVs."""
    stage = "diarization"

    if not input_file.is_file():
        raise StageError(stage, f"input vocals audio does not exist: {input_file}")

    expected = [rttm_output]
    if save_json:
        expected.append(json_output)
    ensure_outputs_available(expected, overwrite, stage)

    existing_segments = list(segments_dir.glob("*.wav")) if segments_dir.exists() else []
    if save_segments and existing_segments and not overwrite:
        raise StageError(
            stage,
            f"segment outputs already exist in {segments_dir}. Pass --overwrite to replace them.",
        )
    if save_segments and overwrite:
        for segment in existing_segments:
            segment.unlink()

    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise StageError(stage, f"missing diarization dependency: {exc.name}") from exc

    selected_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    if selected_device == "cuda" and not torch.cuda.is_available():
        raise StageError(stage, "CUDA was requested but torch.cuda.is_available() is false")
    if selected_device not in {"cuda", "cpu"}:
        raise StageError(stage, f"unsupported device: {selected_device}")

    LOGGER.info("stage=%s model=%s device=%s", stage, model, selected_device)

    token = os.environ.get(token_env) or os.environ.get("HUGGINGFACE_TOKEN")
    load_args: dict[str, Any] = {}
    if token:
        load_args["token"] = token

    try:
        pipeline = Pipeline.from_pretrained(model, **load_args)
    except Exception as exc:
        raise StageError(
            stage,
            f"could not load pyannote model '{model}': check your token first",
        ) from exc
    if pipeline is None:
        raise StageError(stage, f"pyannote returned no pipeline for model '{model}'")
    pipeline.to(torch.device(selected_device))

    try:
        audio = load_audio_for_pyannote(input_file, target_sr=target_sample_rate)
    except Exception as exc:
        if isinstance(exc, StageError):
            raise
        raise StageError(stage, f"could not load audio {input_file}: {exc}") from exc

    audio["uri"] = source_id
    duration = audio["waveform"].shape[-1] / audio["sample_rate"]
    LOGGER.info(
        "stage=%s loaded_audio=%s duration=%.2f sample_rate=%s",
        stage,
        input_file,
        duration,
        audio["sample_rate"],
    )

    try:
        result = pipeline(audio)
    except Exception as exc:
        raise StageError(stage, f"pyannote failed for {input_file}: {exc}") from exc
    finally:
        del audio

    annotation = extract_annotation(result)
    annotation.uri = source_id
    segment_data = segments_from_annotation(annotation)

    rttm_output.parent.mkdir(parents=True, exist_ok=True)
    write_rttm(annotation, rttm_output)

    if save_json:
        write_json(
            segment_data,
            json_output,
            source_id=source_id,
            input_file=input_file,
        )

    segment_files: list[Path] = []
    if save_segments:
        segment_files = write_segment_wavs(
            input_file,
            annotation,
            segments_dir,
            padding_sec=segment_padding_sec,
            fade_sec=segment_fade_sec,
            min_duration_sec=segment_min_duration_sec,
        )

    return {
        "rttm": rttm_output.resolve(),
        "json": json_output.resolve() if save_json else None,
        "segments_dir": segments_dir.resolve() if save_segments else None,
        "segment_count": len(segment_files) if save_segments else len(segment_data),
        "speaker_count": len(annotation.labels()),
    }
