# S1 review: synthesis and roadmap (`docs/research/deep_2026-10/S1_synthesis.md`)

Date: 2026-10-19. Reviewer: close-out audit, working to `V_REVIEW.md`. Research only: no code
edits, no commits, no Guesty writes. The database was opened read-only (`mode=ro&immutable=1`) and
only comp asking prices and counts were read.

This review replaces the 2026-10-17 file, which was a structural close-out. That file checked that
the seven deliverables existed and spot-checked seven code paths. It did not open citations or run
searches, so it did not meet `V_REVIEW.md`.

## Verdict: ACCEPT WITH FIXES

S1 has every deliverable `S1_SYNTHESIS.md` asks for, uses the post-review wording for H1–H7, and
keeps the field-MDE and inactive-canary constraints in front of every roadmap item. The hard numbers
it rests on mostly check out (§B): the $9.99 dashboard, the 350-listing / 15 km estimator, the AirROI
72-day lead and drought panel, the Open-Meteo default unit and licence, the FTC rule, the 0.595 owner
share, the inactive live-write path, and the 0–8% anchor coverage. No citation was fabricated.

Six problems need fixing before S1 is handed to a builder:

1. **Code status is out of date.** Commit `d3e8b92` (2026-10-19 10:20) fixed the road feed, the
   wind unit, the 2027 holidays, the Ikon rows and the drought multiplier. §2.2, §4.3 and roadmap
   item 2 still describe them as open. The residual risks of that commit (A3) are not in S1.
2. **The comp-availability claim is imprecise and cites the wrong file** (A1).
3. **Edge 4.4 overclaims.** PriceLabs has published a dynamic minimum-stay engine since 2023 that
   weighs "guaranteed revenue" against the opportunity cost of neighbouring nights and counts
   turnover cost (search 10). The defensible edge is the owner-net economics and the 16-sleeper
   LOS demand, not stay-level opportunity cost as such.
4. **The "soft season" evidence is quoted without its own attribution.** The Inntopia source S1
   cites attributes the soft start partly to a post-drought "snow hangover" and reports that winters
   after the five worst snow years finished **up** on average (B6). That changes how §4.5 and §9
   should use the −10.9%.
5. **Several superseded figures came back:** "natural experiment", "$2,427" as the 14-guest figure,
   "0.7–8 percent" (§3 H4) against "0.7–9.8 percent" (§1), and "2–3 times more precise" without the
   1.8× current-quality figure.
6. **The build prompts are not self-contained** and "What not to do" has no reasons. `S1_SYNTHESIS.md`
   asks for prompts "ready to hand to an implementation agent" in the style of `docs/prompts/*.md`;
   §7 gives four-line sketches with no context, files, acceptance criteria or constraints.

## A. Repo claims checked against the code

