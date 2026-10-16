"""Inactive canary: every abort path, read-back, rollback, idempotency."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from src.pms import PushResult
from src.pms.canary import CanaryAuthorization, CanaryChange, CanaryController
from src.security.kill_switch import SwitchState

D1, D2, D3 = date(2027, 1, 12), date(2027, 1, 13), date(2027, 1, 14)
NOW = datetime(2026, 12, 1, tzinfo=timezone.utc)
OPEN = lambda pid: SwitchState(True, "permitted (test)")     # noqa: E731
SHUT = lambda pid: SwitchState(False, "kill switch engaged")  # noqa: E731


class FakeAdapter:
    """In-memory calendar. The only writer these tests use."""
    name, live = "fake", False

    def __init__(self, *, drop_write_on=None, corrupt_field_on=None, fail_write_on=None,
                 fail_rollback=False):
        self.cal = {d: {"date": d.isoformat(), "price": 1000.0, "status": "available",
                        "min_stay": 2, "blocked": False} for d in (D1, D2, D3)}
        self.writes = []
        self.drop_write_on, self.corrupt_field_on = drop_write_on, corrupt_field_on
        self.fail_write_on, self.fail_rollback = fail_write_on, fail_rollback

    def fetch_calendar(self, pid, start, end):
        return [dict(v) for d, v in self.cal.items() if start <= d <= end]

    def push_rate(self, pid, d, price, min_stay=None):
        self.writes.append((d, price))
        is_rollback = price == 1000.0
        if d == self.fail_write_on and not is_rollback:
            return PushResult(pid, d, None, price, False, "failed", "503")
        if is_rollback and self.fail_rollback:
            return PushResult(pid, d, None, price, False, "failed", "rollback refused")
        if d != self.drop_write_on or is_rollback:
            self.cal[d]["price"] = price
        if d == self.corrupt_field_on and not is_rollback:
            self.cal[d]["min_stay"] = 7
        return PushResult(pid, d, None, price, True, "applied")


def _auth(**over):
    base = dict(authorization_id="AUTH-TEST", property_id="summit_haus", dates=(D1, D2, D3),
                approver="named approver", rollback_owner="named owner", max_abs_move=150.0,
                max_pct_move=0.10, max_writes=2, expires_at=NOW + timedelta(days=1), floor_price=900.0)
    base.update(over)
    return CanaryAuthorization(**base)


def _run(scope, adapter=None, auth="default", changes=None, switch=OPEN, health="handle",
         readiness=None, **kw):
    adapter = adapter or FakeAdapter()
    ctl = CanaryController(adapter, scope, switch=switch, now=lambda: NOW)
    changes = changes if changes is not None else [CanaryChange(D1, 1080.0), CanaryChange(D2, 1050.0)]
    readiness = readiness if readiness is not None else {D1: "ready", D2: "ready", D3: "ready"}
    res = ctl.run(_auth() if auth == "default" else auth, changes, health=health, readiness=readiness, **kw)
    return res, adapter


def test_completed_canary_writes_reads_back_and_records(scope):
    res, a = _run(scope)
    assert res.status == "completed" and res.abort_code is None
    assert a.cal[D1]["price"] == 1080.0 and a.cal[D2]["price"] == 1050.0
    assert [e["step"] for e in res.receipt] == [
        "authorized", "snapshot", "dry_run_diff", "written_and_verified", "written_and_verified"]


def test_dry_run_writes_nothing(scope):
    res, a = _run(scope, dry_run_only=True)
    assert res.status == "dry_run" and a.writes == []


@pytest.mark.parametrize("kwargs, code", [
    ({"auth": None}, "NO_AUTHORIZATION"),
    ({"auth": _auth(approver=" ")}, "NO_NAMED_APPROVER"),
    ({"auth": _auth(expires_at=NOW - timedelta(seconds=1))}, "AUTHORIZATION_EXPIRED"),
    ({"auth": _auth(property_id="creekside_haven")}, "SCOPE_MISMATCH"),
    ({"changes": []}, "NO_CHANGES"),
    ({"auth": _auth(max_writes=1)}, "MAX_WRITES_EXCEEDED"),
    ({"changes": [CanaryChange(D1, 1050.0), CanaryChange(D1, 1060.0)]}, "DUPLICATE_DATE"),
    ({"changes": [CanaryChange(date(2027, 2, 1), 1050.0)]}, "DATE_NOT_AUTHORIZED"),
    ({"health": "suggest"}, "STALE_HEALTH"),
    ({"readiness": {D1: "ready", D2: "not_ready"}}, "OPERATIONAL_RESTRICTION"),
    ({"readiness": {D1: "ready"}}, "OPERATIONAL_RESTRICTION"),
    ({"switch": SHUT}, "KILL_SWITCH"),
    ({"changes": [CanaryChange(D1, 1200.0)]}, "MOVE_CAP_EXCEEDED"),
    ({"changes": [CanaryChange(D1, 1140.0)], "auth": _auth(max_abs_move=500.0)}, "MOVE_CAP_EXCEEDED"),
    ({"changes": [CanaryChange(D1, -1.0)]}, "BELOW_FLOOR"),
    ({"changes": [CanaryChange(D1, 950.0)], "auth": _auth(floor_price=980.0)}, "BELOW_FLOOR"),
])
def test_preflight_aborts_never_write(scope, kwargs, code):
    res, a = _run(scope, **kwargs)
    assert (res.status, res.abort_code) == ("aborted", code)
    assert a.writes == []


def test_missing_snapshot_aborts(scope):
    a = FakeAdapter()
    del a.cal[D2]
    res, _ = _run(scope, adapter=a)
    assert res.abort_code == "SNAPSHOT_MISSING" and a.writes == []


def test_unavailable_night_is_never_written(scope):
    a = FakeAdapter()
    a.cal[D1]["status"] = "booked"
    res, _ = _run(scope, adapter=a)
    assert res.abort_code == "NIGHT_NOT_AVAILABLE" and a.writes == []


def test_live_adapter_requires_operator_signed_authorization(scope):
    a = FakeAdapter()
    a.live = True
    res, _ = _run(scope, adapter=a)
    assert res.abort_code == "LIVE_ADAPTER_UNSIGNED" and a.writes == []


def test_real_kill_switch_keeps_controller_inactive(scope, control):
    a = FakeAdapter()
    ctl = CanaryController(a, scope, now=lambda: NOW)   # default switch = the real one
    res = ctl.run(_auth(), [CanaryChange(D1, 1050.0)], health="handle", readiness={D1: "ready"})
    assert res.abort_code == "KILL_SWITCH" and a.writes == []


@pytest.mark.parametrize("adapter_kw, code", [
    ({"drop_write_on": D2}, "READBACK_MISMATCH"),
    ({"corrupt_field_on": D2}, "NON_PRICE_FIELD_CHANGED"),
    ({"fail_write_on": D2}, "WRITE_FAILED"),
])
def test_post_write_failures_roll_back_everything_written(scope, adapter_kw, code):
    a = FakeAdapter(**adapter_kw)
    res, _ = _run(scope, adapter=a)
    assert (res.status, res.abort_code) == ("aborted", code)
    assert a.cal[D1]["price"] == 1000.0 and a.cal[D2]["price"] == 1000.0
    assert set(res.rolled_back) == set(res.written)


def test_kill_switch_engaged_mid_canary_aborts_and_rolls_back(scope):
    calls = {"n": 0}

    def flips(pid):
        calls["n"] += 1
        return SwitchState(calls["n"] <= 2, "engaged mid-run")   # preflight + first write only

    res, a = _run(scope, switch=flips)
    assert res.abort_code == "KILL_SWITCH"
    assert a.cal[D1]["price"] == 1000.0 and res.rolled_back == [D1.isoformat()]


def test_failed_rollback_is_reported_not_hidden(scope):
    a = FakeAdapter(drop_write_on=D2, fail_rollback=True)
    res, _ = _run(scope, adapter=a)
    assert res.status == "aborted_rollback_failed"
    assert res.receipt[-1]["step"] == "rollback" and res.receipt[-1]["failed"]


def test_idempotent_rerun_does_not_rewrite(scope):
    keys: set[str] = set()
    a = FakeAdapter()
    for _ in range(2):
        ctl = CanaryController(a, scope, switch=OPEN, completed_keys=keys, now=lambda: NOW)
        res = ctl.run(_auth(), [CanaryChange(D1, 1080.0)], health="handle", readiness={D1: "ready"})
        assert res.status == "completed"
    assert a.writes == [(D1, 1080.0)]


def test_no_authorization_object_exists_in_source():
    """Inactive by construction: nothing outside tests builds an authorization."""
    from pathlib import Path
    src = Path(__file__).parents[2] / "src"
    users = [p for p in src.rglob("*.py")
             if "CanaryAuthorization(" in p.read_text() and p.name != "canary.py"]
    assert users == []
    assert "operator_signed=True" not in (src / "pms" / "canary.py").read_text()
