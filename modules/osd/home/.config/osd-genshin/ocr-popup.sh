#!/usr/bin/env bash
# Usage: ocr-popup.sh /path/to/screenshot.png
set -u
FILE="${1:-}"
[ -f "$FILE" ] || exit 1
THEME="$HOME/.config/rofi-genshin/shot-menu.rasi"

say() { notify-send -a "Paimon" -i "$FILE" "$1" "$2"; }

if ! command -v tesseract >/dev/null 2>&1; then
    say "Paimon" "tesseract is not installed"
    exit 1
fi

text=$(tesseract "$FILE" - -l eng+fas 2>/dev/null)
[ -z "${text//[[:space:]]/}" ] && text=$(tesseract "$FILE" - -l eng 2>/dev/null)

mapfile -t TXT_LINES < <(printf '%s\n' "$text" | sed 's/[[:space:]]*$//' | sed '/^$/d')
if [ "${#TXT_LINES[@]}" -eq 0 ]; then
    say "✦ Nothing Found" "No text was detected in the image"
    exit 0
fi

# Full text is on the clipboard from the start
printf '%s\n' "${TXT_LINES[@]}" | wl-copy

ACTIONS=(
    "✦  Copy All Text"
    "✦  Copy as One Line"
    "✦  Edit in Editor"
    "✦  Save as .txt"
)
NA=${#ACTIONS[@]}

sel=$(printf '%s\n' "${ACTIONS[@]}" "${TXT_LINES[@]}" | rofi -dmenu -i -multi-select -no-custom \
    -format i -p "✦ Text" \
    -mesg "<span foreground='#d3bc8e'>✦ Paimon:</span> ${#TXT_LINES[@]} lines found | Enter = copy line | Shift+Enter = multi-select" \
    -theme "$THEME" \
    -theme-str 'imagebox { enabled: false; } listview { lines: 12; }')

[ -z "$sel" ] && exit 0

act=-1
picked=()
while IFS= read -r i; do
    [ -z "$i" ] && continue
    if [ "$i" -lt "$NA" ]; then
        [ "$act" -lt 0 ] && act="$i"
    else
        picked+=("${TXT_LINES[$((i - NA))]}")
    fi
done <<< "$sel"

case "$act" in
    0)
        printf '%s\n' "${TXT_LINES[@]}" | wl-copy
        say "✦ All Text Copied" "${#TXT_LINES[@]} lines"
        ;;
    1)
        one=$(printf '%s\n' "${TXT_LINES[@]}" | paste -sd' ')
        printf '%s' "$one" | wl-copy
        say "✦ Copied as One Line" "${one:0:120}"
        ;;
    2)
        TMP="$(mktemp --suffix=.txt)"
        printf '%s\n' "${TXT_LINES[@]}" > "$TMP"
        if command -v kitty >/dev/null 2>&1; then
            setsid kitty -e "${EDITOR:-nvim}" "$TMP" >/dev/null 2>&1 &
        else
            setsid xdg-open "$TMP" >/dev/null 2>&1 &
        fi
        ;;
    3)
        OUT="${FILE%.png}.txt"
        printf '%s\n' "${TXT_LINES[@]}" > "$OUT"
        say "✦ Text Saved" "$(basename "$OUT")"
        ;;
    *)
        if [ "${#picked[@]}" -gt 0 ]; then
            joined=$(printf '%s\n' "${picked[@]}")
            printf '%s' "$joined" | wl-copy
            say "✦ ${#picked[@]} Line(s) Copied" "${joined//$'\n'/ | }"
        fi
        ;;
esac
