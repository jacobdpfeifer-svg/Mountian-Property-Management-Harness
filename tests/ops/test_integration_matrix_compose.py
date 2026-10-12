"""Stage 3 integration matrix: readiness x autonomy x night type x direction through compose.

Every cell runs `recommend_night` twice on the same database: once with
`operations.readiness_gate` off (the ops-disabled baseline) and once with it on.
The contract under test (docs/rules/OPERATIONS.md):

1. Ops only restricts: it never raises a price, never lowers one because
   feasibility is low, and never grants autonomy.
2. at_risk / inspection_required demote handle -> suggest; inspection_required
   blocks upward moves; out_of_service / remediation block the night.
3. A readiness hold never lands a price outside the floor or the move cap.
4. A restricting state shows a `readiness` reason whose contribution is the
   dollar effect of the hold.
5. No ops data (or a ready state) is byte-identical to ops disabled.
"""

from __future__ import annotations

import copy
import sqlite3
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.compose import recommend_night
from src.config import load_policy
from src.db import connect, init_db
from src.features import build_features_for_property
from src.guardrails import DataHealth
from src.ingest import CsvIngestAdapter
from src.ops import AssetEvent
from src.ops.db import record_asset_event
from src.ops.readiness import transition

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample"
PID = "aspen_glow"
AS_OF = date(2026, 11, 1)
STAY = date(2026, 12, 5)
EVENT_AT = datetime(2026, 10, 31, 9, 0)

STATES = ("none", "ready", "at_risk", "inspection_required", "out_of_service",
          "remediation_in_progress", "verified_ready")
LEVELS = ("watch", "suggest", "handle", "escalate")
NIGHTS = ("peak_blackout", "normal_peak", "shoulder", "orphan_gap")
DIRECTIONS = ("up", "down", "flat")
RESTRICTING = {"at_risk", "inspection_required", "out_of_service", "remediation_in_progress"}
HUMAN = "Dana Ops"


def _event(conn, system: str = "spa", severity: str = "critical", source: str = "manual") -> str:
    event_id, _ = record_asset_event(conn, AssetEvent(
        property_id=PID, system_type=system, observed_at=EVENT_AT.isoformat(),
        severity=severity, source_type=source, source_ref=f"matrix:{system}:{severity}",
        effective_from=(STAY - timedelta(days=1)).isoformat(),
        effective_to=(STAY + timedelta(days=1)).isoformat(),
    ))
    return event_id


def _put_state(conn, state: str) -> None:
    """Reach `state` for STAY through legal, evidenced transitions only."""
    if state == "none":
        return
    window = {"effective_from": STAY - timedelta(days=1), "effective_to": STAY + timedelta(days=1)}
    ev = _event(conn)
    t = EVENT_AT
    step = timedelta(minutes=5)
    if state in ("ready", "verified_ready", "at_risk"):
        transition(conn, PID, "at_risk", evidence_event_id=ev, actor="telemetry", at=t, **window)
        if state == "at_risk":
            return
        transition(conn, PID, "verified_ready", evidence_event_id=ev, actor=HUMAN, at=t + step,
                   **window)
        if state == "ready":
            transition(conn, PID, "ready", evidence_event_id=ev, actor=HUMAN, at=t + 2 * step,
                       **window)
        return
    if state == "inspection_required":
        transition(conn, PID, state, evidence_event_id=ev, actor=HUMAN, at=t, **window)
        return
    transition(conn, PID, "out_of_service", evidence_event_id=ev, actor=HUMAN, at=t, **window)
    if state == "remediation_in_progress":
        transition(conn, PID, state, evidence_event_id=ev, actor=HUMAN, at=t + step, **window)


