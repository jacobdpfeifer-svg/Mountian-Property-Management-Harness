"""Tests for the flag-gated pricing math and the default-off wiring."""

from datetime import date, timedelta

from src.bookprob import BookingProbability
from src.features import NightFeatures
from src.pricing import (
    apply_interim_guard,
    apply_models,
    best_horizon_price,
    candidate_min_stays,
    demand_price_factor,
    enabled,
    estimate_beta,
    portfolio_lambda,
    portfolio_pair,
    posterior_beta,
    stay_choice,
    thompson_beta,
    unconstrained_optimum,
)


def test_flags_default_off_when_the_block_is_missing():
    assert enabled({}, "learned_elasticity") is False
    assert enabled({"models": {"learned_elasticity": {"enabled": False}}}, "learned_elasticity") is False
    assert enabled({"models": {"learned_elasticity": {"enabled": True}}}, "learned_elasticity") is True


def test_beta_hat_needs_both_sides_and_clips():
    flat = [100.0] * 8 + [110.0] * 8
    booked = [True] * 8 + [False] * 8
    # A small price gap and a collapse in the book rate is steeper than -2.5.
    assert estimate_beta(flat, booked) == -2.5
    mild = [100.0] * 8 + [200.0] * 8
    assert estimate_beta(mild, booked) == -1.0
    assert estimate_beta(mild[:10], booked[:10]) is None


def test_posterior_keeps_the_prior_without_a_slope():
    assert posterior_beta(-0.65, None, 0) == -0.65
    post = posterior_beta(-0.65, -1.5, 40)
    assert abs(post - ((40 * -0.65 + 40 * -1.5) / 80)) < 1e-9


def test_thompson_is_stable_for_a_seed_and_skipped_on_blackout():
    stay = date(2026, 12, 25)
    as_of = date(2026, 11, 1)
    first = thompson_beta(-1.2, 40, property_id="summit_haus", stay_date=stay, as_of=as_of, explore=True)
    second = thompson_beta(-1.2, 40, property_id="summit_haus", stay_date=stay, as_of=as_of, explore=True)
    assert first == second
    assert thompson_beta(-0.2, 40, property_id="summit_haus", stay_date=stay, as_of=as_of, explore=False) == -0.3


def test_interim_guard_forces_a_peak_night_behind_pace_to_be_elastic():
    assert apply_interim_guard(-0.65, season="peak_ski", pacing_ratio=0.5, lead_days=14) == -1.05
    assert apply_interim_guard(-1.4, season="peak_ski", pacing_ratio=0.5, lead_days=14) == -1.4
    assert apply_interim_guard(-0.65, season="early_winter", pacing_ratio=0.5, lead_days=14) == -0.65


def test_demand_factor_moves_with_pace_and_stays_inside_the_band():
    assert demand_price_factor(pacing_ratio=1, sqi=1, event=False) == 1.0
    hot = demand_price_factor(pacing_ratio=2, sqi=1.5, event=True, macro_z=1)
    assert hot == 1.20
    cold = demand_price_factor(pacing_ratio=0, sqi=0.5, event=False)
    assert cold == 0.85


def test_horizon_can_prefer_a_higher_price_when_continuation_is_valuable():
    # At a low price the book probability is high but continuation is worth more if we wait.
    price, _value = best_horizon_price([100.0, 200.0], [0.9, 0.4], continuation=180.0)
    assert price == 200.0
    myopic, _ = best_horizon_price([100.0, 200.0], [0.9, 0.4], continuation=0.0)
    assert myopic == 100.0


def test_stay_choice_picks_the_longer_stay_when_it_pays_and_caps_the_move():
    anchor = date(2027, 2, 1)
    prices = {anchor + timedelta(days=i): 400.0 + i for i in range(5)}
    length, delta = stay_choice(anchor, prices, [2, 4], standing=2, orphan_gap=0)
    assert length == 4
    assert abs(delta) <= 0.08 * prices[anchor] + 1e-6


def test_orphan_gap_shorter_than_the_rule_is_a_candidate():
    assert 1 in candidate_min_stays([2, 3], gap_nights=1, standing=2)


def test_cancel_survival_falls_as_lead_time_grows():
    from src.pricing import cancel_survival

    assert cancel_survival(0) == 1.0
    assert cancel_survival(7) > cancel_survival(60)
    assert 0.5 < cancel_survival(60) < 1.0


def test_portfolio_lambda_is_higher_when_twins_are_close_and_cloud_9_has_no_pair():
    assert portfolio_lambda(900, 920) == 0.15
    assert portfolio_lambda(900, 1200) == 0.05
    assert portfolio_pair("summit_haus") == "overlook_ridge"
    assert portfolio_pair("cloud_9") is None
    assert unconstrained_optimum(700, -0.65) > 700


def _night() -> NightFeatures:
    return NightFeatures(
        property_id="summit_haus",
        stay_date=date(2026, 12, 25),
        status="available",
        listed_price=2000.0,
        booked_price=None,
        lead_time_days=30,
        day_of_week=4,
        season="peak_ski",
        season_multiplier=1.15,
        lead_multiplier=1.0,
        dow_multiplier=1.0,
        demand_strength=0.5,
        demand_event=None,
        is_orphan_gap=False,
        gap_size=0,
        min_floor_rate=300.0,
        max_ceiling_rate=4000.0,
        base_ceiling_rate=800.0,
        min_stay=3,
    )


def _probability() -> BookingProbability:
    return BookingProbability(0.4, 1000.0, -1.2, "22-60", 20, False, 1.5)


def test_disabled_models_return_the_same_probability_object():
    bp = _probability()
    adjustment = apply_models(
        None, _night(), {}, bp,
        as_of=date(2026, 9, 29), floor=300, ceil=2000, sqi=1.0, steps=10,
    )
    assert adjustment.probability is bp
    assert adjustment.reasons == []
    assert adjustment.objective is None
    assert adjustment.price_delta == 0.0


def test_demand_flag_scales_the_reference_price(tmp_path):
    from src.db import connect, init_db

    path = tmp_path / "models.db"
    init_db(path)
    policy = {"models": {"demand_shifts_price": {"enabled": True}}, "seasons": {}}
    bp = _probability()
    with connect(path) as conn:
        adjustment = apply_models(
            conn, _night(), policy, bp,
            as_of=date(2026, 9, 29), floor=300, ceil=2000, sqi=1.0, steps=10,
        )
    assert adjustment.probability is not bp
    assert abs(adjustment.probability.price_ref - 1075.0) < 1e-6
    assert adjustment.reasons[0][0] == "demand_level"


def test_portfolio_flag_scales_the_reference_when_the_twin_quote_is_known():
    policy = {"models": {"portfolio_pricing": {"enabled": True}}}
    bp = _probability()
    quotes = {("overlook_ridge", date(2026, 12, 25)): 1980.0}
    adjustment = apply_models(
        None, _night(), policy, bp,
        as_of=date(2026, 9, 29), floor=300, ceil=2000, sqi=1.0, steps=10,
        portfolio_quotes=quotes,
    )
    assert abs(adjustment.probability.price_ref - 850.0) < 1e-6
    assert adjustment.reasons[0][0] == "portfolio_cannibalization"
