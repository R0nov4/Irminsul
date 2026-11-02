#!/usr/bin/env bash
# ✦ Genshin Wallpaper Engine — awww/swww standalone (بدون HyDE)
#
#   wallpaper.sh --start               دیمون رو بالا میاره، آخرین والپیپر رو برمی‌گردونه، واچر رو راه میندازه
#   wallpaper.sh --menu [region]       گالری Rofi (Super+Shift+W)
#   wallpaper.sh --set FILE            ست کردن یه عکس مشخص (FILE بدون فلگ هم کار می‌کنه)
#   wallpaper.sh --next | --prev       عکس بعدی/قبلی توی ریجن فعال
#   wallpaper.sh --random              عکس رندوم توی ریجن فعال
#   wallpaper.sh --wish                «ویش» رندوم با ستاره‌ی ناپایا (و شمارنده)
#   wallpaper.sh --daily               Daily Commission — والپیپر امروز (ریست ساعت ۴ صبح)
#   wallpaper.sh --region NAME         ریجن فعال رو عوض می‌کنه و یه عکس رندوم ازش میذاره
#   wallpaper.sh --mode off|rotate|daily|daynight
#   wallpaper.sh --import PATH [region]  کپی عکس/پوشه (مثلاً از تم‌های HyDE) توی کتابخونه
#   wallpaper.sh --sync                آرت Rofi و لاک‌اسکرین رو دوباره از والپیپر فعلی میسازه
#   wallpaper.sh --status
set -u
shopt -s nullglob

SELF=$(readlink -f "$0")
CFG_DIR="$HOME/.config/hypr-genshin"
CONF="$CFG_DIR/wallpaper.conf"
STATE="$HOME/.cache/hypr-genshin"
THUMBS="$STATE/thumbs-sq"
mkdir -p "$STATE" "$THUMBS"

NOTE_TITLE=""
NOTE_BODY=""
WALLS=()
PICK=""
GAL_RC=1
GAL_PATH=""

# ───────────── تنظیمات (قابل override توی wallpaper.conf) ─────────────
load_config() {
    WALL_DIR="$CFG_DIR/wallpapers"
    AUTO_MODE="off"                       # off | rotate | daily | daynight
    ROTATE_MINUTES=30
    DAY_START=6                           # روز: ۶ تا ۱۸ — مثل اسپلش بوت
    NIGHT_START=18
    TRANSITION="grow"                     # grow | outer | wipe | wave | fade | center | any | random
    TRANSITION_DURATION="1.6"
    TRANSITION_FPS=60
    TRANSITION_POS="center"
    TRANSITION_BEZIER=".43,1.19,1,.4"
    RESIZE="crop"
    FILTER="Lanczos3"
    ROFI_ART="$HOME/.config/rofi-genshin/art.png"
    LOCK_IMG="$STATE/lock.png"
    GALLERY_THEME="$HOME/.config/rofi-genshin/genshin-wallpaper.rasi"
    ICON_DIR="$CFG_DIR/icons"             # اختیاری: anemo.png geo.png electro.png dendro.png hydro.png pyro.png cryo.png
    SHOW_RARITY=1
    NOTIFY=1
    SOUND=""                              # اختیاری: مسیر یه فایل صوتی برای وقتی والپیپر عوض میشه
    # shellcheck disable=SC1090
    [ -f "$CONF" ] && . "$CONF" 2>/dev/null
    return 0
}
load_config

# ───────────── بک‌اند: awww (اسم جدید swww) یا swww ─────────────
if command -v awww >/dev/null 2>&1; then WP=awww; WPD=awww-daemon
elif command -v swww >/dev/null 2>&1; then WP=swww; WPD=swww-daemon
else WP=""; WPD=""; fi

IM=""
if command -v magick >/dev/null 2>&1; then IM=magick
elif command -v convert >/dev/null 2>&1; then IM=convert; fi

NJOBS=$(nproc 2>/dev/null || echo 4)

