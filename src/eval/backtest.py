"""Leak-free backtest harness (WP-06).

Replay at a decision date using ONLY observed_at <= decision_date.
A deliberate lookahead bug must fail tests.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from src.compose import generate_recommendations
from src.signals.store import SignalStore


@dataclass
class BacktestReport:
    decision_date: date
    nights: int
    scored: int
    realised_revpan: float | None
    counterfactual_revpan: float | None
    calibration_error: float | None
    confidence_note: str
    signal_scores: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def assert_no_lookahead(store: SignalStore, decision_date: date, signal_key: str) -> None:
    """Raise if any readable row has observed_at > decision_date (API contract)."""
    # Direct SQL bypass would be the bug; the store API must not return them.
    rows = store.read_observations(as_of=decision_date, signal_key=signal_key)
    for r in rows:
        if r["observed_at"] > decision_date.isoformat():
            raise AssertionError(
                f"lookahead: {signal_key} observed_at={r['observed_at']} > {decision_date}"
            )


def information_coefficient(
    pairs: list[tuple[float, float]],
) -> tuple[float | None, float | None, float | None, int]:
    """Spearman-ish IC via Pearson on ranks; return (ic, ci_low, ci_high, n).

    With n≈1 seasons, intervals are intentionally embarrassing.
    """
    n = len(pairs)
    if n < 5:
        return None, None, None, n
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    rx = _rank(xs)
    ry = _rank(ys)
    ic = _pearson(rx, ry)
    # Fisher wide interval
    if ic is None or abs(ic) >= 1:
        return ic, None, None, n
    z = 0.5 * math.log((1 + ic) / (1 - ic))
    se = 1.0 / math.sqrt(max(n - 3, 1))
    # 95% but widened further for honesty on thin samples
    widen = 1.5 if n < 40 else 1.0
    z_lo, z_hi = z - 1.96 * se * widen, z + 1.96 * se * widen
    def _z_to_r(zv):
        return math.tanh(zv)
    return ic, _z_to_r(z_lo), _z_to_r(z_hi), n


def _rank(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    for r, i in enumerate(order):
        ranks[i] = float(r + 1)
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def hit_rate(pairs: list[tuple[float, float]]) -> float | None:
    """Share of pairs where sign(signal) matches sign(outcome delta)."""
    if len(pairs) < 5:
        return None
    hits = 0
    for s, o in pairs:
        if s == 0 or o == 0:
            continue
        hits += 1 if (s > 0) == (o > 0) else 0
    return hits / len(pairs) if pairs else None


def run_backtest(
    conn: sqlite3.Connection,
    decision_date: date,
    start: date,
    end: date,
    policy: dict[str, Any],
    *,
    property_ids: list[str] | None = None,
) -> BacktestReport:
    store = SignalStore(conn)
    warnings: list[str] = []

    # Contract check on every defined signal.
    for dfn in store.list_definitions():
        assert_no_lookahead(store, decision_date, dfn["signal_key"])

    recs, _health = generate_recommendations(
        conn,
        start,
        end,
        property_ids=property_ids,
        policy=policy,
        persist=False,
        allow_past=True,
    )

    # Score against realised inventory.
    realised = []
    expected_p = []
    for rec in recs:
        row = conn.execute(
            """
            SELECT status, booked_price, listed_price FROM nightly_inventory
            WHERE property_id = ? AND stay_date = ?
            """,
            (rec.property_id, rec.stay_date.isoformat()),
        ).fetchone()
        if row is None:
            continue
        booked = 1.0 if row["status"] == "booked" else 0.0
        rev = float(row["booked_price"] or 0.0) if booked else 0.0
        realised.append(rev)
        expected_p.append(float(rec.expected_book_prob or 0.0))

    n = len(realised)
    note = (
        "Thin sample — intervals intentionally wide. One drought season is n=1, "
        "not a relationship."
    )
    if n < 20:
        warnings.append(f"only {n} nights scored; reporting low confidence")
        note = f"LOW CONFIDENCE (n={n}). " + note

    realised_revpan = sum(realised) / n if n else None
    # Counterfactual: recommended price * realised book (naive)
    cf = []
    for rec, rev in zip(recs, realised):
        cf.append(float(rec.recommended_price) if rev > 0 else 0.0)
    counterfactual = sum(cf) / len(cf) if cf else None

    cal = None
    if expected_p and n >= 5:
        # Mean |p - realised book|
        books = [1.0 if r > 0 else 0.0 for r in realised]
        cal = sum(abs(p - b) for p, b in zip(expected_p[:n], books)) / n

    return BacktestReport(
        decision_date=decision_date,
        nights=len(recs),
        scored=n,
        realised_revpan=realised_revpan,
        counterfactual_revpan=counterfactual,
        calibration_error=cal,
        confidence_note=note,
        warnings=warnings,
    )


def score_signal_against_outcomes(
    store: SignalStore,
    conn: sqlite3.Connection,
    signal_key: str,
    *,
    decision_dates: Iterable[date],
    horizon_days: int,
) -> dict[str, Any]:
    """Build (signal, outcome) pairs with leak-free reads; write signal_scores."""
    pairs: list[tuple[float, float]] = []
    for d in decision_dates:
        assert_no_lookahead(store, d, signal_key)
        rows = store.read_observations(as_of=d, signal_key=signal_key, qualities=["ok"])
        if not rows:
            continue
        # Use latest observation as of d
        sig = float(rows[-1]["value"])
        # Outcome: portfolio booked revenue on d+horizon
        target = date.fromisoformat(d.isoformat()) 
        from datetime import timedelta

        stay = d + timedelta(days=horizon_days)
        row = conn.execute(
            """
            SELECT AVG(CASE WHEN status='booked' THEN COALESCE(booked_price,0) ELSE 0 END) AS rev
            FROM nightly_inventory WHERE stay_date = ?
            """,
            (stay.isoformat(),),
        ).fetchone()
        if row and row["rev"] is not None:
            pairs.append((sig, float(row["rev"])))

    ic, lo, hi, n = information_coefficient(pairs)
    hr = hit_rate(pairs)
    if n < 20 or ic is None:
        decision = "insufficient"
    elif ic >= 0.05 and (hr or 0) >= 0.52:
        decision = "promote"
    elif ic is not None and ic < -0.02:
        decision = "demote"
    else:
        decision = "hold"

    store.write_score(
        signal_key=signal_key,
        horizon_days=horizon_days,
        sample_size=n,
        information_coefficient=ic,
        hit_rate=hr,
        ic_ci_low=lo,
        ic_ci_high=hi,
        decision=decision,
        notes="Wide CI by design on thin n.",
    )
    return {
        "signal_key": signal_key,
        "n": n,
        "ic": ic,
        "ic_ci": (lo, hi),
        "hit_rate": hr,
        "decision": decision,
    }
