# R7 review: Winter Park demand drivers

Reviewer: adversarial reviewer (V_REVIEW.md). Date: 2026-10-16. Access date for all URLs: 2026-10-16.
Dossier reviewed: `docs/research/deep_2026-10/R7_winter_park_demand_drivers.md` (620 lines).
Reproduction work: the author's scripts were copied to `/private/tmp/wp_research/review/` (outside the
repo). Reviewer-only checks are in `rev_checks.py` and `comp.py` there. Everything ran under `python3 -I`.
The repo database was opened read-only (`mode=ro&immutable=1`), and only the public comp tables were read.

Status: COMPLETE (2026-10-17)

## 1. Reproduction of the headline numbers

| Claim in dossier | Reproduced? | Reviewer note |
|---|---|---|
| H5: WP lodging Nov–Apr share 71.7% (n = 5, range 69.5–72.8), Dec–Mar 61.4% | **Yes, exactly** (0.695/0.726/0.728/0.721/0.714 → 0.717; Dec–Mar mean 0.614) | Hard-coded monthly lodging tax in `h5_lodging.py` checked against the PDF text of the Dec-2025 town report (`TOTAL SALES TAX - LODGING` table) and the 2026 monthly reports. The 2025 row sums to the report's YTD (5,797,116 vs 5,797,115). The derived April 2026 value (141,325 = May YTD 2,709,164 − Mar YTD 2,463,090 − May 104,749) checks out. The 7%→9% rate step on 1 Jul 2024 is confirmed by the report's own text ("Lodging Tax rate from 1% to 3%, which became effective on 7/1/2024"), and the sector totals include the 2% Transit & Trails tax (sector rows sum to the total including T&T), so dividing by 7%/9% is right. One oddity: the supplemental lodging table's column header reads "February … January", but the Dec values match the industry-sector table (Dec-25 838,951; Dec-23 697,872; Dec-21 585,001), so the values are Jan–Dec and the header is a PDF artifact. The author handled this correctly but should say so. |
| H5: all-taxable WP 68.5% Nov–Apr ex-COVID, 57.6% Dec–Mar; Fraser 51.8%; Grand 49.3%; comparator towns | **Yes** (`h5_share.py` output identical) | — |
| H4 monthly table (all 13 rows) | **Yes, every row to 3 dp** (`h4_monthly.py`, `h4_robust.py`) | See §2 for specification issues. The author left out some rows that the same scripts print (see §2.3). |
| Snow coefficient monthly +0.83…+0.91%/in; WP real taxable +2.0%/in [+1.0, +3.1] | **Yes** (+0.0083…+0.0091; +0.0203 ± 0.0105) | — |
| Daily model: gas −0.151 (season FE) / +0.198 (trend); SWE +1.28% / +2.22%; storm −0.88%; DOW +39/+40/+45; Xmas +41, Thx +28, Pres +20, MLK +12 log points | **Yes, exactly** (`h4_daily.py`, n = 1,611) | Summer daily +0.068 / −0.138 also reproduce. |
| 2026 natural-experiment table (real gas, Berthoud, I-70, SWE, lodging YoY) | **Yes, every cell** | Nominal gas YoY is −18.2% (Jan) and −11.5% (Feb), not −20.1%/−13.6% (those are real). Fine, but label it. |
| Lodging tax Aug 2026 −22.8%, Jul −11.5% | **Yes**: the town Aug-2026 report gives Lodging 235,379 vs 304,779 (−22.8%) | — |
| Large-home comp tier: 5 BR median $1,732 (n = 450), 7 BR $2,598 (n = 148) | **Yes** (`comp_snapshots` ⨝ `comps`, `scrape_status='ok'`, Dec–Mar stays) | — |
| Large-home comp tier: Jan p50 $1,684 / p90 $2,344; Feb $1,843/$2,255; Dec $861/$1,382; Sep $340/$716 | **Reproduced, but the label is wrong** | These are medians of `market_snapshots` p50/p90. That table is **not** the 22-home luxury comp set. The median snapshot covers 11 listings in January but **231 listings in September** and 244 in August (the broad market sweep). So the "Jan $1,684 vs Sep $340" contrast compares two different populations. The actual 22-comp set (`comp_snapshots`, ok rows) gives a Jan median of **$2,073** (p90 $3,098, n = 272), Dec $1,267 (n = 408) and Sep $1,104 (n = 100). The dossier understates the luxury January tier by about 19% and greatly overstates its seasonal swing. |

## 2. Specification audit (H4 and H5)

### 2.1 Year-over-year differencing and the real sample size

The Δ₁₂ log specification is a sound choice for removing seasonality, and the author picked it
deliberately. The problem is that **n = 134 overstates the information**. The 134 Nov–Apr rows come
from only **23 seasons**, and **85% of the variance in YoY real gas is between seasons** (reviewer
calculation: total var 0.0465, mean within-season var 0.0070). Consecutive months share the same
12-month gas change, so the effective sample is closer to 23 than to 134. The Newey–West lag is
counted in **rows**, not calendar months (`ols_hac` runs over the filtered row list). With 6 rows
per season, "12 lags" spans about two seasons. That happens to be a defensible bandwidth, but the
dossier describes it as 12 months, which it is not.

