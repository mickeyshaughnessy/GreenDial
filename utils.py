"""
Utilities Module - Worker Droid Implementation
OpenRouter completion API wrapper (adapted from love-matcher)
"""
import requests
import config

def completion(text, model=None, temperature=None, max_tokens=None):
    """Call OpenRouter chat completion API"""
    model = model or config.OPENROUTER_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    
    if not config.OPENROUTER_API_KEY:
        return "[No API key configured]"
    
    headers = {
        'Authorization': f"Bearer {config.OPENROUTER_API_KEY}",
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://greendial.org',
        'X-Title': 'GreenDial'
    }
    
    payload = {
        'model': model,
        'messages': [{"role": "user", "content": text}],
        'temperature': temperature,
        'max_tokens': max_tokens
    }
    
    try:
        response = requests.post(
            config.OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code >= 400:
            print(f"OpenRouter error: {response.status_code} - {response.text}")
            return "I'm having trouble responding right now. Please try again."
        
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            print(f"Unexpected response format: {result}")
            return "I'm having trouble responding right now. Please try again."
            
    except requests.exceptions.RequestException as e:
        print(f"OpenRouter API error: {e}")
        return "I'm having trouble connecting right now. Please try again."
    except Exception as e:
        print(f"Unexpected error: {e}")
        return "Something went wrong. Please try again."

def completion_with_history(messages, model=None, temperature=None, max_tokens=None):
    """Call OpenRouter with full message history"""
    model = model or config.OPENROUTER_MODEL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    
    if not config.OPENROUTER_API_KEY:
        return "[No API key configured]"
    
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
        response = requests.post(
            config.OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code >= 400:
            print(f"OpenRouter error: {response.status_code} - {response.text}")
            return "I'm having trouble responding right now. Please try again."
        
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            return "I'm having trouble responding right now. Please try again."
            
    except Exception as e:
        print(f"OpenRouter error: {e}")
        return "Something went wrong. Please try again."
