#!/usr/bin/env bash
# Genshin Impact - Theme Builder (Super + Shift + T)
#   theme-select.sh            open the Theme Builder
#   theme-select.sh --restore  re-apply the active theme's accent (for startup)
set -u

. "$HOME/.config/hypr-genshin/resonance-lib.sh" || exit 1

WSH="$CFG/wallpaper.sh"
WCONF="$CFG/wallpaper.conf"
CUR_FILE="$RES_WSTATE/current"                    # written by wallpaper.sh
TRASH="$RES_WSTATE/trash"
ROFI_THEME="$HOME/.config/rofi-genshin/theme-gallery.rasi"
WALL_DIR=$(res_wall_dir)
CUR=$(cat "$CUR_FILE" 2>/dev/null || true)
NJOBS=$(nproc 2>/dev/null || echo 4)
TILDE='~'
PAGE_SIZE=36
SELFILE=""
CLIP=()

if [ "${1:-}" = "--restore" ]; then
    res_theme_apply "$(res_active_theme)" "$CUR"
    exit 0
fi

IM=$(_im || true)
if [ -z "$IM" ]; then
    notify-send -a "Paimon" "Theme Builder" "ImageMagick is not installed (sudo pacman -S imagemagick)"
    exit 1
fi

if pgrep -x rofi >/dev/null 2>&1; then
    pkill -x rofi
    exit 0
fi

