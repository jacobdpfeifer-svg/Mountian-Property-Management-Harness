# Final audit — point-in-time replay

Date: 2026-09-29  
Branch: `feature/point-in-time-replay`  
HEAD: `f5918117d18d0fa56e69e1d862646338ddeb688b`

## Two-minute owner summary

The first replay looked informative but was measuring the wrong group. It only scored nights the engine could still price in the current calendar. Nights that had already booked were removed before scoring, which is why it reported 0 booked outcomes even though the database contained booked nights.

The replay now reconstructs the candidate panel from the decision-day pacing snapshot, uses confirmed booking events in the interval after the decision and before check-in/censor, excludes already-booked nights as a separate category, and reports unresolved/blocked/excluded counts. It also warns when repeated decisions on the same stay night inflate the sample and provides a deduplicated view.

The corrected clean-window run found 4 booked outcomes among 77 resolved decision rows, with a descriptive per-decision Brier score of 0.551. After deduplication, only 17 distinct resolved nights and 4 positive booking events remain. Because the unchanged floors now apply to distinct nights and positive events, clean-window calibration is unmeasurable, not a measurable result.

The engine has not been proven to beat the market. The revenue rows are price swaps under fixed-booking assumptions, not causal experiments. More daily shadow-record data is required.

## Three-run comparison

| Run | Decision window / censor | N decisions | Resolved | Booked | Distinct nights / positives | Calibration | Brier (descriptive) | Direction | Revenue rows |
|---|---|---:|---:|---:|---:|---|---:|---|---:|
| Original | Sep 20–29 / Sep 29 | 9,644 | 52 | 0 | not reported / 0 | No — biased panel | 0.575 | Above 0%; below 0% | 9,623 |
| Run 2 | Sep 20–29 / Sep 29 | 9,736 | 77 | 4 | 17 / 4 | **No** — both floors fail | 0.551 | Above 0%; below 7.1% | 77 |
| Run 3 | Sep 20–29 / Sep 29 | 9,736 | 77 | 4 | 17 / 4 | **No** — both floors fail | 0.551 | Above 0%; below 7.1% | 77 |
| Early separate run | Aug 18–Sep 3 / Sep 29 | 15,257 | 1,105 | 344 | 78 / 22 | Yes, per decision and deduplicated | 0.247 | Above 25.3%; below 33.3% | 1,105 |

Run 2 and Run 3 CSV outputs are byte-identical, and their HTML outputs are byte-identical. Run 3 JSON additionally contains the row-level exclusion ledger; metrics and decision rows are unchanged. Run 3 has 1,190 total exclusion records: 1,113 already-booked and 77 blocked; no recommendation was missing for a pacing candidate.

The early run used the same censor, 2026-09-29, and is a separate column/window only. The missing days remain visible: no Sep 3–20 stitching was performed. No further full replay was launched after this early run.

## What is proven

- The original 0/52 result was a selection artifact: current `booked`/`blocked` rows were excluded before labeling.
- Decision-day pacing status and listed prices are now used when available; current mutable inventory is not used as the replay panel state.
- The label is explicit: booking event after D and on or before `min(S, censor)`; already-booked-at-D is excluded.
- Independent raw SQL/event recomputation of 20 resolved rows found 0 disagreements with the Run 2 CSV.
- Independent Brier recomputation exactly matched 0.5507698946816132 and matched all calibration buckets.
- Repeated-night inflation exists: 77 per-decision eligible rows reduce to 17 distinct nights and 4 positive events.
- The stricter calibration gate applies the unchanged 20-night floor to distinct nights and the unchanged 5-observation floor to positive events; clean Run 3 is therefore unmeasurable.
- Guesty writes stayed at 0. The refusal test remains present and passed.
- Original operator DB checksum and counts were unchanged before/after both monitored runs.

## What is suggestive

- The corrected clean window has some real post-decision bookings (4 labels), unlike the original selected panel.
- The separate early block has more resolved data and 78 deduplicated eligible nights, so it is more measurable as a descriptive calibration window.
- In both corrected clean runs, the direction comparison is 0% above versus 7.1% below, but the sample is too small and observational to infer pricing causality.

## What remains unknown

