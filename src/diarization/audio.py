from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.errors import StageError

def load_audio_for_pyannote(path: str | Path, target_sr: int = 16000) -> dict[str, Any]:
    """Load audio in memory sp pyannote does not invoke TorchCodec decoding."""
    try:
        import torchaudio
    except ImportError as exc:
        raise StageError("diarization", "torchaudio is not installed") from exc
    
    waveform, sample_rate = torchaudio.load(str(path))

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    if sample_rate != target_sr:
        waveform = torchaudio.functional.resample(waveform, sample_rate, target_sr)
        sample_rate = target_sr
    
    return {
        "waveform": waveform,
        "sample_rate": sample_rate
    }