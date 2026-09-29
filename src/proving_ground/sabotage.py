"""Sabotage policies for harness acceptance tests (examiner-owned scoring only)."""

from __future__ import annotations

import random
from datetime import date

from proving_ground_exam.scoring.demand import FLAT_SEASONAL_PRICE


def broken_floor_price(_stay: date, _demand: float, floor: float = 425.0) -> float:
    return floor


def random_price(stay: date, _demand: float, seed: int = 0) -> float:
    rng = random.Random(seed + stay.toordinal())
    return float(rng.randint(9, 40) * 5)


def oracle_passes_l1_regret(regret: float, threshold: float = 0.05) -> bool:
    return regret <= threshold
