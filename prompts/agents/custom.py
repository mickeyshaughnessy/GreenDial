"""
Custom Agent — User-defined agent with a personalized system prompt
"""

AGENT_ID = "custom"
AGENT_NAME = "Custom Agent"
AGENT_EMOJI = "⚙️"

CHAT_KEYWORDS = []  # Invoked explicitly, not by keyword matching

DEFAULT_SYSTEM_PROMPT = """You are a personalized health assistant for GreenDial, configured by the user with specific instructions. Follow those instructions precisely."""


def get_system_prompt(user_settings: dict) -> str:
    """Return the user's custom system prompt, or the default if not set."""
    custom = (user_settings or {}).get("custom_agent_prompt", "").strip()
    return custom if custom else DEFAULT_SYSTEM_PROMPT


SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT  # fallback for agent runner

ONBOARDING_FIELDS = []
ONBOARDING_INTRO = "I'm your custom assistant — configured exactly to your needs."
ONBOARDING_FOCUS = "their specific needs as defined in the custom prompt"
ONBOARDING_PRIORITY = None

CRON_DESCRIPTION = "personalized check-in message"
CRON_GUIDELINES = "- Follow the custom instructions from the user\n- Be specific to their profile"

CRON_CADENCE_HOURS = 20
