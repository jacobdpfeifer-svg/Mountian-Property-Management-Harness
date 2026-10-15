> **SUPERSEDED 2026-10-14 — do not run.** This protocol only re-proves numbers that are
> already known, in a simulated market priced far below the real one. Use
> `scripts/regress_market_sim.py` to check that nothing moved (minutes). The next full run is
> defined in Phase 6 of [`docs/plans/OVERHAUL_2026-10-14.md`](../plans/OVERHAUL_2026-10-14.md)
> and runs only after the simulator is recalibrated. Known errors in this prompt: the
> "2,596 vs 2,243" figure was the Cloud 9/Overlook cap arm, not the base anchor; the L1 step
> should pass `--output-dir "$RUN/l1"`; the flat benchmark already exists for seeds 1–30 in
> `~/wp-price-runs/market_sim/baseline_79dae5d`.

# Full simulation run — next run after `5aa99a7`

You are running the end-to-end simulation and audit protocol on this repo and
writing up what it shows. This run has three jobs:

1. **Regression check.** Confirm that the guardrail-count fix (`a985b40`) did
   not move any revenue number.
2. **New evidence for the owner decision.** Produce real guardrail counts for
   the base-anchor candidate against the default engine. Every earlier
   confirmation reported zero on both sides because of a bug.
3. **New diagnosis.** Decompose the **candidate** (not the default engine)
   against flat. That shows what is left of the gap once the anchor is in.

Nothing here changes policy, calibration, or live rates.

## Read first

- `docs/reports/FULL_SIMULATION_2026-10-12.md`, especially "Second audit:
  corrections and fixes". It lists the mistakes the last two runs made.
- `docs/reports/market_sim/BASE_ANCHOR_2026-10-09.md`: the candidate's
  confirmation on seeds 6–30.
- `docs/prompts/NEXT_MARKET_SIM.md`, sections "Leave these alone" and "How a
  run is isolated".

## Facts that are already settled (do not re-litigate them)

- `seasonal_base_anchor_full_shoulder` is **confirmed** on seeds 6–30 across
  six scenarios (2026-10-09): `normal` +$23.3k, 25/25 wins. `pandemic_collapse`
  is flat (its interval includes zero). Call it CONFIRMED, never "suggestive",
  and do not recommend confirming it again. The open item is owner sign-off on
  the guard and the base rates (Summit $793, Overlook $916, Cloud 9 $1,035).
- The default engine trails flat by about −$46.7k on `normal` (5 seeds, 0/5
  wins). With the candidate, the gap is about −$20k to −$23k.
- On the default engine, 61% of the gap is off-peak. "Only flat sold" (−$53.8k)
  covers every season. It is not evidence of a peak problem on its own.
- `--incremental` gives a different content hash by design: it persists fewer
  no-action rows. It is not a board-scale speedup. Do not run the runtime probe
  again.
- At L1 (W1_calm), `comp_median_follower` scores exactly like flat (there are
  no comp snapshots), and `moat_off` scores exactly like the engine. The report
  now says so.
- Engine-only throughput is about 3.5 jobs/min. Most of the screen's jobs are
  cheap benchmarks.

## Hard rules

- Simulated revenue is not realized revenue. Say "simulated" every time.
- No Guesty writes. No edits to `config/policies/default.yaml`,
  `proving_ground_exam/market/calibration.yaml`, or any learning flag.
- Do not change engine or simulator code during the run. If you find a bug,
  finish the run, then fix it in a separate commit with a regression test, and
  say clearly which results the bug affected.
- One market sim at a time. Stop a run only with `proving-ground market --stop`.
  Never `--resume` a board that was started before `a985b40`: its score-only
  rows carry fake zero guardrail counts.
- Run outputs go under `~/wp-price-runs/`, never inside the repo (it is in
  iCloud). There are about 56 GB free. Retain databases for `normal` only. No
  15×30 grid. No 1,800-job board.
- Run the CLI as `PYTHONPATH=. .venv/bin/python -m src.cli.main …`
  (`uv run wp-price` fails to import `src`).
