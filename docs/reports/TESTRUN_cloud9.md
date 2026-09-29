# TESTRUN Cloud 9 (`cloud_9`) — run 2

**DB path:** `/tmp/testrun_cloud_9.db`  
**Property:** Cloud 9 / `cloud_9`  
**Owner:** `cloud9`  
**Engine market:** `grand_home` (Winter Park / Fraser / Tabernash). Fraser-only is not used.  
**Run window:** 2026-09-24 through 2027-09-23 inclusive  
**Report date:** 2026-09-25 UTC  
**This report is run 2.** It supersedes the salvage Cloud 9 report (364-row four-bucket freeze, hash `0995396faf10030b04c6ab08de7d1a199f3beebc80ff5a659a0177d7fb6e19f1`). Numbers below were recomputed.

## 1. Executive verdict

**Verdict: Cloud 9 produced a full available-night recommendation set on a live 6-bedroom Winter Park/Fraser comp set, and that set is still not a cold-start luxury price.** It is a low-confidence deferral to Guesty’s listed rate. The house stays in shared `grand_home`. Autonomy correctly stayed at `suggest`.

Observed facts:

- Blind export has **321** data rows. Window inventory is 365 nights: 322 available, 39 booked, 4 blocked (one available night was not priced). `recommend` exited 0.
- Own history before the window is **13 nights** (2026-09-11..2026-09-23). Sync is `degraded`: 1 listing, 380 nights, 17 reservations, warning that only 45 booked nights carry a realised price.
- Live comps were discovered independently (`bd>=6`) and persisted in the disposable DB. The operator CSV was **not** loaded as the scrape set. 10 live comps, 10/10 matched, scrape **OK** (104/104 windows). Two of ten room ids also appear in `data/cloud9/comps.csv`.
- Ceiling confidence is 0.10 on 311 of 321 nights. 320 of 321 are `weak_ceiling`. All 321 nights are `suggest`.
- After deference, median remaining distance from listed is **25%** of the model gap. **86%** of nights retain under 40% of that gap.
- 37 nights persist a weak ceiling below the decrease-cap band (same composer order as the twins). 0 nights exceed the ceiling.
- Guesty write count is 0. `rate_changes` is 0. No `creekside_haven`. Identity `unknown`.

Inference:

- A 6-bedroom profile is present in the live market, but sleeps is usually missing, so the group-size *sleeps* filter barely fires. The generic market percentile is still the large-home *bedroom* tier (often ~13 listings), not a sleeps-16 Fraser subset. That tier can pull a 6bd/sleeps-15 house toward mid-luxury 5bd rates. Peak listed rates (median $2,173) sit above that tier p50 ($1,816) and the recommendation follows listed, not the tier.
- The salvage four-price calendar ($880/$955/$1060/$1265) did not recur. This freeze has **195** distinct listed prices (90 nights at $850). That is a real Guesty calendar, not a four-bucket engine artifact.
- This run cannot show revenue superiority. Forward shadow-mode is the next experiment. It was not run.

Delta versus salvage / first pushed run:

- Salvage: 364 rows, unscoped `sync-guesty` pulled extra listings, scrape status was not a 10/10 live set, report was reconstructed after a stalled child. This run: scoped seed (1 listing), live comps, 321 priced available nights, scrape OK.
- What persisted: ~75% deference, weak ceilings, 1-day pacing, uncalibrated bookprob, weak-ceiling override of decrease caps.
- What the salvage already fixed: rounding does not exceed the ceiling; `--property` on Guesty pull. Both held.

Preflight was not re-run. Tree unchanged since Summit: pytest 253 passed, production preflight OK, mypy 2 errors in `src/proving_ground/runner.py`.

## 2. Exact commands and data sources

```bash
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db init-db
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db ingest-csv --properties data/cloud9/properties.csv
# live discover-comps on 2026-12-18, 2026-12-04, 2027-04-24, 2027-07-17
#   --min-bedrooms 6 --min-sleeps 16; persist 10 room ids into comps (not tracked CSVs)
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db scrape-comps --start 2026-09-24 --horizon 365
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db seed-forward-inventory --property cloud_9 --source guesty-readonly --horizon 365 --history 14
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db snapshot
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db health --property cloud_9
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db signals cycle
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db recommend --property cloud_9 --from 2026-09-24 --to 2027-09-23 --limit 500 --technical
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db export --property cloud_9 --from 2026-09-24 --to 2027-09-23 -o data/exports/testrun_cloud9.csv
```

