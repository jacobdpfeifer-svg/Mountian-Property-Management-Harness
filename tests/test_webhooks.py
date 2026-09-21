import sqlite3
from datetime import date

from src.db import init_db
from src.pms.webhooks import record_delivery


def test_guesty_webhook_is_deduplicated_and_bounded(tmp_path):
    path = tmp_path / "webhook.db"
    init_db(path)
    with sqlite3.connect(path) as conn:
        first = record_delivery(
            conn,
            event_id="evt-1",
            event_type="calendar.updated.v2",
            payload={"listingId": "listing-1", "startDate": "2026-12-20", "endDate": "2026-12-27"},
        )
        second = record_delivery(
            conn,
            event_id="evt-1",
            event_type="calendar.updated.v2",
            payload={"listingId": "listing-1", "startDate": "2026-12-20", "endDate": "2026-12-27"},
        )
        assert first.duplicate is False
        assert second.duplicate is True
        assert first.listing_id == "listing-1"
        assert first.start == date(2026, 12, 20)
        assert conn.execute("SELECT COUNT(*) FROM pms_webhook_events").fetchone()[0] == 1
