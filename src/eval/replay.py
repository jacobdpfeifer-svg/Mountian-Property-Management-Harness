"""Honest point-in-time replay of the pricing engine on the real operator DB.

Walks one virtual day at a time over the days we actually observed the calendar
(`pacing_snapshots.as_of`), prices each upcoming night AS OF that day, and logs the
recommendation next to the listed price known that morning and the booking outcome
known by the last sync (the *censor*). It measures two things honestly and keeps them
apart:

  * MEASURED facts (no demand assumption): calibration and direction, scored only on
    nights whose booking outcome is actually settled by the censor. Predicted booking
    probability is *terminal* ("books by check-in"); "booked by the censor" is only a
    partial outcome for nights still in the future, so scoring those would be wrong,
    not merely noisy. Unresolved nights are excluded and the panel says so.
  * An ESTIMATED revenue range with the assumption printed in the title. It never
    claims the engine beat the market: with no counterfactual (we never charged the
    recommended price for real) the only honest figure holds bookings fixed and swaps
    the price, which cannot prove causation.

Guesty stays read-only: the replay reads the operator DB and writes a local results
file. It refuses to run against a DB that already applied live rates.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from html import escape
from pathlib import Path
from typing import Any

from src.compose import generate_recommendations
from src.config import load_policy
from src.eval.backtest import assert_no_lookahead
from src.eval.shadow import GuestyWriteForbidden, guesty_write_count
from src.signals.store import SignalStore
from src.utils import parse_date, season_for

# A night's booking outcome is only "settled" once it has passed check-in by the
# censor date. Below these counts a panel reports `unmeasurable` with its N rather
# than drawing a curve that would mislead.
MIN_CALIBRATION_NIGHTS = 20
MIN_DIRECTION_GROUP = 5
LABEL_DEFINITION = (
    "For a decision on D for stay date S, label booked=true iff a confirmed booking "
    "event occurs after D and on or before min(S, censor); already-booked-at-D "
    "nights are excluded and reported separately."
)


class ReplayError(RuntimeError):
    """The replay cannot run (e.g. no observed calendar days in the window)."""


@dataclass
class ReplayRow:
    as_of: str
    property_id: str
    stay_date: str
    recommended_price: float
    expected_book_prob: float | None
    listed_as_of: float | None
    listed_source: str  # 'pacing' | 'none'
    booked_at: str | None
    booked_by_censor: bool
    resolved: bool
    lead_time_days: int
    season: str
    outcome_label: bool | None = None
    outcome_status: str = "scored"
    exclusion_reason: str | None = None


@dataclass
class DataCeiling:
    pacing_min_as_of: str | None
    pacing_max_as_of: str | None
    decision_days: int
    reservations: int
    nights_with_pacing_listed: int


@dataclass
class ReplayResult:
    generated_at: str
    window_from: str
    window_to: str
    censor_date: str
    property_ids: list[str]
    decision_days: list[str]
    ceiling: DataCeiling
    rows: list[ReplayRow]
    calibration: dict[str, Any]
    direction: dict[str, Any]
    estimated_revenue: dict[str, Any]
    price_ref_note: str
    warnings: list[str] = field(default_factory=list)
    label_definition: str = LABEL_DEFINITION
    panel_counts: dict[str, Any] = field(default_factory=dict)
    excluded_rows: list[dict[str, Any]] = field(default_factory=list)
    memory_set_hash: str = "memory_features_v1:empty"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


# --------------------------------------------------------------------------- data


def label_for_decision(
    decision_date: date,
    stay_date: date,
    booked_at: str | None,
    censor_date: date,
) -> bool | None:
    """Return the interval label, or None when the night is not terminally resolved."""
    if stay_date > censor_date:
        return None
    if booked_at is None:
        return False
    booked_date = parse_date(booked_at)
    if booked_date <= decision_date:
        return None
    return booked_date <= min(stay_date, censor_date)


def exclusion_record(
    as_of: date,
    property_id: str,
    stay_date: date,
    status: str,
    reason: str,
    booked_at: str | None = None,
) -> dict[str, Any]:
    return {
        "as_of": as_of.isoformat(),
        "property_id": property_id,
        "stay_date": stay_date.isoformat(),
        "status": status,
        "reason": reason,
        "booked_at": booked_at,
    }


def _booking_events(conn: sqlite3.Connection, property_ids: list[str]) -> dict[tuple[str, str], str]:
    """Earliest real sale per property/night — see `src.inventory.events`."""
    from src.inventory.events import booking_events

    return booking_events(conn, property_ids)


def _pacing_panel(
    conn: sqlite3.Connection,
    decision_date: date,
    property_ids: list[str],
    horizon_days: int,
) -> dict[tuple[str, str], sqlite3.Row]:
    marks = ",".join("?" for _ in property_ids)
    rows = conn.execute(
        f"""
        SELECT property_id, stay_date, status, listed_price, days_out
        FROM pacing_snapshots
        WHERE as_of = ? AND property_id IN ({marks})
          AND stay_date > ? AND stay_date <= date(?, '+' || ? || ' day')
        """,
        [decision_date.isoformat(), *property_ids, decision_date.isoformat(),
         decision_date.isoformat(), horizon_days],
    ).fetchall()
    return {(r["property_id"], r["stay_date"]): r for r in rows}


def _decision_days(conn: sqlite3.Connection, start: date, end: date) -> list[date]:
    rows = conn.execute(
        """
        SELECT DISTINCT as_of FROM pacing_snapshots
        WHERE as_of BETWEEN ? AND ?
        ORDER BY as_of
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [parse_date(r["as_of"]) for r in rows]


