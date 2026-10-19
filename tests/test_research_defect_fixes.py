from __future__ import annotations

from src.config import load_events, load_resort_config


def test_2027_peak_calendar_windows_are_present():
    from datetime import date
    events = load_events(today=date(2026, 10, 19))
    by_start = {(event["event_name"], event["start"]): event for event in events}
    assert by_start[("MLK weekend", "2027-01-15")]["end"] == "2027-01-18"
    assert by_start[("Presidents Day weekend", "2027-02-12")]["end"] == "2027-02-15"
    assert by_start[("Christmas / New Year holiday peak", "2026-12-20")]["end"] == "2027-01-02"
    assert by_start[("Thanksgiving", "2026-11-25")]["end"] == "2026-11-29"
    # The next two seasons after 2026-10-19 are January 2028 and 2029.
    assert ("MLK weekend", "2028-01-14") in by_start
    assert ("MLK weekend", "2029-01-12") in by_start


def test_ikon_blackouts_are_product_specific():
    from datetime import date
    blackouts = load_resort_config()["ikon_blackouts"]
    assert {row["pass_product"] for row in blackouts} >= {"Ikon Session Pass", "Ikon Base Pass"}
    for row in blackouts:
        assert row["source_url"].startswith("http")
        assert row["verified_on"]
        age = (date(2026, 10, 19) - date.fromisoformat(row["verified_on"])).days
        assert age <= 400


def test_school_breaks_without_verification_do_not_count():
    from datetime import date
    from src.signals.calendars import load_school_breaks, verified_school_breaks
    rows = load_school_breaks()
    assert rows
    assert verified_school_breaks(rows, season="2026-27", as_of=date(2026, 10, 19)) == []
    verified = [{
        "season": "2026-27", "status": "VERIFIED", "source_url": "https://example.gov/cal",
        "verified_on": "2026-10-01", "district": "Example",
    }]
    assert len(verified_school_breaks(verified, season="2026-27", as_of=date(2026, 10, 19))) == 1
    stale = [{**verified[0], "verified_on": "2020-01-01"}]
    assert verified_school_breaks(stale, season="2026-27", as_of=date(2026, 10, 19)) == []


def test_snow_price_prior_is_neutral_until_calibrated():
    from src.signals.features.sqi import load_conditions, price_multiplier

    conditions = load_conditions()
    assert price_multiplier(0.62, conditions) == 1.0
    assert price_multiplier(0.50, conditions) == 1.0
    assert price_multiplier(1.20, conditions) == 1.0
    assert price_multiplier(1.30, conditions) == 1.0
