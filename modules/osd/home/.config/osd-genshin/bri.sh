#!/usr/bin/env bash
# استفاده: bri.sh [up|down] [step]
ACTION="${1:-up}"
STEP="${2:-5}"
R="$HOME/.config/osd-genshin/render.sh"

if command -v brightnessctl >/dev/null 2>&1; then
    case "$ACTION" in
        up|i)   brightnessctl -q set "${STEP}%+" ;;
        down|d) brightnessctl -q set "${STEP}%-" ;;
    esac
    CUR=$(brightnessctl get 2>/dev/null || echo 0)
    MAX=$(brightnessctl max 2>/dev/null || echo 100)
    BRI=$(( (CUR * 100 + MAX / 2) / MAX ))
else
    BRI=100
fi

IMG=$("$R" bri "$BRI")
notify-send -a "." -t 1800 \
    -h string:x-dunst-stack-tag:genshin-osd-bri \
    -i "$IMG" "Sacred Light · ${BRI}%"
