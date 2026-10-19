# R4: Generic STR pricer teardown, and the opening for a specialist

Status: COMPLETE (2026-10-16). Research only; no code or config changed.
Author: deep-research agent, 2026-10-16. All URLs accessed 2026-10-16 unless stated.
Scope: `docs/prompts/DEEP_RESEARCH_2026-10-16/R4_STR_PRICER_TEARDOWN.md`. Tests hypothesis H2.

**Code status, 2026-10-19 (after this dossier was written).** Commit `d3e8b92` changed the code
for the repo defects this pack found. The US-40 feed now calls the CARS 511 GeoJSON endpoint
(`api-511x-co.carsprogram.org/events/map-features`) and stores `QUALITY_UNAVAILABLE` on a non-JSON
response. Open-Meteo requests set `wind_speed_unit=ms`, so the ×2.237 conversion is now correct.
`events.yaml` adds MLK (2027-01-15 to 01-18), Presidents Day (2027-02-12 to 02-15) and Spring Break
(2027-03-06 to 03-21). `winter_park.yaml` keeps only product-specific Ikon Session Pass blackouts
(26–30 Dec 2026, 16–17 Jan 2027, 13–14 Feb 2027, matching the resort's pass page). The SQI price curve
is neutral below normal, so the 0.78 drought cut is gone. The 26 related tests pass. Still open:
live CARS behaviour is unverified; the parser matches "closed" anywhere in a feature's text, so a
shoulder closure (a real value in the feed, e.g. "Right shoulder closed") can set the full-closure
flag; whether the milepost window 233–243 covers the Empire-side approach (OTIS station 000223 there
is at MP 248.7–254.3) is UNVERIFIED; the SQI curve still raises price 12–18% in big-snow years, which
this research did not validate; and Open-Meteo's free tier remains non-commercial. Comp calendar
availability is still not persisted. The findings below are kept as written, because they explain
why each change was needed.

Conventions. **[V]** = vendor's own statement (conflict of interest). **[I]** = independent.
**UNVERIFIED** = could not confirm from a primary source. **STALE** = older than 3 years
(before 2023-10). **ND** = vendor does not disclose. Source IDs `[S#]` resolve in the
reference list at the end.

## 0. Summary

- **What generic pricers are.** PriceLabs, Wheelhouse and Airbnb publish real models.
  PriceLabs uses reference-date booking curves, pacing and pickup, per-date elasticity and
  a Bellman horizon. Wheelhouse uses a GBM base price with kriging, Kaplan-Meier booking
  curves, gamma warping and an asymmetric price response. Airbnb uses a GBM P(book) model
  and a bounded "strategy" layer. All of them sit inside a multiplicative factor stack
  scaled by a **user-owned base price**. Their comp data is scraped calendars. "Booked
  price" is the last listed price before the dates closed, and owner blocks are removed
  heuristically. No vendor publishes an error rate (sections 2, 4.2).
- **H2 is partly supported.** No vendor discloses snow, resort operations, pass
  blackouts, road closures or origin school calendars as inputs. Their comp pools (350
  listings within 15 km; 100-500 listings) cannot be true 5+ bedroom peers in this valley,
  where we find about 14. Their defaults are calibrated on urban data (up to 40%
  last-minute discounts inside 60 days). The independently measured generic tool (Airbnb
  Smart Pricing) earns its lift by **cutting price**: about -6% price, +8.6% revenue, in an
  adopter comparison open to self-selection. H2 is
  **not** supported in its strong form. On modelling and data volume, the generics are
  ahead of our engine, and PriceLabs added fee-isolated comp calendars in 2026 (section 7).
- **Our engine, honestly.** We lead on mountain inputs (SQI, resort ops, CDOT access,
  substitution), safety and owner-net framing. Most of those are candidate-only, off by
  default, or unproven. Comp scraping fails on 67% of rows. Our candidate trails the real
  rate card in simulation, and we cannot measure market pickup: comp calendars are fetched
  but their availability is not stored (section 6). `events.yaml` has no MLK, Presidents or
  Spring Break entries for 2026-27.
- **Booking window and snow.** Winter Park's winter booking window is about **72 days**
  (AirROI, 2025-26, all units), so most winter demand books before the snowpack is known.
  That supports a snow-aware prior in principle. But the size is small: Colorado's
  elasticity implies about -7% revenue in a 60%-of-normal year, and in the 2025-26 drought
  Winter Park ADR *rose* 22% while occupancy fell. Our live SQI curve cuts *price* about 22%
  at drought SQI, roughly three times too strong. Rec 8 says to flatten it until it is
  fitted (sections 3.1a, 13).
- **Top specialist edges.** (1) Peak and holiday ceilings for large homes, set from true
  peers. (2) Block-aware pickup for peers we know by name. (3) Snow-conditioned pricing of
  the first booking wave and the ceiling. (4) Holiday stay blocks and arrival-day rules.
  (5) An owner-net objective on the all-in price. All of them depend first on **fixing
  scrape reliability** (section 8).
- **Shadow benchmark: yes.** Start with a PriceLabs-HLP policy arm in the proving ground,
  which costs nothing. Then run a field shadow with PriceLabs connected to Guesty and Sync
  off. The trial is 30 days, then roughly $30-60/month for three homes. Before that, add a
  Guesty-side daily rate diff, because our write counter cannot see a third-party write.
  PriceLabs' API serves prices only for listings that are syncing (section 9).
- **Antitrust.** RealPage-style rules target pooled nonpublic data, and since July 2026
  the Third Circuit (Cornish-Adebiyi) has let a shared-algorithm hotel case proceed, against
  the Ninth Circuit's Gibson. A single-operator
  engine on public comps plus its own data is clean by construction, so we should not buy
  co-op data for pricing (section 4.4).

## 1. Method

1. Read the repo files the shared context lists so the "our engine" column is honest
   (section 6).
2. Teardown passes per vendor: help centre and API docs first, then engineering blogs and
   founder material, then patents, then third-party reviews and forums, then litigation.
3. Adversarial pass: evidence against each vendor's lift claims, and evidence against H2.

Limits that apply to the whole dossier: Reddit cannot be fetched by this agent's tools
(the search API refuses the domain), so Reddit evidence is absent, not negative. Facebook
host groups are closed and were not read. Several vendor help centres returned 403/404 to
the fetch tool; where only a search snippet was available the claim is tagged
"(snippet)".

## 2. Vendor teardowns

(Sections 2.1-2.11 below.)

### 2.1 PriceLabs (Dynamic Pricing, Hyper Local Pulse, Market Dashboard, Portfolio Analytics)

PriceLabs publishes more about its method than any other STR pricer. Everything below is
**[V]** unless marked.

**Data inputs.**
- Scraped public listing pages and calendars on Airbnb and Vrbo for the Market Dashboard
  [S1]; the HLP pricing blog adds Booking.com and "over 10 million units" [S3]; a 2023 data
  blog adds "direct data from KeyData" [S2]. So PriceLabs mixes scraped data with
  PM-contributed reservation data from Key Data, which matters for the antitrust section (4).
- The customer's own reservations via PMS/OTA integration [S3].
- Hotel future prices and occupancy for the area (seasonality factor uses "historical
  rental and hotel data") [S5].
- No disclosed use of snow, resort operations, road closures, pass blackout calendars,
  school calendars of origin markets, flights or search data. "Known event information"
  is entered manually by PriceLabs' RM team [S8]. **ND** for anything else.

**How bookings are inferred from calendar blocks (the core weakness of every scraper
pricer).** Per the Market Dashboard methodology [S1]:
1. Each listing's calendar is scraped repeatedly; transitions available -> unavailable are
   logged. Consecutive dates that close between two scrapes are initially one booking.
2. Booked date = the scrape interval in which dates closed. Lead time and length of stay
   follow from that.
3. **Booked price = the last listed price seen before the dates closed.** It is a listed
   price, not a transacted price: discounts, weekly/monthly reductions, special offers and
   fees are not observed.
4. "Block removal" heuristics using LOS, booking window, market occupancy and extreme price
   variation try to drop owner blocks. Any "stay" > 60 days is removed.
5. Other channels are seen only through calendar sync onto Airbnb.
6. PriceLabs states the limitation itself: "no method is perfect"; listings with unusually
   high recent occupancy may have missed blocks counted as bookings [S1].
7. Scrape frequency: **ND**.
8. Fee basis: after Airbnb's host-only-fee switch the guest-facing nightly rate in market
   data rose "roughly 15%" [S1]; whether cleaning fee is inside ADR is **ND**.

Known error of this inference, mechanistically (no vendor publishes a measured error rate;
see 4.2 for independent attempts):
- *Owner/maintenance blocks read as bookings* -> occupancy biased up, and the "booked
  price" attached to a block is whatever the listing asked, so a home that blocks its
  Christmas week for the owner contributes a fake high-priced "booking".
- *Back-to-back bookings merged* when both close in one scrape interval -> LOS biased up,
  booking count biased down. Large ski homes with 4-7 night Christmas stays are exactly
  the case where two bookings can abut.
- *Calendar closures by rules* (advance notice, preparation time, max lead time) look like
  bookings. AirDNA retroactively reclassified "advance notice" and "preparation time" days
  in 2024, changing baselines back to 2022 [S47 (snippet), UNVERIFIED primary].
- *Price selection bias*: the last listed price before closure over-represents the price
  at which a night sold *if* listings reprice daily; for listings that price once a season
  it is fine. Unobserved: special offers, weekly discounts, direct-site rates.

**Model.** Per the 2023 "algorithm" blog series by the PriceLabs data-science team [S3][S4]
(September 2023: **STALE** by a few weeks; the HLP algorithm may have changed since):
- *Forecast*: for each future date pick "reference dates" (same season, same weekday,
  holiday/event, booking-curve similarity); the forecast is a function of their final
  booking curves and the future date's curve to date, refined by **pacing** (occupancy now vs
  reference dates at the same lead) and **pickup** (recent booking velocity).
- *Demand*: modelled as P(book | price), not unit counts; **elasticity estimated per date
  and per comp set** [S3]. Price also signals quality, so very low prices do not guarantee a
  booking.
- *Objective*: maximize expected revenue P(book) x price per date; the horizon problem is a
  Bellman recursion over lead time [S4]. The worked toy example: one static price $600 gives
  E[rev] $300; a three-step path ($800 at 360d, $600 at 240d, $400 at 120d) gives $303
  (+1%). PriceLabs says timed last-minute discounts gained "around 9%" in experiments with
  real data and that far-out premiums plus last-minute discounts average +11% [S4] (no
  design, sample, or CI disclosed: **[V]**, unauditable).
- *Far-out premium* is justified as a hedge against forecast uncertainty when little demand
  has booked yet [S4].
- PriceLabs explicitly states mountain markets are "a lot less price sensitive in the Ski
  season than in the Summer season" [S3].

The *user-facing* calculation is still a multiplicative stack around a user-set base price
[S5]: base price ("average nightly rate throughout the year") -> seasonal factor -> demand
factor (day-of-week, events, holidays, forecast) -> pacing factor ("certain markets only")
-> customizations (last-minute, orphan, adjacent factor, smoothing, date overrides) ->
min/max clamp -> offset. So the learned model above lives *inside* the seasonal/demand
factors, and the result is scaled by a **base price the user owns**. If the base price is
wrong (common for a $2k/night home with few comps), every factor scales a wrong number.

**Defaults that matter for a luxury ski home** [S6][S7]:

| Default | HLP (current algorithm) | Old algorithm |
|---|---|---|
| Last-minute discount | market-driven, cap **40%**, only within 60 days | gradual 30% over next 15 days |
| Far-out premium | market-driven, starts 60 days out, cap **20%** | 20% ramped over 7 months from day 30; flat 20% after 240 days |
| Occupancy-based adjustment (OBA) | market-driven: listing occupancy vs market, next 60 days; discounts cap 20%, premiums cap 15% | profile tables |
| Orphan day | 20% off gaps of <= 2 days | same |
| Booking recency factor | 5-15% off next 30 days if no booking in 15-45 days and occupancy weak | n/a |
| Safety minimum price | prior-year ADR in a +/-1 week window; exact prior-year ADR on holidays | n/a |

Two mechanics bite here. (a) OBA is computed **per listing** and "blocked dates count as
booked" except for listed PMSs [S7]: an owner block lifts measured occupancy and therefore
price. (b) The "safety minimum" anchors holidays on *last year's* ADR, and applies only to
dates that had a booking last year [S6]; our own repo records a prior-season Christmas average
(`config/policies/default.yaml`, `compose.deference` comment) in a season whose snowpack was
~60% of normal at Berthoud Summit (`docs/ARCHITECTURE.md`, "Drought reframing"), so for
nights that booked last year a prior-year anchor would encode a drought year as the floor
reference (it is a floor, so the harm is limited, but it is the wrong reference).

**Min-stay** [S9]: Lowest/Highest allowed bounds; "Adaptive Occupancy Adjustment" cuts
min-stay by 1 night if next-90-day occupancy is 10-20% behind market, 2 nights if >20%
behind; holidays add 0-2 nights only if the event is flagged important *and* the demand
factor is >= +10%, dampened inside 60 days; far-out and last-minute min-stay rules; orphan
gap fill (gap, gap-1, gap-2); adjacent-booking exceptions; a "Booking Value" rule that sets
min-stay so the stay total clears a threshold. No arrival-day/departure-day (check-in on
Saturday only) rule is described for STRs on that page (**ND**).

**Market granularity.** HLP's pricing market is "350 similar-sized nearby listings in a
maximum radius of 15km", radius set dynamically, found with Uber's H3 grid [S3]. Bedroom
count is the size key and can be edited manually [S10 (snippet)]. Consequence for Winter
Park: 350 "similar-sized" listings within 15 km of Fraser cannot all be 5-6 bedroom,
16-sleeper homes (our own sweep sees ~280 bookable listings in the whole Winter Park /
Fraser bbox, of which only 14 curated peers pass bedrooms >= 5 and sleeps >= 14:
`docs/rules/COMP_DATA.md`, `config/policies/default.yaml` `scrape.group_size`). So either
the radius expands across Grand County (Granby, Grand Lake: different demand) or the set
fills with smaller units. Which one PriceLabs does is **ND**; both dilute the signal for a
large home. The Neighborhood Data tab lets users hand-pick comps for *display*; whether a
hand-picked set changes the pricing market is **ND**.

**Business model.** $19.99 for one listing per month in the US, falling with volume (the
source lists $9.99 each at 5 listings; the 2-4 listing tier is not stated); a 30-day no-card
trial [S11]. One third-party review mentions a 1%-of-revenue plan, but S11 does not, so that
option is **UNVERIFIED**. Figures vary by source and date. Flat per-listing pricing means PriceLabs' revenue does not rise with the customer's
ADR, so it has no direct incentive to push price up or down; its incentive is retention
(customers who see occupancy) and the breadth of its scraped data asset.

**Evidence of lift.** "26% RevPAR boost for new users within three months", "~9% more
revenue than its previous model" in trials, and the +9%/+11% figures above [S2][S3][S4]. All
**[V]**, no published design. A "new users" before/after comparison is confounded by
selection (users adopt when they are underperforming, mean reversion) and by market
trend. No independent evaluation of PriceLabs lift was found (section 4.3).

### 2.2 Wheelhouse

Wheelhouse publishes the most technical engine description of any vendor (a 7-part
research page, last updated 2023-05-01 [S12]; **STALE**). **[V]**.

**Data inputs.** "~20 billion new data points" daily across "21MM listings from major
OTAs", plus hotel and STR future pricing for far-out demand [S12]. Own reservations via
PMS integrations. Search, weather, snow, roads: **ND / not mentioned**.

**Model** [S12]:
1. *Base price*: gradient-boosted trees trained on all active units in a market, target =
   each unit's median nightly price over the prior year; features: bedrooms, bathrooms,
   sleeps, unit type, parking, **fees (cleaning, deposit, extra guest)**, location, booking
   performance of the unit and neighbours, occupancy. Residuals are spatially smoothed by
   **kriging** and added back (example: a +10% pocket). Bedrooms and sleeps are the top
   features (San Francisco example). Cross-validated; no error metric published.
2. *Booking curves*: Kaplan-Meier survival estimates of time-to-booking with right
   censoring; booking curve = 1 - S(t), final occupancy = 1 - S(0).
3. *Gamma warping*: a single parameter gamma warps the market baseline curve to a date's
   curve while keeping it monotone in [0,1].
4. *Price response*: gamma = a + b * (delta - d)^2 * 1[delta > d], delta = relative price
   gap from base. The multiplier is the f^-1(gamma) that equalizes expected occupancy with
   baseline. **40% market occupancy maps to multiplier 1.0**; above it price rises roughly
   linearly then steeply; below it falls "only slightly".
5. *Predictive demand* (far out): seasonality by low-pass filter on average price by day of
   year; day-of-week; local events by high-pass filter after removing both, localized by
   distance.
6. *Reactive demand* (near in): recomputed daily from booking curves and gamma warping.
7. *Blending*: weight on reactive rises as the stay approaches; large, high-certainty spikes
   raise it sooner. Formula **ND**.
8. *Calendar controls*: SF single-night gaps book at 7.3% vs 41.1% for a normal day; a
   "temporality adjustment" starts about two weeks out and reaches roughly 30% off on the
   day, "based on observed operator behavior".
9. *Dynamic pacing*: similar units grouped into "unit types" priced as a portfolio; prices
   firm as a type fills. Wheelhouse's own pacing A/B tests: **+0.9% to +1.5%
   building-level revenue** [S12] - the one vendor-reported lift with a stated design, and
   it is small.

Market granularity: the RM API's Neighborhood Data endpoint defines the neighbourhood as
"same bedroom count, same geographic cluster"; radius and minimum count **ND**; market-wide
aggregates and dynamic comp sets are "future releases" [S13]. Wheelhouse also sells
"Dynamic Sets" (custom comp sets, $12.99/set/month) [S15].

Controls (RM API, 30+ endpoints, beta) [S14]: base-price strategy, seasonality curves,
occupancy pacing, demand sensitivity, gap fills, last-minute discounts, far-future
premiums, check-in/out rules, a Simulation endpoint, per-factor attribution ("10+"
factors: seasonality, local demand, time-to-booking, scarcity, occupancy pacing, custom),
and a base-price "anchor credibility score" 0-100. Strategy presets Conservative /
Recommended / Aggressive trade occupancy against ADR [S16][S17] (snippets).

Business model [S15]: Pro Flex 1% of revenue (excluding taxes and fees, billed at
reservation, refunded on cancellation, $2.99 minimum) or Pro Flat $19.99/listing/month
($16.99 at 10-49). Free tier exists.

Lift: "22% increase in revenue for users" (no baseline or method) [S12] **[V]**; the pacing
A/B +0.9-1.5% is the credible number.

Transfer to Winter Park: the 40%-occupancy-equals-par rule and the "prices fall only
slightly below baseline" shape are calibrated on urban SF data. A ski home with 70% peak
final occupancy (our `DEFAULT_FINAL_OCCUPANCY.peak_ski`, an assumption) and near-zero
summer weekday demand has a different curve; whether Wheelhouse fits market-specific
response curves is **ND**.

### 2.3 Beyond (formerly Beyond Pricing)

**[V]** throughout. Beyond's algorithm explainer [S18] and ski-town note [S19] are both
stamped 2026-10-06 on the site, but the explainer refers to "the last eighteen months" of
pandemic data, so the text likely dates from about 2021 and the stamp is a site-wide
update date. Treat the content as possibly **STALE**.

**Data inputs** [S18]: listing info, occupancy and prices from Airbnb, Vrbo and
Booking.com, "continuously"; future hotel prices to catch anomalies far out; 6+ years of
history per market for seasonality; own reservations through PMS integration. The luxury
page adds "search data" to identify what drives high and low prices [S20], with no
detail (**ND** what search data, from whom).

**Model** [S18]:
- Base price = the property's "value", roughly its average annual price; secondary
  algorithms suggest it; the user can move it as a master lever.
- Seasonality by decomposition over 6+ years, pandemic excluded; "fluid" seasons.
- Seasonal pacing vs prior years.
- Day-of-week analysed by sub-area and season.
- Events: three detectors run together: (1) day-over-day jumps in forward occupancy not
  explained by season and weekday; (2) prior-year demand for recurring events used as a
  placeholder price floor that blends into actual bookings as the date nears; (3) nearby
  hotel price anomalies.
- Far out: relies on historical event demand because reservations are sparse; Beyond warns
  that cheap early bookings undermine this.
- Named but undescribed: last-minute discounts, dynamic channel markups, gap filling.
  Min-stay: **ND** on that page.

**Market granularity**: comp sets of "between 100 and 500 similar listings" of "like
units" in the same area, auto-suggested then hand-adjusted by staff (e.g. separating
beachfront) [S18]. A 100-listing floor in Winter Park cannot be 5+ bedroom homes (see 2.1);
**ND** how Beyond fills it.

