"""Resort ops forecast feature tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.db import connect, init_db
from src.signals.features.resort_ops import compute_resort_ops
from src.signals.store import Observation, SignalDefinition, SignalStore

FIXTURE = Path(__file__).parent / "fixtures" / "signals" / "intrawest_winter_park_lifts.json"


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "ops.db"
    init_db(db)
    return SignalStore(connect(db))


def test_resort_ops_with_observations(store: SignalStore):
    store.upsert_definition(
        SignalDefinition("resort.resort_open", "conditions", "flag", "daily", "t")
    )
    store.upsert_definition(
        SignalDefinition("resort.lifts_on_hold", "conditions", "count", "daily", "t")
    )
    store.upsert_definition(
        SignalDefinition("weather.wind_gust_max_mph", "conditions", "mph", "daily", "t")
    )
    d = date(2025, 12, 20)
    store.write_observations(
        [
            Observation(
                signal_key="resort.resort_open",
                market_id="grand_home",
                observed_at=d.isoformat(),
                effective_date=d.isoformat(),
                value=1.0,
            ),
            Observation(
                signal_key="resort.lifts_on_hold",
                market_id="grand_home",
                observed_at=d.isoformat(),
                effective_date=d.isoformat(),
                value=1.0,
            ),
            Observation(
                signal_key="weather.wind_gust_max_mph",
                market_id="grand_home",
                observed_at=d.isoformat(),
                effective_date=d.isoformat(),
                value=45.0,
                horizon_days=1,
            ),
        ]
    )
    res = compute_resort_ops(store, "grand_home", d, d)
    assert res.closure_risk > 0.15
    assert res.lift_hold_risk > 0.15
    assert res.confidence > 0.2


def test_resort_collector_intrawest_fixture_writes_snapshot(store: SignalStore):
    import src.signals.collectors  # noqa: F401
    from src.signals.collector import get_collector

    coll = get_collector("resort")(
        store,
        intrawest_fixture_path=FIXTURE,
        sleep=lambda _s: None,
    )
    d = date(2025, 12, 20)
    result = coll.run(d, "grand_home")
    assert result.status == "ok"
    snap = store.latest_resort_snapshot(as_of=d, market_id="grand_home")
    assert snap is not None
    assert snap["lift_open"] == 2
    assert snap["trail_open"] == 4
    rows = store.read_observations(
        as_of=d.isoformat(),
        signal_key="resort.lifts_on_hold",
        market_id="grand_home",
        qualities=["ok"],
    )
    assert len(rows) == 1
    assert float(rows[0]["value"]) == pytest.approx(1.0)
