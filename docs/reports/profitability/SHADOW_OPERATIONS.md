# Shadow operations

Date: 2026-10-20. Shadow gate: **NOT_PASSED**. Real shadow days on the operator runtime: **0**. Guesty writes from shadow: **0**.

This shadow phase tests ingestion quality, decision traceability, and forecast calibration. It cannot establish causal revenue lift without a later controlled canary.

## What a day records

[src/shadow/__init__.py](../../../src/shadow/__init__.py) still holds no PMS client. `run_shadow_day` refuses a database that already contains an applied Guesty rate. Each property / as-of / stay date appends `shadow_night` (migration `0007_shadow_night`) with:

- listed rate, minimum stay, availability
- recommended price, reasons, price distance from the listed rate
- health level and autonomy (`observe` on every shadow row)
- comp age, coverage, and price-basis confidence (`unknown` when there is no comp coverage, otherwise `uncertified`, because a scrape is not a certified nightly / stay-total / all-in basis)
- lead time; length of stay and channel when the inventory row has them
- forecast RevPAN from the engine, stored separately
- forecast RevPAN is kept separate from actual results; after the night passes, an append-only, source-fingerprinted outcome-observation ledger records actual ADR, actual RevPAN (zero for an unsold available night), and settled owner net **per stay-night** only when the spine has fully settled actual lines
- weak-ceiling flag

`capture_outcomes` still records booked, available, blocked, or unknown after the night passes. It appends a new outcome observation if later settlement changes the owner-net result; it never rewrites the original calendar outcome. `shadow_report` segments by property, calendar season (winter Dec–Mar, summer Jun–Aug, otherwise other), lead-time bucket, length of stay, channel, price-distance bucket, weak ceiling, comp state, outcome, and refund/owner-net status, with actual ADR, actual RevPAN, and settled owner net per stay-night where available.

The same as-of and property is refused by the `shadow_run` unique key. A second call reports the original health failure again instead of turning a degraded day into a success.

## Orchestrator

`shadow` is in `DAILY_DAG` after `recommendation` and is required. A degraded shadow lowers autonomy to `suggest` and keeps a receipt. A failed shadow forces `observe` and opens an incident. Receipts stay append-only.

Runbook: [docs/runbooks/DEPLOYMENT.md](../../runbooks/DEPLOYMENT.md) section 6. The job is not on launchd. A managed scheduler has not been cut over.

## Tests

- `tests/test_shadow_mode.py`: night fields, append-only outcome metrics, uncertified or unknown price basis, report limitation, gate not passed after one fixture day, append-only shadow tables, degraded rerun writes no rate, and an unrelated database integrity collision fails closed.
- `tests/platform_ops/test_orchestration_observability.py`: degraded shadow receipt and `suggest`; failed shadow `observe` plus an incident.
- `tests/test_shadow_mode.py::test_the_shadow_module_holds_no_pms_client`.
- Quality gates 2026-10-20: 1113 passed.

## Why the gate is not passed

The gate needs 30 calendar days of real rows (`SHADOW_GATE_DAYS`). This session did not insert shadow rows into the operator database and did not invent a 30-day history. Credentials for a read exist. The missing piece is a managed daily runtime that runs `recommend` and then `wp-price shadow-day` for 30 Denver dates, with receipts retained.

## Assumptions

None about revenue lift. Comp price basis on shadow rows is uncertified whenever coverage is non-zero.

## Exceptions

No production shadow receipt exists yet, so there is no degraded or failed production day to list. The fixture tests cover those states.

## External dependencies

Operator launchd or another scheduler pointed at a verified release; a daily `recommend` before shadow; comp coverage that can eventually be certified. See `EXTERNAL_BLOCKERS_AND_REQUESTS.md`.

## Next action

After the release is deployed, run `wp-price shadow-day` once per day for 30 days. Read `wp-price shadow-report`. Do not quote those rows as proof that a different price would have earned more.
