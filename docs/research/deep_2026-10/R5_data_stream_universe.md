# R5: The data-stream universe for Winter Park / Fraser luxury lodging

Date: 2026-10-16. Access date for every web source: **2026-10-16** unless stated otherwise.
Catalog: `docs/research/deep_2026-10/R5_catalog.csv`. It has **121 streams** across all 13
categories, one row per stream, with the 20 columns the prompt specifies.
Author role: research only. No code, config or Guesty changes were made. No large datasets
were downloaded. Endpoint checks were single small requests, such as one JSON page or one
CSV tail.

---

## 1. Summary

1. **The binding constraint is still the comp feed, not a missing exotic signal.** Of the 17
   A-tier streams, the ones that would change owner-net profit most this winter are the
   comp-price anchor (L06/L13), a licensed fallback for it (AirDNA, L07), and market
   on-the-books pace (DestiMetrics, L09). The shared context says only about 3% of nights get a
   comp anchor today. No macro or geopolitical stream can make up for that.
2. **The specialist edge is real but narrow, and it sits in physical-world streams.** These
   are snowpack and the snow forecast (W01, W03, W08), terrain status (R02), US-40/Berthoud and
   I-70 access (A01, X04), relative snow at substitute resorts (X01), and origin-market school
   calendars (C01, C02, G08). The public documentation of PriceLabs, Wheelhouse, Beyond and
   Airbnb Smart Pricing mentions none of the snow, road or origin-calendar streams (§5).
   PriceLabs' own algorithm write-up mentions no weather, snow, flights, search or macro inputs
   ([PriceLabs part 1](https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/)).
   This supports **H2** for these streams specifically. It does not support H2 for search or
   pace data: Beyond and Airbnb both use search signals, and PriceLabs uses pacing.
3. **The best quantified STR snow prior is a short-run, within-month number, not a season
   multiplier.** Parthum & Christensen (2022, *JEEM* 113) regress STR revenue on **daily
   resort-reported snow depth** (OnTheSnow) with **property × month fixed effects**, using AirDNA
   property-days near 236 US resorts, **Aug 2014–May 2017 (STALE)**. For Colorado the elasticity is
   **0.135** (national 0.223); for bookings made <2, <5, <7 and <10 days ahead it is 0.124–0.152
   ([PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC10936566)). Because month fixed
   effects absorb most season-level variation, it does **not** identify a bad-season effect, and
   its variable is resort depth (stream W08), not SNOTEL SWE (W01). An earlier draft turned it into a
   season multiplier, `(SWE/normal)^0.135 ≈ 0.93` at 60% of normal; that is **withdrawn** as a prior.
   2025-26 is the counter-check: Colorado skier visits fell about 24% (preliminary), far more than
   −7%. Other snow-demand studies exist and are not STR-specific: Töglhofer, Eigner & Prettenthaler
   (2011, *Climate Research* 46:1–14) find a one-SD change in snow conditions moved **overnight
   stays** 0.6–1.9% in 185 Austrian ski areas, less with snowmaking and none at high elevation;
   Shih, Nicholls & Holecek (2009, *JTR* 47(3)) find daily lift-ticket sales respond to snow depth,
   temperature and wind chill; HVS (2015, STALE, practitioner) finds the within-season snow–occupancy
   link stronger at drive-to resorts (sources via the R5 review).
