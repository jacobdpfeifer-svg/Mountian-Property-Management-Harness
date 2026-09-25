# TESTRUN 312 Northwoods (`summit_haus`)

**DB path:** `/tmp/testrun_summit_haus.db`  
**Property:** 312 Northwoods / `summit_haus`  
**Run window:** 2026-09-24 through 2027-09-23 inclusive  
**Report date:** 2026-09-25 UTC  

## 1. Executive verdict

**Verdict: experiment blocked for a true blind full-year recommendation run.** The engine did not produce a defensible blind recommendation set for 312 Northwoods because the permitted non-Guesty inputs had no owned forward inventory for the 2026-09-24..2027-09-23 window. The frozen blind output therefore contains **0 recommendation rows**.

Observed facts:

- The blind DB was initialized at `/tmp/testrun_summit_haus.db` and seeded only from scrape-native CSV inputs.
- It contained 2 properties, 332 historical inventory rows, 22 comp-set members, 2,576 comp snapshots, and 184 market snapshots after a partial independent scrape.
- `nightly_inventory` for `summit_haus` covered only 2024-11-01..2025-04-15 before Guesty reveal, so there were 0 target-window owned nights to price.
- The scoped blind command generated 0 recommendations and the scoped audit failed on inventory, comp coverage, demand signals, and missing recommendations.

Inference:

- This run can evaluate acquisition, health gates, scoping, and post-reveal engine behavior, but it cannot validate that the frozen blind recommendation set is comp-grounded or revenue-superior. There is no blind recommendation set to compare.

Highest-value diagnostic finding:

- In a post-freeze copy of `data/wp_pricing.db`, scoped to `summit_haus`, the engine generated 325 current available-night recommendations. Those recommendations are advisory only and are **not** part of the blind frozen set. They show the same structural summer/shoulder concern as the prior audit: summer and shoulder recommendations are frequently below independent market p25/p50, while booking probabilities are weak/uncalibrated and ceilings have very low confidence.

## 2. Exact commands and data sources used

Deterministic checks:

```bash
PYTHONPATH="/tmp/wpprice_deps_1790313044:$PYTHONPATH" /opt/homebrew/bin/python3.12 -m pytest -q
PYTHONPATH="/tmp/wpprice_deps_1790313044:$PYTHONPATH" /opt/homebrew/bin/python3.12 -m mypy
PYTHONPATH="/tmp/wpprice_deps_1790313044:$PYTHONPATH" /opt/homebrew/bin/python3.12 scripts/production_preflight.py
PYTHONPATH="/tmp/wpprice_deps_1790313044:$PYTHONPATH" /opt/homebrew/bin/python3.12 -m pytest --cov=src --cov-report=term-missing -q
PYTHONPATH="/tmp/wpprice_deps_1790313044:$PYTHONPATH" /opt/homebrew/bin/python3.12 -m vulture src scripts --min-confidence 80
PYTHONPATH="/tmp/wpprice_deps_1790313044:$PYTHONPATH" /opt/homebrew/bin/python3.12 -m pip_audit
```

Blind data acquisition:

```bash
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db init-db
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db seed-scrape
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db discover-comps --date 2026-12-18 --min-bedrooms 5 --min-sleeps 14 --limit 20
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db discover-comps --date 2026-12-04 --min-bedrooms 5 --min-sleeps 14 --limit 20
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db discover-comps --date 2027-04-24 --min-bedrooms 5 --min-sleeps 14 --limit 20
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db discover-comps --date 2027-07-17 --min-bedrooms 5 --min-sleeps 14 --limit 20
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db discover-properties --property summit_haus --date 2026-12-18,2027-07-17 --min-price 300
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db scrape-comps --start 2026-09-24 --horizon 365
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db health --property summit_haus
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db snapshot --verify --since 2026-09-24
```

Blind run and freeze:

```bash
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db recommend --property summit_haus --from 2026-09-24 --to 2027-09-23 --limit 500 --technical
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db export --property summit_haus --from 2026-09-24 --to 2027-09-23 -o /tmp/testrun_312.csv
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus.db audit --property summit_haus --from 2026-09-24 --to 2027-09-23
```

