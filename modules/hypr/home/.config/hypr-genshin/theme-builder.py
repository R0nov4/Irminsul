#!/usr/bin/env python3
# Genshin Theme Builder v3 (GTK3) - replaces the rofi menu of v2.
# Same storage as v2: theme = sub-folder of the wallpapers dir, accent in <folder>/.theme
import atexit
import filecmp
import hashlib
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

HOME = os.path.expanduser("~")
CFG = os.path.join(HOME, ".config/hypr-genshin")
CACHE = os.path.join(HOME, ".cache/genshin-theme")
THUMBS = os.path.join(CACHE, "thumbs")
WSTATE = os.path.join(HOME, ".cache/hypr-genshin")
TRASH = os.path.join(WSTATE, "trash")
WSH = os.path.join(CFG, "wallpaper.sh")
WCONF = os.path.join(CFG, "wallpaper.conf")
CUR_FILE = os.path.join(WSTATE, "current")
COLL_FILE = os.path.join(WSTATE, "collection")
PIDFILE = os.path.join(WSTATE, "theme-builder.pid")
# GP_FOLLOW: admin (polkit) window follows the theme accent
POLKIT_AGENT = os.path.join(HOME, ".local/lib/genshin-polkit/agent.py")
POLKIT_FOLLOW = os.path.join(HOME, ".config/genshin-polkit/follow")

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"}
DEFAULT = ("d3bc8e", "f4e8c1", "8a7550")
PRESETS = [
    ("Celestia", "d3bc8e", "f4e8c1", "8a7550"),
    ("Pyro", "ff6b4a", "ffb4a2", "8c2a1a"),
    ("Hydro", "48cae4", "ade8f4", "12607a"),
    ("Electro", "b565f2", "e0aaff", "5a2a8a"),
    ("Dendro", "57cc99", "b7efc5", "2a6b4a"),
    ("Cryo", "90e0ef", "caf0f8", "4a8a9a"),
    ("Geo", "f4b942", "ffe6a7", "8a6420"),
    ("Abyssal", "e63956", "ff8fa3", "6b0f22"),
]
AUTO_CHOICES = [
    ("off", "Off"),
    ("15", "Every 15 min"),
    ("30", "Every 30 min"),
    ("60", "Every hour"),
    ("daily", "Daily at 4 AM"),
    ("daynight", "Day & Night"),
]

POOL = ThreadPoolExecutor(max_workers=4)   # thumbnails
POOL2 = ThreadPoolExecutor(max_workers=2)  # shell / file work
PAL = {}
ACC = {"base": (0.83, 0.74, 0.56), "hi": (0.96, 0.91, 0.76)}


# ───────────────────────────── small helpers ─────────────────────────────
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def hex_trio(h):
    h = h.lstrip("#").lower()
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (
        f"{r:02x}{g:02x}{b:02x}",
        f"{r + (255 - r) * 45 // 100:02x}{g + (255 - g) * 45 // 100:02x}{b + (255 - b) * 45 // 100:02x}",
        f"{r * 55 // 100:02x}{g * 55 // 100:02x}{b * 55 // 100:02x}",
    )


def natkey(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def pretty(s):
    return s.replace("_", " ")


def slugify(s):
    s = re.sub(r"[/\\.]", "", s).strip()
    return re.sub(r"\s+", "_", s)


def is_img(name):
    return not name.startswith(".") and os.path.splitext(name)[1].lower() in IMG_EXT


def list_images(d, maxdepth=3):
    out = []
    d = d.rstrip("/")
    for root, dirs, files in os.walk(d, followlinks=True):
        depth = 0 if root == d else root[len(d):].count(os.sep)
        for f in files:
            if is_img(f):
                out.append(os.path.join(root, f))
        if depth + 1 >= maxdepth:
            dirs[:] = []
    out.sort(key=natkey)
    return out


def read_file(p, default=""):
    try:
        with open(p) as fh:
            return fh.read().strip()
    except OSError:
        return default


def write_file(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)


def sh(script, *args):
    try:
        return subprocess.run(["bash", "-c", script, "_", *args], capture_output=True, text=True, timeout=90)
    except Exception:
        class R:
            stdout = ""
            returncode = 1
        return R()


def lib(script, *args):
    return sh('. "$HOME/.config/hypr-genshin/resonance-lib.sh" 2>/dev/null || exit 1\n' + script, *args)


def wall_dir():
    d = lib("res_wall_dir").stdout.strip()
    return d or os.path.join(CFG, "wallpapers")


def active_theme():
    return read_file(COLL_FILE, "all") or "all"


def notify(title, body=""):
    try:
        subprocess.Popen(["notify-send", "-a", "Paimon", title, body],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def palette(img):
    if img in PAL:
        return PAL[img]
    out = []
    for line in lib('palette_of "$1"', img).stdout.splitlines():
        p = line.split()
        if len(p) >= 4 and all(re.fullmatch(r"[0-9a-f]{6}", x) for x in p[:3]):
            out.append((p[0], p[1], p[2], " ".join(p[3:])))
    PAL[img] = out
    return out


def read_theme(d):
    out = {}
    try:
        with open(os.path.join(d, ".theme")) as fh:
            for line in fh:
                m = re.match(r'^(\w+)="(.*)"\s*$', line)
                if m:
                    out[m.group(1)] = m.group(2)
    except OSError:
        pass
    return out


def write_theme(d, fixed=None):
    with open(os.path.join(d, ".theme"), "w") as fh:
        if not fixed:
            fh.write('ACCENT="auto"\n')
        else:
            n, b, h, l = fixed
            fh.write(f'ACCENT="fixed"\nNAME="{n}"\nBASE="{b}"\nHI="{h}"\nLO="{l}"\n')


def accent_of(d):
    t = read_theme(d)
    if t.get("ACCENT") == "fixed" and all(k in t for k in ("NAME", "BASE", "HI", "LO")):
        return (t["NAME"], t["BASE"], t["HI"], t["LO"])
    return None


def unique_path(d, name):
    stem, ext = os.path.splitext(name)
    t, i = os.path.join(d, name), 1
    while os.path.exists(t):
        t = os.path.join(d, f"{stem}_{i}{ext}")
        i += 1
    return t


def copy_unique(src, destdir):
    b = os.path.basename(src)
    stem, ext = os.path.splitext(b)
    t, i = os.path.join(destdir, b), 1
    while os.path.exists(t):
        try:
            if filecmp.cmp(src, t, shallow=False):
                return 0
        except OSError:
            pass
        t = os.path.join(destdir, f"{stem}_{i}{ext}")
        i += 1
    shutil.copy2(src, t)
    return 1


def import_into(src, dest):
    os.makedirs(dest, exist_ok=True)
    n = 0
    if os.path.isdir(src):
        for f in list_images(src):
            n += copy_unique(f, dest)
    elif os.path.isfile(src) and is_img(os.path.basename(src)):
        n += copy_unique(src, dest)
    return n


def read_conf():
    txt = read_file(WCONF)
    mode = re.search(r'^AUTO_MODE="?([^"\n]*)"?', txt, re.M)
    mins = re.search(r"^ROTATE_MINUTES=(\d+)", txt, re.M)
    return (mode.group(1) if mode else "off"), (mins.group(1) if mins else "")


def set_conf(key, val):
    try:
        lines = open(WCONF).read().splitlines()
    except OSError:
        lines = []
    for i, line in enumerate(lines):
        if line.startswith(key + "="):
            lines[i] = f"{key}={val}"
            break
    else:
        lines.append(f"{key}={val}")
    write_file(WCONF, "\n".join(lines) + "\n")


def polkit_installed():
    return os.path.exists(POLKIT_AGENT)


def polkit_mode():  # GP_FOLLOW_V2
    try:
        with open(POLKIT_FOLLOW) as fh:
            v = fh.read().strip().lower()
    except OSError:
        return "theme"
    if v in ("gold", "genshin"):
        return "gold"
    if v in ("classic", "off", "0", "no", "false"):
        return "classic"
    return "theme"


def set_polkit_mode(mode):
    os.makedirs(os.path.dirname(POLKIT_FOLLOW), exist_ok=True)
    write_file(POLKIT_FOLLOW, mode + "\n")


PIXCACHE = {}


def cover_thumb(path, w, h):
    k = (path, w, h)
    pb = PIXCACHE.get(k)
    if pb is None:
        pb = _cover_thumb(path, w, h)
        if len(PIXCACHE) > 1500:
            PIXCACHE.clear()
        PIXCACHE[k] = pb
    return pb


def _cover_thumb(path, w, h):
    try:
        mt = int(os.stat(path).st_mtime)
    except OSError:
        mt = 0
    key = hashlib.md5(f"{path}|{w}x{h}|{mt}".encode()).hexdigest()[:20]
    cp = os.path.join(THUMBS, f"tb3-{key}.jpg")
    try:
        if os.path.exists(cp):
            return GdkPixbuf.Pixbuf.new_from_file(cp)
    except GLib.Error:
        pass
    try:
        box = max(w, h) * 2
        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, box, box)
        pw, ph = pb.get_width(), pb.get_height()
        s = max(w / pw, h / ph)
        nw, nh = max(w, math.ceil(pw * s)), max(h, math.ceil(ph * s))
        pb = pb.scale_simple(nw, nh, GdkPixbuf.InterpType.BILINEAR)
        pb = pb.new_subpixbuf((nw - w) // 2, (nh - h) // 2, w, h).copy()
        try:
            os.makedirs(THUMBS, exist_ok=True)
            pb.savev(cp, "jpeg", ["quality"], ["88"])
        except GLib.Error:
            pass
        return pb
    except Exception:
        im = shutil.which("magick") or shutil.which("convert")
        if im:
            try:
                os.makedirs(THUMBS, exist_ok=True)
                subprocess.run([im, f"{path}[0]", "-auto-orient", "-thumbnail", f"{w}x{h}^", "-gravity", "center",
                                "-extent", f"{w}x{h}", "-quality", "88", cp], capture_output=True, timeout=40)
                return GdkPixbuf.Pixbuf.new_from_file(cp)
            except Exception:
                pass
        pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h)
        pb.fill(0x3D4559FF)
        return pb


def rrect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def trash_theme(wall, name):
    src = os.path.join(wall, name)
    dest_dir = os.path.join(TRASH, "themes")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{name}-{int(time.time())}")
    try:
        shutil.move(src, dest)
    except (OSError, shutil.Error):
        return False
    return not os.path.exists(src)


# ───────────────────────────── custom widgets ─────────────────────────────
class Thumb(Gtk.DrawingArea):
    """Image with rounded corners (cover-cropped pixbuf is prepared by cover_thumb)."""

    def __init__(self, w, h, radius=10):
        super().__init__()
        self.w, self.h, self.r, self.pb = w, h, radius, None
        self.set_size_request(w, h)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.connect("draw", self.on_draw)

    def set_pixbuf(self, pb):
        self.pb = None
        try:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w, self.h)
            c = cairo.Context(surf)
            rrect(c, 0, 0, self.w, self.h, self.r)
            c.clip()
            Gdk.cairo_set_source_pixbuf(c, pb, 0, 0)
            c.paint()
            self.surf = surf
        except Exception:
            self.surf = None
        self.queue_draw()
        return False

    def on_draw(self, _w, cr):
        s = getattr(self, "surf", None)
        if s is not None:
            cr.set_source_surface(s, 0, 0)
            cr.paint()
        else:
            rrect(cr, 0, 0, self.w, self.h, self.r)
            cr.set_source_rgb(0.24, 0.27, 0.35)
            cr.fill()
        return False


