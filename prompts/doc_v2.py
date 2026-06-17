"""
Doc Prompt System
Builds the context-aware prompt for Doc, GreenDial's primary health coordinator.
"""

import json
from prompts.shared.profile import PROFILE_UPDATE_SYNTAX

# ============ CORE IDENTITY ============

CORE_IDENTITY = """You are Doc, GreenDial's health coordinator. You help people understand and improve their health through conversation, track what they share, and connect them with specialist agents when useful.

- Ask one focused question per turn. Pick the most important thing missing from their profile.
- Don't ask about anything already in the profile.
- Don't open with "Great!" or "I'm glad you asked" — just respond.
- When AGENT CONTEXT is shown, weave those insights into your reply without attributing them."""


# ============ AGENT REDIRECT RULES ============

AGENT_DISPATCH_INSTRUCTIONS = """
## REDIRECT RULES
When the user's question belongs clearly to one specialist domain, redirect them there.
Emit this marker (stripped server-side) and one brief handoff line:

**REDIRECT_TO** {"agent": "diet"}          — nutrition, food, eating, weight
**REDIRECT_TO** {"agent": "exercise"}      — workouts, fitness, movement
**REDIRECT_TO** {"agent": "sleep"}         — sleep, fatigue, insomnia
**REDIRECT_TO** {"agent": "protect"}       — immunity, prevention, screenings, risk
**REDIRECT_TO** {"agent": "mental_health"} — stress, anxiety, depression, mood
**REDIRECT_TO** {"agent": "relationships"} — social connection, loneliness, family
**REDIRECT_TO** {"agent": "environment"}   — air quality, home, workplace
**REDIRECT_TO** {"agent": "custom"}        — if user has a custom agent configured

Redirect reply: one sentence only, e.g. "Connecting you with the Sleep Coach."
Don't answer the question yourself when redirecting.

Handle directly (no redirect) for:
- General health profile questions (age, conditions, medications, goals)
- Questions spanning multiple domains
- Simple check-ins, small talk, or meta questions
- Anything that spans 2+ specialist areas (Cross AI handles those)
"""


# ============ PROFILE FIELD STRUCTURE ============

PROFILE_FIELDS = {
    "primary_concern":    {"priority": 1, "category": "Core"},
    "health_conditions":  {"priority": 1, "category": "Core"},
    "symptoms":           {"priority": 1, "category": "Core"},
    "medications":        {"priority": 2, "category": "Treatment"},
    "allergies":          {"priority": 2, "category": "Safety"},
    "goals":              {"priority": 2, "category": "Objectives"},
    "exercise_frequency": {"priority": 3, "category": "Lifestyle"},
    "diet_type":          {"priority": 3, "category": "Lifestyle"},
    "sleep_hours":        {"priority": 3, "category": "Lifestyle"},
    "stress_level":       {"priority": 3, "category": "Mental"},
    "previous_treatments":{"priority": 3, "category": "History"},
    "age":                {"priority": 4, "category": "Demographics"},
    "family_history":     {"priority": 4, "category": "Background"},
}


# ============ CONVERSATION STAGES ============

def get_conversation_stage(profile):
    filled = sum(1 for v in profile.values() if v)
    if filled == 0:
        return "introduction"
    elif filled < 3:
        return "core_assessment"
    elif filled < 8:
        return "deep_dive"
    elif filled < len(PROFILE_FIELDS) * 0.8:
        return "comprehensive"
    else:
        return "maintenance"


def get_priority_missing_fields(profile):
    missing = [
        (field, cfg["priority"])
        for field, cfg in PROFILE_FIELDS.items()
        if not profile.get(field)
    ]
    missing.sort(key=lambda x: x[1])
    return missing


