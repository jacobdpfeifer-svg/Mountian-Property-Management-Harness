"""CoTrip / Berthoud Pass access parser."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.request import Request, urlopen

_USER_AGENT = "wp-price-signals/1.0 (cdot-access)"
# CDOT traveler information API — public JSON feed for road conditions.
COTRIP_ALERTS_URL = (
    "https://www.cotrip.org/api/alerts?routeName=US%2040&direction=Both"
)


def _risk_from_flags(closed: float, chain: float) -> float:
    return min(1.0, closed * 1.0 + chain * 0.4)


def parse_cotrip_payload(payload: Any) -> dict[str, float]:
    """Derive Berthoud / US-40 access flags from CoTrip alert JSON or fixture dict."""
    if isinstance(payload, dict) and "berthoud_closed" in payload:
        closed = float(payload.get("berthoud_closed", 0))
        chain = float(payload.get("chain_law", 0))
        return {
            "berthoud_closed": closed,
            "chain_law": chain,
            "access_risk": _risk_from_flags(closed, chain),
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
    }


def fetch_cotrip_access(*, timeout_s: float = 20.0) -> dict[str, float]:
    req = Request(COTRIP_ALERTS_URL, headers={"User-Agent": _USER_AGENT})
    with urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = raw
    return parse_cotrip_payload(payload)
