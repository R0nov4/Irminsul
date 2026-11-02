local S = genshin
local B, X, FN = S.bind, S.exec, S.fn
local MOD = "SUPER"

-- Set to true if you want HyDE's own alt-tab switcher instead of the simple
-- cycle that genshin.lua binds.
local USE_HYDE_ALTTAB = false
-- Extra Genshin-only binds that HyDE does not have
local GENSHIN_EXTRAS = true

-- description + optional flags (locked, repeating, release, transparent, mouse)
local function D(text, flags)
    local t = { description = text }
    if flags then
        for k, v in pairs(flags) do
            t[k] = v
        end
    end
    return t
end

local apps = {
    terminal = "kitty",
    explorer = "dolphin || thunar || nautilus",
    browser = "google-chrome-stable || firefox || brave",
    editor = "code || codium || kitty -e nvim",
}

-- ----------------------------------------------------------------------------
-- helper actions
-- ----------------------------------------------------------------------------
local function cycle_fullscreen()
    local w = hl.get_active_window()
    if not w then
        return
    end
    local current = tonumber(w.fullscreen) or 0
    local nxt = (current + 1) % 3
    hl.dispatch(hl.dsp.window.fullscreen_state({ internal = nxt, client = nxt, window = w }))
end

local function move_window(dir, pix)
    local lut = { l = { -1, 0 }, r = { 1, 0 }, u = { 0, -1 }, d = { 0, 1 } }
    local m = lut[dir]
    return function()
        local w = hl.get_active_window()
        if not w then
            return
        end
        local args = w.floating and { x = m[1] * pix, y = m[2] * pix, relative = true } or { direction = dir }
        hl.dispatch(hl.dsp.window.move(args))
    end
end

-- ----------------------------------------------------------------------------
-- Launcher | Apps
-- ----------------------------------------------------------------------------
B(MOD .. " + T", X(apps.terminal), D("[Launcher|Apps] terminal emulator"))
B(MOD .. " + ALT + T", X("hyde-shell pypr toggle console"), D("[Launcher|Apps] dropdown terminal"))
B(MOD .. " + E", X(apps.explorer), D("[Launcher|Apps] file explorer"))
B(MOD .. " + B", X(apps.browser), D("[Launcher|Apps] browser"))
B(MOD .. " + C", X(apps.editor), D("[Launcher|Apps] text editor"))
B("CTRL + SHIFT + ESCAPE", X("hyde-shell system.monitor.sh"), D("[Launcher|Apps] system monitor"))

-- ----------------------------------------------------------------------------
-- Window Management
-- ----------------------------------------------------------------------------
B(MOD .. " + Q", function() return hl.dsp.window.close() end, D("[Window Management] close focused window"))
B("ALT + F4", function() return hl.dsp.window.close() end, D("[Window Management] close focused window"))
B(MOD .. " + ALT + F4", function() return hl.dsp.window.kill() end, D("[Window Management] kill focused window"))
B(MOD .. " + Delete", function() return hl.dsp.exit() end, D("[Window Management] exit hyprland session"))
B(MOD .. " + W", function() return hl.dsp.window.float({ action = "toggle" }) end, D("[Window Management] toggle float true"))
B(MOD .. " + G", function() return hl.dsp.group.toggle() end, D("[Window Management] toggle group"))
B("ALT + P", function() return hl.dsp.window.pseudo() end, D("[Window Management] set a window's pseudotiling state"))
B("SHIFT + F11", FN(cycle_fullscreen), D("[Window Management] cycle fullscreen"))
B(MOD .. " + SHIFT + F", function() return hl.dsp.window.pin() end, D("[Window Management] toggle pin"))
B("CTRL + ALT + DELETE", X("$HOME/.config/power-genshin/launch.sh"), D("[Window Management] logout menu"))

