#!/usr/bin/env bash
# ============================================================
#  Celestia Icon Pack — اپ‌ها + دیسک‌ها + فایل‌ها (به سبک جنشین)
#  هر دسته یه رنگ المنت داره:
#   Anemo=مرورگر/شبکه/عکس  Electro=ترمینال  Geo=فایل‌ها/ماشین‌حساب
#   Dendro=کد/مانیتور  Hydro=چت/صدا/بلوتوث  Pyro=مدیا/PDF  Cryo=بازی/تنظیمات
#  Usage:  bash celestia-icons-pack.sh
# ============================================================

NAME="Celestia"
ICONS="$HOME/.local/share/icons/$NAME"
A="$ICONS/scalable/apps"; D="$ICONS/scalable/devices"
M="$ICONS/scalable/mimetypes"; P="$ICONS/scalable/places"
mkdir -p "$A" "$D" "$M" "$P"

say(){ printf '\033[38;5;180m✦ %s\033[0m\n' "$*"; }

AN='#74c2a8'; EL='#b18fd6'; GE='#f0b232'; DE='#a5c83b'
HY='#4cc2f1'; PY='#ef7a35'; CR='#9fd6e3'

# ---------- index.theme ----------
cat > "$ICONS/index.theme" <<'EOF'
[Icon Theme]
Name=Celestia
Comment=Genshin Celestia icon theme (inherits Papirus for all other icons)
Inherits=Papirus-Dark,Papirus,breeze-dark,Adwaita,hicolor
Directories=scalable/places,scalable/mimetypes,scalable/apps,scalable/devices,symbolic/places,symbolic/actions

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

[scalable/apps]
Size=64
MinSize=16
MaxSize=512
Type=Scalable
Context=Applications

[scalable/devices]
Size=64
MinSize=16
MaxSize=512
Type=Scalable
Context=Devices

[symbolic/places]
Size=16
MinSize=8
MaxSize=512
Type=Scalable
Context=Places

[symbolic/actions]
Size=16
MinSize=8
MaxSize=512
Type=Scalable
Context=Actions
EOF

# ---------- tile templates ----------
app_svg(){ cat <<EOF
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<defs>
<linearGradient id="t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#454e6b"/><stop offset="1" stop-color="#222737"/></linearGradient>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f1e3b8"/><stop offset="1" stop-color="#c3a56b"/></linearGradient>
<radialGradient id="h" cx=".5" cy="0" r=".95"><stop offset="0" stop-color="$1" stop-opacity=".42"/><stop offset="1" stop-color="$1" stop-opacity="0"/></radialGradient>
</defs>
<rect x="4" y="4" width="56" height="56" rx="14" fill="url(#t)" stroke="$1" stroke-width="2"/>
<rect x="4" y="4" width="56" height="56" rx="14" fill="url(#h)"/>
<rect x="7.5" y="7.5" width="49" height="49" rx="11" fill="none" stroke="#d3bc8e" stroke-opacity=".5" stroke-width="1"/>
<path d="M51.5 9.5L52.7 12.8L56 14L52.7 15.2L51.5 18.5L50.3 15.2L47 14L50.3 12.8Z" fill="$1"/>
<g transform="translate(32 33.5) scale(.92)" fill="url(#g)">$2</g>
</svg>
EOF
}

mime_svg(){ cat <<EOF
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<defs>
<linearGradient id="t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#454e6b"/><stop offset="1" stop-color="#222737"/></linearGradient>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f1e3b8"/><stop offset="1" stop-color="#c3a56b"/></linearGradient>
</defs>
<path d="M14 6H38L50 18V56Q50 58 48 58H16Q14 58 14 56V8Q14 6 16 6Z" fill="url(#t)" stroke="#d3bc8e" stroke-width="1.6" stroke-linejoin="round"/>
<path d="M38 6V16Q38 18 40 18H50" fill="#d3bc8e" fill-opacity=".25" stroke="#d3bc8e" stroke-width="1.4" stroke-linejoin="round"/>
<path d="M14.8 45H49.2V56Q49.2 57.2 48 57.2H16Q14.8 57.2 14.8 56Z" fill="$1" fill-opacity=".9"/>
<g transform="translate(32 31) scale(.6)" fill="url(#g)">$2</g>
</svg>
EOF
}

# app "name1,name2,..." COLOR GLYPH   → first name = file, others = copies
mk(){ # dir tpl names color glyph
  local dir="$1" tpl="$2" names="$3" first="${3%%,*}" n
  "$tpl" "$4" "$5" > "$dir/$first.svg"
  IFS=, read -ra al <<< "$names"
  for n in "${al[@]:1}"; do cp "$dir/$first.svg" "$dir/$n.svg"; done
}
app(){ mk "$A" app_svg "$@"; }
mime(){ mk "$M" mime_svg "$@"; }
dev(){ mk "$D" app_svg "$@"; }

