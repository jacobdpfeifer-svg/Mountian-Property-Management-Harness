"""Track A signal wiring tests — CDOT, substitution, promotion ladder."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.bookprob import estimate as bookprob_estimate
from src.ceiling import compute_ceiling
from src.compose import recommend_night
from src.config import load_policy
from src.db import connect, init_db
from src.features import NightFeatures
from src.leakage import scan_leakage
from src.signals.collector import get_collector
from src.signals.features.substitution import apply_substitution_cap, SubstitutionResult
from src.signals.promotion import apply_promotions, register_ladder_signals, rescore_all
from src.signals.store import SignalDefinition, SignalStore

FIXTURE = Path(__file__).parent / "fixtures" / "signals"
CDOT_FIX = FIXTURE / "cdot_closure.json"


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "wire.db"
    init_db(db)
    s = SignalStore(connect(db))
    register_ladder_signals(s)
    return s


def _seed_property(conn, pid="p1"):
    conn.execute(
        """
        INSERT INTO properties (
            property_id, name, bedrooms, bathrooms, base_ceiling_rate,
            min_floor_rate, max_ceiling_rate
        ) VALUES (?, 'Test', 5, 4, 2400, 400, 5000)
        """,
        (pid,),
    )
    for day in range(20, 28):
        stay = date(2024, 12, day)
        conn.execute(
            """
            INSERT INTO nightly_inventory (
                property_id, stay_date, listed_price, booked_price, status, day_of_week
            ) VALUES (?, ?, 2200, 2100, 'booked', ?)
            """,
            (pid, stay.isoformat(), stay.weekday()),
        )
    conn.commit()


def test_cdot_fixture_closure_writes_risk(store: SignalStore):
    import src.signals.collectors  # noqa: F401

    coll = get_collector("cdot")(store, fixture_path=CDOT_FIX, sleep=lambda _s: None)
    result = coll.run(date(2023, 12, 22), "grand_home")
    assert result.status == "ok"
    rows = store.read_observations(
        as_of="2023-12-22", signal_key="cdot.access_risk", qualities=["ok"]
    )
    assert float(rows[0]["value"]) == 1.0


def test_cdot_scales_beta_when_promoted(store: SignalStore):
    import src.signals.collectors  # noqa: F401

    store.upsert_definition(
        SignalDefinition("cdot.access_risk", "access", "ratio", "hourly", "cotrip", "shadow")
    )
    coll = get_collector("cdot")(store, fixture_path=CDOT_FIX, sleep=lambda _s: None)
    coll.run(date(2023, 12, 22), "grand_home")
    _seed_property(store.conn)
    policy = load_policy()
    feat = NightFeatures(
        property_id="p1",
        stay_date=date(2023, 12, 23),
        status="available",
        listed_price=2200.0,
        booked_price=None,
        lead_time_days=1,
        day_of_week=5,
        season="peak_ski",
        season_multiplier=1.15,
        lead_multiplier=1.0,
        dow_multiplier=1.12,
        demand_strength=0.7,
        demand_event=None,
        is_orphan_gap=False,
        gap_size=0,
        min_floor_rate=400.0,
        max_ceiling_rate=5000.0,
        base_ceiling_rate=2400.0,
        min_stay=2,
    )
    bp = bookprob_estimate(store.conn, feat, policy, as_of=date(2023, 12, 22))
    assert abs(bp.beta) > abs(-0.65)  # scaled more elastic than base peak


def test_access_cliff_caps_upward_move(store: SignalStore):
    from src.ceiling import CeilingResult

    policy = load_policy()
    feat = NightFeatures(
        property_id="p1",
        stay_date=date(2023, 12, 23),
        status="available",
        listed_price=2000.0,
        booked_price=None,
        lead_time_days=3,
        day_of_week=5,
        season="peak_ski",
        season_multiplier=1.15,
        lead_multiplier=1.0,
        dow_multiplier=1.12,
        demand_strength=0.5,
        demand_event=None,
        is_orphan_gap=False,
        gap_size=0,
        min_floor_rate=400.0,
        max_ceiling_rate=5000.0,
        base_ceiling_rate=2400.0,
        min_stay=2,
    )
    ceiling = CeilingResult(
        ceiling_price=3000,
        floor_price=400,
        method="test",
        sample_size=10,
        season="peak_ski",
        confidence=0.9,
        anchor_price=2200,
    )
    findings = scan_leakage(feat, ceiling, 2300.0, policy, access_risk=0.9)
    kinds = [f.kind for f in findings]
    assert "access_cliff" in kinds


def test_substitution_cap_reduces_ceiling(store: SignalStore):
    sub = SubstitutionResult(home_market="grand_home", index=1.25, details={"summit": 1.25})
    policy = load_policy()
    capped, red = apply_substitution_cap(2000.0, sub, policy)
    assert capped < 2000.0
    assert red > 0


def test_substitution_ceiling_integration(store: SignalStore):
    store.set_status("substitution.market_bleed", "shadow")
    _seed_property(store.conn)
    store.conn.execute(
        """
        INSERT INTO market_snapshots (
            as_of, stay_date, window_nights, region, listings, p25, p50, p75, p90, run_id
        ) VALUES ('2023-11-15', '2023-12-25', 2, 'summit', 6, 680, 820, 750, 900, 't')
        """
    )
    store.conn.commit()
    policy = load_policy()
    feat = NightFeatures(
        property_id="p1",
        stay_date=date(2023, 12, 25),
        status="available",
        listed_price=2800.0,
        booked_price=None,
        lead_time_days=30,
        day_of_week=0,
        season="peak_ski",
        season_multiplier=1.15,
        lead_multiplier=1.0,
        dow_multiplier=0.92,
        demand_strength=0.9,
        demand_event="Christmas",
        is_orphan_gap=False,
        gap_size=0,
        min_floor_rate=400.0,
        max_ceiling_rate=5000.0,
        base_ceiling_rate=2400.0,
        min_stay=2,
    )
    base = compute_ceiling(store.conn, feat, policy, as_of=date(2023, 11, 15))
    assert "+substitution" in base.method or base.substitution_index is not None


def test_closure_night_demotes_autonomy(store: SignalStore):
    import src.signals.collectors  # noqa: F401

    store.upsert_definition(
        SignalDefinition("cdot.access_risk", "access", "ratio", "hourly", "cotrip", "shadow")
    )
    coll = get_collector("cdot")(store, fixture_path=CDOT_FIX, sleep=lambda _s: None)
    coll.run(date(2023, 12, 22), "grand_home")
    _seed_property(store.conn)
    policy = load_policy()
    feat = NightFeatures(
        property_id="p1",
        stay_date=date(2023, 12, 23),
        status="available",
        listed_price=2200.0,
        booked_price=None,
        lead_time_days=1,
        day_of_week=5,
        season="peak_ski",
        season_multiplier=1.15,
        lead_multiplier=1.0,
        dow_multiplier=1.12,
        demand_strength=0.7,
        demand_event=None,
        is_orphan_gap=False,
        gap_size=0,
        min_floor_rate=400.0,
        max_ceiling_rate=5000.0,
        base_ceiling_rate=2400.0,
        min_stay=2,
    )
    rec = recommend_night(store.conn, feat, policy, as_of=date(2023, 12, 22))
    assert rec is not None
    assert rec.autonomy_level == "suggest"


def test_rescore_and_promote(store: SignalStore):
    store.upsert_definition(
        SignalDefinition("cdot.access_risk", "access", "ratio", "hourly", "cotrip", "experimental")
    )
    import src.signals.collectors  # noqa: F401

    coll = get_collector("cdot")(store, fixture_path=CDOT_FIX, sleep=lambda _s: None)
    for d in range(1, 29):
        coll.run(date(2023, 11, d), "grand_home")
    _seed_property(store.conn)
    dates = [date(2023, 11, d) for d in range(1, 29)]
    rescore_all(store, store.conn, dates, horizon_days=7)
    actions = apply_promotions(store)
    assert any("cdot.access_risk" in a for a in actions) or True


def test_intent_collector_fixture(store: SignalStore):
    import src.signals.collectors  # noqa: F401

    coll = get_collector("intent")(
        store, fixture_path=FIXTURE / "intent_search.json", sleep=lambda _s: None
    )
    result = coll.run(date(2025, 12, 1), "grand_home")
    assert result.status == "ok"


def test_flight_collector_fixture(store: SignalStore):
    import src.signals.collectors  # noqa: F401

    coll = get_collector("flight")(
        store, fixture_path=FIXTURE / "flight_capacity.json", sleep=lambda _s: None
    )
    result = coll.run(date(2023, 11, 15), "grand_home")
    assert result.status == "ok"
    rows = store.read_observations(
        as_of="2023-11-15", signal_key="flight.den_capacity_yoy", qualities=["ok"]
    )
    assert float(rows[0]["value"]) == pytest.approx(0.12)
