#!/usr/bin/env python3
"""Record a frozen experiment's screen decision from its screen boards.

    screen_gate.py --register REG.json --ledger LEDGER.jsonl \
        --candidate-board DIR --comparator-board DIR [--candidate-policy engine]

Freeze first (scripts/freeze_experiment.py), then run the screen boards. This
reads only the register's screen seeds from each board's scoreboard.csv, pairs
them by (scenario, seed), refuses boards made with another calibration, other
code, or before the freeze, and appends the decision to the ledger. Runs no
simulation and never reads evaluation seeds.

`--spec` remains only for the 2026-10-15 post-hoc register (EXP-PACE-V2-001),
which was frozen from boards that already existed.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments import (  # noqa: E402
    LEGACY_REGISTERS, RegisterError, board_provenance_problem, freeze_register, load_register, record_screen, screen_decision,
)


def _board(path: Path, policy: str, seeds: set[int], scenarios: set[str]) -> dict[tuple[str, int], float]:
    out = {}
    for r in csv.DictReader(open(path / "scoreboard.csv")):
        if r["policy"] == policy and int(r["seed"]) in seeds and r["scenario"] in scenarios:
            out[(r["scenario"], int(r["seed"]))] = float(r["owner_net"])
    return out


def _run_config(path: Path) -> dict:
    cfg = json.loads((path / "run_config.json").read_text())
    return cfg.get("config") or cfg


def _calibration(path: Path) -> str:
    return _run_config(path)["calibration_sha256"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path)
    ap.add_argument("--register", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--candidate-board", type=Path, required=True)
    ap.add_argument("--comparator-board", type=Path, required=True)
    ap.add_argument("--candidate-policy", default="engine")
    a = ap.parse_args(argv)
    try:
        if a.register.exists():
            reg = load_register(a.register)
        elif a.spec is not None:
            spec = json.loads(a.spec.read_text())
            if spec.get("experiment_id") not in LEGACY_REGISTERS:
                # Freezing here would skip the exposure, dirty-tree and code-hash checks.
                raise RegisterError("--spec is only for the legacy post-hoc register; "
                                    "use scripts/freeze_experiment.py")
            reg = freeze_register(spec, a.register, repo=ROOT)
        else:
            raise RegisterError(f"{a.register} is not frozen; run scripts/freeze_experiment.py first")
    except RegisterError as exc:
        print(f"screen_gate: {exc}", file=sys.stderr)
        return 2
    problem = (board_provenance_problem(reg, a.candidate_board, candidate=True)
               or board_provenance_problem(reg, a.comparator_board))
    if problem:
        print(f"screen_gate: {problem}", file=sys.stderr)
        return 2
    if _calibration(a.candidate_board) != _calibration(a.comparator_board):
        print("screen_gate: boards used different calibrations; not a paired comparison", file=sys.stderr)
        return 2
    if _calibration(a.candidate_board) != reg["input_sha256"]["calibration"]:
        print("screen_gate: board calibration differs from the register's", file=sys.stderr)
        return 2
    seeds, scen = set(reg["screen"]["seeds"]), set(reg["screen"]["scenarios"])
    cand = _board(a.candidate_board, a.candidate_policy, seeds, scen)
    comp = _board(a.comparator_board, reg["comparator"], seeds, scen)
    keys = sorted(set(cand) & set(comp))
    if len(keys) != len(seeds) * len(scen):
        print(f"screen_gate: incomplete pairing {keys}", file=sys.stderr)
        return 2
    deltas = [round(cand[k] - comp[k], 2) for k in keys]
    if "material_harm_margin" in reg:
        margin = float(reg["material_harm_margin"])
    else:   # fraction of the comparator's mean owner net on the screen, fixed in the register
        margin = float(reg["harm_fraction"]) * sum(comp[k] for k in keys) / len(keys)
    decision, ci, why = screen_decision(deltas, margin=margin, reject_below=reg.get("reject_below"),
                                        require_gain=bool(reg.get("screen_requires_gain", False)))
    entry = record_screen(a.ledger, reg, decision, ci, why, {
        "pairs": [{"scenario": k[0], "seed": k[1], "candidate": cand[k], "comparator": comp[k],
                   "delta": d} for k, d in zip(keys, deltas)],
        "candidate_board": a.candidate_board.name, "comparator_board": a.comparator_board.name})
    print(json.dumps({k: entry[k] for k in ("decision", "interval", "rationale")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