class Ornament(Gtk.DrawingArea):
    """Thin gold divider with a diamond in the middle (the Genshin menu flourish)."""

    def __init__(self, h=18):
        super().__init__()
        self.set_size_request(-1, h)
        self.connect("draw", self.on_draw)

    def on_draw(self, _w, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        cy, cx = h / 2, w / 2
        gap = 34
        br, bg, bb = ACC["base"]
        hr, hg, hb = ACC["hi"]
        for side in (-1, 1):
            x0 = cx + side * gap
            x1 = cx + side * (w / 2 - 6)
            g = cairo.LinearGradient(x0, 0, x1, 0)
            g.add_color_stop_rgba(0, br, bg, bb, 0.95)
            g.add_color_stop_rgba(1, br, bg, bb, 0.0)
            cr.set_source(g)
            cr.set_line_width(1.2)
            cr.move_to(x0, cy)
            cr.line_to(x1, cy)
            cr.stroke()

        def dia(x, r, fill=True):
            cr.move_to(x, cy - r)
            cr.line_to(x + r, cy)
            cr.line_to(x, cy + r)
            cr.line_to(x - r, cy)
            cr.close_path()
            if fill:
                cr.fill()
            else:
                cr.stroke()

        cr.set_source_rgb(hr, hg, hb)
        dia(cx, 6)
        cr.set_source_rgba(br, bg, bb, 0.9)
        cr.set_line_width(1.2)
        dia(cx, 10, fill=False)
        cr.set_source_rgb(br, bg, bb)
        dia(cx - 22, 3)
        dia(cx + 22, 3)
        return False


class Chip(Gtk.DrawingArea):
    """Diamond-shaped accent swatch."""

    def __init__(self, kind, name, base="", hi="", lo="", size=38, on_click=None):
        super().__init__()
        self.kind, self.name = kind, name
        self.base, self.hi, self.lo = base, hi, lo
        self.size, self.selected, self.hover = size, False, False
        self.on_click = on_click
        self.set_size_request(size, size)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.CENTER)
        self.set_tooltip_text(name)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.connect("enter-notify-event", self.on_hover, True)
        self.connect("leave-notify-event", self.on_hover, False)

    def on_press(self, *_a):
        if self.on_click:
            self.on_click(self)
        return True

    def on_hover(self, _w, _e, state):
        self.hover = state
        self.queue_draw()
        return False

    def set_selected(self, v):
        self.selected = v
        self.queue_draw()

    def on_draw(self, _w, cr):
        s = self.size
        cx = cy = s / 2
        d = s / 2 - 5

        def diamond(r):
            cr.move_to(cx, cy - r)
            cr.line_to(cx + r, cy)
            cr.line_to(cx, cy + r)
            cr.line_to(cx - r, cy)
            cr.close_path()

        if self.selected:
            diamond(d + 3)
            cr.set_source_rgba(*ACC["hi"], 0.35)
            cr.set_line_width(5)
            cr.stroke()
        diamond(d)
        if self.kind in ("fix", "pal"):
            g = cairo.LinearGradient(cx - d, cy - d, cx + d, cy + d)
            g.add_color_stop_rgb(0, *rgb(self.hi))
            g.add_color_stop_rgb(1, *rgb(self.lo))
            cr.set_source(g)
        else:
            cr.set_source_rgb(0.15, 0.18, 0.25)
        cr.fill_preserve()
        if self.selected:
            cr.set_source_rgb(*ACC["hi"])
            cr.set_line_width(2.2)
        elif self.hover:
            cr.set_source_rgba(0.93, 0.9, 0.85, 0.9)
            cr.set_line_width(1.6)
        else:
            cr.set_source_rgba(*ACC["base"], 0.55)
            cr.set_line_width(1.1)
        cr.stroke()
        cr.set_source_rgb(*ACC["hi"])
        if self.kind == "auto":
            pts = []
            for i in range(8):
                rr = d * (0.62 if i % 2 == 0 else 0.16)
                a = -math.pi / 2 + i * math.pi / 4
                pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
            cr.move_to(*pts[0])
            for p in pts[1:]:
                cr.line_to(*p)
            cr.close_path()
            cr.fill()
        elif self.kind == "custom":
            cr.set_line_width(2)
            cr.move_to(cx - d * 0.38, cy)
            cr.line_to(cx + d * 0.38, cy)
            cr.move_to(cx, cy - d * 0.38)
            cr.line_to(cx, cy + d * 0.38)
            cr.stroke()
        return False


