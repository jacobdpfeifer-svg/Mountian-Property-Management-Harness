"""Load frozen simulator calibration. No engine imports."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
CALIBRATION_PATH = ROOT / "calibration.yaml"
SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"

LEAD_BUCKETS = ((0, 7), (8, 21), (22, 60), (61, 120))
LOS_VALUES = (2, 3, 4, 5, 7)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping")
    return data


def iter_valued(node: Any, prefix: str = ""):
    """Yield (path, mapping) for every dict that stores a point value."""
    if isinstance(node, dict):
        if "value" in node:
            yield prefix, node
        for key, child in node.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            yield from iter_valued(child, child_path)


def assert_sources(data: dict[str, Any]) -> None:
    missing = []
    for path, node in iter_valued(data):
        source = node.get("source")
        if not isinstance(source, str) or not source.strip():
            missing.append(path)
    if missing:
        raise ValueError("calibration values without source: " + ", ".join(missing))
    for name, seg in data.get("segments", {}).items():
        if not str(seg.get("source", "")).strip():
            missing.append(name)
    if missing:
        raise ValueError("segments without source: " + ", ".join(missing))


def load_calibration(path: Path | None = None) -> dict[str, Any]:
    data = load_yaml(path or CALIBRATION_PATH)
    assert_sources(data)
    return data


def load_scenario(name: str, directory: Path | None = None) -> dict[str, Any]:
    directory = directory or SCENARIO_DIR
    path = directory / f"{name}.yaml"
    if not path.exists():
        known = sorted(p.stem for p in directory.glob("*.yaml"))
        raise FileNotFoundError(f"unknown scenario {name}; known: {known}")
    data = load_yaml(path)
    data["name"] = data.get("name", name)
    return data


def list_scenarios(directory: Path | None = None) -> list[str]:
    directory = directory or SCENARIO_DIR
    return sorted(p.stem for p in directory.glob("*.yaml"))


def season_of(day: date) -> str:
    """Winter-window seasons. November and early December are early winter,
    15 Dec–31 Mar is peak, everything else in the run is shoulder spring.
    """
    if day.month == 11 or (day.month == 12 and day.day <= 14):
        return "early_winter"
    if (day.month == 12 and day.day >= 15) or day.month in (1, 2, 3):
        return "peak_ski"
    return "shoulder_spring"


def daterange(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def value_of(node: dict[str, Any] | float | int) -> float:
    if isinstance(node, dict):
        return float(node["value"])
    return float(node)
