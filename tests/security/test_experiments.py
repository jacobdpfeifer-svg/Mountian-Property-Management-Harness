"""Experiment register: freeze, disjoint seeds, no tuning after freeze, gated evaluation."""

from __future__ import annotations

import json

import pytest

from src.experiments import (
    RegisterError, failure_regions, freeze_register, load_register, open_evaluation,
    paired_interval, record_screen, reliability, screen_decision,
)


def _register(**over):
    base = {"experiment_id": "EXP-T", "candidate_policy": "policy.yaml", "calibration": "cal.yaml",
            "objective": "owner_net", "comparator": "current_practice", "material_harm_margin": 5000,
            "screen": {"seeds": [1, 2, 3], "scenarios": ["normal"]},
            "evaluation": {"seeds": list(range(6, 31)), "scenarios": ["normal", "price_war"]},
            "metrics": ["owner_net"], "stop_conditions": ["any safety failure"]}
    base.update(over)
    return base


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "policy.yaml").write_text("a: 1\n")
    (tmp_path / "cal.yaml").write_text("c: 1\n")
    return tmp_path


def test_freeze_rejects_overlap_and_refreezing(repo):
    with pytest.raises(RegisterError, match="overlap"):
        freeze_register(_register(screen={"seeds": [6], "scenarios": ["normal"]}), repo / "r.json", repo=repo)
    freeze_register(_register(), repo / "r.json", repo=repo)
    with pytest.raises(RegisterError, match="already frozen"):
        freeze_register(_register(), repo / "r.json", repo=repo)


def test_editing_a_frozen_register_is_detected(repo):
    freeze_register(_register(), repo / "r.json", repo=repo)
    body = json.loads((repo / "r.json").read_text())
    body["material_harm_margin"] = 50000
    (repo / "r.json").write_text(json.dumps(body))
    with pytest.raises(RegisterError, match="edited after freeze"):
        load_register(repo / "r.json")


def test_evaluation_stays_closed_after_rework(repo):
    reg = freeze_register(_register(), repo / "r.json", repo=repo)
    decision, ci, why = screen_decision([-9000, -7000, -12000], margin=5000)
    assert decision == "REWORK"
    record_screen(repo / "ledger.jsonl", reg, decision, ci, why, {})
    with pytest.raises(RegisterError, match="closed"):
        open_evaluation(repo / "ledger.jsonl", repo / "r.json", repo=repo)


def test_evaluation_opens_once_and_refuses_post_freeze_tuning(repo):
    reg = freeze_register(_register(), repo / "r.json", repo=repo)
    decision, ci, why = screen_decision([2000, 1500, 3000, 2500], margin=5000)
    assert decision == "ADVANCE_TO_EVALUATION"
    record_screen(repo / "ledger.jsonl", reg, decision, ci, why, {})
    (repo / "policy.yaml").write_text("a: 2\n")   # tuned after the freeze
    with pytest.raises(RegisterError, match="changed after"):
        open_evaluation(repo / "ledger.jsonl", repo / "r.json", repo=repo)
    (repo / "policy.yaml").write_text("a: 1\n")
    open_evaluation(repo / "ledger.jsonl", repo / "r.json", repo=repo)
    with pytest.raises(RegisterError, match="already opened"):
        open_evaluation(repo / "ledger.jsonl", repo / "r.json", repo=repo)


def test_reject_when_harm_is_clear():
    decision, ci, _ = screen_decision([-40000, -38000, -41000, -39000], margin=5000, reject_below=20000)
    assert decision == "REJECT" and ci.hi < -20000


def test_paired_interval_and_failure_regions():
    ci = paired_interval([1.0, 2.0, 3.0, 4.0])
    assert ci.lo <= ci.mean <= ci.hi and ci.favourable == 4
    rows = [{"property": "cloud_9", "season": "peak", "delta": -9000},
            {"property": "cloud_9", "season": "peak", "delta": -7000},
            {"property": "summit_haus", "season": "peak", "delta": 500}]
    assert failure_regions(rows, ("property", "season"), margin=5000) == [
        {"property": "cloud_9", "season": "peak", "n": 2, "mean_delta": -8000.0}]


def test_reliability_against_base_rate():
    out = reliability([0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0], bins=5)
    assert out["beats_base_rate"] and out["brier"] < out["brier_base_rate"]
    with pytest.raises(ValueError):
        reliability([1.2], [1])
