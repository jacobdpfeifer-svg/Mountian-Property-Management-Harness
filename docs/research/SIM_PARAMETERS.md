# Simulator calibration

Date: 2026-09-29
Sources: dossiers 1–4. Every cell is sourced or marked `assumed, swept`.
This file is frozen before any engine score on the market simulator. Phase 2 may set the single Poisson mean so the validation ranges below are met, record that choice here, and then not touch slopes or shares.

Machine copy: `proving_ground_exam/market/calibration.yaml`. A test fails if a YAML parameter has no `source` string.

## Seasons inside a winter run (1 Nov 2026 – 29 Apr 2027, 180 days)

| Code | Dates | Notes |
|---|---|---|
| early_winter | 1 Nov – 14 Dec | Resort typical open is mid-November (`config/resort/winter_park.yaml`). |
| peak_ski | 15 Dec – 31 Mar | Policy season `peak_ski` starts 15 Dec. |
| shoulder_spring | 1 Apr – 29 Apr | Close is typically 15 Apr. The extra days are the tail of the 180-day window. |

Holiday weeks (families and multi-generational shares jump): 19 Dec 2026–3 Jan 2027, 16–19 Jan 2027 (MLK), 13–16 Feb 2027 (Presidents Day), and the local spring-break week encoded in each scenario. **Assumed dates, swept only via the `holiday_shift` scenario**, which moves them by the scenario’s offset. The dates themselves are the US federal holidays for that winter (MLK is the third Monday of January 2027 = 18 Jan; the window is the weekend around it).

## Segment parameters

Shares are of shoppers, and they sum to 1 inside each season column. Low confidence means the Phase 2 sensitivity note lists the sweep; the point value is what the simulator runs.

Price sensitivity is the mean logit coefficient on `log(nightly_price / market_median)`. More negative means more sensitive. It is **not** the engine’s linear-demand β. WTP is a lognormal multiplier on the market median nightly rate; a shopper refuses a stay whose nightly rate exceeds WTP × median (outside option wins if every quote does).

### families_at_holidays

| Cell | Peak | Early winter | Shoulder spring | Source | Confidence | Sweep |
|---|---:|---:|---:|---|---|---|
| Share | 0.28 | 0.18 | 0.12 | Dossier 1. Holiday share is assumed. County summer peak is not this segment. | low | ±0.10 |
| Lead 0–7 / 8–21 / 22–60 / 61+ | 0.10 / 0.20 / 0.45 / 0.25 | 0.20 / 0.35 / 0.30 / 0.15 | 0.25 / 0.40 / 0.25 / 0.10 | Shape follows first-party buckets (13/15/12/7 of 47) shifted later for holidays. First party: proven for mixed months. | low | Dirichlet, wide |
| LOS discrete 2/3/4/5/7 | 0.05/0.15/0.30/0.30/0.20 | 0.10/0.30/0.30/0.20/0.10 | 0.20/0.35/0.25/0.15/0.05 | First-party median 3, p90 5 (n=47). Holiday tail assumed. | low | — |
| Party size | triangular 6–16, mode 10 | same | mode 8 | Homes sleep 16. First-party median 6 across all segments. | low | — |
| Channel airbnb/vrbo/direct | 0.70/0.15/0.15 | same | same | First-party Airbnb 41/47. VRBO/direct split assumed. | med for Airbnb, low for the split | — |
| WTP median multiplier | 1.20, σ=0.15 | 1.10, σ=0.15 | 1.05, σ=0.15 | `assumed, swept` | low | median 1.05–1.35 |
| Logit price coefficient | −1.10 | −1.30 | −1.40 | `assumed, swept`. PriceLabs says ski season is less price-sensitive than summer, qualitatively, no coefficient. https://hello.pricelabs.co/blog/overview-of-pricelabs-dynamic-pricing-algorithm-part-1/ | low | −0.7 to −1.8 |
| Snow / access / macro weights | 0.35 / 0.45 / 0.20 | 0.50 / 0.40 / 0.25 | 0.15 / 0.30 / 0.30 | `assumed, swept`. Denver is the top origin (DMO 2024 report), so access weight is high. | low | each ±0.15 |

