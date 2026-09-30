# Market simulator and learning model

Date: 2026-09-29
Branch: `feature/market-sim-and-learning`

## For the owner

The pricing engine, as it ran in the 1,800-job simulator, makes less money than charging a flat seasonal rate. That is true on the ordinary winter and on every stress case, including the four winters that were never used to adjust the simulator. The gap on an ordinary winter is about $26,000 over the season, and the uncertainty band sits entirely below zero.

A separate five-seed run, after the engine stopped looking at this year's unsold rates when it sets a ceiling, loses by more: about $86,000 versus the same flat rate. Learning rules were tried on that corrected engine. Some of them earn more than the corrected engine and still earn less than the flat rate. None of them is turned on.

Christmas at Summit Haus on the repaired copy moves from $2,875 to $1,855 if you accept the rule that a future listed price is not history. That is a real quote change. It is not a demand discovery. Leave the learning switches off until you have looked at that Christmas number.

Guesty was not written. Applied rate changes in the checks stayed at zero.

## What was built

A shopper market in `proving_ground_exam/market/`: arrivals, a choice model with an outside option, cancellations, four competitor types, and a noisy scrape. It writes the same tables a Guesty sync writes. The driver is `proving-ground market`.

Five learning switches in `config/policies/default.yaml`, all `enabled: false`:

- `learned_elasticity`
- `demand_shifts_price`
- `booking_horizon`
- `stay_pricing`
- `portfolio_pricing`

Guest storage adds city, state, country, and party counts. Names, emails, and phones are not stored. Five consumer indicators register at shadow, not active.

Telluride is a second resort file and a calibration copy. It is not a 16th scenario and it does not change the Winter Park loader.

## Tests

Default suite after the code changes: 417 passed, 2 deselected, exit 0. A later owner-template test passed with the pricing tests (15 passed). The market-sim file passed 26 tests with 1 slow test deselected. The three memory failures from the audit are not on this tree and were not edited.

## Scoreboard

Pre-correction engine, 30 seeds, 15 scenarios. CSV: `docs/reports/market_sim/phase2_scoreboard.csv`. Manifest hash `16ac071dd4aded33989f25aa9db25743d1e626e689dbf329a781afe34647c4b0`.

Engine minus flat is negative on all 15 scenarios. The ordinary-winter interval is −$27,956 to −$23,138. Held out:

| Scenario | Mean engine − flat | 95% interval |
|---|---:|---|
| den_capacity_cut | −26303 | −28791 to −23737 |
| holiday_shift | −26044 | −27989 to −24007 |
| pandemic_collapse | −2063 | −3950 to −282 |
| regime_change | −25821 | −28255 to −23372 |

The engine also loses to following the comp median, on all 15. It beats the public-tool emulator on 14 and loses on `price_war`.

Corrected engine, five seeds, `normal` only (Phase 5): engine minus flat about −$85,926, interval −$94,220 to −$79,330. Learned elasticity and a demand-plus-stay combination each recover about $53,000 of that and still lose to flat by about $33,000. Those flags were not run on stress or held-out winters. `demand_shifts_price` hits the sanity floor thousands of times.

## Simulator checks

Flat `normal`, five seeds: length of stay, inquiry ratio, and both occupancy bands pass. Share of bookings inside 21 days misses the 0.40 floor on four of five seeds. That was not "fixed" by adding shoppers. Mont Luxe's 47 stays are too few to be a winter census.

Family price sensitivity barely moves simulated revenue. How many shoppers arrive moves it a lot. The published parameters were not changed after that.

The one-hour budget for 1,800 full seasons was missed. The grid took about 3.7 hours. Indexes sped up the comp lookup. Repricing only some nights was identical when tested and did not skip nights, because a booking changes the whole book. The season was not shortened and the engine was not replaced.

## Proven, suggestive, unknown

- **Proven.** The pre-correction engine loses to flat and to the comp follower on every scenario in the 1,800-job file, held-out included.
- **Proven.** Future listed prices were in the Christmas anchor. Removing them changes Summit Haus on 2026-12-25 from $2,875 to $1,855 on the repaired copy.
- **Proven.** With the learning flags off, a sample night matches a policy that has no `models` block.
- **Suggestive.** Learned elasticity raises corrected-engine revenue on five ordinary seeds and still loses to flat.
- **Unknown.** Whether you want the $1,855 Christmas quote. Whether any flag survives a stress set and a replay calibration check. Winter flight counts and a Telluride snow station were not collected.

## Recommended defaults

Leave every `models` flag at `enabled: false`.

Do not treat the flat rate as the new policy either. The flat rate won a simulator whose shoppers were not fit to your 47 stays. It is evidence that the current optimum (charge near the ceiling, because peak elasticity is −0.65) is leaving money behind in this world. It is not an instruction to publish the flat rate.

## Remaining risks

The 1,800-job board and the five-seed board are different engines. Do not average them. The big board was started before the anchor correction. The small board uses the correction and is only five seeds of one scenario.

Lead time inside 21 days is too low in the flat world. Long-lead shoppers book first.

`supply_extra` is one extra listing, not a 15% larger market. The outside option wins often, including when a home is free.

Guardrail counts in the big board include peak-blackout holds. They are not 2,000 broken price caps.

No Telluride scrape, no SNOTEL station id, no invented Intrawest feed.

## Commands

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
PYTHONPATH=. .venv/bin/python -m src.cli.main proving-ground market \
  --scenario normal --seeds 1 --workers 1 --policy flat \
  --output-dir .testrun_runs/market_sim/runs
```

The 1,800-job command, which took about 3.7 hours here:

```bash
PYTHONPATH=. .venv/bin/python -m src.cli.main proving-ground market \
  --scenario all --seeds 30 --workers 7 --policy engine \
  --output-dir .testrun_runs/market_sim/runs
```

That CLI call runs one policy. The scoreboard in this folder ran engine, flat, comp_median, and tool. Copies of the operator database stay under `.testrun_runs/`. Do not point `--apply` at `data/wp_pricing.db`.

## Reports

- `docs/reports/market_sim/phase0_BASELINE.md`
- `docs/reports/market_sim/phase1_RESEARCH.md`
- `docs/reports/market_sim/phase2_SIMULATOR.md`
- `docs/reports/market_sim/phase3_MODELS.md`
- `docs/reports/market_sim/phase4_CONSUMER.md`
- `docs/reports/market_sim/phase5_LADDER.md`
- `docs/reports/market_sim/phase6_PORTABILITY.md`
