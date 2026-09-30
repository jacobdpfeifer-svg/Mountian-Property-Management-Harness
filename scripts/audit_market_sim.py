#!/usr/bin/env python3
"""Audit a completed market-simulator scoreboard.

This is intentionally separate from the simulator runner.  It consumes an
already-completed CSV and refuses to call the market.  The corrected full-grid
run can therefore be audited without silently mixing it with the historical
pre-correction board.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from proving_ground_exam.market.stats import bootstrap_mean_ci


REQUIRED_POLICIES = {"engine", "flat", "comp_median", "tool"}


def _f(row: dict[str, str], key: str) -> float:
    return float(row[key])


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty scoreboard: {path}")
    required = {"scenario", "seed", "policy", "revenue", "held_out"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"scoreboard missing columns: {sorted(missing)}")
    return rows


def _provenance(scoreboard: Path) -> dict[str, Any] | None:
    manifest = scoreboard.parent / "manifest.json"
    if not manifest.exists():
        return None
    return json.loads(manifest.read_text(encoding="utf-8")).get("provenance")


# A candidate run and its reference must share the shopper world exactly.
_WORLD_KEYS = ("calibration_sha256", "scenarios_sha256", "max_days")


def merge_reference(
    rows: list[dict[str, str]],
    reference: list[dict[str, str]],
    *,
    provenance: dict[str, Any] | None,
    reference_provenance: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Fill policies the candidate run lacks from a baseline run on the same seeds.

    The baseline's own engine rows come along as ``baseline_engine`` so the
    candidate can be paired against the engine it is meant to replace.
    """
    if provenance and reference_provenance:
        mine, theirs = provenance["config"], reference_provenance["config"]
        drift = [key for key in _WORLD_KEYS if mine.get(key) != theirs.get(key)]
        if drift:
            raise ValueError(f"reference run is a different world: {drift}")
    else:
        raise ValueError("both runs need manifest provenance to be merged")
    present = {row["policy"] for row in rows}
    keys = {(row["scenario"], row["seed"]) for row in rows}
    merged = list(rows)
    for row in reference:
        if (row["scenario"], row["seed"]) not in keys:
            continue
        if row["policy"] == "engine":
            merged.append({**row, "policy": "baseline_engine"})
        elif row["policy"] not in present:
            merged.append(row)
    return merged


def paired(rows: list[dict[str, str]], left: str, right: str) -> dict[str, list[float]]:
    by_key: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for row in rows:
        by_key[(row["scenario"], row["seed"])][row["policy"]] = _f(row, "revenue")
    out: dict[str, list[float]] = defaultdict(list)
    for (scenario, _seed), values in sorted(by_key.items()):
        if left in values and right in values:
            out[scenario].append(values[left] - values[right])
    return dict(out)


def _summary(values: list[float], scenario: str) -> dict[str, Any]:
    ci = bootstrap_mean_ci(values, scenario=scenario, seed=0)
    return {
        "n": len(values),
        "mean": round(float(np.mean(values)), 2),
        "median": round(float(np.median(values)), 2),
        "min": round(float(np.min(values)), 2),
        "max": round(float(np.max(values)), 2),
        "nonnegative": sum(value >= 0 for value in values),
        "bootstrap_95": {k: round(float(v), 2) for k, v in ci.items() if k in {"lo", "hi"}},
    }


def completeness(
    rows: list[dict[str, str]],
    expect_seeds: int | None,
    expect_scenarios: int | None,
    seeds_from: int = 1,
) -> dict[str, Any]:
    seen: dict[tuple[str, str, int], int] = defaultdict(int)
    for row in rows:
        if row["policy"] not in REQUIRED_POLICIES:
            continue
        seen[(row["scenario"], row["policy"], int(row["seed"]))] += 1
    scenarios = sorted({key[0] for key in seen})
    seeds = expect_seeds or max(key[2] for key in seen)
    missing = [
        f"{scenario}/{policy}/{seed}"
        for scenario in scenarios
        for policy in sorted(REQUIRED_POLICIES)
        for seed in range(seeds_from, seeds + 1)
        if (scenario, policy, seed) not in seen
    ]
    duplicates = [f"{s}/{p}/{n}" for (s, p, n), count in sorted(seen.items()) if count > 1]
    expected_rows = (
        (expect_scenarios or len(scenarios)) * len(REQUIRED_POLICIES) * (seeds - seeds_from + 1)
    )
    return {
        "expected_rows": expected_rows,
        "missing": missing[:50],
        "missing_count": len(missing),
        "duplicates": duplicates[:50],
        "scenario_count_ok": expect_scenarios is None or len(scenarios) == expect_scenarios,
        "complete": not missing and not duplicates and sum(seen.values()) == expected_rows,
    }