Note: I exported the frozen blind CSV to `/tmp/testrun_312.csv`, not `data/exports/testrun_312.csv`, because the absolute restriction said the only repository file to create is this report.

Post-freeze reveal/diagnostic:

```bash
# opened read-only for inspection
sqlite3-compatible read-only connection to file:data/wp_pricing.db?mode=ro

# copied to /tmp for scoped post-reveal diagnostics
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus_reveal.db recommend --property summit_haus --from 2026-09-24 --to 2027-09-23 --limit 500 --technical
/opt/homebrew/bin/python3.12 -m src.cli.main --db /tmp/testrun_summit_haus_reveal.db audit --property summit_haus --from 2026-09-24 --to 2027-09-23
```

Data sources:

- Repository docs/config listed in the prompt.
- Blind DB from `seed-scrape`, independent `discover-comps`, and partial independent `scrape-comps`.
- Guesty reveal from existing `data/wp_pricing.db`, opened read-only and queried only after the blind export hash was recorded.
- Post-reveal diagnostics from a copied DB at `/tmp/testrun_summit_haus_reveal.db`.

## 3. Blind-run integrity statement

Observed facts:

- Blind freeze timestamp: **2026-09-25T05:23:42Z**
- Frozen export path: `/tmp/testrun_312.csv`
- SHA-256: `f28264aee5455dc810e0b3875e77b7bdb76d30d3e46668c951ea499b372c87ef`
- Data row count: **0**
- File size: 237 bytes
- Scoped command: `recommend --property summit_haus ...`

Integrity statement:

- I did not inspect Guesty prices, reservations, calendar rates, or the retrospective before this hash was recorded.
- The frozen set was not altered after hashing.
- The post-reveal recommendation run is separate and must not be treated as blind evidence.

## 4. Data coverage and freshness

Blind DB coverage:

| Table | Rows |
|---|---:|
| `properties` | 2 |
| `nightly_inventory` | 332 |
| `comp_set_members` | 22 |
| `comp_snapshots` | 2,576 |
| `market_snapshots` | 184 |
| `price_recommendations` | 0 |
| `pacing_snapshots` | 0 |
| `demand_signals` | 0 |

Blind owned inventory:

- `summit_haus`: 166 rows, 2024-11-01..2025-04-15.
- Target-window owned inventory: **0/365 nights**.
- Classification: **experiment blocker**.

Blind scrape coverage:

- `scrape-comps --horizon 365` was interrupted after prolonged silence while inside an external `pyairbnb.search_all` request.
- It left `comp_scrape_runs.status='running'`, `finished_at=NULL`, and `windows_attempted=0`, even though rows had been committed.
- `market_snapshots`: 184 rows / 184 distinct dates, 2026-09-25..2027-08-11.
- `comp_snapshots`: 434 `ok`, 2,142 `unavailable`.
- Health reported comp coverage **55%**, below the 60% threshold.
- Classification: **operational-risk finding** and **measurement limitation**.

Generic market benchmark:

- Source: independent `market_snapshots`, not curated-comp medians.
- Scope: whole-market scrape output after group-size/live listing filters used by the provider; not a validated curated luxury comp set.
- Average sample size: 27.6 listings per sampled stay date.
- Average p25/p50/p75: **$871 / $1,266 / $1,613**.
- Min observed p25: **$272**.
- Max observed p90: **$7,004**, showing outlier sensitivity.
- Coverage is partial: no market rows after 2027-08-11 and no complete 365-day market coverage.
- Classification: **measurement limitation** and **recommendation-quality risk**.

Pacing:

- `snapshot --verify --since 2026-09-24` failed: no Guesty-synced properties in the blind DB.
- Health reported 0 pacing days; booking probability must be treated as **weak / uncalibrated**.
- Classification: **measurement limitation**.

## 5. Full-year recommendation summary

Blind frozen run:

- Recommendations generated: **0**.
- Cause: no target-window owned inventory in the permitted blind inputs.
- No unavailable dates were manually filled.

Post-reveal scoped diagnostic, not blind:

