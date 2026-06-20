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

POLL_TEMPLATES = {
    "sleep": {
        "question": "How did you sleep last night?",
        "options": [
            {"emoji": "😴", "label": "Excellent"},
            {"emoji": "😊", "label": "Good"},
            {"emoji": "😐", "label": "OK"},
            {"emoji": "😞", "label": "Poor"},
            {"emoji": "🥱", "label": "Rough"},
        ]
    },
    "diet": {
        "question": "How's your eating been today?",
        "options": [
            {"emoji": "🥗", "label": "Clean & healthy"},
            {"emoji": "😋", "label": "Enjoyed it"},
            {"emoji": "💪", "label": "On point"},
            {"emoji": "🍕", "label": "Indulgent"},
            {"emoji": "😤", "label": "Struggling"},
        ]
    },
    "exercise": {
        "question": "How was your activity level today?",
        "options": [
            {"emoji": "💪", "label": "Crushed it"},
            {"emoji": "🏃", "label": "Active"},
            {"emoji": "🧘", "label": "Gentle movement"},
            {"emoji": "🛋️", "label": "Rest day"},
            {"emoji": "😤", "label": "Missed my goal"},
        ]
    },
    "mental_health": {
        "question": "How are you feeling mentally today?",
        "options": [
            {"emoji": "😌", "label": "Calm & clear"},
            {"emoji": "😊", "label": "Good"},
            {"emoji": "😐", "label": "Mixed"},
            {"emoji": "😟", "label": "Stressed"},
            {"emoji": "😢", "label": "Struggling"},
        ]
    },
    "relationships": {
        "question": "How connected do you feel with others today?",
        "options": [
            {"emoji": "🤗", "label": "Very connected"},
            {"emoji": "❤️", "label": "Loved"},
            {"emoji": "😊", "label": "Good"},
            {"emoji": "😞", "label": "Distant"},
            {"emoji": "🙏", "label": "Grateful"},
        ]
    },
    "environment": {
        "question": "How's your environment been today?",
        "options": [
            {"emoji": "🌿", "label": "Fresh & calm"},
            {"emoji": "☀️", "label": "Good"},
            {"emoji": "🏠", "label": "Cozy"},
            {"emoji": "😤", "label": "Stressful"},
            {"emoji": "🌧️", "label": "Heavy"},
        ]
    },
    "protect": {
        "question": "How are you doing with health protection today?",
        "options": [
            {"emoji": "💪", "label": "Strong"},
            {"emoji": "🛡️", "label": "On top of it"},
            {"emoji": "💊", "label": "Managing"},
            {"emoji": "🤒", "label": "Not great"},
            {"emoji": "🌿", "label": "Natural"},
        ]
    },
}

STICKER_UPDATE_SYNTAX = """To record an emoji sticker on the user's health board:

**STICKER_UPDATE** {"area": "sleep", "emoji": "😊", "prompt": "How did you sleep?", "response": "said 7 hours"}

- area: one of sleep, diet, exercise, mental_health, relationships, environment, protect
- emoji: the chosen emoji reflecting how things went
- prompt: the question you asked (stored hidden under the sticker)
- response: user's text if any (stored hidden, can be "")
- date: defaults to today; include "date": "YYYY-MM-DD" to override

Use this whenever the user shares how they're doing in a health area — after a poll answer, or when they volunteer the info conversationally."""
