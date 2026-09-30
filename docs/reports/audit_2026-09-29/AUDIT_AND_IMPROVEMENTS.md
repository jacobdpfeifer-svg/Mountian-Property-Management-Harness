# Repository audit, fixes, and improvement list

Date: 2026-09-29
Branch: `feature/point-in-time-replay` (uncommitted working tree on top of `f591811`)
Scope: the whole pricing path (sync → inventory → features → ceiling → bookprob →
compose → guardrails), the replay, the shadow recorder and the Proving Ground
simulator, read with the replay audit (`docs/reports/replay/audit_3/FINAL.md`) in hand.
Research follow-ups: `docs/research/RESEARCH_PROMPTS.md`.

---

## 1. Summary

**Fixed in this pass (details in §3):**

1. **Inquiries were recorded as bookings.** 130 calendar nights were "booked" only
   because a guest had *asked*. That hid available nights from pricing, fed
   inquiry quotes to the ceiling as prices paid, and made historical pacing
   snapshots wrong. The sync is fixed, and a logged, dry-run-by-default repair
   command fixes existing data.
2. **Owner stays were recorded as sales at $1,041.55/night.** They are now blocked
   nights.
3. **The engine was about 10× slower than it needed to be.** A property-day went
   from 69s to 7s, and the three test cases went from 99s to 11s. Output is
   **byte-identical** to before on all three cases.
4. **The booking-probability model ignored lead time.** It predicted ~91% for open
   near-term nights that booked ~2% of the time. It now learns P(book | still open
   at this lead time) from nights that have already checked in.
5. **The daily shadow recorder saved an arbitrary old run's price** instead of
   today's recommendation.
6. **The replay counted inquiry and owner-stay timestamps as booking events.**
7. **The simulator never applied the engine's prices.** That hid the engine's real
   behavior (see finding M1).
8. A recommendation upsert left five columns stale, and operator DB copies could be
   committed.

**The most important open finding (M1):** in peak season the engine is configured
to believe demand barely responds to price (elasticity −0.65). With that setting
the maths always says "charge the ceiling", and **nothing in the engine can learn
that this is wrong**. Being behind pace only multiplies the elasticity by 1.3, to
−0.85, which still says charge the ceiling. In the closed-loop simulator this took
a January night from $720 to $1,020 in four decisions while the simulated market's
best price was ~$505. Elasticity has to become something the engine learns from
bookings. That is the #1 model change (§4, M1).

---

## 2. What the numbers were vs now

| Measure | Before | After | Notes |
|---|---:|---:|---|
| One property × 365-night decision day | 68.7 s | 7.0 s | cProfile; YAML re-parsed 4,919×, SQI recomputed 325,000× per property-day |
| 3 identical-output check cases | 99.0 s | 10.8 s | byte-identical JSON of every `Recommendation` field |
| Proving Ground full season, weekly decisions | minutes | 6.9 s | engine + moat-off runs |
| Proving Ground full season, **daily** decisions | not practical | 70.9 s | ~0.2 s per simulated day |
| Nights falsely "booked" by inquiries | 130 | 0 after `repair-bookings --apply` | 30 more inquiry-linked nights re-pointed to the real sale covering them |
| Owner-stay nights priced as sales | 6 | 0 | now `blocked`, channel `owner` |
| Historical pacing rows wrongly "booked" | 688 | 0 after repair | logged in `data_repairs` |

Replay before/after on the repaired data is in §6.

---

## 3. Fixes made (all with tests)

### F1 — Guesty sync: only a sale books a night (S1)
`src/pms/sync.py`
- New `BOOKING_STATUSES = {confirmed, checked_in, checked_out}` and `is_market_booking()`.
- Inquiries, declines, expirations and cancellations are **stored** in `reservations`
  as demand evidence (useful for the consumer layer) but never touch
  `nightly_inventory`. Their `confirmed_at` is no longer back-filled from `createdAt`.
- Owner stays (`source=owner`) become `blocked` with no price.
- When the calendar sync sees a night that is no longer booked (e.g. after a
  cancellation), it clears the old `booked_price` / `booked_at` / `reservation_id`.
- Tests: `tests/test_guesty.py::test_inquiry_and_owner_stays_never_become_market_bookings`,
  `::test_calendar_resync_clears_a_cancelled_booking`; the cancelled-reservation test was
  updated to the new contract.

### F2 — One-time data repair (S1)
`src/inventory/repair.py`, CLI `wp-price repair-bookings [--apply]`
- Dry-run by default. Idempotent: a second run reports 0 changes. Every change is
  written to a new `data_repairs` table with before/after JSON.
