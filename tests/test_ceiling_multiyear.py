"""Multi-year ceiling doctrine: same-season YoY is in; cross-season mixing is not."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.ceiling import (
    calendar_distance_days,
    compute_ceiling,
    lookback_start,
    season_year,
)
from src.config import load_policy
from src.db import connect, init_db
from src.features import build_features_for_property


def _book(conn, pid: str, stay: date, price: float, status: str = "booked") -> None:
    conn.execute(
        """INSERT INTO nightly_inventory
           (property_id, stay_date, listed_price, booked_price, status, day_of_week)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            pid,
            stay.isoformat(),
            price,
            price if status == "booked" else None,
            status,
            stay.weekday(),
        ),
    )


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "yoy.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
               VALUES ('test_haus','Test Haus',5,5.5,'[]',711,252,5000,
                       'America/Denver','abc123')"""
        )
        conn.commit()
    return path


def test_calendar_distance_wraps_new_year():
    assert calendar_distance_days(date(2024, 12, 30), date(2026, 1, 2)) == 3
    assert calendar_distance_days(date(2025, 12, 4), date(2026, 12, 4)) == 0
    assert lookback_start(date(2026, 12, 4), 5) == date(2021, 12, 4)
    assert season_year(date(2025, 12, 4)) == season_year(date(2026, 1, 10))


def test_multiyear_same_season_dow_uses_yoy_not_anchor(db: Path):
    """Three years of early-winter Fridays at $700 beat the seasonal-anchor fallback
    even though peak-ski history is huge. That is what the wider window is for."""
    policy = load_policy()
    target = date(2026, 12, 4)  # Friday, early_winter
    assert target.weekday() == 4
    yoy_fridays = [
        date(2025, 11, 28),
        date(2025, 12, 5),
        date(2024, 11, 29),
        date(2024, 12, 6),
        date(2023, 11, 24),
        date(2023, 12, 1),
    ]
    with connect(db) as conn:
        for stay in yoy_fridays:
            assert stay.weekday() == 4
            _book(conn, "test_haus", stay, 700)
        christmas = date(2022, 12, 25)
        for i in range(40):
            _book(conn, "test_haus", christmas + timedelta(days=i), 3000)
        _book(conn, "test_haus", target, 650, status="available")
        conn.commit()
        feats = build_features_for_property(
            conn, "test_haus", target, target, policy=policy
        )
        ceiling = compute_ceiling(conn, feats[0], policy, as_of=date(2026, 11, 1))
    assert feats[0].season == "early_winter"
    assert "season_dow_yoy" in ceiling.method, ceiling.method
    assert "all_history" not in ceiling.method
    assert ceiling.sample_size >= 5
    assert ceiling.confidence == pytest.approx(1.0)
    assert abs(ceiling.ceiling_price - 700) < 50
    assert ceiling.ceiling_price < 1500


def test_peak_years_cannot_inflate_shoulder_ceiling(db: Path):
    """Five years of $3,000 Christmas bookings still cannot price Dec 1."""
    policy = load_policy()
    target = date(2026, 12, 1)  # Tuesday, early_winter
    with connect(db) as conn:
        for year in (2021, 2022, 2023, 2024, 2025):
            for i in range(14):
                _book(conn, "test_haus", date(year, 12, 20) + timedelta(days=i), 3000)
        _book(conn, "test_haus", target, 650, status="available")
        conn.commit()
        feats = build_features_for_property(
            conn, "test_haus", target, target, policy=policy
        )
        ceiling = compute_ceiling(conn, feats[0], policy, as_of=date(2026, 11, 15))
    assert feats[0].season == "early_winter"
    assert "all_history" not in ceiling.method
    assert ceiling.method.startswith("seasonal_anchor")
    assert ceiling.ceiling_price <= ceiling.anchor_price * 1.05
    assert ceiling.ceiling_price < 1500


def test_lookback_drops_nights_older_than_five_years(db: Path):
    """A 5-year lock is a cap, not infinite memory. Ancient same-season Fridays
    must not set the ceiling once they age out of history_lookback_years."""
    policy = load_policy()
    target = date(2026, 12, 4)
    ancient = [
        date(2018, 11, 30),
        date(2018, 12, 7),
        date(2019, 11, 29),
        date(2019, 12, 6),
        date(2020, 11, 27),
        date(2020, 12, 4),
    ]
    with connect(db) as conn:
        for stay in ancient:
            assert stay.weekday() == 4
            _book(conn, "test_haus", stay, 2500)
        _book(conn, "test_haus", target, 650, status="available")
        conn.commit()
        feats = build_features_for_property(
            conn, "test_haus", target, target, policy=policy
        )
        ceiling = compute_ceiling(conn, feats[0], policy, as_of=target)
    assert lookback_start(target, 5) > max(ancient)
    assert "all_history" not in ceiling.method
    assert "season_dow" not in ceiling.method
    assert ceiling.method.startswith("seasonal_anchor")
    assert ceiling.ceiling_price < 1500
