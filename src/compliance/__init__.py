"""Compliance register: permits, inspections, contacts, insurance, and their deadlines.

This is a document-and-deadline tracker, not a legal oracle. Rule packs in
config/compliance/ are transcriptions with source URLs and an explicit review
state. Every check returns one of

    evidence_on_file   a verified credential exists and has not expired
    unverified         a credential exists but nobody has verified it (or it
                       cannot be checked, e.g. listing text not available)
    expiring           inside the pack's warn window
    expired            past its expiry or renewal date
    missing            nothing on file

and the report never says a property is "compliant".
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.config import ROOT, load_portfolio_config, load_yaml

RULE_PACK_DIR = ROOT / "config" / "compliance"
STATUSES = ("evidence_on_file", "unverified", "expiring", "expired", "missing")
_SEVERITY = {"evidence_on_file": 0, "unverified": 1, "expiring": 2, "expired": 3, "missing": 3}


@dataclass
class Credential:
    property_id: str
    jurisdiction: str
    credential_type: str
    identifier: str | None = None
    issued_at: str | None = None
    expires_at: str | None = None
    evidence_ref: str | None = None
    verification_status: str = "unverified"
    verified_by: str | None = None
    notes: str | None = None
    permitted_occupancy: int | None = None
    rule_pack_version: str | None = None


@dataclass
class CheckResult:
    property_id: str
    jurisdiction: str | None
    credential_type: str
    label: str
    status: str
    detail: str
    deadline: str | None = None
    optional: bool = False
    source: str | None = None
    review: str = "unreviewed"

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in ("property_id", "jurisdiction", "credential_type", "label",
                                              "status", "detail", "deadline", "optional", "source",
                                              "review")}


@dataclass
class ComplianceReport:
    as_of: date
    results: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"as_of": self.as_of.isoformat(), "warnings": self.warnings,
                "results": [r.as_dict() for r in self.results]}


def load_rule_pack(jurisdiction: str, directory: Path | None = None) -> dict[str, Any]:
    path = (directory or RULE_PACK_DIR) / f"{jurisdiction}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no rule pack for jurisdiction {jurisdiction!r} at {path}")
    pack = load_yaml(path)
    for key in ("jurisdiction", "version", "source_urls", "requirements"):
        if key not in pack:
            raise ValueError(f"rule pack {path.name} missing {key!r}")
    for req in pack["requirements"]:
        # Every entry must say where it came from and whether a person has
        # reviewed it, so nothing unreviewed can read as settled law.
        for key in ("credential_type", "source", "review"):
            if not req.get(key):
                raise ValueError(f"rule pack {path.name}: {req.get('credential_type')!r} missing {key!r}")
    return pack


def occupancy_cap(pack: dict[str, Any], bedrooms: int | None) -> tuple[int | None, str | None]:
    """Lowest occupancy limit the pack implies for a home: flat cap or bedroom formula."""
    caps: list[tuple[int, str]] = []
    if pack.get("max_occupancy") is not None:
        caps.append((int(pack["max_occupancy"]), f"pack maximum {int(pack['max_occupancy'])}"))
    formula = pack.get("occupancy_formula") or {}
    if formula and bedrooms is not None:
        if int(bedrooms) == 0 and formula.get("studio") is not None:
            caps.append((int(formula["studio"]), f"studio limit {int(formula['studio'])}"))
        else:
            n = int(formula.get("per_bedroom", 2)) * int(bedrooms) + int(formula.get("plus", 0))
            caps.append((n, f"{formula.get('per_bedroom', 2)} per bedroom x {bedrooms} + "
                            f"{formula.get('plus', 0)} = {n} ({formula.get('basis', 'formula')})"))
    if not caps:
        return None, None
    return min(caps)


def evidence_hash(ref: str | None) -> str | None:
    if not ref:
        return None
    path = Path(ref).expanduser()
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_credential(conn: sqlite3.Connection, c: Credential) -> bool:
    """Insert or refresh one credential. Returns True when it was new."""
    from src.ops.db import ensure_ops_tables

    ensure_ops_tables(conn)
    if c.verification_status not in ("unverified", "verified", "rejected"):
        raise ValueError(f"bad verification_status {c.verification_status!r}")
    if not c.identifier or not c.identifier.strip():
        raise ValueError("a credential needs a stable identifier")
    if c.verification_status == "verified" and not c.verified_by:
        raise ValueError("a verified credential needs verified_by")
    digest = evidence_hash(c.evidence_ref)
    if c.verification_status == "verified" and digest is None:
        raise ValueError("a verified credential needs a readable evidence file")
    existed = conn.execute(
        """SELECT credential_id FROM property_credentials WHERE property_id=? AND credential_type=?
           AND identifier IS ?""",
        (c.property_id, c.credential_type, c.identifier),
    ).fetchone()
    conn.execute(
        """INSERT INTO property_credentials (property_id, jurisdiction, credential_type, identifier,
               permitted_occupancy, issued_at, expires_at, evidence_ref, evidence_hash,
               verification_status, verified_at, verified_by, rule_pack_version, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,CASE WHEN ?='verified' THEN datetime('now') END,?,?,?)
           ON CONFLICT(property_id, credential_type, identifier) DO UPDATE SET
               jurisdiction=excluded.jurisdiction,
               permitted_occupancy=excluded.permitted_occupancy,
               issued_at=excluded.issued_at,
               expires_at=excluded.expires_at,
               evidence_ref=excluded.evidence_ref,
               evidence_hash=excluded.evidence_hash,
               verification_status=excluded.verification_status,
               verified_at=excluded.verified_at,
               verified_by=excluded.verified_by,
               rule_pack_version=excluded.rule_pack_version,
               notes=excluded.notes""",
        (c.property_id, c.jurisdiction, c.credential_type, c.identifier,
         c.permitted_occupancy, c.issued_at, c.expires_at, c.evidence_ref, digest,
         c.verification_status, c.verification_status, c.verified_by,
         c.rule_pack_version, c.notes),
    )
    conn.commit()
    return existed is None


def _next_fixed_date(issued: date, month_day: str) -> date:
    month, day = (int(x) for x in month_day.split("-"))
    candidate = date(issued.year, month, day)
    # Issued on the renewal day itself means renewed for the next cycle.
    return candidate if candidate > issued else date(issued.year + 1, month, day)


def deadline_for(cred: sqlite3.Row, renewal: dict[str, Any]) -> date | None:
    """Expiry from the credential, else from the pack's renewal rule."""
    if cred["expires_at"]:
        return date.fromisoformat(str(cred["expires_at"])[:10])
    kind = (renewal or {}).get("kind", "none")
    issued = date.fromisoformat(str(cred["issued_at"])[:10]) if cred["issued_at"] else None
    if kind == "fixed_date" and issued:
        return _next_fixed_date(issued, str(renewal["month_day"]))
    if kind == "annual_from_issue" and issued:
        try:
            return issued.replace(year=issued.year + 1)
        except ValueError:  # Feb 29
            # A Feb-29 credential renews on the last day of February in the
            # following year; adding 365 days would incorrectly yield Mar 1.
            return date(issued.year + 1, 2, 28)
    return None


