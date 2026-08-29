"""Guesty Open API client — verified against the live tenant on 2026-08-29.

Endpoint paths here are the ones the API actually serves, not the ones the docs
imply. In particular the calendar does NOT live at /v1/listings/{id}/calendar; it is
/v1/availability-pricing/api/calendar/listings/{id}. Getting that wrong fails closed
(404) rather than silently, but it is worth pinning in a comment.

Auth: OAuth2 client-credentials, scope 'open-api'. Tokens last 24h and the token
endpoint is rate-limited, so the token is cached to disk across processes — a daily
cron that re-authenticates on every invocation will eventually get throttled.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

TOKEN_URL = "https://open-api.guesty.com/oauth2/token"
BASE = "https://open-api.guesty.com"
# NB: Path("") is Path(".") and therefore truthy, so an `or` fallback here silently
# resolves the cache to the CWD. Test the env var, not the Path.
_TOKEN_CACHE_ENV = os.environ.get("GUESTY_TOKEN_CACHE", "").strip()
TOKEN_CACHE = (
    Path(_TOKEN_CACHE_ENV) if _TOKEN_CACHE_ENV
    else Path(__file__).resolve().parents[2] / "data" / ".guesty_token.json"
)


def load_dotenv(path: Path | str | None = None) -> None:
    """Minimal .env loader so credentials never have to live in source or shell history."""
    p = Path(path) if path else Path(__file__).resolve().parents[2] / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class GuestyListing:
    listing_id: str
    nickname: str
    title: str
    bedrooms: int | None
    bathrooms: float | None
    accommodates: int | None
    base_price: float | None
    weekend_base_price: float | None
    cleaning_fee: float | None
    min_nights: int | None
    address: str | None
    city: str | None
    lat: float | None
    lng: float | None
    timezone: str
    active: bool
    amenities: list[str]

    @property
    def property_id(self) -> str:
        """Stable ASCII slug used as our internal property_id.

        ASCII-folded deliberately: str.isalnum() is True for accented characters, so a
        naive filter yields non-ASCII ids that then leak into filenames, CLI args and
        URLs. Falls back to the listing id if nothing survives folding.
        """
        import unicodedata

        raw = (self.nickname or self.title or self.listing_id).lower()
        folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
        slug = "".join(c if c.isalnum() else "_" for c in folded)
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug.strip("_")[:40] or self.listing_id


class GuestyClient:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None,
                 timeout: int = 30, use_token_cache: bool = True):
        load_dotenv()
        self.client_id = client_id or os.environ.get("GUESTY_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GUESTY_CLIENT_SECRET", "")
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Missing GUESTY_CLIENT_ID / GUESTY_CLIENT_SECRET. Put them in .env "
                "(see .env.example) or export them."
            )
        self.timeout = timeout
        self.use_token_cache = use_token_cache
        self._token: str | None = None
        self._expires_at = 0.0

    # -- auth ---------------------------------------------------------------
    def _cached_token(self) -> str | None:
        if not self.use_token_cache or not TOKEN_CACHE.exists():
            return None
        try:
            blob = json.loads(TOKEN_CACHE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if blob.get("client_id") != self.client_id:
            return None
        if time.time() > float(blob.get("expires_at", 0)) - 300:
            return None
        self._expires_at = float(blob["expires_at"])
        return blob.get("access_token")

    def _store_token(self, token: str, expires_in: float) -> None:
        if not self.use_token_cache:
            return
        TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_CACHE.write_text(json.dumps({
            "client_id": self.client_id, "access_token": token,
            "expires_at": time.time() + expires_in,
        }))
        try:
            TOKEN_CACHE.chmod(0o600)
        except OSError:
            pass

    def token(self) -> str:
        if self._token and time.time() < self._expires_at - 300:
            return self._token
        cached = self._cached_token()
        if cached:
            self._token = cached
            return cached
        import requests

        resp = requests.post(TOKEN_URL, data={
            "grant_type": "client_credentials", "scope": "open-api",
            "client_id": self.client_id, "client_secret": self.client_secret,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        expires_in = float(payload.get("expires_in", 86400))
        self._expires_at = time.time() + expires_in
        self._store_token(self._token, expires_in)
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}", "Accept": "application/json",
                "Content-Type": "application/json"}

    def _get(self, path: str, **params: Any) -> Any:
        import requests

        resp = requests.get(f"{BASE}{path}", headers=self._headers(),
                            params=params or None, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # -- listings -----------------------------------------------------------
    def listings(self, include_inactive: bool = False) -> list[GuestyListing]:
        out: list[GuestyListing] = []
        skip, limit = 0, 100
        while True:
            body = self._get("/v1/listings", limit=limit, skip=skip)
            results = body.get("results", [])
            for raw in results:
                if not include_inactive and not raw.get("active", True):
                    continue
                out.append(self._parse_listing(raw))
            skip += limit
            if skip >= int(body.get("count", 0)) or not results:
                break
        return out

    def listing(self, listing_id: str) -> GuestyListing:
        return self._parse_listing(self._get(f"/v1/listings/{listing_id}"))

    @staticmethod
    def _parse_listing(raw: dict[str, Any]) -> GuestyListing:
        prices = raw.get("prices") or {}
        terms = raw.get("terms") or {}
        addr = raw.get("address") or {}
        return GuestyListing(
            listing_id=raw["_id"],
            nickname=raw.get("nickname") or "",
            title=raw.get("title") or "",
            bedrooms=raw.get("bedrooms"),
            bathrooms=raw.get("bathrooms"),
            accommodates=raw.get("accommodates"),
            base_price=prices.get("basePrice"),
            weekend_base_price=prices.get("weekendBasePrice"),
            cleaning_fee=prices.get("cleaningFee"),
            min_nights=terms.get("minNights"),
            address=addr.get("full"),
            city=addr.get("city"),
            lat=addr.get("lat"),
            lng=addr.get("lng"),
            timezone=raw.get("timezone") or "America/Denver",
            active=bool(raw.get("active", True)),
            amenities=list(raw.get("amenities") or []),
        )

    # -- calendar -----------------------------------------------------------
    def calendar(self, listing_id: str, start: date, end: date) -> list[dict[str, Any]]:
        """Nightly price / status / min-nights. NOTE the availability-pricing path."""
        body = self._get(
            f"/v1/availability-pricing/api/calendar/listings/{listing_id}",
            startDate=start.isoformat(), endDate=end.isoformat(),
        )
        return (body.get("data") or {}).get("days") or []

    # -- reservations -------------------------------------------------------
    def reservations(self, limit: int = 100) -> Iterator[dict[str, Any]]:
        fields = ("_id listingId checkIn checkOut nightsCount status source "
                  "confirmedAt money.fareAccommodation money.hostPayout")
        skip = 0
        while True:
            body = self._get("/v1/reservations", limit=limit, skip=skip, fields=fields)
            results = body.get("results", [])
            yield from results
            skip += limit
            if skip >= int(body.get("count", 0)) or not results:
                break

    # -- write --------------------------------------------------------------
    def set_rate(self, listing_id: str, stay_date: date, price: float,
                 min_nights: int | None = None) -> tuple[bool, str | None]:
        """Write one night's rate. Returns (ok, error).

        Guesty applies the change to the inclusive [startDate, endDate] range, so a
        single night is expressed as the same date twice.
        """
        import requests

        body: dict[str, Any] = {
            "startDate": stay_date.isoformat(),
            "endDate": stay_date.isoformat(),
            "price": round(float(price), 2),
        }
        if min_nights is not None:
            body["minNights"] = int(min_nights)
        try:
            resp = requests.put(
                f"{BASE}/v1/availability-pricing/api/calendar/listings/{listing_id}",
                json=body, headers=self._headers(), timeout=self.timeout,
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — must be recorded, never raised into the run
            return False, f"{type(exc).__name__}: {str(exc)[:200]}"
        return True, None


def parse_guesty_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
