# Testrun diagnostic - 300 Northwoods (`overlook_ridge`)

DB path: `/tmp/testrun_overlook_ridge.db`

Run window: 2026-09-24 through 2027-09-23 inclusive. Property: `overlook_ridge`
(`300 Northwoods`), owner `northwoods`, market `grand_home`.

## 1. Executive verdict

Verdict: **experiment blocker** for this property run. The engine did not produce a
defensible full-year recommendation set because the blind, non-Guesty forward inventory
acquisition failed. The frozen export contains **0 recommendations**. That is the right
failure mode: the engine did not silently fill missing property listed prices from Guesty
or from the generic market after the fact.

Observed facts:

- The isolated DB was created at `/tmp/testrun_overlook_ridge.db`.
- No `creekside_haven` row was present in the isolated DB before or after the blind run.
- Blind comp acquisition succeeded partially but was degraded: 102/104 windows passed,
  24,735 listings were seen, 7/14 configured comps matched, 504 usable comp observations
  were written, and 2 windows timed out.
- Blind forward property inventory was not available from the seed data. `data/scrape`
  inventory ended at 2025-04-15.
- Public owned-listing discovery did not find the exact Northwoods listings. It assigned
  both twins to the same proxy room: `1767097517715247917`, named `PROXY:Sleeps 18 | 2
  Hot Tubs, Sauna & Game Room`.
- Two attempts to scrape forward owned-listing inventory exited with code 143 before
  committing rows.
- The scoped blind recommendation command generated 0 recommendations.
- After freeze, read-only Guesty calendar GETs for the two locked Northwoods listing IDs
  returned full 365-day calendars.

Inference:

- This run cannot validate pricing reasoning for 300 Northwoods because no frozen
  recommendations exist to compare with Guesty, curated comps, or the generic market.
- The most important diagnostic result is data-readiness: without a Guesty calendar pull,
  the current blind path does not reliably supply the property-specific forward
  `listed_price` input required by `build_features`.

No revenue-superiority claim is made. Booking probability and expected RevPAN remain weak
and uncalibrated because pacing history is absent.

## 2. Exact commands and data sources used

Preflight and static checks:

```bash
../../../.venv/bin/python -m pytest -q
../../../.venv/bin/python -m mypy
../../../.venv/bin/python scripts/production_preflight.py
../../../.venv/bin/python scripts/quality_gates.py
```

Blind DB and non-Guesty acquisition:

```bash
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db init-db
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db seed-scrape
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-comps --date 2026-12-26 --min-price 400 --min-bedrooms 5 --min-sleeps 14 --limit 20
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-comps --date 2026-12-05 --min-price 400 --min-bedrooms 5 --min-sleeps 14 --limit 20
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-comps --date 2027-04-24 --min-price 300 --min-bedrooms 5 --min-sleeps 14 --limit 20
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-comps --date 2027-07-10 --min-price 400 --min-bedrooms 5 --min-sleeps 14 --limit 20
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db scrape-comps --horizon 365
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db health --property overlook_ridge
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-properties --date 2026-12-05,2026-12-26,2027-07-10 --min-price 300 --property overlook_ridge --persist
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db discover-properties --date 2026-12-05,2026-12-26,2027-07-10 --min-price 300 --property summit_haus --persist
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db scrape-properties --from 2026-09-24 --to 2027-09-23
```

Blind recommendation and freeze:

```bash
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db recommend --property overlook_ridge --from 2026-09-24 --to 2027-09-23 --limit 500 --technical
../../../.venv/bin/python -m src.cli.main --db /tmp/testrun_overlook_ridge.db export --property overlook_ridge --from 2026-09-24 --to 2027-09-23 -o data/exports/testrun_300.csv
shasum -a 256 data/exports/testrun_300.csv
```

Post-freeze Guesty reveal:

- Used `GuestyClient.calendar()` GETs only.
- Fetched only locked listing IDs:
  - `overlook_ridge`: `69f14a198a424c00146db9d8`
  - `summit_haus`: `69f3fce1fd7011001188056e`
- Did not call `sync-guesty`, because unscoped listing sync could touch
  `creekside_haven`.
- Did not call `set_rate`, `push_rate`, `push_recommendations`, `wp-price push`, or
  any PUT/POST/PATCH/DELETE to Guesty except OAuth.

