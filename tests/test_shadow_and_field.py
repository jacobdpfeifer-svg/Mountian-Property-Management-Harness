from __future__ import annotations

from datetime import date

from src.eval.field_test import arm_for_checkin, power_table
from src.pricing.pickup_shadow import shrunk_pickup_residual


def test_one_booking_cannot_move_the_residual_without_bound():
    out = shrunk_pickup_residual(1.0, 0.2, n_history=1, max_one_booking=0.15)
    assert abs(out["residual"]) <= 0.15
    assert shrunk_pickup_residual(None, 0.2, n_history=10)["quality"] == "unavailable"


def test_checkin_week_assigns_the_whole_stay_and_power_is_low_for_a_small_effect():
    assert arm_for_checkin(date(2026, 11, 1)) == "control"
    assert arm_for_checkin(date(2026, 11, 3)) == "control"
    assert arm_for_checkin(date(2026, 11, 8)) == "treatment"
    assert arm_for_checkin(date(2026, 10, 1)) == "unavailable"
    table = {row["effect"]: row["power"] for row in power_table()}
    assert table[0.02] < 0.2
    assert table[0.33] > table[0.02]
