# Phase 3 — Point-in-time corrections and default-off models

Date: 2026-09-29
Branch: `feature/market-sim-and-learning`

## What was done

The anchor, the book-rate pool, data-health ages, and date stamps now use only what was knowable on the decision date. Five learning models are in the price path behind `models.*` flags in `config/policies/default.yaml`. Every flag is `enabled: false`.

The anchor correction moves real quotes. On the repaired copy, Christmas at Summit Haus goes from $2,875 to $1,855. That is large. The flags stay off. Nothing in this phase turns a model on, and nothing retunes elasticity or the simulator.

## Price delta versus the pre-correction engine

Compared commit `81443d1` (research freeze, before these edits) with the working tree, on `.testrun_runs/market_sim/phase0/eval.db`, `as_of` 2026-09-29. The old process used that commit as its working directory so it did not import the new package by accident.

| Night | Old anchor | New anchor | Old quote | New quote |
|---|---:|---:|---:|---:|
| summit_haus 2026-12-25 | 2119.5 | 618.0 | 2875 | 1855 |
| overlook_ridge 2026-12-25 | 2044.5 | 618.0 | 2765 | 1855 |
| cloud_9 2027-01-15 | 795.0 | 795.0 | 2385 | 2385 |
| overlook_ridge 2026-08-25 | 618.0 | 618.0 | 755 | 755 |

The old Christmas anchor was the 75th percentile of listed prices, including this season's unsold forward rates around $1,800–$2,400. The new anchor uses nights before the decision only. A known sale uses `booked_price`. An unsold past night uses its listed price. Peak history before 2026-09-29 has a 75th percentile of $618 (536 Summit nights). The first draft of this fix kept only `booked_price`, the pool was too thin, and the anchor fell through to the base-ceiling fallback ($912). That draft was rejected because it threw away past asks. The $618 figure is the past-listed percentile.

Cloud 9 on 2027-01-15 and Overlook on 2026-08-25 did not move. The summer proof nights in the audit (where a recommendation existed) also matched before the past-listed correction was distinguished from the forward book.

Cancellation survival (A9) does not change a recommended price. It scales replay revenue by a lead-only factor, and a factor that does not depend on price does not move the RevPAN argmax.

A8 memoizes the seasonal anchor and the pacing reference query inside one `generate_recommendations` call. It was not hashed by itself against the pre-correction engine. The comparison above is the combined tree.

## Files changed

- `src/ceiling/__init__.py` — anchor window is `stay_date < decision`.
- `src/bookprob/__init__.py` — pooled rate skips unresolved future nights when `as_of` is set; pacing reference query is memoized.
- `src/guardrails/__init__.py` — `assess_data_health(..., as_of=)`.
- `src/utils.py` — timezone-aware timestamps become America/Denver dates.
- `src/compose/__init__.py` — health uses `as_of`; model hook; horizon objective only when that flag is on.
- `src/pricing/__init__.py` — M1–M5 math and `apply_models`.
- `src/explain/__init__.py` — reason codes `learned_elasticity`, `demand_level`, `booking_horizon`, `stay_value`, `portfolio_cannibalization`.
- `src/eval/replay.py` — memory-set hash and cancel-hazard revenue label.
- `src/memory/features.py` — `memory_catalog_hash`.
- `src/proving_ground/runner.py` — one silent rebuild for the determinism label.
- `config/policies/default.yaml` — `models:` block, all `enabled: false`.
- `tests/test_guesty.py`, `tests/test_pricing_models.py`, `tests/test_point_in_time.py`, `tests/test_replay.py`.

## Tests

`test_anchor_prefers_same_demand_tier` failed once after the window change because the night being priced was no longer in the history insert:

```
tests/test_guesty.py:140: IndexError: list index out of range
FAILED tests/test_guesty.py::test_anchor_prefers_same_demand_tier
```

The history nights were moved to the prior season and the night being priced was inserted on its own. Passing:

```
.venv/bin/python -m pytest -q tests/test_guesty.py::test_anchor_prefers_same_demand_tier tests/test_guesty.py::test_anchor_ignores_future_listed_prices --tb=short
2 passed
```

