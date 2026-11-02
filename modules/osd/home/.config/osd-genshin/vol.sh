#!/usr/bin/env bash
# استفاده: vol.sh [up|down|mute] [step]
ACTION="${1:-up}"
STEP="${2:-5}"
R="$HOME/.config/osd-genshin/render.sh"

if command -v wpctl >/dev/null 2>&1; then
    case "$ACTION" in
        up|i)   wpctl set-mute @DEFAULT_AUDIO_SINK@ 0; wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ "${STEP}%+" ;;
        down|d) wpctl set-volume @DEFAULT_AUDIO_SINK@ "${STEP}%-" ;;
        mute|m) wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle ;;
    esac
    RAW=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null)
    VOL=$(awk '{printf "%d", $2 * 100 + 0.5}' <<< "$RAW")
    [[ "$RAW" == *"[MUTED]"* ]] && MUTED=1 || MUTED=0
elif command -v pamixer >/dev/null 2>&1; then
    case "$ACTION" in
        up|i)   pamixer -u; pamixer -i "$STEP" ;;
        down|d) pamixer -d "$STEP" ;;
        mute|m) pamixer -t ;;
    esac
    VOL=$(pamixer --get-volume 2>/dev/null || echo 0)
    [ "$(pamixer --get-mute 2>/dev/null)" = "true" ] && MUTED=1 || MUTED=0
fi

if [ "${MUTED:-0}" = "1" ] || [ "${VOL:-0}" -eq 0 ]; then
    IMG=$("$R" mute 0)
    notify-send -a "." -t 1800 \
        -h string:x-dunst-stack-tag:genshin-osd-mute \
        -i "$IMG" "Voice of Teyvat · Sealed"
else
    IMG=$("$R" vol "$VOL")
    notify-send -a "." -t 1800 \
        -h string:x-dunst-stack-tag:genshin-osd-vol \
        -i "$IMG" "Voice of Teyvat · ${VOL}%"
fi
