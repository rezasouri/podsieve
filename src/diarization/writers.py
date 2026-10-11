from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

from ..core.errors import StageError


LOGGER = logging.getLogger(__name__)


_UNSAFE_LABEL = re.compile(r"[^A-Za-z0-9._-]+")
DEFAULT_SEGMENT_PADDING_SEC = 0.25
DEFAULT_SEGMENT_FADE_SEC = 0.005
DEFAULT_MIN_SEGMENT_DURATION_SEC = 0.05


def write_rttm(annotation: Any, output_file: Path) -> None:
    with output_file.open("w", encoding="utf-8") as stream:
        annotation.write_rttm(stream)


def write_json(
    segments: list[dict[str, Any]],
    output_file: Path,
    *,
    source_id: str,
    input_file: Path,
) -> None:
    speakers = sorted({segment["speaker"] for segment in segments})

    document = {
        "source_id": source_id,
        "audio": str(input_file),
        "speaker_count": len(speakers),
        "speakers": speakers,
        "segment_count": len(segments),
        "segments": segments
    }

    output_file.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _apply_edge_fades(samples: np.ndarray, sample_rate: int, fade_sec: float) -> np.ndarray:
    if fade_sec <= 0 or samples.shape[0] < 4:
        return samples

    fade_frames = min(round(fade_sec * sample_rate), samples.shape[0] // 2)
    if fade_frames < 2:
        return samples

    faded = samples.copy()
    fade_in = np.linspace(0.0, 1.0, fade_frames, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, fade_frames, dtype=np.float32)
    faded[:fade_frames] *= fade_in[:, None]
    faded[-fade_frames:] *= fade_out[:, None]
    return faded


def write_segment_wavs(
    input_file: Path,
    annotation: Any,
    segments_dir: Path,
    *,
    padding_sec: float = DEFAULT_SEGMENT_PADDING_SEC,
    fade_sec: float = DEFAULT_SEGMENT_FADE_SEC,
    min_duration_sec: float = DEFAULT_MIN_SEGMENT_DURATION_SEC,
) -> list[Path]:
    try:
        import soundfile as sf
    except ImportError as exc:
        raise StageError("diarization", "soundfile is not installed") from exc

    if padding_sec < 0:
        raise StageError("diarization", "segment padding must be non-negative")
    if fade_sec < 0:
        raise StageError("diarization", "segment fade must be non-negative")
    if min_duration_sec < 0:
        raise StageError("diarization", "minimum segment duration must be non-negative")
    
    outputs: list[Path] = []
    segments_dir.mkdir(parents=True, exist_ok=True)

    with sf.SoundFile(str(input_file), mode="r") as source:
        for index, (turn, _, speaker) in enumerate(annotation.itertracks(yield_label=True)):
            turn_start = float(turn.start)
            turn_end = float(turn.end)
            turn_duration = turn_end - turn_start

            if turn_duration < min_duration_sec:
                LOGGER.debug(
                    "stage=diarization speaker=%s start=%.2f end=%.2f "
                    "duration=%.3f skipped=too_short",
                    speaker,
                    turn_start,
                    turn_end,
                    turn_duration,
                )
                continue

            padded_start = max(0.0, turn_start - padding_sec)
            padded_end = turn_end + padding_sec
            start_frame = max(0, math.floor(padded_start * source.samplerate))
            end_frame = min(len(source), math.ceil(padded_end * source.samplerate))

            if end_frame <= start_frame:
                continue

            safe_speaker = (
                _UNSAFE_LABEL.sub("_", str(speaker)).strip("._-") or "SPEAKER"
            )
            output = segments_dir / f"{safe_speaker}_{index:04d}.wav"

            source.seek(start_frame)
            samples = source.read(end_frame - start_frame, dtype="float32", always_2d=True)
            samples = _apply_edge_fades(samples, source.samplerate, fade_sec)

            sf.write(str(output), samples, source.samplerate, format="WAV", subtype="PCM_16")

            outputs.append(output)
            
            LOGGER.info(
                "stage=diarization speaker=%s start=%.2f end=%.2f "
                "padded_start=%.2f padded_end=%.2f segment=%s",
                speaker,
                turn_start,
                turn_end,
                start_frame / source.samplerate,
                end_frame / source.samplerate,
                output,
            )

    return outputs
