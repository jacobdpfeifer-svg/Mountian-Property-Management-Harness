# Full simulation and performance audit — 2026-10-08

**Commit:** `79dae5d` (dirty working tree; see run manifest)  
**Artifact root:** `~/wp-price-runs/full_sim_20261008_79dae5d/`  
**Copied scoreboard artifacts:** [`docs/reports/market_sim/full_sim_79dae5d/`](market_sim/full_sim_79dae5d/)

Evidence labels: **proven** = produced in this run; **inherited** = prior repo reports; **unknown** = not exercised.

---

## Executive summary

| Layer | Result | Notes |
|--------|--------|--------|
| Proving-ground exam isolation | **PASS** | proven |
| Production preflight | **PASS** | proven |
| Pytest (default, 386 tests) | **PASS** | proven; 2 slow tests deselected |
| Pytest coverage gate (70%) | **FAIL** | 59.3% total; ops + iCloud `* 2.py` duplicates drag coverage |
| Pytest `-m slow` | **PASS** | 2 tests, ~19s |
| Proving Ground L1 | **FAIL** | regret vs oracle, vs baselines, Brier, tail loss |
| Market sim 5-seed screen (`normal`) | **COMPLETE** | audit `gates.complete`; engine still loses to flat |
| Candidate `cloud9_lower_peak_ceiling` | **SUGGESTIVE** | +~$15k vs default engine (5 seeds); still −~$71k vs flat |
| Runtime: `--incremental` | **NO WIN** | ~3% faster full season; not a lever for 1,800-job boards |
| Ops integration tests | **GAP** | no `tests/ops/`; `ops profiles` not smoke-tested (CLI `--db` ordering) |

### Top five fixes (impact-ranked)

1. **Revenue — peak volume and property premia (Cloud 9 / Overlook)**  
   Decomposition shows **−$86k** mean engine−flat on `normal` (5 seeds), driven by **nights only flat sold (−$104k)** and peak occupancy (engine 0.38 vs flat 0.62). Cloud 9 alone **−$56k**. Candidate `cloud9_lower_peak_ceiling.yaml` lifts engine revenue **+$15.2k** vs default engine (4/5 seeds nonnegative) but does not beat flat. **Next:** confirm seeds 6–30, pair with `overlook_lower_peak_ceiling`, inspect peak `peak_blackout` and ceiling binding (`property.md`).

2. **Revenue — diagnostic `premium_cap` policy beats engine in sim**  
   On this screen, `premium_cap` mean revenue ≈ **$267k** vs engine **$181k** (same band as flat/comp_median). Suggests engine premia/ceiling stack is misaligned with shopper WTP, not that “more math” fixes volume. **Next:** trace why `premium_cap` wins without shipping it as production policy (benchmark only).

3. **Hygiene — remove iCloud `* 2.py` duplicates (46 files)**  
   Inflates coverage denominator, risks duplicate test collection, wastes disk (~1.1 GB retained DBs in one screen). **Next:** delete duplicates or move repo off iCloud; add `omit` patterns in coverage for `* 2.py` until cleaned.

4. **Runtime — wall clock is engine-bound, not pool-bound**  
   35 jobs / 7 workers in **166s** (~12.7 jobs/min). Full-season engine job **~122s**. Incremental repricing **~118s** (1.03×). **Next:** profile `generate_recommendations` / ceiling / feature builds; consider `stay_dates` batching and DB pragmas on sim paths; do **not** expect `--incremental` to cut a 3h baseline grid to &lt;1.5h.

5. **Correctness / product — Proving Ground L1 still fails hard gates**  
   Engine revenue **$44k** vs flat **$68k** on W1_calm (single seed run). Safety gates pass; economic gates fail. **Next:** align Phase 0 ladder expectations with market-sim diagnosis or tighten engine before treating L1 pass as release criteria.

---

## Test matrix

