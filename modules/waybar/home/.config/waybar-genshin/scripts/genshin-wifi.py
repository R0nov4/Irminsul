#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ✦ GENSHIN CELESTIA v4 — "Starfell" Teyvat Ley-Line Network Suite    ║
# ║  Mini Popup (Paimon style) + Akasha Terminal (Inventory style)       ║
# ║  Motion engine: one shared timer, frame-region redraws, auto-sleep   ║
# ╚══════════════════════════════════════════════════════════════════════╝
import os, sys
os.environ.setdefault("NO_AT_BRIDGE", "1")      # no accessibility bridge  -> less RAM
os.environ.setdefault("GTK_A11Y", "none")
import math, time, signal, shutil, subprocess, threading, re, random, json, gc, ctypes
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
    HAS_LAYER = True
except Exception:
    HAS_LAYER = False
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo
import cairo

PID_FILE = f"/tmp/genshin-wifi-{os.getuid()}.pid"
CONF_DIR = os.path.expanduser("~/.config/waybar-genshin")
PREFS_FILE = os.path.join(CONF_DIR, "celestia.json")
SHADOW = 14
MINI_W = 396
AKASHA_W, AKASHA_H = 1000, 700

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PREFERENCES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEFAULT_PREFS = {"anim": True, "motes": True, "autoscan": True, "fps": 30, "top": 0, "right": 0}


