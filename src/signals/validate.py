"""Observation validation — out-of-range is failed, never clamped."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.signals.store import Observation, QUALITIES

# Float noise at FieldSpec bounds (e.g. swe_pct 3.0000000000000004 vs max 3.0).
# Values within EPS of a bound are accepted as-is — never rewritten/clamped.
BOUND_EPS = 1e-9


@dataclass
class ValidationResult:
    ok: bool
    observation: Observation | None
    reason: str = ""


def validate_observation(
    obs: Observation,
    *,
    value_min: float | None = None,
    value_max: float | None = None,
    max_staleness_days: int | None = None,
    as_of: str | None = None,
) -> ValidationResult:
    """Reject invalid observations as failed. Never clamp values into range."""
    if obs.quality not in QUALITIES:
        return ValidationResult(False, None, f"invalid quality {obs.quality!r}")

    if obs.quality != "ok":
        # Unavailable / failed / blocked / stale pass through without value checks.
        return ValidationResult(True, obs)

    if obs.value is None:
        return ValidationResult(False, None, "ok observation missing value")

    if value_min is not None and obs.value < value_min - BOUND_EPS:
        return ValidationResult(
            False, None, f"value {obs.value} below min {value_min} (rejected, not clamped)"
        )
    if value_max is not None and obs.value > value_max + BOUND_EPS:
        return ValidationResult(
            False, None, f"value {obs.value} above max {value_max} (rejected, not clamped)"
        )

    if max_staleness_days is not None and as_of is not None:
        from datetime import date

        as_of_d = date.fromisoformat(str(as_of)[:10])
        obs_d = date.fromisoformat(obs.observed_at[:10])
        age = (as_of_d - obs_d).days
        if age > max_staleness_days:
            stale = Observation(
                signal_key=obs.signal_key,
                market_id=obs.market_id,
                observed_at=obs.observed_at,
                effective_date=obs.effective_date,
                value=obs.value,
                horizon_days=obs.horizon_days,
                confidence=obs.confidence,
                quality="stale",
                provenance_url=obs.provenance_url,
                run_id=obs.run_id,
                meta={**obs.meta, "staleness_days": age},
            )
            return ValidationResult(True, stale, f"stale by {age}d")

    return ValidationResult(True, obs)
