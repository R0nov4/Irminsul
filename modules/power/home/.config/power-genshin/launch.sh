#!/usr/bin/env bash
DIR="$HOME/.config/power-genshin"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

# اگه دیالوگ باز بود، ببندش
if pgrep -f "rofi.*power-genshin/theme.rasi" >/dev/null 2>&1; then
    pkill -f "rofi.*power-genshin/theme.rasi"
    exit 0
fi

# آیکون‌های خودت (icons/) اولویت دارن، بعد پیش‌فرض‌ها (icons/default/)
icon() {
    local n="$1" d e
    for d in "$DIR/icons" "$DIR/icons/default"; do
        for e in png svg webp jpg; do
            if [ -f "$d/$n.$e" ]; then
                printf '%s' "$d/$n.$e"
                return
            fi
        done
    done
}

row() { printf '%s\x00icon\x1f%s\n' "$1" "$(icon "$2")"; }

MSG=$'Current progress in Teyvat will be saved automatically.\nSelect an action to proceed:'

IDX=$({
    row "Quit to Desktop (Power Off)" poweroff
    row "Reconnect Server (Reboot)"   reboot
    row "Log Out to Celestia"         logout
    row "Lock Screen (Wait)"          lock
} | rofi -no-config -dmenu -i -no-custom -show-icons -format i \
        -theme "$DIR/theme.rasi" \
        -mesg "$MSG" \
        -selected-row 0)

[ -z "$IDX" ] && exit 0

case "$IDX" in
    0) systemctl poweroff ;;
    1) systemctl reboot ;;
    2)
        # uwsm-managed session: stop it cleanly. Otherwise (SDDM starts Hyprland directly)
        # prefer hyprshutdown, then the Lua dispatcher. Hyprland 0.55+ no longer accepts
        # the old "hyprctl dispatch exit" syntax.
        if command -v uwsm >/dev/null 2>&1 && uwsm check is-active >/dev/null 2>&1; then
            timeout 10 uwsm stop >/dev/null 2>&1
            # if the session is still alive here, uwsm stop did not end the session:
            # fall back to the Lua exit dispatcher (this script dies first when it worked)
            sleep 4
            hyprctl dispatch 'hl.dsp.exit()'
        elif command -v hyprshutdown >/dev/null 2>&1; then
            hyprshutdown
        else
            hyprctl dispatch 'hl.dsp.exit()'
        fi
        ;;
    3)
        if [ -x "$HOME/.config/hyprlock-genshin/launch.sh" ]; then
            "$HOME/.config/hyprlock-genshin/launch.sh"
        else
            hyprlock
        fi
        ;;
esac
