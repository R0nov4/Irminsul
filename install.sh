#!/usr/bin/env bash
# Genshin desktop installer.
#   ./install.sh                                dry run: shows what would change
#   ./install.sh --deps                         install required Arch packages via pacman
#   ./install.sh --apply                        install user files (backups: ~/.genshin-backup/<time>)
#   ./install.sh --apply --system               also SDDM / Plymouth / initcpio / systemd files (sudo)
#   ./install.sh --apply --system --boot        also set Plymouth theme and rebuild initramfs
#   ./install.sh --deps --apply --system --boot full bare-metal installation on fresh Arch Linux
#   --only a,b                                  only these modules
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARGS=("$@")
APPLY=0; SYSTEM=0; BOOT=0; DEPS=0; UPDATE=0; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1;; --system) SYSTEM=1;; --boot) BOOT=1;; --deps) DEPS=1;;
    --update) UPDATE=1; APPLY=1;;
    --only) shift; ONLY="${1:-}";;
    *) echo "unknown option: $1"; exit 1;;
  esac; shift
done

# --update: git pull first, then re-run the (possibly new) script
if [ "$UPDATE" = 1 ] && [ -z "${GS_UPDATED:-}" ]; then
  if [ -d "$REPO/.git" ] && command -v git >/dev/null 2>&1; then
    echo "== Update: git pull =="
    git -C "$REPO" pull --ff-only || { echo "[ERROR] git pull failed (local changes?). Check: git -C $REPO status"; exit 1; }
  else
    echo "== Update: not a git checkout, skipping pull =="
  fi
  exec env GS_UPDATED=1 bash "${BASH_SOURCE[0]}" "${ARGS[@]}"
fi

# a module counts as installed if any of its files already exists at the destination
is_installed() {
  local d="$1" base f t
  for base in home root; do
    [ -d "$d/$base" ] || continue
    while IFS= read -r -d '' f; do
      f="${f#./}"
      if [ "$base" = home ]; then t="$HOME/$f"; else t="/$f"; fi
      if [ -e "$t" ] || [ -L "$t" ]; then return 0; fi
    done < <(cd "$d/$base" && find . \( -type f -o -type l \) -print0)
  done
  return 1
}

if [ "$DEPS" = 1 ]; then
  PKGS=(
    hyprland hyprlock hypridle hyprpicker xdg-desktop-portal-hyprland
    waybar rofi-wayland dunst libnotify kitty fastfetch starship zsh zsh-autosuggestions zsh-syntax-highlighting
    awww grim slurp swappy wl-clipboard cliphist
    tesseract tesseract-data-eng tesseract-data-fas zbar qrencode iproute2
    pipewire wireplumber pamixer playerctl brightnessctl
    polkit polkit-kde-agent network-manager-applet blueman udiskie
    sddm qt6-svg qt6-declarative qt6-5compat qt6-imageformats
    plymouth librsvg python-pillow python-gobject python-cairo gtk3 imagemagick jq curl xorg-xcursorgen
    ttf-jetbrains-mono-nerd noto-fonts gtk-layer-shell libpulse 
    pipewire-pulse python-numpy
    uwsm bluez bluez-utils power-profiles-daemon pipewire-audio
    adwaita-icon-theme
    breeze-icons
    papirus-icon-theme
    hyprsunset qt5ct qt6ct xdg-desktop-portal-gtk
  )
  echo "== Installing Arch Linux dependencies (${#PKGS[@]} packages) =="
  for try in 1 2 3; do
    sudo pacman -S --needed --noconfirm --disable-download-timeout "${PKGS[@]}" && break
    echo "[retry $try/3] pacman failed (network?), retrying..."; sleep 5
  done
  MISSING=$(pacman -T "${PKGS[@]}")
  if [ -n "$MISSING" ]; then
    echo "[ERROR] these packages are still missing:"; echo "$MISSING"; exit 1
  fi
  [ "$APPLY" = 0 ] && exit 0
fi

TS=$(date +%Y%m%d-%H%M%S)
new=0; changed=0; same=0
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT

render() { if grep -qI '@HOME@' "$1"; then sed "s|@HOME@|$HOME|g" "$1" > "$2"; else cp -p "$1" "$2"; fi; }
backup() {   # file, sudo-prefix, backup-root
  { [ -e "$1" ] || [ -L "$1" ]; } || return 0
  local rel="${1#/}"; $2 mkdir -p "$3/$(dirname "$rel")"; $2 cp -a "$1" "$3/$rel"
}
install_tree() {   # src dst sudo-prefix backup-root
  local src="$1" dst="$2" S="$3" BK="$4" f t tgt mode
  while IFS= read -r -d '' f; do
    f="${f#./}"; t="$dst/$f"
    if [ -L "$src/$f" ]; then
      tgt=$(readlink "$src/$f")
      if [ "$(readlink "$t" 2>/dev/null)" = "$tgt" ]; then same=$((same+1)); continue; fi
      echo "LINK   $t -> $tgt"; changed=$((changed+1))
      if [ "$APPLY" = 1 ]; then $S mkdir -p "$(dirname "$t")"; backup "$t" "$S" "$BK"; $S ln -sfn "$tgt" "$t"; fi
      continue
    fi
    render "$src/$f" "$TMP"
    if [ -e "$t" ] && cmp -s "$TMP" "$t"; then same=$((same+1)); continue; fi
    if [ -e "$t" ]; then echo "UPDATE $t"; changed=$((changed+1)); else echo "NEW    $t"; new=$((new+1)); fi
    if [ "$APPLY" = 1 ]; then
      backup "$t" "$S" "$BK"
      mode=$(stat -c %a "$src/$f")
      $S install -D -m "$mode" "$TMP" "$t"
    fi
  done < <(cd "$src" && find . \( -type f -o -type l \) -print0)
}

