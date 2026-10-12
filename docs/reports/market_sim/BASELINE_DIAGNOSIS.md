# Corrected-engine market-sim baseline

Simulated shopper-world revenue only. Not realized revenue. Bootstrap intervals are not family-wise adjusted. Counting “scenarios won” is descriptive only; no policy is the winner of an unadjusted multi-scenario comparison.

Run: `~/wp-price-runs/market_sim/baseline_79dae5d`  
Commit `79dae5d`, `git_dirty: false`, `models_enabled: []`, 1,800 jobs, wall clock 11,306.8 s (~188 min), exit 0.  
Audit `scripts/audit_market_sim.py` exit 0. Same-seed determinism test passed. `content_hash` unique across seeds within every scenario/policy pair. Held-out scenarios scored: `holiday_shift`, `den_capacity_cut`, `regime_change`, `pandemic_collapse`. Decomposition scoreboard reconciliation difference is 0 on all six retained comparisons.

## For the owner

On an ordinary simulated winter (`normal`), the current engine earns about **$93,000 less** per season than a flat seasonal rate (mean engine − flat −$93,012; 95% interval −$98,760 to −$87,708; 0 of 30 seeds nonnegative). The same pattern appears on the four winters that were never used to calibrate the shopper world (about −$89k to −$95k versus flat, except `pandemic_collapse` at −$15k).

The money is not mainly “sold the same nights cheaper.” On `normal` versus flat, nights both policies sold differ by about **−$24k**. Nights only the flat rate sold cost about **−$103k**. Nights only the engine sold add about **+$34k**. Peak ski carries about **−$67k** of the gap: the engine’s ADR is *higher* ($969 vs $900) and occupancy is much *lower* (0.35 vs 0.61). Cloud 9 carries about **−$52k**. Shoulder and early winter are the opposite price error: the engine sits on the **floor** (~18–22% of recommendations) and underprices (ADR $374–$462 vs $650–$750).

The guess that peak elasticity −0.65 pins almost every peak night at the ceiling is **not** supported. Only about **20%** of peak recommendations sit at the ceiling, and almost none of the booked nights are `peak_blackout`. Peak still loses on **volume** at a high ADR. Guardrail clamps on booking days are a few tenths of a night per seed.

## Paired results (engine − other)

### Engine − flat

| scenario | held out | mean | median | min | max | nonnegative/30 | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| normal |  | -93,012 | -90,212 | -130,665 | -70,790 | 0/30 | -98,760 to -87,708 |
| price_war |  | -91,144 | -87,462 | -121,510 | -55,285 | 0/30 | -97,079 to -84,933 |
| holiday_shift | yes | -94,861 | -93,990 | -134,330 | -50,480 | 0/30 | -101,658 to -88,106 |
| den_capacity_cut | yes | -92,829 | -93,190 | -128,342 | -54,940 | 0/30 | -98,707 to -87,259 |
| regime_change | yes | -89,211 | -88,672 | -114,560 | -40,578 | 0/30 | -93,928 to -83,911 |
| pandemic_collapse | yes | -15,114 | -14,378 | -36,115 | 550 | 1/30 | -18,012 to -12,217 |
| drought |  | -91,508 | -92,810 | -131,835 | -54,685 | 0/30 | -96,983 to -86,370 |
| early_closure |  | -89,379 | -88,845 | -130,030 | -49,090 | 0/30 | -95,622 to -83,639 |
| i70_closure |  | -89,236 | -91,185 | -125,750 | -38,806 | 0/30 | -95,052 to -83,489 |
| late_opening |  | -92,282 | -95,730 | -112,445 | -64,370 | 0/30 | -96,258 to -88,063 |
| recession |  | -85,065 | -85,235 | -126,400 | -50,785 | 0/30 | -91,087 to -79,220 |
| record_snow |  | -88,024 | -91,180 | -121,635 | -54,335 | 0/30 | -93,598 to -82,117 |
| scrape_outage |  | -91,443 | -89,590 | -125,845 | -64,775 | 0/30 | -97,371 to -85,503 |
| stale_pms |  | -91,658 | -91,460 | -113,640 | -65,526 | 0/30 | -96,090 to -87,211 |
| supply_surge |  | -89,749 | -86,445 | -131,965 | -64,655 | 0/30 | -94,854 to -84,853 |

