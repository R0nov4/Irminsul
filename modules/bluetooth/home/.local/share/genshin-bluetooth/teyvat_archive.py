#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
 ✦ Teyvat Archive ✦  —  Genshin-styled, D-Bus-native Bluetooth manager
 =====================================================================
 GTK3 + PyGObject + BlueZ (org.bluez, system bus) + obexd (session bus) + PipeWire/Pulse (pactl).
 Everything is LIVE: ObjectManager + PropertiesChanged signals and `pactl subscribe` — no polling.

   ✦ Companions           device cards + character-sheet detail panel (+ Form picker)
   ◎ Ley Line Atlas       live RSSI radar
   ♫ Echoing Conch        Bluetooth audio centre: who sings now, per-companion volume & mute,
                          voice (card profile) picker, "sing here" routing, test chime,
                          harmony rules (audio follows the companion, pause when it fades,
                          restore the volume you chose)
   ✉ Transmission         OBEX file push (drag & drop) + accept incoming files
   ⚚ Statue of the Seven  diagnostics: service, rfkill, adapter, driver, battery,
                          obex, audio, broken pairings, logs, full report
   ⚙ Archive Settings

 CLI:  teyvat-archive [--page companions|atlas|echoes|transmission|statue|settings]
                      [--device MAC] [--pair MAC] [--scan] [--background]
 Keys: Ctrl+F search · F5 Elemental Sight · Ctrl+1..6 pages · Ctrl+Q quit · Esc skips the Wish

 1.2.1 — the constellation wheel in the background turns again (it had been frozen by the speed work).
   Its two rotating layers are baked once as sprites and re-blitted at ~15 fps inside their own box only,
   so it is nearly free. Settings → "Turning star wheel" switches it off; Reduce motion also stops it.

 1.2.0 — ❖ Elemental Reactions is gone. It was a rule editor nobody wanted to fill in; the
   three things people actually used it for are now one switch each on the new
   ♫ Echoing Conch page, next to real audio controls.
   Speed: the whole UI was slow because every twinkling star (and every animated icon)
   forced GTK to repaint the cards, glows and blurred shadows lying on top of it.
     · the night sky is baked once and painted straight onto the root box (no extra layer);
       twinkling is optional (Settings) and off by default
     · blurred CSS box-shadows (the most expensive thing GTK3 draws) and CSS transitions removed
     · page / panel cross-fades removed — pages switch instantly
     · the Wish cinematic no longer repaints the entire window underneath itself: it freezes a
       snapshot of the window and plays on its own opaque layer, it is twice as short
       (2.6 s) and a click / Esc skips it
     · Ley Line diamonds are a still picture again (they were animating on every card)
"""
import os, sys, re, json, math, time, random, hashlib, shutil, copy

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, Gio, GLib, GObject, Pango, PangoCairo
import cairo

APP_ID = "org.teyvat.BluetoothArchive"
VERSION = "1.2.1"
T0 = GLib.get_monotonic_time() / 1e6          # same clock domain as the GTK frame clock
FONT = "HYWenHei-85W,HYWenHei,Noto Serif,Noto Sans Symbols 2,Noto Sans Symbols,DejaVu Sans,serif"


def now_t():
    return GLib.get_monotonic_time() / 1e6 - T0


BLUEZ = "org.bluez"
ADAPTER = "org.bluez.Adapter1"
DEVICE = "org.bluez.Device1"
BATTERY = "org.bluez.Battery1"
PROPS = "org.freedesktop.DBus.Properties"
OBEX = "org.bluez.obex"

esc = GLib.markup_escape_text


# ═════════════════════════════════════════════════════════════ config ══
CONF_DIR = os.path.join(GLib.get_user_config_dir(), "genshin-bluetooth")
CONF_FILE = os.path.join(CONF_DIR, "archive.json")
CFG_REV = 4


class Config:
    DEFAULTS = dict(reduce_motion=False, fps=60, particle_density=0.8, battery_alert=20,
                    scan_seconds=30, show_nameless=False, desktop_notify=True,
                    wish_animation=True, accept_incoming=False, incoming_mode="ask",
                    auto_trust=True, smooth_ui=True, animated_stars=False, animated_wheel=True, vigil=False,
                    audio_follow=False, pause_on_fade=False, remember_volume=True,
                    volumes={}, kind_overrides={}, cfg_rev=CFG_REV)

    def __init__(self):
        self.__dict__["data"] = copy.deepcopy(self.DEFAULTS)
        stored = {}
        try:
            with open(CONF_FILE) as f:
                stored = json.load(f)
        except Exception:
            pass
        if not isinstance(stored, dict):
            stored = {}
        self.data.update(stored)
        for k in ("kind_overrides", "volumes"):
            if not isinstance(self.data.get(k), dict):
                self.data[k] = {}
        rev = int(stored.get("cfg_rev", 0) or 0)
        if rev < 3:
            self.data["fps"] = max(int(self.data.get("fps", 60) or 60), 60)
        if rev < 4:
            self.data.pop("reactions", None)          # 1.1 automations are gone
            self.data["animated_stars"] = False       # the cheap, still sky is the new default
        self.data["cfg_rev"] = CFG_REV

    def __getattr__(self, k):
        try:
            return self.__dict__["data"][k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):          # debounced
        if self.__dict__.get("_timer"):
            return
        self.__dict__["_timer"] = GLib.timeout_add(250, self._write)

    def _write(self):
        self.__dict__["_timer"] = 0
        self.flush()
        return False

    def flush(self):
        try:
            os.makedirs(CONF_DIR, exist_ok=True)
            with open(CONF_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print("config save failed:", e, file=sys.stderr)


CONFIG = Config()
import atexit
atexit.register(CONFIG.flush)


# ═══ DRAW-BEGIN ═════════════════════════════════ palette + cairo art ══
def hx(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


GOLD, CREAM, NAVY = hx("#D3BC8E"), hx("#ECE5D8"), hx("#3B4255")
DEEP, DIM, INK = hx("#1B1F2E"), hx("#8E95A8"), hx("#2B3047")
ELEMENTS = {
    "Anemo": hx("#5CD8B8"), "Geo": hx("#F2B723"), "Electro": hx("#B98CFF"),
    "Dendro": hx("#A5C83B"), "Hydro": hx("#4CC2F1"), "Pyro": hx("#EF7A35"),
    "Cryo": hx("#9FD6E3"),
}
ELEM_LIST = list(ELEMENTS.values())
RARITY = {5: hx("#FFB13F"), 4: hx("#B48BFF"), 3: hx("#6FA8FF")}
KINDS = {  # kind: (label, element, rarity)
    "headphones": ("Headphones", "Hydro", 5),
    "earbuds": ("Earbuds", "Hydro", 5),
    "headset": ("Headset", "Hydro", 4),
    "speaker": ("Speaker", "Pyro", 5),
    "soundbar": ("Soundbar", "Pyro", 5),
    "tv": ("Television", "Electro", 5),
    "car": ("Car Audio", "Geo", 5),
    "microphone": ("Microphone", "Hydro", 4),
    "mouse": ("Mouse", "Anemo", 4),
    "keyboard": ("Keyboard", "Geo", 4),
    "gamepad": ("Controller", "Pyro", 5),
    "console": ("Game Console", "Electro", 5),
    "vr": ("VR Headset", "Electro", 5),
    "phone": ("Phone", "Electro", 4),
    "computer": ("Computer", "Cryo", 4),
    "watch": ("Wearable", "Dendro", 4),
    "tablet": ("Tablet", "Cryo", 4),
    "camera": ("Camera", "Cryo", 4),
    "printer": ("Printer", "Geo", 3),
    "remote": ("Remote", "Anemo", 3),
    "pen": ("Stylus", "Dendro", 3),
    "health": ("Health Sensor", "Dendro", 4),
    "tag": ("Tracker Tag", "Anemo", 3),
    "light": ("Smart Light", "Geo", 3),
    "generic": ("Unknown Wanderer", "Anemo", 3),
}
KIND_ORDER = ["headphones", "earbuds", "headset", "speaker", "soundbar", "tv", "car", "microphone",
              "phone", "tablet", "computer", "watch", "health", "keyboard", "mouse", "gamepad", "console",
              "vr", "remote", "pen", "camera", "printer", "light", "tag", "generic"]
AUDIO_KINDS = ("headphones", "earbuds", "headset", "speaker", "soundbar", "tv", "car", "microphone")
AUDIO_UUIDS = ("110b", "1108", "111e", "110d", "184e", "1850")


def src(cr, c, a=1.0):
    cr.set_source_rgba(c[0], c[1], c[2], a)


def mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def rrect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def glow(cr, col, width, alpha=1.0, fill=False, fill_alpha=0.18):
    """Stroke the current path with a soft elemental glow (path consumed)."""
    if fill:
        src(cr, col, fill_alpha * alpha)
        cr.fill_preserve()
    for w, a in ((width * 3.2, .07), (width * 2.0, .14)):
        cr.set_line_width(w)
        src(cr, col, a * alpha)
        cr.stroke_preserve()
    cr.set_line_width(width)
    src(cr, col, alpha)
    cr.stroke()


def star4(cr, x, y, r, inner=0.28):
    """Genshin's four-pointed sparkle."""
    for i in range(8):
        ang = i * math.pi / 4 - math.pi / 2
        rr = r if i % 2 == 0 else r * inner
        px, py = x + math.cos(ang) * rr, y + math.sin(ang) * rr
        if i == 0:
            cr.move_to(px, py)
        else:
            cr.line_to(px, py)
    cr.close_path()


def star5(cr, x, y, r):
    """Rarity star ★."""
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * .45
        px, py = x + math.cos(a) * rr, y + math.sin(a) * rr
        if i == 0:
            cr.move_to(px, py)
        else:
            cr.line_to(px, py)
    cr.close_path()


# ── pre-rendered layers: static art is drawn ONCE, then only blitted / rotated ──
def dscale(cr):
    """HiDPI scale of the surface we are drawing to (1 or 2 usually)."""
    try:
        s = cr.get_target().get_device_scale()[0]
        return max(1.0, min(4.0, float(s)))
    except Exception:
        return 1.0


def make_surface(side, sc, painter, centered=True):
    n = max(1, int(math.ceil(side * sc)))
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
    try:
        surf.set_device_scale(sc, sc)
    except Exception:
        pass
    c = cairo.Context(surf)
    if centered:
        c.translate(side / 2.0, side / 2.0)
    painter(c)
    surf.flush()
    return surf


_LAYERS = {}


def layer(key, side, sc, painter):
    k = (key, round(side, 1), sc)
    s = _LAYERS.get(k)
    if s is None:
        if len(_LAYERS) > 400:
            _LAYERS.clear()
        s = _LAYERS[k] = make_surface(side, sc, painter)
    return s


def blit(cr, surf, side, ang=0.0, alpha=1.0):
    """Paint a centered layer at the current origin, optionally rotated."""
    cr.save()
    if ang:
        cr.rotate(ang)
    cr.set_source_surface(surf, -side / 2.0, -side / 2.0)
    if alpha >= .999:
        cr.paint()
    else:
        cr.paint_with_alpha(max(0.0, alpha))
    cr.restore()


# ── animated device glyphs, drawn in a -50..50 box ─────────────────────
def _notes(cr, t, col):
    for i in range(2):
        ph = (t * 0.5 + i * 0.5) % 1
        x = (-1 if i else 1) * (12 + math.sin(ph * 6.28) * 5)
        y = -8 - ph * 40
        src(cr, col, math.sin(ph * math.pi))
        cr.new_sub_path()
        cr.arc(x, y, 3.2, 0, 2 * math.pi)
        cr.fill()
        cr.set_line_width(1.8)
        cr.move_to(x + 3, y)
        cr.line_to(x + 3, y - 11)
        cr.line_to(x + 8, y - 8)
        cr.stroke()


def _headphones(cr, t, col, active, mic=False):
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.new_sub_path()
    cr.arc(0, 6, 30, math.pi, 2 * math.pi)
    glow(cr, col, 5)
    for sx in (-1, 1):
        rrect(cr, sx * 31 - 7, 0, 14, 28, 6)
        glow(cr, col, 3, fill=True, fill_alpha=.55)
        rrect(cr, sx * 31 - 3, 6, 6, 16, 3)
        src(cr, CREAM, .55 if active else .25)
        cr.fill()
    if mic:
        cr.move_to(-31, 24)
        cr.curve_to(-30, 38, -18, 42, -6, 40)
        glow(cr, col, 3)
        cr.new_sub_path()
        cr.arc(-5, 40, 3.4, 0, 2 * math.pi)
        src(cr, CREAM, .9)
        cr.fill()
    if active:
        for i in range(3):
            ph = (t * 0.9 + i / 3) % 1
            r = 8 + ph * 18
            for sx in (-1, 1):
                cr.new_sub_path()
                if sx < 0:
                    cr.arc(-38, 14, r, math.pi * 0.72, math.pi * 1.28)
                else:
                    cr.arc(38, 14, r, -math.pi * 0.28, math.pi * 0.28)
                cr.set_line_width(2.4)
                src(cr, col, (1 - ph) * .85)
                cr.stroke()
        _notes(cr, t, col)


def _headset(cr, t, col, active):
    _headphones(cr, t, col, active, mic=True)


def _earbuds(cr, t, col, active):
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for i, sx in enumerate((-1, 1)):
        bob = math.sin(t * 2.4 + i * 1.6) * 3 if active else 0
        x, y = sx * 16, -10 + bob
        rrect(cr, x - sx * 3 - 3.5, y + 6, 7, 26, 3.5)
        glow(cr, col, 2.5, fill=True, fill_alpha=.6)
        cr.new_sub_path()
        cr.arc(x, y, 12, 0, 2 * math.pi)
        glow(cr, col, 3, fill=True, fill_alpha=.5)
        cr.new_sub_path()
        cr.arc(x - sx * 2, y - 1, 4.5, 0, 2 * math.pi)
        src(cr, CREAM, .85 if active else .4)
        cr.fill()
    if active:
        for i in range(3):
            ph = (t * 0.8 + i / 3) % 1
            cr.new_sub_path()
            cr.arc(0, -10, 6 + ph * 32, math.pi * 1.25, math.pi * 1.75)
            cr.set_line_width(2.2)
            src(cr, col, (1 - ph) * .8)
            cr.stroke()


def _speaker(cr, t, col, active):
    rrect(cr, -24, -38, 48, 76, 9)
    glow(cr, col, 3, fill=True, fill_alpha=.2)
    pulse = 1 + (0.1 * max(0, math.sin(t * 9)) if active else 0)
    cr.new_sub_path()
    cr.arc(0, 12, 15 * pulse, 0, 2 * math.pi)
    glow(cr, col, 3, fill=True, fill_alpha=.35)
    cr.new_sub_path()
    cr.arc(0, 12, 5 * pulse, 0, 2 * math.pi)
    src(cr, CREAM, .85)
    cr.fill()
    cr.new_sub_path()
    cr.arc(0, -20, 7, 0, 2 * math.pi)
    glow(cr, col, 2.4)
    cr.new_sub_path()
    cr.arc(0, -20, 2.4, 0, 2 * math.pi)
    src(cr, col)
    cr.fill()
    if active:
        for i in range(3):
            ph = (t * 0.9 + i / 3) % 1
            for sx in (-1, 1):
                cr.new_sub_path()
                if sx < 0:
                    cr.arc(-20, 12, 14 + ph * 20, math.pi * 0.7, math.pi * 1.3)
                else:
                    cr.arc(20, 12, 14 + ph * 20, -math.pi * 0.3, math.pi * 0.3)
                cr.set_line_width(2.2)
                src(cr, col, (1 - ph) * .75)
                cr.stroke()


def _mouse(cr, t, col, active):
    cr.save()
    if active:
        cr.translate(math.sin(t * 1.6) * 4, 0)
        cr.rotate(math.sin(t * 1.6) * 0.12)
    rrect(cr, -19, -32, 38, 64, 19)
    glow(cr, col, 3, fill=True, fill_alpha=.22)
    if active and (t % 2.2) < 0.2:          # left click flash
        cr.move_to(0, -31.5)
        cr.line_to(0, -8)
        cr.curve_to(-8, -5, -14, -6, -18.5, -8)
        cr.curve_to(-18.5, -26, -10, -31.5, 0, -31.5)
        cr.close_path()
        src(cr, col, .75)
        cr.fill()
    cr.move_to(0, -32)
    cr.line_to(0, -8)
    cr.move_to(-18, -8)
    cr.curve_to(-8, -4, 8, -4, 18, -8)
    cr.set_line_width(2)
    src(cr, col, .8)
    cr.stroke()
    rrect(cr, -3.4, -27, 6.8, 14, 3.4)
    src(cr, CREAM, .9)
    cr.fill()
    if active:                               # scrolling wheel ridges
        cr.save()
        rrect(cr, -3.4, -27, 6.8, 14, 3.4)
        cr.clip()
        off = (t * 18) % 4
        for k in range(5):
            y = -28 + off + k * 4
            cr.move_to(-3.4, y)
            cr.line_to(3.4, y)
        cr.set_line_width(1.2)
        src(cr, NAVY, .75)
        cr.stroke()
        cr.restore()
    cr.restore()


