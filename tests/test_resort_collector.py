"""Resort collector + extractor tests (A1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.signals.collector import get_collector
from src.signals.extractors.winter_park_resort import parse_resort_html
from src.signals.features.sqi import compute_sqi
from src.signals.store import SignalDefinition, SignalStore
from src.db import connect, init_db

FIXTURE_JSON = Path(__file__).parent / "fixtures" / "signals" / "winter_park_resort.json"
FIXTURE_HTML = Path(__file__).parent / "fixtures" / "signals" / "winter_park_resort.html"


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "resort.db"
    init_db(db)
    return SignalStore(connect(db))


def test_parse_resort_html_fixture():
    html = FIXTURE_HTML.read_text(encoding="utf-8")
    data = parse_resort_html(html, source_url="https://example.com/report")
    assert data["terrain_open_pct"] == pytest.approx(72.0)
    assert data["lifts_open"] == 18
    assert data["trails_open"] == 95
    assert data["base_depth_in"] == 42


def test_resort_collector_fixture_writes_ok(store: SignalStore):
    import src.signals.collectors  # noqa: F401

    coll = get_collector("resort")(
        store, fixture_path=FIXTURE_JSON, sleep=lambda _s: None
    )
    result = coll.run(date(2025, 12, 20), "grand_home")
    assert result.status == "ok"
    rows = store.read_observations(
        as_of="2025-12-20",
        signal_key="resort.terrain_open_pct",
        market_id="grand_home",
        qualities=["ok"],
    )
    assert len(rows) == 1
    assert float(rows[0]["value"]) == pytest.approx(72.0)


def test_resort_rejects_out_of_range(store: SignalStore, tmp_path):
    import json
    import src.signals.collectors  # noqa: F401

    bad = {"grand_home": {"terrain_open_pct": 150.0}}
    fpath = tmp_path / "bad.json"
    fpath.write_text(json.dumps(bad), encoding="utf-8")
    coll = get_collector("resort")(store, fixture_path=fpath, sleep=lambda _s: None)
    result = coll.run(date(2025, 12, 20), "grand_home")
    assert result.rejected >= 1
    ok = store.read_observations(
        as_of="2025-12-20",
        signal_key="resort.terrain_open_pct",
        qualities=["ok"],
    )
    assert ok == []


def test_sqi_includes_terrain_when_present(store: SignalStore):
    store.upsert_definition(
        SignalDefinition("snotel.swe_pct_normal", "conditions", "ratio", "daily", "t")
    )
    store.upsert_definition(
        SignalDefinition("resort.terrain_open_pct", "conditions", "percent", "daily", "t")
    )
    d = date(2025, 12, 20)
    from src.signals.store import Observation

    store.write_observations(
        [
            Observation(
                signal_key="snotel.swe_pct_normal",
                market_id="grand_home",
                observed_at=d.isoformat(),
                effective_date=d.isoformat(),
                value=0.80,
            ),
            Observation(
                signal_key="resort.terrain_open_pct",
                market_id="grand_home",
                observed_at=d.isoformat(),
                effective_date=d.isoformat(),
                value=72.0,
            ),
        ]
    )
    res = compute_sqi(store, "grand_home", d, d)
    assert "terrain_open_pct" in res.components_used
