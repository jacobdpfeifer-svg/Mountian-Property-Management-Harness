"""The experiment scripts and CLI commands end to end (audit V13: these had no tests)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import freeze_experiment  # noqa: E402
import screen_gate  # noqa: E402

from src.experiments import load_register, sha256_file  # noqa: E402

V3_SPEC = ROOT / "docs" / "reports" / "final_delivery" / "experiments" / "EXP-PACE-V3-001.spec.json"


def test_freeze_refuses_unknown_scenarios_exposed_seeds_and_a_dirty_tree(tmp_path, monkeypatch):
    spec = json.loads(V3_SPEC.read_text())
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**spec, "screen": {**spec["screen"], "scenarios": ["weather"]}}))
    assert freeze_experiment.main(["--spec", str(bad), "--register", str(tmp_path / "r.json"),
                                   "--runs-root", str(tmp_path / "runs"), "--allow-dirty"]) == 2
    runs = tmp_path / "runs" / "x"
    runs.mkdir(parents=True)
    (runs / "results.jsonl").write_text(json.dumps({"scenario": "normal", "seed": 1003}) + "\n")
    assert freeze_experiment.main(["--spec", str(V3_SPEC), "--register", str(tmp_path / "r.json"),
                                   "--runs-root", str(tmp_path / "runs"), "--allow-dirty"]) == 2
    assert not (tmp_path / "r.json").exists()

    class Dirty:
        stdout = " M src/pricing/pace.py"
    monkeypatch.setattr(freeze_experiment.subprocess, "run", lambda *a, **k: Dirty())
    assert freeze_experiment.main(["--spec", str(V3_SPEC), "--register", str(tmp_path / "r.json"),
                                   "--runs-root", str(tmp_path / "empty")]) == 2


def test_freeze_records_full_code_paths_for_v3(tmp_path):
    out = tmp_path / "v3.json"
    assert freeze_experiment.main(["--spec", str(V3_SPEC), "--register", str(out),
                                   "--runs-root", str(tmp_path / "empty"), "--allow-dirty"]) == 0
    reg = load_register(out)
    assert reg["code_paths"] == ["src", "config/policies", "proving_ground_exam"]
    assert reg["seeds_checked_unexposed"] and reg["input_sha256"]["code"]


def _board(path: Path, reg: dict, policy: str, nets: dict[int, float], *, candidate: bool) -> Path:
    path.mkdir(parents=True)
    with open(path / "scoreboard.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["scenario", "seed", "policy", "owner_net"])
        w.writeheader()
        for scenario in ("normal", "scrape_degraded"):          # the V3 screen worlds
            for seed, net in nets.items():
                w.writerow({"scenario": scenario, "seed": seed, "policy": policy, "owner_net": net})
    cfg = {"code_sha256": reg["input_sha256"]["code"], "calibration_sha256": reg["input_sha256"]["calibration"],
           "calibration_file_sha256": reg["input_sha256"]["calibration"], "git_dirty_tracked": False,
           "sensitivity_label": None,
           "engine_policy_sha256": reg["input_sha256"]["candidate_policy"] if candidate else "x"}
    (path / "run_config.json").write_text(json.dumps({"started_at": "2999-01-01T00:00:00+00:00", "config": cfg}))
    return path


def _frozen_v3(tmp_path) -> tuple[Path, dict]:
    out = tmp_path / "v3.json"
    freeze_experiment.main(["--spec", str(V3_SPEC), "--register", str(out),
                            "--runs-root", str(tmp_path / "empty"), "--allow-dirty"])
    return out, load_register(out)


@pytest.mark.parametrize("cand_delta,expected", [
    ({1001: 300, 1002: -200, 1003: 100, 1004: -400, 1005: -100}, "REWORK"),   # harm excluded, no gain
    ({1001: 9000, 1002: 7000, 1003: 8000, 1004: 10000, 1005: 6000}, "ADVANCE_TO_EVALUATION"),
    ({1001: -30000, 1002: -25000, 1003: -28000, 1004: -26000, 1005: -31000}, "REWORK"),
])
def test_screen_gate_uses_require_gain_and_the_fractional_margin(tmp_path, cand_delta, expected):
    reg_path, reg = _frozen_v3(tmp_path)
    base = {s: 400_000.0 + 1000 * (s % 3) for s in range(1001, 1006)}
    comp = _board(tmp_path / "comp", reg, "current_practice", base, candidate=False)
    cand = _board(tmp_path / "cand", reg, "engine", {s: base[s] + d for s, d in cand_delta.items()},
                  candidate=True)
    ledger = tmp_path / "ledger.jsonl"
    assert screen_gate.main(["--register", str(reg_path), "--ledger", str(ledger),
                             "--candidate-board", str(cand), "--comparator-board", str(comp)]) == 0
    entry = json.loads(ledger.read_text().splitlines()[-1])
    assert entry["decision"] == expected


def test_screen_gate_refuses_spec_freezing_for_new_experiments_and_wrong_policy_boards(tmp_path):
    reg_path, reg = _frozen_v3(tmp_path)
    assert screen_gate.main(["--spec", str(V3_SPEC), "--register", str(tmp_path / "new.json"),
                             "--ledger", str(tmp_path / "l.jsonl"), "--candidate-board", "x",
                             "--comparator-board", "y"]) == 2
    base = {s: 400_000.0 for s in range(1001, 1006)}
    comp = _board(tmp_path / "comp", reg, "current_practice", base, candidate=False)
    cand = _board(tmp_path / "cand", reg, "engine", base, candidate=False)    # wrong policy hash
    assert screen_gate.main(["--register", str(reg_path), "--ledger", str(tmp_path / "l.jsonl"),
                             "--candidate-board", str(cand), "--comparator-board", str(comp)]) == 2


def test_market_run_config_records_the_seed_range():
    from src.proving_ground.market_loop import run_config
    cfg = run_config(names=["normal"], seeds=5, policies=("flat",), max_days=None, incremental=False,
                     engine_policy_path=None, seed_start=1001)
    assert cfg["seed_start"] == 1001 and cfg["seeds"] == 5 and cfg["code_sha256"]


def test_delivery_cli_freezes_a_plan_and_reports_readiness(tmp_path, capsys):
    from src.cli.main import main as cli
    spec = json.loads((ROOT / "docs" / "field_test" / "plan.draft.json").read_text())
    spec.pop("status_note")
    spec["covariate_coefficients"] = {"ly_owner_net_per_night": 0.4}
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    with pytest.raises(SystemExit) as e:
        cli(["--db", str(tmp_path / "d.db"), "field-freeze", "--spec", str(tmp_path / "spec.json"),
             "--out", str(tmp_path / "plan.json")])
    assert e.value.code == 0
    reg_path, _ = _frozen_v3(tmp_path)
    with pytest.raises(SystemExit) as e:
        cli(["--db", str(tmp_path / "d.db"), "canary-readiness", "--ledger", str(tmp_path / "none.jsonl"),
             "--register", str(reg_path), "--plan", str(tmp_path / "plan.json"),
             "--signoff", str(tmp_path / "none.json")])
    assert e.value.code == 1 and "NOT READY" in capsys.readouterr().out
