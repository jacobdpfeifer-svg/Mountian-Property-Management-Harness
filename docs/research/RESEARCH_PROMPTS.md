# Research prompt pack — consumer layer, market simulator, novel pricing models

Date: 2026-09-29
Companion to: `docs/reports/audit_2026-09-29/AUDIT_AND_IMPROVEMENTS.md`

These are **research** prompts, not build prompts. Each one is self-contained and
can be handed to a separate agent. The deliverable of every prompt is a written
research dossier with sources, not code. Build decisions come after the dossiers
are reviewed.

## Shared context (paste this above any prompt below)

> You are researching for a private, rules-first short-term-rental (STR) pricing
> engine in `Harness for my wonderful Mother/`. It prices three luxury homes owned
> by **Mont Luxe Collection** in the **Winter Park / Fraser, Colorado** market
> (Grand County): 312 Northwoods ("Summit Haus"), 300 Northwoods ("Overlook Ridge"),
> and Cloud 9. **Guesty** is the system of record, and Airbnb, VRBO, the direct website and
> manual bookings are the channels. The engine maximizes RevPAN (`P × P(book|P)`)
> between a floor and a same-season ceiling, with guardrails, an autonomy ladder
> gated on data health, and explanations for every price. Read `README.md`,
> `docs/ARCHITECTURE.md`, `docs/LOCKED_INPUTS.md`, `docs/rules/PRICING_DOCTRINE.md`
> and `docs/resort/WINTER_PARK_KNOWLEDGE.md` before starting.
>
> The long-term goal is a **pricing method built for mountain and ski-resort
> towns**, better than generalized tools (PriceLabs, Beyond, Wheelhouse, AirDNA
> Smart Rates, Vantory). Later, the same approach would be tested in other
> under-served markets. That includes a **consumer layer**, meaning who the buyers are
> and whether they will actually buy this year, and a **fast market
> simulator** that can compress months of market behavior into minutes so the
> engine can be stress-tested and new pricing models developed.
>
> Current facts you must respect (from the 2026-09-29 audit):
> - Real data is thin: 88 Guesty reservations (48 confirmed incl. 2 owner stays;
>   40 inquiries), pacing snapshots only since 2026-08-18 with gaps (09-02, 09-04..09-19).
> - The engine's price elasticity is a **config constant per season**, never learned.
>   Its booking model was not conditioned on lead time until 2026-09-29.
> - The Proving Ground simulator (`src/proving_ground/`, `proving_ground_exam/`)
>   is a static per-night demand curve. The engine never sees a booking. It is not a
>   market simulation yet.
>
> Rules for every dossier:
> 1. Cite every factual claim with a URL and access date. Mark anything you
>    could not verify as **UNVERIFIED**. Never invent statistics, and flag stale data
>    (older than 3 years) explicitly.
> 2. Separate **individual-level personal data** (usually illegal or unethical to buy or
>    scrape, and out of scope) from **aggregated or first-party data** (in scope).
>    For every data source, state its licence and terms-of-service constraints, cost,
>    refresh cadence, historical depth and whether it has an API. Note Colorado
>    Privacy Act (CPA), CCPA and GDPR implications where guests are in scope.
> 3. For each finding, say what it would change in the engine or simulator,
>    which module it touches (`src/bookprob`, `src/ceiling`, `src/signals`,
>    `src/proving_ground`, …), and how we would **measure** whether it helped.
> 4. Do not recommend anything that writes to Guesty or changes live prices.
> 5. End with a ranked "what to do next" list and a list of open questions for the
>    operator.

---

## Prompt 1 — Who buys Winter Park? Consumer and visitor-profile market data

