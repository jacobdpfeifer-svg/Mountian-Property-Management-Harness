# Phase 2 — Market simulator

Date: 2026-09-29
Branch: `feature/market-sim-and-learning`

## What was done

The examiner package `proving_ground_exam/market/` draws shoppers, runs a mixed logit with an outside option, writes the same reservation, inventory, comp, and signal tables the Guesty sync writes, and scores realized revenue. `src/proving_ground/market_loop.py` steps the three homes, snapshots pacing, calls `generate_recommendations`, and posts listed prices on nights that are still available. The world does not import `src.bookprob`, `src.compose`, `src.conditions`, or `src.elasticity`. W1 is still the proving-ground level runner.

Fifteen scenarios are in `proving_ground_exam/scenarios/`. Held out, and not used to change a parameter: `holiday_shift`, `den_capacity_cut`, `regime_change`, `pandemic_collapse`. Calibration is `proving_ground_exam/market/calibration.yaml`, transcribed from `docs/research/SIM_PARAMETERS.md`. A test fails if a value has no source. The file was not edited to improve an engine score.

The full scoreboard is 15 scenarios × 30 seeds × 4 policies (engine, flat, comp median, tool), 1,800 jobs. It finished with exit 0. Manifest hash `16ac071dd4aded33989f25aa9db25743d1e626e689dbf329a781afe34647c4b0`. The CSV is `docs/reports/market_sim/phase2_scoreboard.csv`. Elapsed wall time was about 3.7 hours, not under one hour.

## Files

- `proving_ground_exam/market/` — shoppers, choice, funnel, competitors, scrape, world, scoring, stats, calibration.
- `proving_ground_exam/scenarios/` — the 15 YAML files. Telluride is not in this folder.
- `src/proving_ground/market_loop.py` — driver, validation report, scoreboard writer.
- `src/cli/main.py` — `proving-ground market`.
- `src/db/schema.sql` — indexes `idx_comp_snap_stay_comp` and `idx_pacing_days_asof`.
- `tests/proving_ground/test_market_sim.py`.

## Tests

Default market tests (the full-season determinism test is `@pytest.mark.slow` and was deselected):

```
.venv/bin/python -m pytest -q tests/proving_ground/test_market_sim.py --tb=line
26 passed, 1 deselected
```

That run was after the Telluride file test was added. The earlier market file, before that test, passed the booking, hash, outage, column-contract, and incremental checks on the first real run. There is no captured failing excerpt for those: they passed when first executed. The decision-step failure that did fail, then pass, is in Phase 0.

What the tests pin: a short season writes a confirmed reservation and blocks those nights; an `inq-` row does not; `rate_changes` applied stays 0; the same seed hashes equal and a different seed does not; a scrape outage writes `failed` and a null price; world insert columns are a subset of the sync writers; the isolation script still passes; incremental repricing matches every `Recommendation` field on three property-nights.

## Validation

Five full-season flat seeds on `normal`, after the outside option was a real alternative. JSON: `.testrun_runs/market_sim/validation/flat_normal.json`. Ranges are in `calibration.yaml` and were not edited after this run.

| Seed | Revenue | Confirmed | LOS | Lead ≤21 | Inquiry/confirmed | Peak occ. | Early occ. | Lead check |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 270400 | 69 | 4.77 | 0.391 | 0.90 | 0.626 | 0.477 | miss |
| 2 | 268100 | 73 | 4.47 | 0.397 | 0.68 | 0.623 | 0.470 | miss |
| 3 | 268050 | 71 | 4.62 | 0.282 | 0.87 | 0.601 | 0.500 | miss |
| 4 | 278600 | 75 | 4.51 | 0.427 | 1.00 | 0.654 | 0.485 | pass |
| 5 | 250750 | 68 | 4.50 | 0.309 | 0.84 | 0.570 | 0.462 | miss |

LOS, inquiry ratio, peak occupancy, and early occupancy pass on all five. Lead time within 21 days misses the 0.40 floor on four of five. The first-party book is 28/47 = 0.60 inside 21 days, but that is 47 stays, not a winter census. The miss is who gets the night: longer-lead shoppers book first. Arrival mean was not raised to hide it.

Mont Luxe's 47 confirmed stays are too thin to be the winter distribution. The check above is the simulated market, not a claim that the three homes book like the 47.

## Sensitivity

World revenue only, flat policy, `normal`, 10 seeds. The family peak-ski price coefficient and the arrival mean were varied on a copy of the calibration in memory. `calibration.yaml` was not edited. Means:

| Arrival mean | Family peak coef −0.7 | −1.1 | −1.8 |
|---:|---:|---:|---:|
| 2.0 | 214785 | 214655 | 214615 |
| 3.2 | 265665 | 264570 | 263795 |
| 5.0 | 305005 | 305340 | 305505 |

