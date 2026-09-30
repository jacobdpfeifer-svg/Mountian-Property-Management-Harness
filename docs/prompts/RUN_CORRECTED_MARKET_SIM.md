# Handoff prompt: full market-sim baseline, diagnosis, and first candidate trials

You are the execution agent for the Winter Park short-term-rental pricing
repository. Your job is to run the shopper-market simulator fully on the current
engine, prove the result is complete and reproducible, explain where the engine
loses money, and then run the first disciplined trials of policy changes that
could make it perform well.

Simulated revenue is evidence about a synthetic shopper world. Never call it
realized revenue, and never call a policy the winner of an unadjusted
multi-scenario comparison.

## Background you need

- Pre-correction 1,800-job board: the engine lost to a flat seasonal rate on all
  15 scenarios, about −$26k per season on `normal`. The engine then stopped
  using future listed prices in its ceiling. A 5-seed `normal` run of the
  corrected engine lost about −$86k. Both boards are **historical context only**.
  Do not average or mix them with anything you produce.
- Leading hypothesis (unproven): peak elasticity is −0.65 in
  `config/policies/default.yaml` (`elasticity_by_season.peak_ski`), which makes
  the revenue optimum equal to the ceiling. Your diagnosis confirms or rejects this.
- All five `models` learning flags are `enabled: false` and stay that way.

Read before starting:

- `docs/reports/market_sim/CORRECTED_RUN_PROTOCOL.md`: the gates. Follow it.
- `docs/reports/market_sim/FINAL.md`
- `docs/reports/market_sim/phase2_SIMULATOR.md` and `phase5_LADDER.md`
- `src/proving_ground/market_loop.py` (runner, checkpoint, resume)
- `config/policies/default.yaml` (sections `pricing`, `ceiling`, `elasticity`,
  `guardrails`, `models`)
- `scripts/audit_market_sim.py` and `scripts/decompose_market_sim.py`

## Hard rules

1. No Guesty connection, no `--apply`, no rate writes. Do not touch
   `data/wp_pricing.db` or anything under `~/Library/Application Support/wp-price`.
2. Do not edit `proving_ground_exam/` (the world, calibration, and scenarios).
3. Do not edit `config/policies/default.yaml`. Candidates are copies passed with
   `--engine-policy`.
4. Every `models.*.enabled` stays `false`, including in candidate copies.
5. If a job fails (`failure.json` appears), stop and report it. Do not work around it.
6. Do not commit, push, or delete files outside your run directory unless the
   user asks. Untracked `* 2.*` files are known iCloud duplicates. Ignore them.
7. Run the CLI as `PYTHONPATH=. .venv/bin/python -m src.cli.main ...`.
   `uv run wp-price` does not work.

## Phase 0: preflight (stop and ask if any check fails)

```bash
cd "<repo root>"
pgrep -fl "proving-ground market"             # must print nothing; another run would compete for CPU
git status --porcelain --untracked-files=no   # must be empty; provenance records git_dirty
git log -1 --oneline
PYTHONPATH=. .venv/bin/python -m pytest -q --ignore-glob="* 2.py"   # all pass
grep -A12 "^models:" config/policies/default.yaml                   # every enabled: false
df -h ~                                                              # need >= 30 GB free
RUN=~/wp-price-runs/market_sim/baseline_$(git rev-parse --short HEAD)
test ! -e "$RUN" && echo "fresh: $RUN"
```

The run directory is deliberately outside iCloud Drive. The repo lives in
iCloud, and syncing thousands of SQLite files corrupts or duplicates them.

## Phase 1: baseline run (1,800 jobs, about 3.5 hours on 7 workers)

```bash
mkdir -p "$RUN"
PYTHONPATH=. nohup caffeinate -i .venv/bin/python -m src.cli.main proving-ground market \
  --scenario all --seeds 30 --workers 7 --grid \
  --retain-dbs normal,price_war,holiday_shift \
  --output-dir "$RUN" > "$RUN/run.log" 2>&1 &
```

- Progress lines in `run.log` read `market jobs N/1800 elapsed … eta …`. Check
  them every 20–30 minutes. Do not poll tightly.
- If the process dies without `failure.json` (sleep, reboot, kill), rerun the
  identical command plus `--resume`. Finished jobs are skipped.
- If `failure.json` exists, stop and report the job and traceback.
- Record the exit status and the wall-clock time.

## Phase 2: verify

```bash
PYTHONPATH=. .venv/bin/python scripts/audit_market_sim.py "$RUN/scoreboard.csv" \
  --expect-seeds 30 --expect-scenarios 15 --json "$RUN/audit.json"   # must exit 0
PYTHONPATH=. .venv/bin/python -m pytest -q -m slow -k two_full_seasons_stay_deterministic
```

Also confirm:

- `provenance.config.models_enabled == []` and `git_dirty == false` in `audit.json`.
- `content_hash` is unique across seeds within every scenario/policy pair.
- All four held-out scenarios (`holiday_shift`, `den_capacity_cut`,
  `regime_change`, `pandemic_collapse`) are scored.

