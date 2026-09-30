"""Noisy observation of competitor prices. The engine never reads the true price."""

from __future__ import annotations

import math

import numpy as np


def observe(
    true_price: float,
    rng: np.random.Generator,
    *,
    log_sigma: float,
    missing_prob: float,
    outage: bool,
) -> tuple[float | None, str]:
    if outage:
        return None, "failed"
    if float(rng.random()) < missing_prob:
        return None, "unavailable"
    noise = math.exp(float(rng.normal(0.0, log_sigma)))
    return round(true_price * noise, 2), "ok"
