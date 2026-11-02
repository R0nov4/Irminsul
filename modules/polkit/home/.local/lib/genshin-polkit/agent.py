#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genshin-style Polkit authentication agent (admin-password dialog).

  * Real agent: registers with polkitd and shows the dialog whenever something
    (pkexec, pacman GUIs, Thunar mounts, NetworkManager, ...) asks for admin rights.
  * Wayland: draws as a full-screen dimmed overlay via gtk-layer-shell and grabs the
    keyboard exclusively (nothing else can steal keystrokes while you type a password).
  * Idle cost is zero: no timers or animations run unless a dialog is on screen.

Usage:
    agent.py              run as the polkit agent (what autostart does)
    agent.py --preview    show the dialog with a fake request (first password is
                          rejected on purpose so you can see the error/shake animation)

Theme:  ~/.config/genshin-polkit/theme      one word: genshin | ronova
        ~/.config/genshin-polkit/custom.css extra CSS loaded last (optional)
        env GENSHIN_POLKIT_THEME overrides the file
        ~/.config/genshin-polkit/follow     theme | classic | gold   (default: theme)
                                            theme = active Theme Builder accent, classic = the file above,
                                            gold = plain Genshin cream/gold
Both are re-read every time a dialog opens, so no restart is needed.
"""
import os
import sys
import ctypes.util

# gtk-layer-shell has to be loaded before libwayland-client, which in Python means
# re-executing ourselves once with LD_PRELOAD.
if not os.environ.get("GENSHIN_POLKIT_REEXEC"):
    os.environ["GENSHIN_POLKIT_REEXEC"] = "1"
    _ls = ctypes.util.find_library("gtk-layer-shell")
    if _ls:
        _pre = os.environ.get("LD_PRELOAD", "")
        if _ls not in _pre:
            os.environ["LD_PRELOAD"] = (_ls + " " + _pre).strip()
            os.execv(sys.executable, [sys.executable] + sys.argv)

# If the agent starts before the compositor is up, Gtk fails to initialise, the agent
# still registers with polkitd, and then rejects every request. Wait for the socket first.
def _wait_for_display(timeout=60.0):
    import glob
    import stat
    import time
    rt = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
    end = time.time() + timeout
    while True:
        names = []
        if os.environ.get("WAYLAND_DISPLAY"):
            names.append(os.environ["WAYLAND_DISPLAY"])
        names += [os.path.basename(p) for p in sorted(glob.glob(os.path.join(rt, "wayland-*")))
                  if not p.endswith(".lock")]
        for n in names:
            p = n if os.path.isabs(n) else os.path.join(rt, n)
            try:
                if stat.S_ISSOCK(os.stat(p).st_mode):
                    os.environ["WAYLAND_DISPLAY"] = n
                    return True
            except OSError:
                pass
        if time.time() >= end:
            return False
        time.sleep(0.25)


if not _wait_for_display():
    if not os.environ.get("DISPLAY"):
        print("genshin-polkit: no display after 60s, giving up", file=sys.stderr, flush=True)
        sys.exit(1)

import fcntl
import grp
import pwd
import signal

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Polkit", "1.0")
gi.require_version("PolkitAgent", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Polkit, PolkitAgent  # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell as LS  # noqa: E402
except (ValueError, ImportError):
    LS = None

import cairo  # noqa: E402,F401  (needed so the 'draw' signal hands us a cairo context)

APP_NAME = "genshin-polkit"
OBJECT_PATH = "/org/genshin/PolicyKit1/AuthenticationAgent"
CFG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "genshin-polkit")

# --------------------------------------------------------------------------- themes
THEMES = {
    # the cream / slate-blue / gold look of the in-game dialogs
    "genshin": dict(panel="#3B4255", panel2="#2D3345", cream="#ECE5D8", ink="#495366",
                    gold="#D3BC8E", accent="#FFCB33", err="#FF9B8A", scrim="rgba(10,12,22,0.62)"),
    # red / black variant for the Ronova theme
    "ronova": dict(panel="#34191F", panel2="#22100F", cream="#F3E6E1", ink="#4A262C",
                   gold="#E2A59A", accent="#FF5A64", err="#FFB4A8", scrim="rgba(8,3,5,0.68)"),
}


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgba(h, a):
    r, g, b = _rgb(h)
    return "rgba(%d,%d,%d,%s)" % (r, g, b, a)


def _base_theme():
    name = os.environ.get("GENSHIN_POLKIT_THEME", "").strip().lower()
    if not name:
        try:
            with open(os.path.join(CFG_DIR, "theme")) as f:
                name = f.read().strip().lower()
        except OSError:
            name = "genshin"
    return name if name in THEMES else "genshin", THEMES.get(name, THEMES["genshin"])


# GP_FOLLOW: colours follow the active Theme Builder accent
# (res_apply in resonance-lib.sh writes HEX / HEX_HI / HEX_LO to element-override.conf)
FOLLOW_FILE = os.path.join(CFG_DIR, "follow")
ELEMENT_FILE = os.path.expanduser("~/.config/hypr-genshin/element-override.conf")


def _follow_mode():  # GP_FOLLOW_V2
    try:
        with open(FOLLOW_FILE) as f:
            v = f.read().strip().lower()
    except OSError:
        return "theme"
    if v in ("gold", "genshin"):
        return "gold"
    if v in ("classic", "off", "0", "no", "false"):
        return "classic"
    return "theme"


def _mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ra, rb))


def _follow_palette(base):
    import colorsys
    import re as _re
    vals = {}
    try:
        with open(ELEMENT_FILE) as f:
            for line in f:
                m = _re.match(r'^(HEX|HEX_HI|HEX_LO)="(#[0-9a-fA-F]{6})"', line.strip())
                if m:
                    vals[m.group(1)] = m.group(2)
    except OSError:
        return None
    hx = vals.get("HEX")
    if not hx:
        return None
    h, s, v = colorsys.rgb_to_hsv(*[x / 255.0 for x in _rgb(hx)])
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * 1.25 + 0.12), 1.0)
    t = dict(base)
    t["panel"] = _mix(base["panel"], hx, 0.14)
    t["panel2"] = _mix(base["panel2"], hx, 0.10)
    t["ink"] = _mix(base["ink"], hx, 0.08)
    t["gold"] = hx
    t["accent"] = "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
    return t


def current_theme():
    name, t = _base_theme()
    if os.environ.get("GENSHIN_POLKIT_THEME", "").strip():
        return name, t
    mode = _follow_mode()
    if mode == "gold":
        return "genshin", THEMES["genshin"]
    if mode == "classic":
        return name, t
    pal = _follow_palette(THEMES["genshin"])
    return ("follow", pal) if pal else (name, t)


def build_css(t):
    c = t
    return """
