"""PMS adapter interface + rate writer.

The operator's system of record is Guesty. `DryRunAdapter` is the default and is the
only implementation that runs without credentials: it records every intended write to
`rate_changes` with result='dry_run' so the full push path is exercised and auditable
before a real key exists. HostawayAdapter remains an inert interface seam and is not
selectable from the CLI.
"""

from __future__ import annotations

import os
import sqlite3
import time
import math
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
    request_id: str | None = None


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
        request_id = None
        if ok and error and error.startswith("request_id="):
            request_id, error = error.split("=", 1)[1], None
        return PushResult(property_id, stay_date, None, price, ok,
                          "applied" if ok else "failed", error, request_id)


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


def _channel_price_matches(adapter: PMSAdapter, rec: Any) -> bool:
    """True when the PMS calendar already shows the recommended price.

    Used after a failed write: a timeout can mean Guesty applied the PUT but the
    client never saw 200. Matching the live listed price is the source of truth.
    """
    try:
        days = adapter.fetch_calendar(rec.property_id, rec.stay_date, rec.stay_date)
    except Exception:
        return False
    target = round(float(rec.recommended_price), 2)
    for day in days or []:
        if not isinstance(day, dict):
            continue
        raw_date = day.get("date")
        try:
            stay = date.fromisoformat(str(raw_date)[:10]) if raw_date else None
        except ValueError:
            stay = None
        if stay != rec.stay_date:
            continue
        price = day.get("price")
        if price is None:
            return False
        return abs(float(price) - target) <= 0.01
    return False


def _apply_local_inventory(
    conn: sqlite3.Connection, rec: Any, min_stay: int | None
) -> None:
    if min_stay is not None:
        conn.execute(
            "UPDATE nightly_inventory SET listed_price=?, min_stay=?, "
            "updated_at=datetime('now') WHERE property_id=? AND stay_date=?",
            (rec.recommended_price, min_stay, rec.property_id,
             rec.stay_date.isoformat()),
        )
    else:
        conn.execute(
            "UPDATE nightly_inventory SET listed_price=?, updated_at=datetime('now') "
            "WHERE property_id=? AND stay_date=?",
            (rec.recommended_price, rec.property_id, rec.stay_date.isoformat()),
        )