Descriptive: engine mean beats flat on **0 of 15** scenarios.

### Engine − comp_median

| scenario | held out | mean | median | min | max | nonnegative/30 | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| normal |  | -89,253 | -88,056 | -116,138 | -59,699 | 0/30 | -94,646 to -83,932 |
| price_war |  | -73,922 | -71,859 | -110,286 | -52,518 | 0/30 | -78,621 to -69,487 |
| holiday_shift | yes | -86,652 | -91,527 | -117,901 | -54,465 | 0/30 | -92,280 to -80,825 |
| den_capacity_cut | yes | -90,062 | -91,145 | -125,573 | -54,495 | 0/30 | -95,686 to -84,693 |
| regime_change | yes | -86,243 | -85,413 | -123,289 | -56,238 | 0/30 | -91,838 to -80,468 |
| pandemic_collapse | yes | -39,873 | -40,064 | -64,121 | -20,913 | 0/30 | -44,938 to -34,867 |
| drought |  | -90,336 | -90,608 | -115,501 | -46,341 | 0/30 | -95,317 to -85,047 |
| early_closure |  | -84,627 | -85,950 | -115,722 | -42,888 | 0/30 | -90,914 to -78,190 |
| i70_closure |  | -84,005 | -87,474 | -104,922 | -34,176 | 0/30 | -89,501 to -78,094 |
| late_opening |  | -89,007 | -90,142 | -119,978 | -55,551 | 0/30 | -94,572 to -83,366 |
| recession |  | -85,529 | -85,758 | -114,862 | -45,419 | 0/30 | -91,625 to -79,793 |
| record_snow |  | -79,774 | -78,636 | -120,760 | -42,344 | 0/30 | -85,521 to -74,454 |
| scrape_outage |  | -91,443 | -89,590 | -125,845 | -64,775 | 0/30 | -97,371 to -85,503 |
| stale_pms |  | -86,946 | -82,711 | -120,793 | -59,461 | 0/30 | -92,735 to -81,451 |
| supply_surge |  | -83,641 | -85,202 | -120,899 | -46,063 | 0/30 | -88,873 to -78,294 |

### Engine − tool

| scenario | held out | mean | median | min | max | nonnegative/30 | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| normal |  | -39,021 | -40,463 | -71,728 | 40 | 1/30 | -44,388 to -33,514 |
| price_war |  | -77,471 | -76,953 | -112,870 | -52,312 | 0/30 | -82,562 to -72,614 |
| holiday_shift | yes | -35,907 | -34,655 | -76,859 | 7,310 | 1/30 | -42,677 to -29,270 |
| den_capacity_cut | yes | -38,760 | -41,117 | -60,676 | 3,767 | 1/30 | -43,783 to -33,555 |
| regime_change | yes | -36,835 | -38,873 | -64,675 | -6,469 | 0/30 | -42,049 to -31,845 |
| pandemic_collapse | yes | -8,357 | -7,287 | -31,647 | 10,563 | 6/30 | -11,963 to -4,861 |
| drought |  | -37,855 | -39,326 | -59,769 | -18,609 | 0/30 | -41,516 to -33,712 |
| early_closure |  | -33,896 | -38,860 | -52,165 | -13,133 | 0/30 | -38,066 to -29,666 |
| i70_closure |  | -35,048 | -37,699 | -55,902 | -7,432 | 0/30 | -39,225 to -30,833 |
| late_opening |  | -39,127 | -36,172 | -73,937 | 1,858 | 1/30 | -44,337 to -33,778 |
| recession |  | -32,418 | -33,596 | -65,654 | -8,962 | 0/30 | -36,409 to -28,474 |
| record_snow |  | -37,175 | -37,184 | -62,951 | -8,420 | 0/30 | -42,919 to -30,961 |
| scrape_outage |  | -34,228 | -34,632 | -64,669 | -7,806 | 0/30 | -39,796 to -28,695 |
| stale_pms |  | -41,303 | -38,014 | -69,086 | -15,903 | 0/30 | -46,637 to -35,949 |
| supply_surge |  | -37,830 | -35,574 | -67,722 | -13,540 | 0/30 | -43,099 to -32,689 |

The gap versus the public-tool imitation is smaller than versus flat, except on `price_war`.

## Loss mechanisms, ranked by dollars (`normal` vs flat, per-seed means)

