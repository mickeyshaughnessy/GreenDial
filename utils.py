import requests, config

def completion(text):
    data = {
        "model": "text-davinci-003",
        "prompt": text,
        "temperature": 0,
        "max_tokens": 200
    }
    headers = {
        "Authorization": "Bearer %s" % config.openai_api_key,
        "Content-Type" : "application/json"
    }
    resp = requests.post(config.openai_url, headers=headers, json=data)
    out_text = resp.json().get("choices", [])[0].get('text')
    return out_text 
