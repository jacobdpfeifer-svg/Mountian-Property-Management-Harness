"""Preregistered field test: freeze, assignment, settled owner-net outcomes, analysis, stop rules."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta

import pytest

from src.data_spine.ingest import ingest
from src.db import connect, init_db
from src.db.migrations import apply_migrations
from src.experiments.field import (
    Block, BlockOutcome, PlanError, analyse, arm_for, block_outcomes, blocks, check_stop_rules,
    freeze_plan, load_plan, paired_effect,
)

SCOPE = frozenset({"summit_haus", "overlook_ridge", "cloud_9"})
OWNERS = {"summit_haus": "owner_a", "overlook_ridge": "owner_a", "cloud_9": "owner_b"}


def _plan(**over):
    base = {"plan_id": "FT-T", "properties": sorted(SCOPE), "owners": OWNERS, "start": "2027-01-04",
            "end": "2027-03-28", "block_days": 7, "primary_metric": "settled owner net per eligible night",
            "portfolio_margin": 0.03, "segment_margin": 0.05, "alpha": 0.10,
            "stop_rules": {"max_pickup_gap": 0.15, "min_nights": 10, "max_cancel_gap": 0.10},
            "comparator": "current_practice", "candidate_register": "EXP-X", "analysis": "sign-flip"}
    base.update(over)
    return base


def test_freeze_validates_and_detects_edits(tmp_path):
    with pytest.raises(PlanError, match="owner"):
        freeze_plan(_plan(owners={"summit_haus": "a"}), tmp_path / "p.json")
    with pytest.raises(PlanError, match="numeric"):
        freeze_plan(_plan(covariate_coefficients={"ly": "TO FIT"}), tmp_path / "x.json")
    with pytest.raises(PlanError, match="status_note"):
        freeze_plan(_plan(status_note="DRAFT"), tmp_path / "y.json")
    freeze_plan(_plan(), tmp_path / "p.json")
    with pytest.raises(PlanError, match="frozen"):
        freeze_plan(_plan(), tmp_path / "p.json")
    body = json.loads((tmp_path / "p.json").read_text())
    body["segment_margin"] = 0.5
    (tmp_path / "p.json").write_text(json.dumps(body))
    with pytest.raises(PlanError, match="edited"):
        load_plan(tmp_path / "p.json")


def test_assignment_is_paired_balanced_deterministic_and_needs_a_frozen_plan(tmp_path):
    with pytest.raises(PlanError, match="frozen"):
        blocks(_plan())
    plan = freeze_plan(_plan(), tmp_path / "p.json")
    bs = blocks(plan)
    assert bs == blocks(load_plan(tmp_path / "p.json"))
    for pid in SCOPE:
        mine = [b for b in bs if b.property_id == pid]
        assert len(mine) == 12                                   # 84 days / 7
        for pair in {b.pair for b in mine}:
            assert sorted(b.arm for b in mine if b.pair == pair) == ["control", "treatment"]
    other = freeze_plan(_plan(plan_id="FT-U"), tmp_path / "q.json")
    assert [b.arm for b in blocks(other)] != [b.arm for b in bs]
    look = arm_for(plan)
    assert look("cloud_9", "2027-01-04") in ("treatment", "control")
    assert look("cloud_9", "2026-12-01") == "not_assigned"


def test_sign_flip_interval_covers_the_true_effect_near_its_nominal_rate():
    rng = random.Random(3)
    hits = 0
    reps = 150
    for _ in range(reps):
        pairs = [(100 + 8 + rng.gauss(0, 30), 100 + rng.gauss(0, 30)) for _ in range(14)]
        e = paired_effect(pairs, alpha=0.10, draws=1500)
        hits += e.lo <= 8 <= e.hi
    assert 0.83 <= hits / reps <= 0.97                           # nominal 90%


def test_too_few_pairs_give_an_unbounded_interval_not_a_false_claim():
    e = paired_effect([(120, 100), (130, 100), (125, 100)], alpha=0.10)
    assert e.lo == float("-inf") and e.hi == float("inf")       # 2/8 = 0.25 > 0.10
    e = paired_effect([(120, 100)] * 5, alpha=0.10)              # 2/32 < 0.10
    assert e.lo > 0


def _outcomes(plan, effect_by_pid, noise=1.0, seed=1):
    rng = random.Random(seed)
    out = []
    for b in blocks(plan):
        base = 100 + rng.gauss(0, noise)
        val = base * (1 + effect_by_pid[b.property_id]) if b.arm == "treatment" else base
        out.append(BlockOutcome(b, 7, val * 7, complete=True))
    return out


def test_analysis_decisions(tmp_path):
    plan = freeze_plan(_plan(), tmp_path / "p.json")
    up = analyse(_outcomes(plan, {p: 0.06 for p in SCOPE}), plan)
    assert up["decision"] == "PROVEN"
    # 12 weeks = 6 pairs per home: too few to show per-home harm at alpha / k, and the
    # analysis says so instead of implying safety.
    short = analyse(_outcomes(plan, {"summit_haus": 0.20, "overlook_ridge": 0.20, "cloud_9": -0.15}), plan)
    assert short["decision"] != "PROVEN" and "harm_note" in short["segments"]["property:cloud_9"]
    # 16 weeks = 8 pairs per home: the one owner paying for the others is caught.
    long_plan = freeze_plan(_plan(plan_id="FT-LONG", end="2027-04-25"), tmp_path / "long.json")
    hurt = analyse(_outcomes(long_plan, {"summit_haus": 0.20, "overlook_ridge": 0.20, "cloud_9": -0.15}),
                   long_plan)
    assert hurt["decision"] == "HARM" and "property:cloud_9" in hurt["why"][0]
    # A single-home owner is the same segment as the home: judged once.
    assert "owner:owner_b" not in hurt["segments"] and "owner:owner_a" in hurt["segments"]
    # A fired stop rule is HARM whatever the money says.
    stopped = analyse(_outcomes(plan, {p: 0.06 for p in SCOPE}), plan, fired_stop_rules=["pickup_gap:cloud_9"])
    assert stopped["decision"] == "HARM"
    # No true effect: never PROVEN, and a false HARM alarm stays rare. Five segment
    # tests (three homes, two owners) put it near 5%; preregistered as intended,
    # because a false alarm costs a re-test while a missed harm costs an owner.
    nulls = [analyse(_outcomes(plan, {p: 0.0 for p in SCOPE}, noise=20, seed=s), plan)["decision"]
             for s in range(200)]
    assert nulls.count("PROVEN") <= 14 and nulls.count("HARM") <= 10     # each about 5% or less


def test_incomplete_pairs_are_left_out_and_reported(tmp_path):
    plan = freeze_plan(_plan(), tmp_path / "p.json")
    outs = _outcomes(plan, {p: 0.06 for p in SCOPE})
    outs[0].complete = False
    res = analyse(outs, plan)
    assert res["incomplete_pairs"] and res["complete_pairs"] == 17


# -- outcomes from the spine ---------------------------------------------------------------

@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "f.db"
    init_db(path, seed_markets=False)
    c = connect(path)
    apply_migrations(c)
    yield c
    c.close()


def _lin(t="2027-01-01T00:00:00+00:00"):
    return {"source_system": "t", "source_updated_at": t, "observed_at": t}


def _stay(conn, key, pid, ci, nights, *, lodging, settled=True, status="confirmed", refund=0.0):
    co = (date.fromisoformat(ci) + timedelta(days=nights)).isoformat()
    ingest(conn, "reservation", [{**_lin(), "reservation_key": key, "property_id": pid, "channel": "direct",
                                  "status": status, "check_in": ci, "check_out": co, "nights": nights,
                                  "booked_at": "2026-12-01T00:00:00+00:00", "price_basis": "stay_total_ex_fees",
                                  "currency": "USD", "gross_lodging": lodging, "guest_fees": 0}],
           allowed_property_ids=SCOPE)
    state = "settled" if settled else "pending"
    lines = [("gross_lodging", lodging), ("management_fee", lodging * 0.25), ("cleaning_cost", 100.0)]
    if refund:
        lines.append(("refund", refund))
    ingest(conn, "financial_ledger", [{
        **_lin(), "entry_key": f"{key}:{k}", "reservation_key": key, "property_id": pid, "channel": "direct",
        "entry_type": k, "amount": a, "currency": "USD", "basis": "actual", "settlement_state": state,
        "settled_at": "2027-03-01T00:00:00+00:00" if settled else None} for k, a in lines],
        allowed_property_ids=SCOPE)


def test_block_outcomes_split_stays_across_blocks_and_wait_for_settlement(conn, tmp_path):
    plan = freeze_plan(_plan(properties=["cloud_9"], owners={"cloud_9": "owner_b"}), tmp_path / "p.json")
    b0, b1 = [b for b in blocks(plan) if b.pair == 0]
    # 4 nights: 2 in the first block, 2 in the second. Net = 1000 - 250 - 100 = 650.
    _stay(conn, "r1", "cloud_9", (b0.end - timedelta(days=1)).isoformat(), 4, lodging=1000.0)
    # Unsettled stay in the second pair: that pair is pending.
    p1 = [b for b in blocks(plan) if b.pair == 1][0]
    _stay(conn, "r2", "cloud_9", p1.start.isoformat(), 2, lodging=800.0, settled=False)
    # An owner block removes nights from the eligible denominator.
    ingest(conn, "listing_constraint", [{**_lin(), "constraint_key": "ob1", "property_id": "cloud_9",
                                         "constraint_type": "owner_block", "start_date": b0.start.isoformat(),
                                         "end_date": (b0.start + timedelta(days=1)).isoformat(),
                                         "effect": "restrict", "active": 1}], allowed_property_ids=SCOPE)
    outs = {(o.block.pair, o.block.start): o for o in block_outcomes(conn, plan)}
    first, second = outs[(0, b0.start)], outs[(0, b1.start)]
    assert first.eligible_nights == 5 and second.eligible_nights == 7
    assert first.owner_net == pytest.approx(325.0) and second.owner_net == pytest.approx(325.0)
    assert first.complete and second.complete
    assert not outs[(1, p1.start)].complete and outs[(1, p1.start)].pending == ["r2"]


def test_refunds_reduce_the_nights_they_came_from(conn, tmp_path):
    plan = freeze_plan(_plan(properties=["cloud_9"], owners={"cloud_9": "owner_b"}), tmp_path / "p.json")
    b0 = blocks(plan)[0]
    _stay(conn, "r1", "cloud_9", b0.start.isoformat(), 2, lodging=1000.0, refund=400.0)
    o = [x for x in block_outcomes(conn, plan) if x.block == b0][0]
    assert o.owner_net == pytest.approx(1000 - 250 - 100 - 400)


def test_pickup_gap_stop_rule_fires(conn, tmp_path):
    plan = freeze_plan(_plan(properties=["cloud_9"], owners={"cloud_9": "owner_b"}), tmp_path / "p.json")
    look = arm_for(plan)
    recs = []
    for b in blocks(plan):
        for i in range(7):
            d = b.start + timedelta(days=i)
            booked = (b.arm == "control") or i == 0
            recs.append({**_lin(), "property_id": "cloud_9", "stay_date": d.isoformat(),
                         "status": "booked" if booked else "available", "listed_price": 1000.0,
                         "price_basis": "nightly_ex_fees", "currency": "USD"})
    ingest(conn, "calendar_observation", recs, allowed_property_ids=SCOPE)
    fired = check_stop_rules(conn, plan, as_of=date(2027, 1, 1))
    assert fired and fired[0].startswith("pickup_gap:cloud_9")
    assert look("cloud_9", blocks(plan)[0].start) == blocks(plan)[0].arm


def test_covariate_adjustment_narrows_the_interval_and_keeps_coverage(tmp_path):
    """Demand swings shared with a known covariate (e.g. last year's same week) are removed."""
    plan = freeze_plan(_plan(covariate_coefficients={"ly": 1.0}), tmp_path / "p.json")
    raw_plan = freeze_plan(_plan(plan_id="FT-RAW"), tmp_path / "q.json")
    rng = random.Random(9)
    outs, outs_raw, cov = [], [], {}
    for p, src in ((plan, outs), (raw_plan, outs_raw)):
        rng = random.Random(9)
        for b in blocks(p):
            demand = rng.gauss(0, 40)                   # big week-to-week swing
            y = 100 + demand + rng.gauss(0, 3) + (6 if b.arm == "treatment" else 0)
            src.append(BlockOutcome(b, 7, y * 7, complete=True))
            if p is plan:
                cov[(b.property_id, b.start)] = {"ly": demand}
    adj = analyse(outs, plan, covariates=cov)["portfolio"]
    raw = analyse(outs_raw, raw_plan)["portfolio"]
    assert (adj["hi"] - adj["lo"]) < 0.5 * (raw["hi"] - raw["lo"])
    assert adj["lo"] <= 6 <= adj["hi"]
    with pytest.raises(PlanError, match="covariates"):
        analyse(outs, plan)
