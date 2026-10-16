# Live safety evidence

Date: 2026-10-15. Authority decision: **observe**. Guesty writes performed: **0**.

Prompt 04's preconditions are not met: no candidate has `ADVANCE_TO_SHADOW`
(the pace candidate is `REWORK`), the runtime is not deployed from a verified
release, and no written canary scope exists. This file therefore records only
the repository-side controls that a future canary would rely on.

## Controls proven with fakes (no live system touched)

| Control | Evidence |
|---|---|
| Global kill switch: missing/expired/malformed permit, wrong environment, uncovered property, or KILL → blocked | `tests/security/test_controls.py` (8 parametrized cases + engage/override/expiry) |
| `GuestyClient.set_rate` sends no HTTP request when blocked (wrong env, unknown listing, missing or read-only credential, KILL) | `test_set_rate_never_reaches_http_when_blocked` (asserts zero `requests.put` calls) |
| `push_recommendations` refuses out-of-scope and kill-switched rows for live adapters, with audit events | `test_push_refuses_out_of_scope_and_kill_switched_writes` |
| Canary preflight aborts (17 codes) before any write | `tests/security/test_canary.py::test_preflight_aborts_never_write` and neighbours |
| Read-back mismatch, non-price field change, write failure, kill switch mid-run → rollback of every written night, verified by read-back | `test_post_write_failures_roll_back_everything_written`, `test_kill_switch_engaged_mid_canary_aborts_and_rolls_back` |
| Failed rollback reported as `aborted_rollback_failed` | `test_failed_rollback_is_reported_not_hidden` |
| Idempotent re-run does not rewrite | `test_idempotent_rerun_does_not_rewrite` |
| Controller inactive by construction: no `CanaryAuthorization` built in `src/`; real switch blocks; live adapter needs `operator_signed` | `test_no_authorization_object_exists_in_source`, `test_real_kill_switch_keeps_controller_inactive`, `test_live_adapter_requires_operator_signed_authorization` |
| The only `push_rate` call sites are the two guarded boundaries | `tests/test_guesty.py::test_set_rate_is_unreachable_without_push_recommendations` (extended, not loosened) |

## Not available (BLOCKED / NOT_MEASURED)

Shadow run on the live read path (NOT_MEASURED); signed canary change request,
pre/post Guesty snapshots, adapter and read-back receipts, channel-visible
verification, staging rollback proof (all BLOCKED on operator authorization and
a write credential).
