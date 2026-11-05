#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_assets.py — generates every image/audio asset for Teyvat Forecast.

Everything is drawn from vector shapes (Pillow) at 4x supersampling and
downscaled with LANCZOS, so the project ships no binary blobs I can't
account for. Audio (soft rain/wind loops + UI click) is synthesized with
pure math. Re-run any time:  python3 tools/gen_assets.py [--out DIR]

Deterministic (seeded RNG). Pillow required.
"""

import math
import random
import struct
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------- palette --- #

GOLD = (211, 188, 142, 255)
GOLD_DIM = (138, 122, 92, 255)
CREAM = (236, 229, 216, 255)
CREAM_DIM = (185, 176, 160, 255)
NAVY = (23, 27, 38, 255)
NAVY_CARD = (23, 27, 38, 240)          # card bg incl. 94% alpha
RED = (200, 29, 45, 255)
HYDRO = (76, 194, 241, 255)
CRYO = (159, 214, 227, 255)
ELECTRO = (179, 128, 255, 255)
PYRO = (239, 121, 56, 255)
ANEMO = (116, 194, 168, 255)
GEO = (247, 182, 82, 255)
DENDRO = (123, 178, 110, 255)
WHITE = (255, 255, 255, 255)

SS = 4  # supersample factor


def canvas(px: int) -> Image.Image:
    return Image.new("RGBA", (px * SS, px * SS), (0, 0, 0, 0))


def finish(img: Image.Image, px: int) -> Image.Image:
    return img.resize((px, px), Image.LANCZOS)


def soft(img: Image.Image, radius: float) -> Image.Image:
    """Composite a blurred glow copy under the sharp shape."""
    glow = img.filter(ImageFilter.GaussianBlur(radius))
    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    base.alpha_composite(glow)
    base.alpha_composite(glow)
    base.alpha_composite(img)
    return base


def tint(img: Image.Image, color, blur: float = 8) -> Image.Image:
    """Return a glow layer of img's alpha shape in `color`."""
    alpha = img.split()[3]
    layer = Image.new("RGBA", img.size, color)
    layer.putalpha(alpha)
    return layer.filter(ImageFilter.GaussianBlur(blur))


def save(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    print(f"  {path.name:26s} {path.stat().st_size:7d} B")


# ------------------------------------------------------------ shape helpers -- #


def disc(dr, cx, cy, r, color):
    dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def ring(dr, cx, cy, r, width, color):
    dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)


def rrect(dr, box, radius, color):
    dr.rounded_rectangle(box, radius=radius, fill=color)


def poly(dr, points, color):
    dr.polygon(points, fill=color)


def cloud_shape(size, cx, cy, w, color):
    """Draw a soft cloud; returns the image."""
    img = canvas(size)
    dr = ImageDraw.Draw(img)
    h = w * 0.46
    r1, r2, r3 = w * 0.26, w * 0.34, w * 0.22
    disc(dr, cx - w * 0.24, cy, r1, color)
    disc(dr, cx + w * 0.02, cy - h * 0.28, r2, color)
    disc(dr, cx + w * 0.27, cy - h * 0.05, r3, color)
    rrect(dr, [cx - w * 0.42, cy - r1 * 0.42, cx + w * 0.42, cy + r1 * 0.58],
          r1 * 0.5, color)
    return img


def sun_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    c = px * SS / 2
    disc(dr, c, c, px * SS * 0.21, GOLD)
    disc(dr, c - px * SS * 0.05, c - px * SS * 0.05, px * SS * 0.13,
         (min(255, GOLD[0] + 20), min(255, GOLD[1] + 20), min(255, GOLD[2] + 18), 255))
    for i in range(8):
        a = math.radians(i * 45)
        r0, r1 = px * SS * 0.27, px * SS * 0.44
        w = px * SS * (0.035 if i % 2 == 0 else 0.026)
        x0, y0 = c + r0 * math.cos(a), c + r0 * math.sin(a)
        x1, y1 = c + r1 * math.cos(a), c + r1 * math.sin(a)
        dr.line([x0, y0, x1, y1], fill=GOLD, width=int(w), joint="curve")
        disc(dr, x1, y1, w * 0.65, GOLD)
    return finish(soft(img, px * SS * 0.03), px)


