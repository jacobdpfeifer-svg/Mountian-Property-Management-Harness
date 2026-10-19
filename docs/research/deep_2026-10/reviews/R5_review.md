# R5 review: data-stream universe (`docs/research/deep_2026-10/R5_data_stream_universe.md`, `R5_catalog.csv`)

Reviewer: adversarial review (V_REVIEW.md). Date: 2026-10-16. Status: COMPLETE.

## 0. Structural checks (done)

- Catalog: 116 rows, 20 columns, no ragged rows (parsed with `csv.DictReader`). Tier mix A 18 / B 37 / C 61. All 13 categories present (L 14, A 13, W 12, M 12, C 10, S 8, G 8, R 8, Z 8, E 7, P 7, X 5, Q 4).
- Search log: 73 lines tagged `S` (2 extended), 30 tagged `F`, 9 tagged `C` (several C lines bundle many checks). The "73 WebSearch / ~30 WebFetch" totals match the log. The log numbers 1–112, so "73" is not the last index; that is fine.

## 1. Repo claims (verified by reading code; one live call)

| Dossier claim | Verdict | Evidence |
|---|---|---|
| `weather.py` uses Open-Meteo | **Correct** | `FORECAST_URL = api.open-meteo.com/v1/forecast`, `ARCHIVE_URL = archive-api.open-meteo.com/v1/archive` (`src/signals/collectors/weather.py:22-23`). |
| `flight.py` fixture-only / `unavailable` | **Correct** | No fixture → `QUALITY_UNAVAILABLE`, reason `bts_fixture_required_brief_only_mode`. Note it is a **BTS T-100 DEN capacity YoY** proxy, not flight *search*; the dossier maps it nowhere in the catalog (S04 says `no`). |
| `intent.py` fixture-only | **Correct** | No fixture → `use_fixture_or_enable_trends_fetch`. |
| `regulatory.py` fixture-only | **Correct** | No fixture → `no_machine_readable_source`. |
| `cdot.py` covers US-40 only | **Correct but materially incomplete** | See finding R-1 below. |
| A01 "already live" (catalog tier reason, §4.9) | **Wrong in effect** | See R-1. |
| E01 gasoline "not in repo (proposed in dossier 03)" | **Partly wrong** | `macro.eia_gasoline` is already registered at shadow in `src/signals/consumer.py:17` (no collector). Catalog `already_in_repo` should say so. |
| SNOTEL station 335:CO:SNTL | Correct | `config/policies/markets.yaml:14`. |
| Intrawest lift feed | Correct | `src/signals/extractors/intrawest.py:15` (`snowreporting.herokuapp.com/feed`). |

**R-1 (load-bearing, missed by the author): the "live" US-40 collector cannot ever report a closure.** `src/signals/extractors/cotrip.py` calls `https://www.cotrip.org/api/alerts?routeName=US%2040&direction=Both`. On 2026-10-16 that URL returns HTTP 200 **`text/html`** (an ~12 kB single-page-app shell that fetches `511.cotrip.org/configs/main.json`), not JSON. `parse_cotrip_payload` then falls back to the raw HTML string, finds none of "berthoud", "us 40", "closure" or "chain law" in it (reviewer grep: zero hits), and returns `{'berthoud_closed': 0.0, 'chain_law': 0.0, 'access_risk': 0.0}` — which `cdot.py` stores as **`QUALITY_OK`**. Reviewer ran `fetch_cotrip_access()` once and got exactly that. So A01, the stream the dossier calls "already live" and the clearest "no generic pricer sees it" edge, is a silent false negative that will pass the `cdot_max_age_hours: 6` freshness check. The dossier verified the separate CARS host (`api-511x-co.carsprogram.org`, also 200 for the reviewer) but never checked what the repo actually calls. Secondary issues in the same parser: any alert text containing "closure" anywhere plus "us 40" anywhere sets `berthoud_closed = 1` (no segment/milepost match), and "traction law" is counted as chain law. The collector also only records the status at `as_of`; there is no forecast or history, so §4.9's "on a high access-risk *forecast* for arrival day" rule has no input yet.

