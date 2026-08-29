"""Comp scraper tests — fully offline via fixtures.

The scraper's dangerous failure is not an exception, it is plausible-looking garbage:
a markup change that makes the parser return a constant, or a block that returns three
listings instead of 280. Those two cases get explicit adversarial fixtures here,
because a scraper that fails loudly is a nuisance and one that fails quietly moves
real rates.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.comps import comp_evidence, market_percentile
from src.config import load_policy
from src.db import connect, init_db
from src.features import build_features_for_property
from src.guardrails import assess_data_health
from src.ingest import CsvIngestAdapter
from src.scrape import plan_windows, run_scrape
from src.scrape.parse import nightly_price, validate_observation, validate_sweep
from src.scrape.providers import FixtureProvider

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
FIX = Path(__file__).parent / "fixtures"
START = date(2026, 12, 1)


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "scrape.db"
    init_db(path)
    with connect(path) as conn:
        CsvIngestAdapter(
            properties_csv=SAMPLE / "properties.csv",
            inventory_csv=SAMPLE / "nightly_inventory.csv",
            comps_csv=SAMPLE / "comps.csv",
            demand_csv=SAMPLE / "demand_signals.csv",
            inquiries_csv=SAMPLE / "booking_inquiries.csv",
        ).load_all(conn)
    return path


# ---------------------------------------------------------------------- parse

def test_nightly_price_prefers_breakdown_over_arithmetic():
    """price.unit.amount is the STAY TOTAL. Dividing by the wrong night count is the
    easiest way to build a plausible but wrong comp set, so the breakdown string —
    which states its own night count — wins."""
    listing = {"price": {"break_down": [{"description": "3 nights x $94.00"}],
                         "unit": {"amount": 282.0, "qualifier": "for 3 nights"}}}
    assert nightly_price(listing, window_nights=2) == 94.0  # not 282/2 = 141


def test_nightly_price_falls_back_to_qualifier():
    listing = {"price": {"unit": {"amount": 600.0, "qualifier": "for 4 nights"}}}
    assert nightly_price(listing, window_nights=2) == 150.0


def test_nightly_price_returns_none_when_absent():
    assert nightly_price({"price": {}}, 2) is None


# ----------------------------------------------------------------- validation

def test_validation_rejects_constant_parser():
    policy = load_policy()
    v = validate_sweep([199.0] * 100, 100, policy)
    assert not v.ok
    assert any("constant" in r or "variance" in r for r in v.reasons)


def test_validation_rejects_blocked_sweep():
    policy = load_policy()
    v = validate_sweep([300.0, 400.0, 500.0], 3, policy)
    assert not v.ok
    assert any("blocked" in r for r in v.reasons)


def test_validation_accepts_a_real_market():
    policy = load_policy()
    prices = [200 + i * 7.3 for i in range(120)]
    assert validate_sweep(prices, 130, policy).ok


def test_observation_rejects_implausible_jump():
    policy = load_policy()
    ok, why = validate_observation(4000.0, previous=400.0, policy=policy)
    assert not ok and "10.0x" in why
    assert validate_observation(430.0, previous=400.0, policy=policy)[0]


# ------------------------------------------------------------------ windows

def test_plan_windows_samples_weekend_and_midweek():
    windows = plan_windows(START, 21)
    assert windows
    assert {w.weekday() for w in windows} == {1, 4}  # Tue + Fri
    assert all(START <= w < START + __import__("datetime").timedelta(days=21) for w in windows)


# --------------------------------------------------------------- orchestrator

def test_successful_scrape_populates_comps_and_market(db: Path):
    policy = load_policy()
    provider = FixtureProvider(FIX / "winter_park_sweep.json")
    with connect(db) as conn:
        rep = run_scrape(conn, provider, policy, horizon_days=14, start=START,
                         fetch_calendars=False)
        ok = conn.execute(
            "SELECT COUNT(*) c FROM comp_snapshots WHERE scrape_status='ok'"
        ).fetchone()["c"]
        market = conn.execute("SELECT COUNT(*) c FROM market_snapshots").fetchone()["c"]
        run = conn.execute("SELECT * FROM comp_scrape_runs WHERE run_id=?",
                           (rep.run_id,)).fetchone()
    assert rep.status == "ok"
    assert rep.comps_matched == rep.comps_expected == 5
    assert ok > 0 and market > 0
    assert run["status"] == "ok" and run["finished_at"] is not None


def test_broken_parser_writes_no_prices(db: Path):
    """A constant-returning parser must poison nothing. The run is recorded as failed
    and every touched night is marked 'failed', not left silently absent."""
    policy = load_policy()
    with connect(db) as conn:
        rep = run_scrape(conn, FixtureProvider(FIX / "broken_parser.json"), policy,
                         horizon_days=14, start=START, fetch_calendars=False)
        prices = conn.execute(
            "SELECT COUNT(*) c FROM comp_snapshots WHERE listed_price IS NOT NULL"
        ).fetchone()["c"]
        failed = conn.execute(
            "SELECT COUNT(*) c FROM comp_snapshots WHERE scrape_status='failed'"
        ).fetchone()["c"]
    assert rep.status == "failed"
    assert prices == 0, "a broken parser must not write a single price"
    assert failed > 0, "failure must be recorded, not silently absent"


def test_blocked_sweep_is_detected(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        rep = run_scrape(conn, FixtureProvider(FIX / "blocked_sweep.json"), policy,
                         horizon_days=14, start=START, fetch_calendars=False)
    assert rep.status == "failed"
    assert rep.windows_ok == 0
    assert any("blocked" in e for e in rep.errors)


def test_unavailable_is_distinguished_from_failed(db: Path):
    """The distinction that keeps a fully-booked market from looking like an outage."""
    policy = load_policy()
    with connect(db) as conn:
        run_scrape(conn, FixtureProvider(FIX / "winter_park_sweep.json"), policy,
                   horizon_days=14, start=START, fetch_calendars=False)
        statuses = {
            r["scrape_status"]
            for r in conn.execute("SELECT DISTINCT scrape_status FROM comp_snapshots")
        }
    assert "ok" in statuses
    assert "failed" not in statuses


def test_scrape_is_idempotent(db: Path):
    policy = load_policy()
    provider = FixtureProvider(FIX / "winter_park_sweep.json")
    with connect(db) as conn:
        run_scrape(conn, provider, policy, horizon_days=14, start=START, fetch_calendars=False)
        first = conn.execute("SELECT COUNT(*) c FROM comp_snapshots").fetchone()["c"]
        run_scrape(conn, provider, policy, horizon_days=14, start=START, fetch_calendars=False)
        second = conn.execute("SELECT COUNT(*) c FROM comp_snapshots").fetchone()["c"]
    assert first == second


def test_scrape_without_room_ids_fails_loudly(tmp_path: Path):
    policy = load_policy()
    path = tmp_path / "empty.db"
    init_db(path)
    with connect(path) as conn:
        rep = run_scrape(conn, FixtureProvider(FIX / "winter_park_sweep.json"), policy,
                         horizon_days=14, start=START, fetch_calendars=False)
    assert rep.status == "failed"
    assert any("discover-comps" in e for e in rep.errors)


# ------------------------------------------------------- downstream integration

def test_scraped_comps_reach_the_ceiling(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        run_scrape(conn, FixtureProvider(FIX / "winter_park_sweep.json"), policy,
                   horizon_days=14, start=START, fetch_calendars=False)
        feats = build_features_for_property(conn, "aspen_glow", START, START, policy=policy)
        ev = comp_evidence(conn, feats[0], policy)
        from src.ceiling import compute_ceiling
        ceiling = compute_ceiling(conn, feats[0], policy)
    assert ev.usable, ev.reason
    assert ev.price and ev.price > 0
    assert "comp" in ceiling.method
    assert ceiling.comp_weight > 0


def test_only_ok_rows_count_as_comp_evidence(db: Path):
    """'unavailable' means checked-and-no-price; 'failed' means we could not check.
    Neither is evidence — counting them would let a degrading scraper move the ceiling."""
    policy = load_policy()
    with connect(db) as conn:
        run_scrape(conn, FixtureProvider(FIX / "winter_park_sweep.json"), policy,
                   horizon_days=14, start=START, fetch_calendars=False)
        conn.execute("UPDATE comp_snapshots SET scrape_status='failed'")
        conn.commit()
        feats = build_features_for_property(conn, "aspen_glow", START, START, policy=policy)
        ev = comp_evidence(conn, feats[0], policy)
    assert not ev.usable
    assert ev.price is None


def test_market_percentile_is_independent_of_comp_set(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        run_scrape(conn, FixtureProvider(FIX / "winter_park_sweep.json"), policy,
                   horizon_days=14, start=START, fetch_calendars=False)
        price, n = market_percentile(conn, START)
    assert price and price > 0
    assert n >= 250, "the sweep sees the whole market, not just the comp set"


def test_failed_scrape_demotes_autonomy(db: Path):
    """End-to-end safety property: a degraded scraper must cost the system its
    authority to write rates."""
    policy = load_policy()
    with connect(db) as conn:
        run_scrape(conn, FixtureProvider(FIX / "broken_parser.json"), policy,
                   horizon_days=14, start=START, fetch_calendars=False)
        health = assess_data_health(conn, policy)
    assert health.granted_level == "suggest"
    assert not health.can_push
    assert any("comp" in f for f in health.failures)


def test_sweep_deduplicates_room_ids(tmp_path: Path):
    """Airbnb's paginated search overlaps and can return a listing twice; duplicates
    would double-count it in the market percentile."""
    import json
    dup = {"sweeps": {START.isoformat(): [
        {"room_id": "A", "nightly_price": 100.0, "name": "a"},
        {"room_id": "A", "nightly_price": 100.0, "name": "a"},
        {"room_id": "B", "nightly_price": 200.0, "name": "b"},
    ]}, "calendars": {}}
    f = tmp_path / "dup.json"
    f.write_text(json.dumps(dup))
    sweep = FixtureProvider(f).sweep(START, 2)
    assert [l.room_id for l in sweep.listings] == ["A", "B"]
