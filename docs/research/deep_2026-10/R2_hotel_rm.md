# R2: Hotel and resort revenue management, and what transfers to three Winter Park homes

Date: 2026-10-16, revised 2026-10-17 after review (`reviews/R2_review.md`; responses in Appendix D). Every web source was accessed on 2026-10-16 unless marked (2026-10-17) for sources added in revision.
Scope: research only. No code edits, commits, Guesty writes or price changes were made. No booked revenue, Guesty ids or guest data appear here.
Method: 60+ web searches across broad, specific and adversarial passes, plus full-text reads of the primary sources marked **[read in full]**. The search log is in Appendix A and the self-audit in Appendix C.

Labels used throughout:
- **UNVERIFIED** marks a claim seen only in a secondary or snippet source.
- **STALE** marks data more than three years old (before October 2023).
- **VENDOR** marks a figure reported by the party that sells the product, which is a conflict of interest.

---

## 0. Summary

1. **Hotel revenue management is three things: forecasting with pickup, controlling length of stay with bid prices, and pricing against the market.** All three have a single-unit analogue for a large home. The one that hotels value most and that we lack entirely is **forward market occupancy**: how full the destination is for a future date, measured from bookings rather than prices (Demand360, Forward STAR, DestiMetrics). Our pace signal is computed from three homes. A ±3-day window holds at most 21 home-nights, but those nights are filled in multi-night blocks (typical LOS 4), so the effective sample is about 5 stays and the sampling error of the on-books share is about ±0.2. At long leads, where the expected share is small, the pace *ratio* is dominated by noise (§2.3). A comp-set on-the-books series of 20–40 large homes is about **3× more precise** (not 10×); only a full-market series such as DestiMetrics or a PriceLabs dashboard can do much better, and those are coarser in product mix.
2. **DestiMetrics does cover Winter Park, with caveats.** A DestiMetrics product sheet (c. 2016, STALE) lists Winter Park among its MTNWEST reporting destinations. Winter Park Central Reservations was a charter member of the central-reservations association whose members receive DestiMetrics "Reservation Activity" reports. Current Inntopia briefings cover 17 western mountain destinations but publish only regional aggregates, split into Colorado+Utah versus the rest of the West (Park Record, 2026-04-21, https://www.parkrecord.com/2026/04/21/after-a-warm-winter-western-resorts-are-hoping-for-a-better-summer/, accessed 2026-10-17). Access works by **contributing data**: DestiMetrics says participation in its Reservation Activity Outlook is a prerequisite for the comparative reports. Property-level reports cost **$250–$500 each, or $925–$2,000 per pack** (one-off prices; the page states no subscription period and no participation rule). No public price exists for destination-level access, and no Guesty integration was found. **Whether Winter Park is a current participating destination today is UNVERIFIED.** The cheapest way to confirm is to ask the Grand County Tourism Board or the Winter Park & Fraser Chamber, which publish "professionally managed" occupancy figures whose provider they do not name.
3. **Cheaper forward-occupancy substitutes exist and should be tested first.**
   - **PriceLabs Market Dashboard** costs $9.99 per dashboard per month, refreshes daily, shows forward occupancy and pickup with last-year comparisons, and can filter by bedroom count. Its marketing page says pricing "starts at" $9.99, so larger reports may cost more. Its help page does not document the data source; if, like most STR data vendors, it infers bookings from calendars, a blocked night can look booked (UNVERIFIED for PriceLabs).
   - **Key Data ProData** is built from PMS-direct reservations and shows a Winter Park page. Its price is custom-quoted.
   - **AirDNA pacing** covers six to twelve months forward. AirDNA's help page says six months; a claim that advance bookings carry little information beyond about four months comes only from a search snippet of a blocked AirDNA page (UNVERIFIED).
   - **Our own scraper** already records whether a comp is "checked and unavailable". Turned into a **large-home forward availability index**, that becomes a hyper-local Demand360. No vendor sells this for 5+ bedroom homes in Winter Park.
4. **Three hotel lessons map directly onto our weak spots:**
   - **Price elasticity cannot be learned from our own prices naively.** In a [read in full] Management Science study of 9 European hotels (8 of them resorts, about 60,000 bookings), naive regressions gave positive or near-zero price effects. Only when the system's recommendation was used as a control did plausible negative elasticities appear. One resort hotel's winter price sensitivity was not distinguishable from zero, far below its off-season sensitivity (Garcia, Tolvanen & Wagner 2022). Our M1 median-split estimator is the confounded design, and because M1 clips β to [−2.5, −0.3], its bias shows up as pinning at −0.3, which pushes price toward the ceiling. **But the fix does not transfer cheaply:** our move caps, deference and clamps are deterministic functions of the recommendation, so they give no identifying variation. Only the engine's own randomized exploration (M1's Thompson draws) and genuinely random approval lag do. With about 100 bookings, a power estimate (§3.1) puts the standard error of β near ±2.7 per season. Log the data now, and estimate only when the simulator shows adequate power.
   - **Length-of-stay controls are worth more than the nightly price on a few critical nights.** A blocking 1-night booking can destroy a multi-night sale (the hotel "Oktoberfest" problem). A bid-price rule per night, priced as the cost of the stay it displaces, replaces our ad-hoc orphan discount.
   - **Optimize net, not gross.** Hotels are moving from RevPAR to NRevPAR and GOPPAR. An HSMAI study found 53% of respondents who see limits in current metrics name the missing costs. For us the per-stay guest fees ($1,430 at 10 guests) make the **all-in nightly price of a 1-night stay 72% above the nightly rate**, versus 18% for a 4-night stay (§6). Since Airbnb's total-price default (April 2025) and the FTC's short-term-lodging fee rule, guests compare these all-in totals. So price sensitivity depends on the length of stay. Under the candidate config the fees roughly cover per-stay costs (owner fee margin ≈ $28 per stay), so selling a short stay costs the owner little. Whether a 1-night stay for a 16-sleeper sells at all is a demand question, not a cost question.
5. **What hotel RMS cannot give us:** network-scale forecasting (Weatherford & Kimes; SAS describes 584,000 forecasts nightly), overbooking (one unit), open pricing by segment (we have one public price), and ML forecasting (100 reservations). The closest published vacation-rental case (Wyndham Destinations, a choice-based logit with a booking-curve heuristic) reported +3.5% and +5.2% revenue per unit in two regions (company-measured; §9). Published hotel lifts are 2–4% (Carlson Rezidor, compliant versus non-compliant hotels) and 2.7% (IHG retail segment). Vendors report their own 15–20% lifts with no controls. Our field tests detect only effects larger than about 33%, so **no hotel-sized gain will ever be visible in our own A/B results**. Measurement must lean on the simulator and on variance reduction.

---

## 1. Foundations: how hotel RM came to be and what it controls

### 1.1 History (Marriott, Holiday Inn, Hilton, IHG)

