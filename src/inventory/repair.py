"""One-time repair for nights that were marked booked by a non-sale.

Before `src/pms/sync.py` learned `is_market_booking`, every non-cancelled Guesty
reservation (inquiries and owner stays included) was written into
`nightly_inventory` as a booked night, with the inquiry quote (or a stale earlier
fare) as `booked_price`. The daily snapshotter then copied that state into
`pacing_snapshots`, so the error is baked into history too.

A later `sync-guesty` fixes the current calendar and clears the bad
`reservation_id` link. It does not rewrite history. This repair therefore finds
contaminated nights from the reservation records themselves, not only from the
link still sitting on `nightly_inventory`.

For each night covered by a reservation that is not a market booking:

* inventory still pointing at that non-sale, and covered by a real booking →
  re-point to that booking;
* inventory still pointing at an owner stay → `blocked`, booking price cleared;
* inventory still pointing at an inquiry or other non-sale → `available`;
* a pacing row that says `booked` before a real confirmation (or with no real
  confirmation) is put back to `available`, or `blocked` for an owner stay.

A cancelled reservation is a former sale. A stale live link to it is released,
and its confirmation stamp is kept. Its historical snapshots are not treated
as inquiry contamination.

Nights a fresh sync already corrected are left alone. Non-booking reservations
also lose the `confirmed_at` that sync back-filled from `createdAt`. Every
changed value is written to `data_repairs`. Dry-run unless ``apply=True``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.pms.sync import BOOKING_STATUSES, OWNER_SOURCES, is_market_booking
from src.utils import parse_date

REPAIR_ID = "booking_contamination_v1"
# A cancellation was a sale and then wasn't. Its historical "booked" snapshots
# can be true for the days it was confirmed. Never-sold rows (inquiries,
# declines) cannot.
_CANCELLED_STATUSES = frozenset({"canceled", "cancelled"})


@dataclass
class RepairReport:
    applied: bool
    inventory_rows: int = 0
    pacing_rows: int = 0
    reservations_rows: int = 0
    by_action: dict[str, int] = field(default_factory=dict)

    def bump(self, action: str) -> None:
        self.by_action[action] = self.by_action.get(action, 0) + 1


def _ensure_log(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS data_repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_id TEXT NOT NULL,
            table_name TEXT NOT NULL,
            row_key TEXT NOT NULL,
            before_json TEXT NOT NULL,
            after_json TEXT NOT NULL,
            reason TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _is_cancelled(res: sqlite3.Row) -> bool:
    return str(res["status"] or "").lower() in _CANCELLED_STATUSES


def _is_owner_stay(res: sqlite3.Row) -> bool:
    return (
        str(res["status"] or "").lower() in BOOKING_STATUSES
        and str(res["source"] or "").lower() in OWNER_SOURCES
    )


def _stay_nights(res: sqlite3.Row) -> list[str]:
    cur, end = parse_date(res["check_in"]), parse_date(res["check_out"])
    if cur is None or end is None:
        return []
    nights: list[str] = []
    while cur < end:
        nights.append(cur.isoformat())
        cur += timedelta(days=1)
    return nights


def _market_bookings(conn: sqlite3.Connection) -> dict[tuple[str, str], sqlite3.Row]:
    """(property, night) -> earliest real booking covering it."""
    out: dict[tuple[str, str], sqlite3.Row] = {}
    for r in conn.execute(
        "SELECT * FROM reservations ORDER BY confirmed_at, reservation_id"
    ).fetchall():
        if not is_market_booking(r["status"], r["source"]):
            continue
        for night in _stay_nights(r):
            out.setdefault((r["property_id"], night), r)
    return out


def repair_booking_contamination(conn: sqlite3.Connection, *, apply: bool = False) -> RepairReport:
    report = RepairReport(applied=apply)
    if apply:
        _ensure_log(conn)

    def log(table: str, key: dict, before: dict, after: dict, reason: str) -> None:
        if apply:
            conn.execute(
                "INSERT INTO data_repairs (repair_id, table_name, row_key, before_json, "
                "after_json, reason) VALUES (?, ?, ?, ?, ?, ?)",
                (REPAIR_ID, table, json.dumps(key, sort_keys=True),
                 json.dumps(before, sort_keys=True, default=str),
                 json.dumps(after, sort_keys=True, default=str), reason),
            )

    reservations = {
        r["reservation_id"]: r for r in conn.execute("SELECT * FROM reservations").fetchall()
    }
    real = _market_bookings(conn)
    inventory = {
        (n["property_id"], n["stay_date"]): n
        for n in conn.execute(
            """
            SELECT property_id, stay_date, status, booked_price, booked_at,
                   reservation_id, channel
            FROM nightly_inventory
            """
        )
    }

    # Nights a never-sold reservation touched. Owner wins over an inquiry when
    # both cover a night and no real booking does. Cancellations are former
    # sales: a stale inventory link is cleared below, but their pacing history
    # is not rewritten just because the stay later cancelled.
    owner_nights: set[tuple[str, str]] = set()
    touched: set[tuple[str, str]] = set()
    for res in reservations.values():
        if is_market_booking(res["status"], res["source"]) or _is_cancelled(res):
            continue
        owner = _is_owner_stay(res)
        for night in _stay_nights(res):
            key = (res["property_id"], night)
            touched.add(key)
            if owner:
                owner_nights.add(key)
    for key, n in inventory.items():
        res = reservations.get(n["reservation_id"])
        if res is None or is_market_booking(res["status"], res["source"]):
            continue
        if not _is_cancelled(res):
            touched.add(key)
            if _is_owner_stay(res):
                owner_nights.add(key)

    for key in sorted(touched):
        n = inventory.get(key)
        cover = real.get(key)
        owner = key in owner_nights and cover is None
        if n is not None:
            linked = reservations.get(n["reservation_id"])
            if linked is not None and not is_market_booking(linked["status"], linked["source"]):
                before = {
                    k: n[k] for k in ("status", "booked_price", "booked_at", "reservation_id", "channel")
                }
                if cover is not None:
                    action = "repoint_to_real_booking"
                    after = {
                        "status": "booked", "booked_price": cover["nightly_rate"],
                        "booked_at": cover["confirmed_at"],
                        "reservation_id": cover["reservation_id"],
                        "channel": cover["source"],
                    }
                elif _is_owner_stay(linked):
                    action = "owner_stay_to_blocked"
                    after = {
                        "status": "blocked", "booked_price": None, "booked_at": None,
                        "reservation_id": n["reservation_id"], "channel": "owner",
                    }
                else:
                    action = "non_sale_to_available"
                    after = {
                        "status": "available", "booked_price": None, "booked_at": None,
                        "reservation_id": None, "channel": n["channel"],
                    }
                if after != before:
                    report.inventory_rows += 1
                    report.bump(action)
                    log("nightly_inventory",
                        {"property_id": key[0], "stay_date": key[1]},
                        before, after, action)
                    if apply:
                        conn.execute(
                            """
                            UPDATE nightly_inventory SET status=?, booked_price=?, booked_at=?,
                                reservation_id=?, channel=?
                            WHERE property_id=? AND stay_date=?
                            """,
                            (after["status"], after["booked_price"], after["booked_at"],
                             after["reservation_id"], after["channel"], key[0], key[1]),
                        )

        # History is independent of whether sync already fixed the live row.
        confirmed_day: date | None = (
            parse_date(cover["confirmed_at"]) if cover is not None and cover["confirmed_at"] else None
        )
        target = "blocked" if owner else "available"
        for p in conn.execute(
            """
            SELECT as_of, status FROM pacing_snapshots
            WHERE property_id=? AND stay_date=? AND status='booked'
            """,
            key,
        ).fetchall():
            if confirmed_day is not None and parse_date(p["as_of"]) >= confirmed_day:
                continue
            report.pacing_rows += 1
            reason = f"pacing_booked_to_{target}"
            report.bump(reason)
            log("pacing_snapshots",
                {"property_id": key[0], "stay_date": key[1], "as_of": p["as_of"]},
                {"status": "booked"}, {"status": target}, reason)
            if apply:
                conn.execute(
                    "UPDATE pacing_snapshots SET status=? WHERE as_of=? AND property_id=? AND stay_date=?",
                    (target, p["as_of"], key[0], key[1]),
                )

    # A cancelled stay may still be linked on the live row. Release that link
    # without rewriting the snapshots from when it was actually confirmed.
    for key, n in inventory.items():
        if key in touched:
            continue
        linked = reservations.get(n["reservation_id"])
        if linked is None or not _is_cancelled(linked):
            continue
        cover = real.get(key)
        before = {k: n[k] for k in ("status", "booked_price", "booked_at", "reservation_id", "channel")}
        if cover is not None:
            action = "repoint_to_real_booking"
            after = {
                "status": "booked", "booked_price": cover["nightly_rate"],
                "booked_at": cover["confirmed_at"], "reservation_id": cover["reservation_id"],
                "channel": cover["source"],
            }
        else:
            action = "cancelled_sale_to_available"
            after = {
                "status": "available", "booked_price": None, "booked_at": None,
                "reservation_id": None, "channel": n["channel"],
            }
        if after == before:
            continue
        report.inventory_rows += 1
        report.bump(action)
        log("nightly_inventory", {"property_id": key[0], "stay_date": key[1]}, before, after, action)
        if apply:
            conn.execute(
                """
                UPDATE nightly_inventory SET status=?, booked_price=?, booked_at=?,
                    reservation_id=?, channel=?
                WHERE property_id=? AND stay_date=?
                """,
                (after["status"], after["booked_price"], after["booked_at"],
                 after["reservation_id"], after["channel"], key[0], key[1]),
            )

    for rid, r in reservations.items():
        if is_market_booking(r["status"], r["source"]) or _is_cancelled(r) or r["confirmed_at"] is None:
            continue
        report.reservations_rows += 1
        report.bump("clear_confirmed_at_on_non_sale")
        log("reservations", {"reservation_id": rid}, {"confirmed_at": r["confirmed_at"]},
            {"confirmed_at": None}, "clear_confirmed_at_on_non_sale")
        if apply:
            conn.execute("UPDATE reservations SET confirmed_at=NULL WHERE reservation_id=?", (rid,))

    if apply:
        conn.commit()
    return report
