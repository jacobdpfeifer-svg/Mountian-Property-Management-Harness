"""Engine driver for the shopper market. The world never imports this module."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from collections.abc import Collection
from typing import Any

from proving_ground_exam.market.competitors import tool_price
from proving_ground_exam.market.parameters import (
    ROOT as MARKET_ROOT,
    CALIBRATION_PATH,
    daterange,
    is_v2,
    list_scenarios,
    load_calibration,
    load_scenario,
    season_of,
    value_of,
)
from proving_ground_exam.market.rngutil import generator
from proving_ground_exam.market.scoring import hindsight_revenue, realized
from proving_ground_exam.market.world import MarketWorld, seed_market_db
from src.compose import Recommendation, generate_recommendations
from src.config import load_policy, load_policy_overlay
from src.db import DB_KIND_DEMO, connect, init_db, mark_db_identity
from src.pacing import take_snapshot

CORE_POLICIES = ("engine", "flat", "comp_median", "tool")
# Calibration v2 adds the homes' real rate card as a benchmark: what the manager
# charges today. A grid run on v2 includes it automatically.
V2_POLICIES = ("current_practice",)
# Benchmarks that separate "the engine is worse than one flat rate" from
# "the engine's property premia are worse". hindsight_oracle is not a policy:
# it is the non-deployable bound already stored on every result.
DIAGNOSTIC_POLICIES = ("property_flat", "comp_property", "premium_cap")
POLICIES = CORE_POLICIES + DIAGNOSTIC_POLICIES + V2_POLICIES
CALIBRATIONS = {"v1": CALIBRATION_PATH, "v2": MARKET_ROOT / "calibration_v2.yaml"}


def resolve_calibration(name_or_path: str | Path | None) -> Path:
    """``v1``/``v2`` or a path. None means the official v1 file."""
    if name_or_path is None:
        return CALIBRATION_PATH
    key = str(name_or_path)
    if key in CALIBRATIONS:
        return CALIBRATIONS[key]
    return Path(key).expanduser()
_RESUME_IGNORE = frozenset({
    # The file's hash (calibration_file_sha256) is the identity; the path is for readers.
    "calibration_path",
    "git_dirty",
    "git_dirty_tracked",
    "git_status",
    "git_untracked",
})
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


def _property_season_rate(world: MarketWorld, prop: str, night: date) -> float:
    """This home's base, scaled by the same seasonal shape as the flat benchmark.

    Peak uses the property base itself (Cloud 9 1035, Overlook 916, Summit 793),
    not the single $900 peak flat rate.
    """
    base = float(world.cal["properties"][prop]["base"])
    peak = value_of(world.cal["flat_price"]["peak_ski"])
    return base * value_of(world.cal["flat_price"][season_of(night)]) / peak


def _apply_current_practice(world: MarketWorld, nights: list[date]) -> None:
    """Each home at its real seasonal listed price (publicly listed rate card).

    Calibration v2 only. Holiday nights use the holiday rate.
    """
    card = world.cal.get("current_practice")
    if not card:
        raise ValueError("current_practice needs calibration v2 (a current_practice rate card)")
    prices = {}
    for prop in world.properties:
        rates = card[prop]
        for night in nights:
            prices[(prop, night)] = value_of(world.priced_by_span(rates, night))
    world.set_own_prices(prices)


def _comp_medians(conn: sqlite3.Connection, day: date) -> dict[date, float]:
    return {
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


def _apply_property_flat(world: MarketWorld, nights: list[date]) -> None:
    prices = {}
    for prop in world.properties:
        for night in nights:
            prices[(prop, night)] = _property_season_rate(world, prop, night)
    world.set_own_prices(prices)


def _apply_comp_property(world: MarketWorld, conn: sqlite3.Connection, day: date, nights: list[date]) -> None:
    """Follow the comp median, scaled by this home's base relative to the portfolio median base."""
    medians = _comp_medians(conn, day)
    bases = sorted(float(meta["base"]) for meta in world.cal["properties"].values())
    portfolio = bases[len(bases) // 2]
    prices = {}
    for prop in world.properties:
        scale = float(world.cal["properties"][prop]["base"]) / portfolio
        for night in nights:
            fallback = _property_season_rate(world, prop, night)
            prices[(prop, night)] = medians.get(night, fallback / scale) * scale
    world.set_own_prices(prices)


def _apply_premium_cap(world: MarketWorld, conn: sqlite3.Connection, day: date, nights: list[date]) -> None:
    """Property flat, capped at the comp median when assumed quality is below 1.

    Quality of 1.0 may sit 10% above the comp median. This is a diagnostic
    benchmark, not a deployable engine policy.
    """
    medians = _comp_medians(conn, day)
    prices = {}
    for prop in world.properties:
        quality = value_of(world.cal["properties"][prop]["quality"])
        allowance = 1.10 if quality >= 1.0 else 1.0
        for night in nights:
            flat_price = _property_season_rate(world, prop, night)
            comp = medians.get(night)
            prices[(prop, night)] = flat_price if comp is None else min(flat_price, comp * allowance)
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
    persist_recommendations: bool = True,
    approval_rate: float | None = None,
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
        persist=persist_recommendations,
        allow_past=True,
        as_of=day,
        stay_dates=stay_dates,
        # Keyed by decision day so a retained job database can say which
        # recommendation priced a night on the day it booked.
        run_id=f"sim-{day.isoformat()}",
    )
    prices = {
        (rec.property_id, rec.stay_date): rec.recommended_price
        for rec in recs
        if _goes_live(rec, world, day, approval_rate)
    }
    world.set_own_prices(prices)
    if incremental:
        current = _fingerprint(conn, props, nights, day)
        for rec in recs:
            key = (rec.property_id, rec.stay_date)
            cache[key] = (current.get(key), _serialize_rec(rec), rec.recommended_price)
    return recs


