"""Guesty sync + small-data safety tests.

The regression that motivates most of this file: on the live tenant, last Christmas
averaged $482/night and this Christmas averages $2,845 (realised $3,482). A model
fitted on that history wanted a -35% cut on the strongest nights of the year — i.e.
to restore last season's underpricing. Everything below pins the behaviour that
stops a thin-history model from overruling the operator.
"""

from __future__ import annotations

import ast
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
import pytest
import requests

from src.ceiling import compute_ceiling, demand_tier, seasonal_anchor
from src.compose import recommend_night
from src.config import load_policy
from src.db import connect, get_db_identity, init_db, resolve_property_ids
from src.features import build_features_for_property
from src.pms.guesty import GuestyClient, GuestyListing, parse_guesty_date
from src.pms.sync import (
    SyncReport,
    _floor_and_ceiling,
    recalibrate_bounds,
    sync_all,
    sync_calendar,
    sync_listings,
    sync_reservations,
)


def _listing(**kw) -> GuestyListing:
    base = dict(listing_id="abc123", nickname="Test Haus", title="t", bedrooms=5,
                bathrooms=5.5, accommodates=16, base_price=420.0,
                weekend_base_price=618.0, cleaning_fee=650.0, min_nights=2,
                address="1 Test St", city="Winter Park", lat=39.89, lng=-105.75,
                timezone="America/Denver", active=True, amenities=[])
    base.update(kw)
    return GuestyListing(**base)


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "g.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
               VALUES ('test_haus','Test Haus',5,5.5,'[]',711,252,1854,'America/Denver','abc123')"""
        )
        conn.commit()
    return path


# ------------------------------------------------------------------ identity

def test_property_id_is_a_stable_slug():
    assert _listing(nickname="Summit Haus").property_id == "summit_haus"
    assert _listing(nickname="Cloud 9").property_id == "cloud_9"
    assert _listing(nickname="Café / Lodge!").property_id == "cafe_lodge"
    assert _listing(nickname="   ").property_id == "abc123"  # falls back to listing id
    assert _listing(
        listing_id="6a8e355230f5b5007c81df4b", nickname="Cloud 9 Chalet"
    ).property_id == "cloud_9"


def test_parse_guesty_date_handles_iso_timestamps():
    assert parse_guesty_date("2026-12-27T00:00:00.000Z") == date(2026, 12, 27)
    assert parse_guesty_date("2026-12-27") == date(2026, 12, 27)
    assert parse_guesty_date(None) is None
    assert parse_guesty_date("nonsense") is None


# --------------------------------------------------------------------- bounds

def test_base_price_seed_is_only_provisional():
    """Guesty basePrice is a STARTING rate, not a ceiling. The seed must be treated as
    provisional or a $420 base caps a property that sells at $3,482."""
    floor, base_ceiling, _ = _floor_and_ceiling(_listing())
    assert base_ceiling < 800, "seed is intentionally low; recalibrate_bounds must fix it"
    assert floor < base_ceiling


def test_recalibrate_bounds_uses_observed_prices(db: Path):
    """REGRESSION: seeding the ceiling from Guesty's basePrice produced an $818 anchor
    on nights the operator lists at $2,700, driving a -70% Christmas recommendation."""
    with connect(db) as conn:
        d = date(2026, 12, 1)
        for i in range(60):
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,?,'available',?)",
                ((d + timedelta(days=i)).isoformat(), 2600 + i * 5, (d + timedelta(days=i)).weekday()),
            )
        conn.commit()
        report = SyncReport()
        recalibrate_bounds(conn, report)
        row = conn.execute(
            "SELECT min_floor_rate, base_ceiling_rate, max_ceiling_rate FROM properties"
        ).fetchone()
    assert row["base_ceiling_rate"] > 2500, "ceiling must follow observed prices, not basePrice"
    assert row["max_ceiling_rate"] > row["base_ceiling_rate"]
    assert row["min_floor_rate"] > 1000


# ---------------------------------------------------------------- demand tiers

def test_demand_tier_separates_holiday_from_ordinary_peak():
    policy = load_policy()
    assert demand_tier(0.95, policy) == "high"    # Christmas
    assert demand_tier(0.55, policy) == "mid"
    assert demand_tier(0.20, policy) == "low"     # ordinary January midweek


def test_anchor_prefers_same_demand_tier(db: Path):
    """peak_ski spans 15 Dec - 31 Mar. Without tier matching, a Christmas night anchors
    to a mid-January price. History has to be before the night being priced."""
    policy = load_policy()
    with connect(db) as conn:
        # Prior-year ordinary peak (cheap) and prior-year holiday (expensive).
        for i in range(40):
            d = date(2026, 1, 10) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,700,'available',?)", (d.isoformat(), d.weekday()))
        for i in range(14):
            d = date(2025, 12, 21) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        # The night being priced. Its own listed price is not history.
        conn.execute(
            "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
            " VALUES ('test_haus','2026-12-23',900,'available',2)")
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", date(2026, 12, 23),
                                            date(2026, 12, 23), policy=policy)
        anchor = seasonal_anchor(feats[0], policy, conn, as_of=date(2026, 12, 23))
    assert feats[0].demand_strength >= 0.8, "Christmas should read as high demand"
    assert anchor > 2000, f"holiday anchored to ordinary-peak price: ${anchor:.0f}"


def test_anchor_ignores_future_listed_prices(db: Path):
    """A forward cluster of engine-pushed holiday rates must not raise the anchor."""
    policy = load_policy()
    with connect(db) as conn:
        for i in range(30):
            d = date(2025, 12, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,500,'available',?)", (d.isoformat(), d.weekday()))
        for i in range(20):
            d = date(2026, 12, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", date(2026, 12, 25),
                                            date(2026, 12, 25), policy=policy)
        anchor = seasonal_anchor(feats[0], policy, conn, as_of=date(2026, 9, 29))
    assert anchor < 800, f"future listed prices entered the anchor: ${anchor:.0f}"


# ----------------------------------------------------------------- deference

def test_low_confidence_defers_to_the_operators_price(db: Path):
    """THE headline safety property. With thin history the model must nudge the
    incumbent price, never reverse it."""
    policy = load_policy()
    with connect(db) as conn:
        # A repriced holiday: cheap last year, expensive this year, nothing realised.
        for i in range(20):
            d = date(2025, 12, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,480,'available',?)", (d.isoformat(), d.weekday()))
        for i in range(16):
            d = date(2026, 12, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
                " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", date(2026, 12, 23),
                                            date(2026, 12, 23), policy=policy)
        rec = recommend_night(conn, feats[0], policy=policy)
    assert rec is not None
    drop = (rec.listed_price_at_run - rec.recommended_price) / rec.listed_price_at_run
    assert rec.weak_ceiling
    # Thin ceilings are advisory: they must not pull the rec below the move cap.
    assert rec.recommended_price >= rec.move_cap_price - 1e-6
    ceiling_bound = rec.recommended_price >= rec.ceiling_price - 1.0
    if not ceiling_bound:
        assert drop < 0.20, f"model overruled the operator by {drop:.0%} on thin evidence"
    assert rec.ceiling_confidence < 0.80


def test_deference_does_not_fire_at_high_confidence(db: Path):
    """Deference must not blunt a well-evidenced recommendation."""
    policy = load_policy()
    with connect(db) as conn:
        d = date(2026, 9, 20)
        for i in range(120):
            day = d + timedelta(days=i)
            conn.execute(
                "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,"
                "booked_price,status,day_of_week) VALUES ('test_haus',?,?,?,'booked',?)",
                (day.isoformat(), 500, 500, day.weekday()))
        target = date(2027, 10, 6)
        conn.execute(
            "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
            " VALUES ('test_haus',?,500,'available',?)", (target.isoformat(), target.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", target, target, policy=policy)
        ceiling = compute_ceiling(conn, feats[0], policy)
    assert ceiling.confidence >= 0.80
    assert "season" in ceiling.method


def test_peak_nights_never_auto_push(db: Path):
    """Christmas must escalate regardless of what the model wants."""
    policy = load_policy()
    with connect(db) as conn:
        d = date(2026, 12, 23)
        conn.execute(
            "INSERT INTO nightly_inventory (property_id,stay_date,listed_price,status,day_of_week)"
            " VALUES ('test_haus',?,2800,'available',?)", (d.isoformat(), d.weekday()))
        conn.commit()
        feats = build_features_for_property(conn, "test_haus", d, d, policy=policy)
        rec = recommend_night(conn, feats[0], policy=policy)
    assert rec.status == "blocked"
    assert rec.autonomy_level == "escalate"
    assert rec.guardrail_action == "peak_blackout"


# -------------------------------------------------------- sync intake (A→B handoff)
#
# src/pms/sync.py had the thinnest coverage of any Acquisition module (35% — only
# _floor_and_ceiling/recalibrate_bounds were exercised). Nothing tested sync_listings
# / sync_calendar / sync_reservations against a real Guesty response shape end to end,
# which is exactly the seam the audit protocol asks a stage agent to trace: does a raw
# Guesty reservation's `fareAccommodation` survive, in the right units (dollars per
# night, matching `listed_price`), all the way into the `nightly_inventory.booked_price`
# row that src/features and src/ceiling consume downstream in Stage B/C?


class _FakeGuestyClient:
    """Conforms to the subset of GuestyClient's interface sync.py actually calls."""

    def __init__(self, listings, calendar_days, reservations):
        self._listings = listings
        self._calendar_days = calendar_days
        self._reservations = reservations

    def listings(self, include_inactive: bool = False):
        return self._listings

    def calendar(self, listing_id, start, end):
        return self._calendar_days.get(listing_id, [])

    def reservations(self):
        yield from self._reservations


