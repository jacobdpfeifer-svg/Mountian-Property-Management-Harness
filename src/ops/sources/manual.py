"""Manual source: YAML profiles and crew roster → stored profiles and capacity."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

from src.ops import CapacitySnapshot
from src.ops.db import ImportResult, finish_import, record_capacity, start_import
from src.ops.economics import roster_minutes
from src.ops.profiles import load_ops_config, load_profiles, store_profiles

SOURCE = "manual"


def roster_snapshots(ops_cfg: dict[str, Any], start: date, end: date, as_of: date) -> list[CapacitySnapshot]:
    zones = sorted({z for c in (ops_cfg.get("capacity") or {}).get("crews") or []
                    for z in c.get("zones") or []})
    out: list[CapacitySnapshot] = []
    d = start
    while d <= end:
        for zone in zones:
            minutes = roster_minutes(ops_cfg, zone, d)
            if minutes is not None:
                out.append(CapacitySnapshot(as_of=as_of.isoformat(), service_date=d.isoformat(),
                                            access_zone=zone, available_worker_minutes=minutes,
                                            source=SOURCE, confidence=0.3))
        d += timedelta(days=1)
    return out


def import_manual(conn: sqlite3.Connection, start: date, end: date, *, as_of: date) -> ImportResult:
    """Store any new profile versions and snapshot the roster for [start, end]."""
    result = start_import(conn, SOURCE, "profiles+capacity")
    new_versions = store_profiles(conn, load_profiles())
    if new_versions:
        result.errors.append(f"info: {new_versions} new profile version(s) stored")
    record_capacity(conn, roster_snapshots(load_ops_config(), start, end, as_of), result)
    return finish_import(conn, result)
