"""NWS forecast collector (WP-04) — secondary SQI input only.

The Open-Meteo free tier is non-commercial, so production forecasts come from
api.weather.gov (public domain, CC0). Historical snowfall stays on SNOTEL
(`snotel.py`). This collector does not fill past days: a missing archive is
unavailable, not a zero.

Gridpoint wind is often metres per second (`wmoUnit:m_s-1`). The conversion to
mph is explicit and tested. A unit we do not recognise disables that field
for the day instead of guessing.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE

NWS_POINTS = "https://api.weather.gov/points/{lat},{lng}"
# Contact is the public repo. NWS requires a descriptive User-Agent.
NWS_USER_AGENT = (
    "wp-price-signals/1.0 "
    "(Winter Park pricing research; "
    "https://github.com/jacobdpfeifer-svg/Mountian-Property-Management-Harness)"
)
# metres per second -> miles per hour. 1 m/s = 2.236936... mph; the previous
# Open-Meteo path used 2.237, and tests pin that factor.
MS_TO_MPH = 2.237
MM_TO_CM = 0.1
POWDER_CM = 15.0
FORECAST_HORIZON_DAYS = 16

# Open-Meteo archive is not used. These fields have no licence-clean historical
# source inside this collector. SNOTEL covers snow-water equivalent.
HISTORICAL_FIELDS_DISABLED = (
    "weather.snowfall_sum_cm",
    "weather.temp_mean_c",
    "weather.snowmaking_hours",
    "weather.powder_day",
    "weather.wind_gust_max_mph",
)


def stull_wet_bulb(temp_c: float, rh: float) -> float:
    """Stull (2011) wet-bulb approximation."""
    rh = max(0.0, min(100.0, rh))
    return (
        temp_c * math.atan(0.151977 * (rh + 8.313659) ** 0.5)
        + math.atan(temp_c + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * (rh ** 1.5) * math.atan(0.023101 * rh)
        - 4.686035
    )


def wind_to_mph(value: float, unit: str) -> float | None:
    """Convert a wind speed to mph. Unknown units return None (fail closed)."""
    u = (unit or "").lower().replace(" ", "")
    if u in {"wmoUnit:m_s-1".lower(), "m/s", "ms", "m_s-1"}:
        return float(value) * MS_TO_MPH
    if u in {"wmoUnit:km_h-1".lower(), "km/h", "kmh"}:
        return float(value) * 0.621371
    if u in {"wmoUnit:mi_h-1".lower(), "mph", "mi/h"}:
        return float(value)
    return None


def snowfall_to_cm(value: float, unit: str) -> float | None:
    u = (unit or "").lower()
    if "mm" in u:
        return float(value) * MM_TO_CM
    if "cm" in u:
        return float(value)
    if u.endswith(":m") or u in {"m", "wmoUnit:m".lower()}:
        return float(value) * 100.0
    if "inch" in u or u.endswith(":in"):
        return float(value) * 2.54
    return None


def temp_to_c(value: float, unit: str) -> float | None:
    u = (unit or "").lower()
    if "degc" in u or u in {"c", "celsius"}:
        return float(value)
    if "degf" in u or u in {"f", "fahrenheit"}:
        return (float(value) - 32.0) * 5.0 / 9.0
    return None


def _valid_day(valid_time: str) -> date | None:
    """NWS validTime is 'start/duration', for example '2026-10-19T18:00:00+00:00/PT1H'."""
    if not valid_time or "/" not in valid_time and "T" not in valid_time:
        return None
    start = valid_time.split("/", 1)[0]
    try:
        return datetime.fromisoformat(start.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _series(prop: dict[str, Any] | None) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(prop, dict):
        return "", []
    values = prop.get("values") or []
    if not isinstance(values, list):
        return str(prop.get("uom") or ""), []
    return str(prop.get("uom") or ""), [v for v in values if isinstance(v, dict)]


def nws_grid_to_daily(grid: dict[str, Any], as_of: date) -> dict[str, Any]:
    """Collapse an NWS gridpoint document into the daily dict the fixture path uses.

    Days before `as_of` are dropped. A value whose unit cannot be converted is
    omitted for that day, not stored as zero.
    """
    props = grid.get("properties") if isinstance(grid, dict) else None
    if not isinstance(props, dict):
        raise ValueError("nws_grid_missing_properties")
    snow_u, snow_vals = _series(props.get("snowfallAmount"))
    temp_u, temp_vals = _series(props.get("temperature"))
    rh_u, rh_vals = _series(props.get("relativeHumidity"))
    gust_u, gust_vals = _series(props.get("windGust"))

    days: dict[str, dict[str, list[float]]] = {}

    def bucket(day: date) -> dict[str, list[float]]:
        key = day.isoformat()
        return days.setdefault(key, {"snow": [], "temp": [], "rh": [], "gust": []})

    for item in snow_vals:
        day = _valid_day(str(item.get("validTime") or ""))
        cm = snowfall_to_cm(item.get("value"), snow_u) if item.get("value") is not None else None
        if day is None or cm is None or day < as_of or (day - as_of).days > FORECAST_HORIZON_DAYS:
            continue
        bucket(day)["snow"].append(cm)
    for item in temp_vals:
        day = _valid_day(str(item.get("validTime") or ""))
        c = temp_to_c(item.get("value"), temp_u) if item.get("value") is not None else None
        if day is None or c is None or day < as_of or (day - as_of).days > FORECAST_HORIZON_DAYS:
            continue
        bucket(day)["temp"].append(c)
    for item in rh_vals:
        day = _valid_day(str(item.get("validTime") or ""))
        if day is None or item.get("value") is None or day < as_of:
            continue
        if (day - as_of).days > FORECAST_HORIZON_DAYS:
            continue
        bucket(day)["rh"].append(float(item["value"]))
    for item in gust_vals:
        day = _valid_day(str(item.get("validTime") or ""))
        mph = wind_to_mph(item.get("value"), gust_u) if item.get("value") is not None else None
        if day is None or mph is None or day < as_of or (day - as_of).days > FORECAST_HORIZON_DAYS:
            continue
        bucket(day)["gust"].append(mph)

    daily: dict[str, list] = {
        "time": [],
        "snowfall_sum": [],
        "temperature_2m_mean": [],
        "relative_humidity_2m_mean": [],
        "wind_gust_max_mph": [],
        "units_dropped": [],
    }
    for key in sorted(days):
        part = days[key]
        daily["time"].append(key)
        daily["snowfall_sum"].append(sum(part["snow"]) if part["snow"] else None)
        daily["temperature_2m_mean"].append(
            sum(part["temp"]) / len(part["temp"]) if part["temp"] else None
        )
        daily["relative_humidity_2m_mean"].append(
            sum(part["rh"]) / len(part["rh"]) if part["rh"] else None
        )
        daily["wind_gust_max_mph"].append(max(part["gust"]) if part["gust"] else None)
    if not snow_u and not any(daily["snowfall_sum"]):
        daily["units_dropped"].append("snowfall_unit_unrecognised_or_absent")
    return {"daily": daily, "source": "nws"}


@register_collector
class WeatherCollector(Collector):
    schema = CollectorSchema(
        collector_id="weather",
        category="conditions",
        cadence="6-hourly",
        source="nws",
        fields=[
            FieldSpec("snowfall_sum_cm", unit="cm", value_min=0.0, value_max=200.0),
            FieldSpec("temp_mean_c", unit="celsius", value_min=-50.0, value_max=40.0),
            FieldSpec("snowmaking_hours", unit="hours", value_min=0.0, value_max=24.0,
                      description="Hours with wet-bulb suitable for snowmaking"),
            FieldSpec("powder_day", unit="flag", value_min=0.0, value_max=1.0),
            FieldSpec("wind_gust_max_mph", unit="mph", value_min=0.0, value_max=150.0,
                      description="Daily max wind gust for wind-hold risk"),
        ],
    )

    def __init__(self, store, *, fixture_path: Path | None = None, session=None, sleep=None):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.fixture_path = fixture_path
        self.session = session or requests.Session()

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        market = self.store.get_market(market_id)
        if market is None:
            raise ValueError(f"unknown market {market_id}")
        lat = market["centroid_lat"]
        lng = market["centroid_lng"]
        if lat is None or lng is None:
            return []

        if self.fixture_path:
            data = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
            provenance = "fixture"
        else:
            try:
                data = self._fetch_nws(float(lat), float(lng), as_of)
            except (requests.RequestException, ValueError, KeyError) as exc:
                return [
                    Observation(
                        signal_key="weather.snowfall_sum_cm",
                        market_id=market_id,
                        observed_at=as_of.isoformat(),
                        effective_date=as_of.isoformat(),
                        value=None,
                        quality=QUALITY_UNAVAILABLE,
                        provenance_url=NWS_POINTS.format(lat=lat, lng=lng),
                        meta={
                            "error": str(exc)[:200],
                            "reason": "nws_unavailable",
                            "historical_disabled": list(HISTORICAL_FIELDS_DISABLED),
                        },
                    )
                ]
            provenance = NWS_POINTS.format(lat=lat, lng=lng)

        daily = data.get("daily") or {}
        times = daily.get("time") or []
        snow = daily.get("snowfall_sum") or []
        tmean = daily.get("temperature_2m_mean") or []
        rh = daily.get("relative_humidity_2m_mean") or []
        gusts = daily.get("wind_gust_max_mph") or []

        obs: list[Observation] = []
        for i, t in enumerate(times):
            d = date.fromisoformat(str(t)[:10])
            if d > as_of + timedelta(days=FORECAST_HORIZON_DAYS):
                continue
            # Live NWS days before as_of are already dropped. Fixture files may
            # still describe the decision day itself.
            if not self.fixture_path and d < as_of:
                continue
            horizon = max(0, (d - as_of).days)
            observed_at = as_of.isoformat()
            sf = snow[i] if i < len(snow) else None
            tm = tmean[i] if i < len(tmean) else None
            rhi = rh[i] if i < len(rh) else None
            meta = {
                "lat": lat,
                "lng": lng,
                "source": "nws" if not self.fixture_path else "fixture",
                "historical_not_filled": True,
            }
            if sf is not None:
                obs.append(Observation(
                    signal_key="weather.snowfall_sum_cm",
                    market_id=market_id,
                    observed_at=observed_at,
                    effective_date=d.isoformat(),
                    horizon_days=horizon,
                    value=float(sf),
                    quality=QUALITY_OK,
                    provenance_url=provenance,
                    meta=meta,
                ))
                obs.append(Observation(
                    signal_key="weather.powder_day",
                    market_id=market_id,
                    observed_at=observed_at,
                    effective_date=d.isoformat(),
                    horizon_days=horizon,
                    value=1.0 if float(sf) >= POWDER_CM else 0.0,
                    quality=QUALITY_OK,
                    provenance_url=provenance,
                    meta=meta,
                ))
            if tm is not None and rhi is not None:
                obs.append(Observation(
                    signal_key="weather.temp_mean_c",
                    market_id=market_id,
                    observed_at=observed_at,
                    effective_date=d.isoformat(),
                    horizon_days=horizon,
                    value=float(tm),
                    quality=QUALITY_OK,
                    provenance_url=provenance,
                    meta=meta,
                ))
                wb = stull_wet_bulb(float(tm), float(rhi))
                hours = 18.0 if wb <= -2.0 else (6.0 if wb <= 0.0 else 0.0)
                obs.append(Observation(
                    signal_key="weather.snowmaking_hours",
                    market_id=market_id,
                    observed_at=observed_at,
                    effective_date=d.isoformat(),
                    horizon_days=horizon,
                    value=hours,
                    quality=QUALITY_OK,
                    provenance_url=provenance,
                    meta={**meta, "wet_bulb_c": wb},
                ))
            elif tm is not None:
                obs.append(Observation(
                    signal_key="weather.temp_mean_c",
                    market_id=market_id,
                    observed_at=observed_at,
                    effective_date=d.isoformat(),
                    horizon_days=horizon,
                    value=float(tm),
                    quality=QUALITY_OK,
                    provenance_url=provenance,
                    meta=meta,
                ))
            gust = gusts[i] if i < len(gusts) else None
            if gust is not None:
                obs.append(Observation(
                    signal_key="weather.wind_gust_max_mph",
                    market_id=market_id,
                    observed_at=observed_at,
                    effective_date=d.isoformat(),
                    horizon_days=horizon,
                    value=float(gust),
                    quality=QUALITY_OK,
                    provenance_url=provenance,
                    meta=meta,
                ))
        return obs

    def _fetch_nws(self, lat: float, lng: float, as_of: date) -> dict[str, Any]:
        headers = {"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"}
        points_url = NWS_POINTS.format(lat=lat, lng=lng)
        points = self.session.get(points_url, headers=headers, timeout=30)
        points.raise_for_status()
        body = points.json()
        grid_url = ((body.get("properties") or {}).get("forecastGridData"))
        if not grid_url:
            raise ValueError("nws_points_missing_forecast_grid")
        grid = self.session.get(grid_url, headers=headers, timeout=60)
        grid.raise_for_status()
        return nws_grid_to_daily(grid.json(), as_of)
