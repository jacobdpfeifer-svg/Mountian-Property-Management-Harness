#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT"
PY="$ROOT/.venv/bin/python"
RUN="${RUN:-$HOME/wp-price-runs/market_sim/sensitivity_$(git -C "$ROOT" rev-parse --short HEAD)}"
SENS="$ROOT/config/market_sim/sensitivity"

mkdir -p "$RUN"
exec > >(tee -a "$RUN/run.log") 2>&1

for f in "$SENS"/*.yaml; do
  name="$(basename "$f" .yaml)"
  log_out="$RUN/sensitivity_$name"
  echo "[$(date -Iseconds)] sensitivity $name"
  "$PY" -m src.cli.main proving-ground market \
    --scenario normal --seeds 5 --workers 7 --grid \
    --sensitivity "$f" \
    --output-dir "$log_out"
done

echo "[$(date -Iseconds)] done sensitivity grid at $RUN"
