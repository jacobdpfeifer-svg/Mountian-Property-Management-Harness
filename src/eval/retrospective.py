"""Guesty retrospective: ceiling / comps / leakage vs realised prices.

This is the honest counterpart to `run_backtest`. That helper still scores the
full composer (including booking-probability) on *available* nights. This module
scores every historical night that has a realised listed or booked price, at a
fixed lead-time decision date, and splits the result into:

  1. Layers we CAN back with Guesty history (ceiling, leakage vs realised price;
     comps only when a snapshot existed on or before the decision date).
  2. Layers we CANNOT validate retrospectively (booking-probability / pacing).
     Guesty does not store the historical booking calendar. Reconstructing it
     from today's inventory (`pacing.backfill_from_inventory`) is biased and is
     never used here.

The naive counterfactual (engine price on nights that booked, else $0) is the
same estimator `run_backtest` already labels naive. It assumes conversion still
happens at a different price. That is an upper/lower bound, not a proof.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.ceiling import compute_ceiling
from src.comps import CompEvidence, comp_evidence
from src.compose import recommend_night
from src.config import load_policy
from src.db import PROPERTY_OWNER_IDS
from src.features import build_features
from src.leakage import scan_leakage
from src.utils import parse_date

THIN_SAMPLE_NOTE = (
    "Thin sample — intervals intentionally wide. One drought season is n=1, "
    "not a relationship."
)


@dataclass
class NightScore:
    property_id: str
    owner_id: str | None
    stay_date: date
    decision_date: date
    lead_days: int
    status: str
    season: str
    demand_strength: float
    demand_event: str | None
    guesty_listed: float | None
    guesty_booked: float | None
    realised_revenue: float
    ceiling_price: float
    ceiling_confidence: float
    ceiling_method: str
    floor_price: float
    leakage_kind: str
    leakage_detail: str
    comp_usable: bool
    comp_reason: str
    comp_price: float | None
    approx_comp_price: float | None
    approx_comp_reason: str
    layer_price: float
    engine_price: float | None
    expected_revpan: float | None
    expected_book_prob: float | None
    naive_cf_revenue: float
    booked_at: str | None


@dataclass
class PropertySummary:
    property_id: str
    owner_id: str | None
    nights: int
    booked_nights: int
    available_nights: int
    realised_revpan: float | None
    naive_cf_revpan: float | None
    naive_delta: float | None
    mean_ceiling_minus_booked: float | None
    peak_underprice_nights: int
    shoulder_over_discount_nights: int
    contemporaneous_comp_nights: int
    approx_comp_nights: int
    booked_at_coverage: float
    engine_nights: int


@dataclass
class RetrospectiveReport:
    lead_days: int
    start: date | None
    end: date | None
    calendar_span: tuple[str | None, str | None]
    reservation_span: tuple[str | None, str | None]
    nights: list[NightScore]
    by_property: dict[str, PropertySummary]
    by_owner: dict[str, PropertySummary]
    portfolio: PropertySummary
    warnings: list[str] = field(default_factory=list)
    confidence_note: str = THIN_SAMPLE_NOTE
    pacing_validated: bool = False


def listing_created_on(listing_id: str | None) -> date | None:
    """Guesty listing ids are Mongo ObjectIds; the first 4 bytes are created-at."""
    if not listing_id or len(listing_id) < 8:
        return None
    try:
        ts = int(listing_id[:8], 16)
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()
    except (TypeError, ValueError):
        return None


def _owner_for(conn: sqlite3.Connection, property_id: str) -> str | None:
    row = conn.execute(
        "SELECT owner_id FROM properties WHERE property_id = ?", (property_id,)
    ).fetchone()
    if row and row["owner_id"]:
        return str(row["owner_id"])
    return PROPERTY_OWNER_IDS.get(property_id)


def _layer_price(ceiling_price: float, findings: list[Any], listed: float | None) -> float:
    """Ceiling/leakage suggestion without treating P(book) as evidence."""
    listed = listed or ceiling_price
    if not findings:
        return ceiling_price
    by_kind = {f.kind: f for f in findings}
    if "peak_underprice" in by_kind:
        return float(by_kind["peak_underprice"].suggested_adjustment)
    if "shoulder_over_discount" in by_kind:
        return float(by_kind["shoulder_over_discount"].suggested_adjustment)
    if "orphan_gap" in by_kind:
        return float(by_kind["orphan_gap"].suggested_adjustment)
    return ceiling_price


def _summarise(scores: list[NightScore], *, property_id: str | None, owner_id: str | None) -> PropertySummary:
    n = len(scores)
    booked = [s for s in scores if s.status == "booked"]
    avail = [s for s in scores if s.status == "available"]
    realised = [s.realised_revenue for s in scores]
    cf = [s.naive_cf_revenue for s in scores]
    realised_revpan = sum(realised) / n if n else None
    naive_cf = sum(cf) / n if n else None
    gaps = [s.ceiling_price - float(s.guesty_booked) for s in booked if s.guesty_booked]
    booked_at_n = sum(1 for s in booked if s.booked_at)
    return PropertySummary(
        property_id=property_id or "ALL",
        owner_id=owner_id,
        nights=n,
        booked_nights=len(booked),
        available_nights=len(avail),
        realised_revpan=realised_revpan,
        naive_cf_revpan=naive_cf,
        naive_delta=(naive_cf - realised_revpan) if (naive_cf is not None and realised_revpan is not None) else None,
        mean_ceiling_minus_booked=(sum(gaps) / len(gaps)) if gaps else None,
        peak_underprice_nights=sum(1 for s in scores if s.leakage_kind == "peak_underprice"),
        shoulder_over_discount_nights=sum(1 for s in scores if s.leakage_kind == "shoulder_over_discount"),
        contemporaneous_comp_nights=sum(1 for s in scores if s.comp_usable),
        approx_comp_nights=sum(1 for s in scores if s.approx_comp_price is not None),
        booked_at_coverage=(booked_at_n / len(booked)) if booked else 0.0,
        engine_nights=sum(1 for s in scores if s.engine_price is not None),
    )


def score_history(
    conn: sqlite3.Connection,
    *,
    start: date | None = None,
    end: date | None = None,
    property_ids: list[str] | None = None,
    policy: dict[str, Any] | None = None,
    lead_days: int = 30,
    today: date | None = None,
) -> RetrospectiveReport:
    policy = policy or load_policy()
    today = today or date.today()
    warnings: list[str] = [
        "Booking-probability / pacing is NOT validated here. Guesty cannot return "
        "the historical booking calendar, and pacing.backfill_from_inventory is a "
        "biased reconstruction — not evidence.",
        "Guesty calendar listed_price on past nights is the price Guesty shows "
        "now, not a snapshot of the listing at booking time. Realised booked_price "
        "(fareAccommodation / nights) is the conversion evidence.",
        "Comp snapshots dated after the decision date are excluded from the "
        "primary ceiling. Any 'today's comps' figure is labelled approximation.",
    ]

    span = conn.execute(
        "SELECT MIN(stay_date) mn, MAX(stay_date) mx FROM nightly_inventory"
    ).fetchone()
    res_span = conn.execute(
        "SELECT MIN(check_in) mn, MAX(check_in) mx FROM reservations"
    ).fetchone() if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reservations'"
    ).fetchone() else None

    created: dict[str, date | None] = {}
    for r in conn.execute("SELECT property_id, pms_listing_id FROM properties"):
        created[r["property_id"]] = listing_created_on(r["pms_listing_id"])
        if created[r["property_id"]]:
            warnings.append(
                f"{r['property_id']} appeared in Guesty around {created[r['property_id']]} "
                "(decoded from the listing id). Calendar days before that are padding "
                "from the API range request, not nights this engine could have priced."
            )

    start = start or min((d for d in created.values() if d), default=None) or (
        parse_date(span["mn"]) if span and span["mn"] else today
    )
    end = end or min(today - timedelta(days=1), parse_date(span["mx"]) if span and span["mx"] else today)
    if end > today:
        end = today - timedelta(days=1)
        warnings.append("Future stay dates were dropped — they have no realised outcome yet.")

    features = build_features(conn, start, end, property_ids=property_ids, policy=policy)
    scores: list[NightScore] = []

    for feat in features:
        if feat.status == "blocked":
            continue
        if feat.listed_price is None and feat.booked_price is None:
            continue
        if feat.stay_date > today:
            continue
        opened = created.get(feat.property_id)
        if opened and feat.stay_date < opened:
            continue
        decision = feat.stay_date - timedelta(days=lead_days)
        priced = replace(
            feat,
            lead_time_days=lead_days,
            status="available" if feat.status == "available" else feat.status,
        )
        ceiling = compute_ceiling(conn, priced, policy, as_of=decision)
        listed = feat.listed_price if feat.listed_price is not None else feat.booked_price
        leak_feat = replace(
            priced,
            status="available",
            listed_price=listed,
        )
        findings = scan_leakage(leak_feat, ceiling, ceiling.ceiling_price, policy)
        primary = findings[0] if findings else None

        contemporaneous = comp_evidence(conn, priced, policy, as_of=decision)
        approx = comp_evidence(conn, priced, policy, allow_stale=True)
        approx_price = approx.price if approx and approx.usable else None
        if approx_price is not None and (contemporaneous is None or not contemporaneous.usable):
            warnings.append(
                "Some nights use today's/latest comp set as a labelled approximation "
                "because no snapshot existed at the historical decision date."
            )

        rec = recommend_night(
            conn, priced, policy=policy, as_of=decision, include_booked=True,
        )
        realised = float(feat.booked_price or 0.0) if feat.status == "booked" else 0.0
        engine = rec.recommended_price if rec else None
        naive_cf = float(engine) if (engine is not None and realised > 0) else 0.0

        scores.append(NightScore(
            property_id=feat.property_id,
            owner_id=_owner_for(conn, feat.property_id),
            stay_date=feat.stay_date,
            decision_date=decision,
            lead_days=lead_days,
            status=feat.status,
            season=feat.season,
            demand_strength=feat.demand_strength,
            demand_event=feat.demand_event,
            guesty_listed=feat.listed_price,
            guesty_booked=feat.booked_price,
            realised_revenue=realised,
            ceiling_price=ceiling.ceiling_price,
            ceiling_confidence=ceiling.confidence,
            ceiling_method=ceiling.method,
            floor_price=ceiling.floor_price,
            leakage_kind=(primary.kind if primary else "none"),
            leakage_detail=(primary.detail if primary else ""),
            comp_usable=bool(contemporaneous and contemporaneous.usable),
            comp_reason=(contemporaneous.reason if contemporaneous else "no comps"),
            comp_price=(contemporaneous.price if contemporaneous and contemporaneous.usable else None),
            approx_comp_price=approx_price,
            approx_comp_reason=(approx.reason if approx else "no comps"),
            layer_price=_layer_price(ceiling.ceiling_price, findings, listed),
            engine_price=engine,
            expected_revpan=(rec.expected_revpan if rec else None),
            expected_book_prob=(rec.expected_book_prob if rec else None),
            naive_cf_revenue=naive_cf,
            booked_at=None,
        ))

    booked_at_map: dict[tuple[str, str], str] = {}
    try:
        for row in conn.execute(
            "SELECT property_id, stay_date, booked_at FROM nightly_inventory "
            "WHERE booked_at IS NOT NULL"
        ):
            booked_at_map[(row["property_id"], row["stay_date"])] = str(row["booked_at"])
    except sqlite3.OperationalError:
        pass
    for s in scores:
        s.booked_at = booked_at_map.get((s.property_id, s.stay_date.isoformat()))

    # Deduplicate the approximation warning
    warnings = list(dict.fromkeys(warnings))

    by_prop: dict[str, PropertySummary] = {}
    grouped: dict[str, list[NightScore]] = defaultdict(list)
    for s in scores:
        grouped[s.property_id].append(s)
    for pid, rows in grouped.items():
        by_prop[pid] = _summarise(rows, property_id=pid, owner_id=rows[0].owner_id)

    by_owner: dict[str, PropertySummary] = {}
    owners: dict[str, list[NightScore]] = defaultdict(list)
    for s in scores:
        owners[s.owner_id or "unassigned"].append(s)
    for oid, rows in owners.items():
        by_owner[oid] = _summarise(rows, property_id=None, owner_id=oid)

    portfolio = _summarise(scores, property_id=None, owner_id=None)
    note = THIN_SAMPLE_NOTE
    if portfolio.nights < 20:
        note = f"LOW CONFIDENCE (n={portfolio.nights}). " + note
        warnings.append(f"only {portfolio.nights} nights scored; reporting low confidence")

    return RetrospectiveReport(
        lead_days=lead_days,
        start=start,
        end=end,
        calendar_span=(span["mn"] if span else None, span["mx"] if span else None),
        reservation_span=(
            (res_span["mn"], res_span["mx"]) if res_span else (None, None)
        ),
        nights=scores,
        by_property=by_prop,
        by_owner=by_owner,
        portfolio=portfolio,
        warnings=warnings,
        confidence_note=note,
        pacing_validated=False,
    )


def _pick_examples(scores: list[NightScore], k: int = 5) -> list[NightScore]:
    """Clearest nights to explain — mix of engine above and below Guesty, not a cherry-pick."""
    booked = [s for s in scores if s.status == "booked" and s.guesty_booked and s.engine_price]
    if not booked:
        booked = [s for s in scores if s.guesty_listed and s.engine_price]
    if not booked:
        return []
    ranked = sorted(
        booked,
        key=lambda s: abs(float(s.engine_price or 0) - float(s.guesty_booked or s.guesty_listed or 0)),
        reverse=True,
    )
    high = [s for s in ranked if float(s.engine_price or 0) > float(s.guesty_booked or s.guesty_listed or 0)]
    low = [s for s in ranked if float(s.engine_price or 0) < float(s.guesty_booked or s.guesty_listed or 0)]
    out: list[NightScore] = []
    # Interleave so a large favorable gap cannot crowd out the unfavorable ones.
    for pair in zip(high, low):
        for s in pair:
            if s not in out:
                out.append(s)
            if len(out) >= k:
                return out
    for s in high + low + ranked:
        if s not in out:
            out.append(s)
        if len(out) >= k:
            return out
    return out[:k]


def _money(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"${v:,.0f}"


def _pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v:.0%}"


def format_markdown(report: RetrospectiveReport) -> str:
    p = report.portfolio
    lines: list[str] = []
    lines.append("# Guesty vs this engine — honest historical comparison")
    lines.append("")
    lines.append(
        f"**Stay window:** {report.start} → {report.end}  "
        f"· **Decision lead time:** {report.lead_days} days before each night  "
        f"· **Nights scored:** {p.nights}"
    )
    lines.append("")
    lines.append(
        f"**What Guesty's API actually returned:** calendar nights "
        f"{report.calendar_span[0] or '—'} → {report.calendar_span[1] or '—'}; "
        f"reservation check-ins {report.reservation_span[0] or '—'} → "
        f"{report.reservation_span[1] or '—'}."
    )
    lines.append("")
    lines.append(f"**Confidence:** {report.confidence_note}")
    lines.append("")

    lines.append("## What this comparison can and cannot support")
    lines.append("")
    lines.append("### Backed by real historical data")
    lines.append("")
    lines.append(
        "- Finished reservations: stay dates, booking confirmation time (when Guesty "
        "sent `confirmedAt`), guest count, and what was actually paid "
        "(`fareAccommodation` / nights)."
    )
    lines.append(
        "- Today's Guesty calendar for those dates (listed price + current status). "
        "Treat listed price on past nights as Guesty's *current memory* of the rate, "
        "not a recovered 90/60/30-day snapshot."
    )
    lines.append(
        "- This engine's **ceiling**, **leakage scan** (peak underprice / shoulder "
        "over-discount / orphan gap), and **own-history** on nights whose booking "
        "was already confirmed by the decision date."
    )
    lines.append(
        "- Comp evidence **only** when a snapshot existed on or before the decision "
        f"date ({p.contemporaneous_comp_nights} night(s) in this run)."
    )
    lines.append("")
    lines.append("### Not validated — do not quote as proof")
    lines.append("")
    lines.append(
        "- **Booking-probability and pacing.** Guesty cannot return what the calendar "
        "looked like at 90/60/30/14/7 days out. The daily snapshotter "
        "(`src/pacing`) was not running then. `backfill_from_inventory` reconstructs "
        "prior days from *current* state and labels that output as biased — a night "
        "booked yesterday looks like it was booked weeks ago. This report does **not** "
        "call that function and does **not** claim the P(book|P) model is calibrated."
    )
    lines.append(
        "- **Expected RevPAN** on each night is the composer output. It is shown so "
        "you can see what the engine *would print today looking backward*. It is not "
        "a measured revenue lift."
    )
    lines.append(
        "- **Naive counterfactual RevPAN** (engine price if the night booked, else $0) "
        "is the same estimator already in `src/eval/backtest.py`. It assumes every "
        "guest who paid Guesty's price would also have paid the engine's price. If "
        "the engine is higher, that overstates revenue. If it is lower, it understates "
        "the rate they actually achieved. It is a bound, not a win."
    )
    if p.approx_comp_nights and p.contemporaneous_comp_nights < p.nights:
        lines.append(
            f"- **Today's comp set as approximation** on {p.approx_comp_nights} night(s). "
            "Those listings are the current curated set, scraped or entered around "
            "now, not the market as it stood at the historical decision date."
        )
    lines.append("")

    lines.append("## Portfolio")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Nights compared | {p.nights} |")
    lines.append(f"| Booked / still-open (historical leftover) | {p.booked_nights} / {p.available_nights} |")
    lines.append(f"| Realised RevPAN (Guesty money / scored nights) | {_money(p.realised_revpan)} |")
    lines.append(f"| Naive counterfactual RevPAN (unproven) | {_money(p.naive_cf_revpan)} |")
    lines.append(f"| Naive delta (engine − Guesty, unproven) | {_money(p.naive_delta)} |")
    lines.append(f"| Mean ceiling − booked price (headroom if conversion held) | {_money(p.mean_ceiling_minus_booked)} |")
    lines.append(f"| Peak-underprice flags | {p.peak_underprice_nights} |")
    lines.append(f"| Shoulder-over-discount flags | {p.shoulder_over_discount_nights} |")
    lines.append(f"| Nights with contemporaneous comps | {p.contemporaneous_comp_nights} |")
    lines.append(f"| Booked nights with a confirmation timestamp | {_pct(p.booked_at_coverage)} |")
    lines.append("")

    if p.naive_delta is None:
        lines.append("**Verdict:** not enough scored nights to compare.")
    elif abs(p.naive_delta) < 25:
        lines.append(
            "**Verdict:** the naive counterfactual is essentially a tie. That is not "
            "a case that this engine would have beaten Guesty PriceOptimizer. It is "
            "also not a case that Guesty clearly won. Do not sell it as either."
        )
    elif p.naive_delta > 0:
        lines.append(
            f"**Verdict:** the naive bound is {_money(p.naive_delta)} / night in this "
            "engine's favour. That is **not** proven extra revenue. It mostly says "
            "the ceiling/leakage layer wanted higher rates on nights that already "
            "converted at Guesty's price. Conversion at the higher price is unknown."
        )
    else:
        lines.append(
            f"**Verdict:** the naive bound is {_money(p.naive_delta)} / night against "
            "this engine. Guesty's realised rates were higher than what this engine "
            "would have recommended on booked nights, or the engine would have cut "
            "nights that still sold. Do not claim a win."
        )
    lines.append("")

    lines.append("## By property")
    lines.append("")
    lines.append(
        "| Property | Owner | Nights | Booked | Realised RevPAN | Naive CF RevPAN | Naive Δ | "
        "Ceiling − booked | Peak flags |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for pid in sorted(report.by_property):
        ps = report.by_property[pid]
        lines.append(
            f"| {pid} | {ps.owner_id or '—'} | {ps.nights} | {ps.booked_nights} | "
            f"{_money(ps.realised_revpan)} | {_money(ps.naive_cf_revpan)} | "
            f"{_money(ps.naive_delta)} | {_money(ps.mean_ceiling_minus_booked)} | "
            f"{ps.peak_underprice_nights} |"
        )
    lines.append("")

    lines.append("## By owner")
    lines.append("")
    lines.append(
        "Owner ids come from `config/portfolio/mont_luxe.yaml` "
        "(`northwoods` = Summit Haus + Overlook Ridge; `cloud9` = Cloud 9)."
    )
    lines.append("")
    lines.append(
        "| Owner | Properties in this run | Nights | Realised RevPAN | Naive CF RevPAN | Naive Δ |"
    )
    lines.append("|---|---|---:|---:|---:|---:|")
    for oid in sorted(report.by_owner):
        ps = report.by_owner[oid]
        props = sorted({n.property_id for n in report.nights if (n.owner_id or "unassigned") == oid})
        lines.append(
            f"| {oid} | {', '.join(props)} | {ps.nights} | "
            f"{_money(ps.realised_revpan)} | {_money(ps.naive_cf_revpan)} | {_money(ps.naive_delta)} |"
        )
    lines.append("")

    examples = _pick_examples(report.nights)
    lines.append("## Example nights (clearest gaps, both directions)")
    lines.append("")
    lines.append(
        "These are the nights where the engine price and Guesty's realised/listed "
        "price differ most. The list is mixed on purpose: a report that only showed "
        "favorable nights would not survive an operator who still has the Guesty "
        "folio in front of them."
    )
    lines.append("")
    if not examples:
        lines.append("_No comparable booked nights with an engine price._")
    for s in examples:
        gprice = s.guesty_booked if s.guesty_booked is not None else s.guesty_listed
        direction = "higher than" if (s.engine_price or 0) > (gprice or 0) else "lower than"
        event = s.demand_event or "no named event"
        if s.status == "booked" and (s.engine_price or 0) > (gprice or 0):
            outcome = (
                "Outcome: the night booked at Guesty's price. Charging the engine's "
                "higher rate is unproven — we do not know if that guest would still have converted."
            )
        elif s.status == "booked":
            outcome = (
                "Outcome: the night booked at Guesty's price. The engine's lower rate "
                "would have left money on a stay that already sold."
            )
        else:
            outcome = (
                "Outcome: the night did not book, so we cannot say a different rate would have filled it."
            )
        lines.append(
            f"- **{s.stay_date} · {s.property_id}** ({s.season}, {event}). "
            f"Guesty charged/listed {_money(gprice)}; "
            f"this engine at {s.lead_days} days out would have recommended "
            f"{_money(s.engine_price)} ({direction} Guesty). "
            f"Ceiling {_money(s.ceiling_price)} via `{s.ceiling_method}` "
            f"(confidence {s.ceiling_confidence:.0%}). "
            f"Leakage: {s.leakage_kind}"
            + (f" — {s.leakage_detail}" if s.leakage_detail else "")
            + ". "
            + (
                f"Contemporaneous comps {_money(s.comp_price)}."
                if s.comp_usable
                else (
                    f"No contemporaneous comps ({s.comp_reason}). "
                    + (
                        f"Today's-comp approximation {_money(s.approx_comp_price)} "
                        f"— not used as proof."
                        if s.approx_comp_price is not None
                        else "No usable comps even as approximation."
                    )
                )
            )
            + " "
            + outcome
        )
    lines.append("")

    lines.append("## Warnings")
    lines.append("")
    for w in report.warnings:
        lines.append(f"- {w}")
    lines.append("")
    lines.append(
        "Pacing model validated retrospectively: "
        f"**{'yes' if report.pacing_validated else 'no'}**."
    )
    lines.append("")
    return "\n".join(lines)


def write_report(report: RetrospectiveReport, path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(format_markdown(report), encoding="utf-8")
    return out


def seed_curated_comps(conn: sqlite3.Connection, root: Path | None = None) -> dict[str, int]:
    """Load the operator's curated comp CSVs so the approximation path has a set."""
    from src.ingest import CsvIngestAdapter

    root = root or Path(__file__).resolve().parents[2]
    counts = {"scrape": 0, "cloud9": 0, "cloud9_manual": 0}
    scrape = root / "data" / "scrape" / "comps.csv"
    if scrape.exists():
        counts["scrape"] = CsvIngestAdapter(comps_csv=scrape).load_comps(conn)
    cloud = root / "data" / "cloud9" / "comps.csv"
    if cloud.exists():
        counts["cloud9"] = CsvIngestAdapter(comps_csv=cloud).load_comps(conn)
    manual = root / "data" / "cloud9" / "comps_manual_snapshots.csv"
    if manual.exists():
        counts["cloud9_manual"] = CsvIngestAdapter(comps_csv=manual).load_comps(conn)
    conn.commit()
    return counts
