"""src/scrape/properties.py — owned-listing (twins/Cloud 9) scrape tests.

This module had ZERO direct tests before this pass (0/23% line coverage on a
200-line module) despite LOCKED_INPUTS.md flagging "twins comp set still
pipeline-exercise" / "comp scraper not run for twins" as an open item — this is
exactly the code that runs when it is. It is a separate path from src/scrape's
market-comp sweep (tests/test_scrape.py): this one populates the *owned*
listings' own nightly_inventory rows (price + availability) from the market
sweep + Airbnb calendar, which src/pacing and src/features consume directly.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.db import connect, init_db
from src.scrape import plan_windows
from src.scrape.properties import (
    DiscoveryMatch,
    _fill_price_gaps,
    discover_owned_listings,
    persist_room_ids,
    score_listing,
    scrape_properties,
)
from src.scrape.providers import FixtureProvider

START = date(2026, 12, 1)  # a Tuesday


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "props.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone)
               VALUES ('summit_haus','Summit Haus',5,5.5,'[]',1854,252,3000,'America/Denver')"""
        )
        conn.commit()
    return path


# --------------------------------------------------------------- score_listing

def test_score_listing_matches_name_and_address_variants():
    assert score_listing("summit_haus", "Summit Haus - Luxury Ski Chalet") == 10
    # Address-only matches (no "haus"/"ridge" in the matched pattern) score lower
    # than a name match — see score_listing's weighting.
    assert score_listing("summit_haus", "Home at 312 N Woods Pl") == 5
    assert score_listing("overlook_ridge", "300 N. Woods, Winter Park") == 5
    assert score_listing("summit_haus", "Totally unrelated cabin") == 0
    assert score_listing("summit_haus", None) == 0


def test_score_listing_weak_n_woods_match_scores_lower_than_name_match():
    weak = score_listing("summit_haus", "5BR home on N Woods area")
    strong = score_listing("summit_haus", "Summit Haus")
    assert 0 < weak < strong


# ----------------------------------------------------------- discover_owned_listings

def test_discover_owned_listings_picks_best_scoring_room(tmp_path: Path):
    fixture = {
        "sweeps": {
            (START + timedelta(days=17)).isoformat(): [
                {"room_id": "r1", "nightly_price": 2600.0, "name": "Summit Haus - 312 N Woods"},
                {"room_id": "r2", "nightly_price": 900.0, "name": "Some other 3BR condo"},
            ],
            (START + timedelta(days=23)).isoformat(): [],
            (START + timedelta(days=4)).isoformat(): [],
        },
        "calendars": {},
    }
    path = tmp_path / "discover.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    matches = discover_owned_listings(
        FixtureProvider(path), [START + timedelta(days=17), START + timedelta(days=23),
                                START + timedelta(days=4)],
        property_ids=["summit_haus"],
    )
    assert len(matches) == 1
    assert matches[0].room_id == "r1"
    assert matches[0].score == 10


def test_discover_owned_listings_falls_back_to_luxury_proxy_when_not_found(tmp_path: Path):
    """Direct-book-only twins never appear in a market sweep by name — the proxy
    fallback exists precisely so the ceiling still gets *some* market signal."""
    fixture = {
        "sweeps": {
            (START + timedelta(days=17)).isoformat(): [
                {"room_id": "proxy1", "nightly_price": 1400.0, "name": "5BR Luxury Northwood Lodge"},
                {"room_id": "small1", "nightly_price": 250.0, "name": "Cozy studio"},
            ],
            (START + timedelta(days=23)).isoformat(): [],
            (START + timedelta(days=4)).isoformat(): [],
        },
        "calendars": {},
    }
    path = tmp_path / "proxy.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    matches = discover_owned_listings(
        FixtureProvider(path), [START + timedelta(days=17), START + timedelta(days=23),
                                START + timedelta(days=4)],
        property_ids=["summit_haus"],
    )
    assert len(matches) == 1
    assert matches[0].room_id == "proxy1"
    assert matches[0].name.startswith("PROXY:")


def test_discover_owned_listings_no_proxy_fallback_when_disabled(tmp_path: Path):
    fixture = {"sweeps": {(START + timedelta(days=17)).isoformat(): [
        {"room_id": "proxy1", "nightly_price": 1400.0, "name": "5BR Luxury Lodge"},
    ]}, "calendars": {}}
    path = tmp_path / "no_proxy.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    matches = discover_owned_listings(
        FixtureProvider(path), [START + timedelta(days=17)],
        property_ids=["summit_haus"], allow_proxy_fallback=False,
    )
    assert matches == []


# ------------------------------------------------------------------ _fill_price_gaps

def test_fill_price_gaps_forward_fills_from_nearest_same_weekday():
    prices = {date(2026, 12, 1): 400.0, date(2026, 12, 8): 460.0}  # both Tuesdays
    filled = _fill_price_gaps(prices, date(2026, 12, 1), date(2026, 12, 8))
    # 12/2 (Wed) has no same-weekday observation in range -> stays unfilled.
    assert date(2026, 12, 2) not in filled
    # 12/1 and 12/8 pass through unchanged.
    assert filled[date(2026, 12, 1)] == 400.0
    assert filled[date(2026, 12, 8)] == 460.0