def _censor_date(conn: sqlite3.Connection, fallback: date) -> date:
    row = conn.execute("SELECT MAX(as_of) AS m FROM pacing_snapshots").fetchone()
    if row and row["m"]:
        return parse_date(row["m"])
    return fallback


def _listed_as_of(conn: sqlite3.Connection, as_of: date, property_id: str) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT stay_date, listed_price FROM pacing_snapshots
        WHERE as_of = ? AND property_id = ? AND listed_price IS NOT NULL
        """,
        (as_of.isoformat(), property_id),
    ).fetchall()
    return {r["stay_date"]: float(r["listed_price"]) for r in rows}


def _outcomes(conn: sqlite3.Connection, property_id: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT stay_date, status, booked_at FROM nightly_inventory
        WHERE property_id = ?
        """,
        (property_id,),
    ).fetchall()
    return {r["stay_date"]: r for r in rows}


def _data_ceiling(conn: sqlite3.Connection, decision_days: list[date]) -> DataCeiling:
    pac = conn.execute("SELECT MIN(as_of) AS lo, MAX(as_of) AS hi FROM pacing_snapshots").fetchone()
    res = conn.execute("SELECT COUNT(*) AS n FROM reservations").fetchone()
    listed = conn.execute(
        "SELECT COUNT(*) AS n FROM pacing_snapshots WHERE listed_price IS NOT NULL"
    ).fetchone()
    return DataCeiling(
        pacing_min_as_of=pac["lo"] if pac else None,
        pacing_max_as_of=pac["hi"] if pac else None,
        decision_days=len(decision_days),
        reservations=int(res["n"] if res else 0),
        nights_with_pacing_listed=int(listed["n"] if listed else 0),
    )


# ------------------------------------------------------------------------- replay


