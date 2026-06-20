"""
Utilities Module
LLM completion via OpenRouter API
"""
import json
import requests
import config
from datetime import datetime, timedelta

# Module-level tracker — set after each successful completion call
_last_used_model = None


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


def get_last_model_used():
    return _last_used_model


_HEADERS = {
    'Authorization': None,  # filled at call time
    'Content-Type': 'application/json',
    'HTTP-Referer': 'https://greendial.org',
    'X-Title': 'GreenDial',
}

def _api_headers():
    return {**_HEADERS, 'Authorization': f"Bearer {config.OPENROUTER_API_KEY}"}


def _build_sequence(primary, fallback_key='OPENROUTER_FALLBACK_MODELS'):
    """Return [primary] + deduplicated fallbacks in order."""
    fallbacks = getattr(config, fallback_key, getattr(config, 'OPENROUTER_FALLBACK_MODELS', []))
    seen = {primary}
    result = [primary]
    for m in fallbacks:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _completion_once(model, messages, temperature, max_tokens):
    """Single attempt against one model. Returns (text, error_str)."""
    global _last_used_model
    payload = {'model': model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens}
    try:
        print(f"[LLM] Calling {model}...")
        resp = requests.post(config.OPENROUTER_API_URL, headers=_api_headers(), json=payload, timeout=30)

        if resp.status_code == 429:
            print(f"[LLM] Rate limited on {model}")
            return None, "rate_limited"

        if resp.status_code >= 400:
            snippet = resp.text[:200]
            print(f"[LLM] Error {resp.status_code} from {model}: {snippet}")
            try:
                with open("/tmp/llm_debug.log", "a") as f:
                    f.write(f"{datetime.utcnow().isoformat()} {model} {resp.status_code}: {snippet}\n")
            except Exception:
                pass
            return None, f"http_{resp.status_code}"

        result = resp.json()
        choices = result.get('choices') or []
        if choices:
            _last_used_model = model
            return choices[0]['message']['content'], None

        print(f"[LLM] No choices from {model}: {result}")
        return None, "no_choices"

    except requests.exceptions.Timeout:
        print(f"[LLM] Timeout on {model}")
        return None, "timeout"
    except requests.exceptions.RequestException as e:
        print(f"[LLM] Connection error on {model}: {e}")
        return None, "connection_error"
    except Exception as e:
        print(f"[LLM] Unexpected error on {model}: {e}")
        return None, str(e)


def completion(prompt, model=None, temperature=None, max_tokens=None, system_prompt=None, use_fallback=False):
    """Call OpenRouter with automatic sequential fallback through OPENROUTER_FALLBACK_MODELS."""
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    if not config.OPENROUTER_API_KEY:
        print("[LLM] No API key configured")
        return "I'm having trouble connecting. Please configure an API key."

    primary = model or (config.OPENROUTER_FALLBACK_MODEL if use_fallback else config.OPENROUTER_MODEL)
    sequence = _build_sequence(primary)

    for attempt, m in enumerate(sequence):
        text, err = _completion_once(m, messages, temperature, max_tokens)
        if text is not None:
            if attempt > 0:
                print(f"[LLM] Succeeded on fallback {m} (attempt {attempt+1})")
            return text
        more = "trying next" if attempt + 1 < len(sequence) else "no more fallbacks"
        print(f"[LLM] {m} failed ({err}), {more}")

    return "I'm having trouble responding right now. Please try again."


