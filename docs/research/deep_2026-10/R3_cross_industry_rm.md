# R3: Price optimization across other industries, and what transfers to three Winter Park homes

Date: 2026-10-16. Access date for every web source below is 2026-10-16 unless stated otherwise.
Author: deep-research agent (R3 of the 2026-10-16 pack). Research only. No code was changed.

Conventions used in this file:

- **[Sxx]** refers to the source register in Appendix A, which gives each source's class (1–7 per
  `00_DEPTH_STANDARD.md`), URL and what was actually read (full text, abstract only, or a secondary summary).
- **UNVERIFIED** means a claim I could not confirm against a primary source. **STALE** means the data is
  older than three years (before 2023-10). **PAYWALL** means only the abstract or a summary was read.
- "Owner net" means the objective defined in `docs/plans/OVERHAUL_2026-10-14.md` Phase 3.1: room revenue
  minus channel fee minus management fee plus fee margin minus turnover cost, measured against
  `current_practice` (the homes' real rate card).
- No booked revenue, Guesty ids or guest data appear here. All Mont Luxe figures are the public listed
  rates already quoted in the shared context.

## 0. Executive summary

1. **The ski industry is the most useful neighbour, and mostly not for its pricing math.** Vail and Alterra
   have spent a decade converting weather-exposed, day-of demand into non-refundable advance commitment:
   about 74% of Vail's skier visits came from advance-commitment products for 2025/26, and passes were
   about 65% of Vail's FY2025 lift revenue [S01][S03]. For us that has two consequences. (a) Pass sales are
   a **published, dated, leading indicator** of the season's committed skier base, released four times a
   year with a clean `observed_at` (the press-release timestamp). The 2026/27 Epic number is weak: units
   −12%, dollars −6% through 2026-09-18, with the weakness in destination, lower-frequency products and
   with Colorado/Utah locals "modestly" improved [S02]. (b) Pass economics moved the marginal skier's lift
   cost to roughly zero after purchase. That makes snow and access the trip trigger, and the lodging night
   the main variable cost the guest still controls. Lodging is where the guest's price sensitivity lands.
2. **Cruise is the closest analogue to a large luxury home, and its lesson is "manage the booking curve for
   price", not "fill the ship".** Royal Caribbean runs AI models daily over "about 20 million" price points,
   holds a booked load factor within "a couple of points" of history, and in 2026 has been *raising*
   close-in prices instead of discounting them [S10]. Carnival describes the same posture as "managing the
   booking curve for price" [S12]. The mechanism transfers directly to our pace pricing: a target booked
   share by lead time, a tolerance band, and price as the control variable. The other cruise idea that
   transfers is the **price-drop guarantee** (reprice before final payment), which is a formal RM instrument
   [S14][S15].
3. **Event ticketing supplies one tool and one caution.** The tool: secondary-market resale prices as a
   willingness-to-pay discovery mechanism, which for us means "what comps *sell* at, not what they ask"
   (comp availability transitions). The caution: the 2024 Oasis sale drew a UK competition-authority
   investigation that closed with Ticketmaster undertakings on disclosing **tiered** prices in the queue
   [S20][S21] (see the correction note below), and the 2025 FTC suit alleges drip pricing [S45]. The rule
   that carries over: never let the price change, or fees appear, during the guest's decision.
4. **Learning while earning at ~100 bookings a year is possible only in a narrow form.** Bandit theory
   (Besbes & Zeevi; Keskin & Zeevi; den Boer's survey; Ferreira, Simchi-Levi & Wang's Thompson sampling with
   inventory) says regret scales with √T, or log T when outcomes at an incumbent price are known, in the
   *number of sales opportunities* [S30][S31][S33][S60]. Our T per home per
   season is in the low dozens of booking decisions. Unpooled bandits cannot learn a home-level elasticity in
   one season. What survives is: (a) a hierarchical prior pooled across our three homes and the comp set,
   (b) small, bounded, logged price perturbations off-peak only, and (c) learning from **comps' fills**
   (which are many more observations than ours) rather than only our own, but only once an identification
   strategy handles the fact that comp prices are set in response to demand (§10.2).
5. **Rideshare and Rue La La show the value of real data; neither model transfers as-is.** Uber's surge is a
   real-time clearing price for a market that rebalances in minutes [S24][S25]. Rue La La's gain (about 10%
   in a field test, measured by the authors with the retailer) came from estimating demand for products that
   had never been sold by borrowing from similar products, and then solving a pricing integer program
   [S27]. That borrowing is exactly what three homes need.
6. **Fee presentation is now a regulated price lever.** The FTC rule in force since 2025-05-12 requires the
   total price, including mandatory fees, to be shown first for short-term lodging [S40]. Our $600 cleaning
   + $75/guest + $80 insurance sit inside the price every guest compares. Blake et al. (StubHub) measured
   that hiding fees raised purchases and spending [S41]. The engine already prices on the all-in price
   (`src/pricing/pace.py: all_in_beta`). This dossier adds a ranked list of changes on top.

Top five recommendations (full table in §13):

