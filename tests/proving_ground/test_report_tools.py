"""Regression tests for the 2026-10-14 audit fixes to the reporting tools.

Each test pins one way a report number was wrong or could silently go wrong.
"""

from __future__ import annotations

import ast
import csv
import importlib.util
import sqlite3
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------- decomposer


def test_at_ceiling_survives_price_rounding():
    decomp = _script("decompose_market_sim")
    # A $911.95 ceiling rounded to $909: the old $0.50 test called this "not at ceiling".
    assert decomp._at_ceiling(909.0, 911.95)
    assert not decomp._at_ceiling(850.0, 911.95)
    assert decomp._at_floor(331.0, 330.0)
    assert not decomp._at_ceiling(None, 911.95)


def test_model_wants_ceiling_reads_the_pre_bound_price():
    decomp = _script("decompose_market_sim")
    assert decomp._model_wants_ceiling({"model_price": 1200.0, "ceiling_price": 1035.0})
    assert not decomp._model_wants_ceiling({"model_price": 900.0, "ceiling_price": 1035.0})
    assert not decomp._model_wants_ceiling({"model_price": None, "ceiling_price": 1035.0})


def _job_db(path: Path, *, booked_price: float | None, engine: bool) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE nightly_inventory (property_id TEXT, stay_date TEXT, status TEXT, "
        "listed_price REAL, booked_price REAL, booked_at TEXT)"
    )
    status = "booked" if booked_price is not None else "available"
    conn.execute(
        "INSERT INTO nightly_inventory VALUES ('cloud_9', '2027-02-13', ?, 1000, ?, ?)",
        (status, booked_price, "2027-01-20" if booked_price is not None else None),
    )
    if engine:
        conn.execute(
            "CREATE TABLE price_recommendations (run_id TEXT, property_id TEXT, stay_date TEXT, "
            "final_price REAL, ceiling_price REAL, floor_price REAL, model_price REAL, guardrail_action TEXT)"
        )
        conn.execute(
            "INSERT INTO price_recommendations VALUES "
            "('sim-2027-01-20', 'cloud_9', '2027-02-13', 1029, 1035, 440, 1400, NULL)"
        )
    conn.commit()
    conn.close()


