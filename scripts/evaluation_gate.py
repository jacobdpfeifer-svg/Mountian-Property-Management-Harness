#!/usr/bin/env python3
"""Grade a frozen experiment's held-out evaluation boards and record the verdict.

    evaluation_gate.py --register REG.json --ledger LEDGER.jsonl \
        --candidate-board DIR [DIR ...] --comparator-board DIR [DIR ...] [--candidate-policy engine]

Refuses unless the screen advanced and evaluation was opened (open_evaluation),
and unless every board was produced by the register's frozen code after the
freeze. Reads `manifest.json` rows (they carry owner_net_by_property). Runs no
simulation. The verdict is appended to the ledger once.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments import (  # noqa: E402
    RegisterError, _append, _entries, board_provenance_problem, evaluation_decision, load_register,
)


def _rows(boards: list[Path], policy: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in boards:
        out.extend(r for r in json.loads((b / "manifest.json").read_text())["rows"] if r["policy"] == policy)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--candidate-board", type=Path, nargs="+", required=True)
    ap.add_argument("--comparator-board", type=Path, nargs="+", required=True)
    ap.add_argument("--candidate-policy", default="engine")
    a = ap.parse_args(argv)
    try:
        reg = load_register(a.register)
    except RegisterError as exc:
        print(f"evaluation_gate: {exc}", file=sys.stderr)
        return 2
    entries = _entries(a.ledger, reg["experiment_id"])
    opened = [e for e in entries if e["type"] == "evaluation_opened"
              and e.get("register_sha256") == reg["register_sha256"]]
    if not opened:
        print("evaluation_gate: evaluation was never opened for this register", file=sys.stderr)
        return 2
    opened_at = datetime.fromisoformat(opened[0]["at"])
    if any(e["type"] == "evaluation_decision" for e in entries):
        print("evaluation_gate: this register already has an evaluation verdict", file=sys.stderr)
        return 2
    # Held-out boards must start after the screen passed and evaluation was opened.
    problem = (board_provenance_problem(reg, *a.candidate_board, candidate=True, not_before=opened_at)
               or board_provenance_problem(reg, *a.comparator_board, not_before=opened_at))
    if problem:
        print(f"evaluation_gate: {problem}", file=sys.stderr)
        return 2
    verdict = evaluation_decision(reg, _rows(a.candidate_board, a.candidate_policy),
                                  _rows(a.comparator_board, reg["comparator"]))
    if verdict["decision"] == "INCOMPLETE":
        print(json.dumps(verdict, indent=1))
        return 3
    _append(a.ledger, {"type": "evaluation_decision", "experiment_id": reg["experiment_id"],
                       "register_sha256": reg["register_sha256"], **verdict,
                       "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    print(json.dumps({k: verdict[k] for k in ("decision", "reasons")}, indent=1))
    return 0 if verdict["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
