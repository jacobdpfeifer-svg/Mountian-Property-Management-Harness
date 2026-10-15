#!/usr/bin/env python3
"""Paired default vs candidate scoreboard stats for market-sim confirmation.

Each scoreboard row is one (seed, policy) job. Rows are paired by seed. By
default both sides are the ``engine`` rows; ``--left-policy`` and
``--right-policy`` pair other policies, for example a candidate engine board
against the ``flat`` rows of a benchmark board.

Guardrails are reported per action. The scoreboard stores the no-guardrail
rows under the empty key; they are shown as ``none`` and are not triggers.
Counts depend on how many nights stay open (each open night is re-priced
daily), so rates per 1,000 recommendations are reported too.
"""

from __future__ import annotations

import argparse
import ast
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


NO_GUARDRAIL = "none"


def _load_rows(
    path: Path, policy: str = "engine", scenario: str | None = None
) -> dict[int, dict[str, str]]:
    """Rows of one policy keyed by seed. A board holding several scenarios
    needs ``scenario``; keying by seed alone would let one scenario's row
    silently overwrite another's."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [
            row for row in csv.DictReader(handle)
            if row["policy"] == policy and (scenario is None or row["scenario"] == scenario)
        ]
    scenarios = {row["scenario"] for row in rows}
    if len(scenarios) > 1:
        raise ValueError(
            f"{path} holds {policy} rows for {len(scenarios)} scenarios "
            f"({', '.join(sorted(scenarios))}); pass --scenario"
        )
    out: dict[int, dict[str, str]] = {}
    for row in rows:
        seed = int(row["seed"])
        if seed in out:
            raise ValueError(f"{path} has two {policy} rows for seed {seed}")
        out[seed] = row
    return out


def _load_engine_rows(path: Path) -> dict[int, dict[str, str]]:
    return _load_rows(path, "engine")


def guardrails_by_action(row: dict[str, str]) -> dict[str, int]:
    """Parse ``guardrail_by_action`` (a dict repr or JSON); rename '' to ``none``."""
    raw = (row.get("guardrail_by_action") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(raw)
    return {(key or NO_GUARDRAIL): int(value) for key, value in parsed.items()}


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
        # Kept for old readers. For a metric where lower is better (guardrail
        # counts), read seeds_left_higher / seeds_left_lower instead.
        "nonnegative": sum(v >= 0 for v in values),
        "seeds_left_higher": sum(v > 0 for v in values),
        "seeds_left_lower": sum(v < 0 for v in values),
        "bootstrap_95": {"lo": round(float(ci["lo"]), 4), "hi": round(float(ci["hi"]), 4)},
    }


def paired_report(
    combined_csv: Path,
    default_csv: Path,
    *,
    seeds_from: int,
    seeds_to: int | None,
    left_policy: str = "engine",
    right_policy: str = "engine",
    scenario: str | None = None,
) -> dict[str, Any]:
    combined = _load_rows(combined_csv, left_policy, scenario)
    default = _load_rows(default_csv, right_policy, scenario)
    seeds = sorted(set(combined) & set(default))
    if seeds_to is not None:
        seeds = [s for s in seeds if seeds_from <= s <= seeds_to]
    else:
        seeds = [s for s in seeds if s >= seeds_from]
    scenario = combined[seeds[0]]["scenario"] if seeds else "unknown"

    deltas: dict[str, list[float]] = {m: [] for m in METRICS}
    guardrail_delta: list[float] = []
    by_action: dict[str, list[float]] = {}
    rates: dict[str, dict[str, list[float]]] = {}
    totals: dict[str, dict[str, int]] = {"left": {}, "right": {}}
    has_guardrails = left_policy == "engine" and right_policy == "engine"
    for seed in seeds:
        c, d = combined[seed], default[seed]
        for m in METRICS:
            deltas[m].append(_f(c, m) - _f(d, m))
        if not has_guardrails:
            continue
        guardrail_delta.append(_f(c, "guardrail_triggers") - _f(d, "guardrail_triggers"))
        gc, gd = guardrails_by_action(c), guardrails_by_action(d)
        recs_c, recs_d = sum(gc.values()), sum(gd.values())
        for action in sorted(set(gc) | set(gd)):
            by_action.setdefault(action, []).append(gc.get(action, 0) - gd.get(action, 0))
            totals["left"][action] = totals["left"].get(action, 0) + gc.get(action, 0)
            totals["right"][action] = totals["right"].get(action, 0) + gd.get(action, 0)
            if recs_c and recs_d:
                cell = rates.setdefault(action, {"left": [], "right": []})
                cell["left"].append(1000 * gc.get(action, 0) / recs_c)
                cell["right"].append(1000 * gd.get(action, 0) / recs_d)
    # An action absent from a seed's dict counted 0 there; pad so every list has n entries.
    for action, values in by_action.items():
        values.extend([0.0] * (len(guardrail_delta) - len(values)))

    result: dict[str, Any] = {
        "scenario": scenario,
        "seeds_from": seeds_from,
        "seeds_to": seeds_to,
        "seed_count": len(seeds),
        "left_policy": left_policy,
        "right_policy": right_policy,
        "combined_minus_default": {m: _summary(deltas[m], scenario) for m in METRICS},
    }
    if has_guardrails:
        result["guardrail_triggers_delta"] = _summary(guardrail_delta, scenario)
        result["guardrail_by_action_delta"] = {
            action: _summary(values, scenario) for action, values in sorted(by_action.items())
        }
        result["guardrail_by_action_totals"] = totals
        result["guardrail_rate_per_1000_recs"] = {
            action: {
                "left_mean": round(float(np.mean(cell["left"])), 3),
                "right_mean": round(float(np.mean(cell["right"])), 3),
                "delta_mean": round(float(np.mean(cell["left"]) - np.mean(cell["right"])), 3),
            }
            for action, cell in sorted(rates.items())
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("combined_scoreboard", type=Path)
    parser.add_argument("default_scoreboard", type=Path)
    parser.add_argument("--seeds-from", type=int, default=6)
    parser.add_argument("--seeds-to", type=int, default=None)
    parser.add_argument("--scenario", default=None, help="Required when a board holds several scenarios")
    parser.add_argument("--left-policy", default="engine", help="Policy rows to read from the first board")
    parser.add_argument("--right-policy", default="engine", help="Policy rows to read from the second board")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    result = paired_report(
        args.combined_scoreboard,
        args.default_scoreboard,
        seeds_from=args.seeds_from,
        seeds_to=args.seeds_to,
        left_policy=args.left_policy,
        right_policy=args.right_policy,
        scenario=args.scenario,
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.json_path:
        args.json_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
