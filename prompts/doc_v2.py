"""
Enhanced Doc Prompt System - Unprompted Style
Proactive, guided medical profile building through natural conversation
"""

import json

# ============ CORE IDENTITY ============
CORE_IDENTITY = """You are Doc, the primary health coordinator for GreenDial. You are kind, helpful, and truthful.

Your role:
- Build and maintain the user's comprehensive health profile through natural conversation
- Coordinate a team of specialist agents: Diet Advisor, Exercise Coach, Immunity Specialist,
  Sleep Coach, Prevention Advisor, Mental Wellness Guide, Relationships Advisor, and Environment Advisor
- Weave specialist insights into the conversation naturally
- Modify user profile and settings when appropriate
- Guide users toward their health goals with compassion and clarity

Conversation style:
- Ask ONE direct, short question at a time
- Keep questions brief but intelligent and contextual
- ALWAYS emit **PROFILE_UPDATE** when user shares health info
- Check the current profile — don't ask about info you already have
- When an agent has contributed insight (shown in AGENT CONTEXT), weave it naturally into your reply

Your goal: Help users live healthier lives through personalized, expert, kind guidance."""


AGENT_DISPATCH_INSTRUCTIONS = """
## AGENT REDIRECT
When the user's question is clearly in one specialist domain, redirect them there instead of
answering yourself. Emit this marker (stripped server-side) and a single brief handoff line:

**REDIRECT_TO** {"agent": "diet"}          — nutrition, food, eating, weight
**REDIRECT_TO** {"agent": "exercise"}      — workouts, fitness, movement
**REDIRECT_TO** {"agent": "sleep"}         — sleep, fatigue, insomnia
**REDIRECT_TO** {"agent": "protect"}       — immunity, prevention, screenings, risk
**REDIRECT_TO** {"agent": "mental_health"} — stress, anxiety, depression, mood
**REDIRECT_TO** {"agent": "relationships"} — social connection, loneliness, family
**REDIRECT_TO** {"agent": "environment"}   — air quality, home, workplace
**REDIRECT_TO** {"agent": "custom"}        — if user has a custom agent configured

Your visible reply when redirecting: one sentence, e.g. "Connecting you with the Sleep Coach now."
Do NOT answer the question yourself when redirecting.

Answer Doc directly (no redirect) for:
- General health profile questions (age, conditions, medications, goals)
- Questions spanning multiple domains
- Simple check-ins, small talk, or "how does this work" questions
- Cross AI territory (2+ domains at once)
"""


# ============ MEDICAL PROFILE STRUCTURE ============

