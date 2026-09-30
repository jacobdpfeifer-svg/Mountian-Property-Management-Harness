"""Turn cost, readiness probability, and crew capacity.

All reads are point-in-time: outcomes are only counted when their service date is
before `as_of`, capacity snapshots only when observed by `as_of`. Every number
carries its basis (estimate vs observed) and sample size.
"""

from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from src.ops import OpsProfile
from src.ops.turns import Turn, build_turn, derive_turns


@dataclass(frozen=True)
class CostEstimate:
    amount: float
    basis: str  # estimate | observed
    n: int

    def as_dict(self) -> dict[str, Any]:
        return {"amount": self.amount, "basis": self.basis, "n": self.n}


@dataclass(frozen=True)
class ReadyEstimate:
    p: float
    prior: float
    on_time: int
    n: int
    bucket_max_slack: float | None

    def as_dict(self) -> dict[str, Any]:
        return {"p": round(self.p, 3), "prior": self.prior, "on_time": self.on_time,
                "n": self.n, "bucket_max_slack": self.bucket_max_slack}


@dataclass(frozen=True)
class CapacityView:
    service_date: date
    access_zone: str
    available_worker_minutes: float
    committed_worker_minutes: float
    available_source: str
    committed_source: str
    turns: int

    @property
    def utilization(self) -> float | None:
        if self.available_worker_minutes <= 0:
            return None
        return self.committed_worker_minutes / self.available_worker_minutes

    def as_dict(self) -> dict[str, Any]:
        u = self.utilization
        return {
            "service_date": self.service_date.isoformat(),
            "access_zone": self.access_zone,
            "available_worker_minutes": round(self.available_worker_minutes, 1),
            "committed_worker_minutes": round(self.committed_worker_minutes, 1),
            "utilization": None if u is None else round(u, 3),
            "available_source": self.available_source,
            "committed_source": self.committed_source,
            "turns": self.turns,
        }


# ------------------------------------------------------------------- cost

def observed_costs(conn: sqlite3.Connection, property_id: str, as_of: date) -> list[float]:
    rows = conn.execute(
        """SELECT cost FROM turnover_outcomes
           WHERE property_id=? AND service_type='turnover' AND cost IS NOT NULL
             AND service_date < ?""",
        (property_id, as_of.isoformat()),
    ).fetchall()
    return [float(r["cost"]) for r in rows]


def turn_cost(
    conn: sqlite3.Connection,
    profile: OpsProfile,
    *,
    as_of: date,
    ops_policy: dict[str, Any],
    snow: bool = False,
) -> CostEstimate:
    """Median observed turnover cost once there are enough turns, else the profile build-up."""
    min_n = int((ops_policy.get("economics") or {}).get("min_observed_turns", 5))
    costs = observed_costs(conn, profile.property_id, as_of)
    if len(costs) >= min_n:
        amount = float(statistics.median(costs))
        if snow and profile.snow_clearance_required:
            amount += profile.snow_cost_per_visit
        return CostEstimate(round(amount, 2), "observed", len(costs))
    return CostEstimate(profile.estimated_cost(snow=snow), "estimate", len(costs))


# ------------------------------------------------------ ready probability

def _buckets(ops_policy: dict[str, Any]) -> list[dict[str, Any]]:
    rp = ops_policy.get("ready_probability") or {}
    buckets = rp.get("buckets") or [{"max_slack": None, "prior": 0.9}]
    return list(buckets)


def bucket_for(slack: float | None, ops_policy: dict[str, Any]) -> dict[str, Any]:
    buckets = _buckets(ops_policy)
    if slack is None:
        return buckets[-1]
    for b in buckets:
        if b.get("max_slack") is None or slack <= float(b["max_slack"]):
            return b
    return buckets[-1]


