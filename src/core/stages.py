from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .errors import StageError


LOGGER = logging.getLogger(__name__)


def describe_paths(paths: Sequence[Path] | Path | None) -> str:
    if paths is None:
        return "-"
    if isinstance(paths, Path):
        return str(paths)
    return ", ".join(str(path) for path in paths)


@contextmanager
def stage_logging(
    stage: str,
    *,
    input_path: Path | str | None,
    output_paths: Sequence[Path] | Path | None,
    parameters: Mapping[str, Any] | None = None,
) -> Iterator[None]:
    started = time.monotonic()
    LOGGER.info(
        "stage=%s status=started input=%s output=%s parameters=%s",
        stage,
        input_path or "-",
        describe_paths(output_paths),
        dict(parameters or {}),
    )
    try:
        yield
    except Exception as exc:
        duration = time.monotonic() - started
        LOGGER.error(
            "stage=%s status=failed duration=%.2fs error=%s",
            stage,
            duration,
            exc,
        )
        if isinstance(exc, StageError):
            raise
        raise StageError(stage, str(exc)) from exc
    else:
        duration = time.monotonic() - started
        LOGGER.info("stage=%s status=completed duration=%.2fs", stage, duration)


def log_skipped_stage(stage: str, reason: str) -> None:
    LOGGER.info(
        f"stage={stage} status=skipped input=- output=- duration=0.00s reason={reason}"
    )