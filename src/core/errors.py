from __future__ import annotations


class PipelineError(RuntimeError):
    """Base exception for actionable pipeline failures."""


class StageError(PipelineError):
    """A pipeline stage failed."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(f"{stage} stage failed: {message}")
