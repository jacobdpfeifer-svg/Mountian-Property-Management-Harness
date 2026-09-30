"""Engine driver for the shopper market. The world never imports this module."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from proving_ground_exam.market.competitors import tool_price
from proving_ground_exam.market.parameters import (
    daterange,
    list_scenarios,
    load_calibration,
    load_scenario,
    value_of,
)
from proving_ground_exam.market.scoring import hindsight_revenue, realized
from proving_ground_exam.market.world import MarketWorld, seed_market_db
from src.compose import Recommendation, generate_recommendations
from src.config import load_policy
from src.db import DB_KIND_DEMO, connect, init_db, mark_db_identity
from src.pacing import take_snapshot

POLICIES = ("engine", "flat", "comp_median", "tool")
_LEAD_EDGES = (8, 15, 22, 61, 121)


def _bucket(lead: int) -> int:
    for edge in _LEAD_EDGES:
        if lead < edge:
            return edge
    return 9999


def _dates(cal: dict[str, Any], max_days: int | None) -> tuple[date, date, list[date]]:
    start = date.fromisoformat(cal["season_start"])
    end = date.fromisoformat(cal["season_end"])
    nights = list(daterange(start, end))
    if max_days and max_days > 0:
        nights = nights[:max_days]
        end = nights[-1]
    return start, end, nights


def _open_db(path: Path) -> sqlite3.Connection:
    init_db(path)
    conn = connect(path)
    mark_db_identity(conn, DB_KIND_DEMO, "market_sim", force=True)
    return conn


def _fingerprint(
    conn: sqlite3.Connection,
    properties: list[str],
    nights: list[date],
    as_of: date,
) -> dict[tuple[str, date], tuple]:
    start, end = nights[0], nights[-1]
    placeholders = ",".join("?" * len(properties))
    rows = conn.execute(
        f"""
        SELECT property_id, stay_date, status, listed_price
        FROM nightly_inventory
        WHERE property_id IN ({placeholders}) AND stay_date BETWEEN ? AND ?
        ORDER BY property_id, stay_date
        """,
        (*properties, start.isoformat(), end.isoformat()),
    ).fetchall()
    by_prop: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_prop.setdefault(row["property_id"], []).append(row)
    comps = {
        row["stay_date"]: row["px"]
        for row in conn.execute(
            """
            SELECT stay_date, ROUND(AVG(listed_price), 2) AS px
            FROM comp_snapshots
            WHERE as_of = ? AND scrape_status = 'ok' AND listed_price IS NOT NULL
            GROUP BY stay_date
            """,
            (as_of.isoformat(),),
        )
    }
    # The seasonal anchor reads every listed price, and pacing reads the
    # whole book. A change to either moves recommendations that a per-night
    # lead bucket would have treated as unchanged.
    digest = {
        row["property_id"]: (row["n"], round(float(row["px"] or 0), 2), row["booked"])
        for row in conn.execute(
            f"""
            SELECT property_id,
                   COUNT(*) AS n,
                   SUM(listed_price) AS px,
                   SUM(CASE WHEN status = 'booked' THEN 1 ELSE 0 END) AS booked
            FROM nightly_inventory
            WHERE property_id IN ({placeholders})
            GROUP BY property_id
            """,
            properties,
        )
    }
    out: dict[tuple[str, date], tuple] = {}
    for prop, prop_rows in by_prop.items():
        statuses = [row["status"] for row in prop_rows]
        for index, row in enumerate(prop_rows):
            stay = date.fromisoformat(row["stay_date"])
            neighbors = tuple(statuses[max(0, index - 2): index + 3])
            out[(prop, stay)] = (
                _bucket((stay - as_of).days),
                row["status"],
                neighbors,
                round(float(row["listed_price"] or 0), 2),
                comps.get(row["stay_date"]),
                digest.get(prop),
            )
    return out


def _apply_flat(world: MarketWorld, nights: list[date]) -> None:
    prices = {}
    for prop in world.properties:
        for night in nights:
            prices[(prop, night)] = world._flat(night)
    world.set_own_prices(prices)


def _apply_comp_median(world: MarketWorld, conn: sqlite3.Connection, day: date, nights: list[date]) -> None:
    medians = {
        date.fromisoformat(row["stay_date"]): float(row["px"])
        for row in conn.execute(
            """
            SELECT stay_date, AVG(listed_price) AS px
            FROM comp_snapshots
            WHERE as_of = ? AND scrape_status = 'ok' AND listed_price IS NOT NULL
            GROUP BY stay_date
            """,
            (day.isoformat(),),
        )
        if row["px"] is not None
    }
    prices = {}
    for prop in world.properties:
        for night in nights:
            prices[(prop, night)] = medians.get(night, world._flat(night))
    world.set_own_prices(prices)


def _apply_tool(world: MarketWorld, conn: sqlite3.Connection, day: date, nights: list[date]) -> None:
    prices = {}
    price_war = bool(world.scenario.get("price_war"))
    for prop, meta in world.cal["properties"].items():
        booked = {
            date.fromisoformat(row["stay_date"])
            for row in conn.execute(
                """
                SELECT stay_date FROM nightly_inventory
                WHERE property_id = ? AND status = 'booked' AND stay_date >= ?
                """,
                (prop, day.isoformat()),
            )
        }
        horizon = [day + timedelta(days=i) for i in range(30)]
        occ = sum(1 for night in horizon if night in booked) / len(horizon)
        for night in nights:
            if night < day:
                continue
            prices[(prop, night)] = tool_price(
                night,
                base=float(meta["base"]),
                holiday=world.is_holiday(night),
                occupancy_30=occ,
                lead_days=(night - day).days,
                price_war=price_war,
            )
    world.set_own_prices(prices)


def _serialize_rec(rec: Recommendation) -> str:
    payload = asdict(rec)
    return json.dumps(payload, sort_keys=True, default=str)


def _apply_engine(
    world: MarketWorld,
    conn: sqlite3.Connection,
    day: date,
    nights: list[date],
    *,
    incremental: bool,
    cache: dict[tuple[str, date], tuple],
    engine_policy: dict | None = None,
) -> list[Recommendation]:
    start, end = nights[0], nights[-1]
    props = list(world.properties)
    stay_dates = None
    if incremental and cache:
        current = _fingerprint(conn, props, nights, day)
        changed = {key[1] for key, fp in current.items() if cache.get(key, (None,))[0] != fp}
        # Always reprice the first night of each property so a sample of fields moves.
        if changed:
            stay_dates = changed
        else:
            return []
    recs, _health = generate_recommendations(
        conn,
        max(day, start),
        end,
        property_ids=props,
        policy=engine_policy or load_policy(),
        persist=True,
        allow_past=True,
        as_of=day,
        stay_dates=stay_dates,
    )
    prices = {(rec.property_id, rec.stay_date): rec.recommended_price for rec in recs}
    world.set_own_prices(prices)
    if incremental:
        current = _fingerprint(conn, props, nights, day)
        for rec in recs:
            key = (rec.property_id, rec.stay_date)
            cache[key] = (current.get(key), _serialize_rec(rec), rec.recommended_price)
    return recs


@dataclass
class MarketResult:
    scenario: str
    seed: int
    policy: str
    held_out: bool
    scores: dict[str, Any]
    content_hash: str
    hindsight_revenue: float
    hindsight_gap: float | None


def run_market_job(
    scenario_name: str,
    seed: int,
    policy: str,
    *,
    db_path: Path | None = None,
    max_days: int | None = None,
    incremental: bool = False,
    decision_limit: int | None = None,
    calibration: dict | None = None,
    scenario_doc: dict | None = None,
    engine_policy: dict | None = None,
) -> MarketResult:
    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {POLICIES}")
    cal = calibration if calibration is not None else load_calibration()
    scenario = scenario_doc if scenario_doc is not None else load_scenario(scenario_name)
    start, end, nights = _dates(cal, max_days)
    if db_path is None:
        db_path = Path(f".testrun_runs/market_sim/job_{scenario_name}_{policy}_{seed}.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = _open_db(db_path)
    try:
        seed_market_db(conn, cal, start, end)
        world = MarketWorld(cal, scenario, seed, conn, season_start=start, season_end=end)
        cache: dict[tuple[str, date], tuple] = {}
        for index, day in enumerate(nights):
            if decision_limit is not None and index >= decision_limit:
                break
            world.begin_day(day)
            take_snapshot(conn, as_of=day)
            if policy == "flat":
                _apply_flat(world, nights)
            elif policy == "comp_median":
                _apply_comp_median(world, conn, day, nights)
            elif policy == "tool":
                _apply_tool(world, conn, day, nights)
            else:
                _apply_engine(
                    world, conn, day, nights,
                    incremental=incremental, cache=cache, engine_policy=engine_policy,
                )
            world.end_day(day)
        scores = realized(conn, list(world.properties))
        hind, gap = hindsight_revenue(
            world.shoppers, cal["properties"], start, end, value_of(cal["median_nightly"])
        )
        payload = {
            "scenario": scenario_name,
            "seed": seed,
            "policy": policy,
            "scores": scores,
            "hindsight_revenue": hind,
            "hindsight_gap": gap,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return MarketResult(
            scenario=scenario_name,
            seed=seed,
            policy=policy,
            held_out=bool(scenario.get("held_out")),
            scores=scores,
            content_hash=digest,
            hindsight_revenue=hind,
            hindsight_gap=gap,
        )
    finally:
        conn.close()


def validation_report(result: MarketResult, cal: dict[str, Any] | None = None) -> dict[str, Any]:
    cal = cal or load_calibration()
    rules = cal["validation"]
    scores = result.scores
    checks = {
        "lead_le_21": scores["lead_le_21"],
        "los_mean": scores["los_mean"],
        "inquiry_per_confirmed": scores["inquiry_per_confirmed"],
        "occupancy_peak": scores["occupancy_peak"],
        "occupancy_early": scores["occupancy_early"],
    }
    report = {}
    for name, observed in checks.items():
        rule = rules[name]
        lo, hi = float(rule["lo"]), float(rule["hi"])
        report[name] = {
            "observed": observed,
            "lo": lo,
            "hi": hi,
            "passed": lo <= observed <= hi,
            "source": rule.get("source", ""),
        }
    report["passed"] = all(item["passed"] for item in report.values() if isinstance(item, dict))
    return report


def write_scoreboard(results: list[MarketResult], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for result in results:
        row = {
            "scenario": result.scenario,
            "seed": result.seed,
            "policy": result.policy,
            "held_out": result.held_out,
            "content_hash": result.content_hash,
            "hindsight_revenue": result.hindsight_revenue,
            "hindsight_gap": result.hindsight_gap,
            **result.scores,
        }
        rows.append(row)
    manifest = {
        "rows": rows,
        "note": "Paired comparisons use a common shopper seed. Intervals are not family-wise adjusted.",
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    csv_path = output_dir / "scoreboard.csv"
    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")
    md_path = output_dir / "REPORT.md"
    lines = ["# Market simulator scoreboard", ""]
    lines.append("| scenario | seed | policy | revenue | revpan | occupancy | held_out |")
    lines.append("|---|---:|---|---:|---:|---:|---|")
    for row in rows:
        lines.append(
            f"| {row['scenario']} | {row['seed']} | {row['policy']} | {row['revenue']:.2f} | "
            f"{row['revpan']:.2f} | {row['occupancy']:.3f} | {row['held_out']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {"manifest": str(manifest_path), "csv": str(csv_path), "report": str(md_path), "hash": digest}


def scenario_names(requested: str) -> list[str]:
    if requested == "all":
        names = list_scenarios()
        if not names:
            raise FileNotFoundError("no scenarios in proving_ground_exam/scenarios")
        return names
    load_scenario(requested)
    return [requested]


def _discard_db(path: Path) -> None:
    path.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def _pool_job(job: tuple[str, int, str, str, int | None, bool]) -> MarketResult:
    name, seed, policy, output_dir, max_days, incremental = job
    db_path = Path(output_dir) / "dbs" / f"{name}_{policy}_{seed}.db"
    try:
        return run_market_job(
            name, seed, policy, db_path=db_path, max_days=max_days, incremental=incremental,
        )
    finally:
        _discard_db(db_path)


def run_pool(
    scenario_name: str,
    seeds: int,
    policy: str,
    *,
    workers: int,
    output_dir: Path,
    max_days: int | None = None,
    incremental: bool = False,
) -> dict[str, str]:
    from concurrent.futures import ProcessPoolExecutor, as_completed

    names = scenario_names(scenario_name)
    jobs = [
        (name, seed, policy, str(output_dir), max_days, incremental)
        for name in names
        for seed in range(1, seeds + 1)
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[MarketResult] = []
    if workers <= 1 or len(jobs) == 1:
        for job in jobs:
            results.append(_pool_job(job))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_pool_job, job) for job in jobs]
            done = 0
            for future in as_completed(futures):
                results.append(future.result())
                done += 1
                if done == 1 or done % 10 == 0 or done == len(jobs):
                    print(f"market jobs {done}/{len(jobs)}", flush=True)
    results.sort(key=lambda item: (item.scenario, item.seed, item.policy))
    return write_scoreboard(results, output_dir)


def run_grid(
    scenario_name: str,
    seeds: int,
    policies: tuple[str, ...],
    *,
    workers: int,
    output_dir: Path,
    max_days: int | None = None,
    incremental: bool = False,
) -> dict[str, str]:
    """One scoreboard covering every policy. Jobs share a process pool."""
    from concurrent.futures import ProcessPoolExecutor, as_completed

    names = scenario_names(scenario_name)
    jobs = [
        (name, seed, policy, str(output_dir), max_days, incremental)
        for policy in policies
        for name in names
        for seed in range(1, seeds + 1)
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[MarketResult] = []
    if workers <= 1 or len(jobs) == 1:
        for index, job in enumerate(jobs, start=1):
            results.append(_pool_job(job))
            if index == 1 or index % 10 == 0 or index == len(jobs):
                print(f"market jobs {index}/{len(jobs)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_pool_job, job) for job in jobs]
            done = 0
            for future in as_completed(futures):
                results.append(future.result())
                done += 1
                if done == 1 or done % 10 == 0 or done == len(jobs):
                    print(f"market jobs {done}/{len(jobs)}", flush=True)
    results.sort(key=lambda item: (item.scenario, item.policy, item.seed))
    return write_scoreboard(results, output_dir)
