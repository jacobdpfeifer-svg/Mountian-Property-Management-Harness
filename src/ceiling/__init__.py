"""Ceiling engine — conditional on Season Quality Index when enabled.

Stationarity is false: a $482 drought Christmas must not set a normal-snow ceiling.
When sqi.enabled (conditions.yaml):
  price_norm = price_obs / f(SQI(t))
  aggregate percentile on norms
  re-inflate by f(SQI_forecast(target))

Kill switch sqi.enabled=false reverts to the pre–Pfeifer Optimization stationary engine.
Existing season-contamination invariants are preserved either way.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from src.comps import CompEvidence, comp_evidence
from src.config import load_events
from src.features import NightFeatures, _demand_index, _db_demand
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


def demand_index(conn: sqlite3.Connection) -> dict[date, tuple]:
    """date -> demand strength, from events.yaml plus any DB signals (shim)."""
    index = {d: v[0] for d, v in _demand_index(load_events()).items()}
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

    @property
    def is_thin(self) -> bool:
        return self.confidence < 1.0


def _percentile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("empty values")
    return float(np.percentile(np.array(values, dtype=float), q * 100.0))


def _conditions():
    from src.signals.features.sqi import load_conditions, sqi_enabled

    return load_conditions(), sqi_enabled


def _sqi_for(conn: sqlite3.Connection, stay: date, as_of: date, market_id: str = "grand_home"):
    from src.signals.features.sqi import compute_sqi, load_conditions, price_multiplier
    from src.signals.store import SignalStore

    store = SignalStore(conn)
    conditions = load_conditions()
    result = compute_sqi(store, market_id, stay, as_of, conditions)
    mult = price_multiplier(result.sqi, conditions)
    curve_conf = float(conditions.get("curve_confidence", 0.35))
    return result, mult, min(result.confidence, curve_conf)


def seasonal_anchor(
    feat: NightFeatures,
    policy: dict[str, Any],
    conn: sqlite3.Connection | None = None,
) -> float:
    """Ceiling of last resort for a night with too little realised history."""
    if conn is not None:
        cfg = policy.get("ceiling", {})
        pct = float(cfg.get("anchor_listed_percentile", 0.75))
        min_n = int(cfg.get("anchor_min_listed_nights", 20))
        tier_min_n = int(cfg.get("anchor_min_tier_nights", 8))
        seasons = policy.get("seasons", {})
        demand = demand_index(conn)

        rows = conn.execute(
            """
            SELECT stay_date, listed_price FROM nightly_inventory
            WHERE property_id = ? AND listed_price IS NOT NULL AND listed_price > 0
            """,
            (feat.property_id,),
        ).fetchall()

        same: list[float] = []
        same_tier: list[float] = []
        target_tier = demand_tier(feat.demand_strength, policy)
        for r in rows:
            stay = parse_date(r["stay_date"])
            if season_for(stay, seasons)[0] != feat.season:
                continue
            price = float(r["listed_price"])
            same.append(price)
            if demand_tier(demand.get(stay, 0.2), policy) == target_tier:
                same_tier.append(price)

        pool = same_tier if len(same_tier) >= tier_min_n else same
        if len(pool) >= min(min_n, tier_min_n) and pool is same_tier:
            return max(float(np.percentile(np.array(pool, dtype=float), pct * 100.0)),
                       feat.min_floor_rate)
        if len(same) >= min_n:
            return max(float(np.percentile(np.array(same, dtype=float), pct * 100.0)),
                       feat.min_floor_rate)
    return max(feat.base_ceiling_rate * feat.season_multiplier, feat.min_floor_rate)


def compute_ceiling(
    conn: sqlite3.Connection,
    feat: NightFeatures,
    policy: dict[str, Any],
    *,
    as_of: date | None = None,
    market_id: str = "grand_home",
) -> CeilingResult:
    cfg = policy.get("ceiling", {})
    pct = float(cfg.get("percentile", 0.90))
    min_n = int(cfg.get("min_history_nights", 5))
    allow_cross = bool(cfg.get("allow_cross_season_fallback", False))
    conf_cfg = cfg.get("confidence", {})
    seasons = policy.get("seasons", {})
    decision_date = as_of or feat.stay_date

    from src.signals.features.sqi import load_conditions, sqi_enabled, price_multiplier

    conditions = load_conditions()
    use_sqi = sqi_enabled(conditions)

    rows = conn.execute(
        """
        SELECT stay_date, booked_price, day_of_week
        FROM nightly_inventory
        WHERE property_id = ?
          AND status = 'booked'
          AND booked_price IS NOT NULL
          AND stay_date < ?
        """,
        (feat.property_id, feat.stay_date.isoformat()),
    ).fetchall()

    same_season: list[tuple[date, float]] = []
    same_season_dow: list[tuple[date, float]] = []
    for row in rows:
        stay = parse_date(row["stay_date"])
        season, _ = season_for(stay, seasons)
        if season != feat.season:
            continue
        price = float(row["booked_price"])
        same_season.append((stay, price))
        dow = int(row["day_of_week"] if row["day_of_week"] is not None else stay.weekday())
        if dow == feat.day_of_week:
            same_season_dow.append((stay, price))

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

    anchor = seasonal_anchor(feat, policy, conn)
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
            else:
                sqi_target = res.sqi
        except Exception:
            use_sqi = False

    pool_dow = _pool_prices(same_season_dow)
    pool_season = _pool_prices(same_season)

    if len(pool_dow) >= min_n:
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

    ev: CompEvidence | None = comp_evidence(conn, feat, policy)
    comp_price = None
    comp_w = 0.0
    if ev is not None and ev.usable:
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

    ceiling = min(max(blended, feat.min_floor_rate), feat.max_ceiling_rate)
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
    )
