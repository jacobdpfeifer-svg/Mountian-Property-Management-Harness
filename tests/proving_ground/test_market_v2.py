"""Calibration v2 (2026-10-14 overhaul): realistic market level, fees judged
all-in, per-home value, capacity, owner economics, production-faithful mode.

v1 must stay bit-identical; that is proven by scripts/regress_market_sim.py
against the golden boards, not here.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from proving_ground_exam.market.choice import Alternative, all_in_nightly, alternative_utility, loss_reason
from proving_ground_exam.market.parameters import load_calibration, reference_price, seasonal, stay_fees
from proving_ground_exam.market.scoring import stay_economics
from proving_ground_exam.market.shoppers import Shopper
from src.proving_ground.market_loop import resolve_calibration, run_market_job

V2 = resolve_calibration("v2")


def _shopper(*, party: int = 10, los: int = 2, wtp: float = 1.2, coef: float = -1.1) -> Shopper:
    return Shopper(
        shopper_id="s", segment="families_at_holidays", check_in=date(2027, 2, 10), los=los,
        party=party, channel="airbnb", wtp_multiplier=wtp, price_coef=coef, gumbels={},
        convert_u=0.0, decision_day=date(2027, 1, 1),
    )


def _free(alt_id: str) -> dict[str, set[date]]:
    return {alt_id: {date(2027, 2, 10), date(2027, 2, 11), date(2027, 2, 12), date(2027, 2, 13)}}


KW = dict(fit_penalty=-1.2, fit_ratio=0.35, season_end=date(2027, 4, 29))


def test_v2_calibration_loads_with_every_value_sourced():
    cal = load_calibration(V2)
    assert cal["version"] == 2
    assert cal["properties"]["cloud_9"]["sleeps"] == 18
    assert set(cal["current_practice"]) == set(cal["properties"])


def test_reference_price_uses_season_and_holiday():
    cal = load_calibration(V2)
    assert reference_price(cal, date(2027, 2, 10), holiday=False) == 2000
    assert reference_price(cal, date(2026, 12, 26), holiday=True) == 2600
    assert reference_price(cal, date(2026, 11, 10), holiday=False) == 900
    v1 = load_calibration(resolve_calibration("v1"))
    assert reference_price(v1, date(2027, 2, 10), holiday=True) == 700


def test_seasonal_picks_a_season_but_leaves_other_mappings_alone():
    assert seasonal({"peak_ski": 1.2, "early_winter": 1.1, "shoulder_spring": 1.05}, "early_winter") == 1.1
    assert seasonal({"low": 6, "mode": 10, "high": 16}, "peak_ski") == {"low": 6, "mode": 10, "high": 16}
    assert seasonal([0.1, 0.9], "peak_ski") == [0.1, 0.9]


def test_fees_raise_the_all_in_price_most_for_short_stays_and_big_parties():
    fees = {"cleaning_per_stay": 600, "per_guest": 75, "insurance_per_stay": 80}
    assert stay_fees(fees, 12) == 600 + 900 + 80
    alt = Alternative("cloud_9", "own", 18, 1.0, 2000.0, fees=stay_fees(fees, 12))
    two = all_in_nightly(alt, _shopper(party=12, los=2))
    seven = all_in_nightly(alt, _shopper(party=12, los=7))
    assert two == pytest.approx(2000 + 1580 / 2)
    assert two > seven > 2000
    # Fees shown less prominently count less (drip display).
    assert all_in_nightly(alt, _shopper(party=12, los=2), fee_salience=0.5) == pytest.approx(2000 + 395)


def test_fees_can_push_a_stay_over_the_shopper_cap():
    shopper = _shopper(party=12, los=2, wtp=1.2)
    no_fee = Alternative("h", "own", 18, 1.0, 2000.0)
    with_fee = Alternative("h", "own", 18, 1.0, 2000.0, fees=1580.0)
    assert alternative_utility(shopper, no_fee, free=_free("h"), median=2000.0, **KW) > -1e17
    assert alternative_utility(shopper, with_fee, free=_free("h"), median=2000.0, **KW) == -1e18
    assert loss_reason(shopper, with_fee, None, free=_free("h"), median=2000.0, **KW) == "above_wtp"


def test_value_index_raises_what_shoppers_will_pay_for_a_home():
    shopper = _shopper(wtp=1.0)
    plain = Alternative("h", "own", 18, 1.0, 2100.0)
    valued = Alternative("h", "own", 18, 1.0, 2100.0, value_index=1.10)
    assert alternative_utility(shopper, plain, free=_free("h"), median=2000.0, **KW) == -1e18
    assert alternative_utility(shopper, valued, free=_free("h"), median=2000.0, **KW) > -1e17


def test_capacity_screen_stops_a_party_too_big_for_the_home():
    shopper = _shopper(party=17)
    twin = Alternative("summit_haus", "own", 16, 1.0, 1500.0)
    args = dict(free=_free("summit_haus"), median=2000.0, **KW)
    assert alternative_utility(shopper, twin, **args) > -1e17
    assert alternative_utility(shopper, twin, enforce_capacity=True, **args) == -1e18
    assert loss_reason(shopper, twin, None, enforce_capacity=True, **args) == "capacity"


def test_owner_net_counts_fees_channel_management_and_turnover():
    econ = load_calibration(V2)["economics"]
    fees = load_calibration(V2)["guest_fees"]
    out = stay_economics(4000.0, nights=2, party=10, channel="airbnb", guest_fees=fees, economics=econ)
    guest_paid = 4000 + 600 + 750 + 80
    assert out["guest_paid"] == guest_paid
    assert out["channel_fee"] == pytest.approx(0.155 * guest_paid)
    assert out["management_fee"] == pytest.approx(1000.0)
    assert out["owner_net"] == pytest.approx(guest_paid * 0.845 - 1000 - (350 + 750 + 80))


def test_v2_job_reports_owner_economics_and_current_practice_runs(tmp_path: Path):
    cal = load_calibration(V2)
    result = run_market_job("normal", 1, "current_practice", db_path=tmp_path / "cp.db",
                            max_days=3, calibration=cal)
    for key in ("owner_net", "pm_fee_income", "guest_paid", "channel_fees", "stay_costs"):
        assert key in result.scores
    v1 = run_market_job("normal", 1, "flat", db_path=tmp_path / "v1.db", max_days=3)
    assert "owner_net" not in v1.scores


def test_current_practice_needs_v2(tmp_path: Path):
    with pytest.raises(ValueError, match="calibration v2"):
        run_market_job("normal", 1, "current_practice", db_path=tmp_path / "x.db", max_days=1)


def test_zero_approval_keeps_suggested_prices_off_the_listing(tmp_path: Path):
    """Production pushes only unblocked 'handle' prices; the simulated engine
    only ever suggests, so with nobody approving, listings never move."""
    cal = load_calibration(V2)
    db = tmp_path / "e.db"
    result = run_market_job("normal", 1, "engine", db_path=db, max_days=2, calibration=cal, approval_rate=0.0)
    import sqlite3

    conn = sqlite3.connect(db)
    try:
        listed = {row[0] for row in conn.execute(
            "SELECT DISTINCT listed_price FROM nightly_inventory WHERE stay_date < '2026-12-01'")}
    finally:
        conn.close()
    assert listed == {900.0}
    assert result.scores["guardrail_triggers"] >= 0
