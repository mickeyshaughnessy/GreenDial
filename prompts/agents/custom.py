"""
Custom Agent — User-defined agent with a personalized system prompt
"""

AGENT_ID = "custom"
AGENT_NAME = "Custom Agent"
AGENT_EMOJI = "⚙️"

CHAT_KEYWORDS = []  # Custom agent is invoked explicitly, not by keyword matching

DEFAULT_SYSTEM_PROMPT = """You are a personalized health assistant for GreenDial.
You have been configured by the user with specific instructions.
Always be kind, helpful, and truthful.
"""


def get_system_prompt(user_settings: dict) -> str:
    """Return the user's custom system prompt, or the default if not set."""
    custom = (user_settings or {}).get("custom_agent_prompt", "").strip()
    return custom if custom else DEFAULT_SYSTEM_PROMPT


SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT  # used as fallback by agent runner

CRON_PROMPT_TEMPLATE = """You are a personalized health assistant configured by the user.

CUSTOM INSTRUCTIONS FROM USER:
{custom_prompt}

USER PROFILE:
{profile_json}

RECENT CONVERSATION:
{transcript}

Generate a short, helpful check-in message (max 20 words) tailored to the user's custom instructions and profile.

Output JSON:
{{"message": "...", "type": "custom_checkin"}}
"""
