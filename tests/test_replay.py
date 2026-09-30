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
    exclusion_record,
    label_for_decision,
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
        rows.append(_row(
            stay_date=(date(2026, 10, 1) + timedelta(days=i)).isoformat(),
            resolved=True, expected_book_prob=0.5, booked_by_censor=booked,
            outcome_label=booked,
        ))
    out = score_calibration(rows)
    assert out["measurable"] is True
    assert out["eligible"] == 40
    assert out["distinct_nights"] == 40
    assert out["positive_events"] == 20
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
    assert "cancel_hazard" in out
    assert out["cancel_hazard"]["engine_revpan"] < out["bookings_unchanged"]["engine_revpan"]


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
    html = paths["html"].read_text()
    assert "Label definition:" in html
    assert "booked=true iff" in html


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


def test_replay_label_contract_and_effective_n_fixture():
    """A booking panel must distinguish four decision/outcome states."""
    censor = date(2026, 9, 29)
    assert label_for_decision(date(2026, 9, 20), date(2026, 9, 25),
                              "2026-09-19T12:00:00Z", censor) is None
    assert label_for_decision(date(2026, 9, 20), date(2026, 9, 25),
                              "2026-09-22T12:00:00Z", censor) is True
    assert label_for_decision(date(2026, 9, 20), date(2026, 9, 25), None, censor) is False
    assert label_for_decision(date(2026, 9, 20), date(2026, 10, 5),
                              None, censor) is None

    rows = [
        _row(as_of="2026-09-20", stay_date="2026-09-25", booked_by_censor=True,
             outcome_label=True),
        _row(as_of="2026-09-21", stay_date="2026-09-25", booked_by_censor=True,
             outcome_label=True),
    ] + [
        _row(as_of="2026-09-20", stay_date=f"2026-10-{i:02d}", booked_by_censor=False,
             outcome_label=False)
        for i in range(1, 20)
    ]
    scored = score_calibration(rows)
    assert scored["eligible"] == 21
    assert scored["deduplicated"]["eligible"] == 20
    assert scored["effective_n_warning"] is True


def test_replay_materializes_exclusion_ledger():
    row = exclusion_record(
        date(2026, 9, 20), "p", date(2026, 9, 25), "booked", "already_booked_at_decision",
        "2026-09-19T12:00:00Z",
    )
    assert row == {
        "as_of": "2026-09-20",
        "property_id": "p",
        "stay_date": "2026-09-25",
        "status": "booked",
        "reason": "already_booked_at_decision",
        "booked_at": "2026-09-19T12:00:00Z",
    }


def test_booking_events_and_repair_ignore_inquiries_and_owner_stays(leak_db: Path):
    """Only a confirmed guest sale is a booking event.

    Regression: sync wrote inquiries and owner stays into nightly_inventory as booked
    nights with a booked_at stamp, and the replay's inventory fallback turned those
    stamps into positive labels. The repair must restore the history as well.
    """
    from src.eval.replay import _booking_events
    from src.inventory.repair import repair_booking_contamination

    with connect(leak_db) as conn:
        rows = [
            ("inq", "inquiry", "airbnb2", "2026-09-10", "2026-09-12", "2026-09-01T10:00:00Z"),
            ("own", "confirmed", "owner", "2026-09-12", "2026-09-13", "2026-09-02T10:00:00Z"),
            ("real", "confirmed", "airbnb2", "2026-09-13", "2026-09-14", "2026-09-05T10:00:00Z"),
        ]
        for rid, status, source, ci, co, stamp in rows:
            conn.execute(
                "INSERT INTO reservations (reservation_id, property_id, check_in, check_out, "
                "status, source, confirmed_at, nightly_rate) VALUES (?, 'test_haus', ?, ?, ?, ?, ?, 900)",
                (rid, ci, co, status, source, stamp),
            )
        for night, rid, stamp in [
            ("2026-09-10", "inq", "2026-09-01T10:00:00Z"),
            ("2026-09-11", "inq", "2026-09-01T10:00:00Z"),
            ("2026-09-12", "own", "2026-09-02T10:00:00Z"),
            ("2026-09-13", "real", "2026-09-05T10:00:00Z"),
        ]:
            conn.execute(
                "INSERT INTO nightly_inventory (property_id, stay_date, booked_price, status, "
                "day_of_week, reservation_id, booked_at) VALUES ('test_haus', ?, 1233, 'booked', 0, ?, ?)",
                (night, rid, stamp),
            )
            conn.execute(
                "INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status) "
                "VALUES ('2026-09-03', 'test_haus', ?, 7, 'booked')",
                (night,),
            )
        conn.commit()

        events = _booking_events(conn, ["test_haus"])
        assert set(events) == {("test_haus", "2026-09-13")}

        report = repair_booking_contamination(conn, apply=True)
        assert report.by_action["non_sale_to_available"] == 2
        assert report.by_action["owner_stay_to_blocked"] == 1
        inv = dict(conn.execute(
            "SELECT stay_date, status FROM nightly_inventory WHERE property_id='test_haus'"
        ).fetchall())
        pace = dict(conn.execute(
            "SELECT stay_date, status FROM pacing_snapshots WHERE as_of='2026-09-03'"
        ).fetchall())
        logged = conn.execute("SELECT COUNT(*) FROM data_repairs").fetchone()[0]
        again = repair_booking_contamination(conn, apply=False)
    assert inv == {"2026-09-10": "available", "2026-09-11": "available",
                   "2026-09-12": "blocked", "2026-09-13": "booked"}
    # The real sale was confirmed 09-05, so its 09-03 "booked" snapshot is untouched
    # only because it was not inquiry-linked; the inquiry nights are restored.
    assert pace == {"2026-09-10": "available", "2026-09-11": "available",
                    "2026-09-12": "blocked", "2026-09-13": "booked"}
    assert logged > 0
    assert again.inventory_rows == again.pacing_rows == again.reservations_rows == 0