- Every number in the report gets a label: **proven** (produced in this run),
  **inherited** (from an earlier report, with its path), or **unknown**.

## Setup

```bash
cd "<repo>"
git status --porcelain            # must be empty; stop and report if not
SHA=$(git rev-parse --short HEAD) # expected 5aa99a7 or a descendant
RUN=~/wp-price-runs/full_sim_$(date +%Y%m%d)_$SHA
PREV=~/wp-price-runs/full_sim_20261012_82f3f0a_2
REF79=~/wp-price-runs/market_sim
mkdir -p "$RUN"; echo "RUN=$RUN" > "$RUN/env.sh"
{ git log -1 --format='%H %s'; .venv/bin/python -V; df -h ~ | tail -1; } > "$RUN/manifest_env.txt"
```

If `HEAD` is not `5aa99a7`, list the commits since then in the report. Say
whether any of them could move scores (engine, simulator, or policy files).

## Steps

### 1. Gates

```bash
P="PYTHONPATH=. .venv/bin/python"
eval $P scripts/check_proving_ground_isolation.py  > "$RUN/gate_isolation.log" 2>&1
eval $P scripts/production_preflight.py            > "$RUN/gate_preflight.log" 2>&1
eval $P scripts/quality_gates.py                   > "$RUN/gate_quality.log" 2>&1
eval $P -m pytest -m slow -q                       > "$RUN/pytest_slow.log" 2>&1
eval $P -m pytest tests/ops -q                     > "$RUN/ops_tests.log" 2>&1
eval $P -m src.cli.main proving-ground run --level 1 --seed 20260925 > "$RUN/proving_ground_l1.log" 2>&1
```

Expected: everything passes, about 840+ tests at ≥70% coverage with mypy
clean, and 445 ops tests. L1 exits 0 with audit verdict FAIL (the economic
gates). The L1 content hash should still be `9be657c9…`. In the L1 report, the
Brier column should read `n/a` for policies other than the engine, and the
twin-baseline lines should be present. Run the full `tests/ops`, not just the
three-test integration matrix.

### 2. Five-seed screen (regression check)

```bash
eval $P -m src.cli.main proving-ground market --scenario normal --seeds 5 --workers 7 \
  --grid --diagnostics --retain-dbs normal --output-dir "$RUN/market_screen_benchmarks" \
  > "$RUN/market_screen.log" 2>&1
eval $P scripts/audit_market_sim.py "$RUN/market_screen_benchmarks/scoreboard.csv" \
  --expect-seeds 5 --expect-scenarios 1 --json "$RUN/market_screen_benchmarks/audit.json"
eval $P scripts/property_diagnostics.py "$RUN/market_screen_benchmarks" --scenario normal \
  --md "$RUN/market_screen_benchmarks/property.md" --json "$RUN/market_screen_benchmarks/property.json"
eval $P scripts/decompose_market_sim.py "$RUN/market_screen_benchmarks" --left engine --right flat \
  --md "$RUN/market_screen_benchmarks/decomp_engine_vs_flat.md" --json "$RUN/market_screen_benchmarks/decomp_engine_vs_flat.json"
```

Compare all 35 rows with `$PREV/market_screen_benchmarks/scoreboard.csv`.
Revenue must match to the cent on every row. Content hashes and guardrail
counts must also match, because these databases are retained. Any difference
is a regression: stop and report it before going further.

### 3. Candidate screen and the new decomposition

```bash
C=seasonal_base_anchor_full_shoulder
eval $P -m src.cli.main proving-ground market --scenario normal --seeds 5 --workers 7 \
  --policy engine --engine-policy config/policies/candidates/$C.yaml \
  --retain-dbs normal --output-dir "$RUN/screen_$C" > "$RUN/candidate.log" 2>&1
eval $P scripts/audit_market_sim.py "$RUN/screen_$C/scoreboard.csv" \
  --reference "$RUN/market_screen_benchmarks/scoreboard.csv" \
  --expect-seeds 5 --expect-scenarios 1 --json "$RUN/screen_$C/audit.json"
eval $P scripts/property_diagnostics.py "$RUN/screen_$C" --scenario normal \
  --engine-policy config/policies/candidates/$C.yaml \
  --md "$RUN/screen_$C/property.md" --json "$RUN/screen_$C/property.json"
# The decomposer reads both policies from one dbs/ folder. Link the flat databases in.
for f in "$RUN"/market_screen_benchmarks/dbs/normal_flat_*.db; do ln -sf "$f" "$RUN/screen_$C/dbs/"; done
eval $P scripts/decompose_market_sim.py "$RUN/screen_$C" --left engine --right flat \
  --md "$RUN/screen_$C/decomp_candidate_vs_flat.md" --json "$RUN/screen_$C/decomp_candidate_vs_flat.json"
```

