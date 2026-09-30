"""Flag-gated pricing adjustments. Every function is a no-op unless the caller asks.

The policy block is `models.<name>.enabled`. Missing keys stay off. These helpers
do not read the clock and do not write the database.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Callable

import numpy as np

MODEL_NAMES = (
    "learned_elasticity",
    "demand_shifts_price",
    "booking_horizon",
    "stay_pricing",
    "portfolio_pricing",
)
TWINS = ("overlook_ridge", "summit_haus")
BETA_LO = -2.5
BETA_HI = -0.3


def enabled(policy: dict[str, Any], name: str) -> bool:
    block = (policy.get("models") or {}).get(name) or {}
    return bool(block.get("enabled", False))


def unconstrained_optimum(price_ref: float, beta: float) -> float:
    if price_ref <= 0 or beta >= 0:
        return price_ref
    return price_ref * (beta - 1.0) / (2.0 * beta)


def clip_beta(beta: float) -> float:
    return float(min(BETA_HI, max(BETA_LO, beta)))


def estimate_beta(prices: list[float], booked: list[bool]) -> float | None:
    """Book-rate slope above versus below the median as-of price.

    Returns None when either side has fewer than 8 nights or the two median
    prices are the same. The caller then keeps the prior.
    """
    if len(prices) != len(booked) or len(prices) < 16:
        return None
    ordered = sorted(zip(prices, booked, strict=True), key=lambda item: item[0])
    mid = len(ordered) // 2
    lo, hi = ordered[:mid], ordered[mid:]
    if len(lo) < 8 or len(hi) < 8:
        return None
    p_lo = sum(p for p, _ in lo) / len(lo)
    p_hi = sum(p for p, _ in hi) / len(hi)
    if p_lo <= 0 or abs(p_hi - p_lo) < 1e-6:
        return None
    r_lo = sum(1 for _, flag in lo if flag) / len(lo)
    r_hi = sum(1 for _, flag in hi if flag) / len(hi)
    if r_lo <= 0:
        return None
    slope = ((r_hi / r_lo) - 1.0) / ((p_hi / p_lo) - 1.0)
    return clip_beta(slope)


def posterior_beta(prior: float, beta_hat: float | None, n: int) -> float:
    if beta_hat is None or n <= 0:
        return prior
    return (40.0 * prior + n * beta_hat) / (40.0 + n)


def _generator(*parts: object) -> np.random.Generator:
    raw = ":".join(str(part) for part in parts).encode()
    seed = int.from_bytes(hashlib.sha256(raw).digest()[:8], "little")
    return np.random.Generator(np.random.PCG64(seed))


def thompson_beta(
    beta_post: float,
    n: int,
    *,
    property_id: str,
    stay_date: date,
    as_of: date,
    explore: bool,
) -> float:
    if not explore:
        return clip_beta(beta_post)
    scale = 0.35 / (40.0 + n) ** 0.5
    draw = float(_generator(property_id, stay_date.isoformat(), as_of.isoformat()).normal(beta_post, scale))
    return clip_beta(draw)


def apply_interim_guard(beta: float, *, season: str, pacing_ratio: float | None, lead_days: int | None) -> float:
    if (
        season == "peak_ski"
        and pacing_ratio is not None
        and pacing_ratio < 0.70
        and lead_days is not None
        and lead_days <= 21
    ):
        return min(beta, -1.05)
    return beta


def demand_price_factor(
    *,
    pacing_ratio: float | None,
    sqi: float | None,
    event: bool,
    macro_z: float | None = None,
) -> float:
    pace = 1.0 if pacing_ratio is None else float(pacing_ratio)
    snow = 1.0 if sqi is None else float(sqi)
    raw = 1.0 + 0.15 * (pace - 1.0) + 0.10 * (snow - 1.0) + (0.10 if event else 0.0)
    if macro_z is not None:
        raw += 0.05 * float(macro_z)
    return float(min(1.20, max(0.85, raw)))


def shrunk_lead_rate(hits: int, n: int, prior: float, k: float = 12.0) -> float:
    return (hits + k * prior) / (n + k) if n + k else prior


def horizon_value(prob: float, price: float, continuation: float) -> float:
    return prob * price + (1.0 - prob) * continuation


def best_horizon_price(
    grid: list[float],
    probs: list[float],
    continuation: float,
) -> tuple[float, float]:
    """Return (price, value) maximizing prob*P + (1-prob)*C."""
    best_price = grid[0]
    best_value = float("-inf")
    for price, prob in zip(grid, probs, strict=True):
        value = horizon_value(prob, price, continuation)
        if value > best_value:
            best_value = value
            best_price = price
    return best_price, best_value


def candidate_min_stays(rule_nights: list[int], gap_nights: int | None, standing: int | None) -> list[int]:
    found = sorted({int(n) for n in rule_nights if int(n) > 0})
    if gap_nights and standing and int(gap_nights) < int(standing) and int(gap_nights) not in found:
        found.append(int(gap_nights))
        found.sort()
    return found


def stay_choice(
    anchor: date,
    nightly_prices: dict[date, float],
    candidates: list[int],
    standing: int,
    orphan_gap: int,
) -> tuple[int, float]:
    """Pick the min-stay with the best value per night. Adjustment is dollars on the anchor night.

    A candidate is disqualified when any night in the stay has no price. An orphan
    gap shorter than the candidate is charged half a night's price per leftover night.
    The adjustment is capped at ±8% of the anchor night's myopic price.
    """
    myopic = nightly_prices[anchor]

    def value_of(length: int) -> float | None:
        total = 0.0
        for offset in range(length):
            price = nightly_prices.get(anchor + timedelta(days=offset))
            if price is None:
                return None
            total += price
        if orphan_gap > 0 and orphan_gap < length:
            total -= 0.5 * myopic * orphan_gap
        return total

    standing_value = value_of(standing)
    if standing_value is None:
        return standing, 0.0
    best_length = standing
    best_per = standing_value / standing
    best_value = standing_value
    for length in candidates:
        total = value_of(length)
        if total is None or length <= 0:
            continue
        per = total / length
        if per > best_per:
            best_per = per
            best_length = length
            best_value = total
    raw = (best_value - standing_value) / best_length
    cap = 0.08 * myopic
    return best_length, float(min(cap, max(-cap, raw)))


def portfolio_lambda(price_self: float, price_other: float) -> float:
    gap = abs(price_self - price_other) / max(price_other, 1.0)
    return 0.15 if gap < 0.10 else 0.05


def portfolio_pair(property_id: str) -> str | None:
    if property_id not in TWINS:
        return None
    return TWINS[1] if property_id == TWINS[0] else TWINS[0]


# Daily cancel hazards from the frozen simulator calibration. A lead-only
# survival rate scales every price on a night by the same constant, so it does
# not move the RevPAN argmax. Replay uses it to label revenue, not to reprice.
_CANCEL_STEPS = ((60, 0.004), (21, 0.002), (8, 0.001), (0, 0.0004))


def cancel_daily_hazard(lead_days: int) -> float:
    for threshold, rate in _CANCEL_STEPS:
        if lead_days >= threshold:
            return rate
    return 0.0004


def cancel_survival(lead_days: int) -> float:
    """Probability a booking made `lead_days` out is still in place at check-in."""
    survival = 1.0
    for day in range(max(0, int(lead_days)), 0, -1):
        survival *= 1.0 - cancel_daily_hazard(day)
    return survival


@dataclass
class ModelAdjustment:
    """What the enabled flags change before the RevPAN search.

    `probability` is the original object when every flag is off.
    `reasons` are (code, message, dollar contribution) before guardrails.
    `objective` replaces expected RevPAN only for the booking-horizon flag.
    `price_delta` is added to the searched optimum only for stay pricing.
    """

    probability: Any
    reasons: list[tuple[str, str, float]]
    objective: Callable[[float], float] | None
    price_delta: float
    min_stay_nights: int | None


def _any_model(policy: dict[str, Any]) -> bool:
    return any(enabled(policy, name) for name in MODEL_NAMES)


def _pooled_book_outcomes(
    conn: sqlite3.Connection,
    as_of: date,
    season: str,
    seasons: dict[str, Any],
) -> tuple[list[float], list[bool]]:
    from src.runcache import memo
    from src.utils import parse_date, season_for

    def _load() -> tuple[list[float], list[bool]]:
        prices: list[float] = []
        booked: list[bool] = []
        rows = conn.execute(
            """
            SELECT listed_price, status, booked_at, stay_date
            FROM nightly_inventory
            WHERE stay_date < ? AND listed_price IS NOT NULL AND listed_price > 0
            """,
            (as_of.isoformat(),),
        )
        for row in rows:
            if season_for(parse_date(row["stay_date"]), seasons)[0] != season:
                continue
            sold = row["status"] == "booked" and (
                not row["booked_at"] or parse_date(row["booked_at"]) <= as_of
            )
            prices.append(float(row["listed_price"]))
            booked.append(sold)
        return prices, booked

    return memo(("m1_outcomes", id(conn), as_of.isoformat(), season), _load)


def _macro_z(conn: sqlite3.Connection, as_of: date, market_id: str) -> float | None:
    from src.signals.store import SignalStore

    row = SignalStore(conn).latest_observation(
        as_of=as_of,
        signal_key="macro.consumer_confidence",
        market_id=market_id,
        effective_date=as_of,
    )
    if row is None or row["value"] is None:
        return None
    return float(row["value"])


def apply_models(
    conn: sqlite3.Connection,
    feat: Any,
    policy: dict[str, Any],
    probability: Any,
    *,
    as_of: date,
    floor: float,
    ceil: float,
    sqi: float | None,
    steps: int,
    portfolio_quotes: dict[tuple[str, date], float] | None = None,
) -> ModelAdjustment:
    """Apply M1–M5. Missing or disabled flags leave `probability` untouched."""
    if not _any_model(policy):
        return ModelAdjustment(probability, [], None, 0.0, None)

    from src.bookprob import _lead_bucket, _lead_observations

    bp = probability
    reasons: list[tuple[str, str, float]] = []
    seasons = policy.get("seasons", {})

    if enabled(policy, "learned_elasticity"):
        prior = float(bp.beta)
        prices, booked = _pooled_book_outcomes(conn, as_of, feat.season, seasons)
        hat = estimate_beta(prices, booked)
        post = clip_beta(posterior_beta(prior, hat, len(prices)))
        blackout = float(feat.demand_strength) >= 0.85
        drawn = thompson_beta(
            post,
            len(prices),
            property_id=feat.property_id,
            stay_date=feat.stay_date,
            as_of=as_of,
            explore=not blackout,
        )
        guarded = apply_interim_guard(
            drawn,
            season=feat.season,
            pacing_ratio=bp.pacing_ratio,
            lead_days=feat.lead_time_days,
        )
        before = unconstrained_optimum(bp.price_ref, prior)
        after = unconstrained_optimum(bp.price_ref, post)
        bp = replace(bp, beta=guarded)
        reasons.append((
            "learned_elasticity",
            f"Posterior beta {post:.2f} from prior {prior:.2f} on {len(prices)} nights",
            after - before,
        ))

    if enabled(policy, "demand_shifts_price"):
        macro = _macro_z(conn, as_of, getattr(feat, "market_id", "grand_home"))
        factor = demand_price_factor(
            pacing_ratio=bp.pacing_ratio,
            sqi=sqi,
            event=bool(feat.demand_event),
            macro_z=macro,
        )
        before = unconstrained_optimum(bp.price_ref, bp.beta)
        shifted = bp.price_ref * factor
        after = unconstrained_optimum(shifted, bp.beta)
        bp = replace(bp, price_ref=shifted)
        reasons.append((
            "demand_level",
            f"Reference price scaled by {factor:.2f} for pace, snow, and events",
            after - before,
        ))

    if enabled(policy, "portfolio_pricing"):
        pair = portfolio_pair(feat.property_id)
        other = None
        if pair is not None:
            other = (portfolio_quotes or {}).get((pair, feat.stay_date))
            if other is None:
                row = conn.execute(
                    """
                    SELECT listed_price FROM nightly_inventory
                    WHERE property_id = ? AND stay_date = ?
                    """,
                    (pair, feat.stay_date.isoformat()),
                ).fetchone()
                if row is not None and row["listed_price"]:
                    other = float(row["listed_price"])
        if pair is not None and other:
            self_price = float(feat.listed_price or bp.price_ref)
            lam = portfolio_lambda(self_price, other)
            before = unconstrained_optimum(bp.price_ref, bp.beta)
            shifted = bp.price_ref * (1.0 - lam)
            after = unconstrained_optimum(shifted, bp.beta)
            bp = replace(bp, price_ref=shifted)
            reasons.append((
                "portfolio_cannibalization",
                f"Twin {pair} is ${other:.0f}; reference scaled by {1.0 - lam:.2f}",
                after - before,
            ))

    objective = None
    if enabled(policy, "booking_horizon") and ceil > floor:
        leadb = _lead_bucket(feat.lead_time_days)
        obs = _lead_observations(conn, as_of, seasons)
        pool = [item for item in obs if item[0] == leadb] if leadb != "unknown" else []
        hits = sum(1 for item in pool if item[2])
        rate = shrunk_lead_rate(hits, len(pool), float(bp.p_ref))
        continuation = rate * (floor + ceil) / 2.0
        grid = [float(p) for p in np.linspace(floor, ceil, max(2, steps))]
        revpan_price = grid[int(np.argmax([p * bp.prob_at(p) for p in grid]))]
        horizon_price, _ = best_horizon_price(
            grid, [bp.prob_at(p) for p in grid], continuation
        )

        def objective(price: float, _bp=bp, _c=continuation) -> float:
            return horizon_value(_bp.prob_at(price), price, _c)

        reasons.append((
            "booking_horizon",
            f"Hold value ${continuation:.0f}; horizon price ${horizon_price:.0f}",
            horizon_price - revpan_price,
        ))

    price_delta = 0.0
    min_stay_nights = None
    if enabled(policy, "stay_pricing"):
        rules = (policy.get("min_stay_rules") or {}).get("by_season", {}).get(feat.season, [])
        rule_nights = [int(row["min_nights"]) for row in rules]
        standing = int(feat.min_stay or (policy.get("min_stay_rules") or {}).get("fallback_min_nights", 2))
        gap = int(feat.gap_size) if feat.is_orphan_gap else 0
        candidates = candidate_min_stays(rule_nights, gap or None, standing)
        horizon = max(candidates or [standing])
        nightly: dict[date, float] = {}
        rows = conn.execute(
            """
            SELECT stay_date, listed_price FROM nightly_inventory
            WHERE property_id = ? AND stay_date >= ? AND stay_date < ?
              AND listed_price IS NOT NULL AND listed_price > 0
            """,
            (
                feat.property_id,
                feat.stay_date.isoformat(),
                (feat.stay_date + timedelta(days=horizon)).isoformat(),
            ),
        )
        for row in rows:
            from src.utils import parse_date

            nightly[parse_date(row["stay_date"])] = float(row["listed_price"])
        if feat.stay_date not in nightly and feat.listed_price:
            nightly[feat.stay_date] = float(feat.listed_price)
        if feat.stay_date in nightly and candidates:
            chosen, delta = stay_choice(feat.stay_date, nightly, candidates, standing, gap)
            price_delta = delta
            if chosen != standing:
                min_stay_nights = chosen
            reasons.append((
                "stay_value",
                f"Stay length {chosen} versus standing {standing}",
                delta,
            ))

    return ModelAdjustment(bp, reasons, objective, price_delta, min_stay_nights)
