"""Measured hard gates for the Proving Ground."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.proving_ground.thresholds import HARD_GATES


@dataclass(frozen=True)
class MeasuredGate:
    name: str
    observed: float | str
    threshold: float | str
    passed: bool
    measured_by: str


def measure_lookahead_violations(
    conn: sqlite3.Connection,
    decision_date: date,
    *,
    signal_key: str = "pg_canary",
) -> int:
    """Return count of observations with observed_at > decision_date (must be 0 at runtime)."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM signal_observations
        WHERE signal_key = ? AND observed_at > ?
        """,
        (signal_key, decision_date.isoformat()),
    ).fetchone()
    return int(row["c"] if row else 0)


def count_lookahead_canary_trips(
    conn: sqlite3.Connection,
    decision_date: date,
) -> int:
    """Detect poisoned future-dated rows that must never inform pricing at decision_date."""
    return measure_lookahead_violations(conn, decision_date, signal_key="pg_canary")


def measure_guesty_write_attempts(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM rate_changes
        WHERE actor NOT IN ('dry_run', 'engine') AND result NOT IN ('dry_run', 'pending')
        """
    ).fetchone()
    return int(row["c"] if row else 0)


def measure_guardrail_violations(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    property_id: str,
) -> int:
    rows = conn.execute(
        """
        SELECT recommended_price, floor_price, ceiling_price, weak_ceiling
        FROM price_recommendations
        WHERE run_id = ? AND property_id = ?
        """,
        (run_id, property_id),
    ).fetchall()
    violations = 0
    for row in rows:
        price = float(row["recommended_price"])
        floor_p = float(row["floor_price"])
        ceiling = float(row["ceiling_price"])
        advisory = bool(row["weak_ceiling"])
        if price < floor_p - 0.01:
            violations += 1
        elif not advisory and price > ceiling + 0.01:
            violations += 1
    return violations


def measure_auto_pushes_while_unhealthy(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT rc.result, dhr.granted_level
        FROM rate_changes rc
        LEFT JOIN data_health_runs dhr ON dhr.run_id = rc.request_id
        WHERE rc.result = 'applied' AND COALESCE(dhr.granted_level, 'handle') != 'handle'
        """
    ).fetchall()
    return len(rows)


def build_hard_gates(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    property_id: str,
    decision_date: date,
    determinism_label: str,
) -> list[MeasuredGate]:
    lookahead = count_lookahead_canary_trips(conn, decision_date)
    guesty = measure_guesty_write_attempts(conn)
    guardrails = measure_guardrail_violations(conn, run_id=run_id, property_id=property_id)
    unhealthy = measure_auto_pushes_while_unhealthy(conn)
    return [
        MeasuredGate(
            "lookahead_violations",
            lookahead,
            HARD_GATES["lookahead_violations"],
            lookahead <= HARD_GATES["lookahead_violations"],
            "src.proving_ground.gates.count_lookahead_canary_trips",
        ),
        MeasuredGate(
            "guesty_write_attempts",
            guesty,
            HARD_GATES["guesty_write_attempts"],
            guesty <= HARD_GATES["guesty_write_attempts"],
            "src.proving_ground.gates.measure_guesty_write_attempts",
        ),
        MeasuredGate(
            "guardrail_violations",
            guardrails,
            HARD_GATES["guardrail_violations"],
            guardrails <= HARD_GATES["guardrail_violations"],
            "src.proving_ground.gates.measure_guardrail_violations",
        ),
        MeasuredGate(
            "auto_pushes_while_unhealthy",
            unhealthy,
            HARD_GATES["auto_pushes_while_unhealthy"],
            unhealthy <= HARD_GATES["auto_pushes_while_unhealthy"],
            "src.proving_ground.gates.measure_auto_pushes_while_unhealthy",
        ),
        MeasuredGate(
            "same_seed_determinism",
            determinism_label,
            "identical_output_hashes",
            determinism_label == "identical_output_hashes",
            "src.proving_ground.runner.verify_determinism",
        ),
    ]


def gates_to_dict(gates: list[MeasuredGate]) -> list[dict[str, Any]]:
    return [
        {
            "name": g.name,
            "observed": g.observed,
            "threshold": g.threshold,
            "passed": g.passed,
            "measured_by": g.measured_by,
        }
        for g in gates
    ]
