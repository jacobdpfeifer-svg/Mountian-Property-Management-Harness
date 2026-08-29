"""Cross-valley substitution index (WP-11).

Compare home price-per-SQI against substitute markets' price-per-SQI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.signals.features.sqi import compute_sqi
from src.signals.store import SignalStore


@dataclass
class SubstitutionResult:
    home_market: str
    index: float  # >1 means substitutes look cheaper per quality (share bleed risk)
    details: dict[str, float]


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