| # | S1 claim | What the code or data says | Result |
|---|---|---|---|
| A1 | "Calendar availability is fetched and then discarded: `_enrich_min_nights` in `src/scrape/providers.py` writes `min_nights` only" (§1, §2) | `_enrich_min_nights` is in `src/scrape/__init__.py` (line 323). It calls `provider.calendar()` (12 months of `available` and `min_nights` per day, `providers.py` line 218) and writes only `min_nights`, and only onto rows that already exist for that `as_of`. Separately, `comp_snapshots.available` **is** stored for every quoted stay date: as of 2026-10-19 there are 1,722 `ok` rows with available = 1 and 7,686 `unavailable` rows with available = 0 | **Partly.** Wrong file. The precise statement is: quote-level availability is stored for dates the sweep quoted; the full daily calendar is fetched and dropped |
| A2 | 65.2% of scrape rows failed; 0–8% of Dec–Mar nights have ≥3 fresh comps | Re-counted 2026-10-19: 19,516 of 28,900 scrape rows failed (67.5%). Running `pace.comp_anchor` read-only for each home's own comp set over Dec 2026–Mar 2027 gives 10/121, 0/121 and 0/121 nights with ≥3 fresh quotes (8%, 0%, 0%). Pooling all 22 comps instead gives 28/121 (23%) | **Supports**, with a new point: two of three homes get no anchor at all because their comp-set membership is thin, not only because scrapes fail |
| A3 | Code defects in §2.2 are open | `d3e8b92` repointed `cotrip.py` to `api-511x-co.carsprogram.org/events/map-features` with fail-closed quality; set `wind_speed_unit=ms`; added MLK, Presidents Day and Spring Break 2027; made Ikon rows Session-Pass-specific; flattened the SQI curve below 1.0. Reviewer ran the 26 related tests: all pass. Residual risks: (a) the parser marks `berthoud_closed` if the word "closed" appears anywhere in a matching feature's JSON, and the live feed carries values such as "Right shoulder closed"; (b) the Berthoud milepost window is 233–243, while OTIS station 000223 on the Empire-side approach sits at MP 248.7–254.3, so east-side events not labelled "Berthoud" may be missed (UNVERIFIED); (c) the SQI curve still multiplies price by 1.12–1.18 in big-snow years, which no dossier validated; (d) Open-Meteo's free tier is still non-commercial | **Outdated** |
| A4 | Learned elasticity and pace pricing are on only in the candidate `pace_learned_owner_net.yaml` (§2.1) | The current candidate is `pace_v3_anchor_repair.yaml` (peak prior −1.00, others −1.10; `beta_is_all_in: true`; `min_comp_quotes: 3`). Both candidates use channel fee 0.155, management fee 0.25 and turnover $350, so 0.595 is unchanged | **Partly** (names the older candidate) |
| A5 | Live write refused without `--confirm-live-write` | `src/cli/main.py` lines 729–731 | **Supports** |
| A6 | `ANCHOR_MAX_AGE_DAYS` 42, minimum 3 comps | `pace.py` lines 149–150 | **Supports** |
| A7 | Ladder IC ≥ 0.05, hit rate ≥ 0.52; IC is a rank correlation on levels | `config/policies/signals.yaml` lines 6–8 (also `min_observations: 30`); `src/eval/backtest.py` `_rank` | **Supports** |
| A8 | Elasticity luxury prior default −0.8 | `src/elasticity/__init__.py` line 85 | **Supports** |
| A9 | `src/eval/shadow.py`, `src/signals/promotion.py`, `src/signals/comp_movement.py` exist | All present | **Supports** |
| A10 | The booked-price comment was removed from the tree and all remote histories (§2.2) | `main` and `origin/main` are at `bcef02b` (2026-10-19 10:23, "Remove remaining realized-price references"). `git log --all -S` finds no commit containing the figure on any ref. Appendix D item 2 still says the pack "does not edit or purge it" | **Supports**, but Appendix D contradicts it |

## B. Citation spot-check (18 opened, all 2026-10-19)

| # | Source | Claim checked | Result |
|---|---|---|---|
| 1 | PriceLabs billing article | Dashboard from $9.99 for up to 1,000 listings | Supports ("USD $9.99 for up to 1000 listings") |
| 2 | hello.pricelabs.co/market-dashboards | ~350 listings within 15 km | Supports. It is Revenue Estimator Pro, as §1 says; dashboards use a 0.1–50 km radius |
| 3 | open-meteo.com/en/docs | `wind_speed_unit` default km/h | Supports ("kmh"; others ms, mph, kn) |
| 4 | open-meteo.com/en/terms | Free tier non-commercial | Supports |
| 5 | FTC fee-rule FAQ (the eCFR link redirected to a bot wall) | Covers short-term lodging; total price more prominent; effective 2025-05-12 | Supports |
| 6 | Post Independent, 2026-09-24 | −10.9% Nov–Jan bookings, −4.4% occupancy, ADR about −2% | **Partly.** Figures support. The article also attributes the soft start to "lingering effects from poor snow", which Foley calls a "snow hangover", and cites an Inntopia study: after the five worst snow seasons of the past 24 years, the next winter's occupancy rose 2.5%, rates 2.3% and revenue 4.9% on average. The R7 review's statement that the source names gas, airfare and sentiment and "not" snow was wrong |
| 7 | AirROI ski-market blog | Winter Park 72-day lead; occupancy 44.9%→35.8%; ADR +22.2%; RevPAR −4.7%; supply +9.9% | Supports, every figure |
| 8 | AirROI Winter Park page | ADR $437, occupancy 31.5% | Supports (updated 2026-09-12; data as of 2026-07-31) |
| 9 | Ikon FAQ | Full pass no blackouts; Base and Session limited | Supports |
| 10 | Winter Park lift-ticket/pass page | Session Pass blackouts 26–30 Dec 2026, 16–17 Jan 2027, 13–14 Feb 2027; Ikon, Base and Season Pass have none | **Partly.** Session dates match exactly. The page lists no dates beside the other products rather than stating "none", and Ikon's FAQ says the Base Pass has limited blackout dates in general |
| 11 | CDOT hosted CoTrip alerts FeatureServer | Live public layer with structured alerts | Supports (fields include `roadwayclosure`, `startmilemarker`) |
| 12 | NWS API documentation | Public, User-Agent required | Supports |
| 13 | Weatherford & Kimes 2003 (DOI 403; record via search) | Additive pickup beats multiplicative; multiplicative deteriorates beyond about 7 days | **Partly.** Pickup was among the most robust methods (with exponential smoothing and moving averages). The 7-day detail was not confirmed |
| 14 | Garcia, Tolvanen & Wagner 2022 (DOI 403; abstract via search) | Identification from recommendations and implementation delay; DiD stable only pooled | Supports (68(11):7918–7939). The ~60,000-booking figure rests on R2's full read |
| 15 | Pierce & Shoup 2013 (DOI 403; via search) | Elasticity about −0.4 from more than 5,000 price changes | Supports (5,294 changes) |
| 16 | Levin, Lewis & Wolak 2017 (DOI 403; abstract via search) | Aggregation biases elasticity toward zero | Supports (about 10× larger with daily city data) |
| 17 | Canina, Walsh & Enz 2003, eCommons record cited by S1 | 1.74 elasticity; upscale/resort least affected; "in some cuts resort demand did not fall"; "Cornell PDF opened this pass" | **Partly.** Title, year and the headline finding (effects differ by segment) confirmed. The 1.74 figure and the segment detail are not in the accessible excerpt, and the PDF could not be located from the record page, so S1's resort detail is UNVERIFIED |
| 18 | Cornish-Adebiyi v. Caesars, 3d Cir. 2026-07-29 (law-firm alerts) | Revived algorithmic-pricing claim built on pooled nonpublic data | Supports. Opinion text not read |

