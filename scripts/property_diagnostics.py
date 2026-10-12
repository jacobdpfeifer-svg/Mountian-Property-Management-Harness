#!/usr/bin/env python3
"""Property-level market-sim diagnosis from retained job databases.

The portfolio scoreboard hides the Cloud 9 and Overlook Ridge gap. This report
is by property: price against the flat rate and the comp median, the engine's
ceiling and floor, simulated quality and willingness to pay, why a home lost
the shopper, and occupancy by lead bucket.

Choice reasons are present only for runs started after the trace table was
added. Older retained databases still produce the price and occupancy sections.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from proving_ground_exam.market.parameters import LEAD_BUCKETS, load_calibration, season_of, value_of
from src.ceiling import compute_ceiling
from src.config import load_policy, load_policy_overlay
from src.features import build_features_for_property


PROBE_DATES = (date(2026, 11, 25), date(2026, 12, 24), date(2027, 1, 16))


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _lead_bucket(lead: int | None) -> str:
    if lead is None:
        return "unsold"
    for lo, hi in LEAD_BUCKETS:
        if lo <= lead <= hi:
            return f"{lo}-{hi}"
    return f"{LEAD_BUCKETS[-1][1] + 1}+"


def _seeds(db_dir: Path, scenario: str, policy: str) -> list[int]:
    found = []
    for path in db_dir.glob(f"{scenario}_{policy}_*.db"):
        found.append(int(path.stem.rsplit("_", 1)[1]))
    return sorted(found)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _nights(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = []
    for row in conn.execute(
        """
        SELECT property_id, stay_date, status, listed_price, booked_price, booked_at
        FROM nightly_inventory
        """
    ):
        stay = date.fromisoformat(row["stay_date"])
        booked = row["status"] == "booked" and row["booked_price"] is not None
        lead = None
        if booked and row["booked_at"]:
            lead = (stay - date.fromisoformat(str(row["booked_at"])[:10])).days
        price = float(row["booked_price"]) if booked else (
            float(row["listed_price"]) if row["listed_price"] is not None else None
        )
        rows.append({
            "property_id": row["property_id"],
            "stay_date": row["stay_date"],
            "season": season_of(stay),
            "booked": booked,
            "price": price,
            "lead": _lead_bucket(lead),
        })
    return rows


def _recommendations(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT property_id, stay_date, ceiling_price, floor_price,
                   listed_price_at_run, final_price, recommended_price, ceiling_confidence
            FROM price_recommendations
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    out = []
    for row in rows:
        out.append({
            "property_id": row["property_id"],
            "season": season_of(date.fromisoformat(row["stay_date"])),
            "ceiling": float(row["ceiling_price"]),
            "floor": float(row["floor_price"]),
            "listed": None if row["listed_price_at_run"] is None else float(row["listed_price_at_run"]),
            "final": None if row["final_price"] is None else float(row["final_price"]),
            "recommended": float(row["recommended_price"]),
            "confidence": None if row["ceiling_confidence"] is None else float(row["ceiling_confidence"]),
        })
    return out


def _trace(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    try:
        return list(conn.execute(
            """
            SELECT property_id, reason, wtp, quality, nightly
            FROM sim_choice_trace
            """
        ))
    except sqlite3.OperationalError:
        return []


def _probe_ceiling(conn: sqlite3.Connection, policy: dict[str, Any]) -> list[dict[str, Any]]:
    props = [row["property_id"] for row in conn.execute("SELECT property_id FROM properties")]
    found = []
    for prop in props:
        for probe in PROBE_DATES:
            features = build_features_for_property(
                conn, prop, probe, probe, policy=policy, as_of=date(2026, 11, 1),
            )
            if not features:
                continue
            ceiling = compute_ceiling(conn, features[0], policy, as_of=date(2026, 11, 1))
            found.append({
                "property_id": prop,
                "stay_date": probe.isoformat(),
                "season": features[0].season,
                "ceiling": round(ceiling.ceiling_price, 2),
                "method": ceiling.method,
                "booked_n": ceiling.booked_sample_size,
                "listed_n": ceiling.listed_sample_size,
                "anchor_booked_n": ceiling.anchor_booked_sample_size,
                "holiday_n": ceiling.holiday_sample_size,
                "band_low": None if ceiling.band_low is None else round(ceiling.band_low, 2),
                "band_high": None if ceiling.band_high is None else round(ceiling.band_high, 2),
                "thin_anchor": ceiling.thin_anchor,
                "confidence": ceiling.confidence,
            })
    return found


def _accumulate(bucket: dict[str, list[float]], key: str, value: float | None) -> None:
    if value is not None:
        bucket[key].append(value)


def diagnose(
    run_dir: Path,
    scenario: str,
    *,
    policy_path: Path | None = None,
) -> dict[str, Any]:
    db_dir = run_dir / "dbs"
    engine_seeds = _seeds(db_dir, scenario, "engine")
    if not engine_seeds:
        raise FileNotFoundError(f"no retained {scenario} engine databases under {db_dir}")
    cal = load_calibration()
    # Candidate reports must use the same policy file that produced the run.
    # Falling back to default is useful for legacy retained databases, but it
    # must be explicit in the report so a candidate cannot look like default.
    policy = load_policy_overlay(policy_path) if policy_path else load_policy()
    policies = ["engine", "flat", "comp_median"]
    present = {name: _seeds(db_dir, scenario, name) for name in policies}
    price_acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    occ_acc: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    rec_acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    reasons: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    wtp_acc: dict[str, list[float]] = defaultdict(list)
    quality: dict[str, float] = {}
    probes: list[dict[str, Any]] = []
    trace_rows = 0

    for prop, meta in cal["properties"].items():
        quality[prop] = value_of(meta["quality"])

    for seed in engine_seeds:
        books = {}
        for name in policies:
            path = db_dir / f"{scenario}_{name}_{seed}.db"
            if not path.exists():
                continue
            conn = _connect(path)
            try:
                books[name] = _nights(conn)
                if name == "engine":
                    for rec in _recommendations(conn):
                        season_key = f"{rec['property_id']}|{rec['season']}"
                        for field in ("ceiling", "floor", "listed", "final", "confidence"):
                            _accumulate(rec_acc[season_key], field, rec[field])
                    for row in _trace(conn):
                        trace_rows += 1
                        reasons[row["property_id"]][row["reason"]] += 1
                        if row["wtp"] is not None:
                            wtp_acc[row["property_id"]].append(float(row["wtp"]))
                    if seed == engine_seeds[0]:
                        probes.extend(_probe_ceiling(conn, policy))
            finally:
                conn.close()
        if "engine" not in books:
            continue
        others = {
            name: {(row["property_id"], row["stay_date"]): row for row in rows}
            for name, rows in books.items()
            if name != "engine"
        }
        for row in books["engine"]:
            key = f"{row['property_id']}|{row['season']}"
            _accumulate(price_acc[key], "engine", row["price"])
            bucket = row["lead"] if row["booked"] else "unsold"
            occ_acc[(row["property_id"], row["season"], bucket)].append(1.0)
            night_key = (row["property_id"], row["stay_date"])
            for name, indexed in others.items():
                other = indexed.get(night_key)
                if other is not None:
                    _accumulate(price_acc[key], name, other["price"])

    properties = []
    seasons = sorted({key.split("|", 1)[1] for key in price_acc})
    prop_ids = sorted({key.split("|", 1)[0] for key in price_acc})
    for prop in prop_ids:
        by_season = {}
        for season in seasons:
            key = f"{prop}|{season}"
            if key not in price_acc and key not in rec_acc:
                continue
            lead = {}
            for (p, s, bucket), values in occ_acc.items():
                if p == prop and s == season:
                    lead[bucket] = {"nights": len(values)}
            total = sum(item["nights"] for item in lead.values()) or 1
            for bucket, item in lead.items():
                item["share"] = round(item["nights"] / total, 4)
            by_season[season] = {
                "mean_price": {name: _mean(vals) for name, vals in price_acc[key].items()},
                "engine_band": {name: _mean(vals) for name, vals in rec_acc[key].items()},
                "lead_buckets": lead,
            }
        properties.append({
            "property_id": prop,
            "name": cal["properties"].get(prop, {}).get("name", prop),
            "quality": quality.get(prop),
            "mean_wtp_of_shoppers": _mean(wtp_acc[prop]),
            "loss_reasons": dict(reasons[prop]),
            "seasons": by_season,
        })

    probe_summary: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in probes:
        probe_summary[row["property_id"]].append(row)

    policy_label = str(policy_path) if policy_path else "default.yaml"
    return {
        "scenario": scenario,
        "policy_path": policy_label,
        "engine_seeds": engine_seeds,
        "policies_found": {name: seeds for name, seeds in present.items() if seeds},
        "choice_trace_rows": trace_rows,
        "choice_trace_note": (
            "Reasons count shopper-property considerations. "
            "above_wtp and price are price losses; outside is a feasible listing "
            "lost to the outside option; unavailable is calendar; fit is party size."
            if trace_rows
            else "This database has no sim_choice_trace. Price and occupancy are still reported. "
            "A new run records why each home lost the shopper."
        ),
        "properties": properties,
        "ceiling_probes": probe_summary,
        "ceiling_probe_note": (
            "Ceiling probes are seed 1, as of 2026-11-01, before this simulated season's "
            "own bookings. holiday_n is the booked sample inside 19 Dec–3 Jan. "
            "The band is a reporting interval; it is not itself a price change. "
            f"Policy used for the probe: {policy_label}."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Property diagnosis: {report['scenario']}",
        "",
        report["choice_trace_note"],
        "",
        report["ceiling_probe_note"],
        "",
    ]
    for prop in report["properties"]:
        lines.append(f"## {prop['name']} (`{prop['property_id']}`)")
        lines.append("")
        lines.append(
            f"Simulated quality {prop['quality']}. "
            f"Mean willingness-to-pay multiplier among shoppers who considered it: "
            f"{prop['mean_wtp_of_shoppers']}."
        )
        if prop["loss_reasons"]:
            rendered = ", ".join(f"{name} {count}" for name, count in sorted(prop["loss_reasons"].items()))
            lines.append(f"Loss reasons: {rendered}.")
        lines.append("")
        lines.append("| season | engine price | flat price | comp price | ceiling | floor | listed | final |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for season, block in prop["seasons"].items():
            price = block["mean_price"]
            band = block["engine_band"]
            lines.append(
                f"| {season} | {price.get('engine')} | {price.get('flat')} | {price.get('comp_median')} | "
                f"{band.get('ceiling')} | {band.get('floor')} | {band.get('listed')} | {band.get('final')} |"
            )
        lines.append("")
        lines.append("| season | lead bucket | nights | share |")
        lines.append("|---|---|---:|---:|")
        for season, block in prop["seasons"].items():
            for bucket, item in sorted(block["lead_buckets"].items()):
                lines.append(f"| {season} | {bucket} | {item['nights']} | {item['share']} |")
        lines.append("")
    if report["ceiling_probes"]:
        lines.append("## Ceiling sample sizes")
        lines.append("")
        lines.append("| property | date | booked n | listed n | holiday booked n | band | thin |")
        lines.append("|---|---|---:|---:|---:|---|---|")
        for prop, rows in report["ceiling_probes"].items():
            # Average identical probes across seeds by showing the first seed's shape
            # and the mean booked count.
            seen = {}
            for row in rows:
                seen.setdefault(row["stay_date"], []).append(row)
            for stay, group in sorted(seen.items()):
                booked = _mean([row["booked_n"] for row in group])
                listed = _mean([row["listed_n"] for row in group])
                holiday = _mean([row["holiday_n"] for row in group])
                sample = group[0]
                lines.append(
                    f"| {prop} | {stay} | {booked} | {listed} | {holiday} | "
                    f"{sample['band_low']}–{sample['band_high']} | {sample['thin_anchor']} |"
                )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--scenario", default="normal")
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--md", dest="md_path", type=Path)
    parser.add_argument(
        "--engine-policy",
        type=Path,
        help="Policy YAML used for the engine run; candidate files may extend default",
    )
    args = parser.parse_args()
    report = diagnose(args.run_dir, args.scenario, policy_path=args.engine_policy)
    text = render_markdown(report)
    if args.json_path:
        args.json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_path:
        args.md_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
