# R3 review: Price optimization across other industries

Reviewer: adversarial reviewer (V). Date: 2026-10-16. Dossier: `docs/research/deep_2026-10/R3_cross_industry_rm.md` (~17,000 words).
No code edits; this file is the only write.

## Verdict: ACCEPT WITH FIXES

This is a strong dossier. It covers the four starred industries, it uses primary filings and papers,
it states its own gaps, and it corrected its own Oasis error in the open. I found no fabricated
citation. Of 24 dossier citations checked, 17 supported the claim fully, 7 partly, none failed to
support it and none were dead (row 25 in section B is a cross-check, not a dossier citation). The
headline numbers that bear the most weight check out: Vail 2026/27 pass sales (units −12%, dollars
−6% through 2026-09-18), Huang's 26% / 90% / 56% / +1.7% counterfactual, the CMA undertakings, and
Rue La La's 9.7% [2.3%, 17.8%].

Four reasoning faults have to be fixed before S1 builds on this dossier:

1. **The M1 exploration premise is wrong for the engine under review.** The "~1% of price per SD"
   figure uses default priors and skips the all-in conversion. With the current candidate it is
   about 3–4% (A3, C1).
2. **Comp-fill identification is overclaimed.** The 20,000 comp listing-nights are observational,
   not randomized arms, so SE ≈ 0.08 says nothing about bias. Huang, a source the dossier read in
   full, finds that prices are endogenous in exactly this kind of calendar-scrape data (C2).
3. **Recommendation 1 is tied to the wrong gap.** The −6.6% gap comes from the reference level
   (anchor), not from how price responds to pace (C3).
4. **Recommendation 5's "−38% avoided loss" cites the wrong cause.** It is attributed to an
   owner-cost objective, but OVERHAUL blames hard peak caps and low ceilings (C4).

The dossier also missed several things my own searches found: a causal study of pass pricing
effects on overnight stays, Amazon's primary price-experimentation paper, the RealPage
settlement terms, California AB 325, Colorado HB25-1090 and the critique of the SFpark elasticity
(section E).

## A. Repo claims checked against the code

