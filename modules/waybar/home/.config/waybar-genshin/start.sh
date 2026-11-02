#!/usr/bin/env bash
# start.sh          : نوار جنشین رو (اگه بالا نیست) بالا میاره. چند بار صدا زدنش مشکلی نداره.
# start.sh restart  : می‌بندتش و دوباره بالا میاره.
LOG=/tmp/genshin-bar.log
CFG="$HOME/.config/waybar-genshin/config.jsonc"
CSS="$HOME/.config/waybar-genshin/style.css"

exec 8>/tmp/genshin-start.lock
flock -w 30 8 || exit 0

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
echo "[$(date +%T)] start.sh ($*)" >> "$LOG"

if [ "${1:-}" = "restart" ]; then
    pkill -f 'waybar-genshin/config.jsonc' 2>/dev/null
    sleep 0.7
fi

# GENSHIN_STALE_FIX: kill a waybar left over from an old Hyprland session (stale IPC signature)
cur_sig="${HYPRLAND_INSTANCE_SIGNATURE:-$(ls -t "$XDG_RUNTIME_DIR/hypr" 2>/dev/null | head -n1)}"
stale=0
for p in $(pgrep -f 'waybar-genshin/config.jsonc' 2>/dev/null); do
    psig=$(tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | sed -n 's/^HYPRLAND_INSTANCE_SIGNATURE=//p')
    if [ -n "$psig" ] && [ "$psig" != "$cur_sig" ]; then stale=1; fi
done
if [ "$stale" = 1 ]; then
    echo "[$(date +%T)] stale waybar from an old session, replacing" >> "$LOG"
    pkill -f 'waybar-genshin/config.jsonc' 2>/dev/null
    sleep 0.7
fi

if pgrep -f 'waybar-genshin/config.jsonc' >/dev/null 2>&1; then
    echo "[$(date +%T)] already running" >> "$LOG"
    exit 0
fi

# منتظر آماده شدن Hyprland (تا ۳۰ ثانیه)
for i in $(seq 1 60); do
    if [ -z "${WAYLAND_DISPLAY:-}" ]; then
        for s in "$XDG_RUNTIME_DIR"/wayland-*; do
            case "$s" in *.lock) continue ;; esac
            [ -S "$s" ] && { export WAYLAND_DISPLAY="${s##*/}"; break; }
        done
    fi
    if [ -z "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
        sig=$(ls -t "$XDG_RUNTIME_DIR/hypr" 2>/dev/null | head -n1)
        [ -n "$sig" ] && export HYPRLAND_INSTANCE_SIGNATURE="$sig"
    fi
    if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ] \
       && hyprctl monitors >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done
echo "[$(date +%T)] env: WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-} SIG=${HYPRLAND_INSTANCE_SIGNATURE:-}" >> "$LOG"

# شورتکات‌ها رو دوباره ست کن (اگه userprefs.conf لود نشده باشه هم کار کنه)
if [ -x "$HOME/.config/rofi-genshin/launch.sh" ]; then
    hyprctl keyword unbind SUPER,A >/dev/null 2>&1
    hyprctl keyword bind SUPER,A,exec,"$HOME/.config/rofi-genshin/launch.sh" >/dev/null 2>&1
fi
if [ -x "$HOME/.config/hyprlock-genshin/launch.sh" ]; then
if [ -x "$HOME/.config/wlogout-genshin/launch.sh" ]; then
    hyprctl keyword unbind Ctrl,Alt,Delete >/dev/null 2>&1
    hyprctl keyword bind SUPER,Backspace,exec,"$HOME/.config/wlogout-genshin/launch.sh" >/dev/null 2>&1
fi
    hyprctl keyword unbind SUPER,L >/dev/null 2>&1
    hyprctl keyword bind SUPER,L,exec,"$HOME/.config/hyprlock-genshin/launch.sh" >/dev/null 2>&1
if [ -x "$HOME/.config/wlogout-genshin/launch.sh" ]; then
    hyprctl keyword unbind Ctrl,Alt,Delete >/dev/null 2>&1
    hyprctl keyword bind SUPER,Backspace,exec,"$HOME/.config/wlogout-genshin/launch.sh" >/dev/null 2>&1
fi
fi

# نوار خود HyDE رو خاموش کن
systemctl --user stop hyde-Hyprland-bar.service 2>/dev/null
pkill -x waybar 2>/dev/null
sleep 0.3

# اگه آپدیت pacman اسکریپت جای waybar رو پاک کرده باشه، مستقیم با کانفیگ خودمون بالا میاد
if grep -q 'waybar-genshin' /usr/bin/waybar 2>/dev/null; then
    BIN=/usr/bin/waybar.orig
else
    BIN=/usr/bin/waybar
fi
echo "[$(date +%T)] launching $BIN" >> "$LOG"
# اجرای waybar با نگهبان: اگه کرش کرد خودش بعد از ۱ ثانیه دوباره بالا میاد
export BIN CFG CSS LOG
setsid -f bash -c '
n=0
while :; do
    t0=$(date +%s)
    "$BIN" -c "$CFG" -s "$CSS" >> "$LOG" 2>&1
    rc=$?
    case $rc in 0|130|143) break ;; esac
    [ -S "$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket.sock" ] || { echo "[$(date +%T)] hyprland session gone, guard exiting" >> "$LOG"; break; }
    echo "[$(date +%T)] waybar crashed (exit $rc), restarting" >> "$LOG"
    if [ $(( $(date +%s) - t0 )) -lt 5 ]; then n=$((n+1)); else n=0; fi
    if [ "$n" -ge 5 ]; then echo "[$(date +%T)] waybar keeps crashing, giving up" >> "$LOG"; break; fi
    sleep 1
done
' >/dev/null 2>&1 8>&-

# راه‌اندازی نوتیفیکیشن جنشین
if [ -x "$HOME/.config/dunst-genshin/start.sh" ]; then
    "$HOME/.config/dunst-genshin/start.sh" 8>&- &
fi

# راه‌اندازی کلیدهای OSD صدا و نور جنشین
if [ -x "$HOME/.config/osd-genshin/patch-hyde-osd.sh" ]; then
    "$HOME/.config/osd-genshin/patch-hyde-osd.sh" >/dev/null 2>&1
    hyprctl keyword bindel ,XF86AudioRaiseVolume,exec,"$HOME/.config/osd-genshin/vol.sh up 5" >/dev/null 2>&1
    hyprctl keyword bindel ,XF86AudioLowerVolume,exec,"$HOME/.config/osd-genshin/vol.sh down 5" >/dev/null 2>&1
    hyprctl keyword bindl  ,XF86AudioMute,exec,"$HOME/.config/osd-genshin/vol.sh mute" >/dev/null 2>&1
    hyprctl keyword bindel ,XF86MonBrightnessUp,exec,"$HOME/.config/osd-genshin/bri.sh up 5" >/dev/null 2>&1
    hyprctl keyword bindel ,XF86MonBrightnessDown,exec,"$HOME/.config/osd-genshin/bri.sh down 5" >/dev/null 2>&1
fi

# اعمال قاب طلایی پنجره‌ها، انیمیشن‌ها و نشانگر موس جنشین
if [ -x "$HOME/.config/hypr-genshin/apply.sh" ]; then
    "$HOME/.config/hypr-genshin/apply.sh" 8>&- &
fi
