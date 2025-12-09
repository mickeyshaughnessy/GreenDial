"""
Supervisor Prompt - First stage LLM call

The supervisor analyzes the user's message and context, then constructs
a dynamic system prompt for Doc (the second stage).
"""

import json

SUPERVISOR_SYSTEM = """You are a conversation supervisor for a health assistant named Doc.

Your job: Analyze the user's message and prepare context for Doc to respond helpfully.

Output JSON:
{
  "length": "short|medium|long",
  "tone": "casual|formal",
  "focus": "what Doc should address in the response",
  "context": "relevant background info Doc needs",
  "profile_action": "none|gather|update",
  "profile_fields": ["relevant fields"]
}

Guidelines:
- length: short (<10 words), medium (10-30), long (30+) - Doc should roughly match
- tone: casual (informal language) or formal (professional)
- focus: The main thing Doc should respond to
- context: Any relevant info from profile/history that helps Doc respond
- profile_action: "gather" if key info missing, "update" if user shared health info
- profile_fields: Which fields are relevant

Output ONLY the JSON object."""


SUPERVISOR_USER_TEMPLATE = """## USER MESSAGE
{user_input}

## DOC'S STYLE SETTING
{doc_style}

## CURRENT PROFILE
{profile_json}

## MISSING PROFILE FIELDS
{missing_fields}

## RECENT CONVERSATION
{recent_transcript}

Analyze and output JSON instructions for Doc:"""


DOC_STYLE_DESCRIPTIONS = {
    "questioning": "Be curious and inquisitive. Ask follow-up questions to learn more.",
    "professional": "Be clinical and direct. Focus on facts and clear guidance.",
    "friendly": "Be warm and personable. Show genuine interest and care."
}


DOC_SYSTEM_TEMPLATE = """You are Doc, a health assistant helping {username}.

## STYLE
{doc_style_instruction}
{length_instruction}
{tone_instruction}

## FOCUS
{focus_instruction}

{context_instruction}

{profile_instruction}

## RULES
- End with ONE question
- If user shared health info, emit **PROFILE_UPDATE** {{"fieldname": "value"}} (e.g. {{"goals": "lose weight"}})

{profile_context}

{history_context}"""


LENGTH_INSTRUCTIONS = {
    "short": "Keep your response brief - a sentence or two.",
    "medium": "Respond conversationally - a few sentences.",
    "long": "You can be more thorough in your response."
}

TONE_INSTRUCTIONS = {
    "casual": "Be relaxed and conversational.",
    "formal": "Be professional and clear."
}

PROFILE_INSTRUCTIONS = {
    "none": "",
    "gather": "Try to learn about: {fields}",
    "update": """User shared health info. Emit a profile update.

FORMAT (use actual field names as keys):
**PROFILE_UPDATE**
{{"goals": "their goal", "age": "44"}}

CORRECT: {{"goals": "get stronger", "weight": "180lbs"}}
WRONG: {{"field": "goals", "value": "get stronger"}}

Fields to update: {fields}"""
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


def build_supervisor_prompt(user_input, profile=None, recent_transcript="", settings=None):
    """Build the prompt for the supervisor (first LLM call)"""
    profile = profile or {}
    settings = settings or {}
    missing = get_missing_fields(profile)
    
    doc_style = settings.get("doc_style", "questioning")
    doc_style_desc = DOC_STYLE_DESCRIPTIONS.get(doc_style, DOC_STYLE_DESCRIPTIONS["questioning"])
    
    return {
        "system": SUPERVISOR_SYSTEM,
        "user": SUPERVISOR_USER_TEMPLATE.format(
            user_input=user_input,
            doc_style=f"{doc_style}: {doc_style_desc}",
            profile_json=json.dumps(profile, indent=2) if profile else "{}",
            missing_fields=", ".join(missing) if missing else "None - profile is complete",
            recent_transcript=recent_transcript[-1000:] if recent_transcript else "No previous conversation"
        )
    }


def parse_supervisor_response(response_text):
    """Parse supervisor's JSON response, with fallback defaults"""
    defaults = {
        "length": "medium",
        "tone": "casual",
        "focus": "Respond helpfully",
        "context": "",
        "profile_action": "none",
        "profile_fields": []
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


def build_doc_prompt(supervisor_output, username="Guest", profile=None, recent_transcript="", settings=None):
    """Build Doc's system prompt from supervisor instructions"""
    profile = profile or {}
    settings = settings or {}
    
    # Doc style from settings
    doc_style = settings.get("doc_style", "questioning")
    doc_style_inst = DOC_STYLE_DESCRIPTIONS.get(doc_style, DOC_STYLE_DESCRIPTIONS["questioning"])
    
    # Length instruction
    length = supervisor_output.get("length", "medium")
    length_inst = LENGTH_INSTRUCTIONS.get(length, LENGTH_INSTRUCTIONS["medium"])
    
    # Tone instruction
    tone_inst = TONE_INSTRUCTIONS.get(supervisor_output.get("tone", "casual"), TONE_INSTRUCTIONS["casual"])
    
    # Focus
    focus_inst = supervisor_output.get('focus', 'Help the user')
    
    # Context from supervisor
    context = supervisor_output.get("context", "")
    context_inst = f"## CONTEXT\n{context}" if context else ""
    
    # Profile instruction
    profile_action = supervisor_output.get("profile_action", "none")
    profile_fields = supervisor_output.get("profile_fields", [])
    profile_inst = PROFILE_INSTRUCTIONS.get(profile_action, "")
    if profile_inst and profile_fields:
        profile_inst = profile_inst.format(fields=", ".join(profile_fields))
    
    # Profile context
    profile_context = ""
    if profile:
        profile_context = f"## USER PROFILE\n{json.dumps(profile, indent=2)}"
    
    # History context
    history_context = ""
    if recent_transcript:
        lines = recent_transcript.strip().split('\n')[-6:]
        history_context = f"## RECENT\n" + "\n".join(lines)
    
    system_prompt = DOC_SYSTEM_TEMPLATE.format(
        username=username,
        doc_style_instruction=doc_style_inst,
        length_instruction=length_inst,
        tone_instruction=tone_inst,
        focus_instruction=focus_inst,
        context_instruction=context_inst,
        profile_instruction=profile_inst,
        profile_context=profile_context,
        history_context=history_context
    )
    
    # Clean up extra whitespace
    system_prompt = "\n".join(line for line in system_prompt.split("\n") if line.strip() or line == "")
    
    return system_prompt
