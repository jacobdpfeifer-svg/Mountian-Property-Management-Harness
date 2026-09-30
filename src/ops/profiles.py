"""Property operations profiles: config/operations/mont_luxe.yaml → OpsProfile.

The version of a profile is the hash of its resolved fields, so every stored
turn cost can be traced to the exact assumptions that produced it.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from src.config import ROOT, load_yaml
from src.ops import OpsProfile

OPS_CONFIG_PATH = ROOT / "config" / "operations" / "mont_luxe.yaml"
OPS_POLICY_PATH = ROOT / "config" / "policies" / "operations.yaml"

_PROFILE_FIELDS = {f.name for f in fields(OpsProfile)} - {"property_id", "version"}


def load_ops_config(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or OPS_CONFIG_PATH)


def load_ops_policy(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or OPS_POLICY_PATH)


def _version(resolved: dict[str, Any]) -> str:
    raw = json.dumps(resolved, sort_keys=True, default=str).encode()
    return "opsprof_" + hashlib.sha256(raw).hexdigest()[:12]


def resolve_profiles(cfg: dict[str, Any]) -> dict[str, OpsProfile]:
    defaults = dict(cfg.get("defaults") or {})
    out: dict[str, OpsProfile] = {}
    for pid, block in (cfg.get("properties") or {}).items():
        merged = {**defaults, **(block or {})}
        unknown = set(merged) - _PROFILE_FIELDS
        if unknown:
            raise ValueError(f"unknown ops profile field(s) for {pid}: {sorted(unknown)}")
        if "base_clean_minutes" not in merged:
            raise ValueError(f"ops profile for {pid} needs base_clean_minutes")
        merged.setdefault("checkout_time", "10:00")
        merged.setdefault("checkin_time", "16:00")
        merged["snow_clearance_required"] = bool(merged.get("snow_clearance_required", False))
        out[str(pid)] = OpsProfile(property_id=str(pid), version=_version(merged), **merged)
    return out


def load_profiles(path: Path | None = None) -> dict[str, OpsProfile]:
    return resolve_profiles(load_ops_config(path))


def store_profiles(conn: sqlite3.Connection, profiles: dict[str, OpsProfile]) -> int:
    """Write any new profile versions. Returns how many versions were new."""
    from src.ops.db import ensure_ops_tables

    ensure_ops_tables(conn)
    created = 0
    for p in profiles.values():
        row = asdict(p)
        row["snow_clearance_required"] = int(p.snow_clearance_required)
        cols = list(row)
        cur = conn.execute(
            f"INSERT OR IGNORE INTO property_operations_profile ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})",
            [row[c] for c in cols],
        )
        created += cur.rowcount
    conn.commit()
    return created


def minutes_of_day(hhmm: str) -> int:
    hh, mm = str(hhmm).split(":", 1)
    return int(hh) * 60 + int(mm)