# ───────────── ریجن‌ها (هفت ملت) ─────────────
declare -A REGION_EL=( [mondstadt]=anemo [liyue]=geo [inazuma]=electro [sumeru]=dendro [fontaine]=hydro [natlan]=pyro [snezhnaya]=cryo )
declare -A EL_COLOR=( [anemo]='#74C2A8' [geo]='#F9B94A' [electro]='#B08FC2' [dendro]='#A5C83B' [hydro]='#4CC2F1' [pyro]='#EF7938' [cryo]='#9FD6E3' )

GAL_HINT="<span background='#ECE5D8' foreground='#2E3446'><b> Enter </b></span> Select      <span background='#ECE5D8' foreground='#2E3446'><b> Alt+R </b></span> Wish      <span background='#ECE5D8' foreground='#2E3446'><b> Alt+D </b></span> Daily Commission      <span background='#ECE5D8' foreground='#2E3446'><b> Alt+T </b></span> Regions      <span background='#ECE5D8' foreground='#2E3446'><b> Esc </b></span> Close"

# ───────────── ابزارهای کوچک ─────────────
notify() { # title body [icon]
    [ "${NOTIFY:-1}" = 1 ] || return 0
    command -v notify-send >/dev/null 2>&1 || return 0
    local a=(-a Paimon -h string:x-canonical-private-synchronous:genshin-wallpaper)
    [ -n "${3:-}" ] && a+=(-i "$3")
    notify-send "${a[@]}" "$1" "$2" >/dev/null 2>&1 || true
}

need_backend() {
    if [ -z "$WP" ]; then
        notify "✦ Paimon" "awww / swww is not installed"
        echo "awww/swww not found (swww was renamed to awww)" >&2
        exit 1
    fi
}