def _keyboard(cr, t, col, active):
    rrect(cr, -46, -24, 92, 46, 7)
    glow(cr, col, 3, fill=True, fill_alpha=.18)
    keys, kw, step = [], 6.4, 8.4
    for r in range(3):
        for c in range(10 - (r == 2)):
            keys.append((-42 + r * 2.4 + c * step, -19 + r * step, kw, kw))
    keys.append((-22, -19 + 3 * step, 44, kw))
    lit = set()
    if active:
        s = int(t * 7)
        for j in range(3):
            lit.add((s * 7 + j * 13 + (s // 3) * 5) % len(keys))
    for i, (x, y, w, h) in enumerate(keys):
        if i in lit:
            continue
        rrect(cr, x, y, w, h, 1.8)
    cr.set_line_width(1.2)
    src(cr, col, .55)
    cr.stroke()
    for i in lit:
        x, y, w, h = keys[i]
        rrect(cr, x, y, w, h, 1.8)
        glow(cr, col, 1.3, fill=True, fill_alpha=.95)


def _gamepad(cr, t, col, active):
    cr.move_to(-20, -18)
    cr.line_to(20, -18)
    cr.curve_to(34, -18, 42, -8, 44, 8)
    cr.curve_to(46, 22, 40, 30, 32, 28)
    cr.curve_to(26, 27, 22, 18, 14, 14)
    cr.line_to(-14, 14)
    cr.curve_to(-22, 18, -26, 27, -32, 28)
    cr.curve_to(-40, 30, -46, 22, -44, 8)
    cr.curve_to(-42, -8, -34, -18, -20, -18)
    cr.close_path()
    glow(cr, col, 3, fill=True, fill_alpha=.22)
    src(cr, CREAM, .85)
    cr.rectangle(-30, -4.25, 14, 4.5)
    cr.rectangle(-25.25, -9, 4.5, 14)
    cr.fill()
    hot = int(t * 3) % 4 if active else -1
    for k, (dx, dy) in enumerate(((0, -6), (6, 0), (0, 6), (-6, 0))):
        cr.new_sub_path()
        cr.arc(24 + dx, -2 + dy, 3.2, 0, 2 * math.pi)
        if k == hot:
            glow(cr, col, 1.5, fill=True, fill_alpha=1)
        else:
            src(cr, col, .7)
            cr.fill()
    for sx in (-1, 1):
        ox = math.cos(t * 2 + sx) * 2.2 if active else 0
        oy = math.sin(t * 2 + sx) * 2.2 if active else 0
        cr.new_sub_path()
        cr.arc(sx * 10, 7, 5.5, 0, 2 * math.pi)
        src(cr, col, .35)
        cr.fill()
        cr.new_sub_path()
        cr.arc(sx * 10 + ox, 7 + oy, 3.6, 0, 2 * math.pi)
        src(cr, CREAM, .9)
        cr.fill()


def _phone(cr, t, col, active):
    rrect(cr, -21, -40, 42, 80, 8)
    glow(cr, col, 3, fill=True, fill_alpha=.2)
    rrect(cr, -16, -32, 32, 62, 3)
    src(cr, col, .16 if active else .08)
    cr.fill()
    cr.move_to(-5, -36)
    cr.line_to(5, -36)
    cr.set_line_width(2)
    src(cr, CREAM, .7)
    cr.stroke()
    if active:
        cr.save()
        rrect(cr, -16, -32, 32, 62, 3)
        cr.clip()
        for i in range(3):
            ph = (t * 0.7 + i / 3) % 1
            cr.new_sub_path()
            cr.arc(0, 0, ph * 30, 0, 2 * math.pi)
            cr.set_line_width(1.8)
            src(cr, col, (1 - ph) * .8)
            cr.stroke()
        cr.restore()
    cr.save()
    cr.rotate(t * 0.8 if active else 0)
    star4(cr, 0, 0, 10)
    src(cr, CREAM, .9 if active else .45)
    cr.fill()
    cr.restore()


def _computer(cr, t, col, active):
    rrect(cr, -36, -34, 72, 48, 4)
    glow(cr, col, 3, fill=True, fill_alpha=.18)
    cr.move_to(-46, 20)
    cr.line_to(46, 20)
    cr.line_to(40, 27)
    cr.line_to(-40, 27)
    cr.close_path()
    glow(cr, col, 2.5, fill=True, fill_alpha=.5)
    widths = (40, 26, 48, 18, 34)
    prog = ((t * 0.6) % 1.4) if active else 1.0
    for i, w in enumerate(widths):
        f = max(0.0, min(1.0, prog * len(widths) - i))
        if f <= 0:
            break
        cr.rectangle(-28, -26 + i * 7.4, w * f, 3.2)
        src(cr, col if i % 2 else CREAM, .8)
        cr.fill()


def _watch(cr, t, col, active):
    rrect(cr, -11, -46, 22, 26, 4)
    rrect(cr, -11, 20, 22, 26, 4)
    src(cr, col, .45)
    cr.fill()
    cr.new_sub_path()
    cr.arc(0, 0, 23, 0, 2 * math.pi)
    glow(cr, col, 3.5, fill=True, fill_alpha=.2)
    for k in range(12):
        a = k * math.pi / 6
        r1 = 15 if k % 3 == 0 else 17
        cr.move_to(math.cos(a) * r1, math.sin(a) * r1)
        cr.line_to(math.cos(a) * 20, math.sin(a) * 20)
    cr.set_line_width(1.6)
    src(cr, CREAM, .7)
    cr.stroke()
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    am, ah = t * 1.4 - math.pi / 2, t * 0.12 + 0.6
    cr.move_to(0, 0)
    cr.line_to(math.cos(ah) * 10, math.sin(ah) * 10)
    cr.set_line_width(3)
    src(cr, CREAM, .95)
    cr.stroke()
    cr.move_to(0, 0)
    cr.line_to(math.cos(am) * 16, math.sin(am) * 16)
    cr.set_line_width(2)
    src(cr, col)
    cr.stroke()
    cr.new_sub_path()
    cr.arc(0, 0, 2.6, 0, 2 * math.pi)
    src(cr, GOLD)
    cr.fill()


def _tablet(cr, t, col, active):
    rrect(cr, -32, -40, 64, 80, 6)
    glow(cr, col, 3, fill=True, fill_alpha=.18)
    rrect(cr, -26, -33, 52, 64, 2)
    src(cr, col, .1)
    cr.fill()
    n = int(40 * (((t * 0.35) % 1) if active else 1))
    cr.move_to(-22, 0)
    for i in range(1, n + 1):
        cr.line_to(-22 + i * 44 / 40, math.sin(i / 40 * math.pi * 3) * 12)
    cr.set_line_width(2.2)
    src(cr, CREAM, .85)
    cr.stroke()
    tx, ty = -22 + n * 44 / 40, math.sin(n / 40 * math.pi * 3) * 12
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(tx, ty)
    cr.line_to(tx + 10, ty - 16)
    cr.set_line_width(3.5)
    src(cr, col)
    cr.stroke()


def _generic(cr, t, col, active):
    cr.save()
    cr.rotate(t * 0.6 if active else 0)
    star4(cr, 0, 0, 34, .22)
    glow(cr, col, 2.5, fill=True, fill_alpha=.35)
    cr.rotate(math.pi / 4)
    star4(cr, 0, 0, 20, .3)
    src(cr, CREAM, .6)
    cr.fill()
    cr.restore()


def _tv(cr, t, col, active):
    """Television: a little Teyvat landscape with a drifting sun plays on the screen."""
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(-16, 37)
    cr.line_to(16, 37)
    cr.move_to(0, 26)
    cr.line_to(0, 37)
    cr.set_line_width(3.2)
    src(cr, col, .85)
    cr.stroke()
    rrect(cr, -47, -34, 94, 60, 7)
    glow(cr, col, 3, fill=True, fill_alpha=.16)
    cr.save()
    rrect(cr, -41, -28, 82, 48, 3)
    cr.clip()
    src(cr, col, .14 if active else .06)
    cr.paint()
    sx = (math.sin(t * .45) * 22) if active else -12
    g = cairo.RadialGradient(sx, -10, 0, sx, -10, 24)
    g.add_color_stop_rgba(0, CREAM[0], CREAM[1], CREAM[2], .45 if active else .15)
    g.add_color_stop_rgba(1, CREAM[0], CREAM[1], CREAM[2], 0)
    cr.set_source(g)
    cr.paint()
    cr.new_sub_path()
    cr.arc(sx, -10, 6.5, 0, 2 * math.pi)
    src(cr, CREAM, .9 if active else .45)
    cr.fill()
    sh = t * 16 if active else 0
    for li, (base, amp, alpha) in enumerate(((8, 5, .35), (14, 4, .6))):
        cr.move_to(-42, 22)
        for k in range(18):
            x = -42 + k * 5
            cr.line_to(x, base + math.sin((x + sh * (1 + li)) * .1 + li * 2) * amp)
        cr.line_to(42, 22)
        cr.close_path()
        src(cr, col, alpha)
        cr.fill()
    cr.restore()


def _soundbar(cr, t, col, active):
    if active:
        for i in range(3):
            ph = (t * .8 + i / 3) % 1
            cr.new_sub_path()
            cr.arc(0, 0, 20 + ph * 30, math.pi * 1.2, math.pi * 1.8)
            cr.set_line_width(2.2)
            src(cr, col, (1 - ph) * .75)
            cr.stroke()
    rrect(cr, -48, -9, 96, 22, 8)
    glow(cr, col, 3, fill=True, fill_alpha=.22)
    for k in range(4):
        x = -33 + k * 22
        p = (.5 + .5 * math.sin(t * 8 - k * 1.2)) if active else 0
        cr.new_sub_path()
        cr.arc(x, 2, 5 + p * 1.6, 0, 2 * math.pi)
        src(cr, CREAM if k in (1, 2) else col, .5 + .45 * p)
        cr.fill()
    cr.move_to(-30, 22)
    cr.line_to(30, 22)
    cr.set_line_width(1.6)
    src(cr, col, .35)
    cr.stroke()


def _car(cr, t, col, active):
    cr.save()
    if active:
        cr.translate(0, math.sin(t * 10) * .8)
    cr.move_to(-46, 14)
    cr.line_to(-46, 2)
    cr.curve_to(-46, -4, -40, -6, -34, -7)
    cr.line_to(-22, -22)
    cr.curve_to(-19, -25, -16, -26, -12, -26)
    cr.line_to(14, -26)
    cr.curve_to(19, -26, 22, -24, 25, -21)
    cr.line_to(35, -8)
    cr.curve_to(42, -7, 46, -4, 46, 2)
    cr.line_to(46, 14)
    cr.close_path()
    glow(cr, col, 3, fill=True, fill_alpha=.2)
    cr.move_to(-28, -9)
    cr.line_to(-19, -20)
    cr.line_to(-3, -20)
    cr.line_to(-3, -9)
    cr.close_path()
    cr.move_to(3, -9)
    cr.line_to(3, -20)
    cr.line_to(16, -20)
    cr.line_to(26, -9)
    cr.close_path()
    src(cr, CREAM, .35 if active else .16)
    cr.fill()
    rrect(cr, 39, -2, 6, 5, 2)
    src(cr, CREAM if active else DIM, .9)
    cr.fill()
    cr.restore()
    for wx in (-26, 26):
        cr.new_sub_path()
        cr.arc(wx, 15, 10, 0, 2 * math.pi)
        src(cr, DEEP, 1)
        cr.fill_preserve()
        cr.set_line_width(3)
        src(cr, col, .9)
        cr.stroke()
        cr.save()
        cr.translate(wx, 15)
        cr.rotate(t * 6 if active else 0)
        for k in range(3):
            cr.rotate(2 * math.pi / 3)
            cr.move_to(0, 0)
            cr.line_to(0, -6.5)
        cr.set_line_width(2)
        src(cr, CREAM, .8)
        cr.stroke()
        cr.restore()
    if active:
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for k in range(3):
            ph = (t * 1.5 + k / 3) % 1
            x = -50 - ph * 14
            cr.move_to(x, -12 + k * 9)
            cr.line_to(x - 9, -12 + k * 9)
            cr.set_line_width(2)
            src(cr, col, (1 - ph) * .7)
            cr.stroke()


def _console(cr, t, col, active):
    """Handheld console (Switch / Deck style) with a star sprite hopping across the screen."""
    rrect(cr, -48, -24, 96, 48, 14)
    glow(cr, col, 3, fill=True, fill_alpha=.2)
    rrect(cr, -27, -18, 54, 36, 3)
    src(cr, DEEP, .9)
    cr.fill_preserve()
    cr.set_line_width(1.4)
    src(cr, col, .7)
    cr.stroke()
    cr.save()
    rrect(cr, -27, -18, 54, 36, 3)
    cr.clip()
    if active:
        cr.rectangle(-27, 10, 54, 8)
        src(cr, col, .35)
        cr.fill()
        x = -18 + ((t * 20) % 36)
        y = 4 - abs(math.sin(t * 3)) * 14
        star4(cr, x, y, 5, .3)
        src(cr, CREAM, .95)
        cr.fill()
    else:
        star4(cr, 0, 0, 6, .3)
        src(cr, col, .4)
        cr.fill()
    cr.restore()
    cr.new_sub_path()
    cr.arc(-38, -8, 5, 0, 2 * math.pi)
    src(cr, CREAM, .8)
    cr.fill()
    cr.rectangle(-42, 8.5, 8, 3)
    cr.rectangle(-39.5, 6, 3, 8)
    src(cr, col, .8)
    cr.fill()
    hot = int(t * 3) % 4 if active else -1
    for k, (dx, dy) in enumerate(((0, -4.5), (4.5, 0), (0, 4.5), (-4.5, 0))):
        cr.new_sub_path()
        cr.arc(38 + dx, -8 + dy, 2.2, 0, 2 * math.pi)
        src(cr, CREAM if k == hot else col, 1 if k == hot else .75)
        cr.fill()
    cr.new_sub_path()
    cr.arc(38, 10, 4.5, 0, 2 * math.pi)
    src(cr, CREAM, .8)
    cr.fill()


def _printer(cr, t, col, active):
    ph = ((t * .35) % 1) if active else 1.0
    rrect(cr, -26, -40, 52, 22, 2)
    src(cr, CREAM, .45)
    cr.fill()
    L = 8 + ph * 30
    rrect(cr, -26, 0, 52, L + 8, 2)
    src(cr, CREAM, .9)
    cr.fill()
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for k, wid in enumerate((34, 26, 30, 18)):
        y = 14 + k * 7
        if y < 4 + L:
            cr.move_to(-17, y)
            cr.line_to(-17 + wid, y)
    cr.set_line_width(2.2)
    src(cr, col, .8)
    cr.stroke()
    rrect(cr, -44, -24, 88, 32, 7)
    src(cr, DEEP, 1)
    cr.fill()
    rrect(cr, -44, -24, 88, 32, 7)
    glow(cr, col, 3, fill=True, fill_alpha=.28)
    cr.move_to(-30, 2)
    cr.line_to(30, 2)
    cr.set_line_width(2.4)
    src(cr, DEEP, .9)
    cr.stroke()
    blink = (.5 + .5 * math.sin(t * 6)) if active else .3
    cr.new_sub_path()
    cr.arc(32, -12, 3.4, 0, 2 * math.pi)
    src(cr, ELEMENTS["Dendro"] if active else DIM, .4 + .6 * blink)
    cr.fill()


def _camera(cr, t, col, active):
    cr.move_to(-44, -20)
    cr.line_to(-18, -20)
    cr.line_to(-12, -30)
    cr.line_to(12, -30)
    cr.line_to(18, -20)
    cr.line_to(44, -20)
    cr.line_to(44, 30)
    cr.line_to(-44, 30)
    cr.close_path()
    glow(cr, col, 3, fill=True, fill_alpha=.2)
    flash = active and (t % 3.2) < .14
    rrect(cr, 26, -15, 11, 6, 2)
    src(cr, CREAM, 1 if flash else .45)
    cr.fill()
    cr.new_sub_path()
    cr.arc(0, 5, 19, 0, 2 * math.pi)
    src(cr, DEEP, .95)
    cr.fill_preserve()
    glow(cr, col, 3)
    cr.save()
    cr.translate(0, 5)
    cr.rotate(t * .8 if active else .3)
    r = 14 * ((.42 + .22 * math.sin(t * 1.7)) if active else .45)
    for k in range(6):
        a = k * math.pi / 3
        cr.move_to(math.cos(a) * r, math.sin(a) * r)
        cr.line_to(math.cos(a + 1.25) * 15, math.sin(a + 1.25) * 15)
    cr.set_line_width(1.7)
    src(cr, col, .85)
    cr.stroke()
    for k in range(6):
        a = k * math.pi / 3
        if k == 0:
            cr.move_to(math.cos(a) * r, math.sin(a) * r)
        else:
            cr.line_to(math.cos(a) * r, math.sin(a) * r)
    cr.close_path()
    src(cr, CREAM, .3 if active else .15)
    cr.fill()
    cr.restore()
    if flash:
        cr.new_sub_path()
        cr.arc(0, 5, 19, 0, 2 * math.pi)
        src(cr, CREAM, .6)
        cr.fill()


def _vr(cr, t, col, active):
    cr.move_to(-40, -20)
    cr.line_to(40, -20)
    cr.curve_to(46, -20, 48, -16, 48, -10)
    cr.line_to(48, 10)
    cr.curve_to(48, 17, 44, 20, 38, 20)
    cr.line_to(16, 20)
    cr.curve_to(9, 20, 8, 10, 0, 10)
    cr.curve_to(-8, 10, -9, 20, -16, 20)
    cr.line_to(-38, 20)
    cr.curve_to(-44, 20, -48, 17, -48, 10)
    cr.line_to(-48, -10)
    cr.curve_to(-48, -16, -46, -20, -40, -20)
    cr.close_path()
    glow(cr, col, 3, fill=True, fill_alpha=.22)
    for sx in (-1, 1):
        cr.save()
        cr.translate(sx * 22, -2)
        cr.scale(13, 9)
        cr.new_sub_path()
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        src(cr, DEEP, .9)
        cr.fill_preserve()
        cr.set_line_width(2)
        src(cr, col, .9)
        cr.stroke()
        if active:
            star4(cr, sx * 22 + math.sin(t * 1.3 + sx) * 7, -3, 4.5, .3)
            src(cr, CREAM, .9)
            cr.fill()
    if active:
        for i in range(3):
            ph = (t * .35 + i / 3) % 1
            star4(cr, -30 + i * 30 + math.sin(t + i) * 4, -26 - ph * 22, 3 + 2 * (1 - ph), .3)
            src(cr, ELEM_LIST[(i * 2) % 7], math.sin(ph * math.pi))
            cr.fill()


def _microphone(cr, t, col, active):
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.new_sub_path()
    cr.arc(0, -10, 24, 0, math.pi)
    cr.move_to(0, 14)
    cr.line_to(0, 32)
    cr.move_to(-15, 34)
    cr.line_to(15, 34)
    glow(cr, col, 3)
    rrect(cr, -13, -44, 26, 46, 13)
    glow(cr, col, 3, fill=True, fill_alpha=.32)
    for y in (-32, -25, -18, -11):
        cr.move_to(-8, y)
        cr.line_to(8, y)
    cr.set_line_width(1.6)
    src(cr, CREAM, .55)
    cr.stroke()
    if active:
        for sx in (-1, 1):
            for k in range(4):
                hgt = 4 + abs(math.sin(t * 7 + k * 1.3 + sx)) * (18 - k * 3)
                x = sx * (32 + k * 6)
                cr.move_to(x, -20 - hgt / 2)
                cr.line_to(x, -20 + hgt / 2)
        cr.set_line_width(3)
        src(cr, col, .85)
        cr.stroke()


def _remote(cr, t, col, active):
    cr.save()
    cr.rotate(.4)
    if active:
        for i in range(3):
            ph = (t * 1.1 + i / 3) % 1
            cr.new_sub_path()
            cr.arc(0, -44, 6 + ph * 22, math.pi * 1.25, math.pi * 1.75)
            cr.set_line_width(2.2)
            src(cr, col, (1 - ph) * .8)
            cr.stroke()
    rrect(cr, -14, -42, 28, 84, 13)
    glow(cr, col, 3, fill=True, fill_alpha=.2)
    cr.new_sub_path()
    cr.arc(0, -30, 4, 0, 2 * math.pi)
    src(cr, ELEMENTS["Pyro"] if active else col, .9)
    cr.fill()
    cr.new_sub_path()
    cr.arc(0, -11, 9, 0, 2 * math.pi)
    cr.set_line_width(2)
    src(cr, CREAM, .6)
    cr.stroke()
    hot = int(t * 4) % 4 if active else -1
    for k, (dx, dy) in enumerate(((0, -6), (6, 0), (0, 6), (-6, 0))):
        cr.new_sub_path()
        cr.arc(dx, -11 + dy, 1.6, 0, 2 * math.pi)
        src(cr, CREAM, 1 if k == hot else .35)
        cr.fill()
    for rr in range(3):
        for cc in range(3):
            cr.new_sub_path()
            cr.arc(-6 + cc * 6, 8 + rr * 7, 1.9, 0, 2 * math.pi)
    src(cr, col, .7)
    cr.fill()
    cr.restore()


def _pen(cr, t, col, active):
    N = 35
    n = int(N * ((t * .3) % 1)) if active else N
    pts = [(-42 + i * 1.6, 28 + math.sin(i / N * math.pi * 4) * 7) for i in range(n + 1)]
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    if len(pts) > 1:
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.set_line_width(2.4)
        src(cr, col, .8 if active else .4)
        cr.stroke()
    tx, ty = pts[-1]
    cr.save()
    cr.translate(tx, ty)
    cr.rotate(math.pi / 4)
    cr.move_to(0, 0)
    cr.line_to(-5, -12)
    cr.line_to(5, -12)
    cr.close_path()
    src(cr, CREAM, .9)
    cr.fill()
    rrect(cr, -5.5, -62, 11, 50, 4)
    glow(cr, col, 2.6, fill=True, fill_alpha=.35)
    cr.move_to(-5.5, -48)
    cr.line_to(5.5, -48)
    cr.set_line_width(2)
    src(cr, CREAM, .6)
    cr.stroke()
    cr.restore()


def _ecg(u):
    if 26 <= u < 30:
        return -(u - 26) * 5.5
    if 30 <= u < 35:
        return -22 + (u - 30) * 6.4
    if 35 <= u < 39:
        return 10 - (u - 35) * 2.5
    if 50 <= u < 62:
        return -5 * math.sin((u - 50) / 12 * math.pi)
    return 0.0


def _health(cr, t, col, active):
    beat = 1 + (.09 * max(0.0, math.sin(t * 7)) ** 6 if active else 0)
    cr.save()
    cr.translate(0, -2)
    cr.scale(beat, beat)
    cr.move_to(0, 36)
    cr.curve_to(-30, 16, -44, 2, -44, -12)
    cr.curve_to(-44, -28, -32, -38, -20, -38)
    cr.curve_to(-10, -38, -3, -32, 0, -24)
    cr.curve_to(3, -32, 10, -38, 20, -38)
    cr.curve_to(32, -38, 44, -28, 44, -12)
    cr.curve_to(44, 2, 30, 16, 0, 36)
    cr.close_path()
    cr.restore()
    glow(cr, col, 3, fill=True, fill_alpha=.25)
    off = (t * 38) % 80 if active else 12
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for k in range(51):
        x = -40 + k * 1.6
        y = -4 + _ecg((x + 40 + off) % 80)
        if k == 0:
            cr.move_to(x, y)
        else:
            cr.line_to(x, y)
    cr.set_line_width(2.6)
    src(cr, CREAM, .95 if active else .5)
    cr.stroke()


def _tag(cr, t, col, active):
    if active:
        for i in range(3):
            ph = (t * .6 + i / 3) % 1
            cr.new_sub_path()
            cr.arc(0, 6, 22 + ph * 26, 0, 2 * math.pi)
            cr.set_line_width(2)
            src(cr, col, (1 - ph) * .6)
            cr.stroke()
    cr.new_sub_path()
    cr.arc(0, -25, 8, 0, 2 * math.pi)
    cr.set_line_width(3.2)
    src(cr, col, .85)
    cr.stroke()
    cr.new_sub_path()
    cr.arc(0, 6, 24, 0, 2 * math.pi)
    glow(cr, col, 3, fill=True, fill_alpha=.3)
    cr.new_sub_path()
    cr.arc(0, 6, 15, 0, 2 * math.pi)
    src(cr, CREAM, .12)
    cr.fill()
    cr.save()
    cr.translate(0, 6)
    cr.rotate(t * .7 if active else 0)
    star4(cr, 0, 0, 10, .3)
    src(cr, CREAM, .9 if active else .5)
    cr.fill()
    cr.restore()


def _light(cr, t, col, active):
    lum = (.6 + .4 * math.sin(t * 2.2)) if active else 0.0
    if active:
        g = cairo.RadialGradient(0, -12, 0, 0, -12, 46)
        g.add_color_stop_rgba(0, col[0], col[1], col[2], .38 * lum)
        g.add_color_stop_rgba(1, col[0], col[1], col[2], 0)
        cr.set_source(g)
        cr.new_sub_path()
        cr.arc(0, -12, 46, 0, 2 * math.pi)
        cr.fill()
        cr.save()
        cr.translate(0, -12)
        cr.rotate(t * .4)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for k in range(10):
            a = k * 2 * math.pi / 10
            r2 = 37 + 4 * math.sin(t * 3 + k)
            cr.move_to(math.cos(a) * 30, math.sin(a) * 30)
            cr.line_to(math.cos(a) * r2, math.sin(a) * r2)
        cr.set_line_width(2.4)
        src(cr, col, .3 + .5 * lum)
        cr.stroke()
        cr.restore()
    cr.new_sub_path()
    cr.arc(0, -12, 22, math.pi * .7, math.pi * 2.3)
    cr.line_to(9, 18)
    cr.line_to(-9, 18)
    cr.close_path()
    glow(cr, mix(col, CREAM, .5 * lum), 3, fill=True, fill_alpha=.22 + .5 * lum)
    rrect(cr, -10, 20, 20, 5, 2)
    rrect(cr, -8, 27, 16, 5, 2)
    src(cr, col, .8)
    cr.fill()
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.move_to(-6, 8)
    cr.line_to(-3, -6)
    cr.line_to(0, 2)
    cr.line_to(3, -6)
    cr.line_to(6, 8)
    cr.set_line_width(1.8)
    src(cr, CREAM, .4 + .6 * lum)
    cr.stroke()


DEVICE_DRAW = dict(headphones=_headphones, headset=_headset, earbuds=_earbuds,
                   speaker=_speaker, mouse=_mouse, keyboard=_keyboard, gamepad=_gamepad,
                   phone=_phone, computer=_computer, watch=_watch, tablet=_tablet,
                   tv=_tv, soundbar=_soundbar, car=_car, console=_console, printer=_printer,
                   camera=_camera, vr=_vr, microphone=_microphone, remote=_remote, pen=_pen,
                   health=_health, tag=_tag, light=_light, generic=_generic)


def draw_device_emblem(cr, kind, cx, cy, size, t, col, state="connected",
                       battery=None, busy=False, ring=True):
    """Device 'character portrait': halo, ornate ring, energy ring, animated glyph."""
    active = state == "connected"
    if not active:
        col = mix(col, (0.62, 0.64, 0.70), .45 if state == "paired" else .72)
    tt = t if active else 1.3
    sc = dscale(cr)
    s = size / 100.0
    side = size + 4
    cr.save()
    cr.translate(cx, cy)
    g = cairo.RadialGradient(0, 0, 4 * s, 0, 0, 50 * s)
    g.add_color_stop_rgba(0, col[0], col[1], col[2], .40 if active else .14)
    g.add_color_stop_rgba(1, col[0], col[1], col[2], 0)
    cr.new_sub_path()
    cr.arc(0, 0, 50 * s, 0, 2 * math.pi)
    cr.set_source(g)
    cr.fill()
    if ring:
        def ring_painter(c, s=s, active=active):
            c.scale(s, s)
            c.new_sub_path()
            c.arc(0, 0, 43.5, 0, 2 * math.pi)
            c.set_line_width(1.2)
            src(c, GOLD, .6 if active else .35)
            c.stroke()
            for k in range(4):
                c.save()
                c.rotate(k * math.pi / 2)
                star4(c, 0, -43.5, 4.2, .3)
                src(c, GOLD, .95 if active else .5)
                c.fill()
                c.restore()
            c.set_dash([1.5, 5])
            c.new_sub_path()
            c.arc(0, 0, 39.5, 0, 2 * math.pi)
            c.set_line_width(1.2)
            src(c, GOLD, .35)
            c.stroke()
        blit(cr, layer(("dring", active), side, sc, ring_painter), side, t * 0.25 if active else 0)
    if battery is not None:
        lvl = max(0, min(100, battery)) / 100.0
        bc = ELEMENTS["Dendro"] if battery > 50 else (ELEMENTS["Geo"] if battery > 20 else ELEMENTS["Pyro"])
        pulse = (.55 + .45 * math.sin(t * 6)) if battery <= 20 else 1
        segs = 24
        nseg = int(round(segs * lvl))

        def batt_painter(c, s=s, bc=bc, nseg=nseg):
            c.scale(s, s)
            c.new_sub_path()
            c.arc(0, 0, 48, 0, 2 * math.pi)
            c.set_line_width(3.2)
            src(c, bc, .14)
            c.stroke()
            for i in range(nseg):
                a0 = -math.pi / 2 + i * 2 * math.pi / segs + .035
                c.new_sub_path()
                c.arc(0, 0, 48, a0, a0 + 2 * math.pi / segs - .07)
            c.set_line_width(3.2)
            src(c, bc, 1)
            c.stroke()
        blit(cr, layer(("batt", nseg, bc), side, sc, batt_painter), side, 0, pulse)
    cr.scale(s, s)
    if busy:
        cr.save()
        cr.rotate(t * 4)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.new_sub_path()
        cr.arc(0, 0, 47, 0, math.pi * .6)
        cr.set_line_width(3.4)
        src(cr, GOLD, .95)
        cr.stroke()
        cr.new_sub_path()
        cr.arc(0, 0, 47, math.pi, math.pi * 1.6)
        src(cr, CREAM, .6)
        cr.stroke()
        cr.restore()
    cr.scale(.62, .62)
    DEVICE_DRAW.get(kind, _generic)(cr, tt, col, active)
    cr.restore()


def _emblem_ring_painter(R, col):
    def p(c):
        c.new_sub_path()
        c.arc(0, 0, R * .92, 0, 2 * math.pi)
        c.set_line_width(1.6)
        src(c, col, .9)
        c.stroke()
        c.new_sub_path()
        c.arc(0, 0, R * .84, 0, 2 * math.pi)
        c.set_line_width(1)
        src(c, col, .45)
        c.stroke()
        for k in range(36):
            a0 = k * math.pi / 18
            r0 = R * (.84 if k % 3 == 0 else .875)
            c.move_to(math.cos(a0) * r0, math.sin(a0) * r0)
            c.line_to(math.cos(a0) * R * .92, math.sin(a0) * R * .92)
        c.set_line_width(1)
        src(c, col, .6)
        c.stroke()
        for k in range(4):
            c.save()
            c.rotate(k * math.pi / 2)
            star4(c, 0, -R * .92, R * .075, .3)
            src(c, col, 1)
            c.fill()
            c.restore()
    return p


def _hept_points(R):
    return [(math.cos(k * 2 * math.pi / 7 - math.pi / 2) * R * .62,
             math.sin(k * 2 * math.pi / 7 - math.pi / 2) * R * .62) for k in range(7)]


def _emblem_hept_painter(R, col):
    def p(c):
        pts = _hept_points(R)
        for i in range(7):
            c.move_to(*pts[i])
            c.line_to(*pts[(i + 3) % 7])
        c.set_line_width(1.1)
        src(c, col, .55)
        c.stroke()
        c.new_sub_path()
        c.arc(0, 0, R * .62, 0, 2 * math.pi)
        c.set_line_width(.8)
        src(c, col, .35)
        c.stroke()
    return p


def draw_adapter_emblem(cr, cx, cy, R, t, state="on"):
    """The adapter as a rotating Constellation wheel with the seven elements."""
    on = state in ("on", "scan")
    col = GOLD if on else DIM
    sc = dscale(cr)
    side = 2 * R + 4
    cr.save()
    cr.translate(cx, cy)
    if state == "scan":
        for i in range(4):
            ph = (t * 0.55 + i / 4) % 1
            cr.new_sub_path()
            cr.arc(0, 0, R * 0.25 + ph * R * 0.8, 0, 2 * math.pi)
            cr.set_line_width(2.2 * (1 - ph) + 0.4)
            src(cr, ELEMENTS["Anemo"], (1 - ph) * 0.7)
            cr.stroke()
    ci = (t * 0.25) % 7 if on else 0
    core = mix(ELEM_LIST[int(ci) % 7], ELEM_LIST[(int(ci) + 1) % 7], ci - int(ci)) if on else DIM
    g = cairo.RadialGradient(0, 0, 0, 0, 0, R)
    g.add_color_stop_rgba(0, core[0], core[1], core[2], .45 if on else .12)
    g.add_color_stop_rgba(1, core[0], core[1], core[2], 0)
    cr.new_sub_path()
    cr.arc(0, 0, R, 0, 2 * math.pi)
    cr.set_source(g)
    cr.fill()
    blit(cr, layer(("ering", on, round(R, 1)), side, sc, _emblem_ring_painter(R, col)), side,
         t * .18 if on else 0)
    rot = -t * .12 if on else 0
    blit(cr, layer(("ehept", on, round(R, 1)), side, sc, _emblem_hept_painter(R, col)), side, rot)
    cr.save()
    cr.rotate(rot)
    for i, (x, y) in enumerate(_hept_points(R)):
        pulse = (.5 + .5 * math.sin(t * 2 + i)) if on else 0
        if on:
            cr.new_sub_path()
            cr.arc(x, y, R * .13, 0, 2 * math.pi)
            src(cr, ELEM_LIST[i], .2 * pulse)
            cr.fill()
        cr.new_sub_path()
        cr.arc(x, y, R * (.055 + .015 * pulse), 0, 2 * math.pi)
        src(cr, ELEM_LIST[i] if on else DIM, .95)
        cr.fill()
    cr.restore()
    cr.rotate(t * .5 if on else 0)
    star4(cr, 0, 0, R * .3, .22)
    src(cr, CREAM if on else DIM, .95)
    cr.fill()
    cr.rotate(math.pi / 4)
    star4(cr, 0, 0, R * .17, .3)
    src(cr, core, .9)
    cr.fill()
    cr.restore()


def draw_leyline(cr, x, y, w, h, level, col=None):
    """Five diamonds = Ley Line strength (a still picture — no per-frame cost)."""
    col = col or ELEMENTS["Anemo"]
    n, step = 5, w / 5.0
    r = min(h / 2.0, step / 2.4)
    for i in range(n):
        cx, cy = x + step * (i + .5), y + h / 2.0
        cr.move_to(cx, cy - r)
        cr.line_to(cx + r * .75, cy)
        cr.line_to(cx, cy + r)
        cr.line_to(cx - r * .75, cy)
        cr.close_path()
        if i < level:
            src(cr, col, .95 - .06 * i)
            cr.fill_preserve()
            cr.set_line_width(1)
            src(cr, CREAM, .5)
            cr.stroke()
        else:
            cr.set_line_width(1)
            src(cr, DIM, .6)
            cr.stroke()


# ── sidebar navigation icons (vector, drawn in a -12..12 box) ───────────
def draw_nav_icon(cr, key, col):
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)

    def stroke(w=1.9):
        cr.set_line_width(w)
        src(cr, col)
        cr.stroke()

    if key == "companions":
        star4(cr, -1.5, 1.5, 10, .3)
        src(cr, col)
        cr.fill()
        star4(cr, 7.5, -7.5, 3.6, .35)
        cr.fill()
    elif key == "atlas":
        for r in (10.2, 5.6):
            cr.new_sub_path()
            cr.arc(0, 0, r, 0, 2 * math.pi)
        stroke(1.7)
        cr.move_to(0, 0)
        cr.line_to(7.4, -7.0)
        stroke(2.1)
        cr.new_sub_path()
        cr.arc(-4.2, 4.4, 2.0, 0, 2 * math.pi)
        src(cr, col)
        cr.fill()
    elif key == "echoes":                      # conch shell with a sound wave
        cr.move_to(-9.5, 8.5)
        cr.curve_to(-11, -2, -4, -10.5, 4, -9.5)
        cr.curve_to(9.5, -8.5, 10.5, -2, 6.5, 1)
        cr.curve_to(3, 3.5, -1.5, 1.5, -1, -2.5)
        cr.curve_to(-0.5, -5.5, 3.5, -5.5, 4, -3)
        stroke(1.8)
        cr.move_to(-9.5, 8.5)
        cr.line_to(1.5, 6.2)
        cr.curve_to(4, 5.6, 6, 3.8, 6.5, 1)
        stroke(1.8)
        cr.new_sub_path()
        cr.arc(-9.5, 8.5, 6.5, -math.pi * .05, math.pi * .45)
        stroke(1.4)
        cr.new_sub_path()
        cr.arc(-9.5, 8.5, 10.5, -math.pi * .02, math.pi * .4)
        stroke(1.4)
    elif key == "transmission":
        rrect(cr, -10.5, -7.5, 21, 15, 2.6)
        stroke(1.8)
        cr.move_to(-9.5, -6)
        cr.line_to(0, 1.6)
        cr.line_to(9.5, -6)
        stroke(1.8)
    elif key == "statue":
        cr.move_to(0, -11.5)
        cr.line_to(2.6, -8.4)
        cr.line_to(0, -5.3)
        cr.line_to(-2.6, -8.4)
        cr.close_path()
        src(cr, col)
        cr.fill()
        cr.new_sub_path()
        cr.arc(0, -1.6, 2.4, 0, 2 * math.pi)
        src(cr, col)
        cr.fill()
        cr.move_to(-9, -6.5)
        cr.curve_to(-7, -1, -4, 1.6, 0, 1.6)
        cr.curve_to(4, 1.6, 7, -1, 9, -6.5)
        stroke(1.8)
        cr.move_to(-2.6, 2)
        cr.line_to(-4.6, 8.4)
        cr.line_to(4.6, 8.4)
        cr.line_to(2.6, 2)
        stroke(1.7)
        cr.move_to(-8.5, 11.2)
        cr.line_to(8.5, 11.2)
        stroke(2.0)
    elif key == "settings":
        n = 8
        for k in range(n):
            a = k * 2 * math.pi / n
            cr.move_to(math.cos(a) * 6.5, math.sin(a) * 6.5)
            cr.line_to(math.cos(a) * 10.2, math.sin(a) * 10.2)
        stroke(3.4)
        cr.new_sub_path()
        cr.arc(0, 0, 6.8, 0, 2 * math.pi)
        stroke(2.0)
        cr.new_sub_path()
        cr.arc(0, 0, 2.7, 0, 2 * math.pi)
        stroke(1.8)
    else:
        star4(cr, 0, 0, 10, .3)
        src(cr, col)
        cr.fill()
# ═══ DRAW-END ═══════════════════════════════════════════════════════════


def hexs(c):
    return "#%02x%02x%02x" % tuple(int(v * 255) for v in c)


_FONT_CACHE = {}


def _font(size, bold):
    k = (size, bold)
    fd = _FONT_CACHE.get(k)
    if fd is None:
        fd = _FONT_CACHE[k] = Pango.FontDescription.from_string(
            "%s %s%s" % (FONT, "Bold " if bold else "", size))
    return fd


def draw_text(cr, text, x, y, size=12, col=CREAM, alpha=1.0, bold=False, align="center"):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(_font(size, bold))
    layout.set_text(text, -1)
    w, h = layout.get_pixel_size()
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    cr.move_to(x, y - h / 2)
    src(cr, col, alpha)
    PangoCairo.show_layout(cr, layout)
    return w, h


# ═══════════════════════════════════════════════════ device knowledge ══
UUIDS = {
    "1101": "Serial Port", "1103": "Dial-up Networking", "1105": "OBEX Object Push",
    "1106": "OBEX File Transfer", "1108": "Headset (HSP)", "110a": "A2DP Audio Source",
    "110b": "A2DP Audio Sink", "110c": "AVRCP Target", "110d": "Advanced Audio",
    "110e": "AVRCP Controller", "110f": "AVRCP Controller", "1112": "Headset Gateway",
    "1115": "PAN User", "1116": "Network Access Point", "1117": "Group Network",
    "111e": "Hands-Free (HFP)", "111f": "Hands-Free Gateway", "112d": "SIM Access",
    "112f": "Phonebook Access", "1132": "Message Access", "1133": "Message Notification",
    "1124": "Human Interface Device", "1200": "PnP Information", "1203": "Generic Audio",
    "1800": "Generic Access", "1801": "Generic Attribute", "180a": "Device Information",
    "180f": "Battery Service", "1812": "HID over GATT", "1813": "Scan Parameters",
    "1844": "Volume Control", "1845": "Volume Offset", "1846": "Coordinated Set",
    "184e": "Audio Stream Control (LE Audio)", "184f": "Broadcast Audio Scan",
    "1850": "Published Audio Capabilities", "1853": "Common Audio",
    "1854": "Hearing Access", "fe2c": "Google Fast Pair", "fd6f": "Exposure Notification",
}


def uuid_name(u):
    u = u.lower()
    short = u[4:8] if u.endswith("-0000-1000-8000-00805f9b34fb") else None
    if short and short in UUIDS:
        return UUIDS[short], short
    return ("Custom talent", u[:8])


# ── companion forms ─────────────────────────────────────────────────────
# order: strong name hints → Class of Device → BLE Appearance → weak (brand) hints → icon.
# The exact same "kind|regex" strings live in genshin-bluetooth.sh.
NAME_HINTS = [
    "headphones|airpods max",
    "earbuds|airpods|buds|earbud|earphone|earpods| wf [0-9c]| tws |freebuds|pods |elite [0-9]| liberty",
    "remote| remote| rcu? |clicker|presenter|selfie|shutter| spotlight ",
    "pen|stylus|pencil| s ?pen | pen |wacom",
    "gamepad|dualsense|dualshock|controller|gamepad|joy ?con|8bitdo|stadia|xbox wireless|xbox elite",
    "console|steam ?deck|nintendo switch|playstation| ps[345] |rog ally|legion go|xbox (series|one)",
    "vr|oculus|meta quest| quest [0-9p]| vive | pico [0-9]|valve index| vr |xreal|nreal|viture|rokid|vision pro",
    "health|heart ?rate| hrm|polar h[0-9]|tickr|wahoo| scale |thermometer|blood pressure|oximeter|glucose|omron|cadence|speed sensor| oura | whoop ",
    "watch|watch| band |amazfit|garmin|fitbit",
    "tag|airtag| tile |smart ?tag|chipolo|pebblebee| nut |find my",
    "keyboard|keyboard|keychron|mx keys| k[0-9]{3} ",
    "mouse|mouse|mx master|mx anywhere|mx ergo|trackball|trackpad",
    "soundbar|sound ?bar|playbar|sonos (beam|arc|ray)|jbl bar| hw [a-z][0-9]| ht [a-z]| sb[0-9]{2}| yas [0-9]| signa s|magnifi|tv speaker|home ?theat",
    "tv| tv |television|bravia|webos|android ?tv|google ?tv|fire ?tv| roku |chromecast| qled | oled |vidaa| mi ?tv|mitv| mi box|shield tv|smart ?tv|tizen",
    "car| car |car ?kit|car ?audio|car ?multimedia|carplay|android auto|uconnect| my ?car |toyota|honda|nissan|mazda| mzd |hyundai| kia | ford | sync |chevrolet| chevy | bmw | audi |mercedes| mb bluetooth|volkswagen| vw |skoda|peugeot|renault|citroen|tesla|subaru|lexus|volvo| jeep |porsche|kenwood|head ?unit|car stereo| mmi |entune|mylink| dacia | fiat | opel |suzuki|mitsubishi|geely|chery| byd |haval| xav ",
    "microphone| mic |microphone| rode |wireless go|hollyland| lark | boya |shure",
    "camera|camera| cam |gopro| hero ?[0-9]|insta360| dji |osmo| ilce |canon eos| eos |nikon|fujifilm|lumix|ricoh|webcam",
    "printer|printer|deskjet|officejet|laserjet|selphy|pixma|epson|instax|phomemo|niimbot|sprocket|zink|label ?maker",
    "light| bulb|lamp | lamp| light|govee|lifx|yeelight| hue |nanoleaf|led ?strip|elk bledom|triones| qhm |magic ?home",
    "headset|headset|hands ?free|plantronics|jabra (evolve|talk|engage)",
    "headphones|headphone| wh [0-9]| wh ch| mdr | ath |quietcomfort| qc ?[0-9]|momentum|beats (studio|solo|executive|flex|ep)|powerbeats|bose 700|shokz|openrun|soundcore (life|space|q[0-9])|jbl (tune|live|quantum|club)| hd [0-9]{3}| px[0-9]",
    "speaker|speaker|soundlink| boom | flip [0-9]| charge [0-9]| go [0-9]| clip [0-9]| pill| srs |homepod| echo |nest (audio|mini)|soundcore (motion|flare|boom|select)|wonderboom|megaboom|emberton|stanmore|acton|woburn|kilburn|middleton|tufton|willen|beosound|bose home",
    "tablet|ipad|tablet| tab |matepad|mediapad| pad [0-9]|xiaomi pad|redmi pad|kindle|remarkable|boox",
    "computer|laptop|desktop|macbook|imac|mac ?mini|mac ?studio|notebook|thinkpad|ideapad|galaxy book|chromebook|pixelbook|matebook|zenbook|vivobook|surface (pro|book|go|studio|laptop)| pc | linux | ubuntu | arch | archlinux | fedora | manjaro | debian | mint | nixos | windows | cachyos | endeavouros ",
    "phone|iphone|phone|galaxy [asmzn][0-9]|galaxy note| pixel [0-9]|oneplus| poco |redmi note|realme",
]
NAME_HINTS_WEAK = [
    "speaker| jbl |marshall|ultimate ears| ue |tribit| sonos |harman| bose |anker|soundcore|olufsen| b o |edifier",
    "headphones| sony |sennheiser|audio technica|akg|skullcandy|jabra|jlab|baseus| qcy |haylou",
    "phone|xiaomi|huawei| oppo | vivo |motorola| moto |honor|samsung|galaxy|redmi|google",
]


def _compile_hints(rules):
    out = []
    for s in rules:
        kind, rx = s.split("|", 1)
        out.append((kind, re.compile(rx)))
    return out


_HINTS, _HINTS_WEAK = _compile_hints(NAME_HINTS), _compile_hints(NAME_HINTS_WEAK)


def norm_name(s):
    return " " + " ".join(re.findall(r"[a-z0-9]+", (s or "").lower())) + " "


def _hint(rules, n):
    for kind, rx in rules:
        if rx.search(n):
            return kind
    return None


def class_kind(c):
    """Bluetooth Class of Device → form (major / minor device class)."""
    try:
        c = int(c or 0)
    except (TypeError, ValueError):
        return None
    if not c:
        return None
    major, minor = (c >> 8) & 0x1f, (c >> 2) & 0x3f
    if major == 1:
        return "tablet" if minor == 7 else "computer"
    if major == 2:
        return "phone"
    if major == 4:          # audio / video
        return {1: "headset", 2: "headset", 4: "microphone", 5: "speaker", 6: "headphones", 7: "speaker",
                8: "car", 9: "tv", 10: "speaker", 11: "camera", 12: "camera", 13: "camera", 14: "tv",
                15: "tv", 16: "camera", 18: "console"}.get(minor)
    if major == 5:          # peripheral
        low, ptr = (c >> 2) & 0xf, (c >> 6) & 3
        if low in (1, 2):
            return "gamepad"
        if low in (3, 9):
            return "remote"
        if low in (5, 7):
            return "pen"
        if ptr in (1, 3):
            return "keyboard"
        if ptr == 2:
            return "mouse"
        return None
    if major == 6:          # imaging
        if c & 0x80:
            return "printer"
        if c & 0x20:
            return "camera"
        if c & 0x10:
            return "tv"
        return None
    if major == 7:
        return "vr" if minor == 5 else "watch"
    if major == 8:
        return {4: "gamepad", 5: "console"}.get(minor)
    if major == 9:
        return "health"
    return None


def appearance_kind(ap):
    """BLE GAP Appearance → form (category = value >> 6)."""
    try:
        ap = int(ap or 0)
    except (TypeError, ValueError):
        return None
    if not ap:
        return None
    cat, sub = ap >> 6, ap & 0x3f
    if cat == 2:
        return "tablet" if sub == 7 else "computer"
    if cat == 15:
        return {1: "keyboard", 3: "gamepad", 4: "gamepad", 5: "pen", 7: "pen", 10: "remote"}.get(sub, "mouse")
    if cat == 33:
        return "soundbar" if sub == 2 else "speaker"
    if cat == 34:
        return "microphone" if sub in (0, 1) else "speaker"
    if cat == 37:
        return {1: "earbuds", 2: "headset"}.get(sub, "headphones")
    if cat == 39:
        return "tv" if sub == 10 else "speaker"
    return {1: "phone", 3: "watch", 5: "tv", 6: "remote", 7: "vr", 8: "tag", 9: "tag", 10: "speaker",
            12: "health", 13: "health", 14: "health", 16: "health", 17: "health", 18: "health",
            22: "light", 31: "light", 35: "car", 40: "tv", 42: "console", 49: "health", 50: "health",
            52: "health"}.get(cat)


def icon_kind(i):
    for needle, kind in (("headset", "headset"), ("headphone", "headphones"), ("gaming", "gamepad"),
                         ("keyboard", "keyboard"), ("mouse", "mouse"), ("input-tablet", "pen"),
                         ("video-display", "tv"), ("television", "tv"), ("camera", "camera"),
                         ("printer", "printer"), ("phone", "phone"), ("tablet", "tablet")):
        if needle in i:
            return kind
    if i == "computer":
        return "computer"
    if i in ("audio-card", "multimedia-player"):
        return "speaker"
    if i.startswith("input"):
        return "mouse"
    if i.startswith("audio"):
        return "headphones"
    return None


def classify(icon, name, cls=0, appearance=0):
    n = norm_name(name)
    return (_hint(_HINTS, n) or class_kind(cls) or appearance_kind(appearance)
            or _hint(_HINTS_WEAK, n) or icon_kind((icon or "").lower()) or "generic")


def ley_line(rssi):
    if rssi is None:
        return 0, "Dormant"
    if rssi >= -55:
        return 5, "Resonant"
    if rssi >= -65:
        return 4, "Strong"
    if rssi >= -75:
        return 3, "Steady"
    if rssi >= -85:
        return 2, "Faint"
    return 1, "Fading"


FRIENDLY = [
    ("page-timeout", "The companion didn't answer — is it awake and in range?"),
    ("Host is down", "The companion is asleep or out of range"),
    ("AuthenticationFailed", "Pact rejected — authentication failed"),
    ("AuthenticationCanceled", "Pact cancelled"),
    ("AuthenticationRejected", "Pact rejected by the companion"),
    ("AuthenticationTimeout", "Pact timed out — confirm on the device faster"),
    ("ConnectionAttemptFailed", "Connection attempt failed"),
    ("profile-unavailable", "No usable profile — is the audio stack (PipeWire/WirePlumber bluez) running?"),
    ("AlreadyExists", "Already bonded"),
    ("AlreadyConnected", "Already resonating"),
    ("InProgress", "A ritual is already in progress"),
    ("NotReady", "Adapter not ready — awaken the Ley Lines first"),
    ("Blocked", "Sealed by rfkill"),
    ("rfkill", "Sealed by rfkill"),
    ("abort-by-local", "Connection aborted locally"),
    ("DoesNotExist", "That companion vanished from the Archive"),
    ("NoReply", "Timed out waiting for the Ley Lines"),
    ("Timeout", "Timed out"),
    ("ServiceUnknown", "The service isn't running"),
]


def clean_err(msg):
    msg = msg or "Unknown error"
    for needle, nice in FRIENDLY:
        if needle.lower() in msg.lower():
            return nice
    msg = re.sub(r"^GDBus\.Error:[\w.]+:\s*", "", msg)
    return msg


def human(n):
    n = float(n or 0)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return ("%.0f %s" if u == "B" else "%.1f %s") % (n, u)
        n /= 1024


class Dev:
    """Immutable snapshot of a BlueZ Device1 (+Battery1)."""

    def __init__(self, path, p, battery=None):
        self.path = path
        self.address = p.get("Address", "")
        self.name = p.get("Name") or ""
        self.alias = p.get("Alias") or self.name or self.address
        self.icon = p.get("Icon", "")
        self.cls = p.get("Class", 0) or 0
        self.appearance = p.get("Appearance", 0) or 0
        self.connected = bool(p.get("Connected", False))
        self.paired = bool(p.get("Paired", False))
        self.trusted = bool(p.get("Trusted", False))
        self.blocked = bool(p.get("Blocked", False))
        self.bonded = p.get("Bonded")
        self.legacy = p.get("LegacyPairing")
        self.rssi = p.get("RSSI")
        self.txpower = p.get("TxPower")
        self.uuids = list(p.get("UUIDs", []) or [])
        self.modalias = p.get("Modalias", "")
        self.resolved = p.get("ServicesResolved")
        self.wake = p.get("WakeAllowed")
        self.adapter = p.get("Adapter")
        self.battery = battery
        self.auto_kind = classify(self.icon, self.alias + " " + self.name, self.cls, self.appearance)
        ov = (CONFIG.kind_overrides or {}).get(self.address.upper())
        self.overridden = ov in KINDS
        self.kind = ov if self.overridden else self.auto_kind
        self.label, self.element, self.rarity = KINDS[self.kind]
        self.color = ELEMENTS[self.element]

    @property
    def state(self):
        return "connected" if self.connected else ("paired" if self.paired else "new")

    @property
    def nameless(self):
        return not self.name and bool(re.match(r"^([0-9A-F]{2}[-:]){5}[0-9A-F]{2}$", self.alias, re.I))

    @property
    def rank(self):
        return 0 if self.connected else (1 if self.paired else 2)

    @property
    def audio(self):
        """Has a voice: an audio form, or it advertises an audio profile."""
        if self.kind in AUDIO_KINDS:
            return True
        return any(uuid_name(u)[1] in AUDIO_UUIDS for u in self.uuids)


# ════════════════════════════════════════════════════════ utilities ══
def later(ms, fn, *args):
    def _cb():
        fn(*args)
        return False
    return GLib.timeout_add(ms, _cb)


def run_async(argv, cb=None, env=None):
    """Run a command without blocking the UI. cb(ok: bool, output: str). env adds variables."""
    flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
    try:
        if env:
            lau = Gio.SubprocessLauncher.new(flags)
            for k, v in env.items():
                lau.setenv(k, str(v), True)
            proc = lau.spawnv(argv)
        else:
            proc = Gio.Subprocess.new(argv, flags)
    except GLib.Error as e:
        if cb:
            later(1, cb, False, e.message)
        return

    def done(p, res, *_):
        try:
            _ok, out, _err = p.communicate_utf8_finish(res)
        except GLib.Error as e:
            if cb:
                cb(False, e.message)
            return
        if cb:
            cb(p.get_successful(), out or "")
    proc.communicate_utf8_async(None, None, done)


def run_chain(cmds, cb):
    """Run several commands sequentially; cb(list of (title, ok, out))."""
    results = []

    def step(i):
        if i >= len(cmds):
            cb(results)
            return
        title, argv = cmds[i]

        def got(ok, out):
            results.append((title, ok, out))
            step(i + 1)
        run_async(argv, got)
    step(0)


def notify_now(title, body="", icon="bluetooth"):
    """Desktop notification that ignores the 'Desktop notifications' switch."""
    if shutil.which("notify-send"):
        run_async(["notify-send", "-a", "Teyvat Archive", "-i", icon, title, body])


def desktop_notify(title, body="", icon="bluetooth"):
    if CONFIG.desktop_notify:
        notify_now(title, body, icon)


def cls(w, *names):
    ctx = w.get_style_context()
    for n in names:
        ctx.add_class(n)
    return w


def uncls(w, *names):
    ctx = w.get_style_context()
    for n in names:
        ctx.remove_class(n)
    return w


def gbtn(label, cb, *classes):
    b = Gtk.Button(label=label)
    cls(b, "gbtn", *classes)
    b.connect("clicked", lambda *_: cb())
    return b


def section(text):
    lb = Gtk.Label(xalign=0)
    lb.set_markup(esc(text))
    return cls(lb, "section")


def show_widget(w, vis):
    parent = w.get_parent()
    target = parent if isinstance(parent, Gtk.FlowBoxChild) else w
    target.set_visible(vis)


# ── background vigil: XDG autostart entry ───────────────────────────────
AUTOSTART = os.path.join(GLib.get_user_config_dir(), "autostart", "teyvat-archive.desktop")


def autostart_enabled():
    return os.path.isfile(AUTOSTART)


def set_autostart(on):
    try:
        if on:
            exe = shutil.which("teyvat-archive")
            cmd = ('"%s" --background' % exe) if exe else \
                ('"%s" "%s" --background' % (sys.executable, os.path.abspath(__file__)))
            os.makedirs(os.path.dirname(AUTOSTART), exist_ok=True)
            with open(AUTOSTART, "w") as f:
                f.write("[Desktop Entry]\nType=Application\nName=Teyvat Archive (vigil)\n"
                        "Comment=Keeps the pairing agent and the harmony rules awake\nExec=%s\nIcon=bluetooth\n"
                        "Terminal=false\nNoDisplay=true\nX-GNOME-Autostart-enabled=true\n" % cmd)
        elif os.path.exists(AUTOSTART):
            os.remove(AUTOSTART)
        return True, ""
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════ BlueZ ═════
class BlueZ(GObject.Object):
    """Live mirror of org.bluez via ObjectManager + PropertiesChanged."""
    __gsignals__ = {
        "device-added": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "device-removed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "device-changed": (GObject.SignalFlags.RUN_FIRST, None, (str, GObject.TYPE_PYOBJECT)),
        "adapter-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "paired": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "availability": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self):
        super().__init__()
        self.bus = None
        self.mgr = None
        self.adapter = None
        self.known = set()

    def start(self):
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            self.mgr = Gio.DBusObjectManagerClient.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusObjectManagerClientFlags.DO_NOT_AUTO_START,
                BLUEZ, "/", None, None, None)
        except GLib.Error as e:
            print("Teyvat Archive: D-Bus error:", e.message, file=sys.stderr)
            self.emit("availability", False)
            return
        m = self.mgr
        m.connect("object-added", self._obj_added)
        m.connect("object-removed", self._obj_removed)
        m.connect("interface-added", self._iface_added)
        m.connect("interface-removed", self._iface_removed)
        m.connect("interface-proxy-properties-changed", self._props_changed)
        m.connect("notify::name-owner", self._owner_changed)
        self._pick_adapter()
        for obj in m.get_objects():
            self._obj_added(m, obj)
        self.emit("availability", m.get_name_owner() is not None)

    def _obj_added(self, mgr, obj):
        path = obj.get_object_path()
        if obj.get_interface(ADAPTER) is not None and self.adapter is None:
            self._pick_adapter()
        if obj.get_interface(DEVICE) is not None and path not in self.known:
            self.known.add(path)
            self.emit("device-added", path)

    def _obj_removed(self, mgr, obj):
        path = obj.get_object_path()
        if path in self.known:
            self.known.discard(path)
            self.emit("device-removed", path)
        if path == self.adapter:
            self.adapter = None
            self._pick_adapter()

    def _iface_added(self, mgr, obj, iface):
        name, path = iface.get_interface_name(), obj.get_object_path()
        if name == DEVICE:
            self._obj_added(mgr, obj)
        elif name == BATTERY and path in self.known:
            self.emit("device-changed", path, ["Percentage"])
        elif name == ADAPTER:
            self._pick_adapter()

    def _iface_removed(self, mgr, obj, iface):
        name, path = iface.get_interface_name(), obj.get_object_path()
        if name == DEVICE and path in self.known:
            self.known.discard(path)
            self.emit("device-removed", path)
        elif name == BATTERY and path in self.known:
            self.emit("device-changed", path, ["Percentage"])
        elif name == ADAPTER and path == self.adapter:
            self.adapter = None
            self._pick_adapter()

    def _props_changed(self, mgr, obj, iface, changed, invalidated):
        path, name = obj.get_object_path(), iface.get_interface_name()
        try:
            ch = changed.unpack()
        except Exception:
            ch = {}
        if name in (DEVICE, BATTERY) and path in self.known:
            if name == DEVICE and ch.get("Paired") is True:
                self.emit("paired", path)
            self.emit("device-changed", path, list(ch.keys()) + list(invalidated or []))
        elif name == ADAPTER and path == self.adapter:
            self.emit("adapter-changed")

    def _owner_changed(self, *_):
        up = self.mgr.get_name_owner() is not None
        if not up:
            self.adapter = None
        self.emit("availability", up)
        self._pick_adapter()

    def _pick_adapter(self):
        if not self.mgr:
            return
        cands = sorted(o.get_object_path() for o in self.mgr.get_objects()
                       if o.get_interface(ADAPTER) is not None)
        self.adapter = cands[0] if cands else None
        self.emit("adapter-changed")

    def props(self, path, iface=DEVICE):
        if not self.mgr or not path:
            return {}
        obj = self.mgr.get_object(path)
        if obj is None:
            return {}
        p = obj.get_interface(iface)
        if p is None:
            return {}
        out = {}
        for n in p.get_cached_property_names() or []:
            if n in ("ManufacturerData", "ServiceData", "AdvertisingData"):
                continue            # big byte blobs we never show -> skip unpacking them
            v = p.get_cached_property(n)
            if v is not None:
                try:
                    out[n] = v.unpack()
                except Exception:
                    pass
        return out

    def dev(self, path):
        return Dev(path, self.props(path, DEVICE), self.props(path, BATTERY).get("Percentage"))

    def adapter_props(self):
        return self.props(self.adapter, ADAPTER) if self.adapter else {}

    def call(self, path, iface, method, args=None, cb=None, timeout=25000):
        if not self.bus:
            if cb:
                cb(False, "System bus unavailable", None)
            return

        def done(bus, res, *_):
            try:
                val = bus.call_finish(res)
                ok, err = True, None
            except GLib.Error as e:
                ok, err, val = False, clean_err(e.message), None
            if cb:
                cb(ok, err, val)
        self.bus.call(BLUEZ, path, iface, method, args, None,
                      Gio.DBusCallFlags.NONE, timeout, None, done, None)

    def set_prop(self, path, iface, name, variant, cb=None):
        self.call(path, PROPS, "Set", GLib.Variant("(ssv)", (iface, name, variant)), cb)


# ════════════════════════════════════════════════ pairing agent ═══════
AGENT_XML = """<node><interface name="org.bluez.Agent1">
 <method name="Release"/>
 <method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
 <method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
 <method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
 <method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
 <method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
 <method name="RequestAuthorization"><arg type="o" direction="in"/></method>
 <method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
 <method name="Cancel"/>
</interface></node>"""


class PairingAgent:
    """org.bluez.Agent1 — PIN / passkey / confirmation dialogs, Genshin-style."""
    PATH = "/org/teyvat/archive/agent"

    def __init__(self, win):
        self.win = win
        self.reg_id = None
        self.dialog = None
        self.iface = Gio.DBusNodeInfo.new_for_xml(AGENT_XML).interfaces[0]

    def register(self):
        bus = self.win.bz.bus
        if not bus:
            return
        if self.reg_id is None:
            try:
                self.reg_id = bus.register_object(self.PATH, self.iface, self._call, None, None)
            except Exception as e:
                print("agent export failed:", e, file=sys.stderr)
                return

        def registered(ok, err, _v):
            if not ok and "exist" not in (err or "").lower():
                print("RegisterAgent:", err, file=sys.stderr)
            self.win.bz.call("/org/bluez", "org.bluez.AgentManager1", "RequestDefaultAgent",
                             GLib.Variant("(o)", (self.PATH,)), None)
        self.win.bz.call("/org/bluez", "org.bluez.AgentManager1", "RegisterAgent",
                         GLib.Variant("(os)", (self.PATH, "KeyboardDisplay")), registered)

    def unregister(self):
        bus = self.win.bz.bus
        if bus and self.reg_id is not None:
            try:
                bus.call_sync(BLUEZ, "/org/bluez", "org.bluez.AgentManager1", "UnregisterAgent",
                              GLib.Variant("(o)", (self.PATH,)), None, Gio.DBusCallFlags.NONE, 800, None)
            except Exception:
                pass
            bus.unregister_object(self.reg_id)
            self.reg_id = None

    def _name(self, path):
        d = self.win.devs.get(path)
        return d.alias if d else os.path.basename(path or "?")

    def _close(self):
        if self.dialog is not None:
            self.dialog.dismiss()
            self.dialog = None

    def _call(self, conn, sender, path, iface, method, params, inv, *_):
        args = params.unpack() if params is not None else ()
        dev = args[0] if args else None
        name = esc(self._name(dev)) if dev else ""
        reject = lambda: inv.return_dbus_error("org.bluez.Error.Rejected", "Rejected by user")

        if method in ("Release", "Cancel"):
            self._close()
            inv.return_value(None)
        elif method == "RequestConfirmation":
            key = "%06d" % args[1]
            self.win.present()
            self.dialog = self.win.ask(
                "Pact with %s" % self._name(dev),
                "Does this sigil match the one shown on <b>%s</b>?\n\n"
                "<span size='xx-large' weight='bold' foreground='#D3BC8E' letter_spacing='6000'>%s</span>" % (name, key),
                lambda ok: inv.return_value(None) if ok else reject(), ok="Sigils match")
        elif method in ("RequestAuthorization", "AuthorizeService"):
            d = self.win.devs.get(dev)
            if method == "AuthorizeService" and d and d.trusted:
                inv.return_value(None)
                return
            what = ("the talent <b>%s</b>" % esc(uuid_name(args[1])[0])) if method == "AuthorizeService" else "a pact"
            self.dialog = self.win.ask("Authorization", "<b>%s</b> requests %s.\nAllow it?" % (name, what),
                                       lambda ok: inv.return_value(None) if ok else reject(), ok="Allow")
        elif method == "RequestPinCode":
            self.win.present()
            self.dialog = self.win.ask(
                "PIN for %s" % self._name(dev),
                "Enter the PIN code (often <b>0000</b> or <b>1234</b>), or type the one shown on the device.",
                lambda txt: inv.return_value(GLib.Variant("(s)", (txt,))) if txt else reject(),
                entry=True, ok="Offer PIN")
        elif method == "RequestPasskey":
            self.win.present()

            def got(txt):
                if txt and txt.isdigit():
                    inv.return_value(GLib.Variant("(u)", (int(txt),)))
                else:
                    reject()
            self.dialog = self.win.ask("Passkey for %s" % self._name(dev),
                                       "Enter the 6-digit passkey shown on the device.", got,
                                       entry=True, numeric=True, ok="Offer passkey")
        elif method == "DisplayPinCode":
            self.win.toast("Type this PIN on %s" % self._name(dev), args[1], "info", sticky=True)
            inv.return_value(None)
        elif method == "DisplayPasskey":
            entered = args[2] if len(args) > 2 else 0
            self.win.toast("Type on %s" % self._name(dev), "%06d   (%d typed)" % (args[1], entered), "info")
            inv.return_value(None)
        else:
            inv.return_dbus_error("org.bluez.Error.Rejected", "Unknown method")


# ══════════════════════════════════════════════════════════ OBEX ══════
OBEX_AGENT_XML = """<node><interface name="org.bluez.obex.Agent1">
 <method name="Release"/>
 <method name="AuthorizePush"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
 <method name="Cancel"/>
</interface></node>"""


class ObexManager(GObject.Object):
    """OBEX Object Push (send) + incoming-file agent via obexd on the session bus."""
    __gsignals__ = {"transfer": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,))}
    AGENT_PATH = "/org/teyvat/archive/obex_agent"

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.n = 0
        self.subs = {}
        self.agent_id = None
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            self.bus = None

    def _emit(self, info):
        self.emit("transfer", dict(info))

    def send(self, mac, filepath):
        self.n += 1
        info = dict(key="out%d" % self.n, name=os.path.basename(filepath), mac=mac, direction="out",
                    status="summoning", transferred=0, size=os.path.getsize(filepath),
                    file=filepath, t0=time.monotonic(), error="")
        self._emit(info)
        if not self.bus:
            info.update(status="error", error="No session bus")
            self._emit(info)
            return

        def created(bus, res, *_):
            try:
                info["session"] = bus.call_finish(res).unpack()[0]
            except GLib.Error as e:
                info.update(status="error", error=clean_err(e.message))
                self._emit(info)
                return
            bus.call(OBEX, info["session"], "org.bluez.obex.ObjectPush1", "SendFile",
                     GLib.Variant("(s)", (filepath,)), GLib.VariantType("(oa{sv})"),
                     Gio.DBusCallFlags.NONE, -1, None, sent, None)

        def sent(bus, res, *_):
            try:
                tpath, props = bus.call_finish(res).unpack()
            except GLib.Error as e:
                info.update(status="error", error=clean_err(e.message))
                self._emit(info)
                self._remove_session(info)
                return
            info["transfer"] = tpath
            info["status"] = props.get("Status", "queued")
            info["size"] = props.get("Size", info["size"])
            info["t0"] = time.monotonic()
            self._watch(tpath, info)

        self.bus.call(OBEX, "/org/bluez/obex", "org.bluez.obex.Client1", "CreateSession",
                      GLib.Variant("(sa{sv})", (mac, {"Target": GLib.Variant("s", "opp")})),
                      GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, 90000, None, created, None)

    def _watch(self, tpath, info):
        def on_sig(conn, sender, path, iface, signal, params, *_):
            iname, changed, _inv = params.unpack()
            if iname != "org.bluez.obex.Transfer1":
                return
            if "Transferred" in changed:
                info["transferred"] = changed["Transferred"]
            if "Size" in changed:
                info["size"] = changed["Size"]
            if "Status" in changed:
                info["status"] = changed["Status"]
            self._emit(info)
            if info["status"] in ("complete", "error"):
                self._finish(tpath, info)
        self.subs[tpath] = self.bus.signal_subscribe(
            OBEX, PROPS, "PropertiesChanged", tpath, None, Gio.DBusSignalFlags.NONE, on_sig)
        self._emit(info)

    def _finish(self, tpath, info):
        sid = self.subs.pop(tpath, None)
        if sid is not None:
            self.bus.signal_unsubscribe(sid)
        if info["direction"] == "out":
            self._remove_session(info)
            if info["status"] == "complete":
                self.win.toast("Offering delivered ✦", info["name"], "ok")
        elif info["status"] == "complete":
            dest_dir = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
                                    or os.path.expanduser("~/Downloads"), "Teyvat Offerings")
            try:
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, os.path.basename(info["file"]))
                base, ext = os.path.splitext(dest)
                k = 1
                while os.path.exists(dest):
                    dest = "%s (%d)%s" % (base, k, ext)
                    k += 1
                shutil.move(info["file"], dest)
                info["file"] = dest
            except Exception as e:
                info["error"] = str(e)
            self._emit(info)
            self.win.toast("An offering arrived ✦", os.path.basename(info["file"]), "ok")
            desktop_notify("An offering arrived", info["file"], "document-save")

    def _remove_session(self, info):
        if info.get("session") and self.bus:
            self.bus.call(OBEX, "/org/bluez/obex", "org.bluez.obex.Client1", "RemoveSession",
                          GLib.Variant("(o)", (info["session"],)), None,
                          Gio.DBusCallFlags.NONE, -1, None, lambda *a: None, None)

    def set_receiving(self, on):
        if not self.bus:
            return False
        if on and self.agent_id is None:
            try:
                node = Gio.DBusNodeInfo.new_for_xml(OBEX_AGENT_XML)
                self.agent_id = self.bus.register_object(self.AGENT_PATH, node.interfaces[0],
                                                         self._agent_call, None, None)
            except Exception as e:
                self.win.toast("Cannot accept offerings", str(e), "err")
                return False

            def reg(bus, res, *_):
                try:
                    bus.call_finish(res)
                    self.win.toast("Offerings welcome", "Incoming files will be accepted", "ok")
                except GLib.Error as e:
                    self.win.toast("obexd refused the agent", clean_err(e.message), "err")
            self.bus.call(OBEX, "/org/bluez/obex", "org.bluez.obex.AgentManager1", "RegisterAgent",
                          GLib.Variant("(o)", (self.AGENT_PATH,)), None,
                          Gio.DBusCallFlags.NONE, -1, None, reg, None)
        elif not on and self.agent_id is not None:
            try:
                self.bus.call_sync(OBEX, "/org/bluez/obex", "org.bluez.obex.AgentManager1", "UnregisterAgent",
                                   GLib.Variant("(o)", (self.AGENT_PATH,)), None,
                                   Gio.DBusCallFlags.NONE, 800, None)
            except Exception:
                pass
            self.bus.unregister_object(self.agent_id)
            self.agent_id = None
        return True

    def _agent_call(self, conn, sender, path, iface, method, params, inv, *_):
        if method != "AuthorizePush":
            inv.return_value(None)
            return
        tpath = params.unpack()[0]

        def got(bus, res, *_):
            try:
                props = bus.call_finish(res).unpack()[0]
            except GLib.Error:
                inv.return_dbus_error("org.bluez.obex.Error.Rejected", "No transfer info")
                return
            name = os.path.basename(props.get("Name") or "offering.bin")
            size = props.get("Size", 0)

            def decide(ok):
                if not ok:
                    inv.return_dbus_error("org.bluez.obex.Error.Rejected", "Declined")
                    return
                root = os.path.join(GLib.get_user_cache_dir(), "obexd")
                os.makedirs(root, exist_ok=True)
                dest = os.path.join(root, name)
                info = dict(key=tpath, name=name, direction="in", status="queued", transferred=0,
                            size=size, file=dest, t0=time.monotonic(), error="")
                self._watch(tpath, info)
                inv.return_value(GLib.Variant("(s)", (dest,)))

            def ask():
                self.win.ask("An offering arrives",
                             "Accept <b>%s</b> (%s)?" % (esc(name), human(size)), decide,
                             ok="Accept", cancel="Decline")

            mode = CONFIG.incoming_mode
            if mode == "all":
                decide(True)
            elif mode == "trusted" and props.get("Session"):
                def got_sess(b2, r2, *_):
                    try:
                        sp = b2.call_finish(r2).unpack()[0]
                        d = self.win.dev_by_mac(sp.get("Destination", ""))
                        decide(True) if d and d.trusted else ask()
                    except GLib.Error:
                        ask()
                bus.call(OBEX, props["Session"], PROPS, "GetAll",
                         GLib.Variant("(s)", ("org.bluez.obex.Session1",)), GLib.VariantType("(a{sv})"),
                         Gio.DBusCallFlags.NONE, -1, None, got_sess, None)
            else:
                ask()

        self.bus.call(OBEX, tpath, PROPS, "GetAll", GLib.Variant("(s)", ("org.bluez.obex.Transfer1",)),
                      GLib.VariantType("(a{sv})"), Gio.DBusCallFlags.NONE, -1, None, got, None)


