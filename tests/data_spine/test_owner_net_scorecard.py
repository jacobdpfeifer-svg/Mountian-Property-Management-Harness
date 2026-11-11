"""Owner-net labels, unlinked money, the monthly scorecard, and the hurdle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data_spine.contracts import Reason
from src.data_spine.ingest import ingest
from src.data_spine.owner_net import (
    classify_components, load_system_cost, owner_net_for_reservation, owner_net_hurdle, property_month,
    reconcile_statement, render_owner_month,
)
from src.db import connect, init_db
from src.db.migrations import apply_migrations

FIXTURE = Path(__file__).parents[1] / "fixtures" / "data_spine" / "synthetic_lifecycle.json"
SCOPE = frozenset({"summit_haus", "overlook_ridge", "cloud_9"})


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "spine.db"
    init_db(path, seed_markets=False)
    c = connect(path)
    apply_migrations(c)
    yield c
    c.close()


def test_direct_channel_fee_is_not_applicable_and_owner_block_lodging_is_too():
    labels = classify_components({}, actual_types=set(), assumed=set(), channel="direct")
    assert labels["channel_and_payment_fees"] == "not_applicable"
    assert labels["settled_lodging"] == "missing"
    blocked = classify_components({}, actual_types=set(), assumed=set(), channel="direct", owner_block=True)
    assert blocked["settled_lodging"] == "not_applicable"
    ota = classify_components({}, actual_types=set(), assumed=set(), channel="airbnb")
    assert ota["channel_and_payment_fees"] == "missing"


def test_unlinked_money_is_quarantined(conn):
    fx = json.loads(FIXTURE.read_text())
    orphan = dict(fx["financial_ledger"][0], entry_key="ORPHAN", reservation_key=None, statement_key=None)
    res = ingest(conn, "financial_ledger", [orphan], allowed_property_ids=SCOPE)
    assert res.accepted == []
    assert Reason.UNLINKED_MONEY in res.quarantined[0]["reasons"]


def test_duplicate_ledger_line_is_an_exception(conn):
    fx = json.loads(FIXTURE.read_text())
    for name in ("financial_ledger", "owner_statement"):
        ingest(conn, name, fx[name], allowed_property_ids=SCOPE)
    extra = dict(fx["financial_ledger"][0], entry_key="E1-DUP")
    ingest(conn, "financial_ledger", [extra], allowed_property_ids=SCOPE)
    rec = reconcile_statement(conn, "S-SYN-2026-12-summit")
    assert rec.status == "exception"


def test_month_report_distinguishes_settled_from_assumed_and_blocks(conn):
    fx = json.loads(FIXTURE.read_text())
    for name in ("reservation", "financial_ledger", "owner_statement"):
        res = ingest(conn, name, fx[name], allowed_property_ids=SCOPE)
        assert res.ok, res.quarantined
    direct = owner_net_for_reservation(conn, "R-SYN-003")
    assert direct.field_class["channel_and_payment_fees"] == "actual"
    cancelled = owner_net_for_reservation(conn, "R-SYN-002")
    assert "refunds_concessions_chargebacks" in cancelled.field_class
    report = property_month(conn, "overlook_ridge", "2026-12-01", "2026-12-31")
    text = render_owner_month(report)
    assert "realized profit" not in text.lower()
    assert report["result_label"] in ("settled", "INCOMPLETE", "partially_assumed")
    if report["result_label"] != "settled":
        assert "not settled owner net" in text
    ingest(conn, "listing_constraint", [{
        "source_system": "fixture", "source_updated_at": "2026-12-01T00:00:00+00:00",
        "observed_at": "2026-12-01T00:00:00+00:00", "constraint_key": "B1",
        "property_id": "cloud_9", "constraint_type": "owner_block",
        "start_date": "2026-12-01", "end_date": "2026-12-02", "effect": "restrict", "active": 1,
    }], allowed_property_ids=SCOPE)
    blocked = property_month(conn, "cloud_9", "2026-12-01", "2026-12-31")
    assert blocked["owner_block_nights"]
    assert blocked["field_class"]["settled_lodging_on_owner_block"] == "not_applicable"
    assert "realized profit" not in render_owner_month(blocked).lower()
    assert blocked["result_label"] != "settled" or blocked["month_owner_net"] is not None


def test_reconciliation_shortfall_stays_incomplete(conn):
    fx = json.loads(FIXTURE.read_text())
    bad = dict(fx["owner_statement"][0], reported_owner_net=1.0)
    ingest(conn, "reservation", [r for r in fx["reservation"] if r["property_id"] == "summit_haus"],
           allowed_property_ids=SCOPE)
    ingest(conn, "financial_ledger", [r for r in fx["financial_ledger"] if r["property_id"] == "summit_haus"],
           allowed_property_ids=SCOPE)
    ingest(conn, "owner_statement", [bad], allowed_property_ids=SCOPE)
    report = property_month(conn, "summit_haus", "2026-12-01", "2026-12-31")
    assert report["result_label"] == "INCOMPLETE"
    assert report["reconciliation_value"] < 0.99
    assert report["exceptions"]


def test_hurdle_needs_explicit_inputs_and_shows_property_allocation():
    missing = owner_net_hurdle(annual_system_operating_cost=None, annual_sellable_nights=None)
    assert missing["status"] == "missing" and missing["per_available_night"] is None
    portfolio = owner_net_hurdle(annual_system_operating_cost=10000, annual_sellable_nights=500)
    assert portfolio["status"] == "supplied" and portfolio["per_available_night"] == 20.0
    split = owner_net_hurdle(
        annual_system_operating_cost=10000, annual_sellable_nights=500,
        cost_share_by_property={"summit_haus": 0.5, "overlook_ridge": 0.5},
        nights_by_property={"summit_haus": 100, "overlook_ridge": 400},
        allocation_method="equal cost share, actual sellable nights",
    )
    assert split["by_property"]["summit_haus"]["per_available_night"] == 50.0
    assert split["by_property"]["overlook_ridge"]["per_available_night"] == 12.5
    hidden = owner_net_hurdle(
        annual_system_operating_cost=10000, annual_sellable_nights=500,
        cost_share_by_property={"summit_haus": 0.5}, allocation_method="share only",
    )
    assert hidden["status"] == "missing"


def test_system_cost_file_feeds_the_hurdle_and_month_report(tmp_path, conn):
    path = tmp_path / "system_cost.yaml"
    path.write_text(
        "annual_system_operating_cost_usd: 10000\n"
        "annual_sellable_nights: 500\n"
        "allocation_method: equal property cost share\n"
        "cost_share_by_property: {summit_haus: 0.5, overlook_ridge: 0.5}\n"
        "nights_by_property: {summit_haus: 100, overlook_ridge: 400}\n",
        encoding="utf-8")
    loaded = load_system_cost(path)
    assert loaded["status"] == "supplied"
    report = property_month(conn, "summit_haus", "2026-12-01", "2026-12-31", **loaded["values"])
    assert report["system_operating_cost"] == {
        "status": "supplied", "amount": 10000,
        "note": "recorded separately from pricing-influenced owner net",
    }
    assert report["hurdle"]["by_property"]["summit_haus"]["per_available_night"] == 50.0
