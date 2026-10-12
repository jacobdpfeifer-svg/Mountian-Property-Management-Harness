# Corrected market board

Date: 2026-10-01
Commit: `79dae5d063077b2002a927095a50e0753c8ef3ec`
Branch at run time: clean `feature/ops-layer` (learning flags off)

## Proven facts about this run

The board is 15 scenarios × seeds 1–30 × four policies (`engine`, `flat`, `comp_median`, `tool`) = 1,800 jobs. Every cell is present once. Within each scenario and policy the 30 content hashes differ. Re-running `normal` engine seeds 1 and 2 reproduced the scoreboard hashes; the two seeds do not share a hash.

| Item | Value |
|---|---|
| Command | `PYTHONPATH=. .venv/bin/python -m src.cli.main proving-ground market --scenario all --seeds 30 --workers 7 --grid --retain-dbs normal,price_war,holiday_shift --output-dir ~/wp-price-runs/market_sim/baseline_79dae5d` |
| Output | `~/wp-price-runs/market_sim/baseline_79dae5d` |
| Manifest hash | `9d9257e12ba5e3ce0c8f600a7a08c260f94231d78cdf86bbdded0bc0d218aa1b` |
| Calibration SHA-256 | `ea4add7941aa991d6fc4513dcab9d3c9e91b4e38978e4fe7fa01bbe6cb1287ea` |
| Policy SHA-256 | `2d3bbc93c2345c1723f21996522bce60c34456453b24ae28713d0f91f32200eb` |
| `models_enabled` | none |
| Python | 3.12.14 |
| Workers | 7 |
| Elapsed | 11,306.8 seconds (about 3.14 hours) |
| Exit | scoreboard written, `completed_jobs` 1800, no `failure.json` |
| Audit | `corrected_audit.json` beside the scoreboard; `gates.complete` true |

Held-out scenarios are in the scoreboard and in the paired tables: `den_capacity_cut`, `holiday_shift`, `pandemic_collapse`, `regime_change`.

`rate_changes.result = 'applied'` is 0 on all 360 retained databases (`normal`, `price_war`, `holiday_shift`, four policies, 30 seeds). The market driver does not call the Guesty writer. Retaining every scenario's database needed about 84 GB plus headroom; this volume had about 65–70 GB free, so the other twelve scenarios' databases were discarded after scoring.

Seeds 1–5 of `normal` match the Phase 5 corrected pair exactly. Flat simulated revenue: 270400, 268100, 268050, 278600, 250750. Engine: 184215, 193285, 182025, 177365, 169380. That five-seed engine-minus-flat mean is −$85,926, interval −$94,220 to −$79,330. The 30-seed `normal` mean is −$93,012, interval −$98,760 to −$87,708. Same corrected engine, larger sample. The interval still sits entirely below zero. These two figures are the corrected comparison. They are not averaged with anything else.

The Phase 2 file `docs/reports/market_sim/phase2_scoreboard.csv` is historical pre-correction context. Its ordinary-winter engine-minus-flat mean was about −$25,534. That file is a different engine.

## Paired simulated revenue

Engine minus the other policy, same scenario and seed. Bootstrap intervals are marginal 95% intervals on the paired seed differences. They are not adjusted for 15 scenarios. A negative mean means the engine's simulated revenue was lower. No policy is named a production winner from the unadjusted multi-scenario average.

### Engine minus flat

| Scenario | Held out | Mean | Median | Min | Max | Seeds ≥ 0 | 95% interval |
|---|---|---:|---:|---:|---:|---:|---|
| normal | no | −93012 | −90212 | −130665 | −70790 | 0 | −98760 to −87708 |
| drought | no | −91508 | −92810 | −131835 | −54685 | 0 | −96983 to −86370 |
| early_closure | no | −89379 | −88845 | −130030 | −49090 | 0 | −95622 to −83639 |
| i70_closure | no | −89236 | −91185 | −125750 | −38806 | 0 | −95052 to −83489 |
| late_opening | no | −92282 | −95730 | −112445 | −64370 | 0 | −96258 to −88063 |
| price_war | no | −91144 | −87462 | −121510 | −55285 | 0 | −97079 to −84933 |
| recession | no | −85065 | −85235 | −126400 | −50785 | 0 | −91087 to −79220 |
| record_snow | no | −88024 | −91180 | −121635 | −54335 | 0 | −93598 to −82117 |
| scrape_outage | no | −91443 | −89590 | −125845 | −64775 | 0 | −97371 to −85503 |
| stale_pms | no | −91658 | −91460 | −113640 | −65526 | 0 | −96090 to −87211 |
| supply_surge | no | −89749 | −86445 | −131965 | −64655 | 0 | −94854 to −84853 |
| den_capacity_cut | yes | −92829 | −93190 | −128342 | −54940 | 0 | −98707 to −87259 |
| holiday_shift | yes | −94861 | −93990 | −134330 | −50480 | 0 | −101658 to −88106 |
| pandemic_collapse | yes | −15114 | −14378 | −36115 | 550 | 1 | −18012 to −12217 |
| regime_change | yes | −89211 | −88672 | −114560 | −40578 | 0 | −93928 to −83911 |

