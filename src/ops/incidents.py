"""Disruption coordinator: signal crosses threshold → incident candidate → a person
approves bounded actions → outcome recorded.

    scan      reads signal_observations point-in-time for as_of .. as_of+lookahead,
              groups consecutive crossing days into one window per rule and market,
              and lists affected properties, arrivals, departures, and turns.
              Idempotent: the same window is the same incident.
    approve   one allowed action (src/ops/actions.py); forbidden actions raise.
    reject / outcome   recorded in incident_actions.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from src.ops.actions import ForbiddenAction, IncidentError, check_action, execute
from src.ops.profiles import load_ops_policy, load_profiles
from src.ops.turns import _crosses, market_for, signal_value

__all__ = ["ForbiddenAction", "IncidentError", "scan", "approve", "reject", "record_outcome",
           "list_incidents", "show"]


@dataclass
class IncidentCandidate:
    incident_id: str
    incident_type: str
    market_id: str
    window_start: date
    window_end: date
    severity: str
    signal_key: str
    signal_value: float
    threshold: float
    affected: dict[str, Any]
    actions: list[str]
    created: bool = False


def _incident_id(rule_type: str, market: str, start: date) -> str:
    raw = f"{rule_type}|{market}|{start.isoformat()}"
    return "inc_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _affected(conn: sqlite3.Connection, property_ids: list[str], start: date, end: date) -> dict[str, Any]:
    arrivals: list[dict[str, Any]] = []
    departures: list[dict[str, Any]] = []
    for pid in property_ids:
        for r in conn.execute(
            """SELECT reservation_id, property_id, check_in, check_out, source FROM reservations
               WHERE property_id=? AND LOWER(status) IN ('confirmed','checked_in')
                 AND ((check_in>=? AND check_in<=?) OR (check_out>=? AND check_out<=?))""",
            (pid, start.isoformat(), end.isoformat(), start.isoformat(), end.isoformat()),
        ).fetchall():
            row = {"reservation_id": r["reservation_id"], "property_id": r["property_id"],
                   "check_in": str(r["check_in"])[:10], "check_out": str(r["check_out"])[:10],
                   "owner_stay": (r["source"] or "").lower() == "owner"}
            if start.isoformat() <= row["check_in"] <= end.isoformat():
                arrivals.append(row)
            if start.isoformat() <= row["check_out"] <= end.isoformat():
                departures.append(row)
    turns = sorted({(d["property_id"], d["check_out"]) for d in departures})
    return {
        "properties": property_ids,
        "arrivals": arrivals,
        "departures": departures,
        "turns": [{"property_id": p, "service_date": d} for p, d in turns],
    }


def scan(conn: sqlite3.Connection, as_of: date, ops_policy: dict[str, Any] | None = None) -> list[IncidentCandidate]:
    policy = ops_policy if ops_policy is not None else load_ops_policy()
    cfg = policy.get("incidents") or {}
    lookahead = int(cfg.get("lookahead_days", 3))
    by_market: dict[str, list[str]] = {}
    for pid in load_profiles():
        by_market.setdefault(market_for(conn, pid), []).append(pid)
    found: list[IncidentCandidate] = []
    for rule in cfg.get("rules") or []:
        for market, pids in by_market.items():
            hits: list[tuple[date, float]] = []
            for offset in range(lookahead + 1):
                day = as_of + timedelta(days=offset)
                val = signal_value(conn, rule["signal_key"], market, day, as_of)
                if val is not None and _crosses(val, rule.get("op", ">="), float(rule["threshold"])):
                    hits.append((day, val))
            # Consecutive crossing days form one window.
            windows: list[list[tuple[date, float]]] = []
            for day, val in hits:
                if windows and day == windows[-1][-1][0] + timedelta(days=1):
                    windows[-1].append((day, val))
                else:
                    windows.append([(day, val)])
            for w in windows:
                start, end = w[0][0], w[-1][0]
                worst = max(w, key=lambda item: abs(item[1] - float(rule["threshold"])))[1]
                cand = IncidentCandidate(
                    incident_id=_incident_id(rule["type"], market, start),
                    incident_type=rule["type"], market_id=market, window_start=start,
                    window_end=end, severity=rule.get("severity", "warn"),
                    signal_key=rule["signal_key"], signal_value=worst,
                    threshold=float(rule["threshold"]),
                    affected=_affected(conn, pids, start, end),
                    actions=[a for a in rule.get("actions") or [] if a not in ("",)],
                )
                for a in cand.actions:
                    check_action(a)  # a misconfigured rule must not smuggle in a forbidden action
                cur = conn.execute(
                    """INSERT OR IGNORE INTO incidents (incident_id, incident_type, market_id,
                           detected_at, window_start, window_end, severity, signal_key, signal_value,
                           threshold, affected_json, actions_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (cand.incident_id, cand.incident_type, market, as_of.isoformat(),
                     start.isoformat(), end.isoformat(), cand.severity, cand.signal_key,
                     cand.signal_value, cand.threshold, json.dumps(cand.affected),
                     json.dumps(cand.actions)),
                )
                cand.created = cur.rowcount > 0
                if not cand.created:
                    conn.execute(
                        """UPDATE incidents SET window_end=MAX(window_end, ?), signal_value=?,
                               affected_json=? WHERE incident_id=? AND status IN ('candidate','acknowledged')""",
                        (end.isoformat(), cand.signal_value, json.dumps(cand.affected), cand.incident_id),
                    )
                found.append(cand)
    conn.commit()
    return found


