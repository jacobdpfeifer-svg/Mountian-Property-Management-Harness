"""Post-run audit — data health, guardrails, and known regression checks."""

from __future__ import annotations

import json
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

    # --- data completeness ---
    for pid in props:
        row = conn.execute(
            "SELECT airbnb_room_id FROM properties WHERE property_id = ?", (pid,)
        ).fetchone()
        report.add(
            f"room_id:{pid}",
            bool(row and row["airbnb_room_id"]),
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
        report.add(
            f"inventory:{pid}",
            total >= 28,
            f"{total} nights, {inv['avail']} available, {inv['priced']} with price",
        )

    health = assess_data_health(conn, policy)
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
    report.add("demand_signals", int(demand or 0) >= 10, f"{demand} rows in range")

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

    bounds_ok = all(
        (r["floor_price"] or 0) <= r["recommended_price"] <= (r["ceiling_price"] or 1e9)
        for r in recs
    )
    report.add("price_bounds", bounds_ok, "floor <= recommended <= ceiling")

    max_inc = float(g.get("max_increase_pct", 0.12))
    max_dec = float(g.get("max_decrease_pct", 0.15))
    move_violations = 0
    for r in recs:
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
            report.add("shoulder_median_move", median < 0.05, f"median {median:+.1%} on Dec 1-14")

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

    # twin parity
    if "summit_haus" in props and "overlook_ridge" in props:
        twins = conn.execute(
            """
            SELECT a.stay_date, a.recommended_price AS summit, b.recommended_price AS overlook
            FROM price_recommendations a
            JOIN price_recommendations b
              ON a.stay_date = b.stay_date AND a.run_id = b.run_id
            WHERE a.property_id = 'summit_haus' AND b.property_id = 'overlook_ridge'
              AND a.stay_date >= ? AND a.stay_date <= ?
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        if twins:
            diffs = [abs(r["summit"] - r["overlook"]) for r in twins]
            max_diff = max(diffs)
            report.add("twin_parity", max_diff <= 50, f"max delta ${max_diff:.0f} across {len(twins)} nights")

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
