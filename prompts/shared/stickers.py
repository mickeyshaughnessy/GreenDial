"""
Sticker Board definitions: areas, pixel-art sticker library, poll templates.

Custom pixel stickers live in /stickers/pixel/ (32×32 PNG, image-rendering:
pixelated). Stored values use ``px:<id>`` so the UI can render an <img>;
legacy unicode emoji values still render as text.
"""
from __future__ import annotations

import hashlib
import json
import os
import random

STICKER_AREAS = ["sleep", "diet", "exercise", "mental_health", "relationships", "environment", "protect"]

AREA_LABELS = {
    "sleep": "Sleep",
    "diet": "Diet",
    "exercise": "Exercise",
    "mental_health": "Mental Health",
    "relationships": "Relationships",
    "environment": "Environment",
    "protect": "Protect",
}

# Fallback area icons (unicode) when pixel catalog is unavailable
AREA_EMOJIS = {
    "sleep": "🌙",
    "diet": "🥗",
    "exercise": "💪",
    "mental_health": "🧠",
    "relationships": "❤️",
    "environment": "🌿",
    "protect": "🛡️",
}

PIXEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "stickers",
    "pixel",
)
PIXEL_CATALOG_PATH = os.path.join(PIXEL_DIR, "catalog.json")

_PIXEL_CATALOG = None
_PIXEL_BY_AREA = None


