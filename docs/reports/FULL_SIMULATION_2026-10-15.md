# Full simulation and performance audit — 2026-10-15 (Phase 6)

**Run commit:** `d291c60` (tracked tree clean at start; untracked `docs/prompts/FINAL_DELIVERY/` appeared during long boards)  
**Artifact root:** `~/wp-price-runs/full_sim_20261015_d291c60/`  
**Copied scoreboard artifacts:** [`docs/reports/market_sim/full_sim_d291c60/`](market_sim/full_sim_d291c60/)  
**Protocol:** Phase 6 in [`docs/plans/OVERHAUL_2026-10-14.md`](../plans/OVERHAUL_2026-10-14.md) (supersedes v1-only [`FULL_SIMULATION_RUN.md`](../prompts/FULL_SIMULATION_RUN.md))  
**Calibration:** v2 (`proving_ground_exam/market/calibration_v2.yaml`)

End-to-end gates, v1 golden regression, v2 calibration validation, v2 market evidence (owner net headline), sensitivity overlays, and production-faithful approval mode. No policy, calibration, or Guesty changes during the run.

Evidence labels: **proven** = produced in this run; **inherited** = prior reports; **unknown** = not exercised.

Simulated owner net and revenue are evidence about the synthetic shopper world calibrated to v2. They are not realized revenue.

**Commits since `27ffa40` (2026-10-13 report):** `a2a4183` (public-repo hygiene), `6fdd3c9` (report/tool fixes), `261ab20` (calibration v2 + owner net), `c37b2fb` (pace candidate, deploy scripts), `d291c60` (Cloud 9 comp test). Engine/simulator/policy paths changed in `261ab20`–`c37b2fb`; v1 golden boards still match (**proven**).

---

## Executive summary

| Layer | Result | Notes |
|--------|--------|--------|
| Proving-ground exam isolation | **PASS** | proven |
| Production preflight | **PASS** | proven; rate-cap check 4 pairs vs `data/exports/rate_card.yaml`; deploy SHA unknown (warning only) |
| Quality gates | **PASS** | 875 passed; **78.90%** coverage (≥70%) |
| Pytest `-m slow` | **PASS** | 4 tests |
| Ops (`tests/ops`) | **PASS** | 811 passed |
| Proving Ground L1 | **FAIL** (economic) | hash `deb183d14d1a…`; CLI exit **1** |
| v1 golden regression | **PASS** | default + base-anchor candidate boards match golden CSVs |
| v2 calibration validation (10 seeds) | **PASS** | public bands + booked ADR vs export |
| v2 5-seed screen (`normal`) | **COMPLETE** | see owner-net table below |
| v2 30-seed confirmation (4 scenarios) | **COMPLETE** | paired seeds 6–30 on owner net |
| Pace candidate `pace_learned_owner_net` | **SCREEN + CONFIRMATION** | `--allow-models` (learned elasticity + pace); beats default engine; still trails `current_practice` on `normal` (CI crosses zero) |
| Sensitivity overlays (v2, 10 seeds × 10) | **COMPLETE** | under `v2_sensitivity/` |
| Production-faithful (`approval-rate 0.7`, 10 seeds) | **COMPLETE** | engine owner net +$7.8k vs recommendation-quality screen on overlapping seeds (screen uses seeds 1–5 only; not a strict paired test) |

### Owner net — 5-seed screen (`normal`, proven)

| Policy | Mean simulated owner net / season |
|--------|----------------------------------:|
| `current_practice` | $364,689 |
| `pace_learned_owner_net` (candidate) | $340,700 |
| default `engine` | $224,126 |
| `property_flat` | $201,387 |

### Owner net — 25 paired seeds (6–30), confirmation

| Comparison | Scenario | Mean Δ | 95% bootstrap | Seeds left higher |
|------------|----------|-------:|---------------|------------------:|
| engine − `current_practice` | normal | **−$126,674** | −$134,247 to −$118,690 | 0/25 |
| engine − `current_practice` | price_war | −$131,152 | −$137,480 to −$125,044 | 0/25 |
| engine − `current_practice` | holiday_shift | −$138,047 | −$144,645 to −$131,769 | 0/25 |
| engine − `current_practice` | pandemic_collapse | −$8,366 | −$14,974 to −$1,616 | 8/25 |
| pace − default engine | normal | **+$116,281** | +$110,189 to +$121,594 | 25/25 |
| pace − `current_practice` | normal | **−$10,393** | −$17,459 to −$3,462 | 9/25 |
| pace − `current_practice` | pandemic_collapse | +$5,180 | −$1,814 to +$12,707 | 15/25 |

Full JSON: [`paired_owner_net_6_30.json`](market_sim/full_sim_d291c60/paired_owner_net_6_30.json), [`paired_pace_owner_net_6_30.json`](market_sim/full_sim_d291c60/paired_pace_owner_net_6_30.json).

