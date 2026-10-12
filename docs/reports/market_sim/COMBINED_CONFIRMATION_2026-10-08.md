# Combined candidate confirmation — 2026-10-08

**Candidate:** `config/policies/candidates/cloud9_overlook_lower_peak_ceiling.yaml`  
**Commit:** `79dae5d` (dirty working tree; see run manifests)  
**Artifact root:** `~/wp-price-runs/market_sim/combined_confirmation_79dae5d/`  
**Grading window:** paired seeds **6–30** (25 seeds); seeds 1–5 continuity only.

Simulated shopper revenue only. Not realized revenue. `default.yaml` and `calibration.yaml` were not edited. Guesty was not touched.

---

## Decision

**Promote for owner review** — the combined candidate beats the default engine on every graded scenario (mean paired revenue ≥ 0), including held-out worlds and `price_war`. Cloud 9 and Overlook show higher peak occupancy in the retained diagnostic sample without binding lower peak list prices into a revenue collapse on those homes.

Beating the default engine **does not** beat the flat benchmark: on seeds 6–30, combined engine revenue is still roughly **−$46k** vs flat on `normal` (same shopper world as `baseline_79dae5d`). Do not copy the candidate into `default.yaml` without owner approval.

---

## Command matrix

| Step | Command pattern | Jobs | Output dir |
|------|-----------------|-----:|------------|
| 1–12 | `proving-ground market --scenario <S> --seeds 30 --workers 7 --policy engine` (+ `--engine-policy` for combined) | 30 each | `default_<S>_1_30`, `combined_<S>_1_30` |
| Scenarios | `normal`, `holiday_shift`, `den_capacity_cut`, `regime_change`, `pandemic_collapse`, `price_war` | 360 total | score-only |
| Diagnostics | `--seeds 6 --workers 1 --retain-dbs normal` (default + combined) | 6 each | `*_normal_diagnostic` |
| Audit | `scripts/audit_market_sim.py … --engine-only --seeds-from 6` | — | `combined_<S>_audit_seeds_6_30.json` |
| Paired metrics | `scripts/paired_market_sim.py … --seeds-from 6` | — | `combined_<S>_paired_seeds_6_30.json` |

Orchestration script: `~/wp-price-runs/market_sim/combined_confirmation_79dae5d/run_matrix.sh`.

---

## Seeds 6–30: combined minus default engine (revenue)

| Scenario | Held out | Mean Δ | 95% CI | Wins / 25 |
|----------|----------|-------:|--------|----------:|
| normal | | +$48,454 | +$43,318 to +$53,780 | 25/25 |
| holiday_shift | yes | +$49,026 | +$42,680 to +$55,215 | 25/25 |
| den_capacity_cut | yes | +$47,553 | +$43,534 to +$51,772 | 25/25 |
| regime_change | yes | +$44,381 | +$38,727 to +$50,023 | 25/25 |
| pandemic_collapse | yes | +$8,331 | +$5,484 to +$11,581 | 21/25 |
| price_war | | +$46,779 | +$42,351 to +$52,011 | 25/25 |

Portfolio-level paired deltas (same seeds): **RevPAN** +$89.7, **occupancy** +0.103, **occupancy_peak** +0.174 on `normal`; guardrail trigger count unchanged vs default.

Full paired JSON: `~/wp-price-runs/market_sim/combined_confirmation_79dae5d/combined_*_paired_seeds_6_30.json`.

---

## Property peak evidence (diagnostic retain, seeds 1–6, `normal`)

Aggregated `property.md` under `default_normal_diagnostic` vs `combined_normal_diagnostic`:

| Property | Peak unsold share (default → combined) | Peak occupancy (approx.) | Peak mean engine price |
|----------|----------------------------------------|--------------------------|-------------------------|
| Cloud 9 | 90.7% → 60.0% | 9% → 40% | $1,121 → $1,026 |
| Overlook Ridge | 61.7% → 41.3% | 38% → 59% | $1,045 → $911 |

More peak nights book at modestly lower peak list levels; booked peak volume rises sharply on both target homes.

---

## Disk usage

| Path | Size |
|------|-----:|
| Score-only confirmation dirs (12 × 30 jobs) | ~1 MB total |
| `default_normal_diagnostic` + `combined_normal_diagnostic` | ~966 MB |
| **Total** `combined_confirmation_79dae5d` | ~967 MB |

---

## Profiling (before batching)

One full-season job: `normal`, seed 6, default engine, `persist_recommendations=False`, `trace_choices=False`.

- Wall time: **~166 s**
- Dominant cumulative time: `generate_recommendations` → `recommend_night` (~156 s), **SQLite `execute`** (~73 s), `estimate` / `pacing_ratio` (~48 s), `compute_ceiling` (~38 s), repeated YAML/config loads and `comp_evidence` / SQI reads.

Profile: `~/wp-price-runs/market_sim/combined_confirmation_79dae5d/profiles/default_seed6.prof` and `top25.txt`.

**Batching:** No engine change shipped in this pass. Next step per runbook: one isolated cache/batch with pytest, compile, 60-day hash equivalence, then re-profile.

---

## Verification

- Confirmation matrix: 12/12 scoreboards complete (30 engine rows each).
- Audits: `--engine-only` completeness true for all six scenarios.
- New helper: `scripts/paired_market_sim.py` (paired RevPAN/occupancy/peak/guardrails).
