"""Offline evaluation — recommendation outcomes + RevPAN reporting."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.utils import parse_date


@dataclass
class RevpanReport:
    property_id: str | None
    start: date
    end: date
    available_nights: int
    booked_nights: int
    blocked_nights: int
    revenue: float
    revpan: float
    adr: float
    occupancy: float
    recommended_nights: int
    accepted_or_overridden: int
    applied_nights: int
    avg_recommended_vs_listed: float | None
    # E[RevPAN] delta: sum over nights of (P_rec * p(book|P_rec)) - (P_listed * p(book|P_listed)).
    # This replaces v1's `potential_lift_vs_listed`, which summed max(0, rec - listed)
    # across every recommendation and therefore assumed BOTH that every suggestion was
    # accepted AND that every night still booked at the higher price. That number was
    # structurally incapable of being negative and would have been quoted as "revenue
    # found". Only nights whose recommendation actually reached a channel are counted.
    expected_revpan_delta: float | None
    measurable_nights: int
    owner_id: str | None = None


def record_outcomes_from_inventory(
    conn: sqlite3.Connection,
    start: date | None = None,
    end: date | None = None,
) -> int:
    """Join latest recommendation per night to eventual inventory outcome."""
    params: list[Any] = []
    date_filter = ""
    if start is not None:
        date_filter += " AND r.stay_date >= ?"
        params.append(start.isoformat())
    if end is not None:
        date_filter += " AND r.stay_date <= ?"
        params.append(end.isoformat())

    # Latest recommendation per property/date
    rows = conn.execute(
        f"""
        WITH latest AS (
            SELECT property_id, stay_date, MAX(id) AS max_id
            FROM price_recommendations
            GROUP BY property_id, stay_date
        )
        SELECT r.id AS recommendation_id, r.property_id, r.stay_date,
               r.recommended_price, i.status, i.listed_price, i.booked_price
        FROM price_recommendations r
        JOIN latest l ON l.max_id = r.id
        LEFT JOIN nightly_inventory i
          ON i.property_id = r.property_id AND i.stay_date = r.stay_date
        WHERE 1=1 {date_filter}
        """,
        params,
    ).fetchall()

    n = 0
    for row in rows:
        existing = conn.execute(
            "SELECT id FROM recommendation_outcomes WHERE recommendation_id = ?",
            (row["recommendation_id"],),
        ).fetchone()
        applied = conn.execute(
            """SELECT 1 FROM rate_changes
               WHERE recommendation_id = ? AND result = 'applied' LIMIT 1""",
            (row["recommendation_id"],),
        ).fetchone()
        was_applied = 1 if applied else 0
        booked = 1 if row["status"] == "booked" else 0
        booked_price = float(row["booked_price"]) if row["booked_price"] is not None else None
        revenue = float(booked_price or 0) if booked else 0.0
        final_listed = float(row["listed_price"]) if row["listed_price"] is not None else None
        if existing:
            conn.execute(
                """
                UPDATE recommendation_outcomes SET
                    final_listed_price = ?, booked = ?, booked_price = ?,
                    revenue = ?, price_was_applied = ?, evaluated_at = datetime('now')
                WHERE recommendation_id = ?
                """,
                (final_listed, booked, booked_price, revenue, was_applied,
                 row["recommendation_id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO recommendation_outcomes (
                    recommendation_id, property_id, stay_date,
                    final_listed_price, booked, booked_price, revenue, price_was_applied
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["recommendation_id"],
                    row["property_id"],
                    row["stay_date"],
                    final_listed,
                    booked,
                    booked_price,
                    revenue,
                    was_applied,
                ),
            )
        n += 1
    conn.commit()
    return n


def compute_revpan(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    property_id: str | None = None,
    property_ids: list[str] | None = None,
    owner_id: str | None = None,
) -> RevpanReport:
    ids = list(property_ids) if property_ids is not None else (
        [property_id] if property_id else None
    )
    params: list[Any] = [start.isoformat(), end.isoformat()]
    prop_filter = ""
    if ids:
        placeholders = ",".join("?" for _ in ids)
        prop_filter = f" AND property_id IN ({placeholders})"
        params.extend(ids)

    inv = conn.execute(
        f"""
        SELECT status, listed_price, booked_price
        FROM nightly_inventory
        WHERE stay_date >= ? AND stay_date <= ? {prop_filter}
        """,
        params,
    ).fetchall()

    available = booked = blocked = 0
    revenue = 0.0
    for row in inv:
        if row["status"] == "blocked":
            blocked += 1
        elif row["status"] == "booked":
            booked += 1
            revenue += float(row["booked_price"] or row["listed_price"] or 0)
        else:
            available += 1

    avail_for_revpan = available + booked  # blocked excluded
    revpan = revenue / avail_for_revpan if avail_for_revpan else 0.0
    adr = revenue / booked if booked else 0.0
    occ = booked / avail_for_revpan if avail_for_revpan else 0.0

    rec_params: list[Any] = [start.isoformat(), end.isoformat()]
    rec_filter = ""
    if ids:
        placeholders = ",".join("?" for _ in ids)
        rec_filter = f" AND r.property_id IN ({placeholders})"
        rec_params.extend(ids)
    recs = conn.execute(
        f"""
        SELECT r.recommended_price, r.listed_price_at_run, r.status,
               r.expected_book_prob, r.expected_revpan,
               COALESCE(o.price_was_applied, 0) AS applied
        FROM price_recommendations r
        LEFT JOIN recommendation_outcomes o ON o.recommendation_id = r.id
        WHERE r.stay_date >= ? AND r.stay_date <= ? {rec_filter}
        """,
        rec_params,
    ).fetchall()

    deltas: list[float] = []
    accepted = 0
    applied = 0
    revpan_delta = 0.0
    measurable = 0
    for r in recs:
        if r["status"] in {"accepted", "overridden"}:
            accepted += 1
        listed = r["listed_price_at_run"]
        if listed is not None:
            deltas.append(float(r["recommended_price"]) - float(listed))
        if int(r["applied"] or 0) == 1:
            applied += 1
            # Only nights where the recommendation actually reached the channel can
            # say anything about the engine's effect.
            if r["expected_revpan"] is not None and r["expected_book_prob"] is not None and listed:
                p = float(r["expected_book_prob"])
                revpan_delta += float(r["expected_revpan"]) - (float(listed) * p)
                measurable += 1

    avg_delta = sum(deltas) / len(deltas) if deltas else None

    label_pid = property_id
    if label_pid is None and ids and len(ids) == 1 and not owner_id:
        label_pid = ids[0]
    return RevpanReport(
        property_id=label_pid,
        start=start,
        end=end,
        available_nights=available,
        booked_nights=booked,
        blocked_nights=blocked,
        revenue=revenue,
        revpan=revpan,
        adr=adr,
        occupancy=occ,
        recommended_nights=len(recs),
        accepted_or_overridden=accepted,
        applied_nights=applied,
        avg_recommended_vs_listed=avg_delta,
        expected_revpan_delta=revpan_delta if measurable else None,
        measurable_nights=measurable,
        owner_id=owner_id,
    )


def format_report(report: RevpanReport) -> str:
    if report.property_id:
        prop = report.property_id
    elif report.owner_id:
        prop = f"owner:{report.owner_id}"
    else:
        prop = "ALL"
    lines = [
        f"RevPAN report — {prop} — {report.start} → {report.end}",
        f"  Available nights (open): {report.available_nights}",
        f"  Booked nights:           {report.booked_nights}",
        f"  Blocked nights:          {report.blocked_nights}",
        f"  Revenue:                 ${report.revenue:,.0f}",
        f"  RevPAN:                  ${report.revpan:,.2f}",
        f"  ADR:                     ${report.adr:,.2f}",
        f"  Occupancy:               {report.occupancy:.1%}",
        f"  Recommendations:         {report.recommended_nights}",
        f"  Accepted/overridden:     {report.accepted_or_overridden}",
        f"  Actually applied:        {report.applied_nights}",
    ]
    if report.avg_recommended_vs_listed is not None:
        lines.append(f"  Avg rec - listed:        ${report.avg_recommended_vs_listed:,.2f}")
    if report.expected_revpan_delta is not None:
        lines.append(
            f"  E[RevPAN] delta:         ${report.expected_revpan_delta:,.2f} "
            f"over {report.measurable_nights} applied night(s)"
        )
    else:
        lines.append("  E[RevPAN] delta:         n/a (no recommendation reached a channel yet)")
    return "\n".join(lines)


def portfolio_reports(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    property_ids: list[str] | None = None,
    owner_id: str | None = None,
) -> list[RevpanReport]:
    if property_ids is None:
        if owner_id:
            from src.db import resolve_property_ids

            property_ids = resolve_property_ids(conn, owner_id=owner_id) or []
        else:
            property_ids = [
                r["property_id"]
                for r in conn.execute(
                    "SELECT property_id FROM properties ORDER BY property_id"
                ).fetchall()
            ]
    reports = [compute_revpan(conn, start, end, pid) for pid in property_ids]
    if owner_id:
        reports.append(
            compute_revpan(conn, start, end, property_ids=property_ids, owner_id=owner_id)
        )
    elif len(property_ids) != 1:
        reports.append(compute_revpan(conn, start, end, None))
    return reports
