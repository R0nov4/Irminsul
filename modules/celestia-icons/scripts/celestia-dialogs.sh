#!/usr/bin/env bash
# ============================================================
#  Celestia Dialogs — دیزاین جنشینی برای پنجره انتخاب فایل (Open/Save)
#  + آیکون‌های سایدبار (symbolic) به سبک Celestia
#  Usage:  bash celestia-dialogs.sh
# ============================================================

NAME="Celestia"
ICONS="$HOME/.local/share/icons/$NAME"
BK="$HOME/.config/celestia-backup-dialogs-$(date +%Y%m%d-%H%M%S)"
say(){ printf '\033[38;5;180m✦ %s\033[0m\n' "$*"; }
warn(){ printf '\033[38;5;203m! %s\033[0m\n' "$*"; }

mkdir -p "$ICONS/symbolic/places" "$ICONS/symbolic/actions" "$BK"

# ============================================================
# 1. Symbolic icons (GTK recolors them with CSS `color`)
# ============================================================
say "Symbolic icons"
SP="$ICONS/symbolic/places"; SA="$ICONS/symbolic/actions"

sym(){ # dir "name1,name2" "path data"
  local dir="$1" names="$2" first="${2%%,*}" n
  printf '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><g fill="#bebebe" fill-rule="evenodd">%s</g></svg>\n' "$3" > "$dir/$first.svg"
  IFS=, read -ra al <<< "$names"
  for n in "${al[@]:1}"; do cp "$dir/$first.svg" "$dir/$n.svg"; done
}

sym "$SP" "user-home-symbolic,folder-home-symbolic" \
  '<path d="M8 1.2L1.2 7.4H3.4V14.4H6.6V10H9.4V14.4H12.6V7.4H14.8Z"/>'
sym "$SP" "folder-symbolic,folder-open-symbolic,inode-directory-symbolic" \
  '<path d="M1.5 3H6.2L7.7 4.6H14.5V13H1.5Z"/>'
sym "$SP" "folder-documents-symbolic" \
  '<path d="M3.5 1.5H9.5L12.5 4.5V14.5H3.5ZM5.5 7.4H10.5V8.6H5.5ZM5.5 10H10.5V11.2H5.5Z"/>'
sym "$SP" "folder-download-symbolic" \
  '<path d="M6.5 1.5H9.5V7H12L8 11.4L4 7H6.5Z"/><path d="M2.5 12.8H13.5V14.4H2.5Z"/>'
sym "$SP" "folder-music-symbolic" \
  '<circle cx="4.5" cy="12" r="2.3"/><circle cx="11.5" cy="10.5" r="2.3"/><path d="M6.2 12V3L13.4 1.5V10.5H12V3.3L7.6 4.2V12Z"/>'
sym "$SP" "folder-pictures-symbolic" \
  '<path d="M1.5 13.5L6 6.5L9 10.5L11 8L14.5 13.5Z"/><circle cx="11" cy="4.5" r="1.8"/>'
sym "$SP" "folder-videos-symbolic" \
  '<path d="M1.5 3.5H10.5V12.5H1.5Z"/><path d="M11.5 6.3L14.5 4.3V11.7L11.5 9.7Z"/>'
sym "$SP" "folder-publicshare-symbolic,folder-templates-symbolic,folder-remote-symbolic" \
  '<path d="M8 1L9.8 6.2L15 8L9.8 9.8L8 15L6.2 9.8L1 8L6.2 6.2Z"/>'
sym "$SP" "network-workgroup-symbolic,network-server-symbolic" \
  '<path d="M8 1A7 7 0 1 1 8 15A7 7 0 1 1 8 1ZM8 2.6A5.4 5.4 0 1 0 8 13.4A5.4 5.4 0 1 0 8 2.6Z"/><path d="M7.4 2.6H8.6V13.4H7.4Z"/><path d="M2.6 7.4H13.4V8.6H2.6Z"/>'
