"""Phase 4: compliance register (tracking only) and the monthly owner receipt."""

from __future__ import annotations

from datetime import date

import pytest
from conftest import add_reservation

from src.compliance import Credential, add_credential, check, deadline_for, listing_mentions
from src.db import connect
from src.ops import TurnoverOutcome
from src.ops.db import record_outcomes, start_import
from src.receipt.owner_monthly import PlaceholderOwnerName, load_owner_month, render


@pytest.fixture()
def portfolio(monkeypatch):
    """Give the twins a jurisdiction and an owner fee without editing config."""
    from src import config

    real = config.load_portfolio_config()
    real["properties"]["summit_haus"]["jurisdiction"] = "winter_park"
    real["properties"]["overlook_ridge"]["jurisdiction"] = "grand_county_unincorporated"
    real["owners"]["northwoods"]["management_fee_pct"] = 0.25
    real["owners"]["northwoods"]["name"] = "Test Family"
    monkeypatch.setattr("src.compliance.load_portfolio_config", lambda: real)
    monkeypatch.setattr("src.receipt.owner_monthly.load_portfolio_config", lambda: real)
    return real


def _results(report, pid):
    return {r.credential_type: r for r in report.results if r.property_id == pid}


def test_fixed_date_and_annual_renewals():
    row = {"expires_at": None, "issued_at": "2025-10-15"}
    assert deadline_for(row, {"kind": "fixed_date", "month_day": "09-30"}) == date(2026, 9, 30)
    assert deadline_for(row, {"kind": "annual_from_issue"}) == date(2026, 10, 15)
    assert deadline_for({"expires_at": "2027-01-01", "issued_at": None}, {"kind": "none"}) == date(2027, 1, 1)


def test_listing_match_ignores_punctuation():
    assert listing_mentions("STR-2025-014", "Winter Park license str 2025 014 ...") is True
    assert listing_mentions("STR-2025-014", "no number here") is False
    assert listing_mentions("STR-2025-014", None) is None


def test_statuses_never_claim_compliance(ops_db, portfolio):
    with connect(ops_db) as conn:
        add_credential(conn, Credential("summit_haus", "winter_park", "str_registration", "WP-1",
                                        issued_at="2025-10-01", verification_status="verified",
                                        verified_by="jacob", permitted_occupancy=16))
        add_credential(conn, Credential("summit_haus", "winter_park", "liability_insurance", "POL-9",
                                        expires_at="2026-10-10", verification_status="verified",
                                        verified_by="jacob"))
        add_credential(conn, Credential("summit_haus", "winter_park", "responsible_agent", "Agent A"))
        rep = check(conn, date(2026, 9, 30), listing_texts={"summit_haus": "Permit WP-1. Sleeps 16."})
        late = check(conn, date(2026, 10, 1))
    r = _results(rep, "summit_haus")
    assert r["str_registration"].status == "expiring"          # shared 09-30 renewal
    assert r["liability_insurance"].status == "expiring"
    assert r["responsible_agent"].status == "unverified"
    assert r["fire_life_safety_inspection"].status == "missing"
    assert r["fireplace_cleaning"].optional
    assert _results(late, "summit_haus")["str_registration"].status == "expired"
    # No listing text supplied → the advertised number cannot be confirmed.
    assert "listing text not available" in _results(late, "summit_haus")["str_registration"].detail
    assert all(res.status in ("evidence_on_file", "unverified", "expiring", "expired", "missing")
               for res in rep.results)
    assert any("not been reviewed" in w for w in rep.warnings)


def test_emergency_contacts_count_and_occupancy_cap(ops_db, portfolio):
    with connect(ops_db) as conn:
        conn.execute("UPDATE properties SET max_occupancy=18 WHERE property_id='overlook_ridge'")
        add_credential(conn, Credential("overlook_ridge", "grand_county_unincorporated",
                                        "emergency_contact", "Contact 1"))
        add_credential(conn, Credential("overlook_ridge", "grand_county_unincorporated", "str_permit",
                                        "GC-7", issued_at="2026-06-01", verification_status="verified",
                                        verified_by="jacob"))
        rep = check(conn, date(2026, 9, 30), listing_texts={"overlook_ridge": "GC-7"})
    r = _results(rep, "overlook_ridge")
    assert r["emergency_contact"].status == "missing" and "1 of 2" in r["emergency_contact"].detail
    assert r["str_permit"].status == "unverified" and "sleeps 18" in r["str_permit"].detail


def test_missing_jurisdiction_is_reported(ops_db):
    with connect(ops_db) as conn:
        rep = check(conn, date(2026, 9, 30), property_ids=["summit_haus"])
    assert [(r.credential_type, r.status) for r in rep.results] == [("jurisdiction", "missing")]


def test_verified_needs_a_person(ops_db):
    with connect(ops_db) as conn, pytest.raises(ValueError):
        add_credential(conn, Credential("cloud_9", "fraser", "str_registration", "F-1",
                                        verification_status="verified"))


def test_owner_receipt_refuses_placeholder_names(ops_db):
    with connect(ops_db) as conn, pytest.raises(PlaceholderOwnerName):
        load_owner_month(conn, "northwoods", "2026-08")


def test_owner_receipt_arithmetic(ops_db, portfolio):
    with connect(ops_db) as conn:
        # 4 of 5 nights in August; payout implies $600 channel cost on the whole stay.
        add_reservation(conn, "a", "summit_haus", date(2026, 8, 28), date(2026, 9, 2),
                        fare=5000.0, cleaning=500.0, payout=4900.0)
        add_reservation(conn, "own", "overlook_ridge", date(2026, 8, 10), date(2026, 8, 12), source="owner")
        add_reservation(conn, "b", "overlook_ridge", date(2026, 8, 14), date(2026, 8, 16), fare=2000.0)
        result = start_import(conn, "csv", "outcomes")
        record_outcomes(conn, [TurnoverOutcome("overlook_ridge", "2026-08-16", "csv:generic", "t1",
                                               cost=700.0, qa_pass=True)], result)
        conn.execute("""INSERT INTO owner_ledger_entries (owner_id, property_id, entry_date, category, amount, memo)
                        VALUES ('northwoods','summit_haus','2026-08-12','maintenance',340,'pump')""")
        om = load_owner_month(conn, "northwoods", "2026-08")
        html = render(om)
    summit = next(p for p in om.properties if p.property_id == "summit_haus")
    overlook = next(p for p in om.properties if p.property_id == "overlook_ridge")
    assert summit.nights_sold == 4 and summit.gross_accommodation == pytest.approx(4000.0)
    assert summit.cleaning_fees == pytest.approx(400.0)
    assert summit.channel_cost == pytest.approx(480.0)
    assert overlook.channel_cost_missing == 1        # no payout recorded; not guessed
    assert overlook.gross_accommodation == 2000.0   # owner stay excluded
    assert overlook.turns_observed == 1 and overlook.service_observed == 700.0
    # The owner stay's checkout (08-12) is a turn without an invoice → estimated.
    assert overlook.turns_estimated == 1 and overlook.service_estimated == 720.0
    assert om.management_fee == pytest.approx(0.25 * 6000.0)
    expected = (4400.0 + 2000.0) - 480.0 - 700.0 - 720.0 - 340.0 - 1500.0
    assert om.net == pytest.approx(expected)
    assert "Test Family" in html and "Net to owner" in html