# ───────────────────────────── stylesheet ─────────────────────────────
CSS_BODY = r"""
window.gt, window.gd { background-color: transparent; }

.mainframe {
  background-image: linear-gradient(to bottom, #3b4358, #2a3041);
  border: 2px solid @gold;
  border-radius: 22px;
}
.mainframe label { color: @cream; }
.mainframe *:focus { outline-style: none; outline-color: transparent; }

label.spark { color: @gold; font-size: 16px; }
label.title { color: @gold_hi; font-size: 24px; font-weight: bold; letter-spacing: 4px; }
label.subtitle { color: alpha(@cream, 0.6); font-size: 12px; }
label.dname { color: @gold_hi; font-size: 22px; font-weight: bold; }
label.muted { color: alpha(@cream, 0.62); font-size: 12px; }
label.section { color: @gold; font-size: 12px; font-weight: bold; letter-spacing: 2px; }
label.status { color: @gold_hi; font-size: 12px; }
label.tag { background-color: @gold; color: @ink; border-radius: 999px; padding: 0px 9px; font-size: 11px; font-weight: bold; }
label.bigmsg { color: @cream; font-size: 17px; font-weight: bold; }

.sidebar { background-color: alpha(#1c2130, 0.5); border-radius: 18px; padding: 12px; }
.themes, .themes row { background-color: transparent; }
.themes row { border-radius: 14px; padding: 7px 9px; margin: 2px 0px; border: 2px solid transparent; }
.themes row:hover { background-color: alpha(@cream, 0.08); }
.themes row:selected { background-color: @cream; border-color: @gold; }
.themes row label.row-name { color: @cream; font-size: 14px; font-weight: bold; }
.themes row label.row-sub { color: alpha(@cream, 0.6); font-size: 11px; }
.themes row:selected label.row-name { color: @ink; }
.themes row:selected label.row-sub { color: alpha(@ink, 0.75); }

scrolledwindow, viewport, flowbox, flowboxchild { background-color: transparent; }
flowboxchild { padding: 3px; }
scrollbar { background-color: transparent; }
scrollbar trough { background-color: alpha(#ffffff, 0.06); border-radius: 6px; min-width: 6px; }
scrollbar slider { background-color: @gold; border-radius: 6px; min-width: 6px; min-height: 30px; border: none; }

button.pill {
  background-image: none; background-color: @cream; box-shadow: none; text-shadow: none;
  border: 2px solid transparent; border-radius: 999px; padding: 8px 22px;
}
button.pill label { color: @ink; font-weight: bold; }
button.pill:hover { background-color: #fff6e0; border-color: @gold; box-shadow: 0 0 12px alpha(@gold, 0.55); }
button.pill:disabled { opacity: 0.4; }
button.pill.big { padding: 11px 38px; font-size: 15px; }

button.ghost {
  background-image: none; background-color: alpha(#ffffff, 0.05); box-shadow: none; text-shadow: none;
  border: 1px solid alpha(@cream, 0.3); border-radius: 999px; padding: 5px 15px;
}
button.ghost label { color: @cream; }
button.ghost:hover { border-color: @gold; background-color: alpha(@gold, 0.14); }
button.ghost:hover label { color: @gold_hi; }
button.ghost:disabled { opacity: 0.35; }
button.ghost.danger:hover { border-color: #ff8fa3; background-color: alpha(#ff8fa3, 0.14); }
button.ghost.danger:hover label { color: #ff8fa3; }
button.ghost.on { background-color: @cream; border-color: @gold; }
button.ghost.on label { color: @ink; font-weight: bold; }
button.close { padding: 2px 11px; }

.card { background-color: #3d4559; border: 2px solid transparent; border-radius: 15px; }
.card:hover { border-color: alpha(@gold, 0.6); }
.card.sel { background-color: @cream; border-color: @gold; }
.card label.cname { color: alpha(@cream, 0.85); font-size: 11px; }
.card.sel label.cname { color: @ink; }
label.badge { background-color: @gold; color: @ink; border-radius: 999px; min-width: 18px; min-height: 18px; margin: 3px; font-size: 10px; font-weight: bold; }
label.check { background-color: @gold; color: @ink; border-radius: 999px; min-width: 24px; min-height: 24px; margin: 7px; font-weight: bold; }

.empty { border: 2px dashed alpha(@gold, 0.5); border-radius: 18px; background-color: alpha(#1c2130, 0.35); }
.dropping { border: 2px dashed @gold; border-radius: 18px; background-color: alpha(@gold, 0.1); }
.footer { border-top: 1px solid alpha(@gold, 0.35); }

.gframe { background-color: #2f3647; border: 2px solid @gold; border-radius: 20px; padding: 22px 26px; }
.gframe label { color: @cream; }
entry.gentry {
  background-image: none; background-color: #1f2431; color: @cream; caret-color: @gold;
  border: 1px solid alpha(@cream, 0.3); border-radius: 12px; padding: 9px 14px; box-shadow: none;
}
entry.gentry:focus { border-color: @gold; }
.trashrow { background-color: alpha(#ffffff, 0.05); border-radius: 12px; padding: 8px 12px; }
"""


def build_css(base, hi, lo):
    head = (f"@define-color gold #{base};\n@define-color gold_hi #{hi};\n@define-color gold_lo #{lo};\n"
            "@define-color cream #ece5d8;\n@define-color ink #3b4255;\n")
    return head + CSS_BODY


def lbl(text="", cls=None, xalign=None, ellipsize=False):
    w = Gtk.Label(label=text)
    if cls:
        w.get_style_context().add_class(cls)
    if xalign is not None:
        w.set_xalign(xalign)
    if ellipsize:
        w.set_ellipsize(Pango.EllipsizeMode.END)
    return w


def btn(text, cls, cb=None):
    b = Gtk.Button(label=text)
    for c in cls.split():
        b.get_style_context().add_class(c)
    if cb:
        b.connect("clicked", lambda *_: cb())
    return b


def hbox(spacing=8):
    return Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)


def vbox(spacing=8):
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)


