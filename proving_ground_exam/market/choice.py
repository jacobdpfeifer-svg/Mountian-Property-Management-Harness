"""Mixed logit on total stay price. Gumbel shocks come from the shopper, not from prices."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from proving_ground_exam.market.shoppers import Shopper


@dataclass(frozen=True)
class Alternative:
    alt_id: str
    kind: str  # own | comp | outside
    sleeps: int
    quality: float
    nightly: float | None  # None for the outside option


def stay_nights(check_in: date, los: int) -> list[date]:
    return [check_in + timedelta(days=i) for i in range(los)]


def choose(
    shopper: Shopper,
    alternatives: list[Alternative],
    *,
    free: dict[str, set[date]],
    median: float,
    fit_penalty: float,
    fit_ratio: float,
    season_end: date,
) -> str:
    """Return the chosen alt_id. Infeasible options get utility -inf and cannot win
    unless every option is infeasible, in which case the outside option wins.
    """
    nights = stay_nights(shopper.check_in, shopper.los)
    best_id = "outside"
    best_u = -1e18
    for alt in alternatives:
        shock = shopper.gumbels.get(alt.alt_id, 0.0)
        if alt.kind == "outside":
            utility = 0.0 + shock
        else:
            if shopper.check_in > season_end or nights[-1] > season_end:
                utility = -1e18
            elif any(night not in free.get(alt.alt_id, set()) for night in nights):
                utility = -1e18
            elif alt.nightly is None:
                utility = -1e18
            elif alt.nightly > shopper.wtp_multiplier * median:
                utility = -1e18
            else:
                fit = fit_penalty if shopper.party < fit_ratio * alt.sleeps else 0.0
                utility = (
                    alt.quality
                    + fit
                    + shopper.price_coef * math.log(max(alt.nightly, 1.0) / median)
                    + shock
                )
        if utility > best_u:
            best_u = utility
            best_id = alt.alt_id
    return best_id