Reviewer re-estimates (`rev_checks.py`):

| Spec | Author (NW-12 rows) | Season-clustered (23–25 clusters) | Season block bootstrap (2,000) | Season-aggregated OLS (n = 23–25) |
|---|---|---|---|---|
| Berthoud Nov–Apr | +0.058 [−0.070, +0.185] | +0.054 [−0.095, +0.204] | [−0.096, +0.179] | +0.091 [−0.044, +0.227] |
| Berthoud Nov–Apr + unemp | +0.040 [−0.054, +0.135] | [−0.056, +0.137] | [−0.099, +0.132] | +0.078 [−0.052, +0.208] |
| Berthoud Nov–Apr, gas lagged 1 / 2 months (booking-time gas) | — | +0.038 / +0.073 | [−0.100, +0.150] / [−0.047, +0.184] | +0.105 / +0.117 |
| Berthoud Nov–Apr + I-70 traffic control | — | +0.062 [−0.054, +0.178] | [−0.080, +0.154] | +0.095 |
| Berthoud Jun–Sep | −0.098 [−0.197, +0.001] | −0.100 [−0.195, −0.006] | [−0.196, −0.014] | −0.110 [−0.262, +0.041] |
| Berthoud Jun–Sep + unemp | −0.127 [−0.235, −0.019] | [−0.234, −0.020] | [−0.224, −0.019] | −0.132 [−0.273, +0.009] |
| Berthoud Jun–Sep + I-70 control | — | **−0.045 [−0.110, +0.019]** | [−0.110, +0.018] | −0.046 |
| I-70 Jun–Sep + unemp | −0.087 [−0.119, −0.054] | [−0.134, −0.039] | [−0.125, −0.030] | −0.098 [−0.169, −0.027] |

Conclusion: the **winter null survives** every inference method, gas lags of 1–2 months, and the
I-70 control. **The summer Berthoud effect is fragile**: it survives clustering but not season
aggregation, and it halves and loses significance once I-70 traffic is controlled for. In other words,
the summer drop at Berthoud is mostly common to the whole I-70 mountain corridor. That fits a
statewide fuel or macro effect, but nothing specific to Winter Park. (I-70 is a "bad control" if gas
moves I-70 too, so this is not decisive, but the dossier should report it.)

### 2.2 Power: "not supported" vs "not detected"

The winter monthly CI lower bounds are −0.07 to −0.13, and the season-FE daily CI reaches −0.31.
The data therefore **cannot exclude** the literature's short-run VMT elasticity (≈ −0.1 to −0.15,
FHWA/Brand). The verdict "NOT SUPPORTED" reads as "no effect". The defensible wording is
"**no effect detected; winter effect bounded at ≤ about 4% of access traffic for a 30% gas rise**".
H4 as stated ("gas is *suppressing* demand") is a claim about *direction*, and a −4% effect would
count as suppression. The dossier's own text in §2.5 ("every CI excludes effects larger than about
−0.3") contradicts the monthly summary in the self-audit and §7 ("CI excludes < −0.13 monthly").
Pick one bound and state the MDE.

### 2.3 Endogeneity and confounding

- **Gas is not exogenous to demand at the macro level.** Retail gas tracks crude, and crude rises in
  booms (2005–08, 2021–22) when leisure travel also rises. That biases β **toward positive**, so a
  near-zero winter β is compatible with a modestly negative causal effect. The unemployment control
  is a weak macro proxy. The author drops the positive tax-sales β (+0.15 to +0.20) as "spurious" for
  exactly this reason, but keeps the negative summer traffic β at face value. The asymmetry is not
  justified. Fixes: (a) instrument with an oil *supply*-shock series (Kilian 2009 or Baumeister &
  Hamilton 2019 shocks, or the 2026 Hormuz shock as a dated event), or (b) add US real PCE/consumer
  sentiment (UMich) plus a Denver-area employment series as controls, and report β both ways.
- **Snow.** Control is via the YoY change in the monthly mean SWE anomaly. That is adequate for
  monthly data. The 2026 "natural experiment" is **not** a natural experiment in the causal sense.
  It is one season in which snow and gas moved in opposite directions in Jan–Feb and the *same*
  direction in Mar–May. It shows that snow dominated, not that gas has no effect. Rename it and drop
  "mis-attributed" from the verdict bullet, or soften it to "dominated by".
- **Outcome validity.** US-40 ADT mixes residents, freight, RMNP/Grand Lake through-traffic (summer)
  and day-trippers. Overnight lodging demand is a minority of it. The traffic elasticity is a weak
  proxy for 5+ BR lodging demand, which the dossier says only in §2.7. Lodging tax is the better
  outcome, but it has only about 5 clean seasons.
