#!/bin/bash
# Daily Guesty sync + pacing snapshot + gap check.
#
# Order: sync-guesty, then snapshot, then verify. Snapshot still runs if sync
# fails so a stale calendar is captured rather than skipping the day. Verify
# still runs if snapshot fails so a crash cannot hide a missing day.
# Never run later ingest from this job — ingest would overwrite nightly_inventory
# after the snapshot.
#
# Exit code is non-zero when any step is degraded or failed (same contract as
# scrape-comps). Set PACING_ALERT_EMAIL and/or PACING_ALERT_SLACK_WEBHOOK to
# notify; until those are set, launchd's non-zero exit + this log is the signal.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: missing venv python at $PYTHON" >&2
  exit 1
fi

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

wp_price() {
  "$PYTHON" -c 'import sys; from src.cli.main import main; raise SystemExit(main(sys.argv[1:]))' "$@"
}

alert() {
  local msg="$1"
  if [[ -n "${PACING_ALERT_SLACK_WEBHOOK:-}" ]]; then
    curl -sS -X POST -H 'Content-type: application/json' \
      --data "{\"text\":\"${msg}\"}" \
      "$PACING_ALERT_SLACK_WEBHOOK" || true
  fi
  if [[ -n "${PACING_ALERT_EMAIL:-}" ]]; then
    printf '%s\n' "$msg" | mail -s "wp-price pacing job failed" "$PACING_ALERT_EMAIL" || true
  fi
}

DB="${WP_PRICE_DB:-${ROOT}/data/wp_pricing.db}"
LOG_DIR="${PACING_LOG_DIR:-${ROOT}/data/logs}"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/pacing-$(date +%Y-%m-%d).log"

{
  echo "===== $(date +%Y-%m-%dT%H:%M:%S%z) daily pacing ====="
  echo "root=$ROOT db=$DB"

  sync_rc=0
  snap_rc=0
  verify_rc=0

  echo "--- sync-guesty ---"
  wp_price --db "$DB" sync-guesty || sync_rc=$?

  echo "--- snapshot ---"
  wp_price --db "$DB" snapshot || snap_rc=$?

  echo "--- snapshot --verify ---"
  if [[ -n "${PACING_VERIFY_SINCE:-}" ]]; then
    wp_price --db "$DB" snapshot --verify --since "$PACING_VERIFY_SINCE" || verify_rc=$?
  else
    wp_price --db "$DB" snapshot --verify || verify_rc=$?
  fi

  rc=0
  if [[ $sync_rc -ne 0 || $snap_rc -ne 0 || $verify_rc -ne 0 ]]; then
    rc=1
    echo "FAILED sync_rc=$sync_rc snap_rc=$snap_rc verify_rc=$verify_rc"
    alert "wp-price pacing job failed (sync=$sync_rc snapshot=$snap_rc verify=$verify_rc). See $LOG"
  else
    echo "OK"
  fi
  echo "===== done rc=$rc ====="
  exit "$rc"
} >>"$LOG" 2>&1
