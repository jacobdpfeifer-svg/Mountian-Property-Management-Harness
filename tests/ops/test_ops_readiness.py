"""Phase 3: readiness state machine, compose gate, incidents and bounded actions."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from conftest import add_reservation, add_signal

from src.compose import generate_recommendations
from src.config import load_policy
from src.db import connect, init_db
from src.ingest import CsvIngestAdapter
from src.ops import AssetEvent
from src.ops import incidents as inc
from src.ops.db import record_asset_event
from src.ops.readiness import (
    ReadinessError,
    current_state,
    revenue_at_risk,
    scan_signal_risk,
    state_for_night,
    transition,
)
from src.ops.profiles import load_ops_policy

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample"


def _event(conn, pid="cloud_9", system="heat", at="2026-12-20T06:00:00", source="manual", **reading):
    event_id, _ = record_asset_event(conn, AssetEvent(
        property_id=pid, system_type=system, observed_at=at, severity="critical",
        source_type=source, reading=reading))
    return event_id


def test_legal_path_through_the_states(ops_db):
    with connect(ops_db) as conn:
        e = _event(conn)
        steps = ["at_risk", "out_of_service", "remediation_in_progress", "verified_ready", "ready"]
        for i, state in enumerate(steps):
            st = transition(conn, "cloud_9", state, evidence_event_id=e, actor="jacob",
                            at=f"2026-12-20T{6 + i:02d}:30:00")
            assert st.state == state
        hist = [r["to_state"] for r in conn.execute(
            "SELECT to_state FROM readiness_transitions ORDER BY transition_id")]
        resolved = conn.execute("SELECT status, verified_by FROM asset_health_events").fetchone()
    assert hist == steps
    assert tuple(resolved) == ("resolved", "jacob")


@pytest.mark.parametrize("path,bad", [
    (["out_of_service"], "ready"),               # must go through remediation
    (["out_of_service"], "verified_ready"),
    ([], "remediation_in_progress"),
    (["inspection_required"], "ready"),          # inspection must be verified
])
def test_illegal_edges_raise(ops_db, path, bad):
    with connect(ops_db) as conn:
        e = _event(conn)
        for i, state in enumerate(path):
            transition(conn, "cloud_9", state, evidence_event_id=e, actor="jacob", at=f"2026-12-20T{6 + i:02d}:30:00")
        with pytest.raises(ReadinessError):
            transition(conn, "cloud_9", bad, evidence_event_id=e, actor="jacob", at="2026-12-20T09:00:00")


def test_automatic_actors_can_only_raise_to_at_risk(ops_db):
    with connect(ops_db) as conn:
        e = _event(conn)
        for state in ("inspection_required", "out_of_service"):
            with pytest.raises(ReadinessError):
                transition(conn, "cloud_9", state, evidence_event_id=e, actor="signal")
        transition(conn, "cloud_9", "at_risk", evidence_event_id=e, actor="telemetry",
                   at="2026-12-20T07:00:00")
        with pytest.raises(ReadinessError):
            transition(conn, "cloud_9", "verified_ready", evidence_event_id=e, actor="telemetry",
                       at="2026-12-20T08:00:00")


def test_evidence_is_required(ops_db):
    with connect(ops_db) as conn:
        with pytest.raises(ReadinessError):
            transition(conn, "cloud_9", "at_risk", evidence_event_id="evt_missing", actor="jacob")


def test_sensor_verification_needs_a_passing_reading(ops_db):
    with connect(ops_db) as conn:
        cold = _event(conn, source="sensor", temp_f=41)
        transition(conn, "cloud_9", "inspection_required", evidence_event_id=cold, actor="jacob",
                   at="2026-12-20T06:30:00")
        with pytest.raises(ReadinessError):
            transition(conn, "cloud_9", "verified_ready", evidence_event_id=cold, actor="sensor_check",
                       at="2026-12-20T07:00:00")
        warm = _event(conn, source="sensor", at="2026-12-20T08:00:00", temp_f=62)
        st = transition(conn, "cloud_9", "verified_ready", evidence_event_id=warm, actor="sensor_check",
                        at="2026-12-20T08:05:00")
    assert st.state == "verified_ready"


def test_window_limits_which_nights_are_restricted(ops_db):
    with connect(ops_db) as conn:
        e = _event(conn)
        transition(conn, "cloud_9", "out_of_service", evidence_event_id=e, actor="jacob",
                   at="2026-12-20T06:30:00", effective_from=date(2026, 12, 22),
                   effective_to=date(2026, 12, 24))
        inside = state_for_night(conn, "cloud_9", date(2026, 12, 23), date(2026, 12, 21))
        outside = state_for_night(conn, "cloud_9", date(2026, 12, 26), date(2026, 12, 21))
        before = state_for_night(conn, "cloud_9", date(2026, 12, 23), date(2026, 12, 19))
    assert inside.state == "out_of_service"
    assert outside.state == "ready" and before.state == "ready"


def test_revenue_at_risk_prorates_and_counts_exposure(ops_db):
    with connect(ops_db) as conn:
        add_reservation(conn, "r1", "cloud_9", date(2026, 12, 20), date(2026, 12, 25), fare=10000.0)
        add_reservation(conn, "own", "cloud_9", date(2026, 12, 26), date(2026, 12, 28), source="owner")
        risk = revenue_at_risk(conn, "cloud_9", date(2026, 12, 23), date(2026, 12, 27), load_ops_policy())
    # 2 of 5 nights fall in the window; the owner stay is not revenue.
    assert risk["booked_value"] == 4000.0
    assert risk["reservations"] == ["r1"]
    assert risk["total"] == 4000.0 + 2000.0 + 500.0


def test_signal_scan_sets_at_risk_once(ops_db):
    with connect(ops_db) as conn:
        add_signal(conn, "weather.temp_mean_c", -25.0, date(2026, 12, 21), observed=date(2026, 12, 20))
        conn.commit()
        first = scan_signal_risk(conn, date(2026, 12, 20), load_ops_policy(), ["cloud_9", "summit_haus"])
        again = scan_signal_risk(conn, date(2026, 12, 20), load_ops_policy(), ["cloud_9", "summit_haus"])
        st = current_state(conn, "cloud_9", "2026-12-20T12:00:00")
    assert {c["property_id"] for c in first} == {"cloud_9", "summit_haus"}
    assert again == [] and st.state == "at_risk" and st.actor == "signal"


# ---------------------------------------------------------------- compose gate

@pytest.fixture()
def sample_db(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("MONTLUXE_MEMORY_ROOT", str(tmp_path / "memroot"))
    path = tmp_path / "sample.db"
    init_db(path)
    with connect(path) as conn:
        CsvIngestAdapter(
            properties_csv=SAMPLE / "properties.csv",
            inventory_csv=SAMPLE / "nightly_inventory.csv",
            comps_csv=SAMPLE / "comps.csv",
            demand_csv=SAMPLE / "demand_signals.csv",
            inquiries_csv=SAMPLE / "booking_inquiries.csv",
        ).load_all(conn)
    return path


def test_compose_gate_demotes_clamps_and_blocks(sample_db):
    policy = load_policy()
    with connect(sample_db) as conn:
        e1 = _event(conn, pid="cabin_ridge", at="2026-11-01T08:00:00")
        transition(conn, "cabin_ridge", "inspection_required", evidence_event_id=e1, actor="jacob",
                   at="2026-11-01T08:00:00", effective_from=date(2026, 12, 3),
                   effective_to=date(2026, 12, 5))
        e2 = _event(conn, pid="aspen_glow", system="water", at="2026-11-01T08:00:00")
        transition(conn, "aspen_glow", "out_of_service", evidence_event_id=e2, actor="jacob",
                   at="2026-11-01T08:00:00", effective_from=date(2026, 12, 2),
                   effective_to=date(2026, 12, 4))
        recs, _ = generate_recommendations(conn, date(2026, 12, 1), date(2026, 12, 7),
                                           property_ids=["cabin_ridge", "aspen_glow"],
                                           policy=policy, persist=False, as_of=date(2026, 11, 1))
    by = {(r.property_id, r.stay_date): r for r in recs}
    codes = lambda r: [x["code"] for x in r.reasons]  # noqa: E731
    for day in (3, 4, 5):
        r = by.get(("cabin_ridge", date(2026, 12, day)))
        if r is None:
            continue
        assert "readiness" in codes(r)
        assert r.autonomy_level != "handle"
        assert r.recommended_price <= (r.listed_price_at_run or r.recommended_price) + 0.01
    for day in (2, 3, 4):
        r = by.get(("aspen_glow", date(2026, 12, day)))
        if r is None:
            continue
        assert r.status == "blocked" and r.autonomy_level == "escalate"
        assert "readiness" in codes(r)
    for key, r in by.items():
        if key[0] == "cabin_ridge" and key[1].day in (1, 2, 6, 7):
            assert "readiness" not in codes(r)
    assert any(k[0] == "aspen_glow" and k[1].day in (2, 3, 4) for k in by), "no restricted nights priced"
    assert any(k[0] == "cabin_ridge" and k[1].day in (3, 5) for k in by), "no inspection nights priced"


# ------------------------------------------------------------------- incidents

def test_incident_scan_is_idempotent_and_lists_affected_stays(ops_db):
    with connect(ops_db) as conn:
        add_reservation(conn, "arr", "summit_haus", date(2026, 12, 21), date(2026, 12, 26))
        add_reservation(conn, "dep", "cloud_9", date(2026, 12, 17), date(2026, 12, 22))
        for day in (21, 22):
            add_signal(conn, "cdot.berthoud_closed", 1.0, date(2026, 12, day), observed=date(2026, 12, 20))
        conn.commit()
        found = [i for i in inc.scan(conn, date(2026, 12, 20)) if i.incident_type == "access_closure"]
        again = [i for i in inc.scan(conn, date(2026, 12, 20)) if i.incident_type == "access_closure"]
    [i] = found
    assert i.created and not again[0].created and i.incident_id == again[0].incident_id
    assert (i.window_start, i.window_end) == (date(2026, 12, 21), date(2026, 12, 22))
    assert [a["reservation_id"] for a in i.affected["arrivals"]] == ["arr"]
    assert [d["reservation_id"] for d in i.affected["departures"]] == ["dep"]


def test_approved_actions_write_drafts_and_never_send(ops_db, tmp_path):
    with connect(ops_db) as conn:
        add_reservation(conn, "arr", "summit_haus", date(2026, 12, 21), date(2026, 12, 26))
        add_signal(conn, "cdot.berthoud_closed", 1.0, date(2026, 12, 21), observed=date(2026, 12, 20))
        conn.commit()
        [i] = [x for x in inc.scan(conn, date(2026, 12, 20)) if x.incident_type == "access_closure"]
        out = inc.approve(conn, i.incident_id, "draft_guest_notice", actor="jacob")
        drafts = json.loads(Path(out["output_ref"]).read_text())
        task = inc.approve(conn, i.incident_id, "add_snow_check", actor="jacob")
        hold = inc.approve(conn, i.incident_id, "suppress_auto_price", actor="jacob")
        st = current_state(conn, "summit_haus")
        log = [(r["action_code"], r["status"]) for r in inc.show(conn, i.incident_id)["log"]]
    assert drafts["drafts"][0]["status"] == "DRAFT - not sent"
    assert "312 Northwoods" in drafts["drafts"][0]["text"] and "cotrip.org" in drafts["drafts"][0]["text"]
    assert "dry run" in task["summary"]
    assert st.state == "at_risk" and "summit_haus" in hold["summary"]
    assert ("draft_guest_notice", "executed") in log and ("add_snow_check", "approved") in log


@pytest.mark.parametrize("action", ["cancel_reservation", "issue_refund", "send_access_code",
                                    "send_guest_message", "close_inventory", "declare_safe"])
def test_forbidden_actions_raise(ops_db, action):
    with connect(ops_db) as conn:
        add_signal(conn, "cdot.berthoud_closed", 1.0, date(2026, 12, 21), observed=date(2026, 12, 20))
        conn.commit()
        [i] = [x for x in inc.scan(conn, date(2026, 12, 20)) if x.incident_type == "access_closure"]
        with pytest.raises(inc.ForbiddenAction):
            inc.approve(conn, i.incident_id, action, actor="jacob")
        n = conn.execute("SELECT COUNT(*) FROM incident_actions").fetchone()[0]
    assert n == 0


def test_live_task_write_refuses_without_gate_and_on_demo_db(ops_db):
    with connect(ops_db) as conn:
        add_signal(conn, "cdot.berthoud_closed", 1.0, date(2026, 12, 21), observed=date(2026, 12, 20))
        conn.commit()
        [i] = [x for x in inc.scan(conn, date(2026, 12, 20)) if x.incident_type == "access_closure"]
        with pytest.raises(inc.IncidentError, match="confirm-live-write"):
            inc.approve(conn, i.incident_id, "add_heat_check", actor="jacob", adapter="guesty")
        with pytest.raises(inc.IncidentError, match="identity"):
            inc.approve(conn, i.incident_id, "add_heat_check", actor="jacob", adapter="guesty", live=True)
        failed = conn.execute(
            "SELECT COUNT(*) FROM incident_actions WHERE status='failed'").fetchone()[0]
    assert failed == 2


def test_misconfigured_rule_cannot_smuggle_a_forbidden_action(ops_db):
    policy = load_ops_policy()
    policy["incidents"]["rules"][0]["actions"].append("issue_refund")
    with connect(ops_db) as conn:
        add_signal(conn, "cdot.berthoud_closed", 1.0, date(2026, 12, 21), observed=date(2026, 12, 20))
        conn.commit()
        with pytest.raises(inc.ForbiddenAction):
            inc.scan(conn, date(2026, 12, 20), policy)
