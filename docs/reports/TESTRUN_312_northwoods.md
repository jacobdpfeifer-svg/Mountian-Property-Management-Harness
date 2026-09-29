# TESTRUN 312 Northwoods (`summit_haus`) — run 2

**DB path:** `/tmp/testrun_summit_haus.db`  
**Property:** 312 Northwoods / `summit_haus`  
**Run window:** 2026-09-24 through 2027-09-23 inclusive  
**Report date:** 2026-09-25 UTC  
**This report is run 2.** It supersedes the first pushed run (commit `8826bfd` and the local salvage), which froze an empty export. Numbers below were recomputed. They were not copied from that run.

## 1. Executive verdict

**Verdict: the engine produced a full available-night recommendation set, and that set is not yet a comp-grounded price.** It is an explainable, guardrail-shaped nudge around Guesty’s listed rate, on weak ceilings, with an uncalibrated booking probability.

Observed facts:

- Blind export has **311** data rows (311 available nights). 46 booked and 8 blocked nights in the window were not priced. `recommend` exited 0. Guesty write count is 0.
- Every recommendation has ceiling confidence below 0.80 (303 nights at 0.10, 4 at 0.17, 4 at 0.35). 307 of 311 are flagged `weak_ceiling`.
- After deference, the median remaining distance from the listed price is **25%** of the unconstrained model’s distance (311 nights). **88%** of nights retain under 40% of that gap. That is the configured 75% pull toward the incumbent rate when confidence is 0.10 (`min_model_weight` 0.25).
- The market sweep passed 104/104 windows and was still marked **degraded**: only 7 of 14 curated comps matched. Six curated comps are Breckenridge, Keystone, Silverthorne, or Vail seeds and contributed 0 observations.
- Stored market percentiles are independent of the curated set. 194 of 208 snapshot dates are the large-home tier (5–24 listings, median about 13). 14 dates fell back to a wide sweep (191–251 listings).

Inference:

- Summer and shoulder look soft against the large-home market mostly because **Guesty’s listed rate is already soft and deference follows it**, not because the final recommendation independently discovered a lower clearing price. The unconstrained RevPAN optimum is often much lower still (June 1 model about $388 versus same-day market p50 about $1,122). That gap is the elasticity beta (`summer` −1.10, `shoulder_*` −1.70) on a thin, low-confidence ceiling. Final recommendations do not fully express it, except where a weak ceiling is below the decrease cap and the last clamp throws the decrease cap away (21 nights; see section 10).
- This run cannot show the engine beats Guesty on revenue. Forward nights have no booking outcomes. The next experiment is forward shadow-mode, which this session did not run.

Delta versus the first pushed run:

- The empty-export blocker did not recur. Run 1 hash `f28264aee5455dc810e0b3875e77b7bdb76d30d3e46668c951ea499b372c87ef` was a header-only CSV (0 rows) because the blind DB had no target-window inventory. This run seeded a read-only Guesty calendar before `recommend`.
- What persisted: ~75% deference on low-confidence nights, weak ceilings, uncalibrated bookprob, and elasticity optima below summer/shoulder market levels.
- What the salvage already fixed and this run did not re-break: recommendations are not rounded *above* the ceiling (0 nights). Scoped seed pulled 1 listing, not `creekside_haven`. DB identity stayed `unknown`.

## 2. Exact commands and data sources

