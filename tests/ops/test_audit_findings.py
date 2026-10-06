"""Audit 2026-10-06: reproductions for Stage 2 component findings.

Each test pins the contract the finding is about. Tests for open findings are
marked xfail(strict=True) with the finding id, so they flip to a failure the
moment the behaviour changes and the finding table must be updated.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from conftest import add_open_nights, add_reservation, add_signal

from src.db import connect
from src.ops import AssetEvent
from src.ops.db import record_asset_event
from src.ops.readiness import (
    AT_RISK,
    INSPECTION_REQUIRED,
    READY,
    ReadinessError,
    auto_escalate,
    scan_signal_risk,
    state_for_night,
    transition,
)

PID = "cloud_9"


def _ev(conn, system, *, severity="warn", source="manual", at="2026-12-01T08:00:00",
        start=None, end=None, ref=None):
    event_id, _ = record_asset_event(conn, AssetEvent(
        property_id=PID, system_type=system, observed_at=at, severity=severity,
        source_type=source, source_ref=ref or f"{system}:{at}",
        effective_from=start.isoformat() if start else None,
        effective_to=end.isoformat() if end else None,
    ))
    return event_id


# ------------------------------------------------------------- readiness


def test_verifying_one_system_does_not_clear_another_systems_window(ops_db):
    """OPS-013: readiness is one state per property. A verified_ready for the
    hot tub (Dec 5) must not clear an open snow-access risk on Dec 20-22."""
    storm = date(2026, 12, 20)
    with connect(ops_db) as conn:
        snow = _ev(conn, "snow_access", source="signal", start=storm, end=storm + timedelta(days=2))
        transition(conn, PID, AT_RISK, evidence_event_id=snow, actor="signal",
                   at="2026-12-01T08:00:00", effective_from=storm,
                   effective_to=storm + timedelta(days=2))
        spa = _ev(conn, "spa", at="2026-12-04T08:00:00", start=date(2026, 12, 5),
                  end=date(2026, 12, 5))
        auto_escalate(conn, PID, spa, actor="telemetry", note="spa low temp",
                      at="2026-12-04T08:00:00", effective_from=date(2026, 12, 5),
                      effective_to=date(2026, 12, 5))
        transition(conn, PID, "verified_ready", evidence_event_id=spa, actor="Dana Ops",
                   at="2026-12-04T12:00:00")
        night = state_for_night(conn, PID, storm, "2026-12-04T13:00:00")
        snow_open = conn.execute("SELECT status FROM asset_health_events WHERE event_id=?",
                                 (snow,)).fetchone()["status"]
    assert snow_open == "open"
    assert night.state == AT_RISK, f"storm night shows {night.state} after an unrelated spa check"


def test_signal_outside_an_inspection_window_does_not_abort_the_scan(ops_db):
    """OPS-014: inspection_required -> at_risk is not an edge. A signal for a
    night outside the inspection window raised ReadinessError and aborted the
    whole scan, so later properties were never checked."""
    with connect(ops_db) as conn:
        ev = _ev(conn, "spa", start=date(2026, 12, 2), end=date(2026, 12, 3))
        transition(conn, PID, INSPECTION_REQUIRED, evidence_event_id=ev, actor="Dana Ops",
                   at="2026-12-01T08:00:00", effective_from=date(2026, 12, 2),
                   effective_to=date(2026, 12, 3))
        add_signal(conn, "cdot.access_risk", 1.0, date(2026, 12, 5), observed=date(2026, 12, 1))
        conn.commit()
        policy = {"incidents": {"lookahead_days": 5},
                  "readiness": {"auto_at_risk": [{"signal_key": "cdot.access_risk", "op": ">=",
                                                  "threshold": 1.0,
                                                  "system_type": "snow_access"}]}}
        changed = scan_signal_risk(conn, date(2026, 12, 2), policy,
                                   [PID, "summit_haus"])
        storm = state_for_night(conn, PID, date(2026, 12, 5), "2026-12-02T23:59:59")
        other = state_for_night(conn, "summit_haus", date(2026, 12, 5), "2026-12-02T23:59:59")
    assert other.state == AT_RISK, "later properties must still be scanned"
    assert storm.state == AT_RISK
    assert {c["property_id"] for c in changed} >= {"summit_haus"}


def test_recovery_sees_a_critical_event_stamped_in_utc(ops_db):
    """OPS-015: timestamps are compared as text. A critical spa reading stamped
    2026-12-05T01:00Z (18:00 MST on Dec 4) is invisible to a naive local 20:00
    verification, so the heat check marks the house ready over an open
    critical spa failure."""
    with connect(ops_db) as conn:
        heat = _ev(conn, "heat", source="sensor", at="2026-12-04T17:00:00",
                   start=date(2026, 12, 5), end=date(2026, 12, 5))
        transition(conn, PID, AT_RISK, evidence_event_id=heat, actor="telemetry",
                   at="2026-12-04T17:00:00", effective_from=date(2026, 12, 5),
                   effective_to=date(2026, 12, 5))
        _ev(conn, "spa", severity="critical", source="sensor", at="2026-12-05T01:00:00+00:00")
        with pytest.raises(ReadinessError, match="critical spa"):
            transition(conn, PID, "verified_ready", evidence_event_id=heat, actor="Dana Ops",
                       at="2026-12-04T20:00:00")


def test_task_minutes_respect_mixed_offsets():
    """OPS-022: minutes_between drops tzinfo when only one side has it, so a
    UTC completion against a local schedule is off by the UTC offset."""
    from src.ops.sources.normalize import minutes_between

    assert minutes_between("2026-12-05T16:00:00", "2026-12-05T23:30:00+00:00") == 30


@pytest.mark.xfail(strict=True, reason="OPS-016 open")
def test_automatic_actor_names_outside_the_fixed_set_are_not_trusted(ops_db):
    """OPS-016: only 'signal', 'telemetry', 'system' are treated as automatic.
    An importer that writes actor='breezeway' (or any other non-human string)
    can mark a property verified_ready."""
    with connect(ops_db) as conn:
        ev = _ev(conn, "spa", severity="warn", start=date(2026, 12, 5), end=date(2026, 12, 5))
        transition(conn, PID, AT_RISK, evidence_event_id=ev, actor="telemetry",
                   at="2026-12-04T08:00:00", effective_from=date(2026, 12, 5),
                   effective_to=date(2026, 12, 5))
        with pytest.raises(ReadinessError):
            transition(conn, PID, "verified_ready", evidence_event_id=ev, actor="breezeway",
                       at="2026-12-04T09:00:00")


# ------------------------------------------------------------- incidents


def _incident_policy():
    return {"incidents": {"lookahead_days": 3, "rules": [{
        "type": "heavy_snowfall", "signal_key": "weather.snowfall_sum_cm", "op": ">=",
        "threshold": 20, "severity": "warn", "actions": ["alert_responsible_agent"]}]}}


@pytest.mark.xfail(strict=True, reason="OPS-017 open")
def test_partial_rerun_inside_a_window_reuses_the_incident(ops_db):
    """OPS-017: incident_id = type|market|window_start. Rescanning on day 2 of a
    3-day storm sees a window that starts on day 2 and opens a second incident."""
    from src.ops.incidents import scan

    storm = date(2026, 12, 10)
    with connect(ops_db) as conn:
        for i in range(3):
            add_signal(conn, "weather.snowfall_sum_cm", 30, storm + timedelta(days=i),
                       observed=storm - timedelta(days=1))
        conn.commit()
        first = scan(conn, storm - timedelta(days=1) + timedelta(days=1), _incident_policy())
        second = scan(conn, storm + timedelta(days=1), _incident_policy())
        n = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    assert {c.incident_id for c in first} == {c.incident_id for c in second}
    assert n == 1


@pytest.mark.xfail(strict=True, reason="OPS-018 open")
def test_forbidden_action_in_a_rule_fails_even_without_a_signal(ops_db):
    """OPS-018: a rule listing a forbidden action only fails when it fires."""
    from src.ops.actions import ForbiddenAction
    from src.ops.incidents import scan

    policy = _incident_policy()
    policy["incidents"]["rules"][0]["actions"] = ["send_guest_message"]
    with connect(ops_db) as conn, pytest.raises(ForbiddenAction):
        scan(conn, date(2026, 12, 1), policy)


# ------------------------------------------------------------- turns / capacity


@pytest.mark.xfail(strict=True, reason="OPS-019 open")
def test_overlapping_reservations_are_reported_not_silently_dropped(ops_db):
    """OPS-019: two occupying reservations that overlap (a double booking or a
    stale duplicate) yield no flag; the overlapped stay gets no arrival turn."""
    from src.ops.profiles import load_ops_policy, load_profiles
    from src.ops.turns import derive_turns

    with connect(ops_db) as conn:
        add_reservation(conn, "a", PID, date(2026, 12, 1), date(2026, 12, 5))
        add_reservation(conn, "b", PID, date(2026, 12, 3), date(2026, 12, 7))
        conn.commit()
        turns = derive_turns(conn, load_profiles()[PID], date(2026, 12, 1), date(2026, 12, 10),
                             as_of=date(2026, 11, 1), ops_policy=load_ops_policy(),
                             point_in_time_reservations=False)
    flagged = [t for t in turns if getattr(t, "conflict", None)]
    assert flagged, f"overlap a/b produced turns {[t.turn_id for t in turns]} with no conflict"


@pytest.mark.xfail(strict=True, reason="OPS-020 open")
def test_a_day_with_no_rostered_crew_is_critical_not_unknown(ops_db):
    """OPS-020: a weekday with no crew rostered has 0 worker-minutes; the
    report labels the day 'unknown' instead of 'critical'."""
    from src.ops.economics import capacity_view
    from src.ops.profiles import load_ops_config, load_ops_policy, load_profiles
    from src.ops.turns import derive_turns

    sat = date(2026, 12, 5)  # Saturday
    cfg = load_ops_config()
    cfg["capacity"] = {"crews": [{"name": "weekday", "zones": [load_profiles()[PID].access_zone],
                                  "workers": 2, "minutes_per_worker": 480,
                                  "weekdays": [0, 1, 2, 3, 4]}]}
    with connect(ops_db) as conn:
        add_reservation(conn, "a", PID, date(2026, 12, 1), sat)
        add_reservation(conn, "b", PID, sat, date(2026, 12, 8))
        conn.commit()
        profiles = load_profiles()
        turns = derive_turns(conn, profiles[PID], sat, sat, as_of=date(2026, 11, 1),
                             ops_policy=load_ops_policy(), point_in_time_reservations=False)
        view = capacity_view(conn, profiles[PID].access_zone, sat, as_of=date(2026, 11, 1),
                             ops_cfg=cfg, profiles=profiles, turns=turns)
    assert view.turns == 1
    assert view.utilization is not None and view.utilization > 1.0


# ------------------------------------------------------------- point in time


def test_ops_inputs_ignore_everything_recorded_after_as_of(ops_db):
    """2B: outcomes, capacity, profiles, and signals recorded after as_of are invisible."""
    from src.ops.economics import _imported_capacity, observed_costs
    from src.ops.turns import signal_value

    as_of = date(2026, 12, 1)
    with connect(ops_db) as conn:
        from src.ops.db import ensure_ops_tables

        ensure_ops_tables(conn)
        for i, (svc, imported) in enumerate([("2026-11-20", "2026-11-21T10:00:00"),
                                             ("2026-11-25", "2026-12-03T10:00:00"),
                                             ("2026-12-02", "2026-12-02T10:00:00")]):
            conn.execute(
                """INSERT INTO turnover_outcomes (property_id, service_date, source, source_task_id,
                       service_type, cost, imported_at) VALUES (?,?,?,?,?,?,?)""",
                (PID, svc, "csv", f"t{i}", "turnover", 100.0 * (i + 1), imported))
        conn.execute(
            """INSERT INTO operations_capacity_snapshots (as_of, service_date, access_zone,
                   available_worker_minutes, committed_worker_minutes, service_type, source)
               VALUES ('2026-12-02', '2026-12-05', 'z', 999, 0, 'turnover', 'csv')""")
        add_signal(conn, "weather.snowfall_sum_cm", 40, date(2026, 12, 5),
                   observed=date(2026, 12, 2))
        conn.commit()
        assert observed_costs(conn, PID, as_of) == [100.0]
        assert _imported_capacity(conn, "z", date(2026, 12, 5), as_of) is None
        assert signal_value(conn, "weather.snowfall_sum_cm", "grand_home", date(2026, 12, 5),
                            as_of) is None


# ------------------------------------------------------------- compliance


def test_fixed_date_renewal_issued_on_the_renewal_day_lasts_a_year():
    """OPS-021: Winter Park renews on 09-30. A registration issued on 2026-09-30
    must run to 2027-09-30, not expire the day it was issued."""
    from src.compliance import deadline_for

    cred = {"issued_at": "2026-09-30", "expires_at": None}
    assert deadline_for(cred, {"kind": "fixed_date", "month_day": "09-30"}) == date(2027, 9, 30)


def test_no_output_calls_a_property_compliant(ops_db):
    """2G: the register reports evidence and deadlines; it never says compliant."""
    from src.compliance import check, render_text

    with connect(ops_db) as conn:
        text = render_text(check(conn, date(2026, 12, 1)))
    lowered = text.lower().replace("not a legal determination", "")
    assert " compliant" not in lowered and "compliant " not in lowered


# ------------------------------------------------------------- owner ledger


def test_ledger_rows_never_land_on_the_wrong_owner_or_level(ops_db, tmp_path):
    """OPS-023: a misspelled property became an owner-level charge, and an
    owner/property mismatch was accepted and then vanished from both receipts."""
    from src.ops.sources.csv_import import import_csv

    csv = tmp_path / "ledger.csv"
    csv.write_text(
        "owner_id,property,entry_date,category,amount,memo\n"
        "northwoods,312 Northwods,2026-12-03,maintenance,500,typo\n"
        "cloud9,312 Northwoods,2026-12-03,maintenance,400,wrong owner\n"
        "northwoods,312 Northwoods,2026-12-03,maintenance,300,good\n"
        "northwoods,,2026-12-03,other,50,owner-level\n",
        encoding="utf-8",
    )
    with connect(ops_db) as conn:
        result = import_csv(conn, csv, kind="ledger")
        rows = [tuple(r) for r in conn.execute(
            "SELECT owner_id, property_id, amount FROM owner_ledger_entries ORDER BY amount")]
    assert result.rejected == 2, result.errors
    assert rows == [("northwoods", None, 50.0), ("northwoods", "summit_haus", 300.0)]