IMG_FIND=( \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' -o -iname '*.gif' -o -iname '*.bmp' -o -iname '*.avif' \) )

PRESETS=(
    "Celestia|d3bc8e|f4e8c1|8a7550"
    "Pyro|ff6b4a|ffb4a2|8c2a1a"
    "Hydro|48cae4|ade8f4|12607a"
    "Electro|b565f2|e0aaff|5a2a8a"
    "Dendro|57cc99|b7efc5|2a6b4a"
    "Cryo|90e0ef|caf0f8|4a8a9a"
    "Geo|f4b942|ffe6a7|8a6420"
    "Abyssal|e63956|ff8fa3|6b0f22"
)

# ═════════════════════════════ helpers ═════════════════════════════
esc() { local s=$1; s=${s//&/&amp;}; s=${s//</&lt;}; s=${s//>/&gt;}; printf '%s' "$s"; }
pretty() { printf '%s' "${1//_/ }"; }
note() { notify-send -a "Paimon" "$1" "${2:-}" >/dev/null 2>&1 || true; }

first_image() { find -L "$1" -maxdepth "${2:-3}" -type f -not -name '.*' "${IMG_FIND[@]}" -print -quit 2>/dev/null; }
count_images() { find -L "$1" -maxdepth "${2:-3}" -type f -not -name '.*' "${IMG_FIND[@]}" 2>/dev/null | wc -l; }

swatch() { # HI LO → png path (gradient + diamond)
    local sw="$RES_CACHE/thumbs/sw-$1-$2.png"
    [ -s "$sw" ] || "$IM" -size 272x272 "gradient:#$1-#$2" \
        -fill '#ffffff44' -draw 'polygon 136,64 184,136 136,208 88,136' "$sw" 2>/dev/null
    printf '%s' "$sw"
}

wp_thumb() {
    local t="$RES_CACHE/thumbs/$(res_key "$1").png"
    [ -s "$t" ] || "$IM" -define jpeg:size=544x544 "$1[0]" -auto-orient -thumbnail '272x272^' \
        -gravity center -extent 272x272 "$t" 2>/dev/null
    printf '%s' "$t"
}

prime_thumbs() { # generate missing thumbnails in parallel
    local f
    for f in "$@"; do
        [ -s "$RES_CACHE/thumbs/$(res_key "$f").png" ] && continue
        while [ "$(jobs -rp | wc -l)" -ge "$NJOBS" ]; do wait -n 2>/dev/null || break; done
        ( wp_thumb "$f" >/dev/null ) &
    done
    wait
}

card_icon() { if [ -n "${1:-}" ] && [ -f "$1" ]; then wp_thumb "$1"; else swatch d3bc8e 8a7550; fi; }

new_icon() {
    local p="$RES_CACHE/thumbs/new-theme.png"
    [ -s "$p" ] || "$IM" -size 272x272 "gradient:#4a5470-#2e3446" -fill '#d3bc8eee' \
        -draw 'rectangle 120,66 152,206' -draw 'rectangle 66,120 206,152' "$p" 2>/dev/null
    printf '%s' "$p"
}

folder_icon() {
    local p="$RES_CACHE/thumbs/folder.png"
    [ -s "$p" ] || "$IM" -size 272x272 xc:'#3d4559' -fill '#d3bc8e' \
        -draw 'roundrectangle 46,70 120,110 8,8' -draw 'roundrectangle 46,92 226,206 14,14' \
        -fill '#f4e8c1' -draw 'roundrectangle 46,108 226,206 14,14' "$p" 2>/dev/null
    printf '%s' "$p"
}

folder_thumb() { local f; f=$(first_image "$1" 1); if [ -n "$f" ]; then wp_thumb "$f"; else folder_icon; fi; }

# 2x2 collage of a theme's first images (single thumb when fewer than 4)
collage() {
    local dir="$1" key t imgs=() th=() f
    key="coll-$(printf '%s' "$dir" | md5sum | cut -c1-12)-$(stat -c %Y "$dir" 2>/dev/null || echo 0)"
    t="$RES_CACHE/thumbs/$key.png"
    if [ ! -s "$t" ]; then
        mapfile -t imgs < <(find -L "$dir" -maxdepth 3 -type f -not -name '.*' "${IMG_FIND[@]}" 2>/dev/null | sort | head -n 4)
        if [ "${#imgs[@]}" -ge 4 ]; then
            for f in "${imgs[@]}"; do th+=("$(wp_thumb "$f")"); done
            "$IM" \( "${th[0]}" "${th[1]}" +append \) \( "${th[2]}" "${th[3]}" +append \) -append \
                -resize 272x272 "$t" 2>/dev/null
        elif [ "${#imgs[@]}" -ge 1 ]; then
            cp -f "$(wp_thumb "${imgs[0]}")" "$t" 2>/dev/null
        fi
        [ -s "$t" ] || cp -f "$(swatch d3bc8e 8a7550)" "$t" 2>/dev/null
    fi
    printf '%s' "$t"
}

# Single-column text list → prints the chosen index (empty on cancel)
menu_list() { # mesg item...
    local mesg="$1" n; shift
    n=$#; [ "$n" -gt 10 ] && n=10
    printf '%s\n' "$@" | rofi -dmenu -i -format i -no-custom -p "✦" \
        -mesg "$mesg" -theme "$ROFI_THEME" \
        -theme-str "window { width: 680px; } listview { columns: 1; lines: $n; } element { orientation: horizontal; padding: 10px 16px; } element-text { horizontal-align: 0.0; font: \"Noto Sans 11\"; }"
}

title_mesg() { # title [subtitle]
    printf "<span size='x-large' foreground='#f4e8c1'><b>✦   %s   ✦</b></span>" "$1"
    [ -n "${2:-}" ] && printf "\n<span foreground='#d3bc8e'>%s</span>" "$2"
    return 0
}

text_prompt() { # title hint [prefill] → typed text (rc 1 when empty)
    local out
    out=$(rofi -dmenu -p "✦" -filter "${3:-}" -mesg "$(title_mesg "$1" "$2")" -theme "$ROFI_THEME" \
        -theme-str 'window { width: 680px; } mainbox { children: [ message, inputbar ]; } listview { enabled: false; }' </dev/null)
    [ -n "$out" ] || return 1
    printf '%s' "$out"
}

confirm() { # title sub yes-label → rc 0 when confirmed
    local c
    c=$(menu_list "$(title_mesg "$1" "$2")" "←  Cancel" "$3")
    [ "$c" = 1 ]
}

slugify() { printf '%s' "$1" | sed -E 's#[/\\.]##g; s/^[[:space:]]+//; s/[[:space:]]+$//; s/[[:space:]]+/_/g'; }

hex_trio() { # RRGGBB → "BASE HI LO"
    local h=${1#\#} r g b
    h=${h,,}
    r=$((16#${h:0:2})); g=$((16#${h:2:2})); b=$((16#${h:4:2}))
    printf '%02x%02x%02x %02x%02x%02x %02x%02x%02x' "$r" "$g" "$b" \
        $((r+(255-r)*45/100)) $((g+(255-g)*45/100)) $((b+(255-b)*45/100)) \
        $((r*55/100)) $((g*55/100)) $((b*55/100))
}

# ═════════════════════════ files / storage ═════════════════════════
write_theme() { # theme auto | theme fixed NAME BASE HI LO
    local f="$WALL_DIR/$1/.theme"
    if [ "$2" = auto ]; then
        printf 'ACCENT="auto"\n' > "$f"
    else
        printf 'ACCENT="fixed"\nNAME="%s"\nBASE="%s"\nHI="%s"\nLO="%s"\n' "$3" "$4" "$5" "$6" > "$f"
    fi
}

theme_accent_label() {
    local f="$1/.theme"
    if [ -f "$f" ] && grep -q '^ACCENT="fixed"' "$f"; then sed -n 's/^NAME="\(.*\)"/\1/p' "$f"; else printf 'Auto'; fi
}

copy_unique() { # src destdir — never overwrites a different file with the same name
    local b=${1##*/} n=1 t
    t="$2/$b"
    while [ -e "$t" ]; do
        cmp -s -- "$1" "$t" && return 0
        t="$2/${b%.*}_$n.${b##*.}"; n=$((n+1))
    done
    cp -- "$1" "$t"
}

import_into() { # src(file|dir) theme
    local dest="$WALL_DIR/$2" f
    mkdir -p "$dest"
    if [ -d "$1" ]; then
        find -L "$1" -maxdepth 3 -type f -not -name '.*' "${IMG_FIND[@]}" -print0 2>/dev/null \
          | while IFS= read -r -d '' f; do copy_unique "$f" "$dest"; done
    elif [ -f "$1" ]; then
        copy_unique "$1" "$dest"
    fi
    return 0
}

trash_theme_dir() { # theme → 0 when it is really gone
    local t="$1" dir="$WALL_DIR/$1" dest
    mkdir -p "$TRASH/themes"
    dest="$TRASH/themes/$t-$(date +%s)"
    mv -- "$dir" "$dest" 2>/dev/null || { cp -a -- "$dir" "$dest" 2>/dev/null && rm -rf -- "$dir"; }
    [ ! -e "$dir" ] || return 1
    if [ "$(res_active_theme)" = "$t" ]; then printf 'all' > "$RES_WSTATE/collection"; fi
    return 0
}

clip_paths() { # paths copied in a file manager / copied as text
    command -v wl-paste >/dev/null 2>&1 || return 0
    local u p
    { wl-paste -t text/uri-list 2>/dev/null; wl-paste -t text/plain -n 2>/dev/null; } | tr -d '\r' \
      | while IFS= read -r u; do
            case "$u" in
                file://*) p=${u#file://}; p=$(printf '%b' "${p//%/\\x}") ;;
                '~'*)     p=${u/#\~/$HOME} ;;
                /*)       p=$u ;;
                *)        continue ;;
            esac
            [ -e "$p" ] && printf '%s\n' "$p"
        done | sort -u
}

has_dialog() { command -v zenity >/dev/null 2>&1 || command -v kdialog >/dev/null 2>&1 || command -v yad >/dev/null 2>&1; }

system_dialog() {
    if command -v zenity >/dev/null 2>&1; then
        zenity --file-selection --multiple --separator='|' --title='Pick images' \
            --file-filter='Images | *.png *.jpg *.jpeg *.webp *.PNG *.JPG *.JPEG' 2>/dev/null | tr '|' '\n'
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --getopenfilename "$HOME" 'image/*' --multiple --separate-output 2>/dev/null
    elif command -v yad >/dev/null 2>&1; then
        yad --file --multiple --separator='|' --title='Pick images' 2>/dev/null | tr '|' '\n'
    fi
}

set_conf() { # KEY VALUE  (wallpaper.conf is a sourced shell file)
    [ -f "$WCONF" ] || : > "$WCONF"
    if grep -q "^$1=" "$WCONF"; then sed -i "s|^$1=.*|$1=$2|" "$WCONF"; else printf '%s=%s\n' "$1" "$2" >> "$WCONF"; fi
}

# ════════════════════════ built-in image browser ═══════════════════
sel_toggle() {
    if grep -Fxq -- "$1" "$SELFILE"; then
        grep -Fxv -- "$1" "$SELFILE" > "$SELFILE.t"; mv -f "$SELFILE.t" "$SELFILE"
    else
        printf '%s\n' "$1" >> "$SELFILE"
    fi
}

import_selected() { # theme
    local f
    while IFS= read -r f; do
        [ -n "$f" ] && import_into "$f" "$1"
    done < "$SELFILE"
    return 0
}

# browse_images THEME → 0 when something was added
browse_images() {
    local theme="$1" cwd="" page=0 focus="" sel=0
    local idx kind arg c p parent f d lbl m i total start before after LIST SELN pair
    local ROWS=() imgs=() dirs=() slice=()
    before=$(count_images "$WALL_DIR/$theme")
    SELFILE=$(mktemp)

    while true; do
        ROWS=(); LIST=$(mktemp)
        SELN=$(( $(wc -l < "$SELFILE") ))

        if [ -z "$cwd" ]; then
            # ── places ──
            mapfile -t CLIP < <(clip_paths)
            if [ "${#CLIP[@]}" -gt 0 ]; then
                ROWS+=("clip|"); printf '%s\0icon\x1f%s\n' "⎘  Paste ${#CLIP[@]} copied item(s)" "$(new_icon)" >> "$LIST"
            fi
            ROWS+=("type|"); printf '%s\0icon\x1f%s\n' "⌨  Type a path…" "$(swatch 8fb7ff 3d5a99)" >> "$LIST"
            if has_dialog; then
                ROWS+=("sys|"); printf '%s\0icon\x1f%s\n' "⌕  System file dialog…" "$(swatch c9a6ff 5a3d99)" >> "$LIST"
            fi
            for pair in "Home|$HOME" "Pictures|$HOME/Pictures" "Downloads|$HOME/Downloads" \
                        "Desktop|$HOME/Desktop" "Documents|$HOME/Documents" "Videos|$HOME/Videos" \
                        "HyDE themes|$HOME/.config/hyde/themes" "Wallpapers|$WALL_DIR"; do
                IFS='|' read -r lbl p <<< "$pair"
                [ -d "$p" ] || continue
                ROWS+=("dir|$p"); printf '%s\0icon\x1f%s\n' "▸  $lbl" "$(folder_thumb "$p")" >> "$LIST"
            done
            for m in /run/media/"${USER:-$(id -un)}"/* /mnt/*; do
                [ -d "$m" ] || continue
                ROWS+=("dir|$m"); printf '%s\0icon\x1f%s\n' "▸  ${m##*/} (drive)" "$(folder_thumb "$m")" >> "$LIST"
            done
        else
            # ── a folder ──
            ROWS+=("up|");     printf '%s\0icon\x1f%s\n' "◂  Back" "$(folder_icon)" >> "$LIST"
            ROWS+=("places|"); printf '%s\0icon\x1f%s\n' "⌂  Places" "$(folder_icon)" >> "$LIST"
            mapfile -d '' -t imgs < <(find -L "$cwd" -maxdepth 1 -type f -not -name '.*' "${IMG_FIND[@]}" -print0 2>/dev/null | sort -zV)
            mapfile -d '' -t dirs < <(find -L "$cwd" -mindepth 1 -maxdepth 1 -type d -not -name '.*' -print0 2>/dev/null | sort -zV)
            total=${#imgs[@]}

            if [ "$SELN" -gt 0 ]; then
                ROWS+=("done|");  printf '%s\0icon\x1f%s\n' "✔  Add $SELN selected" "$(swatch f4e8c1 d3bc8e)" >> "$LIST"
                ROWS+=("clear|"); printf '%s\0icon\x1f%s\n' "☐  Clear selection" "$(swatch 8a8f9c 464b58)" >> "$LIST"
            fi
            if [ "$total" -gt 0 ]; then
                ROWS+=("all|");    printf '%s\0icon\x1f%s\n' "☑  Select all $total here" "$(swatch ade8f4 12607a)" >> "$LIST"
                ROWS+=("folder|"); printf '%s\0icon\x1f%s\n' "＋  Add this whole folder ($total)" "$(swatch b7efc5 2a6b4a)" >> "$LIST"
            fi
            for d in "${dirs[@]}"; do
                ROWS+=("dir|$d"); printf '%s\0icon\x1f%s\n' "▸  ${d##*/}" "$(folder_thumb "$d")" >> "$LIST"
            done
            if [ "$page" -gt 0 ]; then
                ROWS+=("prev|"); printf '%s\0icon\x1f%s\n' "‹  Previous page" "$(folder_icon)" >> "$LIST"
            fi
            if [ $(( (page+1) * PAGE_SIZE )) -lt "$total" ]; then
                ROWS+=("next|"); printf '%s\0icon\x1f%s\n' "›  Next page ($(( total - (page+1)*PAGE_SIZE )) more)" "$(folder_icon)" >> "$LIST"
            fi
            start=$(( page * PAGE_SIZE ))
            slice=("${imgs[@]:$start:$PAGE_SIZE}")
            if [ "${#slice[@]}" -gt 0 ]; then
                prime_thumbs "${slice[@]}"
                for f in "${slice[@]}"; do
                    lbl="    ${f##*/}"
                    grep -Fxq -- "$f" "$SELFILE" && lbl="✔  ${f##*/}"
                    ROWS+=("img|$f"); printf '%s\0icon\x1f%s\n' "$lbl" "$(wp_thumb "$f")" >> "$LIST"
                done
            fi
        fi

        sel=0
        for i in "${!ROWS[@]}"; do
            [ -n "$focus" ] && [ "${ROWS[i]}" = "img|$focus" ] && sel=$i
        done

        idx=$(rofi -dmenu -i -show-icons -format i -no-custom -p "✦" -selected-row "$sel" \
                -mesg "$(title_mesg "Choose images" "$(esc "${cwd:-Places}" | sed "s#^$HOME#$TILDE#") · Enter ticks an image · $SELN selected")" \
                -theme "$ROFI_THEME" -theme-str 'listview { columns: 6; lines: 3; }' < "$LIST")
        rm -f "$LIST"

        if [ -z "$idx" ]; then
            if [ "$SELN" -gt 0 ]; then
                c=$(menu_list "$(title_mesg "Leave without adding?" "$SELN images are selected")" "←  Keep choosing" "✕  Discard and leave")
                [ "$c" = 0 ] && continue
            fi
            rm -f "$SELFILE" "$SELFILE.t"
            return 1
        fi

        IFS='|' read -r kind arg <<< "${ROWS[$idx]}"
        case "$kind" in
            up)     parent=$(dirname -- "$cwd"); if [ "$parent" = "$cwd" ]; then cwd=""; else cwd=$parent; fi; page=0; focus="" ;;
            places) cwd=""; page=0; focus="" ;;
            dir)    cwd=$arg; page=0; focus="" ;;
            img)    sel_toggle "$arg"; focus=$arg ;;
            all)    for f in "${imgs[@]}"; do grep -Fxq -- "$f" "$SELFILE" || printf '%s\n' "$f" >> "$SELFILE"; done ;;
            clear)  : > "$SELFILE" ;;
            prev)   page=$((page-1)) ;;
            next)   page=$((page+1)) ;;
            type)
                p=$(text_prompt "Path" "A folder or an image file, e.g. ~/Pictures/Hyperion" "${cwd:+$cwd/}") || continue
                p=${p/#\~/$HOME}
                if [ -d "$p" ]; then cwd=${p%/}; [ -n "$cwd" ] || cwd=/; page=0; focus=""
                elif [ -f "$p" ]; then
                    grep -Fxq -- "$p" "$SELFILE" || printf '%s\n' "$p" >> "$SELFILE"
                    cwd=$(dirname -- "$p"); focus=$p; page=0
                else note "Theme Builder" "Path not found: $p"; fi ;;
            clip)   for p in "${CLIP[@]}"; do import_into "$p" "$theme"; done; break ;;
            sys)    while IFS= read -r p; do [ -n "$p" ] && import_into "$p" "$theme"; done < <(system_dialog); break ;;
            folder) import_selected "$theme"; import_into "$cwd" "$theme"; break ;;
            done)   import_selected "$theme"; break ;;
        esac
    done

    rm -f "$SELFILE" "$SELFILE.t"
    after=$(count_images "$WALL_DIR/$theme")
    if [ "$after" -gt "$before" ]; then
        note "✦ $(pretty "$theme")" "$((after - before)) image(s) added"
        return 0
    fi
    return 1
}

