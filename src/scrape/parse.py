"""Price extraction and sanity validation for scraped market data.

The dangerous failure mode of a scraper is NOT an exception — it is a markup or
schema change that yields plausible-looking garbage. A parser returning a constant,
or off by a factor of the stay length, will sail through any try/except and quietly
poison the ceiling. Everything here is written to fail loudly and to be checkable.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Any

# "3 nights x $94.00"  /  "2 nights x $1,240"
_BREAKDOWN = re.compile(r"(\d+)\s*nights?\s*x\s*\$?([\d,]+(?:\.\d+)?)", re.I)
_QUALIFIER = re.compile(r"(\d+)\s*nights?", re.I)


def _to_float(text: str) -> float | None:
    try:
        return float(str(text).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def nightly_price(listing: dict[str, Any], window_nights: int) -> float | None:
    """Nightly rate from an Airbnb search result.

    Airbnb quotes a stay total plus a breakdown string; `price.unit.amount` is the
    TOTAL for the searched window, not a nightly rate. Dividing by the wrong night
    count is the single easiest way to produce a plausible but wrong comp set, so the
    breakdown string (which states its own night count) is preferred over arithmetic.
    """
    price = listing.get("price") or {}

    for item in price.get("break_down") or []:
        m = _BREAKDOWN.search(str(item.get("description", "")))
        if m:
            nights = int(m.group(1))
            amount = _to_float(m.group(2))
            if nights > 0 and amount:
                return amount

    unit = price.get("unit") or {}
    amount = _to_float(unit.get("amount"))
    if amount is None:
        return None
    m = _QUALIFIER.search(str(unit.get("qualifier", "")))
    nights = int(m.group(1)) if m else window_nights
    return amount / nights if nights > 0 else None


@dataclass
class SweepValidation:
    ok: bool
    listings: int
    parsed: int
    rejected: int
    reasons: list[str] = field(default_factory=list)

    @property
    def parse_rate(self) -> float:
        return self.parsed / self.listings if self.listings else 0.0


def validate_sweep(
    prices: list[float],
    listings_seen: int,
    policy: dict[str, Any],
) -> SweepValidation:
    """Reject a sweep that looks like a broken parser rather than a real market."""
    cfg = policy.get("scrape", {}).get("validation", {})
    min_listings = int(cfg.get("min_listings_per_sweep", 25))
    min_parse_rate = float(cfg.get("min_parse_rate", 0.70))
    max_identical = float(cfg.get("max_identical_share", 0.60))
    lo = float(cfg.get("min_plausible_price", 20))
    hi = float(cfg.get("max_plausible_price", 20000))

    reasons: list[str] = []
    clean = [p for p in prices if lo <= p <= hi]
    rejected = len(prices) - len(clean)

    if listings_seen < min_listings:
        reasons.append(f"only {listings_seen} listings (need {min_listings}) — sweep likely blocked")
    if listings_seen and (len(clean) / listings_seen) < min_parse_rate:
        reasons.append(
            f"parse rate {len(clean) / listings_seen:.0%} below {min_parse_rate:.0%} — parser likely broken"
        )
    if len(clean) >= 10:
        mode_count = max(clean.count(p) for p in set(clean))
        if mode_count / len(clean) > max_identical:
            reasons.append(
                f"{mode_count / len(clean):.0%} of prices identical — parser likely returning a constant"
            )
        if statistics.pstdev(clean) == 0:
            reasons.append("zero price variance across the market")

    return SweepValidation(not reasons, listings_seen, len(clean), rejected, reasons)


def validate_observation(
    price: float,
    previous: float | None,
    policy: dict[str, Any],
) -> tuple[bool, str | None]:
    """Reject an individual comp reading that moved implausibly since last capture."""
    cfg = policy.get("scrape", {}).get("validation", {})
    lo = float(cfg.get("min_plausible_price", 20))
    hi = float(cfg.get("max_plausible_price", 20000))
    max_ratio = float(cfg.get("max_change_ratio", 5.0))

    if not (lo <= price <= hi):
        return False, f"${price:.0f} outside plausible band ${lo:.0f}-${hi:.0f}"
    if previous and previous > 0:
        ratio = price / previous
        if ratio > max_ratio or ratio < 1 / max_ratio:
            return False, f"${price:.0f} is {ratio:.1f}x the previous ${previous:.0f}"
    return True, None