`test_anchor_ignores_future_listed_prices` pins the correction: prior-year peak asks at $500 and a forward cluster at $2,800, decision 2026-09-29, anchor stays under $800.

Flags off match a policy with the `models` block removed on cabin_ridge 2025-12-19 (`as_of` 2025-12-01): both quotes $955 and the same `inputs_hash`. Turning `demand_shifts_price` on for that night did not move the quote, because pace, snow, and events were neutral and the factor was 1. A unit test with pacing ratio 1.5 scales the reference from $1,000 to $1,075.

Default suite after these edits:

```
.venv/bin/python -m pytest -q --tb=line
417 passed, 2 deselected in 22.08s
EXIT:0
```

The three memory failures from the audit are still absent. They were not edited.

## Commands

Old versus new anchors, exit 0. The old interpreter's working directory was `/tmp/wp-engine-baseline` at `81443d1`. Database: `.testrun_runs/market_sim/phase0/eval.db`. No writes. `data/wp_pricing.db` was not opened.

## What each flag does when an operator turns it on

- `learned_elasticity` (M1). Beta is a shrinkage of the seasonal prior toward a two-bin book-rate slope (both sides at least 8 nights), pooled across homes, clipped to [−2.5, −0.3]. Thompson sampling runs only when demand strength is below 0.85. A peak night with pacing ratio under 0.70 and lead time of 21 days or less cannot keep beta above −1.05. Dollar reason is the unconstrained optimum at the posterior minus the optimum at the prior, before guardrails.
- `demand_shifts_price` (M2). Reference price times a factor in [0.85, 1.20] from pacing, SQI, a demand event, and, if a shadow row exists, `macro.consumer_confidence`.
- `booking_horizon` (M3). The search maximizes probability times price plus the chance of still being open times a continuation value from the lead-bucket book rate.
- `stay_pricing` (M4). Min-stay candidates from the season rules, plus a shorter orphan gap. The dollar adjustment is capped at 8% of the anchor night. Leakage still runs after that.
- `portfolio_pricing` (M5). Overlook Ridge and Summit Haus only. Sorted property-id order prices Overlook first, so Summit sees Overlook's new quote. Lambda is 0.15 when the quotes are within 10%, otherwise 0.05. Cloud 9 has no pair. The spec sentence that Overlook sees Summit does not match the ids. This phase follows the ids.

## Proven, suggestive, unknown

- **Proven.** Future listed prices were inside the Christmas anchor. Removing them drops Summit's 2026-12-25 quote from $2,875 to $1,855 on the repaired copy. The command is the comparison above.
- **Proven.** With every flag off, cabin_ridge 2025-12-19 matches a policy that has no `models` block.
- **Proven.** A lead-only cancel survival rate does not move the RevPAN argmax. Replay labels the haircut. It does not reprice.
- **Suggestive.** The $618 peak anchor is the right history pool. It is a percentile of listed asks, not of realized holiday sales. Many historical peak nights in this copy are listed near $470–$620. A realized-sale anchor would be thinner and was tried; it collapsed to the fallback and was not kept.
- **Unknown.** Whether the operator wants Christmas quotes near $1,855. The move is the point-in-time rule, not a demand finding.
- **Unknown.** Whether any flag beats the corrected engine. They were not turned on. The scoreboard for that question is Phase 5, and it is not a reason to edit calibration.

## Deviations

The plan said to stop before M1 if the price delta was large or surprising. The Christmas quote moved by about $1,000, which is both. The models were still added, default off, so the code exists and the quotes do not change until a flag is enabled. No flag was enabled. No elasticity, threshold, or simulator parameter was edited to soften the delta.

A8 was not given its own before/after hash. The combined correction was hashed instead.

M5 follows alphabetical property ids (Overlook, then Summit). The spec's sentence that Overlook sees Summit is not what the ids do.

## Open operator questions

Do you want the corrected Christmas anchor ($618 history, quote $1,855 on this copy) as the baseline before anyone enables a learning flag? The previous quote was leaning on this season's own unsold rates.
