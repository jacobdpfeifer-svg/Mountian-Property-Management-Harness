#!/usr/bin/env python3
"""Golden-board regression check for the market simulator.

Re-runs a small, fixed board and compares it with a committed golden
scoreboard. Revenue must match to the cent; content hashes and guardrail
counts must match exactly. This answers "did anything move?" in minutes,
which is all a reproduction-only full run ever proved.

    PYTHONPATH=. .venv/bin/python scripts/regress_market_sim.py            # default board
    PYTHONPATH=. .venv/bin/python scripts/regress_market_sim.py --board candidate
    PYTHONPATH=. .venv/bin/python scripts/regress_market_sim.py --update   # after an intended change

A score-only job now reports the same content hash and guardrail counts as a
retained one (a985b40), so the board runs without retained databases.

``--update`` rewrites the golden file. Use it only for an intended change, and
say in the commit which change moved the scores.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "config" / "market_sim" / "golden"

# name -> (golden file, extra CLI args)
BOARDS: dict[str, tuple[str, list[str]]] = {
    "default": ("normal_5seed_grid.csv", ["--grid", "--diagnostics"]),
    "candidate": (
        "normal_5seed_base_anchor.csv",
        ["--policy", "engine", "--engine-policy",
         "config/policies/candidates/seasonal_base_anchor_full_shoulder.yaml"],
    ),
}
COMPARED = ("revenue", "content_hash", "guardrail_triggers", "guardrail_by_action")


def _rows(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {(r["scenario"], r["seed"], r["policy"]): r for r in csv.DictReader(handle)}


def compare(golden: Path, fresh: Path) -> list[str]:
    """Human-readable differences; empty means the boards match."""
    want, got = _rows(golden), _rows(fresh)
    problems = [f"missing row {key}" for key in sorted(set(want) - set(got))]
    problems += [f"unexpected row {key}" for key in sorted(set(got) - set(want))]
    for key in sorted(set(want) & set(got)):
        for column in COMPARED:
            a, b = want[key].get(column), got[key].get(column)
            if column == "revenue" and a is not None and b is not None:
                if round(float(a), 2) != round(float(b), 2):
                    problems.append(f"{key} revenue {a} -> {b}")
            elif a != b:
                problems.append(f"{key} {column} {a} -> {b}")
    return problems


def run_board(name: str, seeds: int, workers: int, out_dir: Path) -> Path:
    _, extra = BOARDS[name]
    cmd = [
        sys.executable, "-m", "src.cli.main", "proving-ground", "market",
        "--scenario", "normal", "--seeds", str(seeds), "--workers", str(workers),
        "--output-dir", str(out_dir), *extra,
    ]
    subprocess.run(cmd, cwd=ROOT, check=True, env={**os.environ, "PYTHONPATH": str(ROOT)})
    return out_dir / "scoreboard.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--board", choices=sorted(BOARDS), default="default")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--workers", type=int, default=7)
    parser.add_argument(
        "--scoreboard", type=Path,
        help="Compare an existing scoreboard instead of running the board",
    )
    parser.add_argument("--update", action="store_true", help="Rewrite the golden file from this run")
    args = parser.parse_args()

    golden = GOLDEN_DIR / BOARDS[args.board][0]
    with tempfile.TemporaryDirectory(prefix="regress_market_") as tmp:
        fresh = args.scoreboard or run_board(args.board, args.seeds, args.workers, Path(tmp) / "board")
        if args.update:
            GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fresh, golden)
            print(f"golden updated: {golden.relative_to(ROOT)}")
            return 0
        if not golden.exists():
            print(f"no golden file at {golden}; run with --update first", file=sys.stderr)
            return 2
        problems = compare(golden, fresh)
    if problems:
        print(f"REGRESSION: {len(problems)} difference(s) vs {golden.relative_to(ROOT)}")
        for line in problems[:50]:
            print(f"  {line}")
        return 1
    print(f"OK: {len(_rows(golden))} rows match {golden.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