def run_replay(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    property_ids: list[str],
    *,
    policy: dict[str, Any] | None = None,
    horizon_days: int = 365,
    censor: date | None = None,
) -> ReplayResult:
    policy = policy or load_policy()

    writes = guesty_write_count(conn)
    if writes:
        raise GuestyWriteForbidden(
            f"replay refused: {writes} Guesty write(s) already in rate_changes; "
            "the replay reads only and must not run on a DB that touched live rates"
        )

    decision_days = _decision_days(conn, start, end)
    if not decision_days:
        raise ReplayError(
            f"no pacing_snapshots between {start} and {end}; nothing to replay "
            "(the observed-calendar days define the decision days)"
        )
    censor_date = censor or _censor_date(conn, fallback=max(decision_days))
    store = SignalStore(conn)
    definitions = store.list_definitions()
    booking_events = _booking_events(conn, property_ids)

    used_current_listed = 0
    rows: list[ReplayRow] = []
    panel_counts: dict[str, Any] = {"by_decision_day": {}, "by_property": {}}
    excluded_rows: list[dict[str, Any]] = []
    for d in decision_days:
        # Defense in depth: the engine already gates signals by as_of, but assert the
        # store never hands back a row observed after the virtual day.
        for dfn in definitions:
            assert_no_lookahead(store, d, dfn["signal_key"])

        recs, _health = generate_recommendations(
            conn,
            d + timedelta(days=1),
            d + timedelta(days=horizon_days),
            property_ids=property_ids,
            policy=policy,
            persist=False,
            allow_past=True,
            as_of=d,
        )
        rec_map = {(r.property_id, r.stay_date.isoformat()): r for r in recs}
        panel = _pacing_panel(conn, d, property_ids, horizon_days)
        day_counts: dict[str, dict[str, int]] = {}
        for pid in property_ids:
            counts = {
                "candidate": 0, "emitted": 0, "resolved": 0, "unresolved": 0,
                "booked": 0, "already_booked_at_decision": 0, "blocked": 0,
                "missing_recommendation": 0,
            }
            for (row_pid, sd), snap in panel.items():
                if row_pid != pid:
                    continue
                counts["candidate"] += 1
                if snap["status"] == "blocked":
                    counts["blocked"] += 1
                    excluded_rows.append(
                        exclusion_record(d, pid, parse_date(sd), "blocked", "blocked_at_decision")
                    )
                    continue
                if snap["status"] == "booked":
                    counts["booked"] += 1
                    counts["already_booked_at_decision"] += 1
                    excluded_rows.append(
                        exclusion_record(
                            d, pid, parse_date(sd), "booked", "already_booked_at_decision",
                            booking_events.get((pid, sd)),
                        )
                    )
                    continue
                rec = rec_map.get((pid, sd))
                if rec is None:
                    counts["missing_recommendation"] += 1
                    excluded_rows.append(
                        exclusion_record(d, pid, parse_date(sd), snap["status"], "no_recommendation")
                    )
                    continue
                counts["emitted"] += 1
                booked_at = booking_events.get((pid, sd))
                booked_by_censor = bool(
                    booked_at is not None and parse_date(booked_at) <= censor_date
                )
                label = label_for_decision(d, rec.stay_date, booked_at, censor_date)
                if label is None and booked_at is not None and parse_date(booked_at) <= d:
                    counts["already_booked_at_decision"] += 1
                    counts["emitted"] -= 1
                    excluded_rows.append(
                        exclusion_record(
                            d, pid, rec.stay_date, snap["status"],
                            "already_booked_at_decision", booked_at,
                        )
                    )
                    continue
                resolved = label is not None
                counts["resolved" if resolved else "unresolved"] += 1
                if label:
                    counts["booked"] += 1
                listed_price = snap["listed_price"]
                if listed_price is None:
                    used_current_listed += 1
                rows.append(ReplayRow(
                    as_of=d.isoformat(),
                    property_id=pid,
                    stay_date=sd,
                    recommended_price=float(rec.recommended_price),
                    expected_book_prob=(
                        float(rec.expected_book_prob)
                        if rec.expected_book_prob is not None else None
                    ),
                    listed_as_of=(float(listed_price) if listed_price is not None else None),
                    listed_source="pacing" if listed_price is not None else "none",
                    booked_at=booked_at,
                    booked_by_censor=booked_by_censor,
                    resolved=resolved,
                    lead_time_days=(rec.stay_date - d).days,
                    season=season_for(rec.stay_date, policy.get("seasons", {}))[0],
                    outcome_label=label,
                    outcome_status="resolved" if resolved else "unresolved",
                ))
            day_counts[pid] = counts
            pcounts = panel_counts["by_property"].setdefault(pid, {})
            for key, value in counts.items():
                pcounts[key] = pcounts.get(key, 0) + value
        panel_counts["by_decision_day"][d.isoformat()] = day_counts

    price_ref_note = (
        f"{used_current_listed} logged decision(s) had no listed price in the "
        "decision-day pacing snapshot; they are marked listed_source=none and "
        "excluded from reference-price comparisons."
        if used_current_listed else
        "Every logged decision used the listed price recorded on that day."
    )

    from src.memory.features import memory_catalog_hash

    return ReplayResult(
        generated_at=date.today().isoformat(),
        window_from=start.isoformat(),
        window_to=end.isoformat(),
        censor_date=censor_date.isoformat(),
        property_ids=list(property_ids),
        decision_days=[d.isoformat() for d in decision_days],
        ceiling=_data_ceiling(conn, decision_days),
        rows=rows,
        calibration=score_calibration(rows),
        direction=score_direction(rows),
        estimated_revenue=estimate_revenue(rows),
        price_ref_note=price_ref_note,
        memory_set_hash=memory_catalog_hash(),
        warnings=(
            ["Rows repeat the same stay night across decision days; see deduplicated calibration."]
            if len({(r.property_id, r.stay_date) for r in rows}) < len(rows) else []
        ),
        panel_counts=panel_counts,
        excluded_rows=excluded_rows,
    )


