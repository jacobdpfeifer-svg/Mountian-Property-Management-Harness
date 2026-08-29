"""Comp scrape orchestrator.

Sweeps the market on a sampled schedule, filters to the curated comp set, validates
hard, and records exactly what happened. The contract with the rest of the engine is
that this module NEVER writes a number it is not confident in — a degraded run leaves
`scrape_status='failed'` rows and a `comp_scrape_runs` record, the comp coverage gate
in src/guardrails then sees the gap, and autonomy demotes itself to advisory.

Sampling: pricing every night individually would need one request per comp per night.
Instead one market-wide sweep per window covers every comp at once, and windows are
sampled (one weekend + one midweek per week) because the ceiling consumes comp
evidence at the season x day-of-week level, not per-night.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np

from src.scrape.parse import validate_observation, validate_sweep
from src.scrape.providers import CompProvider, SweepResult


@dataclass
class ScrapeReport:
    run_id: str
    provider: str
    windows_attempted: int = 0
    windows_ok: int = 0
    listings_seen: int = 0
    comps_matched: int = 0
    comps_expected: int = 0
    observations: int = 0
    rejected: int = 0
    status: str = "running"
    errors: list[str] = field(default_factory=list)

    @property
    def comp_match_rate(self) -> float:
        return self.comps_matched / self.comps_expected if self.comps_expected else 0.0


def plan_windows(start: date, horizon_days: int, nights: int = 2) -> list[date]:
    """One weekend (Fri) and one midweek (Tue) check-in per week across the horizon."""
    windows: list[date] = []
    cur = start
    end = start + timedelta(days=horizon_days)
    while cur < end:
        week = cur - timedelta(days=cur.weekday())
        for target in (1, 4):  # Tue, Fri
            d = week + timedelta(days=target)
            if start <= d < end and d not in windows:
                windows.append(d)
        cur += timedelta(days=7)
    return sorted(windows)


def _comp_index(conn: sqlite3.Connection) -> dict[str, str]:
    """airbnb_room_id -> comp_id for active comps."""
    return {
        str(r["airbnb_room_id"]): r["comp_id"]
        for r in conn.execute(
            "SELECT comp_id, airbnb_room_id FROM comps "
            "WHERE active = 1 AND airbnb_room_id IS NOT NULL AND airbnb_room_id != ''"
        ).fetchall()
    }


def _previous_price(conn: sqlite3.Connection, comp_id: str, stay_date: date) -> float | None:
    row = conn.execute(
        "SELECT listed_price FROM comp_snapshots WHERE comp_id = ? AND stay_date = ? "
        "AND scrape_status = 'ok' AND listed_price IS NOT NULL ORDER BY as_of DESC LIMIT 1",
        (comp_id, stay_date.isoformat()),
    ).fetchone()
    return float(row["listed_price"]) if row else None


def _record_market(conn: sqlite3.Connection, as_of: date, sweep: SweepResult,
                   prices: list[float], run_id: str, *, region: str = "winter_park") -> None:
    if len(prices) < 5:
        return
    arr = np.array(prices, dtype=float)
    for stay in sweep.stay_dates:
        conn.execute(
            """
            INSERT INTO market_snapshots (as_of, stay_date, window_nights, region,
                listings, p25, p50, p75, p90, run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(as_of, stay_date, region) DO UPDATE SET
                listings=excluded.listings, p25=excluded.p25, p50=excluded.p50,
                p75=excluded.p75, p90=excluded.p90, run_id=excluded.run_id
            """,
            (as_of.isoformat(), stay.isoformat(), sweep.nights, region, len(prices),
             *[float(np.percentile(arr, q)) for q in (25, 50, 75, 90)], run_id),
        )


def run_scrape(
    conn: sqlite3.Connection,
    provider: CompProvider,
    policy: dict[str, Any],
    horizon_days: int = 120,
    as_of: date | None = None,
    start: date | None = None,
    fetch_calendars: bool = True,
    region: str = "winter_park",
) -> ScrapeReport:
    as_of = as_of or date.today()
    start = start or as_of
    run_id = uuid.uuid4().hex[:12]
    nights = int(policy.get("scrape", {}).get("window_nights", 2))

    comps = _comp_index(conn)
    report = ScrapeReport(run_id=run_id, provider=provider.name, comps_expected=len(comps))
    conn.execute(
        "INSERT INTO comp_scrape_runs (run_id, provider, horizon_days, comps_expected) "
        "VALUES (?, ?, ?, ?)",
        (run_id, provider.name, horizon_days, len(comps)),
    )
    conn.commit()

    if not comps:
        report.status = "failed"
        report.errors.append("no active comps with an airbnb_room_id — run `wp-price discover-comps`")
        _finish(conn, report)
        return report

    matched_ids: set[str] = set()

    for check_in in plan_windows(start, horizon_days, nights):
        report.windows_attempted += 1
        sweep = provider.sweep(check_in, nights)
        if not sweep.ok:
            report.errors.append(f"{check_in}: {sweep.error}")
            _mark_failed(conn, comps.values(), as_of, sweep.stay_dates, run_id)
            continue

        prices = [l.nightly_price for l in sweep.listings if l.nightly_price]
        validation = validate_sweep([float(p) for p in prices], len(sweep.listings), policy)
        report.listings_seen += len(sweep.listings)
        if not validation.ok:
            report.errors.append(f"{check_in}: " + "; ".join(validation.reasons))
            report.rejected += validation.rejected
            # A sweep that fails validation is a suspected parser/block failure. Its
            # numbers are discarded entirely rather than partially trusted.
            _mark_failed(conn, comps.values(), as_of, sweep.stay_dates, run_id)
            continue

        report.windows_ok += 1
        _record_market(conn, as_of, sweep, [float(p) for p in prices], run_id, region=region)

        seen_this_window: set[str] = set()
        for listing in sweep.listings:
            comp_id = comps.get(listing.room_id)
            if comp_id is None:
                continue
            seen_this_window.add(comp_id)
            matched_ids.add(comp_id)
            for stay in sweep.stay_dates:
                if listing.nightly_price is None:
                    _write(conn, comp_id, as_of, stay, None, 0, None, "failed",
                           nights, provider.name, run_id)
                    continue
                ok, why = validate_observation(
                    float(listing.nightly_price), _previous_price(conn, comp_id, stay), policy
                )
                if not ok:
                    report.rejected += 1
                    report.errors.append(f"{comp_id} {stay}: {why}")
                    _write(conn, comp_id, as_of, stay, None, None, None, "failed",
                           nights, provider.name, run_id)
                    continue
                _write(conn, comp_id, as_of, stay, float(listing.nightly_price), 1, None,
                       "ok", nights, provider.name, run_id)
                report.observations += 1

        # Absent from a valid sweep means unavailable, not unknown. Recording that
        # explicitly is what stops a fully-booked comp set looking like a scrape failure.
        for comp_id in set(comps.values()) - seen_this_window:
            for stay in sweep.stay_dates:
                _write(conn, comp_id, as_of, stay, None, 0, None, "unavailable",
                       nights, provider.name, run_id)
        conn.commit()

    if fetch_calendars:
        _enrich_min_nights(conn, provider, comps, as_of)

    report.comps_matched = len(matched_ids)
    report.status = _verdict(report, policy)
    _finish(conn, report)
    return report


def _verdict(report: ScrapeReport, policy: dict[str, Any]) -> str:
    cfg = policy.get("scrape", {}).get("validation", {})
    min_window_rate = float(cfg.get("min_window_success_rate", 0.70))
    min_match = float(cfg.get("min_comp_match_rate", 0.60))
    if report.windows_ok == 0:
        return "failed"
    rate = report.windows_ok / report.windows_attempted if report.windows_attempted else 0.0
    if rate < min_window_rate or report.comp_match_rate < min_match:
        return "degraded"
    return "ok"


def _write(conn: sqlite3.Connection, comp_id: str, as_of: date, stay: date,
           price: float | None, available: int | None, min_nights: int | None,
           status: str, window_nights: int, source: str, run_id: str) -> None:
    conn.execute(
        """
        INSERT INTO comp_snapshots (comp_id, as_of, stay_date, listed_price, available,
            min_nights, scrape_status, window_nights, source, capture_method, run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'scrape', ?)
        ON CONFLICT(comp_id, as_of, stay_date) DO UPDATE SET
            listed_price=excluded.listed_price, available=excluded.available,
            min_nights=COALESCE(excluded.min_nights, comp_snapshots.min_nights),
            scrape_status=excluded.scrape_status, window_nights=excluded.window_nights,
            source=excluded.source, capture_method='scrape', run_id=excluded.run_id
        """,
        (comp_id, as_of.isoformat(), stay.isoformat(), price, available, min_nights,
         status, window_nights, source, run_id),
    )


def _mark_failed(conn: sqlite3.Connection, comp_ids, as_of: date,
                 stay_dates: list[date], run_id: str) -> None:
    for comp_id in set(comp_ids):
        for stay in stay_dates:
            conn.execute(
                """
                INSERT INTO comp_snapshots (comp_id, as_of, stay_date, scrape_status,
                    capture_method, run_id)
                VALUES (?, ?, ?, 'failed', 'scrape', ?)
                ON CONFLICT(comp_id, as_of, stay_date) DO NOTHING
                """,
                (comp_id, as_of.isoformat(), stay.isoformat(), run_id),
            )
    conn.commit()


def _enrich_min_nights(conn: sqlite3.Connection, provider: CompProvider,
                       comps: dict[str, str], as_of: date) -> None:
    """One calendar call per comp adds min-stay + availability for a full year."""
    for room_id, comp_id in comps.items():
        cal = provider.calendar(room_id)
        for iso, info in cal.items():
            conn.execute(
                "UPDATE comp_snapshots SET min_nights = ? "
                "WHERE comp_id = ? AND stay_date = ? AND as_of = ?",
                (info.get("min_nights"), comp_id, iso, as_of.isoformat()),
            )
    conn.commit()


def _finish(conn: sqlite3.Connection, report: ScrapeReport) -> None:
    conn.execute(
        """
        UPDATE comp_scrape_runs SET finished_at = datetime('now'),
            windows_attempted = ?, windows_ok = ?, listings_seen = ?, comps_matched = ?,
            observations = ?, rejected = ?, status = ?, errors = ?
        WHERE run_id = ?
        """,
        (report.windows_attempted, report.windows_ok, report.listings_seen,
         report.comps_matched, report.observations, report.rejected, report.status,
         json.dumps(report.errors[:50]), report.run_id),
    )
    conn.commit()


def discover_comps(
    provider: CompProvider,
    check_in: date,
    nights: int,
    min_price: float,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Rank the live market to help the operator curate a luxury comp set."""
    sweep = provider.sweep(check_in, nights)
    if not sweep.ok:
        return []
    rows = [
        {"room_id": l.room_id, "name": l.name, "nightly_price": l.nightly_price,
         "rating": l.rating}
        for l in sweep.listings
        if l.nightly_price and l.nightly_price >= min_price
    ]
    rows.sort(key=lambda r: r["nightly_price"], reverse=True)
    return rows[:limit]


def min_stay_wall_distribution(
    conn: sqlite3.Connection, stay_date: date, as_of: date | None = None
) -> dict[str, Any]:
    """Comp min-stay distribution for a night — scarce short-stay inventory signal."""
    as_of = as_of or date.today()
    rows = conn.execute(
        """
        SELECT min_nights FROM comp_snapshots
        WHERE stay_date = ? AND as_of <= ? AND scrape_status = 'ok'
          AND min_nights IS NOT NULL
        """,
        (stay_date.isoformat(), as_of.isoformat()),
    ).fetchall()
    vals = [int(r["min_nights"]) for r in rows]
    if not vals:
        return {"n": 0, "share_ge_5": None, "median": None}
    ge5 = sum(1 for v in vals if v >= 5) / len(vals)
    return {
        "n": len(vals),
        "share_ge_5": ge5,
        "median": float(np.median(vals)),
        "short_stay_scarce": ge5 >= 0.5,
    }


def multi_market_regions_from_store(conn: sqlite3.Connection) -> list[tuple[str, str, dict]]:
    """(market_id, region_legacy, bbox) for all active markets — shared sweep budget."""
    from src.signals.store import SignalStore

    store = SignalStore(conn)
    out = []
    for m in store.list_markets():
        bbox = {
            "ne_lat": m["bbox_ne_lat"],
            "ne_lng": m["bbox_ne_lng"],
            "sw_lat": m["bbox_sw_lat"],
            "sw_lng": m["bbox_sw_lng"],
        }
        out.append((m["market_id"], m["region_legacy"] or m["market_id"], bbox))
    return out
