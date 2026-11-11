# Independent test audit — profitability, shadow, model, and canary

Date: 2026-10-20. Auditor role: independent QA, data integrity, and safety. No product code was changed. No Guesty call was made. No frozen register or decision ledger in the repository was edited.

HEAD at audit start: `bcef02b03a3bb8a3a58b5b21d4d71cc67f156db6`. The profitability work is uncommitted. `load_register` accepts `docs/reports/final_delivery/experiments/EXP-PACE-V3-001.register.json`. Its `register_sha256` is `302a3b51dbe6f72d90daf6232ad417fa51d699a9bd0a332e10736932227b9115`, `frozen_at` is `2026-10-20T16:41:18+00:00`, and `git_commit` matches HEAD. The last V3 ledger row is `screen_decision` / `REWORK` at `2026-10-20T16:49:14+00:00` with the same register hash. There is no `evaluation_opened` and no `ADVANCE_TO_EVALUATION` for V3.

There is no symbol `REALIZED_OWNER_NET_MEASURED`. The nearest labels are `property_month` `result_label == "settled"` and the canary packet status `READY_FOR_HUMAN_AUTHORIZATION`.

Realized owner net is not claimed. The read-only spine at `data/profitability_readonly.db` (gitignored) has 78 reservation versions, 159 pending ledger lines, 52 reversed ledger lines, 0 settled lines, 0 owner statements, 2 `INCONSISTENT` quarantines, and 0 shadow runs.

## Commands run

| Command | Result |
|---|---|
| `git status`, `git diff --stat`, `git rev-parse HEAD` | Dirty tree recorded above. 14 tracked files changed, 869 insertions. |
| `.venv/bin/python -m pytest -q tests/data_spine tests/test_shadow_mode.py tests/test_shadow.py tests/security/test_canary.py tests/security/test_canary_readiness.py tests/security/test_canary_packet.py tests/security/test_controls.py tests/security/test_experiments.py tests/security/test_experiment_scripts.py tests/security/test_webhook_ingress.py tests/platform_ops/test_orchestration_observability.py tests/platform_ops/test_scan_repo.py` | 192 passed in 3.79s |
| `.venv/bin/python scripts/quality_gates.py` | Exit 0. Pytest 1115 passed, 3 deselected, coverage 80.78%. Vulture clean. `uv pip check` clean. `pip_audit` reported no known vulnerabilities (local package `wp-str-pricing` skipped). mypy: no issues in 166 files. |
| `.venv/bin/python scripts/scan_repo.py` | `scan_repo: 0 problem(s)`, exit 0 |
| Temporary-database probes against the installed library | Results below. Probes used `init_db` + `apply_migrations` and did not write the repository. |

`docs/reports/profitability/FINAL_PROFITABILITY_GATE.md` says quality gates were 1113 passed and coverage 80.83%. This run is 1115 passed and 80.78%. The newer untracked tests are in the 1115. That doc count was not reproduced.

No command was blocked by a lock, a missing credential, or a missing local dependency. Live settlement evidence is absent; that limits profitability measurement, not the safety conclusion about writes.

## 1. Verified passing controls

These were executed in this audit.

**Ingestion rejects the cases that the contract can see.**

- Unknown property `not_a_home` quarantined `UNKNOWN_IDENTITY:property_id`. Accepted 0. `src/data_spine/contracts.py` lines 146–148.
- Market price basis `unknown` quarantined `AMBIGUOUS_PRICE_BASIS`. Accepted 0.
- Naive `source_updated_at` (`2026-11-15T12:00:00` with no timezone) quarantined `BAD_TIMESTAMP`. Accepted 0.
- A reservation carrying guest email, phone, street address, a 16-digit card number, and a listing id was accepted as a stay, and none of those values appear in the SQLite dump. `validate` keeps only declared fields (`contracts.py` lines 142–143).
- A reservation whose price basis is `nightly_ex_fees` quarantined `AMBIGUOUS_PRICE_BASIS` (`contracts.py` lines 166–167).
- A ledger line with neither `reservation_key` nor `statement_key` quarantined `UNLINKED_MONEY` (`contracts.py` lines 183–185).
- Re-importing the same payout with only `observed_at` changed was a duplicate (accepted 0, duplicates 1). `content_hash` ignores `observed_at` (`src/data_spine/ingest.py` lines 60–63).
- The same payout key with a later `source_updated_at` became version 2 and superseded version 1. Current rows keep one version of that key.
- A statement reissue (`reported_owner_net` 100, then 500) kept both versions. `reconcile_statement` used the current reported value 500 against a computed 500 and returned `reconciled`.
- A ledger line whose property is `summit_haus` attached to an `overlook_ridge` statement was accepted at ingest and then failed reconciliation with `statement includes another property's ledger lines` (`owner_net.py` lines 491–492).
- Guesty pending lodging plus accounting lodging for the same stay produced owner net 270, equal to the accounting lines only (400 − 80 − 50). PMS lines were dropped (`owner_net.py` lines 65–78).

