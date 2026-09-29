from src.compose import advisory_ceiling, final_clamped_price
from src.config import load_policy
from src.utils import clamp_price, round_price_conservative


def test_conservative_round_can_overrun_ceiling_when_listed_is_higher():
    assert round_price_conservative(691.0, 900.0, round_to=5) == 695.0


def test_clamp_price_restores_ceiling_after_overrun_round():
    rounded = round_price_conservative(691.0, 900.0, round_to=5)
    assert clamp_price(rounded, 400.0, 691.0) == 691.0


def test_weak_ceiling_does_not_undo_decrease_cap():
    """Cloud 9 2027-02-14 shape: listed ~$3949, rounded cap $3700, weak ceil $2683."""
    floor, ceil, rounded = 277.0, 2683.34, 3700.0
    assert clamp_price(rounded, floor, ceil) == ceil
    assert final_clamped_price(rounded, floor, ceil, weak_ceiling=True) == rounded


def test_strong_ceiling_still_caps_after_round():
    rounded = round_price_conservative(691.0, 900.0, round_to=5)
    assert final_clamped_price(rounded, 400.0, 691.0, weak_ceiling=False) == 691.0


def test_advisory_ceiling_matches_deference_band_not_030():
    policy = load_policy()
    dcfg = policy["compose"]["deference"]
    assert dcfg["advisory_ceiling_below_confidence"] == dcfg["below_confidence"]
    assert advisory_ceiling(0.29, policy) is True
    assert advisory_ceiling(0.35, policy) is True
    assert advisory_ceiling(0.79, policy) is True
    assert advisory_ceiling(0.80, policy) is False
    assert final_clamped_price(3700.0, 277.0, 2683.34, weak_ceiling=True) == 3700.0