def _goes_live(rec: Recommendation, world: MarketWorld, day: date, approval_rate: float | None) -> bool:
    """Whether a recommendation reaches the listing.

    ``approval_rate`` None scores recommendation quality: every price goes live
    (the owner approves everything). Otherwise the run is production-faithful:
    production pushes only unblocked ``handle`` recommendations
    (src/pms/__init__.py), and everything else goes live only if a human
    approves it that day, with probability ``approval_rate``. A night that is
    not approved keeps yesterday's listed price.
    """
    if approval_rate is None:
        return True
    if rec.status != "blocked" and rec.autonomy_level == "handle":
        return True
    draw = generator(
        world.scenario_name, world.seed, "approve", rec.property_id,
        rec.stay_date.isoformat(), day.isoformat(),
    ).random()
    return float(draw) < approval_rate


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
    persist_recommendations: bool = True,
    trace_choices: bool = True,
    approval_rate: float | None = None,
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
        world = MarketWorld(
            cal, scenario, seed, conn, season_start=start, season_end=end,
            trace_choices=trace_choices,
        )
        cache: dict[tuple[str, date], tuple] = {}
        guardrails: Counter[str] = Counter()
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
            elif policy == "property_flat":
                _apply_property_flat(world, nights)
            elif policy == "comp_property":
                _apply_comp_property(world, conn, day, nights)
            elif policy == "premium_cap":
                _apply_premium_cap(world, conn, day, nights)
            elif policy == "current_practice":
                _apply_current_practice(world, nights)
            else:
                recs = _apply_engine(
                    world, conn, day, nights,
                    incremental=incremental, cache=cache, engine_policy=engine_policy,
                    persist_recommendations=persist_recommendations,
                    approval_rate=approval_rate,
                )
                guardrails.update(rec.guardrail_action or "" for rec in recs)
            world.end_day(day)
        if is_v2(cal):
            scores = realized(
                conn, list(world.properties),
                economics=cal.get("economics"), guest_fees=cal.get("guest_fees"),
            )
        else:
            scores = realized(conn, list(world.properties))
        if policy == "engine":
            # The examiner counts guardrails from persisted recommendations, which a
            # score-only job does not write. Count the same rows here so a score-only
            # job and a retained one report the same counts and content hash.
            scores["guardrail_by_action"] = dict(sorted(guardrails.items()))
            scores["guardrail_triggers"] = sum(n for action, n in guardrails.items() if action)
        hind, gap = hindsight_revenue(
            world.shoppers, cal["properties"], start, end,
            world.reference if is_v2(cal) else value_of(cal["median_nightly"]),
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
        _close_job_db(conn)


def _close_job_db(conn: sqlite3.Connection) -> None:
    """Close a finished job database as a single self-contained file.

    A WAL-mode file makes every later read-only reader (audit, decomposer)
    leave ``-wal``/``-shm`` files beside it. Switching back to a rollback
    journal after the last write means a retained ``.db`` copies and reads
    cleanly on its own. Scores and hashes are computed before this point.
    """
    try:
        # journal_mode cannot change inside an open transaction.
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.Error:
        # A failed job closes as it is; the error that ended it is what matters.
        pass
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
    report: dict[str, Any] = {}
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


def _result_row(result: MarketResult) -> dict[str, Any]:
    return {
        "scenario": result.scenario,
        "seed": result.seed,
        "policy": result.policy,
        "held_out": result.held_out,
        "content_hash": result.content_hash,
        "hindsight_revenue": result.hindsight_revenue,
        "hindsight_gap": result.hindsight_gap,
        **result.scores,
    }


def write_scoreboard(
    results: list[MarketResult],
    output_dir: Path,
    provenance: dict[str, Any] | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [_result_row(result) for result in results]
    manifest: dict[str, Any] = {
        "rows": rows,
        "note": "Paired comparisons use a common shopper seed. Intervals are not family-wise adjusted.",
    }
    if provenance is not None:
        manifest["provenance"] = provenance
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
    lines.append("")
    lines.append(
        "hindsight_revenue on each row is a non-deployable oracle: it charges willingness "
        "to pay and ignores competitors. It is not a policy that can be shipped."
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    oracle_path = output_dir / "hindsight_oracle.csv"
    seen: dict[tuple[str, int], MarketResult] = {}
    for result in results:
        seen.setdefault((result.scenario, result.seed), result)
    with oracle_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["scenario", "seed", "hindsight_revenue", "hindsight_gap", "deployable", "label"],
        )
        writer.writeheader()
        for result in seen.values():
            writer.writerow({
                "scenario": result.scenario,
                "seed": result.seed,
                "hindsight_revenue": result.hindsight_revenue,
                "hindsight_gap": result.hindsight_gap,
                "deployable": False,
                "label": "non-deployable hindsight upper bound",
            })
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {
        "manifest": str(manifest_path),
        "csv": str(csv_path),
        "report": str(md_path),
        "oracle": str(oracle_path),
        "hash": digest,
    }


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


# (scenario, seed, policy, output_dir, max_days, incremental, retain_db,
#  engine_policy_path, sensitivity_path, calibration_path, approval_rate)
Job = tuple[
    str, int, str, str, int | None, bool, bool, str | None, str | None, str | None, float | None
]

CHECKPOINT = "results.jsonl"
RUN_CONFIG = "run_config.json"
FAILURE = "failure.json"
# Measured on full 180-night seasons: an engine job keeps every day's
# recommendations (~80 MB); the other policies keep only the book (~20 MB).
_DB_BYTES = {"engine": 90_000_000}
_DB_BYTES_OTHER = 25_000_000
_DISK_HEADROOM = 10_000_000_000


def _pool_job(job: Job) -> MarketResult:
    from src.proving_ground.sensitivity import apply_sensitivity, load_sensitivity

    (name, seed, policy, output_dir, max_days, incremental, retain_db, engine_policy_path,
     sensitivity_path, calibration_path, approval_rate) = job
    db_path = Path(output_dir) / "dbs" / f"{name}_{policy}_{seed}.db"
    engine_policy = load_policy_overlay(Path(engine_policy_path)) if engine_policy_path else None
    calibration = load_calibration(Path(calibration_path)) if calibration_path else None
    if sensitivity_path:
        calibration = apply_sensitivity(
            calibration if calibration is not None else load_calibration(),
            load_sensitivity(Path(sensitivity_path)),
        )
    try:
        return run_market_job(
            name, seed, policy, db_path=db_path, max_days=max_days, incremental=incremental,
            engine_policy=engine_policy, calibration=calibration,
            persist_recommendations=retain_db,
            trace_choices=retain_db,
            approval_rate=approval_rate,
        )
    finally:
        if not retain_db:
            _discard_db(db_path)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str | None:
    import subprocess

    try:
        out = subprocess.run(
            ["git", *args], cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, timeout=10, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def path_is_icloud(path: Path) -> bool:
    try:
        text = str(path.expanduser().resolve())
    except OSError:
        text = str(path.expanduser())
    return any(marker in text for marker in ("Mobile Documents", "com~apple~CloudDocs", "iCloud Drive", "iCloudDrive"))


def assert_outside_icloud(path: Path) -> None:
    if path_is_icloud(path):
        raise RuntimeError(
            f"{path} is inside iCloud. Databases and logs for a market simulation must live "
            "outside it, for example ~/wp-price-runs/market_sim/."
        )


def _git_provenance() -> dict[str, Any]:
    tracked = _git("status", "--porcelain", "--untracked-files=no")
    full = _git("status", "--porcelain")
    untracked = _git("ls-files", "--others", "--exclude-standard")
    diff = _git("diff", "HEAD")
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(full) if full is not None else None,
        "git_dirty_tracked": bool(tracked) if tracked is not None else None,
        "git_status": full,
        "git_untracked": [] if not untracked else untracked.splitlines(),
        "git_diff_sha256": (
            hashlib.sha256(diff.encode()).hexdigest() if diff is not None else None
        ),
    }


def run_config(
    *,
    names: list[str],
    seeds: int,
    policies: tuple[str, ...],
    max_days: int | None,
    incremental: bool,
    engine_policy_path: Path | None,
    sensitivity_path: Path | None = None,
    retained_scenarios: Collection[str] | None = None,
    calibration_path: Path | None = None,
    approval_rate: float | None = None,
    allow_models: bool = False,
) -> dict[str, Any]:
    """Everything that must match for two runs' rows to be comparable."""
    from proving_ground_exam.market.parameters import SCENARIO_DIR
    from src.config import DEFAULT_POLICY_PATH
    from src.proving_ground.sensitivity import apply_sensitivity, canonical_sha256, load_sensitivity

    policy_path = engine_policy_path or DEFAULT_POLICY_PATH
    policy = load_policy_overlay(policy_path)
    scenario_hash = hashlib.sha256()
    for name in names:
        scenario_hash.update(name.encode())
        scenario_hash.update((SCENARIO_DIR / f"{name}.yaml").read_bytes())
    calibration_file = calibration_path or CALIBRATION_PATH
    file_sha = _sha256_file(calibration_file)
    sensitivity_label = None
    sensitivity_sha = None
    calibration_sha = file_sha
    if sensitivity_path is not None:
        spec = load_sensitivity(sensitivity_path)
        sensitivity_label = str(spec["label"])
        sensitivity_sha = _sha256_file(sensitivity_path)
        calibration_sha = canonical_sha256(apply_sensitivity(load_calibration(calibration_file), spec))
    effective = hashlib.sha256(
        json.dumps(policy, sort_keys=True, default=str).encode()
    ).hexdigest()
    return {
        "scenarios": names,
        "seeds": seeds,
        "policies": list(policies),
        "max_days": max_days,
        "incremental": incremental,
        # Retention changes whether recommendation histories and choice traces
        # exist for diagnosis. It must be part of resume identity even though
        # it does not change the score.
        "retained_scenarios": sorted(retained_scenarios or []),
        **_git_provenance(),
        "calibration_sha256": calibration_sha,
        "calibration_file_sha256": file_sha,
        "calibration_path": str(calibration_file),
        "calibration_version": int(load_calibration(calibration_file).get("version", 1) or 1),
        # None = recommendation quality (every price goes live). A number = the
        # production-faithful mode with that daily human approval rate.
        "approval_rate": approval_rate,
        "sensitivity_label": sensitivity_label,
        "sensitivity_sha256": sensitivity_sha,
        "scenarios_sha256": scenario_hash.hexdigest(),
        "engine_policy_path": str(policy_path),
        "engine_policy_sha256": _sha256_file(policy_path),
        "engine_policy_effective_sha256": effective,
        # Learning models are refused unless a candidate run asks for them.
        "models_allowed": allow_models,
        "models_enabled": sorted(
            name for name, spec in (policy.get("models") or {}).items()
            if isinstance(spec, dict) and spec.get("enabled")
        ),
    }


def _check_disk(output_dir: Path, jobs: list[Job]) -> None:
    import shutil

    need = sum(
        _DB_BYTES.get(job[2], _DB_BYTES_OTHER) for job in jobs if job[6]
    )
    if not need:
        return
    free = shutil.disk_usage(output_dir).free
    if free < need + _DISK_HEADROOM:
        raise RuntimeError(
            f"retaining {sum(1 for job in jobs if job[6])} job databases needs about "
            f"{need / 1e9:.0f} GB plus {_DISK_HEADROOM / 1e9:.0f} GB headroom; "
            f"{free / 1e9:.0f} GB free. Retain fewer scenarios (--retain-dbs normal)."
        )


def _load_checkpoint(path: Path) -> dict[tuple[str, int, str], MarketResult]:
    done: dict[tuple[str, int, str], MarketResult] = {}
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        result = MarketResult(**json.loads(line))
        done[(result.scenario, result.seed, result.policy)] = result
    return done


def _run_jobs(
    jobs: list[Job],
    *,
    workers: int,
    output_dir: Path,
    config: dict[str, Any],
    resume: bool,
    argv: list[str] | None,
) -> list[MarketResult]:
    """One market simulation may run. Databases and logs stay outside iCloud."""
    assert_outside_icloud(output_dir)
    if config.get("models_enabled") and not config.get("models_allowed"):
        raise RuntimeError(
            "market sim refuses a policy with learning models enabled: "
            + ", ".join(config["models_enabled"])
            + " (pass --allow-models to evaluate a model candidate on purpose)"
        )
    from src.proving_ground.run_lock import market_run_lock

    with market_run_lock(output_dir, argv):
        return _execute_jobs(
            jobs, workers=workers, output_dir=output_dir, config=config, resume=resume, argv=argv,
        )


def _execute_jobs(
    jobs: list[Job],
    *,
    workers: int,
    output_dir: Path,
    config: dict[str, Any],
    resume: bool,
    argv: list[str] | None,
) -> list[MarketResult]:
    """Run jobs, appending each result to a checkpoint so a crash loses one job, not the board.

    The first failed job stops the run: queued jobs are cancelled, the failure
    is written to failure.json, and the exception propagates.
    """
    import platform
    import sys
    import time
    import traceback
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from datetime import datetime, timezone

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / CHECKPOINT
    config_path = output_dir / RUN_CONFIG
    done = _load_checkpoint(checkpoint)
    if done and not resume:
        raise FileExistsError(
            f"{checkpoint} already holds {len(done)} results; use a fresh --output-dir or --resume"
        )
    if resume and config_path.exists():
        previous = json.loads(config_path.read_text(encoding="utf-8"))["config"]
        drift = sorted(
            key for key in config
            if key not in _RESUME_IGNORE and previous.get(key) != config[key]
        )
        if drift:
            raise ValueError(f"cannot resume: run config changed since the checkpoint: {drift}")
    started = datetime.now(timezone.utc)
    config_path.write_text(
        json.dumps(
            {
                "config": config,
                "argv": argv,
                "python": sys.version,
                "platform": platform.platform(),
                "workers": workers,
                "started_at": started.isoformat(),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (output_dir / FAILURE).unlink(missing_ok=True)
    todo = [job for job in jobs if (job[0], job[1], job[2]) not in done]
    _check_disk(output_dir, todo)
    results = [done[key] for key in done if key in {(j[0], j[1], j[2]) for j in jobs}]
    clock = time.monotonic()
    total = len(jobs)

    def record(result: MarketResult) -> None:
        results.append(result)
        with checkpoint.open("a", encoding="utf-8") as handle:
            # Key order is kept: scores order becomes the scoreboard column order.
            handle.write(json.dumps(asdict(result)) + "\n")
        finished = len(results)
        ran = finished - (total - len(todo))
        if ran == 1 or finished % 10 == 0 or finished == total:
            elapsed = time.monotonic() - clock
            eta = elapsed / ran * (total - finished) if ran else 0.0
            print(
                f"market jobs {finished}/{total} elapsed {elapsed / 60:.1f}m eta {eta / 60:.0f}m",
                flush=True,
            )

    def fail(job: Job, exc: BaseException) -> None:
        (output_dir / FAILURE).write_text(
            json.dumps(
                {
                    "job": {"scenario": job[0], "seed": job[1], "policy": job[2]},
                    "error": repr(exc),
                    "traceback": "".join(traceback.format_exception(exc)),
                    "completed": len(results),
                    "total": total,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if workers <= 1 or len(todo) <= 1:
        for job in todo:
            try:
                record(_pool_job(job))
            except Exception as exc:
                fail(job, exc)
                raise
    else:
        pool = ProcessPoolExecutor(max_workers=workers)
        try:
            futures = {pool.submit(_pool_job, job): job for job in todo}
            for future in as_completed(futures):
                try:
                    record(future.result())
                except Exception as exc:
                    fail(futures[future], exc)
                    pool.shutdown(wait=True, cancel_futures=True)
                    raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
    finished_at = datetime.now(timezone.utc)
    meta = json.loads(config_path.read_text(encoding="utf-8"))
    meta.update(
        {
            "finished_at": finished_at.isoformat(),
            "elapsed_seconds_this_invocation": round(time.monotonic() - clock, 1),
            "expected_jobs": total,
            "completed_jobs": len(results),
            "resumed_jobs": total - len(todo),
        }
    )
    config_path.write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    return results


def _retains(retain_dbs: bool | Collection[str], scenario: str) -> bool:
    if isinstance(retain_dbs, bool):
        return retain_dbs
    return scenario in retain_dbs


def _provenance(output_dir: Path) -> dict[str, Any]:
    return json.loads((output_dir / RUN_CONFIG).read_text(encoding="utf-8"))


def run_grid(
    scenario_name: str,
    seeds: int,
    policies: tuple[str, ...],
    *,
    workers: int,
    output_dir: Path,
    max_days: int | None = None,
    incremental: bool = False,
    retain_dbs: bool | Collection[str] = False,
    engine_policy_path: Path | None = None,
    sensitivity_path: Path | None = None,
    resume: bool = False,
    argv: list[str] | None = None,
    calibration_path: Path | None = None,
    approval_rate: float | None = None,
    allow_models: bool = False,
) -> dict[str, str]:
    """One scoreboard covering every listed policy. Jobs share a process pool."""
    names = scenario_names(scenario_name)
    policy_arg = str(engine_policy_path) if engine_policy_path else None
    sensitivity_arg = str(sensitivity_path) if sensitivity_path else None
    calibration_arg = str(calibration_path) if calibration_path else None
    if approval_rate is not None and not 0.0 <= approval_rate <= 1.0:
        raise ValueError("approval_rate must be between 0 and 1")
    jobs: list[Job] = [
        (name, seed, policy, str(output_dir), max_days, incremental,
         _retains(retain_dbs, name), policy_arg, sensitivity_arg, calibration_arg, approval_rate)
        for policy in policies
        for name in names
        for seed in range(1, seeds + 1)
    ]
    retained_scenarios: Collection[str] | None
    if retain_dbs is True:
        retained_scenarios = names
    elif isinstance(retain_dbs, Collection) and "all" in retain_dbs:
        retained_scenarios = names
    elif isinstance(retain_dbs, Collection):
        retained_scenarios = retain_dbs
    else:
        retained_scenarios = None
    config = run_config(
        names=names, seeds=seeds, policies=policies, max_days=max_days,
        incremental=incremental, engine_policy_path=engine_policy_path,
        sensitivity_path=sensitivity_path,
        retained_scenarios=retained_scenarios,
        calibration_path=calibration_path,
        approval_rate=approval_rate,
        allow_models=allow_models,
    )
    results = _run_jobs(
        jobs, workers=workers, output_dir=output_dir, config=config, resume=resume, argv=argv,
    )
    results.sort(key=lambda item: (item.scenario, item.policy, item.seed))
    return write_scoreboard(results, output_dir, provenance=_provenance(output_dir))


def run_pool(
    scenario_name: str,
    seeds: int,
    policy: str,
    *,
    workers: int,
    output_dir: Path,
    max_days: int | None = None,
    incremental: bool = False,
    retain_dbs: bool | Collection[str] = False,
    engine_policy_path: Path | None = None,
    sensitivity_path: Path | None = None,
    resume: bool = False,
    argv: list[str] | None = None,
    calibration_path: Path | None = None,
    approval_rate: float | None = None,
) -> dict[str, str]:
    paths = run_grid(
        scenario_name, seeds, (policy,), workers=workers, output_dir=output_dir,
        max_days=max_days, incremental=incremental, retain_dbs=retain_dbs,
        engine_policy_path=engine_policy_path, sensitivity_path=sensitivity_path,
        resume=resume, argv=argv, calibration_path=calibration_path, approval_rate=approval_rate,
    )
    return paths