- On a copy of the operator DB it reported: 130 non-sale → available, 30 re-pointed to
  the real booking, 6 owner → blocked, 688 pacing rows → available, and 42 inquiry
  `confirmed_at` stamps cleared.
- **The operator DB was not modified.** You run it:
  `PYTHONPATH=. .venv/bin/python -m src.cli.main repair-bookings`, check the dry run,
  then add `--apply`. Back up `data/wp_pricing.db` first.

### F3 — Engine performance, identical output (S1 for simulation)
`src/config.py`, new `src/runcache.py`, `src/signals/features/sqi.py`,
`src/bookprob/__init__.py`, `src/ceiling/__init__.py`, `src/compose/__init__.py`
- `load_yaml` caches the parsed file keyed on (path, mtime, size) and returns a deep copy.
- `engine_run_cache()` is a context that exists only inside one
  `generate_recommendations` call. It memoizes SQI, SQI regime, the demand index and the
  pooled inventory rows, because signals and inventory are not written while a run
  prices. Outside a run nothing is cached, so tests that mutate the DB between calls are
  unaffected.
- Proof: identical SHA-1 of the full serialized output for cloud_9@2026-09-25,
  summit_haus@2026-09-21 and overlook_ridge@2026-08-25 before and after.

### F4 — Lead-conditioned booking probability (S1 for calibration)
`src/bookprob/__init__.py::_lead_observations`, `config/policies/default.yaml`
`booking_probability.lead_conditioning`
- For each lead bucket (0–7, 8–21, 22–60, 61+ days), it counts nights that checked in
  before the decision date and were still available in a pacing snapshot at that lead
  time. A night is positive if a real sale landed after that snapshot. Uses the same
  season when there are ≥20 such nights, otherwise all seasons. The pooled rate is
  shrunk toward this with k=12.
- **Price is almost unchanged**: linear demand's argmax does not depend on `p_ref`,
  **except** where the old inflated probability hit the 0.995 cap, which flattened
  E[rev] and nudged the optimum up. In the replay, 0 of 16,084 early-window prices
  changed, and 103 of 10,094 clean-window prices fell by $5–20 (median −$10), mostly
  22–60 days out. Proving Ground revenue was identical. The main effect is on the
  probability that is shown, logged and scored.
- Test: `tests/test_bookprob_pacing.py::test_lead_conditioning_uses_resolved_open_nights`.

### F5 — Shared definition of a booking event (S2)
New `src/inventory/events.py`, used by the replay and by F4. A booking event is a
confirmed, non-owner reservation's confirmation stamp. `nightly_inventory.booked_at` is
a fallback only for legacy rows with no reservation id.
Test: `tests/test_replay.py::test_booking_events_and_repair_ignore_inquiries_and_owner_stays`.

### F6 — Shadow recorder records the right price (S1 for the daily data plan)
`src/eval/shadow.py`
- It used to join every historical run for a night, so the saved "engine price" was
  whichever run SQLite returned last.
- It now takes the latest recommendation created on or before `as_of`, stores that
  run's id and `expected_book_prob` (needed for calibration later), and computes lead
  time from `as_of` instead of a stale column.
- Test: `tests/test_shadow.py::test_shadow_record_uses_latest_run_not_an_arbitrary_one`.

### F7 — Simulator applies the engine's prices (S1 for simulation honesty)
`src/proving_ground/engine_loop.py` (`apply_to_listed=True`), `src/proving_ground/runner.py`
- Each decision's price becomes the listed price, as a push would make it. Each
  policy (engine, moat-off) now runs in its own fresh world, so one doesn't start
  from the other's prices.
- Effect: engine regret went from 30.4% to 45.0% at weekly cadence, and from 27.3% to
  35.4% daily. The old number was **flattered**: re-anchoring to a stale $720–880
  skeleton price was holding the engine back from charging the ceiling. See M1.

### F8 — Small correctness items
- `persist_recommendation` upsert now also updates `ceiling_price`,
  `listed_price_at_run`, `ceiling_confidence`, `rule_version` and `model_version`.
- `.gitignore` now excludes `docs/reports/**/*.db*`, so the three 12 MB operator DB
  copies in `docs/reports/replay/run*/` can't be committed. They hold no guest names
  or emails; `raw_json` has only status, source, timestamps and guest count.

**Test status:** 315 passed, plus 11 of 14 in `tests/test_memory.py`. The 3 memory
failures are the pre-existing ones from the uncommitted memory workstream (claims not
loading). They are unrelated to these changes.

---

## 4. Major model changes needed (ranked)

