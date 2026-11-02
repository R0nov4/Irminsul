#!/usr/bin/env bash
# Usage: shot-menu.sh /path/to/screenshot.png
set -u
FILE="${1:-}"
[ -f "$FILE" ] || exit 1
DIR="$(dirname "$FILE")"
NAME="$(basename "$FILE")"
THEME="$HOME/.config/rofi-genshin/shot-menu.rasi"

say() { notify-send -a "Paimon" -i "$FILE" "$1" "$2"; }

# ── preview: a thumbnail with the EXACT size of the frame (500x214) ──
# Any screenshot (any monitor, region or aspect ratio) is letterboxed into it,
# so rofi never has leftover space to fill with a repeated copy of the image.
TW=500; TH=214; CW=2500
PREVIEW="$FILE"; SCALE="both"
THUMB="$(mktemp --suffix=.png "${XDG_RUNTIME_DIR:-/tmp}/kamera-preview.XXXXXX")"
trap 'rm -f "$THUMB"' EXIT
IM=""
command -v magick  >/dev/null 2>&1 && IM="magick"
[ -z "$IM" ] && command -v convert >/dev/null 2>&1 && IM="convert"
if [ -n "$IM" ] && "$IM" "$FILE" -resize "${TW}x${TH}" -background none -gravity center -extent "${TW}x${TH}" -gravity west -extent "${CW}x${TH}" "$THUMB" 2>/dev/null; then
    PREVIEW="$THUMB"; SCALE="height"
fi

choice=$(printf '%s\n' \
    "✦  Edit in Kamera (Swappy)" \
    "❖  Copy Image" \
    "❖  Copy File Path" \
    "❖  Extract Text (OCR)" \
    "❖  Scan QR Code" \
    "❖  Save As…" \
    "❖  Open in Viewer" \
    "❖  Open Screenshots Folder" \
    "✧  Delete" \
    "✧  Close" \
  | rofi -dmenu -i -no-custom -p "✦ Kamera" \
        -mesg "<span foreground='#d3bc8e'>✦ Paimon:</span> $NAME" \
        -theme "$THEME" \
        -theme-str "imagebox { background-image: url(\"$PREVIEW\", $SCALE); } inputbar { enabled: false; }")

case "$choice" in
    *"Edit in Kamera"*)
        GTK_THEME=GenshinSwappy swappy -f "$FILE" -o "$FILE"
        ;;
    *"Copy Image"*)
        wl-copy --type image/png < "$FILE" && say "✦ Copied" "Image copied to clipboard"
        ;;
    *"Copy File Path"*)
        printf '%s' "$FILE" | wl-copy && say "✦ Copied" "$FILE"
        ;;
    *"Extract Text"*)
        "$HOME/.config/osd-genshin/ocr-popup.sh" "$FILE"
        ;;
    *"Scan QR"*)
        if ! command -v zbarimg >/dev/null 2>&1; then
            say "Paimon" "zbar is not installed"; exit 1
        fi
        qr=$(zbarimg --quiet --raw "$FILE" 2>/dev/null)
        if [ -n "$qr" ]; then
            printf '%s' "$qr" | wl-copy
            say "✦ QR Decoded & Copied" "$qr"
        else
            say "✦ Nothing Found" "No QR code was detected"
        fi
        ;;
    *"Save As"*)
        new=$(rofi -dmenu -p "✦ Name" -mesg "New file name (without extension)" \
              -theme "$THEME" \
              -theme-str 'previewcard { enabled: false; } listview { enabled: false; }' < /dev/null)
        new="${new//\//_}"
        if [ -n "$new" ]; then
            new="${new%.png}.png"
            if mv -n "$FILE" "$DIR/$new"; then say "✦ Renamed" "$new"; fi
        fi
        ;;
    *"Open in Viewer"*)
        setsid xdg-open "$FILE" >/dev/null 2>&1 &
        ;;
    *"Open Screenshots Folder"*)
        setsid xdg-open "$DIR" >/dev/null 2>&1 &
        ;;
    *"Delete"*)
        ok=$(printf '%s\n' "✦  Yes, delete it" "✧  Cancel" \
            | rofi -dmenu -i -no-custom -p "❖ Confirm" \
              -mesg "<span foreground='#d3bc8e'>Paimon:</span> Are you sure? $NAME" \
              -theme "$THEME" \
              -theme-str 'previewcard { enabled: false; } inputbar { enabled: false; }')
        if [[ "$ok" == *"Yes"* ]]; then
            gio trash "$FILE" 2>/dev/null || rm -f "$FILE"
            notify-send -a "Paimon" "✦ Deleted" "$NAME"
        fi
        ;;
    *) : ;;
esac
