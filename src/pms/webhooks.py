"""Small, durable Guesty webhook boundary.

Guesty webhook deliveries are at-least-once and may be out of order.  This
module deliberately does not mutate pricing from an HTTP callback.  It records
the delivery once, extracts a bounded refresh target, and lets the normal
Guesty sync path re-read authoritative calendar data before recommending or
writing a rate.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class WebhookTarget:
    event_id: str
    event_type: str
    listing_id: str | None
    start: date | None
    end: date | None
    duplicate: bool = False


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def record_delivery(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
    received_at: str | None = None,
) -> WebhookTarget:
    """Record one delivery and return the bounded calendar refresh target.

    ``event_id`` should be Guesty's event id or Svix id.  Replaying it is a
    no-op, which makes retries safe. Unknown event shapes are stored and return
    an unbounded target so the caller can choose a full sync.
    """
    if not event_id:
        raise ValueError("webhook event_id is required")
    listing_raw = payload.get("listing")
    listing: dict[str, Any] = listing_raw if isinstance(listing_raw, dict) else {}
    calendar_raw = payload.get("calendar")
    calendar: dict[str, Any] = calendar_raw if isinstance(calendar_raw, dict) else {}
    listing_id = _first(payload, "listingId", "listing_id") or _first(listing, "_id", "id")
    start = _date(_first(payload, "startDate", "start_date")) or _date(_first(calendar, "startDate", "start_date"))
    end = _date(_first(payload, "endDate", "end_date")) or _date(_first(calendar, "endDate", "end_date"))
    cur = conn.execute(
        """INSERT OR IGNORE INTO pms_webhook_events
           (event_id, event_type, listing_id, start_date, end_date, payload_json, received_at)
           VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))""",
        (event_id, event_type, str(listing_id) if listing_id else None,
         start.isoformat() if start else None, end.isoformat() if end else None,
         json.dumps(payload, sort_keys=True), received_at),
    )
    conn.commit()
    return WebhookTarget(str(event_id), event_type, str(listing_id) if listing_id else None,
                         start, end, duplicate=(cur.rowcount == 0))
