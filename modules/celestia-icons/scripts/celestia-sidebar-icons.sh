#!/usr/bin/env bash
# ============================================================
#  Celestia Sidebar Icons — آیکون‌های رنگی سایدبار فایل‌چوزر
#  هر آیکون یه نشان گرد با رنگ المنت + لبه‌ی طلایی + گلیف تیره
#  Usage:  bash celestia-sidebar-icons.sh
#  Undo :  bash celestia-sidebar-icons.sh --undo
# ============================================================

NAME="Celestia"
ICONS="$HOME/.local/share/icons/$NAME"
P="$ICONS/scalable/places"
LIST="$ICONS/.sidebar-icons.list"

say(){ printf '\033[38;5;180m✦ %s\033[0m\n' "$*"; }

strip_css(){ # file
  [ -f "$1" ] && sed -i '/CELESTIA-SIDEBAR-ICONS BEGIN/,/CELESTIA-SIDEBAR-ICONS END/d' "$1"
}

# ---------------- undo ----------------
if [ "$1" = "--undo" ]; then
  say "Undo"
  strip_css "$HOME/.config/gtk-3.0/gtk.css"
  strip_css "$HOME/.config/gtk-4.0/gtk.css"
  if [ -f "$LIST" ]; then
    while read -r f; do rm -f "$P/$f.svg"; done < "$LIST"
    rm -f "$LIST"
  fi
  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$ICONS" >/dev/null 2>&1
  say "Done — کروم رو کامل ببند و باز کن"
  exit 0
fi

mkdir -p "$P"
: > "$LIST"

AN='#74c2a8'; EL='#b18fd6'; GE='#f0b232'; DE='#a5c83b'
HY='#4cc2f1'; PY='#ef7a35'; CR='#9fd6e3'

badge(){ cat <<EOF
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<defs>
<linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity=".6"/><stop offset=".55" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
</defs>
<circle cx="32" cy="32" r="29" fill="$1"/>
<circle cx="32" cy="32" r="29" fill="url(#s)"/>
<circle cx="32" cy="32" r="29" fill="none" stroke="#d3bc8e" stroke-width="3.5"/>
<g transform="translate(32 32)" fill="#272c3b">$2</g>
</svg>
EOF
}

mk(){ # "name1,name2" color glyph
  local names="$1" first="${1%%,*}" n
  badge "$2" "$3" > "$P/$first.svg"
  echo "$first" >> "$LIST"
  IFS=, read -ra al <<< "$names"
  for n in "${al[@]:1}"; do cp "$P/$first.svg" "$P/$n.svg"; echo "$n" >> "$LIST"; done
}

# ---------------- glyphs (box ≈ ±15) ----------------
G_HOME='<path d="M0 -15L-16 -1H-11V14H-3V5H3V14H11V-1H16Z"/>'
G_FOLDER='<path d="M-15 -10H-4L0 -6H15V12H-15Z"/>'
G_DOCS='<path fill-rule="evenodd" d="M-9 -14H3L11 -6V14H-9ZM-5 -1H7V2H-5ZM-5 6H7V9H-5Z"/>'
G_DOWN='<path d="M-4 -14H4V-2H11L0 10L-11 -2H-4Z"/><path d="M-13 12H13V16H-13Z"/>'
G_MUSIC='<circle cx="-7" cy="10" r="5"/><circle cx="6" cy="7" r="5"/><path d="M-3 -12L12 -15V7H9V-9L0 -7V10H-3Z"/>'
G_PICS='<path d="M-15 12L-6 -2L0 6L5 -1L15 12Z"/><circle cx="7" cy="-8" r="4"/>'
G_VID='<path d="M-15 -9H4V9H-15Z"/><path d="M7 -3L15 -8V8L7 3Z"/>'
G_CLOCK='<path fill-rule="evenodd" d="M0 -15A15 15 0 1 1 0 15A15 15 0 1 1 0 -15ZM0 -11A11 11 0 1 0 0 11A11 11 0 1 0 0 -11Z"/><path d="M-1.8 -7H1.8V0L6 3L4.2 6L-1.8 2Z"/>'
G_DESK='<path fill-rule="evenodd" d="M-15 -11H15V6H-15ZM-11 -7V2H11V-7Z"/><path d="M-5 9H5V13H-5Z"/>'
G_TRASH='<path d="M-4 -14H4V-11H12V-7H-12V-11H-4Z"/><path d="M-9 -4H9L8 14H-8Z"/>'
G_NET='<path fill-rule="evenodd" d="M0 -15A15 15 0 1 1 0 15A15 15 0 1 1 0 -15ZM0 -11A11 11 0 1 0 0 11A11 11 0 1 0 0 -11Z"/><path d="M-1.5 -11H1.5V11H-1.5Z"/><path d="M-11 -1.5H11V1.5H-11Z"/>'
G_STAR='<path d="M0 -15L4 -4L15 0L4 4L0 15L-4 4L-15 0L-4 -4Z"/>'
G_PLUS='<path d="M-3 -13H3V-3H13V3H3V13H-3V3H-13V-3H-3Z"/>'

say "Sidebar icons"
mk "document-open-recent"                                   "$HY" "$G_CLOCK"
mk "user-home,folder-home"                                  "$GE" "$G_HOME"
mk "folder,folder-open"                                     "$GE" "$G_FOLDER"
mk "folder-documents"                                       "$GE" "$G_DOCS"
mk "folder-download"                                        "$DE" "$G_DOWN"
mk "folder-music"                                           "$HY" "$G_MUSIC"
mk "folder-pictures"                                        "$AN" "$G_PICS"
mk "folder-videos"                                          "$PY" "$G_VID"
mk "user-desktop,folder-desktop"                            "$EL" "$G_DESK"
mk "user-trash,user-trash-full"                             "$PY" "$G_TRASH"
mk "network-workgroup,network-server"                       "$AN" "$G_NET"
mk "folder-publicshare,folder-templates,folder-remote"      "$CR" "$G_STAR"
mk "list-add"                                               "$GE" "$G_PLUS"

# ---------------- CSS: sidebar uses the colored (regular) icons ----------------
say "CSS"
put_block(){
  local f="$1"
  mkdir -p "$(dirname "$f")"; touch "$f"
  strip_css "$f"
  cat >> "$f" <<'EOF'
/* >>> CELESTIA-SIDEBAR-ICONS BEGIN >>> */
placessidebar row image {
  -gtk-icon-style: regular;
  -gtk-icon-shadow: none;
}
/* <<< CELESTIA-SIDEBAR-ICONS END <<< */
EOF
}
put_block "$HOME/.config/gtk-3.0/gtk.css"
put_block "$HOME/.config/gtk-4.0/gtk.css"

command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$ICONS" >/dev/null 2>&1

say "Done ✦"
echo "کروم (و هر برنامه‌ی دیگه) رو کامل ببند و دوباره باز کن."
echo "تست سریع:  zenity --file-selection"
echo "برگردوندن به حالت قبل:  bash celestia-sidebar-icons.sh --undo"
