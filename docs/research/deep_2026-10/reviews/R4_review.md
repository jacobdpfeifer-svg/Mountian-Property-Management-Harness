# R4 review: generic STR pricer teardown (`docs/research/deep_2026-10/R4_str_pricer_teardown.md`)

Reviewer: adversarial review (V_REVIEW.md). Date: 2026-10-16. Status: COMPLETE.

## 1. Repo audit of the "Our engine today" column (§6) and other repo claims

Checked against `config/policies/default.yaml`, `config/policies/candidates/pace_v3_anchor_repair.yaml`,
`config/policies/{events,conditions,signals}.yaml`, `config/resort/winter_park.yaml`,
`src/scrape/__init__.py`, `src/scrape/providers.py`, `src/signals/comp_movement.py`,
`src/pacing/__init__.py`, `src/shadow/__init__.py`, `src/explain/__init__.py`, `src/compose/__init__.py`,
`src/pricing/pace.py`, `docs/research/MODEL_SPEC.md`, `docs/plans/OVERHAUL_2026-10-14.md`,
`docs/field_test/PREREGISTRATION.md`, `proving_ground_exam/market/competitors.py`.

**Correct as stated** (spot-verified): lead-time curve 0.90 at 0–7 d, 0.97 at 8–21 d, 1.03/1.05 beyond 60/120 d;
fixed `dow_multipliers`; fixed `seasons:` windows; peak β −0.65 linear (default) and −1.00 prior (candidate);
M1 shrinkage κ=40 + Thompson (MODEL_SPEC l.20–24); guardrails +12%/−15%/$250, peak blackout 0.85,
run-scope caps; orphan gap 0.88 + min-stay relaxation; season×lead min-stay table; group-size filter
bedrooms ≥ 5 / sleeps ≥ 14; `intent.enabled: false`, `flight.enabled: false`; `models.*` (learned elasticity,
horizon M3, stay pricing M4, portfolio M5) all `false` in default and only learned elasticity + pace on in the
candidate; candidate anchor 42 d / 3 comps, sensitivity 0.30, bounds 0.85–1.25; shadow module holds no PMS
client and refuses a DB with any Guesty write; explain reasons ranked by signed dollar contribution;
CDOT access gated on `signal_status_at_least(..., "shadow")`; resort ops only demotes autonomy (no price move);
substitution `max_ceiling_reduction_pct: 0.15`; SQI `curve_confidence: 0.35`; the −6.6% / ADR $2,052 vs $2,246 /
early-winter +$3.1k / spring +$2.2k figures match OVERHAUL_2026-10-14 l.205–206; the 33% MDE at 60 weeks per arm
matches `docs/field_test/PREREGISTRATION.md` l.96. Fee dilution arithmetic checks: (600 + 75×10 + 80)/4 = $357.5/night,
357/(2000+357) = 15%.

**Incorrect or misleading** (each is a fix item):

- **R-1. Comp calendar availability is NOT captured.** §6 row 2 says "comp calendars (availability, min-nights) are
  captured (`src/scrape/providers.py` `calendar`)" and edge #2 says "Daily peer calendars (already fetched)".
  `providers.py` fetches `available` and `min_nights`, but the only consumer, `_enrich_min_nights`
  (`src/scrape/__init__.py` ~l.322–332), persists **only `min_nights`**, and only onto rows the sweep already wrote.
  `comp_snapshots.available` is set from *sweep presence* (`_write(..., 1, ...)` when the comp appears in a search
  window, `0`/`'unavailable'` when it does not, l.224–232). Search absence conflates "booked" with "not ranked in
  this search tile / filtered by min-stay", which is a worse block-inference input than the vendors' calendar
  transitions. Edge #2 therefore needs a code change (persist per-day calendar availability) before any
  pickup study, and §6/§8 should say so.
- **R-2. A comp-movement demand signal exists and is omitted.** `src/signals/comp_movement.py`
  (`upsert_comp_movement_signals`, called on every scrape in `src/scrape/__init__.py` l.249) writes
  `demand_signals` from the curated comps' 14-day median listed-price lift. That is a (price-based, not
  booking-based) market-movement input. The "Market pacing / pickup" row should read "N for pickup; P: comp
  price-movement signal feeds demand tier", and §12.1 "what generic tools add that we do not" should note it.
