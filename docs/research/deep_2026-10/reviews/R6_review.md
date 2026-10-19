# R6 review: data-value ranking

Reviewer: adversarial review (V_REVIEW.md). Date: 2026-10-17. Access date for URLs opened in this review: 2026-10-17.
Dossier reviewed: `docs/research/deep_2026-10/R6_data_value_ranking.md`.
The prior `reviews/R6_review.md` was a stub and is not used as evidence.
Reproduction: author scripts under `/private/tmp/wp_research/r6/` were re-run with the project interpreter in isolated mode (`python -I`). System `python3 -I` has no NumPy, so the venv interpreter was used; the scripts themselves were not edited. The operator database was opened read-only (`mode=ro&immutable=1`). Only `signal_scores` and scrape-status aggregates were read. No guest fields, booked revenue, Guesty ids, or names appear below.

## 0. Verdict

**ACCEPT WITH FIXES.**

Comp-data repair as rank 1 survives, and the store makes that conclusion stronger than the inherited “about 67%” line. The value-of-information arithmetic, the promotion-ladder Monte Carlo cells that are printed, the information coefficient of 0.937, the 72-day winter lead time, and the H4 bound are real. The close does not match the scripts that were actually run: lagged weekly snow does not improve a traffic forecast, A- and B-tier streams are dispositioned as families, and the header still describes an older catalog.

## 1. Reproduction of the load-bearing numbers

