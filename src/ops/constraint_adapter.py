"""Operations provider boundary → restrict-only night constraints (06I).

A provider (Turno, Breezeway, Guesty Tasks, …) is anything with
`fetch(start, end) -> {"tasks": [...], "constraints": [...]}` in the data-spine
contract shapes. Results go through the spine contracts, so unknown homes and
ambiguous records quarantine.

Invariant: operations data can only *restrict* a night. `effective_status`
never turns a blocked or booked night into an available one, and a vendor
outage lowers authority (readiness unknown) instead of assuming readiness.
No real provider account is connected (BLOCKED on operator credentials).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from src.data_spine.ingest import current_rows, ingest
from src.observability import SourceHealth


class OpsProvider(Protocol):
    name: str

    def fetch(self, start: date, end: date) -> dict[str, list[dict[str, Any]]]: ...


class ProviderOutage(RuntimeError):
    pass


@dataclass
class OpsImport:
    health: SourceHealth
    accepted: int = 0
    quarantined: list[dict[str, Any]] = field(default_factory=list)


def import_ops(conn: sqlite3.Connection, provider: OpsProvider, start: date, end: date,
               *, allowed_property_ids: frozenset[str]) -> OpsImport:
    try:
        payload = provider.fetch(start, end)
    except Exception as exc:
        return OpsImport(SourceHealth(f"ops:{provider.name}", "missing", required=False,
                                      detail=f"{type(exc).__name__}: {str(exc)[:120]}"))
    tasks = ingest(conn, "ops_task", payload.get("tasks", []), allowed_property_ids=allowed_property_ids)
    cons = ingest(conn, "listing_constraint", payload.get("constraints", []),
                  allowed_property_ids=allowed_property_ids)
    quarantined = tasks.quarantined + cons.quarantined
    state = "partial" if quarantined else "fresh"
    return OpsImport(SourceHealth(f"ops:{provider.name}", state, required=False,
                                  detail=f"{len(quarantined)} quarantined"),
                     len(tasks.accepted) + len(cons.accepted), quarantined)


@dataclass(frozen=True)
class NightRestriction:
    restricted: bool
    reasons: tuple[str, ...]
    readiness: str                  # ready | not_ready | unknown


def restriction_for_night(conn: sqlite3.Connection, property_id: str, stay_date: date, *,
                          provider_health: SourceHealth | None = None,
                          max_turns_per_day: int | None = None) -> NightRestriction:
    d = stay_date.isoformat()
    reasons: list[str] = []
    for c in current_rows(conn, "dim_listing_constraint",
                          "t.property_id = ? AND t.start_date <= ? AND t.end_date >= ?", (property_id, d, d)):
        if c["active"]:
            reasons.append(f"constraint:{c['constraint_type']}")
    tasks = current_rows(conn, "fact_ops_task", "t.property_id = ? AND t.service_date = ?", (property_id, d))
    for t in tasks:
        if t["task_type"] == "incident" and t["status"] not in ("completed", "cancelled"):
            reasons.append("incident_open")
        if t["task_type"] == "turn" and t["status"] == "failed":
            reasons.append("turn_incomplete")
    if max_turns_per_day is not None:
        day_turns = [t for t in current_rows(conn, "fact_ops_task", "t.service_date = ? AND t.task_type = 'turn'",
                                             (d,)) if t["status"] != "cancelled"]
        if len(day_turns) > max_turns_per_day:
            reasons.append("over_capacity")
    if provider_health is not None and provider_health.state in ("missing", "malformed", "stale"):
        readiness = "unknown"
    else:
        readiness = "not_ready" if reasons else "ready"
    return NightRestriction(bool(reasons), tuple(sorted(set(reasons))), readiness)


def effective_status(pms_status: str, restriction: NightRestriction) -> str:
    """Combine PMS availability with operations. Only ever narrows availability."""
    if pms_status != "available":
        return pms_status           # booked/blocked stay exactly as the PMS says
    return "restricted" if restriction.restricted else "available"


def authority_for(restriction: NightRestriction) -> str:
    """Highest autonomy allowed for this night given operations evidence."""
    if restriction.restricted:
        return "observe"
    if restriction.readiness == "unknown":
        return "suggest"
    return "handle"
