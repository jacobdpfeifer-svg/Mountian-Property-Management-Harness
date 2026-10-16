"""Competitor anchor: each own-set comp's latest good quote (2026-10-16 audit repair).

The old query took one global MAX(as_of) for the night across every comp of
every property and every scrape status, then filtered. A later failed scrape,
another home's comp, or a partial scrape that reached one comp therefore
emptied or shrank the anchor. On the real database on 2026-10-16 it was empty
for every night: the four latest scrape days had no good quote at all.
"""

from __future__ import annotations

import sqlite3
import statistics
from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.db import connect, init_db
from src.pricing.pace import ANCHOR_MAX_AGE_DAYS, comp_anchor

STAY = date(2027, 2, 10)
DAY = date(2027, 1, 10)


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    path = tmp_path / "anchor.db"
    init_db(path, seed_markets=False)
    c = connect(path)
    for pid in ("h", "other"):
        c.execute(
            "INSERT INTO properties (property_id, name, bedrooms, bathrooms, base_ceiling_rate,"
            " min_floor_rate, max_ceiling_rate) VALUES (?, ?, 5, 4, 2000, 800, 5000)", (pid, pid))
    yield c
    c.close()


def _comp(c: sqlite3.Connection, comp_id: str, *members: str, active: int = 1) -> None:
    c.execute("INSERT OR IGNORE INTO comps (comp_id, name, active) VALUES (?, ?, ?)", (comp_id, comp_id, active))
    for pid in members:
        c.execute("INSERT INTO comp_set_members (property_id, comp_id) VALUES (?, ?)", (pid, comp_id))


def _quote(c: sqlite3.Connection, comp_id: str, as_of: date, price: float | None,
           status: str = "ok", stay: date = STAY) -> None:
    c.execute(
        "INSERT INTO comp_snapshots (comp_id, as_of, stay_date, listed_price, scrape_status)"
        " VALUES (?, ?, ?, ?, ?)", (comp_id, as_of.isoformat(), stay.isoformat(), price, status))


def _three_comps(c: sqlite3.Connection) -> None:
    for comp in ("a", "b", "c"):
        _comp(c, comp, "h")
    for comp, price in (("a", 1800), ("b", 2000), ("c", 2600)):
        _quote(c, comp, date(2027, 1, 1), price)


def test_latest_quote_on_or_before_the_decision_day(conn):
    _three_comps(conn)
    _quote(conn, "a", date(2027, 1, 20), 9999)          # after the decision day
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)
    assert comp_anchor(conn, "h", date(2027, 3, 1), DAY) == (None, 0)


def test_a_later_failed_scrape_does_not_hide_good_quotes(conn):
    _three_comps(conn)
    for comp in ("a", "b", "c"):
        _quote(conn, comp, date(2027, 1, 9), None, "failed")
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)


def test_a_partial_scrape_updates_only_the_comps_it_reached(conn):
    """The Reaper audit case: the newest scrape reached one comp of three."""
    _three_comps(conn)
    _quote(conn, "a", date(2027, 1, 9), 1900)
    _quote(conn, "b", date(2027, 1, 9), None, "failed")
    _quote(conn, "c", date(2027, 1, 9), None, "blocked")
    # Old behaviour: (1900.0, 1). Now a's new quote plus b's and c's last good ones.
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)


def test_another_homes_comp_set_never_sets_the_date_or_the_quotes(conn):
    _three_comps(conn)
    _comp(conn, "x", "other")
    _quote(conn, "x", date(2027, 1, 9), 300)
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)
    assert comp_anchor(conn, "other", STAY, DAY) == (300.0, 1)


def test_a_shared_comp_counts_once_for_each_home(conn):
    _three_comps(conn)
    _comp(conn, "s", "h", "other")
    _quote(conn, "s", date(2027, 1, 5), 2200)
    assert comp_anchor(conn, "h", STAY, DAY) == (2100.0, 4)
    assert comp_anchor(conn, "other", STAY, DAY) == (2200.0, 1)


def test_zero_negative_and_null_prices_are_not_quotes(conn):
    _three_comps(conn)
    _quote(conn, "a", date(2027, 1, 9), 0)
    _quote(conn, "b", date(2027, 1, 9), -5)
    _quote(conn, "c", date(2027, 1, 9), None)
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)


