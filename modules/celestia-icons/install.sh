#!/usr/bin/env bash
# Celestia icon theme + Genshin file-chooser dialog + sidebar icons
# Usage: install.sh           install / update
#        install.sh --undo    remove everything this module installed
set -u
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICONS="$HOME/.local/share/icons/Celestia"
export CELESTIA_NO_PREVIEW=1

say(){ printf '\033[38;5;180m✦ %s\033[0m\n' "$*"; }

restart_portal(){
  pkill -f xdg-desktop-portal-gtk 2>/dev/null
  systemctl --user restart xdg-desktop-portal.service 2>/dev/null
}

set_gtk_icon_theme(){ # name
  local n="$1" f
  command -v gsettings >/dev/null 2>&1 && gsettings set org.gnome.desktop.interface icon-theme "$n" 2>/dev/null
  for f in "$HOME/.config/gtk-3.0/settings.ini" "$HOME/.config/gtk-4.0/settings.ini"; do
    mkdir -p "$(dirname "$f")"; touch "$f"
    grep -q '^\[Settings\]' "$f" || printf '[Settings]\n' >> "$f"
    if grep -q '^gtk-icon-theme-name=' "$f"; then
      sed -i "s|^gtk-icon-theme-name=.*|gtk-icon-theme-name=$n|" "$f"
    else
      sed -i "/^\[Settings\]/a gtk-icon-theme-name=$n" "$f"
    fi
  done
}

if [ "${1:-}" = "--undo" ]; then
  say "Undo Celestia"
  bash "$D/scripts/celestia-sidebar-icons.sh" --undo >/dev/null 2>&1
  for f in "$HOME/.config/gtk-3.0/gtk.css" "$HOME/.config/gtk-4.0/gtk.css"; do
    [ -f "$f" ] && sed -i '/CELESTIA-DIALOGS BEGIN/,/CELESTIA-DIALOGS END/d' "$f"
  done
  rm -rf "$ICONS"
  set_gtk_icon_theme "Papirus-Dark"
  restart_portal
  say "Done"
  exit 0
fi

for s in theme-installer icons-pack dialogs sidebar-icons; do
  say "celestia-$s"
  bash "$D/scripts/celestia-$s.sh" || printf '! celestia-%s failed\n' "$s"
done

set_gtk_icon_theme "Celestia"
restart_portal
say "Celestia installed ✦"
