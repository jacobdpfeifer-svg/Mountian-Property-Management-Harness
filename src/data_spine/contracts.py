"""Versioned ingestion contracts for the data spine.

A contract declares every field it accepts. Anything else in a source record
(guest names, emails, raw payloads) is dropped before validation, so it can never
reach a fact table or the quarantine table. A record that is ambiguous about
identity, money, price basis, or time is quarantined, never repaired by guessing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable

# Price bases the spine understands. "unknown" is listed so a source can say so
# honestly, but it always quarantines: an unlabelled price may be nightly or an
# all-in total and must not feed a model or an owner-net figure.
PRICE_BASES = frozenset({
    "nightly_ex_fees",      # host nightly rate before guest fees and taxes
    "nightly_all_in",       # nightly rate including guest-paid fees, before taxes
    "stay_total_ex_fees",   # whole stay, before guest fees and taxes
    "stay_total_all_in",    # whole stay including guest fees, before taxes
    "unknown",
})
CURRENCIES = frozenset({"USD"})
CHANNELS = frozenset({"airbnb", "vrbo", "booking_com", "direct", "owner", "other"})

# Owner-economics direction of each ledger entry type. Taxes are pass-through
# and excluded from owner net; they are still recorded for reconciliation.
LEDGER_ENTRY_DIRECTION = {
    "gross_lodging": "credit",
    "guest_fee_income": "credit",
    "cleaning_fee_income": "credit",
    "channel_fee": "debit",
    "payment_processing_fee": "debit",
    "management_fee": "debit",
    "cleaning_cost": "debit",
    "consumables": "debit",
    "refund": "debit",
    "maintenance": "debit",
    "damage_recovery": "credit",
    "tax_collected": "passthrough",
    "tax_remitted": "passthrough",
    "owner_payout": "settlement",   # cash movement to the owner, not economics
    "adjustment": None,             # direction must be stated explicitly
}


class Reason:
    MISSING_FIELD = "MISSING_FIELD"
    BAD_TYPE = "BAD_TYPE"
    BAD_ENUM = "BAD_ENUM"
    BAD_DATE = "BAD_DATE"
    BAD_TIMESTAMP = "BAD_TIMESTAMP"
    AMBIGUOUS_MONEY = "AMBIGUOUS_MONEY"
    AMBIGUOUS_PRICE_BASIS = "AMBIGUOUS_PRICE_BASIS"
    UNKNOWN_IDENTITY = "UNKNOWN_IDENTITY"
    INCONSISTENT = "INCONSISTENT"
    OUT_OF_ORDER_VERSION = "OUT_OF_ORDER_VERSION"


@dataclass(frozen=True)
class Field:
    name: str
    kind: str                 # str | int | money | signed_money | date | timestamp | enum
    required: bool = True
    choices: frozenset[str] | None = None


@dataclass(frozen=True)
class Contract:
    name: str
    schema_version: str
    table: str
    key: Callable[[dict[str, Any]], str]
    fields: tuple[Field, ...]
    property_field: str | None = "property_id"
    extra_checks: Callable[[dict[str, Any]], list[tuple[str, str]]] | None = None

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


# Lineage fields every contract carries.
_LINEAGE = (
    Field("source_system", "str"),
    Field("source_record_id", "str", required=False),
    Field("source_updated_at", "timestamp"),
    Field("observed_at", "timestamp"),
    Field("correction_reason", "str", required=False),
)


def _money_ok(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_field(f: Field, value: Any) -> tuple[str, str] | None:
    if value is None or value == "":
        return (Reason.MISSING_FIELD, f.name) if f.required else None
    if f.kind == "str":
        return None if isinstance(value, str) else (Reason.BAD_TYPE, f.name)
    if f.kind == "int":
        ok = isinstance(value, int) and not isinstance(value, bool)
        return None if ok else (Reason.BAD_TYPE, f.name)
    if f.kind == "money":
        return None if _money_ok(value) and value >= 0 else (Reason.AMBIGUOUS_MONEY, f.name)
    if f.kind == "signed_money":
        return None if _money_ok(value) else (Reason.AMBIGUOUS_MONEY, f.name)
    if f.kind == "date":
        try:
            date.fromisoformat(str(value))
            return None if len(str(value)) == 10 else (Reason.BAD_DATE, f.name)
        except ValueError:
            return (Reason.BAD_DATE, f.name)
    if f.kind == "timestamp":
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return (Reason.BAD_TIMESTAMP, f.name)
        # A naive timestamp is ambiguous across the Denver DST boundary.
        return None if parsed.tzinfo is not None else (Reason.BAD_TIMESTAMP, f.name)
    if f.kind == "enum":
        assert f.choices is not None
        if f.name == "price_basis" and value == "unknown":
            return (Reason.AMBIGUOUS_PRICE_BASIS, f.name)
        if value not in f.choices:
            code = (Reason.AMBIGUOUS_PRICE_BASIS if f.name == "price_basis"
                    else Reason.AMBIGUOUS_MONEY if f.name == "currency" else Reason.BAD_ENUM)
            return (code, f.name)
        return None
    raise AssertionError(f"unknown field kind {f.kind}")


def validate(contract: Contract, record: dict[str, Any], allowed_property_ids: frozenset[str]
             ) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Project `record` onto the contract and return (clean, problems)."""
    clean = {name: record.get(name) for name in contract.field_names}
    problems = [p for f in contract.fields if (p := _check_field(f, clean[f.name])) is not None]
    if contract.property_field:
        pid = clean.get(contract.property_field)
        if pid and pid not in allowed_property_ids:
            problems.append((Reason.UNKNOWN_IDENTITY, contract.property_field))
    if not problems and contract.extra_checks:
        problems.extend(contract.extra_checks(clean))
    return clean, problems


