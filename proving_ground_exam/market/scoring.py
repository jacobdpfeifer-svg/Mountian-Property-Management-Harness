"""Realized-revenue scoring. The examiner does not import the engine."""

from __future__ import annotations

import itertools
import sqlite3
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from proving_ground_exam.market.choice import stay_nights
from proving_ground_exam.market.parameters import season_of, stay_fees, value_of
from proving_ground_exam.market.shoppers import Shopper


def _parse(value: str) -> date:
    return date.fromisoformat(value[:10])


def stay_economics(
    room_revenue: float,
    *,
    nights: int,
    party: int,
    channel: str | None,
    guest_fees: dict[str, Any] | None,
    economics: dict[str, Any],
) -> dict[str, float]:
    """Owner net and manager income for one confirmed stay.

    Guests pay the room plus fees (cleaning per stay, consumables per guest,
    insurance per stay). The channel takes its commission on everything the
    guest pays (Airbnb's host-only fee is charged on the full total). The
    management fee is charged on room revenue. Turnover cleaning, consumables
    and insurance are real costs the fees are meant to cover. Every rate is a
    calibration value with a source and a sweep.
    """
    fees = stay_fees(guest_fees, party)
    guest_paid = room_revenue + fees
    channel_fees = economics.get("channel_fee") or {}
    rate = value_of(channel_fees.get(channel or "", channel_fees.get("default", 0.0)))
    mgmt = value_of(economics["management_fee"]) * room_revenue
    costs = (
        value_of(economics.get("turnover_cost_per_stay", 0.0))
        + value_of(economics.get("consumables_cost_per_guest", 0.0)) * party
        + value_of(economics.get("insurance_cost_per_stay", 0.0))
    )
    return {
        "guest_paid": guest_paid,
        "channel_fee": rate * guest_paid,
        "management_fee": mgmt,
        "stay_costs": costs,
        "owner_net": guest_paid - rate * guest_paid - mgmt - costs,
    }


