"""Overlays for simulator sensitivity. They do not edit calibration.yaml.

The official world stays the file that was hashed for the engine score.
A sensitivity run records its own calibration hash and must not be merged
with that scoreboard.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


def load_sensitivity(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping")
    if not str(data.get("label", "")).strip():
        raise ValueError(f"{path} needs a label")
    return data


def _set_path(root: dict[str, Any], dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    cursor = root
    for key in keys[:-1]:
        child = cursor.get(key)
        if not isinstance(child, dict):
            raise KeyError(dotted)
        cursor = child
    if keys[-1] not in cursor:
        raise KeyError(dotted)
    cursor[keys[-1]] = value


def apply_sensitivity(calibration: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``calibration`` with the sensitivity applied."""
    updated = copy.deepcopy(calibration)
    for dotted, value in (spec.get("set") or {}).items():
        _set_path(updated, str(dotted), value)
    factor = spec.get("scale_price_coef")
    if factor is not None:
        scale = float(factor)
        for segment in updated.get("segments", {}).values():
            coefs = segment.get("price_coef")
            if isinstance(coefs, dict):
                for season, coef in list(coefs.items()):
                    coefs[season] = float(coef) * scale
    return updated


def canonical_sha256(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()
