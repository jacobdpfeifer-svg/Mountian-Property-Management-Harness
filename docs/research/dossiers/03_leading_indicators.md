# Dossier 3 — Will consumers buy this year?

Date: 2026-09-29
Access date for web sources: 2026-09-29

Leading indicators for luxury mountain lodging. Each one enters as a **shadow** signal (point-in-time `observed_at`) or as a simulator scenario knob. None starts `active`.

## Ranked shortlist

| Rank | Indicator | Cadence | Lead | Sign for Winter Park demand | Evidence | Licence / vintage |
|---|---|---|---|---|---|---|
| 1 | Snow / SWE and season open (already in `src/signals`) | Daily | 0–60 days | Higher SWE and an on-time open raise near-term ski demand | Inntopia’s Tom Foley, spring 2025: weak snow plus lower confidence kept skiers home. https://www.steamboatpilot.com/news/bad-snow-years-make-for-bad-bookings-economic-policies-uneven-snowfall-contribute-to-lackluster-colorado-ski-season/ | Public feeds already collected. Vintages exist. |
| 2 | Conference Board Consumer Confidence | Monthly, preliminary then final | 1–6 months | Lower confidence, fewer hotel and airfare plans. September 2026 index 81.9, down 6.7 from August; vacation plans still 42.6% but foreign plans dipped. https://www.prnewswire.com/news-releases/us-consumer-confidence-fell-in-september-302892867.html | Crotts, Thunberg, Shifflet (1993) found a published confidence measure often predicted the direction of US travel volume. https://exa.ai/library/publication/c6c1vhsyd9k — the paper is old; the mechanism is the reason to keep the series, not a Winter Park elasticity. Dragouni et al. review confidence and outbound tourism. https://eprints.bournemouth.ac.uk/24319/1/Post-script_ATR_2016.pdf | Conference Board series is published; redistribution of the microdata is not free. Store the index value and release date only. `observed_at` = release date, never the reference month’s last day. |
| 3 | I-70 / Berthoud access | Daily | 0–3 days | Closures cut Front Range weekend demand | Already a collector (`src/signals/collectors/cdot.py`). Dossier 1: Denver is the top origin. | Public. |
| 4 | NOAA CPC ENSO outlook | Monthly | 1–6 months for snow regime | El Niño / La Niña shifts the odds of a deep or dry winter. The sign for a single season is probabilistic, not a point elasticity. | Already partly in `src/signals/collectors/enso.py`. **UNVERIFIED:** a published regression of Grand County lodging on ONI. | Public CPC outlooks. Use the issue date as `observed_at`. |
| 5 | DEN passenger and scheduled seats | Monthly passengers; schedules weeks ahead | 1–3 months | Less lift into DEN reduces fly-in segments | Visit Denver: 37.1 million visitors in 2024, and DEN is the gateway. https://milehighcre.com/denver-tourism-matches-record-breaking-year-in-2024/ The article does not give a DEN seat-capacity series. FAA/BTS T-100 is the public source. **UNVERIFIED** here: the latest T-100 extract was not downloaded in this pass. | Public BTS. Store monthly totals. |
| 6 | School-holiday calendar (Front Range, Texas, Midwest) | Annual, known ahead | The holiday itself | Shifts arrival dates. Foley (same Steamboat article) attributed a soft March to Easter falling after resorts closed. | Public district calendars. | Enter as scenario `holiday_shift`, and as a dated event list. |
| 7 | Gasoline (drive markets) | Weekly EIA | 2–8 weeks | Higher gas prices tax the Denver and Texas drive trip | **UNVERIFIED** as a Winter Park elasticity. EIA weekly retail gasoline is public. https://www.eia.gov/petroleum/gasdiesel/ (access 2026-09-29; series exists, a local effect size was not estimated). | Public. |
| 8 | Listing supply in Grand County | Monthly if a market snapshot is scraped | 1–3 months | More listings lower occupancy and price | The engine already stores `market_snapshots`. A +15% supply scenario is a simulator stress, not a live coefficient. | Own scrapes. No personal data. |

Dropped from the top 8 as primary inputs: S&P 500 (wealth effect is real in the tourism literature but collinear with confidence; keep as a note, not a second signal), jet fuel (operates through airfare; no local effect size found), Ikon pass unit sales (Alterra statements are sparse; **UNVERIFIED** numeric pass sales for the current year), Google Trends (noisy, easy to overfit).

## Proposed `signal_definitions` (status starts at `shadow`)

| signal_key | cadence | lead window | expected sign on demand |
|---|---|---|---|
| `macro.consumer_confidence` | monthly | 30–180 days | positive |
| `macro.den_passengers` | monthly | 30–90 days | positive |
| `macro.eia_gasoline` | weekly | 14–60 days | negative |
| `macro.enso_oni` | monthly | 30–180 days | regime, not a signed price |
| `demand.listing_supply_index` | monthly | 0–90 days | negative |

Snow, access, and resort ops stay on their existing keys.

## How they enter

- Live engine: shadow only. `assert_no_lookahead` on `observed_at`.
- M2, flag off by default: a bounded shift of the reference price, not of elasticity, until an evaluation says otherwise. Snow already moves bounds through SQI; do not double-count.
- Simulator: scenario multipliers on segment arrival rates.

## Backtest design

Use at least five public winters (for example 2018–19 through 2023–24, excluding the 2020–21 pandemic winter as a separate regime). Outcome: Grand County lodging-tax receipts, rate-adjusted, from Town of Winter Park monthly reports such as https://wpgov.com/wp-content/uploads/2025/03/2024-12-Sales-Tax-Report-Dec-2024-collected-Jan-25.pdf (December 2024 lodging sales were up on the tax-rate change; the report says that excluding the rate change, lodging was about −7% for the month). That series is revenue, not occupancy. A regression that ignores the July 2024 rate change (1% to 3%, https://www.skyhinews.com/news/winter-parks-lodging-tax-will-increase-to-3-in-july/) will be wrong. This backtest is **not run** in this phase. It is the design.

## What to do next

1. Insert the five definitions at `shadow` with no collector auto-promotion to `active`.
2. Do not fit coefficients on one winter of Mont Luxe data.

## Open questions

- Who will paste or fetch the Conference Board release so `observed_at` is the real release timestamp?
- Is DEN capacity worth a collector before the first season of shadow scores?
