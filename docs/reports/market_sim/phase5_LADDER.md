# Phase 5 — Evaluation ladder

Date: 2026-09-29
Branch: `feature/market-sim-and-learning`

## What was done

Flags stay off in `config/policies/default.yaml`. The ladder turns them on only inside a copied policy dict. It does not edit calibration, elasticity constants, or scenario thresholds.

The comparison is five seeds of `normal`, paired against the corrected engine (the anchor fix from Phase 3 is in this process). Flat prices on the same five seeds come from the validation run. Stress scenarios and the four held-out scenarios are not in this table yet. The 30-seed scoreboard is the Phase 2 job, and that job is the pre-correction engine.

A lead-only cancel model does not change prices, so it is not a rung.

## Paired revenue on `normal`, five seeds

Flat: 270400, 268100, 268050, 278600, 250750.

Engine (flags off): 184215, 193285, 182025, 177365, 169380.

Engine minus flat, mean −$85,926. Bootstrap 95% interval on the five paired differences: −$94,220 to −$79,330. The interval excludes zero. The corrected engine loses to a flat seasonal price on this scenario. Intervals are not adjusted for how many comparisons get made. Five seeds are a thin sample. This is not the 30-seed board.

Each flag alone, minus the engine, five paired seeds. Bootstrap 95% intervals. Not adjusted for five comparisons.

| Flag | Mean revenue difference | 95% interval | Interval excludes zero | Safety notes across five seeds |
|---|---:|---|---|---|
| learned_elasticity | +52512 | +46888 to +57949 | yes | sanity_floor 845, move clamps 2,281, peak_blackout 10,954 |
| demand_shifts_price | +29426 | +20765 to +38087 | yes | sanity_floor 6,573 |
| booking_horizon | +17792 | +8731 to +23715 | yes | no sanity_floor; move clamps 744; peak_blackout 11,232 |
| stay_pricing | −466 | −4382 to +2890 | no | no revenue gain |
| portfolio_pricing | +6243 | −1567 to +14167 | no | interval includes zero |
| m1_m2 | +32977 | +23810 to +42680 | yes | sanity_floor 6,669 |
| m2_m4 | +52599 | +43621 to +61597 | yes | sanity_floor 700; still about $33k behind flat |
| m1_m2_m5 | +30122 | +19575 to +40669 | yes | sanity_floor 11,304 |

Every row is still behind the flat policy. The smallest gap to flat is about $33k (`learned_elasticity` and `m2_m4`), and those intervals versus flat exclude zero on the losing side. Replay Brier was not re-measured with any flag on.

`demand_shifts_price` hitting the sanity floor thousands of times is a reason not to enable it. The shift is large enough that the safety clamp is doing the pricing.

## Win rule

No flag is recommended on. Several settings raise `normal` revenue against the corrected engine, and some of those intervals exclude zero. Every one of them still loses to the flat policy. None was run on a stress scenario or a held-out scenario. None has a zero count of sanity-floor or move-cap actions. `stay_pricing` alone and `portfolio_pricing` alone do not clear the revenue bar. The YAML defaults stay off.

Held-out scenarios were not opened for the flags. The non-held-out bar had already failed, and the Phase 2 engine grid was still using the machine. Scoring held-out after a failed bar would not have been a reason to enable a flag.

## Tests

Owner templates were missing for the new reason codes. The first flag run died with:

```
MissingOwnerTemplateError: No owner-facing template for reason code 'learned_elasticity'
```

Templates were added in `src/explain/present.py`. Then:

```
.venv/bin/python -m pytest -q tests/test_owner_explain.py::test_every_compose_reason_code_has_an_owner_template tests/test_pricing_models.py --tb=line
15 passed
```

## Commands

The ladder is `.testrun_runs/market_sim/run_phase5.py`. It is gitignored. Rows: `.testrun_runs/market_sim/phase5/rows.jsonl`. The first attempt exited 1 (missing owner template). The resumed process exited 0.

## Proven, suggestive, unknown

- **Proven.** On these five seeds the corrected engine’s realized revenue is below the flat policy, and the interval excludes zero.
- **Suggestive.** On these five seeds, learned elasticity and the demand-plus-stay combination raise revenue versus the corrected engine, and the intervals exclude zero. Both still lose to flat. `demand_shifts_price` combined with learned elasticity hits the sanity floor thousands of times.
- **Unknown.** Stress and held-out behavior. Replay Brier with the flag on. Whether the operator accepts the lower Christmas anchor that this engine is using.

## Deviations

Five seeds, not thirty. Held-out not scored yet. The Phase 2 grid is a different engine (pre-correction) and is not mixed into these pairs.

## Open operator questions

The corrected engine loses about $86k of simulated revenue to a flat rate on `normal` in this five-seed pair. Learned elasticity closes a large part of that and still trails flat. Do you want that flag evaluated on the stress set before anyone considers enabling it? This report does not enable it.
