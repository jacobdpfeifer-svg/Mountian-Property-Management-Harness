# TESTRUN 300 Northwoods (`overlook_ridge`) — run 2

**DB path:** `/tmp/testrun_overlook_ridge.db`  
**Property:** 300 Northwoods / `overlook_ridge`  
**Run window:** 2026-09-24 through 2027-09-23 inclusive  
**Report date:** 2026-09-25 UTC  
**This report is run 2.** It supersedes the first pushed run, which froze an empty export for this property. Figures below are from this session’s own sweep and freeze.

## 1. Executive verdict

**Verdict: Overlook produced a full available-night set, and it is the same kind of result as Summit: a low-confidence deferral to Guesty’s listed rate, not a comp-grounded twin price.** The two Northwoods houses are not treated as identical twins. On the 303 nights both exports price, the recommendation gap moves with the listed-rate gap (correlation 0.67; same sign on 94% of nights). That divergence is evidence-backed. It is not a one-sided data hole.

Observed facts:

- Blind export has **328** data rows. Window inventory is 365 nights: 328 available, 32 booked, 5 blocked. `recommend` exited 0.
- Ceiling confidence is below 0.80 on every night (317 at 0.10). 325 of 328 are `weak_ceiling`.
- Median remaining distance after deference is **25%** of the model-to-listed gap. **89%** of nights retain under 40% of that gap (the 75% listed weight at confidence 0.10).
- Independent sweep `a98a3d62c2b6`: 104/104 windows validated, status **degraded**, 8/14 curated comps matched, 530 OK observations. Six out-of-market seed comps still contribute nothing. Lakota Summit matched 4 nights (Summit’s sweep matched it 0 times).
- Guesty write count is 0. `rate_changes` is 0.

Inference:

- A shared policy and a shared curated file do not make the shipped prices twins. Deference copies each house’s own listed calendar. Own-history ceilings also differ (median absolute ceiling gap $50 on overlapping nights; correlation of ceiling gap with recommendation gap is only 0.17).
- Summer and shoulder recommendations again sit under the large-home tier because the listed rate is soft and the +12% cap binds, while the unconstrained optimum is softer still. Same mechanism as Summit. Not a revenue result.
- Forward shadow-mode is the next experiment. It was not run.

Delta versus the first pushed run: the empty header-only CSV did not recur. Deference, weak ceilings, one-day pacing, and the weak-ceiling override of decrease caps all persisted. Summit’s run 2 already showed the ceiling-versus-decrease-cap defect; Overlook reproduces it on 20 nights.

Preflight was not re-run. The tree is unchanged since Summit’s preflight: pytest 253 passed, production preflight OK, mypy 2 errors in `src/proving_ground/runner.py`.

## 2. Exact commands and data sources

```bash
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db init-db
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db seed-scrape
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-comps --date 2026-12-18 --min-bedrooms 5 --min-sleeps 14 --limit 20
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-comps --date 2026-12-04 --min-bedrooms 5 --min-sleeps 14 --limit 20
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-comps --date 2027-04-24 --min-bedrooms 5 --min-sleeps 14 --limit 20
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-comps --date 2027-07-17 --min-bedrooms 5 --min-sleeps 14 --limit 20
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db scrape-comps --start 2026-09-24 --horizon 365
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db seed-forward-inventory --property overlook_ridge --source guesty-readonly --horizon 365 --history 14
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db snapshot
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db health --property overlook_ridge
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db signals cycle
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db recommend --property overlook_ridge --from 2026-09-24 --to 2027-09-23 --limit 500 --technical
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db export --property overlook_ridge --from 2026-09-24 --to 2027-09-23 -o data/exports/testrun_300.csv
```

`scrape-comps` exited 1 (`degraded`). It was not retried. Discover ranks were not written into tracked CSVs.

Post-freeze:

```bash
.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db audit --property overlook_ridge --from 2026-09-24 --to 2027-09-23
```

Audit overall **FAIL** for the same checks as Summit (degraded scrape, demand signals 27/121, price bounds, 17 move-cap violations, shoulder median +11.9%). `guesty_writes` passed at 0.

Seed synced **1** listing. Properties in the DB are `overlook_ridge` and `summit_haus` (the scrape CSV). `summit_haus` has no target-window nights in this DB (historical seed only, 166 rows). No `creekside_haven`. Identity `unknown`.

Twin comparison uses this run’s Summit freeze `data/exports/testrun_312.csv` (hash `bc426c452d479794bb3965e9dc74a8fb9c83fe85291f92086c3a936552feddc7`), opened only after Overlook’s hash was recorded. The empty run-1 CSVs were not used as prices.

## 3. Blind-run integrity

