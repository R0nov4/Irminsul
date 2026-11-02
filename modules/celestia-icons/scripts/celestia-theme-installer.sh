#!/usr/bin/env bash
# ============================================================
#  Celestia — Genshin-style global theme
#  GTK3 + GTK4/libadwaita + Qt5/Qt6 (qt5ct/qt6ct, KDE colors) + Icon theme
#  Usage:  bash celestia-theme-installer.sh
#          bash celestia-theme-installer.sh --uninstall
# ============================================================

NAME="Celestia"
THEMES="$HOME/.local/share/themes/$NAME"
ICONS="$HOME/.local/share/icons/$NAME"
BK="$HOME/.config/celestia-backup-$(date +%Y%m%d-%H%M%S)"

say(){ printf '\033[38;5;180m✦ %s\033[0m\n' "$*"; }
warn(){ printf '\033[38;5;203m! %s\033[0m\n' "$*"; }

if [ "$1" = "--uninstall" ]; then
  rm -rf "$THEMES" "$ICONS" \
         "$HOME/.local/share/color-schemes/$NAME.colors" \
         "$HOME/.config/qt5ct/colors/$NAME.conf" \
         "$HOME/.config/qt6ct/colors/$NAME.conf" \
         "$HOME/.config/environment.d/90-celestia.conf"
  say "Removed. Settings files (gtk-3.0/gtk-4.0/qt5ct/qt6ct) are untouched; backups are in ~/.config/celestia-backup-*"
  exit 0
fi

mkdir -p "$BK"
bk(){ [ -e "$1" ] && cp -a "$1" "$BK/$(echo "$1" | tr '/' '_')"; }

# ---------- 0. dependencies ----------
need=()
for p in qt5ct qt6ct papirus-icon-theme; do
  pacman -Qq "$p" >/dev/null 2>&1 || need+=("$p")
