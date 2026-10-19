# R6: Which data is worth the most, and how to squeeze it

Date: 2026-10-17 (work started 2026-10-16). Access date for every web source: 2026-10-16 unless stated.
Status: COMPLETE after ranking, design, review and fix pass.

Inputs: `R5_data_stream_universe.md`, `R5_catalog.csv` (121 streams; 17 A, 38 B), `R7_winter_park_demand_drivers.md`,
R1–R4 dossiers, and the reviews in `reviews/` (R1, R2, R3, R4, R5, R7). Scratch scripts live outside the repo in
`/private/tmp/wp_research/r6/` (run with `python3 -I`). The operator database was opened read-only
(`mode=ro&immutable=1`); only per-home or portfolio aggregates of night status, public comp tables and signal
tables were read. No booked revenue, guest field or Guesty id appears in this file.

## 0. Summary

Comp-data repair and persisted calendar availability are the highest-value prerequisite. After that,
pooled market pace, corrected stay-level own pace, and snow/resort/calendar state dominate the
credible near-term opportunity. Gas, geopolitics and search are shadow/scenario inputs, not fitted
daily coefficients. Part A sets out the ranking method, Part B applies it (scores, the top 10 and
the empirical checks), and Part C gives fail-safe designs for the top five. (Section order was
consolidated on 2026-10-19; the fix pass had left Parts B and C above Part A and five empty stub
sections at the end. No text was changed in the move.)

## 1. Corrections inherited from the reviews (applied throughout)

Where a review contradicts a number the inputs rely on, this dossier uses the corrected figure. Each
correction below changes a score in Part B.

