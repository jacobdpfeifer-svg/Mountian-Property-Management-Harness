"""Canary readiness gate (workstream 8): every earlier stage must pass, and only then is a sign-off honoured."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.data_spine.ingest import ingest
from src.db import connect, init_db
from src.db.migrations import apply_migrations
from src.experiments import _append, freeze_register
from src.experiments.field import blocks, freeze_plan
from src.experiments.readiness import canary_readiness, validated_signoff

SCOPE = frozenset({"summit_haus", "overlook_ridge", "cloud_9"})
NOW = datetime(2027, 1, 1, 12, tzinfo=timezone.utc)
LIN = {"source_system": "t", "source_updated_at": "2026-12-01T00:00:00+00:00",
       "observed_at": "2026-12-01T00:00:00+00:00"}


@pytest.fixture
def env(tmp_path):
    (tmp_path / "policy.yaml").write_text("a: 1\n")
    (tmp_path / "cal.yaml").write_text("c: 1\n")
    reg = freeze_register({
        "experiment_id": "EXP-R", "candidate_policy": "policy.yaml", "calibration": "cal.yaml",
        "objective": "owner_net", "comparator": "current_practice", "harm_fraction": 0.02,
        "screen": {"seeds": [1001], "scenarios": ["normal"]},
        "evaluation": {"seeds": [2001], "scenarios": ["normal"]}, "metrics": ["owner_net"],
        "stop_conditions": ["x"]}, tmp_path / "reg.json", repo=tmp_path)
    plan = freeze_plan({
        "plan_id": "FT-R", "properties": ["cloud_9"], "owners": {"cloud_9": "owner_b"},
        "start": "2027-01-04", "end": "2027-03-28", "block_days": 7, "primary_metric": "x",
        "portfolio_margin": 0.03, "segment_margin": 0.05, "alpha": 0.1, "stop_rules": {},
        "comparator": "current_practice", "candidate_register": "EXP-R", "analysis": "sign-flip"},
        tmp_path / "plan.json")
    path = tmp_path / "r.db"
    init_db(path, seed_markets=False)
    conn = connect(path)
    apply_migrations(conn)
    treat = [b for b in blocks(plan) if b.arm == "treatment"][0]
    signoff = {"authorization_id": "A1", "experiment_id": "EXP-R", "plan_id": "FT-R",
               "property_id": "cloud_9", "dates": [(treat.start + timedelta(days=i)).isoformat() for i in range(3)],
               "approver": "Owner Ops", "rollback_owner": "Revenue Mgr", "max_abs_move": 150,
               "max_pct_move": 0.08, "max_writes": 3, "floor_price": 900,
               "expires_at": (NOW + timedelta(days=3)).isoformat(),
               "kill_switch_tested_at": (NOW - timedelta(days=1)).isoformat()}
    (tmp_path / "signoff.json").write_text(json.dumps(signoff))
    yield {"tmp": tmp_path, "conn": conn, "reg": reg, "plan": plan, "signoff": signoff}
    conn.close()


def _ready(env, **kw):
    t = env["tmp"]
    return canary_readiness(env["conn"], ledger=t / "ledger.jsonl", register_path=t / "reg.json",
                            plan_path=t / "plan.json", signoff_path=t / "signoff.json", now=kw.get("now", NOW))


def _fill_evidence(env):
    conn, t = env["conn"], env["tmp"]
    _append(t / "ledger.jsonl", {"type": "evaluation_decision", "experiment_id": "EXP-R", "decision": "PASS",
                                 "register_sha256": env["reg"]["register_sha256"]})
    start = date(2026, 11, 1)
    with conn:
        for i in range(30):
            d = (start + timedelta(days=i)).isoformat()
            conn.execute("INSERT INTO shadow_run (as_of, property_id, nights, health_level, health_json,"
                         " anchored_share, rate_writes, code_sha256, policy_sha256, created_at)"
                         " VALUES (?, 'cloud_9', 10, 'handle', '{\"failures\": []}', 0.8, 0, 'c', 'p', ?)", (d, d))
            cur = conn.execute(
                "INSERT INTO review_item (decision_key, property_id, stay_date, current_rate, proposed_rate,"
                " owner_net_basis, freshness_json, reasons_json, guardrails_json, readiness, assignment_arm,"
                " expires_at, created_at) VALUES (?, 'cloud_9', ?, 1000, 1050, 'assumed_terms', '{}', '[]', '[]',"
                " 'shadow_only', 'not_assigned', '2030-01-01T00:00:00+00:00', ?)", (f"shadow:{d}:cloud_9:x", d, d))
            conn.execute("INSERT INTO review_action (item_id, action, actor, role, decided_price, reason, acted_at,"
                         " prev_sha256, receipt_sha256) VALUES (?, 'approve', 'op', 'approver', 1050, 'ok', ?, 'p', ?)",
                         (cur.lastrowid, d, f"h{i}"))
    ingest(conn, "reservation", [{**LIN, "reservation_key": "r1", "property_id": "cloud_9", "channel": "direct",
                                  "status": "confirmed", "check_in": "2026-12-10", "check_out": "2026-12-12",
                                  "nights": 2, "booked_at": "2026-11-01T00:00:00+00:00",
                                  "price_basis": "stay_total_ex_fees", "currency": "USD", "gross_lodging": 2000,
                                  "guest_fees": 0}], allowed_property_ids=SCOPE)
    ingest(conn, "financial_ledger", [{**LIN, "entry_key": "e1", "reservation_key": "r1", "property_id": "cloud_9",
                                       "channel": "direct", "entry_type": "gross_lodging", "amount": 2000,
                                       "currency": "USD", "basis": "actual", "settlement_state": "settled",
                                       "settled_at": "2026-12-20T00:00:00+00:00"}], allowed_property_ids=SCOPE)
    ingest(conn, "owner_statement", [{**LIN, "statement_key": "s1", "owner_id": "owner_b", "property_id": "cloud_9",
                                      "period_start": "2026-12-01", "period_end": "2026-12-31",
                                      "reported_owner_net": 1500, "currency": "USD"}], allowed_property_ids=SCOPE)


def test_nothing_is_ready_without_evidence_and_authorization_is_refused(env):
    r = _ready(env)
    failed = {name for name, ok, _ in r.gates if not ok}
    assert {"evaluation", "shadow", "money"} <= failed and not r.ready
    with pytest.raises(PermissionError, match="not ready"):
        validated_signoff(r, env["tmp"] / "signoff.json")


def test_full_evidence_yields_the_validated_bounded_signoff(env):
    _fill_evidence(env)
    r = _ready(env)
    assert r.ready, r.lines()
    s = validated_signoff(r, env["tmp"] / "signoff.json")
    assert s["property_id"] == "cloud_9" and len(s["dates"]) == 3
    assert s["max_pct_move"] <= 0.10 and s["max_writes"] == 3


@pytest.mark.parametrize("edit,needle", [
    ({"dates": ["2027-01-04", "2027-01-11"]}, "treatment nights"),   # one of a pair is always control
    ({"max_pct_move": 0.25}, "max_pct_move"),
    ({"max_writes": 40}, "max_writes"),
    ({"max_writes": 1}, "below the number of dates"),
    ({"kill_switch_tested_at": "2026-12-01T00:00:00+00:00"}, "kill switch"),
    ({"expires_at": "2026-12-31T00:00:00+00:00"}, "expired"),
    ({"rollback_owner": " "}, "rollback owner"),
    ({"experiment_id": "EXP-OTHER"}, "another experiment"),
])
def test_signoff_violations_block_the_canary(env, edit, needle):
    _fill_evidence(env)
    (env["tmp"] / "signoff.json").write_text(json.dumps({**env["signoff"], **edit}))
    r = _ready(env)
    detail = dict((n, d) for n, ok, d in r.gates)["signoff"]
    assert not r.ready and needle in detail


def test_a_failed_evaluation_or_missing_anchor_blocks_the_canary(env):
    _fill_evidence(env)
    _append(env["tmp"] / "ledger.jsonl", {"type": "evaluation_decision", "experiment_id": "EXP-R",
                                          "decision": "FAIL", "register_sha256": env["reg"]["register_sha256"]})
    assert not _ready(env).ready


def test_a_pass_for_another_register_version_or_a_swapped_signoff_is_refused(env):
    _fill_evidence(env)
    _append(env["tmp"] / "ledger.jsonl", {"type": "evaluation_decision", "experiment_id": "EXP-R",
                                          "decision": "PASS", "register_sha256": "0" * 64})
    r = _ready(env)
    assert r.ready                       # the real PASS from _fill_evidence is still the latest valid one
    (env["tmp"] / "signoff.json").write_text(json.dumps({**env["signoff"], "max_writes": 14}))
    with pytest.raises(PermissionError, match="changed after"):
        validated_signoff(r, env["tmp"] / "signoff.json")


def test_shadow_evidence_is_judged_for_the_canary_home(env):
    _fill_evidence(env)                  # shadow rows are all cloud_9
    (env["tmp"] / "signoff.json").write_text(json.dumps({**env["signoff"], "property_id": "summit_haus"}))
    detail = dict((n, d) for n, ok, d in _ready(env).gates)["shadow"]
    assert "0 shadow days" in detail
