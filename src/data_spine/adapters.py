"""Source adapters: turn Guesty reads and operator CSV exports into spine contract records.

Nothing here writes to a source system. `ReadOnlyGuesty` exposes only the read
calls a backfill needs; asking it for anything else raises, so a backfill can
never reach `set_rate` even by mistake.

Mapping rules (docs/data/INGESTION_MAPPING.md is the human-readable version):

- An adapter never guesses. A field it cannot map with certainty is left out,
  and the contract's validation quarantines the record with a reason.
- Guesty's reservation money is *booking* money, not settled money: every
  ledger line from it is `basis=actual, settlement_state=pending`. Settlement,
  management fees, cleaning costs and refunds come from the accounting export.
- CSV exports are mapped by a declarative mapping (column -> field, value maps,
  constants) so a new accounting layout is a new mapping file, not new code.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

from src.data_spine.contracts import CONTRACTS

GUESTY = "guesty"

# Guesty `source` -> spine channel. Anything unlisted is "other", never a guess.
CHANNEL_BY_SOURCE = {
    "airbnb": "airbnb", "airbnb2": "airbnb", "airbnb.com": "airbnb",
    "homeaway": "vrbo", "homeaway2": "vrbo", "vrbo": "vrbo",
    "booking.com": "booking_com", "bookingcom": "booking_com",
    "manual": "direct", "direct": "direct", "website": "direct", "bookingengine": "direct",
    "owner": "owner",
}
# Guesty reservation status -> spine status. Inquiries and declines are not stays.
STATUS_MAP = {"confirmed": "confirmed", "reserved": "confirmed", "checked_in": "confirmed",
              "checked_out": "confirmed", "canceled": "cancelled", "cancelled": "cancelled"}
NOT_A_STAY = frozenset({"inquiry", "declined", "expired", "awaiting_payment", "closed"})

# Spine contracts that may be loaded from an operator CSV through a mapping file.
CSV_CONTRACTS = frozenset({"financial_ledger", "owner_statement", "ops_task", "listing_constraint",
                           "market_observation"})


class ReadOnlyGuesty:
    """The read surface of GuestyClient, and nothing else.

    The client is captured only in closures over its read methods; the wrapper
    has no attribute, slot or dict that holds it (2026-10-16 audit: `ro._client`
    reached `set_rate`). Bound methods are not handed out either: each read is a
    plain function, so `ro.listings.__self__` does not exist.
    """

    __slots__ = ()
    _ALLOWED = ("listings", "listing", "calendar", "reservations", "current_rate")

    def __new__(cls, client: Any) -> "ReadOnlyGuesty":
        def reader(name: str):
            method = getattr(client, name)

            def read(*args: Any, **kwargs: Any) -> Any:
                return method(*args, **kwargs)
            read.__name__ = name
            return staticmethod(read)

        namespace = {"__slots__": (), **{n: reader(n) for n in cls._ALLOWED if hasattr(client, n)}}
        bound = type("ReadOnlyGuestyBound", (cls,), namespace)
        return object.__new__(bound)

    def __getattr__(self, name: str) -> Any:
        raise PermissionError(f"ReadOnlyGuesty: {name} is not a read call")

    def __setattr__(self, name: str, value: Any) -> None:
        raise PermissionError("ReadOnlyGuesty is immutable")


def _iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None           # a naive timestamp is ambiguous; leave it out
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _day(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def _money(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None
    return out


def guesty_reservation(raw: dict[str, Any], property_by_listing: dict[str, str], *,
                       observed_at: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    """One Guesty reservation -> (reservation record, pending ledger lines, skip reason).

    Unknown listings, inquiries and declines are skipped with a reason rather than
    quarantined: they are not stays of a home in scope.
    """
    rid = str(raw.get("_id") or "")
    status_raw = str(raw.get("status") or "").lower()
    if status_raw in NOT_A_STAY:
        return None, [], f"status {status_raw} is not a stay"
    pid = property_by_listing.get(str(raw.get("listingId") or ""))
    if pid is None:
        return None, [], "listing not in scope"
    money = raw.get("money") or {}
    source = str(raw.get("source") or "").lower()
    channel = CHANNEL_BY_SOURCE.get(source, "other")
    check_in, check_out = _day(raw.get("checkIn")), _day(raw.get("checkOut"))
    nights = raw.get("nightsCount")
    updated = _iso(raw.get("lastUpdatedAt")) or _iso(raw.get("createdAt"))
    lodging = _money(money.get("fareAccommodation"))
    cleaning = _money(money.get("fareCleaning"))
    record = {
        "source_system": GUESTY, "source_record_id": rid,
        "source_updated_at": updated, "observed_at": observed_at,
        "reservation_key": f"guesty:{rid}", "property_id": pid, "channel": channel,
        "status": STATUS_MAP.get(status_raw, status_raw or None),
        "check_in": check_in, "check_out": check_out,
        "nights": int(nights) if nights is not None else None,
        "booked_at": _iso(raw.get("confirmedAt")) or _iso(raw.get("createdAt")),
        # fareAccommodation is the whole stay's lodging before guest fees and taxes.
        "price_basis": "stay_total_ex_fees",
        "currency": str(money.get("currency") or "USD").upper(),
        "gross_lodging": lodging,
        "guest_fees": cleaning,
    }
    lines: list[dict[str, Any]] = []
    cancelled = record["status"] == "cancelled"

    def line(kind: str, amount: float | None) -> None:
        if amount is None and not cancelled:
            return
        # A cancellation re-issues the same entry keys as `reversed`, so the booking-time
        # lines of a stay that was confirmed and later cancelled stop counting.
        lines.append({
            "source_system": GUESTY, "source_record_id": rid, "source_updated_at": updated,
            "observed_at": observed_at, "entry_key": f"guesty:{rid}:{kind}",
            "reservation_key": record["reservation_key"], "property_id": pid, "channel": channel,
            "entry_type": kind, "amount": abs(amount or 0.0), "currency": record["currency"],
            "basis": "actual", "settlement_state": "reversed" if cancelled else "pending",
        })
    from src.pms.sync import _channel_commission
    line("gross_lodging", lodging)
    line("cleaning_fee_income", cleaning)
    if channel in ("airbnb", "vrbo", "booking_com"):
        line("channel_fee", _channel_commission(money))
    return record, lines, None


def guesty_calendar(days: Iterable[dict[str, Any]], property_id: str, *,
                    observed_at: str) -> Iterator[dict[str, Any]]:
    """Guesty calendar days -> calendar_observation records (nightly rate before fees)."""
    for d in days:
        status = str(d.get("status") or "").lower()
        mapped = {"available": "available", "booked": "booked", "reserved": "booked",
                  "unavailable": "blocked", "blocked": "blocked"}.get(status)
        yield {
            "source_system": GUESTY, "source_record_id": f"{property_id}:{d.get('date')}",
            "source_updated_at": observed_at, "observed_at": observed_at,
            "property_id": property_id, "stay_date": _day(d.get("date")), "status": mapped,
            "listed_price": _money(d.get("price")), "min_stay": d.get("minNights"),
            "price_basis": "nightly_ex_fees", "currency": str(d.get("currency") or "USD").upper(),
        }


# -- operator CSV exports ------------------------------------------------------------------

def load_mapping(path: Path) -> dict[str, Any]:
    """A mapping file: contract, source_system, columns {field: column}, values, constants."""
    spec = yaml.safe_load(Path(path).read_text())
    contract = spec.get("contract")
    if contract not in CSV_CONTRACTS:
        raise ValueError(f"mapping contract must be one of {sorted(CSV_CONTRACTS)}, got {contract!r}")
    known = set(CONTRACTS[contract].field_names)
    named = set(spec.get("columns", {})) | set(spec.get("constants", {}))
    unknown = named - known
    if unknown:
        raise ValueError(f"mapping names fields the {contract} contract does not have: {sorted(unknown)}")
    if not spec.get("source_system"):
        raise ValueError("mapping needs a source_system (who produced the export)")
    return spec



def csv_records(csv_path: Path, mapping: dict[str, Any], *, observed_at: str) -> Iterator[dict[str, Any]]:
    """Rows of an export -> contract records. Unmapped columns are dropped (no PII passes)."""
    contract = CONTRACTS[mapping["contract"]]
    kinds = {f.name: f.kind for f in contract.fields}
    columns: dict[str, str] = mapping.get("columns", {})
    values: dict[str, dict[str, str]] = mapping.get("values", {})
    constants: dict[str, Any] = mapping.get("constants", {})
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in columns.values() if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{Path(csv_path).name} lacks mapped columns {missing}")
        for n, row in enumerate(reader, start=2):
            rec: dict[str, Any] = {"source_system": mapping["source_system"],
                                   "source_record_id": f"{Path(csv_path).name}:{n}",
                                   "observed_at": observed_at, **constants}
            for field, column in columns.items():
                raw = row.get(column)
                raw = raw.strip() if isinstance(raw, str) else raw
                if field in values:
                    # Value maps are exhaustive: an unmapped label stays as-is and the
                    # contract quarantines it as BAD_ENUM instead of being guessed.
                    raw = values[field].get(str(raw), raw) if raw is not None else raw
                kind = kinds.get(field)
                if kind in ("money", "signed_money"):
                    m = _money(raw)
                    rec[field] = abs(m) if (kind == "money" and m is not None and mapping.get(
                        "absolute_amounts", True)) else m
                elif kind == "date":
                    rec[field] = _day(raw)
                elif kind == "timestamp":
                    rec[field] = _iso(raw) or (_iso(f"{_day(raw)}T00:00:00+00:00") if _day(raw)
                                               and mapping.get("dates_are_utc_midnight") else None)
                elif kind == "int":
                    try:
                        rec[field] = int(float(raw)) if raw not in (None, "") else None
                    except ValueError:
                        rec[field] = raw
                else:
                    rec[field] = raw if raw != "" else None
            prefix = mapping.get("reservation_key_prefix")
            if prefix and rec.get("reservation_key") and not str(rec["reservation_key"]).startswith(prefix):
                rec["reservation_key"] = f"{prefix}{rec['reservation_key']}"
            rec.setdefault("source_updated_at", observed_at)
            yield rec


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
