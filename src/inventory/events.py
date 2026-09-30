"""Market booking events: when did a night actually sell?

Single definition shared by the replay labeler and the lead-conditioned booking
model. A booking event is a sold, non-owner reservation's confirmation stamp
(confirmed, checked in, or checked out), expanded over its nights.
`nightly_inventory.booked_at` is used only for legacy rows with no reservation id;
a row linked to a reservation is judged by that reservation, so an inquiry or
owner stay can never become a sale.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

from src.pms.sync import BOOKING_STATUSES, OWNER_SOURCES
from src.utils import parse_date


def booking_events(
    conn: sqlite3.Connection,
    property_ids: list[str] | None = None,
) -> dict[tuple[str, str], str]:
    """(property_id, stay_date ISO) -> earliest booking timestamp."""
    events: dict[tuple[str, str], str] = {}
    status_marks = ",".join("?" for _ in BOOKING_STATUSES)
    owner_marks = ",".join("?" for _ in OWNER_SOURCES)
    prop_clause = ""
    params: list[str] = []
    if property_ids is not None:
        prop_clause = f" AND property_id IN ({','.join('?' for _ in property_ids)})"
        params = list(property_ids)
    for r in conn.execute(
        f"""
        SELECT property_id, check_in, check_out, confirmed_at
        FROM reservations
        WHERE LOWER(status) IN ({status_marks}) AND confirmed_at IS NOT NULL
          AND LOWER(COALESCE(source, '')) NOT IN ({owner_marks}){prop_clause}
        """,
        [*sorted(BOOKING_STATUSES), *sorted(OWNER_SOURCES), *params],
    ):
        cur = parse_date(r["check_in"])
        end = parse_date(r["check_out"])
        while cur < end:
            key = (r["property_id"], cur.isoformat())
            old = events.get(key)
            if old is None or str(r["confirmed_at"]) < old:
                events[key] = str(r["confirmed_at"])
            cur += timedelta(days=1)
    for r in conn.execute(
        f"""
        SELECT property_id, stay_date, booked_at
        FROM nightly_inventory
        WHERE booked_at IS NOT NULL AND reservation_id IS NULL{prop_clause}
        """,
        params,
    ):
        key = (r["property_id"], r["stay_date"])
        old = events.get(key)
        if old is None or str(r["booked_at"]) < old:
            events[key] = str(r["booked_at"])
    return events
