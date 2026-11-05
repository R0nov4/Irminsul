#!/usr/bin/env bash
# =============================================================================
# weather.sh — Teyvat Forecast shim for the Waybar "custom/weather" module.
#
# This REPLACES the original standalone fetcher (kept as weather.sh.teyvat-orig.bak
# by install.sh). It reads the shared cache that also feeds the Quickshell
# popup, so the bar and the popup never make duplicate requests.
#
# Output format is 100% identical to the original script:
#   {"text":"23°","tooltip":"City\nClear\nFeels like 22°\n...","class":[...]}
# CSS classes stay the same: day|night + clear|cloud|fog|rain|snow|storm [+offline]
# =============================================================================
set -u

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/teyvat-forecast"
JSON="$CACHE_DIR/weather.json"
FETCH="${TEYVAT_FETCH:-$HOME/.config/teyvat-forecast/teyvat-fetch.py}"
MAX_AGE=1500   # seconds; 25 min = fetch cadence (12 min) + generous slack

file_age() {  # seconds since mtime, or a huge number
  local now
  now=$(date +%s)
  local m
  m=$(stat -c %Y "$1" 2>/dev/null) || { echo 9999999; return; }
  echo $(( now - m ))
}

# --- decide whether we need to heal the cache ourselves --------------------- #
# (never while a preview is active — fake data is intentional then)
need_fetch=0
if [ ! -s "$JSON" ]; then
  need_fetch=1
elif ! jq -e '(.preview // false) == true' "$JSON" >/dev/null 2>&1; then
  [ "$(file_age "$JSON")" -gt "$MAX_AGE" ] && need_fetch=1
  jq -e '(.stale // false) == true' "$JSON" >/dev/null 2>&1 && need_fetch=1
fi

if [ "$need_fetch" = 1 ] && command -v python3 >/dev/null 2>&1 && [ -f "$FETCH" ]; then
  # Self-heal: the systemd timer should normally keep this fresh. If it is
  # disabled or failed, the bar still recovers on its own exec interval.
  timeout 14 python3 "$FETCH" fetch --wait-lock 8 >/dev/null 2>&1
fi

# --- emit Waybar JSON (normal path) ----------------------------------------- #
if [ -s "$JSON" ] && jq -e '.waybar.text' "$JSON" >/dev/null 2>&1; then
  jq -c '{text: .waybar.text, tooltip: .waybar.tooltip,
          class: (.waybar.classes + (if (.stale // false) then ["offline"] else [] end))}' "$JSON"
  exit 0
fi

# --- last resort: same offline output as the original script ---------------- #
jq -nc '{text:"--°",tooltip:"Weather unavailable",class:["day","offline"]}'
