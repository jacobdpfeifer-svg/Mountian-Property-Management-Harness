"""06I ops restrictions and 06J review queue."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from src.ops.constraint_adapter import (
    authority_for, effective_status, import_ops, restriction_for_night,
)
from src.review import ReviewItem, ReviewRefused, act, enqueue, export, verify_chain
from tests.security.conftest import PROPS

TS = "2026-12-01T00:00:00+00:00"
D = date(2026, 12, 20)


def _task(key, pid="summit_haus", task_type="turn", status="scheduled", day=D, **kw):
    return {"source_system": "fixture", "source_updated_at": kw.pop("updated", TS), "observed_at": TS,
            "task_key": key, "property_id": pid, "task_type": task_type, "service_date": day.isoformat(),
            "status": status, "vendor": "fixture_vendor", "currency": "USD", **kw}


def _constraint(key, ctype="maintenance", active=1, effect="restrict", updated=TS):
    return {"source_system": "fixture", "source_updated_at": updated, "observed_at": TS,
            "constraint_key": key, "property_id": "summit_haus", "constraint_type": ctype,
            "start_date": "2026-12-19", "end_date": "2026-12-21", "effect": effect, "active": active}


class Provider:
    name = "fixture"

    def __init__(self, payload=None, outage=False):
        self.payload, self.outage = payload or {}, outage

    def fetch(self, start, end):
        if self.outage:
            raise TimeoutError("vendor API timed out")
        return self.payload


def test_clear_night_is_ready_and_handle(conn):
    imp = import_ops(conn, Provider({"tasks": [_task("T1")]}), D, D, allowed_property_ids=PROPS)
    r = restriction_for_night(conn, "summit_haus", D, provider_health=imp.health)
    assert (r.restricted, r.readiness, authority_for(r)) == (False, "ready", "handle")


def test_incident_and_incomplete_turn_restrict(conn):
    import_ops(conn, Provider({"tasks": [_task("T1", status="failed"),
                                         _task("I1", task_type="incident", status="in_progress")]}),
               D, D, allowed_property_ids=PROPS)
    r = restriction_for_night(conn, "summit_haus", D)
    assert r.reasons == ("incident_open", "turn_incomplete") and authority_for(r) == "observe"


def test_over_capacity_restricts(conn):
    tasks = [_task(f"T{i}", pid=p) for i, p in enumerate(sorted(PROPS))]
    import_ops(conn, Provider({"tasks": tasks}), D, D, allowed_property_ids=PROPS)
    assert "over_capacity" in restriction_for_night(conn, "cloud_9", D, max_turns_per_day=2).reasons


def test_cancelled_turn_does_not_count_and_lifted_constraint_is_a_new_version(conn):
    import_ops(conn, Provider({"constraints": [_constraint("C1")]}), D, D, allowed_property_ids=PROPS)
    assert restriction_for_night(conn, "summit_haus", D).restricted
    lift = _constraint("C1", active=0, updated="2026-12-02T00:00:00+00:00")
    import_ops(conn, Provider({"constraints": [lift],
                              "tasks": [_task("T1", status="cancelled")]}), D, D, allowed_property_ids=PROPS)
    assert not restriction_for_night(conn, "summit_haus", D, max_turns_per_day=0).restricted
    assert conn.execute("SELECT COUNT(*) FROM dim_listing_constraint").fetchone()[0] == 2


def test_vendor_outage_lowers_authority_not_availability(conn):
    imp = import_ops(conn, Provider(outage=True), D, D, allowed_property_ids=PROPS)
    assert imp.health.state == "missing"
    r = restriction_for_night(conn, "summit_haus", D, provider_health=imp.health)
    assert r.readiness == "unknown" and authority_for(r) == "suggest"


def test_operations_can_never_make_a_night_bookable(conn):
    import_ops(conn, Provider({"constraints": [_constraint("C9", effect="allow")]}), D, D,
               allowed_property_ids=PROPS)
    assert conn.execute("SELECT COUNT(*) FROM dim_listing_constraint").fetchone()[0] == 0
    clear = restriction_for_night(conn, "summit_haus", D)
    for status in ("booked", "blocked"):
        assert effective_status(status, clear) == status
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""INSERT INTO dim_listing_constraint (entity_key, version_no, source_system, source_hash,
            schema_version, source_updated_at, observed_at, ingested_at, batch_id, property_id, constraint_type,
            start_date, end_date, effect, active) VALUES ('x',1,'s','h','1',?,?,?, 'b','summit_haus','owner_block',
            '2026-12-01','2026-12-02','allow',1)""", (TS, TS, TS))