* { font-family: "HYWenHei", "HYWenHei-85W", "SDK_SC_Web", "Noto Sans", "DejaVu Sans", sans-serif; }
window.gp-scrim  { background-color: %(scrim)s; }
window.gp-plain  { background-color: transparent; }
window.gp-opaque { background-color: %(panel2)s; }

.gp-card {
  background-image: linear-gradient(to bottom, %(panel)s, %(panel2)s);
  border: 2px solid %(cream)s; border-radius: 16px; padding: 6px;
  box-shadow: 0 22px 64px rgba(0,0,0,0.55);
}
.gp-inner { border: 1px solid %(gold_50)s; border-radius: 11px; padding: 26px 32px 24px 32px; }
.gp-title   { color: %(cream)s; font-size: 22px; font-weight: bold; }
.gp-msg     { color: %(cream)s; font-size: 14px; }
.gp-details { background-color: rgba(0,0,0,0.20); border: 1px solid %(gold_25)s; border-radius: 9px; padding: 9px 13px; }
.gp-key     { color: %(cream_55)s; font-size: 11px; }
.gp-val     { color: %(cream_90)s; font-size: 12px; }
.gp-label   { color: %(gold)s; font-size: 12px; }
.gp-status  { color: %(cream_70)s; font-size: 12px; }
.gp-status.err  { color: %(err)s; }
.gp-status.info { color: %(accent)s; }

entry.gp-entry {
  background-image: none; background-color: %(cream)s; color: %(ink)s;
  caret-color: %(ink)s; border: 2px solid transparent; border-radius: 11px;
  padding: 9px 15px; min-height: 22px; font-size: 15px; box-shadow: none;
  transition: border-color 120ms ease;
}
entry.gp-entry:focus { border-color: %(accent)s; }
entry.gp-entry.err   { border-color: %(err)s; }
entry.gp-entry:disabled { opacity: 0.65; }
entry.gp-entry selection { background-color: %(ink)s; color: %(cream)s; }

