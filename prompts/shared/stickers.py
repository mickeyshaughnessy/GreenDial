"""
Sticker Board definitions: areas, emoji sets, poll templates, and update syntax.
"""

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

AREA_EMOJIS = {
    "sleep": "🌙",
    "diet": "🥗",
    "exercise": "💪",
    "mental_health": "🧠",
    "relationships": "❤️",
    "environment": "🌿",
    "protect": "🛡️",
}

import hashlib
import random

# Each area keeps a fixed positive and negative anchor (always shown, first and
# last). The middle options are sampled from a larger `pool` so the set varies
# day to day, and there's a small chance a `rare` emoji shows up — a "cool find"
# that lands on the user's sticker board. Variation is deterministic per
# (user, area, day) so the options stay stable across refreshes within a day.
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

# Probability a rare emoji appears in a given poll (per area, per day).
RARE_CHANCE = 0.12
# Number of varied middle options drawn from the pool.
MIDDLE_COUNT = 3


def _seeded_rng(seed_key):
    """Deterministic RNG from a string seed.

    Uses sha256 rather than the builtin hash() because hash() is salted
    per-process — across gunicorn workers it would yield different options for
    the same (user, area, day).
    """
    digest = hashlib.sha256((seed_key or "").encode("utf-8")).hexdigest()
    return random.Random(int(digest, 16))


def build_poll_options(area, seed_key=""):
    """Return a varied list of check-in options for `area`.

    Always: positive anchor first, negative anchor last. In between, a random
    sample of the area's pool, plus an occasional rare emoji (flagged
    ``"rare": True``). Deterministic for a given `seed_key` so the same
    (user, area, day) sees a stable set across refreshes.
    """
    t = POLL_TEMPLATES.get(area)
    if not t or "positive" not in t:
        return list((t or {}).get("options", []))

    rng = _seeded_rng(seed_key or area)
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

STICKER_UPDATE_SYNTAX = """To record an emoji sticker on the user's health board:

**STICKER_UPDATE** {"area": "sleep", "emoji": "😊", "prompt": "How did you sleep?", "response": "said 7 hours"}

- area: one of sleep, diet, exercise, mental_health, relationships, environment, protect
- emoji: the chosen emoji reflecting how things went
- prompt: the question you asked (stored hidden under the sticker)
- response: user's text if any (stored hidden, can be "")
- date: defaults to today; include "date": "YYYY-MM-DD" to override

Use this whenever the user shares how they're doing in a health area — after a poll answer, or when they volunteer the info conversationally."""
