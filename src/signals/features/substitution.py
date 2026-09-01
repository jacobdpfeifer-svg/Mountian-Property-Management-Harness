"""Cross-valley substitution index (WP-11).

Compare home price-per-SQI against substitute markets' price-per-SQI.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.signals.features.sqi import compute_sqi
from src.signals.store import SignalStore


@dataclass
class SubstitutionResult:
    home_market: str
    index: float  # >1 means substitutes look cheaper per quality (share bleed risk)
    details: dict[str, float]


def substitute_prices_for(
    conn: sqlite3.Connection,
    *,
    as_of: date,
    target_date: date,
    markets: list[str],
    percentile: float = 0.75,
) -> dict[str, float]:
    """Pull substitute-market p75 from market_snapshots (leak-free on as_of)."""
    prices: dict[str, float] = {}
    for region in markets:
        row = conn.execute(
            """
            SELECT p75 FROM market_snapshots
            WHERE region = ? AND stay_date = ? AND as_of <= ?
            ORDER BY as_of DESC LIMIT 1
            """,
            (region, target_date.isoformat(), as_of.isoformat()),
        ).fetchone()
        if row and row["p75"] is not None:
            prices[region] = float(row["p75"])
    return prices


def substitution_index(
    store: SignalStore,
    *,
    home_market: str,
    home_price: float,
    as_of: date,
    target_date: date,
    substitute_prices: dict[str, float],
) -> SubstitutionResult:
    home_sqi = compute_sqi(store, home_market, target_date, as_of).sqi or 1.0
    home_ppq = home_price / max(home_sqi, 0.1)
    details: dict[str, float] = {}
    ratios = []
    for mid, price in substitute_prices.items():
        sqi = compute_sqi(store, mid, target_date, as_of).sqi or 1.0
        ppq = price / max(sqi, 0.1)
        ratio = home_ppq / max(ppq, 1.0)
        details[mid] = ratio
        ratios.append(ratio)
    idx = sum(ratios) / len(ratios) if ratios else 1.0
    return SubstitutionResult(home_market=home_market, index=idx, details=details)


def apply_substitution_cap(
    ceiling: float,
    sub: SubstitutionResult,
    policy: dict[str, Any],
) -> tuple[float, float]:
    """Return (capped_ceiling, reduction_pct)."""
    cfg = policy.get("substitution", {})
    threshold = float(cfg.get("index_threshold", 1.15))
    max_red = float(cfg.get("max_ceiling_reduction_pct", 0.15))
    if sub.index <= threshold:
        return ceiling, 0.0
    factor = min(1.0, 1.0 / sub.index)
    capped = ceiling * factor
    min_allowed = ceiling * (1.0 - max_red)
    return max(capped, min_allowed), 1.0 - max(capped, min_allowed) / ceiling
