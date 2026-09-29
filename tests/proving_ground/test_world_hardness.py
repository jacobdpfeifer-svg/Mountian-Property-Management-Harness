from __future__ import annotations

from datetime import date

import pytest

from proving_ground_exam.scoring.demand import FLAT_SEASONAL_PRICE, oracle_price, score_policy_nights
from proving_ground_exam.worlds.w1_calm import W1CalmWorld

# Seeds the graded harness actually runs with. 42 is the historical fixture seed;
# 20260925 is the canonical dated run seed used for the L1/L2 artifacts. The rest
# are arbitrary draws so the hardness property is not a single-seed coincidence.
GRADED_SEEDS = (42, 20260925, 1, 7, 101, 999, 20240101, 31337)
MIN_HARDNESS_GAP = 0.05


def _flat_regret(level: int, seed: int) -> float:
    """Flat-vs-oracle regret computed on the SAME scoring path the runner grades with.

    Uses proving_ground_exam.scoring.demand exactly as src/proving_ground/runner.py
    does, so a passing assertion here certifies the season the run is actually graded on.
    """
    world = W1CalmWorld(season_start=date(2026, 11, 1), season_end=date(2027, 4, 15))
    dates = world.stay_dates()
    oracle = score_policy_nights(
        dates, season_start=world.season_start, level=level, seed=seed,
        price_for_night=lambda s, d: oracle_price(d),
    )
    flat = score_policy_nights(
        dates, season_start=world.season_start, level=level, seed=seed,
        price_for_night=lambda s, d: FLAT_SEASONAL_PRICE,
    )
    orevenue = sum(n.revpan for n in oracle)
    frevenue = sum(n.revpan for n in flat)
    return (orevenue - frevenue) / orevenue


@pytest.mark.parametrize("level", (1, 2))
@pytest.mark.parametrize("seed", GRADED_SEEDS)
def test_flat_seasonal_regret_gap_at_least_five_points(level: int, seed: int) -> None:
    """A flat-seasonal baseline must trail the oracle by >= 5pp on every graded seed.

    This is the world-hardness invariant: if a do-nothing flat price nearly matches
    the oracle, the season is too easy to distinguish the engine from a constant and
    the level proves nothing. Asserting across every seed the harness runs with (not
    just one) keeps hardness from being a per-seed accident.
    """
    regret = _flat_regret(level, seed)
    assert regret >= MIN_HARDNESS_GAP, (
        f"L{level} seed={seed}: flat regret {regret:.4f} < {MIN_HARDNESS_GAP} "
        "— world is too flat to grade the engine on this seed"
    )
