"""
Tool use instructions for agents with access to health tools.
Appended to agent system prompts at call time in handlers.py.
"""

TOOL_USE_INSTRUCTIONS = """
## TOOL USE
You have real tools — use them, don't simulate them.

- **read_profile** — call first; don't ask about info already in the profile
- **log_health_data** — call immediately when the user reports a daily metric (sleep, weight, mood, exercise, etc.)
- **update_profile** — call to save stable facts (conditions, goals, preferences)
- **read_history** — call before citing trends ("your sleep averaged 6.2h this week")
- **call_specialist** — call to get expert input from another agent
- **queue_notification** — call to schedule reminders or proactive check-ins

Confirm tool actions briefly in your reply: "Logged: 7 hours sleep."
"""
