"""Comp data providers.

Priority order is configured, not hardcoded, so the operator can move from the free
scraper to a paid feed without touching pricing logic (docs/LOCKED_INPUTS.md keeps
that hybrid explicitly open).

  airbnb_sweep — one market-wide search per date window. ~1 request returns every
                 bookable listing in the bounding box with a parseable nightly rate,
                 so this is dramatically cheaper and less block-prone than N per-comp
                 requests, and it yields the full market distribution for free.
  fixture      — replays recorded JSON. Used by the tests so the whole pipeline is
                 verifiable offline without touching the network.
  manual       — operator-entered CSV (src/ingest). Always available as a floor.
"""

from __future__ import annotations

import json
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.scrape.parse import nightly_price


@dataclass
class Listing:
    room_id: str
    nightly_price: float | None
    name: str | None = None
    bedrooms: int | None = None
    sleeps: int | None = None
    rating: float | None = None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _listing_size(item: dict[str, Any]) -> tuple[int | None, int | None]:
    """Best-effort bedrooms / sleeps from Airbnb search payloads."""
    room = item.get("room") if isinstance(item.get("room"), dict) else {}
    bedrooms = _int_or_none(
        item.get("bedrooms") or item.get("beds") or room.get("bedrooms")
    )
    sleeps = _int_or_none(
        item.get("personCapacity")
        or item.get("person_capacity")
        or item.get("sleeps")
        or item.get("guests")
        or room.get("personCapacity")
    )
    return bedrooms, sleeps


@dataclass
class SweepResult:
    check_in: date
    nights: int
    listings: list[Listing]
    ok: bool
    error: str | None = None

    @property
    def stay_dates(self) -> list[date]:
        return [self.check_in + timedelta(days=i) for i in range(self.nights)]


class CompProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def sweep(self, check_in: date, nights: int) -> SweepResult: ...

    def calendar(self, room_id: str) -> dict[str, dict[str, Any]]:
        """Optional: {ISO date -> {available, min_nights}}. Empty when unsupported."""
        return {}


class PyAirbnbProvider(CompProvider):
    """Live Airbnb market sweep via pyairbnb (MIT, curl_cffi TLS impersonation).

    Rate limiting is deliberately conservative by default. Politeness here is both
    correct engineering and the main thing keeping the source usable: an aggressive
    sweep gets the IP blocked and the whole comp layer degrades to advisory.
    """

    name = "airbnb_sweep"

    def __init__(self, bbox: dict[str, float], policy: dict[str, Any],
                 proxy_url: str = "", currency: str = "USD"):
        self.bbox = bbox
        self.currency = currency
        self.proxy_url = proxy_url
        cfg = policy.get("scrape", {})
        self.min_delay = float(cfg.get("min_request_delay_s", 4.0))
        self.max_delay = float(cfg.get("max_request_delay_s", 8.0))
        self.zoom = int(cfg.get("zoom", 14))
        self.timeout = int(cfg.get("timeout_s", 60))
        self._api_key: str | None = None
        self._last_request = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request
        wait = random.uniform(self.min_delay, self.max_delay) - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.time()

    def _key(self) -> str:
        import pyairbnb

        if self._api_key is None:
            self._api_key = pyairbnb.get_api_key(self.proxy_url)
        return self._api_key

    def sweep(self, check_in: date, nights: int) -> SweepResult:
        try:
            import pyairbnb
        except ImportError:
            return SweepResult(check_in, nights, [], False,
                               "pyairbnb not installed (pip install '.[scrape]')")
        check_out = check_in + timedelta(days=nights)
        self._throttle()
        try:
            raw = pyairbnb.search_all(
                check_in.isoformat(), check_out.isoformat(),
                self.bbox["ne_lat"], self.bbox["ne_lng"],
                self.bbox["sw_lat"], self.bbox["sw_lng"],
                self.zoom, 0, 0,
                currency=self.currency, language="en",
                proxy_url=self.proxy_url, timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001 - any failure must degrade, never raise
            return SweepResult(check_in, nights, [], False, f"{type(exc).__name__}: {exc}")

        # Airbnb's paginated search overlaps: the same room_id can appear more than
        # once in a sweep. Left un-deduplicated it double-counts in the market
        # percentile and inflates the listings-seen validation counter.
        listings: list[Listing] = []
        seen: set[str] = set()
        for item in raw:
            room_id = item.get("room_id")
            if room_id is None or str(room_id) in seen:
                continue
            seen.add(str(room_id))
            rating = item.get("rating")
            bedrooms, sleeps = _listing_size(item)
            listings.append(Listing(
                room_id=str(room_id),
                nightly_price=nightly_price(item, nights),
                name=str(item.get("name") or "") or None,
                bedrooms=bedrooms,
                sleeps=sleeps,
                rating=rating.get("value") if isinstance(rating, dict) else None,
            ))
        return SweepResult(check_in, nights, listings, True)

    def calendar(self, room_id: str) -> dict[str, dict[str, Any]]:
        """12 months of availability + min-nights in one request."""
        try:
            import pyairbnb
        except ImportError:
            return {}
        self._throttle()
        try:
            months = pyairbnb.get_calendar(api_key=self._key(), room_id=str(room_id))
        except Exception:  # noqa: BLE001
            return {}
        out: dict[str, dict[str, Any]] = {}
        for month in months or []:
            for day in month.get("days", []) or []:
                d = day.get("calendarDate")
                if d:
                    out[str(d)] = {
                        "available": bool(day.get("available")),
                        "min_nights": day.get("minNights"),
                    }
        return out


class FixtureProvider(CompProvider):
    """Replays recorded sweeps so the pipeline is testable without the network."""

    name = "fixture"

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._data = json.loads(self.path.read_text(encoding="utf-8"))

    def sweep(self, check_in: date, nights: int) -> SweepResult:
        raw = self._data.get("sweeps", {}).get(check_in.isoformat())
        if raw is None:
            return SweepResult(check_in, nights, [], False, "no fixture for this window")
        listings: list[Listing] = []
        seen: set[str] = set()
        for x in raw:
            if str(x["room_id"]) in seen:
                continue
            seen.add(str(x["room_id"]))
            listings.append(Listing(
                str(x["room_id"]),
                x.get("nightly_price"),
                x.get("name"),
                bedrooms=_int_or_none(x.get("bedrooms")),
                sleeps=_int_or_none(x.get("sleeps") or x.get("personCapacity")),
            ))
        return SweepResult(check_in, nights, listings, True)

    def calendar(self, room_id: str) -> dict[str, dict[str, Any]]:
        return self._data.get("calendars", {}).get(str(room_id), {})


PROVIDERS = {
    "airbnb_sweep": PyAirbnbProvider,
    "fixture": FixtureProvider,
}
