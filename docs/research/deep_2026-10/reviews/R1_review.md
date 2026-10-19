# R1 review: airline RM dossier

Reviewed: `docs/research/deep_2026-10/R1_airline_rm.md` (about 17,900 words, 88 bibliography entries).
Reviewer: adversarial review per `docs/prompts/DEEP_RESEARCH_2026-10-16/V_REVIEW.md`. Date: 2026-10-16.
Inputs read: V_REVIEW, 00_DEPTH_STANDARD, 00_SHARED_CONTEXT, 00_FIELD_NOTES, R1_AIRLINE_RM, `docs/research/MODEL_SPEC.md`,
`src/pricing/pace.py`, `src/bookprob/__init__.py`, `src/compose/__init__.py` (grep), `proving_ground_exam/market/{shoppers,scoring,competitors,world,choice}.py`,
`proving_ground_exam/scenarios/price_war.yaml`, `config/portfolio/mont_luxe.yaml`, `docs/plans/OVERHAUL_2026-10-14.md`.

## Verdict: **ACCEPT WITH FIXES**

The dossier is deep, well organized and mostly honest about evidence quality. It flags STALE, VENDOR and
UNVERIFIED items, and every engine reference it makes exists in the repo. No citation is fabricated. But its
headline equation, and the claim that equation is built on, are stated more strongly than the math allows in
the engine's own setting (findings A–D below). One source (COAT) is reported as supporting R6 when the same
paragraph argues against part of R6's design. One URL points to the wrong thesis. Several prompt items are thin.
R1 (the bid price) and R6 (the switchback) are its two top recommendations, so these errors must be fixed before
S1 uses them.

---

## 1. Depth audit (MUSTs checked independently)

| MUST | Reviewer finding | Status |
|---|---|---|
| Inline citation + access date | Inline `[Sn: URL]` throughout, with one global access date. S61 has no URL ("seen in search results … not fetched"). | PASS (minor: S61) |
| ≥ 40 distinct sources | 88 entries (S1–S87 + S50b). | PASS |
| ≥ 4 classes | Reviewer count from §13: class 1 ≈ 56 (incl. mixed), class 2 = 3, class 3 ≈ 9, class 4 = 4, class 5 = 1 (only "as reported"), class 6 = 5, class 7 ≈ 11. At least 6 classes have real content. | PASS |
| Read primary sources | Depth column: **full 12, partial 1, abstract 28, biblio 5, summary 41**. Nearly half the sources (41/88) were seen only as search-engine summaries, including open-access MIT DSpace theses (S12, S28, S29, S53) and arXiv papers (S7, S84, S86) whose full text is freely available. Two of the three errors in §2 below come from summary-only sources. Textbooks (S14, S80, S81) were not read; the §1.7 DP content is "from memory". | **PARTIAL** (self-audit says PARTIAL PASS; reviewer agrees but rates it worse) |
| UNVERIFIED / STALE / no fabrication | Labels used consistently; no fabricated citation found. But Boyd & Kallesen is marked "could not locate" when it is indexed (IAOR 63773), and S53's URL is the wrong thesis (see §2). | PASS with fixes |
| Multi-pass search (broad/specific/adversarial) | Appendix A: 73 queries, B/S/A labels, 4 rate-limited. | PASS |
| Mechanisms with implementable math | Strong: Littlewood, EMSR-a/b, DAVN LP, DP, EM steps, Fiig transformation, capacity-1 recursion, PODS WTP, ROM. The pass-through claims are wrong in the engine's units and model (findings A–C). | PASS with fixes |
| Quantified impact + who measured | Thorough, with conflict notes. Misses Fetcherr's own 6–9% claim (§2, #18). | PASS |
| Map to engine modules + owner-net measurement | Every module named exists: `src/compose`, `src/bookprob`, `src/pricing/pace.py` (`comp_anchor`, `own_sold_evidence`, `owner_terms`, `all_in_beta`, `ANCHOR_MAX_AGE_DAYS`), `src/pacing`, `src/min_stay`, `src/leakage`, `src/elasticity`, `src/experiments`, `src/eval`, `src/review`, `src/explain`. M3, M4 and M5 are described exactly as in MODEL_SPEC. | PASS |
| Honest transferability | Good "does not transfer" list. Weak spot: R6's switchback is declared transferable without dealing with advance-purchase timing (finding E). | PASS with fixes |
| "What generic STR pricers miss" (H2) | §11, rests on PriceLabs public posts, defers to R4. | PASS |
| Ranked recs with impact/confidence/effort/data/measurement | Present (R1–R10). Impact ranges are unexplained priors, and no rec says how big an effect the field test could detect (finding F). | PASS with fixes |
| Open questions, self-audit, search log | Present. | PASS |

