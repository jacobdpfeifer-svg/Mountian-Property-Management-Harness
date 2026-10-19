"""Calendar persistence: four states, and a failure does not erase a good row."""

from __future__ import annotations

from src.db import connect, init_db
from src.scrape.calendar_store import (
    CALENDAR_UNAVAILABLE,
    FETCH_FAILED,
    QUOTED_OK,
    calendar_from_provider,
    classify_scrape_error,
)


def test_failure_does_not_overwrite_a_quoted_day(tmp_path):
    db = tmp_path / "cal.db"
    init_db(db)
    conn = connect(db)
    conn.execute("INSERT INTO comps (comp_id, name) VALUES ('c1', 'Peer')")
    calendar_from_provider(
        conn, "c1",
        {"2026-12-20": {"available": True, "min_nights": 3}},
        source="fixture", fetched_at="2026-10-19T00:00:00Z",
    )
    calendar_from_provider(
        conn, "c1", None, source="fixture", fetched_at="2026-10-19T01:00:00Z",
        error="timeout talking to host",
    )
    # The failed fetch is recorded, and the earlier good night is still quoted_ok.
    good = conn.execute(
        "SELECT source_status, min_nights FROM comp_calendar WHERE stay_date = '2026-12-20'"
    ).fetchone()
    assert good["source_status"] == QUOTED_OK
    assert good["min_nights"] == 3
    failed = conn.execute(
        "SELECT source_status, restrictions FROM comp_calendar WHERE source_status = ?",
        (FETCH_FAILED,),
    ).fetchone()
    assert failed["restrictions"] == "timeout"
    conn.execute("INSERT INTO comps (comp_id, name) VALUES ('c2', 'Other')")
    calendar_from_provider(
        conn, "c2",
        {"2026-12-21": {"available": False, "min_nights": 2}},
        source="fixture", fetched_at="2026-10-19T00:00:00Z",
    )
    blocked = conn.execute(
        "SELECT source_status FROM comp_calendar WHERE comp_id = 'c2'"
    ).fetchone()
    assert blocked["source_status"] == CALENDAR_UNAVAILABLE
    # Same stamp again does not duplicate.
    calendar_from_provider(
        conn, "c2",
        {"2026-12-21": {"available": False, "min_nights": 2}},
        source="fixture", fetched_at="2026-10-19T00:00:00Z",
    )
    n = conn.execute("SELECT COUNT(*) FROM comp_calendar WHERE comp_id = 'c2'").fetchone()[0]
    assert n == 1
    assert classify_scrape_error("HTTP 403 forbidden") == "blocked"
