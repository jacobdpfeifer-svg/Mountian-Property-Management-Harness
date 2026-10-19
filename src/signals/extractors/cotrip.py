"""CoTrip / Berthoud Pass access parser.

Classification uses the CARS headlinePhrase (category, code) and quantity
labels, not a search for the word "closed". The live feed's lane and shoulder
phrases contain that word (observed 2026-10-19: "Right shoulder closed" is
category 3, code 131) and must not set a full-closure flag.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from src.config import ROOT, load_yaml

_USER_AGENT = "wp-price-signals/1.0 (cdot-access)"
# CDOT traveler information API — public GeoJSON feed used by the current 511 app.
# The old www.cotrip.org/api/alerts URL is an HTML application shell, not an API.
COTRIP_ALERTS_URL = "https://api-511x-co.carsprogram.org/events/map-features"
ACCESS_POLICY_PATH = ROOT / "config" / "policies" / "access.yaml"

_US40 = "us 40"
_I70 = "i 70"

# Headline phrases observed on the live CARS feed, 2026-10-19.
# Category 48 code 28 is "Road closed". Category 50 code 48 is "Seasonal Closure".
FULL_CLOSURE_CODES = frozenset({(48, 28), (50, 48)})
# Category 3 is a lane or shoulder impact. Category 46 code 24 is "Lane closure".
LANE_OR_SHOULDER_CODES = frozenset({
    (3, 128),  # right lane
    (3, 129),  # left lane
    (3, 130),  # center lane
    (3, 131),  # right shoulder
    (3, 132),  # left shoulder
    (3, 188),  # two left lanes
    (3, 189),  # three left lanes
    (3, 192),  # two right lanes
    (3, 206),  # both shoulders
    (46, 24),  # lane closure
})
# No chain-law headline was active on 2026-10-19. Quantity labels are the
# structured field the feed uses for restrictions (width, height, length).
CHAIN_QUANTITY_LABELS = frozenset({
    "chain law",
    "traction law",
    "passenger vehicle chain law",
    "passenger vehicle traction law",
})

# Named so a shoulder is not a full closure. access_risk is a feature input;
# I-70 flags are stored separately and are not folded into this number.
_CLOSURE_RISK = 1.0
_CHAIN_RISK = 0.4
_LANE_RISK = 0.25


def _risk_from_flags(closed: float, chain: float, lane: float = 0.0) -> float:
    return min(1.0, closed * _CLOSURE_RISK + chain * _CHAIN_RISK + lane * _LANE_RISK)


def load_access_policy(path=None) -> dict[str, Any]:
    data = load_yaml(path or ACCESS_POLICY_PATH)
    us40 = data.get("us40_berthoud") or {}
    i70 = data.get("i70") or {}
    try:
        us40_min = float(us40["min_milepost"])
        us40_max = float(us40["max_milepost"])
        empire = float(i70["empire_junction_milepost"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"access policy is missing mileposts: {exc}") from exc
    if us40_min >= us40_max:
        raise ValueError("us40 milepost window is empty")
    return {
        "us40_min": us40_min,
        "us40_max": us40_max,
        "i70_empire": empire,
    }


def _route(location: dict[str, Any]) -> str:
    return str(location.get("routeDesignator") or "").replace("-", " ").strip().lower()


def _milepoints(location: dict[str, Any]) -> list[float]:
    points = []
    for key in ("primaryPoint", "secondaryPoint"):
        point = location.get(key)
        if not isinstance(point, dict):
            continue
        raw = point.get("linearReference")
        if raw is None:
            continue
        try:
            points.append(float(raw))
        except (TypeError, ValueError):
            continue
    return points


def _headline(report: dict[str, Any]) -> tuple[int, int] | None:
    phrase = report.get("headlinePhrase") or {}
    if not isinstance(phrase, dict):
        return None
    try:
        return int(phrase["category"]), int(phrase["code"])
    except (KeyError, TypeError, ValueError):
        return None


def _chain_from_quantities(report: dict[str, Any]) -> bool:
    quantities = report.get("quantities") or []
    if not isinstance(quantities, list):
        return False
    for item in quantities:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip().lower()
        if label in CHAIN_QUANTITY_LABELS:
            return True
    return False


def _in_window(milepoints: list[float], lo: float, hi: float) -> bool:
    return any(lo <= mp <= hi for mp in milepoints)


def _classify_feature(feature: dict[str, Any], policy: dict[str, float]) -> dict[str, float]:
    """Flags for one feature. Zeros mean the feature is not this kind of event."""
    props = feature.get("properties") or {}
    report = props.get("eventReport") if isinstance(props.get("eventReport"), dict) else {}
    if report.get("active") is False or props.get("active") is False:
        return {}
    location = report.get("location") if isinstance(report.get("location"), dict) else {}
    route = _route(location)
    milepoints = _milepoints(location)
    phrase = _headline(report)
    chain = _chain_from_quantities(report)
    full = phrase in FULL_CLOSURE_CODES
    lane = phrase in LANE_OR_SHOULDER_CODES
    out = {
        "berthoud_closed": 0.0,
        "chain_law": 0.0,
        "lane_or_shoulder": 0.0,
        "i70_east_shared_negative": 0.0,
        "i70_west_substitution": 0.0,
        "matched": 0.0,
    }
    if route == _US40 and _in_window(milepoints, policy["us40_min"], policy["us40_max"]):
        out["matched"] = 1.0
        if full:
            out["berthoud_closed"] = 1.0
        if chain:
            out["chain_law"] = 1.0
        if lane and not full:
            out["lane_or_shoulder"] = 1.0
    elif route == _I70 and milepoints:
        # A closure east of Empire is shared. A closure west is substitution.
        # Lane and shoulder events on I-70 are not either signal.
        if full:
            if any(mp > policy["i70_empire"] for mp in milepoints):
                out["i70_east_shared_negative"] = 1.0
                out["matched"] = 1.0
            if any(mp < policy["i70_empire"] for mp in milepoints):
                out["i70_west_substitution"] = 1.0
                out["matched"] = 1.0
    return out


def _ok(closed: float, chain: float, lane: float, *, feature_count: float,
        i70_east: float = 0.0, i70_west: float = 0.0,
        reason: str | None = None) -> dict[str, Any]:
    result = {
        "berthoud_closed": closed,
        "chain_law": chain,
        "access_risk": _risk_from_flags(closed, chain, lane),
        "i70_east_shared_negative": i70_east,
        "i70_west_substitution": i70_west,
        "quality": "ok",
        "feature_count": feature_count,
    }
    if reason:
        result["reason"] = reason
    return result


def parse_cotrip_payload(payload: Any, *, policy: dict[str, float] | None = None) -> dict[str, Any]:
    """Derive access flags from 511 JSON or a legacy fixture dict.

    A non-JSON response is explicitly unavailable. It must never become a clean
    set of zero-valued flags, because zero means the road was checked and no
    risk was found.
    """
    if isinstance(payload, str):
        return {"quality": "unavailable", "reason": "non_json_payload"}

    if isinstance(payload, dict) and isinstance(payload.get("features"), list):
        try:
            window = policy or load_access_policy()
        except (OSError, ValueError) as exc:
            return {"quality": "unavailable", "reason": f"access_policy:{exc}"}
        flags = [
            _classify_feature(f, window)
            for f in payload["features"]
            if isinstance(f, dict)
        ]
        matched = [f for f in flags if f.get("matched")]
        closed = 1.0 if any(f.get("berthoud_closed") for f in matched) else 0.0
        chain = 1.0 if any(f.get("chain_law") for f in matched) else 0.0
        lane = 1.0 if any(f.get("lane_or_shoulder") for f in matched) else 0.0
        east = 1.0 if any(f.get("i70_east_shared_negative") for f in flags) else 0.0
        west = 1.0 if any(f.get("i70_west_substitution") for f in flags) else 0.0
        return _ok(
            closed, chain, lane,
            feature_count=float(len(matched)),
            i70_east=east,
            i70_west=west,
            reason=None if matched or east or west else "no_matching_events",
        )

    if isinstance(payload, dict) and "berthoud_closed" in payload:
        closed = float(payload.get("berthoud_closed", 0))
        chain = float(payload.get("chain_law", 0))
        return _ok(closed, chain, 0.0, feature_count=0.0)

    # Legacy list/dict fixtures that predate headlinePhrase. They are not the
    # live feed. A bare "closed" still does not count; the phrase has to name
    # a road closure or a chain law on US 40 / Berthoud.
    text = json.dumps(payload).lower()
    if "berthoud" not in text and "us 40" not in text and "us-40" not in text:
        return _ok(0.0, 0.0, 0.0, feature_count=0.0, reason="unrelated_legacy_alert")
    closed = 1.0 if any(
        k in text for k in ("road closed", "closed due to", "berthoud pass closed", "us 40 closed")
    ) else 0.0
    chain = 1.0 if any(k in text for k in ("chain law", "chains required", "traction law")) else 0.0
    return _ok(closed, chain, 0.0, feature_count=0.0, reason="legacy_text")


def fetch_cotrip_access(*, timeout_s: float = 20.0) -> dict[str, Any]:
    req = Request(COTRIP_ALERTS_URL, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return {"quality": "unavailable", "reason": f"fetch_failed:{exc.__class__.__name__}"}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"quality": "unavailable", "reason": "non_json_payload"}
    return parse_cotrip_payload(payload)


def health_receipt(parsed: dict[str, Any]) -> dict[str, Any]:
    """A run is ok with counts, or unavailable with a reason. Never a bare zero."""
    if parsed.get("quality") != "ok":
        return {
            "status": "unavailable",
            "reason": parsed.get("reason") or "cotrip_unavailable",
        }
    return {
        "status": "ok",
        "feature_count": parsed.get("feature_count", 0),
        "berthoud_closed": parsed.get("berthoud_closed"),
        "chain_law": parsed.get("chain_law"),
        "access_risk": parsed.get("access_risk"),
        "i70_east_shared_negative": parsed.get("i70_east_shared_negative", 0),
        "i70_west_substitution": parsed.get("i70_west_substitution", 0),
        "reason": parsed.get("reason"),
    }
