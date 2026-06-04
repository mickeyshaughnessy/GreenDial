"""
GreenDial Health Agents

Each agent is an expert AI assistant for a specific health domain.
All agents are kind, helpful, and truthful.

Agent contract:
  - AGENT_ID:   unique slug used in API routes and user settings
  - AGENT_NAME: display name shown to users
  - AGENT_EMOJI: display emoji
  - SYSTEM_PROMPT: core personality + expertise
  - CHAT_KEYWORDS: list of lowercase keywords that hint Doc should invoke this agent
  - CRON_PROMPT_TEMPLATE: template for periodic check-in notifications
    (receives profile, recent_transcript as format kwargs)
"""

from . import diet, exercise, protect, sleep, mental_health, relationships, environment, custom, cross_ai

# Ordered registry — Doc and cron runner look agents up here
# cross_ai is listed last so keyword matching prefers specialists
REGISTRY = {
    "diet":          diet,
    "exercise":      exercise,
    "protect":       protect,
    "sleep":         sleep,
    "mental_health": mental_health,
    "relationships": relationships,
    "environment":   environment,
    "custom":        custom,
    "cross_ai":      cross_ai,
}

# Legacy IDs from before the immunity+disease_prevention merge — map to protect
LEGACY_ID_MAP = {
    "immunity":           "protect",
    "disease_prevention": "protect",
}

ALL_AGENT_IDS = list(REGISTRY.keys())


def get_agent(agent_id: str):
    return REGISTRY.get(agent_id)


def agents_for_message(user_message: str) -> list:
    """Return list of agent_ids whose keywords appear in the user message (excludes cross_ai)."""
    text = user_message.lower()
    matched = []
    for agent_id, module in REGISTRY.items():
        if agent_id == "cross_ai":
            continue
        for kw in getattr(module, "CHAT_KEYWORDS", []):
            if kw in text:
                matched.append(agent_id)
                break
    return matched


def get_missing_onboarding_fields(agent_id: str, profile: dict) -> list:
    """Return which ONBOARDING_FIELDS for this agent are missing from the profile."""
    module = REGISTRY.get(agent_id)
    if not module:
        return []
    fields = getattr(module, "ONBOARDING_FIELDS", [])
    return [f for f in fields if not profile.get(f)]


def needs_onboarding(agent_id: str, profile: dict, agent_prefs: dict) -> bool:
    """True if this agent has onboarding fields and they haven't all been gathered."""
    prefs = (agent_prefs or {}).get(agent_id, {})
    if prefs.get("onboarded"):
        return False
    missing = get_missing_onboarding_fields(agent_id, profile)
    return len(missing) >= 2  # needs onboarding if 2+ fields still missing