# ══════════════════════════════════════════════════ audio (pactl) ═════
_MAC_FULL = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", re.I)
_MAC_ANY = re.compile(r"([0-9A-F]{2}[:_]){5}[0-9A-F]{2}", re.I)


def bt_mac(obj):
    """MAC of a pactl card / sink, or None when it isn't a Bluetooth one."""
    props = obj.get("properties") or {}
    name = obj.get("name") or ""
    bluetooth = (name.startswith("bluez") or props.get("device.api") == "bluez5"
                 or props.get("device.bus") == "bluetooth" or "api.bluez5.address" in props)
    if not bluetooth:
        return None
    for k in ("api.bluez5.address", "device.string"):
        v = str(props.get(k) or "")
        if _MAC_FULL.match(v):
            return v.upper()
    m = _MAC_ANY.search(name)
    return m.group(0).replace("_", ":").upper() if m else None


def sink_volume(s):
    vols = list((s.get("volume") or {}).values())
    try:
        pcts = [int(str(v.get("value_percent", "100%")).strip().rstrip("%")) for v in vols]
        return int(round(sum(pcts) / len(pcts))) if pcts else 100
    except Exception:
        return 100


def pulse_snapshot(cb):
    """One look at the audio graph. cb(dict(ok, err, cards{mac}, sinks{mac}, default, default_desc))."""
    if not shutil.which("pactl"):
        cb(dict(ok=False, err="pactl is not installed — Arch: libpulse (with pipewire-pulse) · "
                              "Debian: pulseaudio-utils", cards={}, sinks={}, default="", default_desc=""))
        return
    cmds = [("cards", ["pactl", "-f", "json", "list", "cards"]),
            ("sinks", ["pactl", "-f", "json", "list", "sinks"]),
            ("info", ["env", "LC_ALL=C", "pactl", "info"])]

    def done(results):
        res = {t: (ok, o) for t, ok, o in results}
        out = dict(ok=True, err="", cards={}, sinks={}, default="", default_desc="")
        info = res.get("info", (False, ""))[1]
        if not res.get("info", (False, ""))[0]:
            out.update(ok=False, err="The audio server does not answer (is pipewire-pulse / pulseaudio running?)")
            cb(out)
            return
        try:
            cards = json.loads(res["cards"][1])
            sinks = json.loads(res["sinks"][1])
        except Exception:
            out.update(ok=False, err="pactl can't speak JSON here — it needs PulseAudio ≥ 16 or a recent "
                                     "pipewire-pulse (pactl -f json)")
            cb(out)
            return
        for c in cards if isinstance(cards, list) else []:
            mac = bt_mac(c)
            if mac:
                out["cards"][mac] = c
        descs = {}
        for s in sinks if isinstance(sinks, list) else []:
            descs[s.get("name", "")] = s.get("description") or s.get("name", "")
            mac = bt_mac(s)
            if mac and mac not in out["sinks"]:
                out["sinks"][mac] = dict(name=s.get("name", ""), desc=s.get("description") or "",
                                         vol=sink_volume(s), mute=bool(s.get("mute")),
                                         state=str(s.get("state", "")).lower())
        m = re.search(r"Default Sink:\s*(\S+)", info)
        out["default"] = m.group(1) if m else ""
        out["default_desc"] = descs.get(out["default"], out["default"])
        cb(out)
    run_chain(cmds, done)


