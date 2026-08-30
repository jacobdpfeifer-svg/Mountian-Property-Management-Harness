"""Comp rate-movement → demand_signals (optional upstream contributor).

Writes a soft demand strength from curated-comp median price changes vs a
lookback window. Does NOT replace calendar events; takes the max with existing
signals only when the movement score is higher.

Weather/snowfall remain on the SQI path — never written here.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

import numpy as np


def upsert_comp_movement_signals(
    conn: sqlite3.Connection,
    *,
    as_of: date | None = None,
    lookback_days: int = 14,
    region: str = "winter_park",
    # Map median WoW lift → signal_strength contribution (owner-tunable via caller).
    lift_to_strength: tuple[tuple[float, float], ...] = (
        (0.08, 0.55),
        (0.15, 0.70),
        (0.25, 0.85),
    ),
) -> int:
    """Derive demand_signals rows from comp median rate movement. Returns rows written."""
    as_of = as_of or date.today()
    prior = as_of - timedelta(days=lookback_days)

    current = conn.execute(
        """
        SELECT stay_date, AVG(listed_price) AS med
        FROM comp_snapshots
        WHERE scrape_status = 'ok' AND listed_price IS NOT NULL
          AND as_of >= ? AND as_of <= ?
        GROUP BY stay_date
        """,
        (prior.isoformat(), as_of.isoformat()),
    ).fetchall()
    if not current:
        return 0

    baseline = {
        r["stay_date"]: float(r["med"])
        for r in conn.execute(
            """
            SELECT stay_date, AVG(listed_price) AS med
            FROM comp_snapshots
            WHERE scrape_status = 'ok' AND listed_price IS NOT NULL
              AND as_of >= ? AND as_of < ?
            GROUP BY stay_date
            """,
            ((prior - timedelta(days=lookback_days)).isoformat(), prior.isoformat()),
        ).fetchall()
    }

    written = 0
    for row in current:
        stay = row["stay_date"]
        cur = float(row["med"])
        base = baseline.get(stay)
        if not base or base <= 0:
            continue
        lift = (cur - base) / base
        strength = 0.0
        for threshold, score in lift_to_strength:
            if lift >= threshold:
                strength = score
        if strength <= 0:
            continue
        existing = conn.execute(
            """
            SELECT signal_strength FROM demand_signals
            WHERE signal_date=? AND region=? AND event_name=?
            """,
            (stay, region, "Comp-set rate lift"),
        ).fetchone()
        if existing and float(existing["signal_strength"]) >= strength:
            continue
        conn.execute(
            """
            INSERT INTO demand_signals (
                signal_date, region, event_name, signal_strength, source
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(signal_date, region, event_name) DO UPDATE SET
                signal_strength=excluded.signal_strength,
                source=excluded.source
            """,
            (stay, region, "Comp-set rate lift", strength, "comp_movement"),
        )
        written += 1
    if written:
        conn.commit()
    return written


def market_median_lift(
    conn: sqlite3.Connection, stay_date: date, lookback_days: int = 14
) -> float | None:
    """Diagnostic helper: fraction change in market p50 vs prior window."""
    as_of = date.today()
    rows = conn.execute(
        """
        SELECT as_of, p50 FROM market_snapshots
        WHERE stay_date = ? AND p50 IS NOT NULL
        ORDER BY as_of DESC LIMIT 20
        """,
        (stay_date.isoformat(),),
    ).fetchall()
    if len(rows) < 2:
        return None
    recent = [float(r["p50"]) for r in rows if True][:5]
    older_cut = (as_of - timedelta(days=lookback_days)).isoformat()
    older = [float(r["p50"]) for r in rows if str(r["as_of"])[:10] <= older_cut]
    if not recent or not older:
        return None
    base = float(np.mean(older))
    if base <= 0:
        return None
    return (float(np.mean(recent)) - base) / base
