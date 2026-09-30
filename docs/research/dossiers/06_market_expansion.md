# Dossier 6 — Where a mountain-built pricer could go next

Date: 2026-09-29
Access date for web sources: 2026-09-29

## Traits that punish a generic nightly tool

Thin comps, a few large homes rather than a hotel, weather and road shocks, holiday weeks that are not ordinary weekends, and a drive-versus-fly mix. PriceLabs’ own ski-regulation note says nightly caps push managers to yield, not occupancy, and that supply cuts of 27–38% of available nights showed up in some regulated markets while December–February ADR rose 11–17%. https://hello.pricelabs.co/blog/str-regulations-in-usa-ski-market/ Those percentages are PriceLabs’ summary of markets they watch, not an independent audit. Treat them as **suggestive**.

## Ranked shortlist

| Rank | Market | Why it matches | Regulation (public) | Rebuild versus reuse |
|---|---|---|---|---|
| 1 | Telluride, CO | Small luxury inventory, hard holiday peaks, airport (TEX) plus a long drive, heavy snow swings | Town does not cap the count of licenses, but one person or business cannot hold a financial interest in more than two. Classic licenses pay a per-bedroom regulatory fee. https://www.telluride-co.gov/FAQ.aspx?QID=275 and https://telluride.municipal.codes/TMC/6-1-25 | New `config/resort/telluride.yaml` (areas, season, airport). Signals: a SNOTEL near Telluride instead of Berthoud, CDOT passes (Lizard Head / Dallas Divide) instead of I-70’s main ski corridor, TEX seats instead of DEN. Scrape bbox changes. Portfolio and choice code stay. |
| 2 | Big Sky, MT | Large-home luxury, weather, limited beds, no city STR cap | Unincorporated. State public-accommodation license, not a town cap. A brokerage note cites AirDNA ADR about $995 and 54% occupancy as of June 2026. https://so-red.com/blog/the-big-sky-short-term-rental-license-that-doesnt-survive-closing — AirDNA figure via a secondary blog, **suggestive**, not a primary extract. | Resort YAML, SNOTEL, Bozeman airport, scrape region. No Ikon-blackout clone unless the operator confirms the pass product. |
| 3 | Steamboat Springs, CO | Same I-70 / snow / DestiMetrics world as Winter Park, so the simulator transfers, but the mountain and pass (Yampa) differ | County and city STR rules exist; this pass did not cite a single ordinance section. **UNVERIFIED** numeric cap. | Smaller diff than Telluride: Colorado signals mostly reuse, resort feed id and bbox change. |
| 4 | Mount Bachelor / Bend, OR | Weather-driven, drive and fly (RDM), less “Ikon Front Range” structure | **UNVERIFIED** in this pass. | New state signals. Choice model and guardrails reuse. |
| 5 | 30A / South Walton, FL (non-ski control) | Holiday compression and large homes without snow. Tests whether the method is “event compression” or only “ski.” | **UNVERIFIED** cap details here. | Drop SNOTEL. Add a hurricane/beach-closure signal. If this market is second, the portability spec must say the snow block is optional. |

Not chosen first: Whistler, the Alps, Niseko. Currency, language, and platform mix are a larger rebuild. Park City and Breckenridge are closer but more competed and better served by generic tools, so a win is harder to see.

## What must be rebuilt versus reused

| Piece | Reuse | Rebuild per market |
|---|---|---|
| `src/compose`, guardrails, bookprob flags | Yes | Priors in policy, not code |
| `config/resort/*.yaml` | Pattern | One file: areas, season dates, feed id |
| SNOTEL / road / airport collectors | Interfaces | Station ids, road ids, airport code |
| Scrape bbox and comp set | Code | Region coordinates |
| `proving_ground_exam/market/calibration.yaml` | Schema | Segment shares and validation ranges |
| Portfolio twins | Code | Only if that market has a twin pair |

Phase 6 builds rank 1 (Telluride) as a config and a scenario file, runs the simulator, and writes the diff list. It does not scrape Telluride listings and does not claim a live win.

## Open questions

- Does the operator want the second market to stay in Colorado (Telluride or Steamboat) for signal reuse? This dossier picks Telluride.
- Any plan to operate there, or is the file only a portability test? Phase 6 treats it as a test.