# ═══════════════════════ theme pieces ═══════════════════════
activate_theme() {
    local t="$1"
    if [ -f "$WSH" ]; then
        bash "$WSH" --region "$t" >/dev/null 2>&1
    else
        mkdir -p "$RES_WSTATE"; printf '%s' "$t" > "$RES_WSTATE/collection"
    fi
    note "✦ $([ "$t" = all ] && echo 'All of Teyvat' || pretty "$t")" "Theme active — Super+Shift+W shows its images"
}

pick_accent() { # theme
    local theme="$1" first LIST rows=() pb ph pl pn p idx kind nm b h l hx trio
    first=$(first_image "$WALL_DIR/$theme")
    LIST=$(mktemp)

    rows+=("auto|||||")
    printf '%s\0icon\x1f%s\n' "⟳  Auto (per image)" "$(card_icon "$first")" >> "$LIST"

    if [ -n "$first" ]; then
        while read -r pb ph pl pn; do
            [ -n "${pb:-}" ] || continue
            rows+=("fix|$pn|$pb|$ph|$pl")
            printf '%s\0icon\x1f%s\n' "◆  $pn (from images)" "$(swatch "$ph" "$pl")" >> "$LIST"
        done < <(palette_of "$first")
    fi
    for p in "${PRESETS[@]}"; do
        IFS='|' read -r pn pb ph pl <<< "$p"
        rows+=("fix|$pn|$pb|$ph|$pl")
        printf '%s\0icon\x1f%s\n' "❖  $pn" "$(swatch "$ph" "$pl")" >> "$LIST"
    done
    rows+=("custom|||||")
    printf '%s\0icon\x1f%s\n' "✎  Custom colour…" "$(swatch ffffff 777777)" >> "$LIST"

    idx=$(rofi -dmenu -i -show-icons -format i -no-custom -p "✦" \
            -mesg "$(title_mesg "Accent colour" "theme: $(esc "$(pretty "$theme")") — Auto follows every image, a colour stays fixed")" \
            -theme "$ROFI_THEME" -theme-str 'listview { lines: 3; }' < "$LIST")
    rm -f "$LIST"
    [ -n "$idx" ] || return 1

    IFS='|' read -r kind nm b h l <<< "${rows[$idx]}"
    case "$kind" in
        auto)   write_theme "$theme" auto ;;
        fix)    write_theme "$theme" fixed "$nm" "$b" "$h" "$l" ;;
        custom)
            hx=$(text_prompt "Custom colour" "Hex colour, e.g. #e63956") || return 1
            hx=${hx#\#}
            if ! [[ "$hx" =~ ^[0-9a-fA-F]{6}$ ]]; then note "Theme Builder" "Not a valid hex colour"; return 1; fi
            trio=$(hex_trio "$hx"); read -r b h l <<< "$trio"
            write_theme "$theme" fixed "Custom" "$b" "$h" "$l" ;;
    esac

    if [ "$(res_active_theme)" = "$theme" ]; then res_theme_apply "$theme" "$CUR"; fi
    return 0
}