## 2. Citation spot-check (25 opened; 15 required)

| # | Source | Claim checked | Result |
|---|---|---|---|
| 1 | S26 Cooper, Homem-de-Mello, Kleywegt, *OR* 54(5):968–987 | spiral-down over repeated flights | **Supports** |
| 2 | S69 Talluri, Castejón, Codina, Magaz (UPF wp 1196, full PDF) | alternating weeks; 9 months ÷ 4 systems ≈ 9 weeks each; 52-week-prior normalization; Easter deleted; "within-model" quote | **Supports.** The paper also flags analyst observer bias and chose Monday–Sunday blocks to limit round trips that cross arms. The dossier should carry the observer-bias point into R6. |
| 3 | S50 Atlanta News First (Delta/Fetcherr) | "~3% of domestic fares … target 20% by end-2025" | **Partly.** The article says 3% of domestic *flights*. The 20% figure is quoted from an advocacy group, with no date. Other reports put "3% of fares, 20% by end of 2025" in Hauenstein's mouth on the Q2-2025 call (e.g. constellationr.com, eplaneai.com), so the claim is probably right but the cited source does not carry it. |
| 4 | S24 Fiig et al. 2010 (full PDF) | f_M → 1/b "price elasticity cost"; HF 10–16%; DAVN-MR ≈ +16%; LF 85→72–74%; duopoly 10–13% / 9–14%; "not a zero-sum game" | **Supports** |
| 5 | S37 Wittman, Fiig, Belobaba 2018 (full PDF) | 5–7% over traditional RM; joint DPE < 1% over independent | **Supports** |
| 6 | S25 Belobaba 2004 deck (full PDF) | LF 74.6→77.8%, revenue −15%, RM share 5→8%+, "spiral down", "manual overrides" | **Supports** |
| 7 | S12 Williamson 1992 | no network gain below ~85% LF; 2–4% above | **Supports** ("non-existent" below 85%) |
| 8 | S84 COAT, arXiv 2607.14318 (full PDF) | "2023 pilot rejected customer-level randomization, used test-vs-control markets — consistent with randomizing time blocks not guests" | **Misrepresented.** The test-vs-control markets and the fairness reason are correct. But the same passage says: *"Temporal alternating between AI pricing and legacy pricing was rejected due to the advance-purchase nature of airline bookings … Year-over-year comparisons were also unsuitable."* Those are R6's two pillars. Also: IBM Research, July 2026; the pilot was ancillary seat-upgrade pricing, 17 weeks, +6.9% upsell per booking, evaluated by synthetic control; "2023" is the end of the training data, not the pilot date. |
| 9 | S86 arXiv 2206.04424 (full PDF) | French rail RM "up to 16.2% below optimal dynamic" | **Partly.** D'Haultfœuille, Wang, Février, Wilner. The abstract says only "substantial losses". The 16.2 the reviewer found is a social-welfare figure (observed SW = 16.23 in Table 6), not a revenue gap. Table 6 revenue: 12.21 observed vs 13.44–14.70 under the stopping-time strategy, a 9–17% gap. Likely misread; fix the number and cite the table. |
| 10 | S38 Szymański, Belobaba, Papen 2021 | CP up to 2.0% first mover, 1.2% both | **Supports** |
| 11 | S11 Talluri & van Ryzin 1998 | not optimal in general; asymptotically optimal; constant over time; non-unique | **Supports** |
| 12 | S72 Wang et al. 2021 (Wyndham) | +3.5% / +5.2% revenue per unit, two regions, part of 2018 | **Supports** |
| 13 | S64 Koupriouchina et al. 2023 | 20,081,973 forecasts, 1,752 hotels, 232 chains; overrides help group, hurt transient, help events | **Supports** |
| 14 | S56 Cohen et al. 2023 | 5,000-itinerary field experiment; quality-adjusted ladder gives a smoother, more profitable path | **Supports** (abstract gives no %) |
| 15 | S18 Lee 1990 | 10% accuracy → 0.5–3.0% revenue | **Supports** |
| 16 | S65 Zeni 2003 | US Airways; analysts add up to 3% | **Supports** (JRPM 2(1):37–46) |
| 17 | S58 Baker McKenzie on *Gibson v. Cendyn* | 9th Cir. Aug 15 2025; independent adoption not §1; DOJ amicus | **Supports** |
| 18 | S48 Aviation Week (Fetcherr) | "significant increases in revenue; no audited %" | **Partly.** The article does quote Fetcherr's own claim that it "can boost revenue 6–9%". The dossier omits that vendor number; it belongs in the §5.4 VENDOR table. |
| 19 | S46 PROS WTP case study | +4.7%, six routes, three markets | **Supports** (fetched page was a listing; confirmed via the PROS case text in search: ~$1.5M, $5B+ airline) |
| 20 | S13 Gallego & van Ryzin 1994 | closed form for exponential demand; fixed price asymptotically optimal; prices rise with less stock | **Partly.** The first two are in the abstract. The direction of monotonicity is not in the abstract (it is in the paper, so this is acceptable). |
| 21 | S53 dspace 1721.1/60708 | matching losses 9.2% / 3.4–8.5% / network vs leg | **Does not support (wrong URL).** 60708 is D'Huart (2010), "A competitive approach to airline revenue management", whose abstract has none of these figures. The figures match the abstract at **dspace.mit.edu/handle/1721.1/42054**. Fix the URL and attribution. |
| 22 | S85 Bacon, Reuters Events | "2–5% … they don't actually measure this gain" | **Dead.** Redirects to the events.reutersevents.com home page; the quote cannot be checked. Find an archive copy or mark UNVERIFIED. |
| 23 | S87 Li, Granados, Netessine 2014 | 5.2–19% strategic | **Supports** (5.2%–19.2%, first–third quartile across markets, *Mgmt Sci* 60(9):2114–2137). The dossier leaves out the paper's counterfactual: strategic consumers do not necessarily hurt revenue, and committing to non-decreasing prices can hurt leisure markets. That bears directly on §3.5. |
| 24 | S15 Weatherford & Pölt 2002 | 2–12% revenue from better unconstraining | **Supports** (abstract via IAOR/search; Springer paywalled). The 60–80% censoring detail was not confirmed. |
| 25 | S74 Zhang, Mehta, Singh, Srinivasan 2021 | Smart Pricing −5.7% price, +8.6% revenue | **Partly.** Rotman coverage confirms lower prices and "nearly 9%" revenue. The 5.7% was not confirmed from an accessible page. |