- **CPI deflation.** CPI-U all items includes gasoline (a small weight). Nominal and real results are
  identical (−0.004 vs −0.006, all months), so this does not matter. The Oct-2025 CPI interpolation
  is fine.
- **COVID handling.** Dropping Mar 2020–Jun 2021 *and* every YoY pair whose base month falls in that
  window is correct (`h4_robust.yoy` checks both ends). The daily model uses 14 Mar 2020 – 30 Jun 2021.
  The 2021-22 rebound winter therefore never enters the monthly winter regressions, which is good,
  though the dossier does not mention it.
- **Unreported rows.** `h4_monthly.py` also prints Berthoud all-months 2010+ β = −0.081
  [−0.165, +0.002] and I-70 levels all-months β = −0.102 [−0.175, −0.028] (Dec–Mar levels −0.080).
  §2.2 says "A levels version … gives similar signs", but the I-70 levels results are more negative
  than anything in the table. Report all printed specifications, or a specification curve.

### 2.4 H5 specification

- **n = 5 seasons is enough for this question**, because the share is very stable: range 69.5–72.8,
  SD ≈ 1.3 pp, t-based 95% CI on the mean ≈ 70.1–73.3%. "About 70%" is inside the CI. The
  limitation is not n but **definition and attribution**:
  1. The verdict leans on Nov–Apr. Dec–Mar gives 61%. The practitioner's "winter months" most
     likely means the ski season (the resort runs roughly mid-November to mid-April), so Nov–Apr is
     a fair reading. The dossier should still lead with "71.7% of ski-season (Nov–Apr) lodging; 61%
     for Dec–Mar", not "SUPPORTED".
  2. Lodging tax is attributed to the **PM office's location**. The Outside-County business
     location is 17% of all town sales tax. If large-home PMs or marketplace facilitators remit from
     outside, the town series under-represents exactly the 5+ BR tier we price. Mark this as the main
     validity threat.
  3. The lodging series starts in 2020. The all-taxable series shows the winter share falling from
     71% (2016-19) to 64% (2025-26). It is not known whether the lodging share also fell before 2020.
     Pulling the 2016–2019 town reports would settle that cheaply. The dossier lists this pull, but
     its claim "lodging share has been flat at ~72%" covers 5 years only.
- **Season-year choice.** May–April is fine, and the share is computed within the season-year, so
  the rate change and the DOR unit change do not bias it. Confirmed.
- **DOR quarterly filers.** These shift sales into Mar/Jun/Sep/Dec. Under Nov–Apr the June spike
  (holding Apr–Jun sales) moves April sales *out* of winter, and the December spike (Oct–Dec) moves
  October sales *in*. The net bias is small and of unknown sign. The dossier says the shares are
  "unaffected", which is not established. The town lodging series is presumably monthly-remitted and
  less exposed. Note this.

## 3. Citation spot-check (22 URLs opened, plus 3 local copies of cited PDFs)

