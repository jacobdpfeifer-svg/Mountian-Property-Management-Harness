# R5: The data-stream universe for mountain lodging demand

Outputs:
- `docs/research/deep_2026-10/R5_data_stream_universe.md`
- `docs/research/deep_2026-10/R5_catalog.csv` (one row per stream)

## Question

What is the **complete** set of data streams that could plausibly move demand, willingness to pay
or competitor supply for Winter Park / Fraser luxury lodging? For each one, what is the causal
mechanism, how far ahead does it lead, and can we actually get it?

Be exhaustive first and judge later. The operator explicitly wants geopolitical and macro streams
considered.

## Categories (each must be covered; add any we missed)

1. **Own and market lodging data.** Our Guesty pace, inquiries, listing views and conversion (if
   exposed). Comp calendars and prices. Market occupancy on the books (DestiMetrics, Key Data,
   AirDNA, PriceLabs Market Dashboard, Transparent). New supply and listing churn. STR licence
   counts (Grand County, Winter Park, Fraser).
2. **Search and intent.** Google Trends ("Winter Park lodging", "Winter Park snow"), Airbnb and
   VRBO search-volume proxies, flight search data (Google Flights, Hopper, Skyscanner insights),
   destination-marketing data (Visit Winter Park / Chamber), and website traffic to our direct
   site.
3. **Snow and weather.** SNOTEL, NRCS. NOAA/NWS forecasts and long-range CPC outlooks. ENSO.
   OpenSnow-type forecasts. Resort-reported snowfall and base depth, and terrain open %. How
   powder days drive last-minute bookings. Snowmaking temperature windows.
4. **Access and travel.** I-70 and US-40 (Berthoud Pass) traffic counts and closures (CDOT, COtrip).
   Eisenhower Tunnel counts. The Winter Park Express (Amtrak ski train) schedule and sellouts.
   DEN passenger volume and TSA throughput. Airfares into DEN by origin. Rental-car rates.
   Shuttle services.
5. **Energy and cost-to-travel.** Colorado retail gasoline (EIA weekly, AAA). Diesel. Jet fuel.
   EV-charging access. (Hypothesis H4.)
6. **Macro and consumer.** University of Michigan and Conference Board consumer sentiment. Denver
   metro employment and income. S&P 500 / wealth effect (luxury guests). Inflation. Interest
   rates. Travel-intention surveys (Deloitte, Destination Analysts, MMGY, US Travel).
   **Recession indicators.**
7. **Geopolitical and international.** USD exchange rates (MXN, GBP, AUD, CAD, BRL, EUR). Visa and
   entry policy. Travel advisories. Conflicts affecting airfare or fuel. International ski
   tourism to the US. Tariff and trade effects on consumer spending. Federal policy shocks
   (government shutdown effects on federal-employee travel and national parks).
8. **Calendar.** School calendars of origin markets (Denver Metro, Colorado Springs, Texas,
   Kansas, Oklahoma, Nebraska, Midwest). University breaks. Federal holidays and their
   positions. Easter date. Spring-break distributions. Jewish holidays. Mexico's Semana Santa
   (Holy Week) and Christmas school calendar. Hosted events (World Cup ski events, festivals,
   concerts, Winter Park summer events, weddings, conferences in Denver).
9. **Resort operations and the ski industry.** Opening and closing dates. Pass sales (Alterra and
   Vail disclosures). Lift-ticket prices. Terrain and lift outages. Labor shortages and their
   effect on capacity. NSAA skier-visit reports. Colorado Ski Country USA.
10. **Regulation and supply.** STR licence caps, moratoriums and taxes (Grand County, Fraser,
    Winter Park). Lodging-tax rates. HOA rules. Insurance cost trends.
11. **Competitor and substitute destinations.** Pricing, snow and access at Breckenridge, Keystone,
    Steamboat, Vail and Copper. Substitution when I-70 is jammed. Utah and Tahoe snow (fly-in
    substitution).
12. **Reputation and listing quality.** Reviews, ratings and photos of comps. Superhost/Premier
    Host status. Listing rank.
13. **Anything else** a creative, rigorous researcher would add: social media buzz, Reddit
    trip-report volume, wildfire smoke, air quality, avalanche-closure events, power outages,
    and so on.

## For every stream (CSV columns)

`id, category, name, provider, url, mechanism (why it should move demand/WTP), affected segment
(Front Range drive / fly-in / international / group), expected sign, lead time to stay date
(days), update cadence, history depth, granularity (geo/time), access (API/scrape/manual/paid),
cost, licence/ToS constraint, data quality risk, already in repo? (path), prior evidence of
predictive power (cite), estimated value tier (A/B/C with a one-line reason), effort to ingest`

## Required

- At least **80 streams** in the catalog. Each A-tier stream needs a paragraph in the dossier
  with sources.
- For each category, say which streams generic STR pricers already use (from public docs) vs
  which none of them use. That is the specialist edge.
- Verify access claims. Actually load the API docs or data page for every A-tier and B-tier
  source.
- Do not fetch or store large datasets. Note history availability only.