| Claim | Result | Reviewer note |
|---|---|---|
| EVPI ceiling ≈ 3–5% from k = 0.75 and σ = 0.20–0.25, loss ≈ k·E[ε²] | **Re-derived. Holds as a second-order ceiling.** | 0.75 × 0.20² = 3.0%; 0.75 × 0.25² = 4.7%. For linear demand, π = p(a − bp), the loss relative to π* equals (e^ε − 1)², which is ε² at second order. For exponential demand q = e^{−p/θ}, the second-order loss is ε²/2, so k ∈ [0.5, 1] and k = 0.75 is the midpoint the text says it is. Using E[(e^ε − 1)²] for a normal log-price error gives about 3.2% at σ = 0.20 and 5.2% at σ = 0.25. The 0.2% worked example in §A.4 also checks: 0.75 × (0.10² − 0.085²) = 0.21%. The formula is a ceiling on price-level error. It is not applied row by row. |
| Ladder null gate, 4,000 draws, “about 27–31% at any sample size” | **The printed cells match. The sentence does not.** | Re-run, seed 7: n = 40 independent 0.274 (null IC 97.5th = 0.309); n = 40 persistent 0.297 (0.564); n = 90 persistent 0.305 (0.405); n = 200 persistent 0.285 (0.290). The same script, omitted from the table, gives independent-noise promotion of **0.232 at n = 90 and 0.171 at n = 200**. “At any sample size” is the persistent-noise case only. Level-outcome false promotion re-ran at 0.123 (persistent) and 0.028 (iid), inside the stated 3–12%. |
| `calendars.demand_strength` IC = 0.937 (n = 91), hit rate 0.011 | **Verified in `signal_scores`.** | Read-only row: IC 0.9367, n = 91, hit rate 0.01099 (1/91), horizon 14 days, decision `hold`. |
| 17 distinct A-tier streams, not 18 | **The current file has 17 A rows. The dossier’s count story is the old catalog.** | `R5_catalog.csv` parsed with `csv.DictReader`: **121 rows, 20 columns, 17 A / 38 B / 66 C.** No duplicate ids. L13 is absent. W03 and W04 are both B. The header still says “116 streams; 18 A, 37 B.” The body says 17 A “after de-duplicating W03/W04” and “37 B.” See §5. |
| Winter lead time ~72 days (AirROI), not the 15-day mixed-season median | **Supports.** | AirROI, 29 July 2026, winter 2025-26 average booking lead time: “Winter Park at 72.” Used in C1 and as the §A.8 carryover. Vendor, whole-market listings. |
| H4 winter elasticity +0.06 [−0.07, +0.19]; effective n ≈ 23; 30% gas rise bounded ~4% of traffic | **The bound is used. The point estimate is not restated.** | C10 and §B.2 say the winter coefficient is near zero, effective n ≈ 23 seasons, and a 30% gas rise is bounded at about ≤4% of access traffic. That is the R7 review’s recommended wording (author NW interval +0.058 [−0.070, +0.185]; 0.13 × 0.30 ≈ 4% on the wider monthly lower bound). |
| Town lodging Nov–Apr 71.7% | **Inherited, previously reproduced. Not re-opened here.** | R7 review §1 reproduced 71.7% exactly from the town reports (five seasons, 69.5–72.8). R6 cites no URL of its own. Town remittance, not these homes’ revenue. |
| Comp scrape ~67% row failure; calendar availability fetched but not stored | **Code supports the second clause. The 67% figure is a stale mix of rows.** | Read-only `comp_snapshots`: 27,020 rows; `failed` 17,612 (65.2%), `unavailable` 7,686 (28.4%), `ok` 1,722 (6.4%). Every `failed` row is source `manual`. Airbnb-sweep rows are `ok` or `unavailable` (absence from the search tile). `_enrich_min_nights` writes `min_nights` only. `available` is 1 on `ok` and 0 on `unavailable`. Dec 2026–Mar 2027 nights with at least three comps no older than 42 days: about 0%, 0%, and 8% across the three homes. Rank 1 still holds. |
| One booking moving pace ~+8% | **Re-derived from `pace.py`.** | At 120 days the curve share is 0.12. With peak final occupancy 0.70, expected on-books is 0.084. Index (on_books+0.05)/(expected+0.05) goes from about 0.37 at zero bookings to about 0.73 when one night in a 21-night window (three homes × ±3 days) flips. Multiplier `1 + 0.30×(index−1)`, clamped at 0.85, goes 0.85 → 0.919, which is +8.1%. |
| AirROI drought: occupancy 44.9% → 35.8%, ADR +22.2% | **Supports, whole-market.** | Same table: ADR $455 → $556 (+22.2%), RevPAR −4.7%, supply +9.9%. Those ADRs are the market panel, not the luxury tier. |
| Owner share 0.595 | **Not used as a number.** | `owner_terms` in `pace.py` is `1 − channel_fee − management_fee` = 1 − 0.155 − 0.25 = 0.595. A constant share scales payoff and loss together, so the percentage ceiling does not change. |
| Top 10, comp-data repair at #1 | **Yes, in §B.1.** | The ranges are ordinal judgment under the ceiling. They are not a computed EVPI per stream. |
| Comp-fill endogeneity | **Acknowledged, then left unquantified.** | §B.2 says sweep presence conflates booked with “not in this tile,” and design 1 asks for an endogeneity world. The store lead-lag numbers are not in the dossier. |
| Lead-lag tests honest about n | **No. See §5.** | Gas “23 seasons” is the R7 monthly effective n. The weekly scripts use 120 weeks and 7 test seasons, and the season-level snow correlation uses 8 seasons. |

## 2. Repo claims, read from the code

| Claim | Verdict | Where |
|---|---|---|
| IC target is a revenue level, lines cited around `score_signal_against_outcomes` | **Correct** | `src/eval/backtest.py` 191–244. The outcome is the portfolio average of booked revenue on the stay date 14 days ahead. A seasonal signal can rediscover the season. |
| Hit rate skips zeros in the numerator and keeps them in the denominator | **Correct** | `hit_rate` at lines 98–107. `hits / len(pairs)`. The stored hit rate 0.011 with IC 0.937 is what that function produces. |
| `signals.yaml` gate is IC ≥ 0.05 and hit rate ≥ 0.52 | **Correct** | `shadow_to_active`: n ≥ 40, IC ≥ 0.05, hit rate ≥ 0.52. Deprecation at IC ≤ −0.02. `src/signals/promotion.py` reads those keys. |
| Calendar `available` is fetched and not stored | **Correct** | `providers.py` returns `available` and `min_nights`. `_enrich_min_nights` updates `min_nights` only. Sweep presence sets `comp_snapshots.available`. |
| Cotrip collector can store a silent zero | **Correct, by reading the parser** | `cotrip.py` requests `cotrip.org/api/alerts`. A non-JSON body is parsed as text. If the shell contains none of the keywords, the flags are 0. `cdot.py` stores that at `QUALITY_OK`. This review did not re-fetch the live URL; R5’s live call already did. |
| Open-Meteo gusts ×2.237 | **Correct, and the default unit is km/h** | `weather.py` multiplies `wind_gusts_10m_max` by 2.237 and does not set `wind_speed_unit`. Open-Meteo’s docs default that parameter to `kmh`. The factor 2.237 is m/s → mph; km/h → mph is 0.621. The test comment still says “m/s.” |
| Pace is a multiplicative multiplier | **Correct** | `pace_multiplier` is `clip(1 + 0.30×(index−1), 0.85, 1.25)` applied to the reference. Design 2’s warning against multiplying that ratio by a second market ratio matches the code. |
| `comp_movement.py` writes a 14-day lift row | **Correct, with a narrower meaning** | A row is written only when median listed-price lift clears 8%, 15%, or 25%, mapped to strengths 0.55, 0.70, and 0.85. The store has 53 such rows. “A lift exists” is true. The stored number is a threshold score, not the lift. |

