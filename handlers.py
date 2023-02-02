import redis, openai, utils, config, requests, json

redis = redis.StrictRedis()

def add_data(request):
    redis.hset(config.REDHASH_USER_DATA, req.get("user_id"), req.get("event_data"))
    return '{"message" : "ok"}'

def get_data(request):
    data = json.loads(redis.hget(config.REDHASH_USER_DATA, req.get("user_id")))
    return json.dumps(data)

def get_history(request):
    return ""
    user_id = request.get("user_id")
    res = json.loads(redis.hget(config.REDHASH_CHAT_HISTORY, user_id))
    history = res.get('history', [])    
    return '\n'.join(history)

def update_history(request, out_text):
    user_id = request.get("user_id")
    try:
        res = json.loads(redis.hget(config.REDHASH_CHAT_HISTORY, user_id))
        res['history'].append(out_text)
    except:
        res = {'history' : [out_text]}
    redis.hset(config.REDHASH_CHAT_HISTORY, user_id, json.dumps(res)) 
 
def chat(request):
    in_text = "User: " + request.get("text","")
    chat_history = get_history(request) 
    data={
        "model": "text-davinci-003",
        #"prompt": "%s" % utils.chat_preamble % (chat_history, text),
        "prompt": utils.chat_preamble % (chat_history, in_text), 
        "temperature": 0,
        "max_tokens": 200
    }

    headers = {"Authorization": "Bearer %s" % config.openai_api_key, "Content-Type" : "application/json"}
    resp = requests.post(config.openai_url, headers=headers, json=data)
    out_text = "Bot: " + resp.json().get("choices", [])[0].get('text')
    update_history(request, out_text) 
    return out_text 
        