- Latest scoped run id: `fcc8ddba903e`.
- Recommendations for available nights: **325**.
- Guesty reveal inventory had 363 target-window nights for `summit_haus`, of which 325 were available and 38 booked.
- Two target-window dates were absent from `data/wp_pricing.db` inventory; the reveal DB covered 2026-09-24..2027-09-21.

Post-reveal latest-run summary:

| Metric | Value |
|---|---:|
| Avg Guesty listed | $1,195 |
| Avg engine recommendation | $1,004 |
| Avg engine delta | -$191 / -11.5% |
| Min / max recommendation | $335 / $3,195 |
| Escalated nights | 59 |
| Guardrailed nights | 189 |
| Low-confidence ceiling nights | 325 |
| No-action rounding over-ceiling nights | 12 |

Season summary, post-reveal diagnostic:

| Season | Nights | Avg Guesty | Avg rec | Avg delta | Avg ceiling | Escalated |
|---|---:|---:|---:|---:|---:|---:|
| early_winter | 20 | $795 | $694 | -11.8% | $618 | 3 |
| peak_ski | 97 | $2,106 | $1,675 | -17.7% | $1,123 | 53 |
| shoulder_fall | 46 | $431 | $416 | -2.7% | $591 | 2 |
| shoulder_spring | 61 | $600 | $553 | -7.4% | $618 | 0 |
| summer | 101 | $1,105 | $961 | -12.1% | $676 | 1 |

Inference:

- The engine is cautious relative to Guesty in most seasons, especially ski and summer.
- Because all post-reveal ceiling confidences are 0.10 and all booking probabilities are uncalibrated, this caution is not yet defensible as a validated demand response.

## 6. Comparison with Guesty

Observed facts after freeze:

- Read-only production DB contains four properties, including `creekside_haven` with `owner_id=NULL`.
- I did not run `sync-guesty`, because it would likely touch all live listings.
- `summit_haus` reveal inventory: 363 target-window rows, 363 priced, 325 available, 38 booked.

Classification of post-reveal divergences:

- Peak ski large cuts: **potentially justified but dependent on weak assumptions** / sometimes **likely underpriced**. Examples include February 2027 nights where Guesty is $3,096-$3,795 and the engine recommends $1,855, while the engine ceiling is only about $904 and confidence is 0.10. The engine escalates many of these, which is correct.
- Summer high Guesty dates: **likely underpriced or impossible to judge**. July 2027 Guesty prices around $1,400-$2,122 are cut toward $1,215-$1,855, while the engine’s own ceiling often sits near $665-$710 and expected booking probability is frequently 0.1%. The guardrail prevents a full collapse but the underlying ceiling/elasticity story is weak.
- Shoulder spring/fall vs Guesty: **likely underpriced against market; weakly justified against own-history**. The engine stays near Guesty in fall but both are far below the independent market p25 where market rows exist.
- No blind recommendation can be classified against Guesty because the blind set has 0 rows.

## 7. Comparison with generic market averages

Comparison uses the independent blind `market_snapshots`, joined by stay date, against the post-reveal diagnostic recommendations. This is not a curated comp comparison.

Overall where market rows existed:

- Matched dates: 163.
- Recommendations below market p25: 83.
- Recommendations inside market IQR: 66.
- Recommendations above market p75: 14.
- Avg recommendation vs market p50: -$208.
- Avg recommendation / market p50: 0.95.
- Avg Guesty listed / market p50: 1.11.

By season:

| Season | Matched dates | Avg market p25 | Avg market p50 | Avg market p75 | Avg Guesty | Avg rec | Below p25 |
|---|---:|---:|---:|---:|---:|---:|---:|
| early_winter | 11 | $810 | $1,070 | $1,295 | $862 | $749 | 7 |
| peak_ski | 58 | $1,037 | $1,601 | $2,038 | $2,156 | $1,690 | 6 |
| shoulder_fall | 21 | $669 | $882 | $1,092 | $411 | $409 | 21 |
| shoulder_spring | 34 | $847 | $1,156 | $1,405 | $609 | $566 | 34 |
| summer | 39 | $861 | $1,249 | $1,681 | $1,281 | $1,108 | 15 |