def audit(
    rows: list[dict[str, str]],
    *,
    expect_seeds: int | None = None,
    expect_scenarios: int | None = None,
    seeds_from: int = 1,
) -> dict[str, Any]:
    rows = [row for row in rows if int(row["seed"]) >= seeds_from]
    policies = {row["policy"] for row in rows}
    missing = REQUIRED_POLICIES - policies
    if missing:
        raise ValueError(f"scoreboard missing policies: {sorted(missing)}")

    engine_flat = paired(rows, "engine", "flat")
    engine_comp = paired(rows, "engine", "comp_median")
    engine_tool = paired(rows, "engine", "tool")
    scenarios = sorted(engine_flat)
    result: dict[str, Any] = {
        "row_count": len(rows),
        "policies": sorted(policies),
        "scenario_count": len(scenarios),
        "seeds_from": seeds_from,
        "completeness": completeness(rows, expect_seeds, expect_scenarios, seeds_from),
        "engine_minus_flat": {name: _summary(engine_flat[name], name) for name in scenarios},
        "engine_minus_comp_median": {
            name: _summary(engine_comp[name], name) for name in sorted(engine_comp)
        },
        "engine_minus_tool": {
            name: _summary(engine_tool[name], name) for name in sorted(engine_tool)
        },
        "gates": {},
    }
    engine_base = paired(rows, "engine", "baseline_engine")
    if engine_base:
        result["engine_minus_baseline_engine"] = {
            name: _summary(engine_base[name], name) for name in sorted(engine_base)
        }
        result["gates"]["scenarios_beating_baseline_engine"] = sum(
            1 for summary in result["engine_minus_baseline_engine"].values()
            if summary["mean"] >= 0
        )
    result["gates"]["complete"] = result["completeness"]["complete"]
    normal = result["engine_minus_flat"].get("normal")
    result["gates"]["normal_beats_flat"] = bool(normal and normal["mean"] >= 0)
    result["gates"]["normal_ci_excludes_loss"] = bool(
        normal and normal["bootstrap_95"]["lo"] > 0
    )
    result["gates"]["scenarios_beating_flat"] = sum(
        1 for summary in result["engine_minus_flat"].values() if summary["mean"] >= 0
    )
    held_out = {
        row["scenario"]
        for row in rows
        if row["held_out"].lower() in {"true", "1", "yes"}
    }
    result["gates"]["held_out_scenarios_present"] = bool(held_out) and held_out <= set(scenarios)
    result["held_out_scenarios"] = sorted(held_out)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scoreboard", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--expect-seeds", type=int, default=None)
    parser.add_argument("--expect-scenarios", type=int, default=None)
    parser.add_argument(
        "--seeds-from",
        type=int,
        default=1,
        help="Score only seeds >= this, e.g. 6 to exclude seeds 1-5 used to screen a candidate",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        help="Baseline scoreboard.csv supplying flat/comp_median/tool (and baseline_engine) "
        "rows for a candidate run that only ran the engine",
    )
    args = parser.parse_args()
    rows = load_rows(args.scoreboard)
    provenance = _provenance(args.scoreboard)
    if args.reference:
        rows = merge_reference(
            rows,
            load_rows(args.reference),
            provenance=provenance,
            reference_provenance=_provenance(args.reference),
        )
    result = audit(
        rows,
        expect_seeds=args.expect_seeds,
        expect_scenarios=args.expect_scenarios,
        seeds_from=args.seeds_from,
    )
    result["provenance"] = provenance
    if args.reference:
        result["reference"] = str(args.reference)
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_path:
        args.json_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["gates"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