| Step | Command / tool | Exit | Duration (approx.) | Log |
|------|----------------|------|-------------------|-----|
| Env | venv + `manifest_env.txt` | 0 | — | `$RUN/manifest_env.txt` |
| Isolation | `scripts/check_proving_ground_isolation.py` | 0 | &lt;1s | `$RUN/gate_isolation.log` |
| Preflight | `scripts/production_preflight.py` | 0 | &lt;1s | `$RUN/gate_preflight.log` |
| Quality gates | `scripts/quality_gates.py` | 1* | ~40s | `$RUN/gate_quality.log` |
| Pytest slow | `pytest -m slow --ignore-glob='* 2.py'` | 0 | 19s | `$RUN/pytest_slow.log` |
| PG L1 | `proving-ground run --level 1` | 1 | 11s | `$RUN/proving_ground_l1.log` |
| Market screen | `proving-ground market --scenario normal --seeds 5 --workers 7 --grid --diagnostics --retain-dbs normal` | 0 | 166s | `$RUN/market_screen.log` |
| Audit | `scripts/audit_market_sim.py` | 0 | — | `$RUN/market_screen_benchmarks/audit.json` |
| Property diag | `scripts/property_diagnostics.py` | 0 | — | `$RUN/.../property.md` |
| Decompose | `scripts/decompose_market_sim.py --left engine --right flat` | 0 | — | `$RUN/.../decomp_normal_vs_flat.md` |
| Candidate | `cloud9_lower_peak_ceiling` engine × 5 seeds | 0† | ~135s (prior invocation) | `$RUN/screen_cloud9_lower_peak_ceiling/` |
| Runtime probe | `run_market_job` full vs incremental | 0 | 122s + 118s | `$RUN/runtime_probe/timing.txt` |

\*Coverage `fail-under=70` reported **59.3%**; tests themselves passed.  
†Candidate output dir already contained 5 jobs from an earlier partial run in the same audit session; audit re-run succeeded.

**L2:** Vintage fixtures exist under `data/proving_ground/vintages/` (inherited layout). L2 run was **not** executed in this audit (out of plan scope for time); not blocked on missing files.

---

## Revenue performance (proven, 5-seed `normal`)

### Portfolio (audit)

| Comparison | Mean Δ (engine − other) | 95% bootstrap | Seeds ≥ 0 |
|------------|-------------------------|---------------|-----------|
| engine − flat | **−$85,926** | −$94,252 to −$78,748 | 0/5 |
| engine − comp_median | **−$78,110** | −$83,901 to −$72,320 | 0/5 |
| engine − tool | **−$32,863** | −$41,850 to −$22,523 | 0/5 |

Aligns with **inherited** [`BASELINE_DIAGNOSIS.md`](market_sim/BASELINE_DIAGNOSIS.md) direction (engine loses to flat on volume, especially peak).

### Decomposition (engine vs flat, proven)

- Total Δ: **−$85,926** / season (mean over 5 seeds).
- **Only flat sold:** −$103,620 (dominant).
- **Only engine sold:** +$41,707.
- **Both sold, price effect:** −$24,013.
- **Peak season:** Δ **−$57,456**; engine occ **0.38**, flat **0.62**; engine ADR **$976** vs flat **$900** (price up, volume down).
- **Cloud 9:** Δ **−$55,813**; occ **0.33** vs **0.61**.

### Property-level (proven, `property.md`)

- Cloud 9 peak: **~90%** of peak nights unsold; engine peak price **~$1,120** vs flat **$900**; loss reasons dominated by `above_wtp` and `unavailable`.
- `premium_cap` and `property_flat` policies in the same screen outperform default engine on total revenue (see scoreboard CSV in artifact dir).

### Candidate overlay (proven vs reference)

`config/policies/candidates/cloud9_lower_peak_ceiling.yaml`:

- **engine − baseline_engine:** mean **+$15,220** (95% CI **+$6,405 to +$24,036**); 4/5 seeds nonnegative.
- **engine − flat:** still **−$70,706** mean.
- **engine − tool:** mean **−$17,643**; 1/5 seeds beat tool.

Cloud 9 peak engine price in probe drops **~$1,120 → ~$1,029**; peak unsold share improves slightly but remains **~65%** unsold.

---

## Runtime performance (proven)

