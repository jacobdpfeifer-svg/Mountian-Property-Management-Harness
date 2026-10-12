"""Ceiling engine — conditional on Season Quality Index when enabled.

Stationarity is false: a $482 drought Christmas must not set a normal-snow ceiling.
When sqi.enabled (conditions.yaml):
  price_norm = price_obs / f(SQI(t))
  aggregate percentile on norms
  re-inflate by f(SQI_forecast(target))

Kill switch sqi.enabled=false reverts to the pre–Pfeifer Optimization stationary engine.

History is multi-year and same-season: prior years of *this* season (and weekday,
preferring the calendar anniversary window) may fill a thin bucket. Cross-season
mixing stays forbidden — more years of peak-ski does not make Christmas a legal
fallback for a shoulder night. Existing season-contamination invariants hold either
way.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from src.comps import CompEvidence, comp_evidence
from src.config import load_events
from src.features import NightFeatures, _demand_index, _db_demand
from src.runcache import memo
from src.utils import parse_date, season_for


def demand_tier(strength: float, policy: dict[str, Any]) -> str:
    """Bucket a night by demand so anchors compare like with like inside a season."""
    cfg = policy.get("ceiling", {}).get("demand_tiers", {})
    high = float(cfg.get("high", 0.80))
    mid = float(cfg.get("mid", 0.45))
    if strength >= high:
        return "high"
    if strength >= mid:
        return "mid"
    return "low"


def demand_index(conn: sqlite3.Connection) -> dict[date, float]:
    """date -> demand strength, from events.yaml plus any DB signals (shim)."""
    return dict(memo(("demand_index", id(conn)), lambda: _demand_index_uncached(conn)))


def _demand_index_uncached(conn: sqlite3.Connection) -> dict[date, float]:
    index: dict[date, float] = {d: v[0] for d, v in _demand_index(load_events()).items()}
    index.update({d: v[0] for d, v in _db_demand(conn).items()})
    return index


@dataclass
class CeilingResult:
    ceiling_price: float
    floor_price: float
    method: str
    sample_size: int
    season: str
    confidence: float
    anchor_price: float
    comp_price: float | None = None
    comp_weight: float = 0.0
    sqi: float | None = None
    sqi_confidence: float | None = None
    substitution_index: float | None = None
    substitution_reduction_pct: float = 0.0
    # Booked sales and past listed prices are counted separately. sample_size
    # remains the booked pool that set the percentile, when one did.
    booked_sample_size: int = 0
    listed_sample_size: int = 0
    anchor_booked_sample_size: int = 0
    holiday_sample_size: int = 0
    band_low: float | None = None
    band_high: float | None = None
    thin_anchor: bool = False

    @property
    def is_thin(self) -> bool:
        return self.confidence < 1.0


def _percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("empty values")
    return float(np.percentile(np.array(values, dtype=float), q * 100.0))


def lookback_start(as_of: date, years: float) -> date:
    """Inclusive start of the allowed history window (default ~5 years)."""
    days = max(0, int(round(float(years) * 365.25)))
    return as_of - timedelta(days=days)


def calendar_distance_days(stay: date, target: date) -> int:
    """Shortest month-day distance, wrapping the year. Feb 29 maps to Feb 28."""
    day = 28 if stay.month == 2 and stay.day == 29 else stay.day
    try:
        aligned = date(target.year, stay.month, day)
    except ValueError:
        aligned = date(target.year, stay.month, 28)
    delta = abs((aligned - target).days)
    return min(delta, 365 - delta)


def season_year(stay: date) -> int:
    """July–June year so peak_ski Dec/Jan count as one season-year."""
    return stay.year if stay.month >= 7 else stay.year - 1


def _conditions():
    from src.signals.features.sqi import load_conditions, sqi_enabled

    return load_conditions(), sqi_enabled


def _sqi_for(conn: sqlite3.Connection, stay: date, as_of: date, market_id: str = "grand_home"):
    from src.runcache import memo
    from src.signals.features.sqi import compute_sqi, load_conditions, price_multiplier
    from src.signals.store import SignalStore

    def _compute():
        store = SignalStore(conn)
        conditions = load_conditions()
        result = compute_sqi(store, market_id, stay, as_of, conditions)
        mult = price_multiplier(result.sqi, conditions)
        curve_conf = float(conditions.get("curve_confidence", 0.35))
        return result, mult, min(result.confidence, curve_conf)

    return memo(("ceiling_sqi", id(conn), market_id, stay.isoformat(), as_of.isoformat()), _compute)


def _month_day_in_window(stay: date, start: str, end: str) -> bool:
    """Month-day window. A start after the end wraps the new year (12-19 through 01-03)."""
    sm, sd = (int(part) for part in start.split("-"))
    em, ed = (int(part) for part in end.split("-"))
    md = (stay.month, stay.day)
    if (sm, sd) <= (em, ed):
        return (sm, sd) <= md <= (em, ed)
    return md >= (sm, sd) or md <= (em, ed)


def holiday_windows(policy: dict[str, Any]) -> list[dict[str, str]]:
    cfg = (policy.get("ceiling") or {}).get("holiday_pool") or {}
    windows = cfg.get("windows")
    if windows:
        return list(windows)
    return [{"name": "christmas_new_year", "start": "12-19", "end": "01-03"}]


def is_holiday_stay(stay: date, policy: dict[str, Any]) -> bool:
    return any(
        _month_day_in_window(stay, str(window["start"]), str(window["end"]))
        for window in holiday_windows(policy)
    )


def history_band(point: float, booked_n: int) -> tuple[float, float]:
    """Reporting band around a historical price. Wider when booked history is thin.

    This does not change the price. A thin Christmas sample should not be read
    as a precise anchor.
    """
    if booked_n < 5:
        span = 0.35
    elif booked_n < 8:
        span = 0.25
    elif booked_n < 20:
        span = 0.12
    else:
        span = 0.06
    return point * (1.0 - span), point * (1.0 + span)


def _anchor_parts(
    feat: NightFeatures,
    policy: dict[str, Any],
    conn: sqlite3.Connection,
    *,
    as_of: date | None,
) -> tuple[float, int, int]:
    """Return (anchor price, booked nights in the season pool, listed nights).

    Nights before the decision only. A known sale uses booked_price. An unsold
    past night uses its listed price. Future listed prices, including rates
    this engine pushed, are not history.
    """
    cfg = policy.get("ceiling", {})
    pct = float(cfg.get("anchor_listed_percentile", 0.75))
    min_n = int(cfg.get("anchor_min_listed_nights", 20))
    tier_min_n = int(cfg.get("anchor_min_tier_nights", 8))
    seasons = policy.get("seasons", {})
    demand = demand_index(conn)
    decision = as_of or feat.stay_date
    window_start = lookback_start(decision, float(cfg.get("history_lookback_years", 5)))
    target_tier = demand_tier(feat.demand_strength, policy)

    def _compute() -> tuple[float, int, int]:
        rows = conn.execute(
            """
            SELECT stay_date, listed_price, booked_price, status, booked_at
            FROM nightly_inventory
            WHERE property_id = ? AND stay_date >= ? AND stay_date < ?
              AND listed_price IS NOT NULL AND listed_price > 0
            """,
            (feat.property_id, window_start.isoformat(), decision.isoformat()),
        ).fetchall()
        same: list[float] = []
        same_tier: list[float] = []
        booked_n = 0
        listed_n = 0
        for r in rows:
            stay = parse_date(r["stay_date"])
            if season_for(stay, seasons)[0] != feat.season:
                continue
            sale_known = (
                r["status"] == "booked"
                and r["booked_price"] is not None
                and float(r["booked_price"]) > 0
                and (as_of is None or (r["booked_at"] and parse_date(r["booked_at"]) <= decision))
            )
            if sale_known:
                booked_n += 1
                price = float(r["booked_price"])
            else:
                listed_n += 1
                price = float(r["listed_price"])
            same.append(price)
            if demand_tier(demand.get(stay, 0.2), policy) == target_tier:
                same_tier.append(price)
        floor = feat.min_floor_rate
        pool = same_tier if len(same_tier) >= tier_min_n else same
        if len(pool) >= min(min_n, tier_min_n) and pool is same_tier:
            return max(float(np.percentile(np.array(pool, dtype=float), pct * 100.0)), floor), booked_n, listed_n
        if len(same) >= min_n:
            return max(float(np.percentile(np.array(same, dtype=float), pct * 100.0)), floor), booked_n, listed_n
        return max(feat.base_ceiling_rate * feat.season_multiplier, floor), booked_n, listed_n

    return memo(
        ("seasonal_anchor_parts", id(conn), feat.property_id, feat.season, target_tier, decision.isoformat()),
        _compute,
    )


def seasonal_anchor(
    feat: NightFeatures,
    policy: dict[str, Any],
    conn: sqlite3.Connection | None = None,
    *,
    as_of: date | None = None,
) -> float:
    """Ceiling of last resort for a night with too little realised history."""
    if conn is None:
        return max(feat.base_ceiling_rate * feat.season_multiplier, feat.min_floor_rate)
    return _anchor_parts(feat, policy, conn, as_of=as_of)[0]


def _apply_thin_anchor_guard(
    blended: float,
    method: str,
    *,
    booked_n: int,
    confidence: float,
    comp_price: float | None,
    feat: NightFeatures,
    policy: dict[str, Any],
) -> tuple[float, str]:
    """Keep a thin anchor from a large premium or discount unless comps support it.

    Off unless ``ceiling.thin_anchor_guard.enabled`` is true, so the official
    policy price is unchanged.
    """
    guard = (policy.get("ceiling") or {}).get("thin_anchor_guard") or {}
    if not guard.get("enabled"):
        return blended, method
    min_booked = int(guard.get("min_booked", 8))
    thin = booked_n < min_booked or confidence < 1.0 or method.startswith("seasonal_anchor")
    if not thin:
        return blended, method
    if comp_price is not None and comp_price > 0:
        hi = float(guard.get("max_ratio_vs_comp", 1.10))
        lo = float(guard.get("min_ratio_vs_comp", 0.90))
        capped = min(max(blended, comp_price * lo), comp_price * hi)
        if abs(capped - blended) > 0.01:
            return capped, f"{method}+thin_comp"
        return blended, method
    base = max(feat.base_ceiling_rate * feat.season_multiplier, feat.min_floor_rate)
    span = float(guard.get("max_ratio_vs_base_without_comp", 1.10))
    capped = min(max(blended, base / span), base * span)
    if abs(capped - blended) > 0.01:
        return capped, f"{method}+thin_base"
    return blended, method


def seasonal_base_floor(feat: NightFeatures, policy: dict[str, Any], key: str) -> float:
    """Lowest value an in-season reference may take, from the configured base rate.

    The ceiling (p90 of booked prices) and the demand reference (mean of past
    prices) are both read from this season's own nights. In an elastic season
    the RevPAN optimum sits below the reference, so each sale lowers the next
    reference and the price walks down to the floor. ``base_ceiling_rate ×
    season multiplier`` does not depend on the engine's own prices. Returns 0
    unless ``seasonal_base_anchor.enabled`` is true.
    """
    cfg = policy.get("seasonal_base_anchor") or {}
    if not cfg.get("enabled"):
        return 0.0
    ratio = float(cfg.get(key, 0.0))
    return ratio * feat.base_ceiling_rate * feat.season_multiplier


def _apply_property_premium(
    price: float,
    feat: NightFeatures,
    policy: dict[str, Any],
    comp_price: float | None,
) -> float:
    """Cap how far a property's ceiling may sit above the comp price.

    Off unless ``ceiling.property_premium.enabled`` is true.
    ``by_property.<id>.quality`` is an explicit candidate judgment. A quality
    below ``min_quality_for_premium`` may not take the wider premium.
    """
    premium = (policy.get("ceiling") or {}).get("property_premium") or {}
    if not premium.get("enabled") or comp_price is None or comp_price <= 0:
        return price
    by = (premium.get("by_property") or {}).get(feat.property_id) or {}
    ratio = float(by.get("max_ratio_over_comp", premium.get("max_ratio_over_comp", 1.0)))
    quality = by.get("quality")
    minimum = float(premium.get("min_quality_for_premium", 1.0))
    if quality is not None and float(quality) < minimum:
        ratio = min(ratio, float(premium.get("ratio_if_quality_short", 1.0)))
    return min(price, float(comp_price) * ratio)


def _apply_property_season_ceiling(
    price: float,
    feat: NightFeatures,
    policy: dict[str, Any],
) -> float:
    caps = (policy.get("ceiling") or {}).get("property_season_ceiling") or {}
    raw = (caps.get(feat.property_id) or {}).get(feat.season)
    if raw is None:
        return price
    return min(price, float(raw))


def compute_ceiling(
    conn: sqlite3.Connection,
    feat: NightFeatures,
    policy: dict[str, Any],
    *,
    as_of: date | None = None,
    market_id: str | None = None,
) -> CeilingResult:
    cfg = policy.get("ceiling", {})
    market_id = market_id or getattr(feat, "market_id", None) or "grand_home"
    pct = float(cfg.get("percentile", 0.90))
    min_n = int(cfg.get("min_history_nights", 5))
    allow_cross = bool(cfg.get("allow_cross_season_fallback", False))
    conf_cfg = cfg.get("confidence", {})
    seasons = policy.get("seasons", {})
    decision_date = as_of or feat.stay_date
    yoy_window = int(cfg.get("yoy_calendar_window_days", 14))
    window_start = lookback_start(
        decision_date, float(cfg.get("history_lookback_years", 5))
    )

    from src.signals.features.sqi import load_conditions, sqi_enabled, price_multiplier

    conditions = load_conditions()
    use_sqi = sqi_enabled(conditions)

    rows = conn.execute(
        """
        SELECT stay_date, booked_price, day_of_week, booked_at
        FROM nightly_inventory
        WHERE property_id = ?
          AND status = 'booked'
          AND booked_price IS NOT NULL
          AND stay_date < ?
          AND stay_date >= ?
        """,
        (feat.property_id, feat.stay_date.isoformat(), window_start.isoformat()),
    ).fetchall()

    cutoff = (as_of or decision_date).isoformat()
    same_season: list[tuple[date, float]] = []
    same_season_dow: list[tuple[date, float]] = []
    same_season_dow_yoy: list[tuple[date, float]] = []
    holiday_pairs: list[tuple[date, float]] = []
    for row in rows:
        stay = parse_date(row["stay_date"])
        booked_at = row["booked_at"] if "booked_at" in row.keys() else None
        if booked_at and str(booked_at)[:10] > cutoff:
            continue
        season, _ = season_for(stay, seasons)
        if season != feat.season:
            continue
        price = float(row["booked_price"])
        same_season.append((stay, price))
        if is_holiday_stay(stay, policy):
            holiday_pairs.append((stay, price))
        dow = int(row["day_of_week"] if row["day_of_week"] is not None else stay.weekday())
        if dow == feat.day_of_week:
            same_season_dow.append((stay, price))
            if calendar_distance_days(stay, feat.stay_date) <= yoy_window:
                same_season_dow_yoy.append((stay, price))

    def _pool_prices(pairs: list[tuple[date, float]]) -> list[float]:
        if not use_sqi:
            return [p for _, p in pairs]
        norms = []
        for stay, price in pairs:
            try:
                res, mult, _ = _sqi_for(conn, stay, decision_date, market_id)
                norms.append(price / max(mult, 0.05))
            except Exception:
                norms.append(price)  # degrade to raw if SQI unavailable for that night
        return norms

    anchor, anchor_booked_n, anchor_listed_n = _anchor_parts(
        feat, policy, conn, as_of=decision_date
    )
    sqi_target = None
    sqi_conf = None
    target_mult = 1.0

    if use_sqi:
        try:
            res, target_mult, sqi_conf = _sqi_for(
                conn, feat.stay_date, decision_date, market_id
            )
            # No conditioned observations yet → behave as today's stationary engine
            # so existing regressions and empty DBs are unchanged.
            if not res.components_used or res.method == "default_no_components":
                use_sqi = False
                # Not actually applying SQI this call — don't leave a stray
                # confidence value on the result that implies otherwise.
                sqi_conf = None
            else:
                sqi_target = res.sqi
        except Exception:
            use_sqi = False
            sqi_conf = None

    pool_yoy = _pool_prices(same_season_dow_yoy)
    pool_dow = _pool_prices(same_season_dow)
    pool_season = _pool_prices(same_season)
    holiday_cfg = cfg.get("holiday_pool") or {}
    # Future unsold listed prices stay out of this pool. Only booked sales
    # already known on the decision date, inside the holiday window, qualify.
    use_holiday = bool(holiday_cfg.get("enabled")) and is_holiday_stay(feat.stay_date, policy)
    holiday_min = int(holiday_cfg.get("min_nights", min_n))
    pool_holiday = _pool_prices(holiday_pairs) if use_holiday else []

    if use_holiday and len(pool_holiday) >= holiday_min:
        raw_norm = _percentile(pool_holiday, pct)
        n = len(pool_holiday)
        method = f"p{int(pct * 100)}_holiday"
        confidence = float(conf_cfg.get("holiday", conf_cfg.get("season", 0.8)))
        if n < int(holiday_cfg.get("thin_below", 8)):
            confidence = min(confidence, float(holiday_cfg.get("thin_confidence", 0.55)))
    elif len(pool_yoy) >= min_n:
        raw_norm = _percentile(pool_yoy, pct)
        n = len(pool_yoy)
        yoy_years = {season_year(stay) for stay, _ in same_season_dow_yoy}
        if len(yoy_years) >= 2:
            method = f"p{int(pct * 100)}_season_dow_yoy"
            confidence = float(conf_cfg.get("season_dow_yoy", conf_cfg.get("season_dow", 1.0)))
        else:
            method = f"p{int(pct * 100)}_season_dow"
            confidence = float(conf_cfg.get("season_dow", 1.0))
    elif len(pool_dow) >= min_n:
        raw_norm = _percentile(pool_dow, pct)
        method = f"p{int(pct * 100)}_season_dow"
        n = len(pool_dow)
        confidence = float(conf_cfg.get("season_dow", 1.0))
    elif len(pool_season) >= min_n:
        raw_norm = _percentile(pool_season, pct)
        method = f"p{int(pct * 100)}_season"
        n = len(pool_season)
        confidence = float(conf_cfg.get("season", 0.8))
    elif allow_cross and len(rows) >= min_n:
        raw_norm = _percentile([float(r["booked_price"]) for r in rows], pct)
        method = f"p{int(pct * 100)}_all_history_UNSAFE"
        n = len(rows)
        confidence = 0.25
    else:
        raw_norm = anchor / target_mult if use_sqi else anchor
        method = "seasonal_anchor"
        n = len(same_season)
        confidence = float(conf_cfg.get("seasonal_anchor", 0.45))

    if use_sqi:
        raw = raw_norm * target_mult
        method = f"{method}+sqi"
        # Honesty: SQI prior / missing components must lower confidence.
        if sqi_conf is not None:
            confidence = min(confidence, float(sqi_conf))
        curve_conf = float(conditions.get("curve_confidence", 0.35))
        confidence = min(confidence, curve_conf)
    else:
        raw = raw_norm

    blended = confidence * raw + (1.0 - confidence) * anchor

    ev: CompEvidence | None = comp_evidence(conn, feat, policy, as_of=as_of)
    comp_price: float | None = None
    comp_w = 0.0
    # CompEvidence.price is typed float | None because most `usable=False`
    # returns carry price=None; but every `usable=True` return (src/comps
    # comp_evidence) always sets a real float price. ev.price is not None
    # here is therefore always true at runtime — the explicit check below
    # makes that invariant visible to mypy instead of asserting past it.
    if ev is not None and ev.usable and ev.price is not None:
        comp_price = ev.price
        comp_w = float(cfg.get("comp_blend_weight", 0.30)) * ev.coverage
        blended = (1.0 - comp_w) * blended + comp_w * comp_price
        method = f"{method}+comp"

    # Substitution bleed cap — ladder-gated cross-market share shift.
    sub_cfg = policy.get("substitution", {})
    sub_index_val = None
    sub_reduction = 0.0
    if sub_cfg.get("enabled", False):
        from src.signals.promotion import signal_status_at_least
        from src.signals.features.substitution import (
            apply_substitution_cap,
            substitute_prices_for,
            substitution_index,
        )
        from src.signals.store import SignalStore

        store = SignalStore(conn)
        if signal_status_at_least(store, "substitution.market_bleed", "shadow"):
            markets = sub_cfg.get("substitute_markets", ["summit", "clear_creek_eagle"])
            pct = float(sub_cfg.get("price_percentile", 0.75))
            sub_prices = substitute_prices_for(
                conn,
                as_of=decision_date,
                target_date=feat.stay_date,
                markets=markets,
                percentile=pct,
            )
            if sub_prices:
                sub = substitution_index(
                    store,
                    home_market=market_id,
                    home_price=blended,
                    as_of=decision_date,
                    target_date=feat.stay_date,
                    substitute_prices=sub_prices,
                )
                sub_index_val = sub.index
                capped, sub_reduction = apply_substitution_cap(blended, sub, policy)
                if sub_reduction > 0:
                    blended = capped
                    method = f"{method}+substitution"

    blended, method = _apply_thin_anchor_guard(
        blended,
        method,
        booked_n=n,
        confidence=confidence,
        comp_price=comp_price,
        feat=feat,
        policy=policy,
    )
    base_floor = seasonal_base_floor(feat, policy, "ceiling_min_ratio")
    if blended < base_floor:
        blended = base_floor
        method = f"{method}+base_floor"
    blended = _apply_property_premium(blended, feat, policy, comp_price)
    blended = _apply_property_season_ceiling(blended, feat, policy)

    ceiling = min(max(blended, feat.min_floor_rate), feat.max_ceiling_rate)
    band_low, band_high = history_band(raw, n)
    thin_anchor = n < int((cfg.get("thin_anchor_guard") or {}).get("min_booked", 8)) or method.startswith(
        "seasonal_anchor"
    )
    return CeilingResult(
        ceiling_price=ceiling,
        floor_price=feat.min_floor_rate,
        method=method,
        sample_size=n,
        season=feat.season,
        confidence=confidence,
        anchor_price=anchor,
        comp_price=comp_price,
        comp_weight=comp_w,
        sqi=sqi_target,
        sqi_confidence=sqi_conf,
        substitution_index=sub_index_val,
        substitution_reduction_pct=sub_reduction,
        booked_sample_size=n,
        listed_sample_size=anchor_listed_n,
        anchor_booked_sample_size=anchor_booked_n,
        holiday_sample_size=len(holiday_pairs),
        band_low=band_low,
        band_high=band_high,
        thin_anchor=thin_anchor,
    )