Copy `scoreboard.csv`, `manifest.json`, `run_config.json`, `audit.json`, and
`run.log` into `docs/reports/market_sim/baseline/`. Do not copy databases.

## Phase 3: paired results

From `audit.json`, build one table per comparison (engine − flat,
engine − comp_median, engine − tool). Each table has one row per scenario, with
held-out rows marked. Give the mean, median, min, max, nonnegative seeds out
of 30, and the 95% bootstrap interval. State that the intervals are not
family-wise adjusted. Counting "scenarios won" is descriptive only.

## Phase 4: diagnosis

```bash
for s in normal price_war holiday_shift; do
  for r in flat comp_median; do
    PYTHONPATH=. .venv/bin/python scripts/decompose_market_sim.py "$RUN" \
      --scenario $s --right $r \
      --json "$RUN/decomp_${s}_vs_${r}.json" --md "$RUN/decomp_${s}_vs_${r}.md"
  done
done
```

Check that each "Scoreboard reconciliation" difference is 0. Then answer, with
dollar figures:

1. Price or volume? Split the gap into `both_sold` (same nights sold at a
   different price) versus `only_flat_sold` / `only_engine_sold` (nights won
   or lost).
2. Where? Name the seasons, lead buckets, and properties that carry the gap.
3. Is the engine pinned? Report the share of recommendations at the ceiling
   and at the floor by season. Does the −0.65 peak elasticity hypothesis hold?
4. How much of the gap comes from guardrails? That means `peak_blackout` and
   the clamps on booking days, compared with unguarded bookings.
5. Does the same mechanism appear in `price_war` and `holiday_shift`, or is it
   specific to `normal`?

Write `docs/reports/market_sim/BASELINE_DIAGNOSIS.md`. Lead with a plain
summary for the owner, then rank the loss mechanisms by dollars. End with
three sections: **Proven** (from the run), **Simulator-dependent**, and
**Unknown in the real world**. Copy the decomposition `.md`/`.json` files into
`docs/reports/market_sim/baseline/`.

## Phase 5: first candidate trials

Start this only after `BASELINE_DIAGNOSIS.md` is written.

1. Propose at most three candidates. Each targets one ranked mechanism. Each
   is a copy of `default.yaml` at `$RUN/candidates/<name>.yaml` that changes
   only values in `pricing`, `ceiling`, `elasticity`, or `guardrails`.
   `models` stays off. No code edits in this phase. If a fix needs code, write
   it up as a proposal instead.
2. Motivate each value from the mechanism, not from the flat rate. Setting a
   ceiling or price equal to the flat benchmark is overfitting, so don't.
3. Before running a candidate, write it into `BASELINE_DIAGNOSIS.md` under
   "Pre-registered candidates": its name, the YAML diff, the mechanism it
   targets, and the expected direction by season.
4. Screen each candidate (engine only, 5 seeds, all 15 scenarios, about 25 minutes):

   ```bash
   C=<name>
   PYTHONPATH=. caffeinate -i .venv/bin/python -m src.cli.main proving-ground market \
     --scenario all --seeds 5 --workers 7 --policy engine \
     --engine-policy "$RUN/candidates/$C.yaml" --output-dir "$RUN/screen_$C"
   PYTHONPATH=. .venv/bin/python scripts/audit_market_sim.py "$RUN/screen_$C/scoreboard.csv" \
     --reference "$RUN/scoreboard.csv" --expect-seeds 5 --expect-scenarios 15 \
     --json "$RUN/screen_$C/audit.json"
   ```

   `--reference` pairs the candidate against the baseline's flat, comp_median,
   and tool rows, and against the baseline engine (as `baseline_engine`), on
   the same seeds. It refuses a reference from a different world.
5. Promote at most one candidate. To qualify, its mean beats `baseline_engine`
   on `normal` and on at least 3 of the 4 held-out scenarios, and it does not
   make `price_war` or `pandemic_collapse` worse than baseline.
6. Confirm the promoted candidate with the same command at `--seeds 30`
   (about 2.5 hours). Audit it with `--seeds-from 6`, so seeds 1–5, which
   picked it, do not grade it.
7. Write `docs/reports/market_sim/CANDIDATES.md`. Include every screen result
   (losers too), the confirmation table against both flat and
   `baseline_engine`, the YAML diff, and the risks. Do **not** change
   `default.yaml`. The owner decides.

## Deliverables

- `$RUN/`: full outputs, retained databases, logs, screens.
- `docs/reports/market_sim/baseline/`: scoreboard, manifest, run config,
  audit, and decomposition files.
- `docs/reports/market_sim/BASELINE_DIAGNOSIS.md`
- `docs/reports/market_sim/CANDIDATES.md` (if Phase 5 ran)
- A final chat summary of 5–10 plain-language lines. Give the baseline result
  on `normal` and held-out, the dominant loss mechanism in dollars, the
  candidate outcome, and what is still unknown. Report exactly which gates
  passed or failed, and quote any failing output.
