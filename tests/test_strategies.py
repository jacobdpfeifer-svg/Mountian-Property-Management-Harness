"""Tests for large-group luxury STR strategies (min-stay, gaps, comps, demand, PPP)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.compose import generate_recommendations, recommend_night
from src.config import load_policy
from src.db import connect, init_db
from src.features import _db_demand, build_features_for_property
from src.ingest import CsvIngestAdapter
from src.min_stay import decide_min_stay, resolve_policy_min_stay
from src.pms import DryRunAdapter, push_recommendations
from src.scrape import discover_comps
from src.scrape.providers import FixtureProvider, Listing

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"


def _adapter() -> CsvIngestAdapter:
    return CsvIngestAdapter(
        properties_csv=SAMPLE / "properties.csv",
        inventory_csv=SAMPLE / "nightly_inventory.csv",
        comps_csv=SAMPLE / "comps.csv",
        demand_csv=SAMPLE / "demand_signals.csv",
        inquiries_csv=SAMPLE / "booking_inquiries.csv",
    )


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "test.db"
    init_db(path)
    with connect(path) as conn:
        _adapter().load_all(conn)
    return path


def test_policy_min_stay_varies_by_season_and_lead():
    policy = load_policy()
    # Peak ski far out → higher min
    assert resolve_policy_min_stay("peak_ski", 90, policy) == 4
    # Peak ski close-in → lower min
    assert resolve_policy_min_stay("peak_ski", 7, policy) == 2
    # Shoulder → flat 2
    assert resolve_policy_min_stay("shoulder_spring", 100, policy) == 2


def test_recommendation_includes_policy_min_stay(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        # Ensure occupancy for per-person framing
        conn.execute(
            "UPDATE properties SET max_occupancy=16 WHERE property_id='aspen_glow'"
        )
        conn.commit()
        feats = build_features_for_property(
            conn, "aspen_glow", date(2026, 12, 10), date(2026, 12, 10), policy=policy
        )
        assert feats
        feat = feats[0]
        # Force a far-out peak_ski lead so the policy table returns 4
        feat.lead_time_days = 90
        feat.season = "peak_ski"
        rec = recommend_night(conn, feat, policy=policy, run_id="t1")
    assert rec is not None
    assert rec.recommended_min_stay == 4
    assert rec.min_stay_source == "policy"
    assert rec.per_person_nightly is not None
    assert rec.per_person_nightly == round(rec.recommended_price / 16)


def test_gap_override_relaxes_standing_min(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        feats = build_features_for_property(
            conn, "cabin_ridge", date(2026, 12, 5), date(2026, 12, 5), policy=policy
        )
        feat = feats[0]
        assert feat.is_orphan_gap
        feat.lead_time_days = 90
        feat.season = "peak_ski"
        # Standing policy min is 4; gap is typically 1–2
        decision = decide_min_stay(feat, policy, gap_min_stay_action=feat.gap_size)
        assert decision.gap_override
        assert decision.recommended_min_stay == feat.gap_size
        assert decision.policy_min_stay == 4

        rec = recommend_night(conn, feat, policy=policy, run_id="gap1")
    assert rec is not None
    assert rec.min_stay_source == "gap_override"
    assert rec.recommended_min_stay == feat.gap_size


def test_push_writes_min_stay_on_handle(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        recs, health = generate_recommendations(
            conn, date(2026, 12, 5), date(2026, 12, 5),
            property_ids=["cabin_ridge"], policy=policy, persist=True, allow_past=True,
        )
        assert recs
        # Force handle so push path runs
        for r in recs:
            r.autonomy_level = "handle"
            r.status = "suggested"
        counts = push_recommendations(
            conn, recs, DryRunAdapter(), "handle", policy=policy
        )
        assert counts["attempted"] >= 1
        row = conn.execute(
            "SELECT recommended_min_stay, min_stay_source FROM price_recommendations "
            "WHERE property_id='cabin_ridge' AND stay_date='2026-12-05' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row["recommended_min_stay"] is not None


def test_db_demand_prefers_exact_region(db: Path):
    with connect(db) as conn:
        conn.execute(
            "INSERT INTO demand_signals (signal_date, region, event_name, signal_strength, source) "
            "VALUES ('2026-07-10', 'valley', 'Valley noise', 0.99, 'test')"
        )
        conn.execute(
            "INSERT INTO demand_signals (signal_date, region, event_name, signal_strength, source) "
            "VALUES ('2026-07-10', 'winter_park', 'WP Jazz', 0.70, 'test')"
        )
        conn.commit()
        idx = _db_demand(conn, region="winter_park")
    assert idx[date(2026, 7, 10)][0] == 0.70
    assert idx[date(2026, 7, 10)][1] == "WP Jazz"


def test_discover_comps_filters_by_group_size(tmp_path: Path):
    fixture = tmp_path / "fix.json"
    check_in = (date.today() + timedelta(days=45)).isoformat()
    fixture.write_text(
        '{"sweeps": {"%s": ['
        '{"room_id": "big", "nightly_price": 900, "name": "Big", "bedrooms": 5, "sleeps": 16},'
        '{"room_id": "small", "nightly_price": 1200, "name": "Small", "bedrooms": 2, "sleeps": 4}'
        "]}}" % check_in,
        encoding="utf-8",
    )
    provider = FixtureProvider(fixture)
    policy = load_policy()
    rows = discover_comps(
        provider, date.fromisoformat(check_in), 2, min_price=400, policy=policy
    )
    ids = {r["room_id"] for r in rows}
    assert "big" in ids
    assert "small" not in ids


def test_max_occupancy_loaded_from_sample(db: Path):
    with connect(db) as conn:
        row = conn.execute(
            "SELECT max_occupancy FROM properties WHERE property_id='cabin_ridge'"
        ).fetchone()
    assert row["max_occupancy"] == 16
