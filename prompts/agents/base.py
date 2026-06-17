"""
Shared builders for agent onboarding and cron prompts.

Each agent module must define:
  AGENT_NAME           str        — display name ("Diet Advisor")
  AGENT_ID             str        — slug ("diet")
  ONBOARDING_FIELDS    list[str]  — fields to gather during onboarding
  ONBOARDING_FOCUS     str        — topic clause, e.g. "their eating habits"
  ONBOARDING_PRIORITY  str|None   — optional priority hint, e.g. "Prioritize..."
  CRON_DESCRIPTION     str        — e.g. "nutrition check-in notification"
  CRON_GUIDELINES      str        — bullet points for cron generation
"""
import json
from prompts.shared.profile import PROFILE_UPDATE_SYNTAX


def build_onboarding_prompt(module, profile, transcript, turn_number):
    """Standard onboarding interview prompt for any specialist agent."""
    name = getattr(module, 'AGENT_NAME', 'Health Advisor')
    fields = getattr(module, 'ONBOARDING_FIELDS', [])
    focus = getattr(module, 'ONBOARDING_FOCUS', 'their health situation')
    priority = (getattr(module, 'ONBOARDING_PRIORITY', '') or '').strip()

    missing = [f for f in fields if not (profile or {}).get(f)]
    missing_str = ', '.join(missing) if missing else 'none — profile complete'
    profile_str = json.dumps(profile, indent=2) if profile else '{}'
    transcript_str = (transcript or '').strip() or '(first conversation)'
    priority_line = f'\n{priority}' if priority else ''

    return (
        f"You are the {name} for GreenDial, conducting a brief onboarding interview.\n\n"
        f"KNOWN PROFILE:\n{profile_str}\n\n"
        f"FIELDS STILL NEEDED: {missing_str}\n\n"
        f"CONVERSATION SO FAR:\n{transcript_str}\n\n"
        f"This is onboarding turn {turn_number} of 3. "
        f"Ask ONE focused question about {focus}. "
        f"If this is turn 1, introduce yourself in one sentence, then ask.{priority_line}\n\n"
        f"{PROFILE_UPDATE_SYNTAX}\n\n"
        f"{name} (onboarding):"
    )


def build_cron_prompt(module, profile, transcript, settings=None):
    """Standard cron notification prompt for any specialist agent."""
    name = getattr(module, 'AGENT_NAME', 'Health Advisor')
    agent_id = getattr(module, 'AGENT_ID', 'health')
    description = getattr(module, 'CRON_DESCRIPTION', 'health tip')
    guidelines = getattr(module, 'CRON_GUIDELINES', '- Be specific to the user\'s profile\n- Keep it actionable')

    profile_str = json.dumps(profile, indent=2) if profile else '{}'
    transcript_str = (transcript or '').strip() or '(none yet)'

    custom_block = ''
    if agent_id == 'custom':
        custom_prompt = (settings or {}).get('custom_agent_prompt', '')
        if custom_prompt:
            custom_block = f"CUSTOM INSTRUCTIONS FROM USER:\n{custom_prompt}\n\n"

    return (
        f"You are the {name} for GreenDial. Generate a short {description} (max 20 words).\n\n"
        f"{custom_block}"
        f"USER PROFILE:\n{profile_str}\n\n"
        f"RECENT CONVERSATION:\n{transcript_str}\n\n"
        f"{guidelines}\n\n"
        f'Output JSON:\n{{"message": "...", "type": "{agent_id}_checkin"}}'
    )
