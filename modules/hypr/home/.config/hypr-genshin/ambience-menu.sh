#!/usr/bin/env bash
# Genshin Impact - Ambience, Wallpaper Color Sync & Mode Selector (Super + Shift + R)
set -u

ROFI_THEME="$HOME/.config/rofi-genshin/shot-menu.rasi"

if pgrep -x rofi >/dev/null 2>&1; then
    pkill -x rofi
    exit 0
fi

choice=$(printf '%s\n' \
    "✦  Sync Border Accent with Current Wallpaper (Auto-Resonance)" \
    "❖  Glass Mode: Crystal Clear (Opacity 92% + Deep Blur)" \
    "❖  Glass Mode: Solid Teyvat Slate (Opaque 100%)" \
    "☀️  Eye Comfort: Warm Dusk Filter (Hyprsunset 4500K)" \
    "🌙  Eye Comfort: Pure Starlight (Disable Night Filter)" \
    "🔄  Reload Teyvat HUD (Waybar + Dunst + Hyprland)" \
  | rofi -dmenu -i -no-custom -p "✦ Ambience" \
        -mesg "<span foreground='#d3bc8e'>✦ Teyvat Ambience:</span> Visual mode &amp; shader controls" \
        -theme "$ROFI_THEME" \
        -theme-str 'previewcard { enabled: false; } imagebox { enabled: false; } inputbar { enabled: false; } listview { lines: 6; }')

[ -z "$choice" ] && exit 0

case "$choice" in
    *"Sync Border"*)
        # Extract dominant vibrant color from current wallpaper using Python PIL
        read -r C1 C2 HEX < <(python3 - << 'PY'
import os, glob
from PIL import Image

candidates = [os.path.expanduser("~/.config/rofi-genshin/art.png")]
candidates += sorted(glob.glob(os.path.expanduser("~/.config/wallpaper-genshin/*.*")))
img_path = next((p for p in candidates if os.path.isfile(p)), None)

if not img_path:
    print("f4e8c1ff d3bc8eff #d3bc8e")
    raise SystemExit

im = Image.open(img_path).convert("RGB").resize((64, 64))
best = (211, 188, 142)
best_score = -1
for r, g, b in im.getdata():
    mx, mn = max(r, g, b), min(r, g, b)
    sat = (mx - mn) / (mx + 1)
    val = mx / 255.0
    score = sat * val
    if 0.25 < val < 0.95 and score > best_score:
        best_score = score
        best = (r, g, b)

r, g, b = best
r2, g2, b2 = min(255, int(r*1.25)), min(255, int(g*1.25)), min(255, int(b*1.25))
print(f"{r2:02x}{g2:02x}{b2:02x}ff {r:02x}{g:02x}{b:02x}ff #{r:02x}{g:02x}{b:02x}")
PY
)
        hyprctl keyword general:col.active_border "rgba($C1) rgba($C2) rgba(f4e8c1aa) rgba($C1) 45deg" >/dev/null 2>&1
        notify-send -a "Paimon" "✦ Auto-Resonance" "Synced aura with wallpaper ($HEX)"
        ;;
    *"Crystal Clear"*)
        hyprctl keyword decoration:active_opacity 0.92 >/dev/null 2>&1
        hyprctl keyword decoration:inactive_opacity 0.78 >/dev/null 2>&1
        hyprctl keyword decoration:blur:enabled true >/dev/null 2>&1
        notify-send -a "Paimon" "✦ Crystal Clear" "Translucent glass & blur enabled"
        ;;
    *"Solid Teyvat"*)
        hyprctl keyword decoration:active_opacity 1.0 >/dev/null 2>&1
        hyprctl keyword decoration:inactive_opacity 0.96 >/dev/null 2>&1
        notify-send -a "Paimon" "✦ Solid Slate" "Full window opacity enabled"
        ;;
    *"Warm Dusk"*)
        pkill -x hyprsunset 2>/dev/null || true
        if command -v hyprsunset >/dev/null 2>&1; then
            setsid hyprsunset -t 4500 >/dev/null 2>&1 &
            notify-send -a "Paimon" "☀️ Warm Dusk" "Night light set to 4500K"
        else
            notify-send -a "Paimon" "Hyprsunset" "hyprsunset is not installed"
        fi
        ;;
    *"Pure Starlight"*)
        pkill -x hyprsunset 2>/dev/null || true
        notify-send -a "Paimon" "🌙 Pure Starlight" "Night filter disabled"
        ;;
    *"Reload Teyvat HUD"*)
        "$HOME/.config/waybar-genshin/start.sh" restart >/dev/null 2>&1 &
        "$HOME/.config/dunst-genshin/start.sh" >/dev/null 2>&1 &
        hyprctl reload >/dev/null 2>&1
        notify-send -a "Paimon" "🔄 HUD Reloaded" "Waybar, Dunst & Hyprland refreshed"
        ;;
esac
