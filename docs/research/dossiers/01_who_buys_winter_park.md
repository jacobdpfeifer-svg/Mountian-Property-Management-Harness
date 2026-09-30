# Dossier 1 — Who buys Winter Park?

Date: 2026-09-29
Access date for every web source below: 2026-09-29
Question: who books lodging in Winter Park / Fraser / Grand County, especially large luxury homes, and how that differs by season.

## What is proven, suggestive, and unknown

**Proven (first party, this repo).** On a copy of the operator DB, 47 confirmed non-owner stays:

| Measure | Value |
|---|---|
| Length of stay | mean 3.64 nights, median 3, 90th percentile 5 |
| Lead time | mean 40.9 days, median 15; buckets 0–7: 13, 8–21: 15, 22–60: 12, 61+: 7 |
| Party size | mean 7.09, median 6 (n=47 with a guest count) |
| Channel | Airbnb 41, website 3, manual 2, VRBO 1 |
| Home | Summit Haus 26, Overlook Ridge 14, Cloud 9 7 |
| Inquiry length | 40 inquiries, mean 7.95 nights |

Command: query `reservations` on `.testrun_runs/market_sim/phase0/eval.db` (see `phase0_BASELINE.md`). This is Mont Luxe only, mostly June–December 2026. It is not a winter-season sample. **Suggestive** for luxury-home behavior, **unknown** as a market share.

**Proven (public, county-wide, not luxury-specific).** Grand County Colorado Tourism Board 2024 annual report, Datafy in-county visitation: peak visitor-days are June–August; top origin cities Denver, Littleton, Aurora; top spending markets add Fort Collins and Englewood; in-state share rose 0.12 percentage points. VisitGrandCounty.com 2024: Denver 56,168 sessions; Chicago sessions +84.6% YoY; Kansas City +66.9% YoY. Source: https://www.visitgrandcounty.com/wp-content/uploads/2025/07/GCCTB_AnnualReport_2024.docx-FINAL-ua.pdf

**Proven (public, western mountains, not Winter Park alone).** Inntopia DestiMetrics, data through 30 June 2026, 17 western mountain destinations: May–October length of stay averaged 2.7 nights (2.75 a year earlier). Saturday arrivals averaged 2.28 nights. June bookings preferred September–November over June–August, which the authors read as price sensitivity. Luxury properties, previously the strongest tier, showed pressure. Source: https://www.snowsportsnews.com/newsrepository/2026/july/destimetrics-occupancy-at-western-mountain-destinations-is-softening-but-remains-strong-lower-price-options-gaining-traction/

**Stale, do not calibrate to it.** Key Data’s 2021 mountain-season note says end-of-season booking windows are often 60–90 days and that longer stays book earlier. Source: https://www.keydatadashboard.com/blog/2021-mountain-ski-season-trends — older than 3 years.

**UNVERIFIED.** A numeric split of Winter Park luxury (5+ bedroom) demand into families, ski clubs, international, and corporate retreats. DestiMetrics public summaries do not publish that table. AirDNA / Zartico / Placer figures were not purchased. NSAA Kottke demographic tables are paid and were not opened.

## Persona table (calibration target)

Shares are of shoppers who would consider a 5–6 bedroom home. Confidence is low wherever the cell is not Mont Luxe or a DMO fact. Low-confidence cells are swept in `SIM_PARAMETERS.md`.

| Segment | Share of luxury demand | Lead time | LOS | Party | Channel | WTP vs market median | Sensitivity |
|---|---|---|---|---|---|---|---|
| Families at holidays | Peak 0.28, Christmas week 0.40, summer 0.22, shoulder 0.12. **Assumed, swept.** Holiday compression is described by PriceLabs as a demand-factor event, not a Winter Park share. https://help.pricelabs.co/portal/en/kb/articles/understanding-min-nights | Mode 22–60 days in peak; 8–21 otherwise. First-party overall median is 15 days (proven, mixed seasons). | 4–7 peak, 3–5 otherwise. First-party median 3. DestiMetrics all-lodging summer mean 2.7, so luxury homes run longer than the market average (**suggestive**). | 8–14. Homes sleep 16. First-party median 6. | Airbnb-heavy. First-party 41/47 Airbnb (**proven** for these homes). | 1.10–1.30. **Assumed.** | Price: moderate. Snow and school calendars: high. I-70: high for Front Range. |
| Ski groups | Peak 0.22, early winter 0.18, else 0.05. **Assumed, swept.** | Weekend trips: 8–21. **Assumed.** | 2–4. | 6–12. | Airbnb / VRBO. | 0.95–1.15. | Snow and terrain: high. Price: higher than families. PriceLabs states ski-season mountain markets are less price-sensitive than summer, qualitatively. https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/ |
| Couples | Summer 0.25, shoulder 0.30, peak 0.08. **Assumed.** County visitor mix is regional and summer-peaked (DMO, proven for all visitors). | 0–21. | 2–3. | 2–4. These homes are a poor fit; many choose the outside option. | Airbnb. | 0.80–1.00. | Price: high. Snow: low in summer. |
| International | 0.04–0.08 all seasons. **Assumed, swept.** Website growth in Singapore is a traffic spike, not a booking share (DMO). Fly-in via DEN is real but unquantified for Fraser. | 61+. **Assumed.** | 5–8. | 4–8. | Direct or VRBO more than Airbnb. **Assumed.** | 1.05–1.25. | FX and DEN capacity: high. Snow: medium. |
| Multi-generational | Holidays 0.18, summer 0.15, else 0.06. **Assumed.** Matches the product (sleeps 15–16) better than county-wide averages. | 22–60 and 61+. | 5–8. Inquiry mean LOS 7.95 (**proven**) is the best local hint that long quotes are group trips. | 10–16. | Direct and Airbnb. | 1.20–1.50. | Price: lower. Calendar and access: high. |
| Corporate / retreat | Shoulder and midweek summer 0.08, peak weekends 0.02. **Assumed.** | 22–60. | 2–4 midweek. | 8–16. | Direct. | 1.10–1.40. | Macro / confidence: high. Snow: low. |

## What this changes

- Simulator segments and arrival shares: `proving_ground_exam/market/`. Measure sim-to-real on lead-time buckets, LOS, inquiry/confirmed ratio, and seasonal occupancy (`SIM_PARAMETERS.md` validation block).
- Do not put these shares into live prices. They are scenario parameters until a flag wins on the ladder.

## What to do next

1. Freeze the table in `SIM_PARAMETERS.md` with sweep ranges. Do not refit after seeing engine scores.
2. Ask the operator for any owner knowledge of holiday groups versus couples. That is the highest-value missing share.
3. Do not buy individual location data (Placer, Near).

## Open questions

- What fraction of Summit Haus / Overlook Ridge winter nights are one family versus two unrelated groups? First-party data does not say.
- Is Cloud 9’s guest mix different? n=7 confirmed stays. Unknown.
