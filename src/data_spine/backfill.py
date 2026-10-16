"""Read-only historical backfill into the data spine.

`backfill_guesty` reads reservations and calendar through `ReadOnlyGuesty` and
appends them through the contracts. `import_csv` loads an operator export
(accounting ledger, owner statements, ops tasks) through a mapping file. Both
are idempotent: re-running with the same source data adds only duplicates,
which ingest counts and skips.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.data_spine.adapters import (
    ReadOnlyGuesty, csv_records, guesty_calendar, guesty_reservation, load_mapping, now_utc,
)
from src.data_spine.ingest import IngestResult, ingest


@dataclass
class BackfillReport:
    results: list[IngestResult] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)

    def summary(self) -> list[str]:
        lines = [f"{r.contract}: {len(r.accepted)} accepted, {r.duplicates} duplicate, "
                 f"{len(r.quarantined)} quarantined" for r in self.results]
        lines += [f"skipped ({why}): {n}" for why, n in sorted(self.skipped.items())]
        return lines

    @property
    def quarantined(self) -> int:
        return sum(len(r.quarantined) for r in self.results)


def backfill_guesty(conn: sqlite3.Connection, client: Any, *, property_by_listing: dict[str, str],
                    scope: frozenset[str], check_in_from: date, calendar_days: int = 365,
                    today: date | None = None) -> BackfillReport:
    ro = client if isinstance(client, ReadOnlyGuesty) else ReadOnlyGuesty(client)
    observed = now_utc()
    report = BackfillReport()
    reservations, ledger = [], []
    for raw in ro.reservations(check_in_from=check_in_from.isoformat()):
        rec, lines, why = guesty_reservation(raw, property_by_listing, observed_at=observed)
        if rec is None:
            report.skipped[why or "unknown"] = report.skipped.get(why or "unknown", 0) + 1
            continue
        reservations.append(rec)
        ledger.extend(lines)
    report.results.append(ingest(conn, "reservation", reservations, allowed_property_ids=scope))
    # Ledger lines for a reservation the spine does not hold would be orphans.
    held = {r[0] for r in conn.execute("SELECT DISTINCT entity_key FROM fact_reservation_version")}
    orphans = [ln for ln in ledger if ln["reservation_key"] not in held]
    if orphans:
        report.skipped["ledger line of a quarantined reservation"] = len(orphans)
    report.results.append(ingest(conn, "financial_ledger",
                                 [ln for ln in ledger if ln["reservation_key"] in held],
                                 allowed_property_ids=scope))
    today = today or date.today()
    calendar: list[dict[str, Any]] = []
    for listing_id, pid in sorted(property_by_listing.items()):
        if pid not in scope:
            continue
        calendar.extend(guesty_calendar(ro.calendar(listing_id, today, today + timedelta(days=calendar_days)),
                                        pid, observed_at=observed))
    report.results.append(ingest(conn, "calendar_observation", calendar, allowed_property_ids=scope))
    return report


def import_csv(conn: sqlite3.Connection, csv_path: Path, mapping_path: Path, *,
               scope: frozenset[str]) -> BackfillReport:
    mapping = load_mapping(mapping_path)
    report = BackfillReport()
    records = list(csv_records(csv_path, mapping, observed_at=now_utc()))
    report.results.append(ingest(conn, mapping["contract"], records, allowed_property_ids=scope))
    return report
