"""Generic sensor telemetry → asset_health_events.

No hardware is assumed. Any sensor bridge (thermostat, leak sensor, lock, spa
monitor) can drop JSON files in this shape, one object or a list:

    {"property": "summit_haus",          # property_id, Guesty listing id, or alias
     "system": "heat",                   # heat|water|septic|spa|lock|snow_access|power|propane|co_safety
     "observed_at": "2026-12-20T06:15:00-07:00",
     "device_id": "ecobee-upstairs",     # becomes source_ref
     "readings": {"temp_f": 44},
     "severity": "critical"}             # optional; derived from readings when absent

Derived severities use `telemetry` thresholds in config/policies/operations.yaml
(defaults below). A critical reading moves the property to at_risk
automatically; nothing more severe is ever automatic.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.ops import AssetEvent
from src.ops.db import ImportResult, finish_import, record_asset_event, start_import
from src.ops.sources import PropertyResolver
from src.ops.sources.normalize import as_bool, as_float, as_iso_datetime

SOURCE = "telemetry"
DEFAULT_THRESHOLDS: dict[str, Any] = {
    "heat": {"critical_below_f": 45, "warn_below_f": 55},
    "spa": {"warn_below_f": 95},
    "lock": {"warn_battery_below_pct": 20},
}


def derive_severity(system: str, readings: dict[str, Any], thresholds: dict[str, Any]) -> str:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if as_bool(readings.get("leak")) or as_bool(readings.get("alarm")) or as_bool(readings.get("co_alarm")):
        return "critical"
    if as_bool(readings.get("offline")):
        return "warn"
    temp = as_float(readings.get("temp_f"))
    if system in ("heat", "water") and temp is not None:
        cfg = t.get("heat") or {}
        if temp < float(cfg.get("critical_below_f", 45)):
            return "critical"
        if temp < float(cfg.get("warn_below_f", 55)):
            return "warn"
    if system == "spa" and temp is not None and temp < float((t.get("spa") or {}).get("warn_below_f", 95)):
        return "warn"
    battery = as_float(readings.get("battery_pct"))
    if system == "lock" and battery is not None and battery < float(
            (t.get("lock") or {}).get("warn_battery_below_pct", 20)):
        return "warn"
    return "info"


def normalize(obj: dict[str, Any], resolver: PropertyResolver, thresholds: dict[str, Any]) -> AssetEvent:
    pid = resolver.resolve(obj.get("property"), obj.get("property_id"))
    observed = as_iso_datetime(obj.get("observed_at"))
    system = str(obj.get("system") or "").strip()
    if pid is None or observed is None or not system:
        raise ValueError(f"telemetry needs known property, observed_at, system: {obj!r:.120}")
    readings = obj.get("readings") or {}
    if not isinstance(readings, dict):
        raise ValueError("telemetry readings must be an object")
    severity = str(obj.get("severity") or derive_severity(system, readings, thresholds))
    return AssetEvent(property_id=pid, system_type=system, observed_at=observed,
                      severity=severity, source_type="sensor",
                      source_ref=str(obj.get("device_id") or "") or None, reading=readings)


def import_telemetry(conn: sqlite3.Connection, path: Path | str,
                     ops_policy: dict[str, Any] | None = None) -> ImportResult:
    from src.ops.profiles import load_ops_policy
    from src.ops.readiness import auto_escalate

    policy = ops_policy if ops_policy is not None else load_ops_policy()
    result = start_import(conn, SOURCE, "asset_events")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else [payload]
    resolver = PropertyResolver(conn)
    for obj in items:
        result.rows_in += 1
        try:
            event = normalize(obj, resolver, policy.get("telemetry") or {})
            event_id, created = record_asset_event(conn, event)
        except (ValueError, sqlite3.IntegrityError) as exc:
            result.rejected += 1
            result.errors.append(str(exc))
            continue
        if not created:
            result.duplicates += 1
            continue
        result.accepted += 1
        if event.severity == "critical":
            auto_escalate(conn, event.property_id, event_id, actor="telemetry",
                          note=f"critical {event.system_type} reading")
    return finish_import(conn, result)