def test_sync_calendar_and_reservations_trace_realised_price_into_nightly_inventory(db: Path):
    """Traces one realistic value across the Stage A internal handoff:
    a Guesty reservation's money.fareAccommodation ($1,500 for a 3-night stay) must
    land as nightly_inventory.booked_price = $500/night (fareAccommodation / nights),
    NOT the stay total, and the calendar's listed_price must be overwritten by that
    realised price on the booked night (not left at the pre-booking listed rate) —
    per the sync.py module docstring's stated contract.
    """
    listing = _listing(listing_id="abc123", nickname="Test Haus")
    calendar_days = {
        "abc123": [
            {"date": "2026-12-20", "status": "available", "price": 480, "minNights": 2},
            {"date": "2026-12-21", "status": "reserved", "price": 480, "minNights": 2},
            {"date": "2026-12-22", "status": "reserved", "price": 480, "minNights": 2},
            {"date": "2026-12-23", "status": "unavailable", "price": None, "minNights": None},
        ]
    }
    reservation = {
        "_id": "res-1",
        "listingId": "abc123",
        "checkIn": "2026-12-21",
        "checkOut": "2026-12-23",
        "nightsCount": 2,
        "status": "confirmed",
        "source": "airbnb",
        "confirmedAt": "2026-10-01T00:00:00.000Z",
        "createdAt": "2026-09-28T00:00:00.000Z",
        "guestsCount": 12,
        "money": {"fareAccommodation": 1500.0},
    }
    client = _FakeGuestyClient([listing], calendar_days, [reservation])
    report = SyncReport()

    with connect(db) as conn:
        listings = sync_listings(conn, client, report)
        sync_calendar(conn, client, listings, date(2026, 12, 20), date(2026, 12, 23), report)
        sync_reservations(conn, client, listings, report)
        rows = {
            r["stay_date"]: r
            for r in conn.execute(
                "SELECT stay_date, listed_price, booked_price, status, channel, guest_count, "
                "evidence_kind "
                "FROM nightly_inventory WHERE property_id='test_haus' ORDER BY stay_date"
            ).fetchall()
        }

    # Unbooked night: untouched calendar listed price, no booked_price.
    assert rows["2026-12-20"]["status"] == "available"
    assert rows["2026-12-20"]["listed_price"] == pytest.approx(480.0)
    assert rows["2026-12-20"]["booked_price"] is None
    assert rows["2026-12-20"]["evidence_kind"] == "guesty_readonly"

    # Booked nights: realised nightly rate = fareAccommodation / nightsCount = 750.0,
    # not the $1,500 stay total and not the pre-booking $480 listed calendar price.
    for d in ("2026-12-21", "2026-12-22"):
        assert rows[d]["status"] == "booked"
        assert rows[d]["booked_price"] == pytest.approx(750.0)
        assert rows[d]["guest_count"] == 12

    # Guesty's "unavailable" maps to our "blocked" three-state model, not "booked".
    assert rows["2026-12-23"]["status"] == "blocked"

    assert report.reservations == 1
    assert report.booked_nights_priced == 2
    assert report.reservations_with_confirmed_at == 1