def find_bt_sink(mac, cb):
    """cb(sink_name or None, volume %, muted) for the PipeWire / Pulse sink of this companion."""
    key = mac.upper()
    if not shutil.which("pactl"):
        cb(None, 0, False)
        return

    def short(ok, out):
        if ok:
            k2 = key.replace(":", "_")
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) > 1 and k2 in parts[1].upper():
                    cb(parts[1], 100, False)
                    return
        cb(None, 0, False)

    def got(ok, out):
        if ok:
            try:
                for s in json.loads(out):
                    if bt_mac(s) == key:
                        cb(s["name"], sink_volume(s), bool(s.get("mute")))
                        return
                cb(None, 0, False)
                return
            except Exception:
                pass
        run_async(["pactl", "list", "short", "sinks"], short)     # old pactl without -f json
    run_async(["pactl", "-f", "json", "list", "sinks"], got)


def wait_bt_sink(mac, cb, tries=12):
    """The sink shows up a moment AFTER BlueZ reports Connected — poll briefly. cb(sink or None)."""
    def got(name, _vol, _mute):
        if name or tries <= 0:
            cb(name)
        else:
            later(700, wait_bt_sink, mac, cb, tries - 1)
    find_bt_sink(mac, got)


def move_streams(sink, cb):
    run_async(["sh", "-c", 'for i in $(pactl list short sink-inputs | cut -f1); do '
                           'pactl move-sink-input "$i" "$1"; done', "sh", sink], lambda *_: cb(True, ""))


def route_audio(mac, cb, tries=12):
    """Make this companion the default output and move every playing stream onto it."""
    if not shutil.which("pactl"):
        cb(False, "pactl is not installed (pipewire-pulse / pulseaudio-utils)")
        return

    def got(sink):
        if not sink:
            cb(False, "no audio output appeared for this companion")
            return

        def set_def(ok, out):
            if not ok:
                cb(False, out.strip()[:160])
                return
            move_streams(sink, cb)
        run_async(["pactl", "set-default-sink", sink], set_def)
    wait_bt_sink(mac, got, tries)


def set_bt_volume(mac, pct, cb):
    if not shutil.which("pactl"):
        cb(False, "pactl is not installed (pipewire-pulse / pulseaudio-utils)")
        return

    def got(sink):
        if not sink:
            cb(False, "no audio output appeared for this companion")
            return
        run_async(["pactl", "set-sink-volume", sink, "%d%%" % pct],
                  lambda ok, out: cb(ok, "" if ok else out.strip()[:160]))
    wait_bt_sink(mac, got)


CHIMES = ["/usr/share/sounds/freedesktop/stereo/complete.oga",
          "/usr/share/sounds/freedesktop/stereo/bell.oga",
          "/usr/share/sounds/freedesktop/stereo/message.oga",
          "/usr/share/sounds/freedesktop/stereo/audio-volume-change.oga"]


def play_chime(sink, cb):
    f = next((c for c in CHIMES if os.path.isfile(c)), None)
    if not f:
        cb(False, "no freedesktop sound found — install sound-theme-freedesktop")
        return
    if shutil.which("paplay"):
        run_async(["paplay", "--device=%s" % sink, f], lambda ok, out: cb(ok, out.strip()[:160]))
    elif shutil.which("pw-play"):
        run_async(["pw-play", "--target", sink, f], lambda ok, out: cb(ok, out.strip()[:160]))
    else:
        cb(False, "paplay / pw-play not found")


# ═══════════════════════════════════════════════════ base widgets ═════
class Anim:
    """ONE frame-clock ticker for the whole window.

    * a single tick callback on the toplevel drives every animated widget
    * frame rate snaps to an integer divisor of the monitor refresh rate (even frame spacing)
    * pauses while minimised; hidden pages are unmapped and cost nothing
    """
    widgets = set()
    paused = False
    _last = -1.0
    _rr = 60.0
    _rr_t = -99.0

    @classmethod
    def add(cls, w):
        cls.widgets.add(w)
        w.connect("destroy", lambda ww: cls.widgets.discard(ww))

    @classmethod
    def refresh_rate(cls, win, now):
        if now - cls._rr_t > 3.0:
            cls._rr_t = now
            try:
                gw = win.get_window()
                mon = win.get_display().get_monitor_at_window(gw) if gw else None
                r = (mon.get_refresh_rate() / 1000.0) if mon else 0
                cls._rr = r if 20 <= r <= 500 else 60.0
            except Exception:
                cls._rr = 60.0
        return cls._rr

    @classmethod
    def fps(cls, win=None, now=0.0):
        if CONFIG.reduce_motion:
            return 2.0
        want = float(max(10, min(240, int(CONFIG.fps or 60))))
        rr = cls.refresh_rate(win, now) if win is not None else 60.0
        if want >= rr:
            return rr
        return rr / max(1, round(rr / want))

    @classmethod
    def tick(cls, win, clock):
        if cls.paused:
            return True
        now = clock.get_frame_time() / 1e6
        iv = 1.0 / cls.fps(win, now)
        if now - cls._last < iv * 0.75:
            return True
        cls._last = now if now - cls._last > 1.5 * iv else cls._last + iv
        for w in list(cls.widgets):
            try:
                if w.get_mapped() and w.animating():
                    w.request_draw()
            except Exception:
                cls.widgets.discard(w)
        return True


def apply_ui_anim():
    """Master switch for GTK's own animations (switch slides, toast glide)."""
    try:
        on = bool(CONFIG.smooth_ui) and not CONFIG.reduce_motion
        Gtk.Settings.get_default().set_property("gtk-enable-animations", on)
    except Exception:
        pass


class AnimatedArea(Gtk.DrawingArea):
    """DrawingArea driven by the shared Anim ticker.

    CACHE = True : keeps the last frame off-screen; a repaint caused by something else just blits it.
    animating()  : return False when nothing changes with time -> zero per-frame cost
    """
    CACHE = True

    def __init__(self, animate=True):
        super().__init__()
        self._cache = None
        self._ckey = None
        self._dirty = True
        self.connect("draw", self._on_draw)
        if animate:
            Anim.add(self)

    def animating(self):
        return True

    def redraw(self):
        self._dirty = True
        self.queue_draw()

    def request_draw(self):
        self.redraw()

    def frame_t(self):
        fc = self.get_frame_clock()
        if fc is not None:
            ft = fc.get_frame_time()
            if ft:
                return ft / 1e6 - T0
        return now_t()

    def _on_draw(self, w, cr):
        a = self.get_allocation()
        W, H = a.width, a.height
        if W < 1 or H < 1:
            return False
        t = self.frame_t()
        if not self.CACHE:
            self.paint(cr, W, H, t)
            return False
        sc = max(1, self.get_scale_factor())
        key = (W, H, sc)
        if self._cache is None or self._ckey != key:
            self._cache = cairo.ImageSurface(cairo.FORMAT_ARGB32, W * sc, H * sc)
            try:
                self._cache.set_device_scale(sc, sc)
            except Exception:
                pass
            self._ckey = key
            self._dirty = True
        if self._dirty:
            c = cairo.Context(self._cache)
            c.set_operator(cairo.OPERATOR_CLEAR)
            c.paint()
            c.set_operator(cairo.OPERATOR_OVER)
            self.paint(c, W, H, t)
            self._cache.flush()
            self._dirty = False
        cr.set_source_surface(self._cache, 0, 0)
        cr.paint()
        return False

    def paint(self, cr, w, h, t):
        pass


class Backdrop:
    """Night sky painted straight onto the root box — no extra widget, no extra window layer.

    The sky, aurora, wheel rings, gold corners and every star are baked ONCE per size.
    Optional twinkling (Settings) only touches ~two dozen tiny boxes ~20 times a second.
    The constellation wheel turns slowly: its two rotating layers are baked once as sprites and just
    re-blitted at a gentle ~15 fps (only inside the wheel's own box), so it costs almost nothing.
    """
    N_DOTS, N_SPARK = 150, 26
    WHEEL_FPS = 15.0

    def __init__(self, widget):
        self.w = widget
        self._base, self._bkey, self._sprites, self._n = None, None, {}, 0
        self._wl_sprites, self._wl_last = {}, -1.0
        rnd = random.Random(7)
        self.dots = [(rnd.random(), rnd.random(), rnd.uniform(.4, 1.5), rnd.uniform(.15, .6))
                     for _ in range(self.N_DOTS)]
        self.sparks = [(rnd.random(), rnd.random(), rnd.uniform(2.6, 5.4), rnd.uniform(.4, 1.3), rnd.random() * 6.28)
                       for _ in range(self.N_SPARK)]
        widget.connect("draw", self._draw)        # runs BEFORE the box draws its children
        Anim.widgets.add(self)

    # ── Anim protocol
    def get_mapped(self):
        return self.w.get_mapped()

    def _f(self):
        return max(0.0, min(1.5, float(CONFIG.particle_density))) / 1.5

    def stars_on(self):
        return bool(CONFIG.animated_stars) and not CONFIG.reduce_motion and self._f() > 0

    def wheel_on(self):
        return bool(CONFIG.animated_wheel) and not CONFIG.reduce_motion

    def animating(self):
        return self.stars_on() or self.wheel_on()

    @staticmethod
    def _wheel_geom(a):
        return a.width * .86, a.height * .80, min(a.width, a.height) * .42

    def request_draw(self):
        self._n += 1
        a = self.w.get_allocation()
        if self.stars_on() and not self._n % 3:    # twinkling is slow — every 3rd frame is plenty
            for x, y, r, _sp, _ph in self.sparks[:int(self.N_SPARK * self._f())]:
                hs = int(r + 3)
                self.w.queue_draw_area(int(x * a.width) - hs, int(y * a.height) - hs, 2 * hs, 2 * hs)
        if self.wheel_on():
            t = now_t()
            if t - self._wl_last >= 1.0 / self.WHEEL_FPS - 0.004:
                self._wl_last = t
                cx, cy, R = self._wheel_geom(a)
                hs = int(R + 4)
                self.w.queue_draw_area(int(cx) - hs, int(cy) - hs, 2 * hs, 2 * hs)

    def invalidate(self):
        self._base = None
        self.w.queue_draw()

    # ── painting
    def _sprite(self, r, sc):
        k = (round(r, 1), sc)
        sp = self._sprites.get(k)
        if sp is None:
            def p(c, r=r):
                star4(c, 0, 0, r, .25)
                src(c, GOLD, 1)
                c.fill()
            side = 2 * r + 2
            sp = self._sprites[k] = (make_surface(side, sc, p), side)
        return sp

    def _base_layer(self, w, h):
        sc = max(1, self.w.get_scale_factor())
        anim = self.stars_on()
        wheel = self.wheel_on()
        key = (w, h, sc, round(self._f(), 3), anim, wheel)
        if self._base is not None and self._bkey == key:
            return self._base
        k = 4
        sw, sh = max(1, int(w / k)), max(1, int(h / k))
        sky = cairo.ImageSurface(cairo.FORMAT_RGB24, sw, sh)
        c = cairo.Context(sky)
        c.scale(sw / float(w), sh / float(h))
        g = cairo.LinearGradient(0, 0, 0, h)
        for off, col in ((0, "#151926"), (.55, "#222739"), (1, "#2E3550")):
            g.add_color_stop_rgb(off, *hx(col))
        c.set_source(g)
        c.paint()
        t = 20.0
        for i, (col, sp) in enumerate(((ELEMENTS["Hydro"], .07), (ELEMENTS["Electro"], .05), (GOLD, .04))):
            x = w * (.2 + .6 * (.5 + .5 * math.sin(t * sp + i * 2)))
            y = h * (.25 + .5 * (.5 + .5 * math.cos(t * sp * 1.3 + i)))
            rg = cairo.RadialGradient(x, y, 0, x, y, max(w, h) * .45)
            rg.add_color_stop_rgba(0, col[0], col[1], col[2], .10)
            rg.add_color_stop_rgba(1, col[0], col[1], col[2], 0)
            c.set_source(rg)
            c.paint()
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, w * sc, h * sc)
        try:
            surf.set_device_scale(sc, sc)
        except Exception:
            pass
        c = cairo.Context(surf)
        c.save()
        c.scale(w / float(sw), h / float(sh))
        c.set_source_surface(sky, 0, 0)
        pat = c.get_source()
        pat.set_filter(cairo.FILTER_BILINEAR)
        pat.set_extend(cairo.EXTEND_PAD)
        c.paint()
        c.restore()
        self._wheel_rings(c, w * .86, h * .80, min(w, h) * .42, still=not wheel)
        f = self._f()
        for x, y, r, al in self.dots[:int(self.N_DOTS * f)]:
            c.new_sub_path()
            c.arc(x * w, y * h, r, 0, 2 * math.pi)
            src(c, CREAM, al)
            c.fill()
        if not anim:
            for x, y, r, _sp, ph in self.sparks[:int(self.N_SPARK * f)]:
                star4(c, x * w, y * h, r, .25)
                src(c, GOLD, .25 + .45 * abs(math.sin(ph)))
                c.fill()
        src(c, GOLD, .35)
        c.set_line_width(1)
        m, L = 10, 70
        for (x, y, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            c.move_to(x, y + sy * L)
            c.line_to(x, y)
            c.line_to(x + sx * L, y)
            c.stroke()
            star4(c, x + sx * 7, y + sy * 7, 5, .3)
            c.fill()
        surf.flush()
        self._base, self._bkey = surf, key
        return surf

    def _draw(self, w, cr):
        a = w.get_allocation()
        if a.width < 2 or a.height < 2:
            return False
        cr.set_source_surface(self._base_layer(a.width, a.height), 0, 0)
        cr.paint()
        x1, y1, x2, y2 = cr.clip_extents()
        sc = max(1, w.get_scale_factor())
        t = now_t()
        if self.wheel_on():
            self._draw_wheel(cr, a, sc, t, (x1, y1, x2, y2))
        if self.stars_on():
            for x, y, r, sp, ph in self.sparks[:int(self.N_SPARK * self._f())]:
                px, py = x * a.width, y * a.height
                if px < x1 - r or px > x2 + r or py < y1 - r or py > y2 + r:
                    continue
                surf, side = self._sprite(r, sc)
                cr.set_source_surface(surf, px - side / 2.0, py - side / 2.0)
                cr.paint_with_alpha(.15 + .7 * abs(math.sin(t * sp + ph)))
        return False

    # ── constellation wheel: static rings baked into the sky, two slowly turning layers as sprites
    @staticmethod
    def _wheel_spokes(cr, R):
        src(cr, GOLD, .07)
        cr.set_line_width(1.2)
        for k in range(24):
            a = k * math.pi / 12
            r2 = R if k % 2 else R * .9
            cr.move_to(math.cos(a) * R * .82, math.sin(a) * R * .82)
            cr.line_to(math.cos(a) * r2, math.sin(a) * r2)
        cr.stroke()

    @staticmethod
    def _wheel_star(cr, R):
        src(cr, GOLD, .07)
        cr.set_line_width(1.2)
        pts = [(math.cos(k * 2 * math.pi / 7) * R * .55, math.sin(k * 2 * math.pi / 7) * R * .55) for k in range(7)]
        for i in range(7):
            cr.move_to(*pts[i])
            cr.line_to(*pts[(i + 3) % 7])
        cr.stroke()
        for i, (x, y) in enumerate(pts):
            cr.new_sub_path()
            cr.arc(x, y, R * .035, 0, 2 * math.pi)
            src(cr, ELEM_LIST[i], .25)
            cr.fill()

    @staticmethod
    def _wheel_rings(cr, cx, cy, R, still=False):
        cr.save()
        cr.translate(cx, cy)
        src(cr, GOLD, .07)
        cr.set_line_width(1.2)
        for r in (R, R * .82, R * .55, R * .3):
            cr.new_sub_path()
            cr.arc(0, 0, r, 0, 2 * math.pi)
            cr.stroke()
        if still:                                  # animation off -> frozen at the old fixed pose (t = 20 s)
            t = 20.0
            cr.save()
            cr.rotate(t * .03)
            Backdrop._wheel_spokes(cr, R)
            cr.restore()
            cr.save()
            cr.rotate(t * .03 - t * .07)
            Backdrop._wheel_star(cr, R)
            cr.restore()
        cr.restore()

    def _wheel_sprites(self, R, sc):
        k = (int(round(R)), sc)
        sp = self._wl_sprites.get(k)
        if sp is None:
            self._wl_sprites.clear()               # window resized -> drop the old size
            side = 2 * R + 6
            sp = self._wl_sprites[k] = (
                make_surface(side, sc, lambda c: Backdrop._wheel_spokes(c, R)),
                make_surface(side, sc, lambda c: Backdrop._wheel_star(c, R)),
                side)
        return sp

    def _draw_wheel(self, cr, a, sc, t, clip):
        cx, cy, R = self._wheel_geom(a)
        x1, y1, x2, y2 = clip
        if cx + R < x1 or cx - R > x2 or cy + R < y1 or cy - R > y2:
            return
        spokes, star, side = self._wheel_sprites(R, sc)
        for surf, ang in ((spokes, t * .03), (star, t * .03 - t * .07)):
            cr.save()
            cr.translate(cx, cy)
            cr.rotate(ang)
            cr.set_source_surface(surf, -side / 2.0, -side / 2.0)
            cr.paint()
            cr.restore()


class DeviceIcon(AnimatedArea):
    def __init__(self, size=64, ring=True):
        super().__init__()
        self.set_size_request(size, size)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.kind, self.col, self.state = "generic", GOLD, "new"
        self.battery, self.busy, self.ring = None, False, ring

    def update(self, kind, col, state, battery=None, busy=False):
        new = (kind, col, state, battery, busy)
        if new != (self.kind, self.col, self.state, self.battery, self.busy):
            self.kind, self.col, self.state, self.battery, self.busy = new
            self.redraw()

    def animating(self):    # idle / unpaired icons are a still picture -> no per-frame cost
        return (self.state == "connected" or self.busy
                or (self.battery is not None and self.battery <= 20))

    def paint(self, cr, w, h, t):
        draw_device_emblem(cr, self.kind, w / 2, h / 2, min(w, h), t, self.col, self.state,
                           self.battery, self.busy, self.ring)


class AdapterEmblem(AnimatedArea):
    def __init__(self, size=150):
        super().__init__()
        self.set_size_request(size, size)
        self._state = "off"

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, v):
        if v != self._state:
            self._state = v
            self.redraw()

    def animating(self):
        return self._state != "off"

    def paint(self, cr, w, h, t):
        draw_adapter_emblem(cr, w / 2, h / 2, min(w, h) / 2 - 4, t, self._state)


class LeyLineBar(AnimatedArea):
    """Still picture: repaints only when the level / colour actually changes."""

    def __init__(self, w=90, h=14):
        super().__init__(animate=False)
        self.set_size_request(w, h)
        self.set_valign(Gtk.Align.CENTER)
        self._level, self._col = 0, ELEMENTS["Anemo"]

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, v):
        if v != self._level:
            self._level = v
            self.redraw()

    @property
    def col(self):
        return self._col

    @col.setter
    def col(self, v):
        if v != self._col:
            self._col = v
            self.redraw()

    def paint(self, cr, w, h, t):
        draw_leyline(cr, 0, 0, w, h, self._level, self._col)


class Ornament(AnimatedArea):
    def __init__(self, height=14):
        super().__init__(animate=False)
        self.set_size_request(-1, height)

    def paint(self, cr, w, h, t):
        y = h / 2
        g = cairo.LinearGradient(0, 0, w, 0)
        g.add_color_stop_rgba(0, GOLD[0], GOLD[1], GOLD[2], 0)
        g.add_color_stop_rgba(.5, GOLD[0], GOLD[1], GOLD[2], .8)
        g.add_color_stop_rgba(1, GOLD[0], GOLD[1], GOLD[2], 0)
        cr.set_source(g)
        cr.set_line_width(1)
        cr.move_to(0, y)
        cr.line_to(w, y)
        cr.stroke()
        src(cr, DEEP, 1)
        cr.rectangle(w / 2 - 16, y - 6, 32, 12)
        cr.fill()
        star4(cr, w / 2, y, 6, .3)
        src(cr, GOLD)
        cr.fill()
        for dx in (-11, 11):
            star4(cr, w / 2 + dx, y, 2.5, .4)
            cr.fill()


class NavIcon(AnimatedArea):
    """Vector sidebar icon — crisp, always visible, recoloured for hover / checked."""
    COLORS = {"idle": GOLD, "hover": CREAM, "checked": INK}

    def __init__(self, key, size=24):
        super().__init__(animate=False)
        self.key, self.mode = key, "idle"
        self.set_size_request(size, size)
        self.set_valign(Gtk.Align.CENTER)

    def sync(self, btn):
        if btn.get_active():
            m = "checked"
        elif btn.get_state_flags() & Gtk.StateFlags.PRELIGHT:
            m = "hover"
        else:
            m = "idle"
        if m != self.mode:
            self.mode = m
            self.redraw()

    def paint(self, cr, w, h, t):
        s = min(w, h) / 24.0
        cr.translate(w / 2, h / 2)
        cr.scale(s, s)
        draw_nav_icon(cr, self.key, self.COLORS[self.mode])