-- With the Genshin waybar the bar is hidden with SIGUSR1; otherwise HyDE's way
local bar_hide = S.exists(S.home .. "/.config/waybar-genshin/start.sh") and "pkill -SIGUSR1 -x waybar" or "hyde-shell waybar --hide"
B(MOD .. " + CTRL + B", X(bar_hide), D("[Window Management] hide waybar"))
B(MOD .. " + L", X(S.home .. "/.config/hyprlock-genshin/launch.sh"), D("[Genshin] lock screen"))

B(MOD .. " + CTRL + H", function() return hl.dsp.group.prev() end, D("[Window Management|Group Navigation] change active group backwards"))
B(MOD .. " + CTRL + L", function() return hl.dsp.group.next() end, D("[Window Management|Group Navigation] change active group forwards"))

-- Change focus
B(MOD .. " + Left", function() return hl.dsp.focus({ direction = "left" }) end, D("[Window Management|Change focus] focus left"))
B(MOD .. " + Right", function() return hl.dsp.focus({ direction = "right" }) end, D("[Window Management|Change focus] focus right"))
B(MOD .. " + Up", function() return hl.dsp.focus({ direction = "up" }) end, D("[Window Management|Change focus] focus up"))
B(MOD .. " + Down", function() return hl.dsp.focus({ direction = "down" }) end, D("[Window Management|Change focus] focus down"))

