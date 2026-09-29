"""Pass/fail thresholds for the Proving Ground ladder."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LevelThreshold:
    level: int
    regret_vs_oracle_max: float
    baseline_rule: str
    brier_improvement_min: float | None
    worst10_loss_multiplier_max: float
    humility_false_alarm_max: float | None = None
    humility_score_min: float | None = None


HARD_GATES = {
    "lookahead_violations": 0,
    "guesty_write_attempts": 0,
    "guardrail_violations": 0,
    "auto_pushes_while_unhealthy": 0,
}


LEVEL_THRESHOLDS = {
    1: LevelThreshold(
        level=1,
        regret_vs_oracle_max=0.05,
        baseline_rule="at_least_best_baseline",
        brier_improvement_min=0.20,
        worst10_loss_multiplier_max=1.00,
        humility_false_alarm_max=0.05,
    ),
    2: LevelThreshold(
        level=2,
        regret_vs_oracle_max=0.10,
        baseline_rule="at_least_best_baseline_every_world",
        brier_improvement_min=0.15,
        worst10_loss_multiplier_max=1.00,
        humility_false_alarm_max=0.05,
    ),
    3: LevelThreshold(
        level=3,
        regret_vs_oracle_max=0.15,
        baseline_rule="beats_moat_off_ci_in_2_of_3_markets",
        brier_improvement_min=0.10,
        worst10_loss_multiplier_max=1.10,
        humility_false_alarm_max=0.10,
    ),
    4: LevelThreshold(
        level=4,
        regret_vs_oracle_max=0.20,
        baseline_rule="at_least_best_baseline_in_80_pct_scenarios",
        brier_improvement_min=0.05,
        worst10_loss_multiplier_max=1.25,
        humility_score_min=0.50,
    ),
    5: LevelThreshold(
        level=5,
        regret_vs_oracle_max=0.30,
        baseline_rule="at_least_median_baseline_every_scenario",
        brier_improvement_min=None,
        worst10_loss_multiplier_max=1.50,
        humility_score_min=0.70,
    ),
    6: LevelThreshold(
        level=6,
        regret_vs_oracle_max=1.00,
        baseline_rule="beats_4_of_5_baselines_on_regret",
        brier_improvement_min=None,
        worst10_loss_multiplier_max=2.00,
        humility_score_min=0.80,
    ),
}