button.gp-btn {
  background-image: none; background-color: %(cream)s; color: %(ink)s;
  border: none; border-radius: 24px; padding: 8px 18px; font-size: 14px; font-weight: bold;
  text-shadow: none; box-shadow: 0 2px 0 rgba(0,0,0,0.28);
  transition: background-color 120ms ease;
}
button.gp-btn:hover    { background-color: %(accent)s; }
button.gp-btn:active   { background-color: %(gold)s; box-shadow: none; }
button.gp-btn:disabled { opacity: 0.45; box-shadow: none; }
button.gp-btn:disabled:hover { background-color: %(cream)s; }
.gp-ico { background-color: %(ink)s; color: %(cream)s; border-radius: 99px; min-width: 20px; min-height: 20px; font-size: 11px; }

button.gp-chip {
  background-image: none; background-color: transparent; color: %(cream)s;
  border: 1px solid %(gold_50)s; border-radius: 99px; padding: 3px 14px; font-size: 12px;
  box-shadow: none; text-shadow: none;
}
button.gp-chip:hover   { border-color: %(accent)s; }
button.gp-chip:checked { background-color: %(accent)s; color: %(ink)s; border-color: %(accent)s; font-weight: bold; }
""" % dict(
        c,
        gold_50=_rgba(c["gold"], 0.5), gold_25=_rgba(c["gold"], 0.25),
        cream_55=_rgba(c["cream"], 0.55), cream_70=_rgba(c["cream"], 0.7), cream_90=_rgba(c["cream"], 0.9),
    )


# --------------------------------------------------------------------------- helpers
def identity_name(ident):
    if isinstance(ident, Polkit.UnixUser):
        try:
            return pwd.getpwuid(ident.get_uid()).pw_name
        except KeyError:
            return str(ident.get_uid())
    return ident.to_string()


def expand_identities(identities):
    """Groups (e.g. wheel) -> users, drop duplicates, keep order."""
    out, seen = [], set()
    for ident in identities:
        cands = [ident]
        if isinstance(ident, Polkit.UnixGroup):
            cands = []
            try:
                for n in grp.getgrgid(ident.get_gid()).gr_mem:
                    u = Polkit.UnixUser.new_for_name(n)
                    if u:
                        cands.append(u)
            except KeyError:
                pass
        for c in cands:
            k = c.to_string()
            if k not in seen:
                seen.add(k)
                out.append(c)
    return out


def default_identity_index(idents):
    me = os.getuid()
    for i, x in enumerate(idents):
        if isinstance(x, Polkit.UnixUser) and x.get_uid() == me:
            return i
    for i, x in enumerate(idents):
        if isinstance(x, Polkit.UnixUser) and x.get_uid() == 0:
            return i
    return 0


def describe_request(details, action_id):
    """(label, value) rows shown under the message. Helps spot what is really asking."""
    def look(k):
        try:
            return details.lookup(k)
        except Exception:
            return None

    rows = []
    prog = look("command_line") or look("program")
    if not prog:
        pid = look("polkit.caller-pid")
        if pid and pid.isdigit():
            try:
                with open("/proc/%s/cmdline" % pid, "rb") as f:
                    prog = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            except OSError:
                pass
    if prog:
        rows.append(("Requested by", prog[:240]))
    rows.append(("Action", action_id))
    return rows


# --------------------------------------------------------------------------- drawing
def draw_emblem(theme):
    gold, cream, panel2 = _rgb(theme["gold"]), _rgb(theme["cream"]), _rgb(theme["panel2"])

    def f(c):
        return tuple(x / 255.0 for x in c)

    def on_draw(w, cr):
        W, H = w.get_allocated_width(), w.get_allocated_height()
        cx, cy = W / 2.0, H / 2.0
        cr.set_source_rgb(*f(panel2))
        cr.arc(cx, cy, 28, 0, 6.2832)
        cr.fill()
        cr.set_source_rgba(*f(gold), 0.95)
        cr.set_line_width(2)
        cr.arc(cx, cy, 28, 0, 6.2832)
        cr.stroke()
        cr.set_source_rgba(*f(gold), 0.4)
        cr.set_line_width(1)
        cr.arc(cx, cy, 23.5, 0, 6.2832)
        cr.stroke()

        # four-point sparkle: quadratic curves between the tips, control point = centre
        R = 17.0
        tips = [(cx, cy - R), (cx + R, cy), (cx, cy + R), (cx - R, cy)]
        cr.move_to(*tips[0])
        for i in range(4):
            p0, p1 = tips[i], tips[(i + 1) % 4]
            c1 = (p0[0] + (cx - p0[0]) * 2 / 3.0, p0[1] + (cy - p0[1]) * 2 / 3.0)
            c2 = (p1[0] + (cx - p1[0]) * 2 / 3.0, p1[1] + (cy - p1[1]) * 2 / 3.0)
            cr.curve_to(c1[0], c1[1], c2[0], c2[1], p1[0], p1[1])
        cr.close_path()
        cr.set_source_rgb(*f(cream))
        cr.fill_preserve()
        cr.set_source_rgb(*f(gold))
        cr.set_line_width(1)
        cr.stroke()
        return False

    return on_draw


def draw_ornament(theme):
    r, g, b = [x / 255.0 for x in _rgb(theme["gold"])]

    def on_draw(w, cr):
        W, H = w.get_allocated_width(), w.get_allocated_height()
        cx, cy = W / 2.0, H / 2.0
        for side in (-1, 1):
            grad = cairo.LinearGradient(cx + side * 14, 0, cx + side * (W / 2.0), 0)
            grad.add_color_stop_rgba(0, r, g, b, 0.9)
            grad.add_color_stop_rgba(1, r, g, b, 0.0)
            cr.set_source(grad)
            cr.set_line_width(1)
            cr.move_to(cx + side * 14, cy + 0.5)
            cr.line_to(cx + side * (W / 2.0), cy + 0.5)
            cr.stroke()
        cr.set_source_rgb(r, g, b)
        for dx, s in ((0, 4.5), (-9, 2.2), (9, 2.2)):
            cr.move_to(cx + dx, cy - s)
            cr.line_to(cx + dx + s, cy)
            cr.line_to(cx + dx, cy + s)
            cr.line_to(cx + dx - s, cy)
            cr.close_path()
            cr.fill()
        return False

    return on_draw


# --------------------------------------------------------------------------- dialog
class FakeSession:
    """Stand-in for PolkitAgent.Session used by --preview (never authenticates anything)."""

    def __init__(self, dlg):
        self.dlg = dlg
        self.dead = False

    def initiate(self):
        GLib.timeout_add(200, self._ask)

    def _ask(self):
        if not self.dead:
            self.dlg._on_request(self, "Password:", False)
        return False

    def response(self, text):
        GLib.timeout_add(650, self._answer)

    def _answer(self):
        if self.dead:
            return False
        self.dlg.fake_attempts += 1
        self.dlg._on_completed(self, self.dlg.fake_attempts >= 2)
        return False

    def cancel(self):
        self.dead = True


class Request:
    def __init__(self, action_id, message, details, cookie, identities, cancellable, task):
        self.action_id, self.message, self.details = action_id, message, details
        self.cookie, self.identities = cookie, identities
        self.cancellable, self.task = cancellable, task


class Dialog(Gtk.Window):
    def __init__(self, req, on_closed, preview=False):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.req, self.on_closed, self.preview = req, on_closed, preview
        self.fake_attempts = 0
        self.session = None
        self.done = False
        self.awaiting = False
        self.status_text, self.status_kind = "", ""
        self.idents = expand_identities(req.identities) or [Polkit.UnixUser.new(0)]
        self.ident_idx = default_identity_index(self.idents)

        self.theme_name, self.theme = current_theme()
        self._apply_css()

        self.use_layer = bool(LS) and (not hasattr(LS, "is_supported") or LS.is_supported())
        self.set_title("Authentication Required")
        self.set_app_paintable(True)
        scr = self.get_screen()
        vis = scr.get_rgba_visual()
        composited = bool(vis) and scr.is_composited()
        if composited:
            self.set_visual(vis)
        self.set_decorated(False)
        self.get_style_context().add_class(
            "gp-scrim" if self.use_layer else ("gp-plain" if composited else "gp-opaque"))

        if self.use_layer:
            LS.init_for_window(self)
            LS.set_namespace(self, APP_NAME)
            LS.set_layer(self, LS.Layer.OVERLAY)
            for e in (LS.Edge.TOP, LS.Edge.BOTTOM, LS.Edge.LEFT, LS.Edge.RIGHT):
                LS.set_anchor(self, e, True)
            LS.set_exclusive_zone(self, -1)
            try:
                LS.set_keyboard_mode(self, LS.KeyboardMode.EXCLUSIVE)
            except AttributeError:
                LS.set_keyboard_interactivity(self, True)
        else:
            self.set_position(Gtk.WindowPosition.CENTER)
            self.set_keep_above(True)
            self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
            self.set_skip_taskbar_hint(True)

        self._build()
        self.connect("key-press-event", self._on_key)
        self.connect("key-release-event", lambda *a: self._refresh_status())
        self.connect("delete-event", lambda *a: (self._cancel(), True)[1])
        if req.cancellable is not None:
            req.cancellable.connect(lambda c: GLib.idle_add(self._cancel))

        self.card.set_opacity(0.0)
        self.show_all()
        self._fade_in()
        self._new_session()

    # ---- ui
    def _apply_css(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(build_css(self.theme).encode())
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(screen, prov, Gtk.STYLE_PROVIDER_PRIORITY_USER - 1)
        self._providers = [prov]
        custom = os.path.join(CFG_DIR, "custom.css")
        if os.path.exists(custom):
            p2 = Gtk.CssProvider()
            try:
                p2.load_from_path(custom)
                Gtk.StyleContext.add_provider_for_screen(screen, p2, Gtk.STYLE_PROVIDER_PRIORITY_USER)
                self._providers.append(p2)
            except GLib.Error as e:
                print("custom.css ignored:", e.message, file=sys.stderr)

    def _drop_css(self):
        screen = Gdk.Screen.get_default()
        for p in getattr(self, "_providers", []):
            Gtk.StyleContext.remove_provider_for_screen(screen, p)

    def _label(self, text, cls, **kw):
        l = Gtk.Label(label=text, **kw)
        l.get_style_context().add_class(cls)
        return l

    def _build(self):
        outer = Gtk.Box()
        outer.set_halign(Gtk.Align.CENTER)
        outer.set_valign(Gtk.Align.CENTER)
        self.add(outer)

        card = self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.get_style_context().add_class("gp-card")
        card.set_size_request(490, -1)
        outer.pack_start(card, False, False, 0)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        inner.get_style_context().add_class("gp-inner")
        card.pack_start(inner, True, True, 0)

        emblem = Gtk.DrawingArea()
        emblem.set_size_request(64, 64)
        emblem.set_halign(Gtk.Align.CENTER)
        emblem.connect("draw", draw_emblem(self.theme))
        inner.pack_start(emblem, False, False, 0)

        t = self._label("Authentication Required", "gp-title")
        t.set_margin_top(10)
        inner.pack_start(t, False, False, 0)

        orn = Gtk.DrawingArea()
        orn.set_size_request(300, 14)
        orn.set_halign(Gtk.Align.CENTER)
        orn.set_margin_top(8)
        orn.set_margin_bottom(10)
        orn.connect("draw", draw_ornament(self.theme))
        inner.pack_start(orn, False, False, 0)

        msg = self._label(self.req.message or "An application is requesting administrator privileges.", "gp-msg")
        msg.set_line_wrap(True)
        msg.set_justify(Gtk.Justification.CENTER)
        msg.set_max_width_chars(46)
        msg.set_margin_bottom(14)
        inner.pack_start(msg, False, False, 0)

        grid = Gtk.Grid(column_spacing=14, row_spacing=4)
        grid.get_style_context().add_class("gp-details")
        for i, (k, v) in enumerate(describe_request(self.req.details, self.req.action_id)):
            kl = self._label(k, "gp-key", xalign=0)
            kl.set_valign(Gtk.Align.START)
            vl = self._label(v, "gp-val", xalign=0)
            vl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            vl.set_max_width_chars(44)
            vl.set_tooltip_text(v)
            grid.attach(kl, 0, i, 1, 1)
            grid.attach(vl, 1, i, 1, 1)
        inner.pack_start(grid, False, False, 0)

        self.chips = []
        if len(self.idents) > 1:
            row = Gtk.Box(spacing=8)
            row.set_margin_top(14)
            row.pack_start(self._label("Authenticate as", "gp-label"), False, False, 0)
            for i, ident in enumerate(self.idents[:6]):
                b = Gtk.ToggleButton(label=identity_name(ident))
                b.get_style_context().add_class("gp-chip")
                b.set_active(i == self.ident_idx)
                b.connect("clicked", self._on_chip, i)
                row.pack_start(b, False, False, 0)
                self.chips.append(b)
            inner.pack_start(row, False, False, 0)

        self.prompt = self._label("", "gp-label", xalign=0)
        self.prompt.set_margin_top(16)
        self.prompt.set_margin_bottom(6)
        inner.pack_start(self.prompt, False, False, 0)
        self._set_prompt("Password")

        self.entry = Gtk.Entry()
        self.entry.get_style_context().add_class("gp-entry")
        self.entry.set_visibility(False)
        self.entry.set_invisible_char("\u25cf")
        self.entry.set_placeholder_text("Enter password")
        self.entry.set_property("caps-lock-warning", False)
        self.entry.set_sensitive(False)
        self.entry.connect("activate", lambda *a: self._submit())
        self.entry.connect("changed", lambda *a: self._sync_buttons())
        inner.pack_start(self.entry, False, False, 0)

        self.status = self._label("", "gp-status", xalign=0)
        self.status.set_size_request(-1, 22)
        self.status.set_margin_top(7)
        inner.pack_start(self.status, False, False, 0)

        btns = Gtk.Box(spacing=14, homogeneous=True)
        btns.set_margin_top(8)
        self.btn_cancel = self._button("\u2715", "Cancel", self._cancel)
        self.btn_ok = self._button("\u2713", "Confirm", self._submit)
        btns.pack_start(self.btn_cancel, True, True, 0)
        btns.pack_start(self.btn_ok, True, True, 0)
        inner.pack_start(btns, False, False, 0)
        self._sync_buttons()

    def _button(self, icon, text, cb):
        b = Gtk.Button()
        b.get_style_context().add_class("gp-btn")
        b.set_relief(Gtk.ReliefStyle.NONE)
        b.set_can_focus(False)
        box = Gtk.Box(spacing=10)
        box.set_halign(Gtk.Align.CENTER)
        box.pack_start(self._label(icon, "gp-ico"), False, False, 0)
        box.pack_start(Gtk.Label(label=text), False, False, 0)
        b.add(box)
        b.connect("clicked", lambda *a: cb())
        return b

    def _set_prompt(self, text):
        text = (text or "Password").strip().rstrip(":").strip() or "Password"
        who = identity_name(self.idents[self.ident_idx])
        if text.lower() == "password":
            text = "Password for %s" % who
        self.prompt.set_text(text)

    def _sync_buttons(self):
        self.btn_ok.set_sensitive(self.awaiting and bool(self.entry.get_text()))

    # ---- status line
    def _set_status(self, text="", kind=""):
        self.status_text, self.status_kind = text, kind
        self._refresh_status()

    def _refresh_status(self):
        ctx = self.status.get_style_context()
        for k in ("err", "info"):
            ctx.remove_class(k)
        text, kind = self.status_text, self.status_kind
        if not text:
            try:
                km = Gdk.Keymap.get_for_display(Gdk.Display.get_default())
                if km.get_caps_lock_state():
                    text, kind = "Caps Lock is on", "info"
            except Exception:
                pass
        if kind:
            ctx.add_class(kind)
        self.status.set_text(text)

    # ---- animations (only while a dialog is open; ~10 frames each)
    def _fade_in(self):
        state = {"i": 0}

        def step():
            state["i"] += 1
            p = min(state["i"] / 10.0, 1.0)
            e = 1 - (1 - p) ** 3
            self.card.set_opacity(e)
            self.card.set_margin_top(int(18 * (1 - e)))
            return p < 1.0

        GLib.timeout_add(16, step)

    def _shake(self):
        offs = iter([-12, 12, -9, 9, -5, 5, -2, 0])

        def step():
            try:
                o = next(offs)
            except StopIteration:
                return False
            self.card.set_margin_start(max(0, o) * 2)
            self.card.set_margin_end(max(0, -o) * 2)
            return True

        GLib.timeout_add(40, step)

    # ---- session handling
    def _kill_session(self):
        s, self.session = self.session, None
        self.awaiting = False
        if s is not None:
            try:
                s.cancel()
            except Exception:
                pass

    def _new_session(self):
        self._kill_session()
        if self.preview:
            s = FakeSession(self)
        else:
            s = PolkitAgent.Session.new(self.idents[self.ident_idx], self.req.cookie)
            s.connect("request", lambda se, r, echo: self._on_request(se, r, echo))
            s.connect("show-error", lambda se, t: self._on_text(se, t, "err"))
            s.connect("show-info", lambda se, t: self._on_text(se, t, "info"))
            s.connect("completed", lambda se, ok: self._on_completed(se, ok))
        self.session = s
        self.entry.set_sensitive(False)
        s.initiate()

    def _on_request(self, sess, prompt, echo):
        if sess is not self.session or self.done:
            return
        self._set_prompt(prompt)
        self.entry.set_visibility(bool(echo))
        self.entry.set_text("")
        self.entry.set_sensitive(True)
        self.entry.grab_focus()
        self.awaiting = True
        self._sync_buttons()

    def _on_text(self, sess, text, kind):
        if sess is self.session and not self.done and text:
            self._set_status(text.strip(), kind)

    def _on_completed(self, sess, gained):
        if sess is not self.session or self.done:
            return
        if gained:
            self._finish(True)
            return
        self.entry.get_style_context().add_class("err")
        self._set_status("Incorrect password. Please try again.", "err")
        self._shake()
        self._new_session()

    def _on_chip(self, btn, idx):
        if idx == self.ident_idx and btn.get_active():
            return
        self.ident_idx = idx
        for i, b in enumerate(self.chips):
            b.handler_block_by_func(self._on_chip)
            b.set_active(i == idx)
            b.handler_unblock_by_func(self._on_chip)
        self._set_status("")
        self._set_prompt("Password")
        self._new_session()

    def _submit(self):
        text = self.entry.get_text()
        if not (self.awaiting and text and self.session):
            return
        self.awaiting = False
        self.entry.get_style_context().remove_class("err")
        self.entry.set_sensitive(False)
        self._sync_buttons()
        self._set_status("Verifying\u2026", "info")
        self.session.response(text)
        self.entry.set_text("")

    def _on_key(self, w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self._cancel()
            return True
        GLib.idle_add(self._refresh_status)
        return False

    # ---- finishing
    def _finish(self, ok):
        if self.done:
            return
        self.done = True
        self._kill_session() if not ok else None
        task = self.req.task
        if task is not None:
            if ok:
                GLib.idle_add(lambda t=task: (t.return_boolean(True), False)[1])
            else:
                err = GLib.Error.new_literal(Polkit.Error.quark(), "Authentication dialog was dismissed by the user",
                                             Polkit.Error.CANCELLED)
                GLib.idle_add(lambda t=task, e=err: (t.return_error(e), False)[1])
        self.entry.set_text("")
        self._drop_css()
        self.destroy()
        self.on_closed(self, ok)

    def _cancel(self):
        if not self.done:
            self._finish(False)
        return False


# --------------------------------------------------------------------------- agent
# We speak org.freedesktop.PolicyKit1.AuthenticationAgent over D-Bus ourselves instead of
# subclassing PolkitAgent.Listener: with PyGObject 3.58 the listener vfunc receives a C
# callback whose user_data is NULL, and libpolkit-agent crashes in auth_cb
# (polkitagentlistener.c:605). PolkitAgent.Session (the password part) is unaffected.
AGENT_XML = """<node>
  <interface name="org.freedesktop.PolicyKit1.AuthenticationAgent">
    <method name="BeginAuthentication">
      <arg type="s" name="action_id" direction="in"/>
      <arg type="s" name="message" direction="in"/>
      <arg type="s" name="icon_name" direction="in"/>
      <arg type="a{ss}" name="details" direction="in"/>
      <arg type="s" name="cookie" direction="in"/>
      <arg type="a(sa{sv})" name="identities" direction="in"/>
    </method>
    <method name="CancelAuthentication">
      <arg type="s" name="cookie" direction="in"/>
    </method>
  </interface>