# ---------- glyphs (box ≈ ±14) ----------
G_GLOBE='<g fill="none" stroke="#e6d4a4" stroke-width="2.2" stroke-linecap="round"><circle r="12"/><ellipse rx="5" ry="12"/><path d="M-12 0H12M-10 -6H10M-10 6H10"/></g>'
G_TERM='<g fill="none" stroke="#e6d4a4" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M-11 -8L-2 0L-11 8"/><path d="M2 9H12"/></g>'
G_FILES='<path d="M-12 -9H-3L0 -6H12V10H-12Z"/><path d="M-12 -2H12" stroke="#2b3042" stroke-width="1.6"/>'
G_CODE='<g fill="none" stroke="#e6d4a4" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M-6 -8L-13 0L-6 8"/><path d="M6 -8L13 0L6 8"/><path d="M2.5 -11L-2.5 11"/></g>'
G_CHAT='<path d="M-12 -10H12V5H3L-4 12V5H-12Z"/><circle cx="-5" cy="-2.5" r="1.6" fill="#2b3042"/><circle cx="0" cy="-2.5" r="1.6" fill="#2b3042"/><circle cx="5" cy="-2.5" r="1.6" fill="#2b3042"/>'
G_PLANE='<path d="M-13 -1L13 -11L6 11L-1 3L-6 8L-6 1Z"/><path d="M-6 1L13 -11" stroke="#2b3042" stroke-width="1.4"/>'
G_MUSIC='<circle cx="-6" cy="8" r="4"/><circle cx="7" cy="5" r="4"/><path d="M-4 8V-9L9 -12V5H7V-9L-2 -7V8Z"/>'
G_PLAY='<circle r="13" fill="none" stroke="#e6d4a4" stroke-width="2.2"/><path d="M-4 -7L8 0L-4 7Z"/>'
G_GAME='<path d="M-8 -7H8Q14 -7 14 0L12 9Q11 11 9 9L6 6H-6L-9 9Q-11 11 -12 9L-14 0Q-14 -7 -8 -7Z"/><path d="M-9 -2V4M-12 1H-6" stroke="#2b3042" stroke-width="2"/><circle cx="6" cy="-1" r="1.6" fill="#2b3042"/><circle cx="9.5" cy="2" r="1.6" fill="#2b3042"/>'
G_GEAR='<circle r="8.5"/><rect x="-2.2" y="-13" width="4.4" height="6" rx="1"/><rect x="-2.2" y="-13" width="4.4" height="6" rx="1" transform="rotate(45)"/><rect x="-2.2" y="-13" width="4.4" height="6" rx="1" transform="rotate(90)"/><rect x="-2.2" y="-13" width="4.4" height="6" rx="1" transform="rotate(135)"/><rect x="-2.2" y="-13" width="4.4" height="6" rx="1" transform="rotate(180)"/><rect x="-2.2" y="-13" width="4.4" height="6" rx="1" transform="rotate(225)"/><rect x="-2.2" y="-13" width="4.4" height="6" rx="1" transform="rotate(270)"/><rect x="-2.2" y="-13" width="4.4" height="6" rx="1" transform="rotate(315)"/><circle r="3.6" fill="#2b3042"/>'
G_SPEAKER='<path d="M-13 -4H-7L1 -11V11L-7 4H-13Z"/><path d="M6 -5Q10 0 6 5M9.5 -9Q17 0 9.5 9" fill="none" stroke="#e6d4a4" stroke-width="2.2" stroke-linecap="round"/>'
G_BT='<path d="M-6 -6L6 6L0 12V-12L6 -6L-6 6" fill="none" stroke="#e6d4a4" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
G_WIFI='<g fill="none" stroke="#e6d4a4" stroke-width="2.4" stroke-linecap="round"><path d="M-12 -3Q0 -14 12 -3"/><path d="M-7.5 2Q0 -5 7.5 2"/></g><circle cy="8" r="2.4"/>'
G_MON='<g fill="none" stroke="#e6d4a4" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="-13" y="-10" width="26" height="17" rx="2.5"/><path d="M-9 -1H-4L-2 -5L2 3L4 -1H9"/><path d="M-5 11H5"/></g>'
G_CALC='<g fill="none" stroke="#e6d4a4" stroke-width="2.2"><rect x="-9" y="-12" width="18" height="24" rx="3"/></g><rect x="-6" y="-9" width="12" height="5" rx="1"/><circle cx="-4" cy="2" r="1.6"/><circle cx="0" cy="2" r="1.6"/><circle cx="4" cy="2" r="1.6"/><circle cx="-4" cy="7" r="1.6"/><circle cx="0" cy="7" r="1.6"/><circle cx="4" cy="7" r="1.6"/>'
G_EDIT='<path fill-rule="evenodd" d="M-8 -12H3L9 -6V12H-8ZM-5 -1H6V1H-5ZM-5 4H6V6H-5Z"/>'
G_IMG='<path d="M-13 10L-5 -2L0 5L5 -1L13 10Z"/><circle cx="6" cy="-7" r="2.8"/>'
G_BOX='<path d="M-12 -6L0 -12L12 -6V6L0 12L-12 6Z"/><path d="M-12 -6L0 0L12 -6M0 0V12" fill="none" stroke="#2b3042" stroke-width="1.8"/>'
G_STARL='<path d="M0 -13L3.4 -3.4L13 0L3.4 3.4L0 13L-3.4 3.4L-13 0L-3.4 -3.4Z"/>'
G_BOOK='<path d="M-12 -9H-2Q-0.8 -9 -0.8 -7.5V11Q-0.8 9.5 -2.5 9.5H-12ZM12 -9H2Q0.8 -9 0.8 -7.5V11Q0.8 9.5 2.5 9.5H12Z"/>'
G_HDD='<path fill-rule="evenodd" d="M-13 -3H13V8Q13 10 11 10H-11Q-13 10 -13 8ZM6 3A1.6 1.6 0 1 0 6 6.2A1.6 1.6 0 1 0 6 3Z"/><path d="M-11 -4L-7 -11H7L11 -4Z"/>'
G_USB='<rect x="-7" y="-3" width="14" height="15" rx="3"/><rect x="-4" y="-12" width="3" height="8"/><rect x="1" y="-12" width="3" height="8"/>'
G_DISC='<path fill-rule="evenodd" d="M0 -13A13 13 0 1 1 0 13A13 13 0 1 1 0 -13ZM0 -3.5A3.5 3.5 0 1 0 0 3.5A3.5 3.5 0 1 0 0 -3.5Z"/>'
G_PC='<path fill-rule="evenodd" d="M-13 -11H13V6H-13ZM-10.5 -8.5V3.5H10.5V-8.5Z"/><path d="M-3 8H3L4 12H-4Z"/>'

