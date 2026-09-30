# Phase 1 — Research

Date: 2026-09-29

## What was done

Executed the seven prompts in `docs/research/RESEARCH_PROMPTS.md` with web search against public DMO reports, Guesty’s Open API docs, PriceLabs’ public algorithm notes, Inntopia/DestiMetrics press, and academic citations. Wrote one dossier each and the two build documents the later phases consume.

No code, no Guesty calls, no purchased personal data.

## Files changed

- `docs/research/dossiers/01_who_buys_winter_park.md`
- `docs/research/dossiers/02_first_party_guest_data.md`
- `docs/research/dossiers/03_leading_indicators.md`
- `docs/research/dossiers/04_simulator_science.md`
- `docs/research/dossiers/05_pricing_model.md`
- `docs/research/dossiers/06_market_expansion.md`
- `docs/research/dossiers/07_guest_research_plan.md`
- `docs/research/SIM_PARAMETERS.md`
- `docs/research/MODEL_SPEC.md`
- This report.

## Tests

No behavior change, so no new test. The Phase 2 calibration loader will fail if a YAML parameter lacks a `source` string. That test does not exist yet.

## Commands

Web searches on 2026-09-29 (access date used in the dossiers) for Grand County visitation, Guesty reservation fields, PriceLabs algorithm notes, DestiMetrics length of stay, consumer confidence, and ski-town STR rules. First-party aggregates were queried on the Phase 0 DB copy (47 confirmed non-owner stays). Those commands are in dossier 1 and `phase0_BASELINE.md`.

## Results

**Proven:** Grand County’s published 2024 visitor report names Denver, Littleton, and Aurora as the top origin cities, and summer as the peak visitor-day season. DestiMetrics’ June 2026 western-mountain briefing gives a 2.7-night average stay for all lodging, not for these homes. Mont Luxe’s own 47 stays have median LOS 3, median lead 15 days, median party 6, and 41 of 47 on Airbnb. Guesty’s public API exposes hometown and adult/child counts; the pricing DB does not store them yet.

**Suggestive:** ski-season demand is less price-sensitive than summer (PriceLabs’ qualitative statement). Consumer confidence moves travel plans (Conference Board September 2026 release; older academic papers). Telluride is the best next market to test portability because the license rules are public and the physical shocks look like Winter Park’s.

**Unknown:** luxury-segment shares, a numeric Winter Park elasticity, international booking share, and inquiry conversion. Those cells are `assumed, swept` in `SIM_PARAMETERS.md`. No Winter Park-specific elasticity was invented.

## Gate

`SIM_PARAMETERS.md` and `MODEL_SPEC.md` exist. Every calibration cell in `SIM_PARAMETERS.md` has a source or the label `assumed, swept`.

## Deviations

- PODS is cited as the airline-simulator pattern. A single canonical source-code URL was not verified and is marked UNVERIFIED in dossier 4.
- NSAA Kottke, AirDNA, and Zartico were not purchased. Gaps stay unknown.
- The Poisson mean 3.2 is an assumption that Phase 2 may replace once, before any engine score, if the validation ranges miss. The slopes and shares stay frozen.

## Open questions

- Will the operator send the 10-question post-stay instrument in dossier 7?
- Is Telluride the right portability market, or should Phase 6 use Steamboat so more Colorado signals stay?
