"""Data spine: migrations, contracts, append-only lineage, owner net, trace."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.data_spine.contracts import Reason
from src.data_spine.ingest import current_rows, ingest
from src.data_spine.owner_net import (
    Assumption, owner_net_for_reservation, reconcile_statement, trace_reservation,
)
from src.db import connect, init_db
from src.db.migrations import MigrationDrift, apply_migrations, discover, pending, schema_version

FIXTURE = Path(__file__).parents[1] / "fixtures" / "data_spine" / "synthetic_lifecycle.json"
SCOPE = frozenset({"summit_haus", "overlook_ridge", "cloud_9"})


@pytest.fixture
def conn(tmp_path: Path):
    path = tmp_path / "spine.db"
    init_db(path, seed_markets=False)
    c = connect(path)
    apply_migrations(c)
    yield c
    c.close()


@pytest.fixture
def loaded(conn):
    fx = json.loads(FIXTURE.read_text())
    for name in ("price_decision", "reservation", "financial_ledger", "owner_statement"):
        res = ingest(conn, name, fx[name], allowed_property_ids=SCOPE)
        assert res.ok, res.quarantined
    return conn


def test_migrations_apply_once_and_are_versioned(conn):
    assert pending(conn) == []
    assert apply_migrations(conn) == []
    versions = [m.version for m in discover()]
    assert versions == list(range(1, len(versions) + 1)) and len(versions) >= 4
    assert schema_version().startswith(f"{versions[-1]:04d}-")


def test_ingest_refuses_to_commit_a_callers_active_transaction(conn):
    """A spine ingest must not expose or commit unrelated caller work."""
    conn.execute("CREATE TABLE caller_work (value TEXT)")
    conn.execute("INSERT INTO caller_work VALUES ('uncommitted')")
    with pytest.raises(RuntimeError, match="no active transaction"):
        ingest(conn, "calendar_observation", [], allowed_property_ids=SCOPE)
    assert conn.in_transaction
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM caller_work").fetchone()[0] == 0


def test_migration_drift_is_refused(tmp_path: Path):
    mig = tmp_path / "m"
    mig.mkdir()
    (mig / "0001_a.sql").write_text("CREATE TABLE a (x INTEGER);")
    c = sqlite3.connect(tmp_path / "d.db")
    apply_migrations(c, mig)
    (mig / "0001_a.sql").write_text("CREATE TABLE a (x TEXT);")
    with pytest.raises(MigrationDrift):
        apply_migrations(c, mig)


def test_failed_migration_leaves_no_partial_state(tmp_path: Path):
    mig = tmp_path / "m"
    mig.mkdir()
    (mig / "0001_bad.sql").write_text("CREATE TABLE ok (x INTEGER);\nTHIS IS NOT SQL;")
    c = sqlite3.connect(tmp_path / "d.db")
    with pytest.raises(sqlite3.Error):
        apply_migrations(c, mig)
    assert c.execute("SELECT name FROM sqlite_master WHERE name='ok'").fetchone() is None
    assert c.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0


def test_spine_is_append_only(loaded):
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        loaded.execute("UPDATE fact_financial_ledger SET amount = 0")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        loaded.execute("DELETE FROM fact_reservation_version")


def test_pii_is_dropped_by_the_contract(loaded):
    dump = "\n".join(loaded.iterdump())
    assert "someone@example.com" not in dump
    assert "Synthetic Guest" not in dump


def test_modification_is_a_new_version_with_lineage(loaded):
    rows = loaded.execute(
        "SELECT * FROM fact_reservation_version WHERE entity_key='R-SYN-001' ORDER BY version_no"
    ).fetchall()
    assert [r["version_no"] for r in rows] == [1, 2]
    assert rows[1]["supersedes_id"] == rows[0]["id"]
    assert rows[1]["correction_reason"] == "guest extended stay"
    cur = current_rows(loaded, "fact_reservation_version", "t.entity_key = ?", ("R-SYN-001",))
    assert [r["nights"] for r in cur] == [4]
    nights = loaded.execute(
        "SELECT COUNT(*) FROM fact_reservation_night WHERE reservation_version_id=?", (cur[0]["id"],)
    ).fetchone()[0]
    assert nights == 4


def test_reingest_is_idempotent(loaded):
    fx = json.loads(FIXTURE.read_text())
    res = ingest(loaded, "financial_ledger", fx["financial_ledger"], allowed_property_ids=SCOPE)
    assert res.accepted == [] and res.duplicates == len(fx["financial_ledger"])


def test_out_of_order_update_is_quarantined_not_applied(loaded):
    fx = json.loads(FIXTURE.read_text())
    stale = dict(fx["reservation"][0], gross_lodging=1.0, source_updated_at="2026-11-01T00:00:00+00:00")
    res = ingest(loaded, "reservation", [stale], allowed_property_ids=SCOPE)
    assert res.quarantined[0]["reasons"] == [Reason.OUT_OF_ORDER_VERSION]
    cur = current_rows(loaded, "fact_reservation_version", "t.entity_key = ?", ("R-SYN-001",))
    assert cur[0]["gross_lodging"] == 7200.0


@pytest.mark.parametrize("mutate, reason", [
    ({"property_id": "creekside_haven"}, Reason.UNKNOWN_IDENTITY),
    ({"price_basis": "unknown"}, Reason.AMBIGUOUS_PRICE_BASIS),
    ({"price_basis": "nightly_ex_fees"}, Reason.AMBIGUOUS_PRICE_BASIS),
    ({"currency": "EUR"}, Reason.AMBIGUOUS_MONEY),
    ({"gross_lodging": -5.0}, Reason.AMBIGUOUS_MONEY),
    ({"gross_lodging": float("nan")}, Reason.AMBIGUOUS_MONEY),
    ({"source_updated_at": "2026-11-02T12:00:00"}, Reason.BAD_TIMESTAMP),
    ({"nights": 9}, Reason.INCONSISTENT),
    ({"reservation_key": None}, Reason.MISSING_FIELD),
])
def test_ambiguous_reservations_quarantine(conn, mutate, reason):
    fx = json.loads(FIXTURE.read_text())
    rec = dict(fx["reservation"][2], **mutate)
    res = ingest(conn, "reservation", [rec], allowed_property_ids=SCOPE)
    assert res.accepted == []
    assert reason in res.quarantined[0]["reasons"]
    row = conn.execute("SELECT payload_json FROM spine_quarantine").fetchone()
    assert "guest_email" not in row["payload_json"] and "guest_name" not in row["payload_json"]


def test_ledger_adjustment_needs_explicit_direction(conn):
    fx = json.loads(FIXTURE.read_text())
    rec = dict(fx["financial_ledger"][0], entry_key="ADJ", entry_type="adjustment")
    res = ingest(conn, "financial_ledger", [rec], allowed_property_ids=SCOPE)
    assert Reason.AMBIGUOUS_MONEY in res.quarantined[0]["reasons"]


def test_market_observation_without_price_basis_quarantines(conn):
    rec = {"source_system": "scrape", "source_updated_at": "2026-11-01T00:00:00+00:00",
           "observed_at": "2026-11-01T00:00:00+00:00", "comp_key": "comp-a", "stay_date": "2026-12-20",
           "los": 3, "price": 2100.0, "price_basis": "unknown", "currency": "USD"}
    res = ingest(conn, "market_observation", [rec], allowed_property_ids=SCOPE)
    assert res.quarantined[0]["reasons"] == [Reason.AMBIGUOUS_PRICE_BASIS]
    ok = ingest(conn, "market_observation", [dict(rec, price_basis="stay_total_all_in")],
                allowed_property_ids=SCOPE)
    assert len(ok.accepted) == 1


def test_owner_net_uses_corrected_actuals(loaded):
    net = owner_net_for_reservation(loaded, "R-SYN-001")
    # 7200 + 450 - 1116 - 1440 (corrected, not 1400) - 400; tax and payout excluded.
    assert net.total == 4694.0
    assert net.status == "actual"
    assert net.components["management_fee"] == -1440.0


def test_actual_beats_assumption(loaded):
    net = owner_net_for_reservation(
        loaded, "R-SYN-001",
        [Assumption("management_fee", fraction_of_lodging=0.5, source="generic 50%")])
    assert net.components["management_fee"] == -1440.0
    assert net.assumed_components == {}


def test_missing_component_is_incomplete_or_labelled_assumed(conn):
    fx = json.loads(FIXTURE.read_text())
    ingest(conn, "reservation", [fx["reservation"][4]], allowed_property_ids=SCOPE)
    ingest(conn, "financial_ledger", [fx["financial_ledger"][14]], allowed_property_ids=SCOPE)
    net = owner_net_for_reservation(conn, "R-SYN-003")
    assert net.status == "incomplete"
    assert net.missing_components == ["cleaning_cost", "management_fee"]
    net = owner_net_for_reservation(conn, "R-SYN-003", [
        Assumption("management_fee", fraction_of_lodging=0.2, source="owner agreement draft"),
        Assumption("cleaning_cost", flat_amount=400.0, source="ops profile estimate")])
    assert net.status == "partially_assumed"
    assert net.total == 6000.0 - 1200.0 - 400.0
    assert set(net.assumed_components) == {"management_fee", "cleaning_cost"}


def test_cancellation_with_partial_refund(loaded):
    net = owner_net_for_reservation(loaded, "R-SYN-002")
    assert net.total == 1500.0
    cur = current_rows(loaded, "fact_reservation_version", "t.entity_key = ?", ("R-SYN-002",))
    assert cur[0]["status"] == "cancelled"
    assert loaded.execute("SELECT COUNT(*) FROM fact_reservation_night WHERE reservation_version_id=?",
                          (cur[0]["id"],)).fetchone()[0] == 0


@pytest.mark.parametrize("key", ["S-SYN-2026-12-summit", "S-SYN-2026-12-cloud9", "S-SYN-2026-12-overlook"])
def test_statements_reconcile_per_channel(loaded, key):
    rec = reconcile_statement(loaded, key)
    assert rec.status == "reconciled", rec.issues


def test_statement_mismatch_is_an_exception(loaded):
    fx = json.loads(FIXTURE.read_text())
    wrong = dict(fx["owner_statement"][0], reported_owner_net=4800.0,
                 source_updated_at="2027-01-02T00:00:00+00:00", correction_reason="reissued")
    ingest(loaded, "owner_statement", [wrong], allowed_property_ids=SCOPE)
    rec = reconcile_statement(loaded, "S-SYN-2026-12-summit")
    assert rec.status == "exception"
    assert any("differs from ledger" in i for i in rec.issues)


def test_trace_from_decision_to_owner_statement(loaded):
    t = trace_reservation(loaded, "R-SYN-001")
    assert t["decision"]["entity_key"] == "D-SYN-001"
    assert t["decision"]["applied_price"] == 1850.0
    assert [v["status"] for v in t["versions"]] == ["confirmed", "modified"]
    assert len(t["nights"]) == 4
    assert t["owner_net"].total == 4694.0
    assert [s.status for s in t["statements"]] == ["reconciled"]
    superseded = [r for r in t["ledger"] if not r["is_current"]]
    assert [r["amount"] for r in superseded] == [1400.0]
