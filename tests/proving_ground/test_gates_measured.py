from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from src.db import connect, init_db
from src.proving_ground.gates import build_hard_gates, measure_guardrail_violations
from src.signals.store import SignalStore


def test_lookahead_canary_trips(tmp_path: Path):
    from src.signals.store import Observation, QUALITY_OK

    db = tmp_path / "canary.db"
    init_db(db)
    with connect(db) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO markets (market_id, name, ring, county)
               VALUES ('grand_home', 'WP', 'home', 'Grand')"""
        )
        conn.execute(
            """INSERT OR IGNORE INTO signal_definitions (
               signal_key, category, unit, cadence, source, collector
            ) VALUES ('pg_canary', 'test', 'ratio', 'daily', 'proving_ground', 'proving_ground')"""
        )
        conn.commit()
        store = SignalStore(conn)
        future = date(2026, 2, 1)
        store.write_observations([
            Observation(
                signal_key="pg_canary",
                market_id="grand_home",
                effective_date=future.isoformat(),
                observed_at=future.isoformat(),
                value=1.0,
                quality=QUALITY_OK,
            )
        ])
        from src.proving_ground.gates import measure_lookahead_violations

        trips = measure_lookahead_violations(conn, date(2026, 1, 1), signal_key="pg_canary")
    assert trips == 1


def test_measured_by_on_hard_gates(tmp_path: Path):
    db = tmp_path / "g.db"
    init_db(db)
    with connect(db) as conn:
        gates = build_hard_gates(
            conn,
            run_id="r1",
            property_id="x",
            decision_date=date(2026, 1, 1),
            determinism_label="identical_output_hashes",
        )
    for g in gates:
        assert g.measured_by.startswith("src.proving_ground.")


def test_guardrail_violation_counter(tmp_path: Path):
    db = tmp_path / "g2.db"
    init_db(db)
    with connect(db) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone)
               VALUES ('p','P',3,2,'[]',900,400,2000,'America/Denver')"""
        )
        conn.execute(
            """INSERT INTO price_recommendations (
               run_id, property_id, stay_date, recommended_price, ceiling_price, floor_price,
               rule_version, model_version, inputs_hash, status
            ) VALUES ('r','p','2026-12-01', 3000, 2000, 400, 'r','m','h','suggested')"""
        )
        conn.commit()
        n = measure_guardrail_violations(conn, run_id="r", property_id="p")
    assert n == 1


def test_advisory_ceiling_overrun_is_not_a_guardrail_violation(tmp_path: Path):
    db = tmp_path / "g3.db"
    init_db(db)
    with connect(db) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone)
               VALUES ('p','P',3,2,'[]',900,400,2000,'America/Denver')"""
        )
        conn.execute(
            """INSERT INTO price_recommendations (
               run_id, property_id, stay_date, recommended_price, ceiling_price, floor_price,
               rule_version, model_version, inputs_hash, status, weak_ceiling
            ) VALUES ('r','p','2026-12-01', 3700, 2683, 277, 'r','m','h','suggested', 1)"""
        )
        conn.commit()
        n = measure_guardrail_violations(conn, run_id="r", property_id="p")
    assert n == 0
