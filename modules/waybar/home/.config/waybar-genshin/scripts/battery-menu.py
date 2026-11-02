#!/usr/bin/env python3
import os, re, shutil, subprocess, sys
from xml.sax.saxutils import escape
from battery_info import info

HOME = os.path.expanduser("~")
LOG = open("/tmp/battery-menu.log", "a")

def notify(msg):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "Elemental Energy", msg])

if subprocess.run(["pgrep", "-x", "rofi"], capture_output=True).returncode == 0:
    subprocess.run(["pkill", "-x", "rofi"])
    sys.exit(0)

lines = [l.replace("  \u00b7  ", " \u00b7 ") for l in info()["lines"]]
LABELS = {"power-saver": "Power Saver", "balanced": "Balanced", "performance": "Performance"}
ORDER = ["power-saver", "balanced", "performance"]
entries, names, cur = [], [], None
if shutil.which("powerprofilesctl"):
    cur = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True).stdout.strip()
    out = subprocess.run(["powerprofilesctl", "list"], capture_output=True, text=True).stdout
    found = set(re.findall(r"^\s*\*?\s*([a-z-]+):", out, re.M))
    names = [n for n in ORDER if n in found]
    for n in names:
        entries.append(("\u25c6  " if n == cur else "\u25c7  ") + LABELS[n])
else:
    lines.append("Power modes: install power-profiles-daemon")
if not entries:
    entries = ["Close"]

# info goes in the standard rofi message box (not in the list), so up/down only touches the 3 modes
head = '<span foreground="#d3bc8e">\u2726  %s  \u2726</span>' % escape(lines[0])
rest = "\n".join(escape(l) for l in lines[1:])
mesg = head + ("\n" + rest if rest else "") + '\n<span size="x-small"> </span>'

row = names.index(cur) if cur in names else 0
cmd = ["rofi", "-dmenu", "-i", "-no-custom", "-format", "i",
       "-p", "Elemental Energy", "-mesg", mesg,
       "-theme", HOME + "/.config/waybar-genshin/battery-menu.rasi",
       "-theme-str", "listview {lines: %d;}" % len(entries),
       "-selected-row", str(row),
       "-hover-select", "-me-select-entry", "", "-me-accept-entry", "MousePrimary"]
res = subprocess.run(cmd, input="\n".join(entries), capture_output=True, text=True)
sel = res.stdout.strip()
LOG.write("rofi rc=%s sel=%r err=%r\n" % (res.returncode, sel, res.stderr.strip()))

if sel.isdigit() and int(sel) < len(names):
    n = names[int(sel)]
    if n == cur:
        notify("Already in %s mode" % LABELS[n])
    else:
        r = subprocess.run(["powerprofilesctl", "set", n], capture_output=True, text=True)
        now = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True).stdout.strip()
        LOG.write("set %s rc=%s err=%r now=%r\n" % (n, r.returncode, r.stderr.strip(), now))
        if now == n:
            notify("Power mode: " + LABELS[n])
        else:
            notify("Could not switch to %s: %s (still %s)" % (LABELS[n], r.stderr.strip() or "no error text", now))
LOG.close()