Functional check: `api-511x-co.carsprogram.org/events/map-features` returns GeoJSON with a
`features` array; route and milepoint fields match what `d3e8b92` parses.

**Tally: 18 opened — 14 support, 4 partly (B6, B10, B13, B17), 0 do not support, 0 dead, 0 fabricated.**

## C. Reviewer's own searches (11)

1. Falk & Scaglione Magic Pass (for R3) → confirmed DiD, domestic +31%, foreign 0.
2. Tom Bacon "Lost and found" (for R1) → original Reuters Events page dead; no copy found.
3. Weatherford & Kimes 2003 → see B13.
4. Garcia, Tolvanen & Wagner → see B14.
5. Levin, Lewis & Wolak → see B16.
6. Pierce & Shoup → see B15; the 62% in-band figure is from the later UCLA two-year brief.
7. Cornish-Adebiyi v. Caesars → see B18.
8. Inntopia "snow hangover" → DestiMetrics has used the term since at least 2018 for post-drought
   booking hesitation; no formal multi-year study beyond the one quoted in B6.
9. Calendar-scrape booked vs blocked validation → vendor accuracy claims only (AirDNA classifier with
   16 signals; Airbtics 96–98%, self-reported, misses about 20% of last-minute bookings); no
   independent validation. Supports S1's endogeneity caution.
