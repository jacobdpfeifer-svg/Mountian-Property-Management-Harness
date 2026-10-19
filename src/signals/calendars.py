"""Rule-generated holiday windows and sourced school-break rows.

Federal windows follow R7 §2.5: Christmas–New Year is 20 Dec–2 Jan, MLK and
Presidents Day are the Friday through Monday around the third Monday, and
Thanksgiving is Wednesday through Sunday. Dates are not typed by hand.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.config import ROOT

SCHOOL_BREAKS_PATH = ROOT / "config" / "calendars" / "school_breaks.csv"

# Signal strengths are labelled priors, same order of magnitude as the previous
# hand-typed events.yaml rows. They are not fitted.
FEDERAL_RULES = (
    {"event_name": "Christmas / New Year holiday peak", "kind": "christmas_new_year",
     "signal_strength": 0.95, "source": "R7 §2.5"},
    {"event_name": "MLK weekend", "kind": "nth_monday_fri_mon", "month": 1, "n": 3,
     "signal_strength": 0.75, "source": "R7 §2.5"},
    {"event_name": "Presidents Day weekend", "kind": "nth_monday_fri_mon", "month": 2, "n": 3,
     "signal_strength": 0.80, "source": "R7 §2.5"},
    {"event_name": "Thanksgiving", "kind": "thanksgiving_wed_sun",
     "signal_strength": 0.70, "source": "R7 §2.5"},
)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """weekday: Monday is 0. n is 1-based."""
    first = date(year, month, 1)
    shift = (weekday - first.weekday()) % 7
    day = first + timedelta(days=shift + 7 * (n - 1))
    if day.month != month:
        raise ValueError(f"no {n}th weekday {weekday} in {year}-{month}")
    return day


def federal_windows(season_january_years: list[int]) -> list[dict[str, Any]]:
    """One winter season is named by its January year (2027 means 2026-27)."""
    rows: list[dict[str, Any]] = []
    for year in season_january_years:
        for rule in FEDERAL_RULES:
            kind = rule["kind"]
            if kind == "christmas_new_year":
                start = date(year - 1, 12, 20)
                end = date(year, 1, 2)
            elif kind == "nth_monday_fri_mon":
                monday = nth_weekday(year, int(rule["month"]), 0, int(rule["n"]))
                start = monday - timedelta(days=3)
                end = monday
            elif kind == "thanksgiving_wed_sun":
                thursday = nth_weekday(year - 1, 11, 3, 4)
                start = thursday - timedelta(days=1)
                end = thursday + timedelta(days=3)
            else:
                raise ValueError(f"unknown holiday rule {kind}")
            rows.append({
                "event_name": rule["event_name"],
                "start": start.isoformat(),
                "end": end.isoformat(),
                "signal_strength": rule["signal_strength"],
                "source": rule["source"],
                "generated": True,
            })
    return rows


def season_january_years(today: date, ahead: int = 2) -> list[int]:
    """The winter season in progress, plus `ahead` further Januarys.

    On 19 Oct 2026 the in-progress season's January is 2027, and two seasons
    ahead also include 2028 and 2029. `ahead=2` therefore returns three January
    years: current plus the next two. A caller that asks only for the next two
    seasons uses the last two.
    """
    current = today.year if today.month <= 6 else today.year + 1
    return list(range(current, current + ahead + 1))


def load_school_breaks(path: Path | None = None) -> list[dict[str, str]]:
    src = path or SCHOOL_BREAKS_PATH
    if not src.exists():
        return []
    with src.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verified_school_breaks(rows: list[dict[str, str]], *, season: str, as_of: date,
                           max_age_days: int = 400) -> list[dict[str, str]]:
    """Rows the price path may treat as present. Unverified or stale rows are out.

    An empty result is unavailable coverage, not a zero demand score.
    """
    kept = []
    for row in rows:
        if (row.get("season") or "") != season:
            continue
        if (row.get("status") or "").upper() != "VERIFIED":
            continue
        if not (row.get("source_url") or "").startswith("http"):
            continue
        try:
            verified = date.fromisoformat(row["verified_on"])
        except (KeyError, ValueError):
            continue
        if (as_of - verified).days > max_age_days or verified > as_of:
            continue
        kept.append(row)
    return kept
