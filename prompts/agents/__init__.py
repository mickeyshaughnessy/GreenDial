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

from . import diet, exercise, immunity, sleep, disease_prevention, mental_health, relationships, environment, custom

# Ordered registry — Doc and cron runner look agents up here
REGISTRY = {
    "diet":               diet,
    "exercise":           exercise,
    "immunity":           immunity,
    "sleep":              sleep,
    "disease_prevention": disease_prevention,
    "mental_health":      mental_health,
    "relationships":      relationships,
    "environment":        environment,
    "custom":             custom,
}

ALL_AGENT_IDS = list(REGISTRY.keys())


def get_agent(agent_id: str):
    return REGISTRY.get(agent_id)


def agents_for_message(user_message: str) -> list:
    """Return list of agent_ids whose keywords appear in the user message."""
    text = user_message.lower()
    matched = []
    for agent_id, module in REGISTRY.items():
        for kw in getattr(module, "CHAT_KEYWORDS", []):
            if kw in text:
                matched.append(agent_id)
                break
    return matched
