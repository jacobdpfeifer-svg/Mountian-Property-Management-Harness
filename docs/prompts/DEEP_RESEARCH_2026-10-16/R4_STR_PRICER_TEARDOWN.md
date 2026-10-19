# R4: Generic STR pricer teardown, and the opening for a specialist

Output: `docs/research/deep_2026-10/R4_str_pricer_teardown.md`

## Question

What exactly do the generic STR dynamic pricers do: inputs, models, defaults and controls? Where
are they demonstrably weak for a market like Winter Park? Test hypothesis H2 from
`00_FIELD_NOTES.md` with evidence, not assertion.

## Tools to tear down (each one)

PriceLabs (Dynamic Pricing, Market Dashboard, Portfolio Analytics, "Hyper Local Pulse"). Beyond
(Beyond Pricing). Wheelhouse. AirDNA Smart Rates and MarketMinder. Key Data Dashboard (which
uses PM-sourced booking data). DPGO. Vantory. Duetto's vacation-rental product. Airbnb Smart
Pricing. VRBO/Expedia pricing recommendations. Guesty PriceOptimizer (we use Guesty).

For each, document:

1. **Data inputs**, as disclosed or verifiable: scraped calendar availability, scraped listed
   prices, booked-price inference, PM-contributed booking data, events, seasonality, own
   pacing, search data. Be specific about **how they infer bookings from calendar blocks** and
   the known error in that inference.
2. **Model**: the base price, the multiplicative factor stack (seasonality, day of week, lead
   time / last minute, orphan days, occupancy-based adjustments), the customization knobs, and
   what is learned vs fixed. Use help-center docs, patents, founder talks, API docs and
   engineering blogs.
3. **Market granularity**: how they define the comp set and the neighborhood. Do they
   distinguish a 6-bedroom luxury home from a condo in the same town? Bedroom segmentation.
4. **Known weaknesses**: user complaints (Reddit r/airbnb_hosts, BiggerPockets, Facebook host
   groups; cite them), published accuracy evaluations, and lawsuits (for example the RealPage
   antitrust litigation and what it implies for shared-data pricing tools, including DOJ actions
   2024–2026).
5. **Pricing and business model**: the percent-of-revenue fee, and the incentives that creates.
6. **Evidence of lift**: vendor claims vs independent evidence.

## Mountain-market specific weaknesses to probe

- How do they treat **snow conditions, resort opening and closing dates, pass blackout dates,
  traffic and pass closures, and school-district calendars of origin markets** (Denver Public
  Schools, Texas districts)? Usually they don't. Verify per vendor.
- **Holiday-period mechanics**: Christmas–New Year minimum stays, arrival-day rules.
- **Large-home scarcity**: thin comp sets for 5+ bedrooms, and price discovery at
  $1.5k–3k/night.
- **Booking-window shape**: luxury ski homes book 4–10 months out. Do the defaults
  ("last-minute discount", "far-out premium") fit?
- **Fee-inclusive display** and its interaction with nightly price.

## Deliverables

- A feature matrix: rows are capabilities, columns are vendors plus **our engine as of today**
  (read the repo to fill our column honestly, including what is unbuilt or unproven).
- A ranked list of the **specialist edges** we could credibly own. For each: why generics can't
  easily copy it, which data it needs, and how we would prove the edge against a PriceLabs
  baseline in our proving ground and in the field.
- A recommendation on whether to **run PriceLabs (or similar) as a shadow benchmark arm**, with
  its cost.
