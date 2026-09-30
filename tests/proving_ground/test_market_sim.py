"""Shopper-market simulator. Default tests stay on short seasons."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from proving_ground_exam.market.parameters import (
    assert_sources,
    list_scenarios,
    load_calibration,
    load_scenario,
)
from src.db import connect
from src.proving_ground.market_loop import run_market_job, run_pool

HELD_OUT = {"holiday_shift", "den_capacity_cut", "regime_change", "pandemic_collapse"}
ROOT = Path(__file__).resolve().parents[2]

# Fields that must match between a full reprice and incremental repricing.
# run_id and created_at differ by construction.
_REC_FIELDS = (
    "property_id",
    "stay_date",
    "recommended_price",
    "ceiling_price",
    "floor_price",
    "listed_price_at_run",
    "expected_book_prob",
    "expected_revpan",
    "ceiling_confidence",
    "autonomy_level",
    "guardrail_action",
    "reasons",
    "rule_version",
    "model_version",
    "inputs_hash",
    "status",
    "recommended_min_stay",
    "min_stay_source",
    "per_person_nightly",
    "range_low",
    "range_high",
    "evidence_count",
    "model_price",
    "bounded_price",
    "move_cap_price",
    "rounded_price",
    "final_price",
    "weak_ceiling",
    "memory_set_hash",
    "memory_feature_version",
    "memory_claim_refs",
    "memory_counterfactual_price",
)


def test_calibration_values_and_segments_have_sources():
    cal = load_calibration()
    assert_sources(cal)
    assert set(cal["properties"]) == {"summit_haus", "overlook_ridge", "cloud_9"}


def test_calibration_rejects_a_value_without_a_source():
    with pytest.raises(ValueError, match="without source"):
        assert_sources({"arrival_mean": {"value": 3.2}})
    with pytest.raises(ValueError, match="without source"):
        assert_sources({"segments": {"families": {"share": {}}}})


def test_fifteen_scenarios_and_held_out_names():
    names = set(list_scenarios())
    assert len(names) == 15
    held = {name for name in names if load_scenario(name).get("held_out")}
    assert held == HELD_OUT


def test_telluride_portability_file_is_outside_the_fifteen():
    port = ROOT / "proving_ground_exam" / "market" / "portability"
    cal = load_calibration(port / "telluride_calibration.yaml")
    assert cal["market_id"] == "telluride"
    assert cal["season_start"] == "2026-11-26"
    assert "telluride" not in list_scenarios()


def test_simulated_day_books_and_inquiry_does_not(tmp_path: Path):
    db = tmp_path / "book.db"
    result = run_market_job("normal", 1, "flat", db_path=db, max_days=20)
    assert result.scores["confirmed"] >= 1
    assert result.scores["inquiries"] >= 1
    conn = connect(db)
    try:
        booked = conn.execute(
            """
            SELECT reservation_id, property_id, check_in, nights
            FROM reservations WHERE status = 'confirmed'
            """
        ).fetchall()
        assert booked
        for row in booked:
            nights = conn.execute(
                """
                SELECT status, reservation_id FROM nightly_inventory
                WHERE property_id = ? AND stay_date >= ? AND stay_date < date(?, '+' || ? || ' days')
                """,
                (row["property_id"], row["check_in"], row["check_in"], row["nights"]),
            ).fetchall()
            assert len(nights) == row["nights"]
            assert all(night["status"] == "booked" for night in nights)
            assert all(night["reservation_id"] == row["reservation_id"] for night in nights)
        inquiry_blocks = conn.execute(
            "SELECT COUNT(*) AS c FROM nightly_inventory WHERE reservation_id LIKE 'inq-%'"
        ).fetchone()["c"]
        assert inquiry_blocks == 0
        guesty = conn.execute(
            "SELECT COUNT(*) AS c FROM rate_changes WHERE result = 'applied'"
        ).fetchone()["c"]
        assert guesty == 0
    finally:
        conn.close()


def test_same_seed_hashes_match(tmp_path: Path):
    first = run_market_job("normal", 1, "flat", db_path=tmp_path / "a.db", max_days=12)
    second = run_market_job("normal", 1, "flat", db_path=tmp_path / "b.db", max_days=12)
    assert first.content_hash == second.content_hash
    other = run_market_job("normal", 2, "flat", db_path=tmp_path / "c.db", max_days=12)
    assert other.content_hash != first.content_hash


def test_scrape_outage_hides_competitor_prices(tmp_path: Path):
    db = tmp_path / "outage.db"
    run_market_job("scrape_outage", 1, "flat", db_path=db, max_days=4)
    conn = connect(db)
    try:
        rows = conn.execute(
            "SELECT scrape_status, COUNT(*) AS c, SUM(listed_price IS NOT NULL) AS priced FROM comp_snapshots GROUP BY 1"
        ).fetchall()
        assert rows
        assert all(row["scrape_status"] == "failed" for row in rows)
        assert all(row["priced"] == 0 for row in rows)
    finally:
        conn.close()


def test_world_columns_are_a_subset_of_the_live_writers():
    world = (ROOT / "proving_ground_exam/market/world.py").read_text(encoding="utf-8")
    sync = (ROOT / "src/pms/sync.py").read_text(encoding="utf-8")
    scrape = (ROOT / "src/scrape/__init__.py").read_text(encoding="utf-8")
    signals = (ROOT / "src/signals/store.py").read_text(encoding="utf-8")
    assert "reservation_id, property_id, check_in, check_out, nights, status, source" in world
    assert "reservation_id, property_id, listing_id, check_in, check_out, nights" in sync
    assert "comp_id, as_of, stay_date, listed_price, available, scrape_status, source, capture_method" in world
    assert "comp_id, as_of, stay_date, listed_price, available" in scrape
    assert "signal_key, market_id, observed_at, effective_date, horizon_days" in world
    assert "signal_key, market_id, observed_at, effective_date, horizon_days" in signals


def test_exam_package_does_not_import_the_engine():
    script = ROOT / "scripts/check_proving_ground_isolation.py"
    completed = subprocess.run([sys.executable, str(script)], check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "isolation OK" in completed.stdout


def _rec_digest(db: Path) -> str:
    conn = connect(db)
    try:
        runs = conn.execute(
            "SELECT run_id, MIN(id) AS first FROM price_recommendations GROUP BY run_id ORDER BY first"
        ).fetchall()
        assert len(runs) >= 2
        last = runs[-1]["run_id"]
        cols = ", ".join(_REC_FIELDS)
        rows = conn.execute(
            f"SELECT {cols} FROM price_recommendations WHERE run_id = ? ORDER BY property_id, stay_date",
            (last,),
        ).fetchall()
        payload = [tuple(row[name] for name in _REC_FIELDS) for row in rows]
        # Three named property-days must be present, plus the rest of the day.
        wanted = {
            ("summit_haus", "2026-11-15"),
            ("overlook_ridge", "2026-12-25"),
            ("cloud_9", "2027-02-14"),
        }
        found = {(row["property_id"], row["stay_date"]) for row in rows}
        assert wanted <= found
        blob = json.dumps(payload, default=str, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()
    finally:
        conn.close()


def test_incremental_reprice_matches_full_recommendation_fields(tmp_path: Path):
    full = tmp_path / "full.db"
    inc = tmp_path / "inc.db"
    run_market_job("normal", 1, "engine", db_path=full, decision_limit=2)
    run_market_job("normal", 1, "engine", db_path=inc, decision_limit=2, incremental=True)
    assert _rec_digest(full) == _rec_digest(inc)


def test_market_pool_can_retain_job_databases_for_audit(tmp_path: Path):
    output = tmp_path / "retained"
    run_pool("normal", 1, "flat", workers=1, output_dir=output, max_days=2, retain_dbs=True)
    assert (output / "dbs" / "normal_flat_1.db").exists()


def test_market_pool_discards_job_databases_by_default(tmp_path: Path):
    output = tmp_path / "discarded"
    run_pool("normal", 1, "flat", workers=1, output_dir=output, max_days=2)
    assert not (output / "dbs" / "normal_flat_1.db").exists()


def test_market_pool_retains_only_named_scenarios(tmp_path: Path):
    output = tmp_path / "subset"
    run_pool("all", 1, "flat", workers=1, output_dir=output, max_days=1, retain_dbs={"normal"})
    kept = sorted(path.name for path in (output / "dbs").glob("*.db"))
    assert kept == ["normal_flat_1.db"]


def test_market_run_checkpoints_and_records_provenance(tmp_path: Path):
    output = tmp_path / "ckpt"
    paths = run_pool("normal", 2, "flat", workers=1, output_dir=output, max_days=2)
    lines = (output / "results.jsonl").read_text().splitlines()
    assert len(lines) == 2
    provenance = json.loads(Path(paths["manifest"]).read_text())["provenance"]
    assert provenance["completed_jobs"] == provenance["expected_jobs"] == 2
    config = provenance["config"]
    assert config["models_enabled"] == []
    assert len(config["calibration_sha256"]) == 64
    assert config["git_commit"]


def test_market_run_refuses_to_mix_into_a_used_directory(tmp_path: Path):
    output = tmp_path / "used"
    run_pool("normal", 1, "flat", workers=1, output_dir=output, max_days=2)
    with pytest.raises(FileExistsError):
        run_pool("normal", 1, "flat", workers=1, output_dir=output, max_days=2)


def test_market_resume_skips_finished_jobs_and_matches_a_clean_run(tmp_path: Path):
    clean = run_pool("normal", 2, "flat", workers=1, output_dir=tmp_path / "clean", max_days=2)
    partial = tmp_path / "partial"
    run_pool("normal", 1, "flat", workers=1, output_dir=partial, max_days=2)
    # Seed count is part of the config, so widen it the way a crashed run would
    # look: keep the one finished row and let resume do the rest.
    (partial / "run_config.json").unlink()
    resumed = run_pool("normal", 2, "flat", workers=1, output_dir=partial, max_days=2, resume=True)
    provenance = json.loads(Path(resumed["manifest"]).read_text())["provenance"]
    assert provenance["resumed_jobs"] == 1
    assert Path(resumed["csv"]).read_text() == Path(clean["csv"]).read_text()


def test_market_resume_refuses_changed_config(tmp_path: Path):
    output = tmp_path / "drift"
    run_pool("normal", 1, "flat", workers=1, output_dir=output, max_days=2)
    with pytest.raises(ValueError, match="max_days"):
        run_pool("normal", 1, "flat", workers=1, output_dir=output, max_days=3, resume=True)


def test_engine_recommendations_are_keyed_by_decision_day(tmp_path: Path):
    db = tmp_path / "keyed.db"
    run_market_job("normal", 1, "engine", db_path=db, decision_limit=2)
    conn = connect(db)
    try:
        run_ids = [row[0] for row in conn.execute(
            "SELECT DISTINCT run_id FROM price_recommendations ORDER BY run_id"
        )]
    finally:
        conn.close()
    cal = load_calibration()
    assert run_ids[0] == f"sim-{cal['season_start']}"
    assert len(run_ids) == 2


@pytest.mark.slow
def test_two_full_seasons_stay_deterministic(tmp_path: Path):
    first = run_market_job("normal", 1, "flat", db_path=tmp_path / "s1.db")
    second = run_market_job("normal", 1, "flat", db_path=tmp_path / "s2.db")
    assert first.content_hash == second.content_hash
    assert first.scores["confirmed"] > 0


def test_market_run_stops_on_first_failure_and_records_it(tmp_path: Path, monkeypatch):
    from src.proving_ground import market_loop

    def boom(job):
        raise RuntimeError(f"broken {job[0]}/{job[1]}")

    monkeypatch.setattr(market_loop, "_pool_job", boom)
    output = tmp_path / "fails"
    with pytest.raises(RuntimeError, match="broken normal/1"):
        run_pool("normal", 3, "flat", workers=1, output_dir=output, max_days=2)
    failure = json.loads((output / "failure.json").read_text())
    assert failure["job"] == {"scenario": "normal", "seed": 1, "policy": "flat"}
    assert not (output / "scoreboard.csv").exists()


def test_audit_flags_a_missing_seed():
    import importlib.util

    spec = importlib.util.spec_from_file_location("audit_market_sim", ROOT / "scripts" / "audit_market_sim.py")
    audit_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit_mod)
    rows = [
        {"scenario": "normal", "seed": str(seed), "policy": policy, "revenue": "100", "held_out": "False"}
        for seed in (1, 2)
        for policy in ("engine", "flat", "comp_median", "tool")
    ]
    assert audit_mod.audit(rows, expect_seeds=2)["gates"]["complete"]
    result = audit_mod.audit(rows[:-1], expect_seeds=2)
    assert not result["gates"]["complete"]
    assert result["completeness"]["missing"] == ["normal/tool/2"]


def test_audit_can_score_only_unscreened_seeds():
    import importlib.util

    spec = importlib.util.spec_from_file_location("audit_market_sim", ROOT / "scripts" / "audit_market_sim.py")
    audit_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit_mod)
    rows = [
        {"scenario": "normal", "seed": str(seed), "policy": policy, "revenue": str(seed), "held_out": "False"}
        for seed in (1, 2, 3)
        for policy in ("engine", "flat", "comp_median", "tool")
    ]
    result = audit_mod.audit(rows, expect_seeds=3, seeds_from=2)
    assert result["gates"]["complete"]
    assert result["engine_minus_flat"]["normal"]["n"] == 2