Inference:

- The generic market benchmark is noisy and sometimes thin, but it argues against treating the engine’s summer/shoulder discounts as proven. Shoulder spring is the clearest concern: every matched spring recommendation was below market p25.

## 8. Largest divergences

Largest post-reveal cuts vs Guesty:

| Date | Guesty | Rec | Ceiling | Action | Classification |
|---|---:|---:|---:|---|---|
| 2027-02-12 | $3,795 | $1,855 | $904 | sanity_ceiling | likely underpriced / weak ceiling |
| 2027-02-13 | $3,747 | $1,855 | $904 | sanity_ceiling | likely underpriced / weak ceiling |
| 2027-02-14 | $3,726 | $1,855 | $904 | sanity_ceiling | likely underpriced / weak ceiling |
| 2027-07-10 | $2,122 | $1,855 | $695 | sanity_ceiling | likely underpriced / summer ceiling weak |
| 2027-07-04 | $2,010 | $1,760 | $668 | clamped_decrease | likely underpriced / market-dependent |

Largest post-reveal raises vs Guesty:

| Date | Guesty | Rec | Ceiling | Action | Classification |
|---|---:|---:|---:|---|---|
| 2027-01-05 | $1,259 | $1,410 | $2,366 | peak_blackout | potentially justified but escalated |
| 2027-01-13 | $1,291 | $1,445 | $2,366 | peak_blackout | potentially justified but escalated |
| 2027-01-12 | $1,002 | $1,120 | $2,366 | peak_blackout | potentially justified but escalated |
| 2026-11-17 | $347 | $385 | $567 | peak_blackout | small raise, correctly escalated |

Largest gaps below independent market p50:

| Date | Guesty | Rec | Market p25 | p50 | p75 | Classification |
|---|---:|---:|---:|---:|---:|---|
| 2027-04-06 | $588 | $535 | $974 | $1,359 | $1,723 | likely underpriced |
| 2027-04-07 | $599 | $545 | $974 | $1,359 | $1,723 | likely underpriced |
| 2026-12-08 | $593 | $545 | $821 | $1,347 | $1,448 | likely underpriced |
| 2027-08-10 | $849 | $725 | $1,095 | $1,481 | $1,562 | likely underpriced |
| 2027-04-28 | $517 | $485 | $864 | $1,240 | $1,442 | likely underpriced |

## 9. Reasoning-quality assessment

Observed facts:

- Post-reveal reason counts: `thin_history` 323, `revpan_optimum` 319, `guardrail` 189, `base_compose` 136, `ceiling_gap` 8.
- All post-reveal recommendations had ceiling confidence 0.10.
- Booking probability averages were extremely low in peak ski, spring, and summer: peak ski 1.0%, shoulder spring 1.2%, summer 1.1%.

Inference:

- The engine is explainable, but the explanations are dominated by thin-history and guardrail mechanics rather than strong comp or calibrated demand evidence.
- The summer/shoulder underpricing question remains unresolved. The observed pattern is more consistent with weak ceilings and elasticity defaults suppressing prices than with proven soft demand.
- Deference to Guesty/current listed price prevents the engine from fully following its low ceilings downward, but that is a guardrail against bad evidence, not evidence that the engine is correct.

Hypothesis:

- `summer: -1.10` and `shoulder_spring/fall: -1.70` are too strong when combined with weak ceilings and incomplete pacing. They push the RevPAN optimum low, then move caps hide the severity by limiting the final nightly cut.

## 10. Audit and safety findings

Findings:

