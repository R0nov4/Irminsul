#!/usr/bin/env bash
# استفاده:
#   clipboard.sh        (نمایش تاریخچه و کپی مورد انتخاب‌شده - Super+V)
#   clipboard.sh --wipe (پاک کردن کل تاریخچه یا مدیریت - Super+Shift+V)

set -u
THEME="$HOME/.config/rofi-genshin/clipboard.rasi"

# اگر Rofi باز است، با زدن دوباره کلید بسته شود
if pgrep -x rofi >/dev/null 2>&1; then
    pkill -x rofi
    exit 0
fi

if ! command -v cliphist >/dev/null 2>&1; then
    notify-send -a "Paimon" "Clipboard" "cliphist is not installed (sudo pacman -S cliphist)"
    exit 1
fi

if [ "${1:-}" = "--wipe" ]; then
    choice=$(printf "✦ Clear Entire Clipboard Archive\n✦ Cancel" | rofi -dmenu -p "❖ Archive" -theme "$THEME")
    if [[ "$choice" == *"Clear"* ]]; then
        cliphist wipe
        notify-send -a "Paimon" "Teyvat Archive" "Clipboard history cleared."
    fi
    exit 0
fi

sel=$(cliphist list | rofi -dmenu -p "✦ Archive" -theme "$THEME")
[ -z "$sel" ] && exit 0

printf "%s" "$sel" | cliphist decode | wl-copy
