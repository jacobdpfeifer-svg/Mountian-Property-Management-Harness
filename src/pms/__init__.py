"""PMS adapter interface + rate writer.

The operator's system of record is Guesty or Hostaway (vendor still to be confirmed;
see docs/LOCKED_INPUTS.md). The v1 build assumed CSV/iCal exports and shipped only an
`IngestAdapter` ABC with two abstract read methods — no write path at all, despite
auto-push being the chosen authority model.

Both vendors expose reservations, listings, calendar and rate write-back over REST, so
the interface below is vendor-neutral. `DryRunAdapter` is the default and is the only
implementation that runs without credentials: it records every intended write to
`rate_changes` with result='dry_run' so the full push path is exercised and auditable
before a real key exists.
"""

from __future__ import annotations

import os
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class PushResult:
    property_id: str
    stay_date: date
    old_price: float | None
    new_price: float
    ok: bool
    result: str          # applied | failed | dry_run
    error: str | None = None


class PMSAdapter(ABC):
    """Vendor-neutral PMS contract."""

    name: str = "abstract"

    @abstractmethod
    def fetch_calendar(self, property_id: str, start: date, end: date) -> list[dict[str, Any]]: ...

    @abstractmethod
    def push_rate(self, property_id: str, stay_date: date, price: float,
                  min_stay: int | None = None) -> PushResult: ...


class DryRunAdapter(PMSAdapter):
    """Exercises the full write path without touching a channel."""

    name = "dry_run"

    def fetch_calendar(self, property_id: str, start: date, end: date) -> list[dict[str, Any]]:
        return []

    def push_rate(self, property_id: str, stay_date: date, price: float,
                  min_stay: int | None = None) -> PushResult:
        return PushResult(property_id, stay_date, None, price, True, "dry_run")


class GuestyAdapter(PMSAdapter):
    """Guesty rate writer — delegates to the verified client in src/pms/guesty.py.

    Credentials come from .env (GUESTY_CLIENT_ID / GUESTY_CLIENT_SECRET). The
    property_id -> Guesty listing id map is read from properties.pms_listing_id,
    which `wp-price sync-guesty` populates, so nothing has to be configured by hand.
    """

    name = "guesty"

    def __init__(self, conn: sqlite3.Connection | None = None, **kwargs: Any) -> None:
        from src.pms.guesty import GuestyClient

        self.client = GuestyClient(**kwargs)
        self.listing_map: dict[str, str] = {}
        if conn is not None:
            self.load_map(conn)

    def load_map(self, conn: sqlite3.Connection) -> None:
        self.listing_map = {
            r["property_id"]: r["pms_listing_id"]
            for r in conn.execute(
                "SELECT property_id, pms_listing_id FROM properties "
                "WHERE pms_listing_id IS NOT NULL"
            ).fetchall()
        }

    def _listing_id(self, property_id: str) -> str:
        listing_id = self.listing_map.get(property_id)
        if not listing_id:
            raise KeyError(
                f"No Guesty listing id for '{property_id}'. Run `wp-price sync-guesty`."
            )
        return listing_id

    def fetch_calendar(self, property_id: str, start: date, end: date) -> list[dict[str, Any]]:
        return self.client.calendar(self._listing_id(property_id), start, end)

    def push_rate(self, property_id: str, stay_date: date, price: float,
                  min_stay: int | None = None) -> PushResult:
        try:
            listing_id = self._listing_id(property_id)
        except KeyError as exc:
            return PushResult(property_id, stay_date, None, price, False, "failed", str(exc))
        ok, error = self.client.set_rate(listing_id, stay_date, price, min_stay)
        return PushResult(property_id, stay_date, None, price, ok,
                          "applied" if ok else "failed", error)


class HostawayAdapter(PMSAdapter):
    """Hostaway Public API. Not implemented — the operator confirmed Guesty.

    Retained so the interface stays demonstrably vendor-neutral and a future migration
    is a new class rather than a rewrite of the pricing layer.
    """

    name = "hostaway"

    def __init__(self, *_: Any, **__: Any) -> None:
        raise NotImplementedError(
            "Operator is on Guesty; HostawayAdapter is intentionally unimplemented."
        )

    def fetch_calendar(self, property_id: str, start: date, end: date) -> list[dict[str, Any]]:
        raise NotImplementedError

    def push_rate(self, property_id: str, stay_date: date, price: float,
                  min_stay: int | None = None) -> PushResult:
        raise NotImplementedError


ADAPTERS = {"dry_run": DryRunAdapter, "guesty": GuestyAdapter, "hostaway": HostawayAdapter}


def push_recommendations(
    conn: sqlite3.Connection,
    recs: list[Any],
    adapter: PMSAdapter,
    autonomy_level: str,
) -> dict[str, int]:
    """Write rates for recommendations cleared to 'handle'. Every attempt is audited.

    Refuses to write anything unless the run was granted 'handle' by the data-health
    gate. Blocked/escalated recommendations are never pushed.
    """
    if autonomy_level != "handle":
        return {"attempted": 0, "applied": 0, "failed": 0,
                "skipped_autonomy": len(recs)}

    counts = {"attempted": 0, "applied": 0, "failed": 0, "skipped_autonomy": 0}
    for rec in recs:
        if rec.status == "blocked" or rec.autonomy_level != "handle":
            counts["skipped_autonomy"] += 1
            continue
        counts["attempted"] += 1
        res = adapter.push_rate(rec.property_id, rec.stay_date, rec.recommended_price)
        rec_id = conn.execute(
            "SELECT id FROM price_recommendations WHERE run_id=? AND property_id=? AND stay_date=?",
            (rec.run_id, rec.property_id, rec.stay_date.isoformat()),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO rate_changes (recommendation_id, property_id, stay_date,
                old_price, new_price, actor, autonomy_level, result, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (rec_id["id"] if rec_id else None, rec.property_id, rec.stay_date.isoformat(),
             rec.listed_price_at_run, rec.recommended_price, adapter.name,
             autonomy_level, res.result, res.error),
        )
        if res.result == "applied":
            counts["applied"] += 1
            conn.execute(
                "UPDATE nightly_inventory SET listed_price=?, updated_at=datetime('now') "
                "WHERE property_id=? AND stay_date=?",
                (rec.recommended_price, rec.property_id, rec.stay_date.isoformat()),
            )
        elif res.result == "failed":
            counts["failed"] += 1
    conn.commit()
    return counts