## 3. Citation spot-check

Twenty-three cited items were opened or, where the fetch was blocked, checked by a direct search for the same work. The dossier has 34 distinct URLs, which clears the “20 new sources” count on its face. Classes present in those URLs and the named books: academic journals, textbooks (Raiffa & Schlaifer; Grinold & Kahn), a vendor page (AirROI), and practitioner material (the CFA reading and the CUPED note). Government statistics in this dossier are mostly inherited from R7.

| # | Claim as used | What was opened | Result |
|---|---|---|---|
| 1 | Winter Park winter lead time 72 days; occupancy 44.9% → 35.8%; ADR +22.2% | AirROI, 29 July 2026, ski-market booking-pace post | **Supports** the three figures, plus RevPAR −4.7% and supply +9.9%. Whole-market ADR is about $455–$556, not the luxury tier. Vendor. |
| 2 | Strong, Oakley & Brennan 2014 estimate partial EVPI by regressing simulated payoff on the input | PMC4819801 | **Supports.** Nonparametric regression on a probabilistic sensitivity sample; GAM and Gaussian process. |
| 3 | Unrestricted permutation forces extrapolation and can mislead | arXiv 1905.03151 (Hooker, Mentch & Zhou) | **Supports.** The paper’s remedy is another model, which is the drop-column refit R6 recommends. |
| 4 | SHAP gives additive per-prediction attributions | `papers.nips.cc/paper/7062-a` | **Supports.** The page resolves. Lundberg & Lee, NIPS 2017. “Useless for buying data” is the dossier’s inference, and it is the right inference. |
| 5 | Shapley importance has mathematical problems that need a causal fix | arXiv 2002.11097v2 (Kumar et al.) | **Supports.** |
| 6 | IC is residual-return correlation; IR = IC·√breadth | CFA Institute 2025 refresher reading | **Partly.** The reading defines the information coefficient, breadth, and the information ratio, and it also includes the transfer coefficient. The bare IR = IC·√breadth is Grinold’s original form. |
| 7 | In the 1,311-series tourism competition, pure time series beat models with explanatory variables | Hyndman’s competition page | **Supports.** 366 monthly + 427 quarterly + 518 yearly = 1,311. “Pure time series approaches provide more accurate forecasts … than models with explanatory variables.” |
| 8 | A 2022 re-analysis says most claimed findings are still likely true | arXiv 2206.15365 (Chen) | **Partly.** The paper’s own title and abstract say that, for published cross-sectional stock-return predictors, with an FDR bound of about 9–25%. It is not a result about an unpublished pricing-stream screen, and it does not lower the hurdle for this engine. |
| 9 | Howard 1966, information value depends on consequences, not only probabilities | synapsesocial.com record of the paper | **Partly.** The abstract matches. The host is a secondary copy, not the IEEE original. |
| 10 | CUPED cut Bing’s variance by about 50% | exp-platform.com/cuped | **Supports.** Deng, Xu, Kohavi & Walker, WSDM 2013. “Reduce variance by about 50%.” |
| 11 | Google Trends did not beat time series for Spanish rural overnight stays | Cebrián & Domenech 2024, Journal of Tourism Management Research | **Supports.** January 2012–February 2020; models with a Trends predictor did not beat a naïve or non-seasonal Holt–Winters forecast. |
| 12 | Hansen’s SPA test (2005, JBES 23:365–380) discounts clearly bad models | The cited IDEAS URL | **Partly.** That URL is Brown working paper 2001-06. The 2005 JBES article is the published version and does say the test is less sensitive to poor alternatives. The journal page is a different URL. |
| 13 | Ban & Keskin 2021: regret grows like s√T in the number of features that matter, and only logarithmically in the number screened | SSRN 2972985 and the Management Science abstract | **Supports** the rates: lower bound order s√T; unknown predictors give order s√T(log d + log T). “Perhaps three or four learned factors” is the dossier’s judgment from ~100 bookings, not a theorem in the paper. |
| 14 | Granger: past x improves the forecast of y; apparent instantaneous causality often comes from slow recording | Econometric Society page, Econometrica 37(3):424–438 | **Supports.** |
| 15 | White’s Reality Check tests whether the best of many models beats a benchmark after the search | Econometric Society page, Econometrica 2000 | **Supports.** |
| 16 | Choi & Varian 2012 nowcasts travel with Google Trends | The cited Berkeley DataEDGE URL | **Does not.** The page is a 31 May 2012 keynote listing for Hal Varian. It does not name Choi, the Economic Record paper, or tourism. The paper is real; this link is the wrong document. |
| 17 | Harvey, Liu & Zhu: a new return factor needs t > 3 | NBER w20592 | **Supports** the t > 3 hurdle. The same abstract says most claimed findings in financial economics are likely false. That sentence belongs to Harvey, not to the Chen paper. |
| 18 | Open-Meteo wind speed defaults to km/h | open-meteo.com docs | **Supports.** `wind_speed_unit` default `kmh`; alternatives `ms`, `mph`, `kn`. |
| 19 | Cornish-Adebiyi v. Caesars (3d Cir., 29 July 2026) reinstated an algorithmic-pricing case built on nonpublic data | Justia / court opinion reports | **Supports.** Pleading-stage reversal. Nonpublic room rates and occupancy into a shared algorithm. It does not hold that every shared tool is unlawful. |
| 20 | Weatherford & Belobaba 2002: forecast accuracy matters most, and some input errors can help EMSR | Journal of the Operational Research Society abstract, 53(8):811–821 | **Supports** the abstract. Full text not opened (paywall). |
| 21 | Strobl et al. 2008, conditional permutation | PMC2491635 | **Dead to this reviewer (HTTP 403).** A DOI search returns the same paper and the conditional-permutation claim. Not a fabricated citation. |
| 22 | Bojinov, Simchi-Levi & Zhao: switchbacks with carryover | arXiv 2009.00148v4 | **Supports.** Design and analysis of switchback experiments, including temporal interference. |
| 23 | Pölt 1998: a 20% cut in forecast error yields about 1% revenue | Author marks this UNVERIFIED | **Does not locate the primary.** Secondary citations exist (Talluri & van Ryzin, via a hospitality paper; a 2002 Pölt tutorial says about 10% accuracy → 1–2% revenue, up to 4% on high-demand flights). The 1998 AGIFORS paper was not found. The UNVERIFIED label should stay. |