### Top next steps

1. **Holiday / peak pricing on the pace candidate** — 5-seed decomposition still shows peak ADR gap vs `current_practice` (inherited mechanism; candidate closes much of the default-engine gap but not all of the real-rate-card gap).
2. **Systematic sweep** — headroom, pace sensitivity, elasticity prior on 25 held-out seeds (overhaul Phase 4 open work); do not sign off live rate pushes from v1-dollar evidence.
3. **Production path** — shadow at recommendation quality first; use `approval-rate` overlays to bracket production-faithful owner net before any Guesty auto-push.

---

## Test matrix

| Step | Command / tool | Exit | Log |
|------|----------------|------|-----|
| Env | manifest | 0 | `$RUN/manifest_env.txt` |
| Rate card export | `scripts/export_rate_card.py` | 0 | `$RUN/export_rate_card.log` |
| Isolation | `scripts/check_proving_ground_isolation.py` | 0 | `$RUN/gate_isolation.log` |
| Preflight | `scripts/production_preflight.py` | 0 | `$RUN/gate_preflight.log` |
| Quality gates | `scripts/quality_gates.py` | 0 | `$RUN/gate_quality.log` |
| Pytest slow | `pytest -m slow -q` | 0 | `$RUN/pytest_slow.log` |
| Ops | `pytest tests/ops -q` | 0 | `$RUN/ops_tests.log` |
| PG L1 | `proving-ground run --level 1 --seed 20260925 --output-dir $RUN/l1` | **1**† | `$RUN/proving_ground_l1.log` |
| v1 regress | `scripts/regress_market_sim.py` ×2 | 0 | `$RUN/regress_v1_*.log` |
| v2 validation | `scripts/validate_market_calibration.py --calibration v2 --seeds 10` | 0 | `$RUN/v2_calibration_validation.log` |
| v2 screen | `proving-ground market --calibration v2 … --seeds 5 --grid --diagnostics` | 0 | `$RUN/v2_market_screen.log` |
| v2 pace screen | same + `pace_learned_owner_net.yaml` `--allow-models` | 0 | `$RUN/v2_candidate.log` |
| v2 30-seed default | four scenarios × 30 × grid (per-scenario dirs merged) | 0 | `$RUN/v2_default_1_30/run_all.log` |
| v2 30-seed pace | four scenarios × 30 engine-only `--allow-models` | 0 | `$RUN/v2_pace_1_30/run_all.log` |
| Sensitivity | 10 overlays × `--calibration v2 --seeds 10 --grid` | 0 | `$RUN/v2_sensitivity/run.log` |
| Approval | `--approval-rate 0.7 --seeds 10` | 0 | `$RUN/v2_approval_normal_10/run.log` |

†Economic gates fail by design.

**Not run:** v1 30-seed base-anchor reproduction; 15×30 grid; Guesty writes.

---

## Decomposition (5-seed screen, proven)

- **Default engine vs `current_practice`:** total revenue Δ **−$220,753** / season (mean); peak_ski **−$210,245**; Cloud 9 **−$83,628**. Scoreboard reconciliation **0**.
- **Default engine vs `property_flat`:** total revenue Δ **+$38,105** (engine ahead on revenue; still behind on owner net vs `current_practice`).
- **Pace candidate vs `current_practice`:** total revenue Δ **−$30,719** / season (mean). See [`decomp_candidate_vs_current_practice.md`](market_sim/full_sim_d291c60/decomp_candidate_vs_current_practice.md).

---

## Self-check (2026-10-12 / 2026-10-13 corrections)

- Did **not** treat v1 dollar levels as decision-grade; led with v2 and owner net.
- Did **not** call the old base-anchor candidate “unconfirmed” here; this run focused on v2 + pace candidate.
- Did **not** conflate default-engine vs pace-candidate decompositions.
- Labeled 5-seed tables as **screens** and seeds 6–30 as **confirmation**.
- Copied scoreboards, audits, validation JSON, paired owner-net JSON, and decomposition markdown into `docs/reports/market_sim/full_sim_d291c60/` (**no** `.db` files).

---

## File index

| Path | Description |
|------|-------------|
| `~/wp-price-runs/full_sim_20261015_d291c60/` | Full run tree (logs, retained DBs on 5-seed screens only) |
| `docs/reports/market_sim/full_sim_d291c60/` | Copied artifacts for review |
| `docs/reports/market_sim/full_sim_d291c60/v2_calibration_validation.json` | v2 validation gate |
| `docs/reports/market_sim/full_sim_d291c60/paired_owner_net_6_30.json` | Engine vs benchmarks, owner net |
| `docs/reports/market_sim/full_sim_d291c60/paired_pace_owner_net_6_30.json` | Pace vs default / current_practice |
| `$RUN/l1/level_1_seed_20260925_deb183d14d1a/AUDIT_REPORT.md` | L1 audit (outside repo copy) |
