# Deployment runbook

Audience: the operator who runs the daily pricing jobs. Nothing here performs a
Guesty write. Live writes additionally need the canary authorization in
`docs/prompts/FINAL_DELIVERY/04_SHADOW_CANARY_AND_AUTONOMY.md`.

## 1. Build a release (any clean machine)

```bash
git status --porcelain          # must print nothing for tracked files
uv sync --frozen --extra dev
uv run python scripts/quality_gates.py
uv run python scripts/scan_repo.py
uv run python scripts/release.py build --root ~/wp-price-runtime
```

The printed directory is `~/wp-price-runtime/releases/<sha12>/`. It contains
`RELEASE_MANIFEST.json` and `DEPLOYED_SHA`. Record `manifest_sha256` in the
change log; a second machine building the same commit must print the same value
(`release.py manifest`).

## 2. Activate

```bash
uv run python scripts/release.py activate --root ~/wp-price-runtime --release <sha12>
uv run python scripts/release.py verify   --root ~/wp-price-runtime
cat ~/wp-price-runtime/current/DEPLOYED_SHA
```

`verify` recomputes every file checksum. The scheduled jobs must run from
`~/wp-price-runtime/current` (repointing launchd is an operator step; until then
`scripts/deploy_runtime.sh` remains the active path).

## 3. Roll back

```bash
uv run python scripts/release.py rollback --root ~/wp-price-runtime
```

Rollback re-points `current` to the newest earlier release that still verifies
and appends to `activation_history.jsonl`. If none verifies it refuses.

## 4. Database migrations (data spine)

Applied explicitly, never by a daily job:

```bash
uv run python - <<'PY'
from src.db import connect
from src.db.migrations import apply_migrations, pending
from src.observability import backup_db
from pathlib import Path
db = Path("~/Library/Application Support/wp-price/data/wp_pricing.db").expanduser()
print("backup:", backup_db(db, db.parent / "backups"))
conn = connect(db)
print("pending:", [m.name for m in pending(conn)])
print("applied:", apply_migrations(conn))
PY
```

**Live migration status: BLOCKED** — requires the operator to run it on the
operator database after taking the backup. It is proven only on test databases
(`tests/data_spine`, `tests/security`).

## 5. Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `WP_PRICE_ENV` | demo / simulation / staging / production | unset = `unknown` (no writes) |
| `WP_PRICE_CONTROL_DIR` | kill switch + write permit location | `~/.wp-price/control` |
| `GUESTY_CLIENT_ID/SECRET` | read/sync credential | — |
| `GUESTY_WRITE_CLIENT_ID/SECRET` | write credential; must differ from read | absent = no writes |
| `GUESTY_WEBHOOK_SECRET` | `whsec_…` for webhook verification | absent = every delivery dead-lettered |

Secrets stay in the environment or an OS keychain, never in the repository or a
release. Rotation: issue the new credential in Guesty, update the environment,
confirm a read, then revoke the old credential in Guesty. A managed secret store
is BLOCKED on the operator's choice of service.
