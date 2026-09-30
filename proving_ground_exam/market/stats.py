"""Paired differences and bootstrap intervals. Not a family-wise correction."""

from __future__ import annotations

import numpy as np

from proving_ground_exam.market.rngutil import generator


def paired_diff(left: list[float], right: list[float]) -> list[float]:
    if len(left) != len(right) or not left:
        raise ValueError("paired samples must be the same non-empty length")
    return [a - b for a, b in zip(left, right, strict=True)]


def bootstrap_mean_ci(
    values: list[float],
    *,
    scenario: str,
    seed: int,
    draws: int = 2000,
) -> dict[str, float]:
    rng = generator(scenario, seed, "bootstrap")
    sample = np.asarray(values, dtype=float)
    if len(sample) == 0:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0, "draws": 0}
    picks = rng.integers(0, len(sample), size=(draws, len(sample)))
    means = sample[picks].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        "mean": float(sample.mean()),
        "lo": float(lo),
        "hi": float(hi),
        "draws": draws,
    }


MULTIPLE_COMPARISON_NOTE = (
    "Intervals are marginal bootstrap intervals on paired seed differences. "
    "They are not adjusted for the number of flags or scenarios compared."
)