| # | Recommendation | Module | Expected owner-net impact | Confidence |
|---|---|---|---|---|
| 1 | Cruise/SFpark-style **booking-curve band control**: additive pace gap, dead band sized to 3-home noise, raise only above the band, cut only below it and only close in | `src/pricing/pace.py` | Low–Medium: lower price volatility and a robust pace response. It does **not** claim the simulated −6.6% peak gap, which is a level (anchor) gap from an older 5-seed screen (§13 #1) | Medium |
| 2 | **Comp-fill price-response estimator** (Rue La La / secondary-market idea): learn price response from comp availability transitions, pooled hierarchically with our own bookings | `src/scrape`, `src/comps`, `src/elasticity` | Medium, **if** an identification strategy exists: comp prices are endogenous to demand (§10.2) | Low (gated by the scraper and by endogeneity) |
| 3 | **Ski-industry signal pack** at `experimental`: Winter Park dated lift-ticket premium, Inntopia monthly pace, Vail pass/visit releases, Ikon deadline calendar | `src/signals/collectors`, `config/policies/events.yaml`, `signals.yaml` | Low-medium, mostly season-level and far-out nights | Medium-low |
| 4 | **Night and stay bid prices** (car-rental / hotel multi-day displacement) driving min-stay relaxation and stay pricing | `src/min_stay`, `src/compose`, `src/leakage` | Medium off-peak and at holiday edges | Medium |
| 5 | **Owner-net audit and partial control** (Huang; Filippas et al.): no gross-RevPAN code path; owner sets levels, engine sets shape | `src/compose`, `src/eval`, autonomy doctrine | Guards against a known failure class. The simulated default engine's −38% is attributed by OVERHAUL to hard peak caps and a low ceiling/reference, not to a gross objective | High (as an audit) |

> **Correction to item 3 above (made after a primary-source check, kept visible on purpose).** The UK
> Competition and Markets Authority's case page does **not** record a finding of algorithmic dynamic
> pricing for the Oasis sale. Ticketmaster's undertakings (signed 2025-09-15, published 2025-09-25) concern
> undisclosed **tiered** pricing for standing tickets: 24-hour advance notice of tiered pricing, price
> information inside queues, no misleading labels, two years of reporting [S20][S21]. The lesson that
> transfers is about disclosure and price movement during the decision, not about demand-based pricing
> as such.

## 1. Ski lift tickets and season passes (deepest section)

### 1.1 What the filings say, in their own words

Vail Resorts (NYSE: MTN) is the only large North American operator that files publicly. Alterra
Mountain Company, which owns Winter Park and sells the Ikon Pass, is private and discloses almost nothing
numeric (a 2018 Alterra spokesperson said it would not release Ikon sales numbers [S07]). So Vail is the
industry's public instrument panel, and Alterra has to be read through Vail, through NSAA and Colorado Ski
Country visit counts, and through Inntopia's lodging data.

Facts from Vail primary documents:

| Fact | Value | Source |
|---|---|---|
| Pass products' share of lift revenue, FY2025 | about 65% | FY2025 10-K, Item 1 [S03] |
| Share of Mountain + Lodging net revenue earned in fiscal Q2+Q3 (Nov–Apr), FY2025 | about 82% | FY2025 10-K [S03] |
| Advance-commitment guests, 2025/26 | about 2.3 million, about $1 billion of revenue, about 74% of skier visits excluding complimentary | Q1 FY2026 release, 2025-12-10 [S01] |
| 2025/26 pass sales through 2025-12-05 | units −2%, dollars +3%; a 7% price increase drove dollars; the unit decline was mainly Colorado, Utah and Tahoe local drive-to markets; destination "only slightly down" | [S01] |
| New lift-ticket product 2025/26 | an advance lift-ticket discount for guests who book at least a month ahead at select resorts, alongside "Epic Friend" tickets | [S01] |
| FY2026 (year to 2026-07-31) | skier visits 15.30 M, −13.4%; lift revenue $1,451.1 M, −3.5%; effective ticket price (ETP) $94.85, +11.5% | Q4 FY2026 release, 2026-09-28 [S02] |
| Why lift revenue fell less than visits | pass revenue +3.9% for the year: the cash was committed before the snow failed | [S02]; Q3 FY2026 release says lift revenue −5% on visitation −15% for the nine months [S04] |
| 2026/27 pass sales through 2026-09-18 | units −12%, days −10%, dollars −6% (incl. taxes); weakness in destination frequency products, "especially lower frequency passes"; Colorado and Utah locals "modest improvement" after the May deadline | [S02] |
| 2026/27 pass sales through 2026-05-26 | units −10%, days −8%, dollars −5% | [S04] |
| FY2026 managed condo RevPAR / ADR | $105.39 (−9.7%) / $393.60 (−4.8%) | [S02] |
| FY2027 guidance assumption | "a meaningful recovery from the weather-impacted fiscal 2026 season", "a range of normal weather conditions", lower pass demand and more marketing to drive visitation | [S02] |
| Pricing posture | "we charge some of the highest prices for single day lift tickets"; passes "are available at a discount to the single day lift ticket prices" | FY2025 10-K [S03] |
| Snow and pass sales | "Past ski season snowfall levels or consistency of snow conditions can impact sales of pass products" | FY2025 10-K, Item 1A [S03] |
| Epic Coverage | included free with every pass; refunds for certain resort closures and travel restrictions; estimated refunds reduce recognized pass revenue | FY2025 10-K [S03] |

Industry context for 2025/26 (secondary reporting of NSAA and Colorado Ski Country USA figures, not the
associations' own releases): Rocky Mountain region visits about 20.1 M, −24% from 26.5 M; Colorado about
10.5 M, down from 13.9 M, described as the sharpest drop in more than 40 years [S05][S06]. Inntopia
(DestiMetrics) reported western mountain winter 2025/26 occupancy −7%, ADR +1.2%, revenue −5.9%, with
Colorado and Utah occupancy −6.7% against −0.5% in the rest of the region, and April occupancy −18.3% [S08].

**What this means for Winter Park lodging.** The 2025/26 season is a case study (one season, not a natural experiment) that the
engine's own history already contains: a historically poor snow year in which the committed pass base held lift revenue
up while lodging volume (−7% occupancy region-wide) and managed-condo ADR (−4.8% at Vail) fell. The
architecture doc's "drought reframing" (`docs/ARCHITECTURE.md`: last season's low Christmas price was correct
under 60%-of-normal snowpack) is consistent with this industry-wide picture. It is evidence for keeping SQI
as a declared prior with a kill switch rather than fitting it to one bad winter.

### 1.2 The "commitment" strategy as a pricing mechanism

What Vail built is intertemporal price discrimination with an insurance wrapper:

1. **Two goods, one capacity.** A pass is a call option on many ski days, bought months ahead at price
   `p_pass`. A lift ticket is the spot good, bought on or near the day at a date-specific price `p_t(d, lead)`.
2. **The buy rule for a rational skier.** Buy the pass if `E[days] × E[p_t] − p_pass > risk premium`. Raising
   the spot (window) price raises the left side for every skier who expects more than `p_pass / p_t` days.
   With `p_pass` around $1,000 and a $300+ window price, the break-even is about 3–4 days. Vail's peak window
   prices reached $356 at Vail and Beaver Creek in 2025/26 per trade press [S09]; its own spokesperson framed
   day-of window tickets as "the most expensive" option. Whether the window price is set *in order to* push
   pass sales is an inference, not a company statement; the 10-K says only that Vail charges "some of the
   highest prices" and discounts passes against them [S03].
3. **Fences between them.** Price falls with commitment lead: pass (months ahead) < Epic Day Pass (pre-season,
   non-refundable, fixed days) < advance-dated ticket (Vail's new one-month-ahead discount) < window ticket.
   Each step trades flexibility for price.
4. **Insurance removes the main objection.** Epic Coverage refunds for closures and certain travel
   restrictions. That converts the non-refundable commitment into one with a bounded downside, which is what
   a family planning months ahead needs. Cruise lines do the same thing with price-drop repricing (§3).
5. **The cash lands before the weather.** Pass cash is collected in spring and fall and recognized in fiscal
   Q2–Q3 [S03]. That is why FY2026 lift revenue fell 3.5% on visits −13.4% [S02].

The math a lodging engine can borrow is not the pass itself (we cannot sell a season of nights), but the
**price-path direction**. Lift-ticket prices *rise* toward the day, because capacity is rarely binding on a
mountain and the operator wants commitment. Sweeting's study of secondary-market baseball tickets found the
opposite for a seller holding one unit with a deadline: within-seller prices fall about 13%, 18% and 40% at
successive relistings as the event approaches,
because the option value of waiting shrinks [S22]. **A large luxury home is the Sweeting case on most nights
and the ski case on holidays.** On a night that will very likely sell (Christmas–New Year, Presidents' Day),
the home behaves like a mountain on a powder day: hold the price up, reward commitment. On a soft January
Tuesday it behaves like a ticket reseller: the option value of waiting decays toward the cleaning-cost
breakeven. The engine's `pace_multiplier` already moves in both directions; what is missing is an explicit
rule for **which regime a night is in**, decided from the booking curve (see §3.3 and Recommendation 1).

### 1.3 Dynamic lift-ticket pricing: what was published and what worked

- **Liftopia (2006–c.2020).** Founded on the idea that lift tickets should be priced like hotel rooms, with
  date-specific advance prices from demand data; at its peak it sold for 250+ resorts and powered 110+ resort
  web stores ("Cloud Store") [S16]. It ended in an assignment for the benefit of creditors, with Alterra, Aspen
  Skiing Company, Arapahoe Basin and Mountain Collective among those owed, and its assets went to the app
  Skitude; PeakRankings attributes its decline partly to the mega-passes [S17]. Exact dates **UNVERIFIED**
  (the article shows "Dec 7" without a year). Lesson: the dynamic advance-ticket marketplace lost to the pass,
  i.e. to commitment, not to a better spot-pricing algorithm.
- **Winter Park's own lift tickets (Alterra).** Date-based online prices with a limited number of discounted
  advance tickets; secondary guides cite adult 2025/26 tickets around $267–$286 and advance savings of
  15–20% [S18]. These numbers vary across aggregator sites and are **UNVERIFIED** against the resort's own
  booking engine. The engine's resort collector already has a `lift_ticket_window_usd` field
  (`src/signals/collectors/resort.py`).
- **Academic evidence (Norway, Malasevska and co-authors).** Using 722 conjoint questionnaires plus a live
  pricing trial at a partner resort, the team estimated attribute utilities (weather, price, day type) and
  optimized prices by non-linear optimization [S19]. Findings stated in the abstracts and the summary: revenue
  could be raised with weather-related discounts when conditions are poor (*Journal of Outdoor Recreation and
  Tourism* 2017); lower midweek prices raise visits and total revenue (*Tourism Management* 2018, 64:291–302);
  revenue-maximizing prices in bad weather are "significantly lower" than in good weather and a single
  season price is not optimal; and when midweek weather is clearly better than the weekend forecast, skiers
  move to midweek despite a higher price (*Journal of Travel & Tourism Marketing* 37(7), 2020) [S19].
  **PAYWALL**: I read the summary page and abstracts, not the full papers, so I cannot report revenue-lift
  percentages; the summary itself gives none.

**Mechanism worth copying (Malasevska demand shifting).** Model demand on day `d` as
`q_d = a_d + b·p_d + c·(p_{d'} − p_d) + w·W_d`, where `d'` is a substitute day and `W_d` is a weather/snow
quality term. The cross-price term `c` is what makes "shift demand from Saturday to Tuesday" an optimization
rather than a discount. For a home, the analogue is that a party choosing a 4-night ski trip picks *which*
4 nights; a cheap Sunday–Thursday window can pull a party off a full weekend. This belongs in
`proving_ground_exam/` as a shopper behaviour (date flexibility with a cross-price term) before it belongs in
the engine. Field identification with our data is impossible.

### 1.4 How pass sales shift lodging demand: evidence and its limits

I found no study that measures how mega-passes changed overnight stays in **Colorado** (search log Q12).
The reviewer found causal evidence from Switzerland, which I have checked at abstract level:

- **Falk & Scaglione, "Effects of price model copycats in the ski industry"**, *Tourism Analysis* 26:71–75
  (2021) [S80]: a difference-in-differences over 59 Swiss winter destinations, 2012/13–2017/18, 11 of which
  joined the low-price Magic Pass. The pass raised **domestic overnight stays by about 31%** and had **no
  effect on foreign overnight stays**. An earlier Saas-Fee study (*Tourism Review*, 2018,
  doi 10.1108/TR-08-2017-0133) found about +50% for Swiss residents and about +17% for total stays [S81].
- **What it means here.** Cheap passes move overnight demand from the *drive-in, domestic* segment, not
  the fly-in segment. For Winter Park the Front Range is the drive-in segment and the 5+ BR group trade is
  mostly destination. That supports reading a destination-led Epic decline as the more negative sign for
  our homes (next bullet), and it argues against a single pass-sales coefficient: weight it by segment.

What else can be said with sources:

- Vail itself says the 2025/26 unit decline came mostly from local drive-to markets, and the 2026/27 decline
  mostly from destination, lower-frequency products [S01][S02]. **Destination low-frequency pass buyers are
  the guests most likely to rent a 5-bedroom home for a week.** A destination-led pass decline is a more
  negative sign for our segment than a local-led one.
- Ikon's own "pre-season savings" page advertised Winter Park lodging at "up to 50% off" for stays of
  4+ nights, with Early Ups, $100 resort credit and discounted tickets, booking deadline August 28 (season
  most likely 2025/26; the current 2026/27 terms were not visible in the pages I could read) [S13]. A trade
  summary cites "up to 25% off base-area lodging" (**UNVERIFIED**). Either way, resort-side lodging is
  discounted to pass holders who commit early to long stays, and private homes compete with it. That is a
  **pass-linked competitor promotion with a deadline**: worth a calendar entry in `config/policies/events.yaml`.
- The marginal lift cost for a pass holder is zero, so the lodging night is the largest *discretionary*
  spend the pass holder still makes. That should raise the lodging price elasticity of pass holders relative
  to ticket buyers, who already pay $250–$350 a day per skier. For a party of 12, lift tickets alone can
  exceed the nightly rate of the home. **Hypothesis, not evidence.** Test: ask in the direct-booking flow
  (aggregate, opt-in) whether the party holds Ikon/Epic passes, per `docs/research/GUEST_DATA_CONTRACT.md`.

### 1.5 What generic STR pricers miss here (H2)

PriceLabs' public description uses seasonality, day of week, lead-time and occupancy pace, with ski season
described as less price sensitive than summer (dossier 04 quotes their blog). Wheelhouse's vendor-authored comparison describes blending a predictive and a reactive model, with the reactive model weighted more as the stay date nears [S79]; I found no ski-specific inputs (snow, passes) documented for PriceLabs, Wheelhouse or Beyond (search log Q58). None of the generic tools I can
find documentation for ingests **pass sales by segment** or **pass purchase deadlines**. Their market data is
the listing calendar itself (occupancy and price of other listings), which is a *coincident* indicator. Vail's
destination-frequency pass number is a *leading* one, published 2–4 months before the nights it affects. This
is a narrow edge: one number per quarter, with perhaps 10 seasons of history. It can shift a season-level
reference, not a night.

## 2. Car rental

### 2.1 What the industry does

- **Founding case.** National Car Rental's revenue-management program (Geraghty & Johnson, *Interfaces*
  27(1):107–127, 1997) was built in 1993–94 when GM was close to liquidating the company. Models covered
  capacity (fleet), pricing and reservations; the new system is credited with $56 M in its first year after
  the July 1994 rollout, and the team was an Edelman laureate [S23]. **STALE** and self-reported by the
  company's own staff (conflict of interest: the authors ran the program).
- **The structural difference from hotels.** A rental occupies a car for several consecutive days, and cars
  move between stations (one-way rentals, shuttling). Li & Pang (*EJOR* 256(3):850–867, 2017) formulate
  single-station booking control as an infinite-horizon stochastic DP whose state includes the remaining
  lengths of rentals already out; they decompose it into per-day subproblems, build approximate value
  functions or booking limits from those, and report near-optimal performance in a case study with a major
  UK rental company [S26].
- **What the filings disclose.** Avis Budget's FY2025 10-K measures the business by rental days, revenue per
  day (RPD) and utilization (rental days ÷ available rental days), says competition is "based primarily upon
  price", that technology "has increased pricing transparency", and that it "routinely adjust[s] the size …
  of our rental fleet in response to fluctuations in demand" [S28]. The filing does not describe the
  pricing algorithm. Hertz's 2025 turnaround credited "revenue optimization" and fleet discipline and
  referenced a multiyear revenue-management upgrade with Amadeus (secondary summaries of the calls) [S29];
  **UNVERIFIED** against the transcript itself.
- **The platform experiment.** Filippas, Jagabathula & Sundararajan (*Management Science* 69(12):7202–7216,
  2023) studied a sharing-economy marketplace (Huang describes it as a rental-car platform [S35]) that moved
  owners from self-set to centralized prices. Centralized pricing raised utilization and revenue but also
  transaction costs; owners who lost pricing control cut availability, cancelled bookings and left;
  owners who kept partial control reacted much less and got similar revenue gains [S34].

### 2.2 Mechanisms that transfer

1. **Length-of-rental as a displacement problem.** In Li & Pang, accepting a 5-day rental starting Thursday
   blocks Thursday–Monday. Its value is not the sum of daily prices; it is the rental revenue minus the
   expected revenue the blocked days would have earned from other requests (the opportunity cost from the
   decomposed value functions). That is exactly our multi-night stay with gap nights. Engine version:
   for a request `(check-in s, nights m)`, accept/price iff
   `stay_price(s, m) ≥ Σ_{d=s}^{s+m−1} bid(d) + orphan_penalty(s, m)`,
   where `bid(d)` is the expected owner net that night would earn if left open (from `src/bookprob` at the
   current price × owner share) and `orphan_penalty` is the expected loss on 1–2 night holes the stay creates.
   MODEL_SPEC's M4 already prices the stay with an orphan penalty of 0.5 × nightly; a bid-price version
   replaces the constant 0.5 with the night's own expected value. Module: `src/min_stay`, `src/compose`.
2. **Partial control beats full automation (Filippas et al.).** For an operator managing other people's
   homes, owners and the operator need to keep the final say on level while the engine sets *variation*
   (Huang's "platform sets price variation, sellers set levels" remedy, which removed "almost all"
   frictions in his counterfactual [S35]). This is the current autonomy ladder (`docs/rules/AUTONOMY.md`)
   and the ±12% / $250 move cap. The evidence supports keeping it, and it suggests one change: let the owner
   set the **level** (a seasonal anchor) and let the engine set the **shape** around it.
3. **Seller cost belongs in the objective, but Huang's cost transfers weakly.** Huang's counterfactual: a
   pure revenue-maximizing platform algorithm sets prices 26% below the sellers' own baseline, pushes
   occupancy to 90%, and leaves 56% of sellers worse off [S35]. Huang's seller cost is the **opportunity
   cost of time per night** (median about $37 against a $150 median price) for San Francisco private rooms
   and studios, not a turnover or cleaning cost. For our homes the $600 cleaning fee is passed to the guest,
   so the owner-side cost is `turnover_cost_per_stay` ($350 in the candidate) net of the fee margin, about
   $7 a night at typical party and LOS. `pace.py` already optimizes owner net (`owner_terms`). The lesson
   is an analogy: keep owner net as the objective and audit for any gross-RevPAN path. It is not evidence
   of a large loss at our cost structure.

### 2.3 DEN car-rental prices as a demand signal

**Compare first with the cheaper official proxy.** Denver International Airport publishes monthly passenger
traffic reports (official, free, https://www.flydenver.com/) [S87]. They are monthly and mix all purposes,
but they cost nothing and have a long history. A rental-car quote collector is new scraping work with terms
of use questions. Order of work: (1) test DEN monthly passengers against Winter Park lodging-tax receipts
and our own pace at season level; (2) build the rental-quote collector only if (1) shows the fly-in channel
moves our demand. No study or dataset of DEN rental prices as a demand signal was found (reviewer, 2026-10-17).

The task asks whether Denver airport car-rental rates can serve as a mountain demand signal. I found no
published study using rental-car prices as a lodging demand indicator (search log Q18–Q19). Mechanism for why
it might work: DEN rental fleets are set weeks ahead; when ski-week demand exceeds fleet, rental quotes for
AWD/SUV classes rise sharply for specific pick-up dates. Those quotes are visible to anyone through public
search before our own bookings arrive. Mechanism for why it might not: DEN rental demand mixes business,
Denver metro and all mountain resorts (Vail, Breckenridge, Steamboat, Winter Park), so the Winter Park share
is small; fly-in guests to a Winter Park home may also use shuttles. **Test design:** scrape (or buy) daily
quotes for a fixed SUV class, DEN pick-up, 3–7 day rentals, for pick-up dates 7–90 days out; build the
quote's z-score against the same lead and day-of-week; register as `demand.den_rental_quote_z` at
`experimental`; promote only through the ladder in `config/policies/signals.yaml` (IC ≥ 0.05, hit rate ≥ 0.52,
n ≥ 40). Scraping a rental site carries the same terms-of-service and reliability problems as our comp
scraper. **Expected value: low.** It ranks below the comp scraper fix, which is the binding constraint.

## 3. Cruise lines (deepest section, with ski)

### 3.1 Why cruise is the closest analogue

A cruise cabin and a luxury 5-bedroom home share the properties that break airline and hotel methods:
long booking lead (cruise books 12–18 months ahead; our holiday weeks book months ahead), high ticket price,
group and family parties, multi-night fixed bundles (a voyage is a fixed-length stay), and more than one
capacity constraint. Maddah et al. (*EJOR* 207(1):445–455, 2010) model cabin categories **and** lifeboat
seats as joint constraints and show the opportunity cost of accepting a booking is not monotone in time or
reservations, so simple booking limits are not optimal [S36]. For a home the analogous second constraint is
party size against beds (a party of 18 can only book Cloud 9). Biehn ("A cruise ship is not a floating
hotel", *JRPM* 5:135–142, 2006) argues hotel RM practices do not carry over directly [S37]. **PAYWALL**: both
read at abstract level.

### 3.2 What the lines say they do (2025–2026 filings and calls)

- Royal Caribbean, Q2 2026 call (secondary transcript, Investing.com): the company runs "very sophisticated
  AI-driven models" daily over "about 20 million and growing price points"; "every day price integrity is
  very top of mind"; it is "happy with being a couple of points below, a couple of points above" its
  historical booked load factor; "Our book position is in line with prior years at record pricing"; and
  "Today for close-in demand, we're able to increase our pricing", contrasted with discounting a decade ago;
  consumers are "booking closer in due to flexibility and ease" [S10]. Q2 2026 net yields +1.2%, about 100 bp
  above guidance, on better-than-expected close-in demand [S11].
- Carnival: management credits "base loading" and yield management for being at "historical highs on both
  occupancy and price" for 2025, emphasizes total revenue over occupancy, and in September 2026 said "we have
  an opportunity to keep managing the booking curve for price"; more than half of onboard revenue is now
  pre-booked [S12]. (Trade press; **UNVERIFIED** against Carnival's 10-K wording.)
- Empirical study of one cruise company's 300 products (Ayvaz-Cavdaroglu, Gauri & Webster, *Journal of Travel
  Research* 58(1):104–120, 2019): a price-optimization model with partial substitution between departure
  dates, destinations and cabin types, plus advertising as a second lever, estimated a revenue gain of about
  8–20% [S38]. **PAYWALL**, abstract only; the gain is a model counterfactual, not a field test.
- Forecasting: on data from a major North American cruise line, 24 methods were tested; **multiplicative
  methods performed significantly worse**, and additive classical pickup performed best (*JRPM* 10(4):306–324,
  2011) [S39]. **STALE** but structural.

### 3.3 Mechanisms, written so an engineer can build them

**(a) Base loading, then yield ("load and yield").** Phase 1 (far out): open at a price designed to put a
target *base* of bookings on the books early, which de-risks the sailing. Phase 2 (mid and close in): with
the base secured, manage price upward against the booking curve. For us, "base" is the holiday weeks and the
first bookings of each peak month. The current engine has no concept of a base; pace pricing responds to
pace symmetrically at all leads.

**(b) Booking-curve band control.** Inputs: for each night (or stay window) `d`, the on-the-books share
`B(d, ℓ)` at lead `ℓ`, and a target curve `T(ℓ)` with a tolerance band `[T(ℓ) − δ⁻(ℓ), T(ℓ) + δ⁺(ℓ)]`.
Royal Caribbean's "a couple of points below, a couple of points above" is exactly this band. Decision rule:

```
if B(d,ℓ) > T(ℓ) + δ⁺(ℓ):   price ← price × (1 + step_up(ℓ))     # ahead: raise
elif B(d,ℓ) < T(ℓ) − δ⁻(ℓ):  price ← price × (1 − step_down(ℓ))   # behind: cut, but only if ℓ is short enough
else:                         price ← price                         # inside band: hold (price integrity)
```

with `step_down(ℓ) = 0` beyond a lead `ℓ*` (do not discount far out; time still has option value), and
`step_up` capped by the existing move cap. SFpark used the same structure for curb parking, a 60–80%
occupancy target band with periodic step changes. Pierce & Shoup report an elasticity of about −0.4 from 5,294 price and occupancy
changes in the first year (JAPA 79(1):67–81, 2013), and the later UCLA two-year brief reports 62% of
blocks in the target band and average prices down 4% (the first-year paper reported −1%) [S42;
confirmed by search 2026-10-19]. Shoup is the originator of performance parking, so this is practitioner
evidence, not an independent evaluation. Millard-Ball, Weinberger & Hampshire (JAPA 79(4):330–336, 2013;
*Transportation Research A* 2014) find much smaller effects: each rate change moves a block only 0.1–0.2%
closer to target [S82]. The band **structure** transfers; the evidence that it converges fast does not.

Why a band instead of today's continuous `1 + k·(index − 1)`: with three homes, the on-the-books share for a
±3-day window moves in jumps of 1/21 (three homes × seven nights). A continuous multiplier turns that
sampling noise into daily price noise. A dead band absorbs it. The cruise forecasting result [S39] points the
same way: **compare additively** (`B − T`, in percentage points) rather than by ratio (`B / T`), because the
ratio explodes at small `T`. `pace.py`'s `PaceReading.index` is a ratio with +0.05 smoothing; at 120 days out,
`T = 0.70 × 0.12 = 0.084`, so one booked night in the window (1/21 = 0.048) moves the index from 0.37 to
0.73. With `sensitivity 0.30` and `min_multiplier 0.85`, the price multiplier goes from 0.85 (clamped) to
0.92 with one booking and to 1.03 with a second: on a $2,000 night that is $1,700 → $1,838 → $2,050, an 8%
and then a 12% jump from single bookings. Owner blocks shrink the 21-night denominator, which makes each
jump larger. That is a fragile signal to multiply a $2,000 price by. (The additive-pickup result of the
cruise paper [S39] is a *forecast-accuracy* finding; using it for a pace *control* is an analogy. The
ratio-fragility arithmetic above stands on its own.)

**(c) Price integrity and the price-drop guarantee.** Royal Caribbean lets a guest reprice to a lower fare
before final payment unless the lower fare is marked "new bookings only", and a later "Best Price Guarantee"
extended this up to 48 hours before sailing, with the difference paid as onboard credit [S14]. The theory is
Levin, McGill & Nediak (*Operations Research* 55(1):75–97, 2007): a seller who offers compensation if the
price drops before a set date raises early willingness to pay, and price and guarantee terms should be
optimized jointly as a discrete-time control problem [S15]. For our homes, the guarantee would read: "book
now; if our posted price for your exact dates falls before day X, we credit the difference" (as a fee waiver
or a credit, through the direct channel only). It lowers the risk of booking early, which is exactly when a
large party commits, and it disciplines the engine: every price cut on a booked date now has a visible cost.
**Constraint:** Airbnb and VRBO do not support this mechanism; it is a direct-booking feature only.

**(d) Pre-booked ancillaries.** Carnival reports more than half of onboard revenue pre-booked [S12]. The
STR analogue is pre-sold add-ons (lift tickets, ski rental delivery, chef, grocery stocking, hot-tub service,
late checkout). Not a pricing-engine change; noted for the owner as a revenue lever.

### 3.4 Transfer verdict for cruise

Band control (b) and additive pace comparison survive thin data because they need only the on-the-books
count and a target curve, not an elasticity. Price-drop guarantees (c) survive but only on the direct
channel. Full cruise-scale optimization (millions of price points, substitution matrices) does not transfer:
we have three products and roughly 100 bookings.

## 4. Event ticketing and sports

### 4.1 Evidence

- **Secondary markets reveal the price path for a single-unit seller.** Sweeting (*Journal of Political
  Economy* 120(6):1133–1172, 2012) shows that simple dynamic pricing models fit StubHub/eBay sellers of MLB
  tickets closely; sellers cut prices as the game approaches (about 13%, 18% and 40% by successive
  relistings) because the opportunity cost of
  holding a ticket falls as remaining selling chances disappear; dynamic pricing raises the average seller's
  expected payoff by about 16% [S22]. **STALE** (data from the 2000s), but the mechanism is structural.
- **Primary dynamic pricing in sports.** The San Francisco Giants priced 2,000 seats per game with Qcue in
  2009 and all ~42,000 seats in 2010; a CIO case study reports $7 M more ticket revenue that season [S43].
  **STALE**, and the $7 M is a vendor-friendly case study, not an independent estimate (2010 was also a World
  Series season). Shapiro & Drayer found secondary-market price models explained about 80% of the variance in
  resale prices, and teams set floors and ceilings that kept the secondary market from collapsing [S44].
  Digonex launched a competing product in 2009 [S43].
- **Fairness and regulation.** The Oasis 2024 sale led to a CMA investigation that closed with Ticketmaster
  undertakings on tiered-price disclosure (§0 correction) [S20][S21]. In the US, the FTC and seven states
  (including Colorado) sued Live Nation/Ticketmaster in September 2025 alleging drip pricing that raised
  prices "30% or more" at checkout and broker practices; the FTC estimated $3.7 B of resale fees in
  2019–2024 [S45]. Those are allegations, not findings.
- **Fee presentation.** Blake, Moshary, Sweeney & Tadelis (*Marketing Science* 40(4):619–636, 2021): StubHub
  randomized 50% of US users to see fees only at checkout; upfront fee disclosure reduced both the quantity
  and the quality (price tier) of purchases, and the quality effect accounts for at least 28% of the revenue
  decline [S41]. The drip group spent almost 21% more (published paper, Table 3, per the reviewer's
  extraction).

### 4.2 Mechanisms that transfer

1. **WTP discovery from the secondary market → from comps' *sales*, not their asks.** A team learns WTP from
   resale prices; we can learn it from which comp nights *disappear* from availability at what ask. The
   comp scraper already distinguishes "checked and unavailable" from "could not check" (`scrape_status`).
   A comp night that was available at $X on day t and unavailable on day t+1 is a (noisy) sale at ≤ $X. This
   is our largest potential source of price-response observations (see §8.2 and Recommendation 2).
2. **The single-unit price path (Sweeting).** For a home on a night that is not near-certain to sell, the
   optimal path declines toward the deadline as the option value of waiting decays. Expected value of
   keeping a night open at lead ℓ ≈ `Σ_{future decision days} P(book on that day | price) × owner net`. The
   M3 one-step horizon in MODEL_SPEC is a crude version; the Sweeting model gives the shape.
3. **Floors and ceilings protect the incumbent channel.** Teams set floors so dynamic pricing does not
   undercut season-ticket holders. Our analogue is guests who booked early: deep close-in cuts teach future
   guests to wait. This supports keeping the off-peak close-in discount bounded (pace `min_multiplier` 0.85).
4. **Disclosure.** The guest should see one total price that does not change during checkout; the FTC rule
   now requires this for short-term lodging (§9).

## 5. Theme parks

Disney moved from flat to seasonal one-day pricing in 2016 (up to 20% more on peak days) and to date-based
pricing at Walt Disney World in 2018, with prices "modelled off of consumer demand" set in advance for each
date and not changing in real time; the stated aim was to spread attendance across the year [S46]. **STALE.**
Transferable idea: **posted date-based prices, set early and changed rarely**, are a credible alternative
to daily dynamic pricing when the buyer plans months ahead and compares dates, and when price volatility
damages trust. For our peak weeks this argues for publishing the holiday-week price early and moving it
only on a booking-curve breach (band control, §3.3), not daily. I did not find disclosed lift figures for
Disney's date-based pricing.

Six Flags is the adversarial case. In Q2 2025 attendance fell 9% (14.2 M) with fewer single-day tickets,
fewer season passes and lower renewals; the active pass base fell about 579,000 units (−8%). Over the nine
weeks to 2025-08-31, attendance rose by 298,000 visits (the release does not attribute them to
promotions) while per-capita spending fell 4% ($2.50), which the company attributed to "incremental
promotions designed to drive volume" [S47]. The fall is entirely a 7% drop in **admissions** per capita;
in-park product spending per capita rose slightly. So the lesson is that discounts lowered the ticket
yield, not that discounted guests spent less in the park. For our homes, the parallel is that a deep
close-in discount lowers the yield on the night itself and may cost the same to turn over: owner net can
fall while occupancy rises. That is the Huang result (§2.2) seen from the operator side.

## 6. Rideshare surge pricing

- **Consumer surplus and elasticity.** Cohen, Hahn, Hall, Levitt & Metcalfe (NBER w22627, 2016; not peer
  reviewed at the time; two authors were Uber economists, a disclosed conflict) use almost 50 million UberX
  sessions and a regression-discontinuity design on Uber's surge algorithm to estimate demand elasticities at
  several points along the demand curve; they estimate about $2.9 B of consumer surplus in four US cities in
  2015 and describe demand as inelastic [S24]. The identifying variation, as I understand the paper, comes
  from the surge multiplier being a rounded version of an underlying continuous demand/supply measure, so
  sessions just above and below a rounding threshold face different prices under nearly identical
  conditions. **UNVERIFIED**: the abstract does not describe the rounding mechanism; I did not read the body.
- **Who gains.** Castillo (*Econometrica* 93(5):1811–1854, 2025), a spatial equilibrium model on Uber data:
  surge raises total welfare by 2.15% of gross revenue; riders gain 3.57%; drivers lose 0.98% and the
  platform's current profit 0.50%; long-hours drivers are hurt most. Earlier drafts reported different
  magnitudes (3.53% total welfare in the 2020 NBER version) [S25].

**What transfers.**

1. **Natural experiments inside our own pricing rules (RD idea).** Our engine has thresholds that change
   price discontinuously: move caps (±12% / $250), the peak blackout threshold, the 42-day anchor age and
   3-comp minimum (`ANCHOR_MAX_AGE_DAYS`, `ANCHOR_MIN_COMPS` in `pace.py`), and the min-stay lead buckets
   (`min_stay_rules` in `default.yaml`: peak 14/60-day breakpoints). Nights just on either side of a threshold
   are otherwise similar. If the engine logs the "unclamped" price next to the shipped price, each clamp is an
   observation of price response at a known price difference. With ~100 bookings a year the power is tiny;
   pooled with comp-fill observations (§4.2) it becomes usable. Module: `src/explain` / `src/eval` logging;
   analysis in `src/elasticity`.
2. **Real-time clearing does not transfer.** Surge solves a market that rebalances in minutes with elastic
   supply (drivers move). Our supply is three fixed homes and guests plan weeks to months ahead. Price
   changes during a guest's search or checkout harm trust (Oasis, §4) and buy nothing.
3. **Fairness asymmetry.** Rider gains, driver losses: the distribution matters to whoever is on the losing
   side. For an operator, the "losing side" is the owner whose home is discounted to fill occupancy. Report
   owner net per home (already planned) and never let the portfolio term (M5 twin cannibalization) move
   money from one owner to another without showing it (`config/portfolio/mont_luxe.yaml` already separates
   owners).

## 7. Retail and e-commerce markdown optimization

- **Rue La La** (Ferreira, Lee & Simchi-Levi, *M&SOM* 18(1):69–88, 2016). A flash-sale retailer where most
  revenue comes from items never sold before. The method: machine learning to estimate lost sales on
  stocked-out items (unconstraining) and to forecast demand for new items from similar past items, then a
  multiproduct price optimization that includes the effect of competing styles' prices (a reference-price
  term). In a field test, sales did not fall when the tool's recommended price *increases* were applied to
  medium- and high-price items; the estimated revenue increase for the test group was about 9.7%, 90% CI
  [2.3%, 17.8%] [S27]. The authors worked with the retailer (both collaborators, not independent). The
  model detail I give next is from my prior reading of the paper and was **not re-verified this session**
  (the full text request was rate-limited): demand was modelled with regression trees whose features include
  the item's price relative to the average price of competing styles in the same event, and the price
  optimization was made tractable by enumerating the possible *sum* of competing prices and solving a linear
  relaxation for each value.
- **Zara** (Caro & Gallien, *Operations Research* 60(6):1404–1422, 2012). A formal forecasting model feeding a
  price optimization model for clearance markdowns, replacing a manual process; a controlled field test in
  Belgian and Irish stores (fall–winter 2008) increased clearance revenue by about 6%, and Zara adopted it
  worldwide [S48]. **STALE.** Co-developed with the retailer.
- **Amazon.** Cooprider & Nassiri, "Science of price experimentation at Amazon" (*Business Economics*,
  2023; AEA/NABE 2023) [S83; abstract page read 2026-10-19]: Amazon runs **product-randomized**
  experiments, not customer-randomized ones, uses **crossover designs** to improve precision, and controls
  for demand trends. For three homes, randomizing a home's price arm **over time** (crossover by check-in
  week) without showing two prices at once is the closest feasible design. It links directly to
  Recommendation 6 and to R1's field-test design.

**What transfers.**

1. **Borrowing demand from similar products (Rue La La).** Each night of each home is a "new product" with
  almost no own history. The comp set and the market sweep (~280 listings per sweep, README) are the
  "similar past items". This is the strongest methodological case in this dossier for building the price
  response from **market** observations (comp availability transitions), with our own bookings as the
  correction layer.
2. **Price increases can be free.** Rue La La found no sales loss from recommended increases on higher-price
  items. That is the empirical mirror of our problem (the engine was charging *below* the real rate card,
  `OVERHAUL_2026-10-14.md`: $224k vs $365k simulated owner net for the default engine). An engine that
  under-prices luxury inventory is the more common failure.
3. **Markdown with a deadline (Zara).** Clearance pricing is the Gallego–van Ryzin problem (§10.1) with a
  hard end date. It transfers to the last 2–3 weeks before an open night, bounded by the floor (owner net
  ≥ turnover cost + a margin).

## 8. Brief notes: golf, restaurants, parking, electricity, freight

| Industry | Mechanism | Evidence | Transferable idea | Module |
|---|---|---|---|---|
| Golf tee times | Tee-interval (capacity) design; time-of-day pricing | Kimes & Schruben (*JRPM* 2002): shorter intervals can *reduce* revenue; Kimes & Wirtz (*JRPM* 2003): golfers saw time-of-day pricing and reservation/no-show fees as fair, varying price *levels* as unfair, and discounts framed as discounts fairer than surcharges [S49] **STALE** | Present date variation as a **discount off a posted high price**, not a surcharge on a base | `src/explain/present.py` (owner/guest framing) |
| Restaurants | RevPASH; two levers: demand-based pricing and **duration control** | Kimes, Cornell (2004 CHRAQ article on duration control) [S50] **STALE** | Duration control = minimum stay and stay-length shaping; it is a lever separate from price | `src/min_stay` |
| Parking (SFpark) | Target occupancy band 60–80%; step price changes every two months | Pierce & Shoup (practitioner; Shoup originated the idea): 62% of blocks in band after two years (UCLA brief), average price −4% over two years, elasticity −0.4 (5,294 changes); SFMTA: target met 31% more often than control areas [S42] **STALE**. Millard-Ball et al.: each rate change moves a block only 0.1–0.2% closer to target [S82] | **Band control with slow, discrete steps** (Recommendation 1) | `src/pricing/pace.py` |
| Electricity CPP | Peak/off-peak price ratio drives a diminishing-returns ("arc") peak reduction | Faruqui & Sergici "Arcturus": response is a function of the price ratio, with diminishing returns beyond a threshold; enabling tech increases response [S51] | **Diminishing returns to the holiday premium ratio**: past some multiple of the base rate, extra premium mostly loses bookings | `src/ceiling`, simulator WTP |
| Freight (Maersk Spot) | Fixed upfront price + loading guarantee + no-show fee (double the cancellation fee inside 7 days) + carrier compensation if it fails [S52] | Two-sided commitment | Tiered cancellation terms by lead time for direct bookings; a refundable/non-refundable price spread | `src/pms` (policy), `src/bookprob` (cancel hazard) |

## 9. Vacation-rental managers and platforms at scale

- **Airbnb Smart Pricing** (Ye et al., KDD 2018, pp. 932–940). Three stages: a GBM booking-probability model
  per market (listing, temporal, and supply/demand features including views and search/contact rates); a
  "strategy" regression that predicts a price inside a target interval; then personalization. The loss is
  zero when the suggested price lies in `[L, U]` and linear outside it, with `[L, U] = [P, c₂P]` for a
  booked night (c₂ > 1: it might have sold higher) and `[c₁P, P]` for an unbooked night (0 < c₁ < 1: it was
  too high). Offline metrics: price-decrease recall (share of unbooked nights where the suggestion was below
  the listed price) and booking regret (median shortfall of the suggestion below the booked price) [S53]
  (The Morning Paper summary of the paper; the formula is an image in the original).
- **Why Smart Pricing under-prices for some hosts.** Huang (2021 working paper, Kilts/QME conference): a
  revenue-maximizing platform algorithm does not internalize seller costs; in his counterfactual it prices
  26% below the sellers' own baseline, occupancy rises to 90%, the median seller earns 8% less than baseline,
  56% of sellers are worse off and the platform gains 1.7%; a design where the platform sets *variation* and
  sellers set *levels* removes almost all frictions [S35]. Airbnb is paid a share of revenue, not of host
  profit; the incentive gap is structural.
- **Vacasa** (10-K FY2023/FY2024): "proprietary pricing tools to optimize homeowner income", rates adjusted
  "across all our channels based on a guest's itinerary, a home's availability, and real-time booking
  dynamics", with ML teams iterating to improve revenue per available night [S54]. Vacasa lost about 4,000
  homes in the year to Q3 2024 and was acquired by Casago (closed 2025-04-30 / 05-01, about $130 M);
  Casago then sold off all former Vacasa markets [S55]. Sophisticated pricing did not prevent homeowner
  churn; service quality and owner trust drove the business.
- **Sonder** filed Chapter 7 in November 2025 after Marriott ended their licensing agreement [S56]. Not a
  pricing failure as far as the sources say; a reminder that scale and technology do not guarantee unit
  economics.
- **Vrbo / Expedia.** Public material is limited to job postings describing a pricing ML team using causal
  inference, demand estimation, OR and A/B tests, steerable to a volume-vs-profit trade-off [S57]. No
  engineering paper found.
- **STR-specific elasticity estimates.** Huang estimates an average Airbnb price elasticity of −2.51 in San
  Francisco, consistent with experimental estimates he cites [S35]; a 2023 arXiv paper cites a Farronato &
  Fradkin structural estimate of about −2.33 for the Boston economy segment [S58]. These are urban,
  small-unit markets. Our policy priors (peak −0.65, shoulder −1.70) are far less elastic; that is plausible
  for luxury ski-week inventory but is **not supported by any estimate I found** for that segment.

### 9.1 What generic STR pricers miss (H2), from this section

1. **The objective.** A platform paid on revenue optimizes revenue; Huang's counterfactual shows what that
   does to sellers with real per-stay costs. A 16-guest luxury home's turnover cost and the owner's share
   after a 25% management fee make the gap larger, not smaller. Our engine's owner-net objective is a real
   difference, if it is kept everywhere.
2. **Levels vs variation.** Generic tools mostly let the user set a base price and apply multipliers. The
   Huang/Filippas evidence says that split is roughly right; the error is when the *base* is set from the
   tool's market data for small units (the AirDNA $379 market ADR, `OVERHAUL_2026-10-14.md` §2.1) instead
   of the home's own rate card and true peers.
3. **Leading indicators.** None of the generic tools' public documentation mentions pass sales, Inntopia
   pace, or lift-ticket prices (§1.5). This is a weak edge (few observations) but a real one.

## 10. Cross-cutting techniques

### 10.1 The single-unit, finite-horizon price path (Gallego & van Ryzin)

Gallego & van Ryzin (*Management Science* 40(8):999–1020, 1994) solve dynamic pricing of `n` units with a
deadline under Poisson demand of intensity `λ(p)`. For exponential demand `λ(p) = a·e^{−αp}`, in price units
where `α = 1`, the optimal revenue-to-go and price are (their equations 9–10, read from the paper) [S59]:

```
J*(n, t) = log( Σ_{i=0..n} (λ* t)^i / i! ),      λ* = a / e
p*(n, t) = J*(n, t) − J*(n−1, t) + 1
```

For one unit (one home, one night, `n = 1`) this collapses to

```
p*(1, t) = 1 + log(1 + λ* t)        (in units of 1/α)
```

where `t` is the remaining selling time and `λ* t` is the expected number of arrivals that would buy at the
static monopoly price `1/α`. Reading: the price premium over the static price is `log(1 + expected remaining
full-price arrivals)`. It decays to zero at the deadline. More time, or stronger demand, means a higher price;
the paper's Theorem 1 states this monotonicity in general (price rises with remaining time, falls with
remaining stock) [S59]. This is the formal version of Sweeting's empirical finding (§4) and the shape that
MODEL_SPEC's M3 "one-step horizon" approximates.

