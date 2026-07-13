#!/usr/bin/env python3
"""
Generate polished NES/SNES-style cartoon sticker icons for GreenDial.

Original 32×32 game-asset style art (nearest-neighbor ×2 → 64×64 display).
Same sticker IDs as stickers/pixel/catalog.json so the client can switch
display packs without rewriting stored board entries (px:<id>).

Not Nintendo assets — original art with a classic 16-bit icon look:
dark outline, mid fill, highlight, shadow.

Run:
  python3 scripts/generate_cartoon_stickers.py
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PIXEL_CATALOG = ROOT / "stickers" / "pixel" / "catalog.json"
OUT_DIR = ROOT / "stickers" / "cartoon"
CATALOG = OUT_DIR / "catalog.json"

ART = 32
SCALE = 2
SIZE = ART * SCALE  # 64

Color = Tuple[int, int, int, int]

# Cohesive SNES-era palette
P: Dict[str, Color] = {
    "bg": (0, 0, 0, 0),
    "ink": (28, 24, 40, 255),
    "white": (255, 255, 255, 255),
    "offw": (245, 240, 250, 255),
    "cream": (255, 236, 210, 255),
    "skin": (255, 210, 175, 255),
    "skind": (230, 165, 125, 255),
    "skinh": (255, 230, 205, 255),
    "gray": (190, 195, 210, 255),
    "grayd": (110, 115, 135, 255),
    "grayh": (225, 228, 238, 255),
    "black": (20, 18, 28, 255),
    "red": (230, 60, 75, 255),
    "redd": (165, 30, 50, 255),
    "redh": (255, 120, 130, 255),
    "orange": (250, 145, 45, 255),
    "oranged": (200, 95, 25, 255),
    "orangeh": (255, 190, 90, 255),
    "yellow": (255, 220, 55, 255),
    "yellowd": (220, 170, 20, 255),
    "yellowh": (255, 245, 140, 255),
    "gold": (240, 185, 30, 255),
    "goldd": (185, 130, 15, 255),
    "goldh": (255, 230, 100, 255),
    "lime": (140, 225, 70, 255),
    "green": (55, 190, 95, 255),
    "greend": (30, 120, 60, 255),
    "greenh": (130, 235, 150, 255),
    "teal": (55, 205, 195, 255),
    "cyan": (80, 220, 240, 255),
    "sky": (130, 205, 255, 255),
    "skyd": (70, 140, 220, 255),
    "blue": (70, 130, 245, 255),
    "blued": (40, 75, 190, 255),
    "blueh": (140, 185, 255, 255),
    "navy": (35, 50, 110, 255),
    "purple": (165, 105, 245, 255),
    "purpled": (110, 55, 190, 255),
    "purpleh": (205, 165, 255, 255),
    "pink": (255, 150, 200, 255),
    "pinkd": (210, 80, 145, 255),
    "pinkh": (255, 200, 225, 255),
    "rose": (245, 100, 145, 255),
    "brown": (185, 120, 65, 255),
    "brownd": (125, 75, 40, 255),
    "brownh": (220, 165, 110, 255),
}


def new_img() -> Image.Image:
    return Image.new("RGBA", (ART, ART), P["bg"])


def put(img: Image.Image, x: int, y: int, c: Color) -> None:
    if 0 <= x < ART and 0 <= y < ART and c[3] > 0:
        img.putpixel((x, y), c)


def blend(a: Color, b: Color, t: float = 0.5) -> Color:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(4))  # type: ignore


# ── Drawing primitives ─────────────────────────────────────────────────────

def fill_rect(img, x, y, w, h, c):
    for j in range(y, y + h):
        for i in range(x, x + w):
            put(img, i, j, c)


def hline(img, x0, x1, y, c):
    for x in range(min(x0, x1), max(x0, x1) + 1):
        put(img, x, y, c)


def vline(img, x, y0, y1, c):
    for y in range(min(y0, y1), max(y0, y1) + 1):
        put(img, x, y, c)


def disk(img, cx, cy, r, c):
    rr = r * r
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= rr:
                put(img, x, y, c)


def ring(img, cx, cy, r, c, thick=1):
    for t in range(thick):
        rr_out = (r - t) ** 2
        rr_in = (r - t - 1) ** 2 if r - t - 1 > 0 else -1
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if rr_in < d <= rr_out + r // 3:
                    put(img, x, y, c)


def ellipse(img, cx, cy, rx, ry, c):
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            if rx and ry and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.05:
                put(img, x, y, c)


def shaded_disk(img, cx, cy, r, mid, hi, sh, ink=None):
    """Sphere-like shaded circle with optional outline."""
    ink = ink or P["ink"]
    disk(img, cx, cy, r, mid)
    # shadow (bottom-right)
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= r * r:
                # light from top-left
                lx, ly = x - (cx - r * 0.35), y - (cy - r * 0.35)
                if lx * 0.5 + ly * 0.5 > r * 0.35 and d2 > (r * 0.35) ** 2:
                    put(img, x, y, sh)
    # highlight
    disk(img, cx - max(1, r // 3), cy - max(1, r // 3), max(1, r // 4), hi)
    ring(img, cx, cy, r, ink, thick=1)


def outlined_rect(img, x, y, w, h, fill, ink=None, hi=None, sh=None):
    ink = ink or P["ink"]
    fill_rect(img, x, y, w, h, fill)
    if hi:
        hline(img, x + 1, x + w - 2, y + 1, hi)
        vline(img, x + 1, y + 1, y + h - 2, hi)
    if sh:
        hline(img, x + 1, x + w - 2, y + h - 2, sh)
        vline(img, x + w - 2, y + 1, y + h - 2, sh)
    # outline
    hline(img, x, x + w - 1, y, ink)
    hline(img, x, x + w - 1, y + h - 1, ink)
    vline(img, x, y, y + h - 1, ink)
    vline(img, x + w - 1, y, y + h - 1, ink)


def star(img, cx, cy, c, size=2):
    put(img, cx, cy, c)
    for d in range(1, size + 1):
        put(img, cx - d, cy, c)
        put(img, cx + d, cy, c)
        put(img, cx, cy - d, c)
        put(img, cx, cy + d, c)
    if size >= 2:
        put(img, cx - 1, cy - 1, c)
        put(img, cx + 1, cy - 1, c)
        put(img, cx - 1, cy + 1, c)
        put(img, cx + 1, cy + 1, c)


def heart(img, cx, cy, mid, hi=None, sh=None, ink=None):
    ink = ink or P["ink"]
    hi = hi or mid
    sh = sh or mid
    # classic pixel heart
    pts = [
        (0, -2), (-1, -3), (-2, -3), (-3, -2), (-3, -1), (-2, 0), (-1, 1), (0, 2),
        (1, 1), (2, 0), (3, -1), (3, -2), (2, -3), (1, -3),
        (-2, -1), (-1, 0), (0, 0), (0, 1), (1, 0), (2, -1),
        (-1, -1), (0, -1), (1, -1), (1, -2), (-1, -2),
    ]
    for dx, dy in pts:
        put(img, cx + dx, cy + dy, mid)
    put(img, cx - 1, cy - 2, hi)
    put(img, cx + 1, cy - 1, sh)
    # outline-ish dark edge
    for dx, dy in [(-3, -2), (-3, -1), (-2, 0), (-1, 1), (0, 2), (1, 1), (2, 0), (3, -1), (3, -2),
                   (-2, -3), (-1, -3), (1, -3), (2, -3)]:
        if img.getpixel((cx + dx, cy + dy))[3] == 0:
            put(img, cx + dx, cy + dy, ink)


# ── Characters ─────────────────────────────────────────────────────────────

def face(img, mood="happy", cx=16, cy=15, r=9, skin=None):
    """Polished chibi face — game mascot quality."""
    skin = skin or P["skin"]
    skind = blend(skin, P["brownd"], 0.35)
    skinh = blend(skin, P["white"], 0.35)
    shaded_disk(img, cx, cy, r, skin, skinh, skind)

    # eyes
    ey = cy - 1
    if mood == "tired":
        hline(img, cx - 5, cx - 2, ey, P["ink"])
        hline(img, cx + 2, cx + 5, ey, P["ink"])
    elif mood == "wow":
        disk(img, cx - 3, ey, 2, P["white"])
        disk(img, cx + 3, ey, 2, P["white"])
        disk(img, cx - 3, ey, 1, P["ink"])
        disk(img, cx + 3, ey, 1, P["ink"])
        put(img, cx - 3, ey - 1, P["white"])
        put(img, cx + 3, ey - 1, P["white"])
    elif mood == "angry":
        disk(img, cx - 3, ey, 1, P["ink"])
        disk(img, cx + 3, ey, 1, P["ink"])
        hline(img, cx - 5, cx - 2, ey - 2, P["ink"])
        hline(img, cx + 2, cx + 5, ey - 2, P["ink"])
        put(img, cx - 4, ey - 3, P["ink"])
        put(img, cx + 4, ey - 3, P["ink"])
    elif mood == "sick":
        # recolor face greenish already if needed
        disk(img, cx - 3, ey, 1, P["ink"])
        disk(img, cx + 3, ey, 1, P["ink"])
    else:
        disk(img, cx - 3, ey, 1, P["ink"])
        disk(img, cx + 3, ey, 1, P["ink"])
        put(img, cx - 3, ey - 1, P["white"])
        put(img, cx + 3, ey - 1, P["white"])

    # mouth
    my = cy + 3
    if mood == "happy":
        hline(img, cx - 3, cx + 3, my + 1, P["ink"])
        put(img, cx - 3, my, P["ink"])
        put(img, cx + 3, my, P["ink"])
        put(img, cx - 2, my + 1, P["redd"])
        put(img, cx + 2, my + 1, P["redd"])
    elif mood == "sad":
        hline(img, cx - 3, cx + 3, my + 1, P["ink"])
        put(img, cx - 3, my + 2, P["ink"])
        put(img, cx + 3, my + 2, P["ink"])
        put(img, cx + 5, ey + 2, P["sky"])
        put(img, cx + 5, ey + 3, P["skyd"])
    elif mood == "wow":
        disk(img, cx, my + 1, 2, P["ink"])
        disk(img, cx, my + 1, 1, P["redd"])
    elif mood == "angry":
        hline(img, cx - 2, cx + 2, my + 1, P["ink"])
    elif mood == "sick":
        hline(img, cx - 2, cx + 2, my + 1, P["greend"])
        put(img, cx - 5, ey + 2, P["lime"])
    elif mood == "tired":
        hline(img, cx - 2, cx + 2, my + 1, P["grayd"])
    else:
        hline(img, cx - 2, cx + 2, my + 1, P["ink"])

    # blush
    if mood in ("happy", "wow"):
        put(img, cx - 6, cy + 1, P["pink"])
        put(img, cx + 6, cy + 1, P["pink"])
        put(img, cx - 6, cy + 2, P["pinkh"])
        put(img, cx + 6, cy + 2, P["pinkh"])


def face_sick(img, cx=16, cy=15, r=9):
    face(img, "sick", cx, cy, r, skin=P["lime"])


# ── Icon drawers ───────────────────────────────────────────────────────────

def d_moon(img):
    shaded_disk(img, 18, 14, 9, P["yellow"], P["yellowh"], P["yellowd"])
    # crescent cut
    disk(img, 22, 11, 7, P["bg"])
    # stars
    star(img, 6, 8, P["yellowh"], 1)
    star(img, 10, 22, P["gold"], 1)
    star(img, 5, 18, P["yellow"], 1)


def d_zzz(img):
    cols = [P["purple"], P["purpleh"], P["purpled"]]
    for i, (x, y, s) in enumerate([(20, 5, 4), (15, 11, 3), (11, 16, 2)]):
        c = cols[i % 3]
        hline(img, x, x + s, y, c)
        put(img, x + s, y + 1, c)
        hline(img, x, x + s, y + 2, c)


def d_sun(img):
    shaded_disk(img, 16, 16, 7, P["yellow"], P["yellowh"], P["orange"])
    for a in range(8):
        ang = a * math.pi / 4
        x = int(16 + 12 * math.cos(ang))
        y = int(16 + 12 * math.sin(ang))
        put(img, x, y, P["gold"])
        put(img, int(16 + 11 * math.cos(ang)), int(16 + 11 * math.sin(ang)), P["orangeh"])
        put(img, int(16 + 10 * math.cos(ang)), int(16 + 10 * math.sin(ang)), P["yellow"])


def d_cloud(img, y=10):
    ellipse(img, 11, y + 2, 6, 4, P["offw"])
    ellipse(img, 20, y + 2, 6, 4, P["offw"])
    ellipse(img, 16, y, 7, 5, P["white"])
    # outline soft
    for cx, cy, rx, ry in [(11, y + 2, 6, 4), (20, y + 2, 6, 4), (16, y, 7, 5)]:
        for yy in range(cy - ry - 1, cy + ry + 2):
            for xx in range(cx - rx - 1, cx + rx + 2):
                if 0 <= xx < ART and 0 <= yy < ART:
                    inside = ((xx - cx) / max(rx, 1)) ** 2 + ((yy - cy) / max(ry, 1)) ** 2
                    if 0.95 < inside <= 1.25 and img.getpixel((xx, yy))[3] == 0:
                        # only border near cloud
                        pass
    # bottom shadow
    hline(img, 8, 24, y + 5, P["gray"])
    star(img, 26, y - 2, P["sky"], 1)


def d_rain(img):
    d_cloud(img, 8)
    for x, y in [(9, 18), (13, 20), (17, 18), (11, 23), (15, 24), (20, 21)]:
        put(img, x, y, P["blue"])
        put(img, x, y + 1, P["sky"])
        put(img, x + 1, y + 2, P["skyd"])


def d_fire(img):
    # base
    ellipse(img, 16, 22, 7, 4, P["redd"])
    # flames
    for pts, c in [
        ([(12, 20), (10, 14), (13, 10), (14, 16), (12, 20)], P["orange"]),
        ([(16, 20), (14, 12), (16, 6), (18, 12), (16, 20)], P["yellow"]),
        ([(20, 20), (18, 14), (21, 9), (22, 15), (20, 20)], P["orangeh"]),
    ]:
        # fill roughly
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            for x in range(min(xs), max(xs) + 1):
                # distance to polyline centroid
                if abs(x - 16) + abs(y - 14) < 10 + (20 - y) // 2:
                    if 8 <= x <= 24 and 5 <= y <= 24:
                        put(img, x, y, c)
    # core
    ellipse(img, 16, 16, 3, 5, P["yellowh"])
    put(img, 16, 8, P["yellowh"])
    ring(img, 16, 18, 8, P["ink"], 1)


def d_drop(img):
    # teardrop
    for y in range(6, 14):
        w = max(1, (y - 5) // 2)
        for x in range(16 - w, 16 + w + 1):
            put(img, x, y, P["sky"])
    shaded_disk(img, 16, 20, 7, P["blue"], P["cyan"], P["blued"])
    put(img, 13, 18, P["cyan"])
    put(img, 12, 17, P["white"])


def d_apple(img):
    shaded_disk(img, 16, 18, 8, P["red"], P["redh"], P["redd"])
    # leaf
    ellipse(img, 20, 9, 4, 2, P["green"])
    ellipse(img, 20, 9, 4, 2, P["greend"])
    put(img, 18, 9, P["greenh"])
    # stem
    vline(img, 16, 7, 11, P["brownd"])
    put(img, 16, 6, P["brown"])
    # shine
    put(img, 12, 15, P["white"])
    put(img, 13, 14, P["white"])


def d_pizza(img):
    # crust triangle
    for y in range(6, 28):
        w = (y - 5) // 2
        for x in range(16 - w, 16 + w + 1):
            put(img, x, y, P["yellow"])
        put(img, 16 - w, y, P["oranged"])
        put(img, 16 + w, y, P["oranged"])
    # cheese highlight
    for y in range(10, 22):
        w = max(0, (y - 9) // 2 - 1)
        for x in range(16 - w, 16 + w + 1):
            if (x + y) % 5 != 0:
                put(img, x, y, P["yellowh"])
    # pepperoni
    for cx, cy in [(14, 14), (18, 17), (15, 21), (17, 12)]:
        disk(img, cx, cy, 2, P["redd"])
        put(img, cx - 1, cy - 1, P["redh"])
    # outline edges
    for y in range(6, 28):
        w = (y - 5) // 2
        put(img, 16 - w, y, P["ink"])
        put(img, 16 + w, y, P["ink"])


def d_salad(img):
    shaded_disk(img, 16, 18, 9, P["green"], P["greenh"], P["greend"])
    disk(img, 12, 15, 3, P["lime"])
    disk(img, 20, 16, 3, P["redd"])
    disk(img, 16, 21, 2, P["orange"])
    put(img, 14, 14, P["yellow"])
    put(img, 19, 20, P["yellowh"])
    star(img, 24, 8, P["lime"], 1)


def d_dumbbell(img):
    outlined_rect(img, 3, 12, 6, 9, P["grayd"], hi=P["grayh"], sh=P["black"])
    outlined_rect(img, 23, 12, 6, 9, P["grayd"], hi=P["grayh"], sh=P["black"])
    outlined_rect(img, 9, 15, 14, 3, P["gray"], hi=P["grayh"], sh=P["grayd"])
    # shine on bar
    hline(img, 10, 21, 16, P["white"])


def d_trophy(img):
    # cup
    outlined_rect(img, 10, 6, 12, 10, P["gold"], hi=P["goldh"], sh=P["goldd"])
    # handles
    put(img, 8, 9, P["gold"])
    put(img, 7, 10, P["gold"])
    put(img, 8, 11, P["gold"])
    put(img, 23, 9, P["gold"])
    put(img, 24, 10, P["gold"])
    put(img, 23, 11, P["gold"])
    # stem + base
    outlined_rect(img, 13, 16, 6, 5, P["gold"], hi=P["goldh"], sh=P["goldd"])
    outlined_rect(img, 9, 22, 14, 5, P["gold"], hi=P["goldh"], sh=P["goldd"])
    star(img, 16, 11, P["yellowh"], 2)


def d_shield(img):
    # shield body
    for y in range(5, 20):
        w = 10 if y < 16 else max(2, 10 - (y - 16) * 2)
        for x in range(16 - w, 16 + w):
            put(img, x, y, P["blue"] if y < 14 else P["blued"])
        put(img, 16 - w, y, P["ink"])
        put(img, 16 + w - 1, y, P["ink"])
    for y in range(20, 27):
        w = max(1, 10 - (y - 16) * 2)
        for x in range(16 - w, 16 + w):
            put(img, x, y, P["navy"])
        put(img, 16 - w, y, P["ink"])
        put(img, 16 + w - 1, y, P["ink"])
    hline(img, 6, 25, 5, P["ink"])
    # boss
    shaded_disk(img, 16, 13, 3, P["yellow"], P["yellowh"], P["goldd"])
    # highlight
    hline(img, 8, 12, 8, P["blueh"])


def d_lightning(img):
    # bold bolt
    bolt = [
        (18, 3), (12, 3), (10, 4), (8, 14), (13, 14), (11, 15),
        (6, 28), (14, 15), (16, 14), (14, 13), (20, 13), (22, 4), (18, 3),
    ]
    # fill bounding region with yellow if inside polygon-ish
    for y in range(3, 29):
        for x in range(5, 24):
            # rough bolt shape
            if (
                (12 <= x <= 20 and 3 <= y <= 8)
                or (8 <= x <= 16 and 8 <= y <= 15)
                or (6 <= x <= 14 and 15 <= y <= 28 and x + y > 24 and x - y / 3 < 8)
            ):
                put(img, x, y, P["yellow"] if y < 16 else P["gold"])
    # highlight edge
    for y in range(4, 12):
        put(img, 14, y, P["yellowh"])
    # outline
    for x, y in [(12, 3), (18, 3), (22, 4), (20, 13), (16, 14), (14, 15), (6, 28),
                 (8, 14), (10, 4), (13, 14), (11, 15)]:
        put(img, x, y, P["ink"])


def d_heart(img):
    heart(img, 16, 16, P["red"], P["redh"], P["redd"])
    heart(img, 16, 16, P["red"], P["redh"], P["redd"])  # denser
    # bigger heart by disks
    disk(img, 12, 13, 5, P["red"])
    disk(img, 20, 13, 5, P["red"])
    for y in range(13, 26):
        w = max(0, 10 - (y - 13))
        for x in range(16 - w, 16 + w):
            put(img, x, y, P["red"] if y < 20 else P["redd"])
    put(img, 10, 11, P["redh"])
    put(img, 11, 10, P["white"])
    ring(img, 12, 13, 5, P["ink"], 1)
    ring(img, 20, 13, 5, P["ink"], 1)


def d_house(img):
    outlined_rect(img, 7, 14, 18, 13, P["brown"], hi=P["brownh"], sh=P["brownd"])
    # roof
    for i in range(10):
        hline(img, 16 - i - 1, 16 + i, 13 - i, P["redd"])
        put(img, 16 - i - 1, 13 - i, P["ink"])
        put(img, 16 + i, 13 - i, P["ink"])
    for i in range(9):
        hline(img, 16 - i, 16 + i - 1, 12 - i, P["red"])
    # door + windows
    outlined_rect(img, 13, 20, 6, 7, P["brownd"], hi=P["brown"], sh=P["black"])
    outlined_rect(img, 9, 17, 3, 3, P["yellowh"], hi=P["yellow"], sh=P["goldd"])
    outlined_rect(img, 20, 17, 3, 3, P["yellowh"], hi=P["yellow"], sh=P["goldd"])


def d_tree(img):
    outlined_rect(img, 14, 18, 4, 10, P["brown"], hi=P["brownh"], sh=P["brownd"])
    shaded_disk(img, 16, 14, 9, P["green"], P["greenh"], P["greend"])
    shaded_disk(img, 12, 16, 5, P["lime"], P["greenh"], P["green"])
    shaded_disk(img, 20, 15, 5, P["green"], P["lime"], P["greend"])
    star(img, 8, 8, P["yellow"], 1)


def d_bike(img):
    ring(img, 9, 22, 5, P["ink"], 2)
    ring(img, 23, 22, 5, P["ink"], 2)
    disk(img, 9, 22, 1, P["grayd"])
    disk(img, 23, 22, 1, P["grayd"])
    # frame
    hline(img, 9, 23, 16, P["red"])
    hline(img, 9, 23, 17, P["redd"])
    vline(img, 16, 12, 17, P["gray"])
    put(img, 16, 11, P["red"])
    put(img, 15, 10, P["redh"])
    # seat + bars
    hline(img, 13, 17, 12, P["black"])
    put(img, 22, 14, P["ink"])
    put(img, 23, 13, P["ink"])


def d_owl(img):
    shaded_disk(img, 16, 17, 10, P["brown"], P["brownh"], P["brownd"])
    # ear tufts
    for dx in (-8, 8):
        put(img, 16 + dx, 8, P["brownd"])
        put(img, 16 + dx, 7, P["brown"])
        put(img, 16 + dx // 2, 6, P["brownd"])
    # eyes
    shaded_disk(img, 12, 15, 4, P["cream"], P["white"], P["gray"])
    shaded_disk(img, 20, 15, 4, P["cream"], P["white"], P["gray"])
    disk(img, 12, 15, 2, P["ink"])
    disk(img, 20, 15, 2, P["ink"])
    put(img, 12, 14, P["white"])
    put(img, 20, 14, P["white"])
    # beak
    put(img, 16, 18, P["orange"])
    put(img, 15, 19, P["orange"])
    put(img, 17, 19, P["orange"])
    put(img, 16, 20, P["oranged"])


def d_sheep(img):
    # fluffy body
    for cx, cy, r in [(16, 18, 9), (10, 16, 5), (22, 16, 5), (12, 12, 4), (20, 12, 4), (16, 11, 4)]:
        disk(img, cx, cy, r, P["offw"])
    ring(img, 16, 18, 9, P["ink"], 1)
    # face
    shaded_disk(img, 16, 15, 4, P["cream"], P["white"], P["skind"])
    disk(img, 14, 15, 1, P["ink"])
    disk(img, 18, 15, 1, P["ink"])
    put(img, 16, 17, P["pink"])


def d_ufo(img):
    # dome
    shaded_disk(img, 16, 12, 6, P["cyan"], P["white"], P["skyd"])
    # saucer
    ellipse(img, 16, 16, 12, 4, P["gray"])
    ellipse(img, 16, 15, 12, 3, P["grayh"])
    hline(img, 4, 27, 16, P["ink"])
    hline(img, 4, 27, 18, P["ink"])
    for x in (7, 12, 16, 20, 25):
        put(img, x, 17, P["yellow"])
    # beam
    for y in range(20, 30):
        w = (y - 18) // 2
        for x in range(16 - w, 16 + w + 1):
            put(img, x, y, P["lime"] if y % 2 == 0 else P["yellowh"])


def d_bed(img):
    outlined_rect(img, 4, 18, 24, 8, P["blued"], hi=P["blue"], sh=P["navy"])
    outlined_rect(img, 5, 14, 14, 6, P["cream"], hi=P["white"], sh=P["gray"])
    outlined_rect(img, 19, 12, 8, 8, P["pink"], hi=P["pinkh"], sh=P["pinkd"])
    face(img, "tired", cx=23, cy=10, r=4)
    d_zzz(img)


def d_alarm(img):
    shaded_disk(img, 16, 17, 9, P["red"], P["redh"], P["redd"])
    shaded_disk(img, 16, 17, 6, P["white"], P["offw"], P["gray"])
    # hands
    vline(img, 16, 12, 17, P["ink"])
    hline(img, 16, 20, 17, P["redd"])
    put(img, 16, 17, P["ink"])
    # bells
    shaded_disk(img, 9, 9, 3, P["gold"], P["goldh"], P["goldd"])
    shaded_disk(img, 23, 9, 3, P["gold"], P["goldh"], P["goldd"])
    # feet
    put(img, 12, 27, P["ink"])
    put(img, 20, 27, P["ink"])


def d_mug(img):
    outlined_rect(img, 8, 10, 14, 15, P["cream"], hi=P["white"], sh=P["skind"])
    fill_rect(img, 9, 11, 12, 4, P["brown"])
    hline(img, 9, 20, 12, P["brownh"])
    # handle
    for y in range(13, 22):
        put(img, 23, y, P["ink"])
        put(img, 24, y, P["cream"])
        put(img, 25, y, P["ink"])
    put(img, 23, 13, P["ink"])
    put(img, 23, 21, P["ink"])
    # steam
    for x, y in [(11, 6), (15, 5), (19, 6)]:
        put(img, x, y, P["gray"])
        put(img, x + 1, y - 1, P["grayh"])


def d_book(img):
    outlined_rect(img, 6, 6, 20, 20, P["blued"], hi=P["blue"], sh=P["navy"])
    outlined_rect(img, 8, 8, 16, 16, P["cream"], hi=P["white"], sh=P["gray"])
    for y in (12, 16, 20):
        hline(img, 10, 21, y, P["gray"])
    star(img, 24, 10, P["purple"], 1)


def d_pill(img):
    # capsule
    for y in range(12, 20):
        for x in range(6, 16):
            put(img, x, y, P["rose"])
        for x in range(16, 26):
            put(img, x, y, P["white"])
    # round ends
    disk(img, 8, 15, 4, P["rose"])
    disk(img, 24, 15, 4, P["white"])
    hline(img, 6, 25, 11, P["ink"])
    hline(img, 6, 25, 20, P["ink"])
    vline(img, 16, 12, 19, P["ink"])
    put(img, 10, 13, P["pinkh"])
    put(img, 20, 13, P["grayh"])


def d_phone(img):
    outlined_rect(img, 10, 4, 12, 24, P["grayd"], hi=P["gray"], sh=P["black"])
    outlined_rect(img, 12, 7, 8, 15, P["sky"], hi=P["cyan"], sh=P["skyd"])
    disk(img, 16, 25, 1, P["gray"])
    heart(img, 16, 14, P["red"], P["redh"], P["redd"])


def d_germ(img):
    shaded_disk(img, 16, 16, 8, P["lime"], P["greenh"], P["greend"])
    # spikes
    for a in range(12):
        ang = a * math.pi / 6
        x = int(16 + 11 * math.cos(ang))
        y = int(16 + 11 * math.sin(ang))
        put(img, x, y, P["green"])
        put(img, int(16 + 10 * math.cos(ang)), int(16 + 10 * math.sin(ang)), P["lime"])
    disk(img, 13, 14, 1, P["ink"])
    disk(img, 19, 14, 1, P["ink"])
    hline(img, 13, 19, 19, P["greend"])
    put(img, 13, 18, P["greend"])
    put(img, 19, 18, P["greend"])


def d_butterfly(img):
    ellipse(img, 10, 12, 6, 5, P["pink"])
    ellipse(img, 22, 12, 6, 5, P["purple"])
    ellipse(img, 10, 20, 5, 4, P["pinkd"])
    ellipse(img, 22, 20, 5, 4, P["purpled"])
    put(img, 8, 11, P["pinkh"])
    put(img, 24, 11, P["purpleh"])
    outlined_rect(img, 15, 10, 2, 14, P["ink"])
    put(img, 15, 8, P["ink"])
    put(img, 16, 7, P["ink"])
    put(img, 17, 8, P["ink"])
    star(img, 6, 6, P["yellow"], 1)


def d_rainbow(img):
    colors = [P["redd"], P["orange"], P["yellow"], P["green"], P["blue"], P["purple"]]
    for i, c in enumerate(colors):
        for x in range(3, 29):
            t = (x - 16) / 13
            y = int(22 - (1 - t * t) * (14 - i))
            if 4 <= y < 28:
                put(img, x, y, c)
                put(img, x, y + 1, c)


def d_chef(img):
    face(img, "happy", cx=16, cy=18, r=8)
    # hat
    outlined_rect(img, 9, 6, 14, 6, P["white"], hi=P["offw"], sh=P["gray"])
    disk(img, 11, 6, 4, P["white"])
    disk(img, 21, 6, 4, P["white"])
    disk(img, 16, 4, 4, P["white"])
    ring(img, 11, 6, 4, P["ink"], 1)
    ring(img, 21, 6, 4, P["ink"], 1)
    ring(img, 16, 4, 4, P["ink"], 1)


def d_runner(img):
    face(img, "wow", cx=12, cy=8, r=5)
    outlined_rect(img, 10, 13, 5, 7, P["blue"], hi=P["blueh"], sh=P["blued"])
    # legs
    put(img, 10, 21, P["skin"])
    put(img, 9, 22, P["skin"])
    put(img, 8, 23, P["skind"])
    put(img, 14, 21, P["skin"])
    put(img, 16, 22, P["skin"])
    put(img, 17, 23, P["skind"])
    # motion lines
    for x in (20, 23, 26):
        put(img, x, 14, P["yellow"])
        put(img, x, 16, P["gold"])
    star(img, 28, 8, P["yellowh"], 1)


def d_couch(img):
    outlined_rect(img, 3, 16, 26, 10, P["purple"], hi=P["purpleh"], sh=P["purpled"])
    outlined_rect(img, 3, 12, 6, 8, P["purpled"], hi=P["purple"], sh=P["navy"])
    outlined_rect(img, 23, 12, 6, 8, P["purpled"], hi=P["purple"], sh=P["navy"])
    face(img, "tired", cx=16, cy=12, r=5)


def d_cross(img):
    outlined_rect(img, 13, 5, 6, 22, P["red"], hi=P["redh"], sh=P["redd"])
    outlined_rect(img, 6, 12, 20, 6, P["red"], hi=P["redh"], sh=P["redd"])


def d_leaf(img):
    for y in range(6, 28):
        for x in range(6, 26):
            if ((x - 16) / 8) ** 2 + ((y - 16) / 10) ** 2 <= 1:
                # left highlight / right shadow
                put(img, x, y, P["greenh"] if x < 14 else (P["green"] if x < 18 else P["greend"]))
    vline(img, 16, 9, 25, P["greend"])
    put(img, 16, 8, P["brownd"])
    put(img, 12, 12, P["lime"])
    put(img, 11, 14, P["lime"])
    # outline
    for y in range(6, 28):
        for x in range(6, 26):
            inside = ((x - 16) / 8) ** 2 + ((y - 16) / 10) ** 2
            if 0.85 < inside <= 1.05:
                put(img, x, y, P["ink"])


def d_avo(img):
    shaded_disk(img, 16, 17, 10, P["green"], P["lime"], P["greend"])
    shaded_disk(img, 16, 17, 5, P["brownd"], P["brown"], P["black"])
    put(img, 14, 15, P["brownh"])


def d_grape(img):
    for cx, cy in [(12, 12), (18, 12), (15, 16), (11, 17), (19, 17), (15, 21)]:
        shaded_disk(img, cx, cy, 3, P["purple"], P["purpleh"], P["purpled"])
    vline(img, 15, 6, 10, P["greend"])
    put(img, 16, 6, P["green"])


def d_sweet(img):
    # cupcake
    outlined_rect(img, 10, 16, 12, 10, P["brownh"], hi=P["cream"], sh=P["brownd"])
    ellipse(img, 16, 16, 8, 5, P["pink"])
    ellipse(img, 16, 14, 7, 4, P["pinkh"])
    disk(img, 16, 10, 3, P["red"])
    put(img, 16, 8, P["redh"])
    star(img, 24, 8, P["yellow"], 1)


def d_stretch(img):
    face(img, "happy", cx=16, cy=10, r=6)
    outlined_rect(img, 13, 16, 6, 8, P["teal"], hi=P["cyan"], sh=P["greend"])
    # arms up
    hline(img, 6, 13, 14, P["skin"])
    hline(img, 19, 26, 14, P["skin"])
    put(img, 6, 13, P["skind"])
    put(img, 26, 13, P["skind"])


def d_sweat(img):
    face(img, "wow", cx=16, cy=16, r=9)
    for x, y in [(6, 10), (7, 14), (25, 11), (24, 15), (8, 20)]:
        put(img, x, y, P["sky"])
        put(img, x, y + 1, P["blue"])


def d_center(img):
    # mandala / focus gem
    shaded_disk(img, 16, 16, 11, P["purpled"], P["purple"], P["navy"])
    shaded_disk(img, 16, 16, 7, P["purple"], P["purpleh"], P["purpled"])
    shaded_disk(img, 16, 16, 3, P["yellow"], P["yellowh"], P["goldd"])
    star(img, 16, 16, P["white"], 1)


def d_check(img):
    # clipboard / medical
    outlined_rect(img, 8, 6, 16, 22, P["offw"], hi=P["white"], sh=P["gray"])
    outlined_rect(img, 12, 4, 8, 5, P["redd"], hi=P["red"], sh=P["redd"])
    disk(img, 16, 14, 3, P["red"])
    hline(img, 15, 17, 14, P["white"])
    vline(img, 16, 13, 15, P["white"])
    hline(img, 11, 20, 20, P["gray"])
    hline(img, 11, 18, 23, P["gray"])


def d_mask(img):
    face(img, "neutral", cx=16, cy=14, r=8)
    # mask
    outlined_rect(img, 9, 16, 14, 6, P["sky"], hi=P["cyan"], sh=P["skyd"])
    hline(img, 7, 9, 18, P["gray"])
    hline(img, 23, 25, 18, P["gray"])


def d_bullet(img):
    d_shield(img)
    star(img, 16, 12, P["yellowh"], 2)


def generic(img, sid: str, area: str):
    rng = random.Random(sid)
    moods = ["happy", "sad", "tired", "wow", "angry", "neutral"]
    mood = moods[rng.randint(0, len(moods) - 1)]
    skins = [P["skin"], P["cream"], P["pinkh"], P["yellowh"], P["sky"]]
    sk = skins[rng.randint(0, len(skins) - 1)]

    if any(k in sid for k in ("face", "mind")):
        if "sick" in sid or mood == "angry" and "mh" in sid:
            face(img, mood, skin=sk)
        else:
            face(img, mood, skin=sk)
        if rng.random() < 0.35:
            star(img, rng.randint(3, 7), rng.randint(3, 8), P["yellow"], 1)
        if rng.random() < 0.25:
            d_zzz(img)
    elif "food" in sid or area == "diet":
        [d_apple, d_pizza, d_salad, d_mug, d_sweet, d_avo, d_grape][rng.randint(0, 6)](img)
    elif "move" in sid or area == "exercise":
        [d_runner, d_dumbbell, d_trophy, d_lightning, d_bike][rng.randint(0, 4)](img)
    elif "social" in sid or area == "relationships":
        [d_heart, d_phone, lambda i: (face(i, "happy", 11, 16, 6), face(i, "wow", 21, 16, 6))][rng.randint(0, 2)](img)
    elif "place" in sid or area == "environment":
        [d_tree, d_house, d_sun, d_rain, d_cloud][rng.randint(0, 4)](img)
    elif "care" in sid or area == "protect":
        [d_shield, d_pill, d_germ, d_cross, d_check][rng.randint(0, 4)](img)
    elif "moon" in sid or area == "sleep":
        if rng.random() < 0.5:
            d_moon(img)
        else:
            face(img, "tired", skin=sk)
            d_zzz(img)
        if rng.random() < 0.4:
            star(img, 6, 6, P["yellowh"], 1)
    else:
        face(img, mood, skin=sk)


def compose(*fns):
    def _f(img):
        for fn in fns:
            fn(img)
    return _f


DRAWERS: Dict[str, Callable] = {
    "sleep_great": compose(lambda i: face(i, "happy"), d_zzz, lambda i: star(i, 6, 6, P["yellow"], 1)),
    "sleep_rough": compose(lambda i: face(i, "sad"), d_zzz),
    "sleep_ok": lambda i: face(i, "neutral"),
    "sleep_good": compose(lambda i: face(i, "happy"), d_moon),
    "sleep_rested": compose(lambda i: face(i, "happy"), lambda i: star(i, 5, 5, P["gold"], 2)),
    "sleep_dozy": lambda i: face(i, "tired"),
    "sleep_zzz": compose(d_zzz, d_moon),
    "sleep_moon": d_moon,
    "sleep_bed": d_bed,
    "sleep_alarm": d_alarm,
    "sleep_early": compose(d_sun, lambda i: face(i, "tired", 16, 24, 5)),
    "sleep_late": compose(d_moon, lambda i: face(i, "wow", 16, 24, 5)),
    "sleep_broken": compose(lambda i: face(i, "sad"), d_moon),
    "sleep_in": d_bed,
    "sleep_owl": d_owl,
    "sleep_sheep": d_sheep,
    "sleep_ufo": d_ufo,
    "sleep_stars": compose(
        lambda i: star(i, 8, 8, P["yellow"], 2),
        lambda i: star(i, 22, 10, P["gold"], 2),
        lambda i: star(i, 16, 20, P["yellowh"], 1),
        lambda i: star(i, 6, 22, P["yellow"], 1),
    ),
    "sleep_mug": d_mug,
    "sleep_book": d_book,
    "diet_clean": d_salad,
    "diet_struggle": compose(lambda i: face(i, "sad", 10, 10, 5), d_pizza),
    "diet_enjoy": compose(lambda i: face(i, "happy", 10, 8, 5), d_pizza),
    "diet_onpoint": compose(d_salad, lambda i: star(i, 26, 6, P["yellow"], 2)),
    "diet_apple": d_apple,
    "diet_veg": d_salad,
    "diet_water": d_drop,
    "diet_pizza": d_pizza,
    "diet_sweet": d_sweet,
    "diet_comfort": d_mug,
    "diet_chef": d_chef,
    "diet_avo": d_avo,
    "diet_grape": d_grape,
    "diet_feast": compose(d_pizza, lambda i: star(i, 5, 5, P["gold"], 2), lambda i: star(i, 26, 7, P["yellow"], 1)),
    "diet_salad2": d_salad,
    "ex_crush": compose(d_dumbbell, lambda i: face(i, "wow", 16, 7, 5)),
    "ex_skip": d_couch,
    "ex_active": d_runner,
    "ex_walk": d_runner,
    "ex_stretch": d_stretch,
    "ex_bike": d_bike,
    "ex_lift": d_dumbbell,
    "ex_sweat": d_sweat,
    "ex_pr": d_trophy,
    "ex_champ": compose(d_trophy, lambda i: star(i, 5, 5, P["yellow"], 2)),
    "ex_beast": compose(lambda i: face(i, "angry", skin=P["orange"]), d_lightning),
    "ex_electric": d_lightning,
    "mh_calm": compose(lambda i: face(i, "happy"), d_cloud),
    "mh_good": lambda i: face(i, "happy"),
    "mh_mixed": lambda i: face(i, "neutral"),
    "mh_focus": compose(lambda i: face(i, "neutral"), lambda i: star(i, 25, 7, P["cyan"], 2)),
    "mh_light": compose(lambda i: face(i, "happy"), lambda i: star(i, 6, 6, P["yellow"], 2), lambda i: star(i, 25, 8, P["gold"], 1)),
    "mh_stress": compose(lambda i: face(i, "angry"), d_lightning),
    "mh_cloudy": compose(d_cloud, lambda i: face(i, "sad", 16, 24, 5)),
    "mh_burnout": compose(d_fire, lambda i: face(i, "sad", 16, 26, 4)),
    "mh_fog": compose(lambda i: d_cloud(i, 8), lambda i: d_cloud(i, 16)),
    "mh_struggle": lambda i: face(i, "sad"),
    "mh_hope": d_rainbow,
    "mh_inspired": compose(lambda i: face(i, "wow"), lambda i: star(i, 5, 5, P["gold"], 2), lambda i: star(i, 26, 7, P["yellow"], 2)),
    "mh_transform": d_butterfly,
    "mh_center": d_center,
    "rel_connect": compose(d_heart, lambda i: face(i, "happy", 16, 26, 4)),
    "rel_distant": lambda i: face(i, "sad"),
    "rel_loved": d_heart,
    "rel_grateful": compose(lambda i: face(i, "happy"), lambda i: star(i, 5, 5, P["gold"], 2)),
    "rel_support": compose(d_heart, lambda i: face(i, "happy", 16, 8, 5)),
    "rel_reach": d_phone,
    "rel_talk": compose(lambda i: face(i, "happy", 10, 16, 6), lambda i: face(i, "wow", 22, 16, 6)),
    "rel_social": compose(
        lambda i: face(i, "happy", 9, 14, 5),
        lambda i: face(i, "wow", 23, 14, 5),
        lambda i: face(i, "happy", 16, 22, 4),
    ),
    "rel_quiet": lambda i: face(i, "neutral"),
    "rel_bond": d_heart,
    "rel_cherish": compose(d_heart, lambda i: star(i, 6, 6, P["yellow"], 2)),
    "rel_peace": compose(d_leaf, lambda i: face(i, "happy", 16, 24, 4)),
    "rel_celeb": compose(
        lambda i: star(i, 8, 8, P["yellow"], 2),
        lambda i: star(i, 24, 10, P["gold"], 2),
        lambda i: face(i, "wow", 16, 18, 7),
    ),
    "rel_good": lambda i: face(i, "happy"),
    "env_fresh": compose(d_tree, d_sun),
    "env_heavy": d_rain,
    "env_bright": d_sun,
    "env_cozy": d_house,
    "env_tidy": compose(d_house, lambda i: star(i, 6, 6, P["lime"], 1)),
    "env_outdoors": compose(d_tree, d_sun),
    "env_clean": compose(d_drop, lambda i: star(i, 25, 7, P["cyan"], 1)),
    "env_air": compose(d_cloud, lambda i: star(i, 26, 22, P["sky"], 1)),
    "env_busy": compose(d_house, d_lightning),
    "env_nature": d_tree,
    "env_golden": compose(d_sun, lambda i: fill_rect(i, 2, 26, 28, 4, P["gold"])),
    "env_water": compose(d_drop, lambda i: ellipse(i, 16, 26, 10, 3, P["blue"])),
    "env_wild": compose(d_tree, lambda i: face(i, "wow", 24, 24, 4, P["yellowh"])),
    "env_clutter": compose(d_house, lambda i: face(i, "angry", 24, 10, 4)),
    "pr_ontop": d_shield,
    "pr_notgreat": face_sick,
    "pr_manage": d_pill,
    "pr_sun": compose(d_sun, lambda i: disk(i, 16, 22, 5, P["blue"])),
    "pr_hygiene": compose(d_drop, lambda i: star(i, 24, 8, P["white"], 1)),
    "pr_check": d_check,
    "pr_careful": d_mask,
    "pr_bullet": d_bullet,
    "pr_boost": d_mug,
    "pr_picture": compose(lambda i: face(i, "happy"), lambda i: star(i, 5, 5, P["gold"], 2), lambda i: star(i, 26, 6, P["yellow"], 2)),
    "pr_opt": compose(lambda i: face(i, "wow"), d_lightning),
    "pr_strong": compose(d_dumbbell, lambda i: face(i, "wow", 16, 7, 5)),
    "pr_natural": compose(d_tree, d_leaf),
    "pr_rest": d_bed,
    "pr_cross": d_cross,
    "pr_germ": d_germ,
    "pr_pill": d_pill,
}


def generate_one(sid: str, areas: List[str]) -> Image.Image:
    img = new_img()
    drawer = DRAWERS.get(sid)
    if drawer:
        try:
            drawer(img)
        except Exception as e:
            print(f"  ! {sid}: {e}")
            face(img, "happy")
    else:
        generic(img, sid, areas[0] if areas else "sleep")
    return img


def save(img: Image.Image, path: Path) -> None:
    big = img.resize((SIZE, SIZE), Image.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    big.save(path, "PNG", optimize=True)


def main():
    if not PIXEL_CATALOG.exists():
        raise SystemExit(f"Missing {PIXEL_CATALOG}")
    data = json.loads(PIXEL_CATALOG.read_text())
    stickers = data.get("stickers") or []
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out = []
    for s in stickers:
        sid = s["id"]
        areas = s.get("areas") or []
        img = generate_one(sid, areas)
        fname = f"{sid}.png"
        save(img, OUT_DIR / fname)
        out.append({
            "id": sid,
            "label": s.get("label") or sid,
            "areas": areas,
            "rare": bool(s.get("rare")),
            "file": fname,
            "src": f"/stickers/cartoon/{fname}",
            "size": SIZE,
            "style": "cartoon",
        })
        print(f"  {sid}")

    catalog = {
        "size": SIZE,
        "count": len(out),
        "style": "cartoon",
        "description": "Polished original SNES-style cartoon icons (not Nintendo assets)",
        "stickers": out,
    }
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n")
    print(f"\nWrote {len(out)} stickers → {OUT_DIR} ({SIZE}×{SIZE})")


if __name__ == "__main__":
    main()