esc() { local s=$1; s=${s//&/&amp;}; s=${s//</&lt;}; s=${s//>/&gt;}; printf '%s' "$s"; }

pretty_name() { local n=${1##*/}; n=${n%.*}; n=${n//[_-]/ }; printf '%s' "$n"; }

current() { cat "$STATE/current" 2>/dev/null; }
active()  { local a; a=$(cat "$STATE/collection" 2>/dev/null); printf '%s' "${a:-all}"; }

# ───────────── کتابخونه‌ی عکس‌ها ─────────────
list_images() { # dir [depth]
    local d=$1 depth=${2:-1}
    [ -d "$d" ] || return 0
    find -L "$d" -maxdepth "$depth" -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \
        -o -iname '*.webp' -o -iname '*.gif' -o -iname '*.bmp' -o -iname '*.avif' \) -print0 | sort -z
}

collect() { # collection → WALLS
    local c=${1:-all}
    WALLS=()
    if [ "$c" != all ] && [ -d "$WALL_DIR/$c" ]; then
        mapfile -d '' -t WALLS < <(list_images "$WALL_DIR/$c" 3)
    fi
    if [ ${#WALLS[@]} -eq 0 ]; then
        mapfile -d '' -t WALLS < <(list_images "$WALL_DIR" 3)
    fi
}

collections() { # اسم ساب‌فولدرهایی که عکس دارن
    local d
    for d in "$WALL_DIR"/*/; do
        d=${d%/}
        [ -n "$(list_images "$d" 3 | head -c1)" ] && printf '%s\n' "${d##*/}"
    done
}

pick_random() { # collection → یه مسیر (به‌جز عکس فعلی)
    collect "${1:-all}"
    local cur pool=() w
    cur=$(current)
    for w in "${WALLS[@]}"; do [ "$w" = "$cur" ] || pool+=("$w"); done
    [ ${#pool[@]} -eq 0 ] && pool=("${WALLS[@]}")
    [ ${#pool[@]} -eq 0 ] && return 1
    printf '%s\n' "${pool[RANDOM % ${#pool[@]}]}"
}

# ───────────── ستاره‌ها (ناپایایی ثابت برای هر فایل) ─────────────
stars_of() {
    local h; h=$(printf '%s' "${1##*/}" | cksum); h=${h%% *}; h=$(( h % 100 ))
    if [ "$h" -lt 6 ]; then echo 5; elif [ "$h" -lt 22 ]; then echo 4; else echo 3; fi
}
stars_plain() { local n i s=""; n=$(stars_of "$1"); for ((i=0;i<n;i++)); do s+="★"; done; printf '%s' "$s"; }
stars_markup() {
    local n col; n=$(stars_of "$1")
    case $n in 5) col='#D98A1E';; 4) col='#8A5CC8';; *) col='#4E86C6';; esac
    printf "<span foreground='%s'>%s</span>" "$col" "$(stars_plain "$1")"
}

# ───────────── تامبنیل و export ─────────────
thumb_path() {
    local img=$1 k
    k=$(printf '%s' "$img" | cksum | cut -d' ' -f1)-$(stat -c %Y -- "$img" 2>/dev/null || echo 0)
    printf '%s/%s.png' "$THUMBS" "$k"
}
make_thumb() {
    local t; t=$(thumb_path "$1")
    [ -s "$t" ] && return 0
    [ -n "$IM" ] || return 1
    "$IM" "${1}[0]" -auto-orient -thumbnail '440x440^' -gravity center -extent 440x440 "$t" >/dev/null 2>&1 || rm -f "$t"
}
prime_thumbs() {
    [ -n "$IM" ] || return 0
    local f
    for f in "$@"; do
        [ -s "$(thumb_path "$f")" ] && continue
        while [ "$(jobs -rp | wc -l)" -ge "$NJOBS" ]; do wait -n 2>/dev/null || break; done
        make_thumb "$f" &
    done
    wait
}
export_png() { # src dst geometry  — حتماً PNG واقعی (Rofi/hyprlock با پسوند .png و محتوای jpg مشکل دارن)
    local src=$1 dst=$2 geo=${3:-2560x1440} tmp
    mkdir -p "${dst%/*}"
    tmp="$dst.tmp.$$"
    if [ -n "$IM" ]; then
        if "$IM" "${src}[0]" -auto-orient -resize "${geo}>" "png:$tmp" >/dev/null 2>&1; then
            mv -f "$tmp" "$dst"; return 0
        fi
        rm -f "$tmp"
    fi
    case "${src,,}" in *.png) cp -f -- "$src" "$dst" ;; *) return 1 ;; esac
}

run_hooks() { # هر اسکریپت توی wallpaper-hooks.d/*.sh با مسیر عکس اجرا میشه (SDDM، رنگ waybar، …)
    local h
    for h in "$CFG_DIR"/wallpaper-hooks.d/*.sh; do bash "$h" "$1" >/dev/null 2>&1; done
}

play_sound() {
    [ -n "$SOUND" ] && [ -f "$SOUND" ] || return 0
    if command -v pw-play >/dev/null 2>&1; then pw-play "$SOUND" >/dev/null 2>&1
    elif command -v paplay >/dev/null 2>&1; then paplay "$SOUND" >/dev/null 2>&1; fi
}

# ───────────── دیمون ─────────────
ensure_daemon() {
    "$WP" query >/dev/null 2>&1 && return 0
    setsid -f "$WPD" >/dev/null 2>&1
    local i
    for i in $(seq 1 60); do
        "$WP" query >/dev/null 2>&1 && return 0
        sleep 0.1
    done
    return 1
}

# ───────────── اعمال والپیپر ─────────────
propagate() { # آرت منوی Rofi + لاک‌اسکرین + هوک‌ها، پشت‌صحنه
    local img=$1
    (
        [ -n "$ROFI_ART" ] && export_png "$img" "$ROFI_ART" 1920x1080
        [ -n "$LOCK_IMG" ] && export_png "$img" "$LOCK_IMG" 2560x1440
        run_hooks "$img"
    ) >/dev/null 2>&1 &
    disown 2>/dev/null || true
}

announce() {
    local img=$1 n s=""
    n=$(pretty_name "$img")
    [ "$SHOW_RARITY" = 1 ] && s=$'\n'"$(stars_plain "$img")"
    (
        make_thumb "$img"
        ic=$(thumb_path "$img"); [ -s "$ic" ] || ic=$img
        notify "${NOTE_TITLE:-✦ Teyvat Resonance}" "${NOTE_BODY:+$NOTE_BODY$'\n'}$n$s" "$ic"
        play_sound
    ) >/dev/null 2>&1 &
    disown 2>/dev/null || true
}

set_wallpaper() { # img [flags: i=بدون ترنزیشن  q=بی‌صدا]
    local img=$1 flags=${2:-}
    if [ ! -f "$img" ]; then notify "✦ Paimon" "File not found: ${img##*/}"; return 1; fi
    img=$(readlink -f -- "$img")
    need_backend
    ensure_daemon || { notify "✦ Paimon" "$WPD did not start"; return 1; }

    local a=(--resize "$RESIZE" --filter "$FILTER")
    if [[ $flags == *i* ]]; then
        a+=(--transition-type none)
    else
        a+=(--transition-type "$TRANSITION" --transition-duration "$TRANSITION_DURATION"
            --transition-fps "$TRANSITION_FPS" --transition-pos "$TRANSITION_POS")
        [ -n "$TRANSITION_BEZIER" ] && a+=(--transition-bezier "$TRANSITION_BEZIER")
    fi
    "$WP" img "${a[@]}" "$img" >/dev/null 2>&1 \
        || "$WP" img "$img" >/dev/null 2>&1 \
        || { notify "✦ Paimon" "$WP could not set ${img##*/}"; return 1; }

    printf '%s\n' "$img" > "$STATE/current"
    date +%s > "$STATE/last_change"
    propagate "$img"
    [[ $flags == *q* ]] || announce "$img"
    return 0
}

set_with_note() { # title body img flags
    NOTE_TITLE=$1; NOTE_BODY=$2
    set_wallpaper "$3" "${4:-}"
    local rc=$?
    NOTE_TITLE=""; NOTE_BODY=""
    return $rc
}

# ───────────── حالت‌های خودکار ─────────────
daily_id()   { date -d '4 hours ago' +%F; }                      # Daily Commission ساعت ۴ صبح ریست میشه
period_now() { local h; h=$((10#$(date +%H))); if [ "$h" -ge "$DAY_START" ] && [ "$h" -lt "$NIGHT_START" ]; then echo day; else echo night; fi; }

daily_pick() {
    collect "$(active)"
    local n=${#WALLS[@]} days
    [ "$n" -gt 0 ] || return 1
    days=$(( $(date -u -d "$(daily_id)" +%s) / 86400 ))
    printf '%s\n' "${WALLS[days % n]}"
}

auto_apply() { # flags [tick]
    local flags=${1:-} tick=${2:-} w id p last
    case "$AUTO_MODE" in
        daily)
            id=$(daily_id)
            [ "$(cat "$STATE/daily_id" 2>/dev/null)" = "$id" ] && return 1
            w=$(daily_pick) || return 1
            printf '%s\n' "$id" > "$STATE/daily_id"
            set_with_note "✦ Daily Commission" "A new day in Teyvat" "$w" "$flags" ;;
        daynight)
            p=$(period_now)
            [ "$(cat "$STATE/period" 2>/dev/null)" = "$p" ] && return 1
            w=$(pick_random "$p") || return 1
            printf '%s\n' "$p" > "$STATE/period"
            if [ "$p" = day ]; then set_with_note "✦ Daybreak over Teyvat" "" "$w" "$flags"
            else set_with_note "✦ Nightfall in Teyvat" "" "$w" "$flags"; fi ;;
        rotate)
            [ "$tick" = tick ] || return 1
            last=$(cat "$STATE/last_change" 2>/dev/null); last=${last:-0}
            [ $(( $(date +%s) - last )) -ge $(( ROTATE_MINUTES * 60 )) ] || return 1
            w=$(pick_random "$(active)") || return 1
            set_with_note "✦ Teyvat Resonance" "" "$w" "$flags" ;;
        *) return 1 ;;
    esac
}

ensure_watcher() { setsid -f "$SELF" --watch >/dev/null 2>&1 || true; }

watch_loop() {
    exec 9>"$STATE/watch.lock"
    flock -n 9 || exit 0
    local outs="" n
    while true; do
        load_config
        auto_apply "" tick
        n=$("$WP" query 2>/dev/null | wc -l)          # مانیتور وصل/جدا شد → دوباره اعمال کن
        if [ -n "$outs" ] && [ "$n" != "$outs" ] && [ -f "$(current)" ]; then
            set_wallpaper "$(current)" iq
        fi
        outs=$n
        sleep 20
    done
}

restore_current() {
    local cur w; cur=$(current)
    if [ -n "$cur" ] && [ -f "$cur" ]; then set_wallpaper "$cur" iq; return; fi
    w=$(pick_random "$(active)") || w=""
    if [ -n "$w" ]; then set_wallpaper "$w" iq
    else notify "✦ Paimon" "No wallpapers yet — drop images into ${WALL_DIR/#$HOME/~}"; fi
}

start() {
    need_backend
    systemctl --user stop hyprland-wallpaper.service >/dev/null 2>&1 || true   # سرویس والپیپر HyDE
    ensure_daemon || exit 1
    auto_apply iq || restore_current
    setsid -f "$SELF" --thumbs >/dev/null 2>&1 || true
    ensure_watcher
}

# ───────────── Wish / Daily ─────────────
do_wish() {
    local w c
    w=$(pick_random "$(active)") || { notify "✦ Paimon" "The archive is empty…"; return 1; }
    c=$(( $(cat "$STATE/wish_count" 2>/dev/null || echo 0) + 1 ))
    printf '%s\n' "$c" > "$STATE/wish_count"
    set_with_note "✦ Wish Result" "Wish #$c" "$w" ""
}

do_daily_manual() {
    local w; w=$(daily_pick) || { notify "✦ Paimon" "The archive is empty…"; return 1; }
    printf '%s\n' "$(daily_id)" > "$STATE/daily_id"
    set_with_note "✦ Daily Commission" "Today's commission" "$w" ""
}

step() { # +1 / -1
    collect "$(active)"
    local n=${#WALLS[@]} i idx=-1 cur
    [ "$n" -gt 0 ] || return 1
    cur=$(current)
    for i in "${!WALLS[@]}"; do [ "${WALLS[i]}" = "$cur" ] && { idx=$i; break; }; done
    if [ "$idx" -lt 0 ]; then idx=0; else idx=$(( (idx + $1 + n) % n )); fi
    set_wallpaper "${WALLS[idx]}"
}

# ───────────── منوی Rofi ─────────────
ROFI_BASE=(-dmenu -i -format i -no-custom -markup-rows -show-icons)

row_markup() {
    local n s=""
    n=$(pretty_name "$1"); [ ${#n} -gt 16 ] && n="${n:0:15}…"
    n=$(esc "$n")
    [ "$SHOW_RARITY" = 1 ] && s="$(stars_markup "$1")  "
    printf '%s%s' "$s" "$n"
}

region_label() {
    case "$1" in
        day) echo "Daybreak" ;;
        night) echo "Nightfall" ;;
        *) local l=${1//[_-]/ }; echo "${l^}" ;;
    esac
}

region_row() {
    local c=$1 el col sub cnt lbl
    el=${REGION_EL[$c]:-}
    if [ "$c" = all ]; then
        cnt=$(list_images "$WALL_DIR" 3 | tr -cd '\0' | wc -c)
        printf "<span foreground='#D3BC8E'>✦</span>  <b>All of Teyvat</b>  <span foreground='#A9ADBA'>%s</span>" "$cnt"
        return
    fi
    cnt=$(list_images "$WALL_DIR/$c" 3 | tr -cd '\0' | wc -c)
    lbl=$(esc "$(region_label "$c")")
    case "$c" in
        day)   col='#F2D98D'; sub='☀' ;;
        night) col='#8E9BD6'; sub='☾' ;;
        *)     col=${EL_COLOR[$el]:-#D3BC8E}; sub=${el^:-✦} ;;
    esac
    printf "<span foreground='%s'>◆</span>  <b>%s</b>  <span foreground='#A9ADBA'>%s · %s</span>" "$col" "$lbl" "$sub" "$cnt"
}

region_picker() { # → PICK ؛ برگشتی ۰ = انتخاب شد
    local cols=() entries=(all) c el ic out rc
    mapfile -t cols < <(collections)
    if [ ${#cols[@]} -eq 0 ]; then PICK=all; return 0; fi
    entries+=("${cols[@]}")
    out=$(
        for c in "${entries[@]}"; do
            el=${REGION_EL[$c]:-}; ic=""
            [ -n "$el" ] && [ -f "$ICON_DIR/$el.png" ] && ic="$ICON_DIR/$el.png"
            if [ -n "$ic" ]; then printf '%s\0icon\x1f%s\n' "$(region_row "$c")" "$ic"
            else printf '%s\n' "$(region_row "$c")"; fi
        done | rofi "${ROFI_BASE[@]}" -p "✦ Teyvat" -mesg "Choose a region" -theme "$GALLERY_THEME" \
            -theme-str 'window { width: 560px; } listview { columns: 1; lines: 8; scrollbar: false; } element { orientation: horizontal; padding: 8px 14px; spacing: 12px; border-radius: 8px; } element-icon { size: 34px; padding: 0px; } element-text { horizontal-align: 0.0; background-color: transparent; text-color: inherit; padding: 0px; border-radius: 0px; font: "Noto Sans 11"; } element normal.normal, element alternate.normal { background-color: #2E3446B3; text-color: #ECE5D8; } element selected.normal { background-color: #ECE5D8; text-color: #2E3446; border-color: #FFF3CF; }'
    )
    rc=$?
    [ "$rc" -eq 0 ] && [ -n "$out" ] || return 1
    PICK=${entries[$out]}
}

gallery() { # collection → GAL_RC / GAL_PATH
    local coll=$1 w i sel=0 cur out ic title n
    collect "$coll"; n=${#WALLS[@]}
    GAL_PATH=""
    if [ "$n" -eq 0 ]; then notify "✦ Paimon" "Nothing here yet — drop images into ${WALL_DIR/#$HOME/~}"; GAL_RC=2; return; fi
    prime_thumbs "${WALLS[@]}"
    RARITY_ARGS=(); local act="" urg="" k=0
    for w in "${WALLS[@]}"; do
        case $(stars_of "$w") in 5) act+="${act:+,}$k" ;; 4) urg+="${urg:+,}$k" ;; esac
        k=$((k+1))
    done
    [ -n "$act" ] && RARITY_ARGS+=(-a "$act")
    [ -n "$urg" ] && RARITY_ARGS+=(-u "$urg")
    cur=$(current)
    for i in "${!WALLS[@]}"; do [ "${WALLS[i]}" = "$cur" ] && sel=$i; done
    if [ "$coll" = all ]; then title="Teyvat Wallpapers"; else title=$(region_label "$coll"); fi
    out=$(
        for w in "${WALLS[@]}"; do
            ic=$(thumb_path "$w"); [ -s "$ic" ] || ic=$w
            printf '%s\0icon\x1f%s\n' "$(row_markup "$w")" "$ic"
        done | rofi "${ROFI_BASE[@]}" -p "✦ $title" -mesg "$GAL_HINT" -selected-row "$sel" "${RARITY_ARGS[@]}" \
            -kb-custom-1 "Alt+r" -kb-custom-2 "Alt+d" -kb-custom-3 "Alt+t" -theme "$GALLERY_THEME"
    )
    GAL_RC=$?
    if [ "$GAL_RC" -eq 0 ]; then
        if [ -n "$out" ]; then GAL_PATH=${WALLS[$out]}; else GAL_RC=1; fi
    fi
}

menu() {
    local coll=${1:-}
    command -v rofi >/dev/null 2>&1 || { notify "✦ Paimon" "rofi is not installed"; exit 1; }
    if pgrep -x rofi >/dev/null 2>&1; then pkill -x rofi; exit 0; fi      # دوباره Super+Shift+W = بستن
    [ -f "$GALLERY_THEME" ] || notify "✦ Paimon" "Missing theme: ${GALLERY_THEME/#$HOME/~}"
    if [ -z "$coll" ]; then coll=$(active); fi      # open straight on the active theme
    while true; do
        if [ -z "$coll" ]; then
            region_picker || exit 0
            coll=$PICK
        fi
        gallery "$coll"
        case $GAL_RC in
            0)  printf '%s' "$coll" > "$STATE/collection"
                set_wallpaper "$GAL_PATH"; exit 0 ;;
            10) do_wish; exit 0 ;;
            11) do_daily_manual; exit 0 ;;
            12|2) [ -z "$(collections)" ] && exit 0; coll="" ;;
            *)  exit 0 ;;
        esac
    done
}

