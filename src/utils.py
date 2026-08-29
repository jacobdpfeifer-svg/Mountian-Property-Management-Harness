"""Shared date / season / lead-time utilities."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def month_day(d: date) -> str:
    return f"{d.month:02d}-{d.day:02d}"


def in_md_window(d: date, start_md: str, end_md: str) -> bool:
    """Inclusive month-day window; supports wrap across year boundary."""
    md = month_day(d)
    if start_md <= end_md:
        return start_md <= md <= end_md
    return md >= start_md or md <= end_md


def season_for(d: date, seasons: dict[str, Any]) -> tuple[str, float]:
    for name, cfg in seasons.items():
        if in_md_window(d, cfg["start"], cfg["end"]):
            return name, float(cfg.get("base_multiplier", 1.0))
    return "default", 1.0


def lead_time_multiplier(lead_days: int | None, curves: list[dict[str, Any]]) -> float:
    if lead_days is None:
        return 1.0
    for curve in curves:
        if int(curve["min_days"]) <= lead_days <= int(curve["max_days"]):
            return float(curve["multiplier"])
    return 1.0


def round_price(value: float, round_to: int = 5) -> float:
    if round_to <= 0:
        return round(value, 2)
    return float(round(value / round_to) * round_to)


def round_price_conservative(value: float, anchor: float | None, round_to: int = 5) -> float:
    """Round to the price grid WITHOUT ever moving further from `anchor` than `value`.

    Nearest-multiple rounding can breach a hard guardrail: a +12% cap on $480 gives
    $537.60, which rounds up to $540 = +12.5%. Guardrails are invariants, so rounding
    must be conservative — floor an increase, ceil a decrease.
    """
    import math

    if round_to <= 0:
        return round(value, 2)
    if anchor is None:
        return float(round(value / round_to) * round_to)
    if value > anchor:
        return float(math.floor(value / round_to) * round_to)
    if value < anchor:
        return float(math.ceil(value / round_to) * round_to)
    return float(round(value / round_to) * round_to)
