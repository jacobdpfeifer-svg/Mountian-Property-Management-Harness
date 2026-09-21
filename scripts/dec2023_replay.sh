#!/usr/bin/env bash
# Dec 2023 Cloud 9 replay harness with Track A signal fixtures.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${1:-$ROOT/data/dec2023_run.db}"
FIX="$ROOT/tests/fixtures/signals"

cd "$ROOT"
export PYTHONPATH="$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: missing venv python at $PYTHON" >&2
  exit 1
fi

wp_price() {
  "$PYTHON" -c 'import sys; from src.cli.main import main; raise SystemExit(main(sys.argv[1:]))' "$@"
}

wp_price --db "$DB" init-db
wp_price --db "$DB" ingest-csv \
  --properties data/dec2023/properties.csv \
  --inventory data/dec2023/nightly_inventory.csv \
  --comps data/dec2023/comps.csv \
  --demand data/dec2023/demand_signals.csv
"$PYTHON" scripts/load_market_snapshots.py "$DB" data/dec2023/market_snapshots.csv

AS_OF=2023-11-15
wp_price --db "$DB" signals run --collector resort --market grand_home \
  --as-of "$AS_OF" --fixture "$FIX/winter_park_resort.json"
wp_price --db "$DB" signals run --collector cdot --market grand_home \
  --as-of "$AS_OF" --fixture "$FIX/cdot_closure.json"
wp_price --db "$DB" signals promote

wp_price --db "$DB" signals rescore --from 2023-11-01 --to 2023-11-28
wp_price --db "$DB" recommend --from 2023-12-01 --to 2023-12-31 \
  --property cloud_9 --allow-past

echo "Replay complete: $DB"