The first `scrape-comps` after ingest (0 comps) failed with “no active comps”; that is recorded. After persist, scrape `fdb54156a903` exited 0. Discover ranks were not written to tracked CSVs.

A first persist attempt used a non-existent `get_provider` import and was aborted; inventory from the scoped seed was kept. Comps were then persisted with `PyAirbnbProvider`.

Post-freeze:

```bash
.venv/bin/python -m src.cli.main --db /tmp/testrun_cloud_9.db audit --property cloud_9 --from 2026-09-24 --to 2027-09-23
```

Audit overall **FAIL** (demand_signals 27/121, price bounds, 24 move-cap violations). `guesty_writes` passed at 0. `comp_scrape_status` **PASS**. Shoulder median move **PASS** (−3.9%).

`docs/reports/GUESTY_RETROSPECTIVE.md` was not used as a Cloud 9 price source. The −$62 naive bound is a prior-window twins comparison, not this freeze.

## 3. Blind-run integrity

- Export: `data/exports/testrun_cloud9.csv`
- SHA-256: `99ef09113d3816627e3c90882badc18585ea1aea0554a89a338d3007614f1202`
- Row count: **321**
- Blind-freeze timestamp: **2026-09-25T19:34:32Z**
- `recommend` exit: 0

The export was not altered after the hash.

## 4. Data coverage and freshness

| Layer | What was measured |
|---|---|
| Properties | `cloud_9` only. Owner `cloud9`, market `grand_home`, 6 bedrooms, max occupancy 15. Floor/base/max after sync $612 / $2,801 / $5,370. |
| Owned window | 365 nights, 322 available, 39 booked, 4 blocked. Seed: 1 listing, 380 nights, 17 reservations, status `degraded`. `evidence_kind` NULL. |
| Own history | 13 nights immediately before the window. Cold-start is real. |
| Live comps | 10 members, all with Airbnb room ids. Match 10/10, 402 OK snapshots. Sleeps known on 1 of 10 (`28918989`, sleeps 16, 8 OK rows). |
| CSV contrast | Operator file has 5 room ids (plus two direct WPLC/WPH comps with no Airbnb id). Overlap with the live set: Winter Park Ski House `998026465866480254` and Family Friendly 6BR `28918989`. Ranch Creek, The Views, Lakota Reserve, and Deer were not in the live 6bd discover ranks used here. |
| Generic market | 208 stay dates, 2026-09-25..2027-09-22. 194 tier snapshots (n 5–27, mean 13.1) and 14 wide snapshots (n 193–260). Independent of the curated median. |
| Pacing | 1 day, 366 nights. Health SUGGEST. Comp coverage 100%. Comp age ~14 hours. PMS age 0 hours. Gate: degraded sync + 1 day pacing. |
| Signals | Cycle exit 0. Same SNOTEL/weather max rejections. Resort: 0/26 lifts. |

## 5. Full-year recommendation summary

321 nights, all `suggest`. Actions: none 259, `clamped_decrease` 37, `clamped_increase` 25. Bookprob is **weak / uncalibrated**.

| Season | n | Median rec | Median listed | Median move | Same-day tier p25 / p50 / p75 | Rec vs p50 | Rec &lt; p25 |
|---|---:|---:|---:|---:|---|---:|---:|
| shoulder_fall | 51 | $795 | $850 | −5.3% | $588 / $850 / $1,114 | −10% | 3 |
| early_winter | 17 | $875 | $850 | +0.6% | $796 / $1,166 / $1,380 | −22% | 1 |
| peak_ski | 85 | $2,210 | $2,173 | +2.7% | $1,022 / $1,816 / $2,162 | +17% | 1 |
| shoulder_spring | 61 | $820 | $850 | −4.1% | $807 / $1,125 / $1,354 | −27% | 13 |
| summer | 107 | $1,240 | $1,278 | −2.1% | $775 / $1,142 / $1,578 | +12% | 6 |

