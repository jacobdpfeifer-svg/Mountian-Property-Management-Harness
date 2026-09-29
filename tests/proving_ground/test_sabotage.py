from __future__ import annotations

from datetime import date

from proving_ground_exam.scoring.demand import score_policy_nights, true_demand
from proving_ground_exam.worlds.w1_calm import W1CalmWorld
from src.proving_ground.sabotage import broken_floor_price, oracle_passes_l1_regret, random_price
from src.proving_ground.thresholds import LEVEL_THRESHOLDS


def _world() -> W1CalmWorld:
    return W1CalmWorld(season_start=date(2026, 12, 1), season_end=date(2026, 12, 31))


def test_broken_engine_fails_l1_regret():
    world = _world()
    dates = world.stay_dates()
    from proving_ground_exam.scoring.demand import oracle_price

    oracle = score_policy_nights(
        dates, season_start=world.season_start, level=1, seed=1,
        price_for_night=lambda s, d: oracle_price(d),
    )
    broken = score_policy_nights(
        dates, season_start=world.season_start, level=1, seed=1,
        price_for_night=lambda s, d: broken_floor_price(s, d),
    )
    orevenue = sum(n.revpan for n in oracle)
    brevenue = sum(n.revpan for n in broken)
    regret = max(orevenue - brevenue, 0) / orevenue
    assert regret > LEVEL_THRESHOLDS[1].regret_vs_oracle_max


def test_random_policy_fails_l1():
    world = _world()
    dates = world.stay_dates()
    oracle_rev = sum(
        n.revpan for n in score_policy_nights(
            dates, season_start=world.season_start, level=1, seed=2,
            price_for_night=lambda s, d: 800.0,
        )
    )
    random_rev = sum(
        n.revpan for n in score_policy_nights(
            dates, season_start=world.season_start, level=1, seed=2,
            price_for_night=lambda s, d: random_price(s, d, seed=2),
        )
    )
    regret = max(oracle_rev - random_rev, 0) / oracle_rev
    assert regret > LEVEL_THRESHOLDS[1].regret_vs_oracle_max


def test_oracle_passes_l1_threshold():
    world = _world()
    dates = world.stay_dates()
    from proving_ground_exam.scoring.demand import oracle_price

    nights = score_policy_nights(
        dates, season_start=world.season_start, level=1, seed=3,
        price_for_night=lambda s, d: oracle_price(d),
    )
    assert oracle_passes_l1_regret(0.0)