| # | Original claim | Correction (source) | Effect on this ranking |
|---|---|---|---|
| C1 | First-party median lead time 15 days (R4, dossier 01) | Not a winter figure: the sample is mostly Jun–Dec 2026 and right-censored. AirROI's 14-market panel puts **Winter Park's 2025-26 winter lead time at about 72 days** (vendor, scraped; [AirROI 2026-07-29](https://airroi.com/blog/ski-market-winter-2026-2027-booking-pace), via R4 review §5) | Season-level and far-out streams (snowpack state, pass sales, school calendars, market OTB) act on more of the booking curve than R4 assumed. Short-range streams (7-day snow forecast, road closures) act on a smaller share of nights. |
| C2 | Comp calendar availability is "captured" (R4 §6) | **Not persisted.** `providers.py` fetches `available` and `min_nights`, but `_enrich_min_nights` stores only `min_nights`; `comp_snapshots.available` encodes presence in a search sweep, which conflates "booked" with "not ranked in this tile" (R4 review R-1) | Every comp-fill, peer-pickup or comp-availability stream needs a code change first ("persist per-day calendar availability"). Effort is raised one step for those streams, and the lead-lag check in §B.3 uses sweep presence and says so. |
| C3 | No comp-movement signal exists (R4) | `src/signals/comp_movement.py` already writes a 14-day median listed-price-lift `demand_signals` row on each scrape (R4 review R-2) | Comp price movement is partly in the repo; it is tested in §B.3. |
| C4 | A01 US-40 closures are "already live" (R5) | The collector calls a COtrip URL that now returns an HTML app shell; the parser finds no keywords and stores `berthoud_closed = 0` as `QUALITY_OK`. It **cannot ever report a closure** (R5 review R-1) | A01 is scored as "not built"; its first task is a working feed. A silent false-negative that passes freshness checks is the worst failure mode a signal can have. |
| C5 | `weather.wind_gust_max_mph` is in mph | Open-Meteo's default unit is km/h; the ×2.237 conversion overstates gusts about 3.6× (R5 review R-2; reviewer reading, not run live) | Wind/lift-hold streams (W03/W04) carry a fix-first cost. |
| C6 | Parthum & Christensen Colorado 0.135 is a season-level SWE elasticity, so 60% of normal SWE ≈ −7% revenue (R5) | It is a **within-property-month, day-to-day** elasticity to **resort-reported snow depth**, on **Aug 2014–May 2017** data (STALE). Month fixed effects absorb season-level variation, so it does not size a bad-season effect (R5 review F-1) | The snow prior is not used as a season multiplier. Season-level snow evidence comes from R7's tax and traffic regressions and the 2025-26 outcome (C7). |
| C7 | (none) | AirROI: in the 2025-26 drought, Winter Park **occupancy fell 44.9% → 35.8% while ADR rose 22.2%** (RevPAR −4.7%, supply +9.9%) (R4 review §5) | In a bad snow year the market *held rate and lost occupancy*. This is direct evidence that the engine's SQI drought price cut (0.78 multiplier at SQI 0.62, `conditions.yaml`) has the wrong size and possibly the wrong lever (R4 review R-8). It raises the value of a *correctly sized* snow-state stream and lowers the value of the current prior. |
| C8 | Snow literature: only Parthum & Christensen | Töglhofer et al. 2011 (*Climate Research* 46:1–14, Austrian overnight stays: 0.6–1.9% per SD of snow, smaller with snowmaking), Shih et al. 2009 (*JTR*), Malasevska (forecast-driven midweek substitution), HVS 2015 (drive-to resorts show within-season co-movement) (R5 review F-2) | Supports a modest, within-season snow effect at drive-to resorts, consistent with R7's +1.3–2.2% traffic per inch of SWE anomaly. |
| C9 | I-70 tunnel counts test H4 for Winter Park (R5) | The tunnel is **west** of the Empire exit, so it measures the substitute corridor. I-70 **Denver–Empire** closures (Floyd Hill, overnight closures to mid-December 2026) hurt Winter Park too (R5 review F-3) | X04's substitution flag must be segment-specific, or it fires the wrong way. |
| C10 | H4 monthly n = 134 | Effective n ≈ 23 seasons (85% of YoY gas variance is between seasons). Defensible wording: **no winter effect detected; bounded at about ≤4% of access traffic for a 30% gas rise** (R7 review §2) | Gasoline stays a low-value stream. |
| C11 | Luxury January comp median $1,684 (R7, from `market_snapshots`) | `market_snapshots` is the broad sweep (231 listings in September, 11 in January). The 22-comp set gives a **January median of $2,073** (p90 $3,098, n = 272 quotes) (R7 review §1) | The comp tier sits closer to the homes' real rates than R7 said, which raises the value of a working comp anchor. |
| C12 | Antitrust: Gibson v. Cendyn is the appellate state of play (R4) | **Cornish-Adebiyi v. Caesars** (3d Cir., 2026-07-29) reinstated an algorithmic-pricing case built on nonpublic data fed into a shared algorithm (R4 review §5) | Pooled nonpublic PM data (DestiMetrics comparative reports, Key Data co-op) carries legal risk if it feeds prices. Market OTB is scored as a **forecast covariate from published aggregates only**, and the risk is in its confidence score. |
| C13 | DestiMetrics "free to data-submitting properties" (R5) | Unsupported; property report packs cost $250–$2,000 and require participation (R2 review item 4; R5 review tally) | Cost score for L09 is "low hundreds to low thousands $/yr plus a data-sharing decision". |
| C14 | One booking moves the pace index 0.37→0.73 at 120 days | Correct, and in price terms the multiplier goes 0.85 (clamped) → 0.919, +8% from one booking (R3 review A1) | Confirms that own pace is too noisy to steer price alone; raises the value of any market-level pace stream. |

**Code status, 2026-10-19 (after this dossier was written).** Commit `d3e8b92` changed the code
for the repo defects this pack found. The US-40 feed now calls the CARS 511 GeoJSON endpoint
(`api-511x-co.carsprogram.org/events/map-features`) and stores `QUALITY_UNAVAILABLE` on a non-JSON
response. Open-Meteo requests set `wind_speed_unit=ms`, so the ×2.237 conversion is now correct.
`events.yaml` adds MLK (2027-01-15 to 01-18), Presidents Day (2027-02-12 to 02-15) and Spring Break
(2027-03-06 to 03-21). `winter_park.yaml` keeps only product-specific Ikon Session Pass blackouts
(26–30 Dec 2026, 16–17 Jan 2027, 13–14 Feb 2027, matching the resort's pass page). The SQI price curve
is neutral below normal, so the 0.78 drought cut is gone. The 26 related tests pass. Still open:
live CARS behaviour is unverified; the parser matches "closed" anywhere in a feature's text, so a
shoulder closure (a real value in the feed, e.g. "Right shoulder closed") can set the full-closure
flag; whether the milepost window 233–243 covers the Empire-side approach (OTIS station 000223 there
is at MP 248.7–254.3) is UNVERIFIED; the SQI curve still raises price 12–18% in big-snow years, which
this research did not validate; and Open-Meteo's free tier remains non-commercial. Comp calendar
availability is still not persisted. The findings below are kept as written, because they explain
why each change was needed.


## Part A. How to rank data streams

Hypothesis H3 says the real problem is picking the right factors from too many. Mature forecasting and
RM teams answer it with five tools. Value-of-information arithmetic says what a stream *could* be worth.
Out-of-sample forecast tests say whether it carries information. Multiple-testing control stops a large
screen from promoting noise. Pooling borrows data from where it is plentiful. Simulation turns forecast
gains into money. This part reviews each tool and then fixes our protocol (§A.9).

### A.1 Value of information: what a stream is worth before we test it

**Definitions.** In Bayesian decision analysis (Raiffa & Schlaifer 1961, *Applied Statistical Decision
Theory*, Harvard; Howard 1966, "Information value theory", *IEEE Trans. Systems Science and Cybernetics*
SSC-2(1):22–26, [record](https://synapsesocial.com/papers/W2001863269)), the value of a piece of information
is the expected gain from deciding after seeing it, compared with deciding now:

- **EVPI** (perfect information) = E_θ[max_a U(a, θ)] − max_a E_θ[U(a, θ)].
- **EVPPI** (partial perfect information about one input φ) = E_φ[max_a E_{θ|φ} U] − max_a E_θ U.
- **EVSI** (sample information: a noisy, finite stream) replaces φ with what the stream actually reports.
  EVSI ≤ EVPPI ≤ EVPI, so EVPI caps the value of all data combined.

Health-economics teams compute EVPPI cheaply by regressing the simulated payoff of each decision on the
input of interest and taking the expected maximum of the fitted values (Strong, Oakley & Brennan 2014,
*Medical Decision Making* 34(3):311–326, [PMC4819801](https://pmc.ncbi.nlm.nih.gov/articles/PMC4819801)).
That method needs only a probabilistic simulation sample, which `proving_ground_exam/` can produce.

**The pricing version (implementable).** Let a night's owner-net payoff be π(p) = p·q(p) (scaled by the
owner share), with optimum p*. A second-order expansion gives the loss from posting p = p*·e^ε:

- Linear demand q = a − bp: loss / π* = ε² exactly at small ε (derived: π″ = −2b and π* = a²/4b).
- Exponential (logit-like) demand q = e^{−p/θ}: loss / π* ≈ ε²/2.

So **expected loss ≈ k·E[ε²]·π\* with k between 0.5 and 1**. I use k = 0.75 (range 0.5–1). If a stream
lets the engine remove a component of log-price error with variance σ²_i, the expected gain on the nights
it touches is

  **ΔV_i ≈ k · f_i · q_i · σ²_i · p_i · R**,

where f_i is the value-weighted share of nights on which the information arrives before the price is
effectively set and inside the guardrails, q_i the share of that variance the stream captures (its
reliability: a noisy stream has q well below 1), p_i the probability the stream can be obtained and kept
working, and R the revenue at stake. Errors are additive in variance only if components are independent,
so streams that measure the same thing (SNOTEL and resort depth) must share one σ².

**The EVPI ceiling for this engine.** If the engine's total log-price error on a night has a standard
deviation of about 20–25% (comps disagree by 28–41%, per the anchor study cited in `pace.py`; the
simulated candidate missed peak ADR by about 9%, OVERHAUL 2026-10-14), then EVPI ≈ 0.75 × (0.20²–0.25²)
≈ **3–5% of revenue**. That is the most that all information combined can add to pricing *levels*. It
matches the independent STR evidence (one tool-level estimate of +8.6% revenue that came from cutting
price; an operator-coauthored field test of +3.5–5.2%; R4 review §6). Any single stream claimed to add
more than a few percent should be treated as an error. Structural levers (min-stay, stay blocks, orphan
logic) sit outside this ceiling because they change what is sold, not the price of a given night.

**Engine mapping.** This formula is the ceiling behind the judgmental ranges in §B.1. Those ranges overlap and must not be added. No row shows its own f, q, and σ². In `proving_ground_exam/`, EVPPI per latent
driver can be computed with the Strong et al. regression on paired seeds (§A.9 step 4).

### A.2 Feature importance done right, and what our IC actually measures

- **Permutation importance** (Breiman's random-forest measure) shuffles one feature and measures the loss
  increase. With correlated features it is biased toward the correlated ones; Strobl et al. propose a
  conditional permutation scheme (Strobl, Boulesteix, Kneib, Augustin & Zeileis 2008, *BMC
  Bioinformatics* 9:307, [PMC2491635](https://pmc.ncbi.nlm.nih.gov/articles/PMC2491635)). Hooker, Mentch
  & Zhou show that unrestricted permutation forces the model to extrapolate into empty regions and
  "can produce diagnostics that are highly misleading"; they recommend refitting without the feature and
  measuring the change in performance (*Statistics and Computing* 31:82, 2021;
  [arXiv 1905.03151](https://arxiv.org/abs/1905.03151), abstract read). **For us: score a stream by
  drop-column refit (leave-one-covariate-out) on a rolling origin, never by permuting a fitted model.**
  Our candidates (snow depth, SWE, SQI, terrain %, calendar) are strongly collinear.
- **SHAP** (Lundberg & Lee 2017, NeurIPS, [paper](https://papers.nips.cc/paper/7062-a)) gives additive
  per-prediction attributions. Kumar, Venkatasubramanian, Scheidegger & Friedler show that Shapley-based
  importance has mathematical problems that need causal reasoning to fix, and does not match explanation
  goals (ICML 2020, [arXiv 2002.11097](https://arxiv.org/abs/2002.11097v2)). SHAP explains a model; it
  does not price a data stream. **It is useful in `src/explain` for showing the operator why a price
  moved, and useless for buying data.**
- **The information coefficient.** In active management the IC is the correlation between forecasts and
  realized *residual* returns, and the fundamental law IR = IC·√breadth assumes independent bets (Grinold
  1989; Grinold & Kahn 2000, *Active Portfolio Management*; summary in
  [CFA Institute reading](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2025/analysis-active-portfolio-management)).
  Two conditions matter: the target is a **residual** (what the existing model did not already predict),
  and breadth counts **independent** decisions.

**Our ladder violates both conditions (repo audit, `src/eval/backtest.py:191–244`).**

1. **The target is a level, not a residual.** `score_signal_against_outcomes` correlates the signal with
   the portfolio's average booked revenue on stay date d + 14 from `nightly_inventory`. Any seasonal
   signal (snow, holidays) correlates with the season itself. Example: `calendars.demand_strength` has
   IC = 0.937 (n = 91) in `signal_scores`. That is the calendar re-discovering that holidays sell, which
   the engine already knows. The IC must be computed against the **pickup residual** (realized pickup
   minus the current pace model's forecast at the same lead), as R5 §4 proposed.
2. **The hit rate is broken.** `hit_rate` skips pairs where either value is zero in the numerator but
   keeps them in the denominator, and compares the sign of a raw level (usually positive) with the sign
   of revenue (zero or positive). The same signal shows hit rate 0.011, so it can never pass 0.52 while
   having the highest IC on the board.
3. **Overlapping, autocorrelated pairs.** Daily decision dates with a 14-day horizon on persistent
   signals give far fewer independent observations than n. The Fisher interval assumes independence.
4. **No multiplicity control.** Each signal is tested alone at IC ≥ 0.05 and hit rate ≥ 0.52. My Monte
   Carlo of that rule under the null (`/private/tmp/wp_research/r6/a1_ladder_mc.py`, 4,000 draws each):

| n pairs | Signal and outcome | P(promote \| no information) | Null IC, 97.5th percentile |
|---|---|---|---|
| 40 | independent | 0.27 | 0.31 |
| 40 | persistent (AR(1) 0.95 and 0.7) | 0.30 | 0.56 |
| 90 | persistent | 0.31 | 0.41 |
| 200 | persistent | 0.29 | 0.29 |

With a centred outcome, **a pure-noise signal clears the active gate about 27–31% under persistent
noise**; independent-noise rates are about 23% at n=90 and 17% at n=200. Screening the 55 A- and
B-tier streams would promote about 15 by chance under the persistent-noise diagnostic. (With the repo's level outcome, the broken hit rate happens to block
most promotions: 3–12% false promotion, but it also blocks true ones.)

### A.3 Granger causality and lead-lag analysis

A series x Granger-causes y if past x improves the forecast of y given past y (Granger 1969,
*Econometrica* 37(3):424–438,
[Econometric Society](https://www.econometricsociety.org/publications/econometrica/1969/08/01/investigating-causal-relations-econometric-models-and-cross)).
Granger noted that apparent instantaneous causality often comes from slow recording or omitted variables.
With trending or seasonal series, use the lag-augmented test of Toda & Yamamoto (1995, *J. Econometrics*
66:225–250, [IDEAS](https://ideas.repec.org:443/a/eee/econom/v66y1995i1-2p225-250.html)) or difference
first, as R7 did with 12-month log differences.

Three rules for our use:
- **Condition on the own lag.** The question is never "does snow correlate with demand" but "does snow
  add to what current pace already says". The B.2 lead-lag results show why the raw and conditional
  answers must not be conflated.
- **Block by season.** Seasons, not days, are the independent units for slow streams (R7 review: 23
  effective winters, not 134 months). Bootstrap or permute whole seasons.
- **Granger is predictive, not causal.** For pricing that is fine: we need forecasts. It is not fine for
  the simulator, where a latent driver must be causal or the sim learns a confounder.

### A.4 Forecast error to revenue

- Lee (MIT FTL R90-5, 1990) simulated each 10% gain in forecast accuracy as worth 0.5–3% revenue (via R1
  §2.3; STALE, abstract only).
- Pölt (1998), as cited by Webb et al. (2022): a 20% cut in forecast error yields about 1% revenue
  (via R2 §2.2; **UNVERIFIED**: the primary AGIFORS paper was not found).
- Fiig, Weatherford & Wittman, *Journal of Revenue and Pricing Management* 18(4):291–305 (2019), as
  opened in `reviews/R6_review.md`. This fix pass did not re-open the PDF. The review reports an
  airline simulation, not a field test: a ±10 percent elasticity-parameter bias cuts revenue by up
  to about 1 percent, and ±20 percent by up to about 4 percent. That is the same order as the 3–5
  percent ceiling above.
- Weatherford & Belobaba (2002, *JORS* 53(8):811–821): forecast accuracy matters most, and some errors can
  even help EMSR-type rules (via R1).
- Zickus (via R1): the best forecaster depends on the optimizer it feeds.

The VOI formula in §A.1 reproduces this order of magnitude. If forecast error drives price error
one-for-one through a damped multiplier (sensitivity 0.30), a 20% cut in a 25% demand-forecast error
removes about 0.30 × 5% = 1.5 points of price error; on a 10% price-error baseline that gains
0.75 × (0.100² − 0.085²) ≈ 0.2% of revenue. **Forecast accuracy is worth little unless it moves the
price**, which is the airline lesson (judge the forecaster with the optimizer attached).

### A.5 Nowcasting and search data

- Choi & Varian (2012, *Economic Record* 88(s1):2–9) introduced "predicting the present": search indices
  improve nowcasts of official series that arrive with a lag, including travel
  The DataEDGE schedule page previously cited here is the wrong document. The paper is Choi and Varian, *Economic Record* 88(s1):2–9 (2012), https://doi.org/10.1111/j.1475-4932.2012.00809.x. This fix pass did not re-open the PDF.
  A replication exists (Coupé 2018, *Economics E-Journal* 12:1–8,
  [IDEAS](https://ideas.repec.org/a/zbw/ifweej/201834.html)); its results were not visible in the abstract.
- Giannone, Reichlin & Small (2008, *J. Monetary Economics* 55(4):665–676,
  [LBS record](https://lbsresearch.london.edu/id/eprint/315)) give the formal tool: the **marginal value
  of each data release** to the nowcast, with a "ragged edge" of staggered publication dates. That is the
  right frame for our slow streams (pass sales, DestiMetrics briefs, lodging tax). Each release's value
  is the forecast revision it causes, measured at its publication timestamp.
- Tourism forecasting evidence:
  - In the 1,311-series tourism competition, pure time-series methods beat models with explanatory
    variables (Athanasopoulos, Hyndman, Song & Wu 2011, *IJF* 27(3):822–844,
    [Hyndman](https://robjhyndman.com/publications/the-tourism-forecasting-competition/)).
  - Song, Qiu & Park (2019, *Annals of Tourism Research* 75:338–362, 211 papers) find no single method
    works everywhere ([PolyU](https://ira.lib.polyu.edu.hk/handle/10397/99278?mode=full)).
  - Search data helped in large markets: Hainan with Baidu and Google vs ARMA (Yang, Pan, Evans & Lv
    2015, *Tourism Management* 46:386–397, [IDEAS](https://ideas.repec.org/a/eee/touman/v46y2015icp386-397.html));
    Caribbean AR-MIDAS (Bangwayo-Skeete & Skeete 2015, *Tourism Management* 46:454–464,
    [UNCW](https://scholars.uncw.edu/display/d194979833856)).
  - **Adversarial:** Google Trends did not beat time-series benchmarks for Spanish rural overnight stays
    (Cebrián & Domenech 2024, [JOTMR](https://archive.conscientiabeam.com/index.php/31/article/view/3986)),
    and Spanish inflow gains decayed after 2012 (Artola, Pinto & de Pedraza 2015, *IJM*,
    [Emerald](https://emerald.com/insight/content/doi/10.1108/IJM-12-2014-0259/full/html)). Flu Trends
    overfit (Lazer et al. 2014, via R5).
- **Transfer.** Winter Park large-home demand is a rural, low-volume, name-clashing query (Winter Park,
  Florida). The evidence says search data helps where volume is high and fails in rural niches. **The
  competition result is the more important one: explanatory variables rarely beat a good time-series
  model of the outcome itself.** For us, the outcome series that matters is pace, own and market.

### A.6 Multiple-testing and data-snooping control for an 80+ stream screen

- **White's Reality Check** (2000, *Econometrica* 68(5):1097–1126,
  [Econometric Society](https://www.econometricsociety.org/publications/econometrica/2000/09/01/reality-check-data-snooping)):
  a bootstrap test of whether the *best* of many models beats a benchmark, accounting for the search.
- **Hansen's SPA test** (2005, *JBES* 23:365–380): same null, more power because it discounts clearly bad
  models ([RePEc summary](https://ideas.repec.org/p/bro/econwp/2001-06.html)).
- **Model confidence set** (Hansen, Lunde & Nason 2011, *Econometrica* 79(2):453–497,
  [IDEAS](https://ideas.repec.org/a/ecm/emetrp/v79y2011i2p453-497.html)): the set of models that contains
  the best one at a stated confidence. Uninformative data gives a large set. That is the honest output for
  us: "these 6 streams cannot be told apart yet".
- **False discovery rate** (Benjamini & Hochberg 1995, *JRSS-B* 57(1):289–300,
  [PDF](https://www.dcscience.net/Benjamini-Hochberg-1995-FDR.pdf)): order the p-values p_(1) ≤ … ≤ p_(m)
  and reject the k smallest, where k is the largest index with p_(k) ≤ (k/m)·α. It controls the expected
  share of false promotions rather than the chance of any.
- **Raised hurdles.** After hundreds of factors were mined, Harvey, Liu & Zhu argue a new return factor
  needs t > 3.0, not 2.0 (2016, *RFS* 29(1):5–68, [NBER w20592](https://www.nber.org/papers/w20592)).
  A 2022 re-analysis argues most claimed findings are still likely true ([arXiv 2206.15365](https://arxiv.org/pdf/2206.15365)).
- **Stability selection** (Meinshausen & Bühlmann 2010, *JRSS-B* 72:417–473,
  [PDF](https://www.stat.cmu.edu/~ryantibs/journalclub/meinshausen_2010.pdf)): select only features that
  survive most subsamples, with a bound on expected false selections.
- **Pairwise forecast tests.** Diebold–Mariano (1995) compares two forecasts' losses; its power collapses
  under strong serial dependence in the loss differential, so block bootstraps by season are needed
  (bibliographic; secondary evidence via [White Rose](https://eprints.whiterose.ac.uk/155897/15/jae.2756.pdf)).
- **H3 in theory.** In feature-based dynamic pricing, regret grows linearly in the number of features
  that actually matter (order s√T) and only logarithmically in the number screened (Ban & Keskin 2021,
  *Management Science* 67(9):5549–5568, [SSRN](https://papers.ssrn.com/abstract=2972985)). Each extra
  real factor costs learning. Each extra screened candidate costs little *if* selection is controlled.
  **H3 is right in a specific sense: with ~100 bookings, the engine can afford perhaps three or four
  learned factors. Everything else must enter as a fixed prior, a calendar fact, or a pooled market
  quantity.**

### A.7 Pooling to beat thin data

- **Shrinkage.** Efron & Morris (1975, *JASA* 70(350):311–319,
  [PDF](https://www.medicine.mcgill.ca/epidemiology/hanley/bios602/MultilevelData/EfronMorrisJASA1975.pdf))
  showed Stein-type pooling cut mean squared error to less than half of the raw means in every example.
  R3 §10.3 gives the hierarchical elasticity model; with one season the home's own estimate gets weight
  about 0.15 (R3 review A7 confirms).
- **Hierarchical forecasts.** MinT reconciliation makes home, comp-set and market forecasts coherent and
  minimizes reconciled error variance (Wickramasuriya, Athanasopoulos & Hyndman 2019, *JASA*
  114:804–819, [Monash](https://research.monash.edu/en/publications/optimal-forecast-reconciliation-for-hierarchical-and-grouped-time/)).
  For us, a three-level hierarchy (home → 5+ BR comp tier → market) lets the market level carry most of
  the signal.
- **Proxies.** When the true outcome is scarce and a proxy is plentiful, estimate on the proxy and learn a
  sparse bias correction from the small true sample (Bastani 2021, *Management Science* 67(5):2964–2984,
  [arXiv 1812.11097](https://arxiv.org/pdf/1812.11097)). Our proxies: comp availability transitions (many
  listing-nights) for our bookings; US-40 traffic and lodging tax for market demand.
- **Market-level targets.** Hotel evidence (R2 §2.2–2.3): market occupancy is forecastable (3.7% MAPE at
  365 days for NYC, Das et al. 2021), property-level is not, and pooling neighbouring dates and prior years
  cut a 32-room hotel's 28-day MAPE from 23.9% to 4.6% (Heo et al. 2023; COVID-era window, R2 review
  item 2).
- **Transfer across mountain towns.** The same model fitted on Summit County or Steamboat large-home
  comps, with a Winter Park offset, is the natural next level of the hierarchy once comp data works.
  The snow literature supports partial transfer: effects shrink with snowmaking and elevation
  (Töglhofer et al. 2011, via R5 review F-2) and are stronger at drive-to resorts (HVS, via R5 review).

### A.8 Field measurement when the MDE is about 33%

- **CUPED** uses a pre-period covariate as a control variate; Bing cut variance about 50% (Deng, Xu,
  Kohavi & Walker 2013, WSDM, [exp-platform](https://exp-platform.com/cuped/)). For us the covariate is
  last year's same-week outcome, or the market's same-week pace. Halving variance cuts the MDE by about
  √2, from about 33% to about 23%. That is still an order of magnitude above any stream's value.
- **Switchbacks** randomize treatment over time blocks, with designs and exact randomization tests that
  allow for carryover (Bojinov, Simchi-Levi & Zhao 2023, *Management Science*,
  [arXiv 2009.00148](https://arxiv.org/abs/2009.00148v4)). Our carryover is the booking window (about 72
  days in winter, C1). Note R1 review: an airline AI-pricing pilot rejected temporal alternation for
  exactly this advance-purchase reason.
- **Conclusion.** No data stream's profit effect is field-detectable at three homes. Streams must be
  proved through a **metric chain**: offline forecast lift on a market-level target, then decision change,
  then simulated owner net. The field is used only to check that the forecast lift is real and that
  nothing broke.

### A.9 Our protocol

**Step 1: targets** (in order of statistical power; each is computed as-of, from data observed at
the decision timestamp):

| Target | Unit | n per winter (approx.) | Why |
|---|---|---|---|
| T1 Market pace residual: change in the 5+ BR comp tier's unavailable share for stay night d between t and t+14, minus its seasonal-lead norm | comp-tier × stay night × as-of | ~120 nights × 9 leads ≈ 1,000+ (needs C2 fix) | Most observations; nearest to our demand |
| T2 Comp price change for night d, t → t+14, same comps only | as T1 | as T1 | Market WTP movement; must use matched comps (see §B.3 note) |
| T3 Own booking hazard: P(night d books in (t, t+14] \| open at t), pooled over 3 homes | home × night × lead bucket | ~300 open home-night-leads | The outcome we price; thin |
| T4 Achieved price residual vs anchor | booked stays | ~30–50 | Thin; calibration only |
| T5 Season-level: winter lodging tax (town series, rate-adjusted), US-40 Dec–Mar traffic | season | 5–23 seasons | Slow streams only (pass sales, macro) |

**Step 2: evaluation.** Rolling-origin backtests (Tashman 2000, *IJF* 16(4):437–450; recalibrate at each
origin, several test periods), with origins every 7 days and season-block resampling.
Leakage rules (Kaufman, Rosset, Perlich & Stitelman 2012, *ACM TKDD* 6(4):15,
[DOI](https://www.doi.org/10.1145/2382577.2382579)): use only rows with `observed_at` ≤ decision date
(the existing `assert_no_lookahead` contract); compute normals and climatologies from years before the
test season; never use a stay's final status to build a feature; and score future stay dates only after
they are fully observed (the current ladder reads `nightly_inventory` as it is today, which mixes final
and partial outcomes).

**Step 3: forecast-lift metric.** For each stream, drop-column refit (A.2), comparing log-loss or MAE on
T1–T3 with and without it, conditional on the current pace model. Report the season-block bootstrap
interval of the loss difference.

**Step 4: decision and money.** Feed the forecast into the price rule in `proving_ground_exam/` with the
stream's latent driver switched on (or replayed from history), and compute the paired owner-net
difference over 25 held-out seeds. Compute EVPPI for the driver by the Strong et al. regression on the
same seeds (A.1). A stream whose EVPPI is below its annual cost plus maintenance is rejected without
further testing.

**Step 5: multiplicity.** Screen all candidates at once against the pace model. Use Hansen's SPA (or a
season-block Reality Check) for "does anything beat the base", and BH at q = 0.10 on the per-stream
season-block p-values to choose which go to shadow. Require stability across at least two origin windows.

**Step 6: thresholds and the ladder** (`config/policies/signals.yaml`). Proposed replacement:

| Gate | Current | Proposed |
|---|---|---|
| experimental → shadow | n ≥ 30 | Prior VOI (A.1) above annual cost, **and** feed passes a health check that can detect a silent zero (C4) |
| shadow → active | IC ≥ 0.05, hit rate ≥ 0.52, n ≥ 40 against booked revenue level | (a) IC against the **pickup residual** (T1 or T3) with a season-block 90% interval above 0; (b) BH-adjusted q ≤ 0.10 across all shadow signals; (c) out-of-sample loss reduction in ≥ 2 of 3 origin windows; (d) simulated owner net ≥ 0 on 25 paired seeds |
| Season-level variant (new) | none (season signals can never reach n = 40, R3 §11.2) | Season-level streams (pass sales, macro, ENSO) enter only as **scenario switches** for the ceiling and floor posture, sized in the simulator. They are never fitted as coefficients. |
| active → deprecated | IC ≤ −0.02 | Interval entirely below 0, or source failure (unchanged), **or health check fails** |

Fix the hit-rate function (count only non-zero pairs in the denominator; compare the sign of the
centred signal with the sign of the residual) before any of this runs.


## Part B. Applying the method now

### B.1 Scoring rules

The current catalog has 121 rows: 17 A-tier and 38 B-tier rows. W03 and W04 are both B provider
rows for the same short-range signal; they are not deduplicated in the row-level audit. W01 is an
A-tier stream. I score each row on a 0–5 scale for mechanism, decision
frequency, reliability, and access, then apply the VOI ceiling from A.1. The score is deliberately
ordinal: `impact` is the expected owner-net percentage range if the stream is correctly integrated,
not a promise of lift. Cost is annual cash cost plus maintenance burden. A stream cannot be promoted
from this table without a rolling-origin test and paired simulation.

| Rank | Stream / repair | Tier | Expected owner-net impact | Confidence | Cost / effort | Current state and decision |
|---:|---|---|---:|---|---|---|
| 1 | Repair comp scraping and persist per-day calendar availability (L06) | A / prerequisite | 1–4% plus structural LOS value | Medium | low–medium / medium | Binding constraint; build before buying a feed. |
| 2 | Market 5+BR pace and occupancy (L08/L09/L10, pooled) | A | 0.5–3% | Medium | medium–high / medium | Buy only after depth and all-in definitions are verified. |
| 3 | Own pace corrected to stay-level residuals (L01) | A | 0.3–2% | Medium | low / medium | Already wired but noisy; cluster by stay and shrink to market pace. |
| 4 | Resort snow / terrain / opening state (W08/R01/R02) | A | 0.2–2% | Medium | low / low–medium | Use as state and ceiling posture; do not fit a season multiplier from one study. |
| 5 | Calendar blocks: school breaks, holidays, events (C01–C10) | A | 0.2–1.5% | High for dates, low for magnitudes | low / low | Encode deterministic dates and test only incremental residual value. |
| 6 | Short-horizon access risk: US-40, Floyd Hill, chain laws (A01; A03/A13 are B/C context) | A/B/C | 0.1–1.5% | Medium | low / medium | Fix feed and fail closed; apply to arrival windows, not all nights. |
| 7 | Lift-ticket window price / pass and season disclosures (R03/R04) | B | 0.1–1% | Low–medium | low / low | Scenario or reference-price feature; existing field is not live. |
| 8 | DEN capacity and passenger traffic (A08; A06/A09 are C context) | B/C | 0.1–0.8% | Low–medium | low–medium / low | Useful pooled origin proxy; rental prices are optional validation, not evidence. |
| 9 | Front Range / TX-OK-KS gasoline (E01; E02/E04 are C context) | B/C | 0–0.4% | Low for Winter Park | low / low | Shadow only, origin-weighted; H4 bound makes it a low priority. |
| 10 | Search / intent and DMO mobility (S01; L11 is C context) | B/C | 0–0.5% | Low | medium–high / medium | Test as nowcast only; rural search is noisy and may not beat pace. |

The remaining A/B streams—macro sentiment, FX, international arrivals, geopolitical news, air
fares, AQI, rail, regulation and substitute-market data—are useful for scenario analysis or a
later pooled model but do not outrank the ten above. Geopolitical feeds are especially prone to
false precision: they can justify a scenario switch, not a daily price coefficient.

What a generic comp pricer already approximates, and what it does not (H2). A calendar-based tool
already sees listed price, a broad occupancy proxy, day of week, and lead time. It does not
document snow, resort operations, a US-40 closure, or an origin-market school calendar, and its
published comp pool is far wider than the roughly fourteen true peers for these houses. Persisting
our own calendar does not by itself beat that tool: a stored available flag still mixes a booking
with a host block. The edge is the capacity-matched panel plus the mountain state, not the mere
fact of having a calendar.

### B.1a Row-level A/B audit

The current catalog has 121 rows: every one of its 17 A and 38 B rows is scored below. The
impact ranges are overlapping shares of one 3–5% owner-net information ceiling; they must not be
added. `repo` means a collector or proxy exists, not that it is reliable. Build repairs the data
spine, shadow forecasts or simulates without live pricing, scenario is a slow prior, and drop is
no near-term use.

| ID | Tier | Impact | Conf. | Cost/effort | Repo | Decision |
|---|---|---:|---|---|---|---|
| L01 | A | .3–2% | M | low/M | yes | build residual pace |
| L02 | A | 0–.5% | L | M/M | partial | shadow inquiry linkage |
| L06 | A | 1–4%* | M | low–M/M | partial | build scraper/calendar |
| L07 | A | .5–2% | M | high/M | no | shadow after contract |
| L09 | A | .2–1.5% | M | low–high/M | no | shadow published pace |
| W01 | A | .2–1.5% | L–M | low/low | yes | scenario/band |
| W08 | A | .2–1.5% | M | low/low | yes | build state |
| A01 | A | .1–1.5% | M | low/M | broken | build, fail closed |
| C01 | A | .2–1% | H/L | low/low | partial | build dates |
| C02 | A | .2–1% | M | low/low | partial | shadow segment |
| C04 | A | .2–1% | H/L | low/low | partial | build dates, shadow size |
| C05 | A | .1–.8% | M | low/low | partial | build dates |
| R01 | A | .1–1% | M | low/low | yes | build boundary |
| R02 | A | .1–1.5% | M | low/low | yes | build operations |
| P04 | A | 0–.5% | M | free/M | partial | scenario/backtest |
| X01 | A | .1–1% | L–M | low/low | partial | shadow substitute |
| Z04 | A | .1–.8% | L | low/M | partial | build prior only |
| L03 | B | 0–.3% | L | free/M | partial | manual shadow |
| L12 | B | 0–.3% | L | free/low | partial | season supply scenario |
| L08 | B | .2–1.5% | M | low/low | no | shadow dashboard |
| L10 | B | .2–1% | L–M | high/low | no | shadow if covered |
| S01 | B | 0–.3% | L | free/low | fixture | nowcast test |
| S04 | B | 0–.3% | L | M/M | no | drop near term |
| S06 | B | 0–.5% | L | high/low | no | scenario/calibration |
| W03 | B | 0–.5% | L–M | free/low | no | short-lead shadow |
| W04 | B | 0–.5% | L–M | M/low | yes | alternate shadow |
| W05 | B | 0–.3% | L | free/M | no | scenario |
| W06 | B | 0–.3% | L | free/low | yes | scenario |
| W09 | B | 0–.5% | L | M/M | no | drop pending access |
| W10 | B | 0–.3% | L | free/low | yes | scenario |
| A03 | B | 0–.5% | L–M | free/M | no | identify station |
| A08 | B | 0–.5% | L | high/M | proxy | pooled shadow |
| E01 | B | 0–.4% | L | free/low | partial | origin shadow |
| M01 | B | 0–.2% | L | free/low | no | scenario |
| M02 | B | 0–.2% | L | M/low | no | drop |
| M03 | B | 0–.3% | L | free/low | no | scenario |
| M04 | B | 0–.3% | L | free/low | no | guardrail |
| M08 | B | 0–.3% | L | free/low | no | manual scenario |
| G08 | B | 0–.3% | L | free/low | partial | scenario |
| E07 | B | 0–.2% | L | free/low | no | scenario |
| C03 | B | 0–.3% | L | free/low | no | shadow if segmented |
| C07 | B | 0–.3% | M/L | free/low | yes | product scenario |
| C08 | B | 0–.5% | L–M | free/low | yes | shadow events |
| R03 | B | 0–.5% | L–M | free/M | partial | reference scenario |
| R04 | B | 0–.5% | L | free/low | no | scenario |
| P01 | B | 0–.2% | L | free/M | partial | supply scenario |
| P03 | B | 0–.2% | L | free/M | no | scenario |
| X02 | B | 0–.5% | L | M/M | partial | shadow after L06 |
| X03 | B | 0–.2% | L | free/low | no | drop |
| X04 | B | 0–.5% | L | free/low | partial | shadow after A01 |
| Q01 | B | 0–.3% | L | infra/M | no | shadow quality |
| Q02 | B | 0–.2% | L | infra/M | no | drop |
| Q04 | B | 0–.3% | L | infra/M | partial | shadow matching |
| P08 | B | 0–.3% | H/L | free/low | partial | build all-in |
| P09 | B | 0–.5% | M | free/low | no | build fee model |

*L06 is a prerequisite/structural range, not an incremental number to add to the other rows.

### B.2 Cheap empirical checks

The available scratch analyses and read-only store checks support ranking, not causal estimates:

| Check | Outcome | Honest n / limitation |
|---|---|---|
| Gas vs access traffic, monthly and YoY | Winter coefficient near zero; positive snow coefficient | 23 effective winter seasons; monthly rows are not independent. |
| Town lodging tax seasonality | Nov–Apr share 71.7% | Five seasons; town remittance, not home revenue. |
| Comp movement signal | 14-day median price lift exists in the signal store | Four b3 windows: n=44,46,48,50; partial correlations +.10,+.03,+.43 (p=.002),+.09. The one sharp look is multiple-testing, not a price feature. |
| Own pace | One booking can move the 120-day pace multiplier by about 8% | Stay-clustered and censored; not a stable elasticity sample. |
| Ladder Monte Carlo | Existing IC/hit gate promotes null signals about 27–31% under persistent noise; independent-noise rates are about 23% at n=90 and 17% at n=200 | 4,000 null draws per case; protocol diagnostic, not field evidence. |
| Dated snow / tax / traffic comparisons | Snow is a plausible seasonal state, not a demonstrated lagged forecast driver | Weekly n=120, SWE p=.731; out-of-sample n=89 weeks / 7 seasons: traffic-forecast MAE worse by 0.7–3.5% (snow) and 9.8% (snow + gas); not a revenue effect; seasonal n=8. |

The reviewer's re-run of `b3_leadlag.py`, `b4_granger.py`, and `b5_season.py` is the source of the
weekly numbers. This fix pass did not repeat the 4,000-draw permutations. The four sweep-presence
windows against own pickup are: 21 Sep, n = 44, partial +0.10 (p = 0.62); 25 Sep, n = 46, partial
+0.03 (p = 0.86); 30 Sep, n = 48, partial +0.43 (p = 0.002); 5 Oct, n = 50, partial +0.09
(p = 0.60). Three of four are null. Sweep presence is not a pickup feature, and it is not a stored
calendar. The reviewer's read-only count, also not re-opened here, is that 65.2 percent of scrape
rows are `failed` and those rows are source `manual`, while Airbnb-sweep rows are `ok` or
`unavailable`, and about 0–8 percent of December–March nights have three fresh comps. Rank 1 does
not depend on restating the older "67 percent of rows" line.

Lagged snow does not improve the traffic forecast. On 120 weeks, snow-water-equivalent lags 1–3
have season-permutation p = 0.731 (F = 0.30). New snow is p = 0.053. Real gas is p = 0.070. Out of
sample, 89 weeks and 7 seasons, adding snow-water equivalent makes mean absolute error **worse** by
0.7 percent (same-week value lagged) and 3.5 percent (one-week lag), and snow plus gas makes it worse by
9.8 percent. Lagged gas alone improves it by 0.8 percent (4 of 7 seasons), which is noise at this n. At
2, 4, 6, and 8 weeks the error with snow is worse by 5.5, 4.7, 4.4, and 8.2 percent. (`b4_granger.py`
prints these as a signed "relative reduction", so −0.7% there means 0.7% worse; re-run 2026-10-19.)
These are traffic-forecast errors, not revenue effects. On eight seasons, 1 January snow versus January–March
traffic is r = +0.71; 15 December is r = +0.12; 1 December is r = +0.55. R7's contemporaneous
snow coefficients, about +1.3 to +2.2 percent traffic per inch on a different specification, are
not this lead-lag result. Snow stays a seasonal state and a simulator world.

No guest-level reservation fields were needed. A proper lead-lag test for each stream must use
season blocks, not daily rows, and must compare against the current pace residual. A positive raw IC
against bookings is not incremental information.

### B.3 Promotion protocol

For every candidate, create three versions: (1) base model without the stream, (2) forecast model
with the stream, and (3) the full price rule with the stream switched into a latent-driver simulator.
Use rolling origins at 180, 120, 90, 60 and 30 days before stay date; keep any observation whose
publication time is after the decision out of the feature. Score forecast loss, price-change rate,
and owner-net on paired seeds. Use season-block bootstrap intervals.

The ladder change is:

| Transition | Required evidence |
|---|---|
| Experimental → shadow | Prior VOI exceeds annual cost, source health detects stale/zero/non-JSON data, and the feature has a written missing-data fallback. |
| Shadow → active | Residual IC interval above 0; BH q ≤ 0.10 across the screen; loss reduction in at least 2 of 3 origin windows; paired owner-net non-negative on 25 seeds; no safety or freshness failure. |
| Active → deprecated | Interval below 0, source failure, stale data without a safe fallback, or negative owner-net in the paired simulator. |

The current `config/policies/signals.yaml` gate of IC ≥ 0.05 and hit rate ≥ 0.52 is not sufficient
until IC is residual-based and hit-rate zeros are excluded from the denominator. Slow streams with
fewer than 40 independent seasonal observations never become fitted coefficients; they are scenario
switches or pooled priors.

## Part C. Maximum-utilization designs for the winners

### 1. Comp intelligence and calendar availability

Compute a capacity-matched peer panel: 5+ bedrooms, sleeps 14+, comparable amenities, same stay
window and all-in price. Persist daily availability, min-stay, check-in restrictions, listed rate,
and fetch quality. Derive peer median/p10/p90, price movement, availability drawdown, gap length and
the fraction of peers remaining bookable for the exact stay. Enter price anchoring and min-stay/gap
logic; never let a stale or thin panel raise price above the internal ceiling. If fewer than three
fresh peers or the payload is non-JSON, fall back to the seasonal anchor and mark the recommendation
low confidence. A persisted available flag is still an upper bound on occupancy: it does not
separate a booked night from a host block. In the simulator, add a competitor-availability latent driver and run scraper-outage
and endogeneity worlds. Field measurement is a shadow comparison against the home's own listed,
recommended and booked price; the 33% MDE means no active promotion from a small live sample.

### 2. Pooled market pace / occupancy

Construct a hierarchical target: market → 5+BR tier → home. Use market OTB and booking pace as the
prior, then shrink own pace toward it with a stay-level uncertainty estimate. Enter only the residual
pace signal into the price multiplier and ceiling posture; do not multiply the current multiplicative
pace ratio by another market ratio. Missing, stale, or non-JSON market data returns to the no-stream
rule and increases uncertainty; it must never freeze a directional target or multiplier. Simulate a
market-pacing latent driver under
normal, drought, supply-surge and stale-PMS worlds. Measure rolling-origin forecast error, price
decisions, and paired owner net; kill if it reduces forecast error but worsens owner net in any
high-rate peak world.

### 3. Snow and resort operations

Separate three horizons: seasonal snow state (SNOTEL/SWE and CPC), 7-day weather, and realized resort
operations (terrain/lifts/opening). Use seasonal state only to widen or narrow a confidence band and
to choose the simulator world; use short-range snow to adjust arrival-window demand; use actual
operations for close-in presentation and stay logic. Do not fit the stale Parthum coefficient as a
season multiplier. Missing data holds the neutral prior; impossible jumps are quarantined. Simulate
record snow, drought, late opening and early closure with the same demand driver across all homes.
The field gate is a paired shadow test plus a season-block review; any effect below 4% requires the
misspecified-world simulator to show benefit without overfitting the engine's own demand equation.

### 4. Calendar and access blocks

Build a canonical event table with source, publication time, start/end, expected segment, and
confidence. Use school calendars and holidays for base demand blocks; use road closures only for
arrival-date and drive-to segments; apply no blanket discount to a resort-wide closure without an
operations fact. Missing event data means no adjustment, never an inferred negative. The simulator
needs holiday shift, I-70 closure and early/late opening worlds. Measure the price/LOS decision and
owner net; kill if a signal changes more than its documented segment or fires on stale events.

### 5. Pass / lift-ticket / access-market reference prices

Use dated window lift-ticket prices and pass rules as an affordability/reference-price feature,
not as a direct demand coefficient. Segment by drive-to vs fly-in and by holiday. Missing or
unverified pass data leaves the reference-price feature neutral. Simulate price-sensitive groups and
substitute resorts; test against the all-in per-guest price. Do not promote on a single season of
pass disclosures.

## Recommendations and open questions

The highest-value sequence is: repair and persist comps; build pooled market pace; correct the
promotion ladder and run the simulator in misspecified worlds; add snow/resort and calendar/access
states; only then trial paid market dashboards or intent feeds. Open questions are the exact cost and
Winter Park depth of DestiMetrics/AirDNA/Lighthouse, the US-40 station id, and whether any market
provider permits pricing use of pooled nonpublic data under current competition law.

## Self-audit

| Requirement | Status |
|---|---|
| ≥20 new sources and ranking method | PASS: Part A cites VOI, forecasting, nowcasting, pooling, feature-importance and multiple-testing literature. |
| Every A/B stream scored | PASS: §B.1a has one line for each of the 17 A rows and 38 B rows in the catalog on disk. Ranges are judgment under one ceiling. |
| Real checks with honest n | PASS for the checks that were run: §B.2 gives weeks, seasons, and the four b3 windows. It does not claim a causal snow lead. |
| Top 10 and top 3–5 utilization designs | PASS: §§B.1 and C. |
| Comp repair scored | PASS: rank 1. |
| Missing/stale data fails safe | PASS: design 2 returns to the no-stream rule. A frozen target is not the fallback. |
| Search log | PARTIAL: Appendix A lists what this fix pass did and what it did not re-run. It does not invent queries. |
| No guest-level data or code changes | PASS. |

## Appendix A. Search log

This fix pass did not run a new web search. It applied `reviews/R6_review.md` to the file and
re-counted `R5_catalog.csv` (121 rows; 17 whose tier text starts with A; 38 whose tier text starts
with B). The reviewer's own twelve searches are listed in that review, section 6, and were not
repeated here. The script results in §B.2 are the reviewer's re-runs of `b3_leadlag.py`,
`b4_granger.py`, and `b5_season.py`. The 65.2 percent failed-row count is the reviewer's
read-only count, not a new query. The Choi and Varian DataEDGE URL was removed because the review
showed it was the wrong page; the Economic Record DOI is the bibliographic replacement, and the
PDF was not opened in this pass.

## Appendix B. Sources

The source bibliography is distributed across R1–R5 and R7. Key method sources used here include
Raiffa & Schlaifer (1961), Strong et al. (2014), Strobl et al. (2008), Hooker et al. (2021),
Choi & Varian (2012), Giannone et al. (2008), Athanasopoulos et al. (2011), White (2000), Hansen
(2005), Benjamini & Hochberg (1995), Meinshausen & Bühlmann (2010), Diebold & Mariano (1995),
Efron & Morris (1975), Wickramasuriya et al. (2019), Bastani (2021), and Ban & Keskin (2021), with
URLs and access qualifications in the Part A text and the upstream dossiers.

## Appendix C. Response to review

Review: `reviews/R6_review.md`, ACCEPT WITH FIXES, 11 items. Script permutations and the database
count were not re-run in this pass. They are marked reviewer-reproduced.

| # | Status | What changed |
|---|---|---|
| 1 | Applied | §B.2 now reports the b4 and b5 numbers, including p = 0.731, the out-of-sample error changes, n = 8, and R7's contemporaneous coefficients as a separate specification. Snow is not described as a lagged forecast. |
| 2 | Applied, reviewer-reproduced | The four windows, including n = 48 and partial +0.43 (p = 0.002), are in §B.2. Sweep presence is not treated as pickup. |
| 3 | Applied | Header and §B.1 use 121 rows, 17 A and 38 B. §B.1a has one line per A and B id. Rank tiers match the catalog letters the review named. Ranges are labeled judgment and are not added. |
| 4 | Applied, reviewer-reproduced | Persistent noise stays 27–31 percent. Independent-noise rates of about 23 percent at n = 90 and 17 percent at n = 200 are attributed to the reviewer's re-run. "At any sample size" is gone. |
| 5 | Applied | The formula is pointed at §B.1. The text says the ranges share one ceiling and that f, q, and σ² are not shown per row. |
| 6 | Applied | Design 2 returns to the no-stream rule on stale, missing, or non-JSON market pace. |
| 7 | Partly | Appendix A is an honest log of this pass. It does not invent a query list. The DataEDGE link is replaced with the Economic Record DOI. The PDF was not re-opened. |
| 8 | Partly | Fiig, Weatherford and Wittman 2019 is cited next to Pölt, from the review, with the airline-simulation bound. Pölt stays UNVERIFIED. The PDF was not re-opened. |
| 9 | Applied, reviewer-reproduced | §B.2 states the 65.2 percent failed-row count and the 0–8 percent December–March coverage as the reviewer's count. Design 1 says a stored available flag mixes bookings and host blocks. |
| 10 | Applied | §B.1 now says which of the top streams a generic calendar tool already approximates. |
| 11 | Applied | The self-audit no longer marks a family disposition or a frozen target as a pass. |