def moon_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    c = px * SS / 2
    r = px * SS * 0.30
    disc(dr, c, c, r, CREAM)
    # crescent cut
    cut = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d2 = ImageDraw.Draw(cut)
    disc(d2, c + r * 0.62, c - r * 0.28, r * 0.92, (255, 255, 255, 255))
    img.paste((0, 0, 0, 0), (0, 0), cut.split()[3])
    # craters
    d3 = ImageDraw.Draw(img)
    disc(d3, c - r * 0.35, c + r * 0.30, r * 0.11, CREAM_DIM)
    disc(d3, c - r * 0.05, c + r * 0.55, r * 0.07, CREAM_DIM)
    disc(d3, c - r * 0.45, c - r * 0.12, r * 0.05, CREAM_DIM)
    return finish(soft(img, px * SS * 0.03), px)


def cloud_sun_icon(px=96, night=False):
    img = canvas(px)
    sun = moon_icon(px * 2) if night else sun_icon(px * 2)
    sun = sun.resize((int(px * SS * 0.52), int(px * SS * 0.52)), Image.LANCZOS)
    img.alpha_composite(sun, (int(px * SS * 0.46), int(px * SS * 0.04)))
    cl = cloud_shape(px, px * SS * 0.5, px * SS * 0.68, px * SS * 0.62, CREAM)
    img.alpha_composite(cl)
    return finish(soft(img, px * SS * 0.025), px)


def overcast_icon(px=96):
    img = canvas(px)
    back = cloud_shape(px, px * SS * 0.55, px * SS * 0.42, px * SS * 0.5, CREAM_DIM)
    img.alpha_composite(back)
    front = cloud_shape(px, px * SS * 0.45, px * SS * 0.64, px * SS * 0.62, CREAM)
    img.alpha_composite(front)
    return finish(soft(img, px * SS * 0.025), px)


def fog_icon(px=96):
    img = canvas(px)
    cl = cloud_shape(px, px * SS * 0.5, px * SS * 0.36, px * SS * 0.58, CREAM)
    img.alpha_composite(cl)
    dr = ImageDraw.Draw(img)
    for i, w in enumerate([0.62, 0.50, 0.40]):
        y = px * SS * (0.62 + i * 0.13)
        rrect(dr, [px * SS * (0.5 - w / 2), y, px * SS * (0.5 + w / 2), y + px * SS * 0.055],
              px * SS * 0.028, GOLD if i == 1 else CREAM_DIM)
    return finish(soft(img, px * SS * 0.02), px)


def rain_icon(px=96, heavy=True):
    img = canvas(px)
    img.alpha_composite(cloud_shape(px, px * SS * 0.5, px * SS * 0.38,
                                    px * SS * 0.6, CREAM))
    dr = ImageDraw.Draw(img)
    color = HYDRO
    drops = [(-0.20, 0.55), (0.0, 0.62), (0.20, 0.55)] if not heavy else \
            [(-0.26, 0.5), (-0.09, 0.6), (0.09, 0.6), (0.26, 0.5)]
    for dx, dy in drops:
        x = px * SS * (0.5 + dx)
        y = px * SS * dy
        dr.line([x, y, x - px * SS * 0.05, y + px * SS * 0.22],
                fill=color, width=int(px * SS * 0.045))
        disc(dr, x - px * SS * 0.05, y + px * SS * 0.22, px * SS * 0.024, color)
    return finish(soft(img, px * SS * 0.02), px)


