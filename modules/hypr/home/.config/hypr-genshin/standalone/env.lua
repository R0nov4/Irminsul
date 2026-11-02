local S = genshin

local function env(name, value)
    local ok, err = pcall(hl.env, name, value)
    if not ok then
        S.fail("env " .. name, err)
    end
end

env("XDG_CURRENT_DESKTOP", "Hyprland")
env("XDG_SESSION_TYPE", "wayland")
env("XDG_SESSION_DESKTOP", "Hyprland")
env("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
env("QT_QPA_PLATFORM", "wayland;xcb")
env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
env("QT_QPA_PLATFORMTHEME", "qt6ct")
env("MOZ_ENABLE_WAYLAND", "1")
env("GDK_SCALE", "1")
env("ELECTRON_OZONE_PLATFORM_HINT", "auto")

local function xdg(name, fallback)
    local v = os.getenv(name)
    if v == nil or v == "" then
        v = S.home .. fallback
    end
    env(name, v)
end
xdg("XDG_CONFIG_HOME", "/.config")
xdg("XDG_CACHE_HOME", "/.cache")
xdg("XDG_DATA_HOME", "/.local/share")
xdg("XDG_STATE_HOME", "/.local/state")

-- hyde-shell and the HyDE scripts must be on PATH (no duplicates on reload)
local path = os.getenv("PATH") or ""
local have = {}
for seg in (path .. ":"):gmatch("([^:]*):") do
    have[seg] = true
end
for _, extra in ipairs({ S.home .. "/.local/bin", S.home .. "/.local/lib", S.home .. "/.local/lib/hyde" }) do
    if not have[extra] then
        path = (path == "") and extra or (path .. ":" .. extra)
        have[extra] = true
    end
end
env("PATH", path)

-- NVIDIA probe (reads two files only, same as HyDE)
local function has_nvidia_working()
    local version = io.open("/proc/driver/nvidia/version", "r")
    if not version then
        return false
    end
    version:close()
    local initstate = io.open("/sys/module/nvidia/initstate", "r")
    if not initstate then
        return true
    end
    local state = initstate:read("*l")
    initstate:close()
    return state == "live"
end
if has_nvidia_working() then
    env("LIBVA_DRIVER_NAME", "nvidia")
    env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    env("GBM_BACKEND", "nvidia-drm")
end

-- Genshin Official Cursor (locked)
env("XCURSOR_THEME", "Genshin-Official")
env("XCURSOR_SIZE", "32")
env("HYPRCURSOR_THEME", "Genshin-Official")
env("HYPRCURSOR_SIZE", "32")
