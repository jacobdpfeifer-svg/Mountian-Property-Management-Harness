from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from proving_ground_exam.worlds.w1_calm import W1CalmWorld
from src.cli.main import main as cli_main
from src.proving_ground import run_level


def _short_world() -> W1CalmWorld:
    return W1CalmWorld(
        property_id="cabin_ridge",
        season_start=date(2026, 12, 1),
        season_end=date(2026, 12, 21),
    )


def test_proving_ground_same_seed_is_deterministic(tmp_path: Path):
    world = _short_world()
    first = run_level(
        1, seed=123, output_dir=tmp_path, world=world, decision_step_days=7,
        verify_determinism_gate=False,
    )
    second = run_level(
        1, seed=123, output_dir=tmp_path, world=world, decision_step_days=7,
        verify_determinism_gate=False,
    )

    assert first.content_hash == second.content_hash
    assert first.run_id == second.run_id
    assert first.manifest_path.read_text(encoding="utf-8") == second.manifest_path.read_text(
        encoding="utf-8"
    )


def test_proving_ground_writes_manifest_scoreboard_and_queue(tmp_path: Path):
    artifacts = run_level(
        2,
        seed=456,
        output_dir=tmp_path,
        world=_short_world(),
        decision_step_days=7,
        verify_determinism_gate=False,
    )

    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    assert manifest["level"] == 2
    assert manifest["hard_gate_counts"]["guesty_write_attempts"] == 0
    assert manifest["engine_path"] == "generate_recommendations"
    assert manifest["forward_shadow_protocol"]["tool"] == "src/eval/shadow.py"
    hard = {g["name"]: g for g in manifest["gates"] if g.get("measured_by", "").startswith("src.proving_ground.gates")}
    assert hard["guesty_write_attempts"]["passed"] is True
    assert hard["guardrail_violations"]["passed"] is True

    with artifacts.scoreboard_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {r["policy_id"] for r in rows} >= {
        "engine",
        "flat_seasonal",
        "comp_median_follower",
        "moat_off",
        "oracle",
    }
    assert "Fix Card PG-P0-001" in artifacts.approval_queue_path.read_text(encoding="utf-8")
    assert "What is still fake or stubbed" in artifacts.report_path.read_text(encoding="utf-8")


def test_proving_ground_rejects_unimplemented_levels(tmp_path: Path):
    with pytest.raises(ValueError, match="Phase 0 supports"):
        run_level(3, seed=1, output_dir=tmp_path)


@pytest.mark.slow  # runs the full default season (Nov 1–Apr 15) through the real engine; minutes, not seconds
def test_proving_ground_cli_run(tmp_path: Path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli_main([
            "proving-ground",
            "run",
            "--level",
            "1",
            "--seed",
            "789",
            "--output-dir",
            str(tmp_path),
        ])
    out = capsys.readouterr().out
    assert "Proving Ground L1:" in out
    assert "report:" in out
    run_dirs = sorted(tmp_path.iterdir())
    assert run_dirs
    manifest = json.loads((run_dirs[-1] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["engine_path"] == "generate_recommendations"
