"""Resort operations forecast features — rules-first, confidence-banded."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from src.config import load_resort_config
from src.signals.store import SignalStore


@dataclass
class ResortOpsResult:
    closure_risk: float
    lift_hold_risk: float
    terrain_open_forecast: float
    surface_forecast_score: float
    surface_label: str
    staffing_readiness: float
    confidence: float
    details: dict[str, Any]


def _get_ok(store: SignalStore, *, as_of, signal_key, market_id, effective_date):
    row = store.latest_observation(
        as_of=as_of,
        signal_key=signal_key,
        market_id=market_id,
        effective_date=effective_date,
    )
    if row is None or row["value"] is None:
        return None
    return float(row["value"])


def _parse_md(s: str) -> tuple[int, int]:
    m, d = s.split("-")
    return int(m), int(d)


def _in_ski_season(target: date, cfg: dict[str, Any]) -> bool:
    season = cfg.get("season") or {}
    om, od = _parse_md(season.get("typical_open", "11-15"))
    cm, cd = _parse_md(season.get("typical_close", "04-15"))
    t = (target.month, target.day)
    open_day = (om, od)
    close_day = (cm, cd)
    if om > cm:
        return t >= open_day or t <= close_day
    return open_day <= t <= close_day


def _month_packing_label(cfg: dict[str, Any], month: int, temp_c: float | None) -> tuple[str, float]:
    for rule in cfg.get("packing_rules") or []:
        months = rule.get("months") or []
        if month not in months:
            continue
        tmax = rule.get("temp_max_c")
        tmin = rule.get("temp_min_c")
        if tmax is not None and temp_c is not None and temp_c > tmax:
            continue
        if tmin is not None and temp_c is not None and temp_c < tmin:
            continue
        return str(rule.get("label", "variable")), float(rule.get("surface_score", 0.7))
    return "variable", 0.65


def compute_resort_ops(
    store: SignalStore,
    market_id: str,
    target_date: date,
    as_of: date,
    *,
    resort_cfg: dict[str, Any] | None = None,
) -> ResortOpsResult:
    cfg = resort_cfg or load_resort_config()
    resort_id = cfg.get("resort_id", "winter_park")
    details: dict[str, Any] = {}

    resort_open = _get_ok(
        store, as_of=as_of, signal_key="resort.resort_open",
        market_id=market_id, effective_date=target_date,
    )
    lifts_on_hold = _get_ok(
        store, as_of=as_of, signal_key="resort.lifts_on_hold",
        market_id=market_id, effective_date=target_date,
    ) or 0.0
    groomed_pct = _get_ok(
        store, as_of=as_of, signal_key="resort.trails_groomed_pct",
        market_id=market_id, effective_date=target_date,
    )
    terrain_pct = _get_ok(
        store, as_of=as_of, signal_key="resort.terrain_open_pct",
        market_id=market_id, effective_date=target_date,
    )

    # Wind gust forecast (max next 48h from weather observations with horizon).
    wind_rows = store.read_observations(
        as_of=as_of,
        signal_key="weather.wind_gust_max_mph",
        market_id=market_id,
        effective_from=target_date,
        effective_to=target_date + timedelta(days=2),
        qualities=["ok"],
    )
    max_gust = max((float(r["value"]) for r in wind_rows), default=None)
    wh_cfg = cfg.get("wind_hold") or {}
    gust_thresh = float(wh_cfg.get("gust_threshold_mph", 35))
    risk_per_mph = float(wh_cfg.get("risk_per_mph_above", 0.02))
    in_season = _in_ski_season(target_date, cfg)
    wind_risk = 0.0
    if max_gust is not None and max_gust > gust_thresh and in_season:
        wind_risk = min(0.75, (max_gust - gust_thresh) * risk_per_mph)
    details["max_wind_gust_mph"] = max_gust
    details["in_ski_season"] = in_season

    closure_risk = wind_risk
    if resort_open is not None and resort_open < 0.5:
        closure_risk = max(closure_risk, 0.85 if in_season else 0.08)
    elif not in_season:
        closure_risk = max(closure_risk, 0.05)
    if in_season and lifts_on_hold >= 3:
        closure_risk = max(closure_risk, min(1.0, 0.4 + lifts_on_hold * 0.1))
    closure_risk = min(1.0, closure_risk)

    lift_hold_risk = min(1.0, wind_risk + (lifts_on_hold * 0.15 if in_season else 0.0))

    # Terrain open forecast from SWE vs opening sequence thresholds.
    swe = _get_ok(
        store, as_of=as_of, signal_key="snotel.swe_in",
        market_id=market_id, effective_date=target_date,
    )
    if swe is None:
        swe_rows = store.read_observations(
            as_of=as_of,
            signal_key="snotel.swe_in",
            market_id=market_id,
            effective_from=target_date - timedelta(days=7),
            effective_to=target_date,
            qualities=["ok"],
        )
        if swe_rows:
            swe = float(swe_rows[-1]["value"])

    terrain_forecast = 0.5
    if terrain_pct is not None:
        terrain_forecast = terrain_pct / 100.0
    elif swe is not None:
        seq = cfg.get("terrain_opening_sequence") or []
        if seq:
            max_thresh = max(float(s.get("swe_threshold_in", 20)) for s in seq)
            terrain_forecast = min(1.0, max(0.1, swe / max_thresh))
    details["swe_in"] = swe

    # Surface forecast.
    temp = _get_ok(
        store, as_of=as_of, signal_key="weather.temp_mean_c",
        market_id=market_id, effective_date=target_date,
    )
    surface_label, base_score = _month_packing_label(cfg, target_date.month, temp)
    if groomed_pct is not None:
        base_score = 0.5 * base_score + 0.5 * (groomed_pct / 100.0)
    powder_rows = store.read_observations(
        as_of=as_of,
        signal_key="weather.powder_day",
        market_id=market_id,
        effective_from=target_date - timedelta(days=6),
        effective_to=target_date,
        qualities=["ok"],
    )
    if powder_rows:
        powder_days = sum(float(r["value"]) for r in powder_rows)
        if powder_days >= 2:
            surface_label = "fresh_powder"
            base_score = min(1.0, base_score + 0.15)

    # Staffing readiness prior by calendar.
    season = cfg.get("season") or {}
    readiness = float(season.get("staffing_readiness_prior", 0.5))
    ramp_start = season.get("hiring_ramp_start", "08-01")
    ramp_end = season.get("hiring_ramp_end", "10-31")
    rs_m, rs_d = (int(x) for x in ramp_start.split("-"))
    re_m, re_d = (int(x) for x in ramp_end.split("-"))
    in_ramp = (
        (target_date.month > rs_m or (target_date.month == rs_m and target_date.day >= rs_d))
        and (target_date.month < re_m or (target_date.month == re_m and target_date.day <= re_d))
    )
    if in_ramp:
        readiness = min(1.0, readiness + 0.15)

    # Historical wind-hold frequency from resort_events.
    wh_events = store.list_resort_events(
        resort_id=resort_id, event_type="wind_hold",
        from_date=date(target_date.year - 3, 1, 1),
        to_date=target_date,
    )
    if wh_events and target_date.month in {1, 2, 3}:
        lift_hold_risk = min(1.0, lift_hold_risk + 0.05 * len(wh_events) / max(len(wh_events), 5))

    components = sum(
        1 for x in (resort_open, swe, max_gust, groomed_pct) if x is not None
    )
    confidence = min(0.95, 0.25 + 0.15 * components)

    return ResortOpsResult(
        closure_risk=closure_risk,
        lift_hold_risk=lift_hold_risk,
        terrain_open_forecast=terrain_forecast,
        surface_forecast_score=base_score,
        surface_label=surface_label,
        staffing_readiness=readiness,
        confidence=confidence,
        details=details,
    )


def write_resort_ops_features(
    store: SignalStore,
    market_id: str,
    target_date: date,
    as_of: date,
) -> str:
    """Persist resort ops features to signal_features for audit trail."""
    res = compute_resort_ops(store, market_id, target_date, as_of)
    inputs = {"target_date": target_date.isoformat(), "details": res.details}
    mapping = {
        "resort.closure_risk": res.closure_risk,
        "resort.lift_hold_risk": res.lift_hold_risk,
        "resort.terrain_open_forecast": res.terrain_open_forecast,
        "resort.surface_forecast_score": res.surface_forecast_score,
        "resort.staffing_readiness": res.staffing_readiness,
    }
    for key, val in mapping.items():
        store.write_feature(
            feature_key=key,
            market_id=market_id,
            effective_date=target_date,
            as_of=as_of,
            value=val,
            confidence=res.confidence,
            inputs=inputs,
            builder_version="1",
            meta={"surface_label": res.surface_label},
        )
    return res.surface_label


def lift_diff_summary(store: SignalStore, market_id: str, as_of: date) -> list[str]:
    """Compare latest vs prior resort snapshot for brief deltas."""
    import json

    cur = store.latest_resort_snapshot(as_of=as_of, market_id=market_id)
    if cur is None:
        return []
    prev = store.prior_resort_snapshot(as_of=cur["as_of"], market_id=market_id)
    if prev is None:
        return ["First resort snapshot captured — no prior diff."]

    cur_payload = json.loads(cur["payload_json"])
    prev_payload = json.loads(prev["payload_json"])
    cur_lifts = {l["Name"]: l for l in cur_payload.get("lifts") or []}
    prev_lifts = {l["Name"]: l for l in prev_payload.get("lifts") or []}
    lines: list[str] = []
    for name, lift in cur_lifts.items():
        prev_st = (prev_lifts.get(name) or {}).get("StatusEnglish", "unknown")
        cur_st = lift.get("StatusEnglish", "unknown")
        if prev_st != cur_st:
            lines.append(f"- {name}: {prev_st} → {cur_st}")
    if not lines:
        lines.append("- No lift status changes since prior snapshot.")
    return lines