class WishView(Gtk.DrawingArea):
    """The 'Wish' cinematic when a new pact is forged.

    It lives on its own page of the top-level stack and is fully opaque: the window is frozen
    into a snapshot once, so GTK never repaints the real widgets underneath while it plays.
    Short (2.6 s), and a click / Esc / Space skips it.
    """
    DURATION = 2.6
    FALL = .45

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.start, self._pending = None, False
        self.snap = self.dim = None
        self.name, self.kind, self.col, self.rarity = "", "generic", GOLD, 4
        rnd = random.Random(3)
        self.sparks = [(rnd.random() * 2 * math.pi, rnd.uniform(.35, 1), rnd.uniform(1, 3)) for _ in range(48)]
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", lambda *_: (self.finish(), True)[1])
        self.connect("draw", self._draw)
        Anim.add(self)

    @property
    def playing(self):
        return self.start is not None or self._pending

    def animating(self):
        return self.playing

    def request_draw(self):
        self.queue_draw()

    def play(self, name, kind, col, rarity):
        main = self.win.main_overlay
        a = main.get_allocation()
        w, h = max(1, a.width), max(1, a.height)
        sc = max(1, self.win.get_scale_factor())

        def surface():
            s = cairo.ImageSurface(cairo.FORMAT_RGB24, w * sc, h * sc)
            try:
                s.set_device_scale(sc, sc)
            except Exception:
                pass
            return s
        snap = surface()
        c = cairo.Context(snap)
        src(c, DEEP, 1)
        c.paint()
        try:
            main.draw(c)                 # freeze the window once
        except Exception:
            pass
        snap.flush()
        dim = surface()
        c = cairo.Context(dim)
        c.set_source_surface(snap, 0, 0)
        c.paint()
        src(c, (.02, .03, .07), .86)
        c.paint()
        dim.flush()
        self.snap, self.dim = snap, dim
        self.name, self.kind, self.col, self.rarity = name, kind, col, rarity
        self.start, self._pending = None, True
        self.win.top.set_visible_child_name("wish")
        self.queue_draw()

    def finish(self):
        if not self.playing:
            return
        self.start, self._pending = None, False
        self.snap = self.dim = None
        self.win.top.set_visible_child_name("main")

    def _t(self):
        fc = self.get_frame_clock()
        ft = fc.get_frame_time() if fc is not None else 0
        return ft / 1e6 - T0 if ft else now_t()

    def _draw(self, _w, cr):
        a = self.get_allocation()
        w, h = a.width, a.height
        t = self._t()
        if self._pending:
            self._pending, self.start = False, t
        if self.start is None or self.dim is None:
            src(cr, DEEP, 1)
            cr.paint()
            return False
        e = max(0.0, t - self.start)
        if e >= self.DURATION:
            cr.set_source_surface(self.snap, 0, 0)
            cr.paint()
            GLib.idle_add(lambda: self.finish() and False)
            return False
        A_in = min(1.0, e / .22)
        A_out = 1.0 if e < self.DURATION - .35 else max(0.0, (self.DURATION - e) / .35)
        A = A_in * A_out
        cr.set_source_surface(self.dim, 0, 0)
        cr.paint()
        if A < 1:
            cr.set_source_surface(self.snap, 0, 0)
            cr.paint_with_alpha(1 - A)
        rc = RARITY.get(self.rarity, RARITY[4])
        cx, cy = w / 2, h * .42
        if e < self.FALL:                                   # falling star
            q0 = e / self.FALL
            ease = 1 - (1 - q0) ** 3
            sx, sy = w * 1.05, -h * .1
            for k in range(14):
                q = max(0, ease - k * .022)
                cr.new_sub_path()
                cr.arc(sx + (cx - sx) * q, sy + (cy - sy) * q, max(.8, 9 - k * .55), 0, 2 * math.pi)
                src(cr, rc, (1 - k / 14) * .55 * A)
                cr.fill()
            x, y = sx + (cx - sx) * ease, sy + (cy - sy) * ease
            g = cairo.RadialGradient(x, y, 0, x, y, 40)
            g.add_color_stop_rgba(0, CREAM[0], CREAM[1], CREAM[2], .9)
            g.add_color_stop_rgba(1, rc[0], rc[1], rc[2], 0)
            cr.set_source(g)
            cr.new_sub_path()
            cr.arc(x, y, 40, 0, 2 * math.pi)
            cr.fill()
            star4(cr, x, y, 16, .25)
            src(cr, CREAM)
            cr.fill()
            return False
        e2 = e - self.FALL
        if e2 < .3:
            src(cr, CREAM, (1 - e2 / .3) * .45 * A)
            cr.paint()
        L = max(w, h)
        cr.save()                                           # god rays: ONE path, one fill
        cr.translate(cx, cy)
        cr.rotate(e * .25)
        for k in range(12):
            a0 = k * 2 * math.pi / 12
            ca, sa = math.cos(a0), math.sin(a0)
            px, py = -sa, ca
            cr.move_to(0, 0)
            cr.line_to(ca * L + px * 22, sa * L + py * 22)
            cr.line_to(ca * L - px * 22, sa * L - py * 22)
            cr.close_path()
        src(cr, rc, .06 * A)
        cr.fill()
        cr.restore()
        if e2 < .6:
            k = e2 / .6
            cr.new_sub_path()
            cr.arc(cx, cy, (k ** .5) * L * .55, 0, 2 * math.pi)
            cr.set_line_width(2 + 14 * (1 - k))
            src(cr, rc, (1 - k) * .8 * A)
            cr.stroke()
        fly = 1 - (1 - min(1.0, e2 / 1.1)) ** 3             # sparks ease out — quick, then settle
        fade = max(0.0, 1 - e2 / 1.6) * A
        if fade > 0:
            for big in (True, False):
                for ang, sp, sz in self.sparks:
                    if (sz > 2) != big:
                        continue
                    d = fly * sp * 240
                    star4(cr, cx + math.cos(ang) * d, cy + math.sin(ang) * d, sz * 2, .3)
                src(cr, rc if big else CREAM, fade)
                cr.fill()
        size = min(w, h) * .34 * (min(1.0, e2 / .3) ** .5)
        g = cairo.RadialGradient(cx, cy, 0, cx, cy, max(1, size))
        g.add_color_stop_rgba(0, rc[0], rc[1], rc[2], .35 * A)
        g.add_color_stop_rgba(1, rc[0], rc[1], rc[2], 0)
        cr.set_source(g)
        cr.new_sub_path()
        cr.arc(cx, cy, max(1, size), 0, 2 * math.pi)
        cr.fill()
        if size > 4:
            draw_device_emblem(cr, self.kind, cx, cy, size, t, self.col, "connected")
        ty = cy + min(w, h) * .25
        if e2 > .25:
            al = min(1.0, (e2 - .25) / .25) * A
            draw_text(cr, self.name, cx, ty, 26, CREAM, al, bold=True)
            draw_text(cr, "A new companion has answered your call", cx, ty + 36, 11, GOLD, al * .85)
            draw_text(cr, "click to continue", cx, h - 28, 8, CREAM, al * .35)
        n = self.rarity
        for i in range(n):
            st = .4 + i * .08
            if e2 < st:
                continue
            pop = min(1.0, (e2 - st) / .15)
            star5(cr, cx + (i - (n - 1) / 2) * 30, ty + 70, 11 * (1 + (1 - pop) * .7))
            src(cr, rc, pop * A)
            cr.fill()
        return False


class Toaster(Gtk.Revealer):
    """Genshin quest-style banner notifications."""
    GLYPH = {"info": "✦", "ok": "◆", "err": "✕", "warn": "⚠"}

    def __init__(self):
        super().__init__()
        self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.set_transition_duration(180)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.set_margin_top(12)
        box = cls(Gtk.Box(spacing=14), "toast")
        self.icon = Gtk.Label()
        cls(self.icon, "toast-glyph")
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.title = cls(Gtk.Label(xalign=0), "toast-title")
        self.body = cls(Gtk.Label(xalign=0), "toast-body")
        self.body.set_line_wrap(True)
        self.body.set_max_width_chars(60)
        v.pack_start(self.title, False, False, 0)
        v.pack_start(self.body, False, False, 0)
        box.pack_start(self.icon, False, False, 0)
        box.pack_start(v, True, True, 0)
        self.add(box)
        self.q, self.busy = [], False

    def push(self, title, body="", kind="info", sticky=False):
        self.q.append((title, body, kind, sticky))
        del self.q[:-4]                          # never build up a long backlog of banners
        if not self.busy:
            self._next()

    def _next(self):
        if not self.q:
            self.busy = False
            self.set_reveal_child(False)
            return
        self.busy = True
        title, body, kind, sticky = self.q.pop(0)
        self.icon.set_text(self.GLYPH.get(kind, "✦"))
        for k in self.GLYPH:
            uncls(self.icon, "t-" + k)
        cls(self.icon, "t-" + kind)
        self.title.set_text(title)
        self.body.set_text(body or "")
        self.body.set_visible(bool(body))
        self.set_reveal_child(True)
        later(9000 if sticky else (1800 if self.q else 2800), self._hide)

    def _hide(self):
        self.set_reveal_child(False)
        later(220, self._next)


class GDialog(Gtk.Window):
    """Genshin confirm dialog — ⊗ Cancel / ◎ Confirm."""

    def __init__(self, parent, title, markup, cb, entry=False, numeric=False, ok="Confirm", cancel="Cancel"):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_decorated(False)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        cls(self, "gdialog")
        self.cb, self.done = cb, False
        self.is_entry = entry
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for m in ("top", "bottom", "start", "end"):
            getattr(box, "set_margin_" + m)(26)
        box.set_size_request(460, -1)
        t = cls(Gtk.Label(), "dlg-title")
        t.set_markup(esc(title))
        box.pack_start(t, False, False, 0)
        box.pack_start(Ornament(), False, False, 0)
        body = Gtk.Label()
        body.set_markup(markup)
        body.set_line_wrap(True)
        body.set_justify(Gtk.Justification.CENTER)
        body.set_max_width_chars(48)
        box.pack_start(body, False, False, 6)
        self.entry = None
        if entry:
            self.entry = Gtk.Entry()
            self.entry.set_alignment(.5)
            if numeric:
                self.entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
                self.entry.set_max_length(6)
            self.entry.connect("activate", lambda *_: self.finish(True))
            box.pack_start(self.entry, False, False, 0)
        row = Gtk.Box(spacing=16, homogeneous=True)
        row.pack_start(gbtn("⊗   " + cancel, lambda: self.finish(False), "dark"), True, True, 0)
        okb = gbtn("◎   " + ok, lambda: self.finish(True))
        row.pack_start(okb, True, True, 0)
        box.pack_start(row, False, False, 6)
        self.add(box)
        self.connect("key-press-event", self._key)
        self.connect("delete-event", lambda *_: (self.finish(False), True)[1])
        self.show_all()
        (self.entry or okb).grab_focus()

    def _key(self, w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.finish(False)
            return True
        return False

    def finish(self, accepted):
        if self.done:
            return
        self.done = True
        val = (self.entry.get_text().strip() if accepted else None) if self.is_entry else accepted
        self.destroy()
        self.cb(val)

    def dismiss(self):
        if not self.done:
            self.done = True
            self.destroy()


class ScrollCap(AnimatedArea):
    """Little Genshin diamond that sits at either end of the scroll rail."""

    def __init__(self, flip=False):
        super().__init__(animate=False)
        self.flip = flip
        self.set_size_request(12, 14)
        self.set_halign(Gtk.Align.CENTER)

    def paint(self, cr, w, h, t):
        cx, cy = w / 2, h / 2
        cr.move_to(cx, cy - 5.5)
        cr.line_to(cx + 4, cy)
        cr.line_to(cx, cy + 5.5)
        cr.line_to(cx - 4, cy)
        cr.close_path()
        src(cr, DEEP, 1)
        cr.fill_preserve()
        src(cr, GOLD, .95)
        cr.set_line_width(1.2)
        cr.stroke()
        star4(cr, cx, cy, 2.4, .35)
        src(cr, CREAM, 1)
        cr.fill()


def genshin_scroll(child, margin_end=6):
    """Wrap `child` in a scroller with a Genshin rail (◆ │ ▮ │ ◆). Returns (outer, scrolled_window)."""
    sc = Gtk.ScrolledWindow()
    cls(sc, "gscroll-win")
    sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.EXTERNAL)
    sc.set_shadow_type(Gtk.ShadowType.NONE)
    sc.set_hexpand(True)
    sc.set_vexpand(True)
    child.set_margin_end(margin_end)
    sc.add(child)

    adj = sc.get_vadjustment()
    bar = Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL, adjustment=adj)
    cls(bar, "gscroll")
    top, bot = ScrollCap(), ScrollCap(flip=True)
    rail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    rail.set_margin_start(6)
    rail.pack_start(top, False, False, 0)
    rail.pack_start(bar, True, True, 0)
    rail.pack_start(bot, False, False, 0)

    outer = Gtk.Box(spacing=0)
    outer.pack_start(sc, True, True, 0)
    outer.pack_start(rail, False, False, 0)
    state = {"need": None, "top": None, "bot": None}

    def sync(*_):
        need = adj.get_upper() - adj.get_page_size() > 1
        if need != state["need"]:
            state["need"] = need
            rail.set_no_show_all(True)
            rail.set_visible(need)
            if need:
                rail.show_all()
        if need:                                       # only touch opacity when it changes
            ta = .35 if adj.get_value() <= adj.get_lower() + 1 else 1.0
            ba = .35 if adj.get_value() >= adj.get_upper() - adj.get_page_size() - 1 else 1.0
            if ta != state["top"]:
                state["top"] = ta
                top.set_opacity(ta)
            if ba != state["bot"]:
                state["bot"] = ba
                bot.set_opacity(ba)

    adj.connect("changed", sync)
    adj.connect("value-changed", sync)
    GLib.idle_add(sync)
    return outer, sc


def wheel_passthrough(widget, sc):
    """Make the mouse wheel over sliders / spin-buttons / combos scroll the page; Ctrl+wheel still edits."""
    def on_scroll(w, ev):
        if ev.state & Gdk.ModifierType.CONTROL_MASK:
            return False
        adj = sc.get_vadjustment()
        if ev.direction == Gdk.ScrollDirection.UP:
            d = -1
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            d = 1
        elif ev.direction == Gdk.ScrollDirection.SMOOTH:
            ok, dx, dy = ev.get_scroll_deltas()
            d = dy
        else:
            return True
        lo, hi = adj.get_lower(), adj.get_upper() - adj.get_page_size()
        adj.set_value(max(lo, min(hi, adj.get_value() + d * 64)))
        return True
    widget.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
    widget.connect("scroll-event", on_scroll)
    return widget


class Page(Gtk.Box):
    def __init__(self, title, subtitle=""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for m in ("top", "bottom", "start", "end"):
            getattr(self, "set_margin_" + m)(18)
        self.title = cls(Gtk.Label(xalign=0), "page-title")
        self.title.set_text(title)
        self.subtitle = cls(Gtk.Label(xalign=0), "page-sub")
        self.subtitle.set_markup(subtitle)
        self.subtitle.set_line_wrap(True)
        self.pack_start(self.title, False, False, 0)
        self.pack_start(self.subtitle, False, False, 0)
        self.pack_start(Ornament(), False, False, 2)



# ══════════════════════════════════════════════════ Companions page ═══
STATUS_WORD = {"connected": "◆ Resonating", "paired": "◇ Bonded", "new": "· Wandering"}


class DeviceRow(Gtk.ListBoxRow):
    def __init__(self, win, path):
        super().__init__()
        self.win, self.path = win, path
        cls(self, "devrow")
        card = cls(Gtk.Box(spacing=12), "card")
        self.card = card
        self.icon = DeviceIcon(66)
        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        self.name = cls(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END), "card-title")
        self.sub = cls(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END), "card-sub")
        meta = Gtk.Box(spacing=8)
        self.batt = cls(Gtk.Label(xalign=0), "card-meta")
        self.sig = LeyLineBar(70, 12)
        self.sig_lbl = cls(Gtk.Label(xalign=0), "card-meta")
        meta.pack_start(self.batt, False, False, 0)
        meta.pack_start(self.sig, False, False, 0)
        meta.pack_start(self.sig_lbl, False, False, 0)
        mid.pack_start(self.name, False, False, 0)
        mid.pack_start(self.sub, False, False, 0)
        mid.pack_start(meta, False, False, 0)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        self.stars = Gtk.Label(xalign=1)
        self.btn = cls(Gtk.Button(), "gbtn", "small")
        self.btn.connect("clicked", lambda *_: self.win.quick_action(self.path))
        right.pack_start(self.stars, False, False, 0)
        right.pack_start(self.btn, False, False, 0)
        card.pack_start(self.icon, False, False, 0)
        card.pack_start(mid, True, True, 0)
        card.pack_start(right, False, False, 0)
        self.add(card)
        self._last = None

    def refresh(self, d):
        busy = self.path in self.win.busy
        lvl, word = ley_line(d.rssi)
        sig = (d.alias, d.state, d.element, d.label, d.battery, lvl, d.rssi is None, d.rarity, busy,
               d.kind, CONFIG.battery_alert)
        if sig == self._last:          # RSSI wobble that doesn't change anything visible -> no work
            return
        self._last = sig
        self.name.set_text(d.alias)
        self.sub.set_markup("<span foreground='%s'>%s</span> · %s · %s" % (hexs(d.color), d.element, d.label,
                                                                           STATUS_WORD[d.state]))
        self.batt.set_text("⚡ %d%%" % d.battery if d.battery is not None else "")
        self.batt.set_visible(d.battery is not None)
        self.sig.level = lvl
        self.sig.set_visible(d.rssi is not None)
        self.sig_lbl.set_text(word if d.rssi is not None else "")
        self.stars.set_markup("<span foreground='%s'>%s</span>" % (hexs(RARITY[d.rarity]), "★" * d.rarity))
        self.icon.update(d.kind, d.color, d.state, d.battery, busy)
        self.btn.set_label({"connected": "Sever", "paired": "Resonate", "new": "Forge pact"}[d.state])
        self.btn.set_sensitive(not busy)
        (cls if d.connected else uncls)(self.card, "connected")
        (cls if d.battery is not None and d.battery <= CONFIG.battery_alert else uncls)(self.card, "low")


class DetailPanel(Gtk.Stack):
    """Character-sheet style detail for one device."""

    def __init__(self, win):
        super().__init__()
        self.win, self.path, self._upd, self._uuids = win, None, False, None
        self.set_transition_type(Gtk.StackTransitionType.NONE)       # instant — fades cost a lot here
        self.set_hexpand(True)
        cls(self, "panel")

        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER)
        ic = DeviceIcon(180)
        ic.update("generic", GOLD, "paired")         # a still picture: nothing animates while you browse
        lb = Gtk.Label(justify=Gtk.Justification.CENTER)
        lb.set_markup("<span size='large' weight='bold'>Choose a companion</span>\n"
                      "<span alpha='60%'>…to read their entry in the Archive</span>")
        empty.pack_start(ic, False, False, 0)
        empty.pack_start(lb, False, False, 0)
        self.add_named(empty, "empty")

        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_end(8)
        sc.add(box)
        self.add_named(sc, "dev")

        hero = Gtk.Box(spacing=20)
        self.icon = DeviceIcon(200)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        self.stars = Gtk.Label(xalign=0)
        self.title = cls(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END), "detail-title")
        self.elem = Gtk.Label(xalign=0)
        sigrow = Gtk.Box(spacing=10)
        self.sig = LeyLineBar(140, 20)
        self.sig_lbl = cls(Gtk.Label(xalign=0), "dim")
        sigrow.pack_start(self.sig, False, False, 0)
        sigrow.pack_start(self.sig_lbl, False, False, 0)
        self.energy = Gtk.Label(xalign=0)
        for w in (self.stars, self.title, self.elem, sigrow, self.energy):
            info.pack_start(w, False, False, 0)
        hero.pack_start(self.icon, False, False, 0)
        hero.pack_start(info, True, True, 0)
        box.pack_start(hero, False, False, 0)

        acts = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6,
                           column_spacing=8, row_spacing=8, homogeneous=False)
        self.b_conn = gbtn("◎  Resonate", lambda: self.win.quick_action(self.path))
        self.b_pair = gbtn("✦  Forge pact", lambda: self.win.pair_dev(self.path))
        self.b_audio = gbtn("♫  Voice & volume", lambda: self.win.open_echoes(self.path), "dark")
        self.b_send = gbtn("✉  Send offering", lambda: self.win.open_transmission(self.path), "dark")
        self.b_copy = gbtn("⧉  Copy address", self._copy, "dark")
        self.b_forget = gbtn("⊗  Forget", lambda: self.win.forget_dev(self.path), "danger")
        for b in (self.b_conn, self.b_pair, self.b_audio, self.b_send, self.b_copy, self.b_forget):
            acts.add(b)
        box.pack_start(acts, False, False, 0)

        box.pack_start(section("BESTOW A NAME"), False, False, 4)
        rn = Gtk.Box(spacing=8)
        self.e_alias = Gtk.Entry(hexpand=True, placeholder_text="A new name for this companion…")
        self.e_alias.connect("activate", lambda *_: self._rename())
        rn.pack_start(self.e_alias, True, True, 0)
        rn.pack_start(gbtn("✎  Rename", self._rename, "dark"), False, False, 0)
        box.pack_start(rn, False, False, 0)

        box.pack_start(section("FORM · HOW THE ARCHIVE SEES IT"), False, False, 4)
        fr = Gtk.Box(spacing=10)
        self.form = Gtk.ComboBoxText()
        self.form.append("auto", "✦  Auto-detect")
        for k in KIND_ORDER:
            self.form.append(k, "%s  ·  %s" % (KINDS[k][0], KINDS[k][1]))
        self.form.connect("changed", self._form_changed)
        wheel_passthrough(self.form, sc)
        self.form_hint = cls(Gtk.Label(xalign=0), "dim")
        self.form_hint.set_line_wrap(True)
        fr.pack_start(self.form, False, False, 0)
        fr.pack_start(self.form_hint, True, True, 0)
        box.pack_start(fr, False, False, 0)

        box.pack_start(section("BLESSINGS"), False, False, 4)
        sw = Gtk.Grid(column_spacing=14, row_spacing=8)
        self.switches = {}
        for i, (prop, label, hint) in enumerate((
                ("Trusted", "Trusted", "auto-accept connections & services"),
                ("Blocked", "Sealed", "refuse all connections"),
                ("WakeAllowed", "May wake the system", "keyboard / mouse wake-up"))):
            s = Gtk.Switch(valign=Gtk.Align.CENTER)
            s.connect("notify::active", self._toggled, prop)
            l = Gtk.Label(xalign=0)
            l.set_markup("%s  <span size='small' alpha='55%%'>%s</span>" % (label, esc(hint)))
            sw.attach(s, 0, i, 1, 1)
            sw.attach(l, 1, i, 1, 1)
            self.switches[prop] = s
        box.pack_start(sw, False, False, 0)

        box.pack_start(section("ARCHIVE ENTRY"), False, False, 4)
        self.grid = Gtk.Grid(column_spacing=18, row_spacing=5)
        self.vals = {}
        for i, k in enumerate(("Address", "Status", "Element", "Energy", "Ley Line", "Tx Power", "Class",
                               "Appearance", "Modalias", "Pairing", "Bonded", "Services", "Adapter", "Object")):
            kl = cls(Gtk.Label(label=k, xalign=0), "k")
            vl = cls(Gtk.Label(xalign=0, selectable=True, ellipsize=Pango.EllipsizeMode.MIDDLE), "v")
            self.grid.attach(kl, 0, i, 1, 1)
            self.grid.attach(vl, 1, i, 1, 1)
            self.vals[k] = vl
        box.pack_start(self.grid, False, False, 0)

        box.pack_start(section("TALENTS · SERVICES"), False, False, 4)
        self.svc = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=2,
                               column_spacing=8, row_spacing=4, homogeneous=True)
        box.pack_start(self.svc, False, False, 0)

    def show_device(self, path):
        self.path, self._uuids = path, None
        if self.win.devs.get(path):
            self.e_alias.set_text("")
        self.refresh()

    def refresh(self, d=None):
        d = d or self.win.devs.get(self.path)
        if not d:
            self.set_visible_child_name("empty")
            return
        self.set_visible_child_name("dev")
        self._upd = True
        busy = self.path in self.win.busy
        self.icon.update(d.kind, d.color, d.state, d.battery, busy)
        rc = hexs(RARITY[d.rarity])
        self.stars.set_markup("<span foreground='%s' size='large'>%s</span>" % (rc, "★" * d.rarity))
        self.title.set_text(d.alias)
        self.elem.set_markup("<span foreground='%s' weight='bold'>%s</span>  ·  %s  ·  <span alpha='70%%'>%s</span>"
                             % (hexs(d.color), d.element, d.label, STATUS_WORD[d.state]))
        lvl, word = ley_line(d.rssi)
        self.sig.level, self.sig.col = lvl, d.color
        self.sig_lbl.set_text("Ley Line · %s%s" % (word, (" (%d dBm)" % d.rssi) if d.rssi is not None else
                                                   "  — use Elemental Sight to measure"))
        if d.battery is not None:
            col = "#A5C83B" if d.battery > 50 else ("#F2B723" if d.battery > 20 else "#EF7A35")
            self.energy.set_markup("<span foreground='%s' weight='bold'>⚡ Energy %d%%</span>" % (col, d.battery))
        else:
            self.energy.set_markup("<span alpha='50%'>⚡ Energy unknown (no Battery1 reported)</span>")
        self.b_conn.set_label("⊗  Sever resonance" if d.connected else "◎  Resonate")
        show_widget(self.b_conn, d.paired or d.connected)
        show_widget(self.b_pair, not d.paired)
        show_widget(self.b_audio, d.audio and (d.paired or d.connected))
        show_widget(self.b_send, any(u.lower().startswith("00001105") for u in d.uuids)
                    or d.kind in ("phone", "computer", "tablet"))
        for b in (self.b_conn, self.b_pair, self.b_forget):
            b.set_sensitive(not busy)
        self.form.set_active_id(d.kind if d.overridden else "auto")
        self.form_hint.set_markup("detected as <b>%s</b>%s" % (
            esc(KINDS[d.auto_kind][0]),
            "  ·  <span foreground='#D3BC8E'>your choice wins</span>" if d.overridden
            else "  ·  <span alpha='70%'>wrong guess? pick the right form</span>"))
        self.switches["Trusted"].set_active(d.trusted)
        self.switches["Blocked"].set_active(d.blocked)
        self.switches["WakeAllowed"].set_active(bool(d.wake))
        self.switches["WakeAllowed"].set_sensitive(d.wake is not None)
        v = self.vals
        v["Address"].set_text(d.address)
        v["Status"].set_text(", ".join(x for x, c in (("connected", d.connected), ("paired", d.paired),
                                                       ("trusted", d.trusted), ("blocked", d.blocked)) if c) or "unknown")
        v["Element"].set_text("%s · %s · %d★" % (d.element, d.label, d.rarity))
        v["Energy"].set_text("%d%%" % d.battery if d.battery is not None else "—")
        v["Ley Line"].set_text("%s (%s dBm)" % (word, d.rssi) if d.rssi is not None else "—")
        v["Tx Power"].set_text("%s dBm" % d.txpower if d.txpower is not None else "—")
        v["Class"].set_text("0x%06x" % d.cls if d.cls else "—")
        v["Appearance"].set_text("0x%04x" % d.appearance if d.appearance else "—")
        v["Modalias"].set_text(d.modalias or "—")
        v["Pairing"].set_text("—" if d.legacy is None else ("Legacy PIN" if d.legacy else "Secure Simple Pairing"))
        v["Bonded"].set_text("—" if d.bonded is None else ("yes" if d.bonded else "no"))
        v["Services"].set_text("—" if d.resolved is None else ("resolved" if d.resolved else "pending"))
        v["Adapter"].set_text(os.path.basename(d.adapter or "—"))
        v["Object"].set_text(d.path)
        if tuple(d.uuids) != self._uuids:
            self._uuids = tuple(d.uuids)
            for c in self.svc.get_children():
                c.destroy()
            for u in sorted(d.uuids, key=lambda u: uuid_name(u)[0]):
                name, short = uuid_name(u)
                l = cls(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END), "talent")
                l.set_markup("<span foreground='#D3BC8E'>✦</span> %s <span size='small' alpha='45%%'>%s</span>"
                             % (esc(name), esc(short)))
                l.set_tooltip_text(u)
                self.svc.add(l)
            if not d.uuids:
                self.svc.add(cls(Gtk.Label(label="No talents revealed yet", xalign=0), "dim"))
            self.svc.show_all()
        self._upd = False

    def _toggled(self, sw, _p, prop):
        if self._upd or not self.path:
            return
        val = sw.get_active()

        def done(ok, err, _v):
            if not ok:
                self.win.toast("Blessing failed", err, "err")
                self.refresh()
        self.win.bz.set_prop(self.path, DEVICE, prop, GLib.Variant("b", val), done)

    def _form_changed(self, combo):
        if self._upd or not self.path:
            return
        d = self.win.devs.get(self.path)
        if not d:
            return
        kid = combo.get_active_id() or "auto"
        ov = dict(CONFIG.kind_overrides or {})
        if kid == "auto" or kid == d.auto_kind:
            ov.pop(d.address.upper(), None)
        else:
            ov[d.address.upper()] = kid
        CONFIG.kind_overrides = ov
        self.win.reclassify(self.path)
        nd = self.win.devs.get(self.path)
        if nd:
            self.win.toast("A new form ✦", "%s · %s · %s" % (nd.alias, nd.label, nd.element), "ok")

    def _rename(self):
        txt = self.e_alias.get_text().strip()
        if txt and self.path:
            self.win.bz.set_prop(self.path, DEVICE, "Alias", GLib.Variant("s", txt),
                                 lambda ok, err, _v: self.win.toast("Name bestowed ✎" if ok else "Rename failed",
                                                                    txt if ok else err, "ok" if ok else "err"))
            self.e_alias.set_text("")

    def _copy(self):
        d = self.win.devs.get(self.path)
        if d:
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(d.address, -1)
            self.win.toast("Address copied", d.address, "ok")