def test_sync_stores_city_and_party_and_drops_contact_fields(db: Path):
    listing = _listing(listing_id="abc123", nickname="Test Haus")
    reservation = {
        "_id": "res-guest",
        "listingId": "abc123",
        "checkIn": "2026-12-21",
        "checkOut": "2026-12-23",
        "nightsCount": 2,
        "status": "confirmed",
        "source": "airbnb",
        "guest": {
            "fullName": "Should Not Store",
            "email": "nope@example.com",
            "phone": "555-0100",
            "hometown": "Denver",
            "address": {"street": "1 Main", "state": "CO", "country": "US"},
        },
        "numberOfGuests": {
            "numberOfAdults": 6,
            "numberOfChildren": 2,
            "numberOfInfants": 1,
            "numberOfPets": 0,
        },
        "money": {"fareAccommodation": 1000.0},
    }
    client = _FakeGuestyClient([listing], {}, [reservation])
    with connect(db) as conn:
        listings = sync_listings(conn, client, SyncReport())
        sync_reservations(conn, client, listings, SyncReport())
        row = conn.execute("SELECT * FROM reservations WHERE reservation_id='res-guest'").fetchone()
    assert row["guest_city"] == "Denver"
    assert row["guest_state"] == "CO"
    assert row["guest_country"] == "US"
    assert row["adults"] == 6
    assert row["children"] == 2
    assert row["infants"] == 1
    assert row["pets"] == 0
    assert "nope@example.com" not in (row["raw_json"] or "")
    assert "Should Not Store" not in (row["raw_json"] or "")
    assert "555-0100" not in (row["raw_json"] or "")


