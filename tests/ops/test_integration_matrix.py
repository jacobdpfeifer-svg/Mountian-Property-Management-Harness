"""Audit regressions at the ops/pricing and scope seams."""

from datetime import date

from src.ops import OpsProfile
from src.ops.profiles import portfolio_property_ids
from src.ops.sources import PropertyResolver
from src.ops.turns import build_turn
from src.compliance import deadline_for


def test_turn_slack_uses_denver_dst_transition():
    profile = OpsProfile(
        property_id="test", version="v", checkout_time="10:00", checkin_time="16:00",
        base_clean_minutes=0, inspection_minutes=0, laundry_mode="offsite",
        laundry_minutes=0, hot_tub_reset_minutes=0, snow_clearance_required=False,
        snow_clearance_minutes=0, access_zone="test", travel_minutes=0, crew_size=1,
        labor_rate_per_hour=0, fixed_cost_per_turn=0, laundry_cost_per_turn=0,
        hot_tub_cost_per_turn=0, snow_cost_per_visit=0,
    )
    fall = build_turn(profile, service_date=date(2026, 10, 31), departing="a",
                      arriving="b", gap_nights=1)
    spring = build_turn(profile, service_date=date(2026, 3, 7), departing="a",
                        arriving="b", gap_nights=1)
    assert fall.slack_minutes == 1860
    assert spring.slack_minutes == 1740


def test_property_resolver_does_not_admit_undeclared_database_home(ops_db):
    from src.db import connect
    with connect(ops_db) as conn:
        conn.execute("""INSERT INTO properties(
            property_id, name, bedrooms, bathrooms, base_ceiling_rate,
            min_floor_rate, max_ceiling_rate
        ) VALUES ('creekside_haven', 'Creekside', 1, 1, 100, 50, 500)""")
        conn.commit()
        resolver = PropertyResolver(conn)
    assert "creekside_haven" not in portfolio_property_ids()
    assert resolver.resolve("creekside_haven") is None
    assert resolver.resolve("listing-c9") == "cloud_9"


def test_february_29_annual_deadline_is_february_28():
    cred = {"issued_at": "2024-02-29", "expires_at": None}
    assert deadline_for(cred, {"kind": "annual_from_issue"}).isoformat() == "2025-02-28"