- **R-3. Events row understates a live defect.** `config/policies/events.yaml` is dated, not recurring: it
  covers the 2025-26 season (Christmas, MLK 2026-01-16, Presidents 2026-02-13, Spring Break 2026-03-07..22, etc.)
  but for 2026-27 contains **only Christmas 2026-12-20..2027-01-04**. MLK 2027, Presidents 2027 and Spring Break
  2027 are absent, and the calendars collector falls back to this file. The dossier's "one Spring Break window
  03-07..03-22" describes last season's window as if it were current. This raises the priority of rec 9.
- **R-4. Ikon blackout conflict not reconciled.** §3.2 says retailer listings put Winter Park on the Base Pass
  with **no** blackouts; `config/resort/winter_park.yaml` l.83–90 lists Winter Park Ikon blackouts 2025-12-26..27
  and 2026-01-17. The dossier cites the YAML in §6 ("dates in config/resort/winter_park.yaml") without noting that
  its own §3.2 source contradicts it. One of them is wrong; the operator needs to know which (see §3 of this review).
- **R-5. Generic-tool emulator mis-described.** §6 and §9 say `tool_price` "uses pre-HLP defaults ... the old 0.92
  inside 14 days and ×1.20 holidays". The file says it follows "PriceLabs' public description in
  `docs/research/dossiers/04_simulator_science.md`", but the dossier's own §2.1 table gives PriceLabs' *old*
  default as "gradual 30% over next 15 days" and far-out +20% — neither is in `tool_price` (it has 0.92 flat inside
  14 d, ×0.90 below 40% occupancy, ×0.90 price war, no far-out premium). It is a stylised emulator, not either
  PriceLabs vintage. Say that, because rec 2's "update to HLP" is a rewrite, not a parameter change.
- **R-6. Pacing "immutable" is overstated.** `src/pacing/__init__.py` upserts on `(as_of, property_id, stay_date)`
  (`ON CONFLICT ... DO UPDATE`); prior days are not rewritten, but a same-day re-run overwrites. Say "one row per
  as_of day; same-day re-runs overwrite".
- **R-7. Drought citation path.** §2.1 attributes a prior-season Christmas average in a 60%-of-normal snow year to
  `config/policies/default.yaml`; the $482 is there, the 60%-of-normal framing is in `docs/ARCHITECTURE.md` l.19–20.
  Minor, but the dossier should cite both.
