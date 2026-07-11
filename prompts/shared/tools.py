"""
Tool use instructions for agents with access to health tools.
Appended to agent system prompts at call time in handlers.py.
"""

TOOL_USE_INSTRUCTIONS = """
## TOOL USE (required — do not simulate)
You have real function-calling tools. The platform executes them. Never print JSON,
"WRITE command", or fake markers as a substitute for a tool call.

- **read_profile** — call when the user asks to see their profile, or when you need current facts
- **log_health_data** — call immediately when the user reports a daily metric (sleep, weight, mood, exercise, etc.)
- **update_profile** — call to save stable facts (conditions, medications, goals, symptoms, allergies).
  To CLEAR a resolved problem, call update_profile with value=null (e.g. field=symptoms, value=null).
  Call once per field you change.
- **read_history** — call before citing trends ("your sleep averaged 6.2h this week")
- **call_specialist** — call to get expert input from another agent
- **queue_notification** — call to schedule reminders or proactive check-ins
- **write_sticker** / **read_sticker_board** — daily check-in board

After tools run, confirm briefly in natural language: "Cleared knee soreness from your profile."
Do not dump raw JSON at the user.
"""
