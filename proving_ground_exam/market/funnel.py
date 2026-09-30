"""Inquiry conversion and cancellation hazard. Levels are assumed and swept."""

from __future__ import annotations

from proving_ground_exam.market.parameters import value_of
from proving_ground_exam.market.shoppers import Shopper


def converts(shopper: Shopper, cal: dict) -> bool:
    return shopper.convert_u < value_of(cal["conversion"])


def cancel_hazard(lead_days: int, cal: dict) -> float:
    table = cal["cancel_hazard"]
    if lead_days >= 60:
        return value_of(table["ge_60"])
    if lead_days >= 21:
        return value_of(table["ge_21"])
    if lead_days >= 8:
        return value_of(table["ge_8"])
    return value_of(table["ge_0"])
