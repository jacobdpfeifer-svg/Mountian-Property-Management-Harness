#!/usr/bin/env bash
# Confirm the seasonal base anchor candidate against the promoted default on
# seeds 6-30 (seeds 1-5 picked it). Reference runs come from the post-promote
# matrix, which used the same promoted default.yaml.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT"
PY="$ROOT/.venv/bin/python"
SHA="$(git -C "$ROOT" rev-parse --short HEAD)"
RUN="${RUN:-$HOME/wp-price-runs/market_sim/confirm_base_anchor_$SHA}"
REF="${REF:-$HOME/wp-price-runs/market_sim/post_promote_$SHA}"
CAND="$ROOT/config/policies/candidates/seasonal_base_anchor_full_shoulder.yaml"

mkdir -p "$RUN"
exec > >(tee -a "$RUN/run.log") 2>&1

for SCENARIO in normal price_war holiday_shift den_capacity_cut regime_change pandemic_collapse; do
  echo "[$(date -Iseconds)] $SCENARIO candidate"
  "$PY" -m src.cli.main proving-ground market \
    --scenario "$SCENARIO" --seeds 30 --workers 7 --policy engine \
    --engine-policy "$CAND" \
    --output-dir "$RUN/candidate_${SCENARIO}_1_30"

  "$PY" "$ROOT/scripts/audit_market_sim.py" \
    "$RUN/candidate_${SCENARIO}_1_30/scoreboard.csv" \
    --reference "$REF/default_${SCENARIO}_1_30/scoreboard.csv" \
    --expect-seeds 30 --expect-scenarios 1 --seeds-from 6 --engine-only \
    --json "$RUN/candidate_${SCENARIO}_audit_seeds_6_30.json"

  "$PY" "$ROOT/scripts/paired_market_sim.py" \
    "$RUN/candidate_${SCENARIO}_1_30/scoreboard.csv" \
    "$REF/default_${SCENARIO}_1_30/scoreboard.csv" \
    --seeds-from 6 \
    --json "$RUN/candidate_${SCENARIO}_paired_seeds_6_30.json"
done

echo "[$(date -Iseconds)] done base anchor confirmation at $RUN"
