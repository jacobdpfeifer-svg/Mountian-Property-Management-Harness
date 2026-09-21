"""Engine tests.

The v1 suite passed 6/6 while the engine recommended a median +22% price increase on
the weakest demand nights of the year. It contained tautologies (`assert n >= 0`,
`assert sample_size >= 0`) and one assertion that actively enshrined the ceiling-cap
defect as intended behaviour. Every test below either pins a real invariant or is a
regression test for a specific defect found in the audit.
"""

from __future__ import annotations

import copy
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.bookprob import BookingProbability
from src.ceiling import compute_ceiling
from src.cli.main import main
from src.compose import generate_recommendations, recommend_night
from src.config import load_policy
from src.db import connect, init_db
from src.eval import compute_revpan, format_report, record_outcomes_from_inventory
from src.explain import Reason, select_top_reasons
from src.features import build_features_for_property
from src.guardrails import (
    DataHealth,
    apply_guardrails,
    assess_data_health,
    limit_run_scope,
    record_health,
)
from src.ingest import CsvIngestAdapter, ICalIngestAdapter
from src.leakage import scan_leakage
from src.pacing import take_snapshot
from src.pms import DryRunAdapter, PMSAdapter, PushResult, push_recommendations

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
    median +22.4% recommendation on the weakest nights of the year. Multi-year
    history does not change this: thin same-season history must fall back to the
    SEASONAL ANCHOR, never across seasons.
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


def test_cross_season_fallback_cannot_reach_handle(db: Path):
    """allow_cross_season_fallback uses p{pct}_all_history_UNSAFE at confidence 0.25.

    That is below autonomy.require_ceiling_confidence, so per-night demotion in
    recommend_night must drop handle → suggest. Do not assume the label alone
    blocks auto-push — the confidence gate in AUTONOMY.md is the mechanism.
    """
    policy = copy.deepcopy(load_policy())
    policy["ceiling"]["allow_cross_season_fallback"] = True
    policy["autonomy"]["max_level"] = "handle"
    min_conf = float(policy["autonomy"]["require_ceiling_confidence"])
    with connect(db) as conn:
        feats = build_features_for_property(
            conn, "aspen_glow", date(2026, 12, 1), date(2026, 12, 1), policy=policy
        )
        ceiling = compute_ceiling(conn, feats[0], policy)
        health = DataHealth(
            granted_level="handle", pms_age_hours=0.0, comp_age_hours=0.0,
            comp_coverage=1.0, pacing_days=30, failures=[],
        )
        rec = recommend_night(conn, feats[0], policy=policy, health=health)
    assert rec is not None
    assert "all_history_UNSAFE" in ceiling.method, ceiling.method
    assert ceiling.confidence == pytest.approx(0.25)
    assert rec.ceiling_confidence < min_conf
    assert rec.ceiling_confidence == pytest.approx(ceiling.confidence)
    assert rec.autonomy_level != "handle"
    assert rec.autonomy_level == "suggest"
    assert rec.status != "blocked"


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


def test_guardrail_sanity_ceiling_catches_corrupted_listed_price():
    """REGRESSION: the move-cap band is computed relative to `listed`, which is
    untrusted PMS input — it can itself be corrupted (bad sync, unit mismatch,
    fat-fingered entry). Before this check existed, a sane Stage C proposal near
    a $690 anchor, paired with a corrupted $50,000 `listed` price, clamped OUT to
    ~$49,750 ("clamped_decrease" — within 15% of the bad number), i.e. guardrails
    actively made a corrupted input worse instead of catching it."""
    policy = load_policy()
    v = apply_guardrails(proposed=690, listed=50_000, anchor=690,
                         demand_strength=0.2, policy=policy)
    assert v.blocked and v.action == "sanity_ceiling", v
    assert v.price <= 690 * float(policy["guardrails"]["sanity_max_ratio_to_anchor"]) + 0.01
    assert v.price < 10_000, f"corrupted-listed price leaked through: {v}"


