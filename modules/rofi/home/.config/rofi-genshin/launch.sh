#!/usr/bin/env bash
DIR="$HOME/.config/rofi-genshin"
MODE="${1:-drun}"

# اگه باز بود، ببندش (toggle)
if pgrep -x rofi >/dev/null; then
    pkill -x rofi
    exit 0
fi

# کراپ تصویر: center | west | east | north | south | northwest ...
GRAVITY="center"

# ── انتخاب آرت: اول art.* دستی، بعد والپیپر فعلی ──
SRC=""
for f in "$DIR"/art.png "$DIR"/art.jpg "$DIR"/art.jpeg "$DIR"/art.webp; do
    [ -f "$f" ] && SRC="$f" && break
done
if [ -z "$SRC" ]; then
    for f in "$HOME/.cache/hyde/wall.set" "$HOME/.cache/hyde/wall.thmb"; do
        [ -e "$f" ] && SRC="$(realpath "$f" 2>/dev/null || echo "$f")" && break
    done
fi
if [ -z "$SRC" ]; then
    SRC="$(find "$HOME/.cache/hyde/" \( -name '*.png' -o -name '*.jpg' -o -name '*.webp' \) 2>/dev/null | head -n 1)"
fi

# ── کراپ پرتره (کش میشه، فقط وقتی والپیپر عوض بشه دوباره ساخته میشه) ──
IMG="$SRC"
SCALE="height"
IM=""
command -v magick  >/dev/null 2>&1 && IM="magick"
[ -z "$IM" ] && command -v convert >/dev/null 2>&1 && IM="convert"
if [ -n "$SRC" ] && [ -n "$IM" ]; then
    KEY="$(printf '%s' "$SRC$(stat -c %Y "$SRC" 2>/dev/null)$GRAVITY" | md5sum | cut -c1-12)"
    OUT="$DIR/cache/panel-$KEY.png"
    if [ ! -f "$OUT" ]; then
        rm -f "$DIR"/cache/panel-*.png
        "$IM" "${SRC}[0]" -resize 920x1164^ -gravity "$GRAVITY" -extent 920x1164 "$OUT" 2>/dev/null
    fi
    if [ -f "$OUT" ]; then
        IMG="$OUT"
        SCALE="both"
    fi
fi

# ── پیام Paimon ──
H=$((10#$(date +%H)))
if   [ "$H" -ge 5 ]  && [ "$H" -lt 12 ]; then GREET="Good morning"
elif [ "$H" -ge 12 ] && [ "$H" -lt 18 ]; then GREET="Good afternoon"
elif [ "$H" -ge 18 ] && [ "$H" -lt 23 ]; then GREET="Good evening"
else GREET="Still awake"
fi
QUOTES=(
    "Where to next?"
    "Ehe! Pick something already!"
    "Paimon is ready when you are."
    "Adventure awaits!"
    "Don't forget the Emergency Food!"
    "Let's go, let's go!"
)
QUOTE="${QUOTES[RANDOM % ${#QUOTES[@]}]}"

ARGS=(
    -show "$MODE"
    -theme "$DIR/theme.rasi"
    -mesg "<b>${GREET}, Traveler!</b>  ${QUOTE}"
    -theme-str "textbox-time { str: \"$(LC_ALL=C date +%H:%M)\"; }"
    -theme-str "textbox-date { str: \"$(LC_ALL=C date '+%A, %d %B')\"; }"
)
[ -n "$IMG" ] && ARGS+=( -theme-str "imgbox { background-image: url(\"$IMG\", $SCALE); }" )

exec rofi "${ARGS[@]}"