Median rec $1,100 vs median listed $1,078. Year-round recs are not a four-price grid. 33% of recs fall in $780–$900, mostly following the $850 listed cluster.

## 6. Comparison with Guesty

Deference is the primary relationship. 86% of nights keep under 40% of the model-versus-listed gap. Median retained fraction 0.25.

Peak nights track listed (median rec $2,210 vs listed $2,173). Shoulder listed is often $850; recommendations sit a few percent below.

The 37 `clamped_decrease` nights do not persist the cap. Example 2027-02-14: listed $3,949, rounded cap $3,700, recommended $2,683 equal to the ceiling. **Invalid** relative to the engine’s own decrease cap.

No live write.

## 7. Comparison with generic market averages

`market_snapshots` from this DB’s sweep, group-size filter when ≥5 sized listings priced. Curated-comp medians are not substituted.

Shoulder spring recommendations sit ~27% below same-day tier p50 while listed is $850. Summer recommendations sit ~12% *above* tier p50 while listed is $1,278 — the generic 5bd+ tier is below Cloud 9’s listed summer rate, so the whole-market/large-home p50 is **not** dragging summer down. Early winter *is* below p50 because listed $850 is already below $1,166. Peak recs are above tier p50 because listed is.

A sleeps-16 filter would have almost no sample: only one live comp records sleeps. Splitting Fraser out of `grand_home` would not fix that missing sleeps field.

## 8. Largest divergences

**Invalid as a shipped decrease.** 2027-02-12..14: listed $3,859–$3,949, recommended $2,683 = weak ceiling, rounded caps $3,610–$3,700. Same composer defect as the twins.

**Potentially justified as following listed, likely underpriced vs a sleeps-16 peer set.** Shoulder spring: rec $820 vs listed $850 vs tier p50 $1,125. The engine did not independently choose $820; it hugged $850. Whether $850 is the right Fraser 6bd rate is **impossible to judge** with 13 nights of history and 1-day pacing.

**Well-supported as not a mid-market pull on peak.** Peak rec $2,210 vs tier p50 $1,816 vs listed $2,173. Deference kept the house *above* the 5bd+ tier. **Potentially justified** if Guesty’s peak calendar is the right luxury ask; **impossible to judge** as revenue.

**Live vs CSV comps.** The live set includes 8- and 9-bedroom downtown homes (`20731879`, `20534823`, `33799255`) that the operator CSV does not treat as core. Ranch Creek (CSV score 92) did not appear in the 6bd discover ranks persisted here. **The live set is larger-home, not Fraser-substitutable.** That is a finding, not a reason to load the CSV as the scrape set.

## 9. Reasoning-quality assessment

Reasons name the cap, the optimum, and low confidence. They do not say “cold-start, 13 nights of history, sleeps unknown on 9/10 comps.” An operator cannot see that the ceiling is almost entirely a seasonal anchor.

Cold-start probe:

- Larger luxury/group-size profile: 6bd is in the live set. Sleeps-16 is not, except one listing. The generic benchmark is a ~13-listing 5bd+ tier, not a sleeps-16 distribution.
- Generic p50 dragging the rec down: **false on peak and summer** (recs at or above p50 because listed is). **true on shoulder/early winter** only because listed is already $850.
- Curated substitutability: mixed. Two CSV cores matched live. Operator Fraser/direct comps were unused. 8–9bd homes are not Cloud 9 substitutes.
- Market-wide large homes: 10/10 matched this sweep, but 9 of 10 lack sleeps, so percentiles are bedroom-tier, not occupancy-tier.
- Floor/ceiling: floor $612, max $5,370 after sync recalibration. Weak ceilings (~$2,683 peak, ~$1,544 July) sit inside that band and still override decrease caps. **Not defensible as a known ceiling.**
- How a near-zero-history property should be priced: this freeze prices it as “75% listed + 25% model on a 10% ceiling.” That is internally consistent with policy. It is not a comp-anchored cold-start. A Fraser-only market is **rejected for implementation**; it remains a Phase 5 proposal with no evidence it would change this deference result.

## 10. Audit and safety findings

