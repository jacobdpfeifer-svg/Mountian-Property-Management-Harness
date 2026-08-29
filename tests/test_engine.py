"""Engine tests.

The v1 suite passed 6/6 while the engine recommended a median +22% price increase on
the weakest demand nights of the year. It contained tautologies (`assert n >= 0`,
`assert sample_size >= 0`) and one assertion that actively enshrined the ceiling-cap
defect as intended behaviour. Every test below either pins a real invariant or is a
regression test for a specific defect found in the audit.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.bookprob import BookingProbability
from src.ceiling import compute_ceiling
from src.compose import generate_recommendations, recommend_night
from src.config import load_policy
from src.db import connect, init_db
from src.eval import compute_revpan, format_report, record_outcomes_from_inventory
from src.explain import Reason, select_top_reasons
from src.features import build_features_for_property
from src.guardrails import apply_guardrails, assess_data_health
from src.ingest import CsvIngestAdapter, ICalIngestAdapter
from src.leakage import scan_leakage
from src.pacing import take_snapshot

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"


def _adapter() -> CsvIngestAdapter:
    return CsvIngestAdapter(
        properties_csv=SAMPLE / "properties.csv",
        inventory_csv=SAMPLE / "nightly_inventory.csv",
        comps_csv=SAMPLE / "comps.csv",
        demand_csv=SAMPLE / "demand_signals.csv",
        inquiries_csv=SAMPLE / "booking_inquiries.csv",
    )


@pytest.fixture()
def db(tmp_path: Path):
    path = tmp_path / "test.db"
    init_db(path)
    with connect(path) as conn:
        _adapter().load_all(conn)
    return path


# --------------------------------------------------------------------- ingest

def test_csv_ingest_loads_four_properties(db: Path):
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM properties").fetchone()["c"] == 4
        assert conn.execute("SELECT COUNT(*) c FROM nightly_inventory").fetchone()["c"] > 100


def test_ingest_is_idempotent(db: Path):
    """REGRESSION: v1 used bare INSERTs with no unique constraint, so re-running
    ingest silently doubled demand_signals, booking_inquiries and comp_snapshots."""
    with connect(db) as conn:
        before = {
            t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            for t in ("demand_signals", "booking_inquiries", "comp_snapshots", "nightly_inventory")
        }
        _adapter().load_all(conn)
        after = {
            t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            for t in before
        }
    assert before == after, f"re-ingest changed row counts: {before} -> {after}"


def test_ical_does_not_erase_prices(db: Path):
    """REGRESSION: the iCal adapter carries no prices and v1's upsert wrote
    excluded.listed_price unconditionally, so running it after the CSV adapter
    overwrote every listed_price with NULL."""
    with connect(db) as conn:
        row = conn.execute(
            "SELECT stay_date, listed_price FROM nightly_inventory "
            "WHERE property_id='cabin_ridge' AND listed_price IS NOT NULL LIMIT 1"
        ).fetchone()
        assert row is not None
        target_date, price_before = row["stay_date"], row["listed_price"]

        ICalIngestAdapter("cabin_ridge", SAMPLE / "cabin_ridge.ics",
                          default_listed_price=None).load_inventory(conn)

        after = conn.execute(
            "SELECT listed_price FROM nightly_inventory "
            "WHERE property_id='cabin_ridge' AND stay_date=?", (target_date,)
        ).fetchone()["listed_price"]
    assert after == price_before


# -------------------------------------------------------------------- ceiling

def test_ceiling_never_borrows_another_season(db: Path):
    """REGRESSION — the defect that motivated the rewrite.

    The sample history is 308/314 peak-ski nights. v1 fell back to a whole-history
    p90 for early-winter nights, inheriting a Christmas-week ceiling and producing a
    median +22.4% recommendation on the weakest nights of the year. Thin seasonal
    history must fall back to the SEASONAL ANCHOR, never across seasons.
    """
    policy = load_policy()
    with connect(db) as conn:
        feats = build_features_for_property(
            conn, "aspen_glow", date(2026, 12, 1), date(2026, 12, 1), policy=policy
        )
        c = compute_ceiling(conn, feats[0], policy)
        peak = build_features_for_property(
            conn, "aspen_glow", date(2027, 1, 15), date(2027, 1, 15), policy=policy
        )
    assert feats[0].season == "early_winter"
    assert "all_history" not in c.method, f"cross-season fallback fired: {c.method}"
    assert c.method.startswith("seasonal_anchor")
    assert c.confidence < 1.0
    # The early-winter ceiling must not simply be the peak-season number.
    assert c.ceiling_price <= c.anchor_price * 1.05


def test_ceiling_confidence_is_reported(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        feats = build_features_for_property(
            conn, "aspen_glow", date(2026, 12, 5), date(2026, 12, 5), policy=policy
        )
        c = compute_ceiling(conn, feats[0], policy)
    assert 0.0 < c.confidence <= 1.0
    assert c.anchor_price > 0


# ------------------------------------------------------- booking probability

def test_demand_model_has_an_interior_optimum():
    """A constant-elasticity model is degenerate: E[rev] = c * P**(1+beta) is monotone,
    so the optimizer always returns the floor or the ceiling. Linear demand must yield
    an interior optimum that moves the right way with elasticity."""
    inelastic = BookingProbability(0.55, 700, -0.65, "b", 20, False, None)
    elastic = BookingProbability(0.55, 700, -1.70, "b", 20, False, None)
    assert inelastic.unconstrained_optimum > 700   # inelastic -> price above reference
    assert elastic.unconstrained_optimum < 700     # elastic   -> price below reference
    # And it is a true maximum, not an endpoint.
    p = elastic.unconstrained_optimum
    assert elastic.expected_revpan(p) > elastic.expected_revpan(p * 0.6)
    assert elastic.expected_revpan(p) > elastic.expected_revpan(p * 1.6)


def test_probability_is_bounded():
    bp = BookingProbability(0.9, 100, -1.7, "b", 5, True, None)
    for price in (1, 50, 100, 5000, 100000):
        assert 0.0 <= bp.prob_at(price) <= 1.0


# ----------------------------------------------------------------- guardrails

def test_guardrails_cap_large_moves():
    policy = load_policy()
    v = apply_guardrails(proposed=2000, listed=500, anchor=600,
                         demand_strength=0.2, policy=policy)
    assert v.action == "clamped_increase"
    assert v.price < 2000
    assert v.price <= 500 * (1 + policy["guardrails"]["max_increase_pct"]) + 0.01


def test_guardrails_block_peak_nights():
    policy = load_policy()
    v = apply_guardrails(proposed=900, listed=800, anchor=800,
                         demand_strength=0.95, policy=policy)
    assert v.blocked and v.action == "peak_blackout"


def test_guardrail_sanity_floor_catches_absurd_prices():
    policy = load_policy()
    v = apply_guardrails(proposed=10, listed=800, anchor=800,
                         demand_strength=0.2, policy=policy)
    assert v.blocked and v.action == "sanity_floor"


def test_autonomy_is_demoted_by_unhealthy_data(db: Path):
    """The operator chose auto-push AND scraper-first comps. Autonomy must be a
    computed function of data health, not a setting."""
    policy = load_policy()
    with connect(db) as conn:
        h = assess_data_health(conn, policy)
    assert h.failures, "sample data has no pacing history; gate should fail"
    assert h.granted_level == "suggest"
    assert not h.can_push


# -------------------------------------------------------------------- pacing

def test_pacing_snapshot_is_idempotent_and_accumulates(db: Path):
    with connect(db) as conn:
        r1 = take_snapshot(conn, as_of=date.today())
        r2 = take_snapshot(conn, as_of=date.today())
        assert r1["observations_total"] == r2["observations_total"]
        r3 = take_snapshot(conn, as_of=date.today() + timedelta(days=1))
        assert r3["snapshot_days_total"] == 2
        row = conn.execute(
            "SELECT days_out FROM pacing_snapshots ORDER BY as_of, stay_date LIMIT 1"
        ).fetchone()
    assert row is None or row["days_out"] >= 0


# -------------------------------------------------------------------- leakage

def test_orphan_gap_surfaces_min_stay_lever(db: Path):
    """Price is the second lever on an orphan gap; min-stay is the first."""
    policy = load_policy()
    with connect(db) as conn:
        feats = build_features_for_property(
            conn, "cabin_ridge", date(2026, 12, 5), date(2026, 12, 5), policy=policy
        )
        feat = feats[0]
        assert feat.is_orphan_gap
        c = compute_ceiling(conn, feat, policy)
        findings = scan_leakage(feat, c, 700.0, policy)
    gap = [f for f in findings if f.kind == "orphan_gap"]
    assert gap and gap[0].min_stay_action == feat.gap_size


# ------------------------------------------------------------------ compose

def test_recommendations_respect_bounds_and_explain_themselves(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        recs, health = generate_recommendations(
            conn, date(2026, 12, 1), date(2026, 12, 14),
            property_ids=["aspen_glow"], policy=policy,
        )
    assert recs
    for rec in recs:
        assert 1 <= len(rec.reasons) <= 3
        assert rec.floor_price <= rec.recommended_price
        assert rec.expected_book_prob is not None, "RevPAN requires a booking probability"
        assert rec.expected_revpan is not None
        assert rec.rule_version and rec.inputs_hash
        assert rec.autonomy_level in ("watch", "suggest", "handle", "escalate")


def test_shoulder_nights_are_not_priced_off_peak_history(db: Path):
    """End-to-end regression for the audit's headline finding. On this sample the v1
    engine produced a median +22.4% (max +43.6%) on early-December nights."""
    policy = load_policy()
    with connect(db) as conn:
        recs, _ = generate_recommendations(
            conn, date(2026, 12, 1), date(2026, 12, 14), policy=policy,
        )
    deltas = [
        (r.recommended_price - r.listed_price_at_run) / r.listed_price_at_run
        for r in recs if r.listed_price_at_run
    ]
    assert deltas
    median = sorted(deltas)[len(deltas) // 2]
    assert median < 0.05, f"median move {median:+.1%} on shoulder nights"
    assert max(deltas) <= policy["guardrails"]["max_increase_pct"] + 0.001


def test_past_dates_are_refused_by_default(db: Path):
    policy = load_policy()
    with connect(db) as conn:
        recs, _ = generate_recommendations(
            conn, date(2025, 12, 20), date(2025, 12, 31), policy=policy,
        )
        assert recs == []
        past, _ = generate_recommendations(
            conn, date(2025, 12, 20), date(2025, 12, 31), policy=policy,
            allow_past=True, persist=False,
        )
    assert past, "backtesting must still be possible via allow_past"


def test_recommendations_are_deduplicated_per_run(db: Path):
    """REGRESSION: v1's UNIQUE included created_at at second resolution and so
    deduplicated nothing; repeated runs appended duplicate rows forever."""
    policy = load_policy()
    with connect(db) as conn:
        for _ in range(3):
            generate_recommendations(
                conn, date(2026, 12, 1), date(2026, 12, 7),
                property_ids=["aspen_glow"], policy=policy, run_id="fixed-run",
            )
        dupes = conn.execute(
            "SELECT COUNT(*) c FROM (SELECT run_id, property_id, stay_date "
            "FROM price_recommendations GROUP BY 1,2,3 HAVING COUNT(*) > 1)"
        ).fetchone()["c"]
    assert dupes == 0


# ------------------------------------------------------------------- explain

def test_reasons_rank_by_dollar_contribution():
    """v1 ranked by hardcoded weights, so boilerplate outranked whatever actually
    moved the price."""
    reasons = [
        Reason("base_compose", "boilerplate", contribution=0.0),
        Reason("season", "small", contribution=5.0),
        Reason("ceiling_gap", "the real driver", contribution=-120.0),
    ]
    top = select_top_reasons(reasons, max_n=2)
    assert top[0].code == "ceiling_gap"


def test_guardrail_reasons_are_never_ranked_out():
    reasons = [
        Reason("guardrail", "clamped", contribution=1.0, always_show=True),
        Reason("season", "big", contribution=500.0),
        Reason("dow", "bigger", contribution=900.0),
    ]
    top = select_top_reasons(reasons, max_n=2)
    assert any(r.code == "guardrail" for r in top)


# ---------------------------------------------------------------------- eval

def test_revpan_report(db: Path):
    with connect(db) as conn:
        generate_recommendations(conn, date(2026, 12, 1), date(2026, 12, 7),
                                 property_ids=["fraser_view"])
        record_outcomes_from_inventory(conn, date(2025, 12, 15), date(2026, 3, 31))
        report = compute_revpan(conn, date(2025, 12, 15), date(2026, 3, 31), "fraser_view")
    assert report.booked_nights > 0
    assert report.revpan > 0
    assert "RevPAN" in format_report(report)


def test_lift_metric_requires_an_applied_price(db: Path):
    """REGRESSION: v1's `potential_lift_vs_listed` summed max(0, rec - listed) over
    every recommendation, assuming both 100% acceptance and 100% conversion at the
    higher price. It could never be negative. Nothing has been pushed here, so there
    is no measurable effect to report."""
    with connect(db) as conn:
        generate_recommendations(conn, date(2026, 12, 1), date(2026, 12, 7),
                                 property_ids=["fraser_view"])
        record_outcomes_from_inventory(conn, date(2026, 12, 1), date(2026, 12, 7))
        report = compute_revpan(conn, date(2026, 12, 1), date(2026, 12, 7), "fraser_view")
    assert report.applied_nights == 0
    assert report.expected_revpan_delta is None
    assert "n/a" in format_report(report)
