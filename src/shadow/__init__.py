"""Read-only daily shadow mode (workstream 6).

Each day, for each home, the latest engine recommendation for every upcoming night
goes into the review queue beside the rate Guesty currently shows, the day's data
health, and the engine's reasons; the same decision is appended to the spine as a
`price_decision` with `autonomy_level=observe`. People approve, reject or edit in
the review queue (src/review) — those decisions are recorded, never applied.
After a night passes, `capture_outcomes` records what really happened to it.

Write safety: this module holds no PMS client. `run_shadow_day` refuses to run on
a database that has ever applied a Guesty rate, and the `shadow_run.rate_writes`
column is constrained to 0.

`scorecard` summarises shadow evidence for the canary gate (src/gates).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

from src.data_spine.ingest import ingest
from src.eval.shadow import GuestyWriteForbidden, guesty_write_count
from src.review import ReviewItem, enqueue

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ShadowDay:
    as_of: str
    property_id: str
    nights: int
    queued: int
    health_level: str
    anchored_share: float | None
    stale: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _reasons(raw: str | None) -> list[str]:
    try:
        items = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return [str(raw)]
    out = []
    for r in items:
        if isinstance(r, dict):
            out.append(str(r.get("text") or r.get("detail") or r.get("code") or r))
        else:
            out.append(str(r))
    return out


def run_shadow_day(conn: sqlite3.Connection, *, as_of: date, property_id: str, health: Any,
                   policy_sha256: str, code_sha256: str, horizon_days: int = 120,
                   scope: frozenset[str], review_hours: int = 20,
                   arm_for: Any = None, max_rec_age_days: int = 0) -> ShadowDay:
    """Queue today's recommendations for one home. Writes only local, append-only rows.

    `health` is the DataHealth for this home today (src.guardrails.assess_data_health).
    `arm_for(property_id, stay_date) -> str` labels field-test assignment when a
    preregistered field test is active; otherwise every night is `not_assigned`.
    A recommendation made more than `max_rec_age_days` before `as_of` is not
    queued (a reviewer must never approve a stale price as today's); the count
    is returned as `stale`.
    """
    writes = guesty_write_count(conn)
    if writes:
        raise GuestyWriteForbidden(f"shadow refused: {writes} Guesty write(s) recorded in this database")
    # The engine stamps created_at in UTC (datetime('now')); shadow days are local
    # (America/Denver), so both sides are compared as local dates.
    if conn.execute("SELECT 1 FROM shadow_run WHERE as_of = ? AND property_id = ?",
                    (as_of.isoformat(), property_id)).fetchone():
        raise sqlite3.IntegrityError(f"shadow day {as_of} for {property_id} already recorded")
    end = as_of + timedelta(days=horizon_days)
    rows = conn.execute(
        """
        SELECT i.stay_date, i.listed_price, i.status, r.run_id, r.recommended_price, r.reasons,
               date(r.created_at, 'localtime') AS rec_day,
               r.guardrail_action, r.ceiling_confidence, r.expected_book_prob, r.model_version,
               r.inputs_hash
        FROM nightly_inventory i
        JOIN price_recommendations r ON r.id = (
            SELECT p.id FROM price_recommendations p
            WHERE p.property_id = i.property_id AND p.stay_date = i.stay_date
              AND date(p.created_at, 'localtime') <= ?
            ORDER BY p.created_at DESC, p.id DESC LIMIT 1)
        WHERE i.property_id = ? AND i.stay_date > ? AND i.stay_date <= ? AND i.status = 'available'
        ORDER BY i.stay_date
        """, (as_of.isoformat(), property_id, as_of.isoformat(), end.isoformat())).fetchall()
    now = _now()
    expires = (now + timedelta(hours=review_hours)).isoformat(timespec="seconds")
    freshness = {"pms_age_hours": f"{health.pms_age_hours}", "comp_age_hours": f"{health.comp_age_hours}",
                 "comp_coverage": f"{health.comp_coverage:.2f}", "health_level": health.granted_level}
    oldest_ok = (as_of - timedelta(days=max_rec_age_days)).isoformat()
    stale = sum(1 for r in rows if r["rec_day"] < oldest_ok)
    rows = [r for r in rows if r["rec_day"] >= oldest_ok]
    anchored = 0
    decisions = []
    queued = 0
    for r in rows:
        reasons = _reasons(r["reasons"])
        if any("comp median of" in x for x in reasons):
            anchored += 1
        key = f"shadow:{as_of.isoformat()}:{property_id}:{r['stay_date']}"
        enqueue(conn, ReviewItem(
            decision_key=key, property_id=property_id, stay_date=r["stay_date"],
            current_rate=r["listed_price"], proposed_rate=float(r["recommended_price"]),
            all_in_price=None, expected_owner_net=None, owner_net_basis="assumed_terms",
            freshness=freshness, confidence=r["ceiling_confidence"], reasons=reasons,
            guardrails=[r["guardrail_action"]] if r["guardrail_action"] else [],
            readiness="data_blocked" if health.failures else "shadow_only",
            assignment_arm=(arm_for(property_id, r["stay_date"]) if arm_for else "not_assigned"),
            expires_at=expires), scope_property_ids=scope)
        queued += 1
        decisions.append({
            "source_system": "wp_price_shadow", "source_record_id": key,
            "source_updated_at": now.isoformat(timespec="seconds"),
            "observed_at": now.isoformat(timespec="seconds"),
            "decision_key": key, "property_id": property_id, "stay_date": r["stay_date"],
            "run_id": r["run_id"], "policy_hash": policy_sha256, "calibration_hash": None,
            "data_hash": r["inputs_hash"], "model_version": r["model_version"],
            "price_basis": "nightly_ex_fees", "currency": "USD",
            "current_price": r["listed_price"], "recommended_price": float(r["recommended_price"]),
            "human_decision": "pending", "autonomy_level": "observe",
        })
    if decisions:
        res = ingest(conn, "price_decision", decisions, allowed_property_ids=scope)
        if res.quarantined:
            raise RuntimeError(f"shadow decisions quarantined: {res.quarantined[:3]}")
    share = round(anchored / len(rows), 4) if rows else None
    with conn:
        conn.execute(
            """INSERT INTO shadow_run (as_of, property_id, nights, health_level, health_json,
                   anchored_share, rate_writes, code_sha256, policy_sha256, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
            (as_of.isoformat(), property_id, len(rows), health.granted_level,
             json.dumps(asdict(health), sort_keys=True, default=str), share, code_sha256,
             policy_sha256, now.isoformat(timespec="seconds")))
    return ShadowDay(as_of.isoformat(), property_id, len(rows), queued, health.granted_level, share, stale)


def capture_outcomes(conn: sqlite3.Connection, *, as_of: date) -> int:
    """Record what happened to every shadow night that has now passed. Idempotent."""
    pending = conn.execute(
        """SELECT ri.decision_key, ri.property_id, ri.stay_date FROM review_item ri
           WHERE ri.decision_key LIKE 'shadow:%' AND ri.stay_date < ?
             AND NOT EXISTS (SELECT 1 FROM shadow_outcome o WHERE o.decision_key = ri.decision_key)""",
        (as_of.isoformat(),)).fetchall()
    n = 0
    now = _now().isoformat(timespec="seconds")
    with conn:
        for p in pending:
            inv = conn.execute("SELECT status, booked_price, reservation_id FROM nightly_inventory "
                               "WHERE property_id=? AND stay_date=?", (p["property_id"], p["stay_date"])).fetchone()
            status = inv["status"] if inv else "unknown"
            res_key = f"guesty:{inv['reservation_id']}" if inv and inv["reservation_id"] else None
            net_status = None
            if res_key:
                from src.data_spine.owner_net import owner_net_for_reservation
                try:
                    net_status = owner_net_for_reservation(conn, res_key).status
                except Exception:   # spine row absent for this stay: not an outcome failure
                    net_status = "not_in_spine"
            conn.execute(
                """INSERT INTO shadow_outcome (decision_key, stay_date, captured_at, night_status,
                       sold_price, reservation_key, owner_net_status) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (p["decision_key"], p["stay_date"], now, status,
                 inv["booked_price"] if inv and status == "booked" else None, res_key, net_status))
            n += 1
    return n


def scorecard(conn: sqlite3.Connection, *, since: date | None = None,
              property_id: str | None = None) -> dict[str, Any]:
    """Shadow evidence for the canary gate, for one home or the portfolio. Pure read."""
    clauses, params = [], []
    if since:
        clauses.append("as_of >= ?")
        params.append(since.isoformat())
    if property_id:
        clauses.append("property_id = ?")
        params.append(property_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    runs = conn.execute(f"SELECT * FROM shadow_run {where} ORDER BY as_of", params).fetchall()
    days = sorted({r["as_of"] for r in runs})
    longest = streak = 0
    prev: date | None = None
    for d in (date.fromisoformat(x) for x in days):
        streak = streak + 1 if prev and (d - prev).days == 1 else 1
        longest, prev = max(longest, streak), d
    # Healthy = every data-health gate passed that day (a failing gate demotes to
    # "suggest", so the granted level alone cannot tell).
    healthy = [r for r in runs if not json.loads(r["health_json"]).get("failures")]
    items = conn.execute(
        """SELECT ri.proposed_rate, ri.current_rate, ra.action, ra.decided_price
           FROM review_item ri LEFT JOIN review_action ra ON ra.item_id = ri.id
           WHERE ri.decision_key LIKE 'shadow:%' AND (? IS NULL OR ri.property_id = ?)""",
        (property_id, property_id)).fetchall()
    decided = [i for i in items if i["action"]]
    moves = [abs(i["proposed_rate"] / i["current_rate"] - 1) for i in items if i["current_rate"]]
    outcomes = conn.execute("SELECT night_status, COUNT(*) c FROM shadow_outcome GROUP BY 1").fetchall()
    return {
        "shadow_days": len(days), "longest_daily_streak": longest,
        "runs": len(runs), "healthy_run_share": round(len(healthy) / len(runs), 4) if runs else 0.0,
        "anchored_share_median": (round(median([r["anchored_share"] for r in runs if r["anchored_share"] is not None]), 4)
                                  if any(r["anchored_share"] is not None for r in runs) else None),
        "rate_writes": sum(int(r["rate_writes"]) for r in runs),
        "items": len(items), "reviewed_share": round(len(decided) / len(items), 4) if items else 0.0,
        "approved_share_of_reviewed": (round(sum(i["action"] == "approve" for i in decided) / len(decided), 4)
                                       if decided else None),
        "median_abs_move_vs_current": round(median(moves), 4) if moves else None,
        "outcomes": {o["night_status"]: o["c"] for o in outcomes},
    }


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