- **R-8. SQI prior vs the dossier's own snow elasticity (reasoning gap, not a matrix error).**
  `conditions.yaml` maps SQI 0.62 (the "~2025-26 drought Christmas") to a **0.78 price multiplier** and SQI 0.50 to
  0.72. Parthum & Christensen's Colorado elasticity of 0.135 on *revenue* implies SWE at 60% of normal moves revenue
  by about 0.135 × ln(0.6) = −6.9%. The engine's declared prior is roughly 3× stronger and acts on *price*. The
  dossier cites both numbers and recommends calibrating the simulator to P&C (edge #3) but never notes that the
  live prior is inconsistent with that calibration. That belongs in §7/§8/§13 and in rec 8.

**Matrix rows with no error found:** own reservations, base price, seasonality, DOW, elasticity, horizon,
last-minute, far-out, occupancy/pace, orphan, dynamic min-stay, holiday block (M4 off), arrival-day rules (N; no
check-in-day rule found in `src/min_stay` or policies), segmentation, fee-aware comps (P; OVERHAUL 2.10 open),
owner-net (C/U), snow (Y/U), resort ops, road access, school calendars (N), substitution, macro/flights, M5,
guardrails, explanation, shadow, simulator, measured lift.

## 2. Public-repo hygiene and the 47-stay lead-time claim

- The "47 stays, mean lead 40.9 d, median 15 d, 7 booked 61+ d" figure is **not derived by R4**. R4 reuses
  `docs/research/dossiers/01_who_buys_winter_park.md` l.9–14, which states it queried the `reservations` table on a
  copy of the operator DB (`.testrun_runs/market_sim/phase0/eval.db`). The fields used (check-in vs created date,
  nights, guest count, channel) are reservation-level booking attributes, not guest identity fields, and the
  output is portfolio-level summary statistics, not per-guest rows. So R4 did not breach the "no guest fields"
  rule, but the provenance is **not per-home aggregates** either; R4 should say where the number came from and that
  R4 itself ran no query.
- **Misuse of the number (substantive).** Dossier 01 l.20 says the sample is "Mont Luxe only, **mostly
  June–December 2026. It is not a winter-season sample**." R4 calls it only "thin and mixed-season" and then uses
  it four times (§3.1, §3.4, §7 "Not supported" #2, §11 Q4, §13 #6) as evidence against a 4–10 month *winter*
  booking window and to shrink the snow edge. A summer/fall-dominated sample, plus right-censoring (a DB that only
  captures reservations created after Guesty sync began truncates long leads), cannot contradict a winter
  booking-window claim. The 15-day median must be demoted to "not informative about winter" everywhere it carries
  weight, and the operator question (Q4) is the right test.
- **No leaks found.** No Guesty ids, listing ids, addresses, guest data or booked revenue appear in R4. The long
  digit strings are help-centre article ids, a patent number and DOIs. Dollar figures are simulator outputs, policy
  constants, or the $482 last-Christmas average already public in `config/policies/default.yaml`. (Note for the
  operator, outside R4's scope: that same YAML comment also prints a specific booked price for this Christmas, which is
  booked-price data in a public file.)

## 3. Citation spot-check (26 URLs opened, 2026-10-16)

Every load-bearing claim named in the review brief was checked, plus a random sample.

| # | Source | Claim in R4 | Result |
|---|---|---|---|
| 1 | S39 CMU Tepper summary | Smart Pricing adopters: price −5.7%, revenue +8.6% | **Does not support.** The page has no such figures (only 41% lower adoption by Black hosts, 20% demand gap). The figures are in the SSRN abstract (papers.ssrn.com abstract_id=3770371; 403 to the reviewer, confirmed via search snippets). Right numbers, wrong citation, and R4 states "figures from summary", which is false. |
| 2 | S3 PriceLabs algorithm Part 1 | 350 similar-sized listings, max 15 km, dynamic radius, H3; per-date and per-comp-set elasticity; ski season less price-sensitive; 10M units incl. Booking.com | Supports (verbatim). |
| 3 | S4 PriceLabs Part 2 | $600 → $300, path → $303; ~9% LMD gain; +11% average | Supports (verbatim). |
| 4 | S6 PriceLabs default discounts | HLP LMD cap 40% within 60 d; far-out from 60 d cap 20%; old 30%/15 d; orphan 20% ≤2 d; recency 5–15%; safety min prior-year ADR ±1 wk | Supports. Page adds "applies only to dates that had a booking last year" for the safety minimum, which weakens R4's drought-floor point; R4 should add it. |
| 5 | S50 PriceLabs Revenue Accelerator | 2026 fee-stripped comp calendar, 10 comps, guest-price view, LOS all-in | Supports (dated 2026-04-07; "up to 10 competitors over 365 days"). |
| 6 | S79 PriceLabs Customer API | Prices only for actively syncing listings | Supports in substance: "receive prices ... for listings that are actively syncing prices to other channels or PMSs". "Only" is an inference, fairly drawn. |
| 7 | S78 PriceLabs Guesty guide | Shows recommended prices after import; syncs only on Sync Prices / Sync Now; Guesty warns to deactivate other tools | **Partly.** Sync options confirmed; "review your pricing ... in PriceLabs" before sync is implied, not explicit; the "deactivate other tools" text is not on this page (it is attributed to the second, snippet-only Guesty URL). |
| 8 | S11 Rakidzich PriceLabs cost 2026 | ~$19.99/listing/month US; 1% option; tiers | **Partly.** $19.99 for 1 listing and volume tiers confirmed (5 listings $9.99 each); 30-day no-card trial confirmed. The page **does not** mention a 1%-of-revenue PriceLabs plan (only for Wheelhouse/Beyond). ~$60/month for 3 homes is plausible but the 2–4 listing tier is not stated. |
| 9 | S49 Google Patents US11308564B2 | Airbnb, Ye & Yang, granted 2022-04-19, cluster of similar listings | Supports (cluster = listings within a predetermined distance, optionally same room type; two models combined). |
| 10 | S52 Parthum & Christensen (PMC) | 0.223 national, 0.135 CO, bed interaction 0.067, ~12.5M property-days, 236 resorts, 2014–17 | Supports these numbers. **Two errors elsewhere:** §13 #1 says Colorado's 0.135 is "the lowest in their state list"; the paper's range runs from 0.075 (Connecticut) to 2.512 (Tennessee). And "0.12–0.15 even for bookings made 2–10 days ahead" is really cumulative ≤2/≤5/≤7/≤10-day subsamples (0.124–0.152), not a 2–10 day band. |
| 11 | S18 Beyond algorithm explainer | 100–500 like listings; 3 event detectors; "eighteen months" pandemic text | Supports, including R4's dating inference (text refers to April 2020 / April 2022). |
| 12 | S1 PriceLabs Market Dashboard methodology | Last-listed price as booked price; block heuristics; >60-night stays removed; "no method is perfect"; ~15% host-only fee bump; frequency ND | Supports. |
| 13 | S12 Wheelhouse engine | Kriging, KM curves, gamma warping, 40% occ = 1.0, SF gaps 7.3% vs 41.1%, pacing A/B +0.9–1.5%, +22%, 21MM, updated 2023-05-01 | Supports. The page is **STALE** (2023-05-01, ~3.5 years old); R4 does not tag it STALE although it tags others. |
| 14 | S42 Expedia partner blog (Vrbo) | No LOS; PMS-integrated partners ineligible; +38% revenue, +39% bookings | Supports. R4 omits that the two figures come from different windows (Jan–May 2025 vs Nov 2025–Feb 2026). |
| 15 | S24 AirDNA property performance | ML trained on booking data; cannot perfectly separate booked/blocked; last available rate; ADR incl. cleaning | Supports. |
| 16 | S28 KeyData ProData | "not a pricing tool"; "sourced directly from operators, never scraped or modeled"; 80+ PMS; filters | Supports. |
| 17 | S27 Skift (es) AirDNA Adapt | $20/listing; ~3-month beta, 14,000 listings; 15% global / 31% US use dynamic pricing; Guesty integration; no lift | Supports. |
| 18 | S36 Airbnb Help 1168 | Hundreds of factors; early-bird can go below min; Airbnb may switch off in crises | Supports. |
| 19 | S38 Morning Paper on Ye et al. | Naive demand-curve revenue maximization failed in online A/B; PDR and booking-regret definitions | Supports ("these methods often fail to optimize revenue for our hosts in practice"). |
| 20 | S58 Inntopia 2013 | 10 resorts, 5 winters, ~5 months out paid ~10% above average | Supports (STALE, correctly tagged). |
| 21 | S67 DOJ RealPage release | 2025-11-24; nonpublic data ban; 12-month aging; no narrower-than-state geography; monitor | Supports. The 7-year term is not in the release (from S68, not checked). |
| 22 | S70 Baker McKenzie Gibson v. Cendyn | 9th Cir. 2025-08-15, No. 24-3576, affirmed; hub-and-spoke dropped | **Dead link** (301 to a generic listing). The claim is correct per Baker McKenzie's 2025/08 alert, Mondaq and Inside Class Actions; replace the URL. |
| 23 | S72 Otten Johnson HB25-1004 | Vetoed 2025-05-29; governor signalled a narrower bill | **Partly.** Veto date confirmed; the page says nothing about a narrower bill. |
| 24 | S80 arXiv 2606.02595 | Warm-start cuts cold start ~150 → ~30 episodes, 2-room STR | Supports, but only for the HF-TS agent family, one anonymised *urban* market, 1,461 episodes; R4 should carry that qualifier. |
| 25 | S87 arXiv 2503.04489 | Self-preferencing raises commission ~38%, ~5% welfare cost, Tokyo | Supports (37.73%, 5.08%). |
| 26 | S51 TechCrunch 2025-04-21 | Total price (fees, before taxes) shown by default to all users | Supports. |
| 27 | S65 Leoni & Nilsson WP | Surging hurts revenue on average, heterogeneous, causal forests, Ibiza | **Partly.** Finding and method confirmed; the RePEc page does not name Ibiza (UNVERIFIED there). |
| 28 | S41 Edinburgh Evening News | Festival glitch; Airbnb blamed "global systems error" | Not verifiable (403). |
| 29 | S75 Colorado Sun skier visits | 10.5M vs 13.9M, about −24% | Supports via SAM Magazine / Colorado Sun / CSCUSA coverage (Gazette says 13.8M). These are CSCUSA (an industry body) figures; R4 could cite CSCUSA directly instead of a 429 snippet. |

**Tally (29 checked):** supports 19; partly 7 (S11, S52, S65, S72, S78, plus S6 and S42 correct but missing a qualifier that matters, counted here as partly); does not support 1 (S39, wrong page; the number itself is real); dead 1 (S70); unverifiable 1 (S41). **No fabricated citation found.**

## 4. Depth audit (each MUST checked independently)

| MUST | Reviewer finding |
|---|---|
| Inline citation + access date | PASS. A single access date for everything is acceptable. |
| ≥ 40 distinct sources | PASS. 87 reference IDs, several bundling 2–3 URLs. |
| ≥ 4 source classes | PASS on paper (1, 2, 3, 6, 7). Reviewer recount: class 1 has about 11 genuine items (S84 is cited from memory, and S37 was read only at abstract level). Class 2 has 2 textbooks, both "not re-read". **Classes 4 and 5 are zero, and that was avoidable** (see §5): CSCUSA skier-visit data, and the Airbnb, Vail Resorts and Vacasa 10-Ks, are all public. |
| Primary sources read | **FAIL as written; R4's "PARTIAL PASS" is generous.** The KDD 2018 paper is open access but R4 relied on a blog summary of it (S38) for its most-used Airbnb claim. Zhang et al. was not read, and the figure is credited to a page that does not contain it. The Gibson opinion was not read. These are exactly the "blog summary does not replace the paper" cases the standard names. |
| UNVERIFIED / STALE marking | Mostly PASS. Missing STALE tags: Wheelhouse engine page (2023-05-01), S3/S4 (2023-09), Gibbs (tagged), BiggerPockets (tagged). The Ikon "no blackouts" claim is tagged UNVERIFIED but not reconciled with the repo YAML (R-4). |
| No fabrication | PASS. Nothing fabricated was found in 29 checks. |
| Search passes broad/specific/adversarial | PASS. The 70-query log is credible. |
| Mechanisms | PASS. Strong for PriceLabs, Wheelhouse and Airbnb. Thin for Beyond, Guesty, AirDNA Adapt and DPGO, which is mostly because the vendors disclose little; R4 flags this. |
| Quantified evidence + conflicts | PASS, with an overclaim in the §4.3 summary (see §6). |
| Map to engine + owner-net measurement | PASS. Weakened by R-1 (edge #2 assumes data we do not store). |
| Transferability | PASS (§12.2 is good). |
| "What generics miss" | PASS (§7). |
| Ranked recs / open questions / self-audit | PASS. |
| Search log | PASS. |
| Adversarial pass | PASS, but it missed the strongest contrary datum (AirROI's 72-day Winter Park lead time; see §5). |
| Prompt "Cover at minimum" | Reddit/Facebook: honest FAIL (tool limit; the reviewer's own Reddit searches also returned nothing). Every named vendor is covered. Mountain probes are covered. Booking-window shape is **covered with the wrong first-party evidence** (§2 above). Fee-inclusive display: covered. Lawsuits: covered, but **missing the 2026 Third Circuit reversal** (see §5). Feature matrix, edges and shadow recommendation: delivered. |

## 5. Coverage gaps: reviewer's own searches (14 queries)

Queries: Zhang et al. figures (×2); Ikon Base 2026-27 Winter Park blackouts; Gibson v. Cendyn status; Duetto vacation
rental product; Cornish-Adebiyi v. Caesars; PriceLabs ski/snow content; Airbnb 10-K pricing tools; Vacasa 10-K
dynamic pricing; Cornell CHR / HSMAI STR pricing; Reddit PriceLabs Christmas ski underpricing (extended); AirDNA
accuracy validation (extended); Colorado ski STR 2025-26 market reports; Vail Resorts FY2025 10-K; PriceLabs
check-in/check-out restrictions; CSCUSA 2025-26 skier visits.

Material R4 missed, in order of importance:

1. **Winter Park's own booking window is about 72 days, not 15–33.** AirROI, "Ski market winter 2026-27 booking
   pace" (2026-07-29), https://airroi.com/blog/ski-market-winter-2026-2027-booking-pace: across a 14-market,
   24k-listing panel, winter 2025-26 average lead time was **72 days for Winter Park** (range 48 days at Mammoth to
   104 at Big Sky). Lead times lengthened year over year. Winter Park occupancy fell 44.9% → 35.8% while **ADR
   rose 22.2%** (RevPAR −4.7%, supply +9.9%). This is all-unit, vendor-modelled data (scraped, class 7), but it is
   Winter-Park-specific and current. It (a) contradicts R4's reliance on Beyond's 24–33-day all-market averages and
   the 15-day non-winter first-party median, (b) means a pace-reactive generic tool sees snow effects **later**
   than R4's §7/§13 argument assumes, which **strengthens** the snow edge R4 shrank, and (c) independently supports
   §13 #2 ("rates sticky in bad snow years"), and so bears directly on the SQI drought multiplier (R-8).
2. **Cornish-Adebiyi v. Caesars Entertainment (3d Cir., No. 24-3006, opinion 2026-07-29)** reversed dismissal of
   the Atlantic City hotel / Cendyn Rainmaker case and created a split with Gibson. The pleaded facts were nonpublic
   data fed into a shared algorithm, with recommendations accepted about 90% of the time
   (https://www.cov.com/en/news-and-insights/insights/2026/08/third-circuit-reinstates-algorithmic-pricing-antitrust-lawsuit-cornish-adebiyi-v-caesars-entertainment-inc ;
   https://news.bloomberglaw.com/antitrust/caesars-mgm-lose-as-appeals-court-reverses-ai-collusion-ruling).
   R4's §4.4 presents Gibson as the appellate state of play. That is out of date by 2.5 months, and the high
   acceptance rate is directly relevant to the PM-co-op and "aligned defaults" analysis.
3. **Company filings (class 5) were skipped although they are easy to get.** The Vail Resorts FY2025 10-K
   (https://www.sec.gov/Archives/edgar/data/812011/000081201125000104/mtn-20250731.htm) covers snowfall's effect on
   lodging and the fact that pass sales were down ~3% in units for 2025/26; AirROI reports 2026-27 pass units −10%.
   The Vacasa 10-Ks (FY2022–24, e.g. https://www.sec.gov/Archives/edgar/data/1874944/000187494425000003/vcsa-20241231.htm)
   are the only filings that describe an STR operator's own ML dynamic pricing objective (revenue per available
   night, then homeowner income). The Airbnb FY2025 10-K
   (https://www.sec.gov/Archives/edgar/data/1559720/000155972026000004/abnb-20251231.htm) is relevant to the
   Smart Pricing incentives.
4. **Industry-body data (class 4) was skipped.** Colorado Ski Country USA's skier-visit release (via
   https://www.saminfo.com/news/colorado-resorts-endured-historic-visit-decline-in-2025-26) gives 10.5M visits,
   the lowest since 1991-92, and 129 vs 144 operating days. That is a cleaner citation than the Colorado Sun 429
   snippet. DestiMetrics/Inntopia monthly western-lodging reports (e.g. SAM:
   https://www.saminfo.com/news/sam-headline-news/western-destinations-lodging-trends-continued-in-february;
   CO/UT occupancy −6.7% YoY vs −0.5% elsewhere) are industry-standard mountain-lodging data. No Cornell CHR or
   HSMAI STR-pricing study was found, so their absence is acceptable, but R4 should say it looked.
5. **Key Data Summit County 2025-26 outlook** (https://www.keydata.co/blog/summit-county-colorados-2025-26-ski-season-outlook;
   it projected ADR +2% before the drought) is a dated example of a PM-data vendor's forecast missing a snow
   shock. It is a usable adversarial data point for H2.
6. **Arrival-day rules in practice.** OwnerRez and Hostaway forums report that PriceLabs check-in/out restrictions
   are PMS-dependent and can misfire: a Saturday rule blocked all Saturdays on Airbnb, and PMS sync overwrote
   holiday blocks (https://www.ownerrez.com:443/forums/general-help/arrival-restrictions ;
   https://support.hostaway.com/hc/en-us/community/posts/26706609816347-Default-setting-to-check-in-out-restrictions).
   This is the forum evidence the prompt asked for, and it is reachable without Reddit. R4 should also find out
   whether Guesty is among the PMSs that support PriceLabs stay restrictions.
7. **Booked-vs-blocked accuracy.** Search found only self-reported AirDNA benchmarks and single-property anecdotes
   (e.g. https://magicbnb.io/blog/is-airdna-accurate, ~17% overestimate on one property; vendor-adjacent). This
   confirms R4's "no independent validation". Separately, a cheap first-party validation R4 does not propose:
   scrape **our own three homes'** public Airbnb calendars, run the same block inference, and score it against
   Guesty truth (owner blocks included). That is the only ground-truth error rate we can get, and it costs nothing.

## 6. Reasoning problems

- **Booking-window inference is wrong (largest issue).** See §2 and §5.1. Five sections lean on the 15-day median.
  With the 72-day Winter Park figure, §7 "Not supported" #2 and §13 #1 and #6 lose most of their force, and the
  far-out-premium row of §12.2 ("little is sold far out today") becomes an artefact of the sample.
- **"Credible, independent lifts cluster at +3% to +9%" overclaims.** The +3.5/+5.2% (Wang et al.) has operator
  staff as co-authors (R4's own table says so). The +8.6% (Zhang et al.) is an adopter DiD, so it carries
  self-selection into adoption timing. Leoni & Nilsson is about a host behaviour, not a tool's lift. The only
  independent tool-level estimate is Zhang et al., and it is one study of the platform's own tool. Say "one
  independent estimate (+8.6% revenue, achieved by cutting price) and one operator-co-authored field test
  (+3.5–5.2%)".
- **The SQI prior conflicts with the cited elasticity** (R-8). R4 recommends calibrating the simulator's snow
  demand to Parthum & Christensen while the live engine (`sqi.enabled: true`) applies a much larger price cut in a
  drought. AirROI's Winter Park 2025-26 ADR +22% in a drought also argues against it. This is a concrete specialist
  risk: hyper-specialization on snow can **lose** money if the prior has the wrong size. It belongs in §13 and in
  rec 8.
- **PriceLabs' safety minimum.** It applies only to dates that booked last year (S6). R4's drought-floor critique
  should carry that qualifier.
- **Edge #2 depends on data we do not store** (R-1), and its validation plan ("compare with Key Data or Guesty-side
  truth") is unworkable as written: Guesty truth exists only for our own homes, and Key Data cells for ~15 large
  homes would likely be suppressed or be co-op data that rec 10 tells us to refuse. Use the own-homes calendar
  test from §5.7.
- **Shadow write-safety.** The PriceLabs–Guesty connection is an OAuth/marketplace integration that PriceLabs
  creates, not a token we mint, so the "scoped token" mitigation may not exist. The dossier should name the
  fallback: add the homes to PriceLabs **without** a PMS connection (as manual/unconnected listings, if PriceLabs
  supports that; UNVERIFIED) and accept UI-only capture. Our shadow module's Guesty-write counter only sees writes
  made through our own code path. It would **not** detect a PriceLabs write made directly to Guesty, so the "daily
  check" needs a Guesty-side rate diff, not `guesty_write_count`.
- **Cost of the shadow.** The 1% PriceLabs plan is unsupported by S11. The ~$60/month figure assumes $19.99 per
  listing at 3 listings; S11 lists tiers only at 1 and 5. State the cost as a range.

## 7. Verdict

**ACCEPT WITH FIXES.** The vendor teardown is unusually well sourced: no fabrications, and 26 of 29 spot checks
support or partly support the claims. The matrix is mostly honest, and the shadow-arm recommendation is sound. Four
things stop an unconditional accept: (1) a first-party statistic misused against its own source's caveat, which
also contradicts current Winter Park data; (2) one repo capability claimed that the code does not have (comp
calendar availability), on which edge #2 depends; (3) the antitrust section is out of date by a circuit split;
(4) the primary-source MUST is not met for the two most-quoted academic claims. None of these requires new
fieldwork. All are fixable in the text.

## 8. Numbered fix list

1. **Demote the 15-day / 47-stay median everywhere** (§0, §3.1, §3.4, §7 "Not supported" #2, §11 Q4, §12.2
   far-out row, §13 #1 and #6). Quote dossier 01's own caveat ("mostly June–December 2026, not a winter-season
   sample") and add right-censoring. State the provenance: R4 ran no query, and dossier 01 reports portfolio-level
   statistics from reservation booking attributes, not guest identity fields.
2. **Add AirROI's Winter Park 2025-26 data** (72-day average lead; occupancy 44.9% → 35.8%; ADR +22.2%) as the
   best available current market booking window. Re-argue §7 #2 and §13 #1 (the pace lag is longer, so the snow
   edge is larger) and §13 #2 (rates held in the drought). Flag it [vendor-modelled, scraped].
3. **Fix the comp-calendar claim (R-1).** §6 row 2 and edge #2 should say that per-day calendar availability is
   fetched by `providers.calendar` but **not persisted** (`_enrich_min_nights` stores only `min_nights`), and that
   `comp_snapshots.available` comes from search-sweep presence. Make "persist calendar availability" a
   prerequisite step in rec 5.
4. **Add the comp price-movement signal (R-2)** (`src/signals/comp_movement.py`) to the market-pacing row and to
   §12.1.
5. **Events row (R-3):** say that `events.yaml` is dated and holds only Christmas for 2026-27 (no MLK, Presidents
   or Spring Break 2027), and raise rec 9's priority accordingly.
6. **Reconcile Ikon blackouts (R-4):** the repo YAML lists Winter Park blackouts while §3.2's sources say none.
   Verify against ikonpass.com or raise it as an operator question. The "diversion" edge (#6) depends on it.
7. **Correct the emulator description (R-5):** `tool_price` matches neither PriceLabs vintage. Rec 2 is a rewrite.
   Also correct pacing "immutable" (R-6) and add `docs/ARCHITECTURE.md` as the source for "60% of normal" (R-7).
8. **Add the SQI-prior inconsistency (R-8)** to §7/§13 and rec 8: the drought multiplier of 0.78 against the
   ~−7% revenue that P&C's 0.135 implies, plus Winter Park's drought ADR rise. Recommend flattening or capping the
   SQI price curve until it is fitted, and measure the owner-net effect on drought-scenario nights in the proving
   ground (`scenarios/drought.yaml`).
9. **Fix S39:** cite the SSRN abstract (or the Marketing Science article) for −5.7% / +8.6%, remove "figures from
   summary", and say that the design is an adopter DiD subject to selection.
10. **Read and cite the KDD 2018 full paper** (open access) for the "naive revenue maximization failed online"
    claim instead of the Morning Paper. Read the Gibson opinion, or at least say it was not read in §4.4 as well
    as in §14.
11. **Fix P&C errors:** delete "Colorado ... lowest in their state list" (Connecticut 0.075 is lowest), and restate
    the lead-time result as cumulative ≤2/≤5/≤7/≤10-day subsamples (0.124–0.152).
12. **Update §4.4 with Cornish-Adebiyi v. Caesars (3d Cir. 2026-07-29)** and the circuit split. Reassess the
    implication for PM-pooled products, and note that PriceLabs ingests Key Data (relevant only if we ever *adopt*
    PriceLabs prices, not to a shadow).
13. **Replace dead S70** with the Baker McKenzie 2025/08 alert or Mondaq. Drop "signalling a narrower bill" from
    S72 or source it.
14. **Fill classes 4 and 5:** CSCUSA skier visits (replace the S75 snippet); the Vail Resorts FY2025 10-K
    (snowfall and lodging, pass units); the Vacasa 10-K (STR operator pricing objective); the Airbnb 10-K (Smart
    Pricing incentives). Update the self-audit counts.
15. **Tone down the lift summary in §4.3** to "one independent tool-level estimate plus one operator-co-authored
    field test", and add the two Vrbo measurement windows.
16. **Shadow arm (§9):** (a) replace the "scoped Guesty token" mitigation with a Guesty-side daily rate diff,
    because `guesty_write_count` cannot see third-party writes; (b) give the unconnected-listing fallback as an
    option to check (UNVERIFIED); (c) state the cost as a range and drop the unsupported PriceLabs 1% plan;
    (d) ask whether PriceLabs stay restrictions support Guesty.
17. **Edge #2 validation:** replace "compare with Key Data or Guesty-side truth" with the own-homes test: run the
    block inference on our three homes' public calendars and score it against Guesty truth. Report precision and
    recall of the booking label, and occupancy bias.
18. **Add forum evidence on arrival-day rules** from OwnerRez and Hostaway (§5.6) to §3.5 and §4.1.
19. **Tag S12 (2023-05-01) and S3/S4 (2023-09) STALE** in the same way the others are tagged. Add the S80 qualifier
    (HF-TS family, one urban market). Add the S6 qualifier (safety minimum only on dates booked last year).
20. **Self-audit:** change "Read primary sources" to FAIL until fixes 9–10 are done, and list classes 4 and 5 as
    filled once fix 14 is done.

Status: COMPLETE.
