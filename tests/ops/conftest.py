"""Shared fixtures for the operations layer: a DB with the three Mont Luxe homes."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.db import connect, init_db

PROPS = (
    ("summit_haus", "312 Northwoods", "listing-312"),
    ("overlook_ridge", "300 Northwoods", "listing-300"),
    ("cloud_9", "Cloud 9", "listing-c9"),
)


def add_reservation(conn, rid, pid, check_in, check_out, *, fare=None, cleaning=None,
                    payout=None, channel_commission=None, status="confirmed", source="airbnb"):
    nights = (check_out - check_in).days
    conn.execute(
        """INSERT INTO reservations (reservation_id, property_id, check_in, check_out, nights,
               status, source, fare_accommodation, fare_cleaning, host_payout, channel_commission)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (rid, pid, check_in.isoformat(), check_out.isoformat(), nights, status, source,
         fare, cleaning, payout, channel_commission),
    )
    for i in range(nights):
        conn.execute(
            """INSERT INTO nightly_inventory (property_id, stay_date, listed_price, status, reservation_id)
               VALUES (?,?,?,?,?) ON CONFLICT(property_id, stay_date) DO UPDATE SET
               status=excluded.status, reservation_id=excluded.reservation_id""",
            (pid, (check_in + timedelta(days=i)).isoformat(), 1000.0,
             "blocked" if source == "owner" else "booked", rid),
        )


def add_open_nights(conn, pid, start, nights, *, price=1000.0, min_stay=None):
    for i in range(nights):
        conn.execute(
            """INSERT INTO nightly_inventory (property_id, stay_date, listed_price, status, min_stay)
               VALUES (?,?,?,?,?) ON CONFLICT(property_id, stay_date) DO NOTHING""",
            (pid, (start + timedelta(days=i)).isoformat(), price, "available", min_stay),
        )


def add_signal(conn, key, value, effective, observed=None, market="grand_home"):
    conn.execute(
        """INSERT OR IGNORE INTO signal_definitions (signal_key, category, unit, cadence, source, status)
           VALUES (?,?,?,?,?,?)""",
        (key, "test", "x", "daily", "test", "active"),
    )
    conn.execute(
        """INSERT INTO signal_observations (signal_key, market_id, observed_at, effective_date, value)
           VALUES (?,?,?,?,?)""",
        (key, market, (observed or effective).isoformat(), effective.isoformat(), value),
    )


@pytest.fixture()
def ops_db(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("MONTLUXE_MEMORY_ROOT", str(tmp_path / "memroot"))
    path = tmp_path / "ops.db"
    init_db(path)
    with connect(path) as conn:
        for pid, name, listing in PROPS:
            conn.execute(
                """INSERT INTO properties (property_id, name, bedrooms, bathrooms, base_ceiling_rate,
                       min_floor_rate, max_ceiling_rate, pms_listing_id, max_occupancy)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (pid, name, 6, 5.0, 1500, 500, 4000, listing, 16),
            )
        conn.commit()
    return path
