"""
Utilities Module
Configurable LLM completion with Ollama fallback
"""
import requests
import config


def _call_ollama(messages, temperature=None, max_tokens=None):
    """Fallback to local Ollama instance"""
    if not config.OLLAMA_ENABLED:
        return None
    
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    
    payload = {
        'model': config.OLLAMA_MODEL,
        'messages': messages,
        'stream': False,
        'options': {
            'temperature': temperature
        }
    }
    if max_tokens:
        payload['options']['num_predict'] = max_tokens
    
    try:
        print(f"[Ollama] Calling {config.OLLAMA_MODEL}...")
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('message', {}).get('content', '')
        else:
            print(f"[Ollama] Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"[Ollama] Connection error: {e}")
        return None


def completion(prompt, model=None, temperature=None, max_tokens=None):
    """
    Call configurable LLM API with Ollama fallback.
    
    Flow:
    1. Try configured LLM_API_URL (OpenRouter, OpenAI, etc.)
    2. On error/429, fallback to Ollama if enabled
    3. Return error message if both fail
    """
    model = model or config.LLM_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    
    messages = [{"role": "user", "content": prompt}]
    
    # If no API key, try Ollama directly
    if not config.LLM_API_KEY:
        print("[LLM] No API key configured, trying Ollama...")
        result = _call_ollama(messages, temperature, max_tokens)
        if result:
            return result
        return "I'm having trouble connecting. Please check the LLM configuration."
    
    # Try primary LLM API
    headers = {
        'Authorization': f"Bearer {config.LLM_API_KEY}",
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://greendial.app',
        'X-Title': 'GreenDial'
    }
    
    payload = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens
    }
    
    try:
        print(f"[LLM] Calling {config.LLM_API_URL}...")
        response = requests.post(
            config.LLM_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        # Rate limited or error - try Ollama fallback
        if response.status_code == 429:
            print("[LLM] Rate limited (429), trying Ollama fallback...")
            result = _call_ollama(messages, temperature, max_tokens)
            if result:
                return result
            return "I'm being rate limited. Please try again in a moment."
        
        if response.status_code >= 400:
            print(f"[LLM] Error: {response.status_code} - {response.text[:200]}")
            result = _call_ollama(messages, temperature, max_tokens)
            if result:
                return result
            return "I'm having trouble responding right now. Please try again."
        
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        
        print(f"[LLM] Unexpected response: {result}")
        return "I'm having trouble responding right now."
        
    except requests.exceptions.Timeout:
        print("[LLM] Timeout, trying Ollama fallback...")
        result = _call_ollama(messages, temperature, max_tokens)
        if result:
            return result
        return "The request timed out. Please try again."
        
    except requests.exceptions.RequestException as e:
        print(f"[LLM] Connection error: {e}")
        result = _call_ollama(messages, temperature, max_tokens)
        if result:
            return result
        return "I'm having trouble connecting right now. Please try again."
        
    except Exception as e:
        print(f"[LLM] Unexpected error: {e}")
        return "Something went wrong. Please try again."
