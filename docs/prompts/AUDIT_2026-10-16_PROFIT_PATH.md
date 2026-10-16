# Independent audit — the 2026-10-16 "path to profitability" build

You are auditing uncommitted work in `~/code/harness` (branch `main`, base commit `9df78c0`). Run
`git status` and `git diff` to see it. Treat every claim in the docs as unverified until you
reproduce it. You have no context from the author. That is intentional.

## What was built (workstreams 2–9)

| WS | Claim | Where |
|---|---|---|
| 2 | `comp_anchor` uses each own-set active comp's latest good quote, ≤ 42 days old; min 3 comps at the call site. The old rule took one global `MAX(as_of)` and went empty on real data | `src/pricing/pace.py`, `src/pricing/__init__.py`, `tests/test_comp_anchor.py` |
| 2 | Cap/min chosen by a study (real drift + Monte Carlo + real holdout) | `scripts/anchor_rule_study.py`, `docs/reports/anchor_rule_study/` |
| 3 | Register hashes code (`code_sha256` over `CODE_PATHS`); freeze refuses exposed seeds, unknown scenarios, dirty tree; sim takes `--seed-start`; boards record `code_sha256` | `src/experiments/__init__.py`, `scripts/freeze_experiment.py`, `src/proving_ground/market_loop.py`, `src/cli/main.py` |
| 4 | Read-only Guesty → spine adapters; CSV import via mapping files | `src/data_spine/adapters.py`, `backfill.py`, `config/data_mapping/` |
| 5 | Screen requires a gain; evaluation gate (superiority on normal, non-inferiority in every world, per-home harm); sim reports owner net per property; new `scrape_degraded` world | `scripts/screen_gate.py`, `scripts/evaluation_gate.py`, `proving_ground_exam/market/scoring.py`, `world.py` |
| 6 | Shadow mode: review queue + spine decisions + append-only runs/outcomes; refuses stale recs and DBs with past writes | `src/shadow/`, `src/db/migrations/0006_shadow.sql` |
| 7/9 | Field test: frozen plan, seeded paired week blocks, settled owner net per eligible night, sign-flip CI, segment harm, stop rules | `src/experiments/field.py`, `docs/field_test/` |
| 8 | Canary readiness gates; returns validated sign-off only (never builds an authorization) | `src/experiments/readiness.py`, `docs/runbooks/CANARY.md` |

## What to check — find defects, not style

1. **Correctness of `comp_anchor`.** Try to break it. Cases: duplicate `(comp, as_of, stay)` rows,
   timestamps vs dates in `as_of`, inactive comps, shared comps, age-cap boundary off-by-one. Is the
   SQL index-friendly at 120 nights × 3 homes × daily runs?
2. **Study validity.** Does `anchor_rule_study.py` score the old rule faithfully? Is the minimax-regret
   choice sensitive to fitted parameters? Any leakage in `holdout` (index built from the held comp, or
   from future days)? Are the conclusions in `DECISION.md` supported by `results.json`?
3. **Experiment integrity.** Can a board made by different code, a dirty tree, or before freeze pass
   `screen_gate`/`evaluation_gate`? Does `code_sha256` miss any code that changes prices or the sim?
   Is the `started_at` vs `frozen_at` string comparison sound across timezone formats? Can
   `exposed_seeds` be fooled?
4. **Evaluation statistics.** `paired_interval` is a percentile bootstrap on 25 seeds; is that
   adequate? Is `evaluation_decision` right when a home's comparator mean is ≤ 0?
5. **Field-test statistics.** Verify the sign-flip CI coverage, the bisection in `paired_effect`,
   the unbounded-interval guard, the allocation of multi-night stays across blocks, settlement
   gating, and the decision rule's multiplicity (claimed ~5% false HARM under the null).
6. **Money semantics.** Do the Guesty adapter's ledger lines double-count with the accounting
   import (both may send `gross_lodging` for the same stay under different `entry_key`s)? This is a
   suspected weak point. Prove or disprove it, and propose the fix.
7. **Write safety.** Is there any path from new code to `set_rate`/`push_rate`? Can `ReadOnlyGuesty`
   be bypassed (`object.__getattribute__`, `_client`)? Does shadow mode ever write outside its tables?
8. **Confidentiality.** The repo is public. Is any real listing name, id, address, guest field or
   Cloud 9 data newly tracked? Run `python scripts/scan_repo.py`.
9. **Tests.** Run `.venv/bin/python -m pytest -q`. Ten `tests/proving_ground` tests fail only while
   another market sim holds `~/wp-price-runs/market_sim/RUN.lock`. Confirm that is the only cause.
   Which new behaviour is untested?

## Report

For each finding give file:line, a concrete failing input or scenario, severity (blocker / major /
minor), and the smallest fix. Separate **verified** findings (you reproduced them) from **suspected**
ones. Do not edit files. End with a one-paragraph verdict: is this safe to commit, and what blocks
EXP-PACE-V3-001 from being frozen?
