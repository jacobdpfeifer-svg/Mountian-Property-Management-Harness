"""Turns, slack, cost, readiness probability, capacity, and the shadow report."""

from __future__ import annotations

from datetime import date

import pytest
from conftest import add_open_nights, add_reservation, add_signal

from src.db import connect
from src.ops import TurnoverOutcome
from src.ops.db import record_outcomes, start_import
from src.ops.economics import (
    capacity_view,
    observed_readiness,
    ready_probability,
    turn_cost,
)
from src.ops.profiles import load_ops_config, load_ops_policy, load_profiles, resolve_profiles
from src.ops.shadow import build_report
from src.ops.turns import derive_turns

AS_OF = date(2026, 12, 1)


@pytest.fixture()
def profiles():
    return load_profiles()


@pytest.fixture()
def policy():
    return load_ops_policy()


def test_profile_estimate_is_the_documented_build_up(profiles):
    p = profiles["summit_haus"]
    assert p.basis == "estimate"
    # 480 clean + 45 inspection + 60 hot tub (laundry offsite) = 585 worker-minutes.
    assert p.worker_minutes() == 585
    assert p.elapsed_minutes() == 195
    # 585/60*$40 + 20 min travel x 3 workers + $60 + $180 laundry + $50 spa.
    assert p.estimated_cost() == 720.0
    assert p.estimated_cost(snow=True) == 720.0 + 60 / 60 * 40 + 85


def test_profile_version_changes_with_content():
    cfg = load_ops_config()
    a = resolve_profiles(cfg)["summit_haus"].version
    cfg["properties"]["summit_haus"]["base_clean_minutes"] = 481
    assert resolve_profiles(cfg)["summit_haus"].version != a


def test_unknown_profile_field_is_rejected():
    cfg = load_ops_config()
    cfg["properties"]["summit_haus"]["clean_minutes_typo"] = 1
    with pytest.raises(ValueError):
        resolve_profiles(cfg)


def test_turns_cover_same_day_gap_and_open_departures(ops_db, profiles, policy):
    with connect(ops_db) as conn:
        add_reservation(conn, "r1", "summit_haus", date(2026, 12, 20), date(2026, 12, 23))
        add_reservation(conn, "r2", "summit_haus", date(2026, 12, 23), date(2026, 12, 26))
        add_reservation(conn, "r3", "summit_haus", date(2026, 12, 28), date(2027, 1, 2))
        add_reservation(conn, "own", "summit_haus", date(2027, 1, 2), date(2027, 1, 4), source="owner")
        add_reservation(conn, "x", "summit_haus", date(2027, 1, 5), date(2027, 1, 7), status="canceled")
        turns = derive_turns(conn, profiles["summit_haus"], date(2026, 12, 1), date(2027, 1, 31),
                             as_of=AS_OF, ops_policy=policy)
    by_dep = {t.departing_reservation: t for t in turns}
    assert set(by_dep) == {"r1", "r2", "r3", "own"}
    assert by_dep["r1"].same_day and by_dep["r1"].turn_id == "summit_haus|r1|r2"
    # 360-minute window - 195 elapsed - 20 travel.
    assert by_dep["r1"].slack_minutes == 145
    assert by_dep["r2"].gap_nights == 2
    assert by_dep["r3"].arriving_reservation == "own"  # owner stays still need a turn
    assert by_dep["own"].arriving_reservation is None and by_dep["own"].slack_minutes is None


def test_weather_buffer_is_point_in_time(ops_db, profiles, policy):
    with connect(ops_db) as conn:
        add_reservation(conn, "r1", "summit_haus", date(2026, 12, 20), date(2026, 12, 23))
        add_reservation(conn, "r2", "summit_haus", date(2026, 12, 23), date(2026, 12, 26))
        # Snow forecast that we only learn about on 12-22.
        add_signal(conn, "weather.snowfall_sum_cm", 20, date(2026, 12, 23), observed=date(2026, 12, 22))
        conn.commit()
        early = derive_turns(conn, profiles["summit_haus"], date(2026, 12, 23), date(2026, 12, 23),
                             as_of=date(2026, 12, 21), ops_policy=policy)[0]
        late = derive_turns(conn, profiles["summit_haus"], date(2026, 12, 23), date(2026, 12, 23),
                            as_of=date(2026, 12, 22), ops_policy=policy)[0]
    assert early.weather_buffer_minutes == 0 and not early.snow_expected
    assert late.weather_buffer_minutes == 45 and late.snow_expected
    # Snow adds 60 worker-minutes of clearance (20 elapsed with 3 workers) and the 45 buffer.
    assert late.slack_minutes == early.slack_minutes - 20 - 45