Preflight (no Guesty prices):

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy
.venv/bin/python scripts/production_preflight.py
```

Results: pytest **253 passed**. Preflight **OK**. mypy **2 errors** in `src/proving_ground/runner.py` (uncommitted proving-ground code, not the recommend path).

Blind acquisition and freeze:

```bash
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db init-db
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db seed-scrape
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db discover-comps --date 2026-12-18 --min-bedrooms 5 --min-sleeps 14 --limit 20
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db discover-comps --date 2026-12-04 --min-bedrooms 5 --min-sleeps 14 --limit 20
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db discover-comps --date 2027-04-24 --min-bedrooms 5 --min-sleeps 14 --limit 20
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db discover-comps --date 2027-07-17 --min-bedrooms 5 --min-sleeps 14 --limit 20
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db scrape-comps --start 2026-09-24 --horizon 365
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db seed-forward-inventory --property summit_haus --source guesty-readonly --horizon 365 --history 14
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db snapshot
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db signals cycle
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db health --property summit_haus
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db recommend --property summit_haus --from 2026-09-24 --to 2027-09-23 --limit 500 --technical
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db export --property summit_haus --from 2026-09-24 --to 2027-09-23 -o data/exports/testrun_312.csv
```

`discover-comps` printed live market ranks and did not write them into the curated set (doing so would have edited tracked CSVs). `scrape-comps` exited 1 with status `degraded` after 104/104 validated windows. That was recorded, not retried.

Post-freeze only:

```bash
.venv/bin/python -m src.cli.main --db /tmp/testrun_summit_haus.db audit --property summit_haus --from 2026-09-24 --to 2027-09-23
```

Audit overall **FAIL** (comp scrape degraded, demand-signal coverage, price bounds, 17 move-cap violations, shoulder median move). It passed `guesty_writes` with count 0.

Sources: scrape-native CSVs (`seed-scrape`), live Airbnb sweeps, read-only Guesty calendar/reservations for `summit_haus` only, policy `config/policies/default.yaml`. `docs/reports/GUESTY_RETROSPECTIVE.md` was opened only after the hash below was recorded. Its −$62 naive bound is not a price input and is not evidence of forward revenue.

## 3. Blind-run integrity

Frozen before any Guesty comparison:

- Export: `data/exports/testrun_312.csv`
- SHA-256: `bc426c452d479794bb3965e9dc74a8fb9c83fe85291f92086c3a936552feddc7`
- Row count: **311** data rows (312 lines including header)
- Blind-freeze timestamp: **2026-09-25T17:46:18Z**
- `recommend` exit: 0

Nothing after this hash changed the export or the recommendation rows.

## 4. Data coverage and freshness

| Layer | What was measured |
|---|---|
| Properties in DB | `summit_haus`, `overlook_ridge` from seed CSVs. No `creekside_haven`. Identity `unknown`. |
| Owned window | 365 nights, 311 available, 46 booked, 8 blocked. Seed synced 1 listing, 380 nights, 40 reservations. `evidence_kind` is NULL on all 365 window nights (sync did not stamp `guesty_readonly`). |
| Historical seed inventory | 2024-11-01..2025-04-15 (166 nights) before the forward seed extended `summit_haus`. |
| Curated comps | 14 comps, 11 members on `summit_haus`. Matched 7/14. OK snapshots: 500. Unavailable: 2,412. |
| Generic market | 208 stay dates, 2026-09-25..2027-09-22, run `2bb9b68f2f6a`, 25,191 listing observations. As-of is 2026-09-25 (same day). |
| Market join to recs | 178 of 311 recommendations land on a swept stay date. The other 133 are nights outside the Fri/Sat and Tue/Wed windows. Those nights are not given a borrowed percentile. |
| Pacing | 1 distinct `as_of` (2026-09-25), 366 nights captured. Health: SUGGEST. Gate: only 1 day of pacing (need 14). |
| Signals | Cycle exit 0. SNOTEL and weather degraded (values above collector max, rejected not clamped). Resort snapshot: 0/26 lifts open (shoulder date). |
| Comp age at health | about 12 hours (sweep finished the same morning). PMS age 0 hours. |

Generic market sample, where a same-day snapshot exists, is the large-home tier when at least 5 sized listings priced (194 dates: n 5–24). It is the wide sweep only on 14 dates (n 191–251). It is never the curated-comp median. Curated median is reported separately and is thin (often 1–2 OK comps per night).

## 5. Full-year recommendation summary

311 suggested or escalated nights. Autonomy: 289 `suggest`, 22 `escalate`. No `handle`.

Guardrail actions: `clamped_increase` 135, none 133, `clamped_decrease` 21, `sanity_floor` 12, `peak_blackout` 10.

Median expected book probability **0.32** (mean 0.37). Treat as **weak / uncalibrated**. One pacing day cannot support it.

Median recommended vs listed by season (recommendations only):

| Season | n | Median rec | Median listed | Median move | Same-day market p25 / p50 / p75 (median of snapshots joined) | Rec vs p50 | Model below p25 |
|---|---:|---:|---:|---:|---|---:|---:|
| shoulder_fall | 36 | $518 | $388 | +11.6% | $648 / $833 / $1,103 | −43% | 1 |
| early_winter | 18 | $900 | $806 | +11.6% | $766 / $1,105 / $1,454 | −17% | 0 |
| peak_ski | 96 | $2,230 | $2,066 | +7.7% | $985 / $1,494 / $2,052 | +33% | 0 |
| shoulder_spring | 61 | $640 | $575 | +11.4% | $833 / $1,201 / $1,370 | −44% | 6 |
| summer | 100 | $1,010 | $1,044 | −5.9% | $718 / $1,056 / $1,597 | −16% | 19 |

Market columns use only nights with a same-day `market_snapshots` row. Peak recommendations sit above the tier p50 and near the curated Winter Park comp median (about $2,168). Shoulder recommendations sit on the +12% increase cap above a low listed rate, still under tier p25 on many joined nights.

## 6. Comparison with Guesty

Listed price is the incumbent rate pulled into the disposable DB by `seed-forward-inventory --source guesty-readonly` before recommend. It was not used as a comp.

- On 88% of nights the post-deference price keeps less than 40% of the gap between the RevPAN optimum and the listed rate. Median retained fraction is 0.25, which is the 75% listed weight at confidence 0.10.
- Increase-capped nights (135) are mostly +11% to +12% versus listed. The model wanted a larger increase; deference and the cap both bind.
- Decrease-capped nights that survive to the export are not actually at the cap. See section 10: the final price equals the weak ceiling, which is below the decrease band.
- `sanity_floor` (12 nights) lifts implausibly low listed rates in early November and early December (listed about $337–$608) up to about $590–$880. The model on those nights was about $1,140–$1,625. Market p50 on the joined nights is about $790–$1,105. The floor guardrail is doing the work, not the comps.
- No rate was written back. `rate_changes` count is 0. Audit `guesty_writes` is 0.

## 7. Comparison with generic market averages

The generic benchmark is `market_snapshots` from the whole bbox sweep, then the group-size filter in policy (`min_bedrooms` 5, `min_sleeps` 14) when that tier has at least 5 prices. Curated-comp medians are a different series.

Same-day tier medians (section 5) put shoulder and spring recommendations well below p50, summer recommendations modestly below p50, and peak recommendations above p50 and inside or above p75. Curated OK comps, where present, price higher than the tier p50 (shoulder curated median about $1,098 vs tier p50 $833; summer about $1,806 vs $1,056; peak about $2,168 vs $1,494). With one or two OK comps per night, that curated median is not a stable anchor. It is also not silently substituted for the market percentile.

133 recommendations have no same-day market row. They are omitted from the percentile comparison rather than filled from the curated median.

## 8. Largest divergences

Classified with the prompt vocabulary.

**Likely underpriced relative to the large-home tier, but the recommendation is mostly the listed rate.** Shoulder fall and shoulder spring: median rec about 43% below same-day p50 because listed itself is low and 135 nights are increase-capped at roughly +12%. Example: 2027-06-01 model $388, listed $597, rec $575, market p25/p50/p75 $808 / $1,122 / $1,484, one curated comp at $1,499. **Potentially justified but dependent on weak assumptions** if June demand is truly soft; **likely underpriced** if the tier percentile is the right peer set. The optimum, not the final rec, is the elasticity artifact.

**Invalid as a ceiling, and the final price follows that ceiling.** 2027-02-12..14: listed $3,830–$3,848, decrease-cap floor about $3,580–$3,598, rounded cap about $3,580–$3,600, persisted `recommended_price` equals the ceiling at $2,715–$2,767. Same-day tier p50 on 2027-02-12 is about $998, so the listed rate is far above the tier and the ceiling is in between. **Impossible to judge** as a market-clearing price: confidence 0.10, comp coverage thin, and the persisted number is not the guardrailed number.

**Well-supported as a guardrail, not as a comp price.** 2026-12-08: listed $601, model $1,625, rec $880 via `sanity_floor`, tier p50 about $1,105. The listed rate is not a credible luxury peak-approach rate. The engine refused to sit on it. It still did not reach the model or the tier median.

**Peak vs tier.** Median peak rec $2,230 vs tier p50 $1,494 (+33%) and listed $2,066. **Potentially justified** by curated WP comps near $2,168 and by a less elastic peak beta, **impossible to judge** as revenue-superior. Several peak nights are `peak_blackout` (no cut).

## 9. Reasoning-quality assessment

The chain is legible. Reasons state the move cap, the RevPAN optimum, the booking probability, and that low ceiling confidence keeps the suggestion near the listed rate.

What is not defensible as a price:

- Booking probabilities are printed as if they were measured (about 18–74% in the technical log) on one day of pacing. They are uncalibrated.
- Ceiling confidence is 0.10 on 303 nights, and 307 nights are explicitly weak. A 10% ceiling should not be allowed to replace a decrease cap (section 10).
- Comp evidence is usually one source. Six curated comps cannot match this market at all.
- Elasticity betas are policy constants, not estimated from this sweep. PriceLabs’ public Hyper Local Pulse note says mountain markets are less price-sensitive in ski season than in summer ([algorithm overview](https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/)). That supports the *direction* of `summer` −1.10 versus a less elastic peak. It does not validate these magnitudes, and their estimator uses on the order of 350 similar listings, not a 7-comp degraded set.

Summer/shoulder probe: the betas do push the unconstrained optimum below the tier on summer (19 joined nights with model < p25) and some spring nights. The **shipped** summer recommendation (median $1,010 vs listed $1,044 vs tier p50 $1,056) is not a large independent underprice. The shipped shoulder recommendation is under the tier because it hugs a low listed rate. Both statements are true. Soft listed rates and elastic optima are different mechanisms. This run’s final CSV mostly shows the first, except on the 21 ceiling-override nights, which show the second.

## 10. Audit and safety findings

Classified, not fixed.

- **Experiment blocker (verified clear this run):** unscoped `creekside_haven` was not in the DB. Seed and recommend were scoped to `summit_haus`.
- **Operational-risk finding (held):** Guesty writes 0. No `push`, no `set_rate`.
- **Recommendation-quality risk:** on 21 nights `recommended_price` equals a weak ceiling that sits **below** the decrease-cap band, while `rounded_price` / `move_cap_price` sit on that band. Example 2027-07-10: listed $2,170, move-cap and rounded $1,920, ceiling and recommended $1,423. Audit reports 21 price-bound failures and 17 move-cap violations (sanity actions excluded from the move count). Rounding does **not** exceed the ceiling (0 nights). The salvage clamp after `round_price_conservative` is working; the last ceiling clamp then undoes `clamped_decrease`.
- **Measurement limitation:** pacing history is 1 day. Bookprob is weak / uncalibrated. No historical contemporaneous comp archive (the retrospective’s comp count was 0 for the same reason). 133 priced nights have no same-day market percentile.
- **Recommendation-quality risk:** curated set includes out-of-market seed comps (Breck, Vail, Keystone) with zero matches. Match rate 50% forced `degraded` even though every window validated.
- **Measurement limitation:** `evidence_kind` is NULL, so later readers cannot see that these nights came from the read-only Guesty seed.
- **Low-priority improvement:** mypy errors in `src/proving_ground/runner.py` lines 282 and 294. SNOTEL/weather collector max rejections. Audit `demand_signals` 27/121 and `shoulder_median_move` median +11.6% (the increase cap, which the check wants under +5%).
- **Operational-risk finding:** health stays `suggest`. 0 peak nights at `handle`. Appropriate.

## 11. Stress-test results

| Case | Label | Why |
|---|---|---|
| No comps | unsafe | Match rate already 50%, and many nights have one OK comp. Removing them would leave deference and the ceiling. |
| Stale comps | unmeasurable | This sweep is same-day. There is no prior snapshot to age. |
| Low comp coverage | unsafe | Current state. Comp-grounded claims are not supported. |
| Missing pacing | unsafe | Bookprob is uncalibrated at 1 day. |
| Weak ceiling confidence | unsafe | 307/311 weak. On 21 nights the weak ceiling overrides the decrease cap. |
| Elasticity beta shifted modestly | highly sensitive | Unconstrained optima already diverge from the tier by hundreds of dollars. Final recs hide much of that via deference. |
| High-demand dates | robust vs listed, highly sensitive vs tier | Peak recs track listed and curated WP comps, and sit above tier p50. |
| Orphan gaps / short windows | unmeasurable | No counterfactual recomputation in this read-only session. |
| Corrupted or implausible listed prices | robust | `sanity_floor` fired on 12 early-winter nights with listed rates near $350–$600. |
| Rounding at floor/ceiling | robust against overrun; unsafe when ceiling is below the decrease cap | 0 recs above ceiling. 21 recs below the decrease band because ceiling wins last. |
| Full-market vs luxury-filtered statistics | highly sensitive | 194/208 snapshots are the small tier (n≈13), not the ~230-listing sweep. Using the wide fallback as the peer set would move p50. |

## 12. Proposed changes, ranked

1. **Do not let a weak ceiling override a move cap.** When `weak_ceiling` is set, persist `move_cap_price` (or the rounded cap) and keep the ceiling advisory. Evidence: 21 nights in this freeze, including 2027-02-12 and 2027-07-10. High confidence this is a composer order bug. Do not change betas to “fix” those nights.
2. **Drop or replace out-of-market seed comps** (Breck/Vail/Keystone) so a Winter Park sweep can reach the 60% match gate. Evidence: 0 OK rows on those six ids; scrape status degraded despite 104/104 good windows.
3. **Stamp `evidence_kind=guesty_readonly`** on the seed path so a later audit can tell incumbent rates from comps.
4. **Keep bookprob labeled uncalibrated** until pacing has 14 days. No coefficient change from this run.
5. **Do not retune `summer` / `shoulder` betas from this freeze.** The final prices mostly did not follow those optima. A beta change would be aimed at a number the export does not ship, and there are no booking outcomes.

## 13. External tools worth considering

**PriceLabs Market Dashboards / Hyper Local Pulse — verdict: shadow.**

- Problem: tier percentiles here often rest on about 13 listings, and elasticity is a constant.
- Thesis: PriceLabs describes a hyper-local set of about 350 similar listings and date-specific elasticity, and states that mountain markets are less price-sensitive in ski season than in summer ([overview](https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/), [market dashboard](https://help.pricelabs.co/portal/en/kb/articles/market-intel-dashboard)).
- Why this repo cannot cover it: the scraper is one bbox sweep plus a 14-row curated file, and pacing history is one day.
- Benefit: an external percentile and occupancy series to compare beside `market_snapshots`, without becoming the price.
- Cost: a vendor feed and a daily join. New failure mode: treating their booked-price estimate as observed ADR.
- Validation: record their p25/p50/p75 next to this engine’s tier for 30 days. Adopt only if the series stays defined on nights this sweep leaves blank. Do not push either price to Guesty.

**AirDNA occupancy priors — verdict: reject for this run.** No occupancy outcome exists yet to calibrate a prior, and a prior would further dress up the uncalibrated bookprob.

## Delta note

Run 1 could not price the year. Run 2 can, because owned nights now come from a read-only Guesty seed. The priced year is still a low-confidence deferral to the listed rate, with a real defect where weak ceilings undercut decrease caps. Revenue superiority is not claimed.

## Orchestrator completion

- DB path: `/tmp/testrun_summit_haus.db`
- Export hash: `bc426c452d479794bb3965e9dc74a8fb9c83fe85291f92086c3a936552feddc7`
- Export row count: 311
- Blind-freeze timestamp: 2026-09-25T17:46:18Z
- Sections 1–13 addressed, including the summer/shoulder elasticity probe.
- This run changed no engine, policy, or schema files. The new artifacts are this report and `data/exports/testrun_312.csv`.
- Guesty write count: 0 (read-only; no rates pushed)