def test_guardrail_blackout_wins_label_but_sanity_still_caps_price():
    """When a night is both a peak-demand blackout AND the price is sanity-implausible,
    'peak_blackout' stays the reported reason (AUTONOMY.md: the highest-demand nights
    always escalate) but the sanity ceiling must still cap the number a human reviews —
    the two checks are not mutually exclusive on the safety side, only on the label."""
    policy = load_policy()
    v = apply_guardrails(proposed=690, listed=50_000, anchor=690, demand_strength=0.95, policy=policy)
    assert v.blocked and v.action == "peak_blackout"
    assert v.price <= 690 * float(policy["guardrails"]["sanity_max_ratio_to_anchor"]) + 0.01
    assert "seasonal anchor" in (v.detail or "")


def test_guardrail_sanity_ceiling_does_not_fire_on_legitimate_peak_pricing():
    """Control: a genuinely high but anchor-consistent price must NOT be treated
    as corrupted. The seasonal anchor already reflects the property's own history,
    so a proposal a little above the current listing at the same order of
    magnitude as the anchor must pass through untouched."""
    policy = load_policy()
    v = apply_guardrails(proposed=750, listed=700, anchor=690,
                         demand_strength=0.2, policy=policy)
    assert v.action != "sanity_ceiling"
    assert not v.blocked


def test_limit_run_scope_withholds_largest_moves_first():
    """REGRESSION: this hard invariant (max_nights_changed_per_run /
    max_pct_of_open_nights_per_run, AUTONOMY.md) had zero direct test coverage —
    only exercised indirectly via the CLI push command. A run that wants to move
    more of the calendar than allowed must withhold the BIGGEST swings for human
    review, not an arbitrary subset, since the largest moves are the ones most
    likely to be a data fault rather than a real opportunity."""

    @dataclass
    class _Rec:
        listed_price_at_run: float | None
        recommended_price: float

    policy = copy.deepcopy(load_policy())
    policy["guardrails"]["max_nights_changed_per_run"] = 40
    policy["guardrails"]["max_pct_of_open_nights_per_run"] = 1.0
    # 5 recommendations with distinct move sizes; cap to 3 via open_nights * pct.
    recs = [
        _Rec(listed_price_at_run=500.0, recommended_price=505.0),   # $5 move
        _Rec(listed_price_at_run=500.0, recommended_price=550.0),   # $50 move (largest)
        _Rec(listed_price_at_run=500.0, recommended_price=520.0),   # $20 move
        _Rec(listed_price_at_run=500.0, recommended_price=510.0),   # $10 move
        _Rec(listed_price_at_run=500.0, recommended_price=530.0),   # $30 move
    ]
    policy["guardrails"]["max_pct_of_open_nights_per_run"] = 3 / 10  # 3 allowed of 10 open
    pushable, withheld = limit_run_scope(recs, open_nights=10, policy=policy)

    assert len(pushable) == 3
    assert len(withheld) == 2
    pushable_moves = sorted(abs(r.recommended_price - r.listed_price_at_run) for r in pushable)
    withheld_moves = sorted(abs(r.recommended_price - r.listed_price_at_run) for r in withheld)
    assert pushable_moves == [5.0, 10.0, 20.0]
    assert withheld_moves == [30.0, 50.0], "the two largest moves must be withheld, not pushed"


def test_limit_run_scope_ignores_sub_dollar_noise_and_missing_listed_price():
    @dataclass
    class _Rec:
        listed_price_at_run: float | None
        recommended_price: float

    policy = load_policy()
    recs = [
        _Rec(listed_price_at_run=500.0, recommended_price=500.5),  # < $1, not a "change"
        _Rec(listed_price_at_run=None, recommended_price=600.0),   # no listed price at all
        _Rec(listed_price_at_run=500.0, recommended_price=510.0),  # a real $10 change
    ]
    pushable, withheld = limit_run_scope(recs, open_nights=100, policy=policy)
    assert len(pushable) == 1
    assert pushable[0].recommended_price == 510.0
    assert withheld == []