**Five hand-calculated stays matched to the cent.** Formula used by the code: economic credits minus economic debits. Taxes and `owner_payout` are outside that sum. Allocated system cost is a separate hurdle, not a debit.

| Stay | Input | Expected | Observed | Status |
|---|---|---|---|---|
| Short expensive Airbnb, 2 nights | 2400 lodging + 180 retained guest fee − 360 channel − 72 payment − 480 management − 300 cleaning − 40 consumables | 1328 | 1328 | `actual` |
| Long direct, 14 nights | 4200 − 630 management − 180 cleaning; no channel fee | 3390 | 3390 | `actual`; channel fees `not_applicable` |
| Full refund | 1200 − 180 − 240 − 200 − 1200 refund | −620 | −620 | `actual` |
| Partial refund after a 300 payout | 1000 − 150 − 200 − 150 − 200 refund; payout excluded | 300 | 300 | `actual`; payout absent from components |
| Missing management terms | 900 − 135 channel − 150 cleaning; no management line | not `actual` | total 615, status `incomplete`, management field `missing` | `incomplete` |

Also matched: taxes of 80 collected and 80 remitted left direct-stay net at 540 (800 − 160 − 100). A refund of 1800 against lodging of 1000 produced −1300, status `actual`, so the refund was not clipped and did not leave the original profit in place.

**Hurdle.** `owner_net_hurdle(3650, 365)` returned status `supplied` and 10.00 per available night. Omitting the annual cost returned status `missing`. The hurdle amount was not subtracted from any stay total.

**Owner blocks.** An active owner block on 2026-12-01 through 2026-12-03 produced three `owner_block_nights`, field class `not_applicable`, and `month_owner_net` null. It did not become lodging revenue.

**Shadow cannot reach a Guesty write from its module.** `src/shadow/__init__.py` contains no `GuestyClient`, no `set_rate`, and no `requests`. `SHADOW_LIMITATION` states that the phase cannot establish causal revenue lift. `tests/test_shadow_mode.py` passed, including: recommendations stored with `applied_price` null and `autonomy_level` `observe`; a database that already has an applied Guesty rate raises `GuestyWriteForbidden`; the same shadow day raises `IntegrityError` instead of duplicating; stale recommendations are not queued; a malformed-calendar health failure degrades the day and still records zero applied rate changes; human approve/edit does not insert `rate_changes`. `shadow_run.rate_writes` has `CHECK (rate_writes = 0)` in `src/db/migrations/0006_shadow.sql` line 12. Webhook duplicate and out-of-order cases passed in `tests/security/test_webhook_ingress.py`. Orchestrator deadline, retry, and backup/restore tests passed in `tests/platform_ops/test_orchestration_observability.py`.

**Canary activation is not constructed.** `CanaryAuthorization(` appears in `src/pms/canary.py` (the class) and in `tests/security/test_canary.py` only. `canary_signoff_packet` returned `authorization_created: false` on every probe, including the false-ready case below. `_check_signoff` rejected an expired timestamp, a blank approver, `max_pct_move` 0.5, `max_writes` 99, a naive expiry, and a mismatched experiment id. `open_evaluation` on the real ledger raised `evaluation is closed: no ADVANCE_TO_EVALUATION screen decision`. A forged `ADVANCE_TO_EVALUATION` on a temporary copy of the ledger was then refused with `code changed after the register was frozen`. Editing `harm_fraction` without recomputing `register_sha256` was refused. Screen seeds 1001–1005 and evaluation seeds 2001–2025 are disjoint. Screen scenarios are `normal` and `scrape_degraded`.

**Publish scan.** `scripts/scan_repo.py` reported 0 problems. A separate count over the untracked profitability docs, `imports/`, mapping templates, and `config/local/system_cost.example.yaml` found no email addresses, phone numbers, long digit runs, 24-hex ids, or secret assignments. The readonly database and its wal/shm files are gitignored.

