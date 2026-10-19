# Deep research pack — 2026-10

Index of the research program set up in `docs/prompts/DEEP_RESEARCH_2026-10-16/`. Current state is
recorded in [AUDIT_2026-10-19.md](AUDIT_2026-10-19.md), which supersedes
[AUDIT_2026-10-17.md](AUDIT_2026-10-17.md). Every dossier has an adversarial review in `reviews/` and
a "Response to review" appendix with one row per numbered fix. Research only: the engine-code fixes
this pack recommended were made separately in commits `d3e8b92` and `bcef02b` (2026-10-19). Nothing in
this folder is committed.

| ID | File | Review verdict and fix status | Words | Sources |
|---|---|---|---:|---|
| R1 | [Airline RM](R1_airline_rm.md) | ACCEPT WITH FIXES; 23 fixes, 3 partly | 22,132 | 96 bibliography entries |
| R2 | [Hotel RM](R2_hotel_rm.md) | ACCEPT WITH FIXES; 15 fixes, 1 partly | 17,310 | 90 distinct sources |
| R3 | [Cross-industry RM](R3_cross_industry_rm.md) | ACCEPT WITH FIXES; 18 fixes, 1 not done (coverage gaps) | 19,448 | 87 sources |
| R4 | [STR pricer teardown](R4_str_pricer_teardown.md) | ACCEPT WITH FIXES; 20 fixes | 20,008 | 91 numbered source records |
| R5 | [Data-stream universe](R5_data_stream_universe.md) + [catalog](R5_catalog.csv) | ACCEPT WITH FIXES; 16 fixes, 3 partly | 10,921 | 86 entries; catalog 121 rows (17 A, 38 B, 20 columns) |
| R6 | [Data-value ranking](R6_data_value_ranking.md) | ACCEPT WITH FIXES; 11 fixes, 2 partly | 8,687 | Method sources in Part A; upstream bibliographies |
| R7 | [Winter Park demand drivers](R7_winter_park_demand_drivers.md) | ACCEPT WITH FIXES; 17 fixes, 2 partly; all headline numbers reproduce | 10,094 | 60+ URLs plus original data analysis |
| S1 | [Synthesis and roadmap](S1_synthesis.md) | ACCEPT WITH FIXES (V_REVIEW 2026-10-19: 18 citations, 11 searches); 16 fixes | 10,609 | 30+ named plus upstream |

## Three-line abstracts

- **R1:** Airline RM's transferable core is a capacity-1 bid price, unconstraining and owner-net units.
  Peak-at-ceiling needs a separate demand-model fix (R1a). The field cannot see effects under about
  33%, so a 4% gain needs about 4,000 weeks per arm; simulation on a misspecified world is the gate.
- **R2:** Hotel practice supports pooled additive pickup, length-of-stay control and owner-net
  measurement. A 20–40-comp market pace series is about 3× more precise than own pace (1.8× at
  today's scrape quality). Most recommendation logging already exists; fill it.
- **R3:** Other industries support band control, pooling, reference-price framing and crossover
  experiments. Comp-fill learning is blocked by price endogeneity until an identification strategy
  exists. Pass prices move domestic overnight stays (+31% Swiss DiD), not foreign ones.
- **R4:** Generic pricers are sophisticated and broad. PriceLabs already prices neighbouring-night
  opportunity cost in minimum-stay rules. The specialist edge is capacity-matched comps, mountain state
  and owner-net economics for 14-to-18-guest stays.
- **R5:** 121 streams, 17 A-tier. Comp repair, own pace, market pace, snow and resort state,
  calendars and access rank ahead of gas, macro, geopolitics and search.
- **R6:** Value-of-information caps any single stream near 3–5% of revenue. Comp repair ranks #1.
  Lagged weekly snow makes traffic forecasts worse; snow is a seasonal state. Every top design fails
  safe on stale data.
- **R7:** Winter Park town-remitted lodging is 71.7% Nov–Apr. Gas has no detectable winter effect,
  bounded at about 4% of access traffic for a 30% rise. A post-drought "snow hangover" delays
  bookings rather than lowering the season.
- **S1:** Build the comp data spine first, then close the signal-health residuals, pooled additive
  pickup, mountain state bands and owner-net stay controls. Four self-contained build prompts are in
  §7. Airline-scale machinery, overbooking and RL will not pay at three homes.

## Leak scan (2026-10-19)

No 24-character hex ids, booked-price figures or guest names in this folder or the prompt folder. The
cold-call company and person are unnamed. The shared-context December peak clause is a listed range
from the public calendar (read 2026-10-19), not a booked rate.
