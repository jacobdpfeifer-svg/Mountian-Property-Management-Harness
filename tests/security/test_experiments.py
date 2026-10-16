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


# -- code hash and seed exposure (2026-10-16) -------------------------------------------

def test_code_change_after_freeze_is_a_new_candidate(repo):
    (repo / "src").mkdir()
    (repo / "src" / "anchor.py").write_text("X = 1\n")
    reg = freeze_register(_register(code_paths=["src"]), repo / "r.json", repo=repo)
    decision, ci, why = screen_decision([2000, 1500, 3000, 2500], margin=5000)
    record_screen(repo / "ledger.jsonl", reg, decision, ci, why, {})
    (repo / "src" / "anchor.py").write_text("X = 2\n")
    with pytest.raises(RegisterError, match="new candidate"):
        open_evaluation(repo / "ledger.jsonl", repo / "r.json", repo=repo)
    (repo / "src" / "anchor.py").write_text("X = 1\n")
    (repo / "src" / "__pycache__").mkdir()
    (repo / "src" / "__pycache__" / "anchor.cpython-312.pyc").write_bytes(b"noise")
    open_evaluation(repo / "ledger.jsonl", repo / "r.json", repo=repo)


def test_code_hash_sees_renames_and_new_files(repo):
    from src.experiments import code_sha256
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("X = 1\n")
    h1 = code_sha256(repo, ["src"])
    (repo / "src" / "a.py").rename(repo / "src" / "b.py")
    h2 = code_sha256(repo, ["src"])
    (repo / "src" / "c.py").write_text("")
    assert len({h1, h2, code_sha256(repo, ["src"])}) == 3
    with pytest.raises(RegisterError, match="does not exist"):
        code_sha256(repo, ["missing"])


def test_exposed_seeds_are_refused_at_freeze(repo, tmp_path):
    from src.experiments import exposed_seeds
    runs = tmp_path / "runs" / "old" / "normal"
    runs.mkdir(parents=True)
    (runs / "scoreboard.csv").write_text(
        "scenario,seed,policy,owner_net\n" + "".join(f"normal,{s},engine,1\n" for s in range(1, 31))
        + "price_war,40,engine,1\nbroken,notanint,engine,1\n")
    exposed = exposed_seeds(tmp_path / "runs")
    assert exposed["normal"] == set(range(1, 31)) and exposed["price_war"] == {40}
    with pytest.raises(RegisterError, match="already exposed"):
        freeze_register(_register(), repo / "r.json", repo=repo, exposed=exposed)
    assert not (repo / "r.json").exists()
    fresh = _register(screen={"seeds": [101, 102, 103], "scenarios": ["normal"]},
                      evaluation={"seeds": list(range(201, 226)), "scenarios": ["normal", "price_war"]})
    body = freeze_register(fresh, repo / "r.json", repo=repo, exposed=exposed)
    assert body["seeds_checked_unexposed"] is True
    # The seed is exposed per scenario: 40 is fresh in normal but not in price_war.
    with pytest.raises(RegisterError, match="price_war"):
        freeze_register(_register(experiment_id="EXP-U", screen={"seeds": [41], "scenarios": ["normal"]},
                                  evaluation={"seeds": [40], "scenarios": ["price_war"]}),
                        repo / "u.json", repo=repo, exposed=exposed)


def _rows(policy_net, scenarios=("normal", "price_war"), seeds=range(201, 206), homes=None):
    out = []
    for s in scenarios:
        for n in seeds:
            net = policy_net(s, n)
            split = homes(s, n) if homes else {"a": net / 2, "b": net / 2}
            out.append({"scenario": s, "seed": n, "owner_net": net, "owner_net_by_property": split})
    return out


def _eval_register():
    return {"evaluation": {"seeds": list(range(201, 206)), "scenarios": ["normal", "price_war"],
                           "primary_scenarios": ["normal"]}, "harm_fraction": 0.02, "segment_fraction": 0.03}


def test_evaluation_passes_only_with_superiority_and_no_harm():
    from src.experiments import evaluation_decision
    comp = _rows(lambda s, n: 100_000 + n)
    good = _rows(lambda s, n: 100_000 + n + (4000 + 50 * (n % 3) if s == "normal" else -500 + 30 * (n % 2)))
    assert evaluation_decision(_eval_register(), good, comp)["decision"] == "PASS"
    stress_harm = _rows(lambda s, n: 100_000 + n + (4000 if s == "normal" else -6000 + 10 * n))
    out = evaluation_decision(_eval_register(), stress_harm, comp)
    assert out["decision"] == "FAIL" and any("price_war: harm" in r for r in out["reasons"])
    flat = _rows(lambda s, n: 100_000 + n + (-100 + 50 * (n % 3)))
    assert any("not superior" in r for r in evaluation_decision(_eval_register(), flat, comp)["reasons"])


def test_evaluation_catches_one_home_paying_for_the_other():
    from src.experiments import evaluation_decision
    comp = _rows(lambda s, n: 100_000 + n)
    shifted = _rows(lambda s, n: 104_000 + n + 10 * (n % 2),
                    homes=lambda s, n: {"a": 62_000 + n / 2, "b": 42_000 + n / 2})
    out = evaluation_decision(_eval_register(), shifted, comp)
    assert out["decision"] == "FAIL" and any(" b mean delta" in r for r in out["reasons"])


