"""Nightly feature builder."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from src.config import load_events, load_policy
from src.utils import lead_time_multiplier, parse_date, season_for


@dataclass
class NightFeatures:
    property_id: str
    stay_date: date
    status: str
    listed_price: float | None
    booked_price: float | None
    lead_time_days: int | None
    day_of_week: int
    season: str
    season_multiplier: float
    lead_multiplier: float
    dow_multiplier: float
    demand_strength: float
    demand_event: str | None
    is_orphan_gap: bool
    gap_size: int
    min_floor_rate: float
    max_ceiling_rate: float
    base_ceiling_rate: float
    min_stay: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["stay_date"] = self.stay_date.isoformat()
        return d


def _demand_index(events: list[dict[str, Any]]) -> dict[date, tuple[float, str]]:
    index: dict[date, tuple[float, str]] = {}
    for ev in events:
        start = parse_date(ev["start"])
        end = parse_date(ev["end"])
        strength = float(ev["signal_strength"])
        name = str(ev["event_name"])
        cur = start
        while cur <= end:
            prev = index.get(cur)
            if prev is None or strength > prev[0]:
                index[cur] = (strength, name)
            cur += timedelta(days=1)
    return index


def _db_demand(
    conn: sqlite3.Connection,
    region: str = "winter_park",
) -> dict[date, tuple[float, str]]:
    """Load demand_signals for one region (plus legacy blank-region rows).

    Region collapse was a bug: valley/substitute market signals could overwrite
    Winter Park strengths for the same calendar date. Exact-region rows win.
    """
    best: dict[date, tuple[float, str, bool]] = {}
    rows = conn.execute(
        """
        SELECT signal_date, event_name, signal_strength, region FROM demand_signals
        WHERE region = ? OR region = '' OR region IS NULL
        """,
        (region,),
    ).fetchall()
    for row in rows:
        d = parse_date(row["signal_date"])
        strength = float(row["signal_strength"])
        exact = (row["region"] or "").strip() == region
        prev = best.get(d)
        if prev is None:
            best[d] = (strength, row["event_name"], exact)
            continue
        prev_strength, _prev_name, prev_exact = prev
        if exact and not prev_exact:
            best[d] = (strength, row["event_name"], True)
        elif exact == prev_exact and strength > prev_strength:
            best[d] = (strength, row["event_name"], exact)
    return {d: (s, n) for d, (s, n, _) in best.items()}


def _orphan_gaps(conn: sqlite3.Connection, property_id: str, max_gap: int) -> dict[date, int]:
    """Return available dates that sit in a 1..max_gap hole between booked nights."""
    rows = conn.execute(
        """
        SELECT stay_date, status FROM nightly_inventory
        WHERE property_id = ?
        ORDER BY stay_date
        """,
        (property_id,),
    ).fetchall()
    if not rows:
        return {}
    by_date = {parse_date(r["stay_date"]): r["status"] for r in rows}
    dates = sorted(by_date)
    gaps: dict[date, int] = {}
    i = 0
    while i < len(dates):
        if by_date[dates[i]] != "available":
            i += 1
            continue
        j = i
        while j < len(dates) and by_date[dates[j]] == "available":
            # contiguous calendar days
            if j > i and (dates[j] - dates[j - 1]).days != 1:
                break
            j += 1
        run = dates[i:j]
        gap_len = len(run)
        if 1 <= gap_len <= max_gap:
            left = dates[i - 1] if i > 0 else None
            right = dates[j] if j < len(dates) else None
            left_booked = left is not None and by_date[left] == "booked" and (dates[i] - left).days == 1
            right_booked = (
                right is not None and by_date[right] == "booked" and (right - dates[j - 1]).days == 1
            )
            if left_booked and right_booked:
                for d in run:
                    gaps[d] = gap_len
        i = j
    return gaps


def build_features_for_property(
    conn: sqlite3.Connection,
    property_id: str,
    start: date,
    end: date,
    policy: dict[str, Any] | None = None,
) -> list[NightFeatures]:
    policy = policy or load_policy()
    prop = conn.execute(
        "SELECT * FROM properties WHERE property_id = ?", (property_id,)
    ).fetchone()
    if prop is None:
        raise KeyError(f"Unknown property_id: {property_id}")

    event_demand = _demand_index(load_events())
    demand_region = str(
        (policy.get("scrape") or {}).get("region")
        or (policy.get("demand") or {}).get("region")
        or "winter_park"
    )
    event_demand.update(_db_demand(conn, region=demand_region))
    max_gap = int(policy.get("leakage", {}).get("orphan_gap", {}).get("max_gap_nights", 2))
    orphan = _orphan_gaps(conn, property_id, max_gap)

    rows = conn.execute(
        """
        SELECT * FROM nightly_inventory
        WHERE property_id = ? AND stay_date >= ? AND stay_date <= ?
        ORDER BY stay_date
        """,
        (property_id, start.isoformat(), end.isoformat()),
    ).fetchall()

    seasons = policy.get("seasons", {})
    dow_mults = {int(k): float(v) for k, v in policy.get("dow_multipliers", {}).items()}
    lead_curves = policy.get("lead_time_curves", [])
    as_of = date.today()

    features: list[NightFeatures] = []
    for row in rows:
        stay = parse_date(row["stay_date"])
        season, season_mult = season_for(stay, seasons)
        lead = row["lead_time_days"]
        if lead is None and row["status"] == "available":
            lead = (stay - as_of).days
            if lead < 0:
                lead = 0
        demand = event_demand.get(stay, (0.2, None))
        features.append(
            NightFeatures(
                property_id=property_id,
                stay_date=stay,
                status=row["status"],
                listed_price=float(row["listed_price"]) if row["listed_price"] is not None else None,
                booked_price=float(row["booked_price"]) if row["booked_price"] is not None else None,
                lead_time_days=int(lead) if lead is not None else None,
                day_of_week=int(row["day_of_week"] if row["day_of_week"] is not None else stay.weekday()),
                season=season,
                season_multiplier=season_mult,
                lead_multiplier=lead_time_multiplier(
                    int(lead) if lead is not None else None, lead_curves
                ),
                dow_multiplier=dow_mults.get(
                    int(row["day_of_week"] if row["day_of_week"] is not None else stay.weekday()),
                    1.0,
                ),
                demand_strength=float(demand[0]),
                demand_event=demand[1],
                is_orphan_gap=stay in orphan,
                gap_size=orphan.get(stay, 0),
                min_floor_rate=float(prop["min_floor_rate"]),
                max_ceiling_rate=float(prop["max_ceiling_rate"]),
                base_ceiling_rate=float(prop["base_ceiling_rate"]),
                min_stay=int(row["min_stay"]) if row["min_stay"] is not None else None,
            )
        )
    return features


def build_features(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    property_ids: list[str] | None = None,
    policy: dict[str, Any] | None = None,
) -> list[NightFeatures]:
    if property_ids is None:
        property_ids = [
            r["property_id"]
            for r in conn.execute("SELECT property_id FROM properties ORDER BY property_id").fetchall()
        ]
    out: list[NightFeatures] = []
    for pid in property_ids:
        out.extend(build_features_for_property(conn, pid, start, end, policy=policy))
    return out
