"""Regression tests for run-scoped engine memoization."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date
from pathlib import Path

from src.compose import generate_recommendations
from src.config import CONDITIONS_PATH, load_conditions, load_yaml
from src.db import connect, init_db
from src.ingest import CsvIngestAdapter
from src.runcache import engine_run_cache

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"


def _sample_db(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    adapter = CsvIngestAdapter(
        properties_csv=SAMPLE / "properties.csv",
        inventory_csv=SAMPLE / "nightly_inventory.csv",
        comps_csv=SAMPLE / "comps.csv",
        demand_csv=SAMPLE / "demand_signals.csv",
        inquiries_csv=SAMPLE / "booking_inquiries.csv",
    )
    with connect(path) as conn:
        adapter.load_all(conn)
    return path


def _fingerprint(recs: list) -> str:
    rows = sorted(
        (
            r.property_id,
            r.stay_date.isoformat(),
            r.recommended_price,
            r.guardrail_action or "",
            r.inputs_hash,
        )
        for r in recs
    )
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def test_load_yaml_deepcopy_outside_run_cache():
    first = load_yaml(CONDITIONS_PATH)
    first["__mutation_probe__"] = True
    second = load_yaml(CONDITIONS_PATH)
    assert "__mutation_probe__" not in second


def test_load_yaml_single_copy_per_file_inside_run_cache():
    with engine_run_cache():
        first = load_yaml(CONDITIONS_PATH)
        second = load_yaml(CONDITIONS_PATH)
        assert first is second
    third = load_yaml(CONDITIONS_PATH)
    assert third is not first


def test_generate_recommendations_60_day_window_is_deterministic(tmp_path: Path):
    db = _sample_db(tmp_path)
    start = date(2026, 12, 1)
    end = start.replace(day=1)  # noqa: PLW2901 — anchor month
    from datetime import timedelta

    end = start + timedelta(days=59)
    with connect(db) as conn:
        conn.execute("PRAGMA query_only = ON")
        a, _ = generate_recommendations(
            conn,
            start,
            end,
            property_ids=["aspen_glow"],
            persist=False,
            allow_past=True,
        )
        b, _ = generate_recommendations(
            conn,
            start,
            end,
            property_ids=["aspen_glow"],
            persist=False,
            allow_past=True,
        )
    assert _fingerprint(a) == _fingerprint(b)
    assert len(a) == len(b) > 0