def load_prefs():
    p = dict(DEFAULT_PREFS)
    try:
        with open(PREFS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            for k in p:
                if k in d and type(d[k]) is type(p[k]):
                    p[k] = d[k]
    except Exception:
        pass
    if p.get("top") == 30:  # old default -> new tighter default
        p["top"] = 0
    for env, k in (("CELESTIA_TOP", "top"), ("CELESTIA_RIGHT", "right"), ("CELESTIA_FPS", "fps")):
        v = os.environ.get(env, "")
        if v.lstrip("-").isdigit():
            p[k] = int(v)
    if os.environ.get("CELESTIA_NO_ANIM"):
        p["anim"] = False
    p["fps"] = max(10, min(60, int(p["fps"])))
    return p


def save_prefs(p):
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(p, f, indent=2)
    except Exception as e:
        print("prefs:", e, file=sys.stderr)


PREFS = load_prefs()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MEMORY CONTROL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
try:
    _LIBC = ctypes.CDLL("libc.so.6")
except Exception:
    _LIBC = None
_TRIM = [0.0]


def trim_memory(*_):
    """Collect garbage and hand freed heap pages back to the OS (throttled)."""
    now = time.monotonic()
    if now - _TRIM[0] < 3.0:
        return False
    _TRIM[0] = now
    gc.collect()
    if _LIBC is not None:
        try:
            _LIBC.malloc_trim(0)
        except Exception:
            pass
    return False


def later_trim(ms=900):
    GLib.timeout_add(ms, trim_memory)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MOTION ENGINE — a single timer that sleeps when nothing moves
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def lerp(a, b, k):
    return a + (b - a) * k


def e_lin(t):
    return t


def e_out(t):
    return 1.0 - (1.0 - t) ** 3


def e_inout(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def e_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print("anim:", e, file=sys.stderr)
        return None


class Motion:
    """One shared clock for every animation.

    * driven by the window's frame clock (vsync) -> evenly paced frames, no timer jitter
    * tweens (hover, fades, slides) always run at full frame rate
    * ambient redraws (glows, rings, graph) are throttled on their own clock and slow
      themselves down automatically when the machine can't keep up, then speed back up
    * sleeps completely when nothing moves"""

    def __init__(self):
        self.t0 = time.monotonic()
        self.tw = []
        self.amb = []
        self.host = None
        self.tick_id = 0
        self.src = 0
        self.iv = 0
        self.busy = False
        self.enabled = True
        self.fps = 30
        self.amb_fps = 30.0
        self.last_amb = -1.0
        self.last_tick = 0.0
        self.amb_mark = 0.0
        self.base = 16.7
        self.gap = 16.7
        self.good = 0
        self.slow = 0

    def now(self):
        return time.monotonic() - self.t0

    def attach(self, host):
        self.host = host
        self.amb_fps = float(self.fps)
        self._sched()

    def tween(self, dur, fn, delay=0.0, ease=e_out, done=None, key=None, owner=None):
        if key is not None and self.tw:
            self.tw = [w for w in self.tw if w[5] != key]
        if not self.enabled or dur <= 0:
            _safe(fn, 1.0)
            if done:
                _safe(done)
            return
        _safe(fn, 0.0)
        self.tw.append([self.now() + delay, dur, fn, ease, done, key, owner])
        self._sched()

    def finish_all(self):
        tw, self.tw = self.tw, []
        for w in tw:
            _safe(w[2], 1.0)
            if w[4]:
                _safe(w[4])

    def kill(self, owner):
        if self.tw:
            self.tw = [w for w in self.tw if w[6] is not owner]
        self.unwatch(owner)

    def watch(self, o):
        if o not in self.amb:
            self.amb.append(o)
            self._sched()

    def unwatch(self, o):
        if o in self.amb:
            self.amb.remove(o)
            self._sched()

    def set_enabled(self, on):
        self.enabled = bool(on)
        if not on:
            self.finish_all()
        self._sched()

    def _want(self):
        return 1 if (self.tw or (self.amb and self.enabled)) else 0

    def _sched(self):
        if self.busy:
            return
        want = self._want()
        if want == self.iv:
            return
        self.iv = want
        if not want:
            if self.src:
                GLib.source_remove(self.src)
                self.src = 0
            return
        if self.host is not None:
            if not self.tick_id:
                self.tick_id = self.host.add_tick_callback(self._frame)
        elif not self.src:
            self.src = GLib.timeout_add(16, self._timer)

    def _frame(self, widget, clock):
        if self._step():
            return GLib.SOURCE_CONTINUE
        self.tick_id = 0
        self.iv = 0
        return GLib.SOURCE_REMOVE

    def _timer(self):
        if self._step():
            return True
        self.src = 0
        self.iv = 0
        return False

    def _adapt(self, tm):
        """Measure how long the last painted ambient frame really took and adjust the
        ambient frame rate: slower CPU -> fewer ambient frames, never a laggy UI."""
        if self.last_tick:
            dt = (tm - self.last_tick) * 1000.0
            if 4.0 < dt < 120.0:
                self.base = max(8.0, min(self.base * 1.01, dt, 40.0))
        self.last_tick = tm
        if self.amb_mark:
            gap = (tm - self.amb_mark) * 1000.0
            self.amb_mark = 0.0
            if gap < 400.0:
                self.gap = gap
                if gap > max(30.0, self.base * 1.8):
                    # a painted ambient frame took clearly longer than a frame slot
                    self.slow += 1
                    self.good = 0
                    if self.slow >= 6 and self.amb_fps > 12.0:
                        self.amb_fps = max(12.0, self.amb_fps * 0.8)
                        self.slow = 0
                else:
                    self.slow = 0
                    if gap < self.base * 1.35 and self.amb_fps < self.fps:
                        self.good += 1
                        if self.good >= 45:
                            self.amb_fps = min(float(self.fps), self.amb_fps * 1.25)
                            self.good = 0

    def _step(self):
        self.busy = True
        tm = time.monotonic()
        t = tm - self.t0
        self._adapt(tm)
        cur, self.tw = self.tw, []
        keep, fin = [], []
        for w in cur:
            st, dur, fn, ease, done, key, owner = w
            if owner is not None and getattr(owner, "_dead", False):
                continue
            if t < st:
                keep.append(w)
                continue
            p = clamp((t - st) / dur)
            _safe(fn, ease(p))
            if p < 1.0:
                keep.append(w)
            elif done:
                fin.append(done)
        if self.tw:
            nk = {w[5] for w in self.tw if w[5] is not None}
            keep = [w for w in keep if w[5] is None or w[5] not in nk] + self.tw
        self.tw = keep
        for d in fin:
            _safe(d)
        if self.enabled and self.amb and t - self.last_amb >= 1.0 / self.amb_fps - 0.5 * self.base / 1000.0:
            self.last_amb = t
            self.amb_mark = time.monotonic()
            for o in list(self.amb):
                _safe(o._amb, t)
        self.busy = False
        return self._want() != 0


M = Motion()
M.enabled = bool(PREFS["anim"])
M.fps = PREFS["fps"]


def T():
    return M.now()


# >>> DRAW-BEGIN
PI = math.pi
TAU = 2 * math.pi
SERIF = "HYWenHei 85W,HYWenHei,Noto Serif,DejaVu Serif,Serif"
SANS = "Noto Sans,Vazirmatn,Inter,DejaVu Sans,Sans"
MONO = "JetBrains Mono,Noto Sans Mono,DejaVu Sans Mono,Monospace"

GOLD, GOLD_HI, CREAM, INK, INK2, NAVY = "#D3BC8E", "#F2E1B5", "#ECE5D8", "#3B4354", "#495366", "#1E2233"

ELEM = {
    "anemo":   ("#5FC1A0", "#B8F7E0", "Anemo"),
    "geo":     ("#E9A92A", "#FFE4A0", "Geo"),
    "electro": ("#A86BD9", "#E6C9FF", "Electro"),
    "dendro":  ("#8DB52C", "#DDF58F", "Dendro"),
    "hydro":   ("#3BA8E6", "#B9EAFF", "Hydro"),
    "pyro":    ("#E8642C", "#FFC9A0", "Pyro"),
    "cryo":    ("#86C7DA", "#EAFBFF", "Cryo"),
}
RARITY = {5: ("#6E4A35", "#D79B4A"), 4: ("#4E4772", "#A985C8"), 3: ("#3E5378", "#58A2C9"),
          2: ("#3F5C56", "#5FA07F"), 1: ("#4F535C", "#8A8C92"), 0: ("#3A3E49", "#5B5F69")}
RARITY_NAME = {5: "Legendary", 4: "Epic", 3: "Rare", 2: "Uncommon", 1: "Common", 0: "Unattuned"}


def hx(h):
    h = h.lstrip("#")
    return int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0


def src(cr, h, a=1.0):
    r, g, b = hx(h)
    cr.set_source_rgba(r, g, b, a)


def lin(x0, y0, x1, y1, stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for o, h, a in stops:
        r, gg, b = hx(h)
        g.add_color_stop_rgba(o, r, gg, b, a)
    return g


def rad(cx, cy, r0, r1, stops, fx=None, fy=None):
    g = cairo.RadialGradient(cx if fx is None else fx, cy if fy is None else fy, r0, cx, cy, r1)
    for o, h, a in stops:
        r, gg, b = hx(h)
        g.add_color_stop_rgba(o, r, gg, b, a)
    return g


def rrect(cr, x, y, w, h, r):
    if not isinstance(r, (tuple, list)):
        r = (r, r, r, r)
    m = max(0.0, min(w, h) / 2.0)
    tl, tr, br, bl = [max(0.0, min(v, m)) for v in r]
    cr.new_path()
    cr.arc(x + w - tr, y + tr, tr, -PI / 2, 0)
    cr.arc(x + w - br, y + h - br, br, 0, PI / 2)
    cr.arc(x + bl, y + h - bl, bl, PI / 2, PI)
    cr.arc(x + tl, y + tl, tl, PI, 1.5 * PI)
    cr.close_path()


_GS = {}
_GB = (4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256)


def glow(cr, cx, cy, r, h, a):
    """Soft radial glow.  The gradient is rasterised once per (colour, size bucket) and
    then blitted - far cheaper than filling a radial gradient on every frame."""
    if r <= 0 or a <= 0.003:
        return
    if r > 256 or r < 1.5:
        cr.new_path()
        cr.arc(cx, cy, r, 0, TAU)
        cr.set_source(rad(cx, cy, 0, r, [(0, h, a), (0.45, h, a * 0.45), (1, h, 0)]))
        cr.fill()
        return
    R0 = _GB[0]
    for bsz in _GB:
        R0 = bsz
        if bsz >= r:
            break
    sp = _GS.get((h, R0))
    if sp is None:
        sp = cairo.ImageSurface(cairo.FORMAT_ARGB32, 2 * R0, 2 * R0)
        c = cairo.Context(sp)
        c.set_source(rad(R0, R0, 0, R0, [(0, h, 1.0), (0.45, h, 0.45), (1, h, 0.0)]))
        c.paint()
        sp.flush()
        _GS[(h, R0)] = sp
    k = r / float(R0)
    cr.save()
    cr.translate(cx - r, cy - r)
    cr.scale(k, k)
    cr.set_source_surface(sp, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_BILINEAR)
    cr.paint_with_alpha(a)
    cr.restore()
    cr.new_path()


def path_sparkle(cr, k=0.16):
    cr.move_to(0, -1)
    cr.curve_to(k, -k, k, -k, 1, 0)
    cr.curve_to(k, k, k, k, 0, 1)
    cr.curve_to(-k, k, -k, k, -1, 0)
    cr.curve_to(-k, -k, -k, -k, 0, -1)
    cr.close_path()


def path_star5(cr, inner=0.47):
    for i in range(10):
        r = 1.0 if i % 2 == 0 else inner
        a = -PI / 2 + i * PI / 5
        x, y = r * math.cos(a), r * math.sin(a)
        if i == 0:
            cr.move_to(x, y)
        else:
            cr.line_to(x, y)
    cr.close_path()


def path_diamond(cr, w=0.62, h=1.0):
    cr.move_to(0, -h); cr.line_to(w, 0); cr.line_to(0, h); cr.line_to(-w, 0); cr.close_path()


def _hl(cr, a, mono):
    if mono:
        cr.set_source_rgba(0.08, 0.10, 0.16, a)
    else:
        cr.set_source_rgba(1, 1, 1, a)


def _elem(cr, name, alpha, mono):
    pat = cr.get_source()
    if name == "anemo":
        cr.set_line_width(0.17)
        for k in range(3):
            cr.save(); cr.rotate(k * TAU / 3)
            cr.move_to(0.06, -0.14)
            cr.curve_to(0.5, -0.62, 1.02, -0.12, 0.66, 0.40)
            cr.restore()
        cr.stroke()
        cr.arc(0, 0, 0.15, 0, TAU); cr.fill()
    elif name == "geo":
        cr.set_line_width(0.13)
        cr.move_to(0, -0.95); cr.line_to(0.78, -0.12); cr.line_to(0, 0.95); cr.line_to(-0.78, -0.12); cr.close_path()
        cr.stroke()
        cr.move_to(0, -0.52); cr.line_to(0.38, -0.1); cr.line_to(0, 0.52); cr.line_to(-0.38, -0.1); cr.close_path()
        cr.fill()
        cr.set_line_width(0.07)
        cr.move_to(-0.74, -0.12); cr.line_to(-0.4, -0.1)
        cr.move_to(0.4, -0.1); cr.line_to(0.74, -0.12)
        cr.stroke()
        _hl(cr, 0.55 * alpha, mono)
        cr.move_to(0, -0.52); cr.line_to(0.38, -0.1); cr.line_to(0, -0.1); cr.close_path(); cr.fill()
    elif name == "electro":
        cr.set_line_width(0.12)
        for k in range(3):
            a0 = -PI / 2 + k * TAU / 3 + 0.33
            cr.new_sub_path(); cr.arc(0, 0, 0.8, a0, a0 + TAU / 3 - 0.66)
        cr.stroke()
        for k in range(3):
            a = -PI / 2 + k * TAU / 3
            cr.new_sub_path(); cr.arc(0.8 * math.cos(a), 0.8 * math.sin(a), 0.095, 0, TAU)
        cr.fill()
        cr.move_to(0.15, -0.6); cr.line_to(-0.3, 0.08); cr.line_to(-0.03, 0.08)
        cr.line_to(-0.14, 0.6); cr.line_to(0.31, -0.1); cr.line_to(0.04, -0.1); cr.close_path()
        cr.fill()
    elif name == "dendro":
        cr.save(); cr.rotate(PI / 5)
        cr.move_to(0, -1); cr.curve_to(0.8, -0.5, 0.72, 0.5, 0, 0.95)
        cr.curve_to(-0.72, 0.5, -0.8, -0.5, 0, -1); cr.close_path(); cr.fill()
        cr.set_source_rgba(0.06, 0.12, 0.05, 0.42 * alpha)
        cr.set_line_width(0.07)
        cr.move_to(0, -0.72); cr.line_to(0, 0.82)
        cr.move_to(0, -0.15); cr.line_to(0.32, -0.42)
        cr.move_to(0, 0.18); cr.line_to(-0.32, -0.08)
        cr.move_to(0, 0.48); cr.line_to(0.3, 0.24)
        cr.stroke()
        cr.restore()
    elif name == "hydro":
        cr.move_to(0, -1)
        cr.curve_to(0.35, -0.45, 0.72, -0.05, 0.72, 0.32)
        cr.curve_to(0.72, 0.74, 0.4, 1.0, 0, 1.0)
        cr.curve_to(-0.4, 1.0, -0.72, 0.74, -0.72, 0.32)
        cr.curve_to(-0.72, -0.05, -0.35, -0.45, 0, -1)
        cr.close_path(); cr.fill()
        _hl(cr, 0.7 * alpha, mono)
        cr.set_line_width(0.1)
        cr.arc(0, 0.34, 0.44, PI * 0.62, PI * 1.08); cr.stroke()
        cr.arc(0.2, -0.05, 0.07, 0, TAU); cr.fill()
    elif name == "pyro":
        cr.move_to(0.05, -1)
        cr.curve_to(0.3, -0.5, 0.8, -0.25, 0.72, 0.35)
        cr.curve_to(0.68, 0.8, 0.35, 1.0, 0, 1.0)
        cr.curve_to(-0.4, 1.0, -0.72, 0.75, -0.72, 0.35)
        cr.curve_to(-0.72, 0.0, -0.52, -0.2, -0.42, -0.48)
        cr.curve_to(-0.3, -0.22, -0.2, -0.16, -0.12, -0.22)
        cr.curve_to(-0.16, -0.55, -0.05, -0.8, 0.05, -1)
        cr.close_path(); cr.fill()
        _hl(cr, 0.78 * alpha, mono)
        cr.move_to(0, -0.08)
        cr.curve_to(0.2, 0.2, 0.4, 0.4, 0.38, 0.6)
        cr.curve_to(0.36, 0.86, 0.18, 0.95, 0, 0.95)
        cr.curve_to(-0.18, 0.95, -0.36, 0.86, -0.38, 0.6)
        cr.curve_to(-0.4, 0.4, -0.2, 0.2, 0, -0.08)
        cr.close_path(); cr.fill()
    elif name == "cryo":
        cr.set_line_width(0.12)
        for k in range(6):
            cr.save(); cr.rotate(k * PI / 3)
            cr.move_to(0, -0.22); cr.line_to(0, -0.95)
            cr.move_to(0, -0.56); cr.line_to(0.25, -0.8)
            cr.move_to(0, -0.56); cr.line_to(-0.25, -0.8)
            cr.restore()
        cr.stroke()
        for k in range(6):
            a = k * PI / 3
            x, y = 0.24 * math.cos(a), 0.24 * math.sin(a)
            if k == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.close_path(); cr.fill()
    cr.set_source(pat)


def draw_icon(cr, name, cx, cy, s, color=None, alpha=1.0, rot=0.0):
    """Hand-drawn Genshin-style glyphs in a unit box [-1..1] scaled by s."""
    if s <= 0.05 or alpha <= 0.003:
        return
    cr.save()
    cr.new_path()
    cr.translate(cx, cy)
    if rot:
        cr.rotate(rot)
    cr.scale(s, s)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)

    def col(default=GOLD, a=1.0):
        src(cr, color or default, alpha * a)

    if name in ELEM:
        base, light, _ = ELEM[name]
        if color:
            src(cr, color, alpha)
        else:
            cr.set_source(lin(0, -1, 0, 1, [(0, light, alpha), (1, base, alpha)]))
        _elem(cr, name, alpha, bool(color))
    elif name == "sparkle":
        col(); path_sparkle(cr); cr.fill()
    elif name == "diamond":
        col(); path_diamond(cr, 0.7, 1.0); cr.fill()
    elif name == "star":
        path_star5(cr)
        if color:
            src(cr, color, alpha)
        else:
            cr.set_source(lin(0, -1, 0, 1, [(0, "#FFF0A6", alpha), (0.5, "#FFCC32", alpha), (1, "#E89A1C", alpha)]))
        cr.fill_preserve()
        cr.set_line_width(0.12); cr.set_source_rgba(0.35, 0.22, 0.05, 0.55 * alpha); cr.stroke()
    elif name == "primogem":
        if color:
            col(); path_sparkle(cr, 0.2); cr.fill()
        else:
            cr.set_source(lin(-1, -1, 1, 1, [(0, "#FFF6D8", alpha), (0.5, "#EBCB80", alpha), (1, "#B3843A", alpha)]))
            path_sparkle(cr, 0.2); cr.fill()
            path_diamond(cr, 0.32, 0.52)
            cr.set_source(lin(0, -0.5, 0, 0.5, [(0, "#FFFFFF", alpha), (1, "#8CCBF2", alpha)])); cr.fill()
            cr.set_line_width(0.04); cr.set_source_rgba(1, 1, 1, 0.65 * alpha)
            cr.move_to(0, -0.52); cr.line_to(0, 0.52); cr.move_to(-0.32, 0); cr.line_to(0.32, 0); cr.stroke()
            cr.save(); cr.translate(0.6, -0.62); cr.scale(0.22, 0.22); cr.set_source_rgba(1, 1, 1, 0.95 * alpha)
            path_sparkle(cr, 0.12); cr.fill(); cr.restore()
    elif name == "close":
        col(CREAM); cr.set_line_width(0.1); cr.arc(0, 0, 0.88, 0, TAU); cr.stroke()
        cr.set_line_width(0.14)
        cr.move_to(-0.33, -0.33); cr.line_to(0.33, 0.33); cr.move_to(0.33, -0.33); cr.line_to(-0.33, 0.33); cr.stroke()
    elif name == "confirm":
        src(cr, "#F2B53A", alpha); cr.set_line_width(0.27); cr.arc(0, 0, 0.5, 0, TAU); cr.stroke()
    elif name == "cancel":
        src(cr, "#4CA6E8", alpha); cr.set_line_width(0.25)
        cr.move_to(-0.42, -0.42); cr.line_to(0.42, 0.42); cr.move_to(0.42, -0.42); cr.line_to(-0.42, 0.42); cr.stroke()
    elif name == "plus":
        col(); cr.set_line_width(0.2)
        cr.move_to(0, -0.66); cr.line_to(0, 0.66); cr.move_to(-0.66, 0); cr.line_to(0.66, 0); cr.stroke()
    elif name == "refresh":
        col(); cr.set_line_width(0.16)
        a0, a1 = -PI * 0.32, PI * 1.32
        cr.arc(0, 0, 0.66, a0, a1); cr.stroke()
        ex, ey = 0.66 * math.cos(a1), 0.66 * math.sin(a1)
        tx_, ty_ = -math.sin(a1), math.cos(a1)
        nx, ny = math.cos(a1), math.sin(a1)
        cr.move_to(ex + tx_ * 0.34, ey + ty_ * 0.34)
        cr.line_to(ex + nx * 0.24, ey + ny * 0.24)
        cr.line_to(ex - nx * 0.24, ey - ny * 0.24)
        cr.close_path(); cr.fill()
    elif name in ("lock", "unlock"):
        col(); cr.set_line_width(0.15)
        if name == "lock":
            cr.move_to(-0.36, 0.02); cr.line_to(-0.36, -0.28); cr.arc(0, -0.28, 0.36, PI, TAU); cr.line_to(0.36, 0.02)
        else:
            cr.move_to(-0.36, 0.02); cr.line_to(-0.36, -0.38); cr.arc(0, -0.38, 0.36, PI, 1.95 * PI)
        cr.stroke()
        rrect(cr, -0.62, -0.02, 1.24, 0.98, 0.16); col(); cr.fill()
        _hl(cr, 0.55 * alpha, True); cr.arc(0, 0.4, 0.11, 0, TAU); cr.fill()
    elif name == "wifi":
        col(); cr.set_line_width(0.15)
        for r in (0.36, 0.74, 1.12):
            cr.new_sub_path(); cr.arc(0, 0.62, r, -PI * 0.76, -PI * 0.24)
        cr.stroke()
        cr.arc(0, 0.62, 0.14, 0, TAU); cr.fill()
    elif name == "compass":
        col(); cr.set_line_width(0.06); cr.arc(0, 0, 0.95, 0, TAU); cr.stroke()
        cr.set_line_width(0.035); cr.arc(0, 0, 0.74, 0, TAU); cr.stroke()
        cr.set_line_width(0.05)
        for k in range(8):
            a = k * PI / 4
            cr.move_to(0.74 * math.cos(a), 0.74 * math.sin(a)); cr.line_to(0.84 * math.cos(a), 0.84 * math.sin(a))
        cr.stroke()
        cr.save(); cr.scale(0.64, 0.64); path_sparkle(cr, 0.13); cr.restore(); cr.fill()
        for k in range(4):
            a = k * PI / 2
            cr.save(); cr.translate(0.95 * math.cos(a), 0.95 * math.sin(a)); cr.scale(0.11, 0.11)
            path_diamond(cr, 0.8, 1.0); cr.restore()
        cr.fill()
        _hl(cr, 0.6 * alpha, True); cr.arc(0, 0, 0.1, 0, TAU); cr.fill()
    elif name == "gear":
        col()
        for k in range(8):
            cr.save(); cr.rotate(k * PI / 4); cr.rectangle(-0.14, -0.96, 0.28, 0.4); cr.restore()
        cr.fill()
        cr.set_line_width(0.3); cr.arc(0, 0, 0.5, 0, TAU); cr.stroke()
    elif name == "chart":
        col()
        for i, hh in enumerate((0.55, 0.95, 0.7, 1.5)):
            rrect(cr, -0.86 + i * 0.45, 0.85 - hh, 0.3, hh, 0.07); cr.fill()
    elif name == "book":
        col()
        cr.move_to(-0.06, -0.58); cr.curve_to(-0.35, -0.82, -0.72, -0.78, -0.94, -0.62)
        cr.line_to(-0.94, 0.74); cr.curve_to(-0.72, 0.6, -0.35, 0.62, -0.06, 0.84); cr.close_path(); cr.fill()
        cr.move_to(0.06, -0.58); cr.curve_to(0.35, -0.82, 0.72, -0.78, 0.94, -0.62)
        cr.line_to(0.94, 0.74); cr.curve_to(0.72, 0.6, 0.35, 0.62, 0.06, 0.84); cr.close_path(); cr.fill()
        _hl(cr, 0.4 * alpha, True); cr.set_line_width(0.06)
        for yy in (-0.3, -0.05, 0.2):
            cr.move_to(-0.75, yy); cr.line_to(-0.25, yy + 0.06); cr.move_to(0.25, yy + 0.06); cr.line_to(0.75, yy)
        cr.stroke()
    elif name == "shield":
        col()
        cr.move_to(0, -0.96); cr.curve_to(0.35, -0.76, 0.6, -0.72, 0.82, -0.72); cr.line_to(0.82, -0.05)
        cr.curve_to(0.82, 0.5, 0.42, 0.8, 0, 0.98); cr.curve_to(-0.42, 0.8, -0.82, 0.5, -0.82, -0.05)
        cr.line_to(-0.82, -0.72); cr.curve_to(-0.6, -0.72, -0.35, -0.76, 0, -0.96); cr.close_path(); cr.fill()
        _hl(cr, 0.55 * alpha, True)
        cr.save(); cr.translate(0, -0.02); cr.scale(0.42, 0.42); path_sparkle(cr, 0.14); cr.restore(); cr.fill()
    elif name == "waypoint":
        col()
        cr.new_path(); cr.move_to(0, -1); cr.line_to(0.42, -0.42); cr.line_to(0, 0.16); cr.line_to(-0.42, -0.42); cr.close_path(); cr.fill()
        cr.move_to(-0.64, 0.96); cr.line_to(-0.36, 0.46); cr.line_to(0.36, 0.46); cr.line_to(0.64, 0.96); cr.close_path(); cr.fill()
        cr.set_line_width(0.07); cr.save(); cr.translate(0, 0.32); cr.scale(1, 0.3); cr.arc(0, 0, 0.62, 0, TAU); cr.restore(); cr.stroke()
        _hl(cr, 0.5 * alpha, True); cr.move_to(0, -1); cr.line_to(0.42, -0.42); cr.line_to(0, -0.42); cr.close_path(); cr.fill()
    elif name == "eye":
        col(); cr.set_line_width(0.12)
        cr.move_to(-0.95, 0); cr.curve_to(-0.5, -0.64, 0.5, -0.64, 0.95, 0)
        cr.curve_to(0.5, 0.64, -0.5, 0.64, -0.95, 0); cr.close_path(); cr.stroke()
        cr.arc(0, 0, 0.28, 0, TAU); cr.fill()
    elif name == "copy":
        col(); cr.set_line_width(0.13)
        rrect(cr, -0.75, -0.75, 1.0, 1.1, 0.15); cr.stroke()
        rrect(cr, -0.25, -0.35, 1.0, 1.1, 0.15); cr.fill()
    elif name == "qr":
        col(); cr.set_line_width(0.12)
        for (qx, qy) in ((-0.9, -0.9), (0.2, -0.9), (-0.9, 0.2)):
            rrect(cr, qx + 0.06, qy + 0.06, 0.58, 0.58, 0.08); cr.stroke()
            cr.rectangle(qx + 0.24, qy + 0.24, 0.22, 0.22); cr.fill()
        for (qx, qy) in ((0.25, 0.25), (0.6, 0.25), (0.25, 0.6), (0.6, 0.6), (0.42, 0.42)):
            cr.rectangle(qx, qy, 0.2, 0.2)
        cr.fill()
    elif name == "power":
        col(); cr.set_line_width(0.16)
        cr.arc(0, 0.08, 0.7, -PI / 2 + 0.62, 1.5 * PI - 0.62); cr.stroke()
        cr.move_to(0, -0.9); cr.line_to(0, -0.12); cr.stroke()
    elif name == "key":
        col(); cr.set_line_width(0.15)
        cr.arc(-0.48, 0, 0.36, 0, TAU); cr.stroke()
        cr.move_to(-0.12, 0); cr.line_to(0.92, 0); cr.move_to(0.6, 0); cr.line_to(0.6, 0.34)
        cr.move_to(0.84, 0); cr.line_to(0.84, 0.26); cr.stroke()
    elif name in ("arrow_down", "arrow_up"):
        col(); cr.set_line_width(0.18)
        if name == "arrow_up":
            cr.scale(1, -1)
        cr.move_to(0, -0.82); cr.line_to(0, 0.72)
        cr.move_to(-0.48, 0.26); cr.line_to(0, 0.76); cr.line_to(0.48, 0.26); cr.stroke()
    elif name == "chevron":
        col(); cr.set_line_width(0.2)
        cr.move_to(-0.25, -0.55); cr.line_to(0.3, 0); cr.line_to(-0.25, 0.55); cr.stroke()
    elif name == "hidden":
        col(); cr.set_line_width(0.12)
        cr.move_to(-0.95, 0); cr.curve_to(-0.5, -0.64, 0.5, -0.64, 0.95, 0)
        cr.curve_to(0.5, 0.64, -0.5, 0.64, -0.95, 0); cr.close_path(); cr.stroke()
        cr.arc(0, 0, 0.26, 0, TAU); cr.fill()
        cr.set_line_width(0.14); cr.move_to(-0.8, -0.8); cr.line_to(0.8, 0.8); cr.stroke()
    elif name == "motion":
        col(); cr.set_line_width(0.13)
        for i, yy in enumerate((-0.45, 0.0, 0.45)):
            cr.move_to(-0.9 + i * 0.18, yy); cr.line_to(0.2 + i * 0.18, yy)
        cr.stroke()
        cr.save(); cr.translate(0.55, 0); cr.scale(0.4, 0.4); path_sparkle(cr, 0.14); cr.restore(); cr.fill()
    cr.restore()


def draw_stars(cr, x, y, n, sz, gap=1.5):
    for i in range(int(n)):
        draw_icon(cr, "star", x + sz / 2 + i * (sz + gap), y + sz / 2, sz / 2)


def draw_spinner(cr, cx, cy, r, t, color="#FFF4D6", n=3):
    for k in range(n):
        a = t * 4.2 + k * TAU / n
        for j in range(6):
            aa = a - j * 0.17
            cr.new_path()
            cr.arc(cx + r * math.cos(aa), cy + r * math.sin(aa), max(0.4, 2.3 - j * 0.33), 0, TAU)
            src(cr, color, (1 - j / 6.0) * 0.95)
            cr.fill()
    glow(cr, cx, cy, r * 1.15, color, 0.18 + 0.1 * math.sin(t * 5))


def draw_badge(cr, glyph, cx, cy, r, variant="ink", hv=0.0, t=0.0):
    """Round glyph disc used inside Genshin pill buttons."""
    if hv > 0.01:
        glow(cr, cx, cy, r + 4, "#FFF0C8", 0.45 * hv)
    cr.new_path(); cr.arc(cx, cy, r, 0, TAU)
    if variant == "ink":
        cr.set_source(rad(cx, cy, 0, r, [(0, "#4A5368", 1), (1, "#353C4D", 1)], fy=cy - r * 0.4)); cr.fill()
        gcol = GOLD_HI
    else:
        src(cr, CREAM, 0.10 + 0.08 * hv); cr.fill_preserve(); cr.set_line_width(1); src(cr, GOLD, 0.45 + 0.4 * hv); cr.stroke()
        gcol = GOLD
    rot = hv * 0.5 if glyph in ("gear", "refresh", "compass") else 0.0
    if glyph in ("confirm", "cancel"):
        draw_icon(cr, glyph, cx, cy, r * (0.62 + 0.06 * hv), rot=rot)
    elif glyph in ELEM:
        draw_icon(cr, glyph, cx, cy, r * 0.58, rot=rot)
    else:
        draw_icon(cr, glyph, cx, cy, r * 0.55, gcol, rot=rot)


def draw_orb(cr, w, h, el, active, hv=0.0, t=0.0, kick=99.0):
    cx, cy = w / 2.0, h / 2.0
    r = min(w, h) / 2.0 - 5
    base, light, _ = ELEM[el]
    rr = r * (1 + 0.07 * hv)
    if active:
        br = 0.5 + 0.5 * math.sin(t * 2.4)
        glow(cr, cx, cy, rr + 6, light, 0.40 + 0.28 * br)
    if hv > 0.01:
        glow(cr, cx, cy, rr + 6, "#FFF4D6", 0.32 * hv)
    if 0 <= kick < 0.7:
        k = kick / 0.7
        cr.new_path(); cr.arc(cx, cy, rr + k * 9, 0, TAU)
        cr.set_line_width(2.2 * (1 - k)); src(cr, light, 0.9 * (1 - k)); cr.stroke()
    cr.new_path(); cr.arc(cx, cy, rr, 0, TAU)
    cr.set_source(rad(cx, cy, 0, rr, [(0, "#434C64", 1), (1, "#1C2030", 1)], fy=cy - rr * 0.45)); cr.fill()
    cr.set_line_width(1.7 if active else 1.0)
    cr.arc(cx, cy, rr - 0.5, 0, TAU)
    if active:
        src(cr, GOLD_HI, 1)
    else:
        cr.set_source_rgba(lerp(0.83, 1, hv), lerp(0.74, 1, hv), lerp(0.56, 1, hv), lerp(0.35, 0.85, hv))
    cr.stroke()
    if active:
        cr.set_line_width(1); cr.arc(cx, cy, rr - 3.5, 0, TAU); src(cr, base, 0.8); cr.stroke()
        for k in range(3):
            a = t * 1.5 + k * TAU / 3
            draw_icon(cr, "sparkle", cx + (rr + 1.2) * math.cos(a), cy + (rr + 1.2) * math.sin(a),
                      2.4 + 0.6 * math.sin(t * 3 + k), "#FFFFFF", 0.9)
    bob = math.sin(t * 2.2) * 0.8 if active else 0.0
    draw_icon(cr, el, cx, cy + bob, rr * 0.52 * (1 + 0.08 * hv), None, 1.0 if (active or hv > 0.5) else 0.82 + 0.18 * hv)


def draw_art(cr, w, h, el=None, icon=None, t=0.0):
    cx, cy = w / 2.0, h / 2.0
    R = min(w, h) / 2.0
    light = ELEM[el][1] if el else "#FFF6E3"
    br = 0.5 + 0.5 * math.sin(t * 1.8)
    glow(cr, cx, cy, R, light, (0.42 + 0.16 * br) if el else 0.25)
    cr.set_line_width(1); cr.set_source_rgba(1, 1, 1, 0.25)
    cr.new_path(); cr.arc(cx, cy, R * 0.74, 0, TAU); cr.stroke()
    cr.save(); cr.translate(cx, cy); cr.rotate(t * 0.35)
    cr.set_dash([2, 4]); cr.set_source_rgba(1, 1, 1, 0.24)
    cr.new_path(); cr.arc(0, 0, R * 0.92, 0, TAU); cr.stroke(); cr.set_dash([])
    cr.restore()
    for k in range(4):
        a = k * PI / 2 + PI / 4 - t * 0.5
        draw_icon(cr, "diamond", cx + R * 0.74 * math.cos(a), cy + R * 0.74 * math.sin(a), 2.6, "#FFFFFF", 0.7)
    bob = math.sin(t * 2.0) * R * 0.03
    if icon:
        draw_icon(cr, icon, cx, cy + bob, R * 0.44, "#FFF8EA", 0.95)
    elif el:
        draw_icon(cr, el, cx, cy + bob, R * 0.46)
    else:
        draw_icon(cr, "wifi", cx, cy, R * 0.42, "#FFF8EA", 0.45)
    ph = (t % 3.0) / 3.0
    if el and ph < 0.35:
        k = ph / 0.35
        draw_icon(cr, "sparkle", cx + R * 0.38, cy - R * 0.4, R * 0.16 * math.sin(k * PI), "#FFFFFF", 0.95)


def draw_tile(cr, x, y, w, h, rarity, el, label=None, locked=False, active=False,
              hover=0.0, selected=False, saved=False, t=0.0, busy=False, faint=False):
    strip_h = 22 if label is not None else 0
    lift = 3.0 * hover
    if lift > 0.05:
        cr.new_path(); rrect(cr, x + 4, y + h - 3, w - 8, 6, 3)
        cr.set_source_rgba(0, 0, 0, 0.30 * hover); cr.fill()
    y -= lift
    img_h = h - strip_h
    c0, c1 = RARITY.get(rarity, RARITY[1])
    if selected:
        p = 0.5 + 0.5 * math.sin(t * 3.0)
        glow(cr, x + w / 2, y + h / 2, max(w, h) * 0.75, "#FFE9B0", 0.16 + 0.12 * p)
        rrect(cr, x - 2.5, y - 2.5, w + 5, h + 5, 9); cr.set_line_width(2); src(cr, GOLD_HI, 0.7 + 0.3 * p); cr.stroke()
    if strip_h:
        rrect(cr, x, y, w, h, 7); src(cr, "#E9E5DC"); cr.fill()
    rrect(cr, x, y, w, img_h, (7, 7, 20 if strip_h else 15, 0 if strip_h else 7))
    cr.set_source(lin(x, y, x + w, y + img_h, [(0, c0, 1), (1, c1, 1)]))
    cr.fill_preserve()
    cr.save(); cr.clip()
    glow(cr, x + w * 0.5, y + img_h * 0.42, img_h * 0.6, ELEM[el][1], 0.38 + 0.12 * hover)
    cr.new_path(); cr.move_to(x, y + img_h * 0.22); cr.line_to(x + w * 0.5, y); cr.line_to(x + w * 0.72, y)
    cr.line_to(x, y + img_h * 0.42); cr.close_path(); cr.set_source_rgba(1, 1, 1, 0.07 + 0.05 * hover); cr.fill()
    cr.restore()
    s = min(w, img_h) * (0.25 if strip_h else 0.27) * (1 + 0.06 * hover)
    bob = math.sin(t * 2.3) * 1.2 if active else 0.0
    icx, icy = x + w / 2, y + img_h * (0.43 if rarity else 0.5) + bob
    draw_icon(cr, el, icx, icy, s)
    if busy:
        draw_spinner(cr, icx, icy, s * 1.45, t)
    if rarity:
        ss = min(11.0, w / 6.6)
        total = rarity * ss + (rarity - 1) * 1.0
        draw_stars(cr, x + w / 2 - total / 2, y + img_h - ss - (5 if strip_h else 3), rarity, ss, 1.0)
    if locked:
        draw_icon(cr, "lock", x + w - (10 if strip_h else 8), y + (10 if strip_h else 8), 4.5 if strip_h else 3.6, "#FFFFFF", 0.85)
    if active:
        tw = 1 + 0.25 * math.sin(t * 3.2)
        glow(cr, x + 11, y + 11, 11 * tw, "#FFF4D6", 0.7)
        draw_icon(cr, "sparkle", x + 11, y + 11, (6.5 if strip_h else 5) * tw, "#FFFFFF", rot=t * 0.6)
    elif saved and strip_h:
        draw_icon(cr, "key", x + 11, y + 11, 5, "#FFFFFF", 0.8)
    if faint:
        rrect(cr, x, y, w, img_h, (7, 7, 20 if strip_h else 15, 0 if strip_h else 7))
        cr.set_source_rgba(0.10, 0.11, 0.16, 0.45); cr.fill()
    if strip_h:
        text(cr, label, x + w / 2, y + img_h + 3.5, 10, INK2, bold=True, align="center", max_w=w - 8)
    if hover > 0.01 and not selected:
        rrect(cr, x + 0.75, y + 0.75, w - 1.5, h - 1.5, 7); cr.set_line_width(1.5)
        cr.set_source_rgba(1, 1, 1, 0.9 * hover); cr.stroke()


def draw_tabbar(cr, W, H, tabs, pos, hov, t):
    n = len(tabs)
    tw = (W - 12) / float(n)
    rrect(cr, 0.5, 0.5, W - 1, H - 1, (H - 1) / 2.0)
    src(cr, "#080A12", 0.5); cr.fill_preserve()
    cr.set_line_width(1); src(cr, GOLD, 0.30); cr.stroke()
    cy = H / 2.0
    ix = 6 + pos * tw + tw / 2.0
    r = min(tw, H) / 2.0 - 4
    frac = abs(pos - round(pos))
    stretch = 1 + 0.35 * math.sin(frac * PI)
    glow(cr, ix, cy, r + 8, "#FFF0C8", 0.40 + 0.08 * math.sin(t * 2.5))
    cr.save(); cr.translate(ix, cy); cr.scale(stretch, 1)
    cr.new_path(); cr.arc(0, 0, r, 0, TAU); cr.restore()
    cr.set_source(rad(ix, cy, 0, r * stretch, [(0, "#FFFDF6", 1), (1, CREAM, 1)])); cr.fill_preserve()
    cr.set_line_width(1.2); cr.set_source_rgba(1, 1, 1, 0.95); cr.stroke()
    draw_icon(cr, "diamond", ix, H - 3.2, 2.4, GOLD_HI, 0.9)
    for i, tab in enumerate(tabs):
        icon = tab[1]
        cx = 6 + i * tw + tw / 2.0
        k = clamp(1 - abs(i - pos))
        hv = hov[i] if i < len(hov) else 0.0
        if hv > 0.01 and k < 0.5:
            cr.new_path(); cr.arc(cx, cy, r, 0, TAU); src(cr, CREAM, 0.10 * hv); cr.fill_preserve()
            cr.set_line_width(1); cr.set_source_rgba(1, 1, 1, 0.55 * hv); cr.stroke()
        s = r * 0.5 * (1 + 0.1 * hv + 0.06 * k)
        rot = hv * 0.4 if icon in ("gear", "compass") else 0.0
        if k < 0.999:
            draw_icon(cr, icon, cx, cy, s, GOLD, (0.72 + 0.28 * hv) * (1 - k), rot=rot)
        if k > 0.001:
            draw_icon(cr, icon, cx, cy, s, INK, k, rot=rot)


def draw_divider(cr, w, h, t=0.0):
    cy = int(h / 2) + 0.5
    cx = w / 2.0
    lw = w * 0.44
    cr.set_line_width(1)
    for side in (-1, 1):
        cr.new_path()
        cr.set_source(lin(cx, cy, cx + side * lw, cy, [(0, GOLD, 0.75), (1, GOLD, 0)]))
        cr.move_to(cx + side * 10, cy); cr.line_to(cx + side * lw, cy); cr.stroke()
        draw_icon(cr, "diamond", cx + side * lw * 0.32, cy, 2.4, GOLD, 0.65)
        draw_icon(cr, "diamond", cx + side * 15, cy, 1.8, GOLD, 0.9)
    ph = t % 3.6
    if ph < 1.4:
        k = e_inout(ph / 1.4)
        for side in (-1, 1):
            gx = cx + side * (12 + k * (lw - 12))
            glow(cr, gx, cy, 9, "#FFF6DC", 0.75 * (1 - k))
            draw_icon(cr, "sparkle", gx, cy, 3.2 * (1 - k * 0.6), "#FFFFFF", 0.95 * (1 - k))
    pulse = 1 + 0.12 * math.sin(t * 2.2)
    glow(cr, cx, cy, 10 * pulse, "#FFE9B8", 0.25)
    draw_icon(cr, "diamond", cx, cy, 5.5 * pulse, GOLD)
    draw_icon(cr, "diamond", cx, cy, 2.6, NAVY)


def draw_fade_line(cr, w, h):
    cy = int(h / 2) + 0.5
    cr.new_path(); cr.set_line_width(1)
    cr.set_source(lin(0, 0, w, 0, [(0, GOLD, 0.5), (1, GOLD, 0)]))
    cr.move_to(0, cy); cr.line_to(w, cy); cr.stroke()


def draw_corner_orn(cr, a=0.7):
    """Genshin-like filigree bracket, drawn at origin pointing into +x/+y."""
    cr.new_path(); cr.set_line_width(1.3)
    cr.move_to(0, 52); cr.line_to(0, 16); cr.curve_to(0, 6, 6, 0, 16, 0); cr.line_to(52, 0)
    src(cr, GOLD, a); cr.stroke()
    cr.set_line_width(0.8)
    cr.move_to(6, 34); cr.curve_to(6, 14, 14, 6, 34, 6)
    src(cr, GOLD, a * 0.55); cr.stroke()
    cr.new_path(); cr.arc(17, 17, 5.5, PI * 0.85, PI * 2.35)
    src(cr, GOLD, a * 0.5); cr.stroke()
    draw_icon(cr, "diamond", 9, 9, 3.6, GOLD_HI, a)
    draw_icon(cr, "diamond", 0, 56, 2.2, GOLD, a * 0.8)
    draw_icon(cr, "diamond", 56, 0, 2.2, GOLD, a * 0.8)
    draw_icon(cr, "sparkle", 17, 17, 2.2, GOLD_HI, a * 0.8)


def draw_bg(cr, W, H, m, seed=7):
    """Static frame (cached into an image surface by the window)."""
    cr.save()
    cr.set_operator(cairo.OPERATOR_SOURCE); cr.set_source_rgba(0, 0, 0, 0); cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    x, y, ww, hh = m, m, W - 2 * m, H - 2 * m
    for i in range(m, 0, -1):
        rrect(cr, x - i, y - i + 3, ww + 2 * i, hh + 2 * i, 18 + i)
        cr.set_source_rgba(0, 0, 0, 0.03 * (1 - i / float(m + 1)) ** 1.4); cr.fill()
    rrect(cr, x, y, ww, hh, 18)
    cr.set_source(lin(0, y, 0, y + hh, [(0, "#2E334A", 0.978), (0.45, "#23273A", 0.978), (1, "#181B28", 0.988)]))
    cr.fill_preserve()
    cr.save(); cr.clip()
    glow(cr, x + ww * 0.5, y - 30, ww * 0.78, "#E8D3A2", 0.14)
    glow(cr, x + ww, y + hh, ww * 0.6, "#6FC7B4", 0.07)
    glow(cr, x, y + hh * 0.6, ww * 0.45, "#8C7BD9", 0.05)
    wx, wy, wr = x + ww - 70, y + 70, min(ww, hh) * 0.36
    cr.set_line_width(1)
    for rr, a in ((wr, 0.07), (wr * 0.78, 0.05), (wr * 0.45, 0.05)):
        cr.new_path(); cr.arc(wx, wy, rr, 0, TAU); src(cr, GOLD, a); cr.stroke()
    for k in range(12):
        a = k * TAU / 12
        cr.move_to(wx + wr * 0.78 * math.cos(a), wy + wr * 0.78 * math.sin(a))
        cr.line_to(wx + wr * math.cos(a), wy + wr * math.sin(a))
    src(cr, GOLD, 0.05); cr.stroke()
    draw_icon(cr, "sparkle", wx, wy, wr * 0.42, GOLD, 0.05)
    rnd = random.Random(seed * 1000 + int(ww) * 7 + int(hh))
    pts = [(x + 30 + rnd.random() * ww * 0.35, y + hh * 0.55 + rnd.random() * hh * 0.4) for _ in range(6)]
    cr.set_line_width(0.8)
    cr.new_path()
    for i, (px, py) in enumerate(pts):
        (cr.move_to if i == 0 else cr.line_to)(px, py)
    src(cr, GOLD_HI, 0.07); cr.stroke()
    for px, py in pts:
        glow(cr, px, py, 6, "#FFF3D0", 0.25)
        draw_icon(cr, "sparkle", px, py, 2.2, "#FFF3D0", 0.35)
    n = int(ww * hh / 2600)
    for _ in range(n):
        px, py = x + rnd.random() * ww, y + rnd.random() * hh
        rr = 0.4 + rnd.random() * 1.0
        cr.new_path(); cr.arc(px, py, rr, 0, TAU); src(cr, "#FFF6E0", 0.05 + rnd.random() * 0.24); cr.fill()
    for _ in range(max(3, n // 18)):
        px, py = x + rnd.random() * ww, y + rnd.random() * hh
        draw_icon(cr, "sparkle", px, py, 2.0 + rnd.random() * 2.6, "#FFF1CC", 0.16 + rnd.random() * 0.28)
    cr.restore()
    cr.set_line_width(1)
    rrect(cr, x + 0.5, y + 0.5, ww - 1, hh - 1, 18)
    cr.set_source(lin(0, y, 0, y + hh, [(0, GOLD_HI, 0.75), (0.5, GOLD, 0.45), (1, GOLD, 0.6)])); cr.stroke()
    rrect(cr, x + 5.5, y + 5.5, ww - 11, hh - 11, 14); src(cr, GOLD, 0.14); cr.stroke()
    for (ox, oy, sx, sy) in ((x + 7, y + 7, 1, 1), (x + ww - 7, y + 7, -1, 1),
                             (x + 7, y + hh - 7, 1, -1), (x + ww - 7, y + hh - 7, -1, -1)):
        cr.save(); cr.translate(ox, oy); cr.scale(sx, sy); draw_corner_orn(cr, 0.7); cr.restore()
    tx_ = x + ww / 2.0
    for side in (-1, 1):
        cr.new_path(); cr.set_source(lin(tx_, 0, tx_ + side * 80, 0, [(0, GOLD_HI, 0.9), (1, GOLD_HI, 0)]))
        cr.set_line_width(1.4); cr.move_to(tx_ + side * 8, y + 0.7); cr.line_to(tx_ + side * 80, y + 0.7); cr.stroke()
        cr.new_path(); cr.set_line_width(1)
        cr.arc(tx_ + side * 20, y + 0.7, 7, 0 if side > 0 else PI / 2, PI / 2 if side > 0 else PI)
        src(cr, GOLD_HI, 0.55); cr.stroke()
        cr.new_path(); cr.set_source(lin(tx_, 0, tx_ + side * 50, 0, [(0, GOLD, 0.6), (1, GOLD, 0)]))
        cr.move_to(tx_ + side * 6, y + hh - 0.7); cr.line_to(tx_ + side * 50, y + hh - 0.7); cr.stroke()
    draw_icon(cr, "diamond", tx_, y + 0.7, 5, "#2D3248")
    cr.set_line_width(1.2); cr.save(); cr.translate(tx_, y + 0.7); cr.scale(3.6, 5); path_diamond(cr, 1, 1); cr.restore()
    src(cr, GOLD_HI, 1); cr.stroke()
    draw_icon(cr, "diamond", tx_, y + hh - 0.7, 3.2, GOLD, 0.9)
    cr.restore()


def draw_shimmer(cr, w, h, t, radius=12, period=4.6, dur=1.1):
    ph = t % period
    if ph > dur:
        return
    k = e_inout(ph / dur)
    x = -w * 0.5 + k * w * 2.0
    rrect(cr, 0, 0, w, h, (radius, radius, 0, 0))
    cr.save(); cr.clip()
    g = cairo.LinearGradient(x - 70, 0, x + 10, h)
    g.add_color_stop_rgba(0, 1, 1, 1, 0)
    g.add_color_stop_rgba(0.5, 1, 0.98, 0.9, 0.24)
    g.add_color_stop_rgba(1, 1, 1, 1, 0)
    cr.set_source(g); cr.paint()
    cr.restore()


def draw_radar(cr, w, h, t):
    cx, cy = w / 2.0, h / 2.0
    R = min(w, h) / 2.0 - 4
    glow(cr, cx, cy, R, "#FFF0C8", 0.12)
    for k in range(3):
        ph = (t * 0.55 + k / 3.0) % 1.0
        cr.new_path(); cr.arc(cx, cy, R * ph, 0, TAU)
        cr.set_line_width(1.4); src(cr, GOLD_HI, 0.6 * (1 - ph)); cr.stroke()
    cr.set_line_width(1); src(cr, GOLD, 0.25)
    cr.new_path(); cr.arc(cx, cy, R, 0, TAU); cr.stroke()
    a0 = t * 2.2
    for j in range(14):
        aa = a0 - j * 0.07
        cr.new_path(); cr.move_to(cx, cy); cr.arc(cx, cy, R, aa - 0.07, aa); cr.close_path()
        src(cr, GOLD_HI, 0.22 * (1 - j / 14.0)); cr.fill()
    rnd = random.Random(5)
    for i in range(5):
        ba, br = rnd.random() * TAU, R * (0.3 + rnd.random() * 0.6)
        d = (a0 - ba) % TAU
        if d < 1.6:
            a = 1 - d / 1.6
            draw_icon(cr, "sparkle", cx + br * math.cos(ba), cy + br * math.sin(ba), 3.4 * a + 1, "#FFFFFF", a)
    draw_icon(cr, "compass", cx, cy, R * 0.3, GOLD, 0.9, rot=-t * 0.6)


def smooth_path(cr, pts, ymin, ymax):
    cr.move_to(*pts[0])
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, min(ymax, max(ymin, p1[1] + (p2[1] - p0[1]) / 6.0)))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, min(ymax, max(ymin, p2[1] - (p3[1] - p1[1]) / 6.0)))
        cr.curve_to(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])


def fmt_speed(kb):
    if kb >= 1024:
        return f"{kb / 1024.0:.1f} MB/s"
    return f"{kb:.0f} KB/s"


def draw_traffic(cr, W, H, rx, tx, frac=1.0, t=0.0):
    text(cr, "LEY LINE FLOW", 6, 4, 9, GOLD, bold=True, spacing=2.2)
    rnow = lerp(rx[-2], rx[-1], frac)
    tnow = lerp(tx[-2], tx[-1], frac)
    w1, _ = text(cr, fmt_speed(tnow), W - 6, 1, 12, "#F2C98A", family=MONO, bold=True, align="right")
    draw_icon(cr, "arrow_up", W - 6 - w1 - 9, 9, 5, "#F2C98A")
    x2 = W - 6 - w1 - 26
    w2, _ = text(cr, fmt_speed(rnow), x2, 1, 12, "#8FE3C8", family=MONO, bold=True, align="right")
    draw_icon(cr, "arrow_down", x2 - w2 - 9, 9, 5, "#8FE3C8")
    gx, gy, gw, gh = 6, 30, W - 12, H - 30 - 20
    if gw < 20 or gh < 10:
        return
    cr.set_line_width(1); cr.set_dash([2, 5])
    for i in range(4):
        yy = int(gy + gh * i / 3.0) + 0.5
        cr.new_path(); cr.move_to(gx, yy); cr.line_to(gx + gw, yy); src(cr, GOLD, 0.10); cr.stroke()
    cr.set_dash([])
    mx = max(max(rx), max(tx), 32.0) * 1.15
    n = len(rx)
    step = gw / float(max(1, n - 2))
    cr.save(); cr.rectangle(gx, gy - 6, gw, gh + 12); cr.clip()

    def pts(hist):
        return [(gx + gw + (i - (n - 1)) * step + (1 - frac) * step,
                 gy + gh - min(1.0, v / mx) * gh) for i, v in enumerate(hist)]
    for hist, c in ((tx, "#E8B866"), (rx, "#6FD0B0")):
        p = pts(hist)
        cr.new_path(); smooth_path(cr, p, gy, gy + gh)
        cr.line_to(p[-1][0], gy + gh); cr.line_to(p[0][0], gy + gh); cr.close_path()
        cr.set_source(lin(0, gy, 0, gy + gh, [(0, c, 0.30), (1, c, 0.0)])); cr.fill()
        cr.new_path(); smooth_path(cr, p, gy, gy + gh)
        cr.set_line_width(2); cr.set_line_join(cairo.LINE_JOIN_ROUND); src(cr, c, 0.95); cr.stroke()
    cr.restore()
    for hist, c in ((tx, "#E8B866"), (rx, "#6FD0B0")):
        v = lerp(hist[-2], hist[-1], frac)
        lx, ly = gx + gw, gy + gh - min(1.0, v / mx) * gh
        glow(cr, lx, ly, 9 + 2 * math.sin(t * 4), c, 0.75)
        cr.new_path(); cr.arc(lx, ly, 2.6, 0, TAU); src(cr, "#FFFFFF", 0.95); cr.fill()
    text(cr, f"peak  {fmt_speed(mx / 1.15)}", 6, H - 15, 9, "#7D8496")
    text(cr, "last 60 s", W - 6, H - 15, 9, "#7D8496", align="right")


_DISC = {}
_TICKS = [(math.cos(i / 72.0 * TAU - PI / 2), math.sin(i / 72.0 * TAU - PI / 2)) for i in range(72)]


def draw_dial(cr, W, H, sig, con, t=0.0, intro=1.0):
    cx, cy = W / 2.0, H / 2.0
    R = min(W, H) / 2.0 - 16
    sp = _DISC.get(R)
    if sp is None:
        c0 = R + 13
        n = int(math.ceil(c0 * 2))
        sp = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
        c = cairo.Context(sp)
        c.arc(n / 2.0, n / 2.0, R + 12, 0, TAU)
        c.set_source(rad(n / 2.0, n / 2.0, 0, R + 12, [(0, "#343C5A", 0.9), (0.72, "#1F2338", 0.55), (1, "#1F2338", 0)]))
        c.fill()
        sp.flush()
        if len(_DISC) > 6:
            _DISC.clear()
        _DISC[R] = sp
    cr.set_source_surface(sp, cx - sp.get_width() / 2.0, cy - sp.get_height() / 2.0)
    cr.paint()
    cr.set_line_width(1); cr.new_path(); cr.arc(cx, cy, R + 9, 0, TAU); src(cr, GOLD, 0.35); cr.stroke()
    cr.save(); cr.translate(cx, cy); cr.rotate(-t * 0.12)
    cr.set_dash([2, 9]); cr.set_line_width(1.2); cr.new_path(); cr.arc(0, 0, R + 13, 0, TAU); src(cr, GOLD_HI, 0.3); cr.stroke()
    cr.set_dash([]); cr.restore()
    cr.save(); cr.translate(cx, cy); cr.rotate(t * 0.05)
    for long_, alpha in ((True, 0.55), (False, 0.18)):
        cr.new_path()
        r1, r2 = R + 3, R + (8 if long_ else 5)
        for i, (ca, sa) in enumerate(_TICKS):
            if (i % 6 == 0) == long_:
                cr.move_to(r1 * ca, r1 * sa); cr.line_to(r2 * ca, r2 * sa)
        src(cr, GOLD, alpha); cr.stroke()
    cr.restore()
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_width(7); cr.new_path(); cr.arc(cx, cy, R - 6, 0, TAU); src(cr, GOLD, 0.10); cr.stroke()
    val = sig * intro if con else 0
    if con and val > 0.3:
        a1 = -PI / 2 + TAU * min(100, val) / 100.0
        cr.set_line_width(16); cr.new_path(); cr.arc(cx, cy, R - 6, -PI / 2, a1); src(cr, "#FFE7A8", 0.10); cr.stroke()
        cr.set_line_width(7); cr.new_path(); cr.arc(cx, cy, R - 6, -PI / 2, a1)
        cr.set_source(lin(cx - R, cy - R, cx + R, cy + R, [(0, "#FFF3D0", 1), (1, "#C9974A", 1)])); cr.stroke()
        hx_, hy_ = cx + (R - 6) * math.cos(a1), cy + (R - 6) * math.sin(a1)
        glow(cr, hx_, hy_, 14 + 3 * math.sin(t * 3.4), "#FFF4D6", 0.85)
        draw_icon(cr, "sparkle", hx_, hy_, 7 + 1.2 * math.sin(t * 3.4), "#FFFFFF", rot=t * 0.8)
    lvl = int(round(val / 100.0 * 6)) if con else 0
    rr = R * 0.62
    nodes = [(cx + rr * math.cos(-PI / 2 + k * PI / 3), cy + rr * math.sin(-PI / 2 + k * PI / 3)) for k in range(6)]
    for k in range(6):
        a, b = nodes[k], nodes[(k + 1) % 6]
        lit = (k + 1) < lvl or lvl == 6
        cr.new_path(); cr.move_to(*a); cr.line_to(*b)
        cr.set_line_width(1.3 if lit else 0.8)
        src(cr, GOLD_HI if lit else GOLD, (0.55 + 0.2 * math.sin(t * 2 + k)) if lit else 0.13); cr.stroke()
    for k, (nx, ny) in enumerate(nodes):
        if k < lvl:
            tw = 0.5 + 0.5 * math.sin(t * 2.6 + k * 1.1)
            glow(cr, nx, ny, 12 + 3 * tw, "#FFE7A8", 0.45 + 0.25 * tw)
            draw_icon(cr, "sparkle", nx, ny, 6 + 1.6 * tw, "#FFF8E6")
        else:
            cr.new_path(); cr.arc(nx, ny, 3.2, 0, TAU); src(cr, "#8E95A6", 0.35); cr.fill()
            cr.set_line_width(1); cr.arc(nx, ny, 6, 0, TAU); src(cr, GOLD, 0.2); cr.stroke()
    text(cr, f"{int(round(val))}%" if con else "—", cx, cy - 30, 34, CREAM, family=SERIF, bold=True, align="center")
    text(cr, "SIGNAL", cx, cy + 14, 9, GOLD, bold=True, align="center", spacing=2.5)
    text(cr, f"Constellation  C{lvl}", cx, cy + 29, 10, "#A5ABBA", align="center")


def draw_dns_card(cr, w, h, name, ips, el, fa, en, active, hv=0.0, t=0.0, kick=99.0):
    lift = 4 * hv
    x, y, ww, hh = 4, 6 - lift, w - 8, h - 12
    base, light, ename = ELEM[el]
    cx = x + ww / 2.0
    if hv > 0.01:
        rrect(cr, x + 6, y + hh + lift - 2, ww - 12, 6, 3); cr.set_source_rgba(0, 0, 0, 0.3 * hv); cr.fill()
    if active:
        glow(cr, cx, y + hh / 2, max(ww, hh) * 0.7, light, 0.14 + 0.08 * math.sin(t * 2))
    rrect(cr, x, y, ww, hh, (10, 10, 24, 10))
    cr.set_source(lin(0, y, 0, y + hh, [(0, base, 0.62 + 0.15 * hv), (0.5, "#262B3E", 0.97), (1, "#1A1D2B", 0.98)]))
    cr.fill_preserve()
    cr.save(); cr.clip()
    glow(cr, cx, y + 54, 64, light, 0.32 + 0.12 * hv)
    draw_icon(cr, el, x + ww - 16, y + hh - 26, 34, light, 0.07, rot=t * 0.1 if active else 0)
    if active:
        draw_shimmer(cr, ww + 2 * x, hh + 2 * y, t + 1.3, 10, 3.8, 1.2)
    cr.restore()
    cr.save(); cr.translate(cx - 32, y + 22); draw_orb(cr, 64, 64, el, active, hv, t, kick); cr.restore()
    text(cr, name, cx, y + 92, 15, CREAM, family=SERIF, bold=True, align="center", max_w=ww - 10)
    text(cr, ename.upper(), cx, y + 114, 8.5, light, bold=True, align="center", spacing=2.4)
    cr.set_line_width(1); cr.new_path()
    cr.set_source(lin(x + 14, 0, x + ww - 14, 0, [(0, GOLD, 0), (0.5, GOLD, 0.5), (1, GOLD, 0)]))
    cr.move_to(x + 14, y + 132.5); cr.line_to(x + ww - 14, y + 132.5); cr.stroke()
    draw_icon(cr, "diamond", cx, y + 132.5, 3, GOLD)
    text(cr, en, cx, y + 140, 10, "#C3C7D2", align="center", max_w=ww - 10)
    if fa:
        text(cr, fa, cx, y + 156, 10.5, GOLD, align="center", max_w=ww - 10)
    text(cr, ips.split()[0] if ips else "DHCP", cx, y + hh - 22, 9.5, "#8E95A6", family=MONO, align="center")
    rrect(cr, x + 0.5, y + 0.5, ww - 1, hh - 1, (10, 10, 24, 10))
    if active:
        cr.set_line_width(2); src(cr, GOLD_HI, 1)
    else:
        cr.set_line_width(1 + 0.5 * hv)
        cr.set_source_rgba(lerp(0.83, 1, hv), lerp(0.74, 1, hv), lerp(0.56, 1, hv), lerp(0.28, 0.85, hv))
    cr.stroke()
    if active:
        rrect(cr, cx - 36, y - 1, 72, 15, 7.5); src(cr, CREAM); cr.fill()
        text(cr, "RESONATING", cx, y + 0.5, 8, INK, bold=True, align="center", spacing=1.2)


def paint_gem(cr, w, h, t):
    cx, cy = w / 2.0, h / 2.0 + math.sin(t * 2.0) * 1.6
    glow(cr, cx, cy, w / 2.0, "#FFE7B0", 0.22 + 0.12 * math.sin(t * 2.0 + 1))
    draw_icon(cr, "primogem", cx, cy, w * 0.36)
    for k in range(2):
        a = t * 1.3 + k * PI
        draw_icon(cr, "sparkle", cx + math.cos(a) * w * 0.42, cy + math.sin(a) * w * 0.18,
                  1.6 + 0.8 * math.sin(t * 3 + k), "#FFFFFF", 0.55 + 0.4 * math.sin(a) ** 2)


def paint_logo(cr, w, h, t):
    cx, cy = w / 2.0, h / 2.0
    glow(cr, cx, cy, w / 2.0, "#FFE7B0", 0.18 + 0.08 * math.sin(t * 1.7))
    draw_icon(cr, "compass", cx, cy, w * 0.42, GOLD, rot=t * 0.25)
    draw_icon(cr, "sparkle", cx, cy, w * 0.14, GOLD_HI, rot=-t * 0.6)
# <<< DRAW-END


_FD = {}


def _font(family, size, bold, italic):
    k = (family, size, bold, italic)
    fd = _FD.get(k)
    if fd is None:
        if len(_FD) > 96:
            _FD.clear()
        fd = Pango.FontDescription()
        fd.set_family(family)
        fd.set_weight(Pango.Weight.BOLD if bold else Pango.Weight.NORMAL)
        fd.set_absolute_size(size * Pango.SCALE)
        if italic:
            fd.set_style(Pango.Style.ITALIC)
        _FD[k] = fd
    return fd


_LC = {}


def _layout(cr, s, size, family, bold, italic, spacing, max_w):
    key = (str(s), size, family, bold, italic, spacing, max_w)
    hit = _LC.get(key)
    if hit is not None:
        PangoCairo.update_layout(cr, hit)
        return hit
    if len(_LC) > 500:
        _LC.clear()
    layout = _LC[key] = PangoCairo.create_layout(cr)
    layout.set_auto_dir(False)
    layout.set_font_description(_font(family or SANS, size, bold, italic))
    if spacing:
        try:
            al = Pango.AttrList()
            al.insert(Pango.attr_letter_spacing_new(int(spacing * Pango.SCALE)))
            layout.set_attributes(al)
        except Exception:
            pass
    layout.set_text(str(s), -1)
    if max_w:
        layout.set_width(int(max_w * Pango.SCALE))
        layout.set_ellipsize(Pango.EllipsizeMode.END)
    return layout


def text(cr, s, x, y, size=11, color=CREAM, alpha=1.0, family=None, bold=False,
         align="left", max_w=None, italic=False, spacing=0):
    layout = _layout(cr, s, size, family, bold, italic, spacing, max_w)
    w, h = layout.get_pixel_size()
    if align == "center":
        x -= w / 2.0
    elif align == "right":
        x -= w
    src(cr, color, alpha)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return w, h


def measure(s, size, family=None, bold=False, spacing=0):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    cr = cairo.Context(surf)
    return _layout(cr, s, size, family, bold, False, spacing, None).get_pixel_size()


def text_gold(cr, s, x, y, size, family=SERIF, t=0.0, period=5.0, dur=1.2):
    """Serif title filled with a gold gradient, plus a periodic light sweep."""
    layout = _layout(cr, s, size, family, True, False, 0, None)
    w, h = layout.get_pixel_size()
    cr.save()
    cr.move_to(x, y + 1.2)
    PangoCairo.layout_path(cr, layout)
    cr.set_source_rgba(0, 0, 0, 0.45); cr.fill()
    cr.new_path(); cr.move_to(x, y)
    PangoCairo.layout_path(cr, layout)
    cr.set_source(lin(0, y, 0, y + h, [(0, "#FFF7E4", 1), (0.55, "#F2E1B5", 1), (1, "#C9A867", 1)]))
    cr.fill_preserve()
    ph = t % period
    if ph < dur:
        k = e_inout(ph / dur)
        sx = x - 60 + k * (w + 120)
        g = cairo.LinearGradient(sx - 30, y, sx + 30, y + h)
        g.add_color_stop_rgba(0, 1, 1, 1, 0)
        g.add_color_stop_rgba(0.5, 1, 1, 1, 0.9)
        g.add_color_stop_rgba(1, 1, 1, 1, 0)
        cr.set_source(g); cr.fill()
    cr.new_path()
    cr.restore()
    return w, h


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CSS — TEYVAT THEME
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CSS = b"""
window { background-color: transparent; }
label { color: #ECE5D8; font-family: "Noto Sans", "Vazirmatn", "Inter", sans-serif; }

@keyframes cel-breathe {
    from { box-shadow: 0 0 0 0 rgba(242,225,181,0.0); }
    to   { box-shadow: 0 0 10px 1px rgba(242,225,181,0.55); }
}
@keyframes cel-busy {
    from { background-color: rgba(168,107,217,0.16); border-color: rgba(230,201,255,0.35); }
    to   { background-color: rgba(168,107,217,0.48); border-color: rgba(230,201,255,0.95); }
}
@keyframes cel-rowbusy {
    from { border-color: rgba(168,107,217,0.25); }
    to   { border-color: rgba(230,201,255,0.85); }
}

.eyebrow { color: #D3BC8E; font-size: 9px; font-weight: 800; letter-spacing: 2px; }
.title-lg, .page-title, .hero-name, .ph-title {
    font-family: "HYWenHei 85W", "HYWenHei", "Noto Serif", "DejaVu Serif", serif;
}
.page-title { color: #F2E1B5; font-size: 16px; font-weight: 700; }
.muted { color: #A5ABBA; font-size: 11px; }
.tiny { color: #8E95A6; font-size: 10px; font-weight: 600; }
.orb-name { color: #8E95A6; font-size: 9px; font-weight: 700; transition: color 300ms ease; }
.orb-name.on { color: #F2E1B5; }
.net-name { color: #ECE5D8; font-size: 12.5px; font-weight: 700; }
.net-name.faint { color: #9AA0AE; }
.meta { color: #8E95A6; font-size: 10px; }
.hero-name { color: #FFFFFF; font-size: 17px; font-weight: 700; text-shadow: 0 1px 3px rgba(0,0,0,0.45); }
.hero-type { color: rgba(255,255,255,0.88); font-size: 10.5px; font-weight: 600; }
.hero-rarity { color: rgba(255,255,255,0.72); font-size: 9px; font-weight: 800; letter-spacing: 2px; }
.ink { color: #6A7181; font-size: 11px; font-weight: 600; }
.ink-b { color: #3B4354; font-size: 11.5px; font-weight: 800; }
.akey { color: #B9BDC8; font-size: 11px; }
.aval { color: #ECE5D8; font-size: 11.5px; font-weight: 700; }
.flavor { color: #8A8476; font-size: 10.5px; font-style: italic; }
.flavor-dark { color: #9A9FAD; font-size: 10.5px; font-style: italic; }
.pw-title { color: #ECE5D8; font-size: 11.5px; }
.ph-title { color: #D9D2C3; font-size: 13.5px; font-weight: 700; }
.pref-title { color: #ECE5D8; font-size: 12px; font-weight: 700; }
.pref-sub { color: #8E95A6; font-size: 10px; }
.chip {
    background-color: rgba(236,229,216,0.07); border: 1px solid rgba(211,188,142,0.20);
    border-radius: 10px; padding: 2px 9px; color: #D9D2C3; font-size: 10px; font-weight: 700;
}
.badge { border-radius: 9px; padding: 1px 7px; font-size: 8.5px; font-weight: 800; letter-spacing: 1px; }
.badge.on {
    background-color: rgba(211,188,142,0.25); border: 1px solid rgba(242,225,181,0.75); color: #F2E1B5;
    animation: cel-breathe 1.6s ease-in-out infinite alternate;
}
.badge.saved { background-color: rgba(236,229,216,0.07); border: 1px solid rgba(236,229,216,0.22); color: #B9B2A4; }
.badge.faint { background-color: transparent; border: 1px dashed rgba(165,171,186,0.45); color: #8E95A6; }
.badge.busy {
    border: 1px solid rgba(230,201,255,0.6); color: #F1E2FF;
    animation: cel-busy 0.8s ease-in-out infinite alternate;
}

.hero-top { border-radius: 12px 12px 0 0; padding: 12px 10px 10px 14px; transition: background-image 400ms ease; }
.hero-top.big { border-radius: 14px 14px 0 0; padding: 16px 12px 14px 16px; }
.r5 { background-image: linear-gradient(125deg, #6E4A35 0%, #A8713A 55%, #D79B4A 100%); }
.r4 { background-image: linear-gradient(125deg, #4E4772 0%, #7D63A3 55%, #A985C8 100%); }
.r3 { background-image: linear-gradient(125deg, #3E5378 0%, #4A79A6 55%, #58A2C9 100%); }
.r2 { background-image: linear-gradient(125deg, #3F5C56 0%, #4E7F68 55%, #5FA07F 100%); }
.r1 { background-image: linear-gradient(125deg, #4F535C 0%, #6A6D75 55%, #8A8C92 100%); }
.r0 { background-image: linear-gradient(125deg, #343844 0%, #444955 55%, #575C68 100%); }
.hero-bottom { background-color: #ECE5D8; border-radius: 0 0 12px 12px; padding: 7px 8px 9px 8px; }
.hero-bottom.big { border-radius: 0 0 14px 14px; padding: 10px 10px 12px 10px; }
.hero-bottom label { color: #495366; }
.hero-bottom .ink-b { color: #3B4354; }
.hero-bottom .flavor { color: #8A8476; }

.panel { background-color: rgba(10,12,20,0.40); border: 1px solid rgba(211,188,142,0.18); border-radius: 14px; padding: 12px; }
.panel.tight { padding: 6px; }
.pw-card { background-color: rgba(10,12,20,0.58); border: 1px solid rgba(211,188,142,0.42); border-radius: 14px; padding: 8px 10px; }
.toast {
    background-color: rgba(22,25,38,0.97); border: 1px solid rgba(211,188,142,0.80);
    border-radius: 22px; padding: 6px 16px 6px 7px; box-shadow: 0 6px 18px rgba(0,0,0,0.5);
}
.toast label { color: #ECE5D8; font-size: 11.5px; font-weight: 700; }
.row-static {
    background-color: rgba(236,229,216,0.045); border: 1px solid rgba(211,188,142,0.14); border-radius: 12px; padding: 7px 10px;
    transition: all 200ms ease;
}
.row-static:hover { border-color: rgba(242,225,181,0.45); background-color: rgba(236,229,216,0.08); }
.row-static.alt { background-color: rgba(236,229,216,0.075); }
.row-static.on { border-color: rgba(242,225,181,0.7); background-image: linear-gradient(90deg, rgba(211,188,142,0.22), rgba(211,188,142,0.03)); }

button { background-image: none; box-shadow: none; text-shadow: none; -gtk-icon-shadow: none; min-height: 0; min-width: 0; }
button.flat-x, button.flat-x:hover, button.flat-x:active, button.flat-x:checked, button.flat-x:focus {
    background-color: transparent; background-image: none; border-color: transparent;
    border-width: 0; box-shadow: none; padding: 0; outline-color: transparent;
}
button.g-btn {
    background-color: #ECE5D8; color: #3B4354; border: 2px solid rgba(255,255,255,0);
    border-radius: 22px; padding: 3px 20px 3px 4px; font-weight: 800; font-size: 12px;
    box-shadow: 0 0 0 1px rgba(211,188,142,0.6), 0 3px 8px rgba(0,0,0,0.35);
    transition: all 180ms ease;
}
button.g-btn label { color: #3B4354; font-weight: 800; }
button.g-btn:hover {
    background-color: #FBF7EF; border-color: #FFFFFF;
    box-shadow: 0 0 0 1px rgba(255,255,255,0.95), 0 0 18px rgba(255,236,190,0.7);
}
button.g-btn:active { background-color: #D9D0BF; box-shadow: 0 0 0 1px rgba(211,188,142,0.6), 0 1px 3px rgba(0,0,0,0.35); }
button.g-btn-dark {
    background-color: rgba(59,67,84,0.92); color: #ECE5D8; border: 2px solid rgba(211,188,142,0.38);
    border-radius: 22px; padding: 3px 18px 3px 4px; font-weight: 700; font-size: 12px;
    box-shadow: 0 3px 8px rgba(0,0,0,0.30); transition: all 180ms ease;
}
button.g-btn-dark label { color: #ECE5D8; font-weight: 700; }
button.g-btn-dark:hover { background-color: rgba(78,88,108,0.97); border-color: rgba(255,255,255,0.85); box-shadow: 0 0 16px rgba(255,236,190,0.4); }
button.g-btn-dark:active { background-color: rgba(40,46,60,0.97); }
button.g-btn.sm, button.g-btn-dark.sm { padding: 2px 14px 2px 3px; font-size: 11px; }
button.g-btn.sm label, button.g-btn-dark.sm label { font-size: 11px; }

button.g-row {
    background-color: rgba(236,229,216,0.045); border: 1px solid rgba(211,188,142,0.14);
    border-radius: 12px; padding: 6px 10px 6px 6px; transition: all 200ms ease;
}
button.g-row:hover { background-color: rgba(236,229,216,0.11); border-color: rgba(255,255,255,0.7); box-shadow: 0 0 14px rgba(255,236,190,0.22); }
button.g-row:active { background-color: rgba(236,229,216,0.16); }
button.g-row.on { background-image: linear-gradient(90deg, rgba(211,188,142,0.26), rgba(211,188,142,0.03)); border-color: rgba(242,225,181,0.75); }
button.g-row.busy { animation: cel-rowbusy 0.9s ease-in-out infinite alternate; }
button.g-row.ghost { background-color: transparent; border: 1px dashed rgba(211,188,142,0.38); padding: 8px 10px; }
button.g-row.ghost:hover { border-color: rgba(255,255,255,0.8); background-color: rgba(236,229,216,0.06); }
button.g-row.ghost label { color: #CDBF9F; font-size: 11.5px; font-weight: 700; }

button.attr { background-color: transparent; border: 1px solid transparent; border-radius: 7px; padding: 3px 8px; transition: all 160ms ease; }
button.attr:hover { background-color: rgba(59,67,84,0.08); border-color: rgba(211,188,142,0.7); }
button.attr-dark { background-color: rgba(236,229,216,0.035); border: 1px solid transparent; border-radius: 7px; padding: 5px 10px; transition: all 160ms ease; }
button.attr-dark.alt { background-color: rgba(236,229,216,0.075); }
button.attr-dark:hover { background-color: rgba(236,229,216,0.12); border-color: rgba(242,225,181,0.6); }

button.seg {
    background-color: rgba(59,67,84,0.07); border: 1px solid rgba(184,154,94,0.55); border-radius: 14px;
    padding: 3px 12px; transition: all 180ms ease;
}
button.seg label { color: #495366; font-size: 11px; font-weight: 800; }
button.seg:hover { border-color: #8F7748; background-color: rgba(59,67,84,0.12); }
button.seg:checked { background-color: #3B4354; border-color: #3B4354; box-shadow: 0 0 8px rgba(184,154,94,0.5); }
button.seg:checked label { color: #F2E1B5; }
button.seg.dark { background-color: rgba(236,229,216,0.05); border-color: rgba(211,188,142,0.35); }
button.seg.dark label { color: #CDBF9F; }
button.seg.dark:checked { background-color: #ECE5D8; border-color: #FFFFFF; }
button.seg.dark:checked label { color: #3B4354; }

entry.g-entry {
    background-color: #ECE5D8; background-image: none; color: #3B4354; caret-color: #3B4354;
    border: 2px solid rgba(211,188,142,0.85); border-radius: 18px; padding: 6px 14px;
    box-shadow: none; font-size: 12px; font-weight: 600; transition: all 200ms ease;
}
entry.g-entry:focus { border-color: #FFFFFF; box-shadow: 0 0 12px rgba(255,236,190,0.7); }
entry.g-entry.on-cream { background-color: #FFFFFF; border-color: #CDBB93; }
entry.g-entry.on-cream:focus { border-color: #B89A5E; box-shadow: 0 0 8px rgba(184,154,94,0.45); }
entry.g-entry.err, entry.g-entry.err:focus { border-color: #E06A4A; box-shadow: 0 0 12px rgba(224,106,74,0.7); }
entry.g-entry selection { background-color: #D3BC8E; color: #1E2233; }
entry.g-entry.small { padding: 3px 10px; font-size: 11px; }
entry.g-entry.pw { padding: 3px 12px; border-width: 1px; border-radius: 14px; font-size: 11.5px; min-height: 0; }

switch {
    background-color: rgba(59,67,84,0.95); background-image: none; border: 1px solid rgba(211,188,142,0.55);
    border-radius: 14px; min-width: 46px; min-height: 22px; color: transparent; box-shadow: none;
    transition: all 250ms ease;
}
switch:checked { background-color: #C9AE76; border-color: #F2E1B5; box-shadow: 0 0 10px rgba(242,225,181,0.45); }
switch slider {
    background-color: #ECE5D8; background-image: none; border: 1px solid rgba(255,255,255,0.6);
    border-radius: 50%; min-width: 20px; min-height: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.45);
    transition: all 250ms ease;
}
switch:checked slider { background-color: #FFFFFF; }
switch image { color: transparent; }

scrolledwindow, viewport { background-color: transparent; border-width: 0; }
scrollbar, scrollbar trough { background-color: transparent; border-width: 0; }
scrollbar slider { background-color: rgba(211,188,142,0.35); border-radius: 4px; min-width: 4px; min-height: 30px; border-width: 0; transition: all 200ms ease; }
scrollbar slider:hover { background-color: rgba(242,225,181,0.65); min-width: 6px; }
flowbox, flowboxchild { background-color: transparent; padding: 0; border-width: 0; }
stack { background-color: transparent; }
tooltip, tooltip.background {
    background-color: rgba(30,34,51,0.97); border: 1px solid rgba(211,188,142,0.7); border-radius: 10px;
}
tooltip label { color: #ECE5D8; font-size: 11px; }
"""

DNS_PRESETS = [
    ("Cloudflare",    "1.1.1.1 1.0.0.1",                 "anemo",   "", "Fastest"),
    ("Google",        "8.8.8.8 8.8.4.4",                 "dendro",  "", "Reliable"),
    ("Quad9",         "9.9.9.9 149.112.112.112",         "cryo",    "", "Malware shield"),
    ("OpenDNS",       "208.67.222.222 208.67.220.220",   "pyro",    "", "Phishing filter"),
    ("AdGuard",       "94.140.14.14 94.140.15.15",       "electro", "", "Ad blocking"),
    ("Family",        "185.228.168.168 185.228.169.168", "geo",     "", "CleanBrowsing"),
    ("Auto",          "",                                "hydro",   "", "Router default"),
]

FLAVOR = {
    "anemo": "A free breeze from Mondstadt — the 2.4 GHz wind travels far, slipping through walls and over hills.",
    "electro": "Swift as the Shogun's judgement — 5 GHz strikes fast, but fades beyond stone.",
    "cryo": "A pristine current from Snezhnaya — 6 GHz, crystal-clear and rarely crowded.",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  NETWORK BACKEND (nmcli) — robust discovery + robust attunement
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_ENV = os.environ.copy()
_ENV["LC_ALL"] = "C.UTF-8"


def run_full(args, timeout=8):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=_ENV)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), 1


