"""Guesty sync + small-data safety tests.

The regression that motivates most of this file: on the live tenant, last Christmas
averaged an earlier seasonal level and this Christmas averages a higher seasonal level (realised $a much higher realized price). A model
fitted on that history wanted a -35% cut on the strongest nights of the year — i.e.
to restore last season's underpricing. Everything below pins the behaviour that
stops a thin-history model from overruling the operator.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.ceiling import compute_ceiling, demand_tier, seasonal_anchor
from src.compose import recommend_night
from src.config import load_policy
from src.db import connect, init_db
from src.features import build_features_for_property
from src.pms.guesty import GuestyListing, parse_guesty_date
from src.pms.sync import SyncReport, _floor_and_ceiling, recalibrate_bounds


def _listing(**kw) -> GuestyListing:
    base = dict(listing_id="abc123", nickname="Test Haus", title="t", bedrooms=5,
                bathrooms=5.5, accommodates=16, base_price=420.0,
                weekend_base_price=618.0, cleaning_fee=650.0, min_nights=2,
                address="1 Test St", city="Winter Park", lat=39.89, lng=-105.75,
                timezone="America/Denver", active=True, amenities=[])
    base.update(kw)
    return GuestyListing(**base)


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "g.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
               VALUES ('test_haus','Test Haus',5,5.5,'[]',711,252,1854,'America/Denver','abc123')"""
        )
        conn.commit()
    return path


# ------------------------------------------------------------------ identity

def test_property_id_is_a_stable_slug():
    assert _listing(nickname="Summit Haus").property_id == "summit_haus"
    assert _listing(nickname="Cloud 9").property_id == "cloud_9"
    assert _listing(nickname="Café / Lodge!").property_id == "cafe_lodge"
    assert _listing(nickname="   ").property_id == "abc123"  # falls back to listing id


def test_parse_guesty_date_handles_iso_timestamps():
    assert parse_guesty_date("2026-12-27T00:00:00.000Z") == date(2026, 12, 27)
    assert parse_guesty_date("2026-12-27") == date(2026, 12, 27)
    assert parse_guesty_date(None) is None
    assert parse_guesty_date("nonsense") is None


# --------------------------------------------------------------------- bounds

def test_base_price_seed_is_only_provisional():
    """Guesty basePrice is a STARTING rate, not a ceiling. The seed must be treated as
    provisional or a $420 base caps a property that sells at $a much higher realized price."""
    floor, base_ceiling, _ = _floor_and_ceiling(_listing())
    assert base_ceiling < 800, "seed is intentionally low; recalibrate_bounds must fix it"
    assert floor < base_ceiling


def test_recalibrate_bounds_uses_observed_prices(db: Path):
    """REGRESSION: seeding the ceiling from Guesty's basePrice produced an $818 anchor
    on nights the operator lists at $2,700, driving a -70% Christmas recommendation."""
    with connect(db) as conn:
        d = date(2026, 12, 1)
        for i in range(60):
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,?,'available',?)",
                ((d + timedelta(days=i)).isoformat(), 2600 + i * 5, (d + timedelta(days=i)).weekday()),
            )
        conn.commit()
        report = SyncReport()
        recalibrate_bounds(conn, report)
        row = conn.execute(
            "SELECT min_floor_rate, base_ceiling_rate, max_ceiling_rate FROM properties"
        ).fetchone()
    assert row["base_ceiling_rate"] > 2500, "ceiling must follow observed prices, not basePrice"
    assert row["max_ceiling_rate"] > row["base_ceiling_rate"]
    assert row["min_floor_rate"] > 1000


# ---------------------------------------------------------------- demand tiers

def test_demand_tier_separates_holiday_from_ordinary_peak():
    policy = load_policy()
    assert demand_tier(0.95, policy) == "high"    # Christmas
    assert demand_tier(0.55, policy) == "mid"
    assert demand_tier(0.20, policy) == "low"     # ordinary January midweek


def test_anchor_prefers_same_demand_tier(db: Path):
    """peak_ski spans 15 Dec - 31 Mar. Without tier matching, a Christmas night anchors
    to a mid-January price."""
    policy = load_policy()
    with connect(db) as conn:
        # cheap ordinary peak nights (Jan) + expensive holiday nights (late Dec)
        for i in range(40):
            d = date(2027, 1, 10) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,700,'available',?)", (d.isoformat(), d.weekday()))
        for i in range(14):
            d = date(2026, 12, 21) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", date(2026, 12, 23),
                                            date(2026, 12, 23), policy=policy)
        anchor = seasonal_anchor(feats[0], policy, conn)
    assert feats[0].demand_strength >= 0.8, "Christmas should read as high demand"
    assert anchor > 2000, f"holiday anchored to ordinary-peak price: ${anchor:.0f}"


# ----------------------------------------------------------------- deference

def test_low_confidence_defers_to_the_operators_price(db: Path):
    """THE headline safety property. With thin history the model must nudge the
    incumbent price, never reverse it."""
    policy = load_policy()
    with connect(db) as conn:
        # A repriced holiday: cheap last year, expensive this year, nothing realised.
        for i in range(20):
            d = date(2025, 12, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,480,'available',?)", (d.isoformat(), d.weekday()))
        for i in range(16):
            d = date(2026, 12, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", date(2026, 12, 23),
                                            date(2026, 12, 23), policy=policy)
        rec = recommend_night(conn, feats[0], policy=policy)
    assert rec is not None
    drop = (rec.listed_price_at_run - rec.recommended_price) / rec.listed_price_at_run
    assert drop < 0.20, f"model overruled the operator by {drop:.0%} on thin evidence"
    assert rec.ceiling_confidence < 0.80


def test_deference_does_not_fire_at_high_confidence(db: Path):
    """Deference must not blunt a well-evidenced recommendation."""
    policy = load_policy()
    with connect(db) as conn:
        d = date(2026, 9, 20)
        for i in range(120):
            day = d + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,"
                "booked_price,status,day_of_week) VALUES ('test_haus',?,?,?,'booked',?)",
                (day.isoformat(), 500, 500, day.weekday()))
        target = date(2027, 10, 6)
        conn.execute(
            "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
            " VALUES ('test_haus',?,500,'available',?)", (target.isoformat(), target.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", target, target, policy=policy)
        ceiling = compute_ceiling(conn, feats[0], policy)
    assert ceiling.confidence >= 0.80
    assert "season" in ceiling.method


def test_peak_nights_never_auto_push(db: Path):
    """Christmas must escalate regardless of what the model wants."""
    policy = load_policy()
    with connect(db) as conn:
        d = date(2026, 12, 23)
        conn.execute(
            "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
            " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", d, d, policy=policy)
        rec = recommend_night(conn, feats[0], policy=policy)
    assert rec.status == "blocked"
    assert rec.autonomy_level == "escalate"
    assert rec.guardrail_action == "peak_blackout"
