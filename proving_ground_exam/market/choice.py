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


def alternative_utility(
    shopper: Shopper,
    alt: Alternative,
    *,
    free: dict[str, set[date]],
    median: float,
    fit_penalty: float,
    fit_ratio: float,
    season_end: date,
    outside_utility: float = 0.0,
    ignore_fit: bool = False,
) -> float:
    """Utility of one alternative. Infeasible options are -1e18 and cannot win."""
    shock = shopper.gumbels.get(alt.alt_id, 0.0)
    if alt.kind == "outside":
        return outside_utility + shock
    nights = stay_nights(shopper.check_in, shopper.los)
    if shopper.check_in > season_end or nights[-1] > season_end:
        return -1e18
    if any(night not in free.get(alt.alt_id, set()) for night in nights):
        return -1e18
    if alt.nightly is None or alt.nightly > shopper.wtp_multiplier * median:
        return -1e18
    fit = 0.0
    if not ignore_fit and shopper.party < fit_ratio * alt.sleeps:
        fit = fit_penalty
    return (
        alt.quality
        + fit
        + shopper.price_coef * math.log(max(alt.nightly, 1.0) / median)
        + shock
    )


def choose(
    shopper: Shopper,
    alternatives: list[Alternative],
    *,
    free: dict[str, set[date]],
    median: float,
    fit_penalty: float,
    fit_ratio: float,
    season_end: date,
    outside_utility: float = 0.0,
) -> str:
    """Return the chosen alt_id. Infeasible options get utility -inf and cannot win
    unless every option is infeasible, in which case the outside option wins.
    """
    best_id = "outside"
    best_u = -1e18
    for alt in alternatives:
        utility = alternative_utility(
            shopper,
            alt,
            free=free,
            median=median,
            fit_penalty=fit_penalty,
            fit_ratio=fit_ratio,
            season_end=season_end,
            outside_utility=outside_utility,
        )
        if utility > best_u:
            best_u = utility
            best_id = alt.alt_id
    return best_id


def loss_reason(
    shopper: Shopper,
    alt: Alternative,
    chosen: Alternative | None,
    *,
    free: dict[str, set[date]],
    median: float,
    fit_penalty: float,
    fit_ratio: float,
    season_end: date,
    outside_utility: float = 0.0,
) -> str:
    """Why this own listing was not the choice. Does not affect choose().

    ``unavailable`` and ``above_wtp`` are hard screens. ``fit`` means the
    party-size penalty flipped the winner. ``outside`` means the listing was
    feasible but the shopper chose the outside option; that is intentionally
    not called a price loss because quality and the random utility shock can
    also explain it. ``other`` is a loss to a different listing.
    """
    if chosen is not None and alt.alt_id == chosen.alt_id:
        return "chosen"
    nights = stay_nights(shopper.check_in, shopper.los)
    if shopper.check_in > season_end or nights[-1] > season_end:
        return "outside_window"
    if any(night not in free.get(alt.alt_id, set()) for night in nights):
        return "unavailable"
    if alt.nightly is None or alt.nightly > shopper.wtp_multiplier * median:
        return "above_wtp"
    kwargs = dict(
        free=free,
        median=median,
        fit_penalty=fit_penalty,
        fit_ratio=fit_ratio,
        season_end=season_end,
        outside_utility=outside_utility,
    )
    utility = alternative_utility(shopper, alt, **kwargs)
    without_fit = alternative_utility(shopper, alt, ignore_fit=True, **kwargs)
    chosen_u = -1e18 if chosen is None else alternative_utility(shopper, chosen, **kwargs)
    fit_active = shopper.party < fit_ratio * alt.sleeps
    if fit_active and without_fit > chosen_u >= utility:
        return "fit"
    if chosen is None or chosen.kind == "outside" or chosen.nightly is None:
        return "outside"
    if alt.nightly > chosen.nightly + 1.0:
        return "price"
    return "other"