def _board(path: Path, rows: list[tuple[str, str, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "seed", "policy", "revenue"])
        for policy, seed, revenue in rows:
            writer.writerow(["normal", seed, policy, revenue])


def test_decomposer_reads_right_policy_from_another_run_and_reconciles_both(tmp_path: Path):
    decomp = _script("decompose_market_sim")
    cand, bench = tmp_path / "cand", tmp_path / "bench"
    (cand / "dbs").mkdir(parents=True)
    (bench / "dbs").mkdir(parents=True)
    _job_db(cand / "dbs" / "normal_engine_1.db", booked_price=1029.0, engine=True)
    _job_db(bench / "dbs" / "normal_flat_1.db", booked_price=900.0, engine=False)
    _board(cand / "scoreboard.csv", [("engine", "1", 1029.0)])
    _board(bench / "scoreboard.csv", [("flat", "1", 900.0)])

    result = decomp.decompose(cand, "normal", "engine", "flat", right_dir=bench)

    assert result["totals"]["revenue_delta"] == 129.0
    assert result["scoreboard_check"]["engine"]["difference"] == 0.0
    assert result["scoreboard_check"]["flat"]["difference"] == 0.0
    season = result["engine_recommendations_by_season"]["peak_ski"]
    assert season["share_at_ceiling"] == 1.0
    assert season["share_model_wants_ceiling"] == 1.0
    assert "none" in season["guardrail"]


# ------------------------------------------------------------- paired script


def _scoreboard(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _row(scenario: str, seed: int, policy: str, revenue: float, guards: str = "{}") -> dict[str, str]:
    total = sum(v for k, v in ast.literal_eval(guards).items() if k)
    return {
        "scenario": scenario, "seed": str(seed), "policy": policy, "revenue": str(revenue),
        "revpan": "1", "occupancy": "0.5", "adr": "800", "occupancy_peak": "0.5",
        "guardrail_triggers": str(total), "guardrail_by_action": guards,
    }


def test_paired_refuses_a_board_that_mixes_scenarios(tmp_path: Path):
    paired = _script("paired_market_sim")
    left, right = tmp_path / "left.csv", tmp_path / "right.csv"
    _scoreboard(left, [_row("normal", 6, "engine", 100.0)])
    _scoreboard(right, [_row("normal", 6, "flat", 90.0), _row("price_war", 6, "flat", 10.0)])
    with pytest.raises(ValueError, match="pass --scenario"):
        paired.paired_report(left, right, seeds_from=6, seeds_to=None, right_policy="flat")
    result = paired.paired_report(
        left, right, seeds_from=6, seeds_to=None, right_policy="flat", scenario="normal"
    )
    assert result["combined_minus_default"]["revenue"]["mean"] == 10.0


def test_paired_reports_guardrails_by_action_with_none_named(tmp_path: Path):
    paired = _script("paired_market_sim")
    left, right = tmp_path / "cand.csv", tmp_path / "default.csv"
    _scoreboard(left, [_row("normal", 6, "engine", 120.0, "{'': 980, 'clamped_increase': 20}")])
    _scoreboard(right, [_row("normal", 6, "engine", 100.0, "{'': 950, 'sanity_floor': 50}")])
    result = paired.paired_report(left, right, seeds_from=6, seeds_to=None)

    by_action = result["guardrail_by_action_delta"]
    assert "" not in by_action
    assert by_action["none"]["mean"] == 30.0
    assert by_action["sanity_floor"]["mean"] == -50.0
    assert by_action["clamped_increase"]["seeds_left_higher"] == 1
    assert result["guardrail_triggers_delta"]["mean"] == -30.0
    assert result["guardrail_rate_per_1000_recs"]["sanity_floor"]["right_mean"] == 50.0


# ------------------------------------------------------------ golden boards


def test_regress_compare_flags_moved_revenue_and_hash(tmp_path: Path):
    regress = _script("regress_market_sim")
    golden, fresh = tmp_path / "golden.csv", tmp_path / "fresh.csv"
    base = {"scenario": "normal", "seed": "1", "policy": "engine", "revenue": "100.00",
            "content_hash": "abc", "guardrail_triggers": "5", "guardrail_by_action": "{}"}
    _scoreboard(golden, [base])
    _scoreboard(fresh, [base])
    assert regress.compare(golden, fresh) == []
    _scoreboard(fresh, [{**base, "revenue": "100.01", "content_hash": "abd"}])
    problems = regress.compare(golden, fresh)
    assert any("revenue" in p for p in problems)
    assert any("content_hash" in p for p in problems)


# ----------------------------------------------------------- rate-cap check


def test_preflight_rate_check_fails_a_cap_below_real_listed_prices(tmp_path: Path, monkeypatch):
    preflight = _script("production_preflight")
    card = tmp_path / "rate_card.yaml"
    card.write_text(yaml.safe_dump({"homes": {"cloud_9": {"by_season": {
        "peak_ski": {"listed_p25": 1653.0}, "holiday": {"listed_p25": 3178.0},
    }}}}))
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setattr(preflight, "load_policy", lambda: {
        "ceiling": {"property_season_ceiling": {"cloud_9": {"peak_ski": 1035}}}
    })
    errors, note = preflight.check_rate_caps(card)
    assert len(errors) == 2 and "cut real rates" in errors[0]
    assert "2 cap/season pairs" in note

    monkeypatch.setattr(preflight, "load_policy", lambda: {
        "ceiling": {"property_season_ceiling": {"cloud_9": {"peak_ski": 4000}}}
    })
    assert preflight.check_rate_caps(card)[0] == []


def test_preflight_rate_check_skips_without_the_local_export(tmp_path: Path, monkeypatch):
    preflight = _script("production_preflight")
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    errors, note = preflight.check_rate_caps(tmp_path / "missing.yaml")
    assert errors == [] and "SKIPPED" in note


# ------------------------------------------------------------ rate card export


def test_rate_card_export_reads_no_guest_fields(tmp_path: Path):
    export = _script("export_rate_card")
    db = tmp_path / "op.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE properties (property_id TEXT, name TEXT, bedrooms INT, max_occupancy INT,
            base_ceiling_rate REAL, min_floor_rate REAL, max_ceiling_rate REAL);
        CREATE TABLE nightly_inventory (property_id TEXT, stay_date TEXT, listed_price REAL,
            booked_price REAL, status TEXT, channel TEXT, reservation_id TEXT, guest_count INT);
        CREATE TABLE comps (comp_id TEXT, name TEXT, bedrooms INT, sleeps INT);
        CREATE TABLE comp_set_members (property_id TEXT, comp_id TEXT);
        CREATE TABLE comp_snapshots (comp_id TEXT, stay_date TEXT, listed_price REAL, scrape_status TEXT);
        INSERT INTO properties VALUES ('cloud_9', 'Cloud 9', 6, 16, 1041, 440, 5571);
        INSERT INTO nightly_inventory VALUES ('cloud_9', '2026-12-24', 3400, 3300, 'booked', 'airbnb', 'R-SECRET', 12);
        INSERT INTO nightly_inventory VALUES ('cloud_9', '2027-02-10', 2100, NULL, 'available', NULL, NULL, NULL);
        INSERT INTO comps VALUES ('c1', 'Comp', 6, 18);
        INSERT INTO comp_set_members VALUES ('cloud_9', 'c1');
        INSERT INTO comp_snapshots VALUES ('c1', '2027-02-10', 2000, 'ok');
        INSERT INTO comp_snapshots VALUES ('c1', '2027-02-11', NULL, 'unavailable');
        """
    )
    conn.commit()
    conn.close()

    result = export.export(db, start="2026-11-01", end="2027-04-30")
    text = yaml.safe_dump(result)
    assert "R-SECRET" not in text
    home = result["homes"]["cloud_9"]["by_season"]
    assert home["holiday"]["booked_adr"] == 3300.0
    assert home["peak_ski"]["listed_median"] == 2100.0
    assert result["comps"]["c1"]["by_season"]["peak_ski"]["unavailable_share"] == 0.5


# ------------------------------------------------------------------ L1 runner


def test_l1_unmeasured_gate_is_not_a_pass_and_baselines_have_no_brier(tmp_path: Path):
    from src.proving_ground import run_level

    artifacts = run_level(1, seed=20260925, output_dir=tmp_path, verify_determinism_gate=False)
    report = artifacts.report_path.read_text()
    assert "| humility_false_alarm_rate | not_measured | 0.05 | NOT MEASURED |" in report
    assert not artifacts.passed
    with artifacts.scoreboard_path.open(newline="") as handle:
        rows = {row["policy_id"]: row for row in csv.DictReader(handle)}
    assert rows["engine"]["brier"] != ""
    assert rows["flat_seasonal"]["brier"] == ""
    assert rows["oracle"]["brier"] == ""


# -------------------------------------------------------------- job database


def test_finished_job_database_is_a_single_file(tmp_path: Path):
    from src.proving_ground.market_loop import run_market_job

    db = tmp_path / "job.db"
    run_market_job("normal", 1, "flat", db_path=db, max_days=2)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        conn.close()
    assert not Path(f"{db}-wal").exists()
