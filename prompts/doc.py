"""
Doc's System Prompt - Modular Architecture

The prompt is built dynamically from components based on context.
"""

# ============ CORE IDENTITY ============
CORE = """You are Doc, a health assistant. You help users build their health profile through natural conversation."""


# ============ PROFILE UPDATE INSTRUCTIONS ============
# Only included when profile has missing fields
PROFILE_INSTRUCTIONS = """
## PROFILE UPDATES
When the user shares health info, emit:

**PROFILE_UPDATE**
{"field": "value"}

Operations:
- Set: {"age": "44"} - sets the field
- Append: {"medications": "+aspirin"} - adds to existing (use + prefix)
- Delete: {"allergies": null} - removes the field
- Nested: {"vitals": {"bp": "120/80"}} - creates sub-object

Fields: primary_concern, health_conditions, medications, allergies, age, weight, height, location, diet_type, exercise_frequency, exercise_type, sleep_hours, sleep_quality, stress_level, goals, notes

Example - User says "I'm 44 and have diabetes":
**PROFILE_UPDATE**
{"age": "44", "health_conditions": "diabetes"}
"""


# ============ PROFILE CONTEXT ============
# Template for showing current profile
PROFILE_CONTEXT = """
## CURRENT PROFILE
{profile_json}
"""

# When profile is empty
PROFILE_EMPTY = """
## PROFILE STATUS
Empty - gather basic info: why they're here, any health conditions, goals.
"""

# When profile is partial
PROFILE_PARTIAL = """
## PROFILE STATUS
Partial - missing: {missing_fields}
"""

# When profile is complete
PROFILE_COMPLETE = """
## PROFILE STATUS
Complete. Focus on their goals and providing helpful responses.
"""


# ============ CHAT HISTORY ============
# Recent messages (last few exchanges)
CHAT_RECENT = """
## RECENT CONVERSATION
{recent_messages}
"""

# Summarized older history (if available)
CHAT_SUMMARY = """
## CONVERSATION SUMMARY
{summary}
"""


# ============ STYLE MIRRORING ============
# Dynamic based on user's detected style
STYLE_MIRROR_SHORT = """
## YOUR STYLE
User writes briefly. Match them: 1-2 short sentences max. No fluff."""

STYLE_MIRROR_MEDIUM = """
## YOUR STYLE
User writes moderate length. Match them: 2-3 sentences. Be conversational."""

STYLE_MIRROR_LONG = """
## YOUR STYLE
User writes detailed messages. You can be more thorough, but stay focused."""

STYLE_MIRROR_CASUAL = """
## TONE
User is casual/informal. Match their energy. Use contractions, be relaxed."""

STYLE_MIRROR_FORMAL = """
## TONE
User is formal. Be professional and clear."""


# ============ RESPONSE RULES ============
RESPONSE_RULES = """
## RULES
- ALWAYS end your response with exactly ONE question
- Match the user's message length
- Only update profile with info they explicitly stated
- Keep the conversation going - never leave them hanging
"""


# ============ FINAL INSTRUCTION ============
FINAL_INSTRUCTION = """
---
User: {user_input}

Doc (respond briefly, then ask ONE question):"""


# ============ BUILDER FUNCTIONS ============

def analyze_user_style(user_input, recent_messages=""):
    """Analyze user's communication style from their messages"""
    style = {
        "length": "medium",
        "tone": "casual",
        "avg_words": 0
    }
    
    # Analyze current input
    words = len(user_input.split())
    style["avg_words"] = words
    
    # Determine length style
    if words <= 5:
        style["length"] = "short"
    elif words <= 20:
        style["length"] = "medium"
    else:
        style["length"] = "long"
    
    # Determine tone
    formal_indicators = ["please", "would", "could", "appreciate", "regarding", "kindly"]
    casual_indicators = ["hey", "yeah", "yep", "nope", "gonna", "wanna", "lol", "!", "haha"]
    
    input_lower = user_input.lower()
    formal_count = sum(1 for w in formal_indicators if w in input_lower)
    casual_count = sum(1 for w in casual_indicators if w in input_lower)
    
    if formal_count > casual_count:
        style["tone"] = "formal"
    else:
        style["tone"] = "casual"
    
    return style


def get_missing_fields(profile):
    """Get list of missing important profile fields"""
    important = ["primary_concern", "health_conditions", "goals"]
    secondary = ["age", "medications", "exercise_frequency", "sleep_hours"]
    
    missing = []
    for field in important:
        if not profile.get(field):
            missing.append(field)
    
    if len(missing) < 3:
        for field in secondary:
            if not profile.get(field):
                missing.append(field)
                if len(missing) >= 3:
                    break
    
    return missing


def build_prompt(user_input, username="Guest", profile=None, recent_transcript="", summary="", settings=None):
    """
    Build the complete prompt dynamically based on context.
    
    Args:
        user_input: Current user message
        username: User's name
        profile: User's profile dict (or None/empty)
        recent_transcript: Recent chat messages (last 5-10 exchanges)
        summary: Summarized older conversation history
        settings: User settings dict
    
    Returns:
        Complete prompt string
    """
    import json
    
    profile = profile or {}
    settings = settings or {}
    parts = []
    
    # 1. Core identity
    parts.append(CORE)
    
    # 2. Analyze user style and add mirroring instructions
    style = analyze_user_style(user_input, recent_transcript)
    
    if style["length"] == "short":
        parts.append(STYLE_MIRROR_SHORT)
    elif style["length"] == "long":
        parts.append(STYLE_MIRROR_LONG)
    else:
        parts.append(STYLE_MIRROR_MEDIUM)
    
    if style["tone"] == "formal":
        parts.append(STYLE_MIRROR_FORMAL)
    else:
        parts.append(STYLE_MIRROR_CASUAL)
    
    # 3. Profile instructions (if profile incomplete)
    missing = get_missing_fields(profile)
    if missing:
        parts.append(PROFILE_INSTRUCTIONS)
    
    # 4. Profile context
    if not profile:
        parts.append(PROFILE_EMPTY)
    elif missing:
        parts.append(PROFILE_PARTIAL.format(missing_fields=", ".join(missing)))
        parts.append(PROFILE_CONTEXT.format(profile_json=json.dumps(profile, indent=2)))
    else:
        parts.append(PROFILE_COMPLETE)
        parts.append(PROFILE_CONTEXT.format(profile_json=json.dumps(profile, indent=2)))
    
    # 5. Conversation summary (if available)
    if summary and summary.strip():
        parts.append(CHAT_SUMMARY.format(summary=summary))
    
    # 6. Recent conversation (if available)
    if recent_transcript and recent_transcript.strip():
        # Only include last portion
        lines = recent_transcript.strip().split('\n')
        recent = '\n'.join(lines[-10:])  # Last 10 lines
        parts.append(CHAT_RECENT.format(recent_messages=recent))
    
    # 7. Response rules
    parts.append(RESPONSE_RULES)
    
    # 8. Final instruction with user input
    parts.append(FINAL_INSTRUCTION.format(user_input=user_input))
    
    return "\n".join(parts)


# ============ LEGACY SUPPORT ============
# Keep these for backward compatibility during transition

DOC_SYSTEM = """You are Doc, a health assistant. Build the user's health profile through conversation.

## RULES
- ONE question per response
- Match user's message length
- Emit **PROFILE_UPDATE** {{"field": "value"}} when user shares health info

## STYLE
{style_instructions}

User: {username}
Profile: {user_profile}
Recent: {transcript}

---
User: {user_input}

Doc:"""
# Note: DOC_SYSTEM uses .format() so double braces are correct there

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