# ───────────── ابزارها ─────────────
import_cmd() {
    local src=${1:-} coll=${2:-} dest f n=0
    if [ -z "$src" ] || [ ! -e "$src" ]; then echo "usage: wallpaper.sh --import <file|dir> [region]"; exit 1; fi
    dest="$WALL_DIR"; [ -n "$coll" ] && dest="$WALL_DIR/$coll"
    mkdir -p "$dest"
    if [ -d "$src" ]; then
        while IFS= read -r -d '' f; do
            [ -e "$dest/${f##*/}" ] || { cp -- "$f" "$dest/" && n=$((n+1)); }
        done < <(list_images "$src" 6)
    else
        [ -e "$dest/${src##*/}" ] || { cp -- "$src" "$dest/" && n=1; }
    fi
    echo "[ok] imported $n image(s) → $dest"
}

set_mode() {
    case "${1:-}" in off|rotate|daily|daynight) ;; *) echo "modes: off | rotate | daily | daynight"; exit 1 ;; esac
    mkdir -p "$CFG_DIR"
    if [ -f "$CONF" ] && grep -q '^AUTO_MODE=' "$CONF"; then
        sed -i "s|^AUTO_MODE=.*|AUTO_MODE=\"$1\"|" "$CONF"
    else
        printf 'AUTO_MODE="%s"\n' "$1" >> "$CONF"
    fi
    rm -f "$STATE/daily_id" "$STATE/period"
    load_config
    need_backend
    auto_apply "" || true
    ensure_watcher
    notify "✦ Paimon" "Auto mode: $1"
    echo "[ok] AUTO_MODE=$1"
}

