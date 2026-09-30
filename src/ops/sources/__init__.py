"""Every way operations data can arrive, normalized to one write path.

Sources:
  manual        config/operations/mont_luxe.yaml (profiles + crew roster)
  csv           column-mapped CSV, with presets for vendor exports
  guesty_tasks  Guesty Open API tasks (reuses Guesty auth)
  breezeway     Breezeway API (client credentials)
  turno         Turno API (bearer token)
  telemetry     generic sensor JSON → asset_health_events
  webhooks      Guesty task.* webhook deliveries → bounded task re-read

API clients are written from public vendor documentation and have NOT been
verified against a live tenant. They fail closed: missing credentials report
`unconfigured`; an unexpected payload shape rejects the row rather than guessing.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import Any

from src.ops.profiles import load_ops_config

SOURCE_NAMES = ("manual", "csv", "guesty_tasks", "breezeway", "turno", "telemetry", "webhooks")


class SourceUnconfigured(RuntimeError):
    """Credentials or configuration for a source are missing."""


class PropertyResolver:
    """Map a vendor's property reference to a Mont Luxe property_id. Never guesses."""

    def __init__(self, conn: sqlite3.Connection | None = None, ops_cfg: dict[str, Any] | None = None):
        cfg = ops_cfg if ops_cfg is not None else load_ops_config()
        self._ids = set((cfg.get("properties") or {}).keys())
        self._lookup: dict[str, str] = {}
        for pid in self._ids:
            self._lookup[pid.lower()] = pid
        for pid, names in (cfg.get("aliases") or {}).items():
            for name in names or []:
                self._lookup[str(name).strip().lower()] = pid
        if conn is not None:
            try:
                rows = conn.execute(
                    "SELECT property_id, pms_listing_id, name FROM properties"
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            for r in rows:
                pid = str(r["property_id"])
                self._ids.add(pid)
                self._lookup.setdefault(pid.lower(), pid)
                if r["pms_listing_id"]:
                    self._lookup[str(r["pms_listing_id"]).strip().lower()] = pid
                if r["name"]:
                    self._lookup.setdefault(str(r["name"]).strip().lower(), pid)

    def resolve(self, *refs: Any) -> str | None:
        for ref in refs:
            if ref is None:
                continue
            key = str(ref).strip().lower()
            if key in self._lookup:
                return self._lookup[key]
        return None


@dataclass(frozen=True)
class SourceStatus:
    name: str
    configured: bool
    detail: str
    last_run: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        return {"source": self.name, "configured": self.configured,
                "detail": self.detail, "last_run": self.last_run}


def _last_run(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    try:
        row = conn.execute(
            "SELECT * FROM ops_import_runs WHERE source=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (name,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    return {k: row[k] for k in ("run_id", "kind", "started_at", "status", "rows_in",
                                 "accepted", "rejected")}


def status(conn: sqlite3.Connection) -> list[SourceStatus]:
    from src.ops.sources.breezeway import BreezewayClient
    from src.ops.sources.turno import TurnoClient

    out: list[SourceStatus] = []
    cfg = load_ops_config()
    n_props = len(cfg.get("properties") or {})
    out.append(SourceStatus("manual", n_props > 0,
                            f"{n_props} profile(s); basis={(cfg.get('defaults') or {}).get('basis')}",
                            _last_run(conn, "manual")))
    out.append(SourceStatus("csv", True, "always available: wp-price ops import --source csv",
                            _last_run(conn, "csv")))
    from src.pms.guesty import load_dotenv

    load_dotenv()
    guesty_ok = bool(os.environ.get("GUESTY_CLIENT_ID") and os.environ.get("GUESTY_CLIENT_SECRET"))
    out.append(SourceStatus("guesty_tasks", guesty_ok,
                            "uses GUESTY_CLIENT_ID/SECRET" if guesty_ok else "GUESTY_CLIENT_ID/SECRET not set",
                            _last_run(conn, "guesty_tasks")))
    out.append(SourceStatus("breezeway", BreezewayClient.configured(),
                            "BREEZEWAY_CLIENT_ID/SECRET" + (" set" if BreezewayClient.configured() else " not set"),
                            _last_run(conn, "breezeway")))
    out.append(SourceStatus("turno", TurnoClient.configured(),
                            "TURNO_API_TOKEN" + (" set" if TurnoClient.configured() else " not set"),
                            _last_run(conn, "turno")))
    out.append(SourceStatus("telemetry", True, "JSON files: wp-price ops import --source telemetry",
                            _last_run(conn, "telemetry")))
    try:
        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM pms_webhook_events WHERE event_type LIKE 'task%'"
        ).fetchone()["c"]
    except sqlite3.OperationalError:
        pending = 0
    out.append(SourceStatus("webhooks", True, f"{pending} Guesty task event(s) recorded",
                            _last_run(conn, "webhooks")))
    return out