STAGE_INSTRUCTIONS = {
    "introduction": "The user is new. Find out what brings them here.",
    "core_assessment": "Focus: conditions, medications, allergies, symptoms. Ask about the most important missing one.",
    "deep_dive": "Focus: lifestyle (diet, exercise, sleep, stress), treatment history, family history.",
    "comprehensive": "Profile mostly filled. Check STATUS for remaining gaps and ask about the top missing field.",
    "maintenance": "Profile complete. Check on progress and update anything that's changed.",
}


# ============ PROMPT BUILDER ============

def build_doc_prompt(user_input, profile, recent_transcript="", username="Guest",
                     agent_context=None, history_summary=None,
                     style_hint=None, focus=None):
    """Build the complete prompt for Doc.

    style_hint: optional string from prompts.shared.style (cross-conversation style)
    focus:      optional string from supervisor analysis (what to address)
    agent_context: optional specialist response to weave in
    history_summary: optional compact summary of tracked health history (14 days)
    """
    stage = get_conversation_stage(profile)
    stage_instruction = STAGE_INSTRUCTIONS.get(stage, STAGE_INSTRUCTIONS["introduction"])

    missing = get_priority_missing_fields(profile)
    missing_text = f"Missing: {', '.join(f[0] for f in missing[:5])}" if missing else "Profile complete"

    profile_summary = json.dumps(profile, indent=2) if profile else "{empty}"

    recent_lines = (recent_transcript or '').strip().split('\n')[-8:]
    recent_text = '\n'.join(recent_lines) if any(recent_lines) else "(start of conversation)"

    # Optional sections
    style_section = f"\n## STYLE\n{style_hint}" if style_hint else ""
    focus_section = f"\n## FOCUS\n{focus}" if focus else ""

    agent_section = ""
    if agent_context:
        agent_section = (
            "\n## AGENT CONTEXT\n"
            "A specialist provided the following. Weave it into your reply naturally — "
            "don't quote it or attribute it:\n\n"
            f"{agent_context}"
        )

    history_section = ""
    if history_summary:
        history_section = (
            "\n## TRACKED HEALTH HISTORY (last 14 days)\n"
            f"{history_summary}\n\n"
            "Use these numbers when the user asks about progress or trends. "
            "Mention a clear trend proactively when relevant."
        )

    return (
        f"{CORE_IDENTITY}\n\n"
        f"{AGENT_DISPATCH_INSTRUCTIONS}\n\n"
        f"## STAGE: {stage_instruction}\n\n"
        f"## CURRENT PROFILE\n{profile_summary}\n\n"
        f"## STATUS\n{missing_text}\n\n"
        f"## RECENT CONVERSATION\n{recent_text}"
        f"{agent_section}"
        f"{history_section}"
        f"{style_section}"
        f"{focus_section}\n\n"
        f"## INSTRUCTIONS\n"
        f"- End with one short question.\n"
        f"- Use the profile update syntax below when the user shares health info.\n"
        f"- Redirect to a specialist when the question is clearly one domain's territory.\n\n"
        f"{PROFILE_UPDATE_SYNTAX}\n\n"
        f"---\n"
        f"User ({username}): {user_input}\n\n"
        f"Doc:"
    )


# ============ MISC HELPERS ============

def get_next_probing_question(profile, last_field_updated=None):
    missing = get_priority_missing_fields(profile)
    if not missing:
        return None
    return f"What about your {missing[0][0].replace('_', ' ')}?"


# ============ LEGACY CONSTANTS (kept for backward compat) ============

DOC_STYLES = {
    "questioning": "Be curious. Brief acknowledgment, ONE question.",
    "professional": "Be clinical. Note info, ONE direct question.",
    "friendly": "Be warm. React naturally, ONE friendly question."
}

DEFAULT_STYLE = "questioning"

HEALTH_TIPS = [
    "Drinking water first thing in the morning can help kickstart your metabolism.",
    "Even a 10-minute walk can boost your mood and energy levels.",
    "Good sleep is as important as diet and exercise for overall health.",
    "Stress management is a key part of physical health.",
    "Small, consistent changes work better than dramatic overhauls."
]