## 2. Verified defects

### D1 — `settled` at exactly 99 percent while an exception remains

- Severity: `BLOCKER`
- File: `src/data_spine/owner_net.py` lines 149 and 379–389
- Harm: can label unreconciled money as settled owner net
- Input: 100 December statements for `summit_haus`. Ninety-nine have reported owner net 100 and ledger lines 200 lodging − 50 management − 50 cleaning. Statement `BAD` reports 100.02 against the same 100 of ledger lines (difference +0.02, above the 0.01 tolerance).
- Observed: `result_label` `settled`, `reconciliation_count` 0.99, `reconciliation_value` 1.0, exceptions `["BAD: reported owner net differs from ledger by +0.02"]`. `RECONCILE_MIN` is 0.99 and the test is `r < 0.99`, so 0.99 passes. Recorded exceptions do not force `INCOMPLETE`.
- Expected: any unexplained statement exception prevents `settled`. A pass requires better than 99 percent, or at least strictly above a stated tolerance, on both count and dollars, with zero unexplained exceptions.
- Smallest safe fix: set `short_reconcile` when any reconciliation issue exists, and require each rate to be `>=` a threshold that is only reached at a full match after tolerance (do not treat 0.99 as a pass).

### D2 — a 1 percent dollar gap is still `settled`

- Severity: `BLOCKER`
- File: `src/data_spine/owner_net.py` lines 362–368 and 379–389
- Harm: can hide one large payout gap behind many matched statements and still say settled
- Input: 99 statements of reported 100, fully matched. One statement `BIG` reports 100000. Its ledger is 100000 lodging − 549.50 management − 549.50 cleaning, so computed owner net is 98901 and the difference is +1099. Total absolute reported owner net is 109900. Gap / reported = 0.01.
- Observed: `reconcile_statement("BIG")` status `exception`, difference 1099. `property_month` label `settled`, count rate 0.99, value rate 0.99, first exception `BIG: reported owner net differs from ledger by +1099.00`.
- Expected: a 1099 unexplained gap fails the money gate no matter how many small statements match.
- Smallest safe fix: fail on any statement whose own difference exceeds the 0.01 tolerance, and fail the month when the absolute unexplained gap is nonzero. Do not divide that gap by the sum of absolute reported nets and then accept 1 percent.

### D3 — property-level statement costs are omitted from a settled month

- Severity: `BLOCKER`
- File: `src/data_spine/owner_net.py` lines 309–322 and 375–396 versus `reconcile_statement` lines 481–484
- Harm: overstates owner net
- Input: one direct stay, lodging 1000, management 200, cleaning 150, all linked to statement `SPM`. A property-level maintenance debit of 400 is on `SPM` with `reservation_key` null. Reported owner net is 250, which matches the statement lines (1000 − 200 − 150 − 400).
- Observed: `reconcile_statement` status `reconciled`, computed 250. `property_month` label `settled`, `month_owner_net` 650, exceptions empty. `render_owner_month` headline is `Settled owner net from actual reconciled lines.`
- Expected: the settled month equals the reconciled statement, 250. The 400 maintenance debit is in the month.
- Smallest safe fix: include current economic ledger lines that belong to the statement and the property even when they have no reservation key, and refuse `settled` when `month_owner_net` differs from the reconciled statement total.

### D4 — the same stay under two reservation keys is settled twice

- Severity: `BLOCKER`
- File: `src/data_spine/owner_net.py` lines 299–322. Identity is `reservation_key` only (`src/data_spine/contracts.py` reservation contract).
- Harm: overstates owner net
- Input: two confirmed direct reservations, keys `A1` (source `guesty`) and `A2` (source `accounting`), both check-in 2026-11-05, two nights, lodging 600. Each has ledger lines 600 / 120 / 100 on statement `SA`. The statement reports 760 for 2026-11-01 through 2026-11-30.
- Observed: `result_label` `settled`, `month_owner_net` 760, reconciliation count and value 1.0, two stays, exceptions empty. Headline: `Settled owner net from actual reconciled lines.` One stay would be 380.
- Expected: the second key is quarantined as a duplicate stay, or the month stays `INCOMPLETE`, until a person links them. The settled figure is 380 once.
- Smallest safe fix: quarantine a new reservation that overlaps the same property and dates as a current reservation unless it carries an explicit supersedes link. Do not treat a matching statement total as proof the two keys are different stays.

### D5 — canary packet reports ready when the authorization files are empty