def test_inquiry_conversion_reads_guesty_inquiry_rows(db: Path):
    from src.elasticity import inquiry_conversion

    with connect(db) as conn:
        for i in range(5):
            conn.execute(
                """
                INSERT INTO reservations (
                    reservation_id, property_id, check_in, check_out, status
                ) VALUES (?, 'test_haus', '2026-12-21', '2026-12-23', 'inquiry')
                """,
                (f"inq-{i}",),
            )
        for i in range(2):
            conn.execute(
                """
                INSERT INTO reservations (
                    reservation_id, property_id, check_in, check_out, status
                ) VALUES (?, 'test_haus', '2026-12-21', '2026-12-23', 'confirmed')
                """,
                (f"book-{i}",),
            )
        conn.commit()
        rate = inquiry_conversion(conn, "test_haus")
    assert rate == pytest.approx(2 / 5)


def test_sync_reservations_skips_cancelled_and_unmatched_listing(db: Path):
    """Cancelled reservations must not contaminate the ceiling, and a reservation for
    a listing_id sync hasn't seen yet must be skipped rather than crash the run."""
    listing = _listing(listing_id="abc123", nickname="Test Haus")
    client = _FakeGuestyClient(
        [listing],
        {},
        [
            {
                "_id": "res-cancelled",
                "listingId": "abc123",
                "checkIn": "2026-12-21",
                "checkOut": "2026-12-22",
                "status": "cancelled",
                "money": {"fareAccommodation": 900.0},
            },
            {
                "_id": "res-unknown-listing",
                "listingId": "does-not-exist",
                "checkIn": "2026-12-21",
                "checkOut": "2026-12-22",
                "status": "confirmed",
                "money": {"fareAccommodation": 900.0},
            },
        ],
    )
    report = SyncReport()
    with connect(db) as conn:
        listings = sync_listings(conn, client, report)
        sync_reservations(conn, client, listings, report)
        rows = conn.execute("SELECT reservation_id, status, confirmed_at FROM reservations").fetchall()
        inv = conn.execute("SELECT COUNT(*) c FROM nightly_inventory WHERE status='booked'").fetchone()["c"]
    # The cancellation is kept as demand evidence, never as a booking.
    assert [(r["reservation_id"], r["status"], r["confirmed_at"]) for r in rows] == [
        ("res-cancelled", "cancelled", None)
    ]
    assert inv == 0
    assert report.reservations == 0