| # | Cited URL (claim) | Result |
|---|---|---|
| 1 | postindependent.com …/colorado-ski-destinations-see-slow-start-to-winter-bookings/ (Colorado Nov–Jan bookings −10.9%, Nov–Feb occupancy −4.4%, ADR ≈ −2% as of 31 Aug 2026; gas +27%, airfare +23%; August-for-August −26.7%) | **Supports**, all six figures. The article attributes them to "Inntopia" (Tom Foley); DestiMetrics is Inntopia's product, so the label is fine. Note that the same article blames gas, airfare and sentiment, **not** a "snow hangover" (see §5). |
| 2 | wpgov.com …/2026-08-Sales-Tax-Report-collected-Sep-26.pdf (WP lodging −22.8% Aug 2026) | **Supports.** The live fetch returned an undecodable PDF; verified against the author's downloaded copy: Lodging 235,379 vs 304,779 = −22.8%. |
| 3 | wpgov.com …/2025-12-Sales-Tax-Report-collected-Jan-26.pdf (lodging series 2020–25, 1%→3% on 7/1/2024, PM-office attribution) | **Supports** (local text layer; see §1). |
| 4 | airroi.com …/winter-park (ADR $437, median $338, top-10% $802, peak $532, low $373, occ 31.5%, 1,185 listings) | **Supports**, every figure. |
| 5 | airroi.com …/vail ($819 / $593 / $1,588 / $1,083 / $665 / 29.4% / 1,594) | **Supports**, every figure. |
| 6 | airroi.com …/breckenridge ($581 / $426 / $1,067 / peak $747 / low $487 / 36.7% / 3,171) | **Partly.** ADR, median, top-10%, occupancy and listings match. The page gives peak $790 and low $470 as *best/worst single month*, not the 3-month seasonal averages used for WP. The peak/low columns are not computed the same way across markets. |
| 7 | dtdapps.codot.gov OTIS ArcGIS layer (station ids 000223 "ON SH 40 E/O HENDERSON MINE RD", MP 248.719–254.313, AADT 8,300; 000106 at Eisenhower Tunnel, MP 205.4–216.2, AADT 35,000) | **Supports**, exactly. |
| 8 | OTIS `GetMonthlyTrafficVolumeForStation/000223.json` | **Supports.** Live 2026 Jan–Sep values (8,818 … 8,187) are identical to the author's file. |
| 9 | gazette.com 2026/06/04 (Colorado skier visits −24% to 10.5 M, CSCUSA) | **Supports.** |
| 10 | gazette.com 2026/03/04 (gas spike after US–Iran war / Hormuz) | **Partly.** The article says the early-March rise was mainly **seasonal** (summer blend, demand). It calls Hormuz a risk that would reach the pump in 2–6 weeks. The dossier attributes the jump to the war outright. |
| 11 | kktv.com 2026/09/07 (record Labor Day gas) | **Supports** ($4.19 CO average). The article gives no cause. |
| 12 | postindependent.com …/colorado-high-country-gas-prices-spike/ ("$4.54 in Grand County on 2 Sep 2026", AAA in-state substitution) | **Does not support as cited.** The page reports Grand County **$4.50 on 5 May 2026**. The AAA in-state-substitution quote is supported. |
| 13 | steamboatpilot.com …/gas-prices-surge-in-mountain-towns-but-easter-travelers-arent-staying-home/ ("Easter 2026 mountain travel held up") | **Does not support.** Published 3 Apr 2026, before Easter. It quotes an analyst expecting visitation "pretty much flat or down" and reports no outcome. |
| 14 | corp.inntopia.com …/summer-finishes-modestly… (gas +4.1% as "pressure") | **Supports** that claim. The dossier §4 also cites "Canadian −43.9% (seasonal, Nov 2025) … links in §2", but this Nov-2025 note says **−52.9%**. The −43.9% comes from the *December* 2025 DestiMetrics release, which is not linked. **Wrong link.** |
| 15 | snowsportsnews.com 2026/may DestiMetrics (summer OTB +4.9%, inflation 3.8%, sentiment near record low, Canada −42.6% vs 2024, luxury held up) | **Supports.** The luxury evidence is for *summer* only. "Every 2025–26 DestiMetrics tier table" (§2.7) overstates it. |
| 16 | pmc.ncbi.nlm.nih.gov PMC10936566 (Parthum & Christensen 2022: 0.223 national, 0.135 CO, 0.21 Mountain West; 12.5 M obs, 236 resorts, AirDNA 2014–17) | **Supports**, every figure (Mountain West 0.208). |
| 17 | nber.org w12530 (Hughes, Knittel & Sperling: −0.21…−0.34 → −0.034…−0.077) | **Supports.** |
| 18 | dallasfed.org 2020/0616 ("newer instrument gives −0.27 to −0.35") | **Partly.** −0.27…−0.35 is Levin, Lewis & Wolak's daily-transaction estimate, not an instrument. The page's central point, that **monthly aggregate time series bias elasticities toward zero**, applies directly to R7's own monthly design, and the dossier leaves it out. |
| 19 | fhwa.dot.gov …/impacts.cfm (2008 VMT −0.12…−0.30; lit. SR −0.15, LR −0.30; rural single-earner −0.09) | **Partly.** All numbers are present, but −0.091 is a *fuel-consumption* elasticity, not VMT, and the page itself gives two long-run values (−0.30 and −0.25). |
| 20 | js.sagamorepub.com …/13064 (Steiner, Stinespring & Dieringer 2026) | **Supports** ("modestly responsive" to fuel, insensitive to fees; 30 parks × 30 years; FEGLS). |
| 21 | aspenchamber.org/about/demographics/ ($143,506, n = 929, March 2025, online) | **Partly.** $143,506 (Future Partners 2025) is confirmed. The page states no n, date or method; those details come from elsewhere and are uncited. |
| 22 | steamboatpilot.com …/ikon-pass-2026-27-on-sale-higher-price/ (Ikon $1,399 vs Epic $1,089) | **Supports.** |
| 23 | codot.gov CTIO April 2026 WPE recap PDF (39,451 riders, 57 round trips, 88% load factor) | **Supports** (live fetch 404 today; confirmed via the search-index copy of the same PDF). Note that it is labelled a *draft*. |
| 24 | colorail.org (2,751 continued to Fraser) | **Supports.** |
| 25 | cbsnews.com Berthoud ~30 h closure | **Supports** ("closed for nearly 30 hours"). |
| 26 | codot.gov Sept 2026 US-40 MP 236–240 rock holds | **Supports.** |
| 27 | i70solutions.org 2024 user survey (3,611 FR respondents, 92%, 75% reduced, 10.4 days, 61% weekends) | **Supports** (author's local text layer: "Three-quarters … reduced"; "10.4 … 61% … weekends"). |
| — | flydenver.com 2025 milestones | Dead to fetch (403); not counted. |

**Tally (27 checked): 19 support, 5 partly, 2 do not support, 1 wrong link (the Canada figure; the URL itself supports a different claim). No fabricated citations found.** One factual claim has **no citation at all**: "Denver-area inflation 5% in mid-2026, Colorado Sun" (§2.4). The reviewer found Denver CPI at 3.9% y/y to July 2026 (USAFacts, https://usafacts.org/answers/what-is-the-current-inflation-rate/metro-area/denver-co/) and no such Colorado Sun piece. Treat it as unsupported.

## 4. Depth audit (MUSTs checked by the reviewer)

| MUST | Reviewer finding |
|---|---|
| ≥ 40 distinct sources | **PASS.** 58 distinct URLs in the text, plus 6 more AirROI market pages written as "…/fraser" etc. |
| ≥ 4 source classes | **PASS.** Academic (7: Hughes et al., Stevens et al., Steiner et al., Oh & Hammitt, Parthum & Christensen, Englin & Moeltner, Falk), government/official (≈ 20: EIA, FRED, CDOT ×8, NRCS, DOR, Town of WP ×3, FHWA, Dallas Fed, DEN, Grand County, Fraser), vendor (AirROI, AirDNA, Key Data, Inntopia), industry body (I-70 Coalition/RRC, CSCUSA via press, NSAA secondary), trade press/news (≈ 15). No textbooks, which is acceptable for this topic. |
| Inline URL + access date | **PASS** (single header access date). Exceptions: the uncited "5% Denver inflation" and the uncited Aspen survey details. |
| Primary sources | **PASS.** This is the dossier's strength: primary data was downloaded and analysed. |
| UNVERIFIED / STALE marking | **Mostly PASS.** Missing: the "Easter held up" claim, the Hormuz attribution and the "every DestiMetrics tier table" claim should be UNVERIFIED or removed. |
| No invented statistics | **FAIL on two items** (not fabrications of sources, but misquotes): $4.54 / 2 Sep 2026 (the source says $4.50 / 5 May) and Denver inflation 5% (no source). The self-audit claim "every number traces to a downloaded series or cited page" is therefore false. |
| Search passes incl. adversarial | **PASS (thin adversarial on gas).** It missed the two most direct contrary sources (§6). |
| Mechanisms | **PASS** for regressions. **Weak** for recommendation 2's decision rule ("hold rate until snow decides"), which has no demand model behind it (§5). |
| Quantified impact + conflicts | **PASS** for elasticities. The H7 "Est. impact" column is qualitative only (High/Medium/Low). |
| Map to engine + owner-net measurement | **PASS** (§7, §9). |
| Transferability | **PASS** (fuel share of a group's trip cost; closures vs multi-night stays). |
| "What generic pricers miss" | **PASS** (§8). |
| Recommendations / open questions / self-audit | **PASS** in form. The self-audit overstates (see "No invented statistics"). |
| No booked revenue / Guesty ids / guest data | **PASS.** Grep found no 24-hex ids, no names, no payouts. First-party content is limited to a reservation *count* (54), dossier-01 party-size aggregates, and public comp asking prices. |

## 5. Reasoning problems (overclaiming)

1. **"Snow hangover" attribution (H7 rank 3, rec 3).** The −10.9% / −4.4% / −2% DestiMetrics
   figures are Colorado-wide. The source article attributes the softness to gas +27%, airfares +23%
   and consumer sentiment, not to prior-season snow. The dossier uses these numbers as evidence of a
   *snow* hangover in §7 and as evidence *against* gas in §2. Choose one reading. Better: say that a
   post-bad-snow-year booking lag is plausible but untested, and design the test (prior-season SWE
   anomaly vs early-season OTB pace across 10+ seasons of DestiMetrics or comp availability).
2. **Rec 2's rule ("do not cut price on behind-pace before mid-December in a below-normal snow
   year") is not derived from anything.** The analysis shows snow shifts *volume*. It says nothing
   about whether price elasticity changes in a low-snow year. Standard RM logic says that when demand
   shifts down, the revenue-maximizing price usually falls too. "A demand drop that price cannot
   fix" (§8) is an assertion. The rule may be right for a 3-home luxury group product with a high
   floor, but it must be framed as a hypothesis for the simulator: a paired owner-net comparison of
   snow-conditioned pace vs plain pace on 2025-26-like seeds, before it reaches `pace.py`.
3. **"±10–20% of winter revenue in play"** (H7 rank 2) is the Jan–Mar 2026 lodging-tax decline.
   That decline is how much revenue fell, not how much a pricing rule could recover. Restate it as
   exposure, not achievable impact.
4. **H4 verdict wording.** See §2.2. The winter evidence supports "no detectable effect; bounded
   small", not "NOT SUPPORTED". The "mis-attributed" bullet rests on one season that is confounded
   by snow.
5. **Summer "PARTLY".** Season-aggregated and I-70-controlled estimates include zero (§2.1), and the
   daily summer estimates (+0.07, −0.14) include zero. Two of the four Berthoud monthly specs exclude
   zero only under row-level inference. State that summer is "suggestive, about −0.1, not robust".
6. **Asymmetric treatment of "spurious" results** (positive tax β discarded, negative summer β kept),
   §2.3.
7. **Comp-tier seasonality** built on two different populations (§1, last row). The claim "5+ BR tier
   prices at 3–5× the town's peak-season ADR" survives with the correct comp-set numbers (Jan $2,073
   vs $532 is 3.9×), but the Dec ($861) and Sep ($340) figures must be replaced.
8. **All-in per-guest arithmetic** (§3.4). "$2,427/night" holds only at 8 guests ($2,000 +
   ($600 + 8×$75 + $80)/3). At 14 guests it is $2,577 (/14 = $184, which matches the stated figure).
   Neither includes lodging/sales tax (9% town + county/state) or platform guest fees, both of which
   appear in the all-in prices guests see. Add them, or say they are excluded.
9. **H1 "luxury tier has held up better … in every 2025–26 DestiMetrics tier table"** is
   unsupported. The one fetched table (May 2026) is about summer.

## 6. Coverage gaps and reviewer's own searches (14 searches)

Prompt "cover at minimum" items:

| Item | Status |
|---|---|
| 1 H5 town/county/Fraser monthly tax, both winter definitions, first-party compare | Covered well. First-party share not computable (documented). Fraser lodging monthly is not online (documented). |
| 2 H4 EIA, CDOT station ids + portal, lodging tax, published elasticities, Python analysis with snow + holidays | Covered. Elasticity literature **misses the two most relevant hotel/lodging studies** (below). No supply-shock identification. |
| 3 H1 ADR distributions, Inntopia summaries, guest origin/income, Ikon demographics, per-guest lens | Mostly covered. **Thin:** Colorado Tourism Office/Longwoods (searched, nothing reported); Ikon demographics (none found); no Inntopia market-by-market ADR. |
| 4 Segments with relative size, lead time, price sensitivity | **Thin.** The table has no relative *sizes* (shares) for any segment except rail. Lead times are mostly assumed. |
| 5 Access shocks quantified on occupancy | Partly. Traffic effects of storm days are quantified; occupancy effect untested (honestly stated). Chain/traction-law days are not separated from storm days. |
| 6 Summer drivers, growth trend, how to raise | Thin on drivers (no Trestle or wedding counts; honestly stated). |
| 7 H7 ranked factors by revenue impact | Ranked, but impact is qualitative only. |

Reviewer searches and what they found (the author missed all of the following):

1. **Canina, Walsh & Enz (2003), *Cornell Hotel and Restaurant Administration Quarterly*** (a
   prompt-named journal), "The effects of gasoline-price changes on room demand". STR monthly data
   for branded US hotels 1988–2000. Press release: a 1% gas rise cuts room demand ≈ 1.74%, economy
   ≈ 2.89%, upscale least affected, strongest at highway/suburban locations
   (https://www.news.cornell.edu/stories/2002/05/gas-price-rise-could-cause-big-losses-lodging-industry ;
   https://ecommons.cornell.edu/entities/publication/3e4221b1-2e38-448a-8de7-694d5e8df7b8). STALE, and the
   magnitude is implausibly large (reviewer saw only the press summary, so it is UNVERIFIED as a
   coefficient). It is the main published *lodging* contradiction of R7's null and must be discussed,
   especially its finding that upscale is least sensitive, which supports R7's luxury argument.
2. **STR (2022), "Historical analysis: rising gas prices have limited impact on US hotel demand"**
   (https://str.com/data-insights-blog/historical-analysis-rising-gas-prices-have-limited-impact-us-hotel-demand):
   real gas vs room demand correlation 0.54 and vs RevPAR 0.16 since 1990. In interstate hotels, gas
   peaks coincide with occupancy peaks, i.e. the same seasonal/macro confounding R7 found. Vendor,
   but it is the industry benchmark and corroborates R7.
3. **Levin, Lewis & Wolak (2017), *AEJ: Economic Policy* 9(3):314–347** (NBER w22345,
   https://www.nber.org/papers/w22345). Elasticities from daily city-level data are an order of
   magnitude larger than from aggregated data, and monthly national aggregation yields ≈ 0. This is a
   direct methodological threat to a monthly aggregate design. R7's daily model partly answers it
   and should say so.
4. **Coglianese, Davis, Kilian & Stock (2017), *J. Applied Econometrics* 32(1):1–15**
   (https://scholar.harvard.edu/sites/scholar.harvard.edu/files/stock/files/coglianese_et_al-2017-journal_of_applied_econometrics.pdf):
   tax-instrument IV for gasoline demand, with anticipation effects. Relevant if R7 adopts an IV.
5. **Edelstein & Kilian (2009)** / Kilian supply-shock identification (Econbrowser summary
   https://econbrowser.com/archives/2007/05/new_study_of_th_1 ). Energy-price shocks cut services
   spending ≈ 1.5% and consumer sentiment more than proportionally. Gas affects leisure through an
   **income/sentiment channel**, not only trip fuel cost. This undercuts the "fuel is < 1% of trip
   cost, so no effect" argument (§2.6, §2.7) for the group segment.
6. **Sullivan & Picha (1982), ASCE *J. Transportation Engineering*** (https://ascelibrary.com/doi/10.1061/TPEJAN.0000979):
   1977–79 gas shock. Local attractions lost the most visitation; nationally drawing attractions lost
   the least. STALE, but it is the closest "attraction type × gas" evidence.
7. Ski-specific gas elasticity (two query forms): **none found**, which confirms the author's
   statement.
8. Colorado 2008 (gas peak) vs ski visits: CSCUSA 2008-09 visits −6.9%, but **Front Range visits
   +2.5%** (SAM, https://www.saminfo.com/news/sam-headline-news/5469-110-colorado-visits-dropped-5-5-percent-in-2008-09).
   This fits R7's substitution-toward-closer-trips argument. Worth adding.
9. Fuel-price substitution toward closer destinations: Longwoods 2026 tracking (44% cutting trips,
   a similar share going closer) via secondary reports; Pang (2014), *Tourism Economics* 20(6):1297–1318
   (https://ideas.repec.org/a/sae/toueco/v20y2014i6p1297-1318.html). Supports the offsetting-
   substitution mechanism R7 hypothesizes.
10. Colorado 2025-26: 26 areas −24%, days open 129 vs 144 average (Colorado Sun,
    https://coloradosun.com/2026/05/05/us-skier-visits-drop-2025-26/). This adds a *supply-side*
    (fewer operating days) channel to the snow story that the traffic model does not separate.
11. Denver CPI 2026: 3.9% y/y to July 2026 (USAFacts, above). This contradicts the dossier's
    uncited 5%.
12. Shih, Nicholls & Holecek (2009), *JTR* 47(3):359–372: snow depth, not snowfall, drives lift
    sales (secondary summary). This is consistent with R7's finding that SWE anomaly matters more
    than the snowfall proxy (whose coefficient is ≈ 0 in `h4_monthly.py`, unreported).
13. Inntopia December 2025 release (source of the −43.9% Canada figure; via SAM,
    https://www.saminfo.com/news/sam-headline-news/season-opened-slowly-at-most-western-destinations).
14. WPE recap search: the CTIO PDF is a draft. Prior-season ridership is 38,339 in CTIO's
    comparable basis but 43,919 per ColoRail; the bases differ.

## 7. Verdict: **ACCEPT WITH FIXES**

The dossier does real primary-data work, and every headline number reproduces exactly from the
author's scripts and the downloaded data: H5 71.7% / 61.4%, all 13 monthly H4 rows, the daily
model and holiday effects, the 2026 table, and the August lodging −22.8%. The winter-gas null is
robust to season clustering, season block bootstrap, season aggregation, 1–2-month gas lags and an
I-70 control. The H5 share is stable enough that n = 5 seasons supports "about 70%" under the
Nov–Apr definition. No fabricated sources, and no booked revenue, Guesty ids or guest data. The
problems are fixable: verdict wording that outruns power, a fragile summer effect presented as
robust, two misquoted and one uncited figure, a mislabelled comp-tier table, a missing lodging-
specific gas literature (CHRAQ 2003, STR 2022, Levin et al. 2017), and a snow-pace pricing rule
asserted without a demand model.

## 8. Numbered fix list

1. **H4 verdict:** change "NOT SUPPORTED (winter)" to "No effect detected in winter. A 30% gas rise
   moves access traffic by at most ≈ 4% (CI lower bound −0.13 monthly)." State one bound
   consistently in §2.5, §2.7, §7 and the summary table, and give the MDE.
2. **Report season-clustered or season-block-bootstrap CIs** alongside NW, and the season-aggregated
   estimate. Correct the NW description: lags are rows (≈ 2 seasons), not 12 calendar months. State
   that 85% of YoY gas variance is between seasons (≈ 23 effective observations).
3. **Summer:** add the I-70-controlled (−0.045 [−0.110, +0.019]) and season-aggregated results and the
   daily summer estimates to the verdict. Downgrade summer to "suggestive, ≈ −0.1, not robust".
   Clarify which "2 of 4 specs" exclude zero.
4. **Endogeneity:** add a paragraph on macro co-movement biasing β upward, and apply the same
   standard to the positive tax β and the negative summer β. Either run a supply-shock IV
   (Kilian/Baumeister–Hamilton series, or the dated 2026 Hormuz shock) or add UMich sentiment and
   real PCE controls and report both.
5. **Rename the "2026 natural experiment"** to "2026 case study". Replace "mis-attributed" with "in
   2025-26 the snow effect dominated any gas effect".
6. **Report every specification the scripts print**, including I-70 levels −0.102 [−0.175, −0.028],
   Berthoud 2010+ −0.081, and the ≈ 0 snowfall-proxy coefficient, or show a specification curve.
   Fix "levels gives similar signs".
7. **Fix §3.2 comp tier:** the Jan/Feb/Dec/Sep p50/p90 values come from `market_snapshots` (11
   listings in Jan, 231 in Sep), not the 22-home comp set. Replace them with `comp_snapshots`
   ok-row figures (Jan median ≈ $2,073, p90 ≈ $3,098; Dec ≈ $1,267; Sep ≈ $1,104) or label the
   populations. State the sleeps assumption behind "$115 / $166 per sleeping slot".
8. **Correct misquotes:** Grand County gas ($4.50 on 5 May 2026, not $4.54 on 2 Sep). Remove or
   re-source "Easter 2026 mountain travel held up" (the source predates Easter). Re-source Denver
   inflation (3.9% y/y Jul 2026, USAFacts; there is no Colorado Sun "5%"). Re-attribute the March gas
   rise (seasonal per AAA; war effects lagged). Link the December 2025 DestiMetrics release for
   Canada −43.9%. Then correct the self-audit row "No invented statistics".
9. **Add the missing lodging/gas literature:** Canina, Walsh & Enz 2003 CHRAQ (and reconcile its
   −1.7 elasticity and "upscale least affected" with R7), STR 2022, and Levin, Lewis & Wolak 2017
   (aggregation bias, plus why the daily model partly answers it). Also add the energy-shock
   income/sentiment channel (Edelstein & Kilian), which weakens the "fuel < 1% of trip cost" argument.
   Add CSCUSA 2008-09 Front Range +2.5% as substitution evidence.
10. **H5 framing:** lead with "71.7% of ski-season (Nov–Apr) town-remitted lodging (95% CI ≈ 70–73%,
    n = 5); 61% Dec–Mar". Make PM-office attribution the primary validity caveat, especially whether
    5+ BR PMs remit to Winter Park. Fix the DOR quarterly-filer statement (net bias of unknown sign,
    not "unaffected"). Note the PDF header artifact ("February … January") and how it was resolved.
11. **Snow hangover (rec 3, H7 rank 3):** reconcile with the source, which blames gas, airfare and
    sentiment. Present it as a hypothesis with a test design (prior-season SWE vs early-season OTB
    pace across seasons).
12. **Rec 2 decision rule:** reframe it as a simulator hypothesis with a paired owner-net test
    (snow-conditioned vs plain pace on low-snow seeds). Justify why holding price beats cutting when
    demand shifts down, or drop "price cannot fix". Restate "±10–20% in play" as exposure, not
    recoverable impact.
13. **H7 table:** replace qualitative High/Medium/Low with order-of-magnitude owner-net ranges and
    their derivation, even if rough.
14. **Segments table:** add relative size estimates (even ranges, with sources: GCCTB/Datafy origin
    shares, CSCUSA in-state share, DEN share) or mark each as UNKNOWN.
15. **§3.4 all-in math:** show the formula, include or explicitly exclude lodging taxes (9% town +
    county/state) and platform guest fees, and give the $2,577 all-in at 14 guests.
16. **Breckenridge peak/low ADR:** AirROI defines these differently across market pages. Recompute
    on one definition or drop the peak/low column.
17. Remove "every 2025–26 DestiMetrics tier table" or cite the tables (only the May 2026 summer
    table was found).

## Addendum: scoped re-review, 2026-10-19

The fix pass recorded resolutions in R7 Appendix C; the close-out audit applied fixes 2–16 to the
body. Consistency check by the same audit, not an independent review.

- `rev_checks.py` was re-run: every row of §2.1 above reproduces exactly; R7 §2.3 now carries them.
- `comp_snapshots` was re-queried read-only: January median $2,073 (n = 308, more data than at review
  time), December $1,267, September $1,104. R7 §3.2 uses these.
- **One correction to this review.** §3 row 1 and §5 item 1 say the Post Independent article blames
  gas, airfare and sentiment, "not" a snow hangover. Re-opened on 2026-10-19, the article attributes
  the slow start partly to "lingering effects from poor snow", which Foley calls a "snow hangover", and
  reports an Inntopia study in which winters after the five worst snow years finished with occupancy
  +2.5% and revenue +4.9% on average. R7 now treats the hangover as a practitioner-reported booking
  delay, not a level cut, which is weaker than both the original draft and this review's reading.
- H4 wording, the case-study label, the comp tier, the all-in arithmetic and the H7 priors are
  consistent across the glance line, §2.7, §7, §9 and the verdict table.

Verdict unchanged: ACCEPT WITH FIXES, fixes 4 and 14 partly applied (ledger in R7 Appendix C).
