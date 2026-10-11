from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .errors import StageError


def ensure_outputs_available(
    paths: Sequence[Path],
    overwrite: bool,
    stage: str,
) -> None:
    existing = [path for path in paths if path.exists()]

    if existing and not overwrite:
        joined = ", ".join(str(path) for path in existing)
        raise StageError(
            stage,
            f"output already exists: {joined}. Pass --overwrite to replace it.",
        )