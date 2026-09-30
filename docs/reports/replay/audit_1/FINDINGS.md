# Phase 1 — independent audit of point-in-time replay

Date: 2026-09-29  
Branch/HEAD: `feature/point-in-time-replay` / `f5918117d18d0fa56e69e1d862646338ddeb688b`  
Window audited: 2026-09-20 through 2026-09-29; properties `summit_haus`, `overlook_ridge`, `cloud_9`; horizon 365; censor 2026-09-29.

This phase was read-only against `data/wp_pricing.db` (a symlink to `/Users/jacobpfeifer/Library/Application Support/wp-price/data/wp_pricing.db`). No replay code, policy, elasticity parameters, or operator data was changed. The only Phase 1 artifact created is this file.

## 1. Root cause of 0/52

The zero is caused by panel selection before labeling, not by a failed date join.

The path is:

1. `src/eval/replay.py:195-203` calls `generate_recommendations(..., persist=False, allow_past=True, as_of=d)`.
2. `src/features/__init__.py:159-166` builds features from the current `nightly_inventory` table, not a historical inventory snapshot.
3. `src/compose/__init__.py:247-251` returns no recommendation unless the feature status is `available`; `booked` and `blocked` are omitted because `include_booked` is not passed.
4. `src/compose/__init__.py:711-717` drops every `None` recommendation.
5. Only after that, `src/eval/replay.py:205-236` looks up the current inventory row by `(property_id, stay_date)`, copies `booked_at`, and computes `booked_by_censor`.

The lookup itself is an exact key lookup: `_outcomes()` at `src/eval/replay.py:129-137` selects `nightly_inventory` for one property and maps `stay_date`; the replay then does `outcomes.get(sd)` at lines 215-216. There is no reservation join in the replay. `property_id` values and ISO `stay_date` values match the inventory schema. The three booked sample rows below have valid `booked_at` values and reservation IDs, but have no CSV row because they were excluded at step 3.

`parse_date()` at `src/utils.py:9-14` intentionally takes `str(value)[:10]`, so values such as `2026-09-01T21:01:26.480Z` parse as `2026-09-01`. The censor comparison at `src/eval/replay.py:217-219` therefore works for the observed ISO timestamps. This truncates UTC timestamps to a calendar date, which is acceptable only if the label contract is date-granular; it is not the cause of the zero here.

Status semantics are explicit in `src/db/schema.sql:80-98`: `available`, `booked`, and `blocked`. `recommend_night()` treats only `available` as priceable. The current table contains 305 `booked` rows, 304 with `booked_at`, plus 175 blocked rows. For the three target properties and stay dates through the censor, there are 193 booked nights and 42 blocked nights.

Three concrete booked nights:

| Property/date | Raw inventory evidence | Replay CSV | Why absent |
|---|---|---|---|
| `cloud_9` / 2026-09-25 | `status=booked`, `booked_at=2026-09-01T21:01:26.480Z`, reservation `6a973bef2a15218917fc6a60` | no match | `recommend_night()` refuses current `booked` status |
| `cloud_9` / 2026-09-26 | `status=booked`, same booking timestamp/reservation | no match | same |
| `cloud_9` / 2026-09-29 | `status=booked`, `booked_at=2026-09-21T20:42:25.248Z`, reservation `6ab176e2f21da911b3527be6` | no match | same |

The existing CSV has 9,644 rows, 52 resolved rows, and `booked_by_censor=false` on all 9,644 rows. The 52 resolved rows all have an empty `booked_at`. Thus the join/parse path is not observing a zero outcome; the booked population has already been selected out.

## 2. Selection bias and exclusion counts

For each decision day, the current inventory contains 1,095 target-property nights in `D+1..D+365`. The emitted count equals the `available` count. The remainder is silently excluded by status:

| Decision day | Available/emitted | Excluded booked | Excluded blocked | Total candidate nights |
|---|---:|---:|---:|---:|
| 2026-09-20 | 955 | 123 | 17 | 1,095 |
| 2026-09-21 | 957 | 121 | 17 | 1,095 |
| 2026-09-22 | 959 | 119 | 17 | 1,095 |
| 2026-09-23 | 961 | 117 | 17 | 1,095 |
| 2026-09-24 | 963 | 116 | 16 | 1,095 |
| 2026-09-25 | 966 | 113 | 16 | 1,095 |
| 2026-09-26 | 969 | 110 | 16 | 1,095 |
| 2026-09-27 | 972 | 110 | 13 | 1,095 |
| 2026-09-28 | 972 | 110 | 13 | 1,095 |
| 2026-09-29 | 970 | 109 | 13 | 1,092 |

