#!/usr/bin/env python3
"""Paired default vs candidate scoreboard stats for market-sim confirmation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from proving_ground_exam.market.stats import bootstrap_mean_ci


METRICS = (
    "revenue",
    "revpan",
    "occupancy",
    "adr",
    "occupancy_peak",
)


def _load_engine_rows(path: Path) -> dict[int, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    out: dict[int, dict[str, str]] = {}
    for row in rows:
        if row["policy"] != "engine":
            continue
        out[int(row["seed"])] = row
    return out


def _f(row: dict[str, str], key: str) -> float:
    return float(row[key])


def _summary(values: list[float], scenario: str) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    ci = bootstrap_mean_ci(values, scenario=scenario, seed=0)
    arr = np.asarray(values, dtype=float)
    return {
        "n": len(values),
        "mean": round(float(arr.mean()), 4),
        "median": round(float(np.median(arr)), 4),
        "stdev": round(float(arr.std(ddof=1)), 4) if len(values) > 1 else 0.0,
        "min": round(float(arr.min()), 4),
        "max": round(float(arr.max()), 4),
        "nonnegative": sum(v >= 0 for v in values),
        "bootstrap_95": {"lo": round(float(ci["lo"]), 4), "hi": round(float(ci["hi"]), 4)},
    }


def paired_report(
    combined_csv: Path,
    default_csv: Path,
    *,
    seeds_from: int,
    seeds_to: int | None,
) -> dict[str, Any]:
    combined = _load_engine_rows(combined_csv)
    default = _load_engine_rows(default_csv)
    seeds = sorted(set(combined) & set(default))
    if seeds_to is not None:
        seeds = [s for s in seeds if seeds_from <= s <= seeds_to]
    else:
        seeds = [s for s in seeds if s >= seeds_from]
    scenario = combined[seeds[0]]["scenario"] if seeds else "unknown"

    deltas: dict[str, list[float]] = {m: [] for m in METRICS}
    guardrail_delta: list[float] = []
    for seed in seeds:
        c, d = combined[seed], default[seed]
        for m in METRICS:
            deltas[m].append(_f(c, m) - _f(d, m))
        guardrail_delta.append(_f(c, "guardrail_triggers") - _f(d, "guardrail_triggers"))

    result: dict[str, Any] = {
        "scenario": scenario,
        "seeds_from": seeds_from,
        "seeds_to": seeds_to,
        "seed_count": len(seeds),
        "combined_minus_default": {m: _summary(deltas[m], scenario) for m in METRICS},
        "guardrail_triggers_delta": _summary(guardrail_delta, scenario),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("combined_scoreboard", type=Path)
    parser.add_argument("default_scoreboard", type=Path)
    parser.add_argument("--seeds-from", type=int, default=6)
    parser.add_argument("--seeds-to", type=int, default=None)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    result = paired_report(
        args.combined_scoreboard,
        args.default_scoreboard,
        seeds_from=args.seeds_from,
        seeds_to=args.seeds_to,
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_path:
        args.json_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