**Engine version (first implementation).** Per night `d` at lead `ℓ`:

1. `α` from the elasticity at the reference price: for exponential demand the point elasticity is `−α·p`, so
   `α = −β / P_ref` (with `β` the all-in-adjusted elasticity from `pace.all_in_beta`).
2. `λ* t` = expected number of "would-book-at-reference" arrivals between now and the night, from the
   booking curve: `λ* t ≈ −ln(1 − q_rem(ℓ))`, where `q_rem(ℓ)` is the probability that an open night at
   lead `ℓ` still sells at the reference price (for the reference curve in `pace.py`:
   `final_occ × (1 − curve_share(ℓ)) / (1 − final_occ × curve_share(ℓ))`). A Poisson stream with mean
   `λ* t` produces at least one buyer with probability `1 − e^{−λ* t} = q_rem`.
3. `P*(ℓ) = P_ref·[1 + log(1 + λ* t)] / (αP_ref)`; with `αP_ref = −β`, `P* = P_ref · (1 + log(1 + λ*t)) / (−β)`.
   For `β = −1` and no remaining demand this returns `P_ref`. Owner net enters by replacing price with
   owner share × price + fee margin before the argmax, as `pace.py` already does.
4. Clamp by floor, ceiling and move caps as today.

Where it breaks: exponential demand is a modelling choice; multi-night stays are not single units (§2.2
handles that); and `λ*` depends on the curve we cannot yet estimate well. Use it as the *shape* (how fast
the premium should decay with lead) inside the simulator before letting it set levels.

