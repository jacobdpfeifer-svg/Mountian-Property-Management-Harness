# Corrected market-sim run report

Date of this write-up: 2026-10-01  
Protocol: [docs/prompts/RUN_CORRECTED_MARKET_SIM.md](../../prompts/RUN_CORRECTED_MARKET_SIM.md) and [CORRECTED_RUN_PROTOCOL.md](CORRECTED_RUN_PROTOCOL.md)

**All dollar figures below are simulated shopper-world revenue.** They are not realized Winter Park revenue and are not a reason to write rates to Guesty. Bootstrap intervals are not family-wise adjusted. Counting “scenarios won” is descriptive only.

This report is the narrative of one execution. The scoreboard tables live in [BASELINE_DIAGNOSIS.md](BASELINE_DIAGNOSIS.md). The YAML trials live in [CANDIDATES.md](CANDIDATES.md). Copies of the baseline artifacts (no databases) are in [baseline/](baseline/).

---

## What this run was for

The pricing engine had already been changed so it no longer treats this year’s unsold listed prices as history when it builds a ceiling. Older 1,800-job boards (about −$26k vs flat before that change, about −$86k on a 5-seed `normal` after it) are **historical context only**. They were not averaged into this board.

This run was meant to:

1. Score the current engine, from a clean commit, on all 15 winters × 30 seeds × 4 policies (1,800 jobs).
2. Prove the board is complete and reproducible.
3. Split the loss into price vs volume, by season, property, and booking lead.
4. Test the guess that peak elasticity −0.65 pins the engine at its ceiling.
5. Try at most three YAML-only policy copies, without editing `config/policies/default.yaml` and without turning learning on.

Hard rules held: no Guesty, no `--apply`, no edits to `proving_ground_exam/` or `default.yaml`, all five `models.*.enabled` flags stayed `false`.

---

## What happened operationally

### Preflight

An older market-sim was still running from Cursor (output under `.testrun_runs/market_sim/corrected_full` in iCloud, `--retain-dbs` of everything). It was stopped so it would not compete for CPU. Its files were left in place.

Then:

| check | result |
|---|---|
| `pgrep proving-ground market` | empty after the kill |
| `git status --porcelain --untracked-files=no` | empty |
| HEAD | `79dae5d Make the market-sim board resumable and auditable, and add the run prompt.` |
| pytest `--ignore-glob="* 2.py"` | 375 passed, 2 deselected |
| `models.*.enabled` | all `false` |
| disk | ~65 GB free (need ≥ 30 GB) |
| run directory | `~/wp-price-runs/market_sim/baseline_79dae5d` did not exist |

Output was placed **outside iCloud Drive** on purpose. The repo lives in iCloud; thousands of SQLite files there duplicate and corrupt.

### Two false starts

The first start (about 15:34 local) wrote `run_config.json` and in-flight databases, then died with **zero** lines in `results.jsonl` and an empty `run.log`. A second session had started another 1,800-job grid into iCloud (`corrected_full`) and `pkill -f "proving-ground market"` killed this process too.

That competing job was stopped again. Incomplete databases in `~/wp-price-runs/.../dbs` were discarded (nothing had been checkpointed). The protocol run was restarted at **16:30 local / 22:30 UTC** with unbuffered Python so progress would actually print.

A later `pkill` from the other session did not recur. From that restart, the run completed without `--resume`.

### Baseline grid

```
PYTHONPATH=. .venv/bin/python -m src.cli.main proving-ground market \
  --scenario all --seeds 30 --workers 7 --grid \
  --retain-dbs normal,price_war,holiday_shift \
  --output-dir ~/wp-price-runs/market_sim/baseline_79dae5d
```

| | |
|---|---|
| Started | 2026-09-30T22:30:09Z |
| Finished | 2026-10-01T01:38:36Z |
| Wall clock | 11,306.8 s (~188 minutes) |
| Jobs | 1,800 / 1,800, `resumed_jobs: 0` |
| Exit | 0, no `failure.json` |
| Python | 3.12.14, macOS arm64, 7 workers, `caffeinate -i` |
| Commit | `79dae5d`, `git_dirty: false` |
| `models_enabled` | `[]` |
| Scoreboard hash | `9d9257e12ba5e3ce0c8f600a7a08c260f94231d78cdf86bbdded0bc0d218aa1b` |

Engine jobs ran first (all 15 × 30). Those are slow (~2.5 jobs/minute). After job ~450, flat / competitor-median / tool jobs finished in a few minutes. Early ETAs of many hours were an artifact of that mix.

