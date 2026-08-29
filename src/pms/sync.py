"""Guesty -> local schema sync.

Replaces the CSV/iCal bootstrap as the system of record. Three passes:

  listings     -> properties        (identity, floors/ceilings seeded from Guesty prices)
  calendar     -> nightly_inventory (nightly price, status, min-stay)
  reservations -> booked_price      (what actually converted, for the ceiling)

The calendar carries the LISTED price for every night including booked ones, but a
listed price on a booked night is not what the guest paid. Booked prices are therefore
taken from reservations (fareAccommodation / nights) and written over the calendar's
number, because the ceiling model is explicitly built on realised prices.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from src.pms.guesty import GuestyClient, GuestyListing, parse_guesty_date

# Guesty calendar day status -> our three-state model.
_STATUS = {
    "available": "available",
    "unavailable": "blocked",
    "booked": "booked",
    "reserved": "booked",
}


@dataclass
class SyncReport:
    listings: int = 0
    nights: int = 0
    reservations: int = 0
    booked_nights_priced: int = 0
    horizon_days: int = 0
    history_days: int = 0
    warnings: list[str] = field(default_factory=list)


def _floor_and_ceiling(listing: GuestyListing) -> tuple[float, float, float]:
    """Provisional bounds from Guesty's base rates, used only until the calendar lands.

    WARNING: Guesty's `basePrice` is a STARTING rate that dynamic pricing adjusts
    upward; it is not a ceiling. Seeding a ceiling from it understates reality badly
    (measured: basePrice $420/$618 on properties whose calendar carries $2,600-2,841
    at Christmas and which realised $a much higher realized price/night). `recalibrate_bounds` overwrites
    these from observed prices as soon as the calendar is synced.
    """
    base = float(listing.base_price or 0) or 400.0
    weekend = float(listing.weekend_base_price or base)
    anchor = max(base, weekend)
    return round(base * 0.60), round(anchor * 1.15), round(anchor * 3.0)


def recalibrate_bounds(conn: sqlite3.Connection, report: SyncReport) -> None:
    """Reset each property's floor/ceiling from what it actually lists and achieves.

    The operator's own calendar is a far better prior than any configured base rate:
    it already encodes their seasonality, their weekend structure and their judgement.
    Realised booked prices are included because a night that sold above the listed
    distribution proves the ceiling is higher than the calendar suggests.
    """
    import numpy as np

    for row in conn.execute("SELECT property_id FROM properties").fetchall():
        pid = row["property_id"]
        prices = [
            float(r["p"]) for r in conn.execute(
                """
                SELECT listed_price AS p FROM nightly_inventory
                WHERE property_id = ? AND listed_price IS NOT NULL AND listed_price > 0
                UNION ALL
                SELECT booked_price AS p FROM nightly_inventory
                WHERE property_id = ? AND booked_price IS NOT NULL AND booked_price > 0
                """,
                (pid, pid),
            ).fetchall()
        ]
        if len(prices) < 30:
            report.warnings.append(f"{pid}: only {len(prices)} observed prices — bounds left at seed")
            continue
        arr = np.array(prices, dtype=float)
        floor = float(np.percentile(arr, 5)) * 0.80
        base_ceiling = float(np.percentile(arr, 90))
        max_ceiling = max(float(arr.max()) * 1.35, base_ceiling * 1.5)
        conn.execute(
            "UPDATE properties SET min_floor_rate=?, base_ceiling_rate=?, max_ceiling_rate=? "
            "WHERE property_id=?",
            (round(floor), round(base_ceiling), round(max_ceiling), pid),
        )
    conn.commit()


def sync_listings(conn: sqlite3.Connection, client: GuestyClient,
                  report: SyncReport) -> list[GuestyListing]:
    listings = client.listings()
    for l in listings:
        floor, base_ceiling, max_ceiling = _floor_and_ceiling(l)
        conn.execute(
            """
            INSERT INTO properties (property_id, name, bedrooms, bathrooms, amenities,
                base_ceiling_rate, min_floor_rate, max_ceiling_rate, luxury_tier,
                target_alos, timezone, pms_listing_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'luxury', 3.0, ?, ?)
            ON CONFLICT(property_id) DO UPDATE SET
                name=excluded.name, bedrooms=excluded.bedrooms,
                bathrooms=excluded.bathrooms, amenities=excluded.amenities,
                timezone=excluded.timezone, pms_listing_id=excluded.pms_listing_id
            """,
            (l.property_id, l.nickname or l.title, l.bedrooms or 0,
             float(l.bathrooms or 0), json.dumps(l.amenities),
             base_ceiling, floor, max_ceiling, l.timezone, l.listing_id),
        )
        if l.base_price and l.weekend_base_price and l.base_price == l.weekend_base_price:
            report.warnings.append(
                f"{l.nickname}: base and weekend base are both ${l.base_price:.0f} — "
                "no weekend differential configured in Guesty"
            )
    report.listings = len(listings)
    conn.commit()
    return listings


def sync_calendar(conn: sqlite3.Connection, client: GuestyClient,
                  listings: list[GuestyListing], start: date, end: date,
                  report: SyncReport) -> None:
    for l in listings:
        # Guesty caps calendar range per request; walk it in chunks.
        cur = start
        while cur <= end:
            chunk_end = min(cur + timedelta(days=364), end)
            for day in client.calendar(l.listing_id, cur, chunk_end):
                stay = parse_guesty_date(day.get("date"))
                if stay is None:
                    continue
                status = _STATUS.get(str(day.get("status", "")).lower(), "blocked")
                price = day.get("price")
                conn.execute(
                    """
                    INSERT INTO nightly_inventory (property_id, stay_date, listed_price,
                        booked_price, status, day_of_week, channel, min_stay, updated_at)
                    VALUES (?, ?, ?, NULL, ?, ?, 'guesty', ?, datetime('now'))
                    ON CONFLICT(property_id, stay_date) DO UPDATE SET
                        listed_price=excluded.listed_price,
                        status=excluded.status,
                        day_of_week=excluded.day_of_week,
                        channel='guesty',
                        min_stay=excluded.min_stay,
                        updated_at=datetime('now')
                    """,
                    (l.property_id, stay.isoformat(),
                     float(price) if price is not None else None,
                     status, stay.weekday(), day.get("minNights")),
                )
                report.nights += 1
            cur = chunk_end + timedelta(days=1)
    conn.commit()


def sync_reservations(conn: sqlite3.Connection, client: GuestyClient,
                      listings: list[GuestyListing], report: SyncReport) -> None:
    by_listing = {l.listing_id: l.property_id for l in listings}
    for res in client.reservations():
        if str(res.get("status", "")).lower() in {"canceled", "cancelled", "declined", "expired"}:
            continue
        pid = by_listing.get(res.get("listingId"))
        ci, co = parse_guesty_date(res.get("checkIn")), parse_guesty_date(res.get("checkOut"))
        if not pid or not ci or not co:
            continue
        report.reservations += 1
        money = res.get("money") or {}
        fare = money.get("fareAccommodation")
        nights = int(res.get("nightsCount") or (co - ci).days or 1)
        # Accommodation fare / nights is the realised nightly rate. Host payout is net
        # of channel fees and cleaning, so it is the wrong basis for a price ceiling.
        nightly = (float(fare) / nights) if fare and nights > 0 else None
        for i in range(nights):
            stay = ci + timedelta(days=i)
            conn.execute(
                """
                INSERT INTO nightly_inventory (property_id, stay_date, listed_price,
                    booked_price, status, day_of_week, channel, reservation_id, updated_at)
                VALUES (?, ?, NULL, ?, 'booked', ?, ?, ?, datetime('now'))
                ON CONFLICT(property_id, stay_date) DO UPDATE SET
                    booked_price=COALESCE(excluded.booked_price, nightly_inventory.booked_price),
                    status='booked',
                    channel=COALESCE(excluded.channel, nightly_inventory.channel),
                    reservation_id=excluded.reservation_id,
                    updated_at=datetime('now')
                """,
                (pid, stay.isoformat(), nightly, stay.weekday(),
                 res.get("source") or "guesty", res.get("_id")),
            )
            if nightly:
                report.booked_nights_priced += 1
    conn.commit()


def sync_all(conn: sqlite3.Connection, client: GuestyClient,
             horizon_days: int = 365, history_days: int = 540) -> SyncReport:
    report = SyncReport(horizon_days=horizon_days, history_days=history_days)
    today = date.today()
    listings = sync_listings(conn, client, report)
    sync_calendar(conn, client, listings,
                  today - timedelta(days=history_days),
                  today + timedelta(days=horizon_days), report)
    sync_reservations(conn, client, listings, report)
    recalibrate_bounds(conn, report)

    booked = conn.execute(
        "SELECT COUNT(*) c FROM nightly_inventory WHERE status='booked' AND booked_price IS NOT NULL"
    ).fetchone()["c"]
    if booked < 60:
        report.warnings.append(
            f"only {booked} booked nights carry a realised price — the ceiling model will "
            "lean on seasonal anchors and comps until history accumulates"
        )
    return report
