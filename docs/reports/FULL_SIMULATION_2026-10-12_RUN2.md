# Full simulation and performance audit — 2026-10-12 (run 2)

**Run commit:** `82f3f0a` (tracked tree clean; untracked prior run reports in working tree)  
**Artifact root:** `~/wp-price-runs/full_sim_20261012_82f3f0a_2/`  
**Copied scoreboard artifacts:** [`docs/reports/market_sim/full_sim_82f3f0a_2/`](market_sim/full_sim_82f3f0a_2/)  
**Prior same-day run:** [`FULL_SIMULATION_2026-10-12.md`](FULL_SIMULATION_2026-10-12.md) → `~/wp-price-runs/full_sim_20261012_82f3f0a/`

Replication of the end-to-end protocol from the Oct-8 and Oct-12 audits. No policy, calibration, or Guesty changes.

Evidence labels: **proven** = produced in this run; **inherited** = prior repo reports; **unknown** = not exercised.

---

## Executive summary

| Layer | Result | Notes |
|--------|--------|--------|
| Proving-ground exam isolation | **PASS** | proven |
| Production preflight | **PASS** | proven |
| Quality gates (`scripts/quality_gates.py`) | **PASS** | 840 tests; **79.0%** coverage (≥70%) |
| Pytest `-m slow` | **PASS** | 3 tests, ~32s |
| Proving Ground L1 | **FAIL** | safety OK; regret / vs baselines / Brier / tail loss |
| Market sim 5-seed screen (`normal`) | **COMPLETE** | matches run 1 scores; engine mean **−$46.7k** vs flat (0/5) |
| Candidate `seasonal_base_anchor_full_shoulder` | **CONFIRMED (2026-10-09)** | this screen: **+$26.3k** vs promoted default (5/5), **−$20.3k** vs flat (1/5 nonnegative); seeds 6–30 already run on six scenarios (four held out): `normal` +$23.3k 25/25, `pandemic_collapse` CI crosses zero — see [`BASE_ANCHOR_2026-10-09.md`](market_sim/BASE_ANCHOR_2026-10-09.md) |
| Runtime: `--incremental` | **MODEST** | ~2% faster this probe; revenue matches; content hash differs |
| Ops integration smoke | **PASS** | `tests/ops/test_integration_matrix.py` (3 tests) |

Revenue and audit numbers match the earlier Oct-12 run on the same commit (deterministic sim). Wall clock varied (market screen ~157s vs ~137s; runtime probe ~1.02× vs ~1.10×).

### Top fixes

1. **Revenue — close remaining flat gap (~$20k on 5 seeds)** — peak volume / `only_flat_sold` (−$53.8k decomposition).
2. **Revenue — owner decision on the base-anchor candidate.** Seeds 6–30 were already confirmed on 2026-10-09 (`BASE_ANCHOR_2026-10-09.md`); do not rerun them. The open item is owner sign-off on the guard and base rates (see run 1, `FULL_SIMULATION_2026-10-12.md`).
3. **Product — L1 economic gates** vs market-sim evidence.
4. **Runtime — engine-bound full season (~109–117 s/job)**; incremental is not a board-scale lever.
5. **Disk — ~1.1 GB retained DBs per screen** at ~95% disk use.

---

## Test matrix

