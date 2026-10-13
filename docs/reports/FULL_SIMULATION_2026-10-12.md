# Full simulation and performance audit — 2026-10-12

**Run commit:** `82f3f0a` (tracked tree clean at run time)  
**Artifact root:** `~/wp-price-runs/full_sim_20261012_82f3f0a/`  
**Copied artifacts:** [`docs/reports/market_sim/full_sim_82f3f0a/`](market_sim/full_sim_82f3f0a/)

The report and copied artifacts were added after the simulation, so the
checkout is not clean even though the run manifests record a clean tree. The
manifests, logs, and retained databases stay under the external artifact root.

Simulated shopper revenue only. Not realized revenue. `default.yaml` and
`calibration.yaml` were not edited. Guesty was not touched.

Evidence labels: **proven** = produced on 2026-10-12; **inherited** = earlier
repo reports; **unknown** = not exercised.

This report was audited a second time after its first version. That audit
corrected several claims and fixed two measurement defects in code. The
corrections are listed in [Second audit](#second-audit-corrections-and-fixes).

---

## Executive summary

| Layer | Result | Notes |
|--------|--------|--------|
| Proving-ground exam isolation | **PASS** | proven |
| Production preflight | **PASS** | proven |
| Quality gates (`scripts/quality_gates.py`) | **PASS** | proven: 840 tests at run time, 79.0% coverage; 842 / 79.05% after the second-audit fixes |
| Pytest `-m slow` | **PASS** | proven: 3 tests, ~33 s |
| Proving Ground L1 | **FAIL** | proven: safety gates pass; regret, vs-baselines, Brier, tail-loss fail. Same numbers as 2026-10-08 |
| Market sim 5-seed screen (`normal`) | **REPRODUCED** | engine − flat **−$46,680** (0/5). Same as the 2026-10-09 post-promote run on every seed |
| Candidate `seasonal_base_anchor_full_shoulder` | **CONFIRMED (inherited), awaiting owner** | 5-seed screen reproduced (+$26,343 vs default, 5/5). Held-out confirmation was already done on 2026-10-09 |
| Runtime: `--incremental` | **NO PROVEN WIN** | same revenue; content hash differs, now explained; speed-up is within noise |
| Ops tests | **PASS** | proven: `tests/ops/` 445 passed, including `test_audit_findings.py` |

### What this run shows

The main result is that the merge at `82f3f0a` did not change engine
behaviour. All 35 screen rows and all 5 candidate rows match earlier runs to the
cent:

- engine and candidate rows match the 2026-10-09 `79dae5d` runs
  (`post_promote_79dae5d/default_normal_*`, `screen_base_anchor_79dae5d/`);
- the 30 benchmark rows match the 2026-10-08 screen
  (`full_sim_20261008_79dae5d`) on revenue and content hash.

So the ops-layer merge (`fb2e1ec`, `82f3f0a`) is score-neutral for pricing. No
revenue number in this report is new evidence about the engine.

### Top fixes (impact-ranked)

1. **Owner decision on `seasonal_base_anchor_full_shoulder`.** It is already
   confirmed. On 2026-10-09 it was tested on seeds 6–30 across six scenarios:
   +$23.3k on `normal` (25/25), gap to flat about −$23k, and `pandemic_collapse`
   flat (interval includes zero). See
   [`BASE_ANCHOR_2026-10-09.md`](market_sim/BASE_ANCHOR_2026-10-09.md). The
   blocker is owner sign-off on the guard and on the base rates (Summit $793,
   Overlook $916, Cloud 9 $1,035), not more simulation. Do not rerun seeds 6–30
   for this candidate unless the engine changes.

2. **The remaining gap is peak, but only once the anchor is in.** On the default
   engine the loss is spread across seasons: early winter −$11.5k, peak −$18.2k,
   shoulder −$16.9k. About 61% is off-peak, and that is what the anchor
   targets. At peak the engine prices above flat (ADR $940 vs $900, 32.8% of
   peak recommendations at the ceiling) and sells fewer nights (occupancy 0.528
   vs 0.615). Cloud 9 carries the largest share (−$22.6k). The "only flat sold"
   line (−$53.8k) covers every season, so it does not show a peak problem by
   itself. The next diagnostic should decompose the **candidate** against flat,
   not the default engine.

3. **Proving Ground L1 cannot fail on the vs-baselines gate in an informative way.**
   In W1_calm, `comp_median_follower` scores exactly like `flat_seasonal`. The
   world has no comp snapshots, so every night (166/166) falls back to the flat
   price. `moat_off` scores exactly like `engine`. The best baseline is
   therefore flat. Give W1 a comp series, or drop it from the gate, before L1
   economic gates are used as release criteria. The Brier gate is valid: it
   compares engine Brier (0.190) with a predict-the-mean forecast, and −0.97
   means the engine is about twice as bad as that forecast.

4. **Runtime is engine-bound.** One full-season engine job takes 117–156 s
   depending on load. The 15 jobs/min figure comes from a mixed board where
   30 of 35 jobs are cheap benchmarks. An engine-only board at seven workers
   runs about 7 jobs per ~2 min (the 5-job candidate board took 119 s). Profile
   before changing code. The 2026-10-09 batching profile is the baseline
   (136 s, `persist_recommendations=False`).

5. **Disk.** The host was at 95% (26 GiB free at start, 23 GiB after). This run
   retained **1.5 GB** (1.1 GB screen and 396 MB candidate). Retain databases
   only when a decomposition or property diagnosis needs them.

---

## Test matrix

| Step | Command / tool | Exit | Duration (approx.) | Log |
|------|----------------|------|-------------------|-----|
| Env | venv + `manifest_env.txt` | 0 | — | `$RUN/manifest_env.txt` |
| Isolation | `scripts/check_proving_ground_isolation.py` | 0 | &lt;1s | `$RUN/gate_isolation.log` |
| Preflight | `scripts/production_preflight.py` | 0 | &lt;1s | `$RUN/gate_preflight.log` |
| Quality gates | `scripts/quality_gates.py` | 0 | ~73s (pytest 67 s) | `$RUN/gate_quality.log` |
| Pytest slow | `pytest -m slow --ignore-glob='* 2.py'` | 0 | 33s | `$RUN/pytest_slow.log` |
| PG L1 | `proving-ground run --level 1 --seed 20260925` | 0† | 9s | `$RUN/proving_ground_l1.log` |
| Market screen | `proving-ground market --scenario normal --seeds 5 --workers 7 --grid --diagnostics --retain-dbs normal` | 0 | 137s | `$RUN/market_screen.log` |
| Audit / decompose | `audit_market_sim.py`, `property_diagnostics.py`, `decompose_market_sim.py` | 0 | — | `$RUN/market_screen_benchmarks/*` |
| Candidate | `--policy engine --engine-policy config/policies/candidates/seasonal_base_anchor_full_shoulder.yaml --retain-dbs normal`, 5 seeds | 0 | 119s | `$RUN/screen_seasonal_base_anchor_full_shoulder/` |
| Runtime probe | `run_market_job` full vs incremental, seed 1 | 0 | 223s | `$RUN/runtime_probe/timing.txt` (script not kept) |
| Ops smoke | 3 tests (command not recorded) | 0 | &lt;1s | `$RUN/ops_smoke.log` |

†CLI exit 0; audit verdict **FAIL** (economic gates).

**Not run:** 15×30 full grid (~1,800 jobs), Guesty live writes,
`run_testruns.py` agents, sensitivity overlays, L2 vintages, replay on the
production DB.

---

## Revenue performance (proven, 5-seed `normal`, promoted `default.yaml`)

All figures reproduce the 2026-10-09 runs exactly.

### Portfolio (audit)

| Comparison | Mean Δ (engine − other) | 95% bootstrap | Seeds ≥ 0 |
|------------|-------------------------|---------------|-----------|
| engine − flat | **−$46,680** | −$58,105 to −$35,372 | 0/5 |
| engine − comp_median | **−$38,864** | −$49,333 to −$28,396 | 0/5 |
| engine − tool | **+$6,383** | −$4,424 to +$18,925 | 2/5 |

Mean season revenue by policy: flat $267,180; premium_cap $266,816;
comp_median $259,364; property_flat $256,328; comp_property $253,427;
**engine $220,500**; tool $214,117. The engine beats only `tool`, and that
interval includes zero.

### Decomposition (engine vs flat)

- Total Δ: **−$46,680** per season (mean).
- Night split: both sold −$25,299 (price), only flat sold −$53,760, only engine sold +$32,379.
- By season: early winter **−$11,531** (engine ADR $478 vs $750, 20.1% of recs at the floor); peak **−$18,210** (ADR $940 vs $900, occupancy 0.528 vs 0.615, 32.8% at the ceiling); shoulder **−$16,939** (ADR $376 vs $650, 23.2% at the floor).
- By property: Cloud 9 **−$22,564** (occupancy 0.517 vs 0.614), Summit Haus −$13,560, Overlook Ridge −$10,556.

### Candidate overlay (`seasonal_base_anchor_full_shoulder.yaml`)

Against this screen (promoted default engine):

| Comparison | Mean Δ | 95% bootstrap | Seeds ≥ 0 |
|------------|--------|---------------|-----------|
| candidate − default engine | **+$26,343** | +$20,762 to +$33,472 | 5/5 |
| candidate − flat | **−$20,336** | −$36,745 to −$4,044 | 1/5 |
| candidate − comp_median | −$12,521 | −$27,974 to +$2,932 | 1/5 |
| candidate − tool | **+$32,727** | +$19,688 to +$49,998 | 5/5 |

Inherited confirmation (seeds 6–30, 2026-10-09): `normal` +$23,296 (25/25),
`price_war` +$23,339, held-out `holiday_shift` +$20,708, `den_capacity_cut`
+$22,869, `regime_change` +$18,904 (23/25), `pandemic_collapse` +$1,693
(−$527 to +$4,130, 14/25).

Guardrail mix, seeds 1–5 (retained, so counts are real): the candidate
removes `sanity_floor` (150–194 per season → 0) and raises `clamped_increase`
(19–24 → 74–79). Mean occupancy falls from 0.577 to 0.537 while ADR rises from
$707 to $850.

---

## Runtime performance

| Metric | Value |
|--------|--------|
| Screen wall clock | 136.8 s for 35 jobs (5 engine, 30 benchmark) |
| Candidate wall clock | 119.3 s for 5 engine jobs |
| Full-season engine job (seed 1) | 117.1 s (original probe); 152.6 s on rerun with two jobs in parallel |
| Incremental | 106.0 s (original, 1.10×); 155.9 s on rerun (0.98×) |
| Retained DBs | 1.1 GB screen + 396 MB candidate |

### Incremental hash mismatch (corrected)

The original probe recorded `revenue_match=True`, `hash_match=False`. The first
version of this report called that a "probe anomaly" because a rerun matched.
That rerun had turned off `persist_recommendations`, which hid the cause.

Rerun with `run_market_job` defaults
([`runtime_probe_rerun.py`](market_sim/full_sim_82f3f0a/runtime_probe_rerun.py),
[output](market_sim/full_sim_82f3f0a/runtime_probe_rerun.txt)):

- full: hash `a57e7e8f…`, identical to the screen's seed-1 engine row;
- incremental: same revenue, prices, and guardrail actions, but 3 fewer
  no-action recommendation rows (`"": 33,733` vs `33,736`), so the hash
  differs.

Incremental mode skips repricing on days when nothing changed, so it writes
fewer rows. This is expected bookkeeping, not a pricing defect. Content hashes
are not comparable between full and incremental runs. The comparable checks are
revenue and the recommendation-field test
(`test_incremental_reprice_matches_full_recommendation_fields`). The speed-up is
not established: 1.10× once and 0.98× once. Do not use incremental mode for
boards.

---

## Second audit: corrections and fixes

### Corrections to the first version of this report

| First version said | Evidence | Correction |
|---|---|---|
| Screen "improved vs inherited Oct-8 screen (−$86k)" | Every engine row equals `post_promote_79dae5d` seeds 1–5 | The improvement came from the cap promotion (`c7c7672`) and was measured on 2026-10-09. This run reproduces it. |
| Candidate **SUGGESTIVE**; next step "confirm on held-out seeds 6–30" | `BASE_ANCHOR_2026-10-09.md`, `confirm_base_anchor_79dae5d/` | Already confirmed on six scenarios. The next step is the owner decision. |
| "Peak volume is the main lever (only_flat_sold −$53.8k)" | `decomp_normal_vs_flat.md` by season | "Only flat sold" covers all seasons. Off-peak is 61% of the default-engine gap. Peak leads only after the anchor. |
| Incremental hash mismatch is a "probe anomaly" | Rerun with defaults reproduces it | Real and explained (above). |
| "Seven workers delivered ~15 jobs/min" | 30 of 35 jobs are benchmarks | Engine-only throughput is ~3.5 jobs/min. |
| Retained DBs ~1.1 GB | `du` | 1.5 GB including the candidate. |
| Ops "integration matrix smoke passes" | 3 unnamed tests | Full `tests/ops/`: 445 passed. |
| L1 vs-baselines compares to three baselines | W1 has no comp snapshots | Two of the three baselines duplicate flat and the engine. |
| Copied artifacts are enough to inspect the candidate | Only the audit JSON was copied | Added `candidate_scoreboard.csv`, `candidate_property.md`, and both runtime-probe outputs. |

### Code fixes

1. **Score-only market jobs reported zero guardrails**
   (`src/proving_ground/market_loop.py`). The pool sets
   `persist_recommendations` only when databases are retained, and the
   examiner counted guardrails from persisted rows. Every score-only board
   therefore reported `guardrail_triggers = 0`, and an identical job had a
   different content hash depending on retention (seen in the old runs: 5/5
   revenue match, 0/5 hash match against score-only boards). As a result,
   `scripts/paired_market_sim.py` reported a guardrail delta of exactly zero
   on every seed-6–30 confirmation. `COMBINED_CONFIRMATION_2026-10-08/09`
   turned that into "guardrail trigger count unchanged vs default". The
   retained diagnostics show a real drop (mean 2,596 → 2,243 on seeds 1–6).
   The engine job now counts guardrail actions from the recommendations it
   produced, whether or not they are persisted. Retained-run numbers and
   hashes are unchanged. Score-only runs now report real counts and match
   retained runs. Old score-only scoreboards keep their zeros, so do not
   `--resume` an old score-only board across this change.
   Test: `test_score_only_engine_job_reports_the_retained_guardrail_counts`.

2. **L1 report readability** (`src/proving_ground/runner.py`, display only;
   the L1 run hash is unchanged at `9be657c9…`). The Brier column now prints
   `n/a` for policies that make no forecast, where it used to print `0.0000`.
   The "still fake or stubbed" list now names any baseline that scored
   identically to its twin. Test:
   `test_proving_ground_report_does_not_print_unscored_brier_or_hide_twin_baselines`.

Verification after the fixes: `scripts/quality_gates.py` **842 passed,
79.05% coverage**, mypy clean; `pytest -m slow` 3 passed; L1 rerun gives the
same hash and verdict; `tests/ops/` 445 passed.

### Still open

- Score-only boards from before this fix (including all seed-6–30
  confirmations) have no guardrail evidence. Rerun a confirmation only if
  guardrail behaviour matters to the owner decision.
- The first version's "29 passed, 1 deselected" targeted run had no recorded
  command. The full suite above replaces it.

---

## File index

| Path | Description |
|------|-------------|
| `~/wp-price-runs/full_sim_20261012_82f3f0a/` | Full run tree |
| `docs/reports/market_sim/full_sim_82f3f0a/scoreboard.csv` | 5-seed screen |
| `docs/reports/market_sim/full_sim_82f3f0a/audit.json` | Audit gates and deltas |
| `docs/reports/market_sim/full_sim_82f3f0a/property.md` | Property diagnosis (default engine) |
| `docs/reports/market_sim/full_sim_82f3f0a/decomp_normal_vs_flat.md` | Engine vs flat decomposition |
| `docs/reports/market_sim/full_sim_82f3f0a/candidate_scoreboard.csv` | Base-anchor candidate, 5 seeds |
| `docs/reports/market_sim/full_sim_82f3f0a/candidate_property.md` | Property diagnosis (candidate) |
| `docs/reports/market_sim/full_sim_82f3f0a/candidate_base_anchor_audit.json` | Candidate vs default engine |
| `docs/reports/market_sim/full_sim_82f3f0a/runtime_probe_original.txt` | Original probe result |
| `docs/reports/market_sim/full_sim_82f3f0a/runtime_probe_rerun.{py,txt}` | Probe rerun script and output |
