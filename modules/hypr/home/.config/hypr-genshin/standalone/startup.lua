local S = genshin
local H = S.home

local systemd_env = "WAYLAND_DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_TYPE XDG_SESSION_DESKTOP XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME QT_QPA_PLATFORMTHEME"

local cmds = {
    -- ۱. متغیرهای محیطی D-Bus و Systemd
    "dbus-update-activation-environment --systemd " .. systemd_env,
    "hyprctl setcursor Genshin-Official 32 && gsettings set org.gnome.desktop.interface cursor-theme Genshin-Official || true",
    "systemctl --user import-environment " .. systemd_env,
    "command -v uwsm >/dev/null 2>&1 && uwsm finalize || true",

    -- ۲. موتور والپیپر مستقل (swww + آخرین والپیپر جنشین)
    "pgrep -x swww-daemon >/dev/null || swww-daemon &",
    "if [ -x " .. H .. "/.config/wallpaper-genshin/wallpaper.sh ]; then " ..
        "shopt -s nullglob; w=(" .. H .. "/.config/wallpaper-genshin/*.{png,jpg,jpeg}); " ..
        "[ ${#w[@]} -gt 0 ] && " .. H .. "/.config/wallpaper-genshin/wallpaper.sh \"${w[0]}\" >/dev/null 2>&1 & " ..
    "fi",

    -- ۳. نوار بالای Genshin Waybar و نوتیفیکیشن Genshin Dunst
    H .. "/.config/waybar-genshin/start.sh &",
    H .. "/.config/dunst-genshin/start.sh &",

    -- ۴. ایجنت احراز هویت Polkit (تشخیص خودکار مسیر در آرچ لینوکس)
    "pgrep -f 'polkit.*agent' >/dev/null || (" ..
        "/usr/lib/polkit-kde-authentication-agent-1 || " ..
        "/usr/lib/hyprpolkitagent/hyprpolkitagent || " ..
        "/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1" ..
    ") &",

    -- ۵. تاریخچه کلیپ‌بورد (متن و تصویر برای منوی Super + V)
    "pgrep -f '^wl-paste --type text' >/dev/null || wl-paste --type text --watch cliphist store &",
    "pgrep -f '^wl-paste --type image' >/dev/null || wl-paste --type image --watch cliphist store &",

    -- ۶. قفل خودکار، فیلتر نور آبی و اپلت‌های سیستم‌تری
    "pgrep -x hypridle >/dev/null || (command -v hypridle >/dev/null && hypridle) &",
    "pgrep -x hyprsunset >/dev/null || (command -v hyprsunset >/dev/null && hyprsunset) &",
    -- "pgrep -x nm-applet >/dev/null || (command -v nm-applet >/dev/null && nm-applet --indicator) &",
    "pgrep -x udiskie >/dev/null || (command -v udiskie >/dev/null && udiskie --no-automount --smart-tray) &",
    "pgrep -x blueman-applet >/dev/null || (command -v blueman-applet >/dev/null && blueman-applet) &",
}

local ok, err = pcall(hl.on, "hyprland.start", function()
    for _, cmd in ipairs(cmds) do
        pcall(hl.exec_cmd, cmd)
    end
end)
if not ok then
    S.fail("hyprland.start hook", err)
end