Data sources:

- Required docs and config listed in the prompt.
- `data/scrape/properties.csv`, `data/scrape/inventory.csv`, `data/scrape/comps.csv`.
- Public Airbnb sweep provider through `discover-comps`, `scrape-comps`, and attempted
  `scrape-properties`.
- Post-freeze Guesty calendar GETs.

## 3. Blind-run integrity statement

Blind freeze timestamp: `2026-09-25T01:01:48-0600`.

Export path: `data/exports/testrun_300.csv`

Export SHA-256:

```text
f28264aee5455dc810e0b3875e77b7bdb76d30d3e46668c951ea499b372c87ef
```

Export row count: **0 data rows**. The file contains only the CSV header.

Integrity boundary:

- No Guesty calendar, reservation, or current-price data was inspected before this export
  was written and hashed.
- The empty export is itself the frozen blind result. Later Guesty data was used only for
  comparison and did not alter the frozen export.

## 4. Data coverage and freshness

Blind property inventory:

- Properties: 2 rows, `overlook_ridge` and `summit_haus`.
- `creekside_haven`: 0 rows.
- Seed inventory range: 2024-11-01 to 2025-04-15 for both twins.
- Blind forward inventory for 2026-09-24 to 2027-09-23: **0 rows before reveal**.
- Owned-listing discovery: exact match failed; both twins assigned same proxy listing.
- Owned-listing forward scrape: failed twice with exit code 143 and committed no forward
  rows.

Comp and market coverage:

- Curated comp members: 11 for `overlook_ridge`, 11 for `summit_haus`.
- `comp_snapshots`: 2,912 rows covering 2026-09-25 to 2027-09-22.
- Usable `ok` comp observations: 504.
- `market_snapshots`: 204 sampled stay dates, 2026-09-25 to 2027-09-22.
- Market snapshots are sampled windows, not every date in the 365-day horizon.
- Market distributions prefer the large-group tier when at least 5 sized listings exist;
  otherwise they fall back to the full validated sweep.
- Average listings per market snapshot: 26.2.
- `comp_scrape_runs`: latest run `3025808c51b6`, status `degraded`, 102/104 windows OK,
  7/14 comps matched.

Health:

- Autonomy: `SUGGEST`.
- PMS age: 0.0h in the blind seed DB, but this is scrape seed/update metadata, not a
  Guesty-synced PMS calendar.
- Comp age: about 25h at health check.
- Comp coverage: 64%.
- Pacing history: 0 days.
- Health failures: only 0d pacing history; pacing verification failed because no
  Guesty-synced properties had `pms_listing_id`.

Measurement limitations:

- Pacing and booking probability are weak and uncalibrated.
- Historical contemporaneous comp snapshots are absent for prior booking decisions.
- Full-year actual market coverage is incomplete because snapshots are sampled and two
  scrape windows timed out.
- Generic market statistics are independent of the curated comp set but are not always
  luxury/group-size pure because the scraper falls back to full-sweep distributions when
  the sized tier is too thin.

## 5. Full-year recommendation summary

Frozen recommendation count for `overlook_ridge`: **0**.

Command output:

```text
Generated 0 recommendations (2026.08.3 / rules_v2_revpan)
Autonomy granted: SUGGEST [2 gate failure(s)]
Guardrails: 0 clamped, 0 blocked/escalated
```

Observed fact:

- There were no available 2026-09-24 to 2027-09-23 `nightly_inventory` rows for
  `overlook_ridge` in the blind DB at recommendation time.

Inference:

- The engine could not price the requested window because the required property-night
  feature inputs did not exist.

Classification:

- Missing blind forward property inventory: **experiment blocker**.
- Pacing gap: **measurement limitation** and **recommendation-quality risk**.
- Degraded comp scrape: **recommendation-quality risk**.

Rounding defect check:

- No recommendation rows existed, so no post-rounding floor/ceiling overrun could occur in
  this frozen run.
- The known `round_price_conservative` ceiling-overrun defect remains a live
  **operational-risk finding** from prior evidence, but it was unobservable here.

## 6. Comparison with Guesty

Post-freeze Guesty reveal summary:

| Property | Days | Priced | Available | Booked | Blocked |
|---|---:|---:|---:|---:|---:|
| `overlook_ridge` | 365 | 365 | 347 | 13 | 5 |
| `summit_haus` | 365 | 365 | 327 | 31 | 7 |

