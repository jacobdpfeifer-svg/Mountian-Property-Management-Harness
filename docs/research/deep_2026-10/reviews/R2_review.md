# R2 review: Hotel and resort RM (`docs/research/deep_2026-10/R2_hotel_rm.md`)

Reviewer: adversarial V pass. Date: 2026-10-16. All URLs were accessed on 2026-10-16.
Inputs read: `V_REVIEW.md`, `00_DEPTH_STANDARD.md`, `00_SHARED_CONTEXT.md`, `00_FIELD_NOTES.md`, `R2_HOTEL_RM.md`, the dossier, and, to check the engine claims, `src/pricing/pace.py`, `docs/research/MODEL_SPEC.md`, `config/policies/default.yaml` and `config/policies/candidates/pace_learned_owner_net.yaml`.

## Verdict: ACCEPT WITH FIXES

This is a strong dossier. I found no fabricated citation. The load-bearing academic results check out against the primary text: Garcia et al., Heo et al., the DestiMetrics 2016 sheet and the CRADR deck. The engine-mapping is unusually concrete. Several problems still need fixing before S1 relies on it:

- The headline statistical argument ("market pace is ten times more precise") rests on an independence assumption and a 300-listing comp slice that our own recommendation (20–40 comps) contradicts.
- The Garcia et al. transfer overstates how identifiable elasticity is with our data and design.
- The 1-night all-in "must fall to $928" benchmark compares the wrong products.
- One owner-net figure is mis-stated: direct versus OTA is +21%, not +12%.
- A dozen citations only partly support the sentence they are attached to.
- Some named "cover at minimum" items are missing (Marriott One Yield/MORE, Agency360), as is the closest published vacation-rental RM case.

None of this needs a rewrite. It needs targeted corrections.

---

## 1. Depth audit (each MUST checked independently)