PROFILE_FIELDS = {
    # Core Health Status
    "primary_concern": {
        "priority": 1,
        "category": "Core",
        "questions": [
            "What's your main health concern?",
            "What brings you here?",
            "What health issue are you dealing with?"
        ],
        "follow_ups": [
            "When did this start?",
            "Is it affecting your daily life?",
            "Seen a doctor about it?"
        ]
    },
    "health_conditions": {
        "priority": 1,
        "category": "Core",
        "questions": [
            "Any chronic health conditions?",
            "Any diagnosed medical conditions?",
            "Managing any health problems?"
        ],
        "follow_ups": [
            "When diagnosed with {condition}?",
            "Is {condition} well controlled?",
            "What treatments for {condition}?"
        ]
    },
    "medications": {
        "priority": 2,
        "category": "Treatment",
        "questions": [
            "Taking any medications?",
            "On any prescriptions?",
            "Any supplements or vitamins?"
        ],
        "follow_ups": [
            "Dosage of {medication}?",
            "How long on {medication}?",
            "Any side effects?",
            "Taking it consistently?"
        ]
    },
    "allergies": {
        "priority": 2,
        "category": "Safety",
        "questions": [
            "Any allergies?",
            "Any drugs you can't take?",
            "Past allergic reactions?"
        ],
        "follow_ups": [
            "What happens with {allergen}?",
            "How severe?"
        ]
    },
    "symptoms": {
        "priority": 1,
        "category": "Current State",
        "questions": [
            "What symptoms now?",
            "How are you feeling?",
            "Any discomforts?"
        ],
        "follow_ups": [
            "{symptom} severity 1-10?",
            "When is {symptom} worst?",
            "What makes {symptom} better?",
            "How long with {symptom}?"
        ]
    },
    
    # Lifestyle Factors
    "exercise_frequency": {
        "priority": 3,
        "category": "Lifestyle",
        "questions": [
            "How often do you exercise?",
            "Active during the week?"
        ],
        "follow_ups": [
            "What type of exercise?",
            "How long per session?",
            "What stops you from exercising more?"
        ]
    },
    "diet_type": {
        "priority": 3,
        "category": "Lifestyle",
        "questions": [
            "How's your diet?",
            "Typical eating pattern?"
        ],
        "follow_ups": [
            "Following a specific diet?",
            "Any dietary restrictions?",
            "Meals per day?",
            "Any food cravings?"
        ]
    },
    "sleep_hours": {
        "priority": 3,
        "category": "Lifestyle",
        "questions": [
            "Hours of sleep per night?",
            "Sleep quality good?"
        ],
        "follow_ups": [
            "Trouble falling or staying asleep?",
            "Wake up rested?",
            "Typical bedtime?"
        ]
    },
    "stress_level": {
        "priority": 3,
        "category": "Mental Health",
        "questions": [
            "Stress level 1-10?",
            "Feeling stressed lately?"
        ],
        "follow_ups": [
            "Main stress sources?",
            "Physical effects of stress?",
            "How do you manage stress?"
        ]
    },
    
    # Background Information
    "age": {
        "priority": 4,
        "category": "Demographics",
        "questions": [
            "How old are you?",
            "Your age?"
        ],
        "follow_ups": []
    },
    "family_history": {
        "priority": 4,
        "category": "Background",
        "questions": [
            "Any family health history?",
            "Conditions run in family?"
        ],
        "follow_ups": [
            "Who had {condition}?",
            "Age when diagnosed?"
        ]
    },
    "previous_treatments": {
        "priority": 3,
        "category": "History",
        "questions": [
            "Tried any treatments?",
            "What have you tried already?"
        ],
        "follow_ups": [
            "Did {treatment} work?",
            "Why stop {treatment}?",
            "Problems with {treatment}?"
        ]
    },
    "goals": {
        "priority": 2,
        "category": "Objectives",
        "questions": [
            "Health goals?",
            "What do you want to improve?",
            "Where in 3-6 months?"
        ],
        "follow_ups": [
            "Biggest obstacle to {goal}?",
            "Tried {goal} before?",
            "What's success?"
        ]
    }
}


# ============ CONVERSATION STAGES ============

def get_conversation_stage(profile):
    """Determine what stage of profile building we're in"""
    filled_fields = sum(1 for k, v in profile.items() if v)
    total_fields = len(PROFILE_FIELDS)
    
    if filled_fields == 0:
        return "introduction"
    elif filled_fields < 3:
        return "core_assessment"
    elif filled_fields < 8:
        return "deep_dive"
    elif filled_fields < total_fields * 0.8:
        return "comprehensive"
    else:
        return "maintenance"


def get_priority_missing_fields(profile):
    """Get missing fields sorted by priority"""
    missing = []
    for field, config in PROFILE_FIELDS.items():
        if field not in profile or not profile[field]:
            missing.append((field, config["priority"], config))
    
    # Sort by priority (lower number = higher priority)
    missing.sort(key=lambda x: x[1])
    return missing


def suggest_next_question(profile, recent_context=""):
    """Suggest the next question Doc should ask based on profile gaps"""
    missing = get_priority_missing_fields(profile)
    
    if not missing:
        return None, None
    
    # Get highest priority missing field
    field_name, priority, config = missing[0]
    
    # Choose a question from the options
    questions = config["questions"]
    question = questions[0]  # Could randomize this
    
    # If we have recent context about this topic, use follow-up
    if recent_context and field_name in recent_context.lower():
        # Try to extract what they mentioned
        if config["follow_ups"]:
            question = config["follow_ups"][0]
    
    return field_name, question


def generate_follow_up_questions(field_name, field_value, profile):
    """Generate follow-up questions for a field that was just filled"""
    if field_name not in PROFILE_FIELDS:
        return []
    
    config = PROFILE_FIELDS[field_name]
    follow_ups = config.get("follow_ups", [])
    
    # Customize follow-ups based on what they said
    customized = []
    for q in follow_ups:
        if "{" in q:
            # Replace placeholders
            if "{condition}" in q and isinstance(field_value, str):
                customized.append(q.replace("{condition}", field_value))
            elif "{medication}" in q and isinstance(field_value, str):
                customized.append(q.replace("{medication}", field_value))
            elif "{symptom}" in q and isinstance(field_value, str):
                customized.append(q.replace("{symptom}", field_value))
            elif "{treatment}" in q and isinstance(field_value, str):
                customized.append(q.replace("{treatment}", field_value))
            elif "{allergen}" in q and isinstance(field_value, str):
                customized.append(q.replace("{allergen}", field_value))
            elif "{goal}" in q and isinstance(field_value, str):
                customized.append(q.replace("{goal}", field_value))
        else:
            customized.append(q)
    
    return customized[:2]  # Return max 2 follow-ups


