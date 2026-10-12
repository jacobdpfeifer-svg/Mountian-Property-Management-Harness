"""Guesty Open API tasks → TurnoverOutcome.

Paths from the public reference (2026-09-30), NOT yet verified against the live
tenant the way src/pms/guesty.py was:
  GET  /v1/tasks-open-api/tasks               columns (required), filters, limit, skip
  POST /v1/tasks-open-api/create-single-task  (used only by the gated task writer)

Guesty tasks carry no cost. They do carry planned duration, completion time, and
the mustFinishBefore deadline, so they supply duration and readiness lateness;
cost still comes from profiles or another source.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Iterator

from src.ops import TurnoverOutcome
from src.ops.sources import PropertyResolver
from src.ops.sources.normalize import (
    as_float,
    as_iso_date,
    as_iso_datetime,
    blank,
    first,
    minutes_between,
    service_type_for,
)

SOURCE = "guesty_tasks"
LIST_PATH = "/v1/tasks-open-api/tasks"
CREATE_PATH = "/v1/tasks-open-api/create-single-task"
COLUMNS = (
    "_id id status type taskTitle title listing listingId reservation reservationId "
    "scheduledFor startTime endTime canStartAfter mustFinishBefore completedAt "
    "plannedDuration assignee assigneeId assigneeFullName"
)
DONE = frozenset({"completed", "done", "finished"})
SKIP = frozenset({"canceled", "cancelled", "deleted"})

Getter = Callable[..., Any]


def _results(body: Any) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [r for r in body if isinstance(r, dict)]
    if isinstance(body, dict):
        for key in ("results", "data", "tasks"):
            val = body.get(key)
            if isinstance(val, list):
                return [r for r in val if isinstance(r, dict)]
    raise ValueError(f"unexpected Guesty tasks payload shape: {type(body).__name__}")


def fetch_tasks(get: Getter, start: date, end: date, *, limit: int = 25) -> Iterator[dict[str, Any]]:
    """Page through tasks and retain tasks scheduled/completed in ``[start, end]``.

    Guesty's Tasks API uses a different filter grammar from reservations, and
    flexible tasks have no ``startTime``. Client-side filtering avoids silently
    dropping those tasks while the tenant-specific filter shape is unverified.
    """
    skip = 0
    while True:
        page = _results(get(LIST_PATH, columns=COLUMNS, limit=limit, skip=skip))
        for task in page:
            stamp = first(task, "startTime", "scheduledFor.startTime", "canStartAfter",
                          "scheduledFor.canStartAfter", "mustFinishBefore",
                          "scheduledFor.mustFinishBefore", "completedAt", "endTime")
            day = as_iso_date(stamp)
            if day is not None and start.isoformat() <= day <= end.isoformat():
                yield task
        if len(page) < limit:
            break
        skip += limit


def normalize_task(task: dict[str, Any], resolver: PropertyResolver) -> TurnoverOutcome | None:
    """None for cancelled or not-yet-finished tasks; raises on an unusable shape."""
    status = str(task.get("status") or "").strip().lower()
    if status in SKIP or status not in DONE:
        return None
    task_id = first(task, "_id", "id")
    listing_id = first(task, "listingId", "listing.listingId", "listing._id", "listing.id")
    pid = resolver.resolve(listing_id, first(task, "listing.title", "listing.nickname"))
    if blank(task_id) or pid is None:
        raise ValueError(f"task {task_id!r}: unknown listing {listing_id!r}")
    fixed_start = first(task, "startTime", "scheduledFor.startTime")
    start = fixed_start or first(task, "canStartAfter", "scheduledFor.canStartAfter")
    completed = first(task, "completedAt", "endTime")
    deadline = first(task, "mustFinishBefore", "scheduledFor.mustFinishBefore")
    late = None
    if completed and deadline:
        late = minutes_between(deadline, completed)
        if late is None:  # finished before the deadline
            late = -float(minutes_between(completed, deadline) or 0.0)
    service_date = as_iso_date(start) or as_iso_date(completed)
    if service_date is None:
        raise ValueError(f"task {task_id!r}: no start or completion time")
    planned_hours = as_float(task.get("plannedDuration"))
    return TurnoverOutcome(
        property_id=pid,
        service_date=service_date,
        source=SOURCE,
        source_task_id=str(task_id),
        service_type=service_type_for(first(task, "type", "taskTitle", "title")),
        turn_id=None,
        scheduled_start=as_iso_datetime(start),
        completed_at=as_iso_datetime(completed),
        # Guesty documents plannedDuration in hours; our canonical unit is minutes.
        required_minutes=planned_hours * 60.0 if planned_hours is not None else None,
        # canStartAfter is an eligibility boundary, not an actual clock-in time.
        actual_minutes=minutes_between(fixed_start, completed) if fixed_start else None,
        cost=None,
        late_ready_minutes=late,
        assignee_ref=None if blank(first(task, "assigneeId", "assignee.assigneeId")) else str(
            first(task, "assigneeId", "assignee.assigneeId")),
        raw={"status": status, "reservation": first(task, "reservationId", "reservation._id",
                                                     "reservation.id")},
    )


def client_getter() -> Getter:
    """Bound GET on the shared Guesty client. Raises SourceUnconfigured without creds."""
    from src.ops.sources import SourceUnconfigured
    from src.pms.guesty import GuestyClient

    try:
        client = GuestyClient()
    except RuntimeError as exc:
        raise SourceUnconfigured(str(exc)) from exc
    return client._get


def create_task(post: Callable[[str, dict[str, Any]], Any], body: dict[str, Any]) -> Any:
    """One task create. Callers must hold the live-write gate (see src/ops/actions.py)."""
    if blank(body.get("title")):
        raise ValueError("Guesty task needs a title")
    return post(CREATE_PATH, body)


def client_poster() -> Callable[[str, dict[str, Any]], Any]:
    from src.ops.sources import SourceUnconfigured
    from src.pms.guesty import BASE, GuestyClient

    try:
        client = GuestyClient()
    except RuntimeError as exc:
        raise SourceUnconfigured(str(exc)) from exc

    def post(path: str, body: dict[str, Any]) -> Any:
        import requests

        resp = requests.post(f"{BASE}{path}", json=body, headers=client._headers(),
                             timeout=client.timeout)
        resp.raise_for_status()
        return resp.json()

    return post
