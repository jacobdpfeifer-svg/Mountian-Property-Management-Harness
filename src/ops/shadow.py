"""Phase 1 shadow report: what does servicing the calendar cost, and what would
the current min-stay settings add? Reads only; writes nothing to pricing.

Min-stay counterfactual: for each open window of W consecutive available nights,
a min-stay of L allows at most floor(W / L) stays, and every stay adds one turn.
The report compares the PMS min-stay, the engine's latest recommended min-stay,
and each candidate length. It is a worst case (window fully sold with shortest
stays), and is labelled as such.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from src.ops import OpsProfile
from src.ops.economics import (
    capacity_view,
    observed_readiness,
    ready_probability,
    turn_cost,
)
from src.ops.profiles import load_ops_config, load_ops_policy, load_profiles
from src.ops.readiness import current_state
from src.ops.turns import Turn, derive_turns
from src.utils import parse_date


@dataclass
class OpenWindow:
    property_id: str
    start: date
    nights: int
    pms_min_stay: int | None
    recommended_min_stay: int | None


@dataclass
class OpsReport:
    as_of: date
    start: date
    end: date
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    turns: list[dict[str, Any]] = field(default_factory=list)
    capacity: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, dict[str, Any]] = field(default_factory=dict)
    min_stay: list[dict[str, Any]] = field(default_factory=list)
    readiness: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(), "start": self.start.isoformat(),
            "end": self.end.isoformat(), "profiles": self.profiles, "turns": self.turns,
            "capacity": self.capacity, "summary": self.summary, "min_stay": self.min_stay,
            "readiness": self.readiness, "notes": self.notes,
        }


def open_windows(conn: sqlite3.Connection, property_id: str, start: date, end: date) -> list[OpenWindow]:
    rows = conn.execute(
        """SELECT stay_date, status, min_stay FROM nightly_inventory
           WHERE property_id=? AND stay_date>=? AND stay_date<=? ORDER BY stay_date""",
        (property_id, start.isoformat(), end.isoformat()),
    ).fetchall()
    rec = {
        str(r["stay_date"]): r["recommended_min_stay"]
        for r in conn.execute(
            """SELECT p.stay_date, p.recommended_min_stay FROM price_recommendations p
               JOIN (SELECT stay_date, MAX(id) AS id FROM price_recommendations
                     WHERE property_id=? AND stay_date>=? AND stay_date<=? GROUP BY stay_date) l
                 ON l.id = p.id""",
            (property_id, start.isoformat(), end.isoformat()),
        ).fetchall()
    }
    windows: list[OpenWindow] = []
    run: list[sqlite3.Row] = []

    def flush() -> None:
        if not run:
            return
        pms = [int(r["min_stay"]) for r in run if r["min_stay"]]
        recs = [int(rec[str(r["stay_date"])]) for r in run if rec.get(str(r["stay_date"]))]
        windows.append(OpenWindow(property_id, parse_date(run[0]["stay_date"]), len(run),
                                  min(pms) if pms else None, min(recs) if recs else None))
        run.clear()

    prev: date | None = None
    for r in rows:
        d = parse_date(r["stay_date"])
        if r["status"] != "available" or (prev is not None and d != prev + timedelta(days=1)):
            flush()
        if r["status"] == "available":
            run.append(r)
        prev = d
    flush()
    return windows


def _max_turns(nights: int, min_stay: int | None) -> int | None:
    if not min_stay or min_stay <= 0:
        return None
    return nights // int(min_stay)


def build_report(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    *,
    as_of: date | None = None,
    property_ids: list[str] | None = None,
    policy: dict[str, Any] | None = None,
) -> OpsReport:
    as_of = as_of or date.today()
    ops_policy = load_ops_policy()
    ops_cfg = load_ops_config()
    profiles = load_profiles()
    if property_ids:
        profiles = {pid: p for pid, p in profiles.items() if pid in property_ids}
    report = OpsReport(as_of=as_of, start=start, end=end)
    observed = observed_readiness(conn, profiles, as_of, ops_policy)
    all_turns: list[Turn] = []
    candidates = _candidate_lengths(policy)
    for pid, profile in profiles.items():
        report.profiles[pid] = {"version": profile.version, "basis": profile.basis,
                                "worker_minutes": profile.worker_minutes(),
                                "elapsed_minutes": round(profile.elapsed_minutes(), 1)}
        turns = derive_turns(conn, profile, start, end, as_of=as_of, ops_policy=ops_policy)
        all_turns.extend(turns)
        costs: list[float] = []
        low_ready = 0
        for t in turns:
            cost = turn_cost(conn, profile, as_of=as_of, ops_policy=ops_policy, snow=t.snow_expected)
            ready = ready_probability(t.slack_minutes, ops_policy, observed)
            costs.append(cost.amount)
            min_p = float((ops_policy.get("stay") or {}).get("min_p_ready", 0.6))
            if t.arriving_reservation and ready.p < min_p:
                low_ready += 1
            report.turns.append({**t.as_dict(), "cost": cost.as_dict(), "ready": ready.as_dict()})
        base_cost = turn_cost(conn, profile, as_of=as_of, ops_policy=ops_policy)
        report.summary[pid] = {
            "turns": len(turns),
            "same_day": sum(1 for t in turns if t.same_day),
            "service_cost": round(sum(costs), 2),
            "cost_basis": base_cost.basis,
            "observed_turns": base_cost.n,
            "low_readiness_turns": low_ready,
        }
        report.readiness[pid] = current_state(conn, pid, as_of).as_dict()
        report.min_stay.extend(_min_stay_rows(conn, profile, start, end, base_cost.amount,
                                              candidates))
    zones = sorted({p.access_zone for p in profiles.values()})
    d = start
    while d <= end:
        for zone in zones:
            view = capacity_view(conn, zone, d, as_of=as_of, ops_cfg=ops_cfg,
                                 profiles=profiles, turns=all_turns)
            if view.turns:
                row = view.as_dict()
                u = view.utilization
                cap = ops_policy.get("capacity") or {}
                row["flag"] = (
                    "unknown" if u is None else
                    "critical" if u >= float(cap.get("critical_utilization", 1.0)) else
                    "warn" if u >= float(cap.get("warn_utilization", 0.85)) else "ok"
                )
                report.capacity.append(row)
        d += timedelta(days=1)
    if any(p.basis == "estimate" for p in profiles.values()):
        report.notes.append("Some profiles are estimates (config/operations/mont_luxe.yaml); "
                            "costs are labelled with their basis.")
    if any(r["available_source"] == "roster" for r in report.capacity):
        report.notes.append("Capacity from the roster counts a multi-zone crew in each zone; "
                            "utilization is optimistic until capacity is imported.")
    report.notes.append("Min-stay turn counts are worst case: each open window fully sold "
                        "with the shortest allowed stays.")
    return report


def _candidate_lengths(policy: dict[str, Any] | None) -> list[int]:
    if policy is None:
        from src.config import load_policy

        policy = load_policy()
    rules = (policy.get("min_stay_rules") or {}).get("by_season") or {}
    found = {int(r["min_nights"]) for rows in rules.values() for r in rows or []}
    found.add(1)
    return sorted(found)


def _min_stay_rows(conn: sqlite3.Connection, profile: OpsProfile, start: date, end: date,
                   unit_cost: float, candidates: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for w in open_windows(conn, profile.property_id, start, end):
        pms_turns = _max_turns(w.nights, w.pms_min_stay)
        rec_turns = _max_turns(w.nights, w.recommended_min_stay)
        extra = None if pms_turns is None or rec_turns is None else rec_turns - pms_turns
        rows.append({
            "property_id": w.property_id,
            "window_start": w.start.isoformat(),
            "nights": w.nights,
            "pms_min_stay": w.pms_min_stay,
            "recommended_min_stay": w.recommended_min_stay,
            "max_turns_pms": pms_turns,
            "max_turns_recommended": rec_turns,
            "extra_turns_recommended": extra,
            "extra_cost_recommended": None if extra is None else round(extra * unit_cost, 2),
            "by_candidate": {
                str(L): {"max_turns": w.nights // L, "service_cost": round((w.nights // L) * unit_cost, 2)}
                for L in candidates if L <= w.nights
            },
        })
    return rows


def render_text(report: OpsReport) -> str:
    lines = [f"Operations report {report.start} → {report.end} (as of {report.as_of})", ""]
    for pid, s in report.summary.items():
        prof = report.profiles[pid]
        state = report.readiness.get(pid, {}).get("state", "ready")
        lines.append(
            f"{pid}: {s['turns']} turn(s), {s['same_day']} same-day, service ${s['service_cost']:,.0f} "
            f"[{s['cost_basis']}, n={s['observed_turns']}], low-readiness {s['low_readiness_turns']}, "
            f"profile {prof['version']} ({prof['basis']}), readiness {state}"
        )
    if report.turns:
        lines += ["", "Turns:"]
        for t in report.turns:
            slack = "open" if t["slack_minutes"] is None else f"{t['slack_minutes']:.0f}m"
            buf = f" +{t['weather_buffer_minutes']:.0f}m weather" if t["weather_buffer_minutes"] else ""
            lines.append(
                f"  {t['service_date']} {t['property_id']:<15} gap={t['gap_nights']!s:<4} "
                f"slack={slack:<7} P(ready)={t['ready']['p']:.2f} cost=${t['cost']['amount']:,.0f}"
                f"{' SAME-DAY' if t['same_day'] else ''}{buf}"
            )
    hot = [c for c in report.capacity if c["flag"] in ("warn", "critical", "unknown")]
    if hot:
        lines += ["", "Capacity pressure:"]
        for c in hot:
            u = "?" if c["utilization"] is None else f"{c['utilization']:.0%}"
            lines.append(f"  {c['service_date']} {c['access_zone']}: {u} of "
                         f"{c['available_worker_minutes']:.0f} worker-min [{c['flag']}]")
    extra = [m for m in report.min_stay if (m["extra_turns_recommended"] or 0) > 0]
    if report.min_stay:
        lines += ["", "Min-stay counterfactuals (worst case):"]
        for m in report.min_stay:
            cand = ", ".join(f"{k}n→{v['max_turns']} turns ${v['service_cost']:,.0f}"
                             for k, v in m["by_candidate"].items())
            lines.append(f"  {m['property_id']} {m['window_start']} ({m['nights']}n) "
                         f"PMS min {m['pms_min_stay']} rec {m['recommended_min_stay']}: {cand}")
        if extra:
            total = sum(m["extra_cost_recommended"] or 0 for m in extra)
            lines.append(f"  Engine recommendations add up to {sum(m['extra_turns_recommended'] for m in extra)} "
                         f"turn(s) (${total:,.0f}) versus PMS settings.")
    if report.notes:
        lines += ["", *[f"note: {n}" for n in report.notes]]
    return "\n".join(lines)


def capacity_by_date(report: OpsReport) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in report.capacity:
        out[c["service_date"]].append(c)
    return dict(out)