# -------------------------------------------------------------------------- scores


def _scored_label(row: ReplayRow) -> bool | None:
    if row.outcome_label is not None:
        return row.outcome_label
    if row.resolved:
        # Backward-compatible path for callers constructing the pre-contract
        # ReplayRow directly (the real replay always sets outcome_label).
        return row.booked_by_censor
    return None


def score_calibration(rows: list[ReplayRow], *, bins: int = 5) -> dict[str, Any]:
    """Reliability of predicted booking chance — only on RESOLVED nights.

    Terminal probability vs a censored outcome is apples-to-oranges, so unresolved
    future nights are excluded rather than plotted with "wide error bars".
    """
    eligible = [
        r for r in rows
        if r.resolved and r.expected_book_prob is not None and _scored_label(r) is not None
    ]
    reason = (
        "Predicted booking chance is terminal (books by check-in); nights still in the "
        "future are unresolved and are excluded so the curve is not misleading."
    )
    deduped: list[ReplayRow] = []
    seen: set[tuple[str, str]] = set()
    for row in sorted(eligible, key=lambda r: (r.property_id, r.stay_date, r.as_of)):
        key = (row.property_id, row.stay_date)
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    distinct_nights = len(deduped)
    positive_events = sum(1 for r in deduped if _scored_label(r))
    dedup_brier = sum(
        ((r.expected_book_prob or 0) - (1.0 if _scored_label(r) else 0.0)) ** 2
        for r in deduped
    ) / len(deduped) if deduped else None
    minimum_failures = []
    if len(eligible) < MIN_CALIBRATION_NIGHTS:
        minimum_failures.append(f"{len(eligible)} decision rows < {MIN_CALIBRATION_NIGHTS}")
    if distinct_nights < MIN_CALIBRATION_NIGHTS:
        minimum_failures.append(
            f"{distinct_nights} distinct resolved nights < {MIN_CALIBRATION_NIGHTS}"
        )
    if positive_events < MIN_DIRECTION_GROUP:
        minimum_failures.append(
            f"{positive_events} positive booked events < {MIN_DIRECTION_GROUP}"
        )
    if minimum_failures:
        return {
            "measurable": False,
            "eligible": len(eligible),
            "distinct_nights": distinct_nights,
            "positive_events": positive_events,
            "deduplicated": {
                "measurable": False,
                "eligible": distinct_nights,
                "positive_events": positive_events,
                "brier": dedup_brier,
            },
            "effective_n_warning": distinct_nights < len(eligible),
            "reason": reason + " Calibration floor not met: " + "; ".join(minimum_failures) + ".",
        }

    width = 1.0 / bins
    buckets: list[dict[str, Any]] = []
    for i in range(bins):
        lo, hi = i * width, (i + 1) * width
        grp = [
            r for r in eligible
            if (lo <= (r.expected_book_prob or 0) < hi)
            or (i == bins - 1 and (r.expected_book_prob or 0) == 1.0)
        ]
        if not grp:
            continue
        pred = sum((r.expected_book_prob or 0) for r in grp) / len(grp)
        obs = sum(1 for r in grp if _scored_label(r)) / len(grp)
        buckets.append({"lo": lo, "hi": hi, "n": len(grp),
                        "mean_predicted": pred, "observed_rate": obs})
    brier = sum(
        ((r.expected_book_prob or 0) - (1.0 if _scored_label(r) else 0.0)) ** 2
        for r in eligible
    ) / len(eligible)
    return {
        "measurable": True,
        "eligible": len(eligible),
        "distinct_nights": distinct_nights,
        "positive_events": positive_events,
        "bins": buckets,
        "brier": brier,
        "effective_n_warning": len(deduped) < len(eligible),
        "deduplicated": {
            "measurable": True,
            "eligible": len(deduped),
            "positive_events": positive_events,
            "brier": dedup_brier,
            "reason": "One earliest eligible decision per property/night."
                      " The per-decision score remains the primary panel.",
        },
    }


