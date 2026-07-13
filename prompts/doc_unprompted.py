"""
Doc unprompted check-in prompts.

Used by GET /Doc when ProactivePolicy allows a message. Keep replies short —
this is a proactive nudge, not a full consultation turn.
"""
import json

SYSTEM_PROMPT = """You are Doc, GreenDial's primary health coordinator.
You are sending ONE unprompted check-in message to a user who has not just messaged you.

Rules:
- At most 2 short sentences (~40 words total). Listen more than you speak.
- Prefer a concrete reference to something in their profile, recent chat, stickers, or history.
- Friendly, specific, actionable — not a lecture or multi-question survey.
- Do NOT dump JSON, call tools as text, or invent medical diagnoses.
- Do NOT start with "As an AI" or generic wellness fluff.
- If there is truly nothing useful to say, reply with exactly: NOTHING
"""


def build_unprompted_prompt(
    *,
    username: str = "friend",
    profile: dict = None,
    recent_transcript: str = "",
    history_summary: str = "",
    sticker_context: str = None,
    doc_style: str = "questioning",
) -> str:
    profile = profile or {}
    profile_str = json.dumps(profile, indent=2) if profile else "{}"
    transcript = (recent_transcript or "").strip() or "(no recent chat)"
    history = (history_summary or "").strip() or "(none)"
    stickers = (sticker_context or "").strip() or "(none)"
    style = (doc_style or "questioning").strip()

    return (
        f"User: {username}\n"
        f"Doc style preference: {style}\n\n"
        f"## PROFILE\n{profile_str}\n\n"
        f"## RECENT DOC CHAT\n{transcript}\n\n"
        f"## TRACKED HISTORY\n{history}\n\n"
        f"## STICKER / CHECK-IN CONTEXT\n{stickers}\n\n"
        "Write one unprompted Doc message for this user right now "
        "(or NOTHING if you should stay quiet)."
    )