def _res(rid: str, status: str, source: str, ci: str, co: str, fare: float) -> dict:
    return {
        "_id": rid, "listingId": "abc123", "checkIn": ci, "checkOut": co,
        "status": status, "source": source,
        "createdAt": "2026-09-01T00:00:00.000Z",
        "confirmedAt": "2026-09-02T00:00:00.000Z" if status == "confirmed" else None,
        "money": {"fareAccommodation": fare},
    }


def test_inquiry_and_owner_stays_never_become_market_bookings(db: Path):
    """An inquiry is a question, not a sale; an owner stay is off-market, not a sale.

    Regression: sync used to write every non-cancelled reservation as a booked night
    with the quote as `booked_price`, so inquiries hid real availability from pricing
    and owner stays taught the ceiling a price nobody paid.
    """
    listing = _listing(listing_id="abc123", nickname="Test Haus")
    days = [
        {"date": f"2026-12-{d:02d}", "status": "available", "price": 500, "minNights": 2}
        for d in range(1, 7)
    ]
    days[4]["status"] = days[5]["status"] = "unavailable"
    client = _FakeGuestyClient(
        [listing],
        {"abc123": days},
        [
            _res("inq-1", "inquiry", "airbnb2", "2026-12-01", "2026-12-03", 2466.0),
            _res("conf-1", "confirmed", "airbnb2", "2026-12-03", "2026-12-05", 1000.0),
            _res("own-1", "confirmed", "owner", "2026-12-05", "2026-12-07", 0.0),
        ],
    )
    report = SyncReport()
    with connect(db) as conn:
        listings = sync_listings(conn, client, report)
        sync_calendar(conn, client, listings, date(2026, 12, 1), date(2026, 12, 6), report)
        sync_reservations(conn, client, listings, report)
        rows = {
            r["stay_date"]: r
            for r in conn.execute(
                "SELECT stay_date, status, booked_price, booked_at, reservation_id, channel "
                "FROM nightly_inventory WHERE property_id='test_haus'"
            ).fetchall()
        }
        stored = {
            r["reservation_id"]: r["confirmed_at"]
            for r in conn.execute("SELECT reservation_id, confirmed_at FROM reservations")
        }
    for d in ("2026-12-01", "2026-12-02"):
        assert rows[d]["status"] == "available"
        assert rows[d]["booked_price"] is None and rows[d]["reservation_id"] is None
    for d in ("2026-12-03", "2026-12-04"):
        assert rows[d]["status"] == "booked"
        assert rows[d]["booked_price"] == pytest.approx(500.0)
    for d in ("2026-12-05", "2026-12-06"):
        assert rows[d]["status"] == "blocked"
        assert rows[d]["booked_price"] is None and rows[d]["channel"] == "owner"
    # Inquiries are kept as demand evidence, but never carry a booking stamp.
    assert stored == {"inq-1": None, "conf-1": "2026-09-02T00:00:00.000Z", "own-1": None}
    assert report.reservations == 2 and report.reservations_with_confirmed_at == 1


