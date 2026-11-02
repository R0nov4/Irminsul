#!/usr/bin/env bash
# p = all monitors | m = focused monitor | s / sf = select region
set -u
MODE="${1:-s}"
SAVE_DIR="${XDG_PICTURES_DIR:-$HOME/Pictures}/Screenshots"
mkdir -p "$SAVE_DIR"
FILE="$SAVE_DIR/Genshin_$(date +%Y%m%d_%H%M%S).png"

pgrep -x swappy >/dev/null 2>&1 && pkill -x swappy
pgrep -x rofi   >/dev/null 2>&1 && pkill -x rofi

case "$MODE" in
    p)
        grim "$FILE"
        ;;
    m)
        mon=$(hyprctl monitors -j 2>/dev/null | jq -r '.[] | select(.focused == true) | .name' 2>/dev/null)
        if [ -n "$mon" ]; then grim -o "$mon" "$FILE"; else grim "$FILE"; fi
        ;;
    *)
        geom=$(slurp -b 161a2666 -c d3bc8eff -w 2 2>/dev/null) || exit 0
        [ -z "$geom" ] && exit 0
        grim -g "$geom" "$FILE"
        ;;
esac

[ -s "$FILE" ] || exit 1
wl-copy --type image/png < "$FILE" 2>/dev/null || true
notify-send -a "Paimon" -i "$FILE" "✦ Kamera Captured" "Saved & copied to clipboard"

setsid "$HOME/.config/osd-genshin/shot-menu.sh" "$FILE" >/dev/null 2>&1 &
