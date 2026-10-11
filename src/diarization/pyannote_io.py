from __future__ import annotations

from typing import Any

from ..core.errors import StageError


def extract_annotation(result: Any) -> Any:
    annotation = getattr(result, "speaker_diarization", result)

    if not hasattr(annotation, "itertracks"):
        raise StageError("diarization", f"unexpected pyannote result type: {type(result).__name__}")
    
    return annotation

def segments_from_annotation(annotation: Any) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "start": round(float(turn.start), 6),
            "end": round(float(turn.end), 6),
            "duration": round(float(turn.end - turn.start), 6),
            "speaker": str(speaker),
        }
        for index, (turn, _, speaker) in enumerate(annotation.itertracks(yield_label=True))
    ]