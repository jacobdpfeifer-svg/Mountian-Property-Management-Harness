"""Forward shadow observations — engine rec vs live Guesty vs realized stay."""

from __future__ import annotations

import sqlite3
from datetime import date

from src.config import load_policy
from src.utils import parse_date, season_for


class GuestyWriteForbidden(RuntimeError):
    """Shadow recording must never sit on a DB that already wrote live rates."""


SHADOW_DDL = """
CREATE TABLE IF NOT EXISTS shadow_daily (
    as_of TEXT NOT NULL,
    property_id TEXT NOT NULL,
    stay_date TEXT NOT NULL,
    recommended_price REAL,
    guesty_listed_price REAL,
    status TEXT,
    booked INTEGER,
    lead_time_days INTEGER,
    cancelled INTEGER,
    occupancy REAL,
    adr REAL,
    revpan REAL,
    season TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (as_of, property_id, stay_date)
);
"""


def ensure_shadow_table(conn: sqlite3.Connection) -> None:
    conn.executescript(SHADOW_DDL)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(shadow_daily)")}
    for col, decl in (("rec_run_id", "TEXT"), ("expected_book_prob", "REAL")):
        if col not in have:
            conn.execute(f"ALTER TABLE shadow_daily ADD COLUMN {col} {decl}")
    conn.commit()


def record_shadow_day(
    conn: sqlite3.Connection,
    *,
    as_of: date,
    property_id: str,
) -> int:
    """Snapshot today's engine rec vs Guesty listed/booked inventory for one property.

    Writes only to `shadow_daily`. Aborts if this DB already applied Guesty rates.
    """
    writes = guesty_write_count(conn)
    if writes:
        raise GuestyWriteForbidden(
            f"shadow-record refused: {writes} Guesty write(s) already in rate_changes"
        )
    ensure_shadow_table(conn)
    policy = load_policy()
    seasons = policy.get("seasons", {})
    # The engine's price for a night is its LATEST recommendation made on or before
    # as_of. Joining every run (the old query) wrote one row per historical run and
    # the upsert kept whichever the scan returned last — often a stale run.
    rows = conn.execute(
        """
        SELECT i.stay_date, i.listed_price, i.status, i.booked_price,
               r.recommended_price, r.expected_book_prob, r.run_id
        FROM nightly_inventory i
        LEFT JOIN price_recommendations r ON r.id = (
            SELECT p.id FROM price_recommendations p
            WHERE p.property_id = i.property_id AND p.stay_date = i.stay_date
              AND date(p.created_at) <= ?
            ORDER BY p.created_at DESC, p.id DESC LIMIT 1
        )
        WHERE i.property_id = ? AND i.stay_date >= ?
        """,
        (as_of.isoformat(), property_id, as_of.isoformat()),
    ).fetchall()
    written = 0
    for row in rows:
        booked = 1 if row["status"] == "booked" else 0
        listed = row["listed_price"]
        adr = row["booked_price"] if booked else listed
        occ = 1.0 if booked else 0.0
        revpan = (adr or 0) * occ
        stay = parse_date(str(row["stay_date"]))
        season_name, _ = season_for(stay, seasons)
        conn.execute(
            """
            INSERT INTO shadow_daily (
                as_of, property_id, stay_date, recommended_price, guesty_listed_price,
                status, booked, lead_time_days, cancelled, occupancy, adr, revpan, season,
                rec_run_id, expected_book_prob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(as_of, property_id, stay_date) DO UPDATE SET
                recommended_price=excluded.recommended_price,
                rec_run_id=excluded.rec_run_id,
                expected_book_prob=excluded.expected_book_prob,
                lead_time_days=excluded.lead_time_days,
                guesty_listed_price=excluded.guesty_listed_price,
                status=excluded.status,
                booked=excluded.booked,
                occupancy=excluded.occupancy,
                adr=excluded.adr,
                revpan=excluded.revpan,
                season=excluded.season
            """,
            (
                as_of.isoformat(),
                property_id,
                row["stay_date"],
                row["recommended_price"],
                listed,
                row["status"],
                booked,
                (stay - as_of).days,
                occ,
                adr,
                revpan,
                season_name,
                row["run_id"],
                row["expected_book_prob"],
            ),
        )
        written += 1
    conn.commit()
    return written


def guesty_write_count(conn: sqlite3.Connection) -> int:
    """Count live Guesty writes recorded in rate_changes."""
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rate_changes'"
    ).fetchone() is None:
        return 0
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM rate_changes
        WHERE result = 'applied' AND lower(COALESCE(actor, '')) LIKE '%guesty%'
        """
    ).fetchone()
    return int(row["n"] or 0)
