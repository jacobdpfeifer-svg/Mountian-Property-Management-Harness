"""Point-in-time replay: honesty guards, scoring, and the bookprob leak fix."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.bookprob import estimate
from src.config import load_policy
from src.db import connect, init_db
from src.eval.replay import (
    ReplayError,
    ReplayRow,
    estimate_revenue,
    run_replay,
    score_calibration,
    score_direction,
    write_reports,
)
from src.eval.shadow import GuestyWriteForbidden
from src.features import build_features_for_property
from src.ingest import CsvIngestAdapter

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"


def _row(**kw) -> ReplayRow:
    base = dict(
        as_of="2026-09-20", property_id="p", stay_date="2026-09-25",
        recommended_price=1000.0, expected_book_prob=0.5, listed_as_of=900.0,
        listed_source="pacing", booked_at=None, booked_by_censor=False,
        resolved=True, lead_time_days=5, season="summer",
    )
    base.update(kw)
    return ReplayRow(**base)


# ------------------------------------------------------------- scoring: honesty


def test_calibration_refuses_unresolved_future_nights():
    """Terminal probability vs a censored outcome would mislead; unresolved excluded."""
    rows = [_row(resolved=False, expected_book_prob=0.4, booked_by_censor=False)
            for _ in range(50)]
    out = score_calibration(rows)
    assert out["measurable"] is False
    assert out["eligible"] == 0
    assert "terminal" in out["reason"].lower()


def test_calibration_measurable_on_enough_resolved():
    rows = []
    for i in range(40):
        booked = i % 2 == 0
        rows.append(_row(resolved=True, expected_book_prob=0.5, booked_by_censor=booked))
    out = score_calibration(rows)
    assert out["measurable"] is True
    assert out["eligible"] == 40
    assert 0.0 <= out["brier"] <= 1.0


def test_direction_unmeasurable_when_groups_thin():
    rows = [_row(resolved=True, recommended_price=1000, listed_as_of=900)]  # 1 above
    out = score_direction(rows)
    assert out["measurable"] is False


def test_estimate_revenue_is_labeled_and_not_a_win():
    rows = [
        _row(recommended_price=1000, listed_as_of=800, booked_by_censor=True, expected_book_prob=0.5),
        _row(recommended_price=1200, listed_as_of=900, booked_by_censor=False, expected_book_prob=0.4),
    ]
    out = estimate_revenue(rows)
    assert out["measurable"] is True
    assert "do not respond to price" in out["assumption"]
    assert out["comparable_nights"] == 2
    # Both figures are price-swap under fixed bookings; they are references, not proof.
    assert "bookings_unchanged" in out and "engine_demand_model" in out


# --------------------------------------------------------------- run_replay guards


def _seed_sample(path: Path) -> None:
    init_db(path)
    with connect(path) as conn:
        CsvIngestAdapter(
            properties_csv=SAMPLE / "properties.csv",
            inventory_csv=SAMPLE / "nightly_inventory.csv",
            comps_csv=SAMPLE / "comps.csv",
            demand_csv=SAMPLE / "demand_signals.csv",
            inquiries_csv=SAMPLE / "booking_inquiries.csv",
        ).load_all(conn)


def test_run_replay_refuses_guesty_writes(tmp_path: Path):
    db = tmp_path / "r.db"
    _seed_sample(db)
    with connect(db) as conn:
        conn.execute(
            "INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status, listed_price)"
            " VALUES ('2026-09-20','aspen_glow','2026-12-01',72,'available',1000)"
        )
        conn.execute(
            """INSERT INTO rate_changes
               (property_id, stay_date, old_price, new_price, actor, autonomy_level, result)
               VALUES ('aspen_glow','2026-12-01',100,110,'guesty','handle','applied')"""
        )
        conn.commit()
        with pytest.raises(GuestyWriteForbidden):
            run_replay(conn, date(2026, 9, 20), date(2026, 9, 21), ["aspen_glow"])


def test_run_replay_raises_without_pacing_days(tmp_path: Path):
    db = tmp_path / "r.db"
    _seed_sample(db)
    with connect(db) as conn:
        with pytest.raises(ReplayError):
            run_replay(conn, date(2030, 1, 1), date(2030, 1, 2), ["aspen_glow"])


def test_run_replay_end_to_end_writes_reports(tmp_path: Path):
    db = tmp_path / "r.db"
    _seed_sample(db)
    with connect(db) as conn:
        for i in range(2):
            as_of = date(2026, 9, 20) + timedelta(days=i)
            conn.execute(
                "INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status, listed_price)"
                " VALUES (?, 'aspen_glow', '2026-12-05', ?, 'available', 1200)",
                (as_of.isoformat(), (date(2026, 12, 5) - as_of).days),
            )
        conn.commit()
        result = run_replay(
            conn, date(2026, 9, 20), date(2026, 9, 21), ["aspen_glow"], horizon_days=120
        )
    assert result.decision_days == ["2026-09-20", "2026-09-21"]
    assert result.rows, "expected at least one priced night-decision"
    # Future ski nights are unresolved by the Sept censor -> calibration unmeasurable.
    assert result.calibration["measurable"] is False
    paths = write_reports(result, tmp_path / "out")
    assert paths["html"].exists() and paths["json"].exists() and paths["csv"].exists()
    assert "does not show the engine beat the market" in paths["html"].read_text()


# ------------------------------------------------------- bookprob lookahead leak


@pytest.fixture()
def leak_db(tmp_path: Path):
    path = tmp_path / "leak.db"
    init_db(path)
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,pms_listing_id)
               VALUES ('test_haus','Test Haus',5,5.5,'[]',2000,300,5000,
                       'America/Denver','abc123')"""
        )
        conn.commit()
    return path


def test_bookprob_pool_ignores_bookings_after_decision(leak_db: Path):
    """A sale confirmed after the decision date must not enter the booking pool.

    Ten summer-Friday nights all booked, but stamped booked_at AFTER the decision
    date: as-of that date the model should see zero bookings; as-of after the
    stamp it should see them, so p_ref must be strictly higher later.
    """
    target = date(2026, 7, 17)  # Friday, summer
    decision = date(2026, 7, 1)
    after = date(2026, 8, 1)
    with connect(leak_db) as conn:
        for i in range(10):
            night = target - timedelta(days=7 * (i + 1))  # earlier summer Fridays
            conn.execute(
                """INSERT INTO nightly_inventory
                   (property_id, stay_date, listed_price, booked_price, status,
                    day_of_week, booked_at)
                   VALUES ('test_haus', ?, 1800, 1900, 'booked', ?, ?)""",
                (night.isoformat(), night.weekday(), "2026-07-20"),  # booked_at after decision
            )
        conn.execute(
            """INSERT INTO nightly_inventory
               (property_id, stay_date, listed_price, status, day_of_week)
               VALUES ('test_haus', ?, 2000, 'available', ?)""",
            (target.isoformat(), target.weekday()),
        )
        conn.commit()
        policy = load_policy()
        feat = build_features_for_property(conn, "test_haus", target, target, policy=policy)[0]
        p_before = estimate(conn, feat, policy, as_of=decision).p_ref
        p_after = estimate(conn, feat, policy, as_of=after).p_ref
    assert p_before < p_after, (
        f"leak: p_ref did not rise once bookings became known ({p_before} !< {p_after})"
    )
