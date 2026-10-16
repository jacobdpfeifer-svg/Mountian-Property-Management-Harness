# Platform readiness

Assessment date: 2026-10-15 (after the repository-controlled delivery pass).
Decision: **repository controls PASS locally; deployment and canary remain
BLOCKED on operator infrastructure and authority.** No deployment was performed.

## Built and tested in this pass

| Area (prompt) | What exists | Proof |
|---|---|---|
| Immutable release + rollback (06A) | `scripts/release.py`: build from `git archive HEAD`, read-only files, `RELEASE_MANIFEST.json` + `DEPLOYED_SHA`, atomic activation, rollback to the latest verified release | `tests/platform_ops/test_release.py`; identical `manifest_sha256` on two clean-copy runs |
| CI (06A) | `.github/workflows/ci.yml`: lock check, frozen sync, quality gates, pip-audit, publish scan, migrations, manifest reproducibility, slow lane, golden V1 board | Written; **not yet executed on GitHub** (NOT_MEASURED) |
| Reproducible dependencies | `uv.lock` was stale (no `hypothesis`); regenerated, only that package added; CI now runs `uv lock --check` | clean-copy run |
| Scope (06B) | `PortfolioScope`: exactly the three homes or `ScopeError`; quarantine + redacted audit at sync, webhook, push, review, canary, ingest (recommendation and owner-report paths still rely on the existing locked-portfolio filter, without an audit event) | `tests/security/test_controls.py` |
| Environments and credentials (06B) | `WP_PRICE_ENV`; env ↔ DB-identity check; separate write credential with no fallback | same |
| Kill switch (06B/03) | Permit + KILL file, evaluated at call time, fails closed on any error; enforced in `GuestyClient.set_rate`, `push_recommendations` (live adapters), and the canary | same; existing `set_rate` retry tests now run under an explicit test permit |
| Publish scanner | `scripts/scan_repo.py` over tracked + untracked-unignored files | 0 problems; detection test |
| Webhook ingress (06C) | Svix-format signature before persistence, 5-minute replay window, dedupe, redacted immutable receipt, dead letter, scope quarantine, bounded refetch queue | `tests/security/test_webhook_ingress.py` |
| Observability + DR (06E) | Run receipts (append-only), autonomy ceiling, incidents, local alert sink, SQLite backup/restore with checksum + integrity check | `tests/platform_ops/test_orchestration_observability.py` |
| Orchestration (06F) | Dependency DAG for the eight declared jobs; lock; deadlines; retry/backoff; idempotent repeat; missed-snapshot detection without backfill | same (chaos tests) |
| Runbooks | `docs/runbooks/DEPLOYMENT.md`, `docs/runbooks/INCIDENT_AND_ROLLBACK.md`, `docs/adr/0001-…`, `DATA_FLOW.md` | — |

## Prompt 03 acceptance gates

| Gate | State |
|---|---|
| Clean machine produces an identical release manifest and passes the suite | PASS locally (scratch copy); CI run NOT_MEASURED |
| Every scheduled job has owner, schedule, deadline, retry, alert, receipt | PASS as documented + library; live scheduler not cut over (BLOCKED/integration) |
| Stale/broken source → visible degraded state, no broadened authority | PASS (`autonomy_ceiling`, orchestration chaos tests, ops vendor outage) |
| Malformed price, out-of-scope listing, stale pace, failed read-back, rollback have passing integration tests | PASS (spine quarantine; scope tests; stale health → `STALE_HEALTH`; canary read-back/rollback tests) |
| Deployed runtime proves its version; nothing confidential tracked or reported | Version: BLOCKED (no deployment). Working tree scan: PASS. Git history: FAIL (listing ids in old commits) |

## Still BLOCKED (external)

Managed runtime and database; secret manager and automated rotation; external
alert/log destination; encrypted off-host backups; live webhook subscription
and endpoint; a second (write) Guesty credential; applying spine migrations to
the operator database; history purge (owner-approved force push); running CI
(owner-approved push to the public repository).

## Limits worth knowing

- A job that overruns its deadline is recorded failed, but Python cannot kill
  its thread; downstream jobs are skipped so nothing consumes its partial output.
- Backups are local and unencrypted.
- The webhook verifier follows Svix's public format; it has not been checked
  against a live Guesty delivery.