**Tally (23): supports 16, partly 4, does not 2, dead 1.** No fabricated citation in this set.

## 4. Depth audit

The author’s self-audit is not accepted as evidence.

| MUST | Reviewer | Note |
|---|---|---|
| Inline URL or full reference, plus an access date | **PASS, with one bad link** | Header access date 2026-10-16. Thirty-four distinct URLs. Choi’s link does not carry the claim (§3.16). Tashman 2000 is named without a URL. |
| ≥ 20 new sources, plus the upstream dossiers | **PASS** | 34 URLs in this file, on top of R1–R5 and R7. Several are abstracts or IDEAS records rather than the paper. |
| At least four source classes | **PASS** | Academic, textbook, vendor, practitioner. Industry-body material is the missing Pölt/AGIFORS paper. Little new government data in this file; R7 carries that. |
| Primary sources where they exist | **PARTIAL** | Strong, Hooker, Kumar, Granger, White, Harvey, Chen, CUPED, and the tourism-competition abstract were opened. Weatherford & Belobaba is the abstract. Pölt’s primary was not found. The Choi link is not the paper. |
| Mark UNVERIFIED and STALE; invent nothing | **PASS on the labels that are there** | Pölt is UNVERIFIED. Lee 1990 is STALE and “via R1, abstract only.” Parthum is corrected off the season multiplier. The failure is omission and overclaim (§5), not a made-up paper. |
| Broad, specific, and adversarial search passes, with a query log | **FAIL** | Appendix A is one paragraph. It names topics. It does not list queries or what each query returned. A reviewer cannot audit the search. This review’s own searches are in §6. |
| Mechanisms an engineer could implement | **PASS for Part A** | EVPI expansion, residual IC, BH threshold, rolling-origin targets, and the proposed ladder are concrete. The §B.1 scores do not show f, q, or σ², so the formula is not yet an implementation. |
| Quantified impact, and who measured it | **PARTIAL** | Airline ranges are sourced and partly conflicted (Pölt). The top-10 owner-net ranges are judgment. AirROI is a vendor. |
| Map to a module and an owner-net measurement | **PASS** | Designs name the anchor, the pace multiplier, the ceiling, min-stay, and paired seeds in `proving_ground_exam`. The 33% MDE is treated as a reason to stay in shadow. |
| Transferability to three homes | **PASS** | Search data, airline forecast-to-revenue rules, and “three or four learned factors” are fenced. Ban & Keskin is a many-customer personalized-pricing model; the dossier uses the rate, not the auto-loan 47% result. |
| “What generic STR pricers miss” (H2) | **FAIL** | No such note. The ranking implies comps, calendars, and local state. The prompt asked for the note where H2 is in scope, and H2 is half of this dossier’s question. |
| Ranked recommendations, open questions, self-audit | **PARTIAL** | The top 10, the open questions (feed cost, US-40 station, competition law), and a self-audit are present. The self-audit marks “every A/B stream scored” and “lead-lag n” as PASS. Both are wrong (§5). |
| R6: score every A and B stream | **FAIL** | Family rows and a remainder sentence. See §5. |
| R6: cheap lead-lag checks with honest n | **FAIL** | Scripts exist and were re-run. The dossier does not report their n, and one summary contradicts the out-of-sample results. |