`gates.normal_beats_flat` is false. `gates.scenarios_beating_flat` is 0.

### Engine minus comp median

Negative on all 15 scenarios, and every scenario has 0 seeds at or above zero. On `normal` the mean is −$89,253 (median −$88,056, min −$116,138, max −$59,699, interval −$94,646 to −$83,932). On `scrape_outage` the comp-median gap equals the flat gap (−$91,443).

### Engine minus tool

The mean is negative on all 15 scenarios. On `normal` it is −$39,021 (1 of 30 seeds at or above zero, interval −$44,388 to −$33,514). The largest mean gap is `price_war`, −$77,471.

## Normal decomposition

From the 30 retained `normal` engine databases and the 30 retained `normal` flat databases. Figures are means across seeds. Dollars are simulated revenue. Scoreboard means match the database sums: engine $165,738.38, flat $258,750.00.

Mean occupancy is 0.463 for the engine and 0.583 for flat. Mean listed price is $781 versus $823. Mean booked price is $662 versus $822.

| Season | Engine simulated revenue | Flat | Difference | Engine occupancy | Flat occupancy | Engine booked price | Flat booked price |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 32290 | 41900 | −9610 | 0.530 | 0.423 | 462 | 750 |
| peak_ski | 107739 | 174990 | −67251 | 0.346 | 0.606 | 969 | 900 |
| shoulder_spring | 25709 | 41860 | −16151 | 0.790 | 0.740 | 374 | 650 |

| Property | Engine | Flat | Difference | Engine occupancy | Flat occupancy | Engine booked price | Flat booked price |
|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | 34191 | 86625 | −52434 | 0.317 | 0.584 | 598 | 824 |
| overlook_ridge | 52436 | 86632 | −34196 | 0.434 | 0.584 | 671 | 824 |
| summit_haus | 79111 | 85493 | −6382 | 0.637 | 0.580 | 690 | 819 |

Confirmed-stay simulated revenue by lead bucket (`market_loop` edges 8, 15, 22, 61, 121). The longest confirmed lead in these 60 databases is 120 days, so the 121+ bucket is empty.

| Lead days | Engine | Flat | Difference | Engine nights | Flat nights |
|---|---:|---:|---:|---:|---:|
| 0–7 | 16526 | 24275 | −7750 | 28.1 | 29.9 |
| 8–14 | 16936 | 29122 | −12186 | 28.5 | 36.1 |
| 15–21 | 21351 | 30530 | −9179 | 34.4 | 37.0 |
| 22–60 | 71424 | 116360 | −44936 | 92.9 | 136.6 |
| 61–120 | 39503 | 58463 | −18960 | 65.9 | 75.0 |

Engine recommendation rows per seed, averaged: unmodified 34,800; `peak_blackout` 2,308; `sanity_floor` 182; `clamped_increase` 109; `clamped_decrease` 4.

On the recommendation in force when an engine night booked, the mean booked nights are: no guardrail action 228.9 nights ($149,526); `peak_blackout` 14.2 nights ($13,649); `sanity_floor` 6.4 nights ($2,380); move clamps under one night combined.

## Diagnosis

The corrected engine still loses on `normal`. Learning flags stay off. No constant was changed after this board.

The gap is a combination, and peak occupancy is the large piece. Peak ski is −$67,251 of the −$93,012. At peak the engine's booked price is higher than flat ($969 versus $900) and its occupancy is much lower (0.35 versus 0.61). Early winter and shoulder spring are the price-gap piece: occupancy is higher than flat, and the booked price is much lower ($462 versus $750 early, $374 versus $650 in shoulder), together about −$25,760. The 22–60 day lead bucket holds −$44,936 of the stay-level gap, in line with fewer mid-lead nights sold. Cloud 9 is the largest property gap (−$52,434), with occupancy 0.32 versus 0.58.

`peak_blackout` is a small booked-night share (about 14 nights and $13,649 of engine simulated revenue). It does not account for the peak occupancy hole. Most booked engine nights have an empty guardrail action.

## Simulator-dependent evidence

These dollars are scores inside the synthetic shopper world in `proving_ground_exam/market/`. Shoppers, the outside option, competitor rules, and the published calibration decide who books. The flat seasonal price is a benchmark inside that world. Family price sensitivity was already known to move this world less than arrival volume, and the calibration file was not edited for this run. Intervals are not a causal estimate for Winter Park and are not adjusted for the number of scenarios.

## Unknown real-world performance

Nothing here is revenue collected on a live listing. Whether the lower Christmas anchor is the quote to publish, and whether any learning flag would survive stress and held-out winters, was not tested. Those flags were not turned on. Winter flight counts and a Telluride snow station are still uncollected.
