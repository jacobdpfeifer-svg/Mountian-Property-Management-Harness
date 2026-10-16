# Incident, kill-switch, and rollback runbook

## Stop all writes now

```bash
python -m src.security.kill_switch engage --reason "<why>"
python -m src.security.kill_switch status     # must print "writes_allowed": false
```

Engaging needs no permit and takes effect on the next write check (each write
re-checks). To resume, the operator deletes the `KILL` file **and** issues a new
permit; there is no command that does either.

## Severity

| Severity | Examples | Automatic effect | Response |
|---|---|---|---|
| sev1 | read-back mismatch; rollback failed; write outside scope; secret exposure | autonomy → observe; incident file + alert | engage kill switch; operator restores prior rates from the canary snapshot; rotate secrets if exposed |
| sev2 | required job failed (snapshot, PMS sync, recommendation, review); reconciliation exceptions | autonomy → observe/suggest; incident + alert | fix the source; re-run the day (idempotent); never backfill a missed snapshot |
| sev3 | optional source degraded (comps, signals, ops vendor) | autonomy capped at suggest | track; no paging |

Incidents are JSON files under `<run root>/incidents/`; alerts append to
`<run root>/alerts.jsonl`. Paging/email delivery is BLOCKED on an
operator-chosen alert service (`src/observability.AlertSink` is the seam).

## Scheduled jobs

| Job | Owner | Schedule (America/Denver) | Deadline | Retries | Required for > observe | Alert |
|---|---|---|---|---|---|---|
| snapshot | operator | 06:05 | 10 min | 2, backoff 5 s ×2ⁿ | yes | sev2 |
| pms_sync | operator | 06:10 | 10 min | 2 | yes | sev2 |
| comp_collection | operator | 07:00 | 10 min | 2 | no | sev3 |
| signals | operator | 07:15 | 10 min | 2 | no | sev3 |
| ops_import | operator | 07:20 | 10 min | 2 | no | sev3 |
| recommendation | operator | after snapshot + pms_sync | 10 min | 2 | yes | sev2 |
| review_artifact | operator | after recommendation | 10 min | 2 | yes | sev2 |
| outcome_reconciliation | operator | after pms_sync | 10 min | 2 | no | sev3 |

The dependency graph and degraded results are in `src/orchestration` (tested by
`tests/platform_ops/test_orchestration_observability.py`). Wiring the existing
CLI commands into it and moving launchd to it are operator/integration steps.

## Canary abort and rollback

The canary controller (`src/pms/canary.py`) aborts on: missing/expired
authorization, unnamed approver, live adapter without operator signature, scope
mismatch, unauthorized date, write-count cap, duplicate date, data health not
`handle`, operational restriction, kill switch, missing snapshot, unavailable
night, rate below floor, move cap, write failure, read-back mismatch, or a
changed non-price field. After any abort it writes each already-changed night
back to its snapshot price and verifies by read-back; a failed rollback is
reported as `aborted_rollback_failed` (sev1).

## Database restore

```python
from pathlib import Path
from src.observability import restore_db
restore_db(Path("<backup>.db"), Path("<target>.db"))       # verifies checksum + integrity_check
```

Restore refuses to overwrite an existing file unless `overwrite=True`. Encrypted
off-host retention is BLOCKED on an operator storage/KMS choice.