def listing_mentions(identifier: str | None, text: str | None) -> bool | None:
    """None when there is nothing to check against."""
    if not identifier or text is None:
        return None
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
    return norm(identifier) in norm(text)


def _check_requirement(
    rows: list[sqlite3.Row],
    req: dict[str, Any],
    *,
    property_id: str,
    jurisdiction: str,
    as_of: date,
    listing_text: str | None,
    max_occupancy: int | None,
    pack_max_occupancy: int | None,
) -> CheckResult:
    label = str(req.get("label") or req["credential_type"])
    ctype = str(req["credential_type"])
    optional = bool(req.get("optional", False))
    need = int(req.get("count", 1))
    live = [r for r in rows if r["verification_status"] != "rejected"]

    def result(status: str, detail: str, deadline: date | None = None) -> CheckResult:
        return CheckResult(property_id, jurisdiction, ctype, label, status, detail,
                           deadline.isoformat() if deadline else None, optional,
                           str(req.get("source") or ""), str(req.get("review") or "unreviewed"))

    if len(live) < need:
        have = f"{len(live)} of {need} on file" if need > 1 else "nothing on file"
        return result("missing", have + (" (optional: only if applicable)" if optional else ""))
    worst = "evidence_on_file"
    details: list[str] = []
    earliest: date | None = None
    warn = int(req.get("warn_days", 30))
    for r in live:
        deadline = deadline_for(r, req.get("renewal") or {})
        status = "evidence_on_file" if r["verification_status"] == "verified" else "unverified"
        if status == "evidence_on_file":
            current_hash = evidence_hash(r["evidence_ref"])
            if current_hash is None or current_hash != r["evidence_hash"]:
                status = "unverified"
                details.append(f"{r['identifier'] or ctype}: evidence file missing or changed")
        if deadline is not None:
            earliest = deadline if earliest is None or deadline < earliest else earliest
            if deadline < as_of:
                status = "expired"
                details.append(f"{r['identifier'] or ctype} expired {deadline}")
            elif deadline <= as_of + timedelta(days=warn):
                status = "expiring" if _SEVERITY["expiring"] > _SEVERITY[status] else status
                details.append(f"{r['identifier'] or ctype} due {deadline}")
        elif (req.get("renewal") or {}).get("kind") not in (None, "none"):
            status = max(status, "unverified", key=_SEVERITY.__getitem__)
            details.append(f"{r['identifier'] or ctype}: no issue/expiry date recorded")
        if r["verification_status"] != "verified":
            details.append(f"{r['identifier'] or ctype} not verified")
        if req.get("listing_match"):
            hit = listing_mentions(r["identifier"], listing_text)
            if hit is None:
                status = max(status, "unverified", key=_SEVERITY.__getitem__)
                details.append("listing text not available to confirm the number is advertised")
            elif not hit:
                status = max(status, "unverified", key=_SEVERITY.__getitem__)
                details.append(f"number {r['identifier']} not found in listing text")
        if req.get("occupancy_check"):
            permitted = r["permitted_occupancy"]
            known = [c for c in (permitted, pack_max_occupancy) if c is not None]
            cap = min(int(c) for c in known) if known else None
            if cap is not None and max_occupancy is not None and max_occupancy > int(cap):
                status = max(status, "unverified", key=_SEVERITY.__getitem__)
                details.append(f"listing sleeps {max_occupancy} but permit allows {cap}")
        worst = max(worst, status, key=_SEVERITY.__getitem__)
    return result(worst, "; ".join(dict.fromkeys(details)) or "verified and current", earliest)