def test_unknown_home_in_ops_feed_quarantines(conn):
    imp = import_ops(conn, Provider({"tasks": [_task("T1", pid="creekside_haven")]}), D, D,
                     allowed_property_ids=PROPS)
    assert imp.health.state == "partial" and imp.quarantined[0]["reasons"] == ["UNKNOWN_IDENTITY"]


# -- review ---------------------------------------------------------------------------

NOW = datetime(2026, 12, 1, 15, tzinfo=timezone.utc)


def _item(key="D1", pid="summit_haus", **over):
    base = dict(decision_key=key, property_id=pid, stay_date="2026-12-20", current_rate=1750.0,
                proposed_rate=1850.0, all_in_price=2210.0, expected_owner_net=1320.0,
                owner_net_basis="assumed_terms", freshness={"pms": "2026-12-01T06:05:00+00:00"},
                confidence=0.6, reasons=["pace behind"], guardrails=[], readiness="ready",
                assignment_arm="not_assigned", expires_at=(NOW + timedelta(hours=12)).isoformat())
    base.update(over)
    return ReviewItem(**base)


def test_review_actions_are_attributable_and_one_per_item(conn):
    i1 = enqueue(conn, _item("D1"), scope_property_ids=PROPS)
    i2 = enqueue(conn, _item("D2"), scope_property_ids=PROPS)
    r1 = act(conn, i1, action="approve", actor="owner-a", role="approver", reason="fits pace", now=NOW)
    r2 = act(conn, i2, action="edit", actor="owner-a", role="approver", reason="hold lower",
             edited_price=1800.0, now=NOW)
    assert r2["prev_sha256"] == r1["receipt_sha256"] and r2["decided_price"] == 1800.0
    with pytest.raises(ReviewRefused, match="already decided"):
        act(conn, i1, action="reject", actor="owner-b", role="approver", reason="x", now=NOW)
    assert verify_chain(conn)


@pytest.mark.parametrize("kw, msg", [
    ({"role": "viewer", "action": "approve"}, "may not"),
    ({"role": "admin", "action": "approve"}, "may not"),
    ({"role": "approver", "action": "edit"}, "positive price"),
    ({"role": "approver", "action": "approve", "reason": " "}, "required"),
])
def test_review_role_and_input_checks(conn, kw, msg):
    i = enqueue(conn, _item(), scope_property_ids=PROPS)
    args = {"actor": "a", "reason": "r", **kw}
    with pytest.raises(ReviewRefused, match=msg):
        act(conn, i, now=NOW, **args)


def test_expired_and_out_of_scope_items_are_refused(conn):
    i = enqueue(conn, _item(), scope_property_ids=PROPS)
    with pytest.raises(ReviewRefused, match="expired"):
        act(conn, i, action="approve", actor="a", role="approver", reason="r", now=NOW + timedelta(days=1))
    with pytest.raises(ReviewRefused, match="outside"):
        enqueue(conn, _item("D9", pid="creekside_haven"), scope_property_ids=PROPS)


def test_export_separates_model_human_and_applied(conn, tmp_path):
    i = enqueue(conn, _item(), scope_property_ids=PROPS)
    act(conn, i, action="edit", actor="owner-a", role="approver", reason="r", edited_price=1800.0, now=NOW)
    enqueue(conn, _item("D2"), scope_property_ids=PROPS)
    data = json.loads(export(conn, tmp_path / "review.json").read_text())
    first, second = data["items"]
    assert data["chain_valid"] is True
    assert (first["model_recommendation"], first["human_price"], first["applied_rate"]) == (1850.0, 1800.0, None)
    assert second["human_decision"] == "pending"
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE review_action SET decided_price = 1")


def test_tampered_chain_is_detected(conn):
    i = enqueue(conn, _item(), scope_property_ids=PROPS)
    act(conn, i, action="approve", actor="a", role="approver", reason="r", now=NOW)
    conn.execute("DROP TRIGGER review_action_no_update")
    conn.execute("UPDATE review_action SET reason='rewritten'")
    assert verify_chain(conn) is False
