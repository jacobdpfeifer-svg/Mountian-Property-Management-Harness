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
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from src.utils import parse_date


def take_snapshot(
    conn: sqlite3.Connection,
    as_of: date | None = None,
    horizon_days: int = 365,
) -> dict[str, Any]:
    """Capture on-the-books state for every future night. Idempotent per as_of date.

    Crash-safety: one COMMIT for the whole run. A mid-loop crash rolls the
    transaction back, so the day is missing entirely rather than half-written.
    Gap detection must then flag that missing (property_id, as_of).
    """
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
    by_property: dict[str, int] = defaultdict(int)
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
        by_property[str(r["property_id"])] += 1
    # Single commit: partial days never land. Do not commit inside the loop.
    conn.commit()

    distinct = conn.execute("SELECT COUNT(DISTINCT as_of) AS c FROM pacing_snapshots").fetchone()["c"]
    total = conn.execute("SELECT COUNT(*) AS c FROM pacing_snapshots").fetchone()["c"]
    status = "ok" if written > 0 else "failed"
    return {
        "as_of": as_of.isoformat(),
        "nights_captured": written,
        "properties_captured": dict(by_property),
        "snapshot_days_total": int(distinct or 0),
        "observations_total": int(total or 0),
        "status": status,
    }


def guesty_properties(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Properties that have been synced from Guesty (stable listing id present)."""
    rows = conn.execute(
        """
        SELECT property_id, date(created_at, 'localtime') AS synced_on
        FROM properties
        WHERE pms_listing_id IS NOT NULL AND TRIM(pms_listing_id) != ''
        ORDER BY property_id
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        synced = parse_date(r["synced_on"]) if r["synced_on"] else None
        if synced is None:
            continue
        out.append({"property_id": r["property_id"], "synced_on": synced})
    return out


def verify_snapshots(
    conn: sqlite3.Connection,
    *,
    as_of: date | None = None,
    since: date | None = None,
) -> dict[str, Any]:
    """Find missing (property_id, as_of) days since each property's first Guesty sync.

    A property-day counts as present if at least one pacing_snapshots row exists
    for that pair. Exit-code contract matches scrape-comps: non-zero when the
    run is degraded or failed so a scheduler can alert without parsing output.
    """
    as_of = as_of or date.today()
    props = guesty_properties(conn)
    if not props:
        return {
            "status": "failed",
            "as_of": as_of.isoformat(),
            "since": since.isoformat() if since else None,
            "properties": 0,
            "expected_days": 0,
            "present_days": 0,
            "gaps": [],
            "errors": ["No Guesty-synced properties (pms_listing_id is empty)."],
        }

    earliest = min(p["synced_on"] for p in props)
    window_start = since or earliest
    if window_start > as_of:
        return {
            "status": "ok",
            "as_of": as_of.isoformat(),
            "since": window_start.isoformat(),
            "earliest_guesty_sync": earliest.isoformat(),
            "properties": len(props),
            "expected_days": 0,
            "present_days": 0,
            "gaps": [],
            "errors": [],
        }

    present_rows = conn.execute(
        """
        SELECT property_id, as_of, COUNT(*) AS n
        FROM pacing_snapshots
        WHERE as_of >= ? AND as_of <= ?
        GROUP BY property_id, as_of
        """,
        (window_start.isoformat(), as_of.isoformat()),
    ).fetchall()
    present = {(r["property_id"], r["as_of"]) for r in present_rows if r["n"]}

    gaps: list[dict[str, str]] = []
    expected = 0
    for p in props:
        start = max(window_start, p["synced_on"])
        d = start
        while d <= as_of:
            expected += 1
            if (p["property_id"], d.isoformat()) not in present:
                gaps.append({"property_id": p["property_id"], "as_of": d.isoformat()})
            d += timedelta(days=1)

    status = "ok" if not gaps else "degraded"
    return {
        "status": status,
        "as_of": as_of.isoformat(),
        "since": window_start.isoformat(),
        "earliest_guesty_sync": earliest.isoformat(),
        "properties": len(props),
        "expected_days": expected,
        "present_days": expected - len(gaps),
        "gaps": gaps,
        "errors": (
            [f"{len(gaps)} missing (property_id, as_of) day(s) since {window_start.isoformat()}"]
            if gaps else []
        ),
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