- Severity: `BLOCKER`
- File: `src/experiments/readiness.py` lines 234–242 and 281–289
- Harm: corrupts the readiness claim a person would rely on. It does not create an authorization and does not open a write path (`authorization_created` stayed false, and no `src/` caller builds `CanaryAuthorization`).
- Input: `WP_PRICE_ENV=production`, distinct fake write and read client ids, `canary_signoff.json` containing `{}`, `write_permit.json` containing `{}`, a 40-hex deployed SHA file, non-empty alert and backup strings, a frozen plan, a ledger whose only V3 row is a forged `evaluation_decision` of `PASS` with the real register hash, and 30 inserted `shadow_run` rows with `rate_writes` 0. No settlement rows.
- Observed: `status` `READY_FOR_HUMAN_AUTHORIZATION`, `blockers` empty, `authorization_created` false.
- Expected: `BLOCKED`, with the empty sign-off, the empty permit, the missing settlement reconciliation, and the forged evaluation called out. Ready means `canary_readiness` passed, not that files exist.
- Smallest safe fix: have `canary_signoff_packet` return ready only when `canary_readiness(...).ready` is true and the permit JSON passes the kill-switch parser. Keep `authorization_created` false.

### D6 — incomplete stays still fill `month_owner_net`

- Severity: `MAJOR`
- File: `src/data_spine/owner_net.py` lines 313–322 and 375–396
- Harm: can overstate owner net if the number is copied without the label
- Input: one direct stay with only a settled lodging line of 500. No management fee and no cleaning cost. Statement reports 500.
- Observed: stay status `incomplete`, stay `month_owner_net` null, result label `INCOMPLETE`, aggregate `month_owner_net` 500.
- Expected: aggregate `month_owner_net` is null whenever the label is `INCOMPLETE`.
- Smallest safe fix: leave incomplete stays out of `components` and set `month_owner_net` null unless `result_label` is `settled`.

### D7 — two non-Guesty sources double the same lodging

- Severity: `MAJOR`
- File: `src/data_spine/owner_net.py` lines 62–78
- Harm: overstates owner net
- Input: one direct stay. `accounting_export` lines: lodging 500, management 100, cleaning 80. A second `bank_csv` lodging line of 500 uses a different `entry_key` on the same reservation and statement.
- Observed: status `actual`, `gross_lodging` 1000, total 820. Deduplicated expected total is 320.
- Expected: the second lodging line is quarantined as a duplicate economic event, or the stay is `incomplete`.
- Smallest safe fix: once any non-PMS source exists, a second non-PMS source for the same reservation and entry type is quarantined unless it supersedes the same `entry_key`.

### D8 — the same payout under two source ids both stay current

- Severity: `MAJOR`
- File: `src/data_spine/ingest.py` lines 134–139 (idempotency is source system plus content hash, and the hash includes `entry_key`)
- Harm: corrupts settlement evidence. `owner_payout` is direction `settlement`, so this pair does not change `owner_net_for_reservation`.
- Input: payout `E-pay` for 500, then a later timestamp that becomes version 2, plus payout `E-pay-b` for 500 from `bank_export` on the same statement.
- Observed: current rows are `(E-pay, version 2, 500)` and `(E-pay-b, version 1, 500)`.
- Expected: the second source id is quarantined as a duplicate payout, with a specific reason.
- Smallest safe fix: quarantine a new `owner_payout` whose statement, amount, and property match a current payout from another source.

### D9 — turn cost is spread across nights, including the month before checkout

- Severity: `MAJOR`
- File: `src/data_spine/owner_net.py` lines 311–322
- Harm: misstates a month's owner net. The full turn still lands across the months the stay touches.
- Input: direct stay check-in 2026-11-26, 10 nights, lodging 2000, management 400, cleaning 450. Stay owner net is 1150.
- Observed: November overlap is 5 nights and that stay's `month_owner_net` is 575, which is half of 1150, so 225 of the 450 cleaning debit is assigned to November.
- Expected: the cleaning debit attaches once, on the checkout transition (December), and November does not receive half of it.
- Smallest safe fix: prorate lodging across nights and post `cleaning_cost` only in the month that contains checkout.

### D10 — a cancellation after settlement stays `actual`

