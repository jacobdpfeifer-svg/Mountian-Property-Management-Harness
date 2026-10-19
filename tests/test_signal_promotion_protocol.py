"""Regression tests for the promotion-protocol fixes."""

from __future__ import annotations

from src.eval.backtest import hit_rate
from src.signals.promotion import benjamini_hochberg, null_promotion_rates


def test_hit_rate_ignores_zeros_in_the_denominator_and_centres():
    pairs = [(1.0, 1.0), (2.0, 1.0), (3.0, 1.0), (0.0, 1.0), (4.0, 1.0), (5.0, -1.0)]
    # Mean signal is 2.5. After centring, the raw zero is not zero, so it counts.
    # Two of the six centred pairs agree with the outcome sign.
    assert hit_rate(pairs) == 2 / 6
    # A centred zero is left out of the denominator, as is a zero outcome.
    flat = [(1.0, 1.0), (1.0, -1.0), (1.0, 1.0), (1.0, -1.0), (1.0, 0.0), (3.0, 1.0)]
    # Mean signal is 8/6. Five centred values are negative; the last is positive.
    # The zero outcome is dropped. Three of the five remaining pairs agree.
    assert hit_rate(flat) == 3 / 5


def test_hit_rate_returns_none_when_too_few_nonzero_pairs():
    pairs = [(1.0, 0.0)] * 6
    assert hit_rate(pairs) is None


def test_benjamini_hochberg_rejects_only_the_small_p_values():
    flags = benjamini_hochberg([0.001, 0.04, 0.2, 0.8], q=0.10)
    assert flags[0] is True
    assert flags[3] is False


def test_null_monte_carlo_controlled_rate_is_below_the_uncorrected_rate():
    rates = null_promotion_rates(n_sims=80, n_signals=20, n_seasons=6)
    assert rates["uncorrected"] > 0.25
    assert rates["bh"] < rates["uncorrected"]
    assert rates["bh"] < 0.20