The price coefficient barely moves revenue. Arrival mean moves it a lot. The point values in the YAML stay the official ones. JSON: `.testrun_runs/market_sim/sweep_summary.json`.

## Speed

The hour budget is 15 × 30 × 180 days × 3 homes. It was missed. A comp lookup was scanning scrape history through `idx_comp_snap_status` (about 6.4 seconds for 295 nights around day 52, on the order of 38k rows). `idx_comp_snap_stay_comp` and `idx_pacing_days_asof` brought that pass to about 1.2 seconds with the same recommendation hash. Fresh indexed engine seasons are still on the order of a few minutes, not a second.

Incremental repricing was proved identical on two full-horizon decision days (`test_incremental_reprice_matches_full_recommendation_fields`). It does not skip nights in practice: a booking or a comp scrape changes the property digest, and the anchor and the pacing ratio read the whole book. `--incremental` stays off for scoreboards. The season was not trimmed and the engine was not replaced with a surrogate.

## Behavior worth not misreading

The outside option is an alternative with utility 0, not a leftover for when every home is full. On flat seed 1 a large share of shoppers choose it.

`supply_extra` adds one listing, `comp_supply`, at 97% of yesterday's median. It is not a 15% increase in listing count. The scenario name can say supply; the mechanism is one extra comp.

The hindsight revenue charges willingness to pay and ignores competitors. The optimality gap is brute force versus that greedy rule on the first six eligible shoppers only. A gap of zero on a short smoke run is not a season-long proof.

Seeds mix the scenario id and the seed through SHA-256 into PCG64. They do not use Python's salted hash.

## Proven, suggestive, unknown

- **Proven.** Same seed, same hash. A booked night is blocked. An inquiry is not. A scrape outage hides prices. Applied Guesty writes in the short test are 0.
- **Proven.** Flat `normal` misses the lead-time floor on 4 of 5 seeds and passes LOS, inquiry ratio, and both occupancy checks. Parameters were not changed afterward.
- **Suggestive.** Family price sensitivity in the published range does not move world revenue; arrival volume does.
- **Proven.** On this scoreboard the engine loses to flat on every scenario, including the four held-out ones, and the 95% interval excludes zero each time. It also loses to the comp-median follower on every scenario. It beats the tool emulator on 14 scenarios and loses on `price_war`. The workers that produced the CSV imported the engine before the Phase 3 anchor correction, so these dollars are not the corrected Christmas anchor.

## Scoreboard

Engine minus flat, 30 paired seeds, bootstrap 95% interval. Negative means the engine made less revenue. Held-out rows are marked. Intervals are not adjusted for 15 scenarios.

| Scenario | Held out | Mean difference | 95% interval |
|---|---|---:|---|
| normal | no | −25534 | −27956 to −23138 |
| drought | no | −24886 | −26979 to −22687 |
| early_closure | no | −24588 | −27567 to −21645 |
| i70_closure | no | −25356 | −27628 to −23235 |
| late_opening | no | −24498 | −26940 to −22106 |
| price_war | no | −26414 | −29174 to −23652 |
| recession | no | −22624 | −25315 to −20042 |
| record_snow | no | −26353 | −28550 to −24065 |
| scrape_outage | no | −24614 | −27028 to −22326 |
| stale_pms | no | −25756 | −28145 to −23280 |
| supply_surge | no | −24856 | −27440 to −22163 |
| den_capacity_cut | yes | −26303 | −28791 to −23737 |
| holiday_shift | yes | −26044 | −27989 to −24007 |
| pandemic_collapse | yes | −2063 | −3950 to −282 |
| regime_change | yes | −25821 | −28255 to −23372 |

Mean revenue across scenario-means: flat $244,253, comp median $241,373, engine $220,539, tool emulator $196,301.

Engine minus the comp follower is negative on all 15 scenarios, intervals excluding zero. On `scrape_outage` the comp follower matches flat, which is what a missing scrape should do. Engine minus the tool emulator is positive on 14 scenarios. On `price_war` the engine loses to the tool (mean −$12,742, interval −$16,082 to −$9,449).

Mean engine guardrail-trigger counts are about 1,900 to 2,600 per season. That column counts every non-empty `guardrail_action`. These workers did not split the count by action. Later runs show `peak_blackout` is most of it.

## Deviations

The one-hour budget was missed after the index and after the incremental proof. The full grid was still started. Horizon trimming and a surrogate engine were not used.

The scoreboard process imported the engine before the Phase 3 anchor correction. Its prices are the pre-correction engine plus the new indexes. A worker that died and was replaced would import the corrected anchor. If the final CSV mixes the two, this report will say so rather than average them.

## Open operator questions

The lead-time miss is accepted as a limit of first-come booking, not fixed by raising arrivals. Say if you want that floor restated for a winter-only book. Do not expect the 47-stay history to decide it.
