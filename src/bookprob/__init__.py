"""Pooled booking-probability model — what makes RevPAN a real objective.

The v1 build declared RevPAN as the core metric but never estimated a booking
probability: `expected_book_prob` was written to the schema as NULL on every row,
and price was chosen by multiplying rules together. That optimizes a rate, not a
revenue-per-available-night.

Model (deliberately transparent, small-data safe) — FIRST-ORDER LINEAR DEMAND:

    p(book | P) = p_ref * (1 + beta * (P / P_ref - 1))    clamped to [0.001, 0.995]

A constant-elasticity form p = p_ref*(P/P_ref)**beta is the textbook choice but is
DEGENERATE for optimization: E[rev] = const * P**(1+beta) is monotone in P, so the
optimizer always returns the floor (|beta|>1) or the ceiling (|beta|<1) and never an
interior price. Linear demand makes expected revenue quadratic in P, so there is a
real interior optimum:

    P* = P_ref * (beta - 1) / (2 * beta)

which is above the reference price when demand is inelastic (beta=-0.65 -> 1.27x) and
below it when elastic (beta=-1.70 -> 0.79x). beta is the local slope of demand at
P_ref, not a global elasticity.

  * p_ref  — historical booking rate for the (season, demand_tier, dow_class) cell,
             shrunk toward the portfolio prior. Pooled across properties: per-property
             per-cell rates are single-digit-N and would overfit badly.
             DEMAND TIER is part of the cell because peak_ski spans 15 Dec - 31 Mar;
             without it a Christmas night is referenced against mid-January prices and
             the optimizer recommends a large cut on the strongest night of the year.
  * P_ref  — the reference price at which p_ref was observed.
  * beta   — elasticity BY SEASON from policy. Luxury peak inventory is inelastic
             (|beta| < 1), which honestly implies "charge the ceiling"; shoulder
             is elastic (|beta| > 1), which produces a real interior optimum.
             Scaled toward more elastic when pacing is behind.

E[RevPAN] for one night = P * p(book | P). The composer maximizes this over a
grid spanning [floor, ceiling].
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.features import NightFeatures
from src.utils import parse_date, season_for


@dataclass
class BookingProbability:
    p_ref: float
    price_ref: float
    beta: float
    bucket: str
    sample_size: int
    shrunk: bool
    pacing_ratio: float | None

    def prob_at(self, price: float) -> float:
        """Linear demand around (price_ref, p_ref). See module docstring."""
        if price <= 0 or self.price_ref <= 0:
            return self.p_ref
        p = self.p_ref * (1.0 + self.beta * (price / self.price_ref - 1.0))
        return max(0.001, min(0.995, p))

    @property
    def unconstrained_optimum(self) -> float:
        """Closed-form argmax of P * p(P) before floor/ceiling clamping."""
        if self.beta >= 0:
            return self.price_ref
        return self.price_ref * (self.beta - 1.0) / (2.0 * self.beta)

    def expected_revpan(self, price: float) -> float:
        return price * self.prob_at(price)


def _dow_class(dow: int) -> str:
    return "weekend" if dow in (4, 5) else "weekday"


def _lead_bucket(lead: int | None) -> str:
    if lead is None:
        return "unknown"
    if lead <= 7:
        return "0-7"
    if lead <= 21:
        return "8-21"
    if lead <= 60:
        return "22-60"
    return "61+"


def pacing_ratio(
    conn: sqlite3.Connection,
    feat: NightFeatures,
    policy: dict[str, Any],
) -> float | None:
    """How full is this night versus the portfolio norm at the same days_out?

    Returns occupancy_this_night_cohort / occupancy_reference, or None when there
    is not yet enough pacing history. Requires the snapshotter to have been running.
    """
    health = policy.get("data_health", {})
    min_days = int(health.get("pacing_min_snapshot_days", 14))
    distinct = conn.execute("SELECT COUNT(DISTINCT as_of) AS c FROM pacing_snapshots").fetchone()
    if not distinct or int(distinct["c"] or 0) < min_days:
        return None

    row = conn.execute(
        """
        SELECT status, days_out FROM pacing_snapshots
        WHERE property_id = ? AND stay_date = ?
        ORDER BY as_of DESC LIMIT 1
        """,
        (feat.property_id, feat.stay_date.isoformat()),
    ).fetchone()
    if row is None:
        return None
    days_out = int(row["days_out"])
    booked_now = 1.0 if row["status"] == "booked" else 0.0

    ref = conn.execute(
        """
        SELECT AVG(CASE WHEN status = 'booked' THEN 1.0 ELSE 0.0 END) AS occ, COUNT(*) AS n
        FROM pacing_snapshots
        WHERE days_out BETWEEN ? AND ?
        """,
        (max(0, days_out - 3), days_out + 3),
    ).fetchone()
    if ref is None or int(ref["n"] or 0) < 20 or not ref["occ"]:
        return None
    return booked_now / float(ref["occ"]) if float(ref["occ"]) > 0 else None


def estimate(
    conn: sqlite3.Connection,
    feat: NightFeatures,
    policy: dict[str, Any],
    *,
    as_of: date | None = None,
) -> BookingProbability:
    cfg = policy.get("booking_probability", {})
    prior = float(cfg.get("prior_book_rate", 0.55))
    k = float(cfg.get("shrinkage_k", 12))
    min_n = int(cfg.get("min_bucket_nights", 8))
    seasons = policy.get("seasons", {})

    from src.ceiling import demand_index, demand_tier
    from src.signals.features.sqi import load_conditions, sqi_enabled

    dowc = _dow_class(feat.day_of_week)
    leadb = _lead_bucket(feat.lead_time_days)
    tier = demand_tier(feat.demand_strength, policy)
    demand = demand_index(conn)
    conditions = load_conditions()
    use_sqi = sqi_enabled(conditions)

    def _regime_for(stay) -> str:
        """Coarse SQI regime so a drought Christmas never pools with a normal one."""
        if not use_sqi:
            return "all"
        try:
            from src.signals.features.sqi import compute_sqi
            from src.signals.store import SignalStore

            res = compute_sqi(SignalStore(conn), "grand_home", stay, stay, conditions)
            if not res.components_used:
                return "all"
            if res.sqi < 0.75:
                return "drought"
            if res.sqi > 1.15:
                return "big_snow"
            return "normal"
        except Exception:
            return "all"

    target_regime = _regime_for(feat.stay_date)
    bucket = f"{feat.season}/{tier}/{target_regime}/{dowc}/{leadb}"

    # Pooled across properties: per-property cells are far too small at 4 doors.
    rows = conn.execute(
        """
        SELECT stay_date, status, day_of_week, listed_price, booked_price, lead_time_days
        FROM nightly_inventory
        WHERE status IN ('available', 'booked') AND stay_date < ?
        """,
        (feat.stay_date.isoformat(),),
    ).fetchall()

    def _collect(match_tier: bool, match_regime: bool) -> tuple[int, int, list[float]]:
        booked = total = 0
        prices: list[float] = []
        for r in rows:
            stay = parse_date(r["stay_date"])
            if season_for(stay, seasons)[0] != feat.season:
                continue
            dow = int(r["day_of_week"] if r["day_of_week"] is not None else stay.weekday())
            if _dow_class(dow) != dowc:
                continue
            if match_tier and demand_tier(demand.get(stay, 0.2), policy) != tier:
                continue
            if match_regime and target_regime != "all" and _regime_for(stay) != target_regime:
                continue
            total += 1
            if r["status"] == "booked":
                booked += 1
                if r["booked_price"] is not None:
                    prices.append(float(r["booked_price"]))
            elif r["listed_price"] is not None:
                prices.append(float(r["listed_price"]))
        return booked, total, prices

    booked, total, prices = _collect(match_tier=True, match_regime=True)
    if total < min_n:  # widen regime first, then tier
        booked, total, prices = _collect(match_tier=True, match_regime=False)
        bucket += "(regime_widened)"
    if total < min_n:
        booked, total, prices = _collect(match_tier=False, match_regime=False)
        bucket += "(widened)"

    # Beta-binomial shrinkage toward the portfolio prior.
    p_ref = (booked + k * prior) / (total + k) if total >= 0 else prior
    shrunk = total < min_n

    price_ref = (
        sum(prices) / len(prices)
        if prices
        else max(feat.listed_price or feat.base_ceiling_rate, 1.0)
    )

    elas = cfg.get("elasticity_by_season", {})
    beta = float(elas.get(feat.season, elas.get("default", -1.2)))

    pr = pacing_ratio(conn, feat, policy)
    if pr is not None and pr < float(cfg.get("pacing_behind_threshold", 0.70)):
        beta *= float(cfg.get("pacing_elasticity_scale", 1.30))

    decision = as_of or date.today()
    from src.signals.store import SignalStore

    store = SignalStore(conn)

    # CDOT access risk — same-week demand cliff (ladder-gated).
    access_cfg = policy.get("access", {})
    if access_cfg.get("enabled", True):
        from src.signals.features.access import access_risk
        from src.signals.promotion import signal_status_at_least

        if signal_status_at_least(store, "cdot.access_risk", "shadow"):
            risk = access_risk(store, "grand_home", decision)
            threshold = float(access_cfg.get("beta_scale_when_risk_above", 0.5))
            lead = feat.lead_time_days if feat.lead_time_days is not None else 999
            if risk > threshold and lead <= 7:
                beta *= float(access_cfg.get("beta_scale_factor", 1.25))

    p_ref = _adjust_p_ref_with_signals(
        p_ref, conn, feat, policy, store, decision
    )

    return BookingProbability(
        p_ref=max(0.01, min(0.99, p_ref)),
        price_ref=price_ref,
        beta=beta,
        bucket=bucket,
        sample_size=total,
        shrunk=shrunk,
        pacing_ratio=pr,
    )


def _adjust_p_ref_with_signals(
    p_ref: float,
    conn: sqlite3.Connection,
    feat: NightFeatures,
    policy: dict[str, Any],
    store,
    decision: date,
) -> float:
    """Nudge p_ref from intent/flight ladder signals when promoted."""
    from src.signals.promotion import signal_status_at_least

    adjusted = p_ref
    lead = feat.lead_time_days if feat.lead_time_days is not None else 0

    intent_cfg = policy.get("intent", {})
    if intent_cfg.get("enabled", False) and signal_status_at_least(
        store, "intent.search_interest", "shadow"
    ):
        row = store.latest_observation(
            as_of=decision,
            signal_key="intent.search_interest",
            market_id="grand_home",
            effective_date=decision,
        )
        if row and row["value"] is not None:
            z = float(row["value"])
            min_lead = int(intent_cfg.get("min_lead_days", 30))
            max_lead = int(intent_cfg.get("max_lead_days", 90))
            z_hi = float(intent_cfg.get("z_score_high", 1.5))
            nudge = float(intent_cfg.get("p_ref_nudge_pct", 0.05))
            if min_lead <= lead <= max_lead and z > z_hi:
                adjusted *= 1.0 + nudge
            elif z < float(intent_cfg.get("z_score_low", -1.0)):
                adjusted *= 1.0 - nudge

    flight_cfg = policy.get("flight", {})
    if (
        flight_cfg.get("enabled", False)
        and not flight_cfg.get("brief_only", True)
        and signal_status_at_least(store, "flight.den_capacity_yoy", "active")
        and lead > int(flight_cfg.get("min_lead_days", 60))
    ):
        row = store.latest_observation(
            as_of=decision,
            signal_key="flight.den_capacity_yoy",
            market_id="grand_home",
            effective_date=decision,
        )
        if row and row["value"] is not None:
            yoy = float(row["value"])
            threshold = float(flight_cfg.get("capacity_yoy_threshold", 0.10))
            nudge = float(flight_cfg.get("p_ref_nudge_pct", 0.05))
            if yoy > threshold:
                adjusted *= 1.0 + nudge
            elif yoy < -threshold:
                adjusted *= 1.0 - nudge

    return adjusted
