-- =========================================================================
-- Genshin Impact Standalone Core (Hyprland 0.55+ Lua Config)
-- =========================================================================

-- مانیتورها (تنظیم اتوماتیک حداکثر رزولوشن و رفرش‌ریت)
hl.config({
    monitor = { ",preferred,auto,1" },
    
    -- ظاهر پنجره‌ها و قاب طلایی Celestia
    general = {
        border_size = 2,
        gaps_in = 6,
        gaps_out = 12,
        col = {
            active_border = { colors = { "rgba(f4e8c1ff)", "rgba(d3bc8eff)", "rgba(7ec8ffaa)", "rgba(f4e8c1ff)" }, angle = 45 },
            inactive_border = { colors = { "rgba(3b4255cc)", "rgba(262b39cc)" }, angle = 45 },
        },
        layout = "dwindle",
    },

    decoration = {
        rounding = 14,
        blur = { enabled = true, size = 6, passes = 3, new_optimizations = true },
        shadow = { enabled = true, range = 22, render_power = 3, color = 0xcc0d1018 },
    },

    input = {
        follow_mouse = 1,
        touchpad = { natural_scroll = true },
    },
})

-- انیمیشن‌های نرم منوی بازی
hl.curve("teyvatSnap", { type = "bezier", points = { {0.16, 1.0}, {0.3, 1.0} } })
hl.curve("teyvatSoft", { type = "bezier", points = { {0.25, 1.0}, {0.5, 1.0} } })

hl.animation({ leaf = "windows",     enabled = true, speed = 4,  bezier = "teyvatSnap", style = "popin 82%" })
hl.animation({ leaf = "windowsOut",  enabled = true, speed = 4,  bezier = "teyvatSoft", style = "popin 85%" })
hl.animation({ leaf = "windowsMove", enabled = true, speed = 4,  bezier = "teyvatSnap", style = "slide" })
hl.animation({ leaf = "border",      enabled = true, speed = 6,  bezier = "default" })
hl.animation({ leaf = "borderangle", enabled = true, speed = 90, bezier = "teyvatSoft", style = "loop" })
hl.animation({ leaf = "fade",        enabled = true, speed = 4,  bezier = "teyvatSoft" })
hl.animation({ leaf = "workspaces",  enabled = true, speed = 5,  bezier = "teyvatSnap", style = "slidefade 18%" })

-- استارت‌آپ سرویس‌های مستقل جنشین (Waybar، Dunst، OSD، Wallpaper)
hl.exec("swww-daemon &")
hl.exec("$HOME/.config/waybar-genshin/start.sh &")
hl.exec("$HOME/.config/dunst-genshin/start.sh &")
hl.exec("polkit-kde-authentication-agent-1 &")

-- =========================================================================
-- شورتکات‌های مستقل (Keybindings)
-- =========================================================================
local mod = "SUPER"

-- مدیریت پنجره‌ها و سیستم
hl.bind(mod, "Q", "exec", "hyprctl dispatch killactive")
hl.bind(mod, "F", "exec", "hyprctl dispatch fullscreen")
hl.bind(mod, "V", "exec", "hyprctl dispatch togglefloating")
hl.bind(mod, "T", "exec", "kitty")
hl.bind(mod, "RETURN", "exec", "kitty")
hl.bind(mod, "BACKSPACE", "exec", "$HOME/.config/power-genshin/launch.sh")
hl.bind(mod, "L", "exec", "$HOME/.config/hyprlock-genshin/launch.sh || hyprlock")

-- منوی برنامه‌ها (Rofi Paimon) و کلیپ‌بورد
hl.bind(mod, "SPACE", "exec", "$HOME/.config/rofi-genshin/launch.sh")
hl.bind(mod, "A", "exec", "$HOME/.config/rofi-genshin/launch.sh")
hl.bind(mod, "C", "exec", "cliphist list | rofi -dmenu | cliphist decode | wl-copy")

-- اسکرین‌شات فوری با نوتیفیکیشن جنشین
hl.bind("", "Print", "exec", "grim -g \"$(slurp)\" - | wl-copy && notify-send -a \"Paimon\" \"Screenshot\" \"Captured to clipboard\"")

-- جابه‌جایی و مدیریت ورک‌اسپیس‌ها (1 تا 7)
for i = 1, 7 do
    hl.bind(mod, tostring(i), "exec", "hyprctl dispatch workspace " .. i)
    hl.bind(mod .. " SHIFT", tostring(i), "exec", "hyprctl dispatch movetoworkspace " .. i)
end

-- جابه‌جایی با ماوس بین پنجره‌ها
hl.bindm(mod, "mouse:272", "movewindow")
hl.bindm(mod, "mouse:273", "resizewindow")