manage_images() { # theme — tick images, remove them
    local theme="$1" dir="$WALL_DIR/$1" imgs=() ROWS=() LIST MARKS idx kind arg f n sel i focus="" lbl
    MARKS=$(mktemp)
    while true; do
        mapfile -d '' -t imgs < <(find -L "$dir" -maxdepth 3 -type f -not -name '.*' "${IMG_FIND[@]}" -print0 2>/dev/null | sort -zV)
        if [ "${#imgs[@]}" -eq 0 ]; then
            rm -f "$MARKS"
            trash_theme_dir "$theme" && note "✕ $(pretty "$theme")" "Theme had no images left — moved to trash"
            return 0
        fi
        prime_thumbs "${imgs[@]}"
        n=$(( $(wc -l < "$MARKS") ))
        ROWS=(); LIST=$(mktemp)
        ROWS+=("back|"); printf '%s\0icon\x1f%s\n' "←  Back" "$(folder_icon)" >> "$LIST"
        if [ "$n" -gt 0 ]; then
            ROWS+=("rm|"); printf '%s\0icon\x1f%s\n' "✕  Remove $n marked" "$(swatch ff8fa3 6b0f22)" >> "$LIST"
        fi
        for f in "${imgs[@]}"; do
            lbl="    ${f##*/}"
            grep -Fxq -- "$f" "$MARKS" && lbl="✕  ${f##*/}"
            ROWS+=("img|$f"); printf '%s\0icon\x1f%s\n' "$lbl" "$(wp_thumb "$f")" >> "$LIST"
        done
        sel=0
        for i in "${!ROWS[@]}"; do
            [ -n "$focus" ] && [ "${ROWS[i]}" = "img|$focus" ] && sel=$i
        done
        idx=$(rofi -dmenu -i -show-icons -format i -no-custom -p "✦" -selected-row "$sel" \
                -mesg "$(title_mesg "Manage images" "$(esc "$(pretty "$theme")") · ${#imgs[@]} images · Enter marks an image for removal")" \
                -theme "$ROFI_THEME" -theme-str 'listview { columns: 6; lines: 3; }' < "$LIST")
        rm -f "$LIST"
        [ -n "$idx" ] || { rm -f "$MARKS" "$MARKS.t"; return 0; }
        IFS='|' read -r kind arg <<< "${ROWS[$idx]}"
        case "$kind" in
            back) rm -f "$MARKS" "$MARKS.t"; return 0 ;;
            img)
                focus=$arg
                if grep -Fxq -- "$arg" "$MARKS"; then
                    grep -Fxv -- "$arg" "$MARKS" > "$MARKS.t"; mv -f "$MARKS.t" "$MARKS"
                else printf '%s\n' "$arg" >> "$MARKS"; fi ;;
            rm)
                mkdir -p "$TRASH/images/$theme"
                while IFS= read -r f; do [ -n "$f" ] && mv -f -- "$f" "$TRASH/images/$theme/" 2>/dev/null; done < "$MARKS"
                note "✕ $(pretty "$theme")" "$n image(s) moved to trash"
                : > "$MARKS"; focus="" ;;
        esac
    done
}