| # | Dossier claim | What the code says | Result |
|---|---|---|---|
| A1 | Pace index at 120 days: one booked night moves it 0.37 to 0.73 (§3.3) | `src/pricing/pace.py:53-55` `index = (on_books + 0.05)/(expected + 0.05)`; `DEFAULT_CURVE[120] = 0.12`; `DEFAULT_FINAL_OCCUPANCY["peak_ski"] = 0.70`; `window_days: 3` in the candidate. T = 0.084; 0.05/0.134 = 0.373; (1/21 + 0.05)/0.134 = 0.729 | **Correct.** Two caveats the dossier should add: (a) the denominator is nights with status `available` or `booked` only, so owner blocks shrink it below 21 and make the jump larger; (b) the price consequence is what matters: with `sensitivity 0.30`, `min_multiplier 0.85`, the multiplier goes 0.85 (clamped) to 0.919, an 8% price jump from one booking, and a second booking takes it to 1.025 (another +12%). Say that in dollars. |
| A2 | M1 Thompson σ = 0.35/√(40+n) at `src/pricing/__init__.py:94` | Line 94: `scale = 0.35 / (40.0 + n) ** 0.5`. Explore is off when `demand_strength >= 0.85` (line 504-511) | **Correct** location and formula. |
| A3 | One SD of exploration moves price about 0.95% (§10.2) | Arithmetic is right for the inputs used (β = −1.70, linear demand, `unconstrained_optimum = P_ref(β−1)/(2β)`, `src/pricing/__init__.py:36-39`). But the inputs are wrong for the engine under review: (i) the current candidate `config/policies/candidates/pace_v3_anchor_repair.yaml` overrides the priors to peak −1.00 and others −1.10, not −0.65/−1.70; (ii) with `beta_is_all_in: true` the prior is first scaled by `all_in_beta` (`price/(price + 357.5)` at typical party 10, LOS 4), so at $2,000 the working β is −0.85 (peak) or −0.93. Reviewer recomputation, one SD at n = 0: **±3.3–3.8% at peak, ±2.9–3.3% shoulder** at $2,000; ±3.8–4.4% at $1,200. Under the *default* policy peak prior (−0.65 → −0.55 all-in) it is ±5.9% (and the optimum sits at 1.41 × P_ref, so it is usually clamped). | **Wrong as stated.** "~1%, nearly certainty-equivalent, will not learn" overstates the case. The real exploration is 3–4% per SD before move caps, which is comparable to the ~9% three-week comp drift noted in `pace.py:145`. The CVP recommendation may still be right, but its premise must be redone with the candidate's priors and the all-in conversion. |
| A4 | M4 orphan penalty = 0.5 × nightly | `docs/research/MODEL_SPEC.md:64`: "minus `0.5 * nightly` for each orphan night" | **Correct.** |
| A5 | `lift_ticket_window_usd` field exists in `src/signals/collectors/resort.py` | `resort.py:50` FieldSpec(0–500 USD); also parsed in `src/signals/extractors/winter_park_resort.py:72-75` | **Correct**, but the dossier's top signal idea (§11.2, "Winter Park dated lift-ticket prices ... the collector field exists") overreaches: the field is a single *window* price scraped from the resort page, not a per-future-date price curve. "It is also the cheapest: the collector field exists" is misleading; a dated-price scraper of the ticket store is new work with ToS questions (the dossier's own Q4 in §14). |
| A6 | Elasticity SE ≈ 0.72 at 225 nights/arm, ≈ 0.08 at 20,000 (§10.2) | Delta method: Var(ln r̂_hi − ln r̂_lo) ≈ 2(1−p)/(np); ÷ ln(1.1/0.9)² = 115.9/n. Reviewer: SE = 1.08, 0.72, 0.30, 0.076 | **Arithmetic correct.** The inference drawn from the last row is not (see C2): the 20,000 comp listing-nights are not randomized arms, so the SE is a variance bound for an estimator that is biased by price endogeneity. |
| A7 | Hierarchical weight ≈ 0.15 with v = 0.5, τ = 0.3 (§10.3) | (1/0.5)/(1/0.5 + 1/0.09) = 0.153 | Correct and consistent with A6 (0.72² ≈ 0.52). |
| A8 | Gallego–van Ryzin n = 1 reduction `p* = 1 + log(1 + λ*t)` (§10.1) | J*(1,t) = log(1 + λ*t), J*(0,t) = 0, so p* = 1 + log(1 + λ*t) | Correct. Minor: step 2 calibrates λ*t as arrivals "at the reference price" while GvR's λ* is the rate at the static price 1/α, which equals P_ref only when β = −1 (the candidate's peak prior happens to be near that). State the assumption. |

## B. Citation spot-check (25 checks, all accessed 2026-10-16/17)

