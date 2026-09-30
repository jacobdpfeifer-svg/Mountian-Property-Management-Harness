"""Point-in-time date and health behavior."""

from datetime import date

from src.utils import parse_date


def test_utc_evening_booking_stays_on_the_denver_day():
    # 02:00 UTC on 2 Sep is 20:00 the previous evening in Mountain Daylight Time.
    assert parse_date("2026-09-02T02:00:00Z") == date(2026, 9, 1)
    assert parse_date("2026-09-02T18:00:00Z") == date(2026, 9, 2)
    assert parse_date("2026-09-02") == date(2026, 9, 2)
