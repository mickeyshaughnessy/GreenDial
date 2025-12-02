"""
Supervisor Prompt - First stage LLM call

The supervisor analyzes the user's message and context, then constructs
a dynamic system prompt for Doc (the second stage).
"""

import json

SUPERVISOR_SYSTEM = """You are a conversation supervisor for a health assistant named Doc.

Your PRIMARY job: Analyze the user's writing style and ensure Doc mirrors it exactly.

You MUST output valid JSON with this exact structure:
{
  "word_count": <number of words in user message>,
  "target_words": <Doc should respond with approximately this many words>,
  "style": "terse|short|medium|detailed",
  "tone": "casual|neutral|formal|empathetic",
  "punctuation": "minimal|normal|expressive",
  "vocabulary": "simple|normal|sophisticated",
  "focus": "brief description of what Doc should focus on",
  "profile_action": "none|gather|update",
  "profile_fields": ["fields to gather or that were mentioned"],
  "style_notes": "specific observations about user's writing style to mirror"
}

STYLE ANALYSIS (most important):
- Count the user's words exactly
- terse: 1-4 words (respond with 5-15 words)
- short: 5-12 words (respond with 10-25 words)  
- medium: 13-30 words (respond with 20-50 words)
- detailed: 31+ words (respond with 40-80 words)

TONE ANALYSIS:
- casual: contractions, slang, lowercase, "hey", "yeah", "cool", emojis
- neutral: standard writing, mixed case, no strong markers
- formal: complete sentences, proper grammar, "please", "thank you", professional
- empathetic: sharing concerns, health worries, emotional content

PUNCTUATION:
- minimal: few or no punctuation marks, no exclamation points
- normal: standard punctuation
- expressive: multiple punctuation marks, exclamation points, ellipses

VOCABULARY:
- simple: basic words, short sentences
- normal: everyday language
- sophisticated: complex words, medical terms, detailed explanations

style_notes: Note specific things like "user writes in lowercase", "uses abbreviations", "asks direct questions", "no greeting", etc.

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

## CRITICAL: MATCH USER'S STYLE EXACTLY
{style_instruction}

{tone_instruction}

{punctuation_instruction}

{vocabulary_instruction}

{style_notes_instruction}

## FOCUS
{focus_instruction}

{profile_instruction}

## RULES
- STRICTLY match the word count target
- End with exactly ONE short question
- Only emit **PROFILE_UPDATE** if user explicitly shared new health info

{profile_context}

{history_context}"""


STYLE_INSTRUCTIONS = {
    "terse": "LENGTH: User wrote {word_count} words. Respond with {target_words} words MAX. Be extremely brief.",
    "short": "LENGTH: User wrote {word_count} words. Respond with {target_words} words. Keep it short.",
    "medium": "LENGTH: User wrote {word_count} words. Respond with {target_words} words. Be conversational.",
    "detailed": "LENGTH: User wrote {word_count} words. Respond with {target_words} words. You can be thorough."
}

TONE_INSTRUCTIONS = {
    "casual": "TONE: Casual. Use contractions, be relaxed, match their informal energy.",
    "neutral": "TONE: Neutral. Standard conversational tone.",
    "formal": "TONE: Formal. Professional language, complete sentences.",
    "empathetic": "TONE: Empathetic. Be warm, understanding, and supportive."
}

PUNCTUATION_INSTRUCTIONS = {
    "minimal": "PUNCTUATION: Minimal. Few punctuation marks, no exclamation points.",
    "normal": "PUNCTUATION: Normal punctuation.",
    "expressive": "PUNCTUATION: Match their expressive style with appropriate punctuation."
}

VOCABULARY_INSTRUCTIONS = {
    "simple": "VOCABULARY: Simple words, short sentences.",
    "normal": "VOCABULARY: Everyday language.",
    "sophisticated": "VOCABULARY: Can use more detailed/technical language if appropriate."
}

PROFILE_INSTRUCTIONS = {
    "none": "",
    "gather": """PROFILE: Key info missing. Naturally ask about: {fields}
Don't interrogate - weave into conversation.""",
    "update": """PROFILE UPDATE: User shared health info. Emit:
**PROFILE_UPDATE**
{{"field": "value"}}

Fields mentioned: {fields}"""
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
        "word_count": 10,
        "target_words": 25,
        "style": "short",
        "tone": "casual",
        "punctuation": "normal",
        "vocabulary": "normal",
        "focus": "Respond helpfully to the user",
        "profile_action": "none",
        "profile_fields": [],
        "style_notes": ""
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
    
    # Style instruction with word counts
    style = supervisor_output.get("style", "short")
    word_count = supervisor_output.get("word_count", 10)
    target_words = supervisor_output.get("target_words", 25)
    style_inst = STYLE_INSTRUCTIONS.get(style, STYLE_INSTRUCTIONS["short"]).format(
        word_count=word_count,
        target_words=target_words
    )
    
    # Tone instruction
    tone_inst = TONE_INSTRUCTIONS.get(supervisor_output.get("tone", "casual"), TONE_INSTRUCTIONS["casual"])
    
    # Punctuation instruction
    punct_inst = PUNCTUATION_INSTRUCTIONS.get(supervisor_output.get("punctuation", "normal"), PUNCTUATION_INSTRUCTIONS["normal"])
    
    # Vocabulary instruction
    vocab_inst = VOCABULARY_INSTRUCTIONS.get(supervisor_output.get("vocabulary", "normal"), VOCABULARY_INSTRUCTIONS["normal"])
    
    # Style notes
    style_notes = supervisor_output.get("style_notes", "")
    style_notes_inst = f"MIRROR: {style_notes}" if style_notes else ""
    
    # Focus
    focus_inst = supervisor_output.get('focus', 'Help the user with their health questions')
    
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
        history_context = f"## RECENT CONVERSATION\n" + "\n".join(lines)
    
    system_prompt = DOC_SYSTEM_TEMPLATE.format(
        username=username,
        style_instruction=style_inst,
        tone_instruction=tone_inst,
        punctuation_instruction=punct_inst,
        vocabulary_instruction=vocab_inst,
        style_notes_instruction=style_notes_inst,
        focus_instruction=focus_inst,
        profile_instruction=profile_inst,
        profile_context=profile_context,
        history_context=history_context
    )
    
    # Clean up extra whitespace
    system_prompt = "\n".join(line for line in system_prompt.split("\n") if line.strip() or line == "")
    
    return system_prompt
