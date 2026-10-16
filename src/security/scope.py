"""The exact three-property portfolio allowlist.

One object answers "is this property / listing in scope?" for every boundary:
sync, webhook, recommendation, audit, and push. Anything else is quarantined and
produces an audit event. The scope fails closed: if the declared portfolio cannot
be loaded, or does not contain exactly the expected homes, nothing is in scope.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Iterable

# The declared Mont Luxe portfolio. config/portfolio/mont_luxe.yaml must name
# exactly these homes; a mismatch is a configuration error, not a widening.
EXPECTED_PROPERTY_IDS = frozenset({"summit_haus", "overlook_ridge", "cloud_9"})

BOUNDARIES = frozenset({"sync", "webhook", "recommendation", "audit", "push", "canary", "review", "ingest"})


class ScopeError(RuntimeError):
    """The portfolio scope itself is misconfigured; callers must fail closed."""


class OutOfScope(RuntimeError):
    """A property or listing outside the allowlist reached a guarded boundary."""


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    property_id: str | None
    reason: str


@dataclass(frozen=True)
class PortfolioScope:
    property_ids: frozenset[str]
    # Guesty listing id -> property_id, only for in-scope properties.
    listing_ids: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.property_ids != EXPECTED_PROPERTY_IDS:
            raise ScopeError(
                f"portfolio scope must be exactly {sorted(EXPECTED_PROPERTY_IDS)}, "
                f"got {sorted(self.property_ids)}"
            )
        stray = {pid for pid in self.listing_ids.values() if pid not in self.property_ids}
        if stray:
            raise ScopeError(f"listing map points outside the portfolio: {sorted(stray)}")

    # -- checks ---------------------------------------------------------------
    def check_property(self, property_id: str | None) -> ScopeDecision:
        if property_id and property_id in self.property_ids:
            return ScopeDecision(True, property_id, "in_scope")
        return ScopeDecision(False, property_id, "unknown_property")

    def check_listing(self, listing_id: str | None) -> ScopeDecision:
        if not listing_id:
            return ScopeDecision(False, None, "missing_listing_id")
        pid = self.listing_ids.get(str(listing_id))
        if pid:
            return ScopeDecision(True, pid, "in_scope")
        return ScopeDecision(False, None, "unknown_listing")

    def enforce(self, conn: sqlite3.Connection | None, *, boundary: str,
                property_id: str | None = None, listing_id: str | None = None) -> str:
        """Return the in-scope property_id or raise OutOfScope after auditing it."""
        if boundary not in BOUNDARIES:
            raise ValueError(f"unknown boundary {boundary!r}")
        decision = (self.check_listing(listing_id) if listing_id is not None
                    else self.check_property(property_id))
        if not decision.allowed:
            quarantine(conn, boundary=boundary, property_id=property_id,
                       listing_id=listing_id, reason=decision.reason)
            raise OutOfScope(f"{boundary}: {decision.reason} "
                             f"(property={property_id!r}, listing={'set' if listing_id else None})")
        assert decision.property_id is not None
        return decision.property_id

    def filter_properties(self, conn: sqlite3.Connection | None, property_ids: Iterable[str],
                          *, boundary: str) -> list[str]:
        """Keep in-scope ids; audit (quarantine) the rest instead of raising."""
        kept = []
        for pid in property_ids:
            if pid in self.property_ids:
                kept.append(pid)
            else:
                quarantine(conn, boundary=boundary, property_id=pid, listing_id=None,
                           reason="unknown_property")
        return kept


def quarantine(conn: sqlite3.Connection | None, *, boundary: str, property_id: str | None,
               listing_id: str | None, reason: str) -> dict:
    from src.security.audit import record_event

    # Listing ids are confidential (public repo): record that one was present and
    # its last four characters, never the whole id.
    return record_event(
        conn, event_type="scope_quarantine", boundary=boundary, severity="critical",
        subject=property_id or "unknown",
        detail={"reason": reason,
                "listing_suffix": str(listing_id)[-4:] if listing_id else None},
    )


def load_scope(conn: sqlite3.Connection | None = None) -> PortfolioScope:
    """Build the scope from the portfolio config, the local listing map, and the DB.

    Raises ScopeError (fail closed) when the portfolio is not exactly the three homes.
    """
    from src.config import load_portfolio_config

    try:
        cfg = load_portfolio_config()
    except Exception as exc:  # unreadable config must not widen scope
        raise ScopeError(f"portfolio config unreadable: {exc}") from exc
    props = frozenset(str(p) for p in (cfg.get("properties") or {}))
    listing_ids: dict[str, str] = {}
    from src.pms.guesty import LOCKED_LISTING_PROPERTY_IDS

    for lid, pid in LOCKED_LISTING_PROPERTY_IDS.items():
        if pid in props:
            listing_ids[str(lid)] = str(pid)
    if conn is not None:
        try:
            rows = conn.execute(
                "SELECT property_id, pms_listing_id FROM properties WHERE pms_listing_id IS NOT NULL"
            ).fetchall()
        except sqlite3.Error:
            rows = []
        for row in rows:
            if row[0] in props:
                listing_ids.setdefault(str(row[1]), str(row[0]))
    return PortfolioScope(props, listing_ids)
