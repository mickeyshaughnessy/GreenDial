"""
Cross-conversation style detection and mirroring instructions.

Analyzes recent user messages to find the dominant communication pattern,
then returns a system-prompt-level instruction for matching it.
"""
import re

_CASUAL_WORDS = {
    'hey', 'hi', 'yeah', 'yep', 'nope', 'nah', 'ok', 'okay',
    'lol', 'tbh', 'idk', 'omg', 'btw', 'gonna', 'wanna', 'kinda',
    'sorta', 'bc', 'cuz', 'tho', 'haha', 'hm', 'hmm', 'ugh',
}


def _extract_user_messages(transcript):
    """Pull user-turn text from the stored transcript format."""
    lines = []
    for line in (transcript or '').split('\n'):
        m = re.search(r'\] User: (.+)', line)
        if m:
            lines.append(m.group(1).strip())
    return lines


def detect_style(current_text, recent_transcript=""):
    """
    Return (length_style, tone) based on cross-conversation word counts.

    length_style: 'short' | 'medium' | 'long'
    tone:         'casual' | 'neutral'
    """
    messages = _extract_user_messages(recent_transcript)
    if current_text:
        messages.append(current_text.strip())
    if not messages:
        return 'medium', 'neutral'

    counts = [len(m.split()) for m in messages if m]
    avg = sum(counts) / len(counts)

    if avg <= 6:
        length = 'short'
    elif avg <= 25:
        length = 'medium'
    else:
        length = 'long'

    all_words = set(' '.join(messages).lower().split())
    tone = 'casual' if all_words & _CASUAL_WORDS else 'neutral'

    return length, tone


_INSTRUCTIONS = {
    ('short', 'casual'):  "User writes briefly and casually. Match them: 1-2 sentences, conversational, no bullet lists.",
    ('short', 'neutral'): "User writes briefly. Match: 1-2 sentences max, no padding.",
    ('medium', 'casual'): "User writes conversationally. Match: 2-3 sentences, natural tone.",
    ('medium', 'neutral'): "User writes concisely. Match: 2-4 sentences, clear and direct.",
    ('long', 'casual'):   "User writes at length and conversationally. Match their depth: up to 5 sentences.",
    ('long', 'neutral'):  "User writes detailed messages. Match: 3-5 sentences, organized.",
}


def build_style_instruction(current_text, recent_transcript=""):
    """Single-line style instruction for injection into a system prompt."""
    key = detect_style(current_text, recent_transcript)
    return _INSTRUCTIONS.get(key, "Match the user's message length and tone.")