**Mountain content.** Beyond's ski note [S19] reports trailing-12-month averages
(Breckenridge 26-day lead time, 3-night stays, ADR $288; Park City 24 days; Tahoe 33 days;
Mammoth 13 days), says demand "follows snowfall" with surges when storms are forecast, and
that Christmas/New Year searches are 20% of activity in those markets. Its advice for
snow is "real-time market data and alerts" for the manager to act on, which reads as a
human workflow, not a model input. Note these are all-unit market averages; they are not
the booking window of 16-sleeper homes (our `pace.py` `DEFAULT_CURVE` comment cites
"Colorado ski booking windows of 24-33 days (Beyond Pricing)": that citation is to
all-listing, all-season market averages; AirROI's winter-only Winter Park figure is ~72
days [S88], so the cited window understates winter lead times; see 3.4).

**Health score** [S21 (snippet)]: booking speed vs the market; <60 needs change, 60-80
room to improve, 80-100 fine.

**Business model** [S22]: default 1% "Pay on Book" or 1.49% "Pay on Stay"; the fee base
usually includes nightly rent **plus cleaning and extra-guest fees**; cancellation credits
are issued minus a service fee. A percent-of-revenue fee grows with ADR, so at
$2k/night the fee per booked night is ~$20-30 versus ~$0.66/night for a $19.99/month flat
plan at full occupancy. The incentive of a percent-of-booking fee: the vendor is paid on
*booked* revenue, so it is paid more by a booking than by an empty night held for a
higher price; Pay-on-Book also pays it on bookings that later cancel (minus credit). That
is a mild tilt toward conversion over yield. Forum users also report cancelled-booking
fees not being refunded [S23].

**Lift**: Beyond's home page says "proven to grow profits"; no study found. One forum user
who ran Beyond and PriceLabs side by side said Beyond "greatly outperforms PL" [S23]: one
anecdote, contested in the same thread.

### 2.4 AirDNA (Smart Rates, Adapt; MarketMinder)

AirDNA is primarily a scraped-data analytics company. Its booking inference [S24]:
"Revenue and booking figures are projections from a machine learning model trained on
actual booking data" which "can not perfectly distinguish between booked and blocked
nights"; booked price = last available rate before the night closed; weekly/monthly
discounts not applied; **ADR includes cleaning fees**; nights booked while a listing is not
on Airbnb/Vrbo are invisible; listings on both platforms have reservations summed. The
public "how it works" page (403 to this agent) claims 95%+ agreement with Airbnb's public
reporting and a newer model with "2x accuracy" for mid/long stays (snippet only,
**UNVERIFIED**, **[V]**). Agreement with Airbnb's *aggregate* public figures says nothing
about per-listing, per-night error in a thin segment like 5+ bedroom Winter Park homes.

"MarketMinder" is AirDNA's market-analytics product name; this agent could not reach a
primary page describing it (**UNVERIFIED** feature set). Smart Rates (older) chose comps
"by proximity and similar bedroom, bathroom and guest capacity", refreshed daily, and
offered Conservative/Balanced/Aggressive base rates (help-centre snippet, now 404) [S25].

**AirDNA Adapt** (launched 2026-09-01) is AirDNA's new full RMS [S26][S27]: daily rates
and **minimum stays** with a rationale per rate; built-in event detection; auto-built,
editable, unlimited comp sets with a daily comp calendar of rates, min-stays and
availability; four goals (revenue, occupancy, balance, "steadier earnings from earlier
bookings"); an AI assistant that explains decisions and applies changes only on approval;
integrations with Airbnb, **Guesty**, Hostaway, Hospitable, OwnerRez, Uplisting. Beta:
>14,000 listings over ~3 months; **no lift figures published**. Price reported at about $20
per listing [S27]. AirDNA estimates 15% of hosts worldwide and 31% in the US use dynamic
pricing [S27]. Model internals: **ND** ("AI at its core").

### 2.5 Key Data (KeyData Dashboard / ProData)

Key Data is a **benchmarking** product, not a pricer: "No. KeyData is not a pricing tool"
[S28]. Its distinctive asset is **PM-contributed reservation data** from 80+ PMS
integrations, "sourced directly from operators, never scraped or modeled", with OTA data
layered on [S28]; counts of integrations and properties vary across its own pages (50+ to
80+; 700k vs 13M properties) [S29 (snippet)]. It counts only paid guest nights, excluding
owner stays and maintenance holds (snippet) [S29]. Filters include bedroom count,
amenities, location, stay length, booking source; forward pacing vs prior year [S28].
Minimum cell sizes and anonymization: **ND**. PriceLabs ingests Key Data "direct data"
[S2].

Why it matters: Key Data is the only vendor in this set whose data is **transacted**
(booked price, real occupancy), which fixes the block-vs-booking problem. It is also the
data structure that the RealPage cases target: nonpublic, competitor-contributed,
current reservation data feeding pricing decisions (section 4.4).

Its Colorado blog post on booking windows (page dated 2026-09-18 but written during
COVID; **STALE**, true date likely 2021) reported Winter Park bookings "down 34%" in a
60-day window vs the prior year [S30]: useful only as evidence Key Data has Winter Park
coverage.

### 2.6 DPGO

Small vendor; nearly everything is second-hand. Marketing claims "200+ local market data
parameters" and occupancy gains "up to 90%" [S31] **[V]**, unfalsifiable. Third-party
review lists recommended/conservative/aggressive/custom strategies and fees of $1 per
booked night or 0.5% of booked price [S32 (snippet)]. Five Capterra reviews; one reports
dynamic prices silently reverting to base prices [S31]. Model, comp definition,
inference: **ND**. Not a serious benchmark for 5+ bedroom luxury.

### 2.7 Vantory

The repo README says "Not a Vantory clone", so the operator has seen it. Vantory's site
[S33] positions it as an AI "silent C-suite" over the PMS and books (Guesty, Hostaway,
Hostfully, Track, Streamline; QuickBooks, Xero): pricing "on real demand ... what a guest
will actually pay", "benchmarks you against your ceiling, not your past", revenue per
night over full calendars. Fee: $300/month plus $35/door/month; "never takes a cut of your
upside". Claims: 7-13% year-one lift, up to 117% on mispriced units, 4-8% more per home;
footer says dashboard figures are illustrative. Founder: Paul Burke, a former operator who
built and exited an STR portfolio "in his market" (other sources say a Colorado luxury
company; **UNVERIFIED**). Model, data sources, comp method: **ND**. It is the closest
generic tool to our framing (ceiling-relative, owner-economics, explanation) but discloses
no mechanism, so it cannot be benchmarked from public information.

### 2.8 Duetto (vacation-rental product)

No Duetto STR / vacation-rental product was found. Duetto's announcements are hotel
products (group "BlockBuster", function space "OpenSpace") and a resort-operator customer
(Pierre & Vacances / Center Parcs) [S34][S35]. The prompt's "Duetto vacation-rental
product" is **UNVERIFIED / likely nonexistent**; Duetto is covered by R2 (hotel RM).

### 2.9 Airbnb Smart Pricing

Airbnb's help article [S36]: "hundreds of factors about your listing and your area"; host
sets min/max; early-bird discounts can push below the minimum; weekly/monthly/trip-length
discounts override it; Smart Pricing overrides rule-sets; Airbnb may switch it off in
disasters or unrest. Update frequency: **ND**.

The engine behind it is described in Airbnb's KDD 2018 paper (Ye et al., "Customized
Regression Model for Airbnb Dynamic Pricing", KDD '18, doi:10.1145/3219819.3219830)
[S37][S38]:
1. A per-market GBM predicts P(booked) per listing-night from listing features (price,
   room type, capacity, bedrooms, amenities, location, reviews, historical occupancy,
   instant book), temporal features (day of year/week, gaps, lead time) and
   supply/demand features (available listings nearby, page views, search and contact
   rates).
2. A "strategy model" outputs price = calendar price x V, where V is an asymmetric
   exponential in q (booking probability) and a cluster-level demand score D, with learned
   per-listing parameters theta1, theta2 and bend constants phi_H, phi_L in (1,2).
3. It is trained with a **custom hinge-type loss**: zero when the suggestion lies in
   [L, U]; for booked nights L = booked price, U = c2 x price; for unbooked nights U = the
   price that failed to book, L = c1 x price.
4. Offline metrics: *price-decrease recall* (share of unbooked nights where the suggestion
   is below the ask) and *booking regret* (median shortfall of the suggestion below the
   booked price).
5. Crucially (paper text as summarized by The Morning Paper; the KDD abstract confirms only
   that accurate demand curves are "very difficult to estimate" and that the strategy model
   powers Price Tips and Smart Pricing [S37]): **"direct revenue maximization on the estimated demand curves often failed
   to improve host revenue in online A/B tests"**, which is why Airbnb moved to the
   bounded strategy model [S38]. This is first-party evidence from the largest dataset in
   STR that naive `argmax P x P(book|P)` on a fitted demand curve is fragile.

Independent evidence: Zhang, Mehta, Singh and Srinivasan (Marketing Science, 2021) found
adopters' **nightly rate fell about 6% (5.8% per the HBS summary; 5.7% in abstract
snippets) and daily revenue rose 8.6%**, comparing adopters with non-adopters across 2,118
properties in 7 US cities, 2015-17 [S39][S96]. Adoption is self-selected, so this is not a
randomized lift. Smart Pricing
works mainly by **lowering price and raising occupancy**. That matches the forum complaint
that it sets prices "too low" [S40] and a documented Edinburgh Festival glitch (Airbnb blamed a "global systems error") where
Smart Pricing went below hosts' set rates [S41]. A 2025 structural study of Tokyo argues
Airbnb's pricing algorithm "self-preferences" commission revenue, raising Airbnb's
commission by ~38% at a ~5% welfare cost (single-author preprint, not peer reviewed)
[S87]. Airbnb's FY2025 10-K describes its host tools as helping hosts "optimize pricing,
and maximize occupancy" [S95]. Airbnb's incentive: it is
paid a percentage of gross booking value, so it gains from bookings and from marketplace
liquidity and guest satisfaction; it does not bear the host's cost of selling a peak night
cheaply early. For a peak-scarce product (a 16-sleeper on Christmas week), occupancy-led
pricing is the wrong bias.

### 2.10 Vrbo / Expedia rate automation (MarketMaker)

Free tool inside the Vrbo dashboard [S42][S43]. Inputs: supply/demand trends,
seasonality, events, national holidays, rates of booked and unbooked properties,
historically booked rates, property features; updates every 24 h (older pages say up to
48 h); horizon 90/180/365 days; required min/max; up to 10 excluded date ranges; manual
override permanently stops suggestions for that date. **It does not factor in
length-of-stay requirements** and **partners integrated with property-management software
are not eligible** [S42] - so Mont Luxe, on Guesty, cannot use it. Claims (Vrbo internal):
+39% bookings and +38% revenue for units with vs without the tool [S42]: an
adopter-vs-non-adopter comparison with no matching detail, so self-selection is
uncontrolled. **[V]**.

### 2.11 Guesty PriceOptimizer

Built by Guesty's data-science/BI teams, implemented with an outside contractor
(Forbytes) as a microservice inside Guesty [S44]. Inputs per Guesty [S45][S44]: demand,
seasonality, day of week, holidays, local events (auto-detected concerts, festivals,
sports, conventions), location, size, reviews, amenities, average LOS, occupancy,
inventory, competitor prices and stay lengths; user-defined competitor "market groups"
to benchmark ADR and occupancy. Mechanics from help-centre snippets [S46]: base price is
the anchor and **Guesty never changes it automatically** (automatic, manual, market-pricing
or listing-history sources); **demand pacing** = % of (base + other dynamic factors), set
automatically with a "20% lower / 20% higher" aggressiveness option or manually by
occupancy and 15-day "days before check-in" windows; min/max clamps; min-nights,
last-minute, event and time-based rules. Claim: "+33% revenue per available listing in
the first year" for Guesty users [S45] - a platform-adoption claim, not a PriceOptimizer
A/B. Cost: **ND** on the page. Model type, comp radius, snow or road inputs: **ND**.
Because we already pay for Guesty, PriceOptimizer is the cheapest shadow benchmark to
switch on if it can run in recommend-only mode (open question for the operator).

## 3. Mountain-market probes, vendor by vendor

Legend: **Yes** = disclosed as a model input; **Manual** = user/staff can encode it by hand
(override, event, season profile); **No/ND** = not disclosed anywhere found. "ND" is not
proof of absence; it means a vendor that would gain from advertising the feature does not.

