"""Examiner-owned baseline policy labels (scoring only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from proving_ground_exam.scoring.demand import FLAT_SEASONAL_PRICE, oracle_price


@dataclass(frozen=True)
class BaselineSpec:
    policy_id: str
    description: str


BASELINES: tuple[BaselineSpec, ...] = (
    BaselineSpec("flat_seasonal", f"Fixed ${FLAT_SEASONAL_PRICE:.0f} every night"),
    BaselineSpec("comp_median_follower", "Comp-median follower from DB snapshots"),
    BaselineSpec("moat_off", "Engine with sqi.enabled=false"),
    BaselineSpec("oracle", "RevPAN-optimal from examiner demand curve"),
    BaselineSpec("engine", "Production generate_recommendations path"),
)


def flat_price(_stay: date, _demand: float) -> float:
    return FLAT_SEASONAL_PRICE


def oracle_policy(_stay: date, demand: float) -> float:
    return oracle_price(demand)
