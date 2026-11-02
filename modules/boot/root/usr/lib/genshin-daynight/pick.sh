#!/bin/sh
THEME="${1:-/usr/share/plymouth/themes/genshin-loading}"
CONF="${GS_CONF:-/etc/genshin-daynight.conf}"
RTC="${GS_RTC:-/sys/class/rtc/rtc0}"
GS_UTC_OFFSET=0
GS_FORCE=auto
[ -r "$CONF" ] && . "$CONF"

mode=night
case "$GS_FORCE" in
    day|night) mode="$GS_FORCE" ;;
    *)
        t=""
        if [ -n "${GS_FAKE_TIME:-}" ]; then
            t="$GS_FAKE_TIME"
        elif [ -r "$RTC/time" ]; then
            read -r t < "$RTC/time"
        else
            t="$(date -u +%H:%M:%S 2>/dev/null)"
        fi
        h="${t%%:*}"; r="${t#*:}"; m="${r%%:*}"; s="${r#*:}"
        h="${h#0}"; m="${m#0}"; s="${s#0}"
        ok=1
        for v in "$h" "$m" "$s"; do
            case "$v" in ''|*[!0-9]*) [ "$v" = "" ] || ok=0 ;; esac
        done
        if [ "$ok" = 1 ]; then
            secs=$(( ${h:-0} * 3600 + ${m:-0} * 60 + ${s:-0} + GS_UTC_OFFSET ))
            secs=$(( (secs % 86400 + 86400) % 86400 ))
            hour=$(( secs / 3600 ))
            if [ "$hour" -ge 6 ] && [ "$hour" -lt 18 ]; then mode=day; fi
        fi
        ;;
esac

if [ -f "$THEME/$mode.script" ]; then
    rm -f "$THEME/genshin-loading.script"
    cp "$THEME/$mode.script" "$THEME/genshin-loading.script"
fi
[ -n "${GS_PRINT:-}" ] && echo "$mode"
exit 0