1. **Blind owned inventory unavailable** — **experiment blocker**. No permitted non-Guesty target-window owned calendar existed, so the blind recommendation set is empty.
2. **`creekside_haven` exists in production DB** — **operational-risk finding**. The current code includes `locked_portfolio_property_ids()` and unscoped default scoping now appears designed to avoid extras, but the property is still present and any all-listing sync/reporting operation must be treated carefully.
3. **`round_price_conservative` ceiling-overrun verified** — **recommendation-quality risk**. In the post-reveal latest run, 12 no-action recommendations exceeded their own ceiling by up to $4.86 solely because rounding moved toward the listed price. Direct reproduction: `round_price_conservative(691.0, 900.0, round_to=5) == 695.0`.
4. **Move-cap/sanity prices can sit far above computed ceiling** — **recommendation-quality risk**. 180 additional post-reveal over-ceiling rows were due to `clamped_decrease`, `sanity_ceiling`, or `peak_blackout`; some are intentionally allowed by audit logic, but they reveal that the computed ceiling is not operationally trusted on high-listed nights.
5. **Pacing history incomplete** — **measurement limitation**. Blind DB had 0 pacing days; production reveal health had pacing gaps. Booking probability is weak/uncalibrated.
6. **No historical contemporaneous comp snapshots for outcomes** — **measurement limitation**. This prevents retrospective proof that comp-grounded pricing would have converted.
7. **Full 365-day market coverage absent** — **measurement limitation**. Partial independent market rows covered 184 dates through 2027-08-11, not the complete run window.
8. **Scraper run observability/timeout weakness** — **operational-risk finding**. The 365-day scrape stayed silent for several minutes, was interrupted inside the external request layer, and left a `running` run row despite committed snapshots.
9. **Mypy still has 2 errors** — **low-priority improvement** for this diagnostic, because tests/preflight passed and the errors match prior known typing cleanup.

Deterministic check results:

| Check | Result |
|---|---|
| `pytest -q` | 225 passed |
| coverage | 80.52%, passed 70% threshold |
| production preflight | pass |
| mypy | fail: 2 errors |
| vulture | pass/no output at 80% confidence |
| pip-audit | pass/no known vulnerabilities |

## 11. Stress-test results

| Scenario | Result | Notes |
|---|---|---|
| no comps | unsafe | Health demotes, but engine can still emit low-confidence suggestions if owned inventory exists. |
| stale comps | highly sensitive | Production reveal health failed comp staleness; comp-derived confidence should remain advisory. |
| low comp coverage | highly sensitive | Blind health failed at 55% coverage. |
| missing pacing | unsafe for demand claims | Booking probability must be labeled weak/uncalibrated. |
| weak ceiling confidence | highly sensitive | All post-reveal recs had 0.10 confidence; recommendations lean heavily on deference/move caps. |
| elasticity beta shifted both directions | unmeasurable with current data | No calibrated forward booking outcomes; hypothesis only. |
| high-demand dates | robust operationally, weak economically | Peak blackout/escalate works, but ceilings are often too weak to justify the recommended magnitude. |
| orphan gaps / short windows | unmeasurable with current data | No blind forward owned inventory; no reliable gap analysis in frozen set. |
| corrupted/implausible listed prices | partially robust | `sanity_ceiling` catches extremes, but recommendations can still sit far above computed ceiling. |
| rounding at floor/ceiling boundaries | unsafe | Verified no-action ceiling overruns up to $4.86. |
| full-market vs luxury-filtered statistics | highly sensitive | Independent market rows are useful but thin/outlier-prone; curated luxury comps are not enough alone. |

## 12. Proposed changes ranked by impact and confidence

