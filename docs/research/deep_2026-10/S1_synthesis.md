# S1: Synthesis — capability gaps, specialist edges, and a profit-ranked roadmap

Date: 2026-10-17. Access date for every URL opened in this pass: 2026-10-17.
Status: reviewed under `V_REVIEW.md` on 2026-10-19 (`reviews/S1_review.md`: ACCEPT WITH FIXES, 18 citations opened, 11 searches, code and data claims re-checked). Fixes applied in place; Appendix E has one row per fix. Code status is as of commit `bcef02b` (2026-10-19).

Research only. No code edits, no commits, no Guesty writes, no live price changes. Guest-level reservation fields were not read.

Inputs: fixed dossiers R1–R7, R6 review, and the wave-1 reviews; the code paths named below, opened in this pass; primary sources listed in Appendix B. Where a dossier and a primary source disagree, the primary source is used and the disagreement is stated.

## 1. Executive summary

Mature revenue management knows four things this engine does not yet use. First, a scarce unit has an opportunity cost: the bid price is the value of waiting, and the posted price maximizes owner net minus that value, not a multiplier on last year's rate (Talluri and van Ryzin, as implemented for capacity 1 in R1 §4.4; the recursion is in the dossier, not yet in `src/pricing`). Second, a booking curve is a forecast of remaining demand, and the forecast that survives small samples is additive pickup — current bookings plus average historical arrivals still to come — not a ratio of on-books share to an expected share (Weatherford and Kimes, *International Journal of Forecasting* 19(3), 2003, STALE: https://doi.org/10.1016/s0169-2070(02)00011-0, accessed 2026-10-17). Third, censored history lies: a night that sold out early at a low price looks like strong demand and a correct price. Fourth, a recommendation is not a result until recommended, listed, and booked prices are logged separately and scored against owner net. Most of that logging already exists (`price_recommendations` stores the model, bounded, move-capped and final price beside the listed price at run time; `recommendation_outcomes` stores the final listed price, whether it was applied, and whether it booked). The daily `shadow_daily` table has never been populated, and the exploration draw and approval delay are not recorded. Garcia, Tolvanen and Wagner (*Management Science*, 2022, STALE: https://doi.org/10.1287/mnsc.2021.4261) identified hotel elasticities from the gap between a system's recommendation and the price a manager actually posted, on about 60,000 bookings. This portfolio has about 100 reservations. The transferable act is to log the three prices now and estimate later.

Most of the rest of airline and hotel machinery solves problems three homes do not have: hundreds of seats, fare fences, origin-destination networks, overbooking, and denied-boarding cost. Continuous class-free fares are already what a short-term rental posts. Overbooking has an unbounded walk cost when the product is one house. Reinforcement learning needs millions of episodes and a trusted simulator; the proving ground is useful, and it is not that.

Generic short-term-rental pricers are ahead of this engine on modelling and on data volume, and weak on the factors that distinguish a 5-plus-bedroom Winter Park house from the town average. PriceLabs' public Market Dashboard starts at $9.99 per month for up to 1,000 listings (https://help.pricelabs.co/portal/en/kb/articles/market-dashboard-billing-and-subscription, accessed 2026-10-17). Their revenue estimator, a different product, uses up to about 350 listings within 15 km (https://hello.pricelabs.co/market-dashboards/, accessed 2026-10-17). The valley's true peer set for these homes is on the order of 14 listings (R4, post-review). No vendor documentation found in R4 uses snow, resort operations, road closures, or origin-market school calendars. Wheelhouse and Airbnb's own tools have the same shape: large cross-market samples, broad comps, and no mountain-operations state. In simulation the current candidate still trails the homes' real rate card (R1–R4, post-review). The specialist edge is not "we have a model and they do not." It is a capacity-matched calendar, a snow-conditioned seasonal posture, origin calendars, holiday stay blocks, and an owner-net objective on the all-in price.

The data that matters, in order, is the data the engine can actually store. A read-only count on 2026-10-19 shows 67.5% of scrape rows failed (19,516 of 28,900). Running the engine's own `comp_anchor` rule for each home over December 2026–March 2027 gives 8%, 0% and 0% of nights with at least three fresh comps; pooling all 22 comps would give 23%, so two homes are blocked by thin comp-set membership as well as by scrape failures. Quote-level availability is stored for the dates the sweep quoted (`comp_snapshots.available`), but the full daily calendar is fetched and dropped: `_enrich_min_nights` in `src/scrape/__init__.py` calls `provider.calendar()` and writes only `min_nights`, and only onto rows that already exist. Market pace, peer pickup, and any fill-based elasticity need that calendar persisted, and even then fill is endogenous to price and host blocks. After that, pooled additive pickup beats the multiplicative pace ratio in `src/pricing/pace.py`. Snow matters as a seasonal state. A re-run of the Granger and season scripts found that lagged weekly snow-water equivalent does not improve traffic forecasts (Granger p = 0.731; out-of-sample traffic-forecast error worse by 0.7–3.5 percent with snow and 9.8 percent with snow plus gas). January 1 snow-water equivalent versus January–March traffic correlates at +0.71, but on eight seasons only; December 15 is +0.12. Gas improves out-of-sample traffic forecasts by about 0.8 percent and is not a price lever. Forward market occupancy (Inntopia's Colorado briefing) and pass-sales disclosures are cheap scenario inputs, not coefficients.

Build first, in this order: make the scraper reliable, widen the thin comp sets, and persist per-day comp availability; verify live the road, wind, holiday and Ikon fixes that commit `d3e8b92` made on 2026-10-19 and close their residual risks; replace the multiplicative pace ratio with additive pooled pickup; then, and only then, a capacity-1 bid price that does not pretend to fix peak-at-ceiling. Effects under about 4 percent of owner net cannot be seen in the field. The minimum detectable effect is about 33 percent without variance reduction, and the live canary is inactive: `src/cli/main.py` refuses a Guesty write unless `--confirm-live-write` is passed after a separately authorized canary, and the default adapter remains dry-run. Small items are proved in `proving_ground_exam/` on a world whose demand equation is not the engine's own.

## 2. Capability gap matrix

Severity is the distance between what would change owner net here and what the engine does today. Transferability is whether the mature method survives three homes, one unit per night, long stays, and about 100 bookings. "Our engine today" cites files opened in this pass. R4's matrix mis-stated comp availability as captured and mis-stated a comp-movement signal as absent; those errors are not repeated. `src/signals/comp_movement.py` does write a 14-day median listed-price lift. Quote-level availability is stored for quoted dates; the daily calendar from `provider.calendar()` is not.

