"""Leakage scanners — peak underprice, shoulder over-discount, orphan gaps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.ceiling import CeilingResult
from src.features import NightFeatures

LeakKind = Literal[
    "peak_underprice",
    "shoulder_over_discount",
    "orphan_gap",
    "access_cliff",
    "none",
]


@dataclass
class LeakageFinding:
    kind: LeakKind
    severity: float  # 0-1
    suggested_adjustment: float  # absolute price suggestion contribution (pre-clamp)
    detail: str
    # Orphan gaps are primarily a MIN-STAY problem, not a price problem: a 2-night
    # hole between bookings usually cannot be sold at any price while a 3-night
    # minimum is in force. v1 only discounted. Price is the second lever.
    min_stay_action: int | None = None


def scan_leakage(
    feat: NightFeatures,
    ceiling: CeilingResult,
    composed_base: float,
    policy: dict[str, Any],
    *,
    access_risk: float = 0.0,
) -> list[LeakageFinding]:
    """Return actionable leakage findings for an available night."""
    if feat.status != "available":
        return []

    findings: list[LeakageFinding] = []
    leak = policy.get("leakage", {})
    listed = feat.listed_price if feat.listed_price is not None else composed_base

    peak = leak.get("peak_underprice", {})
    min_demand = float(peak.get("min_demand_strength", 0.65))
    under_ratio = float(peak.get("underprice_ratio", 0.85))
    lift = float(peak.get("lift_toward_ceiling", 0.70))
    if feat.demand_strength >= min_demand and listed < ceiling.ceiling_price * under_ratio:
        target = listed + (ceiling.ceiling_price - listed) * lift
        severity = min(1.0, (ceiling.ceiling_price - listed) / max(ceiling.ceiling_price, 1.0))
        event = feat.demand_event or "high demand"
        findings.append(
            LeakageFinding(
                kind="peak_underprice",
                severity=severity,
                suggested_adjustment=target,
                detail=(
                    f"Peak underprice: demand {feat.demand_strength:.2f} ({event}); "
                    f"listed ${listed:.0f} vs ceiling ${ceiling.ceiling_price:.0f}"
                ),
            )
        )

    shoulder = leak.get("shoulder_over_discount", {})
    max_demand = float(shoulder.get("max_demand_strength", 0.35))
    floor_ratio = float(shoulder.get("floor_ratio", 0.95))
    shoulder_floor = ceiling.floor_price * floor_ratio
    if feat.demand_strength <= max_demand and listed < shoulder_floor:
        findings.append(
            LeakageFinding(
                kind="shoulder_over_discount",
                severity=min(1.0, (shoulder_floor - listed) / max(shoulder_floor, 1.0)),
                suggested_adjustment=shoulder_floor,
                detail=(
                    f"Shoulder over-discount: demand {feat.demand_strength:.2f}; "
                    f"listed ${listed:.0f} below productive floor ${shoulder_floor:.0f}"
                ),
            )
        )

    orphan = leak.get("orphan_gap", {})
    gap_mult = float(orphan.get("discount_multiplier", 0.88))
    suggest_min_stay = bool(orphan.get("suggest_min_stay_relaxation", True))
    if feat.is_orphan_gap:
        gap_price = composed_base * gap_mult
        plural = "s" if feat.gap_size != 1 else ""
        detail = (
            f"Orphan gap ({feat.gap_size} night{plural}) between bookings — "
            f"gap-fill candidate at {gap_mult:.0%} of base"
        )
        action = None
        if suggest_min_stay:
            action = feat.gap_size
            # Prefer the engine policy standing min when present; fall back to PMS.
            from src.min_stay import resolve_policy_min_stay

            standing = resolve_policy_min_stay(feat.season, feat.lead_time_days, policy)
            if standing is None:
                standing = feat.min_stay
            if standing is not None and standing > feat.gap_size:
                detail += (
                    f"; standing min-stay is {standing} so this hole is UNSELLABLE at any "
                    f"price — relax to {feat.gap_size} first"
                )
            else:
                detail += f"; hold min-stay at {feat.gap_size}"
        findings.append(
            LeakageFinding(
                kind="orphan_gap",
                severity=0.6,
                suggested_adjustment=gap_price,
                detail=detail,
                min_stay_action=action,
            )
        )

    access_cfg = policy.get("access", {})
    if access_cfg.get("enabled", True) and access_risk > 0:
        risk_hi = float(access_cfg.get("max_upward_move_when_risk_above", 0.8))
        max_up = float(access_cfg.get("max_upward_move_pct", 0.05))
        lead = feat.lead_time_days if feat.lead_time_days is not None else 999
        if access_risk >= risk_hi and lead <= 7 and listed is not None:
            cap = listed * (1.0 + max_up)
            if composed_base > cap:
                findings.append(
                    LeakageFinding(
                        kind="access_cliff",
                        severity=min(1.0, access_risk),
                        suggested_adjustment=cap,
                        detail=(
                            f"Access cliff: Berthoud risk {access_risk:.0%} within "
                            f"{lead}d — cap upward move at +{max_up:.0%} over listed"
                        ),
                    )
                )

    return findings


def apply_leakage_price(
    composed_base: float,
    findings: list[LeakageFinding],
) -> tuple[float, LeakageFinding | None]:
    """Choose the primary leakage-driven price when findings exist.

    Priority: peak lift > access cliff cap > orphan gap discount > shoulder floor raise.
    """
    if not findings:
        return composed_base, None
    by_kind = {f.kind: f for f in findings}
    if "peak_underprice" in by_kind:
        f = by_kind["peak_underprice"]
        return f.suggested_adjustment, f
    if "access_cliff" in by_kind:
        f = by_kind["access_cliff"]
        return f.suggested_adjustment, f
    if "orphan_gap" in by_kind:
        f = by_kind["orphan_gap"]
        return f.suggested_adjustment, f
    if "shoulder_over_discount" in by_kind:
        f = by_kind["shoulder_over_discount"]
        return f.suggested_adjustment, f
    return composed_base, findings[0]
