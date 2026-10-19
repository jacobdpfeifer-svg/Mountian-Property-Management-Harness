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
    from src.runcache import memo, run_cache_active

    st = path.stat()
    key = (str(path.resolve()), st.st_mtime_ns, st.st_size)
    cached = _YAML_CACHE.get(key)
    if cached is None:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Expected mapping in {path}")
        _YAML_CACHE[key] = cached = data
    if run_cache_active():
        # One deepcopy per file per pricing run instead of once per night/module.
        return memo(("yaml", key), lambda: copy.deepcopy(cached))
    return copy.deepcopy(cached)


def load_policy(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or DEFAULT_POLICY_PATH)


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Nested dicts merge. Every other value replaces the base."""
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_policy_overlay(path: Path | None = None) -> dict[str, Any]:
    """Load a policy. A file with ``extends: default`` is merged onto default.yaml.

    The official default file is never written. Candidate trials use this so a
    short YAML diff is a full policy the engine can run.
    """
    if path is None:
        return load_policy()
    raw = load_yaml(path)
    if raw.get("extends") != "default":
        return raw
    overlay = {key: value for key, value in raw.items() if key != "extends"}
    return deep_merge(load_policy(), overlay)


def load_events(path: Path | None = None, *, today: date | None = None) -> list[dict[str, Any]]:
    """Dated local events from YAML, plus rule-generated federal windows.

    Federal names in the YAML are ignored so a hand-typed holiday cannot
    override the rule. `today` is injectable for tests.
    """
    from datetime import date as date_cls

    from src.signals.calendars import FEDERAL_RULES, federal_windows, season_january_years

    data = load_yaml(path or EVENTS_PATH)
    signals = data.get("signals", [])
    if not isinstance(signals, list):
        raise ValueError("events.yaml must contain a 'signals' list")
    federal_names = {rule["event_name"] for rule in FEDERAL_RULES}
    dated = [row for row in signals if row.get("event_name") not in federal_names]
    years = season_january_years(today or date_cls.today(), ahead=2)
    return dated + federal_windows(years)


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
