# Canary readiness

Date: 2026-10-20. Packet status: **BLOCKED**. `authorization_created`: **false**. No `CanaryAuthorization`, write permit, or live adapter was created. Guesty writes: **0**.

## What was run

Existing abort, dry-run, scope, read-back, rollback, and kill-switch tests are in `tests/security/test_canary.py` and `tests/security/test_canary_readiness.py`. They passed inside `scripts/quality_gates.py` (1113 passed, 2026-10-20). `tests/security/test_canary_packet.py` checks that a missing packet stays `BLOCKED` and writes no sign-off file.

`canary_signoff_packet` in [src/experiments/readiness.py](../../../src/experiments/readiness.py) only reads. Invoked against `data/profitability_readonly.db`, the V3 register, and `docs/field_test/plan.draft.json`.

## Blocking list

| Id | Owner | Artifact | Acceptance | Observed |
|---|---|---|---|---|
| environment | operator | `WP_PRICE_ENV=production` matching the database | environment is production | environment is unknown |
| write_credential | Guesty admin | `GUESTY_WRITE_CLIENT_ID` and secret, different from the read credential | `resolve_credential(WRITE)` succeeds and the ids differ | write credential is absent |
| signed_scope | owner and operator | `canary_signoff.json`: one property, dates, floors, max dollar and percent moves, max writes, approver, rollback owner, expiry, emergency stop | signoff gate passes | file absent |
| write_permit | operator | `write_permit.json` | kill switch can permit a write only while this file exists and `KILL` is absent | file absent |
| deployed_sha | operator | `~/wp-price-runtime/current/DEPLOYED_SHA` | `release.py verify` matches the serving sha | no deployed sha |
| alerts | operator | `WP_PRICE_ALERT_DESTINATION` | a failed job is delivered off the laptop | not configured |
| backup | operator | `WP_PRICE_BACKUP_DESTINATION` | restore drill from an encrypted off-host copy | not configured |
| field_plan | operator | frozen field-test plan | `load_plan` succeeds | draft file does not verify (`plan content does not match its hash`) |
| evaluation | model owner | evaluation `PASS` on this frozen register | `evaluation_decision` after a screen advance | no evaluation verdict (screen is REWORK) |
| shadow | operator | 30 real shadow days and zero rate writes | `shadow_report` gate passed | 0 shadow days |

The field-test design in [docs/field_test/PREREGISTRATION.md](../../field_test/PREREGISTRATION.md) is still inactive. Its draft was not frozen and was not edited.

Settlement-based measurement is specified in that preregistration (settled owner net per eligible night, pending money excluded). It cannot be the primary result of a canary until statements exist. Rollback and read-back are implemented and tested on the fake adapter. They have not been drilled on a live calendar. This packet does not schedule that drill.

## Tests

Quality gates 2026-10-20: 1113 passed, mypy clean, `scan_repo.py` 0 problems. Canary tests were not weakened.

## Assumptions

None. Missing files were not created to make the packet pass.

## Exceptions

Every row in the table above.

## External dependencies

A separate write credential, a signed scope, a verified production sha, managed runtime, secret store, external alerts, encrypted off-host backup, a frozen field plan, a model that has passed evaluation, and 30 shadow days. Details: `EXTERNAL_BLOCKERS_AND_REQUESTS.md`.

## Next action

Do not authorize a canary. Re-run `wp-price canary-packet` after a human has supplied the artifacts. The command prints blockers and does not grant authority.
