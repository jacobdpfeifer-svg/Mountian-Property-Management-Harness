# Full simulation and performance audit — 2026-10-13

**Run commit:** `27ffa40` (clean tracked tree; L1 run artifacts untracked under `docs/proving_ground/runs/`)  
**Artifact root:** `~/wp-price-runs/full_sim_20261013_27ffa40/`  
**Copied scoreboard artifacts:** [`docs/reports/market_sim/full_sim_27ffa40/`](market_sim/full_sim_27ffa40/)  
**Regression baseline:** [`FULL_SIMULATION_2026-10-12_RUN2.md`](FULL_SIMULATION_2026-10-12_RUN2.md) → `~/wp-price-runs/full_sim_20261012_82f3f0a_2/`  
**Protocol:** [`docs/prompts/FULL_SIMULATION_RUN.md`](../prompts/FULL_SIMULATION_RUN.md)

End-to-end replication after the guardrail-count fix (`a985b40`). No policy, calibration, or Guesty changes.

Evidence labels: **proven** = produced in this run; **inherited** = prior repo reports or boards; **unknown** = not exercised.

**Commits since `5aa99a7`:** `27ffa40` — adds the run prompt only; no engine, simulator, or policy file changes.

> **Read first — corrected 2026-10-14.** An audit found misread guardrail numbers, a ceiling
> measurement that rounding broke, and a 5-seed headline where a 25-seed one was available.
> All are corrected below and listed in [Corrections](#corrections-2026-10-14). The audit also
> found that the simulated market is priced far below the real one: the homes' real listed
> prices this winter average about $1,700–$2,500/night Dec–Mar, while every simulated price sits
> at $620–$1,035. Every dollar figure here is relative to that too-cheap market. Mechanisms
> (floor spiral, guardrail behaviour, ceiling-bound peak) hold; dollar levels, peak caps and
> base rates do not. See [`docs/plans/OVERHAUL_2026-10-14.md`](../plans/OVERHAUL_2026-10-14.md).

---

## Executive summary

| Layer | Result | Notes |
|--------|--------|--------|
| Proving-ground exam isolation | **PASS** | proven |
| Production preflight | **PASS** | proven |
| Quality gates (`scripts/quality_gates.py`) | **PASS** | 841 passed; **79.04%** coverage (≥70%) |
| Pytest `-m slow` | **PASS** | 3 tests, ~32s |
| Ops (`tests/ops`) | **PASS** | **445** passed |
| Proving Ground L1 | **FAIL** (economic) | hash `9be657c9…`; CLI exit **1** |
| Market sim 5-seed screen (`normal`) | **REGRESSION PASS** | 35/35 rows match RUN2; engine mean **−$46,680** vs flat (0/5) |
| Candidate `seasonal_base_anchor_full_shoulder` | **CONFIRMED (inherited 2026-10-09)** | 5-seed screen matches RUN2; vs flat **−$22,680** on seeds 6–30 (0/25), 5-seed screen −$20,336; candidate-vs-flat decomposition below |
| Guardrails seeds 1–30 (`normal`) | **NEW EVIDENCE** | score-only boards; revenue **reproduces** 2026-10-09; `sanity_floor` eliminated (0 on all 30 seeds), `clamped_increase` +53/seed (25/25); net −124 triggers/seed (6–30) |

### Top next steps

*(Rewritten 2026-10-14.)*

1. **Owner sign-off on the anchor mechanism only.** It removes the off-peak floor spiral
   (`sanity_floor` 0 on all 30 seeds) at the cost of more move-cap clamps (`clamped_increase`
   +53/seed). Do **not** sign off the base rates or peak caps as prices: they are well under
   half of what the homes really list at peak.
2. **Recalibrate the simulator before any peak experiment.** At peak the engine charges the
   ceiling on every night (the model's own price is at or above the ceiling on 100% of peak
   recommendations), so the "peak gap" is the owner caps ($1,035 Cloud 9) against a $900 flat,
   judged by an assumed shopper limit (multiplier × $700, the same for every home and season).
   An experiment in that market would tune the engine to the assumption.

---

## Test matrix

| Step | Command / tool | Exit | Duration (approx.) | Log |
|------|----------------|------|-------------------|-----|
| Env | venv + `manifest_env.txt` | 0 | — | `$RUN/manifest_env.txt` |
| Isolation | `scripts/check_proving_ground_isolation.py` | 0 | &lt;1s | `$RUN/gate_isolation.log` |
| Preflight | `scripts/production_preflight.py` | 0 | &lt;1s | `$RUN/gate_preflight.log` |
| Quality gates | `scripts/quality_gates.py` | 0 | ~76s | `$RUN/gate_quality.log` |
| Pytest slow | `pytest -m slow -q` | 0 | 32s | `$RUN/pytest_slow.log` |
| Ops | `pytest tests/ops -q` | 0 | 19s | `$RUN/ops_tests.log` |
| PG L1 | `proving-ground run --level 1 --seed 20260925` | **1**† | 10s | `$RUN/proving_ground_l1.log` |
| Market screen | `proving-ground market … --seeds 5 --grid --diagnostics --retain-dbs normal` | 0 | 143s | `$RUN/market_screen.log` |
| Audit / decompose (default) | `audit_market_sim.py`, `property_diagnostics.py`, `decompose_market_sim.py` | 0 | — | `$RUN/market_screen_benchmarks/*` |
| Candidate screen | `seasonal_base_anchor_full_shoulder` × 5 seeds, retain `normal` | 0 | 125s | `$RUN/screen_seasonal_base_anchor_full_shoulder/` |
| Candidate decomp | `decompose_market_sim.py` (engine vs flat, flat DBs linked) | 0 | — | `decomp_candidate_vs_flat.*` |
| Default 1–30 | `proving-ground market --seeds 30` (score-only) | 0 | 611s | `$RUN/default_1_30.log` |
| Candidate 1–30 | same with candidate engine policy | 0 | 628s | `$RUN/candidate_1_30.log` |
| Paired 6–30 | `paired_market_sim.py` | 0 | — | `$RUN/paired_normal_seeds_6_30.json` |

†CLI exit 1; audit verdict **FAIL** on economic gates (expected). Content hash unchanged at `9be657c9b5517d7b9e4137cfa774cfeb18e09cc40b5d2b3ab4da2aa6ebf3bf29`. L1 report shows Brier **n/a** for non-forecast policies and twin-baseline notes for `comp_median_follower` / `moat_off` ([`AUDIT_REPORT.md`](../proving_ground/runs/level_1_seed_20260925_9be657c9b551/AUDIT_REPORT.md)). *Note (2026-10-14):* this run's L1 report marked `humility_false_alarm_rate` PASS although it is not measured. The runner now reports it as NOT MEASURED (never a pass) and writes a blank Brier for baselines in `scoreboard.csv`; scores are unchanged but the L1 hash becomes `deb183d1…`. The preflight gained a rate-cap check after this run and now fails on the default policy's peak caps (see the overhaul plan).

**Not run:** 15×30 grid, `--incremental` runtime probe, Guesty live writes, sensitivity overlays.

---

## Regression check (proven)

Compared `$RUN/market_screen_benchmarks/scoreboard.csv` to `$PREV/market_screen_benchmarks/scoreboard.csv` on all **35** rows:

- `revenue`, `content_hash`, `guardrail_triggers`, `guardrail_by_action` — **all match**.

Candidate 5-seed engine rows match `$PREV/screen_seasonal_base_anchor_full_shoulder/scoreboard.csv` revenue to the cent.

**Conclusion:** `a985b40` did not change retained-run simulated revenue or hashes relative to RUN2 (`82f3f0a_2`).

---

## Simulated revenue — default engine (proven, 5-seed `normal`)

| Comparison | Mean Δ | 95% bootstrap | Seeds ≥ 0 |
|------------|--------|---------------|-----------|
| engine − flat | **−$46,680** | −$58,105 to −$35,372 | 0/5 |
| engine − comp_median | **−$38,864** | −$49,333 to −$28,396 | 0/5 |
| engine − tool | **+$6,383** | −$4,424 to +$18,925 | 2/5 |

Decomposition engine vs flat (**proven**, [`decomp_engine_vs_flat.md`](market_sim/full_sim_27ffa40/decomp_engine_vs_flat.md)): total Δ **−$46,680**; **only_flat_sold** **−$53,760** (all seasons); off-peak share of gap **inherited** ~61% from [`FULL_SIMULATION_2026-10-12.md`](FULL_SIMULATION_2026-10-12.md); peak_ski Δ **−$18,210**.

Retained DB disk (**proven**): default screen `dbs/` **1.1 GB**; candidate screen **403 MB** (flat DBs symlinked from default screen).

---

## Candidate overlay (proven screen + inherited confirmation)

**Status:** **CONFIRMED** on seeds 6–30 across six scenarios on 2026-10-09 ([`BASE_ANCHOR_2026-10-09.md`](market_sim/BASE_ANCHOR_2026-10-09.md)); this run does not re-litigate that.

5-seed screen vs promoted default (**proven**):

| Comparison | Mean Δ | 95% bootstrap | Seeds ≥ 0 |
|------------|--------|---------------|-----------|
| candidate − baseline engine | **+$26,343** | +$20,762 to +$33,472 | 5/5 |
| candidate − flat | **−$20,336** | −$36,745 to −$4,044 | 1/5 |
| candidate − tool | **+$32,727** | +$19,688 to +$50,000 | 5/5 |

### Candidate vs flat decomposition (**proven**, main new finding)

Source: [`decomp_candidate_vs_flat.md`](market_sim/full_sim_27ffa40/decomp_candidate_vs_flat.md) (5 seeds, candidate engine policy vs flat).

| Question | Answer (simulated) |
|----------|-------------------|
| Remaining gap to flat | **−$20,336** mean portfolio revenue |
| Dominant season | **peak_ski** **−$19,278** (shoulder **+$1,216**; early_winter **−$2,274**) |
| Dominant property | **Cloud 9** **−$18,954** (Overlook **+$2,162**; Summit **−$3,544**) |
| Price vs volume | **Volume:** **only_flat_sold** **−$59,020** vs **only_engine_sold** **+$29,826**; **both_sold** **+$8,858** (candidate higher ADR on overlapping nights) |
| Peak occupancy | engine **0.524** vs flat **0.615** on peak_ski |
| Peak pricing / ceiling | Candidate peak ADR **942** vs flat **900**. Peak recs at the ceiling (within 1%): **87.1%**; model price ≥ ceiling: **100%** (corrected 2026-10-14; the original "17.7%" used a $0.50 test that price rounding defeats). Cloud 9 probe: final ~$1,028, ceiling $1,035 ([`candidate_property.md`](market_sim/full_sim_27ffa40/candidate_property.md)) |

After the anchor, the remaining gap is **concentrated at peak**, not in the shoulder floor-spiral (shoulder is net positive vs flat). At peak the price is the ceiling, so the peak gap is the ceiling level: the owner caps (Cloud 9 $1,035, Overlook $916, Summit ~$912 from its base) against a single $900 flat. That matches the property split (Overlook +$2.2k, Summit −$3.5k, Cloud 9 −$19.0k). The default engine's peak gap (−$18,210) is about the same, so the anchor did not change peak. In this simulator Cloud 9 cannot earn a premium: its quality is set lower than the twins' (0.95, "assumed"), it is modeled as sleeping 15 (it sleeps 18), and every shopper's limit is the same multiplier × $700 for every home and season. This is a calibration-bound result, not evidence about Cloud 9's real rate.

**Over 25 held-out seeds** (inherited flat board `~/wp-price-runs/market_sim/baseline_79dae5d`, whose seeds 1–5 match this run's flat rows hash for hash): candidate − flat **−$22,680** (95% −$28,311 to −$17,177), 0/25 seeds ahead; default − flat −$45,975 (−$51,211 to −$41,255), 0/25. Files: [`candidate_vs_flat_seeds_6_30.json`](market_sim/full_sim_27ffa40/candidate_vs_flat_seeds_6_30.json), [`default_vs_flat_seeds_6_30.json`](market_sim/full_sim_27ffa40/default_vs_flat_seeds_6_30.json).

---

## Guardrail evidence (proven, score-only seeds 1–30)

**Revenue (reproduction, not new confirmation):** every engine row matches `~/wp-price-runs/market_sim/post_promote_79dae5d/default_normal_1_30/scoreboard.csv` and `~/wp-price-runs/market_sim/confirm_base_anchor_79dae5d/candidate_normal_1_30/scoreboard.csv`. Content hashes differ from those boards by design: they were written before `a985b40`, with fake zero guardrail counts inside the hashed scores.

**The `a985b40` fix works:** on seeds 1–5 the score-only boards report the same content hashes and guardrail counts as the retained screens. Before the fix, score-only hashes depended on retention.

**Paired candidate − default, seeds 6–30** ([`paired_normal_seeds_6_30.json`](market_sim/full_sim_27ffa40/paired_normal_seeds_6_30.json)):

| Metric | Mean Δ | 95% bootstrap | Seeds ≥ 0 |
|--------|--------|---------------|-----------|
| Simulated revenue | **+$23,296** | +$19,551 to +$27,057 | 25/25 |
| `guardrail_triggers` (lower is better) | **−124** | −149 to −97 | candidate higher on 2/25 |

(`+$23,295.56` rounds to inherited **+$23,296**.)

**Sanity:** `guardrail_triggers` **non-zero on all 30 seeds** for both arms. Seeds **1–5** triggers match the retained screens from steps 2–3.

**Seeds 1–6 mean triggers:** default **2,243** vs candidate **2,119** (**proven**). *Corrected 2026-10-14:* the inherited "2,596 → 2,243" in [`FULL_SIMULATION_2026-10-12.md`](FULL_SIMULATION_2026-10-12.md) compared the old engine with the Cloud 9/Overlook **cap** arm, which is now the default. This run's default 2,243 reproduces that number exactly; it is not evidence about the base anchor.

### By action type (`guardrail_by_action`, proven; rewritten 2026-10-14)

Per-seed paired deltas, candidate − default, seeds 6–30 ([`paired_normal_seeds_6_30.json`](market_sim/full_sim_27ffa40/paired_normal_seeds_6_30.json)):

| Action | Mean Δ per seed | 95% bootstrap | Candidate higher / lower | Per 1,000 recs (default → candidate) |
|--------|---:|---|---|---|
| `sanity_floor` | **−183** | −206 to −163 | 0 / 25 | 5.2 → **0.0** (zero on all 30 seeds) |
| `clamped_increase` | **+53** | +49 to +56 | **25 / 0** | 0.6 → 2.0 |
| `clamped_decrease` | −3 | −5 to −1 | 0 / 17 | 0.1 → 0.0 |
| `peak_blackout` | +9 | −3 to +23 | 6 / 1 | 59.5 → 58.2 |
| `none` (no guardrail fired; not a trigger) | +1,077 | +898 to +1,250 | 25 / 0 | — |

How to read it:

- `sanity_floor` disappears: the anchor stops off-peak prices from spiralling to the floor.
- `clamped_increase` rises on every seed: the anchor wants to lift off-peak prices faster than
  the 12%/$250 daily move cap allows. This is the one guardrail change that bears on sign-off.
- `peak_blackout` fires on high-demand dates and is the same in both arms on 22 of 30 seeds.
  Its small rise comes from peak nights that stay unsold longer and so are re-priced more often.
  *(The original report said it "rises on many seeds"; that was wrong.)*
- `none` counts recommendations where no guardrail fired. It rises because the candidate leaves
  more nights unsold, so more open nights are re-priced each day. *(The original report called
  it an "unlabeled bucket"; that was wrong.)*

Trigger rate overall: 6.5% of recommendations (default) vs 6.0% (candidate).

## Corrections (2026-10-14)

| # | Original statement | Correction |
|---|---|---|
| 1 | `""` = "more unlabeled bucket counts" | Rows where no guardrail fired; rises with unsold nights |
| 2 | `peak_blackout` rises on many seeds | Same in both arms on 22/30 seeds |
| 3 | `sanity_floor` −5,423 "fewer" | Zero on all 30 seeds |
| 4 | `clamped_increase` "more" | +53/seed on 25/25 seeds; the sign-off-relevant change |
| 5 | Seeds 1–6 "directionally consistent with 2,596 → 2,243" | That pair was the cap arm; 2,243 is an exact reproduction |
| 6 | Peak recs 17.7% at ceiling | 87.1% within 1%; model ≥ ceiling on 100% |
| 7 | Candidate − flat −$20,336 (5 seeds) | −$22,680 on seeds 6–30, 0/25 |
| 8 | `file:///` links | Plain paths |

Tool fixes behind these (2026-10-14): `scripts/decompose_market_sim.py` (relative ceiling
tolerance, model ≥ ceiling share, `--right-dir` with both sides reconciled),
`scripts/paired_market_sim.py` (per-action deltas, `none` named, per-1,000 rates, policy and
scenario selectors; it now refuses a board that mixes scenarios, which would have let one
scenario's row overwrite another's — no published number used such a board).

## Self-check (against [`FULL_SIMULATION_2026-10-12.md` § Second audit](FULL_SIMULATION_2026-10-12.md#second-audit-corrections-and-fixes))

- Did **not** call the base-anchor candidate unconfirmed; cited 2026-10-09 confirmation.
- Did **not** read the **default-engine** decomposition as proof of a peak-only problem; separated default (off-peak / `only_flat_sold` across seasons) from **candidate** decomposition (peak-led remainder).
- Did **not** treat reproduced 1–30 revenue as new confirmation; labeled guardrails as new evidence.
- Did **not** report throughput or incremental probe figures not measured this run.
- Did **not** recommend re-confirming seeds 6–30 for revenue.
- Copied scoreboards, audits, property/decomp markdown, paired JSON into `docs/reports/market_sim/full_sim_27ffa40/` (no `.db` files).

---

## File index

| Path | Description |
|------|-------------|
| `~/wp-price-runs/full_sim_20261013_27ffa40/` | Full run tree (logs, DBs, scoreboards) |
| `docs/reports/market_sim/full_sim_27ffa40/candidate_vs_flat_seeds_6_30.json` | Candidate vs flat, 25 paired seeds (added 2026-10-14) |
| `docs/reports/market_sim/full_sim_27ffa40/default_vs_flat_seeds_6_30.json` | Default vs flat, 25 paired seeds (added 2026-10-14) |
| `docs/reports/market_sim/full_sim_27ffa40/scoreboard.csv` | 5-seed default screen |
| `docs/reports/market_sim/full_sim_27ffa40/candidate_scoreboard.csv` | 5-seed candidate |
| `docs/reports/market_sim/full_sim_27ffa40/decomp_engine_vs_flat.md` | Default engine vs flat |
| `docs/reports/market_sim/full_sim_27ffa40/decomp_candidate_vs_flat.md` | **New:** candidate vs flat |
| `docs/reports/market_sim/full_sim_27ffa40/paired_normal_seeds_6_30.json` | Paired revenue + guardrail Δ (6–30) |
| `docs/reports/market_sim/full_sim_27ffa40/default_normal_1_30_scoreboard.csv` | Score-only default |
| `docs/reports/market_sim/full_sim_27ffa40/candidate_normal_1_30_scoreboard.csv` | Score-only candidate |
