# Lead diagnostic agent — 312 Northwoods (`summit_haus`)

You are the lead diagnostic agent for the Mont Luxe Collection property:

- **Property ID:** `summit_haus`
- **Display name:** 312 Northwoods
- **Owner:** `northwoods`
- **Market:** `grand_home` — Winter Park / Fraser / Tabernash
- **Run window:** 2026-09-24 through 2027-09-23 inclusive (the next 365 stay dates)

Your task is to perform a complete, **read-only, end-to-end diagnostic** of the pricing
engine for this property.

**The goal is not to claim that the engine beats Guesty on revenue.** Next-year prices
alone cannot establish revenue superiority — that requires forward shadow-mode measurement
against actual bookings (see the closing section). The goal here is to determine whether the
engine produces **defensible, comp-grounded, explainable** recommendations, and whether its
reasoning holds up when compared *afterward* with Guesty and the generic mountain-town market.

## Absolute restrictions
- Do not modify tracked repository files.
- Do not modify policy YAML, portfolio YAML, schemas, or production data.
- Guesty is **read-only**. You may pull listings/calendar/reservations into the local DB
  (`wp-price sync-guesty` or GET helpers). You must never write prices, min-stay, or
  availability back. Do not run `wp-price push` (any adapter). Do not call
  `GuestyClient.set_rate`, `push_rate`, or `push_recommendations`. Do not pass
  `--confirm-live-write`. Do not PUT/POST/PATCH/DELETE `open-api.guesty.com` except OAuth.
- Do not run **unscoped** `recommend`, `audit`, `export`, or `push`. Every invocation must
  carry `--property summit_haus`. Never run `push` in this diagnostic.
- Do not inspect Guesty's current prices, reservations, calendar rates, or the historical
  retrospective **before the blind recommendation run is frozen and hashed** (Phase 2).
- Do not use Guesty rates as an input, anchor, validation target, or comp source during the
  blind phase.
- Use an isolated disposable database (`--db /tmp/testrun_summit_haus.db`) or a clearly
  isolated read-only workspace/worktree. Print the DB path at the top of your report.
- **If any command would touch `creekside_haven`, stop and report the scope failure.**
  (`creekside_haven` is an extra Guesty listing that lingers in the DB — see
  `src/db/__init__.py:234` — which is exactly why unscoped runs are forbidden.)
- **Suggestions only: do not implement fixes.** The only file you create is your report,
  `docs/reports/TESTRUN_312_northwoods.md`.

## Known experimental blockers (treat as givens, verify, do not fix)
1. **Unscoped property-selection defect** — the DB contains `creekside_haven`; an unscoped
   run would price it. Always scope to `summit_haus`.
2. **Guesty write adapter is off-limits** — never write rates back. Live calendars
   must be unchanged. Confirm `Guesty write count: 0` in the report.
3. **`round_price_conservative` ceiling-overrun defect** — rounding may push a valid
   recommendation past the ceiling and make it fail the independent audit. Watch for it;
   classify, don't patch.
4. **Incomplete pacing history** — booking-probability output must be reported as **weak /
   uncalibrated**, never as validated demand.
5. **Guesty data must not be inspected before the blind run is frozen** — enforce the
   blind→freeze→reveal ordering yourself.

Separate observed facts, inferences, hypotheses, and recommendations throughout.

---

## Phase 0 — preflight and audit
Read: `README.md`, `docs/ARCHITECTURE.md`, `docs/LOCKED_INPUTS.md`, `docs/rules/AUTONOMY.md`,
`docs/rules/COMP_DATA.md`, `docs/CLOUD9_RUNBOOK.md`,
`docs/reports/PRODUCTION_READINESS_AUDIT_2026-09-20.md`,
`docs/reports/GUESTY_RETROSPECTIVE.md`, `config/portfolio/mont_luxe.yaml`, and the relevant
`config/policies/*.yaml`.

Run the deterministic checks: `pytest -q`, `mypy` (per `pyproject.toml`),
`python scripts/production_preflight.py`, and any configured coverage/dependency checks.

Specifically investigate:
- the unscoped property-selection defect;
- the `round_price_conservative` ceiling-overrun defect (do recommendations stay inside
  `[floor, ceiling]` **before and after** rounding?);
- incomplete pacing history;
- absence of historical contemporaneous comp snapshots;
- whether the full 365-day horizon has actual market coverage.

Do not fix anything. Classify every finding as: **experiment blocker · measurement
limitation · recommendation-quality risk · operational-risk finding · low-priority
improvement.**

## Phase 1 — blind data acquisition (no Guesty prices)
Build the best independent input set available, without touching Guesty prices:
- initialize the isolated DB;
- load only permitted non-Guesty property/market inputs;
- discover the market independently (`wp-price discover-comps --date <D>` across peak_ski,
  early_winter, shoulder_spring, summer for a 5-bedroom luxury profile via
  `--min-bedrooms`/`--min-sleeps`);
- gather fresh market-wide comp data (`wp-price scrape-comps --horizon 365`) →
  `comp_snapshots` + whole-market `market_snapshots`;
