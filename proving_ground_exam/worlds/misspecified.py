"""Demand worlds that are not the engine's own S(p).

These are gates for later arms. They are not the live demand model and they
do not change default.yaml.
"""

from __future__ import annotations

import math
import random


def linear_engine_prob(price: float, reference: float, beta: float = -1.5) -> float:
    """The engine-shaped curve the misspecified worlds must be able to disagree with."""
    if reference <= 0:
        return 0.0
    ratio = price / reference
    return max(0.0, min(1.0, 0.55 + beta * 0.2 * (ratio - 1.0)))


def kinked_wtp_prob(price: float, reference: float, kink: float = 1.15) -> float:
    """Flat willingness below a kink, then a steep drop. A PODS-style template."""
    if reference <= 0 or price < 0:
        return 0.0
    ratio = price / reference
    if ratio <= kink:
        return 0.62
    drop = (ratio - kink) / kink
    return max(0.0, 0.62 - 1.4 * drop)


def lognormal_price_prob(price: float, reference: float, sigma: float = 0.35) -> float:
    """Purchase probability falls with log price, not with a linear gap."""
    if price <= 0 or reference <= 0:
        return 0.0
    z = math.log(price / reference) / sigma
    return max(0.0, min(1.0, 0.5 * math.erfc(z / math.sqrt(2.0))))


def gamma_frailty_count(mean: float, frailty: float, rng: random.Random) -> float:
    """Over-dispersed weekly demand. frailty is the gamma shape; 1 is very over-dispersed."""
    if mean < 0 or frailty <= 0:
        raise ValueError("demand mean and frailty must be positive")
    scale = 1.0 / frailty
    multiplier = rng.gammavariate(frailty, scale)
    return mean * multiplier


def strategic_waiter_prob(price: float, reference: float, lead_days: int) -> float:
    """Shoppers who wait when the lead is long, even if the price is fair."""
    base = kinked_wtp_prob(price, reference)
    if lead_days > 60:
        return base * 0.45
    return base


def channel_lag_double_book_risk(open_channels: int) -> str:
    """More than one channel still open on the same night is a risk flag, not a price."""
    if open_channels < 0:
        return "unavailable"
    if open_channels > 1:
        return "double_book_risk"
    return "single_channel"
