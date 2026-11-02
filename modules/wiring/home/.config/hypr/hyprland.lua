-- Genshin standalone core (no HyDE Lua layer).
-- Restore the previous config with: genshin-hypr-standalone.sh deactivate
dofile(os.getenv("HOME") .. "/.config/hypr-genshin/standalone/init.lua")

-- Irminsul sound console
pcall(dofile, os.getenv("HOME") .. "/.config/hypr-genshin/audio.lua")
