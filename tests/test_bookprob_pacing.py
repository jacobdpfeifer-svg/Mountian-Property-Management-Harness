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


def test_pacing_ratio_ignores_future_snapshots(db: Path):
    """Point-in-time replay must not read pacing rows with as_of after decision."""
    target = date(2026, 12, 18)
    decision = date(2026, 11, 18)
    with connect(db) as conn:
        for i in range(21):
            as_of = date(2026, 11, 1) + timedelta(days=i)
            status = "booked" if i % 4 == 0 else "available"
            conn.execute(
                """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
                   VALUES (?, 'test_haus', ?, 30, ?)""",
                (as_of.isoformat(), (target + timedelta(days=i)).isoformat(), status),
            )
        conn.execute(
            """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
               VALUES ('2026-11-18', 'test_haus', ?, 30, 'booked')""",
            (target.isoformat(),),
        )
        conn.execute(
            """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
               VALUES ('2026-11-10', 'test_haus', ?, 30, 'available')""",
            ((target + timedelta(days=50)).isoformat(),),
        )
        conn.execute(
            """INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status)
               VALUES ('2026-12-25', 'test_haus', ?, 30, 'available')""",
            (target.isoformat(),),
        )
        conn.commit()
        feat, policy = _feat(conn, target)
        ratio_pit = pacing_ratio(conn, feat, policy, as_of=decision)
        ratio_future = pacing_ratio(conn, feat, policy, as_of=date(2026, 12, 26))
    assert ratio_pit is not None
    assert ratio_pit > 2.0
    assert ratio_future is not None
    assert ratio_pit > ratio_future


def test_lead_conditioning_uses_resolved_open_nights(tmp_path):
    """A night still open 3 days out must not inherit the all-time booking rate.

    Thirty past nights were each available 3 days before check-in and only three
    of them sold after that snapshot; the lead-conditioned p_ref must fall well
    below the unconditioned one, and nights after the decision date must not count.
    """
    import copy
    from datetime import date, timedelta

    from src.bookprob import estimate
    from src.config import load_policy
    from src.db import connect, init_db
    from src.features import build_features_for_property

    path = tmp_path / "lead.db"
    init_db(path)
    decision = date(2026, 9, 20)
    target = decision + timedelta(days=3)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
               VALUES ('h','H',5,5,'[]',2000,300,5000,'America/Denver','x')"""
        )
        for i in range(1, 31):
            stay = decision - timedelta(days=i)
            seen = stay - timedelta(days=3)
            conn.execute(
                "INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status) "
                "VALUES (?, 'h', ?, 3, 'available')",
                (seen.isoformat(), stay.isoformat()),
            )
            if i <= 3:
                conn.execute(
                    "INSERT INTO reservations (reservation_id, property_id, check_in, check_out, "
                    "status, source, confirmed_at) VALUES (?, 'h', ?, ?, 'confirmed', 'airbnb2', ?)",
                    (f"r{i}", stay.isoformat(), (stay + timedelta(days=1)).isoformat(),
                     (seen + timedelta(days=1)).isoformat()),
                )
        # A future open night is unresolved and must be ignored.
        conn.execute(
            "INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status) "
            "VALUES (?, 'h', ?, 3, 'available')",
            (decision.isoformat(), target.isoformat()),
        )
        conn.execute(
            "INSERT INTO nightly_inventory (property_id, stay_date, listed_price, status, "
            "day_of_week, lead_time_days) VALUES ('h', ?, 1000, 'available', ?, 3)",
            (target.isoformat(), target.weekday()),
        )
        conn.commit()
        policy = load_policy()
        off = copy.deepcopy(policy)
        off["booking_probability"]["lead_conditioning"]["enabled"] = False
        feat = build_features_for_property(conn, "h", target, target, policy=policy, as_of=decision)[0]
        on = estimate(conn, feat, policy, as_of=decision)
        base = estimate(conn, feat, off, as_of=decision)
    assert "lead:" in on.bucket and "n=30" in on.bucket
    assert on.p_ref < base.p_ref
    # (3 hits + 12 * prior) / (30 + 12): dominated by the 10% observed rate.
    assert on.p_ref == pytest.approx((3 + 12 * base.p_ref) / 42, rel=1e-6)