1. **Peak volume loss (~−$67k seasonal revenue; nights only flat sold ~−$103k portfolio-wide).** Peak occupancy 0.346 vs 0.606. Largest lead bucket: 22–60 days (−$44k). Cloud 9 (−$52k) and Overlook Ridge (−$34k); Summit Haus is close (−$6k) with *higher* occupancy than flat.
2. **Same-night underpricing (~−$24k `both_sold`).** Mixed: peak ADR is above flat; early winter and shoulder ADR are far below flat.
3. **Shoulder + early winter net (~−$26k combined).** Engine occupancy is *higher* than flat, ADR much lower (shoulder $374 vs $650; early winter $462 vs $750). About 18% of early-winter recommendations and 22% of shoulder recommendations sit at the **floor**.
4. **Guardrails on booking day.** `peak_blackout` 14.2 nights / ~$14k engine revenue; clamps < 0.5 nights. Not the ranked dollar story.
5. **Ceiling pin from peak elasticity −0.65.** 19.7% of peak recommendations at ceiling, 0.0% at floor. The inelastic peak setting does **not** put the engine on the ceiling for most peak nights. Peak still looks too expensive for this shopper world.

`price_war` and `holiday_shift` vs flat show the same split (volume dominates, peak ~−$64k to −$68k, Cloud 9 ~−$51k to −$53k, ~20% peak recs at ceiling, ~18–24% shoulder recs at floor). The mechanism is not specific to `normal`.

## Proven

- Completeness: 1,800 unique scenario × policy × seed rows.
- Provenance: empty `models_enabled`, clean git, commit `79dae5d`.
- Decomposition revenue matches the scoreboard revenue column (difference 0).
- Engine mean is below flat, below competitor-median, and below tool on every scenario’s mean (tool has a few nonnegative seeds, not a mean win except none of the 15 means).
- Peak occupancy gap and Cloud 9 concentration on the three retained scenarios.
- Peak recs at ceiling ~20%, not ~100%. Shoulder/early recs at floor ~18–24%.

## Simulator-dependent

- Shopper choice, outside option, and competitor types in `proving_ground_exam/`.
- Flat seasonal rates and the tool imitation as coded in this synthetic world.
- Elasticity numbers in `booking_probability.elasticity_by_season` interacting with a linear demand curve whose argmax is the ceiling when |β| < 1.

## Unknown in the real world

- Whether Winter Park guests would leave Cloud 9 empty at these peak ADRs.
- Whether a lower peak ceiling would leave money on the table on Christmas weeks in Guesty.
- Whether floor-pinned shoulder prices are a compose/history problem that YAML elasticity cannot fix.
- Any causal effect of shipping a candidate into Guesty (not done).

## Pre-registered candidates

Copies of `config/policies/default.yaml` only. `models.*.enabled` stay false. `default.yaml` is not edited. Values are not copied from the flat benchmark.

### 1. `peak_more_elastic`

- **YAML:** `booking_probability.elasticity_by_season.peak_ski`: −0.65 → **−1.20**
- **Mechanism:** peak volume loss. |β| > 1 so RevPAN’s interior optimum can sit below the ceiling.
- **Expected:** peak occupancy up, peak ADR down, `only_flat_sold` shrinks; early/shoulder mostly unchanged. `price_war` should not get worse if the extra peak elasticity tracks weaker competitor prices.

### 2. `shoulder_off_floor`

- **YAML:** `early_winter` −1.35 → **−1.10**; `shoulder_spring` and `shoulder_fall` −1.70 → **−1.10**
- **Mechanism:** floor-pinned underpricing on early winter and shoulder (~−$26k on `normal`).
- **Expected:** higher ADR and fewer recs at the floor in early/shoulder; some occupancy loss; peak roughly unchanged. Risk: if shoppers need cheap shoulder nights, this can lose volume.

### 3. `lower_peak_ceiling`

- **YAML:** `ceiling.percentile`: 0.90 → **0.80**
- **Mechanism:** peak volume loss while only ~20% of recs are at the ceiling — the history ceiling itself may sit above what this shopper world will pay, including Cloud 9.
- **Expected:** lower peak listed/ceiling band, more peak bookings, smaller Cloud 9 gap; not a copy of the flat $900 peak ADR.

File: `$RUN/candidates/<name>.yaml`.