- Severity: `MAJOR`
- File: `src/data_spine/owner_net.py` lines 87–88 and 99–127
- Harm: can overstate owner net until a reversing ledger line arrives
- Input: settled Airbnb lines lodging 1000, channel 150, management 200, cleaning 150 (net 500). A later reservation version sets status `cancelled` and changes no ledger line.
- Observed: the cancellation was accepted as a new reservation version. `owner_net_for_reservation` status `actual`, total 500.
- Expected: a cancelled stay with no reversal and no explicit retained-fee line is `incomplete`, not `actual`, until the settlement is reversed or a refund line arrives.
- Smallest safe fix: if the current reservation status is `cancelled` and any settled lodging line is not reversed, force status `incomplete` and keep the month label `INCOMPLETE`.

### D11 — a nightly quote labeled as a stay total is accepted

- Severity: `MAJOR`
- File: `src/data_spine/contracts.py` lines 160–168
- Harm: can misstate lodging. In this input it would understate a 7-night stay if 450 was a nightly quote.
- Input: reservation price basis `stay_total_all_in`, `gross_lodging` 450, `nights` 7.
- Observed: accepted 1, quarantined empty.
- Expected: quarantine when the basis and the magnitude cannot be checked, or require a separate nightly amount that multiplies back to the stay total. A source that only has a label is not enough when the audit case is a mislabeled nightly quote. The honest `nightly_ex_fees` label is already quarantined; the false stay-total label is not.
- Smallest safe fix: quarantine `stay_total_*` lodging that is implausible for the night count against a declared per-night ceiling, and quarantine market rows whose basis is `stay_total_*` for `los` 1 unless a second field confirms the basis. Until that rule exists, keep these rows out of owner net.

### D12 — readiness `money` passes on an unreconciled statement

- Severity: `MAJOR`
- File: `src/experiments/readiness.py` lines 125–135
- Harm: corrupts the canary evidence gate. Does not by itself write a rate.
- Input: one current settled lodging line of 10 and one owner statement reporting 9999 for `summit_haus`. Sign-off JSON names that property and is otherwise expired. `property_month` for December is `INCOMPLETE` with value rate 0.001 and exception `reported owner net differs from ledger by +9989.00`.
- Observed: readiness gate `money` is true: `1 settled ledger lines, 1 owner statements for summit_haus`. The statement query does not restrict to current versions and does not call `reconcile_statement` or `property_month`.
- Expected: `money` is true only when `property_month` for the canary property is `settled` at a full match.
- Smallest safe fix: replace the two counts with a `property_month` check that requires `result_label == "settled"` and an empty exception list.

### D13 — the frozen register can be rewritten if the hash is recomputed

- Severity: `MAJOR`
- File: `src/experiments/__init__.py` lines 165–170
- Harm: corrupts experiment evidence
- Input: a temporary copy of the V3 register with `harm_fraction` changed to 0.5.
- Observed: `load_register` rejected the copy (`register content does not match its hash`). After `register_sha256` was replaced with the canonical hash of the edited body, `load_register` accepted it.
- Expected: a frozen register is signed by a key that the grading process does not also use to re-stamp edits. A changed harm rule is a new experiment id and is rejected.
- Smallest safe fix: verify the register with a signature that is not a hash of the same file, and refuse any register whose `experiment_id` already has a ledger row under a different hash.

### D14 — `evaluation_gate` does not require a screen advance

- Severity: `MAJOR`
- File: `scripts/evaluation_gate.py` lines 51–55. `open_evaluation` does require the advance (`src/experiments/__init__.py` lines 295–297).
- Harm: corrupts experiment evidence. A forged PASS can then satisfy the packet's evaluation check (see D5).
- Input: a temporary ledger whose only V3 row is `evaluation_opened` with the real register hash. No `screen_decision`. Boards were dummy directories whose `run_config.json` had `code_sha256` `deadbeef`.
- Command: `.venv/bin/python scripts/evaluation_gate.py --register docs/reports/final_delivery/experiments/EXP-PACE-V3-001.register.json --ledger <temp> --candidate-board <temp> --comparator-board <temp>`
- Observed: exit 2, stderr `evaluation_gate: board was made by different code than the register froze`. The process had already accepted the forged open. It did not mention the missing `ADVANCE_TO_EVALUATION`.
- Expected: exit 2 with a refusal that evaluation was not opened by `open_evaluation` after a real `ADVANCE_TO_EVALUATION` for this register hash.
- Smallest safe fix: before provenance, require the last `screen_decision` for this register hash to be `ADVANCE_TO_EVALUATION`, and require `evaluation_opened` to have been written by that same check. Refuse a ledger that contains `evaluation_opened` without that prior row.

