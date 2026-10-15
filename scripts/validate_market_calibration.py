#!/usr/bin/env python3
"""Validate a simulator calibration against reality before trusting its scores.

"Calibrate before you score": a calibration earns engine scores only if, when the
homes are priced the way they really are priced today (``current_practice``),
the simulated market produces outcomes close to what really happens.

Targets:
- public bands in the calibration's ``validation`` block (lead share, LOS,
  inquiry ratio, peak and early occupancy);
- the homes' real booked ADR by season from the local, gitignored rate-card
  export (``data/exports/rate_card.yaml``), where at least ``--min-booked``
  real nights exist. Without the export these targets are NOT MEASURED.

    PYTHONPATH=. .venv/bin/python scripts/validate_market_calibration.py --calibration v2 --seeds 5

Exit 0 when every measured target passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proving_ground_exam.market.parameters import load_calibration, load_scenario  # noqa: E402
from proving_ground_exam.market.world import HOLIDAY_SPANS  # noqa: E402
from src.proving_ground.market_loop import resolve_calibration, run_market_job  # noqa: E402

RATE_CARD = ROOT / "data" / "exports" / "rate_card.yaml"


def _rate_season(night: date) -> str:
    """Same split as scripts/export_rate_card.py so the comparison is like for like."""
    md = (night.month, night.day)
    if md >= (12, 20) or md <= (1, 2):
        return "holiday"
    if night.month in (1, 2, 3):
        return "peak_ski"
    if night.month in (11, 12):
        return "early_winter"
    return "shoulder_spring"


def booked_adr_by_season(db: Path) -> dict[str, tuple[float, int]]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cells: dict[str, list[float]] = {}
        for stay, price in conn.execute(
            "SELECT stay_date, booked_price FROM nightly_inventory WHERE status='booked' AND booked_price > 0"
        ):
            cells.setdefault(_rate_season(date.fromisoformat(stay)), []).append(float(price))
    finally:
        conn.close()
    return {season: (statistics.fmean(v), len(v)) for season, v in cells.items()}


def validate(calibration: str, seeds: int, *, min_booked: int, tolerance: float) -> dict[str, Any]:
    path = resolve_calibration(calibration)
    cal = load_calibration(path)
    scenario = load_scenario("normal")
    rows: list[dict[str, Any]] = []
    adr: dict[str, list[tuple[float, int]]] = {}
    policy = "current_practice" if cal.get("current_practice") else "flat"
    with tempfile.TemporaryDirectory(prefix="validate_cal_") as tmp:
        for seed in range(1, seeds + 1):
            db = Path(tmp) / f"{seed}.db"
            result = run_market_job(
                "normal", seed, policy, db_path=db, calibration=cal, scenario_doc=scenario,
                trace_choices=False,
            )
            rows.append(result.scores)
            for season, cell in booked_adr_by_season(db).items():
                adr.setdefault(season, []).append(cell)

    checks: list[dict[str, Any]] = []
    for metric, band in (cal.get("validation") or {}).items():
        values = [float(r[metric]) for r in rows if metric in r]
        if not values:
            continue
        mean = statistics.fmean(values)
        checks.append({
            "target": metric, "simulated": round(mean, 4),
            "expected": f"{band['lo']}-{band['hi']}", "source": band.get("source"),
            "result": "PASS" if band["lo"] <= mean <= band["hi"] else "FAIL",
        })

    if RATE_CARD.exists():
        card = yaml.safe_load(RATE_CARD.read_text(encoding="utf-8")) or {}
        for season in ("early_winter", "holiday", "peak_ski", "shoulder_spring"):
            real_prices: list[float] = []
            real_n = 0
            for home in (card.get("homes") or {}).values():
                real = (home.get("by_season") or {}).get(season) or {}
                if real.get("booked_adr") and real.get("booked_nights"):
                    real_prices.append(float(real["booked_adr"]) * int(real["booked_nights"]))
                    real_n += int(real["booked_nights"])
            sim = adr.get(season) or []
            sim_n = sum(n for _, n in sim)
            if real_n < min_booked or not sim_n:
                checks.append({
                    "target": f"booked_adr_{season}", "result": "NOT MEASURED",
                    "note": f"real booked nights {real_n} (< {min_booked}) or none simulated",
                })
                continue
            real_adr = sum(real_prices) / real_n
            sim_adr = sum(a * n for a, n in sim) / sim_n
            off = sim_adr / real_adr - 1
            # The real ADR is confidential: report only the relative error.
            checks.append({
                "target": f"booked_adr_{season}", "simulated_vs_real": f"{off:+.1%}",
                "real_nights": real_n, "tolerance": f"±{tolerance:.0%}",
                "result": "PASS" if abs(off) <= tolerance else "FAIL",
            })
    else:
        checks.append({"target": "booked_adr_*", "result": "NOT MEASURED",
                       "note": f"no {RATE_CARD.relative_to(ROOT)} (run scripts/export_rate_card.py)"})

    measured = [c for c in checks if c["result"] != "NOT MEASURED"]
    return {
        "calibration": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "policy": policy,
        "seeds": seeds,
        "holiday_spans": [f"{a}..{b}" for a, b in HOLIDAY_SPANS],
        "checks": checks,
        "passed": bool(measured) and all(c["result"] == "PASS" for c in measured),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--calibration", default="v2")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--min-booked", type=int, default=10,
                        help="Real booked nights a season needs before its ADR is a target")
    parser.add_argument("--tolerance", type=float, default=0.25,
                        help="Allowed relative ADR error (default 25%%; real samples are small)")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = validate(args.calibration, args.seeds, min_booked=args.min_booked, tolerance=args.tolerance)
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for check in result["checks"]:
        detail = {k: v for k, v in check.items() if k not in ("target", "result", "source")}
        print(f"{check['result']:12s} {check['target']:28s} {detail}")
    print("CALIBRATION VALID" if result["passed"] else "CALIBRATION NOT VALID")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
