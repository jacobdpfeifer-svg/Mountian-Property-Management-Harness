"""Typed claims. A file is evidence; only a confirmed claim can become a feature."""

from __future__ import annotations

import getpass
import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

CANONICAL_PROPERTIES = frozenset({"summit_haus", "overlook_ridge", "cloud_9"})
PRICE_KINDS = frozenset({"minimum_rate", "no_decrease"})
ALL_KINDS = frozenset({
    "annotation",
    "question",
    "property_fact",
    "comp_trust_note",
    "operator_rejection",
    "minimum_rate",
    "no_decrease",
})
MAX_RANGE_DAYS = 90
EXTRACTOR_VERSION = "deterministic_claim_block_v1"

_FENCE = re.compile(r"```mont-luxe-claim\s*\n(.*?)```", re.DOTALL)
_INSTRUCTION = re.compile(
    r"(?i)ignore\s+guardrails|set[_\s-]?rate|<\s*system\s*>|you\s+are\s+now"
)


class ClaimError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    claim_id: str | None = None,
    file_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO memory_events (
            event_id, claim_id, file_id, event_type, actor, payload_hash, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            claim_id,
            file_id,
            event_type,
            actor,
            _payload_hash(payload),
            _now(),
        ),
    )


def latest_claims(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute(
        """
        SELECT c.* FROM memory_claims c
        JOIN (
            SELECT claim_id, MAX(revision) AS revision
            FROM memory_claims GROUP BY claim_id
        ) latest
          ON c.claim_id = latest.claim_id AND c.revision = latest.revision
        ORDER BY c.created_at, c.claim_id
        """
    ))


