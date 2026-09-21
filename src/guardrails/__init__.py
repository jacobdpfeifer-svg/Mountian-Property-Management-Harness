"""Guardrails and the data-health-gated autonomy ladder.

The operator chose auto-push. The operator also chose scraper-first comp data.
That pairing is the reason this module exists: bad scrapers rarely crash, they
quietly return stale or partial data, and an auto-push loop reading a depressed
comp number will move real rates on real inventory before anyone sees a dashboard.

Two mechanisms:

1. HARD INVARIANTS (`apply_guardrails`) — max move %, absolute move cap, sanity
   floor, peak blackout. No autonomy level may override these. A recommendation
   that violates one is clamped, and one that violates a blackout is blocked.

2. DERIVED AUTONOMY (`assess_data_health`) — the ladder level is COMPUTED from
   data freshness/coverage each run, never configured per-run. Stale PMS data or
   thin comp coverage automatically demotes 'handle' (writes rates) to 'suggest'
   (queues for approval, writes nothing).

Ladder: watch < suggest < handle < escalate
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

LEVELS = ["watch", "suggest", "handle", "escalate"]


def _rank(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else 0


@dataclass
class DataHealth:
    granted_level: str
    pms_age_hours: float | None
    comp_age_hours: float | None
    comp_coverage: float
    pacing_days: int
    failures: list[str] = field(default_factory=list)
    scope_key: str = "portfolio"
    consecutive_failed_runs: int = 0
    grace_active: bool = False

    @property
    def can_push(self) -> bool:
        return self.granted_level == "handle"


@dataclass
class GuardrailVerdict:
    price: float
    blocked: bool
    action: str | None       # None = untouched
    detail: str | None = None


def _age_hours(text: str | None) -> float | None:
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return max(0.0, (datetime.now() - datetime.strptime(str(text)[:19], fmt)).total_seconds() / 3600.0)
        except ValueError:
            continue
    return None


def assess_data_health(
    conn: sqlite3.Connection,
    policy: dict[str, Any],
    property_ids: list[str] | None = None,
) -> DataHealth:
    cfg = policy.get("data_health", {})
    max_level = policy.get("autonomy", {}).get("max_level", "suggest")
    failures: list[str] = []
    scope_key = "portfolio" if not property_ids else "properties:" + ",".join(sorted(property_ids))

    prop_clause = ""
    prop_params: list[Any] = []
    if property_ids:
        placeholders = ",".join("?" for _ in property_ids)
        prop_clause = f" WHERE property_id IN ({placeholders})"
        prop_params = list(property_ids)
    row = conn.execute(
        f"SELECT MAX(updated_at) AS mx FROM nightly_inventory{prop_clause}", prop_params
    ).fetchone()
    pms_age = _age_hours(row["mx"] if row else None)
    if pms_age is None:
        failures.append("no PMS data timestamp")
    elif pms_age > float(cfg.get("pms_max_staleness_hours", 24)):
        failures.append(f"PMS data {pms_age:.0f}h old (max {cfg.get('pms_max_staleness_hours')}h)")
    try:
        sync = conn.execute(
            "SELECT status FROM sync_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if sync and sync["status"] in {"failed", "degraded", "running"}:
            failures.append(f"latest PMS sync status is {sync['status']}")
    except sqlite3.OperationalError:
        failures.append("PMS sync status unavailable")

    comp_clause = ""
    comp_params: list[Any] = []
    if property_ids:
        placeholders = ",".join("?" for _ in property_ids)
        comp_clause = (
            " AND comp_id IN (SELECT csm.comp_id FROM comp_set_members csm "
            f"WHERE csm.property_id IN ({placeholders}))"
        )
        comp_params = list(property_ids)
    row = conn.execute(
        "SELECT MAX(as_of) AS mx FROM comp_snapshots "
        "WHERE scrape_status = 'ok'" + comp_clause,
        comp_params,
    ).fetchone()
    comp_age = _age_hours(row["mx"] if row else None)
    if comp_age is None:
        failures.append("no comp snapshots")
    elif comp_age > float(cfg.get("comp_max_staleness_hours", 48)):
        failures.append(f"comp data {comp_age:.0f}h old (max {cfg.get('comp_max_staleness_hours')}h)")

    # Distinct comps on both sides. comp_set_members holds (property, comp) PAIRS, so
    # counting rows there compares pairs against comps and understates coverage.
    if property_ids:
        placeholders = ",".join("?" for _ in property_ids)
        members = conn.execute(
            f"SELECT COUNT(DISTINCT comp_id) AS c FROM comp_set_members "
            f"WHERE property_id IN ({placeholders})", property_ids,
        ).fetchone()["c"] or 0
    else:
        members = conn.execute(
            "SELECT COUNT(DISTINCT comp_id) AS c FROM comp_set_members"
        ).fetchone()["c"] or 0
    observed = conn.execute(
        "SELECT COUNT(DISTINCT comp_id) AS c FROM comp_snapshots "
        "WHERE listed_price IS NOT NULL AND scrape_status = 'ok'" + comp_clause,
        comp_params,
    ).fetchone()["c"] or 0
    coverage = (observed / members) if members else 0.0
    min_members = int(cfg.get("comp_min_members", 3))
    if members < min_members:
        failures.append(f"only {members} comp members (need {min_members})")
    if coverage < float(cfg.get("comp_min_coverage", 0.60)):
        failures.append(f"comp coverage {coverage:.0%} below {float(cfg.get('comp_min_coverage', 0.6)):.0%}")

    pacing_days = conn.execute(
        "SELECT COUNT(DISTINCT as_of) AS c FROM pacing_snapshots" + prop_clause,
        prop_params,
    ).fetchone()["c"] or 0
    if pacing_days < int(cfg.get("pacing_min_snapshot_days", 14)):
        failures.append(f"only {pacing_days}d of pacing history (need {cfg.get('pacing_min_snapshot_days')})")

    # Pfeifer Optimization: stale ACTIVE signals demote autonomy (SQI itself is not on the ladder).
    try:
        from datetime import date as _date

        from src.signals.promotion import signal_freshness_failures
        from src.signals.store import SignalStore

        failures.extend(signal_freshness_failures(SignalStore(conn), _date.today()))
    except Exception as exc:
        # A health check that cannot run is not healthy.  Swallowing this error
        # could accidentally leave a run at `handle` during a schema or signal
        # regression.
        failures.append(f"signal health unavailable: {type(exc).__name__}")

    if not failures:
        return DataHealth(max_level, pms_age, comp_age, coverage, int(pacing_days), [], scope_key)

    # Fail closed for a new scope, then tolerate only the configured number of
    # consecutive bad readings. Recovery is immediate; there is no re-arm grace.
    try:
        prior_rows = conn.execute(
            "SELECT failures FROM data_health_runs WHERE scope_key = ? "
            "ORDER BY rowid DESC LIMIT 100", (scope_key,)
        ).fetchall()
    except sqlite3.OperationalError:
        prior_rows = []
    consecutive = 0
    for prior in prior_rows:
        try:
            prior_failures = json.loads(prior["failures"] or "[]")
        except (TypeError, json.JSONDecodeError):
            prior_failures = ["unparseable prior health record"]
        if not prior_failures:
            break
        consecutive += 1
    consecutive += 1
    grace_runs = max(1, int(cfg.get("demotion_grace_runs", 2)))
    grace_active = bool(prior_rows) and consecutive < grace_runs
    granted = max_level if grace_active else "suggest"
    if grace_active:
        failures.append(
            f"health grace active: {consecutive}/{grace_runs} consecutive failed run(s); "
            "autonomy retained temporarily"
        )
    return DataHealth(
        granted, pms_age, comp_age, coverage, int(pacing_days), failures,
        scope_key, consecutive, grace_active,
    )


def record_health(conn: sqlite3.Connection, run_id: str, health: DataHealth) -> None:
    conn.execute(
        """
        INSERT INTO data_health_runs (run_id, pms_age_hours, comp_age_hours,
            comp_coverage, pacing_days, granted_level, failures, scope_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            pms_age_hours=excluded.pms_age_hours, comp_age_hours=excluded.comp_age_hours,
            comp_coverage=excluded.comp_coverage, pacing_days=excluded.pacing_days,
            granted_level=excluded.granted_level, failures=excluded.failures,
            scope_key=excluded.scope_key
        """,
        (run_id, health.pms_age_hours, health.comp_age_hours, health.comp_coverage,
        health.pacing_days, health.granted_level, json.dumps(health.failures), health.scope_key),
    )


def apply_guardrails(
    proposed: float,
    listed: float | None,
    anchor: float,
    demand_strength: float,
    policy: dict[str, Any],
) -> GuardrailVerdict:
    """Hard invariants. Applied to every recommendation regardless of autonomy."""
    g = policy.get("guardrails", {})

    # Sanity: a price far below the seasonal anchor is a bug, not a bid.
    min_ratio = float(g.get("sanity_min_ratio_to_anchor", 0.40))
    if anchor > 0 and proposed < anchor * min_ratio:
        return GuardrailVerdict(
            price=anchor * min_ratio, blocked=True, action="sanity_floor",
            detail=f"${proposed:.0f} is below {min_ratio:.0%} of the ${anchor:.0f} seasonal anchor",
        )

    blackout = float(g.get("auto_push_blackout_demand_strength", 0.85))
    is_blackout = demand_strength >= blackout

    # Move caps are applied BEFORE the blackout check. The blackout's job is "never
    # auto-push this night", not "skip the guardrails": a blocked recommendation is
    # still shown to a human, so the number they read must be inside the same bounds
    # as any other. Returning early on blackout displayed unclamped prices.
    price = proposed
    action: str | None = None
    detail: str | None = None

    if listed is not None and listed > 0:
        max_up = float(g.get("max_increase_pct", 0.12))
        max_dn = float(g.get("max_decrease_pct", 0.15))
        max_abs = float(g.get("max_abs_move", 250))
        upper = min(listed * (1 + max_up), listed + max_abs)
        lower = max(listed * (1 - max_dn), listed - max_abs)
        if proposed > upper:
            price, action = upper, "clamped_increase"
            detail = f"capped +{max_up:.0%}/${max_abs:.0f}: ${proposed:.0f} -> ${upper:.0f}"
        elif proposed < lower:
            price, action = lower, "clamped_decrease"
            detail = f"capped -{max_dn:.0%}/${max_abs:.0f}: ${proposed:.0f} -> ${lower:.0f}"

    if is_blackout:
        note = f"demand {demand_strength:.2f} >= {blackout:.2f} - requires human approval"
        return GuardrailVerdict(
            price=price, blocked=True, action="peak_blackout",
            detail=f"{note}{'; ' + detail if detail else ''}",
        )
    return GuardrailVerdict(price=price, blocked=False, action=action, detail=detail)


def limit_run_scope(recs: list[Any], open_nights: int, policy: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    """Cap how much of the calendar a single run may move.

    Returns (pushable, withheld). Largest moves are withheld first: a run that wants
    to change more of the calendar than allowed is more likely to be a data fault
    than an opportunity, so the biggest swings are the ones a human should see.
    """
    g = policy.get("guardrails", {})
    max_n = int(g.get("max_nights_changed_per_run", 40))
    max_pct = float(g.get("max_pct_of_open_nights_per_run", 0.35))
    allowed = min(max_n, int(open_nights * max_pct)) if open_nights else max_n
    changed = [r for r in recs if r.listed_price_at_run is not None
               and abs(r.recommended_price - r.listed_price_at_run) >= 1.0]
    if len(changed) <= allowed:
        return changed, []
    changed.sort(key=lambda r: abs(r.recommended_price - r.listed_price_at_run))
    return changed[:allowed], changed[allowed:]