[ "$APPLY" = 0 ] && echo "DRY RUN: nothing will change. Use --apply to install (or --deps to install packages)."
for d in "$REPO"/modules/*/; do
  m=$(basename "$d")
  if [ -n "$ONLY" ] && [[ ",$ONLY," != *",$m,"* ]]; then continue; fi
  if [ "$UPDATE" = 1 ] && [ -z "$ONLY" ] && ! is_installed "$d"; then echo "-- $m (not installed, skipped)"; continue; fi
  echo "-- $m"
  [ -d "$d/home" ] && install_tree "$d/home" "$HOME" "" "$HOME/.genshin-backup/$TS"
  if [ -d "$d/root" ]; then
    if [ "$SYSTEM" = 1 ]; then install_tree "$d/root" "" sudo "/var/backups/genshin/$TS"
    else echo "   (system files skipped; use --system)"; fi
  fi
done
# modules with their own install.sh (celestia-icons) run last, so nothing from
# modules/*/home overwrites the settings they write
if [ "$APPLY" = 1 ]; then
  for d in "$REPO"/modules/*/; do
    m=$(basename "$d")
    if [ -n "$ONLY" ] && [[ ",$ONLY," != *",$m,"* ]]; then continue; fi
    if [ "$UPDATE" = 1 ] && [ -z "$ONLY" ] && ! is_installed "$d"; then continue; fi
    if [ -f "$d/install.sh" ]; then
      echo "-- $m: module installer"
      bash "$d/install.sh" || echo "!  $m installer failed"
    fi
  done
  # shell: install the standalone zsh config (only if the user has no zsh setup of their own,
  # so HyDE / custom setups are never touched), then make zsh the login shell
  if [ "$UPDATE" = 0 ] && { [ -z "$ONLY" ] || [[ ",$ONLY," == *",terminal,"* ]]; }; then
    if [ ! -r /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ] && command -v pacman >/dev/null 2>&1; then
      sudo pacman -S --needed --noconfirm zsh zsh-autosuggestions zsh-syntax-highlighting starship
    fi
  ZS="$REPO/shell/zshrc"
  if [ -f "$ZS" ]; then
    if [ ! -e "$HOME/.zshrc" ] && [ ! -e "$HOME/.zshenv" ]; then
      cp "$ZS" "$HOME/.zshrc" && echo "SHELL: installed ~/.zshrc (Traveler card in kitty)"
    else
      echo "SHELL: ~/.zshrc or ~/.zshenv already exists, left untouched"
    fi
  fi
  if command -v zsh >/dev/null 2>&1 && [ "$(getent passwd "$USER" | cut -d: -f7)" != "$(command -v zsh)" ]; then
    sudo chsh -s "$(command -v zsh)" "$USER" && echo "SHELL: login shell is now zsh (applies to new logins)" || echo "!  chsh failed"
  fi
  fi
fi

[ "$APPLY" = 1 ] && command -v fc-cache >/dev/null 2>&1 && fc-cache -f >/dev/null 2>&1
[ "$APPLY" = 1 ] && command -v gsettings >/dev/null 2>&1 && gsettings set org.gnome.desktop.interface cursor-theme "Genshin-Official" 2>/dev/null || true
[ "$APPLY" = 1 ] && [ "$SYSTEM" = 1 ] && sudo systemctl daemon-reload >/dev/null 2>&1 || true

# swww was renamed to awww; keep the old command names working for the theme scripts
if [ "$APPLY" = 1 ]; then
  for pair in swww:awww swww-daemon:awww-daemon; do
    old="${pair%%:*}"; new="${pair##*:}"
    if ! command -v "$old" >/dev/null 2>&1 && command -v "$new" >/dev/null 2>&1; then
      if [ "$SYSTEM" = 1 ]; then
        sudo ln -sf "$(command -v "$new")" "/usr/local/bin/$old" && echo "SHIM: /usr/local/bin/$old -> $(command -v "$new")"
      else
        mkdir -p "$HOME/.local/bin"
        ln -sf "$(command -v "$new")" "$HOME/.local/bin/$old" && echo "SHIM: ~/.local/bin/$old -> $(command -v "$new")"
      fi
    fi
  done
fi

if [ "$BOOT" = 1 ] && [ "$APPLY" = 1 ]; then
  echo "== Boot: Plymouth + initramfs =="
  MKCONF=/etc/mkinitcpio.conf
  GRUBCFG=/etc/default/grub
  GRUB10=/etc/grub.d/10_linux
  NEED_GRUB=0

  have_hook() { [ -n "$(grep -rEhs '^HOOKS.*genshin-daynight' "$MKCONF" /etc/mkinitcpio.conf.d 2>/dev/null)" ]; }

  if [ ! -f /usr/lib/initcpio/install/genshin-daynight ]; then
    echo "[ERROR] boot hook files are not installed; run with --system too."; exit 1
  fi
  command -v plymouth-set-default-theme >/dev/null 2>&1 || { echo "[ERROR] plymouth is not installed; run --deps first."; exit 1; }

  # 1) HOOKS: genshin-daynight + plymouth right after udev
  if ! have_hook; then
    if grep -qE '^HOOKS=.*\bsystemd\b' "$MKCONF"; then
      echo "BOOT: systemd-based HOOKS found; add 'genshin-daynight plymouth' by hand."
    else
      sudo cp -a "$MKCONF" "$MKCONF.genshin-bak-$TS"
      if grep -qE '^HOOKS=.*\bplymouth\b' "$MKCONF"; then
        sudo sed -i -E '/^HOOKS=/ s/\bplymouth\b/genshin-daynight plymouth/' "$MKCONF"
      else
        sudo sed -i -E '/^HOOKS=/ s/\budev\b/udev genshin-daynight plymouth/' "$MKCONF"
      fi
      echo "BOOT: HOOKS updated (backup: $MKCONF.genshin-bak-$TS)"
    fi
  fi

  # 2) kernel cmdline in /etc/default/grub (match laptop's exact silent flags)
  if [ -f "$GRUBCFG" ]; then
    for flag in plymouth.ignore-serial-consoles rd.udev.log_level=3 loglevel=3 quiet splash vt.global_cursor_default=0; do
      if ! grep -qE "^GRUB_CMDLINE_LINUX_DEFAULT=.*${flag}" "$GRUBCFG"; then
        [ "$NEED_GRUB" = 0 ] && sudo cp -a "$GRUBCFG" "$GRUBCFG.genshin-bak-$TS"
        sudo sed -i -E "/^GRUB_CMDLINE_LINUX_DEFAULT=/ s/\"$/ ${flag}\"/" "$GRUBCFG"
        NEED_GRUB=1
      fi
    done
  fi

  # 3) Remove 'Loading Linux...' and 'Loading initial ramdisk...' echo lines in /etc/grub.d/10_linux
  if [ -f "$GRUB10" ] && grep -q 'echo.*\$message.*grub_quote' "$GRUB10"; then
    sudo cp -a "$GRUB10" "$GRUB10.genshin-bak-$TS"
    sudo sed -i '/echo.*\$message.*grub_quote/d' "$GRUB10"
    NEED_GRUB=1
    echo "BOOT: silenced Loading Linux / ramdisk echo in $GRUB10"
  fi

  if [ "$NEED_GRUB" = 1 ] && [ -f "$GRUBCFG" ]; then
    sudo grub-mkconfig -o /boot/grub/grub.cfg
  fi

  # 4) theme + initramfs
  if have_hook; then
    [ "$(plymouth-set-default-theme 2>/dev/null)" = genshin-loading ] || sudo plymouth-set-default-theme genshin-loading
    sudo mkinitcpio -P
  else
    echo "BOOT: genshin-daynight is not in HOOKS; skipping initramfs rebuild."
  fi
fi

echo; echo "new=$new  changed=$changed  unchanged=$same"
[ "$APPLY" = 1 ] && echo "backups of replaced files: ~/.genshin-backup/$TS"
if [ "$UPDATE" = 1 ]; then
  echo "(modules that are not installed were skipped; force one with: ./install.sh --update --only NAME)"
  [ -f "$REPO/doctor.sh" ] && bash "$REPO/doctor.sh"
fi
exit 0