def completion_with_tools(messages, tools=None, system_prompt=None, model=None,
                          temperature=None, max_tokens=None):
    """
    LLM completion with tool/function calling support (OpenAI-compatible format).

    Tries OPENROUTER_TOOLS_MODEL first, then OPENROUTER_TOOLS_FALLBACK_MODELS in order.
    Retries on 429, 4xx, timeout, and connection errors — does NOT recurse.

    Returns dict:
        {
          "stop_reason": "end_turn" | "tool_calls",
          "text":        str | None,
          "tool_uses":   [{"id","name","input"}, ...],
          "raw_content": dict,
          "model_used":  str,
          "error":       str | None
        }
    """
    global _last_used_model

    primary = model or config.OPENROUTER_TOOLS_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    sequence = _build_sequence(primary, fallback_key='OPENROUTER_TOOLS_FALLBACK_MODELS')

    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    def _err(msg):
        return {"stop_reason": "end_turn", "text": None, "tool_uses": [], "raw_content": None,
                "model_used": primary, "error": msg}

    last_err = "unknown"
    for attempt, m in enumerate(sequence):
        try:
            print(f"[LLM Tools] Calling {m} (tools={len(tools or [])}, attempt={attempt+1}/{len(sequence)})...")
            payload = {
                "model": m,
                "messages": all_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            resp = requests.post(config.OPENROUTER_API_URL, headers=_api_headers(), json=payload, timeout=45)

            if resp.status_code == 429:
                print(f"[LLM Tools] Rate limited on {m}")
                last_err = "rate_limited"
                continue

            if resp.status_code >= 400:
                print(f"[LLM Tools] Error {resp.status_code} on {m}: {resp.text[:200]}")
                last_err = f"http_{resp.status_code}"
                continue

            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            msg_obj = choice.get("message", {})

            if not choice or not msg_obj:
                print(f"[LLM Tools] No choices from {m}: {data}")
                last_err = "no_choices"
                continue

            text = msg_obj.get("content")
            raw_tool_calls = msg_obj.get("tool_calls") or []
            finish_reason = choice.get("finish_reason", "stop")

            tool_uses = []
            for tc in raw_tool_calls:
                try:
                    func = tc.get("function", {})
                    args = func.get("arguments", "{}")
                    tool_uses.append({
                        "id": tc.get("id", f"tc_{len(tool_uses)}"),
                        "name": func.get("name", ""),
                        "input": json.loads(args) if isinstance(args, str) else args,
                    })
                except Exception as e:
                    print(f"[LLM Tools] Could not parse tool call: {e}")

            raw_content = {"role": "assistant", "content": text}
            if raw_tool_calls:
                raw_content["tool_calls"] = raw_tool_calls

            _last_used_model = m
            if attempt > 0:
                print(f"[LLM Tools] Succeeded on fallback {m} (attempt {attempt+1})")

            return {
                "stop_reason": "tool_calls" if (finish_reason == "tool_calls" or tool_uses) else "end_turn",
                "text": text,
                "tool_uses": tool_uses,
                "raw_content": raw_content,
                "model_used": m,
                "error": None,
            }

        except requests.exceptions.Timeout:
            print(f"[LLM Tools] Timeout on {m}")
            last_err = "timeout"
        except requests.exceptions.RequestException as e:
            print(f"[LLM Tools] Connection error on {m}: {e}")
            last_err = "connection_error"
        except Exception as e:
            print(f"[LLM Tools] Unexpected error on {m}: {e}")
            last_err = str(e)

        if attempt + 1 < len(sequence):
            print(f"[LLM Tools] {m} failed ({last_err}), trying next")

    print(f"[LLM Tools] All {len(sequence)} models exhausted, last error: {last_err}")
    return _err(last_err)


def two_stage_completion(user_input, username="Guest", profile=None, recent_transcript="", settings=None):
    """
    Two-stage LLM completion:
    1. Supervisor analyzes context and builds dynamic system prompt
    2. Doc responds using the supervisor's instructions
    
    Returns:
        Doc's response string
    """
    from prompts import supervisor
    
    profile = profile or {}
    settings = settings or {}
    
    # Stage 1: Supervisor
    print("[LLM] Stage 1: Supervisor analyzing...")
    sup_prompt = supervisor.build_supervisor_prompt(user_input, profile, recent_transcript, settings)
    
    supervisor_response = completion(
        prompt=sup_prompt["user"],
        system_prompt=sup_prompt["system"],
        temperature=0.3,  # Lower temp for more consistent JSON
        max_tokens=300
    )
    
    # Parse supervisor output
    sup_output = supervisor.parse_supervisor_response(supervisor_response)
    print(f"[LLM] Supervisor: length={sup_output['length']}, tone={sup_output['tone']}, focus={sup_output['focus'][:50]}")
    
    # Stage 2: Doc
    print("[LLM] Stage 2: Doc responding...")
    doc_system = supervisor.build_doc_prompt(sup_output, username, profile, recent_transcript, settings)
    
    doc_response = completion(
        prompt=user_input,
        system_prompt=doc_system,
        temperature=0.8,
        max_tokens=300
    )
    
    return doc_response