def test_an_unavailable_night_keeps_the_comps_last_good_quote(conn):
    """A comp that sold the night was last seen asking that price; it stays in."""
    _three_comps(conn)
    _quote(conn, "c", date(2027, 1, 9), None, "unavailable")
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)


def test_quotes_older_than_the_age_cap_drop_out(conn):
    _three_comps(conn)                                    # all scraped 2027-01-01
    _quote(conn, "a", date(2027, 1, 15), 1700)
    late = date(2027, 1, 1) + timedelta(days=ANCHOR_MAX_AGE_DAYS + 1)
    assert comp_anchor(conn, "h", STAY, late) == (1700.0, 1)
    edge = date(2027, 1, 1) + timedelta(days=ANCHOR_MAX_AGE_DAYS)
    assert comp_anchor(conn, "h", STAY, edge)[1] == 3
    assert comp_anchor(conn, "h", STAY, DAY, max_age_days=3) == (None, 0)


def test_inactive_comps_do_not_anchor(conn):
    _three_comps(conn)
    _comp(conn, "z", "h", active=0)
    _quote(conn, "z", date(2027, 1, 9), 99999)
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)


def test_a_timestamped_quote_on_the_decision_day_counts(conn):
    _three_comps(conn)
    conn.execute("INSERT INTO comp_snapshots (comp_id, as_of, stay_date, listed_price, scrape_status)"
                 " VALUES ('a', '2027-01-10T08:00:00', ?, 1900, 'ok')", (STAY.isoformat(),))
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)
    conn.execute("UPDATE comp_snapshots SET listed_price = 3000 WHERE as_of = '2027-01-10T08:00:00'")
    assert comp_anchor(conn, "h", STAY, DAY) == (2600.0, 3)


def test_only_the_requested_night_counts(conn):
    _three_comps(conn)
    _quote(conn, "a", date(2027, 1, 9), 99999, stay=STAY + timedelta(days=1))
    assert comp_anchor(conn, "h", STAY, DAY) == (2000.0, 3)


# -- property test against a brute-force reference ---------------------------------------

STATUSES = ("ok", "ok", "ok", "failed", "unavailable", "blocked", "stale")


def _reference(snaps, members, active, as_of, max_age):
    latest = {}
    for comp, day, price, status in snaps:
        if (comp in members and active[comp] and status == "ok" and price is not None and price > 0
                and as_of - timedelta(days=max_age) <= day <= as_of):
            if comp not in latest or day > latest[comp][0]:
                latest[comp] = (day, price)
    prices = [p for _, p in latest.values()]
    return (float(statistics.median(prices)), len(prices)) if prices else (None, 0)


@settings(max_examples=150, deadline=None)
@given(
    snaps=st.lists(st.tuples(
        st.sampled_from("abcdefg"), st.integers(0, 30), st.one_of(st.none(), st.integers(-10, 5000)),
        st.sampled_from(STATUSES)), max_size=40),
    members=st.sets(st.sampled_from("abcdefg"), min_size=1),
    inactive=st.sets(st.sampled_from("abcdefg"), max_size=2),
    decision=st.integers(0, 30),
    max_age=st.integers(0, 20),
)
def test_matches_a_brute_force_reference(tmp_path_factory, snaps, members, inactive, decision, max_age):
    path = tmp_path_factory.mktemp("prop") / "a.db"
    init_db(path, seed_markets=False)
    c = connect(path)
    c.execute("INSERT INTO properties (property_id, name, bedrooms, bathrooms, base_ceiling_rate,"
              " min_floor_rate, max_ceiling_rate) VALUES ('h','h',5,4,2000,800,5000)")
    active = {comp: comp not in inactive for comp in "abcdefg"}
    for comp in "abcdefg":
        c.execute("INSERT INTO comps (comp_id, name, active) VALUES (?, ?, ?)", (comp, comp, int(active[comp])))
    for comp in members:
        c.execute("INSERT INTO comp_set_members VALUES ('h', ?)", (comp,))
    base = date(2027, 1, 1)
    seen = {}
    for comp, offset, price, status in snaps:      # one row per (comp, day): the table is unique on it
        seen[(comp, offset)] = (comp, base + timedelta(days=offset), price, status)
    for comp, day, price, status in seen.values():
        _quote(c, comp, day, price, status)
    got = comp_anchor(c, "h", STAY, base + timedelta(days=decision), max_age_days=max_age)
    want = _reference(seen.values(), members, active, base + timedelta(days=decision), max_age)
    c.close()
    assert got == want