| Mountain driver | PriceLabs | Beyond | Wheelhouse | AirDNA Adapt | Guesty PO | Airbnb SP | Vrbo RA |
|---|---|---|---|---|---|---|---|
| Snowpack / snowfall / forecast storms | ND (manual) | ND; blog tells managers to react to storms by hand [S19] | ND | ND | ND | ND | ND |
| Resort open/close dates, terrain open % | ND; "events" are manual RM-team entries [S8] | ND | ND | ND | ND | ND | ND |
| Pass products and blackout dates (Ikon/Epic) | ND | ND | ND | ND | ND | ND | ND |
| Road / pass closures (I-70, US-40 Berthoud) | ND | ND | ND | ND | ND | ND | Airbnb may switch SP off in disasters [S36] |
| Origin-market school calendars (DPS, Texas ISDs) | ND (indirectly via pace of past years) | ND | ND | ND | ND | ND | ND |
| Holiday detection | Yes (historical + pacing) [S8] | Yes (prior-year event demand as placeholder floor) [S18] | Yes (high-pass filter "events") [S12] | Yes ("built-in event detection") [S26] | Yes (auto events) [S45] | ND | Yes ("national holidays") [S42] |
| Holiday min-stay bump | Yes, +0-2 nights if flagged important and demand >= +10% [S9] | ND | ND | Yes (sets min-stays) [S26] | Manual | No | No (ignores LOS) [S42] |
| Arrival/departure-day rules | Yes, only for some PMSs; holidays via date overrides [S48] | ND | Yes ("check-in/out rules") [S14] | ND | ND | host setting | ND |
| Large-home (5+ BR) comp segmentation | Bedroom-keyed "similar-sized" set of 350 within 15 km [S3] | 100-500 "like units" [S18] | Same bedroom count cluster [S13] | Auto-built comp sets [S26] | User "market groups" [S45] | Cluster of similar listings (patent) [S49] | ND |
| Fee-inclusive comparison | Yes since 2026: competitor calendar with fee isolation (10 comps), guest-price view, LOS all-in analytics [S50] | ND | Base-price model uses fees as features [S12] | ND | ND | Airbnb displays total price [S51] | ND |

**3.1 Snow.** Peer-reviewed evidence that snow moves STR revenue exists: Parthum and
Christensen (JEEM 2022) estimate a snowpack elasticity of daily STR revenue of **0.223**
nationally from ~12.5 million AirDNA property-days near 236 US resorts, **0.135 for
Colorado**, larger early in the season, and a **positive bed-count interaction (0.067)** -
larger properties are *more* snow-sensitive [S52]. Data are 2014-2017 (**STALE** as
calibration, still the best causal estimate). No generic vendor discloses using snow. They
see its effect only after it shows up in pace and pickup. The best current Winter Park
evidence puts the winter booking window at about **72 days** on average (AirROI, winter
2025-26, all units [S88]), so a large share of a winter's bookings is made before the
season's snowpack is known and before pace can register it. A pace-reactive tool therefore
reacts *late* to snow for most winter nights, which is where a snow-aware prior can add
value (sizing caveat in 3.1a and 13). See 3.4.

**3.1a The size of the snow effect, and a problem in our own prior.** Parthum and
Christensen's Colorado elasticity of 0.135 on *revenue* implies that a snowpack at 60% of
normal moves STR revenue by about 0.135 x ln(0.6) = **-6.9%**. Our live engine
(`config/policies/conditions.yaml`, `sqi.enabled: true`) maps SQI 0.62, labelled "~2025-26
drought Christmas", to a **0.78 price multiplier** (-22%) and SQI 0.50 to 0.72 - roughly
three times the revenue effect, and applied to *price*, not revenue. The 2025-26 drought
data point the other way on price: AirROI reports Winter Park winter ADR **up 22.2%** ($455
to $556) while occupancy fell from 44.9% to 35.8% and supply rose 9.9% [S88] (all-unit,
scraped and vendor-modelled; mix and supply effects are not separated). So both the
peer-reviewed elasticity and the one current local observation say the drought shows up in
**occupancy**, not price. Hyper-specialization on snow can lose money if the prior is the
wrong size; see rec 8.

**3.2 Resort ops, passes, roads.** Winter Park's Ikon status is itself a demand
mechanism, but our evidence on it conflicts. Ikon's own 2026-27 Base Pass page lists
Winter Park among the 15 *unlimited* destinations and lists Northern Hemisphere blackouts
of Dec 26-30, 2026, Jan 16-17 and Feb 13-14, 2027 in the same section, without saying
whether they apply to Winter Park [S92]. Retailer listings say Winter Park has **no**
Base Pass blackouts [S53]. Our own `config/resort/winter_park.yaml` lists Winter Park
blackouts of 2025-12-26..27 and 2026-01-17 (last season, "verify annually"). These cannot all
be right; the operator should confirm (section 11, Q8). If Winter Park has no blackouts while
other Base resorts do, Base-Pass holders are diverted *toward* Winter Park on those dates;
if it shares them, the effect reverses. Either way it is a cross-resort signal no generic
tool models, but edge #6 depends on knowing which. Berthoud Pass (US-40) closures for avalanches and snow
removal are frequent and documented case by case in news (e.g. a multi-day January
closure, a March 2026 avalanche closure) but CDOT does not publish an easy closure-hours
series [S54]. Our engine already has a CDOT collector and access-risk feature (section 6).

**3.3 Origin school calendars.** Spring-break weeks differ by origin: Houston ISD
2027-03-08..12; Dallas and Austin ISD 2027-03-15..19 (third-party calendar sites,
**UNVERIFIED** against districts) [S55]; Denver Public Schools 2026-27 spring break is
reported as 03-15..19, 03-22..26 or 03-29..04-02 by different aggregators [S56] -
the conflict itself shows why a curated, verified calendar is an asset. Generic tools see
spring break only as last year's pace on the same calendar dates, which is wrong whenever
district calendars shift week to week year over year (Easter-anchored breaks move by up
to five weeks).

**3.4 Booking-window shape.** The prompt assumes luxury ski homes book 4-10 months out.
Evidence is mixed:
- Commercial luxury-chalet sources say large groups book Christmas 6-12 months ahead
  [S57] (marketing, Alpine).
- Inntopia/DestiMetrics (2013, **STALE**): across 10 US mountain resorts over 5 winters,
  guests booking ~5 months out paid ~10% **above** average ADR; last-minute bookers paid
  well below [S58]. Early bookers pay more in ski lodging - consistent with a far-out
  premium, inconsistent with deep last-minute discounting as revenue-maximizing.
- Beyond's all-unit market averages (trailing 12 months, all seasons): 24-33 day lead
  times for Breckenridge, Park City and Tahoe [S19].
- **AirROI, winter 2025-26 (Dec-Mar), 14 ski markets, >24,000 listings: Winter Park average
  lead time 72 days**; range 48 (Mammoth) to 104 (Big Sky); lead times lengthened year over
  year in most markets as guests locked peak weeks earlier [S88]. All-unit and
  vendor-modelled from scraped calendars (class 7), but Winter-Park-specific, winter-only and
  current. This is the best available market booking window and supersedes the Beyond
  figure (and the `pace.py` `DEFAULT_CURVE` comment that cites it) for winter.
- First-party data (47 stays, mean lead 40.9 days, median 15) is **not informative about
  winter**. Its own source says the sample is "Mont Luxe only, mostly June-December 2026. It
  is not a winter-season sample" (`docs/research/dossiers/01_who_buys_winter_park.md`), and a
  database that starts at Guesty sync right-censors long leads. Provenance: R4 ran no query;
  dossier 01 reports portfolio-level statistics computed from reservation booking
  attributes (dates, nights, party size, channel), not guest identity fields.
- So for large homes the window is probably at least the market's ~72 days and plausibly
  longer for holiday weeks; how far out these homes' own winter weeks book is an open
  question (section 11, Q4), and the answer decides how much a far-out-premium default helps
  or hurts.
Generic defaults (PriceLabs HLP last-minute discount up to 40% inside 60 days; Wheelhouse
~30% same-day; Booking Recency Factor up to 15%) are built for urban, high-turnover inventory.
For a home whose next-best use of an empty Christmas night is nothing, a late discount is
right *if* the night will otherwise go empty, but for a 16-sleeper the relevant question is
whether a *group* will form at all inside 2 weeks; that probability is low and not very
price-elastic. A 40% discount on a $2.5k night to win a party that is not shopping is pure
leakage. Measured at our scale: no data yet.

**3.5 Holiday mechanics.** Christmas-New Year in a large home is sold as a block (e.g. 5-7
nights) with arrival-day constraints. PriceLabs can add 0-2 min-stay nights for important
holidays and supports arrival/departure-day rules only on some PMSs [S9][S48] (whether
Guesty is one of them: **UNVERIFIED**, operator question Q9). Forum reports show the
practical friction: on OwnerRez, a Saturday arrival restriction pushed to Airbnb made every
Saturday display as unavailable, with no workaround (2020, follow-up 2022; **STALE**)
[S98]; on Hostaway, a user reports PriceLabs listing-level settings overwriting holiday
blocks set in the PMS (snippet) [S99]. Vrbo's rate
automation ignores LOS entirely [S42]; Airbnb Smart Pricing prices nights. None
discloses pricing the *stay* (value of a 6-night block vs two 3-night stays plus an orphan).
Our engine has a stay-value model (M4) but it is off (section 6).

**3.6 Large-home scarcity and price discovery.** Our curated twin set is 14 Airbnb IDs;
real scrapes never quoted more than 4 of a set's comps on one day; comps within a set
differ by a median log-price SD of 0.28-0.41 (`docs/reports/anchor_rule_study/DECISION.md`).
A 350-listing HLP market or a 100-500 listing Beyond set in this valley necessarily mixes
in smaller units or other towns. Mechanism of harm: base-price and seasonality factors
estimated from a pool dominated by 2-3 bedroom condos inherit the condo market's booking
curve (shorter lead, more last-minute, more elastic), which pushes generic recommendations
for a 6-bedroom home toward earlier and deeper discounts. Wheelhouse is the exception in
design (same-bedroom-count cluster), but its cluster size in a thin valley is ND.

**3.7 Fee-inclusive display.** The FTC junk-fees rule (16 CFR Part 464, effective
2025-05-12) requires the total price including mandatory fees to be shown clearly and
prominently for short-term lodging [S59]; Airbnb has shown total prices (fees included,
before taxes) to all guests by default since April 2025 [S51]; Airbnb moved PMS-connected
hosts to a 15.5% host-only fee from 2025-10-27, so the host's listed rate now embeds the
platform fee [S60 (vendor blogs; Airbnb primary not found)]. Field evidence that fee
salience changes demand: StubHub's randomized test found upfront fees reduced both the
quantity and quality of purchases (Blake, Moshary, Sweeney, Tadelis, Marketing Science
2021) [S61]. For our homes ($600 cleaning + $75/guest + $80 insurance, typical party 10,
typical LOS 4 in `config/policies/candidates/pace_v3_anchor_repair.yaml`) fees are about
$357/night of a ~$2k nightly rate, so the guest's elasticity to the *nightly* rate is
diluted by about 15% (`src/pricing/pace.py` `all_in_beta`). PriceLabs has closed part of
this gap in 2026 (fee-isolated comp calendar, guest-price view) [S50], so fee-awareness
is *not* a durable specialist edge by itself; fee-aware **optimization** (owner net on the
all-in price) still is not disclosed by any vendor.

## 4. Known weaknesses: evidence

### 4.1 User complaints (forums)

Reddit could not be accessed (tool restriction), so forum evidence is from BiggerPockets
and the Airbnb Community Center. All anecdotal and self-selected.
- BiggerPockets "Does dynamic pricing work?" (Jan 2023, **STALE**) [S23]: an operator
  ran PriceLabs and Beyond side by side and said PriceLabs was "more static" and the tools
  "leave money on the table or keep the property empty"; another "doesn't see enough
  charged for peak times and holidays"; another saw bookings decline on PriceLabs and went
  back to manual; another objected that tools "require a manually entered base price"; one
  saw PriceLabs more than double Christmas-New Year rates while lead times shrank to 2-3
  weeks. Consensus in thread: tools are a baseline that needs manual overrides,
  especially for holidays.
- BiggerPockets threads 2019-2024 [S62 (snippets)]: PriceLabs praised for dynamic
  min-stay and flexibility; Beyond criticized for not refunding fees on cancellations;
  Wheelhouse "very slow to adopt changes".
- Airbnb Community: Smart Pricing prices "stupidly low", ignores the set minimum [S40];
  an Edinburgh Festival glitch cut Smart Prices below hosts' settings [S41].
- Comparison blogs (vendor-adjacent): Wheelhouse recommendations "can lag behind what the
  market will actually bear" when demand is obviously elevated [S63 (snippet)].

Pattern relevant to H2: the recurring complaint is **under-pricing of peak and holiday
nights** and the need for **manual holiday overrides**. That is exactly where our homes
earn most of their money (H5 claims ~70% of revenue in winter). A second pattern is
**stay-rule friction**: arrival-day restrictions that display badly on Airbnb or are
overwritten in PMS sync [S98][S99] (section 3.5).

### 4.2 Accuracy of scraped booking inference (published evaluations)

No independent, ground-truth validation of PriceLabs', Beyond's, Wheelhouse's or AirDNA's
booked-vs-blocked classification was found. What exists:
- Vendors' own caveats: PriceLabs "no method is perfect" [S1]; AirDNA "can not perfectly
  distinguish" [S24].
- AirDNA reported 95%+ agreement with Airbnb's *public aggregate* reporting (snippet,
  **UNVERIFIED**); aggregate agreement does not bound per-segment error.
- Commentary estimating an 8-10 point occupancy overstatement if half of ~20% blocked nights
  are misread as bookings [S47] - a back-of-envelope, not a measurement.
- Key Data's whole pitch is that OTA data is "skewed by owner nights, discounts" [S29];
  self-interested but mechanistically right.
- Academic users of AirDNA (e.g. Parthum and Christensen [S52]) use it as revenue truth
  without validation; it is the field's de facto standard, not a validated one.
- A single-property anecdote (vendor-adjacent blog) reports AirDNA overestimating one
  listing's revenue by ~17% (cited by the reviewer as https://magicbnb.io/blog/is-airdna-accurate;
  not opened by R4, **UNVERIFIED**).
For a 3-home operator, the practical implication: **our own Guesty data is ground truth
for our homes; comps' "occupancy" from any vendor is an estimate with unknown, probably
upward, bias**, worst for large homes that owners block for personal holidays.

**A free ground-truth test we can run.** Scrape our *own three homes'* public Airbnb
calendars daily with the same code path used for comps, run a vendor-style block inference
(available -> unavailable transitions, merged into stays, owner blocks not removed), and
score it against Guesty truth (bookings vs owner blocks vs maintenance holds). Report
precision and recall of the "booked" label, LOS error and occupancy bias. It is the only
measurable error rate for block inference on 5+ bedroom homes in this market, and it is the
validation step for edge #2. It requires per-day calendar availability to be persisted
(section 6, comp calendar row).

### 4.3 Evidence of lift (vendor claims vs independent)

| Source | Claim | Design | Conflict | Weight |
|---|---|---|---|---|
| PriceLabs [S2] | +26% RevPAR for new users in 3 months | before/after on adopters | vendor | very low (selection, mean reversion) |
| PriceLabs [S3][S4] | +9% vs old model; +9% timed LMD; +11% LMD+far-out | "experiments", no design | vendor | low |
| Wheelhouse [S12] | +22% revenue | none | vendor | very low |
| Wheelhouse [S12] | pacing A/B +0.9-1.5% building revenue | A/B | vendor | medium (small, plausible) |
| Guesty [S45] | +33% RevPAL year one | platform users, no design | vendor | very low |
| Vrbo [S42] | +38% revenue (Jan-May 2025), +39% bookings (Nov 2025-Feb 2026) | adopters vs non-adopters, two different windows | platform | very low |
| Vantory [S33] | +7-13% year one | none; dashboard "illustrative" | vendor | very low |
| DPGO [S31] | occupancy up to +90% | none | vendor | none |
| Airbnb (Ye et al.) [S37][S38] | "significant gains" for adopters; naive demand-curve revenue max "often fail[s] to optimize revenue for our hosts in practice" | online A/B | platform | medium (qualitative) |
| Zhang et al. Marketing Science 2021 [S39][S96] | Smart Pricing adopters: nightly price -5.8% (HBS summary; -5.7% in abstract snippets), daily revenue +8.6%; 2,118 properties, 7 US cities, 2015-17 | adopter vs non-adopter comparison (difference-in-differences); adoption is self-selected | independent | medium |
| Hostaway study via agency blog [S82] | dynamic vs static listings: RevPAR +25.1%, occupancy +28.6%, ADR slightly down | treatment vs static control (details not seen) | vendor, secondhand | low |
| Wang et al. Interfaces 2021 [S64] | choice-based dynamic pricing: +3.5% and +5.2% revenue per unit in two Wyndham regions (2018) | regional test | authors include the operator's staff | medium |
| Leoni and Nilsson, IJHM 2021 [S65] | hosts raising prices as the stay approaches ("surging") **lose** revenue on average; effect heterogeneous | causal forests, Ibiza panel | independent | medium |
| Gibbs et al., IJCHM 2018 [S66] | hosts use far less dynamic pricing than hotels | 39,837 listings, 5 markets | independent | context (**STALE**) |

