#!/usr/bin/env bash
# Live system -> repo (modules/). Re-run any time after you change something.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# hand-maintained modules that capture.sh does not know: keep them, don't wipe them
KEEP=(celestia-icons polkit)
KEEPDIR="$(mktemp -d)"
for k in "${KEEP[@]}"; do [ -d "$REPO/modules/$k" ] && mv "$REPO/modules/$k" "$KEEPDIR/$k"; done
# wipe only what capture regenerates (your screenshots in reference/ stay)
rm -rf "$REPO/modules" "$REPO/reference/system" "$REPO/reference/old-installers"
mkdir -p "$REPO/modules" "$REPO/reference/system" "$REPO/reference/old-installers"
for k in "${KEEP[@]}"; do [ -d "$KEEPDIR/$k" ] && mv "$KEEPDIR/$k" "$REPO/modules/$k"; done
rmdir "$KEEPDIR" 2>/dev/null || true
EXC=(--exclude='*.bak*' --exclude='__pycache__' --exclude='.git' --exclude='*~' --exclude='*.old' --exclude='*.old' --exclude='*.log' --exclude='cache' --exclude='.last-backup')

mod() {   # mod <name> <home|root> <path>...
  local name=$1 kind=$2; shift 2
  local base dst="$REPO/modules/$name/$kind" p have=()
  if [ "$kind" = home ]; then base="$HOME"; else base=/; fi
  for p in "$@"; do
    if [ -e "$base/$p" ] || [ -L "$base/$p" ]; then have+=("$p"); else echo "   skip (missing): $p"; fi
  done
  [ ${#have[@]} -gt 0 ] || return 0
  mkdir -p "$dst"
  tar -C "$base" "${EXC[@]}" -cf - "${have[@]}" 2>/dev/null | tar -C "$dst" --warning=no-timestamp -xf - 2>/dev/null
  echo "ok  $name ($kind): ${#have[@]} paths"
}

# files that earlier Genshin installers patched (they left .genshin.bak / .bak-genshin* next to them)
mapfile -t AUTO < <(cd "$HOME" && find .config/zsh .config/hypr .config/kitty .config/dunst .config/hyde .local/lib/hyde \
  -type f \( -name '*.genshin.bak' -o -name '*.bak-genshin*' \) 2>/dev/null \
  | sed -E 's/\.genshin\.bak$//; s/\.bak-genshin.*$//' | sort -u)

mod hypr         home .config/hypr-genshin
mod waybar       home .config/waybar-genshin .config/waybar/genshin-assets .config/autostart
mod rofi         home .config/rofi-genshin
mod power        home .config/power-genshin
mod osd          home .config/osd-genshin .themes/GenshinSwappy .config/swappy
mod audio        home .local/bin/irminsul-volume .local/bin/irminsul-settings .local/bin/pavucontrol
mod bluetooth    home .local/bin/teyvat-archive .local/share/genshin-bluetooth .local/share/applications/teyvat-archive.desktop
mod notif        home .config/dunst-genshin
mod lock         home .config/hyprlock-genshin
mod terminal     home .config/kitty-genshin .config/fastfetch-genshin .config/fastfetch/config.jsonc .local/bin/fastfetch .config/kitty/kitty.conf
mod fonts        home .local/share/fonts/genshin .config/fontconfig/conf.d/99-genshin-alias.conf
mod cursor       home .local/share/icons/Genshin-Official .local/share/icons/default/index.theme .icons/default/index.theme \
                      .config/uwsm/env .config/gtk-3.0/settings.ini .config/gtk-4.0/settings.ini .local/share/hyde/env-theme .local/share/hyde/theme-env .config/xsettingsd/xsettingsd.conf .gtkrc-2.0 .Xresources
mod wiring       home .config/hypr/hyprland.lua
mod login        root etc/sddm.conf.d/zz-genshin-theme.conf usr/share/sddm/themes/genshin-celestia usr/share/sddm/themes/Genshin
mod boot         root usr/share/plymouth/themes/genshin-loading usr/share/plymouth/themes/genshin \
                      usr/lib/initcpio/hooks/genshin-daynight usr/lib/initcpio/install/genshin-daynight \
                      usr/lib/genshin-daynight etc/genshin-daynight.conf etc/mkinitcpio.conf.d/genshin-kms.conf \
                      usr/lib/systemd/system/genshin-daynight-initrd.service \
                      etc/systemd/system/genshin-daynight.service \
                      etc/systemd/system/genshin-plymouth-finish.service \
                      etc/systemd/system/genshin-plymouth-failsafe.service \
                      etc/systemd/system/multi-user.target.wants/genshin-daynight.service \
                      etc/systemd/system/multi-user.target.wants/genshin-plymouth-finish.service \
                      etc/systemd/system/multi-user.target.wants/genshin-plymouth-failsafe.service

# teyvat-forecast (Quickshell weather popup). config.json is NOT captured on
# purpose: it holds the personal city, so a fresh install falls back to an IP
# lookup. Its refresh-timer helper is regenerated below (this script wipes
# modules/ on every run, so a hand-written modules/forecast/install.sh would vanish)
mod forecast     home .config/quickshell/teyvat-forecast .config/teyvat-forecast/teyvat-fetch.py \
                      .local/bin/teyvat-forecast \
                      .config/systemd/user/teyvat-forecast-fetch.service .config/systemd/user/teyvat-forecast-fetch.timer
if [ -d "$REPO/modules/forecast" ]; then
cat > "$REPO/modules/forecast/install.sh" <<'FCEOF'
#!/usr/bin/env bash
# forecast: the files are copied by the main install.sh; this only turns on the refresh timer.
command -v systemctl >/dev/null 2>&1 || { echo "   forecast: no systemctl, timer skipped"; exit 0; }
systemctl --user daemon-reload
systemctl --user enable --now teyvat-forecast-fetch.timer >/dev/null 2>&1 \
  && echo "   forecast: refresh timer enabled" \
  || echo "   forecast: could not enable the timer (no user session?)"
# first fetch so the popup has data right away
python3 "$HOME/.config/teyvat-forecast/teyvat-fetch.py" fetch >/dev/null 2>&1 || true
exit 0
FCEOF
fi

# make paths portable
grep -rIl "$HOME" "$REPO/modules" 2>/dev/null | xargs -r sed -i "s|$HOME|@HOME@|g"

# ── scrub: the live system keeps personal values, the repo must not ──
CAP_USER="$(id -un)"
sed -i "s/^GS_UTC_OFFSET=.*/GS_UTC_OFFSET=0/" "$REPO/modules/boot/root/etc/genshin-daynight.conf" 2>/dev/null || true
sed -i "s|: \"$CAP_USER\"|: \"\"|" "$REPO/modules/login/root/usr/share/sddm/themes/genshin-celestia/Main.qml" 2>/dev/null || true
for f in "$REPO"/modules/terminal/home/.config/fastfetch*/config.jsonc; do
  [ -f "$f" ] && sed -i "s|$CAP_USER|Traveler|g" "$f"
done
sed -i -E '/^[[:space:]]*kb_(layout|options)[[:space:]]*=/d' "$REPO/modules/hypr/home/.config/hypr-genshin/standalone.lua" 2>/dev/null || true
rm -f "$REPO/modules/hypr/home/.config/hypr-genshin/keyboard.conf" "$REPO/modules/hypr/home/.config/hypr-genshin/userprefs.conf"
if grep -rIl -F -e "$CAP_USER" "$REPO/modules" 2>/dev/null | grep -q .; then
  echo "⚠ اسم کاربری هنوز توی این فایل‌ها هست:"; grep -rIl -F -e "$CAP_USER" "$REPO/modules"
fi

# reference material (not installed)
echo "captured -> $REPO/modules"

# polkit autostart belongs to modules/polkit (the waybar capture also picks it up)
rm -f "$REPO/modules/waybar/home/.config/autostart/genshin-polkit.desktop"
