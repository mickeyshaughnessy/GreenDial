"""
Utilities Module

Domain helpers live here. Generic LLM completion is provided by the sibling
ListeningAI package (listening_ai.llm) — this module is a thin adapter so
existing GreenDial call sites (handlers, agent_runner, scripts) keep working.
"""
from datetime import datetime, timedelta

import config

# ---------------------------------------------------------------------------
# Domain helper (health profile history) — stays in GreenDial
# ---------------------------------------------------------------------------

def summarize_history(user, days=14, max_fields=8):
    """Compact text summary of a user's profile_history for LLM context.

    One line per tracked field: entry count, average (numeric) or latest value.
    Returns '' if there is no history in the window.
    """
    history = (user or {}).get('profile_history', {})
    if not history:
        return ""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    lines = []
    for field, entries in list(history.items())[:max_fields]:
        recent = [e for e in entries if e.get('ts', '') >= cutoff]
        if not recent:
            continue
        values = [e.get('v') for e in recent]
        nums = []
        for v in values:
            try:
                nums.append(float(str(v).split()[0]))
            except (ValueError, IndexError):
                pass
        if nums and len(nums) == len(values):
            avg = sum(nums) / len(nums)
            lines.append(f"- {field}: {len(recent)} entries, avg {avg:.1f}, latest {values[-1]}")
        else:
            lines.append(f"- {field}: {len(recent)} entries, latest \"{values[-1]}\"")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ListeningAI LLM adapter
# ---------------------------------------------------------------------------

_LLM_READY = False


def _ensure_llm_configured():
    """Point ListeningAI settings at GreenDial's config (once per process)."""
    global _LLM_READY
    if _LLM_READY:
        return True
    try:
        # Prefer the full bridge (Spaces store + site name) when available.
        # Import host config identity via listening_bridge (it avoids path shadowing).
        import listening_bridge
        listening_bridge.ensure_configured()
        _LLM_READY = True
        return True
    except Exception as e:
        print(f"[LLM] listening_bridge configure failed ({e}); trying Settings only")
    try:
        # Import GreenDial config by file path name: caller's package, not ListeningAI's
        from listening_ai import Settings, configure
        configure(Settings.from_config_module(config))
        _LLM_READY = True
        return True
    except Exception as e:
        print(f"[LLM] listening_ai configure failed: {e}")
        return False


def get_last_model_used():
    """Model id from the last successful ListeningAI completion."""
    try:
        from listening_ai import get_last_model_used as _glm
        return _glm()
    except Exception:
        return None


def completion(prompt, model=None, temperature=None, max_tokens=None, system_prompt=None, use_fallback=False):
    """
    Call OpenRouter via ListeningAI with sequential model fallback.

    Signature preserved for handlers / agent_runner / translate_i18n.
    """
    if not _ensure_llm_configured():
        return "I'm having trouble connecting. Please configure an API key."
    try:
        from listening_ai import completion as lai_completion
        text = lai_completion(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            use_fallback=use_fallback,
        )
        # Map ListeningAI's generic apology to GreenDial's familiar wording
        if text and text.startswith("Sorry, I couldn't reach"):
            return "I'm having trouble responding right now. Please try again."
        return text
    except Exception as e:
        print(f"[LLM] completion error: {e}")
        return "I'm having trouble responding right now. Please try again."


def completion_with_tools(messages, tools=None, system_prompt=None, model=None,
                          temperature=None, max_tokens=None):
    """
    LLM completion with tool/function calling via ListeningAI.

    Returns the ListeningAI response dict, including GreenDial-compat keys
    ``tool_uses`` and ``raw_content`` (aliases of tool_calls / raw_message).
    """
    if not _ensure_llm_configured():
        primary = model or getattr(config, "OPENROUTER_TOOLS_MODEL", "")
        return {
            "stop_reason": "end_turn",
            "text": None,
            "tool_uses": [],
            "tool_calls": [],
            "raw_content": None,
            "raw_message": None,
            "model_used": primary,
            "error": "listening_ai_unavailable",
        }
    try:
        from listening_ai import call_llm_with_tools
        return call_llm_with_tools(
            messages=messages,
            tools=tools,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        print(f"[LLM Tools] error: {e}")
        primary = model or getattr(config, "OPENROUTER_TOOLS_MODEL", "")
        return {
            "stop_reason": "end_turn",
            "text": None,
            "tool_uses": [],
            "tool_calls": [],
            "raw_content": None,
            "raw_message": None,
            "model_used": primary,
            "error": str(e),
        }


def two_stage_completion(user_input, username="Guest", profile=None, recent_transcript="", settings=None):
    """
    Two-stage LLM completion (legacy helper):
    1. Supervisor analyzes context and builds dynamic system prompt
    2. Doc responds using the supervisor's instructions
    """
    from prompts import supervisor

    profile = profile or {}
    settings = settings or {}

    print("[LLM] Stage 1: Supervisor analyzing...")
    sup_prompt = supervisor.build_supervisor_prompt(user_input, profile, recent_transcript, settings)

    supervisor_response = completion(
        prompt=sup_prompt["user"],
        system_prompt=sup_prompt["system"],
        temperature=0.3,
        max_tokens=300,
    )

    sup_output = supervisor.parse_supervisor_response(supervisor_response)
    print(f"[LLM] Supervisor: length={sup_output['length']}, tone={sup_output['tone']}, focus={sup_output['focus'][:50]}")

    print("[LLM] Stage 2: Doc responding...")
    doc_system = supervisor.build_doc_prompt(sup_output, username, profile, recent_transcript, settings)

    return completion(
        prompt=user_input,
        system_prompt=doc_system,
        temperature=0.8,
        max_tokens=300,
    )
