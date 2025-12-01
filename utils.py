"""
Utilities Module
LLM completion via OpenRouter API
"""
import requests
import config


def completion(prompt, model=None, temperature=None, max_tokens=None):
    """
    Call OpenRouter API for LLM completion.
    """
    model = model or config.LLM_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    
    messages = [{"role": "user", "content": prompt}]
    
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