def test_autonomy_is_demoted_by_unhealthy_data(db: Path):
    """The operator chose auto-push AND scraper-first comps. Autonomy must be a
    computed function of data health, not a setting."""
    policy = load_policy()
    with connect(db) as conn:
        h = assess_data_health(conn, policy)
    assert h.failures, "sample data has no pacing history; gate should fail"
    assert h.granted_level == "suggest"
    assert not h.can_push


def test_health_grace_is_asymmetric_and_fail_closed(db: Path):
    """A transient failure is tolerated only after a healthy baseline; recovery is immediate."""
    policy = copy.deepcopy(load_policy())
    with connect(db) as conn:
        baseline = DataHealth("handle", 0.0, 0.0, 1.0, 30, [])
        record_health(conn, "baseline", baseline)
        conn.commit()

        first_bad = assess_data_health(conn, policy)
        assert first_bad.granted_level == "handle"
        assert first_bad.grace_active
        record_health(conn, "first-bad", first_bad)
        conn.commit()

        second_bad = assess_data_health(conn, policy)
        assert second_bad.granted_level == "suggest"
        assert not second_bad.grace_active

        recovered = DataHealth("handle", 0.0, 0.0, 1.0, 30, [])
        record_health(conn, "recovered", recovered)
        conn.commit()
        assert assess_data_health(conn, policy).granted_level == "handle"