def score_direction(rows: list[ReplayRow]) -> dict[str, Any]:
    """Did nights priced ABOVE that day's listed price book stronger than those below?"""
    eligible = [
        r for r in rows
        if r.resolved and r.listed_as_of is not None and _scored_label(r) is not None
    ]
    above = [r for r in eligible if r.recommended_price > (r.listed_as_of or 0)]
    below = [r for r in eligible if r.recommended_price < (r.listed_as_of or 0)]
    if len(above) < MIN_DIRECTION_GROUP or len(below) < MIN_DIRECTION_GROUP:
        return {
            "measurable": False,
            "above_n": len(above),
            "below_n": len(below),
            "reason": "Too few resolved nights in one or both price-direction groups.",
        }
    return {
        "measurable": True,
        "above_n": len(above),
        "below_n": len(below),
        "above_book_rate": sum(1 for r in above if _scored_label(r)) / len(above),
        "below_book_rate": sum(1 for r in below if _scored_label(r)) / len(below),
    }


def estimate_revenue(rows: list[ReplayRow]) -> dict[str, Any]:
    """A LABELED revenue range. Both ends hold bookings fixed and swap the price, so
    neither can prove the engine beat the market. Reported per available night."""
    comparable = [
        r for r in rows
        if r.resolved and r.listed_as_of is not None and _scored_label(r) is not None
    ]
    if not comparable:
        return {"measurable": False, "reason": "No nights with an as-of listed price to compare."}
    n = len(comparable)

    booked = [r for r in comparable if r.resolved and _scored_label(r)]
    engine_a = sum(r.recommended_price for r in booked) / n
    listed_a = sum((r.listed_as_of or 0) for r in booked) / n

    def _p(r: ReplayRow) -> float:
        return r.expected_book_prob if r.expected_book_prob is not None else 0.0

    engine_b = sum(r.recommended_price * _p(r) for r in comparable) / n
    listed_b = sum((r.listed_as_of or 0) * _p(r) for r in comparable) / n

    from src.pricing import cancel_survival

    def _surv(row: ReplayRow) -> float:
        return cancel_survival(row.lead_time_days or 0)

    engine_c = sum(r.recommended_price * _surv(r) for r in booked) / n
    listed_c = sum((r.listed_as_of or 0) * _surv(r) for r in booked) / n

    return {
        "measurable": True,
        "comparable_nights": n,
        "booked_by_censor": len(booked),
        "assumption": "bookings do not respond to price (price-swap only) — not a causal result",
        "bookings_unchanged": {"engine_revpan": engine_a, "listed_revpan": listed_a,
                               "lift": engine_a - listed_a},
        "engine_demand_model": {"engine_revpan": engine_b, "listed_revpan": listed_b,
                                "lift": engine_b - listed_b},
        "cancel_hazard": {
            "engine_revpan": engine_c,
            "listed_revpan": listed_c,
            "lift": engine_c - listed_c,
            "note": (
                "Lead-time survival from the frozen simulator hazards "
                "(0.004/0.002/0.001/0.0004). Same multiplier at every price, "
                "so it does not move the RevPAN argmax. Assumed, not fitted."
            ),
        },
    }