- gather the curated comp evidence available without Guesty;
- collect market-wide price distributions;
- run relevant signals + `wp-price health --property summit_haus`;
- document coverage, freshness, sample sizes, degraded modes, and row counts.

**The generic market benchmark must be independent of the curated comp set.** Report, where
available: market sample size · p25 · p50 · p75 · validated min/max · size/bedroom filters ·
date sampled · freshness · whether the statistic is whole-market or luxury/group-size
filtered. **Do not silently substitute the curated-comp median for the generic market
average.**

## Phase 2 — complete blind recommendation run, then FREEZE
Generate recommendations for every available stay date in the window, scoped explicitly:

```bash
wp-price recommend \
  --property summit_haus \
  --from 2026-09-24 \
  --to 2027-09-23 \
  --limit 500 \
  --technical \
  --db /tmp/testrun_summit_haus.db
```

Then export the complete set, scoped:
`wp-price export --property summit_haus --from 2026-09-24 --to 2027-09-23 -o data/exports/testrun_312.csv --db /tmp/testrun_summit_haus.db`.
Preserve and classify any dates the engine cannot price — do not fill them manually.

Capture, wherever available: stay date · listed price used · recommended price · floor ·
ceiling · confidence · booking probability · expected RevPAN · comp evidence · market
percentile · elasticity/beta · leakage/gap signals · data-health/autonomy level · reason
codes · rounding result · blocked/escalated/degraded status.

**Before looking at Guesty, freeze the output: record the export file's SHA-256 hash and row
count in your report.** This is the integrity boundary — nothing after this may alter the
blind run.

## Phase 3 — Guesty reveal and comparison (only after freeze)
Obtain Guesty's current forward prices by a **read-only** method (`nightly_inventory`
listed/booked columns — inspect the schema first). Do **not** treat current Guesty prices as
historical truth, and do **not** use them to retroactively alter the frozen run.

Compare each recommendation against: (1) Guesty's current listed price; (2) generic market
**p25, p50, p75**; (3) curated-comp statistics; (4) the property's own floor and ceiling;
(5) the engine's stated reason.

Classify each significant divergence as: **well-supported by independent evidence ·
potentially justified but dependent on weak assumptions · likely underpriced · likely
overpriced · invalid (missing/stale/bad data) · impossible to judge.**

Pay special attention to: off-season and shoulder-season prices; prices below or far above
the market distribution; recommendations near the ceiling; low-confidence recommendations;
prices affected by missing pacing; any price that fails the independent audit due to
rounding; **whether elasticity defaults appear to suppress prices** (the prior audit found
`summer: -1.10` / `shoulder: -1.70` can push the RevPAN optimum below the reference price —
e.g. this property showed engine $645 vs ceiling $969 vs Guesty $1,986 on a summer night);
and whether the ceiling is defensible for this property and date.

## Phase 4 — stress tests (analytical, no code changes)
For each of: no comps · stale comps · low comp coverage · missing pacing · weak ceiling
confidence · elasticity beta shifted modestly both directions · high-demand dates · orphan
gaps / short windows · corrupted or implausible listed prices · rounding at floor/ceiling
boundaries · full-market vs luxury-filtered statistics — state whether the result is
**robust · highly sensitive · unsafe · unmeasurable with current data.**

## Phase 5 — final report → `docs/reports/TESTRUN_312_northwoods.md`
1. Executive verdict. 2. Exact commands + data sources used. 3. Blind-run integrity statement
(hash + row count). 4. Data coverage and freshness. 5. Full-year recommendation summary.
6. Comparison with Guesty. 7. Comparison with generic market averages. 8. Largest divergences.
9. Reasoning-quality assessment. 10. Audit and safety findings. 11. Stress-test results.
12. Proposed changes, ranked by impact and confidence. 13. External tools worth considering.

Every proposed external tool or structural change must include: the specific problem it
addresses · a researched thesis (cite external evidence via web search — PriceLabs / AirDNA /
Beyond methodology, STR elasticity research, ski-market demand studies) · why the current
repo can't address it adequately · expected benefit · cost + operational complexity · new
failure modes · a validation plan · and a verdict: **test / shadow / adopt / reject.**

Do not edit code. Do not claim revenue superiority. Confirm at the end that you changed no
tracked files.

## Property-specific focus — 312 Northwoods
This is one of the "twins" (near-identical 5bd to `overlook_ridge` / 300 Northwoods). Probe
hardest whether **summer/shoulder is underpriced by the elasticity betas** vs. genuinely soft
demand — that is the highest-value question for this property.

---

## Separate track (not part of this run) — forward shadow validation
These reports cannot prove the engine's niche Colorado signals produce better *outcomes* than
Guesty. Only a forward shadow run can: keep Guesty's actual price live, record the engine's
recommendation daily, and record bookings, booking lead time, cancellations, occupancy, ADR,
and realized RevPAN — then evaluate by season, property, lead-time bucket, and price-distance
bucket. Flag this as the recommended next experiment; do not attempt it here.
