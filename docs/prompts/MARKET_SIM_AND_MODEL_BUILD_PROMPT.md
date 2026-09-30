# Agent prompt — research, build the market simulator, and upgrade the pricing model

Copy everything below the line into a fresh agent session started in the repo root
(`Harness for my wonderful Mother/`).

---

## Your mission

You are taking this pricing engine from "a rules engine with fixed assumptions,
tested against a toy simulator" to "an engine that learns from bookings, tested
against a realistic, fast market simulator full of synthetic shoppers." The long-term goal is a pricing
method built for mountain and ski-resort towns that beats generalized tools
(PriceLabs, Beyond, Wheelhouse, AirDNA Smart Rates). It must be testable in hard
scenarios in minutes and later portable to other markets.

The work runs in **seven phases**. Do them in order. At the end of every phase, write
the phase report described below, then continue. **Stop and report instead of
continuing** if a phase gate fails, a safety rule would be broken, or a finding
invalidates a later phase's plan.

## Read first (all of it, before touching code)

1. `docs/reports/audit_2026-09-29/AUDIT_AND_IMPROVEMENTS.md`: the current state,
   fixes F1–F8, model changes M1–M7, open issues A1–A10, and the test-run protocol (§7).
2. `docs/research/RESEARCH_PROMPTS.md`: seven research prompts plus shared context.
3. `docs/reports/replay/audit_3/FINAL.md`: how results must be classified.
4. `README.md`, `docs/ARCHITECTURE.md`, `docs/LOCKED_INPUTS.md`,
   `docs/rules/PRICING_DOCTRINE.md`, `docs/rules/AUTONOMY.md`,
   `docs/resort/WINTER_PARK_KNOWLEDGE.md`, `docs/proving_ground/DESIGN.md`.
5. Code: `src/compose/__init__.py`, `src/bookprob/__init__.py`,
   `src/ceiling/__init__.py`, `src/guardrails/__init__.py`, `src/leakage/`,
   `src/min_stay/`, `src/features/__init__.py`, `src/pms/sync.py`,
   `src/inventory/events.py`, `src/inventory/repair.py`, `src/runcache.py`,
   `src/eval/replay.py`, `src/eval/shadow.py`, `src/proving_ground/*`,
   `proving_ground_exam/*`, `config/policies/default.yaml`.

## Facts you must start from (verified 2026-09-29)

- Three homes: Summit Haus (312 Northwoods) and Overlook Ridge (300 Northwoods) are
  near-identical twins with the same owner. Cloud 9 has a separate owner. The market is
  Winter Park / Fraser, CO. Guesty is the system of record.
- Real data is thin: 88 reservations (46 confirmed guest stays, 2 owner stays, 40
  inquiries). Pacing snapshots run from 2026-08-18 with gaps on 09-02 and 09-04..09-19.
  **Never stitch across gaps.**
- Elasticity is a config constant per season. Peak is −0.65, so the optimum is always
  the ceiling. Nothing learns it (audit M1). In the closed-loop simulator, engine regret is
  45.0% weekly / 35.4% daily vs flat 14.9% (L1, seed 20260925).
- The current simulator (`W1_calm`) is one demand number per night and never produces a
  booking. `W1_discrete_choice` exists but is unused.
- Engine speed: ~7s per property per 365-night decision day, and ~71s for a daily-step
  season. The run-scoped cache is only valid because signals and inventory are **not
  written during a pricing run**. Keep that true, or extend `src/runcache.py`
  deliberately.
- Run the CLI as `PYTHONPATH=. .venv/bin/python -m src.cli.main ...` (`uv run` fails).
  Tests: `.venv/bin/python -m pytest -q`. Three failures in `tests/test_memory.py`
  pre-exist and are out of scope. Do not "fix" them by editing those tests.

## Non-negotiable rules

1. **No Guesty writes, ever.** Use only the `dry_run` adapter. `rate_changes` must show 0
   applied Guesty writes before and after every run. Keep the refusal tests.
2. **Never modify `data/wp_pricing.db`.** Work on copies in a scratch or `.testrun_runs/`
   folder. Run `repair-bookings --apply` only on copies. DB copies must never be committed
   (`.gitignore` covers `docs/reports/**/*.db*`).
3. **Test first.** Every behavior change starts with a failing test.
   Every performance change needs an identical-output proof (serialize every
   `Recommendation` field for ≥3 property-days before and after, and compare hashes).
4. **New models ship behind policy flags, default OFF**, until they win on the evaluation
   ladder (Phase 6). Existing guardrails, hard invariants, the autonomy ladder and
   explanations stay intact. New price drivers must emit `Reason`s with dollar
   contributions.
5. **Do not tune to pass.** Never change simulator parameters, thresholds or
   elasticity to make a score look better. Simulator parameters come from research
   dossiers and data, fixed *before* the engine is evaluated on them. Keep a held-out
   scenario set the engine is never tuned on.
6. **No individual-level personal data.** No buying or scraping of personal records.
   Guest data from Guesty is minimized (city/state/country level, party composition, no
   names/emails/phones in the pricing DB) under a written data contract.
