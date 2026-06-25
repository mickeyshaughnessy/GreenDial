#!/usr/bin/env python3
"""Generate GreenDial PWA app icons (brand-dark square + green leaf).

Run once to (re)create files under icons/. Pillow only — no system deps.
"""
import os
from PIL import Image, ImageDraw, ImageChops

BG = (26, 26, 46)        # #1a1a2e  app background
GREEN = (16, 185, 129)   # #10b981  brand green
MIDRIB = (8, 120, 84)    # darker green vein
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def leaf_layer(size, scale):
    """Return an RGBA leaf glyph centered on a transparent `size` square."""
    SS = size * 4  # supersample for smooth edges
    # Vesica-piscis lens = intersection of two offset circles -> pointed leaf
    R = int(SS * 0.42 * scale)
    offset = int(R * 0.55)
    cx = cy = SS // 2
    a = Image.new("L", (SS, SS), 0)
    b = Image.new("L", (SS, SS), 0)
    ImageDraw.Draw(a).ellipse([cx - offset - R, cy - R, cx - offset + R, cy + R], fill=255)
    ImageDraw.Draw(b).ellipse([cx + offset - R, cy - R, cx + offset + R, cy + R], fill=255)
    lens = ImageChops.darker(a, b)  # vertical pointed lens

    leaf = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    fill = Image.new("RGBA", (SS, SS), GREEN + (255,))
    leaf.paste(fill, (0, 0), lens)

    # Midrib vein down the centre
    d = ImageDraw.Draw(leaf)
    top = cy - int(R * 0.82)
    bot = cy + int(R * 0.82)
    d.line([(cx, top), (cx, bot)], fill=MIDRIB + (255,), width=max(2, SS // 90))

    leaf = leaf.rotate(38, resample=Image.BICUBIC, center=(cx, cy))
    return leaf.resize((size, size), Image.LANCZOS)


def make_icon(size, scale=0.62, rounded=False):
    img = Image.new("RGBA", (size, size), BG + (255,))
    if rounded:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=int(size * 0.22), fill=255)
        img.putalpha(mask)
    img.alpha_composite(leaf_layer(size, scale))
    return img


def main():
    os.makedirs(ICON_DIR, exist_ok=True)
    make_icon(192).save(os.path.join(ICON_DIR, "icon-192.png"))
    make_icon(512).save(os.path.join(ICON_DIR, "icon-512.png"))
    # Maskable: leaf inside the ~80% safe zone so launcher masks don't clip it
    make_icon(512, scale=0.46).save(os.path.join(ICON_DIR, "icon-512-maskable.png"))
    print("Wrote icons to", ICON_DIR)


if __name__ == "__main__":
    main()
