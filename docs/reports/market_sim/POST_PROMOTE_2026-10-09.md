# Post-promote verification — 2026-10-09

**Commit:** `79dae5d` (working tree includes engine batching + promoted `default.yaml`)  
**Artifact roots:**

- Post-promote matrix: `~/wp-price-runs/market_sim/post_promote_79dae5d/`
- Sensitivity grid: `~/wp-price-runs/market_sim/sensitivity_79dae5d/`
- Prior combined confirmation: `~/wp-price-runs/market_sim/combined_confirmation_79dae5d/`

Simulated shopper revenue only. Not realized revenue. `calibration.yaml` was not edited. Guesty was not touched.

---

## Decision

**Deploy promoted default for production review** — `config/policies/default.yaml` now includes Cloud 9 / Overlook `property_season_ceiling` caps (same as the confirmed combined candidate). Post-promote paired audits show **zero** engine revenue delta between promoted default and the historical candidate overlay on seeds 6–30 for all six graded scenarios. Engine batching (run-scoped YAML memo, `comp_evidence` memo, ceiling SQI memo) passed pytest and a 60-day fingerprint test; full-season profile wall time fell from ~166 s to ~136 s (~18%).

The engine still **does not beat flat** on `normal` in the synthetic world (~−$46k vs flat at combined confirmation; sensitivity overlays below show the same pattern except `peak_flat_high`). That gap is a product/strategy question, not a reason to revert the caps.

---

## Promotion equivalence (default vs candidate overlay)

Orchestration: [`scripts/post_promote_market_sim.sh`](../../../scripts/post_promote_market_sim.sh)

| Step | Jobs | Notes |
|------|-----:|-------|
| `default_*` vs `overlay_*` per scenario | 30 engine each × 6 scenarios | score-only |
| Paired audit | seeds 6–30 | `overlay_*_paired_seeds_6_30.json` |
| Diagnostic retain | seeds 1–6 × 2 arms | `*_normal_diagnostic` (~476–483 MB each) |

**Paired mean Δ revenue (overlay − default), seeds 6–30:** **$0** on `normal`, `holiday_shift`, `den_capacity_cut`, `regime_change`, `pandemic_collapse`, `price_war` (25/25 wins tied at zero).

---

## Engine batching and equivalence

| Change | File |
|--------|------|
| One deepcopy per YAML file per pricing run | `src/config.py` |
| Run memo for `comp_evidence` | `src/comps/__init__.py` |
| Run memo for ceiling `_sqi_for` | `src/ceiling/__init__.py` |
| Tests | `tests/test_engine_run_cache.py` |

**Profile** (`normal`, seed 6, `persist_recommendations=False`):  
`~/wp-price-runs/market_sim/post_promote_79dae5d/profiles/default_seed6.prof`, `top40.txt`  
Wall **136.4 s** vs **166.2 s** pre-batch (`combined_confirmation_79dae5d/profiles/top25.txt`).

---

## Sensitivity (`normal`, 5 seeds, `--grid`)

Orchestration: [`scripts/sensitivity_market_sim.sh`](../../../scripts/sensitivity_market_sim.sh)  
Promoted default engine; overlays under `config/market_sim/sensitivity/`. Not family-wise adjusted.

| overlay | engine mean rev | flat mean rev | engine − flat |
|---------|----------------:|--------------:|--------------:|
| arrival_high | 261,804 | 303,220 | −41,416 |
| arrival_low | 178,969 | 207,730 | −28,761 |
| cloud9_quality_high | 221,125 | 268,800 | −47,675 |
| cloud9_quality_low | 218,260 | 269,210 | −50,950 |
| outside_option_down | 226,760 | 273,140 | −46,380 |
| outside_option_up | 209,674 | 258,030 | −48,356 |
| peak_flat_high | 216,122 | 171,780 | +44,342 |
| peak_flat_low | 220,388 | 271,580 | −51,192 |
| price_coef_flatter | 220,330 | 271,410 | −51,080 |
| price_coef_steeper | 219,238 | 266,630 | −47,392 |

Scoreboards: `~/wp-price-runs/market_sim/sensitivity_79dae5d/sensitivity_*/scoreboard.csv`.

---

## Disk usage

| Path | Size |
|------|-----:|
| `post_promote_79dae5d` (matrix + diagnostics + profiles) | ~984 MB |
| `sensitivity_79dae5d` (score-only) | ~600 KB |

---

## Verification commands (re-run)

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
PYTHONPATH=. .venv/bin/python -m compileall -q src proving_ground_exam scripts
RUN=~/wp-price-runs/market_sim/post_promote_$(git rev-parse --short HEAD) \
  bash scripts/post_promote_market_sim.sh
RUN=~/wp-price-runs/market_sim/sensitivity_$(git rev-parse --short HEAD) \
  bash scripts/sensitivity_market_sim.sh
```
