# R7: Winter Park demand drivers, testing the practitioner hypotheses with real data

Output: `docs/research/deep_2026-10/R7_winter_park_demand_drivers.md`

## Question

Are the practitioner's claims (H1, H4, H5 and H7 in `00_FIELD_NOTES.md`) true, and how big are the
effects? What is Winter Park's real demand structure, by segment and season?

## Cover at minimum

1. **H5 seasonality (about 70% of revenue in winter).** Find Grand County, Town of Winter Park and
   Town of Fraser **monthly lodging-tax / sales-tax collections** (Colorado Department of Revenue
   publishes county and town sales-tax data; the towns publish budgets and tax reports). Get as
   many years as exist. Compute the winter share (define winter as Dec–Mar and also as Nov–Apr).
   Compare with our homes' per-home monthly aggregates if available in repo docs. Never write
   booked revenue into the dossier; give percentages only.
2. **H4 gas prices.** Assemble the public series: EIA weekly Colorado or Rocky Mountain (PADD 4)
   retail gasoline; CDOT traffic counts on US-40 at Berthoud Pass and on I-70 at the Eisenhower
   Tunnel (find the station IDs and the data portal); Winter Park lodging-tax months. Search for
   **published elasticities of leisure drive travel to gas prices** (FHWA, academic,
   ski-specific). If the data is downloadable in small CSVs, run a simple analysis with Python in
   the scratch area: traffic or tax vs gas price, controlling for snow (SNOTEL) and holidays.
   Report the coefficient, CI and caveats. If data is not obtainable, design the exact test and
   list the data pulls.
3. **H1 middle-class market.** Compare ADR and price distributions for Winter Park vs Breckenridge,
   Vail, Steamboat, Keystone and Aspen (AirDNA public pages, Inntopia public summaries, comp data
   in our repo). Guest origin and income data where published (Colorado Tourism Office/Longwoods
   reports, Winter Park & Fraser Chamber, Alterra). Ikon-pass skier demographics. **What does a
   middle-class core market imply for our luxury 5+ bedroom homes?** Their buyers may be large
   multi-family groups splitting cost, not the wealthy. Price per guest per night may be the
   right lens.
4. **Segments.** Front Range day and drive, Front Range overnight, drive-in from TX/KS/OK/NE,
   fly-in via DEN, international, groups (families, ski clubs, corporate, weddings). Give their
   relative size, lead time and price sensitivity. Cite DestiMetrics/Inntopia summaries, Colorado
   Tourism Office data and the existing dossier 01.
5. **Access shocks.** Berthoud Pass closures, I-70 closures and chain laws, Winter Park Express
   rail. Quantify the effect on occupancy if any evidence exists.
6. **Summer and shoulder.** Summer demand drivers: mountain biking (Trestle), events, Fraser
   River, weddings. Their growth trend. How to raise the non-winter 30%.
7. **H7.** Given all of the above, list the **Winter Park–specific factors** a generic pricer would
   miss, ranked by estimated revenue impact.

## Required

- Put any analysis scripts and downloaded small CSVs in a scratch directory **outside the repo**
  (`/private/tmp/wp_research/`). Put only results, with source URLs, in the dossier.
- For each hypothesis give a verdict: SUPPORTED / PARTLY / NOT SUPPORTED / UNTESTABLE-NOW, with
  the evidence and the data needed to settle it.
