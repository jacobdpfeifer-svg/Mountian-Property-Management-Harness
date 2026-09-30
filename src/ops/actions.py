"""Bounded incident actions. What software may suggest, and what it may never do.

Allowed actions produce drafts, lists, and task suggestions for a person. The
only external write is task creation in Guesty or Breezeway, and it needs
`--confirm-live-write` plus a production database, the same gate as `push`.

Forbidden actions raise. They are high-liability decisions that stay with a
person: cancelling or moving reservations, refunds, access codes, sending
guest messages, safety determinations, and changing availability.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ALLOWED_ACTIONS: dict[str, str] = {
    "alert_responsible_agent": "Write an alert for the responsible agent to act on",
    "move_inspection_earlier": "Suggest (or create, when gated) an earlier inspection task",
    "add_heat_check": "Suggest (or create, when gated) a heat / freeze check task",
    "add_snow_check": "Suggest (or create, when gated) a snow-removal check task",
    "draft_guest_notice": "Write factual guest-notice drafts for a person to edit and send",
    "list_stranded_and_late": "List departures that may be stranded and arrivals that may be late",
    "suggest_date_move": "List open date ranges a person could offer affected arrivals",
    "recommend_temporary_closure": "Write a closure recommendation for a person to apply in Guesty",
    "suppress_auto_price": "Hold affected nights at suggest-only (readiness at_risk for the window)",
}
TASK_ACTIONS = {
    "move_inspection_earlier": ("inspection", "Inspection moved earlier ({incident})"),
    "add_heat_check": ("maintenance", "Heat / freeze check ({incident})"),
    "add_snow_check": ("maintenance", "Snow removal check ({incident})"),
}
FORBIDDEN_ACTIONS = frozenset({
    "cancel_reservation", "move_reservation", "issue_refund", "promise_refund",
    "send_access_code", "send_guest_message", "declare_safe", "declare_unsafe",
    "close_inventory", "change_availability", "pay_vendor",
})


class ForbiddenAction(PermissionError):
    """An action this system must never take."""


class IncidentError(ValueError):
    """Unknown incident or action, or a failed gate."""


def check_action(action: str) -> None:
    if action in FORBIDDEN_ACTIONS:
        raise ForbiddenAction(
            f"{action!r} is never performed by this system; a person does it in Guesty."
        )
    if action not in ALLOWED_ACTIONS:
        raise IncidentError(f"unknown action {action!r}; allowed: {sorted(ALLOWED_ACTIONS)}")


def ops_output_dir() -> Path:
    """Private operator storage (never the repo or iCloud)."""
    from src.memory.paths import ensure_layout

    out = ensure_layout() / "ops"
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o700)
    return out


def _write(incident_id: str, action: str, payload: dict[str, Any]) -> str:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = ops_output_dir() / f"{incident_id}_{action}_{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    path.chmod(0o600)
    return str(path)


def _display_names() -> dict[str, str]:
    from src.config import load_portfolio_config

    props = load_portfolio_config().get("properties") or {}
    return {pid: str(v.get("display_name") or pid) for pid, v in props.items()}


def _open_ranges(conn: sqlite3.Connection, property_id: str, start: date, nights: int,
                 horizon: int = 60, limit: int = 3) -> list[dict[str, str]]:
    rows = conn.execute(
        """SELECT stay_date, status FROM nightly_inventory WHERE property_id=?
           AND stay_date>=? AND stay_date<? ORDER BY stay_date""",
        (property_id, start.isoformat(), (start + timedelta(days=horizon)).isoformat()),
    ).fetchall()
    free = [date.fromisoformat(str(r["stay_date"])[:10]) for r in rows if r["status"] == "available"]
    out: list[dict[str, str]] = []
    run: list[date] = []
    for d in free + [date.max]:
        if run and (d == date.max or d != run[-1] + timedelta(days=1)):
            i = 0
            while i + nights <= len(run) and len(out) < limit:
                out.append({"check_in": run[i].isoformat(),
                            "check_out": (run[i] + timedelta(days=nights)).isoformat()})
                i += nights
            run = []
        if d != date.max:
            run.append(d)
    return out


def execute(
    conn: sqlite3.Connection,
    incident: dict[str, Any],
    action: str,
    *,
    actor: str,
    live: bool = False,
    adapter: str = "dry_run",
) -> dict[str, Any]:
    """Run one approved action. Returns {'output_ref': ..., 'summary': ...}."""
    check_action(action)
    affected = incident["affected"]
    names = _display_names()
    window = f"{incident['window_start']} to {incident['window_end']}"
    iid = incident["incident_id"]

    if action == "draft_guest_notice":
        from src.ops.profiles import load_ops_policy

        template = (load_ops_policy().get("guest_notice_templates") or {}).get(incident["incident_type"])
        if not template:
            raise IncidentError(f"no approved guest-notice template for {incident['incident_type']}")
        drafts = [
            {"reservation_id": a["reservation_id"], "property_id": a["property_id"],
             "check_in": a["check_in"], "status": "DRAFT - not sent",
             "text": template.format(property=names.get(a["property_id"], a["property_id"]),
                                     window=window)}
            for a in affected.get("arrivals", [])
        ]
        ref = _write(iid, action, {"incident": iid, "drafts": drafts,
                                   "note": "Edit and send from Guesty. This system never sends messages."})
        return {"output_ref": ref, "summary": f"{len(drafts)} draft(s) written, none sent"}

    if action == "list_stranded_and_late":
        payload = {"departures_possibly_stranded": affected.get("departures", []),
                   "arrivals_possibly_late": affected.get("arrivals", []),
                   "turns_in_window": affected.get("turns", [])}
        return {"output_ref": _write(iid, action, payload),
                "summary": f"{len(payload['departures_possibly_stranded'])} departure(s), "
                           f"{len(payload['arrivals_possibly_late'])} arrival(s)"}

    if action == "suggest_date_move":
        options = []
        for a in affected.get("arrivals", []):
            nights = max(1, (date.fromisoformat(a["check_out"]) - date.fromisoformat(a["check_in"])).days)
            options.append({**a, "open_alternatives": _open_ranges(
                conn, a["property_id"], date.fromisoformat(incident["window_end"]) + timedelta(days=1), nights)})
        ref = _write(iid, action, {"options": options,
                                   "note": "Offer only with guest agreement; a person moves the reservation."})
        return {"output_ref": ref, "summary": f"alternatives for {len(options)} arrival(s)"}

    if action == "alert_responsible_agent":
        payload = {"incident": iid, "type": incident["incident_type"], "severity": incident["severity"],
                   "window": window, "signal": f"{incident['signal_key']}={incident['signal_value']}",
                   "properties": affected.get("properties", []),
                   "arrivals": len(affected.get("arrivals", [])),
                   "departures": len(affected.get("departures", [])),
                   "recommended_actions": incident.get("actions", [])}
        return {"output_ref": _write(iid, action, payload), "summary": "alert written"}

    if action == "recommend_temporary_closure":
        payload = {"incident": iid, "properties": affected.get("properties", []), "window": window,
                   "recommendation": "Consider closing these nights in Guesty until access/"
                                     "readiness is confirmed. This system does not change availability."}
        return {"output_ref": _write(iid, action, payload), "summary": "closure recommendation written"}

    if action == "suppress_auto_price":
        from src.ops import AssetEvent
        from src.ops.db import record_asset_event
        from src.ops.readiness import auto_escalate

        held = []
        for pid in affected.get("properties", []):
            event_id, _ = record_asset_event(conn, AssetEvent(
                property_id=pid, system_type="other",
                observed_at=datetime.now().replace(microsecond=0).isoformat(),
                severity="warn", source_type="manual", source_ref=f"incident:{iid}",
                effective_from=incident["window_start"], effective_to=incident["window_end"],
                reading={"incident_type": incident["incident_type"]}, verified_by=actor,
            ))
            if auto_escalate(conn, pid, event_id, actor=actor, note=f"incident {iid}",
                             effective_from=date.fromisoformat(incident["window_start"]),
                             effective_to=date.fromisoformat(incident["window_end"])):
                held.append(pid)
        conn.commit()
        return {"output_ref": None, "summary": f"at_risk (suggest-only) for {held or 'none (already restricted)'}"}

    # Task actions.
    service, title = TASK_ACTIONS[action]
    bodies = [{
        "property_id": pid,
        "title": title.format(incident=incident["incident_type"]),
        "type": service,
        "canStartAfter": f"{date.fromisoformat(incident['window_start']) - timedelta(days=1)}T08:00:00",
        "mustFinishBefore": f"{incident['window_start']}T15:00:00",
        "description": f"Incident {iid}: {incident['signal_key']}={incident['signal_value']} ({window}).",
    } for pid in affected.get("properties", [])]
    if adapter == "dry_run" or not live:
        if adapter != "dry_run" and not live:
            raise IncidentError("live task creation needs --confirm-live-write")
        return {"output_ref": _write(iid, action, {"adapter": "dry_run", "tasks": bodies}),
                "summary": f"{len(bodies)} task suggestion(s) written (dry run)"}
    return {"output_ref": _create_live_tasks(conn, iid, action, adapter, bodies),
            "summary": f"{len(bodies)} task(s) created in {adapter}"}


def _create_live_tasks(conn: sqlite3.Connection, iid: str, action: str, adapter: str,
                       bodies: list[dict[str, Any]]) -> str:
    from src.db import DB_KIND_PRODUCTION, get_db_identity

    ident = get_db_identity(conn)
    if ident.kind != DB_KIND_PRODUCTION:
        raise IncidentError(f"refusing live task write: database identity is {ident.kind!r}")
    created: list[Any] = []
    if adapter == "guesty":
        from src.ops.sources.guesty_tasks import client_poster, create_task

        post = client_poster()
        listing = {r["property_id"]: r["pms_listing_id"] for r in conn.execute(
            "SELECT property_id, pms_listing_id FROM properties").fetchall()}
        for b in bodies:
            if not listing.get(b["property_id"]):
                raise IncidentError(f"no Guesty listing id for {b['property_id']}")
            created.append(create_task(post, {
                "title": b["title"], "type": b["type"], "listingId": listing[b["property_id"]],
                "canStartAfter": b["canStartAfter"], "mustFinishBefore": b["mustFinishBefore"],
                "description": b["description"],
            }))
    elif adapter == "breezeway":
        raise IncidentError("Breezeway task creation is not enabled; its create shape is unverified. "
                            "Use --adapter dry_run and create the task in Breezeway.")
    else:
        raise IncidentError(f"unknown adapter {adapter!r}")
    return _write(iid, action, {"adapter": adapter, "created": created})
