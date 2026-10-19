# R6: Which data is worth the most, and how to squeeze it

Output: `docs/research/deep_2026-10/R6_data_value_ranking.md`
Inputs: `R5_data_stream_universe.md`, `R5_catalog.csv`, `R7_winter_park_demand_drivers.md` and their
reviews.

## Question

Of all the candidate streams, which ones would add the most **owner net profit** if the engine used
them, and how do we prove that with three homes and thin data? Then, for the top streams: what is
the design that extracts the maximum value from each?

## Part A: the ranking method (research first, then design)

Research how mature RM and forecasting teams decide which data to buy or build:

- **Value of information (VOI)** and expected value of perfect and sample information.
- Feature importance done right: permutation, SHAP and its pitfalls, and the information
  coefficient as our promotion ladder uses it.
- Granger causality and lead-lag analysis.
- Forecast-error reduction → revenue mapping. Airline studies link forecast accuracy to revenue;
  find them (for example Weatherford & Belobaba; Pölt).
- Nowcasting literature (Choi & Varian, Google Trends for tourism demand forecasting; tourism
  forecasting competition, Athanasopoulos et al. 2011).
- Multiple-testing and data-snooping controls when screening 80+ streams (White's reality check,
  Hansen's SPA, false discovery rate).
- **Pooling to beat thin data.** Use market-level targets (market occupancy, lodging tax, comp
  availability) instead of our 100 bookings. Hierarchical models. Transfer from other mountain
  towns.

Then **design our protocol**. Cover:
- the target variables (market pace, comp availability change, our booking hazard, achieved
  price)
- the evaluation (rolling-origin backtest; leakage rules matching `src/leakage`)
- the metric chain: forecast lift → price decision change → simulated owner-net delta in
  `proving_ground_exam`
- the thresholds, and how this plugs into the existing promotion ladder
  (`config/policies/signals.yaml`)

## Part B: apply it now, as far as the data allows

- Score every A- and B-tier stream from R5 on: expected profit impact (mechanism × effect size
  from literature × how often it changes our decision), confidence, cost, effort, and whether it
  is already partly in the repo.
- Where the repo has data (signals store, comp snapshots, nightly inventory as per-home
  aggregates, opened read-only), run the cheapest real lead-lag checks. Report honestly, with
  sample sizes. Do not read guest-level fields.
- Produce the **top 10 ranked streams**, with a value-tier rationale.

## Part C: maximum utilization design for the top 3–5 streams

For each winner: what exactly the engine should compute from it (features), where it enters (base
level, elasticity, pace target, ceiling, min-stay, gap logic), how it interacts with existing
signals, its failure modes (stale or missing data, which must fail safe), how to simulate it in
`proving_ground_exam` (does the market sim need a new latent driver?), and the field measurement
plan given the ~33% MDE problem.

**Note:** comp-market data quality (scraper at 67% failure) may itself be the highest-value
"stream". Evaluate fixing or replacing it (paid feeds vs scraper hardening) on the same scale.
