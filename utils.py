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


def completion(prompt, model=None, temperature=None, max_tokens=None, system_prompt=None, use_fallback=False):
    """
    Call OpenRouter API for LLM completion with fallback support.
    
    Args:
        prompt: User message content
        model: Model to use (default from config)
        temperature: Sampling temperature
        max_tokens: Max response tokens
        system_prompt: Optional system message (for two-stage calls)
        use_fallback: If True, use paid fallback model
    """
    # Use fallback model if requested, otherwise use primary free model
    if model is None:
        model = config.OPENROUTER_FALLBACK_MODEL if use_fallback else config.OPENROUTER_MODEL
    
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    
    # Build messages array
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    if not config.OPENROUTER_API_KEY:
        print("[LLM] No API key configured")
        return "I'm having trouble connecting. Please configure an API key."
    
    headers = {
        'Authorization': f"Bearer {config.OPENROUTER_API_KEY}",
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://greendial.org',
        'X-Title': 'GreenDial'
    }
    
    payload = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens
    }
    
    try:
        global _last_used_model
        print(f"[LLM] Calling {model}...")
        response = requests.post(
            config.OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=15
        )
        
        # Handle rate limiting - fallback to paid model
        if response.status_code == 429 and not use_fallback:
            print(f"[LLM] Rate limited on {model}, falling back to {config.OPENROUTER_FALLBACK_MODEL}")
            return completion(prompt, model=None, temperature=temperature, max_tokens=max_tokens, 
                            system_prompt=system_prompt, use_fallback=True)
        
        if response.status_code >= 400:
            err_msg = f"[LLM] Error: {response.status_code} - {response.text[:200]}"
            print(err_msg)
            with open("/tmp/llm_debug.log", "a") as f:
                f.write(err_msg + "\n")
            # Try fallback if not already using it
            if not use_fallback:
                print(f"[LLM] Retrying with fallback model {config.OPENROUTER_FALLBACK_MODEL}...")
                return completion(prompt, model=None, temperature=temperature, max_tokens=max_tokens,
                                system_prompt=system_prompt, use_fallback=True)
            return "I'm having trouble responding right now. Please try again."
        
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            _last_used_model = model
            return result['choices'][0]['message']['content']
        
        print(f"[LLM] Unexpected response: {result}")
        return "I'm having trouble responding right now."
        
    except requests.exceptions.Timeout:
        print("[LLM] Timeout")
        return "The request timed out. Please try again."
        
    except requests.exceptions.RequestException as e:
        print(f"[LLM] Connection error: {e}")
        return "I'm having trouble connecting right now. Please try again."
        
    except Exception as e:
        print(f"[LLM] Unexpected error: {e}")
        return "Something went wrong. Please try again."


def completion_with_tools(messages, tools=None, system_prompt=None, model=None,
                          temperature=None, max_tokens=None):
    """
    LLM completion with tool/function calling support (OpenAI-compatible format).

    Args:
        messages: list of {"role": ..., "content": ...} dicts (no system msg)
        tools: list of tool defs in OpenAI format {"type":"function","function":{...}}
        system_prompt: injected as the first system message
        model: defaults to config.OPENROUTER_TOOLS_MODEL

    Returns dict:
        {
          "stop_reason": "end_turn" | "tool_calls",
          "text":        str | None,   # assistant text, None when only tool calls
          "tool_uses":   [{"id","name","input"}, ...],
          "raw_content": dict,         # full assistant message for appending to history
          "error":       str | None
        }
    """
    model = model or config.OPENROUTER_TOOLS_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS

    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    payload = {
        "model": model,
        "messages": all_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://greendial.org",
        "X-Title": "GreenDial",
    }

    def _err(msg):
        return {"stop_reason": "end_turn", "text": None, "tool_uses": [], "raw_content": None, "error": msg}

    try:
        print(f"[LLM Tools] Calling {model} (tools={len(tools or [])})...")
        resp = requests.post(config.OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)

        if resp.status_code == 429:
            # Rate-limited on tools model → retry with fallback (also supports tools)
            if model != config.OPENROUTER_FALLBACK_MODEL:
                print(f"[LLM Tools] Rate limited, retrying with {config.OPENROUTER_FALLBACK_MODEL}")
                return completion_with_tools(messages, tools=tools, system_prompt=system_prompt,
                                             model=config.OPENROUTER_FALLBACK_MODEL,
                                             temperature=temperature, max_tokens=max_tokens)
            return _err("rate_limited")

        if resp.status_code >= 400:
            print(f"[LLM Tools] Error {resp.status_code}: {resp.text[:300]}")
            # Hard errors: try fallback once
            if model != config.OPENROUTER_FALLBACK_MODEL:
                print(f"[LLM Tools] Falling back to {config.OPENROUTER_FALLBACK_MODEL}")
                return completion_with_tools(messages, tools=tools, system_prompt=system_prompt,
                                             model=config.OPENROUTER_FALLBACK_MODEL,
                                             temperature=temperature, max_tokens=max_tokens)
            return _err(f"http_{resp.status_code}")

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")

        text = msg.get("content")           # may be None when only tool calls present
        raw_tool_calls = msg.get("tool_calls") or []

        # Parse tool calls
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

        # Build raw_content for appending back to message history
        raw_content = {"role": "assistant", "content": text}
        if raw_tool_calls:
            raw_content["tool_calls"] = raw_tool_calls

        _last_used_model = model
        return {
            "stop_reason": "tool_calls" if (finish_reason == "tool_calls" or tool_uses) else "end_turn",
            "text": text,
            "tool_uses": tool_uses,
            "raw_content": raw_content,
            "model_used": model,
            "error": None,
        }

    except requests.exceptions.Timeout:
        print("[LLM Tools] Timeout")
        return _err("timeout")
    except Exception as e:
        print(f"[LLM Tools] Unexpected error: {e}")
        return _err(str(e))


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
