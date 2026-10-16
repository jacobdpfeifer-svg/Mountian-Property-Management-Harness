"""Pace pricing: a market-anchored reference, moved by booking pace, priced for owner net.

Why (2026-10-14 audit): at peak the engine charged its ceiling on 100% of nights.
Its reference price was the mean of the home's own past prices, so the demand
model priced against itself, and with peak elasticity -0.65 the revenue optimum
always sat above any ceiling. The ceiling, not the demand model, set the price.

This model changes three things, each off unless ``models.pace_pricing.enabled``:

1. Reference price: the median competitor quote for the night (as of the
   decision day), times an optional per-home premium. A market price does not
   walk down with the engine's own sales. Without quotes the old reference stays.
2. Booking pace: the share of nearby nights (portfolio, +/- ``window_days``)
   already on the books versus the share normally booked at this lead time.
   History supplies the norm once it has ``min_history`` observations; until
   then a documented reference curve does. Ahead of pace raises the reference,
   behind lowers it, bounded (PriceLabs' occupancy rule: low occupancy 15 days
   out -> about -15%).
3. Owner net, all-in: guests react to the total price, so a 1% change in the
   nightly rate is a smaller change in what they compare. Elasticity is scaled
   by nightly / (nightly + fees per night). The search maximizes
   P(book) x (owner's share of the nightly rate + fee margin per night), not
   nightly RevPAN.

Learned elasticity (``models.learned_elasticity``) runs before this and supplies
beta; pace pricing uses whatever beta it produced.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

# Share of a night's final bookings already on the books at a given lead time,
# when there is no history yet. Assumed from the v2 simulator's validated lead
# mix (~37% of bookings within 21 days) and Colorado ski booking windows of
# 24-33 days (Beyond Pricing). Replaced by history as soon as it exists.
DEFAULT_CURVE = {120: 0.12, 90: 0.20, 60: 0.35, 30: 0.55, 21: 0.63, 14: 0.72, 7: 0.85, 0: 1.0}
DEFAULT_FINAL_OCCUPANCY = {"peak_ski": 0.70, "early_winter": 0.45, "shoulder_spring": 0.40,
                           "shoulder_fall": 0.40, "summer": 0.50}


@dataclass(frozen=True)
class PaceReading:
    on_books: float
    expected: float
    source: str  # history | curve
    observations: int

    @property
    def index(self) -> float:
        # Small additive smoothing so a 0/0.05 reading is not "infinitely behind".
        return (self.on_books + 0.05) / (self.expected + 0.05)


def curve_share(lead: int, curve: dict[int, float] | None = None) -> float:
    """Linear interpolation of the reference booking curve at ``lead`` days."""
    points = sorted((int(k), float(v)) for k, v in (curve or DEFAULT_CURVE).items())
    if lead <= points[0][0]:
        return points[0][1]
    for (lo, a), (hi, b) in zip(points, points[1:]):
        if lo <= lead <= hi:
            return a + (b - a) * (lead - lo) / (hi - lo) if hi > lo else a
    return points[-1][1]


def _window(stay: date, days: int) -> tuple[str, str]:
    return (stay - timedelta(days=days)).isoformat(), (stay + timedelta(days=days)).isoformat()


def on_books_share(conn: sqlite3.Connection, stay: date, as_of: date, window_days: int) -> float:
    """Share of portfolio nights within the window that were booked by ``as_of``."""
    lo, hi = _window(stay, window_days)
    row = conn.execute(
        """
        SELECT COUNT(*) AS n,
               SUM(CASE WHEN status = 'booked' AND (booked_at IS NULL OR booked_at <= ?)
                        THEN 1 ELSE 0 END) AS booked
        FROM nightly_inventory
        WHERE stay_date BETWEEN ? AND ? AND status IN ('available', 'booked')
        """,
        (as_of.isoformat(), lo, hi),
    ).fetchone()
    n = int(row["n"] or 0)
    return float(row["booked"] or 0) / n if n else 0.0


def historical_share(
    conn: sqlite3.Connection, lead: int, as_of: date, season_stays: set[str], window: int = 3,
) -> tuple[float, int]:
    """Share booked at this lead among already-stayed nights of the same season.

    Uses pacing snapshots taken ``lead +/- window`` days before stays that are
    now in the past, so every label is known on the decision day.
    """
    if not season_stays:
        return 0.0, 0
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS n, SUM(CASE WHEN status = 'booked' THEN 1 ELSE 0 END) AS booked
        FROM pacing_snapshots
        WHERE days_out BETWEEN ? AND ? AND as_of <= ? AND stay_date < ?
          AND stay_date IN ({",".join("?" * len(season_stays))})
        """,
        (max(0, lead - window), lead + window, as_of.isoformat(), as_of.isoformat(), *sorted(season_stays)),
    ).fetchone()
    n = int(row["n"] or 0)
    return (float(row["booked"] or 0) / n if n else 0.0), n


