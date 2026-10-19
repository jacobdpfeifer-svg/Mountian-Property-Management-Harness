"""CoTrip / Berthoud Pass access parser."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.request import Request, urlopen

_USER_AGENT = "wp-price-signals/1.0 (cdot-access)"
# CDOT traveler information API — public GeoJSON feed used by the current 511 app.
# The old www.cotrip.org/api/alerts URL is an HTML application shell, not an API.
COTRIP_ALERTS_URL = "https://api-511x-co.carsprogram.org/events/map-features"
_BERTHOUD_ROUTE = "us 40"
_BERTHOUD_MIN_MP = 233.0
_BERTHOUD_MAX_MP = 243.0


def _risk_from_flags(closed: float, chain: float) -> float:
    return min(1.0, closed * 1.0 + chain * 0.4)


def _feature_text(feature: dict[str, Any]) -> str:
    props = feature.get("properties") or {}
    return json.dumps(props, sort_keys=True).lower()


def _is_berthoud_feature(feature: dict[str, Any]) -> bool:
    props = feature.get("properties") or {}
    report = props.get("eventReport") or {}
    location = report.get("location") or {}
    route = str(location.get("routeDesignator") or props.get("route") or "").lower()
    if route.replace("-", " ").strip() != _BERTHOUD_ROUTE:
        return "berthoud" in _feature_text(feature)
    points = [location.get("primaryPoint"), location.get("secondaryPoint")]
    milepoints = [p.get("linearReference") for p in points if isinstance(p, dict)]
    if any(mp is not None and _BERTHOUD_MIN_MP <= float(mp) <= _BERTHOUD_MAX_MP for mp in milepoints):
        return True
    return "berthoud" in _feature_text(feature)


def parse_cotrip_payload(payload: Any) -> dict[str, Any]:
    """Derive Berthoud / US-40 access flags from 511 JSON or a fixture dict.

    A non-JSON response is explicitly unavailable. It must never become a clean set of
    zero-valued flags because zero means the road was checked and no risk was found.
    """
    if isinstance(payload, str):
        return {"quality": "unavailable", "reason": "non_json_payload"}

    if isinstance(payload, dict) and isinstance(payload.get("features"), list):
        features = [f for f in payload["features"] if isinstance(f, dict) and _is_berthoud_feature(f)]
        text = " ".join(_feature_text(f) for f in features)
        closed = 1.0 if any(k in text for k in ("road closed", "closure", "closed due to", "closed")) else 0.0
        chain = 1.0 if any(k in text for k in ("chain law", "chains required", "traction law")) else 0.0
        return {
            "berthoud_closed": closed,
            "chain_law": chain,
            "access_risk": _risk_from_flags(closed, chain),
            "quality": "ok",
            "feature_count": float(len(features)),
        }

    if isinstance(payload, dict) and "berthoud_closed" in payload:
        closed = float(payload.get("berthoud_closed", 0))
        chain = float(payload.get("chain_law", 0))
        return {
            "berthoud_closed": closed,
            "chain_law": chain,
            "access_risk": _risk_from_flags(closed, chain),
            "quality": "ok",
        }

    text = json.dumps(payload).lower() if not isinstance(payload, str) else payload.lower()
    closed = 1.0 if any(
        k in text
        for k in (
            "road closed",
            "closure",
            "closed due to",
            "berthoud pass closed",
            "us 40 closed",
        )
    ) else 0.0
    chain = 1.0 if any(
        k in text for k in ("chain law", "chains required", "traction law")
    ) else 0.0
    if "berthoud" not in text and "us 40" not in text and "us-40" not in text:
        # Unrelated alerts — do not invent closure.
        closed = chain = 0.0
    return {
        "berthoud_closed": closed,
        "chain_law": chain,
        "access_risk": _risk_from_flags(closed, chain),
        "quality": "ok",
    }


def fetch_cotrip_access(*, timeout_s: float = 20.0) -> dict[str, Any]:
    req = Request(COTRIP_ALERTS_URL, headers={"User-Agent": _USER_AGENT})
    with urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"quality": "unavailable", "reason": "non_json_payload"}
    return parse_cotrip_payload(payload)
