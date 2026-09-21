#!/bin/bash
# Daily Airbnb market sweep → comp_snapshots for every active airbnb_room_id.
#
# One sweep covers Summit Haus, Overlook Ridge, AND Cloud 9. Comp membership is
# the filter after the sweep (src/scrape), not a separate Cloud 9 job.
# Direct-book comps (Deer, Brooky, Lakota Reserve) stay on the weekly manual CSV.
#
# Exit code is non-zero when the run is degraded or failed so launchd can alert.

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
    printf '%s\n' "$msg" | mail -s "wp-price scrape-comps job failed" "$PACING_ALERT_EMAIL" || true
  fi
}

DB="${WP_PRICE_DB:-${ROOT}/data/wp_pricing.db}"
LOG_DIR="${PACING_LOG_DIR:-${ROOT}/data/logs}"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/scrape-$(date +%Y-%m-%d).log"
HORIZON="${SCRAPE_HORIZON_DAYS:-120}"

{
  echo "===== $(date +%Y-%m-%dT%H:%M:%S%z) daily scrape-comps ====="
  echo "root=$ROOT db=$DB horizon=$HORIZON"

  rc=0
  echo "--- scrape-comps ---"
  wp_price --db "$DB" scrape-comps --horizon "$HORIZON" || rc=$?

  if [[ $rc -ne 0 ]]; then
    echo "FAILED scrape_rc=$rc"
    alert "wp-price scrape-comps job failed (rc=$rc). See $LOG"
  else
    echo "OK"
  fi
  echo "===== done rc=$rc ====="
  exit "$rc"
} >>"$LOG" 2>&1
