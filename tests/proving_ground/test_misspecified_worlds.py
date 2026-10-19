"""Misspecified-world shapes disagree with the engine's linear S(p)."""

from __future__ import annotations

import random

from proving_ground_exam.market.scoring import owner_net_of_gross
from proving_ground_exam.worlds.misspecified import (
    channel_lag_double_book_risk,
    gamma_frailty_count,
    kinked_wtp_prob,
    linear_engine_prob,
    lognormal_price_prob,
    strategic_waiter_prob,
)


def test_kinked_and_lognormal_are_not_the_engine_curve():
    reference = 2000.0
    price = 2600.0
    engine = linear_engine_prob(price, reference)
    assert kinked_wtp_prob(price, reference) != engine
    assert lognormal_price_prob(price, reference) != engine
    # Above the kink the PODS template falls faster than it does just below.
    assert kinked_wtp_prob(reference * 1.3, reference) < kinked_wtp_prob(reference, reference)


def test_waiter_and_frailty_and_channel_flag():
    assert strategic_waiter_prob(2000, 2000, 90) < strategic_waiter_prob(2000, 2000, 10)
    rng = random.Random(1)
    draws = [gamma_frailty_count(4.0, 1.0, rng) for _ in range(30)]
    assert max(draws) > min(draws)
    assert channel_lag_double_book_risk(2) == "double_book_risk"
    assert channel_lag_double_book_risk(-1) == "unavailable"


def test_owner_net_hindsight_flags_the_fee_base():
    out = owner_net_of_gross(1000.0)
    assert out["owner_net"] == 595.0
    assert out["fee_base_confirmed"] is False
