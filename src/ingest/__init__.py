"""Ingest adapters — CSV / iCal → DB."""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from icalendar import Calendar

from src.utils import parse_date


class IngestAdapter(ABC):
    """Thin interface so a PMS API can plug in later without rewriting loaders."""

    @abstractmethod
    def load_properties(self, conn: sqlite3.Connection) -> int: ...

    @abstractmethod
    def load_inventory(self, conn: sqlite3.Connection) -> int: ...


def _room_id(row: dict[str, Any]) -> str | None:
    """Airbnb room id, taken directly or parsed out of a listing URL."""
    explicit = str(row.get("airbnb_room_id") or "").strip()
    if explicit:
        return explicit
    url = str(row.get("source_url") or "")
    m = re.search(r"/rooms/(?:plus/)?(\d+)", url)
    return m.group(1) if m else None


def _json_list(value: Any) -> str:
    if value is None or value == "":
        return "[]"
    if isinstance(value, list):
        return json.dumps(value)
    text = str(value).strip()
    if text.startswith("["):
        return text
    parts = [p.strip() for p in text.split("|") if p.strip()]
    return json.dumps(parts)


def upsert_property(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO properties (
            property_id, name, bedrooms, bathrooms, amenities,
            base_ceiling_rate, min_floor_rate, max_ceiling_rate,
            luxury_tier, target_alos, timezone
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(property_id) DO UPDATE SET
            name=excluded.name,
            bedrooms=excluded.bedrooms,
            bathrooms=excluded.bathrooms,
            amenities=excluded.amenities,
            base_ceiling_rate=excluded.base_ceiling_rate,
            min_floor_rate=excluded.min_floor_rate,
            max_ceiling_rate=excluded.max_ceiling_rate,
            luxury_tier=excluded.luxury_tier,
            target_alos=excluded.target_alos,
            timezone=excluded.timezone
        """,
        (
            row["property_id"],
            row["name"],
            int(row["bedrooms"]),
            float(row["bathrooms"]),
            _json_list(row.get("amenities")),
            float(row["base_ceiling_rate"]),
            float(row["min_floor_rate"]),
            float(row["max_ceiling_rate"]),
            row.get("luxury_tier") or "luxury",
            float(row.get("target_alos") or 3.0),
            row.get("timezone") or "America/Denver",
        ),
    )


def upsert_inventory(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    stay = parse_date(row["stay_date"])
    status = str(row["status"]).strip().lower()
    if status not in {"available", "booked", "blocked"}:
        raise ValueError(f"Invalid status: {status}")
    lead = row.get("lead_time_days")
    lead_i = int(lead) if lead not in (None, "") else None
    listed = row.get("listed_price")
    booked = row.get("booked_price")
    conn.execute(
        """
        INSERT INTO nightly_inventory (
            property_id, stay_date, listed_price, booked_price, status,
            lead_time_days, day_of_week, channel, reservation_id, min_stay
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(property_id, stay_date) DO UPDATE SET
            -- COALESCE: a source that does not carry prices (iCal) must never
            -- erase a price loaded from one that does. v1 overwrote with NULL,
            -- so running the iCal adapter after the CSV adapter silently
            -- destroyed every listed_price for that property.
            listed_price=COALESCE(excluded.listed_price, nightly_inventory.listed_price),
            booked_price=COALESCE(excluded.booked_price, nightly_inventory.booked_price),
            status=excluded.status,
            lead_time_days=COALESCE(excluded.lead_time_days, nightly_inventory.lead_time_days),
            day_of_week=excluded.day_of_week,
            channel=excluded.channel,
            reservation_id=COALESCE(excluded.reservation_id, nightly_inventory.reservation_id),
            min_stay=COALESCE(excluded.min_stay, nightly_inventory.min_stay),
            updated_at=datetime('now')
        """,
        (
            row["property_id"],
            stay.isoformat(),
            float(listed) if listed not in (None, "") else None,
            float(booked) if booked not in (None, "") else None,
            status,
            lead_i,
            stay.weekday(),
            row.get("channel") or None,
            row.get("reservation_id") or None,
            int(row["min_stay"]) if row.get("min_stay") not in (None, "") else None,
        ),
    )


class CsvIngestAdapter(IngestAdapter):
    def __init__(
        self,
        properties_csv: Path | str,
        inventory_csv: Path | str,
        comps_csv: Path | str | None = None,
        demand_csv: Path | str | None = None,
        inquiries_csv: Path | str | None = None,
    ):
        self.properties_csv = Path(properties_csv)
        self.inventory_csv = Path(inventory_csv)
        self.comps_csv = Path(comps_csv) if comps_csv else None
        self.demand_csv = Path(demand_csv) if demand_csv else None
        self.inquiries_csv = Path(inquiries_csv) if inquiries_csv else None

    def load_properties(self, conn: sqlite3.Connection) -> int:
        n = 0
        with self.properties_csv.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                upsert_property(conn, row)
                n += 1
        return n

    def load_inventory(self, conn: sqlite3.Connection) -> int:
        n = 0
        with self.inventory_csv.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                upsert_inventory(conn, row)
                n += 1
        return n

    def load_comps(self, conn: sqlite3.Connection) -> int:
        if not self.comps_csv or not self.comps_csv.exists():
            return 0
        n = 0
        with self.comps_csv.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                conn.execute(
                    """
                    INSERT INTO comps (comp_id, name, bedrooms, bathrooms, amenities,
                        notes, source_url, platform, airbnb_room_id, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(comp_id) DO UPDATE SET
                        name=excluded.name,
                        bedrooms=excluded.bedrooms,
                        bathrooms=excluded.bathrooms,
                        amenities=excluded.amenities,
                        notes=excluded.notes,
                        source_url=excluded.source_url,
                        platform=excluded.platform,
                        airbnb_room_id=COALESCE(excluded.airbnb_room_id, comps.airbnb_room_id),
                        active=excluded.active
                    """,
                    (
                        row["comp_id"],
                        row["name"],
                        int(row["bedrooms"]) if row.get("bedrooms") else None,
                        float(row["bathrooms"]) if row.get("bathrooms") else None,
                        _json_list(row.get("amenities")),
                        row.get("notes"),
                        row.get("source_url"),
                        row.get("platform") or "airbnb",
                        _room_id(row),
                        0 if str(row.get("active", "1")).lower() in {"0", "false", "no"} else 1,
                    ),
                )
                prop_ids = [p.strip() for p in (row.get("for_properties") or "").split("|") if p.strip()]
                for pid in prop_ids:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO comp_set_members (property_id, comp_id)
                        VALUES (?, ?)
                        """,
                        (pid, row["comp_id"]),
                    )
                if row.get("listed_price") not in (None, ""):
                    conn.execute(
                        """
                        INSERT INTO comp_snapshots (
                            comp_id, as_of, stay_date, listed_price, available, source, capture_method
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(comp_id, as_of, stay_date) DO UPDATE SET
                            listed_price=excluded.listed_price, available=excluded.available,
                            source=excluded.source, capture_method=excluded.capture_method
                        """,
                        (
                            row["comp_id"],
                            row.get("as_of") or date.today().isoformat(),
                            row.get("stay_date") or None,
                            float(row["listed_price"]),
                            1 if str(row.get("available", "1")).lower() in {"1", "true", "yes"} else 0,
                            row.get("source") or "manual",
                            "operator_entry",
                        ),
                    )
                n += 1
        return n

    def load_demand(self, conn: sqlite3.Connection) -> int:
        if not self.demand_csv or not self.demand_csv.exists():
            return 0
        n = 0
        with self.demand_csv.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                conn.execute(
                    """
                    INSERT INTO demand_signals (
                        signal_date, region, event_name, signal_strength, source
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(signal_date, region, event_name) DO UPDATE SET
                        signal_strength=excluded.signal_strength, source=excluded.source
                    """,
                    (
                        parse_date(row["signal_date"]).isoformat(),
                        row.get("region") or "winter_park",
                        row["event_name"],
                        float(row["signal_strength"]),
                        row.get("source") or "manual",
                    ),
                )
                n += 1
        return n

    def load_inquiries(self, conn: sqlite3.Connection) -> int:
        if not self.inquiries_csv or not self.inquiries_csv.exists():
            return 0
        n = 0
        with self.inquiries_csv.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                conn.execute(
                    """
                    INSERT INTO booking_inquiries (
                        property_id, inquiry_date, stay_date, inquiry_count, quote_shown,
                        converted, external_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(property_id, inquiry_date, stay_date, external_id)
                    DO UPDATE SET inquiry_count=excluded.inquiry_count,
                        quote_shown=excluded.quote_shown, converted=excluded.converted
                    """,
                    (
                        row["property_id"],
                        parse_date(row["inquiry_date"]).isoformat(),
                        parse_date(row["stay_date"]).isoformat() if row.get("stay_date") else None,
                        int(row.get("inquiry_count") or 1),
                        float(row["quote_shown"]) if row.get("quote_shown") not in (None, "") else None,
                        1 if str(row.get("converted", "0")).lower() in {"1", "true", "yes"} else 0,
                        row.get("external_id") or "",
                    ),
                )
                n += 1
        return n

    def load_all(self, conn: sqlite3.Connection) -> dict[str, int]:
        counts = {
            "properties": self.load_properties(conn),
            "inventory": self.load_inventory(conn),
            "comps": self.load_comps(conn),
            "demand": self.load_demand(conn),
            "inquiries": self.load_inquiries(conn),
        }
        conn.commit()
        return counts


class ICalIngestAdapter:
    """Import blocked/booked ranges from an iCal feed into nightly_inventory.

    Does not set prices — use CSV for rates. Marks nights as booked (SUMMARY contains
    'Reserved'/'Booked') or blocked otherwise when VEVENT covers the date.
    """

    def __init__(self, property_id: str, ical_path: Path | str, default_listed_price: float | None = None):
        self.property_id = property_id
        self.ical_path = Path(ical_path)
        self.default_listed_price = default_listed_price

    @staticmethod
    def _as_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        # Accept both RFC5545 compact (YYYYMMDD) and ISO (YYYY-MM-DD)
        if len(text) == 8 and text.isdigit():
            return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
        return parse_date(text)

    def _events(self) -> Iterable[tuple[date, date, str]]:
        raw = self.ical_path.read_text(encoding="utf-8")
        # Normalize ISO-looking DATE values to RFC5545 compact form for icalendar
        import re

        raw = re.sub(
            r"(DTSTART|DTEND)(;VALUE=DATE)?:(\d{4})-(\d{2})-(\d{2})",
            lambda m: f"{m.group(1)}{m.group(2) or ';VALUE=DATE'}:{m.group(3)}{m.group(4)}{m.group(5)}",
            raw,
        )
        cal = Calendar.from_ical(raw.encode("utf-8"))
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            dtstart = component.get("dtstart")
            dtend = component.get("dtend")
            if dtstart is None or dtend is None:
                continue
            try:
                start = self._as_date(dtstart.dt)
                end = self._as_date(dtend.dt)
            except Exception:
                # Fallback: read raw encoded values
                start = self._as_date(getattr(dtstart, "to_ical", lambda: b"")().decode())
                end = self._as_date(getattr(dtend, "to_ical", lambda: b"")().decode())
            summary = str(component.get("summary") or "")
            # iCal DTEND is exclusive for all-day events
            yield start, end, summary

    def load_inventory(self, conn: sqlite3.Connection) -> int:
        n = 0
        for start, end, summary in self._events():
            status = "booked" if any(k in summary.lower() for k in ("reserved", "booked", "reservation")) else "blocked"
            cur = start
            while cur < end:
                upsert_inventory(
                    conn,
                    {
                        "property_id": self.property_id,
                        "stay_date": cur.isoformat(),
                        "listed_price": self.default_listed_price,
                        "booked_price": self.default_listed_price if status == "booked" else None,
                        "status": status,
                        "lead_time_days": None,
                        "channel": "ical",
                        "reservation_id": summary[:80] or None,
                    },
                )
                n += 1
                from datetime import timedelta

                cur = cur + timedelta(days=1)
        conn.commit()
        return n


__all__ = [
    "IngestAdapter",
    "CsvIngestAdapter",
    "ICalIngestAdapter",
    "upsert_property",
    "upsert_inventory",
]