class CompanionsPage(Page):
    def __init__(self, win):
        super().__init__("Companions", "")
        self.win = win
        tools = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry(placeholder_text="Search the Archive…  (Ctrl+F)")
        self.search.set_size_request(260, -1)
        self.search.connect("search-changed", lambda *_: self.listbox.invalidate_filter())
        tools.pack_start(self.search, False, False, 0)
        self.mode = "all"
        group = None
        for key, label in (("all", "All"), ("connected", "◆ Resonating"), ("paired", "◇ Bonded"), ("new", "· Wandering")):
            b = Gtk.RadioButton.new_from_widget(group)
            b.set_label(label)
            b.set_mode(False)
            cls(b, "chip")
            group = group or b
            b.connect("toggled", self._mode, key)
            tools.pack_start(b, False, False, 0)
        tools.pack_end(gbtn("◈  Elemental Sight", self.win.toggle_scan, "small"), False, False, 0)
        self.pack_start(tools, False, False, 0)

        body = Gtk.Box(spacing=16)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_size_request(470, -1)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_sort_func(self._sort)
        self.listbox.set_filter_func(self._filter)
        self.listbox.connect("row-selected", self._selected)
        ph = Gtk.Label(justify=Gtk.Justification.CENTER)
        ph.set_markup("<span size='large'>No companions here</span>\n"
                      "<span alpha='60%'>Use ◈ Elemental Sight (F5) to search for nearby devices</span>")
        ph.show()
        self.listbox.set_placeholder(ph)
        sc.add(self.listbox)
        body.pack_start(sc, False, False, 0)
        self.detail = DetailPanel(win)
        body.pack_start(self.detail, True, True, 0)
        self.pack_start(body, True, True, 0)

    def _mode(self, b, key):
        if b.get_active():
            self.mode = key
            self.listbox.invalidate_filter()

    def _sort(self, r1, r2, *_):
        d1, d2 = self.win.devs.get(r1.path), self.win.devs.get(r2.path)
        if not d1 or not d2:
            return 0
        k1 = (d1.rank, -(d1.rssi or -999) if d1.rank == 2 else 0, d1.alias.lower())
        k2 = (d2.rank, -(d2.rssi or -999) if d2.rank == 2 else 0, d2.alias.lower())
        return (k1 > k2) - (k1 < k2)

    def _filter(self, row, *_):
        d = self.win.devs.get(row.path)
        if not d:
            return False
        if d.nameless and not d.paired and not CONFIG.show_nameless:
            return False
        if self.mode != "all" and d.state != self.mode:
            return False
        q = self.search.get_text().strip().lower()
        return not q or q in ("%s %s %s %s" % (d.alias, d.address, d.label, d.element)).lower()

    def _selected(self, lb, row):
        if row is not None:
            self.detail.show_device(row.path)


# ════════════════════════════════════════════════ Ley Line Atlas ═══════
class Radar(AnimatedArea):
    CACHE = False

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.pos, self.hits, self.selected = {}, [], None
        self._ang = {}
        self._grid = None
        self._gkey = None
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._click)

    def request_draw(self):       # the corners of the widget are empty -> repaint just the radar disc
        a = self.get_allocation()
        w, h = a.width, a.height
        R = max(40, min(w, h) / 2 - 36) + 40
        self.queue_draw_area(int(w / 2 - R), int(h / 2 - R), int(2 * R), int(2 * R))

    def _click(self, w, ev):
        best, bd = None, 26 ** 2
        for x, y, path in self.hits:
            dd = (x - ev.x) ** 2 + (y - ev.y) ** 2
            if dd < bd:
                best, bd = path, dd
        self.selected = best
        self.win.atlas.show_info(best)
        return True

    def _grid_layer(self, R):
        sc = max(1, self.get_scale_factor())
        key = (round(R, 1), sc)
        if self._grid is None or self._gkey != key:
            side = 2 * R + 4

            def p(c):
                g = cairo.RadialGradient(0, 0, 0, 0, 0, R)
                g.add_color_stop_rgba(0, .1, .13, .2, .55)
                g.add_color_stop_rgba(1, .05, .06, .1, .25)
                c.set_source(g)
                c.new_sub_path()
                c.arc(0, 0, R, 0, 2 * math.pi)
                c.fill()
                for i, name in enumerate(("Resonant", "Strong", "Steady", "Faint", "Fading")):
                    r = R * (i + 1) / 5
                    c.new_sub_path()
                    c.arc(0, 0, r, 0, 2 * math.pi)
                    c.set_line_width(1)
                    src(c, GOLD, .14 + .12 * (i == 4))
                    c.stroke()
                    draw_text(c, name, 6, -r + 9, 7, GOLD, .45, align="left")
                for k in range(12):
                    a = k * math.pi / 6
                    c.move_to(math.cos(a) * R * .2, math.sin(a) * R * .2)
                    c.line_to(math.cos(a) * R, math.sin(a) * R)
                src(c, GOLD, .06)
                c.stroke()
            self._grid, self._gkey = make_surface(side, sc, p), key
        return self._grid, 2 * R + 4

    def paint(self, cr, w, h, t):
        cx, cy = w / 2, h / 2
        R = max(40, min(w, h) / 2 - 36)
        ap = self.win.bz.adapter_props()
        powered, disc = bool(ap.get("Powered")), bool(ap.get("Discovering"))
        grid, side = self._grid_layer(R)
        cr.save()
        cr.translate(cx, cy)
        blit(cr, grid, side)
        cr.restore()
        sweep = (t * 1.1) % (2 * math.pi)
        an = ELEMENTS["Anemo"]
        if powered:
            for k in range(10):
                a1 = sweep - k * .08
                cr.move_to(cx, cy)
                cr.arc(cx, cy, R, a1 - .082, a1)
                cr.close_path()
                src(cr, an, (.2 if disc else .08) * (1 - k / 10))
                cr.fill()
            cr.move_to(cx, cy)
            cr.line_to(cx + math.cos(sweep) * R, cy + math.sin(sweep) * R)
            cr.set_line_width(1.5)
            src(cr, an, .75 if disc else .3)
            cr.stroke()
        draw_adapter_emblem(cr, cx, cy, min(36, R * .18), t, "scan" if disc else ("on" if powered else "off"))
        self.hits = []
        for path, d in list(self.win.devs.items()):
            if d.rssi is None and not d.connected:
                continue
            if d.nameless and not d.paired and not CONFIG.show_nameless:
                continue
            ang = self._ang.get(d.address)
            if ang is None:
                ang = self._ang[d.address] = (int(hashlib.md5(d.address.encode()).hexdigest()[:6], 16) % 3600) / 3600 * 2 * math.pi
            target = max(.3, min(1, (-d.rssi - 30) / 70.0)) if d.rssi is not None else .3
            cur = self.pos.get(path, target)
            cur += (target - cur) * .08
            self.pos[path] = cur
            x, y = cx + math.cos(ang) * R * cur, cy + math.sin(ang) * R * cur
            diff = (sweep - ang) % (2 * math.pi)
            flash = max(0, 1 - diff / .9) if powered else 0
            rg = cairo.RadialGradient(x, y, 0, x, y, 30)
            rg.add_color_stop_rgba(0, d.color[0], d.color[1], d.color[2], .5 * (.4 + flash))
            rg.add_color_stop_rgba(1, d.color[0], d.color[1], d.color[2], 0)
            cr.set_source(rg)
            cr.new_sub_path()
            cr.arc(x, y, 30, 0, 2 * math.pi)
            cr.fill()
            draw_device_emblem(cr, d.kind, x, y, 34 + 8 * d.connected, t, d.color, d.state, None, False, False)
            if path == self.selected:
                cr.save()
                cr.translate(x, y)
                cr.rotate(t)
                cr.set_dash([4, 4])
                cr.new_sub_path()
                cr.arc(0, 0, 26, 0, 2 * math.pi)
                cr.set_line_width(1.5)
                src(cr, GOLD, .9)
                cr.stroke()
                cr.restore()
            draw_text(cr, d.alias[:22], x, y + 28, 8, CREAM, .75 + .25 * flash)
            self.hits.append((x, y, path))


class AtlasPage(Page):
    def __init__(self, win):
        super().__init__("Ley Line Atlas",
                         "Live signal radar — the closer to the Statue, the stronger the Ley Line. "
                         "<span alpha='60%'>RSSI flows only during Elemental Sight.</span>")
        self.win = win
        self.radar = Radar(win)
        frame = cls(Gtk.Box(), "panel")
        frame.pack_start(self.radar, True, True, 0)
        self.pack_start(frame, True, True, 0)
        bar = Gtk.Box(spacing=12)
        self.info = Gtk.Label(xalign=0, hexpand=True)
        self.info.set_markup("<span alpha='60%'>Click a companion on the radar…</span>")
        self.b_act = gbtn("◎  Resonate", self._act)
        self.b_view = gbtn("✦  Open entry", self._view, "dark")
        self.b_act.set_no_show_all(True)
        self.b_view.set_no_show_all(True)
        bar.pack_start(self.info, True, True, 0)
        bar.pack_end(gbtn("◈  Elemental Sight", self.win.toggle_scan), False, False, 0)
        bar.pack_end(self.b_view, False, False, 0)
        bar.pack_end(self.b_act, False, False, 0)
        self.pack_start(bar, False, False, 0)
        self.sel = None

    def show_info(self, path):
        self.sel = path
        d = self.win.devs.get(path) if path else None
        if not d:
            self.info.set_markup("<span alpha='60%'>Click a companion on the radar…</span>")
            self.b_act.hide()
            self.b_view.hide()
            return
        lvl, word = ley_line(d.rssi)
        self.info.set_markup("<b>%s</b>  <span foreground='%s'>%s</span> · %s · Ley Line <b>%s</b>%s"
                             % (esc(d.alias), hexs(d.color), d.element, d.label, word,
                                (" (%d dBm)" % d.rssi) if d.rssi is not None else ""))
        self.b_act.set_label({"connected": "⊗  Sever", "paired": "◎  Resonate", "new": "✦  Forge pact"}[d.state])
        self.b_act.show()
        self.b_view.show()

    def _act(self):
        if self.sel:
            self.win.quick_action(self.sel)

    def _view(self):
        if self.sel:
            self.win.select_device(self.sel)



# ═══════════════════════════════════════════════════ Echoing Conch ═════
def profile_label(pid, p):
    """What the audio server itself calls this voice — no codec guessing."""
    desc = (p.get("description") or pid).strip()
    low = pid.lower()
    if low == "off":
        glyph = "⊘"
    elif "a2dp" in low or "high" in desc.lower():
        glyph = "♫"
    elif any(k in low for k in ("headset", "hfp", "hsp", "handsfree")):
        glyph = "☏"
    else:
        glyph = "✦"
    return "%s  %s" % (glyph, desc)


class EchoCard(Gtk.Box):
    """One Bluetooth voice: volume, mute, voice (card profile), routing, chime."""

    def __init__(self, page, mac):
        super().__init__(spacing=16)
        cls(self, "card", "echo")
        self.page, self.win, self.mac = page, page.win, mac
        self.sink, self.card = None, None
        self._upd, self._user_t, self._vol_src, self._prof_ids = False, -99.0, 0, None
        self.icon = DeviceIcon(84)
        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        top = Gtk.Box(spacing=10)
        self.title = cls(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END), "card-title")
        self.badge = cls(Gtk.Label(xalign=0), "badge")
        top.pack_start(self.title, False, False, 0)
        top.pack_start(self.badge, False, False, 0)
        self.sub = cls(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END), "card-sub")
        vol = Gtk.Box(spacing=10)
        self.mute = cls(Gtk.ToggleButton(label="♪"), "gbtn", "dark", "small", "mute")
        self.mute.set_tooltip_text("Silence / restore this voice")
        self.mute.connect("toggled", self._mute)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.scale.set_draw_value(False)
        self.scale.add_mark(100, Gtk.PositionType.BOTTOM, None)
        self.scale.set_hexpand(True)
        self.scale.set_size_request(240, -1)
        self.scale.connect("value-changed", self._vol)
        wheel_passthrough(self.scale, page.scroller)
        self.vol_lbl = cls(Gtk.Label(xalign=1, width_chars=5), "v")
        vol.pack_start(self.mute, False, False, 0)
        vol.pack_start(self.scale, True, True, 0)
        vol.pack_start(self.vol_lbl, False, False, 0)
        prof = Gtk.Box(spacing=10)
        prof.pack_start(cls(Gtk.Label(label="VOICE", xalign=0), "when"), False, False, 0)
        self.profile = Gtk.ComboBoxText()
        self.profile.set_size_request(330, -1)
        self.profile.connect("changed", self._profile)
        wheel_passthrough(self.profile, page.scroller)
        prof.pack_start(self.profile, False, False, 0)
        for w in (top, self.sub, vol, prof):
            mid.pack_start(w, False, False, 0)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, valign=Gtk.Align.CENTER)
        self.b_sing = gbtn("♫  Sing here", self._sing, "small")
        self.b_sing.set_tooltip_text("Make this the default output and move everything that plays onto it")
        self.b_chime = gbtn("♪  Chime", self._chime, "dark", "small")
        self.b_chime.set_tooltip_text("Play a short test sound on this companion only")
        self.b_sever = gbtn("⊗  Sever", self._sever, "dark", "small")
        for b in (self.b_sing, self.b_chime, self.b_sever):
            right.pack_start(b, False, False, 0)
        self.pack_start(self.icon, False, False, 0)
        self.pack_start(mid, True, True, 0)
        self.pack_start(right, False, False, 0)

    def update(self, d, card, sink, default):
        self._upd = True
        self.card, self.sink = card, sink
        if d:
            self.icon.update(d.kind, d.color, d.state, d.battery)
            alias, el, col, label = d.alias, d.element, d.color, d.label
        else:
            desc = ((card or {}).get("properties") or {}).get("device.description") or (sink or {}).get("desc") or self.mac
            self.icon.update("headphones", ELEMENTS["Hydro"], "connected")
            alias, el, col, label = desc, "Hydro", ELEMENTS["Hydro"], "Voice"
        singing = bool(sink and sink["name"] == default)
        self.title.set_text(alias)
        if singing:
            self.badge.set_markup("<span foreground='#5CD8B8'>◆ singing now</span>")
        elif sink:
            self.badge.set_markup("<span alpha='70%'>◇ waiting</span>")
        else:
            self.badge.set_markup("<span foreground='#F2B723'>⊘ voiceless</span>")
        bits = ["<span foreground='%s'>%s</span> · %s" % (hexs(col), el, esc(label))]
        if d and d.battery is not None:
            bits.append("⚡ %d%%" % d.battery)
        if sink and sink.get("state") == "running":
            bits.append("♫ playing")
        if not sink:
            bits.append("this voice has no output — pick a ♫ voice below" if card else
                        "the audio server hasn't seen it yet")
        self.sub.set_markup("  ·  ".join(bits))
        (cls if singing else uncls)(self, "singing")
        has = sink is not None
        for w in (self.scale, self.mute, self.b_chime):
            w.set_sensitive(has)
        if has:
            if now_t() - self._user_t > 1.5:          # never fight the user's hand on the slider
                self.scale.set_value(sink["vol"])
                self.vol_lbl.set_text("%d%%" % sink["vol"])
            self.mute.set_active(sink["mute"])
            self.mute.set_label("⊘" if sink["mute"] else "♪")
        else:
            self.vol_lbl.set_text("—")
        self.b_sing.set_sensitive(has and not singing)
        self.b_sing.set_label("◆  Singing" if singing else "♫  Sing here")
        self.b_sever.set_visible(bool(d and d.connected))
        profiles = (card or {}).get("profiles") or {}
        active = (card or {}).get("active_profile") or ""
        items = []
        for pid, p in sorted(profiles.items(), key=lambda kv: (kv[0] == "off", -int(kv[1].get("priority", 0) or 0))):
            if p.get("available", True) is False and pid != active:
                continue
            items.append((pid, profile_label(pid, p)))
        ids = tuple(items)
        if ids != self._prof_ids:
            self._prof_ids = ids
            self.profile.remove_all()
            for pid, lab in items:
                self.profile.append(pid, lab)
        self.profile.set_sensitive(bool(items) and card is not None)
        if active:
            self.profile.set_active_id(active)
        self._upd = False

    # ── handlers
    def _vol(self, s):
        if self._upd or not self.sink:
            return
        v = int(round(s.get_value()))
        self.vol_lbl.set_text("%d%%" % v)
        self._user_t = now_t()
        if self._vol_src:
            GLib.source_remove(self._vol_src)
        self._vol_src = GLib.timeout_add(70, self._apply_vol)

    def _apply_vol(self):
        self._vol_src = 0
        if not self.sink:
            return False
        v = int(round(self.scale.get_value()))
        run_async(["pactl", "set-sink-volume", self.sink["name"], "%d%%" % v])
        if CONFIG.remember_volume:
            vols = dict(CONFIG.volumes or {})
            vols[self.mac] = v
            CONFIG.volumes = vols
        return False

    def _mute(self, b):
        if self._upd or not self.sink:
            return
        on = b.get_active()
        b.set_label("⊘" if on else "♪")
        run_async(["pactl", "set-sink-mute", self.sink["name"], "1" if on else "0"])

    def _profile(self, combo):
        if self._upd or not self.card:
            return
        pid = combo.get_active_id()
        if not pid or pid == self.card.get("active_profile"):
            return

        def done(ok, out):
            if ok:
                self.win.toast("A new voice ✦", combo.get_active_text() or pid, "ok")
            else:
                self.win.toast("The voice would not change", out.strip()[:160] or pid, "err")
            self.page.schedule_refresh(300)
        run_async(["pactl", "set-card-profile", self.card.get("name", ""), pid], done)

    def _sing(self):
        name = self.title.get_text()

        def done(ok, msg):
            self.win.toast(("♫ %s sings now" % name) if ok else "Routing failed", msg, "ok" if ok else "err")
            self.page.schedule_refresh(150)
        route_audio(self.mac, done, tries=2)

    def _chime(self):
        if self.sink:
            play_chime(self.sink["name"], lambda ok, msg: ok or self.win.toast("No chime", msg, "warn"))

    def _sever(self):
        d = self.win.dev_by_mac(self.mac)
        if d:
            self.win.dev_call(d.path, "Disconnect")

    def flash(self):
        cls(self, "focus")
        later(1600, uncls, self, "focus")


class EchoesPage(Page):
    """♫ Echoing Conch — the Bluetooth audio centre."""

    def __init__(self, win):
        super().__init__("Echoing Conch",
                         "Every Bluetooth voice in one place — who sings, how loud, and in which voice. "
                         "<span alpha='60%'>Live from PipeWire / PulseAudio.</span>")
        self.win, self.cards, self.state = win, {}, None
        self._sub, self._ref_src, self._loading, self._again, self._focus = None, 0, False, False, None
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer, self.scroller = genshin_scroll(body)

        now = cls(Gtk.Box(spacing=14), "forge")
        self.now_icon = cls(Gtk.Label(label="♫"), "now-glyph")
        self.now_lbl = Gtk.Label(xalign=0, hexpand=True)
        self.now_lbl.set_line_wrap(True)
        self.now_lbl.set_markup("<span alpha='60%'>Listening to the audio server…</span>")
        now.pack_start(self.now_icon, False, False, 0)
        now.pack_start(self.now_lbl, True, True, 0)
        b = gbtn("⟳  Listen again", self.refresh, "dark", "small")
        b.set_valign(Gtk.Align.CENTER)
        now.pack_end(b, False, False, 0)
        body.pack_start(now, False, False, 0)

        body.pack_start(section("COMPANIONS WITH A VOICE"), False, False, 6)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        body.pack_start(self.list, False, False, 0)
        self.empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.empty.set_margin_top(10)
        self.empty.set_margin_bottom(10)
        ic = DeviceIcon(130)
        ic.update("speaker", ELEMENTS["Pyro"], "paired")
        self.empty_lbl = Gtk.Label(justify=Gtk.Justification.CENTER)
        self.empty_lbl.set_line_wrap(True)
        eb = gbtn("✦  Find a companion", lambda: self.win.goto("companions"), "small")
        eb.set_halign(Gtk.Align.CENTER)
        self.empty.pack_start(ic, False, False, 0)
        self.empty.pack_start(self.empty_lbl, False, False, 0)
        self.empty.pack_start(eb, False, False, 0)
        self.empty.set_no_show_all(True)
        body.pack_start(self.empty, False, False, 0)

        body.pack_start(section("HARMONY · DONE FOR YOU"), False, False, 10)
        g = Gtk.Grid(column_spacing=12, row_spacing=10)
        self.rule_sw = {}
        for row, (key, title, hint) in enumerate((
                ("audio_follow", "Audio follows the companion",
                 "when headphones / a speaker / the TV connects, it becomes the output and playing sound moves to it"),
                ("pause_on_fade", "Pause when it fades",
                 "headphones or earbuds disconnect → every player pauses (needs playerctl), no surprise blast from the speakers"),
                ("remember_volume", "Remember each companion's volume",
                 "the volume you set here is restored every time that companion connects"))):
            s = Gtk.Switch(valign=Gtk.Align.CENTER, active=bool(getattr(CONFIG, key)))
            s.connect("notify::active", lambda sw, _p, k=key: setattr(CONFIG, k, sw.get_active()))
            l = Gtk.Label(xalign=0)
            l.set_markup("%s\n<span size='small' alpha='55%%'>%s</span>" % (esc(title), esc(hint)))
            l.set_line_wrap(True)
            g.attach(s, 0, row, 1, 1)
            g.attach(l, 1, row, 1, 1)
            self.rule_sw[key] = s
        body.pack_start(g, False, False, 0)
        hint = cls(Gtk.Label(xalign=0), "dim")
        hint.set_line_wrap(True)
        hint.set_markup("<span size='small'>These work while the Archive runs. To keep them awake with the window "
                        "closed, turn on <b>Keep running in the background</b> in ⚙ Archive Settings.</span>")
        body.pack_start(hint, False, False, 0)
        self.pack_start(outer, True, True, 0)
        self.connect("map", self._on_map)
        self.connect("unmap", lambda *_: self._stop_sub())

    # ── life cycle
    def _on_map(self, *_):
        for k, s in self.rule_sw.items():
            if s.get_active() != bool(getattr(CONFIG, k)):
                s.set_active(bool(getattr(CONFIG, k)))
        self._start_sub()
        self.refresh()

    def _start_sub(self):
        """`pactl subscribe` streams every change of the audio graph -> the page is live, no polling."""
        if self._sub is not None or not shutil.which("pactl"):
            return
        try:
            proc = Gio.Subprocess.new(["pactl", "subscribe"],
                                      Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error:
            return
        self._sub = proc
        stream = Gio.DataInputStream.new(proc.get_stdout_pipe())

        def got(s, res, *_):
            try:
                line, _n = s.read_line_finish_utf8(res)
            except GLib.Error:
                line = None
            if line is None or self._sub is not proc:
                return
            if ("on card" in line or "on sink #" in line or "on server" in line) and "sink-input" not in line:
                self.schedule_refresh(250)
            s.read_line_async(GLib.PRIORITY_DEFAULT, None, got)
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, got)

    def _stop_sub(self):
        if self._sub is not None:
            try:
                self._sub.force_exit()
            except Exception:
                pass
            self._sub = None

    def schedule_refresh(self, ms=200):
        if not self.get_mapped() or self._ref_src:
            return
        self._ref_src = GLib.timeout_add(ms, self._ref_timer)

    def _ref_timer(self):
        self._ref_src = 0
        self.refresh()
        return False

    def focus(self, mac):
        self._focus = (mac or "").upper()
        c = self.cards.get(self._focus)
        if c:
            c.flash()
            self._focus = None

    # ── data
    def refresh(self):
        if self._loading:
            self._again = True
            return
        self._loading = True
        pulse_snapshot(self._loaded)

    def _loaded(self, st):
        self._loading = False
        if self._again:
            self._again = False
            later(60, self.refresh)
        self.state = st
        if not st["ok"]:
            self.now_icon.set_text("⚠")
            self.now_lbl.set_markup("<span foreground='#F2B723' weight='bold'>The conch is silent</span>\n"
                                    "<span size='small'>%s</span>" % esc(st["err"]))
        else:
            self.now_icon.set_text("♫")
            dbt = next((m for m, s in st["sinks"].items() if s["name"] == st["default"]), None)
            dd = self.win.dev_by_mac(dbt) if dbt else None
            who = dd.alias if dd else (st["default_desc"] or "nothing")
            self.now_lbl.set_markup("<span size='small' alpha='60%%'>NOW SINGING THROUGH</span>\n"
                                    "<span size='large' weight='bold' foreground='%s'>%s</span>%s"
                                    % ("#5CD8B8" if dbt else "#ECE5D8", esc(who),
                                       "" if dbt else "  <span size='small' alpha='55%'>· not Bluetooth</span>"))
        macs = set(st["cards"]) | set(st["sinks"])
        for d in self.win.devs.values():
            if d.connected and d.kind in AUDIO_KINDS:
                macs.add(d.address.upper())
        entries = []
        for mac in macs:
            d = self.win.dev_by_mac(mac)
            sink = st["sinks"].get(mac)
            entries.append((0 if sink and sink["name"] == st["default"] else 1,
                            (d.alias if d else mac).lower(), mac, d, st["cards"].get(mac), sink))
        entries.sort(key=lambda e: e[:2])
        for mac in list(self.cards):
            if mac not in macs:
                self.cards.pop(mac).destroy()
        for i, (_r, _a, mac, d, card, sink) in enumerate(entries):
            c = self.cards.get(mac)
            if c is None:
                c = self.cards[mac] = EchoCard(self, mac)
                self.list.pack_start(c, False, False, 0)
                c.show_all()
            self.list.reorder_child(c, i)
            c.update(d, card, sink, st["default"])
        if entries:
            self.empty.hide()
        else:
            self.empty_lbl.set_markup("<span size='large' weight='bold'>No companion is singing</span>\n"
                                      "<span alpha='60%'>Resonate with headphones, earbuds, a speaker or a TV "
                                      "and its voice appears here.</span>")
            self.empty.show_all()
        if self._focus:
            self.focus(self._focus)



# ═════════════════════════════════════════════════ Transmission ═══════
class DropZone(AnimatedArea):
    """Still unless a file hovers over it — then the dashed border flows."""

    def __init__(self):
        super().__init__()
        self.set_size_request(-1, 120)
        self._hover = False

    def animating(self):
        return self._hover

    @property
    def hover(self):
        return self._hover

    @hover.setter
    def hover(self, v):
        if v != self._hover:
            self._hover = v
            self.redraw()

    def paint(self, cr, w, h, t):
        rrect(cr, 6, 6, w - 12, h - 12, 18)
        src(cr, ELEMENTS["Anemo"] if self._hover else GOLD, .08 if self._hover else .04)
        cr.fill_preserve()
        cr.set_dash([10, 7], -t * 24 if self._hover else 0)
        cr.set_line_width(1.6)
        src(cr, ELEMENTS["Anemo"] if self._hover else GOLD, .8)
        cr.stroke()
        cr.set_dash([])
        y = h / 2 - 12 + (math.sin(t * 2.2) * 4 if self._hover else 0)
        star4(cr, w / 2, y, 14, .25)
        src(cr, GOLD, .95)
        cr.fill()
        draw_text(cr, "Drop files here to send them to the chosen companion", w / 2, h / 2 + 24, 10, CREAM, .8)


class TransmissionPage(Page):
    STATUS = {"summoning": "Opening a Ley Line…", "queued": "Queued", "active": "Flowing",
              "suspended": "Paused", "complete": "Delivered ✦", "error": "Lost in the Abyss"}

    def __init__(self, win):
        super().__init__("Transmission", "Send offerings over OBEX Object Push — or accept them from others.")
        self.win, self.rows, self.queue, self.sending = win, {}, [], False
        top = Gtk.Box(spacing=10)
        self.combo = Gtk.ComboBoxText()
        self.combo.set_size_request(300, -1)
        self.chooser = Gtk.FileChooserButton(title="Choose an offering", action=Gtk.FileChooserAction.OPEN)
        self.chooser.set_size_request(240, -1)
        top.pack_start(cls(Gtk.Label(label="To"), "k"), False, False, 0)
        top.pack_start(self.combo, False, False, 0)
        top.pack_start(self.chooser, False, False, 0)
        top.pack_start(gbtn("✉  Dispatch", self._send_chosen), False, False, 0)
        self.pack_start(top, False, False, 0)
        self.drop = DropZone()
        self.drop.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.drop.drag_dest_add_uri_targets()
        self.drop.connect("drag-data-received", self._dropped)
        self.drop.connect("drag-motion", lambda *a: setattr(self.drop, "hover", True) or False)
        self.drop.connect("drag-leave", lambda *a: setattr(self.drop, "hover", False))
        self.pack_start(self.drop, False, False, 0)
        self.pack_start(section("FLOWING OFFERINGS"), False, False, 4)
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        ph = cls(Gtk.Label(label="Nothing has flowed yet."), "dim")
        ph.show()
        self.list.set_placeholder(ph)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.add(self.list)
        self.pack_start(sc, True, True, 0)
        self.pack_start(section("RECEIVING"), False, False, 4)
        rx = Gtk.Box(spacing=12)
        self.rx_sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.rx_sw.set_active(CONFIG.accept_incoming)
        self.rx_sw.connect("notify::active", self._rx_toggled)
        self.rx_mode = Gtk.ComboBoxText()
        for k, l in (("ask", "Ask every time"), ("trusted", "Auto-accept from trusted"), ("all", "Accept everything")):
            self.rx_mode.append(k, l)
        self.rx_mode.set_active_id(CONFIG.incoming_mode)
        self.rx_mode.connect("changed", lambda c: setattr(CONFIG, "incoming_mode", c.get_active_id()))
        rx.pack_start(self.rx_sw, False, False, 0)
        rx.pack_start(Gtk.Label(label="Accept incoming offerings"), False, False, 0)
        rx.pack_start(self.rx_mode, False, False, 0)
        rx.pack_end(gbtn("▤  Open offerings", self._open_dir, "dark", "small"), False, False, 0)
        self.pack_start(rx, False, False, 0)
        win.obex.connect("transfer", self._on_transfer)

    def refresh_devices(self):
        keep = self.combo.get_active_id()
        self.combo.remove_all()
        devs = sorted((d for d in self.win.devs.values() if d.paired), key=lambda d: (d.rank, d.alias.lower()))
        for d in devs:
            self.combo.append(d.address, "%s  ·  %s" % (d.alias, d.label))
        if keep and any(d.address == keep for d in devs):
            self.combo.set_active_id(keep)
        elif devs:
            self.combo.set_active(0)

    def preselect(self, mac):
        self.refresh_devices()
        self.combo.set_active_id(mac)

    def _send_chosen(self):
        f = self.chooser.get_filename()
        if not f:
            self.win.toast("Choose an offering first", "", "warn")
            return
        self._send([f])

    def _dropped(self, w, ctx, x, y, data, info, tm):
        self.drop.hover = False
        files = []
        for u in data.get_uris() or []:
            try:
                p = GLib.filename_from_uri(u)[0]
                if os.path.isfile(p):
                    files.append(p)
            except Exception:
                pass
        self._send(files)

    def _send(self, files):
        mac = self.combo.get_active_id()
        if not mac:
            self.win.toast("Choose a companion first", "Only bonded companions can receive offerings", "warn")
            return
        for f in files:
            self.queue.append((mac, f))
        self._pump()

    def _pump(self):
        if self.sending or not self.queue:
            return
        self.sending = True
        mac, f = self.queue.pop(0)
        self.win.obex.send(mac, f)

    def _on_transfer(self, _o, info):
        key = info["key"]
        if key not in self.rows:
            row = Gtk.ListBoxRow()
            card = cls(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4), "card")
            top = Gtk.Box(spacing=10)
            name = cls(Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE, hexpand=True), "card-title")
            st = cls(Gtk.Label(xalign=1), "card-sub")
            top.pack_start(name, True, True, 0)
            top.pack_start(st, False, False, 0)
            pb = Gtk.ProgressBar()
            meta = cls(Gtk.Label(xalign=0), "card-meta")
            card.pack_start(top, False, False, 0)
            card.pack_start(pb, False, False, 0)
            card.pack_start(meta, False, False, 0)
            row.add(card)
            self.list.prepend(row)
            row.show_all()
            self.rows[key] = (name, st, pb, meta)
        name, st, pb, meta = self.rows[key]
        arrow = "↑" if info["direction"] == "out" else "↓"
        who = ""
        d = self.win.dev_by_mac(info.get("mac", ""))
        if d:
            who = "  →  " + d.alias
        name.set_text("%s  %s%s" % (arrow, info["name"], who))
        st.set_text(self.STATUS.get(info["status"], info["status"]))
        size = info.get("size") or 0
        done = info.get("transferred") or 0
        if info["status"] == "complete":
            done = size
        pb.set_fraction(min(1.0, done / size) if size else (1.0 if info["status"] == "complete" else 0))
        el = max(.001, time.monotonic() - info.get("t0", time.monotonic()))
        txt = "%s / %s · %s/s" % (human(done), human(size), human(done / el))
        if info.get("error"):
            txt += "  · " + info["error"]
        if info["direction"] == "in" and info["status"] == "complete":
            txt = "Saved to " + info["file"]
        meta.set_text(txt)
        if info["direction"] == "out" and info["status"] in ("complete", "error"):
            if info["status"] == "error":
                self.win.toast("Offering lost", "%s — %s" % (info["name"], info.get("error") or "transfer failed"), "err")
            self.sending = False
            later(200, self._pump)

    def _rx_toggled(self, sw, _p):
        on = sw.get_active()
        CONFIG.accept_incoming = on
        self.win.obex.set_receiving(on)

    def _open_dir(self):
        d = os.path.join(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
                         or os.path.expanduser("~/Downloads"), "Teyvat Offerings")
        os.makedirs(d, exist_ok=True)
        run_async(["xdg-open", d])


