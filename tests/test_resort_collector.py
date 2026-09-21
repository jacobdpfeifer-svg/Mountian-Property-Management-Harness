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


def test_resort_collector_live_intrawest_and_html_fallback(store: SignalStore):
    """Exercises the non-fixture path: intrawest_fn(feed_id) + HTML fallback.

    This path was previously untested (0% covered) and carried a latent typing bug:
    ResortCollector declared `intrawest_fn: Callable[[], list[dict]]` (zero args) but
    always invoked it as `self.intrawest_fn(cfg["feed_id"])` (one arg) — any caller
    that supplied a custom collector conforming to the *declared* signature would have
    crashed with a TypeError at runtime. Fixed in src/signals/collectors/resort.py by
    correcting the Callable annotation to `Callable[[int], ...]` and by explicitly
    typing RESORT_SOURCES (which mixed an int feed_id with str URLs and, unannotated,
    caused mypy to widen every `cfg` to `object`, masking real shape errors).
    """
    import src.signals.collectors  # noqa: F401

    calls: list[int] = []

    def fake_intrawest_fn(feed_id: int) -> list[dict]:
        calls.append(feed_id)
        return [
            {
                "StatusEnglish": "Open",
                "Trails": [{"Name": "Parkway", "Status": "Open", "Grooming": "Yes"}],
            },
            {"StatusEnglish": "Closed", "Trails": []},
        ]

    def fake_extract_fn(url: str) -> dict:
        # HTML fallback only supplies fields the feed doesn't have.
        return {"base_depth_in": 42.0, "lift_ticket_window_usd": 219.0}

    coll = get_collector("resort")(
        store,
        intrawest_fn=fake_intrawest_fn,
        extract_fn=fake_extract_fn,
        sleep=lambda _s: None,
    )
    result = coll.run(date(2025, 12, 20), "grand_home")

    assert result.status == "ok"
    assert calls == [5]  # WINTER_PARK_FEED_ID, passed as an int not the dict itself

    rows = {
        r["signal_key"]: float(r["value"])
        for r in store.read_observations(
            as_of="2025-12-20", market_id="grand_home", qualities=["ok"]
        )
    }
    assert rows["resort.terrain_open_pct"] == pytest.approx(100.0)  # 1 of 1 open trail
    assert rows["resort.lifts_open"] == pytest.approx(1.0)
    # HTML fallback fields land only because the feed didn't supply them.
    assert rows["resort.base_depth_in"] == pytest.approx(42.0)
    assert rows["resort.lift_ticket_window_usd"] == pytest.approx(219.0)

    snap = store.conn.execute(
        "SELECT lift_open, lift_total, trail_open, trail_total FROM resort_snapshots "
        "WHERE as_of='2025-12-20' AND market_id='grand_home'"
    ).fetchone()
    assert snap is not None
    assert (snap["lift_open"], snap["lift_total"], snap["trail_open"], snap["trail_total"]) == (1, 2, 1, 1)


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
