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
    """Stands in for requests.Session. The live path is NWS points, then the grid."""

    def __init__(self, points_payload: dict, grid_payload: dict):
        self.points_payload = points_payload
        self.grid_payload = grid_payload
        self.calls: list[str] = []
        self.headers: list[dict] = []

    def get(self, url: str, headers=None, params=None, timeout=None):
        self.calls.append(url)
        self.headers.append(dict(headers or {}))
        if "/points/" in url:
            return _FakeResponse(self.points_payload)
        return _FakeResponse(self.grid_payload)


def test_live_session_reads_nws_grid_and_converts_metres_per_second(store: SignalStore):
    market_id = store.list_markets()[0]["market_id"]
    as_of = date(2025, 12, 20)
    day = as_of.isoformat()
    points = {"properties": {"forecastGridData": "https://api.weather.gov/gridpoints/BOU/1,2"}}
    grid = {
        "properties": {
            "snowfallAmount": {
                "uom": "wmoUnit:mm",
                "values": [{"validTime": f"{day}T18:00:00+00:00/PT6H", "value": 200.0}],
            },
            "temperature": {
                "uom": "wmoUnit:degC",
                "values": [{"validTime": f"{day}T18:00:00+00:00/PT6H", "value": -8.0}],
            },
            "relativeHumidity": {
                "uom": "wmoUnit:percent",
                "values": [{"validTime": f"{day}T18:00:00+00:00/PT6H", "value": 80.0}],
            },
            "windGust": {
                "uom": "wmoUnit:m_s-1",
                "values": [{"validTime": f"{day}T18:00:00+00:00/PT1H", "value": 10.0}],
            },
        }
    }
    session = _FakeSession(points, grid)
    coll = get_collector("weather")(store, session=session, sleep=lambda _s: None)
    result = coll.run(as_of, market_id)
    assert result.status == "ok"
    assert len(session.calls) == 2
    assert "open-meteo.com" not in " ".join(session.calls)
    assert "wp-price-signals" in session.headers[0].get("User-Agent", "")

    rows = list(store.read_observations(
        as_of=as_of.isoformat(), market_id=market_id, signal_key="weather.snowfall_sum_cm",
        qualities=["ok"],
    ))
    by_date = {r["effective_date"]: float(r["value"]) for r in rows}
    # 200 mm = 20 cm. The old Open-Meteo path is not called.
    assert by_date[day] == pytest.approx(20.0)

    gust_rows = list(store.read_observations(
        as_of=as_of.isoformat(), market_id=market_id, signal_key="weather.wind_gust_max_mph",
        qualities=["ok"],
    ))
    # 10 m/s * 2.237 = 22.37 mph.
    assert float(gust_rows[0]["value"]) == pytest.approx(22.37, abs=0.01)


def test_unrecognised_wind_unit_is_omitted_not_stored_as_mph(store: SignalStore):
    from src.signals.collectors.weather import wind_to_mph
    assert wind_to_mph(10.0, "wmoUnit:furlong_per_fortnight") is None


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
