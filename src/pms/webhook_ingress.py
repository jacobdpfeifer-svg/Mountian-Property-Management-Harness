"""Framework-neutral, inactive Guesty webhook ingress.

`handle_delivery(conn, headers, body, ...)` is what an HTTPS endpoint would call.
No endpoint is exposed and no Guesty subscription exists; this is the tested
core that one would wrap.

Order of operations (each step can only make the outcome more conservative):

1. Verify the signature over the raw bytes BEFORE persisting anything from the
   body. Guesty delivers through Svix: headers `svix-id`, `svix-timestamp`,
   `svix-signature` ("v1,<base64 HMAC-SHA256(secret, id.timestamp.body)>"), and
   a `whsec_<base64>` secret. Written from public documentation; not yet
   verified against a live tenant (BLOCKED on operator credentials).
2. Reject timestamps outside the tolerance window (replay protection).
3. Deduplicate on the delivery id; a redelivery is acknowledged, not re-applied.
4. Persist an immutable, redacted receipt.
5. Check the listing against the portfolio scope; out-of-scope is quarantined
   and audited, and requests no refetch.
6. Enqueue a bounded refetch of authoritative Guesty state. The webhook body
   itself never changes a price, inventory row, or reservation.

Anything unverifiable or unparseable goes to the dead letter table with a hash
of the body (never the body) and a reason.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from src.security.audit import redact
from src.security.scope import PortfolioScope

TOLERANCE = timedelta(minutes=5)
MAX_BODY_BYTES = 256 * 1024
MAX_REFETCH_DAYS = 400


@dataclass(frozen=True)
class IngressResponse:
    http_status: int
    outcome: str        # accepted | duplicate | quarantined | dead_letter
    reason: str | None = None
    receipt_id: int | None = None
    refetch_ids: tuple[int, ...] = ()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _secret_bytes(secret: str) -> bytes:
    if not secret.startswith("whsec_"):
        raise ValueError("webhook secret must be a whsec_ value")
    return base64.b64decode(secret[len("whsec_"):])


def sign(secret: str, delivery_id: str, timestamp: int, body: bytes) -> str:
    """Produce a Svix-format signature header value (used by tests and fixtures)."""
    mac = hmac.new(_secret_bytes(secret), f"{delivery_id}.{timestamp}.".encode() + body, hashlib.sha256)
    return "v1," + base64.b64encode(mac.digest()).decode()


def verify(secret: str, headers: Mapping[str, str], body: bytes, now: datetime) -> tuple[str, datetime]:
    """Return (delivery_id, signed_at) or raise ValueError with a dead-letter reason."""
    h = {k.lower(): v for k, v in headers.items()}
    delivery_id, ts_raw, sig_header = h.get("svix-id"), h.get("svix-timestamp"), h.get("svix-signature")
    if not delivery_id or not ts_raw or not sig_header:
        raise ValueError("missing signature headers")
    try:
        ts = int(ts_raw)
    except ValueError:
        raise ValueError("bad timestamp header") from None
    signed_at = datetime.fromtimestamp(ts, timezone.utc)
    if abs(now - signed_at) > TOLERANCE:
        raise ValueError("timestamp outside tolerance (possible replay)")
    expected = sign(secret, delivery_id, ts, body).split(",", 1)[1]
    candidates = [part.split(",", 1)[1] for part in sig_header.split() if part.startswith("v1,")]
    if not any(hmac.compare_digest(expected, c) for c in candidates):
        raise ValueError("signature mismatch")
    return delivery_id, signed_at


def _dead_letter(conn: sqlite3.Connection, reason: str, body: bytes, delivery_id: str | None,
                 now: datetime) -> IngressResponse:
    with conn:
        conn.execute(
            "INSERT INTO webhook_dead_letter (received_at, reason, delivery_id, body_sha256, body_bytes) "
            "VALUES (?, ?, ?, ?, ?)",
            (now.isoformat(), reason, delivery_id, hashlib.sha256(body).hexdigest(), len(body)),
        )
    # Unsigned/invalid → 401 so the sender does not treat it as delivered;
    # a verified-but-unprocessable body → 200 so it is not retried forever.
    status = 401 if reason in {"missing signature headers", "signature mismatch", "bad timestamp header",
                               "timestamp outside tolerance (possible replay)"} else 200
    if reason == "body too large":
        status = 413
    return IngressResponse(status, "dead_letter", reason)


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _extract(payload: dict[str, Any]) -> tuple[str, str | None, date | None, date | None]:
    event_type = str(payload.get("event") or payload.get("type") or "unknown")
    raw_listing, raw_res = payload.get("listing"), payload.get("reservation")
    listing: dict[str, Any] = raw_listing if isinstance(raw_listing, dict) else {}
    reservation: dict[str, Any] = raw_res if isinstance(raw_res, dict) else {}
    listing_id = (payload.get("listingId") or listing.get("_id") or reservation.get("listingId"))
    start = _date(payload.get("startDate") or reservation.get("checkIn"))
    end = _date(payload.get("endDate") or reservation.get("checkOut"))
    return event_type, (str(listing_id) if listing_id else None), start, end


def handle_delivery(
    conn: sqlite3.Connection,
    headers: Mapping[str, str],
    body: bytes,
    *,
    secret: str | None,
    scope: PortfolioScope,
    now: datetime | None = None,
) -> IngressResponse:
    now = now or _now()
    if not secret:
        # No configured secret means nothing can be verified: fail closed.
        return _dead_letter(conn, "signature mismatch", body, None, now)
    if len(body) > MAX_BODY_BYTES:
        return _dead_letter(conn, "body too large", body, None, now)
    try:
        delivery_id, signed_at = verify(secret, headers, body, now)
    except ValueError as exc:
        return _dead_letter(conn, str(exc), body, None, now)

    if conn.execute("SELECT 1 FROM webhook_receipt WHERE delivery_id=?", (delivery_id,)).fetchone():
        return IngressResponse(200, "duplicate", None)
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        return _dead_letter(conn, "malformed json", body, delivery_id, now)

    event_type, listing_id, start, end = _extract(payload)
    if listing_id is None:
        scope_status, property_id = "not_listing_scoped", None
    else:
        decision = scope.check_listing(listing_id)
        scope_status = "in_scope" if decision.allowed else "quarantined"
        property_id = decision.property_id
    with conn:
        cur = conn.execute(
            """INSERT INTO webhook_receipt (delivery_id, signed_at, received_at, body_sha256, event_type,
                   property_id, scope_status, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (delivery_id, signed_at.isoformat(), now.isoformat(), hashlib.sha256(body).hexdigest(),
             event_type, property_id, scope_status, json.dumps(redact(payload), sort_keys=True)),
        )
        receipt_id = int(cur.lastrowid or 0)
        if scope_status == "quarantined":
            from src.security.scope import quarantine

            quarantine(conn, boundary="webhook", property_id=None, listing_id=listing_id,
                       reason="unknown_listing")
            return IngressResponse(200, "quarantined", "unknown_listing", receipt_id)
        refetch = []
        rng: tuple[str | None, str | None]
        if property_id is None:
            kind, rng = "full_reconcile", (None, None)
        else:
            kind = "reservation" if event_type.startswith("reservation") else "calendar"
            if start and end and end >= start and (end - start).days <= MAX_REFETCH_DAYS:
                rng = (start.isoformat(), end.isoformat())
            else:
                kind, rng = "full_reconcile", (None, None)
        cur = conn.execute(
            "INSERT INTO refetch_request (receipt_id, kind, property_id, start_date, end_date, requested_at) "
            "VALUES (?, ?, ?, ?, ?, ?)", (receipt_id, kind, property_id, rng[0], rng[1], now.isoformat()))
        refetch.append(int(cur.lastrowid or 0))
    return IngressResponse(200, "accepted", None, receipt_id, tuple(refetch))


def pending_refetches(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT r.* FROM refetch_request r
           WHERE NOT EXISTS (SELECT 1 FROM refetch_completion c WHERE c.request_id = r.id AND c.outcome = 'ok')
           ORDER BY r.id"""
    ).fetchall()


def complete_refetch(conn: sqlite3.Connection, request_id: int, ok: bool, detail: str | None = None) -> None:
    with conn:
        conn.execute(
            "INSERT INTO refetch_completion (request_id, completed_at, outcome, detail) VALUES (?, ?, ?, ?)",
            (request_id, _now().isoformat(), "ok" if ok else "failed", detail),
        )