The last day has 1,092 rows because the target properties do not all have 365 current inventory rows through 2027-09-29. The replay output counts by day sum to exactly the available/emitted column. There is no recorded exclusion reason in `ReplayResult` or the CSV; the table above is an independent reconstruction from raw SQL and the code path.

The selection is additionally not point-in-time: `build_features_for_property()` reads current `nightly_inventory`, while `pacing_snapshots` supplies the decision-day listed price. A night that was available on D but booked later can be absent from the replay because its current status is now `booked`.

## 3. Label definition

The implemented label is `booked_at is not null and date(booked_at) <= censor`, irrespective of decision day or stay date (`src/eval/replay.py:216-219`). `resolved` is separately defined only as `stay_date <= censor` (`src/eval/replay.py:233`). The scorer uses `resolved` and `booked_by_censor` (`src/eval/replay.py:264-297`).

That is not apples-to-apples for a terminal probability. For a decision made on day D for stay date S, the correct resolved label is:

`booked between D (exclusive) and min(S, censor) (inclusive)`.

In timestamp terms the implementation must use the booking confirmation timestamp and a clearly stated timezone/date boundary. A booking already known at D is not a new booking event for that decision. For S after the censor, the observation is unresolved unless the censor is at or after S; a booking by the censor is useful as an interim event count, but not a terminal “books by check-in” negative.

The current implementation can also assign the same final `booked_at <= censor` outcome to every repeated decision for a night, even for decisions after the booking. That makes the per-decision panel unsuitable without an explicit already-booked exclusion and a separate count.

## 4. Nights booked on decision day

These must be excluded from the “will it book?” panel and reported separately. The current implementation does neither explicitly; most are silently absent because status is already `booked`.

Using current inventory as an audit diagnostic, the target candidate population splits as follows:

| D | Booked with `booked_at <= D` | Booked after D | Blocked | Available |
|---|---:|---:|---:|---:|
| 2026-09-20 | 108 | 15 | 17 | 955 |
| 2026-09-21 | 111 | 10 | 17 | 957 |
| 2026-09-22 | 111 | 8 | 17 | 959 |
| 2026-09-23 | 111 | 6 | 17 | 961 |
| 2026-09-24 | 110 | 6 | 16 | 963 |
| 2026-09-25 | 113 | 0 | 16 | 966 |
| 2026-09-26 | 110 | 0 | 16 | 969 |
| 2026-09-27 | 110 | 0 | 13 | 972 |
| 2026-09-28 | 110 | 0 | 13 | 972 |
| 2026-09-29 | 109 | 0 | 13 | 970 |

This is not a historical as-of truth because the source table is current; it is evidence of the size and direction of the selection problem. A corrected replay must use an as-of-safe booking source and distinguish `already_booked_at_D`, `booked_after_D`, `unbooked_resolved`, and `unresolved`.

## 5. Data adequacy and recoverability

Raw SQL facts:

- `pacing_snapshots` has 26 distinct `as_of` days: 2026-08-18 through 2026-09-01 (15 consecutive days), 2026-09-03, and 2026-09-20 through 2026-09-29 (10 consecutive days).
- The gap is 2026-09-04 through 2026-09-19; 2026-09-02 is also absent. The clean run correctly uses the 10 consecutive September days rather than stitching across the gap.
- `reservations` has 88 rows, `confirmed_at` from `2026-05-12T01:50:31.518Z` through `2026-09-25T17:06:07.420Z`, check-ins from 2026-05-20 through 2027-10-24. There are 48 `confirmed` and 40 `inquiry` rows.
- `nightly_inventory` has 8,799 rows, 304 non-null `booked_at` values, and 8,495 nulls. All 304 non-null values match a reservation's `confirmed_at` date and have a reservation ID. The 304 are associated with 46 distinct `confirmed` reservations; the 40 inquiry rows do not account for the booked-at population.
- Every non-null `booked_at` row has `updated_at` on 2026-09-28, while booking timestamps range from May through September. This demonstrates that the current inventory was refreshed/backfilled later; it does not demonstrate that the historical booking state was recorded live on each decision day.

The early 2026-08-18–09-03 block is usable as a separate labeled window only for nights whose as-of inputs and outcome history meet the same point-in-time requirements. It is not safe to stitch across the gap, and the current `nightly_inventory` table cannot recover historical availability/status or prove what was known on each missing day. The reservations table can support booking-event labels where `confirmed_at` is trustworthy, but it does not repair missing decision-day price/signal snapshots.

## 6. The 21 `listed_source=none` rows

They are all future, unresolved 2027-09-22 through 2027-09-26 rows with no non-null `listed_price` in the matching decision-day `pacing_snapshots` row:

| Decision day | Dates/properties |
|---|---|
| 2026-09-22 | all three properties on 2027-09-22 (3) |
| 2026-09-23 | all three properties on 2027-09-22 and 2027-09-23 (6) |
| 2026-09-24 | all three properties on 2027-09-22, 2027-09-23, 2027-09-24 (9) |
| 2026-09-26 | all three properties on 2027-09-26 (3) |

They are not join failures or booked rows. The replay explicitly marks them `listed_source=none` at `src/eval/replay.py:212-230`, increments `used_current_listed`, and does not populate `listed_as_of` from the current inventory. The provenance note at lines 238-243 is misleading for this case because the code does not actually use today’s price in this replay row; it says those nights are not silently repaired, which is the safe behavior, but the wording should be made exact in a later phase.

## 7. The 8-vs-12 test discrepancy

The branch contains exactly eight `test_*` functions in `tests/test_replay.py` (lines 44, 54, 65, 71, 99, 117, 125, and 167). `git log --all -- tests/test_replay.py src/eval/replay.py` has only commit `f591811` and no earlier or alternate branch version with four additional replay tests. The discrepancy is therefore not four tests lost from this repository history; the four were never present in the reachable history inspected. No tests were fabricated in Phase 1.

## 8. Test coverage gaps

The existing eight tests cover basic scoring floors, revenue labeling, refusal when `rate_changes` contains an applied Guesty write, an empty decision window, report writing, and a bookprob lookahead case. They do not cover:

- selection of current `available` versus `booked` versus `blocked` rows;
- inclusion of booked-after-D outcomes and exclusion/reporting of already-booked-at-D nights;
- the exact interval `(D, min(S, censor)]` or timezone boundary behavior;
- labels sourced from reservations versus `nightly_inventory` and mismatched/missing keys;
- per-property/per-decision-day resolved, unresolved, excluded, or reason counts;
- repeated decisions for one night and effective sample size/deduplicated scoring;
- the 21 missing as-of listed prices and exact provenance wording;
- audit agreement between CSV labels and independent SQL recomputation;
- reservation/status semantics (`confirmed`, `inquiry`, `blocked`);
- the gap between pacing snapshot days and non-stitchable windows;
- performance or preservation of results under any safe optimization.

The Guesty refusal test exists (`tests/test_replay.py:99-115`) and should remain unchanged in substance.

## 9. Performance

The 10-day run took about 23.1 minutes at approximately 99% CPU. The top three evident costs are:

1. `src/eval/replay.py:195-203` recomputes the complete 365-day recommendation set for every decision day; there are 9,644 emitted decisions, so this is inherently a large repeated workload.
2. `src/features/__init__.py:149-166` rebuilds event demand, orphan-gap analysis, and SQL feature rows per property and per day rather than reusing read-only inputs.
3. `src/eval/replay.py:205-207` rereads the full current inventory outcome map for each property on every decision day, while the composer performs many per-night DB-backed model/guardrail calculations and a 40-step price grid (`src/compose/__init__.py:255-258`, `134-147`).

No profiler was run in Phase 1 and no performance change is proposed yet. Any optimization must first prove byte-for-byte or field-for-field identical output on a small window.

## 10. Other result distortions

- **Lookahead risk:** signal observations are guarded by `assert_no_lookahead` at `src/eval/replay.py:190-193`, and the bookprob code has an as-of filter. However, the replay reads current `nightly_inventory` features/status and current outcome rows, not historical calendar vintages. This is the principal remaining data-plumbing lookahead/selection risk.
- **Listed-price fallback/provenance:** missing as-of listed prices are marked `none`; they must not be treated as market observations. The 21 rows should be excluded from direction/revenue comparisons or carried with an explicit missing-reference status.
- **Terminal versus censor label:** the current calibration uses a terminal prediction against a censor-date label, even though `resolved` only checks stay date. The score is not valid for a future stay that has not reached check-in.
- **Repeated decisions:** one stay night appears on multiple decision days. Counting rows inflates N and violates independent-night intuition; the current scoring functions have no deduplicated view or effective sample-size warning.
- **Revenue counterfactual:** `estimate_revenue()` is explicitly a price swap holding bookings fixed (`src/eval/replay.py:321-348`), so it cannot establish causal lift. It is not a rigged causal claim, but its demand-model row can look like a result if read without the assumption.
- **Status versus reservation evidence:** `nightly_inventory.status` is a current calendar state; it is not itself a historical booking event. `reservations.confirmed_at` is the stronger event source for labels, but inquiry rows and historical snapshot completeness need explicit policy.
- **Small sample:** the combined resolved panel is 52 selected night-decisions, below 20 per property (17/17/18), and all 52 are unbooked after the selection problem. The nominal combined calibration floor is crossed but the sample is not representative.