| Metric | Value |
|--------|--------|
| Screen wall clock | 165.7 s (manifest) |
| Jobs | 35 (7 policies × 5 seeds) |
| Throughput | ~12.7 jobs/min |
| Retained DBs (`--retain-dbs normal`, all policies) | **~1.1 GB** under `$RUN/market_screen_benchmarks/dbs` |
| Per-policy DB (typical) | ~23–24 MB (non-engine); engine larger when retained |
| Full-season engine job (seed 1) | **121.8 s** full / **118.1 s** incremental (**1.03×**) |
| Truncated 60-day job | **5.2 s** both paths; content hashes differ on truncated path (incremental skip semantics) |

**Disk:** One probe hit `sqlite3.OperationalError: disk I/O error` writing under `~/wp-price-runs` during a stressed moment (~90% disk full). Full-season timing succeeded on `/tmp`.

**Workers:** 7 workers achieved ~500% CPU in the 35-job screen; parallel efficiency is reasonable; dominant cost remains per-engine-job CPU/SQLite, not orchestration.

---

## Correctness and hygiene backlog

| Item | Severity | Evidence |
|------|----------|----------|
| iCloud `* 2.py` duplicates | P1 | 46 files; coverage includes dead `* 2.py` modules at 0% |
| Coverage gate 70% | P2 | 59.3% with untested `src/ops/*`, `src/compliance/*` |
| `quality_gates.py` | Fixed | Added `--ignore-glob='* 2.py'` for pytest |
| `decompose_market_sim.py` CLI | Doc drift | Plan used `--policy-a`; actual flags are `--left` / `--right` |
| Proving Ground L1 economic gates | P1 | `$RUN/proving_ground/l1/.../AUDIT_REPORT.md` |
| Ops layer untested in CI | P2 | No `tests/ops/` in this checkout |
| Git dirty + untracked ops/compliance | P2 | Market sim provenance records `git_dirty: true` |

---

## Recommended code and ops changes

| # | Change | Hypothesis | Risk |
|---|--------|------------|------|
| 1 | Promote candidate only after seeds 6–30 + held-out scenarios | Cloud 9 ceiling tweak is real but insufficient alone | Overfitting 5 seeds |
| 2 | Investigate `peak_blackout` + ceiling caps on peak volume | Decomp: peak volume gap; guardrail table shows blackout on booked nights | Revenue vs owner peak intent |
| 3 | Study `premium_cap` as upper-bound benchmark in compose/ceiling | Explains gap to “simple” policies | Must not ship as default |
| 4 | Delete or gitignore `* 2.py` | Coverage, CI honesty, less confusion | Accidental delete if one file was canonical |
| 5 | Add `tests/ops/` or exclude ops from fail-under until tested | Coverage gate meaningful | Hides ops debt if only omitted |
| 6 | Default large sim runs: retain engine DBs only | Cuts disk 1.1 GB → ~400 MB for same screen | Less decompose surface |
| 7 | Profile `generate_recommendations` in market loop | Incremental not worth complexity for speed | Incremental still needed for correctness tests |

---

## What was not run

- Full 15×30×grid (~1,800 jobs, ~3 h) — **inherited** baseline only.
- Guesty sync/write, live scrape, `run_testruns.py` agents.
- Sensitivity overlays (`config/market_sim/sensitivity/*`).
- Replay/shadow on production DB.
- Policy edits to `config/policies/default.yaml` or `calibration.yaml` (per run rules).

---

## File index

| Path | Description |
|------|-------------|
| `~/wp-price-runs/full_sim_20261008_79dae5d/` | Full run tree |
| `docs/reports/market_sim/full_sim_79dae5d/scoreboard.csv` | 5-seed screen |
| `docs/reports/market_sim/full_sim_79dae5d/audit.json` | Audit gates + deltas |
| `docs/reports/market_sim/full_sim_79dae5d/property.md` | Property diagnosis |
| `docs/reports/market_sim/full_sim_79dae5d/decomp_normal_vs_flat.md` | Engine vs flat decomposition |
| `docs/reports/market_sim/full_sim_79dae5d/candidate_cloud9_audit.json` | Candidate vs benchmark |
