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
from typing import Any

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
    return out


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
