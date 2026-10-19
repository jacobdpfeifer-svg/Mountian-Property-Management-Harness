"""Field-test design. This module does not assign a live arm and does not push prices.

Assignment is by check-in week. A stay takes the arm of its check-in date.
The power table is here so a small effect is not expected to show up.
"""

from __future__ import annotations

import math
from datetime import date


def arm_for_checkin(check_in: date, *, epoch: date = date(2026, 11, 1)) -> str:
    """Alternate arms by ISO week offset from `epoch`. Whole stay follows check-in."""
    if check_in < epoch:
        return "unavailable"
    weeks = (check_in - epoch).days // 7
    return "treatment" if weeks % 2 else "control"


def power_table(effects: tuple[float, ...] = (0.02, 0.10, 0.33), *,
                weekly_sd: float = 0.18, n_weeks: int = 16) -> list[dict[str, float]]:
    """Rough two-arm power using a normal approximation. Not a licence to run the test."""
    rows = []
    se = weekly_sd * math.sqrt(2 / max(n_weeks, 1))
    for effect in effects:
        z = effect / se if se else 0.0
        # One-sided power at 5%: Phi(z - 1.645).
        power = 0.5 * math.erfc(-(z - 1.645) / math.sqrt(2))
        rows.append({"effect": effect, "se": round(se, 4), "power": round(power, 3)})
    return rows