### 10.2 Learning while earning with ~100 bookings a year

What the theory says, with the parts that matter for us:

| Result | Statement | Implication at our scale |
|---|---|---|
| Besbes & Zeevi (*OR* 2009) [S30] | Pricing with an unknown demand curve over a finite horizon; near-optimal algorithms separate exploration and exploitation, parametric and nonparametric cases | Exploration phases are measured in sales opportunities; ours are few |
| Keskin & Zeevi (*OR* 62(5):1142–1167, 2014) [S31] | Linear demand with unknown parameters: best achievable regret is order √T with no prior knowledge, but order **log T if expected demand at an incumbent price is known**; variants of greedy iterated least squares reach these rates | Our `current_practice` rate card is an incumbent price with known outcomes. Anchoring experiments on it is the theoretically favoured regime |
| den Boer & Zwart (*Mgmt Sci* 60(3):770–783, 2014) [S32] | Greedy (certainty-equivalent) pricing can stop learning; **controlled variance pricing** adds a taboo interval around the average of past prices so prices stay dispersed enough to learn; consistent, with regret bounds | Our M1 Thompson draw does not create enough dispersion (below) |
| den Boer survey (*Surveys in OR&MS* 20(1):1–18, 2015) [S33] | Review of dynamic pricing and learning | Background |
| Ferreira, Simchi-Levi & Wang (*OR* 66(6), 2018) [S60] | Thompson sampling for price-based network RM with inventory constraints; strong guarantees and good numerics | The inventory-aware TS is the right family for limited nights |
| Bastani, Simchi-Levi & Zhu (*Mgmt Sci* 68(3):1865–1881, 2022) [S61] | "Meta" dynamic pricing: learn a shared prior across many products' TS experiments; regret sublinear in the number of products | Treat each (home, season) or each comp as a product drawing from a shared prior |

**Power arithmetic for our data (my calculation, not from a source).** Estimate a constant elasticity from
two price arms `P_hi = 1.1·P_0` and `P_lo = 0.9·P_0`, with booking probability per night-decision `p ≈ 0.3`
and `n` nights per arm. The log-ratio estimator `β̂ = ln(r_hi/r_lo) / ln(P_hi/P_lo)` has
`Var(β̂) ≈ [2(1−p)/(n p)] / [ln(1.1/0.9)]² ≈ 116 / n`. So:

*Variance only; assumes exogenous prices. It says nothing about bias.*

| Nights per arm | SE(β̂) | Who has that many |
|---:|---:|---|
| 100 | 1.08 | — |
| 225 | 0.72 | our three homes, one full winter, every night randomized (unacceptable at peak) |
| 1,300 | 0.30 | about 6 winters of the whole portfolio |
| 20,000 | 0.08 | the market sweep: ~280 listings × ~150 winter nights ≈ 42,000 listing-nights per season |

**Our own bookings cannot identify elasticity within a season at any useful precision.** Comp-market
transitions give enough *variance* (the last row), but not identification. Comp prices are set in response
to demand: hosts raise prices on nights they expect to sell, so a regression of available→unavailable
transitions on ask is biased toward zero or even toward a positive elasticity. Huang [S35], using the same
kind of San Francisco calendar data, finds "prices are endogenous to demand shocks" and needs a control
function. Her data section also gives a blocked-night rule: nights unavailable from the first scan are
treated as owner blocks, not sales. Practitioner tools use the same snapshot differencing, with known
failure modes (a host block created after the first scan looks like a sale). A comp fill also estimates a
market response, not Cloud 9's own-price elasticity against its substitutes.

So a comp-fill estimator needs a named identification strategy before it ranks above Low: a control
function as in Huang, an instrument (for example cost or fee-structure shifters that move asks but not
demand), or discontinuities in comps' own rule-based pricing (minimum-price floors, last-minute rules).
Until then it is a shadow covariate. Scraper reliability (the binding constraint named in the shared
context) and stored calendar availability come first in any case (Recommendation 2).

**What the current M1 does, measured against this.** MODEL_SPEC M1 and `src/pricing/__init__.py:94` draw
`β ~ Normal(β_post, 0.35/√(40+n))`. At `n = 0` the scale is 0.055. With linear demand,
`P* = P_ref(β−1)/(2β)`, so the relative price change per unit of β is `1/(β(β−1))`. An earlier draft used
the default shoulder prior (−1.70) with no all-in conversion and got about 0.95% per SD. That is wrong for
the engine under review. The candidate `pace_v3_anchor_repair.yaml` uses priors of −1.00 (peak) and −1.10
(other seasons), and with `beta_is_all_in: true` the prior is first scaled by `all_in_beta`
(`price/(price + 357.5)` at party 10, LOS 4; `src/pricing/__init__.py` near line 497). At $2,000 the
working β is about −0.85 (peak) or −0.93, so **one SD of exploration moves the price about 3–4%**
(audit recomputation: 3.5% peak and 3.0% other at $2,000; 4.0% and 3.5% at $1,200). Exploration is
switched off on blackout nights (`demand_strength ≥ 0.85`). Over about 100 decisions a season that is
real dispersion, comparable to the ~9% three-week comp drift noted in `pace.py`. It still identifies little:
the power table above gives SE ≈ 0.7 even with a season of randomized nights. So the case for explicit,
controlled exploration rests on the power table, not on M1 being too small to matter. If exploration is
wanted, it should be
explicit: a **taboo-interval / controlled-variance rule on off-peak nights** (keep each new price at least
`δ_t` away from the running mean of recent prices for that home-season, with `δ_t` shrinking like
`t^{−1/4}` per CVP's spirit; the exact schedule should be taken from the paper, which I read at abstract
level only), bounded by the move cap, logged, and **never** on peak-blackout nights.

**What survives at our scale:**

1. Anchor on the incumbent (Keskin–Zeevi log T regime): experiment as small offsets from `current_practice`,
   not from a model optimum.
2. Pool (Bastani et al.; §10.3) across homes and comps.
3. Learn from comps' fills (Rue La La's "similar products").
4. Explore only off-peak, with explicit dispersion, inside the move cap.
5. Do not run per-night bandits: there are about as many arms as observations.

### 10.3 Bayesian hierarchical pooling

Model (first version, implementable in `src/elasticity`):

```
β_{h,s}  ~ Normal(μ_s, τ_s²)          home h, season s
μ_s      ~ Normal(β_prior_s, σ_0²)    β_prior_s from booking_probability.elasticity_by_season
β̂_{h,s} | β_{h,s} ~ Normal(β_{h,s}, v_{h,s})     v from the estimator above (≈116/n)
β̂_{c,s} | μ_s     ~ Normal(μ_s + δ_tier, v_{c,s} + τ_c²)  comps c, with a tier offset δ_tier for capacity
```

Posterior mean for a home (conjugate normal, standard partial pooling as in Gelman et al., *Bayesian Data
Analysis*, 3rd ed., ch. 5 [S62]):

```
E[β_{h,s} | data] = ( β̂_{h,s}/v_{h,s} + μ̂_s/τ_s² ) / ( 1/v_{h,s} + 1/τ_s² )
```

With `v_{h,s} ≈ 0.5` (one season) and `τ_s ≈ 0.3`, the home's own estimate gets weight
`(1/0.5)/(1/0.5 + 1/0.09) ≈ 0.15`. The current `κ = 40` shrinkage in MODEL_SPEC is a fixed-weight version of
the same idea; the hierarchical version lets comp evidence move `μ_s` and lets the weight follow the measured
variance instead of a constant. Measure: replay Brier and log-loss of `P(book)` on held-out nights
(`proving_ground_exam/` L1 gate), then owner net in the 25-seed paired simulator.

### 10.4 Reference prices and fairness

- **Reference-dependent demand.** The standard form (reviewed by Mazumdar, Raj & Sinha, *Journal of
  Marketing* 69(4):84–102, 2005 [S63]; and the "empirical generalizations" of Kalyanaram & Winer, *Marketing
  Science* 14(3, suppl.):G161–G169, 1995 [S64], read at abstract level: consumers use reference prices,
  past prices form them, and they react more to prices above the reference than below) is
  `q = a − b·p + γ⁺·max(r − p, 0) − γ⁻·max(p − r, 0)`, with internal reference price updated by exponential
  smoothing `r_{t+1} = θ r_t + (1 − θ) p_t` and loss aversion `γ⁻ > γ⁺`. For our guests `r` is most plausibly
  (a) what the same week cost last year for repeat guests, and (b) the visible comp prices. Implication: a
  large year-over-year jump on a repeat family's week costs more conversion than the same jump on a new
  guest. Test: aggregate repeat-guest conversion vs YoY price change, per the guest-data contract.
- **Fairness.** Kahneman, Knetsch & Thaler (*AER* 76(4):728–741, 1986): raising prices to exploit a demand
  shift is judged unfair (the snow-shovel vignette: about 82% "unfair" or "very unfair") while passing on
  cost increases is acceptable [S65]. Kimes & Wirtz found golfers accept time-of-day pricing but not varying
  price *levels*, and accept demand pricing better when framed as discounts [S49]. Alnes & Haugom (*Journal
  of Retailing and Consumer Services* 81, 2024) found framing price differences as a loss or a gain has an
  asymmetric effect on perceived fairness, and larger high-low gaps reduce perceived fairness; a survey of
  1,627 skiers in four countries linked perceived unfairness of RM to lower purchase intent and a desire for
  revenge [S66]. **Operational rule:** publish the high (holiday) price as the list price and show lower dates
  as savings against it, rather than surcharging holidays against a base; explain prices with season and
  event reasons the guest can see (holiday week, school breaks), which is what `src/explain/present.py`
  already does for the owner.

### 10.5 Price presentation: all-in fees, drip pricing, charm prices

- **The rule.** The FTC's Rule on Unfair or Deceptive Fees (16 CFR Part 464), effective 2025-05-12, makes it
  unfair and deceptive to advertise any price for short-term lodging without clearly and prominently
  disclosing the total price including mandatory fees; it covers third-party platforms [S40]. Cleaning,
  per-guest consumables and the $80 insurance (if mandatory) must be inside the displayed total.
- **The evidence.** Blake et al. (StubHub field experiment, §4.1): upfront fee display lowered both purchase
  quantity and the price tier bought [S41]. Under the rule, everyone shows all-in, so the competitive
  question becomes how our all-in compares with comps' all-in. Our comp scraper must therefore record
  comps' **fee-inclusive** totals for the same stay length and party (OVERHAUL item 2.10 notes Airbnb totals
  can include fees when no nightly breakdown is shown). Comparing our nightly rate with comps' fee-inclusive
  totals, or the reverse, is a systematic error of the size of the fees: (600 + 75×12 + 80)/4 nights ≈ $395 a
  night, about 20% of a $2,000 rate.
- **The fee structure is itself a price lever.** Per-guest consumables at $75 make the all-in total rise with
  party size; a cleaning fee spread over few nights raises the all-in per-night of short stays. Under all-in
  display, short stays look expensive and long stays cheap. That is demand shaping toward longer stays at no
  nightly discount. `pace.all_in_beta` already scales elasticity by `price/(price + fees per night)`; it uses a
  *typical* LOS and party. A version that uses the requested LOS and party (when known, for quotes on the
  direct site) would be more accurate.
- **Charm prices.** Anderson & Simester (*QME* 1(1):93–110, 2003): in three field experiments, $9 endings
  raised demand, more for new items and less when "sale" cues were present; the authors suggest they work when
  customers have limited information [S67]. For an all-in total near a round threshold (a 4-night stay
  totalling $10,080 vs $9,980), a small nightly adjustment that puts the *total* below the threshold is
  cheap to test. **Hypothesis**; no lodging-specific evidence found. Module: `src/compose` rounding step.
- **Colorado HB25-1090** (effective 2026-01-01) is a state total-price ("junk fee") rule for businesses
  generally, enforced as a deceptive trade practice [S86]. How it applies to short-term rentals is
  unconfirmed; treat all-in display as required in Colorado as well as under the FTC rule.

### 10.6 Demand shaping: low-demand discounts, minimum stays, packaging

- **Low-demand dates.** Disney's date-based prices (§5), Malasevska's midweek and bad-weather discounts
  (§1.3), and SFpark's band steps (§8) all lower price where capacity would otherwise go unused, with
  prices posted in advance. For a home, a soft midweek January night is the only place a discount is likely
  to pay; discounting peak nights to "fill" is the Six Flags trap.
- **Minimum stays as duration control.** Restaurant RM separates duration control from price (Kimes) [S50];
  hotel RM formalized multi-night requests as a DP with heuristics (Bitran & Mondschein, *OR* 43(3):427–443,
  1995) [S68]. Our `min_stay_rules` (peak: 2 nights inside 14 days, 3 for 15–60, 4 beyond 60) are a
  lead-time duration control. The car-rental bid-price test (§2.2) is the rule for when to relax them.