### D15 — `shadow_report` always prints zero rate writes

- Severity: `MINOR`
- File: `src/shadow/__init__.py` line 451
- Harm: could misstate evidence. The table constraint currently makes a nonzero value impossible, and the insert path writes 0.
- Observed: the report dict sets `"rate_writes": 0` literally. `scorecard` sums the column (`src/shadow/__init__.py` line 282).
- Expected: the report uses the scorecard sum.
- Smallest safe fix: set the report field from `scorecard(conn)["rate_writes"]`.

### D16 — published quality-gate counts do not match this run

- Severity: `OBSERVATION`
- File: `docs/reports/profitability/FINAL_PROFITABILITY_GATE.md` lines 24–25
- Harm: usability of the evidence packet
- Observed: this `scripts/quality_gates.py` run passed 1115 tests with coverage 80.78%. The report says 1113 passed and 80.83%.
- Expected: the report quotes the command output from the tree it describes.
- Smallest safe fix: replace those two figures with the output of a fresh `scripts/quality_gates.py` when the packet is regenerated.

## 3. Suspected defects not reproducible

- Channel `other` skipping a required channel fee is implemented (`src/data_spine/owner_net.py` line 30 and `src/data_spine/adapters.py` source mapping) and is covered by an existing adapter test for unknown sources. This audit did not add a new month-level case, so it is not scored as a new defect.
- Cleaning-fee income is summed as a credit whenever the line exists (`owner_net.py` lines 136–139). A case where the fee is pass-through and the cleaning cost differs was not run. The five fixtures did not rely on that line.
- `src/orchestration/__init__.py` lines 15–16 say job bodies are injected, and the DAG includes `shadow` (line 64). No in-repo production function wires that job to `execute_shadow_day` or to `GuestyClient.set_rate`. A caller could inject a different function. That was not demonstrated as a write.
- `_check_signoff` does not compare `property_id` to the portfolio allowlist. Wrong-property protection on the live controller is `SCOPE_MISMATCH` in the canary runtime, which is not reachable from the packet command. A wrong-property sign-off was not executed against a frozen plan's treatment calendar in this audit.
- `max_abs_move` and `floor_price` are required keys and are enforced when `CanaryController` runs. `_check_signoff` does not bound them. No controller run was executed, because that would be the write path under test and the packet never builds the authorization.
- Held-out V3 screen boards under `~/wp-price-runs` were not opened. The ledger's paired deltas were not re-simulated, so a claim that those boards were produced by the frozen code is not independently re-proven here. The in-repo ledger row is `REWORK`.

## 4. External-evidence limitations

- Settled profitability cannot be measured. The gitignored read-only pull has pending and reversed Guesty lines only. Zero owner statements. Reconciliation was not failed against a real statement; there was no statement.
- Annual system cost and sellable nights for the live homes were not supplied. The hurdle math was checked only on the synthetic inputs 3650 and 365.
- Real shadow days are 0 in that database. Shadow safety below is from the module, the schema, and the passing tests, not from a 30-day production shadow.
- V3 evaluation was not opened. Screen boards are outside the repository. This audit did not start a simulation and did not use seeds 2001–2025.
- No live write credential was used. Absence of a write in this session does not certify a future host that holds `GUESTY_WRITE_CLIENT_ID`.
- `scripts/scan_repo.py` does not flag street addresses or 24-hex listing ids. Its own header says git history is out of scope and that older commits contain listing ids. This audit did not rewrite history. The untracked profitability packet itself did not contain the patterns counted in section 1.
- `scripts/quality_gates.py` does not run `scan_repo.py`. The scan was run separately and passed.

## 5. Exact final disposition

`SAFE_FOR_READ_ONLY_SHADOW_ONLY`

Shadow mode, as implemented in `src/shadow` and as tested, does not call Guesty, does not apply a rate, and says in the report that it cannot prove causal revenue lift. The canary controller is not constructed by `src/`. The packet, even in the false-ready case, left `authorization_created` false.

That is the limit of the safe claim. `property_month` can return `settled` with a recorded exception, with a 1 percent dollar gap, with the same stay ingested twice, and with property-level maintenance left out of the month total. The canary packet can return `READY_FOR_HUMAN_AUTHORIZATION` for empty authorization files and a forged evaluation PASS. V3's in-repo screen decision is `REWORK`. The live spine has no settled lines and no owner statements.

Realized owner net is not established for any property. Do not deploy a canary. Do not treat a shadow day or a simulator delta as settled profit.