# ---------- apps ----------
say "Apps"
app "start-here,distributor-logo,distributor-logo-archlinux,archlinux-logo,start-here-archlinux,arch-linux" "$GE" "$G_STARL"
app "firefox,firefox-esr,org.mozilla.firefox,firefox-developer-edition,zen-browser,zen,librewolf,google-chrome,chromium,brave-browser,brave,microsoft-edge,vivaldi,web-browser,internet-web-browser" "$AN" "$G_GLOBE"
app "utilities-terminal,kitty,Alacritty,alacritty,foot,wezterm,org.wezfurlong.wezterm,org.gnome.Terminal,konsole,org.kde.konsole,terminal,xterm,ghostty,com.mitchellh.ghostty" "$EL" "$G_TERM"
app "system-file-manager,thunar,org.gnome.Nautilus,nautilus,org.kde.dolphin,dolphin,nemo,pcmanfm,pcmanfm-qt,yazi" "$GE" "$G_FILES"
app "code,visual-studio-code,code-oss,vscodium,codium,com.visualstudio.code,cursor,zed,dev.zed.Zed,nvim,neovim,sublime-text" "$DE" "$G_CODE"
app "discord,com.discordapp.Discord,vesktop,element,signal-desktop,whatsapp" "$HY" "$G_CHAT"
app "telegram,telegram-desktop,org.telegram.desktop" "$HY" "$G_PLANE"
app "spotify,spotify-client,rhythmbox,multimedia-audio-player" "$PY" "$G_MUSIC"
app "vlc,org.videolan.VLC,mpv,io.mpv.Mpv,celluloid,totem,obs,com.obsproject.Studio,multimedia-video-player" "$PY" "$G_PLAY"
app "steam,com.valvesoftware.Steam,lutris,net.lutris.Lutris,heroic,com.heroicgameslauncher.hgl,bottles,applications-games" "$CR" "$G_GAME"
app "preferences-system,org.gnome.Settings,gnome-control-center,systemsettings,preferences-desktop,nwg-look,qt5ct,qt6ct,kvantummanager,Kvantum,lxappearance" "$CR" "$G_GEAR"
app "pavucontrol,multimedia-volume-control,org.pulseaudio.pavucontrol" "$HY" "$G_SPEAKER"
app "blueman,blueman-manager,bluetooth,preferences-system-bluetooth" "$HY" "$G_BT"
app "nm-connection-editor,nm-applet,network-manager,preferences-system-network,nm-device-wireless" "$AN" "$G_WIFI"
app "utilities-system-monitor,btop,htop,gnome-system-monitor,org.gnome.SystemMonitor,mission-center,io.missioncenter.MissionCenter,net.nokyan.Resources" "$DE" "$G_MON"
app "org.gnome.Calculator,gnome-calculator,accessories-calculator,kcalc,org.kde.kcalc" "$GE" "$G_CALC"
app "accessories-text-editor,org.gnome.TextEditor,gedit,org.gnome.gedit,kate,org.kde.kate,mousepad,text-editor" "$GE" "$G_EDIT"
app "eog,org.gnome.eog,org.gnome.Loupe,imv,feh,nsxiv,viewnior,gwenview,org.kde.gwenview,image-viewer,gimp,org.gimp.GIMP" "$AN" "$G_IMG"
app "file-roller,org.gnome.FileRoller,ark,org.kde.ark,engrampa,xarchiver" "$GE" "$G_BOX"
app "org.pwmt.zathura,zathura,evince,org.gnome.Evince,okular,org.kde.okular" "$PY" "$G_BOOK"

