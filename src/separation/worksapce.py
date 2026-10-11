from __future__ import annotations

import shutil
from pathlib import Path

from ..core.files import ensure_outputs_available
from ..core.errors import StageError


def validate_separation_inputs(
    *,
    input_file: Path,
    vocals_output: Path,
    instrumental_output: Path,
    chunk_seconds: int,
    overwrite: bool,
) -> None:
    """Validate inputs and outputs before separation starts."""
    if not input_file.is_file():
        raise StageError("separation", f"input audio does not exist: {input_file}")

    if chunk_seconds <= 0:
        raise StageError("separation", "chunk_seconds must be greater than zero")

    ensure_outputs_available(
        [vocals_output, instrumental_output],
        overwrite,
        "separation",
    )


def prepare_separation_dirs(
    *,
    model_dir: Path,
    vocals_output: Path,
    instrumental_output: Path,
    work_dir: Path,
) -> tuple[Path, Path]:
    """Create clean work directories for this run."""
    model_dir.mkdir(parents=True, exist_ok=True)
    vocals_output.parent.mkdir(parents=True, exist_ok=True)
    instrumental_output.parent.mkdir(parents=True, exist_ok=True)

    if work_dir.exists():
        shutil.rmtree(work_dir)

    chunks_dir = work_dir / "input_chunks"
    separated_chunks_dir = work_dir / "separated_chunks"

    chunks_dir.mkdir(parents=True, exist_ok=True)
    separated_chunks_dir.mkdir(parents=True, exist_ok=True)

    return chunks_dir, separated_chunks_dir