# ---------------------------------------------------------------------- html report


def _fmt_money(x: float | None) -> str:
    return "—" if x is None else f"${x:,.0f}"


def _fmt_pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.0f}%"


def render_html(result: ReplayResult) -> str:
    c = result.ceiling
    cal = result.calibration
    direction = result.direction
    est = result.estimated_revenue

    if cal.get("measurable"):
        rows_html = "".join(
            f"<tr><td>{b['lo']:.0%}–{b['hi']:.0%}</td><td>{b['n']}</td>"
            f"<td>{_fmt_pct(b['mean_predicted'])}</td><td>{_fmt_pct(b['observed_rate'])}</td></tr>"
            for b in cal["bins"]
        )
        cal_html = (
            f"<p>Scored on <strong>{cal['eligible']}</strong> resolved nights "
            f"across <strong>{cal['distinct_nights']}</strong> distinct nights with "
            f"<strong>{cal['positive_events']}</strong> positive booking events "
            f"(Brier {cal['brier']:.3f}; lower is better).</p>"
            "<table><thead><tr><th>Predicted</th><th>Nights</th>"
            "<th>Mean predicted</th><th>Actually booked</th></tr></thead>"
            f"<tbody>{rows_html}</tbody></table>"
        )
    else:
        cal_html = (
            f"<p class='unmeasurable'>Unmeasurable on this window "
            f"({cal.get('eligible', 0)} decision rows, "
            f"{cal.get('distinct_nights', 0)} distinct nights, "
            f"{cal.get('positive_events', 0)} positive booking events).</p>"
            f"<p class='note'>{escape(cal.get('reason', ''))}</p>"
        )

    if direction.get("measurable"):
        dir_html = (
            f"<p>Priced above listed ({direction['above_n']} nights) booked "
            f"{_fmt_pct(direction['above_book_rate'])}; priced below "
            f"({direction['below_n']} nights) booked {_fmt_pct(direction['below_book_rate'])}.</p>"
        )
    else:
        dir_html = (
            f"<p class='unmeasurable'>Unmeasurable "
            f"(above={direction.get('above_n', 0)}, below={direction.get('below_n', 0)}).</p>"
            f"<p class='note'>{escape(direction.get('reason', ''))}</p>"
        )

    if est.get("measurable"):
        bu = est["bookings_unchanged"]
        dm = est["engine_demand_model"]
        est_html = (
            f"<p class='assumption'>Assumption: {escape(est['assumption'])}.</p>"
            "<table><thead><tr><th>Basis</th><th>Engine RevPAN</th>"
            "<th>Listed RevPAN</th><th>Difference</th></tr></thead><tbody>"
            f"<tr><td>Bookings held fixed (real outcomes)</td><td>{_fmt_money(bu['engine_revpan'])}</td>"
            f"<td>{_fmt_money(bu['listed_revpan'])}</td><td>{_fmt_money(bu['lift'])}</td></tr>"
            f"<tr><td>Engine's own demand model</td><td>{_fmt_money(dm['engine_revpan'])}</td>"
            f"<td>{_fmt_money(dm['listed_revpan'])}</td><td>{_fmt_money(dm['lift'])}</td></tr>"
            "</tbody></table>"
            f"<p class='note'>Per available night, over {est['comparable_nights']} comparable nights "
            f"({est['booked_by_censor']} booked by the censor).</p>"
            "<p class='warn'>This run does not show the engine beat the market. "
            "Both rows swap the price while holding bookings fixed, which cannot prove causation.</p>"
        )
    else:
        est_html = f"<p class='unmeasurable'>{escape(est.get('reason', 'Unmeasurable.'))}</p>"

    days = ", ".join(result.decision_days) if result.decision_days else "—"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Point-in-time replay</title>
