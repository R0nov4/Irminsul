#!/usr/bin/env bash
# forecast: the files are copied by the main install.sh; this only turns on the refresh timer.
command -v systemctl >/dev/null 2>&1 || { echo "   forecast: no systemctl, timer skipped"; exit 0; }
systemctl --user daemon-reload
systemctl --user enable --now teyvat-forecast-fetch.timer >/dev/null 2>&1 \
  && echo "   forecast: refresh timer enabled" \
  || echo "   forecast: could not enable the timer (no user session?)"
# first fetch so the popup has data right away
python3 "$HOME/.config/teyvat-forecast/teyvat-fetch.py" fetch >/dev/null 2>&1 || true
exit 0
