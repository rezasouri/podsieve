from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from .errors import StageError


LOGGER = logging.getLogger(__name__)


def require_executable(name: str, stage: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise StageError(stage, f"required executable '{name}' was not found on PATH")
    return executable


def run_command(
    command: Sequence[str], *, stage: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    LOGGER.info(f"stage={stage} command={shlex.join(command)}")
    try:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise StageError(
            stage,
            f"command failed ({shlex.join(command)}): {detail}",
        ) from exc

    if result.stderr.strip():
        LOGGER.debug(f"stage={stage} stderr={result.stderr.strip()}")
    return result