### M1 — Learn elasticity; stop hard-coding it (highest impact)
`config/policies/default.yaml booking_probability.elasticity_by_season` is the only
thing that sets how price-sensitive guests are. Because `P* = P_ref·(β−1)/(2β)`,
any |β| < 1 means "go to the ceiling". Peak is −0.65, so every peak night goes to the
ceiling unless a guardrail or deference stops it. Pacing feedback cannot cross β = −1.
**Change:** a hierarchical Bayesian elasticity (priors from policy, updated from our
own price/booking outcomes, pooled across homes and seasons), plus bounded price
exploration so it is identifiable. Until then, add a guard: when a peak night is
materially behind pace inside 21 days, β must become elastic.
**Measure:** closed-loop simulator regret across the scenario library (M6), and replay
direction metrics.

### M2 — Demand level must move price
`p_ref` (how busy a night is) cancels out of the linear-demand argmax, so the optimum
depends only on the reference price and β. Holidays and snow move price only through
the ceiling and floor bounds and the leakage rules. **Change:** let demand intensity
(pacing ratio, SQI, events, the consumer-layer indicators) shift `P_ref` or the demand
intercept, not only the probability.

### M3 — Price over the booking horizon, not one night at a time
Today each decision prices each night as if it were the last chance. **Change:**
finite-horizon dynamic pricing or bid-prices (the value of holding vs cutting as
check-in approaches), with lead-conditioned arrival rates from F4's data.

### M4 — Price stays, not nights
Luxury homes sell 3–8 night stays. Orphan gaps and minimum stay are handled by
separate rules today. **Change:** length-of-stay-aware expected revenue, where
minimum stay is a decision variable jointly optimized with price.

### M5 — Price the portfolio together
Summit Haus and Overlook Ridge are near-identical twins that compete with each
other. **Change:** joint pricing with a cannibalization term.

### M6 — Turn the Proving Ground into a market (the fast simulator)
Today the "world" is one number per night and a linear formula. **The engine never
sees a booking**, so no model inside it can learn. `W1_discrete_choice` exists but is
unused. Needed:
- A **guest-arrival process**: each simulated day, shoppers arrive by segment
  (lead time, LOS, party size, willingness to pay, channel). They compare our homes,
  competitor agents and an outside option through a logit choice. Bookings fill the
  calendar and pacing, and cancellations happen.
- **Competitor agents**: static owners, followers, a generalized-tool emulator, and an
  undercutter.
- A **scenario library** (drought, big snow, late opening, I-70 closure weekend,
  holiday shift, recession, DEN capacity cut, supply surge, price war, scraper outage,
  stale PMS).
- **Scoring on realized revenue** at booking-time prices across ≥30 seeds per
  scenario, with paired comparisons (common random numbers) and CIs.
- **Calibration** to Mont Luxe's reservation history and market data (research
  prompts 1, 2, 4), plus sim-to-real checks before any result is trusted.
- **Speed:** a daily-step season is ~71 s per policy today. Scenario × seed runs are
  independent, so run them in parallel processes; 8 cores × 71 s ≈ 8 seasons per
  71 s. Incremental repricing (only nights whose inputs changed) is the next 3–10×.

On "a minute is a day": the simulator should not be paced by wall-clock time at all.
A simulated day ends when the engine finishes deciding, which is already ~0.2–0.4 s.
The limit becomes how many worlds you want, not how long a day takes.

### M7 — Consumer layer
First-party: expand the Guesty sync (guest origin at city/state/country level, party
composition, discounts and fees, repeat guest, the inquiry funnel, cancellations,
reviews) under a written data contract with minimization (research prompt 2).
Market: segment mix and leading indicators (prompts 1 and 3) as dated signals and as
simulator segment parameters. Wire the 40 Guesty inquiries into the existing inquiry
conversion feature, which today reads only the CSV `booking_inquiries` table
(`src/elasticity/__init__.py:20`).

---

## 5. Open audit findings not fixed in this pass

