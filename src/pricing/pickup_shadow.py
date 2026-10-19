"""Pooled additive pickup, as an experimental shadow. Not read by default.yaml.

The price input is the residual versus a reference curve, shrunk toward zero.
One booking cannot move the residual by more than `max_one_booking`. Missing
or stale history returns a neutral residual of 0 with a reason.
"""

from __future__ import annotations


def shrunk_pickup_residual(
    observed: float | None,
    reference: float | None,
    *,
    n_history: int,
    prior_strength: float = 8.0,
    max_one_booking: float = 0.15,
    stale: bool = False,
) -> dict[str, float | str | None]:
    if stale or observed is None or reference is None or n_history < 0:
        return {"residual": 0.0, "quality": "unavailable", "reason": "stale_or_missing"}
    if reference < 0 or observed < 0:
        return {"residual": 0.0, "quality": "unavailable", "reason": "negative_share"}
    raw = observed - reference
    weight = n_history / (n_history + prior_strength)
    shrunk = weight * raw
    if abs(raw) > max_one_booking and n_history <= 1:
        shrunk = max(-max_one_booking, min(max_one_booking, raw))
        reason = "one_booking_bound"
    else:
        reason = "shrunk"
    return {"residual": shrunk, "quality": "ok", "reason": reason}
