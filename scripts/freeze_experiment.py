#!/usr/bin/env python3
"""Freeze a new experiment register before any of its boards exist.

    freeze_experiment.py --spec SPEC.json --register OUT.json [--runs-root ~/wp-price-runs]

Refuses a dirty tracked tree (the frozen code must be a commit), any screen or
evaluation seed that an earlier scoreboard under --runs-root already ran, and a
spec without `code_paths`. Prints the seed ranges to pass to the market sim.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments import CODE_PATHS, RegisterError, exposed_seeds, freeze_register  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--register", type=Path, required=True)
    ap.add_argument("--runs-root", type=Path, default=Path.home() / "wp-price-runs")
    ap.add_argument("--allow-dirty", action="store_true", help="tests only")
    a = ap.parse_args(argv)
    spec = json.loads(a.spec.read_text())
    spec.setdefault("code_paths", list(CODE_PATHS))
    from proving_ground_exam.market.parameters import list_scenarios
    known = set(list_scenarios())
    unknown = sorted({s for part in ("screen", "evaluation") for s in spec[part]["scenarios"]} - known)
    if unknown:
        # EXP-PACE-V2-001 named four worlds that do not exist; its evaluation could not have run.
        print(f"freeze_experiment: unknown scenarios {unknown}; known: {sorted(known)}", file=sys.stderr)
        return 2
    if not a.allow_dirty:
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        if dirty:
            print("freeze_experiment: commit first; the frozen code must be a commit", file=sys.stderr)
            return 2
        spec["git_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                            capture_output=True, text=True).stdout.strip()
    try:
        body = freeze_register(spec, a.register, repo=ROOT, exposed=exposed_seeds(a.runs_root))
    except RegisterError as exc:
        print(f"freeze_experiment: {exc}", file=sys.stderr)
        return 2
    for part in ("screen", "evaluation"):
        seeds = sorted(body[part]["seeds"])
        contiguous = seeds == list(range(seeds[0], seeds[-1] + 1))
        print(f"{part}: --seed-start {seeds[0]} --seeds {len(seeds)}"
              + ("" if contiguous else "  (not contiguous: run each seed)"))
    print(f"frozen {body['experiment_id']} register_sha256={body['register_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
