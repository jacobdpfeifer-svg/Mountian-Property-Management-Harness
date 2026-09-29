"""W1 calm synthetic season — seeds a disposable DB without importing the engine."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from proving_ground_exam.scoring.demand import FLAT_SEASONAL_PRICE

DEFAULT_PROPERTY_ID = "cabin_ridge"
DEFAULT_MARKET_ID = "grand_home"


class W1CalmWorld:
    """Discrete-choice calm season for Level 1 / Level 2 practice."""

    world_id = "W1_calm"

    def __init__(
        self,
        *,
        property_id: str = DEFAULT_PROPERTY_ID,
        market_id: str = DEFAULT_MARKET_ID,
        season_start: date | None = None,
        season_end: date | None = None,
    ):
        self.property_id = property_id
        self.market_id = market_id
        self.season_start = season_start or date(2026, 11, 1)
        self.season_end = season_end or date(2027, 4, 15)

    def stay_dates(self) -> list[date]:
        out: list[date] = []
        d = self.season_start
        while d <= self.season_end:
            out.append(d)
            d += timedelta(days=1)
        return out

    def seed_property(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "UPDATE properties SET market_id = ? WHERE property_id = ?",
            (self.market_id, self.property_id),
        )

    def extend_inventory(self, conn: sqlite3.Connection) -> int:
        """Ensure every season night exists as available inventory with a listed price."""
        n = 0
        for stay in self.stay_dates():
            row = conn.execute(
                """
                SELECT status FROM nightly_inventory
                WHERE property_id = ? AND stay_date = ?
                """,
                (self.property_id, stay.isoformat()),
            ).fetchone()
            if row is not None:
                continue
            listed = FLAT_SEASONAL_PRICE
            if stay.weekday() in {4, 5}:
                listed = 880.0
            if (stay.month, stay.day) in {(12, 24), (12, 25), (12, 31), (1, 1)}:
                listed = 1040.0
            conn.execute(
                """
                INSERT INTO nightly_inventory (
                    property_id, stay_date, listed_price, booked_price,
                    status, lead_time_days, day_of_week, evidence_kind
                ) VALUES (?, ?, ?, NULL, 'available', NULL, ?, 'skeleton')
                """,
                (self.property_id, stay.isoformat(), listed, stay.weekday()),
            )
            n += 1
        conn.commit()
        return n

    def advance(self, conn: sqlite3.Connection, as_of: date, *, level: int) -> None:
        """Publish world-visible state for simulated day ``as_of`` (no engine imports)."""
        del level  # reserved for Level 2 signal fixtures
        self.extend_inventory(conn)
        conn.execute(
            """
            UPDATE nightly_inventory
            SET lead_time_days = CAST(julianday(stay_date) - julianday(?) AS INTEGER)
            WHERE property_id = ? AND stay_date >= ?
            """,
            (as_of.isoformat(), self.property_id, as_of.isoformat()),
        )
        conn.commit()