**R-2 (side finding for the W03/W04 rows).** `weather.py` multiplies Open-Meteo `wind_gusts_10m_max` by 2.237 (m/s → mph), but Open-Meteo's default `wind_speed_unit` is **km/h** and the request does not set it. Gusts would be overstated by about 3.6× (2.237 vs 0.621). The dossier proposes `windGust` for lift-hold prediction (W03) without noticing the existing field is mis-scaled. (Reviewer reading of the code plus Open-Meteo docs default; not run live.)

## 2. Citation spot-check (WebFetch / direct request, accessed 2026-10-16)

| # | Claim in dossier | Source opened | Result |
|---|---|---|---|
| 1 | Parthum & Christensen 2022, *JEEM* 113; CO 0.135, national 0.223; short-window 0.124–0.152; AirDNA; 236 resorts | PMC10936566 (full text) | **Supports the numbers, but the dossier misapplies them** — see §3 F-1. Snow variable is **resort-reported daily snow depth (OnTheSnow)**, not SWE; data are **Aug 2014–May 2017** (STALE, not flagged); the short-window figures are for reservations made "less than" 2/5/7/10 days ahead, not "2–10 days ahead"; CO 0.135 is a text-only state slope from Eq. 2 (Fig. 2), not a tabled estimate with SE; the 236 resorts are with properties within 10 km. |
| 2 | Brent $126.55 on 2026-10-14 | FRED `DCOILBRENTEU` CSV | **Supports** (126.55 on 2026-10-14). Reviewer-computed monthly means: Mar 103.1, Apr 106.6, May 96.9, Jun 85.4, Jul 83.8, Aug 86.7, **Sep 114.2**, Oct-to-date 127.0 — consistent with the dossier's STEO "$114 September" line. |
| 3 | Colorado regular $4.175 (2026-10-12), $4.020 (2026-10-05) | EIA leaf `EMM_EPMR_PTE_SCO_DPG` | **Supports.** |
| 4 | "Aspen Times ties both [Brent $126.55, CO $4.175] to the US–Iran war and Hormuz" | Aspen Times 2026-04-04 | **Partly.** The article (prices as of 2026-04-03, Grand County $4.113, Foley "nothing really dramatic") does attribute *April* prices to "the ongoing U.S. war with Iran" and a near-total Hormuz blockade. It cannot attribute *October* prices. Trade press shows the path was not continuous: the July 2026 STEO cut Brent 14% after a "U.S.-Iran deal reopens Strait of Hormuz" ([MarketScale, 2026-07-17](https://www.marketscale.com/industries/energy/eia-slashes-oil-price-forecast-14-after-us-iran-deal-reopens-strait-of-hormuz.md)); August STEO raised it again on renewed transit constraints ([S&P Global 2026-08-11](https://www.spglobal.com/energy/en/news-research/latest-news/crude-oil/081126-us-eia-raises-brent-outlook-to-87b-on-hormuz-shipping-constraints)). The October attribution needs a current source (the Oct STEO, which the author cites but which the reviewer could not parse — PDF tools unavailable). |
| 5 | Vail 2026/27 pass units −12%, days −10%, dollars −6% through 2026-09-18; weakness in Destination frequency products; CO/UT locals "modest improvement" | SEC 8-K | **Supports** verbatim ("especially lower frequency passes"). |
| 6 | Colorado skier visits −24% to ~10.5M, lowest since 1991-92 | CSCUSA release; Colorado Sun (429) | **Partly / supports via secondary.** The CSCUSA page says "projected preliminary" 10.5M and ">20% below five- and ten-year averages"; it does **not** state −24% or 1991-92. Those figures are in press coverage of the 2026-06-04 CSCUSA meeting ([Post Independent](https://www.postindependent.com/news/colorado-skier-visitation-lowest-35-years/); [SAM](https://www.saminfo.com/news/sam-headline-news/colorado-resorts-endured-historic-visit-decline-in-2025-26)). Colorado Sun returned HTTP 429. Dossier should say "preliminary". |
| 7 | Open-Meteo free API non-commercial only | open-meteo.com/en/pricing | **Supports** ("The free API is for non-commercial use, rate-limited to 10,000 calls/day"). Paid tiers (Standard 1M / Professional 5M / Enterprise) exist; prices not shown. |
| 8 | AirDNA API: Market Data incl. future daily pricing; 12–60 months; listing future pricing; bearer token via sales | airdna.redoc.ly | **Supports.** Also has *submarket* future daily pricing and a "Smart Rates" package (not mentioned). |
| 9 | Conference Board Sept 2026 81.9 (from 88.6); 42.6% vacation intentions, domestic only; non-commercial terms | conference-board.org | **Supports.** |
| 10 | Ikon Base: Winter Park unlimited; blackouts Dec 26–30 2026, Jan 16–17, Feb 13–14 2027 | ikonpass.com | **Supports.** |
| 11 | Eisenhower–Johnson Tunnel counts 2000–Aug 2026; Jan 2026 1,029,653; Jul 2026 1,194,859; Jul 2025 1,242,866 | codot.gov table | **Supports the numbers; the use is wrong** — see §3 F-3. |
| 12 | PriceLabs: ~350 comps within ≤15 km; block removal; no weather/snow/flights/search/macro | PriceLabs algorithm part 1 | **Supports.** Detail: market data are scraped from Airbnb, Vrbo **and Booking.com**; "booking.com hotel-like properties" in §3.1 is a paraphrase. |
| 13 | DestiMetrics: twice-monthly submission, up to 6 months forward, subscriber-only (funding DMOs + data-submitting partners) | Inntopia help page | **Supports.** But Recommendation R2's "**free** property-vs-destination report" for data-submitting partners is **not on this page** (it lists submitters as subscribers and points to Sales). Mark UNVERIFIED or cite. |
| 14 | PriceLabs Market Dashboard $9.99/dashboard/month after one free; booked nights by LOS × booking window | PriceLabs help | **Partly.** Price and LOS × window confirmed; the page does not confirm *forward* occupancy/pacing, which catalog L08's name asserts. |
| 15 | Amadeus Self-Service shut down 2026-07-17 | PhocusWire (403) + search | **Supports via corroboration** (shutdown on 2026-07-17; GitHub org archived that day). |
| 16 | SEP 2026-27: winter break Dec 21 – ~Jan 6; Semana Santa Mar 22 – Apr 2, 2027; DOF 2026-07-15 | Infobae | **Supports** (break ends Tue Jan 5; classes resume Jan 7). |
| 17 | Inside Airbnb 50% review rate × average stay | insideairbnb.com/data-assumptions | **Supports.** Default ALOS is 3 nights (or minimum nights if higher); our homes' ~8-night requests (dossier 02) mean the default would badly mis-state comp occupancy — say so in Q01. |
| 18 | NWS `gridpoints/BOU/37,70` has `snowfallAmount`, `windGust`, `snowLevel`, `hazards` | api.weather.gov (direct) | **Supports**; `points/39.89,-105.76` resolves to BOU 37,70 "Winter Park". |
| 19 | Passover 2027 begins at sundown Apr 21 | Hebcal API (direct) | **Supports** (Erev Pesach 2027-04-21). |
| 20 | 30-park, 30-year panel; visitation "modestly responsive" to fuel prices | JPRA (Steiner, Stinespring & Dieringer 2026) | **Supports** (abstract; no coefficients public). Authors/year should be named in Appendix B entry 10. |
| 21 | GCCTB 2024: Chicago sessions +84.6%, Kansas City +66.9% | GCCTB PDF | **Could not verify** (PDF is AES-encrypted; text unreadable to reviewer). Not evidence of fabrication. |
| 22 | Vail Dec 2025: units −2%, dollars +3%; declines in CO/UT/Tahoe local drive-to markets | SEC 8-K | **Supports** verbatim. |
| 23 | NSAA 2025-26 ≈ 52.6M, −15% | search (SAM) | **Partly** — 52.6M confirmed; SAM headline says **−14%**; −15% appears only in a forum recomputation. |

**Tally (23 checked): supports 16; partly 6; does not 0 (one sub-claim, the "free" DestiMetrics report, unsupported); could not verify 1; dead or fabricated 0.** No fabricated citation found.

## 3. Reasoning findings

**F-1. The snow prior is applied to the wrong variable and the wrong timescale.** Parthum & Christensen's Eq. 1 is `ihs(revenue)_it = β·log(snowpack)_rt + controls + ψ_im`, with **property × month fixed effects**, where snowpack is **daily resort-reported snow depth (OnTheSnow)**. β = 0.135 for Colorado is a *within-property-month, day-to-day* elasticity to resort depth. The dossier turns it into a **season-level SWE multiplier**, "(SWE/normal)^0.135 … 0.93 at 60% of normal" (§1.3, §4.6, R8), and proposes calibrating SQI's SNOTEL weight with it. Three problems: (a) SNOTEL SWE at Berthoud Summit is not resort snow depth. The repo's own note says SNOTEL and gridded estimates disagreed sharply in 2025-26 (`weather.py` docstring: 91% vs 60%), so the mapping is not one-to-one. (b) Month fixed effects absorb most season-level variation, so β does not identify a "bad season" effect. (c) The data are **Aug 2014–May 2017, three seasons**, so the figure is **STALE** under the depth standard and was not flagged. Its revenue is also AirDNA *asking price when booked*. The closest stream to the paper's variable is **W08** (resort-reported depth), not W01. The 2025-26 season (Colorado visits −24%, per CSCUSA coverage) is a ready counter-check: a 0.93 multiplier at 60% SWE looks far too small for that season. Either the season-level effect is much larger than β, or other drivers dominated. The dossier should say this, not present 0.93 as the expected size.

**F-2. The "no study" claims are overstated.** §3.3 says Parthum & Christensen is "the only lodging-revenue elasticity to snowpack" and that no study shows powder pulling bookings forward. The reviewer found, in a few searches:
- Töglhofer, Eigner & Prettenthaler (2011), *Climate Research* 46:1–14 ([abstract](https://int-res.com/abstracts/cr/v46/n1/p1-14)): **overnight stays** (lodging demand) in 185 Austrian ski areas, 1972/73–2006/07. A one-SD change in snow conditions moved stays by 0.6–1.9%, and the effect shrinks with snowmaking and is absent at high elevation. This is directly relevant to Winter Park's snowmaking and elevation.
- Shih, Nicholls & Holecek (2009), *JTR* 47(3):359–372 ([record](https://vtechworks.lib.vt.edu/handle/10919/81425)): daily lift-ticket sales respond to temperature, snow depth and wind chill.
- Malasevska and co-authors (Inland Norway Univ.) ([summary](https://www.scientia.global/wp-content/uploads/Iveta_Malasevska/Dr-Iveta-Malasevska.pdf)): when midweek weather beats the weekend forecast, skiers shift to midweek despite a higher price. That is forecast-driven intertemporal substitution, the mechanism behind W03.
- HVS (Russell 2015, [Hotel-Online](https://www.hotel-online.com/news/snowfallss-impact-on-ski-market-hotels); STALE, practitioner): snowfall and occupancy co-move *within* a season, which implies short booking windows. The effect is stronger at drive-to resorts (Breckenridge, Vail, Keystone) than at destination resorts. Winter Park is a drive-to resort, so this matters.

None of these is STR-specific, but the dossier's "gap" framing and its W03 "UNVERIFIED pull-forward" should cite them.

**F-3. The H4 test in R5 uses the wrong road.** Winter Park traffic leaves I-70 at Empire (exit 232) for US-40 over Berthoud. The Eisenhower–Johnson Tunnel is **west** of that exit. Its counts (A02, the "best free outcome series for testing H4") therefore measure **Summit County / Vail** drive demand, which is our substitute's corridor, not ours. The right outcome series is a CDOT/OTIS count station on US-40 between Empire and Winter Park. A03's mechanism mentions one, but the reviewer could not find a published AADT in one search (UNVERIFIED). Relatedly, **X04's substitution logic has to be segment-specific.** I-70 *between Denver and Empire* (for example the Floyd Hill project, exits 244–247, with overnight full closures in October 2026 and more planned mid-November to mid-December, per [CDOT 2026-10](https://www.codot.gov/news/2026/october-2026-news/i70-floydhill-overnight-i70-closures)) is **shared** by Winter Park traffic and hurts us too. Only closures west of Empire (Georgetown, the tunnel, Vail Pass) favour Winter Park. As written, the X04 flag would fire the wrong way on Floyd Hill and Idaho Springs events.

**F-4. The fuel-share arithmetic covers only the most favourable case, and conflates two quantities.** The §3.5 numbers check out for a Denver party in 3 cars at 20 mpg on a 130-mile round trip: about 20 gal, so +$1/gal ≈ $20, which is 0.17–0.26% of a $7.9k–11.9k stay including the $1,880 fees for 16 guests (reviewer recomputation). But:
- (a) **"Fuel is well under 1% of trip cost" (§1.4) and "fuel is about 0.2–0.3% of stay cost" (R5 row) mix up the *increment* with the *share*.** Total fuel at $4.175 is 0.7–1.7% of the stay for a Denver party.
- (b) 16 guests plus ski gear is more realistically 4 vehicles at about 17 mpg. That gives 0.27–0.40% per $1/gal.
- (c) The dossier itself says Texas, Kansas and Oklahoma drive-in weeks "decide March pricing" (C02). The reviewer's rough distances are Dallas ≈ 1,700 mi and Kansas City ≈ 1,320 mi round trip (UNVERIFIED estimates). On those, +$1/gal is **2–5%** of the stay and total fuel is **7–21%**.

So H4 cannot be dismissed for our segment from Front Range arithmetic. The prior should be split by origin. That is an argument for the shadow test, not against it.

**F-5. The geopolitical attribution is time-shifted.** §1.4 pins October values (Brent $126.55, CO $4.175) on an **April** article. The oil path was not one continuous shock. Brent averaged about $84–87 in June–August (FRED), and the July STEO followed a reported US–Iran deal that reopened Hormuz. It then spiked to $114 in September and about $127 in October. The October driver needs a current citation. The "regime" logic in R7 should also treat oil as a **volatile, mean-reverting** input whose STEO forecasts were revised ±15% month to month, not as a stable season state.

**F-6. Tier assignments are internally inconsistent.** The tiering rule (§2) puts "an outcome series the engine cannot be evaluated without" in A. The catalog applies that rule unevenly:
- **P04** (lodging tax, backtest-only) is **A**, but **A02/A03** (traffic counts, "best free backtest outcome for H4") are **B**. Pick one rule.
- **C04** (federal holidays) is **A** while its own reason says "every pricer has some version". **G08** (SEP calendar, "a demand window generic pricers don't model") is **B**. By the edge criterion, these are inverted.
- **W03** (NWS) is **A** with the reason "licence-clean replacement for Open-Meteo". That is a compliance reason, not value-of-information. Its demand effect is marked UNVERIFIED in §4.7. The same data via Open-Meteo (W04) is **B**. Tier the *signal* once and treat the provider as an access attribute.
- **W01** is **A** "proven elasticity, already live", yet §4.6 says it must not be used as a separate signal, and F-1 shows the elasticity is for W08's variable.
- **Z04** (own cancellation hazard) is **B**, but §3.13 calls it "most valuable" and "needed for correct pace", which is an input to A-tier L01.
- **R04** (pass sales) is **B**, but §3.9 calls it "the strongest season-ahead read this year".
- **A01** is **A** on "already live". R-1 shows it is not.
- **X04** is **B** although §1 lists it in the specialist edge alongside A-tier streams.
- **L13** is a separate A row "folded into L06", so the count of 18 distinct A streams is really 17.

**F-7. Recommendations rely on measurement that cannot reach significance for most streams.** The IC ≥ 0.05 / n ≥ 40 gate is applied to pickup residuals. With about 100 reservations, the short-lead (≤7-day) subset for W03 and A01 will contain few bookings per season. The dossier should estimate n per test (bookings in window × seasons) and say which tests are infeasible this winter. A01 closure-week tests in particular need multiple seasons. Without that, "measurement plan" is nominal for W03, A01, X04 and C05.

**F-8. Licensed-feed reasoning omits that AirDNA is also scraped.** AirDNA's listing "future pricing" comes from the same platform calendars (and typically excludes cleaning and per-guest fees). It moves the ToS exposure to the vendor and fixes reliability, but it does not give fee-inclusive party-fit prices. The trial in R1 should compare **all-in** prices and check 5+ BR coverage in Grand County before claiming "3% → ≥50%". Also note **Transparent is now Lighthouse** ([ShortTermRentalz](https://shorttermrentalz.com/news/lighthouse-rebrand-ota-insight/)). Lighthouse markets a *Market Insight* product with forward-looking demand and **search-volume** data ([API listing](https://providers.apievangelist.com/providers/lighthouse-travel/); vendor, UNVERIFIED). That weakens §5's "platforms have better search data than we can buy" and L11's "C: duplicates L07/L08".

## 4. Coverage gaps (vs. the prompt's minimum list, plus reviewer searches)

Prompt items are mostly present (all 13 categories; rental cars A11, shuttles A12, labour, HOA, insurance, listing rank, tariffs, shutdowns, advisories, university breaks, smoke, wastewater all have rows). Thin or missing:

1. **Platform fee and display rules (missing category item).** The FTC Rule on Unfair or Deceptive Fees (short-term lodging, total-price display, effective 2025-05-12; [FTC FAQ](https://www.ftc.gov/business-guidance/resources/rule-unfair-or-deceptive-fees-frequently-asked-questions)). Airbnb's move to a 15.5% host-only fee for PMS-connected hosts (from about 2025-10-27; dates vary by source; [Hostfully](https://www.hostfully.com/blog/airbnb-host-fees/), vendor). Both change what guests compare and what owner-net is per displayed dollar. They belong in category 10 and in the all-in comp comparison.
2. **I-70 Floyd Hill construction (missing).** Planned full closures on the shared Denver–Empire segment through at least mid-December 2026 (CDOT, above). It is a dated, free, negative access stream distinct from A13.
3. **State STR tax and reclassification risk (missing).** SB24-033 (lodging property-tax reclassification for STRs over 90 nights) was gutted to a study in 2024 ([Vail Daily](https://vaildaily.com/news/bill-hiking-taxes-for-short-term-rentals-to-be-gutted-after-resistance-from-airbnb-vrbo)), and Vail voters narrowly rejected an STR lodging-tax increase in November 2025 (search snippet, UNVERIFIED). These are owner-cost and supply streams. P01–P07 cover only local licences and rates.
4. **Lift-ticket price (R03) is marked UNVERIFIED but is observable.** OnTheSnow lists Winter Park 2025-26 adult $272 weekday / $282 weekend with limited-quantity advance discounts ([OnTheSnow](https://www.onthesnow.com/colorado/winter-park-resort/lift-tickets)). A date-varying resort price is a free read of the resort's own demand forecast and deserves a real access check.
5. **Snow-demand literature (F-2).** Töglhofer 2011, Shih 2009, the Malasevska weather-pricing work and HVS 2015 are missing.
6. **Lighthouse (ex-Transparent) Market Insight** search and demand data are missing (F-8).
7. **Prompt's "Turo/rental car" and "World Cup / events".** Present but thin. One events row; no check of whether Winter Park hosts FIS or other events in 2026-27 (the log says "not confirmed").
8. **Resort capital projects** (new lifts or terrain, such as the Forest Service–approved Discovery/Gemini gondola project, [USFS 66200](https://www.fs.usda.gov/r02/arp/projects/66200)). These are season-level quality shifters and are not catalogued.

Reviewer searches run (16): STEO Oct 2026 Brent/Hormuz; Colorado skier visits −24%; US-40 Berthoud AADT; Amadeus shutdown; NSAA 2025-26; Floyd Hill closures; FTC junk-fee rule; Denver snow vs ski bookings; Töglhofer 2011; Shih 2009; Malasevska weather pricing; Airbnb host-only fee; Winter Park capital projects; Colorado STR tax 2026; Winter Park lift-ticket pricing; Lighthouse STR API.

## 5. Depth audit (reviewer's own check of every MUST)

| MUST | Reviewer verdict | Note |
|---|---|---|
| Inline URL + access date | PASS (weak) | One global access date in the header. Acceptable, but rows with different dates (e.g. CDOT tunnel "through Aug 2026") should carry their own as-of. |
| ≥ 40 distinct sources | PASS | 86 entries / 127 URLs. Several class-3 entries are just API landing pages (Reddit, GA4, NREL), but well above 40 even excluding them. |
| ≥ 4 classes | PASS | All 7 present. Class 2 is one textbook chapter, cited and not used. Class 5 is two filings. |
| Primary sources read | PARTIAL | Ye et al. read via a blog summary (the standard says a blog summary does not replace the paper). Weatherford & Kimes cited by PDF URL but read via "search summary". Both are acknowledged. |
| UNVERIFIED / STALE marking | **FAIL (fixable)** | Parthum & Christensen data (2014–17) not flagged STALE although it is the load-bearing prior. HVS-type evidence absent. The "free" DestiMetrics report and the CSCUSA "−24% / 1991-92" (not on the cited CSCUSA page) are stated as fact. |
| No invented stats/citations | PASS | Nothing fabricated in 23 checks. |
| Search passes (broad/specific/adversarial) | PASS | 73 searches, adversarial set present. The adversarial pass missed the contradicting snow literature (F-2). |
| Mechanisms implementable | PASS | §4 first versions are concrete. |
| Quantified evidence with conflicts | PASS | Vendor claims labelled. |
| Map to module + owner-net measurement | PARTIAL | Modules mapped. Measurement feasibility (n per test) is not estimated (F-7). |
| Transferability | PARTIAL | Thin-data caveats present. The fuel arithmetic is one-segment (F-4), and the snow prior is transferred across variable and timescale (F-1). |
| Generic-pricer note | PASS | §5. Absence-in-docs caveat stated. |
| Ranked recs / open questions / self-audit | PASS | Present. The self-audit overstates "access verified for all A and B" (A01 as the repo calls it was not verified; R-1). |
| R5: ≥ 80 streams; A-tier paragraphs; generic vs none per category | PASS | 116 rows; 18 A paragraphs (17 distinct). |
| R5: verify access for A and B | PARTIAL | See R-1 (the A01 endpoint the repo uses returns HTML). |

## 6. Verdict: **ACCEPT WITH FIXES**

The catalog is broad (116 rows, all 13 categories, clean 20-column CSV). Citations hold up: 16 of 23 support the claim, 6 partly support it, none are fabricated. The headline conclusion stands: comp anchoring is the binding constraint, and the edge is physical-world streams. But four load-bearing items are wrong or misapplied:
- the "already live" US-40 collector, which silently reports zeros;
- the snow prior, which is transferred to the wrong variable and timescale;
- the H4 outcome series, which counts the wrong road;
- the fuel-share dismissal, which holds for one origin segment only.

None of these requires new research breadth. All are fixable in the dossier.

## 7. Fix list (numbered, actionable)

1. **A01 / R-1.** State that `src/signals/extractors/cotrip.py` calls `cotrip.org/api/alerts`, which returns an HTML app shell, so `cdot.py` stores `berthoud_closed = chain_law = access_risk = 0` at `QUALITY_OK` on every live run. Remove "already live" from A01's tier reason, §4.9 and §5. Make "repoint to the CARS 511 API and fail closed (`QUALITY_UNAVAILABLE`) on a non-JSON response" a top-3 recommendation. Note the parser's whole-payload keyword match (false positives) and that there is no forecast input for the §4.9 arrival-day rule.
2. **Snow prior (F-1).** Restate Parthum & Christensen precisely: daily **resort-reported snow depth** (OnTheSnow), property × month fixed effects, AirDNA **2014–2017** (mark **STALE**), and short-window figures for bookings made "<2 / <5 / <7 / <10 days" ahead. Withdraw the "(SWE/normal)^0.135 = 0.93" season multiplier, or label it an extrapolation and test it against 2025-26, when Colorado visits fell about 24%. Map the prior to W08, not W01, in §4.6 and R8.
3. **Snow literature (F-2).** Replace the "only study" and "no study" claims. Cite Töglhofer et al. 2011 (*Climate Research* 46), Shih et al. 2009 (*JTR* 47(3)), the Malasevska weather-pricing work and HVS 2015 (STALE). Use the HVS drive-to vs destination finding in W03 and X01.
4. **H4 outcome series (F-3).** Replace Eisenhower Tunnel counts (A02) as the H4 outcome with a US-40 count station between Empire and Winter Park (find the OTIS station id or mark it UNVERIFIED). Keep A02 only as a *substitute-corridor* control. Update R5 accordingly.
5. **X04 segment logic (F-3).** Specify that I-70 events east of Empire (Floyd Hill, Idaho Springs) are *shared* negatives and that only events west of Empire favour Winter Park. Add a Floyd Hill planned-closure stream (CDOT notices).
6. **Fuel arithmetic (F-4).** Separate the *increment per $1/gal* from the *total fuel share*. Use a realistic 16-guest vehicle count. Add a row per origin: Denver about 0.2–0.4% per $1; Texas, Kansas and Oklahoma drive-in about 2–5% per $1, with total fuel 7–21% (reviewer estimates, recompute). Fix §1.4 ("well under 1%") and the R5 row ("0.2–0.3% of stay cost"). Make H4's prior origin-weighted, tied to C02.
7. **Geopolitical timing (F-5).** Cite a current source (the October 2026 STEO text, quoted) for the October oil driver. Mention the July deal and reopening and the September re-spike. Describe oil as a volatile input in R7, not a season state.
8. **Tier consistency (F-6).** Apply one rule for outcome series (P04 vs A02/A03). Re-tier C04 vs G08 by the stated criteria. Tier W03 and W04 as one signal, with the provider as an access field. Reconcile W01 ("A" but not a signal), Z04 ("most valuable" but B), R04 ("strongest read" but B) and X04 (headline edge but B). Report 17 distinct A streams, or drop the L13 row.
9. **Measurement feasibility (F-7).** For each A-tier stream, estimate the n available for the IC ≥ 0.05 / n ≥ 40 gate per season (bookings within the lead window, closure weeks, break weeks). Flag which tests cannot run before 2027-28, and what pooling (market data such as L09 or simulator) substitutes.
10. **AirDNA trial (F-8).** Add that AirDNA listing prices are scraped and likely exclude cleaning and per-guest fees. Compare all-in party-fit prices. Check Grand County 5+ BR coverage before promising "≥50% anchor coverage".
11. **Lighthouse (F-8).** Update L11 to Lighthouse (ex-Transparent), add its Market Insight search and demand data as a licensable intent stream, and soften §5's "platforms see search data we cannot buy" to "UNVERIFIED".
12. **Missing streams (§4).** Add rows for: the FTC junk-fee rule and Airbnb host-only fee timeline (category 10 / all-in comparison); state STR tax and reclassification risk (SB24-033 history; local ballot measures); resort capital projects (USFS Discovery/Gemini approval). Upgrade R03 from UNVERIFIED using the published OnTheSnow date-varying prices.
13. **Unsupported sub-claims.** Mark the DestiMetrics "free property-vs-destination report" (R2) UNVERIFIED. Attribute "−24%, lowest since 1991-92" to press coverage of the 2026-06-04 CSCUSA meeting and label it *preliminary*. Change NSAA to −14% (SAM). Change L08's name from "future occupancy, pacing" unless the help page confirms forward data.
14. **Catalog repo column.** Set E01 `already_in_repo` to `src/signals/consumer.py (macro.eia_gasoline registered at shadow; no collector)`. Map `flight.py` (BTS T-100 DEN capacity YoY, fixture-only) to A08/A09, not "no".
15. **Side bug for W03/W04 (R-2).** Note that `weather.py` converts Open-Meteo gusts with ×2.237 (m/s→mph), but the API default is km/h. Gusts are overstated about 3.6×. This matters before any wind-hold signal uses them.
16. **Self-audit.** Change "Mark UNVERIFIED and STALE" to PARTIAL (items 2 and 13). Change "verify access for A/B" to PARTIAL (item 1). Change "transferability" to PARTIAL (items 2 and 6).

## Addendum: scoped re-review, 2026-10-19

Most fixes had reached `R5_catalog.csv` but not the dossier body. The close-out audit applied them to
the body and checked them against the catalog. Consistency check by the same audit, not an
independent review.

- §4 now matches the catalog tiers: W03 is B (one signal with W04) and Z04 is A with its own entry.
- The snow prior, fuel arithmetic (origin table), H4 outcome series, AirDNA trial and CSCUSA/NSAA
  figures in the body now match the errata.
- A03's station id is no longer UNVERIFIED: R7 used OTIS continuous station 000223 (MP 248.7–254.3).
- Code status: commit `d3e8b92` fixed A01's endpoint and fail-closed handling and the W04 gust unit;
  the catalog rows record both. Residual parser risks are listed in S1 §2.2.
- Item 7 (geopolitical timing) and item 9 (per-stream n) are partly done; R6 Part B carries the n.

Verdict unchanged: ACCEPT WITH FIXES (ledger in R5 Appendix C).
