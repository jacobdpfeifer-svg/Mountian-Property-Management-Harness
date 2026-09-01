"""Winter Park / Vail Resorts mountain report HTML extractor."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

_USER_AGENT = "wp-price-signals/1.0 (resort-conditions)"


def _pct(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return float(m.group(1)) if m else None


def _int_after(label: str, text: str) -> float | None:
    m = re.search(rf"{re.escape(label)}\s*[:\s]*(\d+)", text, re.I)
    return float(m.group(1)) if m else None


def parse_resort_html(html: str, *, source_url: str | None = None) -> dict[str, Any]:
    """Parse a mountain-report page into ResortCollector field names."""
    data: dict[str, Any] = {"source_url": source_url}

    # Embedded JSON (Next.js / CMS payloads common on Vail Resorts sites).
    for pattern in (
        r'<script[^>]*type="application/json"[^>]*>(\{.*?\})</script>',
        r"__NEXT_DATA__\s*=\s*(\{.*?\})\s*;",
    ):
        for match in re.finditer(pattern, html, re.S):
            try:
                payload = json.loads(match.group(1))
                flat = json.dumps(payload).lower()
                tp = _pct(flat) or _pct(str(payload))
                if tp is not None and "terrain_open_pct" not in data:
                    data["terrain_open_pct"] = tp
            except json.JSONDecodeError:
                continue

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    if "terrain_open_pct" not in data:
        for pat in (
            r"(\d+(?:\.\d+)?)\s*%\s*of\s*terrain\s*open",
            r"terrain\s*open\s*[:\s]*(\d+(?:\.\d+)?)\s*%",
            r"open\s*terrain\s*[:\s]*(\d+(?:\.\d+)?)\s*%",
        ):
            m = re.search(pat, text, re.I)
            if m:
                data["terrain_open_pct"] = float(m.group(1))
                break

    if "lifts_open" not in data:
        v = _int_after("lifts open", text) or _int_after("open lifts", text)
        if v is not None:
            data["lifts_open"] = v

    if "trails_open" not in data:
        v = _int_after("trails open", text) or _int_after("open trails", text)
        if v is not None:
            data["trails_open"] = v

    if "base_depth_in" not in data:
        m = re.search(r"base\s*(?:depth|snow)\s*[:\s]*(\d+)\s*\"", text, re.I)
        if m:
            data["base_depth_in"] = float(m.group(1))

    if "lift_ticket_window_usd" not in data:
        m = re.search(r"\$(\d{2,4})\s*(?:window|lift\s*ticket)", text, re.I)
        if m:
            data["lift_ticket_window_usd"] = float(m.group(1))

    if data.get("terrain_open_pct") is None:
        lifts = data.get("lifts_open")
        trails = data.get("trails_open")
        if lifts is not None and lifts == 0:
            data["terrain_open_pct"] = 0.0

    if data.get("terrain_open_pct") is None:
        raise ValueError("could not parse terrain_open_pct from mountain report")

    return data


def fetch_resort_report(
    url: str,
    *,
    timeout_s: float = 30.0,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    sess = session or requests.Session()
    resp = sess.get(url, headers={"User-Agent": _USER_AGENT}, timeout=timeout_s)
    resp.raise_for_status()
    return parse_resort_html(resp.text, source_url=url)