The honest reading: there is **one independent tool-level estimate** (Zhang et al.:
+8.6% revenue for Smart Pricing adopters, earned by cutting price about 6%, from an adopter
comparison exposed to self-selection) and **one operator-co-authored field test** (Wang et
al.: +3.5% and +5.2% revenue per unit). Leoni and Nilsson measure a host *behaviour*
(surging), not a tool. Everything else is vendor-reported. The best-documented generic
tool earns its lift mostly by **cutting price and buying occupancy**. That is the opposite of
what a scarce, peak-heavy luxury home needs. No independent study measures PriceLabs,
Beyond or Wheelhouse lift, and none covers 5+ bedroom mountain homes.

### 4.4 Litigation and regulation: what shared-data pricing implies

- **DOJ v. RealPage**: proposed final judgment announced 2025-11-24 [S67][S68]. RealPage may
  not use competitors' nonpublic, competitively sensitive data at runtime; model training
  may use only nonpublic data aged >= 12 months and not from active leases; models may not
  determine geographic effects narrower than **state level**; features that limited price
  decreases or aligned competitors' prices must be removed; no market surveys of nonpublic
  data; court-appointed monitor; 7 years (per law-firm summary; not in the DOJ release)
  [S68]; no penalty, no admission. Tunney Act review
  in M.D.N.C. (entry status not verified).
- **DOJ/FTC statement of interest, Duffy v. Yardi** (2024-03-01): competitors jointly
  delegating key aspects of pricing to a common algorithm can be per se illegal even if
  they keep discretion to deviate [S69].
- **Gibson v. Cendyn** (9th Cir., 2025-08-15, No. 24-3576): affirmed dismissal; the
  hotels' individual licences of the same software were "ordinary sales contracts" that "do
  not restrain trade", were non-binding and did not require hotels to follow the
  recommendations; plaintiffs had dropped the hub-and-spoke theory; AAI sought rehearing en
  banc and plaintiffs petitioned (outcome not found) [S70][S71]. **The opinion itself was not
  read** (law-firm summaries only).
- **Cornish-Adebiyi v. Caesars Entertainment** (3d Cir., No. 24-3006, 2026-07-29):
  **reversed** dismissal of the Atlantic City casino-hotel case built on Cendyn's Rainmaker.
  Pleaded facts: hotels fed "current, non-public room-pricing and occupancy data" into the
  shared software and adopted its recommended rates about **90%** of the time; plus factors
  included acceptance even where undercutting would have paid and "de facto data exchanges"
  through the software. The court held this plausibly alleged an agreement, while saying
  that using the same independently operated software is not necessarily a violation [S89].
  With Gibson this is a **circuit split** on algorithmic-pricing Section 1 claims (the
  Covington note itself does not use the word "split"; the characterization is ours). The
  opinion itself was not read.
- **States**: Colorado HB25-1004 (ban on algorithmic rent-setting using nonpublic or shared
  data) passed and was **vetoed** by Gov. Polis on 2025-05-29 [S72]; California AB 325 prohibits use or distribution
  of a "common pricing algorithm" ingesting competitor data and lowers Cartwright Act
  pleading standards (enactment status not verified here) [S73]; 50+ algorithmic-pricing
  bills in 24 states in 2025 [S73].
- **Economics**: Assad, Clark, Ershov and Xu (JPE 2024) found algorithmic-pricing adoption
  raised German gasoline margins only in non-monopoly markets and, in duopolies/triopolies,
  only when all stations adopted - evidence that common algorithms can soften competition
  [S74].

Implications for STR pricers: (1) PriceLabs, Beyond, Wheelhouse and AirDNA mainly use
**public** scraped prices and calendars, which the RealPage settlement leaves untouched;
(2) PM-contributed **nonpublic** current reservation data (Key Data, and PriceLabs' use of
"direct data from KeyData" [S2]) is the RealPage pattern, and after Cornish-Adebiyi it is
also the fact pattern that survived a motion to dismiss in the Third Circuit; a state-level
geography rule would gut a hyper-local co-op product; (3) a pricer that sets many
competitors in one small valley to similar prices with "aligned" defaults, with
recommendations accepted most of the time, is the Yardi-statement and Cornish-Adebiyi
theory; in a valley where a few PMs may manage many of the large homes (not measured here),
that is not hypothetical. The PriceLabs-Key Data link matters to us only if we ever *adopt*
PriceLabs prices; a recommend-only shadow that we never act on is not delegation of
pricing.
For **us**: a single-operator engine that prices its own three homes from public comp
data plus its own data has essentially no shared-data exposure. That is a structural
advantage over any co-op data product, and a reason **not** to buy nonpublic PM-pooled
data. No STR-specific antitrust case was found.

## 5. Business models and incentives

| Vendor | Fee model | Fee at ~$2k/night, 1 booked night | Incentive created |
|---|---|---|---|
| PriceLabs | $19.99 for 1 listing/month (US), lower per listing at volume; 1% option UNVERIFIED [S11] | ~$0.66 at full occupancy | Neutral on price level; retention-driven; data-asset scale |
| Wheelhouse | 1% of revenue ex taxes/fees, or $19.99 flat [S15] | $20 (1%) | Flex plan paid on booked revenue |
| Beyond | 1% Pay-on-Book / 1.49% Pay-on-Stay, base incl. cleaning and extra-guest fees [S22] | $20-30 + share of fees | Paid on bookings, including ones that later cancel (credit minus fee): mild tilt to conversion |
| AirDNA Adapt | about $20/listing (reported) [S27] | ~$0.66 | Drives data subscriptions |
| Guesty PriceOptimizer | add-on; price ND [S45] | ND | Platform stickiness; occupancy raises PMS GBV fees where % based |
| Airbnb Smart Pricing | free; platform takes ~15.5% host-only fee [S60] | n/a | Paid on GBV and liquidity; evidence shows it cuts price [S39] |
| Vrbo rate automation | free; not for PMS-integrated hosts [S42] | n/a | Same as Airbnb |
| Vantory | $300/month + $35/door [S33] | n/a | "Never takes a cut" |
| DPGO | $1/booked night or 0.5% [S32] | $1-10 | Paid on bookings |

At our price level the fee *cost* is small either way (a 1% plan costs $10k per $1M of gross booked revenue; three flat
listings cost roughly $360-720 a year), so cost is not
the decision driver for a shadow benchmark; data access and write-safety are.

For comparison, the one public filing from an STR *operator* that describes its own pricing
objective is Vacasa's: "We use proprietary pricing tools to optimize homeowner income",
with algorithms released to improve "revenue per available night" (FY2024 10-K) [S94].
That is the closest public analogue to our owner-net framing, from a manager whose fee is a
share of revenue; no quantified result is disclosed.

## 6. Feature matrix

Rows are capabilities. **Y** = disclosed and in the product; **P** = partial or manual;
**N** = disclosed absent; **ND** = not disclosed; **C** (our column) = built but only in a
*candidate* policy or behind a flag that is off by default; **U** = unproven (built, never
validated on real outcomes). Sources in sections 2-5. "Our engine today" is read from the
repo on 2026-10-16 (paths given), including uncommitted work noted in the repo.

| Capability | PriceLabs | Beyond | Wheelhouse | AirDNA Adapt | Key Data | Guesty PO | Airbnb SP | Vrbo RA | **Our engine today** |
|---|---|---|---|---|---|---|---|---|---|
| Scraped comp prices | Y (Airbnb, Vrbo, Booking) | Y | Y | Y | P (OTA layer) | Y | internal | internal | **Y but fragile**: one Airbnb search sweep of the bbox (~280 listings), 14 curated twin comps; **67% of scrape rows failed** 2026-09-20..10-16; never >4 comps of a set quoted on one day (`docs/reports/anchor_rule_study/DECISION.md`) |
| Comp booking inference from calendar closures | Y (block removal) | Y | Y | Y (ML) | N (uses PMS truth) | ND | internal truth | internal truth | **N**: `providers.calendar` *fetches* per-day availability and min-nights, but `_enrich_min_nights` (`src/scrape/__init__.py`) **persists only `min_nights`**, and only onto rows the sweep wrote; `comp_snapshots.available` is set from *search-sweep presence* (absent from a search tile -> `unavailable`), which conflates booked with not-ranked or min-stay-filtered. No calendar-transition history, so no booking inference is possible yet |
| PM-contributed booked data (nonpublic) | P (via Key Data) | N/ND | N/ND | N/ND | **Y** | N | n/a | n/a | **N** (deliberate; see 4.4) |
| Own reservations / PMS truth | Y | Y | Y | Y | Y | Y | Y | Y | **Y** Guesty sync; ~100 reservations total; data spine with owner-net ledger (`src/data_spine/`) |
| Own daily pacing snapshots | Y (Portfolio Analytics) | Y | Y | Y | Y | ND | internal | internal | **Y** `pacing_snapshots`, one row per (as_of, property, stay_date); prior days are not rewritten but a same-day re-run overwrites (`ON CONFLICT ... DO UPDATE`, `src/pacing`); history only from 2026 |
| Market pacing / pickup vs prior year | Y (pacing, pickup) | Y (seasonal pacing) | Y (booking curves) | ND | Y | Y (demand pacing) | Y (search/contact rates) | ND | **N** for pickup (pace uses own portfolio only); **P** a comp *price*-movement signal (`src/signals/comp_movement.py`, run on every scrape) writes `demand_signals` from the curated comps' 14-day median listed-price lift, feeding the demand tier |
| Hotel future rates | Y | Y | Y | ND | N | ND | ND | ND | **N** |
| Search / demand-intent data | P (direct-site search insights, limited) | P ("search data") | ND | ND | N | ND | **Y** (views, search, contacts) | ND | **P** intent collector built, **disabled** (`config/policies/default.yaml` `intent.enabled: false`) |
| Base price | user-owned, helper suggests | secondary algo suggests | GBM + kriging | strategy-set | n/a | user-owned, never auto-changed | listing | user min/max | **C**: comp-anchored reference (median of per-comp latest good quote, max age 42 d, >= 3 comps) x pace (`src/pricing/pace.py`, candidate `pace_v3_anchor_repair.yaml`); default engine uses same-season ceiling + seasonal anchor |
| Seasonality | learned (reference dates) | decomposition 6+ yr | low-pass filter | ND | n/a | Y | GBM features | Y | **P**: fixed season windows and multipliers (`seasons:`); same-season 5-yr ceiling; ~1 season of real history |
| Day-of-week | Y learned | Y learned | Y learned | ND | n/a | Y | Y | ND | **P** fixed multipliers (`dow_multipliers`) |
| Events / holidays | Y auto + RM team | Y 3 detectors | Y high-pass | Y | n/a | Y auto | ND | Y holidays | **P, with a live gap**: hand list `config/policies/events.yaml` is *dated*, not recurring. It covers 2025-26 (Christmas, MLK 2026-01-16, Presidents 2026-02-13, one Spring Break window 2026-03-07..22, etc.) but for 2026-27 holds **only Christmas 2026-12-20..2027-01-04**: no MLK, Presidents or Spring Break 2027. The calendars collector falls back to this file because `calendar_signals.json` is absent |
| Elasticity / P(book given price) | Y per date x comp set | ND | Y (gamma price response) | ND | n/a | ND | Y (GBM + strategy model) | ND | **P/C**: default fixed by season (peak -0.65, linear demand); candidate learns beta with shrinkage (kappa=40) + Thompson (`docs/research/MODEL_SPEC.md` M1); **U** |
| Horizon / dynamic program | Y (Bellman) | ND | blending | ND | n/a | ND | ND | ND | **C** one-step continuation (M3), off |
| Last-minute discount | Y up to 40% in 60 d (HLP) | Y | Y ~30% same-day | ND | n/a | Y | ND | ND | **P** lead-time curve 0.90 inside 7 d (`lead_time_curves`); pace multiplier floor 0.85 |
| Far-out premium | Y up to 20% from 60 d | P | Y | ND | n/a | ND | ND | ND | **P** lead curve 1.03-1.05 beyond 60/120 d |
| Occupancy / pace adjustment | Y OBA vs market | Y health score | Y pacing | ND | n/a | Y | Y | ND | **C** pace index vs reference curve or own history (sensitivity 0.30, bounds 0.85-1.25) |
| Orphan / gap nights | Y 20% | Y | Y | ND | n/a | ND | ND | ND | **Y** gap discount 0.88 + min-stay relaxation first (`leakage.orphan_gap`) |
| Dynamic min-stay | Y (rich rules) | ND | Y | Y | n/a | Y | host | N (ignores LOS) | **Y** season x lead table + gap override (`src/min_stay`); owner-tunable, unconfirmed |
| Holiday min-stay / block pricing | P (+0-2 nights) | ND | ND | ND | n/a | P | N | N | **C** stay-value model M4, off |
| Arrival/departure-day rules | P (some PMS) | ND | Y | ND | n/a | ND | host | ND | **N** |
| Large-home (5+ BR) comp segmentation | P (bedroom-keyed, 350 set) | P (100-500 set) | Y (same bedrooms) | ND | Y (filters) | P (user groups) | P (cluster) | ND | **Y** bedrooms >= 5, sleeps >= 14 filter; hand-curated sets |
| Fee-aware comps (strip cleaning fees) | **Y (2026)** 10 comps | ND | P (fees as features) | ND | ND | ND | n/a | ND | **P** `price_basis` captured; tagging of fee-inclusive totals still open (OVERHAUL 2.10) |
| Owner-net (after channel + mgmt fee, turn cost) objective | N (revenue) | N | N | N | n/a | N | N (GBV) | N | **C** owner-net all-in objective (`owner_terms`, `all_in_beta`); **U** |
| Snowpack / snow quality | N/ND | N (manual advice) | ND | ND | n/a | ND | ND | ND | **Y/U** SQI from SNOTEL SWE, terrain, grooming, powder, ENSO -> ceiling multiplier; a **declared prior** (`curve_confidence: 0.35`), not fitted |
| Resort ops (open %, closures, wind holds) | N/ND | ND | ND | ND | n/a | ND | ND | ND | **Y** collector + `resort_ops` demotes autonomy near closures; does not move price |
| Pass blackouts (Ikon) | N/ND | ND | ND | ND | n/a | ND | ND | ND | **P** 2025-26 dates in `config/resort/winter_park.yaml` (conflicts with retailer listings; see 3.2); not a price input |
| Road access (US-40/I-70) | N/ND | ND | ND | ND | n/a | ND | P (disaster off-switch) | ND | **Y/U** CDOT collector; access risk scales beta, caps up-moves, demotes autonomy; gated at shadow status |
| Origin school calendars | N/ND | ND | ND | ND | n/a | ND | ND | ND | **N** (collector exists but has no district data file) |
| Cross-resort substitution | N/ND | ND | ND | ND | P (other markets) | ND | ND | ND | **Y/U** substitution index can cut ceiling up to 15% |
| Macro / gas / flights | N/ND | ND | ND | ND | n/a | ND | ND | ND | **P** registered at shadow / disabled |
| Twin cannibalization (own portfolio) | P (group rules) | ND | Y (unit-type pacing) | ND | n/a | ND | ND | ND | **C** M5, off |
| Guardrails / move caps | min/max, offset | min/max | min/max | approval | n/a | min/max | min/max | min/max | **Y** +12%/-15%/$250 per run, peak blackout, sanity floor, run-scope caps, autonomy from data health |
| Explanation | factor view | ND | factor attribution (10+) | AI rationale | n/a | reasons | ND | ND | **Y** reasons ranked by dollar contribution |
| Recommend-only / shadow mode | P (sync off) | ND | Y (Simulation endpoint) | Y (approval) | n/a | ND | N | N | **Y** `src/shadow` (no PMS client, rate_writes constrained to 0) |
| Offline simulator / benchmark | N (internal) | N | N | N | n/a | N | internal | internal | **Y** proving ground, calibration v2 (validated to booked ADR bands), `current_practice` benchmark; a stylised generalized-tool *competitor* (`tool_price`: x0.92 inside 14 d, x0.90 below 40% occupancy, x0.90 in a price war, x1.20 holidays, no far-out premium) that matches **neither** PriceLabs vintage |
| Measured lift on real outcomes | vendor-claimed | vendor | vendor (A/B +0.9-1.5%) | none | n/a | vendor | independent +8.6% revenue | vendor | **None**: candidate screened at -6.6% vs current practice (v2 sim, 5 seeds, 2026-10-14 version); V3 unscreened; field MDE ~33% without variance reduction |

