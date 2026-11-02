-- Auto-detect user's system keyboard layout & options
local function detect_user_kb()
    local layout, variant, options = nil, "", ""
    -- 1. Check /etc/X11/xorg.conf.d/00-keyboard.conf (systemd-localed standard)
    local f = io.open("/etc/X11/xorg.conf.d/00-keyboard.conf", "r")
    if f then
        local txt = f:read("*a")
        f:close()
        layout = txt:match('Option%s+"XkbLayout"%s+"([^"]+)"') or layout
        variant = txt:match('Option%s+"XkbVariant"%s+"([^"]+)"') or variant
        options = txt:match('Option%s+"XkbOptions"%s+"([^"]+)"') or options
    end
    -- 2. Fallback to /etc/vconsole.conf
    if not layout or layout == "" then
        local vf = io.open("/etc/vconsole.conf", "r")
        if vf then
            local vtxt = vf:read("*a")
            vf:close()
            local km = vtxt:match("KEYMAP=([%w_%-]+)")
            if km then layout = km:match("^([a-zA-Z]+)") end
        end
    end
    if not layout or layout == "" then layout = "us" end
    -- 3. User override: ~/.config/hypr-genshin/keyboard.conf
    local uf = io.open((os.getenv("HOME") or "") .. "/.config/hypr-genshin/keyboard.conf", "r")
    if uf then
        local utxt = uf:read("*a")
        uf:close()
        local ul = utxt:match("layout%s*=%s*([^\r\n]+)")
        local uv = utxt:match("variant%s*=%s*([^\r\n]+)")
        local uo = utxt:match("options%s*=%s*([^\r\n]+)")
        if ul then layout = ul end
        if uv then variant = uv end
        if uo then options = uo end
    end
    -- If user has multiple layouts (e.g. "us,ir" or "us,de") but no toggle shortcut set, add Alt+Shift
    if layout:find(",") and (not options or options == "") then
        options = "grp:alt_shift_toggle"
    end
    return layout, variant, options
end
local _kb_layout, _kb_variant, _kb_options = detect_user_kb()

local S = genshin

-- Keyboard (critical, kept alone in its own table)
S.config({
    input = {
        kb_layout = _kb_layout,
        kb_options = _kb_options,
    },
}, "input.kb")

-- HyDE defaults
S.config({ input = { accel_profile = "flat", numlock_by_default = true } }, "input.defaults")
S.config({
    input = {
        natural_scroll = true,
        touchpad = { natural_scroll = true, scroll_factor = 0.7 },
    },
}, "input.scroll")

S.config({
    decoration = {
        dim_special = 0.3,
        active_opacity = 0.90,
        inactive_opacity = 0.75,
        fullscreen_opacity = 1,
        blur = { special = true },
    },
}, "decoration")
S.config({ dwindle = { preserve_split = true } }, "dwindle")
S.config({ master = { new_status = "master" } }, "master")
S.config({
    misc = {
        vrr = 0,
        disable_hyprland_logo = true,
        disable_splash_rendering = true,
        force_default_wallpaper = 0,
        anr_missed_pings = 5,
        allow_session_lock_restore = true,
    },
}, "misc")
S.config({ xwayland = { force_zero_scaling = true } }, "xwayland")
S.config({ general = { snap = { enabled = true, respect_gaps = true } } }, "general.snap")
S.config({ general = { layout = "dwindle" } }, "general.layout")

-- Genshin gold for groups (HyDE took these from wallbash colours)
S.config({
    group = {
        col = {
            border_active = { colors = { "rgba(f4e8c1ff)", "rgba(d3bc8eff)" }, angle = 45 },
            border_inactive = { colors = { "rgba(3b4255cc)", "rgba(262b39cc)" }, angle = 45 },
        },
        groupbar = {
            enabled = true,
            gradients = 1,
            render_titles = 1,
            blur = true,
        },
    },
}, "group")

-- Same session shutdown handling as HyDE events.lua (uwsm session)
pcall(hl.on, "hyprland.shutdown", function()
    hl.dispatch(hl.dsp.exec_cmd("uwsm stop"))
    hl.dispatch(hl.dsp.exec_cmd("hyprshutdown"))
end)
