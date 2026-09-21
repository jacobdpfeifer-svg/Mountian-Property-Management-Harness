"""src/signals/comp_movement.py was 46% covered per the Step 0 triage map — the
write path (upsert_comp_movement_signals) and the diagnostic helper
(market_median_lift) had no direct tests. This module is the one place Stage B
hands a derived demand signal *back* across the stage boundary into
src/scrape/__init__.py's daily cycle, so it is worth tracing concretely: comp
snapshots -> demand_signals row -> what src/features reads as a calendar event.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.db import connect, init_db
from src.signals.comp_movement import market_median_lift, upsert_comp_movement_signals


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "cm.db"
    init_db(db)
    return connect(db)


def _seed_comp(conn, comp_id="c1"):
    conn.execute(
        "INSERT INTO comps (comp_id, name, bedrooms, sleeps) VALUES (?, 'Comp', 5, 14)",
        (comp_id,),
    )
    conn.commit()


def _snap(conn, comp_id, as_of, stay_date, price, status="ok"):
    conn.execute(
        """
        INSERT INTO comp_snapshots (comp_id, as_of, stay_date, listed_price, scrape_status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (comp_id, as_of.isoformat(), stay_date.isoformat(), price, status),
    )
    conn.commit()


def test_no_recent_snapshots_writes_nothing(conn):
    written = upsert_comp_movement_signals(conn, as_of=date(2024, 12, 1))
    assert written == 0


def test_strong_lift_writes_demand_signal(conn):
    _seed_comp(conn)
    stay = date(2024, 12, 25)
    as_of = date(2024, 12, 10)
    # Baseline window (28-14 days back): $1000. Current window (14 days back): $1300
    # -> +30% lift, above the top (0.25 -> 0.85) threshold.
    _snap(conn, "c1", as_of - timedelta(days=20), stay, 1000.0)
    _snap(conn, "c1", as_of - timedelta(days=5), stay, 1300.0)

    written = upsert_comp_movement_signals(conn, as_of=as_of, lookback_days=14)
    assert written == 1

    row = conn.execute(
        "SELECT * FROM demand_signals WHERE signal_date = ? AND event_name = 'Comp-set rate lift'",
        (stay.isoformat(),),
    ).fetchone()
    assert row is not None
    assert row["signal_strength"] == pytest.approx(0.85)
    assert row["source"] == "comp_movement"


def test_small_lift_below_lowest_threshold_writes_nothing(conn):
    _seed_comp(conn)
    stay = date(2024, 12, 25)
    as_of = date(2024, 12, 10)
    _snap(conn, "c1", as_of - timedelta(days=20), stay, 1000.0)
    _snap(conn, "c1", as_of - timedelta(days=5), stay, 1020.0)  # +2%, below 8% floor

    written = upsert_comp_movement_signals(conn, as_of=as_of, lookback_days=14)
    assert written == 0


def test_existing_stronger_signal_is_not_downgraded(conn):
    """A calendar/manual event with a higher strength must not be overwritten by a
    weaker comp-movement reading for the same night — comp movement only takes the
    max, per the module's own docstring."""
    _seed_comp(conn)
    stay = date(2024, 12, 25)
    as_of = date(2024, 12, 10)
    conn.execute(
        """
        INSERT INTO demand_signals (signal_date, region, event_name, signal_strength, source)
        VALUES (?, 'winter_park', 'Comp-set rate lift', 0.95, 'manual')
        """,
        (stay.isoformat(),),
    )
    conn.commit()
    _snap(conn, "c1", as_of - timedelta(days=20), stay, 1000.0)
    _snap(conn, "c1", as_of - timedelta(days=5), stay, 1300.0)  # would be 0.85

    written = upsert_comp_movement_signals(conn, as_of=as_of, lookback_days=14)
    assert written == 0
    row = conn.execute(
        "SELECT signal_strength FROM demand_signals WHERE signal_date = ?", (stay.isoformat(),)
    ).fetchone()
    assert row["signal_strength"] == pytest.approx(0.95)


def test_only_ok_scrape_status_counts(conn):
    """A 'failed'/'unavailable' snapshot must not silently count as a price reading —
    same discipline as src/comps.comp_evidence."""
    _seed_comp(conn)
    stay = date(2024, 12, 25)
    as_of = date(2024, 12, 10)
    _snap(conn, "c1", as_of - timedelta(days=20), stay, 1000.0)
    _snap(conn, "c1", as_of - timedelta(days=5), stay, 5000.0, status="failed")

    written = upsert_comp_movement_signals(conn, as_of=as_of, lookback_days=14)
    assert written == 0  # the 'failed' row is excluded, so no current-window data


def test_market_median_lift_insufficient_rows_is_none(conn):
    assert market_median_lift(conn, date(2024, 12, 25)) is None


def test_market_median_lift_recent_window_is_not_lookback_filtered(conn, monkeypatch):
    """Documents a real bug found while writing this test (see stage report):
    `recent = [... for r in rows][:5]` takes the 5 newest snapshot rows
    unconditionally instead of filtering to rows newer than `older_cut`, the way
    `older` filters to rows on-or-before it. With only 2 total rows (a realistic
    count for the twice-weekly sweep cadence in docs/rules/COMP_DATA.md), the
    "recent" mean includes the very row that also anchors the "older" baseline,
    understating the true lift. Expected-if-correct would be (1000-800)/800=0.25;
    actual is 0.125 because `recent` = mean(1000, 800), not mean(1000).
    `market_median_lift` has no callers anywhere in src/ (confirmed by repo-wide
    grep) — this is a diagnostic helper, not wired into any pricing path — so this
    is recorded as a correctness bug for the Architect's dismantle-vs-fix call,
    not patched here (no consumer depends on either behavior)."""
    stay = date(2024, 12, 25)
    today = date(2024, 12, 10)

    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr("src.signals.comp_movement.date", _FrozenDate)

    old_as_of = today - timedelta(days=20)
    conn.execute(
        """
        INSERT INTO market_snapshots (as_of, stay_date, window_nights, region, listings, p50)
        VALUES (?, ?, 1, 'winter_park', 50, 800)
        """,
        (old_as_of.isoformat(), stay.isoformat()),
    )
    recent_as_of = today - timedelta(days=1)
    conn.execute(
        """
        INSERT INTO market_snapshots (as_of, stay_date, window_nights, region, listings, p50)
        VALUES (?, ?, 1, 'winter_park', 50, 1000)
        """,
        (recent_as_of.isoformat(), stay.isoformat()),
    )
    conn.commit()

    lift = market_median_lift(conn, stay, lookback_days=14)
    assert lift == pytest.approx(0.125)  # actual (buggy) behavior, not the true 0.25 lift