delete_theme() { # → 0 when deleted
    local t="$1" dir="$WALL_DIR/$1"
    confirm "Delete theme?" "$(esc "$(pretty "$t")") · $(count_images "$dir") images — kept in trash, you can restore it" "✕  Delete theme" || return 1
    if trash_theme_dir "$t"; then
        note "✕ Theme deleted" "$(pretty "$t") is in the trash (Theme Builder → Trash)"
        return 0
    fi
    note "Theme Builder" "Could not delete $(pretty "$t") — check permissions on $dir"
    return 1
}

rename_theme() { # theme → prints the final name
    local t="$1" raw slug cur
    raw=$(text_prompt "Rename theme" "Type the new name" "$(pretty "$t")") || { printf '%s' "$t"; return 0; }
    slug=$(slugify "$raw")
    if [ -z "$slug" ] || [ "$slug" = all ] || [ -e "$WALL_DIR/$slug" ]; then
        note "Theme Builder" "That name can't be used (empty or already exists)"
        printf '%s' "$t"; return 0
    fi
    if mv -- "$WALL_DIR/$t" "$WALL_DIR/$slug" 2>/dev/null; then
        [ "$(res_active_theme)" = "$t" ] && printf '%s' "$slug" > "$RES_WSTATE/collection"
        cur=$(cat "$CUR_FILE" 2>/dev/null || true)
        case "$cur" in "$WALL_DIR/$t/"*) printf '%s\n' "$WALL_DIR/$slug/${cur#"$WALL_DIR/$t/"}" > "$CUR_FILE"; CUR=$(cat "$CUR_FILE") ;; esac
        printf '%s' "$slug"
    else
        note "Theme Builder" "Rename failed"
        printf '%s' "$t"
    fi
}

