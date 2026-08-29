"""SNOTEL collector — NRCS AWDB REST ground truth for snowpack (WP-03).

Primary SQI input. Endpoint: https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data
Elements: WTEQ (snow water equivalent), SNWD (snow depth), duration=DAILY.

Acceptance: 2025-26 Berthoud Summit peak SWE 12.2" ≈ 60% of six-season mean.
Station outages → quality=unavailable, never zero.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import requests

from src.signals.collector import Collector, CollectorSchema, FieldSpec, register_collector
from src.signals.store import Observation, QUALITY_OK, QUALITY_UNAVAILABLE

AWDB_DATA = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"
FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "signals"


def _ski_season(d: date) -> str:
    """Nov–Oct water-year style ski season label, e.g. 2025-26."""
    if d.month >= 10:
        return f"{d.year}-{str(d.year + 1)[2:]}"
    return f"{d.year - 1}-{str(d.year)[2:]}"


def peak_swe_by_season(series: list[tuple[date, float]]) -> dict[str, float]:
    peaks: dict[str, float] = {}
    for d, v in series:
        if v is None:
            continue
        season = _ski_season(d)
        peaks[season] = max(peaks.get(season, 0.0), float(v))
    return peaks


def season_vs_mean(peaks: dict[str, float], season: str, lookback: int = 6) -> tuple[float, float]:
    """Return (peak_inches, pct_of_prior_lookback_mean)."""
    prior = sorted(s for s in peaks if s < season)[-lookback:]
    if season not in peaks:
        raise KeyError(season)
    peak = peaks[season]
    if not prior:
        return peak, 100.0
    mean = sum(peaks[s] for s in prior) / len(prior)
    return peak, 100.0 * peak / mean if mean else 0.0


def parse_awdb_payload(payload: list[dict[str, Any]], element: str = "WTEQ") -> list[tuple[date, float | None]]:
    """Flatten AWDB REST data response into (date, value) pairs."""
    out: list[tuple[date, float | None]] = []
    for station in payload or []:
        for series in station.get("data") or []:
            if series.get("stationElement", {}).get("elementCode") != element:
                # Some payloads nest element at top of data item
                code = (
                    series.get("stationElement", {}).get("elementCode")
                    or series.get("elementCode")
                    or element
                )
                if code != element and series.get("values") is None:
                    continue
            for pt in series.get("values") or []:
                ds = pt.get("date") or pt.get("dateTime")
                if not ds:
                    continue
                d = date.fromisoformat(str(ds)[:10])
                val = pt.get("value")
                out.append((d, None if val is None else float(val)))
    return out


def fetch_awdb(
    stations: list[str],
    begin: date,
    end: date,
    *,
    elements: str = "WTEQ,SNWD",
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    sess = session or requests.Session()
    params = {
        "stationTriplets": ",".join(stations),
        "elements": elements,
        "duration": "DAILY",
        "beginDate": begin.isoformat(),
        "endDate": end.isoformat(),
    }
    r = sess.get(AWDB_DATA, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return data.get("data") or data.get("stationData") or [data]
    return data


@register_collector
class SnotelCollector(Collector):
    schema = CollectorSchema(
        collector_id="snotel",
        category="conditions",
        cadence="daily",
        source="nrcs_awdb_rest",
        fields=[
            FieldSpec("swe_in", unit="inches", value_min=0.0, value_max=80.0,
                      description="Snow water equivalent inches"),
            FieldSpec("snwd_in", unit="inches", value_min=0.0, value_max=300.0,
                      description="Snow depth inches"),
            FieldSpec("swe_pct_normal", unit="ratio", value_min=0.0, value_max=3.0,
                      description="SWE as fraction of DOY climatology"),
        ],
        max_staleness_days=3,
    )

    def __init__(
        self,
        store,
        *,
        fixture_path: Path | None = None,
        http_get: Callable[..., list[dict[str, Any]]] | None = None,
        sleep=None,
    ):
        super().__init__(store, sleep=sleep or (lambda _s: None))
        self.fixture_path = fixture_path
        self.http_get = http_get

    def fetch(self, as_of: date, market_id: str) -> list[Observation]:
        market = self.store.get_market(market_id)
        if market is None:
            raise ValueError(f"unknown market {market_id}")
        stations = json.loads(market["snotel_stations"] or "[]")
        if not stations:
            return []

        begin = date(2010, 10, 1)
        end = as_of

        if self.fixture_path:
            payload = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
        elif self.http_get:
            payload = self.http_get(stations, begin, end)
        else:
            try:
                payload = fetch_awdb(stations, begin, end)
            except requests.RequestException:
                # Station / network outage — emit unavailable, not zero.
                return [
                    Observation(
                        signal_key=self.schema.signal_key(self.schema.fields[0]),
                        market_id=market_id,
                        observed_at=as_of.isoformat(),
                        effective_date=as_of.isoformat(),
                        value=None,
                        quality=QUALITY_UNAVAILABLE,
                        provenance_url=AWDB_DATA,
                        meta={"stations": stations, "reason": "request_failed"},
                    )
                ]

        # Prefer primary station (first in list) for market series.
        primary = stations[0]
        swe_series = _series_for_station(payload, primary, "WTEQ")
        snwd_series = _series_for_station(payload, primary, "SNWD")

        if not swe_series:
            return [
                Observation(
                    signal_key=self.schema.signal_key(self.schema.fields[0]),
                    market_id=market_id,
                    observed_at=as_of.isoformat(),
                    effective_date=as_of.isoformat(),
                    value=None,
                    quality=QUALITY_UNAVAILABLE,
                    provenance_url=AWDB_DATA,
                    meta={"stations": stations, "reason": "empty_series"},
                )
            ]

        # DOY climatology from history strictly before each day (no lookahead within series).
        doy_hist: dict[int, list[float]] = {}
        for d, v in swe_series:
            if v is None:
                continue
            doy_hist.setdefault(d.timetuple().tm_yday, []).append(v)

        obs: list[Observation] = []
        # Emit last 400 days up to as_of (enough for season stats + recent SQI).
        cutoff = as_of - timedelta(days=400)
        for d, v in swe_series:
            if d < cutoff or d > as_of:
                continue
            # observed_at = effective_date for daily telemetry (available same day).
            if v is None:
                obs.append(
                    Observation(
                        signal_key="snotel.swe_in",
                        market_id=market_id,
                        observed_at=d.isoformat(),
                        effective_date=d.isoformat(),
                        value=None,
                        quality=QUALITY_UNAVAILABLE,
                        provenance_url=AWDB_DATA,
                        meta={"station": primary},
                    )
                )
                continue
            obs.append(
                Observation(
                    signal_key="snotel.swe_in",
                    market_id=market_id,
                    observed_at=d.isoformat(),
                    effective_date=d.isoformat(),
                    value=float(v),
                    quality=QUALITY_OK,
                    provenance_url=AWDB_DATA,
                    meta={"station": primary},
                )
            )
            hist = [x for x in doy_hist.get(d.timetuple().tm_yday, []) if True]
            # Use prior years only: values observed on this DOY before this calendar year.
            prior = [
                vv
                for dd, vv in swe_series
                if vv is not None
                and dd.timetuple().tm_yday == d.timetuple().tm_yday
                and dd.year < d.year
            ]
            if prior:
                mean = sum(prior) / len(prior)
                pct = float(v) / mean if mean else None
                if pct is not None:
                    obs.append(
                        Observation(
                            signal_key="snotel.swe_pct_normal",
                            market_id=market_id,
                            observed_at=d.isoformat(),
                            effective_date=d.isoformat(),
                            value=pct,
                            quality=QUALITY_OK,
                            provenance_url=AWDB_DATA,
                            meta={"station": primary, "doy_mean": mean},
                        )
                    )

        snwd_by_d = {d: v for d, v in snwd_series}
        for d, v in swe_series:
            if d < cutoff or d > as_of:
                continue
            sv = snwd_by_d.get(d)
            if sv is None:
                continue
            obs.append(
                Observation(
                    signal_key="snotel.snwd_in",
                    market_id=market_id,
                    observed_at=d.isoformat(),
                    effective_date=d.isoformat(),
                    value=float(sv),
                    quality=QUALITY_OK,
                    provenance_url=AWDB_DATA,
                    meta={"station": primary},
                )
            )
        return obs


def _series_for_station(
    payload: list[dict[str, Any]], station: str, element: str
) -> list[tuple[date, float | None]]:
    """Extract daily series for one station+element from AWDB or fixture shapes."""
    # Fixture shortcut: {"stationTriplet": "...", "WTEQ": [["YYYY-MM-DD", val], ...]}
    if payload and "WTEQ" in (payload[0] if isinstance(payload[0], dict) else {}):
        rows = []
        for block in payload:
            if block.get("stationTriplet") not in (None, station):
                if block.get("stationTriplet") != station:
                    continue
            for pair in block.get(element) or []:
                rows.append((date.fromisoformat(pair[0][:10]), pair[1]))
        if rows:
            return rows

    filtered = []
    for station_block in payload or []:
        triplet = (
            station_block.get("stationTriplet")
            or station_block.get("stationId")
            or station
        )
        if triplet != station and ":" in str(triplet):
            # allow match when payload lacks triplet but we requested one station
            pass
        for series in station_block.get("data") or []:
            code = (series.get("stationElement") or {}).get("elementCode") or series.get(
                "elementCode"
            )
            if code and code != element:
                continue
            for pt in series.get("values") or []:
                ds = pt.get("date") or pt.get("dateTime")
                if not ds:
                    continue
                filtered.append(
                    (
                        date.fromisoformat(str(ds)[:10]),
                        None if pt.get("value") is None else float(pt["value"]),
                    )
                )
        # Alternate shape used by some fixtures
        for pair in station_block.get(element) or []:
            filtered.append((date.fromisoformat(pair[0][:10]), pair[1]))
    return filtered