Guesty current listed-price distribution:

| Property | n | min | p25 | p50 | p75 | p90 | max | avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `overlook_ridge` | 365 | $300 | $537 | $849 | $1,587 | $2,413 | $3,722 | $1,164 |
| `summit_haus` | 365 | $302 | $561 | $915 | $1,661 | $2,502 | $3,858 | $1,214 |

Seasonal Guesty listed-price medians for `overlook_ridge`:

| Season | n | median | p75 | max |
|---|---:|---:|---:|---:|
| shoulder_fall 2026 | 58 | $380 | $500 | $534 |
| early_winter | 24 | $698 | $863 | $1,134 |
| peak_ski | 107 | $2,035 | $2,697 | $3,722 |
| shoulder_spring | 61 | $553 | $593 | $1,027 |
| summer | 107 | $1,001 | $1,370 | $2,074 |
| shoulder_fall 2027 partial | 8 | $604 | $657 | $735 |

Comparison result:

- There are no frozen engine recommendation rows to compare night-by-night against Guesty.
- Therefore every potential divergence is **impossible to judge** as a pricing decision.
- What can be compared is data coverage: Guesty has a complete current calendar while the
  blind path did not.

## 7. Comparison with generic market averages

Representative independent generic market snapshots:

| Target date | Used sampled date | listings | p25 | p50 | p75 | p90 | Statistic type |
|---|---|---:|---:|---:|---:|---:|---|
| 2026-09-24 | 2026-09-25 | 12 | $784 | $895 | $1,167 | $1,867 | market, sized-tier if enough else full sweep |
| 2026-12-05 | 2026-12-05 | 14 | $786 | $1,245 | $1,441 | $1,743 | market, sized-tier if enough else full sweep |
| 2026-12-26 | 2026-12-26 | 219 | $430 | $593 | $892 | $1,198 | market, likely full-sweep fallback |
| 2027-04-24 | 2027-04-24 | 23 | $826 | $1,266 | $1,518 | $1,647 | market, sized-tier if enough else full sweep |
| 2027-07-10 | 2027-07-10 | 11 | $699 | $973 | $1,691 | $2,611 | market, sized-tier if enough else full sweep |
| 2027-09-23 | 2027-09-22 | 9 | $601 | $1,094 | $1,699 | $3,364 | market, sized-tier if enough else full sweep |

Monthly average market snapshots:

| Month | sampled dates | avg listings | avg p25 | avg p50 | avg p75 |
|---|---:|---:|---:|---:|---:|
| 2026-09 | 4 | 12.5 | $738 | $854 | $1,153 |
| 2026-10 | 18 | 12.9 | $602 | $826 | $1,071 |
| 2026-11 | 16 | 40.8 | $736 | $924 | $1,103 |
| 2026-12 | 18 | 85.1 | $713 | $1,046 | $1,331 |
| 2027-01 | 18 | 57.8 | $929 | $1,520 | $1,908 |
| 2027-02 | 16 | 10.9 | $1,251 | $1,813 | $2,378 |
| 2027-03 | 16 | 10.0 | $1,143 | $1,886 | $2,315 |
| 2027-04 | 15 | 19.8 | $942 | $1,296 | $1,526 |
| 2027-05 | 17 | 20.6 | $750 | $1,043 | $1,320 |
| 2027-06 | 18 | 13.6 | $760 | $1,136 | $1,544 |
| 2027-07 | 18 | 11.2 | $763 | $1,189 | $1,879 |
| 2027-08 | 17 | 16.6 | $853 | $1,185 | $1,530 |
| 2027-09 | 13 | 10.4 | $645 | $939 | $1,387 |

Curated comp statistics:

- Usable curated comp observations: 504.
- Min: $575.
- p25: $1,299.
- p50: $1,699.
- p75: $2,073.
- p90: $2,693.
- Max: $3,242.
- Average: $1,731.

Inference:

- Curated comps sit substantially above many generic market medians. That supports the
  architecture's separation between whole-market context and curated luxury comps.
- The 2026-12-26 generic market p75 of $892 is much lower than both Guesty holiday prices
  and curated comp statistics. This is likely full-market contamination and should not be
  used as a luxury ceiling.

