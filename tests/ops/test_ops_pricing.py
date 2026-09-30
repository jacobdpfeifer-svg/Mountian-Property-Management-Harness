"""Phase 2: operations-aware stay length is suggest-only and never moves price."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from conftest import add_open_nights, add_reservation

from src.bookprob import BookingProbability
from src.db import connect
from src.features import NightFeatures
from src.pms import DryRunAdapter, push_recommendations
from src.pricing import apply_models, evaluate_stays, stay_choice

ANCHOR = date(2027, 1, 10)


def _flat(n: int, price: float = 1000.0) -> dict[date, float]:
    return {ANCHOR + timedelta(days=i): price for i in range(n)}


def test_defaulted_ops_arguments_reproduce_stay_choice():
    prices = {ANCHOR: 1000.0, ANCHOR + timedelta(days=1): 1000.0,
              ANCHOR + timedelta(days=2): 1400.0, ANCHOR + timedelta(days=3): 1400.0}
    ev = evaluate_stays(ANCHOR, prices, [2, 4], 2, 0)
    assert (ev.length, ev.delta) == stay_choice(ANCHOR, prices, [2, 4], standing=2, orphan_gap=0)
    assert ev.disqualified == ()


def test_turn_cost_favours_the_longer_stay_on_flat_prices():
    assert evaluate_stays(ANCHOR, _flat(4), [2, 4], 2, 0).length == 2  # tie keeps standing
    ev = evaluate_stays(ANCHOR, _flat(4), [2, 4], 2, 0, turn_cost=800.0)
    assert ev.length == 4
    assert ev.values == {2: 1200.0, 4: 3200.0}


def test_low_readiness_candidates_are_disqualified():
    ev = evaluate_stays(ANCHOR, _flat(4), [2, 3, 4], 2, 0, turn_cost=0.0,
                        p_ready=lambda n: 0.5 if n == 2 else 0.9, min_p_ready=0.6,
                        risk_premium=1000.0)
    assert ev.disqualified == (2,)
    assert ev.length in (3, 4)


def _feat(**over) -> NightFeatures:
    base = dict(
        property_id="cloud_9", stay_date=ANCHOR, status="available", listed_price=1000.0,
        booked_price=None, lead_time_days=30, day_of_week=6, season="peak_ski",
        season_multiplier=1.0, lead_multiplier=1.0, dow_multiplier=1.0, demand_strength=0.5,
        demand_event=None, is_orphan_gap=False, gap_size=0, min_floor_rate=300.0,
        max_ceiling_rate=4000.0, base_ceiling_rate=800.0, min_stay=2,
    )
    base.update(over)
    return NightFeatures(**base)


def _policy(**models) -> dict:
    from src.config import load_policy

    policy = load_policy()
    for name in policy["models"]:
        policy["models"][name]["enabled"] = False
    for name, on in models.items():
        policy["models"][name] = {"enabled": on}
    return policy


def _bp() -> BookingProbability:
    return BookingProbability(0.4, 1000.0, -1.2, "22-60", 20, False, 1.5)


def test_ops_flag_suggests_a_longer_stay_without_moving_price(ops_db):
    with connect(ops_db) as conn:
        add_open_nights(conn, "cloud_9", ANCHOR, 6, price=1000.0, min_stay=2)
        conn.commit()
        adj = apply_models(conn, _feat(), _policy(ops_aware_stay=True), _bp(),
                           as_of=date(2026, 12, 1), floor=300, ceil=2000, sqi=1.0, steps=10)
    assert adj.price_delta == 0.0
    assert adj.min_stay_source == "ops"
    assert adj.min_stay_nights == 4  # peak_ski rules offer 2/3/4
    assert adj.ops_facts["turn_cost"] == 690.0 and adj.ops_facts["cost_basis"] == "estimate"
    [(code, message, contribution)] = adj.reasons
    assert code == "turnover_cost" and contribution == 0.0 and "not pushed" in message


def test_ops_suggestion_needs_a_material_saving(ops_db):
    with connect(ops_db) as conn:
        add_open_nights(conn, "cloud_9", ANCHOR, 6, price=9000.0, min_stay=2)
        conn.commit()
        adj = apply_models(conn, _feat(listed_price=9000.0), _policy(ops_aware_stay=True), _bp(),
                           as_of=date(2026, 12, 1), floor=300, ceil=20000, sqi=1.0, steps=10)
    # $690 spread over 2 vs 4 nights is < 5% of a $9,000 night.
    assert adj.min_stay_nights is None and adj.reasons == []


def test_ops_never_shortens_what_the_stay_model_chose(ops_db):
    with connect(ops_db) as conn:
        add_open_nights(conn, "cloud_9", ANCHOR, 6, price=1000.0, min_stay=2)
        conn.commit()
        both = apply_models(conn, _feat(), _policy(stay_pricing=True, ops_aware_stay=True), _bp(),
                            as_of=date(2026, 12, 1), floor=300, ceil=2000, sqi=1.0, steps=10)
        stay_only = apply_models(conn, _feat(), _policy(stay_pricing=True), _bp(),
                                 as_of=date(2026, 12, 1), floor=300, ceil=2000, sqi=1.0, steps=10)
    assert both.price_delta == stay_only.price_delta
    assert (both.min_stay_nights or 2) >= (stay_only.min_stay_nights or 2)


def test_ops_hook_is_inert_for_properties_without_a_profile(ops_db):
    with connect(ops_db) as conn:
        conn.execute(
            """INSERT INTO properties (property_id, name, bedrooms, bathrooms, base_ceiling_rate,
                   min_floor_rate, max_ceiling_rate) VALUES ('cabin_x','X',3,2,900,300,2000)"""
        )
        add_open_nights(conn, "cabin_x", ANCHOR, 6)
        adj = apply_models(conn, _feat(property_id="cabin_x"), _policy(ops_aware_stay=True), _bp(),
                           as_of=date(2026, 12, 1), floor=300, ceil=2000, sqi=1.0, steps=10)
    assert adj.min_stay_nights is None and adj.reasons == []


def test_tight_same_day_turns_lower_readiness(ops_db):
    from src.ops.pricing_hook import ops_stay_inputs

    with connect(ops_db) as conn:
        add_reservation(conn, "before", "cloud_9", ANCHOR - timedelta(days=3), ANCHOR)
        add_open_nights(conn, "cloud_9", ANCHOR, 2)
        add_reservation(conn, "after", "cloud_9", ANCHOR + timedelta(days=2), ANCHOR + timedelta(days=5))
        add_open_nights(conn, "cloud_9", ANCHOR + timedelta(days=5), 5)
        inputs = ops_stay_inputs(conn, _feat(), as_of=date(2026, 12, 1))
    # 2 nights: same-day turn on both sides. 5+ nights would overlap "after", but
    # the probability only depends on the gaps, so compare 2 against the open side.
    assert inputs.p_ready(2) < inputs.p_ready(8)


class SpyAdapter(DryRunAdapter):
    def __init__(self):
        self.min_stays = []

    def push_rate(self, property_id, stay_date, price, min_stay=None):
        self.min_stays.append(min_stay)
        return super().push_rate(property_id, stay_date, price, min_stay=min_stay)


@pytest.mark.parametrize("source,pushed", [("ops", None), ("policy", 4), ("gap_override", 4),
                                           ("something_new", None)])
def test_push_never_writes_an_ops_min_stay(ops_db, source, pushed):
    rec = SimpleNamespace(
        status="suggested", autonomy_level="handle", recommended_min_stay=4, min_stay_source=source,
        recommended_price=1000.0, floor_price=500.0, listed_price_at_run=1000.0, run_id="r",
        property_id="cloud_9", stay_date=ANCHOR, rule_version="r", model_version="m", inputs_hash="h",
    )
    spy = SpyAdapter()
    with connect(ops_db) as conn:
        policy = _policy()
        policy["min_stay_rules"]["enabled"] = True
        push_recommendations(conn, [rec], spy, "handle", policy=policy)
    assert spy.min_stays == [pushed]