theme_menu() { # theme
    local t="$1" idx n acc
    n=$(count_images "$WALL_DIR/$t"); acc=$(theme_accent_label "$WALL_DIR/$t")
    idx=$(menu_list "$(title_mesg "$(esc "$(pretty "$t")")" "$n images · accent: $(esc "$acc")")" \
          "▶  Activate — Super+Shift+W will show this theme" \
          "＋  Add images" \
          "▦  Manage images (remove)" \
          "◐  Accent colour" \
          "✎  Rename" \
          "✕  Delete theme")
    case "$idx" in
        0) activate_theme "$t" ;;
        1) browse_images "$t"; theme_menu "$t" ;;
        2) manage_images "$t"
           if [ -d "$WALL_DIR/$t" ]; then theme_menu "$t"; else main_menu; fi ;;
        3) pick_accent "$t"; theme_menu "$t" ;;
        4) t=$(rename_theme "$t"); theme_menu "$t" ;;
        5) if delete_theme "$t"; then main_menu; else theme_menu "$t"; fi ;;
    esac
}

create_theme() {
    local raw slug dir
    raw=$(text_prompt "New theme" "Name it, e.g. Hyperion, Liyue Night, Fontaine") || return 0
    slug=$(slugify "$raw")
    if [ -z "$slug" ] || [ "$slug" = all ]; then
        note "Theme Builder" "That name can't be used"
        return 0
    fi
    dir="$WALL_DIR/$slug"
    if [ -d "$dir" ]; then theme_menu "$slug"; return 0; fi
    mkdir -p "$dir"
    if ! browse_images "$slug"; then
        rmdir "$dir" 2>/dev/null || true
        note "Theme Builder" "No images added — theme not created"
        return 0
    fi
    pick_accent "$slug" || write_theme "$slug" auto
    activate_theme "$slug"
}