7. **Point-in-time discipline.** Anything the engine reads in replay or simulation must be
   knowable on the decision day (`as_of`). New signals need `observed_at` vintages.
8. **Honest reporting.** Every claim is labelled **proven / suggestive / unknown**, with
   the command that produced it. Report failures with their output. Cite web sources with
   URL and access date; mark unverifiable claims UNVERIFIED.
9. Branch from the current branch (`feature/point-in-time-replay`) into a new branch
   `feature/market-sim-and-learning`. Commit in small, reviewable commits per phase.
   Do not push or merge unless the operator asks.

---

## Phase 0 — Baseline (short)

- Run the full test suite and record the result.
- Copy the operator DB, then run `repair-bookings` (dry run) and `repair-bookings --apply`
  on the copy. Confirm counts of ~130 / 30 / 6 / 688 / 42, or explain the differences.
- Record baselines on the repaired copy:
  - Early (08-18..09-03) and clean (09-20..09-29) replays, censor 09-29.
  - Proving Ground L1 at weekly and daily cadence for seeds 1–5.
  - Engine timing per property-day.
- Deliverable: `docs/reports/market_sim/phase0_BASELINE.md`.

## Phase 1 — Research (all seven prompts)

Execute all seven prompts in `docs/research/RESEARCH_PROMPTS.md`, using web search and
fetch. Write one dossier per prompt to
`docs/research/dossiers/0N_<slug>.md` following each prompt's deliverable spec.
Depth over breadth: prefer primary sources (DMO reports, DestiMetrics public summaries,
Guesty API docs, academic RM papers).

Then synthesize two documents that the build phases will consume:

1. `docs/research/SIM_PARAMETERS.md`: the calibration table for the simulator. For each
   shopper segment (families-at-holidays, ski groups, couples, international,
   multi-generational, corporate/retreat, plus any the research supports), give its
   share by season, arrival-by-lead-time distribution, LOS distribution, party size,
   channel mix, willingness-to-pay distribution relative to the market median, price
   sensitivity, and sensitivity to snow, access and macro conditions. Every cell needs a
   source and a confidence rating (high/med/low). Low-confidence cells get a sensitivity
   range and are swept in Phase 2.
2. `docs/research/MODEL_SPEC.md`: equations and estimation procedures for M1–M5 (below),
   chosen from dossier 5, with data requirements and failure modes.

Gate: both synthesis documents exist, and every parameter has a source or an explicit
"assumed, swept" label.

## Phase 2 — Market simulator v2 (the fast, realistic world)

Build a new world alongside W1 (keep W1 working for backward compatibility). Suggested
layout (adapt if the code suggests better): `proving_ground_exam/market/` for world logic
and scoring, which must not import the engine (the examiner stays independent);
`src/proving_ground/market_loop.py` for the engine side; and
`proving_ground_exam/scenarios/*.yaml`.

**World model (one simulated day at a time):**
- **Shoppers.** Each day, a Poisson number of shoppers arrives per segment. Each has
  target check-in, LOS, party size, budget/WTP and channel, all drawn from
  `SIM_PARAMETERS.md` and modulated by season, holidays, snow quality, access and macro
  state.
- **Choice.** Each shopper sees a consideration set: our homes that fit the party size
  and are available for the whole stay, competitor listings, and an outside option. They
  choose by multinomial or mixed logit on total stay price, quality and fit. Include
  inquiries that don't convert (with a conversion model) and cancellations (with a hazard
  by lead time).
- **Competitors.** At least four agent types: static owner, market-follower,
  generalized-tool emulator (a PriceLabs-like rule set documented from public sources),
  and adversarial undercutter. Competitor prices are visible to the engine only through a
  simulated scrape, with realistic noise, missing listings and outages.
- **Engine interface.** The engine sees only what it would see live: its calendar,
  bookings and reservations (written through the same tables the Guesty sync writes),
  pacing snapshots, scraped comps and dated signals. Its prices are applied to listed
  prices (closed loop). The world may never read engine internals.
- **Scoring.** Score realized revenue and RevPAN at booking-time prices. Also report
  occupancy, ADR, booking-window mix, orphan nights and guardrail triggers. Compare against:
  - a perfect-hindsight upper bound on the realized shopper stream (ILP or greedy with a
    documented gap);
  - flat seasonal pricing;
  - a comp-median follower;
  - the generalized-tool emulator;
  - the current engine (`model_version` pinned).
- **Scenarios.** Build at least 15 scenarios as YAML, including: normal, drought,
  record snow, late opening, early closure, I-70 closure weekend(s), holiday calendar
  shift, recession / consumer-confidence drop, DEN capacity cut, new-supply surge (+15%
  listings), competitor price war, scraper outage, stale PMS sync, mid-season regime
  change, and a pandemic-like collapse. Mark ≥4 as **held-out**. Nobody tunes on them.
- **Statistics.** Use ≥30 seeds per scenario, common random numbers so policies see the
  same shopper stream, paired differences, bootstrap 95% CIs, and a multiple-comparison
  note when many variants are tried.