-- Alt-Tab (HyDE's own switcher is optional, see USE_HYDE_ALTTAB)
if USE_HYDE_ALTTAB then
    B("ALT + TAB", X("hyde-shell altab --next"), D("[Window Management|alt-tab window switcher] cycle next", { transparent = true }))
    B("ALT + SHIFT + TAB", X("hyde-shell altab --prev"), D("[Window Management|alt-tab window switcher] cycle previous", { transparent = true }))
    B("ALT + ALT_R", X("hyde-shell altab --apply"), D("[Window Management|alt-tab window switcher] switch", { release = true, transparent = true }))
    B("ALT + ALT_L", X("hyde-shell altab --apply"), D("[Window Management|alt-tab window switcher] switch"))
end

-- Resize active window
B(MOD .. " + SHIFT + RIGHT", function() return hl.dsp.window.resize({ x = 30, y = 0, relative = true }) end, D("[Window Management|Resize Active Window] resize window right", { repeating = true }))
B(MOD .. " + SHIFT + LEFT", function() return hl.dsp.window.resize({ x = -30, y = 0, relative = true }) end, D("[Window Management|Resize Active Window] resize window left", { repeating = true }))
B(MOD .. " + SHIFT + UP", function() return hl.dsp.window.resize({ x = 0, y = -30, relative = true }) end, D("[Window Management|Resize Active Window] resize window up", { repeating = true }))
B(MOD .. " + SHIFT + DOWN", function() return hl.dsp.window.resize({ x = 0, y = 30, relative = true }) end, D("[Window Management|Resize Active Window] resize window down", { repeating = true }))

-- Move active window
B(MOD .. " + SHIFT + CONTROL + LEFT", FN(move_window("l", 30)), D("[Window Management|Move active window] left", { repeating = true }))
B(MOD .. " + SHIFT + CONTROL + RIGHT", FN(move_window("r", 30)), D("[Window Management|Move active window] right", { repeating = true }))
B(MOD .. " + SHIFT + CONTROL + UP", FN(move_window("u", 30)), D("[Window Management|Move active window] up", { repeating = true }))
B(MOD .. " + SHIFT + CONTROL + DOWN", FN(move_window("d", 30)), D("[Window Management|Move active window] down", { repeating = true }))

-- Mouse drag / resize
B(MOD .. " + mouse:272", function() return hl.dsp.window.drag() end, D("[Window Management|Drag & Resize with mouse] drag window", { mouse = true }))
B(MOD .. " + mouse:273", function() return hl.dsp.window.resize() end, D("[Window Management|Drag & Resize with mouse] resize window", { mouse = true }))
B(MOD .. " + Z", function() return hl.dsp.window.drag() end, D("[Window Management|Drag & Resize with mouse] hold to move window", { mouse = true }))
B(MOD .. " + X", function() return hl.dsp.window.resize() end, D("[Window Management|Drag & Resize with mouse] hold to resize window", { mouse = true }))

-- Layout
B(MOD .. " + J", function() return hl.dsp.layout("togglesplit") end, D("[Layout Management|Dwindle] toggle split"))

-- ----------------------------------------------------------------------------
-- Rofi menus
-- ----------------------------------------------------------------------------
B(MOD .. " + A", X("$HOME/.config/rofi-genshin/launch.sh"), D("[Launcher|Rofi menus] application finder"))
B(MOD .. " + TAB", X("rofi -show window -theme $HOME/.config/rofi-genshin/clipboard.rasi"), D("[Launcher|Rofi menus] window switcher"))
B(MOD .. " + SHIFT + E", X("rofi -show filebrowser -theme $HOME/.config/rofi-genshin/clipboard.rasi"), D("[Launcher|Rofi menus] file finder"))
B(MOD .. " + slash", X("hyde-shell keybinds_hint"), D("[Launcher|Rofi menus] keybindings hint"))
B(MOD .. " + comma", X("hyde-shell emoji-picker"), D("[Launcher|Rofi menus] emoji picker"))
B(MOD .. " + period", X("hyde-shell glyph-picker"), D("[Launcher|Rofi menus] glyph picker"))
B(MOD .. " + V", X("$HOME/.config/rofi-genshin/clipboard.sh"), D("[Launcher|Rofi menus] clipboard"))
B(MOD .. " + SHIFT + V", X("$HOME/.config/rofi-genshin/clipboard.sh --wipe"), D("[Launcher|Rofi menus] clipboard manager"))
-- [Removed HyDE Theme Bind]
B(MOD .. " + SHIFT + K", X("hyde-shell calculator"), D("[Launcher|Rofi menus] Calculator"))
B(MOD .. " + SHIFT + slash", X("hyde-shell rofi.websearch"), D("[Launcher|Rofi menus] Web Search"))

-- ----------------------------------------------------------------------------
-- Hardware controls
-- ----------------------------------------------------------------------------
-- B("F10", X("$HOME/.config/osd-genshin/vol.sh mute || wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), D("[Hardware Controls|Audio] un/mute output", { locked = true }))
-- B("F11", X("$HOME/.config/osd-genshin/vol.sh down || wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), D("[Hardware Controls|Audio] decrease volume", { locked = true, repeating = true }))
-- B("F12", X("$HOME/.config/osd-genshin/vol.sh up || wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+"), D("[Hardware Controls|Audio] increase volume", { locked = true, repeating = true }))
B("XF86AudioMute", X("$HOME/.config/osd-genshin/vol.sh mute || wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), D("[Hardware Controls|Audio] un/mmute output", { locked = true }))
B("XF86AudioMicMute", X("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), D("[Hardware Controls|Audio] un/mute microphone", { locked = true }))
B("XF86AudioLowerVolume", X("$HOME/.config/osd-genshin/vol.sh down || wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), D("[Hardware Controls|Audio] decrease volume", { locked = true, repeating = true }))
B("XF86AudioRaiseVolume", X("$HOME/.config/osd-genshin/vol.sh up || wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+"), D("[Hardware Controls|Audio] increase volume", { locked = true, repeating = true }))

B("XF86AudioPlay", X("playerctl play-pause"), D("[Hardware Controls|Media] play media", { locked = true }))
B("XF86AudioPause", X("playerctl play-pause"), D("[Hardware Controls|Media] pause media", { locked = true }))
B("XF86AudioNext", X("playerctl next"), D("[Hardware Controls|Media] next media", { locked = true }))
B("XF86AudioPrev", X("playerctl previous"), D("[Hardware Controls|Media] previous media", { locked = true }))
B(MOD .. " + CONTROL + M", X("hyde-shell window.mute"), D("[Hardware Controls|Media] toggle un/mute for active-window"))

B("XF86MonBrightnessUp", X("$HOME/.config/osd-genshin/bri.sh up || brightnessctl set 5%+"), D("[Hardware Controls|Brightness] increase brightness", { locked = true, repeating = true }))
B("XF86MonBrightnessDown", X("$HOME/.config/osd-genshin/bri.sh down || brightnessctl set 5%-"), D("[Hardware Controls|Brightness] decrease brightness", { locked = true, repeating = true }))

-- ----------------------------------------------------------------------------
-- Utilities
-- ----------------------------------------------------------------------------
B(MOD .. " + K", X("hyprctl switchxkblayout all next"), D("[Utilities] toggle keyboard layout", { locked = true }))
B(MOD .. " + ALT + G", X("hyde-shell gamemode"), D("[Utilities] game mode", { locked = true }))
B(MOD .. " + SHIFT + G", X("hyde-shell gamelauncher"), D("[Utilities] game launcher"))

B(MOD .. " + SHIFT + P", X("hyprpicker -an"), D("[Utilities] screen capture] color picker", { locked = true }))
B(MOD .. " + P", X("$HOME/.config/osd-genshin/screenshot.sh s"), D("[Utilities] partial screenshot capture", { locked = true }))
B(MOD .. " + CONTROL + P", X("$HOME/.config/osd-genshin/screenshot.sh sf"), D("[Utilities] freeze and snip screen", { locked = true }))
B(MOD .. " + ALT + P", X("$HOME/.config/osd-genshin/screenshot.sh m"), D("[Utilities] print monitor", { locked = true }))
B("Print", X("$HOME/.config/osd-genshin/screenshot.sh p"), D("[Utilities] print all monitors", { locked = true }))
B(MOD .. " + CONTROL + S", X("hyde-shell screenshot sc"), D("[Utilities] OCR scanner", { locked = true }))

-- ----------------------------------------------------------------------------
-- Theming and wallpaper
-- ----------------------------------------------------------------------------
B(MOD .. " + ALT + Right", X("@HOME@/.config/hypr-genshin/wallpaper.sh --next"), D("[Theming and Wallpaper] next global wallpaper"))
B(MOD .. " + ALT + Left", X("@HOME@/.config/hypr-genshin/wallpaper.sh --prev"), D("[Theming and Wallpaper] previous global wallpaper"))
-- B(MOD .. " + ALT + Up", X("hyde-shell waybar --next"), D("[Theming and Wallpaper] next Waybar layout"))
-- B(MOD .. " + ALT + Down", X("hyde-shell waybar --prev"), D("[Theming and Wallpaper] previous Waybar layout"))
B(MOD .. " + SHIFT + W", X("@HOME@/.config/hypr-genshin/wallpaper.sh --menu"), D("[Theming and Wallpaper] select a global wallpaper"))
B(MOD .. " + SHIFT + R", X("$HOME/.config/hypr-genshin/ambience-menu.sh"), D("[Genshin] Teyvat Ambience & Auto-Resonance"))
B(MOD .. " + SHIFT + T", X("$HOME/.config/hypr-genshin/theme-select.sh"), D("[Genshin] Elemental Resonance Theme Switcher"))
-- B(MOD .. " + SHIFT + Y", X("hyde-shell animations --select"), D("[Theming and Wallpaper] select animations"))
-- B(MOD .. " + SHIFT + U", X("hyde-shell hyprlock --select"), D("[Theming and Wallpaper] select Hyprlock layout"))

-- ----------------------------------------------------------------------------
-- Workspaces
-- ----------------------------------------------------------------------------
-- Numpad keys for workspaces 11-20: bound under both keysyms (NumLock on/off)
local kp = {
    [1] = { "KP_1", "KP_End" },
    [2] = { "KP_2", "KP_Down" },
    [3] = { "KP_3", "KP_Next" },
    [4] = { "KP_4", "KP_Left" },
    [5] = { "KP_5", "KP_Begin" },
    [6] = { "KP_6", "KP_Right" },
    [7] = { "KP_7", "KP_Home" },
    [8] = { "KP_8", "KP_Up" },
    [9] = { "KP_9", "KP_Prior" },
    [10] = { "KP_0", "KP_Insert" },
}

for i = 1, 10 do
    local key = (i == 10) and 0 or i
    B(MOD .. " + " .. key, function() return hl.dsp.focus({ workspace = i }) end, D("[Workspaces|Navigation] navigate to workspace " .. i))
end

for i = 1, 10 do
    for _, key in ipairs(kp[i]) do
        B(MOD .. " + " .. key, function() return hl.dsp.focus({ workspace = tostring(i + 10) }) end, D("[Workspaces|Navigation] navigate to workspace " .. (i + 10)))
    end
end

B(MOD .. " + CONTROL + RIGHT", function() return hl.dsp.focus({ workspace = "r+1" }) end, D("[Workspaces|Navigation|Relative workspace] change active workspace forwards"))
B(MOD .. " + CONTROL + LEFT", function() return hl.dsp.focus({ workspace = "r-1" }) end, D("[Workspaces|Navigation|Relative workspace] change active workspace backwards"))
B(MOD .. " + CONTROL + DOWN", function() return hl.dsp.focus({ workspace = "empty" }) end, D("[Workspaces|Navigation] navigate to the nearest empty workspace"))

for i = 1, 10 do
    local key = (i == 10) and 0 or i
    B(MOD .. " + SHIFT + " .. key, function() return hl.dsp.window.move({ workspace = i }) end, D("[Workspaces|Move window to workspace] move focused window to workspace " .. i))
end

for i = 1, 10 do
    for _, key in ipairs(kp[i]) do
        B(MOD .. " + SHIFT + " .. key, function() return hl.dsp.window.move({ workspace = tostring(i + 10) }) end, D("[Workspaces|Move window to workspace] move focused window to workspace " .. (i + 10)))
    end
end

B(MOD .. " + CONTROL + ALT + RIGHT", function() return hl.dsp.window.move({ workspace = "r+1" }) end, D("[Workspaces|Move window to workspace|Relative workspace] move focused window to next workspace"))
B(MOD .. " + CONTROL + ALT + LEFT", function() return hl.dsp.window.move({ workspace = "r-1" }) end, D("[Workspaces|Move window to workspace|Relative workspace] move focused window to previous workspace"))

B(MOD .. " + mouse_down", function() return hl.dsp.focus({ workspace = "e+1" }) end, D("[Workspaces|Navigation|Mouse] next workspace"))
B(MOD .. " + mouse_up", function() return hl.dsp.focus({ workspace = "e-1" }) end, D("[Workspaces|Navigation|Mouse] previous workspace"))

-- Special workspace (scratchpad)
B(MOD .. " + S", function() return hl.dsp.workspace.toggle_special() end, D("[Workspaces|Navigation|Special workspace] toggle scratchpad"))
B(MOD .. " + SHIFT + S", function() return hl.dsp.window.move({ workspace = "special" }) end, D("[Workspaces|Navigation|Special workspace] move focused window to scratchpad"))
B(MOD .. " + ALT + S", function() return hl.dsp.window.move({ workspace = "special", follow = false }) end, D("[Workspaces|Navigation|Special workspace] move focused window silently to scratchpad"))

-- Move window silently (don't follow)
for i = 1, 10 do
    local key = (i == 10) and 0 or i
    B(MOD .. " + ALT + " .. key, function() return hl.dsp.window.move({ workspace = i, follow = false }) end, D("[Workspaces|Move window (Don't follow)] move focused window to workspace " .. i))
end

-- ----------------------------------------------------------------------------
-- Genshin extras (not in HyDE)
-- ----------------------------------------------------------------------------
if GENSHIN_EXTRAS then
    B(MOD .. " + F", function() return hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" }) end, D("[Genshin] toggle maximize"))
    local power = S.home .. "/.config/power-genshin/launch.sh"
    if S.exists(power) then
        B(MOD .. " + BackSpace", X(power), D("[Genshin] power menu"))
    end
end