## 5. Reasoning, and the orchestrator’s questions

### 17 streams, not 18

The current catalog has **17 rows whose tier starts with A**, and **38 whose tier starts with B**, in **121** rows. The distinct A ids are L01, L02, L06, L07, L09, W01, W08, A01, C01, C02, C04, C05, R01, R02, P04, X01, and Z04.

The dossier uses 17 in the body and in the self-audit, and it uses 18 and 37 in the header (“116 streams; 18 A, 37 B”). The explanation “after de-duplicating W03/W04” describes the catalog the R5 review saw. In the file on disk, W03 and W04 are both B, and L13 is gone. Treating 17 as the A-tier count is right. Treating the path to 17 as a de-duplication, and leaving 37 B in the scoring sentence, is not.

The ranking table then mis-labels tiers against that file. Rank 9 calls gasoline A; E01 is B and E02 and E04 are C. Rank 8 calls DEN capacity A; A08 is B and A06 and A09 are C. Rank 6 includes A13, which is C. Rank 10 includes L11 and several S-rows that are C. Rank 7’s R03 and R04 are both B, which the “A/B” label half-admits.

### 72-day lead time and the H4 bound

Both corrections are used. C1 replaces the 15-day mixed-season median with AirROI’s 72-day winter lead time and says far-out streams (snow state, passes, school calendars, market pace) cover more of the booking curve. §A.8 uses about 72 days as the carryover window for a switchback. C10 and rank 9 use the corrected gas bound: no winter effect detected, about ≤4% of access traffic for a 30% gas rise, effective n ≈ 23 seasons. The point estimate +0.06 [−0.07, +0.19] is not reprinted; “near zero” plus that bound is the right wording.

### Comp-fill endogeneity

Acknowledged in C2, in §B.2, and in design 1’s “endogeneity world.” The check that would show it is not reported. Re-running `b3_leadlag.py` on sweep presence versus own pickup:

| Window | n stay-nights | Raw rank correlation | Partial, after lead, calendar, weekend |
|---|---:|---|---|
| 21 Sep → 17 Oct | 44 | −0.03 (p = 0.91) | +0.10 (p = 0.62) |
| 25 Sep → 17 Oct | 46 | −0.01 (p = 0.99) | +0.03 (p = 0.86) |
| 30 Sep → 17 Oct | 48 | +0.29 (p = 0.11) | **+0.43 (p = 0.002)** |
| 5 Oct → 17 Oct | 50 | +0.04 (p = 0.83) | +0.09 (p = 0.60) |

Three coincident windows (n = 42–44) have correlations between −0.03 and +0.10. One partial correlation in four looks is large. That is a multiple-testing candidate, not a pace feature. Publishing only “a 14-day median price lift exists” hides both the nulls and the one sharp window.

A second endogeneity remains after the calendar is persisted. A public calendar does not separate a booked night from a host block (Inside Airbnb’s data assumptions; the 2024 PLOS One daily-scrape paper). Design 1 should say that a persisted `available` flag is still an upper bound on occupancy.

### Lead-lag n, and what the snow scripts actually say

§A.3 promises that “§B.4 shows these give opposite answers on our data.” There is no §B.4. The completed empirical section is §§B.1–B.3.

§B.2 says “Snow dominates fuel in the observed winter regressions” and gives the gas check an honest seasonal n. It does not give the n of the weekly tests in `b4_granger.py` and `b5_season.py`. Re-run results:

- 196 full weeks, 23 January 2016 through 18 April 2026. Granger samples are **n = 120 weeks**, not 23 seasons.
- SWE-anomaly lags 1–3 → traffic: F = 0.30, season-permutation p = 0.731.
- New-snow lags 1–3: F = 1.91, p = 0.053.
- Real-gas lags 1–3: F = 1.54, p = 0.070.
- Out of sample, 89 test weeks and **7 seasons**: adding the SWE anomaly changes MAE by **−0.7%** (worse; 3 of 7 seasons improved). Lag-1 SWE: **−3.5%** (1 of 7). Lag-1 gas: **+0.8%** (4 of 7). SWE and gas together: **−9.8%** (3 of 7).
- At horizons of 2, 4, 6, and 8 weeks, adding SWE made MAE worse by 5.5%, 4.7%, 4.4%, and 8.2%. In-sample SWE slopes in that script are still positive (about +0.7% to +1.2% per inch). The forecast does not inherit them.
- `b5_season.py`: early-season SWE versus detrended January–March log traffic, **n = 8 seasons**. Dec-1 r = +0.55 (+3.2%/in); Dec-15 r = +0.12 (+0.8%/in); Jan-1 r = +0.71 (+3.6%/in).

Lagged weekly SWE does not improve a traffic forecast in these scripts. Snow can stay a seasonal state and a simulator world, which is what design 3 already says (“do not fit a season multiplier”). It cannot be described as a demonstrated lead of the pace residual. The R7 contemporaneous snow coefficients are a different specification and should be cited as that, with their own n.

The season-permutation block in `b4_granger.py` resizes seasons of unequal length. The out-of-sample MAE comparison does not use that permutation, and it is the result that contradicts the summary sentence.

### Does every top-3 design fail safe?

Designs 1, 3, 4, and 5 do. Missing or non-JSON comps fall back to the seasonal anchor and may not raise price above the internal ceiling. Missing snow holds the neutral prior. Missing events make no adjustment. Missing pass data leaves the reference-price feature neutral.

Design 2 does not. Missing or delayed market pace “freezes the last qualified target and increases uncertainty rather than cutting price.” A frozen high target is still a directional multiplier. Stale data has to return the price rule to the no-stream decision, not hold the last pace ratio.

### Did it score every A- and B-tier stream?

No. §B.1 is ten family rows plus one sentence on “the remaining A/B streams.” The self-audit calls that a PASS because “the catalog is the row-level inventory.” The prompt asked for a score on each A and B stream: mechanism, decision frequency, confidence, cost, effort, and whether it is already in the repo.