def realized(
    conn: sqlite3.Connection,
    properties: list[str],
    *,
    economics: dict[str, Any] | None = None,
    guest_fees: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT property_id, check_in, nights, status, nightly_rate, created_at_pms, guest_count,
               source
        FROM reservations
        WHERE property_id IN ({})
        """.format(",".join("?" * len(properties))),
        properties,
    ).fetchall()
    # Booked prices live on the calendar, which is the price at acceptance.
    revenue = 0.0
    booked_nights = 0
    leads = []
    los = []
    confirmed = 0
    inquiries = 0
    money: dict[str, float] = {
        "guest_paid": 0.0, "channel_fee": 0.0, "management_fee": 0.0,
        "stay_costs": 0.0, "owner_net": 0.0,
    }
    for row in rows:
        if row["status"] == "inquiry":
            inquiries += 1
            continue
        if row["status"] != "confirmed":
            continue
        confirmed += 1
        nights = int(row["nights"] or 0)
        los.append(nights)
        prices = conn.execute(
            """
            SELECT booked_price FROM nightly_inventory
            WHERE property_id = ? AND reservation_id IN (
                SELECT reservation_id FROM reservations
                WHERE property_id = ? AND check_in = ? AND status = 'confirmed'
            )
            """,
            (row["property_id"], row["property_id"], row["check_in"]),
        ).fetchall()
        # Simpler: sum booked_price for this stay via check-in span.
        check_in = _parse(row["check_in"])
        stay_rev = 0.0
        counted = 0
        for offset in range(nights):
            night = check_in + timedelta(days=offset)
            price_row = conn.execute(
                """
                SELECT booked_price, status FROM nightly_inventory
                WHERE property_id = ? AND stay_date = ?
                """,
                (row["property_id"], night.isoformat()),
            ).fetchone()
            if price_row and price_row["status"] == "booked" and price_row["booked_price"]:
                stay_rev += float(price_row["booked_price"])
                counted += 1
        revenue += stay_rev
        booked_nights += counted
        if economics is not None and counted:
            for key, value in stay_economics(
                stay_rev, nights=counted, party=int(row["guest_count"] or 0),
                channel=row["source"], guest_fees=guest_fees, economics=economics,
            ).items():
                money[key] += value
        if row["created_at_pms"]:
            leads.append((check_in - _parse(row["created_at_pms"])).days)
    inventory = conn.execute(
        """
        SELECT property_id, stay_date, status FROM nightly_inventory
        WHERE property_id IN ({})
        ORDER BY property_id, stay_date
        """.format(",".join("?" * len(properties))),
        properties,
    ).fetchall()
    total_nights = len(inventory) or 1
    by_prop: dict[str, list[sqlite3.Row]] = {}
    peak_booked = peak_total = early_booked = early_total = 0
    for row in inventory:
        by_prop.setdefault(row["property_id"], []).append(row)
        season = season_of(_parse(row["stay_date"]))
        if season == "peak_ski":
            peak_total += 1
            peak_booked += int(row["status"] == "booked")
        elif season == "early_winter":
            early_total += 1
            early_booked += int(row["status"] == "booked")
    orphans = 0
    for rows_p in by_prop.values():
        for i, row in enumerate(rows_p):
            if row["status"] != "available" or i == 0 or i == len(rows_p) - 1:
                continue
            if rows_p[i - 1]["status"] == "booked" and rows_p[i + 1]["status"] == "booked":
                orphans += 1
    guardrails = conn.execute(
        """
        SELECT COUNT(*) AS c FROM price_recommendations
        WHERE guardrail_action IS NOT NULL AND guardrail_action != ''
        """
    ).fetchone()
    by_action = {
        row["guardrail_action"]: int(row["c"])
        for row in conn.execute(
            """
            SELECT COALESCE(guardrail_action, '') AS guardrail_action, COUNT(*) AS c
            FROM price_recommendations
            GROUP BY 1
            """
        )
    }
    scores: dict[str, Any] = {
        "revenue": round(revenue, 2),
        "revpan": round(revenue / total_nights, 4),
        "occupancy": round(booked_nights / total_nights, 4),
        "adr": round(revenue / booked_nights, 2) if booked_nights else 0.0,
        "lead_le_21": round(sum(1 for lead in leads if lead <= 21) / len(leads), 4) if leads else 0.0,
        "los_mean": round(sum(los) / len(los), 4) if los else 0.0,
        "inquiry_per_confirmed": round(inquiries / confirmed, 4) if confirmed else 0.0,
        "orphan_nights": orphans,
        "guardrail_triggers": int(guardrails["c"] if guardrails else 0),
        "guardrail_by_action": by_action,
        "confirmed": confirmed,
        "inquiries": inquiries,
        "occupancy_peak": round(peak_booked / peak_total, 4) if peak_total else 0.0,
        "occupancy_early": round(early_booked / early_total, 4) if early_total else 0.0,
    }
    if economics is not None:
        # v2 only: v1 score dicts (and so their content hashes) are unchanged.
        scores["owner_net"] = round(money["owner_net"], 2)
        scores["pm_fee_income"] = round(money["management_fee"], 2)
        scores["guest_paid"] = round(money["guest_paid"], 2)
        scores["channel_fees"] = round(money["channel_fee"], 2)
        scores["stay_costs"] = round(money["stay_costs"], 2)
    return scores


def hindsight_revenue(
    shoppers: list[Shopper],
    properties: dict[str, Any],
    season_start: date,
    season_end: date,
    median: float | Callable[[date], float],
) -> tuple[float, float | None]:
    """Greedy upper bound: charge willingness to pay, ignore competitors.

    ``median`` is the v1 single market median, or (v2) a function giving each
    night's market reference.

    Returns (greedy revenue, optimality gap on a 6-shopper subset or None).
    The gap is (brute - greedy) / brute on that subset. It is not a bound on
    the full-season gap.
    """
    sleeps = {prop: int(meta["sleeps"]) for prop, meta in properties.items()}
    season = set()
    day = season_start
    while day <= season_end:
        season.add(day)
        day += timedelta(days=1)

    def fits(shopper: Shopper) -> list[date] | None:
        nights = stay_nights(shopper.check_in, shopper.los)
        if any(night not in season for night in nights):
            return None
        return nights

    def charge(shopper: Shopper, nights: list[date]) -> float:
        if callable(median):
            return shopper.wtp_multiplier * sum(median(night) for night in nights)
        return shopper.wtp_multiplier * median * len(nights)

    eligible = [(shopper, nights) for shopper in shoppers if (nights := fits(shopper))]
    eligible.sort(key=lambda item: -item[0].wtp_multiplier * item[0].los)

    def assign(order: list[tuple[Shopper, list[date]]]) -> float:
        free = {prop: set(season) for prop in sleeps}
        revenue = 0.0
        for shopper, nights in order:
            options = [
                prop for prop, cap in sleeps.items()
                if shopper.party <= cap and all(night in free[prop] for night in nights)
            ]
            if not options:
                continue
            revenue += charge(shopper, nights)
            for night in nights:
                free[options[0]].discard(night)
        return revenue

    greedy = assign(eligible)
    subset = eligible[:6]
    if len(subset) < 2:
        return round(greedy, 2), None
    ids = list(sleeps) + [None]
    best = 0.0
    # Brute force is only a gap diagnostic on the subset, using the same charge.
    for assignment in itertools.product(ids, repeat=len(subset)):
        free = {prop: set(season) for prop in sleeps}
        revenue = 0.0
        ok = True
        for choice, (shopper, nights) in zip(assignment, subset, strict=True):
            if choice is None:
                continue
            if shopper.party > sleeps[choice] or any(night not in free[choice] for night in nights):
                ok = False
                break
            revenue += charge(shopper, nights)
            for night in nights:
                free[choice].discard(night)
        if ok:
            best = max(best, revenue)
    gap = (best - assign(subset)) / best if best else 0.0
    return round(greedy, 2), round(gap, 4)
