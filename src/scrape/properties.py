"""Scrape owned listings into nightly_inventory (no PMS required)."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from src.scrape import plan_windows
from src.scrape.providers import CompProvider, Listing


# Heuristics for auto-discovery of the operator's twin listings on N Woods Pl.
_DISCOVERY_RULES: dict[str, list[str]] = {
    "summit_haus": [
        r"summit\s*haus",
        r"312\s*n\.?\s*woods",
        r"312\s*n\s*woods",
    ],
    "overlook_ridge": [
        r"overlook\s*ridge",
        r"300\s*n\.?\s*woods",
        r"300\s*n\s*woods",
    ],
}

# When owned listings are direct-book only (not on Airbnb), fall back to the best
# luxury 5BR+ proxy visible in the market sweep. Twins share one proxy curve.
_PROXY_NAME_HINTS = ("5br", "5 br", "luxury", "lakota", "northwood", "sleeps 1")


def _pick_luxury_proxy(listings: list[Listing], min_price: float = 1100.0) -> Listing | None:
    cands = [
        l for l in listings
        if l.nightly_price and l.nightly_price >= min_price
    ]
    if not cands:
        return None

    def _score(l: Listing) -> tuple[int, float]:
        name = _norm(l.name)
        hint = sum(1 for h in _PROXY_NAME_HINTS if h in name)
        return (hint, float(l.nightly_price or 0))

    cands.sort(key=_score, reverse=True)
    return cands[0]


@dataclass
class DiscoveryMatch:
    property_id: str
    room_id: str
    name: str | None
    nightly_price: float | None
    score: int


@dataclass
class PropertyScrapeReport:
    property_id: str
    room_id: str
    nights_written: int = 0
    nights_with_price: int = 0
    nights_available: int = 0
    nights_booked: int = 0
    nights_blocked: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ScrapePropertiesReport:
    properties: list[PropertyScrapeReport] = field(default_factory=list)
    discovery: list[DiscoveryMatch] = field(default_factory=list)
    sweeps_ok: int = 0
    sweeps_failed: int = 0

    @property
    def total_nights(self) -> int:
        return sum(p.nights_written for p in self.properties)


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def score_listing(property_id: str, name: str | None) -> int:
    """Return match score; 0 means no match."""
    text = _norm(name)
    if not text:
        return 0
    best = 0
    for pattern in _DISCOVERY_RULES.get(property_id, []):
        if re.search(pattern, text):
            best = max(best, 10 if "haus" in pattern or "ridge" in pattern else 5)
    if "n woods" in text and property_id in {"summit_haus", "overlook_ridge"}:
        best = max(best, 3)
    return best


def discover_owned_listings(
    provider: CompProvider,
    check_ins: list[date],
    nights: int = 2,
    min_price: float = 300.0,
    property_ids: list[str] | None = None,
    *,
    allow_proxy_fallback: bool = True,
) -> list[DiscoveryMatch]:
    """Search market sweeps and match owned listings by name heuristics."""
    targets = property_ids or list(_DISCOVERY_RULES.keys())
    best: dict[str, DiscoveryMatch] = {}
    all_listings: list[Listing] = []

    for check_in in check_ins:
        sweep = provider.sweep(check_in, nights)
        if not sweep.ok:
            continue
        all_listings.extend(sweep.listings)
        for listing in sweep.listings:
            if listing.nightly_price is not None and listing.nightly_price < min_price:
                continue
            for pid in targets:
                score = score_listing(pid, listing.name)
                if score <= 0:
                    continue
                prev = best.get(pid)
                if prev is None or score > prev.score:
                    best[pid] = DiscoveryMatch(
                        property_id=pid,
                        room_id=listing.room_id,
                        name=listing.name,
                        nightly_price=listing.nightly_price,
                        score=score,
                    )
                elif prev and score == prev.score and listing.room_id != prev.room_id:
                    if (listing.nightly_price or 0) > (prev.nightly_price or 0):
                        best[pid] = DiscoveryMatch(
                            property_id=pid,
                            room_id=listing.room_id,
                            name=listing.name,
                            nightly_price=listing.nightly_price,
                            score=score,
                        )

    missing = [pid for pid in targets if pid not in best]
    if missing and allow_proxy_fallback:
        proxy = _pick_luxury_proxy(all_listings, min_price=max(min_price, 1100.0))
        if proxy:
            for pid in missing:
                best[pid] = DiscoveryMatch(
                    property_id=pid,
                    room_id=proxy.room_id,
                    name=f"PROXY:{proxy.name}",
                    nightly_price=proxy.nightly_price,
                    score=1,
                )

    return [best[pid] for pid in targets if pid in best]


def persist_room_ids(conn: sqlite3.Connection, matches: list[DiscoveryMatch]) -> int:
    for m in matches:
        conn.execute(
            "UPDATE properties SET airbnb_room_id = ? WHERE property_id = ?",
            (m.room_id, m.property_id),
        )
    conn.commit()
    return len(matches)


def _owned_index(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """room_id -> property_ids (twins may share one Airbnb listing)."""
    out: dict[str, list[str]] = {}
    for r in conn.execute(
        "SELECT property_id, airbnb_room_id FROM properties "
        "WHERE airbnb_room_id IS NOT NULL AND airbnb_room_id != ''"
    ).fetchall():
        out.setdefault(str(r["airbnb_room_id"]), []).append(r["property_id"])
    return out


def _fill_price_gaps(prices: dict[date, float], start: date, end: date) -> dict[date, float]:
    """Forward-fill unpriced nights from the nearest same-DOW observation."""
    out = dict(prices)
    for stay in _dates_in_range(start, end):
        if stay in out:
            continue
        dow = stay.weekday()
        best: tuple[int, float] | None = None
        for d, p in prices.items():
            if d.weekday() != dow:
                continue
            dist = abs((d - stay).days)
            if best is None or dist < best[0]:
                best = (dist, p)
        if best:
            out[stay] = best[1]
    return out


def _dates_in_range(start: date, end: date) -> list[date]:
    nights: list[date] = []
    cur = start
    while cur <= end:
        nights.append(cur)
        cur += timedelta(days=1)
    return nights


def _apply_sweep_prices(
    prices: dict[str, dict[date, float]],
    sweep_check_in: date,
    nights: int,
    listing: Listing,
    room_to_property: dict[str, str],
) -> None:
    pid = room_to_property.get(listing.room_id)
    if pid is None or listing.nightly_price is None:
        return
    bucket = prices.setdefault(pid, {})
    for i in range(nights):
        bucket[sweep_check_in + timedelta(days=i)] = float(listing.nightly_price)


def _calendar_status(info: dict[str, Any]) -> str:
    if info.get("available"):
        return "available"
    return "booked"


def scrape_properties(
    conn: sqlite3.Connection,
    provider: CompProvider,
    start: date,
    end: date,
    *,
    policy: dict[str, Any] | None = None,
    discover: bool = False,
    discover_dates: list[date] | None = None,
) -> ScrapePropertiesReport:
    """Populate nightly_inventory for owned listings via calendar + market sweeps."""
    from src.config import load_policy
    from src.pms.sync import SyncReport, recalibrate_bounds

    policy = policy or load_policy()
    cfg = policy.get("scrape", {})
    window_nights = int(cfg.get("window_nights", 2))
    report = ScrapePropertiesReport()

    if discover:
        d_dates = discover_dates or [
            start + timedelta(days=17),
            start + timedelta(days=23),
            start + timedelta(days=4),
        ]
        matches = discover_owned_listings(provider, d_dates, nights=window_nights)
        report.discovery = matches
        persist_room_ids(conn, matches)

    room_to_properties = _owned_index(conn)
    if not room_to_properties:
        return report

    room_ids = sorted(room_to_properties.keys())
    prices_by_room: dict[str, dict[date, float]] = {}

    pad_start = start - timedelta(days=7)
    horizon = (end - pad_start).days + 7
    windows = plan_windows(pad_start, horizon, window_nights)

    for check_in in windows:
        if check_in > end:
            continue
        sweep = provider.sweep(check_in, window_nights)
        if not sweep.ok:
            report.sweeps_failed += 1
            continue
        report.sweeps_ok += 1
        for listing in sweep.listings:
            if listing.room_id not in room_ids:
                continue
            bucket = prices_by_room.setdefault(listing.room_id, {})
            for i in range(window_nights):
                d = check_in + timedelta(days=i)
                if start <= d <= end and listing.nightly_price is not None:
                    bucket[d] = float(listing.nightly_price)

    today = date.today()

    for room_id in room_ids:
        property_ids_for_room = room_to_properties[room_id]
        cal = provider.calendar(room_id)
        room_prices = _fill_price_gaps(prices_by_room.get(room_id, {}), start, end)

        for property_id in property_ids_for_room:
            prop_report = PropertyScrapeReport(property_id=property_id, room_id=room_id)

            for stay in _dates_in_range(start, end):
                iso = stay.isoformat()
                info = cal.get(iso, {})
                status = _calendar_status(info) if info else "available"
                listed = room_prices.get(stay)
                lead = (stay - today).days if stay >= today else None

                conn.execute(
                    """
                    INSERT INTO nightly_inventory (
                        property_id, stay_date, listed_price, booked_price, status,
                        lead_time_days, day_of_week, channel, min_stay, updated_at
                    ) VALUES (?, ?, ?, NULL, ?, ?, ?, 'airbnb_scrape', ?, datetime('now'))
                    ON CONFLICT(property_id, stay_date) DO UPDATE SET
                        listed_price=COALESCE(excluded.listed_price, nightly_inventory.listed_price),
                        status=excluded.status,
                        lead_time_days=excluded.lead_time_days,
                        day_of_week=excluded.day_of_week,
                        channel='airbnb_scrape',
                        min_stay=COALESCE(excluded.min_stay, nightly_inventory.min_stay),
                        updated_at=datetime('now')
                    """,
                    (
                        property_id,
                        iso,
                        listed,
                        status,
                        lead,
                        stay.weekday(),
                        info.get("min_nights") if info else None,
                    ),
                )
                prop_report.nights_written += 1
                if listed is not None:
                    prop_report.nights_with_price += 1
                if status == "available":
                    prop_report.nights_available += 1
                elif status == "booked":
                    prop_report.nights_booked += 1
                else:
                    prop_report.nights_blocked += 1

            if not cal:
                prop_report.errors.append(
                    "calendar API returned no data — status defaults to available"
                )
            if prop_report.nights_with_price == 0:
                prop_report.errors.append("no prices from market sweeps for this listing")
            if any(m.name and m.name.startswith("PROXY:") for m in report.discovery
                   if m.property_id == property_id):
                prop_report.errors.append(
                    "using luxury market proxy — subject listing not found on Airbnb"
                )

            report.properties.append(prop_report)

    conn.commit()
    recalibrate_bounds(conn, SyncReport())
    return report