## Ranked defects and proposed fixes

### S1 — Panel selection and label/scoring contract are wrong

**Evidence:** `src/compose/__init__.py:247-251`, `711-717`; `src/eval/replay.py:205-236`, `264-297`; 193 booked target nights through the censor versus zero booked CSV labels.  
**Fix:** build an as-of-safe candidate/outcome panel independent of whether the current engine still emits a recommendation; label each decision with bookings in `(D, min(S, censor)]`; classify already-booked-at-D separately; score only resolved, not-already-booked decisions. Use reservations/confirmation timestamps where available and state limitations where historical inventory cannot be reconstructed.  
**Risk:** changing the panel changes N and all metrics; stale/backfilled data may still make some labels untrustworthy.  
**Test:** synthetic four-night fixture containing booked-before-D, booked-after-D-before-censor, never-booked resolved, and future-unresolved nights; assert exact inclusion, exclusion reason, label interval, per-day/per-property counts, and no lookahead.

### S1 — Replay reads current inventory state as if it were decision-day state

**Evidence:** `build_features_for_property()` reads `nightly_inventory` directly (`src/features/__init__.py:159-166`); current rows have `updated_at=2026-09-28` despite booking dates as early as May.  
**Fix:** use historical pacing/status snapshots or an explicitly constrained reservation/event reconstruction; never silently substitute current status for historical as-of status.  
**Risk:** some historical states are unrecoverable; correct output may be smaller or unmeasurable.  
**Test:** mutate current status after D in a fixture and assert the D panel/label does not change; assert missing historical state is reported rather than inferred.

### S2 — No explicit unresolved/already-booked/excluded accounting or deduplicated effective N

**Evidence:** `ReplayRow` has only `resolved` and `booked_by_censor` (`src/eval/replay.py:51-64`); score functions count rows, not unique `(property_id, stay_date)` nights (`264-318`).  
**Fix:** add explicit outcome/exclusion categories, per-property/per-decision-day counts, and a per-night deduplicated view plus an inflation warning. Keep calibration floor 20 and direction floor 5.  
**Risk:** report schema changes and lower effective N can make calibration unmeasurable, which is the honest outcome.  
**Test:** repeated decisions for one night produce inflated per-decision N but one deduplicated night and a warning; floor behavior remains unchanged.

### S2 — Reservation/event semantics are not enforced in replay

**Evidence:** replay reads only `nightly_inventory.booked_at` (`src/eval/replay.py:129-137`, `215-219`) and never joins reservations; database contains confirmed and inquiry reservations.  
**Fix:** define the authoritative booking event and status policy; join or precompute an as-of-safe event map, preserving missing/ambiguous evidence as unknown.  
**Risk:** inquiry/confirmed discrepancies may reduce usable labels.  
**Test:** reservation-only, inventory-only, conflicting, missing timestamp, and timezone-boundary fixtures.

### S3 — Missing listed-price provenance is imprecise and may contaminate comparisons

**Evidence:** 21 `listed_source=none` rows; `price_ref_note` wording at `src/eval/replay.py:238-243` refers to using today’s price although the row leaves `listed_as_of` null.  
**Fix:** make provenance exact and exclude missing-reference rows from reference-based metrics with explicit counts.  
**Risk:** direction/revenue N decreases.  
**Test:** fixture with missing pacing price asserts `listed_source=none`, exclusion from comparisons, and exact HTML/JSON provenance.

### S3 — Performance is unnecessarily repeated

**Evidence:** repeated full recommendation generation and per-property inventory reads described in §9.  
**Fix:** only after correctness is fixed, cache immutable read-only inputs or batch safe queries; compare outputs on a small window before/after.  
**Risk:** caching can introduce lookahead or alter ordering; correctness takes priority.  
**Test:** identical serialized rows and score objects before/after on a fixture, plus a profile showing improvement.

## Command log

All commands below exited 0 and were read-only, except the creation of this report directory/file.

```text
sed/rg inspection of src/eval/replay.py, src/compose/__init__.py, src/features/__init__.py,
  src/utils.py, tests/test_replay.py, schema, and prior replay reports
sqlite3 URI mode=ro diagnostic queries against data/wp_pricing.db
git log --all -- tests/test_replay.py src/eval/replay.py
rg '^def test_' tests/test_replay.py
```

The prior run's recorded command and exit code are preserved in `docs/reports/replay/REPLAY_TECHNICAL_LOG_2026-09-29.md`: replay exit 0, Guesty writes 0, 9,644 rows, 52 resolved, Brier 0.575.

## Phase gate

Phase 1 is complete. The ranked list above is the stop point required by the request. No Phase 2 code or test changes have been made.
