"""WeatherCollector tests (A-stage acquisition).

This module carried the thinnest coverage in the Acquisition stage (19%) of any
module — essentially only the JSON-fixture-not-found paths were exercised.
Nothing tested the actual Open-Meteo archive+forecast merge, the powder-day
threshold, the wet-bulb snowmaking-hours derivation, or the RequestException
degrade-to-QUALITY_UNAVAILABLE path — all of which sit directly upstream of SQI
(src/signals/features/sqi.py) and therefore of ceiling confidence.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import requests

from src.db import connect, init_db
from src.signals.collector import get_collector
from src.signals.store import SignalStore

import src.signals.collectors  # noqa: F401 — registers WeatherCollector


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "weather.db"
    init_db(db)
    s = SignalStore(connect(db))
    s.seed_markets()
    return s


def test_unknown_market_raises(store: SignalStore):
    coll = get_collector("weather")(store, sleep=lambda _s: None)
    with pytest.raises(ValueError):
        coll.fetch(date(2025, 12, 20), "not_a_real_market")


def test_fixture_path_emits_snowfall_powder_temp_and_gust(store: SignalStore, tmp_path):
    market_id = store.list_markets()[0]["market_id"]
    as_of = date(2025, 12, 20)
    fixture = {
        "daily": {
            "time": [as_of.isoformat()],
            "snowfall_sum": [18.0],          # >= 15cm threshold -> powder_day
            "temperature_2m_mean": [-6.0],
            "relative_humidity_2m_mean": [80.0],
            "wind_gust_max_mph": [22.0],
        }
    }
    fpath = tmp_path / "weather_fixture.json"
    fpath.write_text(json.dumps(fixture), encoding="utf-8")

    coll = get_collector("weather")(store, fixture_path=fpath, sleep=lambda _s: None)
    result = coll.run(as_of, market_id)
    assert result.status == "ok"

    rows = {
        r["signal_key"]: float(r["value"])
        for r in store.read_observations(as_of=as_of.isoformat(), market_id=market_id, qualities=["ok"])
    }
    assert rows["weather.snowfall_sum_cm"] == pytest.approx(18.0)
    assert rows["weather.powder_day"] == 1.0
    assert rows["weather.temp_mean_c"] == pytest.approx(-6.0)
    assert rows["weather.wind_gust_max_mph"] == pytest.approx(22.0)
    # cold + humid -> wet bulb well below -2C -> 18 snowmaking hours
    assert rows["weather.snowmaking_hours"] == pytest.approx(18.0)


def test_fixture_below_powder_threshold_is_not_a_powder_day(store: SignalStore, tmp_path):
    market_id = store.list_markets()[0]["market_id"]
    as_of = date(2025, 12, 20)
    fixture = {"daily": {"time": [as_of.isoformat()], "snowfall_sum": [4.0]}}
    fpath = tmp_path / "light.json"
    fpath.write_text(json.dumps(fixture), encoding="utf-8")
    coll = get_collector("weather")(store, fixture_path=fpath, sleep=lambda _s: None)
    coll.run(as_of, market_id)
    rows = {
        r["signal_key"]: float(r["value"])
        for r in store.read_observations(as_of=as_of.isoformat(), market_id=market_id, qualities=["ok"])
    }
    assert rows["weather.powder_day"] == 0.0


def test_beyond_16_day_horizon_is_dropped(store: SignalStore, tmp_path):
    market_id = store.list_markets()[0]["market_id"]
    as_of = date(2025, 12, 20)
    from datetime import timedelta

    far = as_of + timedelta(days=30)
    fixture = {"daily": {"time": [far.isoformat()], "snowfall_sum": [10.0]}}
    fpath = tmp_path / "far.json"
    fpath.write_text(json.dumps(fixture), encoding="utf-8")
    coll = get_collector("weather")(store, fixture_path=fpath, sleep=lambda _s: None)
    coll.run(as_of, market_id)
    rows = store.read_observations(as_of=as_of.isoformat(), market_id=market_id, qualities=["ok"])
    assert rows == []


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    """Stands in for requests.Session, returning canned archive/forecast JSON."""

    def __init__(self, archive_payload: dict, forecast_payload: dict):
        self.archive_payload = archive_payload
        self.forecast_payload = forecast_payload
        self.calls: list[str] = []

    def get(self, url: str, params=None, timeout=None):
        self.calls.append(url)
        if "archive" in url:
            return _FakeResponse(self.archive_payload)
        return _FakeResponse(self.forecast_payload)


def test_live_session_merges_archive_and_forecast_without_duplicate_days(store: SignalStore):
    market_id = store.list_markets()[0]["market_id"]
    as_of = date(2025, 12, 20)
    overlap_day = as_of.isoformat()
    archive = {
        "daily": {
            "time": [overlap_day],
            "snowfall_sum": [5.0],
            "temperature_2m_mean": [-3.0],
            "relative_humidity_2m_mean": [70.0],
            "wind_gusts_10m_max": [10.0],  # m/s
        }
    }
    forecast_day = date(2025, 12, 21).isoformat()
    forecast = {
        "daily": {
            "time": [overlap_day, forecast_day],  # overlap must be skipped
            "snowfall_sum": [999.0, 20.0],
            "temperature_2m_max": [-1.0, -2.0],
            "temperature_2m_min": [-9.0, -6.0],
            "wind_gusts_10m_max": [5.0, 8.0],
        }
    }
    session = _FakeSession(archive, forecast)
    coll = get_collector("weather")(store, session=session, sleep=lambda _s: None)
    result = coll.run(as_of, market_id)
    assert result.status == "ok"
    assert len(session.calls) == 2

    rows = list(store.read_observations(
        as_of=as_of.isoformat(), market_id=market_id, signal_key="weather.snowfall_sum_cm",
        qualities=["ok"],
    ))
    by_date = {r["effective_date"]: float(r["value"]) for r in rows}
    # Archive value wins for the overlap day (forecast's 999.0 must be dropped).
    assert by_date[overlap_day] == pytest.approx(5.0)
    assert by_date[forecast_day] == pytest.approx(20.0)

    gust_rows = list(store.read_observations(
        as_of=as_of.isoformat(), market_id=market_id, signal_key="weather.wind_gust_max_mph",
        qualities=["ok"],
    ))
    gust_by_date = {r["effective_date"]: float(r["value"]) for r in gust_rows}
    # 10 m/s * 2.237 = 22.37 mph — unit conversion must actually happen.
    assert gust_by_date[overlap_day] == pytest.approx(22.37, abs=0.01)


def test_request_exception_degrades_to_unavailable_not_raise(store: SignalStore, monkeypatch):
    market_id = store.list_markets()[0]["market_id"]
    as_of = date(2025, 12, 20)

    class _RaisingSession:
        def get(self, *a, **kw):
            raise requests.ConnectionError("network is down")

    coll = get_collector("weather")(store, session=_RaisingSession(), sleep=lambda _s: None)
    result = coll.run(as_of, market_id)
    # The collector must not raise — it must degrade this run to advisory quality,
    # never silently omit data (an outage must be distinguishable from "no snow").
    assert result.status in {"ok", "degraded"}
    rows = store.read_observations(
        as_of=as_of.isoformat(), market_id=market_id, signal_key="weather.snowfall_sum_cm",
    )
    assert any(r["quality"] == "unavailable" for r in rows)