def get_latest(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM memory_claims
        WHERE claim_id = ?
        ORDER BY revision DESC LIMIT 1
        """,
        (claim_id,),
    ).fetchone()


def _ranges_overlap(a_from: str | None, a_to: str | None, b_from: str | None, b_to: str | None) -> bool:
    if not a_from or not a_to or not b_from or not b_to:
        return False
    return a_from <= b_to and b_from <= a_to


def _values_incompatible(kind: str, left: dict[str, Any], right: dict[str, Any]) -> bool:
    if kind == "minimum_rate":
        return float(left.get("minimum")) != float(right.get("minimum"))
    return False


def validate_claim(fields: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized claim body or raise ClaimError with a stable code."""
    kind = str(fields.get("kind") or "").strip()
    if kind not in ALL_KINDS:
        raise ClaimError("unknown_kind")
    scope = str(fields.get("scope_type") or ("property" if kind in PRICE_KINDS else "property")).strip()
    property_id = str(fields.get("property_id") or "").strip() or None
    stay_from = str(fields.get("stay_from") or "").strip() or None
    stay_to = str(fields.get("stay_to") or "").strip() or None
    review_after = str(fields.get("review_after") or "").strip() or None
    price = kind in PRICE_KINDS

    if price:
        if scope != "property":
            raise ClaimError("price_scope")
        if property_id not in CANONICAL_PROPERTIES:
            raise ClaimError("property_id")
        if "," in (property_id or "") or property_id in {"both", "twins", "northwoods"}:
            raise ClaimError("property_id")
        start = _parse_day(stay_from)
        end = _parse_day(stay_to)
        if start is None or end is None or end < start:
            raise ClaimError("date_range")
        if (end - start).days > MAX_RANGE_DAYS:
            raise ClaimError("range_too_long")
        if _parse_day(review_after) is None:
            raise ClaimError("review_after")
        effect = "price_bearing"
        if kind == "minimum_rate":
            try:
                minimum = float(fields.get("minimum"))
            except (TypeError, ValueError):
                raise ClaimError("minimum") from None
            if not (minimum > 0) or minimum != minimum:  # NaN
                raise ClaimError("minimum")
            value = {"minimum": minimum}
        else:
            value = {}
    else:
        effect = "context"
        if kind in {"property_fact", "operator_rejection"}:
            if scope != "property" or property_id not in CANONICAL_PROPERTIES:
                raise ClaimError("property_id")
        elif kind == "comp_trust_note":
            if scope not in {"property", "market"}:
                raise ClaimError("scope")
            if scope == "property" and property_id not in CANONICAL_PROPERTIES:
                raise ClaimError("property_id")
        elif kind in {"annotation", "question"}:
            if scope not in {"property", "owner", "portfolio"}:
                raise ClaimError("scope")
            if scope == "property" and property_id not in CANONICAL_PROPERTIES:
                raise ClaimError("property_id")
            if scope == "portfolio":
                property_id = None
        value = {}
        note = fields.get("note")
        if note:
            text = str(note).strip()
            if len(text) > 280:
                raise ClaimError("note_too_long")
            value["note"] = text

    return {
        "kind": kind,
        "property_id": property_id,
        "scope_type": scope,
        "stay_from": stay_from,
        "stay_to": stay_to,
        "review_after": review_after,
        "value": value,
        "effect_class": effect,
    }


def parse_claim_block(text: str) -> dict[str, Any] | None:
    match = _FENCE.search(text)
    if not match:
        return None
    fields: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        fields[key.strip()] = raw.strip()
    return fields


def instruction_flags(text: str) -> list[str]:
    if _INSTRUCTION.search(text):
        return ["instruction_like"]
    return []


@dataclass
class ProposedClaim:
    claim_id: str
    revision: int
    status: str


def propose_claim(
    conn: sqlite3.Connection,
    fields: dict[str, Any],
    *,
    file_id: str | None = None,
    actor: str = "intake",
    excerpt: str | None = None,
) -> ProposedClaim:
    body = validate_claim(fields)
    claim_id = uuid.uuid4().hex[:12]
    created = _now()
    excerpt_hash = hashlib.sha256(excerpt.encode()).hexdigest() if excerpt else None
    conn.execute(
        """
        INSERT INTO memory_claims (
            claim_id, revision, file_id, parent_claim_id, kind, property_id, scope_type,
            stay_from, stay_to, value_json, effect_class, confidence, status,
            accepted_by, accepted_at, review_after, supersedes_claim_id,
            source_excerpt_hash, created_at
        ) VALUES (?, 1, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 1.0, 'proposed',
                  NULL, NULL, ?, NULL, ?, ?)
        """,
        (
            claim_id, file_id, body["kind"], body["property_id"], body["scope_type"],
            body["stay_from"], body["stay_to"], json.dumps(body["value"], sort_keys=True),
            body["effect_class"], body["review_after"], excerpt_hash, created,
        ),
    )
    _event(
        conn, event_type="proposed", actor=actor, claim_id=claim_id, file_id=file_id,
        payload={"claim_id": claim_id, "revision": 1, "kind": body["kind"], "status": "proposed"},
    )
    return ProposedClaim(claim_id=claim_id, revision=1, status="proposed")


def _copy_revision(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    status: str,
    actor: str,
    event_type: str,
    accepted_by: str | None = None,
    accepted_at: str | None = None,
    supersedes_claim_id: str | None = None,
) -> int:
    revision = int(row["revision"]) + 1
    conn.execute(
        """
        INSERT INTO memory_claims (
            claim_id, revision, file_id, parent_claim_id, kind, property_id, scope_type,
            stay_from, stay_to, value_json, effect_class, confidence, status,
            accepted_by, accepted_at, review_after, supersedes_claim_id,
            source_excerpt_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["claim_id"], revision, row["file_id"], row["claim_id"], row["kind"],
            row["property_id"], row["scope_type"], row["stay_from"], row["stay_to"],
            row["value_json"], row["effect_class"], row["confidence"], status,
            accepted_by if accepted_by is not None else row["accepted_by"],
            accepted_at if accepted_at is not None else row["accepted_at"],
            row["review_after"],
            supersedes_claim_id if supersedes_claim_id is not None else row["supersedes_claim_id"],
            row["source_excerpt_hash"], _now(),
        ),
    )
    _event(
        conn, event_type=event_type, actor=actor, claim_id=row["claim_id"],
        file_id=row["file_id"],
        payload={"claim_id": row["claim_id"], "revision": revision, "status": status},
    )
    return revision


def _overlapping_conflict(conn: sqlite3.Connection, row: sqlite3.Row) -> sqlite3.Row | None:
    if row["kind"] not in PRICE_KINDS:
        return None
    incoming = json.loads(row["value_json"] or "{}")
    for other in latest_claims(conn):
        if other["claim_id"] == row["claim_id"]:
            continue
        if other["status"] != "active":
            continue
        if other["kind"] != row["kind"] or other["property_id"] != row["property_id"]:
            continue
        if not _ranges_overlap(row["stay_from"], row["stay_to"], other["stay_from"], other["stay_to"]):
            continue
        other_value = json.loads(other["value_json"] or "{}")
        if _values_incompatible(row["kind"], incoming, other_value):
            return other
    return None


def confirm_claim(conn: sqlite3.Connection, claim_id: str, *, actor: str | None = None) -> str:
    row = get_latest(conn, claim_id)
    if row is None:
        raise ClaimError("missing_claim")
    if row["status"] != "proposed":
        raise ClaimError("not_proposed")
    validate_claim({
        "kind": row["kind"],
        "property_id": row["property_id"],
        "scope_type": row["scope_type"],
        "stay_from": row["stay_from"],
        "stay_to": row["stay_to"],
        "review_after": row["review_after"],
        **json.loads(row["value_json"] or "{}"),
    })
    who = actor or getpass.getuser()
    conflict = _overlapping_conflict(conn, row)
    if conflict is not None:
        _copy_revision(conn, row, status="conflicted", actor=who, event_type="conflicted")
        _copy_revision(conn, conflict, status="conflicted", actor=who, event_type="conflicted")
        return "conflicted"
    _copy_revision(
        conn, row, status="active", actor=who, event_type="confirmed",
        accepted_by=who, accepted_at=_now(),
    )
    return "active"


def reject_claim(conn: sqlite3.Connection, claim_id: str, *, actor: str | None = None) -> str:
    row = get_latest(conn, claim_id)
    if row is None:
        raise ClaimError("missing_claim")
    if row["status"] not in {"proposed", "conflicted"}:
        raise ClaimError("not_rejectable")
    who = actor or getpass.getuser()
    _copy_revision(conn, row, status="rejected", actor=who, event_type="rejected")
    return "rejected"


def revoke_claim(conn: sqlite3.Connection, claim_id: str, *, actor: str | None = None) -> str:
    row = get_latest(conn, claim_id)
    if row is None:
        raise ClaimError("missing_claim")
    if row["status"] != "active":
        raise ClaimError("not_active")
    who = actor or getpass.getuser()
    _copy_revision(conn, row, status="revoked", actor=who, event_type="revoked")
    return "revoked"


def supersede_claim(
    conn: sqlite3.Connection,
    claim_id: str,
    replaces: str,
    *,
    actor: str | None = None,
) -> str:
    incoming = get_latest(conn, claim_id)
    prior = get_latest(conn, replaces)
    if incoming is None or prior is None:
        raise ClaimError("missing_claim")
    if incoming["status"] != "proposed" or prior["status"] not in {"active", "conflicted"}:
        raise ClaimError("not_supersedable")
    who = actor or getpass.getuser()
    _copy_revision(
        conn, incoming, status="active", actor=who, event_type="confirmed",
        accepted_by=who, accepted_at=_now(), supersedes_claim_id=replaces,
    )
    _copy_revision(conn, prior, status="superseded", actor=who, event_type="superseded")
    return "active"


def pending_summaries(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Redacted rows safe for a receipt. No excerpts, names, or file bytes."""
    out = []
    for row in latest_claims(conn):
        if row["status"] not in {"proposed", "conflicted"}:
            continue
        out.append({
            "claim_id": row["claim_id"],
            "kind": row["kind"],
            "property_id": row["property_id"],
            "stay_from": row["stay_from"],
            "stay_to": row["stay_to"],
            "status": row["status"],
            "effect_class": row["effect_class"],
        })
    return out


def active_price_claims(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return [
        row for row in latest_claims(conn)
        if row["status"] == "active" and row["kind"] in PRICE_KINDS
    ]