def _enum(name: str, choices: frozenset[str] | set[str], required: bool = True) -> Field:
    return Field(name, "enum", required, frozenset(choices))


# -- per-contract consistency checks ------------------------------------------

def _reservation_checks(r: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    nights = (date.fromisoformat(r["check_out"]) - date.fromisoformat(r["check_in"])).days
    if nights <= 0 or nights != r["nights"]:
        out.append((Reason.INCONSISTENT, "nights"))
    # Night-level lodging must be derivable without guessing the basis.
    if r["price_basis"] not in ("stay_total_ex_fees", "stay_total_all_in"):
        out.append((Reason.AMBIGUOUS_PRICE_BASIS, "price_basis"))
    return out


def _ledger_checks(r: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    if r["entry_type"] not in LEDGER_ENTRY_DIRECTION:
        return [(Reason.BAD_ENUM, "entry_type")]
    expected = LEDGER_ENTRY_DIRECTION[r["entry_type"]]
    if expected is None:
        if r.get("direction") not in ("credit", "debit"):
            out.append((Reason.AMBIGUOUS_MONEY, "direction"))
    elif r.get("direction") not in (None, expected):
        out.append((Reason.INCONSISTENT, "direction"))
    if r["settlement_state"] == "settled" and not r.get("settled_at"):
        out.append((Reason.MISSING_FIELD, "settled_at"))
    return out


def _statement_checks(r: dict[str, Any]) -> list[tuple[str, str]]:
    if r["period_end"] < r["period_start"]:
        return [(Reason.INCONSISTENT, "period_end")]
    return []


def _market_checks(r: dict[str, Any]) -> list[tuple[str, str]]:
    return [(Reason.INCONSISTENT, "los")] if r["los"] < 1 else []


def _constraint_checks(r: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    if r["effect"] != "restrict":
        out.append((Reason.INCONSISTENT, "effect"))
    if r["end_date"] < r["start_date"]:
        out.append((Reason.INCONSISTENT, "end_date"))
    if r["active"] not in (0, 1):
        out.append((Reason.BAD_TYPE, "active"))
    return out


def _decision_checks(r: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    if r["recommended_price"] <= 0:
        out.append((Reason.AMBIGUOUS_MONEY, "recommended_price"))
    if r["human_decision"] == "edited" and r.get("human_price") is None:
        out.append((Reason.MISSING_FIELD, "human_price"))
    return out


CONTRACTS: dict[str, Contract] = {}


def _register(c: Contract) -> Contract:
    CONTRACTS[c.name] = c
    return c


PRICE_DECISION = _register(Contract(
    "price_decision", "1.0", "fact_price_decision", key=lambda r: str(r["decision_key"]),
    fields=_LINEAGE + (
        Field("decision_key", "str"), Field("property_id", "str"), Field("stay_date", "date"),
        Field("run_id", "str", required=False), Field("policy_hash", "str"),
        Field("calibration_hash", "str", required=False), Field("data_hash", "str"),
        Field("model_version", "str"), _enum("price_basis", PRICE_BASES), _enum("currency", CURRENCIES),
        Field("current_price", "money", required=False), Field("recommended_price", "money"),
        _enum("human_decision", {"pending", "approved", "rejected", "edited", "not_required"}),
        Field("human_price", "money", required=False), Field("applied_price", "money", required=False),
        _enum("autonomy_level", {"observe", "suggest", "escalate", "handle", "blocked"}),
    ),
    extra_checks=_decision_checks,
))

RESERVATION = _register(Contract(
    "reservation", "1.0", "fact_reservation_version", key=lambda r: str(r["reservation_key"]),
    fields=_LINEAGE + (
        Field("reservation_key", "str"), Field("property_id", "str"), _enum("channel", CHANNELS),
        _enum("status", {"confirmed", "modified", "cancelled"}), Field("check_in", "date"),
        Field("check_out", "date"), Field("nights", "int"), Field("booked_at", "timestamp"),
        _enum("price_basis", PRICE_BASES), _enum("currency", CURRENCIES),
        Field("gross_lodging", "money"), Field("guest_fees", "money"),
        Field("decision_key", "str", required=False),
    ),
    extra_checks=_reservation_checks,
))

CALENDAR = _register(Contract(
    "calendar_observation", "1.0", "fact_calendar_observation",
    key=lambda r: f"{r['property_id']}|{r['stay_date']}",
    fields=_LINEAGE + (
        Field("property_id", "str"), Field("stay_date", "date"),
        _enum("status", {"available", "booked", "blocked"}),
        Field("listed_price", "money", required=False), Field("min_stay", "int", required=False),
        _enum("price_basis", PRICE_BASES), _enum("currency", CURRENCIES),
    ),
))

LEDGER = _register(Contract(
    "financial_ledger", "1.0", "fact_financial_ledger", key=lambda r: str(r["entry_key"]),
    fields=_LINEAGE + (
        Field("entry_key", "str"), Field("reservation_key", "str", required=False),
        Field("property_id", "str"), _enum("channel", CHANNELS),
        _enum("entry_type", set(LEDGER_ENTRY_DIRECTION)), Field("direction", "str", required=False),
        Field("amount", "money"), _enum("currency", CURRENCIES), _enum("basis", {"actual", "assumed"}),
        _enum("settlement_state", {"pending", "settled", "reversed"}),
        Field("settled_at", "timestamp", required=False), Field("statement_key", "str", required=False),
    ),
    extra_checks=_ledger_checks,
))

OWNER_STATEMENT = _register(Contract(
    "owner_statement", "1.0", "fact_owner_statement", key=lambda r: str(r["statement_key"]),
    fields=_LINEAGE + (
        Field("statement_key", "str"), Field("owner_id", "str"), Field("property_id", "str"),
        Field("period_start", "date"), Field("period_end", "date"),
        # Owner net may legitimately be negative in a month of heavy costs, so it
        # is validated as a finite number rather than a non-negative amount.
        Field("reported_owner_net", "signed_money"), _enum("currency", CURRENCIES),
    ),
    extra_checks=_statement_checks,
))

MARKET = _register(Contract(
    "market_observation", "1.0", "fact_market_observation",
    key=lambda r: f"{r['comp_key']}|{r['stay_date']}|{r['los']}|{r['observed_at']}",
    property_field=None,
    fields=_LINEAGE + (
        Field("comp_key", "str"), Field("stay_date", "date"), Field("los", "int"),
        Field("guests", "int", required=False), Field("price", "money"),
        _enum("price_basis", PRICE_BASES), _enum("currency", CURRENCIES),
    ),
    extra_checks=_market_checks,
))

OPS_TASK = _register(Contract(
    "ops_task", "1.0", "fact_ops_task", key=lambda r: str(r["task_key"]),
    fields=_LINEAGE + (
        Field("task_key", "str"), Field("property_id", "str"),
        _enum("task_type", {"turn", "inspection", "maintenance", "incident"}),
        Field("service_date", "date"),
        _enum("status", {"scheduled", "in_progress", "completed", "failed", "cancelled"}),
        Field("vendor", "str"), Field("cost", "money", required=False), _enum("currency", CURRENCIES),
        Field("reservation_key", "str", required=False),
    ),
))

LISTING_CONSTRAINT = _register(Contract(
    "listing_constraint", "1.0", "dim_listing_constraint", key=lambda r: str(r["constraint_key"]),
    fields=_LINEAGE + (
        Field("constraint_key", "str"), Field("property_id", "str"),
        _enum("constraint_type", {"owner_block", "maintenance", "capacity", "emergency", "min_stay_floor"}),
        Field("start_date", "date"), Field("end_date", "date"), Field("effect", "str"),
        Field("active", "int"),
    ),
    extra_checks=_constraint_checks,
))
