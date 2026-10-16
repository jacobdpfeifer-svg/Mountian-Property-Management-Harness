#!/usr/bin/env python3
"""Freeze an experiment register and record its screen decision from existing boards.

    screen_gate.py --spec SPEC.json --register OUT.json --ledger LEDGER.jsonl \
        --candidate-board DIR --comparator-board DIR [--candidate-policy engine]

Reads only the screen seeds named in the spec from each board's scoreboard.csv,
pairs them by (scenario, seed), refuses mismatched calibration, and appends the
decision to the ledger. Runs no simulation and never reads evaluation seeds.
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
    RegisterError, freeze_register, load_register, record_screen, screen_decision,
)


def _board(path: Path, policy: str, seeds: set[int], scenarios: set[str]) -> dict[tuple[str, int], float]:
    out = {}
    for r in csv.DictReader(open(path / "scoreboard.csv")):
        if r["policy"] == policy and int(r["seed"]) in seeds and r["scenario"] in scenarios:
            out[(r["scenario"], int(r["seed"]))] = float(r["owner_net"])
    return out


def _calibration(path: Path) -> str:
    cfg = json.loads((path / "run_config.json").read_text())
    return (cfg.get("config") or cfg)["calibration_sha256"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--register", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--candidate-board", type=Path, required=True)
    ap.add_argument("--comparator-board", type=Path, required=True)
    ap.add_argument("--candidate-policy", default="engine")
    a = ap.parse_args(argv)
    spec = json.loads(a.spec.read_text())
    try:
        reg = load_register(a.register) if a.register.exists() else freeze_register(spec, a.register, repo=ROOT)
    except RegisterError as exc:
        print(f"screen_gate: {exc}", file=sys.stderr)
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
    decision, ci, why = screen_decision(deltas, margin=float(reg["material_harm_margin"]),
                                        reject_below=reg.get("reject_below"))
    entry = record_screen(a.ledger, reg, decision, ci, why, {
        "pairs": [{"scenario": k[0], "seed": k[1], "candidate": cand[k], "comparator": comp[k],
                   "delta": d} for k, d in zip(keys, deltas)],
        "candidate_board": a.candidate_board.name, "comparator_board": a.comparator_board.name})
    print(json.dumps({k: entry[k] for k in ("decision", "interval", "rationale")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
