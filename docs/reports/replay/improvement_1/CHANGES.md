# Improvement 1 — replay panel and label contract

Date: 2026-09-29  
Base: `f5918117d18d0fa56e69e1d862646338ddeb688b`  
Run artifact: `docs/reports/replay/run2/`

## What changed

### `src/eval/replay.py`

- Added the exact label contract: booking event after decision day D and on/before `min(stay_date, censor)`; already-booked-at-D is excluded and reported separately.
- Added `label_for_decision()` and a reservation-confirmation event map, with `nightly_inventory.booked_at` only as a legacy fallback. Current `status` is not treated as a booking event.
- Built the replay candidate panel from decision-day `pacing_snapshots`, rather than silently using current inventory status.
- Added `outcome_label`, `outcome_status`, and `exclusion_reason` fields to rows.
- Added per-decision-day/per-property panel accounting and repeated-night effective-N warnings.
- Added a deduplicated calibration view while preserving calibration floor 20 and direction floor 5.
- Restricted revenue comparison rows to resolved, labeled nights.
- Made missing listed-price provenance exact: missing as-of prices are marked `listed_source=none` and excluded from reference comparisons.
- Printed the exact label definition and panel-accounting provenance in JSON/HTML.

### `src/features/__init__.py`

- When `as_of` is supplied, feature status, listed price, lead time, and orphan-gap status are taken from that decision-day pacing snapshot. This prevents current mutable inventory from standing in for historical state.

### `tests/test_replay.py`

- Added a synthetic regression covering booked-before-D, booked-after-D-before-censor, never-booked resolved, and future-unresolved states.
- Added repeated-night effective-N assertions.
- Updated the report assertion to require the exact label definition.

### Reports

- Phase 1 findings remain at `../audit_1/FINDINGS.md`.
- Run 2 artifacts are in `../run2/`.

## Before/after behavior

| Measure | Original run | Run 2 | Explanation |
|---|---:|---:|---|
| Logged decisions | 9,644 | 9,736 | Decision-day pacing availability is now used; current-state exclusions no longer remove nights that were available on D. |
| Resolved scored decisions | 52 | 77 | Booked outcomes are retained when the night was available at D and the event falls in the valid interval. |
| Booked scored labels | 0 | 4 | Labels now use booking events after D rather than only emitted-current-availability rows. |
| Excluded/already-booked accounting | implicit | explicit in `panel_counts` | Current decision-day booked/blocked statuses are reported instead of silently disappearing. |
| Calibration Brier | 0.575 | 0.551 | This is a changed, more appropriate panel; it is not evidence of model improvement. |
| Deduplicated eligible N | not reported | 17 | Repeated decision rows inflate the per-decision N; deduplicated calibration is correctly unmeasurable below 20. |
| Guesty writes | 0 | 0 | Guard preserved; run used a DB copy. |

The 4 booked labels are not claimed to equal all 14 booked nights observed in the September inventory. The relevant panel is nights available on the decision day, with bookings after that day and before the terminal boundary; the independent Audit 2 must verify each label.

## Test-first evidence

Failing regression before implementation:

```text
ImportError: cannot import name 'label_for_decision' from 'src.eval.replay'
```

After implementation:

```text
.venv/bin/python -m pytest tests/test_replay.py::test_replay_label_contract_and_effective_n_fixture \
  tests/test_replay.py::test_calibration_measurable_on_enough_resolved -q
2 passed
```

Full replay-focused/touched suite:

```text
.venv/bin/python -m pytest tests/test_replay.py tests/test_engine.py \
  tests/test_bookprob_pacing.py tests/test_strategies.py -q
56 passed in 4.56s
```

The branch has 9 replay tests after the honest regression addition; the Phase 1 audit found no historical evidence for the claimed 12.

## Run 2 integrity evidence

- Original operator DB checksum before: `12918aff638ef16b4a08aaa3e4b86a9d9bbfab786aa5db2c9ab4fcdffeba42e3`.
- Original operator DB checksum after: `12918aff638ef16b4a08aaa3e4b86a9d9bbfab786aa5db2c9ab4fcdffeba42e3`.
- Original counts before/after: `rate_changes=0`, `pacing_snapshots=32170`, `reservations=88`, `nightly_inventory=8799`.
- Run 2 copied DB counts: identical.
- Run 2 stdout: completed successfully; `Guesty writes=0`.
- Run 2 stderr: empty.

## Files changed by this improvement

Files changed for this replay fix:

```text
src/eval/replay.py
src/features/__init__.py
tests/test_replay.py
docs/reports/replay/audit_1/FINDINGS.md
docs/reports/replay/improvement_1/CHANGES.md
```

The worktree also contains pre-existing unrelated changes under `docs/operator_surface/`, `src/memory/`, `src/receipt/`, `pyproject.toml`, and an existing `src/compose/__init__.py` modification. Those were not touched by this improvement. No commit, merge, or push was performed.

## Performance

Run 2 took approximately 22m33s and remained CPU-bound. No optimization was applied before independent verification; changing execution order or caching before Audit 2 would risk changing the result. Performance remains an S3 item for Improvement 2, subject to an identical-output proof.
