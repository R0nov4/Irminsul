#!/usr/bin/env bash
# $1 = new wallpaper path (passed by wallpaper.sh)
. "$HOME/.config/hypr-genshin/resonance-lib.sh" || exit 0
res_theme_apply "$(res_active_theme)" "${1:-}"
