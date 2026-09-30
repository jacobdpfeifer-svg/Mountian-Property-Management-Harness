"""Turno (formerly TurnoverBnB) External API v2 → TurnoverOutcome.

Turno grants API access to partners on request; there is no self-serve key.
The public index (apidocs.turnoverbnb.com) describes GET /v2/projects and
GET /v2/projects/{id} with bearer auth plus a partner id header, filterable by
property, cleaner, and date range. The exact base URL, header name, query
parameter names, and field names could not be read from the public page, so all
of them are configurable and the normalizer accepts several spellings.
UNVERIFIED — once access is granted, pin the real shape here and in the tests.

Env: TURNO_API_TOKEN (required), TURNO_PARTNER_ID, TURNO_API_BASE,
     TURNO_PARTNER_HEADER (default "X-Partner-Id").
Without API access, use the CSV path: wp-price ops import --source csv --preset turno.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Callable, Iterator

from src.ops import TurnoverOutcome
from src.ops.sources import PropertyResolver, SourceUnconfigured
from src.ops.sources.normalize import (
    CANCELLED,
    as_float,
    as_iso_date,
    as_iso_datetime,
    as_minutes,
    blank,
    first,
    minutes_between,
    service_type_for,
)

SOURCE = "turno"
DEFAULT_BASE = "https://api.turnoverbnb.com/v2"
DONE = frozenset({"completed", "finished", "done", "approved", "paid"})

Getter = Callable[..., Any]


class TurnoClient:
    def __init__(self, timeout: int = 30):
        from src.pms.guesty import load_dotenv

        load_dotenv()
        self.token = os.environ.get("TURNO_API_TOKEN", "")
        if not self.token:
            raise SourceUnconfigured("TURNO_API_TOKEN not set (Turno grants API access on request)")
        self.base = os.environ.get("TURNO_API_BASE", DEFAULT_BASE).rstrip("/")
        self.partner_id = os.environ.get("TURNO_PARTNER_ID", "")
        self.partner_header = os.environ.get("TURNO_PARTNER_HEADER", "X-Partner-Id")
        self.timeout = timeout

    @staticmethod
    def configured() -> bool:
        from src.pms.guesty import load_dotenv

        load_dotenv()
        return bool(os.environ.get("TURNO_API_TOKEN"))

    def get(self, path: str, **params: Any) -> Any:
        import requests

        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if self.partner_id:
            headers[self.partner_header] = self.partner_id
        resp = requests.get(f"{self.base}{path}", params=params or None, headers=headers,
                            timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


def fetch_projects(get: Getter, start: date, end: date) -> Iterator[dict[str, Any]]:
    page = 1
    while True:
        body = get("/projects", start_date=start.isoformat(), end_date=end.isoformat(), page=page)
        if isinstance(body, list):
            yield from (r for r in body if isinstance(r, dict))
            return
        rows = first(body, "data", "results", "projects") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            raise ValueError("unexpected Turno payload shape")
        yield from (r for r in rows if isinstance(r, dict))
        last = first(body, "meta.last_page", "last_page", "total_pages")
        if not rows or last is None or page >= int(last):
            return
        page += 1


def normalize_project(p: dict[str, Any], resolver: PropertyResolver) -> TurnoverOutcome | None:
    status = str(first(p, "status", "state") or "").strip().lower()
    if status in CANCELLED:
        return None
    completed = first(p, "completed_at", "finished_at", "end_time", "checkout_time")
    if status not in DONE and blank(completed):
        return None
    pid = resolver.resolve(
        first(p, "property.external_id", "property.external_reference", "property_external_id"),
        first(p, "property.name", "property_name", "property.nickname"),
        first(p, "property.address", "property.address1", "property_address"),
    )
    pid_ref = first(p, "id", "project_id", "uuid")
    if pid is None or blank(pid_ref):
        raise ValueError(f"project {pid_ref!r}: unknown property")
    started = first(p, "started_at", "start_time", "checkin_time")
    actual = as_minutes(first(p, "duration", "duration_minutes", "time_spent"))
    if actual is None:
        actual = minutes_between(started, completed)
    cleaner = first(p, "cleaner.id", "cleaner_id", "cleaner.name", "cleaner_name")
    return TurnoverOutcome(
        property_id=pid,
        service_date=as_iso_date(first(p, "date", "project_date", "scheduled_date"))
        or as_iso_date(completed) or "",
        source=SOURCE,
        source_task_id=str(pid_ref),
        service_type=service_type_for(first(p, "service.name", "service_name", "type") or "cleaning"),
        scheduled_start=as_iso_datetime(first(p, "scheduled_start", "start_date")),
        completed_at=as_iso_datetime(completed),
        actual_minutes=actual,
        cost=as_float(first(p, "price", "total", "amount", "total_price", "payment.amount")),
        qa_pass=None,
        assignee_ref=None if blank(cleaner) else str(cleaner),
        raw={"status": status},
    )
