"""Property serviceability: is the house fit to receive a guest?

    ready → at_risk → inspection_required → out_of_service
          → remediation_in_progress → verified_ready → ready

Rules:
  * Every transition cites an asset_health_events row as evidence.
  * Automatic actors (signals, telemetry) may only move a property to at_risk,
    because at_risk only reduces autonomy. Every other state is human-entered.
  * verified_ready needs a named human, or a sensor reading that passes the
    deterministic check in operations.yaml → readiness.sensor_verification.
  * The current state is the latest transition; nothing else stores it.

Pricing effects (applied in src/compose): at_risk demotes the night to
suggest; inspection_required also blocks upward moves; out_of_service blocks
the night and recommends (never performs) an inventory closure.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from src.utils import parse_date

READY = "ready"
AT_RISK = "at_risk"
INSPECTION_REQUIRED = "inspection_required"
OUT_OF_SERVICE = "out_of_service"
REMEDIATION = "remediation_in_progress"
VERIFIED_READY = "verified_ready"
STATES = (READY, AT_RISK, INSPECTION_REQUIRED, OUT_OF_SERVICE, REMEDIATION, VERIFIED_READY)

_RANK = {READY: 0, VERIFIED_READY: 0, AT_RISK: 1, INSPECTION_REQUIRED: 2,
         REMEDIATION: 3, OUT_OF_SERVICE: 3}
EDGES: dict[str, frozenset[str]] = {
    READY: frozenset({AT_RISK, INSPECTION_REQUIRED, OUT_OF_SERVICE}),
    VERIFIED_READY: frozenset({READY, AT_RISK, INSPECTION_REQUIRED, OUT_OF_SERVICE}),
    # A risk never clears merely because its estimated window ended. Recovery
    # is explicit and evidenced: at_risk -> verified_ready -> ready.
    AT_RISK: frozenset({AT_RISK, VERIFIED_READY, INSPECTION_REQUIRED, OUT_OF_SERVICE}),
    INSPECTION_REQUIRED: frozenset({VERIFIED_READY, OUT_OF_SERVICE}),
    OUT_OF_SERVICE: frozenset({REMEDIATION}),
    REMEDIATION: frozenset({VERIFIED_READY, OUT_OF_SERVICE}),
}
AUTO_ACTORS = frozenset({"signal", "telemetry", "system"})
# States that change what pricing may do for a night.
RESTRICTING = frozenset({AT_RISK, INSPECTION_REQUIRED, OUT_OF_SERVICE, REMEDIATION})


class ReadinessError(ValueError):
    """Illegal transition or missing evidence."""


@dataclass(frozen=True)
class ReadinessState:
    property_id: str
    state: str
    effective_from: date | None
    effective_to: date | None
    since: str | None
    evidence_event_id: str | None
    actor: str | None
    note: str | None

    def covers(self, stay_date: date) -> bool:
        if self.effective_from is not None and stay_date < self.effective_from:
            return False
        if self.effective_to is not None and stay_date > self.effective_to:
            return False
        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id, "state": self.state,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "since": self.since, "evidence_event_id": self.evidence_event_id,
            "actor": self.actor, "note": self.note,
        }


def _iso_at(at: datetime | date | str | None) -> str:
    if at is None:
        return datetime.now().replace(microsecond=0).isoformat()
    if isinstance(at, datetime):
        return at.replace(microsecond=0).isoformat()
    if isinstance(at, date):
        return f"{at.isoformat()}T23:59:59"
    return str(at)


def current_state(conn: sqlite3.Connection, property_id: str,
                  as_of: datetime | date | str | None = None) -> ReadinessState:
    """Latest transition at or before as_of (a date means end of that day)."""
    try:
        row = conn.execute(
            """SELECT * FROM readiness_transitions WHERE property_id=? AND at<=?
               ORDER BY at DESC, transition_id DESC LIMIT 1""",
            (property_id, _iso_at(as_of)),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None:
        return ReadinessState(property_id, READY, None, None, None, None, None, None)
    return ReadinessState(
        property_id=property_id,
        state=str(row["to_state"]),
        effective_from=parse_date(row["effective_from"]) if row["effective_from"] else None,
        effective_to=parse_date(row["effective_to"]) if row["effective_to"] else None,
        since=str(row["at"]),
        evidence_event_id=row["evidence_event_id"],
        actor=row["actor"],
        note=row["note"],
    )


def state_for_night(conn: sqlite3.Connection, property_id: str, stay_date: date,
                    as_of: datetime | date | str | None = None) -> ReadinessState:
    """Latest recorded state applicable to a night, with fail-safe expiry.

    A later transition for a different future window must not hide an older
    restriction that covers this night. Restricting states also do not silently
    become ``ready`` when ``effective_to`` passes; only an evidenced recovery
    transition can clear them.
    """
    try:
        rows = conn.execute(
            """SELECT * FROM readiness_transitions WHERE property_id=? AND at<=?
               ORDER BY at DESC, transition_id DESC""",
            (property_id, _iso_at(as_of)),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []

    def from_row(row: sqlite3.Row) -> ReadinessState:
        return ReadinessState(
            property_id=property_id,
            state=str(row["to_state"]),
            effective_from=parse_date(row["effective_from"]) if row["effective_from"] else None,
            effective_to=parse_date(row["effective_to"]) if row["effective_to"] else None,
            since=str(row["at"]), evidence_event_id=row["evidence_event_id"],
            actor=row["actor"], note=row["note"],
        )

    for row in rows:
        st = from_row(row)
        if st.covers(stay_date):
            return st
    if rows:
        latest = from_row(rows[0])
        # Expiry is an estimate of the affected window, not evidence of repair.
        # Once the window has actually elapsed, keep a restrictive state
        # fail-closed until recovery. Before then, nights beyond the forecast
        # window remain unaffected.
        decision_day = parse_date(_iso_at(as_of)[:10])
        if (latest.state in RESTRICTING and latest.effective_to is not None
                and decision_day > latest.effective_to):
            return latest
        return ReadinessState(property_id, READY, None, None, latest.since, None, None, None)
    return ReadinessState(property_id, READY, None, None, None, None, None, None)


def _sensor_verifies(conn: sqlite3.Connection, event_id: str, ops_policy: dict[str, Any]) -> bool:
    row = conn.execute(
        "SELECT source_type, system_type, reading_json FROM asset_health_events WHERE event_id=?",
        (event_id,),
    ).fetchone()
    if row is None or row["source_type"] != "sensor":
        return False
    checks = ((ops_policy.get("readiness") or {}).get("sensor_verification") or {}).get(
        row["system_type"])
    if not checks:
        return False
    reading = json.loads(row["reading_json"] or "{}")
    for key, bound in checks.items():
        if key.startswith("min_"):
            val = reading.get(key.removeprefix("min_"))
            if val is None or float(val) < float(bound):
                return False
        elif key.startswith("max_"):
            val = reading.get(key.removeprefix("max_"))
            if val is None or float(val) > float(bound):
                return False
    return True


def transition(
    conn: sqlite3.Connection,
    property_id: str,
    to_state: str,
    *,
    evidence_event_id: str,
    actor: str,
    at: datetime | str | None = None,
    effective_from: date | None = None,
    effective_to: date | None = None,
    note: str | None = None,
    ops_policy: dict[str, Any] | None = None,
) -> ReadinessState:
    if to_state not in STATES:
        raise ReadinessError(f"unknown state {to_state!r}")
    if not actor:
        raise ReadinessError("a transition needs an actor")
    if not evidence_event_id or conn.execute(
        "SELECT 1 FROM asset_health_events WHERE event_id=? AND property_id=?",
        (evidence_event_id, property_id),
    ).fetchone() is None:
        raise ReadinessError(f"evidence event {evidence_event_id!r} not found for {property_id}")
    at_s = _iso_at(at)
    cur = current_state(conn, property_id, at_s)
    if to_state not in EDGES[cur.state]:
        raise ReadinessError(f"{property_id}: {cur.state} → {to_state} is not an allowed transition")
    if actor in AUTO_ACTORS and to_state != AT_RISK:
        raise ReadinessError(f"automatic actor {actor!r} may only set at_risk, not {to_state}")
    if to_state == VERIFIED_READY and actor in AUTO_ACTORS:
        raise ReadinessError("verified_ready needs a named human or a passing sensor check")
    if to_state == VERIFIED_READY and actor == "sensor_check":
        from src.ops.profiles import load_ops_policy

        if not _sensor_verifies(conn, evidence_event_id, ops_policy or load_ops_policy()):
            raise ReadinessError("sensor reading does not pass readiness.sensor_verification")
    if to_state == VERIFIED_READY and actor != "sensor_check" and actor.strip().lower() in {
            "operator", "human", "user", "unknown"}:
        raise ReadinessError("verified_ready needs the verifier's name, not a generic actor")
    if to_state in (VERIFIED_READY, READY):
        evidence = conn.execute(
            "SELECT system_type FROM asset_health_events WHERE event_id=?", (evidence_event_id,)
        ).fetchone()
        assert evidence is not None  # existence was checked above
        other_critical = conn.execute(
            """SELECT event_id, system_type FROM asset_health_events
               WHERE property_id=? AND status='open' AND severity='critical'
                 AND system_type<>? AND observed_at<=? LIMIT 1""",
            (property_id, evidence["system_type"], at_s),
        ).fetchone()
        if other_critical is not None:
            raise ReadinessError(
                f"cannot mark ready while critical {other_critical['system_type']} event "
                f"{other_critical['event_id']} remains open"
            )
    eff_from = effective_from or parse_date(at_s[:10])
    conn.execute(
        """INSERT INTO readiness_transitions
           (property_id, from_state, to_state, at, effective_from, effective_to,
            evidence_event_id, actor, note) VALUES (?,?,?,?,?,?,?,?,?)""",
        (property_id, cur.state, to_state, at_s, eff_from.isoformat(),
         effective_to.isoformat() if effective_to else None, evidence_event_id, actor, note),
    )
    if to_state == VERIFIED_READY:
        conn.execute(
            """UPDATE asset_health_events SET status='resolved', resolved_at=?,
                   verified_by=COALESCE(verified_by, ?)
               WHERE property_id=? AND status='open' AND observed_at<=?
                 AND system_type=(SELECT system_type FROM asset_health_events WHERE event_id=?)""",
            (at_s, actor if actor not in AUTO_ACTORS else None, property_id, at_s,
             evidence_event_id),
        )
    conn.commit()
    return current_state(conn, property_id, at_s)


def auto_escalate(conn: sqlite3.Connection, property_id: str, event_id: str, *, actor: str,
                  note: str, at: datetime | str | None = None,
                  effective_from: date | None = None,
                  effective_to: date | None = None) -> bool:
    """Move a ready property to at_risk. No-op when it is already at_risk or worse."""
    effective_day = effective_from or parse_date(_iso_at(at)[:10])
    governing = state_for_night(conn, property_id, effective_day, _iso_at(at))
    if _RANK[governing.state] > _RANK[AT_RISK]:
        return False
    cur = current_state(conn, property_id, _iso_at(at))
    if governing.state == AT_RISK and cur.state == AT_RISK and cur.covers(effective_day):
        return False
    transition(conn, property_id, AT_RISK, evidence_event_id=event_id, actor=actor, at=at,
               effective_from=effective_from, effective_to=effective_to, note=note)
    return True


def revenue_at_risk(conn: sqlite3.Connection, property_id: str, start: date, end: date,
                    ops_policy: dict[str, Any]) -> dict[str, Any]:
    """Confirmed booking value in [start, end] plus relocation and review exposure."""
    from src.ops.turns import load_stays

    cfg = ops_policy.get("readiness") or {}
    booked = 0.0
    affected: list[str] = []
    for s in load_stays(conn, property_id, start, end):
        if s.check_out <= start or s.check_in > end or (s.source or "").lower() == "owner":
            continue
        nights = max(1, (s.check_out - s.check_in).days)
        overlap = (min(s.check_out, end + timedelta(days=1)) - max(s.check_in, start)).days
        if overlap <= 0:
            continue
        affected.append(s.reservation_id)
        if s.fare_accommodation:
            booked += float(s.fare_accommodation) * overlap / nights
    relocation = float(cfg.get("relocation_cost", 0.0)) * len(affected)
    review = float(cfg.get("review_loss_value", 0.0)) * len(affected)
    return {
        "booked_value": round(booked, 2),
        "relocation_exposure": round(relocation, 2),
        "review_exposure": round(review, 2),
        "total": round(booked + relocation + review, 2),
        "reservations": affected,
    }


def _crosses(value: float, op: str, threshold: float) -> bool:
    from src.ops.turns import _crosses as crosses

    return crosses(value, op, threshold)


def scan_signal_risk(conn: sqlite3.Connection, as_of: date, ops_policy: dict[str, Any],
                     property_ids: list[str], *, lookahead_days: int | None = None) -> list[dict[str, Any]]:
    """Signals crossing readiness.auto_at_risk → evidence event + at_risk. Idempotent."""
    from src.ops import AssetEvent
    from src.ops.db import record_asset_event
    from src.ops.turns import market_for, signal_value

    days = int(lookahead_days if lookahead_days is not None
               else (ops_policy.get("incidents") or {}).get("lookahead_days", 3))
    rules = (ops_policy.get("readiness") or {}).get("auto_at_risk") or []
    changed: list[dict[str, Any]] = []
    for pid in property_ids:
        market = market_for(conn, pid)
        for offset in range(days + 1):
            day = as_of + timedelta(days=offset)
            for rule in rules:
                val = signal_value(conn, rule["signal_key"], market, day, as_of)
                if val is None or not _crosses(val, rule.get("op", ">="), float(rule["threshold"])):
                    continue
                event_id, _ = record_asset_event(conn, AssetEvent(
                    property_id=pid, system_type=rule.get("system_type", "other"),
                    observed_at=f"{as_of.isoformat()}T00:00:00", severity="warn",
                    source_type="signal", source_ref=f"{rule['signal_key']}@{day.isoformat()}",
                    effective_from=day.isoformat(), effective_to=day.isoformat(),
                    reading={"value": val, "threshold": rule["threshold"]},
                ))
                if auto_escalate(conn, pid, event_id, actor="signal", note=rule.get("note"),
                                 at=f"{as_of.isoformat()}T00:00:00", effective_from=day,
                                 effective_to=as_of + timedelta(days=days)):
                    changed.append({"property_id": pid, "signal_key": rule["signal_key"],
                                    "value": val, "stay_date": day.isoformat()})
    conn.commit()
    return changed


_STATE_ACTION = {
    AT_RISK: "suggest-only until the risk clears",
    INSPECTION_REQUIRED: "no upward moves and suggest-only until inspected",
    OUT_OF_SERVICE: "blocked; recommend closing these nights in Guesty (a human action)",
    REMEDIATION: "blocked while remediation is in progress; recommend keeping the nights closed",
}


def readiness_reason_facts(conn: sqlite3.Connection, st: ReadinessState, as_of: date) -> dict[str, Any]:
    """Facts for the `readiness` reason on a recommendation. Memoized per run."""
    from src.ops.profiles import load_ops_policy
    from src.runcache import memo

    start = st.effective_from or as_of
    end = st.effective_to or (start + timedelta(days=14))
    risk = memo(("ops_revenue_at_risk", id(conn), st.property_id, st.since, start, end),
                lambda: revenue_at_risk(conn, st.property_id, start, end,
                                        memo(("ops_policy",), load_ops_policy)))
    system = None
    if st.evidence_event_id:
        row = conn.execute("SELECT system_type FROM asset_health_events WHERE event_id=?",
                           (st.evidence_event_id,)).fetchone()
        system = row["system_type"] if row else None
    label = st.state.replace("_", " ")
    message = (f"Property {label}{f' ({system})' if system else ''}: {_STATE_ACTION[st.state]}; "
               f"revenue at risk ${risk['total']:,.0f}")
    return {
        "state": st.state,
        "system": system,
        "since": st.since,
        "window_start": start.isoformat(),
        "window_end": st.effective_to.isoformat() if st.effective_to else None,
        "revenue_at_risk": risk["total"],
        "booked_value": risk["booked_value"],
        "affected_reservations": len(risk["reservations"]),
        "action": _STATE_ACTION[st.state],
        "message": message,
    }