- Export: `data/exports/testrun_300.csv`
- SHA-256: `9cb8eeb378f3a9467efa2ec2fb8d02598f33ff5ac57b5e45cf33b81496fce27a`
- Row count: **328**
- Blind-freeze timestamp: **2026-09-25T18:05:23Z**
- `recommend` exit: 0

The export was not altered after the hash.

## 4. Data coverage and freshness

| Layer | What was measured |
|---|---|
| Owned window | 365 nights, 328 available, 32 booked, 5 blocked. Seed: 1 listing, 380 nights. `evidence_kind` NULL on the window. |
| Curated comps | 8/14 matched. OK rows 530. Out-of-market Breck/Vail/Keystone seeds: 0. |
| Generic market | 208 stay dates. 194 tier snapshots (n 5–25) and 14 wide snapshots (n 194–266). As-of 2026-09-25. Independent of the curated median. |
| Pacing | 1 day, 366 nights, property `overlook_ridge` only. Health SUGGEST. Comp coverage 73%. Comp age about 12 hours. |
| Signals | Cycle exit 0. Same SNOTEL/weather max rejections as Summit. Resort: 0/26 lifts. |

## 5. Full-year recommendation summary

328 nights. Actions: none 182, `clamped_increase` 99, `clamped_decrease` 20, `sanity_floor` 17, `peak_blackout` 10. Bookprob remains **weak / uncalibrated**.

| Season | n | Median rec | Median listed | Median move | Same-day tier p50 | Rec vs p50 |
|---|---:|---:|---:|---:|---:|---:|
| shoulder_fall | 46 | $560 | $367 | +11.9% | $900 | −43% |
| early_winter | 13 | $860 | $718 | +11.7% | $1,270 | −26% |
| peak_ski | 101 | $2,160 | $1,978 | +8.8% | $1,633 | +23% |
| shoulder_spring | 61 | $600 | $554 | +8.0% | $1,170 | −48% |
| summer | 107 | $970 | $1,001 | −5.0% | $1,148 | −18% |

Pattern matches Summit: peak above the tier and near the listed rate; shoulder under the tier because the listed rate is low and the increase cap binds; summer final rec near the listed rate, not near the elastic optimum.

## 6. Comparison with Guesty

Deference is the main Guesty relationship. 89% of nights keep under 40% of the model-versus-listed gap. Median retained fraction 0.25.

17 `sanity_floor` nights lift low listed rates. 20 `clamped_decrease` nights do not persist the capped price; they persist the ceiling (section 10). No live write.

## 7. Comparison with generic market averages

Same rule as Summit: `market_snapshots` from this DB’s own sweep, group-size tier when at least 5 sized listings priced, wide sweep otherwise. Curated medians are not substituted.

Shoulder and spring recommendations are about 43–48% below same-day tier p50. Summer is about 18% below. Peak is about 23% above. Those percentiles are a ~5–25 listing tier on 194 dates, not the 200-plus listing sweep.

## 8. Largest divergences

**Twin gap, listed-driven — potentially justified as “follow the incumbent,” not as a comp difference.** 2027-08-21: Overlook rec $1,000 on listed $952; Summit rec $1,423 on listed $1,698. Overlook’s model was $1,158 and its ceiling $1,350, so deference held it near $952. Summit’s final price equals its weak ceiling ($1,423) and ignores a rounded decrease cap. The $423 gap is mostly different listed rates plus Summit’s ceiling override. **Likely underpriced** versus a shared luxury tier if both houses are true substitutes; **well-supported** as a reading of two different Guesty calendars.

**Ceiling gap on similar listed rates.** 2027-04-01: Overlook listed $990, rec $740, ceiling $740. Summit listed $1,026, rec $934, ceiling $934. Models equal the ceilings. Listed rates are within about 4%, recommendations are $194 apart. **Invalid** as a twin price: a weak own-history ceiling, not a comp, sets both numbers.

**Decrease cap discarded.** 2027-02-12: listed $3,712, rounded cap $3,465, recommended $2,717 equal to the ceiling. Same defect as Summit’s $3,848 → $2,767 night. **Invalid** relative to the engine’s own guardrail.

**Shoulder versus tier.** Median fall rec $560 vs tier p50 $900, listed $367. **Likely underpriced** against the tier, **dependent on a weak assumption** if Guesty’s low listed rate is intentional soft demand. The engine did not independently choose $560; it added about 12% to $367.

## 9. Reasoning-quality assessment

Reasons still name the cap, the optimum, and low confidence. They do not say “this house is the twin of 312 and the calendars differ.” An operator reading one house cannot see that the other house’s recommendation moved because its listed rate moved.

Twin probe:

