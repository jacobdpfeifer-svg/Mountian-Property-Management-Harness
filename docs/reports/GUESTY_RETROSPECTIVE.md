# Guesty vs this engine — honest historical comparison

**Stay window:** 2026-04-29 → 2026-09-19  · **Decision lead time:** 30 days before each night  · **Nights scored:** 275

**What Guesty's API actually returned:** calendar nights 2024-09-20 → 2027-10-23; reservation check-ins 2026-05-20 → 2027-10-21.

**Confidence:** Thin sample — intervals intentionally wide. One drought season is n=1, not a relationship.

## What this comparison can and cannot support

### Backed by real historical data

- Finished reservations: stay dates, booking confirmation time (when Guesty sent `confirmedAt`), guest count, and what was actually paid (`fareAccommodation` / nights).
- Today's Guesty calendar for those dates (listed price + current status). Treat listed price on past nights as Guesty's *current memory* of the rate, not a recovered 90/60/30-day snapshot.
- This engine's **ceiling**, **leakage scan** (peak underprice / shoulder over-discount / orphan gap), and **own-history** on nights whose booking was already confirmed by the decision date.
- Comp evidence **only** when a snapshot existed on or before the decision date (0 night(s) in this run).

### Not validated — do not quote as proof

- **Booking-probability and pacing.** Guesty cannot return what the calendar looked like at 90/60/30/14/7 days out. The daily snapshotter (`src/pacing`) was not running then. `backfill_from_inventory` reconstructs prior days from *current* state and labels that output as biased — a night booked yesterday looks like it was booked weeks ago. This report does **not** call that function and does **not** claim the P(book|P) model is calibrated.
- **Expected RevPAN** on each night is the composer output. It is shown so you can see what the engine *would print today looking backward*. It is not a measured revenue lift.
- **Naive counterfactual RevPAN** (engine price if the night booked, else $0) is the same estimator already in `src/eval/backtest.py`. It assumes every guest who paid Guesty's price would also have paid the engine's price. If the engine is higher, that overstates revenue. If it is lower, it understates the rate they actually achieved. It is a bound, not a win.

## Portfolio

| Metric | Value |
|---|---|
| Nights compared | 275 |
| Booked / still-open (historical leftover) | 178 / 97 |
| Realised RevPAN (Guesty money / scored nights) | $487 |
| Naive counterfactual RevPAN (unproven) | $425 |
| Naive delta (engine − Guesty, unproven) | $-62 |
| Mean ceiling − booked price (headroom if conversion held) | $221 |
| Peak-underprice flags | 11 |
| Shoulder-over-discount flags | 2 |
| Nights with contemporaneous comps | 0 |
| Booked nights with a confirmation timestamp | 99% |

**Verdict:** the naive bound is $-62 / night against this engine. Guesty's realised rates were higher than what this engine would have recommended on booked nights, or the engine would have cut nights that still sold. Do not claim a win.

## By property

| Property | Owner | Nights | Booked | Realised RevPAN | Naive CF RevPAN | Naive Δ | Ceiling − booked | Peak flags |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| cloud_9 | cloud9 | 17 | 4 | $87 | $123 | $36 | $338 | 0 |
| overlook_ridge | northwoods | 131 | 104 | $705 | $611 | $-93 | $146 | 5 |
| summit_haus | northwoods | 127 | 70 | $315 | $273 | $-42 | $327 | 6 |

## By owner

Owner ids come from `config/portfolio/mont_luxe.yaml` (`northwoods` = Summit Haus + Overlook Ridge; `cloud9` = Cloud 9).

| Owner | Properties in this run | Nights | Realised RevPAN | Naive CF RevPAN | Naive Δ |
|---|---|---:|---:|---:|---:|
| cloud9 | cloud_9 | 17 | $87 | $123 | $36 |
| northwoods | overlook_ridge, summit_haus | 258 | $513 | $445 | $-68 |

## Example nights (clearest gaps, both directions)

These are the nights where the engine price and Guesty's realised/listed price differ most. The list is mixed on purpose: a report that only showed favorable nights would not survive an operator who still has the Guesty folio in front of them.

- **2026-06-20 · overlook_ridge** (summer, no named event). Guesty charged/listed $228; this engine at 30 days out would have recommended $1,060 (higher than Guesty). Ceiling $994 via `seasonal_anchor` (confidence 45%). Leakage: none. No contemporaneous comps (no fresh comp snapshots for this night). No usable comps even as approximation. Outcome: the night booked at Guesty's price. Charging the engine's higher rate is unproven — we do not know if that guest would still have converted.
- **2026-08-21 · summit_haus** (summer, no named event). Guesty charged/listed $1,986; this engine at 30 days out would have recommended $645 (lower than Guesty). Ceiling $969 via `p90_season` (confidence 80%). Leakage: none. No contemporaneous comps (no fresh comp snapshots for this night). No usable comps even as approximation. Outcome: the night booked at Guesty's price. The engine's lower rate would have left money on a stay that already sold.
- **2026-06-19 · overlook_ridge** (summer, no named event). Guesty charged/listed $228; this engine at 30 days out would have recommended $995 (higher than Guesty). Ceiling $994 via `seasonal_anchor` (confidence 45%). Leakage: none. No contemporaneous comps (no fresh comp snapshots for this night). No usable comps even as approximation. Outcome: the night booked at Guesty's price. Charging the engine's higher rate is unproven — we do not know if that guest would still have converted.
- **2026-08-22 · summit_haus** (summer, no named event). Guesty charged/listed $1,986; this engine at 30 days out would have recommended $655 (lower than Guesty). Ceiling $872 via `p90_season_dow` (confidence 100%). Leakage: none. No contemporaneous comps (no fresh comp snapshots for this night). No usable comps even as approximation. Outcome: the night booked at Guesty's price. The engine's lower rate would have left money on a stay that already sold.
- **2026-08-15 · overlook_ridge** (summer, Summer festival / trail season). Guesty charged/listed $437; this engine at 30 days out would have recommended $1,165 (higher than Guesty). Ceiling $1,083 via `p90_season_dow` (confidence 100%). Leakage: none. No contemporaneous comps (no fresh comp snapshots for this night). No usable comps even as approximation. Outcome: the night booked at Guesty's price. Charging the engine's higher rate is unproven — we do not know if that guest would still have converted.

## Warnings

- Booking-probability / pacing is NOT validated here. Guesty cannot return the historical booking calendar, and pacing.backfill_from_inventory is a biased reconstruction — not evidence.
- Guesty calendar listed_price on past nights is the price Guesty shows now, not a snapshot of the listing at booking time. Realised booked_price (fareAccommodation / nights) is the conversion evidence.
- Comp snapshots dated after the decision date are excluded from the primary ceiling. Any 'today's comps' figure is labelled approximation.
- summit_haus appeared in Guesty around 2026-05-01 (decoded from the listing id). Calendar days before that are padding from the API range request, not nights this engine could have priced.
- overlook_ridge appeared in Guesty around 2026-04-29 (decoded from the listing id). Calendar days before that are padding from the API range request, not nights this engine could have priced.
- cloud_9 appeared in Guesty around 2026-08-26 (decoded from the listing id). Calendar days before that are padding from the API range request, not nights this engine could have priced.
- cloud_9_chalet appeared in Guesty around 2026-08-26 (decoded from the listing id). Calendar days before that are padding from the API range request, not nights this engine could have priced.
- creekside_haven appeared in Guesty around 2026-09-03 (decoded from the listing id). Calendar days before that are padding from the API range request, not nights this engine could have priced.

Pacing model validated retrospectively: **no**.
