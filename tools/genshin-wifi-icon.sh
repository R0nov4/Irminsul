#!/usr/bin/env bash
# ✦ Genshin top-bar Wi-Fi icon — replaces the plain font glyph of the waybar "network" module
#   with Genshin-style SVG icons (wifi / ethernet / off) and a pill that matches the battery pill.
#   Safe to re-run. Backups: config.jsonc.bak-wifiicon, style.css.bak-wifiicon

set -u
D="$HOME/.config/waybar-genshin"
[[ -d $D ]] || { printf 'Folder %s not found.\n' "$D" >&2; exit 1; }
[[ -f $D/config.jsonc && -f $D/style.css ]] || { printf 'config.jsonc / style.css missing in %s\n' "$D" >&2; exit 1; }

mkdir -p "$D/assets/wifi"

cat > "$D/assets/wifi/wifi.svg" <<'SVG_WIFI'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f7ecc6"/>
      <stop offset="1" stop-color="#d3bc8e"/>
    </linearGradient>
  </defs>
  <g fill="none" stroke="url(#g)" stroke-width="2.1" stroke-linecap="round">
    <path d="M1.9 8.1 A15 15 0 0 1 22.1 8.1"/>
    <path d="M5.2 11.6 A10 10 0 0 1 18.8 11.6"/>
    <path d="M8.5 15.1 A5 5 0 0 1 15.5 15.1"/>
  </g>
  <path d="M12 15.9 Q12.45 18.05 14.6 18.5 Q12.45 18.95 12 21.1 Q11.55 18.95 9.4 18.5 Q11.55 18.05 12 15.9 Z" fill="#74c2a8"/>
</svg>
SVG_WIFI

cat > "$D/assets/wifi/ethernet.svg" <<'SVG_ETH'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f7ecc6"/>
      <stop offset="1" stop-color="#d3bc8e"/>
    </linearGradient>
  </defs>
  <g fill="none" stroke="url(#g)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="8.5" y="3" width="7" height="5.5" rx="1.6"/>
    <path d="M12 8.5 V12.5 M5 15.5 V12.5 H19 V15.5"/>
    <rect x="1.8" y="15.5" width="6.4" height="5.5" rx="1.6"/>
    <rect x="15.8" y="15.5" width="6.4" height="5.5" rx="1.6"/>
  </g>
  <path d="M12 3.9 Q12.3 5.4 13.8 5.75 Q12.3 6.1 12 7.6 Q11.7 6.1 10.2 5.75 Q11.7 5.4 12 3.9 Z" fill="#74c2a8"/>
</svg>
SVG_ETH

cat > "$D/assets/wifi/off.svg" <<'SVG_OFF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <g fill="none" stroke="#8e95a6" stroke-opacity="0.65" stroke-width="2.1" stroke-linecap="round">
    <path d="M1.9 8.1 A15 15 0 0 1 22.1 8.1"/>
    <path d="M5.2 11.6 A10 10 0 0 1 18.8 11.6"/>
    <path d="M8.5 15.1 A5 5 0 0 1 15.5 15.1"/>
  </g>
  <path d="M12 15.9 Q12.45 18.05 14.6 18.5 Q12.45 18.95 12 21.1 Q11.55 18.95 9.4 18.5 Q11.55 18.05 12 15.9 Z" fill="#8e95a6" fill-opacity="0.65"/>
  <path d="M3.5 3.5 L20.5 21" stroke="#18202b" stroke-width="4.6" stroke-linecap="round"/>
  <path d="M3.5 3.5 L20.5 21" stroke="#ff6b6b" stroke-width="2.1" stroke-linecap="round" fill="none"/>
</svg>
SVG_OFF

[[ -f $D/config.jsonc.bak-wifiicon ]] || cp -f "$D/config.jsonc" "$D/config.jsonc.bak-wifiicon"
[[ -f $D/style.css.bak-wifiicon ]]    || cp -f "$D/style.css"    "$D/style.css.bak-wifiicon"

