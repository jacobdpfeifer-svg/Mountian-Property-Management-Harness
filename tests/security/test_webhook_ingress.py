"""Webhook ingress: signed, duplicate, out-of-order, delayed, malformed, replay, scope."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.pms.webhook_ingress import complete_refetch, handle_delivery, pending_refetches, sign

SECRET = "whsec_" + base64.b64encode(b"synthetic-test-secret-0123456789").decode()
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def _deliver(conn, scope, payload, *, delivery_id="msg_1", at=NOW, now=NOW, secret=SECRET,
             body=None, sig=None):
    body = body if body is not None else json.dumps(payload).encode()
    ts = int(at.timestamp())
    headers = {"svix-id": delivery_id, "svix-timestamp": str(ts),
               "svix-signature": sig or sign(SECRET, delivery_id, ts, body)}
    return handle_delivery(conn, headers, body, secret=secret, scope=scope, now=now)


CAL = {"event": "calendar.updated", "listingId": "LST-A", "startDate": "2026-12-01", "endDate": "2026-12-05"}


def test_signed_event_records_receipt_and_bounded_refetch(conn, scope):
    r = _deliver(conn, scope, CAL)
    assert (r.http_status, r.outcome) == (200, "accepted")
    req = pending_refetches(conn)
    assert [(q["kind"], q["property_id"], q["start_date"], q["end_date"]) for q in req] == [
        ("calendar", "summit_haus", "2026-12-01", "2026-12-05")]
    # Webhook never touches pricing state directly.
    assert conn.execute("SELECT COUNT(*) FROM rate_changes").fetchone()[0] == 0


def test_bad_signature_is_dead_lettered_before_persistence(conn, scope):
    r = _deliver(conn, scope, CAL, sig="v1," + base64.b64encode(b"x" * 32).decode())
    assert (r.http_status, r.outcome, r.reason) == (401, "dead_letter", "signature mismatch")
    assert conn.execute("SELECT COUNT(*) FROM webhook_receipt").fetchone()[0] == 0
    dl = conn.execute("SELECT * FROM webhook_dead_letter").fetchone()
    assert "LST-A" not in json.dumps(dict(dl))       # only a hash of the body is kept


def test_missing_secret_fails_closed(conn, scope):
    assert _deliver(conn, scope, CAL, secret=None).outcome == "dead_letter"


def test_duplicate_delivery_is_acknowledged_not_reapplied(conn, scope):
    assert _deliver(conn, scope, CAL).outcome == "accepted"
    # Svix retries re-sign the same message id with a fresh timestamp (delayed retry).
    later = NOW + timedelta(hours=3)
    r = _deliver(conn, scope, CAL, at=later, now=later)
    assert r.outcome == "duplicate"
    assert conn.execute("SELECT COUNT(*) FROM refetch_request").fetchone()[0] == 1


def test_replayed_old_signature_is_rejected(conn, scope):
    r = _deliver(conn, scope, CAL, at=NOW - timedelta(minutes=30))
    assert (r.http_status, r.reason) == (401, "timestamp outside tolerance (possible replay)")


def test_out_of_order_events_only_enqueue_refetches(conn, scope):
    newer = dict(CAL, startDate="2026-12-03", endDate="2026-12-04")
    _deliver(conn, scope, newer, delivery_id="msg_2")
    _deliver(conn, scope, CAL, delivery_id="msg_1")
    assert len(pending_refetches(conn)) == 2  # authoritative refetch resolves order


def test_malformed_body_with_valid_signature_is_dead_lettered(conn, scope):
    r = _deliver(conn, scope, None, body=b"{not json")
    assert (r.http_status, r.outcome, r.reason) == (200, "dead_letter", "malformed json")


def test_unknown_listing_is_quarantined_with_no_refetch(conn, scope):
    r = _deliver(conn, scope, dict(CAL, listingId="LST-UNKNOWN"))
    assert r.outcome == "quarantined"
    assert pending_refetches(conn) == []
    assert conn.execute("SELECT boundary FROM audit_events").fetchone()["boundary"] == "webhook"


def test_unbounded_or_unscoped_event_requests_full_reconcile(conn, scope):
    _deliver(conn, scope, {"event": "listing.updated"}, delivery_id="m1")
    _deliver(conn, scope, dict(CAL, endDate="2029-01-01"), delivery_id="m2")
    assert [q["kind"] for q in pending_refetches(conn)] == ["full_reconcile", "full_reconcile"]


def test_receipt_is_redacted_and_immutable(conn, scope):
    payload = {"event": "reservation.new", "reservation": {
        "listingId": "LST-B", "checkIn": "2026-12-10", "checkOut": "2026-12-12",
        "guest": {"fullName": "Synthetic Person", "email": "p@example.com"}}}
    r = _deliver(conn, scope, payload)
    row = conn.execute("SELECT payload_json FROM webhook_receipt").fetchone()
    assert "p@example.com" not in row[0] and "Synthetic Person" not in row[0]
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE webhook_receipt SET event_type='x'")
    complete_refetch(conn, r.refetch_ids[0], ok=True)
    assert pending_refetches(conn) == []


def test_oversized_body_is_refused(conn, scope):
    r = _deliver(conn, scope, None, body=b"x" * (256 * 1024 + 1))
    assert r.http_status == 413
