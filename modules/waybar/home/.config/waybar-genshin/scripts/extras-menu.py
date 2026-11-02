#!/usr/bin/env python3
import json, os, re, shutil, subprocess, sys
from xml.sax.saxutils import escape
from jsonc_load import load

HOME = os.path.expanduser("~")
WB = HOME + "/.config/waybar-genshin"
LOG = open("/tmp/extras-menu.log", "a")

def notify(msg):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "Extras", msg])

if subprocess.run(["pgrep", "-x", "rofi"], capture_output=True).returncode == 0:
    subprocess.run(["pkill", "-x", "rofi"])
    sys.exit(0)

try:
    cfg = load(WB + "/config.jsonc")
except Exception as e:
    LOG.write("config load failed: %r\n" % (e,))
    cfg = {}

TAG = re.compile(r"<[^>]+>")

def run_text(key):
    ex = (cfg.get(key) or {}).get("exec")
    if not ex:
        return ""
    try:
        r = subprocess.run(ex, shell=True, capture_output=True, text=True, timeout=5)
    except Exception:
        return ""
    for ln in r.stdout.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
            t = d.get("text", "") if isinstance(d, dict) else ln
        except Exception:
            t = ln
        return TAG.sub("", str(t)).strip().splitlines()[0] if str(t).strip() else ""
    return ""

ar = run_text("custom/ar") or "AR"
items = []
for key, label in (("custom/handbook", "Adventurer's Handbook"), ("custom/mail", "Mail")):
    m = cfg.get(key) or {}
    txt = run_text(key) if key == "custom/mail" else ""
    if txt:
        label += "   \u00b7 " + txt
    items.append((label, m.get("on-click")))

entries = ["\u25c7  " + l for l, _ in items]
head = '<span foreground="#d3bc8e">\u2726  %s  \u2726</span>' % escape(ar)
mesg = head + '\n<span size="x-small"> </span>'

cmd = ["rofi", "-dmenu", "-i", "-no-custom", "-format", "i",
       "-p", "Extras", "-mesg", mesg,
       "-theme", WB + "/extras-menu.rasi",
       "-theme-str", "listview {lines: %d;}" % len(entries),
       "-selected-row", "0",
       "-hover-select", "-me-select-entry", "", "-me-accept-entry", "MousePrimary"]
res = subprocess.run(cmd, input="\n".join(entries), capture_output=True, text=True)
sel = res.stdout.strip()
LOG.write("rofi rc=%s sel=%r err=%r\n" % (res.returncode, sel, res.stderr.strip()))

if sel.isdigit() and int(sel) < len(items):
    act = items[int(sel)][1]
    if act:
        subprocess.Popen(act, shell=True, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        notify("No action set for this item")
LOG.close()
