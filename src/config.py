"""Policy loading."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]  # repo root (src/config.py → ..)
DEFAULT_POLICY_PATH = ROOT / "config" / "policies" / "default.yaml"
EVENTS_PATH = ROOT / "config" / "policies" / "events.yaml"


# Parsed YAML keyed by (path, mtime_ns, size). The engine loads policy/conditions/
# events once per night per module (≈5k parses per property-day, ~30% of runtime).
# A file edit changes mtime/size and forces a re-parse; callers get a deep copy so
# mutating a returned dict can never leak into another caller.
_YAML_CACHE: dict[tuple[str, int, int], dict[str, Any]] = {}


def load_yaml(path: Path) -> dict[str, Any]:
    st = path.stat()
    key = (str(path.resolve()), st.st_mtime_ns, st.st_size)
    cached = _YAML_CACHE.get(key)
    if cached is None:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Expected mapping in {path}")
        _YAML_CACHE[key] = cached = data
    return copy.deepcopy(cached)


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
RESORT_PATH = ROOT / "config" / "resort" / "winter_park.yaml"
PORTFOLIO_PATH = ROOT / "config" / "portfolio" / "mont_luxe.yaml"


def load_conditions(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or CONDITIONS_PATH)


def load_markets(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or MARKETS_PATH)


def load_resort_config(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or RESORT_PATH)


def load_portfolio_config(path: Path | None = None) -> dict[str, Any]:
    """Load portfolio ownership and market context without embedding it in code."""
    return load_yaml(path or PORTFOLIO_PATH)
