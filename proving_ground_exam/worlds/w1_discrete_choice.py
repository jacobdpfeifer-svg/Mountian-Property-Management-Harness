"""W1 discrete-choice demand — examiner-owned (no engine imports)."""

from __future__ import annotations

import math
import random
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from proving_ground_exam.scoring.demand import FLAT_SEASONAL_PRICE, booking_probability, true_demand


@dataclass(frozen=True)
class BookingOutcome:
    stay_date: date
    booked: bool
    price_paid: float | None


class W1DiscreteChoiceWorld:
    """Multinomial logit vs comp set + outside option; feeds simulated inventory."""

    world_id = "W1_discrete_choice"

    def __init__(
        self,
        *,
        property_id: str = "cabin_ridge",
        market_id: str = "grand_home",
        season_start: date | None = None,
        season_end: date | None = None,
        comp_price: float = 680.0,
    ):
        self.property_id = property_id
        self.market_id = market_id
        self.season_start = season_start or date(2026, 11, 1)
        self.season_end = season_end or date(2027, 4, 15)
        self.comp_price = comp_price

    def stay_dates(self) -> list[date]:
        out: list[date] = []
        d = self.season_start
        while d <= self.season_end:
            out.append(d)
            d += timedelta(days=1)
        return out

    def choice_probability(self, own_price: float, demand: float) -> float:
        """Logit: own vs one comp vs outside option."""
        u_own = 1.2 * demand - (own_price - 640.0) / 400.0
        u_comp = 1.0 * demand - (self.comp_price - 640.0) / 400.0
        u_out = 0.35
        m = max(u_own, u_comp, u_out)
        e_own = math.exp(u_own - m)
        e_comp = math.exp(u_comp - m)
        e_out = math.exp(u_out - m)
        return e_own / (e_own + e_comp + e_out)

    def simulate_booking(self, stay: date, listed_price: float, *, level: int, seed: int) -> BookingOutcome:
        demand = true_demand(stay, season_start=self.season_start, level=level, seed=seed)
        p = self.choice_probability(listed_price, demand)
        rng = random.Random(seed + stay.toordinal())
        if rng.random() < p:
            return BookingOutcome(stay_date=stay, booked=True, price_paid=listed_price)
        return BookingOutcome(stay_date=stay, booked=False, price_paid=None)

    def apply_outcomes(self, conn: sqlite3.Connection, outcomes: list[BookingOutcome]) -> None:
        for o in outcomes:
            if o.booked:
                conn.execute(
                    """
                    UPDATE nightly_inventory
                    SET status = 'booked', booked_price = ?, listed_price = COALESCE(listed_price, ?)
                    WHERE property_id = ? AND stay_date = ?
                    """,
                    (o.price_paid, o.price_paid, self.property_id, o.stay_date.isoformat()),
                )
            else:
                conn.execute(
                    """
                    UPDATE nightly_inventory
                    SET status = 'available', booked_price = NULL
                    WHERE property_id = ? AND stay_date = ? AND status != 'blocked'
                    """,
                    (self.property_id, o.stay_date.isoformat()),
                )
        conn.commit()

    def seed_listed_prices(self, conn: sqlite3.Connection) -> int:
        n = 0
        for stay in self.stay_dates():
            row = conn.execute(
                "SELECT 1 FROM nightly_inventory WHERE property_id = ? AND stay_date = ?",
                (self.property_id, stay.isoformat()),
            ).fetchone()
            if row:
                continue
            listed = FLAT_SEASONAL_PRICE
            if stay.weekday() in {4, 5}:
                listed = 880.0
            conn.execute(
                """
                INSERT INTO nightly_inventory (
                    property_id, stay_date, listed_price, status, day_of_week, evidence_kind
                ) VALUES (?, ?, ?, 'available', ?, 'skeleton')
                """,
                (self.property_id, stay.isoformat(), listed, stay.weekday()),
            )
            n += 1
        conn.commit()
        return n
