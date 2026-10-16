"""Redacted, append-only audit events.

Everything that crosses a scope, credential, or write boundary is recorded here.
Details are redacted before they are stored or logged: secrets, tokens, and guest
identity fields never reach the audit table, a log file, or a report.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY = re.compile(
    r"(secret|token|password|passwd|authorization|api[_-]?key|client[_-]?secret|cookie|"
    r"signature|email|phone|guest[_-]?name|first[_-]?name|last[_-]?name|full[_-]?name|"
    r"address|street|card|iban|account[_-]?number|ssn|dob|birth)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{8,}")
_WHSEC = re.compile(r"whsec_[A-Za-z0-9+/=]{8,}")
_LONG_SECRETISH = re.compile(r"\b[A-Za-z0-9_-]{40,}\b")
_PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")


def redact_text(value: str) -> str:
    value = _BEARER.sub("Bearer " + REDACTED, value)
    value = _WHSEC.sub(REDACTED, value)
    value = _EMAIL.sub(REDACTED, value)
    value = _PHONE.sub(REDACTED, value)
    return _LONG_SECRETISH.sub(REDACTED, value)


def redact(value: Any) -> Any:
    """Recursively redact a JSON-like structure."""
    if isinstance(value, dict):
        return {
            str(k): (REDACTED if _SENSITIVE_KEY.search(str(k)) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _has_table(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_events'"
    ).fetchone() is not None


def record_event(
    conn: sqlite3.Connection | None,
    *,
    event_type: str,
    boundary: str,
    severity: str = "warning",
    subject: str | None = None,
    detail: dict[str, Any] | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """Build a redacted event and append it to `audit_events` when that table exists.

    Returns the redacted event so callers can also surface it (run receipt, alert).
    A database without the spine migrations still gets the event returned; the
    caller decides whether a missing audit sink must block the action.
    """
    from src.security.environment import current_environment

    event = {
        "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": environment or current_environment().value,
        "event_type": event_type,
        "boundary": boundary,
        "severity": severity,
        "subject": redact_text(subject) if subject else None,
        "detail": redact(detail or {}),
    }
    if conn is not None and _has_table(conn):
        conn.execute(
            """INSERT INTO audit_events
               (occurred_at, environment, event_type, boundary, severity, subject, detail_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event["occurred_at"], event["environment"], event_type, boundary, severity,
             event["subject"], json.dumps(event["detail"], sort_keys=True)),
        )
    return event
