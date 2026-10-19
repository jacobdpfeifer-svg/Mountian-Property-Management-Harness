"""Per-day comp calendar. Failures do not erase an earlier good day."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


QUOTED_OK = "quoted_ok"
CALENDAR_UNAVAILABLE = "calendar_unavailable"
NOT_RETURNED = "not_returned"
FETCH_FAILED = "fetch_failed"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def persist_calendar_day(
    conn: sqlite3.Connection,
    *,
    comp_id: str,
    stay_date: str,
    source_status: str,
    source: str,
    fetched_at: str | None = None,
    available: int | None = None,
    min_nights: int | None = None,
    restrictions: str | None = None,
    payload_quality: str = "ok",
) -> str:
    """Insert one day. A fetch_failed row does not replace quoted_ok or calendar_unavailable.

    Re-running with the same fetched_at is a no-op (the unique key).
    """
    stamp = fetched_at or _now()
    if source_status == FETCH_FAILED:
        earlier = conn.execute(
            """
            SELECT source_status FROM comp_calendar
            WHERE comp_id = ? AND stay_date = ? AND source_status IN (?, ?)
            ORDER BY fetched_at DESC LIMIT 1
            """,
            (comp_id, stay_date, QUOTED_OK, CALENDAR_UNAVAILABLE),
        ).fetchone()
        if earlier is not None:
            return "kept_earlier"
    conn.execute(
        """
        INSERT INTO comp_calendar (
            comp_id, stay_date, fetched_at, available, min_nights, restrictions,
            source_status, payload_quality, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(comp_id, stay_date, fetched_at) DO NOTHING
        """,
        (comp_id, stay_date, stamp, available, min_nights, restrictions,
         source_status, payload_quality, source),
    )
    return "inserted"


def classify_scrape_error(message: str) -> str:
    """Group a stored error string. Unknown text stays 'other', not 'unavailable'."""
    text = (message or "").lower()
    if not text:
        return "empty"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "dns" in text or "could not resolve" in text:
        return "dns"
    if "429" in text or "too many" in text:
        return "rate_limited"
    if "403" in text or "401" in text or "forbidden" in text:
        return "blocked"
    if "parse" in text or "json" in text or "non_json" in text:
        return "parse"
    if "no listing" in text or "not found" in text or "404" in text:
        return "missing_listing"
    return "other"


def calendar_from_provider(
    conn: sqlite3.Connection,
    comp_id: str,
    days: dict[str, dict[str, Any]] | None,
    *,
    source: str,
    fetched_at: str | None = None,
    error: str | None = None,
) -> dict[str, int]:
    """Store every day a calendar call returned.

    `days` is iso date -> {available, min_nights, restrictions}. None with an
    error is one fetch_failed marker on no date: the caller passes the dates
    it asked for via `days` being empty and `error` set, and we do not invent
    an unavailable night.
    """
    stamp = fetched_at or _now()
    counts = {QUOTED_OK: 0, CALENDAR_UNAVAILABLE: 0, NOT_RETURNED: 0, FETCH_FAILED: 0}
    if error or days is None:
        # No night is marked unavailable because the fetch itself failed.
        persist_calendar_day(
            conn, comp_id=comp_id, stay_date="", source_status=FETCH_FAILED,
            source=source, fetched_at=stamp, payload_quality="unavailable",
            restrictions=classify_scrape_error(error or "fetch_failed"),
        )
        counts[FETCH_FAILED] += 1
        return counts
    for iso, info in days.items():
        info = info or {}
        if info.get("returned") is False:
            status = NOT_RETURNED
            available = None
        elif info.get("available") in (0, False):
            status = CALENDAR_UNAVAILABLE
            available = 0
        else:
            status = QUOTED_OK
            available = 1 if info.get("available") in (1, True, None) else 0
            if info.get("available") is None and info.get("min_nights") is None:
                status = NOT_RETURNED
                available = None
        result = persist_calendar_day(
            conn,
            comp_id=comp_id,
            stay_date=iso,
            source_status=status,
            source=source,
            fetched_at=stamp,
            available=available,
            min_nights=info.get("min_nights"),
            restrictions=info.get("restrictions"),
            payload_quality="ok" if status != NOT_RETURNED else "partial",
        )
        if result != "kept_earlier":
            counts[status] += 1
    return counts
