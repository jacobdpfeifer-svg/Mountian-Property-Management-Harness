# R7 — Winter Park demand drivers: testing the practitioner hypotheses with real data

Date: 2026-10-16. Author: R7 research agent. Access date for every web source: 2026-10-16 unless stated.
Status: fix pass recorded in Appendix C (2026-10-17). The 2026-10-17 audit propagated the H4 verdict into the glance lines and §2.7. The 2026-10-19 close-out applied the remaining review fixes to the body (Appendix C has one row per fix); the reviewer's robustness script was re-run and the comp-tier figures re-queried read-only on 2026-10-19.

Scratch analysis (outside the repo): scripts in `/private/tmp/wp_research/scripts/`, downloads in
`/private/tmp/wp_research/data/`. Only results and source URLs are recorded here. No booked revenue,
Guesty ids or guest data appear in this file.

## Verdicts at a glance

H1 PARTLY SUPPORTED · H4 no winter effect detected, bounded small; summer suggestive only · H5 SUPPORTED for Winter Park
lodging with winter = Nov–Apr (71.7%), PARTLY otherwise · H7 PARTLY SUPPORTED. Full table with
headline numbers: section "Verdicts at a glance (detail)" near the end.

## 1. H5 — seasonality ("about 70% of annual revenue is earned in winter")

### 1.1 Data

- Colorado Department of Revenue (DOR), *State Sales Tax Return Data by City* (2016–2020 and
  2021-to-date) and *by County* (2016–2019 and 2020-to-date), monthly gross, retail and state net
  taxable sales, linked from https://cdor.colorado.gov/retail-sales-reports (Google Sheets/xlsx).
  Downloaded 2026-10-16; coverage January 2016 – July 2026, 127 months per area.
- DOR caveat (from the same page): some retailers file quarterly or annually, so quarter-end months
  (Mar, Jun, Sep, Dec) carry several months of sales for those filers. The 2016–2020 city file is in
  thousands of dollars; the 2021+ file is in dollars; season shares are computed within a season
  and are unaffected by the unit change, but the 2020-21 season straddles the files. Quarterly filers
  are **not** neutral for the share: under Nov–Apr, the June quarter-end spike moves April sales out of
  winter and the December spike moves October sales in. The net bias is small and of unknown sign.
- State net taxable sales is the best public proxy for visitor spend (lodging, restaurants, retail;
  lodging is taxable in Colorado). It is not lodging alone: DOR does not publish Grand County or
  Winter Park by industry (its county-by-industry tables cover only 11 major counties).

### 1.2 Result — winter share of state net taxable sales, season-years May–April

Season-years 2016-17 … 2025-26 (n = 10; "ex-COVID" drops 2019-20 and 2020-21).

| Area | Dec–Mar share (mean, range) | Dec–Mar ex-COVID | Nov–Apr share (mean, range) | Nov–Apr ex-COVID |
|---|---|---|---|---|
| Town of Winter Park | 56.8% (50.8–62.3) | 57.6% | 67.7% (63.7–71.8) | **68.5%** |
| Town of Fraser | 38.0% (36.3–40.4) | 38.4% | 51.6% (50.6–53.6) | 51.8% |
| Grand County | 37.0% (35.0–39.1) | 37.4% | 48.9% (46.8–50.9) | 49.3% |
| Granby | 30.8% | 30.7% | 44.2% | 44.1% |
| Vail (town) | 57.4% | 57.8% | 66.4% | 66.9% |
| Breckenridge (town) | 51.4% | 52.1% | 62.8% | 63.4% |
| Aspen (city) | 47.6% | 48.5% | 56.1% | 56.9% |
| Steamboat Springs | 43.4% | 43.9% | 55.2% | 55.5% |

(Retail-sales basis, Town of Winter Park: Dec–Mar 66.4%, Nov–Apr 76.9% ex-COVID.)

Town of Winter Park by season (taxable, Dec–Mar / Nov–Apr): 2016-17 62.3/71.1; 2017-18 61.5/71.4;
2018-19 61.2/71.8; 2019-20 56.3/64.6; 2020-21 50.8/63.8; 2021-22 56.2/68.4; 2022-23 56.5/68.7;
2023-24 56.1/67.2; 2024-25 54.5/66.0; 2025-26 52.9/63.7.

Average month share of the Town of Winter Park season-year (taxable, ex-COVID): Dec 14.1%, Jan 14.1%,
Feb 13.5%, Mar 15.9%, Apr 5.6%, May 2.9%, Jun 5.3%, Jul 7.6%, Aug 6.0%, Sep 5.8%, Oct 3.9%, Nov 5.3%.

Trend: winter (Nov–Apr) taxable sales in the town rose about 2.0× from 2016-17 to 2024-25 (nominal) while
May–Oct (of the following calendar year) rose about 2.3×, so the winter share is drifting down by roughly 0.5–0.7 points a year.
2025-26 winter taxable sales fell about 10% from 2024-25 (a low-snow season; see H4).

### 1.3 Result — lodging only: Town of Winter Park lodging-sector sales tax