def pace_reading(
    conn: sqlite3.Connection,
    *,
    stay: date,
    as_of: date,
    season: str,
    final_stays_same_season: set[str],
    cfg: dict[str, Any],
) -> PaceReading:
    lead = max(0, (stay - as_of).days)
    window_days = int(cfg.get("window_days", 3))
    on_books = on_books_share(conn, stay, as_of, window_days)
    hist, n = historical_share(conn, lead, as_of, final_stays_same_season)
    if n >= int(cfg.get("min_history", 60)):
        return PaceReading(on_books, hist, "history", n)
    finals = cfg.get("final_occupancy") or DEFAULT_FINAL_OCCUPANCY
    final = float(finals.get(season, 0.5))
    expected = final * curve_share(lead, cfg.get("reference_curve"))
    return PaceReading(on_books, expected, "curve", n)


def pace_multiplier(reading: PaceReading, cfg: dict[str, Any]) -> float:
    k = float(cfg.get("sensitivity", 0.30))
    lo = float(cfg.get("min_multiplier", 0.85))
    hi = float(cfg.get("max_multiplier", 1.25))
    return float(min(hi, max(lo, 1.0 + k * (reading.index - 1.0))))


# How old a comp's last good quote may be and still count, and how many comps an
# anchor needs. Chosen by scripts/anchor_rule_study.py (minimax regret over 24
# simulated worlds fitted to the real Sep-Oct 2026 scrapes; see
# docs/reports/anchor_rule_study/REPORT.md). A quote drifts ~1% in two days and
# ~9% in three weeks, but the comps in one set differ by 28-41%, so dropping a
# comp costs more than keeping its old quote; and a median of fewer than three
# comps is too exposed to one odd listing. Re-run the study as history grows:
# nothing older than 21 days has been observed yet.
ANCHOR_MAX_AGE_DAYS = 42
ANCHOR_MIN_COMPS = 3


def comp_anchor(conn: sqlite3.Connection, property_id: str, stay: date, as_of: date,
                *, max_age_days: int = ANCHOR_MAX_AGE_DAYS) -> tuple[float | None, int]:
    """Median of each own-set comp's latest good quote for the night, as of the decision day.

    Each active comp in this property's comp set contributes its most recent
    `ok`, positive quote for `stay` scraped on or before `as_of` and no more than
    `max_age_days` old. A failed or blocked scrape never hides an earlier good
    quote, and neither does another property's comp set or a partial scrape
    that reached only some comps (the 2026-10-16 audit: picking one global
    latest scrape date left the anchor empty whenever any later scrape failed).
    `as_of` is compared on its date part, so a quote stamped with a time on the
    decision day counts. The caller decides how many quotes are enough.
    """
    oldest = (as_of - timedelta(days=max_age_days)).isoformat()
    rows = conn.execute(
        """
        SELECT s.listed_price FROM comp_set_members m
        JOIN comps c ON c.comp_id = m.comp_id AND c.active = 1
        JOIN comp_snapshots s ON s.id = (
            SELECT s2.id FROM comp_snapshots s2
            WHERE s2.comp_id = m.comp_id AND s2.stay_date = ?
              AND s2.scrape_status = 'ok' AND s2.listed_price > 0
              AND substr(s2.as_of, 1, 10) <= ? AND substr(s2.as_of, 1, 10) >= ?
            ORDER BY s2.as_of DESC, s2.id DESC LIMIT 1
        )
        WHERE m.property_id = ?
        """,
        (stay.isoformat(), as_of.isoformat(), oldest, property_id),
    ).fetchall()
    prices = sorted(float(r["listed_price"]) for r in rows)
    if not prices:
        return None, 0
    mid = len(prices) // 2
    median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2
    return median, len(prices)


