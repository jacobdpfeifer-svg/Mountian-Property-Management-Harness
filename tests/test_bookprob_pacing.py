"""bookprob.pacing_ratio — was 0% directly-tested (only exercised incidentally
through recommend_night with no pacing history, which always short-circuits to
None). This covers the real ratio computation and its thin-history guard."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.bookprob import pacing_ratio
from src.config import load_policy
from src.db import connect, init_db
from src.features import build_features_for_property


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "pacing.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
               VALUES ('test_haus','Test Haus',5,5.5,'[]',711,252,5000,
                       'America/Denver','abc123')"""
        )
        conn.commit()
    return path


def _feat(conn, target: date):
    conn.execute(
        """INSERT OR IGNORE INTO nightly_inventory
           (property_id, stay_date, listed_price, booked_price, status, day_of_week)
           VALUES ('test_haus', ?, 2000, NULL, 'available', ?)""",
        (target.isoformat(), target.weekday()),
    )
    conn.commit()
    policy = load_policy()
    feats = build_features_for_property(conn, "test_haus", target, target, policy=policy)
    return feats[0], policy


def test_pacing_ratio_none_below_min_snapshot_days(db: Path):
    """Fewer distinct as_of days than data_health.pacing_min_snapshot_days (14)
    must return None, not a ratio computed on too little history."""
    target = date(2026, 12, 18)
    with connect(db) as conn:
        for i in range(5):  # only 5 distinct as_of days
            as_of = date(2026, 12, 1) + timedelta(days=i)
            conn.execute(
                """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
                   VALUES (?, 'test_haus', ?, ?, 'booked')""",
                (as_of.isoformat(), target.isoformat(), (target - as_of).days),
            )
        conn.commit()
        feat, policy = _feat(conn, target)
        assert pacing_ratio(conn, feat, policy) is None


def test_pacing_ratio_none_without_enough_reference_cohort(db: Path):
    """>= min_snapshot_days of *some* history exists, but fewer than 20 snapshots
    share this night's days_out band -> still None, not a ratio on thin n."""
    target = date(2026, 12, 18)
    with connect(db) as conn:
        for i in range(15):
            as_of = date(2026, 11, 1) + timedelta(days=i)
            # days_out=999 is far outside the +/-3 band around the target night's
            # days_out=30, so these pad the >=14-distinct-as_of health gate without
            # joining the reference cohort.
            conn.execute(
                """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
                   VALUES (?, 'test_haus', ?, 999, 'available')""",
                (as_of.isoformat(), (target + timedelta(days=100 + i)).isoformat()),
            )
        # the target night itself, at days_out=30
        as_of = date(2026, 11, 18)
        conn.execute(
            """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
               VALUES (?, 'test_haus', ?, 30, 'booked')""",
            (as_of.isoformat(), target.isoformat()),
        )
        conn.commit()
        feat, policy = _feat(conn, target)
        assert pacing_ratio(conn, feat, policy) is None


def test_pacing_ratio_computes_real_ratio_when_ahead_of_norm(db: Path):
    """This night is booked while the days_out=30 cohort books at 25% -> ratio ~4x
    the portfolio norm (ahead of pace), a real number, not a stub."""
    target = date(2026, 12, 18)
    with connect(db) as conn:
        # >=14 distinct as_of days across the whole table (drives the health gate)
        for i in range(20):
            as_of = date(2026, 11, 1) + timedelta(days=i)
            status = "booked" if i % 4 == 0 else "available"  # 25% booked at this days_out
            conn.execute(
                """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
                   VALUES (?, 'test_haus', ?, 30, ?)""",
                (as_of.isoformat(), (target + timedelta(days=i)).isoformat(), status),
            )
        # latest snapshot for the target night itself: booked, days_out=30
        conn.execute(
            """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
               VALUES ('2026-11-18', 'test_haus', ?, 30, 'booked')""",
            (target.isoformat(),),
        )
        conn.commit()
        feat, policy = _feat(conn, target)
        ratio = pacing_ratio(conn, feat, policy)
    assert ratio is not None
    # booked_now=1.0, reference occupancy ~0.25-0.28 (target night's own row also
    # in the cohort window) -> materially > 1, i.e. genuinely "ahead of pace".
    assert ratio > 2.0
