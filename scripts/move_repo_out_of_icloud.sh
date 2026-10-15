#!/bin/bash
# Move the working repo out of iCloud Drive, without deleting anything.
#
# Why: iCloud makes "name 2.py" conflict copies (113 on 2026-10-14; plain pytest
# collected 53 duplicate tests) and the venv's absolute shebangs break when the
# folder syncs or moves. The daily jobs already run from ~/Library/Application
# Support/wp-price and are unaffected.
#
# What it does: clones the COMMITTED repo to the new place (conflict copies are
# untracked, so they do not come along), points origin at GitHub, rebuilds the
# venv, copies the local-only files git does not track, and runs the quality
# gates there. The old iCloud folder is left in place: delete it yourself once
# the new copy is working.
#
#   scripts/move_repo_out_of_icloud.sh [~/code/harness]
set -euo pipefail

OLD="$(cd "$(dirname "$0")/.." && pwd)"
NEW="${1:-$HOME/code/harness}"
NEW="${NEW/#\~/$HOME}"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3.12}"

cd "$OLD"
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "Commit (or stash) tracked changes first; a clone only carries commits." >&2
  git status --short --untracked-files=no >&2
  exit 2
fi
if [[ -e "$NEW" ]]; then
  echo "$NEW already exists; pick another path." >&2
  exit 2
fi
ORIGIN="$(git remote get-url origin)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

mkdir -p "$(dirname "$NEW")"
git clone --branch "$BRANCH" "$OLD" "$NEW"
git -C "$NEW" remote set-url origin "$ORIGIN"
git -C "$NEW" fetch origin --quiet || echo "note: could not fetch origin (offline?)"

# Local-only files git does not track. Secrets are copied, never printed.
for rel in .env data/.guesty_token.json; do
  if [[ -f "$OLD/$rel" ]]; then
    mkdir -p "$NEW/$(dirname "$rel")"
    cp -p "$OLD/$rel" "$NEW/$rel"
  fi
done
# Gitignored, business-confidential folders (not in the public repo).
for rel in data/exports data/cloud9 data/dec2023 config/local; do
  if [[ -d "$OLD/$rel" ]]; then
    mkdir -p "$NEW/$rel"
    cp -Rp "$OLD/$rel/." "$NEW/$rel/"
  fi
done
# The operator database lives in the runtime; the repo only links to it.
if [[ -L "$OLD/data/wp_pricing.db" ]]; then
  mkdir -p "$NEW/data"
  ln -sfn "$(readlink "$OLD/data/wp_pricing.db")" "$NEW/data/wp_pricing.db"
fi

"$PYTHON" -m venv "$NEW/.venv"
"$NEW/.venv/bin/python" -m pip install -q -U pip
"$NEW/.venv/bin/python" -m pip install -q -e "$NEW[dev,scrape]"

(cd "$NEW" && PYTHONPATH=. .venv/bin/python scripts/quality_gates.py)

cat <<EOF

New working copy: $NEW (branch $BRANCH, origin $ORIGIN)
Next:
  1. Open $NEW in your editor and work there from now on.
  2. When you are satisfied, delete the old iCloud folder yourself:
     $OLD
  3. Daily jobs are unaffected (they run from ~/Library/Application Support/wp-price).
     Deploy from the new copy with: scripts/deploy_runtime.sh
EOF