def snow_icon(px=96):
    img = canvas(px)
    img.alpha_composite(cloud_shape(px, px * SS * 0.5, px * SS * 0.38,
                                    px * SS * 0.6, CREAM))
    dr = ImageDraw.Draw(img)
    flakes = [(-0.20, 0.60), (0.0, 0.70), (0.20, 0.60)]
    for dx, dy in flakes:
        cx, cy = px * SS * (0.5 + dx), px * SS * dy
        r = px * SS * 0.055
        for a in range(0, 360, 60):
            rad = math.radians(a)
            dr.line([cx - r * math.cos(rad), cy - r * math.sin(rad),
                     cx + r * math.cos(rad), cy + r * math.sin(rad)],
                    fill=CRYO, width=int(px * SS * 0.02))
        disc(dr, cx, cy, px * SS * 0.018, CREAM)
    return finish(soft(img, px * SS * 0.02), px)


def storm_icon(px=96):
    img = canvas(px)
    img.alpha_composite(cloud_shape(px, px * SS * 0.5, px * SS * 0.36,
                                    px * SS * 0.62, CREAM_DIM))
    dr = ImageDraw.Draw(img)
    b = px * SS
    poly(dr, [(b * 0.54, b * 0.48), (b * 0.38, b * 0.72), (b * 0.48, b * 0.72),
              (b * 0.42, b * 0.94), (b * 0.62, b * 0.64), (b * 0.50, b * 0.64),
              (b * 0.60, b * 0.48)], ELECTRO)
    return finish(soft(img, px * SS * 0.025), px)


def wind_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    for i, (x0, x1, y) in enumerate([(0.14, 0.72, 0.34), (0.08, 0.60, 0.52),
                                     (0.22, 0.80, 0.70)]):
        w = b * (0.045 - i * 0.008)
        color = [GOLD, CREAM, GOLD_DIM][i]
        dr.arc([b * x0, b * (y - 0.10), b * x1, b * (y + 0.10)],
               start=200 if i % 2 else -20, end=90 if i % 2 else 160,
               fill=color, width=int(w))
        dr.line([b * x1, b * y, b * x1 - b * 0.05, b * y], fill=color, width=int(w))
    return finish(soft(img, b * 0.02), px)


def drop_icon(px=96, color=HYDRO):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    poly(dr, [(b * 0.5, b * 0.12), (b * 0.74, b * 0.52), (b * 0.5, b * 0.86),
              (b * 0.26, b * 0.52)], color)
    disc(dr, b * 0.5, b * 0.55, b * 0.235, color)
    disc(dr, b * 0.44, b * 0.48, b * 0.09,
         (min(255, color[0] + 40), min(255, color[1] + 40), min(255, color[2] + 40), 255))
    return finish(soft(img, b * 0.03), px)


def gauge_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    ring(dr, b * 0.5, b * 0.56, b * 0.34, int(b * 0.05), CREAM_DIM)
    dr.arc([b * 0.16, b * 0.22, b * 0.84, b * 0.90], start=-150, end=-30,
           fill=GOLD, width=int(b * 0.055))
    disc(dr, b * 0.5, b * 0.56, b * 0.08, GOLD)
    dr.line([b * 0.5, b * 0.56, b * 0.66, b * 0.38], fill=CREAM, width=int(b * 0.045))
    return finish(soft(img, b * 0.02), px)


def eye_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    dr.polygon([(b * 0.08, b * 0.5), (b * 0.5, b * 0.22), (b * 0.92, b * 0.5),
                (b * 0.5, b * 0.78)], outline=CREAM, width=int(b * 0.04))
    disc(dr, b * 0.5, b * 0.5, b * 0.17, CREAM)
    disc(dr, b * 0.5, b * 0.5, b * 0.09, NAVY)
    return finish(soft(img, b * 0.02), px)