1. **Require a blind owned-inventory source before diagnostic runs** — impact high, confidence high. Problem: without non-Guesty owned forward inventory, the blind run freezes 0 rows. Current repo cannot solve this because `seed-scrape` has historical/sample inventory only and owned Airbnb discovery was a score-1 proxy. Expected benefit: real blind recommendations. Cost: add or license independent owner calendar scrape, or export a non-price availability skeleton. Failure mode: accidental Guesty leakage if source is not isolated. Validation: run a blind DB with 365 `summit_haus` target-window inventory rows and hash nonzero export. Verdict: **test**.
2. **Fix rounding to clamp after conservative rounding** — impact high, confidence high. Problem: no-action recommendations exceed ceilings. Current code rounds after guardrails without a final bound clamp. Expected benefit: audit becomes meaningful. Cost: small code change plus tests. Failure mode: $5 grid behavior near bounds changes. Validation: reproduce 12 failing dates and direct function examples. Verdict: **adopt** after separate authorized fix.
3. **Separate computed economic ceiling from move-cap-limited operational recommendation** — impact high, confidence medium. Problem: many recommendations are far above computed ceilings due to move caps, while reasons still present the low ceiling. Expected benefit: clearer operator trust. Cost: reporting/schema work. Failure mode: more complicated owner-facing output. Validation: add fields for `model_price`, `bounded_price`, `rounded_price`, and `ceiling_breach_reason`. Verdict: **test**.
4. **Calibrate summer/shoulder elasticity with forward shadow data before handle mode** — impact high, confidence high. Problem: summer/shoulder outputs look suppressed, but no outcome data proves whether that is right. Current repo lacks clean pacing/outcome history. Expected benefit: avoid systematic underpricing of the twins. Cost: one season of shadow measurement. Failure mode: slow feedback cycle. Validation: evaluate bookings by season, lead-time bucket, and price-distance bucket. Verdict: **shadow**.
5. **Add scrape run deadlines and progress logging** — impact medium, confidence high. Problem: long scrape commands are opaque and can leave stale `running` rows. Expected benefit: safer automation. Cost: moderate CLI/provider plumbing. Failure mode: aborting slow but recoverable requests. Validation: forced timeout test leaves `failed`/`degraded`, not `running`. Verdict: **adopt**.
6. **Use independent licensed market data for generic benchmarks** — impact medium/high, confidence medium. Problem: current scraper is thin, ToS-sensitive, and outlier-prone. Expected benefit: stable p25/p50/p75 and historical occupancy/rate context. Cost: subscription and integration. Failure mode: black-box/vendor mismatch for luxury homes. Validation: shadow vendor percentiles against scraped and realized bookings. Verdict: **shadow**.

## 13. External tools worth considering