- **Packaging.** Ikon's pre-season lodging offer bundles a 4+ night stay with lift-ticket discounts and
  resort credit [S13]; cruise lines pre-sell onboard spend [S12]. A direct-booking package (home + lift
  tickets bought at the advance price + rentals) lets the operator present a total that is hard to compare
  line by line, which (per Anderson & Simester's "limited information" mechanism) may soften price
  comparison. Legal/compliance note: any mandatory component must still be in the displayed total [S40].

## 11. Transfer analysis

### 11.1 Transfer table

Value is judged on owner net vs `current_practice`; "High" means plausibly several percent of season owner
net, "Low" means under 1% or unmeasurable at our scale. Effort: S (days), M (1–3 weeks), L (more).

| # | Method (industry) | Core assumption | Holds for 3 STR homes? | Adaptation needed | Expected value (owner net) | Effort |
|---|---|---|---|---|---|---|
| 1 | Booking-curve band control (cruise "a couple of points", SFpark band) | A stable target booked-share curve exists; price is the control | Partly: the curve is noisy at 3 homes, so a dead band is *more* useful, not less | Additive (pp) comparison instead of ratio; band width from binomial noise of the window; no cuts beyond lead ℓ*; holiday weeks use their own curve | Low–Medium (volatility and robustness; the −6.6% gap is a level gap and is not claimed) | S–M |
| 2 | Base loading then yield (cruise) | Early base bookings de-risk the product; later demand pays more | Yes for holiday weeks and peak months; no for soft shoulder | A per-season "base" target (e.g., N holiday-week bookings by lead X); once met, raise; until met, hold at rate card | Medium | M |
| 3 | Price-drop guarantee (cruise; Levin–McGill–Nediak) | Buyers fear later price drops; seller can commit | Direct channel only; OTAs do not support it | Credit-back terms; engine must count the expected guarantee cost when cutting a booked date's price | Low–Medium (enables early group commitment) | M (policy + PMS) |
| 4 | Advance commitment with insurance (ski passes, Epic Coverage, Ikon's separate "Refundable" products) | Customers commit early if downside is capped | Yes: large parties plan early; refundable vs non-refundable split exists on OTAs | A non-refundable price spread and a refundable price; cancel hazard by policy in `src/bookprob` | Low–Medium | M |
| 5 | Pass sales / visits as leading indicators (ski filings) | Season-level demand is partly known months ahead | Yes at season level; no at night level | Shadow signals at season granularity; enter M2's reference shift only after the ladder | Low–Medium | S (collectors) |
| 6 | Weather/snow-contingent prices (Malasevska; Andermatt pilot) | Day-level weather drives day-level demand | Weakly: lodging is booked weeks ahead, so forecasts are useless beyond ~10 days; snowpack matters seasonally | Use snowpack (SQI) as a slow prior; use 5-day forecasts only for last-minute open nights | Low–Medium (only close-in) | S (exists as SQI) |
| 7 | Demand shifting across days (Malasevska cross-price) | Customers substitute between dates | Yes for flexible-date families; unknown share | Simulator shopper behaviour first | Low (uncertain) | M (simulator) |
| 8 | Length-of-rental / multi-day displacement (car rental, Li & Pang; hotel Bitran–Mondschein) | Accepting a multi-day request displaces other requests | Yes, strongly (every booking is multi-night) | Bid price per night = expected owner net if left open; stay accepted if price ≥ Σ bids + orphan loss; drives min-stay relaxations | Medium | M |
| 9 | Partial control: owner sets level, engine sets shape (Filippas; Huang) | Owners have private costs/preferences | Yes | Owner-confirmed seasonal anchors; engine multipliers within caps (current autonomy ladder) | Protects against large losses; keeps owners | S |
| 10 | Owner-cost-aware objective (Huang) | Revenue max ignores per-seller cost | Weakly: Huang's cost is time per night; ours is a turnover cost largely covered by the guest fee (owner-side margin about $7/night) | Keep owner net everywhere; audit any gross-RevPAN code path | Guards a failure class; the −38% default-engine result was caused by peak caps and low ceilings (OVERHAUL), not a gross objective | S (audit) |
| 11 | Single-unit finite-horizon price path (Gallego–van Ryzin; Sweeting) | Poisson arrivals, known demand, one unit, deadline | Approximately per night | Exponential demand calibrated from β; λ*t from the booking curve; simulator first | Medium (shoulder/close-in) | M |
| 12 | Thompson sampling / bandits (Ferreira et al.; Besbes–Zeevi) | Many sales opportunities per arm | **No** at night level (~100 bookings/yr) | Only pooled, off-peak, with explicit dispersion (CVP) and incumbent anchoring | Low in year 1; grows with pooled data | M |
| 13 | Meta / hierarchical prior across products (Bastani et al.; BDA) | Products share a prior | Yes (3 homes + comps share a market) | Normal–normal pooling with comp tier offsets | Medium (it is what makes #12 possible) | M |
| 14 | Learning from similar products and lost sales (Rue La La) | Demand for new items resembles similar past items | Only with an identification strategy: comp asks are endogenous to demand (Huang) | Comp-fill estimator: available→unavailable as a sale at ≤ ask; Huang's blocked-night rule; control function or instrument | Low until identified; gated by scraper health | L (scraper) |
| 15 | Secondary-market WTP discovery (ticketing) | Resale prices reveal WTP | Partly: comps' asks are not sales | Use comps' *transitions*, not asks; weight by capacity tier | Medium (same as #14) | (same) |
| 16 | Regression discontinuity on price rules (Uber surge) | Rule thresholds create quasi-random price variation | Yes in principle; tiny power | Log unclamped vs shipped price and thresholds; pool with #14 | Low alone | S (logging) |
| 17 | Date-based posted prices, changed rarely (Disney) | Planners compare dates months ahead; volatility hurts trust | Yes for holiday weeks | Publish holiday-week prices early; change only on band breach | Low–Medium; trust | S |
| 18 | Discount framing / fairness (Kimes–Wirtz, KKT, Alnes–Haugom) | Framing changes perceived fairness and intent | Yes, esp. repeat families | List the high price; show savings on soft dates; YoY cap on repeat weeks (test) | Low direct; protects reviews | S |
| 19 | All-in display and fee design (FTC rule; Blake et al.) | Guests judge totals | Yes, and now mandatory | Compare all-in vs all-in; LOS/party-specific all-in elasticity; fee design shapes LOS | Medium (comp comparisons currently mix bases) | S–M |
| 20 | Charm totals (Anderson–Simester) | Price endings affect demand under limited info | Untested for lodging | Round the *total* just below thresholds on the direct site; A/B impossible at our n, so simulate only | Low | S |
| 21 | Real-time surge (rideshare) | Market rebalances in minutes; supply elastic | No | Do not copy | None / negative | — |
| 22 | Full-scale cruise/airline optimization (20 M price points) | Large inventory, many observations | No | — | None | — |
| 23 | Volume promotions (Six Flags) | Extra volume pays | Often no: ticket yield falls (Six Flags' −4% was admissions yield), turnover cost rises | Floor = owner-net breakeven, not occupancy | Avoided loss | S |
| 24 | Duration control (restaurants) | Duration is a lever separate from price | Yes (min stay) | Already in `min_stay_rules`; tie relaxation to #8 bid prices | Low–Medium | S |
| 25 | Two-sided commitment with penalties (Maersk Spot) | Both sides bear cancellation cost | Partly (owner blocks; guest cancellations) | Lead-time cancellation tiers; refundable spread | Low | S |

### 11.2 Ski-industry signals we can ingest

All enter at `experimental` and move only through `config/policies/signals.yaml` (n ≥ 30 to shadow; n ≥ 40,
IC ≥ 0.05, hit rate ≥ 0.52 to active). `observed_at` is the publication timestamp, never the period end, so
`assert_no_lookahead` holds. Season-level signals have few observations (one per release, about ten winters
of history); they can never reach n ≥ 40 within the current ladder unless the outcome is defined per
(market × month), so **the ladder needs a season-level variant or these stay shadow forever.** That is an
open question for the operator (§13).

| Signal | Source | Cadence and timing | Lead on Winter Park lodging demand | What it measures | How to test |
|---|---|---|---|---|---|
| Epic pass units, days and dollars YoY, with the segment commentary (destination vs local, frequency) | Vail 8-K press releases on SEC EDGAR [S01][S02][S04] | 4 per year: early June (spring sales to late May), late September (to mid-September), early December (to early December); the March Q2 release covers the season to date | 2–9 months for the coming winter | Committed skier base; destination low-frequency is our segment | Regress Grand County / Winter Park lodging-tax receipts (rate-change adjusted, dossier 03) and Inntopia winter occupancy on YoY pass units, 2015/16–2025/26 excluding 2020/21; out-of-sample sign test on the last 3 seasons; expect sign only, not a coefficient |
| Vail season-to-date metrics (skier visits, lift revenue, ski school, dining) | Vail 8-K, e.g. release of 2026-01-15 covering the period to 2026-01-04: visits −20.0%, lift revenue −1.8% [S69] | Mid-January and early March (with Q2) | 0–10 weeks (February–April nights) | Realized visitation in the season, including snow effect | Correlate with our pace for Feb–Mar nights at the release date; IC on (home × night) pace residuals |
| Ikon pass price and deadline calendar; product changes (e.g. 2026/27: the separate "Ikon Pass Refundable" and "Base Refundable" products refund 100% with no scans by 2027-01-15 and 50% after one scan; full pass $1,329 → $1,349 renewal / $1,399 new) | ikonpass.com, Alterra releases, trade press [S70][S71] | Launch in March; price steps through the year to a December end of sales | Indirect | Alterra's commitment push and competitor resort-lodging offers (pre-season 4+ night lodging deals [S13]) | Calendar entries in `config/policies/events.yaml`; test whether our inquiry volume moves in the 2 weeks around deadlines (aggregate counts only) |
| Inntopia DestiMetrics monthly market briefing (on-the-books occupancy and ADR for the next six months, 17 mountain communities, ~28,000 units) | corp.inntopia.com posts [S08][S72] | Monthly, mid-month, data as of month end | 0–6 months, by arrival month | Coincident-to-leading regional pace for the same arrival months | Directly comparable to our pace: test whether Inntopia's YoY on-the-books occupancy for arrival month m predicts our final occupancy and ADR for m; IC at (month) level, about 7 months × 10 seasons |
| NSAA / Colorado Ski Country visits | Association releases via press [S05][S06] | Annual (May–June preliminary) | Lagging for the next season (via pass sales) | Season outcome | Use only as an outcome/control in the backtests above |
| Winter Park dated lift-ticket prices | Winter Park online ticket store; `lift_ticket_window_usd` field already in `src/signals/collectors/resort.py` | Daily scrape, per future date | 0–90 days, by date | Alterra's own date-level demand forecast, revealed in its price | For each future date, the ticket price's premium over its seasonal median vs our pace for that date; IC by lead bucket. Alterra prices with far more data than we have, so its date premium is a cheap demand forecast |
| Epic/Vail lift-ticket prices at I-70 resorts | vail.com etc. (collector config already lists Vail and Breckenridge report URLs) | Daily | 0–90 days | Competing destination demand | Same as above; also a substitution signal (`src/signals/features/substitution.py`) |
| Pass-holder refund/insurance terms | Vail 10-K (Epic Coverage), Ikon policy | Annual | Season | How much commitment risk Alterra/Vail absorb | Qualitative; no test |

**Expected value, honestly.** These signals inform the *season-level* reference price (M2's `price_ref'`
term), at most a few percent, and they inform it months ahead, when the engine's comp anchor is weakest
(comps quote far-out nights less reliably). The one with night-level resolution and a plausible real edge is
**Winter Park's own dated lift-ticket price**, because it is Alterra's revealed demand forecast per date.
It is **not** cheap: the existing `lift_ticket_window_usd` field (`src/signals/collectors/resort.py`) is a
single window price scraped from the resort page, not a per-date price curve. A dated-price collector for the
ticket store is new work with terms-of-use questions (open question 4), and Alterra's date prices may track
its own lodging forecast rather than private-home demand.

### 11.3 What generic STR pricers miss (H2), consolidated

1. Season-level leading indicators specific to ski markets (pass sales by segment, Inntopia pace, resort
   dated ticket prices). Weak but real, and invisible to tools that read only listing calendars.
2. The owner-cost-aware objective (Huang). A tool paid on revenue, or a host optimizing revenue, under-prices
   high-turnover-cost luxury inventory.
3. Comparisons on the wrong basis: nightly vs all-in under the 2025 FTC rule, and small-unit market ADR vs
   16-sleeper peers.
4. Commitment instruments (price-drop guarantee, refundable spread, packages) that only an operator with a
   direct channel can offer.

Where specialization does **not** give an edge: the core math (pace, elasticity, LOS) is published and
generic tools already do versions of it (dossier 04/05); and with ~100 bookings a year we cannot out-learn a
tool that pools thousands of listings, unless we pool the market ourselves (Recommendation 2).

## 12. Adversarial pass: what contradicts or limits these findings

1. **Raising prices close in can lose money for STR hosts.** A study of Ibiza Airbnb listings (*International
   Journal of Hospitality Management*, 2021) estimates heterogeneous causal effects of price "surging" as
   the stay date approaches and finds it hurts host revenue on average [S76]. A Rome/Milan study (*Journal of
   Business Research*, 2022, >1.2 M observations, 2016–2019) finds greater price variability correlates with
   higher revenue, and earlier work disagrees in both directions (Oskam et al. 2018 positive; Leoni 2020
   negative) [S77]. **Both read only through search-result abstracts; authors UNVERIFIED** (the publisher
   returned HTTP 403, and the session hit a rate limit before a second lookup). Implication: Royal Caribbean's
   2026 close-in price *increases* [S10] come from a booked load factor the line already controls; a home
   that is behind pace should not copy them. Band control (Recommendation 1) only raises when *ahead* of
   the band.
2. **Vendor lift claims are conflicted.** Smart-Pricer claims +6–8% revenue per ticket and +36% advance
   booking time at Zermatt [S73]; the Andermatt pilot with Pricefx used early-booking discounts and five-day
   weather forecasts [S74]; Qcue's Giants case reports $7 M [S43]. All are vendor or vendor-friendly
   materials without a control group. Treat them as existence proofs, not effect sizes.
3. **Using competitor prices carries legal risk only in a narrow form.** The Ninth Circuit (Gibson v. Cendyn,
   2025-08-15) affirmed dismissal of a Sherman Act claim against hotels that independently licensed the same
   pricing software; the DOJ has argued a tougher line in amicus briefs [S75]. The DOJ's proposed final
   judgment with RealPage (2025-11-24, no admission of liability) bars real-time use of competitors'
   nonpublic data, allows nonpublic training data only if at least 12 months old, bans sub-state geographic
   models, requires removing features that limit price decreases, and imposes a monitor; public data stays
   allowed [S84]. California AB 325 (signed 2025-10-06, effective 2026-01-01) bans using a "common pricing
   algorithm" as part of an anticompetitive combination [S85]. Our comp anchor uses public listing prices
   and no shared nonpublic data, which is the safe side of that line, but the engine should never ingest
   competitors' nonpublic data from a shared vendor.
4. **"A cruise ship is a hotel" was the textbook view.** Talluri & van Ryzin treated cruise ships essentially
   as hotels; Biehn and later work argue they are not (as summarized by the 2011 cruise forecasting paper)
   [S37][S39][S78]. Our transfer claim ("cruise is the closest analogue") rests on the multi-constraint,
   long-lead, group nature of the product, not on cruise RM being a distinct science.
5. **Pass sales may say little about our segment.** Vail's numbers are Epic, not Ikon; Winter Park is Ikon.
   Alterra discloses nothing comparable, and Ikon pricing strategy can diverge (2026/27: $1,329 → $1,349
   with renewal or $1,399 new, about +5% only for new buyers, and a no-scan refund limited to the separate
   "Refundable" products [S70][S71], while Epic units fell 12%). The cross-company inference is a proxy.
6. **Sample size defeats most of this.** Every quantitative method here needs observations we do not have.
   The power table in §10.2 is the honest limit: within one season, our own bookings cannot tell an
   elasticity of −0.65 from −1.70.

## 13. Ranked recommendations

Impact is in owner-net terms vs `current_practice`; confidence is mine. Every measurement uses the
calibration-v2 simulator with 25 held-out paired seeds (OVERHAUL Phase 3.4) before any live use, and then
shadow comparisons only (no Guesty writes).

| Rank | Recommendation | Module | Expected impact | Confidence | Effort | Data needed | Measurement plan |
|---|---|---|---|---|---|---|---|
| 1 | **Booking-curve band control** (cruise/SFpark): additive pace gap `B − T` in percentage points; dead band sized to the binomial noise of the 3-home window; raise only above the band; cut only below it and only inside lead ℓ*; separate curves for holiday weeks; hold price inside the band | `src/pricing/pace.py` (`pace_multiplier`, `PaceReading`) | Low–Medium: lower price volatility and a robust pace response. The −6.6% simulated peak gap is a level (anchor) gap from the older 5-seed `pace_learned_owner_net` screen; band control does not obviously raise the peak level and may hold price flat where today's multiplier would lift it. Claim no part of that gap without a paired run on `pace_v3_anchor_repair` | Medium | S–M | Existing pacing snapshots; reference curve | Paired 25-seed owner net vs `pace_v3_anchor_repair` and `current_practice`; daily price volatility (count of guest-visible changes per night). The v2 simulator has no reference-price, volatility or fairness response, so it cannot measure the trust benefit. Field proxy: guest-visible price changes per booked night against inquiry-to-book conversion, in aggregate |
| 2 | **Comp-fill price-response estimator** (Rue La La / secondary market): treat a comp night going available→unavailable between scrapes as a sale at ≤ last ask; estimate a pooled price response by capacity tier and lead; feed it as the hierarchical prior `μ_s` | `src/scrape` (transition capture and owner-block filtering), `src/comps`, `src/elasticity` | Medium if identified; enough variance (§10.2: ~42k listing-nights/season vs 225 own) but comp prices are endogenous, so a control function or instrument is required first | **Low** until an identification strategy exists; also depends on the scraper (67% row failure today) and on separating sales from owner blocks (Huang's blocked-night rule) | L | Daily sweeps with `scrape_status`; stay-length and fee-inclusive totals | First a data-quality gate: share of transitions confirmed by a later "booked" calendar state; then held-out log-loss of comp booking prediction; then simulator owner net with the estimated vs prior β |
| 3 | **Ski-industry signal pack** at `experimental`: Winter Park dated lift-ticket price premium (daily), Inntopia monthly pace, Vail pass units/segment notes and season-to-date metrics, Ikon deadline calendar | `src/signals/collectors` (new dated lift-ticket collector, subject to ToS; new `inntopia`, `vail_filings`), `config/policies/events.yaml`, `signals.yaml` | Low–Medium; largest for far-out nights where comps are thin. Weight pass signals by segment (Falk & Scaglione: domestic +31%, foreign 0) | Medium-low | S per release collector; M for the dated lift-ticket collector | Public pages; release timestamps | Shadow IC and hit rate against pace residuals (night level for lift tickets; month level for Inntopia); season-level backtest on lodging-tax receipts for pass sales (sign only) |
| 4 | **Night-and-stay bid prices** (car rental/hotel multi-day displacement): `bid(d)` = expected owner net if the night stays open; accept/relax min-stay when stay price ≥ Σ bids + orphan loss; replace M4's constant 0.5 × nightly orphan penalty | `src/min_stay`, `src/compose`, `src/leakage` | Medium off-peak and around holiday edges | Medium | M | `src/bookprob` probabilities; gap inventory | Simulator owner net and orphan-night count; turnover count (cost) per season |
| 5 | **Owner-net audit and partial control** (Huang; Filippas): confirm no code path optimizes gross RevPAN; keep owner-confirmed seasonal levels with the engine setting shape inside caps | `src/compose`, `src/eval`, `docs/rules/AUTONOMY.md` | Guards against a known failure class. The −38% default-engine result is attributed by OVERHAUL to hard peak caps and a low ceiling/reference, not to a gross objective, and Huang's cost mechanism transfers weakly (§2.2) | High (as an audit) | S | — | Grep/test that every objective uses `owner_terms`; report owner net per home |
| 6 | **Explicit, bounded exploration** replacing M1's implicit Thompson jitter (about 3–4% of price per SD under the candidate; §10.2): controlled-variance (taboo interval) offsets around the incumbent rate on off-peak nights only, logged with unclamped and shipped prices; RD-style logging at every guardrail threshold | `src/pricing/__init__.py` (`thompson_beta`), `src/explain`, `src/eval` | Low in year 1; enables learning in years 2+ | Medium | M | Pacing snapshots; recommendation logs | Simulator: regret vs a known-β oracle across seeds, on a misspecified world; live: share of off-peak nights with recorded variation, owner-net cost of exploration (expected, from the model). Design: crossover by check-in week (Amazon, S83) |
| 7 | **All-in comparison everywhere** (FTC rule; Blake et al.): comps and our homes compared on fee-inclusive totals for the same LOS and party; LOS/party-specific `all_in_beta` for direct quotes | `src/scrape` (price-basis tagging, OVERHAUL 2.10), `src/comps`, `src/pricing/pace.py` | Medium: removes a ~20% basis error at a $2,000 rate | Medium-high | S–M | Fee fields in scrapes | Share of comp quotes tagged with a price basis; anchor shift after correction; simulator owner net |
| 8 | **Gallego–van Ryzin decay shape** for the option value of an open night, calibrated from β and the booking curve; simulator-first | `src/pricing`, `proving_ground_exam/` | Medium in shoulder and close-in | Medium-low | M | Booking curve; β | Simulator owner net and close-in fill vs current M3 |
| 9 | **Direct-channel commitment products**: price-drop credit before a final-payment date; refundable vs non-refundable spread; pre-sold packages (lift tickets, rentals) | `src/pms` policy, `src/bookprob` cancel hazard, operator website | Low–Medium; mostly early group commitment | Low-medium | M | Direct-booking flow | Aggregate share of holiday-week bookings made >60 days out, before/after; guarantee payouts |
| 10 | **Fairness-aware presentation**: list the high price, show savings on soft dates; publish holiday-week prices early and change only on band breach; test a YoY cap for repeat-guest weeks | `src/explain/present.py`, `src/guardrails` | Low direct | Medium | S | Aggregate repeat-guest counts | Review sentiment mentioning price; repeat-guest rebook rate |
| 11 | **Simulator behaviours** borrowed from ski and cruise: date-flexible shoppers with a cross-price term (Malasevska), early-commitment shoppers who value a guarantee, and diminishing returns to the holiday premium ratio (Arcturus) | `proving_ground_exam/` | Indirect: stops the simulator flattering daily repricing | Medium | M | Literature priors, swept | Sensitivity sweeps; the engine's ranking must be stable across the sweep |

## 14. Open questions for the operator

1. **Season-level signals and the ladder.** Pass sales and Inntopia data will never reach n ≥ 40 at night
   level. Should `signals.yaml` get a season- or month-level promotion rule (for example, sign-correct in at
   least 7 of 9 back-test seasons), or should these stay shadow-only?
2. **Direct-channel policy.** Would the owners accept a price-drop credit (as a fee waiver) on direct bookings
   before a final-payment date? Is there a final-payment date today?
3. **Refundable spread.** Do the homes offer a non-refundable discount on Airbnb/VRBO, and at what spread?
4. **Lift-ticket scraping.** May we scrape Winter Park's dated lift-ticket prices daily (terms of use), or
   should we record only the published window price?
5. **Inntopia.** Is the monthly DestiMetrics briefing enough (public), or is a paid Inntopia subscription for
   Grand County worth asking about?
6. **Exploration budget.** What owner-net cost per season, if any, is acceptable for deliberate off-peak price
   variation that buys learning? (Recommendation 6 needs a number.)
7. **Pass holders.** Can the direct booking flow ask (opt-in, aggregate only) whether the party holds
   Ikon/Epic passes?
8. **Holiday-week posting.** Would the operator publish holiday-week prices early and commit to changing them
   only on a booking-curve breach?

## Appendix A. Source register

Class codes: 1 academic, 2 textbook, 3 vendor/patent, 4 industry body, 5 company filing/call, 6 government,
7 practitioner/trade press. "Read" says what I actually read: **F** full text or primary page; **A** abstract
or bibliographic record only; **S** secondary summary (search-engine summary or press). All accessed
2026-10-16.

| ID | Source | Class | Read |
|---|---|---|---|
| S01 | Vail Resorts, Q1 FY2026 results and season pass sales, 2025-12-10. https://www.prnewswire.com/news-releases/vail-resorts-reports-first-quarter-fiscal-2026-and-season-pass-sales-results-reaffirms-guidance-and-announces-2026-capital-plan-302638473.html | 5 | F |
| S02 | Vail Resorts, Q4 and FY2026 results, FY2027 outlook, 2026-09-28 (PR Newswire via TradingView). https://www.tradingview.com/news/prnewswire:7283bb28fec90:0-vail-resorts-reports-fourth-quarter-and-full-year-fiscal-2026-results-and-provides-fiscal-2027-outlook/ ; also SEC 8-K index https://www.sec.gov/Archives/edgar/data/0000812011/000081201126000048/a20260731pressrelease.htm | 5 | F |
| S03 | Vail Resorts Form 10-K FY2025. https://www.sec.gov/Archives/edgar/data/812011/000081201125000104/mtn-20250731.htm | 5 | F (first ~200k of 313k characters) |
| S04 | Vail Resorts, Q3 FY2026 results and early pass sales, 2026-06-08. https://www.prnewswire.com/news-releases/vail-resorts-reports-third-quarter-fiscal-2026-results-provides-updated-fiscal-2026-guidance-and-provides-early-season-pass-sales-results-302794373.html ; SEC copy https://www.sec.gov/Archives/edgar/data/812011/000081201126000025/a2026430pressrelease.htm | 5 | S |
| S05 | Colorado Sun, US skier visits 2025-26 (NSAA preliminary), 2026-05-05. https://coloradosun.com/2026/05/05/us-skier-visits-drop-2025-26/ | 7 | S |
| S06 | Colorado Sun, Colorado skier visits collapse, 2026-06-04. https://coloradosun.com/2026/06/04/colorado-skier-visits-collapse-2025-26/ | 7 | S |
| S07 | Colorado Sun, Ikon/Epic pass sales 2018. https://coloradosun.com/2018/10/31/ikon-pass-epic-pass-sales-2018/ ; ColoradoBiz on Rusty Gregory https://coloradobiz.com/rusty-gregorys-iconic-rise-to-the-top-of-alterra/ (STALE) | 7 | S |
| S08 | Inntopia/DestiMetrics winter 2025-26 results, reported by SAM: https://www.saminfo.com/news/sam-headline-news/summer-looking-strong-as-western-mountain-lodging-limps-into-winter-season-finale ; SnowSports News 2026-05 https://www.snowsportsnews.com/newsrepository/2026/may/inntopia-destimetrics-winter-s-woes-melt-into-summer-surge-at-western-mountain-destinations/ | 7 | S |
| S09 | SnowBrains, Vail peak lift tickets $356. https://snowbrains.com/vail-resorts-peak-lift-ticket-prices-hit-record-356-with-six-mountains-now-overs-300/ | 7 | S |
| S10 | Royal Caribbean Q2 2026 earnings call transcript (Investing.com). https://www.investing.com/news/transcripts/earnings-call-transcript-royal-caribbean-tops-q2-2026-profit-estimates-93CH-4817466 | 5 | F |
| S11 | Royal Caribbean Q2 2026 call highlights (Yahoo Finance). https://finance.yahoo.com/markets/stocks/articles/royal-caribbean-cruises-q2-earnings-200356250.html | 7 | S |
| S12 | Cruise Industry News, Carnival half booked for 2027 at record prices, 2026-09. https://cruiseindustrynews.com/cruise-news/2026/09/carnival-half-booked-for-2027-at-record-prices/ ; Nasdaq, Carnival booking curve https://www.nasdaq.com/articles/carnivals-record-booking-curve-extends-will-pricing-momentum-last ; Cruise Industry News 2024-10 https://cruiseindustrynews.com/cruise-news/2024/10/carnival-corporation-2025-already-half-sold-momentum-in-occupancy-and-price | 7 | S |
| S13 | Ikon Pass "pre-season savings" page. https://lifted.ikonpass.com/pre-season-savings/ | 3 | S |
| S14 | Royal Caribbean Blog on repricing (2025-12-02) and Best Price Guarantee (2020-05-13). https://royalcaribbeanblog.com/2025/12/02/repricing-royal-caribbean-getting-more-difficult-says-cruise-line-manager ; https://royalcaribbeanblog.com/2020/05/13/how-royal-caribbean-will-let-you-take-advantage-of-price-drop-until-48-hours-your-cruise | 7 | S |
| S15 | Levin, McGill, Nediak, "Price Guarantees in Dynamic Pricing and Revenue Management", *Operations Research* 55(1):75–97, 2007. https://ideas.repec.org/a/inm/oropre/v55y2007i1p75-97.html | 1 | A |
| S16 | PYMNTS, "Dynamic Pricing Gets Lift At Ski Resorts", 2015 https://www.pymnts.com/news/2015/dynamic-pricing-gets-lift-at-ski-resorts/ ; SAM, Evan Reece https://www.saminfo.com/archives/2020-2029/2020/item/165101-trailblazers-evan-reece (STALE) | 7 | S |
| S17 | PeakRankings, Liftopia sold to Skitude. https://www.peakrankings.com/content/liftopia-apparently-sold-to-skitude-transferring-assets-to-liquidator-to-settle-with-partners | 7 | F |
| S18 | Coloradotopia, Winter Park lift tickets https://www.coloradotopia.com/ski-resorts/winter-park/lift-tickets ; OnTheSnow https://www.onthesnow.com/colorado/winter-park-resort/lift-tickets | 7 | S |
| S19 | Scientia, Malasevska summary https://www.scientia.global/dr-iveta-malasevska-ski-economics-using-dynamic-ticket-pricing-to-increase-ski-slope-revenues/ ; Malasevska et al., "Dynamic pricing assuming demand shifting: the alpine skiing industry", *J. Travel & Tourism Marketing* 37(7):785–803, 2020, https://www.tandfonline.com/doi/full/10.1080/10548408.2020.1835787 (PAYWALL); Malasevska & Haugom, "Optimal prices for alpine ski passes", *Tourism Management* 64:291–302, 2018 https://ideas.repec.org/a/eee/touman/v64y2018icp291-302.html | 1 | A/S |
| S20 | UK CMA, Ticketmaster consumer protection case. https://www.gov.uk/cma-cases/ticketmaster-consumer-protection-case | 6 | F |
| S21 | Pollstar 2025-09-29 https://news.pollstar.com/2025/09/29/ticketmaster-makes-voluntary-changes-following-oasis-tickets-investigation-in-uk/ ; Music Business Worldwide https://www.musicbusinessworldwide.com/ticketmaster-didnt-use-dynamic-pricing-for-oasis-concerts-will-change-how-it-sells-tickets-in-uk-watchdog-says | 7 | S |
| S22 | Sweeting, "Dynamic Pricing Behavior in Perishable Goods Markets" / "Price Dynamics in Perishable Goods Markets", *JPE* 120(6):1133–1172, 2012. https://www.econ.umd.edu/sites/www.econ.umd.edu/files/pubs/SWEETING_PDECLINE_0112.pdf ; NBER w14505 | 1 | A |
| S23 | Geraghty & Johnson, "Revenue Management Saves National Car Rental", *Interfaces* 27(1):107–127, 1997. https://pubsonline.informs.org/doi/fpi/10.1287/inte.27.1.107 ; INFORMS Edelman Class of 1996 https://www.informs.org/Recognizing-Excellence/INFORMS-Prizes/Franz-Edelman-Award/Franz-Edelman-Laureates2/Franz-Edelman-Laureates-Class-of-1996 (STALE) | 1/4 | A |
| S24 | Cohen, Hahn, Hall, Levitt, Metcalfe, NBER w22627, 2016. https://www.nber.org/papers/w22627 | 1 | A |
| S25 | Castillo, "Who Benefits from Surge Pricing?", *Econometrica* 93(5):1811–1854, 2025. https://www.econometricsociety.org/publications/econometrica/2025/09/01/Who-Benefits-from-Surge-Pricing | 1 | A |
| S26 | Li & Pang, "Dynamic booking control for car rental revenue management: A decomposition approach", *EJOR* 256(3):850–867, 2017. https://ideas.repec.org/a/eee/ejores/v256y2017i3p850-867.html | 1 | A |
| S27 | Ferreira, Lee, Simchi-Levi, "Analytics for an Online Retailer", *M&SOM* 18(1):69–88, 2016. https://dspace.mit.edu/handle/1721.1/101783 | 1 | A (full text rate-limited) |
| S28 | Avis Budget Group Form 10-K FY2025. https://www.sec.gov/Archives/edgar/data/723612/000072361226000012/car-20251231.htm | 5 | F (first 100k characters) |
| S29 | Hertz Q2 2025 earnings release https://s204.q4cdn.com/384814028/files/doc_financials/2025/q2/Q2-2025-Earnings-Release-final.pdf and call summaries | 5 | S |
| S30 | Besbes & Zeevi, "Dynamic Pricing Without Knowing the Demand Function", *Operations Research* 57(6):1407–1420, 2009. https://faculty.wharton.upenn.edu/wp-content/uploads/2008/06/Dp_wo_demand_risk_ob_az_posted.pdf | 1 | A |
| S31 | Keskin & Zeevi, *Operations Research* 62(5):1142–1167, 2014. https://scholars.duke.edu/publication/1116819 | 1 | A |
| S32 | den Boer & Zwart, "Simultaneously Learning and Optimizing Using Controlled Variance Pricing", *Management Science* 60(3):770–783, 2014. https://ideas.repec.org/a/inm/ormnsc/v60y2014i3p770-783.html | 1 | A |
| S33 | den Boer, "Dynamic pricing and learning: historical origins, current research, and new directions", *Surveys in OR&MS* 20(1):1–18, 2015. https://research.utwente.nl/en/publications/dynamic-pricing-and-learning-historical-origins-current-research--2/ | 1 | A |
| S34 | Filippas, Jagabathula, Sundararajan, *Management Science* 69(12):7202–7216, 2023. https://ideas.repec.org/a/inm/ormnsc/v69y2023i12p7202-7216.html | 1 | A |
| S35 | Huang, "Pricing Frictions and Platform Remedies: The Case of Airbnb", working paper, 2021-10-03. https://www.chicagobooth.edu/-/media/Research/Kilts/docs/qme2021-paper54---Pricing-Frictions-and-Platform-Remedies-The-Case-of-Airbnb | 1 | F (extracted PDF text) |
| S36 | Maddah, Moussawi-Haidar, El-Taha, Rida, "Dynamic cruise ship revenue management", *EJOR* 207(1):445–455, 2010. https://ideas.repec.org/a/eee/ejores/v207y2010i1p445-455.html | 1 | A |
| S37 | Biehn, "A cruise ship is not a floating hotel", *JRPM* 5:135–142, 2006. https://link.springer.com/article/10.1057/palgrave.rpm.5160034 | 1 | A (STALE) |
| S38 | Ayvaz-Cavdaroglu, Gauri, Webster, *Journal of Travel Research* 58(1):104–120, 2019. https://academicrepository.khas.edu.tr/xmlui/handle/20.500.12469/659 | 1 | A |
| S39 | "Forecasting for cruise line revenue management", *JRPM* 10(4):306–324, 2011. https://researchconnect.buffalo.edu/en/publications/forecasting-for-cruise-line-revenue-management/ | 1 | A (STALE) |
| S40 | FTC, Trade Regulation Rule on Unfair or Deceptive Fees, 90 FR (2025-01-10), 16 CFR Part 464. https://www.govinfo.gov/content/pkg/FR-2025-01-10/html/2024-30293.htm ; effective-date note https://www.hotel-online.com/news/ftc-junk-fee-rule-is-effective-may-12-2025 | 6 | S |
| S41 | Blake, Moshary, Sweeney, Tadelis, "Price Salience and Product Choice", *Marketing Science* 40(4):619–636, 2021. https://faculty.haas.berkeley.edu/stadelis/AIP.pdf | 1 | A |
| S42 | Pierce & Shoup, "Pricing Parking by Demand: Assessing Price Adjustments in the SFpark Program" (UCLA) https://www.its.ucla.edu/publication/pricing-parking-by-demand-sfpark ; SFMTA evaluation release https://www.sfmta.com/press-releases/sfpark-evaluation-shows-parking-easier-cheaper-pilot-areas | 1/6 | S (STALE) |
| S43 | CIO, Giants dynamic pricing https://www.cio.com/article/282100/business-intelligence-for-san-francisco-giants-dynamic-pricing-software-hits-a-home-run.html ; TicketNews, Digonex vs Qcue (2009) https://www.ticketnews.com/2009/11/dynamic-pricing-showdown-digonex-launches-competitive-product-to-qcue/ | 7 | S (STALE) |
| S44 | Shapiro & Drayer, *Sport Management Review* 17(2):145–159, 2014. https://ideas.repec.org/a/eee/spomar/v17y2014i2p145-159.html | 1 | A |
| S45 | NPR/WBHM, FTC sues Live Nation and Ticketmaster, 2025-09-18. https://wbhm.org/npr-story/ftc-sues-live-nation-and-ticketmaster-alleging-illegal-resale-tactics | 7 | S |
| S46 | Travelmole, WDW date-based pricing https://travelmole.com/news/walt-disney-world-introduces-date-based-pricing ; Boston.com 2016 https://www.boston.com/news/national-news/2016/02/27/disney-introduces-surge-pricing-at-theme-parks (STALE) | 7 | S |
| S47 | Six Flags Q2 2025 earnings exhibit 99.1 https://www.sec.gov/Archives/edgar/data/1999001/000199900125000152/sixflags-exh991xq22025.htm ; 2025-09-12 update https://www.sec.gov/Archives/edgar/data/1999001/000199900125000164/sixflags-exh991x09122025.htm | 5 | S |
| S48 | Caro & Gallien, "Clearance Pricing Optimization for a Fast-Fashion Retailer", *Operations Research* 60(6):1404–1422, 2012. https://dspace.mit.edu/handle/1721.1/52779 | 1 | A (STALE) |
| S49 | Kimes & Schruben, "Golf course revenue management: a study of tee time intervals", *JRPM* 2002 https://iaorifors.com/paper/50963 ; Kimes & Wirtz (JRPM 2003) as summarized in search results (STALE) | 1 | A/S |
| S50 | Kimes, Cornell restaurant RM / duration control (Cornell eCommons) https://ecommons.cornell.edu/entities/publication/779ca191-03a2-4abe-8e4b-2de7fdd4f7ff | 4 | S (STALE) |
| S51 | Faruqui et al., Arcturus 2.0 (CPUC rate forum 2017) https://webproda.cpuc.ca.gov/-/media/cpuc-website/divisions/energy-division/documents/electric-rates/2017-electric-rate-forum/2017-arcturus-2-0-10122017.pdf ; Brattle Arcturus 3.0 preview https://www.brattle.com/wp-content/uploads/2023/02/Do-Customers-Respond-to-Time-Varying-Rates-A-Preview-of-Arcturus-3.0.pdf | 3 | S |
| S52 | Maersk, Spot fees guide https://www.maersk.com/news/articles/2022/04/28/maersk-spot-a-guide-to-spot-fees ; Spot FAQs https://www.maersk.com/news/articles/2024/03/05/maersk-spot-faqs | 3 | S |
| S53 | Ye et al., "Customized Regression Model for Airbnb Dynamic Pricing", KDD 2018, pp. 932–940 (DOI 10.1145/3219819.3219830); The Morning Paper summary https://blog.acolyer.org/2018//03/customized-regression-model-for-airbnb-dynamic-pricing/ | 1/7 | S (via detailed summary) |
| S54 | Vacasa Form 10-K FY2024 https://www.sec.gov/Archives/edgar/data/1874944/000187494425000003/vcsa-20241231.htm ; FY2022 https://www.sec.gov/Archives/edgar/data/1874944/000187494423000018/vcsa-20221231.htm | 5 | S |
| S55 | Casago completes Vacasa acquisition (Business Wire 2025-05-01) https://secure.businesswire.com/news/home/20250501075877/en/Casago-Completes-Acquisition-of-Vacasa ; ShortTermRentalz on market sales https://shorttermrentalz.com/news/casago-completes-sales-of-former-vacasa-markets/ | 7 | S |
| S56 | Bloomberg, Sonder to file bankruptcy, 2025-11-10 https://www.bloomberg.com/news/articles/2025-11-10/sonder-to-file-bankruptcy-and-liquidate-after-marriott-cuts-ties | 7 | S |
| S57 | Expedia Group job posting, ML Scientist III – Vrbo Pricing https://careers.expediagroup.com/job/machine-learning-scientist-iii-vrbo-pricing/austin-tx/R-105582/ | 7 | S |
| S58 | arXiv 2310.17165 (2023), citing Farronato & Fradkin elasticity estimates https://arxiv.org/html/2310.17165 | 1 | S |
| S59 | Gallego & van Ryzin, "Optimal Dynamic Pricing of Inventories with Stochastic Demand over Finite Horizons", *Management Science* 40(8):999–1020, 1994. https://business.columbia.edu/sites/default/files-efs/pubfiles/3943/vanryzin_optimal_dynamic_pricing.pdf | 1 | F (eqs. 9–10 and Theorem 1 read) |
| S60 | Ferreira, Simchi-Levi, Wang, "Online Network Revenue Management Using Thompson Sampling", *Operations Research* 66(6):1586–1602, 2018. https://dspace.mit.edu/handle/1721.1/125757 | 1 | A |
| S61 | Bastani, Simchi-Levi, Zhu, "Meta Dynamic Pricing", *Management Science* 68(3):1865–1881, 2022. https://arxiv.org/abs/1902.10918v3 | 1 | A |
| S62 | Gelman, Carlin, Stern, Dunson, Vehtari, Rubin, *Bayesian Data Analysis*, 3rd ed., CRC Press, 2013, ch. 5 (hierarchical models) | 2 | Prior knowledge; not re-read |
| S63 | Mazumdar, Raj, Sinha, "Reference Price Research: Review and Propositions", *Journal of Marketing* 69(4):84–102, 2005. https://www.jstor.org/stable/30166553 | 1 | A |
| S64 | Kalyanaram & Winer, "Empirical Generalizations from Reference Price Research", *Marketing Science* 14(3, suppl.):G161–G169, 1995. https://ideas.repec.org/a/inm/ormksc/v14y1995i3_supplementpg161-g169.html | 1 | A |
| S65 | Kahneman, Knetsch, Thaler, "Fairness as a Constraint on Profit Seeking", *AER* 76(4):728–741, 1986. https://ideas.repec.org/a/aea/aecrev/v76y1986i4p728-41.html ; 82% figure as reported in arXiv 2301.07543 | 1 | A/S |
| S66 | Alnes & Haugom, *Journal of Retailing and Consumer Services* 81, 2024 https://ideas.repec.org/a/eee/joreco/v81y2024ics0969698924002480.html ; personality and fairness study of 1,627 skiers (Aalto repository) https://aaltodoc.aalto.fi/items/0779fa7b-c5c9-4d00-92a2-26614c40baae | 1 | S |
| S67 | Anderson & Simester, "Effects of $9 Price Endings on Retail Sales", *QME* 1(1):93–110, 2003. https://ideas.repec.org/a/kap/qmktec/v1y2003i1p93-110.html | 1 | A (STALE) |
| S68 | Bitran & Mondschein, "An Application of Yield Management to the Hotel Industry Considering Multiple Day Stays", *Operations Research* 43(3):427–443, 1995. https://ideas.repec.org/a/inm/oropre/v43y1995i3p427-443.html | 1 | A (STALE) |
| S69 | Vail Resorts season-to-date metrics to 2026-01-04 (release 2026-01-15), via Snow Industry News https://www.snowindustrynews.com/articles/vail-resorts-reports-certain-ski-season-metrics-for-the-season-to-date-period-ended-january-4-2026-visits-down-2 | 5/7 | S |
| S70 | SKI Magazine, Ikon 2026-27 details and refund policy https://headless.skimag.com/news/ikon-pass-2026-2027-details | 7 | F |
| S71 | Steamboat Pilot, Ikon 2026-27 prices about 5% higher https://www.steamboatpilot.com/news/ikon-pass-2026-27-on-sale-higher-price/ ; Salt Lake Tribune 2026-03-06 https://www.sltrib.com/news/environment/2026/03/06/ikon-pass-prices-announced-2026-27/ | 7 | S |
| S72 | Inntopia, "Summer Finishes Modestly; Winter Bookings Are Flat As Daily Rates Edge Up" (data to 2025-10-31). https://corp.inntopia.com/summer-finishes-modestly-winter-bookings-are-flat-as-daily-rates-edge-up/ | 3 | F |
| S73 | Smart-Pricer, Zermatt Bergbahnen case study https://www.smart-pricer.com/?p=2807 | 3 | F (vendor claim) |
| S74 | Pricefx, adjustable pricing in the ski industry (Andermatt pilot) https://www.pricefx.com/learning-center/adjustable-pricing-boosted-ski-industry | 3 | S |
| S75 | Baker McKenzie, Ninth Circuit on algorithmic pricing (Gibson v. Cendyn) https://www.bakermckenzie.com/en/insight/publications/alerts/2025/08/united-states-ninth-circuit-on-algorithmic-pricing | 7 | S |
| S76 | "Dynamic pricing and revenues of Airbnb listings: Estimating heterogeneous causal effects", *Int. J. Hospitality Management*, 2021. https://www.sciencedirect.com/science/article/abs/pii/S0278431921000578 | 1 | S (HTTP 403; authors UNVERIFIED) |
| S77 | "Dynamic pricing in Airbnb: Individual versus professional hosts", *Journal of Business Research*, 2022. https://www.sciencedirect.com/science/article/abs/pii/S0148296321009267 | 1 | S |
| S78 | Talluri & van Ryzin, *The Theory and Practice of Revenue Management*, Springer/Kluwer, 2004 (cited via S39's characterization) | 2 | Not re-read |
| S79 | Wheelhouse, "Wheelhouse vs. Beyond Pricing vs. PriceLabs" (vendor-authored) https://usewheelhouse.com/blog/?p=1860 | 3 | S |
| S80 | Falk, M. & Scaglione, M. (2021) "Effects of price model copycats in the ski industry", *Tourism Analysis* 26:71–75 (DiD, 59 Swiss destinations; domestic overnights +31%, foreign 0). https://openarchive.usn.no/usn-xmlui/handle/11250/2740344 (archive retired 2026; record also at https://hesso.tind.io/record/7511) | 1 | A (added 2026-10-19 from the R3 review; abstract confirmed by search) |
| S81 | Saas-Fee pass-price study, *Tourism Review* (2018), doi 10.1108/TR-08-2017-0133 (about +50% Swiss residents, +17% total stays). https://arodes.hes-so.ch/record/7511/files/Published%20version.pdf | 1 | S (via R3 review) |
| S82 | Millard-Ball, A., Weinberger, R. & Hampshire, R. (2013) "Is the curb 80% full or 20% empty? Assessing the impacts of San Francisco's parking pricing experiment", *JAPA* 79(4):330–336; *Transportation Research A* (2014). https://ideas.repec.org/a/taf/rjpaxx/v79y2013i4p330-336.html | 1 | S (via R3 review) |
| S83 | Cooprider, J. & Nassiri, S. (2023) "Science of price experimentation at Amazon", *Business Economics*. https://amazon.science/publications/science-of-price-experimentation-at-amazon | 1 | A (read 2026-10-19) |
| S84 | DOJ–RealPage proposed final judgment, 2025-11-24, as summarized by Fenwick and CPR News. https://www.fenwick.com/insights/publications/dojs-realpage-settlement-a-blueprint-for-safer-algorithmic-pricing ; https://www.cpr.org/2025/11/25/rent-algorithm-limits-settlement/ | 6/7 | S (via R3 review) |
| S85 | California AB 325 (2025), common pricing algorithms, as summarized by Pillsbury. https://pillsburylaw.com/en/news-and-insights/ab-325-shared-pricing-algorithms-liability-california.html | 6/7 | S (via R3 review) |
| S86 | Colorado HB25-1090 (total-price rule, effective 2026-01-01), Denver7. https://www.denver7.com/news/politics/new-colorado-state-laws-going-into-effect-thursday-for-the-start-of-2026 | 7 | S (via R3 review) |
| S87 | Denver International Airport monthly passenger traffic reports. https://www.flydenver.com/ | 6 | S (via R3 review) |

Distinct sources counted: **87** (S01–S87; S80–S87 added in the 2026-10-19 close-out from the review's own searches, marked "via R3 review" where the author did not reopen them). Grouped URLs inside one
ID count once.

By class (a source carrying two classes is counted once, under the first listed): 1 academic **36**
(S15, S19, S22–S27, S30–S39, S41, S42, S44, S48, S49, S53, S58–S61, S63–S68, S76, S77); 2 textbook **2**
(S62, S78); 3 vendor **7** (S13, S51, S52, S72, S73, S74, S79); 4 industry body **1** (S50; S23 also carries
the INFORMS Edelman listing); 5 filings/calls **10** (S01–S04, S10, S28, S29, S47, S54, S69); 6 government
**2** (S20, S40); 7 trade press/practitioner **21** (S05–S09, S11, S12, S14, S16–S18, S21, S43, S45, S46,
S55–S57, S70, S71, S75). Total 79.

## Appendix B. Search log

WebSearch queries run (64 attempted, 63 returned results; the 64th hit the session limit). "→" gives what each
yielded. Mode was "extended" where marked [x].

| # | Query (abridged) | Yield |
|---|---|---|
| 1 [x] | Vail season-to-date pass sales Sept 2026 FY2026 | Q4 FY2026 release; units −12%, $ −6% (S02) |
| 2 [x] | Vail 10-K pass products % lift revenue advance commitment | 10-K, advance-commitment figures (S01, S03) |
| 3 [x] | Malasevska dynamic pricing ski weather Norway | Paper list (S19) |
| 4 [x] | Alterra Ikon 2026-27 price; Winter Park window price | Ikon prices; no WP window price (S71) |
| 5 | Alterra Ikon sales up percent pass holders | Only 2018 statements; Alterra does not disclose (S07) |
| 6 | Liftopia history acquired shut down | Liftopia/Skitude (S16, S17) |
| 7 | Vail window price >$300 strategy | $356 peak (S09) |
| 8 [x] | Inntopia DestiMetrics 2025-26 results | Winter −7% occupancy (S08) |
| 9 [x] | Biehn cruise ship not floating hotel | S37, S39, S38 leads |
| 10 | Ayvaz-Cavdaroglu cruise RM abstract | 8–20% model gain (S38) |
| 11 [x] | Royal Caribbean 2026 booked position load factor close-in | Q2 2026 transcript (S10, S11) |
| 12 | Cruise price drop policy reprice before final payment | S14 |
| 13 | Levin McGill Nediak price guarantees | S15 |
| 14 | Carnival 10-K booking curve | Trade press on Carnival (S12) |
| 15 | Geraghty Johnson National Car Rental | S23 |
| 16 | Avis 10-K revenue management pricing | S28 |
| 17 | Hertz 2025 revenue management RPD | S29 |
| 18 [x] | Megapass effect on lodging overnight stays Colorado | **No study found** |
| 19 | Winter Park lift ticket price 2025-26 dynamic | S18 |
| 20 | CMA Ticketmaster Oasis undertakings | **Corrected my summary**: tiered, not dynamic (S20, S21) |
| 21 | Sweeting perishable goods secondary market | S22 |
| 22 | Shapiro Drayer Giants Qcue | S44 |
| 23 | Qcue Giants revenue Digonex | S43 |
| 24 | FTC lawsuit Ticketmaster Sept 2025 | S45 |
| 25 | Cohen et al. Uber consumer surplus RD | S24 |
| 26 | Castillo Who Benefits from Surge Pricing | S25 |
| 27 | Ferreira Lee Simchi-Levi Rue La La | S27 (9.7%, CI) |
| 28 | Caro Gallien Zara clearance | S48 |
| 29 | den Boer survey 2015 | S33 |
| 30 | Ferreira Simchi-Levi Wang Thompson sampling | S60 |
| 31 | Keskin Zeevi semi-myopic policies | S31 (√T vs log T) |
| 32 | Ye et al. Airbnb KDD 2018 | S53 |
| 33 [x] | Airbnb pricing elasticity arXiv 2023–2025 | S35, S58 |
| 34 | Filippas et al. centralized pricing | S34 |
| 35 | FTC fees rule short-term lodging May 2025 | S40 |
| 36 | Blake et al. price salience StubHub | S41 |
| 37 | Disney date-based pricing rationale | S46 |
| 38 | SFpark evaluation Pierce Shoup | S42 |
| 39 | Ikon Winter Park lodging discount | S13 (up to 50% off 4+ nights) |
| 40 | NSAA 2025-26 skier visits | S05, S06 |
| 41 | Maddah et al. dynamic cruise RM | S36 |
| 42 | Forecasting for cruise line RM abstract | S39 (multiplicative worse) |
| 43 | Kimes golf tee time RM | S49 |
| 44 | Faruqui critical peak pricing Arcturus | S51 |
| 45 | Anderson Simester $9 endings | S67 |
| 46 | Kahneman Knetsch Thaler fairness | S65 |
| 47 | Mazumdar Raj Sinha reference price | S63 (and S64 lead) |
| 48 | Vacasa 10-K dynamic pricing | S54 |
| 49 | Vacasa Casago; Sonder bankruptcy | S55, S56 |
| 50 | Expedia/Vrbo pricing tech blog | Only job posting (S57) |
| 51 | Bastani meta dynamic pricing | S61 |
| 52 | Gallego van Ryzin 1994; Besbes Zeevi 2009 | S59, S30 |
| 53 | Gibson v. Cendyn; RealPage | S75 (RealPage not returned) |
| 54 | Alnes et al. 2026 fairness skiers | 2026 paper not found; S66 instead |
| 55 | Kimes restaurant RevPASH | S50 |
| 56 | Maersk Spot loading guarantee no-show | S52 |
| 57 | Six Flags 2025 pricing attendance | S47 (adversarial) |
| 58 | PriceLabs/Wheelhouse/Beyond ski snow data | No ski-specific inputs found; S73, S74, S79 |
| 59 | Bitran Mondschein multiple day stays | S68 |
| 60 | den Boer Zwart controlled variance pricing | S32 |
| 61 | Vail season-to-date metrics January 2026 | S69 |
| 62 | Ikon 2026-27 deadlines, refund | S70, S71 |
| 63 [x] | Airbnb hosts adopting dynamic pricing tool effect | S76, S77 (adversarial) |
| 64 | Ibiza IJHM paper authors | **Failed: session limit** |

Passes: broad (1–8, 15–19), specific named papers/people (9–17, 21–36, 41–52, 59–62), adversarial (5, 18, 20,
24, 53, 54, 57, 58, 63). Additional WebFetch reads of primary pages: S01, S02, S03 (two chunks), S10, S17,
S19, S20, S28, S35 (PDF extracted locally), S53, S59 (PDF extracted locally), S64, S70, S72, S73; several
fetches were blocked (Tandfonline, Sage, ResearchGate, ScienceDirect: HTTP 403; Harvard DASH: HTTP 429).

## Appendix C. Self-audit against `00_DEPTH_STANDARD.md`

| MUST | Status | Evidence |
|---|---|---|
| Cite every non-obvious claim inline with URL/reference and access date | PASS | Inline [Sxx] tags; Appendix A gives URLs; one access date (2026-10-16) stated at the top. My own calculations are labelled as such (§10.2, §10.5) |
| ≥ 40 distinct sources | PASS | 79 distinct sources (Appendix A) |
| ≥ 4 source classes | PASS | All 7 classes: academic 36, textbook 2, vendor 7, industry body 1, filings 10, government 2, trade 21 |
| Read primary sources; say when paywalled | PARTIAL PASS | Primary filings and several papers read in full (S01–S03, S10, S20, S35, S59, S72); many academic papers read at abstract level only and marked **A**/**PAYWALL** in Appendix A. Not every primary source could be opened (403/429) |
| Mark UNVERIFIED and STALE | PASS | Marked inline (Liftopia dates, rideshare RD mechanism, Rue La La model detail, Ikon 25% figure, Carnival wording, S76 authors; STALE on pre-2023-10 data) |
| Never fabricate | PASS (to my knowledge) | The one claim I made before checking (Oasis "dynamic pricing") was corrected visibly in §0 after reading the CMA page. Model details recalled from prior reading are flagged as not re-verified |
| Search in broad, specific, adversarial passes | PASS | Appendix B; 63 successful searches, adversarial items listed |
| Mechanisms with math/algorithm (objective, inputs, estimation, decision rule) | PASS | Band control (§3.3), bid-price stays (§2.2), Gallego–van Ryzin (§10.1), power arithmetic and CVP (§10.2), hierarchical pooling (§10.3), reference-price demand (§10.4), Malasevska cross-price (§1.3), Airbnb loss (§9) |
| Quantified impact with who measured and conflicts | PASS | Rue La La 9.7% (authors with retailer), Zara 6%, National $56 M (company staff), Giants $7 M (vendor-friendly), Smart-Pricer (vendor), Ayvaz-Cavdaroglu 8–20% (model counterfactual), SFpark (independent), Castillo (Uber data), Cohen et al. (Uber co-authors) |
| Map every finding to engine module and owner-net measurement | PARTIAL (revised 2026-10-19) | §11.1 table, §11.2 tests, §13 measurement plans with modules. The review found Recs 1, 5 and 10 mapped to the wrong gap or cause; those are corrected, and Recs 1 and 10 now say the simulator cannot measure trust |
| Honest transferability (small inventory, thin data, LOS, groups, fees) | PARTIAL (revised 2026-10-19) | §10.2 power table, §11.1 "holds?" column, §12 adversarial pass, rows 21–23 marked "do not copy". The comp-fill identification claim was overclaimed (price endogeneity) and is now Low pending a strategy. Read levels (reviewer's count from Appendix A): about 22 full, 30 abstract, 27 secondary |
| "What generic STR pricers miss" note | PASS | §1.5, §9.1, §11.3 (and where specialization does not help) |
| Ranked recommendations with impact, confidence, effort, data, measurement | PASS | §13 |
| Open questions for the operator | PASS | §14 |
| Self-audit table | PASS | This table |
| Running search log appendix | PASS | Appendix B |
| Prefer 2020–2026 plus classics | PASS | Filings and calls 2025–2026; classics (Gallego–van Ryzin 1994, KKT 1986, Bitran–Mondschein 1995) marked STALE where data-based |
| Transfer table in R1 format | PASS | §11.1 uses method / core assumption / holds? / adaptation / expected value / effort |
| Ski-industry signals with source, cadence, lead, test | PASS | §11.2 |
| Industries covered (ski★, car rental★, cruise★, ticketing★, theme parks, rideshare, retail, brief five, VR managers) | PASS | §§1–9 |
| Cross-cutting techniques (bandits at ~100 bookings, pooling, reference/fairness, presentation, demand shaping) | PASS | §10 |
| Gaps I could not close | — | No Colorado study on mega-pass effects on lodging (Swiss evidence added, S80–S81); no DEN rental-price demand study; no Alterra pass numbers; Ibiza paper authors unverified; full texts of several key papers (Keskin–Zeevi CVP schedule, Rue La La model) not re-read. **Still thin against the prompt (review fix 14, not done):** Ticketmaster Platinum, NBA/NFL dynamic pricing, Disney park reservations, Evolve, Vail investor-day materials, and a window-price vs pass-price time series |

## Appendix D. Response to review

Review: `reviews/R3_review.md`, ACCEPT WITH FIXES (18 items).

**Audit note (2026-10-19).** The first version of this appendix (2026-10-17) recorded resolutions
for most fixes, but the dossier body had not been edited: the −6.6% and −38% attributions, the
"~1%" exploration premise, "40% or more", the "independent" SFpark claim, the Blake UNVERIFIED flag,
"RealPage settlement not checked" and the "collector field exists" claim were all still in the text,
and S1 and R6 read that text. The close-out audit applied the fixes to the body. It used the
reviewer's evidence, re-derived the exploration arithmetic from the code, and re-checked Falk &
Scaglione (abstract, by search) and Cooprider & Nassiri (abstract page). Rows marked "via review"
rely on the reviewer's reading of a source that was not reopened.

| # | Status | What changed or why not |
|---|---|---|
| 1 | applied (2026-10-19) | §10.2 rewritten: about 3–4% of price per SD under `pace_v3_anchor_repair` with all-in scaling (audit: 3.5% peak, 3.0% other at $2,000; 4.0% / 3.5% at $1,200), with exploration off on blackout nights. The case for explicit exploration is now argued from the power table. §13 #6 updated. |
| 2 | applied (2026-10-19) | §10.2 conclusion states price endogeneity, Huang's control function and blocked-night rule, practitioner snapshot differencing, and three candidate strategies (control function, instrument, rule discontinuities). The power table is captioned "variance only". §0 #2, §13 #2 and §11.1 rows 14–15 drop to Low until a strategy exists. |
| 3 | applied (2026-10-19) | §0 #1, §11.1 row 1 and §13 #1 no longer claim the −6.6% gap. They claim volatility and robustness benefits and require a paired run on `pace_v3_anchor_repair`. |
| 4 | applied (2026-10-19) | §0 #5, §11.1 row 10 and §13 #5 attribute the −38% to peak caps and a low ceiling/reference (OVERHAUL). §2.2 item 3 states Huang's cost is time per night and that our owner-side margin is about $7/night. |
| 5 | applied (2026-10-19) | §1.4 adds Falk & Scaglione (S80) and the Saas-Fee study (S81), replaces "found none" with "none for Colorado", and uses the domestic/foreign split for the drive-in vs destination inference. |
| 6 | applied (2026-10-19) | §3.3 and §8 mark Shoup as practitioner evidence and add Millard-Ball et al. (S82). The 62% figure was confirmed by search on 2026-10-19: it is from the later UCLA two-year brief, not the 2013 JAPA paper, so it is now attributed there rather than marked UNVERIFIED. |
| 7 | applied (2026-10-19) | §11.2 and §12.5: the refund belongs to the separate "Refundable" products; price $1,329 → $1,349 renewal / $1,399 new. |
| 8 | applied (2026-10-19) | §11.2 says the existing field is a single window price and a dated collector is new work under ToS limits. §13 #3 effort is now M for that collector. |
| 9 | applied (2026-10-19) | §5 and §11.1 row 23: −4% is admissions yield, in-park product spending rose, and the 298k visits are not attributed to promotions. |
| 10 | applied (2026-10-19) | §1.2 and §4.1: about 13%, 18% and 40% at successive relistings. |
| 11 | applied (2026-10-19) | §4.1: the UNVERIFIED flag on Blake's 21% is removed (Table 3, via review). |
| 12 | applied (2026-10-19) | §12.3 adds the RealPage proposed final judgment terms (S84) and California AB 325 (S85). §10.5 adds Colorado HB25-1090 (S86). |
| 13 | applied (2026-10-19) | §7 adds Cooprider & Nassiri (S83): product-randomized, crossover designs, trend controls. It is linked to Rec 6 and R1's field design. |
| 14 | **not done** | Ticketmaster Platinum, NBA/NFL, Disney park reservations, Evolve, Vail investor-day material and a window-vs-pass price series were not researched. They are listed as open gaps in Appendix C. None of them bears on a top-5 recommendation. |
| 15 | applied (2026-10-19) | §13 #1 says the v2 simulator cannot measure trust or volatility and names the aggregate field proxy. Rec 10's existing measurement plan is already field-based (review sentiment, repeat-guest rebook rate). Rec 17 does not exist in §13, which has 11 rows; the review's reference is taken to mean Rec 11, whose sensitivity-sweep plan is unchanged. |
| 16 | applied (2026-10-19) | §3.3 gives the dollar path 0.85 → 0.92 → 1.03 ($1,700 → $1,838 → $2,050), notes that owner blocks shrink the denominator, and labels the S39 argument an analogy. |
| 17 | applied (2026-10-19) | §2.3 puts DEN monthly passenger reports (S87) first and rental-car quotes second. |
| 18 | applied (2026-10-19) | Appendix C: "Map every finding" and "Honest transferability" are PARTIAL, with the reviewer's read-level counts (about 22 full, 30 abstract, 27 secondary). |

Also corrected in the audit: three cross-references called the comp-fill estimator "Recommendation 3";
it is Recommendation 2.