**Tally (25):** supports 16 · partly 6 · does not support 1 (wrong URL) · misrepresented 1 · dead 1 · fabricated 0.

## 3. Math and code verification

- **pace.py arithmetic: correct.** `PaceReading.index = (on_books+0.05)/(expected+0.05)`, `pace_multiplier = clip(1+0.30(index−1), 0.85, 1.25)`, `DEFAULT_CURVE[120] = 0.12`, `DEFAULT_FINAL_OCCUPANCY.peak_ski = 0.70`, `min_history = 60`. One booking in a 3-home × 7-night window adds 1/21 = 0.048 to the index numerator; 0.048/0.134 = 0.355; × 0.30 = 10.7%. The "±11%" stands.
- **Linear demand form: correct.** `bookprob`: `p = p_ref(1 + β(P/P_ref − 1))`, the same as the dossier's form.
- **BP/2 derivation: algebra correct.** Maximizing (P − BP)·p(P) gives P* = P_ref(β−1)/(2β) + BP/2. The reviewer reproduced it numerically (pass-through 0.50).
- **Capacity-1 recursion: correct.** `V_k = max_p q_k(p)π(p) + (1−q_k(p))V_{k−1}`. The argmax equals argmax q_k(p)(π(p) − V_{k−1}), V is non-decreasing in time remaining, and BP → 0 at arrival. "M3 is a bid price in disguise" is algebraically right (pP + (1−p)C = p(P−C) + C).

