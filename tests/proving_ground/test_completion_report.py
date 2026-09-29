from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXIT_CRITERIA = {
    "engine_path": "tests/proving_ground/test_engine_runs.py",
    "sabotage": "tests/proving_ground/test_sabotage.py",
    "gates_measured": "tests/proving_ground/test_gates_measured.py",
    "world_hardness": "tests/proving_ground/test_world_hardness.py",
    "l2_vintages": "tests/proving_ground/test_l2_vintages.py",
    "evidence_labels": "tests/proving_ground/test_evidence_labels.py",
    "cli_run": "tests/test_proving_ground.py",
    "fix_card": "docs/proving_ground/proposals/FIX-P0-001.md",
    "evidence_pack": "docs/proving_ground/EVIDENCE_PACK.md",
}


def test_completion_report_files_exist():
    missing = [k for k, rel in EXIT_CRITERIA.items() if not (ROOT / rel).exists()]
    assert not missing, f"Missing exit criteria artifacts: {missing}"