| ID | Sev | Finding | Where | Suggested fix |
|---|---|---|---|---|
| A1 | S2 | `assess_data_health` uses wall-clock ages, so replay and simulator runs are never point-in-time for autonomy or display | `src/guardrails/__init__.py:66` | add `as_of` and compute ages against it |
| A2 | S2 | `seasonal_anchor` takes the 75th percentile of the property's **current** listed prices, including future nights. In replay that's lookahead; live and closed-loop, the engine anchors on its own pushed prices (ratchet risk) | `src/ceiling/__init__.py:125` | restrict to stays < decision, use as-of pacing prices, exclude engine-pushed prices |
| A3 | S2 | The pooled `p_ref` still includes future, unresolved nights as negatives (now mostly overridden by F4) | `src/bookprob/__init__.py` pooled rows | restrict to `stay_date < decision` |
| A4 | S2 | Operator memory claims are read from a store outside the DB, so replay results depend on a file not captured in the replay inputs | `src/memory/features.py` | snapshot the memory set hash into replay metadata, or allow an explicit empty root |
| A5 | S2 | UTC timestamps are truncated to dates. A booking at 7 pm Mountain time on the 1st is recorded as the 2nd | `src/utils.py:9 parse_date`, labels | convert to `America/Denver` before truncation |
| A6 | S2 | Proving Ground baselines are uninformative: `comp_median_follower` = flat (the world has no comps), `moat_off` = engine (the world has no SQI signals) | `src/proving_ground/runner.py` | M6 comp agents and signal fixtures |
| A7 | S3 | The determinism gate rebuilds the whole run twice more (3× cost) | `runner.verify_determinism` | compare against one rebuild |
| A8 | S3 | `seasonal_anchor` and `pacing_ratio` are the next hot spots (~3 s and ~1 s of the 7 s) | profile | memoize per run like F3 |
| A9 | S3 | Cancellations are now stored but not modeled; the replay label ignores cancel-after-confirm | `src/eval/replay.py` | cancellation hazard by lead time |
| A10 | S3 | Run 2's JSON and HTML were regenerated after Improvement 2 (19:49 CSV vs 20:44 HTML/JSON), and its stdout/stderr logs are empty although CHANGES.md quotes stdout | `docs/reports/replay/run2/` | note the provenance in the report, keep logs per run |

---

## 6. Replay validation on repaired data

Windows Aug 18–Sep 3 ("early") and Sep 20–29 ("clean"), censor Sep 29, three homes,
run on copies of the operator DB. Each replay took ~2 min, where the same clean
window took 22.5 min before F3.

| Run | Data | Lead cond. | Resolved rows | Distinct nights / positives | Brier (per decision) | Book rate priced above / below market |
|---|---|---|---:|---:|---:|---|
| Agent's early run (before this pass) | as-is | — | 1,105 | 78 / 22 | 0.247 | 25.3% / 33.3% |
| Early | as-is + F5 event fix | off | 1,323 | 95 / 20 | 0.207 | 12.8% / 29.6% |
| Early | as-is + F5 | on | 1,323 | 95 / 20 | 0.196 | same |
| Early | **repaired** + F5 | off | 1,339 | 96 / 20 | 0.189 | 13.5% / 28.3% |
| Early | **repaired** + F5 | on | 1,339 | 96 / 20 | **0.188** | same |
| Clean | as-is | off/on | 77 | 17 / 4 | unmeasurable | 0% / 7.1% |
| Clean | repaired | off/on | 77 | 17 / 4 | unmeasurable | 0% / 6.5% |

Reading:
- **Proven:** 2 of the agent's 22 early-window positives were inquiry timestamps, not
  sales. Removing them and restoring the inquiry-hidden available nights enlarged and
  cleaned the panel (78 → 96 nights).
- **Suggestive:** calibration improved from 0.247 to 0.188 on the early window. Most
  of that came from the data fixes. Lead conditioning adds little *there*, because that
  window starts on the first day of pacing history, so almost no checked-in nights
  existed to learn lead-time behavior from. Its effect should grow as history
  accumulates. Nights priced above market booked less often (13.5% vs 28.3%);
  that is observational and not a causal price effect.
- **Unknown:** the clean window is still too small (17 nights, 4 sales) to score. None
  of this says whether the engine beats the market.

---

## 7. Protocol for the next test run (hand this to the evaluating agent)

Run everything on **copies** of the operator DB. Never write to Guesty.

1. `cp data/wp_pricing.db <scratch>/eval.db`, then run
   `PYTHONPATH=. .venv/bin/python -m src.cli.main --db <scratch>/eval.db repair-bookings`.
   Confirm the dry run reports ~130 / 30 / 6 / 688 / 42 (or explain any difference),
   then re-run it with `--apply`.
2. Replay both windows **separately** (do not stitch across 09-04..09-19):
   `replay --from 2026-08-18 --to 2026-09-03 --censor 2026-09-29 --property summit_haus,overlook_ridge,cloud_9`
   and the same for `2026-09-20..2026-09-29`. Expect ~2–4 minutes each, down from ~22.
   Report per-decision **and** deduplicated calibration, and compare with §6.
3. Run the Proving Ground at daily cadence for several seeds:
   `proving-ground run --level 1 --seed S` with `decision_step_days=1`. Report the
   distribution of regret across seeds, not one seed.
4. Independently re-verify: a random 20-row label recomputation from raw SQL, that no
   inquiry or owner night is a positive label, and that `rate_changes` holds 0 applied
   Guesty writes before and after.
5. Classify every result as **proven / suggestive / unknown**, as in
   `docs/reports/replay/audit_3/FINAL.md`. Do not tune elasticity or policy to make a
   score pass. M1 is a model change and needs its own design review.