# ───────────────────────────── application ─────────────────────────────
class App:
    CARD_W, CARD_H = 172, 97

    def __init__(self):
        self.wall = wall_dir()
        os.makedirs(self.wall, exist_ok=True)
        os.makedirs(THUMBS, exist_ok=True)
        self.gen = 0
        self.theme = None
        self.sel = set()
        self.last_idx = None
        self.cards, self.order, self.info, self.rows, self.chips = {}, [], {}, {}, []
        self._building = False
        self._status_id = 0
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.set_accent(*DEFAULT)
        self.build_window()
        self.win.show_all()
        self.refresh_sidebar(active_theme() if os.path.isdir(os.path.join(self.wall, active_theme())) else "all",
                             show=True)

    # ── accent / css ──
    def set_accent(self, base, hi, lo):
        if getattr(self, "_acc_cur", None) == (base, hi, lo):
            return
        self._acc_cur = (base, hi, lo)
        ACC["base"], ACC["hi"] = rgb(base), rgb(hi)
        try:
            self.css.load_from_data(build_css(base, hi, lo).encode())
        except GLib.Error as e:
            print("CSS error:", e, file=sys.stderr)
        if hasattr(self, "win"):
            self.win.queue_draw()

    # ── window ──
    def build_window(self):
        screen = Gdk.Screen.get_default()
        W, H = 1180, 720
        try:
            mon = screen.get_display().get_monitor(0).get_geometry()
            W, H = min(W, mon.width - 60), min(H, mon.height - 110)
        except Exception:
            pass
        win = Gtk.Window(title="Genshin Theme Builder")
        self.win = win
        try:
            win.set_wmclass("genshin-theme-builder", "genshin-theme-builder")
        except Exception:
            pass
        win.set_decorated(False)
        win.set_resizable(False)
        win.set_app_paintable(True)
        vis = screen.get_rgba_visual()
        if vis:
            win.set_visual(vis)
        win.get_style_context().add_class("gt")
        win.connect("destroy", lambda *_: Gtk.main_quit())
        win.connect("key-press-event", self.on_key)

        frame = vbox(0)
        frame.get_style_context().add_class("mainframe")
        frame.set_size_request(W, H)
        win.add(frame)
        frame.drag_dest_set(Gtk.DestDefaults.ALL, [Gtk.TargetEntry.new("text/uri-list", 0, 0)], Gdk.DragAction.COPY)
        frame.connect("drag-data-received", self.on_drop)
        frame.connect("drag-motion", lambda *_: self.drag_hl(True) or False)
        frame.connect("drag-leave", lambda *_: self.drag_hl(False))
        self.frame = frame

        # header
        hdr = Gtk.Overlay()
        center = vbox(2)
        center.set_margin_top(16)
        row = hbox(16)
        row.set_halign(Gtk.Align.CENTER)
        row.pack_start(lbl("✦", "spark"), False, False, 0)
        row.pack_start(lbl("Theme Builder", "title"), False, False, 0)
        row.pack_start(lbl("✦", "spark"), False, False, 0)
        center.pack_start(row, False, False, 0)
        center.pack_start(lbl("Build themes from your wallpapers", "subtitle"), False, False, 0)
        orn = Ornament(22)
        orn.set_margin_start(60)
        orn.set_margin_end(60)
        center.pack_start(orn, False, False, 2)
        hdr.add(center)
        close = btn("✕", "ghost close", Gtk.main_quit)
        close.set_halign(Gtk.Align.END)
        close.set_valign(Gtk.Align.START)
        close.set_margin_top(16)
        close.set_margin_end(20)
        hdr.add_overlay(close)
        frame.pack_start(hdr, False, False, 0)

        # body
        body = hbox(18)
        body.set_margin_start(22)
        body.set_margin_end(22)
        body.set_margin_top(6)
        frame.pack_start(body, True, True, 0)

        side = vbox(10)
        side.get_style_context().add_class("sidebar")
        side.set_size_request(270, -1)
        side.pack_start(lbl("Themes", "section", 0), False, False, 2)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list.get_style_context().add_class("themes")
        self.list.connect("row-selected", self.on_row_selected)
        sw.add(self.list)
        side.pack_start(sw, True, True, 0)
        side.pack_start(btn("＋  New theme", "pill", self.new_theme), False, False, 0)
        body.pack_start(side, False, False, 0)

        det = vbox(12)
        self.detail = det
        body.pack_start(det, True, True, 0)

        top = hbox(10)
        names = vbox(2)
        self.l_name = lbl("", "dname", 0, True)
        self.l_sub = lbl("", "muted", 0)
        nrow = hbox(10)
        nrow.pack_start(self.l_name, False, False, 0)
        self.l_active = lbl("Active", "tag")
        self.l_active.set_no_show_all(True)
        self.l_active.set_valign(Gtk.Align.CENTER)
        nrow.pack_start(self.l_active, False, False, 0)
        names.pack_start(nrow, False, False, 0)
        names.pack_start(self.l_sub, False, False, 0)
        top.pack_start(names, True, True, 0)
        self.b_rename = btn("Rename", "ghost", self.rename)
        self.b_delete = btn("Delete", "ghost danger", self.delete)
        top.pack_end(self.b_delete, False, False, 0)
        top.pack_end(self.b_rename, False, False, 0)
        det.pack_start(top, False, False, 0)

        self.acc_row = hbox(10)
        self.acc_row.pack_start(lbl("Accent", "section", 0), False, False, 4)
        self.chipbox = hbox(4)
        self.acc_row.pack_start(self.chipbox, False, False, 0)
        self.l_acc = lbl("", "muted", 0)
        self.acc_row.pack_start(self.l_acc, False, False, 8)
        det.pack_start(self.acc_row, False, False, 0)

        self.toolbar = hbox(8)
        self.toolbar.pack_start(btn("＋  Add images", "pill", self.choose_images), False, False, 0)
        self.toolbar.pack_start(btn("Add folder", "ghost", lambda: self.choose_images(True)), False, False, 0)
        self.b_selall = btn("Select all", "ghost", self.select_all)
        self.b_selnone = btn("Clear", "ghost", self.select_none)
        self.toolbar.pack_start(self.b_selall, False, False, 6)
        self.toolbar.pack_start(self.b_selnone, False, False, 0)
        self.b_remove = btn("Remove selected", "ghost danger", self.remove_selected)
        self.toolbar.pack_end(self.b_remove, False, False, 0)
        self.l_sel = lbl("", "muted", 1, True)
        self.l_sel.set_max_width_chars(30)
        self.l_sel.set_width_chars(30)
        self.toolbar.pack_end(self.l_sel, False, False, 8)
        det.pack_start(self.toolbar, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack.set_transition_duration(160)
        gsw = Gtk.ScrolledWindow()
        gsw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.flow = Gtk.FlowBox()
        self.flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flow.set_homogeneous(True)
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_min_children_per_line(2)
        self.flow.set_max_children_per_line(6)
        self.flow.set_row_spacing(4)
        self.flow.set_column_spacing(4)
        gsw.add(self.flow)
        self.stack.add_named(gsw, "grid")
        self.stack.add_named(self.make_empty("empty"), "empty")
        self.stack.add_named(self.make_empty("all"), "all")
        det.pack_start(self.stack, True, True, 0)

        act = hbox(10)
        act.pack_start(lbl("Super+Shift+W shows the images of the active theme.", "muted", 0, True), True, True, 0)
        self.b_activate = btn("Activate theme", "pill big", self.activate)
        act.pack_end(self.b_activate, False, False, 0)
        # GP_FOLLOW_V2: admin window style  [Theme] [Classic] [Gold]
        self.polkit_box = hbox(2)
        self.polkit_box.set_no_show_all(True)
        self.polkit_lbl = lbl("Admin window", "muted")
        self.polkit_lbl.set_no_show_all(True)
        self.b_polkit = {}
        for key, text, tip in (
                ("theme", "Theme", "Admin-password window uses the active theme colour"),
                ("classic", "Classic", "Admin-password window uses the saved style (genshin / ronova)"),
                ("gold", "Gold", "Admin-password window always uses the plain Genshin gold")):
            pb = btn(text, "ghost", None)
            pb.set_tooltip_text(tip)
            pb.connect("clicked", lambda _b, k=key: self.set_polkit(k))
            pb.show()
            self.b_polkit[key] = pb
            self.polkit_box.pack_start(pb, False, False, 0)
        act.pack_end(self.polkit_box, False, False, 0)
        act.pack_end(self.polkit_lbl, False, False, 6)
        self.refresh_polkit()
        det.pack_start(act, False, False, 0)

        # footer
        foot = hbox(8)
        foot.get_style_context().add_class("footer")
        foot.set_margin_start(22)
        foot.set_margin_end(22)
        foot.set_margin_top(12)
        foot.set_margin_bottom(14)
        foot.set_margin_top(12)
        foot.pack_start(lbl("Auto change", "section", 0), False, False, 8)
        self.auto_btns = {}
        for key, text in AUTO_CHOICES:
            b = btn(text, "ghost", None)
            b.connect("clicked", lambda _b, k=key: self.set_auto(k))
            self.auto_btns[key] = b
            foot.pack_start(b, False, False, 0)
        self.b_trash = btn("Trash", "ghost", self.show_trash)
        foot.pack_end(self.b_trash, False, False, 0)
        self.l_status = lbl("", "status", 1, True)
        self.l_status.set_max_width_chars(22)
        foot.pack_end(self.l_status, False, False, 12)
        frame.pack_start(foot, False, False, 0)
        self.refresh_auto()
        self.refresh_trash_label()

    def make_empty(self, kind):
        box = vbox(10)
        box.get_style_context().add_class("empty")
        box.set_valign(Gtk.Align.FILL)
        inner = vbox(8)
        inner.set_valign(Gtk.Align.CENTER)
        inner.set_halign(Gtk.Align.CENTER)
        if kind == "empty":
            inner.pack_start(lbl("This theme has no images yet", "bigmsg"), False, False, 0)
            inner.pack_start(lbl("Drag images or folders into this window, or add them here.", "muted"), False, False, 0)
            b = btn("＋  Add images", "pill", self.choose_images)
            b.set_halign(Gtk.Align.CENTER)
            b.set_margin_top(10)
            inner.pack_start(b, False, False, 0)
        else:
            self.l_all = lbl("", "muted")
            inner.pack_start(lbl("All of Teyvat", "bigmsg"), False, False, 0)
            inner.pack_start(self.l_all, False, False, 0)
            inner.pack_start(lbl("Activate it to rotate through every image of every theme.", "muted"), False, False, 0)
        box.pack_start(inner, True, True, 0)
        return box

    # ── keyboard / drag ──
    def on_key(self, _w, ev):
        ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
        k = ev.keyval
        if k == Gdk.KEY_Escape:
            Gtk.main_quit()
        elif ctrl and k in (Gdk.KEY_a, Gdk.KEY_A):
            self.select_all()
        elif ctrl and k in (Gdk.KEY_n, Gdk.KEY_N):
            self.new_theme()
        elif ctrl and k in (Gdk.KEY_v, Gdk.KEY_V):
            self.paste()
        elif k == Gdk.KEY_Delete:
            self.remove_selected()
        else:
            return False
        return True

    def drag_hl(self, on):
        ctx = self.detail.get_style_context()
        (ctx.add_class if on else ctx.remove_class)("dropping")

    def on_drop(self, _w, _ctx, _x, _y, data, _info, _t):
        self.drag_hl(False)
        paths = []
        for u in data.get_uris():
            try:
                paths.append(GLib.filename_from_uri(u)[0])
            except Exception:
                pass
        if paths:
            self.import_paths(paths)

    def paste(self):
        try:
            cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            paths = []
            data = cb.wait_for_contents(Gdk.Atom.intern("text/uri-list", False))
            if data:
                for u in data.get_uris():
                    paths.append(GLib.filename_from_uri(u)[0])
            else:
                txt = cb.wait_for_text() or ""
                for line in txt.splitlines():
                    p = os.path.expanduser(line.strip())
                    if os.path.exists(p):
                        paths.append(p)
            if paths:
                self.import_paths(paths)
            else:
                self.say("Nothing to paste: copy some images or a folder first")
        except Exception:
            self.say("Couldn't read the clipboard")

    # ── status line ──
    def say(self, text):
        self.l_status.set_text(text)
        self._status_id += 1
        sid = self._status_id

        def clear():
            if sid == self._status_id:
                self.l_status.set_text("")
            return False
        GLib.timeout_add_seconds(6, clear)

    # ── sidebar ──
    def theme_dir(self, key):
        return self.wall if key == "all" else os.path.join(self.wall, key)

    def refresh_sidebar(self, select, show=False):
        self._building = True
        for r in self.list.get_children():
            self.list.remove(r)
        self.rows, self.info = {}, {}
        act = active_theme()
        try:
            names = sorted([n for n in os.listdir(self.wall)
                            if not n.startswith(".") and os.path.isdir(os.path.join(self.wall, n))], key=natkey)
        except OSError:
            names = []
        for key in ["all"] + names:
            d = self.theme_dir(key)
            imgs = list_images(d)
            acc = None if key == "all" else accent_of(d)
            self.info[key] = {"imgs": imgs, "acc": acc}
            row = Gtk.ListBoxRow()
            row.key = key
            box = hbox(12)
            th = Thumb(56, 56, 12)
            if imgs:
                self.load_thumb(self.gen, th, imgs[0], 56, 56)
            tov = Gtk.Overlay()
            tov.add(th)
            badge = lbl("✔", "badge")
            badge.set_halign(Gtk.Align.END)
            badge.set_valign(Gtk.Align.START)
            badge.set_no_show_all(True)
            badge.set_tooltip_text("Active theme")
            tov.add_overlay(badge)
            if key == act:
                badge.show()
            box.pack_start(tov, False, False, 0)
            info = vbox(2)
            info.set_valign(Gtk.Align.CENTER)
            nrow = hbox(6)
            nrow.pack_start(lbl("All of Teyvat" if key == "all" else pretty(key), "row-name", 0, True),
                            False, False, 0)
            info.pack_start(nrow, False, False, 0)
            label = "Auto" if key == "all" else (acc[0] if acc else "Auto")
            info.pack_start(lbl(f"{len(imgs)} images · {label}", "row-sub", 0), False, False, 0)
            box.pack_start(info, True, True, 0)
            if acc:
                chip = Chip("pal", acc[0], acc[1], acc[2], acc[3], size=26)
                chip.set_sensitive(False)
                box.pack_end(chip, False, False, 0)
            row.add(box)
            self.list.add(row)
            self.rows[key] = row
        self.list.show_all()
        row = self.rows.get(select) or self.rows["all"]
        self.list.select_row(row)
        self._building = False
        if show:
            self.show_theme(row.key)
        self.refresh_trash_label()

    def on_row_selected(self, _lb, row):
        if self._building or row is None:
            return
        self.show_theme(row.key)

    # ── thumbs ──
    def load_thumb(self, gen, th, path, w, h):
        def work():
            if gen != self.gen and w == self.CARD_W:
                return
            pb = cover_thumb(path, w, h)
            GLib.idle_add(th.set_pixbuf, pb)
        POOL.submit(work)

    # ── detail ──
    def show_theme(self, key):
        self.theme = key
        self.gen += 1
        self.sel.clear()
        self.last_idx = None
        info = self.info.get(key) or {"imgs": [], "acc": None}
        n = len(info["imgs"])
        is_all = key == "all"
        self.l_name.set_text("All of Teyvat" if is_all else pretty(key))
        if is_all:
            themes = len(self.info) - 1
            self.l_sub.set_text(f"{n} images across {themes} themes")
            self.l_all.set_text(f"{n} images across {themes} themes")
        else:
            acc = info["acc"][0] if info["acc"] else "Auto"
            self.l_sub.set_text(f"{n} images · accent: {acc}")
        if active_theme() == key:
            self.l_active.show()
        else:
            self.l_active.hide()
        for w in (self.b_rename, self.b_delete, self.acc_row, self.toolbar):
            w.set_visible(not is_all)
        self.b_activate.set_sensitive(n > 0)
        self.b_activate.set_label("Apply again" if active_theme() == key else "Activate theme")
        for c in self.flow.get_children():
            self.flow.remove(c)
        self.cards, self.order = {}, []
        if is_all:
            self.stack.set_visible_child_name("all")
        elif n == 0:
            self.stack.set_visible_child_name("empty")
        else:
            self.build_grid(info["imgs"])
            self.stack.set_visible_child_name("grid")
        if not is_all:
            self.build_accent()
        self.update_selection()
        self.ui_accent(key)

    def build_grid(self, imgs):
        self.order = imgs
        gen = self.gen
        self._grid_pos = 0

        def step():
            if gen != self.gen:
                return False
            end = min(self._grid_pos + 16, len(imgs))
            for i in range(self._grid_pos, end):
                self.add_card(i, imgs[i], gen)
            self._grid_pos = end
            return end < len(imgs)

        if step():
            GLib.idle_add(step, priority=GLib.PRIORITY_LOW)

    def add_card(self, i, p, gen):
        if True:
            eb = Gtk.EventBox()
            eb.get_style_context().add_class("card")
            inner = vbox(6)
            inner.set_margin_start(8)
            inner.set_margin_end(8)
            inner.set_margin_top(8)
            inner.set_margin_bottom(8)
            ov = Gtk.Overlay()
            ov.set_halign(Gtk.Align.CENTER)
            th = Thumb(self.CARD_W, self.CARD_H, 10)
            ov.add(th)
            check = lbl("✔", "check")
            check.set_halign(Gtk.Align.END)
            check.set_valign(Gtk.Align.START)
            check.set_no_show_all(True)
            ov.add_overlay(check)
            inner.pack_start(ov, False, False, 0)
            name = lbl(os.path.basename(p), "cname")
            name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            name.set_max_width_chars(20)
            inner.pack_start(name, False, False, 0)
            eb.add(inner)
            eb.set_tooltip_text(os.path.relpath(p, self.theme_dir(self.theme)))
            eb.connect("button-press-event", self.on_card, p, i)
            self.flow.add(eb)
            self.cards[p] = (eb, check)
            self.load_thumb(gen, th, p, self.CARD_W, self.CARD_H)
            eb.show_all()
            if p in self.sel:
                eb.get_style_context().add_class("sel")
                check.show()

    def on_card(self, _eb, ev, path, idx):
        if ev.button != 1 or ev.type != Gdk.EventType.BUTTON_PRESS:
            return False
        before = set(self.sel)
        if ev.state & Gdk.ModifierType.SHIFT_MASK and self.last_idx is not None:
            a, b = sorted((self.last_idx, idx))
            self.sel.update(self.order[a:b + 1])
        elif path in self.sel:
            self.sel.discard(path)
        else:
            self.sel.add(path)
        self.last_idx = idx
        self.update_selection(before ^ self.sel)
        return True

    def update_selection(self, only=None):
        for p in (list(self.cards) if only is None else only):
            if p not in self.cards:
                continue
            eb, check = self.cards[p]
            on = p in self.sel
            ctx = eb.get_style_context()
            (ctx.add_class if on else ctx.remove_class)("sel")
            check.show() if on else check.hide()
        n = len(self.sel)
        self.l_sel.set_text(f"{n} selected" if n else "Click images to select · Shift selects a range")
        self.b_remove.set_sensitive(n > 0)
        has = bool(self.order)
        for w in (self.b_selall, self.b_selnone, self.b_remove, self.l_sel):
            w.set_visible(has)

    def select_all(self):
        self.sel.update(self.order)
        self.update_selection()

    def select_none(self):
        self.sel.clear()
        self.update_selection()

    # ── accent ──
    def build_accent(self):
        for c in self.chipbox.get_children():
            self.chipbox.remove(c)
        self.chips = []
        d = self.theme_dir(self.theme)
        cur = accent_of(d)
        auto = Chip("auto", "Auto: follows the colours of each image", on_click=self.pick_chip)
        self.add_chip(auto)
        found = cur is None
        if cur is None:
            auto.set_selected(True)
        for n, b, h, l in PRESETS:
            c = Chip("fix", n, b, h, l, on_click=self.pick_chip)
            self.add_chip(c)
            if cur and cur[1] == b:
                c.set_selected(True)
                found = True
        if not found:
            c = Chip("fix", cur[0], cur[1], cur[2], cur[3], on_click=self.pick_chip)
            c.set_selected(True)
            self.add_chip(c)
        self.add_chip(Chip("custom", "Custom colour…", on_click=self.pick_chip))
        self.chipbox.show_all()
        self.l_acc.set_text(cur[0] if cur else "Auto")
        imgs = self.info[self.theme]["imgs"]
        if imgs:
            theme, gen = self.theme, self.gen
            POOL2.submit(lambda: GLib.idle_add(self.add_palette_chips, theme, gen, palette(imgs[0])))

    def add_chip(self, c):
        self.chips.append(c)
        self.chipbox.pack_start(c, False, False, 0)

    def add_palette_chips(self, theme, gen, pal):
        if theme != self.theme or gen != self.gen:
            return False
        have = {c.base for c in self.chips if c.base}
        pos = 1
        for b, h, l, n in pal:
            if b in have:
                continue
            c = Chip("pal", f"{n} (from this theme's images)", b, h, l, on_click=self.pick_chip)
            c.name = n
            self.chips.insert(pos, c)
            self.chipbox.pack_start(c, False, False, 0)
            self.chipbox.reorder_child(c, pos)
            c.show()
            pos += 1
        return False

    def pick_chip(self, chip):
        t = self.theme
        d = self.theme_dir(t)
        if chip.kind == "auto":
            write_theme(d)
        elif chip.kind == "custom":
            hx = self.prompt("Custom colour", "Hex colour, e.g. #e63956", "")
            if not hx:
                return
            hx = hx.lstrip("#")
            if not re.fullmatch(r"[0-9a-fA-F]{6}", hx):
                self.say("That is not a valid hex colour")
                return
            b, h, l = hex_trio(hx)
            write_theme(d, ("Custom", b, h, l))
        else:
            write_theme(d, (chip.name, chip.base, chip.hi, chip.lo))
        if t == active_theme():
            cur = read_file(CUR_FILE)
            POOL2.submit(lambda: lib('res_theme_apply "$1" "$2"', t, cur))
        self.refresh_sidebar(t, show=False)
        self.info = self.info
        acc = accent_of(d)
        self.l_sub.set_text(f"{len(self.info[t]['imgs'])} images · accent: {acc[0] if acc else 'Auto'}")
        self.build_accent()
        self.ui_accent(t)

    def ui_accent(self, key):
        acc = None if key == "all" else self.info.get(key, {}).get("acc")
        if acc:
            self.set_accent(acc[1], acc[2], acc[3])
            return
        imgs = self.info.get(key, {}).get("imgs") if key != "all" else None
        if not imgs:
            self.set_accent(*DEFAULT)
            return

        def work():
            p = palette(imgs[0])
            if p:
                GLib.idle_add(self.apply_pal, key, p[0])
        POOL2.submit(work)

    def apply_pal(self, key, p):
        if key == self.theme:
            self.set_accent(p[0], p[1], p[2])
        return False

    # ── image operations ──
    def choose_images(self, folder=False):
        if self.theme in (None, "all"):
            return
        dlg = Gtk.FileChooserNative.new(
            "Add a folder" if folder else "Add images", self.win,
            Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN, "Add", "Cancel")
        dlg.set_select_multiple(True)
        if not folder:
            flt = Gtk.FileFilter()
            flt.set_name("Images")
            flt.add_mime_type("image/*")
            dlg.add_filter(flt)
        pics = os.path.join(HOME, "Pictures")
        if os.path.isdir(pics):
            dlg.set_current_folder(pics)
        r = dlg.run()
        names = dlg.get_filenames() if r == Gtk.ResponseType.ACCEPT else []
        dlg.destroy()
        if names:
            self.import_paths(names)

    def import_paths(self, paths):
        t = self.theme
        if t in (None, "all"):
            self.say("Pick a theme first")
            return
        dest = os.path.join(self.wall, t)
        self.say("Importing…")

        def work():
            n = sum(import_into(p, dest) for p in paths)
            GLib.idle_add(self.after_import, t, n)
        POOL2.submit(work)

    def after_import(self, t, n):
        self.say(f"{n} image(s) added" if n else "Nothing new to add")
        if n and os.path.isdir(os.path.join(self.wall, t)) and not os.path.exists(os.path.join(self.wall, t, ".theme")):
            write_theme(os.path.join(self.wall, t))
        self.refresh_sidebar(t, show=(self.theme == t))
        return False

    def remove_selected(self):
        if not self.sel or self.theme in (None, "all"):
            return
        t = self.theme
        td = os.path.join(TRASH, "images", t)
        os.makedirs(td, exist_ok=True)
        n = 0
        for p in list(self.sel):
            try:
                shutil.move(p, unique_path(td, os.path.basename(p)))
                n += 1
            except (OSError, shutil.Error):
                pass
        if active_theme() == t and not list_images(os.path.join(self.wall, t)):
            write_file(COLL_FILE, "all")
        self.say(f"{n} image(s) moved to the trash")
        self.refresh_sidebar(t, show=True)

    # ── theme operations ──
    def new_theme(self):
        raw = self.prompt("New theme", "Name it, e.g. Hyperion, Liyue Night, Fontaine")
        if not raw:
            return
        slug = slugify(raw)
        if not slug or slug == "all":
            self.say("That name can't be used")
            return
        d = os.path.join(self.wall, slug)
        fresh = not os.path.isdir(d)
        if fresh:
            os.makedirs(d, exist_ok=True)
            write_theme(d)
        self.refresh_sidebar(slug, show=True)
        if fresh:
            GLib.idle_add(lambda: self.choose_images() or False)

    def rename(self):
        t = self.theme
        raw = self.prompt("Rename theme", "Type the new name", pretty(t))
        if not raw:
            return
        slug = slugify(raw)
        if not slug or slug == "all" or os.path.exists(os.path.join(self.wall, slug)):
            self.say("That name can't be used (empty or already exists)")
            return
        try:
            os.rename(os.path.join(self.wall, t), os.path.join(self.wall, slug))
        except OSError:
            self.say("Rename failed")
            return
        if active_theme() == t:
            write_file(COLL_FILE, slug)
        cur = read_file(CUR_FILE)
        prefix = os.path.join(self.wall, t) + "/"
        if cur.startswith(prefix):
            write_file(CUR_FILE, os.path.join(self.wall, slug, cur[len(prefix):]) + "\n")
        self.refresh_sidebar(slug, show=True)

    def delete(self):
        t = self.theme
        n = len(self.info[t]["imgs"])
        if not self.confirm("Delete theme?", f"{pretty(t)} · {n} images. It stays in the trash, so you can restore it.",
                            "Delete theme"):
            return
        if trash_theme(self.wall, t):
            if active_theme() == t:
                write_file(COLL_FILE, "all")
            notify("Theme deleted", f"{pretty(t)} is in the trash")
            self.say(f"{pretty(t)} moved to the trash")
            self.refresh_sidebar("all", show=True)
        else:
            self.say("Could not delete the theme: check permissions")

    def activate(self):
        t = self.theme
        if not t:
            return
        self.say("Activating…")

        def work():
            if os.path.exists(WSH):
                try:
                    subprocess.run(["bash", WSH, "--region", t], capture_output=True, timeout=120)
                except Exception:
                    pass
            if active_theme() != t:
                write_file(COLL_FILE, t)
            lib('res_theme_apply "$1" "$2"', t, read_file(CUR_FILE))
            notify("All of Teyvat" if t == "all" else pretty(t), "Theme active")
            GLib.idle_add(self.after_activate, t)
        POOL2.submit(work)

    def after_activate(self, t):
        self.say("Theme activated")
        self.refresh_sidebar(t, show=(self.theme == t))
        return False

    # ── admin (polkit) window follows the theme ──
    def refresh_polkit(self):
        cur = polkit_mode()
        for k, pb in self.b_polkit.items():
            ctx = pb.get_style_context()
            (ctx.add_class if k == cur else ctx.remove_class)("on")
        if polkit_installed():
            self.polkit_box.show()
            self.polkit_lbl.show()
        else:
            self.polkit_box.hide()
            self.polkit_lbl.hide()

    def set_polkit(self, key):
        set_polkit_mode(key)
        self.refresh_polkit()
        self.say({"theme": "Admin window follows the theme",
                  "classic": "Admin window: saved style",
                  "gold": "Admin window: plain gold"}[key])

    # ── auto change ──
    def refresh_auto(self):
        mode, mins = read_conf()
        if mode == "rotate":
            cur = mins if mins in ("15", "30", "60") else None
        elif mode in ("daily", "daynight"):
            cur = mode
        else:
            cur = "off"
        for k, b in self.auto_btns.items():
            ctx = b.get_style_context()
            (ctx.add_class if k == cur else ctx.remove_class)("on")

    def set_auto(self, key):
        def work():
            if not os.path.exists(WSH):
                GLib.idle_add(self.say, "wallpaper.sh not found")
                return
            if key == "off":
                args = ["--mode", "off"]
            elif key in ("15", "30", "60"):
                set_conf("ROTATE_MINUTES", key)
                args = ["--mode", "rotate"]
            else:
                args = ["--mode", key]
            subprocess.run(["bash", WSH, *args], capture_output=True)
            GLib.idle_add(self.after_auto)
        POOL2.submit(work)

    def after_auto(self):
        self.refresh_auto()
        self.say("Auto change updated")
        return False

    # ── trash ──
    def trash_items(self):
        themes, images = [], []
        base = os.path.join(TRASH, "themes")
        if os.path.isdir(base):
            for b in sorted(os.listdir(base)):
                p = os.path.join(base, b)
                if os.path.isdir(p):
                    themes.append((b.rsplit("-", 1)[0], p, len(list_images(p))))
        base = os.path.join(TRASH, "images")
        if os.path.isdir(base):
            for b in sorted(os.listdir(base)):
                p = os.path.join(base, b)
                n = len(list_images(p)) if os.path.isdir(p) else 0
                if n:
                    images.append((b, p, n))
        return themes, images

    def refresh_trash_label(self):
        th, im = self.trash_items()
        n = len(th) + len(im)
        self.b_trash.set_label(f"Trash ({n})" if n else "Trash")

    def show_trash(self):
        while True:
            themes, images = self.trash_items()
            d, frame = self.dialog_frame("Trash", "Deleted themes and removed images")
            action = {}
            if not themes and not images:
                frame.pack_start(lbl("The trash is empty.", "muted"), False, False, 8)
            for name, p, n in themes:
                r = hbox(10)
                r.get_style_context().add_class("trashrow")
                r.pack_start(lbl(f"Theme · {pretty(name)} · {n} images", None, 0, True), True, True, 0)
                b = btn("Restore", "ghost", None)
                b.connect("clicked", lambda _b, a=("theme", name, p), dd=d: (action.update(v=a), dd.response(100)))
                r.pack_end(b, False, False, 0)
                frame.pack_start(r, False, False, 0)
            for name, p, n in images:
                r = hbox(10)
                r.get_style_context().add_class("trashrow")
                r.pack_start(lbl(f"{n} images removed from {pretty(name)}", None, 0, True), True, True, 0)
                b = btn("Restore", "ghost", None)
                b.connect("clicked", lambda _b, a=("images", name, p), dd=d: (action.update(v=a), dd.response(100)))
                r.pack_end(b, False, False, 0)
                frame.pack_start(r, False, False, 0)
            row = hbox(10)
            row.set_margin_top(10)
            if themes or images:
                e = btn("Empty the trash", "ghost danger", None)
                e.connect("clicked", lambda _b, dd=d: dd.response(101))
                row.pack_start(e, False, False, 0)
            row.pack_end(btn("Close", "pill", lambda dd=d: dd.response(Gtk.ResponseType.CLOSE)), False, False, 0)
            frame.pack_start(row, False, False, 0)
            d.show_all()
            r = d.run()
            d.destroy()
            if r == 100 and "v" in action:
                kind, name, p = action["v"]
                if kind == "theme":
                    dest = os.path.join(self.wall, name)
                    if os.path.exists(dest):
                        dest += "_restored"
                    shutil.move(p, dest)
                else:
                    dest = os.path.join(self.wall, name)
                    os.makedirs(dest, exist_ok=True)
                    for f in list_images(p):
                        shutil.move(f, unique_path(dest, os.path.basename(f)))
                    shutil.rmtree(p, ignore_errors=True)
                self.say("Restored")
                self.refresh_sidebar(self.theme or "all", show=True)
                continue
            if r == 101:
                if self.confirm("Empty the trash?", "This cannot be undone.", "Delete forever"):
                    shutil.rmtree(os.path.join(TRASH, "themes"), ignore_errors=True)
                    shutil.rmtree(os.path.join(TRASH, "images"), ignore_errors=True)
                    self.refresh_trash_label()
                continue
            break
        self.refresh_trash_label()

    # ── dialogs ──
    def dialog_frame(self, title, sub=None):
        d = Gtk.Dialog(transient_for=self.win, modal=True, destroy_with_parent=True)
        d.set_decorated(False)
        d.set_resizable(False)
        d.set_app_paintable(True)
        vis = Gdk.Screen.get_default().get_rgba_visual()
        if vis:
            d.set_visual(vis)
        d.get_style_context().add_class("gd")
        try:
            d.get_action_area().hide()
            d.get_action_area().set_no_show_all(True)
        except Exception:
            pass
        frame = vbox(10)
        frame.get_style_context().add_class("gframe")
        frame.set_size_request(460, -1)
        frame.pack_start(lbl(title, "dname", 0.5), False, False, 0)
        if sub:
            frame.pack_start(lbl(sub, "muted", 0.5), False, False, 0)
        o = Ornament(18)
        frame.pack_start(o, False, False, 4)
        d.get_content_area().pack_start(frame, True, True, 0)
        return d, frame

    def prompt(self, title, hint, prefill=""):
        d, frame = self.dialog_frame(title, hint)
        e = Gtk.Entry()
        e.get_style_context().add_class("gentry")
        e.set_text(prefill)
        e.connect("activate", lambda *_: d.response(Gtk.ResponseType.OK))
        frame.pack_start(e, False, False, 6)
        row = hbox(10)
        row.set_margin_top(8)
        row.set_halign(Gtk.Align.END)
        row.pack_start(btn("Cancel", "ghost", lambda: d.response(Gtk.ResponseType.CANCEL)), False, False, 0)
        row.pack_start(btn("OK", "pill", lambda: d.response(Gtk.ResponseType.OK)), False, False, 0)
        frame.pack_start(row, False, False, 0)
        d.show_all()
        e.grab_focus()
        e.select_region(0, -1)
        r = d.run()
        text = e.get_text().strip()
        d.destroy()
        return text if r == Gtk.ResponseType.OK and text else None

    def confirm(self, title, text, yes):
        d, frame = self.dialog_frame(title, text)
        row = hbox(10)
        row.set_margin_top(8)
        row.set_halign(Gtk.Align.END)
        row.pack_start(btn("Cancel", "ghost", lambda: d.response(Gtk.ResponseType.CANCEL)), False, False, 0)
        row.pack_start(btn(yes, "pill", lambda: d.response(Gtk.ResponseType.OK)), False, False, 0)
        frame.pack_start(row, False, False, 0)
        d.show_all()
        r = d.run()
        d.destroy()
        return r == Gtk.ResponseType.OK


# ───────────────────────────── entry point ─────────────────────────────
def restore():
    lib('res_theme_apply "$1" "$2"', active_theme(), read_file(CUR_FILE))


def main():
    if "--restore" in sys.argv:
        restore()
        return
    try:
        pid = int(read_file(PIDFILE, "0"))
        if pid and pid != os.getpid() and os.path.exists(f"/proc/{pid}"):
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                if b"theme-builder" in fh.read():
                    os.kill(pid, signal.SIGTERM)  # toggle: second keypress closes it
                    return
    except (OSError, ValueError):
        pass
    write_file(PIDFILE, str(os.getpid()))
    atexit.register(lambda: os.path.exists(PIDFILE) and os.remove(PIDFILE))
    GLib.set_prgname("genshin-theme-builder")
    GLib.set_application_name("Genshin Theme Builder")
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)
    App()
    Gtk.main()


if __name__ == "__main__":
    main()
