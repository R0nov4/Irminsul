-- Genshin Impact: window borders, animations, cursor

hl.config({
    general = {
        border_size = 2,
        gaps_in = 6,
        gaps_out = 12,
        col = {
            active_border = { colors = { "rgba(f4e8c1ff)", "rgba(d3bc8eff)", "rgba(7ec8ffaa)", "rgba(f4e8c1ff)" }, angle = 45 },
            inactive_border = { colors = { "rgba(3b4255cc)", "rgba(262b39cc)" }, angle = 45 },
        },
    },
    decoration = {
        rounding = 14,
        blur = { enabled = true, size = 6, passes = 3, new_optimizations = true },
        shadow = { enabled = true, range = 22, render_power = 3, color = 0xcc0d1018 },
    },
})

hl.curve("teyvatSnap", { type = "bezier", points = { {0.16, 1.0}, {0.3, 1.0} } })
hl.curve("teyvatSoft", { type = "bezier", points = { {0.25, 1.0}, {0.5, 1.0} } })

hl.animation({ leaf = "windows",     enabled = true, speed = 4,  bezier = "teyvatSnap", style = "popin 82%" })
hl.animation({ leaf = "windowsOut",  enabled = true, speed = 4,  bezier = "teyvatSoft", style = "popin 85%" })
hl.animation({ leaf = "windowsMove", enabled = true, speed = 4,  bezier = "teyvatSnap", style = "slide" })
hl.animation({ leaf = "border",      enabled = true, speed = 6,  bezier = "default" })
hl.animation({ leaf = "borderangle", enabled = true, speed = 90, bezier = "teyvatSoft", style = "loop" })
hl.animation({ leaf = "fade",        enabled = true, speed = 4,  bezier = "teyvatSoft" })
hl.animation({ leaf = "workspaces",  enabled = true, speed = 5,  bezier = "teyvatSnap", style = "slidefade 18%" })


-- Genshin Cursor
hl.env("XCURSOR_THEME", "Genshin-Official")
hl.env("XCURSOR_SIZE", "32")
hl.env("HYPRCURSOR_THEME", "Genshin-Official")
hl.env("HYPRCURSOR_SIZE", "32")

hl.on("hyprland.start", function()
  hl.exec_cmd("hyprctl setcursor Genshin-Official 32")
  hl.exec_cmd(os.getenv("HOME") .. "/.config/waybar-genshin/scripts/genshin-scale watch")
end)

hl.on("hyprland.start", function()
end)

hl.on("hyprland.start", function()
  hl.exec_cmd("@HOME@/.config/hypr-genshin/cursor-fix.sh")
  hl.exec_cmd("@HOME@/.config/hypr-genshin/cursor-guard.sh")
end)


-- >>> Genshin Keybinds >>>
-- جلوگیری از دوبار ثبت شدن اگر HyDE خودش این کلیدها رو داشت
pcall(hl.unbind, "ALT + Tab")
pcall(hl.unbind, "ALT + SHIFT + Tab")

-- Alt + Tab : پنجره بعدی
hl.bind("ALT + Tab", function()
    hl.dispatch(hl.dsp.window.cycle_next())
    hl.dispatch(hl.dsp.window.bring_to_top())
end)

-- Alt + Shift + Tab : پنجره قبلی
hl.bind("ALT + SHIFT + Tab", function()
    hl.dispatch(hl.dsp.window.cycle_next({ next = false }))
    hl.dispatch(hl.dsp.window.bring_to_top())
end)
-- <<< Genshin Keybinds <<<

-- GENSHIN_STRIP_HYDE_BINDS: remove HyDE theme-switching binds (HyDE's Lua layer registers them)
do
    local keys = {
        "SUPER + SHIFT + Y",
        "SUPER + SHIFT + U", "SUPER + SHIFT + A",
        "SUPER + ALT + Up", "SUPER + ALT + Down",
    }
    local function strip()
        for _, k in ipairs(keys) do
            pcall(hl.unbind, k)
        end
    end
    pcall(strip)
    -- the HyDE layer may register its binds after this file, so strip again once the session is up
    pcall(hl.on, "hyprland.start", function()
        pcall(hl.exec_cmd, [==[sleep 6; hyprctl eval 'for _, k in ipairs({"SUPER + SHIFT + Y","SUPER + SHIFT + U","SUPER + SHIFT + A","SUPER + ALT + Up","SUPER + ALT + Down"}) do pcall(hl.unbind, k) end']==])
    end)
end


-- Load saved Genshin Elemental Resonance color if set
do
    local f = io.open(os.getenv("HOME") .. "/.config/hypr-genshin/element-override.conf", "r")
    if f then
        local txt = f:read("*a")
        f:close()
        local c1 = txt:match('C1="([0-9a-fA-F]+)"')
        local c2 = txt:match('C2="([0-9a-fA-F]+)"')
        local c3 = txt:match('C3="([0-9a-fA-F]+)"')
        if c1 and c2 and c3 then
            pcall(hl.config, {
                general = {
                    col = {
                        active_border = { colors = { "rgba(" .. c1 .. ")", "rgba(" .. c2 .. ")", "rgba(" .. c3 .. ")", "rgba(" .. c1 .. ")" }, angle = 45 },
                    },
                },
            })
        end
    end
end

-- >>> genshin-polkit
pcall(function() hl.exec_cmd(os.getenv("HOME") .. "/.local/bin/genshin-polkit-launch") end)
-- <<< genshin-polkit
