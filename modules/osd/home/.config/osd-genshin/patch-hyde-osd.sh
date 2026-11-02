#!/usr/bin/env bash
set -u
VOL_F="$HOME/.local/lib/hyde/volumecontrol.sh"
BRI_F="$HOME/.local/lib/hyde/brightnesscontrol.sh"

if [ "${1:-}" = "--undo" ]; then
    [ -f "$VOL_F.bak-genshin" ] && cp -f "$VOL_F.bak-genshin" "$VOL_F" && echo "[ok] volumecontrol restored"
    [ -f "$BRI_F.bak-genshin" ] && cp -f "$BRI_F.bak-genshin" "$BRI_F" && echo "[ok] brightnesscontrol restored"
    exit 0
fi

if [ -f "$VOL_F" ] && ! grep -q "osd-genshin/vol.sh" "$VOL_F"; then
    [ -f "$VOL_F.bak-genshin" ] || cp -f "$VOL_F" "$VOL_F.bak-genshin"
    sed -i '2i # genshin-osd hook\ncase "${*}" in *i*) exec "$HOME/.config/osd-genshin/vol.sh" up ;; *d*) exec "$HOME/.config/osd-genshin/vol.sh" down ;; *m*) exec "$HOME/.config/osd-genshin/vol.sh" mute ;; esac' "$VOL_F"
fi

if [ -f "$BRI_F" ] && ! grep -q "osd-genshin/bri.sh" "$BRI_F"; then
    [ -f "$BRI_F.bak-genshin" ] || cp -f "$BRI_F" "$BRI_F.bak-genshin"
    sed -i '2i # genshin-osd hook\ncase "${*}" in *i*) exec "$HOME/.config/osd-genshin/bri.sh" up ;; *d*) exec "$HOME/.config/osd-genshin/bri.sh" down ;; esac' "$BRI_F"
fi
