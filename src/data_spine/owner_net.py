"""Versioned owner-net contribution, reconciliation, and lineage trace.

Owner net for a reservation = owner-economics credits - debits from the current
(non-superseded, non-reversed) ledger lines. Taxes are pass-through and owner
payouts are cash settlement, so neither is counted.

An actual ledger line always wins. An assumption may fill a component only when
no actual line of that type exists, and the result then says exactly which
components were assumed. A component that is required but neither recorded nor
assumed makes the figure `incomplete`; it is never silently treated as zero.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.data_spine.ingest import current_rows

OWNER_NET_VERSION = "owner_net.v1"

# Components every stay must account for before its owner net is complete.
# Direct/owner stays carry no channel fee.
_REQUIRED = ("gross_lodging", "management_fee", "cleaning_cost")
_REQUIRED_CHANNEL_FEE = frozenset({"airbnb", "vrbo", "booking_com"})
_ECONOMIC = ("credit", "debit")


@dataclass(frozen=True)
class Assumption:
    """A labelled stand-in for a missing actual: fraction of gross lodging or a flat amount."""
    entry_type: str
    fraction_of_lodging: float | None = None
    flat_amount: float | None = None
    source: str = "unspecified assumption"


@dataclass
class OwnerNet:
    reservation_key: str
    version: str
    total: float
    status: str                         # actual | partially_assumed | incomplete | cancelled_no_money
    components: dict[str, float] = field(default_factory=dict)
    actual_components: list[str] = field(default_factory=list)
    assumed_components: dict[str, str] = field(default_factory=dict)
    missing_components: list[str] = field(default_factory=list)
    pending_lines: int = 0
    field_class: dict[str, str] = field(default_factory=dict)


def _signed(row: sqlite3.Row) -> float:
    amount = float(row["amount"])
    return amount if row["direction"] == "credit" else -amount


PMS_SOURCES = frozenset({"guesty"})


def effective_lines(conn: sqlite3.Connection, reservation_key: str) -> list[sqlite3.Row]:
    """Current, non-reversed ledger lines for a stay, with one source of money per stay.

    The PMS reports a stay's money at booking (pending); accounting reports the
    money that actually moved, under its own keys and its own categories (it may
    bundle cleaning into lodging, or settle in parts). Mixing the two by entry
    type double-counts or under-counts (2026-10-16 audit). So once *any* line from
    a non-PMS source exists for the stay, every PMS line is dropped and the
    accounting lines — pending and settled alike — are the stay's money.
    """
    rows = [r for r in current_rows(conn, "fact_financial_ledger", "t.reservation_key = ?", (reservation_key,))
            if r["settlement_state"] != "reversed"]
    if any(r["source_system"] not in PMS_SOURCES for r in rows):
        rows = [r for r in rows if r["source_system"] not in PMS_SOURCES]
    return rows


def owner_net_for_reservation(conn: sqlite3.Connection, reservation_key: str,
                              assumptions: list[Assumption] | None = None) -> OwnerNet:
    lines = [r for r in effective_lines(conn, reservation_key) if r["direction"] in _ECONOMIC]
    res = current_rows(conn, "fact_reservation_version", "t.entity_key = ?", (reservation_key,))
    channel = res[-1]["channel"] if res else (lines[0]["channel"] if lines else "other")
    status_cancelled = bool(res) and res[-1]["status"] == "cancelled"

    components: dict[str, float] = {}
    actual_types: set[str] = set()
    pending = 0
    for row in lines:
        if row["basis"] == "actual":
            actual_types.add(row["entry_type"])
        if row["settlement_state"] == "pending":
            pending += 1
        components[row["entry_type"]] = round(components.get(row["entry_type"], 0.0) + _signed(row), 2)

    out = OwnerNet(reservation_key, OWNER_NET_VERSION, 0.0, "actual", pending_lines=pending)
    required = list(_REQUIRED) + (["channel_fee"] if channel in _REQUIRED_CHANNEL_FEE else [])
    if status_cancelled and "gross_lodging" not in components:
        required = []  # a cancelled stay with no retained money owes nothing further
    lodging = components.get("gross_lodging", 0.0)
    for a in assumptions or []:
        if a.entry_type in components:
            continue  # an actual (or recorded) line exists; never override it
        if a.entry_type not in required:
            continue
        if a.fraction_of_lodging is not None:
            value = -round(abs(lodging) * a.fraction_of_lodging, 2)
        elif a.flat_amount is not None:
            value = -round(abs(a.flat_amount), 2)
        else:
            continue
        components[a.entry_type] = value
        out.assumed_components[a.entry_type] = a.source
    out.components = components
    out.actual_components = sorted(actual_types)
    out.missing_components = sorted(t for t in required if t not in components)
    out.total = round(sum(components.values()), 2)
    if out.missing_components:
        out.status = "incomplete"
    elif out.assumed_components or any(t not in actual_types for t in components):
        out.status = "partially_assumed"
    elif status_cancelled and not components:
        out.status = "cancelled_no_money"
    out.field_class = classify_components(
        components, actual_types=actual_types, assumed=set(out.assumed_components),
        channel=channel, cancelled_no_money=out.status == "cancelled_no_money",
    )
    return out


# Display fields. Amounts still come from the ledger; a label never invents a zero.
# cleaning_fee_income stays separate until an operator says it is retained.
_FIELD_SOURCES: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("settled_lodging", ("gross_lodging",), True),
    ("retained_guest_fees", ("guest_fee_income",), False),
    ("cleaning_fee_income", ("cleaning_fee_income",), False),
    ("channel_and_payment_fees", ("channel_fee", "payment_processing_fee"), False),
    ("management_fee", ("management_fee",), True),
    ("cleaning_and_turn", ("cleaning_cost",), True),
    ("consumables", ("consumables",), False),
    ("stay_maintenance", ("maintenance",), False),
    ("refunds_concessions_chargebacks", ("refund", "concession", "chargeback"), False),
    ("damage_recovery", ("damage_recovery",), False),
)
EXCLUDED_OWNERSHIP_COSTS = ("mortgage", "depreciation", "property_tax", "broad_ownership_costs")
RECONCILE_MIN = 0.99


def load_system_cost(path: Path) -> dict[str, Any]:
    """Load the operator's gitignored profitability hurdle inputs.

    A missing file is an expected external-data state.  A present file must be a
    complete, explicit configuration; partial values must not silently turn into
    a portfolio-wide allocation.
    """
    if not path.is_file():
        return {"status": "missing", "reason": f"system cost file is absent: {path}", "values": {}}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    required = ("annual_system_operating_cost_usd", "annual_sellable_nights")
    missing = [key for key in required if raw.get(key) is None]
    if missing:
        return {"status": "missing", "reason": f"system cost file omits {', '.join(missing)}", "values": raw}
    return {
        "status": "supplied", "reason": None,
        "values": {
            "annual_system_operating_cost": raw["annual_system_operating_cost_usd"],
            "annual_sellable_nights": raw["annual_sellable_nights"],
            "cost_share_by_property": raw.get("cost_share_by_property"),
            "nights_by_property": raw.get("nights_by_property"),
            "allocation_method": raw.get("allocation_method"),
        },
    }


def classify_components(components: dict[str, float], *, actual_types: set[str], assumed: set[str],
                        channel: str, cancelled_no_money: bool = False,
                        owner_block: bool = False) -> dict[str, str]:
    """Label each owner-net field actual, assumed, missing, or not_applicable.

    An absent optional cost is not_applicable. It is not recorded as an actual zero.
    """
    labels: dict[str, str] = {}
    if cancelled_no_money or owner_block:
        return {name: "not_applicable" for name, _, _ in _FIELD_SOURCES}
    for name, types, required in _FIELD_SOURCES:
        channel_required = name == "channel_and_payment_fees" and channel in _REQUIRED_CHANNEL_FEE
        if (name == "channel_and_payment_fees" and channel not in _REQUIRED_CHANNEL_FEE
                and not any(t in components or t in assumed for t in types)):
            labels[name] = "not_applicable"
            continue
        present = [t for t in types if t in components or t in assumed]
        if any(t in assumed for t in types):
            labels[name] = "assumed"
        elif present and all(t in actual_types for t in present):
            labels[name] = "actual"
        elif present:
            labels[name] = "assumed"
        elif required or channel_required:
            labels[name] = "missing"
        else:
            labels[name] = "not_applicable"
    if channel in _REQUIRED_CHANNEL_FEE and "channel_fee" not in components and "channel_fee" not in assumed:
        labels["channel_and_payment_fees"] = "missing"
    return labels


def owner_net_hurdle(*, annual_system_operating_cost: float | None,
                     annual_sellable_nights: int | None,
                     cost_share_by_property: dict[str, float] | None = None,
                     nights_by_property: dict[str, int] | None = None,
                     allocation_method: str | None = None) -> dict[str, Any]:
    """Required incremental owner net per available night.

    Portfolio rate = annual system operating cost / annual sellable nights.
    A per-property rate is reported only with an explicit cost share, that
    property's own sellable nights, and a named allocation method. Sharing the
    portfolio rate across homes would hide a cross-property subsidy.
    """
    excluded = EXCLUDED_OWNERSHIP_COSTS
    base = {"allocation_method": allocation_method, "excluded_ownership_costs": excluded,
            "annual_system_operating_cost": annual_system_operating_cost,
            "annual_sellable_nights": annual_sellable_nights,
            "per_available_night": None, "by_property": None}
    if annual_system_operating_cost is None or annual_sellable_nights is None:
        return {**base, "status": "missing",
                "reason": "annual system operating cost and annual sellable nights were not both supplied"}
    if annual_sellable_nights <= 0 or annual_system_operating_cost < 0:
        return {**base, "status": "missing",
                "reason": "sellable nights must be positive and system cost must be non-negative"}
    per = round(float(annual_system_operating_cost) / int(annual_sellable_nights), 2)
    by_property = None
    if cost_share_by_property or nights_by_property:
        if not allocation_method:
            return {**base, "per_available_night": per, "status": "missing",
                    "reason": "a per-property hurdle needs a named allocation method"}
        if not cost_share_by_property or not nights_by_property:
            return {**base, "per_available_night": per, "status": "missing",
                    "reason": "per-property hurdle needs both cost shares and each property's sellable nights"}
        if abs(sum(cost_share_by_property.values()) - 1.0) > 0.001:
            return {**base, "per_available_night": per, "status": "missing",
                    "reason": "cost shares must sum to 1"}
        if any(n <= 0 for n in nights_by_property.values()):
            return {**base, "per_available_night": per, "status": "missing",
                    "reason": "each property's sellable nights must be positive"}
        by_property = {}
        for pid, share in cost_share_by_property.items():
            nights = nights_by_property.get(pid)
            if nights is None:
                return {**base, "per_available_night": per, "status": "missing",
                        "reason": f"no sellable nights for {pid}"}
            property_cost = round(float(annual_system_operating_cost) * float(share), 2)
            by_property[pid] = {
                "cost_share": share, "allocated_cost": property_cost, "sellable_nights": nights,
                "per_available_night": round(property_cost / nights, 2),
            }
    return {**base, "status": "supplied", "per_available_night": per, "by_property": by_property,
            "reason": None}


def _overlap_nights(check_in: str, check_out: str, period_start: str, period_end: str) -> tuple[int, int]:
    stay_start = date.fromisoformat(check_in)
    stay_end = date.fromisoformat(check_out)
    window_start = date.fromisoformat(period_start)
    window_end = date.fromisoformat(period_end) + timedelta(days=1)
    total = (stay_end - stay_start).days
    lo = max(stay_start, window_start)
    hi = min(stay_end, window_end)
    inside = max(0, (hi - lo).days)
    return inside, total


def _worse_label(labels: list[str]) -> str:
    order = ("missing", "assumed", "actual", "not_applicable")
    for label in order:
        if label in labels:
            return label
    return "not_applicable"


def property_month(conn: sqlite3.Connection, property_id: str, period_start: str, period_end: str,
                   *, assumptions: list[Assumption] | None = None,
                   annual_system_operating_cost: float | None = None,
                   annual_sellable_nights: int | None = None,
                   cost_share_by_property: dict[str, float] | None = None,
                   nights_by_property: dict[str, int] | None = None,
                   allocation_method: str | None = None) -> dict[str, Any]:
    """One property, one month, from append-only spine facts.

    Owner net is prorated evenly across the stay's nights and only the nights
    inside the month are summed. The result is settled owner net only when every
    included stay is actual, every statement reconciles at or above 99% by count
    and value, and nothing required is missing. Anything else stays INCOMPLETE
    or partially_assumed and is not realized profit.
    """
    stays = current_rows(
        conn, "fact_reservation_version",
        "t.property_id = ? AND t.check_in <= ? AND t.check_out > ?",
        (property_id, period_end, period_start),
    )
    components: dict[str, float] = {}
    field_votes: dict[str, list[str]] = {}
    stay_rows = []
    exceptions: list[str] = []
    linked = 0
    money_stays = 0
    for stay in stays:
        net = owner_net_for_reservation(conn, stay["entity_key"], assumptions)
        inside, total = _overlap_nights(stay["check_in"], stay["check_out"], period_start, period_end)
        share = (inside / total) if total else 0.0
        portion = round(net.total * share, 2) if net.status != "incomplete" else None
        if net.components:
            money_stays += 1
        lines = effective_lines(conn, stay["entity_key"])
        if any(r["statement_key"] for r in lines):
            linked += 1
        elif net.components:
            exceptions.append(f"{stay['entity_key']} has money and no statement link")
        for key, value in net.components.items():
            components[key] = round(components.get(key, 0.0) + value * share, 2)
        for key, label in net.field_class.items():
            field_votes.setdefault(key, []).append(label)
        stay_rows.append({
            "reservation_key": stay["entity_key"], "status": net.status,
            "nights_in_month": inside, "nights": total, "owner_net": net.total,
            "month_owner_net": portion, "field_class": net.field_class,
            "missing": net.missing_components, "assumed": net.assumed_components,
            "pending_lines": net.pending_lines,
        })
    blocks = current_rows(
        conn, "dim_listing_constraint",
        "t.property_id = ? AND t.constraint_type = 'owner_block' AND t.active = 1 "
        "AND t.start_date <= ? AND t.end_date >= ?",
        (property_id, period_end, period_start),
    )
    block_nights = []
    for block in blocks:
        start = max(date.fromisoformat(block["start_date"]), date.fromisoformat(period_start))
        end = min(date.fromisoformat(block["end_date"]), date.fromisoformat(period_end))
        day = start
        while day <= end:
            block_nights.append(day.isoformat())
            day += timedelta(days=1)
    if block_nights:
        field_votes.setdefault("settled_lodging", []).append("not_applicable")
    statements = current_rows(
        conn, "fact_owner_statement",
        "t.property_id = ? AND t.period_start <= ? AND t.period_end >= ?",
        (property_id, period_end, period_start),
    )
    recs = []
    for stmt in statements:
        try:
            recs.append(reconcile_statement(conn, stmt["entity_key"]))
        except KeyError as exc:
            exceptions.append(str(exc))
    for rec in recs:
        if rec.status != "reconciled":
            exceptions.extend(f"{rec.statement_key}: {issue}" for issue in rec.issues)
    count_rate = None
    value_rate = None
    if recs:
        count_rate = round(sum(r.status == "reconciled" for r in recs) / len(recs), 4)
        reported = sum(abs(r.reported_owner_net) for r in recs)
        gap = sum(abs(r.difference) for r in recs)
        value_rate = round(1.0 - gap / reported, 4) if reported else (1.0 if count_rate == 1 else 0.0)
    stay_count_rate = round(linked / money_stays, 4) if money_stays else None
    field_class = {key: _worse_label(votes) for key, votes in field_votes.items()}
    for name, _, _ in _FIELD_SOURCES:
        field_class.setdefault(name, "not_applicable")
    if block_nights:
        field_class["settled_lodging_on_owner_block"] = "not_applicable"
    settled_total = round(sum(components.values()), 2) if stay_rows else None
    any_missing = any(v == "missing" for v in field_class.values()) or any(r["status"] == "incomplete" for r in stay_rows)
    any_assumed = any(v == "assumed" for v in field_class.values()) or any(r["status"] == "partially_assumed" for r in stay_rows)
    any_pending = any(r["pending_lines"] for r in stay_rows)
    rates = [r for r in (count_rate, value_rate, stay_count_rate) if r is not None]
    short_reconcile = (not recs) or any(r < RECONCILE_MIN for r in rates) or any_pending
    if not stay_rows and not recs:
        result_label = "INCOMPLETE"
        exceptions.append("no reservations and no owner statement in this period")
    elif any_missing or short_reconcile:
        result_label = "INCOMPLETE"
    elif any_assumed:
        result_label = "partially_assumed"
    else:
        result_label = "settled"
    if result_label != "settled":
        exceptions.append("figure is not settled owner net")
    return {
        "property_id": property_id, "period_start": period_start, "period_end": period_end,
        "version": OWNER_NET_VERSION, "stays": stay_rows, "owner_block_nights": block_nights,
        "components": components, "field_class": field_class,
        "month_owner_net": settled_total, "result_label": result_label,
        "reconciliation_count": count_rate, "reconciliation_value": value_rate,
        "reservation_link_rate": stay_count_rate, "exceptions": exceptions,
        "system_operating_cost": {
            "status": "supplied" if annual_system_operating_cost is not None else "missing",
            "amount": annual_system_operating_cost,
            "note": "recorded separately from pricing-influenced owner net",
        },
        "excluded_ownership_costs": EXCLUDED_OWNERSHIP_COSTS,
        "hurdle": owner_net_hurdle(
            annual_system_operating_cost=annual_system_operating_cost,
            annual_sellable_nights=annual_sellable_nights,
            cost_share_by_property=cost_share_by_property,
            nights_by_property=nights_by_property, allocation_method=allocation_method),
    }


def render_owner_month(report: dict[str, Any]) -> str:
    """Human-readable month. Never calls a partial figure realized profit."""
    label = report["result_label"]
    headline = ("Settled owner net from actual reconciled lines." if label == "settled"
                else "INCOMPLETE — this is not settled owner net." if label == "INCOMPLETE"
                else "Partially assumed — this is not settled owner net.")
    lines = [
        f"# Owner net — {report['property_id']} — {report['period_start']} to {report['period_end']}",
        "", headline, "",
        f"Result: {label}",
        f"Month owner net: {report['month_owner_net']}",
        "",
        "Components (amount, class):",
    ]
    for name, amount in sorted(report["components"].items()):
        lines.append(f"- {name}: {amount}")
    lines.append("")
    lines.append("Field class:")
    for name, klass in sorted(report["field_class"].items()):
        lines.append(f"- {name}: {klass}")
    hurdle = report["hurdle"]
    lines.extend(["", "Hurdle:",
                  f"- status: {hurdle['status']}",
                  f"- per available night: {hurdle['per_available_night']}",
                  f"- allocation method: {hurdle['allocation_method']}",
                  f"- reason: {hurdle['reason']}"])
    if hurdle.get("by_property"):
        for pid, row in sorted(hurdle["by_property"].items()):
            lines.append(f"- {pid}: {row['per_available_night']} on {row['sellable_nights']} nights "
                         f"(share {row['cost_share']})")
    lines.extend(["", "System operating cost is not inside owner net.",
                  "Excluded from pricing-influenced owner net: " + ", ".join(report["excluded_ownership_costs"]) + ".",
                  "", "Exceptions:"])
    if report["exceptions"]:
        lines.extend(f"- {item}" for item in report["exceptions"])
    else:
        lines.append("- none")
    lines.extend(["",
                  f"Reconciliation by statement count: {report['reconciliation_count']}",
                  f"Reconciliation by value: {report['reconciliation_value']}",
                  f"Reservation money linked to a statement: {report['reservation_link_rate']}",
                  "",
                  "Owner-block nights have no lodging revenue (not_applicable), not a zero actual."])
    if report["owner_block_nights"]:
        lines.append(f"Owner-block nights: {len(report['owner_block_nights'])}")
    text = "\n".join(lines) + "\n"
    if "realized profit" in text.lower():
        raise RuntimeError("owner-net report must not say realized profit")
    return text


@dataclass
class StatementReconciliation:
    statement_key: str
    reported_owner_net: float
    computed_owner_net: float
    payout_total: float | None
    difference: float
    status: str                         # reconciled | exception
    issues: list[str] = field(default_factory=list)


def reconcile_statement(conn: sqlite3.Connection, statement_key: str,
                        tolerance: float = 0.01) -> StatementReconciliation:
    stmt = current_rows(conn, "fact_owner_statement", "t.entity_key = ?", (statement_key,))
    if not stmt:
        raise KeyError(f"no owner statement {statement_key!r}")
    s = stmt[-1]
    lines = [r for r in current_rows(conn, "fact_financial_ledger", "t.statement_key = ?",
                                     (statement_key,)) if r["settlement_state"] != "reversed"]
    issues = []
    computed = round(sum(_signed(r) for r in lines if r["direction"] in _ECONOMIC), 2)
    payouts = [float(r["amount"]) for r in lines if r["entry_type"] == "owner_payout"]
    payout_total = round(sum(payouts), 2) if payouts else None
    if any(r["basis"] != "actual" for r in lines):
        issues.append("statement includes assumed ledger lines")
    if any(r["settlement_state"] != "settled" for r in lines):
        issues.append("statement includes unsettled ledger lines")
    if any(r["property_id"] != s["property_id"] for r in lines):
        issues.append("statement includes another property's ledger lines")
    reported = float(s["reported_owner_net"])
    diff = round(reported - computed, 2)
    if abs(diff) > tolerance:
        issues.append(f"reported owner net differs from ledger by {diff:+.2f}")
    if payout_total is not None and abs(payout_total - reported) > tolerance:
        issues.append(f"owner payout {payout_total:.2f} differs from reported {reported:.2f}")
    return StatementReconciliation(statement_key, reported, computed, payout_total, diff,
                                   "exception" if issues else "reconciled", issues)


def trace_reservation(conn: sqlite3.Connection, reservation_key: str,
                      assumptions: list[Assumption] | None = None) -> dict[str, Any]:
    """Decision -> reservation versions -> nights -> ledger -> owner net -> statements."""
    versions = conn.execute(
        "SELECT * FROM fact_reservation_version WHERE entity_key=? ORDER BY version_no",
        (reservation_key,),
    ).fetchall()
    if not versions:
        raise KeyError(f"no reservation {reservation_key!r}")
    current = versions[-1]
    decision = None
    if current["decision_key"]:
        rows = current_rows(conn, "fact_price_decision", "t.entity_key = ?", (current["decision_key"],))
        decision = dict(rows[-1]) if rows else None
    nights = [dict(r) for r in conn.execute(
        "SELECT stay_date, nightly_lodging, price_basis FROM fact_reservation_night "
        "WHERE reservation_version_id=? ORDER BY stay_date", (current["id"],))]
    ledger = [dict(r) for r in conn.execute(
        """SELECT l.*, NOT EXISTS (SELECT 1 FROM fact_financial_ledger s WHERE s.supersedes_id = l.id)
                  AS is_current
           FROM fact_financial_ledger l WHERE reservation_key=? ORDER BY entity_key, version_no""",
        (reservation_key,))]
    statements = sorted({r["statement_key"] for r in ledger if r["statement_key"] and r["is_current"]})
    return {
        "reservation_key": reservation_key,
        "decision": decision,
        "versions": [{"version_no": v["version_no"], "status": v["status"], "check_in": v["check_in"],
                      "check_out": v["check_out"], "gross_lodging": v["gross_lodging"],
                      "correction_reason": v["correction_reason"], "source_hash": v["source_hash"]}
                     for v in versions],
        "nights": nights,
        "ledger": ledger,
        "owner_net": owner_net_for_reservation(conn, reservation_key, assumptions),
        "statements": [reconcile_statement(conn, k) for k in statements],
    }
