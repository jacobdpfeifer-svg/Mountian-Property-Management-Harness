"""Honesty tests for the Guesty retrospective — what we can and cannot claim."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.db import connect, init_db
from src.eval.retrospective import format_markdown, score_history
from src.pacing import backfill_from_inventory


def _seed(conn) -> None:
    conn.execute(
        """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
           base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,owner_id)
           VALUES ('summit_haus','Summit Haus',5,5.5,'[]',2500,400,4000,
                   'America/Denver','northwoods')"""
    )
    conn.execute(
        """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
           base_ceiling_rate,min_floor_rate,max_ceiling_rate,timezone,owner_id)
           VALUES ('cloud_9','Cloud 9',6,4,'[]',1100,400,2000,
                   'America/Denver','cloud9')"""
    )
    # Christmas booked cheap; a later peak night booked high — leak-free cutoff
    # must not let the Dec 26 booking (confirmed Dec 20) inform a Dec 25 decision
    # made on Nov 25.
    rows = [
        ("summit_haus", "2025-12-20", 900, "booked", "2025-10-01"),
        ("summit_haus", "2025-12-21", 900, "booked", "2025-10-01"),
        ("summit_haus", "2025-12-22", 950, "booked", "2025-10-01"),
        ("summit_haus", "2025-12-23", 1000, "booked", "2025-10-15"),
        ("summit_haus", "2025-12-24", 1100, "booked", "2025-11-01"),
        ("summit_haus", "2025-12-25", 1200, "booked", "2025-11-10"),
        ("summit_haus", "2025-12-26", 2800, "booked", "2025-12-20"),
        ("summit_haus", "2026-01-05", 1300, "booked", "2025-12-01"),
        ("summit_haus", "2026-01-10", 400, "available", None),
        ("cloud_9", "2025-12-25", 800, "booked", "2025-09-01"),
    ]
    for pid, stay, price, status, booked_at in rows:
        stay_d = date.fromisoformat(stay)
        booked = price if status == "booked" else None
        listed = price
        conn.execute(
            """INSERT INTO nightly_inventory
               (property_id, stay_date, listed_price, booked_price, status,
                day_of_week, booked_at, channel)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'guesty')""",
            (pid, stay, listed, booked, status, stay_d.weekday(), booked_at),
        )
    conn.commit()


def test_report_separates_validated_from_pacing(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    with connect(db) as conn:
        _seed(conn)
        report = score_history(
            conn, start=date(2025, 12, 20), end=date(2026, 1, 10), lead_days=30,
            today=date(2026, 9, 1),
        )
    md = format_markdown(report)
    assert "Backed by real historical data" in md
    assert "Not validated" in md
    assert "Booking-probability" in md
    assert "pacing" in md.lower()
    assert "backfill_from_inventory" in md
    assert report.pacing_validated is False
    assert "one drought season is n=1" in report.confidence_note.lower() or "n=1" in report.confidence_note


def test_does_not_treat_pacing_backfill_as_evidence(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    with connect(db) as conn:
        _seed(conn)
        biased = backfill_from_inventory(conn, days=5)
        assert "biased" in biased["warning"]
        report = score_history(
            conn, start=date(2025, 12, 20), end=date(2025, 12, 26), lead_days=30,
            today=date(2026, 9, 1),
        )
    assert report.pacing_validated is False
    md = format_markdown(report)
    assert "does **not**" in md or "does not" in md.lower()


def test_future_booking_does_not_inflate_earlier_ceiling(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    with connect(db) as conn:
        _seed(conn)
        report = score_history(
            conn, start=date(2026, 1, 5), end=date(2026, 1, 5),
            property_ids=["summit_haus"], lead_days=30, today=date(2026, 9, 1),
        )
    night = report.nights[0]
    # Decision date is 2025-12-06. The $2,800 Dec 26 booking was confirmed Dec 20 —
    # after that decision — so it must not set the Jan 5 ceiling.
    assert night.decision_date == date(2025, 12, 6)
    assert night.ceiling_price < 2000


def test_owner_rollups_use_portfolio_ids(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    with connect(db) as conn:
        _seed(conn)
        report = score_history(
            conn, start=date(2025, 12, 20), end=date(2025, 12, 26),
            lead_days=30, today=date(2026, 9, 1),
        )
    assert "northwoods" in report.by_owner
    assert "cloud9" in report.by_owner
    md = format_markdown(report)
    assert "northwoods" in md
    assert "By owner" in md


def test_examples_are_not_only_favorable(tmp_path: Path):
    db = tmp_path / "r.db"
    init_db(db)
    with connect(db) as conn:
        _seed(conn)
        report = score_history(
            conn, start=date(2025, 12, 20), end=date(2025, 12, 26),
            lead_days=30, today=date(2026, 9, 1),
        )
    md = format_markdown(report)
    assert "both directions" in md.lower()
    assert "unproven" in md.lower()
