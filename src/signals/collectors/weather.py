"""Open-Meteo weather collector (WP-04) — SECONDARY SQI input only.

IMPORTANT: Gridded reanalysis disagreed with SNOTEL for 2025-26
(Open-Meteo ~91% of normal vs SNOTEL 60%). Ground instrumentation and
modelled weather are NOT interchangeable. This collector feeds short-horizon
snowfall / powder-day counts and wet-bulb snowmaking hours — never as a
substitute for SNOTEL SWE in SQI.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

SNOTEL_DISAGREEMENT_NOTE = (
    "Open-Meteo gridded reanalysis put 2025-26 at ~91% of normal SWE-equivalent "
    "while Berthoud Summit SNOTEL measured 60%. Use as secondary SQI input only."
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


@register_collector
class WeatherCollector(Collector):
    schema = CollectorSchema(
        collector_id="weather",
        category="conditions",
        cadence="6-hourly",
        source="open_meteo",
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
        else:
            try:
                data = self._fetch_archive_and_forecast(lat, lng, as_of)
            except requests.RequestException as exc:
                return [
                    Observation(
                        signal_key="weather.snowfall_sum_cm",
                        market_id=market_id,
                        observed_at=as_of.isoformat(),
                        effective_date=as_of.isoformat(),
                        value=None,
                        quality=QUALITY_UNAVAILABLE,
                        provenance_url=ARCHIVE_URL,
                        meta={"error": str(exc), "note": SNOTEL_DISAGREEMENT_NOTE},
                    )
                ]

        daily = data.get("daily") or {}
        times = daily.get("time") or []
        snow = daily.get("snowfall_sum") or []
        tmean = daily.get("temperature_2m_mean") or []
        rh = daily.get("relative_humidity_2m_mean") or []
        gusts = daily.get("wind_gust_max_mph") or []

        obs: list[Observation] = []
        for i, t in enumerate(times):
            d = date.fromisoformat(str(t)[:10])
            if d > as_of + timedelta(days=16):
                continue
            horizon = max(0, (d - as_of).days)
            observed_at = as_of.isoformat()
            sf = snow[i] if i < len(snow) else None
            tm = tmean[i] if i < len(tmean) else None
            rhi = rh[i] if i < len(rh) else 70.0
            meta = {"note": SNOTEL_DISAGREEMENT_NOTE, "lat": lat, "lng": lng}
            prov = FORECAST_URL if horizon else ARCHIVE_URL
            if sf is not None:
                obs.append(
                    Observation(
                        signal_key="weather.snowfall_sum_cm",
                        market_id=market_id,
                        observed_at=observed_at,
                        effective_date=d.isoformat(),
                        horizon_days=horizon,
                        value=float(sf),
                        quality=QUALITY_OK,
                        provenance_url=prov,
                        meta=meta,
                    )
                )
                obs.append(
                    Observation(
                        signal_key="weather.powder_day",
                        market_id=market_id,
                        observed_at=observed_at,
                        effective_date=d.isoformat(),
                        horizon_days=horizon,
                        value=1.0 if float(sf) >= 15.0 else 0.0,
                        quality=QUALITY_OK,
                        provenance_url=prov,
                        meta=meta,
                    )
                )
            if tm is not None:
                obs.append(
                    Observation(
                        signal_key="weather.temp_mean_c",
                        market_id=market_id,
                        observed_at=observed_at,
                        effective_date=d.isoformat(),
                        horizon_days=horizon,
                        value=float(tm),
                        quality=QUALITY_OK,
                        provenance_url=ARCHIVE_URL,
                        meta=meta,
                    )
                )
                wb = stull_wet_bulb(float(tm), float(rhi or 70))
                hours = 18.0 if wb <= -2.0 else (6.0 if wb <= 0.0 else 0.0)
                obs.append(
                    Observation(
                        signal_key="weather.snowmaking_hours",
                        market_id=market_id,
                        observed_at=observed_at,
                        effective_date=d.isoformat(),
                        horizon_days=horizon,
                        value=hours,
                        quality=QUALITY_OK,
                        provenance_url=ARCHIVE_URL,
                        meta={**meta, "wet_bulb_c": wb},
                    )
                )
            gust = gusts[i] if i < len(gusts) else None
            if gust is not None:
                obs.append(
                    Observation(
                        signal_key="weather.wind_gust_max_mph",
                        market_id=market_id,
                        observed_at=observed_at,
                        effective_date=d.isoformat(),
                        horizon_days=horizon,
                        value=float(gust),
                        quality=QUALITY_OK,
                        provenance_url=prov,
                        meta=meta,
                    )
                )
        return obs

    def _fetch_archive_and_forecast(self, lat: float, lng: float, as_of: date) -> dict[str, Any]:
        begin = as_of - timedelta(days=60)
        archive = self.session.get(
            ARCHIVE_URL,
            params={
                "latitude": lat,
                "longitude": lng,
                "start_date": begin.isoformat(),
                "end_date": as_of.isoformat(),
                "daily": "snowfall_sum,temperature_2m_mean,relative_humidity_2m_mean,wind_gusts_10m_max",
                "timezone": "America/Denver",
            },
            timeout=60,
        )
        archive.raise_for_status()
        hist = archive.json()

        forecast = self.session.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lng,
                "daily": "snowfall_sum,temperature_2m_max,temperature_2m_min,wind_gusts_10m_max",
                "forecast_days": 16,
                "timezone": "America/Denver",
            },
            timeout=60,
        )
        forecast.raise_for_status()
        fut = forecast.json()

        daily: dict[str, list] = {
            "time": [],
            "snowfall_sum": [],
            "temperature_2m_mean": [],
            "relative_humidity_2m_mean": [],
            "wind_gust_max_mph": [],
        }
        hd = hist.get("daily") or {}
        for i, t in enumerate(hd.get("time") or []):
            daily["time"].append(t)
            daily["snowfall_sum"].append((hd.get("snowfall_sum") or [None])[i])
            daily["temperature_2m_mean"].append((hd.get("temperature_2m_mean") or [None])[i])
            daily["relative_humidity_2m_mean"].append(
                (hd.get("relative_humidity_2m_mean") or [70])[i]
            )
            gust_ms = (hd.get("wind_gusts_10m_max") or [None])[i]
            daily["wind_gust_max_mph"].append(
                float(gust_ms) * 2.237 if gust_ms is not None else None
            )
        fd = fut.get("daily") or {}
        for i, t in enumerate(fd.get("time") or []):
            if t in daily["time"]:
                continue
            daily["time"].append(t)
            daily["snowfall_sum"].append((fd.get("snowfall_sum") or [None])[i])
            tmax = (fd.get("temperature_2m_max") or [None])[i]
            tmin = (fd.get("temperature_2m_min") or [None])[i]
            mean = None
            if tmax is not None and tmin is not None:
                mean = (float(tmax) + float(tmin)) / 2.0
            daily["temperature_2m_mean"].append(mean)
            daily["relative_humidity_2m_mean"].append(70.0)
            gust_ms = (fd.get("wind_gusts_10m_max") or [None])[i]
            daily["wind_gust_max_mph"].append(
                float(gust_ms) * 2.237 if gust_ms is not None else None
            )
        return {"daily": daily, "note": SNOTEL_DISAGREEMENT_NOTE}
