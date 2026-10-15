#!/bin/bash
# Refresh the code the daily launchd jobs run, and prove the copy works.
#
# The daily jobs (com.wpprice.pacing, com.wpprice.scrape) run from
# ~/Library/Application Support/wp-price, not from this repo (macOS TCC blocks
# LaunchAgents from iCloud). Nothing refreshed that copy after 2026-09-20, so the
# jobs ran month-old code (2026-10-14 audit: 47 files out of date).
#
# This script only updates code and config. It never copies secrets (.env, the
# Guesty token), never touches a database, and never rewrites the launchd
# schedules — scripts/install_pacing_schedule.sh does first-time setup.
#
#   scripts/deploy_runtime.sh              # refuses an uncommitted tree
#   scripts/deploy_runtime.sh --allow-dirty
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${WP_PRICE_RUNTIME:-$HOME/Library/Application Support/wp-price}"
ALLOW_DIRTY=0
[[ "${1:-}" == "--allow-dirty" ]] && ALLOW_DIRTY=1

cd "$REPO"
SHA="$(git rev-parse HEAD)"
DIRTY="$(git status --porcelain --untracked-files=no)"
if [[ -n "$DIRTY" && $ALLOW_DIRTY -eq 0 ]]; then
  echo "Refusing to deploy uncommitted changes (commit first, or pass --allow-dirty):" >&2
  echo "$DIRTY" >&2
  exit 2
fi
if [[ ! -x "$DEST/.venv/bin/python" ]]; then
  echo "No runtime at $DEST. Run scripts/install_pacing_schedule.sh for first-time setup." >&2
  exit 2
fi

echo "Deploying $SHA${DIRTY:+ (dirty)} to $DEST"
rsync -a --delete --exclude '__pycache__/' --exclude '* 2.*' "$REPO/src/" "$DEST/src/"
rsync -a --exclude '* 2.*' "$REPO/config/" "$DEST/config/"
cp "$REPO/pyproject.toml" "$DEST/pyproject.toml"
for script in daily_pacing.sh daily_scrape.sh production_preflight.py; do
  cp "$REPO/scripts/$script" "$DEST/scripts/$script"
done
chmod +x "$DEST/scripts/daily_pacing.sh" "$DEST/scripts/daily_scrape.sh"
"$DEST/.venv/bin/python" -m pip install -q -e "$DEST[scrape]"

# Smoke test the deployed copy itself, not the repo.
(cd "$DEST" && PYTHONPATH="$DEST" "$DEST/.venv/bin/python" -c \
  'import src.cli.main, src.pacing, src.scrape.properties; print("imports OK")')
(cd "$DEST" && PYTHONPATH="$DEST" "$DEST/.venv/bin/python" scripts/production_preflight.py) || {
  echo "WARNING: preflight failed on the deployed copy (see above). The rate-cap check" >&2
  echo "fails on purpose while the default peak caps sit below real listed prices." >&2
}

printf '%s\n%s\n%s\n' "$SHA" "${DIRTY:+dirty}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DEST/DEPLOYED_SHA"
echo "Recorded $DEST/DEPLOYED_SHA"