# ═════════════════════════════════════════════ Statue of the Seven ═════
class DiagRow(Gtk.Box):
    def __init__(self, title):
        super().__init__(spacing=14)
        cls(self, "card", "diag")
        self.orb = cls(Gtk.Label(label="◇"), "orb", "pending")
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        self.t = cls(Gtk.Label(label=title, xalign=0), "card-title")
        self.d = cls(Gtk.Label(xalign=0, selectable=True), "card-sub")
        self.d.set_line_wrap(True)
        v.pack_start(self.t, False, False, 0)
        v.pack_start(self.d, False, False, 0)
        self.actions = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        self.pack_start(self.orb, False, False, 0)
        self.pack_start(v, True, True, 0)
        self.pack_start(self.actions, False, False, 0)

    def set(self, state, markup):
        for s in ("ok", "warn", "bad", "pending"):
            uncls(self.orb, s)
        cls(self.orb, state)
        self.orb.set_text({"ok": "◆", "warn": "◈", "bad": "✕", "pending": "◇"}[state])
        self.d.set_markup(markup)

    def action(self, label, cb, *classes):
        self.actions.pack_start(gbtn(label, cb, "small", *classes), False, False, 0)
        return self


class StatuePage(Page):
    def __init__(self, win):
        super().__init__("Statue of the Seven",
                         "Pray here when the Ley Lines falter — diagnostics, repairs and the full chronicle.")
        self.win = win
        top = Gtk.Box(spacing=10)
        top.pack_start(gbtn("✦  Divine everything", self.run_all), False, False, 0)
        top.pack_start(gbtn("⧉  Copy full report", self.copy_report, "dark"), False, False, 0)
        self.pack_start(top, False, False, 0)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_end(8)
        sc.add(box)
        self.pack_start(sc, True, True, 0)
        R = self.rows = {}
        R["service"] = DiagRow("bluetoothd service").action("⟳ Restart service", self.restart_service)
        R["rfkill"] = DiagRow("rfkill seal").action("✦ Break the seal", self.unblock)
        R["adapter"] = DiagRow("Ley Line adapter").action("⟳ Power-cycle", self.power_cycle) \
            .action("⚠ Reload driver", self.reload_driver, "danger")
        R["driver"] = DiagRow("Kernel driver & BlueZ")
        R["battery"] = DiagRow("Energy reporting (Battery1)").action("✦ Enable Experimental", self.enable_experimental, "dark")
        R["obex"] = DiagRow("obexd (file transfer)")
        R["audio"] = DiagRow("Audio server")
        R["pairings"] = DiagRow("Corrupted pacts").action("⊗ Purge selected", self.purge_selected, "danger") \
            .action("⊗ Forget wanderers", self.forget_wanderers, "dark")
        for r in R.values():
            box.pack_start(r, False, False, 0)
        self.purge_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.purge_box.set_margin_start(46)
        box.pack_start(self.purge_box, False, False, 0)
        self.checks = {}
        box.pack_start(section("CHRONICLE · journalctl -u bluetooth"), False, False, 6)
        lb = Gtk.Box(spacing=8)
        lb.pack_start(gbtn("⟳  Refresh chronicle", self.load_logs, "dark", "small"), False, False, 0)
        box.pack_start(lb, False, False, 0)
        self.logs = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        cls(self.logs, "logs")
        ls = Gtk.ScrolledWindow()
        ls.set_size_request(-1, 260)
        ls.add(self.logs)
        box.pack_start(ls, False, False, 0)
        self._ran = False

    def ensure_ran(self):
        if not self._ran:
            self._ran = True
            self.run_all()

    def run_all(self):
        for r in self.rows.values():
            r.set("pending", "<i>Divining…</i>")
        steps = [self.chk_service, self.chk_rfkill, self.chk_adapter, self.chk_driver, self.chk_battery,
                 self.chk_obex, self.chk_audio, self.chk_pairings, self.load_logs]
        for i, f in enumerate(steps):
            later(60 * (i + 1), f)

    def chk_service(self):
        def got(ok, out):
            st = out.strip() or "unknown"
            self.rows["service"].set("ok" if st == "active" else "bad",
                                     "bluetooth.service is <b>%s</b>" % esc(st))
        run_async(["systemctl", "is-active", "bluetooth"], got)

    def chk_rfkill(self):
        def got(ok, out):
            if not ok:
                self.rows["rfkill"].set("warn", "rfkill unavailable: %s" % esc(out.strip()[:120]))
                return
            soft = "Soft blocked: yes" in out
            hard = "Hard blocked: yes" in out
            if hard:
                self.rows["rfkill"].set("bad", "<b>Hard-blocked</b> — flip the physical wireless switch / Fn key or check BIOS")
            elif soft:
                self.rows["rfkill"].set("bad", "<b>Soft-blocked</b> — break the seal to free the Ley Lines")
            elif out.strip():
                self.rows["rfkill"].set("ok", "No seals. %d bluetooth radio(s) free." % out.count("Bluetooth"))
            else:
                self.rows["rfkill"].set("warn", "No bluetooth radio known to rfkill")
        run_async(["rfkill", "list", "bluetooth"], got)

    def chk_adapter(self):
        a = self.win.bz.adapter
        p = self.win.bz.adapter_props()
        if not a:
            self.rows["adapter"].set("bad", "No adapter on D-Bus — driver, firmware or service problem")
            return
        self.rows["adapter"].set("ok" if p.get("Powered") else "warn",
                                 "<b>%s</b> · %s · %s · powered: <b>%s</b> · discoverable: %s · pairable: %s"
                                 % (esc(p.get("Alias", "?")), p.get("Address", "?"), os.path.basename(a),
                                    "yes" if p.get("Powered") else "no", "yes" if p.get("Discoverable") else "no",
                                    "yes" if p.get("Pairable") else "no"))

    def chk_driver(self):
        cmd = ["sh", "-c", "(bluetoothctl --version 2>/dev/null; "
               "lsmod 2>/dev/null | awk '/^(btusb|btintel|btrtl|btbcm|btmtk|btqca|hci_uart|bluetooth) /{print $1}' | tr '\\n' ' ')"]

        def got(ok, out):
            lines = out.strip().splitlines()
            ver = lines[0] if lines else "?"
            mods = lines[1] if len(lines) > 1 else ""
            self.rows["driver"].set("ok" if "btusb" in mods or "hci_uart" in mods else "warn",
                                    "BlueZ: <b>%s</b> · modules: %s" % (esc(ver), esc(mods or "none detected")))
        run_async(cmd, got)

    def chk_battery(self):
        n = sum(1 for d in self.win.devs.values() if d.battery is not None)
        if n:
            self.rows["battery"].set("ok", "%d companion(s) report their energy" % n)
            return
        exp = False
        try:
            with open("/etc/bluetooth/main.conf") as f:
                exp = bool(re.search(r"^\s*Experimental\s*=\s*true", f.read(), re.M | re.I))
        except Exception:
            pass
        self.rows["battery"].set("ok" if exp else "warn",
                                 "Experimental is enabled — energy appears once a supporting device connects" if exp else
                                 "No energy readings. Many headsets only report battery with <b>Experimental = true</b> "
                                 "in <tt>/etc/bluetooth/main.conf</tt> [General].")

    def chk_obex(self):
        bus = self.win.obex.bus
        if not bus:
            self.rows["obex"].set("bad", "No session bus")
            return

        def got(b, res, *_):
            try:
                names = b.call_finish(res).unpack()[0]
                ok = OBEX in names
                self.rows["obex"].set("ok" if ok else "warn",
                                      "obexd is activatable — Transmission ready" if ok else
                                      "obexd not found — install <b>bluez-obex</b> (Arch) / <b>bluez-obexd</b> (Debian)")
            except GLib.Error as e:
                self.rows["obex"].set("warn", esc(e.message))
        bus.call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListActivatableNames",
                 None, GLib.VariantType("(as)"), Gio.DBusCallFlags.NONE, -1, None, got, None)

    def chk_audio(self):
        def got(ok, out):
            m = re.search(r"Server Name:\s*(.+)", out)
            extra = "" if shutil.which("playerctl") else \
                " · <span alpha='70%'>playerctl missing — “Pause when it fades” needs it</span>"
            if ok and m:
                self.rows["audio"].set("ok", "Server: <b>%s</b>%s" % (esc(m.group(1)), extra))
            else:
                self.rows["audio"].set("warn", "pactl unavailable — the ♫ Echoing Conch page needs "
                                               "pipewire-pulse or pulseaudio-utils" + extra)
        run_async(["env", "LC_ALL=C", "pactl", "info"], got)

    def chk_pairings(self):
        for c in self.purge_box.get_children():
            c.destroy()
        self.checks = {}
        bad = []
        for d in self.win.devs.values():
            why = []
            if d.paired and d.bonded is False:
                why.append("paired but keys lost (not bonded)")
            if d.paired and not d.uuids:
                why.append("no services ever discovered")
            if d.paired and d.blocked:
                why.append("sealed (blocked)")
            if d.paired and not d.name:
                why.append("nameless bond")
            if why:
                bad.append((d, why))
        stray = sum(1 for d in self.win.devs.values() if not d.paired and not d.connected)
        if bad:
            self.rows["pairings"].set("warn", "%d suspicious pact(s) · %d wandering cached device(s)" % (len(bad), stray))
            for d, why in bad:
                cb = Gtk.CheckButton()
                cb.set_active(True)
                l = Gtk.Label(xalign=0)
                l.set_markup("<b>%s</b>  <span alpha='60%%'>%s — %s</span>" % (esc(d.alias), d.address, esc(", ".join(why))))
                row = Gtk.Box(spacing=8)
                row.pack_start(cb, False, False, 0)
                row.pack_start(l, False, False, 0)
                self.purge_box.pack_start(row, False, False, 0)
                self.checks[d.path] = cb
            self.purge_box.show_all()
        else:
            self.rows["pairings"].set("ok", "All pacts look healthy · %d wandering cached device(s)" % stray)

    def load_logs(self):
        def got(ok, out):
            self.logs.get_buffer().set_text(out if out.strip() else "(no journal access — add yourself to the "
                                                                    "'systemd-journal' or 'wheel' group)")
        run_async(["journalctl", "-u", "bluetooth", "-n", "200", "--no-pager", "-o", "short-iso"], got)

    def _report(self, title):
        def cb(ok, out):
            self.win.toast(title + (" ✦" if ok else " failed"), "" if ok else out.strip()[:200], "ok" if ok else "err")
            later(1500, self.run_all)
        return cb

    def restart_service(self):
        run_async(["pkexec", "systemctl", "restart", "bluetooth"], self._report("Service restarted"))

    def unblock(self):
        def got(ok, out):
            if ok:
                self._report("Seal broken")(True, out)
            else:
                run_async(["pkexec", "rfkill", "unblock", "bluetooth"], self._report("Seal broken"))
        run_async(["rfkill", "unblock", "bluetooth"], got)

    def power_cycle(self):
        a = self.win.bz.adapter
        if not a:
            self.win.toast("No adapter", "", "err")
            return
        self.win.bz.set_prop(a, ADAPTER, "Powered", GLib.Variant("b", False),
                             lambda *_: later(1200, self.win.set_power, True))
        self.win.toast("Power-cycling the adapter…", "", "info")
        later(3000, self.run_all)

    def reload_driver(self):
        self.win.ask("Reload driver", "This unloads and reloads <b>btusb</b>. All companions will disconnect.\nProceed?",
                     lambda ok: ok and run_async(["pkexec", "sh", "-c", "modprobe -r btusb && sleep 1 && modprobe btusb"],
                                                 self._report("Driver reloaded")), ok="Reload")

    def enable_experimental(self):
        script = ("f=/etc/bluetooth/main.conf; [ -f $f ] || printf '[General]\\n' > $f; "
                  "if grep -qE '^#?[[:space:]]*Experimental[[:space:]]*=' $f; then "
                  "sed -i -E '0,/^#?[[:space:]]*Experimental[[:space:]]*=.*/s//Experimental = true/' $f; "
                  "else sed -i '/^\\[General\\]/a Experimental = true' $f; fi; systemctl restart bluetooth")
        self.win.ask("Enable Experimental", "Sets <tt>Experimental = true</tt> in /etc/bluetooth/main.conf "
                     "and restarts bluetoothd (requires your password).",
                     lambda ok: ok and run_async(["pkexec", "sh", "-c", script], self._report("Experimental enabled")),
                     ok="Enable")

    def purge_selected(self):
        paths = [p for p, cb in self.checks.items() if cb.get_active()]
        if not paths:
            self.win.toast("Nothing selected", "", "warn")
            return
        for p in paths:
            self.win.remove_dev(p, quiet=True)
        self.win.toast("Purged %d corrupted pact(s)" % len(paths), "Pair them again from Companions", "ok")
        later(1200, self.chk_pairings)

    def forget_wanderers(self):
        paths = [d.path for d in self.win.devs.values() if not d.paired and not d.connected]
        for p in paths:
            self.win.remove_dev(p, quiet=True)
        self.win.toast("Forgot %d wanderer(s)" % len(paths), "", "ok")

    def copy_report(self):
        self.win.toast("Compiling the chronicle…", "", "info")
        cmds = [("uname", ["uname", "-a"]), ("bluez", ["bluetoothctl", "--version"]),
                ("service", ["systemctl", "status", "bluetooth", "--no-pager", "-n", "0"]),
                ("rfkill", ["rfkill", "list"]), ("modules", ["sh", "-c", "lsmod | grep -Ei 'bt|blue'"]),
                ("audio", ["pactl", "info"]),
                ("audio cards", ["pactl", "list", "short", "cards"]),
                ("journal", ["journalctl", "-u", "bluetooth", "-n", "80", "--no-pager", "-o", "short-iso"])]

        def done(results):
            out = ["# Teyvat Archive report v%s — %s" % (VERSION, time.strftime("%Y-%m-%d %H:%M:%S"))]
            out.append("\n## adapter\n" + json.dumps(self.win.bz.adapter_props(), default=str, indent=1))
            out.append("\n## renderer\nfps target %s · effective %.1f · refresh %.1f Hz · scale %d · twinkle %s · wheel %s"
                       % (CONFIG.fps, Anim.fps(self.win, now_t()), Anim._rr, self.win.get_scale_factor(),
                          CONFIG.animated_stars, CONFIG.animated_wheel))
            out.append("\n## harmony\naudio_follow %s · pause_on_fade %s · remember_volume %s · vigil %s · autostart %s"
                       % (CONFIG.audio_follow, CONFIG.pause_on_fade, CONFIG.remember_volume, CONFIG.vigil,
                          autostart_enabled()))
            out.append("\n## devices")
            for d in sorted(self.win.devs.values(), key=lambda d: d.rank):
                out.append("- %s [%s] %s kind=%s (auto %s%s) icon=%s class=0x%06x appearance=0x%04x battery=%s "
                           "rssi=%s paired=%s bonded=%s trusted=%s connected=%s uuids=%d"
                           % (d.alias, d.address, d.path, d.kind, d.auto_kind, ", overridden" if d.overridden else "",
                              d.icon, int(d.cls or 0), int(d.appearance or 0), d.battery, d.rssi, d.paired,
                              d.bonded, d.trusted, d.connected, len(d.uuids)))
            for title, ok, txt in results:
                out.append("\n## %s\n%s" % (title, txt.strip()))
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text("\n".join(out), -1)
            self.win.toast("Report copied to clipboard ✦", "Paste it in an issue or forum post", "ok")
        run_chain(cmds, done)


# ══════════════════════════════════════════════════════ Settings ══════
class SettingsPage(Page):
    def __init__(self, win):
        super().__init__("Archive Settings", "Bend the Archive to your will. Changes are saved and applied instantly — no restart needed.")
        self.win = win
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer, self.scroller = genshin_scroll(body)
        self.ctl = {}                       # key -> setter, used by "Reset to defaults"
        grids = {}

        def grid(title):
            body.pack_start(section(title), False, False, 8)
            g = Gtk.Grid(column_spacing=20, row_spacing=14)
            body.pack_start(g, False, False, 0)
            grids[title] = [g, 0]
            return title

        def add(gk, label, hint, widget):
            g, r = grids[gk]
            l = Gtk.Label(xalign=0)
            l.set_markup("%s\n<span size='small' alpha='55%%'>%s</span>" % (esc(label), esc(hint)))
            widget.set_valign(Gtk.Align.CENTER)
            widget.set_halign(Gtk.Align.START)
            g.attach(l, 0, r, 1, 1)
            g.attach(widget, 1, r, 1, 1)
            grids[gk][1] = r + 1

        def sw(key, extra=None):
            s = Gtk.Switch(active=bool(getattr(CONFIG, key)))

            def on(*_):
                setattr(CONFIG, key, s.get_active())
                if extra:
                    extra()
            s.connect("notify::active", on)
            self.ctl[key] = lambda v: s.set_active(bool(v))
            return s

        def spin(key, lo, hi, step=1, extra=None):
            s = Gtk.SpinButton.new_with_range(lo, hi, step)
            s.set_value(getattr(CONFIG, key))

            def on(*_):
                setattr(CONFIG, key, int(s.get_value()))
                if extra:
                    extra()
            s.connect("value-changed", on)
            self.ctl[key] = lambda v: s.set_value(v)
            return wheel_passthrough(s, self.scroller)

        sky = lambda: self.win.backdrop.invalidate()
        L = grid("LOOK & MOTION")
        add(L, "Reduce motion", "slow every animation to a gentle 2 fps (saves power)", sw("reduce_motion", apply_ui_anim))
        add(L, "Smooth switches & banners", "GTK's own little slides (pages always switch instantly)",
            sw("smooth_ui", apply_ui_anim))
        add(L, "Wish cinematic", "a short falling-star scene when a new pact is forged · click to skip", sw("wish_animation"))
        add(L, "Twinkling stardust", "animate the stars behind everything (costs a little CPU)", sw("animated_stars", sky))
        add(L, "Turning star wheel", "the big constellation wheel in the corner slowly turns (very cheap)", sw("animated_wheel", sky))
        dens = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1.5, .05)
        dens.set_value(CONFIG.particle_density)
        dens.set_size_request(240, -1)
        wheel_passthrough(dens, self.scroller)
        self._dens_src = 0

        def dens_changed(s):
            CONFIG.particle_density = round(s.get_value(), 2)
            if self._dens_src:
                GLib.source_remove(self._dens_src)
            self._dens_src = GLib.timeout_add(120, lambda: (setattr(self, "_dens_src", 0), sky(), False)[2])
        dens.connect("value-changed", dens_changed)
        self.ctl["particle_density"] = dens.set_value
        add(L, "Stardust density", "how many stars are painted in the sky", dens)
        self.fps_spin = spin("fps", 10, 144, 1, self._fps_info)
        add(L, "Animation FPS", "snapped to your monitor so frames stay evenly spaced", self.fps_spin)
        self.fps_lbl = cls(Gtk.Label(xalign=0), "dim")
        g, r = grids[L]
        g.attach(self.fps_lbl, 1, r, 1, 1)

        C = grid("COMPANIONS")
        add(C, "Desktop notifications", "notify-send for low energy & arrivals", sw("desktop_notify"))
        add(C, "Auto-trust new pacts", "mark freshly paired devices as Trusted", sw("auto_trust"))
        add(C, "Show nameless wanderers", "reveal anonymous BLE beacons", sw("show_nameless", self.win.refilter))
        add(C, "Low-energy alert (%)", "warn when a companion's battery falls below", spin("battery_alert", 5, 60))
        add(C, "Elemental Sight duration (s)", "how long a scan keeps the Ley Lines open", spin("scan_seconds", 10, 300, 5))

        B = grid("BACKGROUND")
        add(B, "Keep running in the background", "closing only hides the window — the pairing agent and the "
            "♫ harmony rules stay awake · Ctrl+Q truly quits", sw("vigil"))
        self.sw_auto = Gtk.Switch(active=autostart_enabled())
        self._auto_guard = False
        self.sw_auto.connect("notify::active", self._autostart)
        add(B, "Start with the system", "XDG autostart of “teyvat-archive --background” · Hyprland / Sway: exec-once it",
            self.sw_auto)

        body.pack_start(gbtn("↺  Reset to defaults", self._reset, "dark"), False, False, 12)
        body.pack_start(section("ABOUT"), False, False, 10)
        ab = Gtk.Label(xalign=0)
        ab.set_markup("<b>Teyvat Archive</b> %s — BlueZ over D-Bus, GTK3, Cairo, PipeWire / Pulse\n"
                      "<span alpha='65%%'>Ctrl+F search · F5 Elemental Sight · Ctrl+1…6 pages · Ctrl+Q quit · Esc skips the Wish\n"
                      "Config: %s</span>" % (VERSION, esc(CONF_FILE)))
        body.pack_start(ab, False, False, 0)
        self.pack_start(outer, True, True, 0)
        self.connect("map", lambda *_: self._on_map())

    def _on_map(self):
        self._fps_info()
        self._auto_guard = True
        self.sw_auto.set_active(autostart_enabled())
        self._auto_guard = False

    def _autostart(self, s, _p):
        if self._auto_guard:
            return
        on = s.get_active()
        ok, err = set_autostart(on)
        if not ok:
            self.win.toast("Autostart failed", err, "err")
            self._auto_guard = True
            s.set_active(not on)
            self._auto_guard = False
            return
        if on and not CONFIG.vigil:
            self.ctl["vigil"](True)               # autostart without staying awake makes no sense
        self.win.toast("Awakens with the system ✦" if on else "Autostart removed", AUTOSTART if on else "",
                       "ok" if on else "info")

    def _fps_info(self):
        try:
            eff = Anim.fps(self.win, now_t() + 10)    # +10 forces a fresh refresh-rate read
            self.fps_lbl.set_markup("<span size='small'>running at <b>%.0f fps</b> on a %.0f Hz display</span>"
                                    % (eff, Anim._rr))
        except Exception:
            pass

    def _reset(self, *_):
        for key, setter in self.ctl.items():
            setter(Config.DEFAULTS[key])
        CONFIG.save()
        apply_ui_anim()
        self.win.backdrop.invalidate()
        self.win.toast("Archive restored", "Settings are back to their defaults", "ok")



# ═══════════════════════════════════════════════════════ window ═══════
NAV = [("companions", "Companions"), ("atlas", "Ley Line Atlas"), ("echoes", "Echoing Conch"),
       ("transmission", "Transmission"), ("statue", "Statue of the Seven"), ("settings", "Archive Settings")]
PAGE_ALIASES = {"reactions": "echoes", "reaction": "echoes", "automations": "echoes", "resonance": "echoes",
                "audio": "echoes", "sound": "echoes", "conch": "echoes"}
NOISY_KEYS = {"RSSI", "ManufacturerData", "ServiceData", "TxPower", "AdvertisingFlags", "AdvertisingData"}