def observed_readiness(
    conn: sqlite3.Connection,
    profiles: dict[str, OpsProfile],
    as_of: date,
    ops_policy: dict[str, Any],
    *,
    lookback_days: int = 730,
) -> dict[float | None, tuple[int, int]]:
    """Pooled (on_time, n) per slack bucket from past turns with a readiness outcome.

    An outcome joins a derived turn by turn_id, else by (property, service date).
    On time means late_ready_minutes <= 0.
    """
    tally: dict[float | None, list[int]] = {}
    start = as_of - timedelta(days=lookback_days)
    end = as_of - timedelta(days=1)
    for profile in profiles.values():
        rows = conn.execute(
            """SELECT turn_id, service_date, late_ready_minutes FROM turnover_outcomes
               WHERE property_id=? AND service_type='turnover'
                 AND late_ready_minutes IS NOT NULL AND service_date >= ? AND service_date < ?""",
            (profile.property_id, start.isoformat(), as_of.isoformat()),
        ).fetchall()
        if not rows:
            continue
        turns = derive_turns(conn, profile, start, end, as_of=as_of, ops_policy=ops_policy)
        by_id = {t.turn_id: t for t in turns}
        by_date = {t.service_date.isoformat(): t for t in turns}
        for r in rows:
            turn = by_id.get(r["turn_id"] or "") or by_date.get(str(r["service_date"])[:10])
            if turn is None:
                continue
            key = bucket_for(turn.slack_minutes, ops_policy).get("max_slack")
            cell = tally.setdefault(key, [0, 0])
            cell[0] += int(float(r["late_ready_minutes"]) <= 0)
            cell[1] += 1
    return {k: (v[0], v[1]) for k, v in tally.items()}


def ready_probability(
    slack: float | None,
    ops_policy: dict[str, Any],
    observed: dict[float | None, tuple[int, int]] | None = None,
) -> ReadyEstimate:
    """Beta-shrunk on-time rate for the slack bucket."""
    bucket = bucket_for(slack, ops_policy)
    prior = float(bucket.get("prior", 0.9))
    k = float((ops_policy.get("ready_probability") or {}).get("prior_strength", 10))
    on_time, n = (observed or {}).get(bucket.get("max_slack"), (0, 0))
    p = (k * prior + on_time) / (k + n) if (k + n) > 0 else prior
    return ReadyEstimate(p=p, prior=prior, on_time=on_time, n=n,
                         bucket_max_slack=bucket.get("max_slack"))


# ---------------------------------------------------------------- capacity

def roster_minutes(ops_cfg: dict[str, Any], zone: str, service_date: date) -> float | None:
    cap = ops_cfg.get("capacity") or {}
    for o in cap.get("overrides") or []:
        if str(o.get("date")) == service_date.isoformat() and o.get("zone") == zone:
            return float(o["available_worker_minutes"])
    crews = [c for c in cap.get("crews") or [] if zone in (c.get("zones") or [])]
    if not crews:
        return None
    # A crew serving several zones is counted in each; utilization is then an
    # upper bound on slack, not a schedule. The report says so.
    total = 0.0
    for c in crews:
        if service_date.weekday() in (c.get("weekdays") or range(7)):
            total += float(c.get("workers", 0)) * float(c.get("minutes_per_worker", 0))
    return total


def _imported_capacity(
    conn: sqlite3.Connection, zone: str, service_date: date, as_of: date
) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM operations_capacity_snapshots
           WHERE access_zone=? AND service_date=? AND as_of<=? AND service_type='turnover'
           ORDER BY as_of DESC, CASE WHEN source='manual' THEN 1 ELSE 0 END LIMIT 1""",
        (zone, service_date.isoformat(), as_of.isoformat()),
    ).fetchone()


def turn_load_minutes(turn: Turn, profile: OpsProfile) -> float:
    """Worker-minutes a turn consumes, including every worker's travel."""
    return turn.predicted_worker_minutes + turn.travel_minutes * max(1, profile.crew_size)


def capacity_view(
    conn: sqlite3.Connection,
    zone: str,
    service_date: date,
    *,
    as_of: date,
    ops_cfg: dict[str, Any],
    profiles: dict[str, OpsProfile],
    turns: list[Turn],
) -> CapacityView:
    zone_profiles = {pid: p for pid, p in profiles.items() if p.access_zone == zone}
    day_turns = [t for t in turns if t.service_date == service_date and t.property_id in zone_profiles]
    derived = sum(turn_load_minutes(t, zone_profiles[t.property_id]) for t in day_turns)
    imported = _imported_capacity(conn, zone, service_date, as_of)
    if imported is not None:
        available = float(imported["available_worker_minutes"])
        available_src = str(imported["source"])
        committed = max(float(imported["committed_worker_minutes"] or 0.0), derived)
        committed_src = f"max({available_src}, derived_turns)"
    else:
        available = roster_minutes(ops_cfg, zone, service_date) or 0.0
        available_src = "roster"
        committed = derived
        committed_src = "derived_turns"
    return CapacityView(service_date, zone, available, committed, available_src,
                        committed_src, len(day_turns))


def hypothetical_turn(profile: OpsProfile, service_date: date, gap_nights: int | None) -> Turn:
    return build_turn(profile, service_date=service_date, departing="hypothetical",
                      arriving=None if gap_nights is None else "hypothetical_next",
                      gap_nights=gap_nights)
