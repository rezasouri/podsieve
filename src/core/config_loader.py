from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from .config import load_config, resolve_from_root
from .errors import PipelineError


def merge_config_layers(*layers: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for layer in layers:
        merged.update(dict(layer))
    return merged


def dataclass_field_names(dataclass_type: type) -> set[str]:
    if not is_dataclass(dataclass_type):
        raise TypeError("dataclass_type must be a dataclass")
    return {field.name for field in fields(dataclass_type)}


def validate_known_keys(
    config_dict: Mapping[str, Any],
    dataclass_type: type,
    *,
    allowed_extra_keys: set[str] | None = None,
    source_name: str = "configuration",
) -> None:
    allowed = dataclass_field_names(dataclass_type) | set(allowed_extra_keys or ())
    unknown = sorted(set(config_dict) - allowed)
    if unknown:
        raise PipelineError(
            f"{source_name} contains unknown keys: " + ", ".join(unknown)
        )


def section_or_top_level_values(
    raw_config: Mapping[str, Any],
    *,
    section: str,
    source_name: str,
) -> dict[str, Any]:
    if section in raw_config:
        values = raw_config.get(section, {})
        if values is None:
            return {}
        if not isinstance(values, Mapping):
            raise PipelineError(
                f"Configuration section '{section}' must be a mapping: {source_name}"
            )
        return dict(values)
    return dict(raw_config)


def load_layer_values(
    path: Path,
    *,
    repo_root: Path,
    section: str,
) -> dict[str, Any]:
    resolved = resolve_from_root(repo_root, path)
    raw_config = load_config(resolved)
    return section_or_top_level_values(
        raw_config,
        section=section,
        source_name=str(resolved),
    )