def push_recommendations(
    conn: sqlite3.Connection,
    recs: list[Any],
    adapter: PMSAdapter,
    autonomy_level: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Write rates for recommendations cleared to 'handle'. Every attempt is audited.

    Refuses to write anything unless the run was granted 'handle' by the data-health
    gate. Blocked/escalated recommendations are never pushed.

    Min-stay: when the recommendation carries `recommended_min_stay` and policy allows
    push (gap overrides respect `leakage.orphan_gap.push_min_stay_relaxation`; policy
    table values always push alongside the rate when present).
    """
    if autonomy_level != "handle":
        return {"attempted": 0, "applied": 0, "failed": 0,
                "skipped_autonomy": len(recs)}

    if getattr(adapter, "name", "") == "guesty":
        from src.db import DB_KIND_PRODUCTION, get_db_identity

        ident = get_db_identity(conn)
        if ident.kind != DB_KIND_PRODUCTION:
            return {
                "attempted": 0,
                "applied": 0,
                "failed": 0,
                "skipped_autonomy": len(recs),
                "refused_db_kind": ident.kind,
            }

    if policy is None:
        from src.config import load_policy
        policy = load_policy()
    push_gap = bool(
        (policy.get("leakage") or {}).get("orphan_gap", {}).get("push_min_stay_relaxation", True)
    )
    policy_min_enabled = bool((policy.get("min_stay_rules") or {}).get("enabled", False))

    counts = {"attempted": 0, "applied": 0, "failed": 0, "skipped_autonomy": 0}
    for rec in recs:
        if rec.status == "blocked" or rec.autonomy_level != "handle":
            counts["skipped_autonomy"] += 1
            continue
        min_stay = getattr(rec, "recommended_min_stay", None)
        source = getattr(rec, "min_stay_source", None)
        if min_stay is not None:
            if source == "gap_override" and not push_gap:
                min_stay = None
            elif source == "policy" and not policy_min_enabled:
                min_stay = None

        # Final write-boundary validation. Recommendations normally arrive from
        # compose(), but adapters must never become an escape hatch around the
        # safety contract. Keep the move-cap check here even if a caller bypasses
        # the normal compose path; enforce the floor for every write, while
        # allowing a gradual move that is temporarily above the model ceiling.
        candidate = float(rec.recommended_price)
        boundary_error = None
        if not math.isfinite(candidate) or candidate <= 0:
            boundary_error = "write-boundary rejected non-positive or non-finite price"
        elif candidate + 0.01 < float(rec.floor_price):
            boundary_error = (
                f"write-boundary rejected price below floor ${float(rec.floor_price):.0f}"
            )
        if boundary_error is None and rec.listed_price_at_run is not None and rec.listed_price_at_run > 0:
            g = policy.get("guardrails", {})
            listed = float(rec.listed_price_at_run)
            upper = min(listed * (1 + float(g.get("max_increase_pct", 0.12))),
                        listed + float(g.get("max_abs_move", 250)))
            lower = max(listed * (1 - float(g.get("max_decrease_pct", 0.15))),
                        listed - float(g.get("max_abs_move", 250)))
            if not (lower - 0.01 <= candidate <= upper + 0.01):
                boundary_error = "write-boundary guardrail rejected candidate"
        if boundary_error is not None:
            rec_id = conn.execute(
                "SELECT id FROM price_recommendations WHERE run_id=? AND property_id=? AND stay_date=?",
                (rec.run_id, rec.property_id, rec.stay_date.isoformat()),
            ).fetchone()
            conn.execute(
                """INSERT INTO rate_changes (
                    recommendation_id, property_id, stay_date, old_price, new_price,
                    actor, autonomy_level, result, error, rule_version, model_version,
                    inputs_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?, ?, ?)""",
                (rec_id["id"] if rec_id else None, rec.property_id,
                 rec.stay_date.isoformat(), rec.listed_price_at_run,
                 rec.recommended_price, adapter.name, autonomy_level,
                 boundary_error, rec.rule_version,
                 rec.model_version, rec.inputs_hash),
            )
            counts["skipped_autonomy"] += 1
            continue
        counts["attempted"] += 1
        try:
            res = adapter.push_rate(
                rec.property_id, rec.stay_date, rec.recommended_price, min_stay=min_stay
            )
        except Exception as exc:  # adapter failures must become audit rows
            res = PushResult(rec.property_id, rec.stay_date, rec.listed_price_at_run,
                             rec.recommended_price, False, "failed",
                             f"{type(exc).__name__}: {str(exc)[:300]}")
        rec_id = conn.execute(
            "SELECT id FROM price_recommendations WHERE run_id=? AND property_id=? AND stay_date=?",
            (rec.run_id, rec.property_id, rec.stay_date.isoformat()),
        ).fetchone()
        result = res.result
        error = res.error
        if result == "failed" and _channel_price_matches(adapter, rec):
            result = "applied"
            prior = error or "write reported failure"
            error = f"reconciled after write failure ({prior})"
            res = PushResult(
                rec.property_id, rec.stay_date, rec.listed_price_at_run,
                rec.recommended_price, True, "applied", error,
                getattr(res, "request_id", None),
            )
        conn.execute(
            """
            INSERT INTO rate_changes (recommendation_id, property_id, stay_date,
                old_price, new_price, actor, autonomy_level, result, error,
                rule_version, model_version, inputs_hash, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (rec_id["id"] if rec_id else None, rec.property_id, rec.stay_date.isoformat(),
             rec.listed_price_at_run, rec.recommended_price, adapter.name,
             autonomy_level, result, error,
             rec.rule_version, rec.model_version, rec.inputs_hash,
             getattr(res, "request_id", None)),
        )
        if result == "applied":
            counts["applied"] += 1
            _apply_local_inventory(conn, rec, min_stay)
        elif result == "failed":
            counts["failed"] += 1
    conn.commit()
    return counts