### ski_groups

Share 0.22 / 0.24 / 0.10. Lead 0.15/0.40/0.35/0.10 peak. LOS 0.25/0.35/0.25/0.10/0.05. Party mode 8, range 4–12. Channel 0.75/0.20/0.05. WTP 1.05 σ=0.12. Price coefficient −1.40 / −1.50 / −1.60. Snow/access/macro 0.70/0.35/0.15. All `assumed, swept` except the qualitative snow dependence (dossier 1). Confidence low. Sweep price coefficient −1.0 to −2.0.

### couples

Share 0.10 / 0.16 / 0.28. Lead 0.40/0.35/0.20/0.05. LOS 0.45/0.35/0.15/0.05/0.00. Party mode 2, range 2–4. Channel 0.80/0.10/0.10. WTP 0.90 σ=0.10. Price coefficient −1.80. Snow/access/macro 0.20/0.25/0.20. `assumed, swept`. These homes often lose them to the outside option via the party-fit penalty. Confidence low.

### international

Share 0.06 / 0.05 / 0.06. Lead 0.05/0.10/0.25/0.60. LOS 0.05/0.10/0.25/0.30/0.30. Party mode 6, range 2–10. Channel 0.40/0.35/0.25. WTP 1.15 σ=0.18. Price coefficient −0.90. Snow/access/macro 0.25/0.20/0.50 (macro here includes FX and DEN). `assumed, swept`. Confidence low. DMO Singapore traffic spike is not a booking share.

### multi_generational

Share 0.28 / 0.27 / 0.24. Lead 0.10/0.25/0.40/0.25. LOS 0.05/0.10/0.25/0.30/0.30. Party mode 12, range 8–16. Channel 0.55/0.20/0.25. WTP 1.30 σ=0.12. Price coefficient −0.80. Snow/access/macro 0.30/0.40/0.25. `assumed, swept`, motivated by sleeps-16 product and inquiry mean LOS 7.95 (proven, n=40), which is not the same as confirmed LOS. Confidence low.

### corporate_retreat

Share 0.06 / 0.10 / 0.20. Lead 0.10/0.25/0.45/0.20. LOS 0.20/0.40/0.25/0.10/0.05. Party mode 10, range 6–16. Channel 0.20/0.10/0.70. WTP 1.25 σ=0.10. Price coefficient −0.70. Snow/access/macro 0.10/0.20/0.60. `assumed, swept`. Confidence low.

Shares sum to 1.00 in each season (0.28+0.22+0.10+0.06+0.28+0.06 = 1; 0.18+0.24+0.16+0.05+0.27+0.10 = 1; 0.12+0.10+0.28+0.06+0.24+0.20 = 1).

## Arrival level and modulators

| Parameter | Value | Source | Confidence |
|---|---|---|---|
| Total shoppers per day, Poisson mean, before modulators | 3.2 | `assumed, swept` [2.0, 5.0]. Chosen so three homes at a 45% peak occupancy and LOS near 4 need on the order of 60 bookings in 180 days (see dossier 4). Phase 2 may replace 3.2 once, before engine scoring, if validation misses. | low |
| Holiday multiplier on family and multi-generational means | 1.8 | `assumed, swept` [1.3, 2.4] | low |
| Snow index 0–1 multiplies ski and family means by `1 + snow_weight * (snow - 0.5) * 2` | scenario | Dossier 3 | med that the sign is positive for ski |
| Access index 0–1 (1 = open) | scenario | CDOT is already a signal. Weight assumed. | med on sign |
| Macro index 0–1 (1 = strong confidence) | scenario | Dossier 3 | med on sign |
| Supply surge | +15% competitor listings (duplicate the four agents with a 0.97 price factor) | Prompt scenario. `assumed` | — |

