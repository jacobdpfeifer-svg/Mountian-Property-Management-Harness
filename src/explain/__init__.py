"""Explainability — attribution, not narration.

The v1 build emitted reasons with hardcoded weights (base_compose=0.8, ceiling_gap=0.9,
...) and ranked by those constants. Because `base_compose` outranked most signals, the
top-3 reasons were dominated by boilerplate that appeared on every night regardless of
what actually moved the price. It described the inputs; it did not attribute the output.

Reasons now carry a `contribution` in dollars — the signed effect of that factor on the
final price — and are ranked by |contribution|. A reason that moved the price by $0 never
displaces one that moved it by $80.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ReasonCode = Literal[
    "ceiling_gap",
    "event_boost",
    "comp_move",
    "gap_night",
    "lead_time",
    "dow",
    "inquiry_soft",
    "season",
    "shoulder_floor",
    "base_compose",
    "revpan_optimum",
    "guardrail",
    "thin_history",
    "pacing",
    "min_stay",
]


@dataclass
class Reason:
    code: ReasonCode
    message: str
    contribution: float = 0.0   # signed dollars this factor moved the final price
    always_show: bool = False   # guardrails/blocks must never be ranked out

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "contribution": round(self.contribution, 2),
        }


def select_top_reasons(reasons: list[Reason], max_n: int = 3) -> list[Reason]:
    """Rank by absolute dollar contribution; pin must-show reasons to the front."""
    pinned = [r for r in reasons if r.always_show]
    rest = sorted(
        (r for r in reasons if not r.always_show),
        key=lambda r: abs(r.contribution),
        reverse=True,
    )
    out: list[Reason] = []
    seen: set[str] = set()
    for r in [*pinned, *rest]:
        if r.code in seen:
            continue
        seen.add(r.code)
        out.append(r)
        if len(out) >= max_n:
            break
    return out
