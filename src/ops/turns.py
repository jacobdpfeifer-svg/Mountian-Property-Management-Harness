"""Turns: the unit of operational work is a stay transition, not a calendar night.

    turn_id = property_id | departing_reservation | arriving_reservation

A turn is serviced on the departing checkout date. Its slack is the time between
checkout and the next check-in, less predicted work, travel, and a weather
buffer read point-in-time from signal_observations.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from src.ops import OpsProfile
from src.ops.profiles import minutes_of_day
from src.utils import parse_date

# Guesty statuses that put people in the house. Owner stays need a turn too, so
# the owner-source exclusion used for market bookings does not apply here.
OCCUPYING_STATUSES = ("confirmed", "checked_in", "checked_out")
OPEN_ARRIVAL = "open"


@dataclass(frozen=True)
class Stay:
    reservation_id: str
    property_id: str
    check_in: date
    check_out: date
    source: str | None
    fare_accommodation: float | None


@dataclass
class Turn:
    turn_id: str
    property_id: str
    service_date: date
    departing_reservation: str
    arriving_reservation: str | None
    gap_nights: int | None
    same_day: bool
    snow_expected: bool
    predicted_worker_minutes: float
    predicted_elapsed_minutes: float
    travel_minutes: float
    weather_buffer_minutes: float
    slack_minutes: float | None
    buffer_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "property_id": self.property_id,
            "service_date": self.service_date.isoformat(),
            "departing": self.departing_reservation,
            "arriving": self.arriving_reservation,
            "gap_nights": self.gap_nights,
            "same_day": self.same_day,
            "snow_expected": self.snow_expected,
            "worker_minutes": round(self.predicted_worker_minutes, 1),
            "elapsed_minutes": round(self.predicted_elapsed_minutes, 1),
            "travel_minutes": self.travel_minutes,
            "weather_buffer_minutes": self.weather_buffer_minutes,
            "slack_minutes": None if self.slack_minutes is None else round(self.slack_minutes, 1),
            "buffer_reasons": list(self.buffer_reasons),
        }


def make_turn_id(property_id: str, departing: str, arriving: str | None) -> str:
    return f"{property_id}|{departing}|{arriving or OPEN_ARRIVAL}"


def load_stays(
    conn: sqlite3.Connection,
    property_id: str,
    start: date | None = None,
    end: date | None = None,
    *,
    as_of: date | None = None,
) -> list[Stay]:
    """Occupying reservations whose checkout falls in [start - 60d, end + 60d]."""
    clauses = ["property_id = ?", f"LOWER(status) IN ({','.join('?' * len(OCCUPYING_STATUSES))})"]
    params: list[Any] = [property_id, *OCCUPYING_STATUSES]
    if start is not None:
        clauses.append("check_out >= ?")
        params.append((start - timedelta(days=60)).isoformat())
    if end is not None:
        clauses.append("check_in <= ?")
        params.append((end + timedelta(days=60)).isoformat())
    if as_of is not None:
        clauses.append(
            "COALESCE(substr(confirmed_at,1,10), substr(first_seen_at,1,10)) <= ?"
        )
        params.append(as_of.isoformat())
    rows = conn.execute(
        "SELECT reservation_id, property_id, check_in, check_out, source, fare_accommodation "
        f"FROM reservations WHERE {' AND '.join(clauses)} ORDER BY check_in, check_out",
        params,
    ).fetchall()
    return [
        Stay(
            reservation_id=str(r["reservation_id"]),
            property_id=str(r["property_id"]),
            check_in=parse_date(r["check_in"]),
            check_out=parse_date(r["check_out"]),
            source=r["source"],
            fare_accommodation=r["fare_accommodation"],
        )
        for r in rows
    ]


def market_for(conn: sqlite3.Connection, property_id: str) -> str:
    try:
        row = conn.execute(
            "SELECT market_id FROM properties WHERE property_id = ?", (property_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    return str(row["market_id"]) if row and row["market_id"] else "grand_home"


def _crosses(value: float, op: str, threshold: float) -> bool:
    if op == ">=":
        return value >= threshold
    if op == "<=":
        return value <= threshold
    if op == ">":
        return value > threshold
    if op == "<":
        return value < threshold
    raise ValueError(f"unsupported op {op!r}")


def signal_value(
    conn: sqlite3.Connection, signal_key: str, market_id: str, effective: date, as_of: date
) -> float | None:
    """Latest ok observation for (signal, market, effective date) known by as_of."""
    try:
        row = conn.execute(
            """SELECT value FROM signal_observations
               WHERE signal_key=? AND market_id=? AND effective_date=? AND observed_at<=?
                 AND quality='ok' AND value IS NOT NULL
               ORDER BY observed_at DESC, horizon_days ASC LIMIT 1""",
            (signal_key, market_id, effective.isoformat(), as_of.isoformat()),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return None if row is None else float(row["value"])


def weather_buffer(
    conn: sqlite3.Connection,
    market_id: str,
    service_date: date,
    as_of: date,
    ops_policy: dict[str, Any],
) -> tuple[float, bool, list[str]]:
    """(buffer minutes, snow expected, reasons). Never reads beyond as_of."""
    minutes = 0.0
    reasons: list[str] = []
    for rule in (ops_policy.get("slack") or {}).get("weather_buffers") or []:
        val = signal_value(conn, rule["signal_key"], market_id, service_date, as_of)
        if val is None:
            continue
        if _crosses(val, rule.get("op", ">="), float(rule["threshold"])):
            minutes += float(rule["minutes"])
            reasons.append(f"{rule['signal_key']}={val:g}")
    snow_cm = float((ops_policy.get("economics") or {}).get("snow_clearance_cm", 5))
    snowfall = signal_value(conn, "weather.snowfall_sum_cm", market_id, service_date, as_of)
    return minutes, bool(snowfall is not None and snowfall >= snow_cm), reasons


def build_turn(
    profile: OpsProfile,
    *,
    service_date: date,
    departing: str,
    arriving: str | None,
    gap_nights: int | None,
    buffer_minutes: float = 0.0,
    snow: bool = False,
    reasons: list[str] | None = None,
) -> Turn:
    worker = profile.worker_minutes(snow=snow)
    elapsed = profile.elapsed_minutes(snow=snow)
    slack: float | None = None
    if gap_nights is not None:
        window = (
            gap_nights * 1440
            + minutes_of_day(profile.checkin_time)
            - minutes_of_day(profile.checkout_time)
        )
        slack = window - elapsed - profile.travel_minutes - buffer_minutes
    return Turn(
        turn_id=make_turn_id(profile.property_id, departing, arriving),
        property_id=profile.property_id,
        service_date=service_date,
        departing_reservation=departing,
        arriving_reservation=arriving,
        gap_nights=gap_nights,
        same_day=gap_nights == 0,
        snow_expected=snow,
        predicted_worker_minutes=worker,
        predicted_elapsed_minutes=elapsed,
        travel_minutes=float(profile.travel_minutes),
        weather_buffer_minutes=buffer_minutes,
        slack_minutes=slack,
        buffer_reasons=list(reasons or []),
    )


def derive_turns(
    conn: sqlite3.Connection,
    profile: OpsProfile,
    start: date,
    end: date,
    *,
    as_of: date,
    ops_policy: dict[str, Any],
    point_in_time_reservations: bool = True,
) -> list[Turn]:
    """Turns whose service date falls in [start, end]."""
    stays = load_stays(
        conn, profile.property_id, start, end,
        as_of=as_of if point_in_time_reservations else None,
    )
    market = market_for(conn, profile.property_id)
    turns: list[Turn] = []
    for i, dep in enumerate(stays):
        if not (start <= dep.check_out <= end):
            continue
        nxt = next((s for s in stays[i + 1:] if s.check_in >= dep.check_out), None)
        gap = None if nxt is None else (nxt.check_in - dep.check_out).days
        buf, snow, reasons = weather_buffer(conn, market, dep.check_out, as_of, ops_policy)
        turns.append(build_turn(
            profile,
            service_date=dep.check_out,
            departing=dep.reservation_id,
            arriving=nxt.reservation_id if nxt else None,
            gap_nights=gap,
            buffer_minutes=buf,
            snow=snow,
            reasons=reasons,
        ))
    return turns
