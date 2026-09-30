# Phase 4 — independent verification of Improvement 1 / Run 2

Date: 2026-09-29  
Artifact audited: `docs/reports/replay/run2/replay_2026-09-29.{csv,json,html}`  
Raw DB audited: `docs/reports/replay/run2/operator_copy.db` (read-only)  
Method: separate Python/SQLite script using `csv`, `sqlite3`, `datetime`, and manual SQL/event expansion; it did not import `src.eval.replay`.

## 1. Independent label recomputation

The independent script built an event map from `reservations` where `status='confirmed'` and `confirmed_at IS NOT NULL`, expanded each reservation over `[check_in, check_out)`, and used `nightly_inventory.booked_at` only when no reservation event existed. For each CSV row it applied:

`S <= censor`, booking date `> D`, and booking date `<= min(S, censor)`.

It selected 20 resolved rows with deterministic seed `20260929`. All 20 agreed with the CSV; disagreements: **0**.

| Sample result | Count |
|---|---:|
| Resolved rows checked | 20 |
| Label disagreements | 0 |
| Hand-true labels | 1 |
| Hand-false labels | 19 |

The one sampled positive was `summit_haus / 2026-09-22`, decision `2026-09-20`, confirmed `2026-09-21T18:36:14.092Z`. The remaining sampled events were either absent or outside the valid interval.

Ten booked nights were independently sampled from target-property `nightly_inventory` rows with `status='booked'`, `stay_date <= 2026-09-29`. All ten had no CSV row, which is correct for this replay panel because their pacing status was already `booked` before the clean decision window. The raw samples included `overlook_ridge` 2026-06-29, 2026-06-10, 2026-07-13, 2026-09-21, 2026-07-31, and 2026-08-15; `summit_haus` 2026-09-01, 2026-06-17, and 2026-08-09. No booked night was silently labeled as an unbooked scored row.

The 14 booked target-property nights from 2026-09-21 through 2026-09-29 explain as follows:

- 4 had a pacing `available` state before their booking event and produced 4 positive decision labels (three Summit nights and Cloud 9 on 2026-09-29; the three Summit nights are repeated outcomes across decisions but are not deduplicated positives).
- 10 were already `booked` in the first clean-window pacing snapshot or had booked before it, so they were excluded as already-booked rather than scored as negatives.

This is plausible and materially different from the original 0/52 selection artifact. It does not claim that four positives are a season-sized sample.

## 2. Independent Brier and calibration

The independent script scored the 77 CSV rows with `resolved=True`, non-null `outcome_label`, and non-null `expected_book_prob`.

```text
eligible = 77
Brier = 0.5507698946816132
```

Independent buckets:

| Predicted interval | N | Mean predicted | Observed rate |
|---|---:|---:|---:|
| 0–20% | 26 | 0.0895997778 | 0.1153846154 |
| 60–80% | 7 | 0.7033623517 | 0.0000000000 |
| 80–100% | 44 | 0.9083037197 | 0.0227272727 |

These match the engine JSON exactly. The deduplicated view has 17 eligible nights and Brier `0.37603137864251807`, so it is correctly marked unmeasurable under the unchanged 20-night floor. The repeated-decision warning is real.

## 3. Independent lookahead check

For all ten decision days, the replay CSV’s `listed_source=pacing` values were checked against the exact `(as_of, property_id, stay_date)` pacing row; the missing-price rows were checked to have `listed_price IS NULL`. No listed price was sourced from a later snapshot.

The raw signal table has 7,237 `signal_observations`, with `observed_at` range 2025-07-28 through 2026-09-03. For every sampled decision day 2026-09-20 through 2026-09-29, the latest raw observation with `observed_at <= D` was 2026-09-03; there were no observations after any of those decision days. The replay’s `assert_no_lookahead` also passed in the run. This verifies the timestamp gate for this dataset, while noting that the later September decision days have no newer signal vintages.

## 4. Guesty guard

The existing refusal test remains present at `tests/test_replay.py:99-115`; it inserts an applied `guesty` rate change and asserts `GuestyWriteForbidden`. It passed in the touched suite. Run 2 stdout reports `Guesty writes=0`; raw SQL on both original and copied DBs reports `rate_changes=0`.

## 5. Run 2 integrity and plausibility

- Original DB SHA-256 before and after: `12918aff638ef16b4a08aaa3e4b86a9d9bbfab786aa5db2c9ab4fcdffeba42e3`.
- Original counts before and after: `rate_changes=0`, `pacing_snapshots=32170`, `reservations=88`, `nightly_inventory=8799`.
- Run 2 copy counts: identical.
- Run 2 completed with exit 0; stderr was empty.
- Run 2: 9,736 logged decisions, 77 resolved scored decisions, 4 booked labels, Brier 0.551.
- Panel accounting reports per-property resolved decisions: Cloud 9 24, Overlook Ridge 28, Summit Haus 25. Per-property calibration remains below 20 only after deduplication; the pooled per-decision score crosses the floor because repeated nights inflate N.

## Remaining defects, ranked

### S2 — Current pacing status is a proxy, not a fully historical booking ledger

Improvement 1 correctly stopped using current inventory status for the replay panel and uses decision-day pacing status. However, the DB has no complete historical reservation/status snapshot for every decision day. The 10 booked nights excluded from the clean window are plausibly already booked, but the replay cannot prove every historical state beyond the available pacing rows. A future shadow-record stream should preserve daily as-of state and confirmation events.

### S2 — Exclusion categories are in aggregate accounting, not materialized rows

Already-booked and blocked nights are counted in `panel_counts` but do not have CSV rows with `exclusion_reason`. This prevents a row-level audit trail for every excluded candidate. The aggregate contract is met, but a future improvement should export an exclusions CSV or explicit row records.

### S2 — Reservation fallback policy needs operational documentation

The replay uses confirmed reservations as the primary event source and `nightly_inventory.booked_at` as a legacy fallback. This is safe for the observed data (all 304 timestamps map to confirmed reservations), but the policy for cancellations, inquiry rows, timezone boundaries, and missing reservation IDs should be explicit in the operator contract.

### S3 — Effective sample size remains too small for a model claim

The pooled per-decision panel has 77 resolved rows, but only 17 deduplicated nights. Per-property deduplicated samples are below the 20-night calibration floor. The Brier result is descriptive only.

### S3 — Runtime remains about 22.5 minutes

Run 2 remains CPU-bound and did not receive an optimization before this audit. Any optimization must be accompanied by identical-output proof on a small window.

No S1 defect remains, and no disagreement was found between the independent hand recomputation and the CSV.

## Independent command evidence

The independent SQL/CSV script used:

```text
sqlite3 URI mode=ro against docs/reports/replay/run2/operator_copy.db
csv.DictReader on docs/reports/replay/run2/replay_2026-09-29.csv
manual date arithmetic for (D, min(S, censor)]
random.seed(20260929)
```

It did not call replay scoring functions. Phase 4 is complete; the remaining work is Improvement 2 / Run 3 and final audit.