## 8. Largest divergences

No engine-vs-Guesty price divergences can be ranked because the frozen engine output has
0 rows.

Observed post-freeze Guesty twin divergences:

| Date | Overlook | Summit | Delta |
|---|---:|---:|---:|
| 2027-08-21 | $946 | $1,698 | -$752 |
| 2027-08-20 | $956 | $1,694 | -$738 |
| 2027-08-14 | $1,005 | $1,202 | -$197 |
| 2027-08-28 | $821 | $1,008 | -$187 |
| 2027-09-12 | $768 | $626 | +$142 |

Twin delta summary across 365 Guesty calendar days:

- Mean Overlook minus Summit: -$50.
- Median: -$38.
- Nights with absolute delta greater than $50: 136.
- Nights with absolute delta greater than $250: 2.
- Maximum absolute delta: $752.

Inference:

- Guesty is not keeping the twins perfectly in lockstep today.
- The two largest divergences are late-August 2027 available nights and should be reviewed
  operationally.
- The engine's blind setup treated both twins identically only because both were assigned
  the same proxy listing. That is not evidence of genuine twin consistency; it is a data
  gap artifact.

## 9. Reasoning-quality assessment

Observed facts:

- The engine refused, effectively, to produce recommendations when no forward
  property-night features existed.
- The health gate demoted autonomy to `SUGGEST`.
- The audit failed after reveal because there were still no recommendation rows.

Inference:

- The safety posture is better than a silent recommendation based only on comps. The
  engine did not use generic market p50/p75 as a substitute for property listed price.
- The explanation layer could not be evaluated because no recommendation reasons were
  generated.
- Booking probability, expected RevPAN, elasticity/beta, leakage, and market percentile
  reasoning are all **unmeasurable with current frozen data**.

Hypothesis:

- If Guesty forward calendar were allowed during the blind phase, the engine would likely
  produce a full recommendation set. That would be a different experiment because Guesty
  current listed prices would become an input.

## 10. Audit and safety findings

Deterministic checks:

- `pytest -q`: 225 passed.
- Coverage/dependency gate: passed, total coverage 80.52%, dependency audit found no known
  vulnerabilities in installed packages.
- `production_preflight.py`: passed.
- `mypy`: failed with two advisory errors:
  - `src/pms/__init__.py:213`: dict value type mismatch.
  - `src/cli/main.py:705`: collector kwargs typing mismatch.

Findings:

| Finding | Classification | Evidence | Recommendation |
|---|---|---|---|
| Blind forward property inventory unavailable | experiment blocker | 0 forward `nightly_inventory` rows before reveal; 0 recs | Add a reliable non-Guesty blind inventory source or explicitly allow read-only Guesty calendar as an input in future non-blind runs. |
| Public owned-listing scrape failed | operational-risk finding | `scrape-properties` exited 143 twice | Add bounded timeout/reporting and resumable commits for public inventory acquisition. |
| Public owned-listing discovery used proxy | recommendation-quality risk | both twins assigned same proxy room | Do not treat proxy-listed prices as property-direct evidence. |
| Comp scrape degraded | recommendation-quality risk | 7/14 comps matched; 2 timeouts | Improve comp membership health or licensed feed fallback. |
| Pacing history absent | measurement limitation | 0 pacing days | Treat booking probability as weak/uncalibrated. |
| Demand signals absent in DB | recommendation-quality risk | audit saw 0/121 demand rows | Config calendar events still exist, but DB demand signal audit fails. |
| Historical contemporaneous comp snapshots absent | measurement limitation | no pre-decision historical comp coverage | Cannot validate historical pricing choices against contemporaneous comps. |
| `round_price_conservative` ceiling-overrun | operational-risk finding | known blocker; unobservable here due 0 recs | Classify only; do not patch in this run. |
| Unscoped selection defect / `creekside_haven` risk | operational-risk finding | known blocker; isolated DB had 0 creekside rows | Continue requiring explicit `--property overlook_ridge`; avoid unscoped Guesty sync in diagnostics. |

Guesty write count: **0**.

## 11. Stress-test results

