"""
Supervisor — First-pass LLM that analyzes incoming messages and returns
style/focus hints for Doc. Called sequentially before Doc in handle_chat().
"""

import json

SUPERVISOR_SYSTEM = """You analyze a health chat message and return instructions for the health AI.

Output JSON only — no explanation:
{
  "length": "short|medium|long",
  "tone": "casual|neutral",
  "focus": "one sentence: what the user is actually asking or expressing",
  "mood": "neutral|distressed|motivated|curious"
}

Definitions:
- length: short (<8 words from user), medium (8-30), long (30+) — Doc should roughly match
- tone: casual (hey/yeah/informal) or neutral (standard)
- focus: the specific thing Doc should respond to, more precise than the raw message
- mood: the user's apparent emotional state right now"""


SUPERVISOR_USER_TEMPLATE = """User message: {user_input}

Profile summary: {profile_summary}

Recent conversation (last few turns):
{recent_transcript}

Output JSON:"""

_DEFAULTS = {
    "length": "medium",
    "tone": "neutral",
    "focus": "",
    "mood": "neutral"
}


def build_analyze_prompt(user_input, profile=None, recent_transcript=""):
    profile_summary = ", ".join(
        f"{k}: {v}" for k, v in (profile or {}).items()
        if v and k in ("primary_concern", "health_conditions", "goals", "age")
    ) or "empty"

    recent = "\n".join(
        (recent_transcript or "").strip().split("\n")[-6:]
    ) or "(start of conversation)"

    return SUPERVISOR_USER_TEMPLATE.format(
        user_input=user_input,
        profile_summary=profile_summary,
        recent_transcript=recent
    )


def parse_response(text):
    """Parse supervisor JSON output; return defaults on failure."""
    try:
        raw = text.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        parsed = json.loads(raw)
        return {**_DEFAULTS, **{k: v for k, v in parsed.items() if k in _DEFAULTS}}
    except Exception:
        return dict(_DEFAULTS)


def analyze(user_input, profile=None, recent_transcript="", utils_module=None, config_module=None):
    """
    Run the supervisor LLM and return a hints dict.
    utils_module and config_module are injected by handlers.py to avoid circular imports.
    Returns: {"length": ..., "tone": ..., "focus": ..., "mood": ...}
    """
    if not utils_module or not config_module:
        return dict(_DEFAULTS)

    prompt = build_analyze_prompt(user_input, profile, recent_transcript)

    try:
        response = utils_module.completion(
            prompt=prompt,
            system_prompt=SUPERVISOR_SYSTEM,
            model=config_module.OPENROUTER_FAST_MODEL if hasattr(config_module, 'OPENROUTER_FAST_MODEL') else None,
            temperature=0.2,
            max_tokens=150
        )
        return parse_response(response)
    except Exception as e:
        print(f"[Supervisor] Failed: {e}")
        return dict(_DEFAULTS)
