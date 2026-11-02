-- Irminsul sound console (written by genshin-audio-installer.sh)
local bin = os.getenv("HOME") .. "/.local/bin/"

hl.bind("SUPER + ALT + A", hl.dsp.exec_cmd(bin .. "irminsul-volume"))            -- popup (press again to close)
hl.bind("SUPER + ALT + SHIFT + A", hl.dsp.exec_cmd(bin .. "irminsul-settings"))      -- full settings window

-- bring back EQ / Mono / Co-op / Clear Voice after login
hl.on("hyprland.start", function()
  hl.exec_cmd("sh -c 'sleep 4; " .. bin .. "irminsul-settings --restore'")
end)