| Scenario | Result | Rationale |
|---|---|---|
| No comps | highly sensitive | The engine can fall back to history/anchors, but this run also lacked forward inventory. |
| Stale comps | highly sensitive | Health gate can demote autonomy; recommendations would be advisory. |
| Low comp coverage | highly sensitive | Actual run was degraded at 50% comp match against expected comps. |
| Missing pacing | unsafe for probability claims | Health demoted to suggest; P(book) and RevPAN are uncalibrated. |
| Weak ceiling confidence | unmeasurable with current data | No recommendation rows were generated. |
| Elasticity beta shifted modestly | unmeasurable with current data | No recommendation rows or beta outputs. |
| High-demand dates | unmeasurable with current data | Guesty has high holiday prices, but engine produced no blind recs. |
| Orphan gaps / short windows | unmeasurable with current data | No recommendation rows or gap findings. |
| Corrupted listed prices | robust in design, untested here | Guardrail tests pass, but no frozen rows exercised this path. |
| Rounding at floor/ceiling boundaries | unsafe until fixed | Known overrun defect remains; no rows here to quantify. |
| Full-market vs luxury-filtered statistics | highly sensitive | Generic market and curated luxury comps diverge materially. |

## 12. Proposed changes ranked by impact and confidence

1. **Add a hard "no forward inventory" pre-recommend failure message.**
   - Problem: The engine generated 0 recommendations without a front-door explanation.
   - Impact: High.
   - Confidence: High.
   - Classification: experiment blocker.
   - Validation: A scoped recommend over a future range with no inventory should exit
     non-zero or print a structured "0 available nights in scope" diagnostic.

2. **Make public owned-listing inventory acquisition resumable and bounded.**
   - Problem: `scrape-properties` exited 143 twice with no committed forward rows.
   - Impact: High.
   - Confidence: Medium.
   - Classification: operational-risk finding.
   - Validation: Run a 365-day scrape and verify partial-window commits plus final report.

3. **Separate "exact owned listing" from "proxy curve" in schema and explanations.**
   - Problem: Both twins were assigned the same proxy listing, which could be mistaken for
     real property-listed price evidence.
   - Impact: High.
   - Confidence: High.
   - Classification: recommendation-quality risk.
   - Validation: Recommendations using proxy inventory must carry degraded status and reason.

4. **Require forward shadow validation before any revenue claims.**
   - Problem: Next-year prices cannot prove better revenue.
   - Impact: High.
   - Confidence: High.
   - Classification: measurement limitation.
   - Validation: Daily record Guesty live price, engine shadow recommendation, bookings,
     lead time, cancellations, occupancy, ADR, and RevPAN by season/property/lead bucket.

5. **Fix the rounding-overrun defect before relying on `audit`.**
   - Problem: Prior audit showed post-rounding prices can exceed computed ceiling.
   - Impact: Medium.
   - Confidence: High.
   - Classification: operational-risk finding.
   - Validation: Add direct boundary tests and end-to-end audit over recommendation rows.

6. **Investigate current Guesty twin divergences.**
   - Problem: Guesty has two late-August 2027 available nights where Summit exceeds
     Overlook by more than $700.
   - Impact: Medium.
   - Confidence: Medium.
   - Classification: recommendation-quality risk.
   - Validation: Determine whether deltas come from real property differences, bookings,
     owner overrides, or accidental configuration drift.

## 13. External tools worth considering

### Licensed market data feed: AirDNA or Key Data