python3 - "$D" <<'PYEOF'
import re, sys, os
D = sys.argv[1]

# ── config.jsonc: network module shows an empty (space) label, the icon comes from CSS ──
p = os.path.join(D, "config.jsonc")
s = open(p, encoding="utf-8").read()
m = re.search(r'"network"\s*:\s*\{', s)
if not m:
    sys.exit("no \"network\" module found in config.jsonc — nothing changed")

def block_end(s, i):
    depth, instr, j = 1, False, i
    while depth and j < len(s):
        c = s[j]
        if instr:
            if c == "\\":
                j += 1
            elif c == '"':
                instr = False
        elif c == '"':
            instr = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        j += 1
    return j

i = m.end()
j = block_end(s, i)
blk = s[i:j - 1]
keys = ("format", "format-wifi", "format-ethernet", "format-disconnected", "format-linked", "format-disabled")
for k in keys:
    blk = re.sub(r'\n[ \t]*"' + re.escape(k) + r'"\s*:\s*"(?:[^"\\]|\\.)*"\s*,?[ \t]*(?=\n)', "", blk)
blk = re.sub(r',(\s*)$', r'\1', blk)          # no dangling comma if the last key was removed
new = "".join('\n        "%s": " ",' % k for k in keys)
if '"' not in blk:                              # block had nothing else -> no trailing comma
    new = new.rstrip(",")
blk = new + blk
s = s[:i] + blk + s[j - 1:]
open(p, "w", encoding="utf-8").write(s)
print("    ✓ network module: icon label emptied")

# ── style.css: replace our block (or append it) ──
p = os.path.join(D, "style.css")
css = open(p, encoding="utf-8").read()
A = os.path.join(D, "assets", "wifi")
block = f"""/* >>> genshin-wifi-icon >>> */
window#waybar #network {{
    color: transparent;
    font-size: 1px;
    min-width: 40px;
    padding: 0;
    margin: 3px 1px;
    background-color: rgba(18, 22, 30, 0.92);
    border: 1.5px solid rgba(211, 188, 142, 0.75);
    border-radius: 18px;
    background-repeat: no-repeat;
    background-position: center;
    background-size: 20px 20px;
    background-image: url("{A}/wifi.svg");
    transition: background-color 200ms ease, border-color 200ms ease;
}}
window#waybar #network.ethernet {{ background-image: url("{A}/ethernet.svg"); }}
window#waybar #network.disconnected,
window#waybar #network.disabled {{
    background-image: url("{A}/off.svg");
    border-color: rgba(211, 188, 142, 0.40);
}}
window#waybar #network.linked {{ opacity: 0.7; }}
window#waybar #network:hover {{
    background-color: rgba(211, 188, 142, 0.25);
    border-color: #ffffff;
}}
/* <<< genshin-wifi-icon <<< */
"""
pat = re.compile(r'/\* >>> genshin-wifi-icon >>> \*/.*?/\* <<< genshin-wifi-icon <<< \*/\n?', re.S)
css = pat.sub("", css).rstrip("\n") + "\n\n\n" + block
open(p, "w", encoding="utf-8").write(css)
print("    ✓ style.css: Genshin wifi pill written")
PYEOF
rc=$?
if [[ $rc -ne 0 ]]; then
    echo "Patch failed — restoring backups." >&2
    cp -f "$D/config.jsonc.bak-wifiicon" "$D/config.jsonc"
    cp -f "$D/style.css.bak-wifiicon" "$D/style.css"
    exit $rc
fi

if [[ -x $D/start.sh ]]; then
    killall waybar.orig 2>/dev/null || true
    setsid "$D/start.sh" >/dev/null 2>&1 &
elif pgrep -x waybar >/dev/null; then
    pkill -USR2 -x waybar 2>/dev/null || true
fi

echo
echo "  ✦ Genshin Wi-Fi icon installed. To undo:"
echo "      cp $D/config.jsonc.bak-wifiicon $D/config.jsonc"
echo "      cp $D/style.css.bak-wifiicon $D/style.css"