def test_repair_fixes_pacing_after_sync_clears_the_inventory_link(leak_db: Path):
    """A refresh fixes the live calendar and drops the bad reservation link.

    Pacing snapshots are not rewritten by sync. The repair has to find those
    nights from the reservation records, including a night sync already
    re-pointed at the real sale.
    """
    from src.inventory.repair import repair_booking_contamination

    with connect(leak_db) as conn:
        conn.execute(
            "INSERT INTO reservations (reservation_id, property_id, check_in, check_out, "
            "status, source, confirmed_at, nightly_rate) VALUES "
            "('inq', 'test_haus', '2026-09-10', '2026-09-15', 'inquiry', 'airbnb2', "
            "'2026-09-01T10:00:00Z', 400),"
            "('real', 'test_haus', '2026-09-14', '2026-09-15', 'confirmed', 'airbnb2', "
            "'2026-09-06T10:00:00Z', 900)"
        )
        conn.execute(
            "INSERT INTO nightly_inventory (property_id, stay_date, listed_price, status, "
            "day_of_week, channel) VALUES ('test_haus', '2026-09-10', 500, 'available', 0, 'guesty')"
        )
        conn.execute(
            "INSERT INTO nightly_inventory (property_id, stay_date, booked_price, status, "
            "day_of_week, reservation_id, booked_at, channel) VALUES "
            "('test_haus', '2026-09-14', 900, 'booked', 0, 'real', '2026-09-06T10:00:00Z', 'airbnb2')"
        )
        for night in ("2026-09-10", "2026-09-14"):
            conn.execute(
                "INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status) "
                "VALUES ('2026-09-03', 'test_haus', ?, 7, 'booked')",
                (night,),
            )
        conn.execute(
            "INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status) "
            "VALUES ('2026-09-07', 'test_haus', '2026-09-14', 7, 'booked')"
        )
        conn.commit()

        report = repair_booking_contamination(conn, apply=True)
        pace = {
            (r["as_of"], r["stay_date"]): r["status"]
            for r in conn.execute(
                "SELECT as_of, stay_date, status FROM pacing_snapshots WHERE property_id='test_haus'"
            )
        }
        real_night = conn.execute(
            "SELECT status, reservation_id, booked_price FROM nightly_inventory "
            "WHERE stay_date='2026-09-14'"
        ).fetchone()
        inquiry_stamp = conn.execute(
            "SELECT confirmed_at FROM reservations WHERE reservation_id='inq'"
        ).fetchone()["confirmed_at"]
        again = repair_booking_contamination(conn, apply=False)

    assert report.inventory_rows == 0
    assert report.by_action["pacing_booked_to_available"] == 2
    assert report.reservations_rows == 1
    assert pace == {
        ("2026-09-03", "2026-09-10"): "available",
        ("2026-09-03", "2026-09-14"): "available",
        ("2026-09-07", "2026-09-14"): "booked",
    }
    assert real_night["status"] == "booked"
    assert real_night["reservation_id"] == "real"
    assert real_night["booked_price"] == 900
    assert inquiry_stamp is None
    assert again.inventory_rows == again.pacing_rows == again.reservations_rows == 0


def test_repair_leaves_cancelled_sale_history_booked(leak_db: Path):
    """A stay that was confirmed and later cancelled is not an inquiry.

    Snapshots taken while it was confirmed stay booked. Only the live row is
    released when it is still linked to that cancelled reservation.
    """
    from src.inventory.repair import repair_booking_contamination

    with connect(leak_db) as conn:
        conn.execute(
            "INSERT INTO reservations (reservation_id, property_id, check_in, check_out, "
            "status, source, confirmed_at, nightly_rate) VALUES "
            "('was-sold', 'test_haus', '2026-09-18', '2026-09-19', 'canceled', 'airbnb2', "
            "'2026-09-01T10:00:00Z', 800)"
        )
        conn.execute(
            "INSERT INTO nightly_inventory (property_id, stay_date, booked_price, status, "
            "day_of_week, reservation_id, booked_at, channel) VALUES "
            "('test_haus', '2026-09-18', 800, 'booked', 0, 'was-sold', '2026-09-01T10:00:00Z', 'airbnb2')"
        )
        conn.execute(
            "INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out, status) "
            "VALUES ('2026-09-05', 'test_haus', '2026-09-18', 13, 'booked')"
        )
        conn.commit()
        report = repair_booking_contamination(conn, apply=True)
        pace = conn.execute(
            "SELECT status FROM pacing_snapshots WHERE stay_date='2026-09-18'"
        ).fetchone()["status"]
        inv = conn.execute(
            "SELECT status, reservation_id FROM nightly_inventory WHERE stay_date='2026-09-18'"
        ).fetchone()
        stamp = conn.execute(
            "SELECT confirmed_at FROM reservations WHERE reservation_id='was-sold'"
        ).fetchone()["confirmed_at"]
    assert report.pacing_rows == 0
    assert pace == "booked"
    assert stamp == "2026-09-01T10:00:00Z"
    # The live calendar must not stay sold after the cancellation.
    assert inv["status"] == "available"
    assert inv["reservation_id"] is None
