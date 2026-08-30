"""Dynamic minimum-stay resolution (date/season × lead time) + gap overrides.

Large-group luxury homes need LOS rules that protect peak weekends far out and
relax close-in so inventory fills. Orphan gaps shorter than the standing rule
temporarily override that rule so the hole remains sellable.

OWNER-TUNABLE: Exact buckets and night counts live in
`config/policies/default.yaml` → `min_stay_rules`. Defaults are reasoned starting
points for Winter Park sleeps-16–18 homes — confirm with the property owner
before trusting auto-push of minNights.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.features import NightFeatures


MinStaySource = Literal["policy", "gap_override", "inventory", "none"]


@dataclass(frozen=True)
class MinStayDecision:
    """Effective minimum stay for one available night."""

    recommended_min_stay: int | None
    policy_min_stay: int | None
    inventory_min_stay: int | None
    source: MinStaySource
    gap_override: bool
    detail: str


def resolve_policy_min_stay(
    season: str,
    lead_days: int | None,
    policy: dict[str, Any],
) -> int | None:
    """Look up standing min-nights from the season × lead-time table.

    Returns None when the feature is disabled or no rule matches.
    """
    cfg = policy.get("min_stay_rules") or {}
    if not cfg.get("enabled", False):
        return None

    by_season = cfg.get("by_season") or {}
    curves = by_season.get(season) or by_season.get("default") or []
    if not curves:
        fallback = cfg.get("fallback_min_nights")
        return int(fallback) if fallback is not None else None

    lead = 0 if lead_days is None else max(0, int(lead_days))
    for row in curves:
        if int(row["min_lead_days"]) <= lead <= int(row["max_lead_days"]):
            return int(row["min_nights"])

    fallback = cfg.get("fallback_min_nights")
    return int(fallback) if fallback is not None else None


def decide_min_stay(
    feat: NightFeatures,
    policy: dict[str, Any],
    gap_min_stay_action: int | None = None,
) -> MinStayDecision:
    """Resolve effective min-stay: policy table, then gap override when tighter.

    Priority:
      1. Gap override — when the orphan window is shorter than the standing rule,
         relax to gap_size so the hole is sellable.
      2. Policy table — season × lead-time lookup.
      3. Inventory/PMS value — pass-through when policy is disabled.
    """
    inventory = feat.min_stay
    policy_min = resolve_policy_min_stay(feat.season, feat.lead_time_days, policy)

    orphan_cfg = (policy.get("leakage") or {}).get("orphan_gap") or {}
    allow_gap = bool(orphan_cfg.get("suggest_min_stay_relaxation", True))

    standing = policy_min if policy_min is not None else inventory

    if (
        allow_gap
        and feat.is_orphan_gap
        and gap_min_stay_action is not None
        and gap_min_stay_action > 0
        and standing is not None
        and gap_min_stay_action < standing
    ):
        return MinStayDecision(
            recommended_min_stay=int(gap_min_stay_action),
            policy_min_stay=policy_min,
            inventory_min_stay=inventory,
            source="gap_override",
            gap_override=True,
            detail=(
                f"Orphan gap of {gap_min_stay_action} night(s) — relaxed min-stay "
                f"from {standing} to {gap_min_stay_action}"
            ),
        )

    if policy_min is not None:
        lead = feat.lead_time_days if feat.lead_time_days is not None else "?"
        return MinStayDecision(
            recommended_min_stay=policy_min,
            policy_min_stay=policy_min,
            inventory_min_stay=inventory,
            source="policy",
            gap_override=False,
            detail=f"Policy min-stay {policy_min} for {feat.season} at {lead}d lead",
        )

    if inventory is not None:
        return MinStayDecision(
            recommended_min_stay=int(inventory),
            policy_min_stay=None,
            inventory_min_stay=inventory,
            source="inventory",
            gap_override=False,
            detail=f"PMS/inventory min-stay {inventory} (policy disabled)",
        )

    return MinStayDecision(
        recommended_min_stay=None,
        policy_min_stay=None,
        inventory_min_stay=None,
        source="none",
        gap_override=False,
        detail="No min-stay rule or inventory value",
    )