| Step | Command / tool | Exit | Duration (approx.) | Log |
|------|----------------|------|-------------------|-----|
| Env | venv + `manifest_env.txt` | 0 | — | `$RUN/manifest_env.txt` |
| Isolation | `scripts/check_proving_ground_isolation.py` | 0 | &lt;1s | `$RUN/gate_isolation.log` |
| Preflight | `scripts/production_preflight.py` | 0 | &lt;1s | `$RUN/gate_preflight.log` |
| Quality gates | `scripts/quality_gates.py` | 0 | ~71s | `$RUN/gate_quality.log` |
| Pytest slow | `pytest -m slow --ignore-glob='* 2.py'` | 0 | 32s | `$RUN/pytest_slow.log` |
| PG L1 | `proving-ground run --level 1 --seed 20260925` | 0† | 9s | `$RUN/proving_ground_l1.log` |
| Market screen | `proving-ground market --scenario normal --seeds 5 --workers 7 --grid --diagnostics --retain-dbs normal` | 0 | 158s | `$RUN/market_screen.log` |
| Audit / decompose | `audit_market_sim.py`, `property_diagnostics.py`, `decompose_market_sim.py` | 0 | — | `$RUN/market_screen_benchmarks/*` |
| Candidate | `seasonal_base_anchor_full_shoulder` × 5 seeds | 0 | 130s | `$RUN/screen_seasonal_base_anchor_full_shoulder/` |
| Runtime probe | `run_market_job` full vs incremental (`/tmp`) | 0 | 217s | `$RUN/runtime_probe/timing.txt` |
| Ops smoke | `pytest tests/ops/test_integration_matrix.py` | 0 | &lt;1s | `$RUN/ops_smoke.log` |

†CLI exit 0; audit verdict **FAIL** (economic gates).

**Not run:** 15×30 grid, Guesty live writes, sensitivity overlays, `run_testruns.py` agents, production replay.

---

## Revenue performance (proven, 5-seed `normal`, promoted `default.yaml`)

### Portfolio (audit)

| Comparison | Mean Δ | 95% bootstrap | Seeds ≥ 0 |
|------------|--------|---------------|-----------|
| engine − flat | **−$46,680** | −$58,105 to −$35,372 | 0/5 |
| engine − comp_median | **−$38,864** | −$49,333 to −$28,396 | 0/5 |
| engine − tool | **+$6,383** | −$4,424 to +$18,925 | 2/5 |

### Decomposition (engine vs flat)

- Total Δ: **−$46,680** / season (mean).
- **Only flat sold:** −$53,760.
- **Only engine sold:** +$32,379.
- **Peak season:** Δ **−$18,210**; engine occ **0.528**, flat **0.615**.
- **Cloud 9:** Δ **−$22,564**; occ **0.517** vs **0.614**.

### Candidate overlay (`seasonal_base_anchor_full_shoulder.yaml`)

vs screen reference (promoted default engine):

| Comparison | Mean Δ | 95% bootstrap | Seeds ≥ 0 |
|------------|--------|---------------|-----------|
| candidate − baseline engine | **+$26,343** | +$20,762 to +$33,472 | 5/5 |
| candidate − flat | **−$20,336** | −$36,745 to −$4,044 | 1/5 |
| candidate − tool | **+$32,727** | +$19,688 to +$49,998 | 5/5 |

---

## Runtime performance (proven)

| Metric | Run 2 | Run 1 (same commit) |
|--------|-------|---------------------|
| Screen wall clock | 157.3 s | 136.8 s |
| Jobs | 35 | 35 |
| Retained DBs | ~1.1 GB | ~1.1 GB |
| Full-season job (seed 1, `/tmp`) | **108.9 s** full / **106.7 s** inc (**1.02×**) | 117.1 / 106.0 (**1.10×**) |
| Revenue / hash | match / **hash mismatch** | match / hash mismatch |

Probe settings: `persist_recommendations=False`, `trace_choices=False`, `normal`, seed 1, full season.

---

## File index

| Path | Description |
|------|-------------|
| `~/wp-price-runs/full_sim_20261012_82f3f0a_2/` | Full run tree |
| `docs/reports/market_sim/full_sim_82f3f0a_2/scoreboard.csv` | 5-seed screen |
| `docs/reports/market_sim/full_sim_82f3f0a_2/audit.json` | Audit gates + deltas |
| `docs/reports/market_sim/full_sim_82f3f0a_2/property.md` | Property diagnosis |
| `docs/reports/market_sim/full_sim_82f3f0a_2/decomp_normal_vs_flat.md` | Engine vs flat decomposition |
| `docs/reports/market_sim/full_sim_82f3f0a_2/candidate_base_anchor_audit.json` | Base-anchor vs default |