@pytest.fixture(scope="module")
def state_dbs(tmp_path_factory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("matrix")
    template = root / "template.db"
    init_db(template)
    with connect(template) as conn:
        CsvIngestAdapter(
            properties_csv=SAMPLE / "properties.csv",
            inventory_csv=SAMPLE / "nightly_inventory.csv",
            comps_csv=SAMPLE / "comps.csv",
            demand_csv=SAMPLE / "demand_signals.csv",
            inquiries_csv=SAMPLE / "booking_inquiries.csv",
        ).load_all(conn)
    out = {}
    for state in STATES:
        path = root / f"{state}.db"
        with sqlite3.connect(template) as src, sqlite3.connect(path) as dst:
            src.backup(dst)
        with connect(path) as conn:
            _put_state(conn, state)
            conn.commit()
        out[state] = path
    return out


@pytest.fixture(autouse=True)
def _memory_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MONTLUXE_MEMORY_ROOT", str(tmp_path / "memroot"))


def _policy(gate: bool) -> dict:
    policy = copy.deepcopy(load_policy())
    policy.setdefault("operations", {})["readiness_gate"] = gate
    # Let the matrix reach `handle`; the sample data has thin ceilings.
    policy["autonomy"]["require_ceiling_confidence"] = 0.0
    policy["autonomy"]["max_level"] = "handle"
    return policy


def _night(conn, kind: str):
    feat = build_features_for_property(conn, PID, STAY, STAY, policy=load_policy())[0]
    feat = replace(feat, status="available")
    if kind == "peak_blackout":
        return replace(feat, season="peak_ski", demand_strength=0.95, demand_event="Holiday")
    if kind == "normal_peak":
        return replace(feat, season="peak_ski", demand_strength=0.6)
    if kind == "shoulder":
        return replace(feat, season="shoulder_spring", demand_strength=0.2)
    return replace(feat, is_orphan_gap=True, gap_size=1, min_stay=3)


def _rec(conn, feat, gate: bool, level: str):
    health = DataHealth(level, 0.0, 0.0, 1.0, 30, [])
    return recommend_night(conn, feat, policy=_policy(gate), health=health, run_id="matrix",
                           as_of=AS_OF)


def _listed_for(conn, feat, direction: str, level: str) -> float:
    """Pick a listed price so the ops-disabled engine moves in `direction`."""
    listed = float(feat.listed_price or 700.0)
    for _ in range(12):  # walk to the engine's fixed point
        nxt = _rec(conn, replace(feat, listed_price=listed), False, level).recommended_price
        if abs(nxt - listed) < 0.01:
            break
        listed = nxt
    if direction == "flat":
        return listed
    return round(listed * (0.85 if direction == "up" else 1.2), 0)


def _move_band(listed: float, policy: dict) -> tuple[float, float]:
    g = policy["guardrails"]
    upper = min(listed * (1 + g["max_increase_pct"]), listed + g["max_abs_move"])
    lower = max(listed * (1 - g["max_decrease_pct"]), listed - g["max_abs_move"])
    return lower, upper


def _comparable(rec) -> dict:
    return asdict(rec)


@pytest.mark.parametrize("direction", DIRECTIONS)
@pytest.mark.parametrize("night", NIGHTS)
@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("state", STATES)
def test_readiness_matrix(state_dbs, state, level, night, direction):
    with connect(state_dbs[state]) as conn:
        feat = _night(conn, night)
        feat = replace(feat, listed_price=_listed_for(conn, feat, direction, level))
        inv_sql = ("SELECT property_id, stay_date, status, listed_price, min_stay "
                   "FROM nightly_inventory ORDER BY property_id, stay_date")
        inv_before = [tuple(r) for r in conn.execute(inv_sql).fetchall()]
        base = _rec(conn, feat, False, level)
        rec = _rec(conn, feat, True, level)
        inv_after = [tuple(r) for r in conn.execute(inv_sql).fetchall()]
    assert inv_after == inv_before, "compose must never write inventory"
    assert base is not None and rec is not None
    listed = float(feat.listed_price)
    codes = [r["code"] for r in rec.reasons]

    # 5. No restricting state: byte-identical to ops disabled.
    if state not in RESTRICTING:
        assert _comparable(rec) == _comparable(base)
        return

    # 1. Ops only restricts.
    assert rec.recommended_price <= base.recommended_price + 0.01
    if state != "inspection_required":
        assert rec.recommended_price == base.recommended_price
    assert not (rec.autonomy_level == "handle"), "a restricting state must never leave handle"
    if base.autonomy_level != "handle":
        assert rec.autonomy_level in (base.autonomy_level, "escalate")

    # 2. State-specific effects.
    held = min(base.recommended_price, listed)
    floor_conflict = state == "inspection_required" and held < base.floor_price
    if state in ("at_risk", "inspection_required") and base.autonomy_level == "handle":
        assert rec.autonomy_level == ("escalate" if floor_conflict else "suggest")
    if state == "inspection_required":
        # Hold at listed, never below the floor; a floor above listed is a human call.
        assert rec.recommended_price == pytest.approx(max(held, base.floor_price))
        if floor_conflict:
            assert rec.autonomy_level == "escalate"
    if state in ("out_of_service", "remediation_in_progress"):
        assert rec.status == "blocked" and rec.autonomy_level == "escalate"

    # 3. A readiness hold never lands outside a limit the baseline respected.
    policy = _policy(True)
    lower, upper = _move_band(listed, policy)
    if base.recommended_price >= base.floor_price - 0.01:
        assert rec.recommended_price >= rec.floor_price - 0.01, (
            f"readiness hold put ${rec.recommended_price:.0f} below floor ${rec.floor_price:.0f}")
    if lower - 0.01 <= base.recommended_price <= upper + 0.01:
        assert lower - 0.01 <= rec.recommended_price <= upper + 0.01

    # 4. The readiness reason is shown with its dollar effect.
    assert "readiness" in codes, f"readiness reason ranked out: {codes}"
    reason = next(r for r in rec.reasons if r["code"] == "readiness")
    assert reason["contribution"] == pytest.approx(
        round(rec.recommended_price - base.recommended_price, 2), abs=0.01)


def test_readiness_reason_is_never_ranked_out(state_dbs):
    """An orphan gap on a guardrail night already pins min_stay and guardrail.
    A tighter reason budget (or one more pinned reason) must not drop readiness."""
    with connect(state_dbs["at_risk"]) as conn:
        feat = replace(_night(conn, "orphan_gap"), listed_price=300.0)
        policy = _policy(True)
        policy.setdefault("explain", {})["max_reasons"] = 2
        rec = recommend_night(conn, feat, policy=policy,
                              health=DataHealth("handle", 0.0, 0.0, 1.0, 30, []),
                              run_id="matrix", as_of=AS_OF)
    codes = [r["code"] for r in rec.reasons]
    assert codes[0] == "readiness", codes


class _SpyAdapter:
    """Dry-run adapter that records every payload it is handed."""

    name = "dry_run"

    def __init__(self):
        self.calls = []

    def fetch_calendar(self, property_id, start, end):
        return []

    def push_rate(self, property_id, stay_date, price, min_stay=None):
        from src.pms import PushResult

        self.calls.append((property_id, stay_date, price, min_stay))
        return PushResult(property_id, stay_date, None, price, True, "dry_run")


@pytest.mark.parametrize("state", STATES)
def test_push_never_writes_a_restricted_night(state_dbs, state):
    """Stage 3 push seam: with health granting handle, a restricted night is
    never handed to the adapter, and the adapter has no availability write."""
    from src.pms import DryRunAdapter, push_recommendations

    with connect(state_dbs[state]) as conn:
        feat = _night(conn, "shoulder")
        feat = replace(feat, listed_price=_listed_for(conn, feat, "down", "handle"))
        rec = _rec(conn, feat, True, "handle")
        spy = _SpyAdapter()
        counts = push_recommendations(conn, [rec], spy, "handle", policy=_policy(True))
    if state in RESTRICTING:
        assert spy.calls == [] and counts["applied"] == 0
    else:
        assert len(spy.calls) == 1
    # The PMS contract has no availability, block, or reservation write at all.
    surface = {n for n in dir(DryRunAdapter) if not n.startswith("_")}
    assert surface == {"name", "fetch_calendar", "push_rate"}
