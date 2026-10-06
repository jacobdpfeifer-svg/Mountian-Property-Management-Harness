"""Property-based tests for the readiness state machine (audit Stage 2C).

Random sequences of asset events and attempted transitions, by automatic and
human actors, over random night windows. Illegal attempts are expected to
raise ReadinessError; the invariants below must hold for whatever succeeds.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.ops import AssetEvent
from src.ops.db import ensure_ops_tables, record_asset_event
from src.ops.readiness import (
    _RANK,
    AUTO_ACTORS,
    RESTRICTING,
    STATES,
    VERIFIED_READY,
    ReadinessError,
    current_state,
    state_for_night,
    transition,
)

PID = "cloud_9"
T0 = datetime(2026, 12, 1, 8, 0)
NIGHTS = [date(2026, 12, 1) + timedelta(days=i) for i in range(14)]
SYSTEMS = ("spa", "heat", "snow_access", "water")
ACTORS = ("signal", "telemetry", "breezeway", "Dana Ops", "Sam Field", "operator", "sensor_check")
POLICY = {"readiness": {"sensor_verification": {"spa": {"min_temp_f": 95}}}}

step = st.fixed_dictionaries({
    "system": st.sampled_from(SYSTEMS),
    "severity": st.sampled_from(("warn", "critical")),
    "source": st.sampled_from(("sensor", "manual", "signal")),
    "temp": st.integers(60, 110),
    "to_state": st.sampled_from(STATES),
    "actor": st.sampled_from(ACTORS),
    "start": st.integers(0, 10),
    "length": st.integers(0, 4),
    "open_ended": st.booleans(),
    "reuse_event": st.booleans(),
    "minutes": st.integers(1, 36 * 60),
})


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_ops_tables(conn)
    return conn


def _snapshot(conn, at: datetime) -> dict[date, str]:
    return {n: state_for_night(conn, PID, n, at).state for n in NIGHTS}


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(step, min_size=1, max_size=12))
def test_readiness_invariants(steps):
    conn = _db()
    at = T0
    events: list[str] = []
    meta: dict[str, tuple[str, str, int]] = {}
    for s in steps:
        at += timedelta(minutes=s["minutes"])
        if events and s["reuse_event"]:
            event_id = events[-1]
        else:
            event_id, _ = record_asset_event(conn, AssetEvent(
                property_id=PID, system_type=s["system"], observed_at=at.isoformat(),
                severity=s["severity"], source_type=s["source"], source_ref=f"h{len(events)}",
                reading={"temp_f": s["temp"]},
            ))
            events.append(event_id)
            meta[event_id] = (s["source"], s["system"], s["temp"])
        start = NIGHTS[s["start"]]
        end = None if s["open_ended"] else start + timedelta(days=s["length"])
        before = _snapshot(conn, at)
        rows_before = conn.execute("SELECT COUNT(*) FROM readiness_transitions").fetchone()[0]
        try:
            transition(conn, PID, s["to_state"], evidence_event_id=event_id, actor=s["actor"],
                       at=at, effective_from=start, effective_to=end, ops_policy=POLICY)
        except ReadinessError:
            # A refused transition writes nothing.
            assert conn.execute("SELECT COUNT(*) FROM readiness_transitions").fetchone()[0] \
                == rows_before
            continue
        after = _snapshot(conn, at)

        # Automatic actors only ever set at_risk and never move a night toward ready.
        if s["actor"] in AUTO_ACTORS:
            assert s["to_state"] == "at_risk"
            for n in NIGHTS:
                assert _RANK[after[n]] >= _RANK[before[n]], (n, before[n], after[n])

        # verified_ready needs a named person or a passing sensor reading.
        if s["to_state"] == VERIFIED_READY:
            assert s["actor"] not in AUTO_ACTORS and s["actor"] != "operator"
            if s["actor"] == "sensor_check":
                source, system, temp = meta[event_id]
                assert source == "sensor" and system == "spa" and temp >= 95

    # Every transition cites an event on this property.
    orphan = conn.execute(
        """SELECT COUNT(*) FROM readiness_transitions t LEFT JOIN asset_health_events e
           ON e.event_id=t.evidence_event_id AND e.property_id=t.property_id
           WHERE e.event_id IS NULL""").fetchone()[0]
    assert orphan == 0

    # The state is derived from history and is the same however it is queried.
    last = conn.execute("SELECT MAX(at) FROM readiness_transitions").fetchone()[0]
    if last:
        as_dt = datetime.fromisoformat(last)
        for n in NIGHTS:
            assert state_for_night(conn, PID, n, as_dt).state == \
                state_for_night(conn, PID, n, last).state
        assert current_state(conn, PID, as_dt).state == current_state(conn, PID, last).state

    # Time passing never counts as recovery: with no new rows, a restricted
    # night stays restricted at any later query time.
    if last:
        now = datetime.fromisoformat(last)
        later = now + timedelta(days=30)
        for n in NIGHTS:
            if state_for_night(conn, PID, n, now).state in RESTRICTING:
                assert state_for_night(conn, PID, n, later).state in RESTRICTING, n


def test_a_property_with_no_events_is_ready_everywhere():
    conn = _db()
    assert {state_for_night(conn, PID, n, T0).state for n in NIGHTS} == {"ready"}
