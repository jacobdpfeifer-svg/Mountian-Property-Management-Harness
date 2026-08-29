"""Policy loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]  # repo root (src/config.py → ..)
DEFAULT_POLICY_PATH = ROOT / "config" / "policies" / "default.yaml"
EVENTS_PATH = ROOT / "config" / "policies" / "events.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_policy(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or DEFAULT_POLICY_PATH)


def load_events(path: Path | None = None) -> list[dict[str, Any]]:
    data = load_yaml(path or EVENTS_PATH)
    signals = data.get("signals", [])
    if not isinstance(signals, list):
        raise ValueError("events.yaml must contain a 'signals' list")
    return signals


CONDITIONS_PATH = ROOT / "config" / "policies" / "conditions.yaml"
MARKETS_PATH = ROOT / "config" / "policies" / "markets.yaml"


def load_conditions(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or CONDITIONS_PATH)


def load_markets(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or MARKETS_PATH)