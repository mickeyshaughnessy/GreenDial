"""
Utilities Module
LLM completion via OpenRouter API
"""
import requests
import config


def completion(prompt, model=None, temperature=None, max_tokens=None, system_prompt=None):
    """
    Call OpenRouter API for LLM completion.
    
    Args:
        prompt: User message content
        model: Model to use (default from config)
        temperature: Sampling temperature
        max_tokens: Max response tokens
        system_prompt: Optional system message (for two-stage calls)
    """
    model = model or config.LLM_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    
    # Build messages array
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    if not config.LLM_API_KEY:
        print("[LLM] No API key configured")
        return "I'm having trouble connecting. Please configure an API key."
    
    headers = {
        'Authorization': f"Bearer {config.LLM_API_KEY}",
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
        print(f"[LLM] Calling {model}...")
        response = requests.post(
            config.LLM_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 429:
            print("[LLM] Rate limited (429)")
            return "I'm being rate limited. Please try again in a moment."
        
        if response.status_code >= 400:
            print(f"[LLM] Error: {response.status_code} - {response.text[:200]}")
            return "I'm having trouble responding right now. Please try again."
        
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
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


def two_stage_completion(user_input, username="Guest", profile=None, recent_transcript=""):
    """
    Two-stage LLM completion:
    1. Supervisor analyzes context and builds dynamic system prompt
    2. Doc responds using the supervisor's instructions
    
    Returns:
        Doc's response string
    """
    from prompts import supervisor
    
    profile = profile or {}
    
    # Stage 1: Supervisor
    print("[LLM] Stage 1: Supervisor analyzing...")
    sup_prompt = supervisor.build_supervisor_prompt(user_input, profile, recent_transcript)
    
    supervisor_response = completion(
        prompt=sup_prompt["user"],
        system_prompt=sup_prompt["system"],
        temperature=0.3,  # Lower temp for more consistent JSON
        max_tokens=300
    )
    
    # Parse supervisor output
    sup_output = supervisor.parse_supervisor_response(supervisor_response)
    print(f"[LLM] Supervisor: style={sup_output['style']}, tone={sup_output['tone']}, action={sup_output['profile_action']}")
    
    # Stage 2: Doc
    print("[LLM] Stage 2: Doc responding...")
    doc_system = supervisor.build_doc_prompt(sup_output, username, profile, recent_transcript)
    
    doc_response = completion(
        prompt=user_input,
        system_prompt=doc_system,
        temperature=0.8,
        max_tokens=300
    )
    
    return doc_response