- Specific problem: Public scrape coverage is degraded, slow, and operationally brittle.
- Researched thesis: AirDNA documents market metrics such as revenue, occupancy, and
  RevPAR/RevPAN-style benchmarking over available nights; its help center notes occupancy
  is based on booked available days and market revenue is aggregated across active earning
  listings. Source: [AirDNA revenue methodology](https://help.airdna.co/en/articles/8374548-how-does-airdna-calculate-revenue) and [AirDNA performance methodology](https://help.airdna.co/en/articles/16975794-my-performance-page-what-it-is-and-how-it-works).
- Why current repo cannot address it adequately: The repo can validate and store scrape
  outputs, but it cannot make the public provider reliable or recover blocked/timeout
  windows.
- Expected benefit: More stable market coverage, cleaner occupancy/RevPAR benchmarks, less
  dependence on proxy discovery.
- Cost and operational complexity: Subscription cost, data contract review, adapter work,
  and periodic reconciliation to existing schema.
- New failure modes: Vendor methodology opacity, lag, market-definition mismatch, API or
  export format changes.
- Validation plan: Run the feed in shadow for 60 days; compare coverage, p25/p50/p75,
  comp freshness, and recommendation deltas against scraper outputs.
- Verdict: **shadow**.

### PriceLabs Market Dashboard / Neighborhood Data

- Specific problem: Need an independent market dashboard to sanity-check generic and
  comp-set distributions.
- Researched thesis: PriceLabs states its Market Dashboards scrape Airbnb and Vrbo, and
  notes future-price medians may not move with demand because many listings are not using
  dynamic pricing. Source: [PriceLabs Market Dashboard FAQ](https://help.pricelabs.co/portal/en/kb/articles/market-dashboard-faqs).
- Why current repo cannot address it adequately: The repo has raw snapshots but not a
  mature external UI or independent vendor benchmark for "what does the market think?"
- Expected benefit: Faster operator review of outliers, market medians, and neighborhood
  demand shifts.
- Cost and operational complexity: SaaS subscription and manual/export integration unless
  API access is available.
- New failure modes: Median market prices may be stale or behaviorally biased; operator
  may overweight vendor dashboard over property-specific evidence.
- Validation plan: Compare PriceLabs p50/p75 and event lifts with repo market snapshots
  for 8-12 representative dates each month.
- Verdict: **test**.

### Beyond-style gap and moving-event logic

- Specific problem: Orphan gaps and moving events need stronger evidence and controls.
- Researched thesis: Beyond describes dynamic pricing using hyper-local market data,
  listing benchmarks, moving events, and gap adjustments; it also emphasizes that no
  single gap adjustment is universally correct. Sources: [Beyond dynamic pricing](https://support.beyondpricing.com/en_us/how-does-beyonds-dynamic-pricing-tool-work-HkF4UBiSd) and [Beyond reservation gap discounts](https://beyondpricing.com/blog/maximizing-occupancy-with-reservation-gap-discounts).
- Why current repo cannot address it adequately: The repo has rules for orphan gaps and
  events, but no forward validation of conversion lift by gap size or moving-event class.
- Expected benefit: Better treatment of short gaps and holiday/event shifts without
  overreacting to weak comps.
- Cost and operational complexity: Either SaaS subscription or substantial internal
  experiment design.
- New failure modes: Over-discounting scarce peak nights; confusing min-stay and price
  levers.
- Validation plan: Shadow gap recommendations by gap size, lead time, season, and final
  booking outcome.
- Verdict: **shadow**.

### Elasticity model upgrade

- Specific problem: Current booking probability is weak because pacing history is absent.
- Researched thesis: Hotel revenue-management literature commonly models demand as a
  price-sensitive function and optimizes revenue from that demand curve; one overview
  describes linear demand with a price slope/elasticity coefficient. Source: [Revenue
  management and dynamic pricing models in hotel business](https://www.numdam.org/item/10.1051/ro/2018001.pdf). A more recent hotel pricing paper emphasizes that demand estimation is central to optimal price selection and models dynamic elasticity. Source: [Modeling Price Elasticity for Occupancy Prediction in Hotel Dynamic Pricing](https://arxiv.org/abs/2208.03135).
- Why current repo cannot address it adequately: It needs daily pacing snapshots and enough
  realized outcomes to estimate elasticity by season/lead bucket; those data are not yet
  present.
- Expected benefit: Less reliance on static beta defaults and better confidence labeling.
- Cost and operational complexity: Several months of shadow data, feature QA, and model
  monitoring.
- New failure modes: Overfit elasticity, leakage from future booking status, unstable
  small-sample coefficients.
- Validation plan: Holdout by season and lead-time bucket; require calibration plots and
  revenue/occupancy error tracking before active use.
- Verdict: **shadow**, not adopt yet.

## Orchestrator completion

- DB path: `/tmp/testrun_overlook_ridge.db`
- Export hash: `f28264aee5455dc810e0b3875e77b7bdb76d30d3e46668c951ea499b372c87ef`
- Export row count: `0`
- Blind-freeze timestamp: `2026-09-25T01:01:48-0600`
- Guesty write count: `0`
- `creekside_haven` touched: `no`
- Every requested report section addressed: `yes`
- Forward shadow validation flagged as the recommended next experiment: `yes`
- Tracked repository files modified other than this report: `no`
