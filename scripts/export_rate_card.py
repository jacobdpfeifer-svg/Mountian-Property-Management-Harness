#!/usr/bin/env python3
"""Export the homes' real rate card and booking outcomes as aggregates.

The simulator, the ``current_practice`` benchmark and the preflight rate check
need the homes' real prices. They must never read guest data. This script is
the boundary: it reads only price, status and channel columns, aggregates them
per home per month and per season, and writes one YAML file.

Columns read from ``nightly_inventory``: property_id, stay_date, listed_price,
booked_price, status, channel. From ``comp_snapshots``/``comps``: public listed
prices and availability of the curated competitors. Nothing else.

The output holds confidential revenue (booked prices). It goes to the
gitignored ``data/exports/`` by default: the GitHub repo is public.

    PYTHONPATH=. .venv/bin/python scripts/export_rate_card.py
    PYTHONPATH=. .venv/bin/python scripts/export_rate_card.py --db path/to/wp_pricing.db --out file.yaml
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_DB = Path("~/Library/Application Support/wp-price/data/wp_pricing.db").expanduser()
DEFAULT_OUT = ROOT / "data" / "exports" / "rate_card.yaml"
HOMES = ("summit_haus", "overlook_ridge", "cloud_9")


def rate_season(day: date) -> str:
    """Season labels used by the rate card. Holiday week is split out from
    peak because its prices are a different market (see the overhaul plan)."""
    md = (day.month, day.day)
    if md >= (12, 20) or md <= (1, 2):
        return "holiday"
    if day.month in (1, 2, 3):
        return "peak_ski"
    if day.month in (11, 12):
        return "early_winter"
    if day.month == 4:
        return "shoulder_spring"
    return "summer_fall"


def _connect(path: Path) -> sqlite3.Connection:
    # immutable=1: read a consistent snapshot without creating -wal/-shm files
    # next to the live operator database.
    conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return round(ordered[index], 2)


def _stats(listed: list[float], booked: list[float], nights: int, blocked: int,
           channels: dict[str, int]) -> dict[str, Any]:
    sellable = nights - blocked
    return {
        "nights": nights,
        "blocked_nights": blocked,
        "listed_mean": round(statistics.fmean(listed), 2) if listed else None,
        "listed_p25": _quantile(listed, 0.25),
        "listed_median": _quantile(listed, 0.5),
        "listed_p75": _quantile(listed, 0.75),
        "booked_nights": len(booked),
        "booked_adr": round(statistics.fmean(booked), 2) if booked else None,
        "booked_p25": _quantile(booked, 0.25),
        "occupancy_on_books": round(len(booked) / sellable, 4) if sellable > 0 else None,
        "booked_channels": dict(sorted(channels.items())),
    }


def export(db_path: Path, *, start: str, end: str) -> dict[str, Any]:
    conn = _connect(db_path)
    try:
        homes: dict[str, Any] = {}
        for prop in conn.execute(
            "SELECT property_id, name, bedrooms, max_occupancy, base_ceiling_rate, "
            "min_floor_rate, max_ceiling_rate FROM properties WHERE property_id IN (?, ?, ?)",
            HOMES,
        ):
            homes[prop["property_id"]] = {
                "name": prop["name"],
                "bedrooms": prop["bedrooms"],
                "max_occupancy_db": prop["max_occupancy"],
                "configured": {
                    "base_ceiling_rate": prop["base_ceiling_rate"],
                    "min_floor_rate": prop["min_floor_rate"],
                    "max_ceiling_rate": prop["max_ceiling_rate"],
                },
            }
        cells: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
            lambda: {"listed": [], "booked": [], "nights": 0, "blocked": 0, "channels": defaultdict(int)}
        )
        for row in conn.execute(
            "SELECT property_id, stay_date, listed_price, booked_price, status, channel "
            "FROM nightly_inventory WHERE property_id IN (?, ?, ?) AND stay_date BETWEEN ? AND ?",
            (*HOMES, start, end),
        ):
            day = date.fromisoformat(row["stay_date"])
            for kind, label in (("month", row["stay_date"][:7]), ("season", rate_season(day))):
                cell = cells[(row["property_id"], kind, label)]
                cell["nights"] += 1
                if row["status"] == "blocked":
                    cell["blocked"] += 1
                if row["listed_price"]:
                    cell["listed"].append(float(row["listed_price"]))
                if row["status"] == "booked" and row["booked_price"]:
                    cell["booked"].append(float(row["booked_price"]))
                    cell["channels"][row["channel"] or "unknown"] += 1
        for (prop_id, kind, label), cell in sorted(cells.items()):
            homes[prop_id].setdefault(f"by_{kind}", {})[label] = _stats(
                cell["listed"], cell["booked"], cell["nights"], cell["blocked"], cell["channels"]
            )

        comps: dict[str, Any] = {}
        comp_cells: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"listed": [], "ok": 0, "unavailable": 0}
        )
        for row in conn.execute(
            "SELECT s.comp_id, s.stay_date, s.listed_price, s.scrape_status "
            "FROM comp_snapshots s JOIN comp_set_members m ON m.comp_id = s.comp_id "
            "WHERE m.property_id IN (?, ?, ?) AND s.stay_date BETWEEN ? AND ?",
            (*HOMES, start, end),
        ):
            cell = comp_cells[(row["comp_id"], rate_season(date.fromisoformat(row["stay_date"])))]
            if row["scrape_status"] == "ok" and row["listed_price"]:
                cell["ok"] += 1
                cell["listed"].append(float(row["listed_price"]))
            elif row["scrape_status"] == "unavailable":
                cell["unavailable"] += 1
        meta = {
            row["comp_id"]: row
            for row in conn.execute("SELECT comp_id, name, bedrooms, sleeps FROM comps")
        }
        for (comp_id, season), cell in sorted(comp_cells.items()):
            info = meta.get(comp_id)
            entry = comps.setdefault(comp_id, {
                "name": info["name"] if info else comp_id,
                "bedrooms": info["bedrooms"] if info else None,
                "sleeps": info["sleeps"] if info else None,
                "by_season": {},
            })
            looked = cell["ok"] + cell["unavailable"]
            entry["by_season"][season] = {
                "quotes": cell["ok"],
                "listed_median": _quantile(cell["listed"], 0.5),
                "listed_p25": _quantile(cell["listed"], 0.25),
                "listed_p75": _quantile(cell["listed"], 0.75),
                # Unavailable = booked or owner-blocked. An upper bound on
                # occupancy, but its ordering by price is the demand signal.
                "unavailable_share": round(cell["unavailable"] / looked, 4) if looked else None,
            }
    finally:
        conn.close()
    return {
        "note": (
            "Aggregates only; no guest fields. Contains confidential booked prices: "
            "keep out of the public repo."
        ),
        "source_db": str(db_path),
        "exported_on": date.today().isoformat(),
        "window": {"start": start, "end": end},
        "seasons": "holiday = 20 Dec-2 Jan; peak_ski = Jan-Mar outside holiday; "
                   "early_winter = Nov-Dec outside holiday; shoulder_spring = Apr",
        "homes": homes,
        "comps": comps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=OPERATOR_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--start", default="2025-11-01")
    parser.add_argument("--end", default="2027-04-30")
    args = parser.parse_args()
    result = export(args.db.expanduser(), start=args.start, end=args.end)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(yaml.safe_dump(result, sort_keys=False), encoding="utf-8")
    print(f"wrote {args.out}")
    for prop_id, home in result["homes"].items():
        for season in ("holiday", "peak_ski", "early_winter"):
            cell = home.get("by_season", {}).get(season)
            if cell:
                print(f"  {prop_id:15s} {season:13s} listed median {cell['listed_median']} "
                      f"booked nights {cell['booked_nights']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