10. Single-unit bid price for vacation rentals → **PriceLabs' Minimum Stay Recommendation Engine**
    (https://hello.pricelabs.co/minimum-stay-recommendation-engine/, 2023-09-11): "selling a couple of
    nights 11 months out brings some 'guaranteed revenue'"; "Taking a booking negatively affects the
    probability of neighboring dates getting booked"; "Check-ins and Check-Outs come with additional
    operational costs". Longer minimum stays far out, shorter close in. Also Wyndham's choice-based
    vacation-rental pricing (*Interfaces*, inte.2021.1075), already in R2.
11. Open-Meteo commercial pricing → about $29/month (Standard) or $99/month (Professional) per the
    vendor's Substack and third-party listings; the official page did not render prices. Relevant to
    roadmap item 2's provider choice.

## D. Depth audit

| MUST | Finding |
|---|---|
| Inline citation + access date | PASS for §1–§4 (URLs and dates inline). §5–§9 lean on dossier references, which is acceptable for a synthesis |
| ≥ 40 sources / ≥ 4 classes | PASS by inheritance from R1–R7; S1's own Appendix B names about 30 |
| Primary sources | PARTIAL: several DOIs were not openable; S1 claims the Canina PDF was opened, which this review could not reproduce |
| UNVERIFIED / STALE | PASS, except the Canina resort detail and the 7-day Weatherford & Kimes detail |
| Mechanisms with math | PASS (owner share, bid-price unit conversion, VOI ceiling) |
| Map to modules + owner-net measurement | PASS |
| Honest transferability | PASS, except edge 4.4 (fix 3) |
| Search log | PARTIAL: query→use only, no result notes; acceptable because the dossiers carry full logs |

## E. Traceability and data feasibility of the roadmap

| Roadmap item | Traces to | Depends on data we cannot get? |
|---|---|---|
| 1 Comp scraper + availability | R4 §6 and review R-1; R6 rank 1 and Design 1; R2 rec 1; R5 L06/L07 | No, but Airbnb terms-of-use risk on scraping (R5 L06) and thin comp-set membership for two homes (A2) |
| 2 Signal health | R5 Appendix C items 1 and 15; R4 rec 9; R3 Ikon review; R7 §5 | No. Mostly implemented (A3); residuals remain |
| 3 Pooled additive pickup | R1 R3; R2 rec 5; R3 rec 1; R6 Design 2 | Partly: the market → 5+ BR pooling layer needs item 1's stored availability; own-pace pooling does not |
| 4 Mountain state and calendar bands | R7 recs 2 and 5; R6 Designs 3–4; R5 W01/W08/C01/C02 | No; origin school calendars are public (R5 C01/C02); Texas dates still UNVERIFIED against district sites |
| 5 Owner-net stay controls, logging, shadow | R1 R1a/R1b/R2; R2 recs 2–3; R3 rec 4; R4 §9 shadow arm | No; the dashboard is an operator purchase decision; the management-fee base is an operator confirmation |

Every item traces to at least two dossier sections. None depends on data that cannot be obtained.

## F. Numbered fix list

1. Rewrite §2.2 as a code-status section: what `d3e8b92` changed, the 26 passing tests, and the four
   residual risks in A3. Recast roadmap item 2 and build prompt 2 as "verify live and close the
   residuals". Update §4.3, which still says `events.yaml` lacks the 2027 holidays.
2. Correct A1 everywhere (§1, §2 preamble, competitor-intelligence row, §4.1): name
   `src/scrape/__init__.py`, and say quote-level availability is stored while the daily calendar is
   dropped. Update the failure rate to 67.5% (2026-10-19) and add the comp-set-membership finding.
3. Narrow edge 4.4 and the H2/H7 wording: PriceLabs already prices stay-level opportunity cost and
   turnover in its minimum-stay engine. The defensible part is owner-net economics (0.595 share, fee
   margin, management-fee base) and 14-to-18-guest LOS demand.
4. §4.5 and §9: report Inntopia's own "snow hangover" attribution and its five-worst-snow-years
   result, and treat the soft early pace as a lead-time delay band, not a level cut.
5. §3 H1: $2,427 is the 8-guest all-in; at 14 guests it is $2,577. State that tax and platform guest
   fees are excluded.
6. §3 H4: "natural experiment" → "case study"; state out-of-sample error consistently (worse by
   0.7–3.5% with snow, 9.8% with snow plus gas, 4.4–8.2% at 2–8 weeks); mark the Canina resort detail
   UNVERIFIED and drop "Cornell PDF opened this pass".
7. §4.5: market pace precision is 2.6–3.7× on a 20–40-comp set and about 1.8× at today's scrape
   quality (R2 §2.3).
8. §2.1: name `pace_v3_anchor_repair.yaml` as the current candidate (same fee terms).
9. Replace the garbled wind-gust paragraph with one clear statement.
10. §2.2 Ikon paragraph: the resort page lists no dates for the non-Session products rather than
    stating "none"; Ikon's FAQ says the Base Pass has limited blackouts generally.
11. §2 pickup row: mark the "beyond about 7 days" Weatherford & Kimes detail UNVERIFIED.
12. Add a "Traces to" column to the roadmap (section E).
13. Expand §6 into a table: method, why it looks attractive, why it will not pay at three homes,
    source.
14. Expand §7 into self-contained build prompts: context, files, constraints, acceptance tests, and
    what not to do, in the style of `docs/prompts/*.md`.
15. Appendix D: update items 1 and 2 to the commit and history state in A3 and A10.
16. Appendix C: change "Primary sources" to PARTIAL and record the A1, B6 and B17 corrections.

## Response to review

See `S1_synthesis.md` Appendix E.