def sun_half_icon(px=96, rising=True):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    cy = b * 0.62
    dr.line([b * 0.08, cy, b * 0.92, cy], fill=CREAM_DIM, width=int(b * 0.035))
    disc(dr, b * 0.5, cy, b * 0.20, GOLD)
    dr.rectangle([b * 0.26, cy, b * 0.74, b * 0.9], fill=(0, 0, 0, 0))
    # re-cut: erase below horizon (draw over with transparent via mask)
    cut = Image.new("L", img.size, 0)
    d2 = ImageDraw.Draw(cut)
    d2.rectangle([0, cy, img.width, img.height], fill=255)
    img.putalpha(Image.composite(Image.new("L", img.size, 0),
                                 img.split()[3], cut))
    for i in range(5):
        a = -160 + i * 40 if rising else 160 - i * 40
        rad = math.radians(-a)
        r0, r1 = b * 0.26, b * 0.36
        dr.line([b * 0.5 + r0 * math.cos(rad), cy + r0 * math.sin(rad),
                 b * 0.5 + r1 * math.cos(rad), cy + r1 * math.sin(rad)],
                fill=GOLD, width=int(b * 0.03))
    # arrow
    ay = b * (0.30 if rising else 0.84)
    dr.line([b * 0.5, cy + (b * 0.06 if rising else -b * 0.06), b * 0.5, ay],
            fill=GOLD, width=int(b * 0.035))
    if rising:
        poly(dr, [(b * 0.5 - b * 0.055, ay + b * 0.06), (b * 0.5 + b * 0.055, ay + b * 0.06),
                  (b * 0.5, ay - b * 0.04)], GOLD)
    else:
        poly(dr, [(b * 0.5 - b * 0.055, ay - b * 0.06), (b * 0.5 + b * 0.055, ay - b * 0.06),
                  (b * 0.5, ay + b * 0.04)], GOLD)
    return finish(soft(img, b * 0.02), px)


def uv_icon(px=96):
    img = sun_icon(px * 2).resize((int(px * SS * 0.66), int(px * SS * 0.66)), Image.LANCZOS)
    base = canvas(px)
    base.alpha_composite(img, (int(px * SS * 0.17), int(px * SS * 0.06)))
    dr = ImageDraw.Draw(base)
    b = px * SS
    poly(dr, [(b * 0.5, b * 0.62), (b * 0.66, b * 0.86), (b * 0.34, b * 0.86)], RED)
    return finish(soft(base, b * 0.02), px)


def thermo_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    rrect(dr, [b * 0.42, b * 0.10, b * 0.58, b * 0.60], b * 0.08, CREAM_DIM)
    disc(dr, b * 0.5, b * 0.70, b * 0.17, RED)
    rrect(dr, [b * 0.455, b * 0.34, b * 0.545, b * 0.62], b * 0.045, RED)
    disc(dr, b * 0.5, b * 0.70, b * 0.09, CREAM)
    for i in range(3):
        dr.line([b * 0.60, b * (0.24 + i * 0.12), b * 0.68, b * (0.24 + i * 0.12)],
                fill=CREAM_DIM, width=int(b * 0.025))
    return finish(soft(img, b * 0.02), px)


def umbrella_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    dr.pieslice([b * 0.14, b * 0.18, b * 0.86, b * 0.86], start=180, end=360,
                fill=RED)
    dr.line([b * 0.5, b * 0.52, b * 0.5, b * 0.86], fill=CREAM, width=int(b * 0.04))
    poly(dr, [(b * 0.5, b * 0.18), (b * 0.5, b * 0.06), (b * 0.66, b * 0.16),
              (b * 0.5, b * 0.24)], GOLD)
    dr.arc([b * 0.42, b * 0.80, b * 0.72, b * 0.98], start=0, end=180,
           fill=CREAM, width=int(b * 0.035))
    return finish(soft(img, b * 0.02), px)


def alert_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    poly(dr, [(b * 0.5, b * 0.12), (b * 0.90, b * 0.84), (b * 0.10, b * 0.84)], GOLD)
    rrect(dr, [b * 0.465, b * 0.34, b * 0.535, b * 0.62], b * 0.03, NAVY)
    disc(dr, b * 0.5, b * 0.73, b * 0.036, NAVY)
    return finish(soft(img, b * 0.02), px)


