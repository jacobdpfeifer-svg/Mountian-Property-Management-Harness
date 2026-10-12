"""Shared value parsing for CSV exports and API payloads."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

CANCELLED = frozenset({"cancelled", "canceled", "deleted", "declined", "void"})
TRUE_WORDS = frozenset({"1", "true", "yes", "y", "pass", "passed", "ok", "approved"})
FALSE_WORDS = frozenset({"0", "false", "no", "n", "fail", "failed", "rejected"})


def blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def as_float(value: Any) -> float | None:
    if blank(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[,$\s]", "", str(value))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def as_bool(value: Any) -> bool | None:
    if blank(value):
        return None
    if isinstance(value, bool):
        return value
    word = str(value).strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    return None


def as_minutes(value: Any) -> float | None:
    """Accept 95, "95", "1:35", "1h 35m", "1.5h"."""
    if blank(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    m = re.fullmatch(r"(\d+):(\d{1,2})(?::(\d{1,2}))?", text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)) + (int(m.group(3) or 0) / 60.0)
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)\s*h(?:ours?|rs?)?)?\s*(?:(\d+(?:\.\d+)?)\s*m(?:in(?:ute)?s?)?)?", text)
    if m and (m.group(1) or m.group(2)):
        return float(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    return as_float(text)


def as_datetime(value: Any) -> datetime | None:
    if blank(value):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M %p", "%m/%d/%Y", "%Y-%m-%d %H:%M",
                "%m/%d/%y %H:%M", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def as_iso_date(value: Any) -> str | None:
    dt = as_datetime(value)
    return None if dt is None else dt.date().isoformat()


def as_iso_datetime(value: Any) -> str | None:
    dt = as_datetime(value)
    return None if dt is None else dt.replace(microsecond=0).isoformat()


def minutes_between(start: Any, end: Any) -> float | None:
    a, b = as_datetime(start), as_datetime(end)
    if a is None or b is None:
        return None
    if (a.tzinfo is None) != (b.tzinfo is None):
        a, b = a.replace(tzinfo=None), b.replace(tzinfo=None)
    delta = (b - a).total_seconds() / 60.0
    return delta if delta >= 0 else None


def service_type_for(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "turnover"
    if any(w in text for w in ("inspect", "qa", "quality")):
        return "inspection"
    if any(w in text for w in ("spa", "hot tub", "hottub", "jacuzzi")):
        return "spa"
    if any(w in text for w in ("snow", "plow", "shovel")):
        return "snow"
    if "laundry" in text or "linen" in text:
        return "laundry"
    if any(w in text for w in ("clean", "turn", "housekeep", "checkout", "departure")):
        return "turnover"
    return "maintenance"


def dig(obj: Any, path: str) -> Any:
    """dig({'a': {'b': 1}}, 'a.b') -> 1. Missing keys return None."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def first(obj: dict[str, Any], *paths: str) -> Any:
    for p in paths:
        v = dig(obj, p)
        if not blank(v):
            return v
    return None