Job databases were kept only for `normal`, `price_war`, and `holiday_shift` (~15 GB, not ~60 GB). Those three are what diagnosis can read.

---

## Did the board pass the gates?

Yes, except the descriptive “engine beats flat” gates, which this engine does not.

| gate | result |
|---|---|
| `scripts/audit_market_sim.py --expect-seeds 30 --expect-scenarios 15` | exit 0, 1,800 unique rows, no missing, no duplicates |
| Provenance `models_enabled == []` and `git_dirty == false` | pass |
| `pytest -m slow -k two_full_seasons_stay_deterministic` | 1 passed |
| `content_hash` unique across seeds within each scenario/policy | 60 pairs, no collisions |
| Held-out winters present | `holiday_shift`, `den_capacity_cut`, `regime_change`, `pandemic_collapse` |
| Decomposition vs scoreboard revenue | difference **0.0** on all six retained comparisons |
| `normal_beats_flat` | **false** (mean −$93,012; interval entirely below zero) |
| Mean beats flat, any scenario | **0 of 15** |

Copies (no databases) went to `docs/reports/market_sim/baseline/`: `scoreboard.csv`, `manifest.json`, `run_config.json`, `audit.json`, `run.log`, and the six `decomp_*` files.

---

## What the engine did versus the three benchmarks

On every scenario’s **mean**, the engine earned less than:

- a **flat seasonal rate**,
- **following competitors** (`comp_median`),
- the **public-tool imitation** (`tool`).

The gap versus flat on an ordinary winter:

- mean **−$93,012**
- median −$90,212
- range −$130,665 to −$70,790
- **0 of 30** seeds nonnegative
- 95% bootstrap interval **−$98,760 to −$87,708**

Held-out versus flat (means): `holiday_shift` −$94,861; `den_capacity_cut` −$92,829; `regime_change` −$89,211; `pandemic_collapse` −$15,114 (1 of 30 seeds nonnegative; interval still below zero).

Versus competitor-median on `normal`: −$89,253 (0/30). Versus tool on `normal`: −$39,021 (1/30 seeds nonnegative). On `price_war`, tool is almost as bad a miss as flat (−$77k vs tool, −$91k vs flat): the engine does not cut with a price war the way the tool imitation does.

The full 15-row tables are in [BASELINE_DIAGNOSIS.md](BASELINE_DIAGNOSIS.md).

---

## Where the money went (`normal` vs flat, per-seed means)

Night-by-night split from retained databases:

| outcome | nights | revenue delta |
|---|---:|---:|
| both sold (same night, different price) | 198 | **−$24k** |
| only flat sold | 117 | **−$103k** |
| only engine sold | 52 | **+$34k** |
| neither | 173 | $0 |
| **net** | | **−$93k** |

So this is mostly **empty nights**, not “we sold the same stays cheaper.”

By season:

| season | engine occ | flat occ | engine ADR | flat ADR | revenue delta |
|---|---:|---:|---:|---:|---:|
| peak ski | 0.35 | 0.61 | $969 | $900 | **−$67k** |
| early winter | 0.53 | 0.42 | $462 | $750 | −$10k |
| shoulder spring | 0.79 | 0.74 | $374 | $650 | −$16k |

Peak: the engine charges **more** and sells **fewer** nights. Shoulder and early winter: the engine charges **much less**, sells a bit more, and still loses money.

By property: **Cloud 9 −$52k** (occ 0.32 vs 0.58), Overlook Ridge −$34k, Summit Haus only −$6k and actually higher occupancy than flat.

By lead time: the 22–60 day bucket is −$44k (97 engine nights vs 140 flat).

### The −0.65 peak-elasticity guess

The hypothesis was: peak elasticity −0.65 is inelastic, so RevPAN’s optimum is the ceiling, so the engine sits on the ceiling all peak season.

**That is not what the tagged recommendations show.** On `normal`, 19.7% of peak recommendations are at the ceiling, 0% at the floor. About 9% of peak recs are `peak_blackout`. On the day a night actually booked, `peak_blackout` is only 14 nights / ~$14k; move clamps are tenths of a night. Guardrails are not the dollar story.

Peak still *behaves* as too expensive for this shopper world (high ADR, low occupancy). The pin is not “almost every rec at the ceiling.”

Shoulder and early winter are the opposite: ~18% of early-winter recs and ~22% of shoulder recs sit at the **floor**.