def refresh_icon(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    dr.arc([b * 0.18, b * 0.18, b * 0.82, b * 0.82], start=-50, end=175,
           fill=CREAM_DIM, width=int(b * 0.06))
    a = math.radians(175)
    x, y = b * 0.5 + b * 0.32 * math.cos(a), b * 0.5 + b * 0.32 * math.sin(a)
    poly(dr, [(x - b * 0.10, y - b * 0.02), (x + b * 0.10, y - b * 0.02),
              (x, y + b * 0.14)], GOLD)
    disc(dr, b * 0.5, b * 0.5, b * 0.07, GOLD)
    return finish(soft(img, b * 0.02), px)


# ------------------------------------------------------------- elements ----- #


def elem_hydro(px=96):
    return drop_icon(px, HYDRO)


def elem_pyro(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    poly(dr, [(b * 0.5, b * 0.08), (b * 0.70, b * 0.38), (b * 0.78, b * 0.66),
              (b * 0.5, b * 0.92), (b * 0.22, b * 0.66), (b * 0.30, b * 0.38)], PYRO)
    poly(dr, [(b * 0.5, b * 0.34), (b * 0.62, b * 0.58), (b * 0.56, b * 0.78),
              (b * 0.44, b * 0.78), (b * 0.38, b * 0.58)], (255, 214, 150, 255))
    return finish(soft(img, b * 0.03), px)


def elem_cryo(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    c = b * 0.5
    for a in range(0, 360, 60):
        rad = math.radians(a)
        for sign in (1, -1):
            r1, r2 = b * 0.18, b * 0.42
            dr.line([c + r1 * math.cos(rad), c + r1 * math.sin(rad),
                     c + r2 * math.cos(rad), c + r2 * math.sin(rad)],
                    fill=CRYO, width=int(b * 0.032))
        # tip diamond
        r2 = b * 0.42
        x, y = c + r2 * math.cos(rad), c + r2 * math.sin(rad)
        poly(dr, [(x - b * 0.05, y), (x, y - b * 0.05), (x + b * 0.05, y),
                  (x, y + b * 0.05)], CREAM)
    disc(dr, c, c, b * 0.09, CREAM)
    return finish(soft(img, b * 0.03), px)


def elem_electro(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    poly(dr, [(b * 0.58, b * 0.06), (b * 0.28, b * 0.52), (b * 0.46, b * 0.52),
              (b * 0.34, b * 0.94), (b * 0.74, b * 0.42), (b * 0.54, b * 0.42),
              (b * 0.70, b * 0.06)], ELECTRO)
    poly(dr, [(b * 0.56, b * 0.20), (b * 0.44, b * 0.44), (b * 0.54, b * 0.44),
              (b * 0.52, b * 0.58), (b * 0.64, b * 0.24), (b * 0.56, b * 0.24)],
         (222, 190, 255, 255))
    return finish(soft(img, b * 0.03), px)


def elem_anemo(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    c = b * 0.5
    for i, r in enumerate([0.34, 0.24, 0.14]):
        dr.arc([c - b * r, c - b * r, c + b * r, c + b * r],
               start=-90, end=140, fill=ANEMO if i % 2 == 0 else CREAM,
               width=int(b * 0.045))
    # arrow tip on outer arc
    a = math.radians(140)
    x, y = c + b * 0.34 * math.cos(a), c + b * 0.34 * math.sin(a)
    poly(dr, [(x - b * 0.02, y - b * 0.10), (x + b * 0.10, y + b * 0.02),
              (x - b * 0.04, y + b * 0.02)], CREAM)
    disc(dr, c, c, b * 0.07, ANEMO)
    return finish(soft(img, b * 0.03), px)


def elem_geo(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    c = b * 0.5
    poly(dr, [(c, b * 0.08), (b * 0.86, c), (c, b * 0.92), (b * 0.14, c)], GEO)
    poly(dr, [(c, b * 0.26), (b * 0.70, c), (c, b * 0.74), (b * 0.30, c)],
         (255, 220, 150, 255))
    dr.line([c, b * 0.26, c, b * 0.74], fill=GEO, width=int(b * 0.03))
    dr.line([b * 0.30, c, b * 0.70, c], fill=GEO, width=int(b * 0.03))
    return finish(soft(img, b * 0.03), px)


def elem_dendro(px=96):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    dr.pieslice([b * 0.14, b * 0.16, b * 0.86, b * 0.88], start=140, end=320, fill=DENDRO)
    dr.line([b * 0.20, b * 0.82, b * 0.56, b * 0.30], fill=(200, 235, 180, 255),
            width=int(b * 0.035))
    for i, (t, ln) in enumerate([(0.45, 0.16), (0.60, 0.14), (0.75, 0.11)]):
        x = b * 0.20 + (b * 0.56 - b * 0.20) * t
        y = b * 0.82 + (b * 0.30 - b * 0.82) * t
        dr.line([x, y, x + b * ln, y - b * ln * 0.4],
                fill=(200, 235, 180, 255), width=int(b * 0.025))
    return finish(soft(img, b * 0.03), px)


# -------------------------------------------------------------- sprites ----- #


def sprite_glow(px=64):
    img = Image.new("RGBA", (px * SS, px * SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    c = px * SS / 2
    steps = 24
    for i in range(steps, 0, -1):
        r = c * (i / steps)
        a = int(255 * (1 - i / steps) ** 2.2)
        disc(dr, c, c, r, (255, 250, 235, a))
    return img.resize((px, px), Image.LANCZOS)


def sprite_rain(px=40):
    """Rain streak. SQUARE canvas on purpose: Qt's ImageParticle draws every
    particle as a size x size quad, so a tall 8x40 sprite got squashed into a
    fat square blob. The streak is drawn thin and centred inside a square."""
    img = Image.new("RGBA", (px * SS, px * SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    cx = px * SS / 2
    for ww, alpha in [(0.085, 60), (0.05, 150), (0.026, 255)]:
        half = px * SS * ww / 2
        rrect(dr, [cx - half, px * SS * 0.06, cx + half, px * SS * 0.94],
              half, (220, 235, 250, alpha))
    return img.resize((px, px), Image.LANCZOS)


def sprite_snow(px=28):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    c = px * SS / 2
    r = px * SS * 0.42
    for a in range(0, 360, 60):
        rad = math.radians(a)
        dr.line([c, c, c + r * math.cos(rad), c + r * math.sin(rad)],
                fill=(240, 248, 255, 235), width=int(px * SS * 0.045))
    disc(dr, c, c, px * SS * 0.10, (255, 255, 255, 255))
    return img.filter(ImageFilter.GaussianBlur(px * SS * 0.02)).resize((px, px), Image.LANCZOS)


def sprite_star(px=22):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    c = px * SS / 2
    # halo FIRST, bright core LAST (ImageDraw overwrites pixels, it does not
    # blend - the old order painted the dim halo over the core, so stars
    # topped out at ~30 % alpha and were almost invisible)
    disc(dr, c, c, px * SS * 0.40, (200, 215, 255, 40))
    disc(dr, c, c, px * SS * 0.30, (220, 230, 255, 110))
    disc(dr, c, c, px * SS * 0.16, (255, 255, 255, 255))
    return img.filter(ImageFilter.GaussianBlur(px * SS * 0.02)).resize((px, px), Image.LANCZOS)


def sprite_spark(px=48):
    """Four-point sparkle: two long arms (0/90 deg) + two short diagonals.
    (The old version never used the arm angle, so all four polygons were the
    same vertical sliver.)"""
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    c = px * SS / 2
    r = px * SS * 0.46
    w = px * SS * 0.05
    for a in (0, 90, 45, 135):
        rad = math.radians(a)
        rr = r if a in (0, 90) else r * 0.55
        dx, dy = math.cos(rad), math.sin(rad)      # arm direction
        nx, ny = -dy, dx                           # arm normal
        poly(dr, [(c - dx * rr, c - dy * rr), (c + nx * w, c + ny * w),
                  (c + dx * rr, c + dy * rr), (c - nx * w, c - ny * w)],
             (255, 244, 214, 255))
    disc(dr, c, c, px * SS * 0.07, (255, 255, 255, 255))
    return img.filter(ImageFilter.GaussianBlur(px * SS * 0.01)).resize((px, px), Image.LANCZOS)


def _cloud_puffs(w, h):
    """Puff layout kept INSIDE the canvas (radius + blur margin), so the
    sprite never gets a hard clipped edge. Wide and low: a flat-bottomed
    cumulus."""
    random.seed(5)
    puffs = []
    for i in range(22):
        x = random.uniform(0.20, 0.80) * w
        y = random.uniform(0.50, 0.68) * h
        r = random.uniform(0.07, 0.13) * w
        puffs.append((x, y, r))
    puffs += [(0.30 * w, 0.58 * h, 0.11 * w), (0.52 * w, 0.46 * h, 0.14 * w),
              (0.70 * w, 0.58 * h, 0.10 * w)]
    return puffs


def sprite_cloud(w=360, h=150):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for x, y, r in _cloud_puffs(w, h):
        dr.ellipse([x - r, y - r * 0.72, x + r, y + r * 0.72],
                   fill=(255, 255, 255, 150))
    return img.filter(ImageFilter.GaussianBlur(9))


def sprite_cloud_dark(w=360, h=150):
    """Darker, more opaque foreground cloud (same puff layout as
    sprite_cloud, so the two layers belong to the same family)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for x, y, r in _cloud_puffs(w, h):
        dr.ellipse([x - r, y - r * 0.72, x + r, y + r * 0.72],
                   fill=(60, 70, 96, 190))
    return img.filter(ImageFilter.GaussianBlur(9))


def sprite_fog(w=512, h=128):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    random.seed(9)
    for i in range(70):
        x = random.uniform(0, w)
        y = random.uniform(h * 0.25, h * 0.75)
        rx, ry = random.uniform(40, 150), random.uniform(10, 30)
        dr.ellipse([x, y, x + rx, y + ry], fill=(226, 232, 240, 90))
    return img.filter(ImageFilter.GaussianBlur(14))


def sprite_wind(px=64):
    """Wind streak. SQUARE canvas (see sprite_rain): a thin horizontal streak
    centred in the quad, so ImageParticle no longer stretches it into a blob."""
    img = Image.new("RGBA", (px * SS, px * SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    cy = px * SS / 2
    for hh, alpha in [(0.090, 50), (0.055, 120), (0.028, 220)]:
        half = px * SS * hh / 2
        rrect(dr, [px * SS * 0.04, cy - half, px * SS * 0.96, cy + half],
              half, (235, 245, 250, alpha))
    return img.resize((px, px), Image.LANCZOS)


def sprite_leaf(px=28):
    img = canvas(px)
    dr = ImageDraw.Draw(img)
    b = px * SS
    dr.pieslice([b * 0.14, b * 0.16, b * 0.86, b * 0.88], start=140, end=320,
                fill=(150, 220, 190, 220))
    dr.line([b * 0.22, b * 0.80, b * 0.62, b * 0.34], fill=(90, 160, 130, 255),
            width=int(b * 0.03))
    return img.resize((px, px), Image.LANCZOS)


def sprite_corner(px=96):
    """Corner mask: opaque card-navy OUTSIDE the rounded corner (bottom-right
    quarter disc is transparent). Rotate for the other corners in QML."""
    img = Image.new("RGBA", (px, px), NAVY_CARD)
    dr = ImageDraw.Draw(img)
    dr.pieslice([0, 0, px * 2, px * 2], start=180, end=270, fill=(0, 0, 0, 0))
    return img


# --------------------------------------------------------------- audio ------ #

SR = 22050


def write_wav(path: Path, samples) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<h", max(-32767, min(32767, int(s * 32767))))
            for s in samples))
    print(f"  {path.name:26s} {path.stat().st_size:7d} B")


def loopify(x, fade_n):
    n = len(x) - fade_n
    y = x[:n]
    for i in range(fade_n):
        t = i / fade_n
        y[i] = x[i] * t + x[n + i] * (1.0 - t)
    return y


def gen_rain(seconds=6.0):
    random.seed(11)
    n = int(SR * seconds)
    fade = int(SR * 0.6)
    prev = 0.0
    out = []
    for i in range(n + fade):
        w = random.uniform(-1, 1)
        v = w - 0.55 * prev          # high-pass tilt: bright rain hiss
        prev = w
        t = i / SR
        amp = 0.16 * (0.85 + 0.15 * math.sin(2 * math.pi * 0.11 * t))
        out.append(v * amp)
    return loopify(out, fade)


def gen_wind(seconds=6.0):
    random.seed(23)
    n = int(SR * seconds)
    fade = int(SR * 0.8)
    b = 0.0
    out = []
    for i in range(n + fade):
        w = random.uniform(-1, 1)
        b = b * 0.986 + w * 0.014    # brown-ish noise
        t = i / SR
        amp = 0.10 + 0.075 * math.sin(2 * math.pi * 0.13 * t) \
            + 0.05 * math.sin(2 * math.pi * 0.31 * t + 1.7)
        out.append(b * 9.0 * amp)
    return loopify(out, fade)


def gen_click():
    n = int(SR * 0.09)
    out = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 46)
        v = 0.5 * math.sin(2 * math.pi * 1250 * t) * env \
            + 0.18 * math.sin(2 * math.pi * 2500 * t) * env * env
        if t < 0.002:
            v += random.uniform(-0.3, 0.3) * (1 - t / 0.002)
        out.append(v * 0.5)
    return out


# ------------------------------------------------------------------ main ---- #


def main():
    out_root = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path(__file__).resolve().parent.parent / "quickshell" / "assets"

    print(f"generating assets into {out_root}")

    icons = out_root / "icons"
    print("[weather icons]")
    save(sun_icon(), icons / "sun.png")
    save(moon_icon(), icons / "moon.png")
    save(cloud_sun_icon(night=False), icons / "sun-cloud.png")
    save(cloud_sun_icon(night=True), icons / "moon-cloud.png")
    save(overcast_icon(), icons / "cloud.png")
    save(overcast_icon(), icons / "overcast.png")
    save(fog_icon(), icons / "fog.png")
    save(rain_icon(heavy=False), icons / "drizzle.png")
    save(rain_icon(heavy=True), icons / "rain.png")
    save(snow_icon(), icons / "snow.png")
    save(storm_icon(), icons / "storm.png")
    save(wind_icon(), icons / "wind.png")

    print("[utility icons]")
    save(drop_icon(96, HYDRO), icons / "humidity.png")
    save(gauge_icon(), icons / "pressure.png")
    save(eye_icon(), icons / "visibility.png")
    save(sun_half_icon(rising=True), icons / "sunrise.png")
    save(sun_half_icon(rising=False), icons / "sunset.png")
    save(uv_icon(), icons / "uv.png")
    save(thermo_icon(), icons / "thermo.png")
    save(umbrella_icon(), icons / "precip.png")
    save(alert_icon(), icons / "alert.png")
    save(refresh_icon(), icons / "refresh.png")

    print("[element emblems]")
    elems = out_root / "elements"
    save(elem_hydro(), elems / "hydro.png")
    save(elem_pyro(), elems / "pyro.png")
    save(elem_cryo(), elems / "cryo.png")
    save(elem_electro(), elems / "electro.png")
    save(elem_anemo(), elems / "anemo.png")
    save(elem_geo(), elems / "geo.png")
    save(elem_dendro(), elems / "dendro.png")

    print("[scene sprites]")
    sp = out_root / "sprites"
    save(sprite_glow(), sp / "glow.png")
    save(sprite_rain(), sp / "rain.png")
    save(sprite_snow(), sp / "snow.png")
    save(sprite_star(), sp / "star.png")
    save(sprite_spark(), sp / "spark.png")
    save(sprite_cloud(), sp / "cloud.png")
    save(sprite_cloud_dark(), sp / "cloud_dark.png")
    save(sprite_fog(), sp / "fog.png")
    save(sprite_wind(), sp / "wind.png")
    save(sprite_leaf(), sp / "leaf.png")
    save(sprite_corner(), sp / "corner.png")

    print("[audio]")
    audio = out_root / "audio"
    write_wav(audio / "rain.wav", gen_rain())
    write_wav(audio / "wind.wav", gen_wind())
    write_wav(audio / "click.wav", gen_click())

    print("done.")


if __name__ == "__main__":
    main()