**PriceLabs Market Dashboards / Portfolio Analytics**  
Problem addressed: independent forward market percentiles, comp dashboards, and pacing context.  
Research thesis: PriceLabs describes Market Dashboards as competitive benchmarking and market intelligence for STR/MTR operators, and says comp sets can flow into dynamic pricing and analytics ([PriceLabs Market Dashboards](https://www.hello.pricelabs.co/market-dashboards/), [PriceLabs KB](https://help.pricelabs.co/portal/en/kb/pricelabs/market-dashboards/market-dashboard)).  
Why current repo is inadequate: the scraper produced partial coverage, no complete 365-day market horizon, and outliers.  
Expected benefit: stable market p25/p50/p75 and an external check against the repo’s own comp layer.  
Cost/complexity: subscription, property mapping, recurring export/API process.  
New failure modes: vendor definitions may not match luxury 5-bedroom twins; dashboards can become a second black box.  
Validation plan: shadow PriceLabs market percentiles against internal recommendations and Guesty outcomes for one season.  
Verdict: **shadow**.

**AirDNA data feed / MarketMinder / Property Performance Data**  
Problem addressed: historical and forward market performance, occupancy/rate distributions, and less fragile market data.  
Research thesis: AirDNA claims broad daily coverage across Airbnb/Vrbo/Booking.com and publishes accuracy/methodology claims, including de-duplication and property performance data ([AirDNA accuracy](https://www.airdna.co/airdna-accuracy), [AirDNA data model](https://www.airdna.co/how-it-works), [AirDNA occupancy methodology](https://help.airdna.co/en/articles/8062178-how-does-airdna-calculate-occupancy-rate)).  
Why current repo is inadequate: no contemporaneous historical comp snapshots, incomplete pacing, and fragile scrape collection.  
Expected benefit: independent historical occupancy/rate priors for calibration and market percentiles.  
Cost/complexity: paid feed, data-contract work, mapping/bedroom/sleeps filters.  
New failure modes: inferred occupancy may be wrong for blocked owner stays; vendor data may lag or smooth local luxury outliers.  
Validation plan: compare AirDNA market occupancy/ADR to actual Guesty bookings by season and lead time.  
Verdict: **shadow**.

**Beyond market insights / clustering methodology**  
Problem addressed: comp clustering and human-reviewed market segmentation.  
Research thesis: Beyond describes market insights sourced from public sites and discusses clustering large volumes of Airbnb/day-level price data with analyst review ([Beyond market insights](https://support.beyondpricing.com/en_us/how-do-i-use-the-market-insights-tab-to-understand-demand-trends-in-my-market-rk4VuSoS_), [Beyond clustering](https://beyondpricing.com/blog/unlocking-the-power-of-data-how-beyond-s-clustering-strategy-upgrades-vacation-rental-pricing)).  
Why current repo is inadequate: curated comp sets are hand-maintained and the generic market benchmark is too thin in some seasons.  
Expected benefit: independent clustering sanity check for the 5bd luxury peer set.  
Cost/complexity: vendor onboarding/export, reconciling Beyond clusters with local rules.  
New failure modes: analyst/cluster choices are not fully reproducible; may overfit to platform-visible listings.  
Validation plan: compare Beyond cluster medians to curated comps and realized bookings without feeding them into pricing initially.  
Verdict: **test**.

**Ski-market snow/demand research as a calibration prior**  
Problem addressed: whether snow and ski-market signals should move ceilings/elasticity.  
Research thesis: Parthum and Christensen model winter recreation behavior using 12 million short-term rental transactions plus daily weather/snowpack and estimate ski-market demand elasticities; CoStar/STR’s ski-resort analysis argues hotel demand can be more stable than snowfall alone when ski conditions remain adequate ([A Market for Snow](https://pubmed.ncbi.nlm.nih.gov/38482074/), [ScienceDirect summary](https://www.sciencedirect.com/science/article/pii/S0095069622000195), [CoStar/STR ski demand article](https://www.costar.com/article/1693578996/mild-winter-cant-put-freeze-on-ski-resorts)).  
Why current repo is inadequate: current SQI and elasticity settings are policy priors without enough property-level outcome calibration.  
Expected benefit: better prior ranges for SQI and season-specific elasticity, especially drought vs normal snowpack.  
Cost/complexity: research translation, not direct plug-in data.  
New failure modes: applying aggregate ski-market elasticity to one luxury home can mislead.  
Validation plan: shadow SQI-adjusted vs non-SQI recommendations and compare conversion by snowpack regime.  
Verdict: **test**.

**STR/CoStar hotel benchmark data**  
Problem addressed: lodging-market context beyond Airbnb supply, especially compression/high-demand weeks.  
Research thesis: CoStar/STR publishes lodging performance and market-demand data; Beyond also notes hotel pricing can inform the upcoming year when vacation-rental signals are sparse.  
Why current repo is inadequate: Airbnb-only scraping misses hotel compression and cross-lodging substitution.  
Expected benefit: independent high-demand and low-demand validation.  
Cost/complexity: paid data, market matching, different unit economics.  
New failure modes: hotel ADR is not directly comparable to 5-bedroom homes.  
Validation plan: use as a directional signal only; do not price directly from hotel ADR.  
Verdict: **test**.

## Forward shadow validation

This report cannot prove the engine beats Guesty on revenue. The recommended next experiment is a forward shadow run:

- Keep Guesty live.
- Record the engine recommendation daily.
- Record bookings, lead time, cancellations, occupancy, ADR, realized RevPAN, and price distance from Guesty.
- Evaluate by season, property, lead-time bucket, and price-distance bucket.

This is especially important for the twins and for the summer/shoulder question.

## Orchestrator completion

- DB path: `/tmp/testrun_summit_haus.db`
- Frozen blind export: `/tmp/testrun_312.csv`
- Export SHA-256: `f28264aee5455dc810e0b3875e77b7bdb76d30d3e46668c951ea499b372c87ef`
- Export row count: `0`
- Blind-freeze timestamp: `2026-09-25T05:23:42Z`
- Every requested report section was addressed.
- No Guesty write adapter was called; no `push --adapter guesty` was run.
- No unscoped `recommend`, `audit`, `export`, or `push` was run.
- No command was run that knowingly touched `creekside_haven`; production reveal used read-only inspection and a copied DB with scoped `summit_haus` commands only.
- I did not modify policy YAML, portfolio YAML, schemas, production data, or tracked repository files other than creating this report.
