#!/usr/bin/env bash
DIR="$HOME/.config/hyprlock-genshin"

# اگه قفل از قبل فعاله، دوباره نساز
FORCE=0; [ "$1" = "--force" ] && FORCE=1
mkdir -p "$DIR/cache"
LOG="$DIR/cache/launch.log"
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/hyprlock-launch.lock"
flock -n 9 || exit 0   # یه launch دیگه همزمان در حال راه‌اندازیه
if pidof hyprlock >/dev/null 2>&1; then
    { echo "$(date '+%F %T') blocked by running hyprlock:"; ps -o pid=,etime=,stat= -C hyprlock; } >> "$LOG" 2>&1
    if [ "$FORCE" = 1 ]; then
        pkill -x hyprlock; sleep 0.3
    else
        notify-send -a Paimon "Lock" "hyprlock is already running (see $LOG)" >/dev/null 2>&1 || true
        exit 0
    fi
fi
hyprctl switchxkblayout all 0 >/dev/null 2>&1 || true

mkdir -p "$DIR/cache"

# ── پس‌زمینه ──
# ۱) عکس ثابت دستی  ۲) عکس ساعتی بازی  ۳) والپیپر فعلی HyDE
BG=""
for f in "$DIR"/bg.png "$DIR"/bg.jpg "$DIR"/bg.jpeg "$DIR"/bg.webp; do
    [ -f "$f" ] && BG="$f" && break
done

if [ -z "$BG" ]; then
    H=$((10#$(date +%H)))
    # ساعت‌ها رو از اینجا می‌تونی عوض کنی
    if   [ "$H" -ge 5 ]  && [ "$H" -lt 8 ];  then T=dawn
    elif [ "$H" -ge 8 ]  && [ "$H" -lt 17 ]; then T=day
    elif [ "$H" -ge 17 ] && [ "$H" -lt 19 ]; then T=dusk
    else T=night
    fi
    [ -f "$DIR/assets/bg/$T.jpg" ] && BG="$DIR/assets/bg/$T.jpg"
fi

if [ -z "$BG" ] && [ -e "$HOME/.cache/hyde/wall.set" ]; then
    SRC="$(realpath "$HOME/.cache/hyde/wall.set" 2>/dev/null)"
    EXT="$(printf '%s' "${SRC##*.}" | tr 'A-Z' 'a-z')"
    case "$EXT" in
        png|jpg|jpeg|webp)
            rm -f "$DIR"/cache/bg-hyde.*
            cp -f "$SRC" "$DIR/cache/bg-hyde.$EXT" && BG="$DIR/cache/bg-hyde.$EXT"
            ;;
    esac
fi
[ -z "$BG" ] && BG="screenshot"

# ── لوگو: اگه logo.png هست، تو یه بوم مربع قرارش بده ──
LOGO=""
if [ -f "$DIR/logo.png" ]; then
    SQ="$DIR/cache/logo-square.png"
    if [ ! -f "$SQ" ] || [ "$DIR/logo.png" -nt "$SQ" ]; then
        IM=""
        command -v magick  >/dev/null 2>&1 && IM="magick"
        [ -z "$IM" ] && command -v convert >/dev/null 2>&1 && IM="convert"
        [ -n "$IM" ] && "$IM" "$DIR/logo.png" -background none -resize 1000x1000 \
            -gravity center -extent 1000x1000 "$SQ" 2>/dev/null
    fi
    [ -f "$SQ" ] && LOGO="$SQ"
fi

# ── ساخت کانفیگ نهایی ──
OUT="$DIR/cache/hyprlock.conf"
sed -e "s#__BG__#$BG#" -e "s#__LOGO__#$LOGO#" "$DIR/template.conf" > "$OUT"

if [ -n "$LOGO" ]; then
    sed -i '/# LOGOTXT_BEGIN/,/# LOGOTXT_END/d' "$OUT"
else
    sed -i '/# LOGO_BEGIN/,/# LOGO_END/d' "$OUT"
fi

# ویجت shape از hyprlock 0.5.0 به بعد هست
V="$(hyprlock --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n1)"
if [ -n "$V" ] && [ "$(printf '%s\n' 0.5.0 "$V" | sort -V | head -n1)" != "0.5.0" ]; then
    sed -i '/# SHAPE_BEGIN/,/# SHAPE_END/d' "$OUT"
fi

exec hyprlock -c "$OUT" 9>&-
