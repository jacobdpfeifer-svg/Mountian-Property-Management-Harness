#!/bin/bash
# Deploy the daily pacing job to a launchd-readable path and kick it once.
#
# macOS TCC blocks LaunchAgents from iCloud Desktop, so the live runtime lives in
# ~/Library/Application Support/wp-price and the workspace DB is a symlink to it.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${WP_PRICE_RUNTIME:-$HOME/Library/Application Support/wp-price}"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.wpprice.pacing.plist"
LABEL="gui/$(id -u)/com.wpprice.pacing"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3.12}"

mkdir -p "$DEST"/{data/logs,src,config,scripts} "${HOME}/Library/LaunchAgents"

rsync -a --delete \
  --exclude '.venv/' \
  --exclude '.git/' \
  --exclude 'data/*.db' \
  --exclude 'data/logs/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  "$REPO/src/" "$DEST/src/"
rsync -a "$REPO/config/" "$DEST/config/"
cp "$REPO/pyproject.toml" "$DEST/pyproject.toml"
cp "$REPO/scripts/daily_pacing.sh" "$DEST/scripts/daily_pacing.sh"
cp "$REPO/scripts/daily_scrape.sh" "$DEST/scripts/daily_scrape.sh"
chmod +x "$DEST/scripts/daily_pacing.sh" "$DEST/scripts/daily_scrape.sh"
if [[ -f "$REPO/.env" ]]; then
  cp "$REPO/.env" "$DEST/.env"
fi
if [[ -f "$REPO/data/.guesty_token.json" ]]; then
  mkdir -p "$DEST/data"
  cp "$REPO/data/.guesty_token.json" "$DEST/data/.guesty_token.json"
fi

# Canonical DB is the runtime copy. Point the workspace file at it so CLI and
# launchd share one database.
mkdir -p "$DEST/data"
if [[ -f "$REPO/data/wp_pricing.db" && ! -L "$REPO/data/wp_pricing.db" ]]; then
  if [[ ! -f "$DEST/data/wp_pricing.db" ]]; then
    cp "$REPO/data/wp_pricing.db" "$DEST/data/wp_pricing.db"
  else
    # Keep whichever copy is newer so an install does not clobber a later job run.
    if [[ "$REPO/data/wp_pricing.db" -nt "$DEST/data/wp_pricing.db" ]]; then
      cp "$REPO/data/wp_pricing.db" "$DEST/data/wp_pricing.db"
    fi
  fi
  mv "$REPO/data/wp_pricing.db" "$REPO/data/wp_pricing.db.icloud-backup"
fi
ln -sfn "$DEST/data/wp_pricing.db" "$REPO/data/wp_pricing.db"

if [[ ! -x "$DEST/.venv/bin/python" ]]; then
  "$PYTHON" -m venv "$DEST/.venv"
fi
"$DEST/.venv/bin/python" -m pip install -q -U pip
"$DEST/.venv/bin/python" -m pip install -q -e "$DEST[scrape]"

VERIFY_SINCE="${PACING_VERIFY_SINCE:-2026-09-20}"
cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.wpprice.pacing</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${DEST}/scripts/daily_pacing.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${DEST}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>5</integer>
  </dict>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PACING_VERIFY_SINCE</key>
    <string>${VERIFY_SINCE}</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key>
  <string>${DEST}/data/logs/pacing-launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${DEST}/data/logs/pacing-launchd.err.log</string>
  <key>RunAtLoad</key>
  <false/>
  <key>Nice</key>
  <integer>5</integer>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
EOF

launchctl bootout "$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
launchctl enable "$LABEL"
launchctl kickstart -k "$LABEL"
echo "Installed $PLIST_DEST"

# Comp refresh: same daily cadence as pacing, later so the unrecoverable
# snapshot is never blocked by a long Airbnb sweep. One job covers all three
# listings' Airbnb comps (Cloud 9 + twins).
SCRAPE_PLIST="${HOME}/Library/LaunchAgents/com.wpprice.scrape.plist"
SCRAPE_LABEL="gui/$(id -u)/com.wpprice.scrape"
cat > "$SCRAPE_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.wpprice.scrape</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${DEST}/scripts/daily_scrape.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${DEST}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>7</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>SCRAPE_HORIZON_DAYS</key>
    <string>${SCRAPE_HORIZON_DAYS:-120}</string>
  </dict>
  <key>StandardOutPath</key>
  <string>${DEST}/data/logs/scrape-launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${DEST}/data/logs/scrape-launchd.err.log</string>
  <key>RunAtLoad</key>
  <false/>
  <key>Nice</key>
  <integer>5</integer>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
EOF

launchctl bootout "$SCRAPE_LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$SCRAPE_PLIST"
launchctl enable "$SCRAPE_LABEL"
# Do not kickstart scrape here: a 120-day sweep is slow and must not race
# the pacing kickstart. First run is the 07:00 calendar interval (or
# `launchctl kickstart -k $SCRAPE_LABEL` when you want one immediately).
echo "Installed $SCRAPE_PLIST"
echo "Runtime $DEST"
launchctl print "$LABEL" | sed -n '1,35p'
echo "--- scrape ---"
launchctl print "$SCRAPE_LABEL" | sed -n '1,35p'
