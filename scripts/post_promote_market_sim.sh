#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT"
PY="$ROOT/.venv/bin/python"
RUN="${RUN:-$HOME/wp-price-runs/market_sim/post_promote_$(git -C "$ROOT" rev-parse --short HEAD)}"
CAND="$ROOT/config/policies/candidates/cloud9_overlook_lower_peak_ceiling.yaml"

mkdir -p "$RUN"

log() { echo "[$(date -Iseconds)] $*"; }

log "post_promote normal default vs candidate overlay"
"$PY" -m src.cli.main proving-ground market \
  --scenario normal --seeds 30 --workers 7 --policy engine \
  --output-dir "$RUN/default_normal_1_30"

"$PY" -m src.cli.main proving-ground market \
  --scenario normal --seeds 30 --workers 7 --policy engine \
  --engine-policy "$CAND" \
  --output-dir "$RUN/overlay_normal_1_30"

"$PY" "$ROOT/scripts/audit_market_sim.py" \
  "$RUN/overlay_normal_1_30/scoreboard.csv" \
  --reference "$RUN/default_normal_1_30/scoreboard.csv" \
  --expect-seeds 30 --expect-scenarios 1 --seeds-from 6 --engine-only \
  --json "$RUN/overlay_normal_audit_seeds_6_30.json"

"$PY" "$ROOT/scripts/paired_market_sim.py" \
  "$RUN/overlay_normal_1_30/scoreboard.csv" \
  "$RUN/default_normal_1_30/scoreboard.csv" \
  --seeds-from 6 \
  --json "$RUN/overlay_normal_paired_seeds_6_30.json"

for SCENARIO in holiday_shift den_capacity_cut regime_change pandemic_collapse price_war; do
  log "scenario $SCENARIO default"
  "$PY" -m src.cli.main proving-ground market \
    --scenario "$SCENARIO" --seeds 30 --workers 7 --policy engine \
    --output-dir "$RUN/default_${SCENARIO}_1_30"

  log "scenario $SCENARIO overlay"
  "$PY" -m src.cli.main proving-ground market \
    --scenario "$SCENARIO" --seeds 30 --workers 7 --policy engine \
    --engine-policy "$CAND" \
    --output-dir "$RUN/overlay_${SCENARIO}_1_30"

  "$PY" "$ROOT/scripts/audit_market_sim.py" \
    "$RUN/overlay_${SCENARIO}_1_30/scoreboard.csv" \
    --reference "$RUN/default_${SCENARIO}_1_30/scoreboard.csv" \
    --expect-seeds 30 --expect-scenarios 1 --seeds-from 6 --engine-only \
    --json "$RUN/overlay_${SCENARIO}_audit_seeds_6_30.json"

  "$PY" "$ROOT/scripts/paired_market_sim.py" \
    "$RUN/overlay_${SCENARIO}_1_30/scoreboard.csv" \
    "$RUN/default_${SCENARIO}_1_30/scoreboard.csv" \
    --seeds-from 6 \
    --json "$RUN/overlay_${SCENARIO}_paired_seeds_6_30.json"
done

log "diagnostic retain normal seeds 1-6"
"$PY" -m src.cli.main proving-ground market \
  --scenario normal --seeds 6 --workers 2 --policy engine \
  --retain-dbs normal --output-dir "$RUN/default_normal_diagnostic"

"$PY" -m src.cli.main proving-ground market \
  --scenario normal --seeds 6 --workers 2 --policy engine \
  --engine-policy "$CAND" \
  --retain-dbs normal --output-dir "$RUN/overlay_normal_diagnostic"

log "done post_promote matrix at $RUN"
