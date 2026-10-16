"""Daily decision review: queue, attributable actions, exportable receipts (06J).

The review surface records what a person decided. It never writes a rate: the
`applied` column in an export comes only from the spine's price decisions,
which only the (inactive) canary controller may populate.

Roles: `approver` may approve/reject/edit; `viewer` may read. Each item takes
exactly one terminal action, before it expires. Actions are hash-chained, so a
removed or reordered receipt is detectable.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROLES = {"approver": {"approve", "reject", "edit"}, "viewer": set()}
GENESIS = "0" * 64


class ReviewRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewItem:
    decision_key: str
    property_id: str
    stay_date: str
    current_rate: float | None
    proposed_rate: float
    all_in_price: float | None
    expected_owner_net: float | None
    owner_net_basis: str
    freshness: dict[str, str]
    confidence: float | None
    reasons: list[str]
    guardrails: list[str]
    readiness: str
    assignment_arm: str
    expires_at: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(conn: sqlite3.Connection, item: ReviewItem, *, scope_property_ids: frozenset[str]) -> int:
    if item.property_id not in scope_property_ids:
        from src.security.scope import quarantine
        quarantine(conn, boundary="review", property_id=item.property_id, listing_id=None,
                   reason="unknown_property")
        raise ReviewRefused(f"{item.property_id} is outside the portfolio")
    if item.owner_net_basis not in ("actual_terms", "assumed_terms", "unavailable"):
        raise ReviewRefused("owner_net_basis must say whether terms are actual or assumed")
    with conn:
        cur = conn.execute(
            """INSERT INTO review_item (decision_key, property_id, stay_date, current_rate, proposed_rate,
                   all_in_price, expected_owner_net, owner_net_basis, freshness_json, confidence,
                   reasons_json, guardrails_json, readiness, assignment_arm, expires_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item.decision_key, item.property_id, item.stay_date, item.current_rate, item.proposed_rate,
             item.all_in_price, item.expected_owner_net, item.owner_net_basis,
             json.dumps(item.freshness, sort_keys=True), item.confidence, json.dumps(item.reasons),
             json.dumps(item.guardrails), item.readiness, item.assignment_arm, item.expires_at,
             _now().isoformat(timespec="seconds")))
    return int(cur.lastrowid or 0)


def act(conn: sqlite3.Connection, item_id: int, *, action: str, actor: str, role: str, reason: str,
        edited_price: float | None = None, now: datetime | None = None) -> dict[str, Any]:
    if role not in ROLES or action not in ROLES[role]:
        raise ReviewRefused(f"role {role!r} may not {action!r}")
    if not actor.strip() or not reason.strip():
        raise ReviewRefused("actor and reason are required")
    item = conn.execute("SELECT * FROM review_item WHERE id=?", (item_id,)).fetchone()
    if item is None:
        raise ReviewRefused(f"no review item {item_id}")
    now = now or _now()
    if now >= datetime.fromisoformat(item["expires_at"]):
        raise ReviewRefused("review item expired")
    if conn.execute("SELECT 1 FROM review_action WHERE item_id=?", (item_id,)).fetchone():
        raise ReviewRefused("item already decided")
    if action == "edit":
        if edited_price is None or not edited_price > 0:
            raise ReviewRefused("edit requires a positive price")
        price: float | None = float(edited_price)
    else:
        price = None if action == "reject" else float(item["proposed_rate"])
    prev = conn.execute("SELECT receipt_sha256 FROM review_action ORDER BY id DESC LIMIT 1").fetchone()
    prev_sha = prev[0] if prev else GENESIS
    body = {"item_id": item_id, "decision_key": item["decision_key"], "action": action, "actor": actor,
            "role": role, "recommended_price": item["proposed_rate"], "decided_price": price,
            "reason": reason, "acted_at": now.isoformat(timespec="seconds"), "prev_sha256": prev_sha}
    receipt_sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    with conn:
        conn.execute(
            """INSERT INTO review_action (item_id, action, actor, role, decided_price, reason, acted_at,
                   prev_sha256, receipt_sha256) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item_id, action, actor, role, price, reason, body["acted_at"], prev_sha, receipt_sha))
    return {**body, "receipt_sha256": receipt_sha}


def verify_chain(conn: sqlite3.Connection) -> bool:
    prev = GENESIS
    for row in conn.execute(
            """SELECT a.*, i.decision_key, i.proposed_rate FROM review_action a
               JOIN review_item i ON i.id = a.item_id ORDER BY a.id"""):
        body = {"item_id": row["item_id"], "decision_key": row["decision_key"], "action": row["action"],
                "actor": row["actor"], "role": row["role"], "recommended_price": row["proposed_rate"],
                "decided_price": row["decided_price"], "reason": row["reason"], "acted_at": row["acted_at"],
                "prev_sha256": prev}
        if row["prev_sha256"] != prev or \
                hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != row["receipt_sha256"]:
            return False
        prev = row["receipt_sha256"]
    return True


def export(conn: sqlite3.Connection, path: Path) -> Path:
    """Queue + decisions + applied rate (from the spine, if any) as one JSON file."""
    applied: dict[str, Any] = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='fact_price_decision'").fetchone():
        from src.data_spine.ingest import current_rows
        applied = {r["entity_key"]: r["applied_price"] for r in current_rows(conn, "fact_price_decision")}
    rows = []
    for r in conn.execute(
            """SELECT i.*, a.action, a.actor, a.role, a.decided_price, a.reason, a.acted_at, a.receipt_sha256
               FROM review_item i LEFT JOIN review_action a ON a.item_id = i.id ORDER BY i.id"""):
        rows.append({
            "decision_key": r["decision_key"], "property_id": r["property_id"], "stay_date": r["stay_date"],
            "current_rate": r["current_rate"], "model_recommendation": r["proposed_rate"],
            "human_decision": r["action"] or "pending", "human_price": r["decided_price"],
            "applied_rate": applied.get(r["decision_key"]), "all_in_price": r["all_in_price"],
            "expected_owner_net": r["expected_owner_net"], "owner_net_basis": r["owner_net_basis"],
            "freshness": json.loads(r["freshness_json"]), "confidence": r["confidence"],
            "reasons": json.loads(r["reasons_json"]), "guardrails": json.loads(r["guardrails_json"]),
            "readiness": r["readiness"], "assignment_arm": r["assignment_arm"], "expires_at": r["expires_at"],
            "actor": r["actor"], "role": r["role"], "reason": r["reason"], "acted_at": r["acted_at"],
            "receipt_sha256": r["receipt_sha256"]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"chain_valid": verify_chain(conn), "items": rows}, indent=1, sort_keys=True))
    return path