## Choice, inquiries, cancels

| Parameter | Value | Source | Confidence |
|---|---|---|---|
| Outside-option utility | 0.0 | Normalization. `assumed` | — |
| Quality, our homes | 1.00 summit, 1.00 overlook, 0.95 cloud | Twins are the same owner and similar size (portfolio file). Cloud 9 quality haircut is `assumed`. | low |
| Quality, competitors | static 0.80, follower 0.85, tool 0.90, undercutter 0.75 | `assumed, swept` | low |
| Party-fit penalty if party < 0.35 × sleeps | −1.2 utility | `assumed`. Stops couples taking a 16-guest house too often. | low |
| Mixed-logit σ on the price coefficient | 0.25 | `assumed, swept` [0.1, 0.5] | low |
| Inquiry conversion probability | 0.55 | `assumed, swept` [0.35, 0.75]. First-party 40 inquiries and 47 confirmed stays are not a conversion rate (dossier 2). | low |
| Cancel daily hazard, lead ≥ 60 / 21–59 / 8–20 / 0–7 | 0.004 / 0.002 / 0.001 / 0.0004 | `assumed, swept`. Too few observed cancels to fit. | low |
| Market median nightly rate (WTP anchor) | 700 | Between the sample flat price 720 and the homes’ floors. `assumed`. Not an AirDNA extract. | low |

## Competitor rules (generalized-tool emulator)

From dossier 4, PriceLabs public docs, implemented as:

- Base 700.
- Peak × 1.15, early winter × 1.00, shoulder × 0.90. Weekend (Fri–Sat) × 1.08.
- Holiday × 1.20.
- Lead ≤ 14 and still open: × 0.92 (last-minute discount). https://help.pricelabs.co/portal/en/kb/articles/pricing-calendar
- If the agent’s own occupancy over the next 30 nights is under 40%: × 0.90.
- Min stay 3 in peak beyond 14 days, else 2. Drop one night if behind. This is a simplification of the published 10–20% rule, labeled as such.

Undercutter: 0.92 × the min of the other three agents’ nightly prices. Follower: yesterday’s median. Static: 680 peak, 620 otherwise.

## Scrape

| Parameter | Value | Source |
|---|---|---|
| Multiplicative noise, log σ | 0.04 | `assumed` |
| Probability a listing is missing on an ok day | 0.08 | `assumed` |
| Outage | scenario sets all rows `failed` | Audit concern: a missing row must not look like a full market |

## Validation ranges (sim-to-real on `normal`)

A `normal` winter run must land inside these, or the miss is written down and accepted as a limit. Ranges are wide because Mont Luxe’s 47 stays are not a winter census.

| Check | Range | Source |
|---|---|---|
| Share of confirmed stays with lead ≤ 21 days | 0.40 – 0.75 | First party 28/47 = 0.60. Wilson-style widening, not a formal interval. |
| Mean LOS of confirmed stays | 2.5 – 6.5 nights | First party mean 3.64. Upper bound allows a more winter-like mix than the June–December sample. DestiMetrics all-lodging summer mean 2.7 is a floor reference, not the target. |
| Inquiry rows / confirmed rows | 0.40 – 1.60 | First party 40/47 = 0.85. |
| Occupancy, peak_ski nights, three homes | 0.25 – 0.75 | First-party December 2026 occupancy was 0.30 and November 0.07, on a partial book. Summer months were 0.22–0.36. The winter band is wider on purpose. **Suggestive.** |
| Occupancy, early_winter | 0.10 – 0.55 | Same. |

If the first-party winter sample is too thin to fail a model, say so in the Phase 2 report. Do not tighten these ranges after seeing engine revenue.

## Sensitivity (low-confidence cells)

Phase 2 records one sweep, not a search: Poisson mean in {2.0, 3.2, 5.0} and family price coefficient in {−0.7, −1.1, −1.8}, on `normal`, 10 seeds, world revenue only (no engine). The point values above stay the official scenario. The sweep is a robustness note.