The candidate rows must match `$PREV/screen_$C/scoreboard.csv` to the cent.

The decomposition is the main new finding. Report the candidate's remaining
gap to flat by season, by property, and by price effect vs volume effect, plus
ceiling and floor rates at peak. Does peak now carry most of the gap? Is it
Cloud 9? Is it volume (fewer nights sold) or price? Back each answer with the
table it comes from.

### 4. Guardrail evidence for the owner decision (score-only, seeds 1–30)

Score-only runs now count guardrails. Run both arms on `normal` with no
retained databases (each takes about 9 minutes):

```bash
eval $P -m src.cli.main proving-ground market --scenario normal --seeds 30 --workers 7 \
  --policy engine --output-dir "$RUN/default_normal_1_30" > "$RUN/default_1_30.log" 2>&1
eval $P -m src.cli.main proving-ground market --scenario normal --seeds 30 --workers 7 \
  --policy engine --engine-policy config/policies/candidates/$C.yaml \
  --output-dir "$RUN/candidate_normal_1_30" > "$RUN/candidate_1_30.log" 2>&1
eval $P scripts/paired_market_sim.py "$RUN/candidate_normal_1_30/scoreboard.csv" \
  "$RUN/default_normal_1_30/scoreboard.csv" --seeds-from 6 --json "$RUN/paired_normal_seeds_6_30.json"
```

Checks:

- Revenue on every row must equal the 2026-10-09 boards
  (`$REF79/post_promote_79dae5d/default_normal_1_30/scoreboard.csv` and
  `$REF79/confirm_base_anchor_79dae5d/candidate_normal_1_30/scoreboard.csv`).
  The paired revenue delta must reproduce +$23,296.
- `guardrail_triggers` must be non-zero on both arms, and seeds 1–5 must equal
  the retained screens from steps 2 and 3.
- Report the paired guardrail delta with its interval, and break it down by
  action type from `guardrail_by_action`. The candidate should trigger fewer
  guardrails (the retained seeds 1–6 averaged 2,596 vs 2,243). If any action
  type goes **up**, call it out: that bears directly on sign-off for the guard.

This step is new evidence about guardrails only. The revenue result is a
reproduction, not a second confirmation.

## Report

Write `docs/reports/FULL_SIMULATION_<YYYY-MM-DD>.md`, copying the structure of
`FULL_SIMULATION_2026-10-12_RUN2.md`: header with the run commit and artifact
root, an executive table, the test matrix (command, exit, duration, log), the
regression results, the candidate-vs-flat decomposition, guardrail evidence,
top next steps, and a file index.

Copy the small artifacts into `docs/reports/market_sim/full_sim_<SHA>/`:
scoreboards, audit and paired JSON, `property.md`, and the decomposition
`.md`/`.json`. Never copy `.db` files.

Top next steps should come from the evidence. Unless something above changes
the picture, they are:

1. Owner sign-off on the base anchor, now with guardrail evidence.
2. A targeted experiment on whatever step 3 shows the remaining gap to be.

Then audit your own report against the corrections table in
`FULL_SIMULATION_2026-10-12.md`, and add a short "Self-check" section saying
you did. Check in particular that you have not:

- called the candidate unconfirmed;
- read the default-engine decomposition as a peak problem;
- treated reproduced numbers as new evidence;
- reported throughput or disk figures you did not measure.

Do not commit or push. Leave the report, copied artifacts, and any code fix
uncommitted for review, and list them at the end of your final message.
