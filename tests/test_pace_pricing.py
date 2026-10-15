"""Pace pricing (2026-10-14 overhaul, Phase 4)."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.config import load_policy, load_policy_overlay
from src.pricing import MODEL_NAMES, enabled
from src.pricing.pace import (
    PaceReading,
    all_in_beta,
    comp_anchor,
    curve_share,
    fees_per_night,
    on_books_share,
    owner_terms,
    pace_multiplier,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "config" / "policies" / "candidates" / "pace_learned_owner_net.yaml"
ECON = {
    "guest_fees": {"cleaning_per_stay": 600, "per_guest": 75, "insurance_per_stay": 80},
    "channel_fee": 0.155, "management_fee": 0.25, "turnover_cost_per_stay": 350,
    "consumables_cost_per_guest": 75, "insurance_cost_per_stay": 80,
    "typical_party": 10, "typical_los": 4,
}


def test_pace_pricing_is_off_in_the_default_policy_and_on_in_the_candidate():
    assert "pace_pricing" in MODEL_NAMES
    assert not enabled(load_policy(), "pace_pricing")
    candidate = load_policy_overlay(CANDIDATE)
    assert enabled(candidate, "pace_pricing") and enabled(candidate, "learned_elasticity")
    # The hard peak caps are removed by null, not left in place by the merge.
    caps = candidate["ceiling"]["property_season_ceiling"]
    assert caps["cloud_9"]["peak_ski"] is None


def test_reference_curve_interpolates_and_is_monotone():
    assert curve_share(0) == 1.0
    assert curve_share(500) == pytest.approx(0.12)
    assert curve_share(45) == pytest.approx((0.35 + 0.55) / 2)
    leads = [0, 7, 14, 21, 30, 60, 90, 120]
    shares = [curve_share(lead) for lead in leads]
    assert shares == sorted(shares, reverse=True)


def test_pace_multiplier_raises_when_ahead_lowers_when_behind_and_is_bounded():
    cfg = {"sensitivity": 0.30, "min_multiplier": 0.85, "max_multiplier": 1.25}
    on_pace = PaceReading(0.40, 0.40, "curve", 0)
    ahead = PaceReading(0.80, 0.40, "curve", 0)
    behind = PaceReading(0.05, 0.40, "curve", 0)
    assert pace_multiplier(on_pace, cfg) == pytest.approx(1.0)
    assert 1.0 < pace_multiplier(ahead, cfg) <= 1.25
    assert 0.85 <= pace_multiplier(behind, cfg) < 1.0
    assert pace_multiplier(PaceReading(1.0, 0.0, "curve", 0), cfg) == 1.25


def test_fees_make_the_nightly_rate_less_elastic():
    fpn = fees_per_night(ECON)
    assert fpn == pytest.approx((600 + 750 + 80) / 4)
    assert all_in_beta(-1.0, 2000.0, ECON) == pytest.approx(-2000 / (2000 + fpn))
    # Cheaper nights carry a bigger fee share, so the effect is larger off-peak.
    assert abs(all_in_beta(-1.0, 600.0, ECON)) < abs(all_in_beta(-1.0, 2000.0, ECON))


def test_owner_terms_split_the_nightly_rate_and_the_fee_margin():
    share, margin = owner_terms(ECON)
    assert share == pytest.approx(1 - 0.155 - 0.25)
    assert margin == pytest.approx(((600 + 750 + 80) * 0.845 - (350 + 750 + 80)) / 4)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE nightly_inventory (property_id TEXT, stay_date TEXT, status TEXT, booked_at TEXT);
        CREATE TABLE comp_snapshots (comp_id TEXT, as_of TEXT, stay_date TEXT, listed_price REAL, scrape_status TEXT);
        CREATE TABLE comp_set_members (property_id TEXT, comp_id TEXT);
        """
    )
    return conn


def test_on_books_share_ignores_bookings_made_after_the_decision_day():
    conn = _db()
    stay = date(2027, 2, 10)
    for offset in range(-3, 4):
        night = (stay + timedelta(days=offset)).isoformat()
        booked_at = "2027-01-05" if offset < 0 else "2027-01-25"
        conn.execute("INSERT INTO nightly_inventory VALUES ('h', ?, 'booked', ?)", (night, booked_at))
    assert on_books_share(conn, stay, date(2027, 1, 10), 3) == pytest.approx(3 / 7)
    assert on_books_share(conn, stay, date(2027, 1, 30), 3) == pytest.approx(1.0)


def test_comp_anchor_uses_the_latest_scrape_on_or_before_the_decision_day():
    conn = _db()
    for comp in ("a", "b", "c"):
        conn.execute("INSERT INTO comp_set_members VALUES ('h', ?)", (comp,))
    rows = [
        ("a", "2027-01-01", 1800), ("b", "2027-01-01", 2000), ("c", "2027-01-01", 2600),
        ("a", "2027-01-20", 9999),  # after the decision day: must be ignored
    ]
    for comp, as_of, price in rows:
        conn.execute("INSERT INTO comp_snapshots VALUES (?, ?, '2027-02-10', ?, 'ok')", (comp, as_of, price))
    median, n = comp_anchor(conn, "h", date(2027, 2, 10), date(2027, 1, 10))
    assert (median, n) == (2000.0, 3)
    assert comp_anchor(conn, "h", date(2027, 3, 1), date(2027, 1, 10)) == (None, 0)


def test_own_sold_evidence_counts_only_sales_known_by_the_decision_day():
    from src.pricing.pace import own_sold_evidence

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE nightly_inventory (property_id TEXT, stay_date TEXT, status TEXT, "
                 "booked_price REAL, booked_at TEXT)")
    rows = [
        ("h", "2026-12-24", "booked", 3300, "2026-10-01"),
        ("h", "2026-12-25", "booked", 3500, "2026-10-02"),
        ("h", "2026-12-26", "booked", 9999, "2026-12-01"),   # sold after the decision day
        ("h", "2026-12-27", "available", None, None),          # listed, never sold: not evidence
        ("other", "2026-12-24", "booked", 100, "2026-10-01"),
    ]
    conn.executemany("INSERT INTO nightly_inventory VALUES (?,?,?,?,?)", rows)
    stays = {"2026-12-24", "2026-12-25", "2026-12-26", "2026-12-27"}
    assert own_sold_evidence(conn, "h", date(2026, 10, 15), stays) == (3400.0, 2)
    assert own_sold_evidence(conn, "h", date(2026, 10, 15), set()) == (None, 0)


def test_blend_reference_moves_toward_own_sales_as_they_accumulate():
    from src.pricing.pace import blend_reference

    assert blend_reference(2000.0, None, 0, 10) == 2000.0
    assert blend_reference(None, 3000.0, 5, 10) == 3000.0
    assert blend_reference(2000.0, 3000.0, 10, 10) == pytest.approx(2500.0)
    assert blend_reference(2000.0, 3000.0, 90, 10) == pytest.approx(2900.0)
