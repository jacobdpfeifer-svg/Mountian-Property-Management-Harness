"""Daily pacing snapshotter.

The single highest-value table in the system and the one the v1 build omitted.
`nightly_inventory` is keyed (property_id, stay_date) and overwritten on every
ingest, so it holds only the CURRENT shape of the calendar. How a date filled in
over time — the pacing curve — was being discarded on every run.

At 4 properties, first-party data is ~1,460 property-nights/yr. Observing each
future night once per day at each lead time turns that into ~40,000 observations
per year, which is the difference between "no model is possible" and "a model is
possible next season".

Every day this does not run is permanently unrecoverable. Run it daily, before
ingest overwrites state, even while nothing consumes it yet.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from src.utils import parse_date


def take_snapshot(
    conn: sqlite3.Connection,
    as_of: date | None = None,
    horizon_days: int = 365,
) -> dict[str, Any]:
    """Capture on-the-books state for every future night. Idempotent per as_of date."""
    as_of = as_of or date.today()
    rows = conn.execute(
        """
        SELECT property_id, stay_date, status, listed_price, min_stay
        FROM nightly_inventory
        WHERE stay_date >= ?
        ORDER BY property_id, stay_date
        """,
        (as_of.isoformat(),),
    ).fetchall()

    written = 0
    for r in rows:
        stay = parse_date(r["stay_date"])
        days_out = (stay - as_of).days
        if days_out < 0 or days_out > horizon_days:
            continue
        conn.execute(
            """
            INSERT INTO pacing_snapshots (as_of, property_id, stay_date, days_out,
                status, listed_price, min_stay)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(as_of, property_id, stay_date) DO UPDATE SET
                days_out=excluded.days_out, status=excluded.status,
                listed_price=excluded.listed_price, min_stay=excluded.min_stay
            """,
            (as_of.isoformat(), r["property_id"], stay.isoformat(), days_out,
             r["status"], r["listed_price"], r["min_stay"]),
        )
        written += 1
    conn.commit()

    distinct = conn.execute("SELECT COUNT(DISTINCT as_of) AS c FROM pacing_snapshots").fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) AS c FROM pacing_snapshots").fetchone()["c"]
    return {
        "as_of": as_of.isoformat(),
        "nights_captured": written,
        "snapshot_days_total": int(distinct or 0),
        "observations_total": int(total or 0),
    }


def backfill_from_inventory(conn: sqlite3.Connection, days: int = 30) -> dict[str, Any]:
    """Best-effort seeding so pacing features are not dead on arrival.

    HONEST LIMITATION: this reconstructs prior days from CURRENT state, so a night
    booked yesterday looks like it was booked `days` ago. It biases pacing to look
    faster than reality. Rows are marked by their as_of only; they are a bootstrap,
    not evidence. Real curves require the daily snapshotter to actually run.
    """
    from datetime import timedelta

    today = date.today()
    written = 0
    for back in range(days, 0, -1):
        as_of = today - timedelta(days=back)
        res = take_snapshot(conn, as_of=as_of)
        written += res["nights_captured"]
    return {"backfilled_days": days, "rows": written, "warning": "reconstructed from current state; biased"}