</node>"""


class _DBusTask:
    """Offers the two calls Dialog makes on the old Gio.Task, answered over D-Bus."""

    def __init__(self, invocation):
        self.inv = invocation
        self.sent = False

    def return_boolean(self, _ok=True):
        if not self.sent:
            self.sent = True
            self.inv.return_value(None)

    def return_error(self, err):
        if self.sent:
            return
        self.sent = True
        code = getattr(err, "code", Polkit.Error.FAILED)
        name = ("org.freedesktop.PolicyKit1.Error.Cancelled" if code == Polkit.Error.CANCELLED
                else "org.freedesktop.PolicyKit1.Error.Failed")
        self.inv.return_dbus_error(name, getattr(err, "message", "") or "authentication failed")


class Agent:
    def __init__(self):
        self.queue = []
        self.current = None
        self.by_cookie = {}

    def on_call(self, conn, sender, path, iface, method, params, invocation):
        try:
            if method == "BeginAuthentication":
                action_id, message, _icon, details, cookie, idents = params.unpack()
                det = Polkit.Details()
                for k, v in details.items():
                    det.insert(k, v)
                identities = []
                for kind, d in idents:
                    if kind == "unix-user":
                        identities.append(Polkit.UnixUser.new(int(d["uid"])))
                    elif kind == "unix-group":
                        identities.append(Polkit.UnixGroup.new(int(d["gid"])))
                req = Request(action_id, message, det, cookie, identities, Gio.Cancellable(), _DBusTask(invocation))
                self.by_cookie[cookie] = req
                self.queue.append(req)
                GLib.idle_add(self._pump)
            elif method == "CancelAuthentication":
                (cookie,) = params.unpack()
                req = self.by_cookie.get(cookie)
                if req is not None:
                    req.cancellable.cancel()
                invocation.return_value(None)
            else:
                invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", str(method))
        except Exception as e:  # never leave polkit hanging on a bug here
            print("agent call failed:", repr(e), file=sys.stderr, flush=True)
            invocation.return_dbus_error("org.freedesktop.PolicyKit1.Error.Failed", str(e))

    def _pump(self):
        if self.current is not None or not self.queue:
            return False
        req = self.queue.pop(0)
        if req.cancellable is not None and req.cancellable.is_cancelled():
            err = GLib.Error.new_literal(Polkit.Error.quark(), "Cancelled", Polkit.Error.CANCELLED)
            req.task.return_error(err)
            self.by_cookie.pop(req.cookie, None)
            GLib.idle_add(self._pump)
            return False
        try:
            self.current = Dialog(req, self._closed)
        except Exception as e:  # never leave polkit hanging on a UI bug
            print("dialog failed:", repr(e), file=sys.stderr, flush=True)
            self.current = None
            err = GLib.Error.new_literal(Polkit.Error.quark(), "Agent UI failed", Polkit.Error.FAILED)
            req.task.return_error(err)
            self.by_cookie.pop(req.cookie, None)
            GLib.idle_add(self._pump)
        return False

    def _closed(self, dlg, ok):
        self.current = None
        self.by_cookie.pop(dlg.req.cookie, None)
        GLib.idle_add(self._pump)


def run_agent():
    rt = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    lock = open(os.path.join(rt, "genshin-polkit.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("genshin-polkit is already running")
        return 0

    agent = Agent()
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        info = Gio.DBusNodeInfo.new_for_xml(AGENT_XML)
        reg_id = bus.register_object(OBJECT_PATH, info.interfaces[0], agent.on_call, None, None)  # noqa: F841
        try:
            subject = Polkit.UnixSession.new_for_process_sync(os.getpid(), None)
        except GLib.Error:
            subject = Polkit.UnixProcess.new(os.getpid())
        locale = os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "en_US.UTF-8"
        Polkit.Authority.get_sync(None).register_authentication_agent_sync(subject, locale, OBJECT_PATH, None)
    except GLib.Error as e:
        print("could not register as polkit agent: %s\n"
              "(is another agent such as polkit-kde / hyprpolkitagent still running?)" % e.message, file=sys.stderr)
        return 1

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)
    print("genshin-polkit: registered (layer-shell: %s)" % ("yes" if LS else "no"), flush=True)
    Gtk.main()
    return 0


def run_preview():
    if "--no-layer" in sys.argv:
        global LS
        LS = None
    req = Request(
        "org.genshin.preview.install",
        "Authentication is required to install software",
        Polkit.Details(), "preview", [Polkit.UnixUser.new(os.getuid()), Polkit.UnixUser.new(0)], None, None)
    req.details.insert("command_line", "/usr/bin/pacman -S --needed teyvat-archive")
    print("preview: the FIRST password is rejected on purpose, the second one is accepted.")

    def closed(dlg, ok):
        print("preview result:", "authenticated" if ok else "cancelled")
        Gtk.main_quit()

    Dialog(req, closed, preview=True)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(run_preview() if "--preview" in sys.argv else run_agent())
