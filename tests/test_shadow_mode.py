"""Read-only daily shadow mode (workstream 6)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.compose import generate_recommendations
from src.config import load_policy
from src.db import connect, init_db
from src.db.migrations import apply_migrations
from src.eval.shadow import GuestyWriteForbidden
from src.guardrails import assess_data_health
from src.ingest import CsvIngestAdapter
from src.review import act
from src.shadow import capture_outcomes, execute_shadow_day, run_shadow_day, scorecard, shadow_report

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
PID = "aspen_glow"
SCOPE = frozenset({PID})
DAY = date(2026, 12, 1)


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "shadow.db"
    init_db(path)
    c = connect(path)
    CsvIngestAdapter(
        properties_csv=SAMPLE / "properties.csv", inventory_csv=SAMPLE / "nightly_inventory.csv",
        comps_csv=SAMPLE / "comps.csv", demand_csv=SAMPLE / "demand_signals.csv",
        inquiries_csv=SAMPLE / "booking_inquiries.csv").load_all(c)
    apply_migrations(c)
    generate_recommendations(c, DAY, DAY + timedelta(days=13), property_ids=[PID], policy=load_policy())
    # The engine stamps recommendations (UTC) with the real clock; the test's day is DAY
    # (18:00 UTC is midday in Denver, where shadow days are counted).
    c.execute("UPDATE price_recommendations SET created_at = ?", (f"{DAY.isoformat()} 18:00:00",))
    c.commit()
    yield c
    c.close()


def _day(conn, as_of=DAY):
    health = assess_data_health(conn, load_policy(), property_ids=[PID], as_of=as_of)
    return run_shadow_day(conn, as_of=as_of, property_id=PID, health=health, policy_sha256="p" * 64,
                          code_sha256="c" * 64, horizon_days=14, scope=SCOPE)


def test_shadow_day_queues_recommendations_with_current_rate_health_and_reasons(conn):
    out = _day(conn)
    assert out.nights > 0 and out.queued == out.nights
    item = conn.execute("SELECT * FROM review_item WHERE decision_key LIKE 'shadow:%' LIMIT 1").fetchone()
    assert item["proposed_rate"] > 0 and item["freshness_json"] and item["reasons_json"] != "[]"
    assert item["readiness"] in ("shadow_only", "data_blocked")
    spine = conn.execute("SELECT human_decision, autonomy_level, applied_price FROM fact_price_decision").fetchall()
    assert len(spine) == out.nights
    assert all(r["autonomy_level"] == "observe" and r["applied_price"] is None for r in spine)
    run = conn.execute("SELECT * FROM shadow_run").fetchone()
    assert run["rate_writes"] == 0 and run["health_json"]


def test_stale_recommendations_are_not_queued_as_todays(conn):
    later = DAY + timedelta(days=5)
    health = assess_data_health(conn, load_policy(), property_ids=[PID], as_of=later)
    out = run_shadow_day(conn, as_of=later, property_id=PID, health=health, policy_sha256="p" * 64,
                         code_sha256="c" * 64, horizon_days=14, scope=SCOPE)
    assert out.queued == 0 and out.stale > 0
    out = run_shadow_day(conn, as_of=later + timedelta(days=1), property_id=PID, health=health,
                         policy_sha256="p" * 64, code_sha256="c" * 64, horizon_days=14, scope=SCOPE,
                         max_rec_age_days=30)
    assert out.queued > 0


def test_shadow_never_writes_rates_and_refuses_a_database_that_did(conn):
    _day(conn)
    assert conn.execute("SELECT COUNT(*) FROM rate_changes WHERE result='applied'").fetchone()[0] == 0
    conn.execute("INSERT INTO rate_changes (property_id, stay_date, old_price, new_price, actor, autonomy_level,"
                 " result) VALUES (?, '2026-12-05', 100, 110, 'guesty', 'suggest', 'applied')", (PID,))
    conn.commit()
    with pytest.raises(GuestyWriteForbidden):
        _day(conn, DAY + timedelta(days=1))


def test_same_day_twice_is_refused_not_duplicated(conn):
    _day(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _day(conn)


def test_human_decisions_are_recorded_and_scored_but_not_applied(conn):
    _day(conn)
    ids = [r[0] for r in conn.execute("SELECT id FROM review_item ORDER BY id LIMIT 2")]
    act(conn, ids[0], action="approve", actor="operator", role="approver", reason="looks right")
    act(conn, ids[1], action="edit", actor="operator", role="approver", reason="too high",
        edited_price=999.0)
    card = scorecard(conn)
    assert card["reviewed_share"] > 0 and card["approved_share_of_reviewed"] == 0.5
    assert card["rate_writes"] == 0 and card["shadow_days"] == 1
    assert conn.execute("SELECT COUNT(*) FROM rate_changes").fetchone()[0] == 0


def test_outcomes_append_actual_metrics_once_after_the_night_passes(conn):
    _day(conn)
    assert capture_outcomes(conn, as_of=DAY) == 0                     # nothing has passed yet
    later = DAY + timedelta(days=30)
    n = capture_outcomes(conn, as_of=later)
    assert n > 0 and capture_outcomes(conn, as_of=later) == 0
    statuses = {r[0] for r in conn.execute("SELECT night_status FROM shadow_outcome")}
    assert statuses <= {"booked", "available", "blocked", "unknown"}
    metrics = conn.execute("SELECT * FROM shadow_outcome_observation").fetchall()
    assert len(metrics) == n
    for metric in metrics:
        if metric["night_status"] == "available":
            assert metric["actual_revpan"] == 0.0 and metric["actual_adr"] is None
        if metric["night_status"] == "booked":
            assert metric["actual_adr"] is not None and metric["actual_revpan"] == metric["actual_adr"]


def test_shadow_tables_are_append_only(conn):
    _day(conn)
    capture_outcomes(conn, as_of=DAY + timedelta(days=30))
    for sql in ("UPDATE shadow_run SET nights = 0", "DELETE FROM shadow_run",
                "UPDATE shadow_outcome SET night_status = 'booked'", "DELETE FROM shadow_outcome",
                "UPDATE shadow_night SET listed_rate = 0", "DELETE FROM shadow_night",
                "UPDATE shadow_outcome_observation SET actual_revpan = 0", "DELETE FROM shadow_outcome_observation"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute(sql)


def test_scorecard_counts_streaks_and_unhealthy_days(conn):
    for k in (0, 1, 3):
        _day(conn, DAY + timedelta(days=k))
    card = scorecard(conn)
    assert card["shadow_days"] == 3 and card["longest_daily_streak"] == 2
    assert 0.0 <= card["healthy_run_share"] <= 1.0


def test_the_shadow_module_holds_no_pms_client():
    text = (ROOT / "src" / "shadow" / "__init__.py").read_text()
    assert "GuestyClient" not in text and "set_rate" not in text
    assert "push_rate" not in text


def test_shadow_night_records_distance_and_the_report_is_not_causal(conn):
    out = _day(conn)
    night = conn.execute("SELECT * FROM shadow_night LIMIT 1").fetchone()
    assert night["autonomy_level"] == "observe"
    assert night["listed_rate"] is not None and night["recommended_price"] is not None
    assert night["price_distance"] == pytest.approx(night["recommended_price"] - night["listed_rate"])
    assert night["adr"] is None and night["revpan"] is None
    assert night["price_basis_confidence"] in ("unknown", "uncertified")
    report = shadow_report(conn)
    assert report["shadow_gate"] == "NOT_PASSED" and report["shadow_days"] == 1
    assert report["nights"] == out.nights
    assert "cannot establish causal revenue lift" in report["limitation"]
    assert {s["segment"] for s in report["segments"]} >= {
        "property", "season", "lead_time", "length_of_stay", "channel", "price_distance",
        "weak_ceiling", "comp_state", "outcome", "refund_status"}
    assert all("actual_revpan" in s and "settled_owner_net_per_night" in s for s in report["segments"])


def test_execute_shadow_day_degrades_without_a_rate_write(conn):
    health = assess_data_health(conn, load_policy(), property_ids=[PID], as_of=DAY)
    health.failures.append("malformed calendar")
    status, detail = execute_shadow_day(
        conn, as_of=DAY, property_ids=[PID], health_for=lambda _p: health,
        policy_sha256="p" * 64, code_sha256="c" * 64, scope=SCOPE, horizon_days=14)
    assert status == "degraded" and "Guesty writes 0" in detail
    again, _ = execute_shadow_day(
        conn, as_of=DAY, property_ids=[PID], health_for=lambda _p: health,
        policy_sha256="p" * 64, code_sha256="c" * 64, scope=SCOPE, horizon_days=14)
    assert again == "degraded"
    assert conn.execute("SELECT COUNT(*) FROM rate_changes WHERE result='applied'").fetchone()[0] == 0


def test_execute_shadow_day_fails_closed_on_an_unrelated_integrity_error(conn):
    """A shadow_night collision is not an idempotent shadow_run duplicate."""
    stay = conn.execute(
        "SELECT stay_date FROM nightly_inventory WHERE property_id=? AND status='available' AND stay_date>? "
        "ORDER BY stay_date LIMIT 1", (PID, DAY.isoformat())).fetchone()["stay_date"]
    conn.execute(
        """INSERT INTO shadow_night (as_of, property_id, stay_date, decision_key, availability, reasons_json,
               health_level, autonomy_level, price_basis_confidence, weak_ceiling, created_at)
           VALUES (?, ?, ?, 'preexisting-collision', 'available', '[]', 'observe', 'observe', 'unknown', 0, 'now')""",
        (DAY.isoformat(), PID, stay))
    conn.commit()
    health = assess_data_health(conn, load_policy(), property_ids=[PID], as_of=DAY)
    status, detail = execute_shadow_day(
        conn, as_of=DAY, property_ids=[PID], health_for=lambda _p: health,
        policy_sha256="p" * 64, code_sha256="c" * 64, scope=SCOPE, horizon_days=14)
    assert status == "failed" and "integrity failure" in detail
    assert conn.execute("SELECT COUNT(*) FROM shadow_run").fetchone()[0] == 0
