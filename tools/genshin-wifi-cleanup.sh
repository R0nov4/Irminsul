#!/usr/bin/env bash
# ✦ Remove every OTHER Wi-Fi / network UI (HyDE & leftovers) — keep only Genshin Celestia.
#
#   bash genshin-wifi-cleanup.sh            → DRY RUN: only shows what it found, changes nothing
#   bash genshin-wifi-cleanup.sh --apply    → disables/removes what it found (everything is backed up)
#
# NOT touched on purpose: NetworkManager itself (nmcli) and the package that ships
# nm-connection-editor — Celestia needs both (connect, 802.1X/VPN editor).

set -u
APPLY=0; [[ ${1:-} == "--apply" ]] && APPLY=1
BK="$HOME/.cache/celestia-purge/$(date +%Y%m%d-%H%M%S)-others"
export APPLY BK

say() { printf '%s\n' "$*"; }
(( APPLY )) && say $'\n  ✦ APPLY mode — backups go to '"${BK/#$HOME/~}" || say $'\n  ✦ DRY RUN — nothing will be changed (add --apply to do it)'

# ── 1. running processes ────────────────────────────────────────────────
say $'\n[1] Running Wi-Fi / network UIs'
found=0
for name in nm-applet nm-tray; do
    if pgrep -ax -- "$name" 2>/dev/null; then
        found=1; (( APPLY )) && { pkill -x -- "$name" 2>/dev/null; say "    − stopped: $name"; }
    fi
done
for pat in 'networkmanager_dmenu' 'rofi.*[Ww]i-?[Ff]i' 'nmtui' 'iwgtk' 'impala'; do
    if pgrep -af -- "$pat" 2>/dev/null | grep -v 'genshin-wifi\|genshin-celestia\|cleanup' ; then
        found=1; (( APPLY )) && { pkill -f -- "$pat" 2>/dev/null; say "    − stopped: $pat"; }
    fi
done
(( found )) || say "    none running"

# ── 2. system autostart (nm-applet tray icon) ──────────────────────────
say $'\n[2] XDG autostart'
for f in /etc/xdg/autostart/nm-applet.desktop /etc/xdg/autostart/nm-tray.desktop; do
    [[ -f $f ]] || continue
    n=$(basename "$f"); ov="$HOME/.config/autostart/$n"
    if [[ -f $ov ]] && grep -q '^Hidden=true' "$ov"; then say "    already disabled: $n"; continue; fi
    say "    found: $f"
    if (( APPLY )); then
        mkdir -p "$HOME/.config/autostart"
        printf '[Desktop Entry]\nType=Application\nName=%s\nHidden=true\n' "$n" > "$ov"
        say "    − disabled via $ov"
    fi
done
for f in "$HOME"/.config/autostart/*.desktop; do
    [[ -f $f ]] || continue
    grep -q '^Hidden=true' "$f" && continue
    if grep -qiE 'nm-applet|nm-tray|networkmanager_dmenu|wi-?fi' "$f" && ! grep -qi 'genshin-wifi' "$f"; then
        say "    found: ${f/#$HOME/~}"
        if (( APPLY )); then mkdir -p "$BK"; cp -a -- "$f" "$BK"/; printf 'Hidden=true\n' >> "$f"; say "    − disabled (Hidden=true)"; fi
    fi
done

# ── 3. Hyprland / HyDE config lines (exec + keybinds) ──────────────────
say $'\n[3] Hyprland / HyDE config lines'
python3 - <<'PYEOF'
import os, re, shutil, glob
apply_ = os.environ["APPLY"] == "1"
bk = os.environ["BK"]
home = os.path.expanduser("~")
line_re = re.compile(r'^\s*(exec(-once)?|execr(-once)?|bind[a-z]*)\s*=', re.I)
bad = re.compile(r'nm-applet|network-manager-applet|nm-tray|networkmanager_dmenu|nmtui|nm-connection-editor|'
                 r'iwgtk|impala|rofi[^#\n]*wi-?fi|wi-?fi[-_ ]?(menu|manager|toggle|qr|select)|(menu|rofi)[-_ ]?wi-?fi', re.I)
keep = re.compile(r'genshin-wifi|celestia', re.I)
total = 0
for root in (os.path.join(home, ".config/hypr"), os.path.join(home, ".config/hyde")):
    for dp, dn, fn in os.walk(root):
        for name in fn:
            if not name.endswith(".conf") or ".bak" in name:
                continue
            p = os.path.join(dp, name)
            try:
                lines = open(p, encoding="utf-8").read().split("\n")
            except Exception:
                continue
            hits = [i for i, l in enumerate(lines)
                    if line_re.match(l) and bad.search(l) and not keep.search(l)]
            if not hits:
                continue
            for i in hits:
                total += 1
                print(f"    {p.replace(home, '~')}:{i+1}:  {lines[i].strip()[:110]}")
            if apply_:
                dst = os.path.join(bk, os.path.relpath(p, home))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(p, dst)
                for i in hits:
                    lines[i] = "# [celestia-cleanup] " + lines[i]
                open(p, "w", encoding="utf-8").write("\n".join(lines))
if total == 0:
    print("    none found")
elif apply_:
    print(f"    − {total} line(s) commented out (prefix '# [celestia-cleanup]')")
PYEOF

# ── 4. old Wi-Fi menu config in waybar-genshin ─────────────────────────
say $'\n[4] Old Wi-Fi menu leftovers'
D="$HOME/.config/waybar-genshin"
any=0
for f in "$D"/wifi-menu.conf "$D"/*wifi*.rasi "$D"/rofi/*wifi*; do
    [[ -e $f ]] || continue
    any=1; say "    found: ${f/#$HOME/~}"
    if (( APPLY )); then mkdir -p "$BK"; cp -a -- "$f" "$BK"/; rm -rf -- "$f"; say "    − moved to backup"; fi
done
(( any )) || say "    none"

# ── 5. report only (not auto-removed) ──────────────────────────────────
say $'\n[5] Report only — review by hand'
say "  Other Wi-Fi/network packages installed:"
pacman -Qq 2>/dev/null | grep -E '^(nm-tray|networkmanager_dmenu.*|iwgtk|impala|wifi-qr|rofi-wifi.*|nmtui|wlctl.*|network-manager-applet)$' \
    | while read -r pk; do
        if [[ $pk == network-manager-applet ]]; then say "    $pk   ← KEEP (ships nm-connection-editor used by Celestia; only its tray icon is disabled above)"
        else say "    $pk   → sudo pacman -Rns $pk"; fi
      done
say "  HyDE scripts/configs mentioning wifi/network menus:"
grep -rIlE 'nm-applet|networkmanager_dmenu|rofi.*wi-?fi|wifi.*(menu|rofi)' \
    "$HOME/.local/lib/hyde" "$HOME/.local/bin" "$HOME/.config/rofi" "$HOME/.config/waybar" "$HOME/.local/share/waybar" 2>/dev/null \
    | grep -v '\.bak' | sed "s|$HOME|~|;s|^|    |" | head -30

if (( APPLY )); then
    command -v hyprctl >/dev/null && hyprctl reload >/dev/null 2>&1 && say $'\n  ✓ Hyprland reloaded'
    say "  ✓ Done. Undo: copy files back from ${BK/#$HOME/~}"
else
    say $'\n  (dry run) Looks right? Run again with --apply.'
fi
