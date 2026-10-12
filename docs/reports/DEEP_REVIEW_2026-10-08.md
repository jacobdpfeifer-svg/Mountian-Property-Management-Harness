# Deep audit and follow-up review — 2026-10-08

## Executive conclusion

The short audit was not a full-season full-grid simulation. It completed 35 jobs
(7 policies × 5 seeds), so roughly 12 minutes is consistent with a screen rather
than the inherited 1,800-job run. The engine itself remains expensive: the
post-fix 10-seed engine run took 5m05s with seven workers, or about 30 seconds
of wall-clock per job at that concurrency.

The most important commercial result is that the normal-scenario loss is mainly
a peak-volume problem. The combined candidate that caps peak ceilings at the
property base for Cloud 9 and Overlook materially improves the result, but still
does not beat the flat benchmark.

## Changes made

1. Market simulation diagnostic tracing is now conditional on retained job DBs.
   Non-retained scoring runs no longer copy all availability sets or write a loss
   trace row for every shopper/property pair.
2. Engine recommendation persistence is conditional on retained job DBs. Scoring
   runs still set prices and score realized revenue, but do not write a full
   recommendation history that will immediately be deleted.
3. Resume metadata now records retained scenarios, preventing a diagnostic resume
   from silently reusing score-only checkpoints with missing evidence.
4. Added `src/__init__.py` and included both `src*` and `proving_ground_exam*` in
   package discovery. The installed `wp-price` entry point previously failed
   outside the repository because these packages were not reliably importable.
5. Added the candidate policy
   `config/policies/candidates/cloud9_overlook_lower_peak_ceiling.yaml`.

## Follow-up simulation results

All runs used `normal`, seeds 1–10, full season, seven workers, and unretained
DBs unless otherwise stated. These are paired simulations: the same seed is used
across policies.

| Policy | Mean revenue | Std. dev. | Mean peak occupancy | Wins vs default |
|---|---:|---:|---:|---:|
| Default engine | $169,721 | $16,244 | 0.356 | — |
| Cloud 9 cap | $189,296 | $16,970 | 0.418 | 9/10 |
| Overlook cap | $208,225 | $13,120 | 0.495 | 10/10 |
| Cloud 9 + Overlook caps | **$218,639** | $13,673 | 0.530 | **10/10** |
| Flat benchmark | $264,570 | $13,329 | 0.615 | 10/10 |
| `premium_cap` diagnostic | $262,476 | $8,404 | 0.736 | 10/10 |

The combined candidate is approximately $48,918 above the default engine over
this screen, but approximately $45,931 below flat. It should remain a candidate,
not be copied into `default.yaml`.

## Micro findings

- The prior decomposition’s dominant loss remains valid: the default engine
  sacrifices too many peak nights for higher ADR.
- The property-specific result is additive: Overlook is the larger single
  contributor, while Cloud 9 still contributes a meaningful improvement.
- `premium_cap` remains a useful upper-bound benchmark. Its performance says the
  default ceiling/premium stack is too permissive in this calibrated world; it
  does not establish that comp-capping is safe in production.
- Incremental repricing should remain a correctness/resume feature, not the main
  performance strategy. The main cost is still the per-day recommendation path.
- Retaining diagnostic databases is intentionally expensive. Use it for a small
  evidence screen, then run larger score-only screens without `--retain-dbs`.

## Macro backlog

1. Run the combined candidate across seeds 6–30 and held-out scenarios before any
   promotion decision.
2. Add a scenario/policy report that separates peak volume, ADR, and property
   contribution automatically, rather than relying on manual decomposition.
3. Profile and batch the recommendation path (`generate_recommendations`, ceiling
   history, and repeated SQLite reads). This is the remaining major runtime
   opportunity.
4. Add `tests/ops/` and either raise ops coverage honestly or keep an explicit
   temporary coverage exclusion with an owner/date. The current 70% gate still
   fails because the new ops/compliance surface is under-tested.
5. Remove or quarantine the 46 iCloud `* 2.py` duplicates after confirming none
   is canonical. This was not done automatically because it is a destructive
   repository cleanup.
6. Keep model promotion separate from repo/runtime changes. The proving-ground
   L1 economic gates still fail, so the candidate result is not a release gate.

## Verification

- Targeted proving-ground tests: 36 passed.
- Full default pytest suite: **439 passed, 2 deselected**.
- Python compile check passed for `src`, `proving_ground_exam`, and `scripts`.
- All follow-up scoreboards completed and were written under `/tmp/wp-price-audit-after/`.