| Capability | Airline best practice | Hotel best practice | Other industries | Generic STR pricers | Our engine today | Gap severity | Transferability |
|---|---|---|---|---|---|---|---|
| Demand forecasting | Unconstrained demand by origin-destination, fare class, and day-to-departure; hierarchical pooling across flights | Arrivals by stay date × length of stay × segment; additive pickup on small samples (Weatherford and Kimes 2003) | Cruise and parking use a booking curve or occupancy band as the controlled state, not a new coefficient every day | Proprietary models on tens or hundreds of thousands of listings; season, day-of-week, holiday, lead, and market occupancy factors | Pace plus a seasonal elasticity prior. `src/pricing/pace.py` `pace_reading` uses portfolio on-books share in a ±3-day window. `src/bookprob/__init__.py` `estimate` shrinks a book rate toward a prior and scales beta by season | High | Transfer the additive pickup and a pooled hazard. Do not transfer network forecasting |
| Unconstraining | Expectation-maximization and choice-based methods so sold-out low fares are not treated as low demand | Projection-detruncation and booking-curve methods on censored hotel history (R2) | Choice models in retail and parking treat a full block as censored, not as zero residual demand | Vendors infer bookings from calendar blocks. That inference confuses "booked" with "not shown in this search tile" (R4) | No unconstraining. `own_sold_evidence` in `src/pricing/pace.py` uses sold prices only, which avoids one spiral path and still treats a sellout as if the observed price were the demand | High | Survival censoring at blocks and minimum stay transfers. Airline EM does not, at this sample size |
| Pickup and pace | Booking curve by reading day; additive pickup beat multiplicative methods in airline tests cited by Weatherford and Kimes | Additive pickup: forecast = bookings on hand + average historical pickup from this reading day to arrival. Pickup was among the most robust methods on the Marriott data (with exponential smoothing and moving averages). A "deteriorates beyond about 7 days" detail attributed to the same paper is UNVERIFIED | SFpark holds a rate when occupancy is inside a band and steps the price only when it leaves (SFMTA data guide, 2018, STALE) | PriceLabs publishes an occupancy rule: low occupancy about 15 days out cuts price on the order of 15 percent (cited in the `pace.py` module docstring; R4) | Multiplicative index `(on_books+0.05)/(expected+0.05)`, then `1 + 0.30*(index-1)` clipped to 0.85–1.25 (`pace_multiplier`). Reference curve `DEFAULT_CURVE` until 60 history rows. One booking at long lead moves the multiplier by about 8 percent (R3 review, carried in R6) | High | Additive or pooled pickup transfers. A second multiplicative market ratio on top of this one does not |
| Elasticity / willingness to pay | Fare adjustment and continuous willingness-to-pay on shopping data; identified where fares vary and volume is large | Garcia et al. (2022, STALE) use the delay between a recommendation and the posted rate. Difference-in-differences only stabilized when hotels were pooled. Their sample is about 60,000 bookings | Pierce and Shoup (*Journal of the American Planning Association*, 2013, STALE) estimate on-street parking elasticity near −0.4 from more than 5,000 price changes (https://doi.org/10.1080/01944363.2013.787307) | Cross-market samples. Airbnb Smart Pricing, in independent work cited by R2, cut price about 5.7 percent and raised revenue about 8.6 percent on mass-market listings — a different product than a 16-sleeper | `src/elasticity/__init__.py` holds a luxury prior (default −0.8) and an inquiry-conversion softener. `src/bookprob` applies a seasonal beta, widens it when pace is behind 0.70, and scales it for all-in fees in `all_in_beta`. Learned elasticity is on only in candidate policies, not the default (`tests/test_pace_pricing.py`) | High | Log the three prices now. Do not fit a slope on ~100 bookings |
| Competitor intelligence | ATPCO and shopping feeds; matching can cost the matcher 3–9 percent in PODS simulations (R1; simulation, not a field result) | Lighthouse-style rate shopping stores the shopped rate, the room type, and restrictions, and separates "no availability" from "shop failed" (R2) | Retail price indexes are quality-adjusted and do not match the cheapest shelf | Broad pools. PriceLabs' estimator uses up to ~350 listings within 15 km. Comp sets inside dynamic pricing can be narrowed, but the published default is not a 14-home peer panel | `comp_anchor` in `src/pricing/pace.py`: median of each active comp's latest `ok` quote, max age 42 days, caller requires at least 3. Failed scrapes do not hide an older good quote. `src/signals/comp_movement.py` records listed-price movement. Read-only store failure was 67.5% on 2026-10-19; Dec 2026–Mar 2027 nights with at least three fresh own-set comps are 8%, 0% and 0% by home | Highest | Capacity-matched quotes and calendars transfer. Matching the cheapest listing does not |
| Forward market occupancy | Industry MIDT and OAG are network products; not the right object here (R1 review narrowed that claim) | Inntopia DestiMetrics: on-the-books occupancy and booking pace for destination lodging, monthly, not listing-level (R2). Colorado August 2026 bookings for November–January arrivals were −10.9 percent versus the prior year (Post Independent, 2026-09-24, quoting Inntopia: https://www.postindependent.com/news/colorado-ski-destinations-see-slow-start-to-winter-bookings/) | — | Market dashboards show occupancy and pace for a radius, usually all bedroom sizes together | No purchased forward series. Own pace is the only on-the-books target, and it is three homes | High | A published aggregate is a scenario prior. A nonpublic pooled feed that other managers also price from is a legal question, not a free covariate (R4 review on *Cornish-Adebiyi v. Caesars*, 3d Cir. 2026-07-29) |
| Length of stay and gaps | A multi-night stay is an itinerary. Accept it when owner net exceeds the sum of bid prices plus the value of any night the stay orphans (R1 §4.4) | Weatherford's length-of-stay linear program beat leg-based EMSR by up to about 2.9 percent in hotel tests, summarized in Zhang and Weatherford (R1; STALE, and the gain depends on load factor) | Cruise control protects holiday departure weeks with minimum-stay and gap rules rather than repricing every cabin every hour (R3) | PriceLabs documents orphan-gap relaxation and gap check-in rules (R2, vendor docs) | `src/min_stay/__init__.py` looks up season × lead, then relaxes an orphan to the gap length when that is shorter. It is a policy table (`min_stay_rules` in the default policy), not a value comparison. The orphan discount is a flat cut, not a demand estimate (R2) | Medium | Stay-level displacement transfers on peak weeks. It is near zero in midweek January |
| Group and displacement | Displacement is the bid price of the inventory a group would take | The same arithmetic, plus a human accept/reject for the group block (R2) | Weddings and reunions in resorts are the hotel group problem in miniature | Weak. Tools price the night; they do not price a two-home reunion against the alternative of selling the homes separately | No group model. A 5-plus-bedroom house is itself the group product. Twins are not jointly priced | Medium | A two-home displacement check transfers. A group-RM system does not |
| Overbooking and cancellation | Overbooking is core. The protection level trades denied-boarding cost against empty seats | Hotels overbook against no-shows and cancellations, with a walk cost | Cruise and cargo overbook perishable capacity when the walk cost is bounded | Some channel controls; not a three-unit practice | Not built. Correctly. `src/pms` sync health is the analogue of a walk, and a double-booked house is not a $200 voucher | Low as a gap; do not close it | Cancellation-adjusted pace transfers. Overbooking does not |
| Price experimentation | Switchback and sandbox tests. Iberia's field sandbox mostly documented how hard measurement is (R1) | Garcia et al. exploit the fact that managers do not post the recommendation immediately | SFpark changed rates about every six weeks, by block and time band, and published the rule | Vendor lift claims are mostly uncontrolled. The independent Airbnb result above is the cleanest external number, and it is mass-market | `proving_ground_exam/` runs paired seeds. `price_recommendations` and `recommendation_outcomes` record recommended, final, listed and booked prices; `shadow_daily` exists but is empty. Live push defaults to dry-run. There is no authorized canary | Medium | Switchback by check-in week can cut variance. It still will not see a 2 percent effect |
| Simulation and validation | PODS: closed-loop, competitive, multi-airline. Gains are inside the simulator (R1 §11.1) | The same warning: a model tested on itself flatters itself | SFpark published the occupancy rule and the data guide so a third party could recompute the rate change | Opaque. Vendors do not publish the demand equation the lift was measured against | `proving_ground_exam/` has calibration v2 and scenarios including drought, record snow, late opening, early closure, holiday shift, I-70 closure, scrape outage, scrape degraded, price war, supply surge, stale PMS, and recession. Historical versions were 2–3× too cheap versus real rates; v2 recalibrated that (shared context) | Medium | Copy the misspecification tests (over-dispersion, strategic waiters, a matcher competitor). Do not copy PODS scale |
| Human override | Analyst "user influences" help on events and groups and hurt when they are free-form (R1) | On 1,752 hotels, overrides improved group and event forecasts and hurt transient forecasts (Koupriouchina, van der Rest and Schwartz, *Tourism Economics* 2023, as cited in R2; the journal abstract was not re-opened here) | — | Operator knobs: base price, minimum stay, last-minute discounts | Guardrails, an explain path (`src/explain`), and receipts. Overrides are not logged as a demand influence with an ex-post score | Medium | A structured, scored influence transfers. A free-form price edit does not |
| Fairness and reference price | Personalised fares drew political cost (Delta / Fetcherr episode, R1; press, not a court holding) | FTC total-price rule, effective 2025-05-12, requires the total price of short-term lodging, including mandatory fees, to be shown more prominently than other prices (16 CFR 464: https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-464, accessed 2026-10-17) | SFpark published the band so the price change was a rule, not a surprise | Platforms show all-in prices. Tools that optimize the nightly rate alone optimize the wrong object | `owner_terms` and `all_in_beta` in `src/pricing/pace.py` scale elasticity by nightly / (nightly + fees per night) and maximize owner share of the nightly rate plus fee margin. The fee stack is the one in the shared context: cleaning, per guest, insurance. The objective is right. The reference guests use is other all-in totals for the same stay, not the town ADR | Medium | All-in and per-guest framing transfer. Personalised prices do not |
| Data-stream breadth and value ranking | Airlines buy shopping, schedule, and search feeds and then throw most of them out with a forecast test | Hotels buy STR / DestiMetrics pace and rate-shop feeds. Metric surveys still show RevPAR dominant and profit metrics rare (R2) | Value-of-information caps the worth of a noisy stream before anyone fits it (R6 Part A) | Many feeds, few mountain-specific ones. Gas, geopolitics, and search are not in the public factor lists | Collectors exist for weather, SNOTEL, resort, CDOT, calendars, flights, ENSO, and intent (`src/signals/collectors/`). Promotion is experimental → shadow → active at information coefficient ≥ 0.05 and hit rate ≥ 0.52 (`config/policies/signals.yaml`, `src/signals/promotion.py`). R6 ranks comp repair first. The information coefficient in `src/eval/backtest.py` is a rank correlation on levels, not on residuals, and the ladder's null-promotion rate in R6's Monte Carlo was about 27–31 percent | High | Rank by value of information and a residual test. Do not promote on a raw correlation with bookings |

### 2.1 How the engine prices today

`src/pricing/pace.py` is off unless `models.pace_pricing.enabled` is set. The default policy leaves it off; the current candidate `config/policies/candidates/pace_v3_anchor_repair.yaml` (and the older `pace_learned_owner_net.yaml`) turns it on together with learned elasticity, with priors −1.00 at peak and −1.10 elsewhere on the all-in price. When it is on, the reference is the median competitor quote, the pace index multiplies that reference, and the search maximizes booking probability times owner net. Owner share of the nightly rate is `1 − channel_fee − management_fee`. With the candidate's 0.155 channel fee and 0.25 management fee, that share is 0.595 (`owner_terms`). Price shifts in a bid-price recursion have to be divided by 0.595 if the continuation value is in owner-net dollars and the grid is in nightly rates (R1 Appendix C). A bid price computed on gross rate will hold peak nights even harder against the ceiling.

The ceiling path is separate. Until 2026-10-19, `config/policies/conditions.yaml` mapped a snow-quality index of 0.62 to a price multiplier of 0.78, annotated as the drought-Christmas knot: a 22 percent price cut. Commit `d3e8b92` made the curve neutral below 1.0; it still raises price 12–18 percent at an index of 1.2–1.3, which no dossier validated. The literature number people have used for a snow effect is much smaller, and it is the wrong object: Parthum and Christensen's Colorado elasticity is a within-property-month response to resort-reported snow depth, so month fixed effects absorb the season (R5 review, carried in R6). AirROI's vendor panel for the 2025-26 drought shows Winter Park occupancy 44.9 percent to 35.8 percent, ADR up 22.2 percent, and RevPAR down 4.7 percent, with supply up 9.9 percent (https://www.airroi.com/blog/ski-market-winter-2026-2027-booking-pace, accessed 2026-10-17; vendor scrape, not an audit). A 22 percent price cut is not a −7 percent revenue effect, and the market's own response in that drought was to hold rate and lose occupancy.

`src/eval/backtest.py` is explicit that replaying recommended prices on nights that booked at the listed price is not a performance metric. It assumes bookings do not respond to price, so any recommendation above the listed rate "wins" by arithmetic. That warning is the right one to keep in front of every later claim.

### 2.2 Data-path defects: found by this pack, fixed in code on 2026-10-19, residuals open

The reviews found four feeds or configs storing a confident wrong value and one public-repo leak.
Commits `d3e8b92` (10:20) and `bcef02b` (10:23) on 2026-10-19 changed the code; the 26 related tests
pass. This section records what changed and what is still open. It does not authorize a live change.

| Defect as found | Change in `d3e8b92` | Still open |
|---|---|---|
| `src/signals/extractors/cotrip.py` called `cotrip.org/api/alerts`, an HTML app shell; a non-JSON body was searched for keywords and stored as "not closed" at good quality | Calls the CARS 511 GeoJSON feed `api-511x-co.carsprogram.org/events/map-features` (returns JSON; checked 2026-10-19). A non-JSON body returns `quality: unavailable`, and `cdot.py` stores `QUALITY_UNAVAILABLE` | Live behaviour on a real closure is unverified. The parser sets `berthoud_closed` if "closed" appears anywhere in a matching feature's text, and the feed carries values such as "Right shoulder closed", so a shoulder closure can raise the full-closure flag. The milepost window is 233–243; whether it covers the Empire-side approach (OTIS station 000223 is at MP 248.7–254.3) is UNVERIFIED. CDOT's hosted CoTrip FeatureServer, with a `roadwayclosure` field, is a structured alternative (https://maps.codot.gov/server/rest/services/Hosted/CoTrip_Alerts_Polyline_%28Live%29_Public_View/FeatureServer/0) |
| `src/signals/collectors/weather.py` multiplied Open-Meteo gusts by 2.237 (m/s → mph) without setting a unit; the API default is km/h (https://open-meteo.com/en/docs), so stored gusts were about 3.6× too high | Requests set `wind_speed_unit=ms`, so the conversion is now correct | Open-Meteo's free tier is non-commercial (https://open-meteo.com/en/terms). Either buy a plan (about $29–99 a month, per the vendor's Substack and third-party listings; official page did not render prices) or move to the free NWS API (https://www.weather.gov/documentation/services-web-api; User-Agent required) |
| `config/policies/events.yaml` had only Christmas for 2026-27 | Adds MLK weekend (2027-01-15 to 01-18), Presidents Day weekend (2027-02-12 to 02-15) and Spring Break peak (2027-03-06 to 03-21) | Signal strengths (0.75, 0.80, 0.85) are priors. Texas spring-break dates are still UNVERIFIED against district sites |
| `config/resort/winter_park.yaml` listed blanket "Ikon" blackouts that matched no product | Only Ikon Session Pass blackouts remain: 26–30 Dec 2026, 16–17 Jan 2027, 13–14 Feb 2027 | The resort page lists these Session dates and no dates beside the other products; Ikon's FAQ says the Base Pass has "limited blackout dates" in general (https://www.ikonpass.com/en/faq). Which product guests hold is not public |
| `config/policies/conditions.yaml` cut price to 0.78 at drought snow | Neutral (1.00) at or below normal snow | Still ×1.12–1.18 at SQI 1.2–1.3; unvalidated upside |
| A `default.yaml` comment, and later a `src/pms/sync.py` docstring, printed a booked price | Removed; `bcef02b` removed the last reference. `main` and `origin/main` contain no commit with the figure on any ref (checked 2026-10-19) | Clones and provider-side caches made before the rewrite may still hold it |

### 2.2a Code status after the research-fixes branch (2026-10-19)

The residuals in the table above were closed in code on branch `research-fixes-2026-10-19`. The historical table stays as the record of what the morning audit found.

- CoTrip classification uses CARS `headlinePhrase` category and code, plus quantity labels. A category-3 shoulder or lane phrase does not set `berthoud_closed`. The US-40 window is 230.0–254.3 in `config/policies/access.yaml` (OTIS station 000223 east end; Fraser at milepost 227 is outside). I-70 full closures east and west of milepost 232 are stored as experimental signals and are not read by `access_risk`. A live read on 2026-10-19 returned `ok` with a shoulder/lane access risk and no full US-40 closure (`docs/reports/cdot_health_2026-10-19.json`).
- Forecasts come from `api.weather.gov`. Open-Meteo is not called. Historical days are not filled by this collector; SNOTEL remains the snow record. Wind in `wmoUnit:m_s-1` converts by 2.237.
- The SQI curve is 1.00 at 1.2 and at 1.3 as well as below 1.0.
- Federal holiday windows are generated (Christmas 20 Dec–2 Jan, MLK and Presidents Friday–Monday, Thanksgiving Wednesday–Sunday). School-break rows in `config/calendars/school_breaks.csv` are unverified and are not a price input. Ikon Base Pass blackouts at Winter Park were re-read on the Ikon product page on 2026-10-19; the Session Pass page URL returned 404.

Phases 1 and 8 of the build prompt (fresh dossier re-reviews and the unfinished literature fixes) are not done. They are listed as operator questions in `docs/reports/RESEARCH_FIXES_LEDGER_2026-10-19.md`.

## 3. Hypothesis verdicts H1–H7

The wording below is the post-review wording. It is not softened and it is not upgraded.

### H1. Winter Park is a middle-class market. Verdict: Partly.

AirROI's all-size Airbnb panel, trailing twelve months through July 2026, pages the dossier read as updated 2026-09-12, puts Winter Park average daily rate at about $437, Breckenridge at about $581, Vail at about $819, and Aspen at about $1,071 (R7 §3.1; the Winter Park page re-opened here still shows $437 ADR and 31.5 percent occupancy: https://www.airroi.com/airbnb-data/united-states/colorado/winter-park, accessed 2026-10-17). Breckenridge is about 1.33 times Winter Park, not a different planet. Vail is about 1.9 times and Aspen about 2.5 times, and those gaps are largest in the top decile, not in the mean.

That town-wide average is the wrong product. The homes' real January comparable set, the curated large-home panel rather than the broad market sweep, is about $2,073 a night (R7 review; the broad sweep's January median of about $1,684 mixed in a thin, small-unit sample and is the figure not to use). A group that splits the house is buying a per-guest price. At a roughly $2,000 nightly rate, three nights, and the fee stack in the shared context, the all-in is on the order of $184 to $303 per guest-night depending on party size (R7 §3.4: all-in $2,427 a night at 8 guests, $303 per guest-night; $2,577 at 14 guests, $184 per guest-night; lodging tax and platform guest fees excluded). That is a mid-range hotel room per person, which is why a "middle-class" town can clear a luxury nightly rate. Income surveys do not settle the label: the Grand County figure of 60 percent of visitors over $100,000 household income is UNVERIFIED (R7, a search extract of a county PDF), and it is not comparable to Aspen or Vail instruments.

What to do with the verdict: price per guest and the all-in total, against other 14-to-18-guest houses. Do not anchor on the town ADR of $437.

### H2. Generic pricers miss the factors that move this market. Verdict: Partly.

No vendor documentation in the R4 teardown uses snow, resort operations, road closures, or origin-market school calendars. Comp pools are too broad for this product: PriceLabs' published estimator uses on the order of 350 listings within 15 km, and the valley has about 14 true peers for these houses. That part of the cold-call claim holds.

The other part does not. PriceLabs, Wheelhouse, and Airbnb run real models on a volume of bookings this engine will not see. They are ahead of this engine on modelling and on data volume. In the proving-ground comparison the candidate still trails the homes' real rate card. The specialist thesis is not that the generic tools are empty. It is that their strength (volume, broad comps, day-of-week and lead factors) is the wrong strength for a 14-peer, snow-and-calendar market, and that their dashboard is still worth buying as a shadow benchmark (section 8). They are also not naive about stays: PriceLabs' dynamic minimum-stay engine (live since September 2023) weighs the "guaranteed revenue" of a short booking against the lower booking probability of neighbouring nights and counts check-in costs (https://hello.pricelabs.co/minimum-stay-recommendation-engine/, accessed 2026-10-19).

### H3. There are too many factors; the problem is picking them. Verdict: Supported.

R6's value-of-information ceiling is the right scale. If log-price error has a standard deviation of about 20–25 percent, the expected loss from that error is on the order of 3–5 percent of revenue, because the loss is quadratic in the percentage price error (R6 §A.1). One more coefficient cannot be worth more than that, and structural choices (which nights are offered as a stay) sit outside the ceiling because they change the product. With about 100 bookings, the only learned factors that are safe are a pooled pace target and, later, a single elasticity, both shrunk hard toward a prior. Everything else — snow state, holiday blocks, road closures, pass rules — should be a deterministic or scenario input with a neutral fallback, not a fitted daily weight. The promotion ladder as configured will not enforce that: information coefficient 0.05 and hit rate 0.52 on level correlations promoted null signals about 27–31 percent of the time in R6's 4,000-draw Monte Carlo.

### H4. Gas prices are suppressing Front Range drive-up demand. Verdict: No winter effect detected; bounded small.

R7's winter elasticity of Berthoud Pass traffic (CDOT station 000223) to real Colorado gasoline is +0.06 with interval [−0.07, +0.19], effective sample about 23 seasons. The monthly rows are not 23 independent experiments: about 85 percent of the year-over-year gas variance is between seasons, so the honest n is seasons. A 30 percent gas rise is at most about 4 percent of winter traffic inside that interval. The re-run out-of-sample check is consistent with that bound: adding gas improves the traffic forecast by about 0.8 percent. That is not a price lever.

Summer is suggestive only. The 2026 path is a case study, not a natural experiment, and it cuts against the winter claim: in January and February 2026 real gas was 14–20 percent cheaper than a year earlier and Winter Park traffic and lodging tax still fell, with Berthoud snow-water equivalent well below the prior year (R7 §2.4). Snow-water equivalent dominates the same regressions: about +1.3 to +2.2 percent traffic per inch above the day-of-year normal.

Fuel's share of the trip is not the same as the elasticity. For a Denver group, fuel is about 1–2 percent of the stay. For a drive-in group from Texas, Kansas, or Oklahoma it can be 7–21 percent (R7). Weigh gas by origin, in a scenario, not as a town-wide multiplier.

Canina, Walsh and Enz (*Cornell Hotel and Restaurant Administration Quarterly*, August 2003, STALE) found that branded-hotel room demand fell as gasoline prices rose over 1988–2000: a 1 percent gas increase associated with about a 1.74 percent drop in rooms sold, largest for highway and economy hotels and smallest up the price ladder (https://ecommons.cornell.edu/entities/publication/224b4575-bbd9-441b-b5dd-810193316c02; the review could open only the record page, which confirms that effects differ by segment). The 1.74 figure and the segment ranking come from the Cornell press summary (R7 §2.6); the claim that resort demand did not fall in some cuts is UNVERIFIED. These homes sit in that least-affected corner, and the study is national hotels, not ski towns. Levin, Lewis and Wolak (*AEJ: Economic Policy* 9(3), 2017, STALE: https://doi.org/10.1257/pol.20140093) show why a monthly aggregate elasticity is biased toward zero: time aggregation and the loss of period fixed effects. R7's "no winter effect" is an upper bound from a biased-toward-zero design, not a proof that a daily origin-weighted effect is exactly zero. It is still too small to price on.

The new forecast result belongs here as well. Lagged weekly snow-water equivalent does not Granger-cause traffic (p = 0.731) and makes out-of-sample traffic-forecast error worse: by 0.7–3.5 percent with snow, 9.8 percent with snow plus gas, and 4.4–8.2 percent at 2–8-week horizons (`b4_granger.py`, re-run 2026-10-19). Season-level snow on 1 January versus January–March traffic is r = +0.71 on n = 8 seasons only; the 15 December reading is r = +0.12. Snow is a seasonal state. It is not a lagged weekly coefficient to drop into the price.

### H5. About 70 percent of annual revenue is earned in winter. Verdict: Supported for Winter Park town lodging, with a scope caveat.

Town of Winter Park lodging-sector sales, converted from the town's monthly sales-tax reports at the rate then in force, put November–April at 71.7 percent of the lodging year across five seasons (2021-22 through 2025-26), range 69.5–72.8 percent. December–March is 61.4 percent (range 59.8–62.3). The August 2026 report, re-opened here, shows lodging tax for that month down 22.8 percent versus August 2025 (https://wpgov.com/wp-content/uploads/2026/10/2026-08-Sales-Tax-Report-collected-Sep-26.pdf, accessed 2026-10-17). That is a summer month. It supports "this season looks soft." It is not itself the winter-share estimate.

Fraser lodging-equivalent taxable sales are about 52 percent November–April, and Grand County about 49 percent (R7 §1.2, Colorado Department of Revenue taxable sales, not lodging alone). The practitioner's 70 percent is a Winter Park town lodging fact. It is not a county fact and it is not yet a fact about these three homes: the operator database does not hold a complete May–April year of reservations for any of them (R7 §1.4).

Caveat, and it is material: the town's report books lodging managed by a property-management company to the company's office location. The series is "lodging tax remitted to the Town of Winter Park," not "nights slept inside the town boundary." Marketplace remittance may be coded differently. UNVERIFIED how the town splits those channels.

### H6. Airlines and hotels have used sophisticated revenue management far longer than short-term rentals. Verdict: Supported, with a transfer caveat.

Airline practice runs from overbooking in the late 1950s through expected-marginal-seat-revenue, origin-destination control, choice-based revenue management, and fare adjustment. Hotel practice at chain scale is a generation behind the airlines and a generation ahead of a three-home engine. Short-term-rental dynamic pricing as a product category is roughly a decade old. That history is real.

Most of the sophistication solves volume and network problems these homes do not have: many seats, many fare products, connecting itineraries, and a denied-boarding cost that is finite. The transferable core is short. Bid price equals value of waiting. Price equals that value plus a markup for willingness to pay, in owner-net units. A multi-night stay is accepted against the sum of those values. Censored demand is unconstrained. Pickup is additive. The recommendation, the listed price, and the booked price are logged apart. The 2–5 percent of revenue that airlines attribute to revenue management is rarely measured as an experiment (R1 §11.1, trade commentary). Magnitudes in the dossiers are priors.

### H7. A hyper-specialized engine for one market can beat generic pricers. Verdict: Partly.

The edge that survives is specific: capacity-matched comps, snow-conditioned pace (a seasonal state and a booking curve, not a weekly lag), origin-market school calendars, holiday stay blocks, and an owner-net objective on the all-in price. Stay-level opportunity cost by itself is not an edge; PriceLabs already prices it in minimum-stay rules. It is not gas, not day-of-week (generic tools already have day-of-week), and not international or geopolitical feeds. Section 4 states the edges so each one can be falsified. Section 6 states the methods that look like specialization and will not pay.

## 4. Specialist edges

Five edges. Each is defensible only while the falsifier has not been observed. None of them is a license to fit another coefficient on a hundred bookings.

### 4.1 Capacity-matched comps, with the calendar stored

The peer set is about fourteen 5-plus-bedroom houses, not 350 listings in a 15 km disk and not the town ADR of $437. A median of those peers, fresh, is a reference price a generic pool will wash out. The calendar — which nights are still bookable, at what minimum stay — is the demand signal the quote alone is not, because a high asking price on a house that has been booked for weeks is not a comp.

Why it is defensible: the product is scarce and unlike the median listing. Generic tools can narrow a comp set, and some operators do. The published default does not, and this engine's own scraper does not keep the daily calendar it already fetches. Two of the three homes also have too few active comps in their own sets to reach three fresh quotes on any December–March night.

Falsifier: after availability is persisted, a capacity-matched median does not beat a broad-market percentile as a predictor of whether these homes book, in a rolling-origin test that holds the price decision out. Or the peer set cannot be kept above three fresh quotes, in which case the edge is real and still unusable.

### 4.2 Snow as a seasonal state on the booking curve, not a weekly lag

The Granger re-run is the constraint. Lagged weekly snow-water equivalent does not improve a traffic forecast. The 1 January snowpack versus January–March traffic correlation is +0.71 on eight seasons, which is a season-level fact with a wide interval, and the 15 December reading (r = +0.12) says the early-winter number is not yet that fact. Use the seasonal state to choose the proving-ground world and to set how wide the price band is. Use realized terrain and lift status, close in, for what the listing should claim. Do not multiply price by 0.78 because the index printed 0.62.

Why it is defensible: generic pricers do not take this state, the 2025-26 drought moved occupancy and RevPAR in the vendor panel, and a weekly coefficient has already failed a forecast test.

Falsifier: a season-blocked test in which a snow-state band changes owner net in the wrong direction on drought and record-snow worlds, or a later sample (more than eight seasons, or these homes' own winters) in which January snowpack and winter occupancy are unrelated. Also falsified if the implementation smuggles the weekly lag back in.

### 4.3 Origin-market calendars and holiday stay blocks

Winter Park winter demand is a Denver-and-Front-Range school calendar plus a few named weekends, on a 72-day winter lead (AirROI 2025-26 winter lead time for Winter Park: 72 days; https://www.airroi.com/blog/ski-market-winter-2026-2027-booking-pace, accessed 2026-10-17). Until 2026-10-19 the engine's `events.yaml` knew only Christmas for 2026-27; commit `d3e8b92` added MLK, Presidents Day and Spring Break 2027 as priors. A generic day-of-week factor does not know which Monday is a school holiday in Jefferson County.

Why it is defensible: the dates are public, the lead time is long enough that the block has to be in the price before December, and no vendor documents this input.

Falsifier: a residual test, after a correct seasonal curve, in which named holiday blocks do not move booking probability for these homes. Or the blocks fire on the wrong segment (a Texas spring-break week applied to a Denver-origin prior). Dates being right is not the same as magnitudes being right; the magnitudes stay at a prior until the residual test passes.

### 4.4 Owner net on the all-in price, for a 14-to-18-guest stay

Guests compare totals. The FTC rule requires the total price, including mandatory fees, to be the prominent price for short-term lodging (16 CFR 464, effective 2025-05-12). Owner net per nightly dollar on the candidate's Airbnb economics is 0.595 after channel and management fees, against a higher share on a direct booking if card cost is the only substitute fee (R2 §6.2; the 3 percent card assumption there is marked as an assumption, not a measured processor rate). A one-night orphan and a seven-night stay are different products because the fee stack is a smaller share of the longer stay. The accept/reject decision for a stay is the sum of the nights' continuation values, not a flat orphan discount.

Why it is defensible, narrowed after review: generic tools already handle part of the stay decision. PriceLabs' dynamic minimum-stay engine (since 2023) trades a short booking's guaranteed revenue against neighbouring nights' lower booking probability and counts check-in costs. What it does not document is the owner's economics: the 0.595 owner share of the nightly rate after channel and management fees, the fee margin per stay, whether the management fee is charged on fees, and the demand for one-night and short stays from 14-to-18-guest parties. The edge is pricing the stay decision in owner-net dollars on this product, not having a stay decision at all. The arithmetic is in `owner_terms`; the stay decision is not yet.

Falsifier: in paired proving-ground runs, stay-level control does not raise owner net on holiday weeks and does raise cancellations or stranded nights enough to offset it. Also falsified if the management fee is charged on fees as well as on the nightly rate, which changes 0.595, and nobody has confirmed that base with the operator.

### 4.5 A published forward pace number, used as a band, not as a coefficient

Inntopia's August 2026 Colorado briefing said bookings made that month for November–January arrivals were 10.9 percent below the prior year, and November–February occupancy on the books was 4.4 percent below, with early-winter rates down about 2 percent (Post Independent, 2026-09-24, quoting Tom Foley at Inntopia). The same article attributes the slow start partly to "lingering effects from poor snow", a "snow hangover" in Foley's words, and partly to economic pressure, airfares and gas. It also reports Inntopia's own study: in western winters after the five poorest snow seasons of the past 24 years, occupancy rose 2.5 percent, rates 2.3 percent and revenue 4.9 percent on average. Western-mountain aggregates in the same news cycle are a different geography and should not be substituted for the Colorado figure. This is a timing shift for the season prior: after a drought, guests book later, so "on pace" is a lower early pace than last year's curve, and the season has historically finished better than the bad year. It is not a reason to cut every open night by 10.9 percent.

Why it is defensible: it is the object hotels pay DestiMetrics for, it is cheap relative to a custom scrape, and it is independent of the three homes' own noise. Market pace with a 20-to-40 comp set is about 2.6–3.7 times more precise than own pace, not 10 times, and about 1.8 times at today's valid-row rate (R2 §2.3). Fourteen peers will land at the low end of that range.

Falsifier: the purchased or dashboard series has no 5-plus-bedroom cut, or its geography is the western aggregate rather than Winter Park, or a shadow year shows it lagging the homes' own bookings with the wrong sign. Vendor occupancy is not these homes' occupancy.

## 5. Roadmap

The ranking is expected owner-net profit per unit effort, not a claim that any item will produce a
field-detectable lift. Impact ranges overlap inside the single 3–5% information ceiling (R6 §A.1);
they are priors. Every item has a simulator gate because the field MDE is about 33% (R1 §9.5: a 4%
effect needs about 4,000 weeks per arm) and the canary is inactive.

| Rank | Build item | Impact / confidence | Prerequisites and module | Proving-ground test, field measure, kill criterion | Traces to |
|---:|---|---|---|---|---|
| 1 | Repair the comp scraper, widen the thin comp sets, and persist per-day calendar availability, min-stay, restrictions and quality | 1–4% structural / medium | `src/scrape/__init__.py` (`_enrich_min_nights`, `_write`), `src/scrape/providers.py` (`calendar`), `comp_set_members`, `src/comps/`; no new vendor first | Outage, non-JSON, thin-panel and host-block worlds; field: share of Dec–Mar nights with ≥3 fresh own-set comps per home (today 8%, 0%, 0%); kill if matched peers do not improve held-out booking or anchor forecasts, or if stale data can raise price | R4 §6 and review R-1; R6 rank 1, Design 1; R2 rec 1; R5 L06/L07 |
| 2 | Verify the signal-health fixes from `d3e8b92` live and close the residuals: shoulder-closure false positives, the Empire-side milepost window, the unvalidated big-snow uplift, and the weather licence | avoided silent loss / high for correctness | `src/signals/extractors/cotrip.py`, `src/signals/collectors/cdot.py`, `src/signals/collectors/weather.py`, `config/policies/conditions.yaml` | Fixtures with shoulder-only, lane-only and full closures; an east-side event without the word "Berthoud"; field: health receipts show `unavailable` rather than zero on bad payloads; kill any signal that moves price while unavailable | R5 Appendix C items 1 and 15; R4 rec 9; R3 review (Ikon); R7 §5; S1 review A3 |
| 3 | Replace the multiplicative own-pace ratio with pooled additive pickup and stay-level residuals | 0.3–2% / medium | `src/pricing/pace.py` (`pace_reading`, `pace_multiplier`), `pacing_snapshots`; the market layer needs item 1 | Misspecified demand worlds with strategic waiters and sellouts; shadow forecast loss and owner net; kill if the peak-ceiling share worsens or one booking moves price more than a set bound | R1 R3; R2 rec 5; R3 rec 1; R6 Design 2 |
| 4 | Add mountain state and calendar bands: snow/resort operations, origin school breaks, holiday blocks, access windows, and a post-drought timing band | 0.2–1.5% each, overlapping / low–medium | repaired feeds (item 2); neutral fallback; 72-day winter curve | Drought, record-snow, late-opening, closure and shifted-school-break worlds; shadow by check-in week; kill on wrong-sign residuals or stale directional output | R7 recs 2 and 5; R6 Designs 3–4; R5 W01/W08/C01/C02 |
| 5 | Owner-net stay controls (R1a demand model, R1b capacity-1 bid price, stay-level displacement) plus filling the existing logging and a shadow benchmark | 0.2–1.5% / medium | `owner_terms`, `src/min_stay`, `src/leakage`, `src/compose`; `price_recommendations`, `recommendation_outcomes`, `shadow_daily` (exists, empty); PriceLabs dashboard optional at $9.99 | Paired seeds for gap, LOS, R1b and R1a separately; field: owner net per home and the share of recommendations with an outcome row; kill if net falls on peak worlds or the fee base is unconfirmed | R1 R1a/R1b/R2; R2 recs 2–3; R3 rec 4; R4 §9 |

No item depends on data that cannot be obtained. Item 1 carries Airbnb terms-of-use risk (R5 L06);
item 4's Texas school dates are still UNVERIFIED against district sites; item 5's dashboard is an
operator purchase and its 0.595 share needs the operator to confirm the management-fee base.

Do not promote paid market pace, AirDNA, lift-ticket, gas, or search feeds until item 1 provides a
credible target and the row-level R6 protocol passes. The PriceLabs dashboard is a cheap shadow
benchmark, not a price authority and not a contradiction of H2.

## 6. What not to do

| Method | Why it looks attractive | Why it will not pay at three homes | Source |
|---|---|---|---|
| Airline-style continuous fare classes, EMSR, LP bid prices | Decades of airline evidence; +1–2% for continuous pricing | A short-term rental already posts a continuous price; LP bid prices are asymptotic in volume | R1 §10 |
| Network origin–destination control | 2–4% above about 85% load in airlines | Applies only to holiday and peak weeks here, and the capacity-1 recursion (item 5) already captures it | R1 §4.4 |
| Overbooking | Core airline and hotel lever | A walk cost for a 16-guest house is unbounded; one double booking erases a season's gain | R1, R2 |
| Reinforcement learning or deep RMS | Vendor claims of 5–7% | Needs millions of episodes and a trusted simulator; we have about 100 bookings | R1, R3 |
| Per-night bandits or Thompson exploration as the learning plan | Learns elasticity "for free" | About as many arms as observations; even a season of randomized nights gives SE(β) ≈ 0.7 | R3 §10.2 |
| A large macro, geopolitical or gas coefficient stack | The news is full of it | H4: no winter effect detected, bounded small; a 30% gas rise moves winter access traffic by at most about 4% | R7 §2.7, R6 |
| Raw comp fill as booked demand | Many more observations than our own bookings | Comp prices are set in response to demand, and blocks look like bookings; vendor accuracy claims are self-reported | R3 §10.2, R6 C2 |
| The Parthum & Christensen coefficient as a drought multiplier | The only quantified STR snow elasticity | It is a within-month, resort-depth, 2014–17 estimate; the market held rate in the 2025-26 drought | R5 §1, R6 C6–C7 |
| A second multiplicative market-pace ratio on top of own pace | Market pace is more precise | Compounds the ratio's instability; use pooled additive pickup instead | R2 §5.2, R3 §3.3 |
| Matching the cheapest comp | Simple and defensive | PODS simulations show the matcher loses 3–9% | R1 §6.2 |
| Pooled nonpublic data from a shared vendor | More data than any scrape | Antitrust exposure after *Cornish-Adebiyi v. Caesars* and the RealPage judgment | R3 §12.3, R4 §4.4 |
| Treating the inactive canary or simulated revenue as evidence of field lift | It is the only number available | Simulated revenue is evidence about a synthetic world; the field cannot see effects under about 33% | R1 §9.5, shared context |

## 7. Build prompts

Each prompt is written to be pasted into a fresh implementation session in `~/code/harness`. All
four share these rules: the repo is public; research and pricing evidence stay in `docs/`; do not
write to Guesty, do not change live prices, do not activate the canary, and do not commit unless the
operator asks; open `data/wp_pricing.db` read-only for analysis; never print guest fields, Guesty
ids or booked revenue; run the test suite with `.venv/bin/python -m pytest -q` before reporting.

### 7.1 Comp data spine (roadmap item 1)

**Context.** The comp anchor (`src/pricing/pace.py` `comp_anchor`) needs at least three fresh `ok`
quotes from a home's own comp set within 42 days. On 2026-10-19, 67.5% of scrape rows failed and the
three homes had such an anchor on 8%, 0% and 0% of December 2026–March 2027 nights. Pooling all 22
comps would reach 23%, so comp-set membership is also binding. `provider.calendar()` in
`src/scrape/providers.py` returns 12 months of per-day `available` and `min_nights`, and
`_enrich_min_nights` in `src/scrape/__init__.py` keeps only `min_nights`, only on rows that already
exist. `comp_snapshots.available` today reflects quote outcomes, not the calendar.

**Goal.** Store the calendar, separate the reasons a night has no quote, and raise anchor coverage
without letting stale or failed data move price.

**Do.**
1. Add a per-day calendar table (or columns) keyed by comp, stay date and fetch time: `available`,
   `min_nights`, any check-in/check-out restriction the provider returns, `source_status`, and
   payload quality. Write every day the calendar returns, not only quoted dates.
2. Distinguish four states for a comp-night: quoted ok, unavailable on the calendar, not returned by
   the search sweep, and fetch failed. Never record a failure as unavailable.
3. Report, per home, how many active comp-set members can produce a quote, and propose (do not apply)
   comp-set additions from the 5+ bedroom, 14+ sleep candidates already in `comps`.
4. Add fixtures for an HTML body, an empty calendar, a stale fetch, a thin panel and a host block.

**Do not.** Change `comp_anchor`'s 42-day and 3-quote rules, treat calendar unavailability as a sale,
add a paid vendor, or alter pricing output.

**Acceptance.** Tests prove each of the four states is stored distinctly; a failed fetch never
overwrites an earlier good row; re-running a scrape is idempotent; a per-home coverage receipt
(nights with ≥3 fresh own-set comps, December–March) is printed. Report the before and after
coverage and the scrape failure rate.

### 7.2 Signal-health follow-up (roadmap item 2)

**Context.** Commit `d3e8b92` repointed `src/signals/extractors/cotrip.py` to the CARS 511 feed
(`api-511x-co.carsprogram.org/events/map-features`), made non-JSON responses `QUALITY_UNAVAILABLE`,
set `wind_speed_unit=ms` in `src/signals/collectors/weather.py`, added the 2027 holidays and made the
Ikon rows Session-Pass-specific. Four risks remain: `parse_cotrip_payload` sets `berthoud_closed` when
"closed" appears anywhere in a matching feature, and the feed has values such as "Right shoulder
closed"; the US-40 milepost window is 233–243 and may miss Empire-side events; the SQI curve in
`config/policies/conditions.yaml` still multiplies price by 1.12–1.18 in big-snow years; Open-Meteo's
free tier is non-commercial.

**Do.**
1. Classify CARS events by structured fields (event type, lane or shoulder impact, the `active` flag,
   route and milepoints) instead of free-text keywords. Only a full-road closure sets
   `berthoud_closed`; a shoulder or single-lane event may raise `access_risk` but not the closure flag.
2. Confirm the US-40 milepost range for the Empire–Berthoud–Winter Park segment from CDOT data and
   set the window from it, with a fixture for an east-side event that does not mention "Berthoud".
3. Propose (do not apply) a neutral SQI curve above 1.0 until a season-blocked test supports an
   uplift, and show the owner-net effect on the proving-ground record-snow world.
4. Write up the weather-provider choice (paid Open-Meteo vs NWS) as an operator decision; do not
   switch providers without approval.

**Do not.** Change pricing policy files without operator approval; promote any signal.

**Acceptance.** Fixture tests for shoulder-only, lane-only, full closure, non-JSON and east-side
events pass; a dry run against the live feed (read-only) stores `ok` or `unavailable` with a reason,
never a bare zero on a bad payload.

### 7.3 Pooled pickup shadow arm (roadmap item 3)

**Context.** `pace_reading` in `src/pricing/pace.py` compares the portfolio's on-books share in a
±3-day window with a reference curve, and `pace_multiplier` turns the ratio into
`1 + 0.30 × (index − 1)` clipped to 0.85–1.25. At 120 days out one booked night moves the multiplier
from 0.85 to 0.92 and a second to 1.03. Hotel and airline evidence favours additive pickup on small
samples (Weatherford and Kimes 2003; R2 §2.3). Winter lead time is about 72 days, not 15.

**Do.**
1. Build an experimental forecast: expected final bookings = on-books + pooled historical pickup from
   this lead to arrival, pooled across the three homes and across neighbouring dates and prior
   seasons, shrunk toward a market or reference curve, net of expected cancellations.
2. Feed only the residual (forecast minus a neutral curve) to price, with an explicit bound on how
   far one booking can move it, and a stale or no-data fallback that returns the neutral curve.
3. Log the forecast, its uncertainty and the shadow price beside the live recommendation.

**Do not.** Multiply in a second market ratio, turn the arm on in the default policy, or tune
`proving_ground_exam/market/calibration.yaml` from held-out results.

**Acceptance.** Paired-seed runs on misspecified worlds (strategic waiters, sellouts, over-dispersed
demand) report owner net and the peak-at-ceiling share against `pace_v3_anchor_repair`; forecast
Brier or MAE by lead bucket on held-out seasons; the bound on single-booking moves is tested.

### 7.4 Owner-net stay controls (roadmap item 5)

**Context.** `owner_terms` gives an owner share of 0.595 of the nightly rate under the candidate's
fees (0.155 channel, 0.25 management) plus a fee margin; whether the management fee is charged on
fees is unconfirmed. `src/min_stay` uses a season × lead table with orphan relaxation; the orphan
discount is a flat cut. R1 separates two changes: R1a, a finite willingness-to-pay demand model to
stop recommendations piling on the ceiling, and R1b, a capacity-1 bid-price recursion, which only
raises prices. PriceLabs already trades neighbouring-night opportunity cost in its minimum-stay
engine, so the value here is pricing that trade in owner-net dollars for 14-to-18-guest stays.

**Do.**
1. Implement R1a and R1b as separate experimental arms. Compute the bid price per home-night by
   backward recursion over daily lead steps; convert owner-net values to nightly-rate units with the
   owner share.
2. Price a stay as the sum of night bid prices plus the value of any night it orphans; derive
   minimum-stay relaxations from that, replacing the flat orphan discount in the arm only.
3. Populate `shadow_daily` daily and extend `recommendation_outcomes` coverage; add the exploration
   draw and the approval delay to the recommendation log.

**Do not.** Write to Guesty, ship either arm to the default policy, or assume the 0.595 base.

**Acceptance.** Paired seeds report R1a and R1b separately: R1a by the share of peak recommendations
at the ceiling and the reliability of booking probability at high prices; R1b by owner net with R1a
held fixed; stranded orphan nights per season; all on a world whose demand curve is not the
engine's own.

## 8. Contradiction resolution

- **PriceLabs:** R2/R4 say generic tools are sophisticated and broad; R5/R6 say the $9.99 dashboard
  can be useful. Both are true: buy it only as a cheap shadow comparator and market-pace prior; do
  not confuse its broad estimator (up to about 350 listings) with a capacity-matched peer panel.
- **15 versus 72 days:** 15 days was a Jun–Dec mixed-season, right-censored sample. About 72 days is
  the winter estimate. Use 72 for winter booking-curve coverage and retain 15 only as a non-winter
  historical statistic.
- **Pace ratio:** R1/R3/R6 agree that a single booking can move the current multiplier about 8% at
  long lead. Replace it with additive pooled pickup; do not add another multiplicative market ratio.
- **R1a versus R1b:** R1b's capacity-1 bid price is an inventory-value arm. R1a is a separate
  demand-model repair for peak-at-ceiling. The bid price alone worsens ceiling behavior; test both.
- **Snow:** R7's contemporaneous/seasonal evidence supports a state prior, while R6's weekly
  Granger check does not support a lagged traffic coefficient. Use state/band and operations facts,
  never a 0.78 drought multiplier.
- **Endogeneity:** persisted calendars improve measurement but still mix bookings and host blocks;
  comp fill is an upper-bound proxy and requires matched-comp, season-block evaluation. Vendors'
  booked-versus-blocked accuracy claims (AirDNA's 16-signal classifier; Airbtics' 96–98 percent) are
  self-reported, with no independent validation found.
- **Snow hangover:** the R7 review said the Inntopia source did not blame snow. Re-opened on
  2026-10-19, it does, in part, and its own study shows post-drought winters finishing up. Use the
  soft early pace as a timing band, not a level cut (§4.5).
- **Stay decisions:** R1 and R4 described generic pricers as nightly multiplier chains with no
  opportunity cost. PriceLabs' minimum-stay engine does price neighbouring-night opportunity cost.
  The edge narrows to owner-net economics on a 16-sleeper (§4.4).
- **Band versus continuous price:** use cruise/SFpark-style bands for noisy slow state, and let
  short-horizon stay controls move only within guardrails. Three homes cannot identify minute-by-minute
  continuous optimization.

## 9. This season and cheap signals

The evidence points to a soft season, with uncertainty: Winter Park town lodging tax was down 22.8%
in August 2026 year over year; Inntopia reported Colorado August bookings for November–January down
10.9% (Inntopia blames a post-drought "snow hangover" in part, and its study of five post-drought winters shows them finishing up on average); AirROI's 2025–26 panel showed Winter Park occupancy 44.9% to 35.8%, ADR up 22.2%, and RevPAR
down 4.7% while supply rose 9.9%; Colorado skier visits were reported down about 24% preliminary.
These are different geographies and products, so they support a scenario band, not a blanket cut.

Cheap shadow inputs are the PriceLabs dashboard, Vail/Epic and Ikon pass disclosures, DestiMetrics
monthly pace, DEN passenger reports, and a dated lift-ticket window-price feed. Gas is origin-weighted
scenario context only. Weekly SWE did not improve the traffic forecast (n=120, p=.731; out-of-sample
error worse by 0.7–3.5% over seven seasons), while January 1 SWE versus Jan–Mar traffic was r=.71 on n=8. Snow
is therefore a seasonal state, not a weekly lead.

## Appendix A. Search log

The synthesis pass used targeted searches in four classes. The query → use log is: `capacity-1
bid price single-unit revenue management` → R1 recursion; `additive pickup multiplicative booking
curve Weatherford Kimes` → pickup choice; `hotel stay-level displacement orphan gap` → R2; `Garcia
Tolvanen Wagner hotel elasticity recommendation posted price` → logging design; `PriceLabs 350
listings 15 km` and `PriceLabs Market Dashboard billing` → generic benchmark and cost; `Winter Park
AirROI 72 day lead time` → corrected winter lead; `Winter Park lodging tax August 2026` → soft-season
check; `Inntopia Colorado August 2026 bookings` → market pace; `Winter Park 5 bedroom Airbnb
January comps` → curated anchor; `Open-Meteo wind speed default unit` → weather defect; `COtrip API
alerts JSON CARS 511` → road-feed defect; `Winter Park Ikon blackout 2026-27` → product rule;
`FTC short-term lodging total price rule` → all-in display; `Cornish-Adebiyi Caesars algorithmic
pricing Third Circuit 2026` → shared-data legal caution; `snow SWE Winter Park traffic Granger` →
R6 lead-lag result; `Fiig Weatherford Wittman forecast accuracy revenue` → forecast-to-revenue
bound; `White Reality Check Hansen SPA BH FDR` → selection protocol; `CUPED switchback carryover`
→ field measurement; `MinT hierarchical forecast reconciliation` → pooling; `tourism forecasting
competition explanatory variables` → adversarial nowcast evidence. Full URLs and access labels are
retained in R1–R7 and R6; this log records what each search changed.

## Appendix B. Sources opened for this synthesis

Evidence was cross-checked across academic, government, vendor, industry, and repository classes:
Talluri & van Ryzin; Weatherford & Kimes; Garcia et al.; Weatherford & Belobaba; Fiig et al.; Ban &
Keskin; White; Hansen SPA; Benjamini–Hochberg; Bojinov et al.; Deng et al. (CUPED); Wickramasuriya
et al. (MinT); Giannone et al.; Athanasopoulos et al.; Choi & Varian; Canina et al.; Levin et al.;
FTC 16 CFR 464; Winter Park Resort pass page; Ikon FAQ; AirROI Winter Park and ski-pace pages;
PriceLabs billing and Market Dashboard pages; Inntopia report as quoted by the Post Independent;
Winter Park town tax report; Colorado DOR series; Open-Meteo documentation; CDOT/511 materials;
and the repository paths `src/pricing/pace.py`, `src/scrape/providers.py`, `src/signals/extractors/cotrip.py`,
`src/signals/collectors/weather.py`, `config/policies/events.yaml`, and `config/resort/winter_park.yaml`.
Several academic links are stale or abstracts only; the dossiers mark those limits, and no such
source is treated as a measured owner-net effect.

## Appendix C. Self-audit

| Depth requirement | Status |
|---|---|
| Broad, specific, adversarial search log | PARTIAL; query→use log above; result notes are in the upstream dossiers and in the review's 11 searches |
| ≥20 sources and ≥4 source classes | PASS; source list and upstream bibliographies |
| Primary sources / stale and unverified labels | PARTIAL (revised 2026-10-19): several DOIs could not be opened; the Canina resort detail and the Weatherford and Kimes 7-day detail are now UNVERIFIED; the claim that the Canina PDF was opened is withdrawn |
| Capability gap matrix with repo paths | PASS; §2 names paths and read-only code findings, corrected for the `_enrich_min_nights` location and quote-level availability |
| H1–H7 verdicts | PASS; §3 uses corrected post-review wording |
| 3–5 falsifiable specialist edges | PASS; §4 has five edges and falsifiers; edge 4.4 narrowed after review |
| Profit-ranked roadmap with impact, confidence, prerequisites, module, tests, field measure, kill criteria | PASS; §5, now with a "Traces to" column |
| MDE and inactive canary respected | PASS; simulator/shadow gates only |
| Code defects included without fixing code | PASS; §2.2 records the operator's 2026-10-19 fixes and the residual risks |
| 2–4 self-contained build prompts | PASS; §7 (four prompts) |
| Contradictions resolved | PASS; §8 |
| What not to do | PASS; §6 table with reasons |
| No guest fields, identifiers, booked revenue, live changes or commits | PASS |

## Appendix D. Open questions for the operator

1. Commit `d3e8b92` implemented the code fixes this pack recommended. Approve build prompt 7.2 to
   close the residual risks (shoulder-closure false positives, milepost window, big-snow uplift,
   weather licence)?
2. The booked-price figure is gone from the tree and from every ref of `main` and `origin/main`
   (`bcef02b`). Anyone who cloned before the rewrite may still have it; no further action is possible
   from this repo.
3. Keep the cold-call company and person unnamed in the public repo, or explicitly authorize naming.
4. Confirm the actual management-fee base, turn cost, channel mix, and whether fee revenue is shared;
   the 0.595 owner share remains conditional on those terms.
5. Decide whether to buy the PriceLabs dashboard or obtain an AirDNA/DestiMetrics trial after the
   comp data-spine repair.
6. Which pass product do most guests hold? The Ikon blackout rows now apply to the Session Pass only.

## Appendix E. Response to review

Review: `reviews/S1_review.md` (2026-10-19), ACCEPT WITH FIXES, 16 items. Applied by the close-out
audit; each source correction rests on the review's own re-opening of the source.

| # | Status | What changed |
|---|---|---|
| 1 | applied | §2.2 is now a code-status table for `d3e8b92` and `bcef02b` with residual risks; §1, §2.1, §4.3, roadmap item 2 and prompt 7.2 updated |
| 2 | applied | §1, the §2 preamble, the competitor-intelligence row and §4.1 name `src/scrape/__init__.py`, distinguish quote-level availability from the dropped calendar, use 67.5%, and add the comp-set-membership finding |
| 3 | applied | §3 H2 and H7, §4.4 and §8 credit PriceLabs' minimum-stay opportunity-cost engine and narrow the edge to owner-net economics for 14-to-18-guest stays |
| 4 | applied | §4.5, §8 and §9 report Inntopia's snow-hangover attribution and its post-drought study, and treat the soft early pace as a timing band |
| 5 | applied | §3 H1: $2,427 at 8 guests, $2,577 at 14; tax and platform fees excluded |
| 6 | applied | §3 H4: "case study"; out-of-sample errors stated consistently; Canina detail UNVERIFIED; "PDF opened" withdrawn |
| 7 | applied | §4.5: 2.6–3.7×, about 1.8× at current quality |
| 8 | applied | §2.1 names `pace_v3_anchor_repair.yaml` |
| 9 | applied | The garbled wind paragraph is replaced by the §2.2 table row |
| 10 | applied | §2.2 Ikon row states what the resort page and Ikon FAQ actually say |
| 11 | applied | §2 pickup row marks the 7-day detail UNVERIFIED |
| 12 | applied | §5 has a "Traces to" column and a data-feasibility note |
| 13 | applied | §6 is a table with reasons and sources |
| 14 | applied | §7 has four self-contained prompts with context, steps, exclusions and acceptance tests |
| 15 | applied | Appendix D updated to the commit and history state |
| 16 | applied | Appendix C updated |

Also found during the fix pass: most of the recommended/listed/booked logging already exists
(`price_recommendations`, `recommendation_outcomes`); `shadow_daily` is empty. §1, the
price-experimentation row, roadmap item 5 and prompt 7.4 now say "populate and extend", not "build".