sym "$SP" "user-desktop-symbolic,computer-symbolic,video-display-symbolic" \
  '<path d="M1.5 2.5H14.5V11.5H1.5ZM3 4V10H13V4Z"/><path d="M5.5 13H10.5V14.3H5.5Z"/>'
sym "$SP" "user-trash-symbolic,user-trash-full-symbolic,edit-delete-symbolic" \
  '<path d="M6 1H10V2.4H6Z"/><path d="M2 2.8H14V4.2H2Z"/><path d="M3.4 4.8H12.6L11.8 14.6H4.2Z"/>'
sym "$SP" "drive-harddisk-symbolic,drive-harddisk-solidstate-symbolic,drive-removable-media-symbolic" \
  '<path d="M1.5 5.5H14.5V12.5H1.5ZM12 8.2A1 1 0 1 0 12 10.2A1 1 0 1 0 12 8.2Z"/>'

sym "$SA" "document-open-recent-symbolic,document-open-recent" \
  '<path d="M8 1A7 7 0 1 1 8 15A7 7 0 1 1 8 1ZM8 2.5A5.5 5.5 0 1 0 8 13.5A5.5 5.5 0 1 0 8 2.5Z"/><path d="M7.3 4.2H8.7V7.7L10.9 9L10.2 10.2L7.3 8.5Z"/>'
sym "$SA" "edit-find-symbolic,system-search-symbolic,find-location-symbolic" \
  '<path d="M6.5 1.3A5.2 5.2 0 1 1 6.5 11.7A5.2 5.2 0 1 1 6.5 1.3ZM6.5 2.9A3.6 3.6 0 1 0 6.5 10.1A3.6 3.6 0 1 0 6.5 2.9Z"/><path d="M6.5 4.1L7.1 5.9L8.9 6.5L7.1 7.1L6.5 8.9L5.9 7.1L4.1 6.5L5.9 5.9Z"/><path d="M10 11.1L11.1 10L14.6 13.5L13.5 14.6Z"/>'
sym "$SA" "list-add-symbolic,tab-new-symbolic" \
  '<path d="M7.2 2H8.8V7.2H14V8.8H8.8V14H7.2V8.8H2V7.2H7.2Z"/>'
sym "$SA" "pan-start-symbolic,go-previous-symbolic" '<path d="M10.2 2.4L11.8 4L7.8 8L11.8 12L10.2 13.6L4.6 8Z"/>'
sym "$SA" "pan-end-symbolic,go-next-symbolic"      '<path d="M5.8 2.4L4.2 4L8.2 8L4.2 12L5.8 13.6L11.4 8Z"/>'
sym "$SA" "pan-down-symbolic,go-down-symbolic"     '<path d="M2.4 5.8L4 4.2L8 8.2L12 4.2L13.6 5.8L8 11.4Z"/>'
sym "$SA" "pan-up-symbolic,go-up-symbolic"         '<path d="M2.4 10.2L4 11.8L8 7.8L12 11.8L13.6 10.2L8 4.6Z"/>'
sym "$SA" "object-select-symbolic,checkbox-checked-symbolic,emblem-ok-symbolic" \
  '<path d="M6.2 12.6L2 8.4L3.6 6.8L6.2 9.4L12.4 3.2L14 4.8Z"/>'

# index.theme: register the symbolic dirs (idempotent)
IDX="$ICONS/index.theme"
if [ -f "$IDX" ]; then
  if ! grep -q 'symbolic/places' "$IDX"; then
    sed -i 's|^Directories=.*|&,symbolic/places,symbolic/actions|' "$IDX"
    cat >> "$IDX" <<'EOF'

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
  fi
else
  warn "index.theme not found — run celestia-theme-installer.sh first"
fi
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$ICONS" >/dev/null 2>&1

# ============================================================
# 2. File-chooser CSS (scoped to .filechooser only, so your own
#    Genshin GTK apps are not affected)
# ============================================================
say "Dialog styling"


