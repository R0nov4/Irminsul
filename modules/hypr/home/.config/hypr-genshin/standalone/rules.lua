local S = genshin

local function rx(list)
    return "^(" .. table.concat(list, "|") .. ")$"
end

local function window_rule(spec)
    local ok, err = pcall(hl.window_rule, spec)
    if not ok then
        S.fail("window_rule " .. tostring(spec.name), err)
    end
end

local function layer_rule(spec)
    local ok, err = pcall(hl.layer_rule, spec)
    if not ok then
        S.fail("layer_rule " .. tostring(spec.name), err)
    end
end

local floating_class = rx({
    "Bitwarden",
    "genshin-theme-builder",
    "org.keepassxc.KeePassXC",
    "hyprland-share-picker",
    "blueman-manager",
    "pavucontrol-qt",
    "com\\.gabm\\.satty",
    "vlc",
    "kvantummanager",
    "qt6ct",
    "qt[56]ct",
    "nwg-(look|displays)",
    "org\\.kde\\.ark",
    "org\\.pulseaudio\\.pavucontrol",
    "nm-(applet|connection-editor)",
    "hyprpolkitagent",
    "console-dropdown",
    "org\\.kde\\.dolphin",
    ".*dialog.*",
    "[Xx]dg-desktop-portal-gtk",
    "org\\.freedesktop\\.impl\\.portal\\.desktop\\.(hyprland|gtk)",
})

local floating_title = rx({
    "Progress Dialog — Dolphin",
    "Copying — Dolphin",
    "Choose Files",
    "Save As",
    "Confirm to replace files",
    "File Operation Progress",
    "Open",
    "Authentication Required",
    "Add Folder to Workspace",
    "File Upload.*",
    "Choose wallpaper.*",
    "Library.*",
    ".*dialog.*",
    "Open File",
    "Volume Control",
    "Save As.*",
    "File Already Exists — Dolphin",
    "Properties for.*",
})

local pinned_title = rx({ "[Pp]icture[-\\s]?[Ii]n[-\\s]?[Pp]icture(.*)" })

local modal_class = rx({ "pinentry-.*" })
local modal_title = rx({
    "Choose Files",
    "Open File",
    "Save As.*",
    "File Operation Progress",
    "Authentication Required",
    "File Upload.*",
})
local modal_initial_title = rx({ "Open File", "Save As.*" })

window_rule({ name = "hyde_floating_class", tag = "+hyde_floating", match = { class = floating_class }, float = true })
window_rule({ name = "hyde_floating_title", tag = "+hyde_floating", match = { title = floating_title }, float = true })

window_rule({
    name = "hyde_pin",
    tag = "+hyde_pin",
    match = { title = pinned_title },
    float = true,
    move = "(monitor_w*0.73) (monitor_h*0.72)",
    size = "(monitor_w*0.25) (monitor_h*0.25)",
    pin = true,
    opacity = "1.0",
})

window_rule({
    name = "hyde_modals",
    tag = "+hyde_modals",
    match = { class = modal_class, title = modal_title, initial_title = modal_initial_title, modal = true },
    float = true,
    center = true,
    pin = true,
})

window_rule({
    name = "xwayland_video_bridge_fixes",
    match = { class = "xwaylandvideobridge" },
    no_initial_focus = true,
    no_focus = true,
    no_anim = true,
    no_blur = true,
    no_follow_mouse = true,
    max_size = { 1, 1 },
    opacity = 0.0,
    float = true,
    workspace = "special:xwayland_video_bridge silent",
})

window_rule({ name = "pypr_noanim", match = { tag = "pypr_noanim" }, no_anim = true })

window_rule({
    name = "filemanagers-fullscreen",
    match = { class = "^(.*dolphin.*)$|^(.*pcmanfm-qt.*)$|^(.*nemo.*)$|^(.*ark.*)$|.*Nautilus.*" },
    opaque = true,
    float = false,
})

-- Layer rules
local blur_layers = rx({ "rofi", "notifications", "swaync-(notification-window|control-center)", "waybar", "logout_dialog" })
local ignore_alpha_layers = rx({ "rofi", "notifications", "swaync-(notification-window|control-center)", "waybar", "selection" })

layer_rule({ name = "hyde_layer_blur", match = { namespace = blur_layers }, blur = true })
layer_rule({ name = "hyde_layer_ignore_alpha", match = { namespace = ignore_alpha_layers }, ignore_alpha = 0 })
layer_rule({ name = "hyde_layer_no_anim", no_anim = true, match = { namespace = "selection" } })

-- Irminsul apps: keep them floating so tiling never squeezes them below their minimum width
window_rule({ name = "irminsul_apps_float", match = { class = ".*[Ii]rminsul.*|.*[Tt]eyvat.*" }, float = true })
-- file dialogs: scale with the monitor instead of GTK's fixed default size
window_rule({ name = "irminsul_file_dialogs", match = { class = "xdg-desktop-portal-gtk" }, float = true, size = "(monitor_w*0.6) (monitor_h*0.7)" })