4. **Geopolitics is live this season, mostly through energy.** As of 2026-10-14, Brent is at
   **$126.55** (FRED, checked by request). Colorado regular gasoline is **$4.175/gal** (EIA
   weekly for 2026-10-12, checked by request). The Aspen Times ties both to the US–Iran war and
   the Strait of Hormuz disruption
   ([Aspen Times 2026-04-04](https://www.aspentimes.com/news/colorado-gas-prices-surge-mountain-towns-easter/)).
   This makes **H4 (gas suppresses drive-up demand)** worth testing now. The prior depends on
   origin. For a Denver party, total fuel is about 0.7–1.7% of the stay and a $1/gal rise adds about
   0.3–0.4%. For Texas, Kansas and Oklahoma drive-in groups, total fuel is about 7–21% of the stay and
   $1/gal adds about 2–5% (§3.5; distances are reviewer estimates). I rate gasoline **B**, a
   test-first shadow signal weighted by origin (C02), not A.
5. **This winter has an unusually strong season-level read.** Vail Resorts' 2026/27 pass units
   are **down about 12%** through 2026-09-18. The weakness is "concentrated among Destination
   frequency products", that is, fly-in buyers, while Colorado and Utah local markets "showed
   modest improvement"
   ([Vail 8-K, SEC](https://www.sec.gov/Archives/edgar/data/0000812011/000081201126000048/a20260731pressrelease.htm)).
   Colorado skier visits fell about 24% in 2025-26 to roughly 10.5M, the lowest since 1991-92,
   per press coverage of Colorado Ski Country USA's 2026-06-04 meeting (**preliminary**)
   ([CSCUSA](https://media.coloradoski.com/2025-26-projected-skier-visits);
   [Colorado Sun](https://coloradosun.com/2026/06/04/colorado-skier-visits-collapse-2025-26/)).
   The Conference Board index fell to **81.9** in September 2026
   ([Conference Board](https://www.conference-board.org/topics/consumer-confidence)). Each of
   these is a slow regime signal. None is a nightly price input.
6. **Three repo findings matter before any new stream is added:**
   - `src/signals/collectors/weather.py` uses Open-Meteo. Open-Meteo's free API is
     **non-commercial only**, and this engine is commercial
     ([Open-Meteo pricing](https://open-meteo.com/en/pricing)). Either buy a plan or move the
     short-range forecast to NWS `api.weather.gov`, which is public domain and has a
     `snowfallAmount` layer for grid BOU/37,70 (checked by request).
   - `flight.py`, `intent.py` and `regulatory.py` are fixture-only or return `unavailable`. On a
     live run they contribute nothing.
   - `cdot.py` covers US-40 only. The I-70 side of the substitution story (X04) is missing.

---

## 2. Method

- **Repo reading.** I read every file under `src/signals/` (10 collectors, 3 extractors, 4
  features), `config/policies/signals.yaml` and the seven 2026-09-29 dossiers (01–07), with
  dossier 03 as the predecessor list. I also read `docs/resort/WINTER_PARK_KNOWLEDGE.md` and
  `config/policies/markets.yaml`. The SNOTEL station is 335:CO:SNTL, Berthoud Summit.
- **Search passes.** There were 73 WebSearch queries in three passes:
  - Broad: providers per category.
  - Specific: named APIs, named papers and named filings.
  - Adversarial: Google Trends sampling critiques, the Google Flu failure, AirDNA accuracy,
    scraping legality, the lack of gas-to-skier evidence, and weather-forecast effects.
  - One query failed when the session limit was hit. Two queries used "extended" mode. The log
    is in Appendix A.
- **Verification.** About 30 WebFetch reads of primary pages: API docs, help centres, SEC
  filings and data pages.
  - About 40 direct HTTP checks. Each pulled one small JSON or CSV response, or only a status
    code. They confirmed endpoints, auth requirements and the latest values. Examples:
    NRCS AWDB OpenAPI paths; the NWS gridpoint layers; the CPC GIS archive back to 2011; the
    Open-Meteo forecast and ensemble endpoints; the EIA API key requirement; Denver weekly
    gasoline back to 2000-06; and FRED CSVs (UMCSENT, SP500, DEXMXUS, SAHMREALTIME,
    DENV708URN, DCOILBRENTEU, DJFUELUSGULF, CUSR0000SETG01).
  - Also the Intrawest lift feed, Hebcal, the COtrip CARS host and CDOT OTIS.
  - Where a page blocked the check (403, 404 or Cloudflare), the catalog says so and marks the
    claim **UNVERIFIED**.
- **Tiering rule.** A is direct or near-direct evidence on Winter Park demand or WTP, obtainable
  now, with a lead that matches when prices are set, or an outcome series the engine cannot be
  evaluated without. B is plausible with evidence elsewhere, or valuable but gated by cost or
  licence. C is weak, indirect, or redundant with a better stream. The tier is a **prior for
  the R6 value-of-information ranking**, not a fitted result.
- **Effect sizes.** Wherever I quote a lift figure, I say who measured it and whether that
  party had a conflict of interest, for example a vendor reporting its own result.

---

## 3. Category-by-category findings

For each category: what exists, what the evidence says, and what generic pricers already use
(their public docs, §5) versus what none of them mention.

### 3.1 Own and market lodging (14 streams: L01–L14)

- **Own pace and inquiries (L01, L02).** These are the outcome-side streams. Guesty's Open API
  exposes calendar (rates, minimum stay, availability), reservations search and a beta
  quotes/inquiries area. It has no listing-analytics endpoint
  ([Guesty Open API](https://open-api-docs.guesty.com/)).
  - Pickup or booking-pace forecasting is the workhorse of hotel RM. In a comparison on Choice
    and Marriott data, pickup, exponential smoothing and moving-average methods were most
    robust, and full booking-curve methods were less accurate (Weatherford & Kimes 2003,
    *IJF* 19(3):401–415,
    [Cornell eCommons](https://ecommons.cornell.edu/bitstream/handle/1813/72130/Kimes30_Comparison_of_Forecasting.pdf)).
    This is **STALE** by date, but it is foundational.
  - Talluri & van Ryzin (2004), *The Theory and Practice of Revenue Management*, ch. 9, covers
    the same pickup and advanced-booking models.
  - With about 100 reservations, own pace is useful only pooled across homes and seasons, with
    a market prior (L09).
- **Funnel data (L03, L04, L05).** Airbnb's host insights page loads (status 200), but it sits
  behind a login and has no public API. Airbnb's own pricing model uses **listing views, search
  and contact rates** as booking-probability features (Ye et al., KDD 2018, summarized by
  [The Morning Paper](https://blog.acolyer.org/2018/10/03/customized-regression-model-for-airbnb-dynamic-pricing/)).
  So the platform treats funnel data as signal. We can see our own views only by manual export.
- **Comp prices and calendars (L06, L13).** The binding constraint. On legality:
  - *hiQ v. LinkedIn* (9th Cir. 2022) held that scraping public pages likely does not violate
    the CFAA.
  - The district court later found hiQ **breached LinkedIn's user agreement**
    ([Jenner summary](https://www.jenner.com/en/news-insights/publications/client-alert-data-scraping-in-hiq-v-linkedin-the-ninth-circuit-reaffirms-narrow-interpretation-of-cfaa);
    [Wikipedia case page](https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn)).
  - So the risk shifts to contract and ToS (account bans, cease-and-desist), not criminal
    liability. A licensed feed is the hedge.
- **Licensed market data (L07–L11).**
  - **AirDNA's API** has a Market Data package: occupancy, ADR, RevPAR, booking lead time, LOS,
    active listings, future daily pricing, and 12–60 months of monthly history. It also has
    listing-level search, comps and **future pricing per listing**. Access is by bearer token
    through sales ([AirDNA API reference](https://airdna.redoc.ly/)).
  - **PriceLabs Market Dashboard** shows booked nights by LOS and booking window. It costs
    **$9.99 per dashboard per month** after one free dashboard
    ([PriceLabs help](https://help.pricelabs.co/portal/en/kb/articles/market-dashboard)).
  - **Key Data** is PMS-direct (80+ PMS integrations), with an API on its EnterpriseData tier
    ([keydata.co](https://www.keydata.co/)). The DMO tier starts at $8,500/yr
    ([Visit NC partner page](https://partners.visitnc.com/key-data-vacation-rental-data-1)).
  - **Inntopia DestiMetrics** pools property-manager submissions, sent twice monthly, and shows
    up to **six months forward** in its DMX portal. Data goes only to subscribing partners:
    funding DMOs and data-submitting properties
    ([Inntopia help](https://help.inntopia.com/1378090/Content/Intelligence/DestiMetrics_Overview.htm)).
  - Accuracy caveat: I found **no independent audit** of AirDNA occupancy. The evidence is
    competitor claims and one-property anecdotes
    ([Airbtics](https://airbtics.com/how-accurate-is-airdna/);
    [BiggerPockets thread](https://www.biggerpockets.com/posts/6534234)).
    Scraped-calendar occupancy confuses owner blocks with bookings. PriceLabs says it applies
    block-removal logic
    ([PriceLabs part 1](https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/)).
- **Supply (L12).** Vendors disagree on the size of the market. For Winter Park, AirDNA shows
  1,881 active listings with supply down 5.9% YoY to July 2026
  ([AirDNA supply page](https://www.airdna.co/vacation-rental-data/app/us/colorado/winter-park/supply)).
  Rabbu shows 629 ([Rabbu](https://rabbu.com/airbnb-data/winter-park-co)). Treat supply as a
  trend, not a level.
- **Generic pricers use:** comps, market pacing and pickup (PriceLabs, Wheelhouse, Beyond), and
  hotel rates (PriceLabs uses booking.com hotel-like properties; Wheelhouse uses nearby hotel
  rates). **None mention:** a 5+ bedroom, sleeps-14+ comp set chosen by party-fit, rather than a
  radius sample of about 350 listings within 15 km
  ([PriceLabs part 1](https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/)).

### 3.2 Search and intent (8 streams: S01–S08)

- **Google Trends (S01).** Search volume improved hotel-room-demand forecasts in Pan, Wu & Song
  (2012, *JHTT* 3(3):196–210, doi:10.1108/17579881211264486): ARMAX beat ARMA
  ([Emerald abstract](https://www.emerald.com/insight/content/doi/10.1108/17579881211264486/full/html);
  [PolyU manuscript](https://ira.lib.polyu.edu.hk/handle/10397/25564)).
  - In Havranek & Zeynalov (2021, *Tourism Economics* 27(1):129–148), weekly Trends data in a
    MIDAS model helped forecast Prague arrivals up to about two months ahead
    ([RePEc](https://ideas.repec.org/a/sae/toueco/v27y2021i1p129-148.html)).
  - **Adversarial findings:**
    - Trends values are re-sampled daily. They differ by download date and location, and they
      round low-volume queries to zero below privacy thresholds
      ([arXiv 2504.07032](https://arxiv.org/pdf/2504.07032);
      [MZES / Hölzl et al.](https://www.mzes.uni-mannheim.de/en/publications/details/default-1b90339871013c563d9e0770aa21fed2-44)).
    - Google Flu Trends overfit many search terms to few outcomes, and missed the 2009
      pandemic (Lazer et al. 2014, *Science* 343:1203–1205,
      [Harvard DASH](https://dash.harvard.edu/handle/1/12016836)).
  - A "Winter Park" query is low-volume and ambiguous: Winter Park, Florida is a city. Use a
    small fixed term set chosen before looking at outcomes, average repeated pulls, and run at
    weekly frequency.
  - The official Trends API (alpha, July 2025) offers a consistently scaled, rolling five-year
    window, but access is by application
    ([Google Search Central blog](https://developers.google.com/search/blog/2025/07/trends-api)).
- **Flight search (S04).** SerpApi's Google Flights endpoint returns `price_insights`:
  `lowest_price`, `price_level`, `typical_price_range` and `price_history`
  ([SerpApi docs](https://serpapi.com/google-flights-api)). Amadeus Self-Service, the former
  free fare-search API, was **shut down on 2026-07-17**
  ([PhocusWire](https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers)).
- **DMO and mobility data (S05, S06).** Grand County's tourism board publishes DMO sessions by
  origin and Datafy visitor data. Examples: Chicago sessions +84.6% and Kansas City +66.9% in
  2024
  ([GCCTB 2024 report](https://www.visitgrandcounty.com/wp-content/uploads/2025/07/GCCTB_AnnualReport_2024.docx-FINAL-ua.pdf)).
  These are for simulator calibration, not live prices.
- **Generic pricers use:** Beyond's "search-powered pricing" (its Beacon plugin), with a claimed
  $5M added revenue over six months and an undisclosed method, so it is a **conflicted,
  unverified** claim
  ([Beyond blog](https://beyondpricing.com/blog/search-powered-pricing-from-beyond-adds-5m-in-revenue-for-our-customers-here-s-how-we-did-it)).
  Airbnb uses its own search and contact rates. **Edge for us:** small. Platforms see search
  data we cannot. Google Trends is a weak substitute at our query volume.

### 3.3 Snow and weather (12 streams: W01–W12)

- **Evidence.** Parthum & Christensen (2022) is the only lodging-revenue elasticity to snowpack
  I found from STR transactions (figures in §1). Their controls include 5-day new snow, holiday
  week, temperature and **snowpack at resorts within 100 km**. Other studies:
  - Falk (2015): low-snow seasons cut skier days by about 2.5% at high-elevation French areas
    ([ERSA pdf](https://gfr.ersa.org/wp-content/uploads/2015/03/falk_schweden.pdf)).
  - Gonseth (2013, *Climatic Change* 119:307–320): snowmaking dampens snow sensitivity, and
    better snow at lower areas pulls visits from higher ones
    ([RePEc](https://ideas.repec.org/a/spr/climat/v119y2013i2p307-320.html)).
  - Industry voice: Tom Foley (Inntopia), "Bad snow years make for bad bookings"
    ([Steamboat Pilot 2025-05-01](https://www.steamboatpilot.com/news/bad-snow-years-make-for-bad-bookings-economic-policies-uneven-snowfall-contribute-to-lackluster-colorado-ski-season/)).
    That is a practitioner claim, not a measurement.
- **Gap.** I found **no empirical study of powder days pulling forward last-minute bookings**
  for ski lodging. That search was run in extended mode. The closest evidence is the
  short-booking-window elasticity above, and forecaster guidance that point snow forecasts lose
  skill beyond about 7 days
  ([OnTheSnow](https://www.onthesnow.com/news/where-to-ski-every-month-of-the-year/);
  practitioner guidance). Treat "powder triggers last-minute demand" as a hypothesis to test
  with our own pickup data.
- **Access verified:**
  - NRCS AWDB REST has `/services/v1/{stations,data,forecasts,reference-data}` with no key
    ([OpenAPI](https://wcc.sc.egov.usda.gov/awdbRestApi/v3/api-docs)).
  - NWS `api.weather.gov/gridpoints/BOU/37,70` exposes `snowfallAmount` (6 h),
    `windGust`, `snowLevel` and `hazards`, updated hourly, with a User-Agent header required.
  - The CPC 6–10/8–14 day GIS archive goes back to 2011
    ([CPC FTP](https://ftp.cpc.ncep.noaa.gov/GIS/us_tempprcpfcst/)). That gives honest
    as-of vintages for backtests.
  - Open-Meteo's Previous Runs API covers 1–7 day leads from January 2024, and its Historical
    Forecast API starts in 2021
    ([Open-Meteo substack](https://openmeteo.substack.com/p/weather-forecasts-from-previous-model-runs)),
    but under the licence problem in §1.
  - OpenSnow's API is for commercial partners only, by email
    ([OpenSnow API](https://opensnow.com/api/index.html)).
  - SNODAS 1 km daily runs from 2003-09-30, now at a "Basic" service level
    ([NSIDC G02158](https://nsidc.org/data/g02158)).
- **Generic pricers use:** no snow or weather input appears in the PriceLabs algorithm
  write-up, Wheelhouse's model description, Beyond's or Airbnb's. PriceLabs says only that ski
  season is "a lot less price sensitive" than summer, which is a seasonal effect. **Edge:**
  yes. This is the clearest H2 territory.

### 3.4 Access and travel (13 streams: A01–A13)

- **US-40/Berthoud (A01).**
  - COtrip events come from CDOT's CARS 511 host `api-511x-co.carsprogram.org`, which responded
    when checked. A community plugin says it needs no key
    ([plugin docs](https://hermes-agent.nousresearch.com/docs/plugins/colorado-traffic)).
    CDOT also documents registered XML feeds
    ([cotrip-feed](https://github.com/jfredrickson/cotrip-feed)).
  - Avalanche closures are real and multi-day. Berthoud stayed closed after the January 2024
    slides ([CDOT 2024-01](https://codot.gov/news/2024/january/us-40-berthoud-pass-to-remain-closed-overnight)).
- **I-70 tunnel counts (A02, A03).** CDOT publishes Eisenhower–Johnson Tunnel monthly counts
  for **2000 through August 2026**. Examples: January 2026 at 1,029,653 vehicles, and July 2026
  at 1,194,859 vs July 2025 at 1,242,866
  ([CDOT table](https://www.codot.gov/travel/eisenhower-tunnel/trafficcounts)).
  - OTIS has hourly continuous counts. Station 000106 was used in a public analysis covering
    2018–2023 ([NYC Data Science blog](https://nycdatascience.com/blog/wp-json/wp/v2/posts/96577);
    [OTIS](https://dtdapps.codot.gov/otis/TrafficData)).
  - The tunnel is **west** of the Empire exit to US-40, so these counts measure the Summit/Vail
    corridor, our substitute. They are a **substitute-corridor control** for H4, not the outcome.
    The H4 outcome is a US-40 count station between Empire and Winter Park (A03): R7 used CDOT
    OTIS continuous station 000223 ("SH 40 E/O Henderson Mine Rd", MP 248.7–254.3, 2025 AADT 8,300). I-70 events east of Empire (Floyd Hill, Idaho Springs) are shared negatives; only
    events west of Empire favour Winter Park (X04). Floyd Hill planned overnight closures continue
    through mid-December 2026 (CDOT) and are a dated negative access stream.
- **Congestion behaviour.** The I-70 Coalition/RRC survey found that 67% of Front Range skiers
  report fewer trips because of traffic, and 45% report more overnight trips. It is **STALE**
  (2019)
  ([Summit Daily](https://www.summitdaily.com/news/new-i-70-study-shows-congestion-is-leading-some-skiers-to-make-fewer-trips-to-the-mountains/)).
  Overnight substitution is the part that favours us.
- **Rail and air (A05–A10).**
  - **Winter Park Express:** 2025-26 ridership 39,451 at an 88% load factor (CDOT CTIO April
    2026 deck, via search snippet; the PDF returned 404 when fetched, so **UNVERIFIED** in
    full). Amtrak says it returns for 2026-27
    ([Amtrak](https://www.amtrak.com/promotions/WinterParkExpress)).
  - **DEN:** a record 82.4M passengers in 2025, +0.1%
    ([DEN press release](https://www.flydenver.com/press-release/denver-international-airport-sees-slight-growth-in-passenger-traffic-over-previous-year/)).
  - **TSA:** hourly throughput by airport is posted weekly as PDFs
    ([data.gov](https://catalog.data.gov/dataset/tsa-foia-reading-room-weekly-passenger-throughput-data)).
  - **DB1B fares:** quarterly; the sample changes to 40% from July 2025, which breaks the
    series ([BTS FAQ](https://transportation.libanswers.com/faq/166146)).
  - **Forward seats (OAG/Cirium):** paid.
- **Generic pricers use:** none of these. **Edge:** yes for US-40 closures and I-70-vs-US-40
  relative congestion. DEN volume is too diluted by hub connecting traffic to help.

### 3.5 Energy and cost-to-travel (7 streams: E01–E07)

- **Data.** EIA's weekly retail series include **Denver city, Colorado state and PADD 4**. The
  release page showed 2026-10-14, with the next release on 2026-10-20
  ([EIA](https://www.eia.gov/dnav/pet/pet_pri_gnd_dcus_nus_w.htm)).
  - API v2 needs a free key. The request without one returned `API_KEY_MISSING`.
  - The Denver weekly history starts in 2000-06.
  - The Colorado price was $4.020 on 2026-10-05 and $4.175 on 2026-10-12.
  - The Aspen Times lists Grand County at $4.113 on 2026-04-03.
  - The EIA STEO gives a dated forward forecast. For October 2026 it reports that Brent
    averaged $114/b in September 2026, with Middle East flows assumed constrained through 4Q26
    ([STEO Oct 2026](https://www.eia.gov/outlooks/steo/archives/oct26.pdf)).
- **Evidence for H4.**
  - **No study links gas prices to Colorado skier days or ski lodging.** That search was run
    in extended mode.
  - The closest is a 30-park, 30-year national-park panel finding visitation "modestly
    responsive" to fuel prices
    ([JPRA](https://js.sagamorepub.com/index.php/jpra/article/view/13064)), plus
    Oh & Hammitt (2011, *Tourism Economics* 17(6))
    ([RePEc](https://ideas.repec.org/a/sae/toueco/v17y2011i6p1311-1324.html)).
  - A Crested Butte official's view that Front Range guests are "more price sensitive" is
    anecdote
    ([Crested Butte News](https://crestedbuttenews.com/2026/04/winter-visitor-numbers-take-hit-with-weird-snow-season/)).
  - Inntopia's Foley, during the April 2026 spike, saw "nothing really dramatic" (Aspen Times).
- **Mechanism check.**
  - The cost depends on origin, and the increment per $1/gal differs from the total fuel share:

    | Origin (round trip) | Vehicles for 16 guests | Gallons | +$1/gal as % of stay | Total fuel at $4.175 as % of stay |
    |---|---|---:|---:|---:|
    | Denver (~130 mi) | 4 at ~17 mpg | ~31 | ~0.3–0.4% | ~0.7–1.7% |
    | Kansas City (~1,320 mi, UNVERIFIED distance) | 4 at ~17 mpg | ~310 | ~2.5–4% | ~10–16% |
    | Dallas (~1,700 mi, UNVERIFIED distance) | 4 at ~17 mpg | ~400 | ~3.5–5% | ~14–21% |

    Stay cost is taken as $7.9k–11.9k including fees for 16 guests (review recomputation). An earlier
    draft used 3 cars at 20 mpg from Denver only and reported 0.2–0.3%, which is the most favourable
    case and mixed the increment with the share.
  - If gas matters, it acts through **sentiment and budget framing**, not the arithmetic. It
    should hit economy lodging and day-trippers more than 16-guest luxury homes.
  - H4 may still be true for the *market*, which lowers comp prices. It is much less likely
    true for *our segment's WTP*.
- **Generic pricers use:** none. **Edge:** testable but probably small. Test before using (§6,
  R5).

### 3.6 Macro and consumer (12 streams: M01–M12)

- **Free, verified FRED CSVs:**
  - UMich sentiment: 51.7 for August 2026
    ([FRED UMCSENT](https://fred.stlouisfed.org/series/UMCSENT)).
  - S&P 500: 7,744.06 on 2026-10-15. S&P's licence limits FRED history to 10 years.
  - Sahm rule, real-time version.
  - Denver–Aurora unemployment: 4.6% for August 2026.
  - CPI airline fares and lodging.
- **Conference Board.** September 2026 index 81.9, down from 88.6. 42.6% plan a vacation within
  six months, with the gain only domestic. Its data terms limit non-subscribers to personal
  noncommercial use, so a commercial engine needs a **licence**
  ([Conference Board](https://www.conference-board.org/topics/consumer-confidence)).
- **Wealth effect.**
  - Visa's research finds travel among the most wealth-sensitive categories, peaking about one
    year after the wealth change and larger in declines
    ([Visa pdf](https://eu.review.visa.com/content/dam/VCOM/global/partner-with-us/documents/weighing-the-wealth-effect.pdf)).
  - Goldman's Struyven estimated that +10% in equities raises jewelry and watch spending by
    about 6% ([CNBC 2019](https://www.cnbc.com/2019/01/17/luxury-spending-could-tumble-after-stock-market-drops.html)).
    This is **STALE**, and the source is bank research with a market-commentary motive.
- **Recession signals.** Sahm (2019) and the Estrella & Mishkin (1998, *Review of Economics and
  Statistics* 80(1)) yield-curve model are standard. Use them as **scenario switches**, not
  coefficients, because there are too few recessions to fit.
- **Surveys.**
  - Deloitte 2025: high-income travellers cut holiday trips from 2.5 to 1.9 and budgets fell
    18% ([Deloitte pdf](https://www.deloitte.com/content/dam/insights/articles/2025/us188641_cic_2025_holiday-travel-survey/pdf/DI_Holiday-travel-survey-2025.pdf)).
  - Future Partners' monthly tracker has 4,000+ completes per wave
    ([Jan 2026 deck](https://futurepartners.com/wp-content/uploads/2026/01/SATS-LIVESTREAM-JANUARY-2026.pdf)).
  - Longwoods' American Travel Sentiment runs to wave 110
    ([Longwoods](https://longwoods-intl.com/american-travel-sentiment/)).
- **Market read.** DestiMetrics' July 2026 briefing paired sentiment weakness with "negativity
  [spreading] … to moderate and luxury segments". Yet luxury ($401+) summer revenue rose 11.5%
  ([SGB](https://sgbonline.com/destimetrics-market-briefing-july-2026/)). That is
  contradictory, and a reason not to hard-code a sentiment-to-luxury sign.
- **Generic pricers use:** none publicly. **Edge:** low. These are national, monthly and
  collinear. Their value is regime detection for the **season-level ceiling and the floor
  posture**, set in October when holiday prices are fixed.

### 3.7 Geopolitical and international (8 streams: G01–G08)

- **FX (G01).**
  - FRED H.10 pairs are free: MXN was 18.40 on 2026-10-09.
  - The strong-dollar evidence is **STALE**. NSAA had international at 6% of US visits in
    2014-15 ([SAM](https://www.saminfo.com/news/sam-headline-news/14657-718-seasona-s-visits-drop-5-percent-to-53-6-million)).
    Vail blamed the strong dollar for its 2015-16 international decline
    ([Denver7](https://www.denver7.com/news/local-news/international-skiers-and-riders-look-to-other-countries-because-of-strong-us-dollar)).
  - The overseas share is about 3% for US resorts generally, with concentration in Vail,
    Aspen and Park City ([SnowBrains](https://snowbrains.com/snow-sanctions-and-sentiment-why-some-global-travelers-are-skipping-u-s-ski-slopes/)).
  - Winter Park's international share is **unknown** (dossier 01: assumed 4–8%).
- **Flows (G02, G03).**
  - NTTO I-94 arrivals: January 2026 at 5.41M, −3.5%. May 2026 Mexico +21% while overseas fell
    6.5% ([Inbound Travel / NTTO](https://www.inboundtravel.org/news/ntto-may-2026-international-travel-volume-tofrom-us)).
  - Canadian return trips from the US fell YoY for 15 straight months to March 2026, with air
    −10.8% in March ([BNN Bloomberg](https://www.bnnbloomberg.ca/business/economics/2026/05/21/canadian-travel-to-us-continues-downward-trend-new-statistics-canada-data-suggests/);
    [StatCan table 24-10-0053-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2410005301)).
  - DestiMetrics saw tariff threats raise Canadian cancellations in July 2026.
- **Mexico calendar (G08).** This is the one geopolitical-adjacent stream with precise timing.
  SEP's 2026-27 calendar (published in the DOF on 2026-07-15) puts the winter break at
  Dec 21, 2026 to about Jan 6, 2027, and **Semana Santa at Mar 22–Apr 2, 2027**, inside the ski
  season ([Infobae](https://www.infobae.com/mexico/2026/07/16/vacaciones-de-invierno-semana-santa-y-mas-las-fechas-del-ciclo-escolar-sep-2026-2027/);
  [UnoTV](https://www.unotv.com/nacional/sep-publica-calendario-escolar-2026-2027-vacaciones-puentes-y-fechas-clave/)).
- **Policy and conflict (G04–G07).**
  - State Department advisories: a JSON API is reported at `cadataapi.state.gov`, but the
    check was blocked by Cloudflare, so it is **UNVERIFIED**.
  - The Economic Policy Uncertainty index is free (Baker, Bloom & Davis 2016, *QJE*
    131(4):1593–1636; [policyuncertainty.com](https://www.policyuncertainty.com/)).
  - GDELT event counts are free and noisy.
  - Federal shutdowns are rare and summer-weighted (Rocky Mountain National Park).
- **How geopolitics actually reaches this engine.** Through **oil, airfare and sentiment**
  (E01, E04, E07, M01, M12), the **dollar** (G01, tiny share here), and **destination-pass
  demand** (R04). It does not reach the engine through any direct conflict feed. The operator
  asked for geopolitics to be considered, and the honest finding is that a conflict index adds
  nothing beyond oil and sentiment for this market. **Generic pricers use:** none. **Edge:**
  low, except G08.

### 3.8 Calendar (10 streams: C01–C10)

- **Holidays, Easter and school calendars set most of the high-value nights.**
  - Foley attributed a soft March to Easter falling after resorts closed.
  - Easter 2027 is **March 28**, inside the season.
  - Passover 2027 starts at sundown on **April 21** (Hebcal API, checked by request), so it
    misses most ski seasons.
- **Texas spring breaks for 2027** per aggregators: Dallas and Austin Mar 15–19, Houston
  Mar 8–12 ([publicschoolscalendar](https://publicschoolscalendar.com/dallas-isd-calendar-2026-2027/)).
  These are **UNVERIFIED** against the districts' own pages.
- **Adversarial finding:** aggregators **disagree** on Denver Public Schools' 2027 spring break:
  Mar 22–26 ([CalendarStates](https://calendarstates.com/colorado/denver-public-schools/))
  versus Mar 29–Apr 2 ([EduCounty](https://www.educounty.net/calendars/colorado/denver-public-schools/)).
  The DPS calendar URL returned 404. The collector must use **official district ICS/PDF only**,
  with a source URL per row.
- **Ikon Base** has unlimited Winter Park access, with blackouts **Dec 26–30 2026, Jan 16–17 and
  Feb 13–14 2027** ([Ikon](https://www.ikonpass.com/en/shop-passes/ikon-base-pass)).
- **Generic pricers use:** holidays and events, which every tool has
  ([PriceLabs](https://help.pricelabs.co/portal/en/kb/articles/demand-factor-sensitivity);
  Wheelhouse via [Lodgify](https://encyclopedia.lodgify.com/wheelhouse)). **None mention:**
  origin-market school calendars weighted by our origin mix, the Mexican SEP calendar, or Ikon
  blackout dates. **Edge:** moderate. These are deterministic, cheap, and applied to the
  highest-value nights.

### 3.9 Resort operations and the ski industry (8 streams: R01–R08)

- **Season dates (R01).** Mary Jane closed on 2026-03-27 at noon, early
  ([Denver Gazette](https://www.denvergazette.com/?p=545176)).
- **Lift and trail feed (R02).** The Intrawest feed is live: it returned "Closed for Season" with
  an update stamp of 2026-04-19. It is unofficial and can change without notice.
- **Lift tickets (R03).** The ticket store returned 403, so whether Winter Park prices tickets
  dynamically by date is **UNVERIFIED**.
- **Pass sales (R04).** These carry the strongest season-ahead read this year. Vail Resorts:
  - December 2025: units −2% and dollars +3%, with declines in Colorado, Utah and Tahoe local
    drive-to markets
    ([SEC](https://www.sec.gov/Archives/edgar/data/812011/000081201125000240/a20251031pressrelease.htm)).
  - September 2026: 2026/27 units −12%, days −10%, dollars −6%, with Destination products
    weakest (SEC 8-K above).
  - Alterra, which owns Winter Park, is private. The full Ikon Pass went from $1,329 to $1,349 with
    renewal or $1,399 new for 2026-27 (about +5% for new buyers only), and the 100%/50% refund applies
    only to the separate "Refundable" products
    ([Steamboat Pilot](https://www.steamboatpilot.com/news/ikon-pass-2026-27-on-sale-higher-price/)).
- **Industry totals (R05, R06).** NSAA 2025-26 (preliminary): about 52.6M visits, −14% (SAM).
  Colorado: 10.5M, −24% (preliminary, press coverage of the 2026-06-04 CSCUSA meeting).
  - These visit totals are backtest targets. They are not live leads.
- **Generic pricers use:** none. **Edge:** yes for live terrain status and season dates, and
  modest for pass sales as an October prior.

### 3.10 Regulation and supply (7 streams: P01–P07)

- **No machine-readable STR licence register** was found for the Town of Winter Park, Fraser or
  unincorporated Grand County.
  - Grand County runs annual permits through Munirevs
    ([FAQ](https://cograndcous.munirevs.com/faq)), with a reported occupancy cap of 16. That
    cap comes from a property manager's blog
    ([SkyRun](https://skyrun.com/blog/navigating-grand-countys-short-termrental-regulations/))
    and is **UNVERIFIED** with the county.
  - Fraser requires registration and, from 2025, a fire inspection (Ordinances
    [488](https://frasercolorado.com/DocumentCenter/View/1577/Ordinance-No-488-Short-Term-Registration-Fees)
    and [516](https://frasercolorado.com/DocumentCenter/View/2124/Ordinance-516-Amending-Chapter-6-Article-8-Short-Term-Rental-Registration)).
    No cap was found.
  - Winter Park's finance page offers lodging returns by email only
    ([wpgov.com/finance](https://wpgov.com/finance/)).
  - A Colorado Open Records Act (CORA) request is the route to the registers.
- **Lodging-tax collections (P04)** are the outcome series for H5 and for backtests.
  - They must be adjusted for Winter Park's lodging tax going from 1% to 3% in July 2024
    (dossier 03, [Sky-Hi News](https://www.skyhinews.com/news/winter-parks-lodging-tax-will-increase-to-3-in-july/)).
  - The Colorado Department of Revenue publishes accommodation (NAICS 721) sales by major city
    and county, with suppression marked "NR"
    ([DOR rev13026](https://spl.cde.state.co.us/artemis/revserials/rev13026internet/rev130262024internet.pdf)).
    Whether Grand County is broken out is **UNVERIFIED**.
- **Generic pricers use:** PriceLabs publishes regulation commentary: regulated ski markets
  saw 27–38% supply cuts and December–February ADR +11–17% (vendor,
  [PriceLabs](https://hello.pricelabs.co/blog/str-regulations-in-usa-ski-market/)). **Edge:**
  slow and structural. It belongs in the season ceiling, not nightly prices.

### 3.11 Competitor and substitute destinations (5 streams: X01–X05)

- **Relative snow (X01).** Relative snow is a demand driver in its own right. Gonseth found
  substitution between resorts, and Parthum & Christensen control for nearby-resort snowpack.
  `config/policies/markets.yaml` already lists SNOTEL for other markets, and
  `features/substitution.py` compares price-per-SQI.
- **Corridor substitution (X04).** The cheap and unique edge is I-70 versus US-40. When I-70 to
  Summit County is closed or jammed and Berthoud is open, Winter Park is the closest open
  big-mountain option from Denver. `cdot.py` reads only US-40 today.
- **Fly-in substitutes (X03).** DestiMetrics reported that Colorado and Utah both struggled in
  2025-26 while the "rest of the West" did better
  ([SAM](https://www.saminfo.com/news/sam-headline-news/western-destinations-lodging-trends-continued-in-february)).
- **Generic pricers use:** comps inside a radius only. **Edge:** yes.

### 3.12 Reputation and listing quality (4 streams: Q01–Q04)

- **Review velocity (Q01)** is the standard public-data proxy for comp bookings. Inside Airbnb
  converts reviews to occupancy using a 50% review rate times average stay
  ([Inside Airbnb](https://insideairbnb.com/data-assumptions/)). Our comps are few, so
  per-comp estimates are noisy, but review velocity is a useful check against the calendar
  "blocked vs booked" ambiguity.
- **Hedonic adjustment (Q04).** Hedonic STR price studies support adjusting comps for amenities
  and capacity (Wang & Nicolau 2017, *IJHM* 62:120–131).
- **Generic pricers use:** Airbnb uses reviews in its booking model (Ye et al.). PriceLabs
  mentions "perceived quality". **Edge:** small.

### 3.13 Anything else (8 streams: Z01–Z08)

- **Most valuable:** our own cancellation hazard (Z04), which is needed for correct pace.
- **Weak:** avalanche and closure history (Z01), Rocky Mountain NP visitation in summer (Z02),
  health and wastewater (Z03), and phone panels (Z06; dossier 01 advises against buying them).
- **Not pricing signals:** social and app proxies (S07, S08, Z07), wildfire smoke (W12, summer
  only), and power outages (E06, operations). They are catalogued so the universe is complete.

---

## 4. A-tier streams (17)

**Measurement feasibility (review fix 9).** The IC ≥ 0.05 / n ≥ 40 gate needs 40 independent
observations. With about 100 reservations of history and a winter lead time of about 72 days, the
short-lead subsets are small: bookings made within 7 days (W03, A01) and closure weeks (A01, X04) give a
handful of observations per season, so those tests cannot pass before 2027-28 on own data. School-break
streams (C01, C02, G08) have one or two windows per year, so their n is counted in **seasons**. Streams
with market-level outcomes (L01, L09, P04) can use market data or the simulator instead. R6 Part B
reports the n actually available for each test; use those counts, not row counts.

Each entry gives the mechanism, an implementable first version, evidence, the module affected,
and the measurement plan. **Measurement convention.** Field A/B tests cannot detect effects
under about 33% (shared context). So every A-tier stream is first scored **offline**: the
information coefficient (IC) of the signal against the **pickup residual**, meaning realized
pickup minus pace-model pickup, at matching lead time, on as-of data. This follows
`config/policies/signals.yaml` (shadow → active at IC ≥ 0.05, hit rate ≥ 0.52, n ≥ 40). The
owner-net effect is then measured in `proving_ground_exam/` against `current_practice`.

1. **L01 Own on-the-books pace (Guesty).**
   - Mechanism: residual demand equals expected final bookings minus bookings on the books.
   - First version: additive pickup (Weatherford & Kimes 2003). Expected final nights for
     stay date *d* = OTB(*d*, *t*) + mean historical pickup from lead *t* to 0 for comparable
     nights, pooled across the three homes and shrunk toward market pace (L09).
   - Decision rule: raise or cut within bounds when the pace ratio leaves a dead band.
   - Module: `src/pricing/pace.py`, already the candidate.
   - Measurement: forecast MAPE of final occupancy by lead bucket, and simulator owner-net.
2. **L02 Inquiries and quotes.**
   - Mechanism: each quote with an outcome is one point on the booking-probability curve.
   - First version: log every quote (price, LOS, party, lead) and its outcome, then fit a
     pooled logit P(book | price/anchor, lead, LOS).
   - Module: `src/elasticity`, `src/bookprob`.
   - Data needed: quote-to-outcome linkage, which dossier 02 says is missing.
   - Measurement: calibration (Brier) on held-out quotes.
3. **L06 / L13 Comp prices and calendars (5+ BR, sleeps 14+).**
   - Mechanism: WTP is anchored by the visible alternative set, and comp calendars closing up
     reveal market pickup.
   - Evidence: comp anchoring is in every generic pricer; PriceLabs uses about 350 comps within
     15 km.
   - Our specialization: party-fit comps (sleeps ≥ 12), all-in price including fees, and
     review velocity (Q01) to separate booked nights from owner blocks.
   - Module: `src/scrape`, `src/comps`, `src/signals/comp_movement.py`.
   - Measurement: share of nights with a valid anchor (today about 3%), and anchor staleness.
     Owner-net effect measured in the simulator.
4. **L07 AirDNA API (licensed comp and market fallback).**
   - Mechanism: the same as L06, but licensed. The **future pricing per listing** endpoint
     gives forward asking prices for named comps. Market endpoints give occupancy and lead-time
     levels with 12–60 months of history.
   - Risk: modelled occupancy, which no independent audit has checked, and unknown cost.
   - Decision: run a two-week trial on our comp IDs, then compare AirDNA future prices with our
     scraped quotes on the nights both cover.
   - Module: `src/comps` (new provider).
   - AirDNA's listing prices are also scraped from platform calendars and likely exclude
     cleaning and per-guest fees. The trial must compare **all-in, party-fit** prices and first check
     how many Grand County 5+ BR listings AirDNA covers.
   - Measurement: anchor coverage on nights with a party-fit all-in comp, and agreement within about
     10% on overlapping nights. "3% → 50%" is a target to test, not a promise.
5. **L09 Inntopia DestiMetrics.**
   - Mechanism: PM-reported on-the-books occupancy up to six months forward, which is real
     bookings rather than scraped calendars. It is the market-level prior for L01.
   - Evidence: the monthly briefings report pace, for example Jul–Dec pace +3.1% in July 2026
     ([SGB](https://sgbonline.com/destimetrics-market-briefing-july-2026/)).
   - Open question: whether Winter Park/Grand County is a participating destination. The
     public briefings do not name destinations.
   - Module: `src/pricing/pace.py` (market prior); `proving_ground_exam/` calibration.
   - Measurement: does the market pace ratio reduce our own pace-forecast error?
6. **W01 SNOTEL SWE (Berthoud Summit and neighbours).**
   - Mechanism: ski quality and terrain set trip value.
   - Prior: Parthum & Christensen report a Colorado STR revenue elasticity of about 0.135 to
     resort-reported snow depth. Appendix C withdraws using that figure as a season SWE
     multiplier. It is a stale within-property-month result (2014–17). `(SWE/normal)^0.135`
     (about 0.93 at 60% of normal) is an extrapolation to test, not a prior to ship.
   - First version: already feeds SQI. Do **not** add it as a separate price signal, or it is
     double-counted, and do **not** size a drought cut from this coefficient.
   - Module: `src/signals/features/sqi.py`, `src/ceiling`.
   - Measurement: IC of SQI against pickup residual over seasons; a simulator sweep of the SQI
     weight.
7. **W03 NWS gridpoint forecast (snowfallAmount, windGust).** *Re-tiered to **B** in the fix pass
   (catalog): W03 and W04 are one short-lead forecast signal with the provider as an access attribute,
   and its own pull-forward effect is UNVERIFIED with small short-lead n. Kept here for the design;
   Z04 (below) took its A slot.*
   - Mechanism: storms 1–7 days out move short-lead demand. Snow pulls skiers, while a severe
     storm with a chain law or closure risk pushes them away. Wind forecasts predict lift holds.
   - Evidence: the 2–10 day booking elasticity of 0.124–0.152 (Parthum & Christensen). A powder
     pull-forward effect is **UNVERIFIED**.
   - First version: daily as-of snapshots of 72-hour and 7-day snowfall totals. Rule inside
     7 days: a forecast of ≥ 12 in. over 72 hours before an unsold weekend means hold rather
     than run the last-minute discount, unless the access risk from A01/W11 is high.
   - Also replaces the commercial-use problem with Open-Meteo.
   - Module: `src/signals/collectors/weather.py`, `src/pricing` (last-minute logic).
   - Measurement: IC on pickup residual for nights within 7 days.
8. **W08 Resort-reported snow and terrain** (already ingested).
   - Mechanism: what shoppers see, such as new snow and terrain %.
   - Module: `collectors/resort.py`, `features/resort_ops.py`.
   - Measurement: same IC test. Must be checked for collinearity with W01.
9. **A01 US-40/Berthoud closures and chain law** (not live). The current parser calls `cotrip.org/api/alerts`, which returns an HTML shell, and can store a zero closure as good data. Appendix C is controlling: use a JSON feed such as CARS 511 and fail closed on non-JSON.
   - Mechanism: a closure or chain law cuts same-week Front Range arrivals and drives
     cancellations. No comp-price feed can see it.
   - Rule: on a high access-risk forecast for arrival day, do not discount into it, because the
     demand is not there. Instead hold, and loosen minimum stay for the days after.
   - Module: `features/access.py`, `src/min_stay`.
   - Measurement: cancellations and pickup in closure weeks versus matched weeks.
10. **C01 Front Range school calendars.** Breaks set family travel windows. The first version
    is an official ICS-sourced date table per district, weighted by origin share (Denver metro
    first, per dossier 01 and DMO data), feeding the `demand_strength` field the
    `calendars.py` collector already defines. Module: `collectors/calendars.py`,
    `src/ceiling`. Measurement: pickup and ADR on break nights versus non-break nights,
    year-on-year.
11. **C02 Fly/drive-in origin school calendars** (Texas, Oklahoma, Kansas, Nebraska, Midwest).
    Same mechanism and implementation as C01. The Texas mid-March weeks decide March pricing.
12. **C04 Federal holidays and their weekday positions.** Deterministic. Module: `src/ceiling`,
    `src/min_stay`. Everyone has this. Our edge is only in interacting it with C01 and C02.
13. **C05 Easter position.** Easter inside or outside the season shifts spring demand (Foley).
    2027: March 28, inside. A deterministic feature.
14. **R01 Season open and close dates (including Mary Jane).** Set the ski-demand boundary. Rule:
    after the announced close, switch to shoulder pricing. Before it, the SQI-conditional close
    risk widens the floor posture. Module: `config/resort/winter_park.yaml`,
    `features/resort_ops.py`.
15. **R02 Live lift and trail status.**
    - Mechanism: terrain open % early season drives holiday WTP.
    - First version: already in `resort_ops`. Add an as-of store because the feed has no
      history.
    - Measurement: IC on December pickup residual.
16. **P04 Lodging-tax collections (Winter Park, Fraser, Grand County; DOR NAICS 721).** The only
    public market-revenue outcome series. Needed to test H5 (about 70% winter share) and to
    validate the simulator's seasonality. Must be adjusted for the July 2024 rate change.
    Module: `proving_ground_exam/` calibration. It does not affect live pricing.
17. **X01 Relative snow at substitute resorts.**
    - Mechanism: better snow nearby pulls share away (Gonseth 2013), so Winter Park's relative
      SQI matters as well as its absolute SQI.
    - First version: SQI(home) / median SQI(Summit County, Steamboat), which `substitution.py`
      already computes per price.
    - Measurement: IC of the relative-SQI term after controlling for the absolute term.
18. **Z04 Own cancellation and modification flow by lead time** (A since the fix pass).
    - Mechanism: cancellations after storms or closures release inventory, and pace that ignores
      them overstates on-the-books (the review's point that refundable bookings inflate "ahead of
      pace"). It is an input to L01.
    - Evidence: 13 own cancellations since onboarding (Dossier 02), far too few to fit.
    - First version: a cancellation hazard by lead time from a literature or market prior, updated
      with own data; pace counts bookings net of expected cancellations.
    - Module: `src/pms/sync.py` (source), `src/pricing/pace.py`, `src/bookprob`.
    - Measurement: calibration of predicted vs realized cancellations by lead bucket, pooled across
      seasons.

L13 (party-fit comps) is folded into L06 above. Party-fit comps are the comp set that actually
substitutes for a 16-guest home.

---

## 5. What generic STR pricers use vs. the specialist edge

Sources: [PriceLabs algorithm part 1](https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/),
[PriceLabs demand factor](https://help.pricelabs.co/portal/en/kb/articles/demand-factor-sensitivity),
[Wheelhouse CompSets](https://usewheelhouse.com/blog/?p=4469) and
[Lodgify on Wheelhouse](https://encyclopedia.lodgify.com/wheelhouse),
[Beyond search-powered pricing](https://beyondpricing.com/blog/search-powered-pricing-from-beyond-adds-5m-in-revenue-for-our-customers-here-s-how-we-did-it),
and Airbnb Smart Pricing (Ye et al., KDD 2018,
[summary](https://blog.acolyer.org/2018/10/03/customized-regression-model-for-airbnb-dynamic-pricing/);
[talk](https://videolectures.net/kdd2018_ye_airbnb_dynamic_pricing)).
All of these are vendors describing their own products. Absence from the public docs is **not
proof** that a tool lacks the input, and R4 should probe further.

| Category | Used by at least one generic pricer (public docs) | Mentioned by none (specialist edge) |
|---|---|---|
| 1 Lodging | Comps (radius, about 350 in 15 km), market pacing and pickup, hotel rates, own bookings, block removal | Party-fit 5+ BR comp set, all-in fee-inclusive comparison, DestiMetrics PM-reported pace |
| 2 Intent | Search (Beyond Beacon; Airbnb search/contact rates and views) | Google Trends by origin DMA (weak), fly-in fare level by origin |
| 3 Snow/weather | None (PriceLabs: ski season "less price sensitive", seasonal only) | SNOTEL, NWS snowfall, CPC outlooks, ENSO, snowmaking windows |
| 4 Access | None | US-40/Berthoud closures, I-70 vs US-40 substitution, WP Express sell-outs |
| 5 Energy | None | Gasoline, STEO forward (test H4) |
| 6 Macro | None | Season-level regime: sentiment, S&P, recession |
| 7 Geopolitical | None | SEP Mexico calendar; oil shock; FX (small here) |
| 8 Calendar | Holidays, events, day of week | Origin-weighted school calendars, Ikon blackouts, Semana Santa |
| 9 Resort ops | None | Terrain %, lift holds, season close, pass-sales prior |
| 10 Regulation | Commentary only (PriceLabs) | Licence counts as a supply lead |
| 11 Substitutes | Implicitly via radius comps | Relative snow and corridor substitution |
| 12 Reputation | Reviews (Airbnb), "perceived quality" (PriceLabs) | Review velocity as a booked-vs-blocked check |
| 13 Other | — | Own cancellation hazard by storm and closure |

**H2 verdict (for R6 and S1).**
- **Partly supported.** Generic pricers do not collect snow, road, resort-ops or
  origin-calendar data, and those streams plausibly move Winter Park demand.
- **Not supported** for pace data, and **UNVERIFIED** for search data. The platforms have search
  data we cannot see, but Lighthouse (formerly Transparent) markets a Market Insight product with
  forward demand and search-volume data that may be licensable (vendor claim, UNVERIFIED).
- **Unknown** for the size of the gap. The STR snow prior (Colorado 0.135, short-run, STALE) and
  the Austrian overnight-stay studies imply single-digit-percent effects in most seasons, but
  2025-26 fell much further. That is real money on $2k+ nights, but
  below what a three-home field test can detect.

---

## 6. Ranked recommendations

| # | Recommendation | Expected impact (owner-net) | Confidence | Effort | Data needed | Measurement |
|---|---|---|---|---|---|---|
| R0 | Repoint A01 to the CARS 511 feed and fail closed (`QUALITY_UNAVAILABLE`) on a non-JSON response; test the parser for whole-payload keyword false positives. **Status 2026-10-19:** implemented in commit `d3e8b92` after this dossier was written; live behaviour not yet verified. | Prevents a silent false "road open" on the highest-impact access nights | High | Low | CARS 511 feed | Share of runs stored as unavailable vs ok; manual check on a known closure day |
| R1 | Fix comp anchoring first. Run a 2-week AirDNA API trial (future pricing per listing for our party-fit comps) alongside the scraper, and add review velocity (Q01) to separate booked from blocked nights. | Highest. Without anchors the pace-plus-elasticity candidate runs mostly unanchored. Size UNVERIFIED; the simulator should quantify it. | Medium | Medium | AirDNA trial key; comp listing IDs | Anchor coverage on nights with a party-fit **all-in** comp (target 3% → ≥50%, after checking Grand County 5+ BR coverage); agreement with scraped quotes; simulator owner-net with vs without anchors |
| R2 | Ask Inntopia whether Grand County/Winter Park participates in DestiMetrics, and whether Mont Luxe can join as a data-submitting partner for the property-vs-destination report (whether that report is free is UNVERIFIED). | High. A market on-the-books prior for thin own pace. | Medium | Low | Twice-monthly submission of own aggregates | Pace-forecast MAPE with vs without the market prior |
| R3 | Move the short-range forecast to NWS `api.weather.gov` (public domain), or buy an Open-Meteo commercial plan. Store daily as-of snapshots. | Compliance fix plus the inside-7-day storm rule (§4.7) | High (licence); low–medium (effect) | Low | None | IC on pickup residual within 7 days |
| R4 | Add I-70 events to `cdot.py` and build the I-70-closed / US-40-open substitution flag (X04). | Small but unique. Same-week, high-value weekends. | Medium | Low | COtrip CARS feed | Pickup on flagged vs matched days |
| R5 | Test H4 before using gasoline. Regress a US-40 count (A03) and Winter Park lodging-tax receipts on EIA Colorado gasoline, with Eisenhower counts (A02) as a substitute-corridor control, controlling for SNOTEL, holidays/Easter and the 2020-21 regime. Weight the prior by origin (C02). Keep `macro.eia_gasoline` in shadow. | Small for Denver parties (+$1/gal ≈ 0.3–0.4% of the stay); 2–5% for TX/KS/OK drive-in groups. Matters for market comps. R7 later found no winter effect, bounded small. | Low | Low | A02, E01, W01, P04 | Coefficient and CI. Promote only if IC ≥ 0.05 on pickup residuals. |
| R6 | Build an official-source calendar table: district ICS for C01/C02, SEP for G08, Ikon blackouts (C07), Easter. Keep a provenance URL per row and reject aggregators. | Moderate, on the highest-value nights | High | Low | Annual manual refresh | ADR and pickup on break nights, YoY |
| R7 | Add an October season-regime input for the ceiling and floor posture: Vail pass-sales change (R04), Conference Board vacation intentions (licence) or UMich (FRED), S&P drawdown, and Brent/STEO. Use it to set holiday-price aggressiveness, not nightly price. | Moderate in shock years such as 2026-27 | Low–medium | Low | Free FRED and SEC; CB licence optional | Simulator scenario sweep; realized holiday sell-through vs posture |
| R8 | Use the Parthum & Christensen prior (Colorado 0.135; short-run, resort depth, STALE) for the **W08** resort-depth component of SQI only, use relative SQI (X01), and do not size a season or drought multiplier from it. Do not add SNOTEL as a second signal. | Small–moderate | Medium | Low | Existing | SQI IC by season; simulator sweep |
| R9 | Log quote → outcome for every inquiry (L02). | Enables elasticity learning | High | Low–medium | Guesty quotes/inquiries API (beta) | Brier score of the booking-probability model |
| R10 | Request STR licence registers (Winter Park, Fraser, Grand County) once a year under CORA. | Small, season-level | Medium | Low | Records request | Licence count vs AirDNA supply trend |

Deliberately **not** recommended for live pricing:
- Google Trends, unless an offline IC test passes. Sampling noise, a low-volume query, and the
  name clash with Winter Park, Florida all count against it.
- Social or Reddit buzz.
- Conflict indices (GDELT/EPU), which add nothing beyond oil and sentiment.
- DEN or TSA volume, diluted by the hub.
- Phone-panel data.

---

## 7. Open questions for the operator

1. Is Mont Luxe, or the local PM you spoke with, a DestiMetrics data-submitting partner? Does
   Grand County's tourism board fund DestiMetrics or Key Data?
2. Budget appetite for a licensed comp feed (AirDNA or Key Data), given the scraper's 67%
   failure rate.
3. Can you export Airbnb host-insights views and conversion for the three homes once a week?
   This is manual, and ToS-safe if copied by hand.
4. Do your guests' origins match dossier 01, with Denver first, or do Texas and the Midwest
   dominate the winter? This decides which school calendars to weight.
5. Have you seen guests cancel or shorten stays for Berthoud closures? How often per winter?
6. Is the Open-Meteo usage covered by any agreement? If not, R3 is a compliance item.

---

## 8. Self-audit (every MUST in `00_DEPTH_STANDARD.md`)

| MUST | Status | Evidence |
|---|---|---|
| Cite every non-obvious claim inline with URL and access date | PASS | Inline URLs throughout; one access date (2026-10-16) stated in the header; catalog `prior_evidence` column |
| ≥ 40 distinct sources | PASS | Appendix B: 86 numbered source entries holding 127 distinct URLs (129 distinct URLs in the whole document) |
| ≥ 4 source classes | PASS | All 7 classes, counted by Appendix B entry: [1] academic 12, [2] textbook 1, [3] vendor docs 22, [4] industry body 6, [5] filings 2, [6] government/official 19, [7] trade press/practitioner 24 |
| Read primary sources where they exist; note paywalls | PASS, with exceptions | Primary read: Parthum & Christensen (PMC full text), Vail 8-K, API docs, EIA/FRED/NWS/AWDB live. Abstract or summary only: Pan 2012 (Emerald abstract plus PolyU record), Havranek & Zeynalov (RePEc), Ye et al. (Morning Paper summary; KDD PDF not opened), Weatherford & Kimes (search summary of the Cornell PDF), Gonseth/Falk (abstracts). CDOT CTIO deck returned 404. |
| Mark UNVERIFIED and STALE | PARTIAL (revised 2026-10-19) | Marked inline and in the catalog, but the review found Parthum & Christensen (2014–17) unmarked STALE and the −24% and DestiMetrics free-report claims unqualified; corrected in §1 and §6 |
| No invented statistics or citations | PASS (self-check) | Every number is traceable to a cited page or a logged request; unknown prices left UNVERIFIED |
| Several search passes (broad, specific, adversarial) | PASS | 73 searches; adversarial set: Trends sampling, Google Flu, AirDNA accuracy, hiQ/scraping, gas vs skier days (extended), weather-forecast effect, aggregator calendar conflicts |
| Explain mechanisms with implementable detail | PASS | §4: inputs, first version, decision rule per A-tier stream; catalog `mechanism` column for all 121 |
| Quantified evidence with measurer and conflict noted | PASS | Parthum & Christensen (independent academics); Beyond $5M (vendor, method undisclosed); PriceLabs supply/ADR (vendor); Goldman (bank research) |
| Map every finding to engine module and owner-net measurement | PASS | §4 and §6; catalog `already_in_repo` column |
| Assess transferability honestly | PARTIAL (revised 2026-10-19) | The snow coefficient was transferred to the wrong variable and timescale, and the gas arithmetic covered only Denver; both corrected (§1, §3.5) |
| "What generic STR pricers miss" note | PASS | §5 table plus per-category notes |
| End with ranked recommendations, open questions, self-audit | PASS | §6, §7, §8 |
| Search log appendix | PASS | Appendix A |
| Prefer 2020–2026 sources plus classics | PASS | Most sources 2022–2026; classics: Weatherford & Kimes 2003, Talluri & van Ryzin 2004, Pan 2012 |
| Adversarial pass after finishing | PASS | Contradictions recorded: DestiMetrics luxury +11.5% vs "negativity spreading"; Vail local markets improving vs destination weak; no gas-to-skier study; aggregator calendar disagreement |
| R5-specific: ≥ 80 streams | PASS | 121 rows |
| R5: every A-tier stream gets a paragraph with sources | PASS | §4 (17 current A rows; L13 is folded into L06) |
| R5: generic vs none per category | PASS | §3 per category plus §5 |
| R5: verify access for every A and B source | PARTIAL (revised 2026-10-19; A01 was listed as live but returned an HTML shell) | Endpoint or page loaded for all A and B rows except: Airbnb host insights (behind login; page 200), Winter Park ticket store (403), DEN reports (403), Vail IR site (403, but the SEC 8-K was read), State Dept API (Cloudflare), DPS official calendar (404), CDOT CTIO WP Express deck (404). Each is marked UNVERIFIED in the catalog. |
| R5: no large datasets | PASS | Only single small responses (status, one JSON page, CSV tail) |

---

## Appendix A. Search and verification log

S = WebSearch, F = WebFetch, C = direct HTTP check (one small response). "→" = what it yielded.

**Broad and specific passes**
1. S DestiMetrics briefing 2026 → SGB July 2026 briefing (17 destinations; Jul–Dec pace +3.1%; Canada cancellations); SAM winter 2025/26 occupancy −7%, ADR +1.2%
2. S Key Data Winter Park → Visit NC partner page (DMO tier from $8,500); AirDNA Winter Park 1,881 listings, −5.9%
3. S AirDNA API docs → docs.airdna.co, airdna.redoc.ly
4. S PriceLabs Market Dashboard pacing → PriceLabs blog; no public market-data API
5. F docs.airdna.co → 403
6. F SGB DestiMetrics July 2026 → pace, luxury +11.5%, origin mix by country
7. F airdna.redoc.ly → packages, 12–60 months history, future pricing per listing
8. S DestiMetrics Grand County → no destination breakdown public
9. S Grand County STR licence list → Munirevs portal, SkyRun (secondary), no public list
10. S Fraser STR cap → Ordinances 488/516, no cap
11. S Winter Park STR Rentalscape → nothing for Winter Park, CO
12. S Winter Park sales-tax report → nothing new
13. S CO DOR county sales → rev111 monthly county series
14. S Transparent API → no public API; EUR 2,500/yr per market (vendor listing)
15. F WP 2024-12 sales-tax PDF → binary, unreadable (no PDF tools available)
16. S wpgov sales tax → none
17. F wpgov.com/finance → lodging returns by email only
18. S Google Trends API alpha → Search Central blog July 2025
19. S Google Trends hotel demand papers → Havranek & Zeynalov; Caribbean MIDAS; Malta
20. S Airbnb search predicting bookings → CBS Lassen; arXiv 2602.18358
21. F Trends API blog → truncated; details from search snippets
22. S Pan, Wu & Song 2012 → JHTT 3(3):196–210
23. S snowfall vs skier visits → Falk 2015; Gonseth 2013; Parthum & Christensen; UO thesis
24. S (extended) powder day last-minute bookings → no empirical study
25. F PMC10936566 → Parthum & Christensen 2022 elasticities
26. F UO thesis page → title only
27. F AWDB Swagger UI → empty; C AWDB `v3/api-docs` → 4 paths verified
28. S AWDB forecasts → CRAN awdb, TSTool
29. S api.weather.gov snowfall → NWS memos; C NWS points + gridpoint → `snowfallAmount` verified
30. C CPC GIS FTP → archive to 2011; C Open-Meteo forecast and ensemble → verified
31. F Open-Meteo pricing → free tier non-commercial
32. S Open-Meteo historical forecast → 2021+ and Previous Runs 2024+
33. S OpenSnow API → commercial partners only
34. S SNODAS → NSIDC G02158
35. S CDOT OTIS Eisenhower → monthly table, station 000106 hourly
36. S COtrip API → CARS host (no key, community); XML feeds with registration
37. S CAIC API → none documented; Berthoud avalanche closures
38. F CDOT Eisenhower counts → 2000–Aug 2026 table values
39. F Hermes COtrip plugin → host `api-511x-co.carsprogram.org`
40. S Berthoud AADT → none found; Sept 2026 rock-mitigation holds
41. C OTIS, CARS host, data.colorado.gov → 200
42. S I-70 congestion survey → I-70 Coalition/RRC (STALE)
43. S WP Express 2026-27 → Amtrak promo page; CTIO recap snippet
44. S DEN monthly traffic → reports page, 2025 record
45. F CTIO WP Express deck → 404
46. S TSA throughput → FOIA weekly PDFs
47. S BTS DB1B → BTS FAQ; 40% sample from July 2025
48. S Amadeus self-service → shut down 2026-07-17
49. S SerpApi Google Flights → price_insights
50. S OAG/Cirium DEN capacity → nothing public
51. F EIA weekly gasoline page → Denver, Colorado, PADD 4 series
52. S gas prices and tourism elasticity → national-parks panel; Oh & Hammitt
53. S AAA Colorado gas API → none
54. C EIA API (key required); EIA Denver history from 2000-06; FRED UMCSENT
55. S Destination Analysts tracker → Future Partners, Longwoods
56. S wealth effect and luxury travel → Visa; Goldman via CNBC
57. S Conference Board vacation series → premium dataset; since 1978 (Skift)
58. S Deloitte holiday survey → 2025 high-income cuts
59. S NTTO I-94 → data.gov ITA-0033; 2026 monthly releases
60. S StatCan Canadian trips → 15-month decline
61. S FX and ski visitation → NSAA 2014-15, Vail 2015-16 (STALE)
62. S State Dept advisories API → `cadataapi.state.gov` (community)
63. C State Dept API → Cloudflare block; FRED DEXMXUS, SAHMREALTIME, SP500, DENV708URN → verified
64. S SEP 2026-27 calendar → winter break and Semana Santa dates
65. S Texas spring break 2027 → aggregators
66. S Hebcal API → developer page
67. S WP events and FIS 2026-27 → not confirmed; Mary Jane closure
68. S DPS/Jeffco calendars → **failed (session limit)**
69. S Denver conventions 2027 → denverconvention.com listings
70. F Hebcal → session limit
71. C Intrawest feed, Guesty docs, Hebcal (Passover 2027) → verified
72. S PriceLabs algorithm factors → help and blog
73. S Airbnb KDD 2018 → Morning Paper, VideoLectures
74. S Wheelhouse data sources → CompSets 101, Lodgify
75. S Beyond search-powered pricing → Beyond blog
76. F PriceLabs part 1 → full input list; no weather/snow/search/macro
77. F Beyond blog → claims; method undisclosed
78. F Morning Paper (Ye et al.) → feature list
79. S Inntopia participation → help page, tiers
80. F Guesty Open API → API areas
81. S Vail pass sales Dec 2025 → SEC 8-K
82. F Inntopia DestiMetrics overview → 6-month forward window, subscriber-only
83. S Vail FY2026 Q4 → 8-K Sept 2026
84. S Ikon 2026-27 → prices, refund policy
85. F Vail 8-K FY2026 → pass-sales quotes
86. F PriceLabs Market Dashboard help → $9.99/month
87. F keydata.co (after 301) → PMS-direct, API
88. F Conference Board → Sept 2026 81.9, licence terms
89. F SerpApi docs → parameters and fields
90. F WP ticket store → 403
91. S Ikon blackout dates → TPG, Sun Peaks
92. S DPS 2026-27 spring break → aggregators conflict
93. F dpsk12.org/calendar → 404
94. F Ikon Base page → blackout dates; Winter Park unlimited
95. S DOR NAICS 721 → rev13025/rev13026 series

**Adversarial pass**

96. S Lazer et al. 2014 Google Flu → *Science* 343
97. S AirDNA accuracy critique → no independent audit
98. S weather forecast and hotel bookings → PolyU paper; anecdotes
99. S (extended) gas prices vs Colorado skier days → no study; EIA $4.02
100. F Aspen Times 2026-04-04 → Iran war, Hormuz, Grand County $4.113
101. S CSCUSA 2025-26 → −24%, 10.5M
102. C EIA Colorado weekly (Oct 2026), FRED Brent, jet fuel, CPI airfare → verified
103. S EIA STEO October 2026 → Brent September average $114
104. F Steamboat Pilot (Foley) → quotes
105. S Inside Airbnb review-rate method → data assumptions page
106. S hiQ v. LinkedIn → CFAA vs contract
107. C 26 B-tier source pages → mostly 200 (failures listed in §8)
108. C StatCan table title, CSCUSA release text → verified
109. S Google Trends sampling critique → arXiv 2504.07032, MZES, EDML 2020
110. S Havranek & Zeynalov → *Tourism Economics* 27(1)
111. S Weatherford & Kimes 2003 → *IJF* 19(3)
112. C 9 more source pages (events, SEP, Airbnb insights, Transparent, STEO, US Travel 403, SerpApi hotels, Reddit API, PriceLabs MD) → status checked

Totals: **73 WebSearch** (1 failed on the session limit), **about 30 WebFetch**, **about 40 HTTP
checks**.

---

## Appendix B. Sources

Class codes: [1] academic, [2] textbook, [3] vendor docs, [4] industry body, [5] filing,
[6] government/official, [7] trade press/practitioner.

**[1] Academic**
1. Parthum, B. & Christensen, P. (2022). A market for snow. *JEEM* 113. https://pmc.ncbi.nlm.nih.gov/articles/PMC10936566
2. Pan, B., Wu, D.C. & Song, H. (2012). *JHTT* 3(3):196–210. https://www.emerald.com/insight/content/doi/10.1108/17579881211264486/full/html ; https://ira.lib.polyu.edu.hk/handle/10397/25564
3. Havranek, T. & Zeynalov, A. (2021). *Tourism Economics* 27(1):129–148. https://ideas.repec.org/a/sae/toueco/v27y2021i1p129-148.html
4. Lazer, D. et al. (2014). *Science* 343:1203–1205. https://dash.harvard.edu/handle/1/12016836
5. Weatherford, L. & Kimes, S. (2003). *IJF* 19(3):401–415. https://ecommons.cornell.edu/bitstream/handle/1813/72130/Kimes30_Comparison_of_Forecasting.pdf
6. Ye, P. et al. (2018). Customized regression model for Airbnb dynamic pricing. KDD. https://videolectures.net/kdd2018_ye_airbnb_dynamic_pricing ; https://blog.acolyer.org/2018/10/03/customized-regression-model-for-airbnb-dynamic-pricing/
7. Falk, M. (2015). Snow depth and skier days. https://gfr.ersa.org/wp-content/uploads/2015/03/falk_schweden.pdf
8. Gonseth, C. (2013). *Climatic Change* 119:307–320. https://ideas.repec.org/a/spr/climat/v119y2013i2p307-320.html
9. Oh, C.-O. & Hammitt, W. (2011). *Tourism Economics* 17(6). https://ideas.repec.org/a/sae/toueco/v17y2011i6p1311-1324.html
10. National-park visitation and fuel prices (2026). *JPRA*. https://js.sagamorepub.com/index.php/jpra/article/view/13064
11. Google Trends preprocessing (2025). arXiv 2504.07032. https://arxiv.org/pdf/2504.07032 ; Hölzl et al. (MZES): https://www.mzes.uni-mannheim.de/en/publications/details/default-1b90339871013c563d9e0770aa21fed2-44 ; Behnen et al. (EDML 2020): https://imada.sdu.dk/Research/EDML/2020/EDML20_paper_5.pdf
12. Baker, Bloom & Davis (2016), *QJE* 131(4); Estrella & Mishkin (1998), *Review of Economics and Statistics* 80(1); Wang & Nicolau (2017), *IJHM* 62:120–131 (bibliographic; not opened this pass)

**[2] Textbook**
13. Talluri, K. & van Ryzin, G. (2004). *The Theory and Practice of Revenue Management*. Springer. Ch. 9 (forecasting).

**[3] Vendor docs**
14. AirDNA API reference https://airdna.redoc.ly/ ; supply page https://www.airdna.co/vacation-rental-data/app/us/colorado/winter-park/supply
15. PriceLabs algorithm part 1 https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/ ; demand factor https://help.pricelabs.co/portal/en/kb/articles/demand-factor-sensitivity ; Market Dashboard https://help.pricelabs.co/portal/en/kb/articles/market-dashboard ; ski regulation https://hello.pricelabs.co/blog/str-regulations-in-usa-ski-market/
16. Wheelhouse https://usewheelhouse.com/blog/?p=4469 ; Lodgify https://encyclopedia.lodgify.com/wheelhouse
17. Beyond https://beyondpricing.com/blog/search-powered-pricing-from-beyond-adds-5m-in-revenue-for-our-customers-here-s-how-we-did-it
18. Guesty Open API https://open-api-docs.guesty.com/
19. Inntopia DestiMetrics https://help.inntopia.com/1378090/Content/Intelligence/DestiMetrics_Overview.htm
20. Key Data https://www.keydata.co/ ; https://partners.visitnc.com/key-data-vacation-rental-data-1
21. Transparent https://seetransparent.com/
22. Open-Meteo pricing https://open-meteo.com/en/pricing ; previous runs https://openmeteo.substack.com/p/weather-forecasts-from-previous-model-runs
23. OpenSnow API https://opensnow.com/api/index.html
24. SerpApi Google Flights https://serpapi.com/google-flights-api ; Google Hotels https://serpapi.com/google-hotels-api
25. Hebcal https://www.hebcal.com/home/developer-apis
26. Intrawest/Alterra lift feed https://snowreporting.herokuapp.com/feed/5/lifts
27. Ikon Base Pass https://www.ikonpass.com/en/shop-passes/ikon-base-pass
28. Airbtics on AirDNA https://airbtics.com/how-accurate-is-airdna/ ; Rabbu https://rabbu.com/airbnb-data/winter-park-co
29. COtrip community plugin https://hermes-agent.nousresearch.com/docs/plugins/colorado-traffic ; cotrip-feed https://github.com/jfredrickson/cotrip-feed
30. Inside Airbnb https://insideairbnb.com/data-assumptions/
31. Google Trends API https://developers.google.com/search/blog/2025/07/trends-api
32. Datafy https://www.datafyhq.com/ ; OAG https://www.oag.com/ ; Placer.ai https://www.placer.ai/
33. Reddit API https://www.reddit.com/dev/api/ ; GA4 Data API https://developers.google.com/analytics/devguides/reporting/data/v1
34. Deckard/Rentalscape https://www.rentalscaleup.com/rentalscape/
35. SkyRun Grand County STR https://skyrun.com/blog/navigating-grand-countys-short-termrental-regulations/

**[4] Industry body**
36. NSAA https://www.nsaa.org/ ; SAM on NSAA 2014-15 https://www.saminfo.com/news/sam-headline-news/14657-718-seasona-s-visits-drop-5-percent-to-53-6-million
37. Colorado Ski Country USA https://media.coloradoski.com/2025-26-projected-skier-visits
38. The Conference Board https://www.conference-board.org/topics/consumer-confidence
39. U.S. Travel Association https://www.ustravel.org/research (403 on check)
40. I-70 Coalition / RRC (via Summit Daily) https://www.summitdaily.com/news/new-i-70-study-shows-congestion-is-leading-some-skiers-to-make-fewer-trips-to-the-mountains/
41. Grand County Colorado Tourism Board 2024 report https://www.visitgrandcounty.com/wp-content/uploads/2025/07/GCCTB_AnnualReport_2024.docx-FINAL-ua.pdf

**[5] Filings**
42. Vail Resorts 8-K Sept 2026 https://www.sec.gov/Archives/edgar/data/0000812011/000081201126000048/a20260731pressrelease.htm
43. Vail Resorts 8-K Dec 2025 https://www.sec.gov/Archives/edgar/data/812011/000081201125000240/a20251031pressrelease.htm

**[6] Government / official**
44. NRCS AWDB REST https://wcc.sc.egov.usda.gov/awdbRestApi/v3/api-docs
45. NWS API https://api.weather.gov/gridpoints/BOU/37,70
46. NOAA CPC ONI https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt ; GIS outlooks https://ftp.cpc.ncep.noaa.gov/GIS/us_tempprcpfcst/
47. NSIDC SNODAS https://nsidc.org/data/g02158
48. EIA weekly gasoline https://www.eia.gov/dnav/pet/pet_pri_gnd_dcus_nus_w.htm ; EIA API https://www.eia.gov/opendata/register.php ; STEO https://www.eia.gov/outlooks/steo/archives/oct26.pdf
49. FRED: UMCSENT https://fred.stlouisfed.org/series/UMCSENT ; SP500 ; SAHMREALTIME https://fred.stlouisfed.org/series/SAHMREALTIME ; DEXMXUS https://fred.stlouisfed.org/series/DEXMXUS ; DENV708URN https://fred.stlouisfed.org/series/DENV708URN ; DCOILBRENTEU ; DJFUELUSGULF ; CUSR0000SETG01 https://fred.stlouisfed.org/series/CUSR0000SETG01
50. CDOT Eisenhower counts https://www.codot.gov/travel/eisenhower-tunnel/trafficcounts ; OTIS https://dtdapps.codot.gov/otis/TrafficData ; COtrip https://www.cotrip.org/ ; CDOT news (Berthoud 2024) https://codot.gov/news/2024/january/us-40-berthoud-pass-to-remain-closed-overnight ; US-40 holds Sept 2026 https://www.codot.gov/news/2026/september-2026-news/us40-berthoudpass-traffic-holds-scheduled-sept21
51. BTS TranStats DB1B https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EFI ; BTS FAQ https://transportation.libanswers.com/faq/166146
52. TSA throughput https://catalog.data.gov/dataset/tsa-foia-reading-room-weekly-passenger-throughput-data
53. NTTO I-94 https://catalog.data.gov/dataset/i-94-arrivals-monthly-quarterly-and-annual
54. Statistics Canada https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2410005301
55. US State Dept advisories https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html
56. SEP / DOF https://www.gob.mx/sep
57. Town of Fraser ordinances 488/516 (URLs in §3.10); Town of Winter Park https://wpgov.com/finance/ ; Grand County Munirevs https://cograndcous.munirevs.com/faq
58. Colorado DOR statistics https://spl.cde.state.co.us/artemis/revserials/rev13026internet/rev130262024internet.pdf ; rev111 series https://spl.cde.state.co.us/artemis/revserials/rev111internet/
59. DEN https://www.flydenver.com/press-release/denver-international-airport-sees-slight-growth-in-passenger-traffic-over-previous-year/
60. Amtrak Winter Park Express https://www.amtrak.com/promotions/WinterParkExpress
61. NPS IRMA https://irma.nps.gov/Stats/ ; AirNow https://docs.airnowapi.org/ ; NREL AFDC https://developer.nrel.gov/docs/transportation/alt-fuel-stations-v1/ ; CDC NWSS https://www.cdc.gov/nwss/ ; CAIC https://avalanche.state.co.us/
62. Economic Policy Uncertainty https://www.policyuncertainty.com/ ; GDELT https://www.gdeltproject.org/

**[7] Trade press / practitioner**
63. SGB DestiMetrics July 2026 https://sgbonline.com/destimetrics-market-briefing-july-2026/
64. SAM western destinations https://www.saminfo.com/news/sam-headline-news/western-destinations-lodging-trends-continued-in-february
65. Steamboat Pilot (Foley) https://www.steamboatpilot.com/news/bad-snow-years-make-for-bad-bookings-economic-policies-uneven-snowfall-contribute-to-lackluster-colorado-ski-season/
66. Steamboat Pilot (Ikon 2026-27) https://www.steamboatpilot.com/news/ikon-pass-2026-27-on-sale-higher-price/
67. Aspen Times (gas, Iran war) https://www.aspentimes.com/news/colorado-gas-prices-surge-mountain-towns-easter/
68. Colorado Sun (skier visits) https://coloradosun.com/2026/06/04/colorado-skier-visits-collapse-2025-26/
69. Crested Butte News https://crestedbuttenews.com/2026/04/winter-visitor-numbers-take-hit-with-weird-snow-season/
70. Denver Gazette (Mary Jane) https://www.denvergazette.com/?p=545176
71. PhocusWire (Amadeus) https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers
72. Inbound Travel (NTTO releases) https://www.inboundtravel.org/news/ntto-may-2026-international-travel-volume-tofrom-us
73. BNN Bloomberg (StatCan) https://www.bnnbloomberg.ca/business/economics/2026/05/21/canadian-travel-to-us-continues-downward-trend-new-statistics-canada-data-suggests/
74. Denver7 (strong dollar) https://www.denver7.com/news/local-news/international-skiers-and-riders-look-to-other-countries-because-of-strong-us-dollar
75. SnowBrains (international skiers) https://snowbrains.com/snow-sanctions-and-sentiment-why-some-global-travelers-are-skipping-u-s-ski-slopes/
76. Infobae / UnoTV (SEP calendar) https://www.infobae.com/mexico/2026/07/16/vacaciones-de-invierno-semana-santa-y-mas-las-fechas-del-ciclo-escolar-sep-2026-2027/ ; https://www.unotv.com/nacional/sep-publica-calendario-escolar-2026-2027-vacaciones-puentes-y-fechas-clave/
77. School-calendar aggregators (flagged unreliable) https://publicschoolscalendar.com/dallas-isd-calendar-2026-2027/ ; https://calendarstates.com/colorado/denver-public-schools/ ; https://www.educounty.net/calendars/colorado/denver-public-schools/
78. Deloitte holiday travel 2025 https://www.deloitte.com/content/dam/insights/articles/2025/us188641_cic_2025_holiday-travel-survey/pdf/DI_Holiday-travel-survey-2025.pdf
79. Future Partners https://futurepartners.com/wp-content/uploads/2026/01/SATS-LIVESTREAM-JANUARY-2026.pdf ; Longwoods https://longwoods-intl.com/american-travel-sentiment/
80. Visa wealth effect https://eu.review.visa.com/content/dam/VCOM/global/partner-with-us/documents/weighing-the-wealth-effect.pdf ; CNBC (Goldman) https://www.cnbc.com/2019/01/17/luxury-spending-could-tumble-after-stock-market-drops.html
81. hiQ v. LinkedIn: Jenner https://www.jenner.com/en/news-insights/publications/client-alert-data-scraping-in-hiq-v-linkedin-the-ninth-circuit-reaffirms-narrow-interpretation-of-cfaa ; Wikipedia https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn
82. NYC Data Science (Eisenhower hourly) https://nycdatascience.com/blog/wp-json/wp/v2/posts/96577
83. BiggerPockets (AirDNA anecdote) https://www.biggerpockets.com/posts/6534234
84. Sky-Hi News (lodging tax) https://www.skyhinews.com/news/winter-parks-lodging-tax-will-increase-to-3-in-july/
85. OnTheSnow (forecast horizon guidance) https://www.onthesnow.com/news/where-to-ski-every-month-of-the-year/
86. denverconvention.com 2027 listings https://denverconvention.com/events/details/annual-conference-2027

Count check (script): 86 numbered entries; 127 distinct URLs in this appendix; 129 distinct URLs in the document.

## Appendix C. Response to review

Review: `reviews/R5_review.md`, ACCEPT WITH FIXES (16 items). Fix pass by the author (2026-10-17,
mainly in the catalog and an errata list), consistency pass (2026-10-17, A01 and the snow
multiplier in §4), and close-out audit (2026-10-19). The audit found that most errata had reached
the catalog but not the dossier body, and applied them to the body. The catalog is the controlling
table for stream rows.

| # | Status | What changed or why not |
|---|---|---|
| 1 | applied | Catalog A01 records the HTML-shell defect. §4 no longer calls A01 "already live", and §6 has a new R0 for CARS 511 plus fail-closed handling. **Code status:** commit `d3e8b92` (2026-10-19) repointed the extractor to the CARS 511 feed and stores `QUALITY_UNAVAILABLE` on non-JSON. Live behaviour is not verified, and the new parser still matches keywords across a feature's whole property payload. There is still no forecast input for the arrival-day rule. |
| 2 | applied (body 2026-10-19) | §1 item 3 and §4 W01 state the paper's variable (daily resort depth), fixed effects (property × month), sample (2014–17, STALE) and lead buckets. The season multiplier is withdrawn, 2025-26 is cited as the counter-check, and §6 R8 maps the prior to W08. |
| 3 | applied (body 2026-10-19) | §1 item 3 cites Töglhofer et al. 2011, Shih et al. 2009 and HVS 2015, all via the review. The Malasevska weather-pricing work is cited in the catalog (W03) rather than the body. |
| 4 | applied | Catalog A02 and A03 are relabelled. §3.4 now makes Eisenhower a substitute-corridor control and A03 (US-40; R7 identified OTIS station 000223) the H4 outcome, and §6 R5 uses that. |
| 5 | applied | Catalog X04 is segment-specific; §3.4 adds the east/west-of-Empire logic and the Floyd Hill closures. |
| 6 | applied (body 2026-10-19) | §1 item 4 and §3.5 split the increment from the total share, use 4 vehicles at ~17 mpg, and add the Kansas City and Dallas rows. The H4 prior is origin-weighted. §6 R5 is updated and notes R7's later "no winter effect, bounded small" result. |
| 7 | partly | Catalog E-rows cite the October 2026 STEO context and the July/September path. §1 item 4 still leans on the April Aspen Times article for attribution; the review's point that oil is a volatile input is carried in R7 and R6, not rewritten here. |
| 8 | partly | Catalog normalized to 17 A / 38 B rows (L13 folded into L06). Adopted: W03 and W04 are one signal with the provider as an access attribute, both B; Z04 moved to A as an input to L01. Kept with stated reasons: C04 stays A (value of information on the highest-priced nights) and G08 B (unknown Mexico share); R04 and X04 stay B until their measurement limits are resolved. The §4 body still listed W03 as A and had no Z04 entry until the 2026-10-19 audit. R6 uses the catalog tiers. |
| 9 | partly | §4 now opens with a feasibility note: the short-lead and closure tests cannot pass before 2027-28 on own data, and break streams count n in seasons. Per-stream n is in R6 Part B, not repeated here. |
| 10 | applied (body 2026-10-19) | §4 L07 and §6 R1: AirDNA prices are scraped and likely fee-exclusive; compare all-in party-fit prices; check Grand County 5+ BR coverage before any coverage target. |
| 11 | applied | Catalog L11 is Lighthouse (ex-Transparent). §5's search-data verdict is now UNVERIFIED (body 2026-10-19). |
| 12 | applied | Catalog adds the FTC total-price rule and Airbnb host-only fee, SB24-033 and STR tax risk, resort capital projects, and published lift-ticket prices (R03). |
| 13 | applied (body 2026-10-19) | The DestiMetrics free report is UNVERIFIED (§6 R2). The −24% is attributed to press coverage of the 2026-06-04 CSCUSA meeting and labelled preliminary. NSAA is −14% (SAM). Catalog L08 is renamed. |
| 14 | applied | Catalog E01 maps to `src/signals/consumer.py` at shadow with no collector; `flight.py` maps to A08/A09 as fixture-only. |
| 15 | applied | Catalog W04 records the gust-unit defect. **Code status:** commit `d3e8b92` now requests `wind_speed_unit=ms`, so the ×2.237 conversion is correct. The non-commercial licence issue remains (§6 R3). |
| 16 | applied (2026-10-19) | §8 rates "Mark UNVERIFIED and STALE", "Assess transferability" and "verify access" PARTIAL. |