| # | Source | Claim checked | Result |
|---|---|---|---|
| 1 | S02 Vail Q4 FY2026 (TradingView/PRN) | Units −12%, days −10%, $ −6% through 2026-09-18; destination lower-frequency weakness; CO/UT locals "modest improvement"; visits 15.30M −13.4%; lift rev −3.5%; ETP $94.85; condo RevPAR $105.39 / ADR $393.60 | **Supports** (verbatim) |
| 2 | S01 Vail Q1 FY2026 | 2.3M advance-commitment guests, ~$1B, ~74% of visits; units −2%, $ +3%, ~7% price; local drive-to decline; month-ahead lift-ticket discount; Epic Friend | **Supports** |
| 3 | S03 Vail 10-K FY2025 | ~65% of lift revenue from passes; ~82% in Q2+Q3; "some of the highest prices for single day lift tickets"; snowfall affects pass sales; Epic Coverage | **Supports** (all five quotes found, in Risk Factors) |
| 4 | S35 Huang 2021 (PDF text extracted by reviewer) | Revenue-max prices "26% below the baseline prices"; occupancy "jumps up to 90%"; "56% sellers are worse-off"; platform profit "1.7% above the baseline"; seller 8% below baseline; elasticity −2.51; "platform sets price variation but gives sellers the final decision right to determine the price levels" | **Supports.** Nuance missed: Huang's seller costs are the *opportunity cost of time per night* (median $37/night against a $150 median price) for SF private rooms and studios with min stay < 3, not a turnover or cleaning cost. The dossier's "per-booking cost" wording (§2.2) is loose (see C4). |
| 5 | S34 Filippas et al. (IDEAS abstract) | Centralized pricing raised utilization and revenue; non-price adjustments (availability, cancellations, exit); partial control gets similar gains with less reaction | **Supports.** The abstract does not name the platform; the "rental-car" label rests on Huang, as the dossier says. |
| 6 | S20 CMA case page | Undertakings signed 2025-09-15, published 2025-09-25; tiered pricing; 24h notice, queue info, no misleading labels, two years of reporting | **Supports.** The case was opened to look at "dynamic pricing" and the CMA made no finding of breach. The dossier's correction is accurate. |
| 7 | S42 SFMTA release | 60–80% band; target met "31 percent more often"; meter rates −$0.11/h (−4%) | **Supports** |
| 8 | S42 Pierce & Shoup (UCLA page/PDF) | 62% of blocks in band after two years; elasticity −0.4 | **Partly.** −0.4 is confirmed through JAPA 79(1) secondary records. I could not confirm 62% (the PDF is images). "Independent academic evaluation" is doubtful: Shoup is the intellectual originator of performance parking. The elasticity is disputed (E6). |
| 9 | S70 SKI Magazine Ikon 2026/27 | 100% refund with no scans by 2027-01-15, 50% with one scan | **Partly.** The refund applies to the separate "Ikon Pass Refundable" / "Base Refundable" products (Ikon "What's New" page), and SKI says "skiers who buy insurance". The dossier presents it as a general pass feature (§11.2, §12.5). The price also rises "about $70 to $1,349 with renewal discount ($1,399 new)" against a 2025/26 price of $1,329, so "+5%" holds only for new buyers. |
| 10 | S13 Ikon pre-season savings | Winter Park up to 50% off 4+ nights, deadline Aug 28, Early Ups, $100 credit | **Supports.** Also two lift tickets at 35% off. The season is not shown, as the dossier says. |
| 11 | S27 Ferreira, Lee, Simchi-Levi (MIT DSpace) | 9.7%, 90% CI [2.3%, 17.8%]; no sales loss on recommended increases for medium/high-price items | **Supports** |
| 12 | S41 Blake et al. (reviewer extracted the published PDF) | Upfront fees reduce quantity and quality; quality ≥ 28% of the revenue decline | **Supports.** The "~21%" figure the dossier marks UNVERIFIED is in the published paper: the drip group "spend almost 21% more" (Table 3). Remove the flag. |
| 13 | S10 Royal Caribbean Q2 2026 transcript | "about 20 million and growing price points"; "a couple of points below, a couple of points above"; "for close-in demand, we're able to increase our pricing"; "price integrity"; booking closer in | **Supports** (verbatim) |
| 14 | S22 Sweeting (reviewer extracted the UMD PDF) | Prices fall "40% or more"; DP raises seller payoff ~16% | **Partly.** Within-seller declines are "13%, 18% and 40%" at successive relistings. 40% is the end point, not a floor, so "or more" overstates. The 16% is supported. |
| 15 | S25 Castillo, Econometrica | +2.15% total welfare; riders +3.57%; drivers −0.98%; platform −0.50% | **Supports** |
| 16 | S24 Cohen et al., NBER w22627 | ~50M observations, RD design, $2.9B in four cities in 2015 | **Supports** ("observations", not "sessions") |
| 17 | S17 PeakRankings, Liftopia | ABC sale to Skitude; creditors Alterra, Aspen, A-Basin, Mountain Collective; mega-pass pressure; "Dec 7", no year | **Supports** (the report is itself marked unconfirmed by PeakRankings) |
| 18 | S47 Six Flags 8-K exhibit 2025-09-12 | +298k visits from promotions; per-capita in-park spending −4% attributed to volume promotions | **Partly.** The release does not say the 298k visits came *from* promotions. The −4% ($2.50) is entirely a 7% drop in admissions per capita, and in-park *product* spending per capita rose slightly. So the lesson is "discounts lowered the ticket yield", not "discounted guests spent less in the park". |
| 19 | S72 Inntopia | Monthly briefing; on-the-books for 6 months; ~28,000 units in 17 communities | **Supports** |
| 20 | S31 Keskin & Zeevi (Duke record) | √T with no prior information; log T when expected demand at an incumbent price is known | **Supports** |
| 21 | S40 FTC rule, Federal Register | Short-term lodging and live-event tickets; effective 2025-05-12; total price shown more prominently | **Supports.** I could not confirm "covers third-party platforms" in the part of §464.2(f) I read, so mark it partial until quoted. |
| 22 | S53 Morning Paper on Ye et al. | Zero loss inside [L, U]; [P, c₂P] booked, [c₁P, P] unbooked; PDR and booking regret; KDD'18 | **Supports.** The dossier rightly dates the paper KDD 2018, not 2015 as the prompt says. |
| 23 | S43 CIO, Giants/Qcue | 2,000 seats in 2009; park-wide in 2010; $7M | **Partly.** The article says "Revenues increased $7 million last season" and does not credit all of it to Qcue; the CIO says the impact "can be tough" to quantify. The dossier's caveat is right; tighten it to say the source itself does not attribute the gain. |
| 24 | S66 Alnes & Haugom (IDEAS) | Asymmetric framing effect; larger gap lowers fairness; ski industry | **Supports** for JRCS 81. The "1,627 skiers, revenge" claim comes from the second (Aalto) item, which I did not check. |
| 25 | Ikon "What's New 2026/27" (lifted.ikonpass.com, used to check S70/S71) | Refund mechanics | Shows that the refund belongs to the "Refundable" product (see #9) |

Tally: **17 support / 7 partly / 0 do not / 0 dead or fabricated** (row 25 is a cross-check, not a
dossier citation). The partial results are nuance and overstatement, not invention.

## C. Reasoning problems

**C1. The M1 exploration premise (A3).** The dossier concludes that M1 "is nearly
certainty-equivalent and will not learn" because one SD moves price ~0.95%. That holds only for the
default shoulder prior (−1.70) with no all-in scaling. The candidate the dossier is reviewing
(`pace_v3_anchor_repair.yaml`) uses −1.00 / −1.10, and `apply_models` scales β by `all_in_beta`
before drawing (`src/pricing/__init__.py` around line 487). The result is 3–4% per SD. Over
~100 decisions a season that is real price dispersion, comparable to the comp-anchor drift. The
conclusion may still hold, because 3–4% dispersion with SE ≈ 0.7 still identifies little, but it
has to be argued from the power table, not from "~1%".

**C2. Comp-fill identification (§10.2, Rec 2, transfer rows 14–15).** "Comp-market transitions
can [identify elasticity] if the scraper works" does not follow from the SE table:

- Comp prices are set *in response* to demand. Hosts raise prices on nights they expect to sell, so
  an available→unavailable regression on ask is biased toward zero or even positive elasticity.
  Huang, using the same kind of SF calendar data, finds "prices are endogenous to demand shocks"
  and needs a control function. The dossier read Huang in full and does not carry this over.
- Huang's data section is a ready-made precedent for separating owner blocks from bookings
  (nights unavailable from the start are treated as "blocked"). Practitioner scrapers use the same
  snapshot-differencing method (E7). Cite it, and design the estimator around an instrument or a
  control function, not raw transitions.
- Comps' fills estimate a market-level or other-listing response. They are not the own-price
  elasticity of Cloud 9 against its substitutes.

State the bias and name an identification strategy (instrument, control function, or
discontinuities in comps' own rule-based pricing) before ranking this "Medium-High".

**C3. Rec 1 mapped to the −6.6% gap.** OVERHAUL says the gap is "behind at peak on price, not
volume (ADR $2,052 vs $2,246), mostly Cloud 9". That is a *level* problem: the anchor, the Cloud 9
premium, the holiday price. Band control changes how price *responds* to pace and does not obviously
raise the peak level. It may even hold price flat inside the band where today's multiplier would
lift it. The −6.6% also comes from the 5-seed screen of the older `pace_learned_owner_net`
candidate, not the current `pace_v3_anchor_repair`. Rec 1 should claim lower volatility and robust
pace response. It should not claim to close the peak gap unless a simulator run shows that.

**C4. Rec 5 and transfer row 10, "avoided loss (the simulated default engine was −38%)".** OVERHAUL
§Phase 3 gives the root causes as "the hard peak caps, and a ceiling and reference price built from
the season's own (initially low) prices". It does not name a gross-RevPAN objective. The Huang link
is an analogy. In addition, Huang's cost is per-night time cost for small SF units. For our homes
the $600 cleaning fee is passed to the guest, and the owner-side cost is `turnover_cost_per_stay`
($350 in the candidate) net of the fee margin. That makes the margin in `owner_terms` small (about
$7 a night at typical party and LOS). The Huang mechanism therefore transfers weakly here. Restate
the expected impact as "guards against a known failure class", and drop the −38% attribution.

**C5. Cruise forecasting used as a control argument.** S39's "additive pickup beats
multiplicative" is a *forecast accuracy* result. Using it to argue for an additive pace *control*
gap is reasonable but is an analogy, and should be labelled as one. The ratio-fragility argument
(A1) stands on its own arithmetic.

**C6. SFpark used as independent support for band control.** The source has a conflict of interest
(Shoup), the elasticity is disputed (E6), and the reported convergence to the band is small
(Millard-Ball et al.: each rate change moves a block 0.1–0.2% closer to target). The band-control
*structure* still transfers. The evidence of effectiveness is weaker than §3.3 implies.

**C7. Lift-ticket signal ranked as the "cheapest" night-level edge (§11.2).** The existing field is
one window price (A5). A dated price curve is new collector work, probably under ToS limits (open
question 4), and Alterra's date prices may track its own lodging forecast rather than home demand.
The "how to test" cell is fine. Fix the effort and the claim that the field already exists.

**C8. Simulator-only measurement for presentation and trust recommendations (Recs 1, 10, 17).**
The calibration-v2 simulator has no reference-price, volatility or fairness response, so it cannot
reward "price integrity". The dossier half-admits this in Rec 11. The measurement plans for Recs 1
and 10 should say that the simulator cannot detect the claimed trust benefit, and should name the
field proxy: guest-visible price changes per booked night against inquiry-to-book conversion, in
aggregate.

**C9. Pass-sales lead claims.** "2–9 months" lead and "destination low-frequency = our segment" are
reasonable, but Epic says nothing directly about Ikon/Winter Park. Fix 5 below asks for the Falk &
Scaglione evidence, which shows pass-price effects on overnight stays can be large for domestic
guests and zero for foreign ones. That segment split matters for a Front Range drive-up market (H4).

## D. Depth audit (reviewer's own check of each MUST)

| MUST | Reviewer finding |
|---|---|
| Inline citations + access date | PASS. One global access date; acceptable. |
| ≥ 40 distinct sources | PASS: 79 IDs. Many are read only at **A** (abstract) or **S** (secondary) level: about 22 F, 30 A, 27 S by my count of Appendix A. |
| ≥ 4 source classes | PASS: 1 = 36, 2 = 2 (neither re-read), 3 = 7, 4 = 1, 5 = 10, 6 = 2, 7 = 21. Class 4 (industry body) is thin, with one Cornell item. Nothing from NSAA directly, and no AGIFORS or INFORMS RM&P talk on non-airline RM. |
| Primary sources read | PARTIAL, honestly declared. Key papers (Keskin–Zeevi, den Boer–Zwart, Rue La La, Li & Pang) were read at abstract level, yet their mechanisms are relied on (the CVP schedule). |
| UNVERIFIED / STALE marking | PASS, with one flag to remove (Blake 21%) and flags to add (Ikon refund product, SFpark 62%, Sweeting "or more"). |
| No fabrication | PASS. None found in 25 checks. |
| Broad / specific / adversarial passes | PASS: 63 searches. The adversarial pass is real (§12). |
| Mechanisms with math | PASS: band control, bid prices, GvR, power, pooling, reference price. |
| Quantified impact with conflicts | PASS, apart from SFpark "independent" (C6). |
| Map to modules + owner-net measurement | PASS in form. Weak for Recs 1, 5 and 10 (C3, C4, C8). |
| Honest transferability | Mostly PASS. C2 is the main failure: comp-market learning is presented as the escape from thin data without addressing endogeneity. |
| H2 note | PASS (§1.5, §9.1, §11.3, including where specialization does not help). |
| Ranked recs / open questions / self-audit | PASS. The self-audit is too generous on "Map every finding" and "Honest transferability". |
| Search log | PASS. |
| Prompt-specific: transfer table, ski signals table | PASS. |

## E. Coverage gaps and material the author missed (reviewer searches, 17 run)

Missing or thin against the prompt's "Cover at minimum" list:

- **Ticketmaster Platinum**: named in the prompt, absent from the dossier. **NBA/NFL** dynamic
  pricing: absent; MLB only.
- **Disney park reservations**: prompt item; only date-based tickets are covered.
- **Evolve**: prompt item; absent. Later **Airbnb/VRBO** work: thin (one job posting). There is no
  Airbnb engineering-blog material after 2018.
- **Car rental**: one-way pricing and event surges are thin. Hertz–Amadeus is UNVERIFIED.
- **Vail investor-day materials**: the prompt asked for them; only the 10-K and releases are used.
- **Window-rate inflation**: covered only as $356 peak window prices. There is no time series of
  window prices against pass prices.

Found by reviewer searches (the dossier reports not finding most of these):

1. **Pass pricing → overnight stays (causal).** Falk & Scaglione, "Effects of price model copycats
   in the ski industry", *Tourism Analysis* (2021). This is a DiD across 59 Swiss destinations over
   2012/13–2017/18: the Magic Pass raised *domestic* overnight stays by about 31% and had no effect
   on foreign stays. An earlier Saas-Fee study (*Tourism Review* 2018, doi 10.1108/TR-08-2017-0133)
   found about +50% for Swiss residents and about +17% for total stays.
   https://openarchive.usn.no/usn-xmlui/handle/11250/2740344 ; https://arodes.hes-so.ch/record/7511/files/Published%20version.pdf .
   It directly answers the dossier's search Q18 "no study found" and bears on the
   drive-market vs destination split.
2. **Overnight share of US skier visits.** SnowBrains, citing NSAA/Kottke, puts it at about 45.9%
   (2016/17) and 38.8% (2025/26). This is secondary and UNVERIFIED, but it is a trend directly
   relevant to lodging demand under mega-passes. https://snowbrains.com/the-future-of-skiing/ .
   NSAA 2025/26 preliminary: 52.6M visits; season passes 49% of visits.
   https://www.saminfo.com/news/sam-headline-news/u-s-skier-visits-drop-14-in-2025-26-amid-weak-western-snowfall
3. **Alterra pass numbers.** None published; confirmed again. Ikon full pass $1,329 (2025/26) to
   $1,349 renewal / $1,399 new (2026/27). https://gazette.com/?p=1444992 ; S70.
4. **Amazon primary source.** Cooprider & Nassiri, "Science of price experimentation at Amazon",
   *Business Economics* (2023), and the Amazon Science blog (2023-04-14). Amazon randomizes *products
   over time*, not customers (non-discriminatory pricing), and uses crossover designs and trend
   controls. That is directly relevant to experimenting on three homes without showing two prices
   at once. https://amazon.science/publications/science-of-price-experimentation-at-amazon ;
   https://amazon.science/blog/the-science-of-price-experiments-in-the-amazon-store
5. **RealPage settlement.** DOJ proposed final judgment of 2025-11-24, no admission of liability.
   It bars real-time use of competitors' nonpublic data, allows only nonpublic training data at
   least 12 months old, bans sub-state geographic models, requires removing features that limit
   price decreases, and imposes a monitor. Public data remains allowed.
   https://www.fenwick.com/insights/publications/dojs-realpage-settlement-a-blueprint-for-safer-algorithmic-pricing ;
   https://www.cpr.org/2025/11/25/rent-algorithm-limits-settlement/ .
   **California AB 325** (signed 2025-10-06, effective 2026-01-01) bans using a "common pricing
   algorithm" in an anticompetitive combination.
   https://pillsburylaw.com/en/news-and-insights/ab-325-shared-pricing-algorithms-liability-california.html .
   Both strengthen §12.3 and should replace "RealPage not checked".
6. **SFpark critique.** Millard-Ball, Weinberger & Hampshire, JAPA 79(4):330–336 (2013), and
   *Transportation Research A* (2014), "Is the curb 80% full or 20% empty?". They find much smaller
   effects: each rate change moves a block 0.1–0.2% closer to target.
   https://ideas.repec.org/a/taf/rjpaxx/v79y2013i4p330-336.html ;
   https://millardball.its.ucla.edu/wp-content/uploads/sites/22/2022/06/Millard-Ball_Weinberger_Hampshire_2014_Assessing_the_impacts_SFPark.pdf
7. **Calendar-scrape sale inference.** Practitioner methods distinguish blocks from bookings by
   snapshot differencing, with known failure modes (host blocks created after the first scan). No
   peer-reviewed validation was found. https://help.seetransparent.com/listing-nights-in-depth .
   Together with Huang's data section, this is the method base for Rec 2.
8. **DEN car-rental prices as a signal.** No study or dataset found; only anecdotes (Christmas SUV
   quotes doubling close in). A better public proxy may be DEN's monthly passenger traffic reports
   (official, monthly, https://www.flydenver.com/). The dossier should compare the two.
9. **Colorado HB25-1090** (effective 2026-01-01). It is a state total-price ("junk fee") rule for
   businesses generally, enforced as a deceptive trade practice. How it applies to STRs is
   unconfirmed. It belongs next to the FTC rule in §10.5.
   https://www.denver7.com/news/politics/new-colorado-state-laws-going-into-effect-thursday-for-the-start-of-2026

Reviewer searches run (17): Pierce–Shoup elasticity; Blake abstract; RealPage settlement; Alterra
pass numbers; mega-pass lodging effect (extended); Amazon pricing paper; DEN rental-car ski prices;
Wallimann/Saas-Fee; Amazon Science price experiments; Kottke overnight share; Ikon 2026/27 refund;
Airbnb calendar inference; DEN passenger statistics; Magic Pass DiD; California AB 325;
Millard-Ball SFpark critique; Colorado HB25-1090.

## F. Numbered fix list

1. **Redo the M1 exploration arithmetic (§10.2, Rec 6)** with the candidate's priors (−1.00 / −1.10)
   and the `all_in_beta` scaling. Report about ±3–4% per SD at n = 0, and argue for or against CVP
   from the power table, not from "~1%".
2. **Rewrite the comp-fill identification claim (§10.2 conclusion, Rec 2, rows 14–15).** State the
   price-endogeneity bias, cite Huang's control-function finding and blocked-night rule, and name an
   identification strategy. Lower confidence to "Low" until the strategy exists. Keep the SE table,
   but caption it "variance only, assumes exogenous prices".
3. **Re-scope Rec 1's expected impact.** The −6.6% peak gap is a level and anchor gap from an older
   5-seed screen. Claim volatility and robustness benefits, and require a paired run on the current
   `pace_v3_anchor_repair` before claiming any part of the peak gap.
4. **Fix the Rec 5 / row 10 attribution.** OVERHAUL blames the −38% on peak caps and low
   ceiling/reference, not a gross objective. Also note that Huang's cost is per-night time cost for
   small units, and that our owner-side turnover margin is small after the fee pass-through.
5. **Add Falk & Scaglione (Magic Pass DiD, +31% domestic overnights, 0 foreign) and the Saas-Fee
   study to §1.4 and §11.2,** and remove "no study found". Use the domestic/foreign split to
   sharpen the Epic destination vs local inference.
6. **Correct the SFpark treatment (§3.3, §8):** Shoup is not independent; add the Millard-Ball
   et al. critique; mark "62% in band" UNVERIFIED or cite the page.
7. **Correct the Ikon refund (§11.2, §12.5):** it belongs to the "Refundable" product variants
   (insurance per SKI). Price change: $1,329 to $1,349 renewal / $1,399 new.
8. **Correct the lift-ticket signal effort (§1.3, §11.2, Rec 3):** the existing field is a single
   window price; dated prices need a new collector, subject to ToS.
9. **Correct Six Flags (§5, row 23):** the −4% is admissions yield; in-park product spending rose;
   the 298k visits are not attributed to promotions.
10. **Correct Sweeting:** "about 40% by the last relisting (13%, 18%, 40%)", not "40% or more".
11. **Remove the Blake 21% UNVERIFIED flag;** the figure is in the published paper (Table 3).
12. **Replace "RealPage settlement not checked" (§12.3, Appendix C)** with the 2025-11-24 DOJ terms
    and California AB 325. Add Colorado HB25-1090 to §10.5.
13. **Add the Amazon primary source** (Cooprider & Nassiri 2023) to §7, along with its transferable
    idea: randomize over time with crossover designs. That may be the only feasible experiment
    design for three homes, so link it to Rec 6.
14. **Fill the coverage gaps:** Ticketmaster Platinum; NBA/NFL; Disney park reservations; Evolve;
    Vail investor-day material; a short window-price vs pass-price time series.
15. **For Recs 1, 10 and 17,** state that the v2 simulator cannot measure trust or volatility
    effects, and name the aggregate field proxy.
16. **Label the S39 additive-forecast argument as an analogy (C5).** In §3.3, give the price
    consequence of the pace jump in dollars (0.85 → 0.92 → 1.03 multiplier for 0 → 1 → 2 bookings)
    and note that owner blocks shrink the 21-night denominator.
17. **Compare DEN passenger traffic (official, monthly) with rental-car quotes** as the cheaper
    fly-in demand proxy in §2.3.
18. **Revise the self-audit (Appendix C):** "Map every finding" and "Honest transferability" should
    read PARTIAL until fixes 2–4 are made. Report the F/A/S read-level counts.

## Addendum: scoped re-review, 2026-10-19

The 2026-10-17 "Response to review" listed resolutions, but the dossier body had not been edited.
The close-out audit applied fixes 1–13 and 15–18 to the body; fix 14 (coverage gaps) is not done.
This addendum is a consistency check by the same audit, not an independent review.

- Top-5 changes: Rec 1 no longer claims the −6.6% gap; Rec 2 drops to Low until an identification
  strategy exists; Rec 5's −38% is attributed to peak caps and low ceilings. These are the changes the
  review asked for.
- The M1 exploration figure (about 3–4% per SD) was re-derived from `pace_v3_anchor_repair.yaml` and
  `src/pricing/__init__.py`: 3.5% peak and 3.0% other at $2,000.
- Falk & Scaglione was confirmed by search (Tourism Analysis 26:71–75, 2021); Cooprider & Nassiri by its
  abstract page. One correction to this review: the 62% SFpark in-band figure is in the later UCLA
  two-year brief, so R3 now cites it there instead of marking it UNVERIFIED.
- Cross-reference errors fixed: the comp-fill estimator is Recommendation 2, not 3.

Verdict unchanged: ACCEPT WITH FIXES, fixes applied except item 14 (ledger in R3 Appendix D).
