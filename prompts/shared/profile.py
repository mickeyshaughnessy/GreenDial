"""
Canonical PROFILE_UPDATE syntax and field registry.
Import this instead of defining update syntax per-agent or in doc_v2.
"""

PROFILE_UPDATE_SYNTAX = """To record what the user shares, emit:

**PROFILE_UPDATE**
{"field": "value"}

- Set:    {"age": "44"}
- Append: {"medications": "+metformin 500mg"}  (+ prefix adds to existing)
- Delete: {"allergies": null}
- Nested: {"vitals": {"bp": "120/80"}}

Only save what the user explicitly stated. Don't infer."""


# Unified field registry (union across all agents and Doc)
ALL_PROFILE_FIELDS = frozenset({
    # Core
    "primary_concern", "health_conditions", "medications", "allergies",
    "symptoms", "age", "height", "goals", "notes",
    "location", "previous_treatments",
    # Diet
    "diet_type", "dietary_restrictions", "nutrition_goals", "meal_frequency",
    "food_allergies", "supplements",
    # Exercise
    "exercise_frequency", "exercise_type", "fitness_goals", "exercise_limitations",
    "preferred_workout_time", "fitness_level",
    # Sleep
    "sleep_quality", "sleep_issues", "bedtime", "wake_time",
    "sleep_environment", "sleep_aids", "sleep_disorders",
    # Mental health
    "mental_health_concerns", "therapy_status", "mood_notes",
    "mindfulness_practice", "mental_health_history", "coping_strategies",
    # Relationships
    "relationship_status", "social_support", "loneliness_level",
    "relationship_goals", "family_situation", "caregiver_status", "social_activities",
    # Environment
    "living_environment", "environmental_concerns", "workplace_setup",
    "known_exposures", "outdoor_access", "climate_region",
    # Protect / immunity / prevention
    "immune_concerns", "allergy_history", "autoimmune_conditions",
    "vaccination_status", "gut_health_notes", "family_history", "smoking_status",
    "alcohol_use", "last_checkup", "screenings_completed", "screenings_due",
    "cardiovascular_risk_factors",
})