status() {
    local n; n=$(list_images "$WALL_DIR" 3 | tr -cd '\0' | wc -c)
    echo "backend     : ${WP:-none}"
    echo "wallpapers  : $n  ($WALL_DIR)"
    echo "current     : $(current)"
    echo "region      : $(active)"
    echo "auto mode   : $AUTO_MODE"
    echo "wishes made : $(cat "$STATE/wish_count" 2>/dev/null || echo 0)"
    pgrep -f -- "$SELF --watch" >/dev/null 2>&1 && echo "watcher     : running" || echo "watcher     : stopped"
}

usage() { sed -n '2,16p' "$SELF" | sed 's/^# \{0,1\}//'; }

# ───────────── اجرا ─────────────
case "${1:-}" in
    --start)   start ;;
    --watch)   need_backend; watch_loop ;;
    --thumbs)  collect all; prime_thumbs "${WALLS[@]}" ;;
    --menu|"") menu "${2:-}" ;;
    --set)     [ -n "${2:-}" ] || { usage; exit 1; }; set_wallpaper "$2" ;;
    --next)    step 1 ;;
    --prev)    step -1 ;;
    --random)  w=$(pick_random "$(active)") && set_wallpaper "$w" ;;
    --wish)    do_wish ;;
    --daily)   do_daily_manual ;;
    --region)  [ -n "${2:-}" ] || { usage; exit 1; }
               printf '%s' "$2" > "$STATE/collection"
               w=$(pick_random "$2") && set_wallpaper "$w" ;;
    --mode)    set_mode "${2:-}" ;;
    --import)  import_cmd "${2:-}" "${3:-}" ;;
    --sync)    c=$(current); [ -f "$c" ] && { export_png "$c" "$ROFI_ART" 1920x1080; export_png "$c" "$LOCK_IMG" 2560x1440; run_hooks "$c"; echo "[ok] synced"; } ;;
    --status)  status ;;
    -h|--help) usage ;;
    *)         if [ -f "$1" ]; then set_wallpaper "$1"; else usage; exit 1; fi ;;
esac
