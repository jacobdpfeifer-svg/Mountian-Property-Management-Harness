# Point-in-time replay — 2026-09-29

**Headline:** ran with no lookahead (Guesty writes=0). Combined calibration is *technically* measurable on **52** resolved night-decisions, but **0 of 52** had booked by the censor, and **9,592 of 9,644** night-decisions are still unresolved future stays. This is not a two-winter revenue proof and **does not show the engine beat the market**.

**DB:** `data/wp_pricing.db` → `/Users/jacobpfeifer/Library/Application Support/wp-price/data/wp_pricing.db`  
**Command:**

```bash
.venv/bin/python -m src.cli.main --db "data/wp_pricing.db" replay \
  --from 2026-09-20 --to 2026-09-29 \
  --property summit_haus,overlook_ridge,cloud_9 \
  --horizon 365 --out docs/reports/replay
```

CLI: `Replayed 10 decision day(s) over 9644 night-decisions; censor 2026-09-29; Guesty writes=0`  
Artifacts: `docs/reports/replay/replay_2026-09-29.{html,json,csv}` (HTML is the slide screenshot).

---

## 1. Data ceiling

| Fact | N / range |
| --- | --- |
| Pacing `as_of` in the operator DB (all history) | 2026-08-18 → 2026-09-29 (**26** distinct days) |
| Earlier block **excluded** from the headline window | 2026-08-18 → 2026-09-03 (**16** distinct days; gap 2026-09-02 and then a jump) |
| Clean consecutive daily `as_of` used as decision days | 2026-09-20 → 2026-09-29 (**10** days) |
| Reservations in the DB | **88** (`confirmed_at` min 2026-05-12T01:50:31.518Z, max 2026-09-25T17:06:07.420Z) |
| `nightly_inventory` rows with non-null `booked_at` | **304** |
| Pacing rows with non-null `listed_price` (whole DB) | **31,806** |
| Pacing rows with non-null `listed_price` in the clean window (all properties) | **14,608** |
| Target properties with pacing rows | `summit_haus` **9,506**; `overlook_ridge` **9,506**; `cloud_9` **9,506** |
| Night-decisions logged this run | **9,644** |
| Night-decisions with as-of listed price (`listed_source=pacing`) | **9,623** |
| Night-decisions with no as-of listed (`listed_source=none`) | **21** |

A two-winter revenue proof is not claimed. Ten September decision days cannot stand in for a ski season.

---

## 2. No peeking

- Guesty write count: **0**. `rate_changes` has **0** rows; applied-Guesty count (`result='applied'` and actor matching `%guesty%`) is **0**. Replay did not call `set_rate` / `push` / `handle`.
- Decision days match the clean window: `2026-09-20` … `2026-09-29` (**10**).
- Public snow/ENSO vintages are gated by `published_at ≤ D`. Every signal on every decision day passed `assert_no_lookahead` (the replay aborts if that assert fails).
- Listed-price provenance: **9,623 / 9,644** used the listed price recorded on that pacing day; **21 / 9,644** had no as-of listed price (`listed_source=none`) and were **not** silently repaired. Engine note: *“Reference prices for older pool nights use today's listed price where no as-of pacing snapshot exists; those nights are not silently repaired.”*

---

## 3. Measured (resolved nights only)

Resolved = `stay_date ≤ censor 2026-09-29`. Predicted probability is **terminal** (books by check-in). Unresolved future nights are excluded.

### Combined (N night-decisions = 9,644)

- **Calibration: measurable** on **52** resolved nights with `expected_book_prob` (threshold is 20). Brier **0.575** (lower is better).
  - Predicted 0–20%: **18** nights; mean predicted 9.7%; actually booked by censor **0%**
  - Predicted 60–80%: **2** nights; mean predicted 72.7%; actually booked by censor **0%**
  - Predicted 80–100%: **32** nights; mean predicted 94.5%; actually booked by censor **0%**
  - **0 / 52** resolved priced nights have `booked_by_censor=true`. `booked_by_censor` is false on **all 9,644** logged rows.
- **Direction: measurable.** Priced above listed: **18** nights, booked **0%**; priced below: **34** nights, booked **0%**. (Equal groups of 0% booking cannot show a direction effect.)

Why the booked rate is zero on the priced sample: the engine only emitted recommendations for nights it still priced. Inventory for 2026-09-21…2026-09-29 on the three properties includes **14** `status=booked` nights, but those booked stays are not in the 52-row resolved replay panel (`booked_at` empty on all 52). Calibration here is terminal probability vs “still available as of the rec,” not vs the nights that actually checked in.

### Per property (same CSV, sliced)

| Property | Night-decisions | Resolved with p | Calibration | Direction |
| --- | ---: | ---: | --- | --- |
| summit_haus | 3,121 | 17 | **Unmeasurable** (17 < 20) | Measurable: above **6** booked 0%; below **11** booked 0% |
| overlook_ridge | 3,291 | 17 | **Unmeasurable** (17 < 20) | Measurable: above **12** booked 0%; below **5** booked 0% |
| cloud_9 | 3,232 | 18 | **Unmeasurable** (18 < 20) | **Unmeasurable** (above=0, below=18) |

Per-property calibration is unmeasurable because each house is under the 20-night floor. Combined only crosses the floor by pooling the three houses.

**Unresolved:** **9,592 / 9,644** night-decisions have `stay_date` after the censor (mostly 365-day-ahead ski inventory). Those are not scored.

---

## 4. Estimated revenue (assumption in the title)

Assumption printed by the engine: *bookings do not respond to price (price-swap only) — not a causal result.*

Combined, over **9,623** comparable nights (**0** booked by the censor among those priced rows):

| Basis | Engine RevPAN | Listed RevPAN | Difference |
| --- | ---: | ---: | ---: |
| Bookings held fixed (real outcomes) | $0 | $0 | $0 |
| Engine's own demand model | $17.85 | $18.49 | −$0.63 |

Per property, `booked_by_censor` is also **0** on comparable nights (summit_haus 3,114; overlook_ridge 3,284; cloud_9 3,225), so the bookings-held-fixed RevPAN is $0 everywhere.

**This run does not show the engine beat the market.** Both rows swap the price while holding bookings fixed, which cannot prove causation.

---

## 5. How to grow this

Run `wp-price shadow-record` daily on the operator DB (no Guesty writes) so future months accumulate nights that have actually checked in.

Tests: `.venv/bin/python -m pytest tests/test_replay.py -q` → **8 passed** (this branch has 8 tests, not 12). HEAD `f591811`.