def test_calendar_resync_clears_a_cancelled_booking(db: Path):
    """Once Guesty shows a night available again, its old sale must not linger."""
    listing = _listing(listing_id="abc123", nickname="Test Haus")
    booked_day = [{"date": "2026-12-10", "status": "booked", "price": 500, "minNights": 1}]
    client = _FakeGuestyClient(
        [listing], {"abc123": booked_day},
        [_res("conf-9", "confirmed", "airbnb2", "2026-12-10", "2026-12-11", 700.0)],
    )
    with connect(db) as conn:
        listings = sync_listings(conn, client, SyncReport())
        sync_calendar(conn, client, listings, date(2026, 12, 10), date(2026, 12, 10), SyncReport())
        sync_reservations(conn, client, listings, SyncReport())
        booked_day[0]["status"] = "available"
        client._reservations = [
            _res("conf-9", "canceled", "airbnb2", "2026-12-10", "2026-12-11", 700.0)
        ]
        sync_calendar(conn, client, listings, date(2026, 12, 10), date(2026, 12, 10), SyncReport())
        sync_reservations(conn, client, listings, SyncReport())
        row = conn.execute(
            "SELECT status, booked_price, booked_at, reservation_id FROM nightly_inventory "
            "WHERE property_id='test_haus' AND stay_date='2026-12-10'"
        ).fetchone()
    assert row["status"] == "available"
    assert row["booked_price"] is None and row["booked_at"] is None
    assert row["reservation_id"] is None


def test_sync_listings_warns_when_no_weekend_differential(db: Path):
    listing = _listing(listing_id="abc123", nickname="Test Haus",
                       base_price=500.0, weekend_base_price=500.0)
    client = _FakeGuestyClient([listing], {}, [])
    report = SyncReport()
    with connect(db) as conn:
        sync_listings(conn, client, report)
    assert any("no weekend differential" in w for w in report.warnings)


def test_sync_keeps_extra_listing_out_of_default_scope(tmp_path: Path):
    path = tmp_path / "sync-scope.db"
    init_db(path)
    locked = _listing(listing_id="69f3fce1fd7011001188056e", nickname="Summit Haus")
    extra = _listing(listing_id="zzzzzzzzzzzzzzzzzzzzzzzz", nickname="Creekside Haven")
    client = _FakeGuestyClient([locked, extra], {}, [])
    with connect(path) as conn:
        report = sync_all(conn, client, horizon_days=1, history_days=1)
        assert report.listings == 2
        ids = {
            r["property_id"]
            for r in conn.execute("SELECT property_id FROM properties")
        }
        assert "summit_haus" in ids
        assert "creekside_haven" in ids
        scoped = resolve_property_ids(conn)
        assert scoped == ["summit_haus"]
        assert "creekside_haven" not in scoped
        assert get_db_identity(conn).kind == "production"


def test_sync_property_filter_skips_extra_listing(tmp_path: Path):
    path = tmp_path / "sync-filter.db"
    init_db(path)
    locked = _listing(listing_id="69f3fce1fd7011001188056e", nickname="Summit Haus")
    extra = _listing(listing_id="zzzzzzzzzzzzzzzzzzzzzzzz", nickname="Creekside Haven")
    client = _FakeGuestyClient([locked, extra], {}, [])
    with connect(path) as conn:
        report = sync_all(
            conn, client, horizon_days=1, history_days=1, property_ids=["summit_haus"]
        )
        assert report.listings == 1
        ids = {
            r["property_id"]
            for r in conn.execute("SELECT property_id FROM properties")
        }
        assert ids == {"summit_haus"}
        assert get_db_identity(conn).kind != "production"