- **Experiment blocker, clear:** scoped to `cloud_9`. No `creekside_haven`. Seed listed 1 listing.
- **Operational-risk, held:** Guesty writes 0.
- **Recommendation-quality risk:** 37 nights where `recommended_price` equals a weak ceiling below the decrease band. Audit: 37 bound failures, 24 move-cap violations. 0 recs above ceiling.
- **Measurement limitation:** 13 history nights, 1 day of pacing, bookprob uncalibrated, `evidence_kind` NULL, sync `degraded`.
- **Recommendation-quality risk:** unknown sleeps on 9/10 live comps. 6bd discover included 8–9bd homes.
- **Low-priority:** demand_signals 27/121. mypy proving-ground errors unchanged.
- **Correct behavior:** health demoted to SUGGEST. 0 `handle` nights.

## 11. Stress-test results

| Case | Label | Why |
|---|---|---|
| No comps | highly sensitive | This run *had* a complete match. Removing them would leave listed + seasonal anchors only. |
| Stale comps | unmeasurable | Same-day sweep. |
| Low comp coverage | robust vs last salvage | 100% match this run. Coverage ≠ substitutability. |
| Missing pacing | unsafe | 1 day, 13 history nights. |
| Weak ceiling confidence | unsafe | 320/321 weak; 37 nights override the decrease cap. |
| Elasticity beta shifted modestly | highly sensitive | Optima still sit off listed; shipped prices hide most of it. |
| High-demand dates | robust vs listed | Peak rec ≈ listed, above tier p50. |
| Orphan gaps / short windows | unmeasurable | No counterfactual. |
| Corrupted listed prices | unmeasurable | No `sanity_floor` this freeze. 195 distinct listed values. |
| Rounding at bounds | robust against overrun; unsafe under a weak ceiling | Same clamp order as the twins. |
| Full-market vs luxury filter | highly sensitive | 194/208 snapshots are the ~13-listing tier. |
| Fraser-only market | unmeasurable; do not adopt | Sleeps missing; deference would still hug listed. Keep `grand_home`. |

## 12. Proposed changes, ranked

1. Same composer fix as the twins: a weak ceiling must not replace `move_cap_price`. Cloud 9 adds 37 nights (2027-02-14: listed $3,949, cap $3,700, shipped $2,683).
2. Do not split Fraser out of `grand_home` from this freeze. Peak/summer recs were not dragged by the shared-market p50.
3. Persist sleeps on live comps (or drop 8–9bd discover hits) before claiming a sleeps-16 cold-start set. Contrast with the operator CSV is already enough to show the live set is not the CSV set.
4. Stamp `evidence_kind=guesty_readonly` on the seed path.
5. Do not retune elasticity or invent a four-bucket calendar. This freeze is not four buckets.

## 13. External tools worth considering

**PriceLabs occupancy / percentile for cold-start — verdict: shadow.** Problem: 13 nights of history and unknown sleeps. Thesis: PriceLabs prices from a hyper-local similar-size set and date-specific elasticity, and notes mountain markets are less price-sensitive in ski season than in summer ([algorithm overview](https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/)). This repo cannot estimate occupancy priors from 1 pacing day. Benefit: an external occupancy series beside Cloud 9’s $850 shoulder cluster. Cost/vendor + treating booked-price estimates as ADR. Validation: 30 days of shadow columns. Do not push.

**AirDNA occupancy prior — verdict: reject this run.** No outcomes exist to check a prior against, and it would dress up uncalibrated bookprob.

**Fraser-only market — verdict: reject.** Phase 5 proposal only. No evidence it would change deference to listed.

## Delta note

Salvage priced a four-bucket year after an unscoped sync. Run 2 priced 321 nights on a scoped calendar and a live 6bd set that actually matched. The mechanism is still listed-rate deference on a weak ceiling. Cloud 9 stays in `grand_home`.

## Orchestrator completion

- DB path: `/tmp/testrun_cloud_9.db`
- Export hash: `99ef09113d3816627e3c90882badc18585ea1aea0554a89a338d3007614f1202`
- Export row count: 321
- Blind-freeze timestamp: 2026-09-25T19:34:32Z
- Sections 1–13 addressed, including the cold-start / `grand_home` probe.
- No engine, policy, or schema files were changed.
- Guesty write count: 0 (read-only; no rates pushed)