# ---------- devices ----------
say "Devices"
dev "drive-harddisk,drive-harddisk-solidstate,drive-multidisk,drive-harddisk-system" "$GE" "$G_HDD"
dev "drive-removable-media,drive-removable-media-usb,media-removable,media-flash" "$HY" "$G_USB"
dev "drive-optical,media-optical,media-optical-cd,media-optical-dvd" "$CR" "$G_DISC"
dev "computer,computer-laptop,video-display" "$EL" "$G_PC"

# ---------- mimetypes ----------
say "File types"
mime "text-x-generic,text-plain,text-x-preview,x-office-document" "$GE" "$G_EDIT"
mime "application-pdf,application-x-pdf" "$PY" "$G_BOOK"
mime "image-x-generic,image-png,image-jpeg,image-gif,image-webp,image-svg+xml" "$AN" "$G_IMG"
mime "video-x-generic,video-mp4,video-x-matroska,video-webm" "$PY" "$G_PLAY"
mime "audio-x-generic,audio-mpeg,audio-flac,audio-x-wav,audio-ogg" "$HY" "$G_MUSIC"
mime "package-x-generic,application-zip,application-x-tar,application-x-compressed-tar,application-x-7z-compressed,application-x-rar,application-gzip,application-x-xz-compressed-tar" "$GE" "$G_BOX"
mime "text-x-script,application-x-shellscript,text-x-python,text-x-csrc,text-x-chdr,text-x-c++src,text-x-javascript,application-json,text-css,text-x-lua" "$DE" "$G_CODE"
mime "text-html,application-xhtml+xml" "$AN" "$G_GLOBE"
mime "application-x-executable,application-x-appimage" "$EL" "$G_GEAR"
mime "application-x-cd-image,application-x-iso9660-image" "$CR" "$G_DISC"

command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$ICONS" >/dev/null 2>&1

# ---------- preview page ----------
PV="$ICONS/preview.html"
{
  cat <<'EOF'
<!doctype html><meta charset="utf-8"><title>Celestia icons</title>
<style>
body{background:#1e2230;color:#ece5d8;font:14px system-ui,sans-serif;margin:28px}
h1{color:#d3bc8e;font-weight:600} h2{color:#d3bc8e;border-bottom:1px solid #4a5270;padding-bottom:6px;margin-top:34px}
.g{display:flex;flex-wrap:wrap;gap:14px}
figure{margin:0;width:104px;text-align:center}
img{width:64px;height:64px}
figcaption{font-size:11px;color:#9aa0b4;word-break:break-all;margin-top:4px}
</style>
<h1>✦ Celestia icon theme</h1>
EOF
  for d in apps devices mimetypes places; do
    echo "<h2>$d</h2><div class=g>"
    for f in "$ICONS/scalable/$d"/*.svg; do
      n=$(basename "$f" .svg)
      echo "<figure><img src=\"scalable/$d/$n.svg\"><figcaption>$n</figcaption></figure>"
    done
    echo "</div>"
  done
} > "$PV"

say "Done ✦ icons: $(find "$ICONS/scalable" -name '*.svg' | wc -l)"
echo "Preview: $PV"
[ -n "${CELESTIA_NO_PREVIEW:-}" ] || (xdg-open "$PV" >/dev/null 2>&1 &)
echo
echo "If the file manager still shows old icons: close it fully and reopen it."
echo "If you re-run celestia-theme-installer.sh, run this script again after it."