def test_health_demotes_on_pacing_gap(tmp_path: Path):
    """REGRESSION: a hole in the middle of the pacing window must demote autonomy
    even when the distinct-day COUNT already clears `pacing_min_snapshot_days`.

    14 snapshot days with a missing day in the middle is not the same evidence as
    14 consecutive days — the missing day is a hole in the pacing curve that
    src/pacing's own docstring calls "permanently unrecoverable". Counting distinct
    `as_of` values alone cannot see this; only `verify_snapshots` can.
    """
    from src.db import connect as _connect
    from src.db import init_db as _init_db

    policy = load_policy()
    db_path = tmp_path / "gap.db"
    _init_db(db_path, seed_markets=False)

    pid = "gap_house"
    today = date.today()
    span_days = 20  # > pacing_min_snapshot_days(14) even after one gap day
    start = today - timedelta(days=span_days - 1)
    gap_day = start + timedelta(days=10)

    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO properties (property_id, name, bedrooms, bathrooms, amenities,
                base_ceiling_rate, min_floor_rate, max_ceiling_rate, pms_listing_id, created_at)
            VALUES (?, ?, 5, 4.0, '[]', 900, 400, 1800, 'guesty-123', ?)
            """,
            (pid, pid, f"{start.isoformat()} 12:00:00"),
        )
        conn.execute(
            """
            INSERT INTO nightly_inventory (property_id, stay_date, listed_price, status, updated_at)
            VALUES (?, ?, 500, 'available', datetime('now'))
            """,
            (pid, (today + timedelta(days=30)).isoformat()),
        )
        conn.execute(
            "INSERT INTO comps (comp_id, name, active) VALUES (?, ?, 1)", ("c1", "Comp One")
        )
        conn.execute(
            "INSERT INTO comps (comp_id, name, active) VALUES (?, ?, 1)", ("c2", "Comp Two")
        )
        conn.execute(
            "INSERT INTO comps (comp_id, name, active) VALUES (?, ?, 1)", ("c3", "Comp Three")
        )
        for cid in ("c1", "c2", "c3"):
            conn.execute(
                "INSERT INTO comp_set_members (property_id, comp_id) VALUES (?, ?)", (pid, cid)
            )
            conn.execute(
                """
                INSERT INTO comp_snapshots (comp_id, as_of, stay_date, listed_price, scrape_status)
                VALUES (?, datetime('now'), ?, 480, 'ok')
                """,
                (cid, (today + timedelta(days=30)).isoformat()),
            )
        for i in range(span_days):
            as_of = start + timedelta(days=i)
            if as_of == gap_day:
                continue  # the deliberate hole
            conn.execute(
                """
                INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status, listed_price)
                VALUES (?, ?, ?, 30, 'available', 500)
                """,
                (as_of.isoformat(), pid, (today + timedelta(days=30)).isoformat()),
            )
        conn.commit()

        # Sanity: the day COUNT alone already clears the threshold.
        distinct_days = conn.execute(
            "SELECT COUNT(DISTINCT as_of) AS c FROM pacing_snapshots WHERE property_id = ?", (pid,)
        ).fetchone()["c"]
        assert distinct_days == span_days - 1 >= int(policy["data_health"]["pacing_min_snapshot_days"])

        health = assess_data_health(conn, policy, property_ids=[pid])

    assert not health.can_push, (
        f"pacing gap on {gap_day} must demote despite {distinct_days} distinct snapshot "
        f"days; failures={health.failures}"
    )
    assert any("gap" in f.lower() for f in health.failures), health.failures

    # Control: same setup with the gap filled must NOT fail on pacing at all.
    db_path2 = tmp_path / "nogap.db"
    _init_db(db_path2, seed_markets=False)
    with connect(db_path2) as conn:
        conn.execute(
            """
            INSERT INTO properties (property_id, name, bedrooms, bathrooms, amenities,
                base_ceiling_rate, min_floor_rate, max_ceiling_rate, pms_listing_id, created_at)
            VALUES (?, ?, 5, 4.0, '[]', 900, 400, 1800, 'guesty-123', ?)
            """,
            (pid, pid, f"{start.isoformat()} 12:00:00"),
        )
        conn.execute(
            """
            INSERT INTO nightly_inventory (property_id, stay_date, listed_price, status, updated_at)
            VALUES (?, ?, 500, 'available', datetime('now'))
            """,
            (pid, (today + timedelta(days=30)).isoformat()),
        )
        conn.execute(
            "INSERT INTO comps (comp_id, name, active) VALUES (?, ?, 1)", ("c1", "Comp One")
        )
        conn.execute(
            "INSERT INTO comps (comp_id, name, active) VALUES (?, ?, 1)", ("c2", "Comp Two")
        )
        conn.execute(
            "INSERT INTO comps (comp_id, name, active) VALUES (?, ?, 1)", ("c3", "Comp Three")
        )
        for cid in ("c1", "c2", "c3"):
            conn.execute(
                "INSERT INTO comp_set_members (property_id, comp_id) VALUES (?, ?)", (pid, cid)
            )
            conn.execute(
                """
                INSERT INTO comp_snapshots (comp_id, as_of, stay_date, listed_price, scrape_status)
                VALUES (?, datetime('now'), ?, 480, 'ok')
                """,
                (cid, (today + timedelta(days=30)).isoformat()),
            )
        for i in range(span_days):
            as_of = start + timedelta(days=i)
            conn.execute(
                """
                INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status, listed_price)
                VALUES (?, ?, ?, 30, 'available', 500)
                """,
                (as_of.isoformat(), pid, (today + timedelta(days=30)).isoformat()),
            )
        conn.commit()
        health_ok = assess_data_health(conn, policy, property_ids=[pid])

    assert not any("gap" in f.lower() for f in health_ok.failures), health_ok.failures
    assert health_ok.can_push, health_ok.failures


def test_assess_data_health_raise_is_fail_closed(db: Path, monkeypatch: pytest.MonkeyPatch):
    """REGRESSION: an uncaught health-check failure must not grant autonomy or push.

    The crash is the safe behaviour. Do not wrap assess_data_health in a broad
    try/except that defaults to a ladder level — that would fail open.
    """

    def boom(*_a, **_k):
        raise RuntimeError("simulated health failure")

    monkeypatch.setattr("src.compose.assess_data_health", boom)

    exit_code: object = 0
    try:
        main([
            "--db", str(db), "push",
            "--from", "2026-12-05", "--to", "2026-12-05",
            "--adapter", "dry_run", "--property", "aspen_glow",
        ])
    except SystemExit as se:
        exit_code = se.code
    except Exception:
        # Uncaught exception = non-zero process exit. That IS the fail-closed path.
        exit_code = 1

    assert exit_code not in (0, None)
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM data_health_runs").fetchone()["c"] == 0
        assert conn.execute("SELECT COUNT(*) c FROM rate_changes").fetchone()["c"] == 0


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


def test_corrupted_listed_price_does_not_reach_a_real_recommendation(db: Path):
    """Adversarial end-to-end trace (Stage D's job): a single corrupted PMS row —
    the kind a bad Guesty sync or a fat-fingered manual entry produces — must not
    survive the full ceiling -> compose -> guardrails chain as a five-figure
    recommendation. Before the sanity-ceiling guardrail existed, this exact
    scenario clamped OUT to ~$49,750 via 'clamped_decrease' (within 15% of the
    corrupted $50,000 listed price), i.e. the guardrail made the corruption
    worse instead of catching it."""
    policy = load_policy()
    with connect(db) as conn:
        conn.execute(
            "UPDATE nightly_inventory SET listed_price = 50000 "
            "WHERE property_id = 'aspen_glow' AND stay_date = '2026-12-05'"
        )
        conn.commit()
        recs, health = generate_recommendations(
            conn, date(2026, 12, 5), date(2026, 12, 5),
            property_ids=["aspen_glow"], policy=policy, persist=False,
        )
    assert len(recs) == 1
    rec = recs[0]
    assert rec.recommended_price < 5_000, (
        f"corrupted $50,000 listed price leaked through as ${rec.recommended_price:.0f} "
        f"(action={rec.guardrail_action})"
    )
    assert rec.guardrail_action == "sanity_ceiling"
    assert rec.status == "blocked"
    assert rec.autonomy_level == "escalate"


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


def test_connect_applies_schema_patches(tmp_path: Path):
    """REGRESSION: connect() must auto-migrate columns added after initial schema ship.

    Without this, comp_evidence crashes on existing DBs with
    `no such column: c.sleeps` because only init_db() used to call _ensure_columns.
    """
    path = tmp_path / "legacy.db"
    schema = (ROOT / "src" / "db" / "schema.sql").read_text(encoding="utf-8")
    # Simulate a pre-patch DB: create tables but strip the sleeps column patch.
    legacy_schema = schema.replace("    sleeps          INTEGER,\n", "")
    with sqlite3.connect(path) as raw:
        raw.executescript(legacy_schema)
        raw.commit()
    cols_before = {
        r[1]
        for r in sqlite3.connect(path).execute("PRAGMA table_info(comps)").fetchall()
    }
    assert "sleeps" not in cols_before

    with connect(path) as conn:
        cols_after = {r["name"] for r in conn.execute("PRAGMA table_info(comps)").fetchall()}
    assert "sleeps" in cols_after


def test_inputs_hash_is_not_null_and_legacy_rows_are_backfilled(tmp_path: Path):
    """Architecture requires inputs_hash on every recommendation; schema + migrate it."""
    fresh = tmp_path / "fresh.db"
    init_db(fresh)
    with connect(fresh) as conn:
        col = [
            r for r in conn.execute("PRAGMA table_info(price_recommendations)").fetchall()
            if r["name"] == "inputs_hash"
        ][0]
        assert col["notnull"] == 1
        rc_cols = {r["name"] for r in conn.execute("PRAGMA table_info(rate_changes)").fetchall()}
        assert {"rule_version", "model_version", "inputs_hash"} <= rc_cols

    path = tmp_path / "legacy_hash.db"
    schema = (ROOT / "src" / "db" / "schema.sql").read_text(encoding="utf-8")
    legacy = schema.replace("    inputs_hash         TEXT NOT NULL,\n", "    inputs_hash         TEXT,\n")
    with sqlite3.connect(path) as raw:
        raw.row_factory = sqlite3.Row
        raw.executescript(legacy)
        raw.execute(
            """INSERT INTO properties (property_id,name,bedrooms,bathrooms,amenities,
               base_ceiling_rate,min_floor_rate,max_ceiling_rate)
               VALUES ('p1','P',1,1,'[]',100,50,200)"""
        )
        raw.execute(
            """INSERT INTO price_recommendations (
                   run_id, property_id, stay_date, recommended_price, ceiling_price,
                   floor_price, autonomy_level, reasons, rule_version, model_version,
                   inputs_hash, status)
               VALUES ('r1','p1','2026-12-01',100,120,80,'suggest','[]','rv','mv',NULL,'suggested')"""
        )
        raw.commit()
    with connect(path) as conn:
        row = conn.execute("SELECT inputs_hash FROM price_recommendations").fetchone()
        assert row["inputs_hash"] == "legacy-missing"
        rc_cols = {r["name"] for r in conn.execute("PRAGMA table_info(rate_changes)").fetchall()}
        assert {"rule_version", "model_version", "inputs_hash"} <= rc_cols


class _FailingWriteAdapter(PMSAdapter):
    name = "timeout_channel"

    def __init__(self, live_price: float):
        self.live_price = live_price

    def fetch_calendar(self, property_id: str, start: date, end: date):
        return [{"date": start.isoformat(), "price": self.live_price}]

    def push_rate(self, property_id: str, stay_date: date, price: float,
                  min_stay: int | None = None) -> PushResult:
        return PushResult(property_id, stay_date, None, price, False, "failed", "Timeout")


def test_rate_changes_denormalize_provenance_and_reconcile_failed_writes(db: Path):
    """Push must store rule/model/hash on rate_changes even if the rec FK misses,
    and a failed write that actually landed must update inventory + the audit row."""
    policy = load_policy()
    with connect(db) as conn:
        recs, _ = generate_recommendations(
            conn, date(2026, 12, 5), date(2026, 12, 5),
            property_ids=["cabin_ridge"], policy=policy, persist=True, allow_past=True,
        )
        assert recs
        rec = recs[0]
        rec.autonomy_level = "handle"
        rec.status = "suggested"
        rec.run_id = "orphan-run-id"
        listed_before = conn.execute(
            "SELECT listed_price FROM nightly_inventory "
            "WHERE property_id=? AND stay_date=?",
            (rec.property_id, rec.stay_date.isoformat()),
        ).fetchone()["listed_price"]
        counts = push_recommendations(
            conn, [rec], _FailingWriteAdapter(rec.recommended_price), "handle",
            policy=policy,
        )
        assert counts["applied"] == 1
        assert counts["failed"] == 0
        row = conn.execute(
            "SELECT recommendation_id, rule_version, model_version, inputs_hash, "
            "result, error FROM rate_changes"
        ).fetchone()
        listed_after = conn.execute(
            "SELECT listed_price FROM nightly_inventory "
            "WHERE property_id=? AND stay_date=?",
            (rec.property_id, rec.stay_date.isoformat()),
        ).fetchone()["listed_price"]
    assert row["recommendation_id"] is None
    assert row["rule_version"] == rec.rule_version
    assert row["model_version"] == rec.model_version
    assert row["inputs_hash"] == rec.inputs_hash
    assert row["result"] == "applied"
    assert "reconciled" in (row["error"] or "")
    assert listed_after == rec.recommended_price
    assert listed_after != listed_before or listed_before == rec.recommended_price