def own_sold_evidence(
    conn: sqlite3.Connection,
    property_id: str,
    as_of: date,
    stay_dates: set[str],
) -> tuple[float | None, int]:
    """Median price this home actually sold at, for comparable nights, known by as_of.

    Only sales count: a sold price is evidence of what guests pay. Averaging in
    unsold listed prices is what made the old reference spiral down.
    """
    if not stay_dates:
        return None, 0
    rows = conn.execute(
        f"""
        SELECT booked_price FROM nightly_inventory
        WHERE property_id = ? AND status = 'booked' AND booked_price > 0
          AND booked_at IS NOT NULL AND booked_at <= ?
          AND stay_date IN ({",".join("?" * len(stay_dates))})
        """,
        (property_id, as_of.isoformat(), *sorted(stay_dates)),
    ).fetchall()
    prices = sorted(float(r["booked_price"]) for r in rows)
    if not prices:
        return None, 0
    mid = len(prices) // 2
    return (prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2), len(prices)


def blend_reference(comp: float | None, own: float | None, own_n: int, k: float) -> float | None:
    """Comp anchor and own sold evidence, weighted n / (n + k) toward own sales."""
    if comp is None:
        return own
    if own is None or own_n <= 0:
        return comp
    weight = own_n / (own_n + k)
    return (1 - weight) * comp + weight * own


def fees_per_night(econ: dict[str, Any]) -> float:
    """Guest-paid fees spread over a typical stay."""
    fees = econ.get("guest_fees") or {}
    party = float(econ.get("typical_party", 10))
    los = max(1.0, float(econ.get("typical_los", 4)))
    total = (
        float(fees.get("cleaning_per_stay", 0))
        + float(fees.get("per_guest", 0)) * party
        + float(fees.get("insurance_per_stay", 0))
    )
    return total / los


def owner_terms(econ: dict[str, Any]) -> tuple[float, float]:
    """(owner share of the nightly rate, owner fee margin per booked night)."""
    channel = float(econ.get("channel_fee", 0.155))
    mgmt = float(econ.get("management_fee", 0.25))
    party = float(econ.get("typical_party", 10))
    los = max(1.0, float(econ.get("typical_los", 4)))
    fees = econ.get("guest_fees") or {}
    fee_total = (
        float(fees.get("cleaning_per_stay", 0))
        + float(fees.get("per_guest", 0)) * party
        + float(fees.get("insurance_per_stay", 0))
    )
    costs = (
        float(econ.get("turnover_cost_per_stay", 0))
        + float(econ.get("consumables_cost_per_guest", 0)) * party
        + float(econ.get("insurance_cost_per_stay", 0))
    )
    share = 1.0 - channel - mgmt
    margin = (fee_total * (1.0 - channel) - costs) / los
    return share, margin


def all_in_beta(beta: float, price: float, econ: dict[str, Any]) -> float:
    """Elasticity with respect to the nightly rate when guests judge the total.

    If demand responds to the all-in nightly price with elasticity beta, a change
    in the nightly rate moves the all-in price by price / (price + fees per night)
    as much, so the nightly elasticity shrinks by that factor.
    """
    fpn = fees_per_night(econ)
    if price <= 0:
        return beta
    return beta * price / (price + fpn)
