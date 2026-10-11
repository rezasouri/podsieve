from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import PipelineError


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PipelineError(f"Configuration file does not exist: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PipelineError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise PipelineError(f"Configuration root must be a mapping: {path}")
    return data


def config_value(
    config: Mapping[str, Any], section: str, key: str, default: Any = None
) -> Any:
    values = config.get(section, {})
    if not isinstance(values, Mapping):
        raise PipelineError(f"Configuration section '{section}' must be a mapping")
    return values.get(key, default)


def resolve_from_root(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()