| MUST | Reviewer finding | Status |
|---|---|---|
| Inline URL plus access date for non-obvious claims | Inline URLs are nearly everywhere. Access dates are given as one global date in the header, which is acceptable. Some claims carry no source: the "about 20% of nights carry most revenue" claim (§10, H2 note), the 3% direct card processing figure (§3.3), and the "comparable to stay-extension upsells" remark, which is self-flagged. | PASS with gaps (Fix 6, Fix 4) |
| ≥40 sources, ≥4 classes | 74 listed. Reclassify on recount: Leiden news (#22) and the CMU news page (#16) are not academic work; Ye (#15) is cited via a video page and a blog. Textbooks (#23–26) were not read and are cited via secondary works. Even after this the counts stay above the bar: academic ≥18, vendor/patent 25, trade 15, industry body 4, filings 2, official 2. | PASS |
| Read primary sources; disclose paywalls | Garcia, Heo, SAS 2010, HSMAI, MDC and CRADR were genuinely readable, and I verified them. **Webb et al. 2022 is paywalled (abstract only)**, yet the dossier gives specific findings from it (1,826 curves, a 109-room hotel, "multiplicative is zero when OTB = 0", the 60-day threshold, Pölt) without saying so. The dossier's own self-audit marks this MUST "PARTIAL". | PARTIAL (Fix 11) |
| UNVERIFIED / STALE labels; nothing invented | Labelling is good overall. Two misfires: Duetto–FLYR is marked UNVERIFIED but is now confirmed (Hospitality Net 4134812; Hotel Tech Report), and the "Colorado+Utah vs rest of West" split is attributed to a source that does not contain it. | PASS with fixes (Fix 10e, 13) |
| Multi-pass search | A 62-row log with genuine adversarial queries (antitrust, fairness, AirDNA critique, missing DiD studies). | PASS |
| Mechanisms at implementable depth | Bid-price LP and its single-unit form, additive/multiplicative pickup, the Heo pooling formula, the control-function estimator, the availability index and the owner-net algebra are all present. | PASS |
| Quantified impact with conflict flags | §9 table plus VENDOR tags. Good. | PASS |
| Map every finding to a module plus an owner-net measurement | §10 and §11 do this, with simulator plus signals-ladder plans. | PASS |
| Honest transferability | Mostly good (overbooking, open pricing and ML are rejected). The Garcia transfer and the market-pace precision claim are not honest enough. See §4 below. | PARTIAL (Fixes 1–2) |
| H2 note | Present, but two of its five points are overstated against the cited PriceLabs source. | PASS with fixes (Fix 6) |
| Ranked recommendations, open questions, self-audit | Present. Expected impact is qualitative only. Acceptable, since the dossier says so explicitly. | PASS |
| Search log | Present. | PASS |

## 2. Citation spot-check (25 cited URLs opened; PDFs text-extracted where WebFetch could not read them)

Tally: **13 support, 10 partly support, 1 does not support, 1 dead/403, 0 fabricated.**

| # | Source (as cited) | Claim checked | Result |
|---|---|---|---|
| 1 | Garcia, Tolvanen & Wagner, CESifo WP 9127 (ifo.de PDF; full text extracted) | 9 hotels (8 resort), ~50 rooms, ~14 months, ~60k bookings, >5M obs; +€3 → −1%; ψ ≈ −0.0038; ~55% markup; pass-through 0.101 (Table 4); 52.2% accept-all-week; Table 13 hotel 175 winter −0.49 (n.s., SE 0.29), summer −2.42, off-season −4.22; Table 10 lead-time pattern; DiD −1.20; naive DS gives "often positive or very small" coefficients; Hausman IV gives "mostly positive" | **Supports**, with three errors. (a) The gloss "pp of booking probability per euro" is wrong: the tables report "semi-elasticities in p.p." scaled on average booking probability, and the median ψ is −0.38% per euro. (b) "About one third strategic" applies to "the biggest hotel in our sample" only. (c) "About 74% of days had no update" (§8) is not in the extracted text. |
| 2 | Heo, Viverit & Pereira 2023 (PMC10007649) | 32 rooms; MAPE 23.9→4.6% (28d) and 11.9→3.1% (14d) | **Supports** the numbers. **Omits** that the test window is 1 Jul–15 Sep 2020 (COVID). The authors say the booking pattern "changed significantly" and that historical data "has little value". One hotel, about 77 check-in dates. |
| 3 | PriceLabs Market Dashboards help | $9.99/dashboard/month; daily refresh; future occupancy, pickup, last-year lines; bedroom filter | **Partly.** Price, refresh and charts are supported. The "3+ BR bucket" is **not** on the page (it says "your desired bedroom count"), and neither is "calendar-inferred, blocked ≈ booked". The marketing page (hello.pricelabs.co/market-dashboard) says pricing "starts at $9.99 for a 1k-listing report", so it may be tiered. |
| 4 | DestiMetrics property report packs | Individual prices; packs of $925, $1,250 and $2,000 | **Partly.** The prices are right. The "per year" framing (§5.1, §5.2 table) is not on the page, and the page states no participation prerequisite. |
| 5 | DestiMetrics MDC sheet (2016) | Winter Park under MTNWEST; "participation in the RAO is a prerequisite"; 6+6 months | **Supports** (STALE, correctly labelled) |
| 6 | CRADR deck (2016) | Winter Park Central Reservations a charter member (of 26); DestiMetrics and Inntopia associate members; $900 dues; monthly reservation reports | **Supports** |
| 7 | SGB July 2026 | 17 destinations in 7 states; Colorado+Utah split | **Partly.** 17/7, the 51.1-day lead and the >$401 luxury tier are supported. **No Colorado+Utah split** appears in this article. |
| 8 | Snowsports News May 2026 | Winter −7% occupancy, +1.2% ADR; April lead 56.4 days | **Supports.** The season is Nov–Apr, not Nov–Mar (§5.1 table). |
| 9 | SAM "Strong Fall Precedes Slow Winter" | −8.3% / −6.9% / −17.1% | **Dead (403).** My search could not confirm these figures. They are already flagged UNVERIFIED, but §5.1 then uses "March −17%" as its worked example. |
| 10 | Sky-Hi News 2026-03-24 | −7% countywide, >10% Fraser/WP/Silvercreek, provider unnamed | **Supports** |
| 11 | Baker McKenzie (Gibson v. Cendyn) | 2025-08-15 affirmance; DOJ amicus | **Supports** (the URL redirects; the claim is confirmed by Baker McKenzie and Inside Class Actions) |
| 12 | CMU Tepper news (Zhang et al.) | Price −5.7%, revenue +8.6% | **Does not support.** The page has neither figure. The figures are in the paper itself: *Marketing Science* 40(5):813–820, https://pubsonline.informs.org/doi/10.1287/mksc.2021.1295. |
| 13 | Koushik et al. 2012 (RePEc) | $145M to date; ~$400M/yr projected; PERFORM inputs | **Supports.** The 2.7% figure is not in the abstract; it is attributed to "Edelman materials" with no URL. |
| 14 | Koupriouchina et al. 2023 (RePEc) | 20,081,973 forecasts; 1,752 hotels; group+/transient−; events+ | **Partly.** "Late overrides more favourable" is not in the abstract. |
| 15 | RoomPriceGenie occupancy strategy | Target curve; 80% default; Long window; Low aggressiveness; shoulder discounts | **Partly.** All of these are supported, but "Price = base + market factor + occupancy factor" is not on the page, and shoulder discounts were live on only ~10% of properties. |
| 16 | HSMAI/SIT 2018 (PDF extracted) | 953 respondents (27.2%); 77.4/48.5/20.4/13.7; 53.2% missing costs/profit | **Partly.** The figures are correct. **Misused** in §8: 17.8% "organizational constraint" and 55.2% vs 44.5% describe intent to adopt *new metrics*, not "why RM fails at independents". The top negative factor (perceived lack of usefulness, 27.2%) is omitted. The sample is Asia-Pacific. |
| 17 | Webb et al. 2022 (Emerald) | 1,826 curves; 109 rooms; multiplicative failure; 60-day threshold; Pölt | **Partly.** The page is abstract-only and none of these details are visible. The abstract supports only "booking-window shifts degrade accuracy". |
| 18 | INFORMS RM history | Folklore lunch; Hanks/Aeronomics/Oktoberfest; Holiday Inn 1992; Club Med 1993 | **Partly.** All of these are supported, but "Marriott's DFS built with Aeronomics ... by rate and LOS" is **not** on the page; its only "DFS" is Decision Focus Inc. |
| 19 | PriceLabs orphan gaps | 20% default | **Supports**, but the same page also documents min-stay relaxation to the gap length and "smart check-in/check-out" gap blocking, which undercuts H2 point 2 (Fix 6). |
| 20 | US20130006712A1 (Amadeus) | Competitor average plus market-influencer parameters; "one or two BAR levels" | **Supports.** The BAR-levels language is in the description, not claim 1. |
| 21 | US6263315B1 (Talluri) | Time × capacity threshold tables; sum-of-thresholds rule; robustness | **Supports** |
| 22 | Vail FY2025 10-K | 11% of revenue; ~5,000 units; RevPAR $170.70, ADR $325.65, 52.4% occupancy; 20% Epic discount | **Supports** |
| 23 | Key Data, Winter Park | PMS-direct reservations plus VRBO/Airbnb | **Supports** |
| 24 | AirDNA help, future bookings | Pacing 6–12 months; weak beyond 4 months | **Partly.** The page says **six months**, and it does not contain the 4-month claim. That claim relies on a 403 page (snippet only). |
| 25 | Amadeus Demand360 overview sheet (PDF extracted) | >44,000 providers; 12 months forward; updated 5 days a week; GDS air data | **Supports**, but the same sheet says Demand360 tracks "forward-looking availability of alternative accommodation listings". Amadeus also claims 35M STR properties. This contradicts §4 ("Not available for Winter Park homes") and §11 #10 ("no STR coverage benefit"). |

## 3. Arithmetic checks (against the shared context and the candidate config)

| Claim | Check | Result |
|---|---|---|
| F = $1,430 at 10 guests | 600 + 75×10 + 80 | Correct, provided the $75 is per guest per stay, which is how `pace.py` treats it |
| All-in table at p = $2,000 | 3,430 / 2,715 / 2,476.7 / 2,357.5 / 2,204.3 | Correct |
| 1-night all-in ≈ 45% above a 4-night stay | 3,430 / 2,357.5 = 1.455 | Correct |
| Orphan break-even $928 (−54%) | 2,357.5 − 1,430 = 927.5 | Arithmetic correct; **benchmark wrong** (Fix 3) |
| Option B value $833 | 1,400 × (1 − 0.155 − 0.25) | Correct |
| "Direct worth about 12% more to the owner per nightly dollar" | Owner share 0.72 (direct, 3% processing) vs 0.595 (Airbnb): **+21%** owner net. The 12.5 points is the gap per gross dollar. | **Wrong as stated** (Fix 4). The 3% figure is also unsourced. |
| "Direct 10% lower still nets more" | 0.9 × 0.72 = 0.648 > 0.595 | Correct |
| ±11pp pace noise | √(0.25/21) = 0.109 | Arithmetic correct; **assumption wrong** (Fix 1). `on_books_share` counts home-nights in ±3 days across the portfolio and excludes blocked nights, so n ≤ 21. Those nights are filled in multi-night blocks (typical LOS 4), so the effective sample is about 21/LOS ≈ 5–8 stays and the real SE is closer to ±0.18–0.22. At long leads the expected share is small (0.12 × 0.70 ≈ 0.08 at 120 days), so the index (ratio) noise is far larger than the ±7% quoted. The conclusion, that own pace is too noisy, gets *stronger*, but the numbers are wrong. |
| Market pace SE 0.011 ("ten times more precise") | Assumes 300 independent large-home listings. Recommendation #1 shops 20–40 comps, so n = 140–280 listing-nights, about 35–70 effective stays after clustering, giving SE ≈ 0.06–0.08. With 67% scrape failure it is worse still. | **Overclaimed.** On the planned comp set the gain is roughly 2–3×, not 10×. |
| Fee pass-through to owner | With the candidate config, K = 350 + 75×10 + 80 = $1,180; F(1−c) − K = 1,208 − 1,180 ≈ **$28 per stay** | The dossier never states this. It matters for Option B ("no turn cost") and for the §6.2 agency point: per-stay fees roughly cover per-stay costs, so new stays are not costly to the owner. The case for Option B therefore rests on guest willingness to pay, not on avoided cost. |
| Peak β "the engine uses −0.65" | The default is −0.65; the **current candidate** (`pace_learned_owner_net.yaml`) uses −1.00 peak with `beta_is_all_in: true` | Outdated (Fix 9) |

## 4. Reasoning problems

1. **The Garcia transfer is overstated** (§3.1, §10 row, §11 #2). Their identification uses *inattentive, exogenous* lags in following the RMS, with 60k bookings and 5M price observations; it took 9 × 256 GB supercomputing nodes. In our engine, move caps (±12% / $250), deference and floor/ceiling clamps are **deterministic functions of the recommendation and the prior state**. Conditional on f(r) and the cap state, they produce no residual variation. Only operator approval lag (if it is random) and manual overrides (which are likely endogenous: the operator knows things) remain. With about 100 reservations, the estimator will be noise. Garcia's units (a semi-elasticity in pp of booking probability) also cannot be compared directly with the engine's β (an elasticity on an all-in price at about $2,000, against Garcia's €80–210 rooms). "Supports an inelastic peak prior" is a units mismatch, and the 8.6× ratio divides by a non-significant estimate. Note too that M1 is clipped to [−2.5, −0.3] (MODEL_SPEC), so it cannot turn positive. Its bias shows up as pinning at −0.3, which means pushing toward the ceiling. That is worth saying because it ties to a known engine failure.
2. **Market-pace precision.** See §3. The 10× claim drives the "High" ratings on recommendations #1 and #4 and the §10 statement that forward OTB is "the most valuable hotel input for us".
3. **The 1-night benchmark compares the wrong products.** Airbnb has shown total trip prices by default since April 2025, and the FTC's December 2024 rule requires total-price display for short-term lodging. A guest searching one night compares *one-night* all-in prices across listings that also carry per-stay fees. They do not compare against our own 4-night per-night price. The relevant question is whether 1-night demand for a 16-sleeper exists at any price that clears owner net, not whether it can match $2,358. The "54% cut" conclusion (§6.2, §10, and H2 point 2) does not follow.
4. **Heo et al. as "the most directly transferable" result.** The 5× MAPE gain comes from a COVID-disrupted 2020 summer at one Elba hotel, where the classic method's prior-year pickup was broken by design. That is a regime-shift test, not a steady-state one. It is still useful, but it needs that caveat and a backtest on our own `pacing_snapshots` before any Medium-high confidence rating.
5. **H2 note, points 2 and 4.** PriceLabs does more than flat discounts: it relaxes min-stay to the gap length and offers gap-blocking check-in/out rules (its own orphan page, which the dossier cites). Point 4 says mountain forward OTB is "absent from the documented inputs of every pricer reviewed". Yet the dossier's own recommendation #4 is to use PriceLabs' forward-occupancy dashboard. Rephrase it as "not used as a pricing input", and verify that.
6. **The Demand360 dismissal rests on a false premise.** Amadeus markets STR coverage (35M properties) and tracks alternative-accommodation availability. A Demand360 subscription may still be poor value for three homes, but the dossier should say *why* (contract, contribution requirement, cost, Winter Park depth) rather than "no STR coverage".
7. **HSMAI §8 misuse.** The survey is about adopting new *metrics* in Asia-Pacific. It is not evidence on why RM fails at independents.

## 5. Coverage gaps against R2's "Cover at minimum"

| Item | Status |
|---|---|
| 1. Marriott **One Yield / MORE** | **Missing**: named in the prompt, absent from the dossier. Hilton is thin (one IDeaS press release; GRO is not explained). |
| 2. Unconstraining methods | Thin. The concept is defined, but there is no algorithm (projection detruncation, EM, or the simple booking-curve fill used on sold-out nights). It matters because our booked nights are censored by min-stay rules and blocks. |
| 4. **Agency360** | **Missing.** Pace/FLYR is thin. Lighthouse's STR data line (the Transparent acquisition, 2022, https://www.hospitalitynet.org/news/4109377.html; Market Insight forward demand) is not covered, even though it is a candidate STR forward source. No IDeaS patent was found; I could not find one either (two searches, including on Google Patents), so that disclosure is fair. |
| 5. "How much each is worth" (forward OTB vs comp rates) | Thin. Only the vendor's +2.3% figure. There is no attempt to value the input in our own simulator terms. |
| 6. Channel cost optimization | Adequate. It misses Duetto's 2025 HotStats acquisition, which is the clearest industry move toward profit (GOPPAR) benchmarking (https://hoteltechreport.com/news/duetto-acquires-flyr). |
| 7. Alterra lodging; destination pricing tied to lift and snow; packaging | Thin: ownership history only for Alterra, and one 2010 Austrian panel for snow. No ski-lift dynamic-pricing evidence (Malasevska & Haugom 2018, *Tourism Management* 64:291–302, https://ideas.repec.org/a/eee/touman/v64y2018icp291-302.html). |
| 9. Evidence: closest STR analogue | **Missing:** "Choice-Based Dynamic Pricing for Vacation Rentals", *INFORMS J. Applied Analytics* (https://pubsonline.informs.org/doi/10.1287/inte.2021.1075; abstract via search, page 403). A conditional-logit booking model with rolling-window price sensitivity plus a booking-curve heuristic, on Wyndham Destinations vacation rentals, reporting +3.5% and +5.2% revenue per unit in two regions (2018). This is the most transferable published RM case for us. |
| Multi-night single-room DP | **Missing:** Nadarajah, Lim & Ding, "Dynamic pricing for hotel rooms when customers request multiple-day stays" (SMU working paper, 2015; https://ink.library.smu.edu.sg/lkcsb_research/5147). An MDP for one room type with multi-day requests; fluid/ALP heuristics beat single-day decomposition by up to 7%. Directly relevant to the stay-level bid-price recommendation (#3). |
| Fee-inclusive display regime | **Missing:** the FTC junk-fees rule for short-term lodging (finalized 2024-12-17; https://www.cooley.com/news/insight/2024/2024-12-20-ftc-finalizes-junk-fee-rule-aimed-at-live-event-ticket-and-short-term-lodging-fees) and Airbnb's total-price default (April 2025; https://abc7news.com/post/airbnb-will-now-show-total-prices-default/16216095/). Both bear on the all-in elasticity math in §6.2. |
| Local forward-occupancy lead | Partly. The "ask the Tourism Board" recommendation is good. Grand County Tourism Board agendas (https://visitgrandcounty.com/?p=5979) carry Chamber lodging reports, and Sun Valley publishes a monthly fact sheet of the same kind (https://visitsunvalley.com/wp-content/uploads/2026/01/Sun-Valley-Area-Monthly-Fact-Sheet_12.31.2025.pdf). Cite these as evidence that boards share such data. |

Reviewer searches run (19): Garcia MS paper; DestiMetrics −8.3% winter; Zhang Smart Pricing (×2); Gibson v. Cendyn; Lighthouse/Transparent STR; Demand360/Agency360 STR; Duetto–FLYR 2026; STR gap-night optimization papers; FTC junk-fee rule; Airbnb total-price display; IDeaS patents (×2, incl. Google Patents domain); Winter Park DestiMetrics 2025; independent RMS adoption causal studies; Malasevska ski pricing; Airbnb elasticity IV studies; Key Data pricing; single-unit LOS DP papers (×2, incl. Wyndham paper lookup).

## 6. Numbered fix list

1. **Redo the pace-noise math (§0.1, §2.3, §5.2).** Account for clustering of home-nights within stays (effective n ≈ home-nights / mean LOS) and for the small expected share at long leads. Recompute the market SE for the *planned* 20–40-comp set after scrape failure. Replace "ten times" with the corrected ratio, and revisit the "High" ratings on §10's forward-OTB row and §11 #1 and #4 if needed.
2. **Rewrite the Garcia transfer (§0.4, §3.1, §10 row, §11 #2).**
   - Say that our caps, deference and clamps are deterministic in the recommendation, so only random approval lag gives identifying variation; manual overrides are likely endogenous.
   - State Garcia's scale (60k bookings) against ours (~100).
   - Correct the unit gloss: semi-elasticity in pp, median ψ = −0.38%/€. Drop "supports −0.65" and the 8.6× ratio of a non-significant estimate.
   - Note the M1 clip at −0.3.
   - Recast #2 as "log (recommended, listed, booked) now; estimate once the simulator shows adequate power". Add a power calculation to its measurement plan, and lower the impact rating until that exists.
3. **Fix the 1-night benchmark (§0.4, §6.2 item 2, §10 gap row, H2 point 2).** The comparison is 1-night all-in against competing 1-night all-in offers (Airbnb has shown total trip prices by default since April 2025; FTC rule of December 2024), not against our own 4-night per-night price. Keep the LOS-specific `all_in_beta` point, which is right, but drop "must fall to $928 / 54%" as a requirement.
4. **Correct the direct-channel figure (§6.2 item 4):** +21% owner net per nightly dollar (0.72 vs 0.595), or 12.5 points of gross. Source the 3% processing cost or label it an assumption.
5. **State the owner fee margin.** Under the candidate config, F(1−c) − K ≈ $28 per stay. Adjust Option B's justification (it is about guest willingness to pay and acceptance, not avoided turn cost) and the §6.2 item 3 agency discussion.
6. **H2 note:** rewrite point 2. PriceLabs relaxes min-stay to the gap and offers gap-blocking check-in/out, per the cited page. Rewrite point 4 so it is consistent with recommending PriceLabs' forward-occupancy dashboard. Source the "~20% of nights" claim or drop it.
7. **Demand360 and Lighthouse:** remove "no STR coverage benefit" and "Not available for Winter Park homes". Cite Amadeus' STR and alternative-accommodation claims, and give the real reason not to buy. Add Lighthouse's STR data (Transparent, 2022) and Market Insight as a candidate forward source, with cost status. Cover **Agency360**.
8. **Heo et al.:** add the COVID 2020 test-window caveat (one hotel, ~77 check-in dates). Lower #5's confidence until it is backtested on our own snapshots.
9. **Engine facts:** the candidate's peak β prior is −1.00, all-in (`pace_learned_owner_net.yaml`), not −0.65. Mention the M1 clip range.
10. **Citation repairs:**
    - (a) Zhang et al.: cite the paper (10.1287/mksc.2021.1295), not the CMU news page.
    - (b) Marriott DFS/Aeronomics: re-source it (Cross 1997, or Hanks, Cross & Noland 1992) or mark it UNVERIFIED; the INFORMS page does not say it.
    - (c) Koupriouchina "late overrides": cite the thesis or full text, or remove it.
    - (d) RoomPriceGenie "base + market + occupancy": cite a page that says it, or rephrase; note the ~10% rollout of shoulder discounts.
    - (e) The Colorado+Utah split: find the briefing that says it or remove it.
    - (f) DestiMetrics "per year": remove; the page gives one-off prices.
    - (g) AirDNA: the help page says six months; mark the 4-month claim snippet-only.
    - (h) The PriceLabs "3+ BR bucket" and "blocked ≈ booked": not on the cited page; source or mark UNVERIFIED.
    - (i) IHG 2.7%: give the Edelman URL.
    - (j) Garcia "74% of days with no update": give the table or page, or remove.
    - (k) "One third strategic": qualify as the largest hotel only.
11. **Webb et al. 2022:** mark it abstract-only (paywalled) and remove or flag every detail not in the abstract.
12. **HSMAI in §8:** reframe it as new-metric adoption intent (Asia-Pacific) and add the 27.2% "lack of usefulness" factor. Find real evidence on RM failure at independents, or say none was found.
13. **Labels and dates:** Duetto–FLYR is now verified (https://www.hospitalitynet.org/news/4134812, 2026-10-08); also note Duetto's 2025 HotStats acquisition under §6. Change the DestiMetrics season to Nov–Apr. Stop using "March −17.1%" (UNVERIFIED) as the §5.1 worked example.
14. **Fill the coverage gaps:**
    - Marriott One Yield/MORE.
    - An unconstraining algorithm, and how censoring by min-stay and blocks affects our data.
    - The Wyndham vacation-rental choice-based pricing case (inte.2021.1075; +3.5%/+5.2%, measured by the company: medium credibility). Add it to §9 and §10.
    - Nadarajah, Lim & Ding's multi-night single-room MDP as the formal basis for recommendation #3.
    - Ski-lift dynamic-pricing evidence (Malasevska & Haugom 2018) under §7.
15. **Self-audit:** change "Read primary sources" to PARTIAL with the Webb disclosure. Add the reviewer-found misattributions to "Known gaps".