**Finding A: under exponential WTP, pass-through is 100% only when arrivals are sparse.** `p* = BP + 1/b` holds for Poisson intensity λ(p) = a·e^{−bp} (Gallego–van Ryzin; Fiig's continuous limit). The dossier's own §4.4 bucket model, `q_k(p) = 1 − exp(−Λ_k·S(p))`, saturates. The reviewer's numeric check (b = 1/600, BP = $600, pure exponential S):

| Λ_k (expected interested parties per bucket) | 0.01 | 0.1 | 0.5 | 1 | 3 | 10 |
|---|---|---|---|---|---|---|
| Pass-through of BP to price | 0.99 | 0.87 | 0.59 | 0.44 | 0.27 | 0.17 |

The markup is also not 1/b once Λ is non-trivial. The high-Λ nights (Christmas, holiday weeks) are exactly where §3.4, §4.4 and R1 promise the bid price "holds price far out", and there pass-through is weakest. The 100%-vs-50% contrast in §3.4 therefore does not decide the model choice. The choice depends on Λ.

**Finding B: unit mismatch.** π(p) is owner net, `share·p + margin`, with `share = 1 − 0.155 − 0.25 = 0.595` (`owner_terms()`). An owner-net BP moves the optimal **nightly rate** by BP/(2·0.595) ≈ 0.84·BP under linear demand, not BP/2. Under exponential demand with sparse arrivals it moves it by about 1.65·BP, not 1·BP (reviewer numeric check). M3's `C = q(floor+ceiling)/2` is in nightly-rate units, so "replace M3's C with V_{k−1}" needs an explicit unit conversion.

**Finding C: the PODS WTP template has a kink.** `P(WTP ≥ f) = min(1, exp(…))` is flat below basefare. With base $1,500 and 1/b = $600, the optimum sits on the kink for any BP up to about $600, so pass-through is 0. If this form becomes the engine's S(p), the optimizer will pile up at the comp anchor. Use a smooth form, or say so.

**Finding D: the bid price does not fix the "peak always at ceiling" problem; it makes it worse.** BP ≥ 0 always raises p*. Under the current β = −0.65 linear model, P* = 1.27·P_ref + BP/2, so the price moves further above the ceiling. Two claims are therefore wrong: §0 item 2 ("it also fixes the 'peak always at ceiling' degeneracy") and §3.4 item 3. What can fix it is the **demand-model change** (a finite WTP distribution S(p) that falls steeply above market quotes). The recursion does not. These are two separate changes, and R1 currently bundles them. Measure them separately.

**Spiral-down mapping overclaims.** OVERHAUL_2026-10-14 reports the own-sold blend at $332.8k vs $340.7k from **5 seeds, one season each**. A single-season simulation cannot show the repeated-flight spiral that Cooper et al. model. What it shows is a self-referential reference price. "This already happened in our engine" (§3.2) and "cost ~$8k simulated per season" (R4) should become "the same risk; a 5-seed screen, significance not shown".

**Simulator claims check out.** `shoppers.py:75` uses `rng.poisson(mean)`. Competitor agents (`static_owner`, `market_follower`, `generalized_tool`, undercutter via `undercut_factor`; `price_war` sets the factor to 0.80) and the mixed logit with an outside option exist as described. One caveat: `scoring.hindsight_revenue` is a greedy **gross** WTP bound that ignores competitors, so the ROM in §9.3 needs an owner-net hindsight before "perfect = hindsight_revenue in owner-net terms" is true.

## 4. Coverage gaps against the prompt's "Cover at minimum"

| Prompt item | Status | Gap and material found by reviewer |
|---|---|---|
| 1 History | Good | Sabre as a business is only mentioned. Minor. |
| 2 Forecasting | Good; "multiplicative ranks worst" mostly supported | Weatherford & Kimes (2003): booking curve and combination methods were "fairly inaccurate" on Choice data; Weatherford (1998): additive beats multiplicative. Later work agrees: a 2011 cruise-line JRPM study found multiplicative significantly worse, and Ellero & Pellegrini (2014) found additive best in Italian hotels. Missed recent work: Heo, Viverit & Pereira, *JRPM* 2023, extended additive pickup (https://link.springer.com/article/10.1057/s41272-023-00421-1); Fiori & Foroni (2020) extended multiplicative pickup with GLMs. Caveat the dossier skips: these rankings score *forecast error*, while `pace.py` uses the ratio as a *price signal*, so the transfer is an inference. |
| 2 Unconstraining | Good, but misses the most relevant method | **Vulcano, van Ryzin & Ratliff, "Estimating primary demand for substitutable products from sales transaction data", *OR* 60(2):313–334 (2012)** (https://ideas.repec.org/a/inm/oropre/v60y2012i2p313-334.html): EM over MNL choice plus Poisson arrivals, estimating lost sales when availability varies. It fits a twin pair with comp availability far better than single-class EM, and should sit beside the survival model in R4. |
| 3 Buy-down / hybrid | Good | **Boyd & Kallesen exists**: "The science of revenue management when passengers purchase the lowest available fare", *JRPM* 3(2):171–177 (2004) (https://www.iaorifors.com/paper/63773). Remove the UNVERIFIED. |
| 3 Own-price learning | Thin | **Cooper, Homem-de-Mello & Kleywegt, "Learning and pricing with models that do not explicitly incorporate competition", *OR* 63(1):86–103 (2015)** (https://ideas.repec.org/a/inm/oropre/v63y2015i1p86-103.html): sellers that fit monopoly demand curves to their own prices and sales can converge to many different limit prices depending on where they start. This is the exact failure risk for `src/elasticity` learning β from own sales while comps react. It is more relevant than the 2006 paper. |
| 4 Overbooking / cancellation | Adequate | The cancellation-premium source (S35) is a seminar notice only. |
| 5 Vendors | **Thin** | The prompt names Sabre, Amadeus and BCG/Lufthansa. The dossier has no Sabre or Amadeus product row and treats Lufthansa only as continuous pricing. Found: Sabre AirVision Dynamic Availability (2018; Etihad, Aegean; Virgin Australia 2022) and Sabre Air Price IQ, "up to 3% airfare revenue uplift" (VENDOR; https://sabre.com/?p=39090; https://www.ttgasia.com/2018/09/11/sabre-launches-new-dynamic-pricing-solutions-for-airlines/). Lufthansa Group consolidated onto PROS RM + Real-Time Dynamic Pricing (2022) and added PROS Dynamic Ancillary Pricing (Jan 2025) (https://www.businesswire.com/news/home/20220712005223/en). The reviewer found no BCG link; the dossier should say so explicitly. Fetcherr's own "6–9%" is missing (#18). |
| 6 Competitive inputs | Partial | OAG is not mentioned. The S53 matching figures need the correct thesis URL (42054). |
| 7 Leading indicators | **Gap** | "Bookings on competitor flights" (the prompt's words) means **MIDT** (GDS Market Information Data Tapes), and it is absent. Airlines buy competitors' bookings by O&D, class and booking date up to 11 months out. Vendor claims: Amadeus 1–3% bottom line, Sabre +7% share (VENDOR; https://www.businesstravelnews.com/More-News/Giving-The-Big-Guns-More-Firepower). This is the closest airline analogue of our comp **availability drawdown**, which §6.2 says should feed Λ_k, so the analogy should be made explicit. |
| 8 Organizational practice | Good | — |
| 9 Measurement | Good, but finding E | Counterfactual and off-policy evaluation is barely covered. COAT's synthetic-control market design (§2, #8) is the actual 2026 frontier example and is under-used. |
| Textbooks | Weak | Gallego & Topaloglu, *Revenue Management and Pricing Analytics* (Springer 2019; ch. 1, 6, 9: single resource, dependent demand, finite-horizon dynamic pricing) is the modern canonical text for §1.7/§4.4. It is missing; T&vR was cited from memory. |

Reviewer searches run (14): Li/Granados/Netessine figures; PROS 4.7%; Weatherford–Pölt; Airbnb Smart Pricing figures; PODS matching thesis; Delta/Fetcherr Q2-2025 call; Boyd & Kallesen; Vulcano–van Ryzin–Ratliff; Cooper et al. 2015; MIDT; additive vs multiplicative pickup (recent); Sabre/Amadeus continuous pricing; Lufthansa/BCG/PROS; Gallego–Topaloglu.

## 5. Reasoning problems

**Finding E: R6 switchback design.**
- COAT rejected temporal alternation because of advance purchase. Our lead times run 30–120+ days, so prices for a check-in week are set and seen over months.
- Assigning arms by check-in week (as R6 says) avoids COAT's specific problem, because the arm is fixed per stay date, not per decision date. The dossier should say so explicitly instead of citing COAT as support.
- It should also handle stays that cross an arm boundary. Iberia used Monday–Sunday blocks for this; our stays are 4–7 nights.
- The YoY covariate rests on about one prior season of per-home weekly data, with rate-card changes in between. COAT dropped YoY for exactly this kind of instability.

**Finding F: no power arithmetic.**
- R6 sets "target < 15% MDE over two seasons" as an **assumption**. The impact priors for R1–R4 are +0.5% to +4%, more than an order of magnitude below any plausible field MDE.
- The dossier should say plainly that none of R1–R4 can be verified in the field within two seasons. Their only evidence will be simulation, which Talluri et al. (S69) call "within-model".
- R5 should therefore carry a **misspecification** test: build the simulated WTP from a family different from the engine's S(p), so the bid-price engine is not graded against its own assumptions.

**Other problems.**
- **Impact priors are unexplained.** "+1–4%" (R1) and "+1–3%" (R2) cite no mapping from the airline evidence. The airline numbers come from networks with tens to hundreds of seats per leg, where most of the value comes from many units sharing one control. State the reasoning, or give the priors as ranges with "no transfer basis".
- **R1 "Confidence: Medium" is too high** for the joint change, given findings A–D and the fact that Λ_k and S(p) are "mostly prior" at about 100 reservations (as the dossier itself says). Split R1 into R1a (WTP-form demand model, which addresses the ceiling problem) and R1b (bid-price recursion), each with its own confidence.
- **Strategic waiting (§3.5).** S87's own counterfactual says strategic consumers need not hurt revenue and that committing to non-decreasing prices can hurt leisure markets. That cuts against the implied "never discount close-in" stance for leisure ski groups. Report it.
- **Recapture uplift (R-list, M5).** It is reasonable, but the open question (#4) is the only data source. Mark it a prior with no evidence.
- **Effort.** R1 at "M" (1–3 weeks) is optimistic if it includes the pooled hazard model, the WTP model, unit-correct π, and the closed-loop simulator gate (R5) it depends on.

## 6. Numbered fix list

1. **Correct the pass-through claims** (§0 item 1, §1.7, §3.4 items 1–2, §10 fare-adjustment row). State that `p* = BP + 1/b` needs Poisson, non-saturating arrivals. Under the §4.4 bucket model, pass-through falls with Λ_k (reviewer: 0.99 → 0.44 → 0.17 for Λ = 0.01 → 1 → 10). Give the formula or a table.
2. **Fix the units.** BP and π are owner-net dollars. The shift in nightly rate is BP/(2·share) (linear) and about BP/share (exponential, sparse arrivals), with share = 0.595 from `owner_terms()`. Say how M3's rate-unit C maps onto an owner-net V.
3. **Withdraw "the bid price fixes peak-at-ceiling"** (§0 item 2, §3.4 item 3). BP ≥ 0 raises price. Attribute any fix to the WTP demand-model change. Split R1 into R1a (demand model) and R1b (recursion), each with its own impact, confidence and diagnostics.
4. **Handle the PODS WTP kink** (§3.4, §9.2). Note the flat region below basefare and either recommend a smooth S(p) or explain how the optimizer avoids piling up at the anchor.
5. **Rewrite the COAT paragraph** (§9.4 end, §12 "Do not do"). Quote its rejection of temporal alternation and of YoY baselines. Fix the date, scope (ancillary seat pricing, 17 weeks, +6.9%, synthetic control) and depth (the full text is open). Then argue why check-in-week assignment survives, or change R6 toward a synthetic-control design using comp-market series.
6. **Add R6 design details.** Boundary-crossing stays, given 4–7-night LOS (Iberia's Monday–Sunday logic). Analyst and operator observer bias (Iberia §3.1.3). Instability of the YoY covariate with one prior season.
7. **Add explicit power arithmetic.** State that the R1–R4 priors (≤ 4%) are undetectable in the field at any plausible MDE. Make R5's acceptance gate a **misspecified-world** test (simulated WTP family ≠ the engine's S(p)), not only "v2 targets still pass".
8. **Downgrade the spiral-down claim** (§3.2, R4). It was a 5-seed, one-season screen; call it "the same risk", not "already happened", and drop or qualify "~$8k per season".
9. **Fix S53**: use https://dspace.mit.edu/handle/1721.1/42054 (the 60708 record is D'Huart 2010 and lacks the figures). Read the thesis and name the author.
10. **Fix S86**: 16.2 is a welfare figure, not revenue. Use Table 6 (revenue 12.21 observed vs 13.44–14.70 under the stopping-time strategy, a 9–17% gap) and name the authors.
11. **Fix S50**: the article says 3% of *flights*, and the 20% target is not dated there. Cite a source carrying Hauenstein's Q2-2025 remarks, or the transcript.
12. **Add Fetcherr's "6–9%"** (S48) to the §5.4 VENDOR table.
13. **Fix S85 (dead link)**: find an archive copy or mark the quote UNVERIFIED.
14. **Boyd & Kallesen**: cite *JRPM* 3(2):171–177 (2004) (IAOR 63773) and remove the UNVERIFIED.
15. **Add Vulcano, van Ryzin & Ratliff (2012)** to §2.2 and R4 as the choice-based unconstraining method for the twins plus comp availability.
16. **Add Cooper, Homem-de-Mello & Kleywegt (2015)** to §3.2 and R4/M1. It covers learning β from own sales under competition and multiple limit points, which is a direct risk for `src/elasticity`.
17. **Fill the vendor gaps** (§5.4): Sabre Dynamic Availability / Air Price IQ, Amadeus, Lufthansa–PROS RTDP and Dynamic Ancillary Pricing; state that no BCG role was found.
18. **Add MIDT** (competitor bookings) to §7 and map it to comp availability drawdown. Mention OAG in §6.1.
19. **Add the counterfactual from S87** (strategic consumers need not hurt revenue; non-decreasing price commitments can hurt leisure markets) to §3.5, and temper the close-in stance.
20. **Read the open-access primaries** now cited at "summary" depth: the MIT DSpace theses (S12, S28, S29, S53), arXiv S7, S84 and S86, and S33 GAO. Update the depth column. Add Gallego & Topaloglu (2019) as the modern textbook reference for §1.7/§4.4 and check the DP statements against it rather than memory.
21. **ROM mapping** (§9.3): note that `scoring.hindsight_revenue` is a gross greedy bound that ignores competitors. An owner-net hindsight must be built before ROM % is reported.
22. **Justify or widen the impact priors** in §12. Give the transfer reasoning for each, or label them "no transfer basis". Revisit R1's effort estimate given its R5 dependency.
23. **Update the Appendix B self-audit** after these fixes: "read primary sources" should be PARTIAL (41/88 summary-only), and the fix to the "no fabricated citation" line should mention the S53 URL correction.

## Addendum: scoped re-review, 2026-10-19

Scope: R1 §0, §3.4, §9.4–§9.5, §12 and §13, which changed after this review. Checked by the
close-out audit, which also applied some of the fixes, so this is a consistency check, not an
independent review.

- §12 now separates R1a and R1b with distinct diagnostics; the ~$8k spiral figure is withdrawn; the R5
  gate is a misspecified-world test. Consistent with §0 and with fixes 3, 7 and 8.
- §9.5 is new: the power table (60 × (33/d)² weeks per arm) reproduces; it supports "R1–R4 priors are
  undetectable in the field".
- §9.4: the COAT paragraph now matches the full text (17-week premium-seat pilot, +6.9%, synthetic
  control, explicit rejection of temporal alternation and YoY baselines). The dossier's argument that
  check-in-week assignment survives is sound for stay-week assignment; the move to a comp-market
  synthetic-control covariate follows from the source.
- S86 now uses Table 6 (observed 12.21 k€ vs 13.44–14.70 k€): 9–17% gap, recomputed. S53 points to
  Lua (2007), handle 42054. S85 is marked dead.
- Bibliography S88–S95 added; every inline S-number now has a row.
- Not re-checked: S7, S12, S28, S29, S33 remain summary-depth (fix 20, partly).

Verdict unchanged: ACCEPT WITH FIXES, fixes applied (ledger in R1 Appendix C).