def _load(conn: sqlite3.Connection, incident_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
    if row is None:
        raise IncidentError(f"unknown incident {incident_id!r}")
    out = dict(row)
    out["affected"] = json.loads(out.pop("affected_json") or "{}")
    out["actions"] = json.loads(out.pop("actions_json") or "[]")
    return out


def list_incidents(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM incidents"
    params: list[Any] = []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    return conn.execute(sql + " ORDER BY window_start DESC, incident_id", params).fetchall()


def show(conn: sqlite3.Connection, incident_id: str) -> dict[str, Any]:
    inc = _load(conn, incident_id)
    inc["log"] = [dict(r) for r in conn.execute(
        "SELECT * FROM incident_actions WHERE incident_id=? ORDER BY action_id", (incident_id,)
    ).fetchall()]
    return inc


def approve(conn: sqlite3.Connection, incident_id: str, action: str, *, actor: str,
            live: bool = False, adapter: str = "dry_run") -> dict[str, Any]:
    if not actor:
        raise IncidentError("approval needs a named actor")
    check_action(action)
    inc = _load(conn, incident_id)
    if inc["status"] in ("dismissed", "closed"):
        raise IncidentError(f"incident {incident_id} is {inc['status']}")
    conn.execute(
        """INSERT INTO incident_actions (incident_id, action_code, status, actor, payload_json)
           VALUES (?,?,?,?,?)""",
        (incident_id, action, "approved", actor, json.dumps({"adapter": adapter, "live": live})),
    )
    try:
        result = execute(conn, inc, action, actor=actor, live=live, adapter=adapter)
    except Exception as exc:
        conn.execute(
            """INSERT INTO incident_actions (incident_id, action_code, status, actor, outcome)
               VALUES (?,?,?,?,?)""",
            (incident_id, action, "failed", actor, f"{type(exc).__name__}: {exc}"),
        )
        conn.commit()
        raise
    conn.execute(
        """INSERT INTO incident_actions (incident_id, action_code, status, actor, output_ref, outcome)
           VALUES (?,?,?,?,?,?)""",
        (incident_id, action, "executed", actor, result.get("output_ref"), result.get("summary")),
    )
    conn.execute("UPDATE incidents SET status='acknowledged' WHERE incident_id=? AND status='candidate'",
                 (incident_id,))
    conn.commit()
    return {"incident_id": incident_id, "action": action, **result}


def reject(conn: sqlite3.Connection, incident_id: str, action: str, *, actor: str,
           note: str | None = None) -> None:
    _load(conn, incident_id)
    conn.execute(
        """INSERT INTO incident_actions (incident_id, action_code, status, actor, outcome)
           VALUES (?,?,?,?,?)""",
        (incident_id, action, "rejected", actor, note),
    )
    conn.commit()


def record_outcome(conn: sqlite3.Connection, incident_id: str, *, actor: str, outcome: str,
                   close: bool = False) -> None:
    _load(conn, incident_id)
    conn.execute(
        """INSERT INTO incident_actions (incident_id, action_code, status, actor, outcome)
           VALUES (?,?,?,?,?)""",
        (incident_id, "outcome", "outcome", actor, outcome),
    )
    if close:
        conn.execute("UPDATE incidents SET status='closed' WHERE incident_id=?", (incident_id,))
    conn.commit()