- Whether the engine beats the market. No randomized or otherwise causal price comparison exists; revenue rows hold bookings fixed or use the model’s own demand assumptions.
- Whether all historical status states are recoverable. Pacing snapshots are sparse, and `nightly_inventory` was refreshed later than many booking timestamps.
- Whether the predicted probabilities are calibrated for a full ski season. The clean-window independent N is only 17 nights.
- Whether cancellations would change future labels. The replay includes only `reservations.status='confirmed'` events and has no canceled reservation rows in this DB; a later cancellation after confirmation is not independently modeled. This is a label-validity limitation, not proof that cancellations cannot occur.
- Whether `nightly_inventory.booked_at` was live-recorded at booking time. All 304 non-null timestamps match confirmed reservation timestamps, but every row has `updated_at=2026-09-28` while booking dates range back to May. That is consistent with a later import/backfill and does not prove live recording. Confirmed reservation events are primary and inventory timestamps are fallback, but historical as-of validity remains partly unverified.
- Whether inquiry/timezone policies would change future labels. Inquiry rows are not used as confirmed booking events, and timestamp date truncation is date-granular; these policies need operational documentation.

## Data minimum and next steps

The hard technical floors remain 20 distinct resolved nights and 5 positive booking events for calibration, plus 5 observations per direction group. Run 3 has only 17 distinct resolved nights and 4 positives, so it does not meet the floors. Those floors are not sufficient for a season claim or a market-beat claim; this run provides no defensible power calculation for a larger statistical minimum.

The minimum operational next step is daily `wp-price shadow-record` from now through a complete ski season, preserving the decision-day calendar, listed price, signals, booking confirmation event, and status. Do not stitch across missing days. Re-run only when enough unique nights have checked in, and report both per-decision and deduplicated results.

## Integrity attestations

- Guesty writes: **0** in original, copied Run 2, copied Run 3, and early-window databases; `rate_changes` remained empty.
- Original DB SHA-256 before and after: `12918aff638ef16b4a08aaa3e4b86a9d9bbfab786aa5db2c9ab4fcdffeba42e3`.
- Original counts before/after: `rate_changes=0`, `pacing_snapshots=32170`, `reservations=88`, `nightly_inventory=8799`.
- No `assert_no_lookahead` failures occurred. Independent raw checks found signal observations no later than 2026-09-03, hence no signal vintage after the Sep 20–29 decision days.
- Replay suite: **10 passed**.
- Broader touched suite: **56 passed**.
- Full repository suite: **321 passed, 3 failed, 1 deselected** in the working tree. A clean detached checkout of `f591811` reproduced the two failures present in that commit (`6 passed, 2 failed` in `tests/test_memory.py`); the third failing test exists only in the current uncommitted `tests/test_memory.py` and is absent from `f591811`. The clean replay suite was **8 passed**. No memory files were modified for this task.
- No commit, merge, or push was performed.

## Remaining defects

1. **S2:** Historical status is still limited by sparse pacing snapshots and cannot reconstruct every missing day.
2. **S2:** Reservation fallback policy for inquiries, cancellations, missing IDs, and timezone boundaries needs an operator contract.
3. **S3:** Runtime remains about 22.5 minutes for the clean 10-day window; no safe optimization was applied without an identical-output proof.
4. **S3:** Even the corrected clean-window deduplicated sample is below the calibration floor.

The clean-window decision count increased from 9,644 to 9,736 (+92) because Run 3 uses decision-day `pacing_snapshots` to determine availability. The original run used current mutable `nightly_inventory` state, which excluded nights that were booked now even when they were available on the historical decision day. This is a panel-definition change, not fabricated data or engine tuning.

## Deliverables

- Phase 1: `docs/reports/replay/audit_1/FINDINGS.md`
- Improvement 1: `docs/reports/replay/improvement_1/CHANGES.md`
- Run 2: `docs/reports/replay/run2/`
- Phase 4: `docs/reports/replay/audit_2/FINDINGS.md`
- Improvement 2: `docs/reports/replay/improvement_2/CHANGES.md`
- Run 3: `docs/reports/replay/run3/`
- Separate early window: `docs/reports/replay/run_early/`
- Final audit: `docs/reports/replay/audit_3/FINAL.md`