def _load_pixel_catalog():
    global _PIXEL_CATALOG, _PIXEL_BY_AREA
    if _PIXEL_CATALOG is not None:
        return _PIXEL_CATALOG
    _PIXEL_CATALOG = []
    _PIXEL_BY_AREA = {a: {"common": [], "rare": []} for a in STICKER_AREAS}
    try:
        with open(PIXEL_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for s in data.get("stickers") or []:
            entry = {
                "id": s["id"],
                "emoji": f"px:{s['id']}",  # board storage token
                "src": s.get("src") or f"/stickers/pixel/{s['file']}",
                "label": s.get("label") or s["id"],
                "rare": bool(s.get("rare")),
                "areas": s.get("areas") or [],
            }
            _PIXEL_CATALOG.append(entry)
            for area in entry["areas"]:
                if area not in _PIXEL_BY_AREA:
                    continue
                bucket = "rare" if entry["rare"] else "common"
                _PIXEL_BY_AREA[area][bucket].append(entry)
    except Exception as e:
        print(f"[Stickers] pixel catalog not loaded: {e}")
    return _PIXEL_CATALOG


def pixel_catalog():
    return _load_pixel_catalog()


def pixel_for_area(area):
    _load_pixel_catalog()
    return _PIXEL_BY_AREA.get(area) or {"common": [], "rare": []}


def is_pixel_token(value):
    return isinstance(value, str) and (
        value.startswith("px:") or value.startswith("/stickers/pixel/")
    )


def pixel_src(value):
    """Resolve a stored sticker value to an image URL, or None."""
    if not isinstance(value, str):
        return None
    if value.startswith("px:"):
        return f"/stickers/pixel/{value[3:]}.png"
    if value.startswith("/stickers/pixel/"):
        return value
    return None


# Legacy emoji templates (fallback if pixel library missing)
POLL_TEMPLATES = {
    "sleep": {
        "question": "How did you sleep last night?",
        "positive": {"emoji": "😴", "label": "Slept great"},
        "negative": {"emoji": "🥱", "label": "Rough night"},
        "pool": [
            {"emoji": "😊", "label": "Good"},
            {"emoji": "😌", "label": "Rested"},
            {"emoji": "😐", "label": "OK"},
            {"emoji": "💤", "label": "Dozy"},
            {"emoji": "🌗", "label": "Broken sleep"},
            {"emoji": "⏰", "label": "Woke early"},
            {"emoji": "🛌", "label": "Slept in"},
            {"emoji": "🌃", "label": "Late night"},
        ],
        "rare": [
            {"emoji": "🦉", "label": "Night owl"},
            {"emoji": "🌌", "label": "Stargazer"},
            {"emoji": "🐑", "label": "Counted sheep"},
            {"emoji": "🛸", "label": "Wild dreams"},
        ],
    },
    "diet": {
        "question": "How's your eating been today?",
        "positive": {"emoji": "🥗", "label": "Clean & healthy"},
        "negative": {"emoji": "😤", "label": "Struggled"},
        "pool": [
            {"emoji": "😋", "label": "Enjoyed it"},
            {"emoji": "💪", "label": "On point"},
            {"emoji": "🍎", "label": "Fruity"},
            {"emoji": "🥦", "label": "Veggies"},
            {"emoji": "💧", "label": "Hydrated"},
            {"emoji": "🍕", "label": "Indulgent"},
            {"emoji": "🍰", "label": "Sweet tooth"},
            {"emoji": "🍜", "label": "Comfort food"},
        ],
        "rare": [
            {"emoji": "🧑‍🍳", "label": "Chef mode"},
            {"emoji": "🥑", "label": "Avocado win"},
            {"emoji": "🍇", "label": "Superfood"},
            {"emoji": "🦞", "label": "Feast"},
        ],
    },
    "exercise": {
        "question": "How was your activity level today?",
        "positive": {"emoji": "💪", "label": "Crushed it"},
        "negative": {"emoji": "🛋️", "label": "Skipped it"},
        "pool": [
            {"emoji": "🏃", "label": "Active"},
            {"emoji": "🚶", "label": "Walked"},
            {"emoji": "🧘", "label": "Stretched"},
            {"emoji": "🚴", "label": "Cycled"},
            {"emoji": "🏋️", "label": "Lifted"},
            {"emoji": "🤸", "label": "Moved"},
            {"emoji": "😅", "label": "Sweaty"},
            {"emoji": "🧗", "label": "Pushed limits"},
        ],
        "rare": [
            {"emoji": "🏆", "label": "Personal record"},
            {"emoji": "🥇", "label": "Champion"},
            {"emoji": "🦸", "label": "Beast mode"},
            {"emoji": "⚡", "label": "Electric"},
        ],
    },
    "mental_health": {
        "question": "How are you feeling mentally today?",
        "positive": {"emoji": "😌", "label": "Calm & clear"},
        "negative": {"emoji": "😢", "label": "Struggling"},
        "pool": [
            {"emoji": "😊", "label": "Good"},
            {"emoji": "😐", "label": "Mixed"},
            {"emoji": "🧠", "label": "Focused"},
            {"emoji": "🫧", "label": "Light"},
            {"emoji": "😟", "label": "Stressed"},
            {"emoji": "🌥️", "label": "Cloudy"},
            {"emoji": "🔥", "label": "Burnt out"},
            {"emoji": "🌀", "label": "Foggy"},
        ],
        "rare": [
            {"emoji": "🌈", "label": "Hopeful"},
            {"emoji": "✨", "label": "Inspired"},
            {"emoji": "🦋", "label": "Transformed"},
            {"emoji": "🕯️", "label": "Centered"},
        ],
    },
    "relationships": {
        "question": "How connected do you feel with others today?",
        "positive": {"emoji": "🤗", "label": "Very connected"},
        "negative": {"emoji": "😞", "label": "Distant"},
        "pool": [
            {"emoji": "❤️", "label": "Loved"},
            {"emoji": "😊", "label": "Good"},
            {"emoji": "🙏", "label": "Grateful"},
            {"emoji": "🫂", "label": "Supported"},
            {"emoji": "📞", "label": "Reached out"},
            {"emoji": "💬", "label": "Good talk"},
            {"emoji": "👯", "label": "Social"},
            {"emoji": "😶", "label": "Quiet"},
        ],
        "rare": [
            {"emoji": "💞", "label": "Deep bond"},
            {"emoji": "🥰", "label": "Cherished"},
            {"emoji": "🕊️", "label": "Made peace"},
            {"emoji": "🎉", "label": "Celebrated"},
        ],
    },
    "environment": {
        "question": "How's your environment been today?",
        "positive": {"emoji": "🌿", "label": "Fresh & calm"},
        "negative": {"emoji": "🌧️", "label": "Heavy"},
        "pool": [
            {"emoji": "☀️", "label": "Bright"},
            {"emoji": "🏠", "label": "Cozy"},
            {"emoji": "🪴", "label": "Tidy"},
            {"emoji": "🌳", "label": "Outdoors"},
            {"emoji": "🧹", "label": "Cleaned up"},
            {"emoji": "🔆", "label": "Aired out"},
            {"emoji": "😤", "label": "Cluttered"},
            {"emoji": "🌆", "label": "Busy"},
        ],
        "rare": [
            {"emoji": "🏞️", "label": "Nature day"},
            {"emoji": "🌅", "label": "Golden hour"},
            {"emoji": "🌊", "label": "By the water"},
            {"emoji": "🦜", "label": "Wildlife"},
        ],
    },
    "protect": {
        "question": "How are you doing with health protection today?",
        "positive": {"emoji": "🛡️", "label": "On top of it"},
        "negative": {"emoji": "🤒", "label": "Not great"},
        "pool": [
            {"emoji": "💪", "label": "Strong"},
            {"emoji": "💊", "label": "Managing"},
            {"emoji": "🌿", "label": "Natural"},
            {"emoji": "🧴", "label": "Sun-safe"},
            {"emoji": "🧼", "label": "Hygiene"},
            {"emoji": "🩺", "label": "Checked in"},
            {"emoji": "😷", "label": "Careful"},
            {"emoji": "🛌", "label": "Resting up"},
        ],
        "rare": [
            {"emoji": "🦾", "label": "Bulletproof"},
            {"emoji": "🍵", "label": "Immunity boost"},
            {"emoji": "⭐", "label": "Picture of health"},
            {"emoji": "🧬", "label": "Optimized"},
        ],
    },
}

# Preferred pixel anchors per area (positive / negative) when available
PIXEL_ANCHORS = {
    "sleep": ("sleep_great", "sleep_rough"),
    "diet": ("diet_clean", "diet_struggle"),
    "exercise": ("ex_crush", "ex_skip"),
    "mental_health": ("mh_calm", "mh_struggle"),
    "relationships": ("rel_connect", "rel_distant"),
    "environment": ("env_fresh", "env_heavy"),
    "protect": ("pr_ontop", "pr_notgreat"),
}

RARE_CHANCE = 0.12
MIDDLE_COUNT = 3


def _seeded_rng(seed_key):
    digest = hashlib.sha256((seed_key or "").encode("utf-8")).hexdigest()
    return random.Random(int(digest, 16))


def _entry_from_pixel(p, rare=None):
    e = {
        "emoji": p["emoji"],
        "src": p["src"],
        "label": p["label"],
        "pixel_id": p["id"],
    }
    if rare or p.get("rare"):
        e["rare"] = True
    return e


def build_poll_options(area, seed_key=""):
    """Return check-in options for `area` using the pixel library when available.

    Always: positive anchor first, negative last. Middle sample from the
    area pool; occasional rare. Deterministic for seed_key.
    """
    t = POLL_TEMPLATES.get(area) or {}
    rng = _seeded_rng(seed_key or area)
    by_area = pixel_for_area(area)
    common = list(by_area.get("common") or [])
    rare_pool = list(by_area.get("rare") or [])

    if len(common) >= 4:
        # Prefer pixel art
        id_map = {p["id"]: p for p in common + rare_pool}
        pos_id, neg_id = PIXEL_ANCHORS.get(area, (None, None))
        positive = id_map.get(pos_id) or common[0]
        negative = id_map.get(neg_id) or common[-1]
        pool = [p for p in common if p["id"] not in (positive["id"], negative["id"])]
        k = min(MIDDLE_COUNT, len(pool))
        middle = rng.sample(pool, k) if k else []
        options = [_entry_from_pixel(positive)] + [_entry_from_pixel(m) for m in middle]
        if rare_pool and rng.random() < RARE_CHANCE:
            options.append(_entry_from_pixel(rng.choice(rare_pool), rare=True))
        options.append(_entry_from_pixel(negative))
        return options

    # Fallback: legacy unicode emoji templates
    if not t or "positive" not in t:
        return list((t or {}).get("options", []))
    pool = list(t.get("pool", []))
    rare = list(t.get("rare", []))
    k = min(MIDDLE_COUNT, len(pool))
    middle = rng.sample(pool, k) if k else []
    options = [dict(t["positive"])] + [dict(m) for m in middle]
    if rare and rng.random() < RARE_CHANCE:
        chosen = dict(rng.choice(rare))
        chosen["rare"] = True
        options.append(chosen)
    options.append(dict(t["negative"]))
    return options


STICKER_UPDATE_SYNTAX = """To record a sticker on the user's health board:

**STICKER_UPDATE** {"area": "sleep", "emoji": "px:sleep_great", "prompt": "How did you sleep?", "response": "said 7 hours"}

- area: one of sleep, diet, exercise, mental_health, relationships, environment, protect
- emoji: a pixel sticker token like px:sleep_great (preferred) or a unicode emoji
- prompt: the question you asked (stored hidden under the sticker)
- response: user's text if any (stored hidden, can be "")
- date: defaults to today; include "date": "YYYY-MM-DD" to override

Use this whenever the user shares how they're doing in a health area — after a poll answer, or when they volunteer the info conversationally."""
