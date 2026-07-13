#!/usr/bin/env python3
"""
Generate a third sticker style: funny NES/SNES-inspired cartoon icons.

Original artwork in a classic 8/16-bit limited palette — not Nintendo assets.
Uses the same sticker IDs as stickers/pixel/catalog.json so the client can
swap display style without rewriting stored board entries (px:<id>).

Run:
  python3 scripts/generate_cartoon_stickers.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PIXEL_CATALOG = ROOT / "stickers" / "pixel" / "catalog.json"
OUT_DIR = ROOT / "stickers" / "cartoon"
CATALOG = OUT_DIR / "catalog.json"

# Draw at 24×24, scale 2× → 48×48 (slightly larger than pixel set for "chunky cartoon")
ART = 24
SCALE = 2
SIZE = ART * SCALE

# NES-ish limited palette (approx. PPU-friendly colors)
C = {
    "bg": (0, 0, 0, 0),
    "ink": (20, 16, 32, 255),
    "white": (252, 252, 255, 255),
    "cream": (255, 236, 200, 255),
    "skin": (255, 204, 170, 255),
    "skin2": (232, 168, 120, 255),
    "gray": (180, 184, 196, 255),
    "dgray": (88, 92, 108, 255),
    "black": (16, 16, 24, 255),
    "red": (228, 52, 68, 255),
    "dred": (160, 24, 40, 255),
    "orange": (248, 140, 40, 255),
    "yellow": (252, 220, 48, 255),
    "gold": (236, 180, 24, 255),
    "lime": (120, 220, 64, 255),
    "green": (40, 180, 88, 255),
    "dgreen": (24, 112, 56, 255),
    "teal": (48, 200, 184, 255),
    "cyan": (72, 220, 236, 255),
    "sky": (120, 200, 252, 255),
    "blue": (64, 120, 236, 255),
    "dblue": (32, 64, 180, 255),
    "navy": (24, 40, 96, 255),
    "purple": (160, 96, 236, 255),
    "violet": (112, 48, 188, 255),
    "pink": (252, 140, 196, 255),
    "rose": (244, 96, 140, 255),
    "brown": (176, 112, 56, 255),
    "dbrown": (112, 64, 32, 255),
}


def new_img():
    return Image.new("RGBA", (ART, ART), C["bg"])


def px(img, x, y, c):
    if 0 <= x < ART and 0 <= y < ART:
        img.putpixel((x, y), c)


def rect(img, x, y, w, h, c):
    for j in range(y, y + h):
        for i in range(x, x + w):
            px(img, i, j, c)


def circ(img, cx, cy, r, c, fill=True):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if fill and d2 <= r * r + r // 2:
                px(img, x, y, c)
            elif not fill and abs(d2 - r * r) <= max(2, r // 2):
                px(img, x, y, c)


def outline_rect(img, x, y, w, h, c):
    for i in range(x, x + w):
        px(img, i, y, c)
        px(img, i, y + h - 1, c)
    for j in range(y, y + h):
        px(img, x, j, c)
        px(img, x + w - 1, j, c)


def save(img, path: Path):
    big = img.resize((SIZE, SIZE), Image.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    big.save(path, "PNG")


# ── Funny cartoon characters (8-bit mascot vibes) ──────────────────────────

def chibi_face(img, mood="happy", cx=12, cy=11, r=7, skin=None):
    skin = skin or C["skin"]
    circ(img, cx, cy, r, skin)
    circ(img, cx, cy, r, C["ink"], fill=False)
    # big cartoony eyes
    if mood == "happy":
        circ(img, cx - 3, cy - 1, 1, C["ink"])
        circ(img, cx + 3, cy - 1, 1, C["ink"])
        px(img, cx - 3, cy - 2, C["white"])
        px(img, cx + 3, cy - 2, C["white"])
        # grin
        for x in range(cx - 3, cx + 4):
            px(img, x, cy + 3, C["ink"])
        px(img, cx - 3, cy + 2, C["ink"])
        px(img, cx + 3, cy + 2, C["ink"])
    elif mood == "sad":
        circ(img, cx - 3, cy - 1, 1, C["ink"])
        circ(img, cx + 3, cy - 1, 1, C["ink"])
        for x in range(cx - 3, cx + 4):
            px(img, x, cy + 4, C["ink"])
        px(img, cx - 3, cy + 3, C["ink"])
        px(img, cx + 3, cy + 3, C["ink"])
        # tear
        px(img, cx + 5, cy + 1, C["sky"])
        px(img, cx + 5, cy + 2, C["blue"])
    elif mood == "tired":
        for x in range(cx - 4, cx - 1):
            px(img, x, cy - 1, C["ink"])
        for x in range(cx + 2, cx + 5):
            px(img, x, cy - 1, C["ink"])
        for x in range(cx - 2, cx + 3):
            px(img, x, cy + 3, C["dgray"])
    elif mood == "wow":
        circ(img, cx - 3, cy - 1, 2, C["white"])
        circ(img, cx + 3, cy - 1, 2, C["white"])
        circ(img, cx - 3, cy - 1, 1, C["ink"])
        circ(img, cx + 3, cy - 1, 1, C["ink"])
        circ(img, cx, cy + 3, 2, C["ink"], fill=False)
    elif mood == "angry":
        circ(img, cx - 3, cy, 1, C["ink"])
        circ(img, cx + 3, cy, 1, C["ink"])
        # brows
        px(img, cx - 4, cy - 3, C["ink"])
        px(img, cx - 3, cy - 2, C["ink"])
        px(img, cx + 4, cy - 3, C["ink"])
        px(img, cx + 3, cy - 2, C["ink"])
        for x in range(cx - 2, cx + 3):
            px(img, x, cy + 3, C["ink"])
    elif mood == "sick":
        circ(img, cx, cy, r, C["lime"])
        circ(img, cx, cy, r, C["ink"], fill=False)
        circ(img, cx - 3, cy - 1, 1, C["ink"])
        circ(img, cx + 3, cy - 1, 1, C["ink"])
        for x in range(cx - 2, cx + 3):
            px(img, x, cy + 3, C["dgreen"])
    else:  # neutral
        circ(img, cx - 3, cy - 1, 1, C["ink"])
        circ(img, cx + 3, cy - 1, 1, C["ink"])
        for x in range(cx - 2, cx + 3):
            px(img, x, cy + 3, C["ink"])
    # blush
    if mood in ("happy", "wow"):
        px(img, cx - 5, cy + 1, C["pink"])
        px(img, cx + 5, cy + 1, C["pink"])


def draw_moon(img, cx=14, cy=8, r=6):
    circ(img, cx, cy, r, C["yellow"])
    circ(img, cx + 3, cy - 2, r - 1, C["bg"])
    circ(img, cx, cy, r, C["ink"], fill=False)


def draw_star(img, cx, cy, c=None):
    c = c or C["yellow"]
    for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (0, -2), (0, 2)]:
        px(img, cx + dx, cy + dy, c)
    px(img, cx - 1, cy - 1, c)
    px(img, cx + 1, cy - 1, c)
    px(img, cx - 1, cy + 1, c)
    px(img, cx + 1, cy + 1, c)


def draw_heart(img, cx=12, cy=12, c=None):
    c = c or C["red"]
    px(img, cx - 2, cy - 1, c)
    px(img, cx + 1, cy - 1, c)
    rect(img, cx - 3, cy, 6, 2, c)
    rect(img, cx - 2, cy + 2, 4, 1, c)
    px(img, cx - 1, cy + 3, c)
    px(img, cx, cy + 3, c)
    px(img, cx - 1, cy + 4, c)


def draw_zzz(img):
    for i, (x, y, s) in enumerate([(14, 3, 3), (11, 7, 2), (8, 10, 2)]):
        col = C["purple"] if i == 0 else C["violet"]
        for dx in range(s):
            px(img, x + dx, y, col)
            px(img, x + s - 1 - dx, y + 1, col)
            px(img, x + dx, y + 2, col)


def draw_shield(img):
    rect(img, 7, 5, 10, 9, C["blue"])
    outline_rect(img, 7, 5, 10, 9, C["ink"])
    for i in range(5):
        for x in range(8 + i, 16 - i):
            px(img, x, 14 + i, C["dblue"])
    draw_star(img, 12, 9, C["yellow"])


def draw_dumbbell(img):
    rect(img, 3, 9, 4, 6, C["dgray"])
    rect(img, 17, 9, 4, 6, C["dgray"])
    rect(img, 7, 11, 10, 2, C["gray"])
    outline_rect(img, 3, 9, 4, 6, C["ink"])
    outline_rect(img, 17, 9, 4, 6, C["ink"])


def draw_pizza(img):
    # slice triangle-ish
    for y in range(6, 20):
        w = (y - 5) // 2
        for x in range(12 - w, 12 + w + 1):
            px(img, x, y, C["yellow"])
    for y in range(6, 20):
        w = (y - 5) // 2
        px(img, 12 - w, y, C["orange"])
        px(img, 12 + w, y, C["orange"])
    # pepperoni
    circ(img, 10, 12, 1, C["red"])
    circ(img, 14, 14, 1, C["red"])
    circ(img, 11, 16, 1, C["red"])


def draw_apple(img):
    circ(img, 12, 14, 6, C["red"])
    circ(img, 12, 14, 6, C["ink"], fill=False)
    px(img, 12, 6, C["dbrown"])
    px(img, 12, 5, C["dbrown"])
    px(img, 13, 4, C["green"])
    px(img, 14, 5, C["lime"])
    px(img, 9, 12, C["white"])


def draw_trophy(img):
    rect(img, 8, 6, 8, 6, C["gold"])
    rect(img, 10, 12, 4, 3, C["gold"])
    rect(img, 7, 16, 10, 3, C["gold"])
    outline_rect(img, 8, 6, 8, 6, C["ink"])
    px(img, 6, 8, C["gold"])
    px(img, 17, 8, C["gold"])
    draw_star(img, 12, 9, C["yellow"])


def draw_lightning(img):
    pts = [
        (14, 2), (10, 2), (8, 10), (11, 10), (7, 21), (16, 9), (13, 9), (17, 2)
    ]
    # simple bolt via rects
    rect(img, 11, 2, 4, 7, C["yellow"])
    rect(img, 7, 8, 8, 3, C["yellow"])
    rect(img, 8, 11, 4, 8, C["gold"])
    for x, y in [(10, 3), (12, 12), (9, 16)]:
        px(img, x, y, C["white"])


def draw_sun(img):
    circ(img, 12, 12, 5, C["yellow"])
    circ(img, 12, 12, 5, C["ink"], fill=False)
    for a in range(8):
        import math
        ang = a * math.pi / 4
        x = int(12 + 9 * math.cos(ang))
        y = int(12 + 9 * math.sin(ang))
        px(img, x, y, C["gold"])
        px(img, int(12 + 8 * math.cos(ang)), int(12 + 8 * math.sin(ang)), C["orange"])


def draw_cloud(img, y=6):
    circ(img, 8, y + 3, 4, C["white"])
    circ(img, 14, y + 3, 4, C["white"])
    circ(img, 11, y + 1, 4, C["white"])
    rect(img, 6, y + 3, 12, 4, C["white"])


def draw_rain(img):
    draw_cloud(img, 4)
    for x, y in [(7, 14), (11, 16), (15, 14), (9, 18), (13, 19)]:
        px(img, x, y, C["blue"])
        px(img, x, y + 1, C["sky"])


def draw_fire(img):
    rect(img, 8, 12, 8, 8, C["orange"])
    rect(img, 10, 7, 5, 7, C["yellow"])
    px(img, 12, 4, C["yellow"])
    px(img, 11, 5, C["orange"])
    px(img, 13, 6, C["red"])
    px(img, 9, 16, C["red"])
    px(img, 14, 17, C["dred"])


def draw_drop(img):
    for y in range(4, 10):
        w = (y - 3) // 2
        for x in range(12 - w, 12 + w + 1):
            px(img, x, y, C["sky"])
    circ(img, 12, 14, 5, C["blue"])
    circ(img, 12, 14, 5, C["ink"], fill=False)
    px(img, 10, 13, C["cyan"])


def draw_pill(img):
    rect(img, 5, 10, 7, 5, C["rose"])
    rect(img, 12, 10, 7, 5, C["white"])
    outline_rect(img, 5, 10, 14, 5, C["ink"])
    px(img, 12, 10, C["ink"])
    px(img, 12, 14, C["ink"])


def draw_house(img):
    rect(img, 6, 12, 12, 9, C["brown"])
    outline_rect(img, 6, 12, 12, 9, C["ink"])
    for i in range(7):
        for x in range(12 - i, 12 + i + 1):
            px(img, x, 11 - i, C["red"])
    rect(img, 10, 16, 4, 5, C["dbrown"])
    px(img, 8, 14, C["yellow"])
    px(img, 15, 14, C["yellow"])


def draw_tree(img):
    rect(img, 11, 14, 3, 8, C["dbrown"])
    circ(img, 12, 11, 6, C["green"])
    circ(img, 12, 9, 4, C["lime"])
    circ(img, 12, 11, 6, C["ink"], fill=False)


def draw_bike(img):
    circ(img, 7, 16, 4, C["ink"], fill=False)
    circ(img, 17, 16, 4, C["ink"], fill=False)
    circ(img, 7, 16, 1, C["dgray"])
    circ(img, 17, 16, 1, C["dgray"])
    for x in range(7, 18):
        px(img, x, 12, C["red"])
    px(img, 12, 9, C["red"])
    px(img, 12, 10, C["red"])
    px(img, 12, 11, C["gray"])


def draw_owl(img):
    circ(img, 12, 12, 7, C["brown"])
    circ(img, 12, 12, 7, C["ink"], fill=False)
    circ(img, 9, 11, 3, C["cream"])
    circ(img, 15, 11, 3, C["cream"])
    circ(img, 9, 11, 1, C["ink"])
    circ(img, 15, 11, 1, C["ink"])
    px(img, 12, 14, C["orange"])
    px(img, 11, 15, C["orange"])
    px(img, 13, 15, C["orange"])
    # ear tufts
    px(img, 6, 6, C["dbrown"])
    px(img, 18, 6, C["dbrown"])


def draw_sheep(img):
    circ(img, 12, 13, 6, C["white"])
    circ(img, 12, 13, 6, C["ink"], fill=False)
    circ(img, 12, 10, 3, C["cream"])
    circ(img, 11, 10, 1, C["ink"])
    circ(img, 13, 10, 1, C["ink"])
    # fluff bumps
    for cx, cy in [(7, 12), (17, 12), (9, 8), (15, 8)]:
        circ(img, cx, cy, 2, C["white"])


def draw_ufo(img):
    circ(img, 12, 10, 4, C["cyan"])
    rect(img, 5, 11, 14, 3, C["gray"])
    outline_rect(img, 5, 11, 14, 3, C["ink"])
    for x in (7, 10, 13, 16):
        px(img, x, 12, C["yellow"])
    # beam
    for y in range(15, 22):
        w = (y - 14) // 2
        for x in range(12 - w, 12 + w + 1):
            px(img, x, y, C["lime"] if y % 2 == 0 else C["yellow"])


def draw_bed(img):
    rect(img, 3, 14, 18, 5, C["dblue"])
    rect(img, 4, 11, 10, 4, C["cream"])
    rect(img, 14, 10, 6, 5, C["pink"])
    outline_rect(img, 3, 14, 18, 5, C["ink"])
    chibi_face(img, "tired", cx=17, cy=8, r=4)


def draw_alarm(img):
    circ(img, 12, 13, 7, C["red"])
    circ(img, 12, 13, 7, C["ink"], fill=False)
    circ(img, 12, 13, 5, C["white"])
    # hands
    px(img, 12, 13, C["ink"])
    for y in range(9, 13):
        px(img, 12, y, C["ink"])
    for x in range(12, 16):
        px(img, x, 13, C["dred"])
    # bells
    circ(img, 7, 7, 2, C["gold"])
    circ(img, 17, 7, 2, C["gold"])
    # angry face on clock
    px(img, 10, 11, C["ink"])
    px(img, 14, 11, C["ink"])


def draw_mug(img):
    rect(img, 7, 8, 10, 11, C["cream"])
    outline_rect(img, 7, 8, 10, 11, C["ink"])
    rect(img, 8, 9, 8, 3, C["brown"])
    # handle
    for y in range(11, 17):
        px(img, 17, y, C["ink"])
        px(img, 18, y, C["ink"])
    # steam
    for x, y in [(9, 5), (12, 4), (15, 5)]:
        px(img, x, y, C["gray"])
        px(img, x + 1, y - 1, C["gray"])


def draw_book(img):
    rect(img, 5, 5, 14, 15, C["dblue"])
    outline_rect(img, 5, 5, 14, 15, C["ink"])
    rect(img, 6, 6, 12, 13, C["cream"])
    for y in (10, 13, 16):
        for x in range(8, 16):
            px(img, x, y, C["gray"])
    # sleepy Z on cover
    px(img, 14, 7, C["purple"])


def draw_salad(img):
    circ(img, 12, 14, 7, C["green"])
    circ(img, 12, 14, 7, C["ink"], fill=False)
    circ(img, 10, 12, 2, C["lime"])
    circ(img, 14, 13, 2, C["red"])
    circ(img, 12, 16, 2, C["orange"])
    px(img, 9, 15, C["yellow"])


def draw_chef(img):
    chibi_face(img, "happy", cx=12, cy=14, r=6)
    # hat
    rect(img, 7, 4, 10, 5, C["white"])
    circ(img, 9, 4, 3, C["white"])
    circ(img, 15, 4, 3, C["white"])
    circ(img, 12, 3, 3, C["white"])
    outline_rect(img, 7, 6, 10, 3, C["ink"])


def draw_runner(img):
    # stick-figure athlete with motion lines
    chibi_face(img, "wow", cx=10, cy=7, r=4)
    rect(img, 9, 11, 3, 5, C["blue"])
    # legs running
    px(img, 8, 17, C["skin"])
    px(img, 7, 18, C["skin"])
    px(img, 12, 17, C["skin"])
    px(img, 14, 18, C["skin"])
    # motion
    for x in (16, 18, 20):
        px(img, x, 12, C["yellow"])


def draw_couch(img):
    rect(img, 3, 12, 18, 7, C["purple"])
    outline_rect(img, 3, 12, 18, 7, C["ink"])
    rect(img, 3, 10, 4, 4, C["violet"])
    rect(img, 17, 10, 4, 4, C["violet"])
    chibi_face(img, "tired", cx=12, cy=9, r=4)


def draw_butterfly(img):
    circ(img, 8, 10, 4, C["pink"])
    circ(img, 16, 10, 4, C["purple"])
    circ(img, 8, 15, 3, C["violet"])
    circ(img, 16, 15, 3, C["rose"])
    rect(img, 11, 9, 2, 10, C["ink"])
    px(img, 12, 7, C["ink"])


def draw_rainbow(img):
    colors = [C["red"], C["orange"], C["yellow"], C["green"], C["blue"], C["purple"]]
    for i, col in enumerate(colors):
        for x in range(3, 21):
            # arch
            y = 16 - int((1 - ((x - 12) / 10) ** 2) * (10 - i))
            if 4 <= y < 20:
                px(img, x, y, col)
                px(img, x, y + 1, col)


def draw_phone(img):
    rect(img, 8, 4, 8, 16, C["dgray"])
    outline_rect(img, 8, 4, 8, 16, C["ink"])
    rect(img, 9, 6, 6, 10, C["sky"])
    circ(img, 12, 18, 1, C["gray"])
    # heart on screen
    draw_heart(img, 12, 10, C["red"])


def draw_germ(img):
    circ(img, 12, 12, 6, C["lime"])
    circ(img, 12, 12, 6, C["ink"], fill=False)
    for ang in range(8):
        import math
        x = int(12 + 8 * math.cos(ang * 0.785))
        y = int(12 + 8 * math.sin(ang * 0.785))
        px(img, x, y, C["green"])
    circ(img, 10, 11, 1, C["ink"])
    circ(img, 14, 11, 1, C["ink"])
    for x in range(10, 15):
        px(img, x, 15, C["dgreen"])


def draw_generic_by_seed(img, seed: str, area: str):
    """Procedural funny variant for numbered face_/food_/etc stickers."""
    rng = random.Random(seed)
    moods = ["happy", "sad", "tired", "wow", "angry", "neutral", "sick"]
    mood = moods[rng.randint(0, len(moods) - 1)]
    skins = [C["skin"], C["cream"], C["pink"], C["yellow"], C["sky"]]
    skin = skins[rng.randint(0, len(skins) - 1)]

    if "face" in seed or "mind" in seed:
        chibi_face(img, mood, skin=skin)
        if rng.random() < 0.4:
            draw_star(img, rng.randint(2, 5), rng.randint(2, 5), C["yellow"])
        if rng.random() < 0.3:
            draw_zzz(img)
    elif "food" in seed or area == "diet":
        choice = rng.randint(0, 4)
        if choice == 0:
            draw_apple(img)
        elif choice == 1:
            draw_pizza(img)
        elif choice == 2:
            draw_salad(img)
        elif choice == 3:
            draw_mug(img)
        else:
            chibi_face(img, "happy", skin=C["cream"])
            # chef hat mini
            rect(img, 8, 3, 8, 3, C["white"])
    elif "move" in seed or area == "exercise":
        if rng.random() < 0.5:
            draw_runner(img)
        else:
            draw_dumbbell(img)
            if rng.random() < 0.5:
                chibi_face(img, "wow", cx=12, cy=6, r=4)
    elif "social" in seed or area == "relationships":
        draw_heart(img, 8, 10, C["red"])
        draw_heart(img, 16, 12, C["pink"])
        chibi_face(img, "happy", cx=12, cy=16, r=5)
    elif "place" in seed or area == "environment":
        if rng.random() < 0.5:
            draw_tree(img)
        else:
            draw_house(img)
        if rng.random() < 0.4:
            draw_sun(img)
    elif "care" in seed or area == "protect":
        if rng.random() < 0.4:
            draw_shield(img)
        elif rng.random() < 0.5:
            draw_pill(img)
        else:
            draw_germ(img)
    elif "moon" in seed or area == "sleep":
        draw_moon(img)
        if rng.random() < 0.5:
            draw_zzz(img)
        if rng.random() < 0.3:
            chibi_face(img, "tired", cx=8, cy=16, r=4)
    else:
        chibi_face(img, mood, skin=skin)


def draw_leafish(img):
    rect(img, 11, 8, 2, 8, C["dgreen"])
    circ(img, 10, 10, 3, C["green"])
    circ(img, 14, 12, 3, C["lime"])


# Map known sticker ids → drawer functions
DRAWERS = {
    "sleep_great": lambda i: (chibi_face(i, "happy"), draw_zzz(i), draw_moon(i)),
    "sleep_rough": lambda i: (chibi_face(i, "sad"), draw_zzz(i)),
    "sleep_ok": lambda i: chibi_face(i, "neutral"),
    "sleep_good": lambda i: (chibi_face(i, "happy"), draw_moon(i)),
    "sleep_rested": lambda i: (chibi_face(i, "happy"), draw_star(i, 4, 4)),
    "sleep_dozy": lambda i: chibi_face(i, "tired"),
    "sleep_zzz": lambda i: (draw_zzz(i), draw_moon(i)),
    "sleep_moon": lambda i: draw_moon(i),
    "sleep_bed": lambda i: draw_bed(i),
    "sleep_alarm": lambda i: draw_alarm(i),
    "sleep_early": lambda i: (draw_sun(i), chibi_face(i, "tired", cx=12, cy=16, r=4)),
    "sleep_late": lambda i: (draw_moon(i), chibi_face(i, "wow", cx=12, cy=16, r=4)),
    "sleep_broken": lambda i: (chibi_face(i, "sad"), draw_moon(i)),
    "sleep_in": lambda i: draw_bed(i),
    "sleep_owl": lambda i: draw_owl(i),
    "sleep_sheep": lambda i: draw_sheep(i),
    "sleep_ufo": lambda i: draw_ufo(i),
    "sleep_stars": lambda i: (draw_star(i, 6, 6), draw_star(i, 16, 8, C["gold"]), draw_star(i, 12, 16, C["yellow"])),
    "sleep_mug": lambda i: draw_mug(i),
    "sleep_book": lambda i: draw_book(i),
    "diet_clean": lambda i: draw_salad(i),
    "diet_struggle": lambda i: (chibi_face(i, "sad"), draw_pizza(i)),
    "diet_enjoy": lambda i: (chibi_face(i, "happy"), draw_pizza(i)),
    "diet_onpoint": lambda i: (chibi_face(i, "wow"), draw_salad(i)),
    "diet_apple": lambda i: draw_apple(i),
    "diet_veg": lambda i: draw_salad(i),
    "diet_water": lambda i: draw_drop(i),
    "diet_pizza": lambda i: draw_pizza(i),
    "diet_sweet": lambda i: (circ(i, 12, 14, 6, C["pink"]), circ(i, 12, 14, 6, C["ink"], fill=False), circ(i, 12, 12, 2, C["white"]), draw_star(i, 18, 6, C["yellow"])),
    "diet_comfort": lambda i: draw_mug(i),
    "diet_chef": lambda i: draw_chef(i),
    "diet_avo": lambda i: (circ(i, 12, 13, 7, C["green"]), circ(i, 12, 13, 7, C["ink"], fill=False), circ(i, 12, 13, 3, C["dbrown"]), circ(i, 12, 13, 3, C["ink"], fill=False)),
    "diet_grape": lambda i: (circ(i, 10, 10, 3, C["purple"]), circ(i, 14, 10, 3, C["violet"]), circ(i, 12, 14, 3, C["purple"]), px(i, 12, 6, C["dgreen"])),
    "diet_feast": lambda i: (draw_pizza(i), draw_star(i, 4, 4, C["gold"]), draw_star(i, 20, 5, C["yellow"])),
    "diet_salad2": lambda i: draw_salad(i),
    "ex_crush": lambda i: (draw_dumbbell(i), chibi_face(i, "wow", cx=12, cy=5, r=4)),
    "ex_skip": lambda i: draw_couch(i),
    "ex_active": lambda i: draw_runner(i),
    "ex_walk": lambda i: draw_runner(i),
    "ex_stretch": lambda i: (chibi_face(i, "happy"), rect(i, 10, 16, 4, 6, C["blue"])),
    "ex_bike": lambda i: draw_bike(i),
    "ex_lift": lambda i: draw_dumbbell(i),
    "ex_sweat": lambda i: (chibi_face(i, "wow"), px(i, 6, 8, C["sky"]), px(i, 18, 9, C["sky"]), px(i, 5, 12, C["blue"])),
    "ex_pr": lambda i: draw_trophy(i),
    "ex_champ": lambda i: (draw_trophy(i), draw_star(i, 4, 4)),
    "ex_beast": lambda i: (chibi_face(i, "angry", skin=C["orange"]), draw_lightning(i)),
    "ex_electric": lambda i: draw_lightning(i),
    "mh_calm": lambda i: (chibi_face(i, "happy"), draw_cloud(i)),
    "mh_good": lambda i: chibi_face(i, "happy"),
    "mh_mixed": lambda i: chibi_face(i, "neutral"),
    "mh_focus": lambda i: (chibi_face(i, "neutral"), draw_star(i, 18, 5, C["cyan"])),
    "mh_light": lambda i: (chibi_face(i, "happy"), draw_star(i, 5, 5), draw_star(i, 19, 6, C["yellow"])),
    "mh_stress": lambda i: (chibi_face(i, "angry"), draw_lightning(i)),
    "mh_cloudy": lambda i: (draw_cloud(i), chibi_face(i, "sad", cx=12, cy=16, r=4)),
    "mh_burnout": lambda i: (draw_fire(i), chibi_face(i, "sad", cx=12, cy=18, r=3)),
    "mh_fog": lambda i: (draw_cloud(i, 8), draw_cloud(i, 12)),
    "mh_struggle": lambda i: chibi_face(i, "sad"),
    "mh_hope": lambda i: draw_rainbow(i),
    "mh_inspired": lambda i: (chibi_face(i, "wow"), draw_star(i, 4, 4), draw_star(i, 19, 5, C["gold"])),
    "mh_transform": lambda i: draw_butterfly(i),
    "mh_center": lambda i: (circ(i, 12, 12, 8, C["violet"]), circ(i, 12, 12, 5, C["purple"]), circ(i, 12, 12, 2, C["yellow"])),
    "rel_connect": lambda i: (draw_heart(i, 8, 10), draw_heart(i, 16, 12, C["pink"]), chibi_face(i, "happy", cx=12, cy=18, r=4)),
    "rel_distant": lambda i: chibi_face(i, "sad"),
    "rel_loved": lambda i: (draw_heart(i, 12, 10, C["red"]), draw_heart(i, 12, 16, C["rose"])),
    "rel_grateful": lambda i: (chibi_face(i, "happy"), draw_star(i, 4, 4, C["gold"])),
    "rel_support": lambda i: (draw_heart(i, 12, 12), chibi_face(i, "happy", cx=12, cy=6, r=4)),
    "rel_reach": lambda i: draw_phone(i),
    "rel_talk": lambda i: (chibi_face(i, "happy", cx=8, cy=12, r=5), chibi_face(i, "happy", cx=16, cy=12, r=5)),
    "rel_social": lambda i: (chibi_face(i, "happy", cx=7, cy=12, r=4), chibi_face(i, "wow", cx=15, cy=12, r=4), chibi_face(i, "happy", cx=12, cy=18, r=3)),
    "rel_quiet": lambda i: chibi_face(i, "neutral"),
    "rel_bond": lambda i: (draw_heart(i, 9, 12), draw_heart(i, 15, 12, C["pink"])),
    "rel_cherish": lambda i: (draw_heart(i, 12, 11, C["rose"]), draw_star(i, 5, 5, C["yellow"])),
    "rel_peace": lambda i: (circ(i, 12, 12, 7, C["cream"]), circ(i, 12, 12, 7, C["ink"], fill=False), draw_leafish(i)),
    "rel_celeb": lambda i: (draw_star(i, 6, 6), draw_star(i, 18, 8, C["gold"]), chibi_face(i, "wow", cx=12, cy=14, r=5)),
    "rel_good": lambda i: chibi_face(i, "happy"),
    "env_fresh": lambda i: (draw_tree(i), draw_sun(i)),
    "env_heavy": lambda i: draw_rain(i),
    "env_bright": lambda i: draw_sun(i),
    "env_cozy": lambda i: draw_house(i),
    "env_tidy": lambda i: (draw_house(i), draw_star(i, 4, 4, C["lime"])),
    "env_outdoors": lambda i: (draw_tree(i), draw_sun(i)),
    "env_clean": lambda i: (draw_drop(i), draw_star(i, 18, 5, C["cyan"])),
    "env_air": lambda i: (draw_cloud(i), draw_star(i, 18, 16, C["sky"])),
    "env_busy": lambda i: (draw_house(i), draw_lightning(i)),
    "env_nature": lambda i: draw_tree(i),
    "env_golden": lambda i: (draw_sun(i), rect(i, 2, 18, 20, 3, C["gold"])),
    "env_water": lambda i: (draw_drop(i), circ(i, 12, 18, 3, C["blue"])),
    "env_wild": lambda i: (draw_tree(i), chibi_face(i, "wow", cx=18, cy=16, r=3, skin=C["yellow"])),
    "env_clutter": lambda i: (draw_house(i), chibi_face(i, "angry", cx=18, cy=8, r=3)),
    "pr_ontop": lambda i: draw_shield(i),
    "pr_notgreat": lambda i: chibi_face(i, "sick"),
    "pr_manage": lambda i: draw_pill(i),
    "pr_sun": lambda i: (draw_sun(i), draw_shield(i)),
    "pr_hygiene": lambda i: (draw_drop(i), circ(i, 12, 18, 2, C["white"])),
    "pr_check": lambda i: (rect(i, 8, 6, 8, 14, C["white"]), outline_rect(i, 8, 6, 8, 14, C["ink"]), circ(i, 12, 10, 2, C["red"]), rect(i, 10, 14, 4, 4, C["red"])),
    "pr_careful": lambda i: (chibi_face(i, "neutral"), rect(i, 7, 14, 10, 4, C["sky"])),
    "pr_bullet": lambda i: (draw_shield(i), draw_star(i, 12, 9, C["yellow"])),
    "pr_boost": lambda i: draw_mug(i),
    "pr_picture": lambda i: (chibi_face(i, "happy"), draw_star(i, 4, 4, C["gold"]), draw_star(i, 19, 5, C["yellow"])),
    "pr_opt": lambda i: (chibi_face(i, "wow"), draw_lightning(i)),
    "pr_strong": lambda i: (chibi_face(i, "wow"), draw_dumbbell(i)),
    "pr_natural": lambda i: (draw_tree(i), draw_leafish(i)),
    "pr_rest": lambda i: draw_bed(i),
    "pr_cross": lambda i: (rect(i, 10, 5, 4, 14, C["red"]), rect(i, 5, 10, 14, 4, C["red"]), outline_rect(i, 10, 5, 4, 14, C["ink"])),
    "pr_germ": lambda i: draw_germ(i),
    "pr_pill": lambda i: draw_pill(i),
}


def generate_one(sid: str, areas: list) -> Image.Image:
    img = new_img()
    drawer = DRAWERS.get(sid)
    if drawer:
        try:
            drawer(img)
        except Exception:
            chibi_face(img, "happy")
        return img
    area = areas[0] if areas else "sleep"
    draw_generic_by_seed(img, sid, area)
    return img


def main():
    if not PIXEL_CATALOG.exists():
        raise SystemExit(f"Missing pixel catalog: {PIXEL_CATALOG}")
    data = json.loads(PIXEL_CATALOG.read_text())
    stickers = data.get("stickers") or []
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    out_entries = []
    for s in stickers:
        sid = s["id"]
        areas = s.get("areas") or []
        img = generate_one(sid, areas)
        fname = f"{sid}.png"
        save(img, OUT_DIR / fname)
        out_entries.append({
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
        "count": len(out_entries),
        "style": "cartoon",
        "description": "Funny NES/SNES-inspired original cartoon stickers (not Nintendo assets)",
        "stickers": out_entries,
    }
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n")
    print(f"\nWrote {len(out_entries)} stickers → {OUT_DIR}")
    print(f"Catalog → {CATALOG}")


if __name__ == "__main__":
    main()
