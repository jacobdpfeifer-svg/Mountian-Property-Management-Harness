"""Competitor agents. Rules for the generalized tool follow PriceLabs' public description
in docs/research/dossiers/04_simulator_science.md. This is an emulator, not their code.
"""

from __future__ import annotations

from datetime import date, timedelta

from proving_ground_exam.market.parameters import season_of


def _is_weekend(day: date) -> bool:
    return day.weekday() in (4, 5)


def tool_price(
    day: date,
    *,
    base: float,
    holiday: bool,
    occupancy_30: float,
    lead_days: int,
    price_war: bool,
) -> float:
    season = season_of(day)
    factor = {"peak_ski": 1.15, "early_winter": 1.00, "shoulder_spring": 0.90}[season]
    if _is_weekend(day):
        factor *= 1.08
    if holiday:
        factor *= 1.20
    if lead_days <= 14:
        factor *= 0.92
    if occupancy_30 < 0.40:
        factor *= 0.90
    if price_war:
        factor *= 0.90
    return round(base * factor, 2)


def tool_min_stay(day: date, lead_days: int, behind: bool) -> int:
    stay = 3 if season_of(day) == "peak_ski" and lead_days > 14 else 2
    if behind:
        stay = max(1, stay - 1)
    return stay


def static_price(day: date, peak: float, other: float) -> float:
    return peak if season_of(day) == "peak_ski" else other


def occupancy(booked: set[date], start: date, horizon: int = 30) -> float:
    nights = [start + timedelta(days=i) for i in range(horizon)]
    if not nights:
        return 0.0
    return sum(1 for night in nights if night in booked) / len(nights)
