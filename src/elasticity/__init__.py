"""Elasticity priors — luxury cold-start heuristics."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from src.features import NightFeatures


@dataclass
class ElasticityContext:
    prior: float
    conversion_rate: float | None
    soften_upward: bool
    note: str


def inquiry_conversion(conn: sqlite3.Connection, property_id: str) -> float | None:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(inquiry_count), 0) AS inquiries,
            -- v1 summed inquiry_count on converted rows, so one booking recorded
            -- against a 5-inquiry row counted as 5 conversions and inflated the rate.
            COALESCE(SUM(CASE WHEN converted = 1 THEN 1 ELSE 0 END), 0) AS conversions
        FROM booking_inquiries
        WHERE property_id = ?
        """,
        (property_id,),
    ).fetchone()
    inquiries = int(row["inquiries"] or 0)
    if inquiries < 5:
        return None
    return float(row["conversions"]) / float(inquiries)


# NOTE on `luxury_prior`: in v1 this value was read, stored on the context, rendered
# into a human-readable note, and then never used in any arithmetic — the advertised
# "-0.8 luxury elasticity" had zero effect on any price. Elasticity is now applied for
# real in src/bookprob (per-season beta, of which luxury_prior is the peak-season
# default). This module retains only the first-party conversion override.


def elasticity_context(
    conn: sqlite3.Connection,
    feat: NightFeatures,
    policy: dict[str, Any],
) -> ElasticityContext:
    cfg = policy.get("elasticity", {})
    prior = float(cfg.get("luxury_prior", -0.8))
    threshold = float(cfg.get("soft_conversion_threshold", 0.15))
    conv = inquiry_conversion(conn, feat.property_id)
    if conv is not None and conv < threshold:
        return ElasticityContext(
            prior=prior,
            conversion_rate=conv,
            soften_upward=True,
            note=f"Inquiry conversion {conv:.0%} below {threshold:.0%} — soften upward moves",
        )
    return ElasticityContext(
        prior=prior,
        conversion_rate=conv,
        soften_upward=False,
        note=f"Luxury elasticity prior {prior}",
    )


def maybe_soften(
    listed: float | None,
    proposed: float,
    ctx: ElasticityContext,
    policy: dict[str, Any],
) -> float:
    if not ctx.soften_upward or listed is None:
        return proposed
    if proposed <= listed:
        return proposed
    factor = float(policy.get("elasticity", {}).get("soften_factor", 0.5))
    return listed + (proposed - listed) * factor
