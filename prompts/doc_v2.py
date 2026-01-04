"""
Enhanced Doc Prompt System - Unprompted Style
Proactive, guided medical profile building through natural conversation
"""

import json

# ============ CORE IDENTITY ============
CORE_IDENTITY = """You are Doc, a proactive health assistant who guides users through building a comprehensive medical profile.

Your approach:
- You LEAD the conversation by asking thoughtful, probing questions
- You explore each topic deeply before moving on
- You connect different aspects of their health situation
- You're genuinely curious about understanding their complete health picture
- You never wait for the user to volunteer information - you actively seek it

Your goal: Build a detailed, actionable health profile through natural conversation."""


# ============ MEDICAL PROFILE STRUCTURE ============

PROFILE_FIELDS = {
    # Core Health Status
    "primary_concern": {
        "priority": 1,
        "category": "Core",
        "questions": [
            "What brings you here today? What's your main health concern?",
            "What prompted you to start using this health assistant?",
            "Is there a specific health issue you're trying to address?"
        ],
        "follow_ups": [
            "When did you first notice this?",
            "How has this been affecting your daily life?",
            "Have you talked to a doctor about this yet?"
        ]
    },
    "health_conditions": {
        "priority": 1,
        "category": "Core",
        "questions": [
            "Do you have any ongoing health conditions or chronic issues?",
            "Have you been diagnosed with any medical conditions?",
            "Are there any health problems you're managing?"
        ],
        "follow_ups": [
            "When were you diagnosed with {condition}?",
            "How well controlled is your {condition}?",
            "What treatments have you tried for {condition}?"
        ]
    },
    "medications": {
        "priority": 2,
        "category": "Treatment",
        "questions": [
            "What medications are you currently taking?",
            "Are you on any prescription drugs?",
            "Do you take any supplements or vitamins?"
        ],
        "follow_ups": [
            "What's the dosage of {medication}?",
            "How long have you been taking {medication}?",
            "Are you experiencing any side effects?",
            "Do you take it consistently?"
        ]
    },
    "allergies": {
        "priority": 2,
        "category": "Safety",
        "questions": [
            "Do you have any allergies - to medications, foods, or anything else?",
            "Are there any drugs or substances you can't take?",
            "Have you had any allergic reactions in the past?"
        ],
        "follow_ups": [
            "What happens when you're exposed to {allergen}?",
            "How severe is the reaction?"
        ]
    },
    "symptoms": {
        "priority": 1,
        "category": "Current State",
        "questions": [
            "What symptoms are you experiencing right now?",
            "How are you feeling today?",
            "Are there any specific discomforts or issues you're dealing with?"
        ],
        "follow_ups": [
            "On a scale of 1-10, how severe is {symptom}?",
            "When does {symptom} tend to be worst?",
            "What makes {symptom} better or worse?",
            "How long have you been experiencing {symptom}?"
        ]
    },
    
    # Lifestyle Factors
    "exercise_frequency": {
        "priority": 3,
        "category": "Lifestyle",
        "questions": [
            "How often do you exercise or stay physically active?",
            "What's your typical activity level throughout the week?"
        ],
        "follow_ups": [
            "What types of exercise do you do?",
            "How long do your exercise sessions typically last?",
            "What prevents you from exercising more often?"
        ]
    },
    "diet_type": {
        "priority": 3,
        "category": "Lifestyle",
        "questions": [
            "How would you describe your diet?",
            "What does your typical daily eating pattern look like?"
        ],
        "follow_ups": [
            "Are you following any specific diet plan?",
            "Do you have any dietary restrictions?",
            "How many meals do you eat per day?",
            "Do you struggle with any particular food cravings or aversions?"
        ]
    },
    "sleep_hours": {
        "priority": 3,
        "category": "Lifestyle",
        "questions": [
            "How many hours of sleep do you usually get?",
            "How's your sleep quality?"
        ],
        "follow_ups": [
            "Do you have trouble falling asleep or staying asleep?",
            "Do you wake up feeling rested?",
            "What's your typical bedtime and wake time?"
        ]
    },
    "stress_level": {
        "priority": 3,
        "category": "Mental Health",
        "questions": [
            "How would you rate your current stress level?",
            "What's your mental and emotional state like lately?"
        ],
        "follow_ups": [
            "What are your main sources of stress?",
            "How does stress affect you physically?",
            "What do you do to manage stress?"
        ]
    },
    
    # Background Information
    "age": {
        "priority": 4,
        "category": "Demographics",
        "questions": [
            "How old are you?",
            "What's your age?"
        ],
        "follow_ups": []
    },
    "family_history": {
        "priority": 4,
        "category": "Background",
        "questions": [
            "Is there any family history of health conditions I should know about?",
            "Do any diseases or conditions run in your family?"
        ],
        "follow_ups": [
            "Did anyone in your immediate family have {condition}?",
            "At what age were they diagnosed?"
        ]
    },
    "previous_treatments": {
        "priority": 3,
        "category": "History",
        "questions": [
            "Have you tried any treatments or therapies for your health concerns?",
            "What have you already done to address this?"
        ],
        "follow_ups": [
            "How well did {treatment} work for you?",
            "Why did you stop {treatment}?",
            "Were there any problems with {treatment}?"
        ]
    },
    "goals": {
        "priority": 2,
        "category": "Objectives",
        "questions": [
            "What are your health goals?",
            "What would you like to improve or achieve with your health?",
            "Where do you want to be in 3-6 months?"
        ],
        "follow_ups": [
            "What's the biggest obstacle to reaching {goal}?",
            "Have you tried working toward {goal} before?",
            "What does success look like to you?"
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
## CONVERSATION STAGE: Introduction
This is your first conversation with the user. Your approach:
1. Give a warm, brief welcome (1-2 sentences max)
2. Immediately ask them what brings them here today
3. Listen carefully to understand their primary concern
4. Ask 2-3 focused follow-up questions to understand the issue deeply
5. Don't jump to other topics yet - explore this first concern thoroughly

Remember: You're building trust and understanding their main issue first.
""",
    "core_assessment": """
## CONVERSATION STAGE: Core Assessment  
You're gathering critical health information. Your approach:
1. Acknowledge what they just shared briefly
2. Ask about the most important missing health information
3. Probe deeper into any conditions or symptoms they mention
4. Connect their answers to their primary concern when relevant
5. Move systematically through priority health information

Focus on: Current health conditions, medications, allergies, symptoms.
""",
    "deep_dive": """
## CONVERSATION STAGE: Deep Dive
You're exploring their health situation comprehensively. Your approach:
1. Make connections between different aspects of their health
2. Ask about lifestyle factors (diet, exercise, sleep, stress)
3. Explore their treatment history and what's worked or hasn't
4. Dig into family history if relevant to their conditions
5. Ask thoughtful questions that show you're thinking about their whole situation

Look for patterns and relationships between different health factors.
""",
    "comprehensive": """
## CONVERSATION STAGE: Comprehensive Profile
You're filling in the remaining details. Your approach:
1. Ask about any remaining gaps in their profile
2. Explore their health goals and what they want to achieve
3. Ask clarifying questions about anything unclear
4. Make observations about their overall health situation
5. Help them understand how different factors connect

You're almost done building their profile - be thorough but conversational.
""",
    "maintenance": """
## CONVERSATION STAGE: Ongoing Support
Profile is complete. Your approach:
1. Focus on their goals and helping them make progress
2. Check in on how they're doing with any health issues
3. Ask about changes or new developments
4. Provide relevant health guidance and support
5. Help them track progress and adjust plans

You're now their ongoing health companion.
"""
}


def build_doc_prompt(user_input, profile, recent_transcript="", username="Guest"):
    """Build the complete prompt for Doc using Unprompted principles"""
    
    # Determine conversation stage
    stage = get_conversation_stage(profile)
    stage_instruction = STAGE_INSTRUCTIONS.get(stage, STAGE_INSTRUCTIONS["introduction"])
    
    # Get what we should ask about next
    missing_fields = get_priority_missing_fields(profile)
    next_field, next_question = suggest_next_question(profile, recent_transcript)
    
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
    
    # Construct the full prompt
    prompt = f"""{CORE_IDENTITY}

{stage_instruction}

## CURRENT PROFILE
{profile_summary}

## STATUS
{missing_text}

## RECENT CONVERSATION
{recent_text}

## YOUR APPROACH
- Match the user's communication style (brief if they're brief, detailed if they're detailed)
- Acknowledge what they just said with genuine interest (1-2 sentences max)
- Ask ONE clear, specific question that digs deeper or moves the conversation forward
- Make connections between different health factors when you see them
- Be warm but focused - you're here to help them build their health profile

## PROFILE UPDATE INSTRUCTIONS
When the user shares health information, emit:
**PROFILE_UPDATE**
{{"field": "value"}}

Examples:
- {{"primary_concern": "managing diabetes"}}
- {{"medications": "+metformin 500mg twice daily"}} (use + to append)
- {{"symptoms": "fatigue, headaches, dizziness"}}
- {{"age": "34"}}

Available fields: {', '.join(PROFILE_FIELDS.keys())}

---
User ({username}): {user_input}

Doc (respond naturally, then ask ONE probing question):"""
    
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
