"""Mixed logit on total stay price. Gumbel shocks come from the shopper, not from prices."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from proving_ground_exam.market.shoppers import Shopper


@dataclass(frozen=True)
class Alternative:
    alt_id: str
    kind: str  # own | comp | outside
    sleeps: int
    quality: float
    nightly: float | None  # None for the outside option
    # v2: guest-paid fees for this shopper's whole stay (cleaning, per-guest,
    # insurance) and the home's value relative to the market reference. The
    # defaults reproduce v1 exactly.
    fees: float = 0.0
    value_index: float = 1.0


def all_in_nightly(alt: Alternative, shopper: Shopper, fee_salience: float = 1.0) -> float:
    """What the shopper compares: nightly rate plus the salient share of fees per night.

    Platforms must show the total price (FTC 2024 rule for short-term lodging),
    so fees count in full by default. A smaller salience models drip display.
    """
    assert alt.nightly is not None
    return alt.nightly + fee_salience * alt.fees / shopper.los


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
    fee_salience: float = 1.0,
    enforce_capacity: bool = False,
) -> float:
    """Utility of one alternative. Infeasible options are -1e18 and cannot win.

    ``median`` is the market reference for this stay (all-in under v2). A home's
    reference is that times its ``value_index``: the cap is WTP × reference and
    the price term is log(all-in / reference).
    """
    shock = shopper.gumbels.get(alt.alt_id, 0.0)
    if alt.kind == "outside":
        return outside_utility + shock
    nights = stay_nights(shopper.check_in, shopper.los)
    if shopper.check_in > season_end or nights[-1] > season_end:
        return -1e18
    if any(night not in free.get(alt.alt_id, set()) for night in nights):
        return -1e18
    if enforce_capacity and shopper.party > alt.sleeps:
        return -1e18
    if alt.nightly is None:
        return -1e18
    price = all_in_nightly(alt, shopper, fee_salience)
    anchor = median * alt.value_index
    if price > shopper.wtp_multiplier * anchor:
        return -1e18
    fit = 0.0
    if not ignore_fit and shopper.party < fit_ratio * alt.sleeps:
        fit = fit_penalty
    return (
        alt.quality
        + fit
        + shopper.price_coef * math.log(max(price, 1.0) / anchor)
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
    fee_salience: float = 1.0,
    enforce_capacity: bool = False,
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
            fee_salience=fee_salience,
            enforce_capacity=enforce_capacity,
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
    fee_salience: float = 1.0,
    enforce_capacity: bool = False,
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
    if enforce_capacity and shopper.party > alt.sleeps:
        return "capacity"
    if alt.nightly is None or all_in_nightly(alt, shopper, fee_salience) > (
        shopper.wtp_multiplier * median * alt.value_index
    ):
        return "above_wtp"
    kwargs: dict[str, Any] = dict(
        free=free,
        median=median,
        fit_penalty=fit_penalty,
        fit_ratio=fit_ratio,
        season_end=season_end,
        outside_utility=outside_utility,
        fee_salience=fee_salience,
        enforce_capacity=enforce_capacity,
    )
    utility = alternative_utility(shopper, alt, **kwargs)
    without_fit = alternative_utility(shopper, alt, ignore_fit=True, **kwargs)
    chosen_u = -1e18 if chosen is None else alternative_utility(shopper, chosen, **kwargs)
    fit_active = shopper.party < fit_ratio * alt.sleeps
    if fit_active and without_fit > chosen_u >= utility:
        return "fit"
    if chosen is None or chosen.kind == "outside" or chosen.nightly is None:
        return "outside"
    if all_in_nightly(alt, shopper, fee_salience) > all_in_nightly(chosen, shopper, fee_salience) + 1.0:
        return "price"
    return "other"