- Overlapping priced nights: 303. Only Overlook: 25. Only Summit: 8. Those exclusives are availability, not a failed recommend.
- Recommendations within $1: **2 of 303**. Listed rates within $1: **2 of 303**.
- Median absolute listed gap $38. Median absolute recommendation gap $45. Median absolute model gap $50. Median absolute ceiling gap $50.
- Recommendation gap correlates **0.67** with the listed gap and **0.17** with the ceiling gap. 285/303 nights move the same direction as the listed gap.
- Both houses share `grand_home`, the same policy betas, and the same curated file. The shipped difference is the incumbent calendar, then a smaller own-history ceiling difference. That is evidence-backed. It is not evidence the houses should be forced to one price. Forcing them together would erase real listed-rate differences and would still leave the weak-ceiling bug.

Summer/shoulder: same reading as Summit. Elastic optima sit below the tier. Shipped summer median ($970 vs listed $1,001 vs p50 $1,148) mostly follows the listed rate. Shipped shoulder follows a low listed rate up to the increase cap and remains under the tier.

## 10. Audit and safety findings

- **Experiment blocker, clear here:** scope stayed on `overlook_ridge`. No `creekside_haven`.
- **Operational-risk, held:** Guesty writes 0.
- **Recommendation-quality risk:** 20 nights where `recommended_price` equals a weak ceiling below the decrease band (`rounded_price` is the cap). Audit: 20 bound failures, 17 move-cap violations. 0 recommendations above the ceiling.
- **Measurement limitation:** 1 day of pacing; bookprob uncalibrated; no prior-year comp archive; `evidence_kind` NULL.
- **Recommendation-quality risk:** curated file still contains non-Winter Park comps, so 104 clean windows still grade `degraded` (57% match, gate is 60%).
- **Low-priority:** shoulder-median audit check flags +11.9% because that is the increase cap. mypy proving-ground errors unchanged.

## 11. Stress-test results

| Case | Label | Why |
|---|---|---|
| No comps | unsafe | Already degraded at 8/14. |
| Stale comps | unmeasurable | Same-day sweep only. |
| Low comp coverage | unsafe | Current state. |
| Missing pacing | unsafe | 1 day. |
| Weak ceiling confidence | unsafe | 325/328 weak; 20 nights override the decrease cap. |
| Elasticity beta shifted modestly | highly sensitive | Optima diverge from the tier; shipped prices hide most of it. |
| High-demand dates | robust vs listed | Peak median rec $2,160 vs listed $1,978, above tier p50. |
| Orphan gaps / short windows | unmeasurable | No counterfactual recomputation. |
| Corrupted listed prices | robust | 17 `sanity_floor` nights. |
| Rounding at bounds | robust against overrun; unsafe under a weak ceiling | Same clamp order as Summit. |
| Full-market vs luxury filter | highly sensitive | 194/208 snapshots are the small tier. |
| Twin lockstep | highly sensitive | Prices track each house’s listed rate, not a shared twin anchor. |

## 12. Proposed changes, ranked

1. Same composer fix as Summit: a weak ceiling must not replace `move_cap_price`. Overlook adds 20 more nights, including 2027-02-12 (listed $3,712, cap $3,465, shipped $2,717).
2. Do not add a twin-equality constraint. The calendars differ, and the recommendation gap follows that difference. A shared price would be less evidence-backed than the current deferral.
3. If the operator wants the houses priced as substitutes, show both listed rates and both recommendations on one night in the reason text. That is an explanation change, not a beta change.
4. Remove out-of-market seed comps so a clean 104-window sweep can pass the match gate. Overlook got to 57% and still failed.
5. Do not retune elasticity from this pair of freezes.

## 13. External tools worth considering

**PriceLabs neighborhood percentiles — verdict: shadow.** Same thesis as the Summit report: their published mountain-market note says ski season is less price-sensitive than summer, and their comp set is on the order of 350 similar listings ([algorithm overview](https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/)). This repo’s tier is often under 25 listings, and the twin gap is a listed-rate gap a vendor percentile will not explain. Use an external series only as a third column beside both houses. Do not adopt it as the price, and do not push it to Guesty.

**A twin-diff report inside this repo — verdict: test.** The problem (operators cannot see that 300 and 312 diverged because listed rates diverged) is already measured here (correlation 0.67 on 303 nights). No new vendor is required. A later audit can add a read-only comparison once both freezes exist. Not in this property session.

## Delta note

Run 1 priced zero Overlook nights. Run 2 priced 328. Relative to this run’s Summit freeze, the houses are consistent in mechanism and inconsistent in dollars, and the dollar gap is mostly the Guesty calendar.

## Orchestrator completion

- DB path: `/tmp/testrun_overlook_ridge.db`
- Export hash: `9cb8eeb378f3a9467efa2ec2fb8d02598f33ff5ac57b5e45cf33b81496fce27a`
- Export row count: 328
- Blind-freeze timestamp: 2026-09-25T18:05:23Z
- Sections 1–13 addressed, including the twin probe against this run’s Summit freeze.
- No engine, policy, or schema files were changed.
- Guesty write count: 0 (read-only; no rates pushed)
