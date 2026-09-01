"""Alterra / Intrawest lift feed parser (Winter Park feed_id=5).

Primary free source for per-lift and per-trail operational status.
Used by Liftie: https://snowreporting.herokuapp.com/feed/{feed_id}/lifts
"""

from __future__ import annotations

import json
from typing import Any

import requests

_USER_AGENT = "wp-price-signals/1.0 (resort-conditions)"
DEFAULT_FEED_BASE = "https://snowreporting.herokuapp.com/feed"
WINTER_PARK_FEED_ID = 5

OPEN_LIFT_STATUSES = frozenset({"open", "open_to_mid_station"})
OPEN_TRAIL_STATUSES = frozenset({"open"})
HOLD_LIFT_STATUSES = frozenset({"on_hold", "delayed", "temporarily_closed"})


def feed_url(feed_id: int = WINTER_PARK_FEED_ID) -> str:
    return f"{DEFAULT_FEED_BASE}/{feed_id}/lifts"


def fetch_intrawest_lifts(
    feed_id: int = WINTER_PARK_FEED_ID,
    *,
    timeout_s: float = 30.0,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Fetch lift/trail JSON from the Intrawest snow-reporting relay."""
    url = feed_url(feed_id)
    sess = session or requests.Session()
    resp = sess.get(url, headers={"User-Agent": _USER_AGENT}, timeout=timeout_s)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list):
        raise ValueError("expected list of lifts from intrawest feed")
    return payload


def _trail_status(trail: dict[str, Any]) -> str:
    return str(trail.get("StatusEnglish") or trail.get("Status") or "").lower()


def _lift_status(lift: dict[str, Any]) -> str:
    return str(lift.get("StatusEnglish") or lift.get("Status") or "").lower()


def summarize_lifts(lifts: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate lift/trail counts and percentages from raw feed JSON."""
    lift_total = len(lifts)
    lift_open = 0
    lifts_on_hold = 0
    trails: list[dict[str, Any]] = []
    seen_trails: set[tuple[str, str]] = set()

    for lift in lifts:
        st = _lift_status(lift)
        if st in OPEN_LIFT_STATUSES:
            lift_open += 1
        elif st in HOLD_LIFT_STATUSES:
            lifts_on_hold += 1
        for trail in lift.get("Trails") or []:
            key = (trail.get("Name") or "", trail.get("MountainAreaName") or "")
            if key in seen_trails:
                continue
            seen_trails.add(key)
            trails.append(trail)

    trail_total = len(trails)
    trail_open = sum(1 for t in trails if _trail_status(t) in OPEN_TRAIL_STATUSES)
    open_trails = [t for t in trails if _trail_status(t) in OPEN_TRAIL_STATUSES]
    groomed_open = sum(
        1 for t in open_trails if str(t.get("Grooming") or "").lower() in {"yes", "true", "1"}
    )
    trails_groomed_pct = (100.0 * groomed_open / trail_open) if trail_open else None
    terrain_open_pct = (100.0 * trail_open / trail_total) if trail_total else 0.0
    resort_open = 1.0 if lift_open > 0 else 0.0

    return {
        "source_url": feed_url(WINTER_PARK_FEED_ID),
        "lifts": lifts,
        "lift_total": lift_total,
        "lifts_open": float(lift_open),
        "lifts_on_hold": float(lifts_on_hold),
        "trails_open": float(trail_open),
        "trail_total": trail_total,
        "terrain_open_pct": terrain_open_pct,
        "trails_groomed_pct": trails_groomed_pct,
        "resort_open": resort_open,
    }


def parse_intrawest_payload(
    lifts: list[dict[str, Any]], *, source_url: str | None = None, feed_id: int = WINTER_PARK_FEED_ID
) -> dict[str, Any]:
    summary = summarize_lifts(lifts)
    if source_url:
        summary["source_url"] = source_url
    else:
        summary["source_url"] = feed_url(feed_id)
    return summary
