"""
Supervisor Prompt - First stage LLM call

The supervisor analyzes the user's message and context, then constructs
a dynamic system prompt for Doc (the second stage).
"""

import json

SUPERVISOR_SYSTEM = """You are a conversation supervisor for a health assistant named Doc.

Your job: Analyze the user's message and context, then output instructions for Doc.

You MUST output valid JSON with this exact structure:
{
  "style": "short|medium|long",
  "tone": "casual|formal|empathetic",
  "focus": "brief description of what Doc should focus on",
  "profile_action": "none|gather|update",
  "profile_fields": ["fields to gather or that were mentioned"],
  "include_history": true|false,
  "special_instructions": "any specific guidance for this response"
}

Guidelines:
- style: Match user's message length (short=1-5 words, medium=6-20, long=20+)
- tone: casual for informal users, formal for professional, empathetic for health concerns
- focus: What should Doc address? The main topic or question.
- profile_action: "gather" if missing key info, "update" if user shared new info, "none" otherwise
- profile_fields: Which fields are relevant (primary_concern, health_conditions, medications, allergies, age, goals, etc.)
- include_history: true if context from past conversation is relevant
- special_instructions: Edge cases, sensitive topics, or specific guidance

Output ONLY the JSON object, no other text."""


SUPERVISOR_USER_TEMPLATE = """## USER MESSAGE
{user_input}

## CURRENT PROFILE
{profile_json}

## MISSING PROFILE FIELDS
{missing_fields}

## RECENT CONVERSATION
{recent_transcript}

Analyze and output JSON instructions for Doc:"""


DOC_SYSTEM_TEMPLATE = """You are Doc, a health assistant helping {username}.

{style_instruction}

{tone_instruction}

{focus_instruction}

{profile_instruction}

{special_instruction}

## RULES
- End with exactly ONE question to keep the conversation going
- Only emit **PROFILE_UPDATE** if user explicitly shared new health info
- Be concise and match the user's communication style

{profile_context}

{history_context}"""


STYLE_INSTRUCTIONS = {
    "short": "STYLE: User writes briefly. Match them: 1-2 short sentences max.",
    "medium": "STYLE: User writes moderate length. Match them: 2-3 sentences.",
    "long": "STYLE: User writes in detail. You can be thorough but stay focused."
}

TONE_INSTRUCTIONS = {
    "casual": "TONE: Be relaxed and conversational. Use contractions.",
    "formal": "TONE: Be professional and clear. Avoid slang.",
    "empathetic": "TONE: Be warm and understanding. This may be a sensitive topic."
}

PROFILE_INSTRUCTIONS = {
    "none": "",
    "gather": """PROFILE GATHERING: Key info is missing. Naturally work toward learning: {fields}
Don't interrogate - weave questions into conversation.""",
    "update": """PROFILE UPDATE: User shared health info. Emit:
**PROFILE_UPDATE**
{{"field": "value"}}

Fields mentioned: {fields}
Only include what they explicitly stated."""
}


def get_missing_fields(profile):
    """Get list of missing important profile fields"""
    important = ["primary_concern", "health_conditions", "goals"]
    secondary = ["age", "medications", "exercise_frequency"]
    
    missing = []
    for field in important:
        if not profile.get(field):
            missing.append(field)
    
    for field in secondary:
        if not profile.get(field) and len(missing) < 5:
            missing.append(field)
    
    return missing


def build_supervisor_prompt(user_input, profile=None, recent_transcript=""):
    """Build the prompt for the supervisor (first LLM call)"""
    profile = profile or {}
    missing = get_missing_fields(profile)
    
    return {
        "system": SUPERVISOR_SYSTEM,
        "user": SUPERVISOR_USER_TEMPLATE.format(
            user_input=user_input,
            profile_json=json.dumps(profile, indent=2) if profile else "{}",
            missing_fields=", ".join(missing) if missing else "None - profile is complete",
            recent_transcript=recent_transcript[-1000:] if recent_transcript else "No previous conversation"
        )
    }


def parse_supervisor_response(response_text):
    """Parse supervisor's JSON response, with fallback defaults"""
    defaults = {
        "style": "medium",
        "tone": "casual",
        "focus": "Respond helpfully to the user",
        "profile_action": "none",
        "profile_fields": [],
        "include_history": True,
        "special_instructions": ""
    }
    
    try:
        # Try to extract JSON from response
        text = response_text.strip()
        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        parsed = json.loads(text)
        # Merge with defaults
        for key in defaults:
            if key not in parsed:
                parsed[key] = defaults[key]
        return parsed
    except (json.JSONDecodeError, IndexError):
        print(f"[Supervisor] Failed to parse response: {response_text[:200]}")
        return defaults


def build_doc_prompt(supervisor_output, username="Guest", profile=None, recent_transcript=""):
    """Build Doc's system prompt from supervisor instructions"""
    profile = profile or {}
    
    style_inst = STYLE_INSTRUCTIONS.get(supervisor_output.get("style", "medium"), STYLE_INSTRUCTIONS["medium"])
    tone_inst = TONE_INSTRUCTIONS.get(supervisor_output.get("tone", "casual"), TONE_INSTRUCTIONS["casual"])
    focus_inst = f"FOCUS: {supervisor_output.get('focus', 'Help the user with their health questions')}"
    
    # Profile instruction
    profile_action = supervisor_output.get("profile_action", "none")
    profile_fields = supervisor_output.get("profile_fields", [])
    profile_inst = PROFILE_INSTRUCTIONS.get(profile_action, "")
    if profile_inst and profile_fields:
        profile_inst = profile_inst.format(fields=", ".join(profile_fields))
    
    # Special instructions
    special_inst = supervisor_output.get("special_instructions", "")
    if special_inst:
        special_inst = f"NOTE: {special_inst}"
    
    # Profile context
    profile_context = ""
    if profile:
        profile_context = f"## USER PROFILE\n{json.dumps(profile, indent=2)}"
    
    # History context
    history_context = ""
    if supervisor_output.get("include_history") and recent_transcript:
        lines = recent_transcript.strip().split('\n')[-8:]
        history_context = f"## RECENT CONVERSATION\n" + "\n".join(lines)
    
    system_prompt = DOC_SYSTEM_TEMPLATE.format(
        username=username,
        style_instruction=style_inst,
        tone_instruction=tone_inst,
        focus_instruction=focus_inst,
        profile_instruction=profile_inst,
        special_instruction=special_inst,
        profile_context=profile_context,
        history_context=history_context
    )
    
    # Clean up extra whitespace
    system_prompt = "\n".join(line for line in system_prompt.split("\n") if line.strip() or line == "")
    
    return system_prompt