<style>
  :root {{ --ink:#1a1a1a; --muted:#666; --line:#e2e2e2; --warn:#8a1c1c; --bg:#fff; }}
  body {{ font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif; color:var(--ink);
         background:var(--bg); margin:0; padding:24px; max-width:860px; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  h2 {{ font-size:16px; margin:28px 0 8px; border-bottom:1px solid var(--line); padding-bottom:4px; }}
  h3 {{ font-size:14px; margin:14px 0 6px; }}
  .sub {{ color:var(--muted); margin:0 0 16px; }}
  .strip {{ background:#f6f6f4; border:1px solid var(--line); border-radius:8px; padding:12px 16px;
            font-size:13px; color:var(--muted); }}
  table {{ border-collapse:collapse; width:100%; margin:8px 0; font-size:14px; }}
  th,td {{ text-align:left; padding:6px 10px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; }}
  .unmeasurable {{ font-weight:600; }}
  .note {{ color:var(--muted); font-size:13px; }}
  .assumption {{ font-style:italic; color:var(--muted); }}
  .warn {{ color:var(--warn); font-weight:600; }}
</style></head>
<body>
  <h1>Point-in-time replay — method demonstration</h1>
  <p class="sub">Window {escape(result.window_from)} &rarr; {escape(result.window_to)} ·
     censor {escape(result.censor_date)} · properties {escape(", ".join(result.property_ids))} ·
     generated {escape(result.generated_at)}</p>

  <div class="strip">
    Data ceiling (from the DB, not assumed): pacing observed
    {escape(str(c.pacing_min_as_of))} &rarr; {escape(str(c.pacing_max_as_of))};
    {c.decision_days} decision day(s); {c.reservations} reservation(s);
    {c.nights_with_pacing_listed} night(s) carry an as-of listed price.
    A two-winter revenue proof is not claimed.
  </div>

  <h2>1 · No peeking</h2>
  <p>Decision days: {escape(days)}.</p>
  <p>Public snow/ENSO vintages are gated by <code>published_at &le; D</code> and every signal
     passed <code>assert_no_lookahead</code>. Guesty write count: <strong>0</strong>.</p>
  <p class="note"><strong>Label definition:</strong> {escape(result.label_definition)}</p>
  <p class="note">{escape(result.price_ref_note)}</p>

  <h2>Panel accounting</h2>
  <p class="note">Decision-day candidate, emitted, resolved, unresolved, blocked, and
     already-booked counts are included in the JSON provenance under
     <code>panel_counts</code>. Repeated stay nights are flagged in the warnings and
     calibration includes a deduplicated effective-N view.</p>

  <h2>2 · Were the predictions sound</h2>
  <h3>Calibration</h3>
  {cal_html}
  <h3>Direction</h3>
  {dir_html}

  <h2>3 · Estimated revenue (estimate, not a verdict)</h2>
  {est_html}

  <h2>How to grow this</h2>
  <p class="note">Run <code>wp-price shadow-record</code> daily on the operator DB
     (no Guesty writes) so future months accumulate nights that have actually checked
     in. A real crystal-ball check waits until those resolved nights exist.</p>
</body></html>
"""


def write_reports(result: ReplayResult, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = result.generated_at
    json_path = out_dir / f"replay_{stamp}.json"
    csv_path = out_dir / f"replay_{stamp}.csv"
    html_path = out_dir / f"replay_{stamp}.html"

    json_path.write_text(result.to_json(), encoding="utf-8")

    headers = list(ReplayRow.__dataclass_fields__.keys())
    lines = [",".join(headers)]
    for r in result.rows:
        d = asdict(r)
        lines.append(",".join("" if d[h] is None else str(d[h]) for h in headers))
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    html_path.write_text(render_html(result), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "html": html_path}
