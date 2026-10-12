"""Breezeway API → TurnoverOutcome.

From developer.breezeway.io (2026-09-30), NOT yet verified against a live account:
  POST https://api.breezeway.io/public/auth/v1/            {client_id, client_secret}
       → access_token (24h). The token endpoint allows 1 request/minute, so the
       token is cached to disk like Guesty's.
  Header: Authorization: JWT <access_token>
  GET  https://api.breezeway.io/public/inventory/v1/property   limit, page
  GET  https://api.breezeway.io/public/inventory/v1/task/      home_id | reference_property_id,
       scheduled_date=YYYY-MM-DD,YYYY-MM-DD, type_department, limit, page
Task fields used: id, home_id, reference_property_id, name, scheduled_date,
scheduled_time, started_at, finished_at, total_time, total_cost, costs,
rate_paid, type_department, type_task_status{code,name,stage}, assignments.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterator

from src.config import ROOT
from src.ops import TurnoverOutcome
from src.ops.sources import PropertyResolver, SourceUnconfigured
from src.ops.sources.normalize import (
    as_float,
    as_iso_date,
    as_iso_datetime,
    as_minutes,
    blank,
    first,
    minutes_between,
    service_type_for,
)

SOURCE = "breezeway"
AUTH_URL = "https://api.breezeway.io/public/auth/v1/"
BASE = "https://api.breezeway.io/public/inventory/v1"
TOKEN_CACHE = Path(os.environ.get("BREEZEWAY_TOKEN_CACHE", "").strip() or ROOT / "data" / ".breezeway_token.json")
DONE_STAGES = frozenset({"finished", "completed", "closed", "approved", "done"})

Getter = Callable[..., Any]


class BreezewayClient:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None,
                 timeout: int = 30):
        from src.pms.guesty import load_dotenv

        load_dotenv()
        self.client_id = client_id or os.environ.get("BREEZEWAY_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("BREEZEWAY_CLIENT_SECRET", "")
        if not self.client_id or not self.client_secret:
            raise SourceUnconfigured("BREEZEWAY_CLIENT_ID / BREEZEWAY_CLIENT_SECRET not set")
        self.timeout = timeout
        self._token: str | None = None
        self._expires_at = 0.0

    @staticmethod
    def configured() -> bool:
        from src.pms.guesty import load_dotenv

        load_dotenv()
        return bool(os.environ.get("BREEZEWAY_CLIENT_ID") and os.environ.get("BREEZEWAY_CLIENT_SECRET"))

    def token(self) -> str:
        if self._token and time.time() < self._expires_at - 300:
            return self._token
        try:
            blob = json.loads(TOKEN_CACHE.read_text())
            if blob.get("client_id") == self.client_id and time.time() < float(blob["expires_at"]) - 300:
                self._token, self._expires_at = blob["access_token"], float(blob["expires_at"])
                return self._token
        except (OSError, ValueError, KeyError):
            pass
        import requests

        resp = requests.post(AUTH_URL, json={"client_id": self.client_id,
                                             "client_secret": self.client_secret},
                             timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise ValueError("Breezeway auth response had no access_token")
        self._token = str(token)
        self._expires_at = time.time() + 23 * 3600
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE.write_text(json.dumps({"client_id": self.client_id, "access_token": self._token,
                                           "expires_at": self._expires_at}))
        try:
            TOKEN_CACHE.chmod(0o600)
        except OSError:
            pass
        return self._token

    def get(self, path: str, **params: Any) -> Any:
        import requests

        resp = requests.get(f"{BASE}{path}", params=params or None, timeout=self.timeout,
                            headers={"Authorization": f"JWT {self.token()}",
                                     "Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()


def _pages(get: Getter, path: str, **params: Any) -> Iterator[dict[str, Any]]:
    page = 1
    while True:
        body = get(path, page=page, limit=100, **params)
        if isinstance(body, list):
            yield from (r for r in body if isinstance(r, dict))
            return
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise ValueError("unexpected Breezeway payload shape")
        yield from (r for r in body["results"] if isinstance(r, dict))
        total_pages = int(body.get("total_pages") or 1)
        if page >= total_pages or not body["results"]:
            return
        page += 1


def homes(get: Getter, resolver: PropertyResolver) -> dict[int, str]:
    """Breezeway home id → property_id, via reference_property_id (Guesty listing id) or name."""
    out: dict[int, str] = {}
    for prop in _pages(get, "/property"):
        pid = resolver.resolve(prop.get("reference_property_id"), prop.get("name"),
                               prop.get("address1"))
        if pid is not None and prop.get("id") is not None:
            out[int(prop["id"])] = pid
    return out


def fetch_tasks(get: Getter, home_ids: list[int], start: date, end: date) -> Iterator[dict[str, Any]]:
    window = f"{start.isoformat()},{end.isoformat()}"
    for home_id in home_ids:
        yield from _pages(get, "/task/", home_id=home_id, scheduled_date=window)


def _cost(task: dict[str, Any]) -> float | None:
    total = as_float(task.get("total_cost"))
    if total is not None:
        return total
    costs = task.get("costs")
    if isinstance(costs, list) and costs:
        vals: list[float] = []
        for item in costs:
            value = as_float(first(item, "cost", "amount", "total")) if isinstance(item, dict) else None
            if value is not None:
                vals.append(value)
        if vals:
            return float(sum(vals))
    return as_float(task.get("rate_paid"))


def normalize_task(task: dict[str, Any], home_map: dict[int, str],
                   resolver: PropertyResolver) -> TurnoverOutcome | None:
    stage = str(first(task, "type_task_status.stage", "type_task_status.code", "status") or "").lower()
    if stage in {"cancelled", "canceled", "deleted"}:
        return None
    finished = task.get("finished_at")
    if stage not in DONE_STAGES and blank(finished):
        return None
    pid = None
    if task.get("home_id") is not None:
        pid = home_map.get(int(task["home_id"]))
    pid = pid or resolver.resolve(task.get("reference_property_id"))
    if pid is None or blank(task.get("id")):
        raise ValueError(f"task {task.get('id')!r}: unknown home {task.get('home_id')!r}")
    started = task.get("started_at")
    actual = as_minutes(task.get("total_time"))
    if actual is None:
        actual = minutes_between(started, finished)
    dept = first(task, "type_department", "department")
    service = "inspection" if str(dept or "").lower() == "inspection" else service_type_for(
        f"{dept or ''} {task.get('name') or ''}")
    if str(dept or "").lower() == "housekeeping":
        service = "turnover"
    assignees = task.get("assignments") or []
    assignee = None
    if isinstance(assignees, list) and assignees and isinstance(assignees[0], dict):
        assignee = first(assignees[0], "assignee_id", "id", "name")
    return TurnoverOutcome(
        property_id=pid,
        service_date=as_iso_date(task.get("scheduled_date")) or as_iso_date(finished) or "",
        source=SOURCE,
        source_task_id=str(task["id"]),
        service_type=service,
        scheduled_start=as_iso_datetime(
            f"{task['scheduled_date']}T{task['scheduled_time']}" if task.get("scheduled_date")
            and task.get("scheduled_time") else task.get("scheduled_date")),
        completed_at=as_iso_datetime(finished),
        actual_minutes=actual,
        cost=_cost(task),
        assignee_ref=None if blank(assignee) else str(assignee),
        raw={"stage": stage, "department": dept},
    )
