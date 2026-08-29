"""Comp-set evidence.

The v1 build wrote `comps`, `comp_set_members` and `comp_snapshots` and then never
read them: the `comp_move` reason code existed in the taxonomy but was unreachable,
and the doctrine's claim that "competitor rates inform context" was unimplemented.

Comp data is an UNRELIABLE DEPENDENCY (scraper-first, per docs/LOCKED_INPUTS.md).
Every reading therefore carries freshness and coverage, and callers must honour
`usable` rather than reading `price` directly.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from src.features import NightFeatures


@dataclass
class CompEvidence:
    price: float | None
    coverage: float          # fraction of the property's comp set with a usable snapshot
    members: int             # comps in the set
    observed: int            # comps with a snapshot for this night
    age_hours: float | None  # freshness of the newest snapshot used
    usable: bool
    reason: str
    exact_date: bool = True  # False when nearby same-weekday-class nights were used


def _age_hours(as_of: str | None) -> float | None:
    if not as_of:
        return None
    text = str(as_of)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return max(0.0, (datetime.now() - datetime.strptime(text[:19], fmt)).total_seconds() / 3600.0)
        except ValueError:
            continue
    return None


def comp_evidence(
    conn: sqlite3.Connection,
    feat: NightFeatures,
    policy: dict[str, Any],
) -> CompEvidence | None:
    """Percentile of comp-set listed prices for this night, with a usability verdict."""
    health = policy.get("data_health", {})
    max_age = float(health.get("comp_max_staleness_hours", 48))
    min_cov = float(health.get("comp_min_coverage", 0.60))
    min_members = int(health.get("comp_min_members", 3))
    pct = float(policy.get("ceiling", {}).get("comp_percentile", 0.75))

    members = [
        r["comp_id"]
        for r in conn.execute(
            "SELECT comp_id FROM comp_set_members WHERE property_id = ?",
            (feat.property_id,),
        ).fetchall()
    ]
    if not members:
        return CompEvidence(None, 0.0, 0, 0, None, False, "no comp set defined")

    placeholders = ",".join("?" for _ in members)

    def _query(stay_dates: list[str]) -> list[Any]:
        """Latest OK snapshot per comp across the given stay dates.

        scrape_status is filtered to 'ok' deliberately: 'unavailable' means the comp
        was checked and had no price, and 'failed' means we could not check. Treating
        either as evidence would let a degrading scraper quietly move the ceiling.
        """
        dph = ",".join("?" for _ in stay_dates)
        return conn.execute(
            f"""
            SELECT s.comp_id, s.listed_price, s.as_of, s.stay_date
            FROM comp_snapshots s
            JOIN (
                SELECT comp_id, MAX(as_of) AS mx
                FROM comp_snapshots
                WHERE stay_date IN ({dph}) AND comp_id IN ({placeholders})
                  AND scrape_status = 'ok' AND listed_price IS NOT NULL
                GROUP BY comp_id
            ) l ON l.comp_id = s.comp_id AND l.mx = s.as_of
            WHERE s.stay_date IN ({dph}) AND s.listed_price IS NOT NULL
              AND s.scrape_status = 'ok'
            GROUP BY s.comp_id
            """,
            [*stay_dates, *members, *stay_dates],
        ).fetchall()

    def _collect(rows: list[Any]) -> tuple[list[float], list[float]]:
        px: list[float] = []
        ag: list[float] = []
        for r in rows:
            age = _age_hours(r["as_of"])
            if age is not None and age > max_age:
                continue
            px.append(float(r["listed_price"]))
            if age is not None:
                ag.append(age)
        return px, ag

    exact_date = True
    prices, ages = _collect(_query([feat.stay_date.isoformat()]))

    # Sweeps are sampled, so most nights have no exact observation. Fall back to
    # nearby nights of the same weekday class — which is the level the ceiling
    # consumes comp evidence at anyway.
    if (len(prices) / len(members)) < min_cov:
        mcfg = policy.get("scrape", {}).get("match", {})
        span = int(mcfg.get("max_day_distance", 10))
        same_class = bool(mcfg.get("require_same_dow_class", True))
        target_weekend = feat.day_of_week in (4, 5)
        nearby = [
            (feat.stay_date + timedelta(days=d)).isoformat()
            for d in range(-span, span + 1)
            if not same_class
            or (((feat.stay_date + timedelta(days=d)).weekday() in (4, 5)) == target_weekend)
        ]
        alt_prices, alt_ages = _collect(_query(nearby))
        if len(alt_prices) > len(prices):
            prices, ages, exact_date = alt_prices, alt_ages, False

    coverage = len(prices) / len(members)
    newest = min(ages) if ages else None

    if len(members) < min_members:
        return CompEvidence(None, coverage, len(members), len(prices), newest, False,
                            f"comp set has {len(members)} members, need {min_members}", exact_date)
    if not prices:
        return CompEvidence(None, 0.0, len(members), 0, None, False,
                            "no fresh comp snapshots for this night", exact_date)
    if coverage < min_cov:
        return CompEvidence(None, coverage, len(members), len(prices), newest, False,
                            f"comp coverage {coverage:.0%} below {min_cov:.0%}", exact_date)

    price = float(np.percentile(np.array(prices, dtype=float), pct * 100.0))
    window = "" if exact_date else " (nearby same-DOW nights)"
    return CompEvidence(price, coverage, len(members), len(prices), newest, True,
                        f"p{int(pct*100)} of {len(prices)}/{len(members)} comps{window}",
                        exact_date)


def market_percentile(
    conn: sqlite3.Connection,
    stay_date: Any,
    percentile: str = "p75",
) -> tuple[float | None, int]:
    """Whole-market level for a night, independent of the curated comp set.

    A market sweep sees every bookable listing in the bounding box, so this is free
    and does not degrade when the curated set is incomplete. Used to detect a comp
    set that has drifted away from the market it is supposed to represent.
    """
    row = conn.execute(
        f"SELECT {percentile} AS v, listings FROM market_snapshots "
        "WHERE stay_date = ? ORDER BY as_of DESC LIMIT 1",
        (stay_date.isoformat() if hasattr(stay_date, "isoformat") else str(stay_date),),
    ).fetchone()
    if row is None or row["v"] is None:
        return None, 0
    return float(row["v"]), int(row["listings"])
