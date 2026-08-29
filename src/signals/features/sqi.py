"""Season Quality Index — architecture, not a promotion-ladder signal.

Unavailable components are DROPPED and remaining weights renormalised.
Never zero-fill (that reintroduces the drought bug through another door).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.config import load_yaml
from src.signals.store import SignalStore

ROOT = Path(__file__).resolve().parents[3]
CONDITIONS_PATH = ROOT / "config" / "policies" / "conditions.yaml"


def load_conditions(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or CONDITIONS_PATH)


@dataclass
class SQIResult:
    sqi: float
    confidence: float
    components_used: dict[str, float]
    weights_used: dict[str, float]
    missing: list[str]
    method: str


def interpolate_multiplier(sqi: float, curve: list[dict[str, float]]) -> float:
    if not curve:
        return 1.0
    pts = sorted((float(p["sqi"]), float(p["mult"])) for p in curve)
    if sqi <= pts[0][0]:
        return pts[0][1]
    if sqi >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= sqi <= x1:
            if x1 == x0:
                return y0
            t = (sqi - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 1.0


def price_multiplier(sqi: float, conditions: dict[str, Any] | None = None) -> float:
    cfg = conditions or load_conditions()
    return interpolate_multiplier(sqi, cfg.get("price_multiplier_curve") or [])


def _get_ok_value(store: SignalStore, *, as_of, signal_key, market_id, effective_date):
    row = store.latest_observation(
        as_of=as_of,
        signal_key=signal_key,
        market_id=market_id,
        effective_date=effective_date,
    )
    if row is None or row["value"] is None:
        return None
    return float(row["value"])


def compute_sqi(
    store: SignalStore,
    market_id: str,
    target_date: date,
    as_of: date,
    conditions: dict[str, Any] | None = None,
) -> SQIResult:
    cfg = (conditions or load_conditions()).get("sqi", {})
    weights = dict(cfg.get("weights") or {})
    powder_n = int(cfg.get("powder_lookback_days", 7))
    season_ahead = int(cfg.get("season_ahead_horizon_days", 45))
    miss_scale = float(cfg.get("missing_confidence_scale", 0.85))

    components: dict[str, float | None] = {}

    # SWE %-of-normal for target (or nearest available on/before target as_of).
    swe = _get_ok_value(
        store,
        as_of=as_of,
        signal_key="snotel.swe_pct_normal",
        market_id=market_id,
        effective_date=target_date,
    )
    if swe is None:
        # Fall back to latest SWE pct on or before target within 7 days.
        rows = store.read_observations(
            as_of=as_of,
            signal_key="snotel.swe_pct_normal",
            market_id=market_id,
            effective_from=target_date - timedelta(days=7),
            effective_to=target_date,
            qualities=["ok"],
        )
        if rows:
            swe = float(rows[-1]["value"])
    components["swe_pct_normal"] = swe

    terrain = _get_ok_value(
        store,
        as_of=as_of,
        signal_key="resort.terrain_open_pct",
        market_id=market_id,
        effective_date=target_date,
    )
    if terrain is not None:
        terrain = terrain / 100.0  # store as percent 0-100 → ratio for SQI scale ~1
    components["terrain_open_pct"] = terrain

    # Trailing powder days from weather.powder_day
    powder_rows = store.read_observations(
        as_of=as_of,
        signal_key="weather.powder_day",
        market_id=market_id,
        effective_from=target_date - timedelta(days=powder_n - 1),
        effective_to=target_date,
        qualities=["ok"],
    )
    if powder_rows:
        components["powder_days_7"] = sum(float(r["value"]) for r in powder_rows) / powder_n
    else:
        components["powder_days_7"] = None

    horizon = (target_date - as_of).days
    enso = None
    enso_row = store.latest_observation(
        as_of=as_of,
        signal_key="enso.sqi_prior",
        market_id=market_id,
        effective_date=target_date,
    )
    if enso_row is None:
        # also accept effective_date = as_of prior
        rows = store.read_observations(
            as_of=as_of,
            signal_key="enso.sqi_prior",
            market_id=market_id,
            qualities=["ok"],
        )
        if rows:
            enso = float(rows[-1]["value"])
    else:
        enso = float(enso_row["value"])
    # Use ENSO when season-ahead or SWE missing.
    if swe is None or horizon >= season_ahead:
        components["enso_prior"] = enso
    else:
        components["enso_prior"] = None  # not needed in-season with SWE

    # Drop unavailable; renormalise remaining weights.
    used_w: dict[str, float] = {}
    used_c: dict[str, float] = {}
    missing: list[str] = []
    for key, w in weights.items():
        val = components.get(key)
        if val is None:
            missing.append(key)
            continue
        used_w[key] = float(w)
        used_c[key] = float(val)

    if not used_w:
        default = float((conditions or load_conditions()).get("default_sqi", 1.0))
        return SQIResult(
            sqi=default,
            confidence=0.15,
            components_used={},
            weights_used={},
            missing=list(weights.keys()),
            method="default_no_components",
        )

    total_w = sum(used_w.values())
    norm_w = {k: v / total_w for k, v in used_w.items()}
    sqi = sum(norm_w[k] * used_c[k] for k in norm_w)
    # Confidence: full weight coverage → 1.0 * curve prior later; missing mass reduces it.
    missing_mass = sum(float(weights[k]) for k in missing) / max(sum(float(w) for w in weights.values()), 1e-9)
    confidence = max(0.1, (1.0 - missing_mass) * miss_scale)
    method = "renormalised_weights"
    return SQIResult(
        sqi=sqi,
        confidence=confidence,
        components_used=used_c,
        weights_used=norm_w,
        missing=missing,
        method=method,
    )


def sqi_enabled(conditions: dict[str, Any] | None = None) -> bool:
    cfg = (conditions or load_conditions()).get("sqi", {})
    return bool(cfg.get("enabled", True))
