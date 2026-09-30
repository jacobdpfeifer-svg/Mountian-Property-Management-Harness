"""Every operations data path lands in the same tables, idempotently."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.db import connect
from src.ops.readiness import current_state
from src.ops.sources import PropertyResolver, status
from src.ops.sources.api_import import import_breezeway, import_guesty_tasks, import_turno
from src.ops.sources.csv_import import import_csv
from src.ops.sources.manual import import_manual
from src.ops.sources.normalize import as_minutes
from src.ops.sources.telemetry import derive_severity, import_telemetry
from src.ops.sources.webhooks import import_task_webhooks
from src.pms.webhooks import record_delivery

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample" / "ops"


def _outcomes(conn):
    return {r["source_task_id"]: dict(r) for r in conn.execute("SELECT * FROM turnover_outcomes")}


def test_minutes_parse_every_common_spelling():
    assert as_minutes("95") == 95
    assert as_minutes("1:35") == 95
    assert as_minutes("1h 35m") == 95
    assert as_minutes("1.5h") == 90
    assert as_minutes("") is None


def test_resolver_uses_ids_listing_ids_and_aliases_and_never_guesses(ops_db):
    with connect(ops_db) as conn:
        r = PropertyResolver(conn)
    assert r.resolve("summit_haus") == "summit_haus"
    assert r.resolve("listing-c9") == "cloud_9"
    assert r.resolve("312 northwoods") == "summit_haus"
    assert r.resolve("Some Other Cabin") is None


def test_generic_csv_import_is_idempotent(ops_db):
    with connect(ops_db) as conn:
        first = import_csv(conn, SAMPLE / "turnover_outcomes.csv")
        second = import_csv(conn, SAMPLE / "turnover_outcomes.csv")
        rows = _outcomes(conn)
    assert (first.accepted, first.rejected, first.status) == (5, 0, "ok")
    assert (second.accepted, second.duplicates) == (0, 5)
    assert len(rows) == 5
    assert rows["sample-002"]["qa_pass"] == 0 and rows["sample-002"]["late_ready_minutes"] == 20
    assert rows["sample-004"]["service_type"] == "spa"


@pytest.mark.parametrize("preset,file,expected", [
    ("turno", "turno_export.csv", {"T-1001": ("summit_haus", 210.0, 760.0),
                                    "T-1002": ("cloud_9", 195.0, 695.0)}),
    ("breezeway_export", "breezeway_export.csv", {"BW-77": ("overlook_ridge", 240.0, 730.0),
                                                   "BW-78": ("overlook_ridge", 40.0, 60.0)}),
    ("guesty_tasks_export", "guesty_tasks_export.csv", {"gt-1": ("cloud_9", 220.0, 690.0)}),
])
def test_vendor_presets_map_headers(ops_db, preset, file, expected):
    with connect(ops_db) as conn:
        result = import_csv(conn, SAMPLE / file, preset=preset)
        rows = _outcomes(conn)
    assert result.rejected == 0
    assert set(rows) == set(expected)  # cancelled Turno row skipped
    for task_id, (pid, minutes, cost) in expected.items():
        assert rows[task_id]["property_id"] == pid
        assert rows[task_id]["actual_minutes"] == pytest.approx(minutes)
        assert rows[task_id]["cost"] == cost
        assert rows[task_id]["source"] == f"csv:{preset}"
    if preset == "breezeway_export":
        assert rows["BW-78"]["service_type"] == "inspection"


def test_unknown_property_rows_are_rejected_not_guessed(ops_db, tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("property,task_id,service_date,cost\nMystery Chalet,z1,2026-01-01,500\n"
                 "cloud_9,z2,2026-01-02,600\n")
    with connect(ops_db) as conn:
        result = import_csv(conn, f)
    assert (result.accepted, result.rejected, result.status) == (1, 1, "partial")
    assert "Mystery Chalet" in result.errors[0]


def test_capacity_and_ledger_and_asset_csvs(ops_db):
    with connect(ops_db) as conn:
        cap = import_csv(conn, SAMPLE / "capacity.csv", kind="capacity")
        led = import_csv(conn, SAMPLE / "owner_ledger.csv", kind="ledger")
        led_again = import_csv(conn, SAMPLE / "owner_ledger.csv", kind="ledger")
        ev = import_csv(conn, SAMPLE / "asset_events.csv", kind="asset_events")
        reading = json.loads(conn.execute("SELECT reading_json FROM asset_health_events").fetchone()[0])
    assert cap.accepted == 2 and led.accepted == 2 and led_again.duplicates == 2 and ev.accepted == 1
    assert reading == {"temp_f": 52.0}


def test_manual_source_snapshots_the_roster(ops_db):
    with connect(ops_db) as conn:
        result = import_manual(conn, date(2026, 12, 24), date(2026, 12, 26), as_of=date(2026, 12, 1))
        n = conn.execute("SELECT COUNT(*) FROM operations_capacity_snapshots WHERE source='manual'").fetchone()[0]
        profiles = conn.execute("SELECT COUNT(*) FROM property_operations_profile").fetchone()[0]
    assert result.status == "ok" and n == 6 and profiles == 3


def test_unconfigured_api_sources_report_cleanly(ops_db, monkeypatch):
    for var in ("BREEZEWAY_CLIENT_ID", "BREEZEWAY_CLIENT_SECRET", "TURNO_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("src.pms.guesty.load_dotenv", lambda *a, **k: None)
    with connect(ops_db) as conn:
        bw = import_breezeway(conn, date(2026, 1, 1), date(2026, 1, 31))
        tn = import_turno(conn, date(2026, 1, 1), date(2026, 1, 31))
        rows = {s.name: s for s in status(conn)}
    assert bw.status == "unconfigured" and tn.status == "unconfigured"
    assert rows["breezeway"].configured is False
    assert rows["breezeway"].last_run["status"] == "unconfigured"


GUESTY_TASKS = [
    {"_id": "g1", "status": "completed", "type": "cleaning", "listingId": "listing-312",
     "startTime": "2026-01-04T10:30:00Z", "endTime": "2026-01-04T14:30:00Z",
     "mustFinishBefore": "2026-01-04T15:00:00Z", "plannedDuration": 240, "assigneeId": "a1"},
    {"_id": "g2", "status": "pending", "listingId": "listing-312", "startTime": "2026-01-05T10:30:00Z"},
    {"_id": "g3", "status": "completed", "listing": {"listingId": "listing-unknown"},
     "startTime": "2026-01-05T10:30:00Z", "endTime": "2026-01-05T11:00:00Z"},
]


def test_guesty_tasks_normalize_duration_and_lateness(ops_db):
    calls = []

    def fake_get(path, **params):
        calls.append((path, params))
        return {"results": GUESTY_TASKS} if params["skip"] == 0 else {"results": []}

    with connect(ops_db) as conn:
        result = import_guesty_tasks(conn, date(2026, 1, 1), date(2026, 1, 31), get=fake_get)
        rows = _outcomes(conn)
    assert calls[0][0] == "/v1/tasks-open-api/tasks" and "columns" in calls[0][1]
    assert (result.accepted, result.rejected) == (1, 1)
    g1 = rows["g1"]
    assert g1["actual_minutes"] == 240 and g1["late_ready_minutes"] == -30
    assert g1["cost"] is None and g1["service_type"] == "turnover"


def test_breezeway_maps_homes_then_tasks(ops_db):
    def fake_get(path, **params):
        if path == "/property":
            return {"results": [{"id": 11, "reference_property_id": "listing-300", "name": "x"},
                                {"id": 12, "reference_property_id": "other", "name": "Not ours"}],
                    "total_pages": 1}
        assert path == "/task/" and params["home_id"] == 11
        assert params["scheduled_date"] == "2026-01-01,2026-01-31"
        return {"results": [
            {"id": 501, "home_id": 11, "type_department": "housekeeping", "scheduled_date": "2026-01-06",
             "started_at": "2026-01-06T10:30:00", "finished_at": "2026-01-06T14:00:00",
             "total_cost": "712.50", "type_task_status": {"stage": "finished"}},
            {"id": 502, "home_id": 11, "type_department": "housekeeping", "scheduled_date": "2026-01-07",
             "type_task_status": {"stage": "in_progress"}},
        ], "total_pages": 1}

    with connect(ops_db) as conn:
        result = import_breezeway(conn, date(2026, 1, 1), date(2026, 1, 31), get=fake_get)
        rows = _outcomes(conn)
    assert result.accepted == 1
    assert rows["501"]["property_id"] == "overlook_ridge"
    assert rows["501"]["actual_minutes"] == 210 and rows["501"]["cost"] == 712.5


def test_turno_normalizer_accepts_several_spellings(ops_db):
    def fake_get(path, **params):
        return {"data": [
            {"id": 9, "status": "completed", "date": "2026-01-08", "price": 745,
             "property": {"name": "Cloud 9"}, "started_at": "2026-01-08T10:00:00",
             "completed_at": "2026-01-08T13:30:00"},
            {"id": 10, "status": "canceled", "date": "2026-01-09", "property": {"name": "Cloud 9"}},
        ], "meta": {"last_page": 1}}

    with connect(ops_db) as conn:
        result = import_turno(conn, date(2026, 1, 1), date(2026, 1, 31), get=fake_get)
        rows = _outcomes(conn)
    assert result.accepted == 1 and rows["9"]["actual_minutes"] == 210 and rows["9"]["cost"] == 745


def test_api_shape_error_fails_closed(ops_db):
    with connect(ops_db) as conn:
        result = import_guesty_tasks(conn, date(2026, 1, 1), date(2026, 1, 31),
                                     get=lambda path, **p: "not json we know")
        n = conn.execute("SELECT COUNT(*) FROM turnover_outcomes").fetchone()[0]
    assert result.status == "failed" and n == 0


def test_task_webhooks_replay_to_the_same_outcome(ops_db):
    with connect(ops_db) as conn:
        record_delivery(conn, event_id="e1", event_type="task.updated",
                        payload={"task": {**GUESTY_TASKS[0], "status": "in progress"}})
        record_delivery(conn, event_id="e2", event_type="task.updated", payload={"task": GUESTY_TASKS[0]})
        first = import_task_webhooks(conn)
        again = import_task_webhooks(conn)
        rows = _outcomes(conn)
    assert first.accepted == 1 and again.duplicates == 1
    assert rows["g1"]["source"] == "guesty_tasks"


def test_telemetry_derives_severity_and_escalates_only_to_at_risk(ops_db):
    assert derive_severity("heat", {"temp_f": 44}, {}) == "critical"
    assert derive_severity("heat", {"temp_f": 50}, {}) == "warn"
    assert derive_severity("lock", {"battery_pct": 12}, {}) == "warn"
    assert derive_severity("water", {"leak": True}, {}) == "critical"
    with connect(ops_db) as conn:
        result = import_telemetry(conn, SAMPLE / "telemetry_sample.json")
        again = import_telemetry(conn, SAMPLE / "telemetry_sample.json")
        cloud = current_state(conn, "cloud_9", "2026-12-31T00:00:00")
        summit = current_state(conn, "summit_haus", "2026-12-31T00:00:00")
    assert result.accepted == 2 and again.duplicates == 2
    assert cloud.state == "at_risk" and cloud.actor == "telemetry"
    assert summit.state == "ready"  # a warn reading changes nothing