def run_cmd(args, timeout=8):
    o, e, rc = run_full(args, timeout)
    return (o or e), rc


def notify(title, body=""):
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(["notify-send", "-a", "Celestia Network", "-t", "3000", title, body],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def nm_split(line):
    parts = re.split(r"(?<!\\):", line)
    return [re.sub(r"\\(.)", r"\1", p) for p in parts]


def nm_unescape(s):
    return re.sub(r"\\(.)", r"\1", s)


def band_of(freq):
    f = int("".join(c for c in str(freq).split(".")[0] if c.isdigit()) or "0")
    if f >= 5925:
        return "6 GHz", "cryo"
    if f >= 4900:
        return "5 GHz", "electro"
    if f > 0:
        return "2.4 GHz", "anemo"
    return "—", "anemo"


def rarity_of(sig):
    return 5 if sig >= 80 else 4 if sig >= 60 else 3 if sig >= 40 else 2 if sig >= 20 else 1


def get_wifi_dev():
    out, _ = run_cmd(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"])
    for line in out.splitlines():
        p = nm_split(line)
        if len(p) >= 2 and p[1] == "wifi":
            return p[0]
    return ""


def get_radio_enabled():
    out, _ = run_cmd(["nmcli", "radio", "wifi"])
    return out.strip() == "enabled"


_PROF_CACHE = {}


def get_wifi_profiles(quick=False):
    """[{name, uuid, ssid, mode}] — SSID may differ from the profile name."""
    o, e, rc = run_full(["nmcli", "-t", "-f", "NAME,UUID,TYPE", "connection", "show"])
    res = []
    for line in o.splitlines():
        f = nm_split(line)
        if len(f) < 3:
            continue
        name, uuid, typ = f[0], f[1], f[2]
        if typ not in ("802-11-wireless", "wifi"):
            continue
        if uuid not in _PROF_CACHE and not quick:
            oo, ee, r2 = run_full(["nmcli", "-g", "802-11-wireless.ssid,802-11-wireless.mode", "connection", "show", "uuid", uuid])
            lines = oo.splitlines() if r2 == 0 else []
            ssid = nm_unescape(lines[0]) if lines and lines[0] else name
            mode = lines[1].strip() if len(lines) > 1 else "infrastructure"
            _PROF_CACHE[uuid] = (ssid, mode)
        ssid, mode = _PROF_CACHE.get(uuid, (name, "infrastructure"))
        res.append({"name": name, "uuid": uuid, "ssid": ssid, "mode": mode})
    return res


def gather(*calls):
    """Run several blocking calls (each a (fn, *args) tuple) at the same time."""
    out = [None] * len(calls)

    def run(i, c):
        try:
            out[i] = c[0](*c[1:])
        except Exception as e:
            print("gather:", e, file=sys.stderr)
    ths = [threading.Thread(target=run, args=(i, c), daemon=True) for i, c in enumerate(calls)]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    return out


def get_active_info(dev):
    info = {"connected": False, "ssid": "Disconnected", "conn": "", "signal": 0, "freq": "—", "rate": "—",
            "bssid": "—", "chan": "—", "security": "—", "ip": "—", "gw": "—", "dns": "Auto",
            "dns_cfg": "", "mac": "—"}
    if not dev:
        return info
    (r_dev, r_wifi) = gather(
        (run_cmd, ["nmcli", "-t", "-f", "GENERAL.STATE,GENERAL.CONNECTION,GENERAL.HWADDR,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
                   "device", "show", dev]),
        (run_cmd, ["nmcli", "-t", "--escape", "yes", "-f", "IN-USE,SSID,BSSID,CHAN,FREQ,RATE,SIGNAL,SECURITY",
                   "device", "wifi", "list", "--rescan", "no", "ifname", dev]))
    out, _ = r_dev or ("", 1)
    dns_list = []
    for line in out.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.replace("\\:", ":")
        if k == "GENERAL.STATE" and v.startswith("100"):
            info["connected"] = True
        elif k == "GENERAL.CONNECTION" and v and v != "--":
            info["conn"] = v
            info["ssid"] = v
        elif k == "GENERAL.HWADDR":
            info["mac"] = v
        elif k.startswith("IP4.ADDRESS"):
            info["ip"] = v
        elif k == "IP4.GATEWAY" and v:
            info["gw"] = v
        elif k.startswith("IP4.DNS"):
            dns_list.append(v)
    if dns_list:
        info["dns"] = ", ".join(dns_list)
    wout, _ = r_wifi or ("", 1)
    for line in wout.splitlines():
        f = nm_split(line)
        if len(f) >= 8 and f[0] == "*":
            info["connected"] = True
            info["ssid"] = f[1] or info["ssid"]
            info["bssid"], info["chan"], info["freq"], info["rate"] = f[2], f[3], f[4], f[5]
            try:
                info["signal"] = int(f[6])
            except ValueError:
                info["signal"] = 0
            info["security"] = f[7] if f[7] and f[7] != "--" else "Open"
            break
    if info["conn"]:
        o, rc = run_cmd(["nmcli", "-g", "ipv4.dns", "connection", "show", "id", info["conn"]])
        info["dns_cfg"] = o.strip() if rc == 0 else ""
    return info


def _wifi_list_raw(dev, rescan="no"):
    args = ["nmcli", "-t", "--escape", "yes", "-f", "IN-USE,SIGNAL,SECURITY,FREQ,RATE,CHAN,BSSID,SSID",
            "device", "wifi", "list", "--rescan", rescan]
    if dev:
        args += ["ifname", dev]
    o, e, rc = run_full(args, 30)
    return o if rc == 0 else ""


def _parse_aps(out):
    aps = []
    for line in out.splitlines():
        f = nm_split(line)
        if len(f) < 8:
            continue
        inuse, sig, sec, freq, rate, chan, bssid = f[:7]
        ssid = ":".join(f[7:])
        try:
            s = int(sig)
        except ValueError:
            s = 0
        band, el = band_of(freq)
        aps.append({"active": inuse.strip() == "*", "signal": s, "security": sec if sec and sec != "--" else "Open",
                    "band": band, "elem": el, "freq": freq, "rate": rate, "chan": chan, "bssid": bssid,
                    "ssid": ssid})
    return aps


def _group_aps(aps):
    by, hidden = {}, 0
    for a in aps:
        if not a["ssid"]:
            hidden += 1
            continue
        g = by.get(a["ssid"])
        if g is None:
            g = dict(a)
            g["nodes"] = 1
            g["bands"] = {a["band"]}
            by[a["ssid"]] = g
            continue
        g["nodes"] += 1
        g["bands"].add(a["band"])
        better = a["active"] or (not g["active"] and a["signal"] > g["signal"])
        if better:
            for k in ("signal", "security", "band", "elem", "freq", "rate", "chan", "bssid"):
                g[k] = a[k]
        g["active"] = g["active"] or a["active"]
    nets = []
    for g in by.values():
        g["bands"] = " + ".join(sorted(g["bands"], key=lambda b: ("2.4" not in b, b)))
        nets.append(g)
    return nets, hidden


def kick_scan():
    """Ask the radio to scan right now (fire and forget) so fresh results are waiting
    by the time the window is on screen."""
    try:
        subprocess.Popen(["nmcli", "device", "wifi", "rescan"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        pass


def scan_networks(dev, deep=False, progress=None):
    """deep=True: ask the radio for a fresh scan and keep polling/merging until the
    result is stable — fixes the 'network exists but is not listed' problem."""
    aps = _parse_aps(_wifi_list_raw(dev, "no"))
    if deep:
        run_full(["nmcli", "device", "wifi", "rescan"] + (["ifname", dev] if dev else []), 15)
        idx = {a["bssid"]: a for a in aps}
        stable = 0
        for i in range(14):
            time.sleep(0.5)
            added = 0
            for a in _parse_aps(_wifi_list_raw(dev, "no")):
                if a["bssid"] in idx:
                    idx[a["bssid"]].update(a)
                else:
                    idx[a["bssid"]] = a
                    aps.append(a)
                    added += 1
            if added and progress:
                progress(_group_aps([dict(x) for x in aps]))
            stable = stable + 1 if added == 0 else 0
            if i >= 3 and stable >= 3:
                break
        if not aps:
            aps = _parse_aps(_wifi_list_raw(dev, "yes"))
    return _group_aps(aps)


def channel_counts(nets):
    c = {}
    for n in nets:
        if not n.get("faint"):
            c[n["chan"]] = c.get(n["chan"], 0) + 1
    return c


def list_sockets():
    out, _ = run_cmd(["ss", "-tulnpH"])
    res = []
    for ln in out.splitlines():
        p = ln.split()
        if len(p) < 5:
            continue
        proc = " ".join(p[6:]) if len(p) > 6 else ""
        m = re.search(r'\(\("([^"]+)",pid=(\d+)', proc)
        res.append((p[0].upper(), p[1], p[4], f"{m.group(1)}  ·  {m.group(2)}" if m else "kernel / hidden"))
    return res


AUTH_HINTS = ("secrets were required", "802-11-wireless-security.psk", "psk: property is invalid",
              "no secrets", "wrong password", "4-way handshake", "(7)")


def _is_auth(msg):
    m = (msg or "").lower()
    return any(h in m for h in AUTH_HINTS)


def _uuids():
    o, e, rc = run_full(["nmcli", "-g", "UUID", "connection", "show"])
    return set(o.split()) if rc == 0 else set()


def key_mgmt(sec, pw):
    s = (sec or "").upper()
    if "802.1X" in s or "EAP" in s:
        return "enterprise"
    if not pw:
        return "owe" if "OWE" in s else None
    if "WEP" in s:
        return "wep"
    if "WPA3" in s and "WPA2" not in s and "WPA1" not in s:
        return "sae"
    return "wpa-psk"


def nm_connect(dev, ssid, pw=None, sec="", hidden=False, profile=None):
    """Returns (ok, message, needs_password). Three layers:
       1) saved profile  2) targeted rescan + 'device wifi connect'  3) hand-built profile."""
    ifn = ["ifname", dev] if dev else []
    if profile:
        if pw:
            km = key_mgmt(sec or "WPA2", pw)
            if km in ("wpa-psk", "sae"):
                run_full(["nmcli", "connection", "modify", "id", profile,
                          "802-11-wireless-security.key-mgmt", km, "802-11-wireless-security.psk", pw])
        o, e, rc = run_full(["nmcli", "-w", "30", "connection", "up", "id", profile] + ifn, 40)
        if rc == 0:
            return True, "", False
        msg = e or o
        if _is_auth(msg) or not pw:
            return False, msg, _is_auth(msg)
    km = key_mgmt(sec, pw)
    if km == "enterprise":
        return False, "Enterprise (802.1X) ley line — use the NM editor in Pact Settings", False
    run_full(["nmcli", "device", "wifi", "rescan"] + ifn + ["ssid", ssid], 15)
    time.sleep(2.2 if hidden else 1.4)
    before = _uuids()
    args = ["nmcli", "-w", "30", "device", "wifi", "connect", ssid]
    if pw:
        args += ["password", pw]
    args += ifn
    if hidden:
        args += ["hidden", "yes"]
    o, e, rc = run_full(args, 42)
    if rc == 0:
        return True, "", False
    msg = e or o
    for u in _uuids() - before:
        run_full(["nmcli", "connection", "delete", "uuid", u])
    if _is_auth(msg) and "no network" not in msg.lower():
        return False, msg, True
    names = {p["name"] for p in get_wifi_profiles(quick=True)}
    name, i = ssid, 2
    while name in names:
        name = f"{ssid} ✦{i}"
        i += 1
    add = ["nmcli", "connection", "add", "type", "wifi", "con-name", name] + ifn + \
          ["ssid", ssid, "connection.autoconnect", "yes"]
    if hidden:
        add += ["802-11-wireless.hidden", "yes"]
    if km in ("wpa-psk", "sae"):
        add += ["802-11-wireless-security.key-mgmt", km, "802-11-wireless-security.psk", pw]
    elif km == "wep":
        add += ["802-11-wireless-security.key-mgmt", "none", "802-11-wireless-security.wep-key0", pw,
                "802-11-wireless-security.wep-key-type", "1" if len(pw) in (5, 10, 13, 26) else "2"]
    elif km == "owe":
        add += ["802-11-wireless-security.key-mgmt", "owe"]
    o2, e2, rc2 = run_full(add, 15)
    if rc2 != 0:
        return False, e2 or o2 or msg, False
    o3, e3, rc3 = run_full(["nmcli", "-w", "35", "connection", "up", "id", name] + ifn, 45)
    if rc3 == 0:
        return True, "", False
    run_full(["nmcli", "connection", "delete", "id", name])
    m3 = e3 or o3 or msg
    return False, m3, _is_auth(m3)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WIDGET HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CENTER = Gtk.Align.CENTER


class Canvas(Gtk.DrawingArea):
    """Cairo canvas.  painter(cr, w, h, canvas)
       live   : True / callable(t)->bool  → redrawn by the ambient ticker while mapped
       intro  : "rise" | "pop"           → entrance animation (drawn, no relayout)"""

    def __init__(self, painter, w=-1, h=-1, live=None, intro=None, delay=0.0, dur=0.5):
        super().__init__()
        self.painter = painter
        self.hv = 0.0
        self._ht = False
        self.p = 1.0
        self.kind = intro
        self.pulse = -99.0
        self.live = live
        self.born = M.now()
        self._dead = False
        self.set_size_request(w, h)
        self.connect("draw", self._on_draw)
        self.connect("destroy", self._on_destroy)
        if live is not None:
            self.connect("map", lambda *_: M.watch(self))
            self.connect("unmap", lambda *_: M.unwatch(self))
        if intro and M.enabled:
            self.play(delay, dur)

    def play(self, delay=0.0, dur=0.5):
        if not self.kind or not M.enabled:
            return
        self.born = M.now() + delay
        M.tween(dur, self._setp, delay=delay, ease=e_lin if self.kind == "pop" else e_out,
                key=(id(self), "p"), owner=self)

    def _on_destroy(self, *_):
        self._dead = True
        M.kill(self)

    def _amb(self, t):
        lv = self.live
        if lv is True or (callable(lv) and lv(t)):
            self.queue_draw()

    def _setp(self, v):
        self.p = v
        self.queue_draw()

    def hover_to(self, on):
        if on == self._ht:
            return
        self._ht = on
        s, e = self.hv, (1.0 if on else 0.0)
        M.tween(0.22, lambda k: self._seth(lerp(s, e, k)), key=(id(self), "h"), owner=self)

    def _seth(self, v):
        self.hv = v
        self.queue_draw()

    def kick(self):
        self.pulse = M.now()
        M.tween(0.75, lambda k: self.queue_draw(), ease=e_lin, key=(id(self), "k"), owner=self)

    def kick_age(self):
        return M.now() - self.pulse

    def _on_draw(self, wd, cr):
        W, H = wd.get_allocated_width(), wd.get_allocated_height()
        try:
            p = self.p
            if p < 0.999 and self.kind:
                if p <= 0.001:
                    return False
                cr.push_group()
                if self.kind == "rise":
                    cr.translate(0, (1 - p) * 18)
                else:
                    s = 0.55 + 0.45 * e_back(p)
                    cr.translate(W / 2.0, H / 2.0); cr.scale(s, s); cr.translate(-W / 2.0, -H / 2.0)
                try:
                    self.painter(cr, W, H, self)
                finally:
                    cr.pop_group_to_source()
                cr.paint_with_alpha(clamp(p * 1.6) if self.kind == "pop" else p)
            else:
                self.painter(cr, W, H, self)
        except Exception as e:
            print("draw error:", e, file=sys.stderr)
        return False


def hover_bind(btn, *cvs):
    def f(b, _prev):
        on = bool(b.get_state_flags() & Gtk.StateFlags.PRELIGHT)
        for cv in cvs:
            cv.hover_to(on)
    btn.connect("state-flags-changed", f)


def _hook(w):
    if not getattr(w, "_hooked", False):
        w._hooked = True
        w._dead = False

        def gone(*_):
            w._dead = True
            M.kill(w)
        w.connect("destroy", gone)


def appear(w, delay=0.0, dx=0, dur=0.42):
    """Fade (+ optional slide-from-left) a regular widget in."""
    if not M.enabled:
        return w
    _hook(w)
    m0 = getattr(w, "_m0", None)
    if m0 is None:
        m0 = w._m0 = w.get_margin_start()

    def f(k):
        w.set_opacity(k)
        if dx:
            w.set_margin_start(int(round(m0 + dx * (1 - k))))
    M.tween(dur, f, delay=delay, key=(id(w), "ap"), owner=w)
    return w


def shake(w):
    if not M.enabled:
        return
    _hook(w)
    ctx = w.get_style_context()
    ctx.add_class("err")
    GLib.timeout_add(900, lambda: (ctx.remove_class("err") if not getattr(w, "_dead", False) else None, False)[1])

    def f(k):
        off = 9 * math.sin(k * PI * 6) * (1 - k)
        w.set_margin_start(int(max(0, off)))
        w.set_margin_end(int(max(0, -off)))
    M.tween(0.45, f, ease=e_lin, key=(id(w), "sh"), owner=w)


def esc(s):
    return GLib.markup_escape_text(str(s))


def add_cls(w, cls):
    if cls:
        ctx = w.get_style_context()
        for c in cls.split():
            ctx.add_class(c)
    return w


def set_rarity_cls(w, r):
    ctx = w.get_style_context()
    for i in range(6):
        ctx.remove_class(f"r{i}")
    ctx.add_class(f"r{r}")


def lbl(text_="", cls=None, xalign=0.0, markup=False, ell=False, maxw=None, wrap=False):
    l = Gtk.Label()
    l.set_xalign(xalign)
    if markup:
        l.set_markup(text_)
    else:
        l.set_text(text_)
    add_cls(l, cls)
    if ell:
        l.set_ellipsize(Pango.EllipsizeMode.END)
    if maxw:
        l.set_max_width_chars(maxw)
    if wrap:
        l.set_line_wrap(True)
        l.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        if xalign == 0.5:
            l.set_justify(Gtk.Justification.CENTER)
    return l


def box(orient="h", spacing=0, cls=None, homog=False):
    b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL if orient == "h" else Gtk.Orientation.VERTICAL, spacing=spacing)
    b.set_homogeneous(homog)
    return add_cls(b, cls)


def margins(w, t=0, r=0, b=0, l=0):
    w.set_margin_top(t); w.set_margin_end(r); w.set_margin_bottom(b); w.set_margin_start(l)
    return w


def Icon(name, size=16, color=None, alpha=1.0):
    cv = Canvas(lambda cr, w, h, c: draw_icon(cr, name, w / 2.0, h / 2.0, size / 2.0, color, alpha), size, size)
    cv.set_valign(CENTER)
    return cv


def Stars(n, sz=13, delay=0.0):
    """n: int or callable -> int.  Stars pop in one-by-one, then twinkle."""
    getn = n if callable(n) else (lambda: n)
    w = int(5 * (sz + 1.5)) + 4 if callable(n) else int(max(1, n * (sz + 1.5))) + 4

    def paint(cr, W, H, c):
        t = T()
        k_all = getn()
        el = t - c.born
        for i in range(k_all):
            k = clamp((el - i * 0.09) / 0.34) if M.enabled else 1.0
            if k <= 0:
                continue
            draw_icon(cr, "star", 2 + sz / 2.0 + i * (sz + 1.5), H / 2.0, sz / 2.0 * e_back(k))
        ph = t % 3.2
        if k_all and ph < 0.6 and el > 1.0:
            j = int(t / 3.2) % k_all
            a = math.sin(ph / 0.6 * PI)
            draw_icon(cr, "sparkle", 2 + sz * 0.8 + j * (sz + 1.5), H / 2.0 - sz * 0.3, sz * 0.42 * a, "#FFFFFF", a)
    cv = Canvas(paint, w, sz + 4,
                live=lambda t: (t - cv.born) < 0.4 + 5 * 0.09 + 0.1 or (t % 3.2) < 0.7)
    cv.born = M.now() + delay
    cv.set_halign(Gtk.Align.START)
    return cv


def Divider():
    return margins(Canvas(lambda cr, w, h, c: draw_divider(cr, w, h, T()), -1, 16,
                          live=True), 0, 18, 0, 18)


def title_canvas(s, size, period=5.0):
    tw, th = measure(s, size, SERIF, True)
    return Canvas(lambda cr, w, h, c: text_gold(cr, s, 0, 0, size, SERIF, T(), period), tw + 4, th + 3,
                  live=lambda t: (t % period) < 1.3)


def icon_btn(name, size, cb, tip=None, color=CREAM, spin=None, rot=0.0):
    b = add_cls(Gtk.Button(), "flat-x")
    b.set_relief(Gtk.ReliefStyle.NONE)

    def paint(cr, w, h, c):
        hv = c.hv
        t = T()
        if hv > 0.01:
            glow(cr, w / 2.0, h / 2.0, w / 2.0, "#FFF4D6", 0.45 * hv)
        ka = c.kick_age()
        if 0 <= ka < 0.6:
            k = ka / 0.6
            cr.new_path(); cr.arc(w / 2.0, h / 2.0, w * 0.3 + k * w * 0.2, 0, TAU)
            cr.set_line_width(1.6 * (1 - k)); src(cr, GOLD_HI, 0.9 * (1 - k)); cr.stroke()
        r = rot * e_out(hv)
        if spin is not None and spin():
            r = t * 5.0
        draw_icon(cr, name, w / 2.0, h / 2.0, size * 0.40 * (1 + 0.08 * hv), color, 0.82 + 0.18 * hv, rot=r)
    cv = Canvas(paint, size, size, live=(lambda t: bool(spin())) if spin is not None else None)
    b.add(cv)
    hover_bind(b, cv)
    b.set_valign(CENTER)
    b.connect("clicked", lambda *_: (cv.kick(), cb()))
    if tip:
        b.set_tooltip_text(tip)
    return b


def gbtn(label, glyph="confirm", kind="cream", cb=None, tip=None, small=False):
    b = add_cls(Gtk.Button(), ("g-btn" if kind == "cream" else "g-btn-dark") + (" sm" if small else ""))
    h = box("h", 8)
    d = 20 if small else 26
    cv = Canvas(lambda cr, w, hh, c: draw_badge(cr, glyph, w / 2.0, hh / 2.0, d / 2.0 - 2.5 + c.hv * 0.8,
                                                "ink" if kind == "cream" else "glass", c.hv), d + 4, d + 2)
    cv.set_valign(CENTER)
    h.pack_start(cv, False, False, 0)
    b_lbl = lbl(label, xalign=0.5, ell=True, maxw=18)
    b.lbl = b_lbl
    h.pack_start(b_lbl, True, True, 0)
    b.add(h)
    hover_bind(b, cv)
    if cb:
        b.connect("clicked", lambda *_: cb())
    if tip:
        b.set_tooltip_text(tip)
    return b


def section(title, right=None):
    h = box("h", 8)
    h.pack_start(Canvas(lambda cr, w, hh, c: draw_icon(cr, "diamond", w / 2, hh / 2, 4.5 * (1 + 0.15 * math.sin(T() * 2.4)), GOLD),
                        11, 11, live=True), False, False, 0)
    h.pack_start(lbl(title, "eyebrow"), False, False, 0)
    h.pack_start(Canvas(lambda cr, w, hh, c: draw_fade_line(cr, w, hh), -1, 10), True, True, 0)
    if right is not None:
        right.set_valign(CENTER)
        h.pack_end(right, False, False, 0)
    return h


def placeholder(icon, title, hint, radar=False):
    v = box("v", 6)
    margins(v, 16 if radar else 24, 0, 18, 0)
    if radar:
        i = Canvas(lambda cr, w, h, c: draw_radar(cr, w, h, T()), 110, 84, live=True)
    else:
        i = Canvas(lambda cr, w, h, c: (glow(cr, w / 2, h / 2, w / 2, "#FFF0C8", 0.14 + 0.08 * math.sin(T() * 2)),
                                        draw_icon(cr, icon, w / 2, h / 2 + math.sin(T() * 1.8) * 1.5, 17, GOLD, 0.85)),
                   52, 52, live=True, intro="pop")
    i.set_halign(CENTER)
    v.pack_start(i, False, False, 0)
    v.pack_start(lbl(title, "ph-title", 0.5), False, False, 0)
    v.pack_start(lbl(hint, "tiny", 0.5, wrap=True), False, False, 0)
    return v


def scrolled(child, h=-1):
    sc = Gtk.ScrolledWindow()
    sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sc.set_shadow_type(Gtk.ShadowType.NONE)
    if h > 0:
        sc.set_size_request(-1, h)
    sc.add(child)
    return sc


def entry(placeholder_text, secret=False, on_cream=False, on_activate=None, small=False):
    e = add_cls(Gtk.Entry(), "g-entry" + (" on-cream" if on_cream else "") + (" small" if small else ""))
    e.set_placeholder_text(placeholder_text)
    if secret:
        e.set_visibility(False)
        e.set_input_purpose(Gtk.InputPurpose.PASSWORD)
    if on_activate:
        e.connect("activate", lambda *_: on_activate())
    return e


def seg(options, active, cb, dark=False):
    h = box("h", 6)
    btns = []
    lock = [False]

    def toggled(b, val):
        if lock[0]:
            return
        lock[0] = True
        if not b.get_active():
            b.set_active(True)
        else:
            for x in btns:
                if x is not b:
                    x.set_active(False)
            cb(val)
        lock[0] = False
    for label, val in options:
        b = add_cls(Gtk.ToggleButton(label=label), "seg" + (" dark" if dark else ""))
        b.set_active(val == active)
        b.connect("toggled", toggled, val)
        h.pack_start(b, False, False, 0)
        btns.append(b)
    return h


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AMBIENT MOTES — floating light motes, redrawn only in tiny regions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Motes:
    def __init__(self, win, n=14, seed=11):
        self.win = win
        rnd = random.Random(seed)
        self.m = [(rnd.random(), rnd.random(), 0.010 + rnd.random() * 0.028, rnd.random() * TAU,
                   1.1 + rnd.random() * 2.0, rnd.random() < 0.35) for _ in range(n)]
        self.prev = []

    def positions(self, t, W, H):
        m = SHADOW + 10
        ww, hh = W - 2 * m, H - 2 * m
        out = []
        for fx, fy, sp, ph, sz, star in self.m:
            life = (fy + t * sp) % 1.0
            y = m + hh - life * hh
            x = m + fx * ww + math.sin(t * 0.55 + ph) * 12
            a = math.sin(life * PI) * (0.55 + 0.45 * math.sin(t * 2.1 + ph * 3))
            out.append((x, y, sz, max(0.0, a), star))
        return out

    def _amb(self, t):
        w = self.win
        W, H = w.get_allocated_width(), w.get_allocated_height()
        if W < 50 or H < 50:
            return
        pts = self.positions(t, W, H)
        for (x, y, sz, _a, _s) in self.prev + pts:
            r = int(sz * 3.2 + 3)
            w.queue_draw_area(int(x) - r, int(y) - r, 2 * r, 2 * r)
        self.prev = pts

    def draw(self, cr, t, W, H, alpha=1.0):
        for x, y, sz, a, star in self.positions(t, W, H):
            a *= alpha
            if a < 0.02:
                continue
            glow(cr, x, y, sz * 3.0, "#FFE9B8", 0.32 * a)
            if star:
                draw_icon(cr, "sparkle", x, y, sz * 1.5, "#FFF6DD", a, rot=t * 0.4)
            else:
                cr.new_path(); cr.arc(x, y, sz * 0.55, 0, TAU); cr.set_source_rgba(1, 0.98, 0.92, a); cr.fill()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN WINDOW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABS = [
    ("overview", "compass", "Overview",      "Ley-line telemetry & constellation"),
    ("networks", "wifi",    "Ley Lines",     "Inventory of nearby networks"),
    ("dns",      "anemo",   "Elemental DNS", "Resonate your resolver"),
    ("archive",  "book",    "Archive",       "Saved ley lines & teleport waypoint"),
    ("ports",    "shield",  "Ley Guard",     "Listening sockets on this vessel"),
    ("settings", "gear",    "Pact Settings", "Hidden ley lines, motion & system"),
]
TAB_IDX = {t[0]: i for i, t in enumerate(TABS)}


class Celestia(Gtk.Window):
    def __init__(self, mode="mini", tab=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        M.attach(self)
        self.mode = mode
        self.tab = tab if tab in TAB_IDX else "overview"
        self.alive = True
        self.closing = False
        self.quit_pending = False
        self.busy = 0
        self.alpha = 0.0
        self.dev = get_wifi_dev()
        self.info, self.radio, self.profiles, (nets0, self.hidden_n) = gather(
            (get_active_info, self.dev), (get_radio_enabled,), (get_wifi_profiles, True), (scan_networks, self.dev, False))
        self.sig_anim = float(self.info["signal"])
        self.cache = {}
        self.nets, self.net_by = [], {}
        self.nets = self.merge(nets0)
        self.scanning = False
        self.connecting = None
        self.sel_ssid = None
        self.pending = None
        self._reloading = False
        self._info_busy = False
        self.rx_hist = [0.0] * 62
        self.tx_hist = [0.0] * 62
        self.sample_t = M.now()
        self.last_rx = self.last_tx = 0
        self.last_ts = time.time()
        self.tick_n = 0
        self.motes = None
        self._bg = None
        self._bgk = None
        self.toast_gen = 0
        self.toast_kind = "info"
        self.pages, self.page_names, self.page_sigs = {}, {}, {}
        self.page_gen = 0
        self._init_counters()

        self.set_title("Celestia Network")
        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_resizable(False)
        vis = self.get_screen().get_rgba_visual()
        if vis:
            self.set_visual(vis)
        if HAS_LAYER:
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_namespace(self, "genshin-wifi-panel")
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            if hasattr(GtkLayerShell, "set_keyboard_mode"):
                GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
            else:
                GtkLayerShell.set_keyboard_interactivity(self, True)
        else:
            self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
            self.set_keep_above(True)
        self.connect("draw", self.paint_shell)
        self.connect("key-press-event", self.on_key)
        self.connect("focus-out-event", self.on_focus_out)
        self.connect("destroy", lambda *_: Gtk.main_quit())
        self.connect("map", lambda *_: self.motes and M.watch(self.motes))
        self.connect("unmap", lambda *_: self.motes and M.unwatch(self.motes))

        self.ov = Gtk.Overlay()
        self.add(self.ov)
        self.root = margins(box("v", 0), SHADOW, SHADOW, SHADOW, SHADOW)
        self.ov.add(self.root)
        self.build_toast()
        self.ov.set_opacity(0.0)
        self.build()
        self.show_all()
        self.fade(1.0, 0.38)
        GLib.timeout_add(1000, self.tick)
        GLib.timeout_add(60, self._first_scan)

    def _first_scan(self):
        if self.alive:
            self.reload(rescan=bool(PREFS["autoscan"] and self.radio), quiet=bool(self.nets))
        return False

    # ── infrastructure ──────────────────────────────────────────────
    def _bg_surface(self, W, H):
        s = max(1, self.get_scale_factor())
        key = (W, H, self.mode, s)
        if self._bgk != key:
            self._bg = None
            try:
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W * s, H * s)
                surf.set_device_scale(s, s)
            except Exception:
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
            c = cairo.Context(surf)
            draw_bg(c, W, H, SHADOW, seed=3 if self.mode == "mini" else 9)
            surf.flush()
            self._bg, self._bgk = surf, key
        return self._bg

    def paint_shell(self, w, cr):
        W, H = w.get_allocated_width(), w.get_allocated_height()
        cr.save()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.restore()
        if self.alpha <= 0.002:
            return False
        cr.set_source_surface(self._bg_surface(W, H), 0, 0)
        cr.paint_with_alpha(self.alpha)
        if self.motes is not None and M.enabled:
            self.motes.draw(cr, T(), W, H, self.alpha)
        return False

    def setup_motes(self):
        if self.motes is not None:
            M.unwatch(self.motes)
        self.motes = None
        if PREFS["motes"] and PREFS["anim"]:
            self.motes = Motes(self, 12 if self.mode == "mini" else 22, 11 if self.mode == "mini" else 29)
            if self.get_mapped():
                M.watch(self.motes)
        self.queue_draw()

    def fade(self, target, dur, done=None):
        s = self.alpha
        top = int(PREFS["top"])

        def f(k):
            self.alpha = lerp(s, target, k)
            self.ov.set_opacity(self.alpha)
            if HAS_LAYER and self.mode == "mini":
                mv = int(top - 16 * (1 - self.alpha))
                if mv != getattr(self, "_lm", None):
                    self._lm = mv
                    try:
                        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, mv)
                    except Exception:
                        pass
            self.queue_draw()
        M.tween(dur, f, ease=e_out, done=done, key="win-fade")

    def bg(self, fn, done=None):
        def run():
            try:
                r = fn()
            except Exception as e:
                print("worker:", e, file=sys.stderr)
                r = None
            if done:
                GLib.idle_add(self._idle_call, done, r)
        threading.Thread(target=run, daemon=True).start()

    def _idle_call(self, done, r):
        try:
            done(r)
        except Exception as e:
            print("ui:", e, file=sys.stderr)
        return False

    def merge(self, nets):
        """Union the fresh scan with recently-seen ley lines so a flaky scan never hides them."""
        now = time.monotonic()
        cur = set()
        for n in nets:
            n["faint"] = False
            self.cache[n["ssid"]] = (dict(n), now)
            cur.add(n["ssid"])
        out = list(nets)
        if self.radio:
            for ssid, (n, ts) in list(self.cache.items()):
                if ssid in cur:
                    continue
                if now - ts > 150:
                    del self.cache[ssid]
                    continue
                c = dict(n)
                c["faint"], c["active"] = True, False
                out.append(c)
        prof = {}
        for p in self.profiles:
            if p.get("mode") != "ap":
                prof.setdefault(p["ssid"], p["name"])
        for n in out:
            n["profile"] = prof.get(n["ssid"])
            n["saved"] = bool(n["profile"])
            n.setdefault("nodes", 1)
            n.setdefault("bands", n.get("band", "—"))
        out.sort(key=lambda x: (not x["active"], x["faint"], not x["saved"], -x["signal"], x["ssid"].lower()))
        self.net_by = {n["ssid"]: n for n in out}
        return out

    def reload(self, rescan=False, delay=0.0, quiet=False):
        if self._reloading:
            return
        self._reloading = True
        if rescan:
            self.scanning = True
            self.on_scan_state(quiet)

        def part(res):
            GLib.idle_add(self._partial, res[0], res[1])

        def work():
            if delay:
                time.sleep(delay)
            nets, hidden = scan_networks(self.dev, deep=rescan, progress=part if rescan else None)
            info, radio, profiles = gather((get_active_info, self.dev), (get_radio_enabled,), (get_wifi_profiles,))
            return (info, nets, hidden, radio, profiles)

        def done(r):
            self._reloading = False
            self.scanning = False
            if r:
                info, nets, hidden, radio, profiles = r
                self.info, self.radio, self.profiles, self.hidden_n = info, radio, profiles, hidden
                self.nets = self.merge(nets)
                self.tween_signal()
            if self.alive and not self.quit_pending:
                self.refresh()
            later_trim()
        self.bg(work, done)

    def _partial(self, nets, hidden):
        """Networks found while a deep scan is still running show up immediately."""
        if not self.alive or self.quit_pending or not self._reloading:
            return False
        self.hidden_n = hidden
        self.nets = self.merge(nets)
        self.refresh()
        return False

    def rescan(self):
        if not self.radio:
            self.toast("Wi-Fi radio is sealed", "err")
            return
        self.toast("Listening to the winds of Teyvat…", "busy", sticky=True)
        self.reload(rescan=True)

    def on_scan_state(self, quiet):
        if self.mode == "mini" and hasattr(self, "list_box") and not self.nets and not quiet:
            self.fill_list(force=True)

    def tween_signal(self):
        s, e = self.sig_anim, float(self.info["signal"] if self.info["connected"] else 0)
        if abs(s - e) < 0.5:
            self.sig_anim = e
            return

        def f(k):
            self.sig_anim = lerp(s, e, k)
            d = getattr(self, "dial", None)
            if d is not None and not getattr(d, "_dead", False):
                d.queue_draw()
        M.tween(0.9, f, ease=e_inout, key="sig")

    def quit(self, *_):
        if self.closing:
            return
        self.closing = True

        def fin():
            if self.busy > 0:
                self.quit_pending = True
                self.hide()
                try:
                    with open(PID_FILE) as f:
                        if f.read().split()[0] == str(os.getpid()):
                            os.remove(PID_FILE)
                except Exception:
                    pass
            else:
                self.alive = False
                Gtk.main_quit()
        self.fade(0.0, 0.18, fin)

    def spawn(self, args):
        try:
            subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.toast(f"Cannot launch: {e}", "err")

    def copy(self, key, val):
        if not val or val == "—":
            return
        try:
            if shutil.which("wl-copy"):
                subprocess.Popen(["wl-copy", val])
            elif shutil.which("xclip"):
                p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                p.communicate(val.encode())
        except Exception:
            pass
        self.toast(f"Copied {key}  ·  {val}", "ok")

    def _init_counters(self):
        self.last_rx, self.last_tx = self._read_counters()
        self.last_ts = time.time()

    def _read_counters(self):
        try:
            with open(f"/sys/class/net/{self.dev}/statistics/rx_bytes") as f:
                rx = int(f.read().strip())
            with open(f"/sys/class/net/{self.dev}/statistics/tx_bytes") as f:
                tx = int(f.read().strip())
            return rx, tx
        except Exception:
            return 0, 0

    def _speed(self):
        now = time.time()
        dt = max(0.25, now - self.last_ts)
        rx, tx = self._read_counters()
        rk = max(0.0, (rx - self.last_rx) / 1024.0 / dt) if self.last_rx else 0.0
        tk = max(0.0, (tx - self.last_tx) / 1024.0 / dt) if self.last_tx else 0.0
        self.last_rx, self.last_tx, self.last_ts = rx, tx, now
        return rk, tk

    def geometry(self):
        if self.mode == "mini":
            self.set_size_request(MINI_W + 2 * SHADOW, -1)
        else:
            self.set_size_request(AKASHA_W + 2 * SHADOW, AKASHA_H + 2 * SHADOW)
        if not HAS_LAYER:
            self.set_position(Gtk.WindowPosition.CENTER)
            return
        E = GtkLayerShell.Edge
        mini = self.mode == "mini"
        GtkLayerShell.set_anchor(self, E.TOP, mini)
        GtkLayerShell.set_anchor(self, E.RIGHT, mini)
        GtkLayerShell.set_anchor(self, E.BOTTOM, False)
        GtkLayerShell.set_anchor(self, E.LEFT, False)
        if mini:
            GtkLayerShell.set_margin(self, E.TOP, int(PREFS["top"]) - int(16 * (1 - self.alpha)))
            GtkLayerShell.set_margin(self, E.RIGHT, int(PREFS["right"]))

    def build(self):
        for c in self.root.get_children():
            c.destroy()
        self.h_rx = self.h_tx = None
        self.traffic = self.dial = None
        self.pages, self.page_names, self.page_sigs = {}, {}, {}
        self.ov_vals = {}
        self.geometry()
        if self.mode == "mini":
            self.build_mini()
        else:
            self.build_akasha()
        self.root.show_all()
        self._bgk = None
        self.setup_motes()
        self.queue_draw()
        later_trim(1200)

    def refresh(self):
        if self.mode == "mini":
            self.refresh_mini()
        else:
            self.refresh_akasha()
        if self.toast_kind == "busy" and not self.connecting and not self.scanning:
            n = len([x for x in self.nets if not x["faint"]])
            self.toast(f"{n} ley line{'s' if n != 1 else ''} discovered" + (f"  ·  {self.hidden_n} hidden" if self.hidden_n else ""), "ok")

    def switch(self, mode, tab=None):
        if tab:
            self.tab = tab
        if mode == self.mode:
            if mode == "akasha" and tab:
                self.set_tab(tab)
            return
        if self.closing:
            return

        def swap():
            self.mode = mode
            try:
                with open(PID_FILE, "w") as f:
                    f.write(f"{os.getpid()} {mode}")
            except Exception:
                pass
            self.hide()
            self.build()
            self.resize(1, 1)
            self.show_all()
            self.present()
            self.fade(1.0, 0.36)
        self.fade(0.0, 0.15, swap)

    def on_key(self, w, e):
        if e.keyval == Gdk.KEY_Escape:
            rv = getattr(self, "pw_rev", None)
            if self.mode == "mini" and rv is not None and rv.get_reveal_child():
                self.set_pw_open(False)
                return True
            self.quit()
            return True
        if self.mode == "akasha" and (e.state & Gdk.ModifierType.CONTROL_MASK):
            if e.keyval in (Gdk.KEY_Tab, Gdk.KEY_Page_Down):
                self.set_tab(TABS[(TAB_IDX[self.tab] + 1) % len(TABS)][0])
                return True
            if e.keyval in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Page_Up):
                self.set_tab(TABS[(TAB_IDX[self.tab] - 1) % len(TABS)][0])
                return True
        if e.keyval == Gdk.KEY_F5:
            self.rescan()
            return True
        return False

    def on_focus_out(self, *_):
        if self.mode == "mini" and HAS_LAYER:
            GLib.timeout_add(260, self._maybe_close)
        return False

    def _maybe_close(self):
        if self.alive and self.mode == "mini" and not self.is_active() and not self.closing:
            self.quit()
        return False

    def user_busy(self):
        f = self.get_focus()
        if isinstance(f, Gtk.Entry) and f.get_text():
            return True
        rv = getattr(self, "pw_rev", None)
        return bool(self.mode == "mini" and rv is not None and rv.get_reveal_child())

    # ── toast ───────────────────────────────────────────────────────
    def build_toast(self):
        self.toast_box = box("h", 8, "toast")
        self.toast_box.set_halign(CENTER)
        self.toast_box.set_valign(Gtk.Align.END)
        self.toast_box.set_margin_bottom(SHADOW + 6)
        self.toast_box.set_margin_start(SHADOW + 20)
        self.toast_box.set_margin_end(SHADOW + 20)

        def paint(cr, w, h, c):
            t = T()
            k = self.toast_kind
            cx, cy = w / 2.0, h / 2.0
            if k == "busy":
                draw_spinner(cr, cx, cy, 6.5, t, "#E6C9FF")
            elif k == "ok":
                glow(cr, cx, cy, 11, "#B8F7E0", 0.5)
                draw_icon(cr, "sparkle", cx, cy, 7, "#B8F7E0", rot=t * 0.8)
            elif k == "err":
                glow(cr, cx, cy, 11, "#FFC9A0", 0.5)
                draw_icon(cr, "cancel", cx, cy, 8.5)
            else:
                draw_icon(cr, "primogem", cx, cy, 8)
        self.toast_icon = Canvas(paint, 22, 22, live=True)
        self.toast_icon.set_valign(CENTER)
        self.toast_lbl = lbl("", None, ell=True, maxw=52)
        self.toast_box.pack_start(self.toast_icon, False, False, 0)
        self.toast_box.pack_start(self.toast_lbl, False, False, 0)
        self.toast_icon.show()
        self.toast_lbl.show()
        self.toast_box.set_opacity(0.0)
        self.toast_box.set_no_show_all(True)
        self.ov.add_overlay(self.toast_box)
        try:
            self.ov.set_overlay_pass_through(self.toast_box, True)
        except Exception:
            pass

    def toast(self, msg, kind="info", sticky=False, ms=2600):
        self.toast_gen += 1
        g = self.toast_gen
        self.toast_kind = kind
        self.toast_lbl.set_text(msg)
        self.toast_box.show()
        self.toast_icon.queue_draw()
        s = self.toast_box.get_opacity()

        def f(k):
            self.toast_box.set_opacity(lerp(s, 1.0, k))
            self.toast_box.set_margin_bottom(int(SHADOW + 6 + 16 * e_out(k)))
        M.tween(0.32, f, ease=e_back if s < 0.1 else e_out, key="toast")
        if not sticky:
            GLib.timeout_add(ms, self._toast_hide, g)

    def _toast_hide(self, g):
        if g != self.toast_gen:
            return False

        def f(k):
            self.toast_box.set_opacity(1.0 - k)
            self.toast_box.set_margin_bottom(int(SHADOW + 22 - 10 * k))

        def fin():
            if g == self.toast_gen:
                self.toast_box.hide()
                self.toast_kind = "info"
        M.tween(0.3, f, key="toast", done=fin)
        return False

    # ── shared bits ─────────────────────────────────────────────────
    def dns_active(self, ips):
        if not self.info["connected"]:
            return False
        cfg = self.info.get("dns_cfg", "")
        if not ips:
            return cfg.strip() == ""
        return ips.split()[0] in cfg

    def dns_active_preset(self):
        for p in DNS_PRESETS:
            if self.dns_active(p[1]):
                return p
        return None

    def attr_row(self, key, val, icon, cream=True, alt=False, ref=None):
        b = add_cls(Gtk.Button(), "attr" if cream else ("attr-dark" + (" alt" if alt else "")))
        h = box("h", 8)
        ic = Canvas(lambda cr, w, hh, c: draw_icon(cr, icon, w / 2, hh / 2, (11 if cream else 13) / 2.0 * (1 + 0.18 * c.hv),
                                                   INK2 if cream else GOLD, 0.85 + 0.15 * c.hv, rot=c.hv * 0.3),
                    11 if cream else 13, 11 if cream else 13)
        ic.set_valign(CENTER)
        h.pack_start(ic, False, False, 0)
        h.pack_start(lbl(key, "ink" if cream else "akey"), False, False, 0)
        v = lbl(str(val), "ink-b" if cream else "aval", 1.0, ell=True)
        h.pack_start(v, True, True, 0)
        b.add(h)
        hover_bind(b, ic)
        b.set_tooltip_text(f"Click to copy {key}")
        b.connect("clicked", lambda *_: self.copy(key, v.get_text()))
        if ref is not None:
            self.ov_vals[ref] = v
        return b

    def _hero_el(self):
        return band_of(self.info["freq"])[1]

    def hero_sub_text(self):
        i = self.info
        if not i["connected"]:
            return "No ley line connected"
        band, el = band_of(i["freq"])
        return f'{ELEM[el][2]}  ·  {band}  ·  {i["signal"]}%  ·  {i["rate"]}'

    def hero_card(self):
        info = self.info
        con = info["connected"]
        r = rarity_of(info["signal"]) if con else 0
        card = box("v", 0)
        ov = Gtk.Overlay()
        top = box("h", 10, f"hero-top r{r}")
        self.hero_top = top
        lv = box("v", 3)
        lv.set_valign(CENTER)
        lv.pack_start(lbl(info["ssid"] if con else "Not Attuned", "hero-name", ell=True, maxw=20), False, False, 0)
        self.hero_sub = lbl(self.hero_sub_text(), "hero-type", ell=True)
        lv.pack_start(self.hero_sub, False, False, 0)
        if con:
            lv.pack_start(Stars(lambda: rarity_of(self.info["signal"]) if self.info["connected"] else 0, 13, 0.2), False, False, 2)
        top.pack_start(lv, True, True, 0)
        art = Canvas(lambda cr, w, h, c: draw_art(cr, w, h, self._hero_el() if self.info["connected"] else None, None, T()),
                     66, 66, live=True, intro="pop", delay=0.1, dur=0.6)
        top.pack_end(art, False, False, 0)
        ov.add(top)
        sh = Canvas(lambda cr, w, h, c: draw_shimmer(cr, w, h, T(), 12), live=lambda t: (t % 4.6) < 1.25)
        ov.add_overlay(sh)
        try:
            ov.set_overlay_pass_through(sh, True)
        except Exception:
            pass
        card.pack_start(ov, False, False, 0)
        bot = box("v", 1, "hero-bottom")
        if con:
            bot.pack_start(self.attr_row("IPv4", info["ip"], "diamond"), False, False, 0)
            bot.pack_start(self.attr_row("Gateway", info["gw"], "compass"), False, False, 0)
            sp = margins(box("h", 6), 3, 4, 0, 9)
            sp.pack_start(Icon("arrow_down", 11, "#3E9C7F"), False, False, 0)
            self.h_rx = lbl("0 KB/s", "ink-b")
            sp.pack_start(self.h_rx, False, False, 0)
            sp.pack_start(Icon("arrow_up", 11, "#B07E2E"), False, False, 6)
            self.h_tx = lbl("0 KB/s", "ink-b")
            sp.pack_start(self.h_tx, False, False, 0)
            dis = add_cls(Gtk.Button(), "attr")
            dh = box("h", 5)
            pic = Canvas(lambda cr, w, h, c: draw_icon(cr, "power", w / 2, h / 2, 5.5 * (1 + 0.2 * c.hv), "#B5523A"), 12, 12)
            pic.set_valign(CENTER)
            dh.pack_start(pic, False, False, 0)
            dh.pack_start(lbl("Disconnect", "ink-b"), False, False, 0)
            dis.add(dh)
            hover_bind(dis, pic)
            dis.connect("clicked", lambda *_: self.sever())
            sp.pack_end(dis, False, False, 0)
            bot.pack_start(sp, False, False, 0)
        else:
            bot.pack_start(margins(lbl("Choose a ley line below to attune your connection, Traveler.",
                                       "flavor", wrap=True), 4, 6, 4, 6), False, False, 0)
        card.pack_start(bot, False, False, 0)
        return card

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  MINI POPUP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def build_mini(self):
        R = self.root
        self._hero_key = None
        self._list_sig = None
        self._seen_rows = set()
        self.row_meta = {}
        hdr = margins(box("h", 10), 14, 14, 4, 14)
        hdr.pack_start(Canvas(lambda cr, w, h, c: paint_gem(cr, w, h, T()), 44, 44, live=True, intro="pop", dur=0.7),
                       False, False, 0)
        tb = box("v", 0)
        tb.set_valign(CENTER)
        tb.pack_start(lbl("TEYVAT  ·  LEY LINE NETWORK", "eyebrow"), False, False, 0)
        tb.pack_start(title_canvas("Wi-Fi", 22), False, False, 0)
        hdr.pack_start(tb, True, True, 0)
        sw = Gtk.Switch()
        sw.set_active(self.radio)
        sw.set_valign(CENTER)
        sw.set_tooltip_text("Wi-Fi radio")
        sw.connect("notify::active", self.on_radio)
        self.radio_sw = sw
        hdr.pack_start(sw, False, False, 0)
        hdr.pack_start(icon_btn("close", 30, self.quit, "Close  (Esc)", rot=PI / 2), False, False, 0)
        R.pack_start(hdr, False, False, 0)
        R.pack_start(Divider(), False, False, 0)

        body = margins(box("v", 10), 6, 16, 16, 16)
        self.slot_hero = box("v", 0)
        body.pack_start(self.slot_hero, False, False, 0)

        self.dns_lbl = lbl("", "tiny")
        body.pack_start(section("ELEMENTAL DNS", self.dns_lbl), False, False, 0)
        orbs = box("h", 0, homog=True)
        self.orb_names = []
        for i, (name, ips, el, fa, en) in enumerate(DNS_PRESETS):
            col = box("v", 2)
            b = add_cls(Gtk.Button(), "flat-x")
            cv = Canvas(lambda cr, w, h, c, el=el, ips=ips: draw_orb(cr, w, h, el, self.dns_active(ips), c.hv, T(), c.kick_age()),
                        48, 48, live=lambda t, ips=ips: self.dns_active(ips), intro="pop", delay=0.15 + i * 0.05, dur=0.55)
            b.add(cv)
            hover_bind(b, cv)
            b.set_halign(CENTER)
            b.set_tooltip_markup(f"<b>{esc(name)}</b>  ·  {ELEM[el][2]}\n{esc(en)}\n"
                                 f"<tt>{esc(ips or 'Router / DHCP')}</tt>")
            b.connect("clicked", lambda _b, n=name, i_=ips, c=cv: (c.kick(), self.on_dns(n, i_)))
            col.pack_start(b, False, False, 0)
            nl = lbl(name, "orb-name", 0.5, ell=True)
            self.orb_names.append((nl, ips))
            col.pack_start(nl, False, False, 0)
            orbs.pack_start(col, True, True, 0)
        body.pack_start(orbs, False, False, 0)

        right = box("h", 2)
        self.count_lbl = lbl("", "tiny")
        right.pack_start(self.count_lbl, False, False, 4)
        right.pack_start(icon_btn("plus", 24, lambda: self.open_pw(None, manual=True), "Add a hidden / manual ley line", GOLD, rot=PI / 4),
                         False, False, 0)
        right.pack_start(icon_btn("refresh", 24, self.rescan, "Rescan the ley lines  (F5)", GOLD,
                                  spin=lambda: self.scanning, rot=PI), False, False, 0)
        body.pack_start(section("NEARBY LEY LINES", right), False, False, 0)

        self.list_box = box("v", 6)
        self.list_sc = scrolled(self.list_box, 204)
        self.list_h = 204
        body.pack_start(self.list_sc, True, True, 0)
        body.pack_start(self.password_revealer(), False, False, 0)

        ft = box("h", 10, homog=True)
        ft.pack_start(gbtn("Settings", "gear", "dark", lambda: self.switch("akasha", "settings"),
                           "Pact Settings — hidden networks, motion, system"), True, True, 0)
        ft.pack_start(gbtn("Akasha", "compass", "cream", lambda: self.switch("akasha", "overview"),
                           "Open the Akasha Terminal"), True, True, 0)
        body.pack_start(ft, False, False, 0)
        R.pack_start(body, True, True, 0)
        self.refresh_mini(first=True)
        for i, w in enumerate([hdr] + body.get_children()):
            appear(w, 0.03 + i * 0.045, dx=0, dur=0.45)

    def refresh_mini(self, first=False):
        if not hasattr(self, "slot_hero"):
            return
        self.fill_hero()
        ap = self.dns_active_preset()
        self.dns_lbl.set_text(f"{ap[0]} · {ELEM[ap[2]][2]}" if ap else ("Custom" if self.info["connected"] else "—"))
        for nl, ips in self.orb_names:
            ctx = nl.get_style_context()
            (ctx.add_class if self.dns_active(ips) else ctx.remove_class)("on")
        if hasattr(self, "radio_sw") and self.radio_sw.get_active() != self.radio:
            self._sw_lock = True
            self.radio_sw.set_active(self.radio)
            self._sw_lock = False
        self.fill_list(first=first)

    def fill_hero(self):
        info = self.info
        key = (info["connected"], info["ssid"], info["ip"], info["gw"])
        if key == self._hero_key:
            if getattr(self, "hero_sub", None) is not None:
                self.hero_sub.set_text(self.hero_sub_text())
            if getattr(self, "hero_top", None) is not None:
                set_rarity_cls(self.hero_top, rarity_of(info["signal"]) if info["connected"] else 0)
            return
        first = self._hero_key is None
        self._hero_key = key
        for c in self.slot_hero.get_children():
            c.destroy()
        self.h_rx = self.h_tx = None
        card = self.hero_card()
        self.slot_hero.pack_start(card, False, False, 0)
        card.show_all()
        if not first:
            appear(card, 0, dx=14, dur=0.4)

    def list_sig(self):
        return (self.radio, bool(self.nets), self.scanning and not self.nets, self.connecting,
                tuple((n["ssid"], n["active"], n["saved"], n["faint"]) for n in self.nets))

    def fill_list(self, first=False, force=False):
        real = [n for n in self.nets if not n["faint"]]
        self.count_lbl.set_text(f"{len(real)} found" + (f" · {self.hidden_n} hidden" if self.hidden_n else ""))
        sig = self.list_sig()
        if sig == self._list_sig and not force:
            for n in self.nets:
                m = self.row_meta.get(n["ssid"])
                if m is not None:
                    m.set_markup(self.row_meta_markup(n))
            return
        self._list_sig = sig
        for c in self.list_box.get_children():
            c.destroy()
        self.row_meta = {}
        lb = self.list_box
        if self.scanning and not self.nets:
            lb.pack_start(appear(placeholder("compass", "Scanning the ley lines…", "Listening to the winds of Teyvat", radar=True)),
                          False, False, 0)
        elif not self.radio:
            lb.pack_start(appear(placeholder("lock", "Wi-Fi radio is sealed", "Flip the switch above to unseal it")), False, False, 0)
        elif not self.nets:
            lb.pack_start(appear(placeholder("wifi", "No ley lines detected", "Press the refresh glyph, or add a hidden one")),
                          False, False, 0)
            lb.pack_start(appear(self.manual_row(), 0.15), False, False, 0)
        else:
            k = 0
            for n in self.nets:
                row = self.net_row(n)
                lb.pack_start(row, False, False, 0)
                if first or n["ssid"] not in self._seen_rows:
                    appear(row, min(0.6, 0.12 + 0.045 * k) if first else 0.05 * k, dx=26, dur=0.45)
                    k += 1
            lb.pack_start(appear(self.manual_row(), 0.1 + 0.045 * k if first else 0), False, False, 0)
        self._seen_rows = {n["ssid"] for n in self.nets}
        lb.show_all()

    def manual_row(self):
        b = add_cls(Gtk.Button(), "g-row ghost")
        h = box("h", 8)
        ic = Canvas(lambda cr, w, hh, c: draw_icon(cr, "plus", w / 2, hh / 2, 6 * (1 + 0.15 * c.hv), GOLD, rot=c.hv * PI / 2),
                    16, 16)
        ic.set_valign(CENTER)
        h.pack_start(ic, False, False, 0)
        h.pack_start(lbl("Hidden or missing ley line?  Attune manually", None), False, False, 0)
        b.add(h)
        hover_bind(b, ic)
        b.connect("clicked", lambda *_: self.open_pw(None, manual=True))
        return b

    def row_meta_markup(self, n):
        base = ELEM[n["elem"]][0]
        extra = f'  ·  ×{n["nodes"]}' if n.get("nodes", 1) > 1 else ""
        return (f'<span foreground="{base}" weight="bold">◆ {ELEM[n["elem"]][2]}</span>'
                f'  ·  {esc(n.get("bands", n["band"]))}  ·  {esc(n["security"])}  ·  {n["signal"]}%{extra}')

    def net_row(self, n):
        ssid = n["ssid"]
        busy = self.connecting == ssid
        b = add_cls(Gtk.Button(), "g-row" + (" on" if n["active"] else "") + (" busy" if busy else ""))
        h = box("h", 10)

        def ptile(cr, w, hh, c, ssid=ssid, fb=n):
            d = self.net_by.get(ssid, fb)
            draw_tile(cr, 1, 3, w - 2, hh - 4, rarity_of(d["signal"]), d["elem"], locked=d["security"] != "Open",
                      active=d["active"], hover=c.hv * 0.6, t=T(), busy=self.connecting == ssid, faint=d.get("faint", False))
        tile = Canvas(ptile, 42, 54, live=lambda t, ssid=ssid: self.connecting == ssid or
                      bool(self.net_by.get(ssid, {}).get("active")))
        h.pack_start(tile, False, False, 0)
        v = box("v", 2)
        v.set_valign(CENTER)
        v.pack_start(lbl(ssid, "net-name" + (" faint" if n["faint"] else ""), ell=True, maxw=20), False, False, 0)
        meta = lbl(self.row_meta_markup(n), "meta", markup=True, ell=True)
        self.row_meta[ssid] = meta
        v.pack_start(meta, False, False, 0)
        h.pack_start(v, True, True, 0)
        if busy:
            bd = lbl("ATTUNING", "badge busy")
        elif n["active"]:
            bd = lbl("ATTUNED", "badge on")
        elif n["faint"]:
            bd = lbl("FAINT", "badge faint")
        elif n["saved"]:
            bd = lbl("SAVED", "badge saved")
        else:
            bd = None
        if bd is not None:
            bd.set_valign(CENTER)
            h.pack_start(bd, False, False, 0)
        chev = Canvas(lambda cr, w, hh, c: draw_icon(cr, "chevron", w / 2 - 2 + 4 * e_out(c.hv), hh / 2, 5, GOLD, 0.6 + 0.4 * c.hv),
                      14, 14)
        chev.set_valign(CENTER)
        h.pack_start(chev, False, False, 0)
        b.add(h)
        hover_bind(b, chev, tile)
        b.set_tooltip_text(f'{ssid}\n{n["freq"]}  ·  Ch {n["chan"]}  ·  {n["rate"]}\n{n["bssid"]}'
                           + ("\nNot heard in the last scan — still attunable" if n["faint"] else ""))
        b.connect("clicked", lambda *_: self.on_net_click(self.net_by.get(ssid, n)))
        return b

    def password_revealer(self):
        rv = Gtk.Revealer()
        rv.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        rv.set_transition_duration(300 if M.enabled else 0)
        card = box("v", 6, "pw-card")
        th = box("h", 8)
        self.pw_icon = Canvas(lambda cr, w, h, c: (glow(cr, w / 2, h / 2, w / 2, "#FFE7A8", 0.3 + 0.15 * math.sin(T() * 3)),
                                                   draw_icon(cr, "lock", w / 2, h / 2, 7, GOLD)), 18, 18, live=True)
        th.pack_start(self.pw_icon, False, False, 0)
        self.pw_title = lbl("", "pw-title", markup=True, ell=True)
        th.pack_start(self.pw_title, True, True, 0)
        card.pack_start(th, False, False, 0)
        self.pw_ssid_rev = Gtk.Revealer()
        self.pw_ssid_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.pw_ssid_rev.set_transition_duration(220 if M.enabled else 0)
        self.pw_ssid = entry("Ley line name  (SSID)", on_activate=lambda: self.pw_entry.grab_focus())
        self.pw_ssid.get_style_context().add_class("pw")
        self.pw_ssid_rev.add(self.pw_ssid)
        card.pack_start(self.pw_ssid_rev, False, False, 0)
        er = box("h", 6)
        self.pw_entry = entry("Seal password", secret=True, on_activate=self.submit_pw)
        self.pw_entry.get_style_context().add_class("pw")
        er.pack_start(self.pw_entry, True, True, 0)
        er.pack_start(icon_btn("eye", 28, lambda: self.pw_entry.set_visibility(not self.pw_entry.get_visibility()),
                               "Show / hide", GOLD), False, False, 0)
        card.pack_start(er, False, False, 0)
        br = box("h", 8, homog=True)
        br.pack_start(gbtn("Cancel", "cancel", "cream", lambda: self.set_pw_open(False), small=True), True, True, 0)
        br.pack_start(gbtn("Attune", "confirm", "cream", self.submit_pw, small=True), True, True, 0)
        card.pack_start(br, False, False, 0)
        rv.add(card)
        self.pw_rev = rv
        return rv

    def set_pw_open(self, opened):
        """Open/close the password card while the network list shrinks/grows,
        so the popup keeps (almost) the same height instead of jumping."""
        rv = getattr(self, "pw_rev", None)
        sc = getattr(self, "list_sc", None)
        if rv is None:
            return
        if sc is None:
            rv.set_reveal_child(opened)
            return
        full = 204
        small = 112 if self.pw_ssid_rev.get_reveal_child() else 138
        a = getattr(self, "list_h", full)
        b = small if opened else full
        rv.set_transition_duration(260 if M.enabled else 0)

        def f(k):
            h = int(round(lerp(a, b, k)))
            self.list_h = h
            try:
                sc.set_size_request(-1, h)
                if self.mode == "mini":
                    self.resize(MINI_W + 2 * SHADOW, 1)
            except Exception:
                pass
        rv.set_reveal_child(opened)
        M.tween(0.26, f, key="pw-list")

    def open_pw(self, n, manual=False, reason=None):
        if self.mode != "mini":
            self.switch("akasha", "settings")
            return
        if manual:
            self.pending = {"ssid": None, "sec": "", "hidden": True, "profile": None}
            self.pw_title.set_markup("Attune to a <b>hidden ley line</b>  <span size='small' foreground='#8E95A6'>(empty seal = open)</span>")
            self.pw_ssid.set_text("")
            self.pw_ssid_rev.set_reveal_child(True)
        else:
            self.pending = {"ssid": n["ssid"], "sec": n.get("security", "WPA2"), "hidden": False, "profile": n.get("profile")}
            head = esc(reason) + "  ·  " if reason else "Attune to  "
            self.pw_title.set_markup(f'{head}<b>{esc(n["ssid"])}</b>')
            self.pw_ssid_rev.set_reveal_child(False)
        self.pw_entry.set_text("")
        self.pw_entry.set_visibility(False)
        self.set_pw_open(True)
        (self.pw_ssid if manual else self.pw_entry).grab_focus()

    def submit_pw(self):
        p = self.pending
        if not p:
            return
        ssid = p["ssid"] or self.pw_ssid.get_text().strip()
        if not ssid:
            shake(self.pw_ssid)
            self.toast("Name the ley line first", "err")
            return
        pw = self.pw_entry.get_text()
        min_len = 5 if "WEP" in (p["sec"] or "") else 8
        if (pw or not p["hidden"]) and len(pw) < min_len:
            shake(self.pw_entry)
            self.toast(f"Seal too short — needs {min_len}+ characters", "err")
            return
        self.set_pw_open(False)
        self.connect_net(ssid, pw or None, sec=p["sec"] or ("WPA2" if pw else ""), hidden=p["hidden"], profile=p["profile"])

    def on_net_click(self, n):
        if self.connecting:
            self.toast(f"Already attuning to {self.connecting}…", "busy", sticky=True)
            return
        if n["active"]:
            self.sever()
        elif n.get("profile"):
            self.connect_net(n["ssid"], None, sec=n["security"], profile=n["profile"])
        elif "802.1X" in n["security"]:
            self.toast("Enterprise ley line — opening NM editor", "info")
            self.spawn(["nm-connection-editor"])
        elif n["security"] == "Open" or "OWE" in n["security"]:
            self.connect_net(n["ssid"], None, sec=n["security"])
        else:
            self.open_pw(n)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  AKASHA TERMINAL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def build_akasha(self):
        R = self.root
        hdr = margins(box("h", 14), 16, 16, 6, 22)
        hdr.pack_start(Canvas(lambda cr, w, h, c: paint_logo(cr, w, h, T()), 50, 50, live=True, intro="pop", dur=0.7),
                       False, False, 0)
        tb = box("v", 0)
        tb.set_valign(CENTER)
        tb.pack_start(lbl("AKASHA TERMINAL  ·  SUMERU ACADEMIYA", "eyebrow"), False, False, 0)
        tb.pack_start(title_canvas("Celestia Network Matrix", 21), False, False, 0)
        hdr.pack_start(tb, False, False, 0)
        self.tabbar = self.make_tabbar()
        center = box("h")
        center.pack_start(self.tabbar, True, False, 0)
        hdr.pack_start(center, True, True, 0)
        self.mini_btn = gbtn("Wi-Fi", "wifi", "dark", lambda: self.switch("mini"), "Back to the quick panel", small=True)
        hdr.pack_start(self.mini_btn, False, False, 0)
        hdr.pack_start(icon_btn("close", 32, self.quit, "Close  (Esc)", rot=PI / 2), False, False, 0)
        R.pack_start(hdr, False, False, 0)
        R.pack_start(Divider(), False, False, 0)

        pt = margins(box("h", 10), 4, 24, 10, 24)
        self.pt_icon = Canvas(lambda cr, w, h, c: (glow(cr, w / 2, h / 2, w / 2, "#FFE7A8", 0.25),
                                                   draw_icon(cr, self._tab_meta()[1], w / 2, h / 2, 9, GOLD)), 22, 22, intro="pop")
        self.pt_icon.set_valign(CENTER)
        self.pt_text = box("h", 10)
        self.pt_title = lbl("", "page-title")
        self.pt_sub = lbl("", "muted")
        self.pt_sub.set_valign(CENTER)
        self.pt_text.pack_start(self.pt_title, False, False, 0)
        self.pt_text.pack_start(Icon("diamond", 6, GOLD, 0.6), False, False, 0)
        self.pt_text.pack_start(self.pt_sub, False, False, 0)
        pt.pack_start(self.pt_icon, False, False, 0)
        pt.pack_start(self.pt_text, False, False, 0)
        st = box("h", 6)

        def pdot(cr, w, h, c):
            t = T()
            col = "#7CE0C3" if self.info["connected"] else "#E07A7A"
            glow(cr, w / 2, h / 2, w / 2 * (0.8 + 0.2 * math.sin(t * 3)), col, 0.8)
            draw_icon(cr, "diamond", w / 2, h / 2, 3, "#FFFFFF")
        st.pack_start(Canvas(pdot, 16, 16, live=True), False, False, 0)
        self.st_lbl = lbl("", "tiny")
        st.pack_start(self.st_lbl, False, False, 0)
        st.set_valign(CENTER)
        pt.pack_end(st, False, False, 0)
        R.pack_start(pt, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_duration(340 if M.enabled else 0)
        self.stack.set_homogeneous(True)
        margins(self.stack, 0, 22, 20, 22)
        R.pack_start(self.stack, True, True, 0)
        self.update_status()
        for i, w in enumerate((hdr, pt)):
            appear(w, 0.03 + i * 0.06, dx=0, dur=0.45)
        self.set_tab(self.tab, animate=False)

    def update_status(self):
        if getattr(self, "st_lbl", None) is None:
            return
        i = self.info
        self.st_lbl.set_text(f'{i["ssid"]}  ·  {i["ip"]}' if i["connected"] else "Not attuned")
        mb = getattr(self, "mini_btn", None)
        if mb is not None:
            name = i["ssid"] if i["connected"] and i.get("ssid") else "Wi-Fi"
            mb.lbl.set_text(name)
            mb.set_tooltip_text(f"{name} — back to the quick panel")

    def make_tabbar(self):
        n = len(TABS)
        W, H = n * 46 + 12, 50
        cv = Canvas(lambda cr, w, h, c: draw_tabbar(cr, w, h, TABS, c.tab_pos, c.hov, T()), W, H, live=True)
        cv.tab_pos = float(TAB_IDX.get(self.tab, 0))
        cv.hov = [0.0] * n
        cv.hidx = -1
        cv.set_valign(CENTER)
        cv.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK |
                      Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)

        def idx_at(x):
            i = int((x - 6) // 46)
            return i if 0 <= i < n else -1

        def set_hover(i):
            if i == cv.hidx:
                return
            old, cv.hidx = cv.hidx, i
            for j, target in ((old, 0.0), (i, 1.0)):
                if j < 0:
                    continue
                s = cv.hov[j]
                M.tween(0.2, lambda k, j=j, s=s, e=target: (cv.hov.__setitem__(j, lerp(s, e, k)), cv.queue_draw()),
                        key=(id(cv), "hv", j), owner=cv)

        def on_motion(w, e):
            set_hover(idx_at(e.x))
            return False

        def on_leave(w, e):
            set_hover(-1)
            return False

        def on_release(w, e):
            i = idx_at(e.x)
            if i >= 0:
                self.set_tab(TABS[i][0])
            return True

        def on_tip(w, x, y, kb, tip):
            i = idx_at(x)
            if i < 0:
                return False
            tip.set_text(f"{TABS[i][2]}  —  {TABS[i][3]}")
            return True
        cv.connect("motion-notify-event", on_motion)
        cv.connect("leave-notify-event", on_leave)
        cv.connect("button-press-event", lambda *_: True)
        cv.connect("button-release-event", on_release)
        cv.set_has_tooltip(True)
        cv.connect("query-tooltip", on_tip)
        cv.live = lambda t: True
        return cv

    def _tab_meta(self):
        for t in TABS:
            if t[0] == self.tab:
                return t
        return TABS[0]

    def sig_of(self, tid):
        i = self.info
        if tid == "overview":
            return (i["connected"], i["ssid"])
        if tid == "networks":
            return (self.radio, self.scanning and not self.nets,
                    tuple((n["ssid"], n["active"], n["saved"], n["faint"]) for n in self.nets))
        if tid == "dns":
            return (i["connected"], i["conn"], i.get("dns_cfg"), i["dns"])
        if tid == "archive":
            return (tuple(p["name"] for p in self.profiles), i.get("conn"))
        return None

    def _make_page(self, tid):
        w = getattr(self, "page_" + tid)()
        self.page_gen += 1
        name = f"{tid}-{self.page_gen}"
        self.stack.add_named(w, name)
        w.show_all()
        self.pages[tid], self.page_names[tid], self.page_sigs[tid] = w, name, self.sig_of(tid)
        return w

    def drop_page(self, tid):
        w = self.pages.pop(tid, None)
        self.page_names.pop(tid, None)
        self.page_sigs.pop(tid, None)
        if w is not None:
            w.destroy()
        later_trim()

    def replace_page(self, tid):
        old = self.pages.get(tid)
        self._make_page(tid)
        if tid == self.tab:
            self.stack.set_visible_child_full(self.page_names[tid], Gtk.StackTransitionType.CROSSFADE)
        if old is not None:
            GLib.timeout_add(420, lambda: (old.destroy(), later_trim(), False)[2])

    def set_tab(self, tid, animate=True):
        if self.mode != "akasha" or not hasattr(self, "stack"):
            self.tab = tid
            return
        old = self.tab
        self.tab = tid
        if tid not in self.pages:
            self._make_page(tid)
        elif tid != "settings" and self.sig_of(tid) != self.page_sigs.get(tid):
            self.drop_page(tid)
            self._make_page(tid)
        if animate and M.enabled and old != tid:
            tr = Gtk.StackTransitionType.SLIDE_LEFT if TAB_IDX[tid] > TAB_IDX.get(old, 0) else Gtk.StackTransitionType.SLIDE_RIGHT
        else:
            tr = Gtk.StackTransitionType.NONE
        self.stack.set_visible_child_full(self.page_names[tid], tr)
        _, _, name, sub = self._tab_meta()
        self.pt_title.set_text(name)
        self.pt_sub.set_text(sub)
        if animate:
            appear(self.pt_text, 0.05, dx=16, dur=0.38)
            self.pt_icon.play(0, 0.5)
        else:
            self.pt_icon.queue_draw()
        cv = self.tabbar
        s, e = cv.tab_pos, float(TAB_IDX[tid])
        if animate:
            M.tween(0.42, lambda k: (setattr(cv, "tab_pos", lerp(s, e, k)), cv.queue_draw()), ease=e_out,
                    key=(id(cv), "pos"), owner=cv)
        else:
            cv.tab_pos = e
            cv.queue_draw()
        if old != tid and old == "ports" and old in self.pages:
            GLib.timeout_add(450, lambda: (self.drop_page("ports") if self.tab != "ports" else None, False)[1])

    def refresh_akasha(self):
        self.update_status()
        for tid in list(self.pages):
            if tid in ("ports", "settings"):
                continue
            if self.sig_of(tid) == self.page_sigs.get(tid):
                if tid == "networks":
                    for cv in getattr(self, "tiles", {}).values():
                        cv.queue_draw()
                continue
            if tid == self.tab:
                if not self.user_busy():
                    self.replace_page(tid)
            else:
                self.drop_page(tid)

    # ── Overview ──
    def page_overview(self):
        info = self.info
        con = info["connected"]
        band, el = band_of(info["freq"])
        r = rarity_of(info["signal"]) if con else 0
        page = box("h", 16)
        left = box("v", 6, "panel")
        left.set_size_request(320, -1)
        self.dial = Canvas(lambda cr, w, h, c: draw_dial(cr, w, h, self.sig_anim, self.info["connected"], T(), e_out(c.p)),
                           296, 288, live=True)
        self.dial.kind = None
        self.dial.p = 0.0 if M.enabled else 1.0
        M.tween(1.3, self.dial._setp, ease=e_lin, delay=0.15, owner=self.dial)
        left.pack_start(self.dial, False, False, 0)
        left.pack_start(lbl(info["ssid"] if con else "Not Attuned", "hero-name", 0.5, ell=True), False, False, 0)
        if con:
            st = Stars(lambda: rarity_of(self.info["signal"]) if self.info["connected"] else 0, 15, 0.5)
            st.set_halign(CENTER)
            left.pack_start(st, False, False, 0)
        left.pack_start(lbl(f"{ELEM[el][2]} Ley Line  ·  {band}  ·  {RARITY_NAME[r]}" if con else "Select a ley line to attune",
                            "muted", 0.5), False, False, 0)
        left.pack_start(margins(lbl(FLAVOR[el] if con else "The Akasha awaits your connection, Traveler.",
                                    "flavor-dark", 0.5, wrap=True), 4, 8, 0, 8), False, False, 0)
        page.pack_start(left, False, False, 0)

        right = box("v", 12)
        tp = box("v", 0, "panel")
        self.traffic = Canvas(lambda cr, w, h, c: draw_traffic(cr, w, h, self.rx_hist, self.tx_hist,
                                                               clamp((T() - self.sample_t) / 1.0), T()),
                              -1, 148, live=True, intro="rise", delay=0.1)
        tp.pack_start(self.traffic, True, True, 0)
        right.pack_start(tp, False, False, 0)
        ap = box("v", 2, "panel tight")
        rows = [("wifi", "Ley Line (SSID)", info["ssid"] if con else "—", "ssid"), ("diamond", "IPv4 Address", info["ip"], "ip"),
                ("compass", "Gateway", info["gw"], "gw"), ("anemo", "DNS", info["dns"], "dns"),
                ("waypoint", "BSSID", info["bssid"], "bssid"), ("key", "Hardware MAC", info["mac"], "mac"),
                ("chart", "Channel · Freq", f'Ch {info["chan"]}  ·  {info["freq"]}', "chanfreq"),
                ("electro", "Link Rate", info["rate"], "rate"), ("lock", "Security", info["security"], "security")]
        for i, (ic, k, v, ref) in enumerate(rows):
            row = self.attr_row(k, v, ic, cream=False, alt=i % 2 == 1, ref=ref)
            ap.pack_start(row, False, False, 0)
            appear(row, 0.12 + i * 0.035, dx=18, dur=0.4)
        right.pack_start(ap, False, False, 0)
        acts = box("h", 10, homog=True)
        acts.pack_start(gbtn("Wi-Fi QR", "qr", "dark", self.on_qr, "Share this ley line as a QR code"), True, True, 0)
        acts.pack_start(gbtn("Rescan", "refresh", "dark", self.rescan, "Scan the ley lines again"), True, True, 0)
        if con:
            acts.pack_start(gbtn("Disconnect", "cancel", "cream", self.sever), True, True, 0)
        else:
            acts.pack_start(gbtn("Ley Lines", "wifi", "cream", lambda: self.set_tab("networks")), True, True, 0)
        right.pack_start(appear(acts, 0.45), False, False, 0)
        page.pack_start(right, True, True, 0)
        appear(left, 0.0, dur=0.5)
        return page

    def update_overview_vals(self):
        i = self.info
        vals = {"ssid": i["ssid"] if i["connected"] else "—", "ip": i["ip"], "gw": i["gw"], "dns": i["dns"],
                "bssid": i["bssid"], "mac": i["mac"], "chanfreq": f'Ch {i["chan"]}  ·  {i["freq"]}',
                "rate": i["rate"], "security": i["security"]}
        for k, l in list(self.ov_vals.items()):
            if getattr(l, "_dead", False):
                continue
            try:
                if l.get_text() != vals.get(k, l.get_text()):
                    l.set_text(vals[k])
            except Exception:
                self.ov_vals.pop(k, None)

    # ── Networks (inventory) ──
    def page_networks(self):
        page = box("h", 16)
        left = box("v", 10)
        tb = box("h", 8)
        tb.pack_start(lbl("CHANNEL LOAD", "eyebrow"), False, False, 0)
        cc = channel_counts(self.nets)
        for i, (c, cnt) in enumerate(sorted(cc.items(), key=lambda kv: -kv[1])[:5]):
            colr = "#74C2A8" if cnt == 1 else ("#FAB632" if cnt <= 3 else "#EF7938")
            chip = lbl(f'<span foreground="{colr}">●</span>  Ch {esc(c)} · {cnt}', "chip", markup=True)
            tb.pack_start(appear(chip, 0.1 + i * 0.05), False, False, 0)
        tb.pack_end(gbtn("Rescan", "refresh", "dark", self.rescan, small=True), False, False, 0)
        tb.pack_end(gbtn("Hidden", "plus", "dark", lambda: self.set_tab("settings"), "Attune a hidden ley line", small=True),
                    False, False, 0)
        left.pack_start(tb, False, False, 0)
        self.tiles = {}
        if self.scanning and not self.nets:
            inner = placeholder("compass", "Scanning the ley lines…", "Listening to the winds of Teyvat", radar=True)
        elif not self.radio:
            inner = placeholder("lock", "Wi-Fi radio is sealed", "Enable Wi-Fi from the mini popup switch")
        elif not self.nets:
            inner = placeholder("wifi", "No ley lines detected", "Press Rescan, or attune a hidden one in Pact Settings")
        else:
            inner = Gtk.FlowBox()
            inner.set_valign(Gtk.Align.START)
            inner.set_selection_mode(Gtk.SelectionMode.NONE)
            inner.set_homogeneous(True)
            inner.set_min_children_per_line(3)
            inner.set_max_children_per_line(8)
            inner.set_column_spacing(8)
            inner.set_row_spacing(10)
            for i, n in enumerate(self.nets):
                ssid = n["ssid"]
                b = add_cls(Gtk.Button(), "flat-x")
                b.set_tooltip_text(f'{ssid}  ·  {n["signal"]}%  ·  {n.get("bands", n["band"])}'
                                   + ("  ·  faint" if n["faint"] else ""))

                def ptile(cr, w, h, c, ssid=ssid, fb=n):
                    d = self.net_by.get(ssid, fb)
                    draw_tile(cr, 5, 7, w - 10, h - 12, rarity_of(d["signal"]), d["elem"], d["ssid"],
                              locked=d["security"] != "Open", active=d["active"], hover=c.hv,
                              selected=(self.sel_ssid == ssid), saved=d["saved"], t=T(),
                              busy=self.connecting == ssid, faint=d.get("faint", False))
                cv = Canvas(ptile, 96, 124, intro="pop", delay=min(0.7, 0.05 + i * 0.035), dur=0.55,
                            live=lambda t, ssid=ssid: self.sel_ssid == ssid or self.connecting == ssid or
                            bool(self.net_by.get(ssid, {}).get("active")))
                b.add(cv)
                hover_bind(b, cv)
                b.connect("clicked", lambda _b, ssid=ssid, c=cv: (c.kick(), self.select_net(ssid)))
                inner.add(b)
                self.tiles[ssid] = cv
        left.pack_start(scrolled(inner), True, True, 0)
        page.pack_start(left, True, True, 0)
        self.detail = Gtk.Stack()
        self.detail.set_transition_duration(260 if M.enabled else 0)
        self.detail.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.detail.set_size_request(320, -1)
        self.detail_gen = 0
        page.pack_start(self.detail, False, False, 0)
        if not any(n["ssid"] == self.sel_ssid for n in self.nets):
            act = [n for n in self.nets if n["active"]]
            self.sel_ssid = (act[0] if act else self.nets[0])["ssid"] if self.nets else None
        self.fill_detail(animate=False)
        return page

    def select_net(self, ssid):
        if ssid == self.sel_ssid:
            return
        self.sel_ssid = ssid
        for cv in self.tiles.values():
            cv.queue_draw()
        self.fill_detail()

    def fill_detail(self, animate=True):
        n = self.net_by.get(self.sel_ssid) if self.sel_ssid else None
        old = self.detail.get_visible_child()
        content = self.build_detail(n)
        self.detail_gen += 1
        name = f"d{self.detail_gen}"
        self.detail.add_named(content, name)
        content.show_all()
        self.detail.set_visible_child_full(name, Gtk.StackTransitionType.CROSSFADE if animate else Gtk.StackTransitionType.NONE)
        if old is not None:
            GLib.timeout_add(320, lambda: (old.destroy(), False)[1])

    def build_detail(self, n):
        outer = box("v", 0)
        self.d_entry = None
        if not n:
            p = box("v", 0, "panel")
            p.pack_start(placeholder("wifi", "No ley line selected", "Pick a tile from the inventory"), True, True, 0)
            outer.pack_start(p, True, True, 0)
            return outer
        r = rarity_of(n["signal"])
        el = n["elem"]
        ov = Gtk.Overlay()
        top = box("h", 8, f"hero-top big r{r}")
        lv = box("v", 3)
        lv.set_valign(CENTER)
        lv.pack_start(lbl(n["ssid"], "hero-name", ell=True, maxw=16), False, False, 0)
        lv.pack_start(lbl(f'{ELEM[el][2]} Ley Line  ·  {n.get("bands", n["band"])}', "hero-type"), False, False, 0)
        lv.pack_start(lbl(RARITY_NAME[r].upper(), "hero-rarity"), False, False, 0)
        lv.pack_start(Stars(r, 14, 0.15), False, False, 2)
        top.pack_start(lv, True, True, 0)
        top.pack_end(Canvas(lambda cr, w, h, c: draw_art(cr, w, h, el, None, T()), 86, 86, live=True, intro="pop", dur=0.6),
                     False, False, 0)
        ov.add(top)
        sh = Canvas(lambda cr, w, h, c: draw_shimmer(cr, w, h, T() + 0.6, 14), live=lambda t: ((t + 0.6) % 4.6) < 1.25)
        ov.add_overlay(sh)
        try:
            ov.set_overlay_pass_through(sh, True)
        except Exception:
            pass
        outer.pack_start(ov, False, False, 0)
        body = box("v", 1, "hero-bottom big")
        crowd = channel_counts(self.nets).get(n["chan"], 1)
        ctag = "Clear" if crowd == 1 else (f"Busy ({crowd})" if crowd <= 3 else f"Congested ({crowd})")
        status = ("Attuned" if n["active"] else ("Saved · " + n["profile"] if n["saved"] else "Undiscovered")) + \
                 ("  ·  faint" if n["faint"] else "")
        rows = [("chart", "Signal", f'{n["signal"]}%'), ("compass", "Channel", f'{n["chan"]}  ·  {ctag}'),
                ("electro", "Frequency", n["freq"]), ("arrow_down", "Link Rate", n["rate"]),
                ("lock", "Security", n["security"]), ("waypoint", "BSSID", n["bssid"]), ("key", "Status", status)]
        if n.get("nodes", 1) > 1:
            rows.insert(3, ("anemo", "Mesh nodes", f'{n["nodes"]} access points'))
        for i, (ic, k, v) in enumerate(rows):
            body.pack_start(appear(self.attr_row(k, v, ic), 0.06 + i * 0.03, dx=12, dur=0.35), False, False, 0)
        body.pack_start(margins(lbl(FLAVOR.get(el, ""), "flavor", wrap=True), 8, 8, 0, 8), False, False, 0)
        outer.pack_start(body, True, True, 0)
        act = margins(box("v", 8), 12, 0, 0, 0)
        need_pw = not n["active"] and not n["saved"] and n["security"] != "Open" and "OWE" not in n["security"]
        if need_pw:
            er = box("h", 6)
            self.d_entry = entry("Seal password  (min 8)", secret=True, on_activate=lambda: self.attune_detail(n))
            er.pack_start(self.d_entry, True, True, 0)
            de = self.d_entry
            er.pack_start(icon_btn("eye", 28, lambda: de.set_visibility(not de.get_visibility()), "Show / hide", GOLD),
                          False, False, 0)
            act.pack_start(er, False, False, 0)
        row = box("h", 10, homog=True)
        if n["active"]:
            row.pack_start(gbtn("Disconnect", "cancel", "cream", self.sever), True, True, 0)
        else:
            row.pack_start(gbtn("Attune", "confirm", "cream", lambda: self.attune_detail(n)), True, True, 0)
        if n["saved"]:
            row.pack_start(gbtn("Forget", "cancel", "dark", lambda: self.forget(n["profile"])), True, True, 0)
        act.pack_start(row, False, False, 0)
        outer.pack_start(appear(act, 0.25), False, False, 0)
        return outer

    def attune_detail(self, n):
        if self.connecting:
            self.toast(f"Already attuning to {self.connecting}…", "busy", sticky=True)
            return
        pw = None
        if self.d_entry is not None:
            pw = self.d_entry.get_text()
            min_len = 5 if "WEP" in n["security"] else 8
            if len(pw) < min_len:
                shake(self.d_entry)
                self.toast(f"Seal too short — needs {min_len}+ characters", "err")
                self.d_entry.grab_focus()
                return
        if "802.1X" in n["security"]:
            self.toast("Enterprise ley line — opening NM editor", "info")
            self.spawn(["nm-connection-editor"])
            return
        self.connect_net(n["ssid"], pw, sec=n["security"], profile=n.get("profile"))

    # ── DNS ──
    def page_dns(self):
        page = box("v", 14)
        cur = box("h", 14, "panel")
        ap = self.dns_active_preset()
        el = ap[2] if ap else "hydro"
        cur.pack_start(Canvas(lambda cr, w, h, c: draw_orb(cr, w, h, el, True, 0.0, T()), 56, 56, live=True, intro="pop"),
                       False, False, 0)
        tv = box("v", 1)
        tv.set_valign(CENTER)
        tv.pack_start(lbl("CURRENT RESONANCE", "eyebrow"), False, False, 0)
        nm = f"{ap[0]}  ·  {ELEM[ap[2]][2]}" if ap else ("Custom Resolver" if self.info["connected"] else "Not attuned")
        tv.pack_start(lbl(nm, "page-title"), False, False, 0)
        tv.pack_start(lbl(self.info["dns"], "muted", ell=True, maxw=40), False, False, 0)
        cur.pack_start(tv, True, True, 0)
        cb = box("h", 8)
        cb.set_valign(CENTER)
        self.dns_entry = entry("Custom:  1.1.1.1  8.8.8.8", on_activate=self.apply_custom_dns)
        self.dns_entry.set_width_chars(22)
        cb.pack_start(self.dns_entry, False, False, 0)
        cb.pack_start(gbtn("Resonate", "confirm", "cream", self.apply_custom_dns, small=True), False, False, 0)
        cur.pack_end(cb, False, False, 0)
        page.pack_start(appear(cur, 0.0, dx=0), False, False, 0)

        fb = Gtk.FlowBox()
        fb.set_selection_mode(Gtk.SelectionMode.NONE)
        fb.set_homogeneous(True)
        fb.set_min_children_per_line(4)
        fb.set_max_children_per_line(7)
        fb.set_column_spacing(6)
        fb.set_row_spacing(8)
        fb.set_halign(CENTER)
        fb.set_valign(Gtk.Align.START)
        for i, (name, ips, e, fa, en) in enumerate(DNS_PRESETS):
            b = add_cls(Gtk.Button(), "flat-x")
            cv = Canvas(lambda cr, w, h, c, a=(name, ips, e, fa, en): draw_dns_card(cr, w, h, *a, self.dns_active(a[1]),
                                                                                     c.hv, T(), c.kick_age()),
                        124, 206, live=lambda t, ips=ips: self.dns_active(ips), intro="rise", delay=0.08 + i * 0.06, dur=0.55)
            b.add(cv)
            hover_bind(b, cv)
            b.set_tooltip_text(f"{name}  ·  {ips or 'Router / DHCP'}")
            b.connect("clicked", lambda _b, n=name, i_=ips, c=cv: (c.kick(), self.on_dns(n, i_)))
            fb.add(b)
        page.pack_start(fb, False, False, 0)
        page.pack_start(appear(lbl("✦  Choose an element to resonate your DNS — it applies to the attuned ley line and reconnects it.",
                                   "tiny", 0.5), 0.5), False, False, 0)
        return page

    def apply_custom_dns(self):
        raw = self.dns_entry.get_text().replace(",", " ").split()
        ok = [x for x in raw if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", x) or (":" in x and re.fullmatch(r"[0-9a-fA-F:]+", x))]
        if not ok:
            shake(self.dns_entry)
            self.toast("Enter one or more valid IP addresses", "err")
            return
        self.on_dns("Custom", " ".join(ok))

    # ── Archive (saved + hotspot) ──
    def page_archive(self):
        page = box("h", 16)
        left = box("v", 10, "panel")
        profs = [p for p in self.profiles]
        left.pack_start(section("SAVED LEY LINES", lbl(str(len(profs)), "tiny")), False, False, 0)
        lst = box("v", 6)
        if not profs:
            lst.pack_start(placeholder("book", "The archive is empty", "Ley lines you attune to will be recorded here"), False, False, 0)
        for i, p in enumerate(profs):
            name = p["name"]
            on = name == self.info.get("conn")
            row = box("h", 10, "row-static" + (" alt" if i % 2 else "") + (" on" if on else ""))
            row.pack_start(Icon("waypoint" if p.get("mode") == "ap" else "key", 16, GOLD), False, False, 0)
            nv = box("v", 0)
            nv.pack_start(lbl(name, "net-name", ell=True), False, False, 0)
            if p["ssid"] != name or p.get("mode") == "ap":
                nv.pack_start(lbl(("Waypoint · " if p.get("mode") == "ap" else "SSID · ") + p["ssid"], "meta", ell=True), False, False, 0)
            row.pack_start(nv, True, True, 0)
            if on:
                bd = lbl("ATTUNED", "badge on")
                bd.set_valign(CENTER)
                row.pack_start(bd, False, False, 0)
            else:
                row.pack_start(gbtn("Attune", "confirm", "cream",
                                    lambda p=p: self.connect_net(p["ssid"], None, profile=p["name"]), small=True), False, False, 0)
            row.pack_start(gbtn("Forget", "cancel", "dark", lambda n_=name: self.forget(n_), small=True), False, False, 0)
            lst.pack_start(row, False, False, 0)
            if i < 16:
                appear(row, 0.05 + i * 0.04, dx=22)
        left.pack_start(scrolled(lst), True, True, 0)
        page.pack_start(left, True, True, 0)

        right = box("v", 0)
        right.set_size_request(320, -1)
        ov = Gtk.Overlay()
        top = box("h", 8, "hero-top big r4")
        lv = box("v", 3)
        lv.set_valign(CENTER)
        lv.pack_start(lbl("Teleport Waypoint", "hero-name"), False, False, 0)
        lv.pack_start(lbl("Portable Hotspot  ·  Share your ley line", "hero-type"), False, False, 0)
        lv.pack_start(Stars(4, 14, 0.2), False, False, 2)
        top.pack_start(lv, True, True, 0)
        top.pack_end(Canvas(lambda cr, w, h, c: draw_art(cr, w, h, "electro", "waypoint", T()), 80, 80, live=True, intro="pop"),
                     False, False, 0)
        ov.add(top)
        sh = Canvas(lambda cr, w, h, c: draw_shimmer(cr, w, h, T() + 1.7, 14), live=lambda t: ((t + 1.7) % 4.6) < 1.25)
        ov.add_overlay(sh)
        try:
            ov.set_overlay_pass_through(sh, True)
        except Exception:
            pass
        right.pack_start(ov, False, False, 0)
        body = box("v", 6, "hero-bottom big")
        body.pack_start(margins(lbl("Waypoint name", "ink"), 2, 0, 0, 4), False, False, 0)
        self.hs_ssid = entry("Hotspot SSID", on_cream=True)
        self.hs_ssid.set_text("Celestia-AP")
        body.pack_start(self.hs_ssid, False, False, 0)
        body.pack_start(margins(lbl("Seal  (WPA2 password, min 8)", "ink"), 4, 0, 0, 4), False, False, 0)
        self.hs_pw = entry("••••••••", secret=True, on_cream=True)
        body.pack_start(self.hs_pw, False, False, 0)
        body.pack_start(margins(lbl("Activating a waypoint lets fellow travelers teleport into your ley line. "
                                    "Your Wi-Fi card will act as an access point.", "flavor", wrap=True), 8, 4, 0, 4), False, False, 0)
        right.pack_start(body, True, True, 0)
        acts = margins(box("h", 10, homog=True), 12, 0, 0, 0)
        acts.pack_start(gbtn("Activate", "confirm", "cream", self.on_hotspot), True, True, 0)
        acts.pack_start(gbtn("Deactivate", "cancel", "dark", self.stop_hotspot), True, True, 0)
        right.pack_start(acts, False, False, 0)
        page.pack_start(appear(right, 0.1, dx=0), False, False, 0)
        return page

    # ── Ports ──
    def page_ports(self):
        page = box("v", 10)
        socks = list_sockets()
        tcp = sum(1 for s in socks if s[0].startswith("TCP"))
        udp = sum(1 for s in socks if s[0].startswith("UDP"))
        sm = box("h", 18, "panel")
        for ic, k, v, c in (("shield", "LISTENING", len(socks), GOLD), ("anemo", "TCP", tcp, None), ("geo", "UDP", udp, None)):
            g = box("h", 8)
            g.pack_start(Canvas(lambda cr, w, h, cc, ic=ic, c=c: draw_icon(cr, ic, w / 2, h / 2, 11, c), 22, 22, intro="pop"),
                         False, False, 0)
            vv = box("v", 0)
            vv.pack_start(lbl(k, "eyebrow"), False, False, 0)
            vv.pack_start(lbl(str(v), "page-title"), False, False, 0)
            g.pack_start(vv, False, False, 0)
            sm.pack_start(g, False, False, 0)
        sm.pack_end(gbtn("Refresh", "refresh", "dark", lambda: self.replace_page("ports"), small=True), False, False, 0)
        page.pack_start(sm, False, False, 0)
        hdr = margins(box("h", 10), 0, 12, 0, 12)
        for t, wdt, exp in (("PROTO", 70, False), ("STATE", 80, False), ("LOCAL ADDRESS", -1, True), ("PROCESS", 230, False)):
            l = lbl(t, "eyebrow")
            l.set_size_request(wdt, -1)
            hdr.pack_start(l, exp, exp, 0)
        page.pack_start(hdr, False, False, 0)
        lst = box("v", 4)
        if not socks:
            lst.pack_start(placeholder("shield", "No listening sockets", "This vessel is quiet"), False, False, 0)
        for i, (proto, state, local, proc) in enumerate(socks[:80]):
            row = box("h", 10, "row-static" + (" alt" if i % 2 else ""))
            c = ELEM["anemo"][0] if proto.startswith("TCP") else ELEM["geo"][0]
            pl = lbl(f'<span foreground="{c}" weight="bold">◆ {esc(proto)}</span>', markup=True)
            pl.set_size_request(70, -1)
            row.pack_start(pl, False, False, 0)
            s = lbl(state, "tiny")
            s.set_size_request(80, -1)
            row.pack_start(s, False, False, 0)
            row.pack_start(lbl(local, "aval", ell=True), True, True, 0)
            p = lbl(proc, "akey", ell=True)
            p.set_size_request(230, -1)
            row.pack_start(p, False, False, 0)
            lst.pack_start(row, False, False, 0)
            if i < 14:
                appear(row, 0.05 + i * 0.03, dx=18, dur=0.35)
        page.pack_start(scrolled(lst), True, True, 0)
        return page

    # ── Pact Settings ──
    def page_settings(self):
        page = box("h", 16)
        left = box("v", 0)
        left.set_size_request(380, -1)
        ov = Gtk.Overlay()
        top = box("h", 8, "hero-top big r3")
        lv = box("v", 3)
        lv.set_valign(CENTER)
        lv.pack_start(lbl("Hidden Domain", "hero-name"), False, False, 0)
        lv.pack_start(lbl("Attune any ley line by name — hidden or unheard", "hero-type"), False, False, 0)
        lv.pack_start(Stars(3, 14, 0.2), False, False, 2)
        top.pack_start(lv, True, True, 0)
        top.pack_end(Canvas(lambda cr, w, h, c: draw_art(cr, w, h, "hydro", "hidden", T()), 80, 80, live=True, intro="pop"),
                     False, False, 0)
        ov.add(top)
        sh = Canvas(lambda cr, w, h, c: draw_shimmer(cr, w, h, T() + 2.2, 14), live=lambda t: ((t + 2.2) % 4.6) < 1.25)
        ov.add_overlay(sh)
        try:
            ov.set_overlay_pass_through(sh, True)
        except Exception:
            pass
        left.pack_start(ov, False, False, 0)
        body = box("v", 6, "hero-bottom big")
        body.pack_start(margins(lbl("Ley line name  (SSID)", "ink"), 2, 0, 0, 4), False, False, 0)
        self.mn_ssid = entry("e.g.  Mondstadt-5G", on_cream=True)
        body.pack_start(self.mn_ssid, False, False, 0)
        body.pack_start(margins(lbl("Seal type", "ink"), 4, 0, 0, 4), False, False, 0)
        self.mn_sec = "WPA2"

        def set_sec(v):
            self.mn_sec = v
        body.pack_start(margins(seg([("Open", "Open"), ("WPA / WPA2", "WPA2"), ("WPA3", "WPA3"), ("WEP", "WEP")], "WPA2", set_sec),
                                0, 0, 0, 2), False, False, 0)
        body.pack_start(margins(lbl("Seal  (password)", "ink"), 4, 0, 0, 4), False, False, 0)
        er = box("h", 6)
        self.mn_pw = entry("••••••••", secret=True, on_cream=True, on_activate=self.manual_attune)
        er.pack_start(self.mn_pw, True, True, 0)
        mp = self.mn_pw
        er.pack_start(icon_btn("eye", 28, lambda: mp.set_visibility(not mp.get_visibility()), "Show / hide", INK2), False, False, 0)
        body.pack_start(er, False, False, 0)
        hr = margins(box("h", 8), 6, 4, 0, 4)
        hr.pack_start(lbl("Hidden ley line (SSID not broadcast)", "ink"), True, True, 0)
        self.mn_hidden = Gtk.Switch()
        self.mn_hidden.set_active(True)
        self.mn_hidden.set_valign(CENTER)
        hr.pack_start(self.mn_hidden, False, False, 0)
        body.pack_start(hr, False, False, 0)
        body.pack_start(margins(lbl("If a network is visible on your phone but not here, attune it by name — Celestia "
                                    "probes for it directly and writes the profile for you.", "flavor", wrap=True),
                                8, 4, 0, 4), False, False, 0)
        left.pack_start(body, True, True, 0)
        acts = margins(box("h", 10, homog=True), 12, 0, 0, 0)
        acts.pack_start(gbtn("Attune", "confirm", "cream", self.manual_attune), True, True, 0)
        acts.pack_start(gbtn("Clear", "cancel", "dark", lambda: (self.mn_ssid.set_text(""), self.mn_pw.set_text(""))), True, True, 0)
        left.pack_start(acts, False, False, 0)
        page.pack_start(appear(left, 0.0, dx=0), False, False, 0)

        right = box("v", 10, "panel")
        right.pack_start(section("PREFERENCES"), False, False, 0)
        prefs = [("motion", "Elemental animations", "Transitions, hover glows, pop-ins", "anim"),
                 ("primogem", "Floating motes", "Drifting light motes behind the panels", "motes"),
                 ("refresh", "Auto-scan", "Probe the ley lines on open & every 30 s", "autoscan")]
        for i, (ic, title, sub, key) in enumerate(prefs):
            row = box("h", 10, "row-static" + (" alt" if i % 2 else ""))
            row.pack_start(Icon(ic, 18, GOLD), False, False, 0)
            tv = box("v", 0)
            tv.pack_start(lbl(title, "pref-title"), False, False, 0)
            tv.pack_start(lbl(sub, "pref-sub"), False, False, 0)
            row.pack_start(tv, True, True, 0)
            sw = Gtk.Switch()
            sw.set_active(bool(PREFS[key]))
            sw.set_valign(CENTER)
            sw.connect("notify::active", lambda s, _p, k=key: self.set_pref(k, s.get_active()))
            row.pack_start(sw, False, False, 0)
            right.pack_start(appear(row, 0.08 + i * 0.05, dx=20), False, False, 0)
        fr = box("h", 10, "row-static alt")
        fr.pack_start(Icon("chart", 18, GOLD), False, False, 0)
        tv = box("v", 0)
        tv.pack_start(lbl("Motion frame rate", "pref-title"), False, False, 0)
        tv.pack_start(lbl("Lower = less CPU", "pref-sub"), False, False, 0)
        fr.pack_start(tv, True, True, 0)
        fps_seg = seg([("20", 20), ("30", 30), ("45", 45), ("60", 60)], PREFS["fps"], lambda v: self.set_pref("fps", v), dark=True)
        fps_seg.set_valign(CENTER)
        fr.pack_start(fps_seg, False, False, 0)
        right.pack_start(appear(fr, 0.25, dx=20), False, False, 0)
        pr = box("h", 8, "row-static")
        pr.pack_start(Icon("waypoint", 18, GOLD), False, False, 0)
        tv = box("v", 0)
        tv.pack_start(lbl("Mini popup offset", "pref-title"), False, False, 0)
        tv.pack_start(lbl("Top / right margin in px", "pref-sub"), False, False, 0)
        pr.pack_start(tv, True, True, 0)
        self.off_top = entry("top", small=True)
        self.off_top.set_width_chars(4)
        self.off_top.set_text(str(PREFS["top"]))
        self.off_right = entry("right", small=True)
        self.off_right.set_width_chars(4)
        self.off_right.set_text(str(PREFS["right"]))
        for e in (self.off_top, self.off_right):
            e.set_valign(CENTER)
            pr.pack_start(e, False, False, 0)
        pr.pack_start(gbtn("Save", "confirm", "cream", self.save_offsets, small=True), False, False, 0)
        right.pack_start(appear(pr, 0.3, dx=20), False, False, 0)

        right.pack_start(margins(section("SYSTEM"), 6, 0, 0, 0), False, False, 0)
        g = Gtk.Grid()
        g.set_column_spacing(10)
        g.set_row_spacing(10)
        g.set_column_homogeneous(True)
        btns = [gbtn("Deep rescan", "refresh", "dark", self.rescan, "Probe all channels again"),
                gbtn("Restart network", "power", "dark", self.restart_networking, "nmcli networking off → on"),
                gbtn("Forget faint cache", "cancel", "dark", self.clear_cache, "Drop ley lines not heard recently"),
                gbtn("NM editor (legacy)", "gear", "dark", lambda: self.spawn(["nm-connection-editor"]),
                     "Raw NetworkManager editor, for 802.1X / VPN")]
        for i, b in enumerate(btns):
            g.attach(appear(b, 0.35 + i * 0.05), i % 2, i // 2, 1, 1)
        right.pack_start(g, False, False, 0)
        right.pack_start(margins(lbl(f"Device  {self.dev or '—'}   ·   prefs  {PREFS_FILE.replace(os.path.expanduser('~'), '~')}",
                                     "tiny", 0.5), 4, 0, 0, 0), False, False, 0)
        page.pack_start(right, True, True, 0)
        return page

    def manual_attune(self):
        ssid = self.mn_ssid.get_text().strip()
        if not ssid:
            shake(self.mn_ssid)
            self.toast("Name the ley line first", "err")
            return
        pw = self.mn_pw.get_text()
        sec = self.mn_sec
        if sec == "Open":
            pw = ""
        else:
            min_len = 5 if sec == "WEP" else 8
            if len(pw) < min_len:
                shake(self.mn_pw)
                self.toast(f"Seal too short — needs {min_len}+ characters", "err")
                return
        if self.connecting:
            self.toast(f"Already attuning to {self.connecting}…", "busy", sticky=True)
            return
        prof = None
        for p in self.profiles:
            if p["ssid"] == ssid and p.get("mode") != "ap":
                prof = p["name"]
                break
        self.connect_net(ssid, pw or None, sec="" if sec == "Open" else sec, hidden=self.mn_hidden.get_active(), profile=prof)

    def set_pref(self, k, v):
        PREFS[k] = v
        save_prefs(PREFS)
        if k == "anim":
            M.set_enabled(v)
            self.setup_motes()
        elif k == "motes":
            self.setup_motes()
        elif k == "fps":
            M.fps = int(v)
            M._sched()
        self.toast("Pact updated", "ok", ms=1400)

    def save_offsets(self):
        try:
            PREFS["top"] = int(self.off_top.get_text().strip())
            PREFS["right"] = int(self.off_right.get_text().strip())
        except ValueError:
            shake(self.off_top)
            self.toast("Offsets must be whole numbers", "err")
            return
        save_prefs(PREFS)
        self.toast("Popup offset saved", "ok", ms=1400)

    def clear_cache(self):
        self.cache.clear()
        self.reload(rescan=False)
        self.toast("Faint ley lines forgotten", "ok")

    def restart_networking(self):
        self.toast("Re-weaving the ley network…", "busy", sticky=True)
        self.busy += 1

        def work():
            run_cmd(["nmcli", "networking", "off"], 15)
            time.sleep(1.0)
            return run_cmd(["nmcli", "networking", "on"], 15)

        def done(r):
            self.busy -= 1
            ok = bool(r and r[1] == 0)
            self.toast("Ley network restored" if ok else "Restart failed (polkit?)", "ok" if ok else "err")
            if self._finish_if_pending():
                return
            self.reload(rescan=True, delay=3.0, quiet=True)
        self.bg(work, done)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  ACTIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _finish_if_pending(self):
        if self.quit_pending and self.busy <= 0:
            self.alive = False
            Gtk.main_quit()
            return True
        return False

    def connect_net(self, ssid, pw=None, sec="", hidden=False, profile=None):
        if self.connecting:
            self.toast(f"Already attuning to {self.connecting}…", "busy", sticky=True)
            return
        self.connecting = ssid
        self.busy += 1
        self.toast(f"Attuning to {ssid} …", "busy", sticky=True)
        self.refresh()
        dev = self.dev

        def work():
            return nm_connect(dev, ssid, pw, sec, hidden, profile)

        def done(r):
            self.busy -= 1
            self.connecting = None
            ok, msg, need_pw = r if r else (False, "worker error", False)
            short = (msg or "").replace("Error: ", "").strip()[-120:]
            if ok:
                self.toast(f"Ley line attuned  ·  {ssid}", "ok")
                notify("✦ Ley line attuned", ssid)
            else:
                self.toast(f"Attunement failed  ·  {short or ssid}", "err", ms=4200)
                notify("✕ Attunement failed", f"{ssid}\n{short}")
            if self._finish_if_pending():
                return
            if not ok and need_pw and not self.quit_pending:
                fake = {"ssid": ssid, "security": sec or "WPA2", "profile": profile}
                if self.mode == "mini":
                    self.open_pw(fake, reason="Seal rejected")
                else:
                    self.sel_ssid = ssid
            self.reload(delay=0.3)
        self.bg(work, done)

    def sever(self):
        if not self.dev:
            return
        name = self.info.get("ssid", "")
        self.toast(f"Severing {name} …", "busy", sticky=True)
        self.bg(lambda: run_cmd(["nmcli", "device", "disconnect", self.dev]),
                lambda r: (self.toast(f"Ley line severed  ·  {name}", "info"), self.reload(delay=0.4)))

    def forget(self, prof):
        self.bg(lambda: run_cmd(["nmcli", "connection", "delete", "id", prof]),
                lambda r: (self.toast(f"Forgotten  ·  {prof}", "info"), self.reload()))

    def on_radio(self, sw, _pspec):
        if getattr(self, "_sw_lock", False):
            return
        on = sw.get_active()
        if on == self.radio:
            return
        self.radio = on
        self.toast("Unsealing the Wi-Fi radio…" if on else "Sealing the Wi-Fi radio…", "busy", sticky=True)
        self.bg(lambda: run_cmd(["nmcli", "radio", "wifi", "on" if on else "off"]),
                lambda r: (self.toast("Wi-Fi radio unsealed ✦" if on else "Wi-Fi radio sealed", "ok"),
                           self.reload(rescan=on, delay=2.5 if on else 0.3, quiet=False)))

    def on_dns(self, name, ips):
        info = self.info
        if not info["connected"] or not info["conn"]:
            self.toast("Connect to a ley line first", "err")
            return
        conn = info["conn"]
        lst = ",".join(ips.split())
        self.busy += 1

        def work():
            if ips:
                run_cmd(["nmcli", "connection", "modify", "id", conn, "ipv4.ignore-auto-dns", "yes", "ipv4.dns", lst])
            else:
                run_cmd(["nmcli", "connection", "modify", "id", conn, "ipv4.ignore-auto-dns", "no", "ipv4.dns", ""])
            return run_cmd(["nmcli", "connection", "up", "id", conn], timeout=30)

        def done(r):
            self.busy -= 1
            ok = bool(r and r[1] == 0)
            self.toast(f"Elemental DNS  ·  {name}" if ok else "DNS change failed", "ok" if ok else "err")
            if self._finish_if_pending():
                return
            self.reload()
        self.toast(f"Resonating  ·  {name} …", "busy", sticky=True)
        self.bg(work, done)

    def on_hotspot(self):
        ssid = self.hs_ssid.get_text().strip() or "Celestia-AP"
        pw = self.hs_pw.get_text()
        if len(pw) < 8:
            shake(self.hs_pw)
            self.toast("WPA2 seal needs 8+ characters", "err")
            return
        dev = self.dev
        self.toast("Activating waypoint…", "busy", sticky=True)

        def work():
            run_cmd(["nmcli", "connection", "delete", "id", "Genshin-Hotspot"])
            run_cmd(["nmcli", "connection", "add", "type", "wifi", "ifname", dev, "con-name", "Genshin-Hotspot",
                     "autoconnect", "no", "ssid", ssid, "--", "802-11-wireless.mode", "ap", "802-11-wireless.band", "bg",
                     "802-11-wireless-security.key-mgmt", "wpa-psk", "802-11-wireless-security.psk", pw,
                     "ipv4.method", "shared", "ipv6.method", "disabled"])
            return run_cmd(["nmcli", "connection", "up", "id", "Genshin-Hotspot"], timeout=30)
        self.bg(work, lambda r: (self.toast("Waypoint activated  ·  " + ssid if r and r[1] == 0 else "Waypoint failed",
                                            "ok" if r and r[1] == 0 else "err"), self.reload(delay=1.0)))

    def stop_hotspot(self):
        self.bg(lambda: run_cmd(["nmcli", "connection", "down", "id", "Genshin-Hotspot"]),
                lambda r: (self.toast("Waypoint deactivated", "info"), self.reload(delay=1.0)))

    def on_qr(self):
        info = self.info
        if not info["connected"]:
            self.toast("Connect to a ley line first", "err")
            return
        if not shutil.which("qrencode"):
            self.toast("qrencode missing  ·  sudo pacman -S qrencode", "err")
            return
        pw, _ = run_cmd(["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", "id", info["conn"]])
        sec = "WPA" if pw else "nopass"

        def qesc(s):
            return re.sub(r'([\\;,:"])', r"\\\1", s)
        payload = f"WIFI:T:{sec};S:{qesc(info['ssid'])};P:{qesc(pw)};;"
        out = f"/tmp/genshin-qr-{os.getuid()}.png"
        run_cmd(["qrencode", "-s", "9", "-m", "2", "--foreground=3B4354", "--background=ECE5D8", "-o", out, payload])
        if os.path.exists(out):
            self.spawn(["xdg-open", out])

    # ── live updates ──
    def tick(self):
        if not self.alive:
            return False
        if self.quit_pending:
            return True
        rk, tk = self._speed()
        self.rx_hist = (self.rx_hist + [rk])[-62:]
        self.tx_hist = (self.tx_hist + [tk])[-62:]
        self.sample_t = M.now()
        self.tick_n += 1
        if self.h_rx is not None:
            try:
                self.h_rx.set_text(fmt_speed(rk))
                self.h_tx.set_text(fmt_speed(tk))
            except Exception:
                self.h_rx = self.h_tx = None
        if self.tick_n % 4 == 0 and not self._info_busy and not self._reloading:
            self._info_busy = True
            self.bg(lambda: get_active_info(self.dev), self._got_info)
        if (PREFS["autoscan"] and self.tick_n % 30 == 0 and self.radio and not self._reloading
                and not self.connecting and not self.user_busy()):
            self.reload(rescan=True, quiet=True)
        return True

    def _got_info(self, info):
        self._info_busy = False
        if not info or not self.alive:
            return
        prev = self.info
        self.info = info
        self.tween_signal()
        if (prev["connected"], prev["ssid"], prev["ip"]) != (info["connected"], info["ssid"], info["ip"]):
            if not self.connecting:
                self.reload()
            return
        if self.mode == "mini":
            if hasattr(self, "slot_hero"):
                self.fill_hero()
        else:
            self.update_status()
            self.update_overview_vals()


def main():
    global HAS_LAYER
    tab = None
    if "--settings" in sys.argv:
        mode, tab = "akasha", "settings"
    elif any(a in sys.argv for a in ("--akasha", "--advanced")):
        mode = "akasha"
    else:
        mode = "mini"
    for a in sys.argv:
        if a.startswith("--tab="):
            mode, tab = "akasha", a.split("=", 1)[1]
    try:
        with open(PID_FILE) as f:
            parts = f.read().split()
        old = int(parts[0])
        old_mode = parts[1] if len(parts) > 1 else "mini"
        alive = False
        try:
            with open(f"/proc/{old}/cmdline", "rb") as f:
                alive = b"genshin-wifi" in f.read()
        except Exception:
            pass
        if alive and old != os.getpid():
            os.kill(old, signal.SIGTERM)
            if old_mode == mode and tab is None:
                sys.exit(0)
            time.sleep(0.15)
    except (FileNotFoundError, ValueError, IndexError, ProcessLookupError, PermissionError):
        pass
    with open(PID_FILE, "w") as f:
        f.write(f"{os.getpid()} {mode}")
    kick_scan()

    if HAS_LAYER and hasattr(GtkLayerShell, "is_supported"):
        try:
            HAS_LAYER = bool(GtkLayerShell.is_supported())
        except Exception:
            pass

    gc.set_threshold(900, 15, 15)
    prov = Gtk.CssProvider()
    prov.connect("parsing-error", lambda p, sec, err: print("CSS:", err.message, file=sys.stderr))
    try:
        prov.load_from_data(CSS)
    except GLib.Error as e:
        print("CSS warning:", e, file=sys.stderr)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    st = Gtk.Settings.get_default()
    if st is not None and not PREFS["anim"]:
        try:
            st.set_property("gtk-enable-animations", False)
        except Exception:
            pass

    for sig in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda *_: (Gtk.main_quit(), False)[1])
    try:
        Celestia(mode, tab)
        later_trim(2500)
        Gtk.main()
    finally:
        try:
            with open(PID_FILE) as f:
                if f.read().split()[0] == str(os.getpid()):
                    os.remove(PID_FILE)
        except Exception:
            pass


if __name__ == "__main__":
    main()
