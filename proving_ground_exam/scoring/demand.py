"""W1 calm-season demand curve — examiner-owned, no engine imports."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

REFERENCE_PRICE = 640.0
PRICE_SENSITIVITY = 520.0
FLAT_SEASONAL_PRICE = 720.0

HOLIDAYS = {(12, 24), (12, 25), (12, 31), (1, 1)}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _round5(value: float) -> float:
    return float(round(value / 5) * 5)


def true_demand(
    stay_date: date,
    *,
    season_start: date,
    level: int,
    seed: int,
) -> float:
    """Hidden demand intensity for one night (engine must not read this)."""
    rng = random.Random(seed + stay_date.toordinal() * 31 + level * 10_000)
    idx = max(0, (stay_date - season_start).days)
    winter_wave = 0.5 + 0.5 * math.sin((idx / 166.0) * math.pi)
    weekend = 0.15 if stay_date.weekday() in {4, 5} else 0.0
    holiday = 0.22 if (stay_date.month, stay_date.day) in HOLIDAYS else 0.0
    noise = rng.uniform(-0.05, 0.05)
    shock = 0.0
    if level == 2 and date(stay_date.year, 1, 5) <= stay_date <= date(stay_date.year, 1, 9):
        shock = 0.10
    return _clamp(
        0.35 + 0.40 * winter_wave + weekend + holiday + shock + noise,
        0.05,
        0.98,
    )


def booking_probability(price: float, demand: float) -> float:
    penalty = (price - REFERENCE_PRICE) / PRICE_SENSITIVITY
    return _clamp(demand - penalty, 0.02, 0.96)


def oracle_price(demand: float) -> float:
    return _round5((PRICE_SENSITIVITY * demand + REFERENCE_PRICE) / 2)


def revpan_for_price(price: float, demand: float) -> float:
    return price * booking_probability(price, demand)


def oracle_revpan(demand: float) -> tuple[float, float]:
    price = oracle_price(demand)
    return price, revpan_for_price(price, demand)


@dataclass(frozen=True)
class NightScore:
    stay_date: date
    demand: float
    price: float
    book_prob: float
    revpan: float


def score_policy_nights(
    stay_dates: list[date],
    *,
    season_start: date,
    level: int,
    seed: int,
    price_for_night: Callable[[date, float], float],
) -> list[NightScore]:
    out: list[NightScore] = []
    for stay in stay_dates:
        demand = true_demand(stay, season_start=season_start, level=level, seed=seed)
        price = float(price_for_night(stay, demand))
        prob = booking_probability(price, demand)
        out.append(NightScore(
            stay_date=stay,
            demand=demand,
            price=price,
            book_prob=prob,
            revpan=price * prob,
        ))
    return out