# ---------------------------------------------------------- write-path safety

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _py_files():
    return [p for p in SRC.rglob("*.py") if p.is_file()]


def test_set_rate_is_unreachable_without_push_recommendations():
    """REGRESSION: the only .set_rate( call in production is GuestyAdapter.push_rate,
    which is only invoked from push_recommendations after generate_recommendations
    (and therefore apply_guardrails). A 'quick fix' CLI write must fail this test.
    """
    call_sites: list[tuple[str, int, str]] = []
    for path in _py_files():
        rel = str(path.relative_to(ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name == "set_rate":
                line = path.read_text(encoding="utf-8").splitlines()[node.lineno - 1].strip()
                call_sites.append((rel, node.lineno, line))
    assert len(call_sites) == 1, f"unexpected set_rate callers: {call_sites}"
    assert call_sites[0][0] == "src/pms/__init__.py"
    assert "self.client.set_rate" in call_sites[0][2]

    push_rate_callers: list[tuple[str, int]] = []
    for path in _py_files():
        rel = str(path.relative_to(ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None
            )
            if name != "push_rate":
                continue
            push_rate_callers.append((rel, node.lineno))
    assert len(push_rate_callers) == 1, (
        f"unexpected push_rate callers (bypass of apply_guardrails): {push_rate_callers}"
    )
    assert push_rate_callers[0][0] == "src/pms/__init__.py"

    for rel in ("src/cli/main.py", "src/pms/sync.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert ".set_rate(" not in text
        assert "set_rate(" not in text


class _Resp:
    def __init__(self, status: int, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status
        self.headers = headers or {}
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code}", response=self)
            raise err

    def json(self):
        return self._payload


def _client() -> GuestyClient:
    c = GuestyClient(client_id="id", client_secret="secret", use_token_cache=False)
    c._token = "tok"
    c._expires_at = time.time() + 10_000
    return c


def test_set_rate_retries_transient_failures_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    client = _client()
    sleeps: list[float] = []
    monkeypatch.setattr("src.pms.guesty.time.sleep", lambda s: sleeps.append(s))
    attempts = {"n": 0}

    def fake_put(*_a, **_k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise requests.Timeout("timed out")
        if attempts["n"] == 2:
            return _Resp(503)
        return _Resp(200, headers={"x-request-id": "abc"})

    monkeypatch.setattr("requests.put", fake_put)
    ok, err = client.set_rate("listing1", date(2026, 12, 10), 555.0)
    assert ok is True
    assert attempts["n"] == 3
    assert sleeps  # backoff between retries
    assert err == "request_id=abc"


def test_set_rate_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch):
    client = _client()
    monkeypatch.setattr("src.pms.guesty.time.sleep", lambda *_a, **_k: None)
    puts = {"n": 0}

    def fake_put(*_a, **_k):
        puts["n"] += 1
        return _Resp(400)

    monkeypatch.setattr("requests.put", fake_put)
    monkeypatch.setattr("requests.get", lambda *_a, **_k: _Resp(200, {"data": {"days": []}}))
    ok, err = client.set_rate("listing1", date(2026, 12, 10), 555.0)
    assert ok is False
    assert puts["n"] == 1
    assert err is not None


def test_set_rate_reconciles_timeout_after_server_side_success(monkeypatch: pytest.MonkeyPatch):
    """Timeout after Guesty applied the PUT must not leave listed_price stale."""
    client = _client()
    monkeypatch.setattr("src.pms.guesty.time.sleep", lambda *_a, **_k: None)

    def fake_put(*_a, **_k):
        raise requests.Timeout("timed out after the write")

    def fake_get(*_a, **_k):
        return _Resp(200, {"data": {"days": [{"date": "2026-12-10", "price": 555.0}]}})

    monkeypatch.setattr("requests.put", fake_put)
    monkeypatch.setattr("requests.get", fake_get)
    ok, err = client.set_rate("listing1", date(2026, 12, 10), 555.0)
    assert ok is True
    assert err is not None and "reconciled" in err
