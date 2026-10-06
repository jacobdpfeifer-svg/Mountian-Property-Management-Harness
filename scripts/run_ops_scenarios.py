"""Run the operations scenarios on the market sim and write a paired scoreboard.

SIMULATED. Usage (from the repo root, outside iCloud):

    PYTHONPATH=. .venv/bin/python scripts/run_ops_scenarios.py run --out ~/wp-price-runs/ops_audit/sim
    PYTHONPATH=. .venv/bin/python scripts/run_ops_scenarios.py summarize --out ~/wp-price-runs/ops_audit/sim \
        --report docs/reports/ops_compliance_audit_2026-10-05/simulation

`run` is resumable: finished jobs are read back from results.jsonl. Job databases
are deleted after each job.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

from src.proving_ground.ops_scenarios import (
    ARMS,
    OPS_SCENARIOS,
    WINDOW_DAYS,
    WORLDS,
    result_row,
    run_ops_job,
)

METRICS = ("revenue", "net_revenue", "turns", "turn_cost", "violations", "unserviceable",
           "arrivals_on_broken_nights", "false_restricted_nights", "closures",
           "escalations_raised", "escalations_needed", "min_stay_refusals")


def _job(args: tuple[str, str, int, str, str]) -> dict:
    world, scenario, seed, arm, out = args
    db = Path(out) / "dbs" / f"{world}_{scenario}_{seed}_{arm}.db"
    try:
        return result_row(run_ops_job(world, scenario, seed, arm, db))
    finally:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{db}{suffix}").unlink(missing_ok=True)


def _key(row: dict) -> tuple:
    return (row["world"], row["scenario"], int(row["seed"]), row["arm"])


def run(out: Path, seeds: int, workers: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    results = out / "results.jsonl"
    done = set()
    if results.exists():
        done = {_key(json.loads(line)) for line in results.read_text().splitlines() if line.strip()}
    jobs = [(w, s, seed, arm, str(out)) for w in WORLDS for s in OPS_SCENARIOS
            for seed in range(1, seeds + 1) for arm in ARMS
            if (w, s, seed, arm) not in done]
    config = {
        "worlds": WORLDS, "scenarios": OPS_SCENARIOS, "seeds": seeds, "arms": ARMS,
        "window_days": WINDOW_DAYS, "workers": workers,
        "git": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "started": datetime.now(timezone.utc).isoformat(), "pending_jobs": len(jobs),
        "label": "SIMULATED - shopper-market world; not realized revenue",
    }
    (out / "run_config.json").write_text(json.dumps(config, indent=2))
    print(f"{len(done)} done, {len(jobs)} to run", flush=True)
    # Cheap arms first so partial results are still paired.
    jobs.sort(key=lambda j: (j[2], j[3] == "stay"))
    with Pool(workers) as pool, results.open("a") as fh:
        for i, row in enumerate(pool.imap_unordered(_job, jobs), 1):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if i % 50 == 0:
                print(f"{i}/{len(jobs)}", flush=True)


def _ci(diffs: list[float]) -> tuple[float, float, float]:
    if not diffs:
        return (math.nan, math.nan, math.nan)
    mean = statistics.fmean(diffs)
    if len(diffs) < 2:
        return (mean, math.nan, math.nan)
    half = 1.96 * statistics.stdev(diffs) / math.sqrt(len(diffs))
    return (mean, mean - half, mean + half)


def summarize(out: Path, report: Path) -> None:
    rows = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines() if line.strip()]
    by = {_key(r): r for r in rows}
    report.mkdir(parents=True, exist_ok=True)
    with (report / "scoreboard.csv").open("w", newline="") as fh:
        fields = ["world", "scenario", "seed", "arm", "held_out", *METRICS, "ops_min_stay_nights"]
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(rows, key=_key):
            writer.writerow(r)
    lines = ["# Operations scenarios on the market sim (SIMULATED)", "",
             "Every number here comes from the shopper-market simulator with estimated ops",
             "profiles. None of it is realized revenue. Paired by world, scenario, and seed;",
             "intervals are 1.96 x SE of the paired difference, not family-wise adjusted.", ""]
    lines += ["## Contract and operations measures (sums over seeds)", "",
              "| world | scenario | arm | n | violations | unserviceable same-day turns | arrivals on broken nights | false-restricted nights | closures | escalations raised / needed |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for world in WORLDS:
        for scen in OPS_SCENARIOS:
            for arm in ARMS:
                rs = [r for k, r in by.items() if k[0] == world and k[1] == scen and k[3] == arm]
                if not rs:
                    continue
                s = lambda m: sum(int(r[m]) for r in rs)  # noqa: E731
                lines.append(f"| {world} | {scen} | {arm} | {len(rs)} | {s('violations')} | "
                             f"{s('unserviceable')} | {s('arrivals_on_broken_nights')} | "
                             f"{s('false_restricted_nights')} | {s('closures')} | "
                             f"{s('escalations_raised')} / {s('escalations_needed')} |")
    lines += ["", "## Revenue, paired differences (mean per season window, 95% interval)", "",
              "| world | scenario | comparison | n | gross revenue diff | net of turn cost diff | turns diff | shoppers refused by ops min-stay |",
              "|---|---|---|---:|---:|---:|---:|---:|"]
    for world in WORLDS:
        for scen in OPS_SCENARIOS:
            for a, b in (("on", "off"), ("stay", "off"), ("stay", "flat"), ("off", "flat")):
                pairs = [(by[(world, scen, seed, a)], by[(world, scen, seed, b)])
                         for (w, sc, seed, arm) in by if w == world and sc == scen and arm == a
                         and (world, scen, seed, b) in by]
                if not pairs:
                    continue
                g = _ci([x["revenue"] - y["revenue"] for x, y in pairs])
                n_ = _ci([x["net_revenue"] - y["net_revenue"] for x, y in pairs])
                t = statistics.fmean(x["turns"] - y["turns"] for x, y in pairs)
                refused = statistics.fmean(x["min_stay_refusals"] for x, _ in pairs)
                lines.append(f"| {world} | {scen} | {a} - {b} | {len(pairs)} | "
                             f"{g[0]:+,.0f} [{g[1]:+,.0f}, {g[2]:+,.0f}] | "
                             f"{n_[0]:+,.0f} [{n_[1]:+,.0f}, {n_[2]:+,.0f}] | {t:+.2f} | {refused:.1f} |")
    (report / "SCOREBOARD.md").write_text("\n".join(lines) + "\n")
    cfg = json.loads((out / "run_config.json").read_text())
    cfg["rows"] = len(rows)
    (report / "run_config.json").write_text(json.dumps(cfg, indent=2))
    print(f"wrote {report}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("run", "summarize"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--report", type=Path)
    p.add_argument("--seeds", type=int, default=30)
    p.add_argument("--workers", type=int, default=9)
    a = p.parse_args(argv)
    if "CloudDocs" in str(a.out.resolve()):
        print("refusing: keep simulation output outside iCloud Drive", file=sys.stderr)
        return 2
    if a.command == "run":
        run(a.out, a.seeds, a.workers)
    else:
        summarize(a.out, a.report or a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
