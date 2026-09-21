"""Post-run audit — data health, guardrails, and known regression checks."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.config import load_policy
from src.guardrails import assess_data_health


@dataclass
class AuditCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class AuditReport:
    checks: list[AuditCheck] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append(AuditCheck(name, passed, detail))


def _range_days(start: date, end: date) -> int:
    return (end - start).days + 1


def _is_direct_book(row: sqlite3.Row | None) -> bool:
    if row is None:
        return False
    return bool(row["pms_listing_id"]) and not row["airbnb_room_id"]


def _move_cap_band(listed: float, g: dict[str, Any]) -> tuple[float, float]:
    max_up = float(g.get("max_increase_pct", 0.12))
    max_dn = float(g.get("max_decrease_pct", 0.15))
    max_abs = float(g.get("max_abs_move", 250))
    upper = min(listed * (1 + max_up), listed + max_abs)
    lower = max(listed * (1 - max_dn), listed - max_abs)
    return lower, upper


def _within_effective_bounds(r: sqlite3.Row, g: dict[str, Any]) -> bool:
    rec = float(r["recommended_price"])
    floor = float(r["floor_price"] or 0)
    action = r["guardrail_action"] or ""
    listed = r["listed_price_at_run"]

    if rec < floor - 0.01:
        return False

    if action.startswith("sanity_floor"):
        return True

    if listed is not None and listed > 0:
        lower, upper = _move_cap_band(float(listed), g)
        if action in ("clamped_increase", "clamped_decrease", "peak_blackout"):
            return lower - 0.01 <= rec <= upper + 0.01
        if not action and (rec > upper + 0.01 or rec < lower - 0.01):
            return False

    ceil = float(r["ceiling_price"] or 1e9)
    if action in ("clamped_decrease", "clamped_increase", "peak_blackout"):
        return True
    return rec <= ceil + 0.01


def _listed_similar(a: float, b: float, max_pct: float) -> bool:
    base = max(a, b)
    if base <= 0:
        return False
    return abs(a - b) / base <= max_pct


def run_audit(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    property_ids: list[str] | None = None,
    policy: dict[str, Any] | None = None,
) -> AuditReport:
    policy = policy or load_policy()
    report = AuditReport()
    props = property_ids or [
        r["property_id"]
        for r in conn.execute("SELECT property_id FROM properties ORDER BY property_id").fetchall()
    ]
    g = policy.get("guardrails", {})
    acfg = policy.get("audit", {})
    twin_listed_max_pct = float(acfg.get("twin_listed_max_pct", 0.15))
    twin_max_delta = float(acfg.get("twin_max_delta", 50))
    range_days = _range_days(start, end)
    min_demand = max(1, range_days // 3)

    # --- data completeness ---
    for pid in props:
        row = conn.execute(
            "SELECT airbnb_room_id, pms_listing_id FROM properties WHERE property_id = ?",
            (pid,),
        ).fetchone()
        if row and row["airbnb_room_id"]:
            report.add(
                f"room_id:{pid}",
                True,
                f"airbnb_room_id={row['airbnb_room_id']}",
            )
        elif _is_direct_book(row):
            report.add(
                f"room_id:{pid}",
                True,
                "direct-book via Guesty (no Airbnb room id)",
            )
        else:
            report.add(
                f"room_id:{pid}",
                False,
                f"airbnb_room_id={row['airbnb_room_id'] if row else None}",
            )

    for pid in props:
        inv = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) AS avail,
                   SUM(CASE WHEN listed_price IS NOT NULL THEN 1 ELSE 0 END) AS priced
            FROM nightly_inventory
            WHERE property_id = ? AND stay_date >= ? AND stay_date <= ?
            """,
            (pid, start.isoformat(), end.isoformat()),
        ).fetchone()
        total = int(inv["total"] or 0)
        avail = int(inv["avail"] or 0)
        priced = int(inv["priced"] or 0)
        report.add(
            f"inventory:{pid}",
            total >= range_days,
            f"{total}/{range_days} nights, {avail} available, {priced} with price",
        )

    health = assess_data_health(conn, policy, property_ids=props)
    report.summary["autonomy"] = health.granted_level
    report.summary["health_failures"] = health.failures
    report.add(
        "comp_coverage",
        health.comp_coverage >= float(policy.get("data_health", {}).get("comp_min_coverage", 0.6)),
        f"{health.comp_coverage:.0%} (failures: {health.failures})",
    )

    scrape = conn.execute(
        "SELECT status, windows_ok, windows_attempted, comps_matched, comps_expected "
        "FROM comp_scrape_runs WHERE status != 'running' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if scrape:
        report.add(
            "comp_scrape_status",
            scrape["status"] == "ok",
            f"status={scrape['status']} windows={scrape['windows_ok']}/{scrape['windows_attempted']}",
        )

    demand = conn.execute(
        "SELECT COUNT(*) c FROM demand_signals WHERE signal_date >= ? AND signal_date <= ?",
        (start.isoformat(), end.isoformat()),
    ).fetchone()["c"]
    demand_count = int(demand or 0)
    report.add(
        "demand_signals",
        demand_count >= min_demand,
        f"{demand_count}/{min_demand} rows in range",
    )

    # --- recommendation invariants ---
    sql = """
        SELECT * FROM price_recommendations
        WHERE stay_date >= ? AND stay_date <= ?
    """
    params: list[object] = [start.isoformat(), end.isoformat()]
    if props:
        sql += f" AND property_id IN ({','.join('?' for _ in props)})"
        params.extend(props)
    recs = conn.execute(sql, params).fetchall()

    report.summary["recommendation_count"] = len(recs)
    if not recs:
        report.add("recommendations_exist", False, "no recommendations in range")
        return report

    report.add("recommendations_exist", True, f"{len(recs)} recommendations")

    revpan_ok = all(r["expected_book_prob"] is not None and r["expected_revpan"] is not None for r in recs)
    report.add("revpan_fields", revpan_ok, "all recs have expected_book_prob and expected_revpan")

    bounds_ok = all(_within_effective_bounds(r, g) for r in recs)
    report.add("price_bounds", bounds_ok, "floor <= recommended <= effective bounds")

    max_inc = float(g.get("max_increase_pct", 0.12))
    max_dec = float(g.get("max_decrease_pct", 0.15))
    move_violations = 0
    for r in recs:
        action = r["guardrail_action"] or ""
        if action.startswith("sanity_floor"):
            continue
        listed = r["listed_price_at_run"]
        if listed is None or listed <= 0:
            continue
        pct = (r["recommended_price"] - listed) / listed
        if pct > max_inc + 0.001 or pct < -max_dec - 0.001:
            move_violations += 1
    report.add("guardrail_moves", move_violations == 0, f"{move_violations} move cap violation(s)")

    shoulder = [r for r in recs if r["stay_date"] < f"{start.year}-12-15"]
    if shoulder:
        deltas = [
            (r["recommended_price"] - r["listed_price_at_run"]) / r["listed_price_at_run"]
            for r in shoulder
            if r["listed_price_at_run"]
        ]
        if deltas:
            median = sorted(deltas)[len(deltas) // 2]
            report.add(
                "shoulder_median_move",
                median < 0.05,
                f"median {median:+.1%} on {start}..{end}",
            )

    blocked_peak = conn.execute(
        """
        SELECT COUNT(*) c FROM price_recommendations r
        JOIN demand_signals d ON d.signal_date = r.stay_date AND d.signal_strength >= 0.85
        WHERE r.stay_date >= ? AND r.stay_date <= ?
          AND r.autonomy_level = 'handle'
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()["c"]
    report.add("peak_not_handle", int(blocked_peak or 0) == 0, f"{blocked_peak} peak nights at handle")

    # twin parity — only nights where both are available with similar listed prices
    if "summit_haus" in props and "overlook_ridge" in props:
        twins = conn.execute(
            """
            SELECT a.stay_date,
                   a.recommended_price AS summit,
                   b.recommended_price AS overlook,
                   sa.listed_price AS summit_listed,
                   so.listed_price AS overlook_listed
            FROM price_recommendations a
            JOIN price_recommendations b
              ON a.stay_date = b.stay_date AND a.run_id = b.run_id
            JOIN nightly_inventory sa
              ON sa.property_id = 'summit_haus' AND sa.stay_date = a.stay_date
            JOIN nightly_inventory so
              ON so.property_id = 'overlook_ridge' AND so.stay_date = a.stay_date
            WHERE a.property_id = 'summit_haus' AND b.property_id = 'overlook_ridge'
              AND a.stay_date >= ? AND a.stay_date <= ?
              AND sa.status = 'available'
              AND so.status = 'available'
              AND sa.listed_price IS NOT NULL AND sa.listed_price > 0
              AND so.listed_price IS NOT NULL AND so.listed_price > 0
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        comparable: list[sqlite3.Row] = []
        skipped = 0
        for row in twins:
            sl = float(row["summit_listed"])
            ol = float(row["overlook_listed"])
            if _listed_similar(sl, ol, twin_listed_max_pct):
                comparable.append(row)
            else:
                skipped += 1
        if not comparable:
            pct_label = f"{twin_listed_max_pct:.0%}"
            report.add(
                "twin_parity",
                True,
                f"0 comparable twin nights (listed within {pct_label}, {skipped} skipped)",
            )
        else:
            diffs = [abs(r["summit"] - r["overlook"]) for r in comparable]
            max_diff = max(diffs)
            pct_label = f"{twin_listed_max_pct:.0%}"
            report.add(
                "twin_parity",
                max_diff <= twin_max_delta,
                f"max delta ${max_diff:.0f} across {len(comparable)} comparable nights "
                f"(listed within {pct_label}, {skipped} skipped)",
            )

    sqi_runs = conn.execute(
        "SELECT COUNT(*) c FROM signal_runs WHERE collector = 'snotel' AND status = 'ok'"
    ).fetchone()["c"]
    report.add("snotel_collector", int(sqi_runs or 0) > 0, f"{sqi_runs} ok SNOTEL run(s)")

    return report


def format_audit(report: AuditReport) -> str:
    lines = ["# Pricing run audit", ""]
    icon = lambda ok: "PASS" if ok else "FAIL"
    for c in report.checks:
        lines.append(f"- [{icon(c.passed)}] **{c.name}**: {c.detail}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Overall: {'PASS' if report.passed else 'FAIL'}")
    lines.append(f"- Autonomy granted: {report.summary.get('autonomy', '?')}")
    if report.summary.get("health_failures"):
        lines.append(f"- Health gate failures: {', '.join(report.summary['health_failures'])}")
    lines.append(f"- Recommendations: {report.summary.get('recommendation_count', 0)}")
    return "\n".join(lines)