- **Speed.** Run scenario × seed jobs in parallel processes, with deterministic seeding
  and one fresh DB per job. Target: 15 scenarios × 30 seeds × 180 days for 3 homes in
  under 1 hour on a laptop. If that isn't met, profile first. Then add incremental
  repricing (only nights whose inputs changed) with an identical-output proof, before any
  cruder shortcut.
- **CLI.** `proving-ground market --scenario <name|all> --seeds N --workers K --policy <id>`
  writes a manifest with a content hash, a scoreboard CSV and a Markdown report.

**Validation before any engine result is trusted (sim-to-real).** On a "normal"
scenario calibrated to Winter Park, the simulator must reproduce Mont Luxe's observed:
- booking-window distribution;
- LOS distribution;
- inquiry-to-booking ratio;
- rough occupancy by season.

All four must fall within the ranges stated in `SIM_PARAMETERS.md`. If the real data is too
thin, say so and use market aggregates. Document every mismatch.

Gate: validation checklist passes (or failures are documented and accepted as
limitations), determinism holds (same seed gives the same hash), and the current engine
has a baseline scoreboard on all scenarios.

## Phase 3 — Model changes (each behind its own flag, default off)

Implement from `MODEL_SPEC.md`, one change at a time, each with unit tests and its own
`Reason` codes:

- **M1 Learned price sensitivity.** A hierarchical Bayesian elasticity with priors from
  policy, pooled across homes, seasons and markets, and updated from our own price and
  booking outcomes (as-of safe). Add **bounded exploration** (e.g. Thompson sampling
  within move caps, never on peak-blackout nights) so elasticity is identifiable.
  Interim safety guard: a peak night materially behind pace inside 21 days must not keep
  an inelastic assumption.
- **M2 Demand level moves price.** Pacing ratio, SQI, events and consumer-layer
  indicators shift the demand intercept or reference price, not just probability or
  bounds.
- **M3 Booking-horizon pricing.** Finite-horizon dynamic pricing or bid-prices, using
  lead-conditioned arrival and booking rates (`_lead_observations` is the starting data).
- **M4 Stay pricing.** Length-of-stay-aware expected revenue, with minimum stay as a
  decision variable optimized jointly with price and orphan-gap handling.
- **M5 Portfolio pricing.** Joint pricing of the twins with a cannibalization term.

Also do the smaller items: A1 (as-of data health), A2 (as-of, non-self-referential
seasonal anchor), A3 (resolved-only pooled rate), A5 (America/Denver timestamps), A7
(cheaper determinism gate), A8 (memoize `seasonal_anchor` / `pacing_ratio`, with
identical-output proof), and A9 (cancellation model). A4 (memory hash in replay
metadata) and A10 (report provenance) are small. Do them.

Gate: all tests pass, and with every new flag off, output is byte-identical to the
Phase 0 engine.

## Phase 4 — Consumer layer

- Write `docs/research/GUEST_DATA_CONTRACT.md` from dossier 2: field, source API,
  channel availability, privacy class, retention, and use.
- Extend `src/pms/sync.py` to capture only the contracted fields into new, minimized
  columns or tables. Add tests with realistic Guesty response shapes.
- Wire Guesty inquiries (stored in `reservations` since 2026-09-29) into the inquiry
  conversion feature (`src/elasticity/__init__.py` reads only the CSV
  `booking_inquiries` table today).
- Add the top leading indicators from dossier 3 as `signal_definitions` with as-issued
  vintages. They start at the `shadow` ladder status, never `active`.
- Feed segment mix and indicators into the simulator (scenario parameters) and, behind
  flags, into M2.

## Phase 5 — Evaluation ladder

For each flag (and the sensible combinations), run in order:
1. unit tests;
2. replay (early and clean windows on the repaired copy), reporting both per-decision
   and deduplicated results;
3. market simulator on all **non-held-out** scenarios;
4. the held-out scenarios, **once**, at the end.

A change "wins" only if it beats the current engine on paired realized revenue with a
CI that excludes zero on the normal scenario, and does not lose materially on any
stress scenario. It must also keep guardrail violations at 0 and not worsen calibration.
Report losers as clearly as winners. Do not turn any flag on by default. Recommend
defaults for the operator to approve.

## Phase 6 — Portability check

Using dossier 6, create a second resort/market config (e.g. one of the top-ranked
markets). Run the simulator with that market's scenario parameters, and write down
exactly what had to change (`config/resort/*.yaml`, signals, scrape region). That list
is the portability spec.

## Phase 7 — Final report

Write `docs/reports/market_sim/FINAL.md`. Include:
- a two-minute plain-English owner summary;
- a table of every change with its test and commit;
- the simulator validation results;
- the scoreboard across scenarios (engine vs baselines vs each flag) with CIs;
- held-out results;
- what is proven, suggestive and unknown;
- recommended flag defaults (operator decides);
- remaining risks;
- the exact commands to reproduce every number.

Also update `docs/proving_ground/README.md` and the audit document's status column.

## Phase report format (every phase)

`docs/reports/market_sim/phaseN_<name>.md` contains: what was done, files changed, tests
added (with a failing-then-passing excerpt), commands run with exit codes, results
labelled proven/suggestive/unknown, deviations from this plan and why, and open
questions for the operator.