*Added 2026-10-19 (close-out):* PriceLabs' "Y (rich rules)" for dynamic min-stay understates it. Its
Minimum Stay Recommendation Engine (announced 2023-09-11) trades the "guaranteed revenue" of a short
booking against the lower booking probability of neighbouring dates, counts check-in and check-out
costs, and lengthens minimum stays far out and shortens them close in
(https://hello.pricelabs.co/minimum-stay-recommendation-engine/). That is a stay-level
opportunity-cost rule. The specialist edge on stays is therefore owner-net economics for 14-to-18-guest
parties, not having stay-level logic at all (S1 §4.4).

**Honest summary of our column.** We are ahead on *mountain-specific inputs* (SQI, resort
ops, CDOT, substitution, ops layer), on *safety and explanation*, and on *owner-net
framing*. We are behind on everything that needs **data volume**: market pickup, booking
inference on comps, learned seasonality and day-of-week, per-date elasticity, hotel and
search signals. Most of our differentiators are **C** or **U**: built, off or unproven. The
one comp input everything rests on fails on two of three scrape rows.

## 7. H2 verdict: what generic STR pricers miss (and what they do not)

H2 says generic pricers "do not collect the data that moves this market and weight the
wrong factors". Evidence, split:

**Supported.**
1. *No vendor discloses snow, resort operations, pass products, road closures or origin
   school calendars as inputs* (section 3 table). They capture these only indirectly through
   pace and pickup once bookings move. Snow does move STR revenue near ski resorts (elasticity
   0.22 national, 0.135 Colorado, higher for bigger homes) [S52], and 2025-26 showed the size
   of the shock: Colorado skier visits fell about 24% (10.5M vs 13.9M) in one of the worst
   snowpacks in 50 years, the lowest since 1991-92, with resorts open 129 days against a
   20-year average of 144 (Colorado Ski Country USA figures [S91]); Mary Jane closed seven
   weeks early [S76]; Vail Resorts' own 10-K says guests "tend to delay or postpone
   vacations if conditions differ from those that are typical" [S93].
2. *Comp sets are too coarse for 5+ bedroom homes in a thin valley* (350 / 100-500 listing
   sets vs ~14 true peers) [S3][S18]; Wheelhouse's same-bedroom cluster is the exception.
3. *Default factor stacks are urban-calibrated*: up to 40% last-minute discounts within 60
   days, 40%-occupancy-equals-par, 30% same-day [S6][S12]. The STR evidence on late price
   moves is mixed (Leoni and Nilsson find surging hurts [S65]; DestiMetrics found early
   ski bookers pay ~10% more [S58]).
4. *Their booked-price data are inferred listed prices with block contamination*, worst
   where owners block peak weeks [S1][S24].
5. *Their objective is revenue (or GBV), not owner net*, and percent-of-booking fees tilt
   toward conversion [S22]; the one independently measured generic tool lifts revenue by
   cutting price [S39]. Users complain specifically about under-pricing holidays [S23].

**Not supported, or weaker than claimed.**
1. Generic tools are *not* naive multiplier stacks. PriceLabs estimates per-date elasticity
   and solves a horizon DP [S3][S4]; Wheelhouse fits survival booking curves and a price
   response [S12]; Airbnb's system uses a GBM and a learned strategy layer [S38]. Their
   modelling is ahead of our default engine.
2. Pace and pickup partly absorb snow and school effects with a lag. With a winter
   booking window of ~72 days in Winter Park [S88], much of a season's demand is booked
   before the snowpack is known, so the lag is *long* for most nights. That supports a snow
   edge in principle; but the size is small (about -7% revenue for a 60%-of-normal year at
   Colorado's elasticity [S52]) and in 2025-26 it showed up in occupancy, not ADR [S88]. Our
   own SQI prior is about three times that size and acts on price (3.1a), so as built it is
   as likely to lose money as to make it.
3. Fee-awareness is no longer unique: PriceLabs shipped fee-isolated comp calendars and
   guest-price views in 2026 [S50].
4. "Picking the right factors" (H3) cuts against us too: with ~100 reservations we cannot
   *fit* most of our extra factors; the SQI curve is a declared prior. An extra input
   only helps if its weight is right, and we cannot yet show that.

**Verdict.** H2 is **partly supported**: generics omit mountain-specific drivers and
mis-segment large homes, and that is plausibly costly on **peak and holiday nights of
large homes**, where most of our revenue sits. H2 is **not supported** in its strong form
that generics are unsophisticated; on modelling and data volume they are ahead of us. The
specialist edge is therefore narrow and specific (section 8), and nothing yet shows that
our engine captures it: our own candidate trails the homes' current rate card in
simulation.

## 8. Specialist edges we could credibly own (ranked)

Ranking = expected owner-net impact x probability we can prove it, given 3 homes.
"Prove vs PriceLabs" means against a PriceLabs-style arm (section 9) on the same nights.

| # | Edge | Why generics cannot easily copy it | Data needed | How to prove it vs a PriceLabs baseline |
|---|---|---|---|---|
| 1 | **Peak/holiday large-home ceiling discovery**: price Christmas-New Year, MLK, Presidents and spring-break weeks of 16-sleepers from true peers (5+ BR, sleeps 14+) and our own sell-through, not a 350-listing pool | Their pricing market is defined by count and radius for millions of listings; a hand-built, verified peer set for ~15 homes is uneconomic for them | Reliable comp scrape of the 14-20 true peers daily (fix the 67% failure rate first), our pacing snapshots, peer calendar closures | Proving ground: add a `pricelabs_hlp` *policy* arm (section 9) and compare owner net on holiday spans over 25 held-out seeds; field: shadow-log PriceLabs' recommended price for the same nights and score both against realized peer closes and our own bookings ("booking regret" and "price-decrease recall" metrics from Ye et al. [S38]) |
| 2 | **Block-aware peer pickup**: infer peer bookings from calendar closures *for 15-20 homes we know by name*, cleaning owner blocks by hand-maintained knowledge and min-stay patterns | Generics need automated block removal at scale and admit errors [S1]; we can audit 20 calendars | **Persisted** per-day peer calendar availability (fetched today but not stored; a code change), a small labelled set of known owner blocks | First validate the inference on **our own three homes** (public calendar vs Guesty truth: precision/recall of the booked label, occupancy bias; 4.2); then test whether peer pickup predicts our own bookings (IC on the promotion ladder, `config/policies/signals.yaml`) better than PriceLabs' market OBA would |
| 3 | **Snow-conditional first-wave pricing**: SQI (SNOTEL SWE + ENSO prior) shifts the *ceiling and the early-season reference*, not close-in discounts | No generic discloses snow inputs; they wait for pace | SNOTEL, Open-Meteo, resort terrain (collected), multi-season own and peer history | First fix the prior's size (3.1a, rec 8). Then backtest in the proving ground (`scenarios/drought.yaml`, `record_snow.yaml`) with snow-driven demand calibrated to Parthum-Christensen elasticities [S52] and the 2025-26 Winter Park occupancy-not-ADR pattern [S88]; field: SQI must clear the promotion ladder (IC >= 0.05, hit rate >= 0.52); report the owner-net change on nights where SQI moved price |
| 4 | **Stay-block and arrival-rule optimization for holidays** (M4 + arrival-day rules + gap control) | Generic tools price nights; LOS rules are user-set; Vrbo ignores LOS [S42] | Own inquiry/booking LOS mix, holiday arrival-day patterns of peers (calendar data) | Proving ground: owner net per holiday span with M4 on vs off and vs PriceLabs' +0-2-night rule; field: share of holiday nights sold in full blocks and orphan nights left |
| 5 | **Owner-net objective on the all-in price** | Generic tools optimize revenue or GBV; owner net needs the operator's fee schedule and turn costs | Fee schedule (have), turn cost (assumed $350, needs the real figure), channel mix | Score every arm on owner net in the sim (already wired); in the field, compute owner net per night from the data spine |
| 6 | **Event and access calendar of record**: verified origin-district school calendars, Ikon blackouts (diversion to or from Winter Park, depending on whether Winter Park shares them; unresolved, 3.2), Berthoud closure risk | Needs local curation each year | District calendars (DPS, Jeffco, Cherry Creek, Houston, Dallas, Austin ISDs), Ikon list, CDOT feed | Promotion-ladder IC on bookings; proving-ground scenario where calendars shift a week |
| 7 | **No shared nonpublic data** (antitrust-clean by construction) | Co-op products are built on pooled data that RealPage-style rules target [S68][S73] | none | Not a profit edge; a durability edge to keep |

Edges we should **not** claim: modelling sophistication, data scale, market-wide pickup,
learned seasonality from one season, or fee-isolated comps (generic now has it).

## 9. Shadow benchmark arm: recommendation

**Recommendation: yes, run a PriceLabs arm, in two forms, starting with the cheap one.**

1. **Proving ground (now, no cost).** Promote the generalized tool from a competitor agent
   to a *policy* that can price our homes, and update it to PriceLabs' current published
   HLP defaults: last-minute discount up to 40% within 60 days, far-out premium up to 20%
   from 60 days, OBA vs market within 60 days (discount cap 20%, premium cap 15%), orphan
   20% off gaps <= 2 nights, booking-recency factor 5-15%, safety minimum at prior-year
   ADR on dates that booked last year, min-stay rules of [S9] [S6][S7]. Today's emulator
   (`proving_ground_exam/market/competitors.py` `tool_price`) is a stylised competitor that
   matches neither PriceLabs vintage (x0.92 flat inside 14 days, x0.90 below 40% occupancy,
   x0.90 in a price war, x1.20 holidays, no far-out premium; PriceLabs' *old* default was a
   gradual 30% over 15 days plus a 20% far-out premium [S6]). So this is a **rewrite as a
   new policy**, not a parameter change. Base price for the arm = the homes' current rate card
   average (what a PriceLabs user would enter). Score against `current_practice` and our
   candidate on owner net over the 25 held-out seeds. Caveat: an emulator of public
   documentation is a *lower bound* on PriceLabs (it lacks their learned per-date
   elasticity and market data), so a win against it is necessary, not sufficient.
2. **Field shadow (after a write-safety check).** Connect PriceLabs to Guesty with **Sync
   Prices off** and record its recommended calendar daily. Facts: a 30-day free trial with
   no card [S77][S11]; thereafter $19.99 for one listing, with lower per-listing prices at
   volume ($9.99 each at 5 listings; the 3-listing price is not stated), so roughly
   **$30-60/month (~$360-720/year)** for three homes [S11]; PriceLabs shows recommended prices after import and syncs only when Sync
   Prices / Sync Now is used [S78]; but the Customer API serves prices only for listings
   "actively syncing" [S79], so capture would be via the UI/export, not the API
   (**UNVERIFIED** whether an export exists for non-syncing listings). Risks: an accidental
   sync would write rates to Guesty, violating our zero-write rule; Guesty warns to
   deactivate other pricing tools before PriceOptimizer (Guesty help snippet [S78]). The
   PriceLabs-Guesty link is a marketplace integration that PriceLabs establishes, so a
   "scoped token we mint" may not exist. Mitigations: (a) a **Guesty-side daily rate diff**:
   pull every listed rate from Guesty each morning and alert on any change not made through
   our own approved path; our shadow module's `guesty_write_count` sees only writes made by
   our code and **cannot detect a write PriceLabs makes directly to Guesty**; (b) a fallback
   to check: add the homes to PriceLabs as *unconnected* listings with no PMS link, if
   PriceLabs supports that (**UNVERIFIED**), and accept UI-only capture; (c) ask whether
   PriceLabs stay restrictions are supported for Guesty (Q9), which matters if the arm is
   ever allowed to write.
   Guesty PriceOptimizer (14-day trial [S78]) and AirDNA Adapt (approval-gated [S26]) are
   alternative or additional arms.

What the shadow measures: for each night, PriceLabs' price vs ours vs the listed rate,
then realized outcome. With three homes, the field shadow cannot measure *lift* (no
counterfactual bookings at PriceLabs' price), but it can measure (a) direction and size
of disagreement by night type (holiday, peak weekend, shoulder), (b) "booking regret"
on nights we sold below PriceLabs and "price-decrease recall" on nights that went unsold
(Airbnb's metrics [S38]), and (c) whether PriceLabs' late discounts would have hit nights
that later sold at full price. That is enough to see whether edge #1 exists before
spending on a real field test.

## 10. Ranked recommendations

| Rank | Recommendation | Module | Expected impact (owner net) | Confidence | Effort | Data needed | Measurement |
|---|---|---|---|---|---|---|---|
| 1 | Fix comp scrape reliability for the 14-20 true peers before any edge work (per-listing calendar + PDP fetches for named peers, proxy rotation, retry; or a licensed feed for exactly those IDs) | `src/scrape`, `src/comps` | Enabling: every edge in section 8 needs it; today ~3% of Northwoods nights get an anchor | High | M | none new | anchored-night share per home per day; target >= 80% |
| 2 | Add a `pricelabs_hlp` policy arm with current published defaults to the proving ground (a rewrite: the existing `tool_price` is a stylised competitor, not either PriceLabs vintage) | `proving_ground_exam/market/competitors.py`, policies | Tells us whether our candidate beats a realistic generic, not only the rate card | High (that it is informative) | M | public docs (done) | owner net vs arm, 25 held-out seeds, paired |
| 3 | Field shadow of PriceLabs with Sync off (30-day trial, then ~$60/month) once write-safety is verified | `src/shadow`, ops | Information only; cheap test of edge #1 | Medium | S | Guesty token scoping answer | disagreement by night type; booking regret; price-decrease recall |
| 4 | Peak/holiday large-home ceiling from true peers + own sell-through (edge #1), replacing reliance on a sparse median | `src/ceiling`, `src/pricing/pace.py` | Largest single lever: holiday weeks are where sim shows the candidate losing (peak ADR $2,052 vs $2,246 for current practice in the 2026-10-14 screen) | Medium | M | rec 1 | holiday-span owner net in sim; field shadow vs PriceLabs |
| 5 | Block-aware peer pickup from comp calendars (edge #2). **Prerequisite:** persist per-day calendar availability from `providers.calendar` (today only `min_nights` is stored); then validate on our own three homes against Guesty truth | `src/scrape`, `src/comps`, `src/signals` (new collector) | Gives us the market pace generics have and we lack | Medium | M | persisted peer calendars, owner-block labels | own-homes precision/recall and occupancy bias; then IC of peer pickup on own bookings; promotion ladder |
| 6 | Turn on M4 stay pricing + add arrival-day rules for holiday spans, sim-first | `src/min_stay`, `src/compose` | Holiday block value; avoids orphan nights in peak | Medium-low | M | holiday LOS mix | sim owner net on holiday spans; orphan nights left |
| 7 | Do **not** copy generic last-minute defaults; keep late discounts bounded (floor 0.85) and condition them on group-formation probability | `src/pricing/pace.py` | Avoids leakage on peak nights | Medium | S | lead-time-by-party-size data | sim: share of nights sold below 90% of reference inside 14 days that would have sold anyway |
| 8 | **Flatten or cap the SQI price curve now** (e.g. no knot below ~0.93 until fitted, matching the ~-7% revenue that Colorado's 0.135 elasticity implies for a 60%-of-normal year, and consider moving SQI into pace *norms* rather than price); fit weights only when >= 2-3 seasons exist | `config/policies/conditions.yaml`, `src/signals/features/sqi.py`, `src/ceiling` | Avoids a possible ~15-point over-cut on drought nights; snow edge later | Medium (the direction), low (the size) | S | multi-season history | proving ground `scenarios/drought.yaml` and `normal.yaml`: owner net on drought nights with the current curve vs flattened vs off; promotion-ladder IC; dollar-contribution reason |
| 9 | **Urgent part first:** add the missing 2026-27 events (MLK 2027, Presidents 2027, Spring Break 2027) to `events.yaml`, which today holds only Christmas for 2026-27; then verified origin school calendars and Ikon dates as event inputs | `config/policies/events.yaml`, `src/signals/collectors/calendars.py` | Prevents mis-tiering this season's peak weekends; corrects week-shifted spring breaks | High (the gap is real) | S | district calendars yearly, Ikon confirmation | events present for every 2026-27 holiday; IC on booking pickup in break weeks |
| 10 | Refuse nonpublic PM-pooled data (Key Data co-op style) for pricing; buy only aggregates if needed for benchmarking | policy | Avoids antitrust exposure (4.4) | High | none | none | n/a |

## 11. Open questions for the operator

1. Can Guesty issue an API token without rate-write scope, so a PriceLabs (or AirDNA Adapt)
   shadow cannot write prices? Who holds the Guesty admin role?
2. Would you accept ~$60/month for a PriceLabs shadow after the free trial?
3. For the 14 twin peers and the Cloud 9 set: which do you know to be owner-used at
   Christmas (owner blocks), so peer pickup can be cleaned?
4. How far out did Christmas 2025 and 2026 weeks book for these homes, and was anything
   held back (owner use, not yet opened)? The only first-party lead-time sample we have is
   mostly June-December and says nothing about winter; the market figure is ~72 days [S88].
5. What is the real cleaning/turn cost per stay (the model assumes $350)?
6. Does the local PM from the call use PriceLabs/Beyond, and with which overrides on
   holidays? Their override list is a free map of where generic defaults fail here.
7. Any arrival-day rules (e.g. Saturday-to-Saturday at Christmas) you want enforced?
8. Ikon: does Winter Park share the 2026-27 Base Pass blackouts (Dec 26-30, Jan 16-17,
   Feb 13-14)? Ikon's page, retailer listings and our `config/resort/winter_park.yaml`
   disagree (3.2).
9. Does PriceLabs support stay restrictions (check-in/out days) for Guesty-connected
   listings, and would you ever let a benchmark arm write?

## 12. Mechanisms and transferability (what survives at 3 homes)

### 12.1 The generic mechanism in one model, and where it breaks

Every generic tool above reduces to the single-unit perishable-inventory problem: one
night, a deadline, a booking intensity lambda(p, t) that depends on price and time to the
stay. The canonical result (Gallego and van Ryzin, "Optimal dynamic pricing of inventories
with stochastic demand over finite horizons", *Management Science* 40(8), 1994; and
Talluri and van Ryzin, *The Theory and Practice of Revenue Management*, Springer, 2004,
ch. 5) is that with a stationary demand rate the optimal price of the last unit **falls as
the deadline approaches**, because the option value of waiting shrinks. PriceLabs'
Bellman example [S4] and every "last-minute discount" default are this result.

It breaks when the demand rate is **not stationary in lead time**:
- If high-WTP customers arrive early and late arrivals are price-sensitive leisure
  bookers, the optimal path can be flat or even rising until late (airline-style). The
  DestiMetrics finding that ski guests booking ~5 months out paid ~10% above average [S58]
  says ski lodging is closer to this case.
- If the late arrival rate for *this product* is near zero regardless of price (a
  16-person group rarely forms inside two weeks), the late discount buys little and costs
  the full margin on any booking that would have happened anyway.
- If the "inventory" is a multi-night **block** (holiday week), pricing nights
  independently destroys value through orphan nights; the right unit is the stay (Phillips,
  *Pricing and Revenue Optimization*, Stanford University Press, 2005; 2nd ed. 2021,
  chapters on capacity and multi-period pricing), which is what M4 and arrival-day rules
  approximate.

The price-response function matters too: Phillips shows that a constant-elasticity
response gives a corner solution for a single seller, which is why our doctrine uses a
linear response with a real interior optimum (`docs/rules/PRICING_DOCTRINE.md`), and why
Airbnb found naive demand-curve maximization fragile online [S38]. Wheelhouse's
asymmetric response (prices rise steeply above par, fall only slightly below [S12]) and
Airbnb's bounded strategy layer are both practical answers to the same fragility; our
move caps and deference rule are ours.

Implementable first version for us (a summary, already partly in code): objective
`max_p P(book | p, lead, season, pace) * owner_share(p) + fee_margin`, with
`P(book|p) = p_ref * (1 + beta_allin * (p - p_ref) / p_ref)` linear around the comp-anchored
reference (`src/pricing/pace.py`), beta learned with shrinkage (M1), the pace index
`(on_books + 0.05) / (expected + 0.05)` moving `p_ref` by `1 + 0.30 * (index - 1)` within
[0.85, 1.25]; decision rule = grid argmax within guardrails. What generic tools add that
we do not: market pickup as a demand input (we have only a comp *price*-movement signal,
`src/signals/comp_movement.py`, which feeds the demand tier), and a horizon DP. What we add:
owner-net objective, all-in elasticity, mountain priors.

### 12.2 Transferability of generic methods to our setting

| Generic method | Survives at 3 homes, ~100 reservations? | Why |
|---|---|---|
| Per-date elasticity per comp set (PriceLabs) | **No** as estimation; **yes** as borrowed prior | Needs thousands of listing-nights per comp set; we have tens per season. Use generic-scale literature as a prior and shrink |
| Survival booking curves (Wheelhouse) | **Partly** | Kaplan-Meier on our own ~100 stays is noisy; on 15-20 peers' inferred bookings it becomes usable within a season |
| Market pacing / pickup | **Yes, if** peer calendars are scraped reliably | Small N of peers is fine for a market-level index if each is observed daily |
| Learned seasonality / DOW | **No** for now | One season; keep fixed priors |
| Event detection from forward-occupancy jumps | **Partly** | Works with 15-20 peers for big events; noisy for small ones |
| Orphan/gap logic, min-stay rules | **Yes** | Rule-based, little data needed |
| Last-minute discount defaults | **No** (wrong mechanism, see 12.1) | Large-group late demand is thin |
| Far-out premium | **Yes, cautiously** | Consistent with early-booker premium in ski [S58] and a ~72-day Winter Park winter window with lead times lengthening [S88]; how far out *our* winter weeks book is unknown (Q4) |
| Bandit / Thompson exploration | **Yes, gated** | Approval-gated bandits warm-started from history cut cold start from ~150 to ~30 episodes, for the HF-TS agent family, on one anonymised *urban* 2-room operator with 1,461 nightly episodes (arXiv preprint, abstract only) [S80]; our M1 Thompson draw and approval gate fit this pattern |
| Airbnb-style bounded strategy layer and its metrics | **Yes** | Booking regret and price-decrease recall can be computed on our nights now |
| Choice-model pricing across own units (Wang et al. [S64]) | **Partly** | Two twins plus Cloud 9 is a tiny choice set; M5 cannibalization is the right-sized version |

Small inventory, group guests, long stays, high prices and all-in display each push the
same way: fewer, larger, earlier-decided purchases, so less information per day and a
higher cost per pricing error. That favours priors, guardrails and human approval over
fully learned generic machinery - our current architecture - but it also means we cannot
*prove* small edges in the field (MDE ~33% at 60 weeks per arm without variance reduction, per the
2026-10-16 field-test design in `docs/field_test/`). The proving ground is the only place edges of 3-10% can be detected.

## 13. Adversarial pass: what contradicts this dossier

1. *Generic tools may capture part of the snow effect via pace.* Parthum and Christensen
   find elasticities of 0.124-0.152 in cumulative subsamples of bookings made within 2, 5, 7
   and 10 days of the stay [S52], so some snow response is late and pace can see it.
   Colorado's elasticity (0.135) is at the low end of their state range (0.075 Connecticut
   to 2.512 Tennessee). But with a ~72-day Winter Park winter window [S88], most bookings
   precede the snow signal, so this argument now limits the edge less than the first draft
   said. Its size, not its existence, is the issue (3.1a).
2. *Lodging rates are sticky, or rise, in bad snow years.* Inntopia reported mountain
   lodging ADR holding while occupancy fell in recent weak-snow periods [S81 (snippet;
   season unclear)], and AirROI reports Winter Park winter 2025-26 ADR **+22.2%** with
   occupancy down from 44.9% to 35.8% and supply +9.9% [S88]. If the market holds or raises
   rate in a drought, a specialist cutting price on low SQI may simply give money away; SQI
   should probably move *occupancy expectations* (pace norms) more than price. This is the
   strongest argument against our live SQI curve (3.1a, rec 8).
3. *Dynamic pricing evidence is mostly about occupancy.* A Hostaway study reported via an
   agency blog found +25.1% RevPAR and +28.6% occupancy with ADR slightly down for dynamic
   vs static listings [S82 (secondhand, vendor)]; Zhang et al. find price about -6%, revenue
   +8.6% [S39][S96]. Generic tools may beat a static rate card mostly by filling shoulder
   nights, which our homes also need. Our engine's simulated gains have also come off-peak
   (early winter +$3.1k, spring +$2.2k, 2026-10-14 screen), not at peak.
4. *Large homes may be less mis-segmented than claimed.* Wheelhouse's base model ranks
   bedrooms and sleeps as top features and clusters by bedroom count [S12][S13]; PriceLabs
   lets users fix bedroom count [S10]. We have no direct evidence that their Winter Park
   recommendations for 5+ BR homes are wrong; only mechanism and user complaints.
5. *Supply is flexible at peaks.* Farronato and Fradkin (AER 2022, doi:10.1257/aer.20180260)
   show peer supply expands when hotels fill (e.g. New Year's Eve) [S83], which caps peak
   prices. A ceiling-discovery edge has a natural limit when more large homes list for
   Christmas.
6. *A PM-data vendor's pacing missed the drought.* Key Data's Summit County outlook
   (2025-10-16, from 85+ local PMs' first-party reservations) showed 2025-26 on-the-books
   ADR at $521, +2% YoY, with booking windows 1-5% longer [S97] - weeks before the
   worst Colorado snow season in decades. On-the-books pace is not a snow forecast, for
   generics *or* for us; it argues for a snow prior, but also shows how little early pace
   tells anyone about the season.
7. *Lead times may be long enough that far-out pricing matters more, not less.* Earlier
   drafts used a mostly summer/fall first-party sample (median 15 days) to argue the
   opposite; that sample is not informative about winter (3.4). The market window is ~72
   days and lengthening [S88].

None of these reverses the verdict in section 7. Items 2 and 3 say the snow edge is
mostly about *occupancy expectations and early-wave ceilings*, not price cuts, and that our
current SQI curve is probably too strong; items 1 and 7 say the edge exists because most
winter demand books early. The first effort still goes to scrape reliability and peak
large-home ceilings.

## 14. References

All accessed 2026-10-16. Class: 1 academic, 2 textbook, 3 vendor docs / patents, 6
government / official, 7 practitioner, trade press, forums, law-firm analysis.
"(snippet)" = only the search-result text was available (403/404/429 or paywall).

| ID | Class | Source |
|---|---|---|
| S1 | 3 | PriceLabs, "Market Dashboard Methodology: Data Sources and Processing", https://help.pricelabs.co/portal/en/kb/articles/market-dashboard-methodology-data-sources-and-processing |
| S2 | 3 | G. Lamba, "Discover the Science Behind PriceLabs Data", PriceLabs blog, updated 2023-12-06, https://hello.pricelabs.co/science-behind-pricelabs-data/ |
| S3 | 3 | R. Khandelwal, "Overview of PriceLabs' Dynamic Pricing Algorithm (Part 1)", 2023-09-11 (STALE), https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/ |
| S4 | 3 | R. Khandelwal, "... (Part 2)", 2023-09-14 (STALE), https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-2/ |
| S5 | 3 | PriceLabs, "How is pricing calculated", https://help.pricelabs.co/portal/kb/articles/how-is-pricing-calculated |
| S6 | 3 | PriceLabs, "Default Discounts and Premiums", https://help.pricelabs.co/portal/kb/articles/default-discounts-and-premiums |
| S7 | 3 | PriceLabs, "Occupancy Based Adjustments", https://help.pricelabs.co/portal/en/kb/articles/occupancy-based-adjustments |
| S8 | 3 | PriceLabs, "How PriceLabs Handles Event Pricing?", https://help.pricelabs.co/portal/en/kb/articles/how-pricelabs-handles-event-pricing |
| S9 | 3 | PriceLabs, "Understanding min nights", https://help.pricelabs.co/portal/en/kb/articles/understanding-min-nights |
| S10 | 3 | PriceLabs, "How to set bedroom count?" (snippet), https://help.pricelabs.co/portal/en/kb/articles/how-to-edit-the-listing-bedroom-count |
| S11 | 7 | J. Rakidzich, "PriceLabs Cost in 2026" (snippet), https://www.rakidzich.com/articles/how-much-does-pricelabs-cost-2026 ; Capterra PriceLabs pricing (snippet), https://www.capterra.com/p/158348/PriceLabs/pricing/ |
| S12 | 3 | Wheelhouse Research, "Complete overview of the Wheelhouse Pricing Engine", updated 2023-05-01 (STALE), https://usewheelhouse.com/research-pricing-engine |
| S13 | 3 | Wheelhouse RM API, "Neighborhood Data", https://docs.usewheelhouse.com/rm/reference/neighborhood-data |
| S14 | 3 | Wheelhouse changelog, "Introducing Wheelhouse RM APIs", https://feedback.usewheelhouse.com/changelog/introducing-wheelhouse-rm-apis |
| S15 | 3 | Wheelhouse, "Plans & Pricing", https://usewheelhouse.com/pricing |
| S16 | 3 | Wheelhouse help, "How do I adjust demand sensitivity" (snippet), https://help.usewheelhouse.com/en/articles/7991884-how-do-i-adjust-demand-sensitivity |
| S17 | 3 | Wheelhouse help, "Aggressive, recommended and conservative strategy" (snippet), https://help.usewheelhouse.com/en/articles/1182583-what-s-the-difference-between-aggressive-recommended-and-conservative-strategy |
| S18 | 3 | J. Breece, "How Beyond's dynamic pricing algorithm works for you", Beyond blog (stamped 2026-10-06; content likely ~2021), https://beyondpricing.com/blog/how-beyonds-dynamic-pricing-algorithm-works-for-you |
| S19 | 3 | Beyond, "Winter is coming: what ski town STR managers should know", https://beyondpricing.com/blog/winter-is-coming-what-ski-town-short-term-rental-managers-should-know-before-the-snow-hits |
| S20 | 3 | Beyond, "Got a luxury or unique vacation rental?", https://beyondpricing.com/blog/got-a-luxury-or-unique-vacation-rental-dynamic-pricing-from-beyond-can-price-that |
| S21 | 3 | Beyond, "Dynamic pricing and automated base price setting webinar recap" (snippet), https://beyondpricing.com/blog/dynamic-pricing-and-automated-base-price-setting-webinar-recap |
| S22 | 7 | J. Rakidzich, "Beyond Pricing Cost 2026", 2026-09-07, https://www.rakidzich.com/articles/how-much-does-beyond-pricing-cost-2026 |
| S23 | 7 | BiggerPockets forum, "Does dynamic pricing work?", Jan 2023, https://www.biggerpockets.com/forums/530/topics/1088168-does-dynamic-pricing-work |
| S24 | 3 | AirDNA enterprise help, "Property Performance Data", https://enterprise-help.airdna.co/en/articles/8185673-property-performance-data |
| S25 | 3 | AirDNA help, "How does AirDNA's Smart Rates work" (404; snippet), https://help.airdna.co/en/articles/8062167-how-does-airdna-s-smart-rates-work |
| S26 | 3 | AirDNA press release, "AirDNA launches Adapt", 2026-09-01 (republished), https://www.easternprogress.com/airdna-launches-adapt-the-ai-native-revenue-management-system-for-short-term-rental-operators/article_7909c2c5-6473-5abf-8bf0-6135f7d047e3.html |
| S27 | 7 | Skift, "AirDNA enters revenue management market...", 2026-09-01, https://skift.com/es/2026/09/01/airdna-enters-revenue-management-market-with-host-dynamic-pricing-tool-exclusive/ |
| S28 | 3 | KeyData, "ProData for Property Managers", https://www.keydata.co/products/prodata |
| S29 | 3 | KeyData home page and blog (snippets), https://www.keydatadashboard.com/ |
| S30 | 3 | KeyData, "Average booking windows increase as Colorado markets prepare for winter season" (stamped 2026-09-18, COVID-era text; STALE), https://www.keydata.co/blog/average-booking-windows-increase-as-colorado-markets-prepare-for-winter-season |
| S31 | 7 | Capterra, DPGO listing and reviews, https://www.capterra.ca/software/213950/dpgo |
| S32 | 7 | BNBCalc, "DPGO review" (snippet), https://bnbcalc.com/reviews/dpgo-review |
| S33 | 3 | Vantory home page, https://vantory.ai/ |
| S34 | 3 | Duetto press release (HITEC 2024), https://www.hotel-online.com/press_releases/release/duetto-launches-comprehensive-full-service-revenue-solution-at-hitec/ |
| S35 | 3 | Duetto success story, Pierre & Vacances / Center Parcs, https://www.duettocloud.com/en-us/success-stories/pvcp-turning-modern-revenue-tech-into-measurable-tourism-growth-duetto |
| S36 | 3 | Airbnb Help Center, "Smart Pricing" (article 1168), https://www.airbnb.com/help/article/1168 |
| S37 | 1 | P. Ye, J. Qian, J. Chen, C.-H. Wu, Y. Zhou, S. De Mars, F. Yang, L. Zhang, "Customized Regression Model for Airbnb Dynamic Pricing", KDD 2018, doi:10.1145/3219819.3219830; abstract page https://www.kdd.org/kdd2018/accepted-papers/view/customized-regression-model-for-airbnb-dynamic-pricing (full PDF not read: ACM returned 403 on three attempts, including the KDD "Download Full Paper" link; claims about the online A/B failure rest on the paper text as quoted in S38) |
| S38 | 7 | A. Colyer, The Morning Paper summary of S37, https://blog.acolyer.org/2018//03/customized-regression-model-for-airbnb-dynamic-pricing/ |
| S39 | 1 | S. Zhang, N. Mehta, P. V. Singh, K. Srinivasan, "Can an AI Algorithm Mitigate Racial Economic Inequality? An Analysis in the Context of Airbnb", Marketing Science (2021); SSRN abstract https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3770371 (403 to R4; -5.7% / +8.6% seen only in search snippets of the abstract and INFORMS release); CMU summary https://www.cmu.edu/tepper/news/stories/2021/april/airbnb-racial-disparities.html (context only: it does **not** contain the price/revenue figures). Paper itself not read |
| S40 | 7 | Airbtics, "Airbnb smart pricing too low", https://airbtics.com/airbnb-smart-pricing-too-low/ ; Airbnb Community thread, https://community.withairbnb.com/t5/Community-cafe/smart-pricing-not-working/m-p/1265639 |
| S41 | 7 | Edinburgh Evening News, "Edinburgh Airbnb hosts lost out on hundreds after glitch...", https://www.edinburghnews.scotsman.com/news/people/edinburgh-airbnb-hosts-lost-out-on-hundreds-after-glitch-lowered-prices-for-festival-rentals-69880 |
| S42 | 3 | Expedia Group Partner blog, "Vacation rental rate automation with Vrbo", 2025-04-10, updated 2025-12-05, https://partner.expediagroup.com/en-us/resources/blog/vacation-rental-rate-automation-with-vrbo |
| S43 | 3 | Vrbo Help, "Set up rate automation" (snippet), https://help.vrbo.com/articles/Set-up-rate-automation |
| S44 | 3 | Forbytes, "Dynamic Pricing Engine for Guesty" case study, https://forbytes.com/case-studies/guesty-price-engine/ |
| S45 | 3 | Guesty, "Guesty PriceOptimizer", https://www.guesty.com/features/guesty-priceoptimizer/ |
| S46 | 3 | Guesty Help, "Adjusting pricing based on demand with Guesty PriceOptimizer" (403; snippet), https://help.guesty.com/hc/en-gb/articles/14518163143965 ; "Managing base price" (snippet), https://help-lite.guesty.com/hc/en-gb/articles/34675735015453-Managing-base-price-in-Guesty-PriceOptimizer |
| S47 | 7 | STR Tech Report, "Your Data Is Lying" (snippet), https://strtechreport.com/resources/your-data-is-lying |
| S48 | 3 | PriceLabs, "Check-in & Check-out feature" (snippet), https://help.pricelabs.co/portal/en/kb/articles/checkin-checkout-feature |
| S49 | 3 | P. Ye, F. Yang (Airbnb, Inc.), "Hierarchical generation of booking probability", US 11,308,564 B2, granted 2022-04-19, https://patents.google.com/patent/US11308564B2/en |
| S50 | 3 | PriceLabs, "Revenue Accelerator release", updated 2026-04-07, https://hello.pricelabs.co/blog/revenue-accelerator-release/ |
| S51 | 7 | TechCrunch, "Airbnb will automatically display total price to all users", 2025-04-21, https://techcrunch.com/2025/04/21/airbnb-will-automatically-display-total-price-to-all-users/ |
| S52 | 1 | B. Parthum, P. Christensen, "A Market for Snow: Modeling Winter Recreation Patterns Under Current and Future Climate", J. Environmental Economics and Management 113 (2022) 102637, doi:10.1016/j.jeem.2022.102637, https://pmc.ncbi.nlm.nih.gov/articles/PMC10936566/ (data 2014-2017: STALE as calibration) |
| S53 | 7 | Peter Glenn, "Ikon Base Pass 2026-27" (snippet), https://peterglenn.com/ikon-base-pass-2026-27/ ; OnTheSnow Ikon buyer's guide, https://www.onthesnow.com/news/a/632258/buyer-s-guide-to-the-ikon-pass |
| S54 | 7 | Denver7, "Berthoud Pass closed due to avalanche covering all lanes", https://www.denver7.com/news/local-news/berthoud-pass-closed-due-to-avalanche-covering-all-lanes ; Hoodline, 2026-03, https://hoodline.com/2026/03/avalanche-shuts-berthoud-pass-route-into-winter-park/ |
| S55 | 7 | PublicSchoolsCalendar, HISD / Dallas ISD / Austin ISD 2026-27 (snippets), https://publicschoolscalendar.com/hisd-school-calendar-2026-2027/ , https://publicschoolscalendar.com/dallas-isd-calendar-2026-2027/ , https://publicschoolscalendar.com/austin-isd-calendar-2026-2027/ |
| S56 | 7 | DPS 2026-27 calendars, CalendarStates https://calendarstates.com/colorado/denver-public-schools/ ; PublicSchoolsCalendar https://publicschoolscalendar.com/denver-public-school-calendar-2026-2027/ ; EduCounty https://www.educounty.net/calendars/colorado/denver-public-schools/ (all snippets, conflicting) |
| S57 | 7 | Snowthere, "Best Christmas ski resorts for families", https://www.snowthere.com/guides/best-christmas-ski-resorts-families ; A Luxury Travel Blog, https://www.aluxurytravelblog.com/?p=35831 (snippets) |
| S58 | 7 | G. Blanchard, Inntopia, "Are advanced-bookers of ski vacations paying more or less...", 2013-08-20 (STALE), https://corp.inntopia.com/adr-vs-lead-time/ |
| S59 | 6 | FTC, Trade Regulation Rule on Unfair or Deceptive Fees, 90 Fed. Reg. (2025-01-10), 16 CFR Part 464, https://www.govinfo.gov/content/pkg/FR-2025-01-10/html/2024-30293.htm ; FTC FAQ https://www.ftc.gov/business-guidance/resources/rule-unfair-or-deceptive-fees-frequently-asked-questions |
| S60 | 7 | Hospitable Help, "Understanding Airbnb's host-only fee change", https://help.hospitable.com/en/articles/4703232 ; Truvi, "Airbnb Host Fees: What Changed in 2025", https://truvi.com/blog/airbnb-host-fees/ (vendor blogs; Airbnb primary not found) |
| S61 | 1 | T. Blake, S. Moshary, K. Sweeney, S. Tadelis, "Price Salience and Product Choice", Marketing Science 40(4):619-636 (2021), https://faculty.haas.berkeley.edu/stadelis/AIP.pdf (abstract read) |
| S62 | 7 | BiggerPockets threads (snippets), https://www.biggerpockets.com/forums/530/topics/1036671-whats-your-preferred-dynamic-pricing-engine , https://www.biggerpockets.com/forums/530/topics/1021314-dynamic-pricing-software |
| S63 | 7 | Comparison blogs (snippet; exact attribution of the "lag" quote UNVERIFIED), https://staystra.com/pricelabs-vs-wheelhouse-vs-beyond-pricing-2026/ , https://www.gowithsurge.com/blog/airbnb-dynamic-pricing-tools |
| S64 | 1 | Y. Wang, K. McGuire, J. Terbush, M. Towns, C. K. Anderson, "Choice-Based Dynamic Pricing for Vacation Rentals", INFORMS J. Applied Analytics (Interfaces) 51(6):450-462 (2021), doi:10.1287/inte.2021.1075, https://pubsonline.informs.org/doi/10.1287/inte.2021.1075 (abstract; seminar page https://soe.rutgers.edu/event/choice-based-dynamic-pricing-vacation-rentals) |
| S65 | 1 | V. Leoni, J. O. W. Nilsson, "Dynamic pricing and revenues of Airbnb listings: Estimating heterogeneous causal effects", Int. J. Hospitality Management 95 (2021); WP https://ideas.repec.org/p/ubi/deawps/92.html (abstract) |
| S66 | 1 | C. Gibbs, D. Guttentag, U. Gretzel, L. Yao, J. Morton, "Use of dynamic pricing strategies by Airbnb hosts", IJCHM 30(1) (2018), doi:10.1108/IJCHM-09-2016-0540 (abstract; STALE) |
| S67 | 6 | U.S. DOJ, "Justice Department Requires RealPage to End Sharing of Competitively Sensitive Information...", 2025-11-24, https://www.justice.gov/opa/pr/justice-department-requires-realpage-end-sharing-competitively-sensitive-information-and |
| S68 | 7 | Fenwick, "DOJ's RealPage Settlement: A Blueprint for 'Safer' Algorithmic Pricing?", https://www.fenwick.com/insights/publications/dojs-realpage-settlement-a-blueprint-for-safer-algorithmic-pricing ; Baker McKenzie alert (2025-12), https://www.bakermckenzie.com/en/insight/publications/alerts/2025/12/united-states-doj-settles-realpage-case |
| S69 | 7 | Mintz, "DOJ and FTC weigh in on alleged algorithmic price fixing" (Duffy v. Yardi SOI), 2024-03-07, https://www.mintz.com/insights-center/viewpoints/2191/2024-03-07-doj-and-ftc-weigh-alleged-algorithmic-price-fixing-ai |
| S70 | 7 | Baker McKenzie, "Ninth Circuit Clarifies Limits of Antitrust Liability for Algorithmic Pricing Tools" (Gibson v. Cendyn), 2025-09-01, https://connectontech.bakermckenzie.com/united-states-ninth-circuit-clarifies-limits-of-antitrust-liability-for-algorithmic-pricing-tools/ (replaces a dead insightplus link; opinion itself not read) |
| S71 | 7 | American Antitrust Institute, en banc amicus in Gibson v. Cendyn, 2025-10-09, https://www.antitrustinstitute.org/work-product/aai-asks-en-banc-ninth-circuit-to-reconsider-panels-algorithmic-collusion-opinion-gibson-v-cendyn/ |
| S72 | 7 | Otten Johnson, "Colorado's HB25-1004 ... vetoed by Governor Polis", https://www.ottenjohnson.com/news/colorados-hb25-1004-banning-algorithmic-rent-setting-vetoed-by-governor-polis/ (veto date only) |
| S73 | 7 | National Law Review, "Price tags and personal and competitor data: states step into algorithmic pricing", https://natlawreview.com/article/price-tags-and-personal-and-competitor-data-states-step-algorithmic-pricing |
| S74 | 1 | S. Assad, R. Clark, D. Ershov, L. Xu, "Algorithmic Pricing and Competition: Empirical Evidence from the German Retail Gasoline Market", J. Political Economy 132(3):723-771 (2024), doi:10.1086/726906, https://discovery-pp.ucl.ac.uk/id/eprint/10187765 (abstract) |
| S75 | 7 | Colorado Sun, "Colorado skier visits collapse 2025-26", 2026-06-04 (429; snippet; superseded by S91 for the figures), https://coloradosun.com/2026/06/04/colorado-skier-visits-collapse-2025-26/ |
| S76 | 7 | Colorado Politics, "After a snowless winter...", 2026-08-13, https://www.coloradopolitics.com/2026/08/13/after-a-snowless-winter-agents-say-summer-is-luring-second-home-buyers-to-the-mountains/ |
| S77 | 3 | PriceLabs Guesty landing page, 30-day free trial (snippet), https://hello.pricelabs.co/?p=1068 |
| S78 | 3 | PriceLabs, "How to connect PriceLabs with Guesty", https://help.pricelabs.co/portal/en/kb/articles/guesty ; Guesty Help, "Getting started with Guesty PriceOptimizer" (snippet: 14-day trial; deactivate other pricing tools), https://help-lite.guesty.com/hc/en-gb/articles/24924686846621 |
| S79 | 3 | PriceLabs Customer API overview, https://developers.pricelabs.co/customer-api/api-reference/overview ; endpoint index https://developers.pricelabs.co/llms.txt |
| S80 | 1 | O. Miroshnichenko, "Human-in-the-Loop Contextual Bandits for Short-Term Rental Dynamic Pricing", arXiv:2606.02595 (2026-05-22; preprint, abstract read), https://arxiv.org/abs/2606.02595 |
| S81 | 7 | Steamboat Pilot, "'Bad snow years make for bad bookings' ..." (Inntopia data; snippet; season unclear), https://www.steamboatpilot.com/news/bad-snow-years-make-for-bad-bookings-economic-policies-uneven-snowfall-contribute-to-lackluster-colorado-ski-season/ |
| S82 | 7 | Nestoria Estates, "Vancouver hosts: how dynamic pricing lifted RevPAR 25%" (reports a Hostaway study; secondhand), https://www.nestoriaestates.com/post/dynamic-pricing-strategy |
| S83 | 1 | C. Farronato, A. Fradkin, "The Welfare Effects of Peer Entry: The Case of Airbnb and the Accommodation Industry", American Economic Review (2022), doi:10.1257/aer.20180260, https://www.aeaweb.org/doi/10.1257/aer.20180260 (abstract; Brookings summary) |
| S84 | 1 | G. Gallego, G. van Ryzin, "Optimal Dynamic Pricing of Inventories with Stochastic Demand over Finite Horizons", Management Science 40(8):999-1020 (1994). Standard result cited from training knowledge; not re-read for this dossier |
| S85 | 2 | K. T. Talluri, G. J. van Ryzin, *The Theory and Practice of Revenue Management*, Springer (Kluwer), 2004, ch. 5 (dynamic pricing). Cited for standard results; not re-read |
| S86 | 2 | R. L. Phillips, *Pricing and Revenue Optimization*, Stanford University Press, 2005 (2nd ed. 2021). Cited for price-response and multi-period results; not re-read |
| S87 | 1 | K. Hanazawa, "Welfare Effects of Self-Preferencing by a Platform: Empirical Evidence from Airbnb", arXiv:2503.04489 (2025; preprint), https://arxiv.org/abs/2503.04489 |
| S88 | 7 | J. Zhou, AirROI, "Ski market winter 2026-27 booking pace", 2026-07-29 (14 ski markets, >24,000 listings; all-unit, scraped and vendor-modelled), https://airroi.com/blog/ski-market-winter-2026-2027-booking-pace |
| S89 | 7 | Covington & Burling, "Third Circuit reinstates algorithmic pricing antitrust lawsuit: Cornish-Adebiyi v. Caesars Entertainment, Inc." (No. 24-3006, decided 2026-07-29), 2026-08, https://www.cov.com/en/news-and-insights/insights/2026/08/third-circuit-reinstates-algorithmic-pricing-antitrust-lawsuit-cornish-adebiyi-v-caesars-entertainment-inc (opinion itself not read) |
| S90 | 7 | Post Independent, "Colorado saw the lowest skier turnout in more than 35 years this past winter" (snippet; reports CSCUSA figures), https://www.postindependent.com/news/colorado-skier-visitation-lowest-35-years/ |
| S91 | 4 | Colorado Ski Country USA (industry association), 2025-26 skier-visit estimate (10.5M, -3.3M, lowest since 1991-92; 129 vs 144 average operating days), as released via SAM Magazine 2026-06-05, https://www.saminfo.com/news/colorado-resorts-endured-historic-visit-decline-in-2025-26 (403 to R4; figures from search snippets of SAM, Post Independent [S90] and Colorado Sun [S75], which agree) |
| S92 | 3 | Ikon Pass, "26/27 Ikon Base Pass", https://www.ikonpass.com/en/shop-passes/ikon-base-pass |
| S93 | 5 | Vail Resorts, Inc., Form 10-K for fiscal year ended 2025-07-31, https://www.sec.gov/Archives/edgar/data/812011/000081201125000104/mtn-20250731.htm (risk-factor and business sections read in part; 2025/26 pass units ~-3% from a search snippet of the filing) |
| S94 | 5 | Vacasa, Inc., Form 10-K for FY2024, https://www.sec.gov/Archives/edgar/data/1874944/000187494425000003/vcsa-20241231.htm (Item 1 read in part) |
| S95 | 5 | Airbnb, Inc., Form 10-K for FY2025, https://www.sec.gov/Archives/edgar/data/1559720/000155972026000004/abnb-20251231.htm (first third read) |
| S96 | 7 | HBS Working Knowledge, "White Airbnb hosts earn more. Can AI shrink the racial gap?" (summary of S39: price -5.8%, daily revenue +8.6%, 2,118 properties, 7 US cities, 2015-17), https://www.library.hbs.edu/working-knowledge/white-airbnb-hosts-earn-more-can-ai-shrink-the-racial-gap |
| S97 | 3 | KeyData, "Summit County, Colorado's 2025-26 ski season outlook", 2025-10-16, https://www.keydata.co/blog/summit-county-colorados-2025-26-ski-season-outlook |
| S98 | 7 | OwnerRez forum, "Arrival restrictions", 2020-02 with 2022-11 follow-up (STALE), https://www.ownerrez.com/forums/general-help/arrival-restrictions |
| S99 | 7 | Hostaway community, "Default setting to check in/out restrictions" (snippet), https://support.hostaway.com/hc/en-us/community/posts/26706609816347-Default-setting-to-check-in-out-restrictions |

Repo sources read (not counted above): `README.md`, `docs/ARCHITECTURE.md`,
`docs/rules/PRICING_DOCTRINE.md`, `docs/rules/COMP_DATA.md`, `docs/plans/OVERHAUL_2026-10-14.md`,
`docs/research/MODEL_SPEC.md`, `docs/research/dossiers/01,04,05,06`, `docs/resort/WINTER_PARK_KNOWLEDGE.md`,
`docs/reports/anchor_rule_study/DECISION.md`, `src/pricing/pace.py`, `src/compose/__init__.py`
(signal gating), `src/signals/collectors/*`, `src/signals/features/*`, `src/signals/consumer.py`,
`src/scrape/providers.py`, `src/scrape/__init__.py`, `src/shadow/__init__.py`, `src/min_stay/__init__.py`,
`config/policies/{default,signals,events,markets,conditions}.yaml`,
`config/policies/candidates/pace_v3_anchor_repair.yaml`, `config/resort/winter_park.yaml`,
`proving_ground_exam/market/competitors.py`.

## Appendix A. Search log

Searches (web search tool; "ext" = extended mode). Fetches listed after.

| # | Query (abridged) | Yield |
|---|---|---|
| 1 | PriceLabs algorithm base price demand factors help | calc order, event and algorithm pages |
| 2 | PriceLabs Hyper Local Pulse | HLP blog, 350-listing / 15 km comp set |
| 3 | PriceLabs infer bookings calendar blocked accuracy | Market Dashboard methodology (key) |
| 4 | PriceLabs OBA defaults far-out last-minute | default discounts, OBA articles |
| 5 | PriceLabs pricing plans 2026 | conflicting price points |
| 6 | PriceLabs neighborhood data bedroom base price | bedroom-count article; Wheelhouse neighborhood doc |
| 7 | Beyond algorithm base price health score | Beyond blog, webinar recap |
| 8 | Beyond Pricing patent (ext) | no patents found |
| 9 | Wheelhouse RM API neighborhood cluster | API docs, changelog |
| 10 | Wheelhouse strategy demand sensitivity | help articles |
| 11 | Wheelhouse engine base price anchor credibility | research-pricing-engine page (key) |
| 12 | scraped Airbnb calendar accuracy blocked vs booked (ext) | no independent validation; AirDNA caveats |
| 13 | AirDNA Smart Rates / MarketMinder | Smart Rates help (now 404), Adapt mention |
| 14 | AirDNA Adapt launch | 2026-09-01 launch, Skift |
| 15 | Key Data methodology direct vs scraped | PMS-sourced data claims |
| 16 | Key Data pricing product | "not a pricing tool" |
| 17 | Guesty PriceOptimizer how it works | feature page, help articles |
| 18 | DPGO algorithm reviews | Capterra only |
| 19 | Vantory revenue management | not found (Vintory confusion); Wyndham paper lead |
| 20 | "Vantory" short-term rental (ext) | vantory.ai |
| 21 | Choice-based dynamic pricing Wyndham | Interfaces 2021 paper |
| 22 | Customized Regression Model Airbnb KDD 2018 | KDD paper, summaries |
| 23 | AI algorithm racial inequality Airbnb smart pricing | Zhang et al. 2021 |
| 24 | Airbnb Smart Pricing help factors | help article, third-party |
| 25 | Smart pricing too low complaints | community threads, Edinburgh glitch |
| 26 | Vrbo pricing recommendations | MarketMaker, rate automation |
| 27 | Airbnb total price display 2025 | TechCrunch, Fortune |
| 28 | DOJ RealPage settlement terms | DOJ release, law-firm analyses |
| 29 | Gibson v. Cendyn Ninth Circuit | 2025-08-15 decision summaries |
| 30 | DOJ statement of interest Yardi | 2024-03-01 SOI |
| 31 | Colorado HB25-1004 veto; California AB 325 | veto 2025-05-29; AB 325 description |
| 32 | STR pricing antitrust lawsuit PriceLabs Beyond (ext) | none STR-specific |
| 33 | reddit PriceLabs ski Christmas underpriced (ext) | nothing relevant |
| 34 | BiggerPockets PriceLabs vs Beyond vs Wheelhouse luxury (ext) | comparison blogs |
| 35 | site:reddit.com PriceLabs underpricing (ext) | **refused: domain blocked** |
| 36 | site:biggerpockets.com dynamic pricing ski (ext) | 10 threads |
| 37 | Beyond ski season booking window Colorado | Beyond ski note, Key Data, Inntopia |
| 38 | keydata methodology owner nights | ProData page |
| 39 | Duetto vacation rental product | none (hotel only) |
| 40 | Guesty PriceOptimizer demand pacing base price | help snippets |
| 41 | DPGO features pricing plan | review sites |
| 42 | Vrbo MarketMaker rate automation help | Vrbo help, Expedia partner blog |
| 43 | Airbnb hosts dynamic pricing adoption revenue (ext) | Leoni-Nilsson, others |
| 44 | Gibbs et al. IJCHM 2018 | abstract |
| 45 | Leoni-Nilsson causal effects | WP and journal record |
| 46 | Airbnb price elasticity luxury (ext) | Farronato-Fradkin, others |
| 47 | Ikon 2026-27 blackout Winter Park | retailer listings |
| 48 | snowfall effect lodging demand (ext) | Parthum-Christensen JEEM 2022 (key) |
| 49 | PriceLabs ski market snow | nothing from PriceLabs |
| 50 | FTC junk fees short-term lodging | Fed. Reg., FAQ |
| 51 | Blake et al. price salience | Marketing Science 2021 |
| 52 | Airbnb patent price suggestion booking probability (ext) | US11308564B2 |
| 53 | Google Patents vacation rental pricing (ext) | no vendor patents; arXiv bandit paper |
| 54 | PriceLabs Revenue Accelerator 2026 | release page (fee isolation) |
| 55 | PriceLabs Portfolio Analytics pacing | pacing reports help |
| 56 | DPS 2026-27 calendar | conflicting aggregators |
| 57 | Texas ISD spring break 2027 | HISD / Dallas / Austin |
| 58 | Berthoud Pass closures frequency | news items only |
| 59 | PriceLabs check-in/check-out restrictions | feature article |
| 60 | luxury ski home booking window Christmas | chalet marketing sources |
| 61 | Airbnb host-only fee 15.5% PMS hosts | vendor blogs |
| 62 | Gibson v. Cendyn opinion PDF | AAI en banc brief |
| 63 | Assad et al. JPE 2024 | paper record |
| 64 | PriceLabs Customer API prices sync off | API requires syncing listings |
| 65 | PriceLabs Guesty sync off trial | trial, sync steps |
| 66 | PriceLabs case study mountain Colorado | none with numbers |
| 67 | Wheelhouse ski report Winter Park | none; Colorado Politics 2026 article |
| 68 | 2025-26 Colorado ski season lodging | Colorado Sun skier visits -24% |
| 69 | dynamic pricing lowers ADR critique (ext) | Hostaway study (secondhand) |
| 70 | Farronato-Fradkin AER | AER record |
| 71 | (review round, 2026-10-17) AirROI ski market winter 2026-27 booking pace (fetch) | Winter Park 72-day winter lead; ADR +22.2%, occupancy 44.9% to 35.8% |
| 72 | Cornish-Adebiyi v. Caesars (Covington fetch) | 3d Cir. reversal 2026-07-29; ~90% acceptance pleaded |
| 73 | KDD 2018 full paper (ACM pdf, kdd.org link, search "pdf full text") | 403 x3; no open copy found |
| 74 | Zhang et al. SSRN 3770371 abstract figures | SSRN 403; HBS summary gives -5.8% / +8.6% |
| 75 | CSCUSA 2025-26 skier visits | 10.5M, lowest since 1991-92, 129 vs 144 days (snippets; SAM 403) |
| 76 | Vail Resorts 10-K FY2025 snowfall, pass units | 10-K read in part; pass units ~-3% (snippet) |
| 77 | Vacasa 10-K dynamic pricing objective | FY2024 Item 1: "optimize homeowner income", RevPAN algorithms |
| 78 | Airbnb 10-K FY2025 (fetch) | "optimize pricing, and maximize occupancy for our hosts" |
| 79 | Gibson v. Cendyn opinion text / rehearing | no opinion text; en banc petition pending as of late 2025 |
| 80 | Ikon Base Pass 2026-27 (ikonpass.com fetch) | Winter Park unlimited; blackout applicability ambiguous |
| 81 | KeyData Summit County 2025-26 outlook (fetch) | on-the-books ADR +2% as of late Sept 2025 |
| 82 | OwnerRez arrival restrictions (fetch); Hostaway post (snippet) | arrival-day rule friction |
| 83 | Baker McKenzie Gibson alert (replacement URL fetch) | holding confirmed |

Fetches (~50 in the first round, ~16 more in the review round): PriceLabs S1-S9, S50, S78, S79 (+llms.txt); Wheelhouse S12-S15; Beyond S18-S20;
S22; S23; AirDNA S24 (how-it-works 403; Smart Rates 404); S26; S27; KeyData S28, S30 (two
redirects); Vantory S33; S36 (Airbnb 594 page empty); KDD abstract; S38; S42; S44; S45 (Guesty
help 403 x2); S49; S52; S58; S64 seminar page; S76; S80; S87; Colorado Sun (429); ScienceDirect
(403).

## Appendix B. Self-audit against the depth standard

| MUST | Status | Evidence |
|---|---|---|
| Cite every non-obvious claim inline with URL and access date | PASS | Inline `[S#]` keys resolve to URLs in section 14; single access date 2026-10-16 stated at top and in 14 |
| >= 40 distinct sources | PASS | 99 distinct external sources (S1-S99) plus repo files |
| >= 4 source classes | PASS | Class 1 academic: 12 (S37, S39, S52, S61, S64-S66, S74, S80, S83, S84, S87; S84 cited from knowledge, S37 and S39 abstract/summary level); class 2 textbooks: 2 (S85, S86; not re-read); class 3 vendor docs/patents: 43; class 4 industry body: 1 (S91 Colorado Ski Country USA; no Cornell CHR or HSMAI STR-pricing study was found in the reviewer's search or mine); class 5 filings: 3 (S93 Vail Resorts, S94 Vacasa, S95 Airbnb 10-Ks); class 6 government: 2 (S59, S67); class 7: 36. Seven classes |
| Read primary sources where they exist; say so when paywalled | **FAIL (partial)** | Read directly: vendor docs, DOJ release, FTC rule, JEEM paper, patent, arXiv abstracts, 10-Ks (in part), Ikon page, AirROI. **Not read despite trying:** KDD 2018 full paper (ACM 403 on three routes; claim rests on the paper text quoted by S38), Zhang et al. (SSRN 403; figures from HBS summary and abstract snippets), Gibson and Cornish-Adebiyi opinions (law-firm summaries only). Abstract-only: Blake, Leoni-Nilsson, Gibbs, Assad, Farronato-Fradkin. Every case is flagged in section 14 |
| Mark UNVERIFIED and STALE | PASS | UNVERIFIED: AirDNA accuracy claims, Ikon status (now an operator question), school dates, Vantory Colorado origin, host-only fee primary, PriceLabs 1% plan, PriceLabs export / unconnected listings, comparison-blog quote, magicbnb anecdote; STALE: S3/S4 (2023-09), S12 (2023-05), Inntopia 2013, Gibbs 2018, BiggerPockets 2023, OwnerRez 2020-22, Key Data COVID post, Parthum-Christensen data years, Beyond explainer |
| No fabricated stats, features, citations | PASS (self-checked) | Every vendor feature traced to a fetched page or labelled snippet; ND used where not disclosed; textbook results flagged as cited from knowledge |
| Several search passes: broad, specific, adversarial | PASS | 83 search/fetch steps logged (Appendix A), 70 in the first round plus 13 in the review round |
| Mechanisms, not names (math/algorithm detail) | PASS | 2.1 (booking inference steps, factor stack, DP), 2.2 (GBM+kriging, KM curves, gamma warping, response function), 2.9 (GBM + strategy model + loss), 12.1 (Gallego-van Ryzin logic, implementable objective) |
| Quantified evidence with who measured and conflicts | PASS | Lift table 4.3 with design and conflict columns |
| Map every finding to this engine (module, measurement in owner-net terms) | PASS | Sections 6, 8, 9, 10 name modules and owner-net measurements |
| Honest transferability (3 homes, thin data, LOS, groups, high prices, all-in) | PASS | Section 12.2 table and closing paragraph |
| "What generic STR pricers miss" note (H2) | PASS | Section 7 |
| Ranked recommendations with impact, confidence, effort, data, measurement | PASS | Section 10 |
| Open questions for operator | PASS | Section 11 |
| Self-audit table | PASS | This table |
| Running search log | PASS | Appendix A |
| Prefer 2020-2026 sources plus classics | PASS | Most sources 2021-2026; classics S84-S86 |
| Adversarial pass looking for contradictions | PASS | Section 13 |
| Task deliverables: per-vendor teardown (inputs, inference, model, granularity, weaknesses, business model, lift) | PASS with gaps | All 11 named tools covered; Duetto VR product not found; DPGO and MarketMinder thin (vendor discloses little; flagged) |
| Feature matrix incl. honest "our engine" column | PASS | Section 6 |
| Ranked specialist edges with copy-resistance, data, proof plan | PASS | Section 8 |
| Shadow-benchmark recommendation with cost | PASS | Section 9 (~$30-60/month after 30-day trial; Guesty-side rate diff for write-safety open question) |
| Reddit and Facebook host groups | FAIL (tool limits) | Reddit refused by the search tool; Facebook groups closed. Replaced with BiggerPockets and Airbnb Community |

## Appendix C. Response to review (2026-10-17)

Review: `docs/research/deep_2026-10/reviews/R4_review.md` (ACCEPT WITH FIXES, 20 items). I
re-checked every repo claim the reviewer made (R-1 to R-8) against the code and every new
external claim against its source before using it. Status per fix:

| # | Fix | Done | Notes / where I differ |
|---|---|---|---|
| 1 | Demote the 15-day first-party median | Yes (0, 3.1, 3.4, 7, 11 Q4, 12.2, 13) | Dossier 01's caveat quoted; right-censoring and provenance added (R4 ran no query; booking attributes, not guest identity fields) |
| 2 | Add AirROI 72-day Winter Park figure | Yes (3.1, 3.1a, 3.4, 7, 12.2, 13) | Verified on the AirROI page: 72 days, occupancy 44.9% to 35.8%, ADR $455 to $556 (+22.2%), supply +9.9%. Tagged all-unit, scraped, vendor-modelled. I agree it strengthens the existence of a snow edge but, with fix 8, weakens our current *implementation* of it |
| 3 | Comp calendar availability not persisted | Yes (6, 8, 10 rec 5) | Confirmed in `src/scrape/__init__.py`: `_enrich_min_nights` writes only `min_nights`; `available` comes from sweep presence |
| 4 | Comp price-movement signal | Yes (6, 12.1) | Confirmed `upsert_comp_movement_signals` runs on each scrape |
| 5 | `events.yaml` lacks 2026-27 MLK/Presidents/Spring Break | Yes (6, rec 9 raised) | Confirmed |
| 6 | Reconcile Ikon blackouts | Partly | Ikon's official page lists Winter Park as unlimited and lists blackouts in the same section without saying whether they apply to it; I could not resolve it, so it is now operator question Q8 and edge #6 is conditioned on it |
| 7 | Emulator description; pacing immutability; drought citation | Yes (2.1, 6, 9, rec 2) | Confirmed `tool_price` matches neither vintage; pacing upserts on same-day re-runs |
| 8 | SQI prior inconsistency | Yes (3.1a, 7, 8, 10 rec 8, 13) | Arithmetic checked: 0.135 x ln(0.6) = -6.9%. My suggested cap (no knot below ~0.93) is a sizing heuristic, not a fitted value; the proving-ground drought scenario is the test |
| 9 | Fix S39 citation | Yes | The CMU page indeed lacks the figures. HBS Working Knowledge says **-5.8%** price, +8.6% revenue; abstract snippets say -5.7%. I report "about -6%" and both numbers. SSRN returned 403, so the paper itself is still unread |
| 10 | Read KDD full paper and Gibson opinion | **Could not** | ACM returned 403 on the DOI PDF, the kdd.org "Download Full Paper" link and the authorize URL; no other open copy was found. I disagree that it is open access *to this agent*. The "naive maximization failed online" claim now carries a quote verified by the reviewer in S38 and is flagged. Gibson opinion: not read, now stated in 4.4 as well as 14 |
| 11 | P&C errors | Yes (13) | Corrected: Colorado is low but not lowest (Connecticut 0.075); lead-time result restated as cumulative <=2/5/7/10-day subsamples |
| 12 | Cornish-Adebiyi | Yes (0, 4.4) | Verified via Covington. Note: Covington does not use the word "split"; I label that characterization as mine. The opinion itself was not read |
| 13 | Dead S70; S72 narrower bill | Yes | Replacement Baker McKenzie URL fetched and confirmed; "narrower bill" dropped |
| 14 | Classes 4 and 5 | Yes | CSCUSA (S91) is cited through press because SAM returned 403; I count it as class 4 because the figures are the association's. 10-Ks were read only in part (they are 300-400k characters); each use quotes text I saw, except Vail pass units (~-3%), which is from a search snippet of the filing and flagged |
| 15 | Tone down lift summary; Vrbo windows | Yes (4.3) | |
| 16 | Shadow write safety, fallback, cost range, Guesty stay restrictions | Yes (9, 11 Q9) | Agree that `guesty_write_count` cannot see third-party writes; replaced the token idea with a Guesty-side rate diff |
| 17 | Own-homes block-inference validation | Yes (4.2, 8, rec 5) | Adopted; it is cheaper and cleaner than any vendor comparison |
| 18 | Arrival-day forum evidence | Yes (3.5, 4.1) | On reading the OwnerRez thread, the Saturday problem is how *Airbnb displays* an OwnerRez arrival restriction, not a PriceLabs defect; I describe it that way. The Hostaway item is snippet-only |
| 19 | STALE tags and qualifiers | Yes | S3/S4/S12 tagged STALE; S80 and S6 qualifiers added |
| 20 | Self-audit | Yes | "Read primary sources" is now FAIL (partial); classes 4 and 5 counted |

Also from the review: the specific booked-price figure in the public `config/policies/default.yaml`
comment is booked-price data in a public file. That is outside R4's write scope, so it is
flagged here for the operator, and R4 does not repeat it.