- **Origins.** Yield management migrated from airlines after US deregulation in 1978. In February 1988 Eric Orkin's Cornell Quarterly article proposed a yield statistic (revenue realized divided by revenue potential). In January 1988 Smith Travel Research published the first STAR competitive benchmark report, at Holiday Inn's request. The New York Times reported hotel "yield management" on 1988-09-03. AMR planned a system for Hilton, Marriott and Budget by 1991 (Stuart-Hill 2021, HNN/ISHC, [read in full], https://ishc.com/wp-content/uploads/The-Origin-of-Revenue-Management-in-The-Hospitality.pdf).
- **Marriott.** By INFORMS' own account the story is folklore: after a lunch with Robert Crandall, Bill Marriott asked Richard Hanks's team to implement RM. Hanks and Aeronomics consultants discovered the **length-of-stay problem** at Munich's Oktoberfest. Selling peak nights to high-rate short stays displaced lower-rate guests who would have stayed all week, so optimizing each night alone lost money. Marriott first used ad hoc rules, then reframed the problem as **network RM** (INFORMS, History of O.R. Excellence: Revenue Management, https://www.informs.org/Explore/History-of-O.R.-Excellence/O.R.-Methodologies/Revenue-Management; the page cites Hanks, Cross & Noland 1992, *Cornell HRA Quarterly*, and Cross 1997, pp. 139–142). The page also records that **hotels were the first to use bid-price control with a deterministic linear program**: Holiday Inn in 1992 and Club Med in 1993, both with SABRE. Secondary sources (Wikipedia and a Revenue Analytics blog) say Marriott's Demand Forecasting System (DFS) was built with Aeronomics to forecast and control availability by rate and length of stay. The INFORMS page does not say this, so it is UNVERIFIED. Secondary sources credit Marriott RM with **$150–200M per year by the mid-1990s**. The figure traces to Cross (1997), was not verified in the primary text this session, and is UNVERIFIED and STALE.
- **Marriott One Yield (2003).** Marriott built One Yield in-house and began rolling it out in April 2003. It merged the earlier DFS forecasting system and the separate revenue management system, and it covered more than 1,700 of about 2,600 properties. It shows past bookings and current reservations for a stay date and recommends rates. Revenue managers can accept or override a recommendation before rates go to central reservations. A postmortem module replays decisions up to 28 days back against the revenue that would have been optimal. Marriott credits One Yield with up to a 2% leisure revenue increase at installed hotels in 2004, worth $86M in annual profit across individual hotels, and with raising its "inventory effectiveness" ratio (actual revenue divided by optimal revenue) from 83% to 91% (CIO, 2007-06-13, https://www.cio.com/article/274973/budget-the-price-is-always-right.html, accessed 2026-10-17). These are Marriott's own figures and are STALE. Marriott won CIO's Grand Enterprise Value Award for the system in 2005 (https://www.hospitalitynet.org/news/4022124). The "MORE" successor named in the R2 prompt was **not found** in any source this session (UNVERIFIED). The **inventory-effectiveness ratio** is a metric worth copying: it is our ex-post regret.
- **Marriott group pricing.** "Marriott International Increases Revenue by Implementing a Group Pricing Optimizer," *Interfaces* (DOI 10.1287/inte.1090.0482). The abstract describes demand segmentation, **price-elasticity modelling** and optimization to recommend group rates, in operation since late 2006. The full text is paywalled (403). Dollar figures were not verified.
- **IHG.** Koushik, Higbie & Eister (2012), "Retail Price Optimization at InterContinental Hotels Group," *Interfaces* 42(1):45–57. The PERFORM price-optimization module sets rates from **occupancy, price elasticity and competitor prices**. It drops the classical assumption that demand in each rate segment is independent of price. Reported results: **$145M incremental to date, about $400M per year projected** at full rollout (https://ideas.repec.org/a/inm/orinte/v42y2012i1p45-57.html, STALE). The INFORMS Edelman finalist abstract cites a **2.7% revenue increase** "verified and acknowledged in the IHG 2009 annual review" and deployment at 2,077 hotels (https://www.informs.org/Resource-Center/Video-Library/Edelman-Competition-Videos/2011-Edelman-Competition-Videos/2011-Edelman-Finalist-InterContinental-Hotels, via search snippet, accessed 2026-10-17; the page returned 404 on direct fetch). IHG and its consultant (Revenue Analytics) reported these figures, which is a conflict of interest.
- **Carlson Rezidor.** In the SNAP project with JDA, Carlson Rezidor measured a **2–4% revenue improvement in compliant versus non-compliant hotels**, worth more than $16M per year (*Interfaces*, DOI 10.1287/inte.1120.0660; abstract via search; full text paywalled; STALE). Comparing compliant with non-compliant hotels is a self-selected comparison: hotels that comply may differ in other ways.
- **Hilton.** Since 1997 Hilton has used IDeaS. In 2013 it extended IDeaS G3 to more than 2,700 focused-service hotels under its Global Revenue Optimization (GRO) initiative (IDeaS press release, https://ideas.com/de/news/hilton-worldwide-partners-with-ideas-on-global-revenue-initiative/, VENDOR, STALE).

### 1.2 The controls hotels use (definitions)

- **MinLOS / MLOS:** the minimum number of nights a stay starting on a given date must last. **CTA (closed to arrival):** no check-ins on that date, though stays may run through it. **CTD (closed to departure):** no check-outs on that date. A MinLOS alone does not stop a 1-night arrival in the middle of a peak, so practitioners pair MinLOS with CTA (Mews MLOS guide, https://www.mews.com/en/blog/hotel-minimum-length-of-stay; Infor HMS booking restrictions, https://docs.infor.com/hms/2026.x/en-us/hmsolh/s_t1424428597259.html; VENDOR documentation).
- **The network effect, in SAS/IDeaS's own example:** with one room left on Saturday, selling a 1-night Saturday stay at $250 can block a Friday–Saturday 2-night stay at $150 per night. Two nights at $150 earn more than one night at $250 when Friday would otherwise go empty. Their larger worked example has 1,120 room-nights of unconstrained demand reduced to an optimal mix of 720 (Dietz & McGuire, SAS Global Forum 2010 paper 346-2010, [read in full], https://support.sas.com/resources/papers/proceedings10/346-2010.pdf, STALE but canonical).
- **Displacement analysis for groups.** Net group value = room revenue + ancillary revenue − variable costs. Displaced rooms = expected transient rooms + group rooms − capacity. Accept the group only if group value exceeds the displaced transient contribution (Hospitality Net explainer, https://www.hospitalitynet.org/explainer/4134223/how-to-conduct-an-effective-hotel-displacement-analysis; SAS 2010 describes IDeaS V5i's group displacement module).
- **Overbooking.** IDeaS V5i sets overbooking levels as a **newsvendor problem**: the cost of an empty room against the cost of walking a guest, subject to a walk-risk tolerance. The overbooked capacity is then fed into the optimizer (SAS 2010, [read in full]).

### 1.3 The bid-price mechanism, implementable form

Hotel network RM (Talluri & van Ryzin, *The Theory and Practice of Revenue Management*, Springer 2004, chapters 3 and 10; the canonical textbook, cited from the standard formulation and not re-read this session) works as follows:

- **Products** j are (arrival date, length of stay, rate). Each uses resources i (nights) through a_ij ∈ {0,1}.
- **Deterministic LP:** max Σ_j r_j x_j subject to Σ_j a_ij x_j ≤ C_i for every night i, and 0 ≤ x_j ≤ D_j (the forecast demand).
- **Bid price** π_i is the dual on night i. **Decision rule:** accept a request for product j if and only if r_j ≥ Σ_{i ∈ j} π_i. In words, a stay must pay at least the summed opportunity cost of the nights it occupies.
- **Dynamic version** (Talluri's patent US6263315B1, Pricing Research Corp., filed 1998, expired; https://patents.google.com/patent/US6263315): the thresholds live in multidimensional lookup tables indexed by time-to-go and remaining capacity. A request is accepted if its net revenue is at least the sum of the current thresholds for the resources it uses. The patent argues this is more robust to forecast error than a static bid price.
- **Multi-night stays as a stochastic dynamic program:** Bitran & Mondschein (1995), *Operations Research* 43(3):427–443, solved the multi-night case with heuristics and upper bounds tested on a medium-size hotel (https://ideas.repec.org/a/inm/oropre/v43y1995i3p427-443.html, STALE, foundational).
- **One room type, multi-night requests, dynamic pricing:** Nadarajah, Lim & Ding (2015, SMU working paper, https://ink.library.smu.edu.sg/lkcsb_research/5147; abstract via search, accessed 2026-10-17, STALE) model the choice of a per-day booking price for one room type when customers request multi-day stays, as a Markov decision process. The exact policy is intractable, so they use fluid-approximation and approximate-linear-programming heuristics. Their best heuristic earns **up to 7% more than single-day decomposition** and up to 6% more than a fixed-price heuristic. The paper is the closest formal model of our problem: one unit, multi-night stays, posted prices. It is the formal basis for recommendation #3. An earlier Tsinghua seminar abstract by Ding describes the resulting structure: **raise rates on high-demand days and lower them on neighbouring low-demand days**. That is the shoulder-night logic.

**Single-unit translation for a whole home.** C_i = 1 for every night, and a sale is a contiguous block. Night i's bid price is the expected value of keeping it open:

π_i(t) ≈ P(night i is sold later | open at lead t) × E[owner-net per night of the stay that would take it]

For a candidate stay s covering nights {i…i+L−1} at nightly price p, the value of accepting is NetValue(s) = Σ owner-net(s) − Σ_{i ∈ s} π_i(t) − OrphanPenalty(s). The orphan penalty is the expected loss on the 1–2 night holes the stay leaves next to existing bookings:

OrphanPenalty = Σ_holes P(hole unsold) × π_hole

The engine's M3 continuation value C = q × (floor + ceiling) / 2 (MODEL_SPEC.md) is a one-night, myopic version of π_i. M4 is a crude version of the stay-level comparison.

---

## 2. Forecasting

### 2.1 Unconstrained demand by arrival × LOS × segment

The RM cycle is: collect data → **unconstrain** → forecast → optimize → update (SAS 2010, [read in full]). Sales on sold-out nights understate demand, so unconstraining estimates the demand that would have appeared with unlimited capacity. A full-service RMS forecasts LOS 1 through 8+ for 10+ room types and 20+ segments, 365 days out: **over 584,000 forecasts nightly**. Sparse cells (one or two rooms occasionally) use aggregation and disaggregation (SAS 2010). IDeaS says G3 runs **"over 100 models tuned to different types of hotel business,"** uses DP-based optimization, and puts competitor pricing inside the optimization rather than as a post-hoc rule. Validation is by pilots in statistically matched properties, with no published lift figures (https://ideas.com/science-behind-g3-rms/, VENDOR).

**Regrets and denials** are the hotel's direct measure of turned-away demand. Duetto exposes them during restriction periods, broken down by LOS, price point, rate code, room type and country. A hotel's adoption announcement says Duetto uses this shopping data to measure **price sensitivity** and **unconstrain** demand (https://www.duettocloud.com/en-us/library/beyond-bar-the-power-of-open-pricing, VENDOR). For us the analogues are Airbnb/VRBO inquiries, quote requests that don't book, and listing views. Our own direct-site quote log is the cleanest version.

**Unconstraining algorithms.** Weatherford & Pölt (2002, *JRPM* 1(3), DOI 10.1057/palgrave.rpm.5170027; abstract via search, accessed 2026-10-17, STALE) compared six methods on simulated data. **Expectation-maximization (EM) and projection detruncation were the most robust** when 60–80% of observations were constrained. On airline data, better unconstraining was worth 2–12% revenue. A Georgia Tech working paper (Ferguson, Crystal, Higbie & Kapoor) finds EM and its own method best on hotel and casino data (https://repository.gatech.edu/entities/publication/9fcfec43-a0f3-4996-ab40-1fd0a93a4e3a, abstract). The EM version for a censored demand count Y with capacity cap c:
- **E-step:** for each constrained observation (Y ≥ c), replace Y with E[Y | Y ≥ c; μ, σ] under the current normal (or Poisson) fit.
- **M-step:** refit μ and σ on the completed data.
- Iterate to convergence.

**What is censored in our data:** (1) a booked night says nothing about how many other parties wanted it; (2) a night blocked by a min-stay rule, or left as an orphan, was not offered to 1–2-night demand; (3) owner blocks remove nights from sale. For a single unit, unconstraining reduces to estimating **P(book | offered at price p, lead h)** using only the time the night was actually open and saleable. Censoring at the moment of booking is handled like survival analysis: each open day contributes to the hazard and the booking day ends exposure. `pacing_snapshots` already supports this.

### 2.2 Pickup models (the method that wins on small data)

- **Weatherford & Kimes (2003),** *International Journal of Forecasting* 19(3):401–415, on Choice and Marriott data: pickup methods and regression had the lowest error. **Exponential smoothing, pickup and moving average were the most robust.** Booking-curve and combination forecasts were "fairly inaccurate" (https://ecommons.cornell.edu/bitstream/handle/1813/72130/Kimes30_Comparison_of_Forecasting.pdf, STALE, foundational).
- **Additive pickup:** F(d | lead h) = OTB(d, h) + mean over comparable past dates of [final − OTB at h]. **Multiplicative (booking-curve) pickup:** F = OTB(d, h) / mean[OTB at h / final]. Webb, Schwartz, Xiang & Altin (2022, *J. Hospitality & Tourism Insights* 5(5):950–965) studied 1,826 booking curves from a 109-room national-park hotel. The multiplicative method is **most vulnerable because its forecast is zero when nothing is on the books**, and forecast error rises sharply once the booking window falls below about 60 days (https://www.emerald.com/insight/content/doi/10.1108/JHTI-05-2021-0124/full/html; the Emerald HTML returned the data section and Table 1 to this agent on 2026-10-16, but the reviewer saw only the abstract, so the article is probably paywalled for most readers and the details beyond the abstract should be treated as single-read). **Our `pace_reading` is a multiplicative index:** (on_books + 0.05) / (expected + 0.05). The 0.05 smoothing is a patch over exactly this failure.
- **Small-hotel extension.** Heo, Viverit & Pereira (2023), *JRPM* (DOI 10.1057/s41272-023-00421-1), studied a **32-room seasonal hotel**. They averaged incremental pickup over k neighbouring check-in days, then pooled it with N prior years at equal weight 1/(N+1):
  - ā_d(j) = (1/(N+1)) [ā_{0,d}(j) + Σ_n ā_{n,t}(j)]
  - ŷ_d(h) = b_{0,t,h} + Σ_{l<h} ā_d(l)
  - Result: 28-day-ahead MAPE fell from **23.9% (classic) to 4.6%**, and 14-day MAPE from 11.9% to 3.1% (https://pmc.ncbi.nlm.nih.gov/articles/PMC10007649/, [read via PMC]). It borrows strength across neighbouring dates and prior years, which is what our three homes must do. **Caveat:** the test window was 1 July–15 September 2020, during COVID. The authors say booking patterns "changed significantly", which broke the classic method's prior-year pickup. It is one hotel and about 77 check-in dates. So this is a regime-shift test, not a steady-state one. The idea transfers; the size of the gain does not, and it must be backtested on our own `pacing_snapshots`.
- **Market-level ML forecasting.** Das, Chadha & Banerjee (2021), *JRPM* 20(3):351–367, forecast market occupancy for 97 NYC hotels from Amadeus Business Intelligence on-the-books data. LightGBM had a 365-day MAPE of 3.66% against SARIMAX's 5.20%; most models under-forecast event days (https://pmc.ncbi.nlm.nih.gov/articles/PMC8007660/). This shows **market-level series are forecastable**. Our property level is not.
- **Competitive-set occupancy as an input.** Weatherford, Uysal, Webb & Altin found that adding the comp set's predicted occupancy to a property's own forecast improves accuracy (ResearchGate record "Hotel daily occupancy forecasting with competitive sets: a recursive algorithm"; abstract only, magnitudes not verified, UNVERIFIED). Lighthouse claims forward-looking demand data improves forecast accuracy by **up to 20% within 30 days**, with +2.3% RevPAR (https://www.mylighthouse.com/resources/insights/predictive-market-intelligence-hotel-demand-forecast, VENDOR, UNVERIFIED).
- **What forecast accuracy is worth.** A 20% reduction in forecast error is said to yield about a 1% revenue gain. Webb et al. (2022) cite this from Pölt (1998); it is STALE and was not re-derived.

### 2.3 Forecasting with very small inventory: the hotel answer and ours

Hotels with 30–50 rooms still have about 30–50 times our nightly sample. Our `on_books_share` counts portfolio home-nights within ±3 days, excluding blocked nights, so n ≤ 3 × 7 = 21. **Those nights are not independent.** They are filled in stays of typical length 4, so the effective sample is about 21/4 ≈ 5 stays. With the reference curve's expected share e(h) = 0.70 × curve(h) at peak, a binomial standard error on the effective sample, and the engine's index (obs + 0.05)/(e + 0.05) with sensitivity 0.30:

| Lead h | Expected share e | SE of observed share (n_eff ≈ 5.25) | SE of the pace index | Price swing from noise alone (0.30 × SE) |
|---|---|---|---|---|
| 120 days | 0.084 | 0.12 | ≈ 0.90 | ±27% (hits the 0.85/1.25 clamps) |
| 60 days | 0.245 | 0.19 | ≈ 0.64 | ±19% |
| 30 days | 0.385 | 0.21 | ≈ 0.49 | ±15% |
| 14 days | 0.504 | 0.22 | ≈ 0.39 | ±12% |

**The market alternative, with honest numbers.** Recommendation #1 plans 20–40 curated comps. Over a 7-night window that is 140–280 listing-nights, or 35–70 effective stays after the same clustering. At 30 days (e ≈ 0.385) the SE is about 0.058–0.082. That is **2.6–3.7× more precise** than own pace, not 10×. At today's ~33% valid-row rate, 30 comps yield about 10 valid comps, and the gain falls to about 1.8×. Common demand shocks correlate across comps, but that correlation is the signal being measured, not noise. Only a full-market series (hundreds of listings: a PriceLabs dashboard or DestiMetrics) reaches about 10×, and those mix in smaller units. Widening the window to ±7 days helps both own and market series about equally.

Three remedies come from the hotel literature, in order of cost:
1. **Pool across dates and years** (Heo et al.).
2. **Pool across the market**: use a market or comp-set on-the-books series as the pace numerator (Demand360 / DestiMetrics logic).
3. **Shrink the property's deviation toward the market**, so the home's own pace enters only as a residual: pace_home = pace_market × (own/expected)^w, with w = n/(n + κ).
4. **Lower the sensitivity at long leads** (or switch to additive pickup there). The table shows noise alone saturates the clamps at 120 days.

---

## 3. Price optimization

### 3.1 Elasticity estimation in hotels: the endogeneity trap

**Garcia, Tolvanen & Wagner (2022),** *Management Science* 68(11):7918–7939 (CESifo WP 9127, **[read in full]**, https://www.ifo.de/DocDL/cesifo1_wp9127.pdf).

- **Data:** 9 European hotels (8 resort, 1 urban), about 50 rooms each, 14 months, about 60,000 bookings and more than 5M price observations. Prices came from an RMS whose fee is benchmarked against revenue gains.
- **Problem:** managers raise prices when demand is high, so price and bookings correlate positively. **OLS and double-selection models without the recommended rate gave positive or near-zero price coefficients.** Hausman-style instruments (other hotels' prices) also failed, because weather and demand shocks are correlated across markets.
- **Identification:** managers follow the recommendation **with a delay**. Passing a recommendation change through to the actual rate within 10 days averaged only 0.10, and "accept all for a whole week" events made up 52.2% of updates. Conditional on the recommendation (a sufficient statistic for the RMS's demand information), the remaining price variation is inattention, which is exogenous.
- **Estimator:**
  - Q_hit = λ_ht + p_hit η + X'β + f(r_hit, X) + ε
  - Q is a booking indicator, p the actual rate, r the recommended rate, and f a flexible polynomial in r with seasonal interactions selected by post-double-selection LASSO (Belloni, Chernozhukov & Hansen 2014).
- **Results:**
  - Median hotel: **+€3 per night → −1% bookings**. The semi-elasticity ψ = (1/q)(dq/dp) ≈ −0.0038 per euro, i.e. **−0.38% of booking probability per euro**. The implied markup is about 55% of price.
  - **Resort hotel 175, by arrival season (Table 13, in the paper's "p.p." semi-elasticity units): winter −0.49 (SE 0.29, not significant); summer −2.42; off-season −4.22.** These are per-euro semi-elasticities on rooms priced at about €80–210. They are not comparable in level to the engine's β, which is an elasticity on an all-in price near $2,000. Only the **pattern** transfers: winter demand at this resort hotel was much less price-sensitive than off-season demand. No ratio is meaningful, because the winter estimate is not significant.
  - Price sensitivity is **highest for early bookers (>100 days)** and lowest at 21–50 days (Table 10).
  - **For the biggest hotel in the sample only**, about one third of consumers are willing to delay purchase for a better price.
  - On 73.8% of booking days a hotel changed none of its prices (Figure 5 annotation).
  - A difference-in-differences estimate on accept-all events (semi-elasticity −1.20) agrees with the control-function estimate.
- **Engine implication: what transfers and what does not.**
  - **Scale.** Garcia et al. had about 60,000 bookings and more than 5M price observations, and estimation took more than 8,000 CPU hours. We have about 100 reservations.
  - **Source of variation.** Their identifying variation is managers' *inattentive, exogenous* delay in copying recommendations. In our engine, move caps (±12% / $250), deference to the listed price and floor/ceiling clamps are **deterministic functions of the recommendation and the prior state**. Conditional on those, they create no residual variation. What remains is (a) **M1's Thompson draws**, which are deliberate randomization and so a cleaner instrument than inattention; (b) operator approval lag, *if* it is unrelated to demand; and (c) manual overrides, which are probably endogenous because the operator acts on information, and should be excluded.
  - **Current bias.** M1 (book rate above versus below the median as-of price) is the naive design the paper shows is biased toward zero or positive. M1 clips β to [−2.5, −0.3] (MODEL_SPEC), so the bias appears as **pinning at −0.3**, which pushes toward the ceiling, the engine's known failure mode. The candidate config already uses a −1.00 all-in peak prior (`pace_learned_owner_net.yaml`). The default −0.65 is not the current candidate.
  - **Power.** For a rare-event booking model, SE(β) ≈ 1 / (√N_bookings × sd(log p | recommendation)). Take about 50 bookings per season and exploration that moves the log price about 5% around the recommendation: SE ≈ 1/(7.1 × 0.05) ≈ **2.8**, which says nothing. With 10% exploration pooled over three seasons (about 150 bookings): SE ≈ 0.8, which is marginal. Comps' revealed transitions (§5.2) could add observations, but only for the market's elasticity, not ours.
  - **Conclusion.** Log (recommended, listed, exploration draw, booked) per home-night now. Estimate β with the recommendation as a control only after the simulator, with a known true β, shows the SE is small enough to beat the prior. Until then, β stays a shrunk prior.

Supporting evidence:
- At the most aggregated level, US hotel demand elasticity was estimated at **−0.19 (2012)** and is more elastic in the long run (Corgel et al., Cornell, https://ecommons.cornell.edu/bitstream/1813/72477/1/Corgel107_Hotel_industry.pdf; snippet; STALE).
- A 26-month city-hotel study finds **late bookers more elastic** than early ones (ScienceDirect S0261517725002523; abstract only). This contradicts Garcia et al. on direction, so elasticity versus lead time is **property-specific**, not a law.

### 3.2 Optimal BAR, price ladders and continuous prices

Historically hotels pre-set rate plans and the optimizer chose which to open. In SAS's words, hotel RMS "have not been required to measure price sensitivity" and instead allocate inventory across fixed prices (SAS 2010, [read in full]).

- **Price ladder (BAR levels):** pick a level from a discrete table. The Amadeus market-pricing patent describes rules that move BAR "by one or two levels" on market signals (US20130006712A1, Amadeus S.A.S., filed 2011, abandoned, https://patents.google.com/patent/US20130006712). Its claim 1 selects comparable competitors by classified criteria, queries their prices, averages them, and adjusts the provider's expected offer price "according to the estimated average price" through predetermined "market influencer" parameters. **This is almost exactly our comp-anchor median plus pace multiplier.**
- **Continuous price optimization:** IHG PERFORM and Carlson SNAP choose the price from estimated demand as a function of own price **relative to competitor price**, plus remaining capacity and forecast (IHG abstract; Carlson abstract). A first implementable version:
  - P(book | p, h) = P0(h, season) × (p / p_comp)^ε
  - Choose p to maximize P × owner_net(p) + (1 − P) × C(h)
  - Here p_comp is the comp anchor and C(h) the continuation value (§1.3).
- **IDeaS G3 product:** the primary priced product defaults to "BAR". The system picks a price within a user floor and ceiling and offers a LOS option: "a blended rate based on arrival date and stay duration" (IDeaS help, https://help.ideas.com/g3rms_cp/Content/Pricing/Pricing-Configuration-Overview.htm; G3 pricing datasheet; VENDOR).

### 3.3 Open pricing, rate parity and channel net

- **Duetto "Open Pricing":** price every segment, channel and room type independently instead of moving all of them off one BAR. LOS and closed-to-stay restrictions still apply (Duetto glossary and "Beyond BAR", VENDOR). Duetto's patents cover alerts and a profit module using matching weekdays of earlier weeks. Patent numbers were not verified (trade press via search, UNVERIFIED).
- **Rate parity:** OTA contracts required the hotel's lowest rate on the OTA too, even though the OTA channel costs more (SAS 2010). After Booking.com dropped its narrow best-price clause in some EU countries, **hotels' direct channels more often had the strictly lowest price**, and OTA commissions did not change (Hunold, Kesler, Laitenberger & Schlütter 2018, *Int. J. Industrial Organization* 61:542–571; ZEW DP 16-066, https://www.zew.de/fileadmin/FTP/dp/dp16066.pdf).
- **For us:** three channels exist (Airbnb, VRBO, direct). Whether Airbnb's terms prevent a cheaper direct rate is a policy question for the operator (§10). The economics are clear: with an Airbnb host-only fee of about 15.5% against an assumed 3% card processing on direct (not sourced), the owner keeps about 21% more per nightly dollar on direct, so a direct booking at a price 10% lower still nets the owner more (§6.2).

### 3.4 Small-hotel pricers (the closest hotel analogue to STR pricers)

RoomPriceGenie (help center, [read]; https://help.roompricegenie.com/en/knowledge/occupancy-strategy):

- **Price components.** The help-center pages on base price and monthly adjustments (https://help.roompricegenie.com/knowledge/set-base-price ; https://help.roompricegenie.com/en/knowledge/carrying-out-monthly-adjustments; seen as search snippets only) describe the price as built from a base price, a market factor (what comparable local properties would charge) and an occupancy/pickup factor. The occupancy-strategy page does not state this, and how the factors combine (additive or multiplicative) is not documented.
- **Expected occupancy:** the target is built so that **half of the target is booked by the median booking window**. Example: an 80% target with a 14-day median means 40% expected at 14 days. The default target is 80%. Ski and destination hotels select the "Long" window (more than 30 days), drawn from Booking.com market lead-time data.
- **Aggressiveness** sets how strongly price responds to the occupancy gap. Low or Very Low is recommended for very small hotels. High variable costs make the algorithm cut prices more cautiously.
- **Shoulder-night discounts:** nights adjacent to sold-out nights get an automatic discount (one side = base %, both sides = 2×). The page says this was live on only about 10% of properties when written.
- This is, almost line for line, the engine's pace pricing (`DEFAULT_CURVE`, `pace_multiplier`) and orphan discount. **Generic small-property pricers and our engine share the same skeleton.** Specialization has to come from better inputs (market OTB, comp availability, snow, events) and from owner-net economics, not from the pace formula.

Other vendors:
- **Atomize (Mews):** live and historical PMS bookings, competitor pricing, local events; autopilot or copilot; vendor-claimed 15–20% uplift after 12 months (VENDOR, uncontrolled). A third-party review warns that optimization is constrained in markets with limited competitor-rate transparency (Mews community and fitgap listings).
- **Pace Revenue → FLYR for Hospitality (2022):** price per room, night and lead time, updated hourly, with claimed price-sensitivity evaluation; more than 1,000 hotels (https://www.hospitalitynet.org/news/4112519.html, VENDOR). Duetto acquired FLYR Hospitality, announced 2026-10-08, after acquiring the profitability-benchmarking firm **HotStats in 2025** (Hospitality Net, https://www.hospitalitynet.org/news/4134812.html, accessed 2026-10-17; now verified). HotStats is the clearest industry move from revenue toward profit (GOPPAR) benchmarking (§6.1).

### 3.5 What Airbnb itself learned (a platform-scale counterpoint)

Airbnb's own "Smart Pricing" description (Ye et al., KDD 2018, via the Morning Paper summary, https://blog.acolyer.org/2018//03/customized-regression-model-for-airbnb-dynamic-pricing/):

- A GBM booking-probability model per listing-night proved **too inaccurate to support direct revenue maximization**, and A/B tests of that approach failed.
- Airbnb instead learns a price-adjustment curve V(q, demand) around the host's price. Training uses a bound loss: a booked night's price is the lower bound, an unbooked night's price the upper bound.
- Evaluation uses **price-decrease recall** and **booking regret**.

An independent study found adopters of Smart Pricing saw nightly rates **fall 5.7% and daily revenue rise 8.6%**, through occupancy (Zhang, Mehta, Singh & Srinivasan 2021, "Frontiers: Can an AI Algorithm Mitigate Racial Economic Inequality? An Analysis in the Context of Airbnb," *Marketing Science* 40(5):813–820, https://pubsonline.informs.org/doi/10.1287/mksc.2021.1295. The paper page returned 403 to this agent; the −5.7% and +8.6% figures were seen in search summaries of the abstract, and the CMU news page does not contain them). That is the **opposite** of what a luxury peak home needs. Generic algorithms tuned on the mass market lift revenue by lowering price, which supports hypothesis H2.

---

## 4. Vendor systems: the exact data inputs

| System | Data inputs (as documented) | What it outputs | Evidence of impact (who measured it) | Cost and access | What we can take |
|---|---|---|---|---|---|
| **IDeaS G3 RMS (SAS)** | PMS bookings and cancellations by segment, room type and LOS; competitor rates **inside** the optimizer; special events; days to arrival; upgrades; group data (ideas.com/science-behind-g3-rms) | BAR within a floor and ceiling, LOS-blended rates, restrictions, overbooking, group evaluation | None published; "pilots in statistically matched properties" (VENDOR) | Enterprise, per property | DP-based price-and-LOS optimization; competitor price as a model input, not a rule. Our matched-pilot idea is the twin homes. |
| **Duetto GameChanger / Open Pricing** | Web shopping (regrets and denials), bookings and pace, comp rates (via HQ plus, 365 days forward), channel cost, reviews (Duetto library; hotel-online HQ plus release) | Independent prices per segment, channel and room type; LOS restrictions | None independent (VENDOR) | Enterprise | Treat turned-away demand as data. Price channels on net, not parity. |
| **Atomize (Mews)** | Mews PMS live and historical bookings, competitor pricing, local events and holidays | Continuous rate updates; autopilot or copilot | 15–20% uplift claimed (VENDOR) | SaaS, quote | Same skeleton as ours. |
| **FLYR Hospitality (ex-Pace)** | Own bookings, pace, LOS, segment mix (third-party description); hourly repricing (hospitalitynet 2022) | Price per room, night and lead time | None (VENDOR) | SaaS | Lead-time-specific pricing. |
| **RoomPriceGenie** | PMS occupancy and pickup, market factor from comparable properties, Booking.com lead-time medians, user target occupancy (help center) | Price from base price, market factor and occupancy factor (combination not documented); shoulder-night discounts (about 10% rollout) | 15–22% claimed (VENDOR) | SaaS for 5–60 rooms | Explicit target-curve math (half the target by the median lead); aggressiveness damping for small inventory. |
| **Lighthouse (ex-OTA Insight)** | **Live** OTA and brand.com shops incl. **short-term rentals**; dynamic comp set from location, reviews and pricing patterns; anomaly filtering; forward demand from search, flight, GDS and event data (Lighthouse blog) | Rate grids by LOS, guest count, refundable vs lowest; parity; market demand index | +2.3% RevPAR, up to 20% forecast gain (VENDOR, UNVERIFIED) | SaaS per property, quote | **Rate-shopping discipline** (§5.3). Also a **candidate STR forward source**: OTA Insight bought the vacation-rental data firm Transparent in March 2022 (35M+ listings from Airbnb, Vrbo, Booking.com and partners; https://www.hospitalitynet.org/news/4109377, accessed 2026-10-17), and Market Insight is marketed as forward-looking demand monitoring. Winter Park large-home coverage and price are unknown; ask for a demo of the 5+ BR slice. |
| **Amadeus Agency360 / Agency360+** | Travel-agent bookings from the three major GDSs, plus corporate account production (Hotel Tech Report on the Agency360+ launch, https://hoteltechreport.com/news/amadeus-agency360-launch, via search, accessed 2026-10-17) | Agency and corporate share by hotel and comp set | n/a | Contract | **Not relevant**: whole-home ski rentals are rarely booked through GDS travel agents (our inference, not sourced). |
| **Amadeus Demand360** | Confirmed reservations from >44,000 data providers (chains, independents, OTA, GDS, brand.com); air bookings by O&D from 3 GDSs (overview sheet) | 12 months forward OTB occupancy and ADR for the property, comp set and market; updated 5 days a week | Amadeus case articles only (VENDOR) | Requires contributing data and a contract | The **logic** of forward market OTB. The overview sheet also says Demand360 tracks "forward-looking availability of alternative accommodation listings week-over-week" ([read in full]). A reseller listing claims 35M STR properties (ExploreTech, UNVERIFIED). So STR coverage exists in some form, but as **availability**, not bookings, and relative to a hotel's own occupancy. Reasons not to buy for three homes: the product is built around a contributing hotel's comp set; contribution and contract terms are unknown; cost is unpublished; Winter Park depth is unknown. Ask Amadeus only if a free trial shows Winter Park 5+ BR availability series. |
| **CoStar/STR Forward STAR** | Hotel-submitted daily rooms booked and adjusted rooms available, 90 days (weekly) or 365 days (monthly) | OTB and pickup for hotel, submarket and comp set | n/a | Requires contributing data (costar.com guidelines) | Definitions: what counts as "booked", including excluding owner-occupied nights. |
| **Inntopia DestiMetrics** | Monthly occupancy and rate submissions from **participating property managers** in resort destinations; economic indicators; weather and snowfall in Destination Explorer | Destination OTB six months forward; monthly market briefings; property reports | n/a | Participation prerequisite; report packs $250–$2,000 | **The mountain-specific forward OTB** (§5.1). |
| **Key Data (keydata.co)** | Reservations "aggregated directly from professional property manager's reservation systems" plus VRBO and Airbnb data | ADR, occupancy, unit revenue, 40+ KPIs, pacing charts | n/a | Custom quote ("$200+/month for 50+ properties", third-party review, UNVERIFIED) | PMS-direct STR comp data in Winter Park. |
| **PriceLabs Market Dashboard** | Market listing calendars and prices (methodology not documented on its help page) | Future occupancy, pickup, cancellations, last-year lines; bedroom filter; daily refresh | n/a | **From $9.99 per dashboard per month** (help page); the marketing page says pricing "starts at" $9.99, so it may be tiered by report size | The cheapest daily forward market OTB proxy. A filter to "your desired bedroom count" is documented; whether 5+ BR is a separate bucket is UNVERIFIED. |
| **AirDNA** | Scraped Airbnb and Vrbo calendars and listings (third-party critique: blocked nights treated as booked, UNVERIFIED) | Pacing 6 months forward (help page) | A search snippet attributed to AirDNA's forecast page says advance bookings are "not very informative" at 4+ months (page returned 403; UNVERIFIED) | Subscription | Long-horizon pacing is weak, so use short-horizon pacing. |

Patents found (all read on Google Patents):
- **US6263315B1** (Talluri, 1998): dynamic bid-price tables. A request is accepted if its net revenue is at least the sum of the thresholds for the resources it uses.
- **US20130006712A1** (Amadeus, 2011, abandoned): adjust the offer price from comparable competitors' average price using market-influencer weights.
- **US6993494B1** (Harrah's/Caesars, 2000, expired): lower the bid price by the customer's **indirect value** (gaming), then adjust for competitor rates. This is the formal ancestor of "total revenue" hurdle rates.

No IDeaS-assigned patent was confirmed in this session (UNVERIFIED that none exists).

---

## 5. Forward-looking market data: DestiMetrics, Demand360 and STR equivalents

### 5.1 Inntopia DestiMetrics: what is verified

| Question | Finding | Source and status |
|---|---|---|
| What is it? | Denver firm founded 2004 and acquired by Inntopia. Its Reservation Activity Outlook (RAO) collects monthly occupancy and rate data from participating property managers, then anonymizes and aggregates it into destination forward views of six months historic plus six months **on the books**. | DestiMetrics MDC sheet (c. 2016, [read in full], STALE) https://destimetrics.com/wp-content/uploads/2016/03/MDC_1.1_with_links.pdf ; Inntopia product page https://corp.inntopia.com/intelligence/destimetrics/ |
| Does it cover Winter Park? | **The 2016 MTNWEST list includes "Winter Park"** alongside Aspen, Avon, Beaver Creek, Big Sky, Breckenridge, Copper, Gunnison/Crested Butte, Keystone, Mt Bachelor, Jackson Hole, North Lake Tahoe, Park City Area, Snowmass, Steamboat, Summit County, Telluride and Vail. **Winter Park Central Reservations** was one of 26 charter members of CRADR, whose $900-per-year members receive "Monthly Reservation Activity Program Reports"; DestiMetrics and Inntopia were associate members. **Current (2026) participation is UNVERIFIED.** Today's briefings name only "17 mountain destinations across seven western states" (SGB), reported in two subsets, Colorado+Utah and the rest of the West (Park Record). | MDC sheet (STALE); CRADR deck (2016, [read in full], STALE) http://corp.inntopia.com/wp-content/uploads/2016/05/Presentation-CRADR.pdf ; SGB July 2026 https://sgbonline.com/destimetrics-market-briefing-july-2026/ ; Park Record 2026-04-21 https://www.parkrecord.com/2026/04/21/after-a-warm-winter-western-resorts-are-hoping-for-a-better-summer/ (accessed 2026-10-17) |
| Sample size | About 28,000 units, said to be about 55% of rental units in the covered regions (SAM 2024, via search snippet, UNVERIFIED). An older article cites 290 property-management companies, 20 destinations and 30,000 rooms (STALE). | search snippets |
| Granularity | Monthly destination reports; the comparative report is monthly. Destination Explorer (launched April 2023) adds a **Daily Occupancy Report** view with weather, snowfall, consumer confidence, holiday and school-vacation overlays. | https://corp.inntopia.com/inntopia-launches-destination-explorer/ |
| Property access and cost | Property report packs: Multi-Property Comparative $450; Benchmarking Index $250; Revenue Ranking $300; Property vs Self $300; **Property vs Destination (daily occupancy versus the destination, quarterly) $500**; Daily Prop Comp $500; **Occupancy Lead-Time Analysis $350**; Prop Comp $450. Packs: 3 for $925, 5 for $1,250, 7 for $2,000. These are one-off prices; the page states no subscription period. It describes property managers' monthly submissions as the data source, but states no participation prerequisite for buying. | https://corp.inntopia.com/intelligence/destimetrics/property-report-packs/ [read] |
| Participation rule | "Participation in the RAO is a prerequisite" for comparative reports (MDC sheet). Whether a three-home operator can join is not stated, and no Guesty or PMS integration was found. A 2017 note mentions an API for clients to automate reporting (UNVERIFIED). | MDC sheet; search |
| Recent signal (regional) | Search snippets of a SAM article (page 403) say that as of 2026-09-30, winter occupancy on the books was down 8.3% year on year, with December −6.9% and March −17.1% (**UNVERIFIED**; not used below). Verified: the 2025–26 winter (**Nov–Apr**) closed with occupancy −7% and ADR +1.2% (Snowsports News); the Park Record reported −6.7% occupancy and +1.3% ADR for the season and −17.9% bookings for March–August arrivals as of its April report. April 2026 lead time was 56.4 days and July 51.1 days. The luxury tier (above $401 per night) led summer gains. | SAM/search snippet (UNVERIFIED wording); Snowsports News May 2026 [read] https://www.snowsportsnews.com/newsrepository/2026/may/inntopia-destimetrics-winter-s-woes-melt-into-summer-surge-at-western-mountain-destinations/ |
| Local proxy | The Grand County Tourism Board reports occupancy "through all professionally managed properties": about −7% countywide and more than −10% for Fraser, Winter Park and Silvercreek going into March 2026. The provider is not named. | Sky-Hi News 2026-03-24 [read] https://www.skyhinews.com/news/dry-winter-dampens-tourism-as-grand-county-economy-shows-mixed-signals/ |

**Assessment.** DestiMetrics is the mountain-industry standard for forward OTB, and Winter Park was historically inside it. Its data is **monthly and destination-level**, and nearly all of it comes from condo and hotel inventory managed by professional companies. That makes it a **season and month regime signal**, of the form "Winter Park's March on-the-books occupancy is X% below last year at the same date". It is not a nightly price input for a 16-sleeper. The best low-cost path is **to ask the Grand County Tourism Board or the Chamber whether they receive DestiMetrics and will share the Winter Park monthly OTB index**. The Chamber reported 440 members in 2025 (citizenportal summary via search, UNVERIFIED). Buying the Property vs Destination and Lead-Time reports (about $850 one-off, or the 7-pack at $2,000) would in practice require submitting our own data, since the reports compare a property's submissions with the destination. Evidence that boards share such data: the Grand County Tourism Board's agendas carry Chamber lodging reports (https://visitgrandcounty.com/?p=5979), and Sun Valley publishes a monthly lodging fact sheet (https://visitsunvalley.com/wp-content/uploads/2026/01/Sun-Valley-Area-Monthly-Fact-Sheet_12.31.2025.pdf). Both are reviewer-supplied and were not opened by this agent, so they are UNVERIFIED. That is acceptable in aggregate form but must pass the repo's confidentiality rules.

### 5.2 Why forward market occupancy is the highest-value hotel input, and its STR equivalents

Hotels use forward OTB to see a demand shift **before their own pickup reveals it**. Amadeus pitches it explicitly as confirmed reservations versus search-inferred intent, with the advice to "adjust pricing earlier" (https://www.amadeus-hospitality.com/insight/using-forward-looking-occupancy-to-predict-demand-and-maximize-efficiencies/, VENDOR). The statistical reason matters most for us:

- **Own pace:** effective sample of about 5 stays per window, standard error about 0.2 on the on-books share (§2.3).
- **Comp-set pace (20–40 comps, scraper fixed):** 35–70 effective stays, standard error about 0.06–0.08. That is **about 3× more precise**, and only about 1.8× at today's ~33% valid-row rate.
- **Full-market pace** (hundreds of listings, as in a PriceLabs dashboard or DestiMetrics): more precise again because the panel is much larger, and a different product mix (mostly smaller units, condos and hotels). The rejected "10×" claim applied to our own 20–40-comp set; that set is about 3×, or about 1.8× at today's scrape quality (§2.3 and the transfer table).
- A 3× gain allows a pace weight perhaps three times larger for the same noise-driven price variance, but not a large one. **Forward market occupancy is the most valuable hotel input in principle; for us it is a medium-high value input in practice.** Combining the comp-set series with a full-market series, each shrunk by its own variance, is better than either alone.

| Source | Quality of the "booked" signal | Cost | Granularity | Fit for 5+ BR Winter Park homes |
|---|---|---|---|---|
| DestiMetrics | True reservations, PM-submitted | Likely requires data contribution; property reports $250–$2,000 one-off | Monthly, destination | Regime signal only (mostly condos and hotels) |
| Key Data ProData | True reservations, PMS-direct | Quote | Market, filters UNVERIFIED | Possibly good; requires a quote and a check of the bedroom filter |
| PriceLabs Market Dashboard | Source undocumented; probably calendar-inferred (UNVERIFIED) | From $9.99 per month | Daily; bedroom-count filter (granularity UNVERIFIED) | Good cheap proxy if the filter isolates 5+ BR |
| Lighthouse Market Insight / STR data (ex-Transparent) | Forward demand index plus STR listings data; method not public | Quote | Daily | Unknown; request a demo |
| AirDNA pacing | Calendar-inferred; weakness beyond 4 months per a snippet (UNVERIFIED) | Subscription | Daily, 6 months (help page) | Medium |
| **Own comp-calendar availability index** (scraper) | Calendar-inferred, but on **exactly our comp set** | Already built; needs reliability | Daily, per comp | **Best fit if the scraper is fixed**: the hyper-specialized Demand360 |

**Mechanism for the own index.** For each comp c and stay date d, the scraper records `scrape_status` of available, unavailable or failed.
- Define A_t(d) = share of valid comps unavailable for night d as of scrape date t.
- Market pace index = A_t(d) / Ā(h, season, DOW), where Ā is the historical unavailability at the same lead h.
- **Booked versus blocked:** count only availability→unavailability transitions that occur after the comp was previously open for that night. Discount owner blocks by flagging comps that close long runs at once (≥14 contiguous nights), which looks like an owner hold.
- Each closing comp's last-seen price is a **revealed sale-price proxy**, since the price at which inventory disappears is close to its booked price. This is how calendar-scraping vendors infer ADR (AirDNA methodology page via search; UNVERIFIED for AirDNA specifically).

### 5.3 Rate shopping done right: what Lighthouse does that our scraper does not

Our scraper runs one market-wide search sweep with a 2-night window, and about 67% of rows fail (shared context). Practitioner guidance and Lighthouse documentation suggest six practices:

1. **Shop the exact product.** A rate is comparable only with its room category, meal plan, cancellation policy and occupancy. Length-of-stay discounting varies across properties, so comparisons need matching LOS (hoteltechnologynews 2019, https://hoteltechnologynews.com/2019/09/hotel-rate-data-how-to-ensure-accuracy-and-completeness/; Vervotech mapping article, VENDOR). Lighthouse exposes LOS, guest-count, flexible-versus-lowest and single- versus multi-night comparisons (Hotel Tech Report listing). For us: shop **3–4 night stays at 10–16 guests, total price including fees**, and store the price basis (nightly versus all-in), not 2-night nightly rates.
2. **Live, per-property shops instead of a cached search sweep.** Lighthouse contrasts its live shops with "cached data" (Lighthouse blog, VENDOR). Search-result prices on OTAs are often cached or estimated. Google's hotel price-accuracy program exists precisely because cached and fetched prices diverge (https://support.google.com/hotelprices/answer/6318506). A per-listing calendar or quote request for about 20–40 comps is cheaper and more reliable than a 280-listing sweep.
3. **Dynamic comp set** chosen by location, reviews and pricing pattern (Lighthouse). Ours is curated and static, so new large listings are missed.
4. **Anomaly filtering** with an explicit failure status. Ours already separates "checked and unavailable" from "could not check".
5. **Frequency matched to volatility.** A once-daily snapshot of a market that reprices several times a day tells you where competitors were, not where they are (hoteltechnologynews). For 5+ BR homes repricing is slower, and daily is adequate.
6. **Treat availability as a first-class output**, not a by-product (§5.2).

---

## 6. Total revenue management: from RevPAR to owner net

### 6.1 Hotel metrics

The HSMAI Asia Pacific and Singapore Institute of Technology study (2018; 953 respondents, 27.2% response rate; [read in full], STALE, https://academy.hsmai.org/wp-content/uploads/sites/11/2019/02/2019-hsmai-and-sit-revenue-management-metrics-study-final.pdf) found:
- **RevPAR is used by 77.4%** of respondents, RGI by 48.5%, **GOPPAR by 20.4%** and TRevPAR by 13.7%.
- Among those who see limitations in current metrics, 53.2% cite missing costs, profit or other revenue.
- **NRevPAR** = (room revenue − cost of acquisition) / available rooms. It is the most promising new metric, held back by "no standard for the way costs are accounted".

Schwartz, Altin & Singal (2016, *JRPM*) found RevPAR strongly correlated with GOPPAR overall, but GOPPAR is better where non-room revenue and cost structure vary (https://stars.library.ucf.edu/ucfscholar/424). A 2019 *Annals of Tourism Research* study found RevPAR more useful at firm level and mixed at property level (search snippet, UNVERIFIED). SAS/IDeaS note that revenue optimization implicitly assumes low, uniform variable cost. When channel cost or package cost differs, the optimizer "can account for costs ... optimizing on profits instead of top-line revenue" (SAS 2010). The industry is moving that way: Duetto bought the profitability-benchmarking firm HotStats in 2025 and paired it with FLYR Hospitality's pricing in October 2026 (Hospitality Net 4134812).

### 6.2 Mapping to our owner-net objective (worked math)

The engine's `owner_terms` and `fees_per_night` in `src/pricing/pace.py` define per booked night:

- **owner_net(p, n)** = p × (1 − c − m) + [F × (1 − c) − K] / n
- c = channel fee (0.155 on Airbnb host-only); m = management fee (0.25, applied to the nightly rate); F = guest-paid fees per stay; K = owner cost per stay (turn, consumables, insurance).
- F = $600 + $75 × guests + $80, so **F = $1,430 at 10 guests** (treating the $75 as per guest per stay, as `pace.py` does).
- **Owner fee margin per stay.** Under the candidate config (`pace_learned_owner_net.yaml`), K = $350 turnover + $75 × 10 consumables + $80 insurance = $1,180. All three cost inputs are assumed except the fees. So F(1 − c) − K = $1,430 × 0.845 − $1,180 = $1,208.35 − $1,180 ≈ **$28 per stay**. Per-stay fees roughly cover per-stay costs, so an extra stay is close to cost-neutral for the owner apart from the nightly rate.

**All-in nightly price seen by the guest** = p + F/n. At p = $2,000 (inside the listed $1.7k–$2.5k winter range):

| LOS n | All-in per night | vs nightly p |
|---|---|---|
| 1 | $3,430 | +71.5% |
| 2 | $2,715 | +35.8% |
| 3 | $2,477 | +23.8% |
| 4 | $2,358 | +17.9% |
| 7 | $2,204 | +10.2% |

**What guests compare.** Airbnb has shown total prices, including fees, by default since 2025-04-21 (ABC7, https://abc7news.com/post/airbnb-will-now-show-total-prices-default/16216095/, accessed 2026-10-17). The FTC's rule on unfair or deceptive fees, finalized 2024-12-17 and effective in May 2025, requires short-term lodging, including platform rentals, to show the total price with all mandatory fees more prominently than other price information (Avalara summary, https://www.avalara.com/mylodgetax/en/blog/2025/1/new-federal-junk-fees-rule-requires-short-term-rentals-to-reveal-full-price-up-front.html; Cooley, https://www.cooley.com/news/insight/2024/2024-12-20-ftc-finalizes-junk-fee-rule-aimed-at-live-event-ticket-and-short-term-lodging-fees; accessed 2026-10-17). A guest searching for a given stay therefore compares **all-in totals for that stay** across listings that also carry per-stay fees. They do not compare against our own per-night price for a longer stay.

Consequences the hotel world does not face (hotel fees per stay are small relative to the rate):

1. **Effective elasticity depends on LOS.** The engine already scales β by p/(p + F/n) (`all_in_beta`). The table shows that scaling must use the **actual candidate LOS**, not `typical_los`. For a 1-night orphan, β_nightly = β × 2000/3430 = 0.58β.
2. **Orphan nights: the constraint is demand, not cost.** (An earlier draft benchmarked a 1-night stay against our own 4-night all-in price and concluded it needed a 54% cut. That compared the wrong products and is withdrawn.) The right comparison is our 1-night all-in price against **other 1-night all-in offers** for 14–18 guests, which also carry per-stay fees. Owner net of selling a 1-night orphan = 0.595p + $28, which is positive at any price above the floor. The real question is whether 1-night demand for a 16-sleeper exists in a given gap. The current orphan rule, a flat 12% cut (`discount_multiplier: 0.88`), is not tied to that demand.
   - **Option A:** relax min-stay to the gap length and price the gap as its own product, using β scaled by the all-in factor at the gap's actual LOS. PriceLabs already offers min-stay relaxation to the gap length and gap-blocking check-in/check-out rules (https://hello.pricelabs.co/how-to-use-orphan-gaps-for-increasing-revenue/).
   - **Option B:** offer the extra night to the adjacent booked guest. Owner value = p_ext × 0.595, with no new fee and no new turn. Because the fee margin is only about $28, Option B is **not** justified by avoided cost. It is justified only if the adjacent group is more likely to buy (they are already there) than an outsider is to book a 1-night stay. At p_ext = $1,400 that is $833. Whether to offer it is an acceptance-rate question to test.
   - **Option C:** block the gap when its π is low anyway.
   - Choose the option with the highest P(sell) × owner value. Hotels have no strong Option B because hotel guests rarely extend. For whole-home groups it is plausible, but not sourced as a measured practice.
3. **Management fee base.** If the manager's 25% applies to the nightly rate only, a discount on the nightly rate costs the owner (1 − c − m) = 59.5¢ per dollar, while fees are passed through at (1 − c) and then largely consumed by per-stay costs (a margin of about $28 per stay under the candidate config). Shifting the guest's total from nightly to fees (for example a higher cleaning fee and a lower nightly rate) moves money from manager to owner at constant all-in price, but only if the fee is booked to the owner. Who keeps the cleaning fee is unknown (§12). **That is an owner-versus-manager agency question, not a pricing optimization, and it must be surfaced to the operator, not exploited silently.**
4. **Channel net (NRevPAR analogue).** Direct bookings avoid the 15.5% host-only fee and instead pay card processing, **assumed** here at 3% (not sourced; the real Guesty or processor rate should replace it). The owner keeps 1 − 0.03 − 0.25 = 0.72 of each direct nightly dollar against 0.595 on Airbnb: **about 21% more owner net per nightly dollar**, a gap of 12.5 points of gross. A direct booking priced 10% lower still nets more (0.9 × 0.72 = 0.648 > 0.595). Hotel open pricing and the end of parity clauses (Hunold et al.) both point to pricing direct below OTA when contracts allow.

---

## 7. Resort and ski-hotel specifics

- **Vail Resorts lodging** (FY2025 10-K, [read part], https://www.sec.gov/Archives/edgar/data/812011/000081201125000104/mtn-20250731.htm):
  - Lodging is about 11% of net revenue across about 5,000 owned and managed hotel rooms and condo units.
  - Owned hotels FY2025: RevPAR **$170.70**, ADR $325.65, paid occupancy 52.4%.
  - Managed condominium room revenue fell to $81.5M (−5.4%). Management attributed this to **lower ADR over the holiday peak** and fewer managed condo units (earnings release, https://finviz.com/news/178767/vail-resorts-reports-fiscal-2025-fourth-quarter-and-full-year-results-and-provides-fiscal-2026-outlook).
  - Lodging is packaged with lift tickets, ski school, rentals and transport, and **pass holders get 20% off** lodging (Epic Mountain Rewards).
  - The 10-K does not mention dynamic pricing. Ski-resort lodging RM is **packaging and loyalty-led**, with demand driven by the mountain business.
- **Winter Park history:** Intrawest took over operations in about 2002 for $3M plus $2M per year to the City of Denver, which still owns the resort. Intrawest was sold in 2017 to the KSL and Henry Crown venture that became **Alterra** (Pique News Magazine, https://www.piquenewsmagazine.com/whistler-news/intrawest-finalizes-winter-park-deal-with-denver-2463416, STALE). Winter Park is on the **Ikon** pass. The resort-affiliated reservations function (Winter Park Central Reservations) was the historical DestiMetrics and CRADR link.
- **Snow and lodging demand:** in a dynamic panel of 28 Austrian resorts (1986/87–2005/06), Falk (2010, *Tourism Management*) finds a long-run relationship between overnight stays, snow depth, income and accommodation price (https://www.sciencedirect.com/science/article/abs/pii/S0261517709002180; abstract; STALE). Inntopia's analyst attributed the 2026–27 weak pace to a "snow hangover" from the prior season (SAM snippet, UNVERIFIED wording). Snow therefore acts **both in-season and with a one-season lag**, which supports SQI as a prior plus a carry-over term.
- **Lift-ticket dynamic pricing:** Malasevska & Haugom (2018), "Optimal prices for alpine ski passes," *Tourism Management* 64:291–302 (https://ideas.repec.org/a/eee/touman/v64y2018icp291-302.html, abstract, accessed 2026-10-17). They estimated price-response functions from skier surveys at three Norwegian resorts, segmented by day of week and travel distance, and derived optimal segment prices. They conclude resorts could raise total revenue "substantially" with more dynamic pricing. For lodging this matters indirectly: resorts that price lift tickets dynamically by day push price-sensitive day-trippers toward cheap days, and that pattern can flow through to lodging demand by DOW. Lift-ticket price data at Winter Park is a candidate **signal** (R5/R6), not a lever we control.
- **Holiday minimum stays:** listing-level evidence from Copper Mountain condos shows 6-night minimums on holidays and peak periods, 5 in winter and 2 off-season (trip.com listing, via search; anecdotal). The engine's peak minimum of 4 nights at long lead is shorter than the condo norm. For a 16-sleeper the right number depends on the arrival distribution, which we can measure from our own reservations.
- **Group and wedding blocks:** a 5+ BR home is itself a group product. The hotel analogue is (a) a multi-home request (the twin pair blocked together for a reunion or wedding) priced by **displacement analysis**: accept if the package's owner-net exceeds the expected owner-net of selling each home separately on those dates; and (b) summer wedding weekends, where Saturday-night demand displaces Friday–Sunday stays.

---

## 8. The human and organizational side

- **Overrides help in specific places.** In 20,081,973 forecasts across 1,752 hotels, **more frequent user overrides improved accuracy for group forecasts and during special events, but hurt transient forecasts.** Late overrides were more favourable than early ones, a finding from the Leiden thesis summary rather than the journal abstract (Koupriouchina, van der Rest & Schwartz 2023, *Tourism Economics* 29(8):2143–2164, https://ideas.repec.org/a/sae/toueco/v29y2023i8p2143-2164.html; Leiden summary, https://universiteitleiden.nl/en/news/2019/11/hotel-room-rates-human-work-or-algorithmic-plaything). The thesis recommends **logging override reasons** and having vendors measure override effectiveness.
- **The interface shapes overrides.** With identical forecasts, 57 revenue managers given a "deliberate" interface with no chart made about half as many adjustments as those given a fast interface with a chart (Schwartz & Cohen 2004, *Cornell HRA Quarterly* 45(1):85–98; abstract; STALE).
- **Managers follow recommendations, slowly and in bulk.** Copying a whole week's recommendations made up 52.2% of updates, and on 73.8% of booking days a hotel changed none of its prices (Garcia et al. 2022, [read in full], Figure 5 annotation).
- **Adoption barriers (indirect evidence only).** The HSMAI 2018 survey is about **adopting new RM metrics** (NRevPAR, RevPAC) in **Asia-Pacific**, not about why RM fails. Among reasons not to adopt, the top factor was **perceived lack of usefulness (27.2%)**, then organizational constraints (17.8%), effort (8.9%) and data accuracy (7.8%). Independents were more willing than chains to adopt the new metrics (55.2% vs 44.5%). **No rigorous study of why RM fails at independent hotels was found in this session.** The Garcia et al. evidence (copy-all behaviour, rare updates) is the best behavioural evidence on small independents.

---

## 9. Evidence of impact, and critiques

| Claim | Size | Who measured it | Credibility |
|---|---|---|---|
| IHG price optimization | 2.7% retail revenue; $145M to date | IHG and Revenue Analytics (Interfaces, Edelman) | Medium: company-reported, peer-reviewed practice paper |
| Carlson Rezidor SNAP | 2–4% (compliant vs non-compliant hotels) | Carlson and JDA (Interfaces) | Medium-low: self-selection |
| Marriott RM | $150–200M per year, mid-1990s | Cross (1997), secondary | Low: UNVERIFIED, STALE |
| **Wyndham Destinations vacation rentals: choice-based dynamic pricing** | **+3.5% and +5.2% revenue per unit** in two regions, part of the 2018 season | Wang, McGuire, Terbush, Towns & Anderson (2021), *Interfaces* 51(6):450–462, DOI 10.1287/inte.2021.1075 (https://ideas.repec.org/a/inm/orinte/v51y2021i6p450-462.html; abstract via search, accessed 2026-10-17). Company authors with academics | **Medium**: the closest published STR analogue; company-measured; test design not visible in the abstract |
| Atomize, RoomPriceGenie | 15–22% | Vendors | Low: uncontrolled |
| Lighthouse demand data | +2.3% RevPAR | Vendor | Low |
| Airbnb Smart Pricing adopters | Price −5.7%, revenue +8.6% | Zhang et al. 2021 (independent academics) | High for mass-market STR; shows the generic algorithm cuts price |
| Forecast accuracy to revenue | 20% error cut ≈ 1% revenue | Pölt 1998, via Webb et al. | Low-medium, STALE |
| RMS adoption among independents | ~41% vs 76% chains | Vendor blog (webtonic, via search) | Low: UNVERIFIED |

**The Wyndham vacation-rental model, mechanism.** A **conditional logit** predicts the probability that a rental unit is purchased as a function of lead time, availability, property features and **market selling prices**. A nonlinear optimizer sets prices to maximize revenue, and a **booking-curve heuristic** keeps booking pace on target (abstract). That is almost exactly our engine's structure (pooled booking model with a comp anchor, pace adjustment), validated on vacation rentals at scale. Its lesson for us: the gains reported are single-digit percentages, which our field tests cannot detect (MDE ~33%). The engine must be judged in the simulator.

**Adversarial findings:**
1. **No independent difference-in-differences study of RMS adoption** was found. Lift claims are compliance comparisons or vendor before-and-after figures.
2. **Algorithmic-pricing antitrust:** *Gibson v. Cendyn*. On 2025-08-15 the Ninth Circuit affirmed dismissal of Sherman Act §1 claims against Las Vegas hotels that each licensed the same RMS. The DOJ had filed in support of the plaintiffs, and a parallel case against IDeaS users (*Dai v. SAS Institute*) existed (Baker McKenzie, https://insightplus.bakermckenzie.com/bm/antitrust-competition_1/united-states-ninth-circuit-clarifies-limits-of-antitrust-liability-for-algorithmic-pricing-tools). Our engine uses **public** comp prices only and is not a shared vendor across competitors, so the risk is low. Never ingest competitors' non-public data.
3. **Fairness of LOS controls:** a 2019 *Tourism Economics* study finds customers perceive length-of-stay controls as **unfair**, with loyalty members most negative, which lowers willingness to book (SAGE DOI 10.1177/1354816619901207; abstract via proxy mirror, UNVERIFIED detail). Kimes (1994) found RM practices acceptable when customers know their options and restrictions come with benefits; Taylor & Kimes found perceived fairness drives satisfaction and return intent (Cornell eCommons; STALE). For us, explain minimums ("holiday weeks rent Sat–Sat") rather than hiding them.
4. **Market-data limits:** AirDNA says advance bookings are weakly informative beyond about 4 months. Calendar-inferred occupancy confuses blocks with bookings (Magicbnb critique, UNVERIFIED). Elasticity versus lead time has opposite signs in two hotel studies (§3.1).
5. **Hotel methods assume many units.** Bid prices, unconstraining by segment and overbooking all lean on the law of large numbers within a night. With C = 1 the "forecast" is a probability, and the decision is a stay-level accept/reject.

---

## 10. Transfer analysis

Columns follow R1: method | core assumption | holds for 3 STR homes? | adaptation needed | expected value for owner net | effort.

| Method | Core assumption | Holds for 3 homes? | Adaptation needed | Expected value (owner net) | Effort |
|---|---|---|---|---|---|
| **LOS controls (MinLOS, CTA, CTD)** | Stay requests are a mix of lengths and some block better ones | **Yes, strongly.** One unit per night, so every short stay blocks all overlapping stays. | Make min-stay a stay-level decision: compare a candidate stay's owner-net against the summed bid prices of its nights plus the orphan penalty (§1.3). Add CTA/CTD on holiday spans (for example Saturday-to-Saturday holiday weeks) where the guest message is clear. | **High on 10–25 holiday and peak nights per season**; near zero elsewhere | M |
| **Gap nights: exploit vs block** | A hole can be sold at a discount | **Partly.** Fees roughly cover per-stay costs (owner margin ≈ $28 per stay), so any sale above the floor helps the owner. The binding question is whether 1–2-night demand for a 16-sleeper exists, at all-in prices competitive with other short-stay offers. | Evaluate three options: A, relax min-stay to the gap and price it with β at the gap's actual LOS; B, offer the night to the adjacent guest; C, block. Choose max P(sell) × owner value. Replaces the flat 0.88 multiplier. | Medium | S–M |
| **Bid price / displacement** | Opportunity cost per night can be forecast | **Approximately.** π_i = P(sell later) × E[net]. P comes from the pooled booking model, which is noisy. | Single-unit DP or one-step lookahead (M3); shrink hard; use a market pace index to set P(sell later). | Medium (it powers the LOS logic) | M |
| **Pickup forecasting (additive)** | Booking curves are stable by DOW and season | **With pooling only.** Effective n is about 5 stays per window (§2.3). | Heo-style pooling over neighbouring dates and prior years; switch to additive pickup when OTB ≈ 0; shrink toward the **market** pace. | Medium | S |
| **Unconstraining / regrets & denials** | Turned-away demand is observable | **Partly.** Inquiries, quote requests and declines exist. | Log direct-site quote requests and declined inquiries as censored demand (aggregate only; no guest PII). | Low–medium | S |
| **Forward market occupancy (Demand360, Forward STAR, DestiMetrics)** | Market OTB leads own bookings | **Yes, but the gain is about 3× precision on a 20–40-comp set**, not 10× (§2.3, §5.2) | Build a comp-calendar availability index (own scraper); add PriceLabs dashboard (from $9.99/month) and DestiMetrics regime signal as shadow signals; combine series by inverse variance | **Medium-high** if the scraper is reliable | M |
| **Competitor-relative price optimization (IHG/Carlson)** | Demand depends on own price relative to comp price | **Yes for level; elasticity is weakly identified.** | Anchor = comp median (already done); demand = P0 × (p/p_comp)^ε; learn ε with the recommendation-controlled estimator (§3.1) | Medium–high (stops ceiling-pinning) | M |
| **Recommendation-controlled elasticity (Garcia et al.)** | Managers follow recommendations with an *exogenous* delay; tens of thousands of bookings | **Weakly.** Our caps, deference and clamps are deterministic in the recommendation and add no variation; only Thompson exploration and random approval lag do; overrides are endogenous. About 100 bookings gives SE(β) ≈ 2.8 per season (§3.1). | Log (recommended, listed, exploration draw, booked) per night now; estimate only when simulator power analysis says the SE beats the prior | Low now, medium later (prevents a pinned −0.3 β once there is enough data) | S (logging) |
| **Choice-based (conditional logit) booking model with market prices and booking-curve heuristic (Wyndham vacation rentals)** | Unit-level purchase probability depends on lead time, availability, features and market prices | **Yes in structure**; parameters must be pooled across homes and seasons | Matches the engine's pooled booking model plus comp anchor plus pace; use as the reference design for `src/bookprob` | Medium (validates the design; 3.5–5.2% reported) | — (already the structure) |
| **Open pricing by channel and segment** | Many segments and channels with different net | **Partly.** Three channels, one public product. | Allow a direct-channel discount up to the fee differential, subject to platform terms | Low–medium | S |
| **Rate parity** | Contracts force parity | Unknown for Airbnb/VRBO here | Operator decision | Low | — |
| **Overbooking** | Many units, no-shows | **No.** One unit; a "walk" is catastrophic. | None. Use cancellation-policy optimization instead (out of scope). | None | — |
| **Group displacement** | Large blocks displace transient demand | **Yes for twin-home blocks and wedding weekends** | Accept a multi-home package only if its owner-net exceeds the expected separate owner-net | Low–medium (rare, large) | S |
| **Total RM / GOPPAR / NRevPAR** | Costs differ by stay, channel and package | **Yes, more than for hotels.** Turn costs and fees dominate short stays. | Already the objective (owner net). Make LOS and channel explicit in `owner_terms`. Surface the management-fee base and the cleaning-fee owner as agency issues. | Medium | S |
| **ML forecasting (LightGBM, 100 models)** | Thousands of observations per segment | **No** (about 100 reservations) | Use at **market** level only (comp availability series) | Low now | L |
| **Human overrides** | Experts hold information the model lacks | **Yes on events; no on routine nights** (Koupriouchina et al.) | Allow overrides with reason codes; scope them to event and holiday nights; measure them | Medium (avoids harm) | S |
| **Packaging (lift + lodging)** | Lodging sold with resort products | Not owned by us | Partner-perk framing at most (for example a ski-rental partner). Not a pricing lever. | Low | — |
| **Matched-property pilots (IDeaS)** | Comparable twins exist | **Yes. Summit Haus and Overlook Ridge are near-twins.** | Run paired tests between the twins with alternating treatment by week; report with variance reduction | Measurement value high | S |

### What generic STR pricers miss (H2)

1. **They price off the median listing.** Airbnb's own system gains revenue by **lowering** prices about 5.7% for the typical host (Zhang et al. 2021). Small-hotel pricers use the same base + market + occupancy skeleton (RoomPriceGenie). Neither has a 16-sleeper winter demand model, and the PriceLabs market dashboard's coarsest bedroom bucket is "3+".
2. **Their gap handling is rule-based, not demand-based.** PriceLabs is better than a flat discount: its default 20% gap discount comes with min-stay relaxation to the gap length and gap-blocking check-in/check-out rules (https://hello.pricelabs.co/how-to-use-orphan-gaps-for-increasing-revenue/, VENDOR). What it does not do, per its documentation, is decide between selling, extending a neighbour and blocking on the basis of P(sell) for a 16-sleeper at that LOS and owner net. The edge is modest and must be shown in the simulator.
3. **Their elasticity, where they have one, is learned from confounded data.** Garcia et al. show that naive estimates are biased toward zero or positive. A pricer that learns "price up → bookings up" will over-price shoulder nights and under-learn peak.
4. **They show market forward occupancy but do not document using mountain regime data as a pricing input.** PriceLabs *displays* forward market occupancy (which is why recommendation #4 uses it), and its pricing reacts to its own market data. But no reviewed pricer documents using DestiMetrics-type destination OTB or snow carry-over ("snow hangover") as a **pricing input** (UNVERIFIED: only public documentation was checked). Inntopia's Destination Explorer overlays snowfall for analysis, not pricing.
5. **They optimize gross revenue or occupancy, not owner net after the manager's fee base and turn costs.**

Where generic pricers are **not** worse: daily operations, channel push, breadth of comp data and PriceLabs' calendar-scale pacing. Specialization should yield its edge on holiday and peak-weekend nights, which we **expect** to carry a disproportionate share of revenue (an assumption to check against our own per-night aggregates, not a sourced figure), and on LOS and orphan decisions. It yields little on routine shoulder nights.

---

## 11. Ranked recommendations

Impact is stated as a direction and order of magnitude in owner-net terms. No figure here is a measured lift. Every item must be proved in `proving_ground_exam/` (calibration v2) on paired held-out seeds before any live flag changes, consistent with the doctrine.

| # | Recommendation | Module(s) | Expected impact | Confidence | Effort | Data needed | Measurement plan (owner net) |
|---|---|---|---|---|---|---|---|
| 1 | **Rebuild comp acquisition as exact-product, per-listing shops plus a forward availability index.** Shop 20–40 curated 5+ BR comps by calendar and quote for 3–4-night, 10–16-guest stays; tag price basis (nightly or all-in); record available, unavailable and failed per night; compute the market pace index A_t(d)/Ā(h) with booked-versus-blocked heuristics (§5.2–5.3). | `src/scrape`, `src/comps`, `src/pricing/pace.py` | **High for the comp anchor** (3% → most nights; the binding constraint). **Medium for the availability index** (about 3× pace precision on 20–40 comps, §2.3). | Medium | M (2–3 weeks) | Daily comp calendars | (a) Scrape validity >90% of rows and anchor coverage of nights; (b) offline: IC of the market pace index at leads 14/30/60 against our homes' final occupancy, through the signals ladder (IC ≥ 0.05, hit rate ≥ 0.52); (c) simulator: add a market-shock scenario where demand moves before own bookings, comparing paired owner net of pace(own) and pace(market-blended) |
| 2 | **Log now, estimate later: a recommendation-controlled elasticity estimator** (Garcia et al.). Log (recommended, listed, Thompson draw, approval delay, booked) per home-night daily. (Audit note, 2026-10-19: `price_recommendations` already stores the model, bounded, move-capped and final price with the listed price at run time, and `recommendation_outcomes` stores the applied listed price and booking; the gaps are the Thompson draw, the approval delay, and the empty `shadow_daily` table.) Exclude manual overrides as endogenous. When power allows, regress the booking indicator on listed price with a flexible control in the recommendation, pooled over homes with season interactions, shrunk to the prior. Until then, keep β as a shrunk prior (the candidate's −1.00 all-in at peak) and stop trusting the M1 median split, which pins at the −0.3 clip. | `src/elasticity`, `src/bookprob`, `src/pacing` (logging) | **Low now, medium later.** With about 100 bookings, SE(β) ≈ 2.8 per season at 5% exploration (§3.1). | High on the diagnosis (M1 is biased); low on near-term precision | S (logging), M (estimator) | `pacing_snapshots` plus recommendation and exploration history | **Power calculation first:** in the simulator with known true β, find the bookings and exploration spread needed for SE(β) < 0.3 (prior SD scale). Then compare bias and RMSE of the naive vs controlled estimators over 25 seeds, booking-model log-loss and Brier on held-out nights, and paired owner net |
| 3 | **Stay-level bid-price logic for min-stay and orphan gaps**, with Options A, B and C and LOS-specific all-in elasticity (§1.3, §6.2). Replaces the flat orphan multiplier and the M4 heuristic. | `src/leakage`, `src/min_stay`, `src/compose`, `pace.all_in_beta` | **Medium-high on holiday and peak spans** | Medium | M | Booking-probability model by LOS; turn cost K | Simulator holiday spans (Christmas, MLK, Presidents', spring break): paired owner net, orphan nights created, orphan nights monetized, share sold. Live: shadow log of the option chosen vs the current rule |
| 4 | **Add cheap forward market OTB as shadow signals now.** PriceLabs Market Dashboard (bedroom-count filter, from $9.99/month); a Lighthouse Market Insight/STR demo; a request to the Chamber or Tourism Board for the DestiMetrics Winter Park monthly OTB index; a Key Data quote. | `src/signals/collectors` (new, shadow) | Medium | Medium | S | Accounts and an exported series (aggregate) | Signals ladder: 30+ observations to shadow, IC ≥ 0.05 to active. Compare with the own-scraper index (item 1) for agreement |
| 5 | **Pooled additive pickup** (Heo et al.): neighbouring-date and prior-year pooling, additive when OTB is near zero, shrink to market pace with w = n/(n+κ). | `src/pricing/pace.py`, `src/pacing` | Medium (variance reduction of pace) | **Medium** (Heo's gain was measured in a COVID regime shift; backtest on our own snapshots first) | S | `pacing_snapshots` (accumulating) | Backtest MAPE of final occupancy at leads 7–60, classic vs pooled; simulator paired owner net |
| 6 | **LOS- and channel-aware owner-net terms**: all-in β at the candidate LOS (not `typical_los`); optional direct-channel price allowance up to the fee differential, if platform terms allow. | `src/pricing/pace.py` (`owner_terms`, `all_in_beta`) | Medium | Medium-high (arithmetic) | S | Channel fee by channel; K; fee rules | Simulator fee-salience and channel overlays; channel-mix and net-per-night report |
| 7 | **Override protocol**: operator overrides allowed with reason codes, encouraged on event and holiday nights, discouraged on routine nights; monthly scorecard of overridden vs model nights. | `src/review`, `src/explain` | Medium (avoids harm, captures event knowledge) | Medium (hotel evidence) | S | Override log | Owner net and forecast error on overridden vs non-overridden nights, by night type |
| 8 | **Calibrate holiday minimums from our own arrival distribution, and explain them** (Saturday-to-Saturday weeks, CTA on mid-week holiday arrivals). Condo norms are 6 nights on holidays. | `config/policies` `min_stay_rules`, listing copy | Medium on holiday weeks | Low-medium | S | Aggregate LOS and arrival-day counts by season | Simulator holiday scenario; operator review |
| 9 | **Twin-block displacement rule** for weddings and reunions: accept a two-home package price only if owner net ≥ E[separate owner net]. | `src/compose` (advisory) | Low–medium (rare, large) | Medium | S | Inquiry log | Advisory only; ex-post comparison |
| 10 | **Do not build:** overbooking, segment-level open pricing, network-scale ML forecasting. **Do not buy Demand360 or Agency360 now**: Demand360 does track alternative-accommodation availability, but it is built around a contributing hotel's comp set, contract and contribution terms and cost are unpublished, and Winter Park large-home depth is unknown; Agency360 covers GDS travel-agent bookings, which whole-home ski rentals rarely use. Revisit only after a free trial shows a Winter Park 5+ BR series. | — | Avoids waste | Medium-high | — | — | — |

---

## 12. Open questions for the operator

1. Does the Grand County Tourism Board or the Winter Park & Fraser Chamber receive DestiMetrics (or Key Data) reports, and would they share the Winter Park monthly forward-occupancy index?
2. Are you willing to contribute aggregate monthly occupancy and rate data for the homes to DestiMetrics or Key Data in exchange for market access? Confirm the confidentiality terms first.
3. Who keeps the $600 cleaning fee, the owner or the manager? What is the real per-turn cost K, and is the 25% management fee charged on the nightly rate only, or on fees too?
4. Do Airbnb or VRBO terms, or your own policy, allow the direct site to be cheaper than the OTA price?
5. Would you offer an adjacent booked guest an extra night at a discount (Option B) instead of discounting a 1-night gap to strangers?
6. What holiday policy do you want: Saturday-to-Saturday weeks, a 5–7 night minimum, CTA on certain days?
7. How often do multi-home (twin) requests for weddings or reunions arrive?
8. Is there a log of direct-site quote requests and declined inquiries (aggregate counts only)?
9. When you approve recommendations, do you do so in batches with delays? (This is useful for elasticity identification, so keep the approval log.)

---

## Appendix A: Search log (62 web searches, plus about 35 page or PDF fetches)

Mode E = extended, S = standard. "Yield" summarizes what each query produced.

| # | Query (abridged) | Mode | Yield |
|---|---|---|---|
| 1 | Inntopia DestiMetrics Winter Park Colorado occupancy | E | Regional SAM/Steamboat briefings; no Winter Park figure |
| 2 | DestiMetrics participating property management data sharing cost | E | **Property report pack prices**; Inntopia acquisition |
| 3 | Marriott RM history demand forecasting Cross Higbie Interfaces | E | Marriott group pricing Interfaces DOI; DFS secondary claims |
| 4 | "DestiMetrics" "Winter Park" OR "Grand County" lodging report | E | Grand County Tourism Board occupancy (provider unnamed) |
| 5 | DestiMetrics Market Briefing 17 destinations methodology | E | 17 destinations, ~28,000 units; Colorado+Utah split |
| 6 | Grand County Tourism Board occupancy Key Data OR DestiMetrics | E | Board report; no provider named |
| 7 | DestiMetrics destinations list Aspen Vail … "Winter Park" | E | **MDC sheet listing Winter Park**; CRADR deck |
| 8 | "Winter Park" chamber "DestiMetrics" occupancy | E | Nothing specific |
| 9 | Inntopia DestiMetrics Oct 2026 briefing Tom Foley | S | Older briefings; Foley titles |
| 10 | Key Data Dashboard Winter Park forward occupancy | E | Key Data Winter Park page (PMS-direct) |
| 11 | Key Data pricing subscription pacing | S | Custom quote; ProData vs HostData |
| 12 | Marriott One Yield Edelman LOS $150–200M | E | INFORMS history; secondary $ figure |
| 13 | Marriott group pricing optimizer authors $ | S | Lawsuit noise; Interfaces references page |
| 14 | Cross Higbie "RM renaissance" CHQ | S | Anderson & Xie review; ISHC history PDF |
| 15 | Koushik Higbie Eister IHG retail price optimization | S | **IHG abstract: $145M; 2.7%** |
| 16 | Hilton RMS IDeaS GRO Edelman | S | Hilton–IDeaS G3 2013 |
| 17 | IDeaS G3 patent BAR LOS | E | IDeaS help and datasheet; no patent |
| 18 | Duetto Open Pricing explained | E | Duetto glossary and Beyond BAR |
| 19 | patents.google IDeaS revenue management | E | US6263315, US20130006712 |
| 20 | Duetto patent | S | Trade press on alert patent (UNVERIFIED) |
| 21 | SAS Institute patent hotel pricing LOS | E | **SAS Global Forum 346-2010**; Harrah's patent |
| 22 | Amadeus Demand360 methodology | E | Overview sheet; >44,000 providers |
| 23 | CoStar STR Forward STAR methodology | E | Forward STAR guidelines |
| 24 | Lighthouse rate shopper LOS occupancy cached vs live | E | Product descriptions only |
| 25 | Atomize RMS data inputs | S | Mews community; vendor lift claims |
| 26 | RoomPriceGenie algorithm inputs | S | Vendor claims |
| 27 | RoomPriceGenie help occupancy strategy base price market factor | E | **Help-center mechanics** |
| 28 | Lighthouse help LOS guests flexible vs lowest | E | Lighthouse blog |
| 29 | FLYR Hospitality Pace Revenue acquisition | S | 2022 acquisition; Duetto–FLYR 2026 report |
| 30 | Duetto GameChanger inputs regrets denials | S | GameChanger sheet; HQ plus comp rates |
| 31 | Weatherford Kimes forecasting comparison | S | **IJF 2003 abstract** |
| 32 | Pekgün Carlson Rezidor Interfaces lift | S | **2–4% compliant hotels** |
| 33 | RM overrides CHQ evidence | E | Kimes CHR pointers |
| 34 | Judgmental adjustments user overrides hotel forecasts | E | **Koupriouchina; Schwartz & Cohen** |
| 35 | "Judgmental Adjustments …" authors journal | S | Tourism Economics 29(8) details |
| 36 | Schwartz Cohen expert-judgment bias | S | CHRAQ 45(1) abstract |
| 37 | Bitran Mondschein multiple-day stays | S | OR 43(3) abstract |
| 38 | Forecasting with market forward occupancy / comp sets | E | **Heo 2023; Das 2021**; Lighthouse claim |
| 39 | GOPPAR vs RevPAR NetRevPAR HSMAI | S | Schwartz/Altin/Singal; HSMAI study PDF |
| 40 | Vail Resorts 10-K lodging RevPAR 2025 | S | **10-K FY2025** |
| 41 | Winter Park Alterra lodging company | S | Ownership context |
| 42 | Ski condo minimum stay Christmas policy | S | Copper listings: 6-night holiday minimum |
| 43 | Ski accommodation prices snow hedonic elasticity | E | **Falk 2010 panel**; lift-ticket hedonics |
| 44 | Intrawest Winter Park 2002 lease → Alterra | S | Pique 2002; Alterra 2017 |
| 45 | Gibson v. Cendyn hotel algorithmic pricing Ninth Circuit | S | **Affirmed dismissal 2025-08-15** |
| 46 | Hotel price elasticity endogeneity IV | E | **Garcia et al. MS**; Cho et al.; Corgel |
| 47 | Ye "Customized Regression Model for Airbnb Dynamic Pricing" | S | KDD 2018; Acolyer summary |
| 48 | "Demand Estimation Using Managerial Responses …" | S | Authors, CESifo PDF (read in full) |
| 49 | Riasi Schwartz LOS-based room pricing CHQ | S | Not found; related Cornell items |
| 50 | PriceLabs orphan day gap min-stay docs | S | **Orphan defaults (20%)** |
| 51 | PriceLabs Market Dashboard future occupancy cost | S | **$9.99/dashboard/month** |
| 52 | AirDNA pacing methodology blocked vs booked critique | E | AirDNA help; Magicbnb critique |
| 53 | Independent RMS adoption RevPAR difference-in-differences | E | **None found**; vendor stats only |
| 54 | Hunold et al. best price clauses | S | IJIO 2018 findings |
| 55 | Group displacement analysis formula | S | Hospitality Net explainer; eCornell |
| 56 | Inntopia "Winter Park" 2025/2026 on the books | E | **Winter OTB −8.3% (Sept 30 2026)**; Chamber 2025 report |
| 57 | Kimes Wirtz fairness LOS restrictions | S | **2019 LOSC unfairness**; Kimes 1994 |
| 58 | CTA CTD MinLOS definitions | S | Mews, Infor docs |
| 59 | Zhang Mehta Singh Srinivasan Airbnb Smart Pricing | S | **−5.7% price, +8.6% revenue** |
| 60 | Rate shopper data quality problems | S | Mapping and LOS mismatch; Google price accuracy |
| 61 | Town of Winter Park lodging tax seasonality | S | Nothing for Winter Park (Keystone analogue) |
| 62 | DestiMetrics PMS integration Guesty/Streamline | E | **No integration found**; Destination Explorer |
| 63 | "Choice-Based Dynamic Pricing for Vacation Rentals" Wyndham (revision) | S | **Interfaces 51(6); +3.5%/+5.2%** |
| 64 | Nadarajah Lim Ding multiple-day stays (revision) | S | **SMU WP 2015; up to 7% over decomposition** |
| 65 | Lighthouse acquires Transparent STR data (revision) | S | **March 2022; 35M+ listings; Market Insight** |
| 66 | Amadeus Agency360 / Demand360 STR (revision) | S | Agency360 = GDS agent bookings; no STR booking data |
| 67 | FTC junk fees short-term lodging; Airbnb total price (revision) | S | **Rule 2024-12-17, effective May 2025**; Airbnb date found via ABC7 fetch |
| 68 | Marriott One Yield MORE history (revision) | E | **CIO 2007: One Yield 2003, $86M, 83%→91%**; MORE not found |
| 69 | Unconstraining EM projection detruncation (revision) | S | **Weatherford & Pölt 2002; Ferguson et al.** |
| 70 | 2011 Edelman IHG 2.7% (revision) | S | INFORMS abstract confirms 2.7%, 2,077 hotels |

Key fetches and reads: DestiMetrics MDC PDF and CRADR PDF (both read in full); Inntopia product and report-pack pages; Grand County Accommodations Summary 2024 PDF (read); Sky-Hi News; SGB; Snowsports News; ISHC PDF (read); INFORMS history; SAS 346-2010 (read in full); IDeaS science page; Duetto Beyond BAR; RoomPriceGenie help; Lighthouse blog; Amadeus article; FLYR+D360 page; Forward STAR (via search); three Google Patents pages; CESifo WP 9127 (read in full); PMC Heo 2023 and Das 2021; Emerald Webb 2022; HSMAI/SIT 2018 (read in full); Vail 10-K (first third); Pique; Acolyer; PriceLabs help; AirDNA help; Leiden news; Destination Explorer release. Paywalled or blocked (403): Interfaces (Marriott, Carlson), ResearchGate, SAM articles, Gunnison Times, AirDNA forecast page, hospitality-on.

---

## Appendix B: Sources by class (74 original + 16 added in revision = 90 distinct)

Recount note (reviewer): the Ye et al. entry (#15) is cited via a video page and a blog summary; the textbooks (#23–26) were not read this session and are cited through secondary works. Even counting those strictly, every class remains above the bar.

**1. Peer-reviewed and academic (22)**
1. Garcia, Tolvanen & Wagner (2022) *Management Science* 68(11) / CESifo WP 9127. https://www.ifo.de/DocDL/cesifo1_wp9127.pdf
2. Koushik, Higbie & Eister (2012) *Interfaces* 42(1):45–57. https://ideas.repec.org/a/inm/orinte/v42y2012i1p45-57.html
3. Carlson Rezidor SNAP, *Interfaces* (2013). https://pubsonline.informs.org/doi/10.1287/inte.1120.0660 (abstract only)
4. Marriott Group Pricing Optimizer, *Interfaces*. https://doi.org/10.1287/inte.1090.0482 (abstract only)
5. Weatherford & Kimes (2003) *IJF* 19(3). https://ecommons.cornell.edu/bitstream/handle/1813/72130/Kimes30_Comparison_of_Forecasting.pdf
6. Heo, Viverit & Pereira (2023) *JRPM*. https://pmc.ncbi.nlm.nih.gov/articles/PMC10007649/
7. Das, Chadha & Banerjee (2021) *JRPM* 20(3). https://pmc.ncbi.nlm.nih.gov/articles/PMC8007660/
8. Webb, Schwartz, Xiang & Altin (2022) *JHTI* 5(5). https://www.emerald.com/insight/content/doi/10.1108/JHTI-05-2021-0124/full/html
9. Koupriouchina, van der Rest & Schwartz (2023) *Tourism Economics* 29(8). https://ideas.repec.org/a/sae/toueco/v29y2023i8p2143-2164.html
10. Schwartz & Cohen (2004) *CHRAQ* 45(1). https://cris.bgu.ac.il/en/publications/hotel-revenue-management-forecasting-evidence-of-expert-judgment/
11. Bitran & Mondschein (1995) *OR* 43(3). https://ideas.repec.org/a/inm/oropre/v43y1995i3p427-443.html
12. Schwartz, Altin & Singal (2016) *JRPM*. https://stars.library.ucf.edu/ucfscholar/424
13. Falk (2010) *Tourism Management*. https://www.sciencedirect.com/science/article/abs/pii/S0261517709002180
14. Hunold, Kesler, Laitenberger & Schlütter (2018) *IJIO* 61. https://www.zew.de/fileadmin/FTP/dp/dp16066.pdf
15. Ye et al. (2018) KDD, Airbnb dynamic pricing. https://videolectures.net/kdd2018_ye_airbnb_dynamic_pricing
16. Zhang, Mehta, Singh & Srinivasan (2021) *Marketing Science* 40(5):813–820. https://pubsonline.informs.org/doi/10.1287/mksc.2021.1295 (403 to this agent; figures from abstract summaries)
17. Corgel et al., Cornell, hotel industry demand. https://ecommons.cornell.edu/bitstream/1813/72477/1/Corgel107_Hotel_industry.pdf
18. Length-of-stay control fairness (2019) *Tourism Economics*. DOI 10.1177/1354816619901207 (abstract via proxy mirror)
19. Weatherford, Uysal, Webb & Altin, comp-set occupancy forecasting. https://www.researchgate.net/publication/291948151 (abstract; UNVERIFIED)
20. Kimes (1994) and Taylor & Kimes, fairness (Cornell eCommons). https://ecommons.cornell.edu/server/api/core/bitstreams/5fe62090-75bb-457b-9692-bca790b53be8/content
21. Late-booker elasticity, city hotel (2025). https://www.sciencedirect.com/science/article/pii/S0261517725002523 (abstract)
22. Koupriouchina PhD thesis summary, Leiden University news (2019). https://universiteitleiden.nl/en/news/2019/11/hotel-room-rates-human-work-or-algorithmic-plaything (a university news page, not peer-reviewed; counted here because it summarizes a PhD thesis)

**2. Canonical textbooks (4)**
23. Talluri, K. & van Ryzin, G. (2004). *The Theory and Practice of Revenue Management*. Springer. Bid-price LP and DP (not re-read this session).
24. Phillips, R. (2005). *Pricing and Revenue Optimization*. Stanford University Press. Price-response functions (cited via Garcia et al.).
25. Cross, R. (1997). *Revenue Management: Hard-Core Tactics for Market Domination*. Broadway Books. Marriott and Oktoberfest (cited via INFORMS).
26. Ivanov, S. (2014). *Hotel Revenue Management: From Theory to Practice*. Zangador. Metrics (cited via HSMAI).

**3. Vendor documentation, white papers, patents (25)**
27. Dietz & McGuire, SAS Global Forum 2010, paper 346. https://support.sas.com/resources/papers/proceedings10/346-2010.pdf
28. IDeaS, Science behind G3. https://ideas.com/science-behind-g3-rms/
29. IDeaS G3 help, pricing configuration. https://help.ideas.com/g3rms_cp/Content/Pricing/Pricing-Configuration-Overview.htm
30. IDeaS–Hilton release. https://ideas.com/de/news/hilton-worldwide-partners-with-ideas-on-global-revenue-initiative/
31. Duetto, Beyond BAR. https://www.duettocloud.com/en-us/library/beyond-bar-the-power-of-open-pricing
32. Duetto glossary. https://www.duettocloud.com/en-us/glossary
33. RoomPriceGenie help, occupancy strategy. https://help.roompricegenie.com/en/knowledge/occupancy-strategy
34. PriceLabs Market Dashboards help. https://help.pricelabs.co/portal/en/kb/articles/market-intel-dashboard
35. PriceLabs orphan gaps. https://hello.pricelabs.co/how-to-use-orphan-gaps-for-increasing-revenue/
36. Lighthouse, pricing vs traditional rate shopper. https://www.mylighthouse.com/resources/blog/lighthouse-pricing-vs-traditional-rate-shopper
37. Lighthouse, predictive market intelligence. https://www.mylighthouse.com/resources/insights/predictive-market-intelligence-hotel-demand-forecast
38. Amadeus Demand360 overview sheet. https://connect.amadeus-hospitality.com/hubfs/Amadeus-Demand360-Overview-Sheet.pdf
39. Amadeus, forward-looking occupancy. https://www.amadeus-hospitality.com/insight/using-forward-looking-occupancy-to-predict-demand-and-maximize-efficiencies/
40. FLYR Hospitality + Demand360. https://www.flyrhospitality.com/resources/flyr-hospitality-insights-amadeus-demand360
41. CoStar Forward STAR guidelines. https://www.costar.com/products/str-benchmark/resources/guidelines/forward-star-data-reporting-guidelines
42. Inntopia DestiMetrics. https://corp.inntopia.com/intelligence/destimetrics/
43. DestiMetrics property report packs. https://corp.inntopia.com/intelligence/destimetrics/property-report-packs/
44. DestiMetrics MDC sheet (2016). https://destimetrics.com/wp-content/uploads/2016/03/MDC_1.1_with_links.pdf
45. Inntopia Destination Explorer (2023). https://corp.inntopia.com/inntopia-launches-destination-explorer/
46. Key Data, Winter Park. https://www.keydata.co/markets/winter-park-colorado
47. AirDNA help, future bookings. https://help.airdna.co/en/articles/8062184-how-do-i-analyze-future-bookings-with-airdna
48. US6263315B1 (Talluri). https://patents.google.com/patent/US6263315
49. US20130006712A1 (Amadeus). https://patents.google.com/patent/US20130006712
50. US6993494B1 (Harrah's). https://patents.google.com/patent/US6993494
51. Mews MLOS guide and Infor HMS restrictions. https://www.mews.com/en/blog/hotel-minimum-length-of-stay ; https://docs.infor.com/hms/2026.x/en-us/hmsolh/s_t1424428597259.html

**4. Industry bodies (4)**
52. INFORMS, History of O.R. Excellence: RM. https://www.informs.org/Explore/History-of-O.R.-Excellence/O.R.-Methodologies/Revenue-Management
53. HSMAI APAC & SIT, RM Metrics Study (2018). https://academy.hsmai.org/wp-content/uploads/sites/11/2019/02/2019-hsmai-and-sit-revenue-management-metrics-study-final.pdf
54. CRADR presentation (2016). http://corp.inntopia.com/wp-content/uploads/2016/05/Presentation-CRADR.pdf
55. ISHC / HNN, Stuart-Hill (2021). https://ishc.com/wp-content/uploads/The-Origin-of-Revenue-Management-in-The-Hospitality.pdf

**5. Company filings (2)**
56. Vail Resorts FY2025 10-K. https://www.sec.gov/Archives/edgar/data/812011/000081201125000104/mtn-20250731.htm
57. Vail Resorts FY2025 results release. https://finviz.com/news/178767/vail-resorts-reports-fiscal-2025-fourth-quarter-and-full-year-results-and-provides-fiscal-2026-outlook

**6. Government and official (2)**
58. Grand County, Accommodations Summary 2024 (AirDNA-sourced: about 3,200 STRs countywide). https://grandcounty365.com/wp-content/uploads/sites/11/dlm_uploads/2024/11/Accommodations-Summary.pdf
59. Google Hotel Center, price accuracy (platform official documentation). https://support.google.com/hotelprices/answer/6318506

**7. Practitioner and trade press (15)**
60. Sky-Hi News, 2026-03-24. https://www.skyhinews.com/news/dry-winter-dampens-tourism-as-grand-county-economy-shows-mixed-signals/
61. SGB, DestiMetrics July 2026. https://sgbonline.com/destimetrics-market-briefing-july-2026/
62. Snowsports News, May 2026. https://www.snowsportsnews.com/newsrepository/2026/may/inntopia-destimetrics-winter-s-woes-melt-into-summer-surge-at-western-mountain-destinations/
63. SAM, "Strong Fall Precedes Slow Winter" (Oct 2026; snippet only). https://www.saminfo.com/strong-fall-precedes-slow-winter-bookings-forecast-for-western-mountain-destinations/
64. Pique News Magazine, Intrawest–Winter Park. https://www.piquenewsmagazine.com/whistler-news/intrawest-finalizes-winter-park-deal-with-denver-2463416
65. Baker McKenzie, Ninth Circuit algorithmic pricing. https://insightplus.bakermckenzie.com/bm/antitrust-competition_1/united-states-ninth-circuit-clarifies-limits-of-antitrust-liability-for-algorithmic-pricing-tools
66. The Morning Paper (Acolyer), Airbnb CRM. https://blog.acolyer.org/2018//03/customized-regression-model-for-airbnb-dynamic-pricing/
67. Hotel Technology News, rate data accuracy (2019). https://hoteltechnologynews.com/2019/09/hotel-rate-data-how-to-ensure-accuracy-and-completeness/
68. Hospitality Net, displacement explainer. https://www.hospitalitynet.org/explainer/4134223/how-to-conduct-an-effective-hotel-displacement-analysis
69. Hospitality Net, IHG launch (2009). https://www.hospitalitynet.org/news/4043331/ihg-launches-price-optimization-module
70. Hospitality Net, FLYR acquires Pace (2022). https://www.hospitalitynet.org/news/4112519.html
71. STR Specialist, Key Data review. https://strspecialist.com/reviews/key-data-dashboard-review
72. Steamboat Pilot / dossier 03 Inntopia quotes (via prior dossier). https://www.steamboatpilot.com/news/bad-snow-years-make-for-bad-bookings-economic-policies-uneven-snowfall-contribute-to-lackluster-colorado-ski-season/
73. Magicbnb, AirDNA critique. https://magicbnb.io/blog/how-to-read-airdna-data-without-overpaying
74. Mews community, Atomize. https://community.mews.com/mews-rms-atomize-a-mews-company-92/introduction-to-atomize-a-mews-company-ai-powered-real-time-pricing-intelligence-2895

**Added in revision (accessed 2026-10-17)**
75. Wang, McGuire, Terbush, Towns & Anderson (2021), "Choice-Based Dynamic Pricing for Vacation Rentals," *Interfaces* 51(6):450–462. https://ideas.repec.org/a/inm/orinte/v51y2021i6p450-462.html (academic; abstract)
76. Nadarajah, Lim & Ding (2015), "Dynamic pricing for hotel rooms when customers request multiple-day stays," SMU working paper. https://ink.library.smu.edu.sg/lkcsb_research/5147 (academic; abstract via search)
77. Malasevska & Haugom (2018), "Optimal prices for alpine ski passes," *Tourism Management* 64:291–302. https://ideas.repec.org/a/eee/touman/v64y2018icp291-302.html (academic; abstract)
78. Weatherford & Pölt (2002), unconstraining methods, *JRPM* 1(3). https://www.doi.org/10.1057/PALGRAVE.RPM.5170027 (academic; abstract via search)
79. Ferguson, Crystal, Higbie & Kapoor, "A Comparison of Unconstraining Methods to Improve Revenue Management Systems," Georgia Tech. https://repository.gatech.edu/entities/publication/9fcfec43-a0f3-4996-ab40-1fd0a93a4e3a (academic working paper; abstract)
80. CIO, "The Price Is Always Right" (Marriott One Yield), 2007-06-13. https://www.cio.com/article/274973/budget-the-price-is-always-right.html (trade; STALE)
81. Hospitality Net, Marriott wins CIO award for One Yield, 2005. https://www.hospitalitynet.org/news/4022124 (trade; STALE)
82. Hospitality Net, Duetto acquires FLYR Hospitality (2026-10-08; HotStats 2025). https://www.hospitalitynet.org/news/4134812.html (trade)
83. Hospitality Net, OTA Insight acquires Transparent (2022). https://www.hospitalitynet.org/news/4109377 (trade)
84. Hotel Tech Report, Amadeus Agency360+ launch. https://hoteltechreport.com/news/amadeus-agency360-launch (trade; via search)
85. INFORMS, 2011 Edelman finalist IHG (2.7%). https://www.informs.org/Resource-Center/Video-Library/Edelman-Competition-Videos/2011-Edelman-Competition-Videos/2011-Edelman-Finalist-InterContinental-Hotels (industry body; snippet; page 404 on fetch)
86. Park Record, 2026-04-21, DestiMetrics Colorado+Utah split. https://www.parkrecord.com/2026/04/21/after-a-warm-winter-western-resorts-are-hoping-for-a-better-summer/ (trade)
87. ABC7, Airbnb total price default, 2025-04-22. https://abc7news.com/post/airbnb-will-now-show-total-prices-default/16216095/ (trade)
88. Avalara, FTC junk-fees rule for short-term rentals (2025). https://www.avalara.com/mylodgetax/en/blog/2025/1/new-federal-junk-fees-rule-requires-short-term-rentals-to-reveal-full-price-up-front.html (trade)
89. Cooley, FTC finalizes junk-fee rule (2024-12-20). https://www.cooley.com/news/insight/2024/2024-12-20-ftc-finalizes-junk-fee-rule-aimed-at-live-event-ticket-and-short-term-lodging-fees (practitioner; reviewer-supplied URL, not opened; content matches Avalara)
90. Amadeus Demand360 overview sheet, re-read for "alternative accommodation listings" (same document as #38; not double-counted in the 90 because #38 is already counted; this line records the re-read)

---

## Appendix C: Self-audit against 00_DEPTH_STANDARD.md

| MUST | Status | Evidence |
|---|---|---|
| Cite every non-obvious claim inline with URL and access date | **PASS** | Inline URLs throughout; one global access date (2026-10-16) stated in the header. Textbook claims carry full bibliographic references. |
| ≥40 distinct sources across ≥4 classes | **PASS** | 89 distinct sources across all 7 classes after revision (#90 is a re-read, not a new source): academic about 25 counted strictly (excluding the Leiden news page, with the CMU page replaced by the paper), textbooks 4 (cited via secondary works), vendor/patent 25, industry body 5, filings 2, official 2, trade and practitioner about 25 |
| Read primary sources; say so when paywalled | **PARTIAL (disclosed)** | Read in full: Garcia et al., SAS 2010, HSMAI 2018, DestiMetrics MDC, CRADR, ISHC, Heo, Das, Demand360 sheet, patents. Abstract only (paywall): Marriott and Carlson Interfaces, IHG (RePEc abstract), Schwartz & Cohen, the 2019 LOSC study, Zhang et al., and the revision additions (Wyndham, Nadarajah, Malasevska & Haugom, Weatherford & Pölt). **Webb et al. 2022:** this agent's fetch returned the data section and Table 1, but the reviewer saw only the abstract, so details beyond the abstract are flagged as single-read (Appendix D). Textbooks were not re-read this session. |
| Mark UNVERIFIED and STALE; no invented statistics or citations | **PASS (after revision)** | Labels applied, for example Marriott $150–200M and DFS/Aeronomics, current DestiMetrics coverage of Winter Park, the SAM −8.3% figures, PriceLabs' data source and bedroom buckets, and AirDNA's 4-month claim. Duetto–FLYR is now verified. No figure is invented. Engine numbers ($1,430 fees, $28 fee margin, $2,000 example, pace-noise table, power estimate) are arithmetic on the shared-context and candidate-config inputs. The review found 10 partial citations and one misattribution (Zhang via CMU); all were repaired (Appendix D). |
| Multi-pass search (broad, specific, adversarial) | **PASS** | 62 searches (log in Appendix A); adversarial queries #45, 52, 53, 57, 60 and critiques in §9 |
| Explain mechanisms at implementable depth | **PASS** | Bid-price LP and single-unit form (§1.3); pickup formulas (§2.2); control-function elasticity (§3.1); availability index (§5.2); owner-net math (§6.2) |
| Quantified impact, who measured it, conflicts | **PASS** | §9 table, plus VENDOR flags on each vendor claim |
| Map every finding to the engine (module plus owner-net measurement) | **PASS** | §10 transfer table; §11 lists module and measurement plan per item |
| Honest transferability (3 homes, thin data, LOS, groups, fees) | **PASS (after revision)** | §10 marks overbooking, open pricing and ML forecasting as non-transferable. The pace-noise math now accounts for stay clustering, and the market gain is stated as about 3×. The Garcia transfer now states the scale gap, deterministic caps, endogenous overrides and a power estimate. The 1-night benchmark was withdrawn. |
| "What generic STR pricers miss" (H2) | **PASS** | §10 subsection |
| Ranked recommendations with impact, confidence, effort, data and measurement | **PASS** | §11 |
| Open questions for the operator | **PASS** | §12 |
| Search log appendix | **PASS** | Appendix A |
| Recent (2020–2026) plus classics | **PASS** | 2021–2026: Garcia, Heo, Das, Webb, Koupriouchina, Zhang, 2026 briefings, Vail FY2025. Classics: Bitran & Mondschein, Weatherford & Kimes, Talluri & van Ryzin. |
| Extra adversarial pass if finished early | **PASS** | Antitrust, fairness, AirDNA limits, and the absence of independent RMS lift studies |

**Known gaps (honest):**
0. Reviewer-found misattributions, now repaired: Zhang et al. cited via a CMU page lacking the figures; Marriott DFS/Aeronomics attributed to an INFORMS page that does not say it; "Colorado+Utah" attributed to SGB (now Park Record); DestiMetrics prices framed "per year"; AirDNA "6–12 months" (the page says 6); PriceLabs "3+ BR bucket" and "blocked ≈ booked" (not on the page); HSMAI misused as evidence on RM failure at independents; the 2.7% IHG figure lacking a URL; "one third strategic" not qualified to the largest hotel.
1. Whether Winter Park is a **current** DestiMetrics participating destination is unconfirmed. Evidence is from 2016, plus the regional 2026 briefings.
2. DestiMetrics destination-subscription cost is unknown. Only property report prices are public.
3. No IDeaS-assigned patent was located.
4. Lighthouse's technical shop parameters (cache policy, shops per day) are undocumented publicly.
5. Hotel lift figures are company-reported, and no independent difference-in-differences study was found.
6. R2 does not estimate Winter Park seasonality (H5) or gas-price effects (H4). Those belong to R7.

## Appendix E. Response to review

Fix pass by the author (2026-10-17), consistency pass (2026-10-17), and close-out audit
(2026-10-19). The 2026-10-19 audit checked each fix against the body text and reopened the INFORMS
revenue-management history page (fix 10b).

| # | Status | What changed or why not |
|---|---|---|
| 1 | applied | §0.1, §2.3 and §5.2 use clustered effective n (home-nights ÷ LOS) and the small expected share at long leads. The 20–40-comp set is 2.6–3.7× more precise, or about 1.8× at today's valid-row rate. "10×" is kept only for a hundreds-of-listings full-market panel, with the product-mix caveat. §10 and §11 #1 rate the availability index Medium, not High. The "10×" sentence in §5.2 survived the author pass and was corrected in the 2026-10-17 consistency pass. |
| 2 | applied | §0.4, §3.1 and §11 #2: caps, deference and clamps give no identifying variation, and overrides are endogenous. 60,000 bookings against about 100. ψ = −0.38%/€ semi-elasticity. The 8.6× ratio and "supports −0.65" are removed, and the M1 clip at −0.3 is noted. #2 is recast as "log now, estimate later" with an SE(β) power figure and a Low-now rating. |
| 3 | applied | §0.4 and §6.2 item 2 compare 1-night all-in against competing 1-night all-in offers (Airbnb total-price default, April 2025; FTC rule). "$928 / 54%" is withdrawn. |
| 4 | applied | §6.2 item 4: 0.72 vs 0.595, about 21% more owner net per nightly dollar, 12.5 points of gross. The 3% processing rate is labelled an assumption. |
| 5 | applied | §6.2 states the owner fee margin of about $28 per stay. Option B is justified by guest acceptance, not avoided turn cost. |
| 6 | applied | H2 point 2 credits PriceLabs' min-stay relaxation and gap-blocking rules. Point 4 now separates displaying forward occupancy from using regime data as a pricing input, which is consistent with recommendation #4. The "~20% of nights" claim is replaced by a labelled assumption. |
| 7 | applied | §4 covers Amadeus Demand360/Agency360 and Lighthouse (Transparent, Market Insight) STR coverage. "No STR coverage benefit" and "not available for Winter Park" are removed. |
| 8 | applied | §2 and §11 #5 add the COVID test-window caveat, and #5 drops to Medium pending a backtest on our snapshots. |
| 9 | applied | §0.4 and §11 #2 use the candidate's peak β prior of −1.00 all-in and the M1 clip range [−2.5, −0.3]. |
| 10a | applied | Zhang et al. cited to 10.1287/mksc.2021.1295. |
| 10b | applied | The DFS label is gone. The audit reopened the INFORMS page: it does carry the Marriott lunch, Hanks, Aeronomics and Oktoberfest story (as folklore) and Holiday Inn 1992 / Club Med 1993. |
| 10c | partly | The late-override finding is cited to a Leiden University news summary of the thesis, labelled as non-peer-reviewed. The thesis itself was not opened. |
| 10d | applied | RoomPriceGenie is described as a base + market + occupancy skeleton with the vendor source, and the shoulder-discount rollout is noted. |
| 10e | applied | The Colorado+Utah split is cited to the Park Record (2026-04-21). |
| 10f | applied | DestiMetrics prices are one-off; "per year" is removed. |
| 10g | applied | AirDNA: six months (help page). The 4-month claim is marked snippet-only and UNVERIFIED. |
| 10h | applied | "Blocked ≈ booked" is marked UNVERIFIED for PriceLabs. The "3+" bucket is stated as the dashboard's coarsest bedroom filter. |
| 10i | applied | IHG 2.7% has the Edelman URL, marked as a snippet whose page returned 404. |
| 10j | applied | "74% of days with no update" is removed. |
| 10k | applied | "One third strategic" applies to the largest hotel only. |
| 11 | applied | Webb et al. is flagged: the author's single read of the data section is disclosed, and details beyond the abstract are marked single-read. |
| 12 | applied | §8 recasts HSMAI as new-metric adoption intent and adds the 27.2% "lack of usefulness" factor. |
| 13 | applied | Duetto–FLYR is verified (hospitalitynet 4134812), Duetto's HotStats acquisition is noted, the DestiMetrics season is Nov–Apr, and "March −17.1%" is UNVERIFIED and not used. |
| 14 | applied | Marriott One Yield/MORE, unconstraining and censoring, Wyndham choice-based pricing (+3.5% / +5.2%, company-measured), Nadarajah et al. (multi-night MDP) and Malasevska & Haugom (ski-lift pricing) are added. |
| 15 | applied | Appendix C rates "Read primary sources" PARTIAL with the Webb disclosure and lists the misattributions under known gaps. |