The Town of Winter Park publishes a monthly sales-tax report with a **lodging sector** series
(https://wpgov.com/our-government/departments/finance/sales-tax/; December 2025 report:
https://wpgov.com/wp-content/uploads/2026/02/2025-12-Sales-Tax-Report-collected-Jan-26.pdf; August 2026
report: https://wpgov.com/wp-content/uploads/2026/10/2026-08-Sales-Tax-Report-collected-Sep-26.pdf).
The December 2025 report carries the "Total sales tax – lodging" row for every month of 2020–2025;
the 2026 monthly reports give January–August 2026 (April 2026 is an image-only PDF; April was
derived as May YTD − March YTD − May). The lodging tax rate rose on 1 July 2024 (accommodation tax
1% → 3%, so the lodging total went from 7% to 9%: 4% general + accommodation + 2% transit & trails,
per the town's rate page). I converted tax to an implied lodging-sales base by dividing by the rate
in force.

| Season-year (May–Apr) | Dec–Mar share of lodging sales | Nov–Apr share of lodging sales |
|---|---|---|
| 2020-21 (COVID) | 61.3% | 71.5% |
| 2021-22 | 59.8% | 69.5% |
| 2022-23 | 62.3% | 72.6% |
| 2023-24 | 62.3% | 72.8% |
| 2024-25 | 60.8% | 72.1% |
| 2025-26 | 61.9% | 71.4% |
| **Mean 2021-22 … 2025-26 (n = 5)** | **61.4%** (range 59.8–62.3) | **71.7%** (range 69.5–72.8) |

The supplemental lodging table's column header reads "February … January", but its December values
match the industry-sector table (Dec-25, Dec-23, Dec-21), so the values are January–December and the
header is a PDF artifact.

Caveats: (1) **the main validity threat:** the report says lodging managed by a property-management
company is booked to the location of the company's office, so this is "lodging remitted to the Town of
Winter Park", not "lodging physically in town". The outside-county business location is about 17% of
all town sales tax (review). If 5+ BR managers or marketplace facilitators remit from outside, the
series under-represents exactly the tier we price; (2) Airbnb/VRBO marketplace remittance may be coded differently from
PM remittance (UNVERIFIED how the town attributes it); (3) five clean seasons only; (4) the town
series is tax collected in the following month but labelled by sales month.

### 1.4 First-party check (our homes)

The operator database (opened read-only) holds 54 confirmed reservations with check-ins from
June 2026 onward and forward bookings into 2027; there is no complete 12-month history for any
home. A first-party annual winter share **cannot be computed** today. The rate-card export
(`data/exports/rate_card.yaml`, gitignored) covers only November–April. Settling this needs the
Guesty reservation history for at least one full May–April year per home (per-home monthly
room-revenue *shares*, not dollars).

### 1.5 H5 verdict — **SUPPORTED for Winter Park lodging with winter = Nov–Apr; PARTLY otherwise**

- **71.7% of ski-season (Nov–Apr) town-remitted lodging** (n = 5 seasons, range 69.5–72.8%, t-based
  95% CI about 70–73%); **61.4%** for Dec–Mar. The practitioner's "about 70%" matches the Nov–Apr
  reading, which is the ski season. It is town-remitted lodging, not these three homes (caveat (1)).
- All taxable sales in the town: 68.5% Nov–Apr (n = 8 non-COVID seasons), 57.6% Dec–Mar.
- Fraser (51.8%) and Grand County (49.3%) are **not** 70% winter: the county is summer-heavy
  (consistent with the GCCTB/Datafy finding that peak visitor-days are June–August, dossier 01).
- Winter Park is *more* winter-concentrated than Breckenridge (63.4%) and about level with Vail
  (66.9%) on the same all-taxable basis.
- Trend: the all-taxable winter share fell from ~71% (2016-19) to ~64–66% (2024-26); lodging share
  has been flat at ~72% since 2021-22. Summer growth is in restaurants/retail more than lodging.
- For a 5–6 bedroom home the share is probably *higher* than the town average (summer demand skews
  to couples and small groups; dossier 01) — UNVERIFIED until a full first-party year exists.


## 2. H4 — gas prices and Front Range drive-up demand

### 2.1 Data assembled (all public, all downloaded 2026-10-16)

| Series | Source | Coverage | Notes |
|---|---|---|---|
| Colorado regular retail gasoline, monthly $/gal | EIA, series EMM_EPMR_PTE_SCO_DPG, https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMM_EPMR_PTE_SCO_DPG&f=M | Jun 2000 – Sep 2026 (316 months) | Deflated by CPI-U (FRED CPIAUCSL, https://fred.stlouisfed.org/series/CPIAUCSL) to Sep-2026 dollars; Oct-2025 CPI missing (federal shutdown) and interpolated |
| US-40 traffic, CDOT continuous count station **000223** ("SH 40 E/O Henderson Mine Rd", MP 248.7–254.3, the Empire side of Berthoud Pass) | CDOT OTIS Traffic Data Explorer, https://dtdapps.codot.gov/otis/TrafficData; JSON endpoint `/otis/API/TRANSYS/GetMonthlyTrafficVolumeForStation/000223.json` | monthly ADT Jan 1991 – Sep 2026; hourly by direction per day | 2025 AADT 8,300 (OTIS TrafficStations layer). Station ids found via the OTIS ArcGIS layer https://dtdapps.codot.gov/server/rest/services/OTIS/TrafficExplorer/MapServer/0 |
| I-70 traffic, CDOT continuous station **000106** (at Eisenhower Tunnel, MP 205.4–216.2) | same | Jan 1991 – Aug 2026 | 2025 AADT 35,000. Also cross-checked against the EJMT page https://www.codot.gov/travel/ejmt/trafficcounts (monthly 2000–Aug 2026) |
| Snowpack, Berthoud Summit SNOTEL 335:CO:SNTL | NRCS AWDB REST, https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data | daily 1991 – Oct 2026 | the station `src/signals/collectors/snotel.py` already uses; monthly mean SWE anomaly vs day-of-year median, and a snowfall proxy (sum of positive daily snow-depth gains) |
| Colorado unemployment rate | FRED COUR, https://fred.stlouisfed.org/series/COUR | 1976 – Aug 2026 | macro control |
| Winter Park / Fraser / Grand taxable sales | DOR (section 1) | 2016 – Jul 2026 | secondary outcome |

Important geography: Winter Park traffic leaves I-70 at Empire (exit 232) **east** of the
Eisenhower Tunnel, so the tunnel counts Summit/Eagle-bound traffic, not Winter Park's.
Station 000223 is the only continuous counter on the Winter Park access road; it also carries
Grand County residents, freight and through-traffic to Granby/Grand Lake/RMNP (summer).

### 2.2 Model

Monthly, excluding COVID months (Mar 2020 – Jun 2021). Main specification is a
**12-month log difference** (removes month-of-year seasonality and slow trends):

Δ₁₂ log ADT_t = β · Δ₁₂ log realGas_t + γ · Δ₁₂ SWEanom_t (+ δ · Δ₁₂ unemployment_t) + c + ε_t,

with Newey–West (HAC) standard errors at 12 lags. The lags are counted in **rows** of the filtered
series, not calendar months: with six winter rows a season, 12 lags span about two seasons. β is a
short-run elasticity of traffic to the real gas price. A levels version with month dummies and a
quadratic trend does **not** give uniformly similar signs: I-70 levels, all months, is −0.102
[−0.175, −0.028] (Dec–Mar levels −0.080), more negative than any row below (see §2.3).
Implemented in numpy (`/private/tmp/wp_research/scripts/h4_monthly.py`, `h4_robust.py`).

### 2.3 Results — monthly

| Outcome (station) | Months | n | β (gas elasticity) | 95% CI |
|---|---|---|---|---|
| US-40 Berthoud (000223) | Nov–Apr | 134 | **+0.058** | −0.070, +0.185 |
| US-40 Berthoud | Dec–Mar | 91 | +0.028 | −0.065, +0.122 |
| US-40 Berthoud | Nov–Apr, + unemployment | 134 | +0.040 | −0.054, +0.135 |
| US-40 Berthoud | Nov–Apr, + unemployment, ex-2008-09 | 116 | −0.041 | −0.128, +0.047 |
| US-40 Berthoud | Jun–Sep | 93 | **−0.098** | −0.197, +0.001 |
| US-40 Berthoud | Jun–Sep, + unemployment | 92 | **−0.127** | −0.235, −0.019 |
| US-40 Berthoud | Jun–Sep, + unemp, ex-2008-09 | 82 | −0.084 | −0.179, +0.011 |
| US-40 Berthoud | all months | 272 | −0.004 | −0.088, +0.081 |
| I-70 Eisenhower (000106) | Nov–Apr | 134 | +0.008 | −0.033, +0.049 |
| I-70 Eisenhower | Nov–Apr, + unemp, ex-2008-09 | 116 | −0.010 | −0.059, +0.038 |
| I-70 Eisenhower | Jun–Sep, + unemployment | 90 | **−0.087** | −0.119, −0.054 |
| I-70 Eisenhower | Jun–Sep, + unemp, ex-2008-09 | 78 | −0.070 | −0.109, −0.030 |
| Ratio Berthoud / Eisenhower | Nov–Apr | 132 | +0.055 | −0.035, +0.144 |

**Inference by season, not by row.** About 85% of the year-over-year gas variance is between
seasons (total variance 0.0465, mean within-season 0.0070), so the 134 winter rows carry about 23
seasons of information. Season-clustered, season-block-bootstrap (2,000 draws) and season-aggregated
estimates (reviewer's `rev_checks.py`, re-run 2026-10-19 with identical output):

| Spec | Season-clustered | Season block bootstrap | Season-aggregated OLS |
|---|---|---|---|
| Berthoud Nov–Apr | +0.054 [−0.095, +0.204] | [−0.096, +0.179] | +0.091 [−0.044, +0.227] (n = 23) |
| Berthoud Nov–Apr + unemployment | +0.040 [−0.056, +0.137] | [−0.099, +0.132] | +0.078 [−0.052, +0.208] |
| Berthoud Nov–Apr, gas lagged 1 / 2 months | +0.038 / +0.073 | [−0.100, +0.150] / [−0.047, +0.184] | +0.105 / +0.117 |
| Berthoud Nov–Apr + I-70 control | +0.062 [−0.054, +0.178] | [−0.080, +0.154] | +0.095 [−0.037, +0.227] |
| Berthoud Jun–Sep | −0.100 [−0.195, −0.006] | [−0.196, −0.014] | −0.110 [−0.262, +0.041] (n = 25) |
| Berthoud Jun–Sep + unemployment | −0.127 [−0.234, −0.020] | [−0.224, −0.019] | −0.132 [−0.273, +0.009] |
| Berthoud Jun–Sep + I-70 control | −0.045 [−0.110, +0.019] | [−0.110, +0.018] | −0.046 [−0.181, +0.090] |
| I-70 Jun–Sep + unemployment | −0.087 [−0.134, −0.039] | [−0.125, −0.030] | −0.098 [−0.169, −0.027] |

The winter null survives every inference method, booking-time gas lags and the I-70 control. The
summer Berthoud effect survives clustering but not season aggregation, and it halves and includes zero
once I-70 traffic is controlled for (I-70 may itself respond to gas, so that control is not decisive).
Other specifications the scripts print: Berthoud all months 2010+ −0.081 [−0.165, +0.002]; I-70 levels
all months −0.102 [−0.175, −0.028]; the snowfall-proxy coefficient is about zero (SWE anomaly, not
new snowfall, carries the snow effect, consistent with Shih et al. 2009 on snow depth).

**Endogeneity.** Retail gas tracks crude, and crude rises in booms (2005–08, 2021–22) when leisure
travel also rises. That biases β upward, so a near-zero winter β is compatible with a modestly negative
causal effect. The same standard applies to all three surprising signs: the positive tax-sales β below,
the positive daily trend-model β (§2.5), and the negative summer β. No supply-shock instrument (Kilian
2009 or Baumeister–Hamilton shocks, or the dated 2026 Hormuz shock) was run, so these are predictive
associations, not causal elasticities. The winter bound is the defensible output: a 30% gas rise moves
winter access traffic by at most about 4%.

Snow coefficient (Berthoud, Nov–Apr): +0.83% to +0.91% traffic per inch of SWE anomaly
(95% CI roughly ±0.55 points) — the right sign, and larger in relative terms than gas.
Real Winter Park taxable sales (Nov–Apr, n = 44, 2017–2026): **+2.0% per inch of SWE anomaly**
(95% CI +1.0 to +3.1%). The tax-sales regressions give a *positive* gas coefficient
(+0.15 to +0.20), which is confounded: the 2022 gas spike coincided with the post-COVID travel
boom and only nine winters exist. I do not report it as evidence either way, and by the same standard
the negative summer traffic β is not causal evidence either.

### 2.4 The 2026 case study

Colorado gas fell to $2.30 in Dec 2025, then rose to $3.54 (Mar), $4.44 (May) and $4.19 (Sep 2026).
The early-March rise was mainly seasonal (summer blend and demand, per the Gazette); the article
treats the US–Iran war and Strait of Hormuz risk as reaching the pump with a 2–6 week lag, so the
later rises carry the war effect (EIA series above; Colorado Springs Gazette, 2026-03-04, https://gazette.com/2026/03/04/gas-prices-spike-in-colorado-springs-but-reason-goes-beyond-war-in-middle-east ;
KKTV, 2026-09-07, record Labor Day prices, https://www.kktv.com/2026/09/07/gas-is-insane-colorado-shatters-previous-labor-day-weekend-record-gas-prices/ ).

| 2026 vs 2025 | Real gas YoY (nominal: Jan −18.2%, Feb −11.5%) | US-40 Berthoud ADT YoY | I-70 Eisenhower YoY | Berthoud SWE anomaly (2026 vs 2025, in) | WP lodging tax YoY (constant rate) |
|---|---|---|---|---|---|
| Jan | −20.1% | −8.3% | −3.0% | −3.2 vs +1.5 | −10.8% |
| Feb | −13.6% | −12.4% | −3.9% | −4.4 vs +1.7 | −2.9% |
| Mar | +18.5% | −14.1% | −5.1% | −5.8 vs +3.1 | −18.6% |
| Apr | +20.9% | −30.6% | −11.1% | −14.5 vs +1.0 | −53.4% |
| May | +40.9% | −6.9% | −2.7% | −15.4 vs −0.4 | −16.8% |
| Jun | +24.0% | +0.8% | −2.0% | — | +6.6% |
| Jul | +24.0% | −1.9% | −5.0% | — | −11.5% |
| Aug | +35.7% | −7.2% | −4.0% | — | −22.8% |
| Sep | +31.8% | −1.7% | +1.5% | — | n/a |

Reading: in **January–February 2026 gas was 14–20% cheaper than a year earlier, yet Winter Park
traffic fell 8–12% and lodging tax fell 3–11%**. In that season the snow effect dominated any gas
effect (2025-26 Berthoud peak SWE about 60% of the six-season mean, per `snotel.py`'s acceptance note).
One season with snow and gas moving in opposite directions in Jan–Feb and the same direction in
Mar–May cannot show that gas has no effect. The summer-2026 traffic
decline (−2% to −7% with +24–36% gas) is consistent with a summer elasticity of about −0.1 to −0.2.
Summer lodging fell more than traffic (−11.5% Jul, −22.8% Aug), so something beyond fuel cost —
macro (Denver-area CPI +3.9% y/y to July 2026, USAFacts,
https://usafacts.org/answers/what-is-the-current-inflation-rate/metro-area/denver-co/, via the review;
an earlier "5%, Colorado Sun" figure had no source and is withdrawn) or the low-snow carry-over in
spring bookings — is also at work. This cannot be separated with one year.

(Daily-traffic analysis: section 2.6.)

### 2.5 Results — daily (US-40 station 000223, both directions summed)

Daily totals were rebuilt from the OTIS hourly endpoint
(`/otis/API/TRANSYS/GetDailyTrafficVolumeForStationByDay/000223/true/YYYY-M-D.json`) for
1 Jan 2016 – 30 Sep 2026: 3,784 days with both directions. Weekly Colorado retail gasoline from EIA
(https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMM_EPMR_PTE_SCO_DPG&f=W), real.
Nov–Apr model: log daily traffic on log real gas (latest weekly print), Berthoud SWE anomaly vs
day-of-year median, new snow in the last 48 h (snow-depth gains), new-snow × weekend, day-of-week,
month, holiday windows (Christmas–New Year 20 Dec–2 Jan; MLK and Presidents' Fri–Mon; Thanksgiving
Wed–Sun), and either season fixed effects or a linear trend. HAC(14) errors. n = 1,611 winter
days (COVID excluded; 2 closure-like outlier days dropped).

| Term | Season FE | Trend instead of season FE |
|---|---|---|
| log real gas | **−0.151** [−0.308, +0.005] | **+0.198** [+0.122, +0.275] |
| SWE anomaly, per inch | +1.28% [+0.63, +1.93] | +2.22% [+1.66, +2.77] |
| new snow last 48 h, per inch of depth gain | −0.88% [−1.47, −0.28] | −0.86% |
| Friday / Saturday / Sunday vs Monday | +39% / +40% / +45% (log points) | same |
| Christmas–New Year window | +41 log points [+34, +48] | +42 |
| Thanksgiving Wed–Sun | +28 [+22, +33] | +29 |
| Presidents' Fri–Mon | +20 [+16, +24] | +20 |
| MLK Fri–Mon | +12 [−0, +24] | +12 |

Summer (Jun–Sep daily, n = 1,161): gas +0.068 [−0.022, +0.157] with a trend; −0.138 [−0.403, +0.127]
with year fixed effects.

**The gas coefficient flips sign with the specification.** With season fixed effects it is
identified only from within-season gas swings, which are small and correlated with the spring
wind-down; with a trend it picks up the 2021–2023 post-COVID boom, which coincided with high gas.
Neither is a clean causal estimate. What is robust across all specifications: (a) the winter gas
elasticity of Winter Park access traffic is small — every CI excludes effects larger than about
−0.3, and the monthly YoY estimates centre on zero; (b) snowpack and the calendar (weekends,
holidays) dominate. A 30% gas rise at an elasticity of −0.1 to −0.15 is a 3–4% traffic change; a
one-standard-deviation SWE anomaly (about 3–5 in mid-winter at Berthoud) is 4–10%; Christmas week is
+41 log points.

New snow in the last 48 hours *reduces* same-day traffic (storm days: chain/traction law, closures,
people waiting), consistent with CDOT's guidance that storms suppress and then concentrate traffic
(https://www.codot.gov/news/2025/february/prepare-heavy-travel-i70-mountain-corridor-and-other-mountain-passes-this-weekend).

### 2.6 Literature on fuel prices and leisure travel

- Hughes, Knittel & Sperling (2008), *Energy Journal* 29(1):113–134 (NBER w12530,
  https://www.nber.org/papers/w12530): US short-run gasoline-demand elasticity fell from −0.21…−0.34
  (1975–80) to −0.034…−0.077 (2001–06). Gasoline *consumption*, all trips. Peer-reviewed; STALE (>3 y)
  but foundational.
- Dallas Fed (2020), https://www.dallasfed.org/research/economics/2020/0616 : its −0.27 to −0.35 is
  Levin, Lewis & Wolak's daily-transaction estimate, not a new instrument. The page's central point
  applies to this dossier: **monthly aggregate series bias gasoline elasticities toward zero**.
  Government research.
- **Levin, Lewis & Wolak (2017)**, *AEJ: Economic Policy* 9(3):314–347 (NBER w22345,
  https://www.nber.org/papers/w22345): daily city-level elasticities are an order of magnitude larger
  than those from aggregated data, and monthly national aggregation gives about zero. This is a direct
  threat to the monthly design in §2.2–2.3. The daily model (§2.5) partly answers it: its CIs still
  exclude effects beyond about −0.3, but its sign flips with specification.
- FHWA (Brand, 2009), https://www.fhwa.dot.gov/policy/otps/innovation/issue1/impacts.cfm : 2008 VMT
  short-run elasticity −0.12 to −0.30; literature short-run VMT ≈ −0.15, long-run −0.25 to −0.30;
  single-earner rural households least responsive (−0.09, a fuel-consumption elasticity, not VMT). STALE.
- **Canina, Walsh & Enz (2003)**, *Cornell Hotel and Restaurant Administration Quarterly*, "The
  effects of gasoline-price changes on room demand" (STR monthly data, branded US hotels, 1988–2000;
  https://ecommons.cornell.edu/entities/publication/3e4221b1-2e38-448a-8de7-694d5e8df7b8 ; Cornell press
  summary https://www.news.cornell.edu/stories/2002/05/gas-price-rise-could-cause-big-losses-lodging-industry):
  a 1% gas rise cuts room demand about 1.74%, economy about 2.89%, **upscale least affected**, strongest
  at highway and suburban hotels. STALE; the coefficient is UNVERIFIED (press summary only) and looks
  implausibly large. It is the main published lodging result against this dossier's null; its
  upscale finding supports the luxury argument.
- **STR (2022)**, "Historical analysis: rising gas prices have limited impact on US hotel demand"
  (https://str.com/data-insights-blog/historical-analysis-rising-gas-prices-have-limited-impact-us-hotel-demand):
  real gas correlates +0.54 with room demand and +0.16 with RevPAR since 1990, the same seasonal and
  macro confounding found here. Vendor.
- **Edelstein & Kilian (2009)** (summary: https://econbrowser.com/archives/2007/05/new_study_of_th_1):
  energy-price shocks cut services spending about 1.5% and consumer sentiment more than proportionally.
  Gas reaches leisure through an **income and sentiment channel**, not only trip fuel cost, which
  weakens the "fuel is a small share of the trip" argument below.
- **Colorado 2008-09** (gas peak year): Colorado Ski Country visits −6.9% but **Front Range visits
  +2.5%** (SAM, https://www.saminfo.com/news/sam-headline-news/5469-110-colorado-visits-dropped-5-5-percent-in-2008-09),
  consistent with substitution toward closer trips.
- Litman, VTPI *Transportation Elasticities* (2005–2026), https://www.vtpi.org/elasticities.pdf — compendium.
- Stevens, More & Markowski-Lindsay (2014), *Journal of Leisure Research* 46(2):153–164
  (https://fs.usda.gov/nrs/pubs/jrnl/2014/nrs_2014_stevens_001.pdf): 30 national parks, 1993–2010,
  annual per-capita visits; fuel price relative to income had a larger (negative) effect than entrance
  fees. Annual trending series, so the authors themselves flag spurious-correlation risk. STALE.
- Steiner, Stinespring & Dieringer (2026), *Journal of Park and Recreation Administration*
  (https://js.sagamorepub.com/index.php/jpra/article/view/13064): 30 parks × 30 years, FE-GLS;
  visitation "modestly responsive" to fuel prices, insensitive to fees. Paywalled; coefficient not seen.
- Oh & Hammitt (2011), *Tourism Economics* 17(6):1311–1324 (https://journals.sagepub.com/doi/10.5367/te.2011.0093):
  survey of state-park visitors; gas-price effects on trip decisions are moderated by behaviour. STALE.
- No peer-reviewed study of **ski** demand and gasoline prices was found (searched three ways). The
  closest are snow-demand studies: Parthum & Christensen (2022), *JEEM* 113:102637
  (https://pmc.ncbi.nlm.nih.gov/articles/PMC10936566): 12.5 M daily AirDNA booking observations near
  236 US ski resorts, 2014–2017; STR revenue elasticity to snowpack 0.223 nationally, **0.135 for
  Colorado**, 0.21 for the Mountain West; Englin & Moeltner (2004), *Environmental and Resource
  Economics* 29(1):123–136 (https://ideas.repec.org/a/kap/enreec/v29y2004i1p123-136.html), ≈0.21 for
  Tahoe; Falk (2010), *Tourism Management* 31(6):912–924
  (https://ideas.repec.org/a/eee/touman/v31y2010i6p912-924.html), Austrian elasticities ≈0.05–0.07.
- Practitioner/industry: Inntopia DestiMetrics (Nov 2025) cited gasoline +4.1% YoY as "pressure"
  but gave no elasticity (https://corp.inntopia.com/summer-finishes-modestly-winter-bookings-are-flat-as-daily-rates-edge-up/);
  its Aug-2026 briefing reports gas +27% and airfares +23% YoY (Post Independent, 2026-09-24,
  https://www.postindependent.com/news/colorado-ski-destinations-see-slow-start-to-winter-bookings/).

Our Berthoud winter estimate (≈0, CI roughly −0.13…+0.19 monthly) is in line with the post-2000
low short-run elasticities and with the idea that a ski trip's fuel cost is a small share of trip
cost: a 132-mile Denver–Winter Park round trip at 25 mpg uses ~5.3 gal, i.e. **$12–22 at $2.30–4.19**,
against a lift ticket of $150–250 and, for our homes, an all-in lodging bill of several thousand
dollars. For a Denver group of 8–14 splitting a 5–6 bedroom home, fuel is about 1–2% of trip cost.
Two caveats: drive-in groups from Texas, Kansas or Oklahoma can spend 7–21% of the stay on fuel (R5
§3.5), and the income and sentiment channel (Edelstein & Kilian) acts even when fuel is a small share.

### 2.7 H4 verdict — **No effect detected in winter, bounded small; summer is suggestive only**

- Winter (the season that is ~72% of town lodging): no detectable gas effect on Winter Park access
  traffic. Monthly YoY Nov–Apr β = +0.06 [−0.07, +0.19]. About 85% of year-over-year gas variance is
  between seasons, so the effective sample is about 23 seasons, not 134 monthly rows. A 30% gas rise
  is bounded at roughly 4% of access traffic. With unemployment and ex-2008-09, β = −0.04 [−0.13, +0.05];
  I-70 tunnel β ≈ −0.01 [−0.06, +0.04]. Daily estimates straddle zero depending on specification.
- The 2025-26 episode is a case study, not a natural experiment. In Jan–Feb 2026 gas was
  14–20% **cheaper** than a year earlier and traffic still fell 8–12%; in that season the snow effect
  dominated any gas effect (Colorado skier visits −24% to 10.5 M, Colorado Ski Country USA via Colorado Springs Gazette,
  2026-06-04, https://gazette.com/2026/06/04/visits-to-colorados-ski-resorts-fell-20-below-average-this-year-new-data-shows/). The −24% figure is preliminary and press-reported.
- Summer is suggestive only, about −0.1, and not robust. The I-70-controlled estimate reported in
  Appendix C is −0.045 [−0.110, +0.019] and includes zero. Summer 2026 (+24–36% gas) traffic −2% to −7%
  is consistent with a small effect; summer lodging fell more (−11.5% Jul, −22.8% Aug), so other forces
  (inflation, war uncertainty, consumer sentiment — DestiMetrics May 2026,
  https://www.snowsportsnews.com/newsrepository/2026/may/inntopia-destimetrics-winter-s-woes-melt-into-summer-surge-at-western-mountain-destinations/)
  are doing most of the work. The earlier "2 of 4 specs exclude zero" sentence is withdrawn until those
  four specifications are listed side by side.
- **Withdrawn, review fix 8, not re-sourced in this audit:** the Grand County "$4.54 on 2 Sep 2026"
  price, the Easter 2026 "travel held up" sentence, and the claim that the luxury tier held up in
  every 2025–26 DestiMetrics tier table. The review found the gas quote, the Easter source, and the
  tier-table coverage unreliable. Do not use them.
- For a drive-to resort 66 miles from Denver, a gas shock can *substitute in* Front Range visitors who
  would otherwise fly or drive farther — an offsetting effect that would push the net elasticity to zero
  (Colorado 2008-09: Front Range visits +2.5% while total visits fell 6.9%, §2.6).
- For luxury 5–6 BR homes the fuel share of a Denver group's trip is small (about 1–2%, §2.6). Drive-in groups from
  Texas, Kansas, or Oklahoma can be a much larger fuel share, so the portfolio prior stays small
  and the segment prior does not.
- **To settle it:** (1) a gas×segment test once the comp scraper yields a usable daily price/
  availability panel (compare economy units vs 5+ BR); (2) pull the I-70 Coalition/RRC panel's
  trip-frequency question by fuel price; (3) add Denver-metro consumer sentiment as a competing
  regressor. Data pulls are listed in Appendix B.

## 3. H1 — "Winter Park is a middle-class market"

### 3.1 Price distributions, same vendor and window (AirROI, trailing 12 months Aug 2025 – Jul 2026, pages updated 2026-09-12)

Vendor data (AirROI scrapes Airbnb; methodology not audited; all listing sizes pooled, so markets
with more small condos look cheaper). AirROI's peak and low ADR are not defined the same way on every
market page: Breckenridge's page gives best and worst single month, not seasonal averages, so its
peak/low cells are marked not comparable (n/c). Treat the peak/low columns as indicative only. Sources: https://www.airroi.com/airbnb-data/united-states/colorado/winter-park ,
…/fraser , …/keystone , …/breckenridge , …/steamboat-springs , …/vail , …/aspen .

| Market | ADR | ×WP | Median ADR | Top-10% ADR threshold | Peak-season ADR | Low-season ADR | Peak/low | Occupancy | Listings |
|---|---|---|---|---|---|---|---|---|---|
| Fraser | $398 | 0.91 | $326 | $676 | $445 | $354 | 1.26 | 31.4% | 593 |
| Keystone | $402 | 0.92 | $320 | $695 | $539 | $338 | 1.59 | 32.6% | 1,451 |
| **Winter Park** | **$437** | 1.00 | **$338** | **$802** | **$532** | $373 | 1.43 | 31.5% | 1,185 |
| Steamboat Springs | $579 | 1.32 | $447 | $1,024 | $793 | $456 | 1.74 | 30.3% | 2,255 |
| Breckenridge | $581 | 1.33 | $426 | $1,067 | n/c | n/c | n/c | 36.7% | 3,171 |
| Vail | $819 | 1.87 | $593 | $1,588 | $1,083 | $665 | 1.63 | 29.4% | 1,594 |
| Aspen | $1,071 | 2.45 | $887 | $2,056 | $1,282 | $959 | 1.34 | 33.7% | 633 |

AirDNA's public Colorado page (late Sep 2026, via search snippet; the page returns 403 to fetch)
lists Winter Park at $379, Breckenridge $575, Steamboat $598 — same ordering
(https://www.airdna.co/vacation-rental-data/app/us/colorado). Key Data reports Summit County ADR
$521 for 2025-26 (https://www.keydatadashboard.com/blog/summit-county-colorados-2025-26-ski-season-outlook).

Reading: Winter Park/Fraser sit in the **Keystone tier**, about 25–35% below Breckenridge/Steamboat,
about half of Vail and 40% of Aspen. The *tail* is what differs most: Winter Park's top-decile
threshold ($802) is half of Vail's and 39% of Aspen's. Consumer guides describe Winter Park as the
family/value alternative and "Denver's ski area" (e.g. Snowthere, https://www.snowthere.com/guides/winter-park-vs-breckenridge-families),
and the City and County of Denver owns the resort land (Pique, https://www.piquenewsmagazine.com/whistler-news/intrawest-finalizes-winter-park-deal-with-denver-2463416, STALE).

### 3.2 Large-home tier in our own repo data (public listed prices only)

The comp scraper's luxury comp set (22 large homes; `comp_snapshots` joined to `comps`, rows with
`scrape_status = 'ok'`, opened read-only, re-queried 2026-10-19) shows median asking prices of
**$2,073 (p50) and $3,098 (p90) for January stays** (n = 308), $2,073/$2,301 for February (n = 72),
$1,267/$2,334 for December (n = 446) and $1,104/$1,504 for September (n = 100). An earlier draft gave
$1,684/$2,344 (Jan) through $340/$716 (Sep); those were medians of `market_snapshots`, the broad market
sweep (11 listings in January, 231 in September), so they compared different populations and are
withdrawn. By bedroom, the median Dec–Mar asking price is $1,730 for 5 BR comps (n = 508 quotes) and
$2,598 for 7 BR (n = 166). `sleeps` is recorded for few comps (one 5 BR at 18, two 7 BR at 16), so the
per-slot figures are illustrative: **about $96 and $162 per sleeping slot** (the earlier $115/$166
assumed about 15 sleeps). The December 2023 market
evaluation in `data/dec2023/MARKET_EVALUATION.md` showed the same tier at $875–1,750 (curated, older).

So: the 5+ BR tier in Winter Park prices at **about 3.9× the town's peak-season ADR in January
($2,073 vs $532) and about 2.6× its top-decile threshold** — Aspen-like nightly prices in a Keystone-like
market.

### 3.3 Guest income and origin (what is published)

- Grand County visitors (Datafy 2023, cited in the county's Sept-2024 market analysis,
  https://grandcounty365.com/wp-content/uploads/sites/11/dlm_uploads/2024/11/Market-Analysis.pdf):
  **60% of visitors report household income over $100,000**; 53% are households of 3–5. **UNVERIFIED**
  (figures taken from a search-index extract; the PDF's text layer would not decode).
- GCCTB 2024 annual report (dossier 01): top origins Denver, Littleton, Aurora; peak visitor-days
  Jun–Aug; in-state share +0.12 pp.
- Comparators, not like-for-like: Aspen Chamber 2025 visitor profile household income $143,506
  (online, n = 929, March 2025; https://aspenchamber.org/about/demographics/); Vail RRC winter survey
  (COVID-era) 37% of guests ≥ $200k (Vail Daily, https://www.vaildaily.com/news/vail-shows-strength-in-a-survey-of-its-winter-guests/ ,
  STALE); NSAA (secondary summaries) ≈45% of US skiers ≥ $100k (EBSCO research starter,
  https://www.ebsco.com/research-starters/sports-and-leisure/skiing/). Different instruments, years and
  thresholds — no valid income ranking can be built from them.
- Pass mix: Winter Park is on Ikon (unlimited on the full pass; blackout dates on Base,
  https://www.ikonpass.com/en/shop-passes/ikon-base-pass). Ikon 2026-27 launched at $1,399 vs Epic at
  $1,089 (Steamboat Pilot, https://www.steamboatpilot.com/news/ikon-pass-2026-27-on-sale-higher-price/),
  so "Ikon = cheaper skier" is not true at the pass level. No public Ikon-vs-Epic income data was found.

### 3.4 What a middle-class core means for 5–6 BR luxury homes

1. **The buyer is a group, not a rich couple.** First-party: median party 6, mean 7.1, inquiry mean
   LOS 7.95 nights (dossier 01). All-in per night = nightly rate + (cleaning $600 + $75 × guests +
   insurance $80) ÷ nights. At $2,000/night × 3 nights: **$2,427/night at 8 guests ($303 per
   guest-night) and $2,577/night at 14 guests ($184 per guest-night)**. These exclude lodging and sales
   tax (9% town lodging total plus county and state) and any platform guest fee, which guests also see
   in the total; with roughly 9–13% of tax on top (approximate), the per-guest figures rise to roughly $200–340. That is in line with a mid-range hotel room *per person* in a peak week, which is
   why a middle-class market can still clear Aspen-like nightly prices for big homes.
2. **Price per guest-night should be a first-class feature** in `src/elasticity` and the simulator
   (`proving_ground_exam/market/`): elasticity is likely a function of price-per-guest and party size,
   not nightly price. Generic pricers anchor on market ADR and bedroom count, not group economics.
3. **The ceiling is set by substitution to other large homes, not by the town's ADR.** With
   Winter Park's top-decile at $802, market-wide signals carry almost no information about the
   5+ BR tier. Comps must be capacity-matched (≥14 sleeps), and the Summit County large-home tier
   (Breckenridge/Keystone) is the relevant outside option (`src/signals/features/substitution.py`).
4. **Risk asymmetry**: a group whose budget is split 3–4 ways is sensitive to the *per-head* number
   and to the fee stack shown all-in (FTC rule, OVERHAUL plan 2.4); a single wealthy payer is not.
   Test: elasticity by party size bucket once ≥ 1 season of quotes exists.

### 3.5 H1 verdict — **PARTLY SUPPORTED**

- Supported on **price**: Winter Park/Fraser are the cheapest of the seven compared markets with
  Keystone (ADR 0.54× Vail, 0.41× Aspen; top-decile 0.50× Vail).
- Not supported as a contrast with **Breckenridge**: Breckenridge is only 1.26–1.33× Winter Park on
  median/mean ADR — both are mid-market.
- **Untestable now on income/origin**: no like-for-like visitor income survey exists across these
  markets; the one Grand County figure (60% > $100k) is UNVERIFIED and county-wide.
- To settle: buy or request one Datafy/Zartico (Grand County DMO already licenses Datafy) cut by
  lodging type, or RRC's Winter Park mobility study; ask the Chamber for any guest-intercept data.

## 4. Segments: size, lead time, price sensitivity

Relative sizes are **UNKNOWN** for every segment except rail: no origin-by-lodging-type share exists
in public data (GCCTB/Datafy cuts were not available). Lead times are assumptions except where cited.
The first-party "median 15 days" is a mostly Jun–Dec, right-censored sample, not a winter figure;
AirROI's panel puts Winter Park's 2025-26 winter lead time at about 72 days (R4 review).

| Segment | Evidence of size | Lead time | Price sensitivity | Confidence |
|---|---|---|---|---|
| Front Range day-trippers (not our buyer, but they set traffic) | Denver/Littleton/Aurora are the top origins (GCCTB 2024). I-70 Coalition/RRC 2024 user survey (3,611 Front Range respondents): 92% try to avoid peak congestion, **75% say congestion has reduced how often they ski**, average 10.4 I-70 snowsport days/yr, 61% on weekends (https://i70solutions.org/wp-content/uploads/2024/05/I-70-Mountain-Corridor-User-Survey-2024-Final-Report.pdf); 2019: 45% avoid weekend skiing altogether, 51% stay overnight near the resort to avoid traffic (Summit Daily, https://www.summitdaily.com/news/new-i-70-study-shows-congestion-is-leading-some-skiers-to-make-fewer-trips-to-the-mountains/) | same day – days | gas: low (§2); snow: high (+1.3–2.2% traffic per inch SWE anomaly) | medium |
| Front Range overnight (weekend groups, families) | Congestion converts day trips to overnights (51%, 2019). Traffic Fri–Sun +39–45 log points over Monday | 8–21 days (assumption; the first-party 15-day median is not a winter figure) | moderate; driven by snow and school calendars | medium |
| Drive-in TX/KS/OK/NE | VisitGrandCounty web sessions: Kansas City +66.9% YoY (dossier 01). Texas spring break clusters 8–19 March 2027 (Dallas/Austin 15–19 Mar; Houston 8–12 Mar; https://publicschoolscalendar.com/austin-isd-calendar-2026-2027/) — UNVERIFIED against district sites | 30–90 days | moderate; fuel is a larger share for a 1,000-mile drive, but still small vs lodging | low |
| Fly-in via DEN | DEN 82.4 M passengers in 2025 (record, +0.1%), international 4.87 M (+4.8%) (https://www.flydenver.com/press-release/denver-international-airport-celebrates-2025-milestones/). Airfares +23% YoY in Aug 2026 (Inntopia via Post Independent) | 45–90 days (DestiMetrics lead time 56–60 days, all western) | airfare-sensitive; benefits drive-to WP relative to fly-only resorts — UNVERIFIED | low |
| International | Western mountain Canadian bookings −43.9% (DestiMetrics December 2025 release, via SAM, https://www.saminfo.com/news/sam-headline-news/season-opened-slowly-at-most-western-destinations) and −42.6% vs 2024 for summer 2026 (DestiMetrics May 2026, §2.7); NPR 2025-12-01 on politics-driven declines (https://www.npr.org/2025/12/01/nx-s1-5545712/us-ski-resorts-steep-drop-international-travel-politics). Winter Park's share is small (dossier 01: 4–8% assumed) | 61+ days | FX, politics | low |
| Groups (multi-family, ski clubs, corporate, weddings) | First-party: median party 6, mean 7.1; inquiries mean 7.95 nights. No public share table exists (dossier 01) | 22–60+ days | per-head price; fee stack | low |
| Rail (Winter Park Express) | **39,451 riders in 2025-26**, 57 round trips, 88% load factor (CDOT CTIO recap, Apr 2026, https://www.codot.gov/programs/ctio/assets/agenda-item-documents/2026-agenda-item-documents/april-2026/5b-winter-park-express-presentation-draft-2025-26-season-recap.pdf); 2,751 continued to Fraser (ColoRail, https://www.colorail.org/colorado-rail-passenger-news/qi8id2u2mwatwzgasbeodgvx0l57x3) | sells out in advance | — | high (counts) |

Scale check: ≈20k round-trip rail visitors vs roughly 1.1 M vehicle crossings at station 000223 in a
Dec–Mar season (≈9,000–10,000 ADT × 120 days, both directions): rail is ~2–4% of person-trips
(assuming 2–2.5 people per car) — a sell-out indicator, not a demand driver.

## 5. Access shocks

- **Storm days:** each inch of new snow-depth gain in the prior 48 h lowers same-day US-40 traffic by
  ≈0.9% (95% CI 0.3–1.5%), with no significant extra weekend effect (§2.5). This is the traction-law /
  closure / "wait it out" effect, net of the powder pull.
- **Berthoud closures:** CDOT runs planned overnight closures (e.g. 11 pm–5:30 am,
  https://www.codot.gov/news/2024/february/cdot-plans-to-close-berthoud-pass-overnight-saturday);
  unplanned avalanche closures have lasted up to ~30 h (CBS Colorado,
  https://cbsnews.com/colorado/news/teams-look-for-missing-snowboarder-on-berthoud-pass) and have
  stranded weekenders an extra night (Westword,
  https://www.westword.com/news/winter-park-weekenders-experience-delays-getting-back-to-denver-18886048/).
  CDOT scheduled daytime rock-mitigation holds on US-40 MP 236–240 in Sept–Oct 2026
  (https://www.codot.gov/news/2026/september-2026-news/us40-berthoudpass-traffic-holds-scheduled-sept21).
  Only 2 of 1,613 winter days had a daily total below 35% of the season/weekday/month median, so
  full-day closures are rare; most closures are partial-day.
- **I-70:** weekend metering at the tunnel and Floyd Hill–Georgetown bottlenecks (CDOT reversible-lane
  study, https://www.codot.gov/projects/studies/study-archives/I70reversiblelanephaseIIstudy/i-70-reversible-lanes-alternatives-evaluation-draft/@@download/file/I-70%20Reversible%20Lanes%20Alternatives%20Evaluation%20DRAFT.pdf).
  Winter Park traffic exits at Empire before the tunnel, so it avoids the worst of it.
- **Occupancy effect:** no public study quantifies lodging occupancy loss from closures. For our homes
  (3–5-night group stays booked 2–8 weeks out), a closure mostly shifts arrival time; the
  realistic losses are same-week cancellations and lost last-minute fills. Test design: log
  `cdot.berthoud_closed` hourly (collector exists) and join to Guesty cancellations and to comp
  availability changes; with ~10–20 closure events a season this needs 2–3 seasons for power.

## 6. Summer and shoulder

- Size: lodging May–Oct ≈ 28% of the town's lodging year (§1.3); all taxable ≈ 31.5%.
- Growth: town May–Oct taxable sales rose ≈2.3× from 2017 to 2025 (nominal) vs ≈2.0× for winter —
  summer is the faster-growing half, mostly restaurants/retail; lodging's winter share has not moved.
- Drivers (evidence quality is weak): Trestle Bike Park, 40+ miles of lift-served trails, season
  June–September (Pinkbike 2017, https://m.pinkbike.com/news/winter-park-mountain-biking-part-2-trestle-and-granby-lift-served-2017.html , STALE);
  resort events (Winter Park Classics: Point-to-Point 28 Jun, Race Rendezvous 19 Jul;
  https://www.winterparkresort.com/things-to-do/events/race-rendezvous); weddings (resort
  Groups & Weddings; no counts found). No public Trestle visitation numbers exist.
- 2026: DestiMetrics had summer occupancy on the books +4.9% (as of 30 Apr), yet Winter Park lodging
  tax fell 11.5% in July and 22.8% in August, and August arrivals booked in August were −26.7% across
  the West (Post Independent, 2026-09-24). Summer is the season where gas (+24–36%) and macro bite.
- How to raise the non-winter share for 5–6 BR homes: target group events (weddings, reunions,
  bike-team and corporate retreats) with midweek minimum-stay flexibility; price by guest count;
  sell 2-night weekends at a per-head discount when pace is behind; this is a `src/pricing` /
  minimum-stay policy change, measured on summer owner net vs `current_practice`.

## 7. H7 — Winter Park–specific factors a generic pricer would miss (ranked by estimated revenue impact)

Impact estimates are for the three homes' season owner net and are order-of-magnitude priors,
aligned with S1's roadmap priors. They are judgment, not estimates, and every one is below the ~33%
field MDE, so each needs a simulator gate on a misspecified world. "Exposure" is how much revenue the
factor moved, not how much pricing can recover.

| Rank | Factor | Evidence (this dossier) | Generic pricer today | Est. impact | Module |
|---|---|---|---|---|---|
| 1 | **Capacity-matched comp anchor and price-per-guest lens** for 14–18-sleep homes | WP top-decile ADR $802 vs 5+ BR comps $1.7–2.6k; groups split cost | Market ADR × bedroom multiplier; neighbourhood comps pooled | +1–4% (prior; S1 item 1). Mis-anchoring by 2–3× is the error OVERHAUL found in the simulator | `src/comps`, `src/scrape` (binding), `src/elasticity` |
| 2 | **Snowpack-conditioned pace** (read "behind pace" differently in a low-snow year; hold rate until snow decides) | +1.3–2.2% traffic and +2% taxable sales per inch SWE anomaly; 2025-26 town lodging tax Jan −10.8%, Feb −2.9%, Mar −18.6% YoY; Parthum & Christensen CO elasticity 0.135 | Pace vs own history, no snow input (PriceLabs uses occupancy/pickup) | 0–1.5% recoverable (prior). Exposure: town lodging tax fell 3–19% YoY in Jan–Mar 2026; that is how much demand moved, not what pricing can recover | `src/pricing/pace.py`, `src/signals` (SQI, snotel) |
| 3 | **Snow hangover** for next-season bookings (**hypothesis**) | Colorado Nov–Jan bookings −10.9%, Nov–Feb occupancy −4.4%, ADR −2% as of 31 Aug 2026 after the worst snow season. The source (Post Independent, 2026-09-24) gives two causes: lingering effects of last winter's poor snow, a "snow hangover" per Inntopia's Tom Foley, and economic pressure, airfares and gas. It also reports an Inntopia study of western states: in winters after the five poorest snow seasons of the past 24 years, occupancy rose 2.5%, rates 2.3% and revenue 4.9% on average by August. So the hangover is a **delay in advance bookings**, not a weaker season | Sees only lower pickup; may discount early | 0–0.5% (avoids reading a booking delay as weak demand; untested for these homes; test: prior-season SWE anomaly vs early-season on-the-books pace and final occupancy across 10+ seasons of comp availability or DestiMetrics) | `src/pricing/pace.py` reference curves by prior-season snow |
| 4 | **Holiday / school windows specific to Front Range and Texas** | Christmas +41, Thanksgiving +28, Presidents +20, MLK +12 log points in access traffic; Texas spring break 8–19 Mar | Generic US holiday calendar | 0.2–1% (prior): the highest-priced nights of the year | `src/signals/collectors/calendars.py` |
| 5 | **Macro / consumer sentiment and airfare** | DestiMetrics ties 2025-26/2026-27 softness to sentiment (<100 for 24 months) and airfares +23% | Not modelled | 0–0.5% (prior), mostly via lead time | `src/signals` (new), shadow only |
| 6 | **Storm-day access (Berthoud/I-70)** | −0.9% traffic per inch new snow; rare full-day closures | Not modelled | <0.2% for 3–5-night groups; matters for last-minute fills | `cdot` collector, `src/signals/features/access.py` |
| 7 | **Weekend/midweek pattern** | Fri–Sun +39–45 log points | Day-of-week factors exist | ~0 incremental | — |
| 8 | **Gas prices** | winter β ≈ 0 (CI excludes < −0.13 monthly); summer ≈ −0.1 | Not modelled | ~0 (winter), <0.5% (summer, not robust) | shadow only |
| 9 | **International / geopolitics (Canada, FX, war)** | Canada −42…−44% bookings; WP is drive-dominated | Not modelled | ~0 for WP | shadow only |

### H7 verdict — **PARTLY SUPPORTED**

Specialization plausibly beats a generic pricer on factors 1, 2 and 4, and possibly 3 (an untested
hypothesis), where the evidence is strongest and a
generic tool either uses the wrong anchor or reacts late. It does **not** yield an edge on gas,
day-of-week, or international/geopolitical feeds — those effects are small or already priced by
pickup. The edge is mostly **anchoring and interpretation** (what the right comp set is, what a
behind-pace reading means in a given snow year), not more data streams. It is UNTESTED in live
owner-net terms: the current field test can only detect ≥33% effects.

## 8. What generic STR pricers miss (H2 note)

From this market's data: (1) they anchor on market ADR, which for Winter Park ($437; top decile
$802) says almost nothing about 14–18-sleep homes asking $1.7–2.6k; (2) they read pace without a
snow state, so in a 2025-26-type season they read a snow-driven demand drop as ordinary weak pace
(whether holding or cutting price is better then is a simulator question, not a settled fact), and they
may discount early the following autumn before snow decides the season (a hypothesis); (3) their
holiday calendars are national, not Front Range + Texas school calendars; (4) they price per night,
not per guest-night of a cost-splitting group. They do *not* miss much by ignoring gas prices.

## 9. Recommendations (ranked)

| # | Recommendation | Expected impact (owner net) | Confidence | Effort | Data needed | Measurement plan |
|---|---|---|---|---|---|---|
| 1 | Fix the comp anchor first: capacity-matched (≥14 sleeps) comps across WP/Fraser **and** Summit County large homes; the scraper is the binding constraint | High (avoids 2–3× mis-anchoring; enables everything else) | High | Medium (`src/scrape`, `src/comps`) | ≥3 valid comps on ≥50% of nights | share of nights with a valid anchor; paired sim owner net vs `current_practice` (25 seeds) |
| 2 | Add a snowpack state to pace interpretation: reference booking curves conditioned on Berthoud SWE anomaly tercile. Candidate rule, **a simulator hypothesis**: do not cut price on "behind pace" before mid-December in a below-normal snow year unless the gap exceeds the snow-explained gap. Standard RM logic says the optimal price usually falls when demand shifts down, so the rule must win a paired owner-net test (snow-conditioned vs plain pace on 2025-26-like low-snow seeds) before it reaches `pace.py` | 0–1.5% (prior); exposure in extreme years is ±10–20% of winter revenue, most of it not recoverable | Medium-low (traffic and tax effects robust; booking-curve and price effects untested) | Medium (`src/pricing/pace.py`, `src/signals`) | 10+ seasons of comp availability (or DestiMetrics), SNOTEL (have) | shadow: compare pace-gap forecast error with/without snow state; IC on the promotion ladder |
| 3 | Early-winter 2026-27 softness as a **lead-time shift** in the reference curve, not a level cut: DestiMetrics shows −4% to −11% on-the-books vs normal (Colorado-wide). Inntopia attributes it partly to a post-drought "snow hangover" and partly to economic pressure and travel costs, and its own study found that winters after the five worst snow years finished up (occupancy +2.5%, revenue +4.9% on average). So early pace below normal should not by itself trigger discounts. Untested for these homes | 0–0.5% (prior) | Low | Low | DestiMetrics monthly notes (public); 10+ seasons of comp availability to test the hangover | early-winter owner net vs `current_practice`; prior-season SWE vs early-season pace across seasons |
| 4 | Price per guest-night as an elasticity covariate; model party-size buckets in the simulator | Medium-high | Medium (mechanism strong; no first-party elasticity yet) | Medium (`src/elasticity`, `proving_ground_exam/market/`) | quote/inquiry log with party size | elasticity by bucket; sim sensitivity sweep |
| 5 | Front Range + Texas school calendars and the four holiday windows quantified here as calendar features | Medium | High (traffic effects tight) | Low (`calendars.py`) | district calendars yearly | holiday-night ADR and fill vs `current_practice` |
| 6 | Keep gas as a **shadow** signal only; summer coefficient −0.1 at most | Low | High that it is small | Low | EIA weekly (free) | IC on ladder; drop if IC < threshold after 1 season |
| 7 | Log Berthoud closures hourly and join to cancellations | Low-medium | Low | Low (collector exists) | 2–3 seasons | cancellation rate on closure days vs matched days |
| 8 | Summer: per-head pricing and minimum-stay flexibility for groups; don't expect summer to reach more than ~30% of lodging revenue | Low-medium | Low | Medium | summer quotes | summer owner net vs `current_practice` |

## 10. Open questions for the operator

1. Can we get one full May–April Guesty history per home (even from the prior manager) so the
   first-party winter share can be computed as a percentage?
2. Which PM office remits each home's lodging tax (Winter Park vs Fraser vs elsewhere)? It decides
   which town series to watch.
3. Do the practitioner's "gas" comments come from summer 2026 bookings? That is the only season in
   which our data support a gas effect.
4. Party composition on winter stays: one family or several? This decides whether per-guest pricing
   is the right lens.
5. Is a DestiMetrics (Inntopia) subscription or a Grand County Datafy cut affordable? Either would
   settle H1 origin/income and give a weekly pace benchmark.

## Verdicts at a glance (detail)

| Hypothesis | Verdict | Headline numbers |
|---|---|---|
| H1 middle-class market | **PARTLY SUPPORTED** | WP ADR $437 vs Breck $581, Steamboat $579, Vail $819, Aspen $1,071 (AirROI TTM); WP top-decile $802 vs Vail $1,588, Aspen $2,056; income data not comparable |
| H4 gas suppresses drive-up demand | **No effect detected in winter, bounded small; summer suggestive only** | Berthoud Nov–Apr YoY elasticity +0.06 [−0.07, +0.19]; effective n about 23 seasons, not 134 rows; a 30% gas rise is bounded at about 4% of access traffic. Summer I-70-controlled estimate in Appendix C includes zero |
| H5 ~70% of revenue in winter | **SUPPORTED (WP lodging, Nov–Apr); PARTLY otherwise** | WP lodging 71.7% Nov–Apr (n = 5, 69.5–72.8%), 61.4% Dec–Mar; all WP taxable 68.5%; Fraser 51.8%; Grand County 49.3% |
| H7 hyper-specialized engine wins | **PARTLY SUPPORTED** | Edge in comp anchoring, snow-conditioned pace and local calendars; snow hangover is an untested hypothesis; none in gas/DOW/international |

## Appendix A — search log

42 distinct web searches (14 in "extended" mode) plus about 45 page fetches and direct data pulls. Queries in order:

1. CDOT OTIS continuous count station US 40 Berthoud Pass monthly traffic volume
2. CDOT continuous count station Eisenhower Tunnel I-70 monthly traffic counts data download (ext.)
3. Colorado DOR retail sales by county by industry NAICS 721 Grand County
4. data.colorado.gov retail sales by county industry monthly dataset
5. Colorado gas prices 2026 spike why
6. gasoline price elasticity leisure travel tourism visitation national parks (ext.)
7. Journal of Leisure Research 2014 46(2) national park visitation fuel
8. ski resort skier visits gasoline prices effect elasticity drive market (ext.)
9. Englin Moeltner 2004 value of snowfall
10. AirDNA Breckenridge Vail Aspen Steamboat Winter Park ADR comparison
11. Grand County Tourism Board annual report 2025 Datafy origin income (ext.)
12. Town of Winter Park sales tax report lodging monthly (ext.)
13. Winter Park Resort skier visits Front Range share Ikon (ext.)
14. Winter Park skier visits record Alterra (ext.)
15. Winter Park owned by Denver lease Alterra
16. NSAA demographic income > $100k (ext.)
17. Colorado in-state share of skier visits RRC (ext.)
18. Winter Park Express ridership 2025-26
19. Berthoud Pass closure impact businesses (ext.)
20. Trestle Bike Park visits growth
21. Inntopia DestiMetrics 2025-26 final (ext.)
22. DestiMetrics Aug/Sep 2026 winter 2026-27 (ext.)
23. "Strong Fall Precedes Slow Winter Bookings"
24. Hughes Knittel Sperling 2008 short-run elasticity
25. Shih Nicholls Holecek 2009 lift ticket weather
26. Falk 2010 snow depth dynamic panel
27. I-70 corridor weekend congestion Berthoud alternative
28. I-70 Coalition survey avoid weekends
29. Aspen / Vail visitor income surveys (ext.)
30. Winter Park Fraser Chamber RRC visitor survey (ext.)
31. large vacation rental group cost split per person (ext.)
32. Colorado Tourism Office Longwoods 2025 visitor profile
33. Grand County / Fraser / Winter Park STR license caps
34. Ikon vs Epic 2026-27 prices
35. DEN 2025 passengers, Canada
36. Winter Park summer events, weddings, biking
37. Canadian visitors Colorado decline 2025-26
38. Texas spring break 2027 dates
39. Winter Park affordable family vs Vail/Aspen
40. Adversarial: high gas hurting Colorado mountain tourism summer 2026 (ext.)
41. Grand County lodging tax marketing district 1.8% collections by month -> GCCTB 30-year release (50% county-wide / 50% by region), DOR county lodging district spreadsheet (annual only), DR 1490 filed with sales-tax frequency
42. Town of Fraser sales tax report monthly lodging -> Fraser 2024 annual Sales Tax Report only (https://www.frasercolorado.com/DocumentCenter/View/2127/2024-Sales-Tax-Report)

Fetches (not counted as searches): AirROI ×7 market pages, Inntopia Nov/Dec 2025 notes,
   SnowSportsNews May 2026, Post Independent Sept 2026, Gazette June 2026, RRC case studies ×2,
   Stevens 2014 full text, Steiner 2026 abstract, Parthum & Christensen full text, I-70 2024 report.

What each yielded is summarized where it is cited. Dead ends: AirDNA and SAM (403), Westword
(403), GCCTB 2024 PDF and Grand County market analysis (encrypted / undecodable text), Town of
Winter Park April 2026 report (image-only), OTIS county/route station queries (404; solved through
the ArcGIS station layer).

## Appendix B — data pulls (reproducible) and pulls still needed

Done (scripts in `/private/tmp/wp_research/scripts/`): `parse_eia.py` (EIA monthly), `h4_daily.py`
(EIA weekly), `parse_ejmt.py`, OTIS monthly JSON for 000223/000106, `fetch_daily.py` (OTIS hourly →
daily), NRCS AWDB daily 335:CO:SNTL 1991–2026, FRED CPIAUCSL/COUR, DOR city/county xlsx →
`build_tax.py`, Winter Park town reports Dec-2025 and Jan–Aug 2026 → `h5_lodging.py`,
`h5_share.py`, `h4_monthly.py`, `h4_robust.py`.

Still needed to settle open points:
1. Town of Winter Park monthly reports 2016–2019 (lodging sector) to extend the lodging share series
   to ~10 seasons (wpgov.com archive or records request).
2. Town of Fraser lodging/sales tax monthly by sector (only the 2024 annual report is online).
2b. Grand County 1.8% marketing-district lodging tax by month: filed on DOR form DR 1490 at sales-tax
   frequency, so DOR holds it monthly; public tables are annual (request from DOR or GCCTB;
   https://www.visitgrandcounty.com/press-releases/30-years-of-grand-county-colorado-tourism-board/).
3. Hourly OTIS data stored per hour for winter days (closure detection) — rerun `fetch_daily.py`
   saving hours.
4. DestiMetrics Winter Park-specific occupancy/ADR by month and by price tier (subscription).
5. Grand County Datafy origin × lodging-type cut (DMO).
6. Guesty full-year per-home monthly shares (first party; percentages only).

## Self-audit

| MUST (00_DEPTH_STANDARD.md) | PASS/FAIL | Evidence |
|---|---|---|
| Cite every non-obvious claim inline with URL + access date | PASS | URLs inline; single access date 2026-10-16 stated in header |
| ≥ 40 distinct sources | PASS | 55+ distinct URLs plus repo files |
| ≥ 4 source classes | PASS | (1) academic: Hughes et al. 2008, Stevens et al. 2014, Steiner et al. 2026, Oh & Hammitt 2011, Parthum & Christensen 2022, Englin & Moeltner 2004, Falk 2010 (7); (3) vendor: AirROI ×7, AirDNA, Key Data, Inntopia ×3 (12); (4) industry body: I-70 Coalition/RRC, Colorado Ski Country USA (via press), NSAA (secondary) (3); (6) government: EIA ×2, FRED ×2, CDOT ×6, NRCS, DOR, Town of Winter Park ×2, FHWA, Dallas Fed, DEN, Grand County (≈18); (7) trade press/news: ≈15 |
| Read primary sources where they exist | PASS (partial) | Primary data downloaded and analysed; Parthum & Christensen and Stevens full text read; Steiner 2026, Hughes 2008, Falk 2010, Shih 2009 abstract/record only (paywall noted) |
| Mark UNVERIFIED / STALE | PASS | Grand County income, Texas calendars, rail share, PM attribution marked UNVERIFIED; pre-2023 sources marked STALE |
| No invented statistics/citations | PARTIAL (revised 2026-10-19) | No fabricated sources, but the review found two misquotes and one uncited figure ($4.54 Grand County gas, a pre-Easter "travel held up" source, and "Denver inflation 5%"). All three are withdrawn or re-sourced, and the comp-tier figures were relabelled to the right population |
| Several passes: broad, specific, adversarial | PASS | broad (1–20), specific named papers (24–26, 32), adversarial (40; the 2026 cheap-gas/low-traffic test; spec-sensitivity of daily gas β) |
| Mechanisms, not names (math/algorithm) | PASS | §2.2 regression specification, §2.5 daily model, §3.4 per-guest all-in formula; recommendation 2's decision rule is now a simulator hypothesis, not a derived rule |
| Quantified evidence of impact, conflicts noted | PASS | elasticities with season-level CIs (§2.3); H7 impacts are order-of-magnitude priors; vendor (AirROI, Inntopia, STR) conflicts noted |
| Map every finding to the engine (module + owner-net measurement) | PASS | §7 table and §9 |
| Honest transferability (3 homes, thin data, groups, fees) | PASS | §3.4, §5 (closures vs multi-night groups), §2.7 (fuel share of group cost) |
| "What generic STR pricers miss" note | PASS | §8 |
| Ranked recommendations with impact, confidence, effort, data, measurement | PASS | §9 |
| Open questions for the operator | PASS | §10 |
| Self-audit table | PASS | this table |
| Running search log appendix | PASS | Appendix A (42 searches, ~45 fetches) |
| Prefer 2020–2026 sources plus classics | PASS | most data 2016–2026; classics flagged STALE |
| No booked revenue / guest data / Guesty ids in docs | PASS | first-party figures are counts and the published dossier-01 aggregates; comp figures are public asking prices |

## Appendix C. Response to review

Review: `reviews/R7_review.md`, ACCEPT WITH FIXES (17 items). Fix pass by the author (2026-10-17,
recorded in this appendix only), consistency pass (2026-10-17: H4 verdict surfaces; three sentences
withdrawn), and close-out audit (2026-10-19: the remaining fixes applied to the body). The audit
re-ran the reviewer's `rev_checks.py` (identical output) and re-queried `comp_snapshots` read-only.

| # | Status | What changed or why not |
|---|---|---|
| 1 | applied | Glance line, §2.7 and the verdict table say "no effect detected in winter, bounded small"; a 30% gas rise is bounded at about 4% of access traffic (2026-10-17). §2.3 states the same bound (2026-10-19). |
| 2 | applied (2026-10-19) | §2.3 adds season-clustered, season-block-bootstrap and season-aggregated estimates and the 85% between-season variance share. §2.2 corrects the Newey–West description to rows, not months. |
| 3 | applied (2026-10-19) | §2.3 reports the I-70-controlled summer estimate (−0.045 [−0.110, +0.019]), the season-aggregated results and the daily summer estimates. Summer is "suggestive, about −0.1, not robust". The "2 of 4 specs" sentence stays withdrawn; the table now shows which specifications exclude zero under which inference. |
| 4 | partly | §2.3 adds the endogeneity paragraph and applies one standard to the positive tax β, the positive trend β and the negative summer β. **No supply-shock IV and no UMich/real-PCE controls were run.** The result is labelled predictive, not causal. |
| 5 | applied | §2.4 is "The 2026 case study", and the verdict says snow dominated rather than "mis-attributed". |
| 6 | applied (2026-10-19) | §2.2 and §2.3 report I-70 levels −0.102, Berthoud 2010+ −0.081 and the near-zero snowfall-proxy coefficient. "Levels gives similar signs" is corrected. |
| 7 | applied (2026-10-19) | §3.2 uses `comp_snapshots` ok rows (Jan $2,073 / p90 $3,098, n = 308; Dec $1,267; Sep $1,104) and withdraws the `market_snapshots` figures. Per-slot figures restated with the recorded `sleeps` values. The 3–5× claim is now about 3.9×. |
| 8 | applied | Grand County $4.54 and the Easter sentence withdrawn (2026-10-17). Denver inflation re-sourced to 3.9% (USAFacts) and the uncited 5% withdrawn; March gas rise attributed mainly to seasonal factors with a lagged war effect; Canada −43.9% linked to the December 2025 release (2026-10-19). |
| 9 | applied (2026-10-19) | §2.6 adds Canina, Walsh & Enz 2003 (reconciled: upscale least affected), STR 2022, Levin, Lewis & Wolak 2017 (and how the daily model answers it), Edelstein & Kilian, and CSCUSA 2008-09 Front Range +2.5%. Sources via the review; the Canina coefficient is press-summary only. |
| 10 | applied (2026-10-19) | §1.5 leads with 71.7% of ski-season town-remitted lodging and its CI. PM-office attribution is the primary caveat. The DOR quarterly-filer statement now says net bias of unknown sign. The PDF header artifact is explained. |
| 11 | applied, with a correction to the review (2026-10-19) | Snow hangover is presented with a test design in §7, §8, §9 rec 3 and the verdict table. **The review's premise was wrong:** re-opened on 2026-10-19, the Post Independent article attributes the softness partly to "lingering effects from poor snow", called a "snow hangover" per Foley, as well as to economic pressure and travel costs. It also cites an Inntopia study in which winters after the five worst snow years finished with occupancy +2.5% and revenue +4.9% on average. The dossier now treats the hangover as a practitioner-reported booking **delay**, not a level cut, which is a weaker claim than either the original draft or the review. |
| 12 | applied (2026-10-19) | Rec 2 is a simulator hypothesis with a paired owner-net test on low-snow seeds. "Price cannot fix" is removed. ±10–20% is exposure, not recoverable impact. |
| 13 | applied (2026-10-19) | §7 gives order-of-magnitude owner-net priors aligned with S1's roadmap, with the derivation caveat (judgment; all below the field MDE). |
| 14 | partly | §4 states that relative segment sizes are UNKNOWN except rail, and that the 15-day first-party lead time is not a winter figure (72 days per AirROI). No GCCTB/Datafy, CSCUSA in-state or DEN share was obtained. |
| 15 | applied (2026-10-19) | §3.4 shows the formula, $2,427 at 8 guests and $2,577 at 14, and states that lodging and sales tax and platform guest fees are excluded, with an approximate taxed range. |
| 16 | applied (2026-10-19) | Breckenridge peak/low marked not comparable; the column is indicative only. |
| 17 | applied | "Every 2025–26 DestiMetrics tier table" withdrawn (2026-10-17). |

Open evidence gaps remain: longer town lodging history (2016–2019 reports), Fraser and Grand County
monthly lodging series, a supply-shock instrument for H4, hourly closure data, Winter Park-specific
DestiMetrics data, and origin-by-lodging-type shares.
