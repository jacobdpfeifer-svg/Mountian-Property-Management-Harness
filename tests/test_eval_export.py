"""Regression tests for src/eval/export.py.

Step 0 of the production-readiness audit flagged this module at 0% coverage.
It IS reachable in production: `wp-price export` (src/cli/main.py::cmd_export)
calls `export_recommendations_csv` directly. These tests exercise it end to end
against a real sqlite schema so a future change can't silently corrupt the
operator-facing export CSV (e.g. reasons/owner_reasons mapping, date-range
filtering, or the property_id scope filter) without a test noticing.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from src.db import connect, init_db
from src.eval.export import export_recommendations_csv
from src.ingest import upsert_property


def _seed_property(conn, pid: str):
    upsert_property(conn, {
        "property_id": pid,
        "name": pid,
        "bedrooms": 5,
        "bathrooms": 4.0,
        "amenities": "[]",
        "base_ceiling_rate": 1000,
        "min_floor_rate": 400,
        "max_ceiling_rate": 2000,
        "luxury_tier": "luxury",
        "target_alos": 4,
        "timezone": "America/Denver",
    })


def _seed_recommendation(conn, *, pid: str, stay_date: date, price: float, reasons: list[dict]):
    conn.execute(
        """
        INSERT INTO price_recommendations (
            run_id, property_id, stay_date, recommended_price, ceiling_price,
            floor_price, listed_price_at_run, expected_book_prob, expected_revpan,
            ceiling_confidence, autonomy_level, guardrail_action, reasons,
            rule_version, model_version, inputs_hash, status, evidence_count,
            range_low, range_high
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "run-1", pid, stay_date.isoformat(), price, price + 200, 400.0,
            price - 10, 0.5, price * 0.5, 0.8, "suggest", None,
            json.dumps(reasons), "v1", "v1", "hash1", "suggested", 3,
            price - 50, price + 50,
        ),
    )
    conn.commit()


def test_export_recommendations_csv_round_trip(tmp_path: Path):
    db_path = tmp_path / "wp.db"
    init_db(db_path, seed_markets=False)
    with connect(db_path) as conn:
        _seed_property(conn, "summit_haus")
        _seed_property(conn, "overlook_ridge")
        _seed_recommendation(
            conn, pid="summit_haus", stay_date=date(2026, 12, 24), price=900.0,
            reasons=[{"message": "peak demand"}, {"message": "low comp coverage"}],
        )
        _seed_recommendation(
            conn, pid="overlook_ridge", stay_date=date(2026, 12, 25), price=850.0,
            reasons=[],
        )
        # Outside the requested window — must not appear in the export.
        _seed_recommendation(
            conn, pid="summit_haus", stay_date=date(2027, 1, 5), price=700.0,
            reasons=[{"message": "should be excluded by date filter"}],
        )

        out = tmp_path / "export.csv"
        n = export_recommendations_csv(
            conn, date(2026, 12, 20), date(2026, 12, 31), out,
        )

    assert n == 2
    assert out.exists()
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 2

    by_pid = {r["property_id"]: r for r in rows}
    assert by_pid["summit_haus"]["stay_date"] == "2026-12-24"
    assert float(by_pid["summit_haus"]["recommended_price"]) == 900.0
    # The reasons JSON must be flattened into a readable owner_reasons column,
    # not leaked as raw JSON, and multiple reasons must be pipe-joined.
    assert by_pid["summit_haus"]["owner_reasons"] == "peak demand | low comp coverage"
    # No reasons -> empty string, not "null" or a stray pipe.
    assert by_pid["overlook_ridge"]["owner_reasons"] == ""
    # The raw `reasons` column must never leak into the CSV verbatim.
    assert "reasons" not in rows[0]


def test_export_recommendations_csv_property_scope_filter(tmp_path: Path):
    db_path = tmp_path / "wp.db"
    init_db(db_path, seed_markets=False)
    with connect(db_path) as conn:
        _seed_property(conn, "summit_haus")
        _seed_property(conn, "overlook_ridge")
        _seed_recommendation(
            conn, pid="summit_haus", stay_date=date(2026, 12, 24), price=900.0, reasons=[],
        )
        _seed_recommendation(
            conn, pid="overlook_ridge", stay_date=date(2026, 12, 24), price=850.0, reasons=[],
        )

        out = tmp_path / "export_scoped.csv"
        n = export_recommendations_csv(
            conn, date(2026, 12, 20), date(2026, 12, 31), out,
            property_ids=["summit_haus"],
        )

    assert n == 1
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["property_id"] == "summit_haus"


def test_export_recommendations_csv_malformed_reasons_json_does_not_crash(tmp_path: Path):
    """A corrupt `reasons` payload must degrade to an empty owner_reasons, not raise."""
    db_path = tmp_path / "wp.db"
    init_db(db_path, seed_markets=False)
    with connect(db_path) as conn:
        _seed_property(conn, "summit_haus")
        conn.execute(
            """
            INSERT INTO price_recommendations (
                run_id, property_id, stay_date, recommended_price, ceiling_price,
                floor_price, rule_version, model_version, inputs_hash, reasons
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-1", "summit_haus", "2026-12-24", 900.0, 1100.0, 400.0,
                "v1", "v1", "hash1", "{not valid json",
            ),
        )
        conn.commit()

        out = tmp_path / "export_bad_json.csv"
        n = export_recommendations_csv(conn, date(2026, 12, 20), date(2026, 12, 31), out)

    assert n == 1
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows[0]["owner_reasons"] == ""