A-tier rows with no own line include L02 (inquiries), L07 (AirDNA, folded into “buy a feed”), P04 (lodging tax, used only as a check), X01 (substitute-resort snow, placed in the remainder), and Z04 (cancellations). W01 is inside the snow family. The 38 B rows are not scored. That is a fix, not a pass.

### Other overclaims

The top-10 upper bounds add to well above the 3–5% ceiling (about 4 + 3 + 2 + 2 + 1.5 + 1.5 + 1 + 0.8 + 0.4 + 0.5). §A.1 says independent errors add in variance and that the ceiling is for all information together. §B.1 does not say the ranges overlap. A reader can add them.

§A.1 calls the formula “the scoring core of §B.2.” §B.2 is the empirical table. The scores in §B.1 are ordinal. No stream shows an f, a q, or a σ².

Screening “55” A- and B-tier streams matches 17 + 38 by accident and matches the header’s 18 + 37 by construction. The false-promotion count of about 15 uses 0.27 × 55. It should be recomputed on the persistent-noise rate only, and only after the catalog count is fixed. The arithmetic is the same number either way; the label should still be fixed.

The forecast-to-revenue section misses the paper that actually tries to close that link: Fiig, Weatherford & Wittman, *Journal of Revenue and Pricing Management* 18(4):291–305 (2019). They report that earlier work had not established the link, and that a ±10% elasticity-parameter bias cuts revenue by up to about 1%, and ±20% by up to about 4%. That sits next to R6’s own 3–5% ceiling and should be cited. Pölt stays UNVERIFIED.

## 6. Coverage against the prompt, and this reviewer’s searches

| Prompt item | Status |
|---|---|
| VOI, EVPI, EVPPI, EVSI | Covered, with a usable expansion. |
| Permutation, SHAP, and the ladder’s IC | Covered, and the code audit is right. |
| Granger and lead-lag | The rules are covered. The application is not (§5). |
| Forecast error → revenue, including Weatherford & Belobaba and Pölt | Weatherford’s abstract is used fairly. Pölt is honestly UNVERIFIED. Fiig, Weatherford & Wittman 2019 is missing. |
| Nowcasting, Choi & Varian, Athanasopoulos 2011 | The competition result is right. The Choi link is the wrong page. The rural-Trends failure is right. |
| White, Hansen SPA, FDR, and a raised hurdle | Covered. Chen’s equity FDR bound is aimed at the wrong literature. |
| Pooling, hierarchical forecasts, thin-data proxies | Covered. |
| Protocol: targets, leakage, metric chain, ladder | Covered and concrete. |
| Score every A and B stream | Missing as rows. |
| Cheap lead-lag with sample sizes | Scripts ran. The dossier does not report them. |
| Top 10 and top 3–5 designs, including comp repair | Present. Design 2’s stale-data rule is the hole. |
| H2, what generic pricers miss | No note. |

This reviewer’s own searches (12), and what they added:

1. AirROI winter 2026-27 booking pace — confirmed 72 days and the drought table.
2. Weatherford & Belobaba 2002 — abstract supports “accuracy matters most; some errors can help.”
3. Pölt 1998 AGIFORS “20% → 1%” — primary not found; secondary rules of thumb differ (10% → 1–2%).
4. Ban & Keskin 2021 regret — s√T and s√T(log d + log T) confirmed.
5. Open-Meteo `wind_speed_unit` — default `kmh`.
6. Hansen SPA 2005 versus working paper 2001-06 — the cited URL is the working paper.
7. EVPI and quadratic price-error loss — the second-order loss is standard; no STR-specific EVPI paper turned up that replaces §A.1.
8. Cebrián & Domenech 2024 — rural Google Trends did not beat time series.
9. Cornish-Adebiyi v. Caesars, 29 July 2026 — the reinstatement is real and is about nonpublic inputs.
10. Permutation and SHAP critiques — Strobl, Hooker, and Kumar support the dossier’s caution.
11. Fiig, Weatherford & Wittman 2019 — the missing forecast-accuracy paper (§5).
12. Airbnb search absence versus a booked night — calendar “unavailable” includes host blocks (PLOS One 2024; Inside Airbnb). Persisting the calendar does not finish the occupancy measure.

## 7. Verdict

**ACCEPT WITH FIXES.**

