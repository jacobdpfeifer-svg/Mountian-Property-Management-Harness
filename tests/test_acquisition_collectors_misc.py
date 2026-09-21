"""Thin-coverage Acquisition-stage modules that had no direct tests before this
pass: src/signals/extractors/cotrip.py (34%), src/signals/collectors/regulatory.py
(44%), src/signals/collectors/enso.py (55%). All three feed SQI (src/signals/
features/sqi.py) or access-risk features consumed by Stage B/C, so a parse bug
here silently degrades pricing confidence rather than crashing loudly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import src.signals.collectors  # noqa: F401 — registers collectors
from src.db import connect, init_db
from src.signals.collector import get_collector
from src.signals.collectors.enso import oni_for_as_of, parse_oni_ascii
from src.signals.extractors.cotrip import parse_cotrip_payload
from src.signals.store import SignalStore


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "misc.db"
    init_db(db)
    s = SignalStore(connect(db))
    s.seed_markets()
    return s


# ------------------------------------------------------------------- cotrip

def test_cotrip_structured_payload_computes_access_risk():
    out = parse_cotrip_payload({"berthoud_closed": 1, "chain_law": 1})
    assert out["berthoud_closed"] == 1.0
    assert out["chain_law"] == 1.0
    assert out["access_risk"] == pytest.approx(1.0)  # clamped at 1.0


def test_cotrip_text_alert_detects_closure_and_chain_law():
    alerts = [{"description": "US 40 Berthoud Pass CLOSED due to avalanche control"}]
    out = parse_cotrip_payload(alerts)
    assert out["berthoud_closed"] == 1.0
    assert out["access_risk"] > 0


def test_cotrip_unrelated_alert_does_not_invent_closure():
    """An alert with 'closed' in it but nothing about Berthoud/US-40 must not be
    mistaken for a pass closure — the guard exists precisely to prevent that."""
    alerts = [{"description": "I-70 westbound closed near Silverthorne"}]
    out = parse_cotrip_payload(alerts)
    assert out["berthoud_closed"] == 0.0
    assert out["chain_law"] == 0.0
    assert out["access_risk"] == 0.0


def test_cotrip_chain_law_without_closure_is_partial_risk():
    out = parse_cotrip_payload([{"description": "Chain law in effect on US 40 Berthoud Pass"}])
    assert out["berthoud_closed"] == 0.0
    assert out["chain_law"] == 1.0
    assert out["access_risk"] == pytest.approx(0.4)


# ---------------------------------------------------------------- regulatory

def test_regulatory_no_fixture_is_unavailable_not_estimated(store: SignalStore):
    """Doctrine per module docstring: missing machine-readable source -> unavailable,
    never estimated. A collector that fabricates a plausible licence count would be
    exactly the silent-degradation failure mode this audit is looking for."""
    market_id = store.list_markets()[0]["market_id"]
    coll = get_collector("regulatory")(store, sleep=lambda _s: None)
    result = coll.run(date(2026, 1, 15), market_id)
    rows = store.read_observations(as_of="2026-01-15", market_id=market_id)
    assert all(r["quality"] == "unavailable" for r in rows)
    assert all(r["value"] is None for r in rows)


def test_regulatory_fixture_reads_licence_count_and_tax_rate(store: SignalStore, tmp_path):
    import json

    market_id = store.list_markets()[0]["market_id"]
    fpath = tmp_path / "reg.json"
    fpath.write_text(json.dumps({
        market_id: {"str_licence_count": 812, "lodging_tax_rate": 0.084,
                    "source_url": "https://example.gov/licences"}
    }), encoding="utf-8")
    coll = get_collector("regulatory")(store, fixture_path=fpath, sleep=lambda _s: None)
    result = coll.run(date(2026, 1, 15), market_id)
    assert result.status == "ok"
    rows = {
        r["signal_key"]: r
        for r in store.read_observations(as_of="2026-01-15", market_id=market_id, qualities=["ok"])
    }
    assert float(rows["regulatory.str_licence_count"]["value"]) == 812.0
    assert float(rows["regulatory.lodging_tax_rate"]["value"]) == pytest.approx(0.084)
    # effective_date is month-truncated (licence counts are monthly-cadence data).
    assert rows["regulatory.str_licence_count"]["effective_date"] == "2026-01-01"


def test_regulatory_fixture_missing_market_is_unavailable(store: SignalStore, tmp_path):
    import json

    market_id = store.list_markets()[0]["market_id"]
    fpath = tmp_path / "reg_empty.json"
    fpath.write_text(json.dumps({"some_other_market": {"str_licence_count": 5}}), encoding="utf-8")
    coll = get_collector("regulatory")(store, fixture_path=fpath, sleep=lambda _s: None)
    coll.run(date(2026, 1, 15), market_id)
    rows = store.read_observations(as_of="2026-01-15", market_id=market_id)
    assert all(r["quality"] == "unavailable" for r in rows)


# --------------------------------------------------------------------- enso

def test_parse_oni_ascii_current_cpc_layout():
    text = "SEAS  YR   TOTAL   ANOM\n DJF 2024  25.01  -1.32\n MAM 2024  25.50  -0.90\n"
    rows = parse_oni_ascii(text)
    assert rows == [(2024, "DJF", -1.32), (2024, "MAM", -0.90)]


def test_parse_oni_ascii_legacy_layout():
    text = "2024 DJF 25.01 -1.32\n2024 MAM 25.50 -0.90\n"
    rows = parse_oni_ascii(text)
    assert rows == [(2024, "DJF", -1.32), (2024, "MAM", -0.90)]


def test_parse_oni_ascii_skips_malformed_lines():
    text = "SEAS YR TOTAL ANOM\n garbage line\n DJF 2024 25.01 -1.32\n"
    rows = parse_oni_ascii(text)
    assert rows == [(2024, "DJF", -1.32)]


def test_oni_for_as_of_picks_latest_completed_season():
    rows = [(2023, "SON", 0.5), (2024, "DJF", -1.0), (2024, "MAM", -0.8)]
    # Before March, only prior-year rows are eligible (this year's DJF isn't "complete" yet
    # per the conservative month>=3 rule) — falls back to the earliest row when none eligible.
    got_early = oni_for_as_of(rows, date(2024, 1, 15))
    assert got_early is not None
    got_late = oni_for_as_of(rows, date(2024, 6, 1))
    assert got_late == ("2024-MAM", -0.8)


def test_oni_for_as_of_empty_rows_returns_none():
    assert oni_for_as_of([], date(2024, 6, 1)) is None


def test_enso_collector_fixture_text_emits_oni_and_sqi_prior(store: SignalStore):
    market_id = store.list_markets()[0]["market_id"]
    text = "SEAS  YR   TOTAL   ANOM\n DJF 2025  24.50  -1.00\n MAM 2025  25.00  -0.50\n"
    coll = get_collector("enso")(store, fixture_text=text, sleep=lambda _s: None)
    result = coll.run(date(2025, 10, 1), market_id)
    assert result.status == "ok"
    rows = {
        r["signal_key"]: r
        for r in store.read_observations(as_of="2025-10-01", market_id=market_id, qualities=["ok"])
    }
    # as_of is October (month >= 3), so the MAM row is the latest "eligible" season.
    assert float(rows["enso.oni"]["value"]) == pytest.approx(-0.5)
    # La Nina (negative ONI) -> prior > 1.0 per the documented mapping.
    assert float(rows["enso.sqi_prior"]["value"]) > 1.0
    # sqi_prior's effective_date targets Christmas, not the observation date.
    assert rows["enso.sqi_prior"]["effective_date"] == "2025-12-25"


def test_enso_collector_no_rows_parsed_is_unavailable(store: SignalStore):
    market_id = store.list_markets()[0]["market_id"]
    coll = get_collector("enso")(store, fixture_text="not an oni table at all", sleep=lambda _s: None)
    coll.run(date(2025, 10, 1), market_id)
    rows = store.read_observations(as_of="2025-10-01", market_id=market_id)
    assert all(r["quality"] == "unavailable" for r in rows)
