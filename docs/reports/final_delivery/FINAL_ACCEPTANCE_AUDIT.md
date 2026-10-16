# Final acceptance audit — repository-controlled scope

Date: 2026-10-15. Auditor: the implementing agent, reviewing its own work
(not independent of the implementation; a second reviewer should repeat the
checks below). Scope: everything the repository can prove without operator,
vendor, payment, real data, or live authority.

## Verdict: **CONDITIONALLY_ACCEPTED**

The repository-controlled work orders (06A–06F, 06I–06K, and the 06G/06H
guardrail infrastructure) are implemented and tested, and every remaining gap
is either an external gate or a listed condition below. This verdict does
**not** mean deployable, shadow-ready, or profitable: the model screen failed
(REWORK), nothing is deployed, and no realized owner-net evidence exists.

## Conditions (must be closed before `ACCEPTED_FOR_SCOPE`)

1. **Commit the work.** All changes are uncommitted in `~/code/harness`
   (commit/push was not authorized). A release manifest can only describe
   committed code.
2. **Re-run the 10 lock-blocked market-sim tests** once the active V2 run
   (`~/wp-price-runs/full_sim_20261015_d291c60/v2_default_1_30`) releases
   `RUN.lock`. They refused correctly; they did not run.
3. **Observe one green CI run** of `.github/workflows/ci.yml` (needs an
   owner-approved push to the public repository).
4. **Wire `PortfolioScope` audit events into the recommendation and owner-report
   paths** (they exclude out-of-scope homes today but do not record a
   quarantine event). This touches `src/cli/main.py` / engine entry points,
   which this pass deliberately did not edit.

## Trace performed

| Link | Evidence | Result |
|---|---|---|
| Source ingestion → contract | `ingest` on `synthetic_lifecycle.json`; undeclared PII fields dropped | PASS (fixture) |
| Recommendation → review action | `review.enqueue/act/export`; model vs human vs applied separated | PASS (fixture) |
| Review → canary receipt | canary fake adapter: snapshot, dry-run diff, write, read-back, rollback | PASS (fake; inactive) |
| Reservation outcome → financial reconciliation → owner statement | `trace_reservation("R-SYN-001")`, three statements reconcile; a reissued statement mismatch is an exception | PASS (fixture) |
| Model feature → field outcome | none | NOT_MEASURED |

## Checks reproduced

| Check | Command | Result |
|---|---|---|
| Default suite (working tree) | `.venv/bin/python -m pytest -q -p no:cacheprovider --cov=src` | 1004 passed, 1 skipped, 10 failed (all `RUN.lock` refusals); coverage 80% |
| Slow lane | `pytest -m slow` | 3 passed |
| Types / dead code | `mypy src scripts`; `vulture src scripts --min-confidence 80` | clean (157 files); clean |
| Clean environment | fresh copy of tracked + unignored files → `uv lock --check` → `uv sync --frozen --extra dev` → suite | lock OK; 1004 passed, same 10 lock refusals |
| Manifest determinism | `scripts/release.py manifest` twice in the clean copy | identical `manifest_sha256` |
| Publish scan | `scripts/scan_repo.py` | 0 problems; detection test passes |
| Real listing ids in publishable files | compared against gitignored `config/local/listings.yaml` (ids not printed) | none found |
| Default control dir | `~/.wp-price/control` | does not exist → writes blocked |
| Guesty writes | read-only query of the operator DB `rate_changes` | 0 rows (ever) |

Found and fixed during the audit: a stale `uv.lock` (clean install could not
run the suite); a scanner test that tripped the scanner; the canary writing
around the floor guard (caught by the existing call-site regression test,
fixed by routing every canary write through one guarded method); an overstated
scope claim in three reports.

## Safety rules: compliance

| Rule | Status |
|---|---|
| Guesty writes = 0 | Kept. No credential used; all writer tests use fakes or patched `requests.put`. |
| No PII/secrets/confidential data in Git, fixtures, logs, reports | Kept for the working tree. Old commits still contain listing ids (pre-existing; purge needs owner approval). |
| Missing/stale/malformed feed reduces autonomy | Enforced (`autonomy_ceiling`, quarantine, ops outage, orchestration). |
| No tuning after held-out inspection; no held-outs opened | Kept. Evaluation for `EXP-PACE-V2-001` is closed (REWORK). |
| No concurrent market simulations | Kept. No simulation launched; lock-taking tests were left refused. |
| No weakened assertions | Two existing tests were changed: `test_integration_matrix_compose` now lists the `live` flag in the adapter surface (the no-availability-write assertion stands); `test_set_rate_is_unreachable_without_push_recommendations` now allows exactly the canary's single guarded call site and additionally asserts it checks the floor. The three `set_rate` retry tests run under an explicit test permit. |

## Changed files

Modified: `pyproject.toml`, `uv.lock`, `src/pms/__init__.py`, `src/pms/guesty.py`,
`src/pms/sync.py`, `tests/test_guesty.py`, `tests/ops/test_integration_matrix_compose.py`.

Added: `src/db/migrations/` (0001–0005 + runner), `src/data_spine/`,
`src/security/`, `src/pms/webhook_ingress.py`, `src/pms/canary.py`,
`src/observability/`, `src/orchestration/`, `src/ops/constraint_adapter.py`,
`src/review/`, `src/experiments/`, `scripts/release.py`, `scripts/scan_repo.py`,
`scripts/screen_gate.py`, `.github/workflows/ci.yml`, `docs/adr/0001-…`,
`docs/runbooks/`, `tests/data_spine/`, `tests/security/`, `tests/platform_ops/`,
`tests/fixtures/data_spine/`, and the reports in this directory. The prompt pack
`docs/prompts/FINAL_DELIVERY/` and this directory were copied from the iCloud
checkout (originals left in place).