auto_menu() {
    local mode idx
    mode=$(sed -n 's/^AUTO_MODE="\(.*\)"/\1/p' "$WCONF" 2>/dev/null | tail -n1)
    idx=$(menu_list "$(title_mesg "Auto change" "current: ${mode:-off}")" \
          "⏻  Off" \
          "↻  Rotate every 15 minutes" \
          "↻  Rotate every 30 minutes" \
          "↻  Rotate every hour" \
          "☀  Daily Commission — a new image every day at 4 AM" \
          "☾  Day & Night — uses themes named day and night")
    [ -f "$WSH" ] || { note "Theme Builder" "wallpaper.sh not found"; return 0; }
    case "$idx" in
        0) bash "$WSH" --mode off ;;
        1) set_conf ROTATE_MINUTES 15;  bash "$WSH" --mode rotate ;;
        2) set_conf ROTATE_MINUTES 30;  bash "$WSH" --mode rotate ;;
        3) set_conf ROTATE_MINUTES 60;  bash "$WSH" --mode rotate ;;
        4) bash "$WSH" --mode daily ;;
        5) bash "$WSH" --mode daynight ;;
    esac >/dev/null 2>&1
}

trash_menu() {
    local items=() paths=() d b name idx dest
    for d in "$TRASH"/themes/*/; do
        [ -d "$d" ] || continue
        d=${d%/}; b=${d##*/}; name=${b%-*}
        paths+=("$d"); items+=("↺  Restore  $(pretty "$name")  ·  $(count_images "$d") images")
    done
    if [ "${#paths[@]}" -eq 0 ]; then note "Theme Builder" "The trash is empty"; return 0; fi
    items+=("✕  Empty the trash for good")
    idx=$(menu_list "$(title_mesg "Trash" "deleted themes")" "${items[@]}")
    [ -n "$idx" ] || return 0
    if [ "$idx" -eq "${#paths[@]}" ]; then
        confirm "Empty the trash?" "This cannot be undone" "✕  Delete forever" && rm -rf -- "$TRASH/themes" "$TRASH/images"
        return 0
    fi
    d=${paths[$idx]}; b=${d##*/}; name=${b%-*}
    dest="$WALL_DIR/$name"; [ -e "$dest" ] && dest="${dest}_restored"
    mv -- "$d" "$dest" && note "↺ Theme restored" "$(pretty "${dest##*/}")"
}

# ═════════════════════════════ main menu ═════════════════════════════
main_menu() {
    local act LIST ROWS=() d name f mark idx kind arg shown mode
    act=$(res_active_theme)
    LIST=$(mktemp)

    mark="❖"; [ "$act" = all ] && mark="✔"
    ROWS+=("theme|all")
    printf '%s\0icon\x1f%s\n' "$mark  All of Teyvat · $(count_images "$WALL_DIR")" "$(collage "$WALL_DIR")" >> "$LIST"

    for d in "$WALL_DIR"/*/; do
        [ -d "$d" ] || continue
        d=${d%/}; name=${d##*/}
        f=$(first_image "$d")
        [ -n "$f" ] || continue
        mark="❖"; [ "$act" = "$name" ] && mark="✔"
        ROWS+=("theme|$name")
        printf '%s\0icon\x1f%s\n' "$mark  $(pretty "$name") · $(count_images "$d") · $(theme_accent_label "$d")" "$(collage "$d")" >> "$LIST"
    done

    ROWS+=("new|");  printf '%s\0icon\x1f%s\n' "＋  New theme" "$(new_icon)" >> "$LIST"

    mode=$(sed -n 's/^AUTO_MODE="\(.*\)"/\1/p' "$WCONF" 2>/dev/null | tail -n1)
    ROWS+=("auto|"); printf '%s\0icon\x1f%s\n' "⏱  Auto change · ${mode:-off}" "$(swatch c9e8ff 3d5a99)" >> "$LIST"

    if compgen -G "$TRASH/themes/*" >/dev/null 2>&1; then
        ROWS+=("trash|"); printf '%s\0icon\x1f%s\n' "♻  Trash" "$(swatch 8a8f9c 464b58)" >> "$LIST"
    fi

    shown=$([ "$act" = all ] && echo 'All of Teyvat' || pretty "$act")
    idx=$(rofi -dmenu -i -show-icons -format i -no-custom -p "✦" \
            -mesg "$(title_mesg "Theme Builder" "active: $(esc "$shown") · Super+Shift+W shows the images of the active theme")" \
            -theme "$ROFI_THEME" -theme-str 'listview { columns: 4; } element-icon { size: 180px; }' < "$LIST")
    rm -f "$LIST"
    [ -n "$idx" ] || exit 0

    IFS='|' read -r kind arg <<< "${ROWS[$idx]}"
    case "$kind" in
        new)   create_theme ;;
        auto)  auto_menu ;;
        trash) trash_menu; main_menu ;;
        theme) if [ "$arg" = all ]; then activate_theme all; else theme_menu "$arg"; fi ;;
    esac
}

main_menu
