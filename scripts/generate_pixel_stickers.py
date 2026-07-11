#!/usr/bin/env python3
"""
Generate ~300 custom 32×32 pixel-art stickers for GreenDial check-ins.

Resolution matches on-board emoji display (~20–34px cells): source is 16×16
drawn with nearest-neighbor scale to 32×32 for crisp retina-ish display with
image-rendering: pixelated.

Run:
  python3 scripts/generate_pixel_stickers.py
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "stickers" / "pixel"
CATALOG = OUT_DIR / "catalog.json"

# Display size: 32×32 (2× scale of 16×16 art)
ART = 16
SCALE = 2
SIZE = ART * SCALE  # 32

# Consistent palette (RGBA)
P = {
    "bg": (0, 0, 0, 0),
    "ink": (30, 30, 40, 255),
    "white": (250, 250, 252, 255),
    "cream": (255, 245, 220, 255),
    "gray": (160, 165, 175, 255),
    "dgray": (90, 95, 110, 255),
    "green": (16, 185, 129, 255),
    "dgreen": (5, 120, 85, 255),
    "lime": (163, 230, 53, 255),
    "yellow": (250, 204, 21, 255),
    "gold": (234, 179, 8, 255),
    "orange": (249, 115, 22, 255),
    "red": (239, 68, 68, 255),
    "pink": (244, 114, 182, 255),
    "rose": (251, 113, 133, 255),
    "purple": (167, 139, 250, 255),
    "violet": (124, 58, 237, 255),
    "blue": (96, 165, 250, 255),
    "dblue": (37, 99, 235, 255),
    "sky": (125, 211, 252, 255),
    "navy": (30, 58, 95, 255),
    "brown": (180, 120, 70, 255),
    "dbrown": (120, 75, 40, 255),
    "teal": (45, 212, 191, 255),
    "cyan": (34, 211, 238, 255),
}


def new_canvas():
    return Image.new("RGBA", (ART, ART), P["bg"])


def setp(img, x, y, c):
    if 0 <= x < ART and 0 <= y < ART:
        img.putpixel((x, y), c)


def fill_rect(img, x, y, w, h, c):
    for j in range(y, y + h):
        for i in range(x, x + w):
            setp(img, i, j, c)


def circle(img, cx, cy, r, c, fill=True):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if fill and d2 <= r * r:
                setp(img, x, y, c)
            elif not fill and abs(d2 - r * r) <= r:
                setp(img, x, y, c)


def hline(img, x0, x1, y, c):
    for x in range(min(x0, x1), max(x0, x1) + 1):
        setp(img, x, y, c)


def vline(img, x, y0, y1, c):
    for y in range(min(y0, y1), max(y0, y1) + 1):
        setp(img, x, y, c)


def save_scaled(img16, path: Path):
    big = img16.resize((SIZE, SIZE), Image.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    big.save(path, "PNG")


# ── Primitive shapes used to compose stickers ──────────────────────────────

def face(img, mood="happy", skin=None, blush=False):
    skin = skin or P["cream"]
    circle(img, 7, 7, 6, skin)
    circle(img, 7, 7, 6, P["ink"], fill=False)
    # eyes
    setp(img, 5, 6, P["ink"])
    setp(img, 9, 6, P["ink"])
    if mood == "happy":
        hline(img, 5, 9, 9, P["ink"])
        setp(img, 5, 8, P["ink"])
        setp(img, 9, 8, P["ink"])
    elif mood == "sad":
        hline(img, 5, 9, 10, P["ink"])
        setp(img, 5, 9, P["ink"])
        setp(img, 9, 9, P["ink"])
    elif mood == "neutral":
        hline(img, 5, 9, 9, P["ink"])
    elif mood == "tired":
        hline(img, 4, 6, 6, P["ink"])
        hline(img, 8, 10, 6, P["ink"])
        hline(img, 5, 9, 10, P["dgray"])
    elif mood == "wow":
        circle(img, 7, 9, 1, P["ink"])
    if blush:
        setp(img, 4, 8, P["pink"])
        setp(img, 10, 8, P["pink"])


def moon(img, c=None):
    c = c or P["yellow"]
    circle(img, 8, 7, 5, c)
    circle(img, 10, 5, 4, P["bg"])  # crescent cutout via transparent
    # re-ink crescent edge
    for y in range(16):
        for x in range(16):
            if img.getpixel((x, y)) == c:
                if (x - 10) ** 2 + (y - 5) ** 2 <= 12:
                    setp(img, x, y, P["bg"])


def star(img, cx, cy, c):
    setp(img, cx, cy, c)
    setp(img, cx - 1, cy, c)
    setp(img, cx + 1, cy, c)
    setp(img, cx, cy - 1, c)
    setp(img, cx, cy + 1, c)
    setp(img, cx - 1, cy - 1, c)
    setp(img, cx + 1, cy - 1, c)
    setp(img, cx - 1, cy + 1, c)
    setp(img, cx + 1, cy + 1, c)


def heart(img, cx=7, cy=7, c=None):
    c = c or P["red"]
    setp(img, cx - 1, cy - 1, c)
    setp(img, cx + 1, cy - 1, c)
    fill_rect(img, cx - 2, cy, 5, 2, c)
    setp(img, cx - 1, cy + 2, c)
    setp(img, cx, cy + 2, c)
    setp(img, cx + 1, cy + 2, c)
    setp(img, cx, cy + 3, c)
    setp(img, cx - 1, cy, c)
    setp(img, cx + 1, cy, c)
    setp(img, cx, cy, c)


def leaf(img, cx=7, cy=7, c=None):
    c = c or P["green"]
    fill_rect(img, cx - 1, cy - 2, 3, 5, c)
    setp(img, cx, cy - 3, c)
    setp(img, cx, cy + 3, P["dgreen"])
    vline(img, cx, cy - 1, cy + 2, P["dgreen"])


def apple(img):
    circle(img, 7, 9, 4, P["red"])
    setp(img, 7, 4, P["dbrown"])
    setp(img, 8, 3, P["green"])
    setp(img, 9, 4, P["green"])
    setp(img, 5, 7, P["white"])  # shine


def dumbbell(img):
    fill_rect(img, 2, 6, 3, 4, P["dgray"])
    fill_rect(img, 11, 6, 3, 4, P["dgray"])
    hline(img, 5, 10, 7, P["gray"])
    hline(img, 5, 10, 8, P["gray"])


def shield(img, c=None):
    c = c or P["blue"]
    fill_rect(img, 4, 3, 8, 8, c)
    for i in range(4):
        hline(img, 5 + i, 10 - i, 11 + i, c)
    setp(img, 7, 6, P["white"])
    setp(img, 8, 6, P["white"])
    setp(img, 7, 7, P["white"])


def zzz(img):
    # sleep z's
    setp(img, 10, 2, P["purple"])
    hline(img, 10, 12, 2, P["purple"])
    setp(img, 12, 3, P["purple"])
    hline(img, 10, 12, 4, P["purple"])
    setp(img, 8, 5, P["violet"])
    hline(img, 8, 9, 5, P["violet"])
    setp(img, 9, 6, P["violet"])


def sun(img):
    circle(img, 7, 7, 3, P["yellow"])
    for dx, dy in [(-5, 0), (5, 0), (0, -5), (0, 5), (-4, -4), (4, -4), (-4, 4), (4, 4)]:
        setp(img, 7 + dx, 7 + dy, P["gold"])


def cloud(img, y=5):
    fill_rect(img, 3, y + 1, 10, 3, P["white"])
    fill_rect(img, 5, y, 6, 2, P["white"])
    circle(img, 5, y + 2, 2, P["white"])
    circle(img, 10, y + 2, 2, P["white"])


def rain(img):
    cloud(img, 3)
    for x in (4, 7, 10):
        setp(img, x, 9, P["blue"])
        setp(img, x, 11, P["sky"])
        setp(img, x + 1, 13, P["blue"])


def fire(img):
    fill_rect(img, 5, 8, 6, 5, P["orange"])
    fill_rect(img, 6, 5, 4, 4, P["yellow"])
    setp(img, 7, 3, P["yellow"])
    setp(img, 8, 4, P["orange"])
    setp(img, 6, 10, P["red"])
    setp(img, 9, 11, P["red"])


def water_drop(img):
    setp(img, 7, 2, P["sky"])
    fill_rect(img, 5, 4, 5, 2, P["blue"])
    circle(img, 7, 9, 4, P["blue"])
    setp(img, 6, 8, P["sky"])


def pill(img):
    fill_rect(img, 3, 6, 5, 4, P["rose"])
    fill_rect(img, 8, 6, 5, 4, P["white"])
    hline(img, 3, 12, 5, P["ink"])
    hline(img, 3, 12, 10, P["ink"])


def book(img):
    fill_rect(img, 3, 3, 10, 11, P["dblue"])
    fill_rect(img, 4, 4, 8, 9, P["cream"])
    hline(img, 5, 10, 7, P["gray"])
    hline(img, 5, 10, 9, P["gray"])


def house(img):
    fill_rect(img, 4, 7, 8, 7, P["brown"])
    # roof
    for i in range(5):
        hline(img, 7 - i, 7 + i, 6 - i, P["red"])
    fill_rect(img, 6, 10, 3, 4, P["dbrown"])
    setp(img, 5, 9, P["yellow"])  # window


def tree(img):
    fill_rect(img, 7, 10, 2, 5, P["dbrown"])
    circle(img, 7, 7, 4, P["green"])
    circle(img, 7, 6, 3, P["lime"])


def bike(img):
    circle(img, 4, 11, 2, P["ink"], fill=False)
    circle(img, 11, 11, 2, P["ink"], fill=False)
    hline(img, 4, 11, 9, P["dgray"])
    setp(img, 7, 7, P["red"])
    setp(img, 8, 8, P["red"])
    vline(img, 8, 8, 11, P["gray"])


def trophy(img):
    fill_rect(img, 5, 4, 6, 5, P["gold"])
    fill_rect(img, 6, 9, 4, 2, P["gold"])
    fill_rect(img, 4, 12, 8, 2, P["gold"])
    setp(img, 3, 5, P["gold"])
    setp(img, 12, 5, P["gold"])


def lightning(img):
    pts = [(8, 1), (5, 7), (7, 7), (4, 14), (11, 6), (9, 6), (12, 1)]
    # rough bolt
    fill_rect(img, 7, 1, 3, 5, P["yellow"])
    fill_rect(img, 5, 5, 4, 2, P["yellow"])
    fill_rect(img, 6, 7, 3, 4, P["gold"])
    setp(img, 5, 11, P["yellow"])
    setp(img, 4, 12, P["yellow"])
    setp(img, 3, 13, P["gold"])


def brain(img):
    circle(img, 6, 7, 4, P["pink"])
    circle(img, 10, 7, 4, P["rose"])
    fill_rect(img, 5, 9, 6, 3, P["pink"])
    setp(img, 7, 5, P["white"])
    setp(img, 9, 6, P["white"])


def salad(img):
    circle(img, 7, 9, 5, P["dgreen"])
    circle(img, 7, 8, 4, P["green"])
    setp(img, 5, 7, P["red"])
    setp(img, 9, 8, P["orange"])
    setp(img, 7, 10, P["yellow"])
    setp(img, 6, 9, P["lime"])


def pizza(img):
    # slice
    for y in range(3, 14):
        w = (y - 2) // 2
        hline(img, 7 - w, 7 + w, y, P["gold"])
    for y in range(4, 13):
        w = max(0, (y - 3) // 2 - 0)
        if w:
            hline(img, 7 - w + 1, 7 + w - 1, y, P["yellow"])
    setp(img, 6, 7, P["red"])
    setp(img, 8, 9, P["red"])
    setp(img, 7, 11, P["red"])


def bed(img):
    fill_rect(img, 2, 9, 12, 4, P["dblue"])
    fill_rect(img, 3, 7, 5, 3, P["cream"])  # pillow
    fill_rect(img, 8, 8, 5, 2, P["blue"])  # blanket
    vline(img, 2, 6, 12, P["dbrown"])
    vline(img, 13, 8, 12, P["dbrown"])


def alarm(img):
    circle(img, 7, 8, 5, P["red"])
    circle(img, 7, 8, 4, P["white"])
    setp(img, 7, 8, P["ink"])
    vline(img, 7, 5, 8, P["ink"])
    hline(img, 7, 10, 8, P["ink"])
    setp(img, 3, 3, P["dgray"])
    setp(img, 11, 3, P["dgray"])


def mug(img):
    fill_rect(img, 4, 5, 7, 8, P["cream"])
    fill_rect(img, 5, 6, 5, 5, P["brown"])
    setp(img, 11, 7, P["cream"])
    setp(img, 12, 8, P["cream"])
    setp(img, 11, 9, P["cream"])
    # steam
    setp(img, 6, 2, P["gray"])
    setp(img, 8, 1, P["gray"])
    setp(img, 9, 3, P["gray"])


def stretch_person(img):
    # simple stick figure arms up
    circle(img, 7, 3, 2, P["cream"])
    vline(img, 7, 5, 10, P["blue"])
    hline(img, 3, 11, 6, P["blue"])
    setp(img, 5, 11, P["navy"])
    setp(img, 9, 11, P["navy"])
    setp(img, 4, 12, P["navy"])
    setp(img, 10, 12, P["navy"])


def walk_person(img):
    circle(img, 7, 3, 2, P["cream"])
    vline(img, 7, 5, 9, P["green"])
    setp(img, 6, 10, P["navy"])
    setp(img, 8, 11, P["navy"])
    setp(img, 5, 12, P["navy"])
    setp(img, 9, 13, P["navy"])
    hline(img, 5, 9, 6, P["green"])


def run_person(img):
    circle(img, 8, 3, 2, P["cream"])
    setp(img, 7, 5, P["orange"])
    setp(img, 8, 6, P["orange"])
    setp(img, 9, 7, P["orange"])
    setp(img, 6, 8, P["orange"])
    setp(img, 5, 10, P["navy"])
    setp(img, 10, 9, P["navy"])
    setp(img, 4, 12, P["navy"])
    setp(img, 11, 11, P["navy"])
    setp(img, 12, 4, P["yellow"])  # sweat


def phone(img):
    fill_rect(img, 5, 2, 6, 12, P["ink"])
    fill_rect(img, 6, 3, 4, 9, P["sky"])
    hline(img, 7, 8, 13, P["gray"])


def chat_bubbles(img):
    fill_rect(img, 2, 3, 8, 5, P["blue"])
    setp(img, 3, 8, P["blue"])
    fill_rect(img, 6, 8, 8, 5, P["green"])
    setp(img, 12, 13, P["green"])


def handshake(img):
    fill_rect(img, 2, 7, 5, 3, P["cream"])
    fill_rect(img, 9, 7, 5, 3, P["cream"])
    fill_rect(img, 5, 6, 6, 4, P["brown"])
    hline(img, 4, 11, 8, P["dbrown"])


def sun_cloud(img):
    sun(img)
    # partial cloud over
    fill_rect(img, 6, 9, 8, 3, P["white"])
    circle(img, 8, 9, 2, P["white"])
    circle(img, 12, 10, 2, P["white"])


def mountain(img):
    for y in range(14):
        w = y // 2
        hline(img, 7 - w, 7 + w, 14 - y, P["dgray"] if y < 8 else P["gray"])
    setp(img, 7, 3, P["white"])
    setp(img, 6, 4, P["white"])
    setp(img, 8, 4, P["white"])
    hline(img, 0, 15, 14, P["green"])


def germ(img):
    circle(img, 7, 7, 4, P["lime"])
    for a in range(8):
        import math
        x = 7 + int(6 * math.cos(a * 0.785))
        y = 7 + int(6 * math.sin(a * 0.785))
        setp(img, x, y, P["green"])
    setp(img, 5, 6, P["ink"])
    setp(img, 9, 6, P["ink"])


def med_cross(img):
    fill_rect(img, 6, 2, 4, 12, P["red"])
    fill_rect(img, 2, 6, 12, 4, P["red"])
    fill_rect(img, 7, 3, 2, 10, P["white"])
    fill_rect(img, 3, 7, 10, 2, P["white"])


def sparkles(img):
    star(img, 4, 4, P["yellow"])
    star(img, 11, 6, P["gold"])
    star(img, 7, 11, P["yellow"])
    star(img, 12, 12, P["cream"])


def butterfly(img):
    circle(img, 4, 6, 3, P["purple"])
    circle(img, 11, 6, 3, P["violet"])
    circle(img, 4, 10, 2, P["pink"])
    circle(img, 11, 10, 2, P["rose"])
    vline(img, 7, 4, 12, P["ink"])
    setp(img, 7, 3, P["ink"])


def owl(img):
    circle(img, 7, 8, 5, P["brown"])
    circle(img, 5, 7, 2, P["cream"])
    circle(img, 9, 7, 2, P["cream"])
    setp(img, 5, 7, P["ink"])
    setp(img, 9, 7, P["ink"])
    setp(img, 7, 9, P["orange"])
    setp(img, 4, 3, P["dbrown"])
    setp(img, 10, 3, P["dbrown"])


def sheep(img):
    circle(img, 7, 8, 5, P["white"])
    circle(img, 5, 7, 2, P["white"])
    circle(img, 9, 7, 2, P["white"])
    circle(img, 11, 9, 2, P["cream"])  # face
    setp(img, 11, 8, P["ink"])
    setp(img, 12, 9, P["pink"])
    setp(img, 5, 12, P["dgray"])
    setp(img, 9, 12, P["dgray"])


def ufo(img):
    fill_rect(img, 3, 7, 10, 3, P["gray"])
    circle(img, 7, 6, 3, P["cyan"])
    setp(img, 5, 11, P["yellow"])
    setp(img, 7, 12, P["yellow"])
    setp(img, 9, 11, P["yellow"])


def avocado(img):
    circle(img, 7, 8, 5, P["dgreen"])
    circle(img, 7, 8, 4, P["lime"])
    circle(img, 7, 8, 2, P["dbrown"])


def grape(img):
    for cx, cy in [(5, 6), (8, 6), (11, 6), (6, 9), (9, 9), (7, 12)]:
        circle(img, cx, cy, 2, P["violet"])
    setp(img, 8, 3, P["dgreen"])
    setp(img, 9, 2, P["green"])


def lobster(img):
    fill_rect(img, 5, 5, 6, 7, P["red"])
    setp(img, 3, 6, P["red"])
    setp(img, 2, 5, P["red"])
    setp(img, 12, 6, P["red"])
    setp(img, 13, 5, P["red"])
    setp(img, 6, 12, P["red"])
    setp(img, 9, 12, P["red"])
    setp(img, 6, 7, P["ink"])
    setp(img, 9, 7, P["ink"])


def medal(img):
    circle(img, 7, 9, 4, P["gold"])
    circle(img, 7, 9, 2, P["yellow"])
    fill_rect(img, 5, 1, 2, 5, P["red"])
    fill_rect(img, 8, 1, 2, 5, P["blue"])


def hero(img):
    # cape + body
    fill_rect(img, 5, 6, 6, 6, P["blue"])
    circle(img, 7, 3, 2, P["cream"])
    fill_rect(img, 10, 6, 3, 6, P["red"])  # cape
    setp(img, 7, 7, P["yellow"])  # emblem


def rainbow(img):
    colors = [P["red"], P["orange"], P["yellow"], P["green"], P["blue"], P["purple"]]
    for i, c in enumerate(colors):
        for x in range(2, 14):
            y = 10 - int((1 - ((x - 7) / 6) ** 2) * (6 - i * 0.5))
            setp(img, x, y + i // 2, c)


def candle(img):
    fill_rect(img, 6, 7, 4, 7, P["cream"])
    fill_rect(img, 5, 13, 6, 2, P["dgray"])
    setp(img, 7, 5, P["yellow"])
    setp(img, 8, 4, P["orange"])
    setp(img, 7, 3, P["yellow"])


def dove(img):
    # simple bird
    fill_rect(img, 4, 7, 8, 3, P["white"])
    setp(img, 3, 6, P["white"])
    setp(img, 11, 6, P["white"])
    setp(img, 12, 7, P["orange"])
    setp(img, 5, 6, P["ink"])
    setp(img, 7, 9, P["gray"])
    setp(img, 8, 10, P["gray"])


def party(img):
    # confetti + smile
    face(img, "happy")
    setp(img, 2, 2, P["red"])
    setp(img, 13, 3, P["yellow"])
    setp(img, 3, 12, P["blue"])
    setp(img, 12, 13, P["green"])
    setp(img, 1, 7, P["purple"])
    setp(img, 14, 8, P["orange"])


def nature_park(img):
    tree(img)
    # second smaller tree
    fill_rect(img, 12, 11, 1, 3, P["dbrown"])
    circle(img, 12, 9, 2, P["green"])
    hline(img, 0, 15, 14, P["dgreen"])
    sun_dot = True
    setp(img, 2, 2, P["yellow"])
    setp(img, 3, 2, P["yellow"])
    setp(img, 2, 3, P["yellow"])


def water_scene(img):
    hline(img, 0, 15, 10, P["blue"])
    hline(img, 0, 15, 11, P["sky"])
    hline(img, 0, 15, 12, P["blue"])
    hline(img, 0, 15, 13, P["dblue"])
    # boat
    fill_rect(img, 5, 8, 6, 2, P["brown"])
    vline(img, 7, 4, 8, P["dgray"])
    setp(img, 8, 5, P["white"])
    setp(img, 9, 6, P["white"])


def wildlife(img):
    # parrot-ish
    circle(img, 7, 7, 4, P["green"])
    setp(img, 10, 7, P["red"])
    setp(img, 11, 7, P["orange"])
    setp(img, 5, 6, P["ink"])
    setp(img, 6, 10, P["yellow"])
    setp(img, 8, 11, P["yellow"])
    setp(img, 3, 5, P["blue"])
    setp(img, 3, 6, P["blue"])


def armor_arm(img):
    fill_rect(img, 4, 4, 8, 9, P["gray"])
    fill_rect(img, 5, 5, 6, 7, P["dgray"])
    setp(img, 7, 8, P["cyan"])
    setp(img, 8, 8, P["cyan"])
    hline(img, 4, 11, 12, P["ink"])


def tea(img):
    fill_rect(img, 4, 6, 8, 7, P["cream"])
    fill_rect(img, 5, 7, 6, 5, P["dgreen"])
    setp(img, 12, 8, P["cream"])
    setp(img, 13, 9, P["cream"])
    setp(img, 6, 3, P["gray"])
    setp(img, 8, 2, P["gray"])
    setp(img, 9, 4, P["green"])


def dna(img):
    for i in range(12):
        y = 2 + i
        x1 = 5 + (i % 4) - 1
        x2 = 10 - (i % 4) + 1
        setp(img, x1, y, P["cyan"])
        setp(img, x2, y, P["pink"])
        if i % 2 == 0:
            hline(img, x1, x2, y, P["purple"])


def soap(img):
    fill_rect(img, 3, 6, 10, 6, P["sky"])
    fill_rect(img, 4, 7, 8, 4, P["white"])
    circle(img, 5, 4, 1, P["white"])
    circle(img, 8, 3, 2, P["white"])
    circle(img, 11, 5, 1, P["white"])


def sun_safe(img):
    sun(img)
    # lotion bottle
    fill_rect(img, 11, 9, 3, 5, P["orange"])
    setp(img, 12, 8, P["dgray"])


def rest_bed(img):
    bed(img)
    zzz(img)


def strong(img):
    # flexed arm
    fill_rect(img, 3, 8, 6, 4, P["cream"])
    fill_rect(img, 7, 5, 4, 5, P["cream"])
    circle(img, 10, 4, 2, P["cream"])
    setp(img, 5, 9, P["red"])  # band


def managing(img):
    med_cross(img)
    # check
    setp(img, 11, 11, P["green"])
    setp(img, 12, 12, P["green"])
    setp(img, 13, 10, P["green"])


def natural_leaf(img):
    leaf(img, 7, 7)
    leaf(img, 10, 9, P["lime"])
    leaf(img, 4, 9, P["dgreen"])


def hygiene(img):
    soap(img)


def checked_in(img):
    # clipboard check
    fill_rect(img, 4, 2, 8, 12, P["cream"])
    fill_rect(img, 5, 1, 6, 2, P["dgray"])
    hline(img, 5, 10, 5, P["gray"])
    hline(img, 5, 10, 7, P["gray"])
    setp(img, 6, 10, P["green"])
    setp(img, 7, 11, P["green"])
    setp(img, 8, 9, P["green"])


def careful(img):
    # mask face
    face(img, "neutral")
    fill_rect(img, 4, 8, 8, 3, P["sky"])
    hline(img, 3, 4, 8, P["gray"])
    hline(img, 11, 12, 8, P["gray"])


def bulletproof(img):
    shield(img, P["dgray"])
    setp(img, 7, 6, P["yellow"])
    setp(img, 7, 7, P["yellow"])
    setp(img, 7, 8, P["yellow"])


def immunity(img):
    tea(img)


def picture_health(img):
    star(img, 7, 7, P["gold"])
    circle(img, 7, 7, 5, P["yellow"], fill=False)
    sparkles(img)


def optimized(img):
    dna(img)


# ── Catalog definition: compose many variants ──────────────────────────────

def _variant(base_fn, recolor=None, extras=None):
    def fn():
        img = new_canvas()
        base_fn(img)
        if recolor:
            # simple recolor non-transparent pixels matching first key
            pass
        if extras:
            for ex in extras:
                ex(img)
        return img
    return fn


def paint_face(mood, blush=False):
    """Return a painter(img) for faces."""
    def paint(img):
        face(img, mood, blush=blush)
    return paint


def face_mood(mood, blush=False):
    """Zero-arg generator: full sticker with a face."""
    def fn():
        img = new_canvas()
        face(img, mood, blush=blush)
        return img
    return fn


def shape_only(drawer, *args, **kwargs):
    """Zero-arg generator wrapping a drawer(img, ...)."""
    def fn():
        img = new_canvas()
        if args or kwargs:
            drawer(img, *args, **kwargs)
        else:
            drawer(img)
        return img
    return fn


def multi(*parts):
    """Compose painters and/or zero-arg generators into one sticker."""
    def fn():
        img = new_canvas()
        for p in parts:
            try:
                p(img)  # painter(img)
            except TypeError:
                layer = p()  # zero-arg generator → Image
                if layer is not None:
                    img = Image.alpha_composite(img, layer.convert("RGBA"))
        return img
    return fn


# Build list of (id, label, areas, rare, generator)
STICKERS = []


def add(sid, label, areas, gen, rare=False):
    STICKERS.append({
        "id": sid,
        "label": label,
        "areas": areas,
        "rare": rare,
        "gen": gen,
        "file": f"{sid}.png",
    })


def build_catalog():
    """Define ~300 stickers across 7 health areas + shared."""
    STICKERS.clear()

    # ── SLEEP (~45) ──
    sleep = ["sleep"]
    add("sleep_great", "Slept great", sleep, face_mood("happy", True))
    add("sleep_rough", "Rough night", sleep, face_mood("tired"))
    add("sleep_ok", "OK sleep", sleep, face_mood("neutral"))
    add("sleep_good", "Good sleep", sleep, face_mood("happy"))
    add("sleep_rested", "Rested", sleep, multi(paint_face("happy"), sparkles))
    add("sleep_dozy", "Dozy", sleep, face_mood("tired"))
    add("sleep_zzz", "Zzz", sleep, multi(moon, zzz))
    add("sleep_moon", "Moon", sleep, shape_only(moon))
    add("sleep_bed", "Bed", sleep, shape_only(bed))
    add("sleep_alarm", "Alarm", sleep, shape_only(alarm))
    add("sleep_early", "Woke early", sleep, multi(alarm, sun))
    add("sleep_late", "Late night", sleep, multi(moon, lambda i: star(i, 12, 3, P["yellow"])))
    add("sleep_broken", "Broken sleep", sleep, multi(moon, lambda i: fill_rect(i, 6, 6, 4, 1, P["red"])))
    add("sleep_in", "Slept in", sleep, multi(bed, sun))
    add("sleep_owl", "Night owl", sleep, shape_only(owl), rare=True)
    add("sleep_sheep", "Counted sheep", sleep, shape_only(sheep), rare=True)
    add("sleep_ufo", "Wild dreams", sleep, shape_only(ufo), rare=True)
    add("sleep_stars", "Stargazer", sleep, multi(lambda i: star(i, 3, 3, P["yellow"]), lambda i: star(i, 8, 5, P["gold"]), lambda i: star(i, 12, 2, P["yellow"]), moon), rare=True)
    add("sleep_mug", "Nightcap", sleep, shape_only(mug))
    add("sleep_book", "Read in bed", sleep, multi(book, zzz))
    # numbered sleep variants
    for n, mood in enumerate(["happy", "neutral", "sad", "tired", "wow"] * 3):
        add(f"sleep_face_{n:02d}", f"Sleep face {n+1}", sleep, face_mood(mood, n % 2 == 0))
    for n in range(12):
        def gen_moon(n=n):
            img = new_canvas()
            moon(img, [P["yellow"], P["cream"], P["gold"], P["sky"]][n % 4])
            if n % 3 == 0:
                star(img, 2, 2, P["white"])
            if n % 3 == 1:
                zzz(img)
            if n % 3 == 2:
                cloud(img, 11)
            return img
        add(f"sleep_moon_{n:02d}", f"Moon {n+1}", sleep, gen_moon, rare=(n >= 9))

    # ── DIET (~45) ──
    diet = ["diet"]
    add("diet_clean", "Clean & healthy", diet, shape_only(salad))
    add("diet_struggle", "Struggled", diet, face_mood("sad"))
    add("diet_enjoy", "Enjoyed it", diet, face_mood("happy", True))
    add("diet_onpoint", "On point", diet, multi(salad, lambda i: star(i, 13, 2, P["gold"])))
    add("diet_apple", "Fruity", diet, shape_only(apple))
    add("diet_veg", "Veggies", diet, shape_only(leaf))
    add("diet_water", "Hydrated", diet, shape_only(water_drop))
    add("diet_pizza", "Indulgent", diet, shape_only(pizza))
    add("diet_sweet", "Sweet tooth", diet, multi(lambda i: circle(i, 7, 8, 5, P["pink"]), lambda i: fill_rect(i, 4, 4, 8, 2, P["cream"]), lambda i: setp(i, 7, 6, P["red"])))
    add("diet_comfort", "Comfort food", diet, multi(lambda i: fill_rect(i, 3, 8, 10, 5, P["cream"]), lambda i: fill_rect(i, 4, 6, 8, 3, P["gold"]), lambda i: setp(i, 6, 7, P["green"])))
    add("diet_chef", "Chef mode", diet, multi(paint_face("happy"), lambda i: fill_rect(i, 4, 1, 8, 3, P["white"])), rare=True)
    add("diet_avo", "Avocado win", diet, shape_only(avocado), rare=True)
    add("diet_grape", "Superfood", diet, shape_only(grape), rare=True)
    add("diet_feast", "Feast", diet, shape_only(lobster), rare=True)
    add("diet_salad2", "Big salad", diet, multi(salad, water_drop))
    for n in range(15):
        def gen_food(n=n):
            img = new_canvas()
            opts = [apple, salad, avocado, grape, pizza, water_drop, leaf]
            opts[n % len(opts)](img)
            if n % 2:
                star(img, 13, 2, P["yellow"])
            return img
        add(f"diet_food_{n:02d}", f"Food {n+1}", diet, gen_food, rare=(n >= 12))
    for n, mood in enumerate(["happy", "neutral", "wow"] * 4):
        add(f"diet_face_{n:02d}", f"Diet face {n+1}", diet, face_mood(mood, n % 3 == 0))

    # ── EXERCISE (~45) ──
    ex = ["exercise"]
    add("ex_crush", "Crushed it", ex, multi(strong, sparkles))
    add("ex_skip", "Skipped it", ex, multi(paint_face("sad"), lambda i: fill_rect(i, 3, 10, 10, 4, P["brown"])))
    add("ex_active", "Active", ex, shape_only(run_person))
    add("ex_walk", "Walked", ex, shape_only(walk_person))
    add("ex_stretch", "Stretched", ex, shape_only(stretch_person))
    add("ex_bike", "Cycled", ex, shape_only(bike))
    add("ex_lift", "Lifted", ex, shape_only(dumbbell))
    add("ex_sweat", "Sweaty", ex, multi(run_person, lambda i: setp(i, 12, 3, P["sky"])))
    add("ex_pr", "Personal record", ex, shape_only(trophy), rare=True)
    add("ex_champ", "Champion", ex, shape_only(medal), rare=True)
    add("ex_beast", "Beast mode", ex, shape_only(hero), rare=True)
    add("ex_electric", "Electric", ex, shape_only(lightning), rare=True)
    for n in range(18):
        def gen_ex(n=n):
            img = new_canvas()
            [dumbbell, bike, run_person, walk_person, stretch_person, strong, trophy, lightning][n % 8](img)
            if n % 4 == 0:
                star(img, 2, 2, P["gold"])
            return img
        add(f"ex_move_{n:02d}", f"Move {n+1}", ex, gen_ex, rare=(n >= 15))
    for n, mood in enumerate(["happy", "wow", "neutral"] * 4):
        add(f"ex_face_{n:02d}", f"Exercise face {n+1}", ex, face_mood(mood))

    # ── MENTAL HEALTH (~42) ──
    mh = ["mental_health"]
    add("mh_calm", "Calm & clear", mh, face_mood("happy", True))
    add("mh_struggle", "Struggling", mh, face_mood("sad"))
    add("mh_good", "Good", mh, face_mood("happy"))
    add("mh_mixed", "Mixed", mh, face_mood("neutral"))
    add("mh_focus", "Focused", mh, shape_only(brain))
    add("mh_light", "Light", mh, multi(paint_face("happy"), sparkles))
    add("mh_stress", "Stressed", mh, multi(paint_face("sad"), fire))
    add("mh_cloudy", "Cloudy", mh, multi(cloud, paint_face("neutral")))
    add("mh_burnout", "Burnt out", mh, multi(fire, paint_face("tired")))
    add("mh_fog", "Foggy", mh, multi(cloud, lambda i: fill_rect(i, 2, 10, 12, 3, P["gray"])))
    add("mh_hope", "Hopeful", mh, shape_only(rainbow), rare=True)
    add("mh_inspired", "Inspired", mh, multi(sparkles, paint_face("wow")), rare=True)
    add("mh_transform", "Transformed", mh, shape_only(butterfly), rare=True)
    add("mh_center", "Centered", mh, shape_only(candle), rare=True)
    for n in range(16):
        def gen_mh(n=n):
            img = new_canvas()
            [brain, candle, butterfly, rainbow, sparkles,
             lambda i: face(i, "happy"), lambda i: face(i, "sad"), cloud][n % 8](img)
            return img
        add(f"mh_mind_{n:02d}", f"Mind {n+1}", mh, gen_mh, rare=(n >= 13))
    for n, mood in enumerate(["happy", "sad", "neutral", "tired", "wow"] * 2):
        add(f"mh_face_{n:02d}", f"Mind face {n+1}", mh, face_mood(mood, n % 2 == 0))

    # ── RELATIONSHIPS (~42) ──
    rel = ["relationships"]
    add("rel_connect", "Very connected", rel, multi(heart, paint_face("happy")))
    add("rel_distant", "Distant", rel, face_mood("sad"))
    add("rel_loved", "Loved", rel, shape_only(heart))
    add("rel_good", "Good", rel, face_mood("happy", True))
    add("rel_grateful", "Grateful", rel, multi(paint_face("happy"), lambda i: star(i, 12, 2, P["gold"])))
    add("rel_support", "Supported", rel, shape_only(handshake))
    add("rel_reach", "Reached out", rel, shape_only(phone))
    add("rel_talk", "Good talk", rel, shape_only(chat_bubbles))
    add("rel_social", "Social", rel, multi(party, paint_face("happy")))
    add("rel_quiet", "Quiet", rel, face_mood("neutral"))
    add("rel_bond", "Deep bond", rel, multi(lambda i: heart(i, 5, 7, P["red"]), lambda i: heart(i, 10, 8, P["pink"])), rare=True)
    add("rel_cherish", "Cherished", rel, multi(heart, sparkles), rare=True)
    add("rel_peace", "Made peace", rel, shape_only(dove), rare=True)
    add("rel_celeb", "Celebrated", rel, shape_only(party), rare=True)
    for n in range(16):
        def gen_rel(n=n):
            img = new_canvas()
            [heart, handshake, phone, chat_bubbles, dove, party,
             lambda i: face(i, "happy"), lambda i: face(i, "sad")][n % 8](img)
            return img
        add(f"rel_social_{n:02d}", f"Social {n+1}", rel, gen_rel, rare=(n >= 13))
    for n, mood in enumerate(["happy", "sad", "neutral"] * 4):
        add(f"rel_face_{n:02d}", f"Rel face {n+1}", rel, face_mood(mood, True))

    # ── ENVIRONMENT (~40) ──
    env = ["environment"]
    add("env_fresh", "Fresh & calm", env, multi(leaf, sun))
    add("env_heavy", "Heavy", env, shape_only(rain))
    add("env_bright", "Bright", env, shape_only(sun))
    add("env_cozy", "Cozy", env, shape_only(house))
    add("env_tidy", "Tidy", env, multi(house, lambda i: star(i, 12, 3, P["yellow"])))
    add("env_outdoors", "Outdoors", env, shape_only(tree))
    add("env_clean", "Cleaned up", env, multi(house, sparkles))
    add("env_air", "Aired out", env, multi(cloud, leaf))
    add("env_clutter", "Cluttered", env, multi(house, paint_face("tired")))
    add("env_busy", "Busy", env, multi(house, cloud))
    add("env_nature", "Nature day", env, shape_only(nature_park), rare=True)
    add("env_golden", "Golden hour", env, multi(sun, mountain), rare=True)
    add("env_water", "By the water", env, shape_only(water_scene), rare=True)
    add("env_wild", "Wildlife", env, shape_only(wildlife), rare=True)
    for n in range(14):
        def gen_env(n=n):
            img = new_canvas()
            [tree, house, sun, rain, mountain, leaf, cloud, sun_cloud][n % 8](img)
            return img
        add(f"env_place_{n:02d}", f"Place {n+1}", env, gen_env, rare=(n >= 11))
    for n in range(12):
        add(f"env_face_{n:02d}", f"Env face {n+1}", env, face_mood(["happy", "neutral", "sad"][n % 3]))

    # ── PROTECT (~40) ──
    pr = ["protect"]
    add("pr_ontop", "On top of it", pr, shape_only(shield))
    add("pr_notgreat", "Not great", pr, face_mood("sad"))
    add("pr_strong", "Strong", pr, shape_only(strong))
    add("pr_manage", "Managing", pr, shape_only(managing))
    add("pr_natural", "Natural", pr, shape_only(natural_leaf))
    add("pr_sun", "Sun-safe", pr, shape_only(sun_safe))
    add("pr_hygiene", "Hygiene", pr, shape_only(hygiene))
    add("pr_check", "Checked in", pr, shape_only(checked_in))
    add("pr_careful", "Careful", pr, shape_only(careful))
    add("pr_rest", "Resting up", pr, shape_only(rest_bed))
    add("pr_bullet", "Bulletproof", pr, shape_only(bulletproof), rare=True)
    add("pr_boost", "Immunity boost", pr, shape_only(immunity), rare=True)
    add("pr_picture", "Picture of health", pr, shape_only(picture_health), rare=True)
    add("pr_opt", "Optimized", pr, shape_only(optimized), rare=True)
    add("pr_pill", "Meds", pr, shape_only(pill))
    add("pr_cross", "Care", pr, shape_only(med_cross))
    add("pr_germ", "Bug day", pr, shape_only(germ))
    for n in range(14):
        def gen_pr(n=n):
            img = new_canvas()
            [shield, pill, med_cross, tea, dna, soap, strong, germ][n % 8](img)
            return img
        add(f"pr_care_{n:02d}", f"Protect {n+1}", pr, gen_pr, rare=(n >= 11))
    for n in range(10):
        add(f"pr_face_{n:02d}", f"Protect face {n+1}", pr, face_mood(["happy", "neutral", "wow"][n % 3]))

    # ── SHARED / ALL-AREAS extras to pad toward 300 ──
    all_a = list(sleep)  # will expand
    for area in ["sleep", "diet", "exercise", "mental_health", "relationships", "environment", "protect"]:
        for n in range(4):
            def gen_shared(n=n, area=area):
                img = new_canvas()
                star(img, 7, 7, [P["green"], P["yellow"], P["blue"], P["pink"]][n % 4])
                if n % 2:
                    circle(img, 7, 7, 6, [P["green"], P["yellow"], P["blue"], P["pink"]][n % 4], fill=False)
                return img
            add(f"shared_{area}_{n}", f"Mark {n+1}", [area], gen_shared, rare=(n == 3))

    return STICKERS


def main():
    items = build_catalog()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = []
    for item in items:
        gen = item["gen"]
        try:
            img = gen()
        except Exception as e:
            print(f"FAIL {item['id']}: {e}")
            img = new_canvas()
            face(img, "neutral")
        path = OUT_DIR / item["file"]
        save_scaled(img, path)
        catalog.append({
            "id": item["id"],
            "label": item["label"],
            "areas": item["areas"],
            "rare": item["rare"],
            "file": item["file"],
            "src": f"/stickers/pixel/{item['file']}",
            "size": SIZE,
        })
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump({"size": SIZE, "count": len(catalog), "stickers": catalog}, f, indent=2)
    print(f"Wrote {len(catalog)} stickers to {OUT_DIR} ({SIZE}×{SIZE} PNG)")
    print(f"Catalog: {CATALOG}")
    rares = sum(1 for c in catalog if c["rare"])
    print(f"Rare: {rares}, Common: {len(catalog) - rares}")


if __name__ == "__main__":
    main()