`price_war` and held-out `holiday_shift` show the same shape (volume dominates, Cloud 9, ~20% peak at ceiling, floor-pinned shoulder). This is not a `normal`-only artifact.

---

## YAML trials

Three copies of `default.yaml` were written under `$RUN/candidates/` **after** the diagnosis, with expected direction written down first. Only `booking_probability.elasticity_by_season` or `ceiling.percentile` changed. Ceilings were not set to the flat $900 peak. Learning stayed off. No code edits.

Each screen: engine only, 15 scenarios, seeds 1–5, ~75 jobs, paired to the baseline’s flat / competitor / tool rows and to the baseline engine as `baseline_engine`.

| candidate | change | `normal` vs current engine | promote? |
|---|---|---|---|
| `peak_more_elastic` | peak −0.65 → −1.20 | **−$1,797** (2/5) | no |
| `shoulder_off_floor` | early/shoulder → −1.10 | **+$4,923** (5/5) | yes |
| `lower_peak_ceiling` | ceiling percentile 0.90 → 0.80 | +$112 (median $0) | no |

`peak_more_elastic` helped several stress winters (`pandemic_collapse` +$25k on the screen) but **lost on `normal`**, so it was not confirmed. Making peak more elastic was the natural attack on the volume hole; on this shopper world it did not pay on an ordinary winter.

`lower_peak_ceiling` barely moved anything. The history ceiling percentile is not what is emptying Cloud 9.

`shoulder_off_floor` met the promotion rule: beat the current engine on `normal`, on all four held-out means, and did not worsen `price_war` or `pandemic_collapse`.

### Confirmation (seeds 6–30)

450 engine jobs, `~/wp-price-runs/market_sim/baseline_79dae5d/confirm_shoulder_off_floor/`, ~164 minutes, exit 0. Graded with `--seeds-from 6` so the five seeds that picked it do not grade it.

Versus the **current engine** (seeds 6–30):

- `normal`: **+$5,697** (24/25 seeds; interval $4,542 to $6,941)
- `price_war`: +$5,005 (21/25)
- held-out: `holiday_shift` +$4,550; `den_capacity_cut` +$5,090; `regime_change` +$4,668; `pandemic_collapse` **+$86** (interval −$607 to +$814, includes zero)
- descriptive: mean above the current engine on 15 of 15 scenarios

Versus **flat** (same seeds): `normal` **−$88,732** (0/25; interval −$94,932 to −$82,989). Still a large simulated loss. The candidate fixes a slice of shoulder/early underpricing. It does not close the peak / Cloud 9 hole.

---

## What was not done

- `default.yaml` was not changed. Shipping `shoulder_off_floor` is an owner decision.
- Learning flags were not turned on.
- Guesty was not contacted. `data/wp_pricing.db` and `~/Library/Application Support/wp-price` were not touched.
- `proving_ground_exam/` (the shopper world) was not edited.
- Nothing was committed or pushed from this work.
- Peak volume was not fixed. The candidate that aimed at it failed its `normal` screen.

---

## Proven / simulator-dependent / unknown

**Proven in this synthetic world, this commit, this board:** 1,800 complete jobs; learning off; hashes differ by seed; four held-out winters scored; engine mean below all three benchmarks on every scenario; loss is mostly unsold peak nights, concentrated on Cloud 9 and 22–60 day lead; peak recs at ceiling ~20% not ~100%; a milder shoulder elasticity earns ~$5–6k more than this engine and still ~$89k less than flat.

**True only if you believe this shopper model:** choice with an outside option, the coded competitor types, the flat and tool policies, and a linear demand curve whose argmax is the ceiling when |elasticity| < 1.

**Unknown in the real world:** whether guests would actually leave Cloud 9 empty at these peak ADRs; whether a cheaper peak would give up Christmas weeks; whether floor-pinned shoulder prices are a history/compose bug YAML cannot fix; anything about writing these numbers into Guesty.

---

## Where to look

| thing | path |
|---|---|
| Full outputs | `~/wp-price-runs/market_sim/baseline_79dae5d/` |
| Scoreboard / audit / log (repo copies) | `docs/reports/market_sim/baseline/` |
| Diagnosis + paired tables | `docs/reports/market_sim/BASELINE_DIAGNOSIS.md` |
| Candidate screens + confirmation | `docs/reports/market_sim/CANDIDATES.md` |
| Candidate YAML | `~/wp-price-runs/market_sim/baseline_79dae5d/candidates/` |
| Confirmation board | `~/wp-price-runs/market_sim/baseline_79dae5d/confirm_shoulder_off_floor/` |
