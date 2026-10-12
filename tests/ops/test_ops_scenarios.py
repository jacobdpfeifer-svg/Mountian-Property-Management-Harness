"""Stage 4 operations scenarios on the market sim (SIMULATED)."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from src.proving_ground.ops_scenarios import (
    ARMS,
    OPS_SCENARIOS,
    SPECS,
    arm_policy,
    run_ops_job,
)


def test_every_scenario_is_defined_with_a_deterministic_truth():
    assert set(SPECS) == set(OPS_SCENARIOS) and len(OPS_SCENARIOS) == 9
    for name, spec in SPECS.items():
        a = spec.build(random.Random(f"normal|{name}|7"))
        b = spec.build(random.Random(f"normal|{name}|7"))
        assert a == b, name


def test_arm_policies_are_copies_and_never_touch_the_default():
    from src.config import load_policy

    before = load_policy()
    assert arm_policy("off")["operations"]["readiness_gate"] is False
    assert arm_policy("stay")["models"]["ops_aware_stay"]["enabled"] is True
    after = load_policy()
    assert after == before
    assert after["models"]["ops_aware_stay"]["enabled"] is False
    assert after["operations"]["readiness_gate"] is True
    assert set(ARMS) == {"off", "on", "stay", "flat"}


@pytest.mark.slow
def test_hot_tub_failure_closes_and_never_changes_a_restricted_night(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MONTLUXE_MEMORY_ROOT", str(tmp_path / "mem"))
    on = run_ops_job("normal", "hot_tub_failure", 1, "on", tmp_path / "on.db")
    off = run_ops_job("normal", "hot_tub_failure", 1, "off", tmp_path / "off.db")
    assert on.violations == 0
    assert on.escalations_raised >= 1 and off.escalations_raised == 0
    assert on.closures >= 1 and off.closures == 0
    assert on.detail["truth"]["repair_days"] == off.detail["truth"]["repair_days"]
