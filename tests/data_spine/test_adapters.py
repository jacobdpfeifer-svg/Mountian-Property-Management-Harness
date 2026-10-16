"""Source adapters and read-only backfill into the data spine (workstream 4)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from src.data_spine.adapters import ReadOnlyGuesty, guesty_reservation, load_mapping
from src.data_spine.backfill import backfill_guesty, import_csv
from src.data_spine.ingest import current_rows
from src.data_spine.owner_net import owner_net_for_reservation
from src.db import connect, init_db
from src.db.migrations import apply_migrations

SCOPE = frozenset({"summit_haus", "overlook_ridge", "cloud_9"})
LISTINGS = {"L1": "summit_haus", "L2": "cloud_9", "LX": "not_ours"}
MAPPING_DIR = Path(__file__).parents[2] / "config" / "data_mapping"


def _res(rid="r1", listing="L1", status="confirmed", source="airbnb2", fare=4000.0, cleaning=600.0,
         updated="2026-01-03T10:00:00Z", **money):
    return {"_id": rid, "listingId": listing, "status": status, "source": source,
            "checkIn": "2026-02-01", "checkOut": "2026-02-05", "nightsCount": 4,
            "confirmedAt": "2026-01-02T09:00:00Z", "createdAt": "2026-01-02T08:00:00Z",
            "lastUpdatedAt": updated, "guest": {"fullName": "Private Person", "email": "x@y.z"},
            "money": {"fareAccommodation": fare, "fareCleaning": cleaning, "currency": "USD",
                      "hostServiceFeeIncTax": -620.0, **money}}


class FakeGuesty:
    def __init__(self, reservations, days=None):
        self._r, self._days = reservations, days or []
        self.writes = 0

    def reservations(self, **_):
        yield from self._r

    def calendar(self, listing_id, start, end):
        return self._days

    def set_rate(self, *a, **k):
        self.writes += 1


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "spine.db"
    init_db(path, seed_markets=False)
    c = connect(path)
    apply_migrations(c)
    yield c
    c.close()


def test_read_only_wrapper_refuses_writes_mutation_and_the_audited_bypasses():
    fake = FakeGuesty([_res()])
    ro = ReadOnlyGuesty(fake)
    assert list(ro.reservations()) == [_res()]
    with pytest.raises(PermissionError):
        ro.set_rate("L1", date(2026, 2, 1), 1000)
    with pytest.raises(PermissionError):
        ro._client = fake
    with pytest.raises(PermissionError):
        ro._client.set_rate("L1", date(2026, 2, 1), 1000)
    with pytest.raises((AttributeError, TypeError)):
        object.__getattribute__(ro, "_client")
    assert not hasattr(ro.reservations, "__self__")
    with pytest.raises((AttributeError, PermissionError)):
        ro.__dict__
    assert fake.writes == 0


def test_reservation_mapping_is_explicit_and_drops_guest_identity():
    rec, lines, why = guesty_reservation(_res(), LISTINGS, observed_at="2026-01-04T00:00:00+00:00")
    assert why is None
    assert rec["reservation_key"] == "guesty:r1" and rec["channel"] == "airbnb"
    assert rec["price_basis"] == "stay_total_ex_fees" and rec["gross_lodging"] == 4000.0
    assert "guest" not in rec and all("email" not in str(v) for v in rec.values())
    kinds = {ln["entry_type"]: ln for ln in lines}
    assert set(kinds) == {"gross_lodging", "cleaning_fee_income", "channel_fee"}
    assert kinds["channel_fee"]["amount"] == 620.0
    assert all(ln["settlement_state"] == "pending" and ln["basis"] == "actual" for ln in lines)


@pytest.mark.parametrize("raw,reason", [
    (_res(status="inquiry"), "status inquiry is not a stay"),
    (_res(listing="unknown"), "listing not in scope"),
])
def test_non_stays_and_unknown_listings_are_skipped(raw, reason):
    assert guesty_reservation(raw, LISTINGS, observed_at="2026-01-04T00:00:00+00:00")[2] == reason


def test_unknown_source_is_other_and_direct_stays_carry_no_channel_fee():
    rec, lines, _ = guesty_reservation(_res(source="mystery_ota"), LISTINGS, observed_at="2026-01-04T00:00:00+00:00")
    assert rec["channel"] == "other" and "channel_fee" not in {ln["entry_type"] for ln in lines}
    rec, lines, _ = guesty_reservation(_res(source="manual"), LISTINGS, observed_at="2026-01-04T00:00:00+00:00")
    assert rec["channel"] == "direct" and "channel_fee" not in {ln["entry_type"] for ln in lines}


def test_cancelled_reservation_books_no_lodging_money():
    rec, lines, _ = guesty_reservation(_res(status="canceled"), LISTINGS, observed_at="2026-01-04T00:00:00+00:00")
    # Same keys as the booking-time lines, reversed, so a later cancellation supersedes them.
    assert rec["status"] == "cancelled" and lines
    assert all(ln["settlement_state"] == "reversed" for ln in lines)


def test_backfill_is_idempotent_versions_updates_and_quarantines_ambiguity(conn):
    days = [{"date": "2026-10-20", "status": "available", "price": 1500, "minNights": 3},
            {"date": "2026-10-21", "status": "weird", "price": 1500}]
    fake = FakeGuesty([_res(), _res("r2", listing="L2", fare=None), _res("r3", status="inquiry")], days)
    rep = backfill_guesty(conn, fake, property_by_listing=LISTINGS, scope=SCOPE,
                          check_in_from=date(2021, 1, 1), calendar_days=2, today=date(2026, 10, 20))
    by = {r.contract: r for r in rep.results}
    assert len(by["reservation"].accepted) == 1 and len(by["reservation"].quarantined) == 1   # r2: no fare
    assert rep.skipped["status inquiry is not a stay"] == 1
    assert rep.skipped["ledger line of a quarantined reservation"] == 2       # r2: cleaning + channel fee
    assert len(by["financial_ledger"].accepted) == 3
    assert len(by["calendar_observation"].quarantined) >= 1                                  # "weird" status
    assert fake.writes == 0
    # Same data again: nothing new.
    again = backfill_guesty(conn, fake, property_by_listing=LISTINGS, scope=SCOPE,
                            check_in_from=date(2021, 1, 1), calendar_days=2, today=date(2026, 10, 20))
    assert sum(len(r.accepted) for r in again.results if r.contract != "calendar_observation") == 0
    # A later modification is a new version, not an overwrite.
    newer = FakeGuesty([_res(fare=4400.0, updated="2026-01-10T10:00:00Z")])
    backfill_guesty(conn, newer, property_by_listing=LISTINGS, scope=SCOPE,
                    check_in_from=date(2021, 1, 1), calendar_days=0, today=date(2026, 10, 20))
    versions = conn.execute("SELECT version_no, gross_lodging FROM fact_reservation_version "
                            "WHERE entity_key='guesty:r1' ORDER BY version_no").fetchall()
    assert [tuple(v) for v in versions] == [(1, 4000.0), (2, 4400.0)]
    assert current_rows(conn, "fact_reservation_version", "t.entity_key = ?", ("guesty:r1",))[0]["gross_lodging"] == 4400.0


def _mapping(tmp_path: Path, template: str, **edits) -> Path:
    spec = yaml.safe_load((MAPPING_DIR / template).read_text())
    for key, value in edits.items():
        spec[key] = value
    out = tmp_path / template.replace(".template", "")
    out.write_text(yaml.safe_dump(spec))
    return out


def test_accounting_export_is_the_stays_money_and_rejects_unknown_labels(conn, tmp_path):
    backfill_guesty(conn, FakeGuesty([_res()]), property_by_listing=LISTINGS, scope=SCOPE,
                    check_in_from=date(2021, 1, 1), calendar_days=0, today=date(2026, 10, 20))
    spec = yaml.safe_load((MAPPING_DIR / "accounting_ledger.template.yaml").read_text())
    spec["values"]["property_id"] = {"Summit Haus": "summit_haus"}
    mapping = tmp_path / "acct.yaml"
    mapping.write_text(yaml.safe_dump(spec))
    export = tmp_path / "acct.csv"
    export.write_text(
        "Transaction ID,Reservation ID,Listing,Channel,Category,Amount,Currency,Status,Settled Date,"
        "Statement ID,Guest Name\n"
        "t0,r1,Summit Haus,Airbnb,Accommodation,4000,USD,Paid,2026-03-01,s1,Private Person\n"
        "ta,r1,Summit Haus,Airbnb,Cleaning Fee,600,USD,Paid,2026-03-01,s1,Private Person\n"
        "tb,r1,Summit Haus,Airbnb,Channel Commission,-620,USD,Paid,2026-03-01,s1,Private Person\n"
        "t1,r1,Summit Haus,Airbnb,Management Commission,-845.00,USD,Paid,2026-03-01,s1,Private Person\n"
        "t2,r1,Summit Haus,Airbnb,Cleaning Expense,\"-$450.00\",USD,Paid,2026-03-01,s1,Private Person\n"
        "t3,r1,Summit Haus,Airbnb,Mystery Line,-10,USD,Paid,2026-03-01,s1,Private Person\n")
    rep = import_csv(conn, export, mapping, scope=SCOPE)
    res = rep.results[0]
    assert len(res.accepted) == 5 and len(res.quarantined) == 1 and "BAD_ENUM" in res.quarantined[0]["reasons"]
    payloads = " ".join(r[0] for r in conn.execute("SELECT payload_json FROM spine_quarantine"))
    assert "Private Person" not in payloads                       # unmapped columns never stored
    net = owner_net_for_reservation(conn, "guesty:r1")
    assert net.status == "actual" and not net.missing_components
    # 4000 lodging + 600 cleaning income - 620 channel - 845 management - 450 cleaning cost
    assert net.total == pytest.approx(2685.0)


def test_mapping_files_are_validated(tmp_path):
    for template in ("accounting_ledger.template.yaml", "owner_statement.template.yaml", "ops_tasks.template.yaml"):
        load_mapping(MAPPING_DIR / template)
    bad = _mapping(tmp_path, "ops_tasks.template.yaml", columns={"guest_email": "Email"})
    with pytest.raises(ValueError, match="does not have"):
        load_mapping(bad)
    bad = _mapping(tmp_path, "ops_tasks.template.yaml", contract="reservation")
    with pytest.raises(ValueError, match="must be one of"):
        load_mapping(bad)


def test_missing_export_column_fails_loudly(conn, tmp_path):
    export = tmp_path / "ops.csv"
    export.write_text("Task ID,Property\nk1,Summit Haus\n")
    with pytest.raises(ValueError, match="lacks mapped columns"):
        import_csv(conn, export, MAPPING_DIR / "ops_tasks.template.yaml", scope=SCOPE)


def test_settled_accounting_replaces_guesty_booking_money_instead_of_doubling_it(conn, tmp_path):
    """Guesty sends pending lodging/cleaning/channel fee at booking; accounting sends the settled
    figures later under its own keys. Owner net must count each once, and the stay is settled."""
    from src.experiments.field import _all_settled
    backfill_guesty(conn, FakeGuesty([_res()]), property_by_listing=LISTINGS, scope=SCOPE,
                    check_in_from=date(2021, 1, 1), calendar_days=0, today=date(2026, 10, 20))
    spec = yaml.safe_load((MAPPING_DIR / "accounting_ledger.template.yaml").read_text())
    spec["values"]["property_id"] = {"Summit Haus": "summit_haus"}
    mapping = tmp_path / "acct.yaml"
    mapping.write_text(yaml.safe_dump(spec))
    export = tmp_path / "acct.csv"
    rows = [("t1", "Accommodation", "4000"), ("t2", "Cleaning Fee", "600"), ("t3", "Channel Commission", "620"),
            ("t4", "Management Commission", "845"), ("t5", "Cleaning Expense", "450")]
    export.write_text("Transaction ID,Reservation ID,Listing,Channel,Category,Amount,Currency,Status,"
                      "Settled Date,Statement ID\n" + "".join(
                          f"{t},r1,Summit Haus,Airbnb,{c},{a},USD,Paid,2026-03-01,s1\n" for t, c, a in rows))
    assert import_csv(conn, export, mapping, scope=SCOPE).results[0].ok
    net = owner_net_for_reservation(conn, "guesty:r1")
    assert net.total == pytest.approx(4000 + 600 - 620 - 845 - 450)
    assert _all_settled(conn, "guesty:r1")


def _acct(conn, tmp_path, rows):
    spec = yaml.safe_load((MAPPING_DIR / "accounting_ledger.template.yaml").read_text())
    spec["values"]["property_id"] = {"Summit Haus": "summit_haus"}
    mapping = tmp_path / "acct2.yaml"
    mapping.write_text(yaml.safe_dump(spec))
    export = tmp_path / f"acct_{len(list(tmp_path.glob('acct_*.csv')))}.csv"
    export.write_text("Transaction ID,Reservation ID,Listing,Channel,Category,Amount,Currency,Status,"
                      "Settled Date,Statement ID\n" + "".join(
                          f"{t},r1,Summit Haus,Airbnb,{c},{a},USD,{st},{'2026-03-01' if st == 'Paid' else ''},s1\n"
                          for t, c, a, st in rows))
    res = import_csv(conn, export, mapping, scope=SCOPE).results[0]
    assert res.ok, res.quarantined


def _guesty(conn, **kw):
    backfill_guesty(conn, FakeGuesty([_res(**kw)]), property_by_listing=LISTINGS, scope=SCOPE,
                    check_in_from=date(2021, 1, 1), calendar_days=0, today=date(2026, 10, 20))


def test_pending_accounting_lodging_is_not_added_to_guesty_lodging(conn, tmp_path):
    """Audit V6 case 1: was 8000."""
    _guesty(conn)
    _acct(conn, tmp_path, [("t1", "Accommodation", "4000", "Pending")])
    assert owner_net_for_reservation(conn, "guesty:r1").components["gross_lodging"] == 4000


def test_partial_settlement_counts_both_parts_and_is_not_settled(conn, tmp_path):
    """Audit V6 case 2: was 2000 and reported settled."""
    from src.experiments.field import _all_settled
    _guesty(conn)
    _acct(conn, tmp_path, [("t1", "Accommodation", "2000", "Paid"), ("t2", "Accommodation", "2000", "Pending")])
    assert owner_net_for_reservation(conn, "guesty:r1").components["gross_lodging"] == 4000
    assert not _all_settled(conn, "guesty:r1")


def test_a_later_cancellation_reverses_the_booking_lines(conn):
    """Audit V6 case 3: the stay stayed incomplete forever."""
    from src.experiments.field import _all_settled
    _guesty(conn)
    _guesty(conn, status="canceled", updated="2026-01-20T10:00:00Z")
    net = owner_net_for_reservation(conn, "guesty:r1")
    assert net.status == "cancelled_no_money" and net.total == 0 and _all_settled(conn, "guesty:r1")


def test_accounting_that_bundles_cleaning_into_lodging_is_not_double_counted(conn, tmp_path):
    """Audit V6 case 4: cleaning income was counted twice."""
    _guesty(conn)
    _acct(conn, tmp_path, [("t1", "Accommodation", "4600", "Paid"), ("t3", "Channel Commission", "620", "Paid"),
                           ("t4", "Management Commission", "845", "Paid"), ("t5", "Cleaning Expense", "450", "Paid")])
    net = owner_net_for_reservation(conn, "guesty:r1")
    assert "cleaning_fee_income" not in net.components
    assert net.total == pytest.approx(4600 - 620 - 845 - 450)
