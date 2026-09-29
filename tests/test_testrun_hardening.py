from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.run_testruns import (
    PropertyRun,
    check_agent_cmd,
    repair_stale,
    run_agent,
    write_fallback_report,
)
from src.cli.main import main as cli_main
from src.db import connect, init_db
from src.inventory import EmptyInventoryError, require_forward_inventory, seed_empty_skeleton
from src.scrape.timeout import call_with_timeout


def test_check_agent_cmd_rejects_full_auto():
    with pytest.raises(RuntimeError, match="full-auto"):
        check_agent_cmd("codex exec --full-auto -")
    check_agent_cmd("python3 -c 'pass'")


def test_write_fallback_report(tmp_path: Path):
    run = PropertyRun("cloud_9", "x", "TESTRUN_cloud9.md")
    report = tmp_path / "TESTRUN_cloud9.md"
    db = tmp_path / "missing.db"
    write_fallback_report(report, run, db_path=db, export_path=None, reason="stalled")
    text = report.read_text(encoding="utf-8")
    assert "failed_report_missing" in text
    assert "Guesty write count: 0" in text
    assert "Export row count:" in text


def test_repair_stale_running():
    state = {"properties": {"cloud_9": {"status": "running"}}, "audit": {"status": "running"}}
    repair_stale(state)
    assert state["properties"]["cloud_9"]["status"] == "interrupted"
    assert state["audit"]["status"] == "interrupted"


def test_watchdog_kills_hung_agent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TESTRUN_PROPERTY_TIMEOUT_S", "2")
    monkeypatch.setenv("TESTRUN_IDLE_TIMEOUT_S", "30")
    monkeypatch.setenv("TESTRUN_SIGKILL_GRACE_S", "1")
    log = tmp_path / "agent.log"
    code = run_agent(
        "python3 -c 'import time; time.sleep(30)'",
        "prompt",
        cwd=tmp_path,
        log=log,
        workspace=tmp_path,
        prompt=tmp_path / "p.md",
        property_id="x",
        report=tmp_path / "r.md",
    )
    assert code != 0
    assert "wall-clock timeout" in log.read_text(encoding="utf-8")


def test_empty_inventory_preflight(tmp_path: Path):
    db = tmp_path / "inv.db"
    init_db(db)
    with connect(db) as conn:
        conn.execute(
            "INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,"
            "base_ceiling_rate,min_floor_rate,max_ceiling_rate) "
            "VALUES ('summit_haus','S',5,4,'[]',1000,400,2000)"
        )
        conn.commit()
        with pytest.raises(EmptyInventoryError, match="0 available nights"):
            require_forward_inventory(conn, date(2026, 9, 24), date(2026, 9, 26), ["summit_haus"])
        n = seed_empty_skeleton(conn, ["summit_haus"], date(2026, 9, 24), date(2026, 9, 26))
        assert n == 3
        counts = require_forward_inventory(
            conn, date(2026, 9, 24), date(2026, 9, 26), ["summit_haus"]
        )
        assert counts.available == 3
        assert counts.with_listed_price == 0


def test_recommend_cli_exits_2_without_inventory(tmp_path: Path, capsys):
    db = tmp_path / "cli.db"
    init_db(db)
    with connect(db) as conn:
        conn.execute(
            "INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,"
            "base_ceiling_rate,min_floor_rate,max_ceiling_rate) "
            "VALUES ('summit_haus','S',5,4,'[]',1000,400,2000)"
        )
        conn.commit()
    with pytest.raises(SystemExit) as exc:
        cli_main([
            "--db", str(db), "recommend",
            "--property", "summit_haus",
            "--from", "2026-09-24", "--to", "2026-09-26",
            "--dry-run",
        ])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "0 available nights in scope" in err


def test_call_with_timeout_raises():
    def hang() -> None:
        import time
        time.sleep(5)

    with pytest.raises(TimeoutError):
        call_with_timeout(hang, 0.2)


def test_run_scrape_timeout_finishes_degraded_not_running(tmp_path: Path):
    from src.config import load_policy
    from src.ingest import CsvIngestAdapter
    from src.scrape import run_scrape

    db = tmp_path / "scrape.db"
    init_db(db)
    sample = Path(__file__).resolve().parents[1] / "data" / "sample"
    policy = load_policy()
    policy["scrape"]["window_timeout_s"] = 0.2
    policy["scrape"]["run_deadline_s"] = 1.0

    class HangProvider:
        name = "hang"

        def sweep(self, check_in, nights):  # noqa: ARG002
            import time
            time.sleep(5)

        def calendar(self, room_id):  # noqa: ARG002
            return {}

    with connect(db) as conn:
        CsvIngestAdapter(
            properties_csv=sample / "properties.csv",
            inventory_csv=sample / "nightly_inventory.csv",
            comps_csv=sample / "comps.csv",
            demand_csv=sample / "demand_signals.csv",
            inquiries_csv=sample / "booking_inquiries.csv",
        ).load_all(conn)
        report = run_scrape(
            conn, HangProvider(), policy, horizon_days=4,
            fetch_calendars=False, resume=False,
        )
        row = conn.execute(
            "SELECT status FROM comp_scrape_runs WHERE run_id = ?", (report.run_id,)
        ).fetchone()
    assert report.status in {"degraded", "failed"}
    assert report.status != "running"
    assert row["status"] == report.status
    assert report.errors


def test_testrun_db_requires_property(tmp_path: Path):
    db = tmp_path / "testrun_summit_haus.db"
    init_db(db)
    with pytest.raises(SystemExit, match="requires --property"):
        cli_main([
            "--db", str(db), "recommend",
            "--from", "2026-09-24", "--to", "2026-09-26", "--dry-run",
        ])
