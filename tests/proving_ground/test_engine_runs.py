"""Proving Ground acceptance: real engine path."""

from __future__ import annotations

import importlib
import pkgutil
from datetime import date
from pathlib import Path

import pytest

from proving_ground_exam.worlds.w1_calm import W1CalmWorld
from src.proving_ground import run_level
from src.proving_ground.runner import ENGINE_PATH_ACTIVE


def _test_world() -> W1CalmWorld:
    return W1CalmWorld(
        property_id="cabin_ridge",
        season_start=date(2026, 12, 1),
        season_end=date(2026, 12, 21),
    )


def test_engine_path_is_active():
    assert ENGINE_PATH_ACTIVE is True


def test_proving_ground_uses_real_engine_prices(tmp_path: Path):
    artifacts = run_level(
        1,
        seed=42,
        output_dir=tmp_path,
        world=_test_world(),
        decision_step_days=7,
        verify_determinism_gate=False,
    )
    manifest = artifacts.manifest_path.read_text(encoding="utf-8")
    assert '"engine_path": "generate_recommendations"' in manifest
    assert "oracle_price * 0.998" not in manifest
    assert manifest.count('"policy_id": "engine"') >= 1


def test_exam_worlds_do_not_import_engine_modules():
    import proving_ground_exam.worlds as worlds_pkg

    forbidden = ("bookprob", "compose", "conditions", "elasticity")
    for modinfo in pkgutil.walk_packages(worlds_pkg.__path__, worlds_pkg.__name__ + "."):
        mod = importlib.import_module(modinfo.name)
        source_path = Path(mod.__file__ or "")
        if not source_path.exists():
            continue
        text = source_path.read_text(encoding="utf-8")
        for name in forbidden:
            assert f"src.{name}" not in text, f"{modinfo.name} imports forbidden src.{name}"


def test_world_hardness_flat_beats_oracle_by_five_points(tmp_path: Path):
    artifacts = run_level(
        1,
        seed=99,
        output_dir=tmp_path,
        world=_test_world(),
        decision_step_days=7,
        verify_determinism_gate=False,
    )
    import json

    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    gates = {g["name"]: g for g in manifest["gates"]}
    hardness = gates.get("world_hardness_flat_vs_oracle")
    assert hardness is not None
    assert hardness["passed"] is True