done
if [ ${#need[@]} -gt 0 ]; then
  say "Installing: ${need[*]}"
  sudo pacman -S --needed "${need[@]}" || warn "pacman failed — continuing anyway (icons will fall back to Adwaita)"
fi

# ============================================================
# 1. GTK theme  (palette: navy #272c3b / parchment #ece5d8 / gold #d3bc8e)
# ============================================================
say "GTK3 / GTK4 theme"
mkdir -p "$THEMES/gtk-3.0" "$THEMES/gtk-4.0"

cat > "$THEMES/index.theme" <<'EOF'
[Desktop Entry]
Type=X-GNOME-Metatheme
Name=Celestia
Comment=Genshin Celestia theme
Encoding=UTF-8

[X-GNOME-Metatheme]
GtkTheme=Celestia
IconTheme=Celestia
EOF

colors(){ cat <<'EOF'
@define-color theme_bg_color #272c3b;
@define-color theme_fg_color #ece5d8;
@define-color theme_base_color #1e2230;
@define-color theme_text_color #ece5d8;
@define-color theme_selected_bg_color #d3bc8e;
@define-color theme_selected_fg_color #272c3b;
@define-color theme_unfocused_bg_color #272c3b;
@define-color theme_unfocused_fg_color #b9b4aa;
@define-color theme_unfocused_base_color #1e2230;
@define-color theme_unfocused_text_color #ece5d8;
@define-color theme_unfocused_selected_bg_color #b8a47a;
@define-color theme_unfocused_selected_fg_color #272c3b;
@define-color insensitive_bg_color #2b3042;
@define-color insensitive_fg_color #6f7488;
@define-color insensitive_base_color #222735;
@define-color unfocused_insensitive_color #6f7488;
@define-color borders #4a5270;
@define-color unfocused_borders #3a4158;
@define-color warning_color #e8aa5a;
@define-color error_color #e06c6c;
@define-color success_color #82c896;
@define-color tooltip_bg_color #ece5d8;
@define-color tooltip_fg_color #3b4255;
@define-color content_view_bg #1e2230;
@define-color text_view_bg #1e2230;
@define-color wm_title #ece5d8;
@define-color wm_unfocused_title #8a8fa3;
@define-color wm_bg #272c3b;
@define-color wm_unfocused_bg #1e2230;
@define-color link_color #e9d9a8;
@define-color visited_link_color #b8a47a;
@define-color accent_color #d3bc8e;
@define-color accent_bg_color #d3bc8e;
@define-color accent_fg_color #272c3b;
@define-color destructive_color #e06c6c;
@define-color destructive_bg_color #c05050;
@define-color destructive_fg_color #ffffff;
@define-color success_bg_color #5fa578;
@define-color success_fg_color #ffffff;
@define-color warning_bg_color #e8aa5a;
@define-color warning_fg_color #272c3b;
@define-color error_bg_color #c05050;
@define-color error_fg_color #ffffff;
@define-color window_bg_color #272c3b;
@define-color window_fg_color #ece5d8;
@define-color view_bg_color #1e2230;
@define-color view_fg_color #ece5d8;
@define-color headerbar_bg_color #2f3547;
@define-color headerbar_fg_color #ece5d8;
@define-color headerbar_border_color #d3bc8e;
@define-color headerbar_backdrop_color #272c3b;
@define-color headerbar_shade_color rgba(0,0,0,0.30);
@define-color card_bg_color #323849;
@define-color card_fg_color #ece5d8;
@define-color card_shade_color rgba(0,0,0,0.30);
@define-color dialog_bg_color #2b3042;
@define-color dialog_fg_color #ece5d8;
@define-color popover_bg_color #2b3042;
@define-color popover_fg_color #ece5d8;
@define-color sidebar_bg_color #232838;
@define-color sidebar_fg_color #ece5d8;
@define-color sidebar_backdrop_color #202433;
@define-color sidebar_shade_color rgba(0,0,0,0.25);
@define-color secondary_sidebar_bg_color #202433;
@define-color secondary_sidebar_fg_color #ece5d8;
@define-color secondary_sidebar_backdrop_color #1e2230;
@define-color secondary_sidebar_shade_color rgba(0,0,0,0.25);
@define-color thumbnail_bg_color #323849;
@define-color thumbnail_fg_color #ece5d8;
@define-color shade_color rgba(0,0,0,0.30);
@define-color scrollbar_outline_color rgba(0,0,0,0.5);
EOF
}

polish(){ cat <<'EOF'

/* ---- Celestia polish ---- */
headerbar, .titlebar {
  background-image: linear-gradient(to bottom, #353b50, #2a2f40);
  border-bottom: 1px solid alpha(#d3bc8e, 0.45);
  color: #ece5d8;
}
button {
  border-radius: 7px;
  border: 1px solid alpha(#d3bc8e, 0.22);
  background-image: linear-gradient(to bottom, #3a4158, #30364a);
  color: #ece5d8;
}
button:hover { border-color: #d3bc8e; background-image: linear-gradient(to bottom, #444c66, #373e55); }
button:active, button:checked { background-image: none; background-color: #d3bc8e; color: #272c3b; }
button.suggested-action {
  background-image: linear-gradient(to bottom, #e6d4a4, #c9ac74);
  color: #272c3b; border-color: #a88c58;
}
button.destructive-action { border-color: #8a3a3a; }
entry, spinbutton, textview text {
  border-radius: 7px;
  border: 1px solid #4a5270;
  background-color: #1e2230;
  color: #ece5d8;
}
entry:focus, spinbutton:focus { border-color: #d3bc8e; box-shadow: 0 0 0 1px alpha(#d3bc8e, 0.5); }
scrollbar slider { background-color: #4a5270; border-radius: 8px; min-width: 6px; min-height: 6px; }
scrollbar slider:hover { background-color: #d3bc8e; }
tooltip, tooltip.background { background-color: #ece5d8; color: #3b4255; border-radius: 8px; border: 1px solid #d3bc8e; }
popover > contents, menu, .menu { border: 1px solid alpha(#d3bc8e, 0.45); border-radius: 10px; }
menuitem:hover, row:hover { background-color: alpha(#d3bc8e, 0.18); }
row:selected, treeview:selected, iconview:selected, .view:selected, selection {
  background-color: #d3bc8e; color: #272c3b;
}
switch:checked { background-color: #d3bc8e; }
switch:checked slider { background-color: #272c3b; }
progressbar progress, scale highlight, scale fill { background-color: #d3bc8e; }
notebook > header > tabs > tab:checked { border-color: #d3bc8e; box-shadow: inset 0 -2px #d3bc8e; }
EOF
}

gtk4vars(){ cat <<'EOF'

:root {
  --accent-color: #d3bc8e;
  --accent-bg-color: #d3bc8e;
  --accent-fg-color: #272c3b;
  --window-bg-color: #272c3b;
  --window-fg-color: #ece5d8;
  --view-bg-color: #1e2230;
  --view-fg-color: #ece5d8;
  --headerbar-bg-color: #2f3547;
  --headerbar-fg-color: #ece5d8;
  --headerbar-border-color: #d3bc8e;
  --headerbar-backdrop-color: #272c3b;
  --card-bg-color: #323849;
  --card-fg-color: #ece5d8;
  --dialog-bg-color: #2b3042;
  --dialog-fg-color: #ece5d8;
  --popover-bg-color: #2b3042;
  --popover-fg-color: #ece5d8;
  --sidebar-bg-color: #232838;
  --sidebar-fg-color: #ece5d8;
  --sidebar-backdrop-color: #202433;
  --secondary-sidebar-bg-color: #202433;
  --secondary-sidebar-fg-color: #ece5d8;
}
EOF
}

# GTK3: built-in Adwaita (dark) + our colors on top
{
  echo '@import url("resource:///org/gtk/libgtk/theme/Adwaita/gtk-contained-dark.css");'
  colors; polish
} > "$THEMES/gtk-3.0/gtk.css"
cp "$THEMES/gtk-3.0/gtk.css" "$THEMES/gtk-3.0/gtk-dark.css"

# GTK4 theme: built-in Default (dark) + our colors on top
{
  echo '@import url("resource:///org/gtk/libgtk/theme/Default/Default-dark.css");'
  colors; gtk4vars; polish
} > "$THEMES/gtk-4.0/gtk.css"
cp "$THEMES/gtk-4.0/gtk.css" "$THEMES/gtk-4.0/gtk-dark.css"

# libadwaita apps ignore the theme folder → user gtk.css (no import needed)
mkdir -p "$HOME/.config/gtk-4.0" "$HOME/.config/gtk-3.0"
bk "$HOME/.config/gtk-4.0/gtk.css"
{ colors; gtk4vars; polish; } > "$HOME/.config/gtk-4.0/gtk.css"

# settings.ini (keeps your other keys: fonts, cursor ...)
setini(){
  local f="$1" k="$2" v="$3"
  mkdir -p "$(dirname "$f")"
  [ -f "$f" ] || printf '[Settings]\n' > "$f"
  grep -q '^\[Settings\]' "$f" || sed -i '1i [Settings]' "$f"
  if grep -q "^$k=" "$f"; then sed -i "s|^$k=.*|$k=$v|" "$f"
  else sed -i "/^\[Settings\]/a $k=$v" "$f"; fi
}
for d in gtk-3.0 gtk-4.0; do
  f="$HOME/.config/$d/settings.ini"; bk "$f"
  setini "$f" gtk-theme-name "$NAME"
  setini "$f" gtk-icon-theme-name "$NAME"
  setini "$f" gtk-application-prefer-dark-theme 1
done

if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.gnome.desktop.interface gtk-theme "$NAME"
  gsettings set org.gnome.desktop.interface icon-theme "$NAME"
  gsettings set org.gnome.desktop.interface color-scheme prefer-dark
fi

# ============================================================
# 2. Icon theme (gold-trimmed navy folders + Celestia star, inherits Papirus)
# ============================================================
say "Icon theme"
rm -rf "$ICONS"
P="$ICONS/scalable/places"; M="$ICONS/scalable/mimetypes"
mkdir -p "$P" "$M"

cat > "$ICONS/index.theme" <<'EOF'
[Icon Theme]
Name=Celestia
Comment=Genshin Celestia icon theme (inherits Papirus for all other icons)
Inherits=Papirus-Dark,Papirus,breeze-dark,Adwaita,hicolor
Directories=scalable/places,scalable/mimetypes

[scalable/places]
Size=64
MinSize=16
MaxSize=512
Type=Scalable
Context=Places

[scalable/mimetypes]
Size=64
MinSize=16
MaxSize=512
Type=Scalable
Context=MimeTypes
EOF

folder_svg(){ cat <<EOF
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<defs>
<linearGradient id="b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a4158"/><stop offset="1" stop-color="#232838"/></linearGradient>
<linearGradient id="f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4f5878"/><stop offset="1" stop-color="#343a52"/></linearGradient>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ecdcae"/><stop offset="1" stop-color="#c3a56b"/></linearGradient>
</defs>
<path d="M6 14a4 4 0 0 1 4-4h14l5 5h25a4 4 0 0 1 4 4v33a4 4 0 0 1-4 4H10a4 4 0 0 1-4-4z" fill="url(#b)" stroke="#d3bc8e" stroke-width="1.2"/>
<path d="M6 25a3 3 0 0 1 3-3h46a3 3 0 0 1 3 3v26a4 4 0 0 1-4 4H10a4 4 0 0 1-4-4z" fill="url(#f)" stroke="#d3bc8e" stroke-width="1.2"/>
<path d="M9 22.6h46" stroke="#ecdcae" stroke-opacity=".7" stroke-width="1"/>
<g transform="translate(32 40)" fill="url(#g)">$1</g>
</svg>
EOF
}

trash_svg(){ cat <<EOF
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<defs>
<linearGradient id="f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4f5878"/><stop offset="1" stop-color="#2f354a"/></linearGradient>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ecdcae"/><stop offset="1" stop-color="#c3a56b"/></linearGradient>
</defs>
$1
<path d="M26 11V8a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v3" fill="none" stroke="#d3bc8e" stroke-width="2"/>
<path d="M16 18h32l-3 38a3 3 0 0 1-3 3H22a3 3 0 0 1-3-3z" fill="url(#f)" stroke="#d3bc8e" stroke-width="1.3"/>
<rect x="11" y="11" width="42" height="7" rx="2.5" fill="url(#g)"/>
<path d="M27 25v26M32 25v26M37 25v26" stroke="#d3bc8e" stroke-width="2" stroke-linecap="round"/>
</svg>
EOF
}

G_STAR='<path d="M0 -9L2.4 -2.4L9 0L2.4 2.4L0 9L-2.4 2.4L-9 0L-2.4 -2.4Z"/>'
G_DOC='<path fill-rule="evenodd" d="M-6 -8H2L6 -4V8H-6ZM-3 -1H3V0.5H-3ZM-3 3H3V4.5H-3Z"/>'
G_DL='<path d="M-2.5 -8H2.5V-1H6.5L0 6L-6.5 -1H-2.5Z"/><rect x="-7" y="7" width="14" height="2" rx="1"/>'
G_MUS='<circle cx="-3" cy="5" r="3"/><circle cx="5" cy="3" r="3"/><path d="M-1 5V-7L7 -9V3H5V-5L1 -4V5Z"/>'
G_PIC='<path d="M-9 7L-3 -1L1 4L4 0L9 7Z"/><circle cx="4" cy="-5" r="2.2"/>'
G_VID='<path d="M-4 -7L8 0L-4 7Z"/>'
G_HOME='<path d="M0 -9L9 -1H6V8H-6V-1H-9Z"/>'
G_DESK='<path fill-rule="evenodd" d="M-9 -8H9V4H-9ZM-7 -6V2H7V-6Z"/><path d="M-3 6H3V8H-3Z"/>'

mkf(){ folder_svg "$2" > "$P/$1.svg"; }
mkf folder             "$G_STAR"
mkf folder-open        "$G_STAR"
mkf folder-documents   "$G_DOC"
mkf folder-download    "$G_DL"
mkf folder-music       "$G_MUS"
mkf folder-pictures    "$G_PIC"
mkf folder-videos      "$G_VID"
mkf folder-publicshare "$G_STAR"
mkf folder-templates   "$G_STAR"
mkf folder-remote      "$G_STAR"
mkf folder-home        "$G_HOME"
mkf user-home          "$G_HOME"
mkf user-desktop       "$G_DESK"
mkf folder-desktop     "$G_DESK"
cp "$P/folder.svg" "$M/inode-directory.svg"

trash_svg '' > "$P/user-trash.svg"
trash_svg '<path d="M20 11l4-6 6 4 5-6 6 5 4-3 1 6z" fill="#ecdcae"/>' > "$P/user-trash-full.svg"

command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$ICONS" >/dev/null 2>&1

# ============================================================
# 3. Qt5 / Qt6 (qt5ct + qt6ct, Fusion + Celestia palette) and KDE/Dolphin colors
# ============================================================
say "Qt theme"
ACT="#ffece5d8, #ff343a4e, #ff4a5270, #ff3f465e, #ff1a1e2a, #ff2b3042, #ffece5d8, #ffffffff, #ffece5d8, #ff1e2230, #ff272c3b, #ff10131b, #ffd3bc8e, #ff272c3b, #ffe9d9a8, #ffb8a47a, #ff232838, #ff000000, #ffece5d8, #ff3b4255, #ff8a8fa3"
DIS="#ff6f7488, #ff2f3547, #ff3f465e, #ff353b50, #ff1a1e2a, #ff262b3b, #ff6f7488, #ffffffff, #ff6f7488, #ff222735, #ff272c3b, #ff10131b, #ff4a5270, #ff9aa0b4, #ff8a7f62, #ff6e6650, #ff232838, #ff000000, #ffece5d8, #ff3b4255, #ff6f7488"

for v in qt5ct qt6ct; do
  d="$HOME/.config/$v"
  mkdir -p "$d/colors"
  printf '[ColorScheme]\nactive_colors=%s\ninactive_colors=%s\ndisabled_colors=%s\n' "$ACT" "$ACT" "$DIS" > "$d/colors/$NAME.conf"
  bk "$d/$v.conf"
  cat > "$d/$v.conf" <<EOF
[Appearance]
color_scheme_path=$d/colors/$NAME.conf
custom_palette=true
icon_theme=$NAME
standard_dialogs=default
style=Fusion

[Interface]
dialog_buttons_layout=0
stylesheets=@Invalid()
EOF
done

# KDE color scheme (Dolphin & KDE apps)
mkdir -p "$HOME/.local/share/color-schemes"
sec(){ printf '[Colors:%s]\nBackgroundNormal=%s\nBackgroundAlternate=%s\nForegroundNormal=%s\nForegroundInactive=%s\nForegroundActive=%s\nForegroundLink=%s\nForegroundVisited=%s\nForegroundNegative=224,108,108\nForegroundNeutral=232,170,90\nForegroundPositive=130,200,150\nDecorationFocus=%s\nDecorationHover=%s\n\n' "$@"; }
W="39,44,59 47,53,71 236,229,216 138,143,163 211,188,142 233,217,168 184,164,122 211,188,142 233,217,168"
{
  sec View 30,34,48 35,40,56 236,229,216 138,143,163 211,188,142 233,217,168 184,164,122 211,188,142 233,217,168
  sec Window $W
  sec Header $W
  sec Complementary $W
  sec Button 52,58,78 60,67,90 236,229,216 138,143,163 211,188,142 233,217,168 184,164,122 211,188,142 233,217,168
  sec Selection 211,188,142 222,200,155 39,44,59 59,66,85 39,44,59 59,66,85 59,66,85 39,44,59 255,255,255
  sec Tooltip 236,229,216 226,218,203 59,66,85 100,106,125 59,66,85 59,66,85 59,66,85 211,188,142 211,188,142
  printf '[General]\nColorScheme=Celestia\nName=Celestia\n\n[KDE]\ncontrast=4\n\n[WM]\nactiveBackground=39,44,59\nactiveForeground=236,229,216\ninactiveBackground=30,34,48\ninactiveForeground=138,143,163\nactiveBlend=211,188,142\ninactiveBlend=74,82,112\n'
} > "$HOME/.local/share/color-schemes/$NAME.colors"

KW=""
command -v kwriteconfig6 >/dev/null 2>&1 && KW=kwriteconfig6
[ -z "$KW" ] && command -v kwriteconfig5 >/dev/null 2>&1 && KW=kwriteconfig5
if [ -n "$KW" ]; then
  bk "$HOME/.config/kdeglobals"
  $KW --file kdeglobals --group General --key ColorScheme "$NAME"
  $KW --file kdeglobals --group Icons   --key Theme "$NAME"
elif [ ! -f "$HOME/.config/kdeglobals" ]; then
  printf '[General]\nColorScheme=Celestia\n\n[Icons]\nTheme=Celestia\n' > "$HOME/.config/kdeglobals"
fi

# Env var so Qt picks qt6ct/qt5ct
mkdir -p "$HOME/.config/environment.d"
printf 'QT_QPA_PLATFORMTHEME=qt6ct\n' > "$HOME/.config/environment.d/90-celestia.conf"

# ============================================================
# 4. Flatpak apps (optional)
# ============================================================
if command -v flatpak >/dev/null 2>&1; then
  say "Flatpak overrides"
  flatpak override --user \
    --filesystem=xdg-data/themes:ro --filesystem=xdg-data/icons:ro \
    --filesystem=xdg-config/gtk-3.0:ro --filesystem=xdg-config/gtk-4.0:ro \
    --env=GTK_THEME="$NAME" 2>/dev/null
fi

# ============================================================
say "Done ✦  (backup: $BK)"
echo
echo "1) Make sure Hyprland exports this variable, then log out and back in:"
if grep -rqs 'QT_QPA_PLATFORMTHEME' "$HOME/.config/hypr" "$HOME/.config/hypr-genshin" 2>/dev/null; then
  echo "   (already set in your Hyprland config — check that it is 'qt6ct')"
else
  echo "   env = QT_QPA_PLATFORMTHEME,qt6ct       # hyprland.conf syntax"
  echo '   hl.env("QT_QPA_PLATFORMTHEME","qt6ct") # Lua syntax'
fi
echo "2) Test right away:  GTK_THEME=$NAME thunar   (or nautilus / pavucontrol)"
echo "3) Qt:               QT_QPA_PLATFORMTHEME=qt6ct dolphin"
echo "4) HyDE: if hyde-themes overwrites gtk/qt settings on theme switch, re-run this script."