Part A is a real ranking method: the ceiling arithmetic checks, the ladder Monte Carlo cells that are printed check, the code audit of the IC and the hit rate checks, and the opened method papers support the claims attached to them. Rank 1 is the right operational conclusion. The current store shows Dec–Mar anchor coverage of about 0–8% of nights, which is a tighter statement than “67% of rows fail.”

The dossier is not ready to hand to an implementer until the empirical close matches the scripts, the catalog on disk is the catalog being scored, and each winning design fails safe when the feed is stale. Those are edits to this file, not a new research program.

## 8. Numbered fix list

1. **Report the lead-lag scripts, and withdraw “snow dominates” as a forecast claim.** Put the `b4` and `b5` numbers in §B.2: n = 120 weeks, 7 out-of-sample seasons, SWE lags not significant (p = 0.73), out-of-sample SWE changes of −0.7% to −9.8%, and the 2- to 8-week horizons all worse. Put the `b5` correlations at n = 8. Keep snow as a seasonal state and a simulator world. Cite the R7 contemporaneous snow coefficients separately, with their own n. Delete the pointer to §B.4 or write that section.
2. **Publish the four `b3` windows**, including n = 44–50 and the one partial correlation of +0.43 (p = 0.002). Treat that window as one of four looks. State that sweep presence is not a pickup feature on this sample.
3. **Score the current catalog, row by row.** It is 121 rows, 17 A and 38 B, not 116 / 18 / 37. Drop the “de-duplicate W03/W04” sentence. Give every A id and every B id a line: expected owner-net range, confidence, cost, effort, already-in-repo, and the decision (build, shadow, scenario, or drop). Fix the tier letters on ranks 6–10, including E01 as B and A06, A09, A13, and L11 as C. Until that table exists, the self-audit row “every A/B stream scored” is a fail.
4. **Qualify the Monte Carlo.** Say 27–31% for persistent noise. Add the omitted independent-noise rates: about 23% at n = 90 and 17% at n = 200. Delete “at any sample size.”
5. **Make the owner-net ranges shares of one 3–5% ceiling.** Say they overlap and must not be added. Either show f, q, and σ² for each row or label the range as judgment under the ceiling. Point the formula at §B.1, not §B.2.
6. **Design 2 fails safe.** On stale, missing, or non-JSON market pace, the multiplier returns to the no-stream rule. A frozen last target is not that rule. Keep the “do not multiply pace by a second market ratio” warning.
7. **Replace Appendix A with a search log:** each query, and what it returned. The depth standard requires it. The Choi & Varian link has to be the Economic Record paper or a real abstract, not the DataEDGE schedule.
8. **Cite Fiig, Weatherford & Wittman 2019** next to Pölt. Keep Pölt UNVERIFIED. Use the 2019 elasticity-bias results (±10% up to about 1% revenue, ±20% up to about 4%) as the published bound, and say they are airline simulations.
9. **Correct the scrape sentence.** Current read-only counts: 65.2% of rows are `failed`, and those rows are source `manual`; Airbnb-sweep rows are `ok` or `unavailable`. Dec–Mar nights with at least three fresh comps are about 0–8%. Rank 1 stays. Add that a stored calendar flag still mixes bookings and host blocks.
10. **Add the H2 note** in a short paragraph: which of the top streams a generic comp pricer does not collect, and which of them it already approximates with a calendar.
11. **Rewrite the self-audit** so rows 2, 3, and 7 of the depth table above are FAIL until fixes 1, 3, 6, and 7 land. Do not mark the family remainder as a full score.

No code, no commit, and no live price change is required for any of these.

## Addendum: close-out, 2026-10-19

- The out-of-sample sign question is settled: `b4_granger.py` (re-run 2026-10-19) prints a signed
  "relative reduction", so −0.7% means error 0.7% **worse**. Adding lagged snow makes traffic-forecast
  MAE worse by 0.7–3.5%, snow plus gas by 9.8%, and 4.4–8.2% at 2–8-week horizons; lagged gas alone
  improves it 0.8%. R6 §B.2 now says this explicitly. These are forecast errors, not revenue effects.
- R6's sections were out of order (Parts B and C above Part A, five empty stubs at the end); they were
  reordered with no text change.
- A code-status note records commit `d3e8b92` beside corrections C4 and C5.