# ---------------------------------------------------------------- scrape_properties

def test_scrape_properties_writes_price_and_status_from_sweep_and_calendar(db: Path):
    """End-to-end: a market sweep price for the twin's known Airbnb room_id must land
    in nightly_inventory.listed_price (not booked_price — this is a *listed* rate,
    the PMS calendar/reservations path is the only source of realised booked_price),
    and Airbnb calendar availability must set status."""
    end = START + timedelta(days=6)
    windows = plan_windows(START - timedelta(days=7), (end - (START - timedelta(days=7))).days + 7, 2)

    sweeps = {}
    for w in windows:
        if w <= end:
            sweeps[w.isoformat()] = [{"room_id": "room-summit", "nightly_price": 2750.0,
                                       "name": "Summit Haus"}]
    fixture = {
        "sweeps": sweeps,
        "calendars": {
            "room-summit": {
                (START + timedelta(days=1)).isoformat(): {"available": False, "min_nights": 3},
                (START + timedelta(days=2)).isoformat(): {"available": True, "min_nights": 3},
            }
        },
    }
    path = db.parent / "sweep.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    with connect(db) as conn:
        conn.execute(
            "UPDATE properties SET airbnb_room_id='room-summit' WHERE property_id='summit_haus'"
        )
        conn.commit()
        report = scrape_properties(conn, FixtureProvider(path), START, end)
        rows = {
            r["stay_date"]: r
            for r in conn.execute(
                "SELECT stay_date, listed_price, booked_price, status FROM nightly_inventory "
                "WHERE property_id='summit_haus' ORDER BY stay_date"
            ).fetchall()
        }

    assert report.sweeps_ok > 0
    assert len(rows) == 7  # START..end inclusive
    # Calendar-marked booked night.
    booked_day = (START + timedelta(days=1)).isoformat()
    assert rows[booked_day]["status"] == "booked"
    assert rows[booked_day]["booked_price"] is None  # scrape never writes booked_price
    # Tue/Wed and Fri/Sat nights are directly priced by the sampled sweep windows.
    for delta in (0, 1, 3, 4):  # Tue, Wed, Fri, Sat
        d = (START + timedelta(days=delta)).isoformat()
        assert rows[d]["listed_price"] == pytest.approx(2750.0), d
    # Thu/Sun have no same-weekday priced night inside this single-week fixture, so
    # _fill_price_gaps has nothing to forward-fill from — this is a real gap the
    # operator would see, not a bug, but it must not be silently invented as $2750.
    for delta in (2, 5):  # Thu, Sun
        d = (START + timedelta(days=delta)).isoformat()
        assert rows[d]["listed_price"] is None, d
    # A day with no calendar entry at all defaults to available.
    no_cal_day = (START + timedelta(days=5)).isoformat()
    assert rows[no_cal_day]["status"] == "available"


def test_scrape_properties_flags_when_using_proxy(db: Path):
    end = START + timedelta(days=1)
    with connect(db) as conn:
        conn.execute(
            "UPDATE properties SET airbnb_room_id='proxy-room' WHERE property_id='summit_haus'"
        )
        conn.commit()
        windows = plan_windows(START - timedelta(days=7),
                               (end - (START - timedelta(days=7))).days + 7, 2)
        sweeps = {w.isoformat(): [{"room_id": "proxy-room", "nightly_price": 1300.0,
                                    "name": "PROXY:5BR Luxury Lodge"}]
                  for w in windows if w <= end}
        path = db.parent / "proxy_sweep.json"
        path.write_text(json.dumps({"sweeps": sweeps, "calendars": {}}), encoding="utf-8")

        report = scrape_properties(
            conn, FixtureProvider(path), START, end,
            discover=True,
            discover_dates=[START],
        )
    # discover_owned_listings ran and (re)persisted a proxy match; the per-property
    # report must warn that this listing's rate is a market proxy, not its own.
    prop_reports = [p for p in report.properties if p.property_id == "summit_haus"]
    assert prop_reports
    assert any("proxy" in e for e in prop_reports[0].errors)


def test_scrape_properties_no_owned_room_ids_is_a_noop(tmp_path: Path):
    path = tmp_path / "empty.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone)
               VALUES ('summit_haus','Summit Haus',5,5.5,'[]',1854,252,3000,'America/Denver')"""
        )
        conn.commit()
        # No airbnb_room_id set anywhere -> scrape_properties must return early,
        # not error, since discover=False by default.
        fpath = tmp_path / "unused.json"
        fpath.write_text(json.dumps({"sweeps": {}, "calendars": {}}), encoding="utf-8")
        report = scrape_properties(conn, FixtureProvider(fpath), START, START)
    assert report.properties == []
    assert report.total_nights == 0


def test_persist_room_ids_updates_property_rows(db: Path):
    with connect(db) as conn:
        n = persist_room_ids(conn, [DiscoveryMatch("summit_haus", "room-x", "Summit Haus",
                                                     2600.0, 10)])
        row = conn.execute(
            "SELECT airbnb_room_id FROM properties WHERE property_id='summit_haus'"
        ).fetchone()
    assert n == 1
    assert row["airbnb_room_id"] == "room-x"