def test_cost_switches_to_observed_median_with_enough_turns(ops_db, profiles, policy):
    with connect(ops_db) as conn:
        result = start_import(conn, "csv", "outcomes")
        outcomes = [TurnoverOutcome("summit_haus", f"2026-11-0{i}", "csv:generic", f"t{i}", cost=c)
                    for i, c in enumerate([700, 800, 900, 1000], start=1)]
        record_outcomes(conn, outcomes, result)
        est = turn_cost(conn, profiles["summit_haus"], as_of=AS_OF, ops_policy=policy)
        record_outcomes(conn, [TurnoverOutcome("summit_haus", "2026-11-05", "csv:generic", "t5",
                                               cost=1100)], result)
        obs = turn_cost(conn, profiles["summit_haus"], as_of=AS_OF, ops_policy=policy)
        # A turn after as_of is not visible.
        future = turn_cost(conn, profiles["summit_haus"], as_of=date(2026, 11, 5), ops_policy=policy)
    assert (est.basis, est.amount, est.n) == ("estimate", 720.0, 4)
    assert (obs.basis, obs.amount, obs.n) == ("observed", 900.0, 5)
    assert future.basis == "estimate"


def test_ready_probability_shrinks_toward_the_bucket_prior(policy):
    prior = ready_probability(50, policy)
    assert prior.p == pytest.approx(0.70) and prior.n == 0
    shrunk = ready_probability(50, policy, {60: (2, 10)})
    assert shrunk.p == pytest.approx((10 * 0.70 + 2) / 20)
    assert ready_probability(None, policy).prior == 0.97
    assert ready_probability(-30, policy).prior == 0.35


def test_observed_readiness_joins_outcomes_to_turn_slack(ops_db, profiles, policy):
    with connect(ops_db) as conn:
        add_reservation(conn, "r1", "summit_haus", date(2026, 11, 1), date(2026, 11, 4))
        add_reservation(conn, "r2", "summit_haus", date(2026, 11, 4), date(2026, 11, 8))
        result = start_import(conn, "csv", "outcomes")
        record_outcomes(conn, [TurnoverOutcome("summit_haus", "2026-11-04", "csv:generic", "late",
                                               late_ready_minutes=30)], result)
        obs = observed_readiness(conn, profiles, AS_OF, policy)
    # Same-day slack 145 minutes falls in the <=240 bucket.
    assert obs == {240: (0, 1)}


def test_capacity_flags_the_twins_turning_on_one_day(ops_db, profiles, policy):
    with connect(ops_db) as conn:
        for pid in ("summit_haus", "overlook_ridge"):
            add_reservation(conn, f"{pid}-a", pid, date(2026, 12, 28), date(2027, 1, 1))
        turns = []
        for pid in ("summit_haus", "overlook_ridge"):
            turns += derive_turns(conn, profiles[pid], date(2027, 1, 1), date(2027, 1, 1),
                                  as_of=AS_OF, ops_policy=policy)
        view = capacity_view(conn, "northwoods", date(2027, 1, 1), as_of=AS_OF,
                             ops_cfg=load_ops_config(), profiles=profiles, turns=turns)
    assert view.available_source == "roster" and view.available_worker_minutes == 1260
    assert view.committed_worker_minutes == 2 * (585 + 20 * 3)
    assert view.utilization > 1.0


def test_shadow_report_counts_extra_turns_from_shorter_minimums(ops_db):
    with connect(ops_db) as conn:
        add_open_nights(conn, "cloud_9", date(2027, 1, 10), 6, min_stay=3)
        conn.execute(
            """INSERT INTO price_recommendations (run_id, property_id, stay_date, recommended_price,
                   ceiling_price, floor_price, rule_version, model_version, inputs_hash,
                   recommended_min_stay, min_stay_source)
               VALUES ('run1','cloud_9','2027-01-10',1000,2000,500,'r','m','h',2,'policy')"""
        )
        conn.commit()
        report = build_report(conn, date(2027, 1, 1), date(2027, 1, 31), as_of=AS_OF,
                              property_ids=["cloud_9"])
    [row] = report.min_stay
    assert row["nights"] == 6 and row["max_turns_pms"] == 2 and row["max_turns_recommended"] == 3
    assert row["extra_turns_recommended"] == 1
    assert row["extra_cost_recommended"] == 690.0
    assert row["by_candidate"]["1"]["max_turns"] == 6
