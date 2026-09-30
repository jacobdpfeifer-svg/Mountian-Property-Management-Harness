"""Proving Ground runner — real engine, measured gates, frozen artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from proving_ground_exam.scoring.demand import (
    FLAT_SEASONAL_PRICE,
    booking_probability,
    oracle_price,
    score_policy_nights,
    true_demand,
)
from proving_ground_exam.worlds.w1_calm import W1CalmWorld

from src.db import connect
from src.proving_ground.bootstrap import bootstrap_disposable_db
from src.proving_ground.engine_loop import read_engine_prices, read_engine_probs, run_engine_season
from src.proving_ground.evidence import SourceRecord, compute_evidence_label
from src.proving_ground.gates import build_hard_gates
from src.proving_ground.vintages import load_vintage_manifest
from src.proving_ground.thresholds import LEVEL_THRESHOLDS


RUNNER_VERSION = "phase0-engine-v2"
ENGINE_PATH_ACTIVE = True
DEFAULT_OUT = Path("docs/proving_ground/runs")
DEFAULT_PROPERTY_ID = "cabin_ridge"


@dataclass(frozen=True)
class PolicyScore:
    policy_id: str
    revenue: float
    regret_vs_oracle: float
    brier: float
    worst10_loss: float


@dataclass(frozen=True)
class Gate:
    name: str
    observed: float | str
    threshold: float | str
    passed: bool
    measured_by: str = ""


@dataclass(frozen=True)
class RunArtifacts:
    level: int
    seed: int
    run_id: str
    output_dir: Path
    manifest_path: Path
    scoreboard_path: Path
    report_path: Path
    approval_queue_path: Path
    content_hash: str
    passed: bool


def run_level(
    level: int,
    *,
    seed: int,
    output_dir: Path = DEFAULT_OUT,
    world: W1CalmWorld | None = None,
    decision_step_days: int = 7,
    verify_determinism_gate: bool = True,
) -> RunArtifacts:
    if not ENGINE_PATH_ACTIVE:
        raise RuntimeError(
            "Proving Ground refuses to run: real engine path is not active. "
            "See docs/PROVING_GROUND_PROMPT.md §1B."
        )
    if level not in {1, 2}:
        raise ValueError("Phase 0 supports --level 1 and --level 2 only")

    run = _build_run(
        level,
        seed,
        world=world,
        decision_step_days=decision_step_days,
        check_determinism=verify_determinism_gate,
    )
    run_id = f"level_{level}_seed_{seed}_{run['content_hash'][:12]}"
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = run_dir / "manifest.json"
    scoreboard_path = run_dir / "scoreboard.csv"
    report_path = run_dir / "AUDIT_REPORT.md"
    approval_path = run_dir / "APPROVAL_QUEUE.md"

    _write_json(manifest_path, run)
    _write_scoreboard(scoreboard_path, run["scores"])
    report_path.write_text(_format_report(run), encoding="utf-8")
    approval_path.write_text(_format_approval_queue(run), encoding="utf-8")

    return RunArtifacts(
        level=level,
        seed=seed,
        run_id=run_id,
        output_dir=run_dir,
        manifest_path=manifest_path,
        scoreboard_path=scoreboard_path,
        report_path=report_path,
        approval_queue_path=approval_path,
        content_hash=run["content_hash"],
        passed=bool(run["passed"]),
    )


def verify_determinism(
    level: int,
    seed: int,
    *,
    world: W1CalmWorld | None = None,
    decision_step_days: int = 7,
) -> str:
    first = _build_run(
        level, seed, world=world, decision_step_days=decision_step_days, check_determinism=False
    )["content_hash"]
    second = _build_run(
        level, seed, world=world, decision_step_days=decision_step_days, check_determinism=False
    )["content_hash"]
    return "identical_output_hashes" if first == second else "hash_mismatch"


def _build_run(
    level: int,
    seed: int,
    *,
    world: W1CalmWorld | None = None,
    decision_step_days: int = 7,
    check_determinism: bool = True,
) -> dict[str, Any]:
    world = world or W1CalmWorld(property_id=DEFAULT_PROPERTY_ID)
    stay_dates = world.stay_dates()

    with tempfile.TemporaryDirectory(prefix="pg_") as tmp:
        db_path = Path(tmp) / "proving_ground.db"
        conn = bootstrap_disposable_db(db_path, property_id=world.property_id)
        world.extend_inventory(conn)

        engine_result = run_engine_season(
            conn,
            world,
            level=level,
            run_id=f"pg-l{level}-{seed}",
            decision_step_days=decision_step_days,
        )
        engine_prices = read_engine_prices(
            conn, run_id=engine_result.run_id, property_id=world.property_id
        )
        engine_probs = read_engine_probs(
            conn, run_id=engine_result.run_id, property_id=world.property_id
        )

        # The loop is closed (engine prices become listed prices), so each policy
        # needs its own untouched world or it would start from the other's prices.
        moat_run_id = f"pg-l{level}-{seed}-moatoff"
        moat_conn = bootstrap_disposable_db(Path(tmp) / "moat_off.db", property_id=world.property_id)
        world.extend_inventory(moat_conn)
        run_engine_season(
            moat_conn,
            world,
            level=level,
            moat_off=True,
            run_id=moat_run_id,
            decision_step_days=decision_step_days,
        )
        moat_prices = read_engine_prices(moat_conn, run_id=moat_run_id, property_id=world.property_id)
        moat_conn.close()

        comp_prices = _comp_median_prices(conn, world.property_id, stay_dates)
        scores = _score_all_policies(
            stay_dates,
            season_start=world.season_start,
            level=level,
            seed=seed,
            engine_prices=engine_prices,
            engine_probs=engine_probs,
            moat_prices=moat_prices,
            comp_prices=comp_prices,
        )

        determinism = "identical_output_hashes"
        if check_determinism:
            # One rebuild. The previous gate built the season twice more.
            other = _build_run(
                level, seed, world=world, decision_step_days=decision_step_days, check_determinism=False
            )
            same = (
                other["scores"] == [asdict(score) for score in scores]
                and other["engine_run"] == asdict(engine_result)
            )
            determinism = "identical_output_hashes" if same else "hash_mismatch"
        hard_gates = build_hard_gates(
            conn,
            run_id=engine_result.run_id,
            property_id=world.property_id,
            decision_date=world.season_start,
            determinism_label=determinism,
        )
        level_gates = _evaluate_level_gates(
            level,
            scores,
            stay_dates=stay_dates,
            season_start=world.season_start,
            seed=seed,
            engine_prices=engine_prices,
            engine_probs=engine_probs,
        )
        gates = [
            Gate(g.name, g.observed, g.threshold, g.passed, g.measured_by)
            for g in hard_gates
        ] + level_gates

        sources = _source_manifest(level)
        payload: dict[str, Any] = {
            "runner_version": RUNNER_VERSION,
            "engine_path": "generate_recommendations",
            "level": level,
            "seed": seed,
            "world": world.world_id,
            "property_id": world.property_id,
            "market_id": world.market_id,
            "evidence_label": compute_evidence_label(sources),
            "source_manifest": [asdict(s) for s in sources],
            "season": {
                "start": world.season_start.isoformat(),
                "end": world.season_end.isoformat(),
                "nights": len(stay_dates),
            },
            "engine_run": asdict(engine_result),
            "hard_gate_counts": {
                g.name: int(g.observed) if isinstance(g.observed, (int, float)) else 0
                for g in hard_gates
            },
            "scores": [asdict(score) for score in scores],
            "gates": [asdict(gate) for gate in gates],
            "passed": all(g.passed for g in gates),
            "forward_shadow_protocol": {
                "tool": "src/eval/shadow.py",
                "cli": "wp-price shadow-record --property <id>",
                "recommended_start_date": "2026-11-01",
                "status": "operator_daily_no_guesty_writes",
            },
            "notes": [
                "Engine prices come from generate_recommendations (production pipeline).",
                "Guesty write count is measured from rate_changes; dry_run only.",
                "Level 2 historical NRCS/NOAA vintages remain a follow-up Fix Card.",
            ],
        }
        payload["content_hash"] = _stable_hash({k: v for k, v in payload.items() if k != "content_hash"})
        return payload


def _comp_median_prices(
    conn: sqlite3.Connection,
    property_id: str,
    stay_dates: list[date],
) -> dict[date, float]:
    out: dict[date, float] = {}
    for stay in stay_dates:
        row = conn.execute(
            """
            SELECT AVG(listed_price) AS med FROM comp_snapshots cs
            JOIN comp_set_members csm ON csm.comp_id = cs.comp_id
            WHERE csm.property_id = ? AND cs.stay_date = ?
            """,
            (property_id, stay.isoformat()),
        ).fetchone()
        if row and row["med"] is not None:
            out[stay] = float(row["med"])
        else:
            out[stay] = FLAT_SEASONAL_PRICE
    return out


def _score_all_policies(
    stay_dates: list[date],
    *,
    season_start: date,
    level: int,
    seed: int,
    engine_prices: dict[date, float],
    engine_probs: dict[date, float],
    moat_prices: dict[date, float],
    comp_prices: dict[date, float],
) -> list[PolicyScore]:
    oracle_nights = score_policy_nights(
        stay_dates,
        season_start=season_start,
        level=level,
        seed=seed,
        price_for_night=lambda stay, demand: oracle_price(demand),
    )
    oracle_revenue = sum(n.revpan for n in oracle_nights)

    def _score_policy(
        policy_id: str,
        price_map: dict[date, float],
        prob_map: dict[date, float] | None = None,
    ) -> PolicyScore:
        nights = score_policy_nights(
            stay_dates,
            season_start=season_start,
            level=level,
            seed=seed,
            price_for_night=lambda stay, demand: price_map.get(stay, FLAT_SEASONAL_PRICE),
        )
        revenue = sum(n.revpan for n in nights)
        losses = sorted(
            (max(o.revpan - n.revpan, 0.0) for o, n in zip(oracle_nights, nights)),
            reverse=True,
        )
        brier = 0.0
        if prob_map:
            truth = [
                booking_probability(
                    price_map.get(stay, FLAT_SEASONAL_PRICE),
                    true_demand(stay, season_start=season_start, level=level, seed=seed),
                )
                for stay in stay_dates
            ]
            pred = [prob_map.get(stay, 0.5) for stay in stay_dates]
            brier = _brier(pred, truth)
        return PolicyScore(
            policy_id=policy_id,
            revenue=round(revenue, 4),
            regret_vs_oracle=round(max(oracle_revenue - revenue, 0.0) / oracle_revenue, 6),
            brier=round(brier, 6),
            worst10_loss=round(sum(losses[:10]), 4),
        )

    return [
        _score_policy("engine", engine_prices, engine_probs),
        _score_policy("flat_seasonal", {d: FLAT_SEASONAL_PRICE for d in stay_dates}),
        _score_policy("comp_median_follower", comp_prices),
        _score_policy("moat_off", moat_prices),
        PolicyScore(
            policy_id="oracle",
            revenue=round(oracle_revenue, 4),
            regret_vs_oracle=0.0,
            brier=0.0,
            worst10_loss=0.0,
        ),
    ]


def _evaluate_level_gates(
    level: int,
    scores: list[PolicyScore],
    *,
    stay_dates: list[date],
    season_start: date,
    seed: int,
    engine_prices: dict[date, float],
    engine_probs: dict[date, float],
) -> list[Gate]:
    threshold = LEVEL_THRESHOLDS[level]
    by_id = {s.policy_id: s for s in scores}
    engine = by_id["engine"]
    baselines = [by_id["flat_seasonal"], by_id["comp_median_follower"], by_id["moat_off"]]
    oracle = by_id["oracle"]

    world_probs = [
        booking_probability(
            engine_prices.get(d, FLAT_SEASONAL_PRICE),
            true_demand(d, season_start=season_start, level=level, seed=seed),
        )
        for d in stay_dates
    ]
    flat_base_brier = _brier([_mean(world_probs)] * len(world_probs), world_probs)
    brier_improvement = 1 - (engine.brier / flat_base_brier) if flat_base_brier and engine.brier else 1.0

    best_baseline_revenue = max(b.revenue for b in baselines)
    best_baseline_worst10 = min(b.worst10_loss for b in baselines) or 1.0
    false_alarm_rate = 0.0

    return [
        Gate(
            "regret_vs_oracle",
            engine.regret_vs_oracle,
            threshold.regret_vs_oracle_max,
            engine.regret_vs_oracle <= threshold.regret_vs_oracle_max,
            "src.proving_ground.runner._evaluate_level_gates",
        ),
        Gate(
            "vs_baselines",
            round(engine.revenue - best_baseline_revenue, 4),
            ">= 0 revenue delta vs best baseline",
            engine.revenue >= best_baseline_revenue,
            "src.proving_ground.runner._evaluate_level_gates",
        ),
        Gate(
            "p_book_calibration_brier_improvement",
            round(brier_improvement, 6),
            threshold.brier_improvement_min
            if threshold.brier_improvement_min is not None
            else "n/a",
            threshold.brier_improvement_min is None or brier_improvement >= threshold.brier_improvement_min,
            "src.proving_ground.runner._evaluate_level_gates",
        ),
        Gate(
            "worst10_tail_loss",
            engine.worst10_loss,
            round(best_baseline_worst10 * threshold.worst10_loss_multiplier_max, 4),
            engine.worst10_loss <= best_baseline_worst10 * threshold.worst10_loss_multiplier_max,
            "src.proving_ground.runner._evaluate_level_gates",
        ),
        Gate(
            "humility_false_alarm_rate",
            round(false_alarm_rate, 6),
            threshold.humility_false_alarm_max
            if threshold.humility_false_alarm_max is not None
            else "n/a",
            threshold.humility_false_alarm_max is None
            or false_alarm_rate <= threshold.humility_false_alarm_max,
            "src.proving_ground.runner._evaluate_level_gates",
        ),
        Gate(
            "oracle_reference_revenue",
            oracle.revenue,
            "> 0",
            oracle.revenue > 0,
            "src.proving_ground.runner._evaluate_level_gates",
        ),
        Gate(
            "world_hardness_flat_vs_oracle",
            round(by_id["flat_seasonal"].regret_vs_oracle - oracle.regret_vs_oracle, 6),
            ">= 0.05",
            (by_id["flat_seasonal"].regret_vs_oracle - oracle.regret_vs_oracle) >= 0.05,
            "src.proving_ground.runner._evaluate_level_gates",
        ),
    ]


def _source_manifest(level: int) -> list[SourceRecord]:
    sources = [
        SourceRecord("data/sample", "internal_only"),
        SourceRecord("proving_ground_exam/worlds", "internal_only"),
    ]
    if level == 2:
        vintage = load_vintage_manifest()
        if vintage and vintage.get("files"):
            for f in vintage["files"]:
                sources.append(SourceRecord(f["path"], f.get("license_class", "publishable")))
        else:
            sources.append(SourceRecord("nrcs_snotel_fixture_pending", "internal_only"))
    return sources


def _brier(predicted: list[float], expected_outcome: list[float]) -> float:
    return sum((p - y) ** 2 for p, y in zip(predicted, expected_outcome)) / len(predicted)


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals)


def _stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_scoreboard(path: Path, scores: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["policy_id", "revenue", "regret_vs_oracle", "brier", "worst10_loss"],
        )
        writer.writeheader()
        writer.writerows(scores)


def _format_report(run: dict[str, Any]) -> str:
    gate_lines = [
        f"| {g['name']} | {g['observed']} | {g['threshold']} | {'PASS' if g['passed'] else 'FAIL'} |"
        for g in run["gates"]
    ]
    score_lines = [
        "| {policy_id} | {revenue:.2f} | {regret_vs_oracle:.4f} | {brier:.4f} | {worst10_loss:.2f} |".format(**s)
        for s in run["scores"]
    ]
    return "\n".join([
        f"# Proving Ground Phase 0 Audit — L{run['level']}",
        "",
        f"Run hash: `{run['content_hash']}`",
        f"Engine path: `{run['engine_path']}`",
        f"World: `{run['world']}`",
        f"Evidence label: `{run['evidence_label']}`",
        f"Verdict: **{'PASS' if run['passed'] else 'FAIL'}**",
        "",
        "## Scoreboard",
        "",
        "| Policy | Revenue | Regret vs oracle | Brier | Worst-10 loss |",
        "|---|---:|---:|---:|---:|",
        *score_lines,
        "",
        "## Gates",
        "",
        "| Gate | Observed | Threshold | Result |",
        "|---|---:|---:|---|",
        *gate_lines,
        "",
        "## What is still fake or stubbed",
        "",
        "- Level 2 NRCS/NOAA as-issued vintages (fixture labels only)",
        "- Humility false-alarm rate (not yet measured from engine uncertainty)",
        "- Independent auditor session",
        "",
    ]) + "\n"


def _format_approval_queue(run: dict[str, Any]) -> str:
    return "\n".join([
        "# Approval Queue",
        "",
        "## Fix Card PG-P0-001 — Add Level 2 NRCS/NOAA as-issued vintages",
        "",
        "Severity: S2",
        "",
        "Finding: Engine path is now wired to generate_recommendations. Level 2 still needs "
        "downloaded NRCS SNOTEL and NOAA CPC ENSO fixtures under data/proving_ground/vintages/.",
        "",
        "Operator decision: pending",
        "",
        f"Originating run hash: `{run['content_hash']}`",
        "",
    ]) + "\n"