# ============ PROMPT BUILDING ============

STAGE_INSTRUCTIONS = {
    "introduction": """
## STAGE: Introduction
Ask what brings them here. Update profile with their answer, then ask focused follow-ups.
""",
    "core_assessment": """
## STAGE: Core Assessment  
Focus: Current conditions, medications, allergies, symptoms.
Update profile as you gather each piece of info. Ask directly about missing fields.
""",
    "deep_dive": """
## STAGE: Deep Dive
Focus: Lifestyle (diet, exercise, sleep, stress), treatment history, family history.
Keep updating profile. One question at a time.
""",
    "comprehensive": """
## STAGE: Filling Gaps
Look at STATUS section for missing fields. Ask about them. Update profile with answers.
""",
    "maintenance": """
## STAGE: Ongoing Support
Profile complete. Check on progress, changes, and goals. Update profile if anything changes.
"""
}


def build_doc_prompt(user_input, profile, recent_transcript="", username="Guest", agent_context=None):
    """Build the complete prompt for Doc.

    agent_context: optional string containing a specialist agent's response,
                   pre-fetched by handlers.py when a previous Doc turn emitted
                   **CALL_AGENT**.  Doc uses this to enrich its answer.
    """

    # Determine conversation stage
    stage = get_conversation_stage(profile)
    stage_instruction = STAGE_INSTRUCTIONS.get(stage, STAGE_INSTRUCTIONS["introduction"])

    # Get what we should ask about next
    missing_fields = get_priority_missing_fields(profile)

    # Build profile context
    profile_summary = json.dumps(profile, indent=2) if profile else "{empty}"

    # Build missing fields list
    if missing_fields:
        missing_list = ", ".join([f[0] for f in missing_fields[:5]])
        missing_text = f"Missing key information: {missing_list}"
    else:
        missing_text = "Profile is complete"

    # Build recent context
    recent_lines = recent_transcript.strip().split('\n')[-8:] if recent_transcript else []
    recent_text = '\n'.join(recent_lines) if recent_lines else "(This is the start of the conversation)"

    # Agent context section
    agent_section = ""
    if agent_context:
        agent_section = f"""
## AGENT CONTEXT
A specialist agent has provided the following insight for this topic.
Weave it naturally into your reply — do NOT quote it verbatim or attribute it to an agent.
Treat it as your own synthesized knowledge:

{agent_context}
"""

    # Construct the full prompt
    prompt = f"""{CORE_IDENTITY}

{AGENT_DISPATCH_INSTRUCTIONS}

{stage_instruction}

## CURRENT PROFILE
{profile_summary}

## STATUS
{missing_text}

## RECENT CONVERSATION
{recent_text}
{agent_section}
## CRITICAL INSTRUCTIONS

1. **CHECK THE CURRENT PROFILE** — Don't ask about info you already have
2. **UPDATE PROFILE WHEN USER SHARES INFO** — Always emit **PROFILE_UPDATE** markers
3. **CALL AN AGENT IF APPROPRIATE** — Emit **CALL_AGENT** for specialist topics
4. **ONE QUESTION AT A TIME** — End with one short, focused question

## PROFILE UPDATE SYNTAX
Emit every time user shares health info:

**PROFILE_UPDATE**
{{"field": "value"}}

Examples:
- {{"primary_concern": "managing diabetes"}}
- {{"medications": "+metformin 500mg twice daily"}} (use + to append)
- {{"sleep_hours": "6"}}
- {{"age": "34"}}

Available fields: {', '.join(PROFILE_FIELDS.keys())}

---
User ({username}): {user_input}

Doc (coordinate, update profile, help the user):"""

    return prompt


# ============ SUGGESTED NEXT QUESTION ============

def get_next_probing_question(profile, last_field_updated=None):
    """Get a suggested follow-up question based on context"""
    
    # If we just updated a field, suggest a follow-up for that field
    if last_field_updated and last_field_updated in PROFILE_FIELDS:
        field_value = profile.get(last_field_updated)
        follow_ups = generate_follow_up_questions(last_field_updated, field_value, profile)
        if follow_ups:
            return follow_ups[0]
    
    # Otherwise, suggest next missing field question
    field_name, question = suggest_next_question(profile)
    return question