dialog_css_head(){
  local P=("window.filechooser" "window.dialog" "dialog" ".filechooser") out
  hs(){ out=""; for x in "${P[@]}"; do out+="$x headerbar$1, "; done; printf '%s' "${out%, }"; }
  cat <<EOF2
/* ---- header: dark navy, centered title, fading gold line ---- */
$(hs '') {
  min-height: 54px;
  border: none;
  box-shadow: none;
  background-color: #262b3b;
  background-image:
    linear-gradient(to right, rgba(211,188,142,0), #d3bc8e 18%, #d3bc8e 82%, rgba(211,188,142,0)),
    linear-gradient(to bottom, #363c53, #262b3b);
  background-size: 100% 2px, 100% 100%;
  background-position: left bottom, left top;
  background-repeat: no-repeat;
}
$(hs ' .title'), $(hs ' title'), $(hs ' label.title') {
  color: #e9d9a8;
  font-weight: 700;
}
$(hs ' button.text-button') {
  background-image: linear-gradient(to bottom, #f3eee2, #dcd4c2);
  background-color: #e6dfcf;
  color: #3b4255;
  border: 1px solid #b9a56f;
  border-radius: 8px;
  padding: 6px 22px;
  font-weight: 700;
  text-shadow: none;
  box-shadow: none;
}
$(hs ' button.text-button:hover') {
  background-image: linear-gradient(to bottom, #fffaf0, #ebe3cf);
  border-color: #d3bc8e;
}
$(hs ' button.text-button.suggested-action') {
  background-image: linear-gradient(to bottom, #f4e1a4, #d2b46a);
  border-color: #a88c58;
  color: #3b4255;
}
$(hs ' button.text-button.suggested-action:hover') {
  background-image: linear-gradient(to bottom, #fff0bd, #dcc07a);
}
$(hs ' button.image-button') {
  border-radius: 50%;
  border: 1px solid rgba(211,188,142,0.60);
  background-image: linear-gradient(to bottom, #3b4259, #2c3246);
  color: #d3bc8e;
  padding: 6px;
  min-width: 22px;
  min-height: 22px;
  box-shadow: none;
}
$(hs ' button.image-button:hover') { border-color: #e9d9a8; color: #e9d9a8; }
$(hs ' button.image-button:checked') {
  background-image: none;
  background-color: #d3bc8e;
  color: #272c3b;
}

EOF2
}

dialog_css_body(){ cat <<'EOF'
/* ---- window ---- */
filechooser, .filechooser, window.filechooser, window.dialog, dialog {
  background-color: #272c3b;
  color: #ece5d8;
}
window.csd.filechooser { border-radius: 14px; }

/* ---- sidebar (Genshin menu list) ---- */
placessidebar,
placessidebar list,
placessidebar scrolledwindow,
placessidebar viewport {
  background-color: #1f2432;
  background-image: none;
}
placessidebar row {
  min-height: 36px;
  margin: 2px 8px;
  padding: 0 6px;
  border-radius: 8px;
  color: #d8d1c3;
  background-color: transparent;
  background-image: none;
  box-shadow: none;
  outline: none;
}
placessidebar row image { color: #d3bc8e; }
placessidebar row:hover { background-color: rgba(236,229,216,0.10); }
placessidebar row:selected,
placessidebar row:selected:focus,
placessidebar row:selected:backdrop {
  background-color: #ece5d8;
  color: #3b4255;
  box-shadow: inset 4px 0 0 #d3bc8e;
}
placessidebar row:selected label,
placessidebar row:selected image { color: #3b4255; }
placessidebar separator { background-color: rgba(211,188,142,0.25); margin: 6px 14px; min-height: 1px; }

/* ---- path bar: rounded chips ---- */
filechooser .path-bar, filechooser pathbar { padding: 4px 2px; }
filechooser .path-bar button, filechooser pathbar button {
  background-image: none;
  background-color: #2f3547;
  color: #ece5d8;
  border: 1px solid rgba(211,188,142,0.35);
  border-radius: 16px;
  margin: 0 3px;
  padding: 4px 16px;
  box-shadow: none;
}
filechooser .path-bar button:hover, filechooser pathbar button:hover { background-color: #3a4158; border-color: #d3bc8e; }
filechooser .path-bar button:checked, filechooser pathbar button:checked {
  background-color: #d3bc8e;
  background-image: none;
  border-color: #e9d9a8;
  color: #272c3b;
  font-weight: 700;
  box-shadow: 0 0 10px rgba(211,188,142,0.45);
}
filechooser .path-bar button.slider-button, filechooser pathbar button.slider-button,
filechooser .path-bar > button:first-child, filechooser .path-bar > button:last-child {
  border-radius: 50%;
  padding: 4px 8px;
  min-width: 18px;
  color: #d3bc8e;
}

/* ---- checkbox ---- */
filechooser check, filechooser checkbutton check {
  min-width: 18px;
  min-height: 18px;
  border-radius: 5px;
  border: 1px solid #d3bc8e;
  background-image: none;
  background-color: #1e2230;
  color: #272c3b;
  box-shadow: none;
}
filechooser check:hover { border-color: #e9d9a8; }
filechooser check:checked, filechooser check:indeterminate {
  background-color: #d3bc8e;
  border-color: #e9d9a8;
  color: #272c3b;
}

/* ---- file list ---- */
filechooser treeview.view, filechooser columnview, filechooser columnview listview,
filechooser listview, filechooser .view {
  background-color: #1e2230;
  color: #ece5d8;
}
filechooser treeview.view:hover { background-color: rgba(211,188,142,0.14); }
filechooser treeview.view:selected, filechooser treeview.view:selected:focus,
filechooser treeview.view:selected:backdrop,
filechooser listview row:selected, filechooser columnview row:selected,
filechooser listview row:selected:focus, filechooser columnview row:selected:focus {
  background-color: #ece5d8;
  background-image: none;
  color: #3b4255;
  outline: none;
}
filechooser listview row:hover, filechooser columnview row:hover { background-color: rgba(211,188,142,0.14); }

/* ---- column headers: gold on dark ---- */
filechooser treeview header button, filechooser columnview header button {
  background-color: #2a3042;
  background-image: none;
  color: #d3bc8e;
  font-weight: 700;
  border: none;
  border-bottom: 1px solid rgba(211,188,142,0.45);
  border-radius: 0;
  padding: 6px 8px;
  box-shadow: none;
}
EOF
}
dialog_css(){ dialog_css_head; dialog_css_body; }

put_block(){ # file
  local f="$1"
  mkdir -p "$(dirname "$f")"; touch "$f"
  cp -a "$f" "$BK/$(echo "$f" | tr '/' '_')" 2>/dev/null
  sed -i '/CELESTIA-DIALOGS BEGIN/,/CELESTIA-DIALOGS END/d' "$f"
  { echo '/* >>> CELESTIA-DIALOGS BEGIN >>> */'; dialog_css; echo '/* <<< CELESTIA-DIALOGS END <<< */'; } >> "$f"
}
put_block "$HOME/.config/gtk-3.0/gtk.css"
put_block "$HOME/.config/gtk-4.0/gtk.css"

# ============================================================
# 3. Restart the file-chooser portal so Chrome/Firefox pick it up
# ============================================================
pkill -f xdg-desktop-portal-gtk 2>/dev/null
systemctl --user restart xdg-desktop-portal.service 2>/dev/null

say "Done ✦"
echo
echo "Test (without Chrome):"
echo "   zenity --file-selection"
echo "   GTK_DEBUG=interactive zenity --file-selection   # inspector, to see CSS node names"
echo "Then in Chrome press Ctrl+O. Backup: $BK"
echo "Remove the style: delete the CELESTIA-DIALOGS block from ~/.config/gtk-3.0/gtk.css and gtk-4.0/gtk.css"