def test_evaluation_refuses_an_incomplete_board():
    from src.experiments import evaluation_decision
    comp = _rows(lambda s, n: 100_000.0)
    cand = _rows(lambda s, n: 110_000.0)[:-1]
    assert evaluation_decision(_eval_register(), cand, comp)["decision"] == "INCOMPLETE"


def test_board_provenance_closes_every_audited_bypass(repo, tmp_path):
    """2026-10-16 audit V1/V2/V4/V5: each case below passed the gates before the fix."""
    from datetime import datetime, timezone

    from src.experiments import board_provenance_problem, sha256_file
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("X = 1\n")
    reg = freeze_register(_register(code_paths=["src"]), repo / "r.json", repo=repo)
    board = tmp_path / "board"
    board.mkdir()
    good = {"code_sha256": reg["input_sha256"]["code"], "git_dirty_tracked": False,
            "calibration_file_sha256": sha256_file(repo / "cal.yaml"), "sensitivity_label": None,
            "engine_policy_sha256": sha256_file(repo / "policy.yaml")}

    def check(top=None, candidate=True, not_before=None, **cfg):
        body = {"started_at": "2999-01-01T00:00:00+00:00", **(top or {}), "config": {**good, **cfg}}
        (board / "run_config.json").write_text(json.dumps(body))
        return board_provenance_problem(reg, board, candidate=candidate, not_before=not_before)

    assert check() is None
    assert "different code" in check(code_sha256="deadbeef")
    assert "calibration" in check(calibration_file_sha256="WRONG")
    assert "sensitivity" in check(sensitivity_label="fees_high")
    assert "policy" in check(engine_policy_sha256="WRONG")
    assert check(engine_policy_sha256="WRONG", candidate=False) is None     # comparator boards
    assert "clean" in check(git_dirty_tracked=True)
    assert "clean" in check(git_dirty_tracked=None)
    assert "no start" in check(top={"started_at": None})
    assert "before" in check(top={"started_at": "2000-01-01T00:00:00+00:00"})
    # A resume keeps first_started_at; a pre-freeze first start fails even if resumed later.
    assert "before" in check(top={"first_started_at": "2000-01-01T00:00:00+00:00"})
    # Evaluation boards must start after evaluation was opened.
    assert "opened" in check(not_before=datetime(3000, 1, 1, tzinfo=timezone.utc))
    # A register without a code hash fails closed unless it is the legacy one.
    nohash = freeze_register(_register(experiment_id="EXP-NOHASH"), repo / "n.json", repo=repo)
    assert "no code hash" in board_provenance_problem(nohash, board)
    legacy = freeze_register(_register(experiment_id="EXP-PACE-V2-001"), repo / "l.json", repo=repo)
    assert board_provenance_problem(legacy, board) is None


def test_exposure_counts_partial_runs_and_manifests(tmp_path):
    from src.experiments import exposed_seeds
    run = tmp_path / "runs" / "stopped"
    run.mkdir(parents=True)
    (run / "results.jsonl").write_text(json.dumps({"scenario": "normal", "seed": 2001}) + "\nnot json\n")
    (run / "manifest.json").write_text(json.dumps({"rows": [{"scenario": "price_war", "seed": 2002}]}))
    assert exposed_seeds(tmp_path / "runs") == {"normal": {2001}, "price_war": {2002}}


def test_t_interval_has_nominal_coverage_at_five_seeds():
    import random
    rng = random.Random(1)
    hits = 0
    for _ in range(2000):
        ci = paired_interval([rng.gauss(10, 30) for _ in range(5)])
        hits += ci.lo <= 10 <= ci.hi
    assert 0.93 <= hits / 2000 <= 0.97


def test_evaluation_checks_homes_with_non_positive_baselines_and_missing_homes():
    from src.experiments import evaluation_decision
    comp = _rows(lambda s, n: 100_000.0 + n, homes=lambda s, n: {"a": 101_000.0 + n, "b": -1_000.0})
    cand = _rows(lambda s, n: 104_000.0 + n + 10 * (n % 2),
                 homes=lambda s, n: {"a": 154_000.0 + n + 10 * (n % 2), "b": -50_000.0})
    out = evaluation_decision(_eval_register(), cand, comp)
    assert out["decision"] == "FAIL" and any(" b mean delta" in r for r in out["reasons"])
    lacking = _rows(lambda s, n: 104_000.0 + n + 10 * (n % 2), homes=lambda s, n: {"a": 104_000.0 + n})
    out = evaluation_decision(_eval_register(), lacking, comp)
    assert out["decision"] == "FAIL" and any("b missing" in r for r in out["reasons"])


def test_screen_with_require_gain_needs_a_positive_mean():
    d, _, why = screen_decision([-100, 50, -200, 30, -60], margin=5000, require_gain=True)
    assert d == "REWORK" and "no gain" in why
    assert screen_decision([-100, 50, -200, 30, -60], margin=5000)[0] == "ADVANCE_TO_EVALUATION"
    assert screen_decision([900, 1200, 400, 1500, 800], margin=5000, require_gain=True)[0] == "ADVANCE_TO_EVALUATION"
