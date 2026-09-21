"""Audit module regression tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.audit import run_audit
from src.config import load_policy
from src.db import connect, init_db
from src.ingest import upsert_inventory, upsert_property

ROOT = Path(__file__).resolve().parents[1]
START = date(2026, 9, 2)
END = date(2026, 9, 14)


def _check(report, name: str):
    for c in report.checks:
        if c.name == name:
            return c
    raise AssertionError(f"check {name!r} not found: {[c.name for c in report.checks]}")


def _seed_property(conn, pid: str, *, airbnb_room_id: str | None = None, pms_listing_id: str | None = None):
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
        "airbnb_room_id": airbnb_room_id,
    })
    if pms_listing_id:
        conn.execute(
            "UPDATE properties SET pms_listing_id = ? WHERE property_id = ?",
            (pms_listing_id, pid),
        )


def _seed_inventory(conn, pid: str, start: date, nights: int, listed: float = 500.0):
    for i in range(nights):
        d = start + timedelta(days=i)
        upsert_inventory(conn, {
            "property_id": pid,
            "stay_date": d.isoformat(),
            "listed_price": listed,
            "status": "available",
        })
    conn.commit()


def _insert_rec(
    conn,
    *,
    property_id: str,
    stay_date: str,
    recommended: float,
    listed: float,
    ceiling: float,
    floor: float = 400.0,
    guardrail_action: str | None = None,
    run_id: str = "test_run",
):
    conn.execute(
        """
        INSERT INTO price_recommendations (
            run_id, property_id, stay_date, recommended_price, ceiling_price, floor_price,
            listed_price_at_run, expected_book_prob, expected_revpan, ceiling_confidence,
            autonomy_level, guardrail_action, reasons, rule_version, model_version,
            inputs_hash, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', 'test', 'test', 'testhash', 'suggested')
        """,
        (
            run_id, property_id, stay_date, recommended, ceiling, floor,
            listed, 0.4, 200.0, 0.5, "suggest", guardrail_action,
        ),
    )
    conn.commit()


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "audit.db"
    init_db(path, seed_markets=False)
    return path


def test_inventory_scales_to_date_range(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        _seed_property(conn, "summit_haus", airbnb_room_id="123")
        _seed_inventory(conn, "summit_haus", START, 13)
        report_ok = run_audit(conn, START, END, property_ids=["summit_haus"], policy=policy)
        assert _check(report_ok, "inventory:summit_haus").passed

        conn.execute(
            "DELETE FROM nightly_inventory WHERE property_id = 'summit_haus' AND stay_date = ?",
            (END.isoformat(),),
        )
        conn.commit()
        report_short = run_audit(conn, START, END, property_ids=["summit_haus"], policy=policy)
        assert not _check(report_short, "inventory:summit_haus").passed
        assert "12/13" in _check(report_short, "inventory:summit_haus").detail


def test_demand_signals_scales_to_date_range(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        _seed_property(conn, "summit_haus", airbnb_room_id="123")
        _seed_inventory(conn, "summit_haus", START, 13)
        for i in range(4):
            d = (START + timedelta(days=i)).isoformat()
            conn.execute(
                "INSERT INTO demand_signals (signal_date, region, event_name, signal_strength, source) "
                "VALUES (?, 'winter_park', 'Labor Day', 0.65, 'test')",
                (d,),
            )
        conn.commit()
        report = run_audit(conn, START, END, property_ids=["summit_haus"], policy=policy)
        chk = _check(report, "demand_signals")
        assert chk.passed
        assert "4/4" in chk.detail


def test_room_id_skipped_for_direct_book(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        _seed_property(conn, "cloud_9", pms_listing_id="guesty123")
        _seed_inventory(conn, "cloud_9", START, 13)
        report = run_audit(conn, START, END, property_ids=["cloud_9"], policy=policy)
        chk = _check(report, "room_id:cloud_9")
        assert chk.passed
        assert "direct-book" in chk.detail


def test_guardrail_moves_exempts_sanity_floor(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        _seed_property(conn, "overlook_ridge", airbnb_room_id="123")
        _seed_inventory(conn, "overlook_ridge", START, 13)
        _insert_rec(
            conn,
            property_id="overlook_ridge",
            stay_date=START.isoformat(),
            recommended=405.0,
            listed=250.0,
            ceiling=1016.0,
            guardrail_action="sanity_floor",
        )
        report = run_audit(conn, START, END, property_ids=["overlook_ridge"], policy=policy)
        assert _check(report, "guardrail_moves").passed


def test_price_bounds_allows_clamped_above_ceiling(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        _seed_property(conn, "summit_haus", airbnb_room_id="123")
        _seed_inventory(conn, "summit_haus", START, 13)
        # Summit Sep 6: rec $595 > ceiling $550 but clamped_decrease within move cap
        _insert_rec(
            conn,
            property_id="summit_haus",
            stay_date="2026-09-06",
            recommended=595.0,
            listed=696.0,
            ceiling=550.0,
            floor=296.0,
            guardrail_action="clamped_decrease",
        )
        report = run_audit(conn, START, END, property_ids=["summit_haus"], policy=policy)
        assert _check(report, "price_bounds").passed


def test_twin_parity_filters_dissimilar_listed(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        for pid in ("summit_haus", "overlook_ridge"):
            _seed_property(conn, pid, airbnb_room_id="123")
        # Dissimilar listed (24% apart) — Sep 4
        upsert_inventory(conn, {
            "property_id": "summit_haus",
            "stay_date": "2026-09-04",
            "listed_price": 704.0,
            "status": "available",
        })
        upsert_inventory(conn, {
            "property_id": "overlook_ridge",
            "stay_date": "2026-09-04",
            "listed_price": 567.0,
            "status": "available",
        })
        # Similar listed (12.8% apart) — Sep 11
        upsert_inventory(conn, {
            "property_id": "summit_haus",
            "stay_date": "2026-09-11",
            "listed_price": 564.0,
            "status": "available",
        })
        upsert_inventory(conn, {
            "property_id": "overlook_ridge",
            "stay_date": "2026-09-11",
            "listed_price": 500.0,
            "status": "available",
        })
        _insert_rec(
            conn, property_id="summit_haus", stay_date="2026-09-04",
            recommended=705.0, listed=704.0, ceiling=900.0,
        )
        _insert_rec(
            conn, property_id="overlook_ridge", stay_date="2026-09-04",
            recommended=635.0, listed=567.0, ceiling=900.0,
        )
        _insert_rec(
            conn, property_id="summit_haus", stay_date="2026-09-11",
            recommended=590.0, listed=564.0, ceiling=900.0,
        )
        _insert_rec(
            conn, property_id="overlook_ridge", stay_date="2026-09-11",
            recommended=540.0, listed=500.0, ceiling=900.0,
        )
        conn.commit()

        report = run_audit(
            conn, START, END,
            property_ids=["summit_haus", "overlook_ridge"],
            policy=policy,
        )
        chk = _check(report, "twin_parity")
        assert chk.passed
        assert "1 comparable" in chk.detail
        assert "1 skipped" in chk.detail
        assert "$50" in chk.detail