**Question.** What is publicly or commercially knowable about the people who
book lodging in Winter Park / Fraser / Grand County, especially luxury,
large-group homes of 5+ bedrooms? How does that differ by season (Christmas–New Year,
MLK, Presidents' Day, spring break, midweek January, summer, fall shoulder)?

**Investigate at least:**
- **Origin markets**: Front Range (Denver metro) vs drive-in (Texas, Kansas,
  Nebraska, Oklahoma) vs fly-in via DEN vs international (Mexico, UK, Australia,
  Brazil). Look for share by season and trend over 5 years.
- **Party composition**: multi-family groups, multigenerational families, ski-club
  groups, corporate retreats, weddings, bachelor/bachelorette groups. Look for typical
  party size and length of stay.
- **Booking behavior**: booking window (lead time) by segment, length of stay,
  channel preference (Airbnb vs VRBO vs direct), cancellation rates, and sensitivity to
  price vs snow conditions vs school calendars.
- **Spend and wealth**: household income bands for luxury ski travelers, share
  of pass holders (Winter Park is on the **Ikon** pass, owned by Alterra), and ancillary spend.
- **Sources to evaluate** (verify each; do not assume access):
  Inntopia **DestiMetrics** (mountain lodging occupancy, pacing and origin reports; the
  standard for ski towns), Winter Park & Fraser Chamber / Grand County lodging-tax
  reports, Colorado Tourism Office (Longwoods visitor profiles), Colorado Ski
  Country USA, NSAA (Kottke end-of-season report, demographic studies), Alterra and
  Ikon public statements, Denver International Airport traffic stats, CDOT I-70
  counts, AirDNA / Key Data / PriceLabs Market Dashboards (market-level ADR,
  occupancy, lead time and LOS), Zartico / Placer.ai / Near / Visa Destination Insights
  (visitor origin and spend, often licensed to DMOs), Airbnb and Expedia/VRBO trend
  reports, Google Trends, US Census ACS for feeder-market demographics.

**Deliverable.** A persona table for Winter Park luxury homes, with 4–8 segments.
For each segment give share by season, lead-time distribution, LOS distribution,
party size, channel mix and a willingness-to-pay indicator. Give a source and confidence
for every cell. This table becomes the calibration target for the simulator's
guest segments (Prompt 4).

---

## Prompt 2 — Mont Luxe's own guests: what first-party data exists and how to use it lawfully

**Question.** Mont Luxe's own reservation history is the most valuable consumer
data there is. What can we lawfully collect from Guesty, Airbnb, VRBO and the
direct site, and what does it reveal about who actually buys these homes?

**Context.** `src/pms/sync.py` currently keeps only `status`, `source`,
`confirmedAt`, `createdAt` and `guestsCount`, plus fare per night. Before
2026-09-29 it counted inquiries as bookings. It now stores inquiries and
cancellations as separate demand evidence. Snapshot: 88 reservations, and inquiries
average ~8 nights while confirmed stays average ~3.3 nights.

**Investigate:**
- The full **Guesty Open API** reservation, guest, conversation and review objects.
  Cover fields such as guest hometown/country, adults/children/infants/pets, `money`
  breakdown (fees, discounts, taxes), promotion codes, returning-guest flags, inquiry
  → quote → booking funnel, cancellation timestamps and policy, reviews, and
  **Guesty Insights / analytics exports**. Document rate limits and which fields are
  channel-dependent (Airbnb masks some guest data).
- What **Airbnb** and **VRBO** expose to hosts about guests and search demand
  (host insights, "views / conversion" dashboards, search-ranking signals). Also
  what their ToS forbid.
- The direct-booking website: what analytics it can capture ethically (UTM
  source, device, feeder city at the city level, consented email) and the
  consent requirements.
- **Privacy design**: minimization (store city/state/country and party composition,
  never names or emails in the pricing DB), retention, CPA/CCPA rights, and
  pseudonymous guest IDs for repeat-guest detection.
- **Analyses to run on the first-party data**: inquiry-to-booking conversion by
  quote price, LOS and lead time; LOS × season heatmap; origin mix by season;
  repeat-guest rate; cancellation hazard by lead time; price paid vs listed price;
  and which segments book the twins vs Cloud 9.

**Deliverable.** A field-by-field data-contract proposal (field, source API,
availability by channel, privacy class, and use in engine or simulator). Include an analysis
plan with the minimum sample size for each analysis to be meaningful at 3 homes,
and a statement of what cannot be learned from 3 homes alone.

---

## Prompt 3 — Will consumers buy this year? Macro and travel-demand leading indicators

**Question.** Which leading indicators predict, months ahead, whether demand for
luxury mountain lodging, specifically Winter Park, will rise or fall this season?
Which of them could the engine ingest as dated, point-in-time signals?

**Candidates to test for lead and strength of relationship.** Consumer confidence (Conference
Board, University of Michigan), S&P 500 / household net worth (the wealth effect on luxury
travel), airfare CPI and DEN seat capacity (published schedules), jet-fuel prices,
Ikon/Epic season-pass sales announcements, early-season snowfall and NOAA/CPC
ENSO outlooks (already partly in `src/signals`), Google Trends for "Winter Park
lodging", USD exchange rates vs MXN/GBP/AUD, school calendars in feeder markets,
gas prices for drive markets, unemployment in feeder metros, and travel-intent
surveys (Destination Analysts, Deloitte, MMGY). Also cover STR supply growth
(new listings) in Grand County.

**Method expectations.** For each indicator give its release cadence, **as-issued
vintages** (needed so replay has no lookahead; the repo enforces this through
`assert_no_lookahead` and `signal_observations.observed_at`), historical depth,
licence, and published evidence of predictive power for ski or mountain lodging. Give
effect sizes where they exist. Say how it should enter the engine. Options: a prior shift on booking
probability, a scenario parameter in the simulator, or display-only in the brief.

**Deliverable.** A ranked indicator shortlist (top 8) with a proposed
`signal_definitions` entry for each (key, cadence, lead window, expected sign) and a
backtest design using ≥5 past seasons of public data.

---

## Prompt 4 — Market-simulator science: compressing months into minutes without fooling ourselves

**Question.** How should a market simulator for STR pricing be designed so that
(a) a 1–6 month season runs in minutes, (b) its synthetic guests behave like
the real consumer mix, and (c) an engine that scores well in simulation will also
score well live?

**Context to read first.** `src/proving_ground/runner.py`,
`src/proving_ground/engine_loop.py`, `proving_ground_exam/scoring/demand.py`,
`proving_ground_exam/worlds/w1_calm.py`, `proving_ground_exam/worlds/w1_discrete_choice.py`,
`docs/proving_ground/DESIGN.md`, and the audit's §Simulator section. Today the world
publishes no bookings, so the engine gets no feedback. It is scored on its final
price against a static linear demand curve.

**Investigate:**
- **Simulation style**: discrete-event and agent-based simulation of travel shoppers (arrival
  process by lead time, search → consideration set → multinomial or mixed
  logit choice among own homes, competitor listings and an outside option). Survey
  hotel/airline revenue-management simulators in the literature, such as the PODS
  airline simulator, hotel RM simulation studies and the Expedia / Airbnb pricing research
  papers.
- **Calibration and validation**: how to fit segment arrival rates, lead-time/LOS/WTP
  distributions to scarce first-party data plus market aggregates (Prompts 1–2).
  Cover sim-to-real checks (does the sim reproduce observed pacing curves, LOS mix and
  booking windows?), hold-out seasons, and avoiding a simulator tuned to flatter the engine.
- **Competitor agents**: rule-based followers, generalized-tool emulators
  (PriceLabs-like), static owners, and adversarial undercutters.
- **Scenario and stress design**: drought, record snow, late opening or early closure,
  I-70 closure weekends, holiday calendar shifts, recession or consumer-confidence
  shocks, DEN capacity cuts, a new-supply surge, price wars, scraper outages and stale
  PMS data (data-quality stress), pandemic-like demand collapse, and
  mid-season regime change.
- **Statistics**: how many seeds per scenario, paired comparisons (common random
  numbers), confidence intervals on regret, and multiple-comparison control when
  many engine variants are tried.
- **Speed**: after the 2026-09-29 perf fix, one engine decision day is about 4s per home over
  a 365-night horizon. Compare parallel seeds, incremental repricing of only changed
  nights, horizon trimming and a surrogate engine for inner loops, with the
  risks of each.

**Deliverable.** A simulator design document with the world model, agent
definitions, calibration plan, a validation checklist that must pass before any
sim result is trusted, a scenario library spec and a compute budget
(e.g. "20 scenarios × 30 seeds × 180 days in < 1 hour on a laptop").

---

## Prompt 5 — A new pricing model for thin, luxury, mountain inventory

**Question.** What pricing formulation should replace or extend today's
"linear demand around a pooled reference price with a constant per-season
elasticity"? The target is 3–30 luxury homes with sparse bookings, strong
seasonality, multi-night stays and weather-driven demand.

**Investigate and compare, with worked examples at our data scale:**
- **Bayesian hierarchical elasticity**, pooled across homes, seasons and markets,
  with priors from the literature and updated from our own price variation.
  Estimate how much price variation is needed to identify it.
- **Safe exploration**: Thompson sampling or bandits constrained by the
  existing guardrails (move caps, floor, peak blackout), with the regret–revenue
  trade-off at our volume.
- **Finite-horizon dynamic pricing** (dynamic programming or bid-price): the option value
  of holding a night vs cutting now as check-in approaches.
- **Length-of-stay and network pricing**: pricing *stays*, not nights, orphan-gap
  interactions and minimum-stay as a lever.
- **Portfolio or cannibalization-aware pricing** for near-identical twins
  (Summit Haus vs Overlook Ridge).
- **Segment-aware pricing** using the consumer layer (expected segment mix by date,
  with a WTP distribution per segment).
- **Mountain-specific state**: SQI / snowpack, terrain open, I-70 access risk, DEN
  capacity and pass-holder behavior. How should these enter (shift demand level,
  shift elasticity, shift arrival timing)?
- Survey what generalized tools actually do (from public docs, patents and talks) and
  where they are known to fail in mountain markets: holiday compression, snow
  shocks, large-group homes and thin comps.

**Deliverable.** A model spec with equations, assumptions, the estimation procedure,
data requirements, and failure modes. Include a proposed evaluation ladder: replay, then
simulator scenarios, then shadow, then limited live. Give a 1-page comparison vs
today's engine, and say which pieces are genuinely novel.

---

## Prompt 6 — Beyond Winter Park: where generalized pricing tools fail

**Question.** Which other markets share the traits that make generalized STR
pricing underperform (thin comps, luxury or large-group inventory, weather- or
event-driven demand shocks, strong holiday compression, drive-vs-fly mix)? Where
could a mountain-built engine win next?

**Investigate:** other ski towns (Breckenridge, Steamboat, Telluride, Big Sky,
Park City, Tahoe, Jackson, Whistler, the Alps, Niseko), lake and coastal luxury markets
(Lake Tahoe summer, Outer Banks, 30A), desert and event markets (Palm Springs for
Coachella), and national-park gateways. For each market, collect: inventory size and
luxury share, seasonality shape, demand-shock drivers, data availability (comp
scraping feasibility, public signals equivalent to SNOTEL/CDOT), regulation (STR
permits, caps and taxes), and evidence (reviews, forums, case studies) that
generalized tools misprice there.

**Deliverable.** A ranked market-expansion shortlist (top 5) with a "what must
be rebuilt vs reused" table against the current `src/signals` and `config/resort`
architecture (e.g. `config/resort/winter_park.yaml` → one file per resort).

---

## Prompt 7 — Mont Luxe guest persona deep-dive (interview and survey design)

**Question.** What research program would reveal *why* Mont Luxe guests
choose these homes, what they compare them against, and what would make them book
at a higher price or book sooner?

**Investigate:** voice-of-customer methods for STR (post-stay surveys, review
text mining, inquiry-message topic analysis, conjoint and Gabor–Granger price tests,
van Westendorp), response-rate expectations, incentive ethics, and consent. Also
cover how survey-derived WTP compares with revealed-preference data.

**Deliverable.** A research plan the operator can run: survey instrument
(≤10 questions), review-mining taxonomy, inquiry-message coding scheme, sample-size
expectations, and exactly how each output would feed the simulator's segment
parameters or the pricing model.
