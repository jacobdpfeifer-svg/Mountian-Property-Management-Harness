from __future__ import annotations

from src.config import load_events, load_resort_config


def test_2027_peak_calendar_windows_are_present():
    events = {event["event_name"]: event for event in load_events() if event["start"].startswith("2027")}
    assert events["MLK weekend"]["start"] == "2027-01-15"
    assert events["Presidents Day weekend"]["start"] == "2027-02-12"
    assert events["Spring Break peak"]["start"] == "2027-03-06"


def test_ikon_blackouts_are_product_specific():
    blackouts = load_resort_config()["ikon_blackouts"]
    assert blackouts
    assert {row["pass_product"] for row in blackouts} == {"Ikon Session Pass"}


def test_snow_price_prior_is_neutral_until_calibrated():
    from src.signals.features.sqi import load_conditions, price_multiplier

    conditions = load_conditions()
    assert price_multiplier(0.62, conditions) == 1.0
    assert price_multiplier(0.50, conditions) == 1.0
