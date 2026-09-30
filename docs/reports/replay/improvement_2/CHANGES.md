# Improvement 2 — materialized exclusion ledger

Date: 2026-09-29  
Base: Improvement 1 plus independent Audit 2

## Audit 2 finding addressed

Audit 2 found no S1 defect and no disagreement in 20 independent label checks. It did identify an S2 observability gap: blocked and already-booked candidates were present only in aggregate `panel_counts`, not as row-level audit records.

## Test-first evidence

Failing test before implementation:

```text
ImportError: cannot import name 'exclusion_record' from 'src.eval.replay'
```

After implementation:

```text
.venv/bin/python -m pytest tests/test_replay.py::test_replay_materializes_exclusion_ledger \
  tests/test_replay.py -q
10 passed
```

## Changes

- Added `exclusion_record()` to define a stable row-level schema: decision day, property, stay date, pacing status, reason, and booking event.
- Added `ReplayResult.excluded_rows` and materialized records for `blocked_at_decision`, `already_booked_at_decision`, and `no_recommendation` candidates.
- Kept aggregate per-day/per-property counts for concise reporting.
- Preserved all Guesty, no-lookahead, calibration-floor, and direction-floor guards.
- Applied the unchanged calibration floors to distinct resolved nights and positive booking events as well as decision rows; no clean-window calibration claim is emitted for 17 distinct nights / 4 positives.
- Did not tune policy, engine parameters, or elasticity betas.

## Scope

Files changed by Improvement 2:

```text
src/eval/replay.py
tests/test_replay.py
docs/reports/replay/improvement_2/CHANGES.md
```

No performance optimization was applied. The replay remains about 22.5 minutes for this window; an optimization without a proven identical-output baseline would be unsafe.

The full suite result after this change was `321 passed, 3 failed, 1 deselected`. The three failures are pre-existing tests in `tests/test_memory.py` against unrelated uncommitted memory changes; no replay test failed.
