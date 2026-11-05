#!/usr/bin/env bash
# Read-only health check of the installed Genshin setup.
fails=0
ok(){ printf '  ok    %s\n' "$1"; }
bad(){ printf '  FAIL  %s\n' "$1"; fails=$((fails+1)); }
chk(){ if [ -e "$1" ]; then ok "$1"; else bad "missing: $1"; fi; }

echo "== files referenced by hypr configs =="
for p in $(grep -hoE '(~|\$HOME|/home/[a-z0-9_-]+)/\.config/[A-Za-z0-9_./-]*genshin[A-Za-z0-9_./-]*' ~/.config/hypr/*.lua ~/.config/hypr/*.conf 2>/dev/null | sort -u); do
  q=${p/#\~/$HOME}; q=${q/#\$HOME/$HOME}; chk "$q"
done
echo "== scripts: executable + syntax =="
while IFS= read -r f; do
  [ -x "$f" ] || bad "not executable: $f"
  bash -n "$f" 2>/dev/null || bad "syntax error: $f"
done < <(find ~/.config/*-genshin -name '*.sh' -not -path '*/cache/*' 2>/dev/null)
echo "== placeholders =="
n=$(grep -rIl '@HOME@' ~/.config/*-genshin ~/.config/waybar/genshin-assets ~/.config/hypr 2>/dev/null | wc -l)
[ "$n" = 0 ] && ok "no @HOME@ left" || bad "$n files still contain @HOME@"
echo "== cursor =="
chk ~/.local/share/icons/Genshin-Official/cursors/left_ptr
grep -q 'Genshin-Official' ~/.config/gtk-3.0/settings.ini 2>/dev/null && ok "gtk3 cursor" || bad "gtk3 cursor is not Genshin-Official"
grep -q "Genshin-Official" ~/.local/share/hyde/env-theme 2>/dev/null && ok "hyde env-theme cursor" || bad "hyde env-theme cursor is not Genshin-Official"
[ "${XCURSOR_THEME:-}" = Genshin-Official ] && ok "XCURSOR_THEME" || bad "XCURSOR_THEME=${XCURSOR_THEME:-unset}"
echo "== fonts =="
fc-list 2>/dev/null | grep -qi genshin && ok "genshin font visible to fontconfig" || bad "genshin font not found by fc-list"
echo "== login / boot =="
th=$(grep -rhE '^Current=' /etc/sddm.conf.d 2>/dev/null | tail -1 | cut -d= -f2)
[ -n "$th" ] && [ -d "/usr/share/sddm/themes/$th" ] && ok "sddm theme: $th" || bad "sddm theme missing (Current=${th:-none})"
[ "$(plymouth-set-default-theme 2>/dev/null)" = genshin-loading ] && ok "plymouth: genshin-loading" || bad "plymouth theme is not genshin-loading"
grep -rEhs '^HOOKS' /etc/mkinitcpio.conf /etc/mkinitcpio.conf.d 2>/dev/null | grep -q genshin-daynight && ok "HOOKS has genshin-daynight" || bad "genshin-daynight not in HOOKS"
chk /usr/lib/initcpio/hooks/genshin-daynight
chk /usr/lib/genshin-daynight/pick.sh
chk /etc/genshin-daynight.conf
echo "== running =="
{ pgrep -x waybar.orig >/dev/null || pgrep -x waybar >/dev/null; } && ok waybar || bad "waybar not running"
command -v qs >/dev/null 2>&1 && ok quickshell || bad "quickshell not installed (needed by the weather popup)"
systemctl --user is-enabled teyvat-forecast-fetch.timer >/dev/null 2>&1 && ok forecast-timer || bad "weather refresh timer not enabled"
pgrep -x dunst >/dev/null && ok dunst || bad "dunst not running"
echo; if [ "$fails" = 0 ]; then echo "ALL GOOD"; else echo "$fails problem(s)"; fi
exit "$fails"