class ArchiveWindow(Gtk.ApplicationWindow):
    def __init__(self, app, visible=True):
        super().__init__(application=app, title="Teyvat Archive")
        _a = (Gdk.Display.get_default().get_primary_monitor() or Gdk.Display.get_default().get_monitor(0)).get_workarea(); self.set_default_size(min(1240, int(_a.width * 0.94)), min(800, int(_a.height * 0.9)))
        self.set_icon_name("bluetooth")
        self.bz = BlueZ()
        self.devs, self.rows, self.busy, self.warned = {}, {}, set(), set()
        self._guard, self._scan_timer, self._rf_retry = False, None, False
        self._pend, self._pend_src = {}, 0
        self._quitting = self._vigil_told = False
        self.pending_select = None
        self.obex = ObexManager(self)
        self.agent = PairingAgent(self)

        hb = Gtk.HeaderBar(show_close_button=True)
        hb.set_title("✦  Teyvat Archive  ✦")
        hb.set_subtitle("Ley Line Network · Bluetooth")
        self.set_titlebar(hb)

        # top-level: the app, or the (opaque) Wish cinematic — never both being painted
        self.top = Gtk.Stack()
        self.top.set_transition_type(Gtk.StackTransitionType.NONE)
        self.add(self.top)
        self.main_overlay = overlay = Gtk.Overlay()
        self.root = root = Gtk.Box()
        self.backdrop = Backdrop(root)              # the sky is painted by the root box itself
        overlay.add(root)

        side = cls(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6), "sidebar")
        side.set_size_request(250, -1)
        self.emblem = AdapterEmblem(160)
        side.pack_start(self.emblem, False, False, 4)
        self.adapter_name = cls(Gtk.Label(label="…"), "adapter-name")
        self.adapter_sub = cls(Gtk.Label(), "dim")
        side.pack_start(self.adapter_name, False, False, 0)
        side.pack_start(self.adapter_sub, False, False, 0)
        side.pack_start(Ornament(), False, False, 4)
        for label, attr in (("Ley Lines", "power_sw"), ("Visible to others", "disc_sw")):
            row = Gtk.Box(spacing=8)
            row.pack_start(Gtk.Label(label=label, xalign=0), True, True, 0)
            s = Gtk.Switch()
            setattr(self, attr, s)
            row.pack_end(s, False, False, 0)
            side.pack_start(row, False, False, 0)
        self.power_sw.connect("notify::active", lambda s, _p: (not self._guard) and self.set_power(s.get_active()))
        self.disc_sw.connect("notify::active", lambda s, _p: (not self._guard) and self.set_discoverable(s.get_active()))
        self.scan_btn = gbtn("◈  Elemental Sight", self.toggle_scan)
        side.pack_start(self.scan_btn, False, False, 6)
        side.pack_start(Ornament(), False, False, 4)
        self.nav = {}
        group = None
        for key, title in NAV:
            b = Gtk.RadioButton.new_from_widget(group)
            b.set_mode(False)
            cls(b, "nav")
            bx = Gtk.Box(spacing=12)
            icon = NavIcon(key, 24)
            bx.pack_start(icon, False, False, 0)
            bx.pack_start(Gtk.Label(label=title, xalign=0), True, True, 0)
            b.add(bx)
            group = group or b
            b.connect("toggled", self._nav, key)
            b.connect("toggled", lambda btn, ic=icon: ic.sync(btn))
            b.connect("state-flags-changed", lambda btn, _f, ic=icon: ic.sync(btn))
            self.nav[key] = b
            side.pack_start(b, False, False, 0)
            icon.sync(b)
        foot = cls(Gtk.Label(label="v%s · BlueZ / D-Bus" % VERSION), "dim")
        side.pack_end(foot, False, False, 4)
        root.pack_start(side, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)    # instant: no double-page fades
        self.companions = CompanionsPage(self)
        self.atlas = AtlasPage(self)
        self.echoes = EchoesPage(self)
        self.transmission = TransmissionPage(self)
        self.statue = StatuePage(self)
        self.settings = SettingsPage(self)
        for key, page in (("companions", self.companions), ("atlas", self.atlas), ("echoes", self.echoes),
                          ("transmission", self.transmission), ("statue", self.statue), ("settings", self.settings)):
            self.stack.add_named(page, key)
        root.pack_start(self.stack, True, True, 0)

        self.toaster = Toaster()
        overlay.add_overlay(self.toaster)
        overlay.set_overlay_pass_through(self.toaster, True)
        self.top.add_named(overlay, "main")
        self.wish = WishView(self)
        self.top.add_named(self.wish, "wish")

        self.bz.connect("device-added", self.on_dev_added)
        self.bz.connect("device-removed", self.on_dev_removed)
        self.bz.connect("device-changed", self.on_dev_changed)
        self.bz.connect("adapter-changed", self.on_adapter_changed)
        self.bz.connect("paired", self.on_paired)
        self.bz.connect("availability", self.on_availability)
        self.connect("key-press-event", self._key)
        self.connect("delete-event", self._on_delete)
        self.connect("destroy", self._cleanup)
        apply_ui_anim()
        self.connect("window-state-event", self._wstate)
        self.add_tick_callback(Anim.tick)          # the ONE animation clock
        if visible:
            self.show_all()
        else:                                      # --background: build everything, show nothing
            hb.show_all()
            self.top.show_all()
        self.top.set_visible_child_name("main")
        self.bz.start()
        if CONFIG.accept_incoming:
            self.obex.set_receiving(True)
        self.update_summary()

    def _wstate(self, _w, ev):      # minimised -> stop every animation
        Anim.paused = bool(ev.new_window_state & Gdk.WindowState.ICONIFIED)
        return False

    def _on_delete(self, *_):
        """With 'keep running' on, closing only hides the window."""
        if CONFIG.vigil and not self._quitting:
            self.wish.finish()
            self.hide()
            if not self._vigil_told:
                self._vigil_told = True
                notify_now("The Archive keeps vigil ✦", "The pairing agent and the harmony rules stay awake. "
                           "Run teyvat-archive to return — Ctrl+Q inside it truly quits.")
            return True
        return False

    # ── helpers
    def toast(self, title, body="", kind="info", sticky=False):
        self.toaster.push(title, body or "", kind, sticky)

    def ask(self, title, markup, cb, entry=False, numeric=False, ok="Confirm", cancel="Cancel"):
        return GDialog(self, title, markup, cb, entry, numeric, ok, cancel)

    def dev_by_mac(self, mac):
        mac = (mac or "").upper()
        for d in self.devs.values():
            if d.address.upper() == mac:
                return d
        return None

    def refilter(self):
        self.companions.listbox.invalidate_filter()

    def reclassify(self, path):
        if path in self.bz.known:
            self.devs[path] = self.bz.dev(path)
            self._refresh_path(path)
            self.refilter()

    def _nav(self, b, key):
        if b.get_active():
            self.stack.set_visible_child_name(key)
            if key == "transmission":
                self.transmission.refresh_devices()
            elif key == "statue":
                self.statue.ensure_ran()

    def goto(self, key):
        key = PAGE_ALIASES.get(key, key)
        if key in self.nav:
            self.nav[key].set_active(True)

    def select_device(self, path):
        row = self.rows.get(path)
        self.goto("companions")
        if row:
            self.companions.search.set_text("")
            self.companions.listbox.select_row(row)
            self.companions.detail.show_device(path)

    def open_echoes(self, path):
        d = self.devs.get(path)
        self.goto("echoes")
        if d:
            self.echoes.focus(d.address)

    def open_transmission(self, path):
        d = self.devs.get(path)
        self.goto("transmission")
        if d:
            self.transmission.preselect(d.address)

    def update_summary(self):
        ds = [d for d in self.devs.values() if not (d.nameless and not d.paired and not CONFIG.show_nameless)]
        c = sum(d.connected for d in ds)
        p = sum(d.paired for d in ds)
        n = sum(1 for d in ds if not d.paired)
        self.companions.subtitle.set_markup(
            "<span foreground='#D3BC8E'>◆</span> %d resonating   ·   <span foreground='#D3BC8E'>◇</span> %d bonded"
            "   ·   · %d wandering nearby" % (c, p, n))

    # ── BlueZ signals
    def on_dev_added(self, _bz, path):
        d = self.bz.dev(path)
        self.devs[path] = d
        row = DeviceRow(self, path)
        self.rows[path] = row
        self.companions.listbox.add(row)
        row.show_all()
        row.refresh(d)
        self.update_summary()
        if self.pending_select and d.address.upper() == self.pending_select.upper():
            self.pending_select = None
            later(150, self.select_device, path)

    def on_dev_removed(self, _bz, path):
        self.devs.pop(path, None)
        self._pend.pop(path, None)
        row = self.rows.pop(path, None)
        if row:
            row.destroy()
        if self.companions.detail.path == path:
            self.companions.detail.path = None
            self.companions.detail.refresh()
        self.update_summary()

    def on_dev_changed(self, _bz, path, keys):
        """RSSI floods during Elemental Sight are coalesced (4x/s); meaningful changes apply now."""
        keys = set(keys or [])
        self._pend.setdefault(path, set()).update(keys)
        if keys - NOISY_KEYS:
            if self._pend_src:
                GLib.source_remove(self._pend_src)
                self._pend_src = 0
            self._apply_pending()
        elif not self._pend_src:
            self._pend_src = GLib.timeout_add(250, self._pending_timer)

    def _pending_timer(self):
        self._pend_src = 0
        self._apply_pending()
        return False

    def _apply_pending(self):
        pend, self._pend = self._pend, {}
        resort = refilt = False
        for path, keys in pend.items():
            if path not in self.bz.known:
                continue
            r1, r2 = self._dev_changed(path, keys)
            resort |= r1
            refilt |= r2
        if resort:
            self.companions.listbox.invalidate_sort()
        if refilt:
            self.companions.listbox.invalidate_filter()
            self.update_summary()

    def _dev_changed(self, path, keys):
        prev = self.devs.get(path)
        d = self.bz.dev(path)
        self.devs[path] = d
        self._refresh_path(path)
        resort = bool(keys & {"Connected", "Paired", "Alias", "Name"}) or \
            ("RSSI" in keys and d.rank == 2 and prev is not None and prev.rssi != d.rssi)
        refilt = bool(keys & {"Connected", "Paired", "Alias", "Name", "Trusted"}) or \
            (prev is not None and (prev.rssi is None) != (d.rssi is None))
        if prev and "Connected" in keys and prev.connected != d.connected:
            if d.connected:
                self.toast("Resonance established ◆", "%s · %s" % (d.alias, d.label), "ok")
            else:
                self.toast("Resonance faded", d.alias, "info")
            self._harmony(d)
            self.echoes.schedule_refresh(900)
        elif keys & {"Percentage", "Alias"}:
            self.echoes.schedule_refresh(300)
        if d.battery is not None:
            if d.battery <= CONFIG.battery_alert and path not in self.warned:
                self.warned.add(path)
                self.toast("Low energy ⚠", "%s is at %d%%" % (d.alias, d.battery), "warn")
                desktop_notify("Low energy: %s" % d.alias, "Battery at %d%%" % d.battery, "battery-caution")
            elif d.battery > CONFIG.battery_alert + 5:
                self.warned.discard(path)
        return resort, refilt

    def _harmony(self, d):
        """The three ♫ harmony rules of the Echoing Conch."""
        if not d.audio:
            return
        if d.connected:
            vol = (CONFIG.volumes or {}).get(d.address.upper()) if CONFIG.remember_volume else None

            def after_route(ok, msg):
                if ok:
                    self.toast("♫ Audio follows %s" % d.alias, "", "ok")
                if vol is not None:
                    set_bt_volume(d.address, int(vol), lambda *_: self.echoes.schedule_refresh(200))
            if CONFIG.audio_follow:
                route_audio(d.address, after_route)
            elif vol is not None:
                set_bt_volume(d.address, int(vol), lambda *_: self.echoes.schedule_refresh(200))
        elif CONFIG.pause_on_fade and d.kind in ("headphones", "earbuds", "headset") and shutil.which("playerctl"):
            run_async(["playerctl", "-a", "pause"])

    def _refresh_path(self, path):
        d = self.devs.get(path)
        row = self.rows.get(path)
        if d and row:
            row.refresh(d)
        if d and self.companions.detail.path == path:
            self.companions.detail.refresh(d)

    def on_paired(self, _bz, path):
        d = self.bz.dev(path)
        if CONFIG.wish_animation and self.get_visible() and not CONFIG.reduce_motion:
            self.wish.play(d.alias, d.kind, d.color, d.rarity)
        else:
            self.toast("✦ A new pact is forged", "%s · %s" % (d.alias, d.label), "ok")
        desktop_notify("New pact forged ✦", d.alias)

    def on_adapter_changed(self, *_):
        a = self.bz.adapter
        p = self.bz.adapter_props()
        powered, disc = bool(p.get("Powered")), bool(p.get("Discovering"))
        self.emblem.state = "scan" if (powered and disc) else ("on" if powered else "off")
        self.adapter_name.set_text(p.get("Alias") or p.get("Name") or "No adapter")
        self.adapter_sub.set_text("%s · %s" % (p.get("Address", "—"), os.path.basename(a) if a else "—"))
        self._guard = True
        self.power_sw.set_active(powered)
        self.disc_sw.set_active(bool(p.get("Discoverable")))
        self.disc_sw.set_sensitive(powered)
        self._guard = False
        self.scan_btn.set_label("◉  Sealing Sight…  (stop)" if disc else "◈  Elemental Sight")
        (cls if disc else uncls)(self.scan_btn, "active")

    def on_availability(self, _bz, up):
        if up:
            later(300, self.agent.register)
        else:
            self.toast("The Ley Lines are silent", "bluetoothd is not running — visit the Statue of the Seven", "err")

    # ── actions
    def set_power(self, on, then=None):
        a = self.bz.adapter
        if not a:
            run_async(["rfkill", "unblock", "bluetooth"])
            self.toast("No adapter found", "Trying to break the rfkill seal…", "warn")
            return

        def done(ok, err, _v):
            if ok:
                self._rf_retry = False
                self.toast("Ley Lines awakened ✦" if on else "Ley Lines sealed", "", "ok" if on else "info")
                if then:
                    later(400, then)
            elif on and not self._rf_retry:
                self._rf_retry = True
                run_async(["rfkill", "unblock", "bluetooth"], lambda *_: later(900, self.set_power, True, then))
            else:
                self._rf_retry = False
                self.toast("The Ley Lines resist", err, "err")
                self.on_adapter_changed()
        self.bz.set_prop(a, ADAPTER, "Powered", GLib.Variant("b", on), done)

    def set_discoverable(self, on):
        if self.bz.adapter:
            self.bz.set_prop(self.bz.adapter, ADAPTER, "Discoverable", GLib.Variant("b", on),
                             lambda ok, err, _v: ok or self.toast("Glider failed", err, "err"))

    def toggle_scan(self):
        a = self.bz.adapter
        if not a:
            self.toast("No adapter", "Nothing to search with", "err")
            return
        p = self.bz.adapter_props()
        if p.get("Discovering"):
            self.bz.call(a, ADAPTER, "StopDiscovery", None, lambda *x: None)
            return

        def start():
            flt = {"DuplicateData": GLib.Variant("b", True), "Transport": GLib.Variant("s", "auto")}

            def started(ok, err, _v):
                if not ok:
                    self.toast("Elemental Sight failed", err, "err")
                    return
                self.toast("Elemental Sight ◈", "Searching the Ley Lines for %ds…" % CONFIG.scan_seconds, "info")
                if self._scan_timer:
                    GLib.source_remove(self._scan_timer)
                self._scan_timer = GLib.timeout_add_seconds(CONFIG.scan_seconds, self._auto_stop)
            self.bz.call(a, ADAPTER, "SetDiscoveryFilter", GLib.Variant("(a{sv})", (flt,)),
                         lambda *_: self.bz.call(a, ADAPTER, "StartDiscovery", None, started))
        if not p.get("Powered"):
            self.set_power(True, then=start)
        else:
            start()

    def _auto_stop(self):
        self._scan_timer = None
        if self.bz.adapter and self.bz.adapter_props().get("Discovering"):
            self.bz.call(self.bz.adapter, ADAPTER, "StopDiscovery", None, lambda *x: None)
        return False

    def dev_call(self, path, method, busy_msg=None, timeout=30000, then=None):
        d = self.devs.get(path)
        name = d.alias if d else path
        self.busy.add(path)
        self._refresh_path(path)
        if busy_msg:
            self.toast(busy_msg % name, "", "info")

        def done(ok, err, _v):
            self.busy.discard(path)
            self._refresh_path(path)
            if ok:
                if then:
                    then()
            else:
                self.toast("%s failed" % {"Connect": "Resonance", "Disconnect": "Severing",
                                          "Pair": "Pact"}.get(method, method), "%s — %s" % (name, err), "err")
        self.bz.call(path, DEVICE, method, None, done, timeout)

    def quick_action(self, path):
        d = self.devs.get(path)
        if not d:
            return
        if d.connected:
            self.dev_call(path, "Disconnect")
        elif d.paired:
            self.dev_call(path, "Connect", "Opening a Ley Line to %s…")
        else:
            self.pair_dev(path)

    def pair_dev(self, path):
        def after():
            if CONFIG.auto_trust:
                self.bz.set_prop(path, DEVICE, "Trusted", GLib.Variant("b", True))
            later(700, self.dev_call, path, "Connect")
        self.dev_call(path, "Pair", "Forging a pact with %s… (accept on the device if asked)", 90000, after)

    def forget_dev(self, path):
        d = self.devs.get(path)
        if not d:
            return
        self.ask("Forget %s?" % d.alias, "The pact with <b>%s</b> will be severed forever.\n"
                 "You'll need to pair again." % esc(d.alias),
                 lambda ok: ok and self.remove_dev(path), ok="Forget", cancel="Keep")

    def remove_dev(self, path, quiet=False):
        d = self.devs.get(path)
        adapter = (d.adapter if d else None) or self.bz.adapter
        self.bz.call(adapter, ADAPTER, "RemoveDevice", GLib.Variant("(o)", (path,)),
                     lambda ok, err, _v: quiet or self.toast("Companion forgotten" if ok else "Forget failed",
                                                             (d.alias if d else "") if ok else err, "ok" if ok else "err"))

    def pair_by_mac(self, mac, tries=0):
        d = self.dev_by_mac(mac)
        if d:
            self.select_device(d.path)
            self.pair_dev(d.path)
        elif tries < 20:
            if tries == 0 and not self.bz.adapter_props().get("Discovering"):
                self.toggle_scan()
            later(1000, self.pair_by_mac, mac, tries + 1)
        else:
            self.toast("Companion not found", mac, "err")

    def _key(self, w, ev):
        ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
        if self.wish.playing and ev.keyval in (Gdk.KEY_Escape, Gdk.KEY_space, Gdk.KEY_Return):
            self.wish.finish()
            return True
        if ctrl and ev.keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.goto("companions")
            self.companions.search.grab_focus()
            return True
        if ctrl and ev.keyval in (Gdk.KEY_q, Gdk.KEY_Q):
            self._quitting = True           # Ctrl+Q always really quits
            self.close()
            return True
        if ev.keyval == Gdk.KEY_F5:
            self.toggle_scan()
            return True
        if ctrl and Gdk.KEY_1 <= ev.keyval <= Gdk.KEY_6:
            self.goto(NAV[ev.keyval - Gdk.KEY_1][0])
            return True
        return False

    def _cleanup(self, *_):
        CONFIG.flush()
        self.echoes._stop_sub()
        self.agent.unregister()
        self.obex.set_receiving(False)


# NOTE on speed: GTK3 draws CSS box-shadow blur and opacity in software, every time the area under
# it is repainted. This sheet therefore uses crisp borders / gradients instead of blurred glows,
# and no CSS transitions (each transition = many full repaints of that widget).
CSS = """
* { font-family: "HYWenHei-85W", "HYWenHei", "Noto Serif", "Noto Sans Symbols 2", "Noto Sans Symbols", "DejaVu Sans", serif;
    -gtk-icon-shadow: none; text-shadow: none; transition: none; }
window, window.background { background-color: #1B1F2E; color: #ECE5D8; }
headerbar { background-image: linear-gradient(to bottom, #2A3045, #1C2030); border: none;
            border-bottom: 1px solid alpha(#D3BC8E, .55); box-shadow: none; color: #ECE5D8; min-height: 42px; }
headerbar .title { color: #D3BC8E; font-weight: bold; }
headerbar .subtitle { color: alpha(#ECE5D8, .55); }
headerbar button { color: #ECE5D8; background: none; border: none; box-shadow: none; }
headerbar button:hover { color: #D3BC8E; background-color: alpha(#D3BC8E, .12); }

.sidebar { background-image: linear-gradient(to bottom, alpha(#151926, .88), alpha(#262C42, .80));
           border-right: 1px solid alpha(#D3BC8E, .35); padding: 14px 12px; }
.adapter-name { color: #D3BC8E; font-size: 15pt; font-weight: bold; }
.dim, .page-sub, .card-sub, .card-meta { color: alpha(#ECE5D8, .6); }
.card-meta { font-size: 9pt; }
.nav { background: none; background-image: none; border: 1px solid transparent; border-radius: 22px;
       padding: 8px 16px; color: alpha(#ECE5D8, .85); box-shadow: none; }
.nav:hover { color: #ECE5D8; background-color: alpha(#D3BC8E, .12); border-color: alpha(#D3BC8E, .45); }
.nav:checked { color: #2B3047; background-image: linear-gradient(to right, #F3ECDF, #D3BC8E);
               border-color: #FFF3D6; box-shadow: none; }
.chip { background: none; background-image: none; border: 1px solid alpha(#D3BC8E, .4); border-radius: 999px;
        padding: 3px 14px; color: alpha(#ECE5D8, .8); box-shadow: none; }
.chip:hover { border-color: #D3BC8E; color: #ECE5D8; }
.chip:checked { background-color: alpha(#D3BC8E, .9); color: #2B3047; border-color: #FFF3D6; }

.gbtn { background-image: linear-gradient(to bottom, #F5EFE4, #E1D6C2); color: #3B4255;
        border: 2px solid #D3BC8E; border-radius: 999px; padding: 6px 20px; font-weight: bold; box-shadow: none; }
.gbtn label { color: inherit; }
.gbtn:hover { background-image: linear-gradient(to bottom, #FFFBF2, #EDE3CF); border-color: #FFF3D6; }
.gbtn:active, .gbtn:checked { background-image: linear-gradient(to bottom, #D3BC8E, #BFA371); }
.gbtn:disabled { background-image: linear-gradient(to bottom, #8F8A80, #77736B); border-color: #77736B; color: #3B4255; }
.gbtn.dark { background-image: linear-gradient(to bottom, #4C556C, #363D52); color: #ECE5D8;
             border-color: alpha(#D3BC8E, .7); }
.gbtn.dark:hover { background-image: linear-gradient(to bottom, #59627C, #424A61); border-color: #D3BC8E; }
.gbtn.dark:checked { background-image: linear-gradient(to bottom, #6B5B3E, #4B402B); }
.gbtn.dark:disabled { background-image: linear-gradient(to bottom, #3A4052, #2E3343); color: alpha(#ECE5D8, .4);
                      border-color: alpha(#D3BC8E, .25); }
.gbtn.danger { background-image: linear-gradient(to bottom, #4B3438, #362529); color: #FFB4A6; border-color: #C46A5A; }
.gbtn.danger:hover { border-color: #EF7A35; }
.gbtn.small { padding: 2px 14px; font-size: 9pt; min-height: 0; }
.gbtn.mute { padding: 2px 10px; min-width: 22px; }
.gbtn.active { border-color: #5CD8B8; }

list, list row, flowbox, flowboxchild { background: none; background-color: transparent; }
flowboxchild { padding: 0; }
row.devrow { padding: 4px 2px; outline: none; }
row.devrow:selected, row.devrow:hover { background: none; }
.card { background-image: linear-gradient(to right, alpha(#3B4255, .88), alpha(#2C3246, .78));
        border: 1px solid alpha(#D3BC8E, .26); border-radius: 14px; padding: 8px 12px; }
row:hover .card { border-color: alpha(#D3BC8E, .7); }
row:selected .card { border-color: #D3BC8E; background-image: linear-gradient(to right, alpha(#59627C, .95), alpha(#3B4255, .9)); }
.card.connected { border-left: 3px solid #D3BC8E; }
.card.low { border-right: 3px solid #EF7A35; }
.card-title { font-size: 12pt; font-weight: bold; color: #ECE5D8; }
.panel { background-color: alpha(#20253A, .72); border: 1px solid alpha(#D3BC8E, .3); border-radius: 18px; padding: 16px; }
.detail-title { font-size: 24pt; font-weight: bold; color: #ECE5D8; }
.page-title { font-size: 21pt; color: #D3BC8E; font-weight: bold; }
.section { color: #D3BC8E; font-size: 9pt; font-weight: bold; }
.k { color: alpha(#ECE5D8, .5); }
.v { color: #ECE5D8; }
.talent { padding: 3px 6px; border-radius: 8px; background-color: alpha(#ECE5D8, .05); }

.forge { background-image: linear-gradient(to bottom, alpha(#3B4255, .92), alpha(#262B3D, .9));
         border: 1px solid alpha(#D3BC8E, .5); border-radius: 16px; padding: 14px 16px; }
.now-glyph { font-size: 26pt; color: #D3BC8E; min-width: 40px; }
.when { color: #D3BC8E; font-weight: bold; font-size: 9pt; min-width: 48px; }
.echo { padding: 12px 16px; }
.echo:hover { border-color: alpha(#D3BC8E, .6); }
.echo.singing { border-left: 3px solid #5CD8B8;
                background-image: linear-gradient(to right, alpha(#2F4F55, .9), alpha(#2C3246, .8)); }
.echo.focus { border-color: #FFE7B0; }
.badge { font-size: 9pt; }

entry { background-color: alpha(#11141F, .75); background-image: none; color: #ECE5D8; border: 1px solid alpha(#D3BC8E, .45);
        border-radius: 999px; padding: 5px 14px; box-shadow: none; caret-color: #D3BC8E; }
entry:focus { border-color: #D3BC8E; }
entry image { color: #D3BC8E; }
switch { background-image: none; background-color: alpha(#11141F, .8); border: 1px solid alpha(#D3BC8E, .5);
         border-radius: 999px; color: transparent; }
switch:checked { background-color: #D3BC8E; border-color: #FFF3D6; }
switch slider { background-image: none; background-color: #ECE5D8; border-radius: 999px; border: 1px solid #D3BC8E; box-shadow: none; }
scale trough { background-color: alpha(#11141F, .8); border-radius: 999px; min-height: 6px; border: 1px solid alpha(#D3BC8E, .35); }
scale highlight { background-image: linear-gradient(to right, #A88E5E, #F2DFAF); border-radius: 999px; }
scale slider { background-image: none; background-color: #ECE5D8; border: 2px solid #D3BC8E; border-radius: 999px;
               min-width: 16px; min-height: 16px; box-shadow: none; }
scale slider:hover { background-color: #FFF8EA; border-color: #FFE7B0; }
scale:disabled { opacity: .5; }
scale marks, scale value { color: alpha(#ECE5D8, .5); }
scale mark indicator { color: alpha(#D3BC8E, .6); min-height: 4px; }
progressbar trough { background-color: alpha(#11141F, .8); border-radius: 999px; min-height: 8px; border: none; }
progressbar progress { background-image: linear-gradient(to right, #5CD8B8, #D3BC8E); border-radius: 999px; min-height: 8px; border: none; }
scrollbar, scrollbar trough { background: none; border: none; }
scrolledwindow.gscroll-win, scrolledwindow.gscroll-win viewport { background: none; background-color: transparent; border: none; box-shadow: none; }
scrollbar.gscroll { min-width: 12px; background: none; border: none; padding: 0; margin: 0; }
scrollbar.gscroll button { min-width: 0; min-height: 0; padding: 0; margin: 0; border: none; background: none; opacity: 0; }
scrollbar.gscroll trough { min-width: 12px; background-color: transparent; border: none;
        background-image: linear-gradient(to right, transparent 5px, alpha(#D3BC8E, .55) 5px, alpha(#D3BC8E, .55) 7px, transparent 7px); }
scrollbar.gscroll slider { min-width: 6px; min-height: 48px; margin: 0 3px; border: 1px solid #FFF3D6; border-radius: 999px;
        background-image: linear-gradient(to bottom, #F5EFE4, #D3BC8E); background-color: #D3BC8E; box-shadow: none; }
scrollbar.gscroll slider:hover { min-width: 8px; margin: 0 2px; }
scrollbar.gscroll slider:active { background-image: linear-gradient(to bottom, #FFF3D6, #E8CF98); }
scrollbar slider { background-color: alpha(#D3BC8E, .45); border-radius: 999px; min-width: 5px; min-height: 5px; border: none; }
combobox button, spinbutton, spinbutton button, filechooserbutton button {
        background-image: none; background-color: alpha(#11141F, .75); color: #ECE5D8;
        border: 1px solid alpha(#D3BC8E, .45); border-radius: 999px; box-shadow: none; }
combobox:disabled button { color: alpha(#ECE5D8, .4); border-color: alpha(#D3BC8E, .2); }
spinbutton entry { border: none; background: none; }
menu, .menu, .popup menu, popover { background-color: #232839; color: #ECE5D8; border: 1px solid alpha(#D3BC8E, .5); }
menuitem:hover { background-color: alpha(#D3BC8E, .25); }
check { background-image: none; background-color: alpha(#11141F, .8); border: 1px solid #D3BC8E; border-radius: 4px; }
check:checked { background-color: #D3BC8E; color: #2B3047; }
tooltip, tooltip.background { background-color: #1B1F2E; border: 1px solid #D3BC8E; color: #ECE5D8; border-radius: 8px; }

.toast { background-image: linear-gradient(to right, alpha(#10131D, 0), alpha(#10131D, .94) 14%, alpha(#10131D, .94) 86%, alpha(#10131D, 0));
         border-top: 1px solid alpha(#D3BC8E, .65); border-bottom: 1px solid alpha(#D3BC8E, .65); padding: 10px 70px; }
.toast-title { color: #D3BC8E; font-weight: bold; font-size: 12pt; }
.toast-body { color: #ECE5D8; }
.toast-glyph { font-size: 18pt; color: #D3BC8E; }
.t-ok { color: #A5C83B; } .t-err { color: #EF7A35; } .t-warn { color: #F2B723; }

.gdialog { background-image: linear-gradient(to bottom, #2D3349, #1E2233); border: 2px solid #D3BC8E; border-radius: 6px; }
.dlg-title { color: #D3BC8E; font-size: 17pt; font-weight: bold; }

.diag { padding: 10px 14px; }
.orb { font-size: 18pt; min-width: 28px; }
.ok { color: #A5C83B; } .warn { color: #F2B723; } .bad { color: #EF7A35; } .pending { color: alpha(#ECE5D8, .4); }
textview.logs, textview.logs text { background-color: alpha(#0E1018, .85); color: #CFC8BA; font-size: 9pt; }
"""


class ArchiveApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.win = None
        S, N = GLib.OptionArg.STRING, GLib.OptionArg.NONE
        self.add_main_option("page", 0, GLib.OptionFlags.NONE, S,
                             "Open a page: companions|atlas|echoes|transmission|statue|settings", "NAME")
        self.add_main_option("device", 0, GLib.OptionFlags.NONE, S, "Select a device by MAC", "MAC")
        self.add_main_option("pair", 0, GLib.OptionFlags.NONE, S, "Pair a device by MAC (GUI agent)", "MAC")
        self.add_main_option("scan", 0, GLib.OptionFlags.NONE, N, "Start Elemental Sight", None)
        self.add_main_option("background", 0, GLib.OptionFlags.NONE, N,
                             "Start hidden: pairing agent + harmony rules keep running", None)
        self.add_main_option("version", 0, GLib.OptionFlags.NONE, N, "Print version", None)

    def do_handle_local_options(self, options):
        if options.contains("version"):
            print("Teyvat Archive", VERSION)
            return 0
        return -1

    def do_startup(self):
        Gtk.Application.do_startup(self)
        s = Gtk.Settings.get_default()
        s.set_property("gtk-theme-name", "Adwaita")
        s.set_property("gtk-application-prefer-dark-theme", True)
        prov = Gtk.CssProvider()
        try:
            prov.load_from_data(CSS.encode())
        except GLib.Error as e:
            print("CSS warning:", e.message, file=sys.stderr)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def do_command_line(self, cl):
        opts = cl.get_options_dict().end().unpack()
        bg = bool(opts.get("background"))
        if not self.win:
            self.win = ArchiveWindow(self, visible=not bg)
        if bg:                       # vigil start (autostart) or a repeated --background: stay hidden
            if not CONFIG.vigil:
                CONFIG.vigil = True  # started hidden -> closing must not quit what nobody can see
            return 0
        self.win.present()
        if opts.get("page"):
            self.win.goto(opts["page"])
        dev = opts.get("device")
        if dev:
            d = self.win.dev_by_mac(dev)
            if d:
                self.win.select_device(d.path)
            else:
                self.win.pending_select = dev
        if opts.get("pair"):
            later(600, self.win.pair_by_mac, opts["pair"])
        if opts.get("scan"):
            later(500, self.win.toggle_scan)
        return 0


def main():
    return ArchiveApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