def check(
    conn: sqlite3.Connection,
    as_of: date | None = None,
    *,
    property_ids: list[str] | None = None,
    listing_texts: dict[str, str] | None = None,
    rule_dir: Path | None = None,
) -> ComplianceReport:
    as_of = as_of or date.today()
    report = ComplianceReport(as_of=as_of)
    props = load_portfolio_config().get("properties") or {}
    occupancy: dict[str, Any] = {}
    bedrooms: dict[str, Any] = {}
    try:
        for r in conn.execute("SELECT property_id, max_occupancy, bedrooms FROM properties"):
            occupancy[r["property_id"]] = r["max_occupancy"]
            bedrooms[r["property_id"]] = r["bedrooms"]
    except sqlite3.OperationalError:
        pass
    seen_packs: set[str] = set()
    for pid, cfg in props.items():
        if property_ids and pid not in property_ids:
            continue
        jurisdiction = (cfg or {}).get("jurisdiction")
        if not jurisdiction:
            report.results.append(CheckResult(pid, None, "jurisdiction", "STR jurisdiction",
                                              "missing", "jurisdiction not recorded in "
                                              "config/portfolio/mont_luxe.yaml; no rule pack "
                                              "applies until it is",
                                              review="operator_confirm"))
            continue
        pack = load_rule_pack(str(jurisdiction), rule_dir)
        if jurisdiction not in seen_packs:
            seen_packs.add(jurisdiction)
            if not pack.get("reviewed_by"):
                report.warnings.append(
                    f"rule pack {pack['version']} has not been reviewed by a person; "
                    f"sources: {', '.join(pack['source_urls'])}")
        rows = conn.execute(
            "SELECT * FROM property_credentials WHERE property_id=? AND jurisdiction=?",
            (pid, jurisdiction),
        ).fetchall()
        by_type: dict[str, list[sqlite3.Row]] = {}
        for r in rows:
            by_type.setdefault(r["credential_type"], []).append(r)
        cap, cap_basis = occupancy_cap(pack, bedrooms.get(pid))
        for req in pack["requirements"]:
            report.results.append(_check_requirement(
                by_type.get(req["credential_type"], []), req, property_id=pid,
                jurisdiction=str(jurisdiction), as_of=as_of,
                listing_text=(listing_texts or {}).get(pid),
                max_occupancy=occupancy.get(pid), pack_max_occupancy=cap,
            ))
        report.results.append(_booked_occupancy(conn, pid, str(jurisdiction), as_of, rows, cap,
                                                cap_basis, report))
    return report


