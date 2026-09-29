"""Forward owned-inventory seeding for diagnostic and production runs.

Protocol (locked for testruns after 2026-09-25): a truly Guesty-blind year cannot
supply property-specific forward calendars. Public Airbnb discovery often returns
proxies. Diagnostic testruns therefore use **read-only Guesty calendar** as the
owned-inventory source (`guesty-readonly`). Comp sweeps stay independent.
`empty-skeleton` inserts availability rows with no listed price when an operator
explicitly wants compose without an incumbent rate.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


class EmptyInventoryError(RuntimeError):
    """Scoped future inventory is empty; recommend must not freeze a 0-row export."""


@dataclass
class InventoryCount:
    property_ids: list[str]
    start: date
    end: date
    nights: int
    available: int
    with_listed_price: int

    @property
    def empty(self) -> bool:
        return self.nights == 0 or self.available == 0


def count_scoped_inventory(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    property_ids: list[str] | None,
) -> InventoryCount:
    sql = (
        "SELECT COUNT(*) AS n, "
        "SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS avail, "
        "SUM(CASE WHEN listed_price IS NOT NULL THEN 1 ELSE 0 END) AS priced "
        "FROM nightly_inventory WHERE stay_date >= ? AND stay_date <= ?"
    )
    params: list[object] = [start.isoformat(), end.isoformat()]
    ids = list(property_ids or [])
    if ids:
        sql += f" AND property_id IN ({','.join('?' for _ in ids)})"
        params.extend(ids)
    row = conn.execute(sql, params).fetchone()
    return InventoryCount(
        property_ids=ids,
        start=start,
        end=end,
        nights=int(row["n"] or 0),
        available=int(row["avail"] or 0),
        with_listed_price=int(row["priced"] or 0),
    )


def require_forward_inventory(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    property_ids: list[str] | None,
) -> InventoryCount:
    counts = count_scoped_inventory(conn, start, end, property_ids)
    if counts.empty:
        scope = ",".join(counts.property_ids) or "(default locked portfolio)"
        raise EmptyInventoryError(
            "0 available nights in scope: "
            f"property={scope} from={start.isoformat()} to={end.isoformat()} "
            f"inventory_rows={counts.nights} available={counts.available}. "
            "Seed with `wp-price seed-forward-inventory --source guesty-readonly` "
            "or `--source empty-skeleton` before recommend/export."
        )
    return counts


def seed_empty_skeleton(
    conn: sqlite3.Connection,
    property_ids: list[str],
    start: date,
    end: date,
) -> int:
    """Insert availability rows with no listed price (compose without incumbent)."""
    written = 0
    today = date.today()
    cur = start
    while cur <= end:
        for pid in property_ids:
            lead = (cur - today).days if cur >= today else None
            conn.execute(
                """
                INSERT INTO nightly_inventory (
                    property_id, stay_date, listed_price, booked_price, status,
                    lead_time_days, day_of_week, channel, evidence_kind, updated_at
                ) VALUES (?, ?, NULL, NULL, 'available', ?, ?, 'testrun_skeleton',
                          'skeleton', datetime('now'))
                ON CONFLICT(property_id, stay_date) DO UPDATE SET
                    channel=excluded.channel,
                    evidence_kind=excluded.evidence_kind,
                    updated_at=datetime('now')
                WHERE nightly_inventory.listed_price IS NULL
                """,
                (pid, cur.isoformat(), lead, cur.weekday()),
            )
            written += 1
        cur += timedelta(days=1)
    conn.commit()
    return written


def seed_guesty_readonly(
    conn: sqlite3.Connection,
    property_ids: list[str],
    *,
    horizon_days: int = 365,
    history_days: int = 14,
) -> Any:
    """Pull only the scoped listings' calendars. Never writes rates back to Guesty."""
    from src.pms.guesty import GuestyClient
    from src.pms.sync import sync_all

    client = GuestyClient()
    return sync_all(
        conn,
        client,
        horizon_days=horizon_days,
        history_days=history_days,
        property_ids=property_ids,
        mark_production=False,
    )
