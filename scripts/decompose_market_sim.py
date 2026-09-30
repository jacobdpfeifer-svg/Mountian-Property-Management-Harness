#!/usr/bin/env python3
"""Decompose one policy's revenue gap against another from retained job databases.

Reads ``<run_dir>/dbs/<scenario>_<policy>_<seed>.db`` pairs written by
``proving-ground market --retain-dbs`` and reports, averaged per seed:

- revenue, booked nights, occupancy, and ADR by season, property, and lead
  bucket at booking;
- a night-by-night split of the gap into nights both policies sold (price
  effect), nights only one sold (volume effect), and nights neither sold;
- for the engine side: how often the final price sat at the ceiling or the
  floor, and the guardrail action on the day each night booked.

It never runs the market. Every number comes from the retained databases.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from proving_ground_exam.market.parameters import LEAD_BUCKETS, season_of


def _lead_bucket(lead: int) -> str:
    for lo, hi in LEAD_BUCKETS:
        if lo <= lead <= hi:
            return f"{lo}-{hi}"
    return f"{LEAD_BUCKETS[-1][1] + 1}+"


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_nights(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    conn = _connect(path)
    try:
        out = {}
        for row in conn.execute(
            """
            SELECT property_id, stay_date, status, listed_price, booked_price, booked_at
            FROM nightly_inventory
            """
        ):
            booked = row["status"] == "booked" and row["booked_price"] is not None
            stay = date.fromisoformat(row["stay_date"])
            lead = None
            if booked and row["booked_at"]:
                lead = (stay - date.fromisoformat(row["booked_at"][:10])).days
            out[(row["property_id"], row["stay_date"])] = {
                "booked": booked,
                "price": float(row["booked_price"]) if booked else None,
                "listed": float(row["listed_price"]) if row["listed_price"] is not None else None,
                "booked_at": row["booked_at"][:10] if booked and row["booked_at"] else None,
                "lead": lead,
                "season": season_of(stay),
            }
        return out
    finally:
        conn.close()


def load_engine_recs(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    """(run_id, property, stay_date) -> rec. run_id is ``sim-<decision day>``."""
    conn = _connect(path)
    try:
        return {
            (row["run_id"], row["property_id"], row["stay_date"]): dict(row)
            for row in conn.execute(
                """
                SELECT run_id, property_id, stay_date, final_price, ceiling_price,
                       floor_price, COALESCE(guardrail_action, '') AS guardrail_action
                FROM price_recommendations
                """
            )
        }
    finally:
        conn.close()


class Tally:
    def __init__(self) -> None:
        self.nights = 0
        self.booked = 0
        self.revenue = 0.0

    def add(self, night: dict[str, Any]) -> None:
        self.nights += 1
        if night["booked"]:
            self.booked += 1
            self.revenue += night["price"]

    def summary(self, seeds: int) -> dict[str, float]:
        return {
            "revenue": round(self.revenue / seeds, 2),
            "booked_nights": round(self.booked / seeds, 2),
            "occupancy": round(self.booked / self.nights, 4) if self.nights else 0.0,
            "adr": round(self.revenue / self.booked, 2) if self.booked else 0.0,
        }


def _at(value: float | None, target: float | None) -> bool:
    return value is not None and target is not None and abs(value - target) < 0.5


def decompose(run_dir: Path, scenario: str, left: str, right: str) -> dict[str, Any]:
    db_dir = run_dir / "dbs"
    seeds = sorted(
        int(path.stem.rsplit("_", 1)[1])
        for path in db_dir.glob(f"{scenario}_{left}_*.db")
        if (db_dir / f"{scenario}_{right}_{path.stem.rsplit('_', 1)[1]}.db").exists()
    )
    if not seeds:
        raise FileNotFoundError(
            f"no retained {scenario} {left}/{right} database pairs under {db_dir}"
        )
    dims = ("season", "property", "lead_bucket")
    tallies: dict[str, dict[str, dict[str, Tally]]] = {
        dim: defaultdict(lambda: {left: Tally(), right: Tally()}) for dim in dims
    }
    totals = {left: Tally(), right: Tally()}
    split = defaultdict(lambda: {"nights": 0, "revenue_left": 0.0, "revenue_right": 0.0})
    split_by_season: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    rec_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    guard_at_booking: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    engine_side = left if left == "engine" else right if right == "engine" else None

    for seed in seeds:
        nights = {
            left: load_nights(db_dir / f"{scenario}_{left}_{seed}.db"),
            right: load_nights(db_dir / f"{scenario}_{right}_{seed}.db"),
        }
        recs = (
            load_engine_recs(db_dir / f"{scenario}_engine_{seed}.db") if engine_side else {}
        )
        for key in sorted(nights[left]):
            a, b = nights[left][key], nights[right].get(key)
            if b is None:
                continue
            for policy, night in ((left, a), (right, b)):
                totals[policy].add(night)
                tallies["season"][night["season"]][policy].add(night)
                tallies["property"][key[0]][policy].add(night)
                bucket = _lead_bucket(night["lead"]) if night["lead"] is not None else "unsold"
                tallies["lead_bucket"][bucket][policy].add(night)
            kind = (
                "both_sold" if a["booked"] and b["booked"]
                else f"only_{left}_sold" if a["booked"]
                else f"only_{right}_sold" if b["booked"]
                else "neither_sold"
            )
            cell = split[kind]
            cell["nights"] += 1
            cell["revenue_left"] += a["price"] or 0.0
            cell["revenue_right"] += b["price"] or 0.0
            split_by_season[a["season"]][kind] += (a["price"] or 0.0) - (b["price"] or 0.0)
        for (run_id, prop, stay), rec in recs.items():
            season = season_of(date.fromisoformat(stay))
            stats = rec_stats[season]
            stats["recs"] += 1
            stats["at_ceiling"] += _at(rec["final_price"], rec["ceiling_price"])
            stats["at_floor"] += _at(rec["final_price"], rec["floor_price"])
            stats[f"guardrail:{rec['guardrail_action'] or 'none'}"] += 1
        if engine_side:
            for key, night in nights[engine_side].items():
                if not night["booked"] or not night["booked_at"]:
                    continue
                rec = recs.get((f"sim-{night['booked_at']}", key[0], key[1]))
                action = (rec["guardrail_action"] or "none") if rec else "no_rec_that_day"
                cell = guard_at_booking[action]
                cell["nights"] += 1
                cell["revenue"] += night["price"]
                cell["at_ceiling"] += bool(rec and _at(rec["final_price"], rec["ceiling_price"]))

    n = len(seeds)
    by_dim = {}
    for dim, groups in tallies.items():
        by_dim[dim] = {}
        for name in sorted(groups):
            l, r = groups[name][left].summary(n), groups[name][right].summary(n)
            by_dim[dim][name] = {
                left: l,
                right: r,
                "revenue_delta": round(l["revenue"] - r["revenue"], 2),
            }
    return {
        "run_dir": str(run_dir),
        "scenario": scenario,
        "left": left,
        "right": right,
        "seeds": seeds,
        "totals": {
            left: totals[left].summary(n),
            right: totals[right].summary(n),
            "revenue_delta": round(totals[left].revenue / n - totals[right].revenue / n, 2),
        },
        "night_split": {
            kind: {
                "nights": round(cell["nights"] / n, 2),
                f"revenue_{left}": round(cell["revenue_left"] / n, 2),
                f"revenue_{right}": round(cell["revenue_right"] / n, 2),
                "revenue_delta": round((cell["revenue_left"] - cell["revenue_right"]) / n, 2),
            }
            for kind, cell in sorted(split.items())
        },
        "night_split_delta_by_season": {
            season: {kind: round(value / n, 2) for kind, value in sorted(kinds.items())}
            for season, kinds in sorted(split_by_season.items())
        },
        "by": by_dim,
        "engine_recommendations_by_season": {
            season: {
                "recs": stats["recs"],
                "share_at_ceiling": round(stats["at_ceiling"] / stats["recs"], 4),
                "share_at_floor": round(stats["at_floor"] / stats["recs"], 4),
                "guardrail": {
                    key.split(":", 1)[1]: value
                    for key, value in sorted(stats.items()) if key.startswith("guardrail:")
                },
            }
            for season, stats in sorted(rec_stats.items()) if stats["recs"]
        },
        "engine_guardrail_on_booking_day": {
            action: {
                "nights": round(cell["nights"] / n, 2),
                "revenue": round(cell["revenue"] / n, 2),
                "share_at_ceiling": round(cell["at_ceiling"] / cell["nights"], 4),
            }
            for action, cell in sorted(guard_at_booking.items())
        },
        "scoreboard_check": _scoreboard_check(run_dir, scenario, (left, right), seeds, totals, n),
    }


def _scoreboard_check(
    run_dir: Path,
    scenario: str,
    policies: tuple[str, str],
    seeds: list[int],
    totals: dict[str, Tally],
    n: int,
) -> dict[str, Any]:
    """Booked-night revenue should reconcile with the scoreboard's revenue column."""
    path = run_dir / "scoreboard.csv"
    if not path.exists():
        return {"status": "no scoreboard.csv"}
    wanted = {str(seed) for seed in seeds}
    board: dict[str, list[float]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["scenario"] == scenario and row["seed"] in wanted and row["policy"] in policies:
                board[row["policy"]].append(float(row["revenue"]))
    out = {}
    for policy in policies:
        if len(board[policy]) != n:
            out[policy] = {"status": f"scoreboard has {len(board[policy])} of {n} seeds"}
            continue
        mean_board = sum(board[policy]) / n
        mean_db = totals[policy].revenue / n
        out[policy] = {
            "scoreboard_mean": round(mean_board, 2),
            "database_mean": round(mean_db, 2),
            "difference": round(mean_db - mean_board, 2),
        }
    return out


def to_markdown(result: dict[str, Any]) -> str:
    left, right = result["left"], result["right"]
    lines = [
        f"# {left} vs {right} decomposition — {result['scenario']}",
        "",
        f"Seeds: {len(result['seeds'])} ({result['seeds'][0]}–{result['seeds'][-1]}). "
        "All figures are per-seed means from retained job databases (simulated, not realized, revenue).",
        "",
        f"Total revenue delta ({left} − {right}): **{result['totals']['revenue_delta']:,.0f}**",
        "",
        "## Night split",
        "",
        f"| outcome | nights | {left} rev | {right} rev | delta |",
        "|---|---:|---:|---:|---:|",
    ]
    for kind, cell in result["night_split"].items():
        lines.append(
            f"| {kind} | {cell['nights']:.1f} | {cell[f'revenue_{left}']:,.0f} | "
            f"{cell[f'revenue_{right}']:,.0f} | {cell['revenue_delta']:,.0f} |"
        )
    for dim, groups in result["by"].items():
        # Every night in a lead bucket is booked, so occupancy there is always 1;
        # booked nights is the useful volume column.
        volume, label = ("booked_nights", "nights") if dim == "lead_bucket" else ("occupancy", "occ")
        lines += [
            "",
            f"## By {dim.replace('_', ' ')}",
            "",
            f"| {dim} | {left} rev | {right} rev | delta | {left} {label} | {right} {label} | "
            f"{left} ADR | {right} ADR |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for name, cell in groups.items():
            a, b = cell[left], cell[right]
            lines.append(
                f"| {name} | {a['revenue']:,.0f} | {b['revenue']:,.0f} | {cell['revenue_delta']:,.0f} | "
                f"{a[volume]:.3f} | {b[volume]:.3f} | {a['adr']:,.0f} | {b['adr']:,.0f} |"
            )
    if result["engine_recommendations_by_season"]:
        lines += [
            "",
            "## Engine recommendations by season",
            "",
            "| season | recs | at ceiling | at floor | guardrail actions |",
            "|---|---:|---:|---:|---|",
        ]
        for season, stats in result["engine_recommendations_by_season"].items():
            actions = ", ".join(f"{k}={v}" for k, v in stats["guardrail"].items())
            lines.append(
                f"| {season} | {stats['recs']} | {stats['share_at_ceiling']:.1%} | "
                f"{stats['share_at_floor']:.1%} | {actions} |"
            )
        lines += [
            "",
            "## Engine guardrail on the day each night booked",
            "",
            "| action | nights | revenue | at ceiling |",
            "|---|---:|---:|---:|",
        ]
        for action, cell in result["engine_guardrail_on_booking_day"].items():
            lines.append(
                f"| {action} | {cell['nights']:.1f} | {cell['revenue']:,.0f} | "
                f"{cell['share_at_ceiling']:.1%} |"
            )
    lines += ["", "## Scoreboard reconciliation", "", "```", json.dumps(result["scoreboard_check"], indent=2), "```", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="Market run output dir containing dbs/")
    parser.add_argument("--scenario", default="normal")
    parser.add_argument("--left", default="engine")
    parser.add_argument("--right", default="flat")
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--md", dest="md_path", type=Path)
    args = parser.parse_args()
    result = decompose(args.run_dir.expanduser(), args.scenario, args.left, args.right)
    if args.json_path:
        args.json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    markdown = to_markdown(result)
    if args.md_path:
        args.md_path.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