def _booked_occupancy(conn: sqlite3.Connection, pid: str, jurisdiction: str, as_of: date,
                      creds: list[sqlite3.Row], pack_cap: int | None, cap_basis: str | None,
                      report: ComplianceReport) -> CheckResult:
    """Cross-check booked guest counts (last 12 months and next 12) against the cap."""
    caps = [(int(r["permitted_occupancy"]),
             f"{r['verification_status']} permit allows {int(r['permitted_occupancy'])}")
            for r in creds
            if r["permitted_occupancy"] is not None and r["verification_status"] != "rejected"]
    if pack_cap is not None:
        caps.append((pack_cap, cap_basis or f"limit {pack_cap}"))
    label = "Booked guest counts within the occupancy limit"
    source = "reservations.guest_count vs permit / rule pack occupancy"
    if not caps:
        return CheckResult(pid, jurisdiction, "booked_occupancy", label, "unverified",
                           "no occupancy limit on file to compare bookings against",
                           source=source, review="derived")
    cap, basis = min(caps)
    try:
        rows = conn.execute(
            """SELECT reservation_id, check_in, guest_count FROM reservations
               WHERE property_id=? AND LOWER(status) IN ('confirmed','checked_in','checked_out')
                 AND check_out>=? AND check_in<=? ORDER BY check_in""",
            (pid, (as_of - timedelta(days=365)).isoformat(),
             (as_of + timedelta(days=365)).isoformat()),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    unknown = [r for r in rows if r["guest_count"] is None]
    over = [r for r in rows if r["guest_count"] is not None and int(r["guest_count"]) > cap]
    if over:
        listed = ", ".join(f"{str(r['check_in'])[:10]} ({r['guest_count']} guests)" for r in over[:5])
        report.warnings.append(f"{pid}: {len(over)} booking(s) exceed the occupancy limit of {cap} "
                               f"({basis}): {listed}")
        return CheckResult(pid, jurisdiction, "booked_occupancy", label, "unverified",
                           f"{len(over)} of {len(rows)} booking(s) exceed {cap} ({basis}): {listed}",
                           source=source, review="derived")
    detail = f"{len(rows)} booking(s) checked against {cap} ({basis})"
    if unknown:
        detail += f"; {len(unknown)} with no guest count"
    # Within the limit is only evidence when the limit is a verified permit;
    # a limit from an unreviewed rule pack is itself unverified.
    verified_cap = basis.startswith("verified permit")
    status = "evidence_on_file" if rows and not unknown and verified_cap else "unverified"
    return CheckResult(pid, jurisdiction, "booked_occupancy", label, status, detail,
                       source=source, review="derived")


def render_text(report: ComplianceReport) -> str:
    lines = [f"Compliance register as of {report.as_of} "
             "(document and deadline tracking only; not a legal determination)", ""]
    for w in report.warnings:
        lines.append(f"WARNING: {w}")
    if report.warnings:
        lines.append("")
    current = None
    for r in report.results:
        if r.property_id != current:
            current = r.property_id
            lines.append(f"{r.property_id} [{r.jurisdiction or 'jurisdiction unknown'}]")
        opt = " (optional)" if r.optional else ""
        due = f" due {r.deadline}" if r.deadline else ""
        review = "" if r.review == "reviewed" else f" [{r.review}]"
        lines.append(f"  {r.status:<17} {r.label}{opt}{due}{review} - {r.detail}")
    return "\n".join(lines)
