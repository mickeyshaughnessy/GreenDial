"""
Occasional check-ins for short-lived / changing conditions.

Appended to Doc and specialist system prompts so agents ask for updates
(travel, cold, injury, etc.) without re-probing stable facts every turn.
"""

TRANSIENT_CHECK_IN = """
## TRANSIENT UPDATES (occasional)
About once every few turns when it fits naturally — not every message — ask a brief
check-in about short-lived conditions that may have changed:
- travel or temporary environment change
- cold, flu, allergy flare, or other acute illness
- injury, pain flare, or recovery status (e.g. knee)
- big stress week, sleep disruption, or schedule chaos
- new/temporary meds or paused meds

If they share something, save it with update_profile (or PROFILE_UPDATE). Prefer
updating transient fields over re-asking age, long-term goals, or fixed conditions.
Keep the ask to one short question; never lecture.
"""

# Free-suggestion templates for profile + product improvement (non-bounty)
GREEN_DIAL_IMPROVE_SUGGESTIONS = [
    "Want GreenDial to work better for you? Tell Doc what's missing — or leave a note in Feedback.",
    "How could Doc help more usefully? Chat about it, or drop a suggestion in Feedback.",
    "Anything awkward or broken in GreenDial? Talk to Doc about it, or post in Feedback.",
]

PROFILE_UPDATE_SUGGESTIONS = [
    "Any short-term changes I should note — travel, a cold, an injury? Chat with Doc to update your health profile.",
    "Is anything temporary going on (sick day, travel, sore joint)? Update your profile with Doc so advice stays accurate.",
    "Quick profile check: anything new this week — stress spike, sleep crash, or recovery? Tell Doc.",
